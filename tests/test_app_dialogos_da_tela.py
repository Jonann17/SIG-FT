"""`ModuleFrame._abrir_e_esperar` e os dois métodos sobre ele — CP A.

Ver `docs/superpowers/specs/2026-08-28-padronizacao-dialogos-design.md`.

O que precisa ser provado aqui não é aparência, é o contrato com a thread do
robô:

1. o diálogo é **agendado** na thread da interface, não criado na hora — é o
   que torna correto chamar isto de dentro de um `_worker`;
2. quem chamou fica **bloqueado** até o usuário decidir, e é solto depois;
3. chamar da própria thread da interface **falha alto**, em vez de congelar o
   app em silêncio.

O ponto 3 merece explicação: `wait()` chamado na thread do Tk seguraria
justamente a thread que precisa rodar o `after` que solta o `wait()`. O app
trava para sempre, sem mensagem, sem log, sem nada que o usuário possa
reportar. Um `RuntimeError` é infinitamente melhor.

Os testes rodam o "usuário decidindo" de verdade: uma thread chama o método e
bloqueia; a thread principal drena a fila do `after` (como faria o mainloop do
Tk) e clica no botão do diálogo.
"""
from __future__ import annotations

import threading

import customtkinter as ctk  # dublê — tests/ctk_falso.py
import pytest

from sigft.app.widgets import dialogs
from sigft.app.widgets.espera import DialogosDeEspera
from sigft.app.widgets.module_frame import ModuleFrame


class TelaDeTeste(ModuleFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, titulo="Teste", **kwargs)

    def _build_ui(self):
        pass


@pytest.fixture()
def raiz():
    return ctk.CTk()


@pytest.fixture()
def tela(raiz):
    return TelaDeTeste(raiz)


def _rodar_em_thread(funcao):
    """Roda `funcao` numa thread e devolve (thread, caixa_de_resultado)."""
    caixa: dict = {}

    def alvo():
        try:
            caixa["valor"] = funcao()
        except BaseException as erro:  # noqa: BLE001 - o teste inspeciona
            caixa["erro"] = erro

    t = threading.Thread(target=alvo)
    t.start()
    return t, caixa


def _esperar_agendamento(raiz, timeout=5.0):
    """Espera a thread do worker enfileirar o `after`."""
    limite = threading.Event()
    inicio = threading.current_thread()
    del inicio
    for _ in range(int(timeout / 0.01)):
        if raiz.pendentes:
            return True
        limite.wait(0.01)
    return False


# =============================================================================
# A. O diálogo é AGENDADO, não criado na hora
# =============================================================================

def test_pausar_agenda_o_dialogo_em_vez_de_criar_na_hora(tela, raiz):
    t, _ = _rodar_em_thread(lambda: tela.pausar_e_esperar("faça o login"))

    assert _esperar_agendamento(raiz), "o worker não agendou o diálogo"
    # Nada foi construído ainda -- só enfileirado na thread da interface.
    assert len(raiz.pendentes) == 1

    raiz.processar_eventos()          # a interface constrói o diálogo
    _dialogo_aberto(raiz).liberar()   # o usuário clica
    t.join(timeout=5)
    assert not t.is_alive()


def _dialogo_aberto(raiz):
    """O último PausaLoginDialog/RetryLockDialog criado sob a raiz."""
    for filho in reversed(raiz.filhos):
        if isinstance(filho, (dialogs.PausaLoginDialog, dialogs.RetryLockDialog)):
            return filho
    # os diálogos nascem filhos da TELA, não da raiz
    for filho in raiz.filhos:
        for neto in reversed(getattr(filho, "filhos", [])):
            if isinstance(neto, (dialogs.PausaLoginDialog, dialogs.RetryLockDialog)):
                return neto
    raise AssertionError("nenhum diálogo foi aberto")


# =============================================================================
# B. Quem chamou fica bloqueado, e é solto
# =============================================================================

def test_o_worker_fica_bloqueado_ate_o_usuario_decidir(tela, raiz):
    t, _ = _rodar_em_thread(lambda: tela.pausar_e_esperar("faça o login"))
    assert _esperar_agendamento(raiz)

    raiz.processar_eventos()
    # O diálogo está aberto e ninguém clicou: o worker CONTINUA parado.
    t.join(timeout=0.3)
    assert t.is_alive(), "o worker seguiu sem esperar a decisão do usuário"

    _dialogo_aberto(raiz).liberar()
    t.join(timeout=5)
    assert not t.is_alive(), "o worker não foi solto depois do clique"


