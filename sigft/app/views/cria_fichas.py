"""Tela "Cria Fichas PMIB" — Checkpoint 7.3 (Fase 7 do plano).

A tela mais completa do app: lê a lista de materiais, categoriza os itens com
IA para escolher o PDM, deixa o usuário revisar, e cria as fichas no portal.
Tem também o fluxo de edição em massa de projeto.
"""
from __future__ import annotations

import threading
from tkinter import messagebox

import pandas as pd

from sigft.app import backends, file_dialogs
from sigft.app.theme import COLORS
# [CP B] Mensagens e dialogo da pausa de acao manual (login no portal).
from sigft.app.widgets import dialogs as app_dialogs
# [CP A/B] Mixin com `pausar_e_esperar`: abre o dialogo na thread da
# interface e segura o worker ate o usuario decidir. Vem ANTES de
# ctk.CTkFrame na heranca, para o super().__init__ passar por ele.
from sigft.app.widgets.espera import DialogosDeEspera
from sigft.app.views.janelas import (
    JanelaAcaoRobo,
    JanelaResumo,
    JanelaRevisaoPDM,
    JanelaSelecao,
)

import customtkinter as ctk


# =============================================================================
# MÓDULO 1: CRIA FICHAS NO PMIB (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloCriaFichas(DialogosDeEspera, ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Variáveis de Estado
        self.file_path_excel = None; self.file_path_pdm = None
        self.df_data_completo = None; self.df_data_selecionado = None
        self.df_processed = None; self.df_resumo_final = None
        self.bot = None
        self.api_key_gemini = self.controller.get_key("GEMINI")
        self.var_pular_ia = ctk.BooleanVar(value=False)

        # Layout Limpo (Sem sidebar interna)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=3)  # Dá peso 3 para a linha das Abas (ocupa mais espaço)
        self.grid_rowconfigure(2, weight=1)  # Dá peso 1 para a linha do Console (ocupa o resto do espaço disponível)

        # Header
        header = ctk.CTkFrame(self, height=50, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(header, text="Módulo de Criação", font=("Roboto", 24, "bold"), text_color=COLORS["text_white"]).pack(side="left")

        # Criando o sistema de Abas (Tabview)
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=20, pady=0)

        self.tab_criacao = self.tabview.add("Criação de Fichas")
        self.tab_edicao = self.tabview.add("Editar código do projeto")

        # Content Scrollable (Agora mora dentro da Aba 1)
        self.content = ctk.CTkScrollableFrame(self.tab_criacao, fg_color="transparent")
        self.content.pack(fill="both", expand=True)

        # Console (Log) - Agora totalmente responsivo
        # Removido o height fixo para não limitar o crescimento
        self.console = ctk.CTkTextbox(self, font=("Consolas", 12))
        # Trocado "ew" por "nsew" para ele esticar para cima e para baixo também
        self.console.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)

        self._build_ui()          # Constrói a aba de criação
        self._build_ui_edicao()   # Constrói a aba de edição

    def log(self, msg):
        # Garante que a injeção do texto aconteça sempre na fila da Thread Principal da interface
        self.after(0, lambda: [self.console.insert("end", f"> {msg}\n"), self.console.see("end")])

    def _build_ui(self):
        # --- ETAPA 1: CONFIGURAÇÃO E INPUTS ---
        frm_config = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8)
        frm_config.pack(fill="x", pady=10)

        ctk.CTkLabel(frm_config, text="1. Configuração Inicial", font=("Roboto", 16, "bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=15, pady=10)

        # Código do Projeto
        f_proj = ctk.CTkFrame(frm_config, fg_color="transparent")
        f_proj.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(f_proj, text="Código do Projeto:", width=150, anchor="w").pack(side="left")
        # Removido o width fixo para usar o layout responsivo do pack
        self.entry_projeto = ctk.CTkEntry(f_proj, placeholder_text="Ex: SERVIÇOS AUXILIARES ELÉTRICOS / CAP.05 - CONVERSORES ESTÁTICOS DE FREQUENCIA / Especificar subsistema | #ST00=B01MSE00&EPB020 / 08934100BAX00-FS00PB-51 | Evento de Pagamento: 2835 / 2835 a / 2836")
        # Adicionado fill="x" e expand=True para ocupar todo o espaço lateral
        self.entry_projeto.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Botão Selecionar PMIB
        f_pmib = ctk.CTkFrame(frm_config, fg_color="transparent")
        f_pmib.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(f_pmib, text="Arquivo STATUS_PMIB:", width=150, anchor="w").pack(side="left")
        self.btn_pmib = ctk.CTkButton(f_pmib, text="Selecionar Excel (.xlsx)", command=self.selecionar_excel_pmib,
                                      fg_color="#3A3A3A", hover_color="#454545", width=200)
        self.btn_pmib.pack(side="left")
        self.lbl_status = ctk.CTkLabel(f_pmib, text="Aguardando...", text_color="gray")
        self.lbl_status.pack(side="left", padx=10)

        # Checkbox Pular IA e Botão PDM
        f_opts = ctk.CTkFrame(frm_config, fg_color="transparent")
        f_opts.pack(fill="x", padx=15, pady=10)

        self.chk_pular = ctk.CTkCheckBox(f_opts, text="Pular IA (Dados já no Excel)", variable=self.var_pular_ia,
                                         command=self._toggle_pdm_button, fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"])
        self.chk_pular.pack(side="left")

        self.btn_pdm = ctk.CTkButton(f_opts, text="Selecionar PDMs e Instruções", command=self.selecionar_excel_pdm,
                                     fg_color="#3A3A3A", hover_color="#454545", state="normal")
        self.btn_pdm.pack(side="left", padx=20)

        # Novo Label para exibir o nome do arquivo PDM selecionado
        self.lbl_status_pdm = ctk.CTkLabel(f_opts, text="", text_color="gray")
        self.lbl_status_pdm.pack(side="left")

        # --- ETAPA 2: PROCESSAMENTO ---
        frm_action = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8)
        frm_action.pack(fill="x", pady=10)

        ctk.CTkLabel(frm_action, text="2. Execução", font=("Roboto", 16, "bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=15, pady=10)

        # Criamos uma "Tabela Invisível" para organizar os botões perfeitamente
        f_actions_grid = ctk.CTkFrame(frm_action, fg_color="transparent")
        f_actions_grid.pack(fill="x", padx=15, pady=10)

        # Configurando o grid: colunas 0 e 1 dividem o espaço restante igualmente, coluna 2 fica fixa
        f_actions_grid.grid_columnconfigure(0, weight=1, uniform="btn_cols")
        f_actions_grid.grid_columnconfigure(1, weight=1, uniform="btn_cols")
        f_actions_grid.grid_columnconfigure(2, weight=0)

        # --- LINHA 1 (Analisar e Robô) ---
        self.btn_run_ai = ctk.CTkButton(f_actions_grid, text="3. Analisar (IA)", command=self.run_ai_thread,
                                        fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                                        text_color=COLORS["text_white"], font=("Roboto", 14, "bold"),
                                        height=40, state="disabled")
        self.btn_run_ai.grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=(0, 5))

        self.btn_run_auto = ctk.CTkButton(f_actions_grid, text="4. Robô Web", command=self.run_automation_thread,
                                          fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                                          text_color=COLORS["text_white"], font=("Roboto", 14, "bold"),
                                          height=40, state="disabled")
        self.btn_run_auto.grid(row=0, column=1, sticky="ew", padx=(5, 15), pady=(0, 5))

        # --- LINHA 2 (Resumo e Salvar) ---
        self.btn_resumo = ctk.CTkButton(f_actions_grid, text="Ver Resumo", command=self.abrir_resumo_manual,
                                        fg_color="#3A3A3A", hover_color="#454545", text_color=COLORS["text_white"],
                                        font=("Roboto", 12, "bold"), height=40, state="disabled")
        self.btn_resumo.grid(row=1, column=0, sticky="ew", padx=(0, 5), pady=(5, 0))

        self.btn_save = ctk.CTkButton(f_actions_grid, text="5. Salvar no Excel", command=self.salvar_excel,
                                      fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                                      text_color=COLORS["text_white"], font=("Roboto", 12, "bold"),
                                      height=40, state="disabled")
        self.btn_save.grid(row=1, column=1, sticky="ew", padx=(5, 15), pady=(5, 0))

        # --- COLUNA LATERAL (Botão Limpar gigante, ocupando as linhas 0 e 1) ---
        self.btn_reset = ctk.CTkButton(f_actions_grid, text="🗑️\nLimpar", command=self.resetar_processo,
                                       fg_color=COLORS["danger"], hover_color="#B71C1C",
                                       text_color=COLORS["text_white"], font=("Roboto", 14, "bold"),
                                       width=100)  # sticky="nsew" faz ele esticar de cima a baixo
        self.btn_reset.grid(row=0, column=2, rowspan=2, sticky="nsew", padx=(0, 0), pady=0)

        # Barra de Progresso
        self.progress = ctk.CTkProgressBar(frm_action, progress_color=COLORS["accent"])
        self.progress.pack(fill="x", padx=15, pady=15)
        self.progress.set(0)

    def _build_ui_edicao(self):
        # Container igual ao de Criação
        self.content_edicao = ctk.CTkScrollableFrame(self.tab_edicao, fg_color="transparent")
        self.content_edicao.pack(fill="both", expand=True)

        # --- ETAPA 1: CONFIGURAÇÃO ---
        frm_config = ctk.CTkFrame(self.content_edicao, fg_color="#2B2B2B", corner_radius=8)
        frm_config.pack(fill="x", pady=10, padx=10)

        ctk.CTkLabel(frm_config, text="1. Configuração da Edição", font=("Roboto", 16, "bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=15, pady=10)

        # Novo Projeto
        f_proj = ctk.CTkFrame(frm_config, fg_color="transparent")
        f_proj.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(f_proj, text="Novo Código do Projeto:", width=180, anchor="w").pack(side="left")
        self.entry_novo_projeto = ctk.CTkEntry(f_proj, placeholder_text="Ex: NOVO CÓDIGO AQUI...")
        self.entry_novo_projeto.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Selecionar Excel
        f_excel = ctk.CTkFrame(frm_config, fg_color="transparent")
        f_excel.pack(fill="x", padx=15, pady=10)
        ctk.CTkLabel(f_excel, text="Selecionar Fichas (Excel):", width=180, anchor="w").pack(side="left")
        self.btn_excel_edicao = ctk.CTkButton(f_excel, text="Abrir Excel e Selecionar", command=self.selecionar_excel_edicao,
                                              fg_color="#3A3A3A", hover_color="#454545", width=200)
        self.btn_excel_edicao.pack(side="left")

        self.lbl_status_edicao = ctk.CTkLabel(f_excel, text="Nenhum item selecionado.", text_color="gray")
        self.lbl_status_edicao.pack(side="left", padx=10)

        # --- ETAPA 2: EXECUÇÃO ---
        frm_action = ctk.CTkFrame(self.content_edicao, fg_color="#2B2B2B", corner_radius=8)
        frm_action.pack(fill="x", pady=10, padx=10)
        ctk.CTkLabel(frm_action, text="2. Execução em Massa", font=("Roboto", 16, "bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=15, pady=10)

        f_btns = ctk.CTkFrame(frm_action, fg_color="transparent")
        f_btns.pack(fill="x", padx=15, pady=10)

        self.btn_run_edicao = ctk.CTkButton(f_btns, text="▶ Iniciar Robô de Edição", command=self.run_edicao_thread,
                                            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                                            text_color=COLORS["text_white"], font=("Roboto", 14, "bold"), height=40, state="disabled")
        self.btn_run_edicao.pack(fill="x", expand=True)

        self.progress_edicao = ctk.CTkProgressBar(frm_action, progress_color=COLORS["accent"])
        self.progress_edicao.pack(fill="x", padx=15, pady=15)
        self.progress_edicao.set(0)

    # --- Lógica Mantida (apenas ajustada para a nova UI) ---
    def _toggle_pdm_button(self):
        if self.var_pular_ia.get():
            self.btn_pdm.configure(state="disabled", fg_color="#2B2B2B")  # Cor "apagada"
            self.btn_run_ai.configure(state="normal", text="3. Processar (Direto)")
        else:
            self.btn_pdm.configure(state="normal", fg_color="#3A3A3A")
            self.btn_run_ai.configure(text="3. Analisar (IA)")

    def selecionar_excel_pmib(self):
        path = file_dialogs.ask_open_file("cria_fichas.excel_pmib", "excel", filetypes=[("Excel", "*.xlsx")])
        if not path: return
        self.file_path_excel = path
        cols = ["DESCRIÇÃO", "CÓDIGO PMIB"]

        df, cod_sug, erro = backends.DataManager.carregar_planilha_inteligente(path, "Lista de Materiais", cols)
        if df is None:
            df, cod_sug, erro = backends.DataManager.carregar_planilha_inteligente(path, 0, cols)

        if df is not None:
            self.df_data_completo = df
            self.log(f"Carregado: {len(df)} linhas.")

            if cod_sug:
                self.entry_projeto.delete(0, 'end')  # Limpa o campo (placeholder some)
                self.entry_projeto.insert(0, cod_sug)  # Escreve o novo código
                self.log("Código de Projeto preenchido automaticamente.")

            JanelaSelecao(self, df, self.pos_selecao)
        else:
            messagebox.showerror("Erro", erro)

    def pos_selecao(self, indices):
        self.df_data_selecionado = self.df_data_completo.iloc[indices].copy()
        self.log(f"Selecionado: {len(self.df_data_selecionado)} itens.")
        self.lbl_status.configure(text=f"{len(self.df_data_selecionado)} itens selecionados", text_color=COLORS["accent"])
        self.btn_pmib.configure(fg_color=COLORS["primary"])  # Marca visual de sucesso
        self._toggle_pdm_button()
        if not self.var_pular_ia.get():
            self.btn_pdm.configure(fg_color="#3A3A3A")

    def selecionar_excel_pdm(self):
        # Sugestão 1 já aplicada aqui: Filtro para mostrar apenas arquivos Excel
        path = file_dialogs.ask_open_file("cria_fichas.excel_pdm", "excel", filetypes=[("Arquivos Excel", "*.xlsx;*.xls")])
        if path:
            self.file_path_pdm = path
            self.btn_run_ai.configure(state="normal")
            self.btn_pdm.configure(fg_color=COLORS["primary"])

            # Pega apenas o nome do arquivo final (ex: "planilha.xlsx") ignorando as pastas
            nome_arquivo = path.split("/")[-1]
            self.lbl_status_pdm.configure(text=f"Selecionado: {nome_arquivo}", text_color=COLORS["accent"])
            self.log(f"PDMs carregados: {nome_arquivo}")

    def run_ai_thread(self):
        if not self.entry_projeto.get(): return messagebox.showwarning("Aviso", "Preencha o Código do Projeto.")
        if not self.var_pular_ia.get() and not self.file_path_pdm:
            return messagebox.showwarning("Aviso", "Selecione o arquivo de PDMs antes de iniciar a IA.")
        self.api_key_gemini = self.controller.get_key("GEMINI")
        threading.Thread(target=self._ai_worker).start()

    def _ai_worker(self):
        self.btn_run_ai.configure(state="disabled"); self.progress.configure(mode="indeterminate"); self.progress.start()
        try:
            cod_proj = self.entry_projeto.get()
            final_data = []
            if self.var_pular_ia.get():
                self.log("Modo 'Pular IA'. Lendo dados do Excel...")
                for index, row in self.df_data_selecionado.iterrows():
                    item_json = {
                        'item_processado': index,
                        'codigo_projeto': cod_proj,
                        'descricao_original': row['DESCRIÇÃO'],
                        'pdm_escolhido': row.get('PDM', 'NENHUM'),
                        'descricao_curta': row.get('DESC_CURTA', str(row['DESCRIÇÃO'])[:40]),
                        'origem': row.get('ORIGEM', 'Nacional'),
                        'tipo': row.get('TIPO', 'Não Reparável'),
                        'unidade': row.get('UNIDADE', 'Unidade'),
                        'tipo de fabricação': row.get('FABRICACAO', 'Catálogo')
                    }
                    final_data.append(item_json)
                self.log(f"Processados {len(final_data)} itens.")
            else:
                # O modelo sai do painel "Modelos de IA" (CP 3.3) e pode não
                # ser Gemini -- construir o categorizador ANTES de montar o
                # prompt é o que permite logar o modelo de verdade em vez de
                # "Gemini" fixo. O construtor só resolve config, não chama a
                # API, então nada é gasto por adiantá-lo.
                cat = backends.GeminiCategorizer(self.api_key_gemini)
                self.log(f"Processando com IA ({cat.modelo_em_uso})...")
                df_pdms = pd.read_excel(self.file_path_pdm, sheet_name="PDMs")
                lista_pdms = "\n".join("- " + df_pdms['PDM COMPLETO'].dropna().astype(str))

                # Resgatando a inteligência do Script 1
                df_instrucoes = pd.read_excel(self.file_path_pdm, sheet_name="Instruções PDMs")
                cols_grupo = ['N° GRUPO', 'GRUPO DESCRIÇÃO PT', 'GRUPO NOTAS PT']
                cols_classe = ['N° CLASSE', 'CLASSE DESCRIÇÃO PT', 'CLASSE INCLUI PT', 'CLASSE NÃO INCLUI PT', 'CLASSE NOTAS PT']
                df_instrucoes[cols_grupo] = df_instrucoes[cols_grupo].ffill()
                instrucoes = "INÍCIO DO MANUAL DE REGRAS:\n"

                for (n_grupo, desc_grupo, notas_grupo), classes_df in df_instrucoes.groupby(cols_grupo, sort=False):
                    instrucoes += f"\n### GRUPO {n_grupo}: {desc_grupo}\n"
                    if pd.notna(notas_grupo): instrucoes += f"  - Notas do Grupo: {notas_grupo}\n"
                    instrucoes += "  Classes deste Grupo:\n"
                    for _, row_inst in classes_df[cols_classe].iterrows():
                        if pd.notna(row_inst['N° CLASSE']):
                            instrucoes += f"    - CLASSE {row_inst['N° CLASSE']}: {row_inst['CLASSE DESCRIÇÃO PT']}\n"
                            if pd.notna(row_inst['CLASSE INCLUI PT']): instrucoes += f"      - Inclui: {row_inst['CLASSE INCLUI PT']}\n"
                            if pd.notna(row_inst['CLASSE NÃO INCLUI PT']): instrucoes += f"      - Não Inclui: {row_inst['CLASSE NÃO INCLUI PT']}\n"
                            if pd.notna(row_inst['CLASSE NOTAS PT']): instrucoes += f"      - Notas da Classe: {row_inst['CLASSE NOTAS PT']}\n"
                instrucoes += "\nFIM DO MANUAL DE REGRAS."

                res_json = cat.processar_lote(self.df_data_selecionado, lista_pdms, instrucoes)
                for i, item_json in enumerate(res_json):
                    row = self.df_data_selecionado.iloc[i]
                    item_json['codigo_projeto'] = cod_proj
                    item_json['descricao_original'] = row['DESCRIÇÃO']
                    final_data.append(item_json)
                self.log("IA Finalizada.")

            self.df_processed = pd.DataFrame(final_data)
            self.log("Abrindo janela de Revisão...")
            self.after(0, self.abrir_revisao_pdm)
        except Exception as e:
            self.log(f"Erro no processamento: {e}")
            self.after(0, lambda: self.btn_run_ai.configure(state="normal"))
        finally:
            self.progress.stop(); self.progress.configure(mode="determinate"); self.progress.set(0)

    def abrir_revisao_pdm(self):
        if self.df_processed is not None and not self.df_processed.empty:
            JanelaRevisaoPDM(self, self.df_processed, self._pos_revisao_concluida)
        else:
            messagebox.showerror("Erro", "Nenhum dado processado.")
            self.btn_run_ai.configure(state="normal")

    def _pos_revisao_concluida(self, df_atualizado):
        self.df_processed = df_atualizado
        self.log(f"Revisão OK. {len(self.df_processed)} itens prontos.")
        # [ALTERAÇÃO]: Removido 'text_color="black"' para manter o branco definido na criação
        self.btn_run_auto.configure(state="normal", fg_color=COLORS["accent"])
        self.btn_run_ai.configure(state="disabled", text="3. Analisar (OK)")

    def run_automation_thread(self):
        threading.Thread(target=self._bot_worker).start()

    def _bot_worker(self):
        self.btn_run_auto.configure(state="disabled"); self.bot = backends.AutomacaoPMIB()
        try:
            self.bot.iniciar_driver(); self.bot.abrir_portal('https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList')
            # [CP B] Era `messagebox.showinfo` chamado daqui de dentro do worker
            # -- criando widget fora da thread da interface. A instrucao de QUAL
            # pagina abrir foi preservada: e informacao util, nao ruido.
            self.pausar_e_esperar(app_dialogs.MSG_LOGIN_NOVA_FICHA)
            self.log("Iniciando Robô...")
            sucessos = []
            total = len(self.df_processed)

            # Variável de controle para abortar o loop principal (STOP)
            abortar_automacao = False

            for idx, row in self.df_processed.iterrows():
                if abortar_automacao:
                    break

                self.progress.set((idx+1)/total); self.log(f"Processando Item {idx+1}/{total}: {row['descricao_original'][:30]}...")

                # Trabalhamos com uma cópia mutável da linha para permitir alterar o PDM
                row_atual = row.copy()
                retry = True

                while retry:
                    status, res = self.bot.processar_item_individual(row_atual)

                    if status == "SUCESSO":
                        self.log(f" -> ✅ SUCESSO: PMIB {res[0]} | PDM {res[1]}")
                        sucessos.append((row_atual['descricao_original'], res[0], res[1]))
                        retry = False

                    elif status == "PULAR":
                        self.log(" -> ⏭️ PULADO automaticamente (PDM era 'NENHUM').")
                        sucessos.append((row_atual['descricao_original'], "VERIFICAR (PULADO)", "VERIFICAR (PULADO)"))
                        retry = False

                    else:
                        self.log(f" -> ❌ ERRO no Selenium: {res}")

                        # Chama a janela modal e espera a decisão do usuário
                        janela_decisao = JanelaAcaoRobo(self, msg_erro=res, pdm_atual=row_atual.get('pdm_escolhido', ''))
                        escolha = janela_decisao.escolha

                        if escolha == "RETRY":
                            self.log(" -> 🔄 Retentativa solicitada pelo usuário.")
                            messagebox.showinfo("Preparo", "Certifique-se de que a tela do navegador está na lista principal antes de clicar em OK.")
                            # O loop 'while' continua (retry = True)

                        elif escolha == "CHANGE_PDM":
                            novo_pdm = janela_decisao.novo_pdm
                            self.log(f" -> ✏️ PDM alterado pelo usuário para: {novo_pdm}")
                            row_atual['pdm_escolhido'] = novo_pdm
                            messagebox.showinfo("Preparo", "Certifique-se de que a tela do navegador está na lista principal antes de clicar em OK.")
                            # O loop 'while' continua com o 'row_atual' modificado

                        elif escolha == "SKIP":
                            self.log(" -> ⏭️ Item PULADO pelo usuário.")
                            sucessos.append((row_atual['descricao_original'], "VERIFICAR (PULADO)", "VERIFICAR (PULADO)"))
                            # Força o reset da tela para o próximo item do laço iniciar limpo
                            try: self.bot.abrir_portal('https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList')
                            except: pass
                            retry = False

                        elif escolha == "STOP":
                            self.log(" -> 🛑 Automação interrompida pelo usuário. Salvando progresso parcial...")
                            # Adiciona registro de erro apenas para o item que estava quebrado
                            sucessos.append((row_atual['descricao_original'], "INTERROMPIDO", "INTERROMPIDO"))
                            retry = False
                            abortar_automacao = True  # Quebra o for principal

            # --- Fim do Loop (ou Interrupção) ---
            self.log("Montando resumo final...")
            df_selenium = pd.DataFrame(sucessos, columns=['descricao_original', 'PMIB_CRIADO', 'PDM_COM_REVISAO'])
            self.df_resumo_final = pd.merge(self.df_processed, df_selenium, on='descricao_original', how='inner')

            self.after(0, lambda: JanelaResumo(self, self.df_resumo_final))
            self.btn_save.configure(state="normal"); self.btn_resumo.configure(state="normal")

            # Finaliza o driver
            try: self.bot.driver.quit()
            except: pass

        except Exception as e:
            self.log(f"Erro Fatal na Thread do Robô: {e}")
        finally:
            self.btn_run_auto.configure(state="normal")

    def abrir_resumo_manual(self):
        if self.df_resumo_final is not None: JanelaResumo(self, self.df_resumo_final)

    def salvar_excel(self):
        if hasattr(self, 'df_resumo_final') and self.df_resumo_final is not None:
            lista = [(r['descricao_original'], r['PMIB_CRIADO'], r['PDM_COM_REVISAO']) for _, r in self.df_resumo_final.iterrows()]

            salvo_com_sucesso = False
            while not salvo_com_sucesso:
                ok, msg = backends.DataManager.atualizar_excel_final(self.file_path_excel, "Lista de Materiais", lista)

                if ok:
                    messagebox.showinfo("Sucesso", f"Planilha atualizada!\n{msg}")
                    self.log(f"✅ Excel salvo com sucesso: {msg}")
                    salvo_com_sucesso = True
                else:
                    # Verifica se o erro retornado pelo backend foi de permissão (arquivo aberto)
                    if "ABERTO" in msg.upper() or "PERMISSION" in msg.upper():
                        resposta = messagebox.askretrycancel(
                            "Arquivo Aberto",
                            "O arquivo Excel está ABERTO ou bloqueado.\n\nPor favor, FECHE o arquivo _STATUS_PMIB no Excel e clique em 'Repetir' para tentar salvar novamente."
                        )
                        if not resposta:  # Usuário clicou em "Cancelar"
                            self.log("⚠️ Salvamento cancelado pelo usuário. Os dados não foram gravados no Excel.")
                            break
                    else:
                        # Outro erro inesperado (ex: aba não encontrada). Interrompe o loop.
                        messagebox.showerror("Erro ao Salvar", msg)
                        self.log(f"❌ Erro ao salvar Excel: {msg}")
                        break
        else:
            messagebox.showwarning("Aviso", "Não há dados processados para salvar.")

    def resetar_processo(self):
        """Limpa todo o estado do módulo para iniciar um novo lote limpo."""
        # 1. Limpa variáveis de backend
        self.file_path_excel = None
        self.file_path_pdm = None
        self.df_data_completo = None
        self.df_data_selecionado = None
        self.df_processed = None
        self.df_resumo_final = None
        if self.bot:
            try: self.bot.driver.quit()
            except: pass
            self.bot = None

        # 2. Reseta a UI visualmente
        self.lbl_status.configure(text="Aguardando...", text_color="gray")
        self.btn_pmib.configure(fg_color="#3A3A3A")

        self.lbl_status_pdm.configure(text="", text_color="gray")
        if not self.var_pular_ia.get():
            self.btn_pdm.configure(fg_color="#3A3A3A")

        self.entry_projeto.delete(0, 'end')  # Limpa o input

        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(0)  # Zera a barrinha

        self.console.delete("0.0", "end")
        self.log("Sistema limpo. Pronto para iniciar um novo lote.")

        # 3. Retorna os botões da Criação
        self.btn_run_ai.configure(state="disabled", text="3. Analisar (IA)")
        self.btn_run_auto.configure(state="disabled", fg_color=COLORS["primary"])
        self.btn_resumo.configure(state="disabled")
        self.btn_save.configure(state="disabled")

        # 4. Limpa as variáveis e visuais da Aba de Edição
        self.df_edicao_completo = None
        self.df_edicao_selecionado = None

        # O try/except garante que não quebre caso a UI da edição não tenha sido carregada ainda
        try:
            self.lbl_status_edicao.configure(text="Nenhum item selecionado.", text_color="gray")
            self.btn_excel_edicao.configure(fg_color="#3A3A3A")
            self.entry_novo_projeto.delete(0, 'end')
            self.progress_edicao.stop()
            self.progress_edicao.set(0)
            self.btn_run_edicao.configure(state="disabled")
        except AttributeError:
            pass

    # ---------------------------------------------------------
    # FUNÇÕES DA ABA DE EDIÇÃO
    # ---------------------------------------------------------
    def selecionar_excel_edicao(self):
        path = file_dialogs.ask_open_file("cria_fichas.excel_edicao", "excel", filetypes=[("Excel", "*.xlsx")])
        if not path: return
        cols = ["DESCRIÇÃO", "CÓDIGO PMIB"]
        df, cod_sug, erro = backends.DataManager.carregar_planilha_inteligente(path, "Lista de Materiais", cols)
        if df is None:
            df, cod_sug, erro = backends.DataManager.carregar_planilha_inteligente(path, 0, cols)
        if df is not None:
            # FILTRO INTELIGENTE: Remove da visualização linhas que não têm PMIB
            # (Evita que o usuário tente editar itens não criados)
            df_valido = df[df['CÓDIGO PMIB'].astype(str).str.strip() != ""]
            df_valido = df_valido.dropna(subset=['CÓDIGO PMIB'])

            if df_valido.empty:
                messagebox.showwarning("Aviso", "Nenhum CÓDIGO PMIB encontrado nesta planilha. Certifique-se de que as fichas já foram criadas.")
                return

            self.df_edicao_completo = df_valido.reset_index(drop=True)
            self.log(f"Aba Edição: Carregado {len(self.df_edicao_completo)} itens válidos com PMIB.")

            # Aproveita a mesma inteligência de sugerir o projeto
            if cod_sug:
                self.entry_novo_projeto.delete(0, 'end')
                self.entry_novo_projeto.insert(0, cod_sug)

            JanelaSelecao(self, self.df_edicao_completo, self.pos_selecao_edicao)
        else:
            messagebox.showerror("Erro", erro)

    def pos_selecao_edicao(self, indices):
        self.df_edicao_selecionado = self.df_edicao_completo.iloc[indices].copy()
        qtd = len(self.df_edicao_selecionado)

        self.log(f"Aba Edição: Selecionado {qtd} fichas para editar.")
        self.lbl_status_edicao.configure(text=f"{qtd} fichas selecionadas", text_color=COLORS["accent"])
        self.btn_excel_edicao.configure(fg_color=COLORS["primary"])

        if qtd > 0:
            self.btn_run_edicao.configure(state="normal")
        else:
            self.btn_run_edicao.configure(state="disabled")

    def run_edicao_thread(self):
        novo_projeto = self.entry_novo_projeto.get().strip()
        if not novo_projeto:
            return messagebox.showwarning("Aviso", "Preencha o Novo Código do Projeto.")

        if not hasattr(self, 'df_edicao_selecionado') or self.df_edicao_selecionado is None or self.df_edicao_selecionado.empty:
            return messagebox.showwarning("Aviso", "Selecione ao menos uma ficha no Excel para editar.")

        # Extrai automaticamente a lista de PMIBs da coluna do DataFrame
        lista_pmibs = self.df_edicao_selecionado['CÓDIGO PMIB'].apply(lambda x: str(x).strip() if pd.notna(x) else "").tolist()

        # Filtro extra de segurança (remove eventuais 'nan')
        lista_pmibs = [p for p in lista_pmibs if p and p.lower() != 'nan']

        threading.Thread(target=self._edicao_worker, args=(lista_pmibs, novo_projeto)).start()

    def _edicao_worker(self, lista_pmibs, novo_projeto):
        self.btn_run_edicao.configure(state="disabled")
        self.bot = backends.AutomacaoPMIB()
        try:
            self.bot.iniciar_driver()
            self.bot.abrir_portal('https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList')
            # [CP B] Idem, com a instrucao da pagina PRINCIPAL preservada.
            self.pausar_e_esperar(app_dialogs.MSG_LOGIN_PAGINA_PRINCIPAL)

            self.log(f"Iniciando Edição em Massa de {len(lista_pmibs)} fichas...")
            self.progress_edicao.configure(mode="determinate")

            for idx, pmib in enumerate(lista_pmibs):
                self.progress_edicao.set((idx + 1) / len(lista_pmibs))
                self.log(f"Editando PMIB [{idx+1}/{len(lista_pmibs)}]: {pmib}...")

                status, msg = self.bot.atualizar_projeto_em_massa(pmib, novo_projeto)

                if status == "SUCESSO":
                    self.log(f" -> ✅ SUCESSO: Projeto do {pmib} atualizado.")
                else:
                    self.log(f" -> ❌ ERRO no {pmib}: {msg}")
                    # Para a edição em massa, se der erro, vamos apenas registrar no log e tentar o próximo para não travar o lote

            self.log("Edição em massa concluída!")
            messagebox.showinfo("Concluído", "Processo de edição em massa finalizado. Verifique o log.")

        except Exception as e:
            self.log(f"Erro Fatal na Edição: {e}")
        finally:
            self.btn_run_edicao.configure(state="normal")
            try: self.bot.driver.quit()
            except: pass

