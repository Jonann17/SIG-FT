"""Controles do CustomTkinter que o Qt não tem (E3.1): abas (CTkTabview), área
rolável (CTkScrollableFrame), barra de progresso, slider, e a folha global de
rádio, lista crua (tk.Listbox) e tabela (ttk.Treeview).

(Interruptor/CTkSwitch, CTkOptionMenu e a caixa de marcar: `widgets/controles.py`,
da frente da Aplicação LMR, testados em `test_qt_controles.py`.)

As medidas vêm das capturas do tema dark-blue (demo lado a lado em
`capturas/e3.1/`): ver o relatório da E3.1.
"""
import pytest
from PySide6.QtWidgets import QLabel, QRadioButton, QVBoxLayout, QWidget

from sigft.app import theme
from sigft.app_qt import estilo
from sigft.app_qt.widgets import blocos
from sigft.app_qt.widgets.abas import Abas


@pytest.fixture
def folha_do_app(qapp):
    anterior = qapp.styleSheet()
    qapp.setStyleSheet(estilo.folha_de_estilo())
    yield
    qapp.setStyleSheet(anterior)


def _mostrar(qtbot, *widgets):
    recipiente = QWidget()
    layout = QVBoxLayout(recipiente)
    for w in widgets:
        layout.addWidget(w)
    qtbot.addWidget(recipiente)
    recipiente.show()
    qtbot.waitExposed(recipiente)
    return recipiente


# --- Abas (CTkTabview) ------------------------------------------------------

def test_abas_add_tab_set_get_e_aviso(qt_interface, qtbot):
    mudancas = []
    abas = Abas(ao_mudar=mudancas.append)
    qtbot.addWidget(abas)
    um = abas.add("Processamento IA (Gerar Excel)")
    dois = abas.add("Robô Web (Preencher Portal)")
    assert isinstance(um.layout(), QVBoxLayout)
    assert abas.tab("Robô Web (Preencher Portal)") is dois
    assert abas.get() == "Processamento IA (Gerar Excel)"  # a primeira fica escolhida
    abas.botoes["Robô Web (Preencher Portal)"].click()
    assert abas.get() == "Robô Web (Preencher Portal)" and abas.pilha.currentWidget() is dois
    assert mudancas == ["Robô Web (Preencher Portal)"]
    abas.set("Processamento IA (Gerar Excel)")
    assert abas.botoes["Processamento IA (Gerar Excel)"].isChecked()
    with pytest.raises(ValueError):
        abas.add("Robô Web (Preencher Portal)")


def test_abas_geometria_do_ctktabview(qt_interface, qtbot, folha_do_app):
    # Medido na captura: barra de 27 px (26 do CTk + 1 de arredondamento) a 10 px do topo, centrada; o quadro
    # começa 18 px abaixo do topo (a barra entra 18 px nele); o conteúdo da aba
    # começa em y=42 e x=6 (canto de 6 px). Cada botão: texto + 14 px.
    abas = Abas()
    aba = abas.add("Processamento IA (Gerar Excel)")
    abas.add("Robô Web")
    abas.setFixedSize(420, 200)
    recipiente = _mostrar(qtbot, abas)  # noqa: F841 -- segura vivo
    barra, quadro = abas.barra, abas.quadro
    assert barra.y() == 10 and barra.height() == 27
    assert abs((barra.x() + barra.width() / 2) - abas.width() / 2) <= 1
    assert quadro.y() == 18 and quadro.height() == 200 - 18 and quadro.width() == 420
    topo = aba.mapTo(abas, aba.rect().topLeft())
    assert (topo.x(), topo.y()) == (6, 42)
    b = abas.botoes["Robô Web"]
    assert b.width() == b.fontMetrics().horizontalAdvance("Robô Web") + 14
    assert barra.width() == sum(x.width() for x in abas.botoes.values())


def test_abas_cores_por_parametro(qt_interface, qtbot):
    # As telas pintam fg_color="#2B2B2B", segmented_button_fg_color="#161616" e
    # o selecionado em primary.
    abas = Abas(cor_fundo="#2B2B2B", cor_barra="#161616", cor_selecionada=theme.COLORS["primary"],
                cor_selecionada_hover=theme.COLORS["primary_hover"])
    qtbot.addWidget(abas)
    abas.add("A")
    assert "#2B2B2B" in abas.quadro.styleSheet()
    folha = abas.barra.styleSheet()
    assert "#161616" in folha and theme.COLORS["primary"] in folha
    padrao = Abas()
    qtbot.addWidget(padrao)
    assert estilo.cinza_tk("gray13") in padrao.quadro.styleSheet()  # CTkFrame fg_color
    assert estilo.cinza_tk("gray29") in padrao.barra.styleSheet()


