# -*- coding: utf-8 -*-
"""O instalador do Inno Setup -- o que so o `.iss` sabe.

Nada aqui compila o instalador: isso exige Windows com o Inno Setup 6. O que
da para provar sem compilar e justamente o que mais quebra na pratica, e cada
item abaixo custou uma rodada de CI -- ou uma instalacao travada -- a alguem:

  - o `AppMutex`, que TRAVAVA a instalacao por causa de um SIG-FT fantasma
    (secao A: quem fecha o app e o Restart Manager);
  - `VersionInfoVersion` com sufixo de pre-lancamento (o compilador ABORTA);
  - `[InstallDelete]` apontando para `{app}` sozinho (apaga o `unins000.dat`
    e o app deixa de ser desinstalavel pelo caminho normal);
  - `AppUserModelID` divergente (o Windows mostra DOIS botoes na barra de
    tarefas para o mesmo programa).
"""
import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ISS = RAIZ / "installer" / "sigft.iss"


@pytest.fixture(scope="module")
def iss():
    if not ISS.is_file():
        pytest.fail(f"{ISS.relative_to(RAIZ)} nao existe")
    return ISS.read_text(encoding="utf-8", errors="strict")


def _diretiva(texto, nome):
    """O valor de `Nome=valor` numa secao do .iss."""
    m = re.search(rf"^{nome}\s*=\s*(.+?)\s*$", texto, re.M | re.I)
    return m.group(1) if m else None


# =============================================================================
# A. Instalar por cima do app aberto -- sem AppMutex  [2026-09-25]
# =============================================================================
#
# O Windows nao deixa sobrescrever um `.exe` em execucao, entao o instalador
# precisa fechar o SIG-FT antes de trocar os arquivos. Ate 2026-09-25 isso era
# o `AppMutex`, e ele TRAVOU a instalacao da 1.1.1-rc.1: "o instalador detectou
# que o SIG-FT Itaipu esta atualmente em execucao", com o SIG-FT fechado.
#
# Havia um SIG-FT.exe vivo SEM JANELA (robo parado numa pausa quando a pessoa
# fechou o app -- `tests/test_fechar_encerra_o_processo.py`). O `AppMutex` so
# pergunta "existe um mutex com esse nome?": nao distingue app aberto de
# fantasma, nem da copia do ZIP do Box rodando de OUTRA pasta, e nao oferece
# fechar -- so "feche e clique OK", que a pessoa nao tinha como atender. Em
# modo silencioso (a atualizacao automatica), abortava sozinho.
#
# O Restart Manager (`CloseApplications`) pergunta a coisa certa: QUEM esta
# usando os arquivos que vao ser trocados. Mostra o app na pagina "Preparando
# para instalar", fecha com um clique e, com `force`, encerra ate o fantasma,
# que nao tem janela para receber o pedido de fechar.

def test_o_iss_NAO_usa_AppMutex(iss):
    assert _diretiva(iss, "AppMutex") is None, (
        "AppMutex trava a instalacao por causa de SIG-FT fantasma (sem janela) "
        "ou da copia do Box -- ver o comentario desta secao"
    )


def test_o_instalador_FECHA_o_app_ate_o_fantasma(iss):
    """`force`: o fantasma nao tem janela para receber o pedido de fechar;
    sem forcar, o Restart Manager desiste dele e a troca dos arquivos falha."""
    assert (_diretiva(iss, "CloseApplications") or "").lower() == "force"


# =============================================================================
# B. A versao -- armadilha n. 2
# =============================================================================

def test_a_versao_de_exibicao_vem_de_fora(iss):
    """O workflow passa `/DMyAppVersion=`; o valor no arquivo e so o default."""
    assert "MyAppVersion" in iss
    assert "#ifndef MyAppVersion" in iss, (
        "sem o #ifndef, o valor do arquivo ganharia do que o workflow passa"
    )


def test_a_versao_BINARIA_e_separada_da_de_exibicao(iss):
    """Armadilha n. 2: `VersionInfoVersion` so aceita DIGITOS.

    Uma versao `1.0.0-rc.1` faz o Inno abortar com 'Value of [Setup] section
    directive "VersionInfoVersion" is invalid'. Entao um pre-lancamento tem
    DUAS versoes: a de exibicao, com sufixo, e a binaria, so numerica.
    """
    assert _diretiva(iss, "VersionInfoVersion") == "{#MyVersionInfo}", (
        "VersionInfoVersion tem de usar a versao NUMERICA, nao a de exibicao"
    )
    assert "#ifndef MyVersionInfo" in iss


