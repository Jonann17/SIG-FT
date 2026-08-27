"""Seletores de arquivo/pasta e a fila de fichas — UMA implementação de cada.

Checkpoint 7.2 do plano (`docs/refatoracao/PLANO_REFATORACAO.md`, Fase 7).

O diagnóstico do plano (§1.4) conta 20+ cópias de "seletor de arquivo com
label de status e mudança de cor" e 2 cópias idênticas da "listbox de fichas
com Adicionar/Remover/Limpar". Este módulo é cada uma dessas coisas, uma vez.

A memória de caminhos é COMPORTAMENTO EMBUTIDO, não chamada manual
--------------------------------------------------------------------
Esta é a exigência explícita do CP 7.2: *"os pickers usam nativamente a
memória de caminhos do CP 1.5 (cada `FilePickerRow` declara sua
chave/categoria — a memória vira comportamento embutido, não chamada
manual)"*.

Na prática: a tela declara `chave="pdm.template"` e `categoria="excel"` UMA
vez, ao construir a linha, e nunca mais chama `file_dialogs`. Antes, cada
`command=` repetia a chamada — e um esquecimento ali fazia aquele campo
específico perder a memória, silenciosamente, sem quebrar nada. É o tipo de
regressão que só aparece como "esse botão sempre abre na pasta errada".

Zero redesign
-------------
Os valores visuais (cinzas `#3A3A3A`/`#454545` do botão, o `#1E1E1E` do fundo
da lista, a fonte "Segoe UI" 11 da listbox, os `padx`/`pady`) são os que as
telas já usavam, copiados. O texto "Nenhum arquivo selecionado" em cinza que
vira o nome do arquivo em verde é o comportamento existente, não uma ideia
nova.
"""
from __future__ import annotations

import os
import tkinter as tk

import customtkinter as ctk

from sigft.app import file_dialogs, theme

# Cinzas do botão de seleção. Literais repetidos ~20 vezes no `frontend.py`;
# não estão no `COLORS` porque nunca foram nomeados — mas são tema.
COR_BOTAO_SELECAO = "#3A3A3A"
COR_BOTAO_SELECAO_HOVER = "#454545"

# Fundo e fonte da listbox de fichas (é um `tk.Listbox` puro, não CustomTkinter
# — por isso as cores vão explícitas: ela não herda tema).
COR_FUNDO_LISTA = "#1E1E1E"
FONTE_LISTA = ("Segoe UI", 11)

TEXTO_SEM_ARQUIVO = "Nenhum arquivo selecionado"
TEXTO_SEM_PASTA = "Nenhuma pasta selecionada"

# Como cada ficha aparece na fila. O emoji e os DOIS espaços depois dele são
# literais das duas cópias — `f" 📊  {os.path.basename(f)}"`. Parecem detalhe
# bobo, mas são a aparência da lista, e a Fase 7 é zero redesign.
PREFIXO_ITEM = " 📊  "


class _LinhaSeletora(ctk.CTkFrame):
    """Base: botão à esquerda, rótulo de status à direita.

    O rótulo começa cinza com o texto "vazio" e passa a verde (`accent`) com o
    nome do que foi escolhido — o padrão que as 20+ cópias seguiam.
    """

    def __init__(
        self,
        master,
        *,
        texto_botao: str,
        texto_vazio: str,
        largura_botao: int = 240,
        pintar_botao: bool = True,
        ao_escolher=None,
        **kwargs,
    ):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)

        self._texto_vazio = texto_vazio
        self._pintar_botao = pintar_botao
        self._ao_escolher = ao_escolher
        self._valor = None

        self.botao = ctk.CTkButton(
            self,
            text=texto_botao,
            width=largura_botao,
            command=self._abrir_dialogo,
            fg_color=COR_BOTAO_SELECAO,
            hover_color=COR_BOTAO_SELECAO_HOVER,
            font=theme.FONTE_CORPO_MIUDO,
        )
        self.botao.pack(side="left")

        self.label_status = ctk.CTkLabel(
            self, text=texto_vazio, text_color=theme.COR_TEXTO_APOIO
        )
        self.label_status.pack(side="left", padx=15)

    # -- API pública ---------------------------------------------------------
    @property
    def valor(self):
        """O que está selecionado: `str`, tupla de `str`, ou `None`."""
        return self._valor

    def limpar(self) -> None:
        """Volta ao estado vazio (cinza), como o `_reset` das telas fazia."""
        self._valor = None
        self.label_status.configure(
            text=self._texto_vazio, text_color=theme.COR_TEXTO_APOIO
        )
        if self._pintar_botao:
            self.botao.configure(fg_color=COR_BOTAO_SELECAO)

    def definir(self, valor, rotulo: str) -> None:
        """Marca como selecionado: rótulo em verde e botão pintado.

        As DUAS coisas mudam de cor — é o "botões de arquivo que ficam verdes
        quando selecionados" que a regra da Fase 7 cita como referência
        visual. O rótulo usa `accent`; o botão, `primary` (era o que as telas
        faziam: `btn.configure(fg_color=COLORS["primary"])`).

        `pintar_botao=False` atende as telas que só mudavam o rótulo — o
        `ModuloPDM` é assim, e uniformizá-lo seria redesign.
        """
        self._valor = valor
        self.label_status.configure(text=rotulo, text_color=theme.COLORS["accent"])
        if self._pintar_botao:
            self.botao.configure(fg_color=theme.COLORS["primary"])

    # -- a implementar -------------------------------------------------------
    def _abrir_dialogo(self) -> None:
        raise NotImplementedError

    def _notificar(self) -> None:
        if self._ao_escolher is not None:
            self._ao_escolher(self._valor)


