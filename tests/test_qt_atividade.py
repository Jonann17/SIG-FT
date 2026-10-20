"""A faixa "Rodando…" (2026-10-20): aparece com a tarefa, some no fim."""
import threading

import pytest

from sigft.app_qt.widgets import atividade
from sigft.app_qt.widgets.module_frame import ModuleFrame


class _Tela(ModuleFrame):
    def __init__(self):
        super().__init__(titulo="Teste")

    def _build_ui(self):
        pass


@pytest.fixture
def tela(qt_interface, qtbot):
    t = _Tela()
    qtbot.addWidget(t)
    t.show()
    return t


def test_relogio():
    assert atividade.relogio(5) == "00:05"
    assert atividade.relogio(125) == "02:05"
    assert atividade.relogio(3725) == "1:02:05"


def test_parada_a_faixa_nao_aparece(tela):
    assert tela.atividade.isHidden()


def test_aparece_com_a_tarefa_e_diz_que_terminou(tela, qtbot):
    liberar = threading.Event()
    tela.iniciar_tarefa(liberar.wait, 5)
    assert tela.atividade.isVisible()
    assert "Rodando" in tela.atividade.rotulo.text()
    liberar.set()
    qtbot.waitUntil(lambda: "Terminou" in tela.atividade.rotulo.text(), timeout=3000)
    assert tela.atividade.rotulo.property("estado") == "ok"


def test_erro_na_tarefa_aparece_na_faixa(tela, qtbot):
    def explode():
        raise ValueError("x")
    tela.iniciar_tarefa(explode)
    qtbot.waitUntil(lambda: "erro" in tela.atividade.rotulo.text(), timeout=3000)
    assert tela.atividade.rotulo.property("estado") == "erro"


def test_progresso_mostra_ficha_x_de_n(tela, qtbot):
    liberar = threading.Event()

    def trabalho():
        tela.informar_progresso(3, 8, "ficha")
        liberar.wait(5)

    tela.iniciar_tarefa(trabalho)
    qtbot.waitUntil(lambda: "Ficha 3 de 8" in tela.atividade.rotulo.text(), timeout=3000)
    liberar.set()
    qtbot.waitUntil(lambda: "Terminou" in tela.atividade.rotulo.text(), timeout=3000)


def test_duas_tarefas_a_faixa_so_fecha_na_ultima(tela, qtbot):
    a, b = threading.Event(), threading.Event()
    tela.iniciar_tarefa(a.wait, 5)
    tela.iniciar_tarefa(b.wait, 5)
    a.set()
    qtbot.wait(200)
    assert "Rodando" in tela.atividade.rotulo.text()
    b.set()
    qtbot.waitUntil(lambda: "Terminou" in tela.atividade.rotulo.text(), timeout=3000)


def test_botao_volta_e_faixa_some_depois(tela, qtbot, monkeypatch):
    monkeypatch.setattr(atividade, "SEGUNDOS_DO_FIM", 0)
    tela.iniciar_tarefa(lambda: None)
    qtbot.waitUntil(lambda: tela.atividade.isHidden(), timeout=3000)
