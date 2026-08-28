"""Tela "Tradutor Técnico (PT -> ES)" — Checkpoint 7.3 (Fase 7 do plano).

Traduz as características técnicas das fichas do português para o espanhol,
criando uma aba nova na própria planilha. O backend usa `xlwings` (automação
do Excel), por isso é Windows-only.

Segunda tela piloto do CP 7.1: já herda de `ModuleFrame`.
"""
from __future__ import annotations

import threading
from tkinter import messagebox

from sigft.app import backends, file_dialogs
from sigft.app.theme import COLORS
from sigft.app.widgets.module_frame import ModuleFrame

import customtkinter as ctk




# =============================================================================
# MÓDULO 4: TRADUTOR DE FICHAS (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloTranslator(ModuleFrame):
    # [CP 7.1] Tela piloto nº 2. Mesmo caso do ModuloApagarLMR: o `log()`
    # antigo escrevia no widget direto, e o `_worker` roda em thread.
    def __init__(self, parent, controller):
        # O backend entra DEPOIS do super(): o `_build_ui` roda dentro dele e
        # nao usa `self.backend` (so `iniciar_traducao`/`parar_traducao` usam,
        # e essas so rodam por clique, com a tela ja montada).
        super().__init__(parent, controller, titulo="Tradutor Técnico (PT -> ES)")
        self.backend = backends.translator_backend.TechnicalTranslator()

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
                for msg in self.backend.processar_arquivo(
                    f_path, retry_lock=self.perguntar_retry_excel
                ):
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
