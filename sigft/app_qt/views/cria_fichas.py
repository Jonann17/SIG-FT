"""Tela "Cria Fichas PMIB" (Módulo de Criação) na interface Qt.

Mesma tela de `sigft/app/views/cria_fichas.py`: lê a lista de materiais,
categoriza os itens com IA para escolher o PDM, deixa a pessoa revisar e cria
as fichas no portal; na segunda aba, a edição em massa do código do projeto.
Serviços, robô e portal são os mesmos (nenhum seletor muda aqui).

O que muda é só COMO as threads falam com a interface. Lá os workers mexiam
em botão e barra direto, abriam o resumo por `after(0)` e chamavam
`messagebox` de dentro do robô; aqui:

* o que o worker precisa da tela (código do projeto, "Pular IA", as linhas
  selecionadas, a planilha de PDMs, o lote do robô) é tirado no clique, e a
  volta é sempre por `interface.na_interface`;
* o resultado da IA vai para a revisão, não para o lote do robô: o robô só
  enxerga o que a pessoa confirmou; e um robô por vez (criação ou edição);
* a janela de decisão do robô (`JanelaAcaoRobo`) nasce na thread da interface
  e o robô espera a resposta;
* o "Preparo" depois de RETRY/CHANGE_PDM continua SEGURANDO o robô até o OK
  (`avisar(..., esperar=True)`): é a pausa para a pessoa arrumar o navegador.
"""
from __future__ import annotations

import functools
import traceback

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QMessageBox, QSizePolicy, QVBoxLayout, QWidget

from sigft.app.textos_dialogos import MSG_LOGIN_NOVA_FICHA, MSG_LOGIN_PAGINA_PRINCIPAL
from sigft.app.theme import COLORS
from sigft.app_qt import estilo, file_dialogs, interface
from sigft.app_qt.views.janelas import JanelaAcaoRobo, JanelaResumo, JanelaRevisaoPDM, JanelaSelecao
from sigft.app_qt.widgets import blocos, controles
from sigft.app_qt.widgets.abas import Abas
from sigft.app_qt.widgets.module_frame import MARGEM_DA_TELA, ModuleFrame
# O catálogo de PDMs (2026-09-22): lê a planilha-mestra da Itaipu e faz o
# pré-filtro de candidatos por item. `cria_fichas_svc` entra pelas guardas
# (`conferir_pdm`); as classes do serviço (DataManager, GeminiCategorizer,
# AutomacaoPMIB) vêm por `self.backend(...)`, que avisa se não carregaram.
from sigft.core import pdm_catalogo
from sigft.services import cria_fichas as cria_fichas_svc

ABA_CRIACAO = "Criação de Fichas"
ABA_EDICAO = "Editar código do projeto"
URL_LISTA = "https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList"
MSG_PREPARO = "Certifique-se de que a tela do navegador está na lista principal antes de clicar em OK."
# Um robô por vez: a criação e a edição usam o mesmo navegador (`self.bot`), e
# uma revisão confirmada no meio não pode subir um segundo robô.
MSG_ROBO_OCUPADO = ("O robô já está trabalhando no portal (criação ou edição). "
                    "Espere ele terminar antes de iniciar outro.")
PLACEHOLDER_PROJETO = (
    "Ex: SERVIÇOS AUXILIARES ELÉTRICOS / CAP.05 - CONVERSORES ESTÁTICOS DE FREQUENCIA / "
    "Especificar subsistema | #ST00=B01MSE00&EPB020 / 08934100BAX00-FS00PB-51 | "
    "Evento de Pagamento: 2835 / 2835 a / 2836")

# Os cinzas que a tela escrevia à mão: #3A3A3A/#454545 é a variante "cinza";
# #2B2B2B é o botão de PDMs "apagado" (a cor do cartão) no modo "Pular IA".
CINZA, CINZA_HOVER, CINZA_APAGADO = "#3A3A3A", "#454545", "#2B2B2B"
COR_ROTULO_APOIO = estilo.cinza_tk("gray")          # text_color="gray" do Tk
# O grid da tela CTk: linha 1 (Tabview, weight=3) e linha 2 (console,
# weight=1). O Tk dá a cada linha o que ela PEDE e reparte a sobra (ou a
# falta) pelos pesos. Pedidos medidos no CTk: Tabview 261, CTkTextbox 200.
PEDIDO_ABAS, PEDIDO_CONSOLE = 261, 200
PESO_ABAS, PESO_CONSOLE = 3, 1
# O CTkScrollableFrame de cada aba: conteúdo 6 px dentro, barra 1 px antes da borda.
RECUO_ROLAGEM = 6


def _rotulo(texto: str, *, tamanho: int = 13, negrito: bool = False, cor: str = controles.COR_TEXTO_CTK,
            largura: int | None = None):
    """CTkLabel de uma linha, anchor="w", 28 px de altura (`width` fixa se pedida).
    Sem `cor`, a do CTkLabel sem text_color (gray84), e não o text_light do app."""
    r = blocos.rotulo(texto, tamanho=tamanho, negrito=negrito, cor=cor, alinhar="esquerda")
    r.setWordWrap(False)
    r.setFixedHeight(blocos.ALTURA_MINIMA_ROTULO)
    if largura:
        r.setFixedWidth(largura)
    return r


def _titulo(texto: str):
    return _rotulo(texto, tamanho=16, negrito=True, cor=COLORS["accent"])


# O "▶" do "Iniciar Robô de Edição": o Roboto não o tem, e a reserva da folha
# (Noto Emoji) desenha o emoji "play" -- um quadrado com o triângulo dentro. A
# lista de fontes de símbolos mora no `estilo` desde a E4.10 (o "⬇" do AutoSpec).
FAMILIAS_COM_SIMBOLO = estilo.FAMILIAS_COM_SIMBOLO


def _botao(texto: str, *, com_simbolo: bool = False, **kw):
    """`blocos.botao` sem Enter: o Tk não ligava tecla nenhuma aos botões."""
    b = blocos.botao(texto, **kw)
    b.setAutoDefault(False)
    if com_simbolo:
        b.setStyleSheet(f"{b.styleSheet()} QPushButton {{ font-family: {FAMILIAS_COM_SIMBOLO}; }}")
    b.setProperty("_folha_base", b.styleSheet())
    return b


def _pintar(botao, fundo: str, hover: str) -> None:
    """O `configure(fg_color=...)` do CTk: troca o fundo, mantém o resto da folha.
    `hover` é o hover_color que o botão já tinha (o configure não o mudava)."""
    botao.setStyleSheet(f"{botao.property('_folha_base')} QPushButton {{ background: {fundo}; }}"
                        f" QPushButton:hover {{ background: {hover}; }}")


