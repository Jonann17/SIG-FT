"""Aba "Revisão no AMP" do PMIB Manager: manda ao AMP (o n8n da GE) as listas da última
conferência, uma por vez, e mostra o que voltou de cada uma.

A tela é fina: a rodada, o pedido e o diagnóstico estão em `services/revisao_amp.py`, e a
chamada em `core/amp/cliente.py`. As listas saem da última conferência da aba ao lado
(`fonte.ultima`, a `UltimaConferencia` da Conferência de Revisões). O endereço e a chave do
webhook vêm de Configuração → Chaves de API; a chave nunca aparece na tela nem no log.
Desenho: `docs/superpowers/specs/2026-10-27-amp-revisao-de-listas-design.md`, §7 e §8.
"""
from __future__ import annotations

import threading

from PySide6.QtWidgets import QApplication, QHBoxLayout

from sigft import __version__
from sigft.app.idioma import marcar, t
from sigft.app_qt import interface
from sigft.app_qt.widgets import blocos, dialogos_selecao
from sigft.app_qt.widgets.module_frame import ModuleFrame
from sigft.core import plataforma
from sigft.core.amp.cliente import ClienteAmp
from sigft.services import revisao_amp as revisao_amp_svc

# As chaves de `config.ENV_VAR_POR_CHAVE` (Configuração → Chaves de API).
CHAVE_URL = "AMP_WEBHOOK_URL"
CHAVE_DO_WEBHOOK = "AMP_WEBHOOK_CHAVE"

TITULO = marcar("Revisão no AMP")
AVISO_SEM_CONFERENCIA = marcar("Confira as revisões antes.")
AVISO_SEM_CHAVE = marcar("Configure o endereço e a chave do webhook do AMP em Configuração → Chaves de API.")
EXPLICACAO = marcar("Manda ao AMP, uma por vez, as listas da última conferência (aba Conferência de "
                    "Revisões). Cada uma volta como um HTML na pasta do _STATUS_PMIB, com o que mudou e a "
                    "tabela pronta para colar: nada é aplicado no Excel. Dois cliques numa lista abrem o HTML.")

# O que a coluna "AMP" diz de cada lista. A falta vem pronta do serviço ("falta: ...").
NA_FILA = marcar("na fila")
PRONTO = marcar("HTML pronto: {nome}")
FALHOU = marcar("falhou: {erro}")
PARADO = marcar("parado")

# Os nomes vão em `marcar` e são traduzidos onde a tabela é montada (`t(c)`). As larguras
# somam 850: cabem na aba a 1280x850 (as colunas esticam, mas não encolhem).
COLUNAS = (
    (marcar("Código"), 180),
    (marcar("Revisão em uso"), 100),
    (marcar("Revisão atual"), 100),
    (marcar("STATUS REAL"), 110),
    (marcar("AMP"), 360),
)
COLUNA_AMP = len(COLUNAS) - 1


def _linha(*widgets) -> QHBoxLayout:
    linha_ = QHBoxLayout()
    linha_.setSpacing(15)
    for widget in widgets:
        linha_.addWidget(widget)
    linha_.addStretch()
    return linha_


def _texto_amp(resultado) -> str:
    if resultado.situacao == "pronto":
        return t(PRONTO, nome=resultado.html.name)
    if resultado.situacao == "falhou":
        return t(FALHOU, erro=resultado.detalhe)
    if resultado.situacao == "parado":
        return t(PARADO)
    return resultado.detalhe


