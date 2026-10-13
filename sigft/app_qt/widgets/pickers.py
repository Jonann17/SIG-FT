"""Seletores de arquivo/pasta da interface Qt — mesma API dos CustomTkinter.

A tela declara `chave`/`categoria` uma vez e nunca mais pensa em memória de
pastas (é o CP 7.2). Rótulo cinza "Nenhum arquivo selecionado" que vira o nome
em verde, botão cinza que vira `primary`: o comportamento de hoje.
"""
from __future__ import annotations

import os

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from sigft.app import theme
from sigft.app_qt import file_dialogs
from sigft.app_qt.estilo import cinza_tk

COR_BOTAO_SELECAO = "#3A3A3A"
COR_BOTAO_SELECAO_HOVER = "#454545"
TEXTO_SEM_ARQUIVO = "Nenhum arquivo selecionado"
TEXTO_SEM_PASTA = "Nenhuma pasta selecionada"


class _LinhaSeletora(QWidget):
    def __init__(self, parent=None, *, texto_botao: str, texto_vazio: str,
                 largura_botao: int = 240, pintar_botao: bool = True, ao_escolher=None) -> None:
        super().__init__(parent)
        self._texto_vazio = texto_vazio
        self._pintar_botao = pintar_botao
        self._ao_escolher = ao_escolher
        self._valor = None
        linha = QHBoxLayout(self)
        linha.setContentsMargins(0, 0, 0, 0)
        self.botao = QPushButton(texto_botao)
        self.botao.setFixedWidth(largura_botao)
        self.botao.clicked.connect(self._abrir_dialogo)
        self.label_status = QLabel()
        linha.addWidget(self.botao)
        linha.addSpacing(15)
        linha.addWidget(self.label_status)
        linha.addStretch()
        self.limpar()

    def _pintar(self, cor: str, cor_texto: str) -> None:
        if self._pintar_botao or cor == COR_BOTAO_SELECAO:
            hover = COR_BOTAO_SELECAO_HOVER if cor == COR_BOTAO_SELECAO else theme.COLORS["primary_hover"]
            self.botao.setStyleSheet(
                f"QPushButton {{ background: {cor}; font-size: 12px; }}"
                f" QPushButton:hover {{ background: {hover}; }}")
        self.label_status.setStyleSheet(f"color: {cor_texto}; background: transparent;")

    @property
    def valor(self):
        return self._valor

    def limpar(self) -> None:
        self._valor = None
        self.label_status.setText(self._texto_vazio)
        self._pintar(COR_BOTAO_SELECAO, cinza_tk(theme.COR_TEXTO_APOIO))

    def definir(self, valor, rotulo: str) -> None:
        self._valor = valor
        self.label_status.setText(rotulo)
        self._pintar(theme.COLORS["primary"], theme.COLORS["accent"])

    def _abrir_dialogo(self) -> None:
        raise NotImplementedError

    def _notificar(self) -> None:
        if self._ao_escolher is not None:
            self._ao_escolher(self._valor)


class FilePickerRow(_LinhaSeletora):
    def __init__(self, parent=None, *, chave: str, categoria: str, texto_botao: str,
                 titulo: str | None = None, filetypes=None, texto_vazio: str = TEXTO_SEM_ARQUIVO,
                 ao_escolher=None, dialog_fn=None, **kwargs) -> None:
        self._chave, self._categoria = chave, categoria
        self._titulo, self._filetypes, self._dialog_fn = titulo, filetypes, dialog_fn
        super().__init__(parent, texto_botao=texto_botao, texto_vazio=texto_vazio,
                         ao_escolher=ao_escolher, **kwargs)

    def _abrir_dialogo(self) -> None:
        caminho = file_dialogs.ask_open_file(self._chave, self._categoria, titulo=self._titulo,
                                             filetypes=self._filetypes, dialog_fn=self._dialog_fn)
        if not caminho:
            return  # cancelar não apaga o que já estava escolhido
        self.definir(caminho, os.path.basename(caminho))
        self._notificar()


class MultiFilePickerRow(_LinhaSeletora):
    def __init__(self, parent=None, *, chave: str, categoria: str, texto_botao: str,
                 titulo: str | None = None, filetypes=None, texto_vazio: str = TEXTO_SEM_ARQUIVO,
                 ao_escolher=None, dialog_fn=None, **kwargs) -> None:
        self._chave, self._categoria = chave, categoria
        self._titulo, self._filetypes, self._dialog_fn = titulo, filetypes, dialog_fn
        super().__init__(parent, texto_botao=texto_botao, texto_vazio=texto_vazio,
                         ao_escolher=ao_escolher, **kwargs)

    def _abrir_dialogo(self) -> None:
        caminhos = file_dialogs.ask_open_files(self._chave, self._categoria, titulo=self._titulo,
                                               filetypes=self._filetypes, dialog_fn=self._dialog_fn)
        if not caminhos:
            return
        self.definir(tuple(caminhos), f"{len(caminhos)} arquivos selecionados")
        self._notificar()


class FolderPickerRow(_LinhaSeletora):
    def __init__(self, parent=None, *, chave: str, categoria: str = "pasta", texto_botao: str,
                 titulo: str | None = None, texto_vazio: str = TEXTO_SEM_PASTA,
                 ao_escolher=None, dialog_fn=None, **kwargs) -> None:
        self._chave, self._categoria = chave, categoria
        self._titulo, self._dialog_fn = titulo, dialog_fn
        super().__init__(parent, texto_botao=texto_botao, texto_vazio=texto_vazio,
                         ao_escolher=ao_escolher, **kwargs)

    def _abrir_dialogo(self) -> None:
        pasta = file_dialogs.ask_directory(self._chave, self._categoria, titulo=self._titulo,
                                           dialog_fn=self._dialog_fn)
        if not pasta:
            return
        self.definir(pasta, os.path.basename(pasta) or pasta)
        self._notificar()
