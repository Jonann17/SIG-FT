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


def test_menu_marca_a_tela_aberta(app_qt):
    # Sistema visual (2026-10-20): a folha pinta o item `ativo` com a marca a 25%.
    assert app_qt.botao_home.property("ativo") is True
    app_qt.show_frame("Analyzer")
    assert app_qt.botoes_menu["Analyzer"].property("ativo") is True
    assert not app_qt.botao_home.property("ativo")
    assert [a for a, b in app_qt.botoes_menu.items() if b.property("ativo")] == ["Analyzer"]
    app_qt.show_home()
    assert app_qt.botao_home.property("ativo") is True
    assert not app_qt.botoes_menu["Analyzer"].property("ativo")


def test_tela_nao_registrada_mostra_aviso(app_qt, monkeypatch):
    # Desde a E4.10 todas as telas do menu estão em `TELAS`; o aviso continua
    # sendo o caminho de uma chave sem fábrica.
    from sigft.app_qt.views.nao_migrada import TelaNaoMigrada
    monkeypatch.delitem(qmain.TELAS, "AutoSpec")
    app_qt.show_frame("AutoSpec")
    assert isinstance(app_qt.telas["AutoSpec"], TelaNaoMigrada)


def test_tela_bloqueada_nao_abre_e_botao_desabilitado(app_qt):
    app_qt.show_frame("CorrecaoPDM")
    assert "CorrecaoPDM" not in app_qt.telas
    assert not app_qt.botoes_menu["CorrecaoPDM"].isEnabled()


def test_barra_lateral_tem_a_largura_total_da_do_interface_antiga(qt_interface, app_qt, qtbot):
    # CTkScrollableFrame(width=260) + barra de rolagem (16) + 1 de borda: o
    # conteúdo começa em x=277 na captura da interface antiga. Os botões ficam com os 246 de
    # antes: os 7 px a mais são a faixa (vazia) onde a interface antiga desenha a rolagem.
    from sigft.app_qt import estilo

    anterior = qt_interface.styleSheet()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())  # sem ela a área ganha moldura de 1 px
    try:
        # [2026-11-04] Alta o bastante para o menu (15 telas, 911 px) não rolar: com a
        # rolagem, os botões perdem os 10 px da barra dela.
        app_qt.resize(1280, 1000)
        app_qt.show()
        qtbot.waitExposed(app_qt)
        barra = app_qt.centralWidget().layout().itemAt(0).widget()
        assert estilo.LARGURA_BARRA_LATERAL == 277
        assert barra.width() == 277
        assert app_qt.pilha.mapTo(app_qt, app_qt.pilha.rect().topLeft()).x() == 277
        assert app_qt.botoes_menu["CriaFichas"].width() == 246
    finally:
        qt_interface.setStyleSheet(anterior)


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
    monkeypatch.chdir(tmp_path)  # o smoke grava o relatório no diretório de trabalho
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    monkeypatch.setattr(qmain.backends, "carregar_todos", lambda **k: None)
    assert qmain._smoke() == 0


def test_smoke_relata_backend_que_nao_carregou(qt_interface, monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
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


def test_smoke_nao_pergunta_nada_mesmo_com_thread_comum_viva(qt_interface, monkeypatch, tmp_path):
    """Offscreen ninguem responde o "Fechar o SIG-FT?": o --smoke travava (exit 124)."""
    import threading

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    monkeypatch.setattr(qmain.backends, "carregar_todos", lambda **k: None)

    def nao_deve_perguntar(*a, **k):
        raise AssertionError("o --smoke nao pode abrir o QMessageBox.question")

    monkeypatch.setattr(qmain.QMessageBox, "question", nao_deve_perguntar)
    liberar = threading.Event()
    viva = threading.Thread(target=liberar.wait, name="tarefa:presa")  # comum, de proposito
    viva.start()
    try:
        assert qmain._smoke() == 0
    finally:
        liberar.set()
        viva.join(3)


def test_main_prepara_dados_e_navegador_antes_da_splash(qt_interface, monkeypatch, capsys):
    """Mesmos passos de partida do app antigo, na mesma ordem."""
    from sigft.core import dados_usuario, instancia
    from sigft.core.rpa import navegador

    eventos = []

    class SplashFalsa:
        pronta = type("S", (), {"connect": lambda self, f: eventos.append("conectou")})()

        def __init__(self):
            eventos.append("splash")

        def show(self):
            eventos.append("show")

        def carregar(self):
            eventos.append("carregar")

    monkeypatch.setattr(instancia, "preparar", lambda: eventos.append("preparar"))
    monkeypatch.setattr(instancia, "encerrar", lambda codigo=0: eventos.append(("encerrar", codigo)))
    monkeypatch.setattr(dados_usuario, "migrar_se_preciso",
                        lambda: eventos.append("migrou") or ["api_config.json"])
    monkeypatch.setattr(navegador, "preparar_ambiente_do_rpa",
                        lambda: eventos.append("navegador") or None)
    monkeypatch.setattr(qmain, "_preparar_qt",
                        lambda: eventos.append("qt") or type(
                            "A", (), {"exec": lambda self: eventos.append("exec")})())
    monkeypatch.setattr(qmain, "SplashScreen", SplashFalsa)
    qmain.main()
    assert eventos.index("migrou") < eventos.index("splash")
    assert eventos.index("navegador") < eventos.index("splash")
    # 2026-10-20: o tema guardado vale antes da splash (ela abre na cor dele).
    assert eventos.index("qt") < eventos.index("splash")
    assert eventos[-1] == ("encerrar", 0)
    saida = capsys.readouterr().out
    assert "[SIG-FT] Configuracao importada para a pasta de dados: api_config.json" in saida
    assert "[SIG-FT] Nenhum Chrome/Edge encontrado." in saida


def test_smoke_nao_deixa_a_janela_viva(qt_interface, monkeypatch, tmp_path):
    # Release 1.3.0 (2026-10-23): cada smoke deixava a janela principal inteira
    # viva (~700 peças). Com várias na mesma sessão de testes, cada troca de folha
    # do app repintava todas, os testes ficavam lentos e, no Windows, o processo
    # caiu pintando uma peça de uma janela dessas.
    from PySide6.QtWidgets import QApplication

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    monkeypatch.setattr(qmain.backends, "carregar_todos", lambda **k: None)
    antes = len(QApplication.allWidgets())
    assert qmain._smoke() == 0
    assert len(QApplication.allWidgets()) <= antes
