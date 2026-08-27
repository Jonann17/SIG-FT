"""Tela "LMR" — Checkpoint 7.3 (Fase 7 do plano).

Preenchimento automático das aplicações LMR no portal, a partir de uma
planilha. É RPA: abre o navegador e pede login manual antes de começar.
"""
from __future__ import annotations

import os
import threading
from tkinter import messagebox, simpledialog

from sigft.app import backends, file_dialogs
from sigft.app.theme import COLORS

import customtkinter as ctk


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

        info_text = ("Este módulo lê uma aba de um arquivo Excel e cadastra as aplicações no Portal PMIB.\n"
                     "Você escolhe a aba depois de selecionar o arquivo.\n"
                     "Colunas esperadas: FICHA PMIB, CÓDIGO LMR e TAG LMR.\n"
                     "Será solicitado login no navegador durante o processo.")
        ctk.CTkLabel(frm_main, text=info_text, font=("Roboto", 13), text_color="gray").pack(pady=(0, 20))

        self.btn_run = ctk.CTkButton(frm_main, text="Selecionar Excel e Iniciar",
                                     height=50, width=300,
                                     command=self.iniciar_lmr,
                                     font=("Roboto", 14, "bold"),
                                     fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"], text_color=COLORS["text_white"])
        self.btn_run.pack(pady=10)

        # COMEÇAR DE UM CÓDIGO ESPECÍFICO — desligado por padrão.
        #
        # ⚠️ 2026-08-21, pedido do usuário: *"o default das fichas deve ser
        # começar do 0, e somente quando eu peço para começar de uma linha
        # específica que deve aparecer a mensagem (tipo um toggle pra
        # habilitar/desabilitar)"*. Antes, TODA execução abria um Sim/Não e,
        # se sim, um segundo diálogo pedindo o número — duas caixas por ficha
        # para uma resposta que é "não" quase sempre.
        f_inicio = ctk.CTkFrame(frm_main, fg_color="transparent")
        f_inicio.pack(pady=(4, 8))

        self.var_linha_inicial = ctk.BooleanVar(value=False)
        self.entry_linha_inicial = ctk.CTkEntry(f_inicio, width=70, placeholder_text="0",
                                                justify="center")

        def _alternar():
            ligado = self.var_linha_inicial.get()
            self.entry_linha_inicial.configure(state="normal" if ligado else "disabled")
            if not ligado:
                self.entry_linha_inicial.delete(0, "end")

        ctk.CTkSwitch(f_inicio, text="Começar de um código específico",
                      variable=self.var_linha_inicial, command=_alternar,
                      font=("Roboto", 12), progress_color=COLORS["accent"]).pack(side="left", padx=(0, 10))
        self.entry_linha_inicial.pack(side="left")
        self.entry_linha_inicial.configure(state="disabled")

        ctk.CTkLabel(
            frm_main,
            text=("Desligado, processa a ficha inteira desde o começo.\n"
                  "O número conta CÓDIGOS LMR (não linhas do Excel): o mesmo código\n"
                  "espalhado pela planilha é uma aplicação só."),
            text_color="gray70", font=("Roboto", 11), justify="center",
        ).pack(pady=(0, 10))

        ctk.CTkLabel(frm_main, text="O script pedirá:\n1. Arquivo Excel LMR\n2. Seleção das Fichas (Checkbox)",
                     text_color="gray70", font=("Roboto", 12)).pack(pady=(10, 20))

    # --- Lógica Mantida ---
    def iniciar_lmr(self):
        excel_path = file_dialogs.ask_open_file("lmr.excel", "excel", titulo="Selecione o Excel LMR", filetypes=[("Excel", "*.xlsx")])
        if not excel_path: return
        # QUEM ESCOLHE A ABA É O USUÁRIO. A primeira versão disto adivinhava
        # (tentava 'LMR', 'GERAL' e depois qualquer aba com as colunas), e o
        # usuário recusou -- adivinhar aba funciona nove vezes e, na décima,
        # cadastra o lote a partir da planilha errada sem ninguém notar.
        try:
            abas = backends.lmr_backend.listar_abas(excel_path)
        except Exception as e:
            messagebox.showerror("Erro", f"Não consegui ler as abas do arquivo:\n{e}")
            return
        if not abas:
            messagebox.showerror("Erro", "O arquivo não tem nenhuma aba.")
            return

        self._escolher_aba_lmr(excel_path, abas)

    def _escolher_aba_lmr(self, excel_path, abas):
        """Diálogo de uma pergunta só: qual aba ler."""
        janela = ctk.CTkToplevel(self)
        janela.title("Escolha a aba")
        janela.geometry("420x220")
        janela.transient(self.winfo_toplevel())
        janela.grab_set()

        ctk.CTkLabel(janela, text=os.path.basename(excel_path), font=("Roboto", 12, "bold")).pack(pady=(20, 4))
        ctk.CTkLabel(
            janela, text="Qual aba contém as aplicações de LMR?",
            font=("Roboto", 12), text_color="gray70",
        ).pack(pady=(0, 12))

        var_aba = ctk.StringVar(value=abas[0])
        ctk.CTkOptionMenu(janela, values=abas, variable=var_aba, width=300).pack(pady=5)

        def confirmar():
            aba = var_aba.get()
            janela.destroy()
            self.log(f"Lendo {os.path.basename(excel_path)} (aba '{aba}')...")
            self.btn_run.configure(state="disabled")
            threading.Thread(target=self._pre_processamento, args=(excel_path, aba)).start()

        ctk.CTkButton(
            janela, text="Ler esta aba", command=confirmar, width=300,
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
        ).pack(pady=(15, 5))
        ctk.CTkButton(
            janela, text="Cancelar", command=janela.destroy, width=300,
            fg_color="#3A3A3A", hover_color="#454545",
        ).pack(pady=5)

    def _pre_processamento(self, excel_path, aba):
        try:
            automator = backends.lmr_backend.LMRAutomation()
            ok, df_completo, pmibs_unicos, msg = automator.carregar_dados_excel(excel_path, aba)

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

    def _linha_inicial_escolhida(self):
        """Número do toggle, ou `None` quando ele está desligado.

        `None` e `0` NÃO são a mesma coisa para o serviço: `None` quer dizer
        "não me pergunte nada, comece do começo"; um número quer dizer "a tela
        já perguntou, use este". Ler a caixa desligada devolveria `0` e a
        distinção se perderia -- inofensiva hoje, mas é ela que permite o
        serviço avisar quando o número está fora da faixa.
        """
        if not getattr(self, "var_linha_inicial", None) or not self.var_linha_inicial.get():
            return None
        texto = (self.entry_linha_inicial.get() or "").strip()
        if not texto:
            return None
        try:
            return int(texto)
        except ValueError:
            # O serviço também trata, mas avisar aqui é mais cedo e mais perto
            # de quem digitou.
            self.log(f"Linha inicial {texto!r} não é um número. Começando do 0.")
            return None

    def _worker_lmr(self, selecionados, df_completo):
        auto = backends.lmr_backend.LMRAutomation()
        try:
            self.log("Iniciando navegador...")
            auto.iniciar_driver()
            self.log("Carregando portal...")
            auto.abrir_portal()
            messagebox.showinfo("Login Necessário", "Faça login no navegador e clique OK para começar.")

            def cb_log(txt): self.log(txt)
            def cb_ask(tit, msg): return messagebox.askyesno(tit, msg)
            def cb_input(tit, msg): return simpledialog.askstring(tit, msg)

            auto.processar_lista(selecionados, df_completo, callback_log=cb_log,
                                 callback_ask=cb_ask, callback_input=cb_input,
                                 linha_inicio=self._linha_inicial_escolhida())

            self.log("Automação LMR finalizada.")
            messagebox.showinfo("Sucesso", "Processo concluído.")
        except Exception as e:
            self.log(f"Erro Fatal LMR: {e}")
        finally:
            auto.fechar_driver()
            self.btn_run.configure(state="normal")

