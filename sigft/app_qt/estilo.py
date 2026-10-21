"""A aparência do SIG-FT em Qt: os tokens de `sigft/app/tokens.py` virando folha de estilo.

As CORES moram em `tokens.py` (dois temas, mesmos papéis) -- este módulo só as lê.
`folha_de_estilo(tema)` monta a folha do app inteiro para "escuro" ou "claro"
(2026-10-20, sistema visual). As constantes `*_CTK` que sobraram são as que os
widgets pintados à mão (`widgets/controles.py`, `blocos.py`...) ainda leem; a
interface antiga saiu em 2026-10-15 e elas saem junto com a cor crua das telas.
"""
from __future__ import annotations

import os
import re
import sys

from sigft.app import tokens

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASTA_FONTES = os.path.join(_RAIZ, "assets", "fonts")
# Os SVG do Lucide (`sigft/app_qt/icones.py`, 2026-10-20), pela mesma raiz.
PASTA_ICONES = os.path.join(_RAIZ, "assets", "icons")

# SEM o Roboto-Medium, de propósito: o negrito tem de ser SINTETIZADO a partir do
# Regular, como no Tk. A interface antiga registra Regular e Medium (no Windows, com
# AddFontResourceEx), mas o GDI lê o nome de família "antigo" de cada arquivo, e o
# do Medium é "Roboto Medium": uma família à parte. Para o Tk, "Roboto" negrito só
# tem o Regular, e o GDI o engrossa (e alarga cada letra). O Qt lê o nome
# tipográfico ("Roboto", estilo Medium): com o Medium registrado, o negrito virava
# Medium + engrossamento -- outra letra, que não é a do app antigo. Nada no app
# pede peso 500; o arquivo continua em assets/fonts, só não é registrado.
ARQUIVOS_DE_FONTE = ("Roboto-Regular.ttf", "NotoEmoji-Regular.ttf")

# Largura total da barra lateral da interface antiga: CTkScrollableFrame(width=260)
# mais a barra de rolagem dele, sempre visível (16 px), e 1 px de borda. Medido na
# captura: o fundo do conteúdo começa em x=277. Os módulos começam no mesmo x.
LARGURA_BARRA_LATERAL = 277

# Medidas que a interface antiga aplica hoje (decisão: espaçamento igual ao atual).
ALTURA_BOTAO_MENU = 35
ESPACO_MENU = 4
ALTURA_BOTAO_BARRA = 40
# CTkButton: `width` padrão 140, e o texto que não cabe alarga o botão com 7 px de
# folga de cada lado (coluna de 6 = corner_radius, mais 1 do padx do Label do Tk).
# Com a folga de 16 que a barra da Home tinha, os botões saíam de 143 a 171 px
# (lá: 140 a 148) e, com o negrito na largura do Tk, a linha passava da tela.
LARGURA_BOTAO_CTK = 140
FOLGA_TEXTO_BOTAO_CTK = 7

# Sistema visual (2026-10-20): botão e campo com 32 px de altura TOTAL (borda de
# 1 px incluída), raio 6. No QSS o `min-height` NÃO conta a borda: 32 - 2.
ALTURA_BOTAO = 32
ALTURA_CAMPO = 32
BORDA_CONTROLE = 1
# O nome antigo continua importável (teste de medida, telas); o valor é o novo.
ALTURA_CAMPO_CTK = ALTURA_CAMPO

# Espessura da borda (px) de cada variante de botão. `blocos.botao` desconta isto
# da altura: no Qt o `min-height` da folha NÃO inclui a borda, e a altura pedida é
# a total. Desde 2026-10-20 TODA variante tem borda de 1 (no primário e no perigo
# ela tem a cor do fundo; no fantasma, transparente): os botões têm a mesma altura
# qualquer que seja a variante. "" é o botão sem variante (= secundário).
BORDA_DA_VARIANTE = {nome: BORDA_CONTROLE for nome in (
    "", "primario", "secundario", "perigo", "fantasma",
    "acento", "cinza", "neutro", "contorno", "contorno_padrao")}

# Item escolhido (e sob o mouse) do menu lateral: `marca` a 25% sobre a
# superfície da barra, valores da spec (2026-10-20). O texto: `texto` no escuro
# (10,3:1) e a própria marca no claro (6,6:1) -- `texto` claro sobre a marca
# pura dava 2,2:1.
MENU_ESCOLHIDO = {
    "escuro": {"fundo": "#0F3A3F", "texto": tokens.ESCURO["texto"]},
    "claro": {"fundo": "#E3F1F2", "texto": tokens.CLARO["marca"]},
}

# --- O tema de agora ------------------------------------------------------------
# 2026-10-20: o único lugar que diz qual tema está valendo. As peças desenhadas
# com QPainter (`widgets/controles.py`, o delegado das caixas) leem a paleta por
# `paleta_atual()` NA HORA DE PINTAR; o resto da cor está na folha. A troca de
# tema (`sigft/app_qt/tema.py`) muda só isto e reaplica a folha: as funções de
# folha abaixo, sem `tema=`, leem este valor NA CHAMADA.
TEMA_ATUAL = "escuro"
# O aumento da letra que está valendo, em px (`letra.aplicar` muda; 0 = normal).
AUMENTO_LETRA = 0
# Só px (fix round 1, 2026-10-21): o aumento é de 2 PIXELS. Um tamanho em pt
# (nenhuma folha do app usa) fica como está, em vez de crescer 2 pt.
_TAMANHO_DE_LETRA = re.compile(r"(font-size:\s*)(\d+)(px)")
# Onde `letra` guarda, numa peça com folha própria, a folha de ANTES do aumento e
# a que ela pôs (para refazer a partir da base, nunca somar duas vezes).
PROP_FOLHA_BASE = "_letra_folha_base"
PROP_FOLHA_POSTA = "_letra_folha_posta"


def ajustar_tamanhos(folha: str, aumento: int) -> str:
    """Soma `aumento` a cada `font-size` em px de `folha`. Com 0, a mesma folha."""
    if not aumento or not folha:
        return folha
    return _TAMANHO_DE_LETRA.sub(
        lambda m: f"{m.group(1)}{int(m.group(2)) + aumento}{m.group(3)}", folha)


