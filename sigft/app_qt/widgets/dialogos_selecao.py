"""Seleção de itens e arquivos travados -- os diálogos de `sigft/app/widgets/dialogs.py`
que faltavam na interface Qt (E3.1).

Num módulo à parte de `dialogs.py` porque a frente da Aplicação LMR mexe lá ao
mesmo tempo, e para o `dialogs.py` não dobrar de tamanho.

Mesma API e mesmo contrato da interface antiga:

* `SelecaoMultiplaDialog` / `TabelaSelecaoDialog` abrem ao serem construídos
  (como o CTkToplevel) e devolvem a escolha por `ao_confirmar`; fechar no "X"
  (ou Cancelar) não chama ninguém; Esc não fecha. O `wait_window(dialogo)` das telas
  interface antiga vira `dialogo.esperar()`, que também devolve a escolha (None se fechou).
  Só da thread da interface -- quem os abre é um clique.
* `ArquivosTravadosDialog` é janela de ESPERA (o worker está parado num
  `threading.Event`): "X" e Esc equivalem a Seguir e soltam o worker. Quem a
  abre é `DialogosDeEspera.perguntar_arquivos_travados`, de qualquer thread.

Modal só onde a interface antiga chamava `grab_set()` (`modal=True`): a tabela por padrão, a
lista quando a tela pede. Ver a nota longa no `SelecaoMultiplaDialog` da interface antiga.
"""
from __future__ import annotations

import functools

from PySide6.QtCore import QEvent, QEventLoop, QObject, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QListWidget, QMessageBox,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from sigft.app import theme
from sigft.app.idioma import t
from sigft.app.textos_dialogos import TEXTOS_TRAVADOS
from sigft.app_qt import estilo
from sigft.app_qt.widgets import blocos
from sigft.app_qt.widgets.colunas import instalar_colunas
from sigft.app_qt.widgets.dialogs import IgnoraEsc, SoltaAoFechar, sem_tecla
from sigft.app_qt import propriedades

# Diálogo aberto sem pai (ou cujo pai some) precisa de uma referência viva
# enquanto está na tela; sai daqui quando fecha. Chave = id(): a conexão que o
# tira daqui não pode guardar o próprio diálogo (seria um ciclo que o prende).
_ABERTOS: dict = {}


def _esquecer(chave: int, *_sinal) -> None:
    _ABERTOS.pop(chave, None)



def _botao(texto: str, *, largura: int | None = None, variante: str | None = None):
    b = blocos.botao(texto, variante=variante, largura=largura, altura=28)
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


