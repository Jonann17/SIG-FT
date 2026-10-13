import threading

from PySide6.QtWidgets import QWidget

from sigft.app_qt.widgets import dialogs as qd
from sigft.app_qt.widgets.espera import DialogosDeEspera


class Tela(DialogosDeEspera, QWidget):
    pass


def _abertos(tipo):
    from PySide6.QtWidgets import QApplication
    return [w for w in QApplication.topLevelWidgets() if isinstance(w, tipo) and w.isVisible()]


def test_worker_espera_o_login_e_e_solto(qt_interface, qtbot):
    tela = Tela()
    qtbot.addWidget(tela)
    terminou = []
    t = threading.Thread(target=lambda: (tela.pausar_e_esperar("Faça login"), terminou.append(True)))
    t.start()
    qtbot.waitUntil(lambda: len(_abertos(qd.PausaLoginDialog)) == 1, timeout=2000)
    assert terminou == []
    _abertos(qd.PausaLoginDialog)[0].botao.click()
    t.join(3)
    assert terminou == [True]


def test_fechar_no_x_tambem_solta_o_worker(qt_interface, qtbot):
    tela = Tela()
    qtbot.addWidget(tela)
    terminou = []
    t = threading.Thread(target=lambda: (tela.pausar_e_esperar("x"), terminou.append(True)))
    t.start()
    qtbot.waitUntil(lambda: len(_abertos(qd.PausaLoginDialog)) == 1, timeout=2000)
    _abertos(qd.PausaLoginDialog)[0].close()
    t.join(3)
    assert terminou == [True]


def test_retry_excel_devolve_a_escolha(qt_interface, qtbot):
    tela = Tela()
    qtbot.addWidget(tela)
    respostas = []
    t = threading.Thread(target=lambda: respostas.append(tela.perguntar_retry_excel("C:/a.xlsx")))
    t.start()
    qtbot.waitUntil(lambda: len(_abertos(qd.RetryLockDialog)) == 1, timeout=2000)
    dialogo = _abertos(qd.RetryLockDialog)[0]
    assert "a.xlsx" in dialogo.rotulo.text()
    dialogo.botao_repetir.click()
    t.join(3)
    assert respostas == [True]


def test_retry_excel_fechar_no_x_e_cancelar(qt_interface, qtbot):
    tela = Tela()
    qtbot.addWidget(tela)
    respostas = []
    t = threading.Thread(target=lambda: respostas.append(tela.perguntar_retry_excel()))
    t.start()
    qtbot.waitUntil(lambda: len(_abertos(qd.RetryLockDialog)) == 1, timeout=2000)
    _abertos(qd.RetryLockDialog)[0].close()
    t.join(3)
    assert respostas == [False]


def test_janela_nasce_na_thread_da_interface(qt_interface, qtbot):
    tela = Tela()
    qtbot.addWidget(tela)
    t = threading.Thread(target=lambda: tela.pausar_e_esperar("x"))
    t.start()
    qtbot.waitUntil(lambda: len(_abertos(qd.PausaLoginDialog)) == 1, timeout=2000)
    dialogo = _abertos(qd.PausaLoginDialog)[0]
    assert dialogo.thread() is tela.thread()
    dialogo.botao.click()
    t.join(3)


def test_esc_solta_o_login(qt_interface, qtbot):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    tela = Tela()
    qtbot.addWidget(tela)
    terminou = []
    t = threading.Thread(target=lambda: (tela.pausar_e_esperar("x"), terminou.append(True)))
    t.start()
    qtbot.waitUntil(lambda: len(_abertos(qd.PausaLoginDialog)) == 1, timeout=2000)
    QTest.keyClick(_abertos(qd.PausaLoginDialog)[0], Qt.Key.Key_Escape)
    t.join(3)
    assert not t.is_alive()
    assert terminou == [True]


def test_esc_no_retry_excel_e_cancelar(qt_interface, qtbot):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    tela = Tela()
    qtbot.addWidget(tela)
    respostas = []
    t = threading.Thread(target=lambda: respostas.append(tela.perguntar_retry_excel()))
    t.start()
    qtbot.waitUntil(lambda: len(_abertos(qd.RetryLockDialog)) == 1, timeout=2000)
    QTest.keyClick(_abertos(qd.RetryLockDialog)[0], Qt.Key.Key_Escape)
    t.join(3)
    assert not t.is_alive()
    assert respostas == [False]


def test_botoes_continuam_respondendo_como_antes(qt_interface, qtbot):
    evento = threading.Event()
    resultado = {}
    dialogo = qd.RetryLockDialog(None, evento_espera=evento, resultado=resultado)
    qtbot.addWidget(dialogo)
    dialogo.show()
    dialogo.botao_repetir.click()
    assert resultado == {"retry": True}  # o reject() do Esc/X nao sobrescreve
    assert evento.is_set()

    evento2 = threading.Event()
    resultado2 = {}
    dialogo2 = qd.RetryLockDialog(None, evento_espera=evento2, resultado=resultado2)
    qtbot.addWidget(dialogo2)
    dialogo2.show()
    dialogo2.botao_cancelar.click()
    assert resultado2 == {"retry": False}
    assert evento2.is_set()


def test_falha_ao_construir_o_dialogo_solta_o_worker(qt_interface, qtbot, monkeypatch, capsys):
    def quebrado(*a, **k):
        raise RuntimeError("falha de construcao")

    monkeypatch.setattr(qd, "PausaLoginDialog", quebrado)
    monkeypatch.setattr(qd, "RetryLockDialog", quebrado)
    tela = Tela()
    qtbot.addWidget(tela)
    terminou = []
    respostas = []
    t1 = threading.Thread(target=lambda: (tela.pausar_e_esperar("x"), terminou.append(True)))
    t2 = threading.Thread(target=lambda: respostas.append(tela.perguntar_retry_excel()))
    t1.start()
    t2.start()
    # a thread principal precisa seguir processando eventos (join travaria a fila)
    qtbot.waitUntil(lambda: not t1.is_alive() and not t2.is_alive(), timeout=3000)
    assert not t1.is_alive() and not t2.is_alive()
    assert terminou == [True]
    assert respostas == [False]
    assert "falha de construcao" in capsys.readouterr().err
