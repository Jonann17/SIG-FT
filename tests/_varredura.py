"""A varredura das telas: texto cortado e rolagem de lado (fix round 1, 2026-10-21).

Desde 2026-10-28 mede cada tela e cada aba também com o "Como funciona" aberto,
e passa também pela boas-vindas (a página da primeira abertura, fora do menu).

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


# As páginas que não são módulo: não têm o "Como funciona".
_SEM_COMO_FUNCIONA = ("Home", "BoasVindas")


def _medir(alvo: str, tela, qtbot, achados, rolando, onde: str) -> None:
    """Mede a tela como está e, se ela tem o "Como funciona", de novo com ele
    ABERTO (2026-10-28): os itens tiram altura do conteúdo, e o botão muda de
    texto. Abre sem gravar a preferência e fecha no fim."""
    from sigft.app_qt.widgets.como_funciona import ComoFunciona

    rolando += _rolando(onde, tela)
    achados[alvo] |= cortados(tela)
    blocos_da_tela = tela.findChildren(ComoFunciona)
    # Sem o bloco a varredura não mediria o estado aberto: quem varre tira a
    # variável `SIGFT_SEM_COMO_FUNCIONA` do conftest.
    assert alvo in _SEM_COMO_FUNCIONA or len(blocos_da_tela) == 1, f"{onde}: sem o Como funciona"
    for bloco in blocos_da_tela:
        bloco.alternar(True, gravar=False)
        qtbot.wait(10)
        rolando += _rolando(f"{onde} (como funciona aberto)", tela)
        achados[alvo] |= cortados(tela)
        bloco.alternar(False, gravar=False)


def varrer(janela, qtbot) -> tuple[dict[str, set[str]], list[str]]:
    """Visita a Home, os módulos liberados e a boas-vindas: `(cortados por tela, áreas rolando de lado)`.

    Em cada tela com abas (`abas.Abas`), passa por todas e volta à de antes
    (2026-10-22): o que está numa aba que não abre primeiro também conta. Cada
    tela e cada aba é medida também com o "Como funciona" aberto (2026-10-28)."""
    from sigft.app_qt.widgets.abas import Abas

    achados, rolando = {}, []
    modulos = [m[0] for m in catalogo.MODULOS if m[0] not in catalogo.TELAS_BLOQUEADAS]
    for alvo in ["Home", *modulos, "BoasVindas"]:
        janela.show_home() if alvo == "Home" else janela.show_frame(alvo)
        qtbot.wait(30)
        tela = janela.telas[alvo]
        achados[alvo] = set()
        _medir(alvo, tela, qtbot, achados, rolando, alvo)
        for abas in tela.findChildren(Abas):
            antes = abas.get()
            for nome in abas.abas:
                if nome == antes:
                    continue
                abas.set(nome)
                qtbot.wait(10)
                _medir(alvo, tela, qtbot, achados, rolando, f"{alvo}/{nome}")
            abas.set(antes)
    return achados, rolando
