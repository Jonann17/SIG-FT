"""O PySide6 não pode gastar referências do `None` a cada chamada (2026-11-02).

O PySide6-Essentials 6.12.0 tira uma referência do `None` em toda chamada que
devolve `None` (`QPainter.setPen`, `setBrush`, `setRenderHint`...): medido,
100 chamadas levam o refcount do `None` 100 para baixo. No Python 3.12+ o
`None` é imortal e nada acontece; no 3.10 e 3.11 (o mínimo do `SIG-FT.bat` é o
3.10), depois de alguns milhares de pinturas o refcount chega a zero e o
processo cai com "Fatal Python error: none_dealloc" -- no `paintEvent` que
estiver pintando na hora. Era a queda do `gw1` do CI em
`test_qt_tela_busca_pmib.py::test_medidas_iguais_as_do_interface_antiga`.

O 6.11 não tem o defeito: o requirements fixa `<6.12` abaixo do Python 3.12.
"""
from __future__ import annotations

import sys

import pytest

pytest.importorskip("PySide6.QtGui")

from PySide6.QtGui import QColor, QImage, QPainter, QPen  # noqa: E402


def test_pintar_nao_gasta_referencias_do_none(qapp):
    imagem = QImage(20, 20, QImage.Format.Format_ARGB32)
    pintor = QPainter(imagem)
    cor, caneta = QColor("#ff0000"), QPen(QColor("#00ff00"), 2)
    antes = sys.getrefcount(None)
    for _ in range(200):
        pintor.setPen(cor)
        pintor.setPen(caneta)
        pintor.setBrush(cor)
    depois = sys.getrefcount(None)
    pintor.end()
    # pequena folga para o que o próprio Python mexer no meio; o defeito tira 600
    assert depois >= antes - 10, f"o PySide6 gastou {antes - depois} referências do None em 600 chamadas"
