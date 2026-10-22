"""Tela "Upload Características Técnicas" na interface Qt.

Mesma tela da interface antiga (`sigft/app/views/upload_tech_specs.py`, removida em 2026-10-15): extrai as
características técnicas das fichas com IA e salva o resultado em JSON (aba 1),
e envia para o portal (aba 2) -- as duas metades podem rodar separadas.

Irmã quase gêmea de `upload_conditions.py`: a montagem comum (quadro global,
abas, fila, INICIAR/PARAR, aba do robô) mora em `_upload_comum.TelaDeUpload`.
O que muda em relação à tela antiga é só COMO os workers falam com a tela
(console, `interface.na_interface`, `pausar_e_esperar`, `avisar`) e o
`TechSpecsController`, que nasce no primeiro clique em vez de no `__init__`
(sem o backend, lá a tela nem abria).
"""
from __future__ import annotations

import json

from PySide6.QtWidgets import QMessageBox, QVBoxLayout

from sigft.app.idioma import marcar, t
from sigft.app.textos_dialogos import LOGIN_NECESSARIO, MSG_LOGIN_SOLTAR_ROBO, msg_ficha_preenchida
from sigft.app_qt import file_dialogs, interface
from sigft.app_qt.views._upload_comum import ABA_WEB, TelaDeUpload, reabilitar
from sigft.app_qt.widgets import blocos, dialogos_selecao
from sigft.app_qt.widgets.arrastar import Arrastavel
from sigft.core import pmib_regras

ABA_IA = marcar("Processamento IA (Gerar JSON)")


