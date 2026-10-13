"""A aparência do SIG-FT em Qt: a paleta de `theme.py` virando folha de estilo.

As CORES continuam morando em `sigft/app/theme.py` -- este módulo só as lê.
Duas paletas seria o jeito de as duas interfaces divergirem sem ninguém ver.
"""
from __future__ import annotations

import os
import re

from sigft.app import theme

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASTA_FONTES = os.path.join(_RAIZ, "assets", "fonts")

ARQUIVOS_DE_FONTE = ("Roboto-Regular.ttf", "Roboto-Medium.ttf", "NotoEmoji-Regular.ttf")

# Medidas que o CustomTkinter aplica hoje (decisão: espaçamento igual ao atual).
ALTURA_BOTAO_MENU = 35
ESPACO_MENU = 4
ALTURA_BOTAO_BARRA = 40

_SELETOR_TEXTO = "︎"


# Nível (0-255) de "grayNN" no Tk, índice = NN. Vem da tabela X11 (rgb.txt), que NÃO
# é uma fórmula de arredondamento (gray30 -> 77, mas gray50 -> 127): por isso a tabela
# literal. Gerada uma vez; não ler rgb.txt em tempo de execução (não existe no Windows).
_NIVEIS_CINZA_X11 = (
    0, 3, 5, 8, 10, 13, 15, 18, 20, 23,
    26, 28, 31, 33, 36, 38, 41, 43, 46, 48,
    51, 54, 56, 59, 61, 64, 66, 69, 71, 74,
    77, 79, 82, 84, 87, 89, 92, 94, 97, 99,
    102, 105, 107, 110, 112, 115, 117, 120, 122, 125,
    127, 130, 133, 135, 138, 140, 143, 145, 148, 150,
    153, 156, 158, 161, 163, 166, 168, 171, 173, 176,
    179, 181, 184, 186, 189, 191, 194, 196, 199, 201,
    204, 207, 209, 212, 214, 217, 219, 222, 224, 227,
    229, 232, 235, 237, 240, 242, 245, 247, 250, 252,
    255,
)


def cinza_tk(nome: str) -> str:
    """`"grayNN"` do Tk em hexadecimal. O Qt não conhece esses nomes e pinta preto."""
    if nome in ("gray", "grey"):
        return "#BEBEBE"
    achado = re.fullmatch(r"gr[ae]y(\d{1,3})", nome)
    if not achado or int(achado.group(1)) > 100:
        return nome
    valor = _NIVEIS_CINZA_X11[int(achado.group(1))]
    return f"#{valor:02X}{valor:02X}{valor:02X}"


def mono(texto: str) -> str:
    """Pede a versão PRETO E BRANCO de cada emoji (seletor U+FE0E).

    Só a fonte Noto Emoji não basta: sem o seletor, o Qt escolhe a fonte de
    emoji colorida do sistema (testado no protótipo de 2026-10-07).
    """
    saida = []
    for caractere in texto:
        saida.append(caractere)
        if ord(caractere) >= 0x1F000 or 0x2600 <= ord(caractere) <= 0x27BF:
            saida.append(_SELETOR_TEXTO)
    return "".join(saida)


def carregar_fontes() -> list[str]:
    """Registra Roboto e Noto Emoji no Qt. Chamar depois do QApplication.

    Devolve as famílias registradas. Fonte que falta não derruba o app: ele
    abre com a fonte padrão, que é feio, mas não é motivo para não abrir.
    """
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    familias: list[str] = []
    for nome in ARQUIVOS_DE_FONTE:
        indice = QFontDatabase.addApplicationFont(os.path.join(PASTA_FONTES, nome))
        if indice >= 0:
            familias.extend(QFontDatabase.applicationFontFamilies(indice))
    if "Noto Emoji" in familias:
        QFontDatabase.setApplicationEmojiFontFamilies(["Noto Emoji"])
    fonte = QFont()
    fonte.setFamilies(["Roboto", "Noto Emoji"])
    QApplication.setFont(fonte)
    return familias


def folha_de_estilo() -> str:
    """A folha QSS do app inteiro, montada a partir de `theme.py`."""
    c = theme.COLORS
    fam = '"Roboto", "Noto Emoji"'
    return f"""
QMainWindow, QDialog, #conteudo, #tela {{ background: {c['background']}; }}
QWidget {{ font-family: {fam}; color: {c['text_light']}; }}
#sidebar, #sidebar_interno {{ background: {c['sidebar']}; border: none; }}
#secao {{ color: {cinza_tk('gray50')}; font-size: 11px; font-weight: bold; padding-left: 10px; }}
#app_nome {{ color: {cinza_tk('gray60')}; font-size: 13px; }}
QPushButton {{ border-radius: 6px; color: {c['text_light']}; background: {c['primary']};
               border: none; padding: 0 14px; min-height: 28px; font-size: 13px; }}
QPushButton:hover {{ background: {c['primary_hover']}; }}
QPushButton:disabled {{ color: {cinza_tk('gray45')}; }}
QPushButton[menu="true"] {{ background: transparent; text-align: left; padding: 0 10px;
    min-height: {ALTURA_BOTAO_MENU}px; max-height: {ALTURA_BOTAO_MENU}px; font-size: 12px; }}
QPushButton[menu="true"]:hover {{ background: {c['primary']}; }}
#home {{ background: transparent; text-align: left; font-weight: bold;
         border: 1px solid {cinza_tk('gray30')}; }}
#home:hover {{ background: {c['primary']}; }}
QPushButton[barra="true"] {{ min-height: {ALTURA_BOTAO_BARRA}px; padding: 0 16px;
    font-weight: bold; color: {c['text_white']}; }}
QPushButton[variante="acento"] {{ background: {c['accent']}; }}
QPushButton[variante="acento"]:hover {{ background: {c['accent_hover']}; }}
QPushButton[variante="neutro"] {{ background: #3A3A3A; }}
QPushButton[variante="neutro"]:hover {{ background: #4A4A4A; }}
QPushButton[variante="perigo"] {{ background: {c['danger']}; }}
QPushButton[variante="contorno"] {{ background: transparent; border: 1px solid #555555;
    color: {cinza_tk('gray')}; }}
#titulo_home {{ font-size: 32px; font-weight: bold; }}
#subtitulo_home {{ font-size: 16px; color: {cinza_tk('gray70')}; }}
#texto_simples {{ font-size: 14px; }}
#titulo_modulo {{ font-size: 24px; font-weight: bold; color: {c['text_white']}; }}
#card {{ background: {theme.COR_CARTAO}; border: 1px solid #333333; border-radius: 8px; }}
#card:hover {{ border: 1px solid {c['accent']}; }}
#card_titulo {{ color: {c['accent']}; font-size: 15px; font-weight: bold; background: transparent; }}
#card_desc {{ color: {cinza_tk('gray70')}; font-size: 12px; background: transparent; }}
#console {{ background: #1D1E1E; border: 1px solid #333333; border-radius: 6px;
            font-family: "Consolas", "Menlo", monospace; font-size: 12px; }}
QCheckBox {{ font-size: 12px; }}
QCheckBox::indicator {{ width: 20px; height: 20px; border: 2px solid {cinza_tk('gray45')};
                        border-radius: 6px; background: transparent; }}
QCheckBox::indicator:checked {{ background: {c['primary']}; border-color: {c['primary']}; }}
QProgressBar {{ background: #333333; border: none; border-radius: 5px; max-height: 12px; }}
QProgressBar::chunk {{ background: {c['primary']}; border-radius: 5px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: #4A4D50; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""
