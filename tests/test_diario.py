"""O diário de quedas (`sigft/core/diario.py`, 2026-10-26).

Sem Qt: a sessão anterior é lida do disco, a nova é marcada, e os ganchos de
erro (Python, threads, `faulthandler`) gravam no mesmo arquivo. O
`faulthandler` de verdade é o do pytest: aqui ele é trocado por um dublê.
"""
from __future__ import annotations

import ast
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from sigft.core import diario


def _linha(evento: str, quando: str = "2026-10-25 09:00:00") -> str:
    return f"{quando} {evento}\n"


class _FaultFalso:
    """O `faulthandler` de mentira: guarda o NOME do arquivo em que foi ligado."""

    def __init__(self) -> None:
        self.arquivo = None

    def enable(self, arquivo, all_threads=True) -> None:
        self.arquivo = Path(arquivo.name).name

    def disable(self) -> None:
        self.arquivo = None


@pytest.fixture
def ambiente(monkeypatch, tmp_path):
    monkeypatch.delenv(diario.ENV_DESLIGAR, raising=False)
    falso = _FaultFalso()
    monkeypatch.setattr(diario, "faulthandler", falso)
    # Os ganchos que o `abrir` troca voltam ao que eram no fim do teste.
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    diario.esquecer()
    yield SimpleNamespace(pasta=tmp_path, faulthandler=falso)
    diario.esquecer()


def _abrir(pasta, **kw):
    return diario.abrir(versao="1.3.1", idioma="es", pasta=pasta, **kw)


def _texto(pasta) -> str:
    return (pasta / diario.ARQUIVO).read_text(encoding="utf-8")


def _escrever(pasta, *eventos: str) -> None:
    (pasta / diario.ARQUIVO).write_text("".join(_linha(e) for e in eventos), encoding="utf-8")


# --- classificar: a regra, sem disco ------------------------------------------------

def test_sem_abertura_nao_ha_sessao_anterior():
    assert diario.classificar([]) is None
    assert diario.classificar(["lixo", _linha("FECHAMENTO pela janela")]) is None


def test_abertura_com_fechamento_e_normal():
    linhas = [_linha("ABERTURA versao=1.3.0"), _linha("FECHAMENTO pela janela")]
    assert diario.classificar(linhas) == diario.NORMAL


def test_erro_sem_fechamento_e_queda():
    linhas = [_linha("ABERTURA versao=1.3.0"), _linha("ERRO NAO TRATADO (thread principal)"),
              "    Traceback (most recent call last):\n"]
    assert diario.classificar(linhas) == diario.CAIU


def test_rastro_do_faulthandler_sem_fechamento_e_queda():
    assert diario.classificar([_linha("ABERTURA versao=1.3.0")], houve_queda=True) == diario.CAIU


def test_nada_depois_da_abertura_e_encerrado_de_fora():
    assert diario.classificar([_linha("ABERTURA versao=1.3.0")]) == diario.ENCERRADO


def test_erro_e_depois_fechamento_e_normal():
    # Erro num clique (o Qt segue) e a pessoa fechou a janela depois: fechou normal.
    linhas = [_linha("ABERTURA versao=1.3.0"), _linha("ERRO NAO TRATADO (thread principal)"),
              _linha("FECHAMENTO pela janela")]
    assert diario.classificar(linhas) == diario.NORMAL


def test_vale_so_a_ultima_sessao():
    caiu_e_depois_normal = [_linha("ABERTURA a"), _linha("ERRO NAO TRATADO (thread x)"),
                            _linha("ABERTURA b"), _linha("FECHAMENTO pela janela")]
    normal_e_depois_caiu = [_linha("ABERTURA a"), _linha("FECHAMENTO pela janela"),
                            _linha("ABERTURA b"), _linha("ERRO NAO TRATADO (thread x)")]
    assert diario.classificar(caiu_e_depois_normal) == diario.NORMAL
    assert diario.classificar(normal_e_depois_caiu) == diario.CAIU


def test_linha_do_traceback_nao_conta_como_evento():
    linhas = [_linha("ABERTURA a"), "    " + _linha("FECHAMENTO pela janela")]
    assert diario.classificar(linhas) == diario.ENCERRADO


# --- abrir: a sessão anterior e a nova ------------------------------------------------

