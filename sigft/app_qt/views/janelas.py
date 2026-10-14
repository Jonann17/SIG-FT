"""As janelas auxiliares das telas na interface Qt (E3.2).

Mesmas janelas de `sigft/app/views/janelas.py`, com a mesma forma de chamar --
as telas Qt (Cria Fichas, Cópia de Fichas, Correção de PDM) as usam como as
CustomTkinter usavam:

* `JanelaSelecao(tela, df, callback)` e `JanelaSelecaoDuplicadas(tela, fila,
  callback)` -- funções finas sobre o `TabelaSelecaoDialog`;
* `JanelaResumo(tela, df)` -- tabela de conferência ao fim de um lote;
* `JanelaEscolherPDM(tela, catalogo, sugestoes=())` -- modal; o `wait_window(janela)` de lá
  vira `janela.esperar()` (devolve a escolha) e `.escolha` continua lá;
* `JanelaRevisaoPDM(tela, df, callback, catalogo=None)` -- revisão do PDM;
* `JanelaAcaoRobo(tela, msg_erro=..., pdm_atual=...)` -- devolve um objeto com
  `.escolha` e `.novo_pdm`, como a de lá;
* `JanelaRevisaoEdicao(tela, fila)` -- edita os dicts da fila no lugar.

Threads: só a `JanelaAcaoRobo` era aberta de DENTRO do worker (o robô de
`cria_fichas.py`, um widget criado fora da thread da interface -- no macOS isso
derruba o app). Aqui ela é uma função que pode ser chamada de qualquer thread:
a janela nasce na thread da interface e o worker espera num `threading.Event`,
como em `DialogosDeEspera`. As outras são abertas por clique ou por
`self.after(0, ...)`; na tela Qt, quem vem do worker usa
`interface.na_interface(JanelaResumo, self, df)`.

O espaçamento reproduz o `pack` de lá (o pady de dois vizinhos SOMA) e foi
conferido em captura CTk x Qt (`capturas/e3.2`).
"""
from __future__ import annotations

import threading
import traceback
from typing import NamedTuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QSizePolicy, QVBoxLayout,
)

from sigft.app import theme
from sigft.app.theme import COLORS
from sigft.app_qt import estilo, interface
from sigft.app_qt.widgets import blocos, dialogos_selecao, dialogs
# 2026-10-08: o que a revisão de PDMs mostra (confiança, ordem, "por quê",
# 2º e 3º lugar) é regra do serviço; a janela só exibe -- a mesma de lá.
from sigft.services import cria_fichas_escolha as escolha

# Cores com nome do Tk que as telas escreviam ("green", "red"): no Tk 8.6 são
# as do W3C/CSS, e o Qt não as lê da mesma forma em folha de estilo.
VERDE_TK = "#008000"
VERMELHO_TK = "#FF0000"
# CTkLabel sem `text_color`: o texto do tema (gray84), não o text_light.
COR_TEXTO_CTK = estilo.cinza_tk("gray84")

# A janela do robô, aberta pelo worker, fica sem referência na tela: precisa
# continuar viva enquanto está aberta.
_ABERTAS: set = set()


# =============================================================================
# Peças comuns
# =============================================================================
class _Janela(dialogos_selecao.JanelaQueAbre):
    """Um CTkToplevel (abre ao ser construído: `_abrir()` no fim do __init__ de
    cada uma). `parent` faz o papel do `transient(parent)`; `modal` é o
    `grab_set()`; `sempre_por_cima`, o `-topmost`. A referência viva enquanto
    aberta, o `esperar()` (o `wait_window`) e o hideEvent que o solta vêm de
    `dialogos_selecao.JanelaQueAbre`."""

    def __init__(self, parent, *, titulo: str, largura: int, altura: int,
                 modal: bool = False, sempre_por_cima: bool = False) -> None:
        super().__init__(parent, titulo=titulo, geometria=f"{largura}x{altura}", modal=modal,
                         sempre_por_cima=sempre_por_cima)


