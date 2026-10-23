"""A varredura das telas: texto cortado e rolagem de lado (fix round 1, 2026-10-21).

Era de `tests/test_qt_letra.py` (letra grande); desde 2026-10-22 também serve à
varredura dos idiomas (`tests/test_qt_idioma_varredura.py`).
"""
from __future__ import annotations

from sigft.app_qt import catalogo
from sigft.app_qt.widgets import blocos


def cortados(tela) -> set[str]:
    """Os textos (botão, rótulo de uma linha, caixa) mais estreitos que o pedido."""
    from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton

    achados = set()
    for tipo in (QPushButton, QLabel, QCheckBox):
        for w in tela.findChildren(tipo):
            if not w.isVisible() or not w.text().strip():
                continue
            if isinstance(w, QLabel) and (w.wordWrap() or isinstance(w, blocos.RotuloElidido)):
                continue
            if w.width() < w.sizeHint().width():
                achados.add(w.text())
    return achados


def _rolando(alvo: str, tela) -> list[str]:
    from PySide6.QtWidgets import QAbstractScrollArea

    return [f"{alvo}:{type(area).__name__}" for area in [tela, *tela.findChildren(QAbstractScrollArea)]
            if isinstance(area, QAbstractScrollArea) and area.isVisible()
            and area.horizontalScrollBar().isVisible()]


def varrer(janela, qtbot) -> tuple[dict[str, set[str]], list[str]]:
    """Visita a Home e os módulos liberados: `(cortados por tela, áreas rolando de lado)`.

    Em cada tela com abas (`abas.Abas`), passa por todas e volta à de antes
    (2026-10-22): o que está numa aba que não abre primeiro também conta."""
    from sigft.app_qt.widgets.abas import Abas

    achados, rolando = {}, []
    for alvo in ["Home", *(m[0] for m in catalogo.MODULOS if m[0] not in catalogo.TELAS_BLOQUEADAS)]:
        janela.show_home() if alvo == "Home" else janela.show_frame(alvo)
        qtbot.wait(30)
        tela = janela.telas[alvo]
        rolando += _rolando(alvo, tela)
        achados[alvo] = cortados(tela)
        for abas in tela.findChildren(Abas):
            antes = abas.get()
            for nome in abas.abas:
                if nome == antes:
                    continue
                abas.set(nome)
                qtbot.wait(10)
                rolando += _rolando(f"{alvo}/{nome}", tela)
                achados[alvo] |= cortados(tela)
            abas.set(antes)
    return achados, rolando
