r"""O módulo 2 numa janela menor: o formulário rola e o console mantém o
tamanho padrão das telas (pedido do usuário em 2026-09-24).

Medido antes da mudança, numa janela de 1280x700: o formulário da aba
"Processar PDMs" pedia 704 px, o console foi empurrado para baixo da borda e o
fim da aba ("3. Traduzir para inglês", com o botão) sumiu, sem barra de
rolagem. O console esticava para ocupar o que SOBRASSE do formulário: bom com
a janela maximizada, nada com ela menor.

O padrão que as outras telas já seguem (Analyzer, Upload de Condições, Upload
de Características): o formulário rola, o console tem `ALTURA_CONSOLE`.

[2026-10-15] Lia a tela da interface antiga, que saiu do SIG-FT; agora lê a
Qt (`sigft/app_qt/views/pdm.py`), por AST. As medidas de verdade, com a tela
montada, estão em `tests/test_qt_tela_pdm.py`."""
from __future__ import annotations

import ast
import pathlib

import pytest

from sigft.app import theme

VIEW = pathlib.Path(__file__).resolve().parents[1] / "sigft" / "app_qt" / "views" / "pdm.py"


def _metodo(nome):
    for no in ast.walk(ast.parse(VIEW.read_text(encoding="utf-8"))):
        if isinstance(no, ast.ClassDef) and no.name == "ModuloPDM":
            for item in no.body:
                if isinstance(item, ast.FunctionDef) and item.name == nome:
                    return item
    pytest.fail(f"ModuloPDM.{nome} nao existe")


def _super_init():
    for no in ast.walk(_metodo("__init__")):
        if isinstance(no, ast.Call) and ast.unparse(no.func) == "super().__init__":
            return no
    pytest.fail("ModuloPDM.__init__ nao chama o ModuleFrame")


def test_o_formulario_rola_quando_nao_cabe():
    assert "blocos.area_rolavel(self.content_layout" in ast.unparse(_metodo("_build_ui"))


def test_o_console_tem_a_altura_padrao_das_telas():
    """O `ModuleFrame` dá ao console `theme.ALTURA_CONSOLE` se a tela não pedir
    outra altura; a do PDM não pede."""
    import inspect

    from sigft.app_qt.widgets.module_frame import ModuleFrame

    assert "altura_console" not in {k.arg for k in _super_init().keywords}
    padrao = inspect.signature(ModuleFrame.__init__).parameters["altura_console"].default
    assert padrao == theme.ALTURA_CONSOLE


def test_quem_ganha_a_sobra_e_o_formulario_e_nao_o_console():
    """Com a janela maior, a sobra vai para a área do formulário (peso do
    conteúdo 1); o console fica no tamanho padrão (peso 0, altura fixa)."""
    import inspect

    from sigft.app_qt.widgets.module_frame import ModuleFrame

    assert "peso_conteudo" not in {k.arg for k in _super_init().keywords}
    assert inspect.signature(ModuleFrame.__init__).parameters["peso_conteudo"].default == 1
