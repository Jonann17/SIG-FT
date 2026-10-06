"""O pandas de VERDADE dentro de um teste, e só dentro dele.

Irmão de `_openpyxl_de_verdade.py`, pelo mesmo motivo: `tests/conftest.py` troca
o pandas por um `MagicMock`, e um serviço que faz `import pandas as pd` no topo
fica com o dublê preso no nome `pd` -- trocar só o `sys.modules` não o alcança.
Durante o bloco, o pacote real volta ao `sys.modules` e o `pd` dos módulos
passados aponta para ele; no fim, tudo volta como estava (inclusive os
submódulos que o import real deixou para trás, que é o vazamento que quebrou
`test_status_sheet.py` no CP 4.3).

O pandas lê `.xlsx` pelo openpyxl, que ele importa na hora da leitura: para ler
planilha, use junto com `openpyxl_de_verdade()`.

Sem o pacote instalado, o teste é PULADO: nunca dá falso verde.
"""
from __future__ import annotations

import contextlib
import importlib
import sys

import pytest


def _e_do_pandas(nome):
    return nome == "pandas" or nome.startswith("pandas.")


@contextlib.contextmanager
def pandas_de_verdade(*modulos):
    """Durante o bloco, `import pandas` devolve o pacote real, e o nome `pd` de
    cada módulo em `modulos` aponta para ele."""
    guardados = {n: m for n, m in sys.modules.items() if _e_do_pandas(n)}
    for nome in guardados:
        del sys.modules[nome]
    religados = []
    try:
        try:
            real = importlib.import_module("pandas")
        except ImportError:
            pytest.skip("pandas real nao instalado")
        if not hasattr(real, "DataFrame") or "Mock" in type(real).__name__:
            pytest.skip("pandas real nao disponivel")
        for modulo in modulos:
            if hasattr(modulo, "pd"):
                religados.append((modulo, "pd", modulo.pd))
                modulo.pd = real
        yield real
    finally:
        for nome in [n for n in list(sys.modules) if _e_do_pandas(n)]:
            del sys.modules[nome]
        sys.modules.update(guardados)
        for modulo, nome, valor in reversed(religados):
            setattr(modulo, nome, valor)
