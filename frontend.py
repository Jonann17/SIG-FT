import customtkinter as ctk
import threading
import openpyxl
import pandas as pd
from tkinter import filedialog, messagebox, ttk, simpledialog
import tkinter as tk  # <--- ADICIONADO: Essencial para o ícone e manipulação de janelas
import os
import json
from functools import partial
from PIL import Image, ImageTk  # <--- ADICIONADO: ImageTk ajuda na compatibilidade
import importlib
import time
from dotenv import load_dotenv
import sys
import ast
import subprocess

from sigft.core.excel.pmib_codes import normalize_pmib
from sigft.core import prefs
from sigft.app import file_dialogs

# --- VARIÁVEIS GLOBAIS DOS BACKENDS (Inicialmente None) ---
# Isso evita erro de "NameError" nas classes antes do carregamento
DataManager = None
GeminiCategorizer = None
AutomacaoPMIB = None
pdm_backend = None
analyzer_backend = None
translator_backend = None
upload_conditions_backend = None
upload_tech_specs_backend = None
autospec_backend = None
lmr_backend = None
apagar_lmr_backend = None
pmib_manager_backend = None
search_pmib_backend = None

import upload_ficha_duplicada as backend

# Configuração Global
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")
CONFIG_FILE = "api_config.json"

# --- PALETA GE VERNOVA (Mantida) ---
COLORS = {
    "primary": "#035D67",
    "primary_hover": "#047A83",
    "accent": "#00C975",
    "accent_hover": "#00E085",
    "danger": "#D32F2F",
    "sidebar": "#161616",
    "background": "#212121",
    "text_light": "#E0E0E0",
    "text_white": "#FFFFFF"
}


# =============================================================================
# CLASSES AUXILIARES (Pop-ups)
# =============================================================================
class JanelaSelecao(ctk.CTkToplevel):
    def __init__(self, parent, dataframe, callback_confirmar):
        super().__init__(parent)
        self.title("Seleção de Itens")
        self.geometry("900x600")
        self.transient(parent)
        self.grab_set()

        ctk.CTkLabel(self, text="Selecione as linhas para processar:", font=("Arial", 16, "bold")).pack(pady=10)

        self.frame_tabela = ctk.CTkFrame(self)
        self.frame_tabela.pack(fill="both", expand=True, padx=10, pady=10)

        sb_y = ttk.Scrollbar(self.frame_tabela, orient="vertical")
        sb_x = ttk.Scrollbar(self.frame_tabela, orient="horizontal")

        self.tree = ttk.Treeview(
            self.frame_tabela,
            columns=list(dataframe.columns),
            show="headings",
            yscrollcommand=sb_y.set,
            xscrollcommand=sb_x.set,
            selectmode="extended"
        )

        sb_y.config(command=self.tree.yview); sb_x.config(command=self.tree.xview)
        sb_y.pack(side="right", fill="y"); sb_x.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)

        for col in dataframe.columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120)

        for index, row in dataframe.iterrows():
            valores = row.to_numpy().tolist()  # Deixa o Tkinter renderizar o dado bruto
            self.tree.insert("", "end", iid=index, values=valores)

        ctk.CTkButton(self, text="Confirmar Seleção", command=lambda: callback_confirmar([int(i) for i in self.tree.selection()]) or self.destroy()).pack(pady=20, fill="x", padx=20)


class JanelaResumo(ctk.CTkToplevel):
    def __init__(self, parent, df_comparacao):
        super().__init__(parent)
        self.title("Resumo Final")
        self.geometry("1000x500")
        self.transient(parent)

        ctk.CTkLabel(self, text="Resumo da Execução", font=("Arial", 18, "bold")).pack(pady=10)

        frame_tabela = ctk.CTkFrame(self)
        frame_tabela.pack(fill="both", expand=True, padx=10, pady=10)

        sb_y = ttk.Scrollbar(frame_tabela, orient="vertical")
        sb_x = ttk.Scrollbar(frame_tabela, orient="horizontal")

        colunas = ["Descrição Original", "PMIB Criado", "PDM (IA)", "PDM (Portal Final)"]
        tree = ttk.Treeview(frame_tabela, columns=colunas, show="headings", yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

        sb_y.config(command=tree.yview); sb_x.config(command=tree.xview)
        sb_y.pack(side="right", fill="y"); sb_x.pack(side="bottom", fill="x")
        tree.pack(side="left", fill="both", expand=True)

        for col in colunas: tree.heading(col, text=col); tree.column(col, width=300)

        for _, row in df_comparacao.iterrows():
            vals = [row.get('descricao_original', '-'), row.get('PMIB_CRIADO', '-'), row.get('pdm_escolhido', '-'), row.get('PDM_COM_REVISAO', '-')]
            tree.insert("", "end", values=vals)

        ctk.CTkButton(self, text="Fechar", command=self.destroy).pack(pady=10)


class JanelaRevisaoPDM(ctk.CTkToplevel):
    def __init__(self, parent, dataframe, callback_confirmar):
        super().__init__(parent)
        self.title("Revisão de PDMs - Pré-Automação")
        self.geometry("1100x600")
        self.transient(parent)
        self.grab_set()

        self.df_dados = dataframe.copy()  # Trabalha numa cópia para não quebrar o original se cancelar
        self.callback = callback_confirmar

        # --- Cabeçalho e Botões ---
        top_frame = ctk.CTkFrame(self)
        top_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(top_frame, text="Verifique os PDMs sugeridos antes da automação.", font=("Arial", 14, "bold")).pack(side="left")

        btn_confirmar = ctk.CTkButton(top_frame, text="CONFIRMAR E AVANÇAR >>", fg_color="green", command=self.confirmar)
        btn_confirmar.pack(side="right", padx=5)

        btn_editar = ctk.CTkButton(top_frame, text="Editar PDM Selecionado", command=self.editar_pdm)
        btn_editar.pack(side="right", padx=5)

        # --- Tabela (Treeview) ---
        # Usamos ttk.Treeview pois o ctk não tem tabela nativa com colunas complexas
        self.frame_tabela = ctk.CTkFrame(self)
        self.frame_tabela.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        sb_y = ttk.Scrollbar(self.frame_tabela, orient="vertical")
        sb_x = ttk.Scrollbar(self.frame_tabela, orient="horizontal")

        colunas = ["INDEX", "Descrição Original", "PDM Escolhido", "Descrição Curta", "Unidade", "Tipo"]

        self.tree = ttk.Treeview(
            self.frame_tabela,
            columns=colunas,
            show="headings",
            yscrollcommand=sb_y.set,
            xscrollcommand=sb_x.set,
            selectmode="extended"
        )

        sb_y.config(command=self.tree.yview); sb_x.config(command=self.tree.xview)
        sb_y.pack(side="right", fill="y"); sb_x.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)

        # Configura colunas
        self.tree.heading("INDEX", text="ID"); self.tree.column("INDEX", width=40)
        self.tree.heading("Descrição Original", text="Descrição Original"); self.tree.column("Descrição Original", width=350)
        self.tree.heading("PDM Escolhido", text="PDM Escolhido (EDITÁVEL)"); self.tree.column("PDM Escolhido", width=250)
        self.tree.heading("Descrição Curta", text="Descrição Curta"); self.tree.column("Descrição Curta", width=200)
        self.tree.heading("Unidade", text="UN"); self.tree.column("Unidade", width=50)
        self.tree.heading("Tipo", text="Tipo"); self.tree.column("Tipo", width=100)

        self.preencher_tabela()

    def preencher_tabela(self):
        # Limpa atual
        for item in self.tree.get_children(): self.tree.delete(item)

        # Preenche
        for index, row in self.df_dados.iterrows():
            vals = [
                index,
                row.get('descricao_original', ''),
                row.get('pdm_escolhido', ''),
                row.get('descricao_curta', ''),
                row.get('unidade', ''),
                row.get('tipo', '')
            ]
            self.tree.insert("", "end", iid=index, values=vals)

    def editar_pdm(self):
        selecionados = self.tree.selection()
        if not selecionados:
            messagebox.showwarning("Aviso", "Selecione uma ou mais linhas para editar o PDM.")
            return

        novo_pdm = simpledialog.askstring("Editar PDM", "Digite o novo código PDM completo (ex: PDM.1234.001 - NOME):")
        if novo_pdm:
            for iid in selecionados:
                # Atualiza no DataFrame
                idx = int(iid)
                self.df_dados.at[idx, 'pdm_escolhido'] = novo_pdm

                # Atualiza visualmente na Treeview (preserva os outros valores)
                atuais = self.tree.item(iid, "values")
                novos_valores = list(atuais)
                novos_valores[2] = novo_pdm  # Índice 2 é a coluna PDM
                self.tree.item(iid, values=novos_valores)

    def confirmar(self):
        if messagebox.askyesno("Confirmar", "Deseja prosseguir para a automação com estes dados?"):
            self.callback(self.df_dados)
            self.destroy()


class JanelaAcaoRobo(ctk.CTkToplevel):
    """
    Janela modal para decidir o que fazer quando o robô falha em um item.
    Retorna a escolha do usuário e, opcionalmente, um novo PDM.
    """
    def __init__(self, parent, msg_erro, pdm_atual):
        super().__init__(parent)
        self.title("Atenção: Intervenção Necessária")
        self.geometry("500x350")
        self.transient(parent)

        self.escolha = None
        self.novo_pdm = None

        # --- UI ---
        ctk.CTkLabel(self, text="Ocorreu um erro ao processar o item:", font=("Roboto", 14, "bold"), text_color="red").pack(pady=(15, 5))

        box_erro = ctk.CTkTextbox(self, height=60, font=("Consolas", 11))
        box_erro.pack(fill="x", padx=20, pady=5)
        box_erro.insert("0.0", str(msg_erro))
        box_erro.configure(state="disabled")

        ctk.CTkLabel(self, text=f"PDM Atual: {pdm_atual}", font=("Roboto", 12)).pack(pady=5)

        # Frame de Botões
        frm_botoes = ctk.CTkFrame(self, fg_color="transparent")
        frm_botoes.pack(fill="both", expand=True, padx=20, pady=10)

        # Opção 0: Tentar Novamente
        btn_retry = ctk.CTkButton(frm_botoes, text="[0] Tentar Novamente (Mesmo PDM)", command=lambda: self._responder("RETRY"))
        btn_retry.pack(fill="x", pady=5)

        # Opção 1: Pular
        btn_skip = ctk.CTkButton(frm_botoes, text="[1] Pular este Item", fg_color="#B8860B", hover_color="#DAA520", command=lambda: self._responder("SKIP"))
        btn_skip.pack(fill="x", pady=5)

        # Opção 2: Mudar PDM
        frm_mudar = ctk.CTkFrame(frm_botoes, fg_color="transparent")
        frm_mudar.pack(fill="x", pady=5)
        self.entry_pdm = ctk.CTkEntry(frm_mudar, placeholder_text="Novo código PDM...")
        self.entry_pdm.pack(side="left", fill="x", expand=True, padx=(0, 5))
        btn_mudar = ctk.CTkButton(frm_mudar, text="[2] Mudar PDM e Tentar", width=140, command=self._mudar_pdm)
        btn_mudar.pack(side="right")

        # Opção 3: Parar
        btn_stop = ctk.CTkButton(frm_botoes, text="[3] Parar Automação e Salvar", fg_color="red", hover_color="#8B0000", command=lambda: self._responder("STOP"))
        btn_stop.pack(fill="x", pady=5)

        self.protocol("WM_DELETE_WINDOW", lambda: self._responder("STOP"))  # Se fechar no X, para tudo
        self.grab_set()
        self.wait_window()  # Trava a thread aqui até uma decisão

    def _responder(self, acao):
        self.escolha = acao
        self.destroy()

    def _mudar_pdm(self):
        pdm_digitado = self.entry_pdm.get().strip()
        if pdm_digitado:
            self.novo_pdm = pdm_digitado
            self._responder("CHANGE_PDM")
        else:
            messagebox.showwarning("Aviso", "Digite o novo PDM antes de clicar.")


