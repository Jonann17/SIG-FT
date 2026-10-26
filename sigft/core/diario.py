"""O diário de quedas: como cada sessão do SIG-FT terminou (2026-10-26).

Quando alguém diz "o SIG-FT fechou sozinho", o `sigft.log` (`core/saida_log.py`)
não diz se a pessoa fechou a janela, se o app caiu ou se foi encerrado de fora.
Este diário diz: uma linha por evento, com data e hora, em
`Documentos\\SIG-FT\\logs\\diario.log`:

* `ABERTURA` na abertura, com a versão, o idioma e o sistema;
* `FECHAMENTO pela janela` quando a janela principal fecha (o `closeEvent` aceito);
* `ERRO NAO TRATADO (thread ...)` com o traceback, pelo `sys.excepthook` e pelo
  `threading.excepthook` (os robôs rodam em threads). As linhas do traceback vêm
  com 4 espaços na frente: só a linha que começa pela data é evento.

Queda dura (o processo morre sem passar pelo Python): o `faulthandler` grava o
rastro em `logs\\queda.log`, aberto na abertura e mantido aberto.

A sessão ANTERIOR é lida em `abrir`, antes de a nova `ABERTURA` ser gravada
(`classificar`): com `FECHAMENTO` depois da última `ABERTURA`, fechou normal; sem
ele, e com `ERRO NAO TRATADO` ou `queda.log` não vazio, caiu; sem nada, foi
encerrado de fora (Gerenciador de Tarefas, desligamento, falta de luz). O
`queda.log` com rastro vira `queda.log.anterior` antes de o novo ser aberto.

Passou de `LIMITE_BYTES`, o arquivo vira `diario.log.1` (uma cópia só) e
recomeça; a leitura da sessão anterior junta os dois.

**Nunca impede a abertura**: pasta sem permissão, disco cheio ou arquivo
estragado deixam o diário desligado nesta sessão, e nada daqui levanta. Nos
testes vem desligado (`ENV_DESLIGAR`, posta pelo `tests/conftest.py`).

Só biblioteca padrão: nenhum import de interface aqui.
"""
from __future__ import annotations

import faulthandler
import os
import platform
import re
import sys
import threading
import time
import traceback
from pathlib import Path

ENV_DESLIGAR = "SIGFT_SEM_DIARIO"
ARQUIVO = "diario.log"
ARQUIVO_VELHO = "diario.log.1"
ARQUIVO_QUEDA = "queda.log"
ARQUIVO_QUEDA_ANTERIOR = "queda.log.anterior"
LIMITE_BYTES = 1024 * 1024

ABERTURA = "ABERTURA"
FECHAMENTO = "FECHAMENTO pela janela"
ERRO = "ERRO NAO TRATADO"

# Como a sessão anterior acabou (`classificar`).
NORMAL = "normal"
CAIU = "caiu"
ENCERRADO = "encerrado"

# Só a linha que COMEÇA pela data é evento (o traceback vem recuado).
_EVENTO = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} (ABERTURA|FECHAMENTO|ERRO NAO TRATADO)\b")

_pasta: Path | None = None        # None: diário desligado nesta sessão
_anterior: str | None = None
_dispensado = False
_arquivo_queda = None             # o queda.log aberto, onde o faulthandler escreve


def classificar(linhas: list[str], houve_queda: bool = False) -> str | None:
    """Como a última sessão de `linhas` acabou: `NORMAL`, `CAIU` ou `ENCERRADO`.
    `None` quando não há `ABERTURA` (primeira vez, ou diário apagado)."""
    eventos = [m.group(1) for linha in linhas if (m := _EVENTO.match(linha))]
    if ABERTURA not in eventos:
        return None
    ultima = len(eventos) - 1 - eventos[::-1].index(ABERTURA)
    depois = eventos[ultima + 1:]
    if "FECHAMENTO" in depois:
        return NORMAL
    if ERRO in depois or houve_queda:
        return CAIU
    return ENCERRADO


def _ler_linhas(pasta: Path) -> list[str]:
    """`diario.log.1` e depois `diario.log`: a sessão anterior pode ter começado
    antes de uma rotação."""
    linhas: list[str] = []
    for nome in (ARQUIVO_VELHO, ARQUIVO):
        try:
            linhas += (pasta / nome).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            pass
    return linhas


def _houve_queda(pasta: Path) -> bool:
    try:
        return (pasta / ARQUIVO_QUEDA).stat().st_size > 0
    except OSError:
        return False


def _guardar_queda_anterior(pasta: Path) -> None:
    """O `queda.log` com rastro vira `queda.log.anterior` (o vazio é só reaberto)."""
    try:
        if _houve_queda(pasta):
            os.replace(pasta / ARQUIVO_QUEDA, pasta / ARQUIVO_QUEDA_ANTERIOR)
    except OSError:
        pass


