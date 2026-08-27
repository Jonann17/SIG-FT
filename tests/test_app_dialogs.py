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


# =============================================================================
# E. TabelaSelecaoDialog — consolida JanelaSelecao + JanelaSelecaoDuplicadas
# =============================================================================

def _tabela(raiz, **kwargs):
    kwargs.setdefault("colunas", ["Descrição", "PMIB"])
    kwargs.setdefault("linhas", [(10, ("Bomba", "4500.0001")), (20, ("Válvula", "4500.0002"))])
    return dialogs.TabelaSelecaoDialog(raiz, **kwargs)


def test_tabela_monta_cabecalhos_e_linhas(raiz):
    dialogo = _tabela(raiz)

    assert dialogo.tree.cabecalhos == {"Descrição": "Descrição", "PMIB": "PMIB"}
    assert dialogo.tree.linhas["10"] == ("Bomba", "4500.0001")
    assert dialogo.tree.linhas["20"] == ("Válvula", "4500.0002")


def test_tabela_devolve_a_CHAVE_da_linha_nao_a_posicao(raiz):
    """O defeito clássico desta tela.

    A chave é o índice do DataFrame / a posição na fila de origem. Devolver a
    posição VISUAL faria o lote processar a ficha errada quando a origem
    estivesse filtrada ou reordenada — sem erro nenhum aparecer.
    """
    recebidos = []
    dialogo = _tabela(raiz, ao_confirmar=recebidos.append)

    dialogo.tree.selection_set(20)
    dialogo.confirmar()

    assert recebidos == [["20"]]


def test_tabela_confirmar_sem_selecao_avisa_e_nao_fecha(raiz):
    """Confirmar com nada marcado é um cancelamento silencioso disfarçado."""
    recebidos = []
    dialogo = _tabela(raiz, ao_confirmar=recebidos.append)

    dialogo.confirmar()

    assert recebidos == []
    assert not dialogo.destruido


def test_tabela_preselecionar_tudo_marca_todas_as_linhas(raiz):
    """`JanelaSelecaoDuplicadas` vinha com tudo marcado; `JanelaSelecao`, não."""
    dialogo = _tabela(raiz, preselecionar_tudo=True)

    assert set(dialogo.selecionados) == {"10", "20"}


def test_tabela_sem_preselecao_comeca_vazia(raiz):
    dialogo = _tabela(raiz)
    assert dialogo.selecionados == []


def test_tabela_confirmar_fecha_a_janela(raiz):
    dialogo = _tabela(raiz)
    dialogo.tree.selection_set(10)

    dialogo.confirmar()

    assert dialogo.destruido


def test_tabela_cancelar_e_opcional(raiz):
    """`JanelaSelecao` só tinha Confirmar; `JanelaSelecaoDuplicadas` tinha os dois."""
    com = _tabela(raiz)
    sem = _tabela(raiz, com_cancelar=False)

    assert com.botao_cancelar is not None
    assert sem.botao_cancelar is None


def test_tabela_de_dataframe_usa_o_INDICE_como_chave(raiz):
    """`JanelaSelecao` devolvia `[int(i) for i in tree.selection()]` — o índice
    do DataFrame, não a posição da linha na tela."""

    class LinhaFalsa:
        def __init__(self, valores):
            self._valores = valores

        def to_numpy(self):
            return self

        def tolist(self):
            return self._valores

    class DataFrameFalso:
        columns = ["A", "B"]

        def iterrows(self):
            # Índices NÃO sequenciais, como um DataFrame filtrado.
            yield 7, LinhaFalsa(["a1", "b1"])
            yield 42, LinhaFalsa(["a2", "b2"])

    dialogo = dialogs.TabelaSelecaoDialog.de_dataframe(raiz, DataFrameFalso())

    assert set(dialogo.tree.linhas) == {"7", "42"}
    assert dialogo.tree.linhas["42"] == ("a2", "b2")


def test_tabela_larguras_por_coluna(raiz):
    dialogo = _tabela(raiz, larguras={"Descrição": {"width": 400}})

    assert dialogo.tree.colunas_config["Descrição"]["width"] == 400
    # A que não foi citada cai no padrão das cópias.
    assert dialogo.tree.colunas_config["PMIB"]["width"] == 120


# =============================================================================
# F. SelecaoMultiplaDialog — a variante de lista simples
# =============================================================================

def test_lista_multipla_mostra_os_itens(raiz):
    dialogo = dialogs.SelecaoMultiplaDialog(raiz, itens=["A", "B", "C"])
    assert dialogo.listbox.itens == ["A", "B", "C"]


def test_lista_multipla_devolve_os_TEXTOS_marcados(raiz):
    """Os dois popups faziam `[lb.get(i) for i in lb.curselection()]`."""
    recebidos = []
    dialogo = dialogs.SelecaoMultiplaDialog(
        raiz, itens=["4500.0001", "4500.0002", "4500.0003"], ao_confirmar=recebidos.append
    )

    dialogo.listbox.selecionar(0, 2)
    dialogo.confirmar()

    assert recebidos == [["4500.0001", "4500.0003"]]


def test_lista_multipla_sem_selecao_devolve_lista_vazia(raiz):
    """O popup de códigos tratava vazio como "cancelou" — quem decide é a tela."""
    recebidos = []
    dialogo = dialogs.SelecaoMultiplaDialog(
        raiz, itens=["A"], ao_confirmar=recebidos.append
    )

    dialogo.confirmar()

    assert recebidos == [[]]
    assert dialogo.destruido


def test_lista_multipla_usa_a_fonte_monoespacada(raiz):
    """Códigos PMIB alinhados — era `font=("Consolas", 11)` no popup."""
    dialogo = dialogs.SelecaoMultiplaDialog(raiz, itens=["A"])
    assert dialogo.listbox.kwargs["font"] == theme.FONTE_CONSOLE