def _rotulo(texto: str, fonte: tuple = theme.FONTE_CORPO, *, cor: str = COR_TEXTO_CTK,
            alinhar: str = "centro") -> QLabel:
    """CTkLabel: altura mínima 28, fonte em PIXELS, fundo transparente.
    `alinhar="esquerda"` é o `anchor="w"`."""
    r = QLabel(texto)
    r.setAlignment(Qt.AlignmentFlag.AlignCenter if alinhar == "centro"
                   else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    r.setMinimumHeight(blocos.ALTURA_MINIMA_ROTULO)
    r.setStyleSheet(f"QLabel {{ {blocos.folha_fonte_tk(fonte)} color: {cor}; background: transparent; }}")
    return r


def _botao(texto: str, *, fundo: str | None = None, hover: str = estilo.AZUL_CTK_HOVER) -> QPushButton:
    """CTkButton padrão destas janelas: 28 de altura e `width` 140 que o texto
    largo alarga (`largura_minima`). `fundo` sem `hover` = o hover do tema: é o
    que o CTk faz com `fg_color` sem `hover_color`."""
    b = blocos.botao(texto, altura=28, largura_minima=estilo.LARGURA_BOTAO_CTK,
                     cor_fundo=fundo, cor_hover=hover)
    # Enter não aperta botão nenhum: o Tk não ligava tecla nestas janelas.
    b.setAutoDefault(False)
    b.setDefault(False)
    return b


_tabela = dialogos_selecao.tabela_ttk
_linha = dialogos_selecao.linha_ttk


# Esc não fecha. Todas as `_Janela` já o herdam de `JanelaQueAbre` (a revisão
# de PDM, que jogava fora as edições, e o `_PopupEdicao`, que perdia o texto
# dos campos); o nome fica para a janela do robô, que é um QDialog cru (fechar
# ali é PARAR o lote).
_IgnoraEsc = dialogs.IgnoraEsc


def _faixa(*widgets, espaco: int = 0) -> QHBoxLayout:
    linha = QHBoxLayout()
    linha.setContentsMargins(0, 0, 0, 0)
    linha.setSpacing(espaco)
    for w in widgets:
        if w is None:
            linha.addStretch()
        else:
            linha.addWidget(w)
    return linha


# =============================================================================
# Seleção (funções sobre o TabelaSelecaoDialog)
# =============================================================================
def JanelaSelecao(parent, dataframe, callback_confirmar):  # noqa: N802 -- nome de lá
    """Escolher linhas de uma planilha. O callback recebe os ÍNDICES do
    DataFrame em `int` (o `[int(i) for i in tree.selection()]` de lá): o
    ModuloCriaFichas indexa o DataFrame com eles."""
    return dialogos_selecao.TabelaSelecaoDialog.de_dataframe(
        parent,
        dataframe,
        titulo="Seleção de Itens",
        instrucao="Selecione as linhas para processar:",
        geometria="900x600",
        com_cancelar=False,
        ao_confirmar=lambda chaves: callback_confirmar([int(i) for i in chaves]),
    )


def JanelaSelecaoDuplicadas(parent, fila_completa, callback_confirmar):  # noqa: N802 -- nome de lá
    """Selecionar, entre as duplicadas, quais rodar agora. Tudo já vem marcado;
    a chave de cada linha é a POSIÇÃO na fila -- o callback recebe os próprios
    dicts da `fila_completa` (a revisão manual os edita no lugar)."""
    colunas = ("Descrição", "PMIB Original (Base)", "PMIB Alvo (Novo)")
    linhas = [
        (idx, (item["descricao"], item["pmib_original"], item["pmib_alvo"]))
        for idx, item in enumerate(fila_completa)
    ]

    def _confirmar(chaves):
        callback_confirmar([fila_completa[int(i)] for i in chaves])

    return dialogos_selecao.TabelaSelecaoDialog(
        parent,
        colunas=colunas,
        linhas=linhas,
        titulo="Selecionar Fichas para Cópia",
        instrucao="Selecione as fichas que deseja processar neste lote:",
        geometria="900x500",
        larguras={
            "Descrição": {"width": 400},
            "PMIB Original (Base)": {"width": 150, "anchor": "center"},
            "PMIB Alvo (Novo)": {"width": 150, "anchor": "center"},
        },
        preselecionar_tudo=True,
        ao_confirmar=_confirmar,
    )


# =============================================================================
# Resumo
# =============================================================================
class JanelaResumo(_Janela):
    """Tabela de conferência ao fim de um lote de criação. Sem modal."""

    COLUNAS = ["Descrição Original", "PMIB Criado", "PDM (IA)", "PDM (Portal Final)"]

    def __init__(self, parent, df_comparacao) -> None:
        super().__init__(parent, titulo="Resumo Final", largura=1000, altura=500)
        layout = QVBoxLayout(self)
        # título pady=10 | quadro padx=10, pady=10 | Fechar pady=10 (somados).
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(0)
        self.rotulo = _rotulo("Resumo da Execução", ("Arial", 18, "bold"))
        layout.addWidget(self.rotulo)
        layout.addSpacing(20)

        self.tree = _tabela([(c, 300, "w") for c in self.COLUNAS])
        for _, row in df_comparacao.iterrows():
            _linha(self.tree, [row.get("descricao_original", "-"), row.get("PMIB_CRIADO", "-"),
                               row.get("pdm_escolhido", "-"), row.get("PDM_COM_REVISAO", "-")])
        quadro = QHBoxLayout()
        quadro.setContentsMargins(10, 0, 10, 0)
        quadro.addWidget(self.tree)
        layout.addLayout(quadro, 1)
        layout.addSpacing(20)

        self.botao_fechar = _botao("Fechar")
        self.botao_fechar.clicked.connect(self.close)
        layout.addWidget(self.botao_fechar, 0, Qt.AlignmentFlag.AlignHCenter)
        self._abrir()


# =============================================================================
# Escolher PDM
# =============================================================================
class JanelaEscolherPDM(_Janela):
    """Escolha de um PDM do catálogo, com busca (`CatalogoPDM.buscar`).

    Modal. A escolha fica em `.escolha` (um `PDM`, ou None se cancelou/fechou);
    `esperar()` é o `wait_window` de lá e devolve a mesma coisa.
    """

    LINHAS_VISIVEIS = 40

    def __init__(self, parent, catalogo, sugestoes=()) -> None:
        super().__init__(parent, titulo="Escolher PDM", largura=900, altura=560, modal=True)
        self.catalogo = catalogo
        self.escolha = None
        self._achados = []
        # 2º e 3º lugar da IA, fixos no topo enquanto a busca está vazia.
        self._sugestoes = list(sugestoes or ())
        self._rotulo_da_sugestao = {pdm.codigo: rotulo for pdm, rotulo in self._sugestoes}

        layout = QVBoxLayout(self)
        # topo padx=10, pady=10 (busca com pady=(6, 0)) | lista pady=(6, 0) |
        # rodapé pady=10.
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        self.rotulo = _rotulo(f"Busque entre os {len(catalogo)} PDMs do catálogo:",
                              ("Roboto", 13, "bold"), alinhar="esquerda")
        layout.addWidget(self.rotulo)
        layout.addSpacing(6)
        self.entry_busca = QLineEdit()
        self.entry_busca.setPlaceholderText("ex.: valvula esfera  |  4820.004  |  camera")
        self.entry_busca.textChanged.connect(lambda _t: self._atualizar())
        self.entry_busca.returnPressed.connect(self.confirmar)
        layout.addWidget(self.entry_busca)
        layout.addSpacing(10 + 6)

        self.lista = _tabela([("PDM", 330, "w"), ("Classe", 70, "w"), ("Características", 460, "w")],
                             selecao="browse", barra_horizontal=False)
        self.lista.itemDoubleClicked.connect(lambda _i, _c: self.confirmar())
        layout.addWidget(self.lista, 1)
        layout.addSpacing(10)

        self.lbl_contagem = _rotulo("", cor=estilo.cinza_tk(theme.COR_TEXTO_APOIO), alinhar="esquerda")
        self.botao_usar = _botao("USAR ESTE PDM", fundo=COLORS["accent"])
        self.botao_usar.clicked.connect(self.confirmar)
        self.botao_cancelar = _botao("Cancelar", fundo="#3A3A3A")
        self.botao_cancelar.clicked.connect(self.cancelar)
        # pack(side="right", padx=5) dos dois: 10 entre eles, 5 da borda.
        rodape = _faixa(self.lbl_contagem, None, self.botao_usar, self.botao_cancelar)
        rodape.insertSpacing(3, 10)
        rodape.addSpacing(5)
        layout.addLayout(rodape)

        self._atualizar()
        self._abrir()
        self.entry_busca.setFocus()

    def _atualizar(self) -> None:
        procurado = self.entry_busca.text()
        self._achados = self.catalogo.buscar(procurado, limite=self.LINHAS_VISIVEIS)
        com_sugestoes = not procurado.strip() and self._sugestoes
        if com_sugestoes:
            self._achados = escolha.juntar_sugestoes(self._sugestoes, self._achados, self.LINHAS_VISIVEIS)
        self.lista.clear()
        for posicao, pdm in enumerate(self._achados):
            detalhe = "; ".join(pdm.caracteristicas[:6])
            if com_sugestoes and pdm.codigo in self._rotulo_da_sugestao:
                detalhe = "★ " + self._rotulo_da_sugestao[pdm.codigo]
            _linha(self.lista, (pdm.completo, pdm.classe, detalhe), chave=posicao)
        self.lbl_contagem.setText(
            f"{len(self._achados)} PDM(s) na lista"
            + (f" (mostrando os {self.LINHAS_VISIVEIS} primeiros)"
               if len(self._achados) >= self.LINHAS_VISIVEIS else ""))
        if self._achados:
            primeiro = self.lista.topLevelItem(0)
            primeiro.setSelected(True)
            self.lista.setCurrentItem(primeiro)

    def confirmar(self) -> None:
        selecionados = self.lista.selectedItems()
        if not selecionados:
            QMessageBox.warning(self, "Aviso", "Selecione um PDM da lista.")
            return
        self.escolha = self._achados[selecionados[0].data(0, Qt.ItemDataRole.UserRole)]
        self.accept()

    def cancelar(self) -> None:
        self.escolha = None
        self.reject()

    def esperar(self):
        super().esperar()
        return self.escolha


# =============================================================================
# Revisão do PDM
# =============================================================================
class JanelaRevisaoPDM(_Janela):  # Esc não fecha: herdado de JanelaQueAbre
    """Revisão, linha a linha, do PDM que a IA escolheu, antes do robô. Modal.

    Trabalha numa CÓPIA do DataFrame; `callback_confirmar(df)` só no
    "CONFIRMAR" (com o sim da pessoa). Com `catalogo`, editar abre a
    `JanelaEscolherPDM` (com o 2º e o 3º lugar da IA, se a linha é uma só);
    sem ele (modo "Pular IA"), o campo de texto livre. A ordem das linhas, a
    coluna "Confiança" e o "por quê" sob a tabela vêm do serviço
    (`cria_fichas_escolha`), como lá.
    """

    def __init__(self, parent, dataframe, callback_confirmar, catalogo=None) -> None:
        # 1250x640 (era 1100x600), como lá: a coluna Confiança cabe sem
        # empurrar "Tipo" para fora; a altura extra é do "por quê".
        super().__init__(parent, titulo="Revisão de PDMs - Pré-Automação", largura=1250, altura=640,
                         modal=True)
        self.df_dados = dataframe.copy()
        self.callback = callback_confirmar
        self.catalogo = catalogo

        layout = QVBoxLayout(self)
        # topo padx=10, pady=10 | tabela padx=10, pady=(0, 10) | "por quê"
        # padx=12, pady=(0, 10).
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        # CTkFrame de fundo padrão (gray13, cantos 6), da altura dos botões.
        self.topo = QFrame(objectName="topo_revisao")
        self.topo.setStyleSheet(f"#topo_revisao {{ background: {estilo.cinza_tk(estilo.FUNDO_QUADRO_CTK)};"
                                " border-radius: 6px; }")
        self.rotulo = _rotulo("Verifique os PDMs sugeridos antes da automação.", ("Arial", 14, "bold"),
                              alinhar="esquerda")
        self.botao_editar = _botao("Editar PDM Selecionado")
        self.botao_editar.clicked.connect(self.editar_pdm)
        self.botao_confirmar = _botao("CONFIRMAR E AVANÇAR >>", fundo=VERDE_TK)
        self.botao_confirmar.clicked.connect(self.confirmar)
        # pack(side="right", padx=5) dos dois botões.
        faixa = _faixa(self.rotulo, None, self.botao_editar, self.botao_confirmar)
        faixa.insertSpacing(3, 10)
        faixa.addSpacing(5)
        self.topo.setLayout(faixa)
        layout.addWidget(self.topo)

        self.tree = _tabela([("ID", 40, "w"), ("Descrição Original", 350, "w"),
                             ("PDM Escolhido (EDITÁVEL)", 250, "w"), ("Confiança", 140, "w"),
                             ("Descrição Curta", 200, "w"), ("UN", 50, "w"), ("Tipo", 100, "w")])
        layout.addWidget(self.tree, 1)

        # O "por quê" da linha selecionada: justificativa, conferências e o que
        # a IA leu do material. Texto da IA: fonte do corpo, nunca mono. O
        # CTkLabel não quebra linha e corta o que passa da janela; aqui, sem
        # `Ignored`, uma justificativa longa ALARGARIA a janela.
        self.lbl_porque = _rotulo("", alinhar="esquerda")
        self.lbl_porque.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        # Texto da IA: nunca interpretado como HTML (o QLabel adivinharia).
        self.lbl_porque.setTextFormat(Qt.TextFormat.PlainText)
        faixa_porque = QHBoxLayout()
        faixa_porque.setContentsMargins(2, 0, 2, 0)  # padx=12 = os 10 da borda + 2
        faixa_porque.addWidget(self.lbl_porque)
        layout.addLayout(faixa_porque)
        self.tree.itemSelectionChanged.connect(self._mostrar_porque)

        self.preencher_tabela()
        self._abrir()

    def preencher_tabela(self) -> None:
        self.tree.clear()
        # A ORDEM vem do serviço (o que precisa de olho primeiro); a coluna ID
        # continua com o índice original, que é o que liga a linha à planilha.
        indices = list(self.df_dados.index)
        linhas = [row for _index, row in self.df_dados.iterrows()]
        for posicao in escolha.ordem_para_revisao(linhas):
            index, row = indices[posicao], linhas[posicao]
            _linha(self.tree, [index, row.get("descricao_original", ""), row.get("pdm_escolhido", ""),
                               escolha.rotulo_de_confianca(row), row.get("descricao_curta", ""),
                               row.get("unidade", ""), row.get("tipo", "")],
                   chave=index)

    def _linha_do_df(self, item):
        return self.df_dados.loc[item.data(0, Qt.ItemDataRole.UserRole)]

    def _mostrar_porque(self) -> None:
        selecionados = self.tree.selectedItems()
        texto = ""
        if len(selecionados) == 1:
            texto = escolha.texto_do_porque(self._linha_do_df(selecionados[0]))
        self.lbl_porque.setText(texto)

    def editar_pdm(self) -> None:
        selecionados = self.tree.selectedItems()
        if not selecionados:
            QMessageBox.warning(self, "Aviso", "Selecione uma ou mais linhas para editar o PDM.")
            return

        if self.catalogo is not None:
            sugestoes = []
            if len(selecionados) == 1:
                sugestoes = escolha.sugestoes_da_linha(self._linha_do_df(selecionados[0]), self.catalogo)
            janela = JanelaEscolherPDM(self, self.catalogo, sugestoes=sugestoes)
            escolhido = janela.esperar()
            novo_pdm = escolhido.completo if escolhido else None
        else:
            texto, ok = QInputDialog.getText(
                self, "Editar PDM", "Digite o novo código PDM completo (ex: PDM.1234.001 - NOME):")
            novo_pdm = texto if ok else None

        if novo_pdm:
            for item in selecionados:
                self.df_dados.at[item.data(0, Qt.ItemDataRole.UserRole), "pdm_escolhido"] = novo_pdm
                item.setText(2, novo_pdm)  # coluna do PDM; o resto da linha fica
                item.setText(3, "MANUAL")  # a confiança era da escolha da IA

    def confirmar(self) -> None:
        resposta = QMessageBox.question(
            self, "Confirmar", "Deseja prosseguir para a automação com estes dados?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resposta == QMessageBox.StandardButton.Yes:
            self.callback(self.df_dados)
            self.accept()


# =============================================================================
# Ação do robô
# =============================================================================
class DecisaoRobo(NamedTuple):
    """O que a `JanelaAcaoRobo` devolve: os dois atributos que o robô lia dela."""

    escolha: str
    novo_pdm: str | None = None


class DialogoAcaoRobo(_IgnoraEsc, QDialog):
    """A janela de decisão quando o robô falha num item: RETRY, SKIP,
    CHANGE_PDM (com `novo_pdm`) ou STOP. Fechar no "X" = STOP, como lá.

    Não abre sozinha: quem a abre é `JanelaAcaoRobo`, de qualquer thread.
    """

    def __init__(self, parent, msg_erro, pdm_atual) -> None:
        super().__init__(parent)
        self.setWindowTitle("Atenção: Intervenção Necessária")
        self.resize(500, 350)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)  # o grab_set()
        self.escolha = None
        self.novo_pdm = None
        # Quem espera a resposta (o worker) é solto por aqui se a janela sumir
        # sem `done()` -- ver `JanelaAcaoRobo`.
        self.ao_sumir = None

        layout = QVBoxLayout(self)
        # pady somados: título (15, 5) | caixa 5 | PDM 5 | quadro de botões 10,
        # e cada botão pady=5 dentro dele.
        layout.setContentsMargins(0, 15, 0, 0)
        layout.setSpacing(0)
        self.rotulo_erro = _rotulo("Ocorreu um erro ao processar o item:", ("Roboto", 14, "bold"),
                                   cor=VERMELHO_TK)
        layout.addWidget(self.rotulo_erro)
        layout.addSpacing(10)

        # CTkTextbox(height=60, font=("Consolas", 11)), desabilitado.
        self.caixa_erro = QPlainTextEdit(str(msg_erro))
        self.caixa_erro.setReadOnly(True)
        self.caixa_erro.setFixedHeight(60)
        self.caixa_erro.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.caixa_erro.setWordWrapMode(QTextOption.WrapMode.WrapAnywhere)  # wrap="char"
        self.caixa_erro.setStyleSheet(_FOLHA_CAIXA_TEXTO)
        self.caixa_erro.document().setDocumentMargin(0)
        caixa = QHBoxLayout()
        caixa.setContentsMargins(20, 0, 20, 0)
        caixa.addWidget(self.caixa_erro)
        layout.addLayout(caixa)
        layout.addSpacing(10)

        self.rotulo_pdm = _rotulo(f"PDM Atual: {pdm_atual}", ("Roboto", 12))
        layout.addWidget(self.rotulo_pdm)
        layout.addSpacing(5 + 10 + 5)

        botoes = QVBoxLayout()
        botoes.setContentsMargins(20, 0, 20, 0)
        botoes.setSpacing(10)
        self.botao_retry = _botao("[0] Tentar Novamente (Mesmo PDM)")
        self.botao_retry.clicked.connect(lambda: self._responder("RETRY"))
        self.botao_pular = _botao("[1] Pular este Item", fundo="#B8860B", hover="#DAA520")
        self.botao_pular.clicked.connect(lambda: self._responder("SKIP"))
        self.entry_pdm = QLineEdit()
        self.entry_pdm.setPlaceholderText("Novo código PDM...")
        self.botao_mudar = _botao("[2] Mudar PDM e Tentar")
        self.botao_mudar.clicked.connect(self._mudar_pdm)
        self.botao_parar = _botao("[3] Parar Automação e Salvar", fundo=VERMELHO_TK, hover="#8B0000")
        self.botao_parar.clicked.connect(lambda: self._responder("STOP"))
        botoes.addWidget(self.botao_retry)
        botoes.addWidget(self.botao_pular)
        mudar = _faixa(self.entry_pdm, self.botao_mudar, espaco=5)  # entrada padx=(0, 5)
        botoes.addLayout(mudar)
        botoes.addWidget(self.botao_parar)
        layout.addLayout(botoes)
        layout.addStretch()

    def _responder(self, acao: str) -> None:
        self.escolha = acao
        self.accept()

    def _mudar_pdm(self) -> None:
        pdm_digitado = self.entry_pdm.text().strip()
        if pdm_digitado:
            self.novo_pdm = pdm_digitado
            self._responder("CHANGE_PDM")
        else:
            QMessageBox.warning(self, "Aviso", "Digite o novo PDM antes de clicar.")

    def reject(self) -> None:
        """O "X" chega aqui (pelo `closeEvent`): sem decisão, PARA tudo, como lá."""
        if self.escolha is None:
            self.escolha = "STOP"
        super().reject()

    def hideEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        """Sumiu sem `done()` (`hide()`, o pai fechando): sem decisão é STOP, e
        `ao_sumir` solta o worker. Minimizar (evento espontâneo) não conta."""
        super().hideEvent(evento)
        if evento.spontaneous():
            return
        if self.escolha is None:
            self.escolha = "STOP"
        if self.ao_sumir is not None:
            self.ao_sumir()


# CTkTextbox do tema: fundo gray20, sem borda, cantos 6, texto gray84; a
# barra de rolagem é a do CTk (16 px, alça gray41 de 8).
_FOLHA_CAIXA_TEXTO = (
    f"QPlainTextEdit {{ background: {estilo.cinza_tk('gray20')}; border: none; border-radius: 6px;"
    f" color: {COR_TEXTO_CTK}; padding: 3px 0 3px 6px; {blocos.folha_fonte_tk(('Consolas', 11))} }}"
    f" QScrollBar:vertical {{ width: {estilo.LARGURA_ROLAGEM_CTK}px; background: transparent;"
    " margin: 6px 0 6px 0; }"
    f" QScrollBar::handle:vertical {{ background: {estilo.cinza_tk('gray41')}; border-radius: 4px;"
    " margin: 0 4px; min-height: 20px; }"
    f" QScrollBar::handle:vertical:hover {{ background: {estilo.cinza_tk('gray53')}; }}"
    " QScrollBar::add-line, QScrollBar::sub-line { height: 0; }"
    " QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }")


def JanelaAcaoRobo(parent, msg_erro, pdm_atual) -> DecisaoRobo:  # noqa: N802 -- nome de lá
    """Pergunta o que fazer com o item que falhou e ESPERA a resposta.

    Chamável do worker (o robô): a janela nasce na thread da interface e o
    worker espera num `threading.Event`. Da própria thread da interface,
    `exec()`. Devolve `DecisaoRobo(escolha, novo_pdm)` -- o robô lê
    `.escolha` e `.novo_pdm`, como lia da janela de lá. Se a janela não
    abrir, STOP: a resposta segura (salva o que já foi feito).
    """
    if interface.na_thread_da_interface():
        dialogo = DialogoAcaoRobo(parent, msg_erro, pdm_atual)
        dialogo.exec()
        return DecisaoRobo(dialogo.escolha or "STOP", dialogo.novo_pdm)

    evento = threading.Event()
    caixa: dict = {}

    def abrir() -> None:
        try:
            dialogo = DialogoAcaoRobo(parent, msg_erro, pdm_atual)

            def fim(*_sinal) -> None:
                if evento.is_set():
                    return
                caixa["decisao"] = DecisaoRobo(dialogo.escolha or "STOP", dialogo.novo_pdm)
                _ABERTAS.discard(dialogo)
                evento.set()

            # Três saídas, e qualquer uma solta o worker (uma vez só): fechou
            # (`finished`), sumiu sem `done()` (`ao_sumir`, do hideEvent) ou foi
            # destruída junto com o pai (`destroyed`: aí não há mais o que ler
            # nela, e a resposta fica STOP).
            dialogo.finished.connect(fim)
            dialogo.ao_sumir = fim
            dialogo.destroyed.connect(lambda *_: evento.set())
            _ABERTAS.add(dialogo)
            dialogo.show()
            dialogo.raise_()
            dialogo.activateWindow()
        except Exception:  # noqa: BLE001 -- o worker não pode ficar preso
            traceback.print_exc()
            evento.set()

    interface.na_interface(abrir)
    evento.wait()
    return caixa.get("decisao", DecisaoRobo("STOP"))


# =============================================================================
# Revisão e edição manual (Cópia de Fichas)
# =============================================================================
class JanelaRevisaoEdicao(_Janela):
    """Ver a fila e corrigir à mão os códigos Original/Alvo (quando o regex
    falhou). Edita os dicts da `fila_selecionada` NO LUGAR: a tela lê deles."""

    def __init__(self, parent, fila_selecionada) -> None:
        super().__init__(parent, titulo="Revisão e Edição Manual", largura=900, altura=500,
                         modal=True, sempre_por_cima=True)
        self.fila_selecionada = fila_selecionada
        self.popup = None

        layout = QVBoxLayout(self)
        # rótulo pady=10 | quadro padx=20, pady=10 | Concluir pady=15.
        layout.setContentsMargins(0, 10, 0, 15)
        layout.setSpacing(0)
        self.rotulo = _rotulo("Dê um DUPLO CLIQUE em uma linha para editar os códigos PMIB.",
                              ("Roboto", 14, "bold"))
        layout.addWidget(self.rotulo)
        layout.addSpacing(20)

        self.tree = _tabela([("ID", 40, "center"), ("Descrição", 350, "w"),
                             ("PMIB Original (Ler Dados)", 150, "center"),
                             ("PMIB Alvo (Escrever)", 150, "center")],
                            selecao="browse", barra_horizontal=False)
        self.tree.itemDoubleClicked.connect(lambda _i, _c: self.on_double_click())
        quadro = QHBoxLayout()
        quadro.setContentsMargins(20, 0, 20, 0)
        quadro.addWidget(self.tree)
        layout.addLayout(quadro, 1)
        layout.addSpacing(10 + 15)
        self.atualizar_tabela()

        self.botao_concluir = _botao("Concluir Revisão", fundo=COLORS["primary"])
        self.botao_concluir.clicked.connect(self.close)
        layout.addWidget(self.botao_concluir, 0, Qt.AlignmentFlag.AlignHCenter)
        self._abrir()

    def atualizar_tabela(self) -> None:
        self.tree.clear()
        for idx, item in enumerate(self.fila_selecionada):
            _linha(self.tree, (idx + 1, item["descricao"], item["pmib_original"], item["pmib_alvo"]),
                   chave=idx)

    def on_double_click(self, _evento=None) -> None:
        selecionado = self.tree.selectedItems()
        if not selecionado:
            return
        self.popup = _PopupEdicao(self, selecionado[0].data(0, Qt.ItemDataRole.UserRole))

    def _salvar(self, idx: int, novo_orig: str, novo_alvo: str) -> None:
        self.fila_selecionada[idx]["pmib_original"] = novo_orig
        self.fila_selecionada[idx]["pmib_alvo"] = novo_alvo
        self.atualizar_tabela()


class _PopupEdicao(_Janela):
    """O pop-up "Editar Item" da revisão (400x300, por cima e modal)."""

    def __init__(self, revisao: JanelaRevisaoEdicao, idx: int) -> None:
        super().__init__(revisao, titulo="Editar Item", largura=400, altura=300,
                         modal=True, sempre_por_cima=True)
        self._revisao = revisao
        self._idx = idx
        item_ref = revisao.fila_selecionada[idx]

        layout = QVBoxLayout(self)
        # rótulos pady=(15, 0), campos pady=5, Salvar pady=20; padx=20.
        layout.setContentsMargins(20, 15, 20, 0)
        layout.setSpacing(0)
        self.rotulo_orig = _rotulo("PMIB Original (Ficha Base):", alinhar="esquerda")
        self.entry_orig = QLineEdit(item_ref["pmib_original"])
        self.rotulo_alvo = _rotulo("PMIB Alvo (Nova Ficha):", alinhar="esquerda")
        self.entry_alvo = QLineEdit(item_ref["pmib_alvo"])
        layout.addWidget(self.rotulo_orig)
        layout.addSpacing(5)
        layout.addWidget(self.entry_orig)
        layout.addSpacing(5 + 15)
        layout.addWidget(self.rotulo_alvo)
        layout.addSpacing(5)
        layout.addWidget(self.entry_alvo)
        layout.addSpacing(5 + 20)
        self.botao_salvar = _botao("Salvar Alteração", fundo=COLORS["primary"])
        self.botao_salvar.clicked.connect(self.salvar)
        layout.addWidget(self.botao_salvar, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()
        self._abrir()

    def salvar(self) -> None:
        novo_orig = self.entry_orig.text().strip()
        novo_alvo = self.entry_alvo.text().strip()
        if not novo_orig or not novo_alvo:
            QMessageBox.warning(self, "Aviso", "Os códigos não podem ficar vazios.")
            return
        self._revisao._salvar(self._idx, novo_orig, novo_alvo)
        self.accept()
