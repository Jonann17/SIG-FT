"""Tela "Busca PMIB" — Checkpoint 7.3 (Fase 7 do plano).

Procura fichas numa árvore de pastas e mostra o resultado em tabela, com
atalho para abrir o arquivo encontrado no Explorer.
"""
from __future__ import annotations

import os
import subprocess
import threading
from tkinter import messagebox

from sigft.app import backends, file_dialogs
from sigft.app.theme import COLORS

import customtkinter as ctk


# [CP 7.3] Vivia solta no topo do `frontend.py`. So esta tela a usa, entao
# veio junto em vez de virar utilitario compartilhado que ninguem compartilha.
def _altura_do_textbox(texto, largura_em_caracteres=90, altura_da_linha=20, folga=12):
    """Altura em pixels para um `CTkTextbox` caber `texto` sem cortar.

    Conta as quebras de linha reais mais as que o `wrap="word"` vai fazer, e
    soma uma FOLGA para o padding interno do widget.

    A folga é o conserto: a versão anterior usava 18px por linha e nenhuma
    folga, e cortava a última linha justamente no caso mais comum — um caminho
    de arquivo longo, que ocupa 2 linhas. Sobrava altura para o texto e faltava
    para a margem que o próprio textbox reserva.

    `largura_em_caracteres=90` é a estimativa de quantos caracteres cabem numa
    linha do card. Subestimar é o lado seguro: sobra altura, não falta.

    Também elimina a duplicação — a fórmula estava copiada nos dois textboxes
    do card (caminho e amostra), com os mesmos números mágicos nos dois.
    """
    linhas = texto.split("\n")
    # `-(-a // b)` é divisão para cima: uma linha de 91 caracteres ocupa 2.
    total = sum(max(1, -(-len(linha) // largura_em_caracteres)) for linha in linhas)
    return max(35, total * altura_da_linha + folga)


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
            searcher = backends.search_pmib_backend.PMIBSearcher()
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

            texto_caminho = f"📂 Caminho:\n{caminho_arq}"
            altura_dinamica_cam = _altura_do_textbox(texto_caminho)

            # Linha 2: Caminho Completo (Textbox com altura dinâmica)
            txt_caminho = ctk.CTkTextbox(card, font=("Consolas", 11), text_color="#A0A0A0", fg_color="transparent", border_width=0, height=altura_dinamica_cam, wrap="word")
            txt_caminho.insert("0.0", texto_caminho)
            txt_caminho.configure(state="disabled")  # Bloqueia digitação, mas permite selecionar e copiar
            txt_caminho.pack(fill="x", padx=10, pady=2)

            # Linha 3: Amostra (Textbox com altura dinâmica)
            if amostra:
                texto_amostra = f"🔎 Amostra: {amostra}"
                altura_dinamica_amo = _altura_do_textbox(texto_amostra)

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

