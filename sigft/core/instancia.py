"""O mutex nomeado que deixa a atualização automática funcionar.

Por que isto existe
-------------------
**O Windows não deixa sobrescrever um `.exe` em execução.** Sem tratamento, a
atualização falha com "arquivo em uso" — o sintoma clássico de auto-update
quebrado, e o mais confuso: a pessoa clica em "atualizar", o instalador abre,
dá erro no meio e deixa a instalação pela metade.

A saída do Inno Setup é o `AppMutex`: o app cria um **mutex nomeado** ao abrir,
o instalador declara **o mesmo nome**, e com isso o Inno descobre que o SIG-FT
está rodando e o fecha antes de trocar os arquivos.

⚠️ **Os dois nomes têm de ser iguais**, e a divergência não dá erro nenhum —
só faz a atualização falhar. Por isso `tests/test_instalador.py` lê o `.iss` e
este módulo e reprova se divergirem.

O `AppUserModelID`
------------------
Segunda coisa que mora aqui, pelo mesmo motivo (um nome que precisa bater entre
o app e o instalador). O Windows agrupa janelas na barra de tarefas por esse
identificador. Se o atalho declarar um e a janela outro, o sistema trata os
dois como **aplicativos diferentes** e mostra dois botões lado a lado para o
mesmo programa — foi o que aconteceu no Corella Suite, que mostrava o ícone do
Python ao lado do ícone do app.

E a **versão não entra no identificador**: mudá-lo a cada atualização quebraria
o atalho que a pessoa fixou na barra de tarefas.
"""
from __future__ import annotations

import os

# Tem de ser IDÊNTICO ao `AppMutex` de `installer/sigft.iss`. Há teste travando
# os dois juntos — não mude um sem o outro.
NOME_MUTEX = "SIGFTItaipu_AppMutex"

# Idem, para o `AppUserModelID:` dos atalhos do `.iss`. Sem versão dentro.
APP_USER_MODEL_ID = "GEVernova.SIGFT.Itaipu"

_handle = None


def criar_mutex() -> bool:
    """Cria o mutex nomeado. `True` se criou, `False` fora do Windows ou falhando.

    Guarda o handle num global de propósito: enquanto o processo viver, o mutex
    existe; quando ele morre, o Windows o libera sozinho. Não há o que fechar
    à mão, e fechar cedo seria pior — o instalador deixaria de enxergar o app.

    Idempotente: chamar duas vezes não cria dois mutexes nem levanta.

    Nunca levanta: isto roda no bootstrap, e um app que não abre por causa de
    um mutex seria uma troca péssima.
    """
    global _handle

    if os.name != "nt":
        return False
    if _handle is not None:
        return True

    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL,
                                          wintypes.LPCWSTR]

        # `bInitialOwner=False`: não precisamos da posse, só da EXISTÊNCIA do
        # nome. É por ela que o Inno pergunta.
        handle = kernel32.CreateMutexW(None, False, NOME_MUTEX)
        if not handle:
            return False
        _handle = handle
        return True
    except Exception:  # noqa: BLE001 — ver o docstring
        return False


def declarar_identidade_na_barra_de_tarefas() -> bool:
    """Diz ao Windows qual é o `AppUserModelID` deste processo.

    Tem de ser chamada **antes de a primeira janela existir**: depois, o
    Windows já agrupou a janela sob o identificador que deduziu sozinho (o do
    `python.exe`, tipicamente) e não a reagrupa.

    Nunca levanta.
    """
    if os.name != "nt":
        return False
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            APP_USER_MODEL_ID)
        return True
    except Exception:  # noqa: BLE001
        return False


def preparar() -> None:
    """As duas coisas, numa chamada. Use no bootstrap, antes da janela."""
    declarar_identidade_na_barra_de_tarefas()
    criar_mutex()
