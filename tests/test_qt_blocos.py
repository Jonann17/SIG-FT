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


# --- nome de arquivo longo: elidido, nunca alarga o formulário (polimento A3) ----
NOME_LONGO = ("Lista de PDMs SAM-GM revisao final aprovada pelo cliente em setembro de 2026 "
              "- versao definitiva para fatiamento geral.xlsx")


def test_rotulo_elidido_com_espaco_mede_e_mostra_como_o_qlabel(com_folha, qtbot):
    elidido = blocos.rotulo("Template FT.xlsx", alinhar="esquerda", elidir=True)
    comum = blocos.rotulo("Template FT.xlsx", alinhar="esquerda")
    comum.setWordWrap(False)
    for r in (elidido, comum):
        qtbot.addWidget(r)
        r.ensurePolished()
    assert isinstance(elidido, blocos.RotuloElidido) and not elidido.wordWrap()
    assert elidido.sizeHint() == comum.sizeHint()
    elidido.resize(elidido.sizeHint())
    assert elidido.texto_visivel() == elidido.text() == "Template FT.xlsx"


def _linha_de_arquivo(rotulo):
    from PySide6.QtWidgets import QHBoxLayout

    tela = QWidget()
    linha = QHBoxLayout(tela)
    linha.setContentsMargins(0, 0, 0, 0)
    linha.setSpacing(0)
    linha.addWidget(blocos.botao("Selecionar", largura=100))
    linha.addSpacing(15)
    linha.addWidget(rotulo)
    linha.addStretch()
    return tela


def test_rotulo_elidido_sem_espaco_corta_no_meio_e_nao_alarga(com_folha, qtbot):
    r = blocos.rotulo("Nenhum arquivo selecionado", alinhar="esquerda", elidir=True)
    tela = _linha_de_arquivo(r)
    qtbot.addWidget(tela)
    minima_antes = tela.minimumSizeHint().width()

    r.mostrar_caminho("/dados/" + NOME_LONGO)

    assert tela.minimumSizeHint().width() <= minima_antes, "o nome longo alargava a linha"
    tela.resize(500, 40)
    tela.show()
    qtbot.waitExposed(tela)
    # O texto do rótulo continua inteiro; o caminho completo vai no tooltip.
    assert r.text() == NOME_LONGO and r.toolTip() == "/dados/" + NOME_LONGO
    visivel = r.texto_visivel()
    assert "…" in visivel and visivel.startswith("Lista") and visivel.endswith(".xlsx")
    assert r.fontMetrics().horizontalAdvance(visivel) <= r.contentsRect().width()
    assert r.geometry().right() < tela.width()
    # Com espaço de novo, volta a mostrar tudo.
    tela.resize(1400, 40)
    qtbot.waitUntil(lambda: r.texto_visivel() == NOME_LONGO, timeout=1000)


def test_rotulo_elidido_desenha_o_texto_visivel(com_folha, qtbot):
    # O que se vê é o texto elidido, na cor da folha do rótulo.
    from PySide6.QtGui import QColor

    r = blocos.rotulo(NOME_LONGO, alinhar="esquerda", cor="#00FF00", elidir=True)
    tela = _linha_de_arquivo(r)
    qtbot.addWidget(tela)
    tela.resize(400, 40)
    tela.show()
    qtbot.waitExposed(tela)
    imagem = r.grab().toImage()
    verdes = [x for x in range(imagem.width()) for y in range(imagem.height())
              if QColor(imagem.pixel(x, y)).green() > 150 and QColor(imagem.pixel(x, y)).red() < 100]
    assert verdes and max(verdes) < r.width()


