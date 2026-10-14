"""Console de log das telas, rápido e seguro para chamar de qualquer thread.

O `CTkTextbox` reescrevia e rolava a cada linha; num lote de milhares de linhas
isso pesava. Aqui as linhas que chegam são juntadas e escritas em LOTE a cada
`INTERVALO_MS` (medido no protótipo: 10.000 linhas em ~0,1 s), e o console
guarda no máximo `MAX_LINHAS` -- as mais antigas saem.
"""
from __future__ import annotations

import threading
from collections import deque

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QPlainTextEdit

from sigft.app import theme
from sigft.app_qt import interface

PREFIXO_LINHA = "> "
INTERVALO_MS = 50
MAX_LINHAS = 20_000
# Onde o texto começa no CTkTextbox, a mais do que no QPlainTextEdit cru (que já
# tem a margem de 4 do documento): 4 px à direita e 5 px abaixo, medidos nas
# capturas do polimento (Tradutor, PDM e Upload: o ">" e a base da 1a linha).
RECUO_TEXTO_CTK = (4, 5)


def formatar_linha(msg: object) -> str:
    """A linha como as telas escrevem: ``"> {msg}"``. Aceita qualquer objeto."""
    return f"{PREFIXO_LINHA}{msg}"


class ConsoleFrame(QPlainTextEdit):
    def __init__(self, parent=None, *, altura: int | None = theme.ALTURA_CONSOLE) -> None:
        super().__init__(parent)
        self.setObjectName("console")
        self.setReadOnly(True)
        self.setMaximumBlockCount(MAX_LINHAS)
        if altura is not None:
            self.setFixedHeight(altura)
        # Só a vista recua (a barra de rolagem continua com a altura toda); a
        # faixa que sobra é o fundo do próprio console, da mesma cor.
        esquerda, cima = RECUO_TEXTO_CTK
        self.setViewportMargins(esquerda, cima, 0, 0)
        self._pendentes: deque[str] = deque()
        self._trava = threading.Lock()
        self._agendado = False

    def log(self, msg: object, nivel: str = "info", contexto: object | None = None) -> None:
        """Assinatura do protocolo `core/callbacks.py`. Qualquer thread."""
        with self._trava:
            self._pendentes.append(formatar_linha(msg))
            if self._agendado:
                return
            self._agendado = True
        try:
            interface.na_interface(self._agendar)
        except RuntimeError:
            # Canal fechado (app fechando) ou ainda não instalado: a linha fica
            # na fila e a PRÓXIMA chamada tenta agendar de novo -- sem isto o
            # `_agendado` ficaria preso em True e o console, mudo para sempre.
            with self._trava:
                self._agendado = False

    def _agendar(self) -> None:
        try:
            QTimer.singleShot(INTERVALO_MS, self._descarregar)
        except RuntimeError:
            pass  # widget destruído

    def _descarregar(self) -> None:
        with self._trava:
            linhas = list(self._pendentes)
            self._pendentes.clear()
            self._agendado = False
        if not linhas:
            return
        try:
            self.appendPlainText("\n".join(linhas))
            barra = self.verticalScrollBar()
            barra.setValue(barra.maximum())
        except RuntimeError:
            pass  # widget destruído entre o agendamento e a escrita