def _gravar(evento: str) -> bool:
    """Uma linha no diário (abre, escreve e fecha: o que foi escrito fica no disco
    mesmo que o processo morra logo depois). `False` se não deu."""
    if _pasta is None:
        return False
    try:
        arquivo = _pasta / ARQUIVO
        try:
            if arquivo.stat().st_size > LIMITE_BYTES:
                os.replace(arquivo, _pasta / ARQUIVO_VELHO)
        except FileNotFoundError:
            pass
        with open(arquivo, "a", encoding="utf-8") as saida:
            saida.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {evento}\n")
        return True
    except Exception:  # noqa: BLE001 -- o diário nunca derruba o app
        return False


def registrar_erro(tipo, valor, rastro, *, onde: str = "") -> None:
    """`ERRO NAO TRATADO (onde)` e o traceback recuado. Nunca levanta."""
    try:
        texto = "".join(traceback.format_exception(tipo, valor, rastro)).rstrip("\n")
        recuado = "\n".join("    " + linha for linha in texto.splitlines())
        _gravar(f"{ERRO} ({onde or 'desconhecido'})\n{recuado}")
    except Exception:  # noqa: BLE001 -- o diário nunca derruba o app
        pass


def registrar_fechamento() -> None:
    """A janela principal fechou (o `closeEvent` aceito)."""
    _gravar(FECHAMENTO)


def _instalar_ganchos(pasta: Path) -> None:
    """Erro não tratado (thread principal e threads) e queda dura vão para o diário.
    Cada gancho chama o que havia antes: o traceback continua saindo onde saía."""
    global _arquivo_queda
    anterior_python = sys.excepthook
    anterior_thread = threading.excepthook

    def _no_python(tipo, valor, rastro):
        registrar_erro(tipo, valor, rastro, onde="thread principal")
        anterior_python(tipo, valor, rastro)

    def _na_thread(args):
        if args.exc_type is not SystemExit:
            nome = args.thread.name if args.thread is not None else "?"
            registrar_erro(args.exc_type, args.exc_value, args.exc_traceback, onde=f"thread {nome}")
        anterior_thread(args)

    sys.excepthook = _no_python
    threading.excepthook = _na_thread
    try:
        _arquivo_queda = open(pasta / ARQUIVO_QUEDA, "w", encoding="utf-8")
        faulthandler.enable(_arquivo_queda, all_threads=True)
    except Exception:  # noqa: BLE001 -- sem o rastro da queda dura, o resto segue
        _arquivo_queda = None


def abrir(*, versao: str, idioma: str, pasta: str | os.PathLike[str] | None = None,
          ganchos: bool = True) -> str | None:
    """Lê como a sessão anterior acabou, marca a `ABERTURA` desta e (com `ganchos`)
    liga os ganchos de erro e o `faulthandler`. Devolve a situação da anterior
    (`NORMAL`, `CAIU`, `ENCERRADO`) ou `None`. Nunca levanta: qualquer falha deixa
    o diário desligado nesta sessão."""
    global _pasta, _anterior
    esquecer()
    if os.environ.get(ENV_DESLIGAR):
        return None
    try:
        if pasta is None:
            from sigft.core.dados_usuario import pasta_logs

            pasta = pasta_logs()
        pasta = Path(pasta)
        anterior = classificar(_ler_linhas(pasta), _houve_queda(pasta))
        _guardar_queda_anterior(pasta)
        _pasta = pasta
        detalhe = (f"versao={versao} idioma={idioma} sistema={platform.platform()} "
                   f"python={platform.python_version()}")
        if not _gravar(f"{ABERTURA} {detalhe}"):
            _pasta = None
            return None
        _anterior = anterior
        if ganchos:
            _instalar_ganchos(pasta)
        return anterior
    except Exception:  # noqa: BLE001 -- o diário nunca impede a abertura
        _pasta = None
        return None


def ligado() -> bool:
    return _pasta is not None


def sessao_anterior() -> str | None:
    return _anterior


def aviso_pendente() -> str | None:
    """`CAIU` ou `ENCERRADO` enquanto o aviso da Home não foi dispensado."""
    if _dispensado or _anterior not in (CAIU, ENCERRADO):
        return None
    return _anterior


def dispensar_aviso() -> None:
    """O "Entendido" da Home: o aviso some até a próxima queda."""
    global _dispensado
    _dispensado = True


def esquecer() -> None:
    """Zera o estado (desliga o `faulthandler` e fecha o `queda.log`, se abertos).
    Os ganchos de `sys`/`threading` ficam: quem testa os devolve (`monkeypatch`)."""
    global _pasta, _anterior, _dispensado, _arquivo_queda
    if _arquivo_queda is not None:
        try:
            faulthandler.disable()
        except Exception:  # noqa: BLE001
            pass
        try:
            _arquivo_queda.close()
        except Exception:  # noqa: BLE001
            pass
    _pasta, _anterior, _dispensado, _arquivo_queda = None, None, False, None
