"""Tela "Conferência de Revisões": aponta as listas cuja REVISÃO EM USO ficou para
trás da ÚLTIMA REVISÃO EMITIDA no Aconex, separadas pelo STATUS REAL, e baixa a
revisão vigente (e a em uso, se faltar) para a pasta do `_STATUS_PMIB` de cada uma.

A tela é fina: a regra e os downloads estão em `services/conferencia_revisoes.py`, e
o Aconex em `core/aconex/`. Ela usa o que o último Gestão PMIB deixou na mapeadora e
não roda o Gestão sozinha. Desenho:
`docs/superpowers/specs/2026-10-26-aconex-ao-vivo-design.md`, §5.
"""
from __future__ import annotations

import os
import threading
from datetime import date, datetime
from pathlib import Path

from PySide6.QtWidgets import QHBoxLayout, QInputDialog, QTabWidget

from sigft.app.idioma import marcar, t
from sigft.app_qt import file_dialogs, interface
from sigft.app_qt.widgets import blocos, dialogos_selecao
from sigft.app_qt.widgets.module_frame import ModuleFrame
from sigft.core import prefs
from sigft.core.aconex.cliente import ClienteAconex, ErroAconex
from sigft.core.aconex.credenciais import PREFERENCIA_PERFIL, PerfilAconex, escolher_perfil, ler_perfis
from sigft.core.aconex.diagnostico import linha, sondar
from sigft.core.aconex.status_real import ORDEM_DAS_CATEGORIAS
from sigft.services import conferencia_revisoes as conferencia_svc

# As chaves do Gestão PMIB: as duas telas lembram a mesma mapeadora e a mesma pasta raiz.
CHAVE_DIALOGO_MAPEADORA = "pmib_manager.master"
CHAVE_PASTA_RAIZ = "pmib_manager.pasta_raiz"

AVISO_SEM_CONEXAO = marcar("Sem conexão com o Aconex: as listas aparecem, mas nada foi baixado.")
AVISO_MAPEADORA_ANTIGA = marcar("A mapeadora não foi atualizada hoje. Rode o Gestão PMIB antes para ver "
                                "as revisões mais recentes.")

NOME_DA_CATEGORIA = {
    "aprovada": marcar("Aprovadas"),
    "em_processo": marcar("Em processo"),
    "nao_aprovada": marcar("Não aprovadas"),
    "outros": marcar("Outros"),
}
SITUACAO = {"baixado": marcar("baixado"), "ja_existia": marcar("já existia"), "falhou": marcar("falhou")}

# Os nomes vão em `marcar` e são traduzidos onde a tabela é montada (`t(c)`).
COLUNAS = (
    (marcar("Código"), 200),
    (marcar("Revisão em uso"), 100),
    (marcar("Última revisão emitida"), 140),
    (marcar("Status da revisão"), 140),
    (marcar("STATUS REAL"), 140),
    (marcar("PDF"), 300),
)


def perfil_do_aconex(pai) -> PerfilAconex | None:
    """O perfil do cofre do DocManager: o único, o preferido, ou o que a pessoa
    escolher numa janela (a escolha fica gravada). `None` sem perfil ou se ela
    desistir. Chamar na thread da interface."""
    perfis = ler_perfis()
    if not perfis:
        return None
    perfil = escolher_perfil(perfis, prefs.ler_preferencia(PREFERENCIA_PERFIL, ""))
    if perfil is not None:
        return perfil
    nome, ok = QInputDialog.getItem(pai, t("Perfil do Aconex"),
                                    t("Há mais de um perfil no cofre do DocManager. Qual usar?"),
                                    [p.nome for p in perfis], 0, False)
    if not ok:
        return None
    prefs.gravar_preferencia(PREFERENCIA_PERFIL, nome)
    return next((p for p in perfis if p.nome == nome), None)


def _texto_do_pdf(item, downloads) -> str:
    """O que aconteceu com os PDFs da lista; sem download, o motivo do item."""
    if not downloads:
        return item.motivo
    partes = []
    for d in downloads:
        texto = f"[{d.revisao or '?'}] {t(SITUACAO[d.situacao])}"
        partes.append(f"{texto} ({d.detalhe})" if d.detalhe else texto)
    return "; ".join(partes)


def _linha(*widgets) -> QHBoxLayout:
    linha_ = QHBoxLayout()
    linha_.setSpacing(15)
    for widget in widgets:
        linha_.addWidget(widget)
    linha_.addStretch()
    return linha_