class FilePickerRow(_LinhaSeletora):
    """Seleciona UM arquivo. Mostra o nome-base em verde.

    `chave`/`categoria` são os da memória de caminhos (CP 1.5) e ficam
    declarados aqui, uma vez.
    """

    def __init__(
        self,
        master,
        *,
        chave: str,
        categoria: str,
        texto_botao: str,
        titulo: str | None = None,
        filetypes=None,
        texto_vazio: str = TEXTO_SEM_ARQUIVO,
        ao_escolher=None,
        dialog_fn=None,
        **kwargs,
    ):
        super().__init__(
            master,
            texto_botao=texto_botao,
            texto_vazio=texto_vazio,
            ao_escolher=ao_escolher,
            **kwargs,
        )
        self._chave = chave
        self._categoria = categoria
        self._titulo = titulo
        self._filetypes = filetypes
        self._dialog_fn = dialog_fn

    def _abrir_dialogo(self) -> None:
        caminho = file_dialogs.ask_open_file(
            self._chave,
            self._categoria,
            titulo=self._titulo,
            filetypes=self._filetypes,
            dialog_fn=self._dialog_fn,
        )
        # Cancelar o diálogo NÃO pode apagar o que já estava escolhido — era o
        # comportamento das telas (o `if f:` antes de mexer no label).
        if not caminho:
            return
        self.definir(caminho, os.path.basename(caminho))
        self._notificar()


class MultiFilePickerRow(_LinhaSeletora):
    """Seleciona N arquivos. Mostra "{n} arquivos selecionados" em verde."""

    def __init__(
        self,
        master,
        *,
        chave: str,
        categoria: str,
        texto_botao: str,
        titulo: str | None = None,
        filetypes=None,
        texto_vazio: str = TEXTO_SEM_ARQUIVO,
        ao_escolher=None,
        dialog_fn=None,
        **kwargs,
    ):
        super().__init__(
            master,
            texto_botao=texto_botao,
            texto_vazio=texto_vazio,
            ao_escolher=ao_escolher,
            **kwargs,
        )
        self._chave = chave
        self._categoria = categoria
        self._titulo = titulo
        self._filetypes = filetypes
        self._dialog_fn = dialog_fn

    def _abrir_dialogo(self) -> None:
        caminhos = file_dialogs.ask_open_files(
            self._chave,
            self._categoria,
            titulo=self._titulo,
            filetypes=self._filetypes,
            dialog_fn=self._dialog_fn,
        )
        if not caminhos:
            return
        self.definir(tuple(caminhos), f"{len(caminhos)} arquivos selecionados")
        self._notificar()


class FolderPickerRow(_LinhaSeletora):
    """Seleciona UMA pasta. Mostra o nome da pasta em verde."""

    def __init__(
        self,
        master,
        *,
        chave: str,
        categoria: str = "pasta",
        texto_botao: str,
        titulo: str | None = None,
        texto_vazio: str = TEXTO_SEM_PASTA,
        ao_escolher=None,
        dialog_fn=None,
        **kwargs,
    ):
        super().__init__(
            master,
            texto_botao=texto_botao,
            texto_vazio=texto_vazio,
            ao_escolher=ao_escolher,
            **kwargs,
        )
        self._chave = chave
        self._categoria = categoria
        self._titulo = titulo
        self._dialog_fn = dialog_fn

    def _abrir_dialogo(self) -> None:
        pasta = file_dialogs.ask_directory(
            self._chave,
            self._categoria,
            titulo=self._titulo,
            dialog_fn=self._dialog_fn,
        )
        if not pasta:
            return
        # Uma pasta terminada em barra tem `basename` vazio — as telas já
        # tratavam isso com `os.path.basename(d) if os.path.basename(d) else d`.
        self.definir(pasta, os.path.basename(pasta) or pasta)
        self._notificar()


