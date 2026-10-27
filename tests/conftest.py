"""
Configuração compartilhada dos testes de caracterização (CP 0.1) e do smoke
de importação (CP 0.2) do plano de refatoração — ver
docs/refatoracao/PLANO_REFATORACAO.md.

Este ambiente de teste NÃO tem as dependências pesadas de produção instaladas
(pandas, openpyxl, playwright, google-generativeai, llama_parse, pypdf, bs4,
xlwings, deep_translator, unidecode etc.) — só a stdlib,
`requests` e (depois de instalado só para rodar os testes) `pytest`.
[CP 3.2] `langchain-google-genai`/`langchain-core` foram REMOVIDOS de
`requirements.txt` (o uso residual em `autospec_backend.py` foi migrado para
`LLMClient`) — não há mais nada a stubar para elas.
A interface (Qt, `sigft/app_qt/`) não é dublada: os testes dela usam o
PySide6 de verdade, em modo offscreen (ver `qt_interface`). A interface antiga
saiu do SIG-FT em 2026-10-15, com os dublês dela.

Os módulos `*_backend.py` importam essas dependências pesadas no topo do
arquivo. Para conseguir importar e testar as funções PURAS (regex/string, sem
I/O nem estado) que vivem dentro desses módulos, este conftest injeta um
`unittest.mock.MagicMock()` em `sys.modules` para cada pacote/submódulo pesado
ANTES que qualquer teste importe os módulos de produção. Um MagicMock devolve
qualquer atributo automaticamente, então `from langchain_core.prompts
import By` funciona sem o pacote real instalado.

O pytest garante que os `conftest.py` de um diretório são carregados antes da
coleta/importação dos módulos de teste daquele diretório — por isso o stub
feito aqui já está em vigor quando `test_*.py` faz `import pdm_backend` etc.

IMPORTANTE: nenhuma linha de código de PRODUÇÃO é alterada por este arquivo.
O stub existe só para tornar o import possível neste ambiente de teste; o
comportamento das funções caracterizadas continua sendo o comportamento real
do código em produção (só os SDKs pesados — nunca usados pelas funções puras
testadas aqui — é que viram Mocks).
"""
import os as _os_qt
import sys as _sys_qt

# [Qt6] Sem display no CI e no contêiner: o Qt desenha em memória. Tem de vir
# antes de qualquer import do PySide6, e setdefault deixa quem quiser ver a
# janela (QT_QPA_PLATFORM=xcb) rodar com display de verdade.
_os_qt.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# [Qt6] No Linux, o fontconfig dos testes esconde o Roboto e o Noto Emoji
# instalados na máquina: valem os do app, registrados pelo `qapp` abaixo. Também
# antes de qualquer import do PySide6. Ver tests/test_qt_fontes_dos_testes.py.
if _sys_qt.platform.startswith("linux"):
    _os_qt.environ.setdefault(
        "FONTCONFIG_FILE",
        _os_qt.path.join(_os_qt.path.dirname(_os_qt.path.abspath(__file__)), "fontes_dos_testes.conf"))

import os
import sys
from unittest.mock import MagicMock

import pytest

