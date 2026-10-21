# -*- coding: utf-8 -*-
"""Nada do usuario pode ser gravado na PASTA DO PROGRAMA.

O DEFEITO QUE ORIGINOU ESTE ARQUIVO (2026-09-21, primeira instalacao real)
---------------------------------------------------------------------------
O app instalado abria e **nenhum modulo funcionava**. O sintoma exato, do
usuario: "a janela de escolher arquivo abre, eu escolho o _STATUS_PMIB, e o
botao nao fica verde -- nao acontece nada".

O caminho:

    def _abrir_dialogo(self):
        caminho = file_dialogs.ask_open_file(...)   # <- levanta aqui
        if not caminho:
            return
        self.definir(caminho, os.path.basename(caminho))   # nunca chega

Dentro de `ask_open_file`, depois de o usuario ja ter escolhido o arquivo:

    prefs.remember_dir(chave, categoria, os.path.dirname(caminho),
                       config_path=config_path)

`config_path` vinha do default da propria funcao:

    config_path: str | os.PathLike[str] = prefs.CONFIG_FILE   # "user_prefs.json"

e `prefs.CONFIG_FILE` e o **NOME** do arquivo, nao um caminho. O `prefs`
passou a resolver o caminho real tardiamente (`config_path=None` ->
`Documentos\\SIG-FT\\`) na Frente 3, mas quem passa o nome cru **anula essa
resolucao**: `open("user_prefs.json", "w")` grava relativo ao DIRETORIO DE
TRABALHO, que no app instalado e `C:\\Program Files\\SIG-FT Itaipu\\`.

Sob `Program Files` um processo sem elevacao nao escreve: `PermissionError`.
A excecao sobe pelo callback do Tk, que a manda para o stderr -- e o
`SIG-FT.spec` usa `console=False`, entao ela sumia. Para o usuario, "nao
acontece nada".

E valia para TODO seletor de TODO modulo, porque todos passam por
`file_dialogs`. Dai "nenhum modulo funciona".

A MESMA causa estava em `core/llm/selecao.py` (8 assinaturas) e nos dois
lugares que a chamam com o nome cru, incluindo um arquivo da frente do
Rafael -- por isso o conserto e no RESOLVEDOR e nao nas assinaturas: assim
o ponto de chamada dele passa a funcionar sem que eu edite o arquivo dele.

POR QUE NENHUM TESTE PEGOU
--------------------------
Porque todo teste passa `config_path` apontando para um `tmp_path`
ABSOLUTO -- justamente a costura que o defeito desliga. O default de
producao, que e o unico caminho que o usuario percorre, nao era exercitado
por ninguem.
"""

import pytest

from sigft.app import file_dialogs
from sigft.core import prefs
from sigft.core.llm import selecao


@pytest.fixture
def instalado(tmp_path, monkeypatch):
    """Reproduz a maquina do usuario: programa numa pasta, dados noutra.

    Devolve `(programa, dados)`. O diretorio de trabalho fica sendo o do
    PROGRAMA, que e o que acontece quando se clica no atalho do menu Iniciar.
    """
    programa = tmp_path / "Program Files" / "SIG-FT Itaipu"
    dados = tmp_path / "Documentos" / "SIG-FT"
    programa.mkdir(parents=True)
    dados.mkdir(parents=True)

    monkeypatch.setenv("SIGFT_DADOS_DIR", str(dados))
    monkeypatch.chdir(programa)
    return programa, dados


def _recusa_escrita(pasta, nome):
    """Faz `open(nome, "w")` falhar dentro de `pasta`, em qualquer sistema.

    `chmod` nao serve: a suite roda como root no CI, e root ignora a
    permissao. Uma PASTA com o nome do arquivo faz o `open(..., "w")`
    levantar `IsADirectoryError` -- e o ponto do teste e que a gravacao nem
    deveria ser TENTADA ali.
    """
    (pasta / nome).mkdir()


# =============================================================================
# A. O sintoma do usuario, reproduzido
# =============================================================================

def test_escolher_arquivo_FUNCIONA_com_a_pasta_do_programa_sem_escrita(instalado):
    """O caso exato: "escolho o arquivo e o botao nao fica verde".

    Sem o conserto, `ask_open_file` levanta depois de o usuario ja ter
    escolhido, e a tela nunca chega a marcar a selecao.
    """
    programa, _dados = instalado
    _recusa_escrita(programa, prefs.CONFIG_FILE)
    escolhido = r"C:\Users\luan\Downloads\4500063671_STATUS_PMIB.xlsx"

    devolvido = file_dialogs.ask_open_file(
        "analyzer.status_pmib", "excel", dialog_fn=lambda **kw: escolhido)

    assert devolvido == escolhido, (
        "a selecao do usuario nao chegou de volta a tela -- e por isso que o "
        "rotulo nao fica verde e 'nao acontece nada'"
    )


