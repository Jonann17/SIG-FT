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
"""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QAbstractButton, QLabel, QWidget

from sigft.app_qt import estilo

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
    "external-link", "sun", "moon", "monitor",
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
    tela que não abre."""
    chave = (nome, cor, tamanho)
    if chave in _CACHE:
        return _CACHE[chave]
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
    _CACHE[chave] = resultado
    return resultado


def conferir() -> list[str]:
    """Os nomes de `NOMES` que não desenham. É o que o `--smoke` do Release
    confere: um SVG ou o QtSvg fora do `.exe` daria botões em branco, calado."""
    return sorted(nome for nome in NOMES if icone(nome, estilo.paleta_atual()["texto"]).isNull())


def _cor(widget: QWidget) -> str:
    papel = widget.property("icone_cor")
    if papel:
        return estilo.paleta_atual()[papel]
    return estilo.cor_do_texto_da_variante(widget.property("variante"))


def _pintar(widget: QWidget) -> None:
    nome = widget.property("icone")
    tamanho = int(widget.property("icone_tamanho") or TAMANHO_PADRAO)
    desenho = icone(nome, _cor(widget), tamanho)
    if isinstance(widget, QAbstractButton):
        widget.setIcon(desenho)
        widget.setIconSize(QSize(tamanho, tamanho))
    elif isinstance(widget, QLabel):
        widget.setPixmap(desenho.pixmap(tamanho, tamanho))


def aplicar(widget: QWidget, nome: str, *, papel_cor: str | None = None,
            tamanho: int = TAMANHO_PADRAO) -> QWidget:
    """Põe o ícone `nome` num botão (ao lado do texto, que FICA: teste e leitor
    de tela o leem) ou num rótulo (como desenho). A cor é a do texto da variante
    do botão, ou a da chave `papel_cor` da paleta. Devolve o widget."""
    widget.setProperty("icone", nome)
    widget.setProperty("icone_cor", papel_cor)
    widget.setProperty("icone_tamanho", tamanho)
    _pintar(widget)
    return widget


def reaplicar(raiz: QWidget) -> None:
    """Repinta, com a paleta do tema de agora, todo ícone posto por `aplicar`
    em `raiz` e nos filhos dela. A troca de tema chama isto (Task 7)."""
    for widget in [raiz, *raiz.findChildren(QWidget)]:
        if widget.property("icone"):
            _pintar(widget)
