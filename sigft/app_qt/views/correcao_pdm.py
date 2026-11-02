"""Tela "Correção de PDM" na interface Qt -- trocar ou atualizar o PDM sem perder as características.

Mesma tela da interface antiga (`sigft/app/views/correcao_pdm.py`, removida em 2026-10-15) (leia a docstring de lá: o
portal apaga TODAS as características na troca; o robô fotografa, troca e repõe
o que couber). Continua BLOQUEADA no menu (`catalogo.TELAS_BLOQUEADAS`): o port
existe para estar pronto quando ela for liberada, depois do roteiro
`docs/ROTEIRO_CORRECAO_PDM.md` numa máquina com o portal.

A tela é FINA, como lá: planilha, prévia e ações em massa em
`services/correcao_pdm_planilha.py`; o fluxo do portal em
`services/correcao_pdm.py`. O que muda é COMO o worker fala com a interface:

* a thread é a de `iniciar_tarefa` (comum, não daemon: o "X" da janela pergunta
  antes de matar um robô que está trocando PDM; lá era daemon);
* barra de progresso e a pergunta do relatório vão por `interface.na_interface`;
* os dois interruptores são lidos no mesmo momento de lá (depois do login),
  mas na thread da interface (`_na_interface_e_esperar`), não pelo worker.
"""
from __future__ import annotations

import weakref

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMessageBox, QVBoxLayout, QWidget

from sigft.app import theme
from sigft.app.idioma import marcar, t
from sigft.app.textos_dialogos import MSG_LOGIN_NOVA_FICHA
from sigft.app_qt import estilo, file_dialogs, interface
from sigft.app_qt.views.janelas import JanelaEscolherPDM
from sigft.app_qt.widgets import blocos, controles, dialogos_selecao
from sigft.app_qt.widgets.atividade import ROTULO_FICHA
from sigft.app_qt.widgets.como_funciona import instalar_como_funciona
from sigft.app_qt.widgets.arrastar import Arrastavel
from sigft.app_qt.widgets.module_frame import ModuleFrame
from sigft.core import pdm_catalogo
from sigft.services import correcao_pdm as correcao_svc
from sigft.services import correcao_pdm_planilha as planilha_svc

URL_LISTA_DE_FICHAS = "https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList"

# Os nomes vão em `marcar` e são traduzidos onde a tabela é montada (`t(c)`):
# ninguém procura a coluna pelo nome, só pela posição (2026-10-22).
COLUNAS = (
    (marcar("Ficha"), 150),
    (marcar("Descrição"), 250),
    (marcar("PDM atual"), 260),
    (marcar("PDM novo"), 260),
    (marcar("Prévia"), 230),
)

# O cinza escrito à mão nos botões de lá é a variante "cinza"; o vermelho do
# "Parar", a "perigo".

# A grade da tela de lá: conteúdo com peso 3, console com peso 1 e
# `sticky="ew"` -- o console NÃO estica: fica com 150 px, centrado na linha
# dele, e a linha leva 1/4 da altura que sobra. A sobra conta a partir da
# altura PEDIDA do conteúdo, em que a tabela entra com a do ttk.Treeview
# padrão (10 linhas de 20 + cabeçalho de 20 + 1 de borda = 221, medido).
PESO_CONTEUDO, PESO_CONSOLE = 3, 1
ALTURA_PEDIDA_TABELA = 221
LARGURA_ROTULO_ACOES = 148


class _ReaplicaProgresso(QObject):
    """A barra estica com a tela (`fill="x"`): o trecho cheio do CTkProgressBar
    depende da largura (pontas redondas por dentro), então é refeito a cada
    mudança de tamanho."""

    def __init__(self, tela: ModuloCorrecaoPDM) -> None:
        super().__init__(tela)
        # Fraca: a tela já segura este filtro (filho dela); a referência forte
        # fechava um ciclo, como o do puxador do console (`widgets/fraco.py`).
        self._ref_tela = weakref.ref(tela)

    def eventFilter(self, objeto, evento) -> bool:  # noqa: N802 -- nome do Qt
        tela = self._ref_tela()
        if tela is not None and evento.type() == QEvent.Type.Resize:
            blocos.definir_progresso(objeto, tela._fracao)
        return False


