from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QDialog, QLineEdit

from sigft.app import backends
from sigft.app_qt.views import lmr as tela_mod


class RoboFalso:
    def __init__(self, carregar=None, falha=None):
        self.passos, self.callbacks = [], {}
        self._carregar = carregar or (lambda c, a: (True, "DF", ["111", "222"], f"lidas 2 fichas de {a}"))
        self.falha = falha

    def carregar_dados_excel(self, caminho, aba):
        self.passos.append(("carregar", caminho, aba))
        return self._carregar(caminho, aba)

    def iniciar_driver(self):
        self.passos.append("driver")

    def abrir_portal(self):
        self.passos.append("portal")

    def processar_lista(self, selecionados, df, *, callback_log, callback_ask, callback_input, linha_inicio):
        self.callbacks = dict(log=callback_log, ask=callback_ask, input=callback_input, inicio=linha_inicio)
        if self.falha:
            raise self.falha
        callback_log("processando...")
        self.passos.append(("lista", tuple(selecionados), df))
        return ["111"], []

    def fechar_driver(self):
        self.passos.append("fechou")


@pytest.fixture
def tela(qt_interface, qtbot, monkeypatch):
    robo = RoboFalso()
    marcadas, abertos = [], []

    def marcar_status_pmib(caminho, completas, incompletas, *, retry_lock, callback_log):
        marcadas.append((caminho, completas, incompletas, retry_lock, callback_log))
        return 1, "1 ficha marcada no _STATUS_PMIB."

    modulo = SimpleNamespace(
        listar_abas=lambda caminho: ["Plan1", "LMR"],
        LMRAutomation=lambda: robo,
        marcar_status_pmib=marcar_status_pmib)
    monkeypatch.setattr(backends, "lmr_backend", modulo)

    def abrir(*a, **k):
        abertos.append((a, k))
        return "/tmp/LMR.xlsx"

    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", abrir)
    t = tela_mod.ModuloLMR()
    qtbot.addWidget(t)
    t.robo, t.marcadas, t.avisos, t.pausas, t.abertos, t.abas_pedidas = robo, marcadas, [], [], abertos, []
    monkeypatch.setattr(t, "avisar", lambda ti, m, tipo="info": t.avisos.append((tipo, ti, m)))
    monkeypatch.setattr(t, "pausar_e_esperar", lambda m, texto_botao=None: t.pausas.append(m))

    def escolher_aba(nome, abas):
        t.abas_pedidas.append((nome, abas))
        return "LMR"

    monkeypatch.setattr(t, "escolher_aba", escolher_aba)
    monkeypatch.setattr(t, "escolher_pmibs", lambda pmibs: ["222"])
    return t


def _esperar_fim(tela, qtbot, ultima):
    qtbot.waitUntil(lambda: "fechou" in tela.robo.passos, timeout=3000)
    qtbot.waitUntil(tela.btn_run.isEnabled, timeout=2000)
    qtbot.waitUntil(lambda: ultima in tela.console.toPlainText(), timeout=2000)
    return tela.console.toPlainText()


def test_textos_e_caixa_da_linha_inicial(tela):
    from sigft.app import theme
    assert tela.label_titulo.text() == "Automação LMR"
    assert tela.btn_run.text() == "Selecionar Excel e Iniciar"
    assert tela.picker_status.botao.text() == "Selecionar _STATUS_PMIB"
    assert tela.picker_status.label_status.text() == "Nenhum (o lote não será marcado na planilha)"
    assert tela.caminho_status_pmib is None
    r = tela._rotulos
    assert r["titulo"].text() == "Preenchimento Automático de LMR (Aplicações)"
    assert theme.COLORS["accent"] in r["titulo"].styleSheet()
    assert r["info"].text().startswith("Este módulo lê uma aba de um arquivo Excel")
    assert "#808080" in r["info"].styleSheet()                      # "gray" do Tk
    assert r["marcar"].text() == "Marcar o resultado no _STATUS_PMIB (opcional):"
    assert "#B3B3B3" in r["desligado"].styleSheet() and "font-size: 11px" in r["desligado"].styleSheet()
    assert r["script"].text() == "O script pedirá:\n1. Arquivo Excel LMR\n2. Seleção das Fichas (Checkbox)"
    assert isinstance(tela.caixa_linha_inicial, QCheckBox)
    assert tela.caixa_linha_inicial.text() == "Começar de um código específico"
    assert isinstance(tela.entry_linha_inicial, QLineEdit)
    assert tela.entry_linha_inicial.placeholderText() == "0"
    assert not tela.entry_linha_inicial.isEnabled()
    tela.caixa_linha_inicial.setChecked(True)
    assert tela.entry_linha_inicial.isEnabled()
    tela.entry_linha_inicial.setText("12")
    assert tela._linha_inicial_escolhida() == 12
    tela.caixa_linha_inicial.setChecked(False)
    assert tela.entry_linha_inicial.text() == "" and tela._linha_inicial_escolhida() is None