class FileQueueList(ctk.CTkFrame):
    """A lista de fichas com Adicionar / Remover Seleção / Limpar Tudo.

    Substitui as DUAS cópias idênticas (`ModuloUploadConditions` e
    `ModuloUploadTechSpecs`). O contador no topo ("Planilhas PMIB Selecionadas
    (N)") acompanha a lista sozinho — nas cópias, era responsabilidade de cada
    método que mexia na lista lembrar de atualizá-lo.

    A lista é um `tk.Listbox` puro (não há equivalente no CustomTkinter), por
    isso as cores vão explícitas: ela não herda o tema.
    """

    def __init__(
        self,
        master,
        *,
        chave: str,
        categoria: str = "excel",
        rotulo: str = "Planilhas PMIB Selecionadas",
        titulo_dialogo: str | None = None,
        filetypes=None,
        texto_adicionar: str = "Adicionar Fichas",
        prefixo_item: str = PREFIXO_ITEM,
        ao_mudar=None,
        dialog_fn=None,
        **kwargs,
    ):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)

        self._chave = chave
        self._categoria = categoria
        self._rotulo = rotulo
        self._titulo_dialogo = titulo_dialogo
        self._filetypes = filetypes
        self._prefixo_item = prefixo_item
        self._ao_mudar = ao_mudar
        self._dialog_fn = dialog_fn
        self._arquivos: list[str] = []

        self.label_contador = ctk.CTkLabel(
            master, text=f"{rotulo} (0)", font=("Roboto", 12, "bold")
        )

        self.listbox = tk.Listbox(
            self,
            selectmode=tk.EXTENDED,
            bg=COR_FUNDO_LISTA,
            fg=theme.COLORS["text_light"],
            selectbackground=theme.COLORS["primary"],
            selectforeground="white",
            highlightthickness=0,
            borderwidth=0,
            font=FONTE_LISTA,
            activestyle="none",
        )
        self.listbox.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)

        self.scrollbar = tk.Scrollbar(self, bg=theme.COR_CARTAO, troughcolor=COR_BOTAO_SELECAO)
        self.scrollbar.pack(side="left", fill="y", pady=5)
        self.listbox.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.listbox.yview)

        botoes = ctk.CTkFrame(self, fg_color="transparent", width=120)
        botoes.pack(side="right", fill="y", padx=(10, 0))

        self.botao_adicionar = ctk.CTkButton(
            botoes, text=texto_adicionar, command=self.adicionar, fg_color=COR_BOTAO_SELECAO
        )
        self.botao_adicionar.pack(pady=5)

        self.botao_remover = ctk.CTkButton(
            botoes,
            text="Remover Seleção",
            command=self.remover_selecionados,
            fg_color=theme.COLORS["danger"],
        )
        self.botao_remover.pack(pady=5)

        self.botao_limpar = ctk.CTkButton(
            botoes,
            text="Limpar Tudo",
            command=self.limpar,
            fg_color="transparent",
            border_width=1,
            border_color="#555",
        )
        self.botao_limpar.pack(pady=5)

    # -- API pública ---------------------------------------------------------
    @property
    def arquivos(self) -> list[str]:
        """Cópia da fila — mexer no retorno não altera a lista."""
        return list(self._arquivos)

    def adicionar(self) -> None:
        escolhidos = file_dialogs.ask_open_files(
            self._chave,
            self._categoria,
            titulo=self._titulo_dialogo,
            filetypes=self._filetypes,
            dialog_fn=self._dialog_fn,
        )
        if not escolhidos:
            return
        for caminho in escolhidos:
            # Adicionar o mesmo arquivo duas vezes o processaria duas vezes.
            if caminho not in self._arquivos:
                self._arquivos.append(caminho)
        self._redesenhar()
        self._notificar("adicionou", len(escolhidos))

    def remover_selecionados(self) -> None:
        selecionados = sorted(self.listbox.curselection(), reverse=True)
        if not selecionados:
            return
        # De trás para frente: remover pela frente desloca os índices
        # seguintes, e a seleção múltipla passa a apagar a linha errada.
        for indice in selecionados:
            del self._arquivos[indice]
        self._redesenhar()
        self._notificar("removeu", len(selecionados))

    def limpar(self) -> None:
        self._arquivos.clear()
        self._redesenhar()
        self._notificar("limpou", 0)

    def definir(self, caminhos) -> None:
        """Substitui a fila inteira (usado ao restaurar estado)."""
        self._arquivos = list(caminhos)
        self._redesenhar()

    # -- interno -------------------------------------------------------------
    def _notificar(self, acao: str, quantidade: int) -> None:
        """Avisa a tela para que ela escreva no console dela.

        As duas cópias logavam "N arquivos selecionados. Total na fila: M" — o
        texto é da TELA, não do widget, então ele fica lá.
        """
        if self._ao_mudar is not None:
            self._ao_mudar(acao, quantidade, len(self._arquivos))

    def _redesenhar(self) -> None:
        self.listbox.delete(0, tk.END)
        for caminho in self._arquivos:
            self.listbox.insert(tk.END, f"{self._prefixo_item}{os.path.basename(caminho)}")
        self.label_contador.configure(text=f"{self._rotulo} ({len(self._arquivos)})")
