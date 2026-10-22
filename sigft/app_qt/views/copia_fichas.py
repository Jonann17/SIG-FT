"""Tela "Cópia de Fichas" (fichas duplicadas) na interface Qt.

Mesma tela da interface antiga (`sigft/app/views/copia_fichas.py`, removida em 2026-10-15): identifica as fichas
duplicadas a partir do `_STATUS_PMIB`, deixa a pessoa escolher e revisar os
pares original/alvo, e copia o conteúdo de uma para a outra no portal (o robô
novo, Playwright, de `services/duplicadas_robo.py`).

Layout = o ATUAL da tela antiga (depois do CP 5.5, que tirou o robô Selenium e o
"Salvar COMPLETO"): cartão 1 com o botão do `_STATUS_PMIB` e o rótulo; cartão
2 com os dois botões, o interruptor do log de auditoria e a barra de progresso.

O que muda é só COMO as threads falam com a interface: lá `self.after(0, ...)`
(disciplina) e a leitura da caixa do log de auditoria de dentro do worker;
aqui `iniciar_tarefa`/`interface.na_interface` (mecanismo), a caixa lida no
clique, e a pausa de login por `pausar_e_esperar` (a janela nasce na thread da
interface e o worker espera).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy

from sigft import config as sigft_config
from sigft.app.idioma import t
from sigft.app.textos_dialogos import MSG_LOGIN_LOTE
from sigft.app_qt import estilo, file_dialogs, interface
from sigft.app_qt.views.janelas import JanelaRevisaoEdicao, JanelaSelecaoDuplicadas
from sigft.app_qt.widgets import blocos, controles
from sigft.app_qt.widgets.arrastar import Arrastavel
from sigft.app_qt.widgets.module_frame import MARGEM_DA_TELA, ModuleFrame
from sigft.services import duplicadas

# O grid da tela antiga: linha 1 (quadro rolável, weight=3) e linha 2 (console,
# weight=1). O Tk dá a cada linha o que ela PEDE e reparte a sobra (ou a
# falta) pelos pesos -- não a altura toda, como o stretch do Qt. Pedidos
# medidos na interface antiga: CTkScrollableFrame 212, CTkTextbox 200.
PEDIDO_ROLAVEL, PEDIDO_CONSOLE = 212, 200
PESO_ROLAVEL, PESO_CONSOLE = 3, 1
# O CTkScrollableFrame: conteúdo 6 px dentro do quadro, barra 1 px antes da borda.
RECUO_ROLAGEM = 6


def _rotulo(texto: str, *, tamanho: int = 13, negrito: bool = False, papel: str | None = None):
    """CTkLabel de uma linha, anchor="w", 28 px de altura."""
    r = blocos.rotulo(texto, tamanho=tamanho, negrito=negrito, papel=papel, alinhar="esquerda")
    r.setWordWrap(False)
    r.setFixedHeight(blocos.ALTURA_MINIMA_ROTULO)
    return r


# =============================================================================
# MÓDULO 7: UPLOAD DE FICHAS DUPLICADAS (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloCopiaFichas(ModuleFrame):
    # Arrastar arquivo do Explorer para o botão (2026-10-21, etapa 1b).
    ARRASTAVEIS = (Arrastavel("btn_status", "copia_fichas.status_pmib", (".xlsx", ".xlsm")),)
    def __init__(self, parent=None, controller=None) -> None:
        # Variáveis de Estado
        self.caminho_status = None
        self.fila_completa: list[dict] = []
        self.fila_selecionada: list[dict] = []
        # Duplicadas encontradas que o robô NÃO consegue processar (sem ficha
        # original ou sem código do material). Ficam fora da fila, mas contadas
        # e explicadas -- ver `_worker_leitura_excel`.
        self.impedidas = []
        self.janela_selecao = None
        # Um robô por vez (como `_upload_comum` e `cria_fichas`): liga e
        # desliga só na thread da interface, e segura os botões que a seleção
        # e a leitura religariam no meio do lote.
        self._robo_ativo = False
        super().__init__(parent, controller, titulo=t("Módulo: Cópia de Fichas PMIB"), altura_console=None)
        # Lá a tela não é o ModuleFrame: header pady=10, quadro rolável pady=0,
        # console pady=10, dentro do padx/pady=20 do `show_frame`. Os pady
        # vizinhos SOMAM: 10 entre header e quadro, 10 entre quadro e console.
        raiz = self.layout()
        raiz.setContentsMargins(MARGEM_DA_TELA + 20, MARGEM_DA_TELA + 10,
                                MARGEM_DA_TELA + 20, MARGEM_DA_TELA + 10)
        raiz.setSpacing(0)
        raiz.insertSpacing(1, 10)                       # header (…, 10) + quadro (0, …)
        raiz.insertSpacing(3, 10)                       # quadro (…, 0) + console (10, …)

    # --- montagem -------------------------------------------------------------
    def _build_ui(self) -> None:
        # Container Principal: CTkScrollableFrame transparente, com a barra
        # sempre à vista (a interface antiga reserva a faixa mesmo sem nada para rolar; sem
        # ela, os cartões ficariam 11 px mais largos). A barra da interface antiga fica 1 px
        # antes da borda direita (x 946..962 numa área que acaba em 963), e o
        # conteúdo vai até ela (900 = 923 - 6 - 17).
        self.area, corpo = blocos.area_rolavel(self.content_layout, margem=RECUO_ROLAGEM,
                                               barra_sempre_visivel=True)

        # --- ETAPA 1: CONFIGURAÇÃO ---
        corpo.addSpacing(10)                            # frm_config: pady=10
        config = self._cartao(corpo, fim=10)
        self.cartao_config = config.parentWidget()
        self.rotulo_etapa1 = _rotulo(t("1. Selecionar Arquivo Base"), tamanho=16, negrito=True,
                                     papel="destaque")
        config.addWidget(self.rotulo_etapa1)
        config.addSpacing(20)                           # título (…, 10) + f_pmib (10, …)

        linha = QHBoxLayout()
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(0)
        self.btn_status = blocos.botao(t("Selecionar _STATUS_PMIB"), variante="cinza", largura=250, altura=28)
        self.btn_status.clicked.connect(self.selecionar_excel_pmib)
        linha.addWidget(self.btn_status)
        linha.addSpacing(15)                            # lbl_status: padx=15
        self.lbl_status = _rotulo(t("Aguardando seleção..."), papel="legenda")
        linha.addWidget(self.lbl_status)
        linha.addStretch()
        config.addLayout(linha)

        # --- ETAPA 2: AÇÕES ---
        corpo.addSpacing(20)                            # frm_config (…, 10) + frm_action (10, …)
        acoes = self._cartao(corpo, fim=15)
        self.cartao_acoes = acoes.parentWidget()
        self.rotulo_etapa2 = _rotulo(t("2. Execução"), tamanho=16, negrito=True, papel="destaque")
        acoes.addWidget(self.rotulo_etapa2)
        acoes.addSpacing(20)                            # título (…, 10) + grade (10, …)

        # Duas colunas iguais (uniform="cols"), padx=(0, 5) e (5, 0).
        grade = QHBoxLayout()
        grade.setContentsMargins(0, 0, 0, 0)
        grade.setSpacing(10)
        self.btn_resumo = blocos.botao(t("1. Revisar / Editar Fichas"), variante="cinza", altura=40)
        self.btn_resumo.clicked.connect(self.abrir_revisao)
        # CP 5.5: aqui havia TRÊS botões -- "2. Iniciar Robô Web" (o robô em
        # Selenium), "3. Salvar 'COMPLETO' no Excel" e este. Os dois primeiros
        # saíram com o Selenium; quem marca o COMPLETO agora é
        # `duplicadas_robo.marcar_status_na_planilha`, seção por seção, e o
        # robô já a chama sozinho no fim do lote.
        self.btn_robo_novo = blocos.botao(t("2. Iniciar Robô Web"), variante="primario", altura=40)
        self.btn_robo_novo.clicked.connect(self.run_robo_novo_thread)
        for b in (self.btn_resumo, self.btn_robo_novo):
            b.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            b.setEnabled(False)
            grade.addWidget(b, 1)
        acoes.addLayout(grade)
        acoes.addSpacing(18)                            # grade (…, 10) + interruptor (8, …)

        # Log de auditoria (2026-08-18): ligado, grava em `logs/` TUDO que
        # aparece no console mais o HTML de cada seção que o robô visita. O
        # HTML vai só para o arquivo; o console continua legível.
        self.switch_auditoria = controles.Interruptor(
            t("Gravar log de auditoria (com a estrutura das telas)"))
        self.switch_auditoria.setChecked(True)
        acoes.addWidget(self.switch_auditoria, 0, Qt.AlignmentFlag.AlignLeft)
        acoes.addSpacing(15)                            # interruptor (…, 0) + barra (15, …)

        # Progresso: CTkProgressBar (a cor é a da folha), pack(fill="x", pady=15).
        self.progress = blocos.barra_progresso(barra=blocos.BarraDeProgresso())
        self.progress.definir(0)
        acoes.addWidget(self.progress)

        corpo.addSpacing(10)                            # frm_action: pady=10

    @staticmethod
    def _cartao(corpo, *, fim: int):
        """O cartão (`blocos.cartao`): peças com padx=15, título com pady 10."""
        layout = blocos.cartao(corpo)
        layout.setContentsMargins(15, 10, 15, fim)
        layout.setSpacing(0)
        return layout

    def resizeEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        self._repartir_altura()
        super().resizeEvent(evento)

    def _console_voltou_ao_padrao(self) -> None:
        self._repartir_altura()

    def _repartir_altura(self) -> None:
        """Quadro rolável × console como o grid do Tk: cada um com o que pede,
        a sobra repartida 3:1 (o Tk trunca a parte do quadro; o resto é do console)."""
        if self.altura_console_escolhida is not None:
            return   # a pessoa arrastou a barrinha: a altura é a dela (ModuleFrame)
        margens = self.layout().contentsMargins()
        disponivel = (self.height() - margens.top() - margens.bottom()
                      - self.header.sizeHint().height() - 10 - 10)
        sobra = disponivel - PEDIDO_ROLAVEL - PEDIDO_CONSOLE
        rolavel = PEDIDO_ROLAVEL + int(sobra * PESO_ROLAVEL / (PESO_ROLAVEL + PESO_CONSOLE))
        self.console.setFixedHeight(max(disponivel - rolavel, 0))

    # =========================================================================
    # LÓGICA DE INTERFACE
    # =========================================================================
    def selecionar_excel_pmib(self) -> None:
        path = file_dialogs.ask_open_file("copia_fichas.status_pmib", "excel",
                                          filetypes=[("Excel", "*.xlsx;*.xlsm")])
        if not path:
            return
        self.caminho_status = path
        # A fila da planilha anterior não vai mais para o robô: sem isto,
        # "2. Iniciar Robô Web" seguia ligado com ela durante a leitura.
        self.fila_selecionada = []
        self.btn_resumo.setEnabled(False)
        self.btn_robo_novo.setEnabled(False)

        self.log("Lendo arquivo Excel, aguarde...")
        # O botão desliga NO CLIQUE e volta no fim da leitura, dê no que der.
        # Thread comum: ler o Excel é tarefa da pessoa (o "X" pergunta antes).
        self.iniciar_tarefa(self._worker_leitura_excel, path, botao=self.btn_status)

    def _worker_leitura_excel(self, caminho: str) -> None:
        # CP 6.2: quem identifica as duplicadas é `sigft/services/duplicadas.py`
        # (prefixo `PDM.9900.000` na coluna do PDM usado). As impedidas viram
        # log em vez de sumirem caladas.
        try:
            fichas, mensagem = duplicadas.localizar_duplicadas(
                caminho, callback_log=self.log)
            self.log(mensagem)

            self.impedidas = [f for f in fichas if not f.pronta_para_duplicar]
            for ficha in self.impedidas:
                self.log(f"   [Fora da fila] linha {ficha.linha} "
                         f"({ficha.pmib or 'sem código PMIB'}): falta "
                         f"{ficha.motivo_de_impedimento}.")

            # OBSERVAÇÕES sem código PMIB: a ficha ENTRA na fila (o texto pode
            # ser o código em outra grafia), mas com aviso. O botão
            # "1. Revisar / Editar Fichas" corrige à mão.
            for ficha in fichas:
                if ficha.pronta_para_duplicar and not ficha.original_e_codigo_pmib:
                    self.log(f"   [Atenção] linha {ficha.linha} ({ficha.pmib}): "
                             f"OBSERVAÇÕES não tem código PMIB -- o robô vai tentar "
                             f"com {ficha.ficha_original!r}. Confira em 'Revisar / Editar'.")

            # O robô precisa das duas pontas -- original e alvo. Sem elas a
            # ficha fica fora da fila, mas saiu no log acima com o motivo.
            self.fila_completa = [
                {
                    "descricao": ficha.descricao or "Sem Descrição",
                    "pmib_original": ficha.ficha_original,
                    "pmib_alvo": ficha.pmib,
                    "codigo_material": ficha.codigo_material,
                    "codigo_fornecedor": ficha.codigo_fornecedor,
                    "linha_excel": ficha.linha,
                }
                for ficha in fichas if ficha.pronta_para_duplicar
            ]
            interface.na_interface(self._pos_leitura_sucesso)
        except Exception as e:  # noqa: BLE001 -- vira log, como lá
            self.log(f"Falha na leitura: {e}")

    def _pos_leitura_sucesso(self) -> None:
        self.btn_status.setEnabled(not self._robo_ativo)
        # Lá: configure(fg_color=primary) -- aqui, a variante primária.
        estilo.definir_variante(self.btn_status, "primario")
        texto = t("Planilha carregada. Encontradas {n} duplicadas.", n=len(self.fila_completa))
        if self.impedidas:
            texto += t(" ({n} sem dados para o robô. Ver log.)", n=len(self.impedidas))
        self.lbl_status.setText(texto)
        self._pintar_status("ok")
        self.log(f"{len(self.fila_completa)} fichas identificadas como cópia.")

        if self.fila_completa:
            # Abre imediatamente a janela para selecionar quais processar
            self.janela_selecao = JanelaSelecaoDuplicadas(self, self.fila_completa, self._pos_selecao)

    def _pintar_status(self, papel: str | None) -> None:
        """O `configure(text_color=...)` do rótulo de status: o papel de texto."""
        estilo.definir_papel(self.lbl_status, papel)

    def _pos_selecao(self, selecionados) -> None:
        self.fila_selecionada = selecionados
        self.lbl_status.setText(t("{n} fichas na fila para processar.", n=len(self.fila_selecionada)))
        self.log(f"Fila final configurada com {len(self.fila_selecionada)} fichas.")

        ligado = bool(self.fila_selecionada) and not self._robo_ativo
        self.btn_resumo.setEnabled(ligado)
        self.btn_robo_novo.setEnabled(ligado)

    def abrir_revisao(self) -> None:
        if self.fila_selecionada:
            JanelaRevisaoEdicao(self, self.fila_selecionada)

    # =========================================================================
    # ROBÔ NOVO (Fase 6) — Playwright, sem uma linha de Selenium
    # =========================================================================
    def run_robo_novo_thread(self) -> None:
        if not self.fila_selecionada or self._robo_ativo:
            return
        self._robo_ativo = True
        # Os botões desligam AQUI, na thread da interface, e voltam no fim do
        # worker por `na_interface`.
        for botao in (self.btn_robo_novo, self.btn_resumo, self.btn_status):
            botao.setEnabled(False)
        # Tudo lido no clique -- a caixa, a fila e a planilha que o robô marca
        # no fim: o worker não toca widget nem lê o estado da tela.
        self.iniciar_tarefa(self._worker_robo_novo, self.switch_auditoria.isChecked(),
                            self._fichas_para_o_robo_novo(), self.caminho_status)

    def _fichas_para_o_robo_novo(self):
        """Os dicts da fila viram `FichaDuplicada` de novo.

        Reconstruir do DICT é o que faz a edição manual valer:
        `JanelaRevisaoEdicao` altera `pmib_original`/`pmib_alvo` no dicionário.
        """
        return [
            duplicadas.FichaDuplicada(
                pmib=item["pmib_alvo"],
                descricao=item.get("descricao", ""),
                pdm_usado="",
                codigo_material=item.get("codigo_material", ""),
                codigo_fornecedor=item.get("codigo_fornecedor", ""),
                ficha_original=item["pmib_original"],
                linha=item.get("linha_excel", 0),
            )
            for item in self.fila_selecionada
        ]

    def _definir_progresso(self, fracao) -> None:
        try:
            self.progress.definir(fracao)
        except RuntimeError:
            pass  # tela já destruída

    def _religar_botoes(self) -> None:
        self._robo_ativo = False
        try:
            self.btn_status.setEnabled(True)
            for botao in (self.btn_robo_novo, self.btn_resumo):
                botao.setEnabled(bool(self.fila_selecionada))
        except RuntimeError:
            pass  # tela já destruída

    def _progresso_do_lote(self, fracao: float, total: int) -> None:
        """A barra da tela e o "Ficha 3 de 8" da faixa. Thread do robô."""
        interface.na_interface(self._definir_progresso, fracao)
        self.informar_progresso(round(fracao * total), total, "ficha")

    def _worker_robo_novo(self, gravar_auditoria: bool, fichas, caminho_status) -> None:
        # Import tardio de propósito: puxa o Playwright, e quem nunca clica
        # neste botão não deve pagar por isso na abertura do aplicativo.
        from sigft.core import log_execucao
        from sigft.services import duplicadas_robo

        engine = None
        log_auditoria = None
        registrar = self.log
        try:
            if gravar_auditoria:
                log_auditoria = log_execucao.LogDeExecucao(
                    "duplicadas", contexto={"fichas": len(fichas)})
                # `envolver` grava no arquivo E repassa para o console.
                registrar = log_auditoria.envolver(self.log)
                self.log(f"[Auditoria] Gravando em: {log_auditoria.caminho}")

            registrar(f"[Robô novo] {len(fichas)} ficha(s) na fila. Abrindo o navegador...")
            engine, portal = duplicadas_robo.iniciar()
            engine.goto(sigft_config.PORTAL_URL)

            # O portal exige login manual: a janela nasce na thread da
            # interface e este worker espera o "Continuar".
            self.pausar_e_esperar(t(MSG_LOGIN_LOTE))

            resultados = duplicadas_robo.processar_lote(
                fichas,
                callback_log=registrar,
                callback_progresso=lambda fracao: self._progresso_do_lote(fracao, len(fichas)),
                portal=portal,
                log_auditoria=log_auditoria,
            )

            # Marca o `_STATUS_PMIB` seção a seção: COMPLETO só onde TUDO deu
            # certo, INCOMPLETO no resto.
            registrar("[Robô novo] Marcando o _STATUS_PMIB...")
            marcadas, falhas = duplicadas_robo.marcar_status_na_planilha(
                caminho_status, resultados, callback_log=registrar)

            concluidas = [r for r in resultados if r.ok]
            registrar(f"[Robô novo] {len(concluidas)} de {len(resultados)} sem pendência; "
                      f"{marcadas} linha(s) marcada(s) na planilha"
                      + (f", {len(falhas)} falha(s)." if falhas else "."))
            registrar("[Robô novo] Confira no portal o que o log marcou como "
                      "pendência antes de mudar o status das fichas.")
        except Exception as erro:  # noqa: BLE001 -- vira log, como lá
            registrar(f"[Robô novo] Falha: {type(erro).__name__}: {erro}")
        finally:
            # Fecha o log ANTES de mexer no navegador: se `engine.fechar()`
            # travar, o arquivo já está íntegro no disco.
            if log_auditoria is not None:
                log_auditoria.fechar()
                self.log(f"[Auditoria] Log salvo: {log_auditoria.caminho}")
            if engine is not None:
                try:
                    engine.fechar()
                except Exception:  # noqa: BLE001
                    pass
            interface.na_interface(self._religar_botoes)