def test_linha_inicial_vazia_ou_invalida(tela, qtbot):
    tela.caixa_linha_inicial.setChecked(True)
    assert tela._linha_inicial_escolhida() is None
    tela.entry_linha_inicial.setText("abc")
    assert tela._linha_inicial_escolhida() is None
    qtbot.waitUntil(lambda: "Linha inicial 'abc' não é um número. Começando do 0."
                    in tela.console.toPlainText(), timeout=2000)


def test_picker_do_status_usa_a_memoria_de_pastas(tela, qtbot, monkeypatch):
    chamadas = []

    def falso(chave, categoria, **k):
        chamadas.append((chave, categoria, k["titulo"], k["filetypes"]))
        return "/pasta/_STATUS_PMIB.xlsx"

    monkeypatch.setattr(tela_mod.pickers.file_dialogs, "ask_open_file", falso)
    tela.picker_status.botao.click()
    assert chamadas == [("lmr.status_pmib", "excel", "Selecione o _STATUS_PMIB",
                         [("Excel", "*.xlsx *.xlsm")])]
    assert tela.caminho_status_pmib == "/pasta/_STATUS_PMIB.xlsx"
    qtbot.waitUntil(lambda: "_STATUS_PMIB selecionado: _STATUS_PMIB.xlsx"
                    in tela.console.toPlainText(), timeout=2000)


def test_fluxo_completo(tela, qtbot):
    from sigft.app.textos_dialogos import MSG_LOGIN_LMR
    tela.caminho_status_pmib = "/tmp/STATUS.xlsx"
    tela.caixa_linha_inicial.setChecked(True)
    tela.entry_linha_inicial.setText("7")
    tela.btn_run.click()
    texto = _esperar_fim(tela, qtbot, "1 ficha marcada no _STATUS_PMIB.")
    assert tela.abertos == [(("lmr.excel", "excel"),
                             {"titulo": "Selecione o Excel LMR", "filetypes": [("Excel", "*.xlsx")]})]
    assert tela.abas_pedidas == [("LMR.xlsx", ["Plan1", "LMR"])]
    assert tela.robo.passos == [("carregar", "/tmp/LMR.xlsx", "LMR"), "driver", "portal",
                                ("lista", ("222",), "DF"), "fechou"]
    assert tela.pausas == [MSG_LOGIN_LMR]
    assert tela.robo.callbacks["log"] == tela.log
    assert tela.robo.callbacks["ask"] == tela.perguntar_sim_nao
    assert tela.robo.callbacks["input"] == tela.pedir_texto
    assert tela.robo.callbacks["inicio"] == 7
    [(caminho, completas, incompletas, retry_lock, callback_log)] = tela.marcadas
    assert (caminho, completas, incompletas) == ("/tmp/STATUS.xlsx", ["111"], [])
    assert retry_lock == tela.perguntar_retry_excel and callback_log == tela.log
    assert tela.avisos == [("info", "Sucesso", "Processo concluído.")]
    ordem = ["Lendo LMR.xlsx (aba 'LMR')...", "lidas 2 fichas de LMR",
             "1 fichas selecionadas. Iniciando robô...", "Iniciando navegador...",
             "Carregando portal...", "processando...", "Automação LMR finalizada.",
             "Marcando o _STATUS_PMIB...", "1 ficha marcada no _STATUS_PMIB."]
    posicoes = [texto.index(linha) for linha in ordem]
    assert posicoes == sorted(posicoes)