# --- área rolável com a barra sempre à vista (polimento A4) ---------------------
def test_area_rolavel_com_a_barra_sempre_visivel_e_o_recorte_do_ctk(com_folha, qtbot):
    # CTkScrollableFrame: a barra fica SEMPRE à vista (alça cheia sem nada para
    # rolar), numa faixa de 17 px (16 da barra + 1 até a borda direita), com a
    # alça de 8 a 4 px do começo da faixa e 10 px do topo; o conteúdo começa
    # 6 px para dentro e vai até a faixa; e o canvas fica 6 px para dentro do
    # quadro em cima e embaixo: o que rola some ali.
    from PySide6.QtCore import QPoint

    tela = QWidget()
    raiz = QVBoxLayout(tela)
    raiz.setContentsMargins(0, 0, 0, 0)
    area, corpo = blocos.area_rolavel(raiz, cor="gray13", barra_sempre_visivel=True)
    rotulo = blocos.rotulo("linha", alinhar="esquerda")
    corpo.addWidget(rotulo)
    qtbot.addWidget(tela)
    tela.resize(400, 300)
    tela.show()
    qtbot.waitExposed(tela)

    assert area.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOn
    barra = area.verticalScrollBar()
    # A folha própria da barra entra numa volta do laço depois da global (10 px).
    qtbot.waitUntil(lambda: barra.width() == 17, timeout=1000)
    assert barra.isVisible()
    p = barra.mapTo(area, QPoint(0, 0))
    assert (p.x(), p.y(), barra.width(), barra.height()) == (400 - 17, 0, 17, 300)
    assert "margin: 10px 5px 10px 4px" in barra.styleSheet()
    vista = area.viewport()
    assert (vista.x(), vista.y(), vista.width(), vista.height()) == (0, 6, 400 - 17, 300 - 12)
    p = rotulo.mapTo(area, QPoint(0, 0))
    assert (p.x(), p.y(), rotulo.width()) == (6, 6, 400 - 17 - 6)


def test_area_rolavel_sem_o_parametro_continua_igual(com_folha, qtbot):
    area, corpo = blocos.area_rolavel(cor="gray13")
    qtbot.addWidget(area)
    assert area.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    margens = corpo.contentsMargins()
    assert (margens.left(), margens.top(), margens.right(), margens.bottom()) == (6, 6, 6, 6)


# --- polimento B1/B4: folha reconstruída da base e botões sem foco ----------------
def test_pintar_reconstroi_a_folha_a_partir_da_base(com_folha, qtbot):
    # O `configure(fg_color=...)` da interface antiga: trocar a cor de novo não acumula regra.
    b = blocos.botao("Selecionar", variante="cinza", tamanho_fonte=12)
    qtbot.addWidget(b)
    base = b.styleSheet()
    for cor in ("#035D67", "#123456", "#035D67"):
        blocos.pintar(b, f"QPushButton {{ background: {cor}; }}")
    assert b.styleSheet() == f"{base} QPushButton {{ background: #035D67; }}"
    assert b.styleSheet().count("background") == 1


def test_marcar_arquivo_escolhido_nao_acumula(com_folha, qtbot):
    b = blocos.botao("Selecionar", variante="cinza")
    r = blocos.rotulo("Nenhum arquivo selecionado", alinhar="esquerda", elidir=True)
    for w in (b, r):
        qtbot.addWidget(w)
    blocos.marcar_arquivo_escolhido(b, r, "/d/a.xlsx")
    folhas = (b.styleSheet(), r.styleSheet())
    blocos.marcar_arquivo_escolhido(b, r, "/d/b.xlsx")
    blocos.marcar_arquivo_escolhido(b, r, "/d/c.xlsx")
    assert (b.styleSheet(), r.styleSheet()) == folhas
    assert r.text() == "c.xlsx" and r.toolTip() == "/d/c.xlsx"
    assert theme.COLORS["accent"] in r.styleSheet() and theme.COLORS["primary"] in b.styleSheet()


def test_botao_nao_pega_foco_e_nenhuma_tecla_o_aperta(com_folha, qtbot):
    # Como o CTkButton, que nunca pegava o foco: Espaço e Enter não o apertam,
    # nem numa janela de diálogo (onde o Qt o faria "padrão").
    from PySide6.QtWidgets import QDialog, QLineEdit

    dialogo = QDialog()
    layout = QVBoxLayout(dialogo)
    campo = QLineEdit()
    b = blocos.botao("Confirmar", variante="primario")
    cliques = []
    b.clicked.connect(lambda: cliques.append(1))
    layout.addWidget(campo)
    layout.addWidget(b)
    qtbot.addWidget(dialogo)
    dialogo.show()
    qtbot.waitExposed(dialogo)
    assert b.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert not b.autoDefault() and not b.isDefault()
    campo.setFocus()
    for tecla in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space, Qt.Key.Key_Tab):
        qtbot.keyClick(campo, tecla)
    assert cliques == [] and not b.hasFocus()
