"""As janelas auxiliares das telas — Checkpoint 7.3 (Fase 7 do plano).

Pop-ups que uma tela abre para pedir uma decisão ou mostrar um resultado, e
que não são compartilhados o bastante para virar widget genérico:

* `JanelaSelecao` e `JanelaSelecaoDuplicadas` — já eram funções finas sobre o
  `TabelaSelecaoDialog` desde o CP 7.2; vieram junto porque quem as usa está
  aqui do lado;
* `JanelaResumo` — tabela de conferência ao fim de um lote de criação;
* `JanelaRevisaoPDM` — revisão item a item do PDM que a IA escolheu;
* `JanelaAcaoRobo` — o que fazer quando o robô encontra a ficha já existente;
* `JanelaRevisaoEdicao` — correção manual dos códigos quando o regex falha.

Por que não foram para `widgets/dialogs.py`: aquele arquivo é dos diálogos
GENÉRICOS, que várias telas usam e que não sabem nada do domínio. Estes aqui
conhecem PDM, código PMIB e fila de duplicadas — são das telas, não do
catálogo de widgets.
"""
from __future__ import annotations

from tkinter import messagebox, simpledialog, ttk

from sigft.app.theme import COLORS
from sigft.app.widgets import dialogs as app_dialogs

import customtkinter as ctk


# =============================================================================
# CLASSES AUXILIARES (Pop-ups)
# =============================================================================
def JanelaSelecao(parent, dataframe, callback_confirmar):
    """[CP 7.2] Era uma classe de ~40 linhas montando um Treeview a mao.

    Agora e uma chamada ao `TabelaSelecaoDialog`, que serve tambem a
    `JanelaSelecaoDuplicadas` -- as duas faziam a mesma tabela com scrollbars e
    devolviam a escolha por callback; o que mudava era a origem dos dados.

    Continua sendo chamada como `JanelaSelecao(self, df, callback)`, entao os 2
    call sites nao mudaram. Vira funcao, e nao classe, porque ninguem guardava
    a instancia nem chamava metodo nela.

    As chaves voltam como STRING do Treeview; o `int()` aqui reproduz o
    `[int(i) for i in self.tree.selection()]` do codigo antigo -- os callbacks
    do ModuloCriaFichas indexam o DataFrame com elas.
    """
    return app_dialogs.TabelaSelecaoDialog.de_dataframe(
        parent,
        dataframe,
        titulo="Seleção de Itens",
        instrucao="Selecione as linhas para processar:",
        geometria="900x600",
        com_cancelar=False,
        ao_confirmar=lambda chaves: callback_confirmar([int(i) for i in chaves]),
    )

