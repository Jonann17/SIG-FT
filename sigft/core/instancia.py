"""A instância do SIG-FT no Windows: a identidade na barra de tarefas e o fim do processo.

O `AppUserModelID`
------------------
O Windows agrupa janelas na barra de tarefas por esse identificador. Se o
atalho declarar um e a janela outro, o sistema trata os dois como
**aplicativos diferentes** e mostra dois botões lado a lado para o mesmo
programa — foi o que aconteceu no Corella Suite, que mostrava o ícone do
Python ao lado do ícone do app. O nome tem de bater com o `AppUserModelID:`
dos atalhos do `installer/sigft.iss`, e há teste travando os dois juntos.

E a **versão não entra no identificador**: mudá-lo a cada atualização quebraria
o atalho que a pessoa fixou na barra de tarefas.

Fechar a janela ENCERRA o processo  [2026-09-25]
-----------------------------------------------
Ao instalar a 1.1.1-rc.1, o usuário recebeu "o instalador detectou que o
SIG-FT Itaipu está atualmente em execução" — com o SIG-FT fechado. Havia um
`SIG-FT.exe` vivo, SEM JANELA: um robô tinha parado na pausa de login e a
pessoa fechou o app ali. A thread do robô é comum (não-daemon), fica
esperando um clique que nunca vem, e o Python espera por ela antes de
encerrar — para sempre. Reproduzido com o app de verdade sob xvfb, junto com
um segundo caminho: a montagem da janela principal falhar.

Por isso `encerrar()`: quando a janela principal fecha, o processo termina,
com ou sem thread presa. Quem fecha com uma tarefa em andamento é avisado
antes (`tarefas_em_andamento`, usada pelo "X" da janela).

O mutex que morava aqui saiu na mesma data
------------------------------------------
Este módulo criava um mutex nomeado para o `AppMutex` do instalador. Era ele
que acusava o fantasma: o `AppMutex` só pergunta "existe um mutex com esse
nome?", não distingue app aberto de processo sem janela (nem da cópia do ZIP
do Box rodando de outra pasta), e não oferece fechar. O instalador passou a
usar o Restart Manager (`CloseApplications=force`), que pergunta QUEM usa os
arquivos da pasta instalada e fecha até o fantasma. Ver `installer/sigft.iss`
e `tests/test_instalador.py`, seção A.
"""
from __future__ import annotations

import os
import sys
import threading

# Tem de bater com o `AppUserModelID:` dos atalhos do `.iss`. Sem versão dentro.
APP_USER_MODEL_ID = "GEVernova.SIGFT.Itaipu"


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
    """O que precisa acontecer antes da primeira janela. Use no bootstrap."""
    declarar_identidade_na_barra_de_tarefas()


def tarefas_em_andamento() -> list[str]:
    """Os nomes das threads COMUNS ainda vivas — o trabalho da pessoa.

    São as threads que o Python espera antes de encerrar: o robô de um módulo,
    a tradução, a consulta à IA. As `daemon` ficam de fora de propósito: a
    consulta de atualização, por exemplo, é de fundo e pode morrer com o app;
    perguntar por ela ao fechar seria um aviso falso.
    """
    principal = threading.main_thread()
    return [t.name for t in threading.enumerate()
            if t is not principal and t.is_alive() and not t.daemon]


def encerrar(codigo: int = 0) -> None:
    """Termina o processo AGORA, mesmo com thread presa. Não volta.

    `os._exit`, e não o fim normal: o fim normal espera cada thread comum
    terminar, e uma que espera um clique numa janela que já não existe não
    termina nunca — é o `SIG-FT.exe` sem janela que travava o instalador.

    O log é descarregado antes: no `.exe` o `print` vai para o `sigft.log`, e a
    última linha costuma ser justamente a que explica o encerramento.
    """
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.flush()
        except Exception:  # noqa: BLE001 -- sem console, ou arquivo já fechado
            pass
    os._exit(codigo)
