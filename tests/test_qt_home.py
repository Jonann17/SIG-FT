from PySide6.QtCore import QPoint, Qt

from sigft.app_qt import catalogo
from sigft.app_qt.views.home import HomeView
from sigft.app_qt.views.nao_migrada import TelaNaoMigrada


class Controller:
    def __init__(self):
        self.visitas = []

    def show_frame(self, nome):
        self.visitas.append(nome)


def test_um_card_por_modulo_com_os_textos(qt_interface, qtbot):
    home = HomeView(controller=Controller())
    qtbot.addWidget(home)
    assert list(home.cards) == [m[0] for m in catalogo.MODULOS]


def test_clique_no_card_inteiro_navega(qt_interface, qtbot):
    ctrl = Controller()
    home = HomeView(controller=ctrl)
    qtbot.addWidget(home)
    home.show()
    qtbot.mouseClick(home.cards["Analyzer"], Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
    assert ctrl.visitas == ["Analyzer"]


def test_icones_da_barra_em_preto_e_branco(qt_interface, qtbot):
    home = HomeView(controller=Controller())
    qtbot.addWidget(home)
    assert "\ufe0e" in home.botoes_barra["atividades"].text()


def test_canal_de_testes_lembra_a_escolha(qt_interface, qtbot, monkeypatch):
    from sigft.services import updater
    gravado = []
    monkeypatch.setattr(updater, "canal_testes_ligado", lambda: False)
    monkeypatch.setattr(updater, "ligar_canal_testes", gravado.append)
    home = HomeView(controller=Controller())
    qtbot.addWidget(home)
    home.caixa_canal_testes.setChecked(True)
    assert gravado == [True]


def test_tela_nao_migrada_diz_o_nome(qt_interface, qtbot):
    t = TelaNaoMigrada("AutoSpec")
    qtbot.addWidget(t)
    assert "AutoSpec" in t.mensagem.text()
