"""Seletores de arquivo/pasta da interface Qt — mesma API da interface antiga.

A tela declara `chave`/`categoria` uma vez e nunca mais pensa em memória de
pastas (é o CP 7.2). Rótulo cinza "Nenhum arquivo selecionado" que vira o nome
em verde, botão cinza que vira `primary`: o comportamento de hoje.
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget,
)

from sigft.app import theme
from sigft.app_qt import file_dialogs
from sigft.app_qt import estilo
from sigft.app_qt.estilo import cinza_tk
from sigft.app_qt.widgets import blocos

COR_BOTAO_SELECAO = "#3A3A3A"
COR_BOTAO_SELECAO_HOVER = "#454545"
TEXTO_SEM_ARQUIVO = "Nenhum arquivo selecionado"
TEXTO_SEM_PASTA = "Nenhuma pasta selecionada"

# A fila de fichas (`FileQueueList`): a lista é um `tk.Listbox` cru lá, com as
# cores escritas à mão; fonte "Segoe UI" 11 (PONTOS -- widget cru do Tk).
COR_FUNDO_LISTA = "#1E1E1E"
FONTE_LISTA = ("Segoe UI", 11)
# O emoji e os DOIS espaços são literais do app antigo.
PREFIXO_ITEM = " 📊  "


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
        # Lá o rótulo vai com `pack(side="left", padx=15)`: 15 px dos DOIS lados
        # e nada mais -- sem o espaçamento automático do layout. O de depois
        # conta quando a linha vai centrada (largura natural igual à de lá).
        linha.setSpacing(0)
        self.botao = QPushButton(texto_botao)
        blocos.sem_tecla(self.botao)   # como o CTkButton: nunca pega o foco
        self.botao.setFixedWidth(largura_botao)
        self.botao.clicked.connect(self._abrir_dialogo)
        # Elidido: um nome comprido não alarga o formulário (o caminho vai no tooltip).
        self.label_status = blocos.RotuloElidido()
        linha.addWidget(self.botao)
        linha.addSpacing(15)
        linha.addWidget(self.label_status)
        linha.addSpacing(15)
        linha.addStretch()
        self.limpar()

    def _pintar(self, cor: str, cor_texto: str) -> None:
        if self._pintar_botao or cor == COR_BOTAO_SELECAO:
            hover = COR_BOTAO_SELECAO_HOVER if cor == COR_BOTAO_SELECAO else theme.COLORS["primary_hover"]
            self.botao.setStyleSheet(
                f"QPushButton {{ background: {cor}; font-size: 12px; }}"
                f" QPushButton:hover {{ background: {hover}; }}")
        # 13 px: a fonte padrão do CTkLabel; sem ela o rótulo pegava a do app.
        self.label_status.setStyleSheet(
            f"color: {cor_texto}; background: transparent; font-size: 13px;")

    @property
    def valor(self):
        return self._valor

    def limpar(self) -> None:
        self._valor = None
        self.label_status.setText(self._texto_vazio)
        self.label_status.setToolTip("")
        self._pintar(COR_BOTAO_SELECAO, cinza_tk(theme.COR_TEXTO_APOIO))

    def definir(self, valor, rotulo: str) -> None:
        """`valor` é o caminho (ou a tupla de caminhos): vai inteiro no tooltip."""
        self._valor = valor
        caminhos = "\n".join(valor) if isinstance(valor, (tuple, list)) else str(valor)
        self.label_status.mostrar_caminho(caminhos, rotulo)
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


class FileQueueList(QWidget):
    """A lista de fichas com Adicionar / Remover Seleção / Limpar Tudo.

    Mesma API da interface antiga: `arquivos` (cópia), `adicionar()`,
    `remover_selecionados()`, `limpar()`, `definir(caminhos)`, e
    `ao_mudar(acao, quantidade, total)` com acao "adicionou"/"removeu"/"limpou".

    `label_contador` ("Planilhas PMIB Selecionadas (N)") NÃO entra neste widget:
    lá ele nasce no `master` e a tela o empacota onde quer -- aqui a tela faz
    `layout.addWidget(fila.label_contador)` antes de pôr a fila.
    """

    def __init__(self, parent=None, *, chave: str, categoria: str = "excel",
                 rotulo: str = "Planilhas PMIB Selecionadas", titulo_dialogo: str | None = None,
                 filetypes=None, texto_adicionar: str = "Adicionar Fichas",
                 prefixo_item: str = PREFIXO_ITEM, ao_mudar=None, dialog_fn=None) -> None:
        super().__init__(parent)
        self._chave, self._categoria = chave, categoria
        self._rotulo, self._titulo_dialogo, self._filetypes = rotulo, titulo_dialogo, filetypes
        self._prefixo_item = prefixo_item
        self._ao_mudar, self._dialog_fn = ao_mudar, dialog_fn
        self._arquivos: list[str] = []

        # CTkLabel ("Roboto", 12, "bold"): pixels; altura mínima de CTkLabel.
        self.label_contador = QLabel(f"{rotulo} (0)")
        self.label_contador.setMinimumHeight(blocos.ALTURA_MINIMA_ROTULO)
        self.label_contador.setStyleSheet("font-size: 12px; font-weight: bold; background: transparent;")

        linha = QHBoxLayout(self)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(0)

        self.listbox = QListWidget()
        self.listbox.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        # A tk.Scrollbar fica sempre à vista, ao lado da lista.
        self.listbox.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.listbox.setFont(blocos.fonte_tk(FONTE_LISTA, em_pontos=True))
        # A barra de rolagem fica a escura do app: lá a tela pedia uma tk.Scrollbar
        # escura (bg=COR_CARTAO, troughcolor=#3A3A3A) -- o Windows ignora essas
        # cores e a desenha clara, mas a intenção escrita era a escura.
        self.listbox.setStyleSheet(
            f"QListWidget {{ background: {COR_FUNDO_LISTA}; color: {theme.COLORS['text_light']};"
            f" border: none; outline: none; {blocos.folha_fonte_tk(FONTE_LISTA, em_pontos=True)} }}"
            f" QListWidget::item:selected {{ background: {theme.COLORS['primary']}; color: white; }}"
            f" QListWidget::item {{ padding: {estilo.FOLGA_LINHA_LISTA_TK}px 0; }}"
            " QListWidget::item:hover:!selected { background: transparent; }")
        # pack(side="left", padx=(5, 0), pady=5) da lista e da barra.
        caixa_lista = QVBoxLayout()
        caixa_lista.setContentsMargins(5, 5, 0, 5)
        caixa_lista.addWidget(self.listbox)
        linha.addLayout(caixa_lista, 1)
        linha.addSpacing(10)  # a coluna de botões: pack(side="right", padx=(10, 0))

        coluna = QVBoxLayout()
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(10)  # pady=5 de cada botão: 5 + 5 entre dois
        coluna.addSpacing(5)
        # fg_color sem hover_color lá: o hover é o do tema (padrão de `cor_hover`).
        self.botao_adicionar = blocos.botao(texto_adicionar, largura=estilo.LARGURA_BOTAO_CTK, altura=28,
                                            cor_fundo=COR_BOTAO_SELECAO)
        self.botao_remover = blocos.botao("Remover Seleção", largura=estilo.LARGURA_BOTAO_CTK, altura=28,
                                          cor_fundo=theme.COLORS["danger"])
        self.botao_limpar = blocos.botao("Limpar Tudo", variante="contorno",
                                         largura=estilo.LARGURA_BOTAO_CTK, altura=28,
                                         cor_texto=estilo.TEXTO_BOTAO_CTK)
        for botao in (self.botao_adicionar, self.botao_remover, self.botao_limpar):
            coluna.addWidget(botao)
        coluna.addStretch()
        linha.addLayout(coluna)

        self.botao_adicionar.clicked.connect(self.adicionar)
        self.botao_remover.clicked.connect(self.remover_selecionados)
        self.botao_limpar.clicked.connect(self.limpar)

    # -- API pública ---------------------------------------------------------
    @property
    def arquivos(self) -> list[str]:
        return list(self._arquivos)

    def adicionar(self) -> None:
        escolhidos = file_dialogs.ask_open_files(self._chave, self._categoria, titulo=self._titulo_dialogo,
                                                 filetypes=self._filetypes, dialog_fn=self._dialog_fn)
        if not escolhidos:
            return
        for caminho in escolhidos:
            if caminho not in self._arquivos:  # o mesmo arquivo duas vezes rodaria duas vezes
                self._arquivos.append(caminho)
        self._redesenhar()
        self._notificar("adicionou", len(escolhidos))

    def remover_selecionados(self) -> None:
        selecionados = sorted((self.listbox.row(i) for i in self.listbox.selectedItems()), reverse=True)
        if not selecionados:
            return
        for indice in selecionados:  # de trás para frente: os índices não andam
            del self._arquivos[indice]
        self._redesenhar()
        self._notificar("removeu", len(selecionados))

    def limpar(self) -> None:
        self._arquivos.clear()
        self._redesenhar()
        self._notificar("limpou", 0)

    def definir(self, caminhos) -> None:
        """Substitui a fila inteira (restaurar estado); não avisa."""
        self._arquivos = list(caminhos)
        self._redesenhar()

    # -- interno -------------------------------------------------------------
    def _notificar(self, acao: str, quantidade: int) -> None:
        if self._ao_mudar is not None:
            self._ao_mudar(acao, quantidade, len(self._arquivos))

    def _redesenhar(self) -> None:
        self.listbox.clear()
        self.listbox.addItems([estilo.mono(f"{self._prefixo_item}{os.path.basename(c)}")
                               for c in self._arquivos])
        self.label_contador.setText(f"{self._rotulo} ({len(self._arquivos)})")