def test_o_iss_CORTA_o_sufixo_de_pre_lancamento_sozinho(iss):
    """O `.iss` calcula a versao binaria em vez de exigir as duas.

    O workflow ja passa `/DMyVersionInfo`, entao no caminho automatico isto
    nunca e exercitado. A conta existe para quem compila A MAO: sem ela,
    `iscc /DMyAppVersion=1.0.0-rc.1` aborta, e a mensagem do Inno nao diz que
    o problema e o sufixo -- gasta-se uma tarde nisso.
    """
    assert 'Pos("-", MyAppVersion)' in iss, (
        "o .iss precisa cortar o sufixo de pre-lancamento sozinho"
    )
    assert "Copy(MyAppVersion" in iss


def test_nenhum_default_de_versao_tem_sufixo(iss):
    """O valor escrito no arquivo tambem nao pode ter sufixo."""
    for m in re.finditer(r'#define\s+My(?:AppVersion|VersionInfo)\s+"([^"]+)"', iss):
        assert "-" not in m.group(1), (
            f"o default `{m.group(1)}` tem sufixo de pre-lancamento; como "
            f"VersionInfoVersion, o Inno o recusa"
        )


# =============================================================================
# C. O escopo da instalacao -- o que voce pediu
# =============================================================================

def test_o_instalador_PERGUNTA_o_escopo(iss):
    """Pedido do usuario: Program Files como padrao, mas ele PERGUNTA.

    Quem nao tem senha de administrador escolhe "somente para mim", vai para
    %LOCALAPPDATA%\\Programs, e ai a atualizacao automatica roda sem nenhum
    popup do UAC.
    """
    assert (_diretiva(iss, "PrivilegesRequired") or "").lower() == "admin"

    permitido = (_diretiva(iss, "PrivilegesRequiredOverridesAllowed") or "").lower()
    assert "dialog" in permitido, (
        "sem `dialog` o instalador NAO pergunta -- exige admin e pronto"
    )


def test_o_padrao_e_program_files(iss):
    assert "{autopf}" in (_diretiva(iss, "DefaultDirName") or "")


# =============================================================================
# D. `[InstallDelete]` -- a armadilha do Corella
# =============================================================================

def _entradas_de(iss, secao):
    """As linhas `Type: ...; Name: "..."` de uma secao, como pares."""
    m = re.search(rf"^\[{secao}\]$(.*?)(?=^\[|\Z)", iss, re.M | re.S)
    if not m:
        return []
    return [
        (tipo.strip().lower(), nome.strip())
        for tipo, nome in re.findall(
            r'Type:\s*([A-Za-z]+)\s*;\s*Name:\s*"([^"]+)"', m.group(1))
    ]


def _alvos_de(iss, secao):
    return [nome for _tipo, nome in _entradas_de(iss, secao)]


@pytest.mark.parametrize("secao", ["InstallDelete", "UninstallDelete"])
def test_nunca_apagar_app_sozinho(iss, secao):
    """A armadilha que o Corella Suite documentou, e ela e severa.

    Em `{app}` mora o `unins000.dat` -- o registro do que o instalador
    escreveu. Apagando-o, a entrada em Programas e Recursos fica orfa e o
    aplicativo deixa de ser desinstalavel pelo caminho normal. O usuario fica
    com um programa que nao sai da maquina.
    """
    for tipo, alvo in _entradas_de(iss, secao):
        if alvo.strip() not in ("{app}", "{app}\\*", "{app}/*"):
            continue
        # `dirifempty` e o idioma SEGURO e padrao do Inno: ele so remove a
        # pasta se ela ja estiver vazia, entao nunca alcanca o unins000.dat.
        # O que destroi e apagar conteudo.
        assert tipo == "dirifempty", (
            f"[{secao}] tem `Type: {tipo}` sobre `{alvo}`. Isso apagaria o "
            f"unins000.dat -- o registro do que o instalador escreveu -- e a "
            f"entrada em Programas e Recursos ficaria orfa: o SIG-FT deixaria "
            f"de ser desinstalavel pelo caminho normal."
        )


