"""Tela "Correção de PDM" — trocar ou atualizar o PDM sem perder as características.

Trocar o PDM de uma ficha faz o portal apagar TODAS as características
técnicas, inclusive as que o PDM novo também tem. Esta tela fotografa antes,
troca, e repõe o que couber — e lista, em vez de sumir calado, o que não voltou.

A tela é FINA de propósito: a leitura da planilha, a prévia e as ações em massa
estão em `services/correcao_pdm_planilha.py`, e o fluxo do portal em
`services/correcao_pdm.py`. Aqui só ficam widgets e a thread (princípio 2 da
arquitetura: UI nunca contém regra de negócio).

Plano em `docs/refatoracao/CORRECAO_PDM.md`.
"""
from __future__ import annotations

import threading
from tkinter import messagebox, ttk

from sigft.app import file_dialogs
from sigft.app.theme import COLORS
from sigft.app.views.janelas import JanelaEscolherPDM
from sigft.app.widgets import dialogs as app_dialogs
from sigft.app.widgets.espera import DialogosDeEspera
from sigft.core import pdm_catalogo
from sigft.services import correcao_pdm as correcao_svc
from sigft.services import correcao_pdm_planilha as planilha_svc

import customtkinter as ctk


URL_LISTA_DE_FICHAS = "https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList"

COLUNAS = (
    ("Ficha", 150),
    ("Descrição", 250),
    ("PDM atual", 260),
    ("PDM novo", 260),
    ("Prévia", 230),
)


