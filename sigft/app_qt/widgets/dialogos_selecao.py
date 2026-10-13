"""Seleção de itens e arquivos travados -- os diálogos de `sigft/app/widgets/dialogs.py`
que faltavam na interface Qt (E3.1).

Num módulo à parte de `dialogs.py` porque a frente da Aplicação LMR mexe lá ao
mesmo tempo, e para o `dialogs.py` não dobrar de tamanho.

Mesma API e mesmo contrato dos CustomTkinter:

* `SelecaoMultiplaDialog` / `TabelaSelecaoDialog` abrem ao serem construídos
  (como o CTkToplevel) e devolvem a escolha por `ao_confirmar`; fechar no "X"
  (ou Esc, ou Cancelar) não chama ninguém. O `wait_window(dialogo)` das telas
  CTk vira `dialogo.esperar()`, que também devolve a escolha (None se fechou).
  Só da thread da interface -- quem os abre é um clique.
* `ArquivosTravadosDialog` é janela de ESPERA (o worker está parado num
  `threading.Event`): "X" e Esc equivalem a Seguir e soltam o worker. Quem a
  abre é `DialogosDeEspera.perguntar_arquivos_travados`, de qualquer thread.

Modal só onde o CTk chamava `grab_set()` (`modal=True`): a tabela por padrão, a
lista quando a tela pede. Ver a nota longa no `SelecaoMultiplaDialog` do CTk.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QEventLoop, QObject, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QListWidget, QMessageBox,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from sigft.app import theme
from sigft.app.textos_dialogos import TEXTOS_TRAVADOS
from sigft.app_qt import estilo
from sigft.app_qt.widgets import blocos

# Diálogo aberto sem pai (ou cujo pai some) precisa de uma referência viva
# enquanto está na tela; sai daqui quando fecha.
_ABERTOS: set = set()



def _folha_de_fundo(cor: str) -> str:
    """Botão com `fg_color` e sem `hover_color` no CTk: o fundo pedido e o hover do tema."""
    return (f"QPushButton {{ background: {cor}; }}"
            f" QPushButton:hover {{ background: {estilo.AZUL_CTK_HOVER}; }}")


def _geometria(texto: str) -> tuple[int, int]:
    """"900x600" do Tk em (900, 600)."""
    largura, altura = texto.lower().split("+")[0].split("x")
    return int(largura), int(altura)


def _botao(texto: str, *, largura: int | None = None, variante: str | None = None,
           cor: str | None = None):
    b = blocos.botao(texto, variante=variante, largura=largura, altura=28)
    if cor:
        b.setStyleSheet(b.styleSheet() + " " + _folha_de_fundo(cor))
    # Enter não confirma sozinho: o Tk não ligava tecla nenhuma nestas janelas.
    b.setAutoDefault(False)
    b.setDefault(False)
    return b


def _linha_de_botoes(*botoes, padx: int = 10) -> QHBoxLayout:
    """`pack(side="left", padx=10)` de cada botão, a fileira centrada."""
    linha = QHBoxLayout()
    linha.setContentsMargins(0, 0, 0, 0)
    linha.setSpacing(2 * padx)
    linha.addStretch()
    for b in botoes:
        linha.addWidget(b)
    linha.addStretch()
    return linha


class _JanelaQueAbre(QDialog):
    """Base: título, tamanho, sempre por cima, modal se pedido, e abre já."""

    def __init__(self, parent, *, titulo: str, geometria: str, modal: bool) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.resize(*_geometria(geometria))
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        if modal:
            self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._escolha = None
        _ABERTOS.add(self)
        self.finished.connect(lambda _r: _ABERTOS.discard(self))

    def _abrir(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def esperar(self):
        """O `wait_window` do CTk: volta quando a janela fecha, sem parar o laço
        de eventos. Devolve o que foi confirmado, ou None."""
        if self.isVisible():
            laco = QEventLoop()
            self.finished.connect(laco.quit)
            laco.exec()
        return self._escolha

    def _confirmar_com(self, escolha, ao_confirmar) -> None:
        self._escolha = escolha
        if ao_confirmar is not None:
            ao_confirmar(escolha)
        self.accept()


class SelecaoMultiplaDialog(_JanelaQueAbre):
    """Lista simples para escolher vários textos (o `tk.Listbox` do CTk).

    Devolve os TEXTOS marcados, ou as POSIÇÕES com `devolver_indices=True`.
    `estilo_lista` são as opções do `tk.Listbox` que as telas passavam (bg, fg,
    selectbackground, selectforeground, borderwidth); sem ele, a lista crua do
    Tk: branca de texto preto (folha global, `claro`). `fonte_lista` é de
    widget cru do Tk (PONTOS); `fonte_instrucao`, de CTkLabel (pixels).
    """

    def __init__(self, parent=None, *, itens, titulo: str = "Seleção",
                 instrucao: str = "Selecione um ou mais itens:", geometria: str = "500x500",
                 texto_confirmar: str = "Confirmar Seleção", modal: bool = False,
                 com_selecionar_todos: bool = False, devolver_indices: bool = False,
                 estilo_lista: dict | None = None, fonte_lista: tuple | None = None,
                 fonte_instrucao: tuple | None = None, ao_confirmar=None) -> None:
        super().__init__(parent, titulo=titulo, geometria=geometria, modal=modal)
        self._ao_confirmar = ao_confirmar
        self._devolver_indices = devolver_indices

        layout = QVBoxLayout(self)
        # Tk: rótulo pady=10, quadro pady=10 (5 com estilo), botões pady=15 -- e
        # o pady de dois vizinhos SOMA.
        pady_quadro = 5 if estilo_lista else 10
        layout.setContentsMargins(0, 10, 0, 15)
        layout.setSpacing(0)

        self.rotulo = QLabel(instrucao)
        self.rotulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rotulo.setMinimumHeight(blocos.ALTURA_MINIMA_ROTULO)
        self.rotulo.setFont(blocos.fonte_tk(fonte_instrucao or theme.FONTE_SUBTITULO))
        self.rotulo.setStyleSheet("background: transparent;")
        layout.addWidget(self.rotulo)
        layout.addSpacing(10 + pady_quadro)

        self.listbox = QListWidget()
        # selectmode="multiple": cada clique marca/desmarca, sem Ctrl.
        self.listbox.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.listbox.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        fonte = fonte_lista or theme.FONTE_CONSOLE
        self.listbox.setFont(blocos.fonte_tk(fonte, em_pontos=True))
        if estilo_lista:
            folha = _folha_da_listbox(estilo_lista)
        else:
            # A Listbox crua: branca, e com a barra de rolagem clara do sistema.
            self.listbox.setProperty("claro", True)
            self.listbox.setProperty("barra_nativa", True)
            folha = ""
        self.listbox.setStyleSheet(
            f"QListWidget {{ {blocos.folha_fonte_tk(fonte, em_pontos=True)} outline: none; }} {folha}"
            f" QListWidget::item {{ padding: {estilo.FOLGA_LINHA_LISTA_TK}px 0; }}"
            " QListWidget::item:hover:!selected { background: transparent; }")
        self.listbox.addItems([str(item) for item in itens])
        quadro = QHBoxLayout()
        quadro.setContentsMargins(20, 0, 20, 0)
        quadro.addWidget(self.listbox)
        layout.addLayout(quadro, 1)
        layout.addSpacing(pady_quadro + 15)

        self.botao_todos = None
        botoes = []
        if com_selecionar_todos:
            self.botao_todos = _botao("Selecionar Todos", largura=150, cor="#3A3A3A")
            self.botao_todos.clicked.connect(self.selecionar_todos)
            botoes.append(self.botao_todos)
        self.botao_confirmar = _botao(texto_confirmar, largura=150, variante="primario")
        self.botao_confirmar.clicked.connect(self.confirmar)
        botoes.append(self.botao_confirmar)
        layout.addLayout(_linha_de_botoes(*botoes))
        self._abrir()

    @property
    def selecionados(self) -> list[str]:
        return [self.listbox.item(i).text() for i in self.indices]

    @property
    def indices(self) -> list[int]:
        return sorted(self.listbox.row(item) for item in self.listbox.selectedItems())

    def selecionar_todos(self) -> None:
        self.listbox.selectAll()

    def confirmar(self) -> None:
        escolha = self.indices if self._devolver_indices else self.selecionados
        self._confirmar_com(escolha, self._ao_confirmar)


def _folha_da_listbox(opcoes: dict) -> str:
    """As opções do `tk.Listbox` em folha de estilo do QListWidget."""
    fundo = estilo.cinza_tk(opcoes.get("bg", "#FFFFFF"))
    texto = estilo.cinza_tk(opcoes.get("fg", "#000000"))
    selecao = estilo.cinza_tk(opcoes.get("selectbackground", "#0078D7"))
    texto_selecao = estilo.cinza_tk(opcoes.get("selectforeground", "white"))
    borda = int(opcoes.get("borderwidth", 1))
    linha = f"border: {borda}px solid #A0A0A0;" if borda else "border: none;"
    return (f"QListWidget {{ background: {fundo}; color: {texto}; {linha} }}"
            f" QListWidget::item:selected {{ background: {selecao}; color: {texto_selecao}; }}")


class TabelaSelecaoDialog(_JanelaQueAbre):
    """Tabela (o `ttk.Treeview` do CTk) para escolher várias linhas.

    `linhas` são pares `(chave, valores)`; volta a CHAVE (em texto, como o iid
    do Treeview) -- nunca a posição visual. `larguras` como no CTk:
    `{"coluna": {"width": 150, "anchor": "center"}}` (120 sem largura).
    """

    def __init__(self, parent=None, *, colunas, linhas, titulo: str = "Seleção de Itens",
                 instrucao: str = "Selecione as linhas para processar:", geometria: str = "900x600",
                 larguras: dict | None = None, preselecionar_tudo: bool = False,
                 texto_confirmar: str = "Confirmar Seleção", com_cancelar: bool = True,
                 modal: bool = True, ao_confirmar=None) -> None:
        super().__init__(parent, titulo=titulo, geometria=geometria, modal=modal)
        self._ao_confirmar = ao_confirmar
        colunas = list(colunas)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)  # rótulo pady=10 ... botões pady=10
        layout.setSpacing(0)
        self.rotulo = QLabel(instrucao)
        self.rotulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rotulo.setMinimumHeight(blocos.ALTURA_MINIMA_ROTULO)
        self.rotulo.setFont(blocos.fonte_tk(theme.FONTE_SECAO))
        self.rotulo.setStyleSheet("background: transparent;")
        layout.addWidget(self.rotulo)
        layout.addSpacing(20)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(len(colunas))
        self.tree.setHeaderLabels([str(c) for c in colunas])
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setProperty("barra_nativa", True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        # ttk.Scrollbar empacotada: sempre à vista.
        self.tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        cabecalho = self.tree.header()
        cabecalho.setStretchLastSection(False)
        cabecalho.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        cabecalho.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)  # heading do ttk: centrado
        larguras = larguras or {}
        self._larguras_base = []
        alinhamentos = []
        for i, coluna in enumerate(colunas):
            conf = larguras.get(coluna, {})
            largura = int(conf.get("width", 120))
            self._larguras_base.append(largura)
            self.tree.setColumnWidth(i, largura)
            alinhamentos.append(Qt.AlignmentFlag.AlignCenter if conf.get("anchor") == "center"
                                else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for chave, valores in linhas:
            item = QTreeWidgetItem([str(v) for v in valores])
            item.setData(0, Qt.ItemDataRole.UserRole, str(chave))
            for i, alinhamento in enumerate(alinhamentos):
                item.setTextAlignment(i, alinhamento)
            self.tree.addTopLevelItem(item)
            if preselecionar_tudo:
                item.setSelected(True)
        self._esticar = _EsticaColunas(self.tree, self._larguras_base)

        quadro = QHBoxLayout()
        quadro.setContentsMargins(10, 0, 10, 0)  # padx=10, pady=10
        quadro.addWidget(self.tree)
        layout.addLayout(quadro, 1)
        layout.addSpacing(20)

        self.botao_confirmar = _botao(texto_confirmar, variante="primario", largura=140)
        self.botao_confirmar.clicked.connect(self.confirmar)
        botoes = [self.botao_confirmar]
        self.botao_cancelar = None
        if com_cancelar:
            self.botao_cancelar = _botao("Cancelar", largura=140, cor="#3A3A3A")
            self.botao_cancelar.clicked.connect(self.reject)
            botoes.append(self.botao_cancelar)
        layout.addLayout(_linha_de_botoes(*botoes))
        self._abrir()

    @classmethod
    def de_dataframe(cls, master, dataframe, **kwargs):
        """A chave de cada linha é o ÍNDICE do DataFrame, não a posição."""
        linhas = [(indice, linha.to_numpy().tolist()) for indice, linha in dataframe.iterrows()]
        return cls(master, colunas=list(dataframe.columns), linhas=linhas, **kwargs)

    @property
    def selecionados(self) -> list[str]:
        """As chaves marcadas, na ordem da tabela."""
        return [self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)
                for i in range(self.tree.topLevelItemCount()) if self.tree.topLevelItem(i).isSelected()]

    def confirmar(self) -> None:
        selecionados = self.selecionados
        if not selecionados:
            # Confirmar sem nada seria um cancelamento silencioso.
            QMessageBox.warning(self, "Aviso", "Selecione ao menos um item.")
            return
        self._confirmar_com(selecionados, self._ao_confirmar)


class _EsticaColunas(QObject):
    """O ttk.Treeview estica as colunas (`stretch=True`, o padrão) para ocupar a
    largura: a sobra é repartida IGUALMENTE entre elas. Encolher abaixo das
    larguras pedidas, não -- aí aparece a rolagem horizontal."""

    def __init__(self, tree: QTreeWidget, base: list[int]) -> None:
        super().__init__(tree)
        self._tree, self._base = tree, base
        tree.viewport().installEventFilter(self)

    def eventFilter(self, objeto, evento) -> bool:  # noqa: N802 -- nome do Qt
        if evento.type() == QEvent.Type.Resize and self._base:
            sobra = self._tree.viewport().width() - sum(self._base)
            extra = max(0, sobra) // len(self._base)
            resto = max(0, sobra) - extra * len(self._base)
            for i, largura in enumerate(self._base):
                self._tree.setColumnWidth(i, largura + extra + (resto if i == len(self._base) - 1 else 0))
        return False


class ArquivosTravadosDialog(QDialog):
    """Arquivos que não puderam ser gravados, cada um com o motivo e o que fazer;
    Repetir x Seguir. A decisão volta em `resultado["repetir"]`.

    `itens`: `(nome, motivo, o_que_fazer)`; `momento`: "antes", "depois" ou
    "na_hora" (`TEXTOS_TRAVADOS`). Sem modal: a pessoa vai ao Excel fechar os
    arquivos com a janela aberta. "X" e Esc = Seguir.
    """

    def __init__(self, parent=None, *, itens, momento, evento_espera, resultado: dict) -> None:
        super().__init__(parent)
        textos = TEXTOS_TRAVADOS[momento]
        self.itens = [tuple(item) for item in itens]
        self._evento = evento_espera
        self._resultado = resultado
        self._decidido = False
        self.setWindowTitle(textos["titulo"])
        self.resize(620, 380)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        layout = QVBoxLayout(self)
        # pady do Tk somados: (16, 6) | 4 | (6, 4) | (4, 16).
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(0)
        self.rotulo_explicacao = blocos.rotulo(textos["explicacao"], tamanho=13, alinhar="esquerda")
        layout.addWidget(self.rotulo_explicacao)
        layout.addSpacing(6 + 4)

        area, lista = blocos.area_rolavel(cor=theme.COR_CARTAO)
        self.area = area
        for nome, motivo, o_que_fazer in self.itens:
            lista.addSpacing(8)
            r_nome = blocos.rotulo(nome, tamanho=14, negrito=True, alinhar="esquerda")
            r_motivo = blocos.rotulo(f"Motivo: {motivo}. {o_que_fazer}", tamanho=12,
                                     cor=estilo.cinza_tk(theme.COR_TEXTO_APOIO_CLARO), alinhar="esquerda")
            for r in (r_nome, r_motivo):
                r.setContentsMargins(10, 0, 10, 0)
                lista.addWidget(r)
            lista.addSpacing(6)
        layout.addWidget(area, 1)
        layout.addSpacing(4 + 6)

        self.rotulo_rodape = blocos.rotulo(textos["rodape"], tamanho=12,
                                           cor=estilo.cinza_tk(theme.COR_TEXTO_APOIO), alinhar="esquerda")
        layout.addWidget(self.rotulo_rodape)
        layout.addSpacing(4 + 4)

        self.botao_repetir = blocos.botao(textos["repetir"], variante="primario", largura=170, altura=40,
                                          tamanho_fonte=14, negrito=True)
        self.botao_seguir = blocos.botao(textos["seguir"], variante="contorno", largura=170, altura=40)
        for b in (self.botao_repetir, self.botao_seguir):
            b.setAutoDefault(False)
        self.botao_repetir.clicked.connect(self.repetir)
        self.botao_seguir.clicked.connect(self.seguir)
        layout.addLayout(_linha_de_botoes(self.botao_repetir, self.botao_seguir))

    def _responder(self, repetir: bool) -> None:
        self._decidido = True
        self._resultado["repetir"] = repetir
        self._evento.set()

    def repetir(self) -> None:
        self._responder(True)
        self.accept()

    def seguir(self) -> None:
        self._responder(False)
        self.reject()

    def reject(self) -> None:
        """Esc chega aqui sem passar pelo `closeEvent`: também solta o worker."""
        if not self._decidido:
            self._responder(False)
        super().reject()

    def closeEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        if not self._decidido:
            self._responder(False)
        super().closeEvent(evento)
