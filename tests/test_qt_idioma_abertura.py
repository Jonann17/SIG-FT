"""O idioma na abertura e na engrenagem (2026-10-22): a pergunta da primeira
abertura, a seção Idioma da janela Configuração, o reinício e a tradução do Qt."""
import os
import sys

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from sigft.app import idioma
from sigft.app_qt import escolha_de_idioma, reinicio
from sigft.app_qt import main as qmain
from sigft.core import instancia


@pytest.fixture
def prefs(tmp_path, monkeypatch):
    monkeypatch.setattr(idioma, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    return tmp_path / "p.json"


# --- a pergunta da primeira abertura -------------------------------------------------

def test_a_caixa_tem_os_tres_idiomas_cada_um_no_seu(qt_interface, qtbot):
    caixa = escolha_de_idioma.PerguntaDoIdioma()
    qtbot.addWidget(caixa)
    assert [b.text() for b in caixa.botoes.values()] == ["Español", "Português", "English"]
    assert caixa.windowTitle() == "Idioma / Language"
    caixa.botoes["en"].click()
    assert caixa.escolha == "en"
    assert caixa.result() == caixa.DialogCode.Accepted.value


def test_primeira_abertura_pergunta_e_guarda(prefs, monkeypatch):
    monkeypatch.delenv(escolha_de_idioma.ENV_DESLIGAR, raising=False)
    assert escolha_de_idioma.perguntar_na_abertura(abrir=lambda: "es") == "es"
    assert idioma.escolhido() == "es"


def test_ja_escolhido_nao_pergunta(prefs, monkeypatch):
    monkeypatch.delenv(escolha_de_idioma.ENV_DESLIGAR, raising=False)
    idioma.guardar("en")
    perguntas = []
    assert escolha_de_idioma.perguntar_na_abertura(abrir=lambda: perguntas.append(1)) is None
    assert perguntas == []


def test_fechar_sem_escolher_e_portugues_e_pergunta_de_novo(prefs, monkeypatch):
    monkeypatch.delenv(escolha_de_idioma.ENV_DESLIGAR, raising=False)
    assert escolha_de_idioma.perguntar_na_abertura(abrir=lambda: None) is None
    assert idioma.escolhido() is None


def test_nos_testes_e_no_smoke_nunca_pergunta(prefs, monkeypatch):
    assert escolha_de_idioma.perguntar_na_abertura(abrir=lambda: "es") is None   # o conftest desliga
    monkeypatch.delenv(escolha_de_idioma.ENV_DESLIGAR, raising=False)
    monkeypatch.setattr(sys, "argv", ["frontend.py", "--smoke"])
    assert escolha_de_idioma.perguntar_na_abertura(abrir=lambda: "es") is None


def test_main_pergunta_o_idioma_antes_da_splash(qt_interface, monkeypatch):
    from sigft.core import dados_usuario
    from sigft.core.rpa import navegador

    eventos = []

    class SplashFalsa:
        pronta = type("S", (), {"connect": lambda self, f: None})()

        def __init__(self):
            eventos.append(("splash", idioma.atual()))

        def show(self):
            pass

        def carregar(self):
            pass

    app_falso = type("A", (), {"exec": lambda self: None})()
    monkeypatch.setattr(instancia, "preparar", lambda: None)
    monkeypatch.setattr(instancia, "encerrar", lambda codigo=0: None)
    monkeypatch.setattr(dados_usuario, "migrar_se_preciso", lambda: [])
    monkeypatch.setattr(navegador, "preparar_ambiente_do_rpa", lambda: None)
    monkeypatch.setattr(qmain, "_preparar_qt", lambda: eventos.append("qt") or app_falso)
    monkeypatch.setattr(escolha_de_idioma, "perguntar_na_abertura",
                        lambda: eventos.append("idioma") or "en")
    monkeypatch.setattr(qmain, "_aplicar_idioma", lambda app, codigo: idioma.definir(codigo))
    monkeypatch.setattr(qmain, "SplashScreen", SplashFalsa)
    qmain.main()
    assert eventos == ["qt", "idioma", ("splash", "en")]


# --- a tradução do Qt e a linha de comando ------------------------------------------

@pytest.mark.parametrize("codigo, cancelar", [("pt", "Cancelar"), ("es", "Cancelar"), ("en", "Cancel")])
def test_botoes_do_qt_no_idioma(qt_interface, codigo, cancelar):
    app = QApplication.instance()
    try:
        idioma.definir(codigo)
        assert qmain._instalar_traducao(app) is (codigo != "en")
        assert QApplication.translate("QPlatformTheme", "Cancel") == cancelar
    finally:
        idioma.definir("pt")
        qmain._instalar_traducao(app)


def test_preparar_qt_usa_o_idioma_da_linha_de_comando(qt_interface, prefs):
    app = QApplication.instance()
    folha = app.styleSheet()
    try:
        qmain._preparar_qt("escuro", "normal", "en")
        assert idioma.atual() == "en"
        assert idioma.escolhido() is None, "a abertura só lê"
    finally:
        idioma.definir("pt")
        qmain._instalar_traducao(app)
        app.setStyleSheet(folha)


def test_opcao_idioma_da_linha_de_comando():
    assert qmain._opcao_da_linha_de_comando(["f", "--smoke", "--idioma", "es"], "--idioma") == "es"


@pytest.mark.parametrize("codigo", ["es", "en"])
def test_smoke_em_outro_idioma(qt_interface, monkeypatch, tmp_path, codigo):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    monkeypatch.setattr(qmain.backends, "carregar_todos", lambda **k: None)
    monkeypatch.setattr(sys, "argv", ["frontend.py", "--smoke", "--idioma", codigo])
    try:
        assert qmain._smoke() == 0
        assert idioma.atual() == codigo
    finally:
        idioma.definir("pt")
        qmain._instalar_traducao(QApplication.instance())


def test_as_pontas_da_traducao_do_qt_andam_juntas():
    """O que o `main` carrega, o que a conferência do pacote procura e o que o
    `SIG-FT.spec` deixa no pacote são as mesmas traduções."""
    import pathlib

    from sigft.app import conferencia

    assert set(qmain.LOCALE_DO_QT.values()) == {local for local, _c in conferencia.TRADUCOES_DA_QT}
    spec = (pathlib.Path(qmain.__file__).resolve().parents[2] / "SIG-FT.spec").read_text(encoding="utf-8")
    for local in qmain.LOCALE_DO_QT.values():
        assert f'"qtbase_{local}.qm"' in spec


# --- o reinício ----------------------------------------------------------------------

def test_comando_para_reabrir():
    import os

    # `--tema`, `--letra` e `--idioma` (com o valor, separado ou com `=`) só valem no smoke e
    # nas capturas: a instância nova abre no que está guardado, senão o `--idioma xx` passado
    # à mão ganharia do idioma que a pessoa acabou de escolher (revisão da Task 3, 2026-10-22).
    assert reinicio.comando_para_reabrir(congelado=True, executavel=r"C:\SIG-FT\SIG-FT.exe",
                                         argv=[r"C:\SIG-FT\SIG-FT.exe", "--tema", "claro", "--outro"],
                                         raiz=r"C:\SIG-FT") == [r"C:\SIG-FT\SIG-FT.exe", "--outro"]
    assert reinicio.comando_para_reabrir(congelado=False, executavel="/venv/bin/python",
                                         argv=["/repo/sigft/app_qt/main.py", "--smoke", "--letra", "grande",
                                               "--idioma=es", "--idioma", "en", "--tema=escuro", "--x"],
                                         raiz="/repo") == ["/venv/bin/python",
                                                           os.path.join("/repo", "frontend.py"), "--x"]


def _popen_capturado(monkeypatch):
    chamadas = []
    monkeypatch.setattr(reinicio.subprocess, "Popen", lambda comando, **opcoes: chamadas.append(opcoes))
    return chamadas


def test_no_exe_a_instancia_nova_nasce_com_ambiente_proprio(monkeypatch):
    # PyInstaller 6: para abrir uma cópia independente do mesmo `.exe`, o filho
    # precisa de `PYINSTALLER_RESET_ENVIRONMENT=1`, senão herda a pasta temporária
    # do pai, que some quando o pai fecha (revisão da Task 3).
    chamadas = _popen_capturado(monkeypatch)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    reinicio._abrir_processo(["SIG-FT.exe"], "/pasta")
    [opcoes] = chamadas
    assert opcoes["env"]["PYINSTALLER_RESET_ENVIRONMENT"] == "1"
    assert opcoes["env"]["PATH"] == os.environ["PATH"]


def test_do_codigo_fonte_herda_o_ambiente(monkeypatch):
    chamadas = _popen_capturado(monkeypatch)
    monkeypatch.delattr(sys, "frozen", raising=False)
    reinicio._abrir_processo(["python", "frontend.py"], "/pasta")
    [opcoes] = chamadas
    assert "env" not in opcoes


class _Janela:
    def __init__(self):
        self.fechar_sem_perguntar = False
        self.fechada = False

    def close(self):
        self.fechada = True


def test_reiniciar_abre_outra_e_fecha_esta(monkeypatch):
    monkeypatch.delenv(reinicio.ENV_DESLIGAR, raising=False)
    abertos = []
    monkeypatch.setattr(reinicio, "_abrir_processo", lambda comando, pasta: abertos.append((comando, pasta)))
    monkeypatch.setattr(instancia, "tarefas_em_andamento", lambda: [])
    janela = _Janela()
    assert reinicio.reiniciar(janela) is True
    [(comando, pasta)] = abertos
    assert comando[0] == sys.executable
    assert comando[1] == os.path.join(qmain._RAIZ, "frontend.py")
    assert pasta == qmain._RAIZ
    assert janela.fechar_sem_perguntar and janela.fechada


def test_reiniciar_com_tarefa_rodando_recusa(qt_interface, monkeypatch):
    monkeypatch.delenv(reinicio.ENV_DESLIGAR, raising=False)
    abertos, avisos = [], []
    monkeypatch.setattr(reinicio, "_abrir_processo", lambda *a: abertos.append(a))
    monkeypatch.setattr(instancia, "tarefas_em_andamento", lambda: ["robo"])
    monkeypatch.setattr(QMessageBox, "information", lambda pai, titulo, texto: avisos.append(texto))
    janela = _Janela()
    assert reinicio.reiniciar(janela) is False
    assert abertos == [] and not janela.fechada
    assert avisos == [reinicio.MSG_TAREFA_EM_ANDAMENTO]


def test_reiniciar_que_nao_abre_avisa_e_nao_fecha(qt_interface, monkeypatch):
    monkeypatch.delenv(reinicio.ENV_DESLIGAR, raising=False)
    avisos = []

    def falha(*_a):
        raise OSError("sem permissão")

    monkeypatch.setattr(reinicio, "_abrir_processo", falha)
    monkeypatch.setattr(instancia, "tarefas_em_andamento", lambda: [])
    monkeypatch.setattr(QMessageBox, "warning", lambda pai, titulo, texto: avisos.append(texto))
    janela = _Janela()
    assert reinicio.reiniciar(janela) is False
    assert not janela.fechada and "sem permissão" in avisos[0]


def test_nos_testes_nunca_reinicia(monkeypatch):
    abertos = []
    monkeypatch.setattr(reinicio, "_abrir_processo", lambda *a: abertos.append(a))
    assert reinicio.reiniciar(_Janela()) is False      # o conftest desliga
    assert abertos == []


def test_aplicar_idioma_de_verdade_liga_traducao_e_folga(qt_interface):
    """O caminho real da primeira abertura (revisao final, 2026-10-22): escolher es
    liga a traducao do Qt e o vigia de largura de `letra`, sem precisar reiniciar."""
    from sigft.app_qt import letra
    app = QApplication.instance()
    try:
        qmain._aplicar_idioma(app, "es")
        assert idioma.atual() == "es"
        assert letra._vigia
        assert QApplication.translate("QPlatformTheme", "Cancel") == "Cancelar"
    finally:
        qmain._aplicar_idioma(app, "pt")
        letra.reavaliar_vigia()
