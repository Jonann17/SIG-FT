"""DocPack, Etapa 2 -- o conteúdo: a lista de materiais do PDF da lista (Aconex + AMP) no
`_STATUS_PMIB` dos dossiês que a Etapa 1 deixou vazios (a lista com preço é do módulo Lista de
Preços desde 2026-11-05).

A tela é fina: o que é um dossiê vazio, o download, o pedido ao AMP e a gravação estão em
`services/docpack_etapa2.py`. O fluxo tem duas metades, de propósito: "Consultar no AMP" só
baixa e pergunta (nada é escrito nas planilhas), e "Gravar nas planilhas" mostra o que voltou
e grava só com o "sim". O webhook é o do workflow da Criação do _STATUS_PMIB
(`amp/criacao_status_pmib/`, `AMP_CRIACAO_STATUS_PMIB_*`), configurado no "Configurar IA" do
DocPack, entrada "Etapa 2: Conteúdo" (desde 2026-11-05; antes, um botão Webhook… nesta aba). Desenho: `docs/base-conhecimento/15b-docpack-etapa2.md`.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout

from sigft.app.idioma import marcar, t
from sigft.app_qt import file_dialogs, interface
from sigft.app_qt.views.conferencia_revisoes import perfil_do_aconex
from sigft.app_qt.widgets.ia_do_modulo import avisos as avisos_da_ia, chaves_do_webhook_so
from sigft.app_qt.widgets import blocos, controles, dialogos_selecao, webhook_amp
from sigft.app_qt.widgets.module_frame import ModuleFrame
from sigft.core import plataforma, prefs
from sigft.core.aconex.cliente import ClienteAconex
from sigft.core.amp.cliente import ClienteAmp
from sigft.services import docpack_etapa2 as etapa2_svc
from sigft.services import revisao_amp as revisao_amp_svc

# O webhook do workflow da Criação do _STATUS_PMIB (`amp/criacao_status_pmib/`, do Luan), que esta
# etapa reusa: o mesmo workflow e o mesmo agente, com nomes próprios no `api_config.json`.
# [2026-11-05] Os nomes vêm do "Configurar IA" (`ia_por_modulo.SO_WORKFLOW`): é lá que o
# webhook se configura agora, e não mais num botão desta aba.
CHAVES_DO_WEBHOOK = chaves_do_webhook_so("docpack_conteudo")
CHAVE_PASTA_RAIZ = "docpack.raiz"   # a mesma raiz da Etapa 1

TITULO = marcar("DocPack · Etapa 2")
AVISO_SEM_RAIZ = marcar("Selecione a pasta raiz antes.")
AVISO_SEM_CHAVE = marcar("Configure o endereço e a chave do webhook em Configurar IA, no alto do DocPack.")
AVISO_NADA_MARCADO = marcar("Marque pelo menos uma lista.")
AVISO_NADA_PRONTO = marcar("Nenhuma lista com materiais para gravar: consulte no AMP antes.")
AVISO_SEM_PERFIL = marcar("Nenhum perfil do Aconex neste Windows: uso o PDF que já está na pasta de cada lista.")
WEBHOOK_NAO_CONFIGURADO = marcar("Workflow AMP sem configurar: use Configurar IA, no alto do DocPack.")
WEBHOOK_CONFIGURADO = marcar("Workflow AMP configurado (em Configurar IA).")
TEXTO_BAIXAR = marcar("Baixar do Aconex a revisão vigente (sem isso, vai o PDF que já está na pasta)")
PERGUNTA_GRAVAR = marcar("Gravar estes materiais no _STATUS_PMIB? Planilha que já tiver material é "
                         "recusada.\n\n{resumo}")

NA_FILA = marcar("na fila")
PRONTA = marcar("{n} material(is) do AMP")
FALHOU = marcar("falhou: {erro}")
PARADO = marcar("parado")
GRAVADO = marcar("gravado")

# Os nomes vão em `marcar` e são traduzidos onde a tabela é montada. As larguras somam 850.
COLUNAS = (
    (marcar("Código"), 220),
    (marcar("Dossiê"), 250),
    (marcar("Situação"), 290),
    # [2026-11-09, pedido do Luan] O botão "Abrir Pasta" do dossiê, o mesmo da Conferência de
    # Revisões (`dialogos_selecao.botao_de_pasta`): ali estão o PDF, o _STATUS_PMIB e o HTML do AMP.
    (marcar("Pasta"), 90),
)
COL_SITUACAO = 2
COL_PASTA = 3


def _linha(*widgets) -> QHBoxLayout:
    linha_ = QHBoxLayout()
    linha_.setSpacing(10)
    for widget in widgets:
        linha_.addWidget(widget)
    linha_.addStretch()
    return linha_


def _situacao(proposta) -> str:
    if proposta.situacao == "pronta":
        return t(PRONTA, n=len(proposta.materiais))
    if proposta.situacao == "parado":
        return t(PARADO)
    return t(FALHOU, erro=proposta.detalhe)


class ModuloDocPackEtapa2(ModuleFrame):
    def __init__(self, parent=None, controller=None, *, embutida=False, console_externo=None,
                 progresso_externo=None) -> None:
        self.pasta_raiz = (prefs.ultima_pasta(CHAVE_PASTA_RAIZ) or prefs.get_default_dir("sobressalentes_pmib")
                           or "")
        self.dossies: list[etapa2_svc.Dossie] = []
        self.propostas: list[etapa2_svc.Proposta] = []
        self._cancelado = threading.Event()
        super().__init__(parent, controller, titulo=t(TITULO), com_progresso=True, embutida=embutida,
                         console_externo=console_externo, progresso_externo=progresso_externo)

    # -- montagem ----------------------------------------------------------
    def _build_ui(self) -> None:
        lay = self.content_layout
        cartao = blocos.cartao(lay)

        self.btn_pasta = blocos.botao(t("Pasta raiz..."), variante="cinza", largura_minima=140)
        self.btn_pasta.clicked.connect(self._sel_pasta)
        self.lbl_pasta = blocos.rotulo(t("Não selecionada"), alinhar="esquerda", elidir=True, papel="legenda")
        self.btn_testar_amp = blocos.botao(t("Testar conexão com o AMP"), variante="cinza", largura_minima=200)
        self.btn_testar_amp.clicked.connect(self._testar_conexao)
        linha_ = QHBoxLayout()
        linha_.setSpacing(10)
        for widget, peso in ((self.btn_pasta, 0), (self.lbl_pasta, 1),
                             (self.btn_testar_amp, 0)):
            linha_.addWidget(widget, peso)
        cartao.addLayout(linha_)
        self.lbl_webhook = blocos.rotulo("", alinhar="esquerda", elidir=True, papel="legenda")
        cartao.addWidget(self.lbl_webhook)
        self.caixa_aconex = controles.CaixaDeMarcar(t(TEXTO_BAIXAR), tamanho_fonte=12)
        self.caixa_aconex.setChecked(True)
        cartao.addWidget(self.caixa_aconex)

        self.btn_procurar = blocos.botao(t("Procurar dossiês vazios"), variante="primario", largura_minima=180,
                                         negrito=True)
        self.btn_procurar.clicked.connect(self._procurar)
        self.btn_consultar = blocos.botao(t("Consultar no AMP"), variante="cinza", largura_minima=150)
        self.btn_consultar.clicked.connect(self._consultar)
        self.btn_gravar = blocos.botao(t("Gravar nas planilhas"), variante="primario", largura_minima=160,
                                       negrito=True)
        self.btn_gravar.clicked.connect(self._gravar)
        self.btn_gravar.setEnabled(False)       # só com alguma proposta pronta
        self.btn_parar = blocos.botao(t("Parar"), variante="perigo", largura_minima=90)
        self.btn_parar.clicked.connect(self._parar)
        cartao.addLayout(_linha(self.btn_procurar, self.btn_consultar, self.btn_gravar, self.btn_parar))

        self.lbl_totais = blocos.rotulo("", alinhar="esquerda", negrito=True)
        lay.addWidget(self.lbl_totais)
        self.tabela = dialogos_selecao.tabela_ttk([(t(c), largura, "w") for c, largura in COLUNAS])
        # [2026-11-05] Barra de rolagem de lado (pedido do Jonathan): a coluna cresce
        # até caber o texto (`ajustar_ao_conteudo`) e o que não cabe na tela rola.
        self.tabela.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        lay.addWidget(self.tabela, 1)
        self._mostrar_pasta()
        self._mostrar_webhook()
        # O "Configurar IA" grava o webhook: a linha de estado acompanha na hora.
        avisos_da_ia().mudou.connect(self._ia_mudou)

    def _ia_mudou(self, _tarefa: str) -> None:
        self._mostrar_webhook()

    def showEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        self._mostrar_webhook()
        super().showEvent(evento)

    def _mostrar_pasta(self) -> None:
        if self.pasta_raiz:
            blocos.marcar_arquivo_escolhido(self.btn_pasta, self.lbl_pasta, self.pasta_raiz)

    def _sel_pasta(self) -> None:
        pasta = file_dialogs.ask_directory(CHAVE_PASTA_RAIZ, "pasta",
                                           titulo=t("Selecione a pasta raiz das listas (SOBRESSALENTES - PMIB)"))
        if pasta:
            self.pasta_raiz = pasta
            self._mostrar_pasta()

    # -- o webhook ---------------------------------------------------------
    def _webhook(self) -> tuple[str, str]:
        return webhook_amp.ler(self.controller, CHAVES_DO_WEBHOOK)

    def _mostrar_webhook(self) -> None:
        url, chave = self._webhook()
        self.lbl_webhook.setText(t(WEBHOOK_CONFIGURADO) if url and chave else t(WEBHOOK_NAO_CONFIGURADO))

    def _webhook_ou_aviso(self) -> tuple[str, str] | None:
        url, chave = self._webhook()
        if not url or not chave:
            self.avisar(t(TITULO), t(AVISO_SEM_CHAVE), "aviso")
            return None
        return url, chave


    def _testar_conexao(self) -> None:
        webhook = self._webhook_ou_aviso()
        if webhook is not None:
            self.iniciar_tarefa(self._worker_testar, *webhook, botao=self.btn_testar_amp)

    def _worker_testar(self, url: str, chave: str) -> None:
        self.log(f"Testando o AMP da Criação do _STATUS_PMIB: {url}")
        for linha in revisao_amp_svc.testar_conexao(ClienteAmp(url, chave, log_cb=self.log)):
            self.log(linha)

    # -- procurar ----------------------------------------------------------
    def _procurar(self) -> None:
        if not self.pasta_raiz:
            self.avisar(t(TITULO), t(AVISO_SEM_RAIZ), "aviso")
            return
        self.iniciar_tarefa(self._worker_procurar, self.pasta_raiz, botao=self.btn_procurar)

    def _worker_procurar(self, raiz: str) -> None:
        self.log(f"Procurando dossiês vazios em {raiz}...")
        varredura = etapa2_svc.procurar_dossies(raiz)
        self.log(f"{len(varredura.vazios)} dossiê(s) com a lista de materiais vazia; "
                 f"{len(varredura.com_materiais)} já com materiais (ficam fora).")
        for codigo, motivo in varredura.ilegiveis:
            self.log(f"  ⚠️ {codigo}: {motivo}")
        interface.na_interface(self._mostrar_dossies, varredura.vazios)

    def _mostrar_dossies(self, dossies) -> None:
        self.dossies, self.propostas = list(dossies), []
        self.btn_gravar.setEnabled(False)
        self.tabela.clear()
        for indice, dossie in enumerate(self.dossies):
            item = dialogos_selecao.linha_ttk(self.tabela, (dossie.codigo, dossie.pasta.name, t(NA_FILA)),
                                              chave=indice)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Checked)
            item.setToolTip(1, str(dossie.pasta))
            dialogos_selecao.botao_de_pasta(self.tabela, item, COL_PASTA, dossie.pasta, self._abrir_pasta)
        dialogos_selecao.ajustar_ao_conteudo(self.tabela)
        self.lbl_totais.setText(t("{n} dossiê(s) vazio(s)", n=len(self.dossies)))

    def _abrir_pasta(self, pasta) -> None:
        try:
            plataforma.abrir_no_sistema(pasta)
        except OSError as erro:
            self.log(f"[AVISO] Não consegui abrir a pasta {pasta}: {erro}")

    def marcados(self) -> list[etapa2_svc.Dossie]:
        escolhidos = []
        for linha in range(self.tabela.topLevelItemCount()):
            item = self.tabela.topLevelItem(linha)
            if item.checkState(0) == Qt.CheckState.Checked:
                escolhidos.append(self.dossies[item.data(0, Qt.ItemDataRole.UserRole)])
        return escolhidos

    # -- consultar ---------------------------------------------------------
    def _consultar(self) -> None:
        dossies = self.marcados()
        if not dossies:
            self.avisar(t(TITULO), t(AVISO_NADA_MARCADO), "aviso")
            return
        webhook = self._webhook_ou_aviso()
        if webhook is None:
            return
        perfil = None
        if self.caixa_aconex.isChecked():
            perfil = perfil_do_aconex(self)
            if perfil is None:
                self.log("[AVISO] " + t(AVISO_SEM_PERFIL))
        self._cancelado.clear()
        self.iniciar_tarefa(self._worker_consultar, dossies, perfil, *webhook, botao=self.btn_consultar)

    def _worker_consultar(self, dossies, perfil, url: str, chave: str) -> None:
        aconex = ClienteAconex(perfil, log_cb=self.log) if perfil is not None else None
        propostas = etapa2_svc.consultar(dossies, aconex, ClienteAmp(url, chave, log_cb=self.log),
                                         log_cb=self.log, progress_cb=self._progresso,
                                         cancelado_cb=self._cancelado.is_set)
        interface.na_interface(self._mostrar_propostas, propostas)

    def _linha_do(self, dossie) -> int | None:
        try:
            return self.dossies.index(dossie)
        except ValueError:
            return None

    def _mostrar_propostas(self, propostas) -> None:
        self.propostas = list(propostas)
        for proposta in self.propostas:
            linha = self._linha_do(proposta.dossie)
            if linha is not None:
                self.tabela.topLevelItem(linha).setText(COL_SITUACAO, _situacao(proposta))
            dialogos_selecao.ajustar_ao_conteudo(self.tabela)
        self.btn_gravar.setEnabled(any(p.situacao == "pronta" for p in self.propostas))

    # -- gravar ------------------------------------------------------------
    def _gravar(self) -> None:
        prontas = [p for p in self.propostas if p.situacao == "pronta"]
        if not prontas:
            self.avisar(t(TITULO), t(AVISO_NADA_PRONTO), "aviso")
            return
        # Sem `botao=`: quem religa o "Gravar" é `_mostrar_gravacoes`, só se ainda houver o que
        # gravar (o `iniciar_tarefa` o religaria sempre, no fim da tarefa).
        self.btn_gravar.setEnabled(False)
        self.iniciar_tarefa(self._worker_gravar, prontas)

    def _worker_gravar(self, prontas) -> None:
        resultados = []
        try:
            resumo = etapa2_svc.resumo_da_proposta(prontas)
            self.log("Proposta do AMP:\n" + resumo)
            if not self.perguntar_sim_nao(t(TITULO), t(PERGUNTA_GRAVAR, resumo=resumo)):
                self.log("Nada foi gravado.")
                return
            resultados = etapa2_svc.gravar(prontas, log_cb=self.log, progress_cb=self._progresso)
        finally:
            interface.na_interface(self._mostrar_gravacoes, resultados)

    def _mostrar_gravacoes(self, resultados) -> None:
        for resultado in resultados:
            linha = self._linha_do(resultado.dossie)
            if linha is None:
                continue
            texto = t(GRAVADO) if resultado.situacao == "gravado" else resultado.detalhe
            item = self.tabela.topLevelItem(linha)
            item.setText(COL_SITUACAO, texto)
            dialogos_selecao.ajustar_ao_conteudo(self.tabela)
            if resultado.situacao == "gravado":
                item.setCheckState(0, Qt.CheckState.Unchecked)
        gravados = {id(r.dossie) for r in resultados if r.situacao in ("gravado", "parcial")}
        self.propostas = [p for p in self.propostas if id(p.dossie) not in gravados]
        self.btn_gravar.setEnabled(any(p.situacao == "pronta" for p in self.propostas))

    def _progresso(self, fracao: float) -> None:
        if self.progress_bar is not None:
            interface.na_interface(blocos.definir_progresso, self.progress_bar, fracao)

    def _parar(self) -> None:
        self._cancelado.set()
        self.log("Parada pedida: termino a lista que está no AMP e paro.")