def test_a_preferencia_vai_para_a_pasta_de_DADOS(instalado):
    """A causa raiz, medida onde ela aparece: o arquivo no lugar errado."""
    programa, dados = instalado

    file_dialogs.ask_open_file(
        "analyzer.status_pmib", "excel",
        dialog_fn=lambda **kw: r"C:\Users\luan\Downloads\x_STATUS_PMIB.xlsx")

    assert not (programa / prefs.CONFIG_FILE).exists(), (
        f"gravou na pasta do PROGRAMA ({programa}). Sob `Program Files` isso "
        f"e PermissionError, e a atualizacao apagaria o arquivo."
    )
    assert (dados / prefs.CONFIG_FILE).is_file(), (
        f"a preferencia nao chegou a pasta de dados ({dados})"
    )


@pytest.mark.parametrize("funcao, argumentos", [
    ("ask_open_file", ("k", "excel")),
    ("ask_open_files", ("k", "excel")),
    ("ask_save_file", ("k", "excel")),
    ("ask_directory", ("k", "excel")),
])
def test_NENHUM_dos_quatro_dialogos_escreve_na_pasta_do_programa(
        instalado, funcao, argumentos):
    """Os quatro tinham o mesmo default. Consertar um so deixaria o resto."""
    programa, _dados = instalado
    resultado = (r"C:\Users\luan\Downloads" if funcao == "ask_directory"
                 else r"C:\Users\luan\Downloads\x.xlsx")

    getattr(file_dialogs, funcao)(*argumentos, dialog_fn=lambda **kw: resultado)

    assert not (programa / prefs.CONFIG_FILE).exists(), (
        f"{funcao} gravou na pasta do programa"
    )


# =============================================================================
# B. A escolha de modelo de IA, mesma causa
# =============================================================================

def test_a_escolha_de_modelo_vai_para_a_pasta_de_DADOS(instalado):
    """`selecao` grava no `api_config.json`, e tinha o mesmo default cru.

    Sob `Program Files` isso levanta na hora de salvar, e na hora de LER
    devolve vazio -- o app cairia no modelo padrao sem dizer nada.
    """
    programa, dados = instalado
    from sigft import config

    selecao.definir_por_tarefa("tech_specs", "openrouter", "um/modelo")

    assert not (programa / config.CONFIG_FILE).exists(), (
        "a escolha de modelo foi gravada na pasta do programa"
    )
    assert (dados / config.CONFIG_FILE).is_file()


def test_o_que_foi_escolhido_e_LIDO_de_volta(instalado):
    """Gravar no lugar certo e ler do errado daria o mesmo sintoma."""
    selecao.definir_por_tarefa("tech_specs", "openrouter", "um/modelo")

    assert selecao.resolver("tech_specs")["model"] == "um/modelo"


# =============================================================================
# C. O guard: nome de arquivo NAO e caminho
# =============================================================================

def test_um_nome_puro_e_resolvido_para_a_pasta_de_dados(instalado):
    """A regra, travada.

    `CONFIG_FILE` e o NOME do arquivo -- o proprio comentario dele diz isso.
    Quem passa um nome puro quer O arquivo, nao um arquivo relativo a
    qualquer diretorio de trabalho em que o app tenha sido aberto.
    """
    _programa, dados = instalado

    assert prefs._resolver(prefs.CONFIG_FILE) == str(dados / prefs.CONFIG_FILE)
    assert prefs._resolver(None) == str(dados / prefs.CONFIG_FILE)


def test_um_caminho_de_verdade_continua_intocado(tmp_path, instalado):
    """A costura dos testes nao pode ser atropelada pelo conserto."""
    meu = tmp_path / "outro" / "user_prefs.json"
    meu.parent.mkdir(parents=True)

    assert prefs._resolver(meu) == meu
    assert prefs._resolver(str(meu)) == str(meu)


def test_selecao_tambem_resolve_o_nome_puro(instalado):
    _programa, dados = instalado
    from sigft import config

    assert selecao._resolver(config.CONFIG_FILE) == str(dados / config.CONFIG_FILE)
    assert selecao._resolver(None) == str(dados / config.CONFIG_FILE)


