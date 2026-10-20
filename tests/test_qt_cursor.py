"""A mãozinha do mouse em todo widget clicável (2026-10-20).

Relato: na Home, botões como "Salvar Chaves" e o menu lateral mostravam a
seta -- a fábrica `blocos.botao` (125 usos) nunca pôs a mãozinha.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLabel, QPushButton, QRadioButton, QWidget

from sigft.app_qt import cursor
from sigft.app_qt.widgets import blocos

MAO = Qt.CursorShape.PointingHandCursor
SETA = Qt.CursorShape.ArrowCursor


def _mostrar(qtbot, *widgets):
    pai = QWidget()
    qtbot.addWidget(pai)
    for w in widgets:
        w.setParent(pai)
    pai.show()
    return pai


def test_botao_da_fabrica_ganha_a_maozinha(qapp, qtbot):
    cursor.instalar(qapp)
    b = blocos.botao("Salvar Chaves")
    _pai = _mostrar(qtbot, b)
    assert b.cursor().shape() == MAO


def test_radio_combo_e_botao_cru_tambem(qapp, qtbot):
    cursor.instalar(qapp)
    r, c, p = QRadioButton("Direcionada"), QComboBox(), QPushButton("  Home")
    _pai = _mostrar(qtbot, r, c, p)
    assert {r.cursor().shape(), c.cursor().shape(), p.cursor().shape()} == {MAO}


def test_texto_nao_ganha_maozinha(qapp, qtbot):
    cursor.instalar(qapp)
    rotulo = QLabel("só texto")
    _pai = _mostrar(qtbot, rotulo)
    assert rotulo.cursor().shape() == SETA


def test_desabilitado_volta_a_seta_e_reabilitado_volta_a_mao(qapp, qtbot):
    cursor.instalar(qapp)
    b = blocos.botao("Rodar")
    _pai = _mostrar(qtbot, b)
    b.setEnabled(False)
    assert b.cursor().shape() == SETA
    b.setEnabled(True)
    assert b.cursor().shape() == MAO


def test_quem_escolheu_o_proprio_cursor_manda(qapp, qtbot):
    cursor.instalar(qapp)
    b = QPushButton("arrastar")
    b.setCursor(Qt.CursorShape.OpenHandCursor)
    _pai = _mostrar(qtbot, b)
    assert b.cursor().shape() == Qt.CursorShape.OpenHandCursor


def test_instalar_duas_vezes_nao_duplica(qapp):
    assert cursor.instalar(qapp) is cursor.instalar(qapp)


def test_o_app_instala_o_filtro_ao_subir():
    import inspect
    from sigft.app_qt import main
    assert "cursor.instalar(app)" in inspect.getsource(main._preparar_qt)
