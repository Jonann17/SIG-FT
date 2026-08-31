"""O esqueleto de uma tela de módulo: header + conteúdo + console (+ progresso).

Checkpoint 7.1 do plano (`docs/refatoracao/PLANO_REFATORACAO.md`, Fase 7).

As 12 telas do `frontend.py` abrem com o MESMO bloco de ~12 linhas: configura
o grid, cria um header transparente com o título em Roboto 24 bold, cria
`self.content`, cria `self.console`, chama `self._build_ui()`. Este módulo é
esse bloco, uma vez só.

Zero redesign, e o que isso exige na prática
--------------------------------------------
Padronizar aqui é padronizar o PADRÃO DOMINANTE — não uniformizar à força.
As 12 telas concordam no esqueleto mas divergem em quatro detalhes, e cada
divergência é visível na tela:

* **peso da linha de conteúdo** — `weight=1` (7 telas), `weight=3` (2) e
  `weight=0` (3, onde o conteúdo deve ocupar só o necessário);
* **altura do console** — 150 px (6), 120 px (1) e SEM `height` (5, onde o
  grid o estica);
* **`sticky` do console** — `"ew"` (8) e `"nsew"` (4);
* **barra de progresso no esqueleto** — só o `ModuloPMIBManager` tem uma; nas
  outras a barra (quando existe) mora dentro do conteúdo, e não é problema
  daqui.

Forçar as 12 ao mesmo valor mudaria o layout de 5 telas — exatamente o que a
regra da fase proíbe. Então cada uma passa o que já usava, e o DEFAULT é o
valor dominante, de modo que a maioria não precise passar nada.
"""
from __future__ import annotations

import customtkinter as ctk

from sigft.app import theme
from sigft.app.widgets.console import ConsoleFrame
from sigft.app.widgets.espera import DialogosDeEspera


class ModuleFrame(DialogosDeEspera, ctk.CTkFrame):
    """Base das telas de módulo.

    A subclasse implementa `_build_ui()` e desenha DENTRO de `self.content`,
    exatamente como as telas fazem hoje.

    Parâmetros que reproduzem as divergências reais entre as 12 telas:

    `peso_conteudo`
        `weight` da linha 1 do grid (a do conteúdo). Padrão 1.
    `altura_console`
        Altura do console em px, ou `None` para não fixar altura (o grid
        estica). Padrão `theme.ALTURA_CONSOLE` (150).
    `console_sticky`
        `"ew"` (padrão) ou `"nsew"`.
    `console_pady`
        Padrão `theme.PADDING_Y`; duas telas usam tupla assimétrica.
    `com_progresso`
        Quando `True`, cria `self.progress_bar` entre o conteúdo e o console
        (row 2) e empurra o console para a row 3 — o arranjo do
        `ModuloPMIBManager`.
    """

    def __init__(
        self,
        parent,
        controller=None,
        *,
        titulo: str,
        cor_titulo: str | None = None,
        peso_conteudo: int = 1,
        altura_console: int | None = theme.ALTURA_CONSOLE,
        console_sticky: str = "ew",
        console_pady: int | tuple = theme.PADDING_Y,
        com_progresso: bool = False,
        largura_progresso: int = 600,
        altura_progresso: int = 12,
        cor_progresso: str | None = None,
        construir: bool = True,
        embutida: bool = False,
        console_externo=None,
    ):
        super().__init__(parent)
        self.controller = controller
        self.embutida = embutida

        # --- Tela EMBUTIDA (dentro da aba de outra tela) --------------------
        # [2026-08-28] Uma tela dentro de uma aba não pode trazer o próprio
        # header nem o próprio console: quem já está na seção "Aplicação LMR"
        # não precisa de um segundo título dizendo "Aplicação LMR", e dois
        # consoles na mesma janela dividem o log em dois lugares — o pior jeito
        # de acompanhar um lote.
        #
        # Então ela desenha DIRETO no espaço que recebeu e escreve no console
        # do pai. `self.content` continua sendo "onde desenhar", que é o que o
        # `_build_ui` de cada tela espera — por isso migrar uma tela para
        # dentro de uma aba não exige reescrever o `_build_ui` dela.
        if embutida:
            self.grid_columnconfigure(0, weight=1)
            self.grid_rowconfigure(0, weight=1)
            self.header = None
            self.label_titulo = None
            self.progress_bar = None
            self.console = console_externo
            # ROLÁVEL, e isso não é preferência: dentro de uma aba sobra menos
            # altura que numa tela inteira (o header e o console da seção
            # comem espaço), e o conteúdo que não cabe simplesmente SOME —
            # sem barra, sem aviso. Na primeira montagem da seção de LMR isso
            # cortou o último passo do "O robô irá:" da tela de exclusão, que
            # é justamente onde ela diz que vai apagar tudo.
            #
            # É o mesmo recurso que o `ModuloCriaFichas` já usa nas abas dele.
            self.content = ctk.CTkScrollableFrame(self, fg_color="transparent")
            self.content.grid(row=0, column=0, sticky="nsew")
            if construir:
                self._build_ui()
            return

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=peso_conteudo)

        # --- Header ---------------------------------------------------------
        self.header = ctk.CTkFrame(self, height=theme.ALTURA_HEADER, fg_color="transparent")
        self.header.grid(row=0, column=0, sticky="ew", padx=theme.PADDING_X, pady=theme.PADDING_Y)
        self.label_titulo = ctk.CTkLabel(
            self.header,
            text=titulo,
            font=theme.FONTE_TITULO_MODULO,
            text_color=cor_titulo or theme.COLORS["text_white"],
        )
        self.label_titulo.pack(side="left")

        # --- Conteúdo -------------------------------------------------------
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=theme.PADDING_X, pady=theme.PADDING_Y)

        # --- Progresso (opcional) e console ---------------------------------
        linha_console = 2
        self.progress_bar = None
        if com_progresso:
            self.progress_bar = ctk.CTkProgressBar(
                self,
                width=largura_progresso,
                height=altura_progresso,
                progress_color=cor_progresso or theme.COLORS["primary"],
            )
            self.progress_bar.grid(row=2, column=0, padx=theme.PADDING_X, pady=(theme.PADDING_Y, 0))
            self.progress_bar.set(0)
            linha_console = 3

        self.console = ConsoleFrame(self, altura=altura_console)
        self.console.grid(
            row=linha_console,
            column=0,
            sticky=console_sticky,
            padx=theme.PADDING_X,
            pady=console_pady,
        )

        # `construir=False` existe para a subclasse que precisa preparar
        # atributos ANTES de desenhar (várias telas de hoje montam listas e
        # `StringVar` no `__init__` antes do `_build_ui`). Ela chama
        # `self._build_ui()` quando estiver pronta.
        if construir:
            self._build_ui()

    # -- a ser implementado pela tela ---------------------------------------
    def _build_ui(self) -> None:
        """Desenha os controles da tela dentro de `self.content`."""
        raise NotImplementedError(
            f"{type(self).__name__} precisa implementar _build_ui()."
        )

    # -- log ----------------------------------------------------------------
    def log(self, msg: object, nivel: str = "info", contexto: object | None = None) -> None:
        """Delega ao console — thread-safe. Assinatura do protocolo do CP 1.4.

        Existe para que as telas continuem chamando `self.log(...)`, como as 12
        já chamam: migrar uma tela não deve exigir reescrever cada chamada.
        """
        self.console.log(msg, nivel, contexto)
