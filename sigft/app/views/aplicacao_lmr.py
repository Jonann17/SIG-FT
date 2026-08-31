"""Seção "Aplicação LMR" — as duas telas de LMR num lugar só, em abas.

[2026-08-28] Pedido do usuário: *"quero apenas que os módulos de aplicação LMR
virem um só na interface. Daí dentro da seção Aplicação LMR tenha duas abas,
para upload e exclusão"*.

Antes eram duas entradas separadas na barra lateral ("7.1. LMR (Upload)" e
"7.2. Apagar LMR"), o que espalhava por dois lugares duas operações sobre a
MESMA aba do portal e a MESMA coluna da planilha — inclusive com o risco de
alguém abrir a tela errada, já que uma delas é destrutiva.

O molde é o do `ModuloCriaFichas`, que já resolve isto no projeto desde antes:
UM header, um `CTkTabview`, UM console compartilhado. Não é padrão novo.

Por que o console é compartilhado
----------------------------------
Dois consoles dividiriam o log em dois lugares. Como as duas abas conversam
com o mesmo portal e a mesma planilha, acompanhar um trabalho exigiria olhar
para as duas caixas e reconstruir a ordem de cabeça — o pior jeito possível de
seguir um lote. Com um console só, a ordem dos eventos é a ordem na tela.
"""
from __future__ import annotations

from sigft.app.theme import COLORS
from sigft.app.views.apagar_lmr import ModuloApagarLMR
from sigft.app.views.lmr import ModuloLMR
from sigft.app.widgets.module_frame import ModuleFrame

import customtkinter as ctk


class ModuloAplicacaoLMR(ModuleFrame):
    """Header + abas (Upload / Exclusão) + console compartilhado."""

    def __init__(self, parent, controller):
        super().__init__(
            parent,
            controller,
            titulo="Aplicação LMR",
            # O conteúdo é o Tabview, que precisa do espaço; o console fica com
            # a altura padrão embaixo, como nas outras telas.
            peso_conteudo=3,
            console_sticky="nsew",
        )

    def _build_ui(self):
        self.tabview = ctk.CTkTabview(self.content)
        self.tabview.pack(fill="both", expand=True)

        aba_upload = self.tabview.add("Upload de Aplicações")
        aba_exclusao = self.tabview.add("Exclusão de Aplicações")

        # As duas telas entram EMBUTIDAS: sem header e sem console próprios,
        # escrevendo no console desta seção. O `_build_ui` de cada uma não
        # mudou — elas continuam desenhando em `self.content`, que no modo
        # embutido é o espaço da aba.
        self.tela_upload = ModuloLMR(
            aba_upload,
            self.controller,
            embutida=True,
            console_externo=self.console,
        )
        self.tela_upload.pack(fill="both", expand=True)

        self.tela_exclusao = ModuloApagarLMR(
            aba_exclusao,
            self.controller,
            embutida=True,
            console_externo=self.console,
        )
        self.tela_exclusao.pack(fill="both", expand=True)

        # A aba destrutiva fica com o rótulo em vermelho no aviso interno dela
        # (já era assim). Aqui, só garantimos que a aba que abre por padrão é a
        # de Upload — abrir direto na tela que APAGA seria um convite ao erro.
        self.tabview.set("Upload de Aplicações")

    # -- atalhos, para quem já conhecia os nomes antigos ---------------------
    @property
    def cor_aviso_destrutivo(self):
        """Mantida para o caso de alguém estilizar a aba de exclusão."""
        return COLORS["danger"]
