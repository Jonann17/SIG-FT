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

# SEM o Roboto-Medium, de propósito: o negrito tem de ser SINTETIZADO a partir do
# Regular, como no Tk. O CustomTkinter registra Regular e Medium (no Windows, com
# AddFontResourceEx), mas o GDI lê o nome de família "antigo" de cada arquivo, e o
# do Medium é "Roboto Medium": uma família à parte. Para o Tk, "Roboto" negrito só
# tem o Regular, e o GDI o engrossa (e alarga cada letra). O Qt lê o nome
# tipográfico ("Roboto", estilo Medium): com o Medium registrado, o negrito virava
# Medium + engrossamento -- outra letra, que não é a do app antigo. Nada no app
# pede peso 500; o arquivo continua em assets/fonts, só não é registrado.
ARQUIVOS_DE_FONTE = ("Roboto-Regular.ttf", "NotoEmoji-Regular.ttf")

# Largura total da barra lateral do CustomTkinter: CTkScrollableFrame(width=260)
# mais a barra de rolagem dele, sempre visível (16 px), e 1 px de borda. Medido na
# captura: o fundo do conteúdo começa em x=277. Os módulos começam no mesmo x.
LARGURA_BARRA_LATERAL = 277

# Medidas que o CustomTkinter aplica hoje (decisão: espaçamento igual ao atual).
ALTURA_BOTAO_MENU = 35
ESPACO_MENU = 4
ALTURA_BOTAO_BARRA = 40
# CTkButton: `width` padrão 140, e o texto que não cabe alarga o botão com 7 px de
# folga de cada lado (coluna de 6 = corner_radius, mais 1 do padx do Label do Tk).
# Com a folga de 16 que a barra da Home tinha, os botões saíam de 143 a 171 px
# (lá: 140 a 148) e, com o negrito na largura do Tk, a linha passava da tela.
LARGURA_BOTAO_CTK = 140
FOLGA_TEXTO_BOTAO_CTK = 7

# Tema "dark-blue" do CustomTkinter (customtkinter/assets/themes/dark-blue.json),
# o que `sigft/app/main.py` usa: é o que pinta tudo o que as telas antigas não
# coloriam à mão.
AZUL_CTK = "#1F538D"
AZUL_CTK_HOVER = "#14375E"
# CTkButton do mesmo tema: borda (índice 1 = escuro) de um botão com
# `border_width` e sem `border_color`, e texto de um botão desabilitado (gray60).
BORDA_CTK = "#949A9F"
TEXTO_DESABILITADO_CTK = "gray60"
# Texto de um CTkButton (e das abas e do CTkOptionMenu) que não diz `text_color`:
# o do tema, que NÃO é o text_light (#E0E0E0) de theme.py. Botão que lá passava
# text_color=COLORS["text_light"] (menu e Home da barra lateral, glossário) diz
# isso aqui também, com a cor explícita.
TEXTO_BOTAO_CTK = "#DCE4EE"
# CTkEntry do mesmo tema: altura 28 (borda incluída), borda 2 #565B5E, fundo
# #343638, texto gray84, dica (placeholder) gray62, fonte 13. Lá o Entry do Tk vai
# na grade com padx=6 e pady=(2, 3): a caixa do texto tem 23 px, 1 px mais perto
# do topo. Aqui: borda 2 + padding (0, 3, 1, 3) + 23 de conteúdo = 28, e o texto
# começa no mesmo x (medido: 8 px da borda de fora, nas duas capturas).
ALTURA_CAMPO_CTK = 28
BORDA_CAMPO_CTK = 2

# Espessura da borda (px) de cada variante de botão que tem borda. `blocos.botao`
# desconta isto da altura: no Qt o `min-height` da folha NÃO inclui a borda, e no
# CustomTkinter `height` é a altura total do botão, borda incluída.
BORDA_DA_VARIANTE = {"contorno": 1, "contorno_padrao": 1}

_SELETOR_TEXTO = "\ufe0e"   # U+FE0E: pede a forma de texto (preto e branco)
_SELETOR_EMOJI = "\ufe0f"   # U+FE0F: pede a forma de emoji (colorida)


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
    """`"grayNN"` do Tk em hexadecimal. O Qt não conhece esses nomes e pinta preto.

    `"gray"` sem número é #808080, e NÃO o #BEBEBE do rgb.txt do X11: o Tk 8.6
    adotou o valor do W3C/CSS para gray/grey (os "grayNN" seguem o X11).
    """
    if nome in ("gray", "grey"):
        return "#808080"
    achado = re.fullmatch(r"gr[ae]y(\d{1,3})", nome)
    if not achado or int(achado.group(1)) > 100:
        return nome
    valor = _NIVEIS_CINZA_X11[int(achado.group(1))]
    return f"#{valor:02X}{valor:02X}{valor:02X}"


