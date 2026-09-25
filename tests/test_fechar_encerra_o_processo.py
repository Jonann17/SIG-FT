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

import customtkinter as ctk
import pytest
from tkinter import messagebox as caixa

from sigft.core import instancia
from sigft.services import updater

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
# C. `main()`: janela fechada, processo encerrado
# =============================================================================

def test_main_ENCERRA_o_processo_quando_a_janela_fecha(monkeypatch):
    from sigft.app import main as modulo
    from sigft.core.rpa import navegador

    eventos = []

    class _SplashFalsa:
        def mainloop(self):
            eventos.append("a janela fechou")

    monkeypatch.setattr(modulo, "SplashScreen", _SplashFalsa)
    monkeypatch.setattr(navegador, "preparar_ambiente_do_rpa", lambda: None)
    monkeypatch.setattr(instancia, "encerrar",
                        lambda codigo=0: eventos.append(("encerrou", codigo)))

    modulo.main()

    assert eventos == ["a janela fechou", ("encerrou", 0)]


# =============================================================================
# D. O "X" da janela principal
# =============================================================================

TELAS = [
    "HomeView", "ModuloCriaFichas", "ModuloPDM", "ModuloAnalyzer",
    "ModuloTranslator", "ModuloUploadConditions", "ModuloUploadTechSpecs",
    "ModuloCopiaFichas", "ModuloCorrecaoPDM", "ModuloAutoSpec",
    "ModuloAplicacaoLMR", "ModuloPMIBManager", "ModuloBuscaPMIB",
]


class _TelaVazia(ctk.CTkFrame):
    def __init__(self, parent=None, controller=None, **_kw):
        super().__init__(parent)

    def grid_forget(self):
        pass


@pytest.fixture
def janela(monkeypatch):
    """A janela principal DE VERDADE, com as telas trocadas por quadros vazios."""
    from sigft.app import main as modulo

    for nome in TELAS:
        monkeypatch.setattr(modulo, nome, _TelaVazia)
    monkeypatch.setattr(updater, "deve_verificar", lambda: False)
    return modulo.SIG_FT_App()


def test_o_X_da_janela_principal_passa_pelo_fechar(janela):
    assert janela.protocolos.get("WM_DELETE_WINDOW") == janela.fechar


def test_sem_tarefa_o_X_fecha_DIRETO(janela, monkeypatch):
    monkeypatch.setattr(instancia, "tarefas_em_andamento", lambda: [])
    monkeypatch.setattr(caixa, "askyesno",
                        lambda *a, **k: pytest.fail("perguntou sem tarefa nenhuma"))

    janela.fechar()

    assert janela.destruido


def test_com_tarefa_o_X_PERGUNTA_e_nao_fecha_se_a_pessoa_desistir(janela, monkeypatch):
    """Fechar agora interrompe o robo no ponto em que ele esta -- no meio de
    uma planilha, inclusive. A pessoa tem de saber antes."""
    perguntas = []
    monkeypatch.setattr(instancia, "tarefas_em_andamento", lambda: ["robo-do-modulo"])
    monkeypatch.setattr(caixa, "askyesno",
                        lambda titulo, msg, **k: perguntas.append(msg) or False)

    janela.fechar()

    assert not janela.destruido
    [pergunta] = perguntas
    assert "andamento" in pergunta and "interromp" in pergunta


def test_com_tarefa_e_a_pessoa_confirmando_fecha(janela, monkeypatch):
    monkeypatch.setattr(instancia, "tarefas_em_andamento", lambda: ["robo-do-modulo"])
    monkeypatch.setattr(caixa, "askyesno", lambda *a, **k: True)

    janela.fechar()

    assert janela.destruido


# =============================================================================
# E. A montagem da janela falhando
# =============================================================================

class _SplashQueJaSaiu:
    def withdraw(self):
        pass

    def destroy(self):
        pass


def test_falha_ao_montar_a_janela_AVISA_e_encerra_em_vez_de_virar_fantasma(monkeypatch):
    from sigft.app import main as modulo

    eventos = []

    def janela_quebrada():
        raise RuntimeError("tela quebrada na abertura")

    monkeypatch.setattr(modulo, "SIG_FT_App", janela_quebrada)
    monkeypatch.setattr(caixa, "showerror",
                        lambda titulo, msg, **k: eventos.append(("aviso", msg)))
    monkeypatch.setattr(instancia, "encerrar",
                        lambda codigo=0: eventos.append(("encerrou", codigo)))

    modulo.SplashScreen.iniciar_app_principal(_SplashQueJaSaiu())

    [(tipo, aviso), fim] = eventos
    assert tipo == "aviso"
    assert "tela quebrada na abertura" in aviso
    assert "sigft.log" in aviso, "sem dizer onde esta o detalhe, ninguem acha"
    assert fim == ("encerrou", 1)
