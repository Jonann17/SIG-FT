"""Console de log das telas, rápido e seguro para chamar de qualquer thread.

O `CTkTextbox` reescrevia e rolava a cada linha; num lote de milhares de linhas
isso pesava. Aqui as linhas que chegam são juntadas e escritas em LOTE a cada
`INTERVALO_MS` (medido no protótipo: 10.000 linhas em ~0,1 s), e o console
guarda no máximo `MAX_LINHAS` -- as mais antigas saem.

Filtro (2026-10-21, etapa 1b): cada linha guarda o nível (`sigft/app/niveis_log`),
e a barra de BAIXO mostra "Tudo / Avisos / Erros", uma busca sem acento e sem
caixa e "Copiar" (o que está à vista). A barra mora na margem de baixo da vista:
a altura do console e o começo do texto são os de antes (testes de medida das
telas). As linhas ficam guardadas com um número de ordem: `marca()` e
`linhas(desde=...)` são o que a janela de resumo do lote lê.
"""
from __future__ import annotations

import threading
from collections import deque
from typing import NamedTuple

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QHBoxLayout, QLineEdit, QPlainTextEdit, QPushButton, QWidget,
)

from sigft.app import busca, niveis_log, theme
from sigft.app_qt import interface
from sigft.app_qt.widgets import blocos

PREFIXO_LINHA = "> "
INTERVALO_MS = 50
MAX_LINHAS = 20_000
# Onde o texto começa no CTkTextbox, a mais do que no QPlainTextEdit cru (que já
# tem a margem de 4 do documento): 4 px à direita e 5 px abaixo, medidos nas
# capturas do polimento (Tradutor, PDM e Upload: o ">" e a base da 1a linha).
RECUO_TEXTO_CTK = (4, 5)
# A barra do filtro, na margem de baixo da vista (2026-10-21).
ALTURA_BARRA = 28
FILTROS = (("tudo", "Tudo"), ("avisos", "Avisos"), ("erros", "Erros"))
# "Avisos" mostra avisos E erros: tudo o que pede atenção.
NIVEIS_DO_FILTRO = {
    "tudo": None,
    "avisos": frozenset({niveis_log.AVISO, niveis_log.ERRO}),
    "erros": frozenset({niveis_log.ERRO}),
}
TEXTO_BUSCA = "Buscar no console"
TEXTO_COPIAR = "Copiar"
TEXTO_COPIADO = "Copiado"
DICA_COPIAR = "Copia as linhas que estão à vista, com o filtro e a busca de agora."
MS_DO_COPIADO = 1500
# A busca espera a pessoa parar de digitar: redesenhar até `MAX_LINHAS` linhas a
# cada tecla pesa (revisão de 2026-10-21). Os botões do filtro são imediatos.
MS_DA_BUSCA = 150


class Linha(NamedTuple):
    """Uma linha do console: número de ordem, a mensagem (sem o "> ") e o nível."""
    seq: int
    msg: str
    nivel: str


def formatar_linha(msg: object) -> str:
    """A linha como as telas escrevem: ``"> {msg}"``. Aceita qualquer objeto."""
    return f"{PREFIXO_LINHA}{msg}"


class BarraDoConsole(QWidget):
    """Tudo / Avisos / Erros, a busca e o Copiar. Filha do console; os sinais vão
    a métodos DESTA barra (nada de lambda com o console: mural de 2026-10-14)."""

    def __init__(self, console: "ConsoleFrame") -> None:
        super().__init__(console)
        self.setObjectName("barra_console")
        # Sem isto um QWidget comum não pinta o `background` da folha.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(4)
        self.grupo = QButtonGroup(self)
        self.grupo.setExclusive(True)
        self.botoes: dict[str, QPushButton] = {}
        for indice, (chave, texto) in enumerate(FILTROS):
            botao = QPushButton(texto)
            blocos.sem_tecla(botao)
            botao.setCheckable(True)
            self.grupo.addButton(botao, indice)
            self.botoes[chave] = botao
            lay.addWidget(botao)
        self.botoes["tudo"].setChecked(True)
        self.grupo.idClicked.connect(self._escolheu_filtro)
        lay.addSpacing(8)
        self.campo = QLineEdit()
        self.campo.setPlaceholderText(TEXTO_BUSCA)
        self.campo.setClearButtonEnabled(True)
        self.campo.textChanged.connect(self._digitou)
        self._espera_da_busca = QTimer(self)
        self._espera_da_busca.setSingleShot(True)
        self._espera_da_busca.setInterval(MS_DA_BUSCA)
        self._espera_da_busca.timeout.connect(self._buscou)
        lay.addWidget(self.campo, 1)
        self.copiar = QPushButton(TEXTO_COPIAR)
        blocos.sem_tecla(self.copiar)
        self.copiar.setToolTip(DICA_COPIAR)
        self.copiar.clicked.connect(self._copiar)
        lay.addWidget(self.copiar)
        self._volta = QTimer(self)
        self._volta.setSingleShot(True)
        self._volta.timeout.connect(self._texto_do_copiar)

    def marcar(self, filtro: str) -> None:
        botao = self.botoes[filtro]
        if not botao.isChecked():
            botao.setChecked(True)

    def _escolheu_filtro(self, indice: int) -> None:
        self.parentWidget().filtrar(FILTROS[indice][0])

    def _digitou(self, _texto: str) -> None:
        self._espera_da_busca.start()   # recomeça a cada tecla

    def _buscou(self) -> None:
        self.parentWidget().buscar(self.campo.text())

    def _copiar(self) -> None:
        if not self.parentWidget().copiar():
            return
        self.copiar.setText(TEXTO_COPIADO)
        self._volta.start(MS_DO_COPIADO)

    def _texto_do_copiar(self) -> None:
        self.copiar.setText(TEXTO_COPIAR)


