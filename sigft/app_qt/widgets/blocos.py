"""Peças que todas as telas repetem: o quadro cinza, o rótulo, o botão.

Nas telas antigas cada uma vinha com cor, fonte e tamanho escritos à
mão. Aqui a COR vem toda da folha de estilo (objectName, `variante` dos botões,
`papel` dos rótulos -- desde 2026-10-20 nenhuma peça daqui tem cor própria);
fonte e tamanho continuam por chamada, porque variam de tela a tela.
"""
from __future__ import annotations

import os

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QFontMetrics, QPainter, QPalette
from PySide6.QtWidgets import (
    QFrame, QLabel, QProgressBar, QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget,
)

from sigft.app_qt import estilo
from sigft.app_qt import propriedades

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


class RotuloElidido(QLabel):
    """Rótulo de uma linha para um nome que pode ser comprido (arquivo, pasta).

    Com espaço, é um QLabel comum: mede e desenha igual. Sem espaço, o texto é
    ELIDIDO no meio (`QFontMetrics.elidedText`: o começo e a extensão ficam à
    vista) em vez de alargar o formulário -- um nome de ~85 caracteres ou mais
    empurrava a tela além da janela. É o único lugar que elide: `text()`
    continua sendo o texto inteiro, e `mostrar_caminho` põe o caminho completo
    no tooltip.
    """

    MODO = Qt.TextElideMode.ElideMiddle

    def mostrar_caminho(self, caminho: str, texto: str | None = None) -> None:
        """O nome do arquivo (ou `texto`) no rótulo e o caminho completo no tooltip."""
        self.setText(texto if texto is not None else (os.path.basename(caminho) or caminho))
        self.setToolTip(caminho)

    def texto_visivel(self) -> str:
        """O que cabe na largura de agora (o próprio texto, quando cabe)."""
        return self.fontMetrics().elidedText(self.text(), self.MODO, self._caixa_do_texto().width())

    def minimumSizeHint(self) -> QSize:  # noqa: N802 -- nome do Qt
        # A largura do texto deixa de ser o mínimo: o layout pode estreitar o
        # rótulo, e o que não couber é elidido. Ao menos as reticências cabem.
        dica = super().minimumSizeHint()
        return QSize(self.fontMetrics().horizontalAdvance("…"), dica.height())

    def _caixa_do_texto(self):
        margem = self.margin()
        return self.contentsRect().adjusted(margem, margem, -margem, -margem)

    def paintEvent(self, _evento) -> None:  # noqa: N802 -- nome do Qt
        # O desenho do QLabel de texto puro -- a moldura e o `drawItemText` do
        # estilo, que pinta o texto na cor da paleta (a da folha) --, com o
        # texto que cabe no lugar do inteiro. Sem `self.style()`: o estilo de um
        # widget com folha é um QStyleSheetStyle que o Qt recria quando a folha
        # muda, e chamá-lo pelo Python derrubava o app (objeto já apagado).
        pintor = QPainter(self)
        self.drawFrame(pintor)
        if not self.isEnabled():
            grupo = QPalette.ColorGroup.Disabled
        elif self.isActiveWindow():
            grupo = QPalette.ColorGroup.Active
        else:
            grupo = QPalette.ColorGroup.Inactive
        pintor.setPen(self.palette().color(grupo, self.foregroundRole()))
        pintor.drawText(self._caixa_do_texto(), int(self.alignment()), self.texto_visivel())
        pintor.end()


def rotulo(texto: str, *, tamanho: int = 13, negrito: bool = False, papel: str | None = None,
           alinhar: str = "centro", elidir: bool = False) -> QLabel:
    """`elidir=True`: um `RotuloElidido` (uma linha) para nome de arquivo ou pasta.

    `papel` é o papel de texto da folha (`legenda`, `destaque`, `aviso`, `erro`,
    `ok`...): a cor sai dela, e não do rótulo (2026-10-20, tema claro/escuro)."""
    etiqueta = RotuloElidido(texto) if elidir else QLabel(texto)
    if papel:
        etiqueta.setProperty("papel", papel)
    etiqueta.setAlignment(_ALINHAMENTO[alinhar])
    etiqueta.setWordWrap(not elidir)
    etiqueta.setMinimumHeight(ALTURA_MINIMA_ROTULO)
    folha = f"font-size: {tamanho}px; background: transparent;"
    if negrito:
        folha += " font-weight: bold;"
    etiqueta.setStyleSheet(folha)
    return etiqueta


