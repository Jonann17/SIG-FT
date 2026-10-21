"""Interruptor (CTkSwitch) e menu de opções (CTkOptionMenu) desenhados à mão.

As medidas vêm do tema dark-blue da interface antiga e da captura da tela LMR
de 2026-10-08 (Xvfb, 1280x850). As cores, desde 2026-10-20, são as da paleta do
tema (`estilo.paleta_atual()`): a fidelidade à CTk caiu com a saída dela.
"""
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QStyle, QStyleOptionButton

from sigft.app_qt import estilo
from sigft.app_qt.widgets import controles


def _cor(imagem, x, y) -> str:
    return imagem.pixelColor(x, y).name().upper()


def _na_folha(qtbot, widget):
    widget.setStyleSheet(estilo.folha_de_estilo())
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    return widget


# --- Interruptor ----------------------------------------------------------------

def test_interruptor_e_uma_caixa_de_marcar_com_as_medidas_do_ctkswitch(qt_interface, qtbot):
    chave = _na_folha(qtbot, controles.Interruptor("Começar de um código específico",
                                                   tamanho_fonte=12))
    assert isinstance(chave, QCheckBox)
    # CTkSwitch: height=24; trilho 36x18 na coluna 0, 6 px de vão, e o texto.
    largura_texto = chave.fontMetrics().horizontalAdvance(chave.text())
    assert chave.sizeHint().height() == 24
    assert chave.sizeHint().width() == 36 + 6 + largura_texto
    assert chave.font().pixelSize() == 12


def test_interruptor_desenha_trilho_e_botao_como_o_ctk(qt_interface, qtbot):
    p = estilo.paleta_atual()
    chave = _na_folha(qtbot, controles.Interruptor("Ligar"))
    chave.resize(chave.sizeHint())
    y0 = (chave.height() - 18) // 2
    desligado = chave.grab().toImage()
    # Desligado: botão (18 px, `texto_suave`) à esquerda, trilho (30x12, `borda`)
    # à direita dele. 2026-10-20: cores da paleta (eram #D5D9DE/#4A4D50 da CTk).
    assert _cor(desligado, 9, y0 + 9) == p["texto_suave"]
    assert _cor(desligado, 27, y0 + 9) == p["borda"]
    assert _cor(desligado, 27, y0 + 1) != p["borda"]   # o trilho é mais baixo que o botão
    chave.setChecked(True)
    ligado = chave.grab().toImage()
    # Ligado: trilho `primaria`, botão `texto_sobre_primaria` (contrasta nos dois temas).
    assert _cor(ligado, 27, y0 + 9) == p["texto_sobre_primaria"]
    assert _cor(ligado, 9, y0 + 9) == p["primaria"]


def test_interruptor_alterna_clicando_no_texto(qt_interface, qtbot):
    chave = _na_folha(qtbot, controles.Interruptor("Começar de um código específico"))
    chave.resize(chave.sizeHint())
    sinais = []
    chave.toggled.connect(sinais.append)
    qtbot.mouseClick(chave, Qt.MouseButton.LeftButton, pos=QPoint(chave.width() - 5, 12))
    qtbot.mouseClick(chave, Qt.MouseButton.LeftButton, pos=QPoint(5, 12))
    assert sinais == [True, False]


# --- Menu de opções ---------------------------------------------------------------

def test_menu_de_opcoes_pinta_como_o_ctkoptionmenu(qt_interface, qtbot):
    menu = _na_folha(qtbot, controles.MenuDeOpcoes(["Plan1", "LMR"]))
    menu.setFixedWidth(300)
    assert isinstance(menu, QComboBox)
    # 2026-10-20: 32, a altura de campo do sistema visual (a regra QComboBox da folha);
    # era os 28 do CTkOptionMenu, que saiu com a interface antiga em 2026-10-15.
    assert menu.height() == 32 and menu.sizeHint().height() == 32
    imagem = menu.grab().toImage()
    p = estilo.paleta_atual()
    # 2026-10-20: a cara do QComboBox da folha (era o azul #1F538D/#14375E da CTk):
    # corpo `superficie_alta` inteiro (a seta não tem mais quadrado próprio) e a
    # borda de 1 px `borda`.
    assert _cor(imagem, 150, 3) == p["superficie_alta"]
    assert _cor(imagem, 300 - 26, 3) == p["superficie_alta"]
    assert _cor(imagem, 150, 0) == p["borda"]
    # A seta é um "v" na cor do texto, no quadrado da direita.
    cores_da_seta = {_cor(imagem, x, y) for x in range(280, 293) for y in range(10, 18)}
    assert p["texto"] in cores_da_seta
    assert menu.currentText() == "Plan1"


# --- caixa de marcar comum (folha global) -------------------------------------------

def test_caixa_de_marcar_global_tem_24_px_como_a_ctkcheckbox(qt_interface, qtbot):
    # CTkCheckBox: checkbox_width/height = 24, borda 3 incluída. No QSS, width e
    # height do ::indicator NÃO contam a borda: 18 + 2*3.
    caixa = _na_folha(qtbot, QCheckBox("Versões de teste"))
    opcao = QStyleOptionButton()
    caixa.initStyleOption(opcao)
    indicador = caixa.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, opcao, caixa)
    assert (indicador.width(), indicador.height()) == (24, 24)
