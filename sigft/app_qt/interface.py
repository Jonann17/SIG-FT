"""O ÚNICO caminho de uma thread até um widget.

No CustomTkinter isso era disciplina: `self.after(0, ...)` em cada lugar, e
onde alguém esqueceu, o widget era tocado fora da thread da interface -- no
macOS isso derruba o app (`cria_fichas.py` abria janela de dentro do robô).
Aqui é mecanismo: um sinal Qt com conexão em FILA entrega a função na thread
da interface, venha a chamada de onde vier.
"""
from __future__ import annotations

import threading
import traceback

from PySide6.QtCore import QObject, Qt, Signal, Slot


class _Ponte(QObject):
    executar = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.executar.connect(self._rodar, Qt.ConnectionType.QueuedConnection)

    @Slot(object)
    def _rodar(self, pacote) -> None:
        func, args = pacote
        try:
            func(*args)
        except Exception:  # noqa: BLE001 -- uma falha não pode matar o canal
            traceback.print_exc()


_ponte: _Ponte | None = None
_thread_da_interface: int | None = None


def instalar() -> None:
    """Cria a ponte na thread atual (a da interface). Chamar uma vez, cedo."""
    global _ponte, _thread_da_interface
    if _ponte is None:
        _ponte = _Ponte()
        _thread_da_interface = threading.get_ident()


def na_thread_da_interface() -> bool:
    return threading.get_ident() == _thread_da_interface


def na_interface(func, *args) -> None:
    """Agenda `func(*args)` na thread da interface. Chamável de qualquer thread."""
    if _ponte is None:
        raise RuntimeError("sigft.app_qt.interface.instalar() não foi chamado")
    _ponte.executar.emit((func, args))
