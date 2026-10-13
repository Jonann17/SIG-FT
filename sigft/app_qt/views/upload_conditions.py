"""Tela "Upload de Condições no PMIB" na interface Qt.

Mesma tela de `sigft/app/views/upload_conditions.py`: lê as condições das
fichas com IA (aba 1, gera o Excel de resultados) e preenche as abas
correspondentes no portal (aba 2, o robô), marcando o `_STATUS_PMIB`.

O que muda é só COMO os workers falam com a tela: lá eram `self.after(0, ...)`
e janelas abertas por `after`; aqui o log vai pelo console (seguro de qualquer
thread), os botões e o fim da IA por `interface.na_interface`, a pausa de
login e o Excel travado por `pausar_e_esperar`/`perguntar_retry_excel` (o
worker espera num `Event`) e o aviso do fim por `avisar`. Os serviços e o
fluxo do portal são os mesmos. A montagem comum com a tela de Tech Specs
(irmã quase gêmea) mora em `_upload_comum.TelaDeUpload`.
"""
from __future__ import annotations

import ast

from PySide6.QtWidgets import QMessageBox, QVBoxLayout

from sigft.app import theme
from sigft.app.textos_dialogos import LOGIN_NECESSARIO, MSG_LOGIN_SOLTAR_ROBO, msg_falha_ao_salvar
from sigft.app_qt import file_dialogs, interface
from sigft.app_qt.views._upload_comum import ABA_WEB, URL_PORTAL, TelaDeUpload, reabilitar
from sigft.app_qt.widgets import blocos, dialogos_selecao
from sigft.core.excel.pmib_codes import normalize_pmib

ABA_IA = "Processamento IA (Gerar Excel)"
# Colunas que o Excel de resultados guarda como texto de dicionário.
COLUNAS_DICIONARIO = ["dimensoes", "controle_temperatura", "nocivo", "peso", "protecao",
                      "outros_cuidados", "logistica_reversa"]


def ler_resultados_excel(caminho: str) -> list[dict]:
    """O `resultados_api_pmib.xlsx` em lista de fichas, como a tela CTk lia.

    O PMIB vem como texto e passa pela normalização única (`normalize_pmib`);
    as colunas de dicionário voltam a ser dicionário (`{}` quando vazias).
    """
    import pandas as pd  # pesado: só quando a pessoa carrega um arquivo

    # Força a leitura do PMIB como string logo de cara
    df = pd.read_excel(caminho, dtype={"pmib_codigo": str})
    if "pmib_codigo" in df.columns:
        # CP 1.2: a normalização canônica (core.excel.pmib_codes.normalize_pmib)
        df["pmib_codigo"] = df["pmib_codigo"].apply(normalize_pmib)
    for coluna in COLUNAS_DICIONARIO:
        if coluna in df.columns:
            df[coluna] = df[coluna].fillna("{}").apply(ast.literal_eval)
    return df.to_dict("records")