# 1. Garante a raiz do repositório no sys.path, para "import pdm_backend",
#    "import search_pmib_backend" etc. (os módulos *_backend.py vivem na raiz
#    do repositório, não dentro de um pacote instalável).
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# 2. Dependências pesadas (ausentes neste ambiente) usadas pelos módulos
#    caracterizados no CP 0.1: pdm_backend.py, search_pmib_backend.py,
#    upload_tech_specs_backend.py, analyzer_backend.py, autospec_backend.py e
#    upload_ficha_duplicada.py. Lista levantada via grep dos imports de cada
#    um desses arquivos (`^import \|^from `).
#
#    Ampliada no CP 0.2 (smoke de importação) para cobrir os imports de TOPO
#    dos 12 módulos `*_backend.py` + `upload_ficha_duplicada.py` inteiros
#    (analyzer, apagar_lmr, autospec, cria_fichas_no_pmib_v1, lmr, pdm,
#    pmib_manager, search_pmib, translator, upload_conditions,
#    upload_tech_specs, upload_ficha_duplicada) — ver
#    tests/test_smoke_imports.py. As entradas novas do CP 0.2 estão marcadas
#    abaixo; o restante já vinha do CP 0.1.
#
#    Inclui cada nível pontilhado (ex.: "google", "google.generativeai";
#    "langchain_core", "langchain_core.prompts") pelo mesmo
#    motivo de "from a.b.c import X" precisar resolver "a" e "a.b" durante o
#    import — um MagicMock resolve atributos ausentes automaticamente, mas
#    deixamos os níveis intermediários explícitos por clareza/robustez.
_HEAVY_MODULES = [
    # pandas — usado por pdm_backend, search_pmib_backend,
    # upload_tech_specs_backend, upload_ficha_duplicada.py
    "pandas",
    # openpyxl — usado por pdm_backend, analyzer_backend, autospec_backend,
    # upload_ficha_duplicada.py
    "openpyxl",
    "openpyxl.styles",
    "openpyxl.cell",
    "openpyxl.cell.rich_text",
    "openpyxl.cell.text",
    # google-generativeai — usado por upload_tech_specs_backend,
    # analyzer_backend
    "google",
    "google.generativeai",
    # CP 5.5 (2026-08-25): aqui havia onze entradas stubando o `selenium` e
    # seus submódulos. O pacote saiu do projeto com o motor; stub de módulo
    # que ninguém importa é pior que inútil -- ele faria um `import selenium`
    # acidental PASSAR no teste e só quebrar na máquina do usuário.
    # autospec_backend.py — extração de PDF/HTML e pipeline RAG
    # [CP 3.2] langchain_google_genai/langchain_core(.prompts/.
    # output_parsers) removidos daqui: nenhum arquivo de produção importa
    # langchain_* mais (confirmado por grep) — o uso residual em
    # `autospec_backend.py` foi substituído por `LLMClient` (via `get_llm`).
    # `requests` NÃO é stubado aqui de propósito (é dependência REAL neste
    # ambiente de teste — `providers/openai_compat.py`/`openrouter.py`
    # dependem disso para os testes injetarem `http_post`/`http_get` fakes
    # sem precisar do pacote de verdade em produção).
    "pypdf",
    "bs4",
    "llama_parse",
    # [CP 0.2] translator_backend.py — tradução PT->ES via Excel COM.
    # xlwings automatiza o Excel (Windows-only, importado dentro de
    # `translator._excel_invisivel`); unidecode remove acentos (os testes do
    # tradutor o trocam por uma função de verdade). deep_translator: desde
    # 2026-09-25 só a reserva do `traducao_pdm` (PDMs para inglês) o usa -- o
    # tradutor 4.2 traduz com o modelo local (`core/tradutor_local.py`).
    "deep_translator",
    "unidecode",
    "xlwings",
]

for _mod_name in _HEAVY_MODULES:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = MagicMock(name=_mod_name)

# 2b. [2026-10-15] A interface antiga saiu do SIG-FT, e com ela os dublês
#     escritos à mão das duas bibliotecas dela (`tests/ctk_falso.py` e
#     `tests/tk_falso.py`, CP 7.1/7.2). Nenhum código
#     do repositório os importa mais (`tests/test_sem_interface_antiga.py` trava isso),
#     então não há o que dublar. A interface Qt é testada de verdade, com o
#     pytest-qt em modo offscreen (`qt_interface`, mais abaixo).

# 3. Caso especial pandas: `PMIBSearcher._limpar_texto_parrudo`
#    (search_pmib_backend.py) chama `pd.isna(texto)`. Um MagicMock puro faria
#    `pd.isna(x)` retornar sempre um novo Mock (truthy para QUALQUER x),
#    fazendo o método tratar até strings normais como "vazias" (bug do stub,
#    não do código real). Substituímos `pandas.isna` por uma implementação
#    mínima equivalente à real da pandas (None -> True; float NaN -> True;
#    qualquer outra coisa -> False) para que a caracterização capture o
#    comportamento verdadeiro da função de produção.
sys.modules["pandas"].isna = lambda x: x is None or (isinstance(x, float) and x != x)