def sem_tecla(botao) -> None:
    """Botão que nenhuma tecla aperta, como o CTkButton, que nunca pega o foco.

    No Qt o botão pega o foco no clique (e no Tab), e aí um Espaço perdido o
    apertava; numa janela de diálogo o autoDefault fazia o mesmo com o Enter --
    nas que seguram o robô, soltando-o (e começando o lote) antes de a pessoa
    terminar o login. Esc e o "X" continuam valendo. Todo `botao` nasce assim
    (decisão do polimento, pela paridade com a interface antiga); botões criados à mão
    (barra lateral, abas, seletores) chamam esta função. Era `dialogs.sem_tecla`,
    que continua com esse nome.
    """
    botao.setAutoDefault(False)
    botao.setDefault(False)
    botao.setFocusPolicy(Qt.FocusPolicy.NoFocus)


def variante_da_cor(cor: str | None) -> str | None:
    """A variante de botão que ocupa o lugar de uma cor de fundo escrita à mão
    (2026-10-20): a cor passou a ser decisão da folha do tema, que muda no claro/escuro.
    Verde e azul-marca viram `primario`; vermelho, `perigo`; `transparent`,
    `fantasma`; qualquer outra (os cinzas) é `secundario`. `None` fica `None`."""
    if not cor:
        return None
    return estilo.VARIANTE_DA_COR.get(cor.upper(), "secundario")


def botao(texto: str, *, variante: str | None = None, largura: int | None = None,
          altura: int | None = None, tamanho_fonte: int | None = None,
          negrito: bool = False, cor_fundo: str | None = None,
          largura_minima: int | None = None) -> QPushButton:
    """A cor é da variante, na folha do tema. `cor_fundo` (o `fg_color` de um
    CTkButton pintado à mão) ainda é aceito e vira variante (`variante_da_cor`),
    mas nenhuma tela o passa (guarda em `tests/test_qt_botoes.py`); o
    `cor_texto` e o `cor_hover` saíram em 2026-10-20.

    `largura` FIXA a largura; `largura_minima` é o `width` do CTkButton de
    verdade: o botão tem pelo menos isso, e o texto que não cabe o alarga com
    `FOLGA_TEXTO_BOTAO_CTK` de cada lado (o "Editar PDM Selecionado" de 140 sai
    com 151 lá)."""
    if cor_fundo and not variante:
        variante = variante_da_cor(cor_fundo)
    b = QPushButton(texto)
    sem_tecla(b)
    if variante:
        b.setProperty("variante", variante)
    if largura:
        b.setFixedWidth(largura)
    folha = ""
    if altura:
        # Não basta `setFixedHeight`: ao aplicar a folha do app, o Qt troca a
        # altura mínima pelo `min-height` dela (28 px) e o botão encolhe. A
        # altura vai na folha do PRÓPRIO botão, que ganha da global. O
        # `min-height` do Qt não conta a borda; o `height` da interface antiga conta.
        interna = altura - 2 * estilo.BORDA_DA_VARIANTE.get(variante or "", 0)
        folha += f" min-height: {interna}px; max-height: {interna}px;"
    if largura_minima:
        folga = estilo.FOLGA_TEXTO_BOTAO_CTK
        # O `min-width` do Qt também não conta a borda (1 px em toda variante
        # desde 2026-10-20): a largura pedida continua sendo a total.
        borda = estilo.BORDA_DA_VARIANTE.get(variante or "", 0)
        folha += f" min-width: {largura_minima - 2 * folga - 2 * borda}px; padding: 0 {folga}px;"
    if tamanho_fonte:
        folha += f" font-size: {tamanho_fonte}px;"
    if negrito:
        folha += " font-weight: bold;"
    if folha:
        b.setStyleSheet(f"QPushButton {{{folha} }}")
    return b


# Onde `pintar` guarda a folha com que a peça nasceu (a Criação de Fichas a
# grava logo ao criar o botão; as outras peças, na primeira pintura).
_FOLHA_BASE = "_folha_base"


def pintar(widget, folha: str) -> None:
    """O `configure(fg_color=..., text_color=...)` da interface antiga numa peça com folha
    própria: a folha de quando ela nasceu + `folha`. Pintar de novo REFAZ a
    folha a partir dessa base, em vez de somar regra a regra a cada escolha."""
    base = propriedades.ler(widget, _FOLHA_BASE)
    if base is None:
        # A folha de antes do aumento da letra (2026-10-21): o aumento é refeito
        # depois, pelo vigia de `letra.py`; somado aqui, ele contaria duas vezes.
        base = estilo.folha_sem_aumento(widget)
        widget.setProperty(_FOLHA_BASE, base)
    widget.setStyleSheet(f"{base} {folha}".strip())


