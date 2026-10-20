"""Controles da interface antiga que a folha de estilo não sabe imitar.

O QSS pinta fundo, borda e texto, mas não desenha o botão redondo de um
CTkSwitch, a seta do CTkOptionMenu nem o "v" de uma CTkCheckBox (sem imagem,
a caixa marcada do QSS é só um quadrado cheio). Aqui eles são desenhados à
mão, com as medidas do tema dark-blue da interface antiga. As CORES, desde
2026-10-20, são as da paleta do tema atual (`estilo.paleta_atual()`), lidas na
hora de pintar: nenhuma peça daqui guarda cor, e a troca de tema as alcança.
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

# Os papéis (tokens) de cada parte. Interruptor: trilho `borda` (desligado) ou
# `primaria` (ligado); botão `texto_suave` desligado e `texto_sobre_primaria`
# ligado (contrasta com o trilho nos dois temas), `texto` sob o mouse.
# Menu: corpo `superficie_alta` e borda `borda` (`primaria` sob o mouse), como o
# QComboBox da folha; a seta e o texto em `texto`. Caixa: borda `texto_suave`,
# marcada `primaria` com o "v" `texto_sobre_primaria`, `primaria_hover` sob o
# mouse. Texto desligado: `texto_suave`, como no resto da folha.

# CTkOptionMenu: a altura de campo (32); a seta num quadrado da altura.
ALTURA_MENU = estilo.ALTURA_MENU_CTK

# CTkCheckBox: caixa de 24 com borda 3 e cantos de 6; marcada, enche da cor e
# ganha o "v".
LADO_CAIXA, BORDA_CAIXA, RAIO_CAIXA = 24, 3, 6


def cor_do_texto(habilitado: bool) -> QColor:
    """O texto de um controle pintado: `texto`, ou `texto_suave` desligado."""
    p = estilo.paleta_atual()
    return QColor(p["texto"] if habilitado else p["texto_suave"])


def _pintor(widget) -> QPainter:
    pintor = QPainter(widget)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    return pintor


class Interruptor(QCheckBox):
    """CTkSwitch: um QCheckBox (isChecked, toggled) com a cara do interruptor.

    Clicar no texto também alterna, como lá. Ligado, o trilho é `primaria`.
    """

    def __init__(self, texto: str, parent=None, *, tamanho_fonte: int = 13) -> None:
        super().__init__(texto, parent)
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
        p = estilo.paleta_atual()
        ligado = self.isChecked()
        y0 = (self.height() - ALTURA_TRILHO) / 2
        miolo = QRectF(BORDA_TRILHO, y0 + BORDA_TRILHO,
                       LARGURA_TRILHO - 2 * BORDA_TRILHO, ALTURA_TRILHO - 2 * BORDA_TRILHO)
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(QColor(p["primaria"] if ligado else p["borda"]))
        pintor.drawRoundedRect(miolo, miolo.height() / 2, miolo.height() / 2)
        x_botao = LARGURA_TRILHO - ALTURA_TRILHO if ligado else 0
        sobre = self.isEnabled() and self.underMouse()
        botao = "texto" if sobre else ("texto_sobre_primaria" if ligado else "texto_suave")
        pintor.setBrush(QColor(p[botao]))
        pintor.drawEllipse(QRectF(x_botao, y0, ALTURA_TRILHO, ALTURA_TRILHO))
        pintor.setPen(cor_do_texto(self.isEnabled()))
        pintor.setFont(self.font())
        x_texto = LARGURA_TRILHO + VAO_TEXTO_INTERRUPTOR
        pintor.drawText(QRectF(x_texto, 0, self.width() - x_texto, self.height()),
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())
        pintor.end()


class MenuDeOpcoes(QComboBox):
    """CTkOptionMenu: a lista que abre continua a do Qt; o botão é pintado aqui.

    Desde 2026-10-20 com a cara do QComboBox da folha (corpo `superficie_alta`,
    borda `borda`, que fica `primaria` sob o mouse) e a seta "v" à direita.
    """

    def __init__(self, opcoes: list[str] | None = None, parent=None) -> None:
        super().__init__(parent)
        if opcoes:
            self.addItems(opcoes)
        self.setFixedHeight(ALTURA_MENU)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:  # noqa: N802 -- nome do Qt
        return QSize(super().sizeHint().width(), ALTURA_MENU)

    def wheelEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        # E5.1: a roda do mouse NÃO troca a opção -- o CTkOptionMenu não a escuta.
        # O QComboBox troca, e numa área rolável (o painel de modelos da Home)
        # rolar a janela com o ponteiro em cima de um menu mudaria a escolha
        # sem a pessoa ver. Ignorada, a roda segue para a área, que rola.
        evento.ignore()

    def paintEvent(self, _evento) -> None:  # noqa: N802 -- nome do Qt
        pintor = _pintor(self)
        p = estilo.paleta_atual()
        largura, altura = self.width(), self.height()
        sobre = self.isEnabled() and self.underMouse()
        borda = estilo.BORDA_CONTROLE
        inteiro = QPainterPath()
        inteiro.addRoundedRect(QRectF(borda / 2, borda / 2, largura - borda, altura - borda), 6, 6)
        pintor.setPen(QPen(QColor(p["primaria"] if sobre else p["borda"]), borda))
        pintor.setBrush(QColor(p["superficie_alta"]))
        pintor.drawPath(inteiro)
        # A seta: um "v" de 9x5 px com traço de 2 (o da interface antiga, medido
        # na captura), no meio do quadrado da direita (1 px abaixo do centro).
        cor_texto = cor_do_texto(self.isEnabled())
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


def pintar_caixa(pintor: QPainter, x: float, y: float, marcada: bool, *, sobre: bool = False,
                 lado: int = LADO_CAIXA) -> None:
    """Desenha uma CTkCheckBox de `lado` px (24, o do tema, ou o `checkbox_width`
    da tela) com o canto de cima à esquerda em (x, y). Borda e cantos não mudam
    com o lado, como na interface antiga. `sobre`: o mouse em cima (a cor de
    marcada vira `primaria_hover`)."""
    p = estilo.paleta_atual()
    cor_marcada = p["primaria_hover"] if sobre else p["primaria"]
    pintor.save()
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    metade = BORDA_CAIXA / 2
    quadro = QRectF(x + metade, y + metade, lado - BORDA_CAIXA, lado - BORDA_CAIXA)
    pintor.setPen(QPen(QColor(cor_marcada if marcada else p["texto_suave"]), BORDA_CAIXA))
    pintor.setBrush(QColor(cor_marcada) if marcada else Qt.BrushStyle.NoBrush)
    pintor.drawRoundedRect(quadro, RAIO_CAIXA - metade, RAIO_CAIXA - metade)
    if marcada:
        # draw_checkmark da interface antiga: tamanho 0.58 da caixa, raio tamanho/2.8, traço lado/8.
        raio = round(lado * 0.58) / 2.8
        cx, cy = x + lado / 2, y + lado / 2
        caneta = QPen(QColor(p["texto_sobre_primaria"]), round(lado / 8))
        caneta.setCapStyle(Qt.PenCapStyle.RoundCap)
        caneta.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        pintor.setPen(caneta)
        pintor.drawPolyline([QPointF(cx + raio, cy - raio), QPointF(cx - raio / 4, cy + raio * 0.8),
                             QPointF(cx - raio, cy + raio / 6)])
    pintor.restore()


# --- E4.2: CTkCheckBox avulsa ---------------------------------------------------
# A caixa (`pintar_caixa`: 24 px, a do tema, ou o `lado` pedido) seguida do
# texto, 6 px depois (a coluna de `minsize=6` do CTkCheckBox). Sob o mouse, a
# caixa enche da cor de hover -- marcada ou não (`_on_enter` da interface antiga);
# desmarcada, a borda continua cinza.
VAO_TEXTO_CAIXA = 6


class CaixaDeMarcar(QCheckBox):
    """CTkCheckBox: um QCheckBox (isChecked, toggled) com a caixa e o "v" da interface antiga.

    Clicar no texto também alterna, como lá. Cores: as de `pintar_caixa`.
    """

    def __init__(self, texto: str, parent=None, *, tamanho_fonte: int = 13,
                 lado: int = LADO_CAIXA) -> None:
        super().__init__(texto, parent)
        self._lado = lado   # `checkbox_width`/`checkbox_height` da interface antiga (E4.10: 18 no AutoSpec)
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
            pintor.setBrush(QColor(estilo.paleta_atual()["primaria_hover"]))
            pintor.drawRoundedRect(QRectF(BORDA_CAIXA, y + BORDA_CAIXA, lado - 2 * BORDA_CAIXA,
                                          lado - 2 * BORDA_CAIXA), RAIO_CAIXA / 2, RAIO_CAIXA / 2)
        pintar_caixa(pintor, 0, y, marcada, sobre=sobre, lado=lado)
        pintor.setPen(cor_do_texto(self.isEnabled()))
        pintor.setFont(self.font())
        x_texto = lado + VAO_TEXTO_CAIXA
        pintor.drawText(QRectF(x_texto, 0, self.width() - x_texto, self.height()),
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())
        pintor.end()
