"""O openpyxl de VERDADE dentro de um teste, e só dentro dele.

`tests/conftest.py` troca o openpyxl por um `MagicMock` -- a suíte roda sem as
dependências pesadas. O teste que precisa de planilha de verdade troca o dublê
pelo pacote real SÓ enquanto roda, e devolve o dublê no fim. Fazer a troca no
nível do arquivo VAZAVA módulos reais para o resto da suíte (ver a seção B de
`test_pdm_io.py`).

Existe como módulo porque o marcador que `test_pdm_catalogo.py` usava
(`skipif(openpyxl é o dublê)`) era SEMPRE verdadeiro sob o `conftest.py`: os
9 testes de leitura de planilha daquele arquivo nunca rodaram, nem no CI.

Sem o pacote instalado, o teste é PULADO: nunca dá falso verde.
"""
from __future__ import annotations

import contextlib
import importlib
import sys

import pytest

# Nomes que os módulos do app importam do openpyxl NO TOPO (`from openpyxl
# import load_workbook`). Eles ficam ligados ao dublê no momento do import, e
# trocar o `sys.modules` não os alcança: é preciso religá-los um a um.
_DO_PACOTE = ("load_workbook", "Workbook")
_DE_ESTILO = ("Border", "Side", "Alignment", "Font", "PatternFill")


def _e_do_openpyxl(nome):
    return nome == "openpyxl" or nome.startswith("openpyxl.")


@contextlib.contextmanager
def openpyxl_de_verdade(*modulos):
    """Durante o bloco, `import openpyxl` devolve o pacote real, e os nomes de
    `_DO_PACOTE`/`_DE_ESTILO` que existirem em `modulos` apontam para ele."""
    guardados = {n: m for n, m in sys.modules.items() if _e_do_openpyxl(n)}
    for nome in guardados:
        del sys.modules[nome]
    religados = []
    try:
        try:
            real = importlib.import_module("openpyxl")
        except ImportError:
            pytest.skip("openpyxl real nao instalado")
        if not hasattr(real, "Workbook") or "Mock" in type(real).__name__:
            pytest.skip("openpyxl real nao disponivel")
        estilos = importlib.import_module("openpyxl.styles")
        for modulo in modulos:
            for fonte, nomes in ((real, _DO_PACOTE), (estilos, _DE_ESTILO)):
                for nome in nomes:
                    if hasattr(modulo, nome):
                        religados.append((modulo, nome, getattr(modulo, nome)))
                        setattr(modulo, nome, getattr(fonte, nome))
        yield real
    finally:
        for nome in [n for n in list(sys.modules) if _e_do_openpyxl(n)]:
            del sys.modules[nome]
        sys.modules.update(guardados)
        for modulo, nome, valor in reversed(religados):
            setattr(modulo, nome, valor)
