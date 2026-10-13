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
