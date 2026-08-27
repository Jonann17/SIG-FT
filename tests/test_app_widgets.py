"""Testes de `sigft/app/widgets/` — Checkpoint 7.1 (Fase 7 do plano).

O aceite do CP 7.1 é "`ConsoleFrame` com `log()` thread-safe único" + o
`ModuleFrame` base. O teste que carrega o checkdpoint é o da seção B: provar
que `log()` AGENDA o trabalho na thread da interface em vez de tocar o widget
na hora.

Isso só é testável porque o dublê de `customtkinter` (`tests/ctk_falso.py`,
instalado pelo `conftest.py`) enfileira o `after()` em vez de executá-lo. Com
o CustomTkinter real, um `after(0, ...)` que roda logo em seguida seria
indistinguível de um `insert()` direto — e distinguir os dois é exatamente o
bug que este checkpoint conserta em 7 das 12 telas.
"""
from __future__ import annotations

import threading

import customtkinter as ctk  # o dublê — ver tests/ctk_falso.py
import pytest

from sigft.app import theme
from sigft.app.widgets.console import ConsoleFrame, PREFIXO_LINHA, formatar_linha
from sigft.app.widgets.module_frame import ModuleFrame


@pytest.fixture()
def raiz():
    """Um widget-raiz do dublê, que é quem guarda a fila do `after`."""
    return ctk.CTk()


# =============================================================================
# A. formatar_linha — o formato que as 12 telas já escreviam
# =============================================================================

def test_formato_da_linha_e_o_do_frontend():
    assert formatar_linha("oi") == "> oi\n"


def test_prefixo_e_constante_e_nao_literal_solto():
    assert PREFIXO_LINHA == "> "
    assert formatar_linha("x").startswith(PREFIXO_LINHA)


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("texto", "> texto\n"),
        (42, "> 42\n"),
        (3.5, "> 3.5\n"),
        (None, "> None\n"),
        ("", "> \n"),
        ("com\nquebra", "> com\nquebra\n"),
    ],
)
def test_formatar_linha_aceita_qualquer_objeto(entrada, esperado):
    # As telas antigas caíam numa f-string, que aceita qualquer coisa. Um
    # TypeError novo aqui seria uma regressão num caminho de log -- o caminho
    # que só é exercitado quando algo já deu errado.
    assert formatar_linha(entrada) == esperado


def test_formatar_linha_aceita_excecao():
    assert formatar_linha(ValueError("falhou")) == "> falhou\n"


# =============================================================================
# B. ConsoleFrame.log — thread-safety (o aceite do checkpoint)
# =============================================================================

def test_log_nao_escreve_no_widget_na_hora(raiz):
    """O coração do CP 7.1: `log()` NÃO pode tocar o widget na chamada."""
    console = ConsoleFrame(raiz)

    console.log("mensagem")

    # Nada escrito ainda -- só agendado.
    assert console.texto == ""
    assert len(raiz.pendentes) == 1


def test_log_escreve_quando_a_thread_da_interface_processa(raiz):
    console = ConsoleFrame(raiz)

    console.log("mensagem")
    raiz.processar_eventos()

    assert console.texto == "> mensagem\n"


def test_log_rola_para_o_fim(raiz):
    console = ConsoleFrame(raiz)

    console.log("a")
    raiz.processar_eventos()

    assert console.viu_o_fim == 1


def test_varias_linhas_saem_na_ordem(raiz):
    console = ConsoleFrame(raiz)

    for i in range(5):
        console.log(f"linha {i}")
    raiz.processar_eventos()

    assert console.texto == "".join(f"> linha {i}\n" for i in range(5))


def test_log_de_thread_secundaria_tambem_so_agenda(raiz):
    """O caso real: `_worker()` rodando numa `threading.Thread`."""
    console = ConsoleFrame(raiz)

    def trabalhador():
        console.log("de dentro da thread")

    t = threading.Thread(target=trabalhador)
    t.start()
    t.join()

    # A thread secundária NÃO escreveu no widget -- só deixou na fila.
    assert console.texto == ""
    assert len(raiz.pendentes) == 1

    raiz.processar_eventos()
    assert console.texto == "> de dentro da thread\n"


