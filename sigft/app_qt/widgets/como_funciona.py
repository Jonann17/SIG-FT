"""O "Como funciona": a ajuda de cada tela, logo abaixo do título (2026-10-28).

Ideia do Corella Automation (`corella_suite/ui/widgets/como_funciona.py`, v1.4.0):
ajuda no MESMO lugar em toda tela é ajuda que se acha sem procurar. Uma frase
curta, sempre à vista, diz o que a tela faz; o botão "Como funciona" abre os
itens: o que a tela espera receber, o que ela muda e o que acontece se parar no
meio. Fechado na primeira vez; aberto ou fechado fica lembrado por tela (`prefs`,
chave `como_funciona_aberto.<tela>`), como as colunas e o console.

Os textos moram em `sigft/app/como_funciona.py` (sem Qt). A tela chama
`instalar_como_funciona(self, "<chave>")` no fim do `_build_ui`; uma seção de abas
passa as chaves das abas, e o bloco mostra o texto da aba aberta. A tela embutida
numa aba não ganha bloco: a ajuda dela é a da aba, no bloco da seção.

Desenho: `docs/superpowers/specs/2026-10-28-ajuda-para-quem-comeca-design.md`.
"""
from __future__ import annotations

import logging
import os

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from sigft.app import como_funciona as textos
from sigft.app.idioma import marcar, t
from sigft.app_qt import icones
from sigft.app_qt.widgets import blocos

_log = logging.getLogger(__name__)

ROTULO_FECHADO = marcar("Como funciona")
ROTULO_ABERTO = marcar("Ocultar detalhes")
ICONE = "circle-help"
TAMANHO_ICONE = 14
MARCADOR = "•"
# Entre a frase e o botão; entre um item e o outro; do marcador ao texto.
ESPACO_DA_LINHA = 12
ESPACO_ENTRE_ITENS = 4
RECUO_DO_TEXTO = 8
# Do título ao bloco (o cabeçalho é um QVBoxLayout de espaçamento padrão).
ESPACO_DO_TITULO = 4
# Ligada, nenhuma tela ganha o bloco. Só os testes a ligam (`tests/conftest.py`):
# os testes de medida das telas conferem cada pixel contra a interface antiga, que
# não tinha o bloco. Quem testa o bloco, ou varre as telas com ele, tira a variável.
ENV_DESLIGAR = "SIGFT_SEM_COMO_FUNCIONA"
# Janela sem altura para os itens: eles rolam a partir daqui (uns dois itens).
ALTURA_MINIMA_DOS_ITENS = 48


def _arquivo_de_prefs():
    """O mesmo arquivo do tema, da letra e do console. Função para os testes
    apontarem outro."""
    from sigft.app_qt import tema
    return tema._arquivo_de_prefs()


def ler_aberto(chave: str) -> bool:
    """Se o bloco da `chave` estava aberto. Preferência que não se lê é fechado."""
    from sigft.core import prefs

    try:
        valor = prefs.ler_preferencia(textos.chave_da_preferencia(chave), "",
                                      config_path=_arquivo_de_prefs())
    except Exception:  # noqa: BLE001 -- preferência é conveniência
        _log.warning("nao consegui ler o estado do Como funciona", exc_info=True)
        return False
    return valor == "sim"


def gravar_aberto(chave: str, aberto: bool) -> None:
    """Guarda o estado. Falha vira aviso no log, nunca exceção na tela."""
    from sigft.core import prefs

    try:
        prefs.gravar_preferencia(textos.chave_da_preferencia(chave), "sim" if aberto else "nao",
                                 config_path=_arquivo_de_prefs())
    except Exception:  # noqa: BLE001 -- preferência é conveniência
        _log.warning("nao consegui gravar o estado do Como funciona", exc_info=True)


class _RolagemDosItens(QScrollArea):
    """A área dos itens: pede a altura dos itens na largura que tem, e aceita
    encolher até `ALTURA_MINIMA_DOS_ITENS`, rolando o resto."""

    def __init__(self, lista: QWidget) -> None:
        super().__init__(objectName="como_funciona_detalhe")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(lista)
        # Transparente: o `setWidget` liga o autoFill, que pintava a paleta do Qt.
        lista.setAutoFillBackground(False)
        self.viewport().setAutoFillBackground(False)
        self._largura = -1

    def _altura_dos_itens(self) -> int:
        lista = self.widget()
        largura = self.viewport().width()
        if largura <= 0:
            return lista.sizeHint().height()
        return lista.heightForWidth(largura) if lista.hasHeightForWidth() else lista.sizeHint().height()

    def sizeHint(self) -> QSize:  # noqa: N802 -- nome do Qt
        return QSize(super().sizeHint().width(), self._altura_dos_itens() + 2 * self.frameWidth())

    def minimumSizeHint(self) -> QSize:  # noqa: N802 -- nome do Qt
        return QSize(0, min(self.sizeHint().height(), ALTURA_MINIMA_DOS_ITENS))

    def resizeEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        super().resizeEvent(evento)
        # Na largura nova os itens quebram em outro número de linhas.
        if self.viewport().width() != self._largura:
            self._largura = self.viewport().width()
            self.updateGeometry()