def test_abrir_le_a_sessao_anterior_antes_de_marcar_a_nova(ambiente):
    _escrever(ambiente.pasta, "ABERTURA versao=1.3.0", "FECHAMENTO pela janela")
    assert _abrir(ambiente.pasta) == diario.NORMAL
    assert diario.sessao_anterior() == diario.NORMAL
    assert diario.aviso_pendente() is None
    ultima = _texto(ambiente.pasta).splitlines()[-1]
    assert " ABERTURA " in ultima
    assert "versao=1.3.1" in ultima and "idioma=es" in ultima and "sistema=" in ultima


def test_primeira_abertura_nao_tem_aviso(ambiente):
    assert _abrir(ambiente.pasta) is None
    assert diario.ligado()
    assert diario.aviso_pendente() is None


def test_queda_vira_aviso_ate_ser_dispensado(ambiente):
    _escrever(ambiente.pasta, "ABERTURA versao=1.3.0", "ERRO NAO TRATADO (thread principal)")
    assert _abrir(ambiente.pasta) == diario.CAIU
    assert diario.aviso_pendente() == diario.CAIU
    diario.dispensar_aviso()
    assert diario.aviso_pendente() is None
    assert diario.sessao_anterior() == diario.CAIU


def test_encerrado_de_fora_vira_aviso(ambiente):
    _escrever(ambiente.pasta, "ABERTURA versao=1.3.0")
    assert _abrir(ambiente.pasta) == diario.ENCERRADO
    assert diario.aviso_pendente() == diario.ENCERRADO


def test_queda_log_com_rastro_e_queda_e_vira_o_anterior(ambiente):
    _escrever(ambiente.pasta, "ABERTURA versao=1.3.0")
    (ambiente.pasta / diario.ARQUIVO_QUEDA).write_text("Fatal Python error: Segmentation fault\n",
                                                       encoding="utf-8")
    assert _abrir(ambiente.pasta) == diario.CAIU
    anterior = (ambiente.pasta / diario.ARQUIVO_QUEDA_ANTERIOR).read_text(encoding="utf-8")
    assert anterior.startswith("Fatal Python error")
    assert (ambiente.pasta / diario.ARQUIVO_QUEDA).read_text(encoding="utf-8") == ""
    assert ambiente.faulthandler.arquivo == diario.ARQUIVO_QUEDA


def test_queda_log_vazio_nao_e_queda(ambiente):
    _escrever(ambiente.pasta, "ABERTURA versao=1.3.0", "FECHAMENTO pela janela")
    (ambiente.pasta / diario.ARQUIVO_QUEDA).write_text("", encoding="utf-8")
    assert _abrir(ambiente.pasta) == diario.NORMAL
    assert not (ambiente.pasta / diario.ARQUIVO_QUEDA_ANTERIOR).exists()


def test_fechamento_gravado_a_proxima_abertura_ve_normal(ambiente):
    _abrir(ambiente.pasta)
    diario.registrar_fechamento()
    assert _texto(ambiente.pasta).splitlines()[-1].endswith("FECHAMENTO pela janela")
    diario.esquecer()
    assert _abrir(ambiente.pasta) == diario.NORMAL


def test_sem_fechamento_a_proxima_abertura_ve_encerrado(ambiente):
    _abrir(ambiente.pasta)
    diario.esquecer()
    assert _abrir(ambiente.pasta) == diario.ENCERRADO


def test_pasta_que_nao_grava_desliga_o_diario_e_nao_levanta(ambiente):
    gancho_antes = sys.excepthook
    bloqueio = ambiente.pasta / "nao_e_pasta"
    bloqueio.write_text("um arquivo no lugar da pasta", encoding="utf-8")
    assert _abrir(bloqueio) is None
    assert not diario.ligado()
    assert sys.excepthook is gancho_antes
    diario.registrar_fechamento()
    diario.registrar_erro(ValueError, ValueError("x"), None, onde="thread principal")
    assert diario.aviso_pendente() is None


def test_arquivo_estragado_nao_levanta(ambiente):
    (ambiente.pasta / diario.ARQUIVO).write_bytes(b"\xff\xfe\x00 lixo \x80\x81\n")
    assert _abrir(ambiente.pasta) is None
    assert diario.ligado()