class JanelaResumo(ctk.CTkToplevel):
    def __init__(self, parent, df_comparacao):
        super().__init__(parent)
        self.title("Resumo Final")
        self.geometry("1000x500")
        self.transient(parent)

        ctk.CTkLabel(self, text="Resumo da Execução", font=("Arial", 18, "bold")).pack(pady=10)

        frame_tabela = ctk.CTkFrame(self)
        frame_tabela.pack(fill="both", expand=True, padx=10, pady=10)

        sb_y = ttk.Scrollbar(frame_tabela, orient="vertical")
        sb_x = ttk.Scrollbar(frame_tabela, orient="horizontal")

        colunas = ["Descrição Original", "PMIB Criado", "PDM (IA)", "PDM (Portal Final)"]
        tree = ttk.Treeview(frame_tabela, columns=colunas, show="headings", yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

        sb_y.config(command=tree.yview); sb_x.config(command=tree.xview)
        sb_y.pack(side="right", fill="y"); sb_x.pack(side="bottom", fill="x")
        tree.pack(side="left", fill="both", expand=True)

        for col in colunas: tree.heading(col, text=col); tree.column(col, width=300)

        for _, row in df_comparacao.iterrows():
            vals = [row.get('descricao_original', '-'), row.get('PMIB_CRIADO', '-'), row.get('pdm_escolhido', '-'), row.get('PDM_COM_REVISAO', '-')]
            tree.insert("", "end", values=vals)

        ctk.CTkButton(self, text="Fechar", command=self.destroy).pack(pady=10)

class JanelaEscolherPDM(ctk.CTkToplevel):
    """Escolha de um PDM do catálogo, com busca.

    Substitui o `simpledialog.askstring` de texto livre da revisão. A busca e
    o ranqueamento moram no `CatalogoPDM` (`buscar`), testados sem tkinter;
    aqui fica só a tela. Mostra a classe FSC e as características de cada PDM,
    que é o que permite desempatar os 13 títulos repetidos do catálogo real --
    dois `CAMERA VIDEO`, dois `VALVULA`, e assim por diante.
    """

    LINHAS_VISIVEIS = 40

    def __init__(self, parent, catalogo):
        super().__init__(parent)
        self.title("Escolher PDM")
        self.geometry("900x560")
        self.transient(parent)
        self.grab_set()

        self.catalogo = catalogo
        self.escolha = None
        self._achados = []

        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(
            topo,
            text=f"Busque entre os {len(catalogo)} PDMs do catálogo:",
            font=("Roboto", 13, "bold"),
        ).pack(anchor="w")

        self.entry_busca = ctk.CTkEntry(
            topo, placeholder_text="ex.: valvula esfera  |  4820.004  |  camera"
        )
        self.entry_busca.pack(fill="x", pady=(6, 0))
        self.entry_busca.bind("<KeyRelease>", lambda _e: self._atualizar())
        self.entry_busca.bind("<Return>", lambda _e: self.confirmar())

        frame_lista = ctk.CTkFrame(self)
        frame_lista.pack(fill="both", expand=True, padx=10, pady=(6, 0))

        sb = ttk.Scrollbar(frame_lista, orient="vertical")
        self.lista = ttk.Treeview(
            frame_lista,
            columns=["PDM", "Classe", "Características"],
            show="headings",
            yscrollcommand=sb.set,
            selectmode="browse",
        )
        sb.config(command=self.lista.yview)
        sb.pack(side="right", fill="y")
        self.lista.pack(side="left", fill="both", expand=True)
        for coluna, largura in (("PDM", 330), ("Classe", 70), ("Características", 460)):
            self.lista.heading(coluna, text=coluna)
            self.lista.column(coluna, width=largura, anchor="w")
        self.lista.bind("<Double-1>", lambda _e: self.confirmar())

        rodape = ctk.CTkFrame(self, fg_color="transparent")
        rodape.pack(fill="x", padx=10, pady=10)
        self.lbl_contagem = ctk.CTkLabel(rodape, text="", text_color="gray")
        self.lbl_contagem.pack(side="left")
        ctk.CTkButton(rodape, text="Cancelar", fg_color="#3A3A3A",
                      command=self.cancelar).pack(side="right", padx=5)
        ctk.CTkButton(rodape, text="USAR ESTE PDM", fg_color=COLORS["accent"],
                      command=self.confirmar).pack(side="right", padx=5)

        self._atualizar()
        self.entry_busca.focus_set()

    def _atualizar(self):
        self._achados = self.catalogo.buscar(
            self.entry_busca.get(), limite=self.LINHAS_VISIVEIS
        )
        self.lista.delete(*self.lista.get_children())
        for posicao, pdm in enumerate(self._achados):
            self.lista.insert(
                "", "end", iid=str(posicao),
                values=(pdm.completo, pdm.classe,
                        "; ".join(pdm.caracteristicas[:6])),
            )
        self.lbl_contagem.configure(
            text=f"{len(self._achados)} PDM(s) na lista"
            + (f" (mostrando os {self.LINHAS_VISIVEIS} primeiros)"
               if len(self._achados) >= self.LINHAS_VISIVEIS else "")
        )
        if self._achados:
            self.lista.selection_set("0")

    def confirmar(self):
        selecionado = self.lista.selection()
        if not selecionado:
            messagebox.showwarning("Aviso", "Selecione um PDM da lista.")
            return
        self.escolha = self._achados[int(selecionado[0])]
        self.destroy()

    def cancelar(self):
        self.escolha = None
        self.destroy()


class JanelaRevisaoPDM(ctk.CTkToplevel):
    def __init__(self, parent, dataframe, callback_confirmar, catalogo=None):
        super().__init__(parent)
        self.title("Revisão de PDMs - Pré-Automação")
        self.geometry("1100x600")
        self.transient(parent)
        self.grab_set()

        self.df_dados = dataframe.copy()  # Trabalha numa cópia para não quebrar o original se cancelar
        self.callback = callback_confirmar
        # `catalogo=None` mantém a assinatura antiga válida (e o modo
        # "Pular IA" não tem catálogo): sem ele, `editar_pdm` cai no campo de
        # texto livre de antes.
        self.catalogo = catalogo

        # --- Cabeçalho e Botões ---
        top_frame = ctk.CTkFrame(self)
        top_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(top_frame, text="Verifique os PDMs sugeridos antes da automação.", font=("Arial", 14, "bold")).pack(side="left")

        btn_confirmar = ctk.CTkButton(top_frame, text="CONFIRMAR E AVANÇAR >>", fg_color="green", command=self.confirmar)
        btn_confirmar.pack(side="right", padx=5)

        btn_editar = ctk.CTkButton(top_frame, text="Editar PDM Selecionado", command=self.editar_pdm)
        btn_editar.pack(side="right", padx=5)

        # --- Tabela (Treeview) ---
        # Usamos ttk.Treeview pois o ctk não tem tabela nativa com colunas complexas
        self.frame_tabela = ctk.CTkFrame(self)
        self.frame_tabela.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        sb_y = ttk.Scrollbar(self.frame_tabela, orient="vertical")
        sb_x = ttk.Scrollbar(self.frame_tabela, orient="horizontal")

        colunas = ["INDEX", "Descrição Original", "PDM Escolhido", "Descrição Curta", "Unidade", "Tipo"]

        self.tree = ttk.Treeview(
            self.frame_tabela,
            columns=colunas,
            show="headings",
            yscrollcommand=sb_y.set,
            xscrollcommand=sb_x.set,
            selectmode="extended"
        )

        sb_y.config(command=self.tree.yview); sb_x.config(command=self.tree.xview)
        sb_y.pack(side="right", fill="y"); sb_x.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)

        # Configura colunas
        self.tree.heading("INDEX", text="ID"); self.tree.column("INDEX", width=40)
        self.tree.heading("Descrição Original", text="Descrição Original"); self.tree.column("Descrição Original", width=350)
        self.tree.heading("PDM Escolhido", text="PDM Escolhido (EDITÁVEL)"); self.tree.column("PDM Escolhido", width=250)
        self.tree.heading("Descrição Curta", text="Descrição Curta"); self.tree.column("Descrição Curta", width=200)
        self.tree.heading("Unidade", text="UN"); self.tree.column("Unidade", width=50)
        self.tree.heading("Tipo", text="Tipo"); self.tree.column("Tipo", width=100)

        self.preencher_tabela()

    def preencher_tabela(self):
        # Limpa atual
        for item in self.tree.get_children(): self.tree.delete(item)

        # Preenche
        for index, row in self.df_dados.iterrows():
            vals = [
                index,
                row.get('descricao_original', ''),
                row.get('pdm_escolhido', ''),
                row.get('descricao_curta', ''),
                row.get('unidade', ''),
                row.get('tipo', '')
            ]
            self.tree.insert("", "end", iid=index, values=vals)

    def editar_pdm(self):
        selecionados = self.tree.selection()
        if not selecionados:
            messagebox.showwarning("Aviso", "Selecione uma ou mais linhas para editar o PDM.")
            return

        # Com catálogo, a pessoa ESCOLHE de uma lista com busca; sem ele
        # (modo "Pular IA", em que o PDM vem da planilha e não há catálogo
        # carregado), cai no campo de texto de antes. O `askstring` era o
        # único caminho até 2026-09-22: a pessoa digitava
        # "PDM.1234.001 - NOME" de cabeça, sem busca e sem validação, e o que
        # ela escrevesse ia direto para o filtro de PDM do portal.
        if self.catalogo is not None:
            escolha = JanelaEscolherPDM(self, self.catalogo).escolha
            novo_pdm = escolha.completo if escolha else None
        else:
            novo_pdm = simpledialog.askstring(
                "Editar PDM",
                "Digite o novo código PDM completo (ex: PDM.1234.001 - NOME):",
            )

        if novo_pdm:
            for iid in selecionados:
                # Atualiza no DataFrame
                idx = int(iid)
                self.df_dados.at[idx, 'pdm_escolhido'] = novo_pdm

                # Atualiza visualmente na Treeview (preserva os outros valores)
                atuais = self.tree.item(iid, "values")
                novos_valores = list(atuais)
                novos_valores[2] = novo_pdm  # Índice 2 é a coluna PDM
                self.tree.item(iid, values=novos_valores)

    def confirmar(self):
        if messagebox.askyesno("Confirmar", "Deseja prosseguir para a automação com estes dados?"):
            self.callback(self.df_dados)
            self.destroy()

