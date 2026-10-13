"""Peças de `sigft/app_qt/widgets/blocos.py` medidas na tela, com a folha do app."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from sigft.app import theme
from sigft.app_qt import estilo
from sigft.app_qt.widgets import blocos


@pytest.fixture
def com_folha(qt_interface):
    """A folha de estilo do app aplicada, como em produção; devolvida no fim."""
    anterior = qt_interface.styleSheet()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    yield qt_interface
    qt_interface.setStyleSheet(anterior)


@pytest.mark.parametrize("variante, altura", [
    ("primario", 50), ("perigo", 40), ("contorno_padrao", 32), ("contorno", 40), (None, 35),
])
def test_botao_fica_com_a_altura_pedida(com_folha, qtbot, variante, altura):
    # A folha do app tem `min-height: 28px` para QPushButton; antes ela ganhava
    # do `setFixedHeight` e TODO botão saía com 28 px (30 com borda).
    tela = QWidget()
    QVBoxLayout(tela).addWidget(b := blocos.botao("x", variante=variante, largura=200, altura=altura))
    qtbot.addWidget(tela)
    tela.show()
    qtbot.waitExposed(tela)
    assert b.height() == altura
    assert b.sizeHint().height() == altura
    assert b.width() == 200


def test_cor_do_texto_nao_vale_para_o_botao_desligado(com_folha, qtbot):
    b = blocos.botao("x", altura=40, cor_texto="#FFFFFF")
    qtbot.addWidget(b)
    folha = b.styleSheet()
    assert "color: #FFFFFF" in folha
    assert f"QPushButton:disabled {{ color: {estilo.cinza_tk('gray60')}; }}" in folha


def test_rotulo_com_quebra_ocupa_a_largura_do_cartao(com_folha, qtbot):
    # Com `setAlignment(AlignHCenter)` no layout do cartão, o rótulo com quebra
    # automática ganhava largura estreita e o texto saía cortado.
    tela = QWidget()
    tela.resize(800, 400)
    corpo = blocos.cartao(QVBoxLayout(tela))
    texto = "Primeira linha bem comprida do texto de apoio.\nSegunda.\nTerceira linha."
    corpo.addWidget(r := blocos.rotulo(texto, cor=estilo.cinza_tk(theme.COR_TEXTO_APOIO)))
    qtbot.addWidget(tela)
    tela.show()
    qtbot.waitExposed(tela)
    assert corpo.alignment() == Qt.AlignmentFlag(0)
    assert r.width() == corpo.contentsRect().width()
    assert r.height() >= r.heightForWidth(r.width())
