"""O diário de quedas na interface (2026-10-26): a abertura no `main()`, o
fechamento pela janela e o aviso no topo da Home."""
from __future__ import annotations

import os
import sys
import threading

import pytest
from PySide6.QtWidgets import QMessageBox

from _idioma import ainda_em_portugues, em_idioma
from sigft import _build_info
from sigft.app import idioma
from sigft.app_qt import escolha_de_idioma
from sigft.app_qt import main as qmain
from sigft.app_qt.views import home as home_mod
from sigft.app_qt.views.home import HomeView
from sigft.core import diario, instancia


class _FaultFalso:
    def enable(self, arquivo, all_threads=True) -> None:
        pass

    def disable(self) -> None:
        pass


@pytest.fixture
def diario_em(monkeypatch, tmp_path):
    """Liga o diário numa pasta temporária, com a sessão anterior escrita pelos
    eventos dados (sem os ganchos: o teste é da interface)."""
    monkeypatch.delenv(diario.ENV_DESLIGAR, raising=False)
    monkeypatch.setattr(diario, "faulthandler", _FaultFalso())
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    diario.esquecer()

    def _ligar(*eventos: str):
        texto = "".join(f"2026-10-25 09:00:00 {e}\n" for e in eventos)
        (tmp_path / diario.ARQUIVO).write_text(texto, encoding="utf-8")
        diario.abrir(versao="1.3.1", idioma="pt", pasta=tmp_path, ganchos=False)
        return tmp_path

    yield _ligar
    diario.esquecer()


@pytest.fixture
def janela(qt_interface, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    j = qmain.SIG_FT_App()
    qtbot.addWidget(j)
    return j


def test_nos_testes_o_diario_vem_desligado():
    assert os.environ.get(diario.ENV_DESLIGAR) == "1"
    assert not diario.ligado()


# --- a Home ---------------------------------------------------------------------------

def test_home_sem_aviso_quando_a_ultima_sessao_fechou_normal(qt_interface, qtbot, diario_em):
    diario_em("ABERTURA versao=1.3.0", "FECHAMENTO pela janela")
    home = HomeView()
    qtbot.addWidget(home)
    assert home.aviso_sessao is None


def test_home_avisa_a_queda_e_o_entendido_some_com_ele(qt_interface, qtbot, diario_em):
    diario_em("ABERTURA versao=1.3.0", "ERRO NAO TRATADO (thread principal)")
    home = HomeView()
    qtbot.addWidget(home)
    home.show()
    assert home.aviso_sessao.isVisible()
    assert home.lbl_aviso_sessao.text() == "Da última vez, o SIG-FT fechou de forma inesperada."
    home.btn_entendido.click()
    assert not home.aviso_sessao.isVisible()
    assert diario.aviso_pendente() is None
    outra = HomeView()
    qtbot.addWidget(outra)
    assert outra.aviso_sessao is None


def test_home_avisa_o_encerramento_de_fora(qt_interface, qtbot, diario_em):
    diario_em("ABERTURA versao=1.3.0")
    home = HomeView()
    qtbot.addWidget(home)
    assert home.lbl_aviso_sessao.text() == (
        "Da última vez, o SIG-FT foi encerrado sem fechar a janela "
        "(pelo Gerenciador de Tarefas ou ao desligar o computador).")


def test_abrir_o_registro_abre_a_pasta_de_logs(qt_interface, qtbot, diario_em, monkeypatch):
    chamadas = []
    monkeypatch.setattr(home_mod.pasta_de_logs, "abrir", lambda pai=None: chamadas.append(pai))
    diario_em("ABERTURA versao=1.3.0")
    home = HomeView()
    qtbot.addWidget(home)
    assert home.btn_abrir_registro.toolTip()
    home.btn_abrir_registro.click()
    assert chamadas == [home]


def test_home_sem_aviso_quando_outra_instancia_segura_o_diario(qt_interface, qtbot, diario_em,
                                                               tmp_path):
    # Do fechamento da Task 1: com a trava presa por outra instância, `abrir`
    # devolve None, o diário fica desligado e a Home não avisa nada (a sessão
    # "encerrada de fora" seria a da outra instância, viva).
    from test_diario import _travar_por_fora

    (tmp_path / diario.ARQUIVO).write_text("2026-10-25 09:00:00 ABERTURA versao=1.3.0\n",
                                           encoding="utf-8")
    fd = _travar_por_fora(tmp_path)
    try:
        assert diario.abrir(versao="1.3.1", idioma="pt", pasta=tmp_path, ganchos=False) is None
        home = HomeView()
        qtbot.addWidget(home)
        assert home.aviso_sessao is None
    finally:
        os.close(fd)


@pytest.mark.parametrize("codigo", ["es", "en"])
def test_aviso_traduzido(qt_interface, qtbot, diario_em, codigo):
    diario_em("ABERTURA versao=1.3.0", "ERRO NAO TRATADO (thread principal)")
    with em_idioma(codigo):
        home = HomeView()
        qtbot.addWidget(home)
        assert ainda_em_portugues(home.aviso_sessao, codigo) == set()


# --- a janela -------------------------------------------------------------------------

def test_fechar_a_janela_grava_o_fechamento(janela, diario_em):
    pasta = diario_em()
    janela.fechar_sem_perguntar = True
    janela.close()
    ultima = (pasta / diario.ARQUIVO).read_text(encoding="utf-8").splitlines()[-1]
    assert ultima.endswith("FECHAMENTO pela janela")


def test_fechar_recusado_nao_grava_o_fechamento(janela, diario_em, monkeypatch):
    pasta = diario_em()
    monkeypatch.setattr(instancia, "tarefas_em_andamento", lambda: True)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    janela.close()
    assert "FECHAMENTO" not in (pasta / diario.ARQUIVO).read_text(encoding="utf-8")
    janela.fechar_sem_perguntar = True   # a faxina do qtbot fecha sem perguntar


def test_main_abre_o_diario_depois_do_idioma_e_antes_da_splash(qt_interface, monkeypatch):
    from sigft.core import dados_usuario
    from sigft.core.rpa import navegador

    eventos = []

    class SplashFalsa:
        pronta = type("S", (), {"connect": lambda self, f: None})()

        def __init__(self):
            eventos.append("splash")

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
                        lambda: eventos.append("idioma") or None)
    monkeypatch.setattr(diario, "abrir",
                        lambda **k: eventos.append(("diario", k["versao"], k["idioma"])))
    monkeypatch.setattr(qmain, "SplashScreen", SplashFalsa)
    qmain.main()
    assert eventos == ["qt", "idioma", ("diario", _build_info.VERSAO, idioma.atual()), "splash"]
