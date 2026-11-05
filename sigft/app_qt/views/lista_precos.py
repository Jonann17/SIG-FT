"""Módulo "Lista de Preços" (2026-11-05): a lista com preço de cada sistema, em duas
abas com UM console e UMA barra.

Pedido do Jonathan: a lista com preço saiu do DocPack (o agente do webhook não olha
para ela) e virou módulo próprio, na Gestão.

* **Criar / preencher** (`ModuloListaPrecosCriar`): varre a pasta raiz; cada sistema
  com `_STATUS_PMIB` vivo diz se já tem lista com preço; nos marcados que não têm, a
  lista sai do template com os materiais do `_STATUS_PMIB`.
* **Conferir** (`ModuloListaPrecosConferir`): UMA pasta, escolhida. Mostra as
  divergências entre a lista com preço e o `_STATUS_PMIB`, o link da pasta para a
  conferência humana, e "Atualizar". Lista já valorizada: o aviso fica na tela, e a
  atualização pergunta antes e mantém os preços dos itens que continuam.

A tela é fina: a regra está em `services/lista_precos_arquivo.py`.
"""
from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout

from sigft.app.idioma import marcar, t
from sigft.app_qt import estilo, file_dialogs, interface
from sigft.app_qt.views.aplicacao_lmr import MARGEM_DA_ROLAGEM, MARGEM_DIREITA_DA_ROLAGEM
from sigft.app_qt.widgets import blocos, dialogos_selecao
from sigft.app_qt.widgets.abas import Abas
from sigft.app_qt.widgets.como_funciona import instalar_como_funciona
from sigft.app_qt.widgets.module_frame import ModuleFrame
from sigft.core import plataforma, prefs
from sigft.services import conferencia_revisoes as conferencia_svc
from sigft.services import lista_precos_arquivo as lp_svc

TITULO = marcar("Lista de Preços")
ABA_CRIAR = marcar("Criar / preencher")
ABA_CONFERIR = marcar("Conferir")
CHAVE_PASTA_RAIZ = "lista_precos.raiz"
CHAVE_PASTA_SISTEMA = "lista_precos.sistema"
CHAVE_TEMPLATE = "lista_precos.template"

AVISO_SEM_RAIZ = marcar("Selecione a pasta raiz antes.")
AVISO_SEM_TEMPLATE = marcar("Selecione o template da lista com preço antes.")
AVISO_NADA_MARCADO = marcar("Marque pelo menos um sistema sem lista com preço.")
AVISO_SEM_PASTA = marcar("Selecione a pasta do sistema antes.")
PERGUNTA_CRIAR = marcar("Criar {n} lista(s) com preço? Nenhum arquivo que já existe é tocado.")
PERGUNTA_ATUALIZAR = marcar("Reescrever os materiais de {arquivo} a partir do _STATUS_PMIB?")
PERGUNTA_ATUALIZAR_VALORIZADA = marcar(
    "ATENÇÃO: {arquivo} já está valorizada. Os preços dos itens que continuam são mantidos; os itens "
    "novos entram sem preço, e os que saíram do _STATUS_PMIB saem da lista. Atualizar mesmo assim?")
AVISO_VALORIZADA = marcar("⚠ Lista já valorizada e com divergências com o _STATUS_PMIB. Confira antes de atualizar.")
EM_DIA = marcar("A lista com preço está igual ao _STATUS_PMIB.")
TEM = marcar("sim")
TEM_LEGADO = marcar("sim (PB020-0x, legado)")
NAO_TEM = marcar("não")
ILEGIVEL = marcar("ilegível: {erro}")

# As larguras somam 760: cabem sem rolar de lado na aba vazia, a 1366x768 e com a letra
# grande; com o conteúdo, a coluna cresce até o texto e a barra aparece (`ajustar_ao_conteudo`).
COLUNAS_CRIAR = (
    (marcar("Código"), 200),
    (marcar("Pasta"), 260),
    (marcar("Lista com preço"), 140),
    (marcar("Materiais no _STATUS_PMIB"), 160),
)
COLUNAS_CONFERIR = (
    (marcar("Divergência"), 140),
    (marcar("Item"), 170),
    (marcar("Campo"), 90),
    (marcar("No _STATUS_PMIB"), 180),
    (marcar("Na lista com preço"), 180),
)
TIPOS = {"falta_na_lista": marcar("falta na lista"), "sobra_na_lista": marcar("sobra na lista"),
         "diferente": marcar("diferente")}


