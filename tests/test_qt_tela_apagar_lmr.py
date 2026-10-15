from types import SimpleNamespace

import pytest

from sigft.app import backends
from sigft.app_qt.views import apagar_lmr as tela_mod


class RoboFalso:
    def __init__(self, limpou=True, falha=None):
        self.limpou, self.falha, self.passos = limpou, falha, []

    def iniciar_driver(self):
        self.passos.append("driver")

    def abrir_portal(self):
        self.passos.append("portal")

    def executar_limpeza(self, pmib, callback_log=None):
        if self.falha:
            raise self.falha
        callback_log("apagando...")
        self.passos.append(("limpeza", pmib))
        return self.limpou

    def fechar_driver(self):
        self.passos.append("fechou")


@pytest.fixture
def tela(qt_interface, qtbot, monkeypatch):
    t = tela_mod.ModuloApagarLMR()
    qtbot.addWidget(t)
    t.avisos, t.pausas, t.perguntas = [], [], []
    t.resposta = True
    monkeypatch.setattr(t, "avisar", lambda ti, m, tipo="info": t.avisos.append((tipo, ti, m)))
    monkeypatch.setattr(t, "pausar_e_esperar",
                        lambda m, texto_botao=None: t.pausas.append((m, texto_botao)))

    def perguntar(ti, m):
        t.perguntas.append((ti, m))
        return t.resposta

    monkeypatch.setattr(t, "perguntar_sim_nao", perguntar)
    return t


def _robo(monkeypatch, limpou=True, falha=None, falha_status=None):
    robo = RoboFalso(limpou, falha)
    limpezas = []

    def limpar_status_pmib(caminho, pmibs, *, retry_lock, callback_log):
        if falha_status:
            raise falha_status
        limpezas.append((caminho, pmibs, retry_lock, callback_log))
        return 1, "1 ficha limpa no _STATUS_PMIB."

    modulo = SimpleNamespace(ApagarLMRAutomation=lambda: robo, limpar_status_pmib=limpar_status_pmib)
    monkeypatch.setattr(backends, "apagar_lmr_backend", modulo)
    return robo, limpezas


def _rodar(tela, qtbot, robo, pmib, ultima):
    """Roda o lote e devolve o console depois que `ultima` foi escrita nele.

    O console escreve em lote, alguns ms depois do `log()`: daí a espera.
    """
    tela.entry_pmib.setText(pmib)
    tela.btn_run.click()
    qtbot.waitUntil(lambda: "fechou" in robo.passos, timeout=3000)
    qtbot.waitUntil(tela.btn_run.isEnabled, timeout=2000)
    qtbot.waitUntil(lambda: ultima in tela.console.toPlainText(), timeout=2000)
    return tela.console.toPlainText()


def test_titulo_vermelho_e_textos(tela):
    from sigft.app import theme
    assert tela.label_titulo.text() == "Apagar Aplicações LMR"
    assert theme.COLORS["danger"] in tela.label_titulo.styleSheet()
    assert tela.entry_pmib.placeholderText() == "Ex: 4500063671.1234"
    assert tela.entry_pmib.width() == 250
    assert tela.btn_run.text() == "INICIAR LIMPEZA"
    assert tela.picker_status.botao.text() == "Selecionar _STATUS_PMIB"
    assert tela.picker_status.label_status.text() == "Nenhum (a planilha não será alterada)"
    assert tela.caminho_status is None


def test_picker_do_status_usa_a_memoria_de_pastas(tela, qtbot, monkeypatch):
    chamadas = []

    def falso(chave, categoria, **k):
        chamadas.append((chave, categoria, k["titulo"], k["filetypes"]))
        return "/pasta/_STATUS_PMIB.xlsx"

    monkeypatch.setattr(tela_mod.pickers.file_dialogs, "ask_open_file", falso)
    tela.picker_status.botao.click()
    assert chamadas == [("apagar_lmr.status_pmib", "excel", "Selecione o _STATUS_PMIB (opcional)",
                         [("Excel", "*.xlsx;*.xlsm")])]
    assert tela.caminho_status == "/pasta/_STATUS_PMIB.xlsx"
    qtbot.waitUntil(lambda: "_STATUS_PMIB selecionado: /pasta/_STATUS_PMIB.xlsx"
                    in tela.console.toPlainText(), timeout=2000)


