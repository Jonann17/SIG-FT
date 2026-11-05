"""Aba "DocPack" do PMIB Manager: monta a pasta de cada lista de sobressalentes que ainda
não tem `_STATUS_PMIB`, com os templates (o `_STATUS_PMIB` e a Aplicação LMR) e as
subpastas LMR, IMAGENS e DATASHEETS. A lista com preço é do módulo Lista de Preços.

A tela é fina: quais listas, onde e o que vai em cada dossiê estão em
`services/docpack.py`. A tabela mostra as listas da mapeadora sem `_STATUS_PMIB`;
as colunas de pasta (ET, capítulo, sistema, subsistema, pasta final -- a hierarquia
da ET, corrigida pelo Luan em 2026-11-04) se editam com dois cliques, numa lista com
as pastas que já existem naquele nível (dentro das escolhidas à esquerda) ou com um
nome novo digitado, ou pelo "Sugerir com IA". `/` numa célula põe mais uma pasta
naquele passo.
Desenho: `docs/superpowers/specs/2026-11-03-docpack-design.md`.
"""
from __future__ import annotations

import os
import threading
import weakref
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QCompleter, QHBoxLayout, QStyledItemDelegate

from sigft.app.idioma import marcar, t
from sigft.app_qt import file_dialogs, interface, propriedades
from sigft.app_qt.widgets import blocos, dialogos_selecao
from sigft.app_qt.widgets.module_frame import ModuleFrame
from sigft.core import prefs
from sigft.services import conferencia_revisoes as conferencia_svc
from sigft.services import docpack as docpack_svc

TITULO = marcar("DocPack")
CHAVE_PASTA_RAIZ = "docpack.raiz"
CHAVES_TEMPLATE = {"status_pmib": "docpack.template_status_pmib", "aplicacao_lmr": "docpack.template_aplicacao_lmr"}
AVISO_SEM_MAPEADORA = marcar("Selecione a mapeadora antes.")
AVISO_SEM_RAIZ = marcar("Selecione a pasta raiz antes.")
AVISO_SEM_TEMPLATE = marcar("Selecione o template do _STATUS_PMIB antes.")
AVISO_NADA_MARCADO = marcar("Marque pelo menos uma lista.")
PERGUNTA_CRIAR = marcar("Criar {n} dossiê(s) em {raiz}?")

# Os nomes vão em `marcar` e são traduzidos onde a tabela é montada (`t(c)`). As larguras
# somam 850: cabem na aba a 1280x850 (as colunas esticam, mas não encolhem).
COLUNAS = (
    (marcar("Código"), 140),
    (marcar("Título"), 170),
    (marcar("ET"), 120),
    (marcar("Capítulo"), 110),
    (marcar("Sistema"), 100),
    (marcar("Subsistema"), 110),
    (marcar("Pasta final"), 100),
)
COL_ET, COL_CAPITULO, COL_SISTEMA, COL_SUBSISTEMA, COL_PASTA = 2, 3, 4, 5, 6
# Coluna -> nível do `docpack_svc.Destino`, na ordem do caminho.
NIVEL_DA_COLUNA = dict(zip((COL_ET, COL_CAPITULO, COL_SISTEMA, COL_SUBSISTEMA, COL_PASTA), docpack_svc.NIVEIS))
EDITAVEIS = tuple(NIVEL_DA_COLUNA)
LEGENDA = marcar("Dois cliques numa pasta: escolha uma que já existe ou digite outra. "
                 "Mais uma pasta num passo: separe com / (ex.: MANCAIS/GUIA).")

TEXTOS_TEMPLATE = {"status_pmib": marcar("_STATUS_PMIB..."), "aplicacao_lmr": marcar("Aplicação LMR...")}
FILTROS_TEMPLATE = {"status_pmib": [("Excel", "*.xlsx")], "aplicacao_lmr": [("Excel", "*.xlsx *.xlsm")]}


def _linha(*widgets) -> QHBoxLayout:
    linha_ = QHBoxLayout()
    linha_.setSpacing(10)
    for widget in widgets:
        linha_.addWidget(widget)
    linha_.addStretch()
    return linha_