def test_sem_status_avisa_que_a_planilha_nao_foi_marcada(tela, qtbot):
    tela.btn_run.click()
    texto = _esperar_fim(tela, qtbot, "[i] Nenhum _STATUS_PMIB selecionado.")
    assert "[i] Nenhum _STATUS_PMIB selecionado. A planilha não foi marcada." in texto
    assert tela.marcadas == [] and tela.robo.callbacks["inicio"] is None
    assert tela.avisos == [("info", "Sucesso", "Processo concluído.")]


def test_falha_na_planilha_nao_derruba_o_lote(tela, qtbot, monkeypatch):
    def quebra(*a, **k):
        raise PermissionError("travado")

    monkeypatch.setattr(backends.lmr_backend, "marcar_status_pmib", quebra)
    tela.caminho_status_pmib = "/tmp/STATUS.xlsx"
    tela.btn_run.click()
    texto = _esperar_fim(tela, qtbot, "Marque a planilha à mão.")
    assert "[!] Não consegui marcar o _STATUS_PMIB: PermissionError: travado" in texto
    assert "    O cadastro no portal FOI feito. Marque a planilha à mão." in texto
    assert tela.avisos == [("info", "Sucesso", "Processo concluído.")]


def test_erro_no_portal_vira_erro_fatal_e_fecha_o_driver(tela, qtbot):
    tela.robo.falha = RuntimeError("tabela sumiu")
    tela.btn_run.click()
    texto = _esperar_fim(tela, qtbot, "Erro Fatal LMR:")
    assert "Erro Fatal LMR: tabela sumiu" in texto and "Automação LMR finalizada." not in texto
    assert tela.robo.passos[-1] == "fechou" and tela.avisos == []


def test_selecao_vazia_cancela(tela, qtbot, monkeypatch):
    monkeypatch.setattr(tela, "escolher_pmibs", lambda pmibs: [])
    tela.btn_run.click()
    qtbot.waitUntil(lambda: "Seleção cancelada." in tela.console.toPlainText(), timeout=3000)
    assert "driver" not in tela.robo.passos
    qtbot.waitUntil(tela.btn_run.isEnabled, timeout=2000)


def test_cancelar_a_aba_nao_le_nada(tela, monkeypatch):
    monkeypatch.setattr(tela, "escolher_aba", lambda nome, abas: None)
    tela.btn_run.click()
    assert tela.robo.passos == [] and tela.btn_run.isEnabled()


def test_cancelar_o_arquivo_nao_faz_nada(tela, monkeypatch):
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "")
    tela.btn_run.click()
    assert tela.abas_pedidas == [] and tela.robo.passos == []


def test_falha_ao_ler_o_excel_avisa_com_erro(tela, qtbot):
    tela.robo._carregar = lambda c, a: (False, None, [], "coluna FICHA PMIB ausente")
    tela.btn_run.click()
    qtbot.waitUntil(lambda: tela.avisos != [], timeout=3000)
    assert tela.avisos == [("erro", "Erro", "Falha ao ler Excel:\ncoluna FICHA PMIB ausente")]
    qtbot.waitUntil(tela.btn_run.isEnabled, timeout=2000)
    assert "driver" not in tela.robo.passos


def test_excel_sem_pmib(tela, qtbot, monkeypatch):
    tela.robo._carregar = lambda c, a: (True, "DF", [], "0 linhas")
    escolhidos = []
    monkeypatch.setattr(tela, "escolher_pmibs", lambda p: escolhidos.append(p) or ["x"])
    tela.btn_run.click()
    qtbot.waitUntil(lambda: "Nenhum PMIB encontrado." in tela.console.toPlainText(), timeout=3000)
    qtbot.waitUntil(tela.btn_run.isEnabled, timeout=2000)
    assert escolhidos == []


def test_erro_no_pre_processamento(tela, qtbot):
    def quebra(c, a):
        raise ValueError("planilha corrompida")

    tela.robo._carregar = quebra
    tela.btn_run.click()
    qtbot.waitUntil(lambda: "Erro Pré-processamento: planilha corrompida"
                    in tela.console.toPlainText(), timeout=3000)
    qtbot.waitUntil(tela.btn_run.isEnabled, timeout=2000)


