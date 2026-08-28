"""Diálogos de ação manual — UMA implementação de cada.

Checkpoint 7.2 do plano (`docs/refatoracao/PLANO_REFATORACAO.md`, Fase 7).

Substitui:

* as **3 cópias** de `_mostrar_janela_pausa` (`ModuloUploadConditions`,
  `ModuloUploadTechSpecs`, `ModuloCopiaFichas`) — esqueleto idêntico nas três,
  só a mensagem muda;
* `_mostrar_janela_retry` (`ModuloUploadConditions`), a janela de "Excel
  bloqueado".

O protocolo que estes diálogos implementam
------------------------------------------
Todos seguem o mesmo par, e ele NÃO é detalhe de implementação — é o que
permite ao robô rodar em thread sem congelar a interface:

1. o worker (numa `threading.Thread`) cria um `threading.Event`, pede à
   interface que abra o diálogo com `self.after(0, ...)` e chama
   `evento.wait()`;
2. o diálogo roda na thread da interface e chama `evento.set()` quando o
   usuário decide — soltando o worker.

Por que NÃO há `grab_set()` aqui
--------------------------------
O comentário original, no `ModuloCopiaFichas`, merece sobreviver à
refatoração porque registra uma tentativa que deu errado:

    "Nós propositalmente NÃO usamos top.grab_set() aqui. É ele que bloqueava
    tudo!"

`grab_set()` torna o diálogo modal e captura TODOS os eventos da aplicação —
o usuário deixa de conseguir clicar no console para copiar as pendências, que
é justamente o que ele precisa fazer enquanto o diálogo está aberto. O
`-topmost` dá a visibilidade desejada sem tirar o resto do app do ar.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk

from sigft.app import theme

# Sentinela que as três telas já usavam para escolher a mensagem de login em
# vez da mensagem de "confira e salve". Era uma string solta repetida em três
# arquivos-classe; aqui é uma constante, e quem compara importa daqui.
LOGIN_NECESSARIO = "LOGIN_NECESSARIO"

# Rótulo padrão do botão que solta o robô. É constante porque a tela de
# exclusão de LMR troca o dela: numa ação destrutiva, o botão dizer o que vai
# acontecer ("COMEÇAR A EXCLUSÃO") é mais honesto que um rótulo genérico.
TEXTO_CONTINUAR = "CONTINUAR AUTOMAÇÃO"

# As mensagens, palavra por palavra como estavam. A Fase 7 é zero redesign, e
# texto de interface é aparência: mudar "solte o robô" para "iniciar" seria
# uma alteração de produto sem pedido.
MSG_LOGIN_SOLTAR_ROBO = (
    "O navegador foi aberto.\n\n"
    "1. Faça o LOGIN no site.\n"
    "2. Navegue até a tela inicial do PMIB.\n"
    "3. Clique abaixo para soltar o robô."
)
MSG_LOGIN_LOTE = (
    "O navegador foi aberto.\n\n"
    "1. Faça o LOGIN no site.\n"
    "2. Navegue até a tela inicial do PMIB.\n"
    "3. Clique abaixo para iniciar a automação em lote."
)
MSG_EXCEL_BLOQUEADO = (
    "O arquivo _STATUS_PMIB está aberto no Excel.\n\n"
    "Por favor, FECHE O ARQUIVO e clique em 'Tentar Novamente' para salvar o "
    "status da ficha concluída."
)


def msg_excel_bloqueado(caminho: object) -> str:
    """A mesma mensagem, NOMEANDO o arquivo travado.

    [CP D] Quando a janela passou a servir os 7 pontos de gravação que antes
    falhavam calados, "o arquivo _STATUS_PMIB" deixou de bastar: o `pdm` grava
    ficha e template, o `analyzer` grava relatório, o `autospec` grava a ficha
    preenchida. Dizer QUAL arquivo fechar é a diferença entre o usuário
    resolver em 5 segundos e ficar procurando.
    """
    import os

    nome = os.path.basename(str(caminho)) or str(caminho)
    return (
        f"O arquivo '{nome}' está aberto em outro programa (provavelmente o "
        "Excel), e por isso não pôde ser salvo.\n\n"
        "FECHE O ARQUIVO e clique em 'Tentar Novamente'."
    )


# =============================================================================
# [CP B] As 4 pausas de login que eram `messagebox.showinfo`
# =============================================================================
# Textos PRESERVADOS: cada um diz o que já dizia. Só a forma mudou, para a dos
# passos numerados do modelo. Duas delas carregam instrução específica de qual
# página abrir — isso é informação, não ruído, e some se uniformizarmos.
MSG_LOGIN_APAGAR_LMR = (
    "O navegador foi aberto.\n\n"
    "1. Faça o LOGIN no site.\n"
    "2. Clique abaixo para começar a EXCLUSÃO."
)
MSG_LOGIN_LMR = (
    "O navegador foi aberto.\n\n"
    "1. Faça o LOGIN no site.\n"
    "2. Clique abaixo para começar."
)
MSG_LOGIN_NOVA_FICHA = (
    "O navegador foi aberto.\n\n"
    "1. Faça o LOGIN no portal.\n"
    "2. Navegue até a página com o botão 'Nova Ficha'.\n"
    "3. Clique abaixo quando estiver pronto."
)
MSG_LOGIN_PAGINA_PRINCIPAL = (
    "O navegador foi aberto.\n\n"
    "1. Faça o LOGIN no portal.\n"
    "2. Navegue até a página PRINCIPAL (onde fica a barra de pesquisa).\n"
    "3. Clique abaixo quando estiver pronto."
)

# Rótulo do botão na tela de exclusão de LMR — ação destrutiva.
TEXTO_COMECAR_EXCLUSAO = "COMEÇAR A EXCLUSÃO"


def msg_falha_ao_salvar(nome_secao: str) -> str:
    """Mensagem do `ModuloUploadConditions` quando uma aba não salva."""
    return (
        f"Falha ao salvar a aba '{nome_secao}'. Ocorreu um erro no site.\n\n"
        "1. Resolva o problema no navegador.\n"
        "2. Clique em SALVAR no site.\n"
        "3. Clique no botão abaixo para continuar."
    )


def msg_ficha_preenchida(pmib: str) -> str:
    """Mensagem do `ModuloCopiaFichas` ao terminar uma ficha."""
    return (
        f"Ficha {pmib} preenchida!\n\n"
        "Verifique na tela e copie as pendências (se houverem) do painel ao "
        "lado.\nApós clicar em SALVAR no site, clique no botão abaixo."
    )


class _DialogoDeAcaoManual(ctk.CTkToplevel):
    """Base das janelas que param o robô à espera do usuário.

    Cuida do que as cópias repetiam: título, geometria, `-topmost`, o texto
    centralizado com `wraplength`, e — o mais fácil de esquecer — ligar o
    fechamento no "X" a uma ação que SOLTA o worker. Sem isso, fechar a janela
    deixa a thread do robô presa em `wait()` para sempre.
    """

    def __init__(self, master, *, titulo: str, mensagem: str, geometria: str, pady_texto: int):
        super().__init__(master)
        self.title(titulo)
        self.geometry(geometria)
        # Sem grab_set() -- ver o docstring do módulo.
        self.attributes("-topmost", True)

        ctk.CTkLabel(
            self,
            text=mensagem,
            font=theme.FONTE_CORPO,
            wraplength=400,
            justify="center",
        ).pack(pady=pady_texto, padx=20, expand=True)


class PausaLoginDialog(_DialogoDeAcaoManual):
    """"Ação Manual Necessária" com um botão só: CONTINUAR AUTOMAÇÃO.

    Uso (a partir da thread da interface)::

        PausaLoginDialog(self, mensagem=dialogs.MSG_LOGIN_LOTE,
                         evento_espera=evento)
    """

    def __init__(
        self,
        master,
        *,
        mensagem: str,
        evento_espera,
        texto_botao: str = TEXTO_CONTINUAR,
    ):
        super().__init__(
            master,
            titulo="Ação Manual Necessária",
            mensagem=mensagem,
            geometria="450x250",
            pady_texto=30,
        )
        self._evento = evento_espera

        # Fechar no "X" tem de soltar o robô, igual ao botão.
        self.protocol("WM_DELETE_WINDOW", self.liberar)

        self.botao = ctk.CTkButton(
            self,
            text=texto_botao,
            command=self.liberar,
            fg_color=theme.COLORS["primary"],
            hover_color=theme.COLORS["primary_hover"],
            height=45,
            font=theme.FONTE_BOTAO,
        )
        self.botao.pack(pady=(0, 20))

    def liberar(self) -> None:
        """Solta o worker e fecha."""
        self._evento.set()
        self.destroy()


class RetryLockDialog(_DialogoDeAcaoManual):
    """"Arquivo Bloqueado": Tentar Novamente × Ignorar e Continuar.

    A decisão volta pelo dicionário `resultado`, na chave ``"retry"`` — o
    mesmo contrato que `_mostrar_janela_retry` já usava, para que o worker do
    lado de lá não precise mudar.

    Fechar no "X" equivale a CANCELAR: a alternativa seria repetir uma
    gravação que o usuário acabou de recusar.
    """

    def __init__(self, master, *, mensagem: str = MSG_EXCEL_BLOQUEADO, evento_espera, resultado: dict):
        super().__init__(
            master,
            titulo="Arquivo Bloqueado",
            mensagem=mensagem,
            geometria="450x200",
            pady_texto=20,
        )
        self._evento = evento_espera
        self._resultado = resultado

        self.protocol("WM_DELETE_WINDOW", self.cancelar)

        botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.pack(pady=(0, 20))

        self.botao_repetir = ctk.CTkButton(
            botoes,
            text="Tentar Novamente",
            command=self.repetir,
            fg_color=theme.COLORS["primary"],
            width=150,
            height=40,
        )
        self.botao_repetir.pack(side="left", padx=10)

        self.botao_cancelar = ctk.CTkButton(
            botoes,
            text="Ignorar e Continuar",
            command=self.cancelar,
            fg_color="transparent",
            border_width=1,
            border_color="#555",
            text_color=theme.COR_TEXTO_APOIO,
            width=150,
            height=40,
        )
        self.botao_cancelar.pack(side="left", padx=10)

    def repetir(self) -> None:
        self._resultado["retry"] = True
        self._evento.set()
        self.destroy()

    def cancelar(self) -> None:
        self._resultado["retry"] = False
        self._evento.set()
        self.destroy()


class TabelaSelecaoDialog(ctk.CTkToplevel):
    """Tabela (`ttk.Treeview`) para escolher várias linhas — Confirmar/Cancelar.

    Consolida `JanelaSelecao` (recebia um DataFrame) e `JanelaSelecaoDuplicadas`
    (recebia uma lista de dicionários). As duas montavam o mesmo Treeview com
    scrollbars e devolviam a escolha por callback; o que mudava era a origem
    dos dados e se tudo vinha pré-marcado.

    Por isso este diálogo recebe `colunas` e `linhas` já prontas, e não um
    DataFrame: ele não precisa saber de pandas para desenhar uma tabela, e o
    chamador é quem sabe de onde os dados vêm. Use `TabelaSelecaoDialog.de_dataframe`
    quando a origem for um DataFrame.

    O identificador de cada linha é a CHAVE que volta no callback
    ------------------------------------------------------------
    `linhas` é uma sequência de pares `(chave, valores)`. A `chave` é o que o
    chamador recebe de volta — o índice do DataFrame, a posição na fila, um id
    qualquer. Isso não é detalhe: o defeito clássico desta tela é devolver a
    posição VISUAL da linha quando a origem estava filtrada ou reordenada, e aí
    o lote processa a ficha errada sem nenhum erro aparecer.
    """

    def __init__(
        self,
        master,
        *,
        colunas,
        linhas,
        titulo: str = "Seleção de Itens",
        instrucao: str = "Selecione as linhas para processar:",
        geometria: str = "900x600",
        larguras: dict | None = None,
        preselecionar_tudo: bool = False,
        texto_confirmar: str = "Confirmar Seleção",
        com_cancelar: bool = True,
        modal: bool = True,
        ao_confirmar=None,
    ):
        super().__init__(master)
        self.title(titulo)
        self.geometry(geometria)
        self.attributes("-topmost", True)
        # Modal por PADRÃO aqui (ao contrário dos diálogos de pausa): as duas
        # janelas que esta classe substitui chamavam `grab_set()`, e faz
        # sentido — a tela de trás não tem o que fazer enquanto a escolha do
        # lote não vem. Ver a nota longa no `SelecaoMultiplaDialog`.
        if modal:
            self.transient(master)
            self.grab_set()

        self._ao_confirmar = ao_confirmar
        self._chaves = [str(chave) for chave, _ in linhas]

        ctk.CTkLabel(self, text=instrucao, font=theme.FONTE_SECAO).pack(pady=10)

        quadro = ctk.CTkFrame(self)
        quadro.pack(fill="both", expand=True, padx=10, pady=10)

        barra_y = ttk.Scrollbar(quadro, orient="vertical")
        barra_x = ttk.Scrollbar(quadro, orient="horizontal")

        self.tree = ttk.Treeview(
            quadro,
            columns=list(colunas),
            show="headings",
            yscrollcommand=barra_y.set,
            xscrollcommand=barra_x.set,
            selectmode="extended",
        )
        barra_y.config(command=self.tree.yview)
        barra_x.config(command=self.tree.xview)
        barra_y.pack(side="right", fill="y")
        barra_x.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)

        larguras = larguras or {}
        for coluna in colunas:
            self.tree.heading(coluna, text=coluna)
            self.tree.column(coluna, **larguras.get(coluna, {"width": 120}))

        for chave, valores in linhas:
            self.tree.insert("", "end", iid=str(chave), values=list(valores))
            if preselecionar_tudo:
                self.tree.selection_add(str(chave))

        botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.pack(pady=10)

        self.botao_confirmar = ctk.CTkButton(
            botoes,
            text=texto_confirmar,
            command=self.confirmar,
            fg_color=theme.COLORS["primary"],
        )
        self.botao_confirmar.pack(side="left", padx=10)

        self.botao_cancelar = None
        if com_cancelar:
            self.botao_cancelar = ctk.CTkButton(
                botoes, text="Cancelar", command=self.destroy, fg_color="#3A3A3A"
            )
            self.botao_cancelar.pack(side="left", padx=10)

    @classmethod
    def de_dataframe(cls, master, dataframe, **kwargs):
        """Constrói a partir de um DataFrame, como `JanelaSelecao` fazia.

        A chave de cada linha é o ÍNDICE do DataFrame — não a posição —, que é
        o que `JanelaSelecao` devolvia (`[int(i) for i in tree.selection()]`).
        """
        linhas = [
            (indice, linha.to_numpy().tolist())
            for indice, linha in dataframe.iterrows()
        ]
        return cls(master, colunas=list(dataframe.columns), linhas=linhas, **kwargs)

    @property
    def selecionados(self) -> list[str]:
        """As chaves marcadas, na ordem em que a tabela as devolve."""
        return list(self.tree.selection())

    def confirmar(self) -> None:
        selecionados = self.selecionados
        if not selecionados:
            # Confirmar com nada marcado seria "processar zero itens", que na
            # prática é um cancelamento silencioso -- e o usuário fica sem
            # saber por que nada aconteceu.
            messagebox.showwarning("Aviso", "Selecione ao menos um item.")
            return
        if self._ao_confirmar is not None:
            self._ao_confirmar(selecionados)
        self.destroy()


class SelecaoMultiplaDialog(ctk.CTkToplevel):
    """Lista simples (`tk.Listbox`) para escolher vários itens de texto.

    A variante leve do `TabelaSelecaoDialog`: quando os itens são strings soltas
    (códigos PMIB, nomes de ficha) e não linhas de uma tabela com colunas.
    Consolida os popups montados à mão dentro de `ModuloPDM` e
    `ModuloUploadConditions`.

    Devolve os TEXTOS marcados, que é o que os dois popups faziam
    (`[lb.get(i) for i in lb.curselection()]`).
    """

    def __init__(
        self,
        master,
        *,
        itens,
        titulo: str = "Seleção",
        instrucao: str = "Selecione um ou mais itens:",
        geometria: str = "500x500",
        texto_confirmar: str = "Confirmar Seleção",
        modal: bool = False,
        com_selecionar_todos: bool = False,
        devolver_indices: bool = False,
        estilo_lista: dict | None = None,
        fonte_lista: tuple | None = None,
        fonte_instrucao: tuple | None = None,
        ao_confirmar=None,
    ):
        super().__init__(master)
        self.title(titulo)
        self.geometry(geometria)
        self.attributes("-topmost", True)
        # `modal=True` chama `grab_set()`, e AQUI isso é o certo -- o oposto do
        # que vale para os diálogos de pausa lá em cima. A diferença não é
        # estilo, é para que serve cada um:
        #
        #   * o diálogo de PAUSA fica aberto enquanto o usuário trabalha em
        #     OUTRO lugar (o navegador, o console do app para copiar
        #     pendências). Torná-lo modal tira dele exatamente o que ele
        #     precisa fazer -- foi o defeito que o comentário original
        #     registrava;
        #   * este aqui PERGUNTA e a tela não tem o que fazer sem a resposta:
        #     quem chama segue com `wait_window()`. Sem `grab_set()`, o usuário
        #     pode clicar de volta na tela de trás e disparar a mesma ação de
        #     novo, com o diálogo ainda aberto.
        if modal:
            self.transient(master)
            self.grab_set()

        self._ao_confirmar = ao_confirmar
        self._devolver_indices = devolver_indices

        ctk.CTkLabel(self, text=instrucao, font=fonte_instrucao or theme.FONTE_SUBTITULO).pack(pady=10)

        quadro = ctk.CTkFrame(self, fg_color="transparent")
        quadro.pack(fill="both", expand=True, padx=20, pady=(10 if not estilo_lista else 5))

        # Duas das quatro variantes pintavam a lista (fundo escuro, seleção na
        # cor primária) e duas usavam a Listbox crua. `estilo_lista` carrega
        # essa diferença em vez de uniformizar — uniformizar mudaria a
        # aparência de metade delas.
        opcoes_lista = {
            "selectmode": "multiple",
            "font": fonte_lista or theme.FONTE_CONSOLE,
        }
        opcoes_lista.update(estilo_lista or {})

        self.scrollbar = tk.Scrollbar(quadro)
        self.scrollbar.pack(side="right", fill="y")

        self.listbox = tk.Listbox(quadro, yscrollcommand=self.scrollbar.set, **opcoes_lista)
        self.listbox.pack(side="left", fill="both", expand=True)
        self.scrollbar.config(command=self.listbox.yview)

        for item in itens:
            self.listbox.insert("end", item)

        botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.pack(pady=15)

        self.botao_todos = None
        if com_selecionar_todos:
            self.botao_todos = ctk.CTkButton(
                botoes,
                text="Selecionar Todos",
                command=self.selecionar_todos,
                fg_color="#3A3A3A",
                width=150,
            )
            self.botao_todos.pack(side="left", padx=10)

        self.botao_confirmar = ctk.CTkButton(
            botoes,
            text=texto_confirmar,
            command=self.confirmar,
            fg_color=theme.COLORS["primary"],
            width=150,
        )
        self.botao_confirmar.pack(side="left", padx=10)

    @property
    def selecionados(self) -> list[str]:
        """Os TEXTOS marcados — o que os popups de lista faziam."""
        return [self.listbox.get(i) for i in self.listbox.curselection()]

    @property
    def indices(self) -> list[int]:
        """As POSIÇÕES marcadas.

        Duas das variantes usavam o índice para voltar ao dicionário de origem
        (`dados_dict_lista[i]`). Devolver o texto ali obrigaria a tela a
        procurar o item pela string — frágil e desnecessário.
        """
        return [int(i) for i in self.listbox.curselection()]

    def selecionar_todos(self) -> None:
        self.listbox.select_set(0, "end")

    def confirmar(self) -> None:
        escolha = self.indices if self._devolver_indices else self.selecionados
        if self._ao_confirmar is not None:
            self._ao_confirmar(escolha)
        self.destroy()
