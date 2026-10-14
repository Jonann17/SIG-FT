"""`JanelaPainel` da interface Qt (E3.1): hospeda um `montar(parent)`."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QScrollArea

from sigft.app_qt.widgets.painel_janela import JanelaPainel


@pytest.fixture
def folha_do_app(qapp):
    """A folha do app aplicada, como em produção (sem ela os botões medem outra coisa)."""
    from sigft.app_qt import estilo as _estilo
    anterior = qapp.styleSheet()
    qapp.setStyleSheet(_estilo.folha_de_estilo())
    yield
    qapp.setStyleSheet(anterior)


def test_monta_o_painel_dentro_da_area_rolavel(qt_interface, qtbot):
    recebidos = []

    def montar(parent):
        recebidos.append(parent)
        parent.layout().addWidget(QLabel("painel de gastos"))

    janela = JanelaPainel(None, titulo="Gastos de IA", montar=montar)
    qtbot.addWidget(janela)
    assert janela.isVisible()
    assert janela.windowTitle() == "Gastos de IA"
    assert (janela.width(), janela.height()) == (900, 680)
    assert recebidos == [janela.conteudo]
    assert isinstance(janela.area, QScrollArea) and janela.area.widget() is janela.conteudo
    assert [w.text() for w in janela.conteudo.findChildren(QLabel)] == ["painel de gastos"]


def test_nao_trava_a_janela_principal_e_minimiza(qt_interface, qtbot):
    janela = JanelaPainel(None, titulo="Mural", montar=lambda p: None, geometria="700x500")
    qtbot.addWidget(janela)
    assert (janela.width(), janela.height()) == (700, 500)
    assert janela.windowModality() == Qt.WindowModality.NonModal
    flags = janela.windowFlags()
    assert flags & Qt.WindowType.Window
    assert flags & Qt.WindowType.WindowMinimizeButtonHint


def test_botao_fechar(qt_interface, qtbot, folha_do_app):
    janela = JanelaPainel(None, titulo="x", montar=lambda p: None)
    qtbot.addWidget(janela)
    assert janela.botao_fechar.text() == "Fechar"
    assert janela.botao_fechar.width() == 120
    janela.botao_fechar.click()
    assert not janela.isVisible()


def test_medidas_do_customtkinter(qt_interface, qtbot, folha_do_app):
    # CTkScrollableFrame com padx=10/pady=10; botão Fechar 120 de largura com
    # pady=(0, 12), centrado.
    janela = JanelaPainel(None, titulo="x", montar=lambda p: None)
    qtbot.addWidget(janela)
    qtbot.waitExposed(janela)
    area, botao = janela.area, janela.botao_fechar
    assert (area.x(), area.y()) == (10, 10)
    assert janela.width() - (area.x() + area.width()) == 10
    assert botao.y() - (area.y() + area.height()) == 10
    assert janela.height() - (botao.y() + botao.height()) == 12
    assert abs((botao.x() + botao.width() / 2) - janela.width() / 2) <= 1


def test_sai_do_registro_ao_fechar_e_ao_ser_destruida(qt_interface, qtbot):
    from PySide6.QtWidgets import QWidget

    from sigft.app_qt.widgets import painel_janela

    sem_pai = JanelaPainel(None, titulo="x", montar=lambda p: None)
    assert id(sem_pai) in painel_janela._ABERTAS
    sem_pai.close()
    assert id(sem_pai) not in painel_janela._ABERTAS

    pai = QWidget()
    com_pai = JanelaPainel(pai, titulo="y", montar=lambda p: None)
    chave = id(com_pai)
    assert chave in painel_janela._ABERTAS
    pai.deleteLater()
    del com_pai
    qtbot.waitUntil(lambda: chave not in painel_janela._ABERTAS, timeout=2000)
