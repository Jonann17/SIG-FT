"""O comando que abre a interface antiga (CustomTkinter), enquanto durar a transição.

Um lugar só para os três avisos que o dão: o console do `frontend.py` quando a
Qt não abre, a caixa da janela principal que não montou
(`catalogo.MSG_ABERTURA_FALHOU`) e a tela que não montou (`TelaComErro`).

Só biblioteca padrão: o `frontend.py` o importa justamente quando a Qt falhou.
Sai junto com o `--ctk`, no fim da transição.
"""
from __future__ import annotations

import os
import sys

# Este arquivo vive em <raiz>/sigft/core/; o `frontend.py` fica na raiz.
_FRONTEND = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "frontend.py")


def comando_da_interface_antiga() -> str:
    """No `.exe` é o próprio executável com `--ctk` (não há `frontend.py` para
    passar ao interpretador); rodando do código, o Python atual com o
    `frontend.py` e `--ctk`."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --ctk'
    return f'"{sys.executable}" "{_FRONTEND}" --ctk'
