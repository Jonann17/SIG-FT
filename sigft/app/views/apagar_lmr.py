"""Tela "Apagar Aplicações LMR" — Checkpoint 7.3 (Fase 7 do plano).

Ferramenta destrutiva: apaga TODAS as aplicações LMR de uma ficha do portal.
Daí o título em vermelho e a confirmação antes de começar.

Foi uma das duas telas piloto do CP 7.1 — já herda de `ModuleFrame`, então o
esqueleto (header/conteúdo/console) e o `log()` thread-safe vêm de lá.
"""
from __future__ import annotations

import threading
from tkinter import messagebox

from sigft.app import backends
from sigft.app.theme import COLORS
from sigft.app.widgets.module_frame import ModuleFrame

import customtkinter as ctk




# =============================================================================
# MÓDULO 10: APAGAR LMR (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloApagarLMR(ModuleFrame):
    # [CP 7.1] Tela piloto nº 1 do esqueleto compartilhado. As 12 linhas de
    # __init__ (grid + header + content + console) viraram a chamada ao
    # ModuleFrame; o `log()` proprio saiu, porque o herdado e thread-safe.
    #
    # Isto aqui era um BUG, nao so duplicacao: o `log()` antigo chamava
    # `self.console.insert` DIRETO, e o `_worker` abaixo roda numa
    # threading.Thread. Tocar widget do Tk fora da thread da interface e
    # corrupcao de estado -- log sumindo no meio do lote, no melhor caso.
    def __init__(self, parent, controller):
        super().__init__(
            parent,
            controller,
            titulo="Apagar Aplicações LMR",
            cor_titulo=COLORS["danger"],
        )

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
        auto = backends.apagar_lmr_backend.ApagarLMRAutomation()
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