class ComoFunciona(QWidget):
    """A frase, o botão e os itens da `chave` (de `sigft/app/como_funciona.TEXTOS`)."""

    def __init__(self, chave: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("como_funciona")
        self.chave = ""
        self._gravar = True
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(ESPACO_ENTRE_ITENS)

        linha = QHBoxLayout()
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(ESPACO_DA_LINHA)
        self.frase = QLabel()
        self.frase.setProperty("papel", "legenda")
        self.frase.setWordWrap(True)
        linha.addWidget(self.frase, 1)
        self.botao = blocos.botao(t(ROTULO_FECHADO), variante="secundario")
        # Compacto (folha `#como_funciona_botao`, em `estilo`): na altura da
        # linha da frase, o bloco fechado custa uma linha de texto.
        self.botao.setObjectName("como_funciona_botao")
        self.botao.setCheckable(True)
        self.botao.setCursor(Qt.CursorShape.PointingHandCursor)
        icones.aplicar(self.botao, ICONE, tamanho=TAMANHO_ICONE)
        self.botao.toggled.connect(self._clicou)
        linha.addWidget(self.botao, 0, Qt.AlignmentFlag.AlignTop)
        raiz.addLayout(linha)

        # Os itens rolam quando a janela não tem altura para eles: abrir a ajuda
        # nunca empurra a janela para além da tela (as telas de upload já pedem
        # 750 px dos 850).
        self._lista = QWidget(objectName="como_funciona_lista")
        self._lista.setAutoFillBackground(False)
        self._grade = QGridLayout(self._lista)
        self._grade.setContentsMargins(0, 0, 0, 0)
        self._grade.setHorizontalSpacing(RECUO_DO_TEXTO)
        self._grade.setVerticalSpacing(ESPACO_ENTRE_ITENS)
        self._grade.setColumnStretch(1, 1)
        self._itens: list[QLabel] = []
        self.detalhe = _RolagemDosItens(self._lista)
        self.detalhe.setVisible(False)
        raiz.addWidget(self.detalhe)

        self.mostrar(chave)

    # -- o texto ---------------------------------------------------------------
    def mostrar(self, chave: str) -> None:
        """Mostra o texto da `chave`, aberto ou fechado como ficou da última vez."""
        if chave == self.chave:
            return
        self.chave = chave
        texto = textos.traduzido(chave)
        self.frase.setText(texto.frase)
        for antigo in self._lista.findChildren(QLabel):
            self._grade.removeWidget(antigo)
            antigo.setParent(None)
            antigo.deleteLater()
        self._itens = []
        for linha, item in enumerate(texto.itens):
            marcador = QLabel(MARCADOR, objectName="como_funciona_marcador")
            marcador.setProperty("papel", "legenda")
            rotulo = QLabel(item)
            rotulo.setWordWrap(True)
            rotulo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._grade.addWidget(marcador, linha, 0, Qt.AlignmentFlag.AlignTop)
            self._grade.addWidget(rotulo, linha, 1)
            self._itens.append(rotulo)
        self.detalhe.updateGeometry()
        self.alternar(ler_aberto(chave), gravar=False)

    def rotulos_dos_itens(self) -> list[QLabel]:
        return list(self._itens)

    # -- aberto/fechado ----------------------------------------------------------
    def aberto(self) -> bool:
        return self.botao.isChecked()

    def alternar(self, aberto: bool, *, gravar: bool = True) -> None:
        """Abre ou fecha. `gravar=False` não mexe na preferência (a varredura
        dos testes abre todos para medir)."""
        self._gravar = gravar
        try:
            if self.botao.isChecked() != aberto:
                self.botao.setChecked(aberto)   # volta por `_clicou`
            else:
                self._aplicar(aberto)
        finally:
            self._gravar = True

    def _clicou(self, aberto: bool) -> None:
        self._aplicar(aberto)
        if self._gravar:
            gravar_aberto(self.chave, aberto)

    def _aplicar(self, aberto: bool) -> None:
        self.detalhe.setVisible(aberto)
        rotulo = t(ROTULO_ABERTO if aberto else ROTULO_FECHADO)
        self.botao.setText(rotulo)
        self.botao.setAccessibleName(rotulo)


class _SegueAsAbas:
    """Troca o texto do bloco quando a aba da seção muda (o clique e o `set`)."""

    def __init__(self, bloco: ComoFunciona, abas, chave_da_aba: dict) -> None:
        self.bloco = bloco
        self.abas = abas
        self.chave_da_aba = chave_da_aba
        abas.pilha.currentChanged.connect(self.mudou)

    def mudou(self, *_args) -> None:
        chave = self.chave_da_aba.get(self.abas.get())
        if chave:
            self.bloco.mostrar(chave)


def instalar_como_funciona(tela, chave: str | dict, *, abas=None) -> ComoFunciona | None:
    """Põe o bloco logo abaixo do título do `ModuleFrame`, o mesmo lugar em toda tela.

    `chave`: a do texto (`sigft/app/como_funciona.TEXTOS`); numa seção de abas,
    `{nome da aba na tela: chave}` com as `abas` (`widgets.abas.Abas`), e o bloco
    segue a aba aberta. Tela embutida (sem cabeçalho), ou com `ENV_DESLIGAR`, não
    ganha bloco: devolve `None`.
    """
    if getattr(tela, "header", None) is None or os.environ.get(ENV_DESLIGAR):
        return None
    if isinstance(chave, dict):
        if abas is None:
            raise ValueError("Seção de abas precisa das `abas`.")
        chave_da_aba = dict(chave)
        bloco = ComoFunciona(chave_da_aba.get(abas.get()) or next(iter(chave_da_aba.values())))
        tela._segue_as_abas = _SegueAsAbas(bloco, abas, chave_da_aba)
    else:
        bloco = ComoFunciona(chave)
    cabecalho = tela.header.layout()
    cabecalho.setSpacing(ESPACO_DO_TITULO)
    cabecalho.insertWidget(1, bloco)
    tela.como_funciona = bloco
    return bloco