def folha_sem_aumento(widget) -> str:
    """A folha própria de `widget` como a tela a escreveu, sem o aumento da letra."""
    folha = widget.styleSheet()
    if folha and widget.property(PROP_FOLHA_POSTA) == folha:
        return widget.property(PROP_FOLHA_BASE) or ""
    return folha


def _tema(tema: str | None) -> str:
    """O tema pedido ou, sem pedido, o que está valendo agora."""
    return TEMA_ATUAL if tema is None else tema


def paleta_atual() -> dict[str, str]:
    """A paleta (`tokens.paleta`) do tema que está valendo."""
    return tokens.paleta(TEMA_ATUAL)


# O papel de cor que não é chave da paleta: o texto do item escolhido do menu
# (`MENU_ESCOLHIDO`), que é `texto` no escuro e a `marca` no claro.
PAPEL_MENU_ESCOLHIDO = "menu_escolhido"


def cor_do_papel(papel: str) -> str | None:
    """A cor do `papel` no tema atual: uma chave da paleta ou
    `PAPEL_MENU_ESCOLHIDO`. Papel desconhecido: `None` (quem pede decide)."""
    if papel == PAPEL_MENU_ESCOLHIDO:
        return MENU_ESCOLHIDO["claro" if TEMA_ATUAL == "claro" else "escuro"]["texto"]
    return paleta_atual().get(papel)


# O texto do botão de perigo: branco nos dois temas (o `perigo_fundo` é o mesmo).
TEXTO_SOBRE_PERIGO = "#FFFFFF"


def cor_do_texto_da_variante(variante: str | None) -> str:
    """A cor do texto de um botão da variante `variante` no tema atual, a mesma
    da folha. É a cor do ÍCONE do botão (`icones.aplicar`, 2026-10-20): o ícone
    acompanha o texto ao lado dele."""
    p = paleta_atual()
    variante = SINONIMOS_DE_VARIANTE.get(variante or "", variante or "")
    if variante == "primario":
        return p["texto_sobre_primaria"]
    if variante == "perigo":
        return TEXTO_SOBRE_PERIGO
    return p["texto"]


def definir_propriedade(widget, nome: str, valor) -> None:
    """`setProperty` que a folha enxerga na hora: o Qt só reavalia os seletores
    `[nome="..."]` de um widget já polido quando ele é repolido."""
    widget.setProperty(nome, valor)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def definir_papel(rotulo, papel: str | None) -> None:
    """Troca o papel de texto (`QLabel[papel=...]`) de um rótulo já na tela;
    `None` volta à cor do texto comum."""
    definir_propriedade(rotulo, "papel", papel)


def definir_variante(botao, variante: str | None) -> None:
    """Troca a variante (`QPushButton[variante=...]`) de um botão já na tela."""
    definir_propriedade(botao, "variante", variante)


# --- Cores do mural de atividades (2026-10-20) -------------------------------------
# A cor de cada faixa é a do TEXTO do cabeçalho e do prazo, sobre o `fundo` e
# sobre a `superficie` -- por isso duas, uma por tema, cada uma com 4,5:1 nos
# dois fundos (teste em `test_qt_sem_cor_crua.py`). O roxo da "travada" é
# deliberadamente fora da escala vermelho->laranja->verde do prazo: travada não
# é "mais atrasada", é outra natureza de problema. O laranja e o verde-água do
# claro são mais escuros que os tokens `aviso`/`primaria_hover`, que não chegam
# a 4,5:1 sobre o fundo claro.
COR_DA_FAIXA = {
    "escuro": {"atrasada": tokens.ESCURO["perigo"], "travada": "#B07CE8",
               "deveria_ter_comecado": tokens.ESCURO["aviso"], "em_andamento": "#4DA3A9",
               "comeca_hoje": tokens.ESCURO["primaria"], "proximos_dias": tokens.ESCURO["texto_suave"]},
    "claro": {"atrasada": tokens.CLARO["perigo"], "travada": "#7B3FC4",
              "deveria_ter_comecado": "#9A5C00", "em_andamento": "#047A83",
              "comeca_hoje": tokens.CLARO["primaria"], "proximos_dias": tokens.CLARO["texto_suave"]},
}
# A barra lateral de cada cartão, da criticidade 1 (neutra) à 5 (vermelho): não é
# texto, a mesma escala nos dois temas; a 1 e a sem criticidade seguem o tema.
COR_DA_CRITICIDADE = {5: "#D32F2F", 4: "#FF6F3C", 3: "#FFA726", 2: "#4DA3A9"}

# --- Cores de fundo que as telas escreviam à mão (2026-10-20) ---------------------
# `blocos.variante_da_cor` troca cada uma pela variante de botão que a substitui;
# nenhuma tela passa mais `cor_fundo` (guarda em `tests/test_qt_botoes.py`), a
# tabela fica para o `cor_fundo` que ainda chegar de fora.
VERDE_TK = "#008000"
VERDE_ESCURO = "#2E7D32"
VERMELHO_PARAR = "#8B2E2E"
VERMELHO_CRITICO = "#D32F2F"
AZUL_MARCA_ANTIGO = "#035D67"
VARIANTE_DA_COR = {
    tokens.ESCURO["marca"]: "primario", AZUL_MARCA_ANTIGO: "primario",
    tokens.ESCURO["sucesso"]: "primario", VERDE_TK: "primario", VERDE_ESCURO: "primario",
    tokens.ESCURO["perigo_fundo"]: "perigo", VERMELHO_PARAR: "perigo", VERMELHO_CRITICO: "perigo",
    "TRANSPARENT": "fantasma",
}

