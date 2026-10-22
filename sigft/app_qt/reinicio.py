"""O "Reiniciar agora" da seção Idioma (2026-10-22).

O idioma vale ao abrir (cada tela lê os textos uma vez). Reiniciar abre uma
nova instância do SIG-FT e fecha a atual, que é o mesmo que a pessoa fechar e
abrir. Com uma tarefa rodando (robô, tradução, IA), NÃO reinicia: diz por quê
e nada fecha.

No `.exe` a instância nova é o próprio `SIG-FT.exe`; do código-fonte, o
`frontend.py` com o mesmo Python. Os argumentos vão juntos, menos o `--smoke` e
os que só valem no smoke e nas capturas (`OPCOES_DO_SMOKE`, com o valor).
Nunca nos testes (`ENV_DESLIGAR`, conftest) nem no `--smoke`.
"""
from __future__ import annotations

import os
import subprocess
import sys

from PySide6.QtWidgets import QMessageBox

from sigft.core import instancia

ENV_DESLIGAR = "SIGFT_SEM_REINICIO"
TITULO = "Reiniciar o SIG-FT"
MSG_TAREFA_EM_ANDAMENTO = (
    "Há uma tarefa em andamento (um robô, uma tradução ou uma consulta à IA).\n\n"
    "Espere ela terminar e clique de novo em Reiniciar agora. O idioma novo já "
    "está guardado e vale também na próxima vez que você abrir o SIG-FT."
)
MSG_NAO_REABRIU = (
    "Não consegui abrir o SIG-FT de novo ({erro}).\n\n"
    "O idioma novo já está guardado: feche e abra o SIG-FT para ele valer."
)


# Opções com valor que só valem no smoke e nas capturas. Ficam de fora ao
# reabrir: a instância nova abre no que está guardado, senão um `--idioma xx`
# passado à mão ganharia do idioma que a pessoa acabou de escolher
# (revisão da Task 3, 2026-10-22).
OPCOES_DO_SMOKE = ("--idioma", "--tema", "--letra")


def comando_para_reabrir(*, congelado: bool, executavel: str, argv: list[str], raiz: str) -> list[str]:
    """A linha de comando da instância nova."""
    extras: list[str] = []
    pular_valor = False
    for arg in argv[1:]:
        if pular_valor:
            pular_valor = False
        elif arg == "--smoke" or ("=" in arg and arg.split("=", 1)[0] in OPCOES_DO_SMOKE):
            pass  # `--idioma=es`: opção e valor num argumento só
        elif arg in OPCOES_DO_SMOKE:
            pular_valor = True
        else:
            extras.append(arg)
    if congelado:
        return [executavel, *extras]
    return [executavel, os.path.join(raiz, "frontend.py"), *extras]


def _abrir_processo(comando: list[str], pasta: str) -> None:
    """Abre o processo solto deste: o fim do atual não o leva junto."""
    opcoes: dict = {"cwd": pasta, "close_fds": True}
    if getattr(sys, "frozen", False):
        # PyInstaller 6: a cópia independente do mesmo `.exe` precisa refazer o
        # ambiente dela; sem isso herda a pasta temporária do pai, que some
        # quando o pai fecha.
        opcoes["env"] = {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}
    if os.name == "nt":
        opcoes["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        opcoes["start_new_session"] = True
    subprocess.Popen(comando, **opcoes)  # noqa: S603 -- o próprio SIG-FT, sem shell


def reiniciar(janela, *, pai=None) -> bool:
    """Abre outra instância e fecha `janela` (a principal). `True` se fechou.
    `pai` é de onde a caixa de aviso nasce (a janela Configuração)."""
    if "--smoke" in sys.argv or os.environ.get(ENV_DESLIGAR):
        return False
    if instancia.tarefas_em_andamento():
        QMessageBox.information(pai or janela, TITULO, MSG_TAREFA_EM_ANDAMENTO)
        return False
    # A raiz do projeto é a do `main` (`_RAIZ`, a única calculada com `__file__`,
    # ver tests/test_app_recursos.py). Import aqui: o `main` importa as telas,
    # que importam este módulo.
    from sigft.app_qt.main import _RAIZ

    congelado = bool(getattr(sys, "frozen", False))
    comando = comando_para_reabrir(congelado=congelado, executavel=sys.executable,
                                   argv=list(sys.argv), raiz=_RAIZ)
    pasta = os.path.dirname(sys.executable) if congelado else _RAIZ
    try:
        _abrir_processo(comando, pasta)
    except OSError as erro:
        QMessageBox.warning(pai or janela, TITULO, MSG_NAO_REABRIU.format(erro=erro))
        return False
    # Já conferimos que não há tarefa: fechar sem a pergunta de "tarefa em andamento".
    janela.fechar_sem_perguntar = True
    janela.close()
    return True
