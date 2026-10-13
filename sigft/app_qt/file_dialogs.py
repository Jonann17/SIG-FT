"""Diálogos de arquivo da interface Qt, com a MESMA memória de pastas de hoje.

Toda a lógica (pasta inicial por chave/categoria, lembrar a pasta escolhida,
cancelar devolvendo vazio) mora em `sigft/app/file_dialogs.py`, que não
depende de tkinter para isso: ela aceita um `dialog_fn`. Aqui só se troca o
diálogo do Tk pelo `QFileDialog`, com os mesmos nomes de parâmetro do Tk.
"""
from __future__ import annotations

import os

from PySide6.QtWidgets import QApplication, QFileDialog

from sigft.app import file_dialogs as _base


def filtro_qt(filetypes) -> str:
    """`[("Excel", "*.xlsx;*.xlsm")]` (Tk) -> `"Excel (*.xlsx *.xlsm)"` (Qt)."""
    if not filetypes:
        return ""
    return ";;".join(
        f"{nome} ({' '.join(padrao.replace(';', ' ').split())})" for nome, padrao in filetypes)


def _pai():
    return QApplication.activeWindow()


def _abrir_um(*, initialdir=None, title=None, filetypes=None, **_):
    caminho, _filtro = QFileDialog.getOpenFileName(_pai(), title or "", initialdir or "", filtro_qt(filetypes))
    return caminho


def _abrir_varios(*, initialdir=None, title=None, filetypes=None, **_):
    caminhos, _filtro = QFileDialog.getOpenFileNames(_pai(), title or "", initialdir or "", filtro_qt(filetypes))
    return tuple(caminhos)


def _salvar(*, initialdir=None, title=None, filetypes=None, defaultextension=None, **_):
    caminho, _filtro = QFileDialog.getSaveFileName(_pai(), title or "", initialdir or "", filtro_qt(filetypes))
    if caminho and defaultextension and not os.path.splitext(caminho)[1]:
        caminho += defaultextension
    return caminho


def _pasta(*, initialdir=None, title=None, **_):
    return QFileDialog.getExistingDirectory(_pai(), title or "", initialdir or "")


def ask_open_file(chave, categoria, *, dialog_fn=None, **kwargs) -> str:
    return _base.ask_open_file(chave, categoria, dialog_fn=dialog_fn or _abrir_um, **kwargs)


def ask_open_files(chave, categoria, *, dialog_fn=None, **kwargs):
    return _base.ask_open_files(chave, categoria, dialog_fn=dialog_fn or _abrir_varios, **kwargs)


def ask_save_file(chave, categoria, *, dialog_fn=None, **kwargs) -> str:
    return _base.ask_save_file(chave, categoria, dialog_fn=dialog_fn or _salvar, **kwargs)


def ask_directory(chave, categoria, *, dialog_fn=None, **kwargs) -> str:
    return _base.ask_directory(chave, categoria, dialog_fn=dialog_fn or _pasta, **kwargs)
