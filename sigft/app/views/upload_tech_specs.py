"""Tela "Upload de Características Técnicas" — Checkpoint 7.3 (Fase 7).

Extrai as características técnicas das fichas com IA, salva o resultado em
JSON, e envia para o portal — as duas metades podem rodar separadas, por isso
a tela tem abas.
"""
from __future__ import annotations

import json
import os
import threading
from tkinter import messagebox

from sigft.app import backends, file_dialogs
from sigft.app.theme import COLORS
from sigft.app.widgets import dialogs as app_dialogs, pickers as app_pickers

import customtkinter as ctk


# =============================================================================
# MÓDULO 6: UPLOAD CARACTERÍSTICAS TÉCNICAS (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloUploadTechSpecs(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.api_key = self.controller.get_key("GEMINI")

        # Instancia o nosso novo Orquestrador do Backend
        self.tech_controller = backends.upload_tech_specs_backend.TechSpecsController()

        # Variáveis de Controle da UI
        self.var_processar_completos = ctk.BooleanVar(value=False)
        self.dados_em_memoria = []  # Guarda o JSON caso o usuário queira rodar o web logo em seguida

        # Variáveis para a Aba 1
        self.caminho_status = ctk.StringVar()
        self.caminho_master = ctk.StringVar()
        # [CP 7.2] `lista_fichas_paths` virou PROPRIEDADE lida do FileQueueList
        # -- a fila e a dona dos caminhos completos.

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self, height=50, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(header, text="Upload Características Técnicas", font=("Roboto", 24, "bold"), text_color=COLORS["text_white"]).pack(side="left")

        # Content
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)

        # Console
        self.console = ctk.CTkTextbox(self, height=150, font=("Consolas", 12))
        self.console.grid(row=2, column=0, sticky="ew", padx=20, pady=10)

        self._build_ui()

    def log(self, txt):
        """Garante que o insert no widget de texto ocorra na thread principal."""
        self.after(0, self._log_thread_safe, txt)

    def _log_thread_safe(self, txt):
        self.console.insert("end", f"> {txt}\n")
        self.console.see("end")

    def _build_ui(self):
        # --- PAINEL DE CONFIGURAÇÃO GLOBAL ---
        frm_config = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8)
        frm_config.pack(fill="x", pady=10)

        ctk.CTkLabel(frm_config, text="Configuração Global", font=("Roboto", 14, "bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=15, pady=(10, 0))

        # Linha Única: Arquivo de Status Global e Opções
        f_status_global = ctk.CTkFrame(frm_config, fg_color="transparent")
        f_status_global.pack(fill="x", padx=15, pady=(10, 15))  # Ajustado o pady para dar respiro na borda inferior

        self.btn_status = ctk.CTkButton(f_status_global, text="Selecionar _STATUS_PMIB", width=200, command=self._sel_status,
                                        fg_color="#3A3A3A", hover_color="#454545", font=("Roboto", 12))
        self.btn_status.pack(side="left")

        self.lbl_status_status = ctk.CTkLabel(f_status_global, text="Não selecionado", text_color="gray")
        self.lbl_status_status.pack(side="left", padx=10)

        # O Switch agora entra no mesmo frame (f_status_global), ancorado à direita
        ctk.CTkSwitch(f_status_global, text="Forçar processamento de fichas 'COMPLETO'",
                      variable=self.var_processar_completos, onvalue=True, offvalue=False,
                      progress_color=COLORS["primary"]).pack(side="right", padx=10)

        # --- ABAS DE OPERAÇÃO (TabView) ---
        self.tabview = ctk.CTkTabview(self.content, fg_color="#2B2B2B", segmented_button_fg_color="#161616",
                                      segmented_button_selected_color=COLORS["primary"],
                                      segmented_button_selected_hover_color=COLORS["primary_hover"])
        self.tabview.pack(fill="both", expand=True, pady=10)

        # Aba 1: Processamento IA
        tab1 = self.tabview.add("Processamento IA (Gerar JSON)")
        self._build_tab1(tab1)

        # Aba 2: RPA
        tab2 = self.tabview.add("Robô Web (Preencher Portal)")
        self._build_tab2(tab2)

    def _build_tab1(self, parent):
        # --- NOVO: Frame com Scroll para telas pequenas ---
        scroll_area = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll_area.pack(fill="both", expand=True)

        # 1. Seletor do Master PDM
        frm_arquivos = ctk.CTkFrame(scroll_area, fg_color="#2B2B2B", corner_radius=8)
        frm_arquivos.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(frm_arquivos, text="Referência para IA", font=("Roboto", 14, "bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=15, pady=(10, 5))

        # Linha Master PDM (A linha Status foi movida para as Configurações Globais)
        f_master = ctk.CTkFrame(frm_arquivos, fg_color="transparent")
        f_master.pack(fill="x", padx=15, pady=(5, 15))
        self.btn_master = ctk.CTkButton(f_master, text="Selecionar PDM's SAM-GM", width=200, command=self._sel_master,
                                        fg_color="#3A3A3A", hover_color="#454545", font=("Roboto", 12))
        self.btn_master.pack(side="left")
        self.lbl_master_status = ctk.CTkLabel(f_master, text="Não selecionado", text_color="gray")
        self.lbl_master_status.pack(side="left", padx=10)

        # 2. Área de Fichas (Listbox)
        frm_fichas = ctk.CTkFrame(scroll_area, fg_color="#2B2B2B", corner_radius=8)
        frm_fichas.pack(fill="both", expand=True, padx=10, pady=10)

        # [CP 7.2] A outra copia identica da fila de fichas -- agora e o mesmo
        # FileQueueList do ModuloUploadConditions. O `selectmode=tk.EXTENDED`
        # (SHIFT/CTRL e arrastar o mouse) que o comentario antigo destacava
        # continua ligado: e o padrao do widget.
        self.fila_fichas = app_pickers.FileQueueList(
            frm_fichas,
            chave="upload_tech_specs.fichas",
            categoria="excel",
            rotulo="Fichas Selecionadas",
            titulo_dialogo="Selecione as Fichas PMIB",
            filetypes=[("Excel", "*.xlsx;*.xlsm")],
            ao_mudar=self._logar_mudanca_na_fila,
        )
        self.fila_fichas.label_contador.pack(anchor="w", padx=10, pady=(5, 0))
        self.fila_fichas.pack(fill="both", expand=True, padx=10, pady=5)

        # 3. Botões Principais (Iniciar e Parar)
        frm_acoes = ctk.CTkFrame(scroll_area, fg_color="transparent")
        frm_acoes.pack(fill="x", padx=10, pady=(5, 15))

        self.btn_ia = ctk.CTkButton(frm_acoes, text="INICIAR PROCESSAMENTO IA", command=self._start_ia_process,
                                    fg_color=COLORS.get("primary", "#1f538d"), height=40, width=200, font=("Roboto", 13, "bold"))
        self.btn_ia.pack(side="left", padx=5, expand=True)

        self.btn_parar_ia = ctk.CTkButton(frm_acoes, text="PARAR", command=self._stop_ia_process, state="disabled",
                                          fg_color=COLORS.get("danger", "#B71C1C"), height=40, width=100, font=("Roboto", 13, "bold"))
        self.btn_parar_ia.pack(side="left", padx=5)

    def _build_tab2(self, parent):
        ctk.CTkLabel(parent, text="Lê um arquivo JSON pronto e inicia o Selenium para preencher o Portal Itaipu.", font=("Roboto", 14)).pack(pady=20)

        self.btn_web_mem = ctk.CTkButton(parent, text="Usar Dados Recém Processados (Memória)", command=lambda: self._pre_start_web(self.dados_em_memoria),
                                         fg_color=COLORS.get("primary", "#1f538d"), hover_color=COLORS.get("primary_hover", "#14375e"), height=40, width=350, font=("Roboto", 13, "bold"))
        self.btn_web_mem.pack(pady=10)

        self.btn_web_file = ctk.CTkButton(parent, text="Carregar JSON Salvo no Computador", command=self._start_web_from_file,
                                          fg_color="#3A3A3A", hover_color="#454545", height=40, width=350, font=("Roboto", 13, "bold"))
        self.btn_web_file.pack(pady=10)

        # Novo botão de parar
        self.btn_parar_web = ctk.CTkButton(parent, text="PARAR ROBÔ WEB", command=self._stop_web_process, state="disabled",
                                           fg_color=COLORS.get("danger", "#B71C1C"), height=40, width=350, font=("Roboto", 13, "bold"))
        self.btn_parar_web.pack(pady=(20, 10))

    # =========================================================================
    # FUNÇÕES DE SELEÇÃO DE ARQUIVOS (Aba 1)
    # =========================================================================
    def _sel_status(self):
        path = file_dialogs.ask_open_file("upload_tech_specs.status_pmib", "excel", titulo="Selecione _STATUS_PMIB", filetypes=[("Excel", "*.xlsx;*.xlsm")])
        if path:
            self.caminho_status.set(path)
            self.lbl_status_status.configure(text=os.path.basename(path), text_color=COLORS["accent"])
            self.btn_status.configure(fg_color=COLORS["primary"])

    def _sel_master(self):
        path = file_dialogs.ask_open_file("upload_tech_specs.master", "excel", titulo="Selecione Master PDMs (Template)", filetypes=[("Excel", "*.xlsx;*.xlsm")])
        if path:
            self.caminho_master.set(path)
            self.lbl_master_status.configure(text=os.path.basename(path), text_color=COLORS["accent"])
            self.btn_master.configure(fg_color=COLORS["primary"])

    # [CP 7.2] Idem ModuloUploadConditions: a fila e o FileQueueList, e aqui
    # fica so o texto do console. O contador nao precisa mais de metodo: o
    # FileQueueList o mantem sozinho. Esta tela loga as TRES acoes; a outra so
    # loga a adicao -- o comportamento de cada uma foi preservado como estava.
    @property
    def lista_fichas_paths(self):
        return self.fila_fichas.arquivos

    def _logar_mudanca_na_fila(self, acao, quantidade, total):
        if acao == "adicionou":
            self.log(f"{quantidade} arquivos selecionados. Total na fila: {total}")
        elif acao == "removeu":
            self.log(f"{quantidade} arquivos removidos da fila. Total na fila: {total}")
        elif acao == "limpou":
            self.log("Todas as fichas foram removidas da fila.")

    def _stop_ia_process(self):
        """Dispara o sinal de parada no Backend"""
        if messagebox.askyesno("Confirmar", "Deseja realmente interromper o processo da IA?\nO que já foi processado será salvo."):
            self.log("Sinal de parada enviado! Aguarde o término do item atual...")
            self.btn_parar_ia.configure(state="disabled")
            self.tech_controller.cancelar_processo_ia()

    # =========================================================================
    # LÓGICA DE EXECUÇÃO: IA (Aba 1)
    # =========================================================================
    def _start_ia_process(self):
        status_file = self.caminho_status.get()
        master_file = self.caminho_master.get()
        files = self.lista_fichas_paths

        if not status_file:
            return messagebox.showwarning("Aviso", "Por favor, selecione a planilha de _STATUS_PMIB.")
        if not master_file:
            return messagebox.showwarning("Aviso", "Por favor, selecione a planilha Master PDMs.")
        if not files:
            return messagebox.showwarning("Aviso", "Por favor, adicione pelo menos uma ficha à lista.")

        self.log(f"Iniciando processamento de {len(files)} arquivos...")

        # Controle de Botões
        self.btn_ia.configure(state="disabled")
        self.btn_parar_ia.configure(state="normal")

        self.api_key = self.controller.get_key("GEMINI")
        processar_completos = self.var_processar_completos.get()

        threading.Thread(target=self._worker_ia, args=(files, status_file, master_file, processar_completos), daemon=True).start()

    def _worker_ia(self, files, status_file, master_file, processar_completos):
        try:
            resultados = self.tech_controller.executar_pipeline_ia(
                self.api_key, files, status_file, master_file, processar_completos, callback_log=self.log
            )

            # Passa a responsabilidade de interagir com a UI de volta para a Main Thread
            self.after(0, self._on_ia_finished, resultados)

        except Exception as e:
            self.log(f"Erro Fatal IA: {e}")
            self.after(0, lambda: self.btn_ia.configure(state="normal"))

    def _on_ia_finished(self, resultados):
        # Restaura os botões
        self.btn_ia.configure(state="normal")
        self.btn_parar_ia.configure(state="disabled")

        if not resultados:
            messagebox.showinfo("Aviso", "Nenhum dado gerado. Verifique o console.")
            return

        self.dados_em_memoria = resultados
        self.log(f"Sucesso! {len(resultados)} fichas geradas prontas para o robô.")

        # Lógica de Salvamento e Continuidade
        save_path = file_dialogs.ask_save_file("upload_tech_specs.salvar_json", "json", titulo="Salvar JSON de Resultados", defaultextension=".json", filetypes=[("JSON", "*.json")])
        if save_path:
            sucesso = self.tech_controller.salvar_json(resultados, save_path, callback_log=self.log)
            if sucesso:
                if messagebox.askyesno("Continuar", "Dados salvos! Deseja pular para a Aba 2 e iniciar o Robô Web agora?"):
                    self.tabview.set("Robô Web (Preencher Portal)")
                    self._start_web_process(self.dados_em_memoria)

    # =========================================================================
    # LÓGICA DE EXECUÇÃO: RPA (Aba 2)
    # =========================================================================
    def _pre_start_web(self, dados_json):
        """Abre o popup para o usuário escolher quais fichas do JSON ele quer processar."""
        if not dados_json:
            messagebox.showwarning("Aviso", "Não há dados para iniciar a automação.")
            return

        # [CP 7.2] Quarta e ultima variante do popup de selecao multipla. Identica a do
        # ModuloUploadConditions, tirando geometria, texto e tamanho da fonte.
        def confirmar(indices):
            selecionados_finais = [dados_json[i] for i in indices]
            if selecionados_finais:
                self._start_web_process(selecionados_finais)
            else:
                self.log("Nenhuma ficha selecionada. Operação cancelada.")

        app_dialogs.SelecaoMultiplaDialog(
            self,
            itens=[f"PMIB: {item.get('METADATA', {}).get('PMIB', 'N/A')} | {item.get('METADATA', {}).get('ARQUIVO_ORIGEM', 'N/A')}" for item in dados_json],
            titulo="Selecione as Fichas para Processar",
            instrucao="Selecione quais fichas do JSON deseja enviar para o site:",
            geometria="600x450",
            modal=True,
            com_selecionar_todos=True,
            devolver_indices=True,
            fonte_instrucao=("Roboto", 14, "bold"),
            fonte_lista=("Consolas", 11),
            estilo_lista={
                "bg": "#1E1E1E", "fg": "white",
                "selectbackground": COLORS["primary"],
                "highlightthickness": 0, "borderwidth": 0,
            },
            ao_confirmar=confirmar,
        )

    def _stop_web_process(self):
        """Envia o sinal para o Backend parar o Selenium"""
        if messagebox.askyesno("Confirmar", "Deseja interromper o robô?\nEle vai parar de forma segura antes da próxima ficha/ação."):
            self.log("Sinal de parada enviado ao robô! Aguardando o ciclo atual fechar...")
            self.btn_parar_web.configure(state="disabled")
            self.tech_controller.cancelar_processo_web()

    def _start_web_from_file(self):
        json_file = file_dialogs.ask_open_file("upload_tech_specs.json_resultados", "json", titulo="Selecione JSON de Resultados", filetypes=[("JSON", "*.json")])
        if not json_file: return

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                dados = json.load(f)
            self._pre_start_web(dados)  # <--- Alterado para chamar a janela de seleção
        except Exception as e:
            self.log(f"Erro ao ler JSON: {e}")

    def _start_web_process(self, dados):
        # Desabilita os botões de iniciar e liga o de Parar
        self.btn_web_mem.configure(state="disabled")
        self.btn_web_file.configure(state="disabled")
        self.btn_parar_web.configure(state="normal")

        self.log(f"Iniciando fila de {len(dados)} fichas no navegador...")

        caminho_status = self.caminho_status.get()
        if not caminho_status:
            self.log("Aviso: Arquivo _STATUS_PMIB não selecionado. As fichas NÃO serão marcadas como concluídas.")

        threading.Thread(target=self._worker_web, args=(dados, caminho_status), daemon=True).start()

    # 1. Adicionar o caminho_status aqui na assinatura da função
    def _worker_web(self, dados, caminho_status):
        try:
            # Função para pausar a automação usando Eventos (Thread-safe e Não-bloqueante)
            def pause_callback(estado_ou_pmib):
                # Cria uma "trava" para segurar o robô
                evento_espera = threading.Event()

                # Manda a interface principal desenhar a janela sem travar o programa
                self.after(0, lambda: self._mostrar_janela_pausa(estado_ou_pmib, evento_espera))

                # A thread do robô (Backend) dorme aqui até o usuário clicar no botão e liberar o evento
                evento_espera.wait()

            # 2. Passar o caminho_status para o controlador do backend
            self.tech_controller.executar_pipeline_rpa(dados, caminho_status, callback_log=self.log, callback_pause=pause_callback)

            self.log("Fila de processamento concluída (ou interrompida).")
            self.after(0, lambda: messagebox.showinfo("Aviso", "A fila de automação foi finalizada!"))

        except Exception as e:
            self.log(f"Erro Crítico Web: {e}")
        finally:
            # Restaura todos os botões no final
            self.after(0, lambda: self.btn_web_mem.configure(state="normal"))
            self.after(0, lambda: self.btn_web_file.configure(state="normal"))
            self.after(0, lambda: self.btn_parar_web.configure(state="disabled"))

    def _mostrar_janela_pausa(self, estado_ou_pmib, evento_espera):
        """Cria um aviso customizado que permite copiar os dados do console do app.

        [CP 7.2] Delega para `widgets/dialogs.PausaLoginDialog`. A DICA que
        vivia aqui -- "propositalmente NAO usamos grab_set(), e ele que
        bloqueava tudo" -- mudou de casa junto com a janela: esta no docstring
        do modulo `dialogs`, e agora tem teste que prova que ninguem o chama.
        """
        if estado_ou_pmib == app_dialogs.LOGIN_NECESSARIO:
            msg = app_dialogs.MSG_LOGIN_SOLTAR_ROBO
        else:
            msg = app_dialogs.msg_ficha_preenchida(estado_ou_pmib)

        app_dialogs.PausaLoginDialog(self, mensagem=msg, evento_espera=evento_espera)

