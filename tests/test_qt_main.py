import json

import pytest

from sigft.app_qt import main as qmain


@pytest.fixture
def app_qt(qt_interface, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    janela = qmain.SIG_FT_App()
    qtbot.addWidget(janela)
    return janela


def test_abre_na_home_e_cria_telas_so_na_visita(app_qt):
    assert list(app_qt.telas) == ["Home"]
    app_qt.show_frame("Analyzer")
    assert "Analyzer" in app_qt.telas
    assert app_qt.pilha.currentWidget() is app_qt.telas["Analyzer"]


def test_tela_nao_registrada_mostra_aviso(app_qt):
    from sigft.app_qt.views.nao_migrada import TelaNaoMigrada
    app_qt.show_frame("AutoSpec")
    assert isinstance(app_qt.telas["AutoSpec"], TelaNaoMigrada)


def test_tela_bloqueada_nao_abre_e_botao_desabilitado(app_qt):
    app_qt.show_frame("CorrecaoPDM")
    assert "CorrecaoPDM" not in app_qt.telas
    assert not app_qt.botoes_menu["CorrecaoPDM"].isEnabled()


def test_titulo_com_versao(app_qt):
    from sigft import _build_info
    assert f"v{_build_info.VERSAO}" in app_qt.windowTitle()


def test_salvar_chaves_preserva_o_resto_do_arquivo(app_qt, tmp_path):
    arquivo = tmp_path / "api_config.json"
    arquivo.write_text(json.dumps({"_modelos_ia": {"global": "x"}, "GEMINI": "velha"}), encoding="utf-8")
    app_qt.save_keys({"GEMINI": "nova"})
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    assert dados == {"_modelos_ia": {"global": "x"}, "GEMINI": "nova"}
    assert app_qt.get_key("GEMINI") == "nova"


def test_fechar_com_tarefa_pergunta_antes(app_qt, monkeypatch):
    from sigft.core import instancia
    perguntas = []
    monkeypatch.setattr(instancia, "tarefas_em_andamento", lambda: ["tarefa:x"])
    monkeypatch.setattr(qmain.QMessageBox, "question",
                        lambda *a, **k: perguntas.append(a[2]) or qmain.QMessageBox.StandardButton.No)
    app_qt.show()
    app_qt.close()
    assert perguntas and app_qt.isVisible()


def test_smoke_monta_e_sai_com_zero(qt_interface, monkeypatch, tmp_path):
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    monkeypatch.setattr(qmain.backends, "carregar_todos", lambda **k: None)
    assert qmain._smoke() == 0


def test_smoke_relata_backend_que_nao_carregou(qt_interface, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))

    def carregar(ao_falhar=None, **_):
        ao_falhar("Teste", ImportError("x"))

    monkeypatch.setattr(qmain.backends, "carregar_todos", carregar)
    assert qmain._smoke() == 0
    assert "[smoke] AVISO: o backend 'Teste' nao carregou: ImportError: x" in capsys.readouterr().out


@pytest.mark.parametrize("erro", [SystemExit(1), RuntimeError("quebrou")])
def test_splash_sempre_emite_pronta_mesmo_se_o_carregamento_morre(qt_interface, qtbot, monkeypatch, erro):
    def carregar(**_):
        raise erro

    monkeypatch.setattr(qmain.backends, "carregar_todos", carregar)
    splash = qmain.SplashScreen()
    qtbot.addWidget(splash)
    with qtbot.waitSignal(splash.pronta, timeout=3000):
        splash.carregar()