class ModuloCorrecaoPDM(DialogosDeEspera, ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        self.fichas = []          # list[FichaParaCorrigir]
        self.catalogo = None
        self.automacao = None

        self.var_apagar_vazias = ctk.BooleanVar(value=True)
        self.var_conferir = ctk.BooleanVar(value=False)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=3)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, height=50, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(header, text="Correção de PDM", font=("Roboto", 24, "bold"),
                     text_color=COLORS["text_white"]).pack(side="left")
        ctk.CTkLabel(header, text="  troca o PDM da ficha e repõe as "
                                  "características que o PDM novo também tem",
                     text_color="gray").pack(side="left")

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)

        self.console = ctk.CTkTextbox(self, height=150, font=("Consolas", 12))
        self.console.grid(row=2, column=0, sticky="ew", padx=20, pady=10)

        self._build_ui()

    # -- log ---------------------------------------------------------------
    def log(self, txt):
        self.after(0, self._log_thread_safe, txt)

    def _log_thread_safe(self, txt):
        self.console.insert("end", f"> {txt}\n")
        self.console.see("end")

    # -- montagem ----------------------------------------------------------
    def _build_ui(self):
        frm_arquivos = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8)
        frm_arquivos.pack(fill="x", pady=(0, 10))

        linha = ctk.CTkFrame(frm_arquivos, fg_color="transparent")
        linha.pack(fill="x", padx=15, pady=12)

        ctk.CTkButton(linha, text="Selecionar _STATUS_PMIB", width=200,
                      command=self._sel_status, fg_color="#3A3A3A",
                      hover_color="#454545", font=("Roboto", 12)).pack(side="left")
        self.lbl_status = ctk.CTkLabel(linha, text="Não selecionado", text_color="gray")
        self.lbl_status.pack(side="left", padx=10)

        ctk.CTkButton(linha, text="Planilha de PDMs (opcional)", width=210,
                      command=self._sel_catalogo, fg_color="#3A3A3A",
                      hover_color="#454545", font=("Roboto", 12)).pack(side="left", padx=(20, 0))
        self.lbl_catalogo = ctk.CTkLabel(linha, text="sem catálogo", text_color="gray")
        self.lbl_catalogo.pack(side="left", padx=10)

        # --- ações em massa ---
        frm_acoes = ctk.CTkFrame(self.content, fg_color="transparent")
        frm_acoes.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(frm_acoes, text="Nas fichas selecionadas:",
                     font=("Roboto", 12, "bold")).pack(side="left", padx=(0, 10))
        ctk.CTkButton(frm_acoes, text="Só atualizar a revisão", width=170,
                      command=self._acao_so_revisao,
                      fg_color=COLORS["accent"]).pack(side="left", padx=4)
        ctk.CTkButton(frm_acoes, text="Escolher PDM...", width=140,
                      command=self._acao_escolher_pdm,
                      fg_color="#3A3A3A", hover_color="#454545").pack(side="left", padx=4)
        ctk.CTkButton(frm_acoes, text="Limpar", width=90,
                      command=self._acao_limpar,
                      fg_color="#3A3A3A", hover_color="#454545").pack(side="left", padx=4)

        # --- a tabela ---
        frm_tabela = ctk.CTkFrame(self.content)
        frm_tabela.pack(fill="both", expand=True)
        barra = ttk.Scrollbar(frm_tabela, orient="vertical")
        self.tabela = ttk.Treeview(frm_tabela, columns=[c for c, _ in COLUNAS],
                                   show="headings", yscrollcommand=barra.set,
                                   selectmode="extended")
        barra.config(command=self.tabela.yview)
        barra.pack(side="right", fill="y")
        self.tabela.pack(side="left", fill="both", expand=True)
        for coluna, largura in COLUNAS:
            self.tabela.heading(coluna, text=coluna)
            self.tabela.column(coluna, width=largura, anchor="w")

        # --- rodapé ---
        frm_rodape = ctk.CTkFrame(self.content, fg_color="transparent")
        frm_rodape.pack(fill="x", pady=(10, 0))

        ctk.CTkSwitch(frm_rodape, text="Apagar as que ficarem em branco",
                      variable=self.var_apagar_vazias,
                      progress_color=COLORS["primary"]).pack(side="left")
        ctk.CTkSwitch(frm_rodape, text="Conferir cada ficha antes de salvar",
                      variable=self.var_conferir,
                      progress_color=COLORS["primary"]).pack(side="left", padx=20)

        self.btn_rodar = ctk.CTkButton(frm_rodape, text="INICIAR CORREÇÃO",
                                       width=190, command=self._rodar,
                                       fg_color=COLORS["accent"],
                                       font=("Roboto", 13, "bold"))
        self.btn_rodar.pack(side="right")
        ctk.CTkButton(frm_rodape, text="Parar", width=90, command=self._parar,
                      fg_color="#8B2E2E", hover_color="#A03838").pack(side="right", padx=8)

        self.progress = ctk.CTkProgressBar(self.content)
        self.progress.set(0)
        self.progress.pack(fill="x", pady=(8, 0))

    # -- arquivos ----------------------------------------------------------
    def _sel_status(self):
        caminho = file_dialogs.ask_open_file(
            "correcao_pdm.status_pmib", "excel",
            titulo="Selecione o _STATUS_PMIB",
            filetypes=[("Excel", "*.xlsx *.xlsm")])
        if not caminho:
            return
        try:
            self.fichas = planilha_svc.ler_fichas_do_arquivo(caminho)
        except Exception as erro:  # noqa: BLE001 -- planilha do usuário
            messagebox.showerror("Erro", f"Não consegui ler a planilha:\n{erro}")
            return

        self.lbl_status.configure(text=f"{len(self.fichas)} ficha(s)",
                                  text_color=COLORS["accent"])
        if not self.fichas:
            self.log("Nenhuma ficha encontrada. Confira se a aba é a "
                     "'Lista de Materiais' e se há a coluna CÓDIGO PMIB.")
        self._redesenhar()

    def _sel_catalogo(self):
        caminho = file_dialogs.ask_open_file(
            "correcao_pdm.sam_gm", "excel",
            titulo="Selecione a planilha de PDMs",
            filetypes=[("Excel", "*.xlsx *.xlsm")])
        if not caminho:
            return
        try:
            self.catalogo = pdm_catalogo.carregar(caminho)
        except Exception as erro:  # noqa: BLE001
            messagebox.showerror("Erro", f"Não consegui ler o catálogo:\n{erro}")
            return
        self.lbl_catalogo.configure(text=f"{len(self.catalogo)} PDMs",
                                    text_color=COLORS["accent"])
        self._redesenhar()

    # -- tabela ------------------------------------------------------------
    def _redesenhar(self):
        self.tabela.delete(*self.tabela.get_children())
        for posicao, ficha in enumerate(self.fichas):
            self.tabela.insert(
                "", "end", iid=str(posicao),
                values=(ficha.pmib, ficha.descricao, ficha.pdm_atual,
                        ficha.pdm_novo,
                        planilha_svc.previa(self.catalogo, ficha.pdm_atual,
                                            ficha.pdm_novo)))

    def _selecionadas(self):
        """As fichas marcadas, ou TODAS quando não há seleção.

        "Nenhuma selecionada" quase sempre quer dizer "a planilha inteira" --
        e obrigar a selecionar 25 linhas para aplicar a ação que resolve as 25
        seria o oposto do "um clique" que ela existe para dar.
        """
        marcadas = self.tabela.selection()
        if not marcadas:
            return list(self.fichas)
        return [self.fichas[int(x)] for x in marcadas]

    def _acao_so_revisao(self):
        alvo = self._selecionadas()
        sem_pdm = 0
        for ficha in alvo:
            codigo = planilha_svc.so_a_revisao(ficha.pdm_atual)
            if not codigo:
                sem_pdm += 1
                continue
            ficha.pdm_novo = codigo
        self._redesenhar()
        self.log(f"Só atualizar a revisão: {len(alvo) - sem_pdm} ficha(s).")
        if sem_pdm:
            self.log(f"   {sem_pdm} ficha(s) sem PDM na planilha ficaram de "
                     f"fora: não há código para copiar.")

    def _acao_escolher_pdm(self):
        if self.catalogo is None:
            messagebox.showinfo(
                "Catálogo",
                "Selecione antes a planilha de PDMs: é dela que sai a busca.")
            return
        alvo = self._selecionadas()
        if not alvo:
            return
        janela = JanelaEscolherPDM(self, self.catalogo)
        self.wait_window(janela)
        if janela.escolha is None:
            return
        for ficha in alvo:
            ficha.pdm_novo = janela.escolha.completo
        self._redesenhar()
        self.log(f"{janela.escolha.completo} aplicado a {len(alvo)} ficha(s).")

    def _acao_limpar(self):
        for ficha in self._selecionadas():
            ficha.pdm_novo = ""
        self._redesenhar()

    # -- a rodada ----------------------------------------------------------
    def _rodar(self):
        lote = planilha_svc.lote(self.fichas)
        if not lote:
            messagebox.showinfo(
                "Nada a fazer",
                "Nenhuma ficha tem PDM novo. Use 'Só atualizar a revisão' ou "
                "'Escolher PDM...' antes.")
            return
        if not messagebox.askyesno(
                "Confirmar",
                f"{len(lote)} ficha(s) vão ter o PDM trocado no portal.\n\n"
                "O portal apaga as características técnicas na troca. O robô "
                "fotografa antes e repõe o que couber, e o que não voltar sai "
                "no relatório.\n\nSeguir?"):
            return
        self.btn_rodar.configure(state="disabled")
        threading.Thread(target=self._worker, args=(lote,), daemon=True).start()

    def _parar(self):
        if self.automacao:
            self.automacao.solicitar_parada()
            self.log("Parada pedida. Termino a ficha atual e paro.")

    def _worker(self, lote):
        self.automacao = correcao_svc.AutomacaoCorrecaoPDM()
        try:
            self.automacao.iniciar()
            self.automacao.abrir_portal(URL_LISTA_DE_FICHAS)
            self.pausar_e_esperar(app_dialogs.MSG_LOGIN_NOVA_FICHA)

            resultados = correcao_svc.corrigir_lote(
                self.automacao.portal, lote,
                callback_log=self.log,
                callback_pause=self._pausa_de_conferencia if self.var_conferir.get() else None,
                callback_progress=self._progresso,
                apagar_vazias=self.var_apagar_vazias.get())

            for linha in correcao_svc.relatorio_do_lote(resultados):
                self.log(linha)
            self.after(0, self._oferecer_relatorio, resultados)
        except Exception as erro:  # noqa: BLE001 -- o worker não pode morrer calado
            self.log(f"[Erro] {type(erro).__name__}: {erro}")
        finally:
            self.automacao.fechar()
            self.after(0, lambda: self.btn_rodar.configure(state="normal"))

    def _progresso(self, atual, total, item=None):
        self.after(0, self.progress.set, (atual / total) if total else 0)

    def _pausa_de_conferencia(self, pmib):
        self.pausar_e_esperar(
            f"Confira a ficha {pmib} no portal antes de salvar.")

    def _oferecer_relatorio(self, resultados):
        """Salva o relatório num arquivo, se o usuário quiser.

        No console ele rola e some; a lista do que NÃO voltou é justamente o
        que a pessoa vai usar para preencher à mão.
        """
        if not messagebox.askyesno("Relatório", "Salvar o relatório num arquivo?"):
            return
        caminho = file_dialogs.ask_save_file(
            "correcao_pdm.relatorio", "texto", titulo="Salvar relatorio",
            defaultextension=".txt", filetypes=[("Texto", "*.txt")])
        if not caminho:
            return
        try:
            with open(caminho, "w", encoding="utf-8") as arquivo:
                arquivo.write("\n".join(correcao_svc.relatorio_do_lote(resultados)))
        except OSError as erro:
            messagebox.showerror("Erro", f"Não consegui salvar:\n{erro}")
            return
        self.log(f"Relatório salvo em {caminho}")
