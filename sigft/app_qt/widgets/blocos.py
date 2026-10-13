"""Peças que todas as telas repetem: o quadro cinza, o rótulo, o botão.

Nas telas CustomTkinter cada uma vinha com cor, fonte e tamanho escritos à
mão. Aqui a COR do quadro e dos botões vem da folha de estilo (objectName e
variante); fonte e tamanho continuam por chamada, porque variam de tela a tela.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QLabel, QProgressBar, QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget,
)

from sigft.app_qt import estilo

# "esquerda" é o anchor="w" do CTkLabel: encostado à esquerda, centrado na vertical.
_ALINHAMENTO = {
    "centro": Qt.AlignmentFlag.AlignCenter,
    "esquerda": Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
}

# Altura mínima de um CTkLabel (o `height` padrão dele): um rótulo de uma linha
# ocupa isto na tela antiga mesmo com fonte menor, com o texto centrado.
ALTURA_MINIMA_ROTULO = 28


def cartao(layout_pai) -> QVBoxLayout:
    """O quadro cinza. Rótulos ocupam a largura toda (centram o próprio texto);
    botão de largura fixa vai centrado com `addWidget(b, alignment=AlignHCenter)`.

    Sem `setAlignment` no layout inteiro: ele dava a um rótulo com quebra de
    linha uma largura estreita demais, e o texto saía cortado.
    """
    quadro = QFrame(objectName="cartao")
    layout = QVBoxLayout(quadro)
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(10)
    layout_pai.addWidget(quadro)
    return layout


def rotulo(texto: str, *, tamanho: int = 13, negrito: bool = False, cor: str | None = None,
           alinhar: str = "centro") -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setAlignment(_ALINHAMENTO[alinhar])
    etiqueta.setWordWrap(True)
    etiqueta.setMinimumHeight(ALTURA_MINIMA_ROTULO)
    folha = f"font-size: {tamanho}px; background: transparent;"
    if negrito:
        folha += " font-weight: bold;"
    if cor:
        folha += f" color: {cor};"
    etiqueta.setStyleSheet(folha)
    return etiqueta


def botao(texto: str, *, variante: str | None = None, largura: int | None = None,
          altura: int | None = None, tamanho_fonte: int | None = None,
          negrito: bool = False, cor_texto: str | None = None, cor_fundo: str | None = None,
          cor_hover: str = estilo.AZUL_CTK_HOVER) -> QPushButton:
    """`cor_fundo` é o `fg_color` de um CTkButton pintado à mão; `cor_hover`, o
    `hover_color` (sem ele, o CTk usa o do tema: AZUL_CTK_HOVER)."""
    b = QPushButton(texto)
    if variante:
        b.setProperty("variante", variante)
    if largura:
        b.setFixedWidth(largura)
    folha = ""
    if altura:
        # Não basta `setFixedHeight`: ao aplicar a folha do app, o Qt troca a
        # altura mínima pelo `min-height` dela (28 px) e o botão encolhe. A
        # altura vai na folha do PRÓPRIO botão, que ganha da global. O
        # `min-height` do Qt não conta a borda; o `height` do CTk conta.
        interna = altura - 2 * estilo.BORDA_DA_VARIANTE.get(variante or "", 0)
        folha += f" min-height: {interna}px; max-height: {interna}px;"
    if tamanho_fonte:
        folha += f" font-size: {tamanho_fonte}px;"
    if negrito:
        folha += " font-weight: bold;"
    extra = ""
    if cor_fundo:
        folha += f" background: {cor_fundo};"
        extra += f" QPushButton:hover {{ background: {cor_hover}; }}"
    if cor_texto:
        folha += f" color: {cor_texto};"
        # A folha do botão ganha da do app em TODOS os estados: sem repetir o
        # desabilitado aqui, o texto ficaria com `cor_texto` mesmo desligado.
        extra += f" QPushButton:disabled {{ color: {estilo.cinza_tk(estilo.TEXTO_DESABILITADO_CTK)}; }}"
    if folha:
        b.setStyleSheet(f"QPushButton {{{folha} }}{extra}")
    return b


# --- E3.1: fonte de tupla do Tk, área rolável, barra de progresso, slider -----

# Famílias que o Tk acha e o Qt talvez não: a de reserva tem a mesma cara.
_RESERVA_DA_FAMILIA = {
    "Consolas": ["Consolas", "Menlo", "DejaVu Sans Mono", "monospace"],
    "Segoe UI": ["Segoe UI", "Roboto"],
}


def fonte_tk(tupla, *, em_pontos: bool = False) -> QFont:
    """`("Roboto", 14, "bold")` do Tk em QFont.

    O mesmo número quer dizer coisas diferentes lá: num widget do
    CustomTkinter é PIXEL (o CTk passa o tamanho negativo ao Tk); num widget
    cru do Tk (`tk.Listbox`, `ttk.Treeview`) é PONTO. `em_pontos=True` para os
    crus.
    """
    familia, tamanho, *estilos = tuple(tupla)
    fonte = QFont()
    fonte.setFamilies(_RESERVA_DA_FAMILIA.get(familia, [familia]) + ["Roboto", "Noto Emoji"])
    if familia == "Consolas":
        fonte.setStyleHint(QFont.StyleHint.Monospace)
    if em_pontos:
        fonte.setPointSize(int(tamanho))
    else:
        fonte.setPixelSize(int(tamanho))
    marcas = " ".join(str(e) for e in estilos)
    fonte.setBold("bold" in marcas)
    fonte.setItalic("italic" in marcas)
    return fonte


def folha_fonte_tk(tupla, *, em_pontos: bool = False) -> str:
    """A mesma fonte de `fonte_tk`, em folha de estilo.

    Para widget que a folha do app alcança: o `font-family` dela (Roboto) GANHA
    do `setFont`, então numa lista em Consolas a família tem de ir na folha.
    """
    f = fonte_tk(tupla, em_pontos=em_pontos)
    familias = ", ".join(f'"{n}"' for n in f.families())
    tamanho = f"{f.pointSize()}pt" if em_pontos else f"{f.pixelSize()}px"
    peso = "bold" if f.bold() else "normal"
    return f"font-family: {familias}; font-size: {tamanho}; font-weight: {peso};"


def geometria_tk(texto: str) -> tuple[int, int]:
    """O `geometry("900x600")` do Tk (com ou sem "+x+y") em (largura, altura)."""
    largura, altura = texto.lower().split("+")[0].split("x")
    return int(largura), int(altura)


def area_rolavel(layout_pai=None, *, cor: str | None = None, margem: int = 6):
    """CTkScrollableFrame: devolve `(area, layout)` -- os filhos vão no `layout`.

    `cor=None` é o `fg_color="transparent"` (o uso mais comum nas telas); com
    cor, o quadro tem os cantos de 6 do CTkFrame. `margem` é o recuo do
    conteúdo (6 = o canto, medido). A barra de rolagem é a do CTk (16 px, alça
    gray41 de 8) e aparece só quando há o que rolar -- a mesma decisão da barra
    lateral (main.py): lá ela é um traço sempre visível que não rola nada.
    """
    # Folhas SEMPRE com seletor de objectName: uma "background: transparent"
    # solta vale para todos os descendentes e apagava o fundo de cartões e
    # botões postos na área.
    area = QScrollArea(objectName="area_rolavel")
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    fundo = estilo.cinza_tk(cor) if cor else "transparent"
    area.setStyleSheet(f"#area_rolavel {{ background: {fundo}; border: none; border-radius: 6px; }}")
    area.viewport().setObjectName("area_rolavel_vista")
    area.viewport().setStyleSheet("#area_rolavel_vista { background: transparent; }")
    interno = QWidget(objectName="area_rolavel_interno")
    interno.setStyleSheet("#area_rolavel_interno { background: transparent; }")
    layout = QVBoxLayout(interno)
    layout.setContentsMargins(margem, margem, margem, margem)
    layout.setSpacing(0)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    area.setWidget(interno)
    # A alça começa no canto do quadro (margem) + os 4 do border_spacing.
    area.verticalScrollBar().setStyleSheet(estilo.folha_rolagem_ctk(margem_vertical=margem + 4))
    if layout_pai is not None:
        layout_pai.addWidget(area)
    return area, layout


def barra_progresso(*, largura: int | None = None, altura: int = 8, cor: str | None = None,
                    fundo: str = estilo.TRILHO_CTK, barra: QProgressBar | None = None) -> QProgressBar:
    """CTkProgressBar: `width`/`height`/`progress_color`/`fg_color` do CTk.

    Padrão do tema: 200 x 8 (aqui a largura só é fixada se pedida), trilho
    #4A4D50, progresso azul, pontas redondas (corner_radius=1000 -> metade da
    altura). Faixa 0-1000, sem texto. `barra=` estiliza uma que já existe (ex.:
    `ModuleFrame.progress_bar`).
    """
    barra = barra or QProgressBar()
    barra.setRange(0, 1000)
    barra.setTextVisible(False)
    barra.setFixedHeight(altura)
    if largura:
        barra.setFixedWidth(largura)
    raio = altura // 2
    barra.setStyleSheet(
        f"QProgressBar {{ background: {fundo}; border: none; border-radius: {raio}px;"
        f" min-height: {altura}px; max-height: {altura}px; }}"
        f" QProgressBar::chunk {{ background: {cor or estilo.AZUL_CTK}; border-radius: {raio}px; }}")
    return barra


def definir_progresso(barra: QProgressBar, fracao: float) -> None:
    """O `progress_bar.set(fracao)` do CTk (0.0 a 1.0) numa barra de `barra_progresso`.

    O CTk desenha o trecho cheio com as pontas redondas DENTRO da barra: com
    raio r e largura L, ele vai até r + fracao * (L - 2r) + r -- em 0 já há um
    ponto de 2r, e em 40% de 200 x 8 o fim está em 84,8 (o `setValue` cru daria 80).
    Com a barra em modo indeterminado, não faz nada (lá o `set` também não aparece
    enquanto a animação corre); o valor volta a contar depois de `modo_indeterminado(barra, False)`.
    """
    if barra.maximum() == barra.minimum():
        return  # em modo indeterminado (faixa 0-0) um valor não quer dizer nada
    fracao = min(max(float(fracao), 0.0), 1.0)
    largura = barra.width() or 1
    raio = barra.height() / 2
    cheio = 2 * raio + fracao * (largura - 2 * raio)
    barra.setValue(round(barra.maximum() * min(cheio / largura, 1.0)))


def modo_indeterminado(barra: QProgressBar, ligado: bool) -> None:
    """O `configure(mode="indeterminate")` + `start()`/`stop()` do CTkProgressBar.

    Ligado: faixa 0-0, que o Qt anima sozinho (o bloco que vai e vem). Desligado:
    volta à faixa 0-1000 de `barra_progresso`, em zero (o `stop()` + `set(0)` que a
    tela fazia).
    """
    if ligado:
        barra.setRange(0, 0)
    else:
        barra.setRange(0, 1000)
        barra.setValue(0)


def slider(*, minimo: int = 0, maximo: int = 100, largura: int = 200, cor_botao: str | None = None,
           cor_percorrido: str | None = None, cor_botao_hover: str | None = None) -> QSlider:
    """CTkSlider horizontal (`from_`/`to` inteiros; `number_of_steps` = a faixa).

    A cara vem da folha global; `cor_botao`/`cor_percorrido` são o
    `button_color`/`progress_color` do CTk (o Analisador pinta os dois de
    primary). O hover do botão, que o CTk deriva do tema, vira `cor_botao_hover`.
    """
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(minimo, maximo)
    s.setFixedSize(largura, estilo.ALTURA_SLIDER_CTK)
    folha = ""
    if cor_botao:
        folha += f" QSlider::handle:horizontal {{ background: {cor_botao}; }}"
    if cor_botao_hover:
        folha += f" QSlider::handle:horizontal:hover {{ background: {cor_botao_hover}; }}"
    if cor_percorrido:
        folha += f" QSlider::sub-page:horizontal {{ background: {cor_percorrido}; }}"
    if folha:
        s.setStyleSheet(folha.strip())
    return s