# As cores do tema "dark-blue" da CTk que os widgets pintados à mão liam
# (AZUL_CTK, AZUL_CTK_HOVER, BORDA_CTK, TEXTO_BOTAO_CTK, TEXTO_DESABILITADO_CTK,
# TRILHO_CTK, FUNDO_QUADRO_CTK, FUNDO_QUADRO_INTERNO_CTK) saíram em 2026-10-20:
# toda peça lê a paleta (`paleta_atual()`) ou a folha. A varredura
# `tests/test_qt_sem_cor_crua.py` acusa o nome que voltar fora daqui.

# Altura do menu de opções (`widgets.controles.MenuDeOpcoes`, que o desenha): a
# de campo desde 2026-10-20 (era os 28 do CTkOptionMenu); a regra QComboBox da
# folha já dá 32, e o `sizeHint` dele tem de dizer o mesmo.
ALTURA_MENU_CTK = ALTURA_CAMPO

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
    # Remedido no polimento: o engrossamento soma 0,5-0,7 px por letra (13 a 16
    # px) e o hinting completo o arredonda para 1 px; título longo em minúsculas
    # sai até ~9% mais largo que no Tk da captura do Linux -- que usa o
    # Roboto-Medium engrossado (o fontconfig acha o Medium em ~/.fonts), e não o
    # Regular engrossado do GDI do Windows. Textos curtos e maiúsculas ficam
    # iguais; o hinting padrão erra mais (tudo ~7% mais estreito). Um ajuste por
    # letra consertaria os longos e estragaria os curtos: não há.
    fonte.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    QApplication.setFont(fonte)
    return familias




def _escurecer(cor: str, fator: float) -> str:
    """`cor` ("#RRGGBB") com cada canal multiplicado por `1 - fator`: o hover do
    botão de perigo, que não tem token próprio (o `perigo` claro é texto, e o
    branco sobre ele não chega a 4,5:1)."""
    cor = cor.lstrip("#")
    canais = (round(int(cor[i:i + 2], 16) * (1 - fator)) for i in (0, 2, 4))
    return "#" + "".join(f"{c:02X}" for c in canais)


# Variantes antigas que a folha trata como as novas (2026-10-20): as telas ainda
# passam esses nomes, e `blocos.botao` os troca na Task 4 do plano.
SINONIMOS_DE_VARIANTE = {
    "acento": "primario",
    "cinza": "secundario", "neutro": "secundario",
    "contorno": "secundario", "contorno_padrao": "secundario",
}


def _seletor_variante(variante: str, estado: str = "") -> str:
    """`QPushButton[variante="..."]` da variante e de cada sinônimo dela, com o
    nome novo POR ÚLTIMO (o teste procura a regra pelo nome novo seguido de "{")."""
    nomes = [antiga for antiga, nova in SINONIMOS_DE_VARIANTE.items() if nova == variante]
    nomes.append(variante)
    return ", ".join(f'QPushButton[variante="{n}"]{estado}' for n in nomes)


def folha_de_estilo(tema: str | None = None) -> str:
    """A folha QSS do app inteiro no `tema` ("escuro" ou "claro"), dos tokens, com
    o aumento da letra que está valendo (`AUMENTO_LETRA`, 2026-10-21).

    Sem argumento, o tema que está valendo (`TEMA_ATUAL`, que `tema.aplicar`
    define)."""
    return ajustar_tamanhos(_folha_base(tema), AUMENTO_LETRA)


