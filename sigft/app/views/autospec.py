"""Tela "AutoSpec AI" — Checkpoint 7.3 (Fase 7 do plano).

Preenche as especificações técnicas da ficha a partir de manuais e datasheets,
com IA. Inclui a seção de *Conferência de documentos*, que abre no navegador os
documentos que a IA marcou como duvidosos.

⚠️ Módulo da frente do Rafael (ver `docs/refatoracao/TRABALHO_PARALELO.md`).
A lógica da conferência vive em `sigft/services/autospec_conferencia.py` —
aqui só há widget, que foi o combinado justamente para este checkpoint só
precisar mover tela.
"""
from __future__ import annotations

import os
import threading
import webbrowser
from tkinter import messagebox

from sigft.app import backends, file_dialogs
from sigft.app.theme import COLORS
from sigft.services import autospec_conferencia as conferencia_txt

import customtkinter as ctk


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

        # --- SEÇÃO 5: CONFERÊNCIA DE DOCUMENTOS ---
        # Bloco AUTOCONTIDO (2026-08-13). Ver `_build_conferencia`.
        self._build_conferencia()

    # =========================================================================
    # CONFERÊNCIA DE DOCUMENTOS DUVIDOSOS  (frente AutoSpecAI — Rafael)
    # =========================================================================
    # ⚠️ LEIA ANTES DE MEXER — CP 7.3 (quebrar frontend.py em app/views/*.py)
    #
    # Este bloco é AUTOCONTIDO de propósito: são 6 métodos com prefixo
    # `_conferencia`/`_build_conferencia` + 7 atributos (`self.conferencia`,
    # `self.marcados_conf`, `self.frm_conf`, `self.lista_conf`,
    # `self.btn_conf`, `self.btn_conf_salvar`, `self.btn_conf_importar`).
    # Nada fora daqui depende deles, e eles não dependem de nada fora da
    # própria classe — a única amarração com o resto de `ModuloAutoSpec` é a
    # chamada de `_conferencia_mostrar` no fim do `_worker` e o
    # `_novo_core()`, que os dois workers compartilham.
    #
    # Para o CP 7.3: mova o bloco INTEIRO junto com `ModuloAutoSpec`, sem
    # tentar separar. A lógica já está fora daqui, em
    # `sigft/services/autospec_conferencia.py` — o que sobrou é só desenho de
    # widget, que é exatamente o que o checkpoint quer mover.
    #
    # POR QUE ESTA TELA EXISTE: o filtro anti-intruso (§4.3) tem três
    # destinos, e o do meio (`duvidoso`) não tem como ser resolvido por
    # código. Numa ficha real entrou uma camiseta da Minnie do site do Target
    # porque a URL continha o código do material; no mesmo lote um datasheet
    # legítimo foi barrado por não citar a marca no título. Indistinguíveis
    # para o programa, triviais para quem abre o link.
    #
    # POR QUE ELA NÃO SE ESCONDE MAIS (2026-08-17): a lista morria junto com
    # o aplicativo, e foi exatamente o que o Luan relatou — conferir 20 links
    # não cabe numa sessão. Salvar/importar `.txt` resolve, mas o botão de
    # IMPORTAR precisa estar visível ANTES de existir conferência nenhuma,
    # que é a situação de quem reabriu o app no dia seguinte. Por isso a
    # seção fica sempre montada, com um estado vazio no lugar da lista.
    # =========================================================================
    def _build_conferencia(self):
        """Monta a seção. Fica sempre visível: sem nada a conferir, mostra o
        estado vazio e só o botão de importar funciona."""
        self.conferencia = None
        self.marcados_conf = {}

        self.frm_conf = ctk.CTkFrame(
            self.content, fg_color="#2B2B2B", corner_radius=8,
            border_width=1, border_color=COLORS["warning"],
        )
        ctk.CTkLabel(
            self.frm_conf, text="5. Conferência de documentos",
            font=("Roboto", 14, "bold"), text_color=COLORS["warning"],
        ).pack(anchor="w", padx=15, pady=(10, 2))
        ctk.CTkLabel(
            self.frm_conf, justify="left", anchor="w", text_color="#CCCCCC",
            font=("Roboto", 11), wraplength=680,
            text=(
                "Estes documentos citam o fabricante OU o código, mas não os dois — "
                "podem ser o datasheet certo num distribuidor, ou a página de outro "
                "produto. Abra o link, confira, e marque os que são deste material.\n"
                "Não precisa terminar agora: salve em .txt e importe depois para "
                "continuar de onde parou."
            ),
        ).pack(anchor="w", padx=15, pady=(0, 8))

        self.lista_conf = ctk.CTkScrollableFrame(
            self.frm_conf, height=190, fg_color="#1E1E1E"
        )
        self.lista_conf.pack(fill="x", padx=15, pady=(0, 10))

        linha_btns = ctk.CTkFrame(self.frm_conf, fg_color="transparent")
        linha_btns.pack(fill="x", padx=20, pady=(0, 8))
        self.btn_conf_salvar = ctk.CTkButton(
            linha_btns, text="SALVAR CONFERÊNCIA (.txt)", height=32,
            command=self._conferencia_salvar, font=("Roboto", 12),
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
        )
        self.btn_conf_salvar.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.btn_conf_importar = ctk.CTkButton(
            linha_btns, text="IMPORTAR CONFERÊNCIA (.txt)", height=32,
            command=self._conferencia_importar, font=("Roboto", 12),
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
        )
        self.btn_conf_importar.pack(side="left", fill="x", expand=True, padx=(5, 0))

        self.btn_conf = ctk.CTkButton(
            self.frm_conf, text="PROCESSAR OS DOCUMENTOS MARCADOS",
            height=40, command=self._conferencia_processar,
            font=("Roboto", 13, "bold"),
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF",
        )
        self.btn_conf.pack(fill="x", padx=20, pady=(0, 15))
        self.frm_conf.pack(fill="x", pady=10)
        self._conferencia_mostrar(None)

    def _conferencia_mostrar(self, conferencia, marcados=None):
        """Preenche a lista. `marcados` vem do `.txt` importado — é o que faz
        a conferência retomada nascer com o que já tinha sido conferido."""
        self.conferencia = conferencia
        self.marcados_conf = {}
        for w in self.lista_conf.winfo_children():
            w.destroy()

        estado = "normal" if conferencia else "disabled"
        self.btn_conf.configure(state=estado)
        self.btn_conf_salvar.configure(state=estado)

        if not conferencia:
            ctk.CTkLabel(
                self.lista_conf, justify="left", anchor="w", text_color="gray",
                font=("Roboto", 11), wraplength=650,
                text=("Nenhuma conferência pendente.\n\n"
                      "Se você salvou uma conferência anterior em .txt, use "
                      "IMPORTAR CONFERÊNCIA para continuar de onde parou."),
            ).pack(anchor="w", padx=10, pady=10)
            return

        marcados = marcados or {}
        for i_pend, pendencia in enumerate(conferencia.pendencias):
            ctk.CTkLabel(
                self.lista_conf, text=f"📄 {pendencia.nome_curto}  —  {pendencia.material[:60]}",
                font=("Roboto", 12, "bold"), anchor="w", text_color=COLORS["accent"],
            ).pack(fill="x", padx=6, pady=(8, 2))

            for i_doc, doc in enumerate(pendencia.documentos):
                linha = ctk.CTkFrame(self.lista_conf, fg_color="transparent")
                linha.pack(fill="x", padx=6, pady=1)

                var = ctk.BooleanVar(value=bool(marcados.get((i_pend, i_doc))))
                self.marcados_conf[(i_pend, i_doc)] = var
                ctk.CTkCheckBox(
                    linha, text="", variable=var, width=24,
                    checkbox_width=18, checkbox_height=18,
                ).pack(side="left")

                url = doc.get("url", "")
                titulo = (doc.get("title") or url)[:70]
                # O link é um botão porque CTkLabel não tem clique nativo; o
                # visual de link é feito à mão.
                ctk.CTkButton(
                    linha, text=f"🔗 {titulo}", anchor="w", height=22,
                    fg_color="transparent", hover_color="#333333",
                    text_color="#6FB3FF", font=("Roboto", 11, "underline"),
                    command=lambda u=url: webbrowser.open(u),
                ).pack(side="left", fill="x", expand=True)

    def _conferencia_salvar(self, automatico=False):
        """Grava a aba num `.txt` na pasta do `_STATUS_PMIB`.

        `automatico=True` é a gravação que acontece sozinha quando o lote
        termina. O botão só protege quem lembra de clicar nele, e o relato
        que originou isto foi de alguém que precisou fechar o aplicativo no
        meio da conferência.
        """
        if not self.conferencia:
            if not automatico:
                messagebox.showinfo("Conferência", "Não há conferência para salvar.")
            return None
        marcados = {chave: var.get() for chave, var in self.marcados_conf.items()}
        try:
            caminho = conferencia_txt.salvar_txt(
                self.conferencia, self.status_pmib_path, marcados
            )
        except Exception as e:
            self.log(f"Nao consegui salvar o .txt da conferencia: {e}")
            if not automatico:
                messagebox.showerror("Conferência", f"Não consegui salvar:\n{e}")
            return None
        self.log(f"Conferencia salva em: {caminho}")
        if not automatico:
            messagebox.showinfo("Conferência", f"Conferência salva em:\n{caminho}")
        return caminho

    def _conferencia_importar(self):
        """Retoma uma conferência salva — inclusive de outra sessão do app."""
        caminho = file_dialogs.ask_open_file(
            "autospec.conferencia", "txt",
            titulo="Selecione o .txt da conferência",
            filetypes=[("Texto", "*.txt"), ("Todos", "*.*")],
        )
        if not caminho:
            return
        try:
            conferencia, marcados = conferencia_txt.carregar_txt(caminho)
        except Exception as e:
            return messagebox.showerror("Conferência", f"Não consegui ler o arquivo:\n{e}")
        if not conferencia:
            return messagebox.showwarning(
                "Conferência",
                "Não encontrei nenhum documento neste arquivo.\n\n"
                "Ele precisa ter as linhas 'FICHA:' e os links marcados com [ ] ou [x].",
            )

        self._conferencia_mostrar(conferencia, marcados)
        self.log(f"Conferencia importada de: {caminho}")
        self.log(f" -> {conferencia.total_documentos} documento(s) em "
                 f"{len(conferencia.pendencias)} ficha(s).")
        ausentes = conferencia_txt.fichas_ausentes(conferencia)
        for ficha in ausentes:
            self.log(f" -> AVISO: nao encontrei a ficha {ficha}")
        if ausentes:
            messagebox.showwarning(
                "Conferência",
                f"{len(ausentes)} ficha(s) não estão mais no caminho gravado no "
                "arquivo.\nElas vão falhar no processamento — veja o console.",
            )

    def _conferencia_processar(self):
        if not self.conferencia:
            return
        # Guard que vale sobretudo para a conferência IMPORTADA: quem reabriu
        # o aplicativo tem a lista de links, mas ainda não escolheu o
        # _STATUS_PMIB — e a 2ª passada lê a planilha de status ficha a ficha.
        if not self.status_pmib_path:
            return messagebox.showerror(
                "Erro", "Selecione o arquivo _STATUS_PMIB (seção 1) antes de "
                        "processar a conferência."
            )
        marcados = {chave: var.get() for chave, var in self.marcados_conf.items()}
        selecao = self.conferencia.selecao_por_ficha(marcados)
        if not selecao:
            messagebox.showinfo(
                "Conferência", "Marque ao menos um documento antes de processar."
            )
            return
        self.btn_conf.configure(state="disabled")
        threading.Thread(target=self._conferencia_worker, args=(selecao,)).start()

    def _conferencia_worker(self, selecao):
        try:
            core = self._novo_core()
            core.conferencia = self.conferencia
            for msg in core.processar_conferidos(selecao, self.status_pmib_path):
                self.log(msg)
            self.log("Conferência processada!")
            # A lista FICA na tela: o que não foi marcado continua duvidoso, e
            # limpar aqui repetiria a perda que o .txt veio consertar.
            self.log("Os documentos nao marcados continuam na lista. Se for parar "
                     "agora, use SALVAR CONFERENCIA (.txt).")
            messagebox.showinfo("Sucesso", "Documentos conferidos processados.")
        except Exception as e:
            self.log(f"ERRO na conferência: {e}")
        finally:
            self.btn_conf.configure(state="normal")

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

    def _novo_core(self):
        """Uma instância do backend com as chaves da tela Home.

        Extraído de `_worker` em 2026-08-13 porque a conferência precisa da
        MESMA construção — duplicar as 4 chaves em dois lugares é como uma
        delas fica para trás quando um provedor novo entra.
        """
        return backends.autospec_backend.AutoSpecCore(
            gemini_key=self.controller.get_key("GEMINI"),
            llama_key=self.controller.get_key("LLAMA"),
            google_search_key=self.controller.get_key("GOOGLE_SEARCH"),
            google_cse_id=self.controller.get_key("GOOGLE_CSE")
        )

    def _worker(self):
        try:
            core = self._novo_core()
            for msg in core.process_queue(self.queue, self.status_pmib_path):
                self.log(msg)

            self.log("Processamento Completo!")
            messagebox.showinfo("Sucesso", "Todas as tarefas da fila foram processadas.")
            self.queue = []
            self.update_queue_ui()  # Nota: idealmente via callback seguro, mas ctk aguenta na maioria dos casos
            # Conferência humana: só lista se sobrou dúvida (2026-08-13).
            conferencia = getattr(core, "conferencia", None)
            self._conferencia_mostrar(conferencia)
            # Salva sozinho (2026-08-17). A ordem importa: `_mostrar` acima
            # zera as marcações, então o .txt sai coerente com a lista nova, e
            # não com as marcas do lote anterior.
            if conferencia:
                self._conferencia_salvar(automatico=True)

        except Exception as e:
            self.log(f"ERRO FATAL: {e}")
        finally:
            self.btn_run.configure(state="normal")