def _linha(*widgets) -> QHBoxLayout:
    linha_ = QHBoxLayout()
    linha_.setSpacing(10)
    for widget in widgets:
        linha_.addWidget(widget)
    linha_.addStretch()
    return linha_


def _tabela(colunas):
    tabela = dialogos_selecao.tabela_ttk([(t(c), largura, "w") for c, largura in colunas])
    # A barra de lado só quando a coluna, alargada até o texto, não cabe (2026-11-05).
    tabela.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    return tabela


# ------------------------------------------------------------------ Criar / preencher

class ModuloListaPrecosCriar(ModuleFrame):
    def __init__(self, parent=None, controller=None, *, embutida=False, console_externo=None,
                 progresso_externo=None) -> None:
        self.pasta_raiz = (prefs.ultima_pasta(CHAVE_PASTA_RAIZ) or prefs.get_default_dir("sobressalentes_pmib")
                           or "")
        self.template = prefs.get_last_file(CHAVE_TEMPLATE) or self._template_da_pasta()
        self.caminho_mapeadora = prefs.get_last_file(prefs.CHAVE_MAPEAMENTO) or ""
        self.sistemas: list[lp_svc.Sistema] = []
        self._cancelado = threading.Event()
        super().__init__(parent, controller, titulo=t(TITULO), com_progresso=True, embutida=embutida,
                         console_externo=console_externo, progresso_externo=progresso_externo)

    @staticmethod
    def _template_da_pasta() -> str:
        pasta = prefs.get_default_dir("templates_ficha")
        candidato = Path(pasta) / lp_svc.NOME_TEMPLATE if pasta else None
        return str(candidato) if candidato is not None and candidato.is_file() else ""

    def _build_ui(self) -> None:
        lay = self.content_layout
        cartao = blocos.cartao(lay)
        self.btn_pasta = blocos.botao(t("Pasta raiz..."), variante="cinza", largura_minima=140)
        self.btn_pasta.clicked.connect(self._sel_pasta)
        self.lbl_pasta = blocos.rotulo(t("Não selecionada"), alinhar="esquerda", elidir=True, papel="legenda")
        self.btn_template = blocos.botao(t("Template..."), variante="cinza", largura_minima=120)
        self.btn_template.clicked.connect(self._sel_template)
        self.lbl_template = blocos.rotulo(t("Não selecionado"), alinhar="esquerda", elidir=True, papel="legenda")
        linha_ = QHBoxLayout()
        linha_.setSpacing(10)
        for widget, peso in ((self.btn_pasta, 0), (self.lbl_pasta, 1), (self.btn_template, 0),
                             (self.lbl_template, 1)):
            linha_.addWidget(widget, peso)
        cartao.addLayout(linha_)

        self.btn_varrer = blocos.botao(t("Procurar sistemas"), variante="primario", largura_minima=170, negrito=True)
        self.btn_varrer.clicked.connect(self._varrer)
        self.btn_criar = blocos.botao(t("Criar listas com preço"), variante="primario", largura_minima=190,
                                      negrito=True)
        self.btn_criar.clicked.connect(self._criar)
        self.btn_criar.setEnabled(False)
        self.btn_parar = blocos.botao(t("Parar"), variante="perigo", largura_minima=90)
        self.btn_parar.clicked.connect(self._cancelado.set)
        cartao.addLayout(_linha(self.btn_varrer, self.btn_criar, self.btn_parar))

        self.lbl_totais = blocos.rotulo("", alinhar="esquerda", negrito=True)
        lay.addWidget(self.lbl_totais)
        self.tabela = _tabela(COLUNAS_CRIAR)
        lay.addWidget(self.tabela, 1)
        self._mostrar_arquivos()

    def _mostrar_arquivos(self) -> None:
        if self.pasta_raiz:
            blocos.marcar_arquivo_escolhido(self.btn_pasta, self.lbl_pasta, self.pasta_raiz)
        if self.template:
            blocos.marcar_arquivo_escolhido(self.btn_template, self.lbl_template, self.template)
            self.lbl_template.setToolTip(self.template)

    def _sel_pasta(self) -> None:
        pasta = file_dialogs.ask_directory(CHAVE_PASTA_RAIZ, "pasta",
                                           titulo=t("Selecione a pasta raiz das listas (SOBRESSALENTES - PMIB)"))
        if pasta:
            self.pasta_raiz = pasta
            self._mostrar_arquivos()

    def _sel_template(self) -> None:
        caminho = file_dialogs.ask_open_file(CHAVE_TEMPLATE, "excel", titulo=t("Template da lista com preço"),
                                             filetypes=[("Excel", "*.xlsm *.xlsx")])
        if not caminho:
            return
        self.template = caminho
        try:
            prefs.remember_file(CHAVE_TEMPLATE, caminho)
        except Exception:  # noqa: BLE001 -- lembrar é conveniência
            pass
        self._mostrar_arquivos()

    # -- procurar -------------------------------------------------------------
    def _varrer(self) -> None:
        if not self.pasta_raiz:
            self.avisar(t(TITULO), t(AVISO_SEM_RAIZ), "aviso")
            return
        self.iniciar_tarefa(self._worker_varrer, self.pasta_raiz, botao=self.btn_varrer)

    def _worker_varrer(self, raiz: str) -> None:
        self.log(f"Procurando os sistemas com _STATUS_PMIB em {raiz}...")
        sistemas = lp_svc.varrer(raiz)
        sem = sum(1 for s in sistemas if s.lista is None)
        legado = sum(1 for s in sistemas if s.legado)
        self.log(f"{len(sistemas)} sistema(s): {sem} sem lista com preço, {legado} com lista no formato "
                 f"legado (PB020-0x).")
        interface.na_interface(self._mostrar_sistemas, sistemas)

    def _mostrar_sistemas(self, sistemas) -> None:
        self.sistemas = list(sistemas)
        self.tabela.clear()
        for indice, sistema in enumerate(self.sistemas):
            if sistema.lista is None:
                tem = t(NAO_TEM)
            else:
                tem = t(TEM_LEGADO) if sistema.legado else t(TEM)
            materiais = t(ILEGIVEL, erro=sistema.erro) if sistema.erro else str(sistema.materiais)
            item = dialogos_selecao.linha_ttk(self.tabela, (sistema.codigo, str(sistema.pasta), tem, materiais),
                                              chave=indice)
            if sistema.lista is None and not sistema.erro:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked)
            else:
                # Já tem lista (ou o _STATUS_PMIB não abre): não há o que criar, sem caixa.
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            item.setToolTip(1, str(sistema.pasta))
        dialogos_selecao.ajustar_ao_conteudo(self.tabela)
        sem = sum(1 for s in self.sistemas if s.lista is None)
        self.lbl_totais.setText(t("{n} sistema(s), {sem} sem lista com preço", n=len(self.sistemas), sem=sem))
        self.btn_criar.setEnabled(sem > 0)

    def marcados(self) -> list[lp_svc.Sistema]:
        escolhidos = []
        for linha in range(self.tabela.topLevelItemCount()):
            item = self.tabela.topLevelItem(linha)
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable and item.checkState(0) == Qt.CheckState.Checked:
                escolhidos.append(self.sistemas[item.data(0, Qt.ItemDataRole.UserRole)])
        return escolhidos

    # -- criar ----------------------------------------------------------------
    def _criar(self) -> None:
        if not self.template:
            self.avisar(t(TITULO), t(AVISO_SEM_TEMPLATE), "aviso")
            return
        escolhidos = self.marcados()
        if not escolhidos:
            self.avisar(t(TITULO), t(AVISO_NADA_MARCADO), "aviso")
            return
        self._cancelado.clear()
        self.iniciar_tarefa(self._worker_criar, escolhidos, self.template, self.caminho_mapeadora,
                            botao=self.btn_criar)

    def _titulos(self, caminho_mapeadora: str) -> dict[str, str]:
        """O título de cada lista (DESCRIÇÃO da mapeadora), quando a mapeadora abre."""
        if not caminho_mapeadora:
            return {}
        try:
            mapeadora = conferencia_svc.ler_mapeadora(caminho_mapeadora)
        except Exception as erro:  # noqa: BLE001 -- sem título, a Capa leva o nome da pasta
            self.log(f"  ⚠️ Mapeadora não lida ({erro}): o título da Capa será o nome da pasta.")
            return {}
        return {lista.codigo.strip().upper(): lista.descricao for lista in mapeadora.listas if lista.descricao}

    def _worker_criar(self, escolhidos, template: str, caminho_mapeadora: str) -> None:
        for sistema in escolhidos:
            self.log(f"  {sistema.codigo} → {sistema.pasta}")
        if not self.perguntar_sim_nao(t(TITULO), t(PERGUNTA_CRIAR, n=len(escolhidos))):
            self.log("Lista de Preços cancelada: nada foi criado.")
            return
        lp_svc.criar_listas(escolhidos, template, titulos=self._titulos(caminho_mapeadora), log_cb=self.log,
                            progress_cb=self._progresso, cancelado_cb=self._cancelado.is_set)
        self._worker_varrer(self.pasta_raiz)

    def _progresso(self, fracao: float) -> None:
        if self.progress_bar is not None:
            interface.na_interface(blocos.definir_progresso, self.progress_bar, fracao)