# =============================================================================
# D. O guard capstone: a pasta do programa fica VAZIA
# =============================================================================

def test_a_pasta_do_programa_continua_VAZIA_depois_de_usar_o_app(instalado):
    """A invariante, escrita de uma vez.

    O app instalado mora em `Program Files`, que é somente-leitura para
    usuário comum E é reescrita a cada atualização. Nada que seja do usuário
    pode nascer ali: o que não falhar por permissão some na próxima versão.

    Este teste exercita os DEFAULTS DE PRODUÇÃO -- sem passar `config_path` --,
    que é exatamente o que nenhum outro teste fazia. Todos passavam um
    `tmp_path` absoluto, ou seja, desligavam a única coisa que estava quebrada.
    """
    programa, dados = instalado

    file_dialogs.ask_open_file("k", "excel", dialog_fn=lambda **kw: r"C:\x\a.xlsx")
    file_dialogs.ask_directory("k", "excel", dialog_fn=lambda **kw: r"C:\x")
    selecao.definir_por_tarefa("tech_specs", "openrouter", "um/modelo")
    selecao.definir_global("openrouter", "outro/modelo")

    sujeira = sorted(p.name for p in programa.iterdir())
    assert sujeira == [], (
        f"a pasta do programa recebeu {sujeira}. Sob `Program Files` isso é "
        f"PermissionError -- e o erro some, porque o .exe não tem console."
    )
    assert sorted(p.name for p in dados.iterdir()), (
        "e o outro lado da invariante: os dados TÊM de chegar à pasta do usuário"
    )


def test_os_caches_de_IA_tambem_ficam_fora_do_programa():
    """Os outros nomes de arquivo do pacote, conferidos de uma vez.

    Eles já estavam certos (resolvem por `dados_usuario.caminho`), e o teste
    existe para que continuem: são o mesmo tipo de arquivo, com o mesmo
    destino, e a próxima pessoa a criar um vai copiar de algum destes.
    """
    from sigft.core.llm import catalogo
    from sigft.core.dados_usuario import pasta_dados

    caminho = catalogo.caminho_cache("openrouter")

    assert str(pasta_dados()) in caminho, (
        f"o cache de modelos foi parar em {caminho!r}, fora da pasta de dados"
    )


# =============================================================================
# E. O catálogo do OpenRouter, mesma causa (2026-09-25)
# =============================================================================
#
# O sintoma, do usuário: "configurei a chave do OpenRouter e o catálogo não
# aparece". O botão "Atualizar lista de modelos" buscava a lista, a lista
# CHEGAVA, e o painel voltava dizendo que o catálogo não tinha sido baixado.
#
# O catálogo (`core/llm/catalogo.py`) pede a lista a
# `providers/openrouter.listar_modelos`, que tem um cache PRÓPRIO -- e esse
# ficou para trás quando os dados saíram da pasta do programa (79886e4): o
# default dele era o nome cru `config.OPENROUTER_CATALOGO_CACHE`, gravado
# relativo ao diretório de trabalho. Sob `Program Files` a gravação levanta,
# a exceção leva junto a lista que acabara de chegar, e o `except` largo do
# catálogo a transforma em "nenhum modelo". Gemini e AMP não passam por ali,
# por isso só o OpenRouter sumia.
#
# O teste logo acima não pegou porque confere o CAMINHO que o catálogo
# calcula, e não quem de fato grava.

class _RespostaDoCatalogo:
    """`GET /models` do OpenRouter, no formato da resposta real."""

    def raise_for_status(self):
        pass

    def json(self):
        return {"data": [
            {"id": "minimax/minimax-m3", "name": "MiniMax: MiniMax M3",
             "context_length": 1000000,
             "pricing": {"prompt": "0.0000003", "completion": "0.0000012"}},
            {"id": "x-ai/grok-4.5", "name": "xAI: Grok 4.5",
             "context_length": 256000,
             "pricing": {"prompt": "0.000003", "completion": "0.000015"}},
        ]}


def _get_do_catalogo(url, headers=None, timeout=None):
    # Só responde ao endpoint do OpenRouter: outro ramo do catálogo (Gemini,
    # AMP) não pode satisfazer estes testes por engano.
    assert url == "https://openrouter.ai/api/v1/models", url
    return _RespostaDoCatalogo()