def test_desligado_pela_variavel_nao_grava_nada(ambiente, monkeypatch):
    monkeypatch.setenv(diario.ENV_DESLIGAR, "1")
    assert _abrir(ambiente.pasta) is None
    assert not diario.ligado()
    assert not (ambiente.pasta / diario.ARQUIVO).exists()


# --- tamanho ---------------------------------------------------------------------------

def test_passou_de_1_mb_vira_ponto_1_e_recomeca(ambiente):
    grande = "x" * (diario.LIMITE_BYTES + 1)
    (ambiente.pasta / diario.ARQUIVO).write_text(grande, encoding="utf-8")
    _abrir(ambiente.pasta)
    assert (ambiente.pasta / diario.ARQUIVO_VELHO).read_text(encoding="utf-8") == grande
    linhas = _texto(ambiente.pasta).splitlines()
    assert len(linhas) == 1 and " ABERTURA " in linhas[0]


def test_sessao_que_ficou_metade_no_ponto_1_tambem_conta(ambiente):
    (ambiente.pasta / diario.ARQUIVO_VELHO).write_text(_linha("ABERTURA versao=1.3.0"), encoding="utf-8")
    (ambiente.pasta / diario.ARQUIVO).write_text(_linha("FECHAMENTO pela janela"), encoding="utf-8")
    assert _abrir(ambiente.pasta) == diario.NORMAL


# --- ganchos ----------------------------------------------------------------------------

def test_thread_que_quebra_fica_no_diario(ambiente, monkeypatch):
    vistos = []
    # No corpo do teste (e não na fixture): o pytest pode pôr o gancho dele ao
    # começar a fase do teste, e é o que estiver aqui que o diário embrulha.
    monkeypatch.setattr(threading, "excepthook", lambda args: vistos.append(args.exc_type))
    _abrir(ambiente.pasta)

    def quebrar():
        raise RuntimeError("robo caiu de proposito")

    linha = threading.Thread(target=quebrar, name="robo-teste")
    linha.start()
    linha.join()
    texto = _texto(ambiente.pasta)
    assert "ERRO NAO TRATADO (thread robo-teste)" in texto
    assert "    Traceback (most recent call last):" in texto
    assert "RuntimeError: robo caiu de proposito" in texto
    assert vistos == [RuntimeError]   # o gancho de antes continua sendo chamado


def test_erro_da_thread_principal_fica_no_diario(ambiente, monkeypatch):
    vistos = []
    monkeypatch.setattr(sys, "excepthook", lambda tipo, valor, rastro: vistos.append(tipo))
    _abrir(ambiente.pasta)
    try:
        raise ValueError("de proposito")
    except ValueError:
        sys.excepthook(*sys.exc_info())
    assert vistos == [ValueError]
    assert "ERRO NAO TRATADO (thread principal)" in _texto(ambiente.pasta)
    assert diario.classificar(_texto(ambiente.pasta).splitlines()) == diario.CAIU


def test_sem_ganchos_nao_troca_nada(ambiente):
    antes = (sys.excepthook, threading.excepthook)
    _abrir(ambiente.pasta, ganchos=False)
    assert (sys.excepthook, threading.excepthook) == antes
    assert ambiente.faulthandler.arquivo is None


def test_modulo_nao_importa_interface():
    from test_sem_interface_antiga import MODULOS_PROIBIDOS

    arvore = ast.parse(Path(diario.__file__).read_text(encoding="utf-8"))
    nomes = {n.module if isinstance(n, ast.ImportFrom) else a.name
             for n in ast.walk(arvore) if isinstance(n, (ast.Import, ast.ImportFrom))
             for a in (n.names if isinstance(n, ast.Import) else [n])}
    assert not any(n and n.split(".")[0] in MODULOS_PROIBIDOS | {"PySide6"} for n in nomes)


# --- correções da revisão (2026-10-26) ----------------------------------------------

def _travar_por_fora(pasta):
    """Pega a trava como se fosse outra instância do SIG-FT. Um segundo descritor
    conflita mesmo dentro do mesmo processo, nos dois mecanismos."""
    import os

    fd = os.open(pasta / diario.ARQUIVO_TRAVA, os.O_RDWR | os.O_CREAT)
    if sys.platform == "win32":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return fd


