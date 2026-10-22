"""A barrinha que muda o tamanho do console embaixo das telas (2026-10-21).

Pedido do Luan: a pessoa arrasta a barrinha entre a tela e o console para
aumentar ou diminuir o console; cada tela lembra o tamanho, e o duplo clique
volta ao padrão.

Por que uma barrinha SOLTA e não um `QSplitter`: as telas montam a coluna de
jeitos diferentes (espaçamentos inseridos por índice, o console numa faixa na
Correção de PDM, a altura repartida no `resizeEvent` na Criação e na Cópia) e os
testes de medida conferem cada pixel contra a tela antiga. Um splitter mudaria a
árvore e a medida de todas; a barrinha é filha da tela, fora do layout, e fica
no vão que já existe acima do console. Sem arrastar, nada sai do lugar.

Quem decide a altura é a tela (`ModuleFrame`): a barrinha só mede o arrasto. A
preferência fica em `prefs` (chave `console.<classe da tela>`); ler ou gravar
que falha vira aviso no log e nunca derruba a tela.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QWidget

from sigft.app.idioma import marcar, t
from sigft.app_qt.widgets.console import ALTURA_BARRA, RECUO_TEXTO_CTK

_log = logging.getLogger(__name__)

ALTURA_PUXADOR = 6
# Do fim da barrinha ao topo do console: o vão mais estreito das telas é 10 px
# (Criação, Cópia, Gestão de Sobressalentes); 6 + 2 cabem nele.
FOLGA_ATE_O_CONSOLE = 2
LARGURA_MARCA = 36
DICA = marcar("Arraste para mudar o tamanho do console. Duplo clique volta ao tamanho padrão.")
# O que a tela guarda para o conteúdo, no mínimo, quando o console cresce.
MIN_CONTEUDO = 120
# Espera depois do último movimento antes de gravar (e ao esconder a tela, na hora).
MS_PARA_GRAVAR = 400
PREFIXO_CHAVE = "console."


def chave_da_tela(tela) -> str:
    return f"{PREFIXO_CHAVE}{type(tela).__name__}"


def altura_minima_do_console(console) -> int:
    """A barra do filtro e duas linhas de texto."""
    linha = console.fontMetrics().lineSpacing()
    _, cima = RECUO_TEXTO_CTK
    margem_doc = int(console.document().documentMargin())
    return ALTURA_BARRA + cima + 2 * linha + 2 * margem_doc + 2 * console.frameWidth()


def _arquivo_de_prefs():
    """O mesmo arquivo do tema e da letra. Função para os testes apontarem outro."""
    from sigft.app_qt import tema
    return tema._arquivo_de_prefs()


def ler_altura(tela) -> int | None:
    """A altura guardada para a tela, ou `None` (nunca guardada, estragada, ou o
    arquivo não se deixa ler)."""
    from sigft.core import prefs

    try:
        texto = prefs.ler_preferencia(chave_da_tela(tela), "", config_path=_arquivo_de_prefs())
    except Exception:  # noqa: BLE001 -- preferência é conveniência
        _log.warning("nao consegui ler o tamanho do console", exc_info=True)
        return None
    try:
        valor = int(texto)
    except (TypeError, ValueError):
        return None
    return valor if valor > 0 else None


def gravar_altura(tela, altura: int | None) -> None:
    """Guarda a altura (`None` esquece). Falha vira aviso no log."""
    from sigft.core import prefs

    try:
        prefs.gravar_preferencia(chave_da_tela(tela), "" if altura is None else str(int(altura)),
                                 config_path=_arquivo_de_prefs())
    except Exception:  # noqa: BLE001 -- lembrar não pode derrubar a tela
        _log.warning("nao consegui gravar o tamanho do console", exc_info=True)


class PuxadorDoConsole(QWidget):
    """A barrinha. Filha da tela, posta à mão logo acima do console; segue o
    console (filtro de eventos nele e nos pais dele até a tela)."""

    def __init__(self, tela) -> None:
        super().__init__(tela)
        self.setObjectName("puxador_console")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.SplitVCursor)
        self.setToolTip(t(DICA))
        self.setFixedHeight(ALTURA_PUXADOR)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        self.marca = QWidget(objectName="puxador_console_marca")
        self.marca.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.marca.setFixedSize(LARGURA_MARCA, ALTURA_PUXADOR - 4)
        self.marca.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lay.addWidget(self.marca, 0, Qt.AlignmentFlag.AlignCenter)
        self._tela = tela
        # Arrastando: onde a barrinha foi pega (px abaixo do topo dela) e a base
        # das peças do console na tela (y global), que não sai do lugar.
        self._pega: float | None = None
        self._base = 0
        self._limites = (0, 0)
        self._vigiados: list[QWidget] = []
        # Letra ou tema trocados: o mínimo do console pode ter subido. A conta
        # espera o Qt terminar de repolir (um disparo só por troca).
        self._reajuste = QTimer(self)
        self._reajuste.setSingleShot(True)
        self._reajuste.setInterval(0)
        self._reajuste.timeout.connect(self._reajustar)
        self._vigiar()
        self.reposicionar()

    # -- seguir o console --------------------------------------------------------
    def _vigiar(self) -> None:
        widget = self._tela.console
        while widget is not None and widget is not self._tela:
            widget.installEventFilter(self)
            self._vigiados.append(widget)
            widget = widget.parentWidget()

    def eventFilter(self, obj, evento) -> bool:  # noqa: N802 -- nome do Qt
        if evento.type() in (QEvent.Type.Move, QEvent.Type.Resize,
                             QEvent.Type.Show, QEvent.Type.Hide):
            self.reposicionar()
        elif evento.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange) \
                and obj is self._tela.console:
            self._reajuste.start()
        return False

    def _reajustar(self) -> None:
        try:
            self._tela._ajustar_console_ao_espaco()
            self.reposicionar()
        except RuntimeError:
            pass  # tela destruída antes do disparo

    def reposicionar(self) -> None:
        console = self._tela.console
        try:
            topo = console.mapTo(self._tela, console.rect().topLeft())
        except RuntimeError:
            return  # console destruído com a tela
        self.setGeometry(topo.x(), topo.y() - FOLGA_ATE_O_CONSOLE - ALTURA_PUXADOR,
                         console.width(), ALTURA_PUXADOR)
        self.setVisible(console.isVisibleTo(self._tela) and console.height() > 0)
        self.raise_()

    # -- destaque (hover e arrasto) ----------------------------------------------
    def _destacar(self, ligado: bool) -> None:
        if bool(self.property("ativo")) == ligado:
            return
        for widget in (self, self.marca):
            widget.setProperty("ativo", ligado)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def enterEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        self._destacar(True)
        super().enterEvent(evento)

    def leaveEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        if self._pega is None:
            self._destacar(False)
        super().leaveEvent(evento)

    # -- arrastar ----------------------------------------------------------------
    def mousePressEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        if evento.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(evento)
        self._pega = evento.globalPosition().y() - self.mapToGlobal(QPoint(0, 0)).y()
        self._base = self._tela.base_do_console_global()
        self._limites = self._tela.limites_do_console()
        self._destacar(True)
        evento.accept()

    def mouseMoveEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        if self._pega is None:
            return super().mouseMoveEvent(evento)
        minimo, maximo = self._limites
        # A barrinha vai para onde o cursor está; o console ocupa da barrinha
        # até a base. Na Correção de PDM a faixa é maior que o console centrado
        # nela: no primeiro movimento o console passa a encher a faixa, e a
        # barrinha segue o cursor sem pular (revisão de 2026-10-21).
        topo = evento.globalPosition().y() - self._pega
        altura = self._base - round(topo) - ALTURA_PUXADOR - FOLGA_ATE_O_CONSOLE
        self._tela.escolher_altura_do_console(max(minimo, min(altura, maximo)))
        evento.accept()

    def mouseReleaseEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        if self._pega is None:
            return super().mouseReleaseEvent(evento)
        self._pega = None
        if not self.underMouse():
            self._destacar(False)
        evento.accept()

    def mouseDoubleClickEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        if evento.button() != Qt.MouseButton.LeftButton:
            return super().mouseDoubleClickEvent(evento)
        self._pega = None
        self._tela.console_ao_padrao()
        evento.accept()