# ------------------------------------------------------------------ Conferir

class ModuloListaPrecosConferir(ModuleFrame):
    def __init__(self, parent=None, controller=None, *, embutida=False, console_externo=None,
                 progresso_externo=None) -> None:
        self.pasta = ""
        self.conferencia: lp_svc.Conferencia | None = None
        super().__init__(parent, controller, titulo=t(TITULO), com_progresso=True, embutida=embutida,
                         console_externo=console_externo, progresso_externo=progresso_externo)

    def _build_ui(self) -> None:
        lay = self.content_layout
        cartao = blocos.cartao(lay)
        self.btn_pasta = blocos.botao(t("Pasta do sistema..."), variante="cinza", largura_minima=170)
        self.btn_pasta.clicked.connect(self._sel_pasta)
        self.lbl_pasta = blocos.rotulo(t("Não selecionada"), alinhar="esquerda", elidir=True, papel="legenda")
        self.btn_abrir = blocos.botao(t("Abrir a pasta"), variante="cinza", largura_minima=130)
        self.btn_abrir.clicked.connect(self._abrir_pasta)
        self.btn_abrir.setEnabled(False)
        linha_ = QHBoxLayout()
        linha_.setSpacing(10)
        for widget, peso in ((self.btn_pasta, 0), (self.lbl_pasta, 1), (self.btn_abrir, 0)):
            linha_.addWidget(widget, peso)
        cartao.addLayout(linha_)

        self.btn_conferir = blocos.botao(t("Conferir"), variante="primario", largura_minima=130, negrito=True)
        self.btn_conferir.clicked.connect(self._conferir)
        self.btn_atualizar = blocos.botao(t("Atualizar a lista"), variante="primario", largura_minima=160,
                                          negrito=True)
        self.btn_atualizar.clicked.connect(self._atualizar)
        self.btn_atualizar.setEnabled(False)
        cartao.addLayout(_linha(self.btn_conferir, self.btn_atualizar))

        self.lbl_aviso = blocos.rotulo("", alinhar="esquerda", negrito=True)
        self.lbl_aviso.setWordWrap(True)
        lay.addWidget(self.lbl_aviso)
        self.lbl_totais = blocos.rotulo("", alinhar="esquerda", papel="legenda")
        lay.addWidget(self.lbl_totais)
        self.tabela = _tabela(COLUNAS_CONFERIR)
        lay.addWidget(self.tabela, 1)

    def _sel_pasta(self) -> None:
        pasta = file_dialogs.ask_directory(CHAVE_PASTA_SISTEMA, "pasta",
                                           titulo=t("Selecione a pasta do sistema (com o _STATUS_PMIB)"))
        if pasta:
            self.definir_pasta(pasta)

    def definir_pasta(self, pasta: str) -> None:
        self.pasta = pasta
        blocos.marcar_arquivo_escolhido(self.btn_pasta, self.lbl_pasta, pasta)
        self.lbl_pasta.setToolTip(pasta)
        self.btn_abrir.setEnabled(True)
        self.conferencia = None
        self.btn_atualizar.setEnabled(False)
        self.tabela.clear()
        self.lbl_aviso.setText("")
        self.lbl_totais.setText("")

    def _abrir_pasta(self) -> None:
        """O link da pasta: a conferência humana da divergência é no Excel, ali."""
        if self.pasta:
            try:
                plataforma.abrir_no_sistema(self.pasta)
            except Exception as erro:  # noqa: BLE001 -- vira log
                self.log(f"Não foi possível abrir a pasta: {erro}")

    def _conferir(self) -> None:
        if not self.pasta:
            self.avisar(t(TITULO), t(AVISO_SEM_PASTA), "aviso")
            return
        self.iniciar_tarefa(self._worker_conferir, self.pasta, botao=self.btn_conferir)

    def _worker_conferir(self, pasta: str) -> None:
        self.log(f"Conferindo a lista com preço de {pasta}...")
        try:
            conferencia = lp_svc.conferir(pasta)
        except (lp_svc.ErroListaDePrecos, ValueError) as erro:
            self.log(f"  ❌ {erro}")
            interface.na_interface(self._mostrar_erro, str(erro))
            return
        self.log(f"  {conferencia.sistema.lista.name}: {len(conferencia.itens_lista)} item(ns); _STATUS_PMIB: "
                 f"{len(conferencia.itens_status)}; {len(conferencia.divergencias)} divergência(s)"
                 + ("; lista valorizada" if conferencia.valorizada else "") + ".")
        interface.na_interface(self._mostrar_conferencia, conferencia)

    def _mostrar_erro(self, erro: str) -> None:
        self.conferencia = None
        self.tabela.clear()
        self.btn_atualizar.setEnabled(False)
        self.lbl_aviso.setText(erro)
        estilo.definir_papel(self.lbl_aviso, "erro")

    def _mostrar_conferencia(self, conferencia) -> None:
        self.conferencia = conferencia
        self.tabela.clear()
        for d in conferencia.divergencias:
            dialogos_selecao.linha_ttk(self.tabela, (t(TIPOS[d.tipo]), d.item, d.campo, d.no_status, d.na_lista))
        dialogos_selecao.ajustar_ao_conteudo(self.tabela)
        if conferencia.em_dia:
            self.lbl_aviso.setText(t(EM_DIA))
            estilo.definir_papel(self.lbl_aviso, "ok")
        elif conferencia.valorizada:
            self.lbl_aviso.setText(t(AVISO_VALORIZADA))
            estilo.definir_papel(self.lbl_aviso, "aviso")
        else:
            self.lbl_aviso.setText("")
            estilo.definir_papel(self.lbl_aviso, None)
        self.lbl_totais.setText(t("{arquivo}: {n} divergência(s)", arquivo=conferencia.sistema.lista.name,
                                  n=len(conferencia.divergencias)))
        self.btn_atualizar.setEnabled(not conferencia.em_dia)

    def _atualizar(self) -> None:
        if self.conferencia is None:
            return
        self.iniciar_tarefa(self._worker_atualizar, self.conferencia, botao=self.btn_atualizar)

    def _worker_atualizar(self, conferencia) -> None:
        arquivo = conferencia.sistema.lista.name
        pergunta = PERGUNTA_ATUALIZAR_VALORIZADA if conferencia.valorizada else PERGUNTA_ATUALIZAR
        if not self.perguntar_sim_nao(t(TITULO), t(pergunta, arquivo=arquivo)):
            self.log("Atualização cancelada: a lista ficou como estava.")
            return
        while True:
            try:
                lp_svc.atualizar(conferencia, log_cb=self.log)
                break
            except PermissionError:
                if not self.perguntar_retry_excel(conferencia.sistema.lista):
                    self.log(f"  ❌ {arquivo} está aberto no Excel: nada foi escrito.")
                    return
        self._worker_conferir(str(conferencia.sistema.pasta))