def _folha_base(tema: str | None = None) -> str:
    """A folha QSS do app inteiro no `tema`, dos tokens, sem o aumento da letra.

    Sem argumento, o tema que está valendo (`TEMA_ATUAL`, que `tema.aplicar`
    define)."""
    tema = _tema(tema)
    p = tokens.paleta(tema)
    menu = MENU_ESCOLHIDO["claro" if tema == "claro" else "escuro"]
    f = tokens.FONTE
    raio, raio_cartao = tokens.RAIO["controle"], tokens.RAIO["cartao"]
    fam = '"Roboto", "Noto Emoji"'
    mono_fam = '"Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono", monospace'
    altura_botao = ALTURA_BOTAO - 2 * BORDA_CONTROLE
    altura_campo = ALTURA_CAMPO - 2 * BORDA_CONTROLE
    perigo_hover = _escurecer(p["perigo_fundo"], 0.15)
    # Notas que não cabem dentro da folha (comentário de QSS também é texto dela):
    # * botão sem variante = secundário (contorno `borda`, texto `texto`); as
    #   variantes antigas são sinônimos (SINONIMOS_DE_VARIANTE). Cada variante que
    #   diz `color:` repete o `:disabled` (mesma especificidade: a regra de depois ganha). O primário tem o
    #   texto ESCURO no tema escuro (branco sobre o verde vivo dava 3,1:1);
    # * perigo: fundo `perigo_fundo` e texto branco (5,3:1), nos dois temas;
    # * papéis de texto: QLabel[papel=...]. O "aviso" ganha o fundo `superficie`
    #   (pílula): a cor de aviso só chega a 4,5:1 sobre a superfície no claro
    #   (4,2 sobre o fundo). O "ok" usa `primaria`, e não `sucesso`, pelo mesmo
    #   motivo (sucesso claro sobre o fundo: 4,2; primária: 4,9);
    # * #console: escuro nos DOIS temas (é saída de terminal), fonte mono;
    # * QCheckBox::indicator: width/height NÃO contam a borda -- 20 + 2*2 = 24;
    # * #quadro_caixas/#lista_caixas: a seleção de fichas; as linhas são de
    #   `dialogs._DelegadoDaCaixa`; abas: não há regra de QTabWidget, é `widgets/abas`.
    return f"""
QMainWindow, #conteudo, #tela {{ background: {p['fundo']}; }}
QDialog {{ background: {p['fundo']}; }}
QWidget {{ font-family: {fam}; color: {p['texto']}; }}
QToolTip {{ background: {p['superficie_alta']}; color: {p['texto']}; border: 1px solid {p['borda']};
    padding: 4px 8px; }}
#sidebar, #sidebar_interno {{ background: {p['superficie']}; border: none; }}
#secao {{ color: {p['texto_suave']}; font-size: 11px; font-weight: bold; padding-left: 10px; }}
#app_nome {{ color: {p['texto_suave']}; font-size: {f['corpo']}px; }}
QPushButton {{ border-radius: {raio}px; color: {p['texto']}; background: transparent;
    border: {BORDA_CONTROLE}px solid {p['borda']}; padding: 0 14px;
    min-height: {altura_botao}px; font-size: {f['corpo']}px; }}
QPushButton:hover {{ background: {p['superficie_alta']}; }}
QPushButton:pressed {{ background: {p['borda']}; }}
QPushButton:disabled {{ color: {p['texto_suave']}; }}
{_seletor_variante('secundario')} {{ background: transparent; border-color: {p['borda']};
    color: {p['texto']}; }}
{_seletor_variante('secundario', ':hover')} {{ background: {p['superficie_alta']}; }}
{_seletor_variante('secundario', ':disabled')} {{ color: {p['texto_suave']}; }}
{_seletor_variante('primario')} {{ background: {p['primaria']}; border-color: {p['primaria']};
    color: {p['texto_sobre_primaria']}; }}
{_seletor_variante('primario', ':hover')} {{ background: {p['primaria_hover']};
    border-color: {p['primaria_hover']}; }}
{_seletor_variante('primario', ':disabled')} {{ background: {p['superficie_alta']};
    border-color: {p['borda']}; color: {p['texto_suave']}; }}
QPushButton[variante="perigo"] {{ background: {p['perigo_fundo']}; border-color: {p['perigo_fundo']};
    color: {TEXTO_SOBRE_PERIGO}; }}
QPushButton[variante="perigo"]:hover {{ background: {perigo_hover}; border-color: {perigo_hover}; }}
QPushButton[variante="perigo"]:disabled {{ background: {p['superficie_alta']};
    border-color: {p['borda']}; color: {p['texto_suave']}; }}
QPushButton[variante="fantasma"] {{ background: transparent; border-color: transparent; color: {p['texto']}; }}
QPushButton[variante="fantasma"]:hover {{ background: {p['superficie_alta']}; }}
QPushButton[variante="fantasma"]:disabled {{ color: {p['texto_suave']}; }}
QPushButton[variante="fantasma"][papel="link"] {{ color: {p['info']}; text-decoration: underline; }}
QPushButton[variante="fantasma"][papel="link"]:disabled {{ color: {p['texto_suave']}; }}
QPushButton[menu="true"] {{ background: transparent; text-align: left; padding: 0 10px; border: none;
    color: {p['texto']}; min-height: {ALTURA_BOTAO_MENU}px; max-height: {ALTURA_BOTAO_MENU}px;
    font-size: {f['legenda']}px; }}
QPushButton[menu="true"]:hover, QPushButton[menu="true"][ativo="true"] {{ background: {menu['fundo']};
    color: {menu['texto']}; }}
QPushButton[menu="true"][ativo="true"] {{ font-weight: bold; }}
QPushButton[menu="true"]:disabled {{ color: {p['texto_suave']}; }}
#marca, #marca:hover, #marca:pressed {{ background: transparent; border: none; padding: 0;
    min-height: 0; }}
#home {{ background: transparent; text-align: left; font-weight: bold;
         color: {p['texto']}; border: {BORDA_CONTROLE}px solid {p['borda']}; }}
#home:hover, #home[ativo="true"] {{ background: {menu['fundo']}; color: {menu['texto']}; }}
QPushButton[barra="true"] {{ min-height: {ALTURA_BOTAO_BARRA - 2 * BORDA_CONTROLE}px;
    min-width: {LARGURA_BOTAO_CTK - 2 * FOLGA_TEXTO_BOTAO_CTK - 2 * BORDA_CONTROLE}px; padding: 0 {FOLGA_TEXTO_BOTAO_CTK}px;
    font-weight: bold; }}
QLabel[papel="legenda"] {{ color: {p['texto_suave']}; font-size: {f['legenda']}px; }}
QLabel[papel="secao"] {{ font-size: {f['secao']}px; font-weight: bold; }}
QLabel[papel="titulo"] {{ font-size: {f['titulo']}px; font-weight: bold; }}
QLabel[papel="aviso"] {{ color: {p['aviso']}; background: {p['superficie']};
    border-radius: {raio}px; padding: 2px 6px; }}
QLabel[papel="erro"] {{ color: {p['perigo']}; }}
QLabel[papel="ok"] {{ color: {p['primaria']}; }}
#titulo_home {{ font-size: 32px; font-weight: bold; }}
#subtitulo_home {{ font-size: 16px; color: {p['texto_suave']}; }}
#texto_simples {{ font-size: 14px; }}
#titulo_modulo {{ font-size: {f['titulo']}px; font-weight: bold; color: {p['texto']}; }}
#faixa_atividade_texto {{ color: {p['texto']}; font-size: {f['legenda']}px; font-weight: bold; }}
#faixa_atividade_texto[estado="ok"] {{ color: {p['primaria']}; }}
#faixa_atividade_texto[estado="erro"] {{ color: {p['perigo']}; }}
#card {{ background: {p['superficie']}; border: 1px solid {p['borda']}; border-radius: {raio_cartao}px; }}
#card:hover {{ border: 1px solid {p['primaria']}; }}
#card_titulo {{ color: {p['primaria']}; font-size: {f['secao']}px; font-weight: bold; background: transparent; }}
#card_icone {{ background: transparent; }}
#card_desc {{ color: {p['texto_suave']}; font-size: {f['legenda']}px; background: transparent; }}
#console {{ background: {p['console_fundo']}; border: none; border-radius: {raio}px;
            color: {p['console_texto']}; font-family: {mono_fam}; font-size: 12px; }}
#notas_atualizacao {{ background: {p['superficie_alta']}; border: none; border-radius: {raio}px;
    color: {p['texto']}; font-size: 12px; padding: 5px 4px 3px 4px; }}
QCheckBox {{ font-size: 12px; }}
QCheckBox::indicator {{ width: 20px; height: 20px; border: 2px solid {p['texto_suave']};
                        border-radius: {raio}px; background: transparent; }}
QCheckBox::indicator:hover {{ border-color: {p['primaria']}; }}
QCheckBox::indicator:checked {{ background: {p['primaria']}; border-color: {p['primaria']}; }}
QCheckBox::indicator:disabled {{ border-color: {p['borda']}; }}
QProgressBar {{ background: {p['superficie_alta']}; border: none; border-radius: 5px; max-height: 12px; }}
QProgressBar::chunk {{ background: {p['primaria']}; border-radius: 5px; }}
QLineEdit {{ background: {p['superficie_alta']}; border: {BORDA_CONTROLE}px solid {p['borda']};
             border-radius: {raio}px; color: {p['texto']}; placeholder-text-color: {p['texto_suave']};
             font-size: {f['corpo']}px; padding: 0 6px;
             min-height: {altura_campo}px; max-height: {altura_campo}px; }}
QLineEdit:focus {{ border-color: {p['primaria']}; }}
QLineEdit:disabled {{ color: {p['texto_suave']}; }}
QComboBox {{ background: {p['superficie_alta']}; border: {BORDA_CONTROLE}px solid {p['borda']};
             border-radius: {raio}px; padding: 0 10px; color: {p['texto']}; font-size: {f['corpo']}px;
             min-height: {altura_campo}px; max-height: {altura_campo}px; }}
QComboBox:focus, QComboBox:on {{ border-color: {p['primaria']}; }}
QComboBox:disabled {{ color: {p['texto_suave']}; }}
QComboBox QAbstractItemView {{ background: {p['superficie']}; color: {p['texto']};
    selection-background-color: {menu['fundo']}; selection-color: {menu['texto']};
    border: 1px solid {p['borda']}; outline: none; }}
QListWidget {{ background: {p['superficie']}; color: {p['texto']}; border: none; }}
QListWidget::item:selected {{ background: {menu['fundo']}; color: {menu['texto']}; }}
#quadro_caixas {{ background: {p['superficie']}; border-radius: {raio}px; }}
#lista_caixas {{ background: transparent; border: none; font-size: {f['corpo']}px; }}
{folha_rolagem_ctk('#lista_caixas', margem_vertical=4, tema=tema)}
#cartao {{ background: {p['superficie']}; border-radius: {raio_cartao}px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {p['borda']}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {p['texto_suave']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
""" + _folha_e31(tema) + _folha_telas(tema) + _folha_ferramentas(tema)


