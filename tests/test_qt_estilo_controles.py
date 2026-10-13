from sigft.app import theme
from sigft.app_qt import estilo


def _qss():
    return estilo.folha_de_estilo()


def test_botao_padrao_e_o_azul_do_customtkinter():
    assert "QPushButton {" in _qss()
    assert estilo.AZUL_CTK == "#1F538D" and estilo.AZUL_CTK_HOVER == "#14375E"
    trecho = _qss().split("QPushButton {", 1)[1].split("}", 1)[0]
    assert estilo.AZUL_CTK in trecho


def test_variante_primario_usa_a_cor_da_marca():
    assert f'QPushButton[variante="primario"] {{ background: {theme.COLORS["primary"]}' in _qss()


def test_campos_abas_listas_e_cartao():
    qss = _qss()
    for trecho in ("QLineEdit", "#343638", "#565B5E", "QTabBar::tab:selected",
                   "QListWidget", "#1E1E1E", "#cartao", theme.COR_CARTAO, "QComboBox"):
        assert trecho in qss, trecho


def test_caixa_marcada_e_fundo_de_dialogo_como_no_ctk():
    qss = _qss()
    assert f"QCheckBox::indicator:checked {{ background: {estilo.AZUL_CTK}" in qss
    assert f"QDialog {{ background: {estilo.cinza_tk('gray10')}" in qss


def test_home_e_dialogos_usam_primario_onde_o_ctk_pintava_primary():
    from sigft.app_qt.views import home
    variantes = {chave: variante for chave, _t, variante in home.BARRA}
    assert variantes["modelos"] == "primario" and variantes["gastos"] == "primario"


# --- Aplicada a widgets de verdade (paridade medida nas capturas de 2026-10-08) ---

def _sob_a_folha(qtbot, *filhos):
    """Põe os widgets num recipiente com a folha do app e devolve o recipiente."""
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    recipiente = QWidget()
    recipiente.setStyleSheet(_qss())
    layout = QVBoxLayout(recipiente)
    for filho in filhos:
        layout.addWidget(filho)
    qtbot.addWidget(recipiente)
    recipiente.show()
    qtbot.waitExposed(recipiente)
    return recipiente


def _cor_do_texto(botao) -> str:
    from PySide6.QtGui import QPalette

    return botao.palette().color(QPalette.ColorRole.ButtonText).name().upper()


def test_texto_do_botao_comum_e_o_do_tema_do_ctk(qt_interface, qtbot):
    # CTkButton sem text_color pinta #DCE4EE (dark-blue.json), e não o
    # text_light (#E0E0E0) do theme.py. Medido: seletor de arquivo e barra da Home.
    from PySide6.QtWidgets import QPushButton

    comum, barra = QPushButton("Selecionar"), QPushButton("Chaves de API")
    barra.setProperty("barra", True)
    recipiente = _sob_a_folha(qtbot, comum, barra)  # noqa: F841 -- segura os filhos vivos
    assert estilo.TEXTO_BOTAO_CTK == "#DCE4EE"
    assert _cor_do_texto(comum) == "#DCE4EE"
    assert _cor_do_texto(barra) == "#DCE4EE"


def test_menu_home_e_glossario_mantem_o_text_light_que_o_ctk_escrevia(qt_interface, qtbot):
    from PySide6.QtWidgets import QPushButton

    menu, home = QPushButton("  1. Cria Fichas PMIB"), QPushButton("Home", objectName="home")
    menu.setProperty("menu", True)
    glossario = QPushButton("Abrir glossário")
    glossario.setProperty("variante", "contorno_padrao")
    recipiente = _sob_a_folha(qtbot, menu, home, glossario)  # noqa: F841 -- segura os filhos vivos
    for botao in (menu, home, glossario):
        assert _cor_do_texto(botao) == theme.COLORS["text_light"].upper(), botao.text()


def test_campo_de_texto_e_o_ctkentry_do_tema(qt_interface, qtbot):
    # CTkEntry: 28 px de altura com a borda, fonte 13, dica gray62. Sem folha
    # própria no campo: é a regra global que dá isso.
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QLineEdit

    campo = QLineEdit()
    campo.setPlaceholderText("Ex: 4500063671.1234")
    recipiente = _sob_a_folha(qtbot, campo)  # noqa: F841 -- segura os filhos vivos
    assert campo.height() == estilo.ALTURA_CAMPO_CTK == 28
    assert campo.sizeHint().height() == 28
    assert campo.font().pixelSize() == 13
    paleta = campo.palette()
    assert paleta.color(QPalette.ColorRole.PlaceholderText).name().upper() == estilo.cinza_tk("gray62")
    assert paleta.color(QPalette.ColorRole.Text).name().upper() == estilo.cinza_tk("gray84")
