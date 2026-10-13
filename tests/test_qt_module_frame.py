import threading

import pytest

from sigft.app import backends
from sigft.app_qt.widgets.module_frame import ModuleFrame


class Tela(ModuleFrame):
    def _build_ui(self):
        self.construida = True


def test_monta_cabecalho_conteudo_console(qt_interface, qtbot):
    t = Tela(titulo="Tradutor Técnico")
    qtbot.addWidget(t)
    assert t.construida and t.label_titulo.text() == "Tradutor Técnico"
    assert t.progress_bar is None and t.console is not None


def test_com_progresso(qt_interface, qtbot):
    t = Tela(titulo="x", com_progresso=True)
    qtbot.addWidget(t)
    assert t.progress_bar.maximum() == 1000


def test_embutida_usa_console_do_pai(qt_interface, qtbot):
    pai = Tela(titulo="pai")
    qtbot.addWidget(pai)
    filha = Tela(titulo="filha", embutida=True, console_externo=pai.console)
    qtbot.addWidget(filha)
    assert filha.header is None and filha.console is pai.console


def test_backend_que_falhou_vira_aviso_e_nao_excecao(qt_interface, qtbot, monkeypatch):
    monkeypatch.setattr(backends, "lmr_backend", None)
    monkeypatch.setattr(backends, "falhas", {"lmr_backend": ImportError("sem xlwings")})
    avisos = []
    monkeypatch.setattr("sigft.app_qt.widgets.module_frame.QMessageBox.warning",
                        lambda *a, **k: avisos.append(a[2]))
    t = Tela(titulo="x")
    qtbot.addWidget(t)
    assert t.backend("lmr_backend") is None
    assert "sem xlwings" in avisos[0]
    qtbot.waitUntil(lambda: "sem xlwings" in t.console.toPlainText(), timeout=2000)


def test_tarefa_desabilita_o_botao_no_clique_e_reabilita_no_fim(qt_interface, qtbot):
    from PySide6.QtWidgets import QPushButton
    t = Tela(titulo="x")
    qtbot.addWidget(t)
    botao = QPushButton("Rodar")
    qtbot.addWidget(botao)
    liberar = threading.Event()
    thread = t.iniciar_tarefa(liberar.wait, 5, botao=botao)
    assert not botao.isEnabled()          # desabilitado ANTES de a thread rodar
    assert not thread.daemon              # tarefa da pessoa: o "X" pergunta antes
    liberar.set()
    thread.join(3)
    qtbot.waitUntil(botao.isEnabled, timeout=2000)


def test_excecao_no_worker_vai_para_o_console_e_solta_o_botao(qt_interface, qtbot):
    from PySide6.QtWidgets import QPushButton
    t = Tela(titulo="x")
    qtbot.addWidget(t)
    botao = QPushButton("Rodar")
    qtbot.addWidget(botao)
    thread = t.iniciar_tarefa(lambda: 1 / 0, botao=botao)
    thread.join(3)
    qtbot.waitUntil(lambda: "ZeroDivisionError" in t.console.toPlainText(), timeout=2000)
    qtbot.waitUntil(botao.isEnabled, timeout=2000)
