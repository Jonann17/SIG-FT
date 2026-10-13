"""Medidas da janela de Excel travado (RetryLockDialog) contra
as do CustomTkinter (sigft/app/widgets/dialogs.py), medidas com winfo_* numa
captura Xvfb (capturas/e4.45): lá o texto vem com pady=20 e `expand=True` e os
botões com pady=(0, 20). A pausa de login tem o teste dela em
`test_qt_tela_copia_fichas.py::test_medidas_da_pausa_de_login`."""
import threading

from sigft.app.textos_dialogos import MSG_EXCEL_BLOQUEADO
from sigft.app_qt import estilo
from sigft.app_qt.widgets import dialogs


def _geo(dlg, w):
    p = w.mapTo(dlg, w.rect().topLeft())
    return p.x(), p.y(), w.width(), w.height()


def _mostrar(qt_interface, qtbot, dlg):
    qtbot.addWidget(dlg)
    dlg.show()
    qtbot.waitExposed(dlg)


def test_excel_travado(qt_interface, qtbot):
    anterior = qt_interface.styleSheet()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    try:
        d = dialogs.RetryLockDialog(None, mensagem=MSG_EXCEL_BLOQUEADO, evento_espera=threading.Event(),
                                    resultado={})
        _mostrar(qt_interface, qtbot, d)
        assert (d.width(), d.height()) == (450, 200)
        assert _geo(d, d.botao_repetir) == (65, 140, 150, 40)
        assert _geo(d, d.botao_cancelar) == (235, 140, 150, 40)
        x, y, w, h = _geo(d, d.rotulo)
        assert y >= 20 and y + h <= 120 and abs(y + h / 2 - 70) <= 1
    finally:
        qt_interface.setStyleSheet(anterior)