class ModuloUploadConditions(TelaDeUpload):
    ABA_IA = ABA_IA
    TEXTO_CONFIG = "Configuração Global (Requerido para IA e Web)"
    MARGENS_CONFIG = (15, 10, 15, 10)               # padx=15; título (10, 5); linha (5, 10)
    TEXTO_INTERRUPTOR = "Forçar processamento de fichas com status 'COMPLETO'"
    TEXTO_WEB = "Lê um arquivo Excel com os resultados e inicia o Selenium para preencher o Portal."
    TEXTO_CARREGAR = "Carregar 'resultados_api_pmib.xlsx'"

    def __init__(self, parent=None, controller=None) -> None:
        # Antes do super(): o `_build_ui` roda lá dentro.
        self.caminho_status = ""          # o StringVar de lá
        self.dados_em_memoria: list = []
        # Referências aos processos ativos (para poder parar)
        self.processor_ativo = None
        self.automacao_ativa = None
        super().__init__(parent, controller, titulo="Upload de Condições no PMIB")
        self.api_key = self._chave()

    # --- montagem (o resto é da base) -------------------------------------------
    def _build_tab1(self, aba: QVBoxLayout) -> None:
        rolavel = self._area_da_aba_ia(aba)
        rolavel.addSpacing(10)                          # quadro das fichas: pady=10
        corpo = self._cartao_na_aba(rolavel, (10, 10, 10, 5))   # contador (10, 0); fila pady=5
        # [CP 7.2] Uma das 2 cópias idênticas da fila de fichas -- o FileQueueList.
        self._fila_de_fichas(corpo, chave="upload_conditions.fichas", rotulo="Planilhas PMIB Selecionadas",
                             filetypes=[("Excel", "*.xlsx;*.xls")])
        rolavel.addSpacing(15)                          # quadro (…, 10) + ações (5, …)
        rolavel.addLayout(self._linha_acoes_ia())
        rolavel.addSpacing(15)                          # ações: pady=(…, 15)

    # --- seleção de arquivos ----------------------------------------------------
    def _sel_status(self) -> None:
        path = file_dialogs.ask_open_file("upload_conditions.status_pmib", "excel",
                                          titulo="Selecione _STATUS_PMIB",
                                          filetypes=[("Excel", "*.xlsx;*.xlsm")])
        if path:
            self.caminho_status = path
            blocos.marcar_arquivo_escolhido(self.btn_status, self.lbl_status_status, path)

    def _logar_mudanca_na_fila(self, acao, quantidade, total) -> None:
        # Esta tela só loga a adição (a irmã loga as três, como lá).
        if acao == "adicionou":
            self.log(f"{quantidade} arquivos selecionados. Total na fila: {total}")

    # --- IA (aba 1) -------------------------------------------------------------
    def _stop_ia_process(self) -> None:
        if self._confirmar("Deseja interromper a IA?\nO que já foi processado será mantido."):
            self.log("Sinal de parada enviado! Aguarde o término do arquivo atual...")
            self.btn_parar_ia.setEnabled(False)
            if self.processor_ativo:
                self.processor_ativo.solicitar_parada()

    def _stop_web_process(self) -> None:
        if self._confirmar("Deseja interromper o robô?\nEle vai parar antes da próxima ficha."):
            self.log("Sinal de parada enviado ao robô! Aguardando o ciclo atual fechar...")
            self.btn_parar_web.setEnabled(False)
            if self.automacao_ativa:
                self.automacao_ativa.solicitar_parada()

    def _start_ia_process(self) -> None:
        status_file = self.caminho_status
        files = self.lista_fichas_paths
        if not status_file:
            QMessageBox.warning(self, "Aviso",
                                "Por favor, selecione a planilha de _STATUS_PMIB na Configuração Global.")
            return
        if not files:
            QMessageBox.warning(self, "Aviso", "Por favor, adicione pelo menos uma ficha à lista.")
            return
        modulo = self.backend("upload_conditions_backend")
        if modulo is None:
            return
        self.log(f"Iniciando processamento de {len(files)} arquivos...")
        self.btn_parar_ia.setEnabled(True)  # Liga o botão parar
        self.api_key = self._chave()
        # O interruptor é lido AQUI, na thread da tela.
        processar_completos = self.switch_completos.isChecked()
        self.iniciar_tarefa(self._worker_ia, modulo, files, status_file, processar_completos,
                            botao=self.btn_ia)

    def _worker_ia(self, modulo, files, status_file, processar_completos=False) -> None:
        try:
            processor = modulo.ConditionsProcessor(self.api_key)
            self.processor_ativo = processor  # para o botão parar funcionar

            df_status, msg = processor.carregar_lookup_status(status_file)
            if df_status is None:
                self.log(f"Erro no Status: {msg}")
                return
            self.log(msg)

            # 2026-08-18: o interruptor "Forçar processamento" CHEGA no backend.
            if processar_completos:
                self.log("Forçar processamento LIGADO: fichas já COMPLETO também serão reprocessadas.")

            resultados = processor.processar_ia_lote(
                files, df_status, callback_log=self.log,
                processar_completos=processar_completos,
            )
            interface.na_interface(self._on_ia_finished, resultados, processor)
        except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
            self.log(f"Erro Fatal IA: {e}")
        finally:
            # Lá o PARAR ficava ligado depois de um erro; aqui ele desliga
            # sempre que a IA acaba (o INICIAR volta pelo `iniciar_tarefa`).
            self.processor_ativo = None
            interface.na_interface(reabilitar, (self.btn_parar_ia, False))

    def _on_ia_finished(self, resultados, processor) -> None:
        reabilitar((self.btn_ia, True), (self.btn_parar_ia, False))
        self.processor_ativo = None

        if not resultados:
            QMessageBox.information(self, "Aviso", "Nenhum dado gerado. Verifique o console.")
            return

        self.dados_em_memoria = resultados
        self.log(f"Sucesso! {len(resultados)} fichas processadas.")

        # Pergunta de Salvamento (o askyesnocancel: Sim / Não / Cancelar)
        modo_salvar = QMessageBox.question(
            self, "Salvar Resultados",
            "Como deseja salvar as fichas processadas?\n\nSIM = Novo Arquivo Excel\n"
            "NÃO = Anexar a um Excel Existente",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes)

        caminho_final = None
        sucesso_salvar = False
        msg_salvar = ""
        if modo_salvar == QMessageBox.StandardButton.Yes:
            caminho_final = file_dialogs.ask_save_file("upload_conditions.salvar_novo", "excel",
                                                       titulo="Salvar Novo Arquivo", defaultextension=".xlsx",
                                                       filetypes=[("Excel", "*.xlsx")])
            if caminho_final:
                sucesso_salvar, msg_salvar = processor.salvar_novo_arquivo(resultados, caminho_final)
        elif modo_salvar == QMessageBox.StandardButton.No:
            caminho_final = file_dialogs.ask_open_file("upload_conditions.anexar", "excel",
                                                       titulo="Selecionar arquivo para ANEXAR",
                                                       filetypes=[("Excel", "*.xlsx")])
            if caminho_final:
                sucesso_salvar, msg_salvar = processor.anexar_a_arquivo_existente(resultados, caminho_final)

        if caminho_final:
            self.log(msg_salvar)
            if sucesso_salvar:
                if self._perguntar_se_continua():
                    self.tabview.set(ABA_WEB)
                    self._pre_start_web(self.dados_em_memoria)
            else:
                QMessageBox.critical(self, "Erro ao Salvar", msg_salvar)

    # --- Robô Web (aba 2) -------------------------------------------------------
    def _pre_start_web(self, dados_dict_lista) -> None:
        if self._robo_ocupado():
            return
        if not self.caminho_status:
            QMessageBox.warning(self, "Aviso",
                                "Selecione o _STATUS_PMIB na Configuração Global antes de iniciar o Robô.")
            return
        if not dados_dict_lista:
            QMessageBox.warning(self, "Aviso", "Não há dados para iniciar a automação.")
            return

        # A escolha volta como POSIÇÃO (`devolver_indices`), para reencontrar o
        # item na lista de origem.
        def confirmar(indices):
            selecionados_finais = [dados_dict_lista[i] for i in indices]
            if selecionados_finais:
                self._start_web_process(selecionados_finais)
            else:
                self.log("Nenhuma ficha selecionada. Operação cancelada.")

        dialogos_selecao.SelecaoMultiplaDialog(
            self,
            itens=[f" Ficha PMIB: {item.get('pmib_codigo', 'N/A')}" for item in dados_dict_lista],
            titulo="Selecione as Fichas para Processar",
            instrucao="Selecione quais PMIBs deseja preencher no portal:",
            geometria="500x400",
            modal=True,
            com_selecionar_todos=True,
            devolver_indices=True,
            fonte_instrucao=("Roboto", 14, "bold"),
            fonte_lista=("Consolas", 12),
            estilo_lista={
                "bg": "#1E1E1E", "fg": "white",
                "selectbackground": theme.COLORS["primary"],
                "highlightthickness": 0, "borderwidth": 0,
            },
            ao_confirmar=confirmar,
        )

    def _start_web_from_file(self) -> None:
        excel_file = file_dialogs.ask_open_file("upload_conditions.excel_resultados", "excel",
                                                titulo="Selecione Excel de Resultados",
                                                filetypes=[("Excel", "*.xlsx;*.xls")])
        if not excel_file:
            return
        try:
            self.log("Lendo arquivo Excel, convertendo strings em dicionários...")
            dados = ler_resultados_excel(excel_file)
            # DENTRO do try, como lá: linhas num formato inesperado também viram
            # "Erro ao ler Excel" (fora dele, a exceção sumia no laço do Qt).
            self._pre_start_web(dados)
        except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
            self.log(f"Erro ao ler Excel: {e}")
            QMessageBox.critical(self, "Erro de Leitura", f"Falha ao ler Excel: {e}")

    def _start_web_process(self, dados) -> None:
        if self._robo_ocupado():
            return
        modulo = self.backend("upload_conditions_backend")
        if modulo is None:
            return
        self._inicio_do_robo()
        self.log(f"Iniciando fila de {len(dados)} fichas no navegador...")
        self.iniciar_tarefa(self._worker_web, modulo, dados, self.caminho_status)

    @staticmethod
    def _mensagem_da_pausa(section_name) -> str:
        """Login, ou a aba que o portal recusou salvar."""
        if section_name == LOGIN_NECESSARIO:
            return MSG_LOGIN_SOLTAR_ROBO
        return msg_falha_ao_salvar(section_name)

    def _worker_web(self, modulo, dados, status_file) -> None:
        auto = None
        try:
            auto = modulo.UploadAutomation()
            self.automacao_ativa = auto

            # Os callbacks do robô: a janela nasce na thread da interface e o
            # robô espera a pessoa (`DialogosDeEspera`).
            def pause_callback(section_name):
                self.pausar_e_esperar(self._mensagem_da_pausa(section_name))

            def ask_callback(_motivo):
                return self.perguntar_retry_excel()

            self.log("Iniciando navegador...")
            auto.iniciar()
            self.log("Carregando portal PMIB...")
            auto.abrir_portal(URL_PORTAL)
            pause_callback(LOGIN_NECESSARIO)
            self.log("Login confirmado. Iniciando preenchimento...")
            auto.processar_lista(dados, status_file, callback_ask=ask_callback, callback_log=self.log,
                                 callback_pause=pause_callback)
            self.log("Fila de processamento web concluída.")
            self.avisar("Aviso", "A fila de automação foi finalizada!")
        except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
            self.log(f"Erro Crítico Web: {e}")
        finally:
            if auto is not None:
                try:
                    auto.fechar()
                except Exception as e:  # noqa: BLE001 -- os botões têm de voltar
                    self.log(f"Erro Crítico Web: {e}")
            self.automacao_ativa = None
            interface.na_interface(self._fim_do_robo)