class ModuloRevisaoAmp(ModuleFrame):
    def __init__(self, parent=None, controller=None, *, fonte=None, embutida=False, console_externo=None,
                 progresso_externo=None) -> None:
        self.fonte = fonte                          # a aba Conferência de Revisões (`fonte.ultima`)
        self.resultados_amp: list[revisao_amp_svc.ResultadoAmp] = []
        self._linha_da_lista: dict[int, int] = {}   # id(ListaParaAmp) -> linha da tabela
        self._resultado_na_linha: list = []
        self._cancelado = threading.Event()
        super().__init__(parent, controller, titulo=t(TITULO), com_progresso=True, embutida=embutida,
                         console_externo=console_externo, progresso_externo=progresso_externo)

    # -- montagem ----------------------------------------------------------
    def _build_ui(self) -> None:
        lay = self.content_layout
        cartao = blocos.cartao(lay)
        self.lbl_explicacao = blocos.rotulo(t(EXPLICACAO), alinhar="esquerda", papel="legenda")
        cartao.addWidget(self.lbl_explicacao)
        self.lbl_webhook = blocos.rotulo("", alinhar="esquerda", elidir=True)
        cartao.addWidget(self.lbl_webhook)

        self.btn_amp = blocos.botao(t("Revisar no AMP"), variante="primario", largura_minima=180, negrito=True)
        self.btn_amp.clicked.connect(self._revisar)
        self.btn_testar_amp = blocos.botao(t("Testar conexão com o AMP"), variante="cinza", largura_minima=200)
        self.btn_testar_amp.clicked.connect(self._testar_conexao)
        self.btn_copiar_diag = blocos.botao(t("Copiar diagnóstico"), variante="cinza", largura_minima=160)
        self.btn_copiar_diag.clicked.connect(self._copiar_diagnostico)
        self.btn_copiar_diag.setEnabled(False)      # só com alguma falha na rodada
        self.btn_parar = blocos.botao(t("Parar"), variante="perigo", largura_minima=90)
        self.btn_parar.clicked.connect(self._parar)
        cartao.addLayout(_linha(self.btn_amp, self.btn_testar_amp, self.btn_copiar_diag, self.btn_parar))

        # Sem barra de lado: as colunas esticam até a largura da tela (`EsticaColunas`).
        self.tabela = dialogos_selecao.tabela_ttk([(t(c), largura, "w") for c, largura in COLUNAS],
                                                  barra_horizontal=False)
        self.tabela.itemDoubleClicked.connect(self._abrir_html)
        lay.addWidget(self.tabela, 1)
        self._mostrar_webhook()

    def showEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        # A chave pode ter sido posta na Configuração com a aba já montada.
        self._mostrar_webhook()
        super().showEvent(evento)

    # -- o webhook ---------------------------------------------------------
    def _webhook(self) -> tuple[str, str]:
        """(endereço, chave) de Configuração → Chaves de API."""
        if self.controller is None:
            return "", ""
        return ((self.controller.get_key(CHAVE_URL) or "").strip(),
                (self.controller.get_key(CHAVE_DO_WEBHOOK) or "").strip())

    def _mostrar_webhook(self) -> None:
        url, chave = self._webhook()
        if not url:
            self.lbl_webhook.setText(t("Webhook do AMP não configurado: Configuração → Chaves de API."))
        elif chave:
            self.lbl_webhook.setText(t("Webhook do AMP: {url} · chave posta", url=url))
        else:
            self.lbl_webhook.setText(t("Webhook do AMP: {url} · sem chave", url=url))

    def _webhook_ou_aviso(self) -> tuple[str, str] | None:
        """O endereço e a chave; faltando um deles, o aviso, e nada é chamado."""
        url, chave = self._webhook()
        if not url or not chave:
            self.avisar(t(TITULO), t(AVISO_SEM_CHAVE), "aviso")
            return None
        return url, chave

    def _listas(self, ultima) -> list:
        """As listas da conferência, com os arquivos de cada uma. Na thread do worker: o
        levantamento da pasta raiz pode demorar."""
        if ultima is None:
            return []
        return revisao_amp_svc.listas_para_amp(ultima.conferencia, ultima.downloads,
                                               ultima.mapeadora.caminho.parent, ultima.pasta_raiz)

    # -- a revisão ---------------------------------------------------------
    def _revisar(self) -> None:
        ultima = getattr(self.fonte, "ultima", None)
        if ultima is None:
            self.avisar(t(TITULO), t(AVISO_SEM_CONFERENCIA), "aviso")
            return
        webhook = self._webhook_ou_aviso()
        if webhook is None:
            return
        self._cancelado.clear()
        self.resultados_amp = []
        self.btn_copiar_diag.setEnabled(False)
        self.iniciar_tarefa(self._worker_revisar, ultima, *webhook, botao=self.btn_amp)

    def _worker_revisar(self, ultima, url: str, chave: str) -> None:
        listas = self._listas(ultima)
        interface.na_interface(self._mostrar_listas, listas)
        if not listas:
            self.log("[AVISO] Nenhuma lista da última conferência tem pasta: nada para mandar ao AMP.")
            return
        resultados = revisao_amp_svc.revisar_listas(
            listas, ClienteAmp(url, chave, log_cb=self.log), versao_sigft=__version__, url=url, chave_posta=True,
            log_cb=self.log, progress_cb=self._progresso, cancelado_cb=self._cancelado.is_set,
            resultado_cb=lambda resultado: interface.na_interface(self._mostrar_resultado, resultado))
        interface.na_interface(self._terminar, resultados)

    def _mostrar_listas(self, listas) -> None:
        self.tabela.clear()
        self._linha_da_lista = {id(lista): i for i, lista in enumerate(listas)}
        self._resultado_na_linha = [None] * len(listas)
        for lista in listas:
            dados = lista.item.lista
            dialogos_selecao.linha_ttk(self.tabela, (dados.codigo, dados.revisao_em_uso, lista.revisao_atual,
                                                     dados.status_real, lista.falta or t(NA_FILA)))

    def _mostrar_resultado(self, resultado) -> None:
        indice = self._linha_da_lista.get(id(resultado.lista))
        if indice is None:
            return
        self._resultado_na_linha[indice] = resultado
        self.tabela.topLevelItem(indice).setText(COLUNA_AMP, _texto_amp(resultado))

    def _terminar(self, resultados) -> None:
        self.resultados_amp = list(resultados)
        falhas = sum(1 for r in self.resultados_amp if r.diagnostico)
        self.btn_copiar_diag.setEnabled(bool(falhas))
        if falhas:
            self.log(f"[AVISO] {falhas} lista(s) falharam. \"Copiar diagnóstico\" copia o texto de cada uma, "
                     "sem texto de documento e sem a chave, para colar numa conversa nova com o Claude.")

    def _progresso(self, fracao: float) -> None:
        if self.progress_bar is not None:
            interface.na_interface(blocos.definir_progresso, self.progress_bar, fracao)

    def _parar(self) -> None:
        self._cancelado.set()
        self.log("Parada pedida: termino a lista que está no AMP e paro.")

    def _copiar_diagnostico(self) -> None:
        texto = revisao_amp_svc.diagnosticos_para_copiar(self.resultados_amp)
        if not texto:
            return
        QApplication.clipboard().setText(texto)
        self.log("Diagnóstico copiado. Cole numa conversa nova com o Claude, com o repositório do SIG-FT.")

    def _abrir_html(self, item, _coluna=0) -> None:
        indice = self.tabela.indexOfTopLevelItem(item)
        resultado = self._resultado_na_linha[indice] if 0 <= indice < len(self._resultado_na_linha) else None
        if resultado is None or resultado.html is None:
            return
        try:
            plataforma.abrir_no_sistema(resultado.html)
        except OSError as erro:
            self.log(f"[AVISO] Não consegui abrir {resultado.html.name}: {erro}")

    # -- o teste de conexão ------------------------------------------------
    def _testar_conexao(self) -> None:
        webhook = self._webhook_ou_aviso()
        if webhook is None:
            return
        self.iniciar_tarefa(self._worker_testar, getattr(self.fonte, "ultima", None), *webhook,
                            botao=self.btn_testar_amp)

    def _worker_testar(self, ultima, url: str, chave: str) -> None:
        listas = self._listas(ultima)
        self.log(f"Testando o AMP em {url}...")
        for linha in revisao_amp_svc.testar_conexao(ClienteAmp(url, chave, log_cb=self.log), listas):
            self.log(linha)
