"""O Qt roda na suíte sem display (QT_QPA_PLATFORM=offscreen)."""
import os

from PySide6.QtWidgets import QLabel


def test_plataforma_offscreen():
    assert os.environ.get("QT_QPA_PLATFORM") == "offscreen"


def test_widget_monta_sem_display(qtbot):
    rotulo = QLabel("SIG-FT")
    qtbot.addWidget(rotulo)
    rotulo.show()
    assert rotulo.text() == "SIG-FT"
