"""Peças que todas as telas repetem: o quadro cinza, o rótulo, o botão.

Nas telas CustomTkinter cada uma vinha com cor, fonte e tamanho escritos à
mão. Aqui a COR do quadro e dos botões vem da folha de estilo (objectName e
variante); fonte e tamanho continuam por chamada, porque variam de tela a tela.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

_ALINHAMENTO = {"centro": Qt.AlignmentFlag.AlignCenter, "esquerda": Qt.AlignmentFlag.AlignLeft}


def cartao(layout_pai) -> QVBoxLayout:
    quadro = QFrame(objectName="cartao")
    layout = QVBoxLayout(quadro)
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(10)
    layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    layout_pai.addWidget(quadro)
    return layout


def rotulo(texto: str, *, tamanho: int = 13, negrito: bool = False, cor: str | None = None,
           alinhar: str = "centro") -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setAlignment(_ALINHAMENTO[alinhar])
    etiqueta.setWordWrap(True)
    estilo = f"font-size: {tamanho}px; background: transparent;"
    if negrito:
        estilo += " font-weight: bold;"
    if cor:
        estilo += f" color: {cor};"
    etiqueta.setStyleSheet(estilo)
    return etiqueta


def botao(texto: str, *, variante: str | None = None, largura: int | None = None,
          altura: int | None = None, tamanho_fonte: int | None = None,
          negrito: bool = False) -> QPushButton:
    b = QPushButton(texto)
    if variante:
        b.setProperty("variante", variante)
    if largura:
        b.setFixedWidth(largura)
    if altura:
        b.setFixedHeight(altura)
    estilo = ""
    if tamanho_fonte:
        estilo += f"font-size: {tamanho_fonte}px;"
    if negrito:
        estilo += " font-weight: bold;"
    if estilo:
        b.setStyleSheet(estilo)
    return b
