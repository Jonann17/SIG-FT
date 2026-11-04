"""Tela "Analyzer" (IA) na interface Qt.

Mesma tela da interface antiga (`sigft/app/views/analyzer.py`, removida em 2026-10-15): valida e pontua fichas técnicas
com IA, separando as aprovadas das que voltam para o fornecedor, e gera o
relatório de pendências em Excel.

Os blocos que `TRABALHO_PARALELO.md` §3.1 manda viajar com a classe estão
aqui: `_perguntar_descricao`, `_gerar_relatorio`, `relatorio_analise`,
`btn_relatorio`, `_parar_de_perguntar_desc` e o import de
`analyzer_relatorio` no topo (fora do carregamento preguiçoso, de propósito).

`_perguntar_descricao` continua precisando de um `self` que seja widget: é
chamado PELO BACKEND, de dentro do worker. Lá ele usava `self.after(0, ...)` +
`Event`; aqui usa `self.pedir_texto` (DialogosDeEspera), que faz o mesmo -- a
janela nasce na thread da interface e o worker espera.

O que muda é só como o worker fala com a pessoa: lá `messagebox` e
`btn.configure` eram chamados de dentro da thread (proibido no Tk); aqui é
`self.avisar(...)`, `interface.na_interface` e `iniciar_tarefa`.
"""
from __future__ import annotations

import os

import openpyxl
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QVBoxLayout,
)

from sigft.app import ia_por_modulo
from sigft.app.idioma import t
from sigft.app_qt import estilo, icones, interface
from sigft.app_qt.widgets import blocos
from sigft.app_qt.widgets import pickers as app_pickers
from sigft.app_qt.widgets.como_funciona import instalar_como_funciona
from sigft.app_qt.widgets.ia_do_modulo import instalar_configurar_ia
from sigft.app_qt.widgets.module_frame import ModuleFrame
from sigft.services import analyzer_relatorio

def _rotulo(texto: str, *, tamanho: int = 13, negrito: bool = False, papel: str | None = None,
            alinhar: str = "esquerda") -> QLabel:
    etiqueta = blocos.rotulo(texto, tamanho=tamanho, negrito=negrito, papel=papel, alinhar=alinhar)
    etiqueta.setWordWrap(False)
    return etiqueta


class JanelaPesos(QDialog):
    """A janela "Configuração de Pesos" (lá um CTkToplevel 500x700, transient e
    sem modal). Os campos ficam na TELA (`entries_pesos`, `entry_max_vars`),
    como lá: é `_salvar_pesos` da tela que os lê."""

    def __init__(self, tela: ModuloAnalyzer, config_map: dict) -> None:
        super().__init__(tela)
        self.setWindowTitle(t("Configuração de Pesos"))
        self.resize(*blocos.geometria_tk("500x700"))
        self.setModal(False)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(10, 10, 10, 0)   # scroll: padx=10, pady=10
        raiz.setSpacing(0)
        # O CTkScrollableFrame de fundo padrão (o fundo da janela), cantos de 6.
        self.area, corpo = blocos.area_rolavel(raiz, fundo="tela", barra_sempre_visivel=True)
        raiz.addSpacing(20)                      # scroll (…, 10) + salvar (10, …)

        self.titulo = _rotulo(t("Pesos dos Campos Fixos"), tamanho=14, negrito=True, alinhar="centro")
        corpo.addSpacing(10)
        corpo.addWidget(self.titulo)
        corpo.addSpacing(10)                     # título (…, 10)

        self.rotulos: list[QLabel] = []
        tela.entries_pesos = {}
        for key, conf in config_map.items():
            # Nome formatado (ex: "tipo_fabricacao" -> "Tipo Fabricacao")
            name_fmt = key.replace("_", " ").title()
            current_val = tela.custom_weights.get(key, conf["weight"])
            rotulo, entry = self._linha(corpo, name_fmt, current_val)
            self.rotulos.append(rotulo)
            tela.entries_pesos[key] = entry

        # Campo Especial: Variáveis Dinâmicas
        corpo.addSpacing(10)                     # traço (10, …); a última linha já pôs os seus 2
        corpo.addWidget(_rotulo("--------------------------------",
                                papel="legenda", alinhar="centro"))
        corpo.addSpacing(15)                     # traço (…, 10) + título (5, …)
        corpo.addWidget(_rotulo(t("Configuração Global"), tamanho=14, negrito=True, alinhar="centro"))
        corpo.addSpacing(5)                      # título (…, 5); a linha põe os seus 5
        _, tela.entry_max_vars = self._linha(corpo, t("Pontos Totais (Specs Técnicas):"),
                                             tela.max_var_points, folga=5)

        self.btn_salvar = blocos.botao(t("Salvar Pesos"), largura=estilo.LARGURA_BOTAO_CTK, altura=28,
                                       variante="primario")
        # Enter num campo não salva: no Tk o Enter não fazia nada aqui.
        self.btn_salvar.setAutoDefault(False)
        self.btn_salvar.setDefault(False)
        self.btn_salvar.clicked.connect(lambda: tela._salvar_pesos(self))
        raiz.addWidget(self.btn_salvar, alignment=Qt.AlignmentFlag.AlignHCenter)
        raiz.addSpacing(10)

    def keyPressEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        # Esc fecharia e perderia os pesos digitados; no Tk não havia tecla nenhuma.
        if evento.key() == Qt.Key.Key_Escape:
            evento.accept()
            return
        super().keyPressEvent(evento)

    @staticmethod
    def _linha(corpo, texto, valor, *, folga: int = 2):
        """`CTkFrame(fill="x", pady=folga)` com rótulo de 250 à esquerda e campo de
        80 à direita."""
        corpo.addSpacing(folga)
        linha = QHBoxLayout()
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(0)
        rotulo = _rotulo(texto)
        rotulo.setFixedWidth(250)
        entry = QLineEdit(str(valor))
        entry.setFixedWidth(80)
        linha.addWidget(rotulo)
        linha.addStretch()
        linha.addWidget(entry)
        corpo.addLayout(linha)
        corpo.addSpacing(folga)
        return rotulo, entry


