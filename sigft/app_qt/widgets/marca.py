"""A marca do alto da barra lateral: o símbolo da GE Vernova e o nome do SIG-FT,
num botão só que volta à Home (sistema visual, 2026-10-20).

O pedido foi o "logo do SIG-FT e da GE": na barra, o da GE é a imagem
(`assets/logo.png`) e o do SIG-FT é o nome escrito embaixo dela. Os dois
moram aqui dentro, então acendem juntos e levam ao mesmo lugar.

Sob o mouse (e com o foco) a marca ganha um brilho na cor `primaria` do tema:
uma sombra sem deslocamento, cujo raio cresce de 0 a `BRILHO_MAXIMO` em
`DURACAO_MS`. Quem desligou as animações no sistema (o Qt responde por
`UI_AnimateMenu`) recebe o brilho direto, sem a transição.

As medidas são as de antes (o rótulo do logo com 180 px de largura e o nome
logo abaixo, no `ESPACO_MENU`): virar botão não mexe no x nem no y de nada
da barra.
"""
from __future__ import annotations

import os

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from sigft.app_qt import estilo, tema

BRILHO_MAXIMO = 18
DURACAO_MS = 150
LARGURA_LOGO = 180
NOME = "SIG-FT System"
DICA = "Voltar ao início"
# A opacidade do brilho por tema. O símbolo da GE tem as letras VAZADAS (o
# fundo aparece por elas), e a sombra preenche o vazado: no escuro, a
# `primaria` (#00C975) inteira apagava o "GE" dentro do círculo. A meia força
# ainda brilha e deixa as letras lerem; no claro a `primaria` é escura e
# inteira mal aparece sobre o branco, então fica cheia.
ALFA_DO_BRILHO = {"escuro": 120, "claro": 255}
# A pasta `assets` pela mesma raiz dos ícones (no `.exe`, `_internal/assets`).
LOGO_PADRAO = os.path.join(os.path.dirname(estilo.PASTA_ICONES), "logo.png")


class Marca(QPushButton):
    """Logo + nome, clicável. `clicked` é ligado pela janela ao `show_home`."""

    def __init__(self, caminho_logo: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("marca")
        self.setToolTip(DICA)
        self.setAccessibleName("SIG-FT, voltar ao início")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(estilo.ESPACO_MENU)
        self.logo = QLabel()
        caminho = caminho_logo or LOGO_PADRAO
        if os.path.exists(caminho):
            self.logo.setPixmap(QPixmap(caminho).scaledToWidth(
                LARGURA_LOGO, Qt.TransformationMode.SmoothTransformation))
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.nome = QLabel(NOME, objectName="app_nome")
        self.nome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for rotulo in (self.logo, self.nome):
            # O clique e o mouse são do botão, não dos rótulos por cima dele.
            rotulo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            lay.addWidget(rotulo)

        self._brilho = QGraphicsDropShadowEffect(self)
        self._brilho.setOffset(0, 0)
        self._brilho.setBlurRadius(0)
        # Apagado, o efeito fica desligado: sombra de raio 0 sem deslocamento
        # ainda tingiria a borda do logo.
        self._brilho.setEnabled(False)
        self._brilho.blurRadiusChanged.connect(self._ao_mudar_brilho)
        self.setGraphicsEffect(self._brilho)
        self._animacao = QPropertyAnimation(self._brilho, b"blurRadius", self)
        self._animacao.setDuration(DURACAO_MS)
        self._animacao.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._pintar_cor()
        # Método ligado (e não `lambda` com `self`): o Qt desfaz a ligação
        # quando a marca morre, e o sinal do módulo não segura a janela viva.
        tema.mudou.connect(self._pintar_cor)

    # -- medidas ------------------------------------------------------------
    # O `QPushButton` mede só o texto e o ícone dele (que aqui não há): quem
    # diz o tamanho é o layout dos dois rótulos.
    def sizeHint(self):  # noqa: N802 -- nome do Qt
        return self.layout().sizeHint()

    def minimumSizeHint(self):  # noqa: N802 -- nome do Qt
        return self.layout().minimumSize()

    # -- cor ----------------------------------------------------------------
    def _pintar_cor(self, _tema: str | None = None) -> None:
        cor = QColor(estilo.paleta_atual()["primaria"])
        cor.setAlpha(ALFA_DO_BRILHO.get(estilo.TEMA_ATUAL, 255))
        self._brilho.setColor(cor)

    # -- brilho -------------------------------------------------------------
    def _ao_mudar_brilho(self, raio: float) -> None:
        self._brilho.setEnabled(raio > 0.5)

    def _brilhar(self, alvo: float) -> None:
        self._animacao.stop()
        if not QApplication.isEffectEnabled(Qt.UIEffect.UI_AnimateMenu):
            self._brilho.setBlurRadius(alvo)
            return
        self._animacao.setStartValue(self._brilho.blurRadius())
        self._animacao.setEndValue(float(alvo))
        self._animacao.start()

    def enterEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        super().enterEvent(evento)
        self._brilhar(BRILHO_MAXIMO)

    def leaveEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        super().leaveEvent(evento)
        if not self.hasFocus():
            self._brilhar(0)

    def focusInEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        super().focusInEvent(evento)
        self._brilhar(BRILHO_MAXIMO)

    def focusOutEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        super().focusOutEvent(evento)
        if not self.underMouse():
            self._brilhar(0)