class _EditorDePasta(QStyledItemDelegate):
    """Só as colunas de pasta se editam, numa lista editável com as pastas que já
    existem naquele nível, dentro das escolhidas nas colunas à esquerda; o nome
    digitado vale do mesmo jeito (pasta nova)."""

    def __init__(self, tela) -> None:
        super().__init__(tela.tabela)
        # Fraca: a tabela (filha da tela) segura este editor; uma referência forte de
        # volta fecharia um ciclo (ver `widgets/fraco.py`).
        self._tela = weakref.ref(tela)

    def createEditor(self, pai, _opcao, indice):  # noqa: N802 -- nome do Qt
        tela = self._tela()
        if tela is None or indice.column() not in EDITAVEIS:
            return None
        campo = QComboBox(pai)
        campo.setEditable(True)
        campo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        sugestoes = tela.sugestoes_para(indice.row(), indice.column())
        campo.addItems(sugestoes)
        completar = QCompleter(sugestoes, campo)
        completar.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completar.setFilterMode(Qt.MatchFlag.MatchContains)
        campo.setCompleter(completar)
        return campo

    def setEditorData(self, campo, indice) -> None:  # noqa: N802 -- nome do Qt
        campo.setEditText(str(indice.data(Qt.ItemDataRole.DisplayRole) or ""))

    def setModelData(self, campo, modelo, indice) -> None:  # noqa: N802 -- nome do Qt
        modelo.setData(indice, " ".join(campo.currentText().split()), Qt.ItemDataRole.EditRole)


