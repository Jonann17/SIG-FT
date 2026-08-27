"""Testes de `sigft/app/widgets/dialogs.py` — Checkpoint 7.2 (Fase 7).

O que estes diálogos têm de perigoso não é a aparência — é o contrato com a
thread do robô. O worker fica parado em `evento.wait()` até o diálogo chamar
`set()`. Qualquer caminho de saída que ESQUEÇA o `set()` deixa a thread presa
para sempre, e o usuário vê um app que simplesmente não responde mais, sem
mensagem nenhuma.

Por isso a seção B testa os TRÊS caminhos de saída de cada diálogo, o "X" da
janela incluído — que é justamente o que se esquece.
"""
from __future__ import annotations

import threading

import customtkinter as ctk  # o dublê — ver tests/ctk_falso.py
import pytest

from sigft.app import theme
from sigft.app.widgets import dialogs


@pytest.fixture()
def raiz():
    return ctk.CTk()


@pytest.fixture()
def evento():
    return threading.Event()


# =============================================================================
# A. As mensagens — texto de interface é aparência, e a Fase 7 é zero redesign
# =============================================================================

def test_sentinela_de_login_e_a_string_que_as_telas_ja_comparavam():
    assert dialogs.LOGIN_NECESSARIO == "LOGIN_NECESSARIO"


def test_mensagens_de_login_mantem_os_tres_passos():
    for msg in (dialogs.MSG_LOGIN_SOLTAR_ROBO, dialogs.MSG_LOGIN_LOTE):
        assert "O navegador foi aberto." in msg
        assert "1. Faça o LOGIN no site." in msg
        assert "2. Navegue até a tela inicial do PMIB." in msg
        assert msg.count("\n") >= 4


def test_as_duas_mensagens_de_login_diferem_so_no_desfecho():
    assert dialogs.MSG_LOGIN_SOLTAR_ROBO.endswith("soltar o robô.")
    assert dialogs.MSG_LOGIN_LOTE.endswith("iniciar a automação em lote.")


def test_mensagem_de_falha_ao_salvar_nomeia_a_secao():
    msg = dialogs.msg_falha_ao_salvar("INFO. GERAIS")
    assert "'INFO. GERAIS'" in msg
    assert "Clique em SALVAR no site" in msg


def test_mensagem_de_ficha_preenchida_nomeia_o_pmib():
    msg = dialogs.msg_ficha_preenchida("4500063671.0929")
    assert "4500063671.0929" in msg
    assert "pendências" in msg


def test_mensagem_de_excel_bloqueado_diz_o_que_fazer():
    assert "_STATUS_PMIB" in dialogs.MSG_EXCEL_BLOQUEADO
    assert "FECHE O ARQUIVO" in dialogs.MSG_EXCEL_BLOQUEADO


# =============================================================================
# B. O contrato com a thread do robô — todo caminho de saída solta o worker
# =============================================================================

def test_pausa_botao_continuar_solta_o_worker(raiz, evento):
    dialogo = dialogs.PausaLoginDialog(raiz, mensagem="oi", evento_espera=evento)

    assert not evento.is_set()
    dialogo.liberar()

    assert evento.is_set()
    assert dialogo.destruido


def test_pausa_fechar_no_x_tambem_solta_o_worker(raiz, evento):
    """O caminho esquecido: sem isto, fechar a janela trava o robô para sempre."""
    dialogo = dialogs.PausaLoginDialog(raiz, mensagem="oi", evento_espera=evento)

    fechar = dialogo.protocolos["WM_DELETE_WINDOW"]
    fechar()

    assert evento.is_set()


def test_pausa_realmente_destrava_uma_thread_em_espera(raiz, evento):
    """O cenário de verdade, com uma thread bloqueada em `wait()`."""
    soltou = []

    def worker():
        evento.wait(timeout=5)
        soltou.append(True)

    t = threading.Thread(target=worker)
    t.start()

    dialogo = dialogs.PausaLoginDialog(raiz, mensagem="oi", evento_espera=evento)
    dialogo.liberar()

    t.join(timeout=5)
    assert soltou == [True]


def test_retry_repetir_devolve_true_e_solta(raiz, evento):
    resultado = {}
    dialogo = dialogs.RetryLockDialog(raiz, evento_espera=evento, resultado=resultado)

    dialogo.repetir()

    assert resultado["retry"] is True
    assert evento.is_set()


def test_retry_cancelar_devolve_false_e_solta(raiz, evento):
    resultado = {}
    dialogo = dialogs.RetryLockDialog(raiz, evento_espera=evento, resultado=resultado)

    dialogo.cancelar()

    assert resultado["retry"] is False
    assert evento.is_set()


def test_retry_fechar_no_x_equivale_a_cancelar(raiz, evento):
    """Repetir uma gravação que o usuário acabou de recusar seria pior."""
    resultado = {}
    dialogo = dialogs.RetryLockDialog(raiz, evento_espera=evento, resultado=resultado)

    dialogo.protocolos["WM_DELETE_WINDOW"]()

    assert resultado["retry"] is False
    assert evento.is_set()


# =============================================================================
# C. Aparência — o que as 3 cópias faziam, preservado
# =============================================================================

def test_pausa_tem_o_titulo_e_a_geometria_das_copias(raiz, evento):
    dialogo = dialogs.PausaLoginDialog(raiz, mensagem="oi", evento_espera=evento)

    assert dialogo.titulo == "Ação Manual Necessária"
    assert dialogo.geometria == "450x250"


def test_retry_tem_o_titulo_e_a_geometria_da_copia(raiz, evento):
    dialogo = dialogs.RetryLockDialog(raiz, evento_espera=evento, resultado={})

    assert dialogo.titulo == "Arquivo Bloqueado"
    assert dialogo.geometria == "450x200"


def test_dialogos_ficam_sempre_no_topo(raiz, evento):
    dialogo = dialogs.PausaLoginDialog(raiz, mensagem="oi", evento_espera=evento)
    assert dialogo.atributos["-topmost"] is True


def test_nenhum_dialogo_chama_grab_set(raiz, evento):
    """O comentário original avisava: `grab_set()` "bloqueava tudo".

    Ele torna o diálogo modal e captura os eventos da aplicação inteira — o
    usuário perde justamente o que precisa fazer enquanto ele está aberto:
    clicar no console para copiar as pendências.
    """
    pausa = dialogs.PausaLoginDialog(raiz, mensagem="oi", evento_espera=evento)
    retry = dialogs.RetryLockDialog(raiz, evento_espera=threading.Event(), resultado={})

    assert not hasattr(pausa, "chamou_grab_set")
    assert not hasattr(retry, "chamou_grab_set")


def test_botao_continuar_usa_a_cor_primaria_do_tema(raiz, evento):
    dialogo = dialogs.PausaLoginDialog(raiz, mensagem="oi", evento_espera=evento)

    assert dialogo.botao.kwargs["fg_color"] == theme.COLORS["primary"]
    assert dialogo.botao.kwargs["text"] == "CONTINUAR AUTOMAÇÃO"


def test_retry_tem_os_dois_botoes_com_os_rotulos_originais(raiz, evento):
    dialogo = dialogs.RetryLockDialog(raiz, evento_espera=evento, resultado={})

    assert dialogo.botao_repetir.kwargs["text"] == "Tentar Novamente"
    assert dialogo.botao_cancelar.kwargs["text"] == "Ignorar e Continuar"
    # O de cancelar é o discreto: transparente com borda.
    assert dialogo.botao_cancelar.kwargs["fg_color"] == "transparent"
    assert dialogo.botao_repetir.kwargs["fg_color"] == theme.COLORS["primary"]
