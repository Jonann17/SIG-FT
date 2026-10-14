import os
import re

import pytest

from sigft.app import theme
from sigft.app_qt import estilo


def test_cinza_tk_converte_como_o_tk():
    assert estilo.cinza_tk("gray70") == "#B3B3B3"
    assert estilo.cinza_tk("gray30") == "#4D4D4D"
    # "gray" sem número: o Tk 8.6 usa o valor do W3C (#808080), não o #BEBEBE do X11.
    assert estilo.cinza_tk("gray") == "#808080"
    assert estilo.cinza_tk("#123456") == "#123456"
    assert estilo.cinza_tk("gray50") == "#7F7F7F"
    assert estilo.cinza_tk("gray90") == "#E5E5E5"
    assert estilo.cinza_tk("gray101") == "gray101"


def test_cinza_tk_bate_com_a_tabela_x11_inteira():
    caminho = "/usr/share/X11/rgb.txt"
    if not os.path.isfile(caminho):
        pytest.skip("rgb.txt do X11 não existe nesta máquina")
    achados = {}
    with open(caminho, encoding="utf-8", errors="replace") as arq:
        for linha in arq:
            m = re.fullmatch(r"\s*(\d+)\s+(\d+)\s+(\d+)\s+gr[ae]y(\d+)\s*", linha)
            if m:
                achados[int(m.group(4))] = int(m.group(1))
    assert sorted(achados) == list(range(101))
    for n, nivel in achados.items():
        assert estilo.cinza_tk(f"gray{n}") == f"#{nivel:02X}{nivel:02X}{nivel:02X}", n


def test_mono_pede_versao_texto_de_cada_emoji():
    assert estilo.mono("\U0001F4CB  Atividades") == "\U0001F4CB\ufe0e  Atividades"
    assert estilo.mono("Upload Condições – ok") == "Upload Condições – ok"


@pytest.mark.parametrize("simbolo", [
    "\u2b07",      # seta para baixo
    "\u23ed",      # proxima faixa
    "\u25b6",      # triangulo de play
    "\u2139",      # i de informacao
    "\u2190",      # inicio do bloco de setas
    "\u2bff",      # fim da faixa U+2190-U+2BFF
    "\u2600",      # simbolos diversos
    "\u27bf",      # dingbats
    "\U0001F4CB",  # emoji do plano 1F000
])
def test_mono_cobre_os_simbolos_usados_como_emoji(simbolo):
    assert estilo.mono(f"{simbolo} x") == f"{simbolo}\ufe0e x"


def test_mono_nao_mexe_em_texto_comum():
    assert estilo.mono("A \u2013 b \u00e7 \u2018") == "A \u2013 b \u00e7 \u2018"


def test_mono_nao_duplica_o_seletor_de_texto():
    assert estilo.mono("\u25b6\ufe0e x") == "\u25b6\ufe0e x"


def test_mono_troca_o_seletor_de_emoji_pelo_de_texto():
    assert estilo.mono("\u2b07\ufe0f x") == "\u2b07\ufe0e x"
    assert estilo.mono("\U0001F4CB\ufe0f x") == "\U0001F4CB\ufe0e x"


def test_mono_e_idempotente():
    uma_vez = estilo.mono("\u2139\ufe0f \u23ed \U0001F3E0 oi")
    assert estilo.mono(uma_vez) == uma_vez


def test_fontes_existem_com_licenca():
    for nome in ("Roboto-Regular.ttf", "Roboto-Medium.ttf", "NotoEmoji-Regular.ttf",
                 "LICENSE-Roboto.txt", "OFL-NotoEmoji.txt"):
        assert os.path.isfile(os.path.join(estilo.PASTA_FONTES, nome)), nome


def test_carregar_fontes_registra_as_familias(qapp):
    familias = estilo.carregar_fontes()
    assert "Roboto" in familias and "Noto Emoji" in familias


def test_negrito_e_sintetizado_do_regular_como_no_tk():
    # O Tk (GDI no Windows) não acha um "Roboto" negrito e engrossa o Regular:
    # o Medium registrado fazia o Qt usar OUTRA letra no negrito (ver estilo.py).
    assert "Roboto-Regular.ttf" in estilo.ARQUIVOS_DE_FONTE
    assert not any("Medium" in nome or "Bold" in nome for nome in estilo.ARQUIVOS_DE_FONTE)


def test_fonte_do_app_usa_hinting_completo_como_o_tk(qapp):
    # Larguras arredondadas ao pixel, com o engrossamento do negrito sintetizado
    # contando -- sem isto o negrito saía ~10% mais estreito que o do Tk no Linux.
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    estilo.carregar_fontes()
    assert QApplication.font().hintingPreference() == QFont.HintingPreference.PreferFullHinting


def test_folha_usa_a_paleta_do_theme():
    qss = estilo.folha_de_estilo()
    for cor in (theme.COLORS["background"], theme.COLORS["sidebar"],
                theme.COLORS["accent"], theme.COR_CARTAO):
        assert cor in qss
    assert "gray" not in qss.replace("Roboto", "")  # nenhum cinza nomeado do Tk vazou