class ModuloUploadTechSpecs(TelaDeUpload):
    # Arrastar arquivo do Explorer para os botões (2026-10-21, etapa 1b).
    ARRASTAVEIS = (
        Arrastavel("btn_status", "upload_tech_specs.status_pmib", (".xlsx", ".xlsm")),
        Arrastavel("btn_master", "upload_tech_specs.master", (".xlsx", ".xlsm")),
    )
    ABA_IA = ABA_IA
    TEXTO_CONFIG = marcar("Configuração Global")
    MARGENS_CONFIG = (15, 10, 15, 15)               # padx=15; título (10, 0); linha (10, 15)
    TEXTO_INTERRUPTOR = marcar("Forçar processamento de fichas 'COMPLETO'")
    TEXTO_WEB = marcar("Lê um arquivo JSON pronto e inicia o Selenium para preencher o Portal Itaipu.")
    TEXTO_CARREGAR = marcar("Carregar JSON Salvo no Computador")

    def __init__(self, parent=None, controller=None) -> None:
        # Antes do super(): o `_build_ui` roda lá dentro.
        self.tech_controller = None       # o orquestrador do backend, no primeiro clique
        self.dados_em_memoria: list = []  # o JSON, caso a pessoa queira rodar o robô em seguida
        self.caminho_status = ""
        self.caminho_master = ""
        super().__init__(parent, controller, titulo=t("Upload Características Técnicas"))
        self.api_key = self._chave()

    def _controlador(self):
        if self.tech_controller is None:
            modulo = self.backend("upload_tech_specs_backend")
            if modulo is None:
                return None
            self.tech_controller = modulo.TechSpecsController()
        return self.tech_controller

    # --- montagem (o resto é da base) -------------------------------------------
    def _build_tab1(self, aba: QVBoxLayout) -> None:
        # Frame com rolagem para telas pequenas (lá também).
        rolavel = self._area_da_aba_ia(aba)
        rolavel.addSpacing(10)                          # referência: pady=(10, …)

        # 1. Seletor do Master PDM
        corpo = self._cartao_na_aba(rolavel, (15, 10, 15, 15))
        self.rotulo_referencia = blocos.rotulo(t("Referência para IA"), tamanho=14, negrito=True,
                                               papel="destaque", alinhar="esquerda")
        self.rotulo_referencia.setWordWrap(False)
        corpo.addWidget(self.rotulo_referencia)
        corpo.addSpacing(10)                            # título (…, 5) + linha (5, …)
        linha, self.btn_master, self.lbl_master_status = self._linha_arquivo(
            t("Selecionar PDM's SAM-GM"), self._sel_master)
        corpo.addLayout(linha)
        rolavel.addSpacing(15)                          # referência (…, 5) + fichas (10, …)

        # 2. Área de Fichas: o mesmo FileQueueList do Upload de Condições.
        corpo = self._cartao_na_aba(rolavel, (10, 5, 10, 5))   # contador (5, 0); fila pady=5
        self._fila_de_fichas(corpo, chave="upload_tech_specs.fichas", rotulo=t("Fichas Selecionadas"),
                             filetypes=[("Excel", "*.xlsx;*.xlsm")])
        rolavel.addSpacing(15)                          # fichas (…, 10) + ações (5, …)

        # 3. Botões Principais (Iniciar e Parar)
        rolavel.addLayout(self._linha_acoes_ia())
        rolavel.addSpacing(15)                          # ações: pady=(…, 15)

    # --- seleção de arquivos (aba 1) --------------------------------------------
    def _sel_status(self) -> None:
        path = file_dialogs.ask_open_file("upload_tech_specs.status_pmib", "excel",
                                          titulo=t("Selecione _STATUS_PMIB"),
                                          filetypes=[("Excel", "*.xlsx;*.xlsm")])
        if path:
            self.caminho_status = path
            blocos.marcar_arquivo_escolhido(self.btn_status, self.lbl_status_status, path)

    def _sel_master(self) -> None:
        path = file_dialogs.ask_open_file("upload_tech_specs.master", "excel",
                                          titulo=t("Selecione Master PDMs (Template)"),
                                          filetypes=[("Excel", "*.xlsx;*.xlsm")])
        if path:
            self.caminho_master = path
            blocos.marcar_arquivo_escolhido(self.btn_master, self.lbl_master_status, path)

    def _logar_mudanca_na_fila(self, acao, quantidade, total) -> None:
        # Esta tela loga as TRÊS ações; a irmã só a adição (como lá).
        if acao == "adicionou":
            self.log(f"{quantidade} arquivos selecionados. Total na fila: {total}")
        elif acao == "removeu":
            self.log(f"{quantidade} arquivos removidos da fila. Total na fila: {total}")
        elif acao == "limpou":
            self.log("Todas as fichas foram removidas da fila.")

    def _stop_ia_process(self) -> None:
        """Dispara o sinal de parada no Backend"""
        if self._confirmar(t("Deseja realmente interromper o processo da IA?\n"
                             "O que já foi processado será salvo.")):
            self.log("Sinal de parada enviado! Aguarde o término do item atual...")
            self.btn_parar_ia.setEnabled(False)
            if self.tech_controller is not None:
                self.tech_controller.cancelar_processo_ia()

    # --- IA (aba 1) -------------------------------------------------------------
    def _start_ia_process(self) -> None:
        status_file, master_file = self.caminho_status, self.caminho_master
        files = self.lista_fichas_paths
        if not status_file:
            QMessageBox.warning(self, t("Aviso"), t("Por favor, selecione a planilha de _STATUS_PMIB."))
            return
        if not master_file:
            QMessageBox.warning(self, t("Aviso"), t("Por favor, selecione a planilha Master PDMs."))
            return
        if not files:
            QMessageBox.warning(self, t("Aviso"), t("Por favor, adicione pelo menos uma ficha à lista."))
            return
        controlador = self._controlador()
        if controlador is None:
            return
        self.log(f"Iniciando processamento de {len(files)} arquivos...")
        self.btn_parar_ia.setEnabled(True)
        self.api_key = self._chave()
        processar_completos = self.switch_completos.isChecked()   # lido na thread da tela
        self.iniciar_tarefa(self._worker_ia, controlador, files, status_file, master_file,
                            processar_completos, botao=self.btn_ia)

    def _worker_ia(self, controlador, files, status_file, master_file, processar_completos) -> None:
        try:
            resultados = controlador.executar_pipeline_ia(
                self.api_key, files, status_file, master_file, processar_completos, callback_log=self.log)
            # A conversa com a pessoa (salvar, continuar) é na thread da interface.
            interface.na_interface(self._on_ia_finished, resultados)
        except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
            self.log(f"Erro Fatal IA: {e}")
        finally:
            # Lá o PARAR ficava ligado depois de um erro; aqui desliga sempre.
            interface.na_interface(reabilitar, (self.btn_parar_ia, False))

    def _on_ia_finished(self, resultados) -> None:
        reabilitar((self.btn_ia, True), (self.btn_parar_ia, False))
        if not resultados:
            QMessageBox.information(self, t("Aviso"), t("Nenhum dado gerado. Verifique o console."))
            return

        self.dados_em_memoria = resultados
        self.log(f"Sucesso! {len(resultados)} fichas geradas prontas para o robô.")

        save_path = file_dialogs.ask_save_file("upload_tech_specs.salvar_json", "json",
                                               titulo=t("Salvar JSON de Resultados"), defaultextension=".json",
                                               filetypes=[("JSON", "*.json")])
        if save_path:
            sucesso = self.tech_controller.salvar_json(resultados, save_path, callback_log=self.log)
            if sucesso:
                if self._perguntar_se_continua():
                    self.tabview.set(t(ABA_WEB))
                    # A janela de seleção, como no Upload Condições: antes o
                    # "Continuar" mandava tudo ao portal sem perguntar quais.
                    self._pre_start_web(self.dados_em_memoria)

    # --- Robô Web (aba 2) -------------------------------------------------------
    def _pre_start_web(self, dados_json) -> None:
        """Abre o popup para a pessoa escolher quais fichas do JSON processar."""
        if self._robo_ocupado():
            return
        if not dados_json:
            QMessageBox.warning(self, t("Aviso"), t("Não há dados para iniciar a automação."))
            return

        def confirmar(indices):
            selecionados_finais = [dados_json[i] for i in indices]
            if selecionados_finais:
                self._start_web_process(selecionados_finais)
            else:
                self.log("Nenhuma ficha selecionada. Operação cancelada.")

        dialogos_selecao.SelecaoMultiplaDialog(
            self,
            # Só exibição (`devolver_indices`): a escolha volta como posição.
            itens=[t("PMIB: {pmib} | {arquivo}", pmib=item.get('METADATA', {}).get('PMIB', 'N/A'),
                     arquivo=item.get('METADATA', {}).get('ARQUIVO_ORIGEM', 'N/A')) for item in dados_json],
            titulo=t("Selecione as Fichas para Processar"),
            instrucao=t("Selecione quais fichas do JSON deseja enviar para o site:"),
            geometria="600x450",
            modal=True,
            com_selecionar_todos=True,
            devolver_indices=True,
            fonte_instrucao=("Roboto", 14, "bold"),
            fonte_lista=("Consolas", 11),
            estilo_lista={
                # As cores da lista são as da folha (2026-10-20); só a borda vale.
                "highlightthickness": 0, "borderwidth": 0,
            },
            ao_confirmar=confirmar,
        )

    def _stop_web_process(self) -> None:
        """Envia o sinal para o Backend parar o robô."""
        if self._confirmar(t("Deseja interromper o robô?\n"
                             "Ele vai parar de forma segura antes da próxima ficha/ação.")):
            self.log("Sinal de parada enviado ao robô! Aguardando o ciclo atual fechar...")
            self.btn_parar_web.setEnabled(False)
            if self.tech_controller is not None:
                self.tech_controller.cancelar_processo_web()

    def _start_web_from_file(self) -> None:
        json_file = file_dialogs.ask_open_file("upload_tech_specs.json_resultados", "json",
                                               titulo=t("Selecione JSON de Resultados"),
                                               filetypes=[("JSON", "*.json")])
        if not json_file:
            return
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                dados = json.load(f)
            # DENTRO do try, como lá: um JSON que não é uma lista de fichas também
            # vira "Erro ao ler JSON" (fora dele, a exceção sumia no laço do Qt).
            self._pre_start_web(dados)
        except Exception as e:  # noqa: BLE001 -- vira mensagem para a pessoa
            # Log e caixa, como o "Erro ao ler Excel" do Upload Condições.
            self.log(f"Erro ao ler JSON: {e}")
            QMessageBox.critical(self, t("Erro de Leitura"), t("Falha ao ler JSON: {erro}", erro=e))

    def _start_web_process(self, dados) -> None:
        if self._robo_ocupado():
            return
        controlador = self._controlador()
        if controlador is None:
            return
        dados = self._revisar_antes_do_portal(dados, pmib_regras.conferir_tech_specs)
        if dados is None:
            return
        self._inicio_do_robo()
        self.log(f"Iniciando fila de {len(dados)} fichas no navegador...")
        caminho_status = self.caminho_status
        if not caminho_status:
            self.log("Aviso: Arquivo _STATUS_PMIB não selecionado. As fichas NÃO serão marcadas como concluídas.")
        self.iniciar_tarefa(self._worker_web, controlador, dados, caminho_status)

    @staticmethod
    def _mensagem_da_pausa(estado_ou_pmib) -> str:
        """Login, ou a ficha que o robô acabou de preencher (a pessoa confere e
        segue); já no idioma da sessão."""
        if estado_ou_pmib == LOGIN_NECESSARIO:
            return t(MSG_LOGIN_SOLTAR_ROBO)
        return msg_ficha_preenchida(estado_ou_pmib)

    def _worker_web(self, controlador, dados, caminho_status) -> None:
        try:
            # A janela nasce na thread da interface; o robô espera a pessoa.
            def pause_callback(estado_ou_pmib):
                self.pausar_e_esperar(self._mensagem_da_pausa(estado_ou_pmib))

            controlador.executar_pipeline_rpa(dados, caminho_status, callback_log=self.log,
                                              callback_pause=pause_callback)
            self.log("Fila de processamento concluída (ou interrompida).")
            self.avisar(t("Aviso"), t("A fila de automação foi finalizada!"))
        except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
            self.log(f"Erro Crítico Web: {e}")
        finally:
            interface.na_interface(self._fim_do_robo)
