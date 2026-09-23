"""Tela "Upload de Condições" — Checkpoint 7.3 (Fase 7 do plano).

Lê as condições das fichas com IA e preenche as abas correspondentes no
portal, atualizando o `_STATUS_PMIB` ao concluir cada seção.
"""
from __future__ import annotations

import ast
import os
import threading
from tkinter import messagebox

import pandas as pd

from sigft.app import backends, file_dialogs
from sigft.app.theme import COLORS
from sigft.app.widgets import dialogs as app_dialogs, pickers as app_pickers
from sigft.core.excel.pmib_codes import normalize_pmib

import customtkinter as ctk


# =============================================================================
# MÓDULO 5: UPLOAD CONDIÇÕES (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloUploadConditions(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.api_key = self.controller.get_key("GEMINI")

        # Variáveis de Controle da UI
        self.var_processar_completos = ctk.BooleanVar(value=False)
        self.dados_em_memoria = []

        # Variáveis Globais de Arquivo
        self.caminho_status = ctk.StringVar()
        # [CP 7.2] `lista_fichas_paths` virou PROPRIEDADE que le do
        # FileQueueList -- a fila e a dona do estado agora, e manter uma lista
        # paralela aqui seria a segunda fonte de verdade que a refatoracao
        # existe para eliminar.

        # Referências aos processos ativos (para poder parar)
        self.processor_ativo = None
        self.automacao_ativa = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self, height=50, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(header, text="Upload de Condições no PMIB", font=("Roboto", 24, "bold"), text_color=COLORS["text_white"]).pack(side="left")

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
        # Como o STATUS_PMIB é usado na IA e no Web, fica no painel global
        frm_config = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8)
        frm_config.pack(fill="x", pady=10)

        ctk.CTkLabel(frm_config, text="Configuração Global (Requerido para IA e Web)", font=("Roboto", 14, "bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=15, pady=(10, 5))

        f_status = ctk.CTkFrame(frm_config, fg_color="transparent")
        f_status.pack(fill="x", padx=15, pady=(5, 10))
        self.btn_status = ctk.CTkButton(f_status, text="Selecionar _STATUS_PMIB", width=200, command=self._sel_status,
                                        fg_color="#3A3A3A", hover_color="#454545", font=("Roboto", 12))
        self.btn_status.pack(side="left")
        self.lbl_status_status = ctk.CTkLabel(f_status, text="Não selecionado", text_color="gray")
        self.lbl_status_status.pack(side="left", padx=10)

        ctk.CTkSwitch(f_status, text="Forçar processamento de fichas com status 'COMPLETO'",
                      variable=self.var_processar_completos,
                      onvalue=True, offvalue=False,
                      progress_color=COLORS["primary"]).pack(side="right", padx=10)

        # --- ABAS DE OPERAÇÃO (TabView) ---
        self.tabview = ctk.CTkTabview(self.content, fg_color="#2B2B2B", segmented_button_fg_color="#161616",
                                      segmented_button_selected_color=COLORS["primary"],
                                      segmented_button_selected_hover_color=COLORS["primary_hover"])
        self.tabview.pack(fill="both", expand=True, pady=10)

        tab1 = self.tabview.add("Processamento IA (Gerar Excel)")
        self._build_tab1(tab1)

        tab2 = self.tabview.add("Robô Web (Preencher Portal)")
        self._build_tab2(tab2)

    def _build_tab1(self, parent):
        scroll_area = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll_area.pack(fill="both", expand=True)

        frm_fichas = ctk.CTkFrame(scroll_area, fg_color="#2B2B2B", corner_radius=8)
        frm_fichas.pack(fill="both", expand=True, padx=10, pady=10)

        # [CP 7.2] Uma das 2 copias identicas da fila de fichas. A listbox, a
        # barra de rolagem, os 3 botoes e o contador vivem agora em
        # widgets/pickers.FileQueueList -- inclusive a memoria de caminhos, que
        # deixou de ser chamada manual.
        self.fila_fichas = app_pickers.FileQueueList(
            frm_fichas,
            chave="upload_conditions.fichas",
            categoria="excel",
            rotulo="Planilhas PMIB Selecionadas",
            titulo_dialogo="Selecione as Fichas PMIB",
            filetypes=[("Excel", "*.xlsx;*.xls")],
            ao_mudar=self._logar_mudanca_na_fila,
        )
        self.fila_fichas.label_contador.pack(anchor="w", padx=10, pady=(10, 0))
        self.fila_fichas.pack(fill="both", expand=True, padx=10, pady=5)

        frm_acoes = ctk.CTkFrame(scroll_area, fg_color="transparent")
        frm_acoes.pack(fill="x", padx=10, pady=(5, 15))

        self.btn_ia = ctk.CTkButton(frm_acoes, text="INICIAR PROCESSAMENTO IA", command=self._start_ia_process,
                                    fg_color=COLORS.get("primary", "#1f538d"), height=40, width=200, font=("Roboto", 13, "bold"))
        self.btn_ia.pack(side="left", padx=5, expand=True)

        self.btn_parar_ia = ctk.CTkButton(frm_acoes, text="PARAR", command=self._stop_ia_process, state="disabled",
                                          fg_color=COLORS.get("danger", "#B71C1C"), height=40, width=100, font=("Roboto", 13, "bold"))
        self.btn_parar_ia.pack(side="left", padx=5)

    def _build_tab2(self, parent):
        ctk.CTkLabel(parent, text="Lê um arquivo Excel com os resultados e inicia o Selenium para preencher o Portal.", font=("Roboto", 14)).pack(pady=20)

        self.btn_web_mem = ctk.CTkButton(parent, text="Usar Dados Recém Processados (Memória)", command=lambda: self._pre_start_web(self.dados_em_memoria),
                                         fg_color=COLORS.get("primary", "#1f538d"), hover_color=COLORS.get("primary_hover", "#14375e"), height=40, width=350, font=("Roboto", 13, "bold"))
        self.btn_web_mem.pack(pady=10)

        self.btn_web_file = ctk.CTkButton(parent, text="Carregar 'resultados_api_pmib.xlsx'", command=self._start_web_from_file,
                                          fg_color="#3A3A3A", hover_color="#454545", height=40, width=350, font=("Roboto", 13, "bold"))
        self.btn_web_file.pack(pady=10)

        self.btn_parar_web = ctk.CTkButton(parent, text="PARAR ROBÔ WEB", command=self._stop_web_process, state="disabled",
                                           fg_color=COLORS.get("danger", "#B71C1C"), height=40, width=350, font=("Roboto", 13, "bold"))
        self.btn_parar_web.pack(pady=(20, 10))

    # =========================================================================
    # FUNÇÕES DE SELEÇÃO DE ARQUIVOS
    # =========================================================================
    def _sel_status(self):
        path = file_dialogs.ask_open_file("upload_conditions.status_pmib", "excel", titulo="Selecione _STATUS_PMIB", filetypes=[("Excel", "*.xlsx;*.xlsm")])
        if path:
            self.caminho_status.set(path)
            self.lbl_status_status.configure(text=os.path.basename(path), text_color=COLORS["accent"])
            self.btn_status.configure(fg_color=COLORS["primary"])

    # [CP 7.2] A fila (listbox + contador + os 3 botoes + memoria de caminho)
    # e o FileQueueList. Sobra aqui so o texto do console, que e da TELA.
    @property
    def lista_fichas_paths(self):
        """Os caminhos na fila. Continua existindo com este nome porque o
        `_pre_start_ia` le por ele."""
        return self.fila_fichas.arquivos

    def _logar_mudanca_na_fila(self, acao, quantidade, total):
        if acao == "adicionou":
            self.log(f"{quantidade} arquivos selecionados. Total na fila: {total}")

    # =========================================================================
    # LÓGICA DE EXECUÇÃO: IA (Aba 1)
    # =========================================================================
    def _stop_ia_process(self):
        if messagebox.askyesno("Confirmar", "Deseja interromper a IA?\nO que já foi processado será mantido."):
            self.log("Sinal de parada enviado! Aguarde o término do arquivo atual...")
            self.btn_parar_ia.configure(state="disabled")
            if self.processor_ativo:
                self.processor_ativo.solicitar_parada()

    def _stop_web_process(self):
        if messagebox.askyesno("Confirmar", "Deseja interromper o robô?\nEle vai parar antes da próxima ficha."):
            self.log("Sinal de parada enviado ao robô! Aguardando o ciclo atual fechar...")
            self.btn_parar_web.configure(state="disabled")
            if self.automacao_ativa:
                self.automacao_ativa.solicitar_parada()

    # =========================================================================
    # A PARADA GERAL, pedida pela home  [2026-09-23]
    # =========================================================================
    def interromper_tudo(self):
        """Responde ao botão de parada da home (`sigft/app/parada.py`).

        Sem caixa de confirmação -- a home já perguntou. Devolve o rótulo do
        que estava rodando.
        """
        parados = []
        if self.processor_ativo:
            self.processor_ativo.solicitar_parada()
            self.btn_parar_ia.configure(state="disabled")
            parados.append("IA das condições")
        if self.automacao_ativa:
            self.automacao_ativa.solicitar_parada()
            self.btn_parar_web.configure(state="disabled")
            parados.append("robô das condições")
        if parados:
            self.log("Parada pedida na Home. Aguardando o ciclo atual fechar...")
        return parados

    def _start_ia_process(self):
        status_file = self.caminho_status.get()
        files = self.lista_fichas_paths

        if not status_file:
            return messagebox.showwarning("Aviso", "Por favor, selecione a planilha de _STATUS_PMIB na Configuração Global.")
        if not files:
            return messagebox.showwarning("Aviso", "Por favor, adicione pelo menos uma ficha à lista.")

        self.log(f"Iniciando processamento de {len(files)} arquivos...")
        self.btn_ia.configure(state="disabled")
        self.btn_parar_ia.configure(state="normal")  # Liga o botão parar
        self.api_key = self.controller.get_key("GEMINI")
        processar_completos = self.var_processar_completos.get()

        threading.Thread(target=self._worker_ia, args=(files, status_file, processar_completos), daemon=True).start()

    def _worker_ia(self, files, status_file, processar_completos=False):
        try:
            # Instancia o backend
            processor = backends.upload_conditions_backend.ConditionsProcessor(self.api_key)
            self.processor_ativo = processor  # Guarda a referência para o botão parar funcionar

            # Carrega o Status
            df_status, msg = processor.carregar_lookup_status(status_file)
            if df_status is None:
                self.log(f"Erro no Status: {msg}")
                self.after(0, lambda: self.btn_ia.configure(state="normal"))
                return
            self.log(msg)

            # 2026-08-18: o interruptor "Forçar processamento" agora CHEGA no
            # backend. Antes ele existia só na tela -- este bloco era um
            # comentário dizendo que a lógica ficaria "para o futuro", e o
            # usuário via um controle que não controlava nada.
            if processar_completos:
                self.log("Forçar processamento LIGADO: fichas já COMPLETO também serão reprocessadas.")

            resultados = processor.processar_ia_lote(
                files, df_status, callback_log=self.log,
                processar_completos=processar_completos,
            )

            self.after(0, self._on_ia_finished, resultados, processor)

        except Exception as e:
            self.log(f"Erro Fatal IA: {e}")
            self.after(0, lambda: self.btn_ia.configure(state="normal"))

    def _on_ia_finished(self, resultados, processor):
        self.btn_ia.configure(state="normal")
        self.btn_parar_ia.configure(state="disabled")
        self.processor_ativo = None  # Limpa a referência

        if not resultados:
            messagebox.showinfo("Aviso", "Nenhum dado gerado. Verifique o console.")
            return

        self.dados_em_memoria = resultados
        self.log(f"Sucesso! {len(resultados)} fichas processadas.")

        # Pergunta de Salvamento
        modo_salvar = messagebox.askyesnocancel("Salvar Resultados", "Como deseja salvar as fichas processadas?\n\nSIM = Novo Arquivo Excel\nNÃO = Anexar a um Excel Existente")

        caminho_final = None
        sucesso_salvar = False
        msg_salvar = ""

        if modo_salvar is True:
            caminho_final = file_dialogs.ask_save_file("upload_conditions.salvar_novo", "excel", titulo="Salvar Novo Arquivo", defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
            if caminho_final:
                sucesso_salvar, msg_salvar = processor.salvar_novo_arquivo(resultados, caminho_final)
        elif modo_salvar is False:
            caminho_final = file_dialogs.ask_open_file("upload_conditions.anexar", "excel", titulo="Selecionar arquivo para ANEXAR", filetypes=[("Excel", "*.xlsx")])
            if caminho_final:
                sucesso_salvar, msg_salvar = processor.anexar_a_arquivo_existente(resultados, caminho_final)

        if caminho_final:
            self.log(msg_salvar)
            if sucesso_salvar:
                if messagebox.askyesno("Continuar", "Dados salvos! Deseja pular para a Aba 2 e iniciar o Robô Web agora?"):
                    self.tabview.set("Robô Web (Preencher Portal)")
                    self._pre_start_web(self.dados_em_memoria)
            else:
                messagebox.showerror("Erro ao Salvar", msg_salvar)

    # =========================================================================
    # LÓGICA DE EXECUÇÃO: RPA (Aba 2)
    # =========================================================================
    def _pre_start_web(self, dados_dict_lista):
        if not self.caminho_status.get():
            return messagebox.showwarning("Aviso", "Selecione o _STATUS_PMIB na Configuração Global antes de iniciar o Robô.")

        if not dados_dict_lista:
            return messagebox.showwarning("Aviso", "Não há dados para iniciar a automação.")

        # [CP 7.2] `devolver_indices` existe por causa deste caso: a escolha volta como
        # POSICAO, para reencontrar o item na lista de origem. Devolver o texto
        # obrigaria a tela a procurar o item pela string exibida.
        def confirmar(indices):
            selecionados_finais = [dados_dict_lista[i] for i in indices]
            if selecionados_finais:
                self._start_web_process(selecionados_finais)
            else:
                self.log("Nenhuma ficha selecionada. Operação cancelada.")

        app_dialogs.SelecaoMultiplaDialog(
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
                "selectbackground": COLORS["primary"],
                "highlightthickness": 0, "borderwidth": 0,
            },
            ao_confirmar=confirmar,
        )

    def _start_web_from_file(self):
        excel_file = file_dialogs.ask_open_file("upload_conditions.excel_resultados", "excel", titulo="Selecione Excel de Resultados", filetypes=[("Excel", "*.xlsx;*.xls")])
        if not excel_file: return

        try:
            self.log("Lendo arquivo Excel, convertendo strings em dicionários...")
            # Força a leitura do PMIB como string logo de cara
            df = pd.read_excel(excel_file, dtype={'pmib_codigo': str})

            # Aplica a mesma correção caso o Excel já tenha salvo sem o zero ou com apóstrofo
            if 'pmib_codigo' in df.columns:
                # CP 1.2: delega para a normalização única e canônica
                # (core.excel.pmib_codes.normalize_pmib), que cobre TODOS os
                # casos que este código só tratava parcialmente (só
                # completava zero quando faltava EXATAMENTE 1 dígito, sem
                # tratar vírgula decimal) — ver docs/refatoracao/PENDENCIAS.md.
                df['pmib_codigo'] = df['pmib_codigo'].apply(normalize_pmib)

            cols_para_converter = ['dimensoes', 'controle_temperatura', 'nocivo', 'peso', 'protecao', 'outros_cuidados', 'logistica_reversa']
            for c in cols_para_converter:
                if c in df.columns:
                    df[c] = df[c].fillna('{}').apply(ast.literal_eval)

            dados = df.to_dict('records')
            self._pre_start_web(dados)
        except Exception as e:
            self.log(f"Erro ao ler Excel: {e}")
            messagebox.showerror("Erro de Leitura", f"Falha ao ler Excel: {e}")

    def _start_web_process(self, dados):
        self.btn_web_mem.configure(state="disabled")
        self.btn_web_file.configure(state="disabled")
        self.btn_parar_web.configure(state="normal")  # Liga o botão parar

        self.log(f"Iniciando fila de {len(dados)} fichas no navegador...")

        threading.Thread(target=self._worker_web, args=(dados,), daemon=True).start()

    def _worker_web(self, dados):
        auto = backends.upload_conditions_backend.UploadAutomation()
        self.automacao_ativa = auto
        status_file = self.caminho_status.get()

        # --- DEFINIÇÃO DOS CALLBACKS DE EVENTOS ---
        def pause_callback(section_name):
            evento_espera = threading.Event()
            # Chama a UI na thread principal
            self.after(0, lambda: self._mostrar_janela_pausa(section_name, evento_espera))
            # Trava o robô até o usuário clicar em "Continuar"
            evento_espera.wait()

        def ask_callback(motivo):
            evento_espera = threading.Event()
            resultado = {"retry": False}  # Dicionário mutável para pegar a resposta da UI
            self.after(0, lambda: self._mostrar_janela_retry(motivo, evento_espera, resultado))
            evento_espera.wait()
            return resultado["retry"]
        # -----------------------------------------

        try:
            self.log("Iniciando navegador...")
            auto.iniciar()

            self.log("Carregando portal PMIB...")
            auto.abrir_portal("https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList")

            # Substituí o messagebox do login por uma chamada da janela customizada também
            pause_callback("LOGIN_NECESSARIO")

            self.log("Login confirmado. Iniciando preenchimento...")
            # Agora passamos os dois callbacks novos
            auto.processar_lista(dados, status_file, callback_ask=ask_callback, callback_log=self.log, callback_pause=pause_callback)

            self.log("Fila de processamento web concluída.")
            self.after(0, lambda: messagebox.showinfo("Aviso", "A fila de automação foi finalizada!"))

        except Exception as e:
            self.log(f"Erro Crítico Web: {e}")
        finally:
            auto.fechar()
            self.automacao_ativa = None
            self.after(0, lambda: self.btn_web_mem.configure(state="normal"))
            self.after(0, lambda: self.btn_web_file.configure(state="normal"))
            self.after(0, lambda: self.btn_parar_web.configure(state="disabled"))

    def _mostrar_janela_pausa(self, section_name, evento_espera):
        """Janela não bloqueante para lidar com erros de salvamento do portal e Login.

        [CP 7.2] A janela em si mora em `sigft/app/widgets/dialogs.py`; aqui
        fica so a escolha da mensagem, que e o unico pedaco especifico desta
        tela. O metodo continua existindo com a mesma assinatura porque os
        `self.after(0, self._mostrar_janela_pausa, ...)` do worker chamam por
        este nome.
        """
        if section_name == app_dialogs.LOGIN_NECESSARIO:
            msg = app_dialogs.MSG_LOGIN_SOLTAR_ROBO
        else:
            msg = app_dialogs.msg_falha_ao_salvar(section_name)

        app_dialogs.PausaLoginDialog(self, mensagem=msg, evento_espera=evento_espera)

    def _mostrar_janela_retry(self, motivo, evento_espera, resultado_dict):
        """Janela com botões de decisão (Repetir / Cancelar) para lidar com Excel bloqueado.

        [CP 7.2] Delega para `widgets/dialogs.RetryLockDialog`. O contrato com
        o worker nao mudou: a decisao volta em `resultado_dict["retry"]`.
        """
        app_dialogs.RetryLockDialog(
            self, evento_espera=evento_espera, resultado=resultado_dict
        )