def test_fechar_no_x_tambem_solta_o_worker(tela, raiz):
    t, _ = _rodar_em_thread(lambda: tela.pausar_e_esperar("faça o login"))
    assert _esperar_agendamento(raiz)
    raiz.processar_eventos()

    _dialogo_aberto(raiz).protocolos["WM_DELETE_WINDOW"]()

    t.join(timeout=5)
    assert not t.is_alive()


# =============================================================================
# C. Chamar da thread da interface falha alto
# =============================================================================

def test_chamar_da_thread_da_interface_levanta_em_vez_de_travar(tela):
    with pytest.raises(RuntimeError, match="travaria o aplicativo"):
        tela.pausar_e_esperar("isto travaria o app")


def test_a_mensagem_do_erro_nomeia_a_tela_e_diz_o_que_fazer(tela):
    with pytest.raises(RuntimeError) as erro:
        tela.perguntar_retry_excel()

    texto = str(erro.value)
    assert "TelaDeTeste" in texto
    assert "worker" in texto


# =============================================================================
# D. pausar_e_esperar — mensagem e botão
# =============================================================================

def test_a_mensagem_chega_ao_dialogo(tela, raiz):
    t, _ = _rodar_em_thread(lambda: tela.pausar_e_esperar("MENSAGEM ESPECÍFICA"))
    assert _esperar_agendamento(raiz)
    raiz.processar_eventos()

    dialogo = _dialogo_aberto(raiz)
    rotulo = dialogo.filhos[0]
    assert rotulo.kwargs["text"] == "MENSAGEM ESPECÍFICA"

    dialogo.liberar()
    t.join(timeout=5)


def test_texto_do_botao_e_o_padrao_quando_nao_informado(tela, raiz):
    t, _ = _rodar_em_thread(lambda: tela.pausar_e_esperar("x"))
    assert _esperar_agendamento(raiz)
    raiz.processar_eventos()

    dialogo = _dialogo_aberto(raiz)
    assert dialogo.botao.kwargs["text"] == dialogs.TEXTO_CONTINUAR

    dialogo.liberar()
    t.join(timeout=5)


def test_texto_do_botao_pode_ser_trocado_para_acao_destrutiva(tela, raiz):
    """Na exclusão de LMR, o botão diz o que vai acontecer."""
    t, _ = _rodar_em_thread(
        lambda: tela.pausar_e_esperar("x", texto_botao=dialogs.TEXTO_COMECAR_EXCLUSAO)
    )
    assert _esperar_agendamento(raiz)
    raiz.processar_eventos()

    dialogo = _dialogo_aberto(raiz)
    assert dialogo.botao.kwargs["text"] == "COMEÇAR A EXCLUSÃO"

    dialogo.liberar()
    t.join(timeout=5)


# =============================================================================
# E. perguntar_retry_excel — devolve a decisão
# =============================================================================

def test_tentar_novamente_devolve_true(tela, raiz):
    t, caixa = _rodar_em_thread(lambda: tela.perguntar_retry_excel())
    assert _esperar_agendamento(raiz)
    raiz.processar_eventos()

    _dialogo_aberto(raiz).repetir()
    t.join(timeout=5)

    assert caixa["valor"] is True


def test_ignorar_e_continuar_devolve_false(tela, raiz):
    t, caixa = _rodar_em_thread(lambda: tela.perguntar_retry_excel())
    assert _esperar_agendamento(raiz)
    raiz.processar_eventos()

    _dialogo_aberto(raiz).cancelar()
    t.join(timeout=5)

    assert caixa["valor"] is False


def test_fechar_no_x_equivale_a_ignorar(tela, raiz):
    t, caixa = _rodar_em_thread(lambda: tela.perguntar_retry_excel())
    assert _esperar_agendamento(raiz)
    raiz.processar_eventos()

    _dialogo_aberto(raiz).protocolos["WM_DELETE_WINDOW"]()
    t.join(timeout=5)

    assert caixa["valor"] is False


