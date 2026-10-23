"""A janela principal abre maximizada (pedido do Jonathan, 2026-10-23): ocupa a
tela inteira, com a barra de título e a barra de tarefas do Windows à vista. O
"restaurar" volta ao tamanho de antes (1280x850)."""
from __future__ import annotations

from sigft.app_qt import escolha_de_idioma
from sigft.app_qt import main as qmain
from sigft.core import instancia


def test_main_abre_a_janela_principal_maximizada(qt_interface, monkeypatch):
    from sigft.core import dados_usuario
    from sigft.core.rpa import navegador

    abrir = []
    mostrada = []

    class SplashFalsa:
        pronta = type("S", (), {"connect": lambda self, f: abrir.append(f)})()

        def show(self):
            pass

        def carregar(self):
            pass

        def close(self):
            pass

    class JanelaFalsa:
        def show(self):
            mostrada.append("normal")

        def showMaximized(self):  # noqa: N802 -- nome do Qt
            mostrada.append("maximizada")

    app_falso = type("A", (), {"exec": lambda self: None})()
    monkeypatch.setattr(instancia, "preparar", lambda: None)
    monkeypatch.setattr(instancia, "encerrar", lambda codigo=0: None)
    monkeypatch.setattr(dados_usuario, "migrar_se_preciso", lambda: [])
    monkeypatch.setattr(navegador, "preparar_ambiente_do_rpa", lambda: None)
    monkeypatch.setattr(qmain, "_preparar_qt", lambda: app_falso)
    monkeypatch.setattr(escolha_de_idioma, "perguntar_na_abertura", lambda: None)
    monkeypatch.setattr(qmain, "SplashScreen", SplashFalsa)
    monkeypatch.setattr(qmain, "SIG_FT_App", JanelaFalsa)
    monkeypatch.setattr(qmain, "_redesenhar_saudacao", lambda principal: None)
    monkeypatch.setattr(qmain.nome_da_pessoa, "perguntar_na_abertura", lambda *a, **k: None)
    qmain.main()
    abrir[0]()
    assert mostrada == ["maximizada"]


def test_restaurar_volta_ao_tamanho_de_sempre(qt_interface, qtbot):
    janela = qmain.SIG_FT_App()
    qtbot.addWidget(janela)
    assert (janela.width(), janela.height()) == (1280, 850)
