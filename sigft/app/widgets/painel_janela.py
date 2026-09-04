"""Janelas que a Home abre — painéis pesados e o mural de atividades.

[2026-09-03] Pedido do usuário: *"precisamos diminuir a densidade de informação
da home criando botões que abrem janelas"*. Os painéis de **configuração de
IA** e de **gastos de IA** saem da Home e passam a morar aqui.

Por que não usar o `PausaLoginDialog`
--------------------------------------
Aqueles diálogos existem para PARAR o robô e esperar uma decisão: têm
`threading.Event`, botão único e o contrato de soltar o worker. Estes aqui não
param nada — o usuário abre, olha, fecha. Reaproveitar aquela classe traria o
mecanismo de espera junto, sem ninguém para esperar.

O que estes compartilham com aqueles é o que importa: **minimizam**, seguem o
tema e não travam a janela principal (sem `grab_set`) — o padrão que o usuário
apontou como o bom em 2026-08-28.
"""
from __future__ import annotations

import customtkinter as ctk

from sigft.app import theme


class JanelaPainel(ctk.CTkToplevel):
    """Janela que hospeda um painel construído por um `montar(parent)`.

    O painel não sabe que está numa janela: recebe um `parent` e desenha nele.
    É o que permite os painéis da Home mudarem de casa sem serem reescritos.
    """

    def __init__(self, master, *, titulo: str, montar, geometria: str = "900x680"):
        super().__init__(master)
        self.title(titulo)
        self.geometry(geometria)
        # Sem grab_set: a janela principal continua utilizável. Mesmo racional
        # dos diálogos de pausa (ver widgets/dialogs.py).
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))

        self.conteudo = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.conteudo.pack(fill="both", expand=True, padx=10, pady=10)

        montar(self.conteudo)

        ctk.CTkButton(
            self, text="Fechar", command=self.destroy,
            fg_color=theme.COLORS["primary"], hover_color=theme.COLORS["primary_hover"],
            width=120,
        ).pack(pady=(0, 12))
