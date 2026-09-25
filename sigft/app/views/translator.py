"""Tela "Tradutor Técnico (PT -> ES)" — Checkpoint 7.3 (Fase 7 do plano).

Traduz as características técnicas das fichas do português para o espanhol,
criando uma aba nova na própria planilha. O backend usa `xlwings` (automação
do Excel), por isso é Windows-only.

Desde 2026-09-25 a tradução é LOCAL (`sigft/core/tradutor_local.py`): nada
sai do computador, e o lote inteiro vai ao serviço de uma vez -- um Excel e um
modelo para todas as fichas.

Segunda tela piloto do CP 7.1: já herda de `ModuleFrame`.
"""
from __future__ import annotations

import threading
from tkinter import messagebox

from sigft.app import backends, file_dialogs
from sigft.app.theme import COLORS
from sigft.app.widgets.module_frame import ModuleFrame
from sigft.core import plataforma

import customtkinter as ctk




# =============================================================================
# MÓDULO 4: TRADUTOR DE FICHAS (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloTranslator(ModuleFrame):
    # [CP 7.1] Tela piloto nº 2. Mesmo caso do ModuloApagarLMR: o `log()`
    # antigo escrevia no widget direto, e o `_worker` roda em thread.
    def __init__(self, parent, controller):
        # O backend nasce no PRIMEIRO CLIQUE (`_backend`), não aqui. Criado no
        # `__init__`, um backend que não carregou (faltou `unidecode` ou
        # `xlwings`) derrubava a janela principal inteira -- PENDENCIAS,
        # 2026-09-24 --, contra a promessa de `backends.carregar_todos` de
        # deixar só esta tela sem funcionar.
        self.backend = None
        super().__init__(parent, controller, titulo="Tradutor Técnico (PT -> ES)")

    def _build_ui(self):
        frm_main = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8)
        frm_main.pack(fill="x", pady=20)

        ctk.CTkLabel(frm_main, text="Tradução Automática de Características", font=("Roboto", 16, "bold"), text_color=COLORS["accent"]).pack(pady=(20, 10))
        ctk.CTkLabel(frm_main, text="Selecione as planilhas para traduzir do Português para Espanhol.\n"
                                    "O sistema cria uma nova aba traduzida.\n"
                                    "A tradução roda neste computador: nenhuma resposta sai daqui.",
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
        self.btn_stop.pack(pady=(10, 10))

        # O "corrigiu uma vez, vale sempre": o termo técnico que o tradutor
        # errar vai para este arquivo (Documentos\SIG-FT\traducao).
        ctk.CTkButton(frm_main, text="Abrir glossário (correções de termos)",
                      height=32, width=300, command=self.abrir_glossario,
                      fg_color="transparent", border_width=1,
                      text_color=COLORS["text_light"]).pack(pady=(0, 20))

    def _backend(self):
        """O tradutor, criado no primeiro uso. `None` (com aviso) se o módulo
        não carregou na abertura do app."""
        if self.backend is None:
            modulo = backends.translator_backend
            if modulo is None:
                messagebox.showerror(
                    "Tradutor", "O módulo do tradutor não carregou na abertura do SIG-FT. "
                                "Veja o log de inicialização e reinstale a versão mais nova.")
                return None
            self.backend = modulo.TechnicalTranslator()
        return self.backend

    def iniciar_traducao(self):
        if self._backend() is None:
            return
        files = file_dialogs.ask_open_files("translator.fichas", "excel", titulo="Selecione as Fichas (.xlsx)", filetypes=[("Excel", "*.xlsx")])
        if not files: return

        self.log(f"Iniciando tradução de {len(files)} arquivos...")
        self.btn_run.configure(state="disabled")
        self.btn_stop.configure(state="normal")

        threading.Thread(target=self._worker, args=(files,)).start()

    def parar_traducao(self):
        if self.backend is not None:
            self.backend.request_stop()
        self.log("[COMANDO] Parada solicitada...")

    def abrir_glossario(self):
        backend = self._backend()
        if backend is None:
            return
        try:
            caminho = backend.caminho_do_glossario()
            self.log(f"Abrindo o glossário: {caminho}")
            plataforma.abrir_no_sistema(caminho)
        except Exception as e:
            messagebox.showerror("Glossário", f"Não consegui abrir o glossário: {e}")

    def _worker(self, files):
        status = backends.translator_backend.STATUS
        ultimo_erro = ""
        try:
            for msg in self.backend.processar_arquivos(
                files, retry_lock=self.perguntar_retry_excel
            ):
                if msg == "PARADO":
                    self.log("Processo interrompido pelo usuário.")
                    return
                if msg == "ABORTADO":
                    self.log("Tradução não iniciada.")
                    messagebox.showerror("Tradutor", ultimo_erro or "A tradução não pôde começar.")
                    return
                if msg in status:
                    continue
                if msg.startswith("[ERRO]"):
                    ultimo_erro = msg
                self.log(msg)

            self.log("Tradução em lote finalizada.")
            messagebox.showinfo("Sucesso", "Processo concluído.")
        except Exception as e:
            self.log(f"Erro Fatal: {e}")
        finally:
            self.btn_run.configure(state="normal")
            self.btn_stop.configure(state="disabled")