# --- E3.1: rádio, slider, barra de progresso, abas, área rolável, tabela ---------
# (Interruptor/CTkSwitch, CTkOptionMenu e a caixa de marcar pintada são de
# `widgets/controles.py`.) As MEDIDAS seguem as da E3.1; as cores, os tokens.
# Rádio 22x22: borda 3 desmarcado, 6 marcado. No Qt `width`/`height` do
# ::indicator NÃO contam a borda.
TAMANHO_RADIO_CTK = 22
# Largura MÍNIMA do rádio: "Português" e "English" ocupam 100; o texto maior
# alarga. No QSS o `min-width` conta só o texto: os 22 da bolinha e os 6 do vão
# vêm por fora.
LARGURA_RADIO_CTK = 100
VAO_TEXTO_RADIO_CTK = 6
# Slider: 16 de altura, trilho de 4, botão redondo de 16; o centro do botão anda
# de 8 a largura - 8, o trilho vai de 6 a largura - 6.
ALTURA_SLIDER_CTK = 16
# Barra de rolagem das listas: faixa de 16 px, alça de 8 (4 de cada lado).
LARGURA_ROLAGEM_CTK = 16
# Fundo do quadro das abas (`widgets/abas.Abas`): regra `#quadro_abas` de
# `_folha_telas`. Na CTk o quadro era INVISÍVEL (gray13 era o próprio fundo
# antigo). Mantido: quadro sobre a tela = `fundo` (os cartões `superficie` de
# dentro continuam se vendo); quadro dentro de um cartão (`Abas(interno=True)`)
# = `superficie`.

# Linha da tabela (QTreeView) e altura do cabeçalho: 24 px, degrau da escala de
# espaço (2026-10-20; era o Treeview nativo do Tk, de 20 px).
ALTURA_LINHA_TABELA = 24
# tk.Listbox: cada linha tem a altura da fonte + 2 * selectborderwidth, que é 1 no
# X11 e 0 no Windows. Folga de cima e de baixo de cada item.
FOLGA_LINHA_LISTA_TK = 0 if sys.platform == "win32" else 1


def folha_rolagem_ctk(seletor: str = "", *, margem_vertical: int = 4, tema: str | None = None,
                      cores: bool = True) -> str:
    """A barra de rolagem das listas: faixa de 16 px, alça de 8 (4 dos lados) na
    cor `borda`, `texto_suave` sob o mouse, sem setas. `seletor` prefixa as regras
    (ex.: "#lista_caixas"); vazio, a folha vale para a própria QScrollBar (folha
    local). `margem_vertical`: onde a alça começa e acaba -- 4, mais o canto do
    quadro quando a barra vai da borda de cima à de baixo dele.

    `cores=False`: só as medidas. É o que a folha LOCAL de um widget deve usar
    (2026-10-20): ela não é regerada na troca de tema, e a cor da alça vem então
    da regra `QScrollBar::handle` da folha do app (as mesmas `borda` e
    `texto_suave`), que é."""
    p = tokens.paleta(_tema(tema))
    pre = f"{seletor} " if seletor else ""
    folga = (LARGURA_ROLAGEM_CTK - 8) // 2
    alca = f" background: {p['borda']};" if cores else ""
    alca_sobre = (f"{pre}QScrollBar::handle:vertical:hover {{ background: {p['texto_suave']}; }}\n"
                  if cores else "")
    return (f"{pre}QScrollBar:vertical {{ width: {LARGURA_ROLAGEM_CTK}px; background: transparent;"
            f" margin: {margem_vertical}px {folga}px; }}\n"
            f"{pre}QScrollBar::handle:vertical {{{alca} border-radius: 4px;"
            " min-height: 20px; }\n"
            f"{alca_sobre}"
            f"{pre}QScrollBar::add-line:vertical, {pre}QScrollBar::sub-line:vertical {{ height: 0; }}\n"
            f"{pre}QScrollBar::add-page:vertical, {pre}QScrollBar::sub-page:vertical {{ background: transparent; }}")