@pytest.mark.parametrize("secao", ["InstallDelete", "UninstallDelete"])
def test_nada_e_apagado_fora_da_pasta_do_programa(iss, secao):
    """Um alvo fora de `{app}` apagaria arquivo de outro programa -- ou, pior,
    a pasta `Documentos\\SIG-FT` com as chaves de API do usuario."""
    for alvo in _alvos_de(iss, secao):
        assert alvo.startswith("{app}"), (
            f"[{secao}] aponta para fora da pasta do programa: {alvo}"
        )


def test_o_installdelete_limpa_o_internal_do_build_anterior(iss):
    """O Inno sobrescreve o que esta em [Files], mas NAO apaga o que sumiu
    entre uma versao e outra. Sem isto, `_internal\\` acumula modulo orfao."""
    alvos = " ".join(_alvos_de(iss, "InstallDelete"))

    assert "_internal" in alvos


# =============================================================================
# E. A pasta de dados do usuario NUNCA e tocada
# =============================================================================

def test_nenhuma_DIRETIVA_alcanca_a_pasta_de_dados(iss):
    """`Documentos\\SIG-FT` guarda as chaves de API e as preferencias.

    A Frente 3 inteira existe para instalar, atualizar e desinstalar nao
    encostarem nelas. Um `[UninstallDelete]` apontando para la desfaria isso
    -- e o usuario perderia as chaves ao desinstalar uma versao para reinstalar
    outra.

    A checagem e sobre as secoes que MEXEM EM DISCO, e nao sobre o texto do
    arquivo, por dois motivos que ja me pegaram duas vezes aqui:

    1. o `.iss` EXPLICA num comentario por que a pasta fica intocada -- e deve
       mesmo, e o que impede alguem de acrescentar a linha. Uma busca por
       substring reprovaria a propria explicacao (mesmo erro do guard do
       `_build_info.py`);
    2. a mensagem final DIZ ao usuario onde as chaves dele ficam. Isso e
       informacao util, nao alvo de remocao -- `[Messages]` e texto de tela.

    O risco real e uma OPERACAO DE ARQUIVO alcancar a pasta.
    """
    secoes_que_mexem_em_disco = ("Files", "Dirs", "InstallDelete", "UninstallDelete")
    proibidos = ("{userdocs}", "{usersavedgames}", "SIGFT_DADOS_DIR",
                 "Documentos\\SIG-FT", "SIG-FT\\api_config")

    for secao in secoes_que_mexem_em_disco:
        m = re.search(rf"^\[{secao}\]$(.*?)(?=^\[|\Z)", iss, re.M | re.S)
        if not m:
            continue
        linhas = "\n".join(
            linha for linha in m.group(1).splitlines()
            if linha.strip() and not linha.lstrip().startswith(";")
        )
        for proibido in proibidos:
            assert proibido not in linhas, (
                f"[{secao}] alcanca `{proibido}` -- a pasta de dados do usuario "
                f"(chaves de API, preferencias) tem de ficar intocada por "
                f"instalar, atualizar E desinstalar"
            )


# =============================================================================
# F. O que o instalador precisa achar
# =============================================================================

def test_o_iss_empacota_a_pasta_do_pyinstaller(iss):
    assert "dist\\SIG-FT" in iss or "dist/SIG-FT" in iss


def test_o_changelog_viaja_junto(iss):
    """A janela de novidades le o CHANGELOG.md; sem ele no pacote ela fica
    vazia depois de atualizar."""
    assert "CHANGELOG.md" in iss


def test_o_icone_do_instalador_existe_no_repositorio(iss):
    """Caminho de icone errado faz o ISCC abortar -- e so na hora do release."""
    if not (m := re.search(r"^SetupIconFile\s*=\s*(.+?)\s*$", iss, re.M)):
        pytest.skip("o instalador nao define um icone proprio")

    # O caminho no `.iss` e relativo a `installer/`, e comeca com `..`.
    # (Um `lstrip("./")` aqui comeria o `..` e o teste reprovaria um icone
    # que existe -- foi o que a primeira versao dele fez.)
    relativo = m.group(1).replace("\\", "/")
    assert (ISS.parent / relativo).resolve().is_file(), (
        f"SetupIconFile aponta para {m.group(1)}, que nao existe"
    )


