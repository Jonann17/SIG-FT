"""Tela "Analyzer" — Checkpoint 7.3 (Fase 7 do plano).

Valida e pontua fichas técnicas com IA, separando as aprovadas das que voltam
para o fornecedor. Gera o relatório de pendências em Excel.

⚠️ `_perguntar_descricao` é chamado PELO BACKEND de dentro da thread de
processamento e abre a janela com `self.after(0, ...)` + `Event`. Por isso ele
precisa de um `self` que seja widget tkinter com `.after()` — não vira função
solta (ver `TRABALHO_PARALELO.md` §3.1).
"""
from __future__ import annotations

import os
import threading
from tkinter import messagebox, simpledialog

import openpyxl

from sigft.app import backends
from sigft.app.theme import COLORS
from sigft.app.widgets import pickers as app_pickers
from sigft.services import analyzer_relatorio

import customtkinter as ctk
# [CP D] Mixin com `perguntar_retry_excel`: a janela de "o arquivo esta
# aberto no Excel, fecho e tento de novo?". Vem ANTES de ctk.CTkFrame.
from sigft.app.widgets.espera import DialogosDeEspera


# =============================================================================
# MÓDULO 3: TECHNICAL DATASHEET ANALYZER (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloAnalyzer(DialogosDeEspera, ctk.CTkFrame):
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

        # [CP 7.2] Os tres seletores desta tela sao FilePickerRow/Folder/Multi.
        # Cada um declara a sua chave da memoria de caminhos UMA vez, aqui, e a
        # tela nunca mais chama file_dialogs -- e o "memoria embutida, nao
        # chamada manual" que o checkpoint pede. O rotulo em verde E o botao
        # pintado continuam iguais: os dois estao no widget.

        # A) Arquivos de Entrada
        self.picker_files = app_pickers.MultiFilePickerRow(
            frm_files,
            chave="analyzer.fichas",
            categoria="excel",
            texto_botao="Selecionar Fichas (.xlsx)",
            largura_botao=200,
            titulo="Selecione as Fichas Técnicas",
            filetypes=[("Excel", "*.xlsx")],
            ao_escolher=self._ao_escolher_fichas,
        )
        self.picker_files.pack(fill="x", padx=15, pady=5)

        # B) Pasta de Saída
        self.picker_out = app_pickers.FolderPickerRow(
            frm_files,
            chave="analyzer.saida",
            texto_botao="Pasta de Saída",
            largura_botao=200,
            titulo="Selecione Pasta de Saída",
            ao_escolher=self._ao_escolher_saida,
        )
        self.picker_out.pack(fill="x", padx=15, pady=5)

        # C) PMIB (Opcional)
        self.picker_pmib = app_pickers.FilePickerRow(
            frm_files,
            chave="analyzer.status_pmib",
            categoria="excel",
            texto_botao="STATUS_PMIB (Opcional)",
            largura_botao=200,
            titulo="Selecione STATUS_PMIB",
            filetypes=[("Excel", "*.xlsx")],
            # Texto proprio desta tela -- ela avisa qual e o padrao quando
            # nada e escolhido, e isso e informacao util, nao ruido.
            texto_vazio="Não selecionado (Padrão: sem contexto)",
            ao_escolher=self._ao_escolher_pmib,
        )
        self.picker_pmib.pack(fill="x", padx=15, pady=(5, 15))

        # --- AÇÃO ---
        self.btn_run = ctk.CTkButton(self.content, text="INICIAR PROCESSAMENTO",
                                     height=50, width=300,
                                     command=self.iniciar_analise,
                                     font=("Roboto", 15, "bold"),
                                     fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"], text_color=COLORS["text_white"])
        self.btn_run.pack(pady=(30, 8))

        # Relatorio para o FORNECEDOR (2026-08-26). Nasce desabilitado: so
        # existe relatorio depois de um lote rodar, e botao que promete o que
        # nao tem e pior que botao ausente.
        self.relatorio_analise = None
        self.btn_relatorio = ctk.CTkButton(
            self.content, text="GERAR RELATÓRIO PARA O FORNECEDOR (.xlsx)",
            height=36, width=300, command=self._gerar_relatorio,
            font=("Roboto", 12), state="disabled",
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"])
        self.btn_relatorio.pack(pady=(0, 25))

    def _gerar_relatorio(self):
        """Grava o `.xlsx` de pendências na pasta de saída da análise.

        Uma linha por material: código PMIB, o que precisa ser corrigido (com
        a justificativa que a IA escreveu para o fornecedor) e a nota. É o
        arquivo que se manda a quem preencheu a ficha.
        """
        if not self.relatorio_analise:
            return messagebox.showinfo(
                "Relatório", "Rode uma análise primeiro — não há pendências para relatar.")
        destino = self.selected_output or os.getcwd()
        try:
            caminho = self.relatorio_analise.salvar_xlsx(
                destino, retry_lock=self.perguntar_retry_excel
            )
        except Exception as e:
            self.log(f"Nao consegui gerar o relatorio: {e}")
            return messagebox.showerror("Relatório", f"Não consegui gerar o arquivo:\n{e}")
        if not caminho:
            return messagebox.showinfo(
                "Relatório", "Nenhuma ficha ficou com pendência — não há o que relatar.")
        self.log(f"Relatorio gerado: {caminho}")
        messagebox.showinfo(
            "Relatório", f"{len(self.relatorio_analise)} ficha(s) com pendência.\n\n"
                         f"Arquivo:\n{caminho}")

    # --- Janela de Configuração de Pesos ---
    def abrir_config_pesos(self):
        if not backends.analyzer_backend:
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
        config_map = backends.analyzer_backend.CONFIG_MAP
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

    # [CP 7.2] Os pickers cuidam do dialogo, da memoria de caminho e das duas
    # mudancas de cor. Sobra a esta tela so guardar o que foi escolhido, no
    # formato que `iniciar_analise` ja esperava.
    def _ao_escolher_fichas(self, caminhos):
        self.selected_files = list(caminhos)

    def _ao_escolher_saida(self, pasta):
        self.selected_output = pasta

    def _ao_escolher_pmib(self, caminho):
        self.selected_pmib = caminho

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

    def _perguntar_descricao(self, arquivo, codigo):
        """Pergunta a descrição do material quando o código PMIB não está no
        `_STATUS_PMIB`.

        Chamado PELO BACKEND, de dentro da thread de processamento — por isso
        a janela é aberta com `self.after(0, ...)` (thread da UI) e a thread
        do backend espera num `Event`. É o mesmo padrão que
        `ModuloUploadConditions._worker_web` já usa; abrir janela tkinter
        fora da thread principal é o caminho curto para travar o app.

        **Cancelar para de perguntar no resto do lote.** Um lote de 50 fichas
        com PMIB desconhecido não pode virar 50 caixas de diálogo
        obrigatórias — e a saída precisa ser óbvia para quem está com pressa.

        Até 2026-08-26 este callback era `lambda f, c: None`: o backend o
        chamava, e ele nunca fazia nada.
        """
        if getattr(self, "_parar_de_perguntar_desc", False):
            return None

        evento = threading.Event()
        resposta = {"texto": None}

        def _abrir():
            try:
                resposta["texto"] = simpledialog.askstring(
                    "Descrição do material",
                    f"A ficha {arquivo} tem o código PMIB {codigo}, que não está "
                    "no _STATUS_PMIB.\n\nSe você souber a descrição do material, "
                    "digite abaixo — ela entra no contexto que vai para a IA.\n\n"
                    "CANCELAR segue sem descrição e não pergunta mais nesta rodada.",
                    parent=self,
                )
            except Exception:
                resposta["texto"] = None
            finally:
                evento.set()

        self.after(0, _abrir)
        evento.wait()

        if resposta["texto"] is None:      # Cancelar (≠ de OK com campo vazio)
            self._parar_de_perguntar_desc = True
            self.log(" -> Sem descricao manual; nao vou perguntar de novo nesta rodada.")
            return None
        texto = resposta["texto"].strip()
        if texto:
            self.log(f" -> Descricao informada a mao: {texto}")
        return texto or None

    def _run_backend(self):
        try:
            self._parar_de_perguntar_desc = False
            analyzer = backends.analyzer_backend.DatasheetAnalyzer(self.api_key)
            # Relatorio para o fornecedor: o backend acumula os achados de
            # cada ficha aqui dentro (ver `_registrar_no_relatorio`).
            self.relatorio_analise = analyzer_relatorio.RelatorioAnalise()
            analyzer.relatorio = self.relatorio_analise
            self.btn_relatorio.configure(state="disabled")
            pmib_sheet = None
            if self.selected_pmib:
                try:
                    wb = openpyxl.load_workbook(self.selected_pmib, data_only=True)
                    # 2026-08-26: era `wb.active` — a aba selecionada quando o
                    # arquivo foi salvo, que pode ser uma capa. Aí NENHUMA
                    # ficha do lote achava descrição. Ver `aba_do_status_pmib`.
                    pmib_sheet = backends.analyzer_backend.aba_do_status_pmib(wb)
                    self.log("STATUS_PMIB carregada.")
                except Exception as e: self.log(f"Erro STATUS_PMIB: {e}")

            ok, falhas = 0, []
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
                    callback_manual_desc=self._perguntar_descricao,
                    retry_lock=self.perguntar_retry_excel,
                )
                # 2026-08-26, duas correções neste laço:
                #
                # 1. `for log in iterador: ...` DESCARTAVA o `return True/False`
                #    do backend -- num generator ele vai para
                #    `StopIteration.value`, nunca é "yieldado". O `if not
                #    isinstance(log_msg, bool)` que estava aqui filtrava um
                #    bool que nunca chegava. Resultado: a tela dizia "Análise
                #    finalizada" mesmo com todas as fichas falhando.
                # 2. Uma exceção numa ficha derrubava o LOTE INTEIRO, e as
                #    fichas seguintes nem eram tentadas.
                try:
                    while True:
                        try:
                            self.log(next(iterador_logs))
                        except StopIteration as fim:
                            ok += 1 if fim.value else 0
                            if not fim.value: falhas.append(fname)
                            break
                except Exception as e:
                    self.log(f"[ERRO] {fname}: {e}")
                    falhas.append(fname)

            self.log(f"Concluído! {ok} de {len(self.selected_files)} ficha(s) processada(s).")
            if self.relatorio_analise:
                self.btn_relatorio.configure(state="normal")
                self.log(f"{len(self.relatorio_analise)} ficha(s) com pendencia. Use "
                         "GERAR RELATORIO PARA O FORNECEDOR (.xlsx).")
            if falhas:
                self.log(f"NAO concluidas ({len(falhas)}): {', '.join(falhas)}")
                messagebox.showwarning(
                    "Análise finalizada com pendências",
                    f"{len(falhas)} de {len(self.selected_files)} ficha(s) não foram "
                    "processadas.\nVeja o console para o motivo de cada uma."
                )
            else:
                messagebox.showinfo("Sucesso", "Análise finalizada.")
        except Exception as e: self.log(f"Erro Fatal: {e}")
        finally: self.btn_run.configure(state="normal")