def _folha_e31(tema: str | None = None) -> str:
    """Rádio, slider, tabela (QTreeView) e lista clara -- E3.1, nas cores do tema.

    Num bloco à parte da folha principal só para as duas frentes da migração não
    mexerem nas mesmas linhas. Medidas: ver as constantes acima.
    """
    tema = _tema(tema)
    p = tokens.paleta(tema)
    menu = MENU_ESCOLHIDO["claro" if tema == "claro" else "escuro"]
    raio_radio = TAMANHO_RADIO_CTK // 2
    trilho = (ALTURA_SLIDER_CTK - 4) // 2  # 6: recuo do trilho nas pontas
    # Notas fora da folha:
    # * rádio: desmarcado borda 3 `texto_suave`, marcado borda 6 `primaria` (o
    #   miolo é o fundo), borda `primaria_hover` sob o mouse; texto 6 px depois;
    # * slider: o sulco é transparente e as duas metades (sub-page/add-page) é que
    #   desenham o trilho de 4 px, recuado 6 px das pontas -- assim o botão anda
    #   a largura inteira (centro de 8 a largura - 8);
    # * tabela e lista "claro": eram as cores do Tk nativo (tabela branca de texto
    #   preto); desde 2026-10-20 seguem o tema, como o resto. A propriedade
    #   `claro` ficou com o nome (as telas a põem), mas a lista não é mais clara
    #   no tema escuro. Barras de rolagem da tabela e de `barra_nativa`, idem.
    return f"""
QRadioButton {{ font-size: 13px; color: {p['texto']}; spacing: {VAO_TEXTO_RADIO_CTK}px;
    background: transparent; min-width: {LARGURA_RADIO_CTK - TAMANHO_RADIO_CTK - VAO_TEXTO_RADIO_CTK}px; }}
QRadioButton:disabled {{ color: {p['texto_suave']}; }}
QRadioButton::indicator {{ width: {TAMANHO_RADIO_CTK - 6}px; height: {TAMANHO_RADIO_CTK - 6}px;
    border: 3px solid {p['texto_suave']}; border-radius: {raio_radio}px; background: transparent; }}
QRadioButton::indicator:checked {{ width: {TAMANHO_RADIO_CTK - 12}px; height: {TAMANHO_RADIO_CTK - 12}px;
    border: 6px solid {p['primaria']}; }}
QRadioButton::indicator:hover {{ border-color: {p['primaria_hover']}; }}
QSlider:horizontal {{ min-height: {ALTURA_SLIDER_CTK}px; max-height: {ALTURA_SLIDER_CTK}px;
    background: transparent; }}
QSlider::groove:horizontal {{ height: {ALTURA_SLIDER_CTK}px; background: transparent; border: none; }}
QSlider::sub-page:horizontal {{ background: {p['primaria']}; border-radius: 2px;
    margin: {trilho}px 0 {trilho}px {trilho}px; }}
QSlider::add-page:horizontal {{ background: {p['borda']}; border-radius: 2px;
    margin: {trilho}px {trilho}px {trilho}px 0; }}
QSlider::handle:horizontal {{ width: {ALTURA_SLIDER_CTK}px; height: {ALTURA_SLIDER_CTK}px;
    border-radius: {ALTURA_SLIDER_CTK // 2}px; background: {p['primaria']}; }}
QSlider::handle:horizontal:hover {{ background: {p['primaria_hover']}; }}
QTreeView {{ background: {p['superficie']}; color: {p['texto']}; border: none;
    outline: none; font-size: 12px; alternate-background-color: {p['superficie_alta']};
    selection-background-color: {menu['fundo']}; selection-color: {menu['texto']}; }}
QTreeView::item {{ height: {ALTURA_LINHA_TABELA}px; padding-left: 4px; border: none; }}
QTreeView::item:hover {{ background: {p['superficie_alta']}; }}
QTreeView::item:selected {{ background: {menu['fundo']}; color: {menu['texto']}; }}
QHeaderView {{ background: {p['superficie_alta']}; }}
QHeaderView::section {{ background: {p['superficie_alta']}; color: {p['texto']}; padding: 0 6px;
    border: none; border-right: 1px solid {p['borda']}; border-bottom: 1px solid {p['borda']};
    height: {ALTURA_LINHA_TABELA}px; font-size: 12px; font-weight: bold; }}
QListWidget[claro="true"] {{ background: {p['superficie']}; color: {p['texto']}; border: 1px solid {p['borda']}; }}
QListWidget[claro="true"]::item:selected {{ background: {menu['fundo']}; color: {menu['texto']}; }}
QTreeView QScrollBar, QAbstractScrollArea[barra_nativa="true"] QScrollBar {{ background: {p['superficie']}; border: none; }}
QTreeView QScrollBar:vertical, QAbstractScrollArea[barra_nativa="true"] QScrollBar:vertical {{ width: 12px; }}
QTreeView QScrollBar:horizontal, QAbstractScrollArea[barra_nativa="true"] QScrollBar:horizontal {{ height: 12px; }}
QTreeView QScrollBar::handle:vertical, QAbstractScrollArea[barra_nativa="true"] QScrollBar::handle:vertical,
QTreeView QScrollBar::handle:horizontal, QAbstractScrollArea[barra_nativa="true"] QScrollBar::handle:horizontal {{
    background: {p['borda']}; border-radius: 4px; min-height: 20px; min-width: 20px; margin: 2px; }}
QTreeView QScrollBar::handle:vertical:hover, QAbstractScrollArea[barra_nativa="true"] QScrollBar::handle:vertical:hover,
QTreeView QScrollBar::handle:horizontal:hover, QAbstractScrollArea[barra_nativa="true"] QScrollBar::handle:horizontal:hover {{
    background: {p['texto_suave']}; }}
QTreeView QScrollBar::add-line, QTreeView QScrollBar::sub-line,
QAbstractScrollArea[barra_nativa="true"] QScrollBar::add-line,
QAbstractScrollArea[barra_nativa="true"] QScrollBar::sub-line {{
    width: 0; height: 0; }}
"""


