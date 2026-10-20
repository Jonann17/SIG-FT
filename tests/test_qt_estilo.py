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


# --- Sistema visual (2026-10-20): a folha sai dos tokens, por tema ----------------

from sigft.app import tokens  # noqa: E402


def _regra(folha, seletor):
    achado = re.search(re.escape(seletor) + r"\s*\{([^}]*)\}", folha)
    assert achado, seletor
    return achado.group(1)


@pytest.mark.parametrize("tema", ["escuro", "claro"])
def test_folha_usa_a_paleta_do_tema(tema):
    p = tokens.paleta(tema)
    folha = estilo.folha_de_estilo(tema)
    assert p["fundo"] in _regra(folha, "QMainWindow, #conteudo, #tela")
    assert p["primaria"] in _regra(folha, 'QPushButton[variante="primario"]')
    assert p["texto_sobre_primaria"] in _regra(folha, 'QPushButton[variante="primario"]')
    assert p["perigo_fundo"] in _regra(folha, 'QPushButton[variante="perigo"]')
    assert p["console_fundo"] in _regra(folha, "#console")


def test_variantes_antigas_viram_as_novas():
    folha = estilo.folha_de_estilo("escuro")
    for antiga in ("acento", "cinza", "neutro", "contorno", "contorno_padrao"):
        assert f'[variante="{antiga}"]' in folha


def test_folhas_dos_dois_temas_sao_diferentes():
    assert estilo.folha_de_estilo("escuro") != estilo.folha_de_estilo("claro")


def test_sem_argumento_e_o_tema_escuro():
    # A abertura (`main._preparar_qt`) chama sem tema até a escolha existir (Task 7).
    assert estilo.folha_de_estilo() == estilo.folha_de_estilo("escuro")


@pytest.mark.parametrize("tema", ["escuro", "claro"])
def test_botao_padrao_e_o_secundario_com_32_de_altura(tema):
    p = tokens.paleta(tema)
    regra = _regra(estilo.folha_de_estilo(tema), "QPushButton")
    assert f"solid {p['borda']}" in regra and f"color: {p['texto']}" in regra
    assert "border-radius: 6px" in regra and "padding: 0 14px" in regra
    # min-height não conta a borda de 1 px: 30 + 2 = os 32 da spec.
    assert f"min-height: {estilo.ALTURA_BOTAO - 2}px" in regra and estilo.ALTURA_BOTAO == 32


@pytest.mark.parametrize("tema,fundo,texto", [
    ("escuro", "#0F3A3F", tokens.ESCURO["texto"]),
    ("claro", "#E3F1F2", "#035D67"),
])
def test_item_escolhido_do_menu_e_a_marca_a_25_por_cento(tema, fundo, texto):
    regra = _regra(estilo.folha_de_estilo(tema), 'QPushButton[menu="true"][ativo="true"]')
    assert fundo in regra and texto in regra
    assert tokens.contraste(texto, fundo) >= 4.5


@pytest.mark.parametrize("tema", ["escuro", "claro"])
def test_campos_marcadores_e_progresso_nas_cores_do_tema(tema):
    p = tokens.paleta(tema)
    folha = estilo.folha_de_estilo(tema)
    campo = _regra(folha, "QLineEdit")
    assert p["superficie_alta"] in campo and p["borda"] in campo
    assert p["primaria"] in _regra(folha, "QLineEdit:focus")
    assert p["superficie_alta"] in _regra(folha, "QComboBox")
    assert p["primaria"] in _regra(folha, "QCheckBox::indicator:checked")
    assert p["primaria"] in _regra(folha, "QRadioButton::indicator:checked")
    assert p["primaria"] in _regra(folha, "QProgressBar::chunk")
    tabela = _regra(folha, "QTreeView")
    assert p["superficie"] in tabela and p["texto"] in tabela
    assert "#FFFFFF; color: #000000" not in folha  # o Treeview nativo do Tk saiu


@pytest.mark.parametrize("tema", ["escuro", "claro"])
def test_papeis_de_texto(tema):
    p = tokens.paleta(tema)
    folha = estilo.folha_de_estilo(tema)
    legenda = _regra(folha, 'QLabel[papel="legenda"]')
    assert p["texto_suave"] in legenda and "font-size: 12px" in legenda
    assert "font-size: 15px" in _regra(folha, 'QLabel[papel="secao"]')
    assert "font-size: 22px" in _regra(folha, 'QLabel[papel="titulo"]')
    aviso = _regra(folha, 'QLabel[papel="aviso"]')
    # Aviso só sobre a superfície: no claro ele não chega a 4,5:1 sobre o fundo.
    assert p["aviso"] in aviso and p["superficie"] in aviso
    assert tokens.contraste(p["aviso"], p["superficie"]) >= 4.5
    assert p["perigo"] in _regra(folha, 'QLabel[papel="erro"]')
    ok = _regra(folha, 'QLabel[papel="ok"]')
    assert p["primaria"] in ok and tokens.contraste(p["primaria"], p["fundo"]) >= 4.5


def test_quadro_das_abas_sai_dos_tokens():
    # O gray13 (#212121) da CTk brigava com o fundo novo (2026-10-20). Lá o quadro
    # era invisível (gray13 = o fundo antigo): continua, agora com os tokens.
    assert estilo.FUNDO_QUADRO_CTK == tokens.ESCURO["fundo"]
    assert estilo.FUNDO_QUADRO_INTERNO_CTK == tokens.ESCURO["superficie"]
