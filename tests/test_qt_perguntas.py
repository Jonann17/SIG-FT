import threading

from PySide6.QtWidgets import QInputDialog, QMessageBox, QWidget

from sigft.app_qt.widgets import dialogs as qd
from sigft.app_qt.widgets.espera import DialogosDeEspera


class Tela(DialogosDeEspera, QWidget):
    pass


def _no_worker(qtbot, func):
    resultado, threads = [], []

    def rodar():
        threads.append(threading.get_ident())
        resultado.append(func())

    t = threading.Thread(target=rodar, daemon=True)
    t.start()
    qtbot.waitUntil(lambda: len(resultado) == 1, timeout=3000)
    return resultado[0]


def test_sim_nao_do_worker_pergunta_na_thread_da_interface(qt_interface, qtbot, monkeypatch):
    onde = []
    monkeypatch.setattr(QMessageBox, "question", staticmethod(
        lambda *a, **k: onde.append(threading.get_ident()) or QMessageBox.StandardButton.Yes))
    tela = Tela()
    qtbot.addWidget(tela)
    assert _no_worker(qtbot, lambda: tela.perguntar_sim_nao("T", "Continua?")) is True
    assert onde == [threading.main_thread().ident]


def test_sim_nao_responde_false_no_nao(qt_interface, qtbot, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", staticmethod(
        lambda *a, **k: QMessageBox.StandardButton.No))
    tela = Tela()
    qtbot.addWidget(tela)
    assert tela.perguntar_sim_nao("T", "Continua?") is False  # da própria thread da interface


def test_pedir_texto_e_cancelar(qt_interface, qtbot, monkeypatch):
    respostas = iter([("PDM-1", True), ("", False)])
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: next(respostas)))
    tela = Tela()
    qtbot.addWidget(tela)
    assert _no_worker(qtbot, lambda: tela.pedir_texto("T", "Novo PDM?")) == "PDM-1"
    assert _no_worker(qtbot, lambda: tela.pedir_texto("T", "Novo PDM?")) is None


def test_avisar_nao_bloqueia_e_mostra_na_thread_da_interface(qt_interface, qtbot, monkeypatch):
    vistos = []
    for nome in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, nome, staticmethod(
            lambda *a, _n=nome, **k: vistos.append((_n, threading.get_ident()))))
    tela = Tela()
    qtbot.addWidget(tela)
    _no_worker(qtbot, lambda: tela.avisar("T", "ok"))
    _no_worker(qtbot, lambda: tela.avisar("T", "cuidado", tipo="aviso"))
    _no_worker(qtbot, lambda: tela.avisar("T", "falhou", tipo="erro"))
    qtbot.waitUntil(lambda: len(vistos) == 3, timeout=2000)
    assert [v[0] for v in vistos] == ["information", "warning", "critical"]
    assert {v[1] for v in vistos} == {threading.main_thread().ident}


def test_selecao_com_caixas(qt_interface, qtbot):
    d = qd.SelecaoComCaixasDialog(None, titulo="Selecione as Fichas",
                                  mensagem="Selecione os PMIBs para processar:",
                                  itens=["A", "B", "C"])
    qtbot.addWidget(d)
    assert d.selecionados() == []
    d.lista.item(2).setCheckState(qd.Qt.CheckState.Checked)
    assert d.selecionados() == ["C"]
    d.botao_todos.click()
    assert d.selecionados() == ["A", "B", "C"]