# 4. [CP 3.4] Rastreamento de uso/custo de IA (`sigft/core/llm/usage.py`) fica
#    LIGADO por padrão em PRODUÇÃO — é o ponto daquele checkpoint. Isso
#    significa que TODA chamada de `LLMClient.generate()` (ver
#    `sigft/core/llm/client.py`) tenta gravar um registro em
#    `config.ARQUIVO_USO_LLM` ("logs/llm_usage.jsonl", caminho relativo ao
#    cwd do processo — a raiz REAL do repositório quando `pytest` roda a
#    partir daqui). Dezenas de testes espalhados por vários arquivos
#    constroem um `LLMClient` de verdade e chamam `.generate()`
#    (`tests/test_llm_client.py`, `tests/test_llm_comparacao.py`,
#    `tests/test_llm_get_llm_factory.py` etc.) — a maioria escrita ANTES do
#    CP 3.4, sem nenhuma ideia de que esta instrumentação existiria.
#
#    Esta fixture `autouse` religa `SIGFT_DESABILITAR_USAGE=1` por padrão
#    para TODA a suíte, protegendo qualquer teste (passado ou futuro) que
#    nunca ouviu falar deste checkpoint — sem exigir que cada um seja
#    tocado individualmente. É importável sem nenhuma dependência pesada
#    (`sigft.core.llm.usage` só usa stdlib + `sigft.config`).
#
#    Os testes DEDICADOS a este checkpoint (`tests/test_llm_usage.py` e a
#    extensão de `tests/test_llm_client.py` que exercita a instrumentação de
#    verdade) fazem `monkeypatch.delenv(usage.ENV_DESABILITAR_USAGE,
#    raising=False)` explicitamente, como a PRIMEIRA linha do próprio corpo
#    do teste (nunca dentro de uma fixture) — evita depender da ordem de
#    instanciação entre esta fixture (deste conftest.py raiz) e qualquer
#    outra: o corpo do teste roda sempre DEPOIS que todas as fixtures já
#    terminaram o setup, então a chamada explícita ali é 100% determinística
#    — combinada com um `caminho=`/`tmp_path` próprio, nunca o `logs/` real.
from sigft.core.llm import usage as _llm_usage  # noqa: E402 - depende do sys.path ajustado acima


@pytest.fixture(autouse=True)
def _desliga_rastreamento_de_uso_de_ia_por_padrao(monkeypatch):
    """Ver nota 4 acima: desliga `sigft.core.llm.usage` por padrão para toda
    a suíte, protegendo qualquer teste que construa um `LLMClient` real e
    chame `.generate()` sem saber do CP 3.4."""
    monkeypatch.setenv(_llm_usage.ENV_DESABILITAR_USAGE, "1")


# 5. [2026-08-12, reescrita em 2026-09-18] A PASTA DE DADOS DO USUÁRIO.
#
#    Nasceu isolando dois caches do AutoSpec (busca web e resposta da IA), que
#    resolviam o caminho a partir de `config.CONFIG_FILE` — ou seja, a RAIZ DO
#    REPOSITÓRIO. Sem isolamento, qualquer teste que chamasse
#    `generate_ai_response` ou `search_and_download` escreveria um `.json` na
#    pasta do projeto; e, pior que a sujeira, o teste seguinte poderia LER o
#    que o anterior gravou — um acerto de cache faz o código pular a chamada
#    de IA, e uma asserção do tipo "o modelo foi chamado 1 vez" passaria ou
#    falharia dependendo da ORDEM dos testes.
#
#    O QUE MUDOU: ela monkeypatchava as DUAS FUNÇÕES do `autospec`. Isso
#    isolava os dois caches e mais nada — e agora há muito mais coisa na pasta
#    de dados: `api_config.json`, `user_prefs.json` e os três caches de
#    modelo (ver `sigft/core/dados_usuario.py`). Isolar função por função não
#    escala, e tinha um efeito ruim: um teste que quisesse verificar PARA ONDE
#    a função real aponta via o dublê, nunca a implementação.
#
#    Agora ela redireciona a PASTA, que é a mesma costura que a produção usa
#    (`SIGFT_DADOS_DIR`). Um arquivo de dados novo passa a ser isolado
#    automaticamente, sem ninguém lembrar de acrescentar linha aqui.
#
#    Usa `tmp_path_factory` e NÃO `tmp_path`: a pasta precisa ficar FORA do
#    `tmp_path` do teste, senão testes que afirmam "não escrevi nada" (ex.:
#    `test_relatorio_lote.py::test_espelho_e_opcional...`) veem a pasta de
#    dados e falham. Aprendido quebrando os dois.
@pytest.fixture(autouse=True)
def _isola_os_dados_do_usuario(monkeypatch, tmp_path_factory):
    from sigft.core import dados_usuario as _dados

    pasta = tmp_path_factory.mktemp("dados_do_usuario")
    monkeypatch.setenv(_dados.ENV_PASTA, str(pasta))
    _dados.esquecer_pasta()
    yield pasta
    _dados.esquecer_pasta()


