"""Aba "Revisão no AMP" do PMIB Manager: manda ao AMP (o n8n da GE) as listas marcadas da
última conferência, uma por vez, e mostra o que voltou de cada uma.

A tela é fina: a rodada, o pedido e o diagnóstico estão em `services/revisao_amp.py`, e a
chamada em `core/amp/cliente.py`. As listas saem da última conferência da aba ao lado
(`fonte.ultima`, a `UltimaConferencia` da Conferência de Revisões) e aparecem assim que a aba
abre, todas marcadas: o Luan desmarca as que não quer. O endereço e a chave do webhook moram
nesta aba (botão Webhook…, `widgets/webhook_amp.py`), com nomes deste workflow; a chave nunca
aparece na tela nem no log. Cada rodada e cada teste de conexão gravam as linhas do console em
`logs\\amp\\` (`core/log_execucao.py`).
Desenho: `docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`, §5.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout

from sigft import __version__
from sigft.app.idioma import marcar, t
from sigft.app_qt import interface
from sigft.app_qt.widgets import blocos, dialogos_selecao, webhook_amp
from sigft.app_qt.widgets.module_frame import ModuleFrame
from sigft.core import dados_usuario, log_execucao, plataforma
from sigft.core.amp.cliente import ClienteAmp
from sigft.services import revisao_amp as revisao_amp_svc

# Os nomes deste workflow no `api_config.json`. Os antigos (Configuração → Chaves de API, até
# 2026-11-03) são adotados uma vez.
CHAVES_DO_WEBHOOK = webhook_amp.ChavesDoWebhook("AMP_REVISAO_LISTAS_URL", "AMP_REVISAO_LISTAS_CHAVE",
                                                antigas=("AMP_WEBHOOK_URL", "AMP_WEBHOOK_CHAVE"))

TITULO = marcar("Revisão no AMP")
TITULO_DO_WEBHOOK = marcar("Webhook da Revisão no AMP")
AVISO_SEM_CONFERENCIA = marcar("Confira as revisões antes.")
AVISO_CONFERENCIA_RODANDO = marcar("A conferência ainda está rodando: espere ela terminar.")
AVISO_SEM_CHAVE = marcar("Configure o endereço e a chave do webhook no botão Webhook…, nesta aba.")
AVISO_NENHUMA_MARCADA = marcar("Marque ao menos uma lista para mandar ao AMP.")
AVISO_TABELA_REFEITA = marcar("A conferência mudou: a tabela foi refeita com as listas dela. Confira as "
                              "marcas e clique em Revisar no AMP de novo.")
WEBHOOK_NAO_CONFIGURADO = marcar("Webhook do AMP não configurado: clique em Webhook…, nesta aba.")
EXPLICACAO = marcar("Manda ao AMP, uma por vez, as listas marcadas da última conferência (aba Conferência "
                    "de Revisões). Cada uma volta como um HTML na pasta do _STATUS_PMIB, com o que mudou e as "
                    "ações no controle: nada é aplicado no Excel. Dois cliques numa lista abrem o HTML.")

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
    (marcar("AMP"), 270),
    (marcar("Pasta"), 90),
)
COLUNA_AMP = 4
COLUNA_PASTA = 5


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


def _chave(chave: str) -> str:
    return "posta" if chave else "não posta"  # nao-e-interface: vai só para o log


class ModuloRevisaoAmp(ModuleFrame):
    def __init__(self, parent=None, controller=None, *, fonte=None, embutida=False, console_externo=None,
                 progresso_externo=None) -> None:
        self.fonte = fonte                          # a aba Conferência de Revisões (`fonte.ultima`)
        self.resultados_amp: list[revisao_amp_svc.ResultadoAmp] = []
        self._listas_na_tabela: list = []           # uma ListaParaAmp por linha, na ordem da tabela
        self._conferencia_na_tabela = None          # a `UltimaConferencia` que a tabela mostra
        self._carregando = False
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
        self.btn_webhook = blocos.botao(t("Webhook…"), variante="cinza", largura_minima=110)
        self.btn_webhook.clicked.connect(self._configurar_webhook)
        self.btn_copiar_diag = blocos.botao(t("Copiar diagnóstico"), variante="cinza", largura_minima=160)
        self.btn_copiar_diag.clicked.connect(self._copiar_diagnostico)
        self.btn_copiar_diag.setEnabled(False)      # só com alguma falha na rodada
        self.btn_parar = blocos.botao(t("Parar"), variante="perigo", largura_minima=90)
        self.btn_parar.clicked.connect(self._parar)
        cartao.addLayout(_linha(self.btn_amp, self.btn_testar_amp, self.btn_webhook, self.btn_copiar_diag,
                                self.btn_parar))

        self.btn_marcar = blocos.botao(t("Marcar todas"), variante="cinza", largura_minima=140)
        self.btn_marcar.clicked.connect(lambda _marcado=False: self._marcar_todas(True))
        self.btn_desmarcar = blocos.botao(t("Desmarcar todas"), variante="cinza", largura_minima=140)
        self.btn_desmarcar.clicked.connect(lambda _marcado=False: self._marcar_todas(False))
        lay.addLayout(_linha(self.btn_marcar, self.btn_desmarcar))

        # Sem barra de lado: as colunas esticam até a largura da tela (`EsticaColunas`), e as
        # larguras somam 850, que cabem a 1280x850 (nenhuma tela rola de lado).
        self.tabela = dialogos_selecao.tabela_ttk([(t(c), largura, "w") for c, largura in COLUNAS],
                                                  barra_horizontal=False)
        self.tabela.itemDoubleClicked.connect(self._abrir_html)
        lay.addWidget(self.tabela, 1)
        self._mostrar_webhook()

    def showEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        # O webhook pode ter mudado, e a Conferência pode ter rodado de novo, com a aba já montada.
        self._mostrar_webhook()
        self.atualizar_listas()
        super().showEvent(evento)

    # -- o webhook ---------------------------------------------------------
    def _webhook(self) -> tuple[str, str]:
        """(endereço, chave) deste workflow (`CHAVES_DO_WEBHOOK`)."""
        return webhook_amp.ler(self.controller, CHAVES_DO_WEBHOOK)

    def _mostrar_webhook(self) -> None:
        url, chave = self._webhook()
        if not url:
            self.lbl_webhook.setText(t(WEBHOOK_NAO_CONFIGURADO))
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

    def _configurar_webhook(self) -> None:
        url, chave = self._webhook()
        janela = webhook_amp.JanelaDoWebhook(self, titulo=t(TITULO_DO_WEBHOOK), url=url, chave=chave)
        if janela.exec() != QDialog.DialogCode.Accepted:
            return
        novo_url, nova_chave = janela.valores()
        if self.controller is not None:
            webhook_amp.gravar(self.controller, CHAVES_DO_WEBHOOK, novo_url, nova_chave)
        self._mostrar_webhook()
        self.log(f"Webhook da Revisão no AMP salvo: {novo_url} · chave {_chave(nova_chave)}")

    def _log_em_arquivo(self, nome: str, url: str, chave: str):
        """O log em `logs\\amp\\` (as linhas do console, com a hora) e o callback que escreve nos
        dois. A chave não vai: só se ela está posta."""
        arquivo = log_execucao.LogDeExecucao(nome, pasta=str(dados_usuario.pasta_logs() / "amp"),
                                             contexto={"SIG-FT": __version__, "webhook": url,
                                                       "chave": _chave(chave)})
        log = arquivo.envolver(self.log)
        log(f"Log em arquivo: {arquivo.caminho}")
        return arquivo, log

    # -- as listas ---------------------------------------------------------
    def _listas(self, ultima) -> list:
        """As listas da conferência, com os arquivos de cada uma. Na thread do worker: o
        levantamento da pasta raiz pode demorar."""
        if ultima is None:
            return []
        return revisao_amp_svc.listas_para_amp(ultima.conferencia, ultima.downloads,
                                               ultima.mapeadora.caminho.parent, ultima.pasta_raiz)

    def atualizar_listas(self) -> None:
        """Enche a tabela com as listas da última conferência, se ela ainda não as mostra. Não
        mexe com a Conferência rodando nem no meio de uma rodada."""
        ultima = getattr(self.fonte, "ultima", None)
        if ultima is None or ultima is self._conferencia_na_tabela or self._carregando or self.rodando():
            return
        if getattr(self.fonte, "rodando", lambda: False)():
            return
        self._carregando = True
        self.iniciar_tarefa(self._worker_carregar, ultima)

    def _worker_carregar(self, ultima) -> None:
        listas = None
        try:
            listas = self._listas(ultima)
            podem = sum(1 for lista in listas if not lista.falta)
            self.log(f"Revisão no AMP: {len(listas)} lista(s) na conferência; {podem} podem ir ao AMP, "
                     f"{len(listas) - podem} com falta.")
        finally:
            interface.na_interface(self._mostrar_listas, listas, ultima)

    def _mostrar_listas(self, listas, ultima) -> None:
        self._carregando = False
        if listas is None:          # o erro já foi para o console (`iniciar_tarefa`)
            return
        self.tabela.clear()
        self._listas_na_tabela = list(listas)
        self._conferencia_na_tabela = ultima
        self._linha_da_lista = {id(lista): i for i, lista in enumerate(listas)}
        self._resultado_na_linha = [None] * len(listas)
        for lista in listas:
            dados = lista.item.lista
            item = dialogos_selecao.linha_ttk(self.tabela, (dados.codigo, dados.revisao_em_uso, lista.revisao_atual,
                                                            dados.status_real, lista.falta, ""))
            dialogos_selecao.botao_de_pasta(self.tabela, item, COLUNA_PASTA, lista.item.pasta, self._abrir_pasta)
            # O QTreeWidgetItem já nasce marcável: a lista com falta perde isso e fica sem caixa.
            if lista.falta:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            else:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked)

    def _itens_com_caixa(self):
        for i, lista in enumerate(self._listas_na_tabela):
            if not lista.falta:
                yield lista, self.tabela.topLevelItem(i)

    def _marcar_todas(self, marcada: bool) -> None:
        estado = Qt.CheckState.Checked if marcada else Qt.CheckState.Unchecked
        for _lista, item in self._itens_com_caixa():
            item.setCheckState(0, estado)

    def marcadas(self) -> list:
        return [lista for lista, item in self._itens_com_caixa() if item.checkState(0) == Qt.CheckState.Checked]

    def _travar_caixas(self, travar: bool) -> None:
        """Durante a rodada as caixas não mudam: a tabela diz o que foi mandado."""
        for _lista, item in self._itens_com_caixa():
            flags = item.flags()
            item.setFlags(flags & ~Qt.ItemFlag.ItemIsUserCheckable if travar
                          else flags | Qt.ItemFlag.ItemIsUserCheckable)
        self.btn_marcar.setEnabled(not travar)
        self.btn_desmarcar.setEnabled(not travar)

    # -- a revisão ---------------------------------------------------------
    def _revisar(self) -> None:
        # Com a Conferência ainda baixando, a última conferência está sem os downloads, e
        # um PDF pode estar pela metade.
        if getattr(self.fonte, "rodando", lambda: False)():
            self.avisar(t(TITULO), t(AVISO_CONFERENCIA_RODANDO), "aviso")
            return
        ultima = getattr(self.fonte, "ultima", None)
        if ultima is None:
            self.avisar(t(TITULO), t(AVISO_SEM_CONFERENCIA), "aviso")
            return
        webhook = self._webhook_ou_aviso()
        if webhook is None:
            return
        if ultima is not self._conferencia_na_tabela:
            self.atualizar_listas()
            self.avisar(t(TITULO), t(AVISO_TABELA_REFEITA), "aviso")
            return
        listas = self.marcadas()
        if not listas:
            self.avisar(t(TITULO), t(AVISO_NENHUMA_MARCADA), "aviso")
            return
        vao = {id(lista) for lista in listas}
        desmarcadas = [lista.item.lista.codigo for lista, _item in self._itens_com_caixa() if id(lista) not in vao]
        com_falta = [lista.item.lista.codigo for lista in self._listas_na_tabela if lista.falta]
        self._cancelado.clear()
        self.resultados_amp = []
        self.btn_copiar_diag.setEnabled(False)
        self._travar_caixas(True)
        for lista in listas:
            self.tabela.topLevelItem(self._linha_da_lista[id(lista)]).setText(COLUNA_AMP, t(NA_FILA))
        self.iniciar_tarefa(self._worker_revisar, listas, desmarcadas, com_falta, *webhook, botao=self.btn_amp)

    def _worker_revisar(self, listas, desmarcadas, com_falta, url: str, chave: str) -> None:
        resultados: list = []
        arquivo, log = self._log_em_arquivo("amp_revisao", url, chave)
        try:
            resultados = revisao_amp_svc.revisar_listas(
                listas, ClienteAmp(url, chave, log_cb=log), versao_sigft=__version__, url=url,
                chave_posta=bool(chave), log_cb=log, progress_cb=self._progresso,
                cancelado_cb=self._cancelado.is_set, desmarcadas=desmarcadas, com_falta=com_falta,
                resultado_cb=lambda resultado: interface.na_interface(self._mostrar_resultado, resultado))
        finally:
            arquivo.fechar()
            interface.na_interface(self._terminar, resultados)

    def _mostrar_resultado(self, resultado) -> None:
        indice = self._linha_da_lista.get(id(resultado.lista))
        if indice is None:
            return
        self._resultado_na_linha[indice] = resultado
        self.tabela.topLevelItem(indice).setText(COLUNA_AMP, _texto_amp(resultado))

    def _terminar(self, resultados) -> None:
        self.resultados_amp = list(resultados)
        self._travar_caixas(False)
        # A lista que voltou com HTML se desmarca: um segundo clique manda só as que faltaram.
        for resultado in self.resultados_amp:
            indice = self._linha_da_lista.get(id(resultado.lista))
            if resultado.situacao == "pronto" and indice is not None:
                self.tabela.topLevelItem(indice).setCheckState(0, Qt.CheckState.Unchecked)
        falhas = sum(1 for r in self.resultados_amp if r.situacao == "falhou")
        self.btn_copiar_diag.setEnabled(any(r.diagnostico for r in self.resultados_amp))
        if falhas:
            self.log(f"[AVISO] {falhas} lista(s) falharam. \"Copiar diagnóstico\" copia o texto de cada uma, "
                     "sem conteúdo de documento e sem a chave, para colar numa conversa nova com o Claude.")

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

    def _abrir_pasta(self, pasta) -> None:
        try:
            plataforma.abrir_no_sistema(pasta)
        except OSError as erro:
            self.log(f"[AVISO] Não consegui abrir a pasta {pasta}: {erro}")

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
        self.iniciar_tarefa(self._worker_testar, *webhook, botao=self.btn_testar_amp)

    def _worker_testar(self, url: str, chave: str) -> None:
        arquivo, log = self._log_em_arquivo("amp_teste", url, chave)
        try:
            log(f"Testando o AMP: {url} · chave {_chave(chave)}")
            for linha in revisao_amp_svc.testar_conexao(ClienteAmp(url, chave, log_cb=log)):
                log(linha)
        finally:
            arquivo.fechar()
