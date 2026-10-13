from types import SimpleNamespace

import pytest

from sigft.app import backends
from sigft.app_qt.views import translator as tela_mod


class TradutorFalso:
    def __init__(self, mensagens):
        self.mensagens = mensagens
        self.parou = False

    def processar_arquivos(self, files, retry_lock=None):
        yield from self.mensagens

    def request_stop(self):
        self.parou = True

    def caminho_do_glossario(self):
        return "/tmp/glossario.csv"


@pytest.fixture
def tela(qt_interface, qtbot, monkeypatch):
    avisos = []
    monkeypatch.setattr(tela_mod.ModuloTranslator, "avisar",
                        lambda self, t, m, tipo="info": avisos.append((tipo, m)))
    t = tela_mod.ModuloTranslator()
    qtbot.addWidget(t)
    t.avisos = avisos
    return t


def _com_backend(monkeypatch, mensagens):
    falso = TradutorFalso(mensagens)
    modulo = SimpleNamespace(TechnicalTranslator=lambda: falso,
                             STATUS=frozenset({"SUCESSO", "ERRO", "PARADO", "ABORTADO", "ERRO_MOVER"}))
    monkeypatch.setattr(backends, "translator_backend", modulo)
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_files", lambda *a, **k: ("/a.xlsx",))
    return falso


def test_monta_com_os_textos(tela):
    assert tela.label_titulo.text() == "Tradutor Técnico (PT -> ES)"
    assert tela.btn_run.text() == "Selecionar Arquivos e Iniciar"
    assert not tela.btn_stop.isEnabled()


def test_lote_completo(tela, qtbot, monkeypatch):
    _com_backend(monkeypatch, ["Traduzindo a.xlsx", "SUCESSO"])
    tela.btn_run.click()
    qtbot.waitUntil(lambda: "Tradução em lote finalizada." in tela.console.toPlainText(), timeout=3000)
    texto = tela.console.toPlainText()
    assert "Iniciando tradução de 1 arquivos..." in texto and "SUCESSO" not in texto
    qtbot.waitUntil(tela.btn_run.isEnabled, timeout=2000)
    assert not tela.btn_stop.isEnabled()
    assert tela.avisos == [("info", "Processo concluído.")]


def test_abortado_avisa_o_ultimo_erro(tela, qtbot, monkeypatch):
    _com_backend(monkeypatch, ["[ERRO] Excel não abriu", "ABORTADO"])
    tela.btn_run.click()
    qtbot.waitUntil(lambda: "Tradução não iniciada." in tela.console.toPlainText(), timeout=3000)
    assert tela.avisos == [("erro", "[ERRO] Excel não abriu")]


def test_parar(tela, monkeypatch):
    falso = _com_backend(monkeypatch, [])
    assert tela._tradutor() is falso
    tela.btn_stop.setEnabled(True)
    tela.btn_stop.click()
    assert falso.parou


def test_backend_que_nao_carregou_nao_abre_dialogo(tela, monkeypatch):
    monkeypatch.setattr(backends, "translator_backend", None)
    monkeypatch.setattr(backends, "falhas", {"translator_backend": ImportError("sem xlwings")})
    monkeypatch.setattr(tela_mod.QMessageBox, "warning", staticmethod(lambda *a: None))
    chamou = []
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_files", lambda *a, **k: chamou.append(1))
    tela.btn_run.click()
    assert chamou == []


def test_medidas_iguais_as_do_customtkinter(qt_interface, qtbot):
    # Medidas da tela antiga (CustomTkinter, 1280x850, sondadas com winfo_*),
    # relativas à área da tela: título em (20, 10) dentro da tela posta com
    # padx/pady=20; cartão 20 px abaixo do conteúdo; botões 50/40/32 de altura
    # com 30/20/10 px de espaço entre as peças; console 20 px abaixo do conteúdo.
    from sigft.app_qt import estilo

    anterior = qt_interface.styleSheet()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    try:
        t = tela_mod.ModuloTranslator()
        qtbot.addWidget(t)
        t.resize(1003, 850)
        t.show()
        qtbot.waitExposed(t)

        def pos(w):
            return w.mapTo(t, w.rect().topLeft())

        assert (pos(t.label_titulo).x(), pos(t.label_titulo).y()) == (40, 30)
        assert pos(t.content).y() - (pos(t.header).y() + t.header.height()) == 20
        assert pos(t.console).y() - (pos(t.content).y() + t.content.height()) == 20
        assert t.height() - (pos(t.console).y() + t.console.height()) == 30
        cartao = t.btn_run.parentWidget()
        assert pos(cartao).y() - pos(t.content).y() == 20
        assert (t.btn_run.height(), t.btn_stop.height(), t.btn_glossario.height()) == (50, 40, 32)
        assert pos(t.btn_stop).y() - (pos(t.btn_run).y() + 50) == 20
        assert pos(t.btn_glossario).y() - (pos(t.btn_stop).y() + 40) == 10
        assert pos(cartao).y() + cartao.height() - (pos(t.btn_glossario).y() + 32) == 20
    finally:
        qt_interface.setStyleSheet(anterior)


def test_glossario_abre_no_sistema(tela, monkeypatch):
    _com_backend(monkeypatch, [])
    abertos = []
    monkeypatch.setattr(tela_mod.plataforma, "abrir_no_sistema", abertos.append)
    tela.abrir_glossario()
    assert abertos == ["/tmp/glossario.csv"]


def test_glossario_que_nao_abre_vira_aviso(tela, monkeypatch):
    _com_backend(monkeypatch, [])
    criticos = []

    def falha(caminho):
        raise OSError("sem programa associado")

    monkeypatch.setattr(tela_mod.plataforma, "abrir_no_sistema", falha)
    monkeypatch.setattr(tela_mod.QMessageBox, "critical", staticmethod(lambda *a: criticos.append(a[2])))
    tela.abrir_glossario()
    assert criticos == ["Não consegui abrir o glossário: sem programa associado"]