# 4. A janela "Revisão antes do portal" (R2, 2026-10-16) é um `exec()` modal:
#    num teste de tela cujo dado viola uma regra do portal, ela abriria de
#    verdade e a suíte ficaria parada para sempre, sem dizer onde. Esta guarda
#    troca o `exec` por um erro com o motivo. Quem quer a janela troca
#    `revisao_portal.perguntar_revisao` (ou o próprio `exec`) no teste.
@pytest.fixture(autouse=True)
def _revisao_antes_do_portal_nao_trava(monkeypatch):
    modulo = sys.modules.get("sigft.app_qt.widgets.revisao_portal")
    if modulo is not None:
        def _exec(self):
            raise AssertionError(
                "A janela 'Revisão antes do portal' abriu num teste sem dublê: o dado do teste "
                "viola uma regra do portal (ajuste o dado) ou o teste precisa trocar "
                "`revisao_portal.perguntar_revisao`.")
        monkeypatch.setattr(modulo.RevisaoAntesDoPortalDialog, "exec", _exec)


# 6. [2026-10-21] A janela de resumo do fim do lote (`app_qt/widgets/resumo_lote`)
#    abre sozinha quando uma tarefa escreve erro ou aviso no console. Dezenas de
#    testes de tela rodam tarefa com erro DE PROPÓSITO; sem esta guarda, cada um
#    deixaria uma janela aberta por cima do seguinte. Quem testa a janela tira a
#    variável (`monkeypatch.delenv`). O nome é `sigft.app.resumo_lote.ENV_DESLIGAR`
#    (teste em tests/test_resumo_lote.py).
@pytest.fixture(autouse=True)
def _sem_janelas_do_fim_da_tarefa(monkeypatch):
    monkeypatch.setenv("SIGFT_SEM_RESUMO_DO_LOTE", "1")
    # [2026-10-21] O aviso do Windows (`app_qt/aviso_windows.py`) NUNCA nos
    # testes: a notificação sairia na máquina de quem roda a suíte.
    monkeypatch.setenv("SIGFT_SEM_AVISO_DO_WINDOWS", "1")
    # [2026-10-26] O diário de quedas (`sigft/core/diario.py`) NUNCA nos testes: o
    # `main()` dos testes gravaria no `logs/` e trocaria o `faulthandler` do pytest.
    # Quem testa o diário tira a variável e usa uma pasta temporária.
    monkeypatch.setenv("SIGFT_SEM_DIARIO", "1")