class JanelaAcaoRobo(ctk.CTkToplevel):
    """
    Janela modal para decidir o que fazer quando o robô falha em um item.
    Retorna a escolha do usuário e, opcionalmente, um novo PDM.
    """
    def __init__(self, parent, msg_erro, pdm_atual):
        super().__init__(parent)
        self.title("Atenção: Intervenção Necessária")
        self.geometry("500x350")
        self.transient(parent)

        self.escolha = None
        self.novo_pdm = None

        # --- UI ---
        ctk.CTkLabel(self, text="Ocorreu um erro ao processar o item:", font=("Roboto", 14, "bold"), text_color="red").pack(pady=(15, 5))

        box_erro = ctk.CTkTextbox(self, height=60, font=("Consolas", 11))
        box_erro.pack(fill="x", padx=20, pady=5)
        box_erro.insert("0.0", str(msg_erro))
        box_erro.configure(state="disabled")

        ctk.CTkLabel(self, text=f"PDM Atual: {pdm_atual}", font=("Roboto", 12)).pack(pady=5)

        # Frame de Botões
        frm_botoes = ctk.CTkFrame(self, fg_color="transparent")
        frm_botoes.pack(fill="both", expand=True, padx=20, pady=10)

        # Opção 0: Tentar Novamente
        btn_retry = ctk.CTkButton(frm_botoes, text="[0] Tentar Novamente (Mesmo PDM)", command=lambda: self._responder("RETRY"))
        btn_retry.pack(fill="x", pady=5)

        # Opção 1: Pular
        btn_skip = ctk.CTkButton(frm_botoes, text="[1] Pular este Item", fg_color="#B8860B", hover_color="#DAA520", command=lambda: self._responder("SKIP"))
        btn_skip.pack(fill="x", pady=5)

        # Opção 2: Mudar PDM
        frm_mudar = ctk.CTkFrame(frm_botoes, fg_color="transparent")
        frm_mudar.pack(fill="x", pady=5)
        self.entry_pdm = ctk.CTkEntry(frm_mudar, placeholder_text="Novo código PDM...")
        self.entry_pdm.pack(side="left", fill="x", expand=True, padx=(0, 5))
        btn_mudar = ctk.CTkButton(frm_mudar, text="[2] Mudar PDM e Tentar", width=140, command=self._mudar_pdm)
        btn_mudar.pack(side="right")

        # Opção 3: Parar
        btn_stop = ctk.CTkButton(frm_botoes, text="[3] Parar Automação e Salvar", fg_color="red", hover_color="#8B0000", command=lambda: self._responder("STOP"))
        btn_stop.pack(fill="x", pady=5)

        self.protocol("WM_DELETE_WINDOW", lambda: self._responder("STOP"))  # Se fechar no X, para tudo
        self.grab_set()
        self.wait_window()  # Trava a thread aqui até uma decisão

    def _responder(self, acao):
        self.escolha = acao
        self.destroy()

    def _mudar_pdm(self):
        pdm_digitado = self.entry_pdm.get().strip()
        if pdm_digitado:
            self.novo_pdm = pdm_digitado
            self._responder("CHANGE_PDM")
        else:
            messagebox.showwarning("Aviso", "Digite o novo PDM antes de clicar.")

