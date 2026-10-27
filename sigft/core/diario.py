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

Duas instâncias abertas: a primeira prende `logs\\diario.trava` pelo processo
todo; a segunda fica sem diário e não toca em nada (2026-10-26). Antes de
desistir ela tenta `TENTATIVAS_TRAVA` vezes: no reinício pelo idioma, o processo
velho ainda pode estar soltando a trava (2026-10-27).

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
ARQUIVO_TRAVA = "diario.trava"
LIMITE_BYTES = 1024 * 1024
# Reinício pelo idioma (`app_qt/reinicio.py`): o processo novo pode chegar ao
# `abrir` com o velho ainda segurando a trava. Tenta algumas vezes antes de
# desistir (2026-10-27).
TENTATIVAS_TRAVA = 5
ESPERA_TRAVA = 0.2

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
_trava: int | None = None         # descritor do diario.trava, preso pelo processo todo

# Marca dos ganchos do diário: um segundo `abrir` no mesmo processo vê que o
# gancho de agora já é o nosso e não empilha outro por cima (2026-10-26).
_MARCA_GANCHO = "_gancho_do_diario"


def classificar(linhas: list[str], houve_queda: bool = False) -> str | None:
    """Como a última sessão de `linhas` acabou: `NORMAL`, `CAIU` ou `ENCERRADO`.
    `None` quando não há `ABERTURA` (primeira vez, ou diário apagado)."""
    # Falta de luz pode deixar bytes NUL no começo de uma linha: não escondem o evento.
    eventos = [m.group(1) for linha in linhas if (m := _EVENTO.match(linha.lstrip("\x00")))]
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


def _guardar_queda_anterior(pasta: Path) -> bool:
    """O `queda.log` com rastro vira `queda.log.anterior` (o vazio é só reaberto).
    `True` se moveu; `False` se não havia rastro ou se o sistema recusou."""
    try:
        if _houve_queda(pasta):
            os.replace(pasta / ARQUIVO_QUEDA, pasta / ARQUIVO_QUEDA_ANTERIOR)
            return True
    except OSError:
        pass
    return False


def _travar(pasta: Path) -> int | None:
    """Prende `diario.trava` para este processo (2026-10-26). Sem ela, uma segunda
    instância leria a sessão viva da primeira como "encerrada de fora", apagaria o
    `queda.log` dela e misturaria as duas sessões no diário.

    Devolve o descritor (fica aberto até `esquecer`); `None` quando nem deu para
    abrir o arquivo da trava (segue sem trava, como antes). Trava já presa por
    outra instância levanta `_OcupadoPorOutra`."""
    try:
        fd = os.open(pasta / ARQUIVO_TRAVA, os.O_RDWR | os.O_CREAT)
    except OSError:
        return None
    try:
        if sys.platform == "win32":
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        raise _OcupadoPorOutra from None
    return fd


def _esperar(segundos: float) -> None:
    time.sleep(segundos)


def _travar_com_paciencia(pasta: Path) -> int | None:
    """`_travar` até `TENTATIVAS_TRAVA` vezes, com `ESPERA_TRAVA` entre elas.
    Presa em todas: `_OcupadoPorOutra`, como `_travar`."""
    for tentativa in range(TENTATIVAS_TRAVA):
        try:
            return _travar(pasta)
        except _OcupadoPorOutra:
            if tentativa == TENTATIVAS_TRAVA - 1:
                raise
            _esperar(ESPERA_TRAVA)
    return None


class _OcupadoPorOutra(Exception):
    """Outra instância do SIG-FT segura o diário."""


def _soltar_trava() -> None:
    global _trava
    if _trava is not None:
        try:
            os.close(_trava)   # fechar solta a trava nos dois mecanismos
        except OSError:
            pass
    _trava = None


def _termina_sem_quebra(arquivo: Path) -> bool:
    """O último byte é `\n` (ou o arquivo está vazio ou não existe)."""
    try:
        with open(arquivo, "rb") as entrada:
            entrada.seek(0, os.SEEK_END)
            if entrada.tell() == 0:
                return True
            entrada.seek(-1, os.SEEK_END)
            return entrada.read(1) == b"\n"
    except FileNotFoundError:
        return True


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
        except OSError:
            # Não existe ainda, ou o sistema recusou a rotação (arquivo aberto por
            # antivírus ou editor): a linha entra assim mesmo e a próxima tenta de novo.
            pass
        # Falta de luz deixa a última linha pela metade (ou em bytes NUL), sem o
        # `\n`: sem quebrar antes, este evento grudaria nela e sumiria da leitura.
        inicio = "" if _termina_sem_quebra(arquivo) else "\n"
        with open(arquivo, "a", encoding="utf-8") as saida:
            saida.write(f"{inicio}{time.strftime('%Y-%m-%d %H:%M:%S')} {evento}\n")
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


