"""Os ícones da interface: SVG de traço do Lucide, pintados na cor do tema.

Sistema visual, 2026-10-20 (Task 6): os emoji dos botões e do menu saíram. O
emoji dependia da fonte de cada máquina (colorido, preto e branco ou um quadrado
vazio) e não seguia o tema; o SVG é o mesmo em toda máquina e sai na cor que se
pedir.

Os arquivos moram em `assets/icons/` (só os usados, copiados do
`lucide-static@0.460.0`, licença ISC em `assets/icons/LICENSE`). O traço deles é
`stroke="currentColor"`: aqui o `currentColor` vira a cor pedida e o
`QSvgRenderer` desenha num `QPixmap` (1x e 2x, para tela de alta densidade).
Sem plugin de imagem do Qt: o hook do pacote tira os de SVG
(`empacotamento/hooks/hook-PySide6.QtGui.py`), e só o módulo QtSvg precisa ir.

Para a troca de tema (Task 7): `aplicar` guarda no widget o nome do ícone (a
propriedade dinâmica `icone`) e, se houver, o papel da cor (`icone_cor`, uma
chave da paleta); `reaplicar(raiz)` repinta todos com a paleta de agora.

O item escolhido do menu e o que está sob o mouse têm o texto noutra cor (a
marca, no claro): `papel_cor_ativo` dá ao ícone a cor desse estado. O estado é a
propriedade `ativo` (quem a muda chama `reaplicar`) ou o mouse em cima (um filtro
de eventos repinta ao entrar e ao sair).
"""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QByteArray, QEvent, QObject, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QAbstractButton, QLabel, QWidget

from sigft.app_qt import estilo
from sigft.app_qt import propriedades

_log = logging.getLogger(__name__)

# A raiz do `estilo` (a mesma das fontes): no `.exe` cai em
# `_internal/assets/icons` (o `("assets", "assets")` do `SIG-FT.spec`).
PASTA = Path(estilo.PASTA_ICONES)

# Os que a interface usa; a pasta tem exatamente estes (teste).
NOMES = frozenset({
    "house", "file-plus", "table", "chart-column", "upload", "languages", "list",
    "wrench", "copy", "sparkles", "tag", "folder-kanban", "search",
    "clipboard-check", "bot", "circle-dollar-sign", "key-round", "refresh-cw",
    "folder-open", "file", "trash-2", "play", "square", "settings", "arrow-down",
    "external-link", "sun", "moon", "monitor", "chevrons-left", "chevrons-right",
    "circle-help", "image",
})

TAMANHO_PADRAO = 18
_ESCALAS = (1, 2)
_CACHE: dict[tuple[str, str, int], QIcon] = {}


def _desenhar(svg: bytes, lado: int, escala: int) -> QPixmap:
    renderizador = QSvgRenderer(QByteArray(svg))
    if not renderizador.isValid():
        return QPixmap()
    pixmap = QPixmap(lado * escala, lado * escala)
    pixmap.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(pixmap)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderizador.render(pintor, QRectF(0, 0, lado * escala, lado * escala))
    pintor.end()
    pixmap.setDevicePixelRatio(escala)
    return pixmap


def icone(nome: str, cor: str, tamanho: int = TAMANHO_PADRAO) -> QIcon:
    """O ícone `nome` na cor `cor` ("#RRGGBB"). Nome desconhecido ou arquivo que
    não desenha: `QIcon()` vazio e um aviso no log -- botão sem ícone, e não a
    tela que não abre. A falha também vai para o cache (2026-10-20): sem isso,
    cada `reaplicar` (toda troca de tema, todo item do menu escolhido) repetia o
    aviso."""
    chave = (nome, cor, tamanho)
    if chave in _CACHE:
        return _CACHE[chave]
    _CACHE[chave] = resultado = _montar(nome, cor, tamanho)
    return resultado