class ModuloAnalyzer(ModuleFrame):
    def __init__(self, parent=None, controller=None) -> None:
        # Variáveis de Estado
        self.controller = controller
        self.api_key = self._chave_gemini()
        self.selected_files: list[str] = []
        self.selected_output = ""
        self.selected_pmib = ""
        self.score_value = 90.0

        # Pesos Personalizados (Inicialmente vazios, usa padrão do backend)
        self.custom_weights: dict = {}
        self.max_var_points = 45.0  # Valor padrão

        self.relatorio_analise = None
        self._parar_de_perguntar_desc = False
        self.janela_pesos = None
        super().__init__(parent, controller, titulo=t("Technical Datasheet Analyzer"))

    def _chave_gemini(self) -> str:
        return self.controller.get_key("GEMINI") if self.controller is not None else ""

    def _build_ui(self) -> None:
        instalar_como_funciona(self, "Analyzer")
        instalar_configurar_ia(self, ia_por_modulo.TAREFAS_DA_TELA.get("ModuloAnalyzer", ()))
        # Lá o conteúdo é um CTkScrollableFrame transparente, com a barra SEMPRE
        # à vista: sem ela os cartões ficariam 11 px mais largos e o que é
        # centrado andaria 5 px.
        self.area, corpo = blocos.area_rolavel(self.content_layout, barra_sempre_visivel=True)

        self.lbl_subtitulo = _rotulo(t("Validação e Pontuação de Fichas Técnicas via IA"), tamanho=16,
                                     alinhar="centro")
        corpo.addWidget(self.lbl_subtitulo)
        corpo.addSpacing(30)                     # subtítulo (…, 20) + cartão (10, …)

        # --- CONTAINER 1: CRITÉRIOS ---
        criterios = self._cartao(corpo)
        self.cartao_criterios = criterios.parentWidget()
        criterios.addWidget(_rotulo(t("1. Critérios de Aprovação e Pesos"), tamanho=14, negrito=True,
                                    papel="destaque"))
        criterios.addSpacing(10)                 # título (…, 5) + controles (5, …)
        controles = QHBoxLayout()
        controles.setContentsMargins(0, 0, 0, 0)
        controles.setSpacing(0)
        self.lbl_score = _rotulo(t("Nota Mínima: {nota}%", nota=int(self.score_value)), tamanho=12, negrito=True,
                                 papel="destaque")
        controles.addWidget(self.lbl_score)
        controles.addSpacing(20)                 # padx=(0, 20)
        self.slider = blocos.slider(minimo=0, maximo=100, largura=300)
        self.slider.setValue(int(self.score_value))
        self.slider.valueChanged.connect(self._update_slider_label)
        controles.addWidget(self.slider)
        controles.addStretch()
        # Botão de Configurar Pesos
        self.btn_config = blocos.botao(t("Configurar Pesos"), largura=150, altura=28, tamanho_fonte=12,
                                       variante="secundario")
        icones.aplicar(self.btn_config, "settings", tamanho=16)   # era o emoji (2026-10-20)
        self.btn_config.clicked.connect(self.abrir_config_pesos)
        controles.addWidget(self.btn_config)
        criterios.addLayout(controles)
        criterios.addSpacing(5)
        corpo.addSpacing(20)                     # cartão (…, 10) + cartão (10, …)

        # --- CONTAINER 2: SELEÇÃO ---
        arquivos = self._cartao(corpo)
        self.cartao_arquivos = arquivos.parentWidget()
        arquivos.addWidget(_rotulo(t("2. Seleção de Arquivos e Pastas"), tamanho=14, negrito=True,
                                   papel="destaque"))

        # [CP 7.2] Cada seletor declara a sua chave da memoria de caminhos UMA
        # vez, aqui; a tela nunca chama file_dialogs.
        # A) Arquivos de Entrada
        self.picker_files = app_pickers.MultiFilePickerRow(
            chave="analyzer.fichas",
            categoria="excel",
            texto_botao=t("Selecionar Fichas (.xlsx)"),
            largura_botao=200,
            titulo=t("Selecione as Fichas Técnicas"),
            filetypes=[("Excel", "*.xlsx")],
            ao_escolher=self._ao_escolher_fichas,
        )
        # B) Pasta de Saída
        self.picker_out = app_pickers.FolderPickerRow(
            chave="analyzer.saida",
            texto_botao=t("Pasta de Saída"),
            largura_botao=200,
            titulo=t("Selecione Pasta de Saída"),
            ao_escolher=self._ao_escolher_saida,
        )
        # C) PMIB (Opcional)
        self.picker_pmib = app_pickers.FilePickerRow(
            chave="analyzer.status_pmib",
            categoria="excel",
            texto_botao=t("STATUS_PMIB (Opcional)"),
            largura_botao=200,
            titulo=t("Selecione STATUS_PMIB"),
            filetypes=[("Excel", "*.xlsx")],
            # Texto proprio desta tela -- ela avisa qual e o padrao quando
            # nada e escolhido, e isso e informacao util, nao ruido.
            texto_vazio=t("Não selecionado (Padrão: sem contexto)"),
            ao_escolher=self._ao_escolher_pmib,
        )
        for picker in (self.picker_files, self.picker_out, self.picker_pmib):
            arquivos.addSpacing(10)              # título/linha (…, 5) + linha (5, …)
            arquivos.addWidget(picker)
        arquivos.addSpacing(15)                  # último seletor: pady=(5, 15)

        # --- AÇÃO ---
        corpo.addSpacing(40)                     # cartão (…, 10) + botão (30, …)
        self.btn_run = blocos.botao(t("INICIAR PROCESSAMENTO"), largura=300, altura=50, tamanho_fonte=15,
                                    negrito=True, variante="primario")
        self.btn_run.clicked.connect(self.iniciar_analise)
        corpo.addWidget(self.btn_run, alignment=Qt.AlignmentFlag.AlignHCenter)
        corpo.addSpacing(8)

        # Relatorio para o FORNECEDOR (2026-08-26). Nasce desabilitado: so
        # existe relatorio depois de um lote rodar, e botao que promete o que
        # nao tem e pior que botao ausente.
        self.btn_relatorio = blocos.botao(t("GERAR RELATÓRIO PARA O FORNECEDOR (.xlsx)"), largura=300,
                                          altura=36, tamanho_fonte=12, variante="primario")
        self.btn_relatorio.setEnabled(False)
        self.btn_relatorio.clicked.connect(self._gerar_relatorio)
        corpo.addWidget(self.btn_relatorio, alignment=Qt.AlignmentFlag.AlignHCenter)
        corpo.addSpacing(25)

    @staticmethod
    def _cartao(corpo) -> QVBoxLayout:
        """O cartão (`blocos.cartao`); as peças vão com padx=15 e começam com pady 10."""
        layout = blocos.cartao(corpo)
        layout.setContentsMargins(15, 10, 15, 0)
        layout.setSpacing(0)
        return layout

    # --- Relatório ---------------------------------------------------------------------
    def _gerar_relatorio(self) -> None:
        """Grava o `.xlsx` de pendências na pasta de saída da análise.

        Uma linha por material: código PMIB, o que precisa ser corrigido (com
        a justificativa que a IA escreveu para o fornecedor) e a nota. É o
        arquivo que se manda a quem preencheu a ficha.
        """
        if not self.relatorio_analise:
            QMessageBox.information(
                self, t("Relatório"), t("Rode uma análise primeiro. Ainda não há pendências para relatar."))
            return
        destino = self.selected_output or os.getcwd()
        try:
            caminho = self.relatorio_analise.salvar_xlsx(
                destino, retry_lock=self.perguntar_retry_excel
            )
        except Exception as e:  # noqa: BLE001 -- vira aviso, como lá
            self.log(f"Nao consegui gerar o relatorio: {e}")
            QMessageBox.critical(self, t("Relatório"), t("Não consegui gerar o arquivo:\n{erro}", erro=e))
            return
        if not caminho:
            QMessageBox.information(
                self, t("Relatório"), t("Nenhuma ficha ficou com pendência. Não há o que relatar."))
            return
        self.log(f"Relatorio gerado: {caminho}")
        QMessageBox.information(
            self, t("Relatório"), t("{n} ficha(s) com pendência.\n\nArquivo:\n{caminho}",
                                    n=len(self.relatorio_analise), caminho=caminho))

    # --- Janela de Configuração de Pesos -----------------------------------------------
    def abrir_config_pesos(self) -> None:
        modulo = self.backend("analyzer_backend")
        if modulo is None:
            return
        # Já aberta: traz para a frente em vez de abrir outra, que salvaria
        # pelos campos da mais nova.
        if self.janela_pesos is not None and self.janela_pesos.isVisible():
            self.janela_pesos.raise_()
            self.janela_pesos.activateWindow()
            return
        # Pega o mapa padrão do backend
        self.janela_pesos = JanelaPesos(self, modulo.CONFIG_MAP)
        self.janela_pesos.show()

    def _salvar_pesos(self, window) -> None:
        try:
            # Lê tudo antes de gravar: um campo inválido não deixa metade salva.
            novos = {key: float(entry.text()) for key, entry in self.entries_pesos.items()}
            max_vars = float(self.entry_max_vars.text())
        except ValueError:
            QMessageBox.critical(window, t("Erro"), t("Certifique-se de usar apenas números (ponto para decimais)."))
            return
        self.custom_weights.update(novos)
        self.max_var_points = max_vars
        QMessageBox.information(window, t("Sucesso"), t("Pesos atualizados para esta sessão."))
        window.close()

    # --- Callbacks UI ------------------------------------------------------------------
    def _update_slider_label(self, value) -> None:
        self.score_value = value
        self.lbl_score.setText(t("Nota Mínima: {nota}%", nota=int(value)))

    # [CP 7.2] Os pickers cuidam do dialogo, da memoria de caminho e das duas
    # mudancas de cor. Sobra a esta tela so guardar o que foi escolhido.
    def _ao_escolher_fichas(self, caminhos) -> None:
        self.selected_files = list(caminhos)

    def _ao_escolher_saida(self, pasta) -> None:
        self.selected_output = pasta

    def _ao_escolher_pmib(self, caminho) -> None:
        self.selected_pmib = caminho

    # --- Lógica ------------------------------------------------------------------------
    def iniciar_analise(self) -> None:
        if self.backend("analyzer_backend") is None:
            return
        if not self.selected_files:
            QMessageBox.warning(self, t("Faltam Dados"), t("Selecione as Fichas."))
            return
        if not self.selected_output:
            QMessageBox.warning(self, t("Faltam Dados"), t("Selecione a Pasta de Saída."))
            return

        self.log(f"Iniciando análise de {len(self.selected_files)} arquivos...")

        # Log dos pesos usados (para auditoria)
        if self.custom_weights:
            self.log(">>> Usando PESOS PERSONALIZADOS nesta análise.")
        else:
            self.log(">>> Usando PESOS PADRÃO.")

        self.api_key = self._chave_gemini()
        # Desliga o relatório já no clique: a lista anterior vai ser trocada.
        self.btn_relatorio.setEnabled(False)
        # Tudo lido no clique: os seletores, a régua e "Configurar Pesos"
        # seguem ligados durante o lote, e mexer neles no meio não pode mudar
        # as fichas que faltam (nem a contagem do fim).
        self.iniciar_tarefa(
            self._run_backend, list(self.selected_files), self.selected_output,
            self.selected_pmib, int(self.score_value), dict(self.custom_weights),
            self.max_var_points, botao=self.btn_run)

    def _perguntar_descricao(self, arquivo, codigo):
        """Pergunta a descrição do material quando o código PMIB não está no
        `_STATUS_PMIB`.

        Chamado PELO BACKEND, de dentro da thread de processamento -- por isso
        passa por `pedir_texto`, que abre a janela na thread da interface e
        deixa o worker esperando.

        **Cancelar para de perguntar no resto do lote.** Um lote de 50 fichas
        com PMIB desconhecido não pode virar 50 caixas de diálogo
        obrigatórias -- e a saída precisa ser óbvia para quem está com pressa.
        """
        if getattr(self, "_parar_de_perguntar_desc", False):
            return None

        texto = self.pedir_texto(
            t("Descrição do material"),
            t("A ficha {arquivo} tem o código PMIB {codigo}, que não está "
              "no _STATUS_PMIB.\n\nSe você souber a descrição do material, "
              "digite abaixo. Ela entra no contexto que vai para a IA.\n\n"
              "CANCELAR segue sem descrição e não pergunta mais nesta rodada.",
              arquivo=arquivo, codigo=codigo),
        )

        if texto is None:      # Cancelar (≠ de OK com campo vazio)
            self._parar_de_perguntar_desc = True
            self.log(" -> Sem descricao manual; nao vou perguntar de novo nesta rodada.")
            return None
        texto = texto.strip()
        if texto:
            self.log(f" -> Descricao informada a mao: {texto}")
        return texto or None

    def _run_backend(self, arquivos, pasta_saida, caminho_pmib, nota_minima, pesos,
                     max_pontos) -> None:
        try:
            self._parar_de_perguntar_desc = False
            backend = self.backend("analyzer_backend")
            if backend is None:
                return
            analyzer = backend.DatasheetAnalyzer(self.api_key)
            # Relatorio para o fornecedor: o backend acumula os achados de
            # cada ficha aqui dentro (ver `_registrar_no_relatorio`).
            self.relatorio_analise = analyzer_relatorio.RelatorioAnalise()
            analyzer.relatorio = self.relatorio_analise
            pmib_sheet = None
            if caminho_pmib:
                try:
                    wb = openpyxl.load_workbook(caminho_pmib, data_only=True)
                    # 2026-08-26: era `wb.active` -- a aba selecionada quando o
                    # arquivo foi salvo, que pode ser uma capa. Ver `aba_do_status_pmib`.
                    pmib_sheet = backend.aba_do_status_pmib(wb)
                    self.log("STATUS_PMIB carregada.")
                except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
                    self.log(f"Erro STATUS_PMIB: {e}")

            ok, falhas = 0, []
            for f_path in arquivos:
                fname = os.path.basename(f_path)
                subfolder = os.path.basename(os.path.dirname(f_path))

                iterador_logs = analyzer.processar_planilha(
                    input_filepath=f_path,
                    root_output_dir=pasta_saida,
                    subfolder_name=subfolder,
                    original_filename=fname,
                    pmib_sheet=pmib_sheet,
                    score_threshold=nota_minima,
                    custom_weights=pesos,
                    max_variable_points=max_pontos,
                    callback_manual_desc=self._perguntar_descricao,
                    retry_lock=self.perguntar_retry_excel,
                )
                # O `return True/False` do backend vem em `StopIteration.value`
                # (um `for` o descartaria), e a exceção de uma ficha não derruba
                # o lote -- as duas correções de 2026-08-26.
                try:
                    while True:
                        try:
                            self.log(next(iterador_logs))
                        except StopIteration as fim:
                            ok += 1 if fim.value else 0
                            if not fim.value:
                                falhas.append(fname)
                            break
                except Exception as e:  # noqa: BLE001 -- a ficha falha, o lote segue
                    self.log(f"[ERRO] {fname}: {e}")
                    falhas.append(fname)

            self.log(f"Concluído! {ok} de {len(arquivos)} ficha(s) processada(s).")
            if self.relatorio_analise:
                interface.na_interface(self.btn_relatorio.setEnabled, True)
                self.log(f"{len(self.relatorio_analise)} ficha(s) com pendencia. Use "
                         "GERAR RELATORIO PARA O FORNECEDOR (.xlsx).")
            if falhas:
                self.log(f"NAO concluidas ({len(falhas)}): {', '.join(falhas)}")
                self.avisar(
                    t("Análise finalizada com pendências"),
                    t("{falhas} de {total} ficha(s) não foram "
                      "processadas.\nVeja o console para o motivo de cada uma.",
                      falhas=len(falhas), total=len(arquivos)),
                    tipo="aviso",
                )
            else:
                self.avisar(t("Sucesso"), t("Análise finalizada."))
        except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
            self.log(f"Erro Fatal: {e}")