def _cor_rotulo(rotulo, cor: str) -> None:
    rotulo.setStyleSheet(f"font-size: 13px; background: transparent; color: {cor};")


def _cartao(corpo, *, fim: int, recuo: int = 0):
    """CTkFrame #2B2B2B de cantos 8: peças com padx=15, título com pady 10.
    `recuo` é o padx do próprio cartão (10 na aba de edição)."""
    linha = QHBoxLayout()
    linha.setContentsMargins(recuo, 0, recuo, 0)
    corpo.addLayout(linha)
    layout = blocos.cartao(linha)
    layout.setContentsMargins(15, 10, 15, fim)
    layout.setSpacing(0)
    return layout


def _linha(layout) -> QHBoxLayout:
    linha = QHBoxLayout()
    linha.setContentsMargins(0, 0, 0, 0)
    linha.setSpacing(0)
    layout.addLayout(linha)
    return linha


def _area_da_aba(aba: QWidget):
    """CTkScrollableFrame transparente que ocupa a aba, com a barra sempre à
    vista (o CTk reserva a faixa mesmo sem nada para rolar). Devolve
    `(area, corpo)`: o conteúdo tem a largura da aba menos 6 + 17."""
    area, corpo = blocos.area_rolavel(aba.layout(), margem=RECUO_ROLAGEM)
    area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
    # A barra do CTk fica 1 px antes da borda direita: faixa de 17 com a alça
    # de 8 a 4 px da esquerda (a mesma da Cópia de Fichas).
    area.verticalScrollBar().setStyleSheet(
        estilo.folha_rolagem_ctk(margem_vertical=RECUO_ROLAGEM + 4)
        + f"\nQScrollBar:vertical {{ width: {estilo.LARGURA_ROLAGEM_CTK + 1}px;"
        f" margin: {RECUO_ROLAGEM + 4}px 5px {RECUO_ROLAGEM + 4}px 4px; }}")
    corpo.setContentsMargins(RECUO_ROLAGEM, RECUO_ROLAGEM, 0, RECUO_ROLAGEM)
    return area, corpo


def _barra():
    """CTkProgressBar(progress_color=accent), pack(fill="x", padx=15, pady=15), em 0."""
    barra = blocos.barra_progresso(barra=blocos.BarraDeProgresso(), cor=COLORS["accent"])
    barra.definir(0)
    return barra


