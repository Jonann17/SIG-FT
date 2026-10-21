"""Arrastar o arquivo para o botão, e os "Últimos arquivos" (2026-10-21, etapa 1b).

`aceitar_arquivo(widget, chave, extensoes, ao_receber)` liga um widget (o botão
que abre o diálogo, ou a linha `FilePickerRow`) a uma chave de diálogo. Soltar
um arquivo nele, ou escolher um dos últimos, ENTREGA o arquivo
(`file_dialogs.entregar`) e chama `ao_receber` (padrão: o clique do botão). O
`ask_open_file(chave)` do clique acha a entrega e não abre o diálogo
(`sigft/app/file_dialogs.py`): nenhuma tela muda o seu `selecionar_...`.
Extensão errada: o widget fica vermelho (`arrasto="recusado"`, cor da folha) e
o soltar não é aceito.

As telas que usam botão declaram `ARRASTAVEIS` (o `ModuleFrame` liga na
montagem, com os últimos arquivos no botão direito). Os sinais vão a métodos
ligados, nunca a lambda com a tela (mural de 2026-10-14).
"""
from __future__ import annotations

import os
from typing import NamedTuple

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QMenu, QToolButton

from sigft.app_qt import estilo, file_dialogs
from sigft.core import prefs

ACEITO = "aceito"
RECUSADO = "recusado"
TEXTO_SEM_RECENTES = "Nenhum arquivo recente"
DICA_ARRASTAR = "Dá para arrastar o arquivo até aqui. Botão direito: últimos arquivos."
SETA_RECENTES = "▾"
DICA_RECENTES = "Últimos arquivos usados aqui"


class Arrastavel(NamedTuple):
    """Um botão de tela que recebe arquivo: o atributo, a chave do diálogo que o
    `selecionar_...` dele usa, as extensões (`None`: qualquer) e se aceita vários."""
    atributo: str
    chave: str
    extensoes: tuple[str, ...] | None
    varios: bool = False


def caminhos_do_arrasto(mime) -> list[str]:
    """Os arquivos locais de um arrasto (do Explorer). Outro conteúdo: lista vazia."""
    if mime is None or not mime.hasUrls():
        return []
    return [url.toLocalFile() for url in mime.urls() if url.isLocalFile() and url.toLocalFile()]


class Receptor(QObject):
    """Filtro de eventos no `widget`: aceita o arrasto e entrega o arquivo."""

    def __init__(self, widget, chave: str, extensoes, ao_receber=None, *, varios: bool = False,
                 destaque=None) -> None:
        super().__init__(widget)
        self.widget = widget
        self.chave = chave
        self.extensoes = tuple(extensoes) if extensoes else None
        self.varios = varios
        self._ao_receber = ao_receber
        self.destaque = destaque if destaque is not None else widget
        self._ok = False
        widget.setAcceptDrops(True)
        widget.installEventFilter(self)

    def aceita(self, caminhos) -> bool:
        if not caminhos or (len(caminhos) > 1 and not self.varios):
            return False
        return all(os.path.isfile(c) and file_dialogs.extensao_aceita(c, self.extensoes) for c in caminhos)

    def receber(self, caminhos) -> None:
        """Entrega `caminhos` e chama `ao_receber` (o clique), como se a pessoa
        os tivesse escolhido no diálogo. A entrega não sobra para o próximo clique."""
        file_dialogs.entregar(self.chave, caminhos)
        try:
            (self._ao_receber or self.widget.click)()
        finally:
            file_dialogs.descartar(self.chave)

    def tem_recentes(self) -> bool:
        return bool(prefs.recentes(self.chave))

    def preencher_menu(self, menu: QMenu) -> None:
        menu.clear()
        lista = prefs.recentes(self.chave)
        if not lista:
            menu.addAction(TEXTO_SEM_RECENTES).setEnabled(False)
        for caminho in lista:
            acao = menu.addAction(os.path.basename(caminho))
            acao.setData(caminho)
            acao.setToolTip(caminho)

    def ligar_menu_de_contexto(self) -> None:
        self.widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.widget.customContextMenuRequested.connect(self._abrir_menu_de_contexto)

    def _abrir_menu_de_contexto(self, posicao) -> None:
        menu = MenuDeRecentes(self, self.widget)
        menu.exec(self.widget.mapToGlobal(posicao))
        menu.deleteLater()

    def _marcar(self, estado: str) -> None:
        estilo.definir_propriedade(self.destaque, "arrasto", estado)

    def eventFilter(self, obj, evento) -> bool:  # noqa: N802 -- nome do Qt
        if obj is not self.widget:
            return False
        tipo = evento.type()
        if tipo == QEvent.Type.DragEnter:
            caminhos = caminhos_do_arrasto(evento.mimeData())
            if not caminhos:
                return False
            self._ok = self.aceita(caminhos)
            self._marcar(ACEITO if self._ok else RECUSADO)
            # Aceito mesmo quando recusado: só assim chega o DragLeave que tira o
            # vermelho. Quem recusa de fato é o DragMove (cursor de proibido).
            evento.accept()
            return True
        if tipo == QEvent.Type.DragMove:
            if self._ok:
                evento.acceptProposedAction()
            else:
                evento.ignore()
            return True
        if tipo == QEvent.Type.DragLeave:
            self._marcar("")
            return False
        if tipo == QEvent.Type.Drop:
            self._marcar("")
            caminhos = caminhos_do_arrasto(evento.mimeData())
            if self._ok and self.aceita(caminhos):
                evento.acceptProposedAction()
                self.receber(caminhos)
            else:
                evento.ignore()
            self._ok = False
            return True
        return False