def _montar(nome: str, cor: str, tamanho: int) -> QIcon:
    caminho = PASTA / f"{nome}.svg"
    try:
        svg = caminho.read_bytes().replace(b"currentColor", cor.encode("ascii"))
    except OSError:
        _log.warning("icone %r nao encontrado em %s", nome, PASTA)
        return QIcon()
    resultado = QIcon()
    for escala in _ESCALAS:
        pixmap = _desenhar(svg, tamanho, escala)
        if pixmap.isNull():
            _log.warning("icone %r nao desenhou (%s)", nome, caminho)
            return QIcon()
        resultado.addPixmap(pixmap)
    return resultado


def conferir() -> list[str]:
    """Os nomes de `NOMES` que não desenham. É o que o `--smoke` do Release
    confere: um SVG ou o QtSvg fora do `.exe` daria botões em branco, calado."""
    return sorted(nome for nome in NOMES if icone(nome, estilo.paleta_atual()["texto"]).isNull())


def _cor(widget: QWidget) -> str:
    papel = propriedades.ler(widget, "icone_cor")
    destacado = bool(propriedades.ler(widget, "ativo")) or (
        bool(propriedades.ler(widget, "icone_sob_mouse")) and widget.isEnabled())
    if destacado and propriedades.ler(widget, "icone_cor_ativo"):
        papel = propriedades.ler(widget, "icone_cor_ativo")
    if papel:
        cor = estilo.cor_do_papel(papel)
        if cor is not None:
            return cor
        # Papel errado não derruba a tela: o ícone sai na cor do texto do botão.
        _log.warning("icone %r: papel de cor desconhecido %r", propriedades.ler(widget, "icone"), papel)
    return estilo.cor_do_texto_da_variante(propriedades.ler(widget, "variante"))


class _SegueOMouse(QObject):
    """Repinta o ícone do widget ao entrar e ao sair o mouse: o `:hover` da folha
    muda a cor do TEXTO, e o ícone não tem `:hover`. Filho do widget (morre com
    ele)."""

    def eventFilter(self, alvo, evento) -> bool:  # noqa: N802 -- nome do Qt
        tipo = evento.type()
        if tipo in (QEvent.Type.Enter, QEvent.Type.Leave):
            alvo.setProperty("icone_sob_mouse", tipo == QEvent.Type.Enter)
            _pintar(alvo)
        return False


def _pintar(widget: QWidget) -> None:
    nome = propriedades.ler(widget, "icone")
    tamanho = int(propriedades.ler(widget, "icone_tamanho") or TAMANHO_PADRAO)
    desenho = icone(nome, _cor(widget), tamanho)
    if isinstance(widget, QAbstractButton):
        widget.setIcon(desenho)
        widget.setIconSize(QSize(tamanho, tamanho))
    elif isinstance(widget, QLabel):
        widget.setPixmap(desenho.pixmap(tamanho, tamanho))


def aplicar(widget: QWidget, nome: str, *, papel_cor: str | None = None,
            papel_cor_ativo: str | None = None, tamanho: int = TAMANHO_PADRAO) -> QWidget:
    """Põe o ícone `nome` num botão (ao lado do texto, que FICA: teste e leitor
    de tela o leem) ou num rótulo (como desenho). A cor é a do texto da variante
    do botão, ou a da chave `papel_cor` da paleta (`estilo.cor_do_papel`).
    `papel_cor_ativo`: a cor quando o widget está `ativo` ou com o mouse em
    cima (o menu: `estilo.PAPEL_MENU_ESCOLHIDO`). Devolve o widget."""
    widget.setProperty("icone", nome)
    widget.setProperty("icone_cor", papel_cor)
    widget.setProperty("icone_cor_ativo", papel_cor_ativo)
    widget.setProperty("icone_tamanho", tamanho)
    if papel_cor_ativo and not propriedades.ler(widget, "icone_segue_mouse"):
        widget.setProperty("icone_segue_mouse", True)
        widget.installEventFilter(_SegueOMouse(widget))
    _pintar(widget)
    return widget


def reaplicar(raiz: QWidget) -> None:
    """Repinta, com a paleta do tema de agora, todo ícone posto por `aplicar`
    em `raiz` e nos filhos dela. A troca de tema chama isto (Task 7)."""
    for widget in [raiz, *raiz.findChildren(QWidget)]:
        if propriedades.ler(widget, "icone"):
            _pintar(widget)
