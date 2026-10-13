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
