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


def cinza_tk(nome: str) -> str:
    """`"grayNN"` do Tk em hexadecimal. O Qt não conhece esses nomes e pinta preto."""
    if nome in ("gray", "grey"):
        return "#BEBEBE"
    achado = re.fullmatch(r"gr[ae]y(\d{1,3})", nome)
    if not achado:
        return nome
    # Meio para cima, como o Tk (o round() do Python arredonda meio para o par).
    valor = (255 * int(achado.group(1)) + 50) // 100
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
