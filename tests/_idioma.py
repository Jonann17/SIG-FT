"""Ajudantes dos testes de idioma (2026-10-22).

`em_idioma` troca o idioma da sessão e volta ao português no fim (a fixture
autouse do conftest volta de qualquer jeito; isto é para trocar no meio de um
teste). `ainda_em_portugues` é a conferência em tela: o texto à vista que tem,
no catálogo, uma tradução DIFERENTE dele mesmo. Pega a constante marcada
(`marcar`) que chegou à tela sem `t()`, que a guarda estática não vê.
"""
from __future__ import annotations

import contextlib

from PySide6.QtWidgets import QAbstractButton, QComboBox, QLabel, QLineEdit, QTreeWidget, QWidget

from sigft.app import idioma


@contextlib.contextmanager
def em_idioma(codigo: str):
    idioma.definir(codigo)
    try:
        yield
    finally:
        idioma.definir(idioma.PADRAO)


def textos_visiveis(raiz: QWidget) -> set[str]:
    """Os textos de `raiz` e dos filhos: título de janela, dica, rótulo, botão,
    caixa, placeholder, itens de menu e cabeçalho de tabela."""
    textos: set[str] = set()
    for w in [raiz, *raiz.findChildren(QWidget)]:
        if w.isWindow() and w.windowTitle():
            textos.add(w.windowTitle())
        if w.toolTip():
            textos.add(w.toolTip())
        if isinstance(w, (QLabel, QAbstractButton)) and w.text().strip():
            textos.add(w.text().strip())
        if isinstance(w, QLineEdit) and w.placeholderText():
            textos.add(w.placeholderText())
        if isinstance(w, QComboBox):
            textos.update(w.itemText(i) for i in range(w.count()))
        if isinstance(w, QTreeWidget):
            cabecalho = w.headerItem()
            textos.update(cabecalho.text(c) for c in range(cabecalho.columnCount()))
    return {texto for texto in textos if texto}


def ainda_em_portugues(raiz: QWidget, codigo: str) -> set[str]:
    traducoes = idioma.catalogo(codigo)
    return {texto for texto in textos_visiveis(raiz) if traducoes.get(texto, texto) != texto}
