"""Controles do CustomTkinter que a folha de estilo não sabe imitar.

O QSS pinta fundo, borda e texto, mas não desenha o botão redondo de um
CTkSwitch, a seta do CTkOptionMenu nem o "v" de uma CTkCheckBox (sem imagem,
a caixa marcada do QSS é só um quadrado cheio). Aqui eles são desenhados à
mão, com as medidas e as cores do tema dark-blue
(customtkinter/assets/themes/dark-blue.json), o que o app antigo usa.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QCheckBox, QComboBox

from sigft.app_qt import estilo

# CTkSwitch: trilho de 36x18 (switch_width/height) com borda transparente de 3
# -- o que se vê é o miolo, 30x12 -- e o botão redondo de 18 px. A linha toda
# tem 24 de altura (height); o texto vem 6 px depois do trilho.
LARGURA_TRILHO, ALTURA_TRILHO, BORDA_TRILHO = 36, 18, 3
VAO_TEXTO_INTERRUPTOR = 6
ALTURA_INTERRUPTOR = 24
COR_TRILHO = estilo.TRILHO_CTK   # CTkSwitch fg_color (o mesmo da barra e do slider)
COR_BOTAO_INTERRUPTOR = "#D5D9DE"
COR_BOTAO_INTERRUPTOR_HOVER = "#FFFFFF"   # gray100
COR_TEXTO_CTK = estilo.cinza_tk("gray84")
COR_TEXTO_DESLIGADO_CTK = estilo.cinza_tk("gray45")

# CTkOptionMenu: 28 de altura; a parte da seta é um quadrado da altura, mais
# escura (button_color), que escurece mais no hover (button_hover_color).
ALTURA_MENU = estilo.ALTURA_MENU_CTK
COR_SETA_MENU_HOVER = "#1E2C40"

# CTkCheckBox: caixa de 24 com borda 3 #949A9F e cantos de 6; marcada, enche
# da cor e ganha o "v" gray90.
LADO_CAIXA, BORDA_CAIXA, RAIO_CAIXA = 24, 3, 6
COR_BORDA_CAIXA = estilo.BORDA_CTK
COR_MARCA_CAIXA = estilo.cinza_tk("gray90")


def _pintor(widget) -> QPainter:
    pintor = QPainter(widget)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    return pintor


class Interruptor(QCheckBox):
    """CTkSwitch: um QCheckBox (isChecked, toggled) com a cara do interruptor.

    `cor_ligado` é o `progress_color` do CTk (o padrão do tema é o azul).
    Clicar no texto também alterna, como lá.
    """

    def __init__(self, texto: str, parent=None, *, cor_ligado: str = estilo.AZUL_CTK,
                 tamanho_fonte: int = 13) -> None:
        super().__init__(texto, parent)
        self._cor_ligado = cor_ligado
        # A folha do widget ganha da global (QCheckBox 12 px): o tamanho é o pedido.
        self.setStyleSheet(f"font-size: {tamanho_fonte}px;")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:  # noqa: N802 -- nome do Qt
        largura = LARGURA_TRILHO + VAO_TEXTO_INTERRUPTOR + self.fontMetrics().horizontalAdvance(self.text())
        return QSize(largura, max(ALTURA_INTERRUPTOR, self.fontMetrics().height()))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 -- nome do Qt
        return self.sizeHint()

    def hitButton(self, pos) -> bool:  # noqa: N802 -- nome do Qt
        return self.rect().contains(pos)

    def paintEvent(self, _evento) -> None:  # noqa: N802 -- nome do Qt
        pintor = _pintor(self)
        y0 = (self.height() - ALTURA_TRILHO) / 2
        miolo = QRectF(BORDA_TRILHO, y0 + BORDA_TRILHO,
                       LARGURA_TRILHO - 2 * BORDA_TRILHO, ALTURA_TRILHO - 2 * BORDA_TRILHO)
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(QColor(self._cor_ligado if self.isChecked() else COR_TRILHO))
        pintor.drawRoundedRect(miolo, miolo.height() / 2, miolo.height() / 2)
        x_botao = LARGURA_TRILHO - ALTURA_TRILHO if self.isChecked() else 0
        sobre = self.isEnabled() and self.underMouse()
        pintor.setBrush(QColor(COR_BOTAO_INTERRUPTOR_HOVER if sobre else COR_BOTAO_INTERRUPTOR))
        pintor.drawEllipse(QRectF(x_botao, y0, ALTURA_TRILHO, ALTURA_TRILHO))
        pintor.setPen(QColor(COR_TEXTO_CTK if self.isEnabled() else COR_TEXTO_DESLIGADO_CTK))
        pintor.setFont(self.font())
        x_texto = LARGURA_TRILHO + VAO_TEXTO_INTERRUPTOR
        pintor.drawText(QRectF(x_texto, 0, self.width() - x_texto, self.height()),
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())
        pintor.end()


class MenuDeOpcoes(QComboBox):
    """CTkOptionMenu: a lista que abre continua a do Qt; o botão é o do CTk.

    `cor`/`cor_seta` são o `fg_color`/`button_color` do CTk (a Busca PMIB pinta
    o menu de #3A3A3A/#454545); o escurecer da seta sob o mouse é o do tema.
    """

    def __init__(self, opcoes: list[str] | None = None, parent=None, *,
                 cor: str = estilo.AZUL_CTK, cor_seta: str = estilo.AZUL_CTK_HOVER) -> None:
        super().__init__(parent)
        self._cor, self._cor_seta = cor, cor_seta
        if opcoes:
            self.addItems(opcoes)
        self.setFixedHeight(ALTURA_MENU)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:  # noqa: N802 -- nome do Qt
        return QSize(super().sizeHint().width(), ALTURA_MENU)

    def paintEvent(self, _evento) -> None:  # noqa: N802 -- nome do Qt
        pintor = _pintor(self)
        largura, altura = self.width(), self.height()
        inteiro = QPainterPath()
        inteiro.addRoundedRect(QRectF(0, 0, largura, altura), 6, 6)
        pintor.setClipPath(inteiro)
        pintor.fillRect(QRectF(0, 0, largura - altura, altura), QColor(self._cor))
        sobre = self.isEnabled() and self.underMouse()
        pintor.fillRect(QRectF(largura - altura, 0, altura, altura),
                        QColor(COR_SETA_MENU_HOVER if sobre else self._cor_seta))
        pintor.setClipping(False)
        # A seta: no Windows e no Linux o CTk a desenha com a fonte de formas dele
        # (não com o polígono do macOS). Medida na captura: um "v" de 9x5 px com
        # traço de 2, no meio do quadrado escuro (1 px abaixo do centro).
        cor_texto = QColor(estilo.TEXTO_BOTAO_CTK if self.isEnabled() else estilo.cinza_tk("gray60"))
        cx, cy = largura - altura / 2, altura / 2 + 1
        caneta = QPen(cor_texto, 2)
        caneta.setCapStyle(Qt.PenCapStyle.RoundCap)
        caneta.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pintor.setPen(caneta)
        pintor.drawPolyline([QPointF(cx - 3.5, cy - 1.75), QPointF(cx, cy + 1.75),
                             QPointF(cx + 3.5, cy - 1.75)])
        # O texto: rótulo do Tk com borda 1, depois dos 6 px do canto.
        pintor.setPen(cor_texto)
        pintor.setFont(self.font())
        caixa_texto = QRectF(7, 0, largura - altura - 10, altura)
        texto = self.fontMetrics().elidedText(self.currentText(), Qt.TextElideMode.ElideRight,
                                              int(caixa_texto.width()))
        pintor.drawText(caixa_texto, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, texto)
        pintor.end()


def pintar_caixa(pintor: QPainter, x: float, y: float, marcada: bool, cor_marcada: str,
                 lado: int = LADO_CAIXA) -> None:
    """Desenha uma CTkCheckBox de `lado` px (24, o do tema, ou o `checkbox_width`
    da tela) com o canto de cima à esquerda em (x, y). Borda e cantos não mudam
    com o lado, como no CTk."""
    pintor.save()
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    metade = BORDA_CAIXA / 2
    quadro = QRectF(x + metade, y + metade, lado - BORDA_CAIXA, lado - BORDA_CAIXA)
    pintor.setPen(QPen(QColor(cor_marcada if marcada else COR_BORDA_CAIXA), BORDA_CAIXA))
    pintor.setBrush(QColor(cor_marcada) if marcada else Qt.BrushStyle.NoBrush)
    pintor.drawRoundedRect(quadro, RAIO_CAIXA - metade, RAIO_CAIXA - metade)
    if marcada:
        # draw_checkmark do CTk: tamanho 0.58 da caixa, raio tamanho/2.8, traço lado/8.
        raio = round(lado * 0.58) / 2.8
        cx, cy = x + lado / 2, y + lado / 2
        caneta = QPen(QColor(COR_MARCA_CAIXA), round(lado / 8))
        caneta.setCapStyle(Qt.PenCapStyle.RoundCap)
        caneta.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        pintor.setPen(caneta)
        pintor.drawPolyline([QPointF(cx + raio, cy - raio), QPointF(cx - raio / 4, cy + raio * 0.8),
                             QPointF(cx - raio, cy + raio / 6)])
    pintor.restore()


# --- E4.2: CTkCheckBox avulsa ---------------------------------------------------
# A caixa de 24 (`pintar_caixa`) seguida do texto, 6 px depois (a coluna de
# `minsize=6` do CTkCheckBox). Sob o mouse, a caixa enche da cor de hover --
# marcada ou não (`_on_enter` do CTk); desmarcada, a borda continua cinza.
VAO_TEXTO_CAIXA = 6


class CaixaDeMarcar(QCheckBox):
    """CTkCheckBox: um QCheckBox (isChecked, toggled) com a caixa e o "v" do CTk.

    Clicar no texto também alterna, como lá. `cor_marcada`/`cor_hover` são o
    `fg_color`/`hover_color` do CTk (o padrão do tema é o azul).
    """

    def __init__(self, texto: str, parent=None, *, tamanho_fonte: int = 13,
                 cor_marcada: str = estilo.AZUL_CTK, cor_hover: str = estilo.AZUL_CTK_HOVER,
                 lado: int = LADO_CAIXA) -> None:
        super().__init__(texto, parent)
        self._cor_marcada, self._cor_hover = cor_marcada, cor_hover
        self._lado = lado   # `checkbox_width`/`checkbox_height` do CTk (E4.10: 18 no AutoSpec)
        # A folha do widget ganha da global (QCheckBox 12 px): o tamanho é o pedido.
        self.setStyleSheet(f"font-size: {tamanho_fonte}px; background: transparent;")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def sizeHint(self) -> QSize:  # noqa: N802 -- nome do Qt
        largura = self._lado + VAO_TEXTO_CAIXA + self.fontMetrics().horizontalAdvance(self.text())
        return QSize(largura, max(self._lado, self.fontMetrics().height()))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 -- nome do Qt
        return self.sizeHint()

    def hitButton(self, pos) -> bool:  # noqa: N802 -- nome do Qt
        return self.rect().contains(pos)

    def paintEvent(self, _evento) -> None:  # noqa: N802 -- nome do Qt
        pintor = _pintor(self)
        lado = self._lado
        y = (self.height() - lado) / 2
        sobre = self.isEnabled() and self.underMouse()
        marcada = self.isChecked()
        if sobre and not marcada:
            pintor.setPen(Qt.PenStyle.NoPen)
            pintor.setBrush(QColor(self._cor_hover))
            pintor.drawRoundedRect(QRectF(BORDA_CAIXA, y + BORDA_CAIXA, lado - 2 * BORDA_CAIXA,
                                          lado - 2 * BORDA_CAIXA), RAIO_CAIXA / 2, RAIO_CAIXA / 2)
        pintar_caixa(pintor, 0, y, marcada, self._cor_hover if sobre else self._cor_marcada, lado)
        pintor.setPen(QColor(COR_TEXTO_CTK if self.isEnabled() else COR_TEXTO_DESLIGADO_CTK))
        pintor.setFont(self.font())
        x_texto = lado + VAO_TEXTO_CAIXA
        pintor.drawText(QRectF(x_texto, 0, self.width() - x_texto, self.height()),
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())
        pintor.end()
