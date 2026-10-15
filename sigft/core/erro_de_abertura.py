"""A interface não abriu: avisar a pessoa SEM interface gráfica nenhuma.

Quem chega aqui é o caso em que a Qt (a única interface do SIG-FT desde
2026-10-15) não importou ou não subiu: PySide6 ausente, DLL que não carrega,
plugin de plataforma que falta. Não há janela para mostrar o erro, e não há
mais a interface antiga para cair. O aviso sai pelo que o sistema operacional
oferece sem biblioteca nenhuma:

* Windows: `MessageBoxW` do `user32`, por `ctypes`;
* Mac: `osascript` (`display alert`);
* outro sistema (ou se a caixa falhar): só a saída de erro.

E o motivo, com a pilha, vai para o `sigft.log` da pasta de dados
(`Documentos\\SIG-FT\\logs\\`) -- é o arquivo que a pessoa manda para quem
cuida do SIG-FT. A saída de erro recebe o mesmo texto: aberto pelo
`SIG-FT.bat` (ou pelo `SIG-FT.command`), ele fica na janela preta, que espera
um Enter antes de fechar.

Só biblioteca padrão: este módulo roda justamente quando o resto falhou.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

TITULO = "SIG-FT"

# O `display alert` pelo `argv` do AppleScript: o texto vai como argumento, e
# não colado no script -- aspas e barras do motivo não precisam de escape.
_SCRIPT_MAC = [
    "-e", "on run argv",
    "-e", "display alert (item 1 of argv) message (item 2 of argv) as critical",
    "-e", "end run",
]

# MB_OK | MB_ICONERROR | MB_SETFOREGROUND | MB_TOPMOST: a caixa vem na frente
# da janela preta, e não escondida atrás dela.
_ESTILO_WINDOWS = 0x0 | 0x10 | 0x10000 | 0x40000


def caminho_do_log() -> str:
    """`Documentos\\SIG-FT\\logs\\sigft.log`, o mesmo do `saida_log`."""
    from sigft.core.dados_usuario import pasta_logs

    return os.path.join(str(pasta_logs()), "sigft.log")


def registrar_no_log(motivo: str, pilha: str = "") -> str | None:
    """Acrescenta o motivo (e a pilha) ao `sigft.log`. Devolve o caminho, ou
    `None` se não deu para gravar -- nunca levanta: o aviso tem de sair mesmo
    com a pasta de dados somente-leitura."""
    try:
        caminho = caminho_do_log()
        with open(caminho, "a", encoding="utf-8") as log:
            log.write(f"\n===== {time.strftime('%d/%m/%Y %H:%M:%S')} "
                      "a interface do SIG-FT nao abriu =====\n")
            log.write(motivo.rstrip() + "\n")
            if pilha:
                log.write(pilha.rstrip() + "\n")
        return caminho
    except Exception:  # noqa: BLE001 -- perder o log é ruim, perder o aviso é pior
        return None


def mensagem(motivo: str, log: str | None) -> str:
    """O texto da caixa (e da janela preta)."""
    if log:
        onde = f"O detalhe completo está em:\n{log}\n\nMande esse arquivo para quem cuida do SIG-FT."
    else:
        onde = ("Não consegui gravar o detalhe no sigft.log. Copie esta mensagem e "
                "mande para quem cuida do SIG-FT.")
    return f"O SIG-FT não conseguiu abrir a janela.\n\n{motivo.strip()}\n\n{onde}"


def mostrar_caixa(texto: str, *, plataforma: str | None = None, rodar=subprocess.run) -> str:
    """Mostra `texto` numa caixa do sistema. Devolve o canal usado:
    `"windows"`, `"mac"` ou `"nenhum"` (fora deles, ou se a caixa falhou)."""
    plataforma = plataforma or sys.platform
    try:
        if plataforma == "win32":
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, texto, TITULO, _ESTILO_WINDOWS)
            return "windows"
        if plataforma == "darwin":
            rodar(["osascript", *_SCRIPT_MAC, TITULO, texto], check=False, timeout=600)
            return "mac"
    except Exception:  # noqa: BLE001 -- sem caixa, fica a saída de erro
        pass
    return "nenhum"


def _na_saida_de_erro(texto: str) -> None:
    # No `.exe` sem console, `sys.stderr` é `None`: o log já tem tudo.
    if sys.stderr is not None:
        try:
            print(texto, file=sys.stderr, flush=True)
        except Exception:  # noqa: BLE001
            pass


def avisar(motivo: str, pilha: str = "", *, plataforma: str | None = None,
           rodar=subprocess.run) -> str:
    """Grava no log, escreve na saída de erro e mostra a caixa. Devolve o texto
    mostrado. Não sai do processo: quem chama sai com 1."""
    log = registrar_no_log(motivo, pilha)
    texto = mensagem(motivo, log)
    if pilha:
        _na_saida_de_erro(pilha.rstrip())
    _na_saida_de_erro(f"[SIG-FT] {texto}")
    mostrar_caixa(texto, plataforma=plataforma, rodar=rodar)
    return texto
