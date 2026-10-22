"""A faixa "Rodando…" de cada tela (2026-10-20).

Robô de portal leva minutos, e antes a única pista de que ele seguia vivo era
o console rolando -- quando a ficha demorava (um campo esperando 20 s), a tela
parecia travada. A faixa aparece sozinha quando `ModuleFrame.iniciar_tarefa`
começa, conta o tempo, mostra "Ficha 3 de 8" quando a tela informa o avanço
(`ModuleFrame.informar_progresso`) e diz como terminou.

Escondida enquanto nada roda: escondida, ela não ocupa espaço, e as medidas
das telas paradas ficam as mesmas de antes.
"""
from __future__ import annotations

import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget

from sigft.app.idioma import marcar, t
from sigft.app_qt.widgets import blocos

# Quanto o "Terminou" fica na tela antes de a faixa sumir.
SEGUNDOS_DO_FIM = 12

# O que se conta no "Ficha 3 de 8": a tela passa um destes (marcados), e a
# faixa traduz na hora de mostrar. Rótulo que não está aqui aparece como veio
# (2026-10-22).
ROTULO_ITEM = marcar("item")
ROTULO_FICHA = marcar("ficha")


def relogio(segundos: float) -> str:
    """125 -> "02:05"; com hora: "1:02:05"."""
    total = int(max(segundos, 0))
    horas, resto = divmod(total, 3600)
    minutos, seg = divmod(resto, 60)
    return f"{horas}:{minutos:02d}:{seg:02d}" if horas else f"{minutos:02d}:{seg:02d}"


class FaixaDeAtividade(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("faixa_atividade")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        self.rotulo = QLabel(objectName="faixa_atividade_texto")
        self.barra: QProgressBar = blocos.barra_progresso(altura=8)
        lay.addWidget(self.rotulo)
        lay.addWidget(self.barra, 1)
        self._inicio = 0.0
        self._avanco = ""
        self._relogio = QTimer(self)
        self._relogio.setInterval(1000)
        self._relogio.timeout.connect(self._atualizar)
        self._sumir = QTimer(self)
        self._sumir.setSingleShot(True)
        self._sumir.timeout.connect(self.hide)
        self.hide()

    # -- estado -----------------------------------------------------------------
    @property
    def rodando(self) -> bool:
        return self._relogio.isActive()

    def comecar(self) -> None:
        self._sumir.stop()
        self._inicio = time.monotonic()
        self._avanco = ""
        self.barra.setRange(0, 0)          # sem total: a barra anda sozinha
        self._relogio.start()
        self._atualizar()
        self.show()

    def progresso(self, atual: int, total: int, rotulo: str = ROTULO_ITEM) -> None:
        if not self.rodando or total <= 0:
            return
        atual = min(max(int(atual), 0), int(total))
        self._avanco = t("{rotulo} {atual} de {total}", rotulo=t(rotulo).capitalize(), atual=atual, total=total)
        if self.barra.maximum() == 0:
            self.barra.setRange(0, 1000)
        blocos.definir_progresso(self.barra, atual / total)
        self._atualizar()

    def terminar(self, ok: bool = True) -> None:
        if not self.rodando:
            return
        self._relogio.stop()
        decorrido = relogio(time.monotonic() - self._inicio)
        if ok:
            self.rotulo.setText("✓  " + t("Terminou em {tempo}", tempo=decorrido))
            self.rotulo.setProperty("estado", "ok")
            self.barra.setRange(0, 1000)
            blocos.definir_progresso(self.barra, 1.0)
        else:
            self.rotulo.setText("✗  " + t("Parou com erro depois de {tempo}. Veja o console.", tempo=decorrido))
            self.rotulo.setProperty("estado", "erro")
            self.barra.setRange(0, 1000)
            self.barra.setValue(0)
        self._repolir()
        self._sumir.start(SEGUNDOS_DO_FIM * 1000)

    # -- desenho ----------------------------------------------------------------
    def _atualizar(self) -> None:
        partes = ["⏳  " + t("Rodando"), relogio(time.monotonic() - self._inicio)]
        if self._avanco:
            partes.insert(1, self._avanco)
        self.rotulo.setText("  ·  ".join(partes))
        if self.rotulo.property("estado") != "rodando":
            self.rotulo.setProperty("estado", "rodando")
            self._repolir()

    def _repolir(self) -> None:
        self.rotulo.style().unpolish(self.rotulo)
        self.rotulo.style().polish(self.rotulo)
