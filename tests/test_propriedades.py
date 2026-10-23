"""`propriedades.ler`: propriedade dinâmica do Qt lida sem gastar o `None`
(PySide6 6.12.0, ver o docstring de `sigft/app_qt/propriedades.py`)."""
from __future__ import annotations

import pathlib
import re
import sys

from sigft.app_qt import propriedades

RAIZ = pathlib.Path(__file__).resolve().parent.parent


def test_le_a_propriedade_posta_e_devolve_o_padrao_da_que_falta(qt_interface):
    from PySide6.QtWidgets import QLabel

    rotulo = QLabel("x")
    rotulo.setProperty("ativo", True)
    assert propriedades.ler(rotulo, "ativo") is True
    assert propriedades.ler(rotulo, "nao_existe") is None
    assert propriedades.ler(rotulo, "nao_existe", "padrao") == "padrao"


def test_ler_a_que_falta_nao_gasta_a_referencia_do_none(qt_interface):
    # No 3.10/3.11 o processo morria quando a contagem chegava a zero; no 3.12+
    # o None é imortal e a conta não muda de qualquer jeito.
    from PySide6.QtWidgets import QLabel

    rotulo = QLabel("x")
    antes = sys.getrefcount(None)
    for _ in range(2000):
        propriedades.ler(rotulo, "nao_existe")
    assert sys.getrefcount(None) >= antes - 50


def test_ninguem_chama_property_direto():
    chamada = re.compile(r"\.property\(")
    achados = []
    for caminho in sorted((RAIZ / "sigft").rglob("*.py")):
        if caminho.name == "propriedades.py":
            continue
        for numero, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), 1):
            if chamada.search(linha):
                achados.append(f"{caminho.relative_to(RAIZ)}:{numero}")
    assert achados == [], "use propriedades.ler(objeto, nome): " + ", ".join(achados)