def test_o_catalogo_do_OpenRouter_APARECE_com_a_pasta_do_programa_sem_escrita(instalado):
    """O caminho do botão "Atualizar lista de modelos", do clique à tela.

    O clique busca com `forcar=True`; depois o painel se remonta lendo SÓ o
    cache (`somente_cache=True`). As duas pontas têm de ver a lista.
    """
    programa, _dados = instalado
    from sigft import config
    from sigft.core.llm import catalogo

    _recusa_escrita(programa, config.OPENROUTER_CATALOGO_CACHE)
    chaves = {"OPENROUTER": "sk-or-v1-chave"}

    baixado = catalogo.listar_modelos(
        "openrouter", chaves, forcar=True, http_get=_get_do_catalogo)
    na_tela = catalogo.listar_modelos("openrouter", chaves, somente_cache=True)

    assert baixado == ["minimax/minimax-m3", "x-ai/grok-4.5"], (
        "a lista chegou da rede e foi descartada -- é o 'catálogo não aparece'"
    )
    assert na_tela == ["minimax/minimax-m3", "x-ai/grok-4.5"]


def test_o_cache_do_provedor_OpenRouter_vai_para_a_pasta_de_DADOS(instalado):
    """A causa, medida na fonte: o default de PRODUÇÃO, sem `cache_path`.

    Os testes de `test_llm_openrouter.py` passam todos um `tmp_path` -- a
    mesma costura que escondeu o defeito de 2026-09-21.
    """
    programa, dados = instalado
    from sigft.core.llm.providers import openrouter

    openrouter.listar_modelos("sk-or-v1-chave", http_get=_get_do_catalogo)

    assert sorted(p.name for p in programa.iterdir()) == [], (
        "o cache do OpenRouter foi gravado na pasta do programa"
    )
    assert (dados / "openrouter_models_cache.json").is_file()


# =============================================================================
# F. O registro de uso de IA e o log de execução, mesma causa (2026-09-25)
# =============================================================================
#
# `config.PASTA_LOGS` é o NOME relativo "logs", e três lugares o usavam como
# caminho: o registro de cada chamada de IA (`core/llm/usage.py`), o log de
# execução em arquivo (`core/log_execucao.py`) e o botão que abre a pasta de
# logs no painel "Gastos de IA". No app instalado, "logs" relativo é
# `Program Files`: a gravação falha em silêncio (o rastreamento nunca derruba
# o app, de propósito) e o painel "Gastos de IA" fica sempre vazio -- sumindo
# justamente o registro que diria por qual provedor uma chamada que falhou
# tinha ido.

def test_o_registro_de_uso_de_IA_vai_para_a_pasta_de_DADOS(instalado, monkeypatch):
    """O default de PRODUÇÃO -- é por ele que o `LLMClient` grava cada chamada."""
    programa, dados = instalado
    from sigft.core.llm import usage

    monkeypatch.delenv(usage.ENV_DESABILITAR_USAGE, raising=False)
    usage.registrar(
        provider="gemini", model="gemini-3.5-flash", tarefa="tech_specs",
        modulo="upload_tech_specs_backend", tokens_in=None, tokens_out=None,
        custo_usd=None, duracao_s=1.0, sucesso=False,
        erro="ConnectionError: ('Connection aborted.', ...)",
    )

    assert sorted(p.name for p in programa.iterdir()) == [], (
        "o registro de uso de IA foi gravado na pasta do programa"
    )
    assert (dados / "logs" / "llm_usage.jsonl").is_file()
    lidos = usage.ler_registros()
    assert [(r["provider"], r["tarefa"], r["sucesso"]) for r in lidos] == [
        ("gemini", "tech_specs", False)
    ], "o painel 'Gastos de IA' não enxerga o que foi gravado"


def test_o_log_de_execucao_vai_para_a_pasta_de_DADOS(instalado):
    programa, dados = instalado
    from sigft.core.log_execucao import LogDeExecucao

    with LogDeExecucao("upload_condicoes") as registro:
        caminho = registro.caminho

    assert sorted(p.name for p in programa.iterdir()) == [], (
        "o log de execução foi gravado na pasta do programa"
    )
    assert caminho.startswith(str(dados / "logs"))


def test_o_botao_da_pasta_de_logs_abre_a_pasta_de_DADOS(instalado, monkeypatch):
    """O botão do painel "Gastos de IA" abria "logs" relativo: a pasta que o
    Explorer mostrava era a do programa, onde nada chega a ser gravado."""
    _programa, dados = instalado
    from sigft.app_qt.views import home
    from sigft.core import plataforma

    abertas = []
    monkeypatch.setattr(plataforma, "abrir_pasta_criando_se_preciso", abertas.append)
    home.HomeView._abrir_pasta_logs_gastos_ia(object())

    assert abertas == [str(dados / "logs")]
