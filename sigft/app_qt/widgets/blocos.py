"""Peças que todas as telas repetem: o quadro cinza, o rótulo, o botão.

Nas telas CustomTkinter cada uma vinha com cor, fonte e tamanho escritos à
mão. Aqui a COR do quadro e dos botões vem da folha de estilo (objectName e
variante); fonte e tamanho continuam por chamada, porque variam de tela a tela.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

from sigft.app_qt import estilo

# "esquerda" é o anchor="w" do CTkLabel: encostado à esquerda, centrado na vertical.
_ALINHAMENTO = {
    "centro": Qt.AlignmentFlag.AlignCenter,
    "esquerda": Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
}

# Altura mínima de um CTkLabel (o `height` padrão dele): um rótulo de uma linha
# ocupa isto na tela antiga mesmo com fonte menor, com o texto centrado.
ALTURA_MINIMA_ROTULO = 28


def cartao(layout_pai) -> QVBoxLayout:
    """O quadro cinza. Rótulos ocupam a largura toda (centram o próprio texto);
    botão de largura fixa vai centrado com `addWidget(b, alignment=AlignHCenter)`.

    Sem `setAlignment` no layout inteiro: ele dava a um rótulo com quebra de
    linha uma largura estreita demais, e o texto saía cortado.
    """
    quadro = QFrame(objectName="cartao")
    layout = QVBoxLayout(quadro)
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(10)
    layout_pai.addWidget(quadro)
    return layout


def rotulo(texto: str, *, tamanho: int = 13, negrito: bool = False, cor: str | None = None,
           alinhar: str = "centro") -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setAlignment(_ALINHAMENTO[alinhar])
    etiqueta.setWordWrap(True)
    etiqueta.setMinimumHeight(ALTURA_MINIMA_ROTULO)
    folha = f"font-size: {tamanho}px; background: transparent;"
    if negrito:
        folha += " font-weight: bold;"
    if cor:
        folha += f" color: {cor};"
    etiqueta.setStyleSheet(folha)
    return etiqueta


def botao(texto: str, *, variante: str | None = None, largura: int | None = None,
          altura: int | None = None, tamanho_fonte: int | None = None,
          negrito: bool = False, cor_texto: str | None = None) -> QPushButton:
    b = QPushButton(texto)
    if variante:
        b.setProperty("variante", variante)
    if largura:
        b.setFixedWidth(largura)
    folha = ""
    if altura:
        # Não basta `setFixedHeight`: ao aplicar a folha do app, o Qt troca a
        # altura mínima pelo `min-height` dela (28 px) e o botão encolhe. A
        # altura vai na folha do PRÓPRIO botão, que ganha da global. O
        # `min-height` do Qt não conta a borda; o `height` do CTk conta.
        interna = altura - 2 * estilo.BORDA_DA_VARIANTE.get(variante or "", 0)
        folha += f" min-height: {interna}px; max-height: {interna}px;"
    if tamanho_fonte:
        folha += f" font-size: {tamanho_fonte}px;"
    if negrito:
        folha += " font-weight: bold;"
    extra = ""
    if cor_texto:
        folha += f" color: {cor_texto};"
        # A folha do botão ganha da do app em TODOS os estados: sem repetir o
        # desabilitado aqui, o texto ficaria com `cor_texto` mesmo desligado.
        extra = f" QPushButton:disabled {{ color: {estilo.cinza_tk(estilo.TEXTO_DESABILITADO_CTK)}; }}"
    if folha:
        b.setStyleSheet(f"QPushButton {{{folha} }}{extra}")
    return b
