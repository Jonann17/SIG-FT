import os

from sigft.app import theme
from sigft.app_qt import estilo


def test_cinza_tk_converte_como_o_tk():
    assert estilo.cinza_tk("gray70") == "#B3B3B3"
    assert estilo.cinza_tk("gray30") == "#4D4D4D"
    assert estilo.cinza_tk("gray") == "#BEBEBE"
    assert estilo.cinza_tk("#123456") == "#123456"


def test_mono_pede_versao_texto_de_cada_emoji():
    assert estilo.mono("\U0001F4CB  Atividades") == "\U0001F4CB︎  Atividades"
    assert estilo.mono("Upload Condições – ok") == "Upload Condições – ok"


def test_fontes_existem_com_licenca():
    for nome in ("Roboto-Regular.ttf", "Roboto-Medium.ttf", "NotoEmoji-Regular.ttf",
                 "LICENSE-Roboto.txt", "OFL-NotoEmoji.txt"):
        assert os.path.isfile(os.path.join(estilo.PASTA_FONTES, nome)), nome


def test_carregar_fontes_registra_as_familias(qapp):
    familias = estilo.carregar_fontes()
    assert "Roboto" in familias and "Noto Emoji" in familias


def test_folha_usa_a_paleta_do_theme():
    qss = estilo.folha_de_estilo()
    for cor in (theme.COLORS["background"], theme.COLORS["sidebar"],
                theme.COLORS["accent"], theme.COR_CARTAO):
        assert cor in qss
    assert "gray" not in qss.replace("Roboto", "")  # nenhum cinza nomeado do Tk vazou