def JanelaSelecaoDuplicadas(parent, fila_completa, callback_confirmar):
    """[CP 7.2] Selecionar, entre as duplicadas encontradas, quais rodar agora.

    Mesma tabela do `JanelaSelecao`, com tres diferencas que viraram parametro:
    as colunas sao fixas, tudo ja vem marcado, e ha botao Cancelar.

    A chave de cada linha e a POSICAO na `fila_completa` -- e assim que o
    callback volta a encontrar o item original.
    """
    colunas = ("Descrição", "PMIB Original (Base)", "PMIB Alvo (Novo)")
    linhas = [
        (idx, (item["descricao"], item["pmib_original"], item["pmib_alvo"]))
        for idx, item in enumerate(fila_completa)
    ]

    def _confirmar(chaves):
        callback_confirmar([fila_completa[int(i)] for i in chaves])

    return app_dialogs.TabelaSelecaoDialog(
        parent,
        colunas=colunas,
        linhas=linhas,
        titulo="Selecionar Fichas para Cópia",
        instrucao="Selecione as fichas que deseja processar neste lote:",
        geometria="900x500",
        larguras={
            "Descrição": {"width": 400},
            "PMIB Original (Base)": {"width": 150, "anchor": "center"},
            "PMIB Alvo (Novo)": {"width": 150, "anchor": "center"},
        },
        preselecionar_tudo=True,
        ao_confirmar=_confirmar,
    )