def _parece_emoji(codigo: int) -> bool:
    """Plano dos emoji (U+1F000+), setas/técnicos/formas/dingbats (U+2190-U+2BFF) e o ℹ."""
    return codigo >= 0x1F000 or 0x2190 <= codigo <= 0x2BFF or codigo == 0x2139


def mono(texto: str) -> str:
    """Pede a versão PRETO E BRANCO de cada emoji (seletor U+FE0E).

    Só a fonte Noto Emoji não basta: sem o seletor, o Qt escolhe a fonte de
    emoji colorida do sistema (testado no protótipo de 2026-10-07).

    Cobre também os símbolos que viram emoji colorido sem ser do plano dos
    emoji (⬇ ⏭ ▶ ℹ e o resto de U+2190-U+2BFF). Se o texto já traz um seletor
    depois do símbolo, não se duplica: o de texto fica, e o de emoji (U+FE0F)
    é TROCADO pelo de texto. Aplicar duas vezes dá o mesmo resultado.
    """
    saida: list[str] = []
    i = 0
    while i < len(texto):
        caractere = texto[i]
        saida.append(caractere)
        i += 1
        if not _parece_emoji(ord(caractere)):
            continue
        saida.append(_SELETOR_TEXTO)
        if i < len(texto) and texto[i] in (_SELETOR_TEXTO, _SELETOR_EMOJI):
            i += 1  # o seletor que já estava foi absorvido pelo de texto
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
    # Hinting completo = largura de cada letra arredondada ao pixel, como o Tk
    # desenha (GDI no Windows, Xft no Linux). No Linux o padrão do Qt usa a largura
    # "de projeto", que ignora o engrossamento do negrito sintetizado: o negrito
    # saía ~10% mais estreito que o do app antigo (medido: 221 x 237 px no
    # "ATENÇÃO: AÇÃO DESTRUTIVA"). No Windows a 100% de escala este já é o padrão
    # do Qt (métricas compatíveis com o GDI); escrito, vale também com escala.
    fonte.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    QApplication.setFont(fonte)
    return familias


