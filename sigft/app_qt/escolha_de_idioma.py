"""A pergunta do idioma na primeira abertura (2026-10-22).

Sem idioma nas preferências (instalação nova, e também quem recebe a
atualização), antes de montar a janela principal: uma caixa pequena,
"Idioma / Language", com os três idiomas, cada um escrito no seu. A janela já
abre no escolhido (sem reiniciar). Fechar sem escolher: português, e pergunta de
novo na próxima abertura (nada é guardado).

Chamada pelo `main.main`, nunca pelo `SIG_FT_App` (nenhum teste que monta a
janela fica esperando) nem no `--smoke`. Nos testes, `ENV_DESLIGAR` (conftest).
"""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout

from sigft.app import idioma
from sigft.app_qt.widgets import blocos
from sigft.app_qt import propriedades

ENV_DESLIGAR = "SIGFT_SEM_PERGUNTA_DO_IDIOMA"
# Nos dois idiomas de propósito: quem abre ainda não escolheu nenhum.
TITULO = "Idioma / Language"
LARGURA_BOTAO = 130
ALTURA_BOTAO = 36


class PerguntaDoIdioma(QDialog):
    """Três botões; o clique guarda a escolha em `escolha` e fecha."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(TITULO)
        self.setModal(True)
        self.escolha: str | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)
        lay.addWidget(blocos.rotulo(TITULO, tamanho=16, negrito=True))
        linha = QHBoxLayout()
        linha.setSpacing(10)
        self.botoes = {}
        for codigo in idioma.IDIOMAS:
            botao = blocos.botao(idioma.NOMES[codigo],
                                 variante="primario" if codigo == idioma.PADRAO else "secundario",
                                 largura=LARGURA_BOTAO, altura=ALTURA_BOTAO)
            botao.setAutoDefault(False)
            botao.setProperty("escolha", codigo)
            botao.clicked.connect(self._escolher)
            self.botoes[codigo] = botao
            linha.addWidget(botao, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addLayout(linha)

    def _escolher(self) -> None:
        self.escolha = propriedades.ler(self.sender(), "escolha")
        self.accept()


def _abrir_caixa() -> str | None:
    caixa = PerguntaDoIdioma()
    caixa.exec()
    return caixa.escolha


def perguntar_na_abertura(*, abrir=None) -> str | None:
    """Pergunta, se ainda não há idioma escolhido, e guarda a resposta. Devolve o
    idioma escolhido agora, ou `None` (não perguntou, ou fechou sem escolher).
    `abrir()` é a costura do teste."""
    if "--smoke" in sys.argv or os.environ.get(ENV_DESLIGAR) or idioma.escolhido() is not None:
        return None
    escolha = (abrir or _abrir_caixa)()
    if escolha not in idioma.IDIOMAS:
        return None
    return idioma.guardar(escolha)