class ModuloConferenciaRevisoes(ModuleFrame):
    def __init__(self, parent=None, controller=None) -> None:
        self.caminho_mapeadora = prefs.get_last_file(prefs.CHAVE_MAPEAMENTO) or ""
        self.pasta_raiz = prefs.ultima_pasta(CHAVE_PASTA_RAIZ) or ""
        self.tabelas = {}
        self._cancelado = threading.Event()
        super().__init__(parent, controller, titulo=t("Conferência de Revisões"), com_progresso=True)

    # -- montagem ----------------------------------------------------------
    def _build_ui(self) -> None:
        lay = self.content_layout
        cartao = blocos.cartao(lay)

        self.btn_mapeadora = blocos.botao(t("Mapeadora..."), variante="cinza", largura_minima=160)
        self.btn_mapeadora.clicked.connect(self._sel_mapeadora)
        self.lbl_mapeadora = blocos.rotulo(t("Não selecionada"), alinhar="esquerda", elidir=True, papel="legenda")
        cartao.addLayout(_linha(self.btn_mapeadora, self.lbl_mapeadora))

        self.btn_pasta = blocos.botao(t("Pasta raiz..."), variante="cinza", largura_minima=160)
        self.btn_pasta.clicked.connect(self._sel_pasta)
        self.lbl_pasta = blocos.rotulo(t("Não selecionada"), alinhar="esquerda", elidir=True, papel="legenda")
        cartao.addLayout(_linha(self.btn_pasta, self.lbl_pasta))

        self.lbl_salva_em = blocos.rotulo("", alinhar="esquerda")
        self.lbl_antiga = blocos.rotulo(t(AVISO_MAPEADORA_ANTIGA), alinhar="esquerda", papel="aviso")
        cartao.addWidget(self.lbl_salva_em)
        cartao.addWidget(self.lbl_antiga)

        self.btn_conferir = blocos.botao(t("Conferir revisões"), variante="primario", largura_minima=180,
                                         negrito=True)
        self.btn_conferir.clicked.connect(self._conferir)
        self.btn_testar = blocos.botao(t("Testar conexão com o Aconex"), variante="cinza", largura_minima=200)
        self.btn_testar.clicked.connect(self._testar_conexao)
        self.btn_parar = blocos.botao(t("Parar"), variante="perigo", largura_minima=90)
        self.btn_parar.clicked.connect(self._parar)
        cartao.addLayout(_linha(self.btn_conferir, self.btn_testar, self.btn_parar))

        self.lbl_totais = blocos.rotulo("", alinhar="esquerda", negrito=True)
        lay.addWidget(self.lbl_totais)
        self.abas = QTabWidget()
        for categoria in ORDEM_DAS_CATEGORIAS:
            # Sem barra de lado: as colunas esticam até a largura da tela (`EsticaColunas`).
            tabela = dialogos_selecao.tabela_ttk([(t(c), largura, "w") for c, largura in COLUNAS],
                                                 barra_horizontal=False)
            self.tabelas[categoria] = tabela
            self.abas.addTab(tabela, t(NOME_DA_CATEGORIA[categoria]))
        lay.addWidget(self.abas, 1)

        self._mostrar_arquivos()

    def _mostrar_arquivos(self) -> None:
        if self.caminho_mapeadora:
            blocos.marcar_arquivo_escolhido(self.btn_mapeadora, self.lbl_mapeadora, self.caminho_mapeadora)
        if self.pasta_raiz:
            blocos.marcar_arquivo_escolhido(self.btn_pasta, self.lbl_pasta, self.pasta_raiz)
        self._mostrar_data()

    def _mostrar_data(self, salva_em: datetime | None = None) -> None:
        """Quando a mapeadora foi salva, e o aviso se não foi hoje (§5.1): a conferência
        usa o que o último Gestão PMIB deixou nela."""
        if salva_em is None and os.path.isfile(self.caminho_mapeadora):
            salva_em = datetime.fromtimestamp(os.path.getmtime(self.caminho_mapeadora))
        if salva_em is None:
            self.lbl_salva_em.setText("")
            self.lbl_antiga.hide()
            return
        self.lbl_salva_em.setText(t("Mapeadora salva em {quando}", quando=salva_em.strftime("%d/%m/%Y %H:%M")))
        self.lbl_antiga.setVisible(salva_em.date() != date.today())

    # -- arquivos ----------------------------------------------------------
    def _sel_mapeadora(self) -> None:
        caminho = file_dialogs.ask_open_file(CHAVE_DIALOGO_MAPEADORA, "excel", titulo=t("Selecione a mapeadora"),
                                             filetypes=[("Excel", "*.xlsx *.xlsm")])
        if not caminho:
            return
        self.caminho_mapeadora = caminho
        try:
            prefs.remember_file(prefs.CHAVE_MAPEAMENTO, caminho)
        except Exception:  # noqa: BLE001 -- lembrar é conveniência; não atrapalha a seleção
            pass
        self._mostrar_arquivos()

    def _sel_pasta(self) -> None:
        pasta = file_dialogs.ask_directory(CHAVE_PASTA_RAIZ, "pasta",
                                           titulo=t("Selecione a pasta raiz dos _STATUS_PMIB"))
        if pasta:
            self.pasta_raiz = pasta
            self._mostrar_arquivos()

    # -- a conferência -----------------------------------------------------
    def _conferir(self) -> None:
        if not self.caminho_mapeadora:
            self.avisar(t("Mapeadora"), t("Selecione a mapeadora antes."), "aviso")
            return
        perfil = perfil_do_aconex(self)
        self._cancelado.clear()
        self.iniciar_tarefa(self._worker_conferir, self.caminho_mapeadora, self.pasta_raiz, perfil,
                            botao=self.btn_conferir)

    def _worker_conferir(self, caminho: str, pasta_raiz: str, perfil: PerfilAconex | None) -> None:
        self.log(f"Lendo a mapeadora {os.path.basename(caminho)}...")
        try:
            mapeadora = conferencia_svc.ler_mapeadora(caminho)
        except Exception as erro:  # noqa: BLE001 -- planilha do usuário
            self.log(f"[ERRO] Não consegui ler a mapeadora: {erro}")
            return
        conferencia = conferencia_svc.conferir(mapeadora, Path(pasta_raiz) if pasta_raiz else None)
        interface.na_interface(self._mostrar, mapeadora, conferencia, [])
        self.log(f"{len(conferencia.itens)} lista(s) com divergência, {conferencia.em_dia} em dia e "
                 f"{conferencia.sem_status_pmib} sem _STATUS_PMIB.")
        if not any(item.pasta is not None for item in conferencia.itens):
            return
        cliente = self._cliente(perfil)
        if cliente is None:
            return
        downloads = conferencia_svc.baixar(conferencia, cliente, log_cb=self.log, progress_cb=self._progresso,
                                           cancelado_cb=self._cancelado.is_set)
        interface.na_interface(self._mostrar, mapeadora, conferencia, downloads)

    def _cliente(self, perfil: PerfilAconex | None) -> ClienteAconex | None:
        """O cliente com o login feito, ou `None` depois de avisar que nada será baixado."""
        if perfil is not None:
            cliente = ClienteAconex(perfil, log_cb=self.log)
            try:
                cliente.conectar()
                return cliente
            except ErroAconex as erro:
                self.log(f"[AVISO] {erro}")
        self.log("[AVISO] " + t(AVISO_SEM_CONEXAO))
        return None

    def _progresso(self, fracao: float) -> None:
        interface.na_interface(self.progress_bar.setValue, int(fracao * 1000))

    def _parar(self) -> None:
        self._cancelado.set()
        self.log("Parada pedida: termino a lista atual e paro.")

    def _mostrar(self, mapeadora, conferencia, downloads) -> None:
        """Os totais e uma tabela por categoria, na ordem da §5.2 (aprovadas primeiro)."""
        self._mostrar_data(mapeadora.salva_em)
        grupos = conferencia.por_categoria()
        totais = [f"{t(NOME_DA_CATEGORIA[c])}: {len(itens)}" for c, itens in grupos.items()]
        totais += [t("Em dia: {n}", n=conferencia.em_dia),
                   t("Sem _STATUS_PMIB: {n}", n=conferencia.sem_status_pmib)]
        self.lbl_totais.setText("  ·  ".join(totais))
        por_codigo: dict = {}
        for d in downloads:
            por_codigo.setdefault(d.codigo, []).append(d)
        for indice, (categoria, itens) in enumerate(grupos.items()):
            self.abas.setTabText(indice, f"{t(NOME_DA_CATEGORIA[categoria])} ({len(itens)})")
            tabela = self.tabelas[categoria]
            tabela.clear()
            for item in itens:
                lista = item.lista
                dialogos_selecao.linha_ttk(tabela, (lista.codigo, lista.revisao_em_uso, lista.ultima_revisao,
                                                    lista.status_da_revisao, lista.status_real,
                                                    _texto_do_pdf(item, por_codigo.get(lista.codigo, []))))

    # -- o teste de conexão ------------------------------------------------
    def _testar_conexao(self) -> None:
        if not self.caminho_mapeadora:
            self.avisar(t("Mapeadora"), t("Selecione a mapeadora antes."), "aviso")
            return
        perfil = perfil_do_aconex(self)
        if perfil is None:
            self.log("[AVISO] " + t("Nenhum perfil do Aconex neste Windows: cadastre-o no DocManager."))
            return
        self.iniciar_tarefa(self._worker_testar, self.caminho_mapeadora, perfil, botao=self.btn_testar)

    def _worker_testar(self, caminho: str, perfil: PerfilAconex) -> None:
        listas = conferencia_svc.ler_mapeadora(caminho).listas
        if not listas:
            self.log("[AVISO] A mapeadora não tem lista nenhuma para testar a busca.")
            return
        codigo = listas[0].codigo
        self.log(f"Testando o Aconex com o perfil {perfil.nome} e a lista {codigo}...")
        for sonda in sondar(ClienteAconex(perfil, log_cb=self.log), codigo):
            self.log(linha(sonda))