class JanelaSelecaoDuplicadas(ctk.CTkToplevel):
    """Janela para selecionar, dentre todas as duplicadas encontradas, quais rodar agora."""
    def __init__(self, parent, fila_completa, callback_confirmar):
        super().__init__(parent)
        self.title("Selecionar Fichas para Cópia")
        self.geometry("900x500")
        self.attributes('-topmost', True)
        self.grab_set()

        self.fila_completa = fila_completa
        self.callback_confirmar = callback_confirmar

        ctk.CTkLabel(self, text="Selecione as fichas que deseja processar neste lote:", font=("Roboto", 14, "bold")).pack(pady=10)

        # Configurando o Treeview
        frame_tree = ctk.CTkFrame(self)
        frame_tree.pack(fill="both", expand=True, padx=20, pady=10)

        cols = ("Descrição", "PMIB Original (Base)", "PMIB Alvo (Novo)")
        self.tree = ttk.Treeview(frame_tree, columns=cols, show="headings", selectmode="extended")

        self.tree.heading("Descrição", text="Descrição")
        self.tree.heading("PMIB Original (Base)", text="PMIB Original (Base)")
        self.tree.heading("PMIB Alvo (Novo)", text="PMIB Alvo (Novo)")

        self.tree.column("Descrição", width=400)
        self.tree.column("PMIB Original (Base)", width=150, anchor="center")
        self.tree.column("PMIB Alvo (Novo)", width=150, anchor="center")

        scroll_y = ttk.Scrollbar(frame_tree, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scroll_y.pack(side="right", fill="y")

        # Inserindo dados
        for idx, item in enumerate(self.fila_completa):
            self.tree.insert("", "end", iid=idx, values=(item["descricao"], item["pmib_original"], item["pmib_alvo"]))
            # Pré-seleciona todos por padrão
            self.tree.selection_add(idx)

        # Botões
        f_btns = ctk.CTkFrame(self, fg_color="transparent")
        f_btns.pack(pady=10)
        ctk.CTkButton(f_btns, text="Confirmar Seleção", command=self.confirmar, fg_color=COLORS["primary"]).pack(side="left", padx=10)
        ctk.CTkButton(f_btns, text="Cancelar", command=self.destroy, fg_color="#3A3A3A").pack(side="left", padx=10)

    def confirmar(self):
        selecionados_iids = self.tree.selection()
        if not selecionados_iids:
            messagebox.showwarning("Aviso", "Selecione ao menos um item.")
            return

        fila_selecionada = [self.fila_completa[int(i)] for i in selecionados_iids]
        self.callback_confirmar(fila_selecionada)
        self.grab_release()
        self.destroy()


class JanelaRevisaoEdicao(ctk.CTkToplevel):
    """Janela para ver o Resumo e editar os códigos Original/Alvo manualmente, caso o Regex tenha falhado."""
    def __init__(self, parent, fila_selecionada):
        super().__init__(parent)
        self.title("Revisão e Edição Manual")
        self.geometry("900x500")
        self.attributes('-topmost', True)
        self.grab_set()

        self.fila_selecionada = fila_selecionada  # Referência direta (alterações aqui afetam o frontend principal)

        ctk.CTkLabel(self, text="Dê um DUPLO CLIQUE em uma linha para editar os códigos PMIB.", font=("Roboto", 14, "bold")).pack(pady=10)

        # Configurando o Treeview
        frame_tree = ctk.CTkFrame(self)
        frame_tree.pack(fill="both", expand=True, padx=20, pady=10)

        cols = ("ID", "Descrição", "PMIB Original", "PMIB Alvo")
        self.tree = ttk.Treeview(frame_tree, columns=cols, show="headings", selectmode="browse")

        self.tree.heading("ID", text="ID")
        self.tree.heading("Descrição", text="Descrição")
        self.tree.heading("PMIB Original", text="PMIB Original (Ler Dados)")
        self.tree.heading("PMIB Alvo", text="PMIB Alvo (Escrever)")

        self.tree.column("ID", width=40, anchor="center")
        self.tree.column("Descrição", width=350)
        self.tree.column("PMIB Original", width=150, anchor="center")
        self.tree.column("PMIB Alvo", width=150, anchor="center")

        scroll_y = ttk.Scrollbar(frame_tree, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scroll_y.pack(side="right", fill="y")

        self.atualizar_tabela()

        # Evento de Duplo Clique para Editar
        self.tree.bind("<Double-1>", self.on_double_click)

        ctk.CTkButton(self, text="Concluir Revisão", command=self.destroy, fg_color=COLORS["primary"]).pack(pady=15)

    def atualizar_tabela(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for idx, item in enumerate(self.fila_selecionada):
            self.tree.insert("", "end", iid=idx, values=(idx+1, item["descricao"], item["pmib_original"], item["pmib_alvo"]))

    def on_double_click(self, event):
        selecionado = self.tree.selection()
        if not selecionado: return

        idx = int(selecionado[0])
        item_ref = self.fila_selecionada[idx]

        # Cria um pequeno popup de edição
        pop = ctk.CTkToplevel(self)
        pop.title("Editar Item")
        pop.geometry("400x300")
        pop.attributes('-topmost', True)
        pop.grab_set()

        ctk.CTkLabel(pop, text="PMIB Original (Ficha Base):", anchor="w").pack(fill="x", padx=20, pady=(15, 0))
        entry_orig = ctk.CTkEntry(pop)
        entry_orig.pack(fill="x", padx=20, pady=5)
        entry_orig.insert(0, item_ref["pmib_original"])

        ctk.CTkLabel(pop, text="PMIB Alvo (Nova Ficha):", anchor="w").pack(fill="x", padx=20, pady=(15, 0))
        entry_alvo = ctk.CTkEntry(pop)
        entry_alvo.pack(fill="x", padx=20, pady=5)
        entry_alvo.insert(0, item_ref["pmib_alvo"])

        def salvar_edicao():
            novo_orig = entry_orig.get().strip()
            novo_alvo = entry_alvo.get().strip()
            if not novo_orig or not novo_alvo:
                messagebox.showwarning("Aviso", "Os códigos não podem ficar vazios.")
                return

            # Atualiza a referência original em memória
            self.fila_selecionada[idx]["pmib_original"] = novo_orig
            self.fila_selecionada[idx]["pmib_alvo"] = novo_alvo

            self.atualizar_tabela()
            pop.destroy()

        ctk.CTkButton(pop, text="Salvar Alteração", command=salvar_edicao, fg_color=COLORS["primary"]).pack(pady=20)


# =============================================================================
# MÓDULO 1: CRIA FICHAS NO PMIB (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloCriaFichas(ctk.CTkFrame):
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

        df, cod_sug, erro = DataManager.carregar_planilha_inteligente(path, "Lista de Materiais", cols)
        if df is None:
            df, cod_sug, erro = DataManager.carregar_planilha_inteligente(path, 0, cols)

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
                self.log("Processando com IA (Gemini)...")
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

                cat = GeminiCategorizer(self.api_key_gemini)
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
        self.btn_run_auto.configure(state="disabled"); self.bot = AutomacaoPMIB()
        try:
            self.bot.iniciar_driver(); self.bot.abrir_portal('https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList')
            messagebox.showinfo("Ação Manual", "Faça login no portal.\nNavegue até a página com o botão 'Nova Ficha'.\n\nClique em OK apenas quando estiver pronto.")
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
                ok, msg = DataManager.atualizar_excel_final(self.file_path_excel, "Lista de Materiais", lista)

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
        df, cod_sug, erro = DataManager.carregar_planilha_inteligente(path, "Lista de Materiais", cols)
        if df is None:
            df, cod_sug, erro = DataManager.carregar_planilha_inteligente(path, 0, cols)
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
        self.bot = AutomacaoPMIB()
        try:
            self.bot.iniciar_driver()
            self.bot.abrir_portal('https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList')
            messagebox.showinfo("Ação Manual", "Faça login no portal.\nNavegue até a página PRINCIPAL (onde fica a barra de pesquisa).\n\nClique em OK apenas quando estiver pronto.")

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


# =============================================================================
# MÓDULO 2: PROCESSAMENTO DE PDMS (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloPDM(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.caminho_destino = ctk.StringVar()

        # Pré-preenchimento com a pasta padrão dos "PDMs modificados"
        # (decisão de produto nº 7 / CP 1.5), quando ela existir de fato no
        # disco desta máquina -- editável pelo usuário como sempre, é só o
        # valor inicial do campo. Os campos de ARQUIVO (template,
        # STATUS_PMIB) NÃO recebem o mesmo tratamento aqui: `get_default_dir`
        # devolve uma PASTA, e esses dois campos guardam o caminho de um
        # ARQUIVO Excel específico (sem Entry visível ligado a eles) -- pré-
        # preencher com uma pasta quebraria a leitura posterior (ex.:
        # `pd.read_excel(pasta, ...)`). Em vez disso, os DIÁLOGOS desses 2
        # campos (`_sel_template`/`_sel_status_pmib`) já abrem na pasta
        # padrão certa via `sigft.core.prefs.get_initial_dir` (chaves
        # `pdm.template`/`pdm.status_pmib`, migradas para `file_dialogs` no
        # CP 1.5) -- ver docs/refatoracao/PENDENCIAS.md para o racional
        # completo desta decisão.
        pasta_padrao_destino = prefs.get_default_dir("pdms_modificados")
        if pasta_padrao_destino is not None:
            self.caminho_destino.set(pasta_padrao_destino)

        # Novas variáveis visuais para a Aba 1
        self.path_sam_gm = ctk.StringVar()
        self.path_pdms_itaipu = ctk.StringVar()
        self.modo_proc = ctk.StringVar(value="todos")  # Preset do RadioButton

        # Novas variáveis visuais para a Aba 2
        self.path_status_pmib = ctk.StringVar()
        self.path_destino_fichas = ctk.StringVar()
        self.path_template = ctk.StringVar()
        self.modo_pmib = ctk.StringVar(value="todos")
        self.modo_saida_fichas = ctk.StringVar(value="apenas_planilhas")  # NOVA: Variável da Melhoria 1

        # Variável para Aba 3
        self.path_clean_dir = ctk.StringVar()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)  # PARA: O conteúdo usa só o espaço necessário
        self.grid_rowconfigure(2, weight=1)  # PARA: O console puxa todo o resto do espaço!

        # Header
        header = ctk.CTkFrame(self, height=50, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(header, text="Gerenciador de PDMs", font=("Roboto", 24, "bold"), text_color=COLORS["text_white"]).pack(side="left")

        # Content
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)

        # Console (Agora sem limite de altura e expandindo em todas as direções - nsew)
        self.console = ctk.CTkTextbox(self, font=("Consolas", 12))
        self.console.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)

        self._build_ui()

    def log(self, txt):
        self.console.insert("end", f"> {txt}\n")
        self.console.see("end")

    def _safe_log(self, txt):
        """Atualiza a interface a partir de uma Thread secundária sem quebrar o Tkinter"""
        self.after(0, lambda: self.log(txt))

    def _build_ui(self):
        # --- PAINEL DE CONFIGURAÇÃO GLOBAL ---
        frm_config = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8)
        frm_config.pack(fill="x", pady=10)

        ctk.CTkLabel(frm_config, text="Configuração Global", font=("Roboto", 14, "bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=15, pady=(10, 5))

        f_path = ctk.CTkFrame(frm_config, fg_color="transparent")
        f_path.pack(fill="x", padx=15, pady=(0, 15))
        ctk.CTkLabel(f_path, text="Pasta dos PDMs Modificados:", width=190, anchor="w").pack(side="left")
        self.entry_dest = ctk.CTkEntry(f_path, textvariable=self.caminho_destino, width=350)
        self.entry_dest.pack(side="left", padx=5)
        ctk.CTkButton(f_path, text="Selecionar", command=self._sel_destino,
                      fg_color="#3A3A3A", hover_color="#454545", width=100).pack(side="left")

        # --- ABAS DE OPERAÇÃO (TabView) ---
        self.tabview = ctk.CTkTabview(self.content, fg_color="#2B2B2B", segmented_button_fg_color="#161616",
                                      segmented_button_selected_color=COLORS["primary"],
                                      segmented_button_selected_hover_color=COLORS["primary_hover"])
        self.tabview.pack(fill="both", expand=True, pady=10)

        # Aba 1: Processar PDMs Itaipu
        tab1 = self.tabview.add("Processar PDMs")
        self._build_tab1(tab1)

        # Aba 2: Criar Fichas
        tab2 = self.tabview.add("Criar planilhas PMIB")
        self._build_tab2(tab2)

        # Aba 3: Limpeza
        tab3 = self.tabview.add("Excluir Duplicados")
        self._build_tab3(tab3)

    def _build_tab1(self, parent):
        # --- SEÇÃO 1: Fatiar lista geral (From Itaipu) ---
        frm_from = ctk.CTkFrame(parent, fg_color="#333333", corner_radius=8)
        frm_from.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(frm_from, text="1. Fatiar Arquivo Geral (From Itaipu)", font=("Roboto", 14, "bold")).pack(anchor="w", padx=10, pady=5)

        # Input do Excel (Estilo Arquivo: Botão + Label)
        f_xl = ctk.CTkFrame(frm_from, fg_color="transparent")
        f_xl.pack(fill="x", padx=10, pady=8)
        self.btn_sam_gm = ctk.CTkButton(f_xl, text="Selecionar PDM's SAM-GM (.xlsx)", width=240, command=self._sel_sam_gm,
                                        fg_color="#3A3A3A", hover_color="#454545", font=("Roboto", 12))
        self.btn_sam_gm.pack(side="left")
        self.lbl_sam_gm_status = ctk.CTkLabel(f_xl, text="Nenhum arquivo selecionado", text_color="gray")
        self.lbl_sam_gm_status.pack(side="left", padx=15)

        # Input da Pasta (Estilo Caminho: Entry + Botão mantido e alinhado)
        f_dir = ctk.CTkFrame(frm_from, fg_color="transparent")
        f_dir.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(f_dir, text="Pasta (PDMs From Itaipu):", width=240, anchor="w").pack(side="left")
        ctk.CTkEntry(f_dir, textvariable=self.path_pdms_itaipu, width=280).pack(side="left", padx=5)
        ctk.CTkButton(f_dir, text="Buscar", width=80, command=lambda: self.path_pdms_itaipu.set(file_dialogs.ask_directory("pdm.pdms_itaipu", "pasta", titulo="Pasta de Origem dos PDMs"))).pack(side="left")

        ctk.CTkButton(frm_from, text="Executar: Criar PDMs From Itaipu", command=self._op1_from_itaipu, fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"]).pack(pady=10)

        # --- SEÇÃO 2: Formatar PDMs (Modificados) ---
        frm_mod = ctk.CTkFrame(parent, fg_color="#333333", corner_radius=8)
        frm_mod.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(frm_mod, text="2. Formatar PDMs (Modificados)", font=("Roboto", 14, "bold")).pack(anchor="w", padx=10, pady=5)

        ctk.CTkLabel(frm_mod, text="Utiliza a 'Pasta (PDMs From Itaipu)' como base para leitura.", font=("Roboto", 11), text_color="gray").pack(anchor="w", padx=10)

        f_rad = ctk.CTkFrame(frm_mod, fg_color="transparent")
        f_rad.pack(fill="x", padx=10, pady=5)
        ctk.CTkRadioButton(f_rad, text="Lote (Todos os Novos)", variable=self.modo_proc, value="todos").pack(side="left", padx=10)
        ctk.CTkRadioButton(f_rad, text="Específico (Escolher 1 arquivo)", variable=self.modo_proc, value="especifico").pack(side="left", padx=10)

        ctk.CTkButton(frm_mod, text="Executar: Criar PDMs Modificados", command=self._op1_modificados, fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"]).pack(pady=10)

    def _build_tab2(self, parent):
        # --- SEÇÃO 1: Configuração de Arquivos e Pastas ---
        frm_files = ctk.CTkFrame(parent, fg_color="#333333", corner_radius=8)
        frm_files.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(frm_files, text="Configuração das Fichas PMIB", font=("Roboto", 14, "bold")).pack(anchor="w", padx=10, pady=5)

        # Input STATUS_PMIB (Estilo Arquivo: Botão + Label)
        f_stat = ctk.CTkFrame(frm_files, fg_color="transparent")
        f_stat.pack(fill="x", padx=10, pady=8)
        self.btn_pmib = ctk.CTkButton(f_stat, text="Selecionar STATUS_PMIB (.xlsx)", width=240, command=self._sel_status_pmib,
                                      fg_color="#3A3A3A", hover_color="#454545", font=("Roboto", 12))
        self.btn_pmib.pack(side="left")
        self.lbl_pmib_status = ctk.CTkLabel(f_stat, text="Nenhum arquivo selecionado", text_color="gray")
        self.lbl_pmib_status.pack(side="left", padx=15)

        # Input Destino Fichas (Estilo Caminho: Entry + Botão mantido)
        f_dest = ctk.CTkFrame(frm_files, fg_color="transparent")
        f_dest.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(f_dest, text="Pasta Destino das Fichas:", width=240, anchor="w").pack(side="left")
        ctk.CTkEntry(f_dest, textvariable=self.path_destino_fichas, width=280).pack(side="left", padx=5)
        ctk.CTkButton(f_dest, text="Buscar", width=80, command=lambda: self.path_destino_fichas.set(file_dialogs.ask_directory("pdm.destino_fichas", "pasta", titulo="Pasta onde as fichas serão criadas"))).pack(side="left")

        # Input Template (Estilo Arquivo: Botão + Label)
        f_temp = ctk.CTkFrame(frm_files, fg_color="transparent")
        f_temp.pack(fill="x", padx=10, pady=8)
        self.btn_template = ctk.CTkButton(f_temp, text="Selecionar Template (.xlsx)", width=240, command=self._sel_template,
                                          fg_color="#3A3A3A", hover_color="#454545", font=("Roboto", 12))
        self.btn_template.pack(side="left")
        self.lbl_template_status = ctk.CTkLabel(f_temp, text="Nenhum arquivo selecionado", text_color="gray")
        self.lbl_template_status.pack(side="left", padx=15)

        # --- SEÇÃO 2: Modo de Execução ---
        frm_exec = ctk.CTkFrame(parent, fg_color="#333333", corner_radius=8)
        frm_exec.pack(fill="x", padx=20, pady=10)

        # Modo de Seleção
        f_rad = ctk.CTkFrame(frm_exec, fg_color="transparent")
        f_rad.pack(fill="x", padx=10, pady=(10, 5))
        ctk.CTkLabel(f_rad, text="Seleção de Itens:", width=120, anchor="w", font=("Roboto", 12, "bold")).pack(side="left")
        ctk.CTkRadioButton(f_rad, text="Todos da Lista", variable=self.modo_pmib, value="todos").pack(side="left", padx=10)
        ctk.CTkRadioButton(f_rad, text="Selecionar Manualmente", variable=self.modo_pmib, value="selecionar").pack(side="left", padx=10)

        # Modo de Saída (Planilhas x Pastas)
        f_out = ctk.CTkFrame(frm_exec, fg_color="transparent")
        f_out.pack(fill="x", padx=10, pady=(5, 10))
        ctk.CTkLabel(f_out, text="Formato de Saída:", width=120, anchor="w", font=("Roboto", 12, "bold")).pack(side="left")
        ctk.CTkRadioButton(f_out, text="Apenas Planilhas (Padrão)", variable=self.modo_saida_fichas, value="apenas_planilhas").pack(side="left", padx=10)
        ctk.CTkRadioButton(f_out, text="Criar Subpastas + Planilhas", variable=self.modo_saida_fichas, value="com_pastas").pack(side="left", padx=10)

        ctk.CTkButton(frm_exec, text="Executar: Criar Fichas PMIB", command=self._op2_executar, fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"]).pack(pady=10)

    def _build_tab3(self, parent):
        ctk.CTkLabel(parent, text="Remove versões antigas de arquivos na pasta (limpeza de versões).", font=("Roboto", 14)).pack(pady=20)

        # Input Pasta Limpeza (Estilo Caminho: Entry + Botão Buscar)
        f_clean = ctk.CTkFrame(parent, fg_color="transparent")
        f_clean.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(f_clean, text="Pasta para Limpeza:", width=240, anchor="w").pack(side="left")
        ctk.CTkEntry(f_clean, textvariable=self.path_clean_dir, width=280).pack(side="left", padx=5)
        ctk.CTkButton(f_clean, text="Buscar", width=80, command=lambda: self.path_clean_dir.set(file_dialogs.ask_directory("pdm.clean_dir", "pasta", titulo="Selecione a pasta para limpar duplicatas"))).pack(side="left")

        self.btn_exec_clean = ctk.CTkButton(parent, text="Executar Limpeza", command=self._op3_executar,
                                            fg_color=COLORS["danger"], hover_color="#B71C1C", height=40, width=300)
        self.btn_exec_clean.pack(pady=30)

    def _sel_destino(self):
        p = file_dialogs.ask_directory("pdm.caminho_destino", "pasta")
        if p: self.caminho_destino.set(p)

    def _sel_sam_gm(self):
        f = file_dialogs.ask_open_file("pdm.sam_gm", "excel", titulo="Selecione o PDM's SAM-GM", filetypes=[("Excel", "*.xlsx *.xls")])
        if f:
            self.path_sam_gm.set(f)
            self.lbl_sam_gm_status.configure(text=os.path.basename(f), text_color=COLORS["accent"])
            self.btn_sam_gm.configure(fg_color=COLORS["primary"])

    def _sel_status_pmib(self):
        f = file_dialogs.ask_open_file("pdm.status_pmib", "excel", titulo="Selecione o STATUS_PMIB", filetypes=[("Excel", "*.xlsx *.xls")])
        if f:
            self.path_status_pmib.set(f)
            self.lbl_pmib_status.configure(text=os.path.basename(f), text_color=COLORS["accent"])
            self.btn_pmib.configure(fg_color=COLORS["primary"])

    def _sel_template(self):
        f = file_dialogs.ask_open_file("pdm.template", "excel", titulo="Selecione o Template", filetypes=[("Excel", "*.xlsx *.xls")])
        if f:
            self.path_template.set(f)
            self.lbl_template_status.configure(text=os.path.basename(f), text_color=COLORS["accent"])
            self.btn_template.configure(fg_color=COLORS["primary"])

    def _op1_from_itaipu(self):
        lista = self.path_sam_gm.get()
        pasta_alvo = self.path_pdms_itaipu.get()
        if not lista: return messagebox.showwarning("Aviso", "Por favor, selecione o arquivo PDM's SAM-GM na tela.")
        if not pasta_alvo: return messagebox.showwarning("Aviso", "Por favor, selecione a Pasta (PDMs From Itaipu) na tela.")

        # Thread para não congelar a tela
        def task():
            self._safe_log(f"Fatiando a lista geral: {os.path.basename(lista)}...")
            res = pdm_backend.pdms_fromItaipu_lista_geral(lista, pasta_alvo, log_callback=self._safe_log)
            self._safe_log(res)
            self.after(0, lambda: messagebox.showinfo("Relatório", res))

        threading.Thread(target=task, daemon=True).start()

    def _op1_modificados(self):
        if not self.caminho_destino.get(): return messagebox.showwarning("Aviso", "Selecione a Pasta dos PDMs Modificados primeiro.")
        origem = self.path_pdms_itaipu.get()
        if not origem: return messagebox.showwarning("Aviso", "Por favor, selecione a 'Pasta (PDMs From Itaipu)' na tela.")

        modo = self.modo_proc.get()
        if modo == "todos":
            def task():
                self._safe_log(f"Processando todos em: {origem}")
                count = 0
                for arq in pdm_backend.listar_arquivos_excel(origem):
                    tbl = pdm_backend.processar_arquivo_pdm(arq)
                    if tbl is not None:
                        ok, msg = pdm_backend.salvar_tabela_formatada(tbl, arq, self.caminho_destino.get())
                        self._safe_log(msg)  # Aqui o laço já está no front, então manda o safe_log direto
                        if ok: count += 1
                self._safe_log(f"Fim: {count} arquivos processados com sucesso.")
                self.after(0, lambda: messagebox.showinfo("Fim", f"{count} arquivos processados com sucesso."))
            threading.Thread(target=task, daemon=True).start()

        elif modo == "especifico":
            # `initialdir=origem`: override CONTEXTUAL -- a pasta que o usuário
            # ACABOU de escolher em "Pasta (PDMs From Itaipu)" nesta mesma tela,
            # momentos antes (não é memória entre sessões; ver
            # sigft.app.file_dialogs._resolver_initialdir).
            arq = file_dialogs.ask_open_file("pdm.arquivo_especifico", "excel", titulo="Selecione o arquivo PDM específico", filetypes=[("Excel", "*.xlsx *.xls")], initialdir=origem)
            if arq:
                def task_esp():
                    tbl = pdm_backend.processar_arquivo_pdm(arq)
                    if tbl is not None:
                        ok, msg = pdm_backend.salvar_tabela_formatada(tbl, arq, self.caminho_destino.get(), force=True)
                        self._safe_log(msg)
                        self.after(0, lambda: messagebox.showinfo("Status", msg))
                threading.Thread(target=task_esp, daemon=True).start()
            else:
                self.log("Seleção de arquivo específico cancelada.")

    def _op2_executar(self):
        pasta_modificados = self.caminho_destino.get()
        if not pasta_modificados: return messagebox.showwarning("Aviso", "Selecione a 'Pasta dos PDMs Modificados' primeiro.")

        status_pmib = self.path_status_pmib.get()
        destino_fichas = self.path_destino_fichas.get()
        template = self.path_template.get()
        modo = self.modo_pmib.get()

        if not status_pmib: return messagebox.showwarning("Aviso", "Por favor, busque o arquivo STATUS_PMIB na tela.")
        if not destino_fichas: return messagebox.showwarning("Aviso", "Por favor, busque a Pasta Destino das Fichas na tela.")
        if not template: return messagebox.showwarning("Aviso", "Por favor, busque o Template Ficha Técnica na tela.")

        lista_sel = None
        if modo == "selecionar":
            try:
                df = pd.read_excel(status_pmib, sheet_name="Lista de Materiais", skiprows=3)
                col_c = next((c for c in df.columns if "CÓDIGO PMIB" in str(c)), None)
                if not col_c: return messagebox.showerror("Erro", "Coluna 'CÓDIGO PMIB' não encontrada.")

                codigos_raw = df[col_c].dropna().unique().tolist()
                codigos_formatados = []
                for c in codigos_raw:
                    # CP 1.2: delega para a normalização única e canônica
                    # (core.excel.pmib_codes.normalize_pmib) — o código
                    # original TRUNCAVA a fração para 4 dígitos quando havia
                    # mais; o canônico NÃO trunca (diferença só visível com
                    # mais de 4 casas decimais, que não ocorre em PMIB
                    # real). Mantém o `str(c).strip()` explícito antes, para
                    # que a normalização sempre veja uma string (mesmo
                    # caminho de código exercido pelo original).
                    c_str = normalize_pmib(str(c).strip())
                    codigos_formatados.append(c_str)
                codigos = sorted(list(set(codigos_formatados)))

                sel_win = ctk.CTkToplevel(self)
                sel_win.title("Selecione os Códigos PMIB")
                sel_win.geometry("400x500")
                sel_win.transient(self)
                sel_win.grab_set()

                ctk.CTkLabel(sel_win, text="Selecione um ou mais códigos:", font=("Roboto", 14)).pack(pady=10)

                frame_lista = ctk.CTkFrame(sel_win, fg_color="transparent")
                frame_lista.pack(fill="both", expand=True, padx=20, pady=10)

                scrollbar = tk.Scrollbar(frame_lista)
                scrollbar.pack(side="right", fill="y")

                lb = tk.Listbox(frame_lista, selectmode="multiple", yscrollcommand=scrollbar.set, font=("Consolas", 11))
                lb.pack(side="left", fill="both", expand=True)
                scrollbar.config(command=lb.yview)

                for c in codigos: lb.insert("end", c)

                def confirm_sel():
                    nonlocal lista_sel
                    lista_sel = [lb.get(i) for i in lb.curselection()]
                    sel_win.destroy()

                ctk.CTkButton(sel_win, text="Confirmar Seleção", command=confirm_sel).pack(pady=15)
                self.wait_window(sel_win)

                if not lista_sel:
                    self.log("Seleção manual de códigos cancelada.")
                    return
            except Exception as e:
                return messagebox.showerror("Erro", f"Ocorreu um erro ao ler o STATUS_PMIB:\n{e}")

        modo_saida = self.modo_saida_fichas.get()
        criar_pastas = (modo_saida == "com_pastas")

        # THREADING DA CRIAÇÃO DE FICHAS
        def task():
            self._safe_log(f"Preparando diretórios (Modo: {'Com Pastas' if criar_pastas else 'Apenas Planilhas'})...")
            dados_pastas, msg = pdm_backend.processar_pastas_fichas(status_pmib, destino_fichas, lista_sel, criar_subpastas=criar_pastas)
            self._safe_log(msg)

            if not dados_pastas:
                self.after(0, lambda: messagebox.showinfo("Aviso", "Nenhum código foi processado."))
                return

            self._safe_log("Injetando os dados dos PDMs no Template (a partir da linha 79)...")

            # Repassando o callback para o backend conversar em tempo real com o terminal!
            msg_res, logs = pdm_backend.aplicar_templates_fichas(dados_pastas, pasta_modificados, template, log_callback=self._safe_log)
            self._safe_log(msg_res)

            self._safe_log(">>> Processo de criação de fichas finalizado!")
            self.after(0, lambda: messagebox.showinfo("Sucesso", "Processo de criação de fichas finalizado com sucesso!"))

        threading.Thread(target=task, daemon=True).start()

    def _op3_executar(self):
        pasta_limpeza = self.path_clean_dir.get()
        if not pasta_limpeza:
            return messagebox.showwarning("Aviso", "Por favor, selecione a pasta para limpeza primeiro.")

        def task():
            self._safe_log(f"Iniciando varredura por duplicados em: {pasta_limpeza}...")
            res = pdm_backend.logica_excluir_duplicados(pasta_limpeza, log_callback=self._safe_log)
            self._safe_log(res)
            self.after(0, lambda: messagebox.showinfo("Resultado", "Limpeza concluída."))

        threading.Thread(target=task, daemon=True).start()


# =============================================================================
# MÓDULO 3: TECHNICAL DATASHEET ANALYZER (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloAnalyzer(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.api_key = self.controller.get_key("GEMINI")

        # Variáveis de Estado
        self.selected_files = []
        self.selected_output = ""
        self.selected_pmib = ""
        self.score_value = 90.0

        # Pesos Personalizados (Inicialmente vazios, usa padrão do backend)
        self.custom_weights = {}
        self.max_var_points = 45.0  # Valor padrão

        # Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self, height=50, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(header, text="Technical Datasheet Analyzer", font=("Roboto", 24, "bold"), text_color=COLORS["text_white"]).pack(side="left")

        # Content
        self.content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)

        # Console
        self.console = ctk.CTkTextbox(self, height=150, font=("Consolas", 12))
        self.console.grid(row=2, column=0, sticky="ew", padx=20, pady=10)

        self._build_ui()

    def log(self, txt):
        self.console.insert("end", f"> {txt}\n"); self.console.see("end")

    def _build_ui(self):
        ctk.CTkLabel(self.content, text="Validação e Pontuação de Fichas Técnicas via IA", font=("Roboto", 16), text_color=COLORS["text_light"]).pack(pady=(0, 20))

        # --- CONTAINER 1: CRITÉRIOS ---
        frm_criteria = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8)
        frm_criteria.pack(fill="x", pady=10)

        ctk.CTkLabel(frm_criteria, text="1. Critérios de Aprovação e Pesos", font=("Roboto", 14, "bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=15, pady=(10, 5))

        # Frame interno para Slider e Botão de Config
        f_controls = ctk.CTkFrame(frm_criteria, fg_color="transparent")
        f_controls.pack(fill="x", padx=15, pady=5)

        self.lbl_score = ctk.CTkLabel(f_controls, text=f"Nota Mínima: {int(self.score_value)}%", font=("Roboto", 12, "bold"), text_color=COLORS["primary"])
        self.lbl_score.pack(side="left", padx=(0, 20))

        self.slider = ctk.CTkSlider(f_controls, from_=0, to=100, number_of_steps=100, command=self._update_slider_label, width=300,
                                    button_color=COLORS["primary"], progress_color=COLORS["primary"])
        self.slider.set(self.score_value)
        self.slider.pack(side="left")

        # Botão de Configurar Pesos
        self.btn_config = ctk.CTkButton(f_controls, text="⚙️ Configurar Pesos", width=150,
                                        command=self.abrir_config_pesos,
                                        fg_color="#3A3A3A", hover_color="#454545", font=("Roboto", 12))
        self.btn_config.pack(side="right")

        # --- CONTAINER 2: SELEÇÃO ---
        frm_files = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8)
        frm_files.pack(fill="x", pady=10)

        ctk.CTkLabel(frm_files, text="2. Seleção de Arquivos e Pastas", font=("Roboto", 14, "bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=15, pady=(10, 5))

        # A) Arquivos de Entrada
        f_in = ctk.CTkFrame(frm_files, fg_color="transparent")
        f_in.pack(fill="x", padx=15, pady=5)
        self.btn_files = ctk.CTkButton(f_in, text="Selecionar Fichas (.xlsx)", width=200, command=self._sel_input_files,
                                       fg_color="#3A3A3A", hover_color="#454545", font=("Roboto", 12))
        self.btn_files.pack(side="left")
        self.lbl_files_status = ctk.CTkLabel(f_in, text="Nenhum arquivo selecionado", text_color="gray")
        self.lbl_files_status.pack(side="left", padx=10)

        # B) Pasta de Saída
        f_out = ctk.CTkFrame(frm_files, fg_color="transparent")
        f_out.pack(fill="x", padx=15, pady=5)
        self.btn_out = ctk.CTkButton(f_out, text="Pasta de Saída", width=200, command=self._sel_output_dir,
                                     fg_color="#3A3A3A", hover_color="#454545", font=("Roboto", 12))
        self.btn_out.pack(side="left")
        self.lbl_out_status = ctk.CTkLabel(f_out, text="Nenhuma pasta selecionada", text_color="gray")
        self.lbl_out_status.pack(side="left", padx=10)

        # C) PMIB (Opcional)
        f_pmib = ctk.CTkFrame(frm_files, fg_color="transparent")
        f_pmib.pack(fill="x", padx=15, pady=(5, 15))
        self.btn_pmib = ctk.CTkButton(f_pmib, text="STATUS_PMIB (Opcional)", width=200, command=self._sel_pmib,
                                      fg_color="#3A3A3A", hover_color="#454545", font=("Roboto", 12))
        self.btn_pmib.pack(side="left")
        self.lbl_pmib_status = ctk.CTkLabel(f_pmib, text="Não selecionado (Padrão: sem contexto)", text_color="gray")
        self.lbl_pmib_status.pack(side="left", padx=10)

        # --- AÇÃO ---
        self.btn_run = ctk.CTkButton(self.content, text="INICIAR PROCESSAMENTO",
                                     height=50, width=300,
                                     command=self.iniciar_analise,
                                     font=("Roboto", 15, "bold"),
                                     fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"], text_color=COLORS["text_white"])
        self.btn_run.pack(pady=30)

    # --- Janela de Configuração de Pesos ---
    def abrir_config_pesos(self):
        if not analyzer_backend:
            return messagebox.showerror("Erro", "Backend Analyzer não carregado.")

        win = ctk.CTkToplevel(self)
        win.title("Configuração de Pesos")
        win.geometry("500x700")
        win.transient(self)

        # Frame Scrollable
        scroll = ctk.CTkScrollableFrame(win)
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(scroll, text="Pesos dos Campos Fixos", font=("Roboto", 14, "bold")).pack(pady=10)

        # Pega o mapa padrão do backend
        config_map = analyzer_backend.CONFIG_MAP
        self.entries_pesos = {}

        # Cria campos para cada item
        for key, conf in config_map.items():
            f = ctk.CTkFrame(scroll, fg_color="transparent")
            f.pack(fill="x", pady=2)

            # Nome formatado (ex: "tipo_fabricacao" -> "Tipo Fabricacao")
            name_fmt = key.replace("_", " ").title()
            ctk.CTkLabel(f, text=name_fmt, width=250, anchor="w").pack(side="left")

            # Valor atual (customizado ou padrão)
            current_val = self.custom_weights.get(key, conf["weight"])

            entry = ctk.CTkEntry(f, width=80)
            entry.insert(0, str(current_val))
            entry.pack(side="right")
            self.entries_pesos[key] = entry

        # Campo Especial: Variáveis Dinâmicas
        ctk.CTkLabel(scroll, text="--------------------------------", text_color="gray").pack(pady=10)
        ctk.CTkLabel(scroll, text="Configuração Global", font=("Roboto", 14, "bold")).pack(pady=5)

        f_var = ctk.CTkFrame(scroll, fg_color="transparent")
        f_var.pack(fill="x", pady=5)
        ctk.CTkLabel(f_var, text="Pontos Totais (Specs Técnicas):", width=250, anchor="w").pack(side="left")
        self.entry_max_vars = ctk.CTkEntry(f_var, width=80)
        self.entry_max_vars.insert(0, str(self.max_var_points))
        self.entry_max_vars.pack(side="right")

        # Botão Salvar
        btn_save = ctk.CTkButton(win, text="Salvar Pesos", command=lambda: self._salvar_pesos(win),
                                 fg_color=COLORS["primary"])
        btn_save.pack(pady=10)

    def _salvar_pesos(self, window):
        try:
            # Salva Pesos Fixos
            for key, entry in self.entries_pesos.items():
                val = float(entry.get())
                self.custom_weights[key] = val

            # Salva Max Vars
            self.max_var_points = float(self.entry_max_vars.get())

            messagebox.showinfo("Sucesso", "Pesos atualizados para esta sessão.")
            window.destroy()
        except ValueError:
            messagebox.showerror("Erro", "Certifique-se de usar apenas números (ponto para decimais).")

    # --- Callbacks UI ---
    def _update_slider_label(self, value):
        self.score_value = value
        self.lbl_score.configure(text=f"Nota Mínima: {int(value)}%")

    def _sel_input_files(self):
        files = file_dialogs.ask_open_files("analyzer.fichas", "excel", titulo="Selecione as Fichas Técnicas", filetypes=[("Excel", "*.xlsx")])
        if files:
            self.selected_files = list(files)
            self.lbl_files_status.configure(text=f"{len(files)} arquivos selecionados", text_color=COLORS["accent"])
            self.btn_files.configure(fg_color=COLORS["primary"])

    def _sel_output_dir(self):
        d = file_dialogs.ask_directory("analyzer.saida", "pasta", titulo="Selecione Pasta de Saída")
        if d:
            self.selected_output = d
            self.lbl_out_status.configure(text=os.path.basename(d) if os.path.basename(d) else d, text_color=COLORS["accent"])
            self.btn_out.configure(fg_color=COLORS["primary"])

    def _sel_pmib(self):
        f = file_dialogs.ask_open_file("analyzer.status_pmib", "excel", titulo="Selecione STATUS_PMIB", filetypes=[("Excel", "*.xlsx")])
        if f:
            self.selected_pmib = f
            self.lbl_pmib_status.configure(text=os.path.basename(f), text_color=COLORS["accent"])
            self.btn_pmib.configure(fg_color=COLORS["primary"])

    # --- Lógica ---
    def iniciar_analise(self):
        if not self.selected_files: return messagebox.showwarning("Faltam Dados", "Selecione as Fichas.")
        if not self.selected_output: return messagebox.showwarning("Faltam Dados", "Selecione a Pasta de Saída.")

        self.log(f"Iniciando análise de {len(self.selected_files)} arquivos...")

        # Log dos pesos usados (para auditoria)
        if self.custom_weights:
            self.log(">>> Usando PESOS PERSONALIZADOS nesta análise.")
        else:
            self.log(">>> Usando PESOS PADRÃO.")

        self.btn_run.configure(state="disabled")
        self.api_key = self.controller.get_key("GEMINI")
        threading.Thread(target=self._run_backend).start()

    def _run_backend(self):
        try:
            analyzer = analyzer_backend.DatasheetAnalyzer(self.api_key)
            pmib_sheet = None
            if self.selected_pmib:
                try:
                    wb = openpyxl.load_workbook(self.selected_pmib, data_only=True)
                    pmib_sheet = wb.active
                    self.log("STATUS_PMIB carregada.")
                except Exception as e: self.log(f"Erro STATUS_PMIB: {e}")

            for f_path in self.selected_files:
                fname = os.path.basename(f_path)
                subfolder = os.path.basename(os.path.dirname(f_path))

                # Chamada atualizada com os novos argumentos: custom_weights e max_variable_points
                iterador_logs = analyzer.processar_planilha(
                    input_filepath=f_path,
                    root_output_dir=self.selected_output,
                    subfolder_name=subfolder,
                    original_filename=fname,
                    pmib_sheet=pmib_sheet,
                    score_threshold=int(self.score_value),
                    custom_weights=self.custom_weights,        # <--- NOVO
                    max_variable_points=self.max_var_points,   # <--- NOVO
                    callback_manual_desc=lambda f, c: None
                )
                for log_msg in iterador_logs:
                    if not isinstance(log_msg, bool): self.log(log_msg)

            self.log("Concluído!")
            messagebox.showinfo("Sucesso", "Análise finalizada.")
        except Exception as e: self.log(f"Erro Fatal: {e}")
        finally: self.btn_run.configure(state="normal")


# =============================================================================
# MÓDULO 4: TRADUTOR DE FICHAS (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloTranslator(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.backend = translator_backend.TechnicalTranslator()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self, height=50, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(header, text="Tradutor Técnico (PT -> ES)", font=("Roboto", 24, "bold"), text_color=COLORS["text_white"]).pack(side="left")

        # Content
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)

        # Console
        self.console = ctk.CTkTextbox(self, height=150, font=("Consolas", 12))
        self.console.grid(row=2, column=0, sticky="ew", padx=20, pady=10)

        self._build_ui()

    def log(self, txt):
        self.console.insert("end", f"> {txt}\n"); self.console.see("end")

    def _build_ui(self):
        frm_main = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8)
        frm_main.pack(fill="x", pady=20)

        ctk.CTkLabel(frm_main, text="Tradução Automática de Características", font=("Roboto", 16, "bold"), text_color=COLORS["accent"]).pack(pady=(20, 10))
        ctk.CTkLabel(frm_main, text="Selecione as planilhas para traduzir do Português para Espanhol.\nO sistema cria uma nova aba traduzida.",
                     font=("Roboto", 13), text_color="gray").pack(pady=(0, 20))

        self.btn_run = ctk.CTkButton(frm_main, text="Selecionar Arquivos e Iniciar",
                                     height=50, width=300,
                                     command=self.iniciar_traducao,
                                     font=("Roboto", 14, "bold"),
                                     fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"], text_color=COLORS["text_white"])
        self.btn_run.pack(pady=10)

        self.btn_stop = ctk.CTkButton(frm_main, text="PARAR AGORA",
                                      height=40, width=200,
                                      command=self.parar_traducao,
                                      state="disabled",
                                      fg_color=COLORS["danger"], hover_color="#B71C1C", text_color=COLORS["text_white"])
        self.btn_stop.pack(pady=(10, 20))

    def iniciar_traducao(self):
        files = file_dialogs.ask_open_files("translator.fichas", "excel", titulo="Selecione as Fichas (.xlsx)", filetypes=[("Excel", "*.xlsx")])
        if not files: return

        self.log(f"Iniciando tradução de {len(files)} arquivos...")
        self.btn_run.configure(state="disabled")
        self.btn_stop.configure(state="normal")

        threading.Thread(target=self._worker, args=(files,)).start()

    def parar_traducao(self):
        self.backend.request_stop()
        self.log("[COMANDO] Parada solicitada...")

    def _worker(self, files):
        try:
            for f_path in files:
                for msg in self.backend.processar_arquivo(f_path):
                    if msg == "PARADO":
                        self.log("Processo interrompido pelo usuário.")
                        return
                    if msg in ["SUCESSO", "ERRO"]: continue
                    self.log(msg)

            self.log("Tradução em lote finalizada.")
            messagebox.showinfo("Sucesso", "Processo concluído.")
        except Exception as e:
            self.log(f"Erro Fatal: {e}")
        finally:
            self.btn_run.configure(state="normal")
            self.btn_stop.configure(state="disabled")


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
        self.lista_fichas_paths = []

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

        self.lbl_fichas_count = ctk.CTkLabel(frm_fichas, text="Planilhas PMIB Selecionadas (0)", font=("Roboto", 12, "bold"))
        self.lbl_fichas_count.pack(anchor="w", padx=10, pady=(10, 0))

        list_container = ctk.CTkFrame(frm_fichas, fg_color="transparent")
        list_container.pack(fill="both", expand=True, padx=10, pady=5)

        self.listbox_fichas = tk.Listbox(
            list_container, selectmode=tk.EXTENDED, bg="#1E1E1E", fg="#E0E0E0",
            selectbackground=COLORS.get("primary", "#1f538d"), selectforeground="white",
            highlightthickness=0, borderwidth=0, font=("Segoe UI", 11), activestyle="none"
        )
        self.listbox_fichas.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)

        scrollbar_fichas = tk.Scrollbar(list_container, bg="#2B2B2B", troughcolor="#3A3A3A")
        scrollbar_fichas.pack(side="left", fill="y", pady=5)
        self.listbox_fichas.config(yscrollcommand=scrollbar_fichas.set)
        scrollbar_fichas.config(command=self.listbox_fichas.yview)

        f_list_btns = ctk.CTkFrame(list_container, fg_color="transparent", width=120)
        f_list_btns.pack(side="right", fill="y", padx=(10, 0))
        ctk.CTkButton(f_list_btns, text="Adicionar Fichas", command=self._sel_fichas, fg_color="#3A3A3A").pack(pady=5)
        ctk.CTkButton(f_list_btns, text="Remover Seleção", command=self._remover_fichas_selecionadas, fg_color=COLORS.get("danger", "#B71C1C")).pack(pady=5)
        ctk.CTkButton(f_list_btns, text="Limpar Tudo", command=self._limpar_todas_fichas, fg_color="transparent", border_width=1, border_color="#555").pack(pady=5)

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

    def _atualizar_contador_fichas(self):
        total = len(self.lista_fichas_paths)
        self.lbl_fichas_count.configure(text=f"Planilhas PMIB Selecionadas ({total})")

    def _sel_fichas(self):
        files = file_dialogs.ask_open_files("upload_conditions.fichas", "excel", titulo="Selecione as Fichas PMIB", filetypes=[("Excel", "*.xlsx;*.xls")])
        if not files: return
        for f in files:
            if f not in self.lista_fichas_paths:
                self.lista_fichas_paths.append(f)
                nome_formatado = f" 📊  {os.path.basename(f)}"
                self.listbox_fichas.insert(tk.END, nome_formatado)
        self._atualizar_contador_fichas()
        self.log(f"{len(files)} arquivos selecionados. Total na fila: {len(self.lista_fichas_paths)}")

    def _remover_fichas_selecionadas(self):
        selecionados = list(self.listbox_fichas.curselection())
        if not selecionados: return
        selecionados.reverse()
        for index in selecionados:
            self.listbox_fichas.delete(index)
            del self.lista_fichas_paths[index]
        self._atualizar_contador_fichas()

    def _limpar_todas_fichas(self):
        self.listbox_fichas.delete(0, tk.END)
        self.lista_fichas_paths.clear()
        self._atualizar_contador_fichas()

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

        threading.Thread(target=self._worker_ia, args=(files, status_file), daemon=True).start()

    def _worker_ia(self, files, status_file):
        try:
            # Instancia o backend
            processor = upload_conditions_backend.ConditionsProcessor(self.api_key)
            self.processor_ativo = processor  # Guarda a referência para o botão parar funcionar

            # Carrega o Status
            df_status, msg = processor.carregar_lookup_status(status_file)
            if df_status is None:
                self.log(f"Erro no Status: {msg}")
                self.after(0, lambda: self.btn_ia.configure(state="normal"))
                return
            self.log(msg)

            # Para aplicar a lógica de "Forçar Processamento", faríamos uma filtragem prévia aqui
            # Como a lógica original já verifica se está completo, podemos passar o df_status modificado
            # ou simplesmente deixar o backend ler como está (no backend original de condições ele lê e pula).
            # Para manter simples, vamos rodar. Se o usuário quiser forçar, ele deveria alterar o Excel,
            # ou precisaremos adicionar essa lógica no backend no futuro.

            resultados = processor.processar_ia_lote(files, df_status, callback_log=self.log)

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

        # Cria a janela de seleção (Toplevel)
        top = ctk.CTkToplevel(self)
        top.title("Selecione as Fichas para Processar")
        top.geometry("500x400")
        top.attributes('-topmost', True)
        top.grab_set()

        ctk.CTkLabel(top, text="Selecione quais PMIBs deseja preencher no portal:", font=("Roboto", 14, "bold")).pack(pady=10)

        list_container = ctk.CTkFrame(top, fg_color="transparent")
        list_container.pack(fill="both", expand=True, padx=20, pady=5)

        listbox = tk.Listbox(list_container, selectmode=tk.MULTIPLE, bg="#1E1E1E", fg="white",
                             selectbackground=COLORS.get("primary", "#1f538d"), font=("Consolas", 12), highlightthickness=0, borderwidth=0)
        listbox.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(list_container, command=listbox.yview)
        scrollbar.pack(side="right", fill="y")
        listbox.config(yscrollcommand=scrollbar.set)

        # Preencher a lista com o PMIBs
        for item in dados_dict_lista:
            pmib = item.get("pmib_codigo", "N/A")
            listbox.insert(tk.END, f" Ficha PMIB: {pmib}")

        selecionados_finais = []

        def confirmar():
            indices = listbox.curselection()
            for i in indices:
                selecionados_finais.append(dados_dict_lista[i])
            top.grab_release()
            top.destroy()
            if selecionados_finais:
                self._start_web_process(selecionados_finais)
            else:
                self.log("Nenhuma ficha selecionada. Operação cancelada.")

        def selecionar_todos():
            listbox.select_set(0, tk.END)

        f_btns = ctk.CTkFrame(top, fg_color="transparent")
        f_btns.pack(pady=15)
        ctk.CTkButton(f_btns, text="Selecionar Todos", command=selecionar_todos, fg_color="#3A3A3A", width=150).pack(side="left", padx=10)
        ctk.CTkButton(f_btns, text="Confirmar Seleção", command=confirmar, fg_color=COLORS.get("primary", "#1f538d"), width=150).pack(side="left", padx=10)

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
        auto = upload_conditions_backend.UploadAutomation()
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
        """Janela não bloqueante para lidar com erros de salvamento do portal e Login."""
        top = ctk.CTkToplevel(self)
        top.title("Ação Manual Necessária")
        top.geometry("450x250")
        top.attributes('-topmost', True)

        def liberar_robo():
            evento_espera.set()
            top.destroy()

        top.protocol("WM_DELETE_WINDOW", liberar_robo)

        if section_name == "LOGIN_NECESSARIO":
            msg = "O navegador foi aberto.\n\n1. Faça o LOGIN no site.\n2. Navegue até a tela inicial do PMIB.\n3. Clique abaixo para soltar o robô."
        else:
            msg = f"Falha ao salvar a aba '{section_name}'. Ocorreu um erro no site.\n\n1. Resolva o problema no navegador.\n2. Clique em SALVAR no site.\n3. Clique no botão abaixo para continuar."

        ctk.CTkLabel(top, text=msg, font=("Roboto", 13), wraplength=400, justify="center").pack(pady=30, padx=20, expand=True)

        btn = ctk.CTkButton(top, text="CONTINUAR AUTOMAÇÃO", command=liberar_robo,
                            fg_color=COLORS.get("primary", "#1f538d"), hover_color=COLORS.get("primary_hover", "#14375e"),
                            height=45, font=("Roboto", 14, "bold"))
        btn.pack(pady=(0, 20))

    def _mostrar_janela_retry(self, motivo, evento_espera, resultado_dict):
        """Janela com botões de decisão (Repetir / Cancelar) para lidar com Excel bloqueado."""
        top = ctk.CTkToplevel(self)
        top.title("Arquivo Bloqueado")
        top.geometry("450x200")
        top.attributes('-topmost', True)

        def acao_repetir():
            resultado_dict["retry"] = True
            evento_espera.set()
            top.destroy()

        def acao_cancelar():
            resultado_dict["retry"] = False
            evento_espera.set()
            top.destroy()

        # Se fechar no X, cancela.
        top.protocol("WM_DELETE_WINDOW", acao_cancelar)

        msg = "O arquivo _STATUS_PMIB está aberto no Excel.\n\nPor favor, FECHE O ARQUIVO e clique em 'Tentar Novamente' para salvar o status da ficha concluída."
        ctk.CTkLabel(top, text=msg, font=("Roboto", 13), wraplength=400, justify="center").pack(pady=20, padx=20, expand=True)

        f_btns = ctk.CTkFrame(top, fg_color="transparent")
        f_btns.pack(pady=(0, 20))

        ctk.CTkButton(f_btns, text="Tentar Novamente", command=acao_repetir,
                      fg_color=COLORS.get("primary", "#1f538d"), width=150, height=40).pack(side="left", padx=10)
        ctk.CTkButton(f_btns, text="Ignorar e Continuar", command=acao_cancelar,
                      fg_color="transparent", border_width=1, border_color="#555", text_color="gray", width=150, height=40).pack(side="left", padx=10)


# =============================================================================
# MÓDULO 6: UPLOAD CARACTERÍSTICAS TÉCNICAS (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloUploadTechSpecs(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.api_key = self.controller.get_key("GEMINI")

        # Instancia o nosso novo Orquestrador do Backend
        self.tech_controller = upload_tech_specs_backend.TechSpecsController()

        # Variáveis de Controle da UI
        self.var_processar_completos = ctk.BooleanVar(value=False)
        self.dados_em_memoria = []  # Guarda o JSON caso o usuário queira rodar o web logo em seguida

        # Variáveis para a Aba 1
        self.caminho_status = ctk.StringVar()
        self.caminho_master = ctk.StringVar()
        self.lista_fichas_paths = []  # Lista invisível com os caminhos completos

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

        # --- NOVO: Variável de classe para o contador ---
        self.lbl_fichas_count = ctk.CTkLabel(frm_fichas, text="Fichas Selecionadas (0)", font=("Roboto", 12, "bold"))
        self.lbl_fichas_count.pack(anchor="w", padx=10, pady=(5, 0))

        list_container = ctk.CTkFrame(frm_fichas, fg_color="transparent")
        list_container.pack(fill="both", expand=True, padx=10, pady=5)

        # --- NOVO: selectmode=tk.EXTENDED permite usar SHIFT e CTRL e arrastar o mouse ---
        self.listbox_fichas = tk.Listbox(
            list_container,
            selectmode=tk.EXTENDED,
            bg="#1E1E1E",
            fg="#E0E0E0",
            selectbackground=COLORS.get("primary", "#1f538d"),
            selectforeground="white",
            highlightthickness=0,
            borderwidth=0,
            font=("Segoe UI", 11),
            activestyle="none"
        )
        self.listbox_fichas.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)

        scrollbar_fichas = tk.Scrollbar(list_container, bg="#2B2B2B", troughcolor="#3A3A3A")
        scrollbar_fichas.pack(side="left", fill="y", pady=5)
        self.listbox_fichas.config(yscrollcommand=scrollbar_fichas.set)
        scrollbar_fichas.config(command=self.listbox_fichas.yview)

        # Botões de Ação da Lista
        f_list_btns = ctk.CTkFrame(list_container, fg_color="transparent", width=120)
        f_list_btns.pack(side="right", fill="y", padx=(10, 0))
        ctk.CTkButton(f_list_btns, text="Adicionar Fichas", command=self._sel_fichas, fg_color="#3A3A3A").pack(pady=5)
        ctk.CTkButton(f_list_btns, text="Remover Seleção", command=self._remover_fichas_selecionadas, fg_color=COLORS.get("danger", "#B71C1C")).pack(pady=5)
        ctk.CTkButton(f_list_btns, text="Limpar Tudo", command=self._limpar_todas_fichas, fg_color="transparent", border_width=1, border_color="#555").pack(pady=5)

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

    def _atualizar_contador_fichas(self):
        """Atualiza a label que mostra a quantidade de arquivos na fila"""
        total = len(self.lista_fichas_paths)
        self.lbl_fichas_count.configure(text=f"Fichas Selecionadas ({total})")

    def _sel_fichas(self):
        files = file_dialogs.ask_open_files("upload_tech_specs.fichas", "excel", titulo="Selecione as Fichas PMIB", filetypes=[("Excel", "*.xlsx;*.xlsm")])
        if not files: return
        for f in files:
            if f not in self.lista_fichas_paths:
                self.lista_fichas_paths.append(f)
                nome_formatado = f" 📊  {os.path.basename(f)}"
                self.listbox_fichas.insert(tk.END, nome_formatado)

        self._atualizar_contador_fichas()
        self.log(f"{len(files)} arquivos selecionados. Total na fila: {len(self.lista_fichas_paths)}")

    def _remover_fichas_selecionadas(self):
        selecionados = list(self.listbox_fichas.curselection())
        if not selecionados: return

        selecionados.reverse()  # Remove de trás pra frente para não bagunçar os índices
        for index in selecionados:
            self.listbox_fichas.delete(index)
            del self.lista_fichas_paths[index]

        self._atualizar_contador_fichas()
        self.log(f"{len(selecionados)} arquivos removidos da fila. Total na fila: {len(self.lista_fichas_paths)}")

    def _limpar_todas_fichas(self):
        self.listbox_fichas.delete(0, tk.END)
        self.lista_fichas_paths.clear()

        self._atualizar_contador_fichas()
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

        # Cria a janela de seleção (Toplevel)
        top = ctk.CTkToplevel(self)
        top.title("Selecione as Fichas para Processar")
        top.geometry("600x450")
        top.attributes('-topmost', True)
        top.grab_set()  # Foca o clique apenas nesta janela até ela ser fechada

        ctk.CTkLabel(top, text="Selecione quais fichas do JSON deseja enviar para o site:", font=("Roboto", 14, "bold")).pack(pady=10)

        # Frame da lista
        list_container = ctk.CTkFrame(top, fg_color="transparent")
        list_container.pack(fill="both", expand=True, padx=20, pady=5)

        # Usamos tk.Listbox porque o CustomTkinter nativo ainda não tem uma Listbox de seleção múltipla tão boa
        listbox = tk.Listbox(list_container, selectmode=tk.MULTIPLE, bg="#1E1E1E", fg="white",
                             selectbackground=COLORS.get("primary", "#1f538d"), font=("Consolas", 11), highlightthickness=0, borderwidth=0)
        listbox.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(list_container, command=listbox.yview)
        scrollbar.pack(side="right", fill="y")
        listbox.config(yscrollcommand=scrollbar.set)

        # Preencher a lista
        for item in dados_json:
            meta = item.get("METADATA", {})
            pmib = meta.get("PMIB", "N/A")
            arq = meta.get("ARQUIVO_ORIGEM", "N/A")
            listbox.insert(tk.END, f"PMIB: {pmib} | {arq}")

        # Funções internas dos botões do popup
        selecionados_finais = []

        def confirmar():
            indices = listbox.curselection()
            for i in indices:
                selecionados_finais.append(dados_json[i])
            top.grab_release()
            top.destroy()
            if selecionados_finais:
                self._start_web_process(selecionados_finais)  # <-- Agora sim, envia pra automação
            else:
                self.log("Nenhuma ficha selecionada. Operação cancelada.")

        def selecionar_todos():
            listbox.select_set(0, tk.END)

        # Frame de botões
        f_btns = ctk.CTkFrame(top, fg_color="transparent")
        f_btns.pack(pady=15)
        ctk.CTkButton(f_btns, text="Selecionar Todos", command=selecionar_todos, fg_color="#3A3A3A", width=150).pack(side="left", padx=10)
        ctk.CTkButton(f_btns, text="Confirmar Seleção", command=confirmar, fg_color=COLORS.get("primary", "#1f538d"), width=150).pack(side="left", padx=10)

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
        """Cria um aviso customizado que permite copiar os dados do console do app."""
        top = ctk.CTkToplevel(self)
        top.title("Ação Manual Necessária")
        top.geometry("450x250")
        top.attributes('-topmost', True)  # Fica sempre no topo, mas permite clicar fora!
        # DICA: Nós propositalmente NÃO usamos top.grab_set() aqui. É ele que bloqueava tudo!

        # Função interna para liberar o robô quando clicar no botão ou fechar no "X"
        def liberar_robo():
            evento_espera.set()  # Destrava o wait() lá na thread do robô
            top.destroy()

        # Garante que se o usuário fechar no "X" da janela, o robô também é liberado
        top.protocol("WM_DELETE_WINDOW", liberar_robo)

        if estado_ou_pmib == "LOGIN_NECESSARIO":
            msg = "O navegador foi aberto.\n\n1. Faça o LOGIN no site.\n2. Navegue até a tela inicial do PMIB.\n3. Clique abaixo para soltar o robô."
        else:
            msg = f"Ficha {estado_ou_pmib} preenchida!\n\nVerifique na tela e copie as pendências (se houverem) do painel ao lado.\nApós clicar em SALVAR no site, clique no botão abaixo."

        ctk.CTkLabel(top, text=msg, font=("Roboto", 13), wraplength=400, justify="center").pack(pady=30, padx=20, expand=True)

        btn = ctk.CTkButton(top, text="CONTINUAR AUTOMAÇÃO", command=liberar_robo,
                            fg_color=COLORS.get("primary", "#1f538d"), hover_color=COLORS.get("primary_hover", "#14375e"),
                            height=45, font=("Roboto", 14, "bold"))
        btn.pack(pady=(0, 20))


# =============================================================================
# MÓDULO 7: UPLOAD DE FICHAS DUPLICADAS (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloCopiaFichas(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Variáveis de Estado
        self.caminho_status = None
        self.fila_completa = []
        self.fila_selecionada = []
        self.sucessos = []
        self.extrator_ativo = None

        # Layout Principal
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=3)
        self.grid_rowconfigure(2, weight=1)

        # Header
        header = ctk.CTkFrame(self, height=50, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(header, text="Módulo: Cópia de Fichas PMIB", font=("Roboto", 24, "bold"), text_color=COLORS["text_white"]).pack(side="left")

        # Container Principal
        self.content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=20, pady=0)

        # Console de Log
        self.console = ctk.CTkTextbox(self, font=("Consolas", 12))
        self.console.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)

        self._build_ui()

    def log(self, msg):
        self.after(0, lambda: [self.console.insert("end", f"> {msg}\n"), self.console.see("end")])

    def _build_ui(self):
        # --- ETAPA 1: CONFIGURAÇÃO ---
        frm_config = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8)
        frm_config.pack(fill="x", pady=10)

        ctk.CTkLabel(frm_config, text="1. Selecionar Arquivo Base", font=("Roboto", 16, "bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=15, pady=10)

        f_pmib = ctk.CTkFrame(frm_config, fg_color="transparent")
        f_pmib.pack(fill="x", padx=15, pady=10)

        self.btn_status = ctk.CTkButton(f_pmib, text="Selecionar _STATUS_PMIB", command=self.selecionar_excel_pmib,
                                        fg_color="#3A3A3A", hover_color="#454545", width=250)
        self.btn_status.pack(side="left")
        self.lbl_status = ctk.CTkLabel(f_pmib, text="Aguardando seleção...", text_color="gray")
        self.lbl_status.pack(side="left", padx=15)

        # --- ETAPA 2: AÇÕES ---
        frm_action = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8)
        frm_action.pack(fill="x", pady=10)

        ctk.CTkLabel(frm_action, text="2. Execução", font=("Roboto", 16, "bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=15, pady=10)

        f_actions_grid = ctk.CTkFrame(frm_action, fg_color="transparent")
        f_actions_grid.pack(fill="x", padx=15, pady=10)
        f_actions_grid.grid_columnconfigure((0, 1, 2), weight=1, uniform="cols")

        self.btn_resumo = ctk.CTkButton(f_actions_grid, text="1. Revisar / Editar Fichas", command=self.abrir_revisao,
                                        fg_color="#3A3A3A", hover_color="#454545", height=40, state="disabled")
        self.btn_resumo.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.btn_robo = ctk.CTkButton(f_actions_grid, text="2. Iniciar Robô Web", command=self.run_automation_thread,
                                      fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"], height=40, state="disabled")
        self.btn_robo.grid(row=0, column=1, sticky="ew", padx=5)

        self.btn_salvar = ctk.CTkButton(f_actions_grid, text="3. Salvar 'COMPLETO' no Excel", command=self.salvar_excel,
                                        fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"], height=40, state="disabled")
        self.btn_salvar.grid(row=0, column=2, sticky="ew", padx=(5, 0))

        # Progresso
        self.progress = ctk.CTkProgressBar(frm_action, progress_color=COLORS["accent"])
        self.progress.pack(fill="x", padx=15, pady=15)
        self.progress.set(0)

    # =========================================================================
    # LÓGICA DE INTERFACE
    # =========================================================================
    def selecionar_excel_pmib(self):
        path = file_dialogs.ask_open_file("copia_fichas.status_pmib", "excel", filetypes=[("Excel", "*.xlsx;*.xlsm")])
        if not path: return
        self.caminho_status = path

        self.log("Lendo arquivo Excel, aguarde...")
        self.btn_status.configure(state="disabled")

        # Joga para Thread para não travar a UI ao ler Excel grande
        threading.Thread(target=self._worker_leitura_excel).start()

    def _worker_leitura_excel(self):
        try:
            gerenciador = backend.GerenciadorFilaPMIB(self.caminho_status)
            # O marcador confirmado anteriormente
            status, resultado = gerenciador.montar_fila_processamento(marcador_duplicada="PDM.9900.000")

            if status:
                self.fila_completa = resultado
                self.after(0, self._pos_leitura_sucesso)
            else:
                self.log(f"Erro: {resultado}")
                self.after(0, lambda: self.btn_status.configure(state="normal"))
        except Exception as e:
            self.log(f"Falha na leitura: {e}")
            self.after(0, lambda: self.btn_status.configure(state="normal"))

    def _pos_leitura_sucesso(self):
        self.btn_status.configure(state="normal", fg_color=COLORS["primary"])
        self.lbl_status.configure(text=f"Planilha carregada. Encontradas {len(self.fila_completa)} duplicadas.", text_color=COLORS["accent"])
        self.log(f"{len(self.fila_completa)} fichas identificadas como cópia.")

        if self.fila_completa:
            # Abre imediatamente a janela para selecionar quais processar
            JanelaSelecaoDuplicadas(self, self.fila_completa, self._pos_selecao)

    def _pos_selecao(self, selecionados):
        self.fila_selecionada = selecionados
        self.lbl_status.configure(text=f"{len(self.fila_selecionada)} fichas na fila para processar.")
        self.log(f"Fila final configurada com {len(self.fila_selecionada)} fichas.")

        if self.fila_selecionada:
            self.btn_resumo.configure(state="normal")
            self.btn_robo.configure(state="normal")
        else:
            self.btn_resumo.configure(state="disabled")
            self.btn_robo.configure(state="disabled")

    def abrir_revisao(self):
        if self.fila_selecionada:
            JanelaRevisaoEdicao(self, self.fila_selecionada)

    # =========================================================================
    # LÓGICA DO ROBÔ WEB
    # =========================================================================
    def run_automation_thread(self):
        if not self.fila_selecionada: return
        threading.Thread(target=self._bot_worker).start()

    def _mostrar_janela_pausa(self, evento_espera):
        """Pausa o robô para o usuário fazer Login e iniciar."""
        top = ctk.CTkToplevel(self)
        top.title("Ação Manual Necessária")
        top.geometry("450x250")
        top.attributes('-topmost', True)

        def liberar_robo():
            evento_espera.set()
            top.destroy()

        top.protocol("WM_DELETE_WINDOW", liberar_robo)

        msg = "O navegador foi aberto.\n\n1. Faça o LOGIN no site.\n2. Navegue até a tela inicial do PMIB.\n3. Clique abaixo para iniciar a automação em lote."
        ctk.CTkLabel(top, text=msg, font=("Roboto", 13), wraplength=400, justify="center").pack(pady=30, padx=20, expand=True)

        ctk.CTkButton(top, text="CONTINUAR AUTOMAÇÃO", command=liberar_robo,
                      fg_color=COLORS["primary"], height=45, font=("Roboto", 14, "bold")).pack(pady=(0, 20))

    def _bot_worker(self):
        self.btn_robo.configure(state="disabled")
        self.btn_resumo.configure(state="disabled")
        self.btn_status.configure(state="disabled")
        self.sucessos = []

        try:
            self.log("Iniciando navegador...")
            # Instancia as duas classes do backend
            self.extrator_ativo = backend.ExtratorFichaBase()
            driver = self.extrator_ativo.iniciar_driver_silencioso()
            injetor = backend.InjetorFichaAlvo(driver, self.extrator_ativo.wait)

            self.log("Acessando portal PMIB...")
            driver.get("https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList")

            # Pausa para o Login do Usuário
            evento_espera = threading.Event()
            self.after(0, lambda: self._mostrar_janela_pausa(evento_espera))
            evento_espera.wait()

            total = len(self.fila_selecionada)
            for idx, item in enumerate(self.fila_selecionada):
                pmib_orig = item["pmib_original"]
                pmib_alvo = item["pmib_alvo"]
                desc = item["descricao"]

                self.progress.set((idx + 1) / total)
                self.log(f"[{idx+1}/{total}] Processando Ficha:\nAlvo: {pmib_alvo} | Base: {pmib_orig}")

                try:
                    # 1. Extração
                    self.log(f" -> Extraindo dados da ficha original...")
                    dados_memoria = self.extrator_ativo.extrair_dados_ficha(pmib_orig)
                    dados_memoria["pmib_alvo"] = pmib_alvo  # Anexa o alvo ao dicionário

                    # 2. Injeção
                    self.log(f" -> Injetando dados na ficha alvo...")
                    sucesso = injetor.clonar_ficha(dados_memoria)

                    if sucesso:
                        self.log(f" -> ✅ SUCESSO na clonagem.")
                        self.sucessos.append(pmib_alvo)

                except Exception as e:
                    self.log(f" -> ❌ ERRO processando {pmib_alvo}: {e}")

            self.log("Automação Web concluída!")
            self.after(0, lambda: messagebox.showinfo("Concluído", "Processo web finalizado. Verifique o log e salve no Excel."))
            self.after(0, lambda: self.btn_salvar.configure(state="normal"))

        except Exception as e:
            self.log(f"Erro Fatal no Robô: {e}")
        finally:
            self.after(0, lambda: self.btn_robo.configure(state="normal"))
            self.after(0, lambda: self.btn_resumo.configure(state="normal"))
            self.after(0, lambda: self.btn_status.configure(state="normal"))
            if self.extrator_ativo and self.extrator_ativo.driver:
                try: self.extrator_ativo.driver.quit()
                except: pass

    # =========================================================================
    # LÓGICA DE SALVAMENTO (Fase 4)
    # =========================================================================
    def salvar_excel(self):
        if not self.sucessos:
            return messagebox.showwarning("Aviso", "Nenhuma ficha foi clonada com sucesso para atualizar o Excel.")

        self.btn_salvar.configure(state="disabled")
        self.log("Atualizando Excel _STATUS_PMIB...")
        threading.Thread(target=self._worker_salvar).start()

    def _worker_salvar(self):
        atualizador = backend.AtualizadorStatusPMIB(self.caminho_status)
        secoes = {
            "INFO. GERAIS": True,
            "CONDIÇÕES": True,
            "CARACT. TÉCNICAS": True,
            "DOCUMENTOS E IMAGENS": True
        }

        erros = 0
        for pmib in self.sucessos:
            ok = atualizador.atualizar_ficha_concluida(pmib, secoes, callback_log=self.log)
            if not ok: erros += 1

        if erros == 0:
            self.log("✅ Todas as fichas foram atualizadas no Excel.")
            self.after(0, lambda: messagebox.showinfo("Sucesso", "Status atualizado no Excel com sucesso!"))
        else:
            self.log(f"⚠️ Terminou com {erros} erros ao salvar no Excel.")
            self.after(0, lambda: messagebox.showwarning("Aviso", "Algumas atualizações falharam. Verifique o log."))

        self.after(0, lambda: self.btn_salvar.configure(state="normal"))


# =============================================================================
# MÓDULO 8: AUTO SPEC AI (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloAutoSpec(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Variáveis de Estado
        self.queue = []
        self.temp_sheet = None
        self.temp_refs = []
        self.status_pmib_path = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self, height=50, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(header, text="AutoSpec AI (RAG & Geração)", font=("Roboto", 24, "bold"), text_color=COLORS["text_white"]).pack(side="left")

        # Content
        self.content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)

        # Console
        self.console = ctk.CTkTextbox(self, height=120, font=("Consolas", 12))
        self.console.grid(row=2, column=0, sticky="ew", padx=20, pady=10)

        self._build_ui()

    def log(self, txt):
        self.console.insert("end", f"> {txt}\n"); self.console.see("end")

    def _build_ui(self):
        # --- SEÇÃO 1: STATUS PMIB ---
        frm_status = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8)
        frm_status.pack(fill="x", pady=10)
        ctk.CTkLabel(frm_status, text="1. Arquivo de Referência", font=("Roboto", 14, "bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=15, pady=10)

        f_st_act = ctk.CTkFrame(frm_status, fg_color="transparent")
        f_st_act.pack(fill="x", padx=15, pady=(0, 15))

        self.lbl_status = ctk.CTkLabel(f_st_act, text="Nenhum _STATUS_PMIB selecionado", text_color="gray", anchor="w")
        self.lbl_status.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(f_st_act, text="Selecionar _STATUS_PMIB", command=self.sel_status,
                      fg_color="#3A3A3A", hover_color="#454545", font=("Roboto", 12)).pack(side="right")

        # --- SEÇÃO 2: MONTADOR DE FILA ---
        frm_job = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8, border_width=1, border_color=COLORS["primary"])
        frm_job.pack(fill="x", pady=10)
        ctk.CTkLabel(frm_job, text="2. Adicionar Tarefa à Fila", font=("Roboto", 14, "bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=15, pady=10)

        # A) Ficha Alvo
        f_sheet = ctk.CTkFrame(frm_job, fg_color="transparent")
        f_sheet.pack(fill="x", padx=15, pady=5)
        self.lbl_sheet = ctk.CTkLabel(f_sheet, text="Ficha: [Nenhuma]", anchor="w", text_color="gray")
        self.lbl_sheet.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(f_sheet, text="Selecionar Ficha (.xlsx)", width=180, command=self.sel_sheet,
                      fg_color="#3A3A3A", hover_color="#454545", font=("Roboto", 12)).pack(side="right")

        # B) Manuais
        f_refs = ctk.CTkFrame(frm_job, fg_color="transparent")
        f_refs.pack(fill="x", padx=15, pady=5)
        self.lbl_refs = ctk.CTkLabel(f_refs, text="Manuais: 0 arquivos", anchor="w", text_color="gray")
        self.lbl_refs.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(f_refs, text="Adic. Manuais (.pdf)", width=180, command=self.sel_refs,
                      fg_color="#3A3A3A", hover_color="#454545", font=("Roboto", 12)).pack(side="right")

        # Botão Add
        ctk.CTkButton(frm_job, text="⬇ Adicionar à Fila ⬇", command=self.add_queue,
                      fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                      text_color=COLORS["text_white"], font=("Roboto", 13, "bold")).pack(fill="x", padx=20, pady=15)

        # --- SEÇÃO 3: VISUALIZAÇÃO DA FILA ---
        frm_queue = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8)
        frm_queue.pack(fill="x", pady=10)
        ctk.CTkLabel(frm_queue, text="Fila de Processamento", font=("Roboto", 14, "bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=15, pady=10)

        self.queue_frame = ctk.CTkScrollableFrame(frm_queue, height=150, fg_color="#1E1E1E")  # Fundo mais escuro para a lista
        self.queue_frame.pack(fill="x", padx=15, pady=(0, 15))
        self.update_queue_ui()

        # --- SEÇÃO 4: EXECUTAR ---
        self.btn_run = ctk.CTkButton(self.content, text="INICIAR PROCESSAMENTO DA FILA",
                                     height=50, command=self.run_process,
                                     font=("Roboto", 15, "bold"),
                                     fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], text_color="#FFFFFF")  # Texto escuro no verde
        self.btn_run.pack(fill="x", padx=30, pady=20)

    # --- Seletores (Lógica Mantida) ---
    def sel_status(self):
        p = file_dialogs.ask_open_file("autospec.status_pmib", "excel", titulo="Selecione _STATUS_PMIB", filetypes=[("Excel", "*.xlsx")])
        if p:
            self.status_pmib_path = p
            self.lbl_status.configure(text=os.path.basename(p), text_color=COLORS["text_white"])

    def sel_sheet(self):
        p = file_dialogs.ask_open_file("autospec.ficha", "excel", titulo="Selecione a Ficha Técnica", filetypes=[("Excel", "*.xlsx")])
        if p:
            self.temp_sheet = p
            self.lbl_sheet.configure(text=f"Ficha: {os.path.basename(p)}", text_color=COLORS["text_white"])

    def sel_refs(self):
        ps = file_dialogs.ask_open_files("autospec.manuais", "pdf", titulo="Selecione Manuais/PDFs", filetypes=[("Docs", "*.pdf *.txt")])
        if ps:
            self.temp_refs = list(ps)
            self.lbl_refs.configure(text=f"Manuais: {len(ps)} arquivos", text_color=COLORS["text_white"])

    def add_queue(self):
        if not self.temp_sheet:
            messagebox.showwarning("Aviso", "Selecione pelo menos a Ficha Técnica (.xlsx).")
            return

        self.queue.append({'sheet': self.temp_sheet, 'refs': self.temp_refs})

        # Reset Temp
        self.temp_sheet = None
        self.temp_refs = []
        self.lbl_sheet.configure(text="Ficha: [Nenhuma]", text_color="gray")
        self.lbl_refs.configure(text="Manuais: 0 arquivos", text_color="gray")
        self.update_queue_ui()

    def remove_queue(self, idx):
        del self.queue[idx]
        self.update_queue_ui()

    def update_queue_ui(self):
        for w in self.queue_frame.winfo_children(): w.destroy()

        if not self.queue:
            ctk.CTkLabel(self.queue_frame, text="Fila vazia.", text_color="gray").pack(pady=10)
            return

        for i, item in enumerate(self.queue):
            f = ctk.CTkFrame(self.queue_frame, fg_color="transparent")
            f.pack(fill="x", pady=2)
            fname = os.path.basename(item['sheet'])
            n_refs = len(item['refs'])

            ctk.CTkLabel(f, text=f"#{i+1}: {fname} (+{n_refs} manuais)", anchor="w", font=("Roboto", 12)).pack(side="left", padx=5)
            ctk.CTkButton(f, text="X", width=30, command=lambda x=i: self.remove_queue(x),
                          fg_color=COLORS["danger"], hover_color="#B71C1C", height=25).pack(side="right", padx=5)

    # --- Execução ---
    def run_process(self):
        if not self.status_pmib_path: return messagebox.showerror("Erro", "Selecione o arquivo _STATUS_PMIB.")
        if not self.queue: return messagebox.showerror("Erro", "Adicione itens à fila.")

        self.btn_run.configure(state="disabled")
        threading.Thread(target=self._worker).start()

    def _worker(self):
        try:
            core = autospec_backend.AutoSpecCore(
                gemini_key=self.controller.get_key("GEMINI"),
                llama_key=self.controller.get_key("LLAMA"),
                google_search_key=self.controller.get_key("GOOGLE_SEARCH"),
                google_cse_id=self.controller.get_key("GOOGLE_CSE")
            )
            for msg in core.process_queue(self.queue, self.status_pmib_path):
                self.log(msg)

            self.log("Processamento Completo!")
            messagebox.showinfo("Sucesso", "Todas as tarefas da fila foram processadas.")
            self.queue = []
            self.update_queue_ui()  # Nota: idealmente via callback seguro, mas ctk aguenta na maioria dos casos

        except Exception as e:
            self.log(f"ERRO FATAL: {e}")
        finally:
            self.btn_run.configure(state="normal")


# =============================================================================
# MÓDULO 9: LMR (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloLMR(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self, height=50, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(header, text="Automação LMR", font=("Roboto", 24, "bold"), text_color=COLORS["text_white"]).pack(side="left")

        # Content
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)

        # Console
        self.console = ctk.CTkTextbox(self, height=150, font=("Consolas", 12))
        self.console.grid(row=2, column=0, sticky="ew", padx=20, pady=10)

        self._build_ui()

    def log(self, txt):
        self.console.insert("end", f"> {txt}\n"); self.console.see("end")

    def _build_ui(self):
        frm_main = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8)
        frm_main.pack(fill="x", pady=20)

        ctk.CTkLabel(frm_main, text="Preenchimento Automático de LMR (Aplicações)", font=("Roboto", 16, "bold"), text_color=COLORS["accent"]).pack(pady=(20, 10))

        info_text = ("Este módulo lê a aba 'GERAL' de um arquivo Excel e cadastra as aplicações no Portal PMIB.\n"
                     "Será solicitado login no navegador durante o processo.")
        ctk.CTkLabel(frm_main, text=info_text, font=("Roboto", 13), text_color="gray").pack(pady=(0, 20))

        self.btn_run = ctk.CTkButton(frm_main, text="Selecionar Excel e Iniciar",
                                     height=50, width=300,
                                     command=self.iniciar_lmr,
                                     font=("Roboto", 14, "bold"),
                                     fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"], text_color=COLORS["text_white"])
        self.btn_run.pack(pady=10)

        ctk.CTkLabel(frm_main, text="O script pedirá:\n1. Arquivo Excel LMR\n2. Seleção das Fichas (Checkbox)",
                     text_color="gray70", font=("Roboto", 12)).pack(pady=(10, 20))

    # --- Lógica Mantida ---
    def iniciar_lmr(self):
        excel_path = file_dialogs.ask_open_file("lmr.excel", "excel", titulo="Selecione o Excel LMR", filetypes=[("Excel", "*.xlsx")])
        if not excel_path: return
        self.log(f"Lendo arquivo: {os.path.basename(excel_path)}...")
        self.btn_run.configure(state="disabled")
        threading.Thread(target=self._pre_processamento, args=(excel_path,)).start()

    def _pre_processamento(self, excel_path):
        try:
            automator = lmr_backend.LMRAutomation()
            ok, df_completo, pmibs_unicos, msg = automator.carregar_dados_excel(excel_path)

            self.log(msg)
            if not ok:
                messagebox.showerror("Erro", f"Falha ao ler Excel:\n{msg}")
                self.btn_run.configure(state="normal")
                return

            if not pmibs_unicos:
                self.log("Nenhum PMIB encontrado.")
                self.btn_run.configure(state="normal")
                return

            self.after(0, lambda: self._janela_selecao_pmib(pmibs_unicos, df_completo))

        except Exception as e:
            self.log(f"Erro Pré-processamento: {e}")
            self.btn_run.configure(state="normal")

    def _janela_selecao_pmib(self, lista_pmibs, df_completo):
        def on_confirm(selecionados):
            if not selecionados:
                self.log("Seleção cancelada.")
                self.btn_run.configure(state="normal")
                return
            self.log(f"{len(selecionados)} fichas selecionadas. Iniciando robô...")
            threading.Thread(target=self._worker_lmr, args=(selecionados, df_completo)).start()

        top = ctk.CTkToplevel(self)
        top.title("Selecione as Fichas")
        top.geometry("450x600")
        top.transient(self)  # Mantém sobre a janela principal
        top.grab_set()

        ctk.CTkLabel(top, text="Selecione os PMIBs para processar:", font=("Roboto", 14, "bold")).pack(pady=10)

        scroll_frame = ctk.CTkScrollableFrame(top)
        scroll_frame.pack(fill="both", expand=True, padx=10, pady=5)

        vars_check = {}
        for pmib in lista_pmibs:
            var = ctk.BooleanVar(value=False)
            chk = ctk.CTkCheckBox(scroll_frame, text=pmib, variable=var, fg_color=COLORS["primary"])
            chk.pack(anchor="w", pady=2)
            vars_check[pmib] = var

        def confirmar():
            escolhidos = [p for p, v in vars_check.items() if v.get()]
            top.destroy()
            on_confirm(escolhidos)

        def selecionar_todos():
            for v in vars_check.values(): v.set(True)

        btn_frame = ctk.CTkFrame(top, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10)
        ctk.CTkButton(btn_frame, text="Todos", width=80, command=selecionar_todos, fg_color="#3A3A3A", hover_color="#454545").pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="CONFIRMAR", width=150, command=confirmar, fg_color=COLORS["accent"], text_color="#161616", hover_color=COLORS["accent_hover"]).pack(side="right", padx=10)

    def _worker_lmr(self, selecionados, df_completo):
        auto = lmr_backend.LMRAutomation()
        try:
            self.log("Iniciando navegador...")
            auto.iniciar_driver()
            self.log("Carregando portal...")
            auto.abrir_portal()
            messagebox.showinfo("Login Necessário", "Faça login no navegador e clique OK para começar.")

            def cb_log(txt): self.log(txt)
            def cb_ask(tit, msg): return messagebox.askyesno(tit, msg)
            def cb_input(tit, msg): return simpledialog.askstring(tit, msg)

            auto.processar_lista(selecionados, df_completo, callback_log=cb_log, callback_ask=cb_ask, callback_input=cb_input)

            self.log("Automação LMR finalizada.")
            messagebox.showinfo("Sucesso", "Processo concluído.")
        except Exception as e:
            self.log(f"Erro Fatal LMR: {e}")
        finally:
            auto.fechar_driver()
            self.btn_run.configure(state="normal")


# =============================================================================
# MÓDULO 10: APAGAR LMR (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloApagarLMR(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self, height=50, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(header, text="Apagar Aplicações LMR", font=("Roboto", 24, "bold"), text_color=COLORS["danger"]).pack(side="left")

        # Content
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)

        # Console
        self.console = ctk.CTkTextbox(self, height=150, font=("Consolas", 12))
        self.console.grid(row=2, column=0, sticky="ew", padx=20, pady=10)

        self._build_ui()

    def log(self, txt):
        self.console.insert("end", f"> {txt}\n"); self.console.see("end")

    def _build_ui(self):
        frm_main = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8)
        frm_main.pack(fill="x", pady=20)

        ctk.CTkLabel(frm_main, text="ATENÇÃO: AÇÃO DESTRUTIVA", font=("Roboto", 16, "bold"), text_color=COLORS["danger"]).pack(pady=(20, 5))
        ctk.CTkLabel(frm_main, text="Esta ferramenta apaga TODAS as aplicações LMR de uma ficha.\nO processo é irreversível.",
                     font=("Roboto", 13), text_color="gray").pack(pady=(0, 20))

        frm_input = ctk.CTkFrame(frm_main, fg_color="transparent")
        frm_input.pack(pady=10)

        ctk.CTkLabel(frm_input, text="Código PMIB:", font=("Roboto", 14, "bold")).pack(side="left", padx=10)
        self.entry_pmib = ctk.CTkEntry(frm_input, width=250, placeholder_text="Ex: 4500063671.1234")
        self.entry_pmib.pack(side="left", padx=10)

        self.btn_run = ctk.CTkButton(frm_main, text="INICIAR LIMPEZA",
                                     height=50, width=350,
                                     command=self.iniciar_limpeza,
                                     font=("Roboto", 14, "bold"),
                                     fg_color=COLORS["danger"], hover_color="#B71C1C", text_color=COLORS["text_white"])
        self.btn_run.pack(pady=20)

        info_steps = "O robô irá:\n1. Abrir o navegador\n2. Solicitar login manual\n3. Acessar a ficha\n4. Clicar em todas as lixeiras até esvaziar a lista."
        ctk.CTkLabel(frm_main, text=info_steps, text_color="gray70", font=("Roboto", 12)).pack(pady=(0, 20))

    # --- Lógica Mantida ---
    def iniciar_limpeza(self):
        pmib = self.entry_pmib.get().strip()
        if not pmib:
            messagebox.showwarning("Aviso", "Digite o código PMIB.")
            return

        if not messagebox.askyesno("Confirmar", f"Tem certeza que deseja APAGAR todas as aplicações do PMIB {pmib}?"):
            return

        self.log(f"Preparando limpeza para: {pmib}...")
        self.btn_run.configure(state="disabled")
        threading.Thread(target=self._worker, args=(pmib,)).start()

    def _worker(self, pmib):
        auto = apagar_lmr_backend.ApagarLMRAutomation()
        try:
            self.log("Iniciando navegador...")
            auto.iniciar_driver()
            self.log("Carregando portal...")
            auto.abrir_portal()
            messagebox.showinfo("Login Necessário", "Faça login no navegador e clique OK para começar a EXCLUSÃO.")

            def cb_log(txt): self.log(txt)

            self.log("Iniciando varredura...")
            auto.executar_limpeza(pmib, callback_log=cb_log)
            self.log("Processo Finalizado.")
            messagebox.showinfo("Sucesso", "Limpeza concluída.")

        except Exception as e:
            self.log(f"Erro Fatal: {e}")
        finally:
            auto.fechar_driver()
            self.btn_run.configure(state="normal")


# =============================================================================
# MÓDULO 11: PMIB MANAGER (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloPMIBManager(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Variáveis visuais dos caminhos
        self.path_api = ctk.StringVar()
        self.path_root = ctk.StringVar()
        self.path_master = ctk.StringVar()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)  # Inputs (Sem expansão)
        self.grid_rowconfigure(2, weight=0)  # Barra de Progresso (Sem expansão)
        self.grid_rowconfigure(3, weight=1)  # Console (Puxa todo o resto do espaço)

        # Header
        header = ctk.CTkFrame(self, height=50, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(header, text="Gestão de Sobressalentes", font=("Roboto", 24, "bold"), text_color=COLORS["text_white"]).pack(side="left")

        # Content (Bloco 1 - Inputs)
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=20, pady=5)

        # Barra de Progresso Centralizada (Bloco 1.5)
        self.progress_bar = ctk.CTkProgressBar(self, width=600, height=12, progress_color=COLORS["primary"])
        self.progress_bar.grid(row=2, column=0, pady=(5, 5))
        self.progress_bar.set(0)  # Inicia zerada

        # Console (Bloco 2 - Output)
        self.console = ctk.CTkTextbox(self, font=("Consolas", 12))
        self.console.grid(row=3, column=0, sticky="nsew", padx=20, pady=(5, 20))

        self._build_ui()

    def log(self, txt):
        self.console.insert("end", f"> {txt}\n"); self.console.see("end")

    def _build_ui(self):
        frm_main = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8)
        frm_main.pack(fill="x", pady=10)

        ctk.CTkLabel(frm_main, text="Configuração de Gestão de Fichas PMIB", font=("Roboto", 16, "bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=15, pady=(15, 5))

        # Input API (Estilo Arquivo: Botão + Label)
        f_api = ctk.CTkFrame(frm_main, fg_color="transparent")
        f_api.pack(fill="x", padx=15, pady=8)
        self.btn_api = ctk.CTkButton(f_api, text="1. Selecionar Histórico Aconex DocManager (.xlsx)", width=280, command=self._sel_api,
                                     fg_color="#3A3A3A", hover_color="#454545", font=("Roboto", 12))
        self.btn_api.pack(side="left")
        self.lbl_api_status = ctk.CTkLabel(f_api, text="Nenhum arquivo selecionado", text_color="gray")
        self.lbl_api_status.pack(side="left", padx=15)

        # Input Pasta Raiz (Estilo Caminho: Entry + Botão Buscar)
        f_root = ctk.CTkFrame(frm_main, fg_color="transparent")
        f_root.pack(fill="x", padx=15, pady=8)
        ctk.CTkLabel(f_root, text="2. Pasta Raiz (Arquivos _STATUS_PMIB):", width=280, anchor="w").pack(side="left")
        ctk.CTkEntry(f_root, textvariable=self.path_root, width=300).pack(side="left", padx=5)
        ctk.CTkButton(f_root, text="Buscar", width=80, command=lambda: self.path_root.set(file_dialogs.ask_directory("pmib_manager.pasta_raiz", "pasta", titulo="Selecione a Pasta Raiz"))).pack(side="left")

        # Input Planilha Mestra (Estilo Arquivo: Botão + Label)
        f_master = ctk.CTkFrame(frm_main, fg_color="transparent")
        f_master.pack(fill="x", padx=15, pady=8)
        self.btn_master = ctk.CTkButton(f_master, text="3. Selecionar Mapeamento Sobressalentes (.xlsx)", width=280, command=self._sel_master,
                                        fg_color="#3A3A3A", hover_color="#454545", font=("Roboto", 12))
        self.btn_master.pack(side="left")
        self.lbl_master_status = ctk.CTkLabel(f_master, text="Nenhum arquivo selecionado", text_color="gray")
        self.lbl_master_status.pack(side="left", padx=15)

        # O botão volta a ter um padding normal, já que a barra sumiu daqui
        self.btn_run = ctk.CTkButton(frm_main, text="INICIAR PROCESSO DE GESTÃO",
                                     height=50, width=350,
                                     command=self.iniciar_gestao,
                                     font=("Roboto", 14, "bold"),
                                     fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"], text_color=COLORS["text_white"])
        self.btn_run.pack(pady=20)

    def _sel_api(self):
        f = file_dialogs.ask_open_file("pmib_manager.api", "excel", titulo="Selecione a Base de Dados API", filetypes=[("Excel", "*.xlsx *.xls")])
        if f:
            self.path_api.set(f)
            self.lbl_api_status.configure(text=os.path.basename(f), text_color=COLORS["accent"])
            self.btn_api.configure(fg_color=COLORS["primary"])

    def _sel_master(self):
        f = file_dialogs.ask_open_file("pmib_manager.master", "excel", titulo="Selecione a Planilha Mestra", filetypes=[("Excel", "*.xlsx *.xls")])
        if f:
            self.path_master.set(f)
            self.lbl_master_status.configure(text=os.path.basename(f), text_color=COLORS["accent"])
            self.btn_master.configure(fg_color=COLORS["primary"])

    # --- Lógica de Execução Segura ---
    def _safe_log(self, txt):
        """Envia o texto para o console de forma segura através da Thread principal"""
        self.after(0, lambda: self.log(txt))

    def iniciar_gestao(self):
        # 1. Coleta e valida os dados visuais ANTES de travar a tela
        api_path = self.path_api.get()
        root_folder = self.path_root.get()
        master_path = self.path_master.get()

        if not api_path:
            return messagebox.showwarning("Aviso", "Por favor, selecione a Base do Aconex (Passo 1).")
        if not root_folder:
            return messagebox.showwarning("Aviso", "Por favor, selecione a Pasta Raiz (Passo 2).")
        if not master_path:
            return messagebox.showwarning("Aviso", "Por favor, selecione a Planilha de mapeamento (Passo 3).")

        # 2. Desativa o botão para evitar cliques duplicados
        self.btn_run.configure(state="disabled")

        # 3. Dispara o processamento em segundo plano (Thread)
        threading.Thread(target=self._worker, args=(api_path, root_folder, master_path), daemon=True).start()

    def _worker(self, api_path, root_folder, master_path):
        try:
            self._safe_log("Iniciando fluxo de gestão de sobressalentes...")

            # Instancia a inteligência do Backend
            manager = pmib_manager_backend.PMIBManager()

            # Callback de Travamento de Arquivo (Thread-Safe)
            def cb_retry_lock():
                resultado = {}
                evento_espera = threading.Event()

                def mostrar_popup():
                    res = messagebox.askretrycancel(
                        "Planilha Mestra Aberta",
                        "O sistema não conseguiu salvar os dados porque a Planilha de Mapeamento está aberta no Excel.\n\nPor favor, salve suas alterações, feche a planilha e clique em 'Repetir'.\nSe quiser abortar o processo, clique em 'Cancelar'."
                    )
                    resultado['retry'] = res
                    evento_espera.set()

                self.after(0, mostrar_popup)
                evento_espera.wait()
                return resultado.get('retry', False)

            # Callback Interativo e Seguro (Thread-Safe)
            def cb_confirm(df_novos):
                resultado = {}
                evento_espera = threading.Event()  # Trava a thread do backend até você clicar

                def desenhar_popup():
                    win = ctk.CTkToplevel(self)
                    win.title("Novas Listas Encontradas")
                    win.geometry("750x550")
                    win.transient(self)
                    win.grab_set()

                    ctk.CTkLabel(win, text="Novas Listas de Sobressalentes Encontradas na base de dados:", font=("Roboto", 16, "bold"), text_color=COLORS["accent"]).pack(pady=(15, 5))
                    ctk.CTkLabel(win, text="Selecione abaixo quais você deseja adicionar à Planilha de Mapeamento.", font=("Roboto", 13), text_color="gray").pack(pady=(0, 10))

                    # Área com Scroll para listar os documentos
                    scroll = ctk.CTkScrollableFrame(win, fg_color="#2B2B2B")
                    scroll.pack(fill="both", expand=True, padx=20, pady=5)

                    check_vars = {}

                    # Cria um Checkbox para cada linha encontrada
                    for idx, row in df_novos.iterrows():
                        var = tk.BooleanVar(value=True)  # Começam todos marcados por padrão
                        texto_doc = f"[{row['No. do Documento']}]  -  {row['Título']}"
                        chk = ctk.CTkCheckBox(scroll, text=texto_doc, variable=var, font=("Roboto", 12))
                        chk.pack(anchor="w", padx=10, pady=6)
                        check_vars[idx] = (var, chk)

                    # Funções dos Botões Auxiliares
                    def selecionar_todos():
                        for var, _ in check_vars.values(): var.set(True)

                    def limpar_selecao():
                        for var, _ in check_vars.values(): var.set(False)

                    # Funções de Conclusão
                    def confirmar():
                        # Filtra o DataFrame original mantendo apenas os índices que ficaram com True
                        idxs_marcados = [i for i, (var, _) in check_vars.items() if var.get()]
                        resultado['df_final'] = df_novos.loc[idxs_marcados]
                        evento_espera.set()  # Libera a Thread do backend
                        win.destroy()

                    def ignorar_todas():
                        resultado['df_final'] = pd.DataFrame()  # Retorna Vazio
                        evento_espera.set()
                        win.destroy()

                    # Tratamento caso o usuário clique no "X" da janela
                    win.protocol("WM_DELETE_WINDOW", ignorar_todas)

                    # Frame para os botões inferiores
                    f_botoes = ctk.CTkFrame(win, fg_color="transparent")
                    f_botoes.pack(fill="x", padx=20, pady=15)

                    # Botões de Massa (Esquerda)
                    ctk.CTkButton(f_botoes, text="Marcar Todas", width=120, fg_color="#3A3A3A", hover_color="#454545", command=selecionar_todos).pack(side="left", padx=5)
                    ctk.CTkButton(f_botoes, text="Desmarcar Todas", width=120, fg_color="#3A3A3A", hover_color="#454545", command=limpar_selecao).pack(side="left", padx=5)

                    # Botões de Ação (Direita)
                    ctk.CTkButton(f_botoes, text="Confirmar Seleção", width=150, fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"], command=confirmar).pack(side="right", padx=5)
                    ctk.CTkButton(f_botoes, text="Ignorar (Não Adicionar)", width=150, fg_color="gray", hover_color="#555555", command=ignorar_todas).pack(side="right", padx=5)

                # Dispara o desenho do popup na Thread Principal (Interface)
                self.after(0, desenhar_popup)

                # O Backend fica "congelado" aqui esperando você clicar em Confirmar ou Ignorar
                evento_espera.wait()

                return resultado.get('df_final', pd.DataFrame())

            # Variável de controle para saber se o usuário cancelou
            sucesso_total = True

            # Lemos a tupla que o backend manda passando ambos os callbacks
            for resposta in manager.executar_fluxo(api_path, root_folder, master_path, callback_confirm=cb_confirm, callback_retry_lock=cb_retry_lock):
                if isinstance(resposta, tuple):
                    msg, progresso = resposta
                    self._safe_log(msg)
                    if progresso is not None:
                        self.after(0, lambda p=progresso: self.progress_bar.set(p))
                else:
                    self._safe_log(resposta)
                    # Se o backend jogar um erro (ex: abortado), marcamos como falha
                    if "[ERRO]" in resposta:
                        sucesso_total = False

            # Validação Final Segura
            if sucesso_total:
                self.after(0, lambda: self.progress_bar.set(1.0))
                self.after(0, lambda: messagebox.showinfo("Sucesso", "Processo de Gestão PMIB finalizado com sucesso!"))
            else:
                self.after(0, lambda: messagebox.showwarning("Aviso", "O processo foi interrompido ou finalizado com erros. Nenhuma alteração foi salva."))

        except Exception as e:
            self._safe_log(f"[ERRO FATAL]: {e}")
            self.after(0, lambda: messagebox.showerror("Erro", f"Ocorreu um erro fatal durante a execução:\n{e}"))
        finally:
            # Reativa o botão ao final de tudo (seja erro ou sucesso)
            self.after(0, lambda: self.btn_run.configure(state="normal"))


# =============================================================================
# MÓDULO 12: BUSCA DE SOBRESSALENTES (SEARCH PMIB)
# =============================================================================
class ModuloBuscaPMIB(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Variáveis de Estado da UI
        self.path_raiz = ctk.StringVar()
        self.tipo_busca = ctk.StringVar(value="direcionada")
        self.coluna_selecionada = ctk.StringVar(value="DESCRIÇÃO")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)  # Inputs
        self.grid_rowconfigure(2, weight=1)  # Console (Expande no espaço vazio)

        # Header
        header = ctk.CTkFrame(self, height=50, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(header, text="Search PMIB (Buscador de Sobressalentes)", font=("Roboto", 24, "bold"), text_color=COLORS["text_white"]).pack(side="left")

        # Configurações de Layout
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=20, pady=5)

        self._build_ui()

    def log(self, txt):
        """Atualiza o console de logs de forma Thread-Safe"""
        self.after(0, lambda: [self.console.insert("end", f"> {txt}\n"), self.console.see("end")])

    def _build_ui(self):
        # --- PAINEL DE CONFIGURAÇÃO E INPUTS ---
        frm_config = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8)
        frm_config.pack(fill="x", pady=5)

        ctk.CTkLabel(frm_config, text="1. Parâmetros de Busca", font=("Roboto", 14, "bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=15, pady=(10, 5))

        # 1. Seleção da Pasta Raiz
        f_root = ctk.CTkFrame(frm_config, fg_color="transparent")
        f_root.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(f_root, text="Pasta Raiz da Busca:", width=150, anchor="w").pack(side="left")
        ctk.CTkEntry(f_root, textvariable=self.path_raiz, width=400).pack(side="left", padx=5)
        ctk.CTkButton(f_root, text="Buscar Pasta", width=100, command=self._selecionar_pasta, fg_color="#3A3A3A", hover_color="#454545").pack(side="left")

        # 2. Modo de Busca e Coluna
        f_modo = ctk.CTkFrame(frm_config, fg_color="transparent")
        f_modo.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(f_modo, text="Modo de Busca:", width=150, anchor="w").pack(side="left")

        self.rb_direc = ctk.CTkRadioButton(f_modo, text="Direcionada (Rápida)", variable=self.tipo_busca, value="direcionada", command=self._toggle_modo_busca)
        self.rb_direc.pack(side="left", padx=(0, 15))

        self.rb_geral = ctk.CTkRadioButton(f_modo, text="Generalista (Lenta)", variable=self.tipo_busca, value="generalista", command=self._toggle_modo_busca)
        self.rb_geral.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(f_modo, text="Coluna Alvo:", anchor="w").pack(side="left", padx=(10, 5))
        colunas_opcoes = ["DESCRIÇÃO", "CÓDIGO DO MATERIAL", "CÓDIGO CMI", "MARCA/MODELO", "CÓDIGO PMIB"]
        self.opt_coluna = ctk.CTkOptionMenu(f_modo, values=colunas_opcoes, variable=self.coluna_selecionada, fg_color="#3A3A3A", button_color="#454545")
        self.opt_coluna.pack(side="left")

        # 3. Termo de Busca
        f_termo = ctk.CTkFrame(frm_config, fg_color="transparent")
        f_termo.pack(fill="x", padx=15, pady=(5, 15))
        ctk.CTkLabel(f_termo, text="Termo Procurado:", width=150, anchor="w").pack(side="left")
        self.entry_termo = ctk.CTkEntry(f_termo, width=400, placeholder_text="Digite o que deseja encontrar...")
        self.entry_termo.pack(side="left", padx=5)

        # Botão Pesquisar (com destaque)
        self.btn_search = ctk.CTkButton(f_termo, text="🔍 PESQUISAR", command=self.iniciar_busca, width=150,
                                        fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"], font=("Roboto", 13, "bold"))
        self.btn_search.pack(side="left", padx=10)

        # --- CONSOLE DE LOGS ---
        # O console agora sobe para a row 2 e vai ocupar o resto da tela lindamente
        self.console = ctk.CTkTextbox(self, font=("Consolas", 12))
        self.console.grid(row=2, column=0, sticky="nsew", padx=20, pady=(15, 20))

    def _toggle_modo_busca(self):
        """Ativa ou desativa a seleção de coluna baseada no modo de busca"""
        if self.tipo_busca.get() == "generalista":
            self.opt_coluna.configure(state="disabled")
        else:
            self.opt_coluna.configure(state="normal")

    def _selecionar_pasta(self):
        p = file_dialogs.ask_directory("search.pasta_raiz", "pasta", titulo="Selecione a Pasta Raiz de Busca")
        if p:
            self.path_raiz.set(p)

    def iniciar_busca(self):
        pasta = self.path_raiz.get()
        termo = self.entry_termo.get().strip()
        modo = self.tipo_busca.get()
        coluna = self.coluna_selecionada.get()

        if not pasta:
            return messagebox.showwarning("Atenção", "Selecione a pasta raiz antes de pesquisar.")
        if not termo:
            return messagebox.showwarning("Atenção", "Digite o termo que deseja pesquisar.")

        self.btn_search.configure(state="disabled")
        self.console.delete("0.0", "end")

        # Roda o backend em outra Thread
        threading.Thread(target=self._worker_busca, args=(pasta, modo, termo, coluna), daemon=True).start()

    def _worker_busca(self, pasta, modo, termo, coluna):
        try:
            searcher = search_pmib_backend.PMIBSearcher()
            resultados = searcher.executar_busca(
                pasta_raiz=pasta,
                tipo_busca=modo,
                termo_busca=termo,
                coluna_especifica=coluna,
                callback_log=self.log
            )

            # Abre o pop-up modal na Thread Principal
            self.after(0, self._mostrar_janela_resultados, resultados)
        except Exception as e:
            self.log(f"Erro Crítico: {e}")
        finally:
            self.after(0, lambda: self.btn_search.configure(state="normal"))

    def _mostrar_janela_resultados(self, resultados):
        """Cria o pop-up com cards iterativos para visualização completa do caminho"""
        if not resultados:
            messagebox.showinfo("Resultados", "Nenhum material encontrado com esses parâmetros.")
            return

        # Janela Toplevel
        win = ctk.CTkToplevel(self)
        win.title(f"Resultados da Busca: {len(resultados)} encontrados")
        win.geometry("900x650")
        win.resizable(True, True)  # Garante que a janela aceita redimensionamento
        # win.transient(self)  <-- REMOVIDO para exibir botões de Maximizar/Minimizar no Windows
        win.grab_set()  # Mantém o foco na janela sem travar a interface do Windows

        # Cabeçalhos
        ctk.CTkLabel(win, text="Resultados Encontrados", font=("Roboto", 18, "bold"), text_color=COLORS.get("accent", "#00C975")).pack(pady=(15, 5))
        # ctk.CTkLabel(win, text="O caminho completo está visível para facilitar a identificação dos sistemas.", font=("Roboto", 12), text_color="gray").pack(pady=(0, 10))

        # Área com Scroll (Substituindo a antiga Treeview)
        scroll = ctk.CTkScrollableFrame(win, fg_color="#2B2B2B")
        scroll.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        # Funções internas para os botões dos cards
        def abrir_arquivo(caminho):
            if os.path.exists(caminho):
                self.log(f"Abrindo arquivo: {os.path.basename(caminho)}")
                try: os.startfile(caminho)
                except AttributeError: subprocess.call(['open', caminho])
            else: messagebox.showerror("Erro", "Arquivo não encontrado.")

        def abrir_pasta(pasta):
            if os.path.exists(pasta):
                self.log(f"Abrindo pasta: {pasta}")
                try: os.startfile(pasta)
                except AttributeError: subprocess.call(['open', pasta])
            else: messagebox.showerror("Erro", "Pasta não encontrada.")

        # Criar um 'Card' para cada resultado encontrado
        for r in resultados:
            cod_itaipu = r.get('codigo_itaipu', 'N/A')
            coluna = r.get('coluna_match', 'N/A')
            amostra = r.get('amostra', '')
            caminho_arq = r.get('caminho_arquivo', '')
            caminho_pasta = r.get('caminho_pasta', '')

            # Frame base do Card
            card = ctk.CTkFrame(scroll, fg_color="#1E1E1E", corner_radius=8, border_width=1, border_color="#3A3A3A")
            card.pack(fill="x", padx=10, pady=8)

            # Linha 1: Título (Código Itaipu) e em qual Coluna achou
            f_top = ctk.CTkFrame(card, fg_color="transparent")
            f_top.pack(fill="x", padx=10, pady=(10, 5))

            # PMIB em um Entry invisível (Largura aumentada para 450px para não cortar códigos longos)
            entry_pmib = ctk.CTkEntry(f_top, font=("Roboto", 14, "bold"), text_color="#FFFFFF", fg_color="transparent", border_width=0, width=450)
            entry_pmib.insert(0, f"PMIB: {cod_itaipu}")
            entry_pmib.configure(state="readonly")
            entry_pmib.pack(side="left")

            ctk.CTkLabel(f_top, text=f"| Match na coluna: {coluna}", font=("Roboto", 12), text_color="gray").pack(side="left", padx=5)

            # Lógica para calcular altura dinâmica do Textbox baseada no tamanho do texto
            texto_caminho = f"📂 Caminho:\n{caminho_arq}"
            # Conta quebras de linha reais (\n) + quebras virtuais (a cada ~100 caracteres)
            linhas_estimadas_cam = texto_caminho.count('\n') + sum([len(linha) // 100 for linha in texto_caminho.split('\n')]) + 1
            altura_dinamica_cam = max(35, linhas_estimadas_cam * 18)  # 18px por linha (mínimo de 35px)

            # Linha 2: Caminho Completo (Textbox com altura dinâmica)
            txt_caminho = ctk.CTkTextbox(card, font=("Consolas", 11), text_color="#A0A0A0", fg_color="transparent", border_width=0, height=altura_dinamica_cam, wrap="word")
            txt_caminho.insert("0.0", texto_caminho)
            txt_caminho.configure(state="disabled")  # Bloqueia digitação, mas permite selecionar e copiar
            txt_caminho.pack(fill="x", padx=10, pady=2)

            # Linha 3: Amostra (Textbox com altura dinâmica)
            if amostra:
                texto_amostra = f"🔎 Amostra: {amostra}"
                linhas_estimadas_amo = texto_amostra.count('\n') + sum([len(linha) // 100 for linha in texto_amostra.split('\n')]) + 1
                altura_dinamica_amo = max(35, linhas_estimadas_amo * 18)

                txt_amostra = ctk.CTkTextbox(card, font=("Roboto", 12), text_color="#E0E0E0", fg_color="transparent", border_width=0, height=altura_dinamica_amo, wrap="word")
                txt_amostra.insert("0.0", texto_amostra)
                txt_amostra.configure(state="disabled")
                txt_amostra.pack(fill="x", padx=10, pady=(2, 5))

            # Linha 4: Botões de Ação explícitos
            f_btns = ctk.CTkFrame(card, fg_color="transparent")
            f_btns.pack(fill="x", padx=15, pady=(0, 10))

            # Usando "lambda c=caminho_arq" para forçar o escopo do loop na hora do clique
            btn_arq = ctk.CTkButton(f_btns, text="📄 Abrir Arquivo", width=120, height=28, fg_color="#3A3A3A", hover_color="#454545",
                                    command=lambda c=caminho_arq: abrir_arquivo(c))
            btn_arq.pack(side="left", padx=(0, 10))

            btn_pasta = ctk.CTkButton(f_btns, text="📁 Abrir Pasta", width=120, height=28, fg_color="#3A3A3A", hover_color="#454545",
                                      command=lambda p=caminho_pasta: abrir_pasta(p))
            btn_pasta.pack(side="left")

        # Botão Fechar no rodapé da janela Modal
        ctk.CTkButton(win, text="Fechar", command=win.destroy, fg_color="#3A3A3A", hover_color="#454545", width=150).pack(pady=(0, 20))


# =============================================================================
# NOVA CLASSE: HOME SCREEN (DASHBOARD ESTILO BASELINE)
# =============================================================================
class HomeView(ctk.CTkScrollableFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Ajuste de layout para expandir
        self.grid_columnconfigure(0, weight=1)

        # --- CABEÇALHO ---
        self.lbl_titulo = ctk.CTkLabel(self, text="SIG-FT", font=ctk.CTkFont(size=32, weight="bold"))
        self.lbl_titulo.grid(row=0, column=0, pady=(20, 5), sticky="w", padx=20)

        self.lbl_subtitulo = ctk.CTkLabel(self, text="Sistema Integrado de Gestão de Fichas Técnicas - GE Vernova",
                                          font=ctk.CTkFont(size=16), text_color="gray70")
        self.lbl_subtitulo.grid(row=1, column=0, pady=(0, 20), sticky="w", padx=20)

        # Descrição Geral
        resumo = ("Bem-vindo ao SIG-FT. Utilize o menu lateral para navegar entre os módulos. "
                  "Abaixo você encontra um resumo do fluxo de trabalho e das funcionalidades disponíveis.")
        self.criar_texto_simples(resumo, row=2)

        # --- ÁREA DE CONFIGURAÇÃO DE APIs (NOVA) ---
        self.criar_area_config_api(row=3)

        # --- SEÇÕES (CARDS) ---

        # 1. Criação e PDM
        self.criar_card_instrucao(
            row=4,
            titulo="1 & 2. Criação e Estruturação",
            descricao="Etapas iniciais para geração da ficha técnica e processamento de PDMs em massa.",
            inputs="- Excel _STATUS_PMIB\n- Lista de PDMs",
            outputs="- Fichas criadas\n- Planilhas formatadas"
        )

        # 2. Análise e Qualidade
        self.criar_card_instrucao(
            row=5,
            titulo="3. Análise de Qualidade (IA)",
            descricao="Módulo 'Analyzer': Verifica a consistência dos dados preenchidos nas fichas antes do upload.",
            inputs="- Planilhas PMIB (.xlsx)",
            outputs="- Relatório de Erros\n- Fichas marcadas para correção"
        )

        # 3. Dados Técnicos (Upload e Tradução)
        desc_upload = ("Conjunto de ferramentas para automação no Portal PMIB:\n"
                       "• Upload Condições: Preenche abas de transporte, armazenamento, etc.\n"
                       "• Upload Caract. Técnicas: Preenche as especificações técnicas.\n"
                       "• Tradutor: Traduz PT <-> ES automaticamente.")
        self.criar_card_instrucao(
            row=6,
            titulo="4. Dados Técnicos e Upload",
            descricao=desc_upload,
            inputs="- Planilhas PMIB\n- Credenciais Portal",
            outputs="- Preenchimento automático no site"
        )

        # 4. AutoSpec AI
        self.criar_card_instrucao(
            row=7,
            titulo="5. AutoSpec AI (RAG)",
            descricao="Inteligência Artificial avançada que lê manuais em PDF e busca na web para preencher fichas técnicas vazias automaticamente.",
            inputs="- Ficha Técnica vazia\n- PDFs dos Manuais (Opcional)",
            outputs="- Ficha Técnica preenchida com sugestões"
        )

        # 5. Gestão LMR
        self.criar_card_instrucao(
            row=8,
            titulo="6. Gestão LMR (Aplicações)",
            descricao="Automação para inserir ou apagar listas de materiais de reposição (Aplicações) no portal.",
            inputs="- Planilha de Aplicações LMR",
            outputs="- Cadastro ou Remoção no Portal"
        )

        # 6. Gerenciamento Geral
        self.criar_card_instrucao(
            row=9,
            titulo="7. PMIB Manager",
            descricao="Gestão macro do processo: Renomeia arquivos, atualiza planilha mestra e calcula KPIs de avanço.",
            inputs="- Base de Dados API\n- Pasta Raiz de Arquivos",
            outputs="- Relatórios de Avanço\n- Organização de Pastas"
        )

        # Espaço final
        ctk.CTkLabel(self, text="").grid(row=10, column=0, pady=20)

    def criar_area_config_api(self, row):
        """Cria o painel de configuração de chaves API."""
        frame = ctk.CTkFrame(self, fg_color=("gray90", "gray16"), corner_radius=10)
        frame.grid(row=row, column=0, sticky="ew", padx=20, pady=10)

        ctk.CTkLabel(frame, text="🔑 Configuração de Chaves API (Global)", font=("Arial", 16, "bold")).pack(pady=10, padx=10, anchor="w")

        # Campos de Chave
        # [SEGURANÇA] Os valores default hardcoded foram removidos.
        # As chaves devem vir do .env ou do api_config.json (ambos fora do versionamento).
        self.entries = {}
        keys_info = [
            ("GEMINI", "Gemini API Key:", ""),
            ("GOOGLE_SEARCH", "Google Search API:", ""),
            ("GOOGLE_CSE", "Google CSE ID:", ""),
            ("LLAMA", "LlamaCloud API:", ""),
            # [CP 3.2] Gateway OpenRouter (padrão) + endpoint OpenAI-
            # compatível genérico da futura IA interna da empresa — ver
            # docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.2.
            ("OPENROUTER", "OpenRouter API Key:", ""),
            ("EMPRESA_LLM_BASE_URL", "IA Empresa (Base URL):", ""),
            ("EMPRESA_LLM_API_KEY", "IA Empresa (API Key):", "")
        ]

        for key_id, label_text, default_val in keys_info:
            f = ctk.CTkFrame(frame, fg_color="transparent")
            f.pack(fill="x", padx=10, pady=2)
            ctk.CTkLabel(f, text=label_text, width=140, anchor="w").pack(side="left")

            entry = ctk.CTkEntry(f, show="*")  # Mascarado por padrão
            entry.pack(side="left", fill="x", expand=True, padx=5)

            # Carrega valor atual do controller ou default
            current_val = self.controller.get_key(key_id)
            if not current_val: current_val = default_val
            entry.insert(0, current_val)

            self.entries[key_id] = entry

        btn_save = ctk.CTkButton(frame, text="Salvar Chaves", command=self.salvar_chaves_api, fg_color="green")
        btn_save.pack(pady=10)

    def salvar_chaves_api(self):
        new_keys = {k: e.get() for k, e in self.entries.items()}
        self.controller.save_keys(new_keys)
        messagebox.showinfo("Sucesso", "Chaves API salvas com sucesso!\nTodos os módulos usarão as novas chaves.")

    def criar_texto_simples(self, texto, row):
        label = ctk.CTkLabel(self, text=texto, font=("Arial", 14), justify="left", wraplength=800)
        label.grid(row=row, column=0, sticky="w", padx=20, pady=10)

    def criar_card_instrucao(self, row, titulo, descricao, inputs, outputs):
        # Card com cor levemente mais clara que o fundo (#2B2B2B se o fundo for #212121)
        card = ctk.CTkFrame(self, fg_color="#2B2B2B", corner_radius=8, border_width=1, border_color="#333333")
        card.grid(row=row, column=0, sticky="ew", padx=20, pady=8)
        card.grid_columnconfigure(0, weight=1)

        # Título com a cor Primária (Teal)
        lbl_tit = ctk.CTkLabel(card, text=titulo, font=ctk.CTkFont(family="Roboto", size=18, weight="bold"), text_color=COLORS["accent"])
        lbl_tit.grid(row=0, column=0, sticky="w", padx=20, pady=(15, 5))

        lbl_desc = ctk.CTkLabel(card, text=descricao, font=("Roboto", 13), text_color="#CCCCCC", justify="left", wraplength=800)
        lbl_desc.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 15))

        # Linha divisória sutil
        linha = ctk.CTkFrame(card, height=1, fg_color="#404040")
        linha.grid(row=2, column=0, sticky="ew", padx=10, pady=0)

        io_frame = ctk.CTkFrame(card, fg_color="transparent")
        io_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=15)
        io_frame.grid_columnconfigure((0, 1), weight=1)

        # Ícones visuais nos textos
        ctk.CTkLabel(io_frame, text="📥 ENTRADAS", font=("Roboto", 11, "bold"), text_color="gray60").grid(row=0, column=0, sticky="w")
        lbl_in = ctk.CTkLabel(io_frame, text=inputs, font=("Roboto", 12), text_color="gray80", justify="left", anchor="w")
        lbl_in.grid(row=1, column=0, sticky="nw", pady=(5, 0))

        ctk.CTkLabel(io_frame, text="📤 SAÍDAS", font=("Roboto", 11, "bold"), text_color="gray60").grid(row=0, column=1, sticky="w")
        lbl_out = ctk.CTkLabel(io_frame, text=outputs, font=("Roboto", 12), text_color="gray80", justify="left", anchor="w")
        lbl_out.grid(row=1, column=1, sticky="nw", pady=(5, 0))


# =============================================================================
# TELA DE CARREGAMENTO (SPLASH SCREEN)
# =============================================================================
class SplashScreen(ctk.CTk):
    def __init__(self):
        super().__init__()
        # Configurações da Janela
        self.title("Carregando...")
        width, height = 500, 350

        # Centralizar
        ws = self.winfo_screenwidth()
        hs = self.winfo_screenheight()
        x = (ws/2) - (width/2)
        y = (hs/2) - (height/2)
        self.geometry(f'{width}x{height}+{int(x)}+{int(y)}')

        self.overrideredirect(True)  # Remove a barra de título
        self.configure(fg_color=COLORS["background"])

        # Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure((0, 1, 2, 3), weight=1)

        # 1. Logo (Com caminho absoluto robusto)
        # Garante que acha a pasta assets onde quer que o script esteja rodando
        base_path = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(base_path, "assets", "logo.png")

        self.logo_img = None  # Mantém referência para não sumir
        if os.path.exists(image_path):
            try:
                pil_img = Image.open(image_path)
                # Redimensiona mantendo proporção
                w_percent = (300 / float(pil_img.size[0]))
                h_size = int((float(pil_img.size[1]) * float(w_percent)))

                self.logo_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(300, h_size))

                lbl_logo = ctk.CTkLabel(self, text="", image=self.logo_img)
                lbl_logo.pack(pady=(50, 10))
            except Exception as e:
                print(f"Erro ao carregar imagem da Splash: {e}")
                ctk.CTkLabel(self, text="GE Vernova", font=("Roboto", 30, "bold"), text_color="white").pack(pady=(50, 10))
        else:
            print(f"Imagem não encontrada em: {image_path}")
            ctk.CTkLabel(self, text="GE Vernova", font=("Roboto", 30, "bold"), text_color="white").pack(pady=(50, 10))

        # 2. Título
        ctk.CTkLabel(self, text="SIG-FT System", font=("Roboto", 16), text_color="gray").pack(pady=(0, 30))

        # 3. Status
        self.status_label = ctk.CTkLabel(self, text="Iniciando...", font=("Roboto", 12), text_color=COLORS["accent"])
        self.status_label.pack(pady=(0, 5))

        # 4. Barra
        self.progress = ctk.CTkProgressBar(self, width=400, height=12, corner_radius=5,
                                           progress_color=COLORS["accent"], fg_color="#333333")
        self.progress.pack(pady=(0, 20))
        self.progress.set(0)

        # Thread de carregamento
        threading.Thread(target=self.carregar_modulos).start()

    def carregar_modulos(self):
        """Importa os módulos pesados um por um e atualiza a barra."""

        # Lista de módulos para importar
        # Formato: (Nome do Arquivo, Variável Global, Classes Específicas, NOME PARA EXIBIÇÃO)
        modulos_para_carregar = [
            ("cria_fichas_no_pmib_v1_backend", "mixed_classes", ["DataManager", "GeminiCategorizer", "AutomacaoPMIB"], "Gerador de Fichas"),
            ("pdm_backend", "pdm_backend", None, "Processamento PDM"),
            ("analyzer_backend", "analyzer_backend", None, "Analisador IA"),
            ("translator_backend", "translator_backend", None, "Tradutor Técnico"),
            ("upload_conditions_backend", "upload_conditions_backend", None, "Upload de Condições"),
            ("upload_tech_specs_backend", "upload_tech_specs_backend", None, "Upload de Specs"),
            ("autospec_backend", "autospec_backend", None, "AutoSpec RAG"),
            ("lmr_backend", "lmr_backend", None, "Automação LMR"),
            ("apagar_lmr_backend", "apagar_lmr_backend", None, "Ferramenta de Limpeza"),
            ("pmib_manager_backend", "pmib_manager_backend", None, "Gerenciador PMIB"),
            ("search_pmib_backend", "search_pmib_backend", None, "Search PMIB")
        ]

        total = len(modulos_para_carregar)

        # Referência às variáveis globais do script principal
        global DataManager, GeminiCategorizer, AutomacaoPMIB
        global pdm_backend, analyzer_backend, translator_backend, upload_conditions_backend
        global upload_tech_specs_backend, autospec_backend, lmr_backend, apagar_lmr_backend, pmib_manager_backend, search_pmib_backend

        start_time = time.time()

        # [ALTERAÇÃO]: Desempacotamos agora 4 variáveis: display_name foi adicionado
        for i, (module_name, target_var, classes, display_name) in enumerate(modulos_para_carregar):
            try:
                # [ALTERAÇÃO]: Usamos display_name na interface
                self.after(0, lambda d=display_name: self.status_label.configure(text=f"Carregando: {d}..."))

                # Simula delay mínimo para visualização (opcional, deixa a transição mais suave)
                time.sleep(0.1)

                # Importação Dinâmica (Usa o module_name real)
                mod = importlib.import_module(module_name)

                # Atribuição às globais
                if target_var == "mixed_classes":
                    DataManager = getattr(mod, "DataManager")
                    GeminiCategorizer = getattr(mod, "GeminiCategorizer")
                    AutomacaoPMIB = getattr(mod, "AutomacaoPMIB")
                else:
                    globals()[target_var] = mod

                # Atualiza Barra
                progresso = (i + 1) / total
                self.after(0, lambda p=progresso: self.progress.set(p))

            except Exception as e:
                print(f"Erro ao carregar {module_name}: {e}")
                # Mostra erro usando o nome amigável
                self.after(0, lambda d=display_name: self.status_label.configure(text=f"Erro em {d}", text_color=COLORS["danger"]))
                time.sleep(1)  # Pausa para ler o erro

        # Finalização
        elapsed = time.time() - start_time
        self.after(0, lambda: self.status_label.configure(text=f"Concluído em {elapsed:.1f}s"))
        self.after(0, lambda: self.progress.set(1.0))

        # Aguarda um momento breve e inicia o App Principal
        time.sleep(0.8)
        self.after(0, self.iniciar_app_principal)

    def iniciar_app_principal(self):
        self.withdraw()  # Esconde a Splash em vez de destruir imediatamente (evita erros do Tcl)
        self.destroy()   # Destrói
        app = SIG_FT_App()
        app.mainloop()


def resource_path(relative_path):
    """ Obtém o caminho absoluto, funcionando tanto no VS Code quanto no .exe """
    try:
        # PyInstaller cria uma pasta temporária (modo executável)
        base_path = sys._MEIPASS
    except Exception:
        # Modo desenvolvimento: pega o diretório onde o arquivo .py ESTÁ SALVO
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


env_path = resource_path('.env')
load_dotenv(env_path)


# =============================================================================
# APP PRINCIPAL (Gerenciador com Layout Novo, Estilizado e com IMAGENS)
# =============================================================================
class SIG_FT_App(ctk.CTk):
    def __init__(self):
        super().__init__()
        # Configuração da Janela
        self.title("SIG-FT - GE Vernova")
        self.geometry("1280x850")

        # --- CARREGAMENTO DE IMAGENS (Ícone e Logo) ---
        # Usa caminho absoluto para garantir que funciona independente de onde o script é chamado
        base_path = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(base_path, "assets", "logo.png")

        # 1. Definir Ícone da Janela (Suporta PNG)
        try:
            if os.path.exists(image_path):
                # AGORA VAI FUNCIONAR: 'tk' foi importado lá em cima
                icon_image = tk.PhotoImage(file=image_path)
                self.wm_iconphoto(False, icon_image)
            else:
                print(f"AVISO: Arquivo de ícone não encontrado em: {image_path}")
        except Exception as e:
            print(f"Aviso: Não foi possível carregar o ícone da janela. Detalhe: {e}")

        # 2. Carregar Imagem para o Menu (Sidebar)
        self.logo_image = None
        try:
            if os.path.exists(image_path):
                self.logo_image = ctk.CTkImage(
                    light_image=Image.open(image_path),
                    dark_image=Image.open(image_path),
                    size=(180, 60)
                )
        except Exception as e:
            print(f"Aviso: Não foi possível carregar a logo do menu. Detalhe: {e}")

        # --- GESTÃO DE CHAVES API ---
        self.api_keys = {}
        self.load_keys()

        # Layout Principal (2 Colunas: Sidebar fixa, Conteúdo dinâmico)
        self.grid_columnconfigure(0, weight=0)  # Sidebar fixa
        self.grid_columnconfigure(1, weight=1)  # Conteúdo expande
        self.grid_rowconfigure(0, weight=1)

        # === 1. CRIANDO O MENU LATERAL (SIDEBAR) ===
        # Substituição do CTkFrame pelo CTkScrollableFrame
        self.sidebar = ctk.CTkScrollableFrame(self, width=260, corner_radius=0, fg_color=COLORS["sidebar"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        # O frame rolável empilha os itens automaticamente; configuração de peso
        # em linha vazia pode bugar a rolagem, por isso não usamos grid_rowconfigure aqui.

        # --- LOGO E TÍTULO ---
        # Alteração: Texto removido, apenas a imagem é exibida
        self.logo_label = ctk.CTkLabel(
            self.sidebar,
            text="",  # Texto vazio
            image=self.logo_image  # A imagem já contém o texto "GE Vernova"
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 10))

        self.lbl_app = ctk.CTkLabel(self.sidebar, text="SIG-FT System", font=ctk.CTkFont(family="Roboto", size=13), text_color="gray60")
        self.lbl_app.grid(row=1, column=0, padx=20, pady=(0, 20))

        # Botão Home
        self.btn_home = ctk.CTkButton(self.sidebar, text="  🏠  Home", command=lambda: self.show_frame("Home"),
                                      fg_color="transparent", border_width=1, border_color="gray30",
                                      text_color=COLORS["text_light"], anchor="w", font=("Roboto", 13, "bold"),
                                      hover_color=COLORS["primary"])
        self.btn_home.grid(row=2, column=0, padx=15, pady=10, sticky="ew")

        # --- BOTÕES DO MENU ---
        # Seção 1: Início
        self._criar_label_secao(self.sidebar, "Início da Ficha", row=3)
        self.btn_pmib = self._criar_botao_menu(self.sidebar, "1. Cria Fichas PMIB", "CriaFichas", row=4)
        self.btn_pdm = self._criar_botao_menu(self.sidebar, "2. Planilhas PMIB", "PDM", row=5)
        self.btn_analise = self._criar_botao_menu(self.sidebar, "3. Analyzer (IA)", "Analyzer", row=6)

        # Seção 2: Dados Técnicos
        self._criar_label_secao(self.sidebar, "Dados Técnicos & Upload", row=7)
        self.btn_cond = self._criar_botao_menu(self.sidebar, "4.1. Upload Condições", "UploadConditions", row=8)
        self.btn_trad = self._criar_botao_menu(self.sidebar, "4.2. Tradutor", "Translator", row=9)
        self.btn_specs = self._criar_botao_menu(self.sidebar, "4.3. Upload Specs", "UploadSpecs", row=10)
        self.btn_copia = self._criar_botao_menu(self.sidebar, "5. Upload duplicadas", "CopiaFichas", row=11)
        self.btn_auto = self._criar_botao_menu(self.sidebar, "6. AutoSpec AI (RAG)", "AutoSpec", row=12)

        # Seção 3: Gestão
        self._criar_label_secao(self.sidebar, "Gestão & LMR", row=13)
        self.btn_lmr = self._criar_botao_menu(self.sidebar, "7.1. LMR (Upload)", "LMR", row=14)
        self.btn_del_lmr = self._criar_botao_menu(self.sidebar, "7.2. Apagar LMR", "ApagarLMR", row=15)
        self.btn_manager = self._criar_botao_menu(self.sidebar, "8. PMIB Manager", "PMIBManager", row=16)
        self.btn_search = self._criar_botao_menu(self.sidebar, "9. Search", "SearchPMIB", row=17)

        # === 2. INICIALIZANDO OS FRAMES (MÓDULOS) ===
        self.container = ctk.CTkFrame(self, fg_color=COLORS["background"])
        self.container.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.frames = {}

        # Instanciação dos Módulos
        self.frames["Home"] = HomeView(parent=self.container, controller=self)
        self.frames["CriaFichas"] = ModuloCriaFichas(parent=self.container, controller=self)
        self.frames["PDM"] = ModuloPDM(parent=self.container, controller=self)
        self.frames["Analyzer"] = ModuloAnalyzer(parent=self.container, controller=self)
        self.frames["Translator"] = ModuloTranslator(parent=self.container, controller=self)
        self.frames["UploadConditions"] = ModuloUploadConditions(parent=self.container, controller=self)
        self.frames["UploadSpecs"] = ModuloUploadTechSpecs(parent=self.container, controller=self)
        self.frames["CopiaFichas"] = ModuloCopiaFichas(parent=self.container, controller=self)
        self.frames["AutoSpec"] = ModuloAutoSpec(parent=self.container, controller=self)
        self.frames["LMR"] = ModuloLMR(parent=self.container, controller=self)
        self.frames["ApagarLMR"] = ModuloApagarLMR(parent=self.container, controller=self)
        self.frames["PMIBManager"] = ModuloPMIBManager(parent=self.container, controller=self)
        self.frames["SearchPMIB"] = ModuloBuscaPMIB(parent=self.container, controller=self)

        for f in self.frames.values():
            f.configure(fg_color=COLORS["background"])

        self.show_frame("Home")

    # --- Métodos Auxiliares de Estilo ---
    def _criar_botao_menu(self, parent, text, frame_name, row):
        # Botões mais limpos, sem cor de fundo sólida, apenas no hover
        btn = ctk.CTkButton(parent, text=f"  {text}", command=lambda: self.show_frame(frame_name),
                            fg_color="transparent",
                            text_color=COLORS["text_light"],
                            anchor="w",
                            font=("Roboto", 12),
                            hover_color=COLORS["primary"],  # Hover na cor da marca
                            height=35)
        btn.grid(row=row, column=0, padx=10, pady=2, sticky="ew")
        return btn

    def _criar_label_secao(self, parent, text, row):
        # Label de seção mais discreto
        label = ctk.CTkLabel(parent, text=text.upper(), font=("Roboto", 11, "bold"), text_color="gray50", anchor="w")
        label.grid(row=row, column=0, padx=20, pady=(20, 5), sticky="w")

    # --- Gerenciamento de Chaves e Navegação ---
    def load_keys(self):
        gemini_api_key = os.getenv('API_GEMINI_LUAN_GMAIL')
        google_search_api = os.getenv('GOOGLE_SEARCH_API')
        google_cse_api = os.getenv('GOOGLE_CSE_API')
        llama_api = os.getenv('LLAMA_CLOUD_API')
        # [CP 3.2] Gateway OpenRouter (padrão) + endpoint OpenAI-compatível
        # genérico da futura IA interna da empresa — nomes de env var
        # idênticos aos de `sigft.config.ENV_VAR_POR_CHAVE`.
        openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
        empresa_llm_base_url = os.getenv('EMPRESA_LLM_BASE_URL')
        empresa_llm_api_key = os.getenv('EMPRESA_LLM_API_KEY')

        defaults = {
            "GEMINI": gemini_api_key,
            "GOOGLE_SEARCH": google_search_api,
            "GOOGLE_CSE": google_cse_api,
            "LLAMA": llama_api,
            "OPENROUTER": openrouter_api_key,
            "EMPRESA_LLM_BASE_URL": empresa_llm_base_url,
            "EMPRESA_LLM_API_KEY": empresa_llm_api_key
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    saved = json.load(f)
                    self.api_keys = {**defaults, **saved}
            except:
                self.api_keys = defaults
        else:
            self.api_keys = defaults

    def save_keys(self, new_keys):
        self.api_keys = new_keys
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.api_keys, f, indent=4)

    def get_key(self, key_id):
        return self.api_keys.get(key_id, "")

    def show_frame(self, name):
        for frame in self.frames.values():
            frame.grid_forget()
        frame = self.frames.get(name)
        if frame:
            frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

    def show_modulo(self, nome_modulo):
        self.show_frame(nome_modulo)

    def show_home(self):
        self.show_frame("Home")


if __name__ == "__main__":
    # O loop principal agora começa pela Splash Screen
    # Ela, por sua vez, chamará o SIG_FT_App ao terminar
    splash = SplashScreen()
    splash.mainloop()