def test_arquivo_sem_abas(tela, monkeypatch):
    monkeypatch.setattr(backends.lmr_backend, "listar_abas", lambda c: [])
    erros = []
    monkeypatch.setattr(tela_mod.QMessageBox, "critical", staticmethod(lambda *a: erros.append(a[1:])))
    tela.btn_run.click()
    assert erros == [("Erro", "O arquivo não tem nenhuma aba.")]


def test_abas_ilegiveis(tela, monkeypatch):
    def quebra(c):
        raise OSError("arquivo corrompido")

    monkeypatch.setattr(backends.lmr_backend, "listar_abas", quebra)
    erros = []
    monkeypatch.setattr(tela_mod.QMessageBox, "critical", staticmethod(lambda *a: erros.append(a[1:])))
    tela.btn_run.click()
    assert erros == [("Erro", "Não consegui ler as abas do arquivo:\narquivo corrompido")]


def test_backend_que_nao_carregou_nao_abre_o_seletor(tela, monkeypatch):
    monkeypatch.setattr(backends, "lmr_backend", None)
    monkeypatch.setattr(backends, "falhas", {"lmr_backend": ImportError("sem selenium")})
    avisos = []
    monkeypatch.setattr("sigft.app_qt.widgets.module_frame.QMessageBox.warning",
                        staticmethod(lambda *a: avisos.append(a[1])))
    tela.btn_run.click()
    assert avisos == ["Módulo indisponível"] and tela.abertos == []


def test_embutida_escreve_no_console_do_pai(qt_interface, qtbot):
    from sigft.app_qt.widgets.console import ConsoleFrame
    console = ConsoleFrame()
    qtbot.addWidget(console)
    t = tela_mod.ModuloLMR(embutida=True, console_externo=console)
    qtbot.addWidget(t)
    assert t.label_titulo is None and t.console is console
    t.log("oi")
    qtbot.waitUntil(lambda: "oi" in console.toPlainText(), timeout=2000)


# --- as duas escolhas, com as janelas de verdade ---------------------------------

def test_escolher_aba_pela_janela(qt_interface, qtbot, monkeypatch):
    t = tela_mod.ModuloLMR()
    qtbot.addWidget(t)
    vistos = []

    def aceitar(dialogo):
        vistos.append((dialogo.windowTitle(), dialogo.rotulo_arquivo.text(), dialogo.rotulo_pergunta.text(),
                       [dialogo.menu.itemText(i) for i in range(dialogo.menu.count())]))
        dialogo.menu.setCurrentIndex(1)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(tela_mod.DialogoDaAba, "exec", aceitar)
    assert t.escolher_aba("LMR.xlsx", ["Plan1", "LMR"]) == "LMR"
    assert vistos == [("Escolha a aba", "LMR.xlsx", "Qual aba contém as aplicações de LMR?",
                       ["Plan1", "LMR"])]
    monkeypatch.setattr(tela_mod.DialogoDaAba, "exec", lambda d: QDialog.DialogCode.Rejected)
    assert t.escolher_aba("LMR.xlsx", ["Plan1", "LMR"]) is None


def test_escolher_pmibs_pela_janela(qt_interface, qtbot, monkeypatch):
    t = tela_mod.ModuloLMR()
    qtbot.addWidget(t)
    vistos = []

    def aceitar(dialogo):
        vistos.append((dialogo.windowTitle(), dialogo.rotulo.text()))
        dialogo.lista.item(1).setCheckState(Qt.CheckState.Checked)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(tela_mod.SelecaoComCaixasDialog, "exec", aceitar)
    assert t.escolher_pmibs(["111", "222"]) == ["222"]
    assert vistos == [("Selecione as Fichas", "Selecione os PMIBs para processar:")]

    def marcar_e_fechar(dialogo):
        dialogo.lista.item(0).setCheckState(Qt.CheckState.Checked)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(tela_mod.SelecaoComCaixasDialog, "exec", marcar_e_fechar)
    assert t.escolher_pmibs(["111", "222"]) == []          # fechar no "X" = nenhuma


# --- paridade visual ------------------------------------------------------------------