# =============================================================================
# MÓDULO 1: CRIA FICHAS NO PMIB (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloCriaFichas(ModuleFrame):
    def __init__(self, parent=None, controller=None) -> None:
        # Variáveis de Estado
        self.file_path_excel = None
        self.file_path_pdm = None
        self.df_data_completo = None
        self.df_data_selecionado = None
        self.df_processed = None
        self.df_resumo_final = None
        self.df_edicao_completo = None
        self.df_edicao_selecionado = None
        self.bot = None
        # Catálogo de PDMs da planilha escolhida. Só existe depois da etapa de
        # IA; a revisão e a conferência pós-portal o consultam.
        self.catalogo = None
        self.api_key_gemini = controller.get_key("GEMINI") if controller is not None else ""
        # Do clique em "3. Analisar" até a revisão fechar, o botão fica
        # desligado: nada (nem o "Pular IA") o religa no meio da cadeia.
        self._ia_em_andamento = False
        # Liga ao subir um robô (criação ou edição) e desliga no fim dele, os
        # dois na thread da interface: os dois robôs usam o navegador e o `self.bot`.
        self._robo_ativo = False
        self.janela_resumo = None
        self._df_da_janela_resumo = None
        super().__init__(parent, controller, titulo="Módulo de Criação", altura_console=None)
        # Lá a tela não é o ModuleFrame: header pady=10, Tabview pady=0,
        # console pady=10, dentro do padx/pady=20 do `show_frame`. Os pady
        # vizinhos SOMAM: 10 entre header e abas, 10 entre abas e console.
        raiz = self.layout()
        raiz.setContentsMargins(MARGEM_DA_TELA + 20, MARGEM_DA_TELA + 10,
                                MARGEM_DA_TELA + 20, MARGEM_DA_TELA + 10)
        raiz.setSpacing(0)
        raiz.insertSpacing(1, 10)                       # header (…, 10) + abas (0, …)
        raiz.insertSpacing(3, 10)                       # abas (…, 0) + console (10, …)

    # --- montagem -------------------------------------------------------------
    def _build_ui(self) -> None:
        # Tabview dentro de um CTkFrame de fundo padrão: o quadro é gray16.
        self.abas = Abas(cor_fundo=estilo.FUNDO_QUADRO_INTERNO_CTK)
        self.content_layout.addWidget(self.abas)
        self.aba_criacao = self.abas.add(ABA_CRIACAO)
        self.aba_edicao = self.abas.add(ABA_EDICAO)
        self._build_ui_criacao()
        self._build_ui_edicao()

    def _build_ui_criacao(self) -> None:
        self.area_criacao, corpo = _area_da_aba(self.aba_criacao)

        # --- ETAPA 1: CONFIGURAÇÃO E INPUTS ---
        corpo.addSpacing(10)                            # frm_config: pady=10
        config = _cartao(corpo, fim=10)
        self.cartao_config = config.parentWidget()
        self.rotulo_etapa1 = _titulo("1. Configuração Inicial")
        config.addWidget(self.rotulo_etapa1)
        config.addSpacing(15)                           # título (…, 10) + f_proj (5, …)

        # Código do Projeto
        linha = _linha(config)
        self.rotulo_projeto = _rotulo("Código do Projeto:", largura=150)
        linha.addWidget(self.rotulo_projeto)
        self.entry_projeto = QLineEdit()  # o visual (28 px) é o do CTkEntry, na folha do app
        self.entry_projeto.setPlaceholderText(PLACEHOLDER_PROJETO)
        linha.addWidget(self.entry_projeto, 1)
        linha.addSpacing(10)                            # entry: padx=(0, 10)
        config.addSpacing(10)                           # f_proj (…, 5) + f_pmib (5, …)

        # Botão Selecionar PMIB
        linha = _linha(config)
        self.rotulo_pmib = _rotulo("Arquivo STATUS_PMIB:", largura=150)
        linha.addWidget(self.rotulo_pmib)
        self.btn_pmib = _botao("Selecionar Excel (.xlsx)", variante="cinza", largura=200, altura=28)
        self.btn_pmib.clicked.connect(self.selecionar_excel_pmib)
        linha.addWidget(self.btn_pmib)
        linha.addSpacing(10)                            # lbl_status: padx=10
        self.lbl_status = _rotulo("Aguardando...", cor=COR_ROTULO_APOIO)
        linha.addWidget(self.lbl_status)
        linha.addStretch()
        config.addSpacing(15)                           # f_pmib (…, 5) + f_opts (10, …)

        # Checkbox Pular IA e Botão PDM
        linha = _linha(config)
        self.chk_pular = controles.CaixaDeMarcar("Pular IA (Dados já no Excel)",
                                                 cor_marcada=COLORS["primary"],
                                                 cor_hover=COLORS["primary_hover"])
        self.chk_pular.toggled.connect(self._toggle_pdm_button)
        linha.addWidget(self.chk_pular)
        linha.addSpacing(20)                            # btn_pdm: padx=20
        # Texto de 2026-09-22: o módulo aceita a planilha-mestra da Itaipu
        # (PDMs SAM-GM) direto -- é dela que vêm a classe FSC e as características.
        self.btn_pdm = _botao("Selecionar planilha de PDMs (mestra)", variante="cinza",
                              largura_minima=estilo.LARGURA_BOTAO_CTK, altura=28)
        self.btn_pdm.clicked.connect(self.selecionar_excel_pdm)
        linha.addWidget(self.btn_pdm)
        linha.addSpacing(20)
        self.lbl_status_pdm = _rotulo("", cor=COR_ROTULO_APOIO)
        linha.addWidget(self.lbl_status_pdm)
        linha.addStretch()

        # --- ETAPA 2: PROCESSAMENTO ---
        corpo.addSpacing(20)                            # frm_config (…, 10) + frm_action (10, …)
        acoes = _cartao(corpo, fim=15)
        self.cartao_acoes = acoes.parentWidget()
        self.rotulo_etapa2 = _titulo("2. Execução")
        acoes.addWidget(self.rotulo_etapa2)
        acoes.addSpacing(20)                            # título (…, 10) + grade (10, …)

        # A "tabela invisível" de lá: colunas 0 e 1 dividem o espaço por igual
        # (uniform, CONTANDO o padx de cada célula: (0, 5) e (5, 15)); a 2 é o
        # Limpar de 100 px, das duas linhas.
        grade = _linha(acoes)
        branco = COLORS["text_white"]
        self.btn_run_ai = _botao("3. Analisar (IA)", variante="primario", altura=40, tamanho_fonte=14,
                                 negrito=True, cor_texto=branco)
        self.btn_run_ai.clicked.connect(self.run_ai_thread)
        self.btn_run_auto = _botao("4. Robô Web", variante="primario", altura=40, tamanho_fonte=14,
                                   negrito=True, cor_texto=branco)
        self.btn_run_auto.clicked.connect(self.run_automation_thread)
        self.btn_resumo = _botao("Ver Resumo", variante="cinza", altura=40, tamanho_fonte=12,
                                 negrito=True, cor_texto=branco)
        self.btn_resumo.clicked.connect(self.abrir_resumo_manual)
        self.btn_save = _botao("5. Salvar no Excel", variante="primario", altura=40, tamanho_fonte=12,
                               negrito=True, cor_texto=branco)
        self.btn_save.clicked.connect(self.salvar_excel)
        for (cima, baixo), margens in (((self.btn_run_ai, self.btn_resumo), (0, 0, 5, 0)),
                                       ((self.btn_run_auto, self.btn_save), (5, 0, 15, 0))):
            coluna = QWidget()
            coluna.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            caixa = QVBoxLayout(coluna)
            caixa.setContentsMargins(*margens)
            caixa.setSpacing(10)                        # linha 0 pady=(0, 5) + linha 1 (5, 0)
            for b in (cima, baixo):
                b.setEnabled(False)
                caixa.addWidget(b)
            grade.addWidget(coluna, 1)
        self.btn_reset = _botao(estilo.mono("🗑️\nLimpar"), variante="perigo", largura=100,
                                tamanho_fonte=14, negrito=True, cor_texto=branco)
        # sticky="nsew" nas duas linhas: a altura é a da grade (90), não a das
        # duas linhas de texto (Ignored: o emoji não pode alargar a grade).
        self.btn_reset.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Ignored)
        self.btn_reset.clicked.connect(self.resetar_processo)
        grade.addWidget(self.btn_reset)
        acoes.addSpacing(25)                            # grade (…, 10) + barra (15, …)

        self.progress = _barra()
        acoes.addWidget(self.progress)
        corpo.addSpacing(10)                            # frm_action: pady=10

    def _build_ui_edicao(self) -> None:
        self.area_edicao, corpo = _area_da_aba(self.aba_edicao)

        # --- ETAPA 1: CONFIGURAÇÃO ---
        corpo.addSpacing(10)                            # frm_config: pady=10, padx=10
        config = _cartao(corpo, fim=10, recuo=10)
        self.cartao_config_edicao = config.parentWidget()
        self.rotulo_etapa1_edicao = _titulo("1. Configuração da Edição")
        config.addWidget(self.rotulo_etapa1_edicao)
        config.addSpacing(15)                           # título (…, 10) + f_proj (5, …)

        linha = _linha(config)
        self.rotulo_novo_projeto = _rotulo("Novo Código do Projeto:", largura=180)
        linha.addWidget(self.rotulo_novo_projeto)
        self.entry_novo_projeto = QLineEdit()
        self.entry_novo_projeto.setPlaceholderText("Ex: NOVO CÓDIGO AQUI...")
        linha.addWidget(self.entry_novo_projeto, 1)
        linha.addSpacing(10)                            # entry: padx=(0, 10)
        config.addSpacing(15)                           # f_proj (…, 5) + f_excel (10, …)

        linha = _linha(config)
        self.rotulo_excel_edicao = _rotulo("Selecionar Fichas (Excel):", largura=180)
        linha.addWidget(self.rotulo_excel_edicao)
        self.btn_excel_edicao = _botao("Abrir Excel e Selecionar", variante="cinza", largura=200, altura=28)
        self.btn_excel_edicao.clicked.connect(self.selecionar_excel_edicao)
        linha.addWidget(self.btn_excel_edicao)
        linha.addSpacing(10)                            # lbl_status_edicao: padx=10
        self.lbl_status_edicao = _rotulo("Nenhum item selecionado.", cor=COR_ROTULO_APOIO)
        linha.addWidget(self.lbl_status_edicao)
        linha.addStretch()

        # --- ETAPA 2: EXECUÇÃO ---
        corpo.addSpacing(20)                            # frm_config (…, 10) + frm_action (10, …)
        acoes = _cartao(corpo, fim=15, recuo=10)
        self.cartao_acoes_edicao = acoes.parentWidget()
        self.rotulo_etapa2_edicao = _titulo("2. Execução em Massa")
        acoes.addWidget(self.rotulo_etapa2_edicao)
        acoes.addSpacing(20)                            # título (…, 10) + f_btns (10, …)
        self.btn_run_edicao = _botao(estilo.mono("▶ Iniciar Robô de Edição"), variante="primario", altura=40,
                                     tamanho_fonte=14, negrito=True, cor_texto=COLORS["text_white"],
                                     com_simbolo=True)
        self.btn_run_edicao.clicked.connect(self.run_edicao_thread)
        self.btn_run_edicao.setEnabled(False)
        acoes.addWidget(self.btn_run_edicao)
        acoes.addSpacing(25)                            # f_btns (…, 10) + barra (15, …)
        self.progress_edicao = _barra()
        acoes.addWidget(self.progress_edicao)
        corpo.addSpacing(10)

    # --- altura: abas × console como o grid do Tk ---------------------------------
    def resizeEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        self._repartir_altura()
        super().resizeEvent(evento)

    def _repartir_altura(self) -> None:
        """Abas × console como o grid do Tk: cada um com o que pede, a sobra
        repartida 3:1 (o Tk trunca a parte das abas; o resto é do console)."""
        margens = self.layout().contentsMargins()
        disponivel = (self.height() - margens.top() - margens.bottom()
                      - self.header.sizeHint().height() - 10 - 10)
        sobra = disponivel - PEDIDO_ABAS - PEDIDO_CONSOLE
        abas = PEDIDO_ABAS + int(sobra * PESO_ABAS / (PESO_ABAS + PESO_CONSOLE))
        self.console.setFixedHeight(max(disponivel - abas, 0))

    # --- Lógica Mantida (apenas ajustada para a nova UI) ---
    def _toggle_pdm_button(self, *_marcada) -> None:
        if self.chk_pular.isChecked():
            self.btn_pdm.setEnabled(False)
            _pintar(self.btn_pdm, CINZA_APAGADO, CINZA_HOVER)  # Cor "apagada"
            if not self._ia_em_andamento:
                self.btn_run_ai.setEnabled(True)
            self.btn_run_ai.setText("3. Processar (Direto)")
        else:
            self.btn_pdm.setEnabled(True)
            _pintar(self.btn_pdm, CINZA, CINZA_HOVER)
            self.btn_run_ai.setText("3. Analisar (IA)")

    def selecionar_excel_pmib(self) -> None:
        # Antes do diálogo: escolher o arquivo para depois ouvir que o módulo
        # não carregou seria pedir o trabalho à toa.
        data_manager = self.backend("DataManager")
        if data_manager is None:
            return
        path = file_dialogs.ask_open_file("cria_fichas.excel_pmib", "excel", filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        self.file_path_excel = path
        cols = ["DESCRIÇÃO", "CÓDIGO PMIB"]

        df, cod_sug, erro = data_manager.carregar_planilha_inteligente(path, "Lista de Materiais", cols)
        if df is None:
            df, cod_sug, erro = data_manager.carregar_planilha_inteligente(path, 0, cols)

        if df is not None:
            self.df_data_completo = df
            self.log(f"Carregado: {len(df)} linhas.")

            if cod_sug:
                self.entry_projeto.setText(cod_sug)  # Escreve o novo código
                self.log("Código de Projeto preenchido automaticamente.")

            JanelaSelecao(self, df, self.pos_selecao)
        else:
            QMessageBox.critical(self, "Erro", erro)

    def pos_selecao(self, indices) -> None:
        # `reset_index(drop=True)`: o número do item é a CHAVE do casamento da
        # resposta da IA (`cria_fichas.alinhar_resposta`), e os itens precisam
        # ser 1, 2, 3 -- não o número da linha na planilha inteira.
        self.df_data_selecionado = self.df_data_completo.iloc[indices].copy().reset_index(drop=True)
        self.log(f"Selecionado: {len(self.df_data_selecionado)} itens.")
        self.lbl_status.setText(f"{len(self.df_data_selecionado)} itens selecionados")
        _cor_rotulo(self.lbl_status, COLORS["accent"])
        _pintar(self.btn_pmib, COLORS["primary"], CINZA_HOVER)  # Marca visual de sucesso
        self._toggle_pdm_button()
        if not self.chk_pular.isChecked():
            _pintar(self.btn_pdm, CINZA, CINZA_HOVER)

    def selecionar_excel_pdm(self) -> None:
        path = file_dialogs.ask_open_file("cria_fichas.excel_pdm", "excel",
                                          filetypes=[("Arquivos Excel", "*.xlsx;*.xls")])
        if path:
            self.file_path_pdm = path
            if not self._ia_em_andamento:
                self.btn_run_ai.setEnabled(True)
            _pintar(self.btn_pdm, COLORS["primary"], CINZA_HOVER)

            # Pega apenas o nome do arquivo final (ex: "planilha.xlsx") ignorando as pastas
            nome_arquivo = path.split("/")[-1]
            self.lbl_status_pdm.setText(f"Selecionado: {nome_arquivo}")
            _cor_rotulo(self.lbl_status_pdm, COLORS["accent"])
            self.log(f"PDMs carregados: {nome_arquivo}")

    # --- IA: clique -> worker -> revisão (uma cadeia, o botão desligado nela toda)
    def run_ai_thread(self) -> None:
        cod_proj = self.entry_projeto.text()
        if not cod_proj:
            QMessageBox.warning(self, "Aviso", "Preencha o Código do Projeto.")
            return
        pular = self.chk_pular.isChecked()
        if not pular and not self.file_path_pdm:
            QMessageBox.warning(self, "Aviso", "Selecione o arquivo de PDMs antes de iniciar a IA.")
            return
        categorizador = None
        if not pular:
            categorizador = self.backend("GeminiCategorizer")
            if categorizador is None:
                return
        self.api_key_gemini = self.controller.get_key("GEMINI") if self.controller is not None else ""
        # As linhas e a planilha de PDMs saem daqui, do clique: a IA leva minutos
        # e "Selecionar Excel" continua ligado -- trocar a seleção no meio poria
        # as descrições novas sob as respostas dadas para as antigas. A seleção é
        # TROCADA (`pos_selecao` cria outro DataFrame), nunca alterada no lugar:
        # esta referência é a do clique.
        df = self.df_data_selecionado
        caminho_pdm = self.file_path_pdm

        self._ia_em_andamento = True
        self.btn_run_ai.setEnabled(False)
        blocos.modo_indeterminado(self.progress, True)
        # Sem `botao=`: o botão NÃO volta no fim do worker -- volta só se a
        # cadeia falhar ou a revisão for fechada sem confirmar.
        self.iniciar_tarefa(self._ai_worker, cod_proj, pular, categorizador, df, caminho_pdm,
                            self.api_key_gemini)

    def _ai_worker(self, cod_proj, pular, categorizador, df, caminho_pdm, chave) -> None:
        """Só lê os argumentos (o que foi tirado no clique) e não grava nada na
        tela: o resultado vai para `_depois_da_ia`, na thread da interface."""
        resultado = None
        try:
            final_data = []
            catalogo = None
            if pular:
                self.log("Modo 'Pular IA'. Lendo dados do Excel...")
                for index, row in df.iterrows():
                    item_json = {
                        'item_processado': index,
                        'codigo_projeto': cod_proj,
                        'descricao_original': row['DESCRIÇÃO'],
                        'pdm_escolhido': row.get('PDM', 'NENHUM'),
                        'descricao_curta': row.get('DESC_CURTA', str(row['DESCRIÇÃO'])[:40]),
                        'origem': row.get('ORIGEM', 'Nacional'),
                        'tipo': row.get('TIPO', 'Não Reparável'),
                        'unidade': row.get('UNIDADE', 'Unidade'),
                        'tipo de fabricação': row.get('FABRICACAO', 'Catálogo'),
                    }
                    final_data.append(item_json)
                self.log(f"Processados {len(final_data)} itens.")
            else:
                # Construir o categorizador ANTES do prompt é o que permite logar
                # o modelo de verdade (o construtor só resolve config, não chama a API).
                cat = categorizador(chave)
                self.log(f"Processando com IA ({cat.modelo_em_uso})...")

                # A planilha-mestra da Itaipu (abas TEMPLATE_PDM/GRUPOS_CLASES)
                # direto, ou o formato manipulado antigo.
                catalogo = pdm_catalogo.carregar(caminho_pdm)
                self.log(
                    f"Catálogo: {len(catalogo)} PDMs, "
                    f"{len(catalogo.classes_com_pdm())} classes com PDM."
                )

                res_json = cat.processar_lote(df, catalogo, callback_log=self.log)
                sem_resposta = 0
                fora_do_catalogo = 0
                for i, item_json in enumerate(res_json):
                    row = df.iloc[i]
                    if item_json is None:
                        # A IA não respondeu este item: fica 'NENHUM' para a
                        # revisão, sem deslocar os seguintes.
                        sem_resposta += 1
                        item_json = {"pdm_escolhido": "NENHUM"}
                        self.log(
                            f" -> ⚠️ Item {i + 1} sem resposta da IA. Marcado "
                            f"'NENHUM' para revisão: {str(row['DESCRIÇÃO'])[:40]}"
                        )

                    ok_pdm, motivo = cria_fichas_svc.conferir_pdm(item_json, catalogo)
                    if not ok_pdm:
                        # PDM inventado pela IA: não pode chegar ao filtro do
                        # portal, que aperta ENTER e leva o que estiver destacado.
                        fora_do_catalogo += 1
                        self.log(f" -> ⚠️ Item {i + 1}: {motivo}. Marcado 'NENHUM'.")
                        item_json["pdm_escolhido"] = "NENHUM"

                    item_json['codigo_projeto'] = cod_proj
                    item_json['descricao_original'] = row['DESCRIÇÃO']
                    final_data.append(item_json)

                self.log(
                    f"IA Finalizada. {len(final_data)} itens | "
                    f"sem resposta: {sem_resposta} | "
                    f"PDM fora do catálogo: {fora_do_catalogo}"
                )

            # Para a REVISÃO, não para o `df_processed`: o robô só enxerga o que
            # a pessoa confirmou (lá, fechar a revisão nova no "X" deixava o robô
            # de um lote anterior apontado para dados que ninguém conferiu).
            resultado = (pd.DataFrame(final_data), catalogo)
            self.log("Abrindo janela de Revisão...")
        except Exception as e:  # noqa: BLE001 -- vira log, como lá
            self.log(f"Erro no processamento: {e}")
        finally:
            interface.na_interface(self._depois_da_ia, resultado)

    def _depois_da_ia(self, resultado) -> None:
        """Na thread da interface, no fim do worker da IA (bem ou mal).

        Protegida: uma exceção aqui sumiria na ponte (`interface._rodar` só a
        imprime) e deixaria "3. Analisar" desligado para sempre.
        """
        self._parar_progresso()
        if resultado is None:
            self._fim_da_cadeia_da_ia()
            return
        df_novo, catalogo_novo = resultado
        # "Pular IA" não carrega catálogo: a revisão usa o que a tela já tinha, como lá.
        catalogo = catalogo_novo if catalogo_novo is not None else self.catalogo
        try:
            self.abrir_revisao_pdm(df_novo, catalogo)
        except Exception as erro:  # noqa: BLE001 -- o botão tem de voltar
            traceback.print_exc()
            self.log(f"Erro ao abrir a revisão: {type(erro).__name__}: {erro}")
            self._fim_da_cadeia_da_ia()

    def _parar_progresso(self) -> None:
        try:
            blocos.modo_indeterminado(self.progress, False)
            self.progress.definir(0)
        except RuntimeError:
            pass  # tela já destruída

    def _fim_da_cadeia_da_ia(self) -> None:
        """A cadeia acabou sem a revisão confirmada: o botão volta."""
        self._ia_em_andamento = False
        try:
            self.btn_run_ai.setEnabled(True)
        except RuntimeError:
            pass  # tela já destruída

    def abrir_revisao_pdm(self, df, catalogo) -> None:
        if df is not None and not df.empty:
            # O catálogo vai junto para o CONFIRMAR: o da tela (o do robô) só
            # muda com a revisão confirmada, como o `df_processed`.
            confirmar = functools.partial(self._pos_revisao_concluida, catalogo=catalogo)
            janela = JanelaRevisaoPDM(self, df, confirmar, catalogo=catalogo)
            janela.finished.connect(self._revisao_fechada)
        else:
            QMessageBox.critical(self, "Erro", "Nenhum dado processado.")
            self._fim_da_cadeia_da_ia()

    def _revisao_fechada(self, resultado) -> None:
        if resultado == QDialog.DialogCode.Accepted:
            self._ia_em_andamento = False
        else:
            # Fechada no "X": lá o botão ficava desligado até o "Limpar".
            self._fim_da_cadeia_da_ia()

    def _pos_revisao_concluida(self, df_atualizado, catalogo=None) -> None:
        self.df_processed = df_atualizado
        self.catalogo = catalogo
        self.log(f"Revisão OK. {len(self.df_processed)} itens prontos.")
        # Com um robô rodando, o "4. Robô Web" volta sozinho no fim dele (e
        # então leva ESTE lote); ligá-lo agora subiria um segundo robô.
        if not self._robo_ativo:
            self.btn_run_auto.setEnabled(True)
        _pintar(self.btn_run_auto, COLORS["accent"], COLORS["primary_hover"])
        self.btn_run_ai.setEnabled(False)
        self.btn_run_ai.setText("3. Analisar (OK)")

    # --- robô de criação ---------------------------------------------------------
    def run_automation_thread(self) -> None:
        if self._robo_ocupado():
            return
        automacao = self.backend("AutomacaoPMIB")
        if automacao is None:
            return
        # O lote e o catálogo saem daqui, do clique: uma revisão confirmada com o
        # robô rodando troca `df_processed`, e o resumo deste robô é do lote DELE.
        self._iniciar_robo(self._bot_worker, automacao, self.df_processed, self.catalogo,
                           botao=self.btn_run_auto)

    # --- um robô por vez (criação ou edição) ----------------------------------------
    def _robo_ocupado(self) -> bool:
        """Com um robô já rodando, diz no console por que nada começa."""
        if self._robo_ativo:
            self.log(MSG_ROBO_OCUPADO)
            return True
        return False

    def _iniciar_robo(self, worker, *args, botao) -> None:
        self._robo_ativo = True
        self.iniciar_tarefa(self._rodar_robo, worker, *args, botao=botao)

    def _rodar_robo(self, worker, *args) -> None:
        """Na tarefa: roda o robô e, dê no que der, devolve a vez (na interface)."""
        try:
            worker(*args)
        finally:
            interface.na_interface(self._robo_terminou)

    def _robo_terminou(self) -> None:
        self._robo_ativo = False

    def _definir_progresso(self, barra, fracao) -> None:
        try:
            barra.definir(fracao)
        except RuntimeError:
            pass  # tela já destruída

    def _bot_worker(self, automacao, df, catalogo) -> None:
        bot = automacao()
        self.bot = bot  # o "Limpar" fecha o navegador por aqui
        try:
            bot.iniciar_driver()
            bot.abrir_portal(URL_LISTA)
            # A instrução de QUAL página abrir: a janela nasce na thread da
            # interface e este worker espera o "Continuar".
            self.pausar_e_esperar(MSG_LOGIN_NOVA_FICHA)
            self.log("Iniciando Robô...")
            sucessos = []
            total = len(df)

            # Variável de controle para abortar o loop principal (STOP)
            abortar_automacao = False

            for idx, row in df.iterrows():
                if abortar_automacao:
                    break

                interface.na_interface(self._definir_progresso, self.progress, (idx + 1) / total)
                self.log(f"Processando Item {idx + 1}/{total}: {row['descricao_original'][:30]}...")

                # Cópia mutável da linha, para permitir alterar o PDM
                row_atual = row.copy()
                retry = True

                while retry:
                    status, res = bot.processar_item_individual(row_atual)

                    if status == "SUCESSO":
                        self.log(f" -> ✅ SUCESSO: PMIB {res[0]} | PDM {res[1]}")
                        self._conferir_pdm_do_portal(
                            pedido=row_atual.get('pdm_escolhido', ''),
                            gravado=res[1],
                            pmib=res[0],
                            catalogo=catalogo,
                        )
                        sucessos.append((row_atual['descricao_original'], res[0], res[1]))
                        retry = False

                    elif status == "PULAR":
                        self.log(" -> ⏭️ PULADO automaticamente (PDM era 'NENHUM').")
                        sucessos.append((row_atual['descricao_original'], "VERIFICAR (PULADO)",
                                         "VERIFICAR (PULADO)"))
                        retry = False

                    else:
                        self.log(f" -> ❌ ERRO no Selenium: {res}")

                        # A janela abre na thread da interface; o robô espera a decisão.
                        decisao = JanelaAcaoRobo(self, msg_erro=res, pdm_atual=row_atual.get('pdm_escolhido', ''))
                        escolha = decisao.escolha

                        if escolha == "RETRY":
                            self.log(" -> 🔄 Retentativa solicitada pelo usuário.")
                            # SEGURA o robô até o OK (a pessoa arruma o navegador).
                            self.avisar("Preparo", MSG_PREPARO, esperar=True)
                            # O loop 'while' continua (retry = True)

                        elif escolha == "CHANGE_PDM":
                            novo_pdm = decisao.novo_pdm
                            self.log(f" -> ✏️ PDM alterado pelo usuário para: {novo_pdm}")
                            row_atual['pdm_escolhido'] = novo_pdm
                            self.avisar("Preparo", MSG_PREPARO, esperar=True)
                            # O loop 'while' continua com o 'row_atual' modificado

                        elif escolha == "SKIP":
                            self.log(" -> ⏭️ Item PULADO pelo usuário.")
                            sucessos.append((row_atual['descricao_original'], "VERIFICAR (PULADO)",
                                             "VERIFICAR (PULADO)"))
                            # Força o reset da tela para o próximo item do laço iniciar limpo
                            try:
                                bot.abrir_portal(URL_LISTA)
                            except Exception:  # noqa: BLE001 -- como lá: segue para o próximo
                                pass
                            retry = False

                        elif escolha == "STOP":
                            self.log(" -> 🛑 Automação interrompida pelo usuário. Salvando progresso parcial...")
                            # Registro de erro apenas para o item que estava quebrado
                            sucessos.append((row_atual['descricao_original'], "INTERROMPIDO", "INTERROMPIDO"))
                            retry = False
                            abortar_automacao = True  # Quebra o for principal

            # --- Fim do Loop (ou Interrupção) ---
            self.log("Montando resumo final...")
            df_selenium = pd.DataFrame(sucessos, columns=['descricao_original', 'PMIB_CRIADO', 'PDM_COM_REVISAO'])
            resumo = pd.merge(df, df_selenium, on='descricao_original', how='inner')

            interface.na_interface(self._fim_do_robo, resumo)

            # Finaliza o driver
            try:
                bot.driver.quit()
            except Exception:  # noqa: BLE001 -- navegador já fechado
                pass

        except Exception as e:  # noqa: BLE001 -- vira log, como lá
            self.log(f"Erro Fatal na Thread do Robô: {e}")

    def _fim_do_robo(self, resumo) -> None:
        self.df_resumo_final = resumo
        try:
            self._mostrar_resumo()
            self.btn_save.setEnabled(True)
            self.btn_resumo.setEnabled(True)
        except RuntimeError:
            pass  # tela já destruída

    def _conferir_pdm_do_portal(self, pedido, gravado, pmib, catalogo) -> None:
        """O PDM que o portal gravou é o que pedimos?

        O fluxo do portal é filtrar-e-apertar-ENTER: uma string que casa vários
        PDMs, ou nenhum, leva o que estiver destacado. Divergência aqui é a
        única forma de descobrir isso sem reabrir a ficha. Só registra no log:
        a ficha já foi criada, e decidir o que fazer com ela é do usuário.
        """
        codigo_pedido = cria_fichas_svc.codigo_do_pdm(pedido)
        codigo_gravado = cria_fichas_svc.codigo_do_pdm(gravado)
        if not codigo_pedido or not codigo_gravado:
            return
        if codigo_pedido != codigo_gravado:
            self.log(
                f" -> ⚠️ DIVERGÊNCIA no PMIB {pmib}: pedimos {codigo_pedido} "
                f"e o portal gravou {codigo_gravado}. Confira a ficha."
            )
            return

        self._conferir_revisao_do_pdm(codigo_gravado, gravado, pmib, catalogo)

    def _conferir_revisao_do_pdm(self, codigo, gravado, pmib, catalogo) -> None:
        """A ficha saiu com a revisão mais nova do PDM? (É o que a Itaipu cobra.)

        - **portal < Master**: a ficha foi criada com uma revisão velha;
        - **portal > Master**: o Master local está desatualizado (o aviso é
          para pedir um novo à Itaipu).
        """
        revisao_gravada = cria_fichas_svc.revisao_do_pdm(gravado)
        if revisao_gravada is None or catalogo is None:
            return
        pdm = catalogo.por_codigo(codigo)
        if pdm is None or pdm.revisao is None:
            return

        if revisao_gravada < pdm.revisao:
            self.log(
                f" -> ⚠️ PMIB {pmib}: a ficha ficou na revisão R{revisao_gravada} "
                f"do {codigo}, mas o catálogo já tem R{pdm.revisao}. A Itaipu "
                f"costuma pedir a revisão mais nova."
            )
        elif revisao_gravada > pdm.revisao:
            self.log(
                f" -> ℹ️ PMIB {pmib}: o portal usou R{revisao_gravada} do "
                f"{codigo} e a sua planilha de PDMs só tem até R{pdm.revisao}. "
                f"Vale pedir um Master atualizado à Itaipu."
            )

    # --- resumo e Excel ------------------------------------------------------------
    def abrir_resumo_manual(self) -> None:
        if self.df_resumo_final is not None:
            self._mostrar_resumo()

    def _mostrar_resumo(self) -> None:
        """Uma janela de resumo só: o segundo clique traz a aberta para a frente.
        Um lote novo fecha a do lote anterior e abre a dele."""
        janela = self.janela_resumo
        try:
            aberta = janela is not None and janela.isVisible()
        except RuntimeError:
            aberta = False  # destruída pelo Qt
        if aberta and self._df_da_janela_resumo is self.df_resumo_final:
            janela.raise_()
            janela.activateWindow()
            return
        if aberta:
            janela.close()
        janela = JanelaResumo(self, self.df_resumo_final)
        # Fechada, a janela (com a tabela inteira) é apagada, como o destroy()
        # do CTk; sem isto, cada "Ver Resumo" deixava uma escondida na tela.
        janela.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.janela_resumo = janela
        self._df_da_janela_resumo = self.df_resumo_final

    def salvar_excel(self) -> None:
        if self.df_resumo_final is not None:
            data_manager = self.backend("DataManager")
            if data_manager is None:
                return
            lista = [(r['descricao_original'], r['PMIB_CRIADO'], r['PDM_COM_REVISAO'])
                     for _, r in self.df_resumo_final.iterrows()]

            salvo_com_sucesso = False
            while not salvo_com_sucesso:
                ok, msg = data_manager.atualizar_excel_final(self.file_path_excel, "Lista de Materiais", lista)

                if ok:
                    QMessageBox.information(self, "Sucesso", f"Planilha atualizada!\n{msg}")
                    self.log(f"✅ Excel salvo com sucesso: {msg}")
                    salvo_com_sucesso = True
                elif "ABERTO" in msg.upper() or "PERMISSION" in msg.upper():
                    # Erro de permissão (arquivo aberto): o `askretrycancel` de lá.
                    botoes = QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel
                    resposta = QMessageBox.warning(
                        self, "Arquivo Aberto",
                        "O arquivo Excel está ABERTO ou bloqueado.\n\nPor favor, FECHE o arquivo "
                        "_STATUS_PMIB no Excel e clique em 'Repetir' para tentar salvar novamente.",
                        botoes)
                    if resposta != QMessageBox.StandardButton.Retry:  # "Cancelar" ou o "X"
                        self.log("⚠️ Salvamento cancelado pelo usuário. Os dados não foram gravados no Excel.")
                        break
                else:
                    # Outro erro inesperado (ex: aba não encontrada). Interrompe o loop.
                    QMessageBox.critical(self, "Erro ao Salvar", msg)
                    self.log(f"❌ Erro ao salvar Excel: {msg}")
                    break
        else:
            QMessageBox.warning(self, "Aviso", "Não há dados processados para salvar.")

    def resetar_processo(self) -> None:
        """Limpa todo o estado do módulo para iniciar um novo lote limpo."""
        # 1. Limpa variáveis de backend
        self.file_path_excel = None
        self.file_path_pdm = None
        self.df_data_completo = None
        self.df_data_selecionado = None
        self.df_processed = None
        self.df_resumo_final = None
        if self.bot:
            try:
                self.bot.driver.quit()
            except Exception:  # noqa: BLE001 -- navegador já fechado
                pass
            self.bot = None

        # 2. Reseta a UI visualmente
        self.lbl_status.setText("Aguardando...")
        _cor_rotulo(self.lbl_status, COR_ROTULO_APOIO)
        _pintar(self.btn_pmib, CINZA, CINZA_HOVER)

        self.lbl_status_pdm.setText("")
        _cor_rotulo(self.lbl_status_pdm, COR_ROTULO_APOIO)
        if not self.chk_pular.isChecked():
            _pintar(self.btn_pdm, CINZA, CINZA_HOVER)

        self.entry_projeto.clear()

        blocos.modo_indeterminado(self.progress, False)
        self.progress.definir(0)  # Zera a barrinha

        self.console.clear()
        self.log("Sistema limpo. Pronto para iniciar um novo lote.")

        # 3. Retorna os botões da Criação
        self.btn_run_ai.setEnabled(False)
        self.btn_run_ai.setText("3. Analisar (IA)")
        self.btn_run_auto.setEnabled(False)
        _pintar(self.btn_run_auto, COLORS["primary"], COLORS["primary_hover"])
        self.btn_resumo.setEnabled(False)
        self.btn_save.setEnabled(False)

        # 4. Limpa as variáveis e visuais da Aba de Edição
        self.df_edicao_completo = None
        self.df_edicao_selecionado = None
        self.lbl_status_edicao.setText("Nenhum item selecionado.")
        _cor_rotulo(self.lbl_status_edicao, COR_ROTULO_APOIO)
        _pintar(self.btn_excel_edicao, CINZA, CINZA_HOVER)
        self.entry_novo_projeto.clear()
        self.progress_edicao.definir(0)
        self.btn_run_edicao.setEnabled(False)

    # ---------------------------------------------------------
    # FUNÇÕES DA ABA DE EDIÇÃO
    # ---------------------------------------------------------
    def selecionar_excel_edicao(self) -> None:
        data_manager = self.backend("DataManager")
        if data_manager is None:
            return
        path = file_dialogs.ask_open_file("cria_fichas.excel_edicao", "excel", filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        cols = ["DESCRIÇÃO", "CÓDIGO PMIB"]
        df, cod_sug, erro = data_manager.carregar_planilha_inteligente(path, "Lista de Materiais", cols)
        if df is None:
            df, cod_sug, erro = data_manager.carregar_planilha_inteligente(path, 0, cols)
        if df is not None:
            # FILTRO INTELIGENTE: só as linhas que têm PMIB (não se edita item não criado)
            df_valido = df[df['CÓDIGO PMIB'].astype(str).str.strip() != ""]
            df_valido = df_valido.dropna(subset=['CÓDIGO PMIB'])

            if df_valido.empty:
                QMessageBox.warning(self, "Aviso", "Nenhum CÓDIGO PMIB encontrado nesta planilha. "
                                                   "Certifique-se de que as fichas já foram criadas.")
                return

            self.df_edicao_completo = df_valido.reset_index(drop=True)
            self.log(f"Aba Edição: Carregado {len(self.df_edicao_completo)} itens válidos com PMIB.")

            # Aproveita a mesma inteligência de sugerir o projeto
            if cod_sug:
                self.entry_novo_projeto.setText(cod_sug)

            JanelaSelecao(self, self.df_edicao_completo, self.pos_selecao_edicao)
        else:
            QMessageBox.critical(self, "Erro", erro)

    def pos_selecao_edicao(self, indices) -> None:
        self.df_edicao_selecionado = self.df_edicao_completo.iloc[indices].copy()
        qtd = len(self.df_edicao_selecionado)

        self.log(f"Aba Edição: Selecionado {qtd} fichas para editar.")
        self.lbl_status_edicao.setText(f"{qtd} fichas selecionadas")
        _cor_rotulo(self.lbl_status_edicao, COLORS["accent"])
        _pintar(self.btn_excel_edicao, COLORS["primary"], CINZA_HOVER)
        self.btn_run_edicao.setEnabled(qtd > 0)

    def run_edicao_thread(self) -> None:
        if self._robo_ocupado():
            return
        novo_projeto = self.entry_novo_projeto.text().strip()
        if not novo_projeto:
            QMessageBox.warning(self, "Aviso", "Preencha o Novo Código do Projeto.")
            return

        if self.df_edicao_selecionado is None or self.df_edicao_selecionado.empty:
            QMessageBox.warning(self, "Aviso", "Selecione ao menos uma ficha no Excel para editar.")
            return

        # Extrai automaticamente a lista de PMIBs da coluna do DataFrame
        lista_pmibs = self.df_edicao_selecionado['CÓDIGO PMIB'].apply(
            lambda x: str(x).strip() if pd.notna(x) else "").tolist()
        # Filtro extra de segurança (remove eventuais 'nan')
        lista_pmibs = [p for p in lista_pmibs if p and p.lower() != 'nan']

        automacao = self.backend("AutomacaoPMIB")
        if automacao is None:
            return
        self._iniciar_robo(self._edicao_worker, lista_pmibs, novo_projeto, automacao,
                           botao=self.btn_run_edicao)

    def _edicao_worker(self, lista_pmibs, novo_projeto, automacao) -> None:
        bot = automacao()
        self.bot = bot  # o "Limpar" fecha o navegador por aqui
        try:
            bot.iniciar_driver()
            bot.abrir_portal(URL_LISTA)
            # A instrução da página PRINCIPAL; o worker espera o "Continuar".
            self.pausar_e_esperar(MSG_LOGIN_PAGINA_PRINCIPAL)

            self.log(f"Iniciando Edição em Massa de {len(lista_pmibs)} fichas...")

            for idx, pmib in enumerate(lista_pmibs):
                interface.na_interface(self._definir_progresso, self.progress_edicao,
                                       (idx + 1) / len(lista_pmibs))
                self.log(f"Editando PMIB [{idx + 1}/{len(lista_pmibs)}]: {pmib}...")

                status, msg = bot.atualizar_projeto_em_massa(pmib, novo_projeto)

                if status == "SUCESSO":
                    self.log(f" -> ✅ SUCESSO: Projeto do {pmib} atualizado.")
                else:
                    # Registra e tenta o próximo, para não travar o lote
                    self.log(f" -> ❌ ERRO no {pmib}: {msg}")

            self.log("Edição em massa concluída!")
            # Espera o OK, como o showinfo de lá: o navegador fecha e o botão
            # volta depois que a pessoa leu.
            self.avisar("Concluído", "Processo de edição em massa finalizado. Verifique o log.", esperar=True)

        except Exception as e:  # noqa: BLE001 -- vira log, como lá
            self.log(f"Erro Fatal na Edição: {e}")
        finally:
            try:
                bot.driver.quit()
            except Exception:  # noqa: BLE001 -- navegador já fechado
                pass
