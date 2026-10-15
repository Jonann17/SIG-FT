# -*- coding: utf-8 -*-
"""Fechar a janela ENCERRA o processo -- o SIG-FT fantasma que travava o instalador.

O DEFEITO (2026-09-25)
----------------------
Ao instalar a 1.1.1-rc.1, o usuario recebeu "o instalador detectou que o
SIG-FT Itaipu esta atualmente em execucao" -- com o SIG-FT fechado. Havia um
SIG-FT.exe vivo, SEM janela, segurando o mutex que o instalador procura.

Reproduzido com o app de verdade sob xvfb, em tres cenarios:

  - abrir e fechar normalmente ............................ o processo termina;
  - fechar com um robo parado na pausa de login ........... NAO termina: a
    thread do robo e comum (nao-daemon), fica esperando um clique que nunca
    vem, e o Python espera por ela antes de encerrar;
  - a montagem da janela principal falhar ................. NAO termina: sobra
    uma janela invisivel e o laco de eventos segue rodando.

O conserto tem duas pontas, e este arquivo trava a do APLICATIVO: fechar a
janela encerra o processo (perguntando antes, se houver tarefa em andamento),
e a falha na abertura vira mensagem em vez de fantasma. A ponta do
INSTALADOR (sem AppMutex, com o Restart Manager fechando ate o fantasma) esta
em `tests/test_instalador.py`, secao A.
"""
import os
import pathlib
import subprocess
import sys
import textwrap
import threading

import pytest

from sigft.core import instancia

RAIZ = pathlib.Path(__file__).resolve().parent.parent


# =============================================================================
# A. O mecanismo, num processo de verdade
# =============================================================================

def _processo_com_robo_preso(fim: str) -> str:
    """Um processo Python com uma thread comum presa para sempre -- o robo
    esperando o clique de "soltar o robo" numa janela que ja nao existe."""
    return textwrap.dedent(f"""
        import sys, threading
        sys.path.insert(0, {str(RAIZ)!r})
        from sigft.core import instancia
        threading.Thread(target=threading.Event().wait, name="robo-preso").start()
        {fim}
    """)


def test_o_FANTASMA_existe_uma_thread_presa_segura_o_processo():
    """O controle: sem nada, o processo nao termina. E exatamente o SIG-FT.exe
    sem janela que o usuario tinha, e que o Gerenciador de Tarefas mostraria."""
    with pytest.raises(subprocess.TimeoutExpired):
        subprocess.run([sys.executable, "-c", _processo_com_robo_preso("pass")],
                       timeout=3, capture_output=True)


def test_encerrar_TERMINA_o_processo_mesmo_com_o_robo_preso():
    resultado = subprocess.run(
        [sys.executable, "-c", _processo_com_robo_preso("instancia.encerrar(0)")],
        timeout=30, capture_output=True, text=True)

    assert resultado.returncode == 0, resultado.stderr


def test_encerrar_descarrega_o_log_antes_de_sair():
    """No `.exe` o `print` vai para o `sigft.log`. A ultima linha antes de
    encerrar costuma ser justamente a que explica o encerramento."""
    codigo = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(RAIZ)!r})
        from sigft.core import instancia
        sys.stdout.write("ultima linha sem quebra")
        instancia.encerrar(0)
    """)
    # SEM `PYTHONUNBUFFERED`: com ela (o contêiner de desenvolvimento a define)
    # a saída não tem buffer, nada fica para trás, e o teste ficava cego --
    # a mutação "encerrar sem flush" passou verde até esta linha existir.
    ambiente = {k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"}
    resultado = subprocess.run([sys.executable, "-c", codigo], timeout=30,
                               capture_output=True, text=True, env=ambiente)

    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout == "ultima linha sem quebra"


# =============================================================================
# B. O que conta como "tarefa em andamento"
# =============================================================================

def test_tarefa_em_andamento_e_thread_COMUM_viva():
    liberar = threading.Event()
    robo = threading.Thread(target=liberar.wait, name="robo-do-teste")
    fundo = threading.Thread(target=liberar.wait, name="consulta-de-fundo", daemon=True)
    robo.start()
    fundo.start()
    try:
        tarefas = instancia.tarefas_em_andamento()
    finally:
        liberar.set()
        robo.join(5)
        fundo.join(5)

    assert "robo-do-teste" in tarefas
    assert "consulta-de-fundo" not in tarefas, (
        "thread daemon (a consulta de atualizacao, por exemplo) nao e tarefa "
        "da pessoa -- perguntar por ela ao fechar seria um aviso falso")
    assert threading.main_thread().name not in tarefas


# =============================================================================
# C. A janela principal (Qt)
# =============================================================================
# [2026-10-15] Estas seções testavam a janela da interface antiga, que saiu do
# SIG-FT. Na Qt:
#   - `main()` encerra o processo quando o laço de eventos termina:
#     `tests/test_qt_main.py::test_main_prepara_dados_e_navegador_antes_da_splash`
#     (o último evento é `instancia.encerrar(0)`);
#   - a falha ao montar a janela avisa (com o caminho do `sigft.log`) e encerra
#     com 1: `tests/test_qt_catalogo.py::test_abertura_que_falha_mostra_o_motivo_e_sai_com_1`;
#   - com tarefa, o "X" pergunta e não fecha se a pessoa desistir:
#     `tests/test_qt_main.py::test_fechar_com_tarefa_pergunta_antes`.
# Aqui, o resto do contrato do "X", portado.

@pytest.fixture
def janela(qt_interface, qtbot, tmp_path, monkeypatch):
    from sigft.app_qt import main as qmain

    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    janela = qmain.SIG_FT_App()
    qtbot.addWidget(janela)
    janela.show()
    return janela


def _perguntas(monkeypatch, resposta):
    from sigft.app_qt import main as qmain

    feitas = []

    def question(pai, titulo, texto, *a, **k):
        feitas.append(texto)
        return resposta

    monkeypatch.setattr(qmain.QMessageBox, "question", question)
    return feitas


def test_sem_tarefa_o_X_fecha_DIRETO(janela, monkeypatch):
    from sigft.app_qt import main as qmain

    monkeypatch.setattr(instancia, "tarefas_em_andamento", lambda: [])
    feitas = _perguntas(monkeypatch, qmain.QMessageBox.StandardButton.No)

    janela.close()

    assert feitas == [], "perguntou sem tarefa nenhuma"
    assert not janela.isVisible()


def test_com_tarefa_a_pergunta_diz_que_interrompe(janela, monkeypatch):
    """Fechar agora interrompe o robo no ponto em que ele esta -- no meio de
    uma planilha, inclusive. A pessoa tem de saber antes."""
    from sigft.app_qt import main as qmain

    monkeypatch.setattr(instancia, "tarefas_em_andamento", lambda: ["robo-do-modulo"])
    feitas = _perguntas(monkeypatch, qmain.QMessageBox.StandardButton.No)

    janela.close()

    assert janela.isVisible()
    [pergunta] = feitas
    assert "andamento" in pergunta and "interromp" in pergunta


def test_com_tarefa_e_a_pessoa_confirmando_fecha(janela, monkeypatch):
    from sigft.app_qt import main as qmain

    monkeypatch.setattr(instancia, "tarefas_em_andamento", lambda: ["robo-do-modulo"])
    _perguntas(monkeypatch, qmain.QMessageBox.StandardButton.Yes)

    janela.close()

    assert not janela.isVisible()
