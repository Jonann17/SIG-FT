r"""A tela do Cria Fichas não tem mais a regra da revisão (2026-10-08).

Lida por AST: as telas não podem ser importadas neste ambiente.
"""
from __future__ import annotations

import ast
import pathlib

TELA = pathlib.Path(__file__).resolve().parent.parent / "sigft" / "app" / "views" / "cria_fichas.py"


def _chamadas():
    nomes = set()
    for no in ast.walk(ast.parse(TELA.read_text(encoding="utf-8"))):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
            nomes.add(no.func.attr)
    return nomes


def test_a_tela_nao_confere_pdm_sozinha():
    """A guarda contra PDM inventado mora em `preparar_para_revisao`."""
    assert "conferir_pdm" not in _chamadas()


def test_a_tela_delega_as_duas_passadas_ao_servico():
    assert "classificar_para_revisao" in _chamadas()
