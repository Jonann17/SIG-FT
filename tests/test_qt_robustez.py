import threading

import pytest
from PySide6.QtWidgets import QPushButton

from sigft.app import backends
from sigft.app_qt import interface


def test_instalar_fora_da_thread_da_interface_recusa(qt_interface, monkeypatch):
    monkeypatch.setattr(interface, "_ponte", None)
    erros = []

    def tentar():
        try:
            interface.instalar()
        except RuntimeError as erro:
            erros.append(str(erro))

    t = threading.Thread(target=tentar, daemon=True)
    t.start()
    t.join(3)
    assert erros and "thread da interface" in erros[0]


def test_console_volta_a_agendar_depois_de_falha(qt_interface, qtbot, monkeypatch):
    from sigft.app_qt.widgets.console import ConsoleFrame
    c = ConsoleFrame()
    qtbot.addWidget(c)
    original = interface.na_interface

    def falha_uma_vez(*a, **k):
        monkeypatch.setattr(interface, "na_interface", original)
        raise RuntimeError("canal fechado")

    monkeypatch.setattr(interface, "na_interface", falha_uma_vez)
    c.log("perdida")
    c.log("chega")
    qtbot.waitUntil(lambda: "chega" in c.toPlainText(), timeout=2000)


def test_botao_destruido_no_fim_da_tarefa_nao_vira_traceback(qt_interface, qtbot, capsys):
    from sigft.app_qt.widgets.module_frame import ModuleFrame

    class Tela(ModuleFrame):
        def _build_ui(self):
            pass

    tela = Tela(titulo="x")
    qtbot.addWidget(tela)
    botao = QPushButton("Rodar")
    liberar = threading.Event()
    thread = tela.iniciar_tarefa(liberar.wait, 5, botao=botao)
    botao.deleteLater()
    qtbot.wait(50)
    liberar.set()
    thread.join(3)
    qtbot.wait(100)
    assert "Traceback" not in capsys.readouterr().err


def test_exigir_nome_desconhecido_e_erro_de_programacao():
    with pytest.raises(KeyError, match="pdm_backnd"):
        backends.exigir("pdm_backnd")


def test_mensagem_nomeia_o_modulo(monkeypatch):
    monkeypatch.setattr(backends, "falhas", {"lmr_backend": TypeError("x")})
    monkeypatch.setattr(backends, "lmr_backend", None)
    with pytest.raises(backends.BackendIndisponivel, match=r"\(módulo lmr_backend\)"):
        backends.exigir("lmr_backend")


def test_traducao_pt_br_instalada(qt_interface):
    from PySide6.QtWidgets import QApplication

    from sigft.app_qt import main as qmain
    assert qmain._instalar_traducao(QApplication.instance()) is True
    assert QApplication.translate("QPlatformTheme", "Cancel") == "Cancelar"


def test_tela_que_falha_ao_montar_vira_tela_de_erro(qt_interface, qtbot, tmp_path, monkeypatch):
    from sigft.app_qt import main as qmain
    from sigft.app_qt.views.nao_migrada import TelaComErro
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))

    def quebra(parent, controller):
        raise ValueError("faltou coluna")

    monkeypatch.setitem(qmain.TELAS, "Analyzer", quebra)
    janela = qmain.SIG_FT_App()
    qtbot.addWidget(janela)
    janela.show_frame("Analyzer")
    assert isinstance(janela.pilha.currentWidget(), TelaComErro)
    assert "faltou coluna" in janela.pilha.currentWidget().mensagem.text()
    assert "Analyzer" not in janela.telas  # a próxima visita tenta de novo


def test_tela_que_falha_ensina_a_abrir_a_antiga(qt_interface, qtbot):
    """Revisão final: uma tela que não monta não tem outra saída hoje."""
    from sigft.app_qt.views.nao_migrada import TelaComErro
    from sigft.core.interface_antiga import comando_da_interface_antiga

    tela = TelaComErro("Analyzer", ValueError("faltou coluna"))
    qtbot.addWidget(tela)
    assert comando_da_interface_antiga() in tela.mensagem.text()