# --- área rolável e barra de progresso ---------------------------------------

def test_area_rolavel_devolve_area_e_layout(qt_interface, qtbot):
    area, layout = blocos.area_rolavel(cor="#2B2B2B")
    qtbot.addWidget(area)
    layout.addWidget(QLabel("linha"))
    assert area.widgetResizable()
    assert area.widget().layout() is layout
    assert "#2B2B2B" in area.styleSheet()
    transparente, _ = blocos.area_rolavel()
    qtbot.addWidget(transparente)
    assert "transparent" in transparente.styleSheet()


def test_barra_progresso_do_ctkprogressbar(qt_interface, qtbot):
    barra = blocos.barra_progresso(largura=600, altura=12, cor=theme.COLORS["primary"])
    qtbot.addWidget(barra)
    assert (barra.width(), barra.height()) == (600, 12)
    assert not barra.isTextVisible()
    folha = barra.styleSheet()
    assert theme.COLORS["primary"] in folha and estilo.TRILHO_CTK in folha
    assert "border-radius: 6px" in folha  # metade da altura: corner_radius=1000
    # set(0.4) do CTk numa barra de 200 x 8: o cheio termina em 8 + 0.4 * 192 = 84,8
    # (medido: 384 numa barra em x=300), não em 80.
    ctk = blocos.barra_progresso(largura=200)
    qtbot.addWidget(ctk)
    blocos.definir_progresso(ctk, 0.4)
    assert ctk.value() == 424
    blocos.definir_progresso(ctk, 0)
    assert ctk.value() == 40  # o ponto de 8 px que o CTk mostra em zero
    blocos.definir_progresso(ctk, 1.5)
    assert ctk.value() == 1000
    padrao = blocos.barra_progresso()
    qtbot.addWidget(padrao)
    assert padrao.height() == 8 and estilo.AZUL_CTK in padrao.styleSheet()


# --- folha global: rádio, slider, tabela e lista crua ----------------------

def test_radio_e_slider_com_as_medidas_do_ctk(qt_interface, qtbot, folha_do_app):
    radio = QRadioButton("Opção A")
    slider = blocos.slider(minimo=0, maximo=10, largura=200)
    recipiente = _mostrar(qtbot, radio, slider)  # noqa: F841 -- segura vivo
    # CTkRadioButton 22x22; CTkSlider 200x16.
    assert estilo.TAMANHO_RADIO_CTK == 22
    assert radio.height() == 22
    assert (slider.width(), slider.height()) == (200, 16)
    assert (slider.minimum(), slider.maximum()) == (0, 10)
    qss = estilo.folha_de_estilo()
    for trecho in ("QRadioButton::indicator", "QSlider::handle:horizontal",
                   "QSlider::sub-page:horizontal", "QTreeView", "QHeaderView::section",
                   'QListWidget[claro="true"]'):
        assert trecho in qss, trecho


def test_slider_com_as_cores_da_tela(qt_interface, qtbot):
    # Analisador: button_color e progress_color = primary.
    s = blocos.slider(cor_botao=theme.COLORS["primary"], cor_percorrido=theme.COLORS["primary"])
    qtbot.addWidget(s)
    assert s.styleSheet().count(theme.COLORS["primary"]) == 2


def test_tabela_e_lista_crua_com_as_cores_do_tk(qt_interface):
    import sys
    t = estilo.TABELA_TK["win32" if sys.platform == "win32" else "outro"]
    qss = estilo.folha_de_estilo()
    assert f"selection-background-color: {t['selecao']}" in qss
    assert "QTreeView { background: #FFFFFF; color: #000000;" in qss


def test_fonte_tk_pixel_ou_ponto(qt_interface):
    f = blocos.fonte_tk(("Roboto", 14, "bold"))
    assert f.pixelSize() == 14 and f.bold()
    g = blocos.fonte_tk(("Consolas", 11), em_pontos=True)
    assert g.pointSize() == 11 and not g.bold()
    assert g.families()[0] == "Consolas"