class JanelaRevisaoEdicao(ctk.CTkToplevel):
    """Janela para ver o Resumo e editar os códigos Original/Alvo manualmente, caso o Regex tenha falhado."""
    def __init__(self, parent, fila_selecionada):
        super().__init__(parent)
        self.title("Revisão e Edição Manual")
        self.geometry("900x500")
        self.attributes('-topmost', True)
        self.grab_set()

        self.fila_selecionada = fila_selecionada  # Referência direta (alterações aqui afetam o frontend principal)

        ctk.CTkLabel(self, text="Dê um DUPLO CLIQUE em uma linha para editar os códigos PMIB.", font=("Roboto", 14, "bold")).pack(pady=10)

        # Configurando o Treeview
        frame_tree = ctk.CTkFrame(self)
        frame_tree.pack(fill="both", expand=True, padx=20, pady=10)

        cols = ("ID", "Descrição", "PMIB Original", "PMIB Alvo")
        self.tree = ttk.Treeview(frame_tree, columns=cols, show="headings", selectmode="browse")

        self.tree.heading("ID", text="ID")
        self.tree.heading("Descrição", text="Descrição")
        self.tree.heading("PMIB Original", text="PMIB Original (Ler Dados)")
        self.tree.heading("PMIB Alvo", text="PMIB Alvo (Escrever)")

        self.tree.column("ID", width=40, anchor="center")
        self.tree.column("Descrição", width=350)
        self.tree.column("PMIB Original", width=150, anchor="center")
        self.tree.column("PMIB Alvo", width=150, anchor="center")

        scroll_y = ttk.Scrollbar(frame_tree, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scroll_y.pack(side="right", fill="y")

        self.atualizar_tabela()

        # Evento de Duplo Clique para Editar
        self.tree.bind("<Double-1>", self.on_double_click)

        ctk.CTkButton(self, text="Concluir Revisão", command=self.destroy, fg_color=COLORS["primary"]).pack(pady=15)

    def atualizar_tabela(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for idx, item in enumerate(self.fila_selecionada):
            self.tree.insert("", "end", iid=idx, values=(idx+1, item["descricao"], item["pmib_original"], item["pmib_alvo"]))

    def on_double_click(self, event):
        selecionado = self.tree.selection()
        if not selecionado: return

        idx = int(selecionado[0])
        item_ref = self.fila_selecionada[idx]

        # Cria um pequeno popup de edição
        pop = ctk.CTkToplevel(self)
        pop.title("Editar Item")
        pop.geometry("400x300")
        pop.attributes('-topmost', True)
        pop.grab_set()

        ctk.CTkLabel(pop, text="PMIB Original (Ficha Base):", anchor="w").pack(fill="x", padx=20, pady=(15, 0))
        entry_orig = ctk.CTkEntry(pop)
        entry_orig.pack(fill="x", padx=20, pady=5)
        entry_orig.insert(0, item_ref["pmib_original"])

        ctk.CTkLabel(pop, text="PMIB Alvo (Nova Ficha):", anchor="w").pack(fill="x", padx=20, pady=(15, 0))
        entry_alvo = ctk.CTkEntry(pop)
        entry_alvo.pack(fill="x", padx=20, pady=5)
        entry_alvo.insert(0, item_ref["pmib_alvo"])

        def salvar_edicao():
            novo_orig = entry_orig.get().strip()
            novo_alvo = entry_alvo.get().strip()
            if not novo_orig or not novo_alvo:
                messagebox.showwarning("Aviso", "Os códigos não podem ficar vazios.")
                return

            # Atualiza a referência original em memória
            self.fila_selecionada[idx]["pmib_original"] = novo_orig
            self.fila_selecionada[idx]["pmib_alvo"] = novo_alvo

            self.atualizar_tabela()
            pop.destroy()

        ctk.CTkButton(pop, text="Salvar Alteração", command=salvar_edicao, fg_color=COLORS["primary"]).pack(pady=20)