def folha_de_estilo() -> str:
    """A folha QSS do app inteiro, montada a partir de `theme.py`."""
    c = theme.COLORS
    fam = '"Roboto", "Noto Emoji"'
    # Notas que não cabem dentro da folha (comentário nela vazaria "gray" no QSS):
    # * variante "contorno": o "Ignorar e Continuar" de sigft/app/widgets/dialogs.py
    #   (borda #555 e texto COR_TEXTO_APOIO, escritos à mão); "contorno_padrao": botão
    #   transparente com border_width=1, sem border_color (a do tema) e com
    #   text_color=text_light escrito à mão -- o glossário do Tradutor;
    # * texto dos botões: TEXTO_BOTAO_CTK (o do tema) na regra geral; text_light só
    #   onde o CTk o escrevia (menu, Home, contorno_padrao). A barra da Home não o
    #   escreve: lá é #DCE4EE (medido na captura), e não branco; e a largura dos
    #   botões dela é a do CTkButton (LARGURA_BOTAO_CTK);
    # * QLineEdit: o CTkEntry do tema (ver ALTURA_CAMPO_CTK). min/max-height não
    #   contam borda nem padding: 28 - 2*2 - 1;
    # * #console: CTkTextbox do tema dark-blue -- fg gray20, border_width 0, texto gray84.
    return f"""
QMainWindow, #conteudo, #tela {{ background: {c['background']}; }}
QDialog {{ background: {cinza_tk('gray10')}; }}
QWidget {{ font-family: {fam}; color: {c['text_light']}; }}
#sidebar, #sidebar_interno {{ background: {c['sidebar']}; border: none; }}
#secao {{ color: {cinza_tk('gray50')}; font-size: 11px; font-weight: bold; padding-left: 10px; }}
#app_nome {{ color: {cinza_tk('gray60')}; font-size: 13px; }}
QPushButton {{ border-radius: 6px; color: {TEXTO_BOTAO_CTK}; background: {AZUL_CTK};
               border: none; padding: 0 14px; min-height: 28px; font-size: 13px; }}
QPushButton:hover {{ background: {AZUL_CTK_HOVER}; }}
QPushButton[variante="primario"] {{ background: {c['primary']}; }}
QPushButton[variante="primario"]:hover {{ background: {c['primary_hover']}; }}
QPushButton:disabled {{ color: {cinza_tk(TEXTO_DESABILITADO_CTK)}; }}
QPushButton[menu="true"] {{ background: transparent; text-align: left; padding: 0 10px;
    color: {c['text_light']}; min-height: {ALTURA_BOTAO_MENU}px; max-height: {ALTURA_BOTAO_MENU}px; font-size: 12px; }}
QPushButton[menu="true"]:hover {{ background: {c['primary']}; }}
QPushButton[menu="true"]:disabled {{ color: {cinza_tk('gray45')}; }}
#home {{ background: transparent; text-align: left; font-weight: bold;
         color: {c['text_light']}; border: 1px solid {cinza_tk('gray30')}; }}
#home:hover {{ background: {c['primary']}; }}
QPushButton[barra="true"] {{ min-height: {ALTURA_BOTAO_BARRA}px;
    min-width: {LARGURA_BOTAO_CTK - 2 * FOLGA_TEXTO_BOTAO_CTK}px; padding: 0 {FOLGA_TEXTO_BOTAO_CTK}px;
    font-weight: bold; }}
QPushButton[variante="acento"] {{ background: {c['accent']}; }}
QPushButton[variante="acento"]:hover {{ background: {c['accent_hover']}; }}
QPushButton[variante="neutro"] {{ background: #3A3A3A; }}
QPushButton[variante="neutro"]:hover {{ background: #4A4A4A; }}
QPushButton[variante="perigo"] {{ background: {c['danger']}; }}
QPushButton[variante="perigo"]:hover {{ background: #B71C1C; }}  /* o hover_color das telas CTk */
QPushButton[variante="contorno"] {{ background: transparent;
    border: {BORDA_DA_VARIANTE['contorno']}px solid #555555; color: {cinza_tk('gray')}; }}
QPushButton[variante="contorno_padrao"] {{ background: transparent;
    border: {BORDA_DA_VARIANTE['contorno_padrao']}px solid {BORDA_CTK}; color: {c['text_light']}; }}
QPushButton[variante="contorno"]:hover, QPushButton[variante="contorno_padrao"]:hover {{
    background: {AZUL_CTK_HOVER}; }}
#titulo_home {{ font-size: 32px; font-weight: bold; }}
#subtitulo_home {{ font-size: 16px; color: {cinza_tk('gray70')}; }}
#texto_simples {{ font-size: 14px; }}
#titulo_modulo {{ font-size: 24px; font-weight: bold; color: {c['text_white']}; }}
#card {{ background: {theme.COR_CARTAO}; border: 1px solid #333333; border-radius: 8px; }}
#card:hover {{ border: 1px solid {c['accent']}; }}
#card_titulo {{ color: {c['accent']}; font-size: 15px; font-weight: bold; background: transparent; }}
#card_desc {{ color: {cinza_tk('gray70')}; font-size: 12px; background: transparent; }}
#console {{ background: {cinza_tk('gray20')}; border: none; border-radius: 6px;
            color: {cinza_tk('gray84')}; font-family: "Consolas", "Menlo", monospace; font-size: 12px; }}
QCheckBox {{ font-size: 12px; }}
QCheckBox::indicator {{ width: 20px; height: 20px; border: 3px solid #949A9F;
                        border-radius: 6px; background: transparent; }}
QCheckBox::indicator:checked {{ background: {AZUL_CTK}; border-color: {AZUL_CTK}; }}
QProgressBar {{ background: #333333; border: none; border-radius: 5px; max-height: 12px; }}
QProgressBar::chunk {{ background: {c['primary']}; border-radius: 5px; }}
QLineEdit {{ background: #343638; border: {BORDA_CAMPO_CTK}px solid #565B5E; border-radius: 6px;
             color: {cinza_tk('gray84')}; placeholder-text-color: {cinza_tk('gray62')};
             font-size: 13px; padding: 0 3px 1px 3px;
             min-height: {ALTURA_CAMPO_CTK - 2 * BORDA_CAMPO_CTK - 1}px;
             max-height: {ALTURA_CAMPO_CTK - 2 * BORDA_CAMPO_CTK - 1}px; }}
QLineEdit:disabled {{ color: {cinza_tk('gray45')}; }}
QComboBox {{ background: {AZUL_CTK}; border-radius: 6px; padding: 4px 10px;
             color: {TEXTO_BOTAO_CTK}; min-height: 22px; }}
QTabWidget::pane {{ border: none; background: {cinza_tk('gray16')}; border-radius: 6px; }}
QTabBar::tab {{ background: {cinza_tk('gray29')}; color: {TEXTO_BOTAO_CTK}; padding: 6px 14px;
                margin: 0 1px; border-radius: 6px; }}
QTabBar::tab:selected {{ background: {AZUL_CTK}; }}
QTabBar::tab:hover:!selected {{ background: {cinza_tk('gray41')}; }}
QListWidget {{ background: #1E1E1E; color: {c['text_light']}; border: none; }}
QListWidget::item:selected {{ background: {c['primary']}; color: white; }}
#cartao {{ background: {theme.COR_CARTAO}; border-radius: 8px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: #4A4D50; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""