# =============================================================================
# G. AppUserModelID -- o botao duplicado na barra de tarefas
# =============================================================================

def test_o_AppUserModelID_do_atalho_bate_com_o_do_app(iss):
    """Divergindo, o Windows trata o atalho fixado e a janela aberta como DOIS
    aplicativos e mostra dois botoes lado a lado. E a versao nao entra no ID:
    muda-lo a cada atualizacao quebraria o atalho fixado."""
    from sigft.core import instancia

    ids = re.findall(r'AppUserModelID:\s*"([^"]+)"', iss)
    if not ids:
        pytest.skip("o instalador nao declara AppUserModelID")

    assert set(ids) == {instancia.APP_USER_MODEL_ID}
    assert not re.search(r"\d+\.\d+\.\d+", instancia.APP_USER_MODEL_ID), (
        "a versao nao pode entrar no AppUserModelID"
    )


# =============================================================================
# H. A atualizacao automatica REABRE o app  [2026-09-25]
# =============================================================================
#
# A atualizacao roda o instalador em `/SILENT` (`sigft/services/updater.py`).
# Nesse modo a linha do `[Run]` que abre o app -- `postinstall skipifsilent` --
# NAO roda: o app fechava para atualizar e nao voltava. Nada no repositorio
# podia mostrar isso, porque ate aqui ninguem chamava a atualizacao.

def _entradas_run(iss):
    """As entradas do `[Run]`, com as linhas continuadas por `\\` juntadas."""
    m = re.search(r"^\[Run\]$(.*?)(?=^\[|\Z)", iss, re.M | re.S)
    if not m:
        return []
    texto = re.sub(r"\\\s*\n\s*", " ", m.group(1))
    return [linha.strip() for linha in texto.splitlines()
            if linha.strip() and not linha.lstrip().startswith(";")]


def _flags(entrada):
    m = re.search(r"Flags:\s*([^;]+)", entrada, re.I)
    return set(m.group(1).lower().split()) if m else set()


def _entrada_que_reabre(iss):
    candidatas = [e for e in _entradas_run(iss)
                  if "{#AppExe}" in e and "skipifsilent" not in _flags(e)]
    assert len(candidatas) == 1, (
        "o [Run] precisa de UMA entrada que abra o app SEM `skipifsilent` -- "
        "e a que reabre depois da atualizacao silenciosa"
    )
    return candidatas[0]


def test_ha_uma_entrada_que_reabre_o_app_depois_da_atualizacao(iss):
    entrada = _entrada_que_reabre(iss)

    assert "nowait" in _flags(entrada), (
        "sem `nowait` o instalador ficaria esperando o app FECHAR para terminar")


def test_o_app_reaberto_sobe_na_conta_de_QUEM_USAVA(iss):
    """Sem `runasoriginaluser`, no app instalado 'para todos' o SIG-FT reaberto
    herdaria o administrador do UAC -- e, com a senha de outra pessoa, abriria
    na conta dela, sem as chaves de API."""
    assert "runasoriginaluser" in _flags(_entrada_que_reabre(iss))


def test_a_reabertura_so_acontece_a_pedido_do_app(iss):
    """A TI pode instalar em massa com `/SILENT`. Sem a condicao, o SIG-FT
    abriria sozinho na maquina de todo mundo no meio da distribuicao."""
    entrada = _entrada_que_reabre(iss)
    m = re.search(r"Check:\s*(\w+)", entrada)
    assert m, "a entrada que reabre tem de ter um `Check:`"

    funcao = m.group(1)
    codigo = re.search(r"^\[Code\]$(.*)", iss, re.M | re.S)
    assert codigo, "o `Check:` aponta para uma funcao que o [Code] tem de definir"
    assert re.search(rf"function\s+{funcao}\b", codigo.group(1), re.I), (
        f"a funcao `{funcao}` do `Check:` nao existe no [Code]")


def test_o_parametro_que_o_iss_le_e_O_MESMO_que_o_app_manda(iss):
    """Os dois lados divergindo nao dao erro nenhum: so fazem o app nao
    reabrir depois de atualizar."""
    from sigft.services import updater

    m = re.search(r"\{param:(\w+)\|", iss)
    assert m, "o [Code] tem de ler o parametro com `{param:NOME|padrao}`"

    assert updater.ARG_REABRIR.lower() == f"/{m.group(1)}=1".lower()