def _rotulo(texto: str, papel: str = "legenda") -> QLabel:
    """CTkLabel de uma linha (28 de altura, fonte 13), no papel de texto pedido."""
    r = QLabel(texto)
    r.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    r.setFixedHeight(blocos.ALTURA_MINIMA_ROTULO)
    r.setStyleSheet("QLabel { font-size: 13px; background: transparent; }")
    _pintar(r, papel)
    return r


def _pintar(rotulo: QLabel, papel: str | None) -> None:
    """O `configure(text_color=...)`: o papel de texto da folha."""
    estilo.definir_papel(rotulo, papel)


def _botao(texto: str, largura: int, **kw):
    """CTkButton de 28 com o `width` de lá (o texto largo alarga). Enter não o
    aperta: o Tk não ligava tecla nenhuma nesta tela."""
    b = blocos.botao(texto, altura=28, largura_minima=largura, **kw)
    b.setAutoDefault(False)
    b.setDefault(False)
    return b


class ModuloCorrecaoPDM(ModuleFrame):
    # Arrastar arquivo do Explorer para os botões (2026-10-21, etapa 1b).
    ARRASTAVEIS = (
        Arrastavel("btn_status", "correcao_pdm.status_pmib", (".xlsx", ".xlsm")),
        Arrastavel("btn_catalogo", "correcao_pdm.sam_gm", (".xlsx", ".xlsm")),
    )
    def __init__(self, parent=None, controller=None) -> None:
        self.fichas = []          # list[FichaParaCorrigir]
        self.catalogo = None
        self.automacao = None
        self._fracao = 0.0
        self._janela_pdm = None
        super().__init__(parent, controller, titulo=t("Correção de PDM"),
                         altura_console=theme.ALTURA_CONSOLE)

    # -- montagem ----------------------------------------------------------
    def _build_ui(self) -> None:
        self._montar_cabecalho()
        instalar_como_funciona(self, "CorrecaoPDM")
        lay = self.content_layout
        lay.setSpacing(0)

        # --- arquivos: o cartão (`blocos.cartao`), linha com padx=15/pady=12
        quadro = QFrame(objectName="cartao")
        linha = QHBoxLayout(quadro)
        linha.setContentsMargins(15, 12, 15, 12)
        linha.setSpacing(0)
        self.btn_status = _botao(t("Selecionar _STATUS_PMIB"), 200, variante="cinza", tamanho_fonte=12)
        self.btn_status.clicked.connect(self._sel_status)
        self.lbl_status = _rotulo(t("Não selecionado"))
        self.btn_catalogo = _botao(t("Planilha de PDMs (opcional)"), 210, variante="cinza", tamanho_fonte=12)
        self.btn_catalogo.clicked.connect(self._sel_catalogo)
        self.lbl_catalogo = _rotulo(t("sem catálogo"))
        linha.addWidget(self.btn_status)
        linha.addSpacing(10)                  # rótulo padx=10
        linha.addWidget(self.lbl_status)
        linha.addSpacing(10 + 20)             # padx=10 do rótulo + padx=(20, 0) do botão
        linha.addWidget(self.btn_catalogo)
        linha.addSpacing(10)
        linha.addWidget(self.lbl_catalogo)
        linha.addStretch()
        lay.addWidget(quadro)
        lay.addSpacing(10)                    # pady=(0, 10)

        # --- ações em massa
        acoes = QHBoxLayout()
        acoes.setContentsMargins(0, 0, 0, 0)
        acoes.setSpacing(0)
        self.rotulo_acoes = QLabel(t("Nas fichas selecionadas:"))
        self.rotulo_acoes.setFixedHeight(blocos.ALTURA_MINIMA_ROTULO)
        # 148 medidos lá e ~136 no Qt: a 12 px o negrito sintetizado do Qt não
        # alarga as letras, e o do Tk soma ~0,5 px por letra (13 px nas 24 do
        # texto). Sem isto os três botões chegavam 12 px para a esquerda.
        self.rotulo_acoes.setMinimumWidth(LARGURA_ROTULO_ACOES)
        self.rotulo_acoes.setStyleSheet(
            "QLabel { font-size: 12px; font-weight: bold; background: transparent; }")
        self.btn_so_revisao = _botao(t("Só atualizar a revisão"), 170, variante="primario")
        self.btn_so_revisao.clicked.connect(self._acao_so_revisao)
        self.btn_escolher_pdm = _botao(t("Escolher PDM..."), 140, variante="cinza")
        self.btn_escolher_pdm.clicked.connect(self._acao_escolher_pdm)
        self.btn_limpar = _botao(t("Limpar"), 90, variante="cinza")
        self.btn_limpar.clicked.connect(self._acao_limpar)
        acoes.addWidget(self.rotulo_acoes)
        acoes.addSpacing(10 + 4)              # padx=(0, 10) do rótulo + padx=4 do botão
        acoes.addWidget(self.btn_so_revisao)
        acoes.addSpacing(8)                   # padx=4 de cada lado
        acoes.addWidget(self.btn_escolher_pdm)
        acoes.addSpacing(8)
        acoes.addWidget(self.btn_limpar)
        acoes.addStretch()
        lay.addLayout(acoes)
        lay.addSpacing(6)                     # pady=(0, 6)

        # --- a tabela (ttk.Treeview com a barra vertical empacotada ao lado)
        self.tabela = dialogos_selecao.tabela_ttk([(t(c), largura, "w") for c, largura in COLUNAS],
                                                  barra_horizontal=False)
        lay.addWidget(self.tabela, 1)
        lay.addSpacing(10)                    # rodapé pady=(10, 0)

        # --- rodapé
        rodape = QHBoxLayout()
        rodape.setContentsMargins(0, 0, 0, 0)
        rodape.setSpacing(0)
        self.chk_apagar_vazias = controles.Interruptor(t("Apagar as que ficarem em branco"))
        self.chk_apagar_vazias.setChecked(True)
        self.chk_conferir = controles.Interruptor(t("Conferir cada ficha antes de salvar"))
        self.btn_parar = _botao(t("Parar"), 90, variante="perigo")
        self.btn_parar.clicked.connect(self._parar)
        self.btn_rodar = _botao(t("INICIAR CORREÇÃO"), 190, variante="primario",
                                tamanho_fonte=13, negrito=True)
        self.btn_rodar.clicked.connect(self._rodar)
        rodape.addWidget(self.chk_apagar_vazias)
        rodape.addSpacing(20)                 # padx=20
        rodape.addWidget(self.chk_conferir)
        rodape.addStretch()
        rodape.addWidget(self.btn_parar)
        rodape.addSpacing(8)                  # padx=8
        rodape.addWidget(self.btn_rodar)
        lay.addLayout(rodape)
        lay.addSpacing(8)                     # barra pady=(8, 0)

        self.progress = blocos.barra_progresso(altura=8)
        self.progress.installEventFilter(_ReaplicaProgresso(self))
        lay.addWidget(self.progress)

        self._montar_faixa_do_console()

    def _montar_cabecalho(self) -> None:
        """Título e, à direita dele, o subtítulo cinza (dois `pack(side="left")`)."""
        cabecalho = self.header.layout()
        cabecalho.removeWidget(self.label_titulo)
        linha = QHBoxLayout()
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(0)
        linha.addWidget(self.label_titulo)
        self.label_subtitulo = _rotulo(t("  troca o PDM da ficha e repõe as "
                                         "características que o PDM novo também tem"))
        linha.addWidget(self.label_subtitulo)
        linha.addStretch()
        cabecalho.addLayout(linha)

    def _montar_faixa_do_console(self) -> None:
        """O console dentro de uma faixa: a linha da grade de lá, em que ele fica centrado."""
        raiz = self.layout()
        raiz.removeWidget(self.console)
        self.faixa_console = QWidget()
        faixa = QVBoxLayout(self.faixa_console)
        faixa.setContentsMargins(0, 0, 0, 0)
        faixa.addWidget(self.console, 0, Qt.AlignmentFlag.AlignVCenter)
        raiz.addWidget(self.faixa_console)
        self.faixa_console.setFixedHeight(theme.ALTURA_CONSOLE)

    def _alvos_do_console(self) -> list:
        # A barrinha muda a faixa E o console (que tem altura fixa dentro dela).
        return [self.faixa_console, self.console]

    def _console_voltou_ao_padrao(self) -> None:
        self._repartir_altura()

    def resizeEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        super().resizeEvent(evento)
        self._repartir_altura()

    def _repartir_altura(self) -> None:
        """A sobra de altura repartida como a grade do Tk (pesos 3 e 1)."""
        if self.altura_console_escolhida is not None:
            return   # a pessoa arrastou a barrinha: a altura é a dela (ModuleFrame)
        raiz = self.layout()
        margens = raiz.contentsMargins()
        disponivel = (self.height() - margens.top() - margens.bottom()
                      - self.header.sizeHint().height() - 2 * raiz.spacing())
        pedido = (self.content_layout.sizeHint().height() - self.tabela.sizeHint().height()
                  + ALTURA_PEDIDA_TABELA)
        sobra = max(0, disponivel - pedido - theme.ALTURA_CONSOLE)
        altura = theme.ALTURA_CONSOLE + sobra * PESO_CONSOLE // (PESO_CONTEUDO + PESO_CONSOLE)
        if self.faixa_console.height() != altura or self.faixa_console.minimumHeight() != altura:
            self.faixa_console.setFixedHeight(altura)

    # -- arquivos ----------------------------------------------------------
    def _sel_status(self) -> None:
        caminho = file_dialogs.ask_open_file(
            "correcao_pdm.status_pmib", "excel",
            titulo=t("Selecione o _STATUS_PMIB"),
            filetypes=[("Excel", "*.xlsx *.xlsm")])
        if not caminho:
            return
        try:
            self.fichas = planilha_svc.ler_fichas_do_arquivo(caminho)
        except Exception as erro:  # noqa: BLE001 -- planilha do usuário
            QMessageBox.critical(self, t("Erro"), t("Não consegui ler a planilha:\n{erro}", erro=erro))
            return

        self.lbl_status.setText(t("{n} ficha(s)", n=len(self.fichas)))
        _pintar(self.lbl_status, "ok")
        if not self.fichas:
            self.log("Nenhuma ficha encontrada. Confira se a aba é a "
                     "'Lista de Materiais' e se há a coluna CÓDIGO PMIB.")
        self._redesenhar()

    def _sel_catalogo(self) -> None:
        caminho = file_dialogs.ask_open_file(
            "correcao_pdm.sam_gm", "excel",
            titulo=t("Selecione a planilha de PDMs"),
            filetypes=[("Excel", "*.xlsx *.xlsm")])
        if not caminho:
            return
        try:
            self.catalogo = pdm_catalogo.carregar(caminho)
        except Exception as erro:  # noqa: BLE001
            QMessageBox.critical(self, t("Erro"), t("Não consegui ler o catálogo:\n{erro}", erro=erro))
            return
        self.lbl_catalogo.setText(t("{n} PDMs", n=len(self.catalogo)))
        _pintar(self.lbl_catalogo, "ok")
        self._redesenhar()

    # -- tabela ------------------------------------------------------------
    def _redesenhar(self) -> None:
        self.tabela.clear()
        for posicao, ficha in enumerate(self.fichas):
            dialogos_selecao.linha_ttk(
                self.tabela,
                (ficha.pmib, ficha.descricao, ficha.pdm_atual, ficha.pdm_novo,
                 planilha_svc.previa(self.catalogo, ficha.pdm_atual, ficha.pdm_novo)),
                chave=str(posicao))

    def _selecionadas(self):
        """As fichas marcadas, ou TODAS quando não há seleção (ver a tela de lá)."""
        marcadas = [self.tabela.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)
                    for i in range(self.tabela.topLevelItemCount())
                    if self.tabela.topLevelItem(i).isSelected()]
        if not marcadas:
            return list(self.fichas)
        return [self.fichas[int(x)] for x in marcadas]

    def _acao_so_revisao(self) -> None:
        alvo = self._selecionadas()
        sem_pdm = 0
        for ficha in alvo:
            codigo = planilha_svc.so_a_revisao(ficha.pdm_atual)
            if not codigo:
                sem_pdm += 1
                continue
            ficha.pdm_novo = codigo
        self._redesenhar()
        self.log(f"Só atualizar a revisão: {len(alvo) - sem_pdm} ficha(s).")
        if sem_pdm:
            self.log(f"   {sem_pdm} ficha(s) sem PDM na planilha ficaram de "
                     f"fora: não há código para copiar.")

    def _acao_escolher_pdm(self) -> None:
        if self.catalogo is None:
            QMessageBox.information(
                self, t("Catálogo"),
                t("Selecione antes a planilha de PDMs: é dela que sai a busca."))
            return
        # Já aberta: traz para a frente em vez de abrir outra por cima.
        if self._janela_pdm is not None and self._janela_pdm.isVisible():
            self._janela_pdm.raise_()
            self._janela_pdm.activateWindow()
            return
        alvo = self._selecionadas()
        if not alvo:
            return
        self._janela_pdm = JanelaEscolherPDM(self, self.catalogo)
        try:
            escolha = self._janela_pdm.esperar()   # o `wait_window` de lá
        finally:
            self._janela_pdm = None
        if escolha is None:
            return
        for ficha in alvo:
            ficha.pdm_novo = escolha.completo
        self._redesenhar()
        self.log(f"{escolha.completo} aplicado a {len(alvo)} ficha(s).")

    def _acao_limpar(self) -> None:
        for ficha in self._selecionadas():
            ficha.pdm_novo = ""
        self._redesenhar()

    # -- a rodada ----------------------------------------------------------
    def _rodar(self) -> None:
        lote = planilha_svc.lote(self.fichas)
        if not lote:
            QMessageBox.information(
                self, t("Nada a fazer"),
                t("Nenhuma ficha tem PDM novo. Use 'Só atualizar a revisão' ou "
                  "'Escolher PDM...' antes."))
            return
        # Operação destrutiva: o Enter fica no "Não" (lá o askyesno o punha no "Sim").
        if not self.perguntar_sim_nao(
                t("Confirmar"),
                t("{n} ficha(s) vão ter o PDM trocado no portal.\n\n"
                  "O portal apaga as características técnicas na troca. O robô "
                  "fotografa antes e repõe o que couber, e o que não voltar sai "
                  "no relatório.\n\nSeguir?", n=len(lote)), padrao_sim=False):
            return
        self.iniciar_tarefa(self._worker, lote, botao=self.btn_rodar)

    def _parar(self) -> None:
        if self.automacao:
            self.automacao.solicitar_parada()
            self.log("Parada pedida. Termino a ficha atual e paro.")

    def _ler_interruptores(self) -> tuple[bool, bool]:
        return self.chk_conferir.isChecked(), self.chk_apagar_vazias.isChecked()

    def _worker(self, lote) -> None:
        self.automacao = correcao_svc.AutomacaoCorrecaoPDM()
        try:
            self.automacao.iniciar()
            self.automacao.abrir_portal(URL_LISTA_DE_FICHAS)
            self.pausar_e_esperar(t(MSG_LOGIN_NOVA_FICHA))

            conferir, apagar_vazias = self._na_interface_e_esperar(self._ler_interruptores)
            resultados = correcao_svc.corrigir_lote(
                self.automacao.portal, lote,
                callback_log=self.log,
                callback_pause=self._pausa_de_conferencia if conferir else None,
                callback_progress=self._progresso,
                apagar_vazias=apagar_vazias)

            for linha in correcao_svc.relatorio_do_lote(resultados):
                self.log(linha)
            interface.na_interface(self._oferecer_relatorio, resultados)
        except Exception as erro:  # noqa: BLE001 -- o worker não pode morrer calado
            self.log(f"[Erro] {type(erro).__name__}: {erro}")
        finally:
            self.automacao.fechar()

    def _progresso(self, atual, total, item=None) -> None:
        interface.na_interface(self._definir_progresso, (atual / total) if total else 0)
        self.informar_progresso(atual, total, ROTULO_FICHA)

    def _definir_progresso(self, fracao: float) -> None:
        self._fracao = fracao
        blocos.definir_progresso(self.progress, fracao)

    def _pausa_de_conferencia(self, pmib) -> None:
        self.pausar_e_esperar(t("Confira a ficha {pmib} no portal antes de salvar.", pmib=pmib))

    def _oferecer_relatorio(self, resultados) -> None:
        """Salva o relatório num arquivo, se o usuário quiser (no console ele rola e some)."""
        # Enter = "Sim", como o askyesno de lá: recusar sem querer perde a lista do que não voltou.
        if not self.perguntar_sim_nao(t("Relatório"), t("Salvar o relatório num arquivo?"), padrao_sim=True):
            return
        caminho = file_dialogs.ask_save_file(
            "correcao_pdm.relatorio", "texto", titulo=t("Salvar relatorio"),
            defaultextension=".txt", filetypes=[(t("Texto"), "*.txt")])
        if not caminho:
            return
        try:
            with open(caminho, "w", encoding="utf-8") as arquivo:
                arquivo.write("\n".join(correcao_svc.relatorio_do_lote(resultados)))
        except OSError as erro:
            QMessageBox.critical(self, t("Erro"), t("Não consegui salvar:\n{erro}", erro=erro))
            return
        self.log(f"Relatório salvo em {caminho}")
