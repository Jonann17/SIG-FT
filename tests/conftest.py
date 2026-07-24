"""
Configuração compartilhada dos testes de caracterização (CP 0.1) e do smoke
de importação (CP 0.2) do plano de refatoração — ver
docs/refatoracao/PLANO_REFATORACAO.md.

Este ambiente de teste NÃO tem as dependências pesadas de produção instaladas
(pandas, openpyxl, selenium, google-generativeai, langchain*, llama_parse,
PyPDF2, bs4, xlwings, deep_translator, unidecode, customtkinter etc.) — só a
stdlib, `requests` e (depois de instalado só para rodar os testes) `pytest`.
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
    "PyPDF2",
    "bs4",
    "langchain_google_genai",
    "langchain_core",
    "langchain_core.prompts",
    "langchain_core.output_parsers",
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
