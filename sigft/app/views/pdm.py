"""Tela "PDM" — Checkpoint 7.3 (Fase 7 do plano).

Fatia o arquivo geral de PDMs vindo de Itaipu, cria as pastas/fichas por
código PMIB a partir do template, e limpa duplicatas de pasta.
"""
from __future__ import annotations

import os
import threading
from tkinter import messagebox

import pandas as pd

from sigft.app import backends, file_dialogs
from sigft.app.theme import COLORS
from sigft.app.widgets import dialogs as app_dialogs
from sigft.core import pdm_catalogo
from sigft.core import prefs
from sigft.core.callbacks import from_legacy
from sigft.core.excel.pmib_codes import normalize_pmib

import customtkinter as ctk
# [CP D] Mixin com `perguntar_retry_excel`: a janela de "o arquivo esta
# aberto no Excel, fecho e tento de novo?". Vem ANTES de ctk.CTkFrame.
from sigft.app.widgets.espera import DialogosDeEspera


# =============================================================================
# MÓDULO 2: PROCESSAMENTO DE PDMS (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloPDM(DialogosDeEspera, ctk.CTkFrame):
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
        # Ficha em ingles (2026-08-28): a pasta dos PDMs traduzidos e o idioma
        # escolhido para a montagem. Default "pt" -- quem nao mexe em nada
        # continua tendo exatamente o comportamento de sempre.
        self.caminho_destino_en = ctk.StringVar()
        self.idioma_ficha = ctk.StringVar(value="pt")

        # Novas variáveis visuais para a Aba 2
        self.path_status_pmib = ctk.StringVar()
        self.path_destino_fichas = ctk.StringVar()
        self.path_template = ctk.StringVar()
        self.modo_pmib = ctk.StringVar(value="todos")
        self.modo_saida_fichas = ctk.StringVar(value="apenas_planilhas")  # NOVA: Variável da Melhoria 1
        # Fonte das perguntas da aba 2 (2026-09-24): a planilha de PDMs é a
        # padrão; a pasta de PDMs Modificados continua como método antigo.
        self.fonte_perguntas = ctk.StringVar(value="planilha")

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
        f_path.pack(fill="x", padx=15, pady=(0, 5))
        ctk.CTkLabel(f_path, text="Pasta dos PDMs Modificados:", width=190, anchor="w").pack(side="left")
        self.entry_dest = ctk.CTkEntry(f_path, textvariable=self.caminho_destino, width=350)
        self.entry_dest.pack(side="left", padx=5)
        ctk.CTkButton(f_path, text="Selecionar", command=self._sel_destino,
                      fg_color="#3A3A3A", hover_color="#454545", width=100).pack(side="left")

        # A planilha de PDMs subiu da aba 1 para cá em 2026-09-24: as duas
        # abas passaram a usá-la (regenerar/fatiar e criar as fichas).
        f_plan = ctk.CTkFrame(frm_config, fg_color="transparent")
        f_plan.pack(fill="x", padx=15, pady=(0, 15))
        ctk.CTkLabel(f_plan, text="Planilha de PDMs (SAM-GM):", width=190, anchor="w").pack(side="left")
        self.btn_sam_gm = ctk.CTkButton(f_plan, text="Selecionar", command=self._sel_sam_gm,
                                        fg_color="#3A3A3A", hover_color="#454545", width=100)
        self.btn_sam_gm.pack(side="left", padx=5)
        self.lbl_sam_gm_status = ctk.CTkLabel(f_plan, text="Nenhum arquivo selecionado", text_color="gray")
        self.lbl_sam_gm_status.pack(side="left", padx=15)

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
        # A pasta From Itaipu fica no topo da aba: a regeneração e o passo 1
        # antigo usam a mesma.
        f_dir = ctk.CTkFrame(parent, fg_color="transparent")
        f_dir.pack(fill="x", padx=20, pady=(10, 0))
        ctk.CTkLabel(f_dir, text="Pasta (PDMs From Itaipu):", width=240, anchor="w").pack(side="left")
        ctk.CTkEntry(f_dir, textvariable=self.path_pdms_itaipu, width=280).pack(side="left", padx=5)
        ctk.CTkButton(f_dir, text="Buscar", width=80, command=lambda: self.path_pdms_itaipu.set(file_dialogs.ask_directory("pdm.pdms_itaipu", "pasta", titulo="Pasta de Origem dos PDMs"))).pack(side="left")

        # --- Regenerar as pastas a partir da planilha (2026-09-24) ---
        # Título e botão na MESMA linha, aqui e no passo 1: com a seção nova a
        # aba cresceu, e o console do log (que a regeneração enche) sumia da
        # janela. Medido por print numa janela de 960 px de altura.
        frm_regen = ctk.CTkFrame(parent, fg_color="#333333", corner_radius=8)
        frm_regen.pack(fill="x", padx=20, pady=6)
        cab_regen = ctk.CTkFrame(frm_regen, fg_color="transparent")
        cab_regen.pack(fill="x", padx=10, pady=(6, 0))
        ctk.CTkLabel(cab_regen, text="Regenerar as pastas a partir da planilha", font=("Roboto", 14, "bold")).pack(side="left")
        ctk.CTkButton(cab_regen, text="Executar: Regenerar as pastas", command=self._op1_regenerar,
                      fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"]).pack(side="right")
        ctk.CTkLabel(
            frm_regen, font=("Roboto", 11), text_color="gray", anchor="w",
            text=("Com a revisão no nome (PDM_1650_001 - ACUMULADOR - R2_formatado.xlsx); "
                  "a versão antiga vai para _versoes_antigas, nada é apagado."),
        ).pack(anchor="w", padx=10, pady=(0, 8))

        # --- SEÇÃO 1: Fatiar lista geral (From Itaipu), método antigo ---
        frm_from = ctk.CTkFrame(parent, fg_color="#333333", corner_radius=8)
        frm_from.pack(fill="x", padx=20, pady=6)
        cab_from = ctk.CTkFrame(frm_from, fg_color="transparent")
        cab_from.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(cab_from, text="1. Fatiar Arquivo Geral (From Itaipu)", font=("Roboto", 14, "bold")).pack(side="left")
        ctk.CTkLabel(cab_from, text="usa a planilha do painel de cima; só cria os PDMs que faltam na pasta",
                     font=("Roboto", 11), text_color="gray").pack(side="left", padx=10)
        ctk.CTkButton(cab_from, text="Executar: Criar PDMs From Itaipu", command=self._op1_from_itaipu, fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"]).pack(side="right")

        # --- SEÇÃO 2: Formatar PDMs (Modificados) ---
        frm_mod = ctk.CTkFrame(parent, fg_color="#333333", corner_radius=8)
        frm_mod.pack(fill="x", padx=20, pady=6)
        ctk.CTkLabel(frm_mod, text="2. Formatar PDMs (Modificados)", font=("Roboto", 14, "bold")).pack(anchor="w", padx=10, pady=5)

        ctk.CTkLabel(frm_mod, text="Utiliza a 'Pasta (PDMs From Itaipu)' como base para leitura.", font=("Roboto", 11), text_color="gray").pack(anchor="w", padx=10)

        f_rad = ctk.CTkFrame(frm_mod, fg_color="transparent")
        f_rad.pack(fill="x", padx=10, pady=5)
        ctk.CTkRadioButton(f_rad, text="Lote (Todos os Novos)", variable=self.modo_proc, value="todos").pack(side="left", padx=10)
        ctk.CTkRadioButton(f_rad, text="Específico (Escolher 1 arquivo)", variable=self.modo_proc, value="especifico").pack(side="left", padx=10)

        ctk.CTkButton(frm_mod, text="Executar: Criar PDMs Modificados", command=self._op1_modificados, fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"]).pack(pady=10)

        # --- Traducao para ingles (2026-08-28) ---
        # Fica nesta aba porque produz uma pasta de PDMs, como os dois botoes
        # acima -- e nao na aba 2, que so CONSOME o que existe.
        ctk.CTkLabel(frm_mod, text="3. Traduzir para inglês (ficha em inglês)",
                     font=("Roboto", 14, "bold")).pack(anchor="w", padx=10, pady=(15, 5))
        ctk.CTkLabel(
            frm_mod, font=("Roboto", 11), text_color="gray", justify="left", anchor="w",
            text=("Lê a 'Pasta dos PDMs Modificados' e grava a versão em inglês noutra pasta.\n"
                  "Rode uma vez; o resultado fica em cache e o glossário editável "
                  "(_GLOSSARIO_PT_EN.txt) corrige termo técnico de vez."),
        ).pack(anchor="w", padx=10)

        f_en = ctk.CTkFrame(frm_mod, fg_color="transparent")
        f_en.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f_en, text="Pasta dos PDMs Modificados (EN):", width=240, anchor="w").pack(side="left")
        ctk.CTkEntry(f_en, textvariable=self.caminho_destino_en, width=280).pack(side="left", padx=5)
        ctk.CTkButton(f_en, text="Buscar", width=80,
                      command=lambda: self.caminho_destino_en.set(
                          file_dialogs.ask_directory("pdm.pdms_modificados_en", "pasta",
                                                     titulo="Pasta dos PDMs Modificados em INGLÊS"))
                      ).pack(side="left")

        ctk.CTkButton(frm_mod, text="Executar: Traduzir PDMs Modificados para inglês",
                      command=self._op1_traduzir, fg_color=COLORS["primary"],
                      hover_color=COLORS["primary_hover"]).pack(pady=10)

    def _build_tab2(self, parent):
        # --- SEÇÃO 1: Configuração de Arquivos e Pastas ---
        frm_files = ctk.CTkFrame(parent, fg_color="#333333", corner_radius=8)
        frm_files.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(frm_files, text="Configuração das Fichas PMIB", font=("Roboto", 14, "bold")).pack(anchor="w", padx=10, pady=5)

        # FONTE DAS PERGUNTAS (2026-09-24). A planilha de PDMs é a padrão: a
        # ficha sai da revisão vigente, sem pasta intermediária para manter. A
        # pasta continua como método antigo, e é por ela que sai a ficha em
        # inglês, que usa os PDMs traduzidos.
        f_fonte = ctk.CTkFrame(frm_files, fg_color="transparent")
        f_fonte.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(f_fonte, text="Fonte das características:", width=240, anchor="w").pack(side="left")
        ctk.CTkRadioButton(f_fonte, text="Planilha de PDMs", variable=self.fonte_perguntas,
                           value="planilha").pack(side="left", padx=10)
        ctk.CTkRadioButton(f_fonte, text="Pasta de PDMs Modificados (método antigo)",
                           variable=self.fonte_perguntas, value="pasta").pack(side="left", padx=10)

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

        # IDIOMA DA FICHA (2026-08-28). Explicito, e nao deduzido do nome do
        # arquivo do template: deduzir quebraria em silencio no dia em que
        # alguem renomeasse o template, e ficha montada com as perguntas no
        # idioma errado nao se denuncia sozinha.
        f_idioma = ctk.CTkFrame(frm_files, fg_color="transparent")
        f_idioma.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(f_idioma, text="Idioma da ficha:", width=240, anchor="w").pack(side="left")
        ctk.CTkRadioButton(f_idioma, text="Português", variable=self.idioma_ficha,
                           value="pt").pack(side="left", padx=10)
        ctk.CTkRadioButton(f_idioma, text="English", variable=self.idioma_ficha,
                           value="en").pack(side="left", padx=10)
        ctk.CTkLabel(f_idioma, text="(English usa a pasta de PDMs traduzidos)",
                     font=("Roboto", 11), text_color="gray").pack(side="left", padx=10)

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
        if not lista: return messagebox.showwarning("Aviso", "Por favor, selecione a Planilha de PDMs no painel de cima.")
        if not pasta_alvo: return messagebox.showwarning("Aviso", "Por favor, selecione a Pasta (PDMs From Itaipu) na tela.")

        # Thread para não congelar a tela
        def task():
            self._safe_log(f"Fatiando a lista geral: {os.path.basename(lista)}...")
            res = backends.pdm_backend.pdms_fromItaipu_lista_geral(
                lista, pasta_alvo, log_callback=self._safe_log,
                retry_lock=self.perguntar_retry_excel,
            )
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
                for arq in backends.pdm_backend.listar_arquivos_excel(origem):
                    tbl = backends.pdm_backend.processar_arquivo_pdm(arq)
                    if tbl is not None:
                        ok, msg = backends.pdm_backend.salvar_tabela_formatada(
                            tbl, arq, self.caminho_destino.get(),
                            retry_lock=self.perguntar_retry_excel,
                        )
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
                    tbl = backends.pdm_backend.processar_arquivo_pdm(arq)
                    if tbl is not None:
                        ok, msg = backends.pdm_backend.salvar_tabela_formatada(
                            tbl, arq, self.caminho_destino.get(), force=True,
                            retry_lock=self.perguntar_retry_excel,
                        )
                        self._safe_log(msg)
                        self.after(0, lambda: messagebox.showinfo("Status", msg))
                threading.Thread(target=task_esp, daemon=True).start()
            else:
                self.log("Seleção de arquivo específico cancelada.")

    def _op1_traduzir(self):
        """Traduz a pasta de PDMs Modificados para inglês.

        Roda em thread como as demais operações da tela; o serviço devolve as
        linhas de log num generator, mesmo contrato do resto do projeto.
        """
        origem = self.caminho_destino.get()
        destino = self.caminho_destino_en.get()
        if not origem:
            return messagebox.showwarning("Aviso", "Selecione a 'Pasta dos PDMs Modificados' primeiro.")
        if not destino:
            return messagebox.showwarning(
                "Aviso", "Selecione a pasta de destino dos PDMs Modificados em INGLÊS.")
        if os.path.abspath(origem) == os.path.abspath(destino):
            return messagebox.showerror(
                "Erro", "A pasta de destino não pode ser a mesma da origem.\n"
                        "Os arquivos em português seriam sobrescritos.")

        def task():
            try:
                from sigft.services import traducao_pdm
                self._safe_log("Traduzindo PDMs Modificados para inglês...")
                # SEM `api_key=`: `get_llm` resolve a chave do provedor que o
                # usuário escolheu para `traduzir_pdm` em "Modelos de IA"
                # (`config.CHAVE_POR_PROVIDER`, mesmo `.env`/`api_config.json`).
                # Passar `get_key("GEMINI")` aqui é o padrão legado dos 5
                # módulos migrados no CP 3.1, e mandaria a chave do Gemini para
                # o OpenRouter de quem tivesse escolhido OpenRouter.
                for linha in traducao_pdm.traduzir_pasta(
                        origem, destino,
                        traduzir=traducao_pdm.motor_padrao(
                            callbacks=from_legacy(callback_log=self._safe_log)),
                        retry_lock=self.perguntar_retry_excel):
                    self._safe_log(linha)
                self.after(0, lambda: messagebox.showinfo(
                    "Tradução", f"Tradução concluída.\n\nPasta: {destino}"))
            except Exception as e:
                # `motivo=str(e)` e nao `{e}` dentro do lambda: o Python APAGA
                # o nome `e` ao sair do `except`, e o lambda so roda depois --
                # viraria NameError na hora de mostrar o erro, justamente
                # quando alguma coisa ja deu errado. E o mesmo defeito que o
                # `pyflakes` acusa como conhecido no resto do app.
                motivo = str(e)
                self._safe_log(f"ERRO na tradução: {motivo}")
                self.after(0, lambda: messagebox.showerror(
                    "Erro", f"Falha na tradução:\n{motivo}"))

        threading.Thread(target=task, daemon=True).start()

    def _op1_regenerar(self):
        """Regenera as pastas a partir da planilha. A validação de verdade (as
        duas pastas iguais, a planilha no formato certo) é do serviço: a tela só
        confere que os campos foram preenchidos."""
        planilha = self.path_sam_gm.get()
        pasta_modificados = self.caminho_destino.get()
        pasta_itaipu = self.path_pdms_itaipu.get()
        if not planilha:
            return messagebox.showwarning("Aviso", "Selecione a planilha de PDMs no painel de cima.")
        if not pasta_modificados:
            return messagebox.showwarning("Aviso", "Selecione a 'Pasta dos PDMs Modificados' no painel de cima.")

        def task():
            try:
                from sigft.services import pdm_regeneracao
                self._safe_log("Regenerando as pastas a partir da planilha de PDMs...")
                resumo = pdm_regeneracao.regenerar_pastas(
                    planilha, pasta_modificados, pasta_itaipu or None,
                    log_callback=self._safe_log, retry_lock=self.perguntar_retry_excel)
                self._safe_log(resumo)
                self.after(0, lambda: messagebox.showinfo("Regeneração", resumo))
            except Exception as e:
                # `motivo` e não `{e}` dentro do lambda: o Python apaga `e` ao
                # sair do `except`, e o lambda só roda depois.
                motivo = str(e)
                self._safe_log(f"ERRO na regeneração: {motivo}")
                self.after(0, lambda: messagebox.showerror("Erro", f"A regeneração não foi feita:\n{motivo}"))

        threading.Thread(target=task, daemon=True).start()

    def _op2_executar(self):
        # A FONTE das perguntas (2026-09-24): a planilha de PDMs, ou a pasta de
        # PDMs Modificados (método antigo). Em inglês, só a pasta: as perguntas
        # coladas têm de ser as traduzidas. Ver `_op1_traduzir`.
        da_planilha = self.fonte_perguntas.get() == "planilha"
        em_ingles = self.idioma_ficha.get() == "en"
        planilha = self.path_sam_gm.get()
        pasta_modificados = None
        if da_planilha:
            if em_ingles:
                return messagebox.showwarning(
                    "Aviso", "A ficha em inglês usa a pasta traduzida. Escolha a fonte "
                             "'Pasta de PDMs Modificados' ou o idioma Português.")
            if not planilha:
                return messagebox.showwarning("Aviso", "Selecione a planilha de PDMs no painel de cima.")
        else:
            pasta_modificados = (self.caminho_destino_en.get() if em_ingles
                                 else self.caminho_destino.get())
            if not pasta_modificados:
                if em_ingles:
                    return messagebox.showwarning(
                        "Aviso", "Idioma da ficha = English, mas a 'Pasta dos PDMs Modificados "
                                 "(EN)' não foi selecionada.\n\nEla fica na aba 1, no passo 3 "
                                 "(Traduzir para inglês).")
                return messagebox.showwarning("Aviso", "Selecione a 'Pasta dos PDMs Modificados' primeiro.")

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

                # [CP 7.2] Popup montado a mao -> SelecaoMultiplaDialog.
                # `modal=True` preserva o `transient` + `grab_set` que ele ja
                # usava: diferente dos dialogos de pausa, este PERGUNTA e a tela
                # nao tem o que fazer sem a resposta -- o `wait_window` logo
                # abaixo depende disso.
                def confirm_sel(escolhidos):
                    nonlocal lista_sel
                    lista_sel = escolhidos

                sel_win = app_dialogs.SelecaoMultiplaDialog(
                    self,
                    itens=codigos,
                    titulo="Selecione os Códigos PMIB",
                    instrucao="Selecione um ou mais códigos:",
                    geometria="400x500",
                    fonte_instrucao=("Roboto", 14),
                    fonte_lista=("Consolas", 11),
                    modal=True,
                    ao_confirmar=confirm_sel,
                )
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
            catalogo = None
            if da_planilha:
                # Antes de criar qualquer subpasta: planilha ilegível para o
                # lote sem deixar pasta vazia para trás.
                self._safe_log("Lendo a planilha de PDMs...")
                try:
                    catalogo = pdm_catalogo.carregar(planilha)
                except Exception as e:
                    motivo = str(e)
                    self._safe_log(f"ERRO ao ler a planilha de PDMs: {motivo}")
                    self.after(0, lambda: messagebox.showerror(
                        "Erro", f"Não consegui ler a planilha de PDMs:\n{motivo}"))
                    return

            self._safe_log(f"Preparando diretórios (Modo: {'Com Pastas' if criar_pastas else 'Apenas Planilhas'})...")
            dados_pastas, msg = backends.pdm_backend.processar_pastas_fichas(status_pmib, destino_fichas, lista_sel, criar_subpastas=criar_pastas)
            self._safe_log(msg)

            if not dados_pastas:
                self.after(0, lambda: messagebox.showinfo("Aviso", "Nenhum código foi processado."))
                return

            if da_planilha:
                msg_res, logs = backends.pdm_backend.aplicar_templates_fichas_da_planilha(
                    dados_pastas, catalogo, template,
                    log_callback=self._safe_log,
                    retry_lock=self.perguntar_retry_excel,
                )
            else:
                self._safe_log("Injetando os dados dos PDMs no Template (a partir da linha 79)...")
                # O idioma vai para o serviço, e não o nome da aba: quem sabe
                # como a aba se chama em inglês é o serviço
                # (`NOME_DA_ABA_EM_INGLES`). A tela só repassa a escolha.
                msg_res, logs = backends.pdm_backend.aplicar_templates_fichas(
                    dados_pastas, pasta_modificados, template,
                    log_callback=self._safe_log,
                    retry_lock=self.perguntar_retry_excel,
                    idioma=self.idioma_ficha.get(),
                )
            self._safe_log(msg_res)

            self._safe_log(">>> Processo de criação de fichas finalizado!")
            self.after(0, lambda: messagebox.showinfo(
                "Fim", f"Processo de criação de fichas finalizado.\n\n{msg_res}"))

        threading.Thread(target=task, daemon=True).start()

    def _op3_executar(self):
        pasta_limpeza = self.path_clean_dir.get()
        if not pasta_limpeza:
            return messagebox.showwarning("Aviso", "Por favor, selecione a pasta para limpeza primeiro.")

        def task():
            self._safe_log(f"Iniciando varredura por duplicados em: {pasta_limpeza}...")
            res = backends.pdm_backend.logica_excluir_duplicados(pasta_limpeza, log_callback=self._safe_log)
            self._safe_log(res)
            self.after(0, lambda: messagebox.showinfo("Resultado", "Limpeza concluída."))

        threading.Thread(target=task, daemon=True).start()

