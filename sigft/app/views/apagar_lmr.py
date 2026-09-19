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
# [CP B] Mensagens e dialogo da pausa de acao manual (login no portal).
from sigft.app.widgets import dialogs as app_dialogs
# [2026-08-28] Seletor do _STATUS_PMIB opcional.
from sigft.app.widgets import pickers as app_pickers

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
    def __init__(self, parent, controller, *, embutida=False, console_externo=None):
        # Antes do super(): o `_build_ui` roda lá dentro e cria o picker, que
        # grava aqui quando o usuário escolhe um arquivo.
        self.caminho_status = None
        super().__init__(
            parent,
            controller,
            titulo="Apagar Aplicações LMR",
            cor_titulo=COLORS["danger"],
            # [2026-08-28] Vira a aba "Exclusão" da seção Aplicação LMR. Sem
            # header próprio (a seção já tem um) e escrevendo no console dela.
            embutida=embutida,
            console_externo=console_externo,
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

        # [2026-08-28] _STATUS_PMIB OPCIONAL, pedido do usuário: apagou as
        # aplicações com sucesso -> a coluna "APLICAÇÃO - LMR" volta a ficar EM
        # BRANCO. É o inverso do que a tela de Aplicação LMR faz, e usa o mesmo
        # módulo (`services/lmr_status.py`).
        #
        # Opcional de propósito: sem a planilha, a tela se comporta exatamente
        # como antes. Quem só quer limpar a ficha no portal não é obrigado a
        # apontar um Excel.
        ctk.CTkLabel(
            frm_main,
            text="Opcional: informe o _STATUS_PMIB para LIMPAR a marcação da coluna\n"
                 "\"APLICAÇÃO - LMR\" das fichas que forem apagadas com sucesso.",
            font=("Roboto", 12),
            text_color="gray70",
            justify="center",
        ).pack(pady=(15, 5))

        self.picker_status = app_pickers.FilePickerRow(
            frm_main,
            chave="apagar_lmr.status_pmib",
            categoria="excel",
            texto_botao="Selecionar _STATUS_PMIB",
            largura_botao=220,
            titulo="Selecione o _STATUS_PMIB (opcional)",
            filetypes=[("Excel", "*.xlsx;*.xlsm")],
            texto_vazio="Nenhum (a planilha não será alterada)",
            ao_escolher=self._ao_escolher_status,
        )
        self.picker_status.pack(pady=(0, 10))

        self.btn_run = ctk.CTkButton(frm_main, text="INICIAR LIMPEZA",
                                     height=50, width=350,
                                     command=self.iniciar_limpeza,
                                     font=("Roboto", 14, "bold"),
                                     fg_color=COLORS["danger"], hover_color="#B71C1C", text_color=COLORS["text_white"])
        self.btn_run.pack(pady=20)

        info_steps = "O robô irá:\n1. Abrir o navegador\n2. Solicitar login manual\n3. Acessar a ficha\n4. Clicar em todas as lixeiras até esvaziar a lista."
        ctk.CTkLabel(frm_main, text=info_steps, text_color="gray70", font=("Roboto", 12)).pack(pady=(0, 20))

    # --- _STATUS_PMIB opcional (2026-08-28) ---
    def _ao_escolher_status(self, caminho):
        self.caminho_status = caminho
        self.log(f"_STATUS_PMIB selecionado: {caminho}")

    def _limpar_status_do_lote(self, pmib, limpou):
        """Limpa a coluna "APLICAÇÃO - LMR" da ficha apagada.

        Só age quando as DUAS condições valem: o usuário informou a planilha E
        a exclusão terminou bem. Limpar a marcação de uma ficha cuja exclusão
        falhou diria que ela está por fazer enquanto as aplicações continuam
        no portal.
        """
        caminho = getattr(self, "caminho_status", None)
        if not caminho:
            return

        if not limpou:
            self.log(
                "   [i] A exclusão não terminou limpa. O _STATUS_PMIB NÃO foi "
                "alterado. A marcação continua como estava, o que é o certo "
                "enquanto houver aplicação na ficha."
            )
            return

        try:
            _n, recado = backends.apagar_lmr_backend.limpar_status_pmib(
                caminho,
                [pmib],
                retry_lock=self.perguntar_retry_excel,
                callback_log=self.log,
            )
            self.log(f"   {recado}")
        except Exception as erro:  # noqa: BLE001
            # A planilha não pode derrubar o resultado: o trabalho no portal
            # já foi feito e não é repetível.
            self.log(f"   [!] Não consegui atualizar o _STATUS_PMIB: {erro}")

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
            # [CP B] Era `messagebox.showinfo`, chamado daqui de dentro do
            # `_worker` -- ou seja, criando widget fora da thread da interface.
            # O botao diz o que vai acontecer: a acao e destrutiva.
            self.pausar_e_esperar(
                app_dialogs.MSG_LOGIN_APAGAR_LMR,
                texto_botao=app_dialogs.TEXTO_COMECAR_EXCLUSAO,
            )

            def cb_log(txt): self.log(txt)

            self.log("Iniciando varredura...")
            limpou = auto.executar_limpeza(pmib, callback_log=cb_log)
            self.log("Processo Finalizado.")

            self._limpar_status_do_lote(pmib, limpou)

            messagebox.showinfo("Sucesso", "Limpeza concluída.")

        except Exception as e:
            self.log(f"Erro Fatal: {e}")
        finally:
            auto.fechar_driver()
            self.btn_run.configure(state="normal")
