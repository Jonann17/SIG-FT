r"""
Smoke de importação (CP 0.2 do plano de refatoração — ver
docs/refatoracao/PLANO_REFATORACAO.md).

Objetivo: pegar quebras de IMPORT (dependência faltando, erro de sintaxe
dentro de um import, símbolo removido/renomeado, exceção em nível de módulo)
em cada um dos módulos `*_backend.py` + `upload_ficha_duplicada.py` — os 12
módulos de negócio que `frontend.py` depende para funcionar: 11 são
carregados DINAMICAMENTE via `importlib.import_module()` dentro de
`SplashScreen.carregar_modulos()`, e `upload_ficha_duplicada` é importado de
forma ESTÁTICA logo no topo de `frontend.py` (`import upload_ficha_duplicada
as backend`, linha 34) — ver docs/base-conhecimento/00-frontend.md e
07-upload-ficha-duplicada.md. Para este smoke test o mecanismo de import (
estático × dinâmico) não importa: os dois são testados da mesma forma, via
`importlib.import_module(nome)`.

Este teste NÃO valida comportamento (isso é papel dos testes de
caracterização do CP 0.1); só valida que `import <modulo>` termina sem
levantar exceção. O `tests/conftest.py` já garante, ANTES da coleta deste
arquivo, que:
  1. a raiz do repositório está em `sys.path` (os módulos vivem soltos na
     raiz, não dentro de um pacote instalável);
  2. toda dependência pesada ausente neste ambiente (pandas, openpyxl,
     selenium, google-generativeai, langchain*, llama_parse, PyPDF2, bs4,
     xlwings, deep_translator, unidecode) está stubada em `sys.modules` via
     `unittest.mock.MagicMock` — suficiente aqui porque este teste só
     IMPORTA os módulos, nunca chama as funções/classes neles definidas (ao
     contrário dos testes de caracterização, que precisam que algumas
     chamadas — ex. `pandas.isna` — se comportem de verdade).

`frontend.py` FICA DE FORA deste smoke de importação: ele importa
`customtkinter`/`tkinter` no topo do arquivo e, mais importante, o bloco
`if __name__ == "__main__":` no fim do arquivo cria uma `SplashScreen`
(janela real) — não há como isolar isso com stub de módulo, e o ambiente de
teste não tem display. `frontend.py` continua coberto pela verificação de
SINTAXE do `python -m compileall .` (que compila para bytecode sem nunca
executar o módulo) — ver `scripts/check.sh`.
"""
import importlib

import pytest

# Os 12 módulos de negócio dos quais frontend.py depende: 11 "*_backend.py"
# (carregados dinamicamente por SplashScreen.carregar_modulos(), lista
# `modulos_para_carregar` em frontend.py) + upload_ficha_duplicada.py
# (import estático no topo de frontend.py, linha 34; mesmo papel de backend,
# nome fora do padrão "*_backend.py"). Nomes conferidos 1:1 com os arquivos
# na raiz do repositório.
MODULOS_BACKEND = [
    "analyzer_backend",
    "apagar_lmr_backend",
    "autospec_backend",
    "cria_fichas_no_pmib_v1_backend",
    "lmr_backend",
    "pdm_backend",
    "pmib_manager_backend",
    "search_pmib_backend",
    "translator_backend",
    "upload_conditions_backend",
    "upload_tech_specs_backend",
]


@pytest.mark.parametrize("nome_modulo", MODULOS_BACKEND, ids=MODULOS_BACKEND)
def test_modulo_backend_importa_sem_erro(nome_modulo):
    """`import <nome_modulo>` deve completar sem levantar exceção.

    Usa `importlib.import_module` (em vez de um `import` estático) para que
    o nome do módulo venha do parâmetro, mantendo um caso de teste — e uma
    linha no relatório do pytest — por módulo.
    """
    modulo = importlib.import_module(nome_modulo)
    assert modulo is not None
