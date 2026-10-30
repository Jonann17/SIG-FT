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
# C. O escopo da instalacao: sempre "so para mim"  [2026-10-27]
# =============================================================================
#
# Ate 2026-10-27 o padrao era Program Files (`admin`) e o instalador PERGUNTAVA
# o escopo (`dialog`). O usuario pediu o contrario: "eliminar o que esta em
# Program Files e basear tudo so no que fazemos agora". A atualizacao por
# arquivos (a do CMI Suite) so funciona com a pasta do programa gravavel, e
# isso so existe na instalacao por usuario.
#
# Quem ja estava em Program Files e MIGRADO pelo instalador completo: instala
# a copia do usuario e, no `ssPostInstall`, roda elevado o desinstalador
# antigo. Sem isso, ficariam duas copias, e o atalho publico abriria a velha,
# que ofereceria a atualizacao de novo, sem fim.

def _codigo(texto):
    m = re.search(r"^\[Code\]$(.*)", texto, re.M | re.S)
    assert m, "o .iss nao tem [Code]"
    return m.group(1)


def _rotina(texto, cabecalho):
    """O corpo de uma `function`/`procedure` do [Code], ate o `end;` da coluna 0."""
    m = re.search(rf"{cabecalho}.*?\nbegin\n(.*?)\nend;", _codigo(texto), re.S | re.I)
    return m.group(1) if m else None


def test_o_instalador_COMPLETO_e_SEMPRE_por_usuario_sem_pergunta(iss_completo):
    assert (_diretiva(iss_completo, "PrivilegesRequired") or "").lower() == "lowest"

    permitido = (_diretiva(iss_completo, "PrivilegesRequiredOverridesAllowed") or "").lower().split()
    assert "dialog" not in permitido, "com `dialog` o instalador volta a perguntar o escopo"
    assert permitido == ["commandline"], "o app passa /CURRENTUSER explicito: a linha de comando tem de valer"


def test_a_pasta_padrao_e_a_do_usuario(iss):
    """Com `lowest`, `{autopf}` e `%LOCALAPPDATA%\\Programs`; um `{pf}` ou
    `{commonpf}` fixo levaria a Program Files, sem permissao de escrita."""
    pasta = _diretiva(iss, "DefaultDirName") or ""
    assert pasta.startswith("{autopf}")


def test_a_migracao_roda_DEPOIS_de_instalar_a_copia_do_usuario(iss):
    corpo = _rotina(iss, r"procedure\s+CurStepChanged\s*\(\s*CurStep\s*:\s*TSetupStep\s*\);")
    assert corpo is not None, "sem CurStepChanged, a copia de Program Files fica para tras"
    assert re.search(r"CurStep\s*=\s*ssPostInstall", corpo)
    assert "MigrarDaInstalacaoParaTodos" in corpo


def test_a_migracao_le_o_desinstalador_da_chave_em_HKLM(iss):
    corpo = _rotina(iss, r"function\s+DesinstaladorParaTodos\b[^;]*;")
    assert corpo is not None
    assert "HKLM64" in corpo and "HKLM32" in corpo
    assert "ChaveDesinstalar" in corpo and "'UninstallString'" in corpo
    assert "HKCU" not in corpo, "a chave do usuario e a da copia NOVA -- nunca desinstale ela"


def test_a_migracao_desinstala_ELEVADO_silencioso_e_ESPERA(iss):
    corpo = _rotina(iss, r"procedure\s+MigrarDaInstalacaoParaTodos\s*;")
    assert corpo is not None
    chamada = re.search(r"ShellExec\((.*?)\);", corpo, re.S)
    assert chamada, "o desinstalador antigo tem de ser chamado com ShellExec (runas)"
    args = chamada.group(1)
    assert "'runas'" in args, "Program Files e HKLM so saem com administrador"
    for parametro in ("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"):
        assert parametro in args
    assert "ewWaitUntilTerminated" in args
    # Instalado elevado pela TI (/ALLUSERS), a chave de HKLM e a da propria
    # instalacao: desinstala-la apagaria o que acabou de ser instalado.
    assert re.search(r"if\s+IsAdminInstallMode\s+or", corpo)


def test_a_migracao_que_falha_NAO_derruba_a_instalacao(iss):
    """UAC recusado ou desinstalador com erro: a copia do usuario ja esta
    instalada e funciona. Vai para o log -- nada de `Abort` nem excecao."""
    corpo = _rotina(iss, r"procedure\s+MigrarDaInstalacaoParaTodos\s*;")
    assert "Log(" in corpo
    for proibido in ("Abort", "RaiseException"):
        assert proibido not in corpo


def test_a_migracao_recusada_AVISA_quem_esta_vendo_e_so_loga_no_silencioso(iss):
    """[2026-10-27, I1] Sem o aviso, quem recusou o UAC (ou nao tem a senha)
    ficaria com duas copias sem saber. Uma caixa so, informativa, e so fora
    do modo silencioso; no silencioso, so o log."""
    corpo = _rotina(iss, r"procedure\s+MigrarDaInstalacaoParaTodos\s*;")
    assert corpo.count("MsgBox(") == 1
    aviso = re.search(r"if\s+not\s+WizardSilent\s+then\s+MsgBox\((.*?)\)\s*else\s+Log\(", corpo, re.S)
    assert aviso, "a caixa so aparece fora do silencioso, e o silencioso vai para o log"
    texto = aviso.group(1)
    assert "mbInformation" in texto
    for trecho in ("Program Files", "Aplicativos", "SIG-FT Itaipu", "administrador"):
        assert trecho in texto
    # So quando a remocao NAO aconteceu.
    assert re.search(r"if\s+not\s+Removida\s+then", corpo)