# ------------------------------------------------------------------ a seção

class ModuloListaPrecos(ModuleFrame):
    """Cabeçalho + abas (Criar / preencher, Conferir) + barra + console compartilhados."""

    def __init__(self, parent=None, controller=None) -> None:
        super().__init__(parent, controller, titulo=t(TITULO), peso_conteudo=3, com_progresso=True)

    def _build_ui(self) -> None:
        blocos.barra_progresso(barra=self.progress_bar, largura=600, altura=12)
        self.layout().setAlignment(self.progress_bar, Qt.AlignmentFlag.AlignHCenter)
        blocos.definir_progresso(self.progress_bar, 0)
        self.abas = Abas()
        self.content_layout.addWidget(self.abas)
        da_secao = {"controller": self.controller, "embutida": True, "console_externo": self.console,
                    "progresso_externo": self.progress_bar}
        self.tela_criar = ModuloListaPrecosCriar(**da_secao)
        self.tela_conferir = ModuloListaPrecosConferir(**da_secao)
        for nome, tela in ((ABA_CRIAR, self.tela_criar), (ABA_CONFERIR, self.tela_conferir)):
            tela.layout().setContentsMargins(MARGEM_DA_ROLAGEM, MARGEM_DA_ROLAGEM,
                                             MARGEM_DIREITA_DA_ROLAGEM, MARGEM_DA_ROLAGEM)
            self.abas.add(t(nome)).layout().addWidget(tela)
        self.abas.set(t(ABA_CRIAR))
        instalar_como_funciona(self, {t(ABA_CRIAR): "ListaPrecos.criar",  # nao-e-interface
                                      t(ABA_CONFERIR): "ListaPrecos.conferir"}, abas=self.abas)  # nao-e-interface