class MenuDeRecentes(QMenu):
    """O menu "Últimos arquivos" de um `Receptor`: refeito a cada abertura."""

    def __init__(self, receptor: Receptor, pai=None) -> None:
        super().__init__(pai)
        self._receptor = receptor
        self.aboutToShow.connect(self._preencher)
        self.triggered.connect(self._escolheu)

    def _preencher(self) -> None:
        self._receptor.preencher_menu(self)

    def _escolheu(self, acao) -> None:
        caminho = acao.data()
        # O arquivo pode ter sumido entre abrir o menu e clicar: a tela não
        # recebe um caminho morto (na próxima abertura ele já não aparece).
        if caminho and self._receptor.aceita([caminho]):
            self._receptor.receber([caminho])


def botao_de_recentes(receptor: Receptor) -> QToolButton:
    """A setinha "▾" ao lado do botão, com o menu dos últimos arquivos."""
    seta = QToolButton()
    seta.setObjectName("seta_recentes")
    seta.setText(estilo.mono(SETA_RECENTES))
    seta.setToolTip(DICA_RECENTES)
    seta.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    seta.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    seta.setMenu(MenuDeRecentes(receptor, seta))
    return seta


def aceitar_arquivo(widget, chave: str, extensoes, ao_receber=None, *, varios: bool = False,
                    destaque=None, menu_de_contexto: bool = False) -> Receptor:
    receptor = Receptor(widget, chave, extensoes, ao_receber, varios=varios, destaque=destaque)
    if menu_de_contexto:
        receptor.ligar_menu_de_contexto()
    return receptor


def ligar_arrastaveis(tela, arrastaveis) -> dict[str, Receptor]:
    """Liga cada `Arrastavel` da tela ao seu botão (atributo que não existe: erro
    com o nome, que o `show_frame` mostra na tela de erro)."""
    receptores: dict[str, Receptor] = {}
    for item in arrastaveis:
        widget = getattr(tela, item.atributo, None)
        if widget is None:
            raise AttributeError(f"{type(tela).__name__}.ARRASTAVEIS: não há '{item.atributo}' na tela")
        receptores[item.atributo] = aceitar_arquivo(widget, item.chave, item.extensoes,
                                                    varios=item.varios, menu_de_contexto=True)
        dica = widget.toolTip()
        if DICA_ARRASTAR not in dica:
            widget.setToolTip(f"{dica}\n\n{DICA_ARRASTAR}" if dica else DICA_ARRASTAR)
    return receptores
