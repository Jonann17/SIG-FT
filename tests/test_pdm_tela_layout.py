r"""O módulo 2 numa janela menor: o formulário rola e o console mantém o
tamanho padrão das telas (pedido do usuário em 2026-09-24).

Medido antes da mudança, numa janela de 1280x700: o formulário da aba
"Processar PDMs" pedia 704 px, o console foi empurrado para baixo da borda e o
fim da aba ("3. Traduzir para inglês", com o botão) sumiu, sem barra de
rolagem. O console esticava para ocupar o que SOBRASSE do formulário: bom com
a janela maximizada, nada com ela menor.

O padrão que as outras telas já seguem (Analyzer, Upload de Condições, Upload
de Características): o formulário rola, o console tem `ALTURA_CONSOLE`.

Por AST: `views/pdm.py` importa customtkinter e exige um root Tk (o mesmo
recurso de `test_pdm_tela_planilha.py`)."""
from __future__ import annotations

import ast
import pathlib

import pytest

VIEW = pathlib.Path(__file__).resolve().parents[1] / "sigft" / "app" / "views" / "pdm.py"


def _init():
    for no in ast.walk(ast.parse(VIEW.read_text(encoding="utf-8"))):
        if isinstance(no, ast.ClassDef) and no.name == "ModuloPDM":
            for item in no.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    return item
    pytest.fail("ModuloPDM.__init__ nao existe")


def _valor_atribuido(metodo, alvo):
    for no in ast.walk(metodo):
        if isinstance(no, ast.Assign) and any(ast.unparse(t) == alvo for t in no.targets):
            return no.value
    pytest.fail(f"{alvo} nao e atribuido no __init__")


def _chamadas(metodo, funcao):
    return [no for no in ast.walk(metodo)
            if isinstance(no, ast.Call) and ast.unparse(no.func) == funcao]


def _kw(chamada, nome):
    return next((k.value for k in chamada.keywords if k.arg == nome), None)


def test_o_formulario_rola_quando_nao_cabe():
    chamada = _valor_atribuido(_init(), "self.content")

    assert ast.unparse(chamada.func).endswith("CTkScrollableFrame")


def test_o_console_tem_a_altura_padrao_das_telas():
    chamada = _valor_atribuido(_init(), "self.console")

    altura = _kw(chamada, "height")
    assert altura is not None and ast.unparse(altura).endswith("ALTURA_CONSOLE")


def test_quem_ganha_a_sobra_e_o_formulario_e_nao_o_console():
    """Com a janela maior, a sobra vai para a área do formulário; o console
    fica no tamanho padrão e não estica nem encolhe."""
    pesos = {}
    for chamada in _chamadas(_init(), "self.grid_rowconfigure"):
        peso = _kw(chamada, "weight")
        pesos[chamada.args[0].value] = peso.value if peso is not None else 0

    assert pesos.get(1) == 1
    assert pesos.get(2, 0) == 0
    grid_do_console, = _chamadas(_init(), "self.console.grid")
    assert _kw(grid_do_console, "sticky").value == "ew"