def marcar_arquivo_escolhido(botao, rotulo, caminho: str) -> None:
    """Arquivo escolhido: o nome no papel `ok` (verde) no rótulo (um
    `RotuloElidido`: elidido se for longo, com o caminho completo no tooltip) e
    o botão na variante `primario` -- as cores são da folha do tema."""
    rotulo.mostrar_caminho(caminho)
    estilo.definir_papel(rotulo, "ok")
    estilo.definir_variante(botao, "primario")


# --- E3.1: fonte de tupla do Tk, área rolável, barra de progresso, slider -----

# Famílias que o Tk acha e o Qt talvez não: a de reserva tem a mesma cara.
_RESERVA_DA_FAMILIA = {
    "Consolas": ["Consolas", "Menlo", "DejaVu Sans Mono", "monospace"],
    "Segoe UI": ["Segoe UI", "Roboto"],
}


def fonte_tk(tupla, *, em_pontos: bool = False) -> QFont:
    """`("Roboto", 14, "bold")` do Tk em QFont.

    O mesmo número quer dizer coisas diferentes lá: num widget do
    interface antiga é PIXEL (a interface antiga passa o tamanho negativo ao Tk); num widget
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


def rotulo_tk(texto: str, fonte: tuple, papel: str | None = None, *, direita: bool = False,
              largura: int | None = None, largura_minima: int | None = None,
              quebra: int | None = None) -> QLabel:
    """CTkLabel com a fonte em tupla do Tk (`("Roboto", 13)`, pixels) e o
    `papel` de texto da folha (a cor sai dela; sem papel, o texto comum): 28 px
    de altura no mínimo, texto centrado na vertical, encostado à esquerda
    (`direita`: o `anchor="e"`).

    Texto PURO, como o do CTkLabel: em AutoText o QLabel tomaria um "Trocar <a>
    por <b> no PDM" (texto da planilha) por HTML e engoliria as "tags".
    `largura` FIXA a largura; `largura_minima` é o `width=` (o texto maior
    alarga); `quebra` é o `wraplength`: o texto que passa dele quebra linha
    naquela largura, e o que cabe fica numa linha só, com a largura dele.
    (Era o `_rotulo` quase igual da Home e do mural.)
    """
    r = QLabel(texto)
    r.setTextFormat(Qt.TextFormat.PlainText)
    horizontal = Qt.AlignmentFlag.AlignRight if direita else Qt.AlignmentFlag.AlignLeft
    r.setAlignment(horizontal | Qt.AlignmentFlag.AlignVCenter)
    r.setMinimumHeight(ALTURA_MINIMA_ROTULO)
    if papel:
        r.setProperty("papel", papel)
    r.setStyleSheet(f"{folha_fonte_tk(fonte)} background: transparent;")
    if largura_minima:
        r.setMinimumWidth(largura_minima)
    if largura:
        r.setFixedWidth(largura)
    if quebra:
        medida = QFontMetrics(fonte_tk(fonte))
        if max(medida.horizontalAdvance(linha) for linha in str(texto).split("\n")) > quebra:
            r.setWordWrap(True)
            r.setFixedWidth(quebra)
    return r


def geometria_tk(texto: str) -> tuple[int, int]:
    """O `geometry("900x600")` do Tk (com ou sem "+x+y") em (largura, altura)."""
    largura, altura = texto.lower().split("+")[0].split("x")
    return int(largura), int(altura)


def area_rolavel(layout_pai=None, *, fundo: str | None = None, margem: int = 6,
                 barra_sempre_visivel: bool = False):
    """CTkScrollableFrame: devolve `(area, layout)` -- os filhos vão no `layout`.

    `fundo=None` é o `fg_color="transparent"` (o uso mais comum nas telas);
    `"cartao"` (a superfície) e `"tela"` (o fundo) são regras
    `QScrollArea[fundo=...]` da folha. Os cantos são os de 6 do CTkFrame. `margem` é o recuo do
    conteúdo (6 = o canto, medido). A barra de rolagem é a da interface antiga (16 px, alça
    gray41 de 8) e aparece só quando há o que rolar -- a mesma decisão da barra
    lateral (main.py): lá ela é um traço sempre visível que não rola nada.

    `barra_sempre_visivel=True` é o CTkScrollableFrame como ele é, para a tela
    que precisa das mesmas larguras de lá:
    * a barra SEMPRE à vista (a interface antiga reserva a faixa e desenha a alça cheia sem
      nada para rolar; sem ela os cartões saíam 11 a 16 px mais largos e o que
      é centrado andava), numa faixa de 17 px -- os 16 da barra + 1 até a borda
      direita --, com a alça de 8 a 4 px do começo da faixa;
    * o conteúdo `margem` px para dentro à esquerda e indo até a faixa;
    * o recorte: o canvas fica `margem` px para dentro do quadro em cima e
      embaixo, e o que rola some ali -- não corre até a borda (num quadro com
      cor, as linhas ficam dentro dos cantos redondos). A barra continua com a
      altura toda.
    """
    # Folhas SEMPRE com seletor de objectName: uma "background: transparent"
    # solta vale para todos os descendentes e apagava o fundo de cartões e
    # botões postos na área.
    area = QScrollArea(objectName="area_rolavel")
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    if fundo:
        area.setProperty("fundo", fundo)
    area.setStyleSheet("#area_rolavel { border: none; border-radius: 6px; }")
    area.viewport().setObjectName("area_rolavel_vista")
    area.viewport().setStyleSheet("#area_rolavel_vista { background: transparent; }")
    interno = QWidget(objectName="area_rolavel_interno")
    interno.setStyleSheet("#area_rolavel_interno { background: transparent; }")
    layout = QVBoxLayout(interno)
    layout.setContentsMargins(margem, margem, margem, margem)
    layout.setSpacing(0)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    area.setWidget(interno)
    # A alça começa no canto do quadro (margem) + os 4 do border_spacing. Só as
    # medidas: a cor da alça é a da folha do app, que a troca de tema regera
    # (2026-10-20); a desta folha local ficaria no tema da criação.
    folha_barra = estilo.folha_rolagem_ctk(margem_vertical=margem + 4, cores=False)
    if barra_sempre_visivel:
        area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        folga = estilo.LARGURA_ROLAGEM_CTK - 8 - 4   # o que sobra da faixa depois da alça
        folha_barra += (f"\nQScrollBar:vertical {{ width: {estilo.LARGURA_ROLAGEM_CTK + 1}px;"
                        f" margin: {margem + 4}px {folga + 1}px {margem + 4}px 4px; }}")
        area.setViewportMargins(0, margem, 0, margem)
        layout.setContentsMargins(margem, 0, 0, 0)
    area.verticalScrollBar().setStyleSheet(folha_barra)
    if layout_pai is not None:
        layout_pai.addWidget(area)
    return area, layout


def barra_progresso(*, largura: int | None = None, altura: int = 8,
                    barra: QProgressBar | None = None) -> QProgressBar:
    """CTkProgressBar: `width`/`height` da interface antiga.

    200 x 8 (aqui a largura só é fixada se pedida), pontas redondas
    (corner_radius=1000 -> metade da altura); trilho e progresso são as cores
    da folha (`superficie_alta` e `primaria`). Faixa 0-1000, sem texto.
    `barra=` estiliza uma que já existe (ex.: `ModuleFrame.progress_bar`).
    """
    barra = barra or QProgressBar()
    barra.setRange(0, 1000)
    barra.setTextVisible(False)
    barra.setFixedHeight(altura)
    if largura:
        barra.setFixedWidth(largura)
    raio = altura // 2
    barra.setStyleSheet(
        f"QProgressBar {{ border: none; border-radius: {raio}px;"
        f" min-height: {altura}px; max-height: {altura}px; }}"
        f" QProgressBar::chunk {{ border-radius: {raio}px; }}")
    return barra


def definir_progresso(barra: QProgressBar, fracao: float) -> None:
    """O `progress_bar.set(fracao)` da interface antiga (0.0 a 1.0) numa barra de `barra_progresso`.

    A interface antiga desenha o trecho cheio com as pontas redondas DENTRO da barra: com
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


def slider(*, minimo: int = 0, maximo: int = 100, largura: int = 200) -> QSlider:
    """CTkSlider horizontal (`from_`/`to` inteiros; `number_of_steps` = a faixa).

    A cara, cores incluídas, vem da folha global (`primaria` no botão e no
    trecho percorrido, desde 2026-10-20).
    """
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(minimo, maximo)
    s.setFixedSize(largura, estilo.ALTURA_SLIDER_CTK)
    return s


class BarraDeProgresso(QProgressBar):
    """CTkProgressBar que guarda a fração e a redesenha quando a largura muda.

    `definir_progresso` converte a fração em valor PELA LARGURA da barra (as
    pontas redondas); sem refazer a conta no resize, o `set(0)` feito antes de
    a tela aparecer viraria um trecho de 8 % numa barra de 870 px. Estilizar com
    `barra_progresso(barra=BarraDeProgresso(), ...)`. (Era `_BarraDeProgresso`
    da Cópia de Fichas; a Criação de Fichas precisa da mesma.)
    """

    fracao = 0.0

    def definir(self, fracao: float) -> None:
        self.fracao = float(fracao)
        definir_progresso(self, self.fracao)

    def resizeEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        super().resizeEvent(evento)
        definir_progresso(self, self.fracao)