def _instalar_ganchos(pasta: Path, *, queda_guardada: bool) -> None:
    """Erro não tratado (thread principal e threads) e queda dura vão para o diário.
    Cada gancho chama o que havia antes: o traceback continua saindo onde saía.

    `queda_guardada` falso com o `queda.log` ainda com rastro (o sistema recusou
    movê-lo): reabre em modo "a", para não apagar a prova da queda anterior."""
    global _arquivo_queda
    _ligar_excepthooks()
    # No Windows o `faulthandler` também grava exceções que o processo sobrevive
    # (as do sistema, tratadas mais acima): `queda.log` com texto não é queda
    # sozinho. Com `FECHAMENTO` depois, `classificar` dá NORMAL do mesmo jeito.
    modo = "a" if not queda_guardada and _houve_queda(pasta) else "w"
    try:
        _arquivo_queda = open(pasta / ARQUIVO_QUEDA, modo, encoding="utf-8")
        faulthandler.enable(_arquivo_queda, all_threads=True)
    except Exception:  # noqa: BLE001 -- sem o rastro da queda dura, o resto segue
        _arquivo_queda = None


def _ligar_excepthooks() -> None:
    """Embrulha `sys.excepthook` e `threading.excepthook`, cada um só se o de agora
    ainda não for o do diário (um segundo `abrir` não empilha outro)."""
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

    setattr(_no_python, _MARCA_GANCHO, True)
    setattr(_na_thread, _MARCA_GANCHO, True)
    if not getattr(anterior_python, _MARCA_GANCHO, False):
        sys.excepthook = _no_python
    if not getattr(anterior_thread, _MARCA_GANCHO, False):
        threading.excepthook = _na_thread


def abrir(*, versao: str, idioma: str, pasta: str | os.PathLike[str] | None = None,
          ganchos: bool = True) -> str | None:
    """Lê como a sessão anterior acabou, marca a `ABERTURA` desta e (com `ganchos`)
    liga os ganchos de erro e o `faulthandler`. Devolve a situação da anterior
    (`NORMAL`, `CAIU`, `ENCERRADO`) ou `None`. Nunca levanta: qualquer falha deixa
    o diário desligado nesta sessão."""
    global _pasta, _anterior, _trava
    esquecer()
    if os.environ.get(ENV_DESLIGAR):
        return None
    try:
        if pasta is None:
            from sigft.core.dados_usuario import pasta_logs

            pasta = pasta_logs()
        pasta = Path(pasta)
        try:
            _trava = _travar_com_paciencia(pasta)
        except _OcupadoPorOutra:
            # Outra instância está aberta: esta fica sem diário e não toca em nada.
            return None
        anterior = classificar(_ler_linhas(pasta), _houve_queda(pasta))
        queda_guardada = _guardar_queda_anterior(pasta)
        _pasta = pasta
        detalhe = (f"versao={versao} idioma={idioma} sistema={platform.platform()} "
                   f"python={platform.python_version()}")
        if not _gravar(f"{ABERTURA} {detalhe}"):
            _pasta = None
            _soltar_trava()
            return None
        _anterior = anterior
        if ganchos:
            _instalar_ganchos(pasta, queda_guardada=queda_guardada)
        return anterior
    except Exception:  # noqa: BLE001 -- o diário nunca impede a abertura
        _pasta = None
        _soltar_trava()
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
    """Zera o estado (desliga o `faulthandler`, fecha o `queda.log` e solta a trava).
    Os ganchos de `sys`/`threading` ficam: quem testa os devolve (`monkeypatch`).
    Teste de gancho usa o dublê de `faulthandler` da fixture; teste do app mantém
    `SIGFT_SEM_DIARIO` posta (o `faulthandler` de verdade é o do pytest)."""
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
    _soltar_trava()
    _pasta, _anterior, _dispensado, _arquivo_queda = None, None, False, None
