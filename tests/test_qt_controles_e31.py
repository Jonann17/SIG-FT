"""Controles da interface antiga que o Qt não tem (E3.1): abas (CTkTabview), área
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
    # nome desconhecido: ValueError, como o CTkTabview (e não KeyError)
    with pytest.raises(ValueError):
        abas.set("Não existe")
    with pytest.raises(ValueError):
        abas.tab("Não existe")


def test_abas_geometria_do_ctktabview(qt_interface, qtbot, folha_do_app):
    # Medido na captura: barra de 27 px (26 da interface antiga + 1 de arredondamento) a 10 px do topo, centrada; o quadro
    # começa 18 px abaixo do topo (a barra entra 18 px nele); o conteúdo da aba
    # começa em y=43 e x=6 (canto de 6 px). Cada botão: texto + 14 px.
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
    assert (topo.x(), topo.y()) == (6, 43)  # winfo na interface antiga: 43
    assert aba.height() == 200 - 43 - 6  # winfo na interface antiga: 151
    b = abas.botoes["Robô Web"]
    assert b.width() == b.fontMetrics().horizontalAdvance("Robô Web") + 14
    assert barra.width() == sum(x.width() for x in abas.botoes.values())


def test_abas_nao_apaga_o_fundo_do_que_vai_dentro(qt_interface, qtbot, folha_do_app):
    # A folha "background: transparent" SEM seletor na aba valia para todos os
    # descendentes: o cartão e os botões da tela embutida perdiam o fundo
    # (Aplicação LMR, Task 8 da Etapa 2).
    from PySide6.QtGui import QColor
    abas = Abas()
    aba = abas.add("A")
    cartao = blocos.cartao(aba.layout())
    botao = blocos.botao("Iniciar", variante="primario", largura=200, altura=50)
    cartao.addWidget(botao)
    abas.setFixedSize(420, 300)
    recipiente = _mostrar(qtbot, abas)  # noqa: F841 -- segura vivo
    quadro_cartao = botao.parentWidget()
    imagem = abas.grab().toImage()

    def cor(w, dx, dy):
        p = w.mapTo(abas, w.rect().topLeft())
        return QColor(imagem.pixel(p.x() + dx, p.y() + dy)).name().upper()

    assert cor(quadro_cartao, 3, quadro_cartao.height() // 2) == theme.COR_CARTAO.upper()
    assert cor(botao, 5, 25) == theme.COLORS["primary"].upper()


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
    # set(0.4) da interface antiga numa barra de 200 x 8: o cheio termina em 8 + 0.4 * 192 = 84,8
    # (medido: 384 numa barra em x=300), não em 80.
    curta = blocos.barra_progresso(largura=200)
    qtbot.addWidget(curta)
    blocos.definir_progresso(curta, 0.4)
    assert curta.value() == 424
    blocos.definir_progresso(curta, 0)
    assert curta.value() == 40  # o ponto de 8 px que a interface antiga mostrava em zero
    blocos.definir_progresso(curta, 1.5)
    assert curta.value() == 1000
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


def test_barra_indeterminada_liga_e_desliga(qt_interface, qtbot):
    # cria_fichas: configure(mode="indeterminate") + start() ... stop().
    barra = blocos.barra_progresso(largura=200)
    qtbot.addWidget(barra)
    blocos.definir_progresso(barra, 0.5)
    blocos.modo_indeterminado(barra, True)
    assert (barra.minimum(), barra.maximum()) == (0, 0)
    blocos.definir_progresso(barra, 0.7)  # não escreve nada com a faixa 0-0
    assert (barra.minimum(), barra.maximum()) == (0, 0)
    blocos.modo_indeterminado(barra, False)
    assert (barra.minimum(), barra.maximum(), barra.value()) == (0, 1000, 0)
    blocos.definir_progresso(barra, 1.0)
    assert barra.value() == 1000


def test_tabela_com_as_cores_do_windows(qt_interface, monkeypatch):
    import sys
    monkeypatch.setattr(sys, "platform", "win32")
    qss = estilo.folha_de_estilo()
    assert "selection-background-color: #0078D7" in qss
    monkeypatch.setattr(sys, "platform", "linux")
    assert "#0078D7" not in estilo.folha_de_estilo()


def test_botao_com_cor_de_fundo_e_hover_do_tema(qt_interface, qtbot):
    b = blocos.botao("Adicionar", cor_fundo="#3A3A3A", altura=28)
    qtbot.addWidget(b)
    assert "background: #3A3A3A" in b.styleSheet()
    assert f"QPushButton:hover {{ background: {estilo.AZUL_CTK_HOVER}; }}" in b.styleSheet()
    c = blocos.botao("x", cor_fundo="#3A3A3A", cor_hover="#454545")
    qtbot.addWidget(c)
    assert "#454545" in c.styleSheet()


def test_uma_cor_de_trilho_so(qt_interface):
    from sigft.app_qt.widgets import controles
    assert controles.COR_TRILHO == estilo.TRILHO_CTK


def test_sem_regras_de_qtabwidget(qt_interface):
    # O CTkTabview é `Abas`; regra de QTabWidget seria código morto.
    assert "QTabBar" not in estilo.folha_de_estilo() and "QTabWidget" not in estilo.folha_de_estilo()


def test_area_rolavel_nao_apaga_o_fundo_dos_filhos(qt_interface, qtbot, folha_do_app):
    # "background: transparent" sem seletor valia para TODO descendente: o cartão
    # e o botão dentro da área perdiam o fundo.
    from PySide6.QtGui import QImage

    area, layout = blocos.area_rolavel(cor="#2B2B2B")
    cartao = blocos.cartao(layout)
    botao = blocos.botao("Gerar", variante="perigo", largura=120, altura=40)
    cartao.addWidget(botao)
    area.resize(400, 300)
    recipiente = _mostrar(qtbot, area)  # noqa: F841 -- segura vivo
    imagem = area.grab().toImage()
    quadro = cartao.parentWidget()
    ponto_cartao = quadro.mapTo(area, quadro.rect().topLeft())
    cor_cartao = imagem.pixelColor(ponto_cartao.x() + 10, ponto_cartao.y() + 5).name().upper()
    centro = botao.mapTo(area, botao.rect().center())
    cor_botao = imagem.pixelColor(centro.x() - 50, centro.y()).name().upper()
    assert cor_cartao == theme.COR_CARTAO.upper()
    assert cor_botao == theme.COLORS["danger"].upper()
    assert isinstance(imagem, QImage)


# --- polimento A5: rádio com a largura mínima da interface antiga e abas com a altura da escolhida ---

def _em_linha(qtbot, *widgets):
    from PySide6.QtWidgets import QHBoxLayout

    recipiente = QWidget()
    linha = QHBoxLayout(recipiente)
    linha.setContentsMargins(0, 0, 0, 0)
    linha.setSpacing(0)
    for w in widgets:
        linha.addWidget(w)
    linha.addStretch()
    qtbot.addWidget(recipiente)
    recipiente.resize(900, 40)
    recipiente.show()
    qtbot.waitExposed(recipiente)
    return recipiente


def test_radio_tem_a_largura_minima_do_ctkradiobutton(qt_interface, qtbot, folha_do_app):
    # O `width=100` padrão do CTkRadioButton é largura MÍNIMA: "Português" e
    # "English" ocupam 100 e empurram o vizinho para o mesmo x de lá; o texto
    # maior alarga. Vale para todo rádio do app (era local do PDM).
    curto, longo = QRadioButton("English"), QRadioButton("Específico (Escolher 1 arquivo)")
    recipiente = _em_linha(qtbot, curto, longo)  # noqa: F841 -- segura vivo
    assert estilo.LARGURA_RADIO_CTK == 100
    assert curto.width() == 100
    assert longo.width() == longo.sizeHint().width() > 100


def test_abas_com_a_altura_da_aba_escolhida(qt_interface, qtbot, folha_do_app):
    # O CTkTabview só põe na grade a aba escolhida: num lugar que não estica
    # (o formulário que rola do PDM), a altura dele é a dessa aba. O
    # QStackedWidget pediria a da maior; `altura_da_escolhida=True` faz como lá.
    def montar(**kw):
        abas = Abas(**kw)
        for nome, altura in (("Alta", 300), ("Baixa", 60)):
            caixa = QWidget()
            caixa.setFixedHeight(altura)
            abas.add(nome).layout().addWidget(caixa)
        recipiente = QWidget()
        coluna = QVBoxLayout(recipiente)
        coluna.addWidget(abas)
        coluna.addStretch(1)       # a sobra fica embaixo, como no formulário do PDM
        qtbot.addWidget(recipiente)
        recipiente.resize(500, 700)
        recipiente.show()
        qtbot.waitExposed(recipiente)
        vivos.append(recipiente)   # sem pai: sem esta referência o Python o apagaria
        return abas

    vivos = []
    abas = montar(altura_da_escolhida=True)
    alta = abas.height()
    abas.set("Baixa")
    qtbot.waitUntil(lambda: abas.height() == alta - 240, timeout=1000)
    abas.botoes["Alta"].click()
    qtbot.waitUntil(lambda: abas.height() == alta, timeout=1000)
    # Sem o parâmetro, continua com a altura da maior (o padrão de hoje).
    padrao = montar()
    altura_padrao = padrao.height()
    padrao.set("Baixa")
    qtbot.wait(20)
    assert padrao.height() == altura_padrao == alta
