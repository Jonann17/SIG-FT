"""Nenhum `.py` do SIG-FT importa as bibliotecas da interface antiga.

Desde 2026-10-15 a interface do SIG-FT é só a Qt (`sigft/app_qt/`): a
CustomTkinter de antes saiu, com o `--ctk` e a queda para ela. Esta é a trava:
nenhum arquivo do repositório (fora do venv) importa `tkinter`, `_tkinter` ou
`customtkinter` -- nem no topo, nem dentro de função, nem por `importlib`
com o nome escrito.

Por AST, e não por busca de texto: o nome pode aparecer num comentário que
conta a história (e aparece aqui, que é a trava). O que não pode é o import.

Este arquivo é o DONO da lista: quem precisa bloquear as mesmas bibliotecas
(o `tests/test_qt_corte.py`, por exemplo) importa `MODULOS_PROIBIDOS` daqui.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent

MODULOS_PROIBIDOS = frozenset({"tkinter", "_tkinter", "customtkinter"})

# Pastas que não são código do SIG-FT.
_FORA = {".venv", "venv", ".git", "build", "dist", "__pycache__", ".claude", "node_modules"}


def _arquivos_py() -> list[Path]:
    arquivos = []
    for caminho in RAIZ.rglob("*.py"):
        partes = set(caminho.relative_to(RAIZ).parts[:-1])
        if partes & _FORA:
            continue
        arquivos.append(caminho)
    return sorted(arquivos)


def _importa_proibido(arvore: ast.AST) -> list[str]:
    achados = []
    for no in ast.walk(arvore):
        nomes = []
        if isinstance(no, ast.Import):
            nomes = [a.name for a in no.names]
        elif isinstance(no, ast.ImportFrom) and no.module and not no.level:
            nomes = [no.module]
        elif (isinstance(no, ast.Call) and no.args and isinstance(no.args[0], ast.Constant)
              and isinstance(no.args[0].value, str)
              and ast.unparse(no.func).split(".")[-1] in {"import_module", "__import__", "find_spec"}):
            nomes = [no.args[0].value]
        for nome in nomes:
            if nome.split(".")[0] in MODULOS_PROIBIDOS:
                achados.append(f"linha {no.lineno}: {nome}")
    return achados


def test_ha_arquivos_para_conferir():
    nomes = {str(c.relative_to(RAIZ)).replace("\\", "/") for c in _arquivos_py()}
    assert {"frontend.py", "sigft/app_qt/main.py", "tests/test_sem_interface_antiga.py"} <= nomes


@pytest.mark.parametrize("caminho", _arquivos_py(), ids=lambda c: str(c.relative_to(RAIZ)))
def test_nenhum_arquivo_importa_a_interface_antiga(caminho):
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    assert not _importa_proibido(arvore), _importa_proibido(arvore)


@pytest.mark.parametrize("fonte", [
    "import tkinter",
    "import tkinter.ttk as ttk",
    "from tkinter import messagebox",
    "import customtkinter as ctk",
    "import _tkinter",
    "def f():\n    from tkinter import filedialog\n",
    "importlib.import_module('customtkinter')",
    "__import__('tkinter')",
])
def test_a_trava_pega_cada_forma_de_import(fonte):
    assert _importa_proibido(ast.parse(fonte))


@pytest.mark.parametrize("fonte", [
    "# import tkinter",
    "x = 'customtkinter'",
    "from . import tkinter_nao",
    "import tkinterx",
])
def test_a_trava_nao_acusa_o_que_nao_e_import(fonte):
    assert not _importa_proibido(ast.parse(fonte))


# -- o pacote e as dependencias -------------------------------------------------

def _excludes_do_spec() -> list[str]:
    arvore = ast.parse((RAIZ / "SIG-FT.spec").read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call) and getattr(no.func, "id", None) == "Analysis":
            for k in no.keywords:
                if k.arg == "excludes":
                    return ast.literal_eval(k.value)
    pytest.fail("o Analysis do SIG-FT.spec perdeu os excludes")


def test_o_pacote_exclui_a_interface_antiga_e_o_tcl_tk():
    """Sem a exclusão, import opcional de terceiros (o `PIL.ImageTk`) levaria o
    `_tkinter`, a libtcl/libtk e os dados do Tcl/Tk para o pacote: medido em
    2026-10-15 no Linux, 334 arquivos e 9 MB."""
    assert MODULOS_PROIBIDOS <= set(_excludes_do_spec())
    spec = (RAIZ / "SIG-FT.spec").read_text(encoding="utf-8")
    assert 'collect_data_files("customtkinter")' not in spec


def test_as_dependencias_nao_trazem_a_interface_antiga():
    for nome in ("requirements.txt", "requirements-dev.txt"):
        pacotes = [linha.split(";")[0].strip().lower()
                   for linha in (RAIZ / nome).read_text(encoding="utf-8").splitlines()
                   if linha.strip() and not linha.strip().startswith("#")]
        assert not [p for p in pacotes if p.split("=")[0].split(">")[0] in MODULOS_PROIBIDOS], nome


def test_a_conferencia_do_pacote_nao_procura_a_interface_antiga():
    from sigft.app import conferencia

    assert not MODULOS_PROIBIDOS & set(conferencia.MODULOS_ESSENCIAIS)