# (E4.10 tinha aqui `FAMILIAS_COM_SIMBOLO`/`botao_com_simbolos`, a fonte de
# símbolos do "▶" e do "⬇" que o Roboto não tem. Os dois viraram ícone, em
# `sigft/app_qt/icones.py`, em 2026-10-20, e a peça saiu.)


# --- Cores que as telas e os widgets escreviam à mão (2026-10-20) -----------------
# Cada cor que morava num `setStyleSheet` de tela virou regra aqui, por
# objectName ou propriedade: assim a troca de tema alcança tudo. O hover da aba
# escolhida (o `primary_hover` antigo, a marca mais clara): branco sobre ele dá
# 5,1:1; sobre a marca, 7,6:1 -- o branco serve nos dois temas.
MARCA_HOVER = "#047A83"
TEXTO_SOBRE_MARCA = "#FFFFFF"


def _folha_telas(tema: str | None = None) -> str:
    """Papéis, cartões, abas, mural e janelas -- as cores que eram das telas.

    Num bloco à parte pelo mesmo motivo do `_folha_e31`. Notas fora da folha:
    * `destaque`: título de seção em verde (a `primaria`): 4,7:1 ou mais no
      fundo, na superfície e na superfície alta, nos dois temas (teste);
    * o cartão com borda (`#cartao[borda=...]`): o do AutoSpec que chama a atenção;
    * abas: medidas na folha local de `widgets/abas.py`; aqui só as cores;
    * mural: `COR_DA_FAIXA`/`COR_DA_CRITICIDADE` (acima), por propriedade;
    * seletores de tema e de letra da Home (`#seletor_tema`, `#seletor_letra`):
      o botão da escolha atual tem `ativo`, pintado como o item escolhido do menu.
    """
    tema = _tema(tema)
    p = tokens.paleta(tema)
    menu = MENU_ESCOLHIDO["claro" if tema == "claro" else "escuro"]
    faixas = COR_DA_FAIXA["claro" if tema == "claro" else "escuro"]
    raio, raio_cartao = tokens.RAIO["controle"], tokens.RAIO["cartao"]
    regras = [
        f'QLabel[papel="destaque"] {{ color: {p["primaria"]}; }}',
        f'QLabel[papel="texto"] {{ color: {p["texto"]}; }}',
        # O título do módulo tem regra por objectName (ganha do papel): o
        # vermelho da ação destrutiva (Apagar LMR) precisa da sua.
        f'#titulo_modulo[papel="erro"] {{ color: {p["perigo"]}; }}',
        f'#cartao[borda="destaque"] {{ border: 1px solid {p["primaria"]}; }}',
        f'#cartao[borda="aviso"] {{ border: 1px solid {p["aviso"]}; }}',
        f'#cartao[fundo="alto"] {{ background: {p["superficie_alta"]}; }}',
        f'QScrollArea[fundo="cartao"] {{ background: {p["superficie"]}; }}',
        f'QScrollArea[fundo="tela"] {{ background: {p["fundo"]}; }}',
        f'#janela_resultados, #janela_painel, #topo_revisao {{ background: {p["fundo"]}; }}',
        f'#painel_home {{ background: {p["superficie"]}; border-radius: {raio_cartao}px; }}',
        f'#quadro_pdm {{ background: {p["superficie_alta"]}; }}',
        # Abas (widgets/abas.py)
        f'#quadro_abas {{ background: {p["fundo"]}; border-radius: {raio}px; }}',
        f'#quadro_abas[interno="true"] {{ background: {p["superficie"]}; }}',
        f'#barra_abas {{ background: {p["superficie_alta"]}; }}',
        f'#barra_abas QPushButton {{ background: {p["superficie_alta"]}; color: {p["texto"]};'
        f' border-color: {p["superficie_alta"]}; }}',
        f'#barra_abas QPushButton:hover {{ background: {p["borda"]}; }}',
        f'#barra_abas QPushButton:checked {{ background: {p["marca"]}; color: {TEXTO_SOBRE_MARCA}; }}',
        f'#barra_abas QPushButton:checked:hover {{ background: {MARCA_HOVER}; }}',
        f'#barra_abas QPushButton:disabled {{ color: {p["texto_suave"]}; }}',
        # Seletor de tema da Home (Task 7): o escolhido como o item do menu.
        f'#seletor_tema QPushButton[ativo="true"], #seletor_letra QPushButton[ativo="true"] '
        f'{{ background: {menu["fundo"]}; color: {menu["texto"]}; border-color: {menu["fundo"]}; }}',
        # Mouse em cima: o texto acompanha o ícone, que já vai para a cor do menu.
        f'#seletor_tema QPushButton:hover, #seletor_letra QPushButton:hover {{ color: {menu["texto"]}; }}',
        # Busca PMIB: o cartão de cada achado, mais fundo que a lista onde está.
        f'#cartao_resultado {{ background: {p["fundo"]}; border: 1px solid {p["borda"]};'
        f' border-radius: 8px; }}',
        f'#cartao_resultado QPlainTextEdit {{ color: {p["texto"]};'
        f' selection-background-color: {menu["fundo"]}; selection-color: {menu["texto"]}; }}',
        f'#cartao_resultado QPlainTextEdit[papel="legenda"] {{ color: {p["texto_suave"]}; }}',
        f'QPlainTextEdit#caixa_texto {{ background: {p["superficie_alta"]}; color: {p["texto"]}; }}',
        f'QPlainTextEdit#caixa_texto QScrollBar::handle:vertical {{ background: {p["borda"]}; }}',
        f'QPlainTextEdit#caixa_texto QScrollBar::handle:vertical:hover {{ background: {p["texto_suave"]}; }}',
        f'QListWidget[com_borda="true"] {{ border: 1px solid {p["borda"]}; }}',
        # Mural de atividades (widgets/mural.py)
        f'#corpo_cartao {{ background: {p["superficie"]}; border-radius: {raio}px; }}',
        f'#barra_criticidade {{ background: {p["borda"]}; border: none; border-radius: 3px; }}',
        f'#barra_criticidade[criticidade="1"] {{ background: {p["texto_suave"]}; }}',
    ]
    for nivel, cor in COR_DA_CRITICIDADE.items():
        regras.append(f'#barra_criticidade[criticidade="{nivel}"] {{ background: {cor}; }}')
    for faixa, cor in faixas.items():
        regras.append(f'QLabel[faixa="{faixa}"] {{ color: {cor}; }}')
        regras.append(f'#regua_faixa[faixa="{faixa}"] {{ background: {cor}; border: none; }}')
    return "\n" + "\n".join(regras) + "\n"


