from sigft.app import theme, tokens
from sigft.app_qt import estilo


def _qss():
    return estilo.folha_de_estilo()


def test_botao_padrao_e_o_azul_do_interface_antiga():
    # 2026-10-20: o botão sem variante é o SECUNDÁRIO do sistema visual (contorno
    # `borda`, texto `texto`); o azul do tema da CTk (que saiu em 2026-10-15) não
    # entra mais na folha.
    assert "QPushButton {" in _qss()
    # As constantes da CTk continuam até os widgets pintados à mão migrarem (Task 5).
    assert estilo.AZUL_CTK == "#1F538D" and estilo.AZUL_CTK_HOVER == "#14375E"
    trecho = _qss().split("QPushButton {", 1)[1].split("}", 1)[0]
    assert tokens.ESCURO["borda"] in trecho and tokens.ESCURO["texto"] in trecho
    assert estilo.AZUL_CTK not in trecho


def test_variante_primario_usa_a_cor_da_marca():
    # 2026-10-20: o primário é o token `primaria` (verde), com o texto escuro; a
    # `marca` fica para a barra lateral e o item escolhido do menu.
    assert f'QPushButton[variante="primario"] {{ background: {tokens.ESCURO["primaria"]}' in _qss()


def test_campos_abas_listas_e_cartao():
    qss = _qss()
    # 2026-10-20: as cores do CTkEntry (#343638, #565B5E) e da lista (#1E1E1E) viraram tokens.
    p = tokens.ESCURO
    for trecho in ("QLineEdit", p["superficie_alta"], p["borda"], "QListWidget", p["superficie"],
                   "#cartao", theme.COR_CARTAO, "QComboBox"):
        assert trecho in qss, trecho


def test_caixa_marcada_e_fundo_de_dialogo_como_no_ctk():
    qss = _qss()
    # 2026-10-20: marcada em `primaria`; o diálogo no `fundo` (era o azul e o gray10 da CTk).
    assert f"QCheckBox::indicator:checked {{ background: {tokens.ESCURO['primaria']}" in qss
    assert f"QDialog {{ background: {tokens.ESCURO['fundo']}" in qss


def test_home_e_dialogos_usam_primario_onde_o_ctk_pintava_primary():
    # E5.1: a barra pinta a cor da interface antiga no próprio botão (fg_color, com o hover
    # do tema, que nenhuma variante tem); modelos e gastos continuam primary.
    from sigft.app_qt.views import home
    cores = {chave: cor for chave, _t, cor, _metodo in home.BARRA}
    assert cores["modelos"] == theme.COLORS["primary"] and cores["gastos"] == theme.COLORS["primary"]


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
    # CTkButton sem text_color pintava #DCE4EE (dark-blue.json). Desde 2026-10-20
    # o texto do botão comum e da barra da Home é o token `texto`.
    from PySide6.QtWidgets import QPushButton

    comum, barra = QPushButton("Selecionar"), QPushButton("Chaves de API")
    barra.setProperty("barra", True)
    recipiente = _sob_a_folha(qtbot, comum, barra)  # noqa: F841 -- segura os filhos vivos
    # A constante da CTk continua até os widgets pintados à mão migrarem (Task 5).
    assert estilo.TEXTO_BOTAO_CTK == "#DCE4EE"
    assert _cor_do_texto(comum) == tokens.ESCURO["texto"]
    assert _cor_do_texto(barra) == tokens.ESCURO["texto"]


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
    # própria no campo: é a regra global que dá isso. 2026-10-20: 32 px (o campo
    # do sistema visual), dica `texto_suave` e texto `texto`.
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QLineEdit

    campo = QLineEdit()
    campo.setPlaceholderText("Ex: 4500063671.1234")
    recipiente = _sob_a_folha(qtbot, campo)  # noqa: F841 -- segura os filhos vivos
    assert campo.height() == estilo.ALTURA_CAMPO_CTK == 32
    assert campo.sizeHint().height() == 32
    assert campo.font().pixelSize() == 13
    paleta = campo.palette()
    assert paleta.color(QPalette.ColorRole.PlaceholderText).name().upper() == tokens.ESCURO["texto_suave"]
    assert paleta.color(QPalette.ColorRole.Text).name().upper() == tokens.ESCURO["texto"]


def test_botao_desligado_muda_a_cor_do_texto_em_toda_variante(qt_interface, qtbot):
    # Revisão da Task 3 (2026-10-20): a regra da variante que diz `color:` vinha
    # depois de `QPushButton:disabled`, com a mesma especificidade, e o botão
    # "cinza"/"fantasma" desligado saía igual ao ligado. Pintado de verdade.
    from PySide6.QtWidgets import QPushButton

    def texto_pintado(botao):
        imagem = botao.grab().toImage()
        fundo = imagem.pixelColor(2, botao.height() // 2).name()
        cores = {imagem.pixelColor(x, y).name()
                 for x in range(imagem.width()) for y in range(imagem.height())}
        return cores - {fundo}

    for variante in (None, "secundario", "cinza", "neutro", "contorno", "contorno_padrao",
                     "fantasma", "primario", "acento", "perigo"):
        ligado, desligado = QPushButton("Executar WWW"), QPushButton("Executar WWW")
        if variante:
            ligado.setProperty("variante", variante)
            desligado.setProperty("variante", variante)
        desligado.setEnabled(False)
        recipiente = _sob_a_folha(qtbot, ligado, desligado)  # noqa: F841 -- segura vivos
        assert _cor_do_texto(desligado) == tokens.ESCURO["texto_suave"], variante
        assert _cor_do_texto(ligado) != _cor_do_texto(desligado), variante
        assert texto_pintado(ligado) != texto_pintado(desligado), variante
