import threading

from sigft.app import backends
from sigft.app_qt.widgets.module_frame import ModuleFrame


class Tela(ModuleFrame):
    def _build_ui(self):
        self.construida = True


def test_monta_cabecalho_conteudo_console(qt_interface, qtbot):
    t = Tela(titulo="Tradutor Técnico")
    qtbot.addWidget(t)
    assert t.construida and t.label_titulo.text() == "Tradutor Técnico"
    assert t.progress_bar is None and t.console is not None


def test_com_progresso(qt_interface, qtbot):
    t = Tela(titulo="x", com_progresso=True)
    qtbot.addWidget(t)
    assert t.progress_bar.maximum() == 1000


def test_embutida_usa_console_do_pai(qt_interface, qtbot):
    pai = Tela(titulo="pai")
    qtbot.addWidget(pai)
    filha = Tela(titulo="filha", embutida=True, console_externo=pai.console)
    qtbot.addWidget(filha)
    assert filha.header is None and filha.console is pai.console


def test_backend_que_falhou_vira_aviso_e_nao_excecao(qt_interface, qtbot, monkeypatch):
    monkeypatch.setattr(backends, "lmr_backend", None)
    monkeypatch.setattr(backends, "falhas", {"lmr_backend": ImportError("sem xlwings")})
    avisos = []
    monkeypatch.setattr("sigft.app_qt.widgets.module_frame.QMessageBox.warning",
                        lambda *a, **k: avisos.append(a[2]))
    t = Tela(titulo="x")
    qtbot.addWidget(t)
    assert t.backend("lmr_backend") is None
    assert "sem xlwings" in avisos[0]
    qtbot.waitUntil(lambda: "sem xlwings" in t.console.toPlainText(), timeout=2000)


def test_tarefa_desabilita_o_botao_no_clique_e_reabilita_no_fim(qt_interface, qtbot):
    from PySide6.QtWidgets import QPushButton
    t = Tela(titulo="x")
    qtbot.addWidget(t)
    botao = QPushButton("Rodar")
    qtbot.addWidget(botao)
    liberar = threading.Event()
    thread = t.iniciar_tarefa(liberar.wait, 5, botao=botao)
    assert not botao.isEnabled()          # desabilitado ANTES de a thread rodar
    assert not thread.daemon              # tarefa da pessoa: o "X" pergunta antes
    liberar.set()
    thread.join(3)
    qtbot.waitUntil(botao.isEnabled, timeout=2000)


def test_excecao_no_worker_vai_para_o_console_e_solta_o_botao(qt_interface, qtbot):
    from PySide6.QtWidgets import QPushButton
    t = Tela(titulo="x")
    qtbot.addWidget(t)
    botao = QPushButton("Rodar")
    qtbot.addWidget(botao)
    thread = t.iniciar_tarefa(lambda: 1 / 0, botao=botao)
    thread.join(3)
    qtbot.waitUntil(lambda: "ZeroDivisionError" in t.console.toPlainText(), timeout=2000)
    qtbot.waitUntil(botao.isEnabled, timeout=2000)


def test_backend_pedido_de_thread_de_fundo_avisa_na_thread_da_interface(
        qt_interface, qtbot, monkeypatch):
    """As telas piloto leem o backend dentro do worker: o QMessageBox nao pode
    nascer la (derruba o app no macOS) -- vai para a thread da interface."""
    monkeypatch.setattr(backends, "lmr_backend", None)
    monkeypatch.setattr(backends, "falhas", {"lmr_backend": ImportError("sem xlwings")})
    chamadas = []
    monkeypatch.setattr(
        "sigft.app_qt.widgets.module_frame.QMessageBox.warning",
        lambda *a, **k: chamadas.append((threading.get_ident(), a[2])))
    t = Tela(titulo="x")
    qtbot.addWidget(t)
    resultado = []
    worker = threading.Thread(
        target=lambda: resultado.append(t.backend("lmr_backend")), daemon=True)
    worker.start()
    worker.join(3)
    assert resultado == [None]                       # o worker nao trava nem recebe lixo
    qtbot.waitUntil(lambda: len(chamadas) == 1, timeout=2000)
    assert chamadas[0][0] == threading.get_ident()   # aviso na thread da interface
    assert worker.ident != chamadas[0][0]
    assert "sem xlwings" in chamadas[0][1]
    qtbot.waitUntil(lambda: "sem xlwings" in t.console.toPlainText(), timeout=2000)


# =============================================================================
# Portados de `tests/test_app_widgets.py` (o esqueleto de tela da interface
# antiga, que saiu em 2026-10-15): o contrato do `ModuleFrame`.
# =============================================================================

class TelaQueConta(ModuleFrame):
    def __init__(self, **kwargs):
        self.construiu = 0
        super().__init__(titulo="Título", **kwargs)

    def _build_ui(self):
        self.construiu += 1


def test_build_ui_e_chamado_uma_vez_e_construir_false_adia(qt_interface, qtbot):
    tela = TelaQueConta()
    qtbot.addWidget(tela)
    assert tela.construiu == 1
    adiada = TelaQueConta(construir=False)
    qtbot.addWidget(adiada)
    assert adiada.construiu == 0
    adiada._build_ui()
    assert adiada.construiu == 1


def test_subclasse_sem_build_ui_falha_com_mensagem_util(qt_interface):
    import pytest

    class TelaIncompleta(ModuleFrame):
        pass

    with pytest.raises(NotImplementedError, match="TelaIncompleta"):
        TelaIncompleta(titulo="x")


def test_cor_do_titulo_pode_ser_trocada_e_controller_fica_acessivel(qt_interface, qtbot):
    """O `ModuloApagarLMR` usa vermelho -- é ação destrutiva. Desde 2026-10-20 o
    título diz o PAPEL (`erro`) e a cor é da folha do tema (some no tema claro)."""
    from sigft.app import tokens
    from sigft.app_qt import estilo

    controlador = object()
    tela = TelaQueConta(papel_titulo="erro", controller=controlador)
    qtbot.addWidget(tela)
    assert tela.label_titulo.property("papel") == "erro"
    assert "color" not in tela.label_titulo.styleSheet()
    assert f'#titulo_modulo[papel="erro"] {{ color: {tokens.ESCURO["perigo"]}; }}' in estilo.folha_de_estilo()
    assert tela.controller is controlador


def test_log_da_tela_delega_ao_console_com_o_protocolo_completo(qt_interface, qtbot):
    tela = TelaQueConta()
    qtbot.addWidget(tela)
    tela.log("pela tela")
    tela.log("msg", nivel="error", contexto={"x": 1})
    qtbot.waitUntil(lambda: tela.console.blockCount() >= 2, timeout=2000)
    assert tela.console.toPlainText().splitlines() == ["> pela tela", "> msg"]
