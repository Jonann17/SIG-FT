"""Seletores de arquivo/pasta da interface Qt — mesma API da interface antiga.

A tela declara `chave`/`categoria` uma vez e nunca mais pensa em memória de
pastas (é o CP 7.2). Rótulo de legenda "Nenhum arquivo selecionado" que vira o
nome em verde (papel `ok`), botão secundário que vira `primario`: as cores são
da folha do tema (2026-10-20).
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget,
)

from sigft.app.idioma import marcar, t
from sigft.app_qt import file_dialogs
from sigft.app_qt import estilo
from sigft.app_qt.widgets import arrastar, blocos

# Os padrões do rótulo vazio; quem passa `texto_vazio` passa já traduzido (2026-10-22).
TEXTO_SEM_ARQUIVO = marcar("Nenhum arquivo selecionado")
TEXTO_SEM_PASTA = marcar("Nenhuma pasta selecionada")

# A fila de fichas (`FileQueueList`): a lista é um `tk.Listbox` cru lá; fonte
# "Segoe UI" 11 (PONTOS -- widget cru do Tk). As cores são as do QListWidget da folha.
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
        # 12 px, a fonte do botão de lá; a cor é a da variante (`_pintar`).
        self.botao.setStyleSheet("QPushButton { font-size: 12px; }")
        self.botao.clicked.connect(self._abrir_dialogo)
        # Elidido: um nome comprido não alarga o formulário (o caminho vai no tooltip).
        self.label_status = blocos.RotuloElidido()
        # 13 px: a fonte padrão do CTkLabel; sem ela o rótulo pegava a do app.
        self.label_status.setStyleSheet("background: transparent; font-size: 13px;")
        linha.addWidget(self.botao)
        linha.addSpacing(15)
        linha.addWidget(self.label_status)
        linha.addSpacing(15)
        linha.addStretch()
        self.limpar()

    def _pintar(self, escolhido: bool) -> None:
        """Vazio: botão `secundario` e rótulo `legenda`. Escolhido: rótulo `ok` e,
        se a linha pinta o botão (`pintar_botao`), botão `primario`."""
        if not escolhido or self._pintar_botao:
            estilo.definir_variante(self.botao, "primario" if escolhido else "secundario")
        estilo.definir_papel(self.label_status, "ok" if escolhido else "legenda")

    @property
    def valor(self):
        return self._valor

    def limpar(self) -> None:
        self._valor = None
        self.label_status.setText(self._texto_vazio)
        self.label_status.setToolTip("")
        self._pintar(False)

    def definir(self, valor, rotulo: str) -> None:
        """`valor` é o caminho (ou a tupla de caminhos): vai inteiro no tooltip."""
        self._valor = valor
        caminhos = "\n".join(valor) if isinstance(valor, (tuple, list)) else str(valor)
        self.label_status.mostrar_caminho(caminhos, rotulo)
        self._pintar(True)

    def _abrir_dialogo(self) -> None:
        raise NotImplementedError

    def _notificar(self) -> None:
        if self._ao_escolher is not None:
            self._ao_escolher(self._valor)

    def _ligar_arrasto(self, chave: str, filetypes, *, varios: bool) -> None:
        """Arrastar arquivo para a linha e a seta dos últimos arquivos, ao lado do
        botão (2026-10-21). A seta só aparece quando há recente: sem recente a
        linha tem as medidas de sempre."""
        self.receptor = arrastar.aceitar_arquivo(self, chave, file_dialogs.extensoes_de(filetypes),
                                                 self._abrir_dialogo, varios=varios, destaque=self.botao,
                                                 alvo=self.botao)
        self.seta_recentes = arrastar.botao_de_recentes(self.receptor)
        self.layout().insertWidget(1, self.seta_recentes)
        self._mostrar_seta()

    def _mostrar_seta(self) -> None:
        self.seta_recentes.setVisible(self.receptor.tem_recentes())


class FilePickerRow(_LinhaSeletora):
    def __init__(self, parent=None, *, chave: str, categoria: str, texto_botao: str,
                 titulo: str | None = None, filetypes=None, texto_vazio: str | None = None,
                 ao_escolher=None, dialog_fn=None, **kwargs) -> None:
        self._chave, self._categoria = chave, categoria
        self._titulo, self._filetypes, self._dialog_fn = titulo, filetypes, dialog_fn
        texto_vazio = texto_vazio if texto_vazio is not None else t(TEXTO_SEM_ARQUIVO)
        super().__init__(parent, texto_botao=texto_botao, texto_vazio=texto_vazio,
                         ao_escolher=ao_escolher, **kwargs)
        self._ligar_arrasto(chave, filetypes, varios=False)

    def _abrir_dialogo(self) -> None:
        caminho = file_dialogs.ask_open_file(self._chave, self._categoria, titulo=self._titulo,
                                             filetypes=self._filetypes, dialog_fn=self._dialog_fn)
        if not caminho:
            return  # cancelar não apaga o que já estava escolhido
        self.definir(caminho, os.path.basename(caminho))
        self._mostrar_seta()
        self._notificar()


class MultiFilePickerRow(_LinhaSeletora):
    def __init__(self, parent=None, *, chave: str, categoria: str, texto_botao: str,
                 titulo: str | None = None, filetypes=None, texto_vazio: str | None = None,
                 ao_escolher=None, dialog_fn=None, **kwargs) -> None:
        self._chave, self._categoria = chave, categoria
        self._titulo, self._filetypes, self._dialog_fn = titulo, filetypes, dialog_fn
        texto_vazio = texto_vazio if texto_vazio is not None else t(TEXTO_SEM_ARQUIVO)
        super().__init__(parent, texto_botao=texto_botao, texto_vazio=texto_vazio,
                         ao_escolher=ao_escolher, **kwargs)
        self._ligar_arrasto(chave, filetypes, varios=True)

    def _abrir_dialogo(self) -> None:
        caminhos = file_dialogs.ask_open_files(self._chave, self._categoria, titulo=self._titulo,
                                               filetypes=self._filetypes, dialog_fn=self._dialog_fn)
        if not caminhos:
            return
        self.definir(tuple(caminhos), t("{n} arquivos selecionados", n=len(caminhos)))
        self._mostrar_seta()
        self._notificar()


class FolderPickerRow(_LinhaSeletora):
    def __init__(self, parent=None, *, chave: str, categoria: str = "pasta", texto_botao: str,
                 titulo: str | None = None, texto_vazio: str | None = None,
                 ao_escolher=None, dialog_fn=None, **kwargs) -> None:
        self._chave, self._categoria = chave, categoria
        self._titulo, self._dialog_fn = titulo, dialog_fn
        texto_vazio = texto_vazio if texto_vazio is not None else t(TEXTO_SEM_PASTA)
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
                 rotulo: str | None = None, titulo_dialogo: str | None = None,
                 filetypes=None, texto_adicionar: str | None = None,
                 prefixo_item: str = PREFIXO_ITEM, ao_mudar=None, dialog_fn=None) -> None:
        # Quem chama traduz o que passa; os padrões são traduzidos aqui (2026-10-22).
        rotulo = rotulo if rotulo is not None else t("Planilhas PMIB Selecionadas")
        texto_adicionar = texto_adicionar if texto_adicionar is not None else t("Adicionar Fichas")
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
        # Cores (fundo, texto, seleção) e a barra de rolagem: as do QListWidget da folha.
        self.listbox.setStyleSheet(
            f"QListWidget {{ border: none; outline: none; {blocos.folha_fonte_tk(FONTE_LISTA, em_pontos=True)} }}"
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
        self.botao_adicionar = blocos.botao(texto_adicionar, largura=estilo.LARGURA_BOTAO_CTK, altura=28,
                                            variante="secundario")
        self.botao_remover = blocos.botao(t("Remover Seleção"), largura=estilo.LARGURA_BOTAO_CTK, altura=28,
                                          variante="perigo")
        self.botao_limpar = blocos.botao(t("Limpar Tudo"), variante="contorno",
                                         largura=estilo.LARGURA_BOTAO_CTK, altura=28)
        for botao in (self.botao_adicionar, self.botao_remover, self.botao_limpar):
            coluna.addWidget(botao)
        coluna.addStretch()
        linha.addLayout(coluna)

        self.botao_adicionar.clicked.connect(self.adicionar)
        self.botao_remover.clicked.connect(self.remover_selecionados)
        self.botao_limpar.clicked.connect(self.limpar)
        # Arrastar várias fichas do Explorer para a fila (2026-10-21).
        self.receptor = arrastar.aceitar_arquivo(self, chave, file_dialogs.extensoes_de(filetypes),
                                                 self.adicionar, varios=True, destaque=self.listbox,
                                                 alvo=self.botao_adicionar)

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