def test_pmib_vazio_avisa_e_nao_roda(tela, monkeypatch):
    robo, _ = _robo(monkeypatch)
    avisos = []
    monkeypatch.setattr(tela_mod.QMessageBox, "warning", staticmethod(lambda *a: avisos.append(a[1:])))
    tela.entry_pmib.setText("   ")
    tela.btn_run.click()
    assert avisos == [("Aviso", "Digite o código PMIB.")]
    assert tela.perguntas == [] and robo.passos == []


def test_nao_confirmar_nao_roda(tela, monkeypatch):
    robo, _ = _robo(monkeypatch)
    tela.resposta = False
    tela.entry_pmib.setText("123")
    tela.btn_run.click()
    assert tela.perguntas == [("Confirmar", "Tem certeza que deseja APAGAR todas as aplicações do PMIB 123?")]
    assert robo.passos == [] and tela.console.toPlainText() == ""
    assert tela.btn_run.isEnabled()


def test_backend_que_nao_carregou_nao_pergunta(tela, monkeypatch):
    monkeypatch.setattr(backends, "apagar_lmr_backend", None)
    monkeypatch.setattr(backends, "falhas", {"apagar_lmr_backend": ImportError("sem selenium")})
    avisos = []
    monkeypatch.setattr("sigft.app_qt.widgets.module_frame.QMessageBox.warning",
                        staticmethod(lambda *a: avisos.append(a[1])))
    tela.entry_pmib.setText("123")
    tela.btn_run.click()
    assert avisos == ["Módulo indisponível"]
    assert tela.perguntas == []


def test_fluxo_completo_com_status(tela, qtbot, monkeypatch):
    from sigft.app.textos_dialogos import MSG_LOGIN_APAGAR_LMR
    robo, limpezas = _robo(monkeypatch, limpou=True)
    tela.caminho_status = "/tmp/STATUS.xlsx"
    texto = _rodar(tela, qtbot, robo, " 4500063671.1234 ", "1 ficha limpa no _STATUS_PMIB.")
    assert robo.passos == ["driver", "portal", ("limpeza", "4500063671.1234"), "fechou"]
    assert tela.perguntas == [
        ("Confirmar", "Tem certeza que deseja APAGAR todas as aplicações do PMIB 4500063671.1234?")]
    assert tela.pausas == [(MSG_LOGIN_APAGAR_LMR, "COMEÇAR A EXCLUSÃO")]
    assert [(c, p) for c, p, *_ in limpezas] == [("/tmp/STATUS.xlsx", ["4500063671.1234"])]
    _c, _p, retry_lock, callback_log = limpezas[0]
    assert retry_lock == tela.perguntar_retry_excel and callback_log == tela.log
    assert tela.avisos == [("info", "Sucesso", "Limpeza concluída.")]
    ordem = ["Preparando limpeza para: 4500063671.1234...", "Iniciando navegador...",
             "Carregando portal...", "Iniciando varredura...", "apagando...",
             "Processo Finalizado.", "   1 ficha limpa no _STATUS_PMIB."]
    posicoes = [texto.index(linha) for linha in ordem]
    assert posicoes == sorted(posicoes)


def test_sem_status_nao_mexe_na_planilha(tela, qtbot, monkeypatch):
    robo, limpezas = _robo(monkeypatch, limpou=True)
    texto = _rodar(tela, qtbot, robo, "1", "Processo Finalizado.")
    assert limpezas == [] and "_STATUS_PMIB" not in texto
    assert tela.avisos == [("info", "Sucesso", "Limpeza concluída.")]


def test_limpeza_incompleta_nao_mexe_no_status(tela, qtbot, monkeypatch):
    robo, limpezas = _robo(monkeypatch, limpou=False)
    tela.caminho_status = "/tmp/STATUS.xlsx"
    texto = _rodar(tela, qtbot, robo, "1", "[i] A exclusão não terminou limpa.")
    assert limpezas == []
    assert ("   [i] A exclusão não terminou limpa. O _STATUS_PMIB NÃO foi alterado. A marcação "
            "continua como estava, o que é o certo enquanto houver aplicação na ficha.") in texto
    assert tela.avisos == [("info", "Sucesso", "Limpeza concluída.")]