# 7. [2026-10-22] O idioma da interface (`sigft/app/idioma.py`) é estado do
#    processo. Todo teste começa e termina em português, onde `t(x) == x`: é por
#    isso que os testes que comparam texto literal continuam valendo. Quem testa
#    outro idioma usa `tests/_idioma.em_idioma(...)`.
@pytest.fixture(autouse=True)
def _sem_janela_esquecida():
    """Janela de topo que o teste criou e deixou aberta sai no fim dele.

    Release 1.3.0 (2026-10-23): no Windows um worker caiu (access violation no
    `paintEvent` de um menu) repintando peças de janelas que testes anteriores
    deixaram vivas; cada troca de folha do app repinta todas as que sobram. O
    que já existia antes do teste (app, fixture de módulo) não é tocado.
    """
    _qtw = sys.modules.get("PySide6.QtWidgets")
    app = _qtw.QApplication.instance() if _qtw is not None else None
    antes = {id(w) for w in app.topLevelWidgets()} if app is not None else set()
    yield
    _qtw = sys.modules.get("PySide6.QtWidgets")
    app = _qtw.QApplication.instance() if _qtw is not None else None
    if app is None:
        return
    from PySide6.QtCore import QEvent
    from shiboken6 import isValid

    sobras = [w for w in app.topLevelWidgets() if id(w) not in antes and isValid(w)]
    for janela in sobras:
        try:
            janela.close()
            janela.deleteLater()
        except RuntimeError:
            pass  # já destruída no meio do caminho
    if sobras:
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture(autouse=True)
def _interface_em_portugues(monkeypatch):
    from sigft.app import idioma as _idioma

    # A pergunta da primeira abertura e o "Reiniciar agora" nunca nos testes: a
    # pasta de dados de cada teste é nova (sem idioma escolhido), e um reinício
    # abriria outro SIG-FT de verdade. Quem testa tira a variável.
    monkeypatch.setenv("SIGFT_SEM_PERGUNTA_DO_IDIOMA", "1")
    monkeypatch.setenv("SIGFT_SEM_REINICIO", "1")

    _idioma.definir(_idioma.PADRAO)
    yield
    _idioma.definir(_idioma.PADRAO)
    # A largura fixa alarga fora do português (`letra._pede_folga`): o vigia que um
    # teste de idioma ligou não pode ficar para o próximo.
    _letra = sys.modules.get("sigft.app_qt.letra")
    if _letra is not None:
        _letra.reavaliar_vigia()


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_teardown(item, nextitem):
    """Depois de um teste Qt, recolhe o lixo NA HORA.

    O pytest-qt fecha as telas com `close()` + `deleteLater()`, mas o
    `processEvents()` dele não roda o DeferredDelete: o C++ das telas fica
    vivo e dono do Python. E uma tela é lixo em ciclo (o seletor guarda um
    método da tela, que guarda o seletor), que o GC só apaga quando quer --
    no meio da pintura do teste seguinte. Aí o QPainter dele quebrava
    (segfault em `QPainter::device()`, 2026-10-08, ordem de testes certa).
    Rodar aqui o DeferredDelete, depois de toda a desmontagem, apaga o C++ fora
    de pintura; o que o GC recolher depois é só casca Python já invalidada.
    """
    yield
    if "qtbot" in getattr(item, "fixturenames", ()):
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def pytest_unconfigure(config):
    """No fim da sessão, apaga pelo Qt as janelas que sobraram, o pai antes.

    Na saída do Python, o PySide apaga cada objeto Qt "do Python" ainda vivo
    numa ordem qualquer. Uma tela vazada (um `lambda` com `self` no sinal de
    um filho: ciclo que passa pelo C++, que o GC não vê) às vezes tinha o
    FILHO apagado antes -- o `lambda` morria, levava a tela, e a tela apagava
    de novo o filho. 6610 testes verdes e o processo morto na saída (código
    134, CI do PR #5, 2026-10-14). Daqui, cada filho morre com o pai, uma vez
    só, e a faxina do PySide não acha mais tela nenhuma.
    Ver tests/test_qt_saida.py.
    """
    if "PySide6.QtWidgets" not in sys.modules:
        return
    import gc

    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return
    for janela in app.topLevelWidgets():
        janela.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()


@pytest.fixture(scope="session")
def qapp(qapp):
    """O `qapp` do pytest-qt com as fontes do app, como o `_preparar_qt`.

    No Release (Windows, `offscreen`) o Qt não vê fonte nenhuma do sistema, só
    as registradas: teste que rodava antes de qualquer `carregar_fontes()`
    desenhava cada letra como caixa de 13 px, e seis medidas quebravam lá
    (2026-10-13). Carregando aqui, todo teste Qt mede com o Roboto do app.
    """
    from sigft.app_qt import estilo

    estilo.carregar_fontes()
    return qapp


@pytest.fixture
def qt_interface(qapp):
    """QApplication pronta e o canal thread -> interface instalado."""
    from sigft.app_qt import interface

    interface.instalar()
    return qapp