def test_log_de_muitas_threads_nao_perde_linha(raiz):
    console = ConsoleFrame(raiz)
    quantidade = 50

    threads = [
        threading.Thread(target=console.log, args=(f"t{i}",)) for i in range(quantidade)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    raiz.processar_eventos()

    for i in range(quantidade):
        assert f"> t{i}\n" in console.texto
    assert console.texto.count(PREFIXO_LINHA) == quantidade


# =============================================================================
# C. ConsoleFrame.log — o protocolo do CP 1.4
# =============================================================================

def test_log_aceita_a_assinatura_completa_do_protocolo(raiz):
    console = ConsoleFrame(raiz)

    console.log("msg", "error", {"pmib": "123"})
    raiz.processar_eventos()

    assert console.texto == "> msg\n"


def test_log_aceita_nivel_e_contexto_nomeados(raiz):
    console = ConsoleFrame(raiz)

    console.log("msg", nivel="warn", contexto={"a": 1})
    raiz.processar_eventos()

    assert console.texto == "> msg\n"


def test_nivel_nao_muda_a_renderizacao(raiz):
    """`core/callbacks.py` diz explicitamente que a UI de hoje ignora o nível.

    Dar cor/prefixo a `error` seria mudar a aparência do app -- redesign, que
    a Fase 7 proíbe. Este teste é o que impede isso de entrar sem decisão.
    """
    console = ConsoleFrame(raiz)

    for nivel in ("info", "warn", "error", "debug"):
        console.log("igual", nivel=nivel)
    raiz.processar_eventos()

    assert console.texto == "> igual\n" * 4


def test_log_serve_de_callback_do_protocolo_sem_adaptador(raiz):
    """`UICallbacks(log=console.log)` tem de funcionar direto."""
    from sigft.core.callbacks import UICallbacks

    console = ConsoleFrame(raiz)
    callbacks = UICallbacks(log=console.log)

    callbacks.log("do serviço", nivel="info")
    raiz.processar_eventos()

    assert console.texto == "> do serviço\n"


# =============================================================================
# D. ConsoleFrame — robustez no fechamento
# =============================================================================

def test_widget_destruido_no_meio_do_caminho_nao_derruba_o_worker(raiz):
    """Trocar de tela com um lote rodando não pode estourar traceback."""
    console = ConsoleFrame(raiz)

    console.log("vai chegar tarde")
    console.destroy()

    raiz.processar_eventos()  # não deve levantar

    assert console.texto == ""


def test_log_apos_tk_encerrado_nao_levanta(raiz):
    console = ConsoleFrame(raiz)

    def after_que_falha(*args, **kwargs):
        raise RuntimeError("main thread is not in main loop")

    console.after = after_que_falha

    console.log("durante o fechamento")  # não deve levantar


# =============================================================================
# E. ConsoleFrame — aparência
# =============================================================================

def test_console_usa_a_fonte_do_tema(raiz):
    console = ConsoleFrame(raiz)
    assert console.kwargs["font"] == theme.FONTE_CONSOLE


def test_altura_padrao_e_a_dominante_do_frontend(raiz):
    console = ConsoleFrame(raiz)
    assert console.kwargs["height"] == 150


def test_altura_none_omite_o_height(raiz):
    """As 5 telas que deixam o grid esticar o console não passam `height`.

    Passar `height=None` ao CustomTkinter NÃO é o mesmo que omitir.
    """
    console = ConsoleFrame(raiz, altura=None)
    assert "height" not in console.kwargs


def test_altura_explicita_e_respeitada(raiz):
    console = ConsoleFrame(raiz, altura=120)  # o ModuloAutoSpec usa 120
    assert console.kwargs["height"] == 120


# =============================================================================
# F. ModuleFrame — o esqueleto
# =============================================================================

class TelaDeTeste(ModuleFrame):
    def __init__(self, parent, **kwargs):
        self.construiu = 0
        super().__init__(parent, titulo="Título", **kwargs)

    def _build_ui(self):
        self.construiu += 1


def test_module_frame_monta_header_conteudo_e_console(raiz):
    tela = TelaDeTeste(raiz)

    assert tela.header is not None
    assert tela.content is not None
    assert isinstance(tela.console, ConsoleFrame)


def test_titulo_usa_a_fonte_e_a_cor_padrao(raiz):
    tela = TelaDeTeste(raiz)

    assert tela.label_titulo.kwargs["text"] == "Título"
    assert tela.label_titulo.kwargs["font"] == theme.FONTE_TITULO_MODULO
    assert tela.label_titulo.kwargs["text_color"] == theme.COLORS["text_white"]


def test_cor_do_titulo_pode_ser_trocada(raiz):
    """O `ModuloApagarLMR` usa vermelho -- é ação destrutiva."""
    tela = TelaDeTeste(raiz, cor_titulo=theme.COLORS["danger"])
    assert tela.label_titulo.kwargs["text_color"] == "#D32F2F"


def test_build_ui_e_chamado_uma_vez(raiz):
    tela = TelaDeTeste(raiz)
    assert tela.construiu == 1


def test_construir_false_adia_o_build_ui(raiz):
    """Telas que preparam atributos antes de desenhar."""
    tela = TelaDeTeste(raiz, construir=False)
    assert tela.construiu == 0

    tela._build_ui()
    assert tela.construiu == 1


def test_subclasse_sem_build_ui_falha_com_mensagem_util(raiz):
    class TelaIncompleta(ModuleFrame):
        pass

    with pytest.raises(NotImplementedError, match="TelaIncompleta"):
        TelaIncompleta(raiz, titulo="x")


def test_console_vai_para_a_linha_2_sem_barra_de_progresso(raiz):
    tela = TelaDeTeste(raiz)

    assert tela.progress_bar is None
    assert tela.console.chamadas_grid[0]["row"] == 2


def test_com_progresso_cria_a_barra_e_empurra_o_console(raiz):
    """O arranjo do `ModuloPMIBManager`."""
    tela = TelaDeTeste(raiz, com_progresso=True)

    assert tela.progress_bar is not None
    assert tela.progress_bar.chamadas_grid[0]["row"] == 2
    assert tela.console.chamadas_grid[0]["row"] == 3


def test_barra_de_progresso_comeca_zerada(raiz):
    tela = TelaDeTeste(raiz, com_progresso=True)
    assert tela.progress_bar.valor == 0


def test_sticky_do_console_e_configuravel(raiz):
    padrao = TelaDeTeste(raiz)
    assert padrao.console.chamadas_grid[0]["sticky"] == "ew"

    esticado = TelaDeTeste(raiz, console_sticky="nsew")
    assert esticado.console.chamadas_grid[0]["sticky"] == "nsew"


def test_pady_do_console_aceita_tupla_assimetrica(raiz):
    tela = TelaDeTeste(raiz, console_pady=(15, 20))
    assert tela.console.chamadas_grid[0]["pady"] == (15, 20)


def test_header_e_conteudo_usam_o_padding_do_tema(raiz):
    tela = TelaDeTeste(raiz)

    assert tela.header.chamadas_grid[0]["padx"] == theme.PADDING_X
    assert tela.content.chamadas_grid[0]["sticky"] == "nsew"


def test_controller_fica_acessivel(raiz):
    controlador = object()
    tela = TelaDeTeste(raiz, controller=controlador)
    assert tela.controller is controlador


# =============================================================================
# G. ModuleFrame.log — delega ao console, preservando thread-safety
# =============================================================================

def test_module_frame_log_delega_ao_console(raiz):
    tela = TelaDeTeste(raiz)

    tela.log("pela tela")
    assert tela.console.texto == ""  # ainda só agendado

    raiz.processar_eventos()
    assert tela.console.texto == "> pela tela\n"


def test_module_frame_log_aceita_o_protocolo_completo(raiz):
    tela = TelaDeTeste(raiz)

    tela.log("msg", nivel="error", contexto={"x": 1})
    raiz.processar_eventos()

    assert tela.console.texto == "> msg\n"