class ModuloDocPack(ModuleFrame):
    def __init__(self, parent=None, controller=None, *, embutida=False, console_externo=None,
                 progresso_externo=None) -> None:
        self.caminho_mapeadora = prefs.get_last_file(prefs.CHAVE_MAPEAMENTO) or ""
        self.pasta_raiz = (prefs.ultima_pasta(CHAVE_PASTA_RAIZ) or prefs.get_default_dir("sobressalentes_pmib")
                           or "")
        self.templates = self._templates_lembrados()
        self.listas: list[conferencia_svc.ListaNaMapeadora] = []
        # As pastas que já existem sob a raiz (`docpack_svc.arvore_existente`).
        self.existentes: dict = {}
        self._cancelado = threading.Event()
        super().__init__(parent, controller, titulo=t(TITULO), com_progresso=True, embutida=embutida,
                         console_externo=console_externo, progresso_externo=progresso_externo)

    @staticmethod
    def _templates_lembrados() -> docpack_svc.Templates:
        """O último de cada template; o que faltar, pelo nome conhecido na pasta Templates."""
        achados = docpack_svc.achar_templates(prefs.get_default_dir("templates_ficha"))
        for campo, chave in CHAVES_TEMPLATE.items():
            lembrado = prefs.get_last_file(chave)
            if lembrado:
                setattr(achados, campo, lembrado)
        return achados

    # -- montagem ----------------------------------------------------------
    def _build_ui(self) -> None:
        lay = self.content_layout
        cartao = blocos.cartao(lay)

        self.btn_mapeadora = blocos.botao(t("Mapeadora..."), variante="cinza", largura_minima=140)
        self.btn_mapeadora.clicked.connect(self._sel_mapeadora)
        self.lbl_mapeadora = blocos.rotulo(t("Não selecionada"), alinhar="esquerda", elidir=True, papel="legenda")
        self.btn_pasta = blocos.botao(t("Pasta raiz..."), variante="cinza", largura_minima=140)
        self.btn_pasta.clicked.connect(self._sel_pasta)
        self.lbl_pasta = blocos.rotulo(t("Não selecionada"), alinhar="esquerda", elidir=True, papel="legenda")
        linha_ = QHBoxLayout()
        linha_.setSpacing(10)
        for widget, peso in ((self.btn_mapeadora, 0), (self.lbl_mapeadora, 1), (self.btn_pasta, 0),
                             (self.lbl_pasta, 1)):
            linha_.addWidget(widget, peso)
        cartao.addLayout(linha_)

        self.botoes_template, self.rotulos_template = {}, {}
        linha_ = QHBoxLayout()
        linha_.setSpacing(10)
        for campo, texto in TEXTOS_TEMPLATE.items():
            botao = blocos.botao(t(texto), variante="cinza", largura_minima=140)
            botao.setProperty("campo", campo)
            botao.clicked.connect(self._sel_template)
            rotulo = blocos.rotulo(t("Não selecionado"), alinhar="esquerda", elidir=True, papel="legenda")
            self.botoes_template[campo], self.rotulos_template[campo] = botao, rotulo
            linha_.addWidget(botao)
            linha_.addWidget(rotulo, 1)
        cartao.addLayout(linha_)

        self.btn_listar = blocos.botao(t("Listar sem _STATUS_PMIB"), variante="primario", largura_minima=180,
                                       negrito=True)
        self.btn_listar.clicked.connect(self._listar)
        self.btn_ia = blocos.botao(t("Sugerir com IA"), variante="cinza", largura_minima=140)
        self.btn_ia.clicked.connect(self._sugerir)
        self.btn_previa = blocos.botao(t("Pré-visualizar"), variante="cinza", largura_minima=130)
        self.btn_previa.clicked.connect(self._previsualizar)
        self.btn_criar = blocos.botao(t("Criar dossiês"), variante="primario", largura_minima=140, negrito=True)
        self.btn_criar.clicked.connect(self._criar)
        self.btn_parar = blocos.botao(t("Parar"), variante="perigo", largura_minima=90)
        self.btn_parar.clicked.connect(self._parar)
        cartao.addLayout(_linha(self.btn_listar, self.btn_ia, self.btn_previa, self.btn_criar, self.btn_parar))

        self.lbl_totais = blocos.rotulo("", alinhar="esquerda", negrito=True)
        self.lbl_totais.setWordWrap(False)   # divide a linha com a legenda: não quebra
        self.lbl_legenda = blocos.rotulo(t(LEGENDA), alinhar="esquerda", papel="legenda", elidir=True)
        self.lbl_legenda.setToolTip(t(LEGENDA))
        linha_ = QHBoxLayout()
        linha_.setSpacing(10)
        linha_.addWidget(self.lbl_totais)
        linha_.addWidget(self.lbl_legenda, 1)
        lay.addLayout(linha_)
        self.tabela = dialogos_selecao.tabela_ttk([(t(c), largura, "w") for c, largura in COLUNAS])
        # [2026-11-05] Barra de rolagem de lado (pedido do Jonathan): a coluna cresce
        # até caber o texto (`ajustar_ao_conteudo`) e o que não cabe na tela rola.
        self.tabela.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.tabela.setEditTriggers(self.tabela.EditTrigger.DoubleClicked | self.tabela.EditTrigger.EditKeyPressed)
        self.tabela.setItemDelegate(_EditorDePasta(self))
        lay.addWidget(self.tabela, 1)
        self._mostrar_arquivos()

    def _mostrar_arquivos(self) -> None:
        if self.caminho_mapeadora:
            blocos.marcar_arquivo_escolhido(self.btn_mapeadora, self.lbl_mapeadora, self.caminho_mapeadora)
        if self.pasta_raiz:
            blocos.marcar_arquivo_escolhido(self.btn_pasta, self.lbl_pasta, self.pasta_raiz)
        for campo, botao in self.botoes_template.items():
            caminho = getattr(self.templates, campo)
            if caminho:
                blocos.marcar_arquivo_escolhido(botao, self.rotulos_template[campo], caminho)
                self.rotulos_template[campo].setToolTip(caminho)

    # -- arquivos ----------------------------------------------------------
    def _sel_mapeadora(self) -> None:
        caminho = file_dialogs.ask_open_file("pmib_manager.master", "excel", titulo=t("Selecione a mapeadora"),
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
                                           titulo=t("Selecione a pasta raiz das listas (SOBRESSALENTES - PMIB)"))
        if pasta:
            self.pasta_raiz = pasta
            self._mostrar_arquivos()

    def _sel_template(self) -> None:
        campo = propriedades.ler(self.sender(), "campo")
        caminho = file_dialogs.ask_open_file(CHAVES_TEMPLATE[campo], "excel", titulo=t(TEXTOS_TEMPLATE[campo]),
                                             filetypes=FILTROS_TEMPLATE[campo])
        if not caminho:
            return
        setattr(self.templates, campo, caminho)
        try:
            prefs.remember_file(CHAVES_TEMPLATE[campo], caminho)
        except Exception:  # noqa: BLE001 -- lembrar é conveniência
            pass
        self._mostrar_arquivos()

    # -- a tabela ----------------------------------------------------------
    def _destino_da_linha(self, item) -> docpack_svc.Destino:
        return docpack_svc.Destino(**{nivel: item.text(coluna).strip() for coluna, nivel in NIVEL_DA_COLUNA.items()})

    def sugestoes_para(self, linha: int, coluna: int) -> list[str]:
        """As pastas que já existem para a coluna, dentro das escolhidas nas colunas de
        pasta à esquerda (as vazias são puladas)."""
        item = self.tabela.topLevelItem(linha)
        if item is None or coluna not in NIVEL_DA_COLUNA:
            return []
        return docpack_svc.opcoes_do_nivel(self.existentes, self._destino_da_linha(item), NIVEL_DA_COLUNA[coluna])

    def _mostrar_listas(self, listas, existentes) -> None:
        self.listas, self.existentes = list(listas), dict(existentes)
        self.tabela.clear()
        for indice, lista in enumerate(self.listas):
            item = dialogos_selecao.linha_ttk(self.tabela, (lista.codigo, lista.descricao) + ("",) * len(EDITAVEIS),
                                              chave=indice)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            item.setToolTip(1, lista.descricao)
        dialogos_selecao.ajustar_ao_conteudo(self.tabela)
        self.lbl_totais.setText(t("{n} lista(s) sem _STATUS_PMIB", n=len(self.listas)))

    def marcadas(self) -> list[tuple[int, docpack_svc.Destino]]:
        """(índice da lista, destino) de cada linha marcada."""
        escolhidas = []
        for linha in range(self.tabela.topLevelItemCount()):
            item = self.tabela.topLevelItem(linha)
            if item.checkState(0) == Qt.CheckState.Checked:
                escolhidas.append((item.data(0, Qt.ItemDataRole.UserRole), self._destino_da_linha(item)))
        return escolhidas

    def _preencher(self, indice: int, destino: docpack_svc.Destino, motivo: str) -> None:
        item = self.tabela.topLevelItem(indice)
        if item is None:
            return
        for coluna, nivel in NIVEL_DA_COLUNA.items():
            item.setText(coluna, getattr(destino, nivel))
        dialogos_selecao.ajustar_ao_conteudo(self.tabela)
        if motivo:
            for coluna in EDITAVEIS:
                item.setToolTip(coluna, motivo)

    # -- listar ------------------------------------------------------------
    def _listar(self) -> None:
        if not self.caminho_mapeadora:
            self.avisar(t(TITULO), t(AVISO_SEM_MAPEADORA), "aviso")
            return
        if not self.pasta_raiz:
            self.avisar(t(TITULO), t(AVISO_SEM_RAIZ), "aviso")
            return
        self.iniciar_tarefa(self._worker_listar, self.caminho_mapeadora, self.pasta_raiz, botao=self.btn_listar)

    def _worker_listar(self, caminho: str, raiz: str) -> None:
        self.log(f"Lendo a mapeadora {os.path.basename(caminho)}...")
        try:
            mapeadora = conferencia_svc.ler_mapeadora(caminho)
        except Exception as erro:  # noqa: BLE001 -- planilha do usuário
            self.log(f"[ERRO] Não consegui ler a mapeadora: {erro}")
            return
        listas = docpack_svc.listas_sem_status_pmib(mapeadora, raiz)
        existentes = docpack_svc.arvore_existente(raiz)
        self.log(f"{len(listas)} lista(s) sem _STATUS_PMIB, de {len(mapeadora.listas)} na mapeadora.")
        interface.na_interface(self._mostrar_listas, listas, existentes)

    # -- a IA --------------------------------------------------------------
    def _sugerir(self) -> None:
        marcadas = self.marcadas()
        if not marcadas:
            self.avisar(t(TITULO), t(AVISO_NADA_MARCADO), "aviso")
            return
        self.iniciar_tarefa(self._worker_sugerir, [i for i, _ in marcadas], botao=self.btn_ia)

    def _cliente_ia(self):
        from sigft.core.llm.client import get_llm
        chave = self.controller.get_key("GEMINI") if self.controller is not None else None
        return get_llm(docpack_svc.TAREFA_IA, chave or None)

    def _worker_sugerir(self, indices: list[int]) -> None:
        try:
            llm = self._cliente_ia()
        except Exception as erro:  # noqa: BLE001 -- sem IA, digita-se
            self.log(f"[AVISO] A IA não está disponível: {erro}")
            return
        self.log(f"Pedindo à IA a pasta de {len(indices)} lista(s)...")
        for indice in indices:
            lista = self.listas[indice]
            destino, motivo = docpack_svc.sugerir_destino(lista, self.existentes, llm)
            if destino is None:
                self.log(f"  ⚠️ {lista.codigo}: {motivo}")
                continue
            caminho = " / ".join(valor or "-" for _, valor in destino.niveis())
            self.log(f"  ✅ {lista.codigo}: {caminho}")
            interface.na_interface(self._preencher, indice, destino, motivo)

    # -- prévia e criação ---------------------------------------------------
    def _pedidos(self) -> list | None:
        """Os pedidos marcados, ou `None` (com o aviso) se falta algo para começar."""
        if not self.pasta_raiz:
            self.avisar(t(TITULO), t(AVISO_SEM_RAIZ), "aviso")
            return None
        if not self.templates.status_pmib:
            self.avisar(t(TITULO), t(AVISO_SEM_TEMPLATE), "aviso")
            return None
        marcadas = self.marcadas()
        if not marcadas:
            self.avisar(t(TITULO), t(AVISO_NADA_MARCADO), "aviso")
            return None
        return [(self.listas[i], destino) for i, destino in marcadas]

    def _logar_plano(self, pedidos, raiz: str) -> int:
        """Escreve no console o que seria criado; devolve quantas listas têm destino válido."""
        validas = 0
        for lista, destino in pedidos:
            try:
                passos = docpack_svc.planejar(lista, raiz, destino, self.templates)
            except docpack_svc.ErroDocPack as erro:
                self.log(f"  ❌ {lista.codigo}: {erro}")
                continue
            validas += 1
            self.log(f"  {lista.codigo} → {docpack_svc.pasta_do_dossie(raiz, destino)}")
            for passo in passos:
                relativo = passo.caminho.relative_to(raiz)
                self.log(f"      {'=' if passo.existe else '+'} {relativo}" + (" (já existe)" if passo.existe else ""))
        return validas

    def _previsualizar(self) -> None:
        pedidos = self._pedidos()
        if pedidos is not None:
            self.iniciar_tarefa(self._worker_previa, pedidos, self.pasta_raiz, botao=self.btn_previa)

    def _worker_previa(self, pedidos, raiz: str) -> None:
        self.log(f"Prévia do DocPack: {len(pedidos)} lista(s). Nada foi criado.")
        self._logar_plano(pedidos, raiz)

    def _criar(self) -> None:
        pedidos = self._pedidos()
        if pedidos is None:
            return
        self._cancelado.clear()
        self.iniciar_tarefa(self._worker_criar, pedidos, self.pasta_raiz,
                            docpack_svc.Templates(**vars(self.templates)), botao=self.btn_criar)

    def _worker_criar(self, pedidos, raiz: str, templates: docpack_svc.Templates) -> None:
        validas = self._logar_plano(pedidos, raiz)
        if not validas:
            return
        if not self.perguntar_sim_nao(t(TITULO), t(PERGUNTA_CRIAR, n=validas, raiz=raiz)):
            self.log("DocPack cancelado: nada foi criado.")
            return
        resultados = docpack_svc.criar_dossies(pedidos, Path(raiz), templates, log_cb=self.log,
                                               progress_cb=self._progresso, cancelado_cb=self._cancelado.is_set)
        # [2026-11-05] O link do Box na mapeadora, para a Conferência de Listas.
        if self.caminho_mapeadora and resultados:
            n = docpack_svc.gravar_links(self.caminho_mapeadora, resultados, log_cb=self.log,
                                         retry_lock=self.perguntar_retry_excel)
            self.log(f"DocPack: {n} link(s) gravado(s) na mapeadora (LINK DA PLANILHA).")

    def _progresso(self, fracao: float) -> None:
        if self.progress_bar is not None:
            interface.na_interface(blocos.definir_progresso, self.progress_bar, fracao)

    def _parar(self) -> None:
        self._cancelado.set()
        self.log("Parada pedida: termino a lista em andamento e paro.")