def test_o_InitializeSetup_continua_criando_o_sinal_sem_relancar(iss):
    """A migracao e no fim; o InitializeSetup so cria o /SINAL, logo ao subir
    -- e e ele que fecha o app antigo antes de a migracao rodar."""
    corpo = _initialize_setup(iss)
    assert "SaveStringToFile" in corpo
    assert "ShellExec" not in corpo and "Exec(" not in corpo
    assert re.search(r"Result\s*:=\s*True", corpo)


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


# =============================================================================
# I. Sem o instalador PEQUENO  [2026-10-30]
# =============================================================================
# O modo atualizacao (/DAtualizacao=1, de 2026-10-07 a 2026-10-30) saiu: a
# atualizacao pequena e o .zip de arquivos que o app aplica, como no
# DocManager. O .iss gera so o completo; `_preprocessar` fica porque o
# `iss_completo` e o que o ISPP entrega ao Inno.

def _preprocessar(texto, definidos=()):
    """O que o ISPP entrega ao Inno com estes `/D`. So `#ifdef`, `#ifndef`,
    `#else` e `#endif` sao avaliados; um `#if <expressao>` fica com as duas
    pernas (so aparece no calculo da versao, no topo)."""
    saida, pilha = [], []
    for linha in texto.splitlines():
        s = linha.strip()
        if s.startswith(("#ifdef ", "#ifndef ")):
            nome = s.split()[1]
            pilha.append([(nome in definidos) == s.startswith("#ifdef "), True])
            continue
        if s.startswith("#if "):
            pilha.append([True, False])
            continue
        if s == "#else":
            if pilha[-1][1]:
                pilha[-1][0] = not pilha[-1][0]
            continue
        if s == "#endif":
            pilha.pop()
            continue
        if all(ativo for ativo, _ in pilha):
            saida.append(linha)
    return "\n".join(saida)


@pytest.fixture(scope="module")
def iss_completo(iss):
    return _preprocessar(iss)


def test_o_modo_pequeno_saiu(iss):
    assert "Atualizacao" not in re.findall(r"^\s*#\w+\s+(\w+)", iss, re.M)
    assert "#include" not in iss
    assert "PrepareToInstall" not in iss and "VersaoDe" not in iss


def test_o_completo_continua_como_era(iss_completo):
    alvos = _alvos_de(iss_completo, "InstallDelete")
    assert "{app}\\_internal" in alvos
    assert 'Source: "..\\dist\\SIG-FT\\*"' in iss_completo
    assert "atualizacao_" not in iss_completo


def test_o_nome_de_saida_e_o_que_o_build_espera(iss_completo):
    release = (RAIZ / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert f"installer/Output/{_diretiva(iss_completo, 'OutputBaseFilename')}.exe" in release


# =============================================================================
# J. O instalador avisa que SUBIU (`/SINAL`)  [2026-10-27]
# =============================================================================
# Ver docs/superpowers/specs/2026-10-27-atualizacao-como-cmi-design.md. O app
# so fecha depois que o `InitializeSetup` cria o arquivo de `/SINAL`; se o
# nome do parametro divergir, o arquivo nunca aparece e TODA atualizacao pelo
# instalador termina em `InstaladorNaoIniciou` depois de 10 minutos.

def _initialize_setup(texto):
    m = re.search(r"function\s+InitializeSetup\s*\(\s*\)\s*:\s*Boolean;(.*?)\nend;",
                  texto, re.S | re.I)
    return m.group(1) if m else None


def test_o_parametro_do_sinal_e_O_MESMO_que_o_app_manda(iss):
    from sigft.services import updater

    corpo = _initialize_setup(iss)
    assert corpo is not None, "sem InitializeSetup, o app espera o sinal ate o tempo limite"
    m = re.search(r"\{param:(\w+)\|", corpo)
    assert m and m.group(1).upper() == updater.PARAM_SINAL.upper()
    assert "SaveStringToFile" in corpo
    assert re.search(r"Result\s*:=\s*True", corpo)


def test_o_completo_cria_o_sinal(iss_completo):
    assert _initialize_setup(iss_completo) is not None


def test_a_chave_do_desinstalador_e_a_que_o_app_regrava(iss):
    """A atualizacao por arquivos regrava `DisplayVersion` (e `DisplayName`)
    na chave que o instalador completo escreve."""
    from sigft.services import updater

    m = re.search(r"ChaveDesinstalar\s*=\s*'([^']+)'", iss)
    assert m and m.group(1) == updater.CHAVE_DESINSTALAR
    assert _diretiva(iss, "AppId").lstrip("{") in updater.CHAVE_DESINSTALAR
    assert _diretiva(iss, "AppVerName") == "{#AppName} {#MyAppVersion}"
    assert re.search(r'#define AppName "([^"]+)"', iss).group(1) == updater.NOME_APP
    assert re.search(r'#define AppExe "([^"]+)"', iss).group(1) == updater.EXECUTAVEL