class JanelaQueAbre(IgnoraEsc, QDialog):
    """Base de um CTkToplevel: título, tamanho, modal se pedido (`grab_set`),
    sempre por cima (`-topmost`, padrão aqui) e abre já (`_abrir()` no fim do
    __init__ da subclasse). `esperar()` é o `wait_window`. Também a base das
    janelas de `views/janelas.py`.

    Esc não fecha (`IgnoraEsc`, revisão final): o Tk não tinha tecla nenhuma, e
    numa seleção feita item a item uma tecla escapada jogava a escolha fora.
    O "X" (e o Cancelar) continuam cancelando."""

    def __init__(self, parent, *, titulo: str, geometria: str, modal: bool,
                 sempre_por_cima: bool = True) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.resize(*blocos.geometria_tk(geometria))
        if sempre_por_cima:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        if modal:
            self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._escolha = None
        self._laco: QEventLoop | None = None
        _ABERTOS[id(self)] = self
        self.finished.connect(functools.partial(_esquecer, id(self)))

    def _abrir(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def esperar(self):
        """O `wait_window` da interface antiga: volta quando a janela fecha, sem parar o laço
        de eventos. Devolve o que foi confirmado, ou None."""
        if self.isVisible():
            self._laco = QEventLoop()
            self.finished.connect(self._laco.quit)
            self._laco.exec()
            self._laco = None
        return self._escolha

    def hideEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        # Escondida por fora (hide(), o pai fechando) sem passar por done():
        # o `esperar()` também tem de voltar.
        # Minimizar (evento espontâneo do sistema) não é fechar.
        if self._laco is not None and not evento.spontaneous():
            self._laco.quit()
        super().hideEvent(evento)

    def _confirmar_com(self, escolha, ao_confirmar) -> None:
        self._escolha = escolha
        if ao_confirmar is not None:
            ao_confirmar(escolha)
        self.accept()


class SelecaoMultiplaDialog(JanelaQueAbre):
    """Lista simples para escolher vários textos (o `tk.Listbox` da interface antiga).

    Devolve os TEXTOS marcados, ou as POSIÇÕES com `devolver_indices=True`.
    `estilo_lista` são as opções do `tk.Listbox` que as telas passavam; desde
    2026-10-20 só o `borderwidth` vale (as cores são as da folha). Sem ele, a
    lista crua do Tk (folha global, `claro`). `fonte_lista` é de
    widget cru do Tk (PONTOS); `fonte_instrucao`, de CTkLabel (pixels).
    """

    def __init__(self, parent=None, *, itens, titulo: str | None = None,
                 instrucao: str | None = None, geometria: str = "500x500",
                 texto_confirmar: str | None = None, modal: bool = False,
                 com_selecionar_todos: bool = False, devolver_indices: bool = False,
                 estilo_lista: dict | None = None, fonte_lista: tuple | None = None,
                 fonte_instrucao: tuple | None = None, ao_confirmar=None) -> None:
        # Quem chama traduz o que passa; os padrões são traduzidos aqui (2026-10-22).
        titulo = titulo if titulo is not None else t("Seleção")
        instrucao = instrucao if instrucao is not None else t("Selecione um ou mais itens:")
        texto_confirmar = texto_confirmar if texto_confirmar is not None else t("Confirmar Seleção")
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
            # 2026-10-20: as cores da lista são as do QListWidget da folha (o tema);
            # das opções do tk.Listbox só a borda continua valendo, na cor `borda`.
            self.listbox.setProperty("com_borda", int(estilo_lista.get("borderwidth", 1)) > 0)
        else:
            # A Listbox crua (com borda), com a barra de rolagem do sistema.
            self.listbox.setProperty("claro", True)
            self.listbox.setProperty("barra_nativa", True)
        self.listbox.setStyleSheet(
            f"QListWidget {{ {blocos.folha_fonte_tk(fonte, em_pontos=True)} outline: none; }}"
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
            self.botao_todos = _botao(t("Selecionar Todos"), largura=150, variante="secundario")
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


class TabelaSelecaoDialog(JanelaQueAbre):
    """Tabela (o `ttk.Treeview` da interface antiga) para escolher várias linhas.

    `linhas` são pares `(chave, valores)`; volta a CHAVE (em texto, como o iid
    do Treeview) -- nunca a posição visual. `larguras` como na interface antiga:
    `{"coluna": {"width": 150, "anchor": "center"}}` (120 sem largura).
    `chave_colunas` liga as colunas lembradas (`widgets/colunas.py`); `colunas_internas` é a chave
    de cada coluna quando o texto mostrado é traduzido.
    """

    def __init__(self, parent=None, *, colunas, linhas, titulo: str | None = None,
                 instrucao: str | None = None, geometria: str = "900x600",
                 larguras: dict | None = None, preselecionar_tudo: bool = False,
                 texto_confirmar: str | None = None, com_cancelar: bool = True,
                 modal: bool = True, ao_confirmar=None, chave_colunas: str | None = None,
                 colunas_internas=None) -> None:
        titulo = titulo if titulo is not None else t("Seleção de Itens")
        instrucao = instrucao if instrucao is not None else t("Selecione as linhas para processar:")
        texto_confirmar = texto_confirmar if texto_confirmar is not None else t("Confirmar Seleção")
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

        larguras = larguras or {}
        self.tree = tabela_ttk([(str(c), int(larguras.get(c, {}).get("width", 120)),
                                 larguras.get(c, {}).get("anchor", "w")) for c in colunas])
        for chave, valores in linhas:
            item = linha_ttk(self.tree, valores, chave=str(chave))
            if preselecionar_tudo:
                item.setSelected(True)
        # [2026-10-26] Colunas lembradas (`widgets/colunas.py`), quando quem abre dá a
        # chave da tabela. A chave de cada coluna é `colunas_internas` (o texto
        # mostrado muda com o idioma) ou, sem ela, o próprio nome da coluna.
        self.colunas = None
        if chave_colunas:
            internas = colunas_internas if colunas_internas is not None else colunas
            self.colunas = instalar_colunas(self.tree, chave_colunas, [str(c) for c in internas])

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
            self.botao_cancelar = _botao(t("Cancelar"), largura=140, variante="secundario")
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
            QMessageBox.warning(self, t("Aviso"), t("Selecione ao menos um item."))
            return
        self._confirmar_com(selecionados, self._ao_confirmar)


class EsticaColunas(QObject):
    """O ttk.Treeview estica as colunas (`stretch=True`, o padrão) para ocupar a
    largura: a sobra é repartida IGUALMENTE entre elas. Encolher abaixo das
    larguras pedidas, não -- aí aparece a rolagem horizontal.

    [2026-10-26] As colunas lembradas (`widgets/colunas.py`) o desligam quando a
    pessoa mexe nas colunas (vale a largura dela) e o religam no "Restaurar
    colunas". `ajustando` diz que a mudança de largura é daqui, e não de quem usa."""

    def __init__(self, tree: QTreeWidget, base: list[int]) -> None:
        super().__init__(tree)
        self._tree, self._base = tree, base
        self.ligado = True
        self.ajustando = False
        tree.viewport().installEventFilter(self)

    def eventFilter(self, objeto, evento) -> bool:  # noqa: N802 -- nome do Qt
        if evento.type() == QEvent.Type.Resize:
            self.esticar()
        return False

    def esticar(self) -> None:
        if not self.ligado or not self._base:
            return
        sobra = self._tree.viewport().width() - sum(self._base)
        extra = max(0, sobra) // len(self._base)
        resto = max(0, sobra) - extra * len(self._base)
        self.ajustando = True
        try:
            for i, largura in enumerate(self._base):
                self._tree.setColumnWidth(i, largura + extra + (resto if i == len(self._base) - 1 else 0))
        finally:
            self.ajustando = False

    def desligar(self) -> None:
        self.ligado = False

    def ligar(self) -> None:
        self.ligado = True
        self.esticar()


def tabela_ttk(colunas, *, selecao: str = "extended", barra_horizontal: bool = True) -> QTreeWidget:
    """O `ttk.Treeview(show="headings")` com as ttk.Scrollbar empacotadas ao lado.

    `colunas`: `[(titulo, largura, anchor)]` (anchor "w" ou "center", o
    `tree.column(..., width=, anchor=)`). `selecao`: "extended" (padrão do ttk)
    ou "browse" (uma linha). As colunas esticam (`EsticaColunas`), o cabeçalho
    é centrado (o heading do ttk), o texto que não cabe é CORTADO (o ttk não põe
    "...") e as barras de rolagem ficam sempre à vista, como as empacotadas.
    Linhas: `linha_ttk(tree, valores, chave=)`.
    """
    tree = QTreeWidget()
    tree.setColumnCount(len(colunas))
    tree.setHeaderLabels([titulo for titulo, _l, _a in colunas])
    tree.setRootIsDecorated(False)
    tree.setUniformRowHeights(True)
    tree.setProperty("barra_nativa", True)
    tree.setTextElideMode(Qt.TextElideMode.ElideNone)
    tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection if selecao == "browse"
                          else QAbstractItemView.SelectionMode.ExtendedSelection)
    tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
    tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn if barra_horizontal
                                      else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    cabecalho = tree.header()
    cabecalho.setStretchLastSection(False)
    cabecalho.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    cabecalho.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
    larguras = [int(largura) for _t, largura, _a in colunas]
    for i, largura in enumerate(larguras):
        tree.setColumnWidth(i, largura)
    tree.setProperty("_alinhamentos", [anchor == "center" for _t, _l, anchor in colunas])
    tree.esticar_colunas = EsticaColunas(tree, larguras)
    return tree


def linha_ttk(tree: QTreeWidget, valores, chave=None) -> QTreeWidgetItem:
    """`tree.insert("", "end", iid=chave, values=valores)`: a chave fica no
    `UserRole` da coluna 0; cada célula com o anchor da sua coluna."""
    item = QTreeWidgetItem([str(v) for v in valores])
    item.setData(0, Qt.ItemDataRole.UserRole, chave)
    for i, centro in enumerate(propriedades.ler(tree, "_alinhamentos") or []):
        item.setTextAlignment(i, Qt.AlignmentFlag.AlignCenter if centro
                              else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    tree.addTopLevelItem(item)
    return item


class ArquivosTravadosDialog(SoltaAoFechar, QDialog):
    """Arquivos que não puderam ser gravados, cada um com o motivo e o que fazer;
    Repetir x Seguir. A decisão volta em `resultado["repetir"]`.

    `itens`: `(nome, motivo, o_que_fazer)`; `momento`: "antes", "depois" ou
    "na_hora" (`TEXTOS_TRAVADOS`). Sem modal: a pessoa vai ao Excel fechar os
    arquivos com a janela aberta. "X" e Esc = Seguir.

    Janela INDEPENDENTE, como o CTkToplevel de lá (sem `transient()`): tem botão
    de minimizar e entrada própria na barra de tarefas, e não vai junto quando a
    janela principal minimiza -- o original diz à pessoa para ir ao Excel e
    "minimizar esta janela, se quiser". Por isso nasce SEM pai Qt (um QDialog com
    pai é "possuído" pela janela principal no Windows); `parent` fica em
    `self.dono` só como referência. Sempre por cima, como o `-topmost` de lá
    (que também ficava por cima do Excel enquanto não minimizada).
    """

    def __init__(self, parent=None, *, itens, momento, evento_espera, resultado: dict) -> None:
        super().__init__(None)
        self.dono = parent
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowStaysOnTopHint)
        textos = TEXTOS_TRAVADOS[momento]
        self.itens = [tuple(item) for item in itens]
        self._evento = evento_espera
        self._resultado = resultado
        self._decidido = False
        self.setWindowTitle(t(textos["titulo"]))
        self.resize(620, 380)

        layout = QVBoxLayout(self)
        # pady do Tk somados: (16, 6) | 4 | (6, 4) | (4, 16).
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(0)
        self.rotulo_explicacao = blocos.rotulo(t(textos["explicacao"]), tamanho=13, alinhar="esquerda")
        layout.addWidget(self.rotulo_explicacao)
        layout.addSpacing(6 + 4)

        area, lista = blocos.area_rolavel(fundo="cartao")
        self.area = area
        for nome, motivo, o_que_fazer in self.itens:
            lista.addSpacing(8)
            r_nome = blocos.rotulo(nome, tamanho=14, negrito=True, alinhar="esquerda")
            r_motivo = blocos.rotulo(t("Motivo: {motivo}. {o_que_fazer}", motivo=motivo, o_que_fazer=o_que_fazer), tamanho=12,
                                     papel="legenda", alinhar="esquerda")
            for r in (r_nome, r_motivo):
                r.setContentsMargins(10, 0, 10, 0)
                lista.addWidget(r)
            lista.addSpacing(6)
        layout.addWidget(area, 1)
        layout.addSpacing(4 + 6)

        self.rotulo_rodape = blocos.rotulo(t(textos["rodape"]), tamanho=12,
                                           papel="legenda", alinhar="esquerda")
        layout.addWidget(self.rotulo_rodape)
        layout.addSpacing(4 + 4)

        self.botao_repetir = blocos.botao(t(textos["repetir"]), variante="primario", largura=170, altura=40,
                                          tamanho_fonte=14, negrito=True)
        self.botao_seguir = blocos.botao(t(textos["seguir"]), variante="contorno", largura=170, altura=40)
        for b in (self.botao_repetir, self.botao_seguir):
            sem_tecla(b)  # nem Enter nem Espaço decidem: o worker espera a pessoa escolher
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

    def _ao_fechar_sem_decidir(self) -> None:
        """"X", Esc ou qualquer `reject()` sem decisão = Seguir (`SoltaAoFechar`)."""
        self._responder(False)
