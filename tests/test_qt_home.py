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


def test_titulo_do_card_fica_no_topo_quando_o_vizinho_e_mais_alto(qt_interface, qtbot):
    # No CTk (grid sticky="nsew" + pack no topo) a sobra do card mais baixo da
    # linha fica EMBAIXO; o título não desce para o meio do card.
    from PySide6.QtWidgets import QLabel

    from sigft.app_qt import estilo

    anterior = qt_interface.styleSheet()
    estilo.carregar_fontes()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    try:
        home = HomeView(controller=Controller())
        qtbot.addWidget(home)
        home.resize(1280 - estilo.LARGURA_BARRA_LATERAL, 850)
        home.show()
        qtbot.waitExposed(home)
        alturas = {card.height() for card in home.cards.values()}
        assert len(alturas) > 1, "o teste precisa de cards de alturas diferentes"
        topos = set()
        for card in home.cards.values():
            titulo = card.findChild(QLabel, "card_titulo")
            topos.add(titulo.y())
            assert titulo.height() == titulo.sizeHint().height(), card._alvo
        assert len(topos) == 1, topos  # 1 da borda + 12 da margem, em todos
    finally:
        qt_interface.setStyleSheet(anterior)


def test_tela_nao_migrada_diz_o_nome(qt_interface, qtbot):
    t = TelaNaoMigrada("AutoSpec")
    qtbot.addWidget(t)
    assert "AutoSpec" in t.mensagem.text()


def test_barra_com_a_largura_do_ctkbutton_e_sem_rolagem_lateral(qt_interface, qtbot):
    # CTkButton: 140 px, ou o texto + 7 de cada lado quando não cabe (lá: 148 no
    # "Atividades do dia" e 140 nos outros). Com a folga antiga (16 px) e o negrito
    # na largura do Tk, a linha passava dos 1003 px da área e surgia rolagem lateral.
    from sigft.app_qt import estilo

    anterior = qt_interface.styleSheet()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    try:
        estilo.carregar_fontes()
        home = HomeView(controller=Controller())
        qtbot.addWidget(home)
        home.resize(1280 - estilo.LARGURA_BARRA_LATERAL, 850)
        home.show()
        qtbot.waitExposed(home)
        for botao in home.botoes_barra.values():
            assert botao.width() >= estilo.LARGURA_BOTAO_CTK, botao.text()
        assert home.horizontalScrollBar().maximum() == 0  # nada a rolar de lado
    finally:
        qt_interface.setStyleSheet(anterior)