def test_segunda_instancia_fica_sem_diario_e_nao_mexe_em_nada(ambiente):
    import os

    _escrever(ambiente.pasta, "ABERTURA versao=1.3.0")
    (ambiente.pasta / diario.ARQUIVO_QUEDA).write_text("rastro da primeira\n", encoding="utf-8")
    antes = _texto(ambiente.pasta)
    fd = _travar_por_fora(ambiente.pasta)
    try:
        assert _abrir(ambiente.pasta) is None
        assert not diario.ligado()
        assert diario.aviso_pendente() is None
        assert _texto(ambiente.pasta) == antes
        queda = (ambiente.pasta / diario.ARQUIVO_QUEDA).read_text(encoding="utf-8")
        assert queda == "rastro da primeira\n"
        assert not (ambiente.pasta / diario.ARQUIVO_QUEDA_ANTERIOR).exists()
        assert ambiente.faulthandler.arquivo is None
    finally:
        os.close(fd)   # a primeira instância fechou: a trava fica livre
    assert _abrir(ambiente.pasta) == diario.CAIU
    assert diario.ligado()


def test_a_trava_e_solta_no_esquecer(ambiente):
    import os

    _abrir(ambiente.pasta)
    with pytest.raises(OSError):
        _travar_por_fora(ambiente.pasta)
    diario.esquecer()
    os.close(_travar_por_fora(ambiente.pasta))


def test_rotacao_que_falha_ainda_grava_a_linha(ambiente, monkeypatch):
    grande = "x" * (diario.LIMITE_BYTES + 1) + "\n"
    (ambiente.pasta / diario.ARQUIVO).write_text(grande, encoding="utf-8")

    def recusar(*_a, **_k):
        raise PermissionError("arquivo aberto por outro programa")

    monkeypatch.setattr(diario.os, "replace", recusar)
    _abrir(ambiente.pasta)
    assert diario.ligado()
    assert " ABERTURA " in _texto(ambiente.pasta).splitlines()[-1]


@pytest.mark.parametrize("rabo", ["\x00\x00\x00", "2026-10-25 09:00:01 FECHAM"])
def test_rabo_rasgado_nao_esconde_a_abertura_seguinte(ambiente, rabo):
    # Falta de luz: a última linha ficou pela metade (ou em bytes NUL), sem o \n.
    texto = _linha("ABERTURA versao=1.3.0") + _linha("FECHAMENTO pela janela") + rabo
    (ambiente.pasta / diario.ARQUIVO).write_text(texto, encoding="utf-8")
    assert _abrir(ambiente.pasta) == diario.NORMAL
    diario.esquecer()   # esta sessão é morta de fora
    assert _abrir(ambiente.pasta) == diario.ENCERRADO


def test_nul_no_comeco_da_linha_nao_esconde_o_evento():
    assert diario.classificar(["\x00\x00" + _linha("ABERTURA a")]) == diario.ENCERRADO


def test_queda_log_que_nao_pode_ser_movido_nao_e_apagado(ambiente, monkeypatch):
    _escrever(ambiente.pasta, "ABERTURA versao=1.3.0")
    (ambiente.pasta / diario.ARQUIVO_QUEDA).write_text("Fatal Python error: x\n", encoding="utf-8")

    def recusar(*_a, **_k):
        raise PermissionError("arquivo aberto por outro programa")

    monkeypatch.setattr(diario.os, "replace", recusar)
    assert _abrir(ambiente.pasta) == diario.CAIU
    assert ambiente.faulthandler.arquivo == diario.ARQUIVO_QUEDA
    diario.esquecer()   # fecha o queda.log para ler o que ficou
    queda = (ambiente.pasta / diario.ARQUIVO_QUEDA).read_text(encoding="utf-8")
    assert queda.startswith("Fatal Python error: x")


def test_segundo_abrir_nao_empilha_os_ganchos(ambiente, monkeypatch):
    vistos = []
    monkeypatch.setattr(sys, "excepthook", lambda tipo, valor, rastro: vistos.append(tipo))
    _abrir(ambiente.pasta)
    _abrir(ambiente.pasta)
    try:
        raise ValueError("de proposito")
    except ValueError:
        sys.excepthook(*sys.exc_info())
    assert vistos == [ValueError]
    assert _texto(ambiente.pasta).count("ERRO NAO TRATADO (thread principal)") == 1