def _folha_ferramentas(tema: str | None = None) -> str:
    """As ferramentas da etapa 1b (2026-10-21).

    * a barrinha que redimensiona o console (`widgets/puxador_console.py`);
    * barra do console (`widgets/console.py`): a paleta ESCURA nos dois temas,
      porque ela fica dentro do console, que é escuro sempre;
    * arrastar arquivo (`widgets/arrastar.py`): borda `primaria` quando o arquivo
      serve, `perigo` (borda e texto) quando não serve; a seta dos recentes;
    * Ctrl+K (`widgets/paleta.py`): cartão `superficie` com borda; item escolhido
      como o do menu.
    """
    tema = _tema(tema)
    p = tokens.paleta(tema)
    e = tokens.ESCURO
    f = tokens.FONTE
    menu = MENU_ESCOLHIDO["claro" if tema == "claro" else "escuro"]
    raio, raio_cartao = tokens.RAIO["controle"], tokens.RAIO["cartao"]
    regras = [
        f"#barra_console {{ background: {e['console_fundo']}; }}",
        f"#barra_console QPushButton {{ background: transparent; color: {e['texto_suave']};"
        f" border: 1px solid transparent; border-radius: 4px; padding: 0 8px;"
        f" min-height: 18px; max-height: 22px; font-size: {f['legenda']}px; }}",
        f"#barra_console QPushButton:hover {{ color: {e['texto']}; }}",
        f"#barra_console QPushButton:checked {{ color: {e['texto']}; background: {e['superficie_alta']};"
        f" border-color: {e['borda']}; }}",
        f"#barra_console QLineEdit {{ background: {e['superficie_alta']}; color: {e['texto']};"
        f" border: 1px solid {e['borda']}; border-radius: 4px; padding: 0 6px;"
        f" min-height: 18px; max-height: 22px; font-size: {f['legenda']}px;"
        f" placeholder-text-color: {e['texto_suave']}; }}",
        f"#barra_console QLineEdit:focus {{ border-color: {e['primaria']}; }}",
        # A barrinha que muda o tamanho do console (widgets/puxador_console.py):
        # parada, só a marca no meio; com o mouse em cima ou arrastando, a faixa
        # toda na `borda` e a marca na `primaria`.
        "#puxador_console { background: transparent; border-radius: 3px; }",
        f'#puxador_console[ativo="true"] {{ background: {p["borda"]}; }}',
        f"#puxador_console_marca {{ background: {p['borda']}; border-radius: 1px; }}",
        f'#puxador_console_marca[ativo="true"] {{ background: {p["primaria"]}; }}',
        # Arrastar arquivo: depois das variantes (mesma especificidade, esta ganha).
        f'QPushButton[arrasto="aceito"], QListWidget[arrasto="aceito"] {{ border: 1px solid {p["primaria"]}; }}',
        f'QPushButton[arrasto="recusado"], QListWidget[arrasto="recusado"] '
        f'{{ border: 1px solid {p["perigo"]}; color: {p["perigo"]}; }}',
        f'#seta_recentes {{ background: transparent; border: none; color: {p["texto_suave"]};'
        f' padding: 0 4px; font-size: {f["corpo"]}px; }}',
        f'#seta_recentes:hover {{ color: {p["texto"]}; }}',
        "#seta_recentes::menu-indicator { image: none; width: 0; }",
        # Ctrl+K (widgets/paleta.py)
        f'#paleta {{ background: {p["superficie"]}; border: 1px solid {p["borda"]};'
        f' border-radius: {raio_cartao}px; }}',
        f'#lista_paleta {{ background: {p["superficie"]}; border: none; outline: none;'
        f' font-size: {f["corpo"]}px; }}',
        f'#lista_paleta::item {{ padding: 6px 8px; border-radius: {raio}px; }}',
        f'#lista_paleta::item:selected {{ background: {menu["fundo"]}; color: {menu["texto"]}; }}',
    ]
    return "\n" + "\n".join(regras) + "\n"


def folha_da_splash(tema: str | None = None) -> str:
    """A folha da splash (Task 10), no `tema` (sem ele, `TEMA_ATUAL`). Mora aqui
    porque cor fora do `estilo.py` reprova (`tests/test_qt_sem_cor_crua.py`).
    O trilho da barra é a `borda`: a `superficie_alta` some sobre o `fundo` claro."""
    p = tokens.paleta(tema or TEMA_ATUAL)
    return f"""
        QLabel {{ background: transparent; }}
        QLabel#splash_titulo {{ color: {p['texto']}; font-size: {tokens.FONTE['titulo']}px;
                                font-weight: bold; }}
        QLabel#splash_versao {{ color: {p['texto_suave']}; font-size: {tokens.FONTE['legenda']}px; }}
        QLabel#splash_status {{ color: {p['texto_suave']}; font-size: {tokens.FONTE['legenda']}px; }}
        QProgressBar {{ background: {p['borda']}; border: none; border-radius: 2px;
                        min-height: 4px; max-height: 4px; }}
        QProgressBar::chunk {{ background: {p['primaria']}; border-radius: 2px; }}
    """
