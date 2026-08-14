"""
Configuração compartilhada dos testes de caracterização (CP 0.1) e do smoke
de importação (CP 0.2) do plano de refatoração — ver
docs/refatoracao/PLANO_REFATORACAO.md.

Este ambiente de teste NÃO tem as dependências pesadas de produção instaladas
(pandas, openpyxl, selenium, google-generativeai, llama_parse, PyPDF2, bs4,
xlwings, deep_translator, unidecode, customtkinter etc.) — só a stdlib,
`requests` e (depois de instalado só para rodar os testes) `pytest`.
[CP 3.2] `langchain-google-genai`/`langchain-core` foram REMOVIDOS de
`requirements.txt` (o uso residual em `autospec_backend.py` foi migrado para
`LLMClient`) — não há mais nada a stubar para elas.
`customtkinter` é a única exceção deliberada: só `frontend.py` a importa, e
`frontend.py` fica de fora do smoke de importação do CP 0.2 (ver nota no
`tests/test_smoke_imports.py`) — por isso não entra em `_HEAVY_MODULES`.

Os módulos `*_backend.py` importam essas dependências pesadas no topo do
arquivo. Para conseguir importar e testar as funções PURAS (regex/string, sem
I/O nem estado) que vivem dentro desses módulos, este conftest injeta um
`unittest.mock.MagicMock()` em `sys.modules` para cada pacote/submódulo pesado
ANTES que qualquer teste importe os módulos de produção. Um MagicMock devolve
qualquer atributo automaticamente, então `from selenium.webdriver.common.by
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
#    Inclui cada nível pontilhado (ex.: "selenium", "selenium.webdriver",
#    "selenium.webdriver.common", "selenium.webdriver.common.by") pelo mesmo
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
    # selenium — usado por upload_tech_specs_backend, upload_ficha_duplicada.py
    "selenium",
    "selenium.webdriver",
    "selenium.webdriver.common",
    "selenium.webdriver.common.by",
    "selenium.webdriver.common.keys",
    # [CP 0.2] submódulo ActionChains — usado só por lmr_backend.py
    # ("from selenium.webdriver.common.action_chains import ActionChains").
    "selenium.webdriver.common.action_chains",
    "selenium.webdriver.support",
    "selenium.webdriver.support.ui",
    "selenium.common",
    "selenium.common.exceptions",
    # autospec_backend.py — extração de PDF/HTML e pipeline RAG
    # [CP 3.2] langchain_google_genai/langchain_core(.prompts/.
    # output_parsers) removidos daqui: nenhum arquivo de produção importa
    # langchain_* mais (confirmado por grep) — o uso residual em
    # `autospec_backend.py` foi substituído por `LLMClient` (via `get_llm`).
    # `requests` NÃO é stubado aqui de propósito (é dependência REAL neste
    # ambiente de teste — `providers/openai_compat.py`/`openrouter.py`
    # dependem disso para os testes injetarem `http_post`/`http_get` fakes
    # sem precisar do pacote de verdade em produção).
    "PyPDF2",
    "bs4",
    "llama_parse",
    # [CP 0.2] translator_backend.py — tradução híbrida PT->ES via Excel COM.
    # xlwings automatiza o Excel (Windows-only, `import xlwings as xw`);
    # deep_translator fornece GoogleTranslator/MyMemoryTranslator; unidecode
    # remove acentos. Nenhum dos três é usado por funções puras testadas —
    # bastam como stub de importação (não há caso especial funcional, ao
    # contrário de "pandas.isna" na seção 3 abaixo).
    "deep_translator",
    "unidecode",
    "xlwings",
]

for _mod_name in _HEAVY_MODULES:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = MagicMock(name=_mod_name)

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


# 5. [2026-08-12] Caches do AutoSpec (busca web e resposta da IA) resolvem o
#    caminho a partir de `config.CONFIG_FILE`, ou seja, a RAIZ DO REPOSITÓRIO.
#    Sem esta fixture, qualquer teste que chame `generate_ai_response` ou
#    `search_and_download` escreveria um `.json` na pasta do projeto — e, pior
#    que a sujeira, o teste seguinte poderia LER o que o anterior gravou:
#    um acerto de cache faz o código pular a chamada de IA, e uma asserção do
#    tipo "o modelo foi chamado 1 vez" passaria ou falharia dependendo da
#    ORDEM dos testes. Mesmo espírito da nota 4: teste nunca toca artefato
#    real do usuário.
#    Usa `tmp_path_factory` e NÃO `tmp_path`: a pasta precisa ficar FORA do
#    `tmp_path` do teste, senão testes que afirmam "não escrevi nada" (ex.:
#    `test_relatorio_lote.py::test_espelho_e_opcional...`) veem a pasta do
#    cache e falham. Aprendido quebrando os dois.
@pytest.fixture(autouse=True)
def _isola_os_caches_do_autospec(monkeypatch, tmp_path_factory):
    try:
        from sigft.services import autospec as _autospec
    except Exception:
        return  # suíte que não importa o AutoSpec não precisa da proteção
    pasta = tmp_path_factory.mktemp("caches_autospec")
    monkeypatch.setattr(
        _autospec, "_caminho_cache_resposta", lambda: str(pasta / "resposta.json")
    )
    monkeypatch.setattr(
        _autospec, "_caminho_cache_busca", lambda: str(pasta / "busca.json")
    )
