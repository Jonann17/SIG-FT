"""Tela "Gerenciador PMIB" — Checkpoint 7.3 (Fase 7 do plano).

Varre a pasta raiz das fichas, cruza com a base de dados API e a planilha
mestra, e mantém o `_STATUS_PMIB` em dia.
"""
from __future__ import annotations

import os
import pathlib
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox

import pandas as pd

from sigft.app import backends, file_dialogs
from sigft.core import prefs
# [2026-09-03] Chave sob a qual o caminho do mapeamento fica lembrado --
# a Home lê por ela para montar o mural de atividades.
from sigft.core.prefs import CHAVE_MAPEAMENTO
from sigft.app.theme import COLORS

# [2026-10-05, T7] A caixa "Gerar painel ao terminar", lembrada entre aberturas.
OPCAO_GERAR_PAINEL = "pmib_manager.gerar_painel"

import customtkinter as ctk


# =============================================================================
# MÓDULO 11: PMIB MANAGER (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloPMIBManager(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Variáveis visuais dos caminhos
        self.path_api = ctk.StringVar()
        self.path_root = ctk.StringVar()
        self.path_master = ctk.StringVar()
        self.path_autorizados = ctk.StringVar()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)  # Inputs (Sem expansão)
        self.grid_rowconfigure(2, weight=0)  # Barra de Progresso (Sem expansão)
        self.grid_rowconfigure(3, weight=1)  # Console (Puxa todo o resto do espaço)

        # Header
        header = ctk.CTkFrame(self, height=50, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(header, text="Gestão de Sobressalentes", font=("Roboto", 24, "bold"), text_color=COLORS["text_white"]).pack(side="left")

        # Content (Bloco 1 - Inputs)
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=20, pady=5)

        # Barra de Progresso Centralizada (Bloco 1.5)
        self.progress_bar = ctk.CTkProgressBar(self, width=600, height=12, progress_color=COLORS["primary"])
        self.progress_bar.grid(row=2, column=0, pady=(5, 5))
        self.progress_bar.set(0)  # Inicia zerada

        # Console (Bloco 2 - Output)
        self.console = ctk.CTkTextbox(self, font=("Consolas", 12))
        self.console.grid(row=3, column=0, sticky="nsew", padx=20, pady=(5, 20))

        self._build_ui()

    def log(self, txt):
        self.console.insert("end", f"> {txt}\n"); self.console.see("end")

    def _build_ui(self):
        frm_main = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8)
        frm_main.pack(fill="x", pady=10)

        ctk.CTkLabel(frm_main, text="Configuração de Gestão de Fichas PMIB", font=("Roboto", 16, "bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=15, pady=(15, 5))

        # Input API (Estilo Arquivo: Botão + Label)
        f_api = ctk.CTkFrame(frm_main, fg_color="transparent")
        f_api.pack(fill="x", padx=15, pady=8)
        self.btn_api = ctk.CTkButton(f_api, text="1. Selecionar Histórico Aconex DocManager (.xlsx)", width=280, command=self._sel_api,
                                     fg_color="#3A3A3A", hover_color="#454545", font=("Roboto", 12))
        self.btn_api.pack(side="left")
        self.lbl_api_status = ctk.CTkLabel(f_api, text="Nenhum arquivo selecionado", text_color="gray")
        self.lbl_api_status.pack(side="left", padx=15)

        # Input Pasta Raiz (Estilo Caminho: Entry + Botão Buscar)
        f_root = ctk.CTkFrame(frm_main, fg_color="transparent")
        f_root.pack(fill="x", padx=15, pady=8)
        ctk.CTkLabel(f_root, text="2. Pasta Raiz (Arquivos _STATUS_PMIB):", width=280, anchor="w").pack(side="left")
        ctk.CTkEntry(f_root, textvariable=self.path_root, width=300).pack(side="left", padx=5)
        ctk.CTkButton(f_root, text="Buscar", width=80, command=lambda: self.path_root.set(file_dialogs.ask_directory("pmib_manager.pasta_raiz", "pasta", titulo="Selecione a Pasta Raiz"))).pack(side="left")

        # Input Planilha Mestra (Estilo Arquivo: Botão + Label)
        f_master = ctk.CTkFrame(frm_main, fg_color="transparent")
        f_master.pack(fill="x", padx=15, pady=8)
        self.btn_master = ctk.CTkButton(f_master, text="3. Selecionar Mapeamento Sobressalentes (.xlsx)", width=280, command=self._sel_master,
                                        fg_color="#3A3A3A", hover_color="#454545", font=("Roboto", 12))
        self.btn_master.pack(side="left")
        self.lbl_master_status = ctk.CTkLabel(f_master, text="Nenhum arquivo selecionado", text_color="gray")
        self.lbl_master_status.pack(side="left", padx=15)

        # O botão volta a ter um padding normal, já que a barra sumiu daqui
        self.btn_run = ctk.CTkButton(frm_main, text="INICIAR PROCESSO DE GESTÃO",
                                     height=50, width=350,
                                     command=self.iniciar_gestao,
                                     font=("Roboto", 14, "bold"),
                                     fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"], text_color=COLORS["text_white"])
        self.btn_run.pack(pady=(20, 8))

        # [2026-10-05, T7] Painel HTML: a foto do dia para quem não tem o Power
        # BI (que continua sendo o painel oficial). Gerado DEPOIS da gravação
        # dos `_STATUS_PMIB`, para mostrar o que acabou de ser gravado.
        f_painel = ctk.CTkFrame(frm_main, fg_color="transparent")
        f_painel.pack(pady=(0, 15))
        try:
            gerar_por_padrao = prefs.get_opcao(OPCAO_GERAR_PAINEL, True)
        except Exception:
            gerar_por_padrao = True  # preferência é conveniência: nunca impede a tela de abrir
        self.var_gerar_painel = ctk.BooleanVar(value=gerar_por_padrao)
        ctk.CTkCheckBox(f_painel, text="Gerar painel ao terminar", variable=self.var_gerar_painel,
                        command=self._lembrar_gerar_painel, font=("Roboto", 12)).pack(side="left", padx=10)
        self.btn_painel = ctk.CTkButton(f_painel, text="Gerar painel", width=160, command=self.gerar_painel,
                                        fg_color="#3A3A3A", hover_color="#454545", font=("Roboto", 12))
        self.btn_painel.pack(side="left", padx=10)

        # [2026-10-05, T4] Autorizações de entrega de Itaipu: o export que
        # Itaipu manda vira AUTORIZADO nos `_STATUS_PMIB` da Pasta Raiz (era o
        # script `apto_para_entrega_att.py`, com os caminhos fixos no código).
        frm_aut = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8)
        frm_aut.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(frm_aut, text="Autorizações de entrega de Itaipu", font=("Roboto", 16, "bold"),
                     text_color=COLORS["accent"]).pack(anchor="w", padx=15, pady=(15, 0))
        ctk.CTkLabel(frm_aut, text="Grava AUTORIZADO nos _STATUS_PMIB da Pasta Raiz (passo 2) para cada PMIB do "
                                   "export de Itaipu (sobressalentes_autorizados_AAAAMMDDhhmm.xlsx).",
                     text_color="gray", wraplength=720, justify="left").pack(anchor="w", padx=15)
        f_aut = ctk.CTkFrame(frm_aut, fg_color="transparent")
        f_aut.pack(fill="x", padx=15, pady=(8, 15))
        self.btn_autorizados = ctk.CTkButton(f_aut, text="4. Selecionar export de autorizados (.xlsx)", width=280,
                                             command=self._sel_autorizados, fg_color="#3A3A3A",
                                             hover_color="#454545", font=("Roboto", 12))
        self.btn_autorizados.pack(side="left")
        self.lbl_autorizados = ctk.CTkLabel(f_aut, text="Nenhum arquivo selecionado", text_color="gray")
        self.lbl_autorizados.pack(side="left", padx=15)
        self.btn_aplicar = ctk.CTkButton(f_aut, text="APLICAR AUTORIZAÇÕES", width=200,
                                         command=self.aplicar_autorizacoes, font=("Roboto", 12, "bold"),
                                         fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                                         text_color=COLORS["text_white"])
        self.btn_aplicar.pack(side="right")

    def _sel_autorizados(self):
        f = file_dialogs.ask_open_file("pmib_manager.autorizados", "excel",
                                       titulo="Selecione o export de autorizados de Itaipu",
                                       filetypes=[("Excel", "*.xlsx")])
        if f:
            self.path_autorizados.set(f)
            self.lbl_autorizados.configure(text=os.path.basename(f), text_color=COLORS["accent"])
            self.btn_autorizados.configure(fg_color=COLORS["primary"])

    def _travar_botoes(self, travar):
        estado = "disabled" if travar else "normal"
        self.btn_run.configure(state=estado)
        self.btn_aplicar.configure(state=estado)
        self.btn_painel.configure(state=estado)

    def _lembrar_gerar_painel(self):
        try:
            prefs.set_opcao(OPCAO_GERAR_PAINEL, bool(self.var_gerar_painel.get()))
        except Exception:
            pass  # lembrar é conveniência; não pode atrapalhar o clique

    def gerar_painel(self):
        root_folder = self.path_root.get()
        master_path = self.path_master.get()
        if not root_folder:
            return messagebox.showwarning("Aviso", "Por favor, selecione a Pasta Raiz (Passo 2).")
        if not master_path:
            return messagebox.showwarning("Aviso", "Por favor, selecione a Planilha de mapeamento (Passo 3).")
        self._travar_botoes(True)

        def tarefa():
            try:
                self._gerar_painel_e_abrir(root_folder, master_path)
            finally:
                self.after(0, lambda: self._travar_botoes(False))

        threading.Thread(target=tarefa, daemon=True).start()

    def _gerar_painel_e_abrir(self, root_folder, master_path):
        """Gera `Painel de Sobressalentes.html` na Pasta Raiz e o abre no
        navegador. Roda na thread do trabalho. Falhar aqui só gera aviso:
        nunca desfaz o que o Gestão PMIB já gravou."""
        from sigft.services import painel  # pandas: só na hora de usar

        saida = os.path.join(root_folder, painel.NOME_DO_ARQUIVO)
        self._safe_log("Gerando o painel de sobressalentes...")
        try:
            caminho = painel.gerar_painel(root_folder, master_path, saida, callback_log=self._safe_log)
        except PermissionError:
            self._safe_log(f"[AVISO] O painel não foi gravado: {os.path.basename(saida)} está aberto ou "
                           "bloqueado. Feche-o e clique em 'Gerar painel'.")
            return False
        except Exception as e:
            self._safe_log(f"[AVISO] O painel não foi gerado: {type(e).__name__}: {e}")
            return False
        try:
            webbrowser.open(pathlib.Path(caminho).resolve().as_uri())
        except Exception as e:
            self._safe_log(f"[AVISO] Painel gravado, mas não consegui abri-lo no navegador ({e}): {caminho}")
        return True

    # Callback de Travamento de Arquivo (Thread-Safe)
    # [2026-10-05] Sem argumento = a Planilha de Mapeamento (Cancelar aborta o
    # processo). Com o CAMINHO = um `_STATUS_PMIB`, que agora também é gravado
    # (situação da autorização, dias de atraso, autorizações): Cancelar pula só
    # aquele arquivo. Chamado da thread do serviço; o diálogo abre na thread da
    # tela.
    def _perguntar_arquivo_aberto(self, caminho=None):
        resultado = {}
        evento_espera = threading.Event()

        def mostrar_popup():
            if caminho is None:
                titulo = "Planilha Mestra Aberta"
                texto = "O sistema não conseguiu salvar os dados porque a Planilha de Mapeamento está aberta no Excel.\n\nPor favor, salve suas alterações, feche a planilha e clique em 'Repetir'.\nSe quiser abortar o processo, clique em 'Cancelar'."
            else:
                titulo = "Planilha _STATUS_PMIB Aberta"
                texto = (f"O arquivo abaixo está aberto no Excel e não pôde ser gravado:\n\n"
                         f"{os.path.basename(caminho)}\n\n"
                         "Salve suas alterações, feche o arquivo e clique em 'Repetir'.\n"
                         "'Cancelar' pula só este arquivo; o processo continua com os outros.")
            resultado['retry'] = messagebox.askretrycancel(titulo, texto)
            evento_espera.set()

        self.after(0, mostrar_popup)
        evento_espera.wait()
        return resultado.get('retry', False)

    def aplicar_autorizacoes(self):
        export = self.path_autorizados.get()
        root_folder = self.path_root.get()
        if not export:
            return messagebox.showwarning("Aviso", "Por favor, selecione o export de autorizados de Itaipu (Passo 4).")
        if not root_folder:
            return messagebox.showwarning("Aviso", "Por favor, selecione a Pasta Raiz dos _STATUS_PMIB (Passo 2).")
        self._travar_botoes(True)
        threading.Thread(target=self._worker_autorizados, args=(export, root_folder), daemon=True).start()

    def _worker_autorizados(self, export, root_folder):
        try:
            # Importado aqui: o serviço é leve, mas a tela não precisa dele
            # até alguém clicar.
            from sigft.services import autorizados

            self.after(0, lambda: self.progress_bar.set(0))
            self._safe_log("Aplicando o export de autorizados de Itaipu...")
            erros = avisos = 0
            for linha in autorizados.executar(export, root_folder,
                                              callback_retry_lock=self._perguntar_arquivo_aberto):
                self._safe_log(linha)
                erros += "[ERRO]" in linha
                avisos += "[AVISO]" in linha
            self.after(0, lambda: self.progress_bar.set(1.0))
            if erros:
                self.after(0, lambda: messagebox.showwarning(
                    "Aviso", "As autorizações não foram aplicadas. Veja o motivo no log."))
            elif avisos:
                self.after(0, lambda n=avisos: messagebox.showwarning(
                    "Concluído com avisos",
                    f"As autorizações foram aplicadas, mas {n} aviso(s) pedem atenção. "
                    "Procure as linhas [AVISO] no log."))
            else:
                self.after(0, lambda: messagebox.showinfo("Sucesso", "Autorizações de Itaipu aplicadas."))
        except Exception as e:
            self._safe_log(f"[ERRO FATAL]: {e}")
            self.after(0, lambda erro=e: messagebox.showerror(
                "Erro", f"Ocorreu um erro ao aplicar as autorizações:\n{erro}"))
        finally:
            self.after(0, lambda: self._travar_botoes(False))

    def _sel_api(self):
        f = file_dialogs.ask_open_file("pmib_manager.api", "excel", titulo="Selecione a Base de Dados API", filetypes=[("Excel", "*.xlsx *.xls")])
        if f:
            self.path_api.set(f)
            self.lbl_api_status.configure(text=os.path.basename(f), text_color=COLORS["accent"])
            self.btn_api.configure(fg_color=COLORS["primary"])

    def _sel_master(self):
        f = file_dialogs.ask_open_file("pmib_manager.master", "excel", titulo="Selecione a Planilha Mestra", filetypes=[("Excel", "*.xlsx *.xls")])
        if f:
            self.path_master.set(f)
            self.lbl_master_status.configure(text=os.path.basename(f), text_color=COLORS["accent"])
            self.btn_master.configure(fg_color=COLORS["primary"])
            # [2026-09-03] Guarda o ARQUIVO (não só a pasta) para o mural de
            # atividades da Home poder ler o mapeamento sem pedir nada ao
            # usuário. Sem isto o mural dizia "não encontrei o mapeamento"
            # mesmo logo depois de o PMIB Manager rodar sobre ele.
            try:
                prefs.remember_file(CHAVE_MAPEAMENTO, f)
            except Exception:
                # Lembrar o caminho é conveniência; não pode atrapalhar a
                # seleção que o usuário acabou de fazer.
                pass

    # --- Lógica de Execução Segura ---
    def _safe_log(self, txt):
        """Envia o texto para o console de forma segura através da Thread principal"""
        self.after(0, lambda: self.log(txt))

    def iniciar_gestao(self):
        # 1. Coleta e valida os dados visuais ANTES de travar a tela
        api_path = self.path_api.get()
        root_folder = self.path_root.get()
        master_path = self.path_master.get()

        if not api_path:
            return messagebox.showwarning("Aviso", "Por favor, selecione a Base do Aconex (Passo 1).")
        if not root_folder:
            return messagebox.showwarning("Aviso", "Por favor, selecione a Pasta Raiz (Passo 2).")
        if not master_path:
            return messagebox.showwarning("Aviso", "Por favor, selecione a Planilha de mapeamento (Passo 3).")

        # 2. Desativa os botões para evitar cliques duplicados
        self._travar_botoes(True)

        # 3. Dispara o processamento em segundo plano (Thread)
        # A caixa é lida AQUI, na thread da tela: variável do Tk lida de outra
        # thread pode levantar "main thread is not in main loop".
        gerar_painel = bool(self.var_gerar_painel.get())
        threading.Thread(target=self._worker, args=(api_path, root_folder, master_path, gerar_painel),
                         daemon=True).start()

    def _worker(self, api_path, root_folder, master_path, gerar_painel=False):
        try:
            self._safe_log("Iniciando fluxo de gestão de sobressalentes...")

            # Instancia a inteligência do Backend
            manager = backends.pmib_manager_backend.PMIBManager()

            # Arquivo aberto no Excel: ver `_perguntar_arquivo_aberto`.
            cb_retry_lock = self._perguntar_arquivo_aberto

            # Callback Interativo e Seguro (Thread-Safe)
            def cb_confirm(df_novos):
                resultado = {}
                evento_espera = threading.Event()  # Trava a thread do backend até você clicar

                def desenhar_popup():
                    win = ctk.CTkToplevel(self)
                    win.title("Novas Listas Encontradas")
                    win.geometry("750x550")
                    win.transient(self)
                    win.grab_set()

                    ctk.CTkLabel(win, text="Novas Listas de Sobressalentes Encontradas na base de dados:", font=("Roboto", 16, "bold"), text_color=COLORS["accent"]).pack(pady=(15, 5))
                    ctk.CTkLabel(win, text="Selecione abaixo quais você deseja adicionar à Planilha de Mapeamento.", font=("Roboto", 13), text_color="gray").pack(pady=(0, 10))

                    # Área com Scroll para listar os documentos
                    scroll = ctk.CTkScrollableFrame(win, fg_color="#2B2B2B")
                    scroll.pack(fill="both", expand=True, padx=20, pady=5)

                    check_vars = {}

                    # Cria um Checkbox para cada linha encontrada
                    for idx, row in df_novos.iterrows():
                        var = tk.BooleanVar(value=True)  # Começam todos marcados por padrão
                        texto_doc = f"[{row['No. do Documento']}]  -  {row['Título']}"
                        chk = ctk.CTkCheckBox(scroll, text=texto_doc, variable=var, font=("Roboto", 12))
                        chk.pack(anchor="w", padx=10, pady=6)
                        check_vars[idx] = (var, chk)

                    # Funções dos Botões Auxiliares
                    def selecionar_todos():
                        for var, _ in check_vars.values(): var.set(True)

                    def limpar_selecao():
                        for var, _ in check_vars.values(): var.set(False)

                    # Funções de Conclusão
                    def confirmar():
                        # Filtra o DataFrame original mantendo apenas os índices que ficaram com True
                        idxs_marcados = [i for i, (var, _) in check_vars.items() if var.get()]
                        resultado['df_final'] = df_novos.loc[idxs_marcados]
                        evento_espera.set()  # Libera a Thread do backend
                        win.destroy()

                    def ignorar_todas():
                        resultado['df_final'] = pd.DataFrame()  # Retorna Vazio
                        evento_espera.set()
                        win.destroy()

                    # Tratamento caso o usuário clique no "X" da janela
                    win.protocol("WM_DELETE_WINDOW", ignorar_todas)

                    # Frame para os botões inferiores
                    f_botoes = ctk.CTkFrame(win, fg_color="transparent")
                    f_botoes.pack(fill="x", padx=20, pady=15)

                    # Botões de Massa (Esquerda)
                    ctk.CTkButton(f_botoes, text="Marcar Todas", width=120, fg_color="#3A3A3A", hover_color="#454545", command=selecionar_todos).pack(side="left", padx=5)
                    ctk.CTkButton(f_botoes, text="Desmarcar Todas", width=120, fg_color="#3A3A3A", hover_color="#454545", command=limpar_selecao).pack(side="left", padx=5)

                    # Botões de Ação (Direita)
                    ctk.CTkButton(f_botoes, text="Confirmar Seleção", width=150, fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"], command=confirmar).pack(side="right", padx=5)
                    ctk.CTkButton(f_botoes, text="Ignorar (Não Adicionar)", width=150, fg_color="gray", hover_color="#555555", command=ignorar_todas).pack(side="right", padx=5)

                # Dispara o desenho do popup na Thread Principal (Interface)
                self.after(0, desenhar_popup)

                # O Backend fica "congelado" aqui esperando você clicar em Confirmar ou Ignorar
                evento_espera.wait()

                return resultado.get('df_final', pd.DataFrame())

            # Variável de controle para saber se o usuário cancelou
            sucesso_total = True
            # [2026-10-05] Avisos não interrompem (um `_STATUS_PMIB` aberto no
            # Excel é pulado e o resto segue), mas não podem terminar num
            # "Sucesso" seco: a pessoa precisa saber que algo ficou para trás.
            avisos = 0

            # Lemos a tupla que o backend manda passando ambos os callbacks
            for resposta in manager.executar_fluxo(api_path, root_folder, master_path, callback_confirm=cb_confirm, callback_retry_lock=cb_retry_lock):
                if isinstance(resposta, tuple):
                    msg, progresso = resposta
                    self._safe_log(msg)
                    if progresso is not None:
                        self.after(0, lambda p=progresso: self.progress_bar.set(p))
                else:
                    self._safe_log(resposta)
                    # Se o backend jogar um erro (ex: abortado), marcamos como falha
                    if "[ERRO]" in resposta:
                        sucesso_total = False
                    elif "[AVISO]" in resposta:
                        avisos += 1

            # [T7] O painel, DEPOIS da gravação: mostra o que acabou de ser
            # gravado. Fluxo com erro não gera (o botão continua lá).
            if gerar_painel and sucesso_total:
                if not self._gerar_painel_e_abrir(root_folder, master_path):
                    avisos += 1
            elif gerar_painel:
                self._safe_log(" -> Painel não gerado: o processo terminou com erro. Use o botão 'Gerar painel'.")

            # Validação Final Segura
            if sucesso_total and avisos:
                self.after(0, lambda: self.progress_bar.set(1.0))
                self.after(0, lambda n=avisos: messagebox.showwarning(
                    "Concluído com avisos",
                    f"O processo de Gestão PMIB terminou, mas {n} aviso(s) pedem atenção "
                    "(ex.: _STATUS_PMIB aberto no Excel, arquivo ilegível).\n\n"
                    "Procure as linhas [AVISO] no log."))
            elif sucesso_total:
                self.after(0, lambda: self.progress_bar.set(1.0))
                self.after(0, lambda: messagebox.showinfo("Sucesso", "Processo de Gestão PMIB finalizado com sucesso!"))
            else:
                # Não dá mais para dizer "nenhuma alteração foi salva": os
                # `_STATUS_PMIB` e a mapeadora são gravados ao longo do fluxo,
                # e o que foi gravado antes do erro continua gravado.
                self.after(0, lambda: messagebox.showwarning(
                    "Aviso", "O processo foi interrompido ou terminou com erros.\n\n"
                             "O que foi gravado antes do erro continua gravado. Veja o log para saber o que faltou."))

        except Exception as e:
            self._safe_log(f"[ERRO FATAL]: {e}")
            # [CP 8.1] `lambda erro=e:` em vez de fechar sobre `e`. O Python
            # APAGA o nome `e` ao sair do bloco `except`, e este lambda só roda
            # depois disso, pelo laço do Tk -- então a caixa que deveria mostrar
            # a causa da falha levantava `NameError`, e o usuário perdia
            # justamente a mensagem que explicaria o que deu errado.
            # Capturar por valor no argumento padrão congela o objeto agora.
            self.after(0, lambda erro=e: messagebox.showerror(
                "Erro", f"Ocorreu um erro fatal durante a execução:\n{erro}"))
        finally:
            # Reativa os botões ao final de tudo (seja erro ou sucesso)
            self.after(0, lambda: self._travar_botoes(False))

