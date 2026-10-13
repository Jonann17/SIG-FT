import threading

import pytest

from sigft.app_qt import interface


def test_funcao_roda_na_thread_da_interface(qt_interface, qtbot):
    vistas = []
    t = threading.Thread(target=lambda: interface.na_interface(
        lambda: vistas.append(threading.get_ident())))
    t.start()
    t.join()
    qtbot.waitUntil(lambda: len(vistas) == 1, timeout=2000)
    assert vistas == [threading.main_thread().ident]


def test_excecao_nao_derruba_o_canal(qt_interface, qtbot, capsys):
    ok = []
    interface.na_interface(lambda: 1 / 0)
    interface.na_interface(lambda: ok.append(True))
    qtbot.waitUntil(lambda: len(ok) == 1, timeout=2000)
    assert "ZeroDivisionError" in capsys.readouterr().err


def test_argumentos_sao_repassados(qt_interface, qtbot):
    recebido = []
    interface.na_interface(lambda a, b: recebido.append((a, b)), 1, "x")
    qtbot.waitUntil(lambda: len(recebido) == 1, timeout=2000)
    assert recebido == [(1, "x")]


def test_sabe_em_que_thread_esta(qt_interface):
    assert interface.na_thread_da_interface()
    fora = []
    t = threading.Thread(target=lambda: fora.append(interface.na_thread_da_interface()))
    t.start()
    t.join()
    assert fora == [False]


def test_sem_instalar_avisa(monkeypatch):
    monkeypatch.setattr(interface, "_ponte", None)
    with pytest.raises(RuntimeError, match="instalar"):
        interface.na_interface(print)