class ConsoleFrame(QPlainTextEdit):
    def __init__(self, parent=None, *, altura: int | None = theme.ALTURA_CONSOLE) -> None:
        super().__init__(parent)
        self.setObjectName("console")
        self.setReadOnly(True)
        self.setMaximumBlockCount(MAX_LINHAS)
        if altura is not None:
            self.setFixedHeight(altura)
        # Só a vista recua (a barra de rolagem continua com a altura toda); a
        # faixa que sobra é o fundo do próprio console, da mesma cor. Embaixo, a
        # margem é a da barra do filtro (`_posicionar_barra`).
        esquerda, cima = RECUO_TEXTO_CTK
        self.setViewportMargins(esquerda, cima, 0, ALTURA_BARRA)
        # Cada linha vai junto com o texto já normalizado (`busca.normalizar`):
        # a busca não normaliza de novo as 20.000 linhas a cada consulta.
        self._pendentes: deque[tuple[Linha, str]] = deque()
        self._linhas: deque[tuple[Linha, str]] = deque(maxlen=MAX_LINHAS)
        self._seq = 0
        self._trava = threading.Lock()
        self._agendado = False
        self._filtro = "tudo"
        self._busca = ""   # já normalizada
        self.barra = BarraDoConsole(self)
        self._posicionar_barra()

    # -- protocolo `core/callbacks.py` -----------------------------------------
    def log(self, msg: object, nivel: str = "info", contexto: object | None = None) -> None:
        """Assinatura do protocolo `core/callbacks.py`. Qualquer thread."""
        texto = f"{msg}"
        nivel_da_linha = niveis_log.classificar(texto, nivel)
        normalizada = busca.normalizar(texto)
        with self._trava:
            self._seq += 1
            item = (Linha(self._seq, texto, nivel_da_linha), normalizada)
            self._linhas.append(item)
            self._pendentes.append(item)
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
        visiveis = [linha for linha, normalizada in linhas if self._passa(linha, normalizada)]
        if not visiveis:
            return
        try:
            self.appendPlainText("\n".join(formatar_linha(linha.msg) for linha in visiveis))
            self._rolar_para_o_fim()
        except RuntimeError:
            pass  # widget destruído entre o agendamento e a escrita

    # -- o que a janela de resumo lê -----------------------------------------
    def marca(self) -> int:
        """O número da última linha recebida (0 = nenhuma)."""
        with self._trava:
            return self._seq

    def linhas(self, desde: int = 0) -> list[Linha]:
        """As linhas guardadas depois da `marca` `desde`, na ordem."""
        with self._trava:
            return [linha for linha, _ in self._linhas if linha.seq > desde]

    # -- filtro, busca, copiar -------------------------------------------------
    def _passa(self, linha: Linha, normalizada: str) -> bool:
        niveis = NIVEIS_DO_FILTRO[self._filtro]
        if niveis is not None and linha.nivel not in niveis:
            return False
        return not self._busca or self._busca in normalizada

    def filtrar(self, filtro: str) -> None:
        if filtro not in NIVEIS_DO_FILTRO:
            raise ValueError(f"filtro desconhecido: {filtro!r}")
        self._filtro = filtro
        self.barra.marcar(filtro)
        self._redesenhar()

    def buscar(self, texto: str) -> None:
        self._busca = busca.normalizar(texto or "").strip()
        self._redesenhar()

    def copiar(self) -> bool:
        """Copia o que está à vista. Nada à vista: a área de transferência fica
        como estava e devolve False (o botão não diz "Copiado")."""
        texto = self.toPlainText()
        if not texto:
            return False
        QApplication.clipboard().setText(texto)
        return True

    def _redesenhar(self) -> None:
        with self._trava:
            todas = list(self._linhas)
            self._pendentes.clear()   # já entram no redesenho
        self.setPlainText("\n".join(formatar_linha(linha.msg) for linha, normalizada in todas
                                    if self._passa(linha, normalizada)))
        self._rolar_para_o_fim()

    def clear(self) -> None:  # noqa: D401 -- o `clear` do Qt, que as telas chamam
        """Limpa a tela E as linhas guardadas. A contagem (`marca`) continua."""
        with self._trava:
            self._linhas.clear()
            self._pendentes.clear()
        super().clear()

    # -- desenho -----------------------------------------------------------------
    def _rolar_para_o_fim(self) -> None:
        rolagem = self.verticalScrollBar()
        rolagem.setValue(rolagem.maximum())

    def _posicionar_barra(self) -> None:
        vista = self.viewport().geometry()
        self.barra.setGeometry(0, vista.bottom() + 1, vista.right() + 1, ALTURA_BARRA)

    def viewportEvent(self, evento) -> bool:  # noqa: N802 -- nome do Qt
        # A vista muda de tamanho com a janela e quando a barra de rolagem
        # aparece: a barra do filtro acompanha, sem cobrir a de rolagem.
        if evento.type() == QEvent.Type.Resize:
            self._posicionar_barra()
        return super().viewportEvent(evento)