@pytest.fixture
def folha(qt_interface):
    from sigft.app_qt import estilo
    anterior = qt_interface.styleSheet()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    yield
    qt_interface.setStyleSheet(anterior)


def _pos(w, base):
    return w.mapTo(base, w.rect().topLeft())


def test_medidas_iguais_as_do_customtkinter(folha, qtbot):
    # Tela antiga avulsa (CustomTkinter, 1280x850, sondada com winfo_*): cartão
    # 20 px abaixo do conteúdo; entre as peças, a SOMA dos pady vizinhos (10, 20,
    # 6, 30, 14, 8, 20) e 20 nas pontas; seletor 240x28; botão 300x50; linha do
    # código (interruptor 24 de altura + 10 + campo 70x28) centrada.
    t = tela_mod.ModuloLMR()
    qtbot.addWidget(t)
    t.resize(1003, 850)
    t.show()
    qtbot.waitExposed(t)

    def y(w):
        return _pos(w, t).y()

    def base(w):
        return y(w) + w.height()

    r = t._rotulos
    cartao = t.btn_run.parentWidget()
    assert y(cartao) - y(t.content) == 20
    assert y(r["titulo"]) - y(cartao) == 20 and r["titulo"].height() == 28
    assert y(r["info"]) - base(r["titulo"]) == 10
    assert y(r["marcar"]) - base(r["info"]) == 20 and r["marcar"].height() == 28
    assert y(t.picker_status) - base(r["marcar"]) == 6
    assert (t.picker_status.botao.width(), t.picker_status.botao.height()) == (240, 28)
    assert y(t.btn_run) - base(t.picker_status) == 30
    assert (t.btn_run.width(), t.btn_run.height()) == (300, 50)
    assert y(t.entry_linha_inicial) - base(t.btn_run) == 14
    assert (t.entry_linha_inicial.width(), t.entry_linha_inicial.height()) == (70, 28)
    assert t.caixa_linha_inicial.height() == 24
    assert y(t.caixa_linha_inicial) - y(t.entry_linha_inicial) == 2
    assert y(r["desligado"]) - base(t.entry_linha_inicial) == 8
    assert y(r["script"]) - base(r["desligado"]) == 20
    assert base(cartao) - base(r["script"]) == 20
    meio = _pos(cartao, t).x() + cartao.width() / 2
    assert abs(_pos(t.btn_run, t).x() + 150 - meio) <= 1
    esquerda = _pos(t.caixa_linha_inicial, t).x()
    direita = _pos(t.entry_linha_inicial, t).x() + 70
    assert abs((esquerda + direita) / 2 - meio) <= 1
    assert _pos(t.entry_linha_inicial, t).x() - (esquerda + t.caixa_linha_inicial.width()) == 10
    seletor = _pos(t.picker_status, t).x() + t.picker_status.width() / 2
    assert abs(seletor - meio) <= 1


def test_janela_da_aba_tem_as_medidas_do_ctk(folha, qtbot):
    # CTkToplevel 420x220: nome do arquivo (12 negrito) em y=20, pergunta (12, gray70)
    # em y=52, menu 300x28 em (60, 97), "Ler esta aba" em (60, 145), "Cancelar" em (60, 183).
    d = tela_mod.DialogoDaAba(None, nome_arquivo="LMR_Aplicacoes_2026.xlsx", abas=["Plan1", "LMR"])
    qtbot.addWidget(d)
    d.show()
    qtbot.waitExposed(d)

    def caixa(w):
        p = _pos(w, d)
        return (p.x(), p.y(), w.width(), w.height())

    assert (d.width(), d.height()) == (420, 220)
    assert caixa(d.rotulo_arquivo)[1::2] == (20, 28)
    assert caixa(d.rotulo_pergunta)[1::2] == (52, 28)
    assert "#B3B3B3" in d.rotulo_pergunta.styleSheet()
    assert caixa(d.menu) == (60, 97, 300, 28)
    assert caixa(d.botao_ler) == (60, 145, 300, 28)
    assert caixa(d.botao_cancelar) == (60, 183, 300, 28)
    assert d.botao_ler.text() == "Ler esta aba" and d.botao_cancelar.text() == "Cancelar"
    assert d.aba_escolhida() == "Plan1"
