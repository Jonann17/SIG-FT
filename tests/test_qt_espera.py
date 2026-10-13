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
    t = threading.Thread(target=lambda: (tela.pausar_e_esperar("Faça login"), terminou.append(True)), daemon=True)
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
    t = threading.Thread(target=lambda: (tela.pausar_e_esperar("x"), terminou.append(True)), daemon=True)
    t.start()
    qtbot.waitUntil(lambda: len(_abertos(qd.PausaLoginDialog)) == 1, timeout=2000)
    _abertos(qd.PausaLoginDialog)[0].close()
    t.join(3)
    assert terminou == [True]


def test_retry_excel_devolve_a_escolha(qt_interface, qtbot):
    tela = Tela()
    qtbot.addWidget(tela)
    respostas = []
    t = threading.Thread(target=lambda: respostas.append(tela.perguntar_retry_excel("C:/a.xlsx")), daemon=True)
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
    t = threading.Thread(target=lambda: respostas.append(tela.perguntar_retry_excel()), daemon=True)
    t.start()
    qtbot.waitUntil(lambda: len(_abertos(qd.RetryLockDialog)) == 1, timeout=2000)
    _abertos(qd.RetryLockDialog)[0].close()
    t.join(3)
    assert respostas == [False]


def test_janela_nasce_na_thread_da_interface(qt_interface, qtbot):
    tela = Tela()
    qtbot.addWidget(tela)
    t = threading.Thread(target=lambda: tela.pausar_e_esperar("x"), daemon=True)
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
    t = threading.Thread(target=lambda: (tela.pausar_e_esperar("x"), terminou.append(True)), daemon=True)
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
    t = threading.Thread(target=lambda: respostas.append(tela.perguntar_retry_excel()), daemon=True)
    t.start()
    qtbot.waitUntil(lambda: len(_abertos(qd.RetryLockDialog)) == 1, timeout=2000)
    QTest.keyClick(_abertos(qd.RetryLockDialog)[0], Qt.Key.Key_Escape)
    t.join(3)
    assert not t.is_alive()
    assert respostas == [False]


def _apertar_enter(janela):
    """Return e Enter (teclado numérico), com o foco no primeiro botão -- o
    caso de uma tecla perdida enquanto a pessoa ainda faz o login."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QPushButton

    botoes = janela.findChildren(QPushButton)
    for botao in botoes:
        assert not botao.autoDefault() and not botao.isDefault(), botao.text()
    if botoes:
        botoes[0].setFocus()
    for tecla in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
        QTest.keyClick(janela, tecla)
        if botoes:
            QTest.keyClick(botoes[0], tecla)


def test_enter_nao_solta_o_login(qt_interface, qtbot):
    # No CTk nenhuma tecla estava ligada: um Enter perdido não pode soltar o
    # robô (e começar o lote) antes de a pessoa terminar o login.
    tela = Tela()
    qtbot.addWidget(tela)
    terminou = []
    t = threading.Thread(target=lambda: (tela.pausar_e_esperar("x"), terminou.append(True)), daemon=True)
    t.start()
    qtbot.waitUntil(lambda: len(_abertos(qd.PausaLoginDialog)) == 1, timeout=2000)
    dialogo = _abertos(qd.PausaLoginDialog)[0]
    _apertar_enter(dialogo)
    qtbot.wait(100)
    assert t.is_alive() and terminou == [] and dialogo.isVisible()
    dialogo.botao.click()
    t.join(3)
    assert terminou == [True]


def test_enter_nao_decide_o_retry_excel(qt_interface, qtbot):
    tela = Tela()
    qtbot.addWidget(tela)
    respostas = []
    t = threading.Thread(target=lambda: respostas.append(tela.perguntar_retry_excel()), daemon=True)
    t.start()
    qtbot.waitUntil(lambda: len(_abertos(qd.RetryLockDialog)) == 1, timeout=2000)
    dialogo = _abertos(qd.RetryLockDialog)[0]
    _apertar_enter(dialogo)
    qtbot.wait(100)
    assert t.is_alive() and respostas == [] and dialogo.isVisible()
    dialogo.botao_cancelar.click()
    t.join(3)
    assert respostas == [False]


def test_enter_nao_decide_os_arquivos_travados(qt_interface, qtbot):
    from sigft.app_qt.widgets import dialogos_selecao

    evento, resultado = threading.Event(), {}
    dialogo = dialogos_selecao.ArquivosTravadosDialog(
        None, itens=[("a.xlsx", "aberto no Excel", "feche o arquivo")], momento="antes",
        evento_espera=evento, resultado=resultado)
    qtbot.addWidget(dialogo)
    dialogo.show()
    qtbot.waitExposed(dialogo)
    _apertar_enter(dialogo)
    qtbot.wait(50)
    assert not evento.is_set() and resultado == {} and dialogo.isVisible()
    dialogo.seguir()
    assert evento.is_set() and resultado == {"repetir": False}


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
    t1 = threading.Thread(target=lambda: (tela.pausar_e_esperar("x"), terminou.append(True)), daemon=True)
    t2 = threading.Thread(target=lambda: respostas.append(tela.perguntar_retry_excel()), daemon=True)
    t1.start()
    t2.start()
    # a thread principal precisa seguir processando eventos (join travaria a fila)
    qtbot.waitUntil(lambda: not t1.is_alive() and not t2.is_alive(), timeout=3000)
    assert not t1.is_alive() and not t2.is_alive()
    assert terminou == [True]
    assert respostas == [False]
    assert "falha de construcao" in capsys.readouterr().err