def test_falha_na_planilha_nao_derruba_o_resultado(tela, qtbot, monkeypatch):
    robo, _ = _robo(monkeypatch, falha_status=PermissionError("travado"))
    tela.caminho_status = "/tmp/STATUS.xlsx"
    texto = _rodar(tela, qtbot, robo, "1", "[!] Não consegui")
    assert "   [!] Não consegui atualizar o _STATUS_PMIB: travado" in texto
    assert tela.avisos == [("info", "Sucesso", "Limpeza concluída.")]


def test_erro_no_portal_vira_erro_fatal_e_fecha_o_driver(tela, qtbot, monkeypatch):
    robo, limpezas = _robo(monkeypatch, falha=RuntimeError("lixeira sumiu"))
    tela.caminho_status = "/tmp/STATUS.xlsx"
    texto = _rodar(tela, qtbot, robo, "1", "Erro Fatal:")
    assert "Erro Fatal: lixeira sumiu" in texto and "Processo Finalizado." not in texto
    assert robo.passos == ["driver", "portal", "fechou"]
    assert limpezas == [] and tela.avisos == []


def test_embutida_escreve_no_console_do_pai(qt_interface, qtbot):
    from sigft.app_qt.widgets.console import ConsoleFrame
    console = ConsoleFrame()
    qtbot.addWidget(console)
    t = tela_mod.ModuloApagarLMR(embutida=True, console_externo=console)
    qtbot.addWidget(t)
    assert t.label_titulo is None and t.console is console
    t.log("oi")
    qtbot.waitUntil(lambda: "oi" in console.toPlainText(), timeout=2000)


def test_medidas_iguais_as_do_interface_antiga(qt_interface, qtbot):
    # Medidas da tela antiga (interface antiga, 1280x850, sondadas com winfo_*):
    # cartão 20 px abaixo do conteúdo; entre as peças, a SOMA dos pady vizinhos
    # (5, 30, 25, 5, 30, 20) e 20 px nas pontas; campo do PMIB 250x28; botão
    # 350x50; seletor 220x28. Linha do PMIB e seletor centrados no cartão.
    from sigft.app_qt import estilo

    anterior = qt_interface.styleSheet()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    try:
        t = tela_mod.ModuloApagarLMR()
        qtbot.addWidget(t)
        t.resize(1003, 850)
        t.show()
        qtbot.waitExposed(t)

        def pos(w):
            return w.mapTo(t, w.rect().topLeft())

        def base(w):
            return pos(w).y() + w.height()

        cartao = t.btn_run.parentWidget()
        assert pos(cartao).y() - pos(t.content).y() == 20
        assert (t.entry_pmib.width(), t.entry_pmib.height()) == (250, 28)
        assert (t.btn_run.width(), t.btn_run.height()) == (350, 50)
        assert (t.picker_status.botao.width(), t.picker_status.botao.height()) == (220, 28)
        r = t._rotulos
        assert pos(r["atencao"]).y() - pos(cartao).y() == 20
        assert pos(r["irreversivel"]).y() - base(r["atencao"]) == 5
        assert pos(t.entry_pmib).y() - base(r["irreversivel"]) == 30
        assert pos(r["opcional"]).y() - base(t.entry_pmib) == 25
        assert pos(t.picker_status).y() - base(r["opcional"]) == 5
        assert pos(t.btn_run).y() - base(t.picker_status) == 30
        assert pos(r["passos"]).y() - base(t.btn_run) == 20
        assert base(cartao) - base(r["passos"]) == 20
        meio = pos(cartao).x() + cartao.width() / 2
        assert abs(pos(t.btn_run).x() + 175 - meio) <= 1
        esquerda, direita = pos(r["pmib"]).x(), pos(t.entry_pmib).x() + 250
        assert abs((esquerda + direita) / 2 - meio) <= 1
        assert pos(t.entry_pmib).x() - (esquerda + r["pmib"].width()) == 20
        assert pos(t.picker_status.botao).x() > pos(cartao).x() + 100
    finally:
        qt_interface.setStyleSheet(anterior)
