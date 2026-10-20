"""A marca da barra lateral (logo da GE Vernova + "SIG-FT System"): brilho na
cor primária sob o mouse e clique que volta à Home (sistema visual, 2026-10-20)."""
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QEnterEvent, QFocusEvent
from PySide6.QtWidgets import QApplication, QLabel

from sigft.app_qt import estilo, tema
from sigft.app_qt.widgets import marca as modulo_marca
from sigft.app_qt.widgets.marca import Marca


def _entrar(m):
    m.enterEvent(QEnterEvent(QPointF(), QPointF(), QPointF()))


def test_hover_acende_e_apaga(qapp, qtbot):
    m = Marca(); qtbot.addWidget(m); m.show()
    _entrar(m)
    qtbot.waitUntil(lambda: m.graphicsEffect().blurRadius() >= 17, timeout=1000)
    m.leaveEvent(QEvent(QEvent.Type.Leave))
    qtbot.waitUntil(lambda: m.graphicsEffect().blurRadius() <= 1, timeout=1000)


def test_foco_acende_e_apaga(qapp, qtbot):
    m = Marca(); qtbot.addWidget(m); m.show()
    m.focusInEvent(QFocusEvent(QEvent.Type.FocusIn))
    qtbot.waitUntil(lambda: m.graphicsEffect().blurRadius() >= 17, timeout=1000)
    m.focusOutEvent(QFocusEvent(QEvent.Type.FocusOut))
    qtbot.waitUntil(lambda: m.graphicsEffect().blurRadius() <= 1, timeout=1000)


def test_sem_animacao_do_sistema_acende_na_hora(qapp, qtbot, monkeypatch):
    # Quem desligou as animações no Windows não espera os 150 ms: o brilho
    # vai direto ao valor final.
    monkeypatch.setattr(QApplication, "isEffectEnabled", staticmethod(lambda _efeito: False))
    m = Marca(); qtbot.addWidget(m)
    _entrar(m)
    assert m.graphicsEffect().blurRadius() == modulo_marca.BRILHO_MAXIMO
    m.leaveEvent(QEvent(QEvent.Type.Leave))
    assert m.graphicsEffect().blurRadius() == 0


def test_identidade_e_dica(qapp, qtbot):
    m = Marca(); qtbot.addWidget(m)
    assert m.objectName() == "marca"
    assert m.toolTip() == "Voltar ao início"
    assert "SIG-FT" in m.accessibleName()
    # Os dois logos do pedido ("el logo de sigft y ge"): o símbolo da GE
    # Vernova (imagem) e o nome do SIG-FT, os dois dentro do mesmo botão.
    rotulos = m.findChildren(QLabel)
    assert any(r.pixmap() is not None and not r.pixmap().isNull() for r in rotulos)
    assert any(r.text() == "SIG-FT System" for r in rotulos)
    assert m.cursor().shape() == Qt.CursorShape.PointingHandCursor


def _rgb(cor):
    return cor.red(), cor.green(), cor.blue()


def test_brilho_na_cor_primaria_e_segue_o_tema(qapp, qtbot, monkeypatch):
    monkeypatch.setattr(estilo, "TEMA_ATUAL", "escuro")
    m = Marca(); qtbot.addWidget(m)
    cor = m.graphicsEffect().color()
    assert _rgb(cor) == _rgb(QColor(estilo.paleta_atual()["primaria"]))
    # Meia força no escuro: inteira, a sombra apagava o "GE" vazado do logo.
    assert cor.alpha() == modulo_marca.ALFA_DO_BRILHO["escuro"] < 255
    monkeypatch.setattr(estilo, "TEMA_ATUAL", "claro")
    tema.mudou.emit("claro")
    cor = m.graphicsEffect().color()
    assert _rgb(cor) == _rgb(QColor(estilo.paleta_atual()["primaria"]))
    assert cor.alpha() == modulo_marca.ALFA_DO_BRILHO["claro"]


def test_clique_volta_para_a_home(qt_interface, qtbot, tmp_path, monkeypatch):
    from sigft.app_qt import main as qmain
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "k.json"))
    j = qmain.SIG_FT_App(); qtbot.addWidget(j)
    j.show_frame("Translator")
    j.marca.click()
    assert j.pilha.currentWidget() is j.telas["Home"]
