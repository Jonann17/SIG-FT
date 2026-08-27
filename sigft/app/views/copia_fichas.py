"""Tela "Cópia de Fichas" (fichas duplicadas) — Checkpoint 7.3 (Fase 7).

Identifica fichas duplicadas a partir da planilha, deixa o usuário revisar os
pares original/alvo, e copia o conteúdo de uma para a outra no portal.
Reconstruída na Fase 6 do plano.
"""
from __future__ import annotations

import threading

from sigft import config as sigft_config
from sigft.app import file_dialogs
from sigft.app.theme import COLORS
from sigft.app.views.janelas import JanelaRevisaoEdicao, JanelaSelecaoDuplicadas
from sigft.app.widgets import dialogs as app_dialogs
from sigft.services import duplicadas

import customtkinter as ctk


# =============================================================================
# MÓDULO 7: UPLOAD DE FICHAS DUPLICADAS (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloCopiaFichas(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Variáveis de Estado
        self.caminho_status = None
        self.fila_completa = []
        self.fila_selecionada = []
        # Duplicadas encontradas que o robô NÃO consegue processar (sem ficha
        # original ou sem código do material). Ficam fora da fila, mas contadas
        # e explicadas -- ver `_worker_leitura_excel`.
        self.impedidas = []

        # Layout Principal
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=3)
        self.grid_rowconfigure(2, weight=1)

        # Header
        header = ctk.CTkFrame(self, height=50, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(header, text="Módulo: Cópia de Fichas PMIB", font=("Roboto", 24, "bold"), text_color=COLORS["text_white"]).pack(side="left")

        # Container Principal
        self.content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=20, pady=0)

        # Console de Log
        self.console = ctk.CTkTextbox(self, font=("Consolas", 12))
        self.console.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)

        self._build_ui()

    def log(self, msg):
        self.after(0, lambda: [self.console.insert("end", f"> {msg}\n"), self.console.see("end")])

    def _build_ui(self):
        # --- ETAPA 1: CONFIGURAÇÃO ---
        frm_config = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8)
        frm_config.pack(fill="x", pady=10)

        ctk.CTkLabel(frm_config, text="1. Selecionar Arquivo Base", font=("Roboto", 16, "bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=15, pady=10)

        f_pmib = ctk.CTkFrame(frm_config, fg_color="transparent")
        f_pmib.pack(fill="x", padx=15, pady=10)

        self.btn_status = ctk.CTkButton(f_pmib, text="Selecionar _STATUS_PMIB", command=self.selecionar_excel_pmib,
                                        fg_color="#3A3A3A", hover_color="#454545", width=250)
        self.btn_status.pack(side="left")
        self.lbl_status = ctk.CTkLabel(f_pmib, text="Aguardando seleção...", text_color="gray")
        self.lbl_status.pack(side="left", padx=15)

        # --- ETAPA 2: AÇÕES ---
        frm_action = ctk.CTkFrame(self.content, fg_color="#2B2B2B", corner_radius=8)
        frm_action.pack(fill="x", pady=10)

        ctk.CTkLabel(frm_action, text="2. Execução", font=("Roboto", 16, "bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=15, pady=10)

        f_actions_grid = ctk.CTkFrame(frm_action, fg_color="transparent")
        f_actions_grid.pack(fill="x", padx=15, pady=10)
        f_actions_grid.grid_columnconfigure((0, 1), weight=1, uniform="cols")

        self.btn_resumo = ctk.CTkButton(f_actions_grid, text="1. Revisar / Editar Fichas", command=self.abrir_revisao,
                                        fg_color="#3A3A3A", hover_color="#454545", height=40, state="disabled")
        self.btn_resumo.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        # CP 5.5: aqui havia TRÊS botões -- "2. Iniciar Robô Web" (o robô em
        # Selenium), "3. Salvar 'COMPLETO' no Excel" e este. Os dois primeiros
        # saíram com o Selenium.
        #
        # O "3. Salvar COMPLETO" foi junto e não por tabela: ele marcava as
        # QUATRO colunas de seção como COMPLETO para toda ficha que não tivesse
        # estourado, sem olhar seção nenhuma. Quem faz isso agora é
        # `duplicadas_robo.marcar_status_na_planilha`, seção por seção e a
        # partir do resultado real -- e o robô já a chama sozinho no fim do
        # lote. Planilha que diz COMPLETO no que ficou pela metade é pior do
        # que planilha vazia.
        self.btn_robo_novo = ctk.CTkButton(
            f_actions_grid, text="2. Iniciar Robô Web",
            command=self.run_robo_novo_thread,
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            height=40, state="disabled")
        self.btn_robo_novo.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        # Log de auditoria (2026-08-18, pedido do usuário: "trabalhar com os
        # logs de saída do que está acontecendo pra eventual auditoria do
        # processo"). Ligado, grava em `logs/` TUDO que aparece no console
        # mais o HTML de cada seção que o robô visita -- que é o que permite
        # mapear uma seção nova do portal sem abrir o "inspecionar elemento".
        # O HTML vai só para o arquivo; o console continua legível.
        self.var_log_auditoria = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(frm_action, text="Gravar log de auditoria (com a estrutura das telas)",
                      variable=self.var_log_auditoria, onvalue=True, offvalue=False,
                      progress_color=COLORS["primary"]).pack(anchor="w", padx=15, pady=(8, 0))

        # CP 5.5: aqui havia um rótulo dizendo "Reconstrução da Fase 6. AINDA
        # NÃO faz documentos, imagens nem Condições -- essas seções continuam
        # com o botão 2." As duas metades ficaram falsas: a Fase 6 fechou
        # fazendo as três, e o botão 2 (o robô em Selenium) não existe mais.
        # Rótulo que mente é pior que rótulo nenhum -- ele manda o usuário
        # procurar um caminho que sumiu.

        # Progresso
        self.progress = ctk.CTkProgressBar(frm_action, progress_color=COLORS["accent"])
        self.progress.pack(fill="x", padx=15, pady=15)
        self.progress.set(0)

    # =========================================================================
    # LÓGICA DE INTERFACE
    # =========================================================================
    def selecionar_excel_pmib(self):
        path = file_dialogs.ask_open_file("copia_fichas.status_pmib", "excel", filetypes=[("Excel", "*.xlsx;*.xlsm")])
        if not path: return
        self.caminho_status = path

        self.log("Lendo arquivo Excel, aguarde...")
        self.btn_status.configure(state="disabled")

        # Joga para Thread para não travar a UI ao ler Excel grande
        threading.Thread(target=self._worker_leitura_excel).start()

    def _worker_leitura_excel(self):
        # CP 6.2: quem identifica as duplicadas passou a ser
        # `sigft/services/duplicadas.py` -- a implementação testada (22 testes)
        # e a que segue a regra que o usuário definiu: prefixo `PDM.9900.000`
        # na coluna do PDM usado. O robô continua sendo o antigo
        # (`backend.ExtratorFichaBase`/`InjetorFichaAlvo`); o que mudou aqui é
        # só QUEM decide quais fichas entram na fila.
        #
        # Três ganhos concretos sobre o `GerenciadorFilaPMIB`, e todos aparecem
        # nesta tela: a coluna do PDM é aceita em mais grafias (com `PDMs
        # usados` o antigo achava ZERO fichas); as impedidas viram log em vez
        # de sumirem caladas; e as linhas que a regra antiga pegaria e esta não
        # saem como aviso, em vez de simplesmente não aparecerem.
        try:
            fichas, mensagem = duplicadas.localizar_duplicadas(
                self.caminho_status, callback_log=self.log)
            self.log(mensagem)

            self.impedidas = [f for f in fichas if not f.pronta_para_duplicar]
            for ficha in self.impedidas:
                self.log(f"   [Fora da fila] linha {ficha.linha} "
                         f"({ficha.pmib or 'sem código PMIB'}): falta "
                         f"{ficha.motivo_de_impedimento}.")

            # OBSERVAÇÕES sem código PMIB: a ficha ENTRA na fila (o texto pode
            # ser o código em outra grafia), mas com aviso -- o módulo antigo
            # descartava essas linhas, e sem o aviso a diferença apareceria
            # como uma busca no portal por "ver ficha do motor", no meio do
            # lote. O botão "1. Revisar / Editar Fichas" corrige à mão.
            for ficha in fichas:
                if ficha.pronta_para_duplicar and not ficha.original_e_codigo_pmib:
                    self.log(f"   [Atenção] linha {ficha.linha} ({ficha.pmib}): "
                             f"OBSERVAÇÕES não tem código PMIB -- o robô vai tentar "
                             f"com {ficha.ficha_original!r}. Confira em 'Revisar / Editar'.")

            # O robô precisa das duas pontas -- original e alvo. Sem elas não
            # há de onde copiar, então a ficha fica fora da fila; mas saiu no
            # log acima, com a linha do Excel e o motivo. O módulo antigo a
            # descartava em silêncio, e ficha que some sem explicação é o erro
            # que ninguém vai procurar.
            self.fila_completa = [
                {
                    "descricao": ficha.descricao or "Sem Descrição",
                    "pmib_original": ficha.ficha_original,
                    "pmib_alvo": ficha.pmib,
                    # Guardados para o CP 6.3 (referência do fabricante e do
                    # fornecedor). A janela de seleção ignora chaves extras.
                    "codigo_material": ficha.codigo_material,
                    "codigo_fornecedor": ficha.codigo_fornecedor,
                    "linha_excel": ficha.linha,
                }
                for ficha in fichas if ficha.pronta_para_duplicar
            ]
            self.after(0, self._pos_leitura_sucesso)
        except Exception as e:
            self.log(f"Falha na leitura: {e}")
            self.after(0, lambda: self.btn_status.configure(state="normal"))

    def _pos_leitura_sucesso(self):
        self.btn_status.configure(state="normal", fg_color=COLORS["primary"])
        texto = f"Planilha carregada. Encontradas {len(self.fila_completa)} duplicadas."
        if self.impedidas:
            texto += f" ({len(self.impedidas)} sem dados para o robô — ver log.)"
        self.lbl_status.configure(text=texto, text_color=COLORS["accent"])
        self.log(f"{len(self.fila_completa)} fichas identificadas como cópia.")

        if self.fila_completa:
            # Abre imediatamente a janela para selecionar quais processar
            JanelaSelecaoDuplicadas(self, self.fila_completa, self._pos_selecao)

    def _pos_selecao(self, selecionados):
        self.fila_selecionada = selecionados
        self.lbl_status.configure(text=f"{len(self.fila_selecionada)} fichas na fila para processar.")
        self.log(f"Fila final configurada com {len(self.fila_selecionada)} fichas.")

        estado = "normal" if self.fila_selecionada else "disabled"
        self.btn_resumo.configure(state=estado)
        self.btn_robo_novo.configure(state=estado)

    def abrir_revisao(self):
        if self.fila_selecionada:
            JanelaRevisaoEdicao(self, self.fila_selecionada)

    # =========================================================================
    # ROBÔ NOVO (Fase 6) — Playwright, sem uma linha de Selenium
    # =========================================================================
    def run_robo_novo_thread(self):
        if not self.fila_selecionada:
            return
        # Os botões são desligados AQUI, na thread da UI, e não lá dentro: o
        # tkinter não é seguro fora da thread principal. O robô antigo fazia
        # isso de dentro do worker -- funcionava na prática e é o tipo de coisa
        # que falha um dia, sem padrão. Código novo não repete.
        for botao in (self.btn_robo_novo, self.btn_resumo, self.btn_status):
            botao.configure(state="disabled")
        threading.Thread(target=self._worker_robo_novo, daemon=True).start()

    def _fichas_para_o_robo_novo(self):
        """Os dicts da fila viram `FichaDuplicada` de novo.

        Reconstruir do DICT, e não guardar o objeto original, é o que faz a
        edição manual valer: `JanelaRevisaoEdicao` altera `pmib_original` e
        `pmib_alvo` direto no dicionário, e é justamente para consertar o caso
        em que a leitura da planilha errou. Ignorar isso aqui mandaria o robô
        buscar de novo o código que o usuário acabou de corrigir.
        """
        return [
            duplicadas.FichaDuplicada(
                pmib=item["pmib_alvo"],
                descricao=item.get("descricao", ""),
                pdm_usado="",
                codigo_material=item.get("codigo_material", ""),
                codigo_fornecedor=item.get("codigo_fornecedor", ""),
                ficha_original=item["pmib_original"],
                linha=item.get("linha_excel", 0),
            )
            for item in self.fila_selecionada
        ]

    def _worker_robo_novo(self):
        # Import tardio de propósito: puxa o Playwright, e quem nunca clica
        # neste botão não deve pagar por isso na abertura do aplicativo.
        from sigft.services import duplicadas_robo

        from sigft.core.log_execucao import LogDeExecucao

        engine = None
        log_auditoria = None
        registrar = self.log
        try:
            fichas = self._fichas_para_o_robo_novo()

            if self.var_log_auditoria.get():
                log_auditoria = LogDeExecucao(
                    "duplicadas", contexto={"fichas": len(fichas)})
                # `envolver` devolve um callback que grava no arquivo E repassa
                # para o console -- o serviço continua sem saber onde o log
                # para (mesmo princípio de `core/callbacks.py`).
                registrar = log_auditoria.envolver(self.log)
                self.log(f"[Auditoria] Gravando em: {log_auditoria.caminho}")

            registrar(f"[Robô novo] {len(fichas)} ficha(s) na fila. Abrindo o navegador...")
            engine, portal = duplicadas_robo.iniciar()
            engine.goto(sigft_config.PORTAL_URL)

            # Mesma pausa de login do robô antigo: o portal exige login manual
            # e não há como automatizá-lo.
            evento_espera = threading.Event()
            self.after(0, lambda: self._mostrar_janela_pausa(evento_espera))
            evento_espera.wait()

            resultados = duplicadas_robo.processar_lote(
                fichas,
                callback_log=registrar,
                callback_progresso=lambda fracao: self.after(
                    0, lambda f=fracao: self.progress.set(f)),
                portal=portal,
                log_auditoria=log_auditoria,
            )

            # Marca o `_STATUS_PMIB` seção a seção: COMPLETO só onde TUDO deu
            # certo, INCOMPLETO no resto. É o pedido do usuário e o conserto de
            # um hábito do fluxo antigo, que marcava as quatro colunas como
            # COMPLETO para toda ficha que não tivesse estourado -- planilha
            # que diz COMPLETO no que ficou pela metade é pior do que planilha
            # vazia, porque ninguém volta a conferir o que está marcado.
            registrar("[Robô novo] Marcando o _STATUS_PMIB...")
            marcadas, falhas = duplicadas_robo.marcar_status_na_planilha(
                self.caminho_status, resultados, callback_log=registrar)

            concluidas = [r for r in resultados if r.ok]
            registrar(f"[Robô novo] {len(concluidas)} de {len(resultados)} sem pendência; "
                     f"{marcadas} linha(s) marcada(s) na planilha"
                     + (f", {len(falhas)} falha(s)." if falhas else "."))
            registrar("[Robô novo] Confira no portal o que o log marcou como "
                     "pendência antes de mudar o status das fichas.")
        except Exception as erro:
            registrar(f"[Robô novo] Falha: {type(erro).__name__}: {erro}")
        finally:
            # Fecha o log ANTES de mexer no navegador: se `engine.fechar()`
            # travar, o arquivo já está íntegro no disco -- e é justamente
            # a execução que morre no meio a que mais interessa auditar.
            if log_auditoria is not None:
                log_auditoria.fechar()
                self.after(0, lambda c=log_auditoria.caminho: self.log(
                    f"[Auditoria] Log salvo: {c}"))
            if engine is not None:
                try:
                    engine.fechar()
                except Exception:
                    pass
            self.after(0, lambda: [
                self.btn_robo_novo.configure(state="normal"),
                self.btn_resumo.configure(state="normal"),
                self.btn_status.configure(state="normal"),
            ])

    def _mostrar_janela_pausa(self, evento_espera):
        """Pausa o robô para o usuário fazer Login e iniciar.

        [CP 7.2] Delega para `widgets/dialogs.PausaLoginDialog`.
        """
        app_dialogs.PausaLoginDialog(
            self, mensagem=app_dialogs.MSG_LOGIN_LOTE, evento_espera=evento_espera
        )

