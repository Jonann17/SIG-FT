"""Tema escuro / claro / sistema, trocado com o app aberto (sistema visual, Task 7, 2026-10-20).

`sigft/app_qt/tema.py` guarda a escolha nas preferências, decide o tema de fato
("sistema" segue o Windows), regera a folha do app e repinta os ícones. Cada
teste aqui que troca o tema devolve o app ao escuro no fim (fixture `volta_ao_escuro`):
o tema é estado do processo, e os outros testes medem cores do escuro.
"""
import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from sigft.app import tokens
from sigft.app_qt import estilo, icones, tema
from sigft.app_qt.widgets import blocos, controles


@pytest.fixture
def volta_ao_escuro(qapp, tmp_path, monkeypatch):
    """Prefs num arquivo de teste e, no fim, o tema e a folha de antes."""
    monkeypatch.setattr(tema, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    folha, atual = qapp.styleSheet(), estilo.TEMA_ATUAL
    yield qapp
    estilo.TEMA_ATUAL = atual
    qapp.setStyleSheet(folha)


def _cor(imagem, x, y) -> str:
    return imagem.pixelColor(x, y).name().upper()


# --- escolha e preferência ------------------------------------------------------

def test_os_tres_temas():
    assert tema.TEMAS == ("escuro", "claro", "sistema")


def test_sistema_segue_o_windows(monkeypatch):
    monkeypatch.setattr(tema, "_esquema_do_sistema", lambda: "claro")
    assert tema.efetivo("sistema") == "claro"
    assert tema.efetivo("escuro") == "escuro"
    monkeypatch.setattr(tema, "_esquema_do_sistema", lambda: "escuro")
    assert tema.efetivo("sistema") == "escuro"
    assert tema.efetivo("claro") == "claro"


def test_esquema_do_sistema_le_o_qt(qapp, monkeypatch):
    from PySide6.QtCore import Qt

    class _Dicas:
        def __init__(self, esquema):
            self.esquema = esquema

        def colorScheme(self):  # noqa: N802 -- nome do Qt
            return self.esquema

    for esquema, esperado in ((Qt.ColorScheme.Light, "claro"), (Qt.ColorScheme.Dark, "escuro"),
                              (Qt.ColorScheme.Unknown, "escuro")):
        monkeypatch.setattr(tema.QGuiApplication, "styleHints", staticmethod(lambda e=esquema: _Dicas(e)))
        assert tema._esquema_do_sistema() == esperado


def test_aplicar_troca_a_folha_e_lembra(volta_ao_escuro):
    qapp = volta_ao_escuro
    tema.aplicar(qapp, "claro")
    assert tokens.CLARO["fundo"] in qapp.styleSheet()
    assert estilo.TEMA_ATUAL == "claro"
    assert tema.escolhido() == "claro"
    tema.aplicar(qapp, "escuro")
    assert tokens.ESCURO["fundo"] in qapp.styleSheet()
    assert tema.escolhido() == "escuro"


def test_aplicar_sistema_lembra_sistema_e_pinta_o_do_windows(volta_ao_escuro, monkeypatch):
    monkeypatch.setattr(tema, "_esquema_do_sistema", lambda: "claro")
    tema.aplicar(volta_ao_escuro, "sistema")
    assert tema.escolhido() == "sistema"
    assert estilo.TEMA_ATUAL == "claro"


def test_aplicar_sem_gravar_nao_mexe_nas_prefs(volta_ao_escuro):
    tema.aplicar(volta_ao_escuro, "claro", gravar=False)
    assert estilo.TEMA_ATUAL == "claro"
    assert tema.escolhido() == "escuro"


def test_escolha_invalida_vira_escuro(tmp_path, monkeypatch):
    monkeypatch.setattr(tema, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    (tmp_path / "p.json").write_text('{"tema": "roxo"}', encoding="utf-8")
    assert tema.escolhido() == "escuro"
    (tmp_path / "p.json").write_text('{"preferencias": {"tema": "roxo"}}', encoding="utf-8")
    assert tema.escolhido() == "escuro"
    (tmp_path / "p.json").write_text('{"preferencias": {"tema": 3}}', encoding="utf-8")
    assert tema.escolhido() == "escuro"


def test_sem_arquivo_de_prefs_e_escuro(tmp_path, monkeypatch):
    monkeypatch.setattr(tema, "_arquivo_de_prefs", lambda: tmp_path / "nao_existe.json")
    assert tema.escolhido() == "escuro"


def test_aplicar_escolha_invalida_vira_escuro(volta_ao_escuro):
    tema.aplicar(volta_ao_escuro, "claro")
    tema.aplicar(volta_ao_escuro, "roxo")
    assert estilo.TEMA_ATUAL == "escuro"
    assert tema.escolhido() == "escuro"


def test_aplicar_avisa_quem_desenhou(volta_ao_escuro):
    recebidos = []
    tema.mudou.connect(recebidos.append)
    try:
        tema.aplicar(volta_ao_escuro, "claro")
    finally:
        tema.mudou.disconnect(recebidos.append)
    assert recebidos == ["claro"]


def test_gravar_que_falha_nao_impede_a_troca(volta_ao_escuro, monkeypatch, tmp_path):
    # Pasta de dados somente-leitura (ou disco cheio): o tema muda igual.
    monkeypatch.setattr(tema, "_arquivo_de_prefs", lambda: tmp_path / "nao_ha" / "p.json")
    tema.aplicar(volta_ao_escuro, "claro")
    assert estilo.TEMA_ATUAL == "claro"


# --- item 1 herdado: as folhas seguem o TEMA_ATUAL lido na chamada ----------------

def test_as_folhas_sem_argumento_seguem_o_tema_atual(monkeypatch):
    monkeypatch.setattr(estilo, "TEMA_ATUAL", "claro")
    assert estilo.folha_de_estilo() == estilo.folha_de_estilo("claro")
    assert estilo.folha_rolagem_ctk("#x") == estilo.folha_rolagem_ctk("#x", tema="claro")
    assert estilo._folha_e31() == estilo._folha_e31("claro")
    assert estilo._folha_telas() == estilo._folha_telas("claro")
    monkeypatch.setattr(estilo, "TEMA_ATUAL", "escuro")
    assert estilo.folha_de_estilo() == estilo.folha_de_estilo("escuro")


# --- itens 2 e 3: o que já está na tela repinta no tema novo ----------------------

def test_interruptor_e_icone_ja_na_tela_repintam_no_tema_novo(volta_ao_escuro, qtbot):
    qapp = volta_ao_escuro
    tema.aplicar(qapp, "escuro", gravar=False)
    raiz = QWidget()
    chave = controles.Interruptor("Ligar", raiz)
    chave.resize(chave.sizeHint())
    botao = QPushButton("Home", raiz)
    botao.move(0, 40)
    icones.aplicar(botao, "house")
    qtbot.addWidget(raiz)
    raiz.show()
    qtbot.waitExposed(raiz)
    y0 = (chave.height() - 18) // 2
    assert _cor(chave.grab().toImage(), 27, y0 + 9) == tokens.ESCURO["borda"]

    tema.aplicar(qapp, "claro")

    assert _cor(chave.grab().toImage(), 27, y0 + 9) == tokens.CLARO["borda"]
    assert _cor(chave.grab().toImage(), 9, y0 + 9) == tokens.CLARO["texto_suave"]
    assert botao.icon().cacheKey() == icones.icone("house", tokens.CLARO["texto"]).cacheKey()


def test_aplicar_repinta_os_icones_das_janelas(volta_ao_escuro, monkeypatch):
    chamados = []
    monkeypatch.setattr(icones, "reaplicar", chamados.append)
    janela = QWidget()
    try:
        tema.aplicar(volta_ao_escuro, "claro")
        assert janela in chamados
    finally:
        janela.deleteLater()


# --- item 4: o ícone do menu segue o item ativo e o mouse --------------------------

def _janela(qt_interface, tmp_path, monkeypatch):
    from sigft.app_qt import main as qmain

    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    return qmain.SIG_FT_App()


def _fechar(janela):
    janela.fechar_sem_perguntar = True
    janela.close()
    janela.deleteLater()


def test_no_claro_o_item_ativo_do_menu_tem_icone_na_cor_marca(volta_ao_escuro, qt_interface,
                                                               tmp_path, monkeypatch):
    from sigft.app_qt import catalogo

    tema.aplicar(volta_ao_escuro, "claro", gravar=False)
    janela = _janela(qt_interface, tmp_path, monkeypatch)
    try:
        alvo, botao = next((a, b) for a, b in janela.botoes_menu.items() if b.isEnabled())
        nome = catalogo.ICONE_DA_TELA[alvo]
        marca = tokens.CLARO["marca"]
        assert botao.icon().cacheKey() == icones.icone(nome, tokens.CLARO["texto"], 16).cacheKey()
        janela.show_frame(alvo)
        assert botao.icon().cacheKey() == icones.icone(nome, marca, 16).cacheKey()
        # O Home, que estava ativo, volta ao texto.
        assert janela.botao_home.icon().cacheKey() == \
            icones.icone("house", tokens.CLARO["texto"], 16).cacheKey()
        janela.show_frame("Home")
        assert botao.icon().cacheKey() == icones.icone(nome, tokens.CLARO["texto"], 16).cacheKey()
        assert janela.botao_home.icon().cacheKey() == icones.icone("house", marca, 16).cacheKey()
    finally:
        _fechar(janela)


def test_no_escuro_o_item_ativo_do_menu_tem_icone_na_cor_do_texto(volta_ao_escuro, qt_interface,
                                                                  tmp_path, monkeypatch):
    # No escuro o texto do item escolhido é `texto` (a marca sobre a marca a 25% sumiria).
    tema.aplicar(volta_ao_escuro, "escuro", gravar=False)
    janela = _janela(qt_interface, tmp_path, monkeypatch)
    try:
        assert janela.botao_home.icon().cacheKey() == \
            icones.icone("house", estilo.MENU_ESCOLHIDO["escuro"]["texto"], 16).cacheKey()
    finally:
        _fechar(janela)


def test_icone_do_menu_segue_o_mouse(volta_ao_escuro, qapp):
    tema.aplicar(qapp, "claro", gravar=False)
    botao = QPushButton(" Copiar")
    botao.setProperty("menu", True)
    icones.aplicar(botao, "copy", papel_cor_ativo="menu_escolhido", tamanho=16)
    try:
        normal = icones.icone("copy", tokens.CLARO["texto"], 16).cacheKey()
        sobre = icones.icone("copy", tokens.CLARO["marca"], 16).cacheKey()
        assert botao.icon().cacheKey() == normal
        QApplication.sendEvent(botao, QEvent(QEvent.Type.Enter))
        assert botao.icon().cacheKey() == sobre
        QApplication.sendEvent(botao, QEvent(QEvent.Type.Leave))
        assert botao.icon().cacheKey() == normal
    finally:
        botao.deleteLater()


# --- itens 5 e 6: cache da falha e papel desconhecido ------------------------------

def test_icone_que_falha_avisa_uma_vez_so(qapp, caplog):
    caplog.set_level("WARNING", logger="sigft.app_qt.icones")
    icones._CACHE.pop(("nao-existe-mesmo", "#FFFFFF", 18), None)
    try:
        assert icones.icone("nao-existe-mesmo", "#FFFFFF").isNull()
        assert icones.icone("nao-existe-mesmo", "#FFFFFF").isNull()
        avisos = [r for r in caplog.records if "nao-existe-mesmo" in r.getMessage()]
        assert len(avisos) == 1
    finally:
        icones._CACHE.pop(("nao-existe-mesmo", "#FFFFFF", 18), None)


def test_papel_de_cor_desconhecido_cai_na_cor_da_variante(qapp, caplog):
    caplog.set_level("WARNING", logger="sigft.app_qt.icones")
    botao = QPushButton("Apagar")
    botao.setProperty("variante", "perigo")
    icones.aplicar(botao, "trash-2", papel_cor="papel_que_nao_existe")
    assert botao.icon().cacheKey() == icones.icone("trash-2", estilo.TEXTO_SOBRE_PERIGO).cacheKey()
    assert any("papel_que_nao_existe" in r.getMessage() for r in caplog.records)


# --- item 7: abas, menu e barras de rolagem seguem o tema --------------------------

def test_abas_e_menu_escolhido_seguem_o_tema(volta_ao_escuro):
    tema.aplicar(volta_ao_escuro, "claro", gravar=False)
    folha = volta_ao_escuro.styleSheet()
    p, menu = tokens.CLARO, estilo.MENU_ESCOLHIDO["claro"]
    assert f'#barra_abas QPushButton:checked {{ background: {p["marca"]};' in folha
    assert f'#barra_abas {{ background: {p["superficie_alta"]}; }}' in folha
    assert f"background: {menu['fundo']};\n    color: {menu['texto']}; }}" in folha
    assert estilo.MENU_ESCOLHIDO["escuro"]["fundo"] not in folha


def test_a_barra_da_area_rolavel_nao_guarda_cor(qapp):
    # A cor da alça vem da folha do app (que a troca de tema regera); a folha
    # própria da barra só tem medidas. Com cor ali, a alça ficava no tema velho.
    import re

    area, _ = blocos.area_rolavel(barra_sempre_visivel=True)
    try:
        assert not re.search(r"#[0-9A-Fa-f]{6}", area.verticalScrollBar().styleSheet())
    finally:
        area.deleteLater()


def test_a_alca_da_area_rolavel_pinta_no_tema_novo(volta_ao_escuro, qtbot):
    from PySide6.QtWidgets import QLabel

    # Nasce no escuro; a troca para o claro tem de chegar à alça.
    tema.aplicar(volta_ao_escuro, "escuro", gravar=False)
    area, corpo = blocos.area_rolavel(fundo="tela")
    for i in range(40):
        corpo.addWidget(QLabel(f"linha {i}"))
    qtbot.addWidget(area)
    area.resize(300, 200)
    area.show()
    qtbot.waitExposed(area)
    barra = area.verticalScrollBar()
    qtbot.waitUntil(lambda: barra.width() == estilo.LARGURA_ROLAGEM_CTK, timeout=1000)
    tema.aplicar(volta_ao_escuro, "claro", gravar=False)
    imagem = barra.grab().toImage()
    meio = barra.width() // 2
    cores = {_cor(imagem, meio, y) for y in range(barra.height())}
    assert tokens.CLARO["borda"] in cores


# --- o seletor da Home --------------------------------------------------------------

def test_home_tem_o_seletor_de_tema(volta_ao_escuro, qt_interface, tmp_path, monkeypatch):
    janela = _janela(qt_interface, tmp_path, monkeypatch)
    try:
        home = janela.telas["Home"]
        assert set(home.botoes_tema) == set(tema.TEMAS)
        icone_esperado = {"escuro": "moon", "claro": "sun", "sistema": "monitor"}
        for escolha, botao in home.botoes_tema.items():
            assert botao.property("icone") == icone_esperado[escolha]
            assert botao.toolTip()
            assert "—" not in botao.toolTip() and "–" not in botao.toolTip()
        assert home.botoes_tema["escuro"].property("ativo") is True
    finally:
        _fechar(janela)


def test_clicar_claro_muda_o_fundo_da_tela(volta_ao_escuro, qt_interface, qtbot, tmp_path, monkeypatch):
    from PySide6.QtCore import Qt

    qt_interface.setStyleSheet(estilo.folha_de_estilo("escuro"))
    estilo.TEMA_ATUAL = "escuro"
    janela = _janela(qt_interface, tmp_path, monkeypatch)
    try:
        janela.resize(1280, 850)
        janela.show()
        qtbot.waitExposed(janela)
        janela.show_frame("Translator")
        janela.show_frame("Home")
        home = janela.telas["Home"]
        tela = janela.findChild(QWidget, "tela")
        assert tela is not None
        assert tela.palette().color(tela.backgroundRole()).name().upper() == tokens.ESCURO["fundo"]

        qtbot.mouseClick(home.botoes_tema["claro"], Qt.MouseButton.LeftButton)

        assert estilo.TEMA_ATUAL == "claro"
        assert tema.escolhido() == "claro"
        assert tela.palette().color(tela.backgroundRole()).name().upper() == tokens.CLARO["fundo"]
        assert home.botoes_tema["claro"].property("ativo") is True
        assert home.botoes_tema["escuro"].property("ativo") is False
        assert home.botoes_tema["claro"].icon().cacheKey() == \
            icones.icone("sun", estilo.MENU_ESCOLHIDO["claro"]["texto"], 16).cacheKey()
    finally:
        _fechar(janela)


def test_o_seletor_cabe_na_linha_do_titulo_sem_alargar_a_home(qt_interface, qtbot):
    # A barra de botões já ocupa quase toda a largura da Home a 1280 px: o
    # seletor fica na linha do título, à direita, e a Home não ganha rolagem
    # horizontal nem mexe no título (46, 46, h 38).
    from sigft.app_qt.views import home as home_mod

    class Controller:
        api_keys: dict = {}

    qt_interface.setStyleSheet(estilo.folha_de_estilo("escuro"))
    tela = home_mod.HomeView(controller=Controller())
    qtbot.addWidget(tela)
    tela.resize(1280 - estilo.LARGURA_BARRA_LATERAL, 850)
    tela.show()
    qtbot.waitExposed(tela)
    corpo = tela.widget()
    assert corpo.minimumSizeHint().width() <= tela.viewport().width()
    qtbot.waitUntil(lambda: corpo.width() == tela.viewport().width(), timeout=1000)
    titulo = tela.label_titulo.geometry()
    for botao in tela.botoes_tema.values():
        from PySide6.QtCore import QPoint

        caixa = botao.geometry()
        topo = botao.mapTo(corpo, QPoint(0, 0))
        assert topo.y() >= 46 and topo.y() + caixa.height() <= 46 + titulo.height()
        assert topo.x() + caixa.width() <= corpo.width() - 57


# --- a abertura e o --smoke --tema ---------------------------------------------------

def test_tema_da_linha_de_comando():
    from sigft.app_qt import main as qmain

    assert qmain._tema_da_linha_de_comando(["frontend.py", "--smoke"]) is None
    assert qmain._tema_da_linha_de_comando(["frontend.py", "--smoke", "--tema", "claro"]) == "claro"
    assert qmain._tema_da_linha_de_comando(["frontend.py", "--tema=sistema"]) == "sistema"


def test_preparar_qt_aplica_o_tema_salvo_sem_gravar(volta_ao_escuro, monkeypatch, tmp_path):
    from sigft.app_qt import main as qmain

    (tmp_path / "p.json").write_text('{"preferencias": {"tema": "claro"}}', encoding="utf-8")
    monkeypatch.setattr(qmain.cursor, "instalar", lambda app: None)
    gravados = []
    monkeypatch.setattr("sigft.core.prefs.gravar_preferencia", lambda *a, **k: gravados.append(a))
    qmain._preparar_qt()
    assert estilo.TEMA_ATUAL == "claro"
    assert tokens.CLARO["fundo"] in volta_ao_escuro.styleSheet()
    qmain._preparar_qt("escuro")   # o --smoke --tema escuro ganha da preferência
    assert estilo.TEMA_ATUAL == "escuro"
    assert gravados == []


def test_com_sistema_escolhido_a_troca_do_windows_troca_o_app(volta_ao_escuro, monkeypatch):
    tema.seguir_o_sistema(volta_ao_escuro)
    tema.aplicar(volta_ao_escuro, "sistema")
    monkeypatch.setattr(tema, "_esquema_do_sistema", lambda: "claro")
    tema._seguindo[0](None)
    assert estilo.TEMA_ATUAL == "claro"
    tema.aplicar(volta_ao_escuro, "escuro")
    tema._seguindo[0](None)   # escolha fixa: o Windows não manda
    assert estilo.TEMA_ATUAL == "escuro"
