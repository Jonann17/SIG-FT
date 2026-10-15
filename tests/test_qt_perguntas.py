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


def test_selecao_com_caixas_tem_as_medidas_e_a_cara_da_janela_do_ctk(qt_interface, qtbot):
    # Janela antiga de 450x600 (sigft/app/views/lmr.py), medida na captura de 2026-10-08:
    # rótulo 14 negrito em y=10 (28 de altura); quadro rolável #212121 em (10, 53),
    # 430x494; caixas de 24 px a cada 28 px, a primeira em (16, 61); "Todos" 80x28
    # em (10, 562) e "CONFIRMAR" 150x28 em (290, 562).
    from PySide6.QtCore import QPoint, Qt

    from sigft.app import theme
    from sigft.app_qt import estilo

    d = qd.SelecaoComCaixasDialog(None, titulo="Selecione as Fichas",
                                  mensagem="Selecione os PMIBs para processar:",
                                  itens=[f"4500063671.{i:04d}" for i in range(1, 31)])
    d.setStyleSheet(estilo.folha_de_estilo())
    qtbot.addWidget(d)
    d.show()
    qtbot.waitExposed(d)

    def caixa(w):
        p = w.mapTo(d, w.rect().topLeft())
        return (p.x(), p.y(), w.width(), w.height())

    assert (d.width(), d.height()) == (450, 600)
    assert caixa(d.rotulo)[1:4:2] == (10, 28)
    assert caixa(d.quadro) == (10, 53, 430, 494)
    assert caixa(d.botao_todos) == (10, 562, 80, 28)
    assert caixa(d.botao_confirmar) == (290, 562, 150, 28)
    linha = d.lista.visualItemRect(d.lista.item(0))
    origem = d.lista.viewport().mapTo(d, linha.topLeft())
    assert (origem.x(), origem.y(), linha.height()) == (16, 59, 28)

    d.lista.item(1).setCheckState(Qt.CheckState.Checked)
    imagem = d.grab().toImage()
    cor = lambda x, y: imagem.pixelColor(x, y).name().upper()  # noqa: E731
    assert cor(200, 300) == "#212121"
    assert cor(17, 73) == estilo.BORDA_CTK                      # borda da caixa desmarcada
    assert cor(22, 92) == theme.COLORS["primary"].upper()       # caixa marcada cheia de primary

    # Clicar no TEXTO marca, como na CTkCheckBox; fora dele, não.
    retangulo = d.lista.visualItemRect(d.lista.item(2))
    qtbot.mouseClick(d.lista.viewport(), Qt.MouseButton.LeftButton,
                     pos=QPoint(retangulo.x() + 60, retangulo.center().y()))
    qtbot.mouseClick(d.lista.viewport(), Qt.MouseButton.LeftButton,
                     pos=QPoint(retangulo.x() + 350, retangulo.center().y()))
    assert d.selecionados() == ["4500063671.0002", "4500063671.0003"]


def test_sim_nao_escolhe_o_botao_padrao(qt_interface, qtbot, monkeypatch):
    # O `askyesno` do Tk tem o "Sim" como padrão; numa ação destrutiva a tela
    # pede o "Não" (`padrao_sim=False`, o padrão de `perguntar_sim_nao`).
    padroes = []
    monkeypatch.setattr(QMessageBox, "question", staticmethod(
        lambda _p, _t, _m, _b, padrao: padroes.append(padrao) or QMessageBox.StandardButton.Yes))
    tela = Tela()
    qtbot.addWidget(tela)
    assert tela.perguntar_sim_nao("Relatório", "Salvar?", padrao_sim=True) is True
    assert tela.perguntar_sim_nao("Confirmar", "Trocar o PDM?") is True
    assert padroes == [QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No]