def test_sem_caminho_usa_a_mensagem_historica_do_status_pmib(tela, raiz):
    t, _ = _rodar_em_thread(lambda: tela.perguntar_retry_excel())
    assert _esperar_agendamento(raiz)
    raiz.processar_eventos()

    dialogo = _dialogo_aberto(raiz)
    assert dialogo.filhos[0].kwargs["text"] == dialogs.MSG_EXCEL_BLOQUEADO

    dialogo.cancelar()
    t.join(timeout=5)


def test_com_caminho_a_mensagem_NOMEIA_o_arquivo_travado(tela, raiz):
    """Agora que a janela serve pdm/analyzer/autospec/translator, dizer «o
    _STATUS_PMIB» seria mentira na maioria dos casos."""
    t, _ = _rodar_em_thread(
        lambda: tela.perguntar_retry_excel(caminho=r"C:\fichas\4500063671.0929.xlsx")
    )
    assert _esperar_agendamento(raiz)
    raiz.processar_eventos()

    dialogo = _dialogo_aberto(raiz)
    texto = dialogo.filhos[0].kwargs["text"]
    assert "4500063671.0929.xlsx" in texto
    assert "FECHE O ARQUIVO" in texto

    dialogo.cancelar()
    t.join(timeout=5)


def test_mensagem_com_caminho_mostra_so_o_nome_do_arquivo(tela):
    """Caminho inteiro numa janela de 450px quebraria o texto."""
    msg = dialogs.msg_excel_bloqueado(r"C:\Users\alguem\Box\muito\fundo\ficha.xlsx")

    assert "ficha.xlsx" in msg
    assert "C:\\Users" not in msg


# =============================================================================
# F. Guarda: quem CHAMA os métodos precisa TER os métodos
# =============================================================================
# Este teste existe por causa de um erro real cometido ao implementar o CP B:
# as chamadas a `self.pausar_e_esperar(...)` foram escritas em 3 telas, mas só
# UMA delas (`ApagarLMR`) herdava de `ModuleFrame`. As outras duas eram
# `ctk.CTkFrame` puro, e teriam estourado `AttributeError` na frente do
# usuário -- no meio de um lote, depois do navegador já aberto.
#
# `compileall` não pega (é atributo, resolvido em tempo de execução), `pyflakes`
# não pega (é `self.`), e nenhum teste de widget pegaria, porque essas telas não
# são instanciadas na suíte. Só uma checagem estrutural pega.

import ast
import pathlib

DIR_VIEWS = pathlib.Path(__file__).resolve().parent.parent / "sigft" / "app" / "views"
METODOS_DO_MIXIN = {"pausar_e_esperar", "perguntar_retry_excel", "_abrir_e_esperar"}
BASES_QUE_FORNECEM = {"DialogosDeEspera", "ModuleFrame"}


def _classes_das_views():
    for arquivo in sorted(DIR_VIEWS.glob("*.py")):
        if arquivo.name == "__init__.py":
            continue
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.ClassDef):
                yield arquivo.name, no


def _metodos_do_mixin_chamados(classe):
    chamados = set()
    for sub in ast.walk(classe):
        if (
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Attribute)
            and isinstance(sub.func.value, ast.Name)
            and sub.func.value.id == "self"
            and sub.func.attr in METODOS_DO_MIXIN
        ):
            chamados.add(sub.func.attr)
    return chamados


def test_toda_tela_que_chama_o_mixin_realmente_herda_dele():
    faltando = []
    for arquivo, classe in _classes_das_views():
        chamados = _metodos_do_mixin_chamados(classe)
        if not chamados:
            continue
        bases = {ast.unparse(b).split(".")[-1] for b in classe.bases}
        if not (bases & BASES_QUE_FORNECEM):
            faltando.append(
                f"{arquivo}::{classe.name} chama {sorted(chamados)} mas herda de "
                f"{sorted(bases)} — falta DialogosDeEspera"
            )

    assert not faltando, "\n".join(faltando)


def test_a_guarda_acima_esta_de_fato_examinando_telas():
    """Sentinela: se o caminho das views mudar, o teste anterior passaria vazio
    e daria uma falsa sensação de segurança."""
    classes = [c for _, c in _classes_das_views() if c.name.startswith("Modulo")]
    assert len(classes) >= 10, f"esperava as 12 telas, achei {len(classes)}"

    com_mixin = [c.name for _, c in _classes_das_views() if _metodos_do_mixin_chamados(c)]
    assert com_mixin, "nenhuma tela chama o mixin — o CP B não foi aplicado?"
