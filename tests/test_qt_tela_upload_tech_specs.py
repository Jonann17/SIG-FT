"""Tela "Upload Características Técnicas" na interface Qt.

Os backends são dublês (o portal não se testa daqui): o que se prova é a TELA
-- textos, validações, a ordem das mensagens, quem habilita o quê, e que o
worker só fala com a pessoa pela thread da interface.
"""
import json
import threading
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QMessageBox

from sigft.app import backends, theme
from sigft.app.textos_dialogos import LOGIN_NECESSARIO, MSG_LOGIN_SOLTAR_ROBO, msg_ficha_preenchida
from sigft.app_qt.views import upload_tech_specs as tela_mod
from sigft.app_qt.views._upload_comum import MSG_ROBO_OCUPADO

ABA_IA = "Processamento IA (Gerar JSON)"
ABA_WEB = "Robô Web (Preencher Portal)"
SIM, NAO = QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No


class ControladorFalso:
    """`TechSpecsController` de mentira."""

    def __init__(self, *, resultados=None, salvou=True, falha_rpa=None):
        self.resultados, self.salvou, self.falha_rpa = resultados, salvou, falha_rpa
        self.chamadas = []

    def executar_pipeline_ia(self, api_key, files, status, master, completos, callback_log=None):
        self.chamadas.append(("ia", api_key, list(files), status, master, completos))
        callback_log("Iniciando motor de IA...")
        return self.resultados

    def salvar_json(self, dados, caminho, callback_log=None):
        self.chamadas.append(("salvar", caminho))
        return self.salvou

    def executar_pipeline_rpa(self, dados, caminho_status, callback_log=None, callback_pause=None):
        self.chamadas.append(("rpa", dados, caminho_status))
        if self.falha_rpa:
            raise self.falha_rpa
        callback_pause("LOGIN_NECESSARIO")
        callback_pause("4500063671.0001")
        callback_log("Fim do processo de RPA.")

    def cancelar_processo_ia(self):
        self.chamadas.append("cancelar_ia")

    def cancelar_processo_web(self):
        self.chamadas.append("cancelar_web")


def _backend(monkeypatch, controlador):
    criados = []

    def novo():
        criados.append(controlador)
        return controlador

    monkeypatch.setattr(backends, "upload_tech_specs_backend", SimpleNamespace(TechSpecsController=novo))
    return criados


@pytest.fixture
def tela(qt_interface, qtbot, monkeypatch):
    controller = SimpleNamespace(get_key=lambda k: {"GEMINI": "chave-123"}.get(k, ""))
    t = tela_mod.ModuloUploadTechSpecs(None, controller)
    qtbot.addWidget(t)
    t.avisos, t.pausas = [], []
    monkeypatch.setattr(t, "avisar", lambda ti, m, tipo="info": t.avisos.append((tipo, ti, m)))
    monkeypatch.setattr(t, "pausar_e_esperar", lambda msg, texto_botao=None: t.pausas.append(
        (threading.current_thread() is threading.main_thread(), msg)))
    return t


@pytest.fixture
def caixas(monkeypatch):
    registro = SimpleNamespace(chamadas=[], respostas=[])

    def pergunta(_parent, titulo, texto, *a, **k):
        registro.chamadas.append(("pergunta", titulo, texto))
        return registro.respostas.pop(0)

    for nome, tipo in (("warning", "aviso"), ("critical", "erro"), ("information", "info")):
        monkeypatch.setattr(tela_mod.QMessageBox, nome, staticmethod(
            lambda _p, ti, te, *a, _t=tipo, **k: registro.chamadas.append((_t, ti, te))))
    monkeypatch.setattr(tela_mod.QMessageBox, "question", staticmethod(pergunta))
    return registro


@pytest.fixture
def selecao(monkeypatch):
    abertas = []

    class Dialogo:
        def __init__(self, parent, **kw):
            self.kw = kw
            abertas.append(self)

    monkeypatch.setattr(tela_mod.dialogos_selecao, "SelecaoMultiplaDialog", Dialogo)
    return abertas


def _texto(t):
    return t.console.toPlainText()


def _com_fila(t, monkeypatch, caminhos=("/d/a.xlsx", "/d/b.xlsx")):
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_files", lambda *a, **k: list(caminhos))
    t.fila_fichas.adicionar()


# ---------------------------------------------------------------------------
# Montagem e seletores
# ---------------------------------------------------------------------------
def test_monta_com_os_textos(tela):
    assert tela.label_titulo.text() == "Upload Características Técnicas"
    assert tela.rotulo_config.text() == "Configuração Global"
    assert tela.btn_status.text() == "Selecionar _STATUS_PMIB"
    assert tela.lbl_status_status.text() == "Não selecionado"
    assert tela.switch_completos.text() == "Forçar processamento de fichas 'COMPLETO'"
    assert list(tela.tabview.abas) == [ABA_IA, ABA_WEB] and tela.tabview.get() == ABA_IA
    assert tela.rotulo_referencia.text() == "Referência para IA"
    assert tela.btn_master.text() == "Selecionar PDM's SAM-GM"
    assert tela.lbl_master_status.text() == "Não selecionado"
    assert tela.fila_fichas.label_contador.text() == "Fichas Selecionadas (0)"
    assert tela.btn_ia.text() == "INICIAR PROCESSAMENTO IA" and tela.btn_ia.isEnabled()
    assert tela.btn_parar_ia.text() == "PARAR" and not tela.btn_parar_ia.isEnabled()
    assert tela.rotulo_web.text() == (
        "Lê um arquivo JSON pronto e inicia o Selenium para preencher o Portal Itaipu.")
    assert tela.btn_web_mem.text() == "Usar Dados Recém Processados (Memória)"
    assert tela.btn_web_file.text() == "Carregar JSON Salvo no Computador"
    assert tela.btn_parar_web.text() == "PARAR ROBÔ WEB" and not tela.btn_parar_web.isEnabled()
    assert tela.caminho_status == tela.caminho_master == ""
    assert tela.api_key == "chave-123"


def test_abre_sem_backend_e_o_controlador_nasce_no_clique(qt_interface, qtbot, monkeypatch):
    # Lá o controlador nascia no __init__: sem o backend a tela nem abria.
    monkeypatch.setattr(backends, "upload_tech_specs_backend", None)
    t = tela_mod.ModuloUploadTechSpecs()
    qtbot.addWidget(t)
    assert t.tech_controller is None and t.api_key == ""


def test_seletores(tela, monkeypatch):
    chamadas = []
    respostas = iter(["/d/_STATUS_PMIB.xlsx", "/d/PDMs SAM-GM.xlsx"])

    def falso(chave, categoria, **k):
        chamadas.append((chave, categoria, k))
        return next(respostas)

    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", falso)
    tela.btn_status.click()
    tela.btn_master.click()
    assert chamadas == [
        ("upload_tech_specs.status_pmib", "excel",
         {"titulo": "Selecione _STATUS_PMIB", "filetypes": [("Excel", "*.xlsx;*.xlsm")]}),
        ("upload_tech_specs.master", "excel",
         {"titulo": "Selecione Master PDMs (Template)", "filetypes": [("Excel", "*.xlsx;*.xlsm")]}),
    ]
    assert tela.caminho_status == "/d/_STATUS_PMIB.xlsx"
    assert tela.caminho_master == "/d/PDMs SAM-GM.xlsx"
    assert tela.lbl_status_status.text() == "_STATUS_PMIB.xlsx"
    assert tela.lbl_master_status.text() == "PDMs SAM-GM.xlsx"
    for rotulo, botao in ((tela.lbl_status_status, tela.btn_status), (tela.lbl_master_status, tela.btn_master)):
        assert theme.COLORS["accent"] in rotulo.styleSheet()
        assert theme.COLORS["primary"] in botao.styleSheet()


def test_fila_loga_as_tres_acoes(tela, monkeypatch, qtbot):
    pedidos = []

    def falso(chave, categoria, **k):
        pedidos.append((chave, categoria, k["titulo"], k["filetypes"]))
        return ["/d/a.xlsx", "/d/b.xlsx", "/d/c.xlsx"]

    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_files", falso)
    tela.fila_fichas.botao_adicionar.click()
    assert pedidos == [("upload_tech_specs.fichas", "excel", "Selecione as Fichas PMIB",
                        [("Excel", "*.xlsx;*.xlsm")])]
    tela.fila_fichas.listbox.item(1).setSelected(True)
    tela.fila_fichas.botao_remover.click()
    tela.fila_fichas.botao_limpar.click()
    qtbot.waitUntil(lambda: "removidas" in _texto(tela), timeout=2000)
    assert _texto(tela).splitlines() == [
        "> 3 arquivos selecionados. Total na fila: 3",
        "> 1 arquivos removidos da fila. Total na fila: 2",
        "> Todas as fichas foram removidas da fila.",
    ]


# ---------------------------------------------------------------------------
# IA (aba 1)
# ---------------------------------------------------------------------------
def test_iniciar_ia_exige_status_master_e_fichas(tela, caixas):
    tela.btn_ia.click()
    tela.caminho_status = "/d/s.xlsx"
    tela.btn_ia.click()
    tela.caminho_master = "/d/m.xlsx"
    tela.btn_ia.click()
    assert caixas.chamadas == [
        ("aviso", "Aviso", "Por favor, selecione a planilha de _STATUS_PMIB."),
        ("aviso", "Aviso", "Por favor, selecione a planilha Master PDMs."),
        ("aviso", "Aviso", "Por favor, adicione pelo menos uma ficha à lista."),
    ]


def test_backend_indisponivel_avisa_e_nao_comeca(tela, caixas, monkeypatch):
    monkeypatch.setattr(backends, "upload_tech_specs_backend", None)
    tela.caminho_status, tela.caminho_master = "/d/s.xlsx", "/d/m.xlsx"
    _com_fila(tela, monkeypatch)
    tela.btn_ia.click()
    assert caixas.chamadas[-1][:2] == ("aviso", "Módulo indisponível")
    assert tela.btn_ia.isEnabled() and not tela.btn_parar_ia.isEnabled()


def _rodar_ia(tela, qtbot, monkeypatch, controlador, *, completos=False):
    _backend(monkeypatch, controlador)
    tela.caminho_status, tela.caminho_master = "/d/s.xlsx", "/d/m.xlsx"
    _com_fila(tela, monkeypatch)
    tela.switch_completos.setChecked(completos)
    tela.btn_ia.click()
    assert not tela.btn_ia.isEnabled() and tela.btn_parar_ia.isEnabled()
    qtbot.waitUntil(lambda: tela.btn_ia.isEnabled() and not tela.btn_parar_ia.isEnabled(), timeout=3000)
    qtbot.wait(100)


def test_ia_sem_resultados(tela, caixas, qtbot, monkeypatch):
    ctrl = ControladorFalso(resultados=[])
    _rodar_ia(tela, qtbot, monkeypatch, ctrl, completos=True)
    assert ctrl.chamadas == [("ia", "chave-123", ["/d/a.xlsx", "/d/b.xlsx"], "/d/s.xlsx", "/d/m.xlsx", True)]
    assert _texto(tela).splitlines()[1:] == ["> Iniciando processamento de 2 arquivos...",
                                             "> Iniciando motor de IA..."]
    assert caixas.chamadas == [("info", "Aviso", "Nenhum dado gerado. Verifique o console.")]


def test_ia_erro_fatal(tela, caixas, qtbot, monkeypatch):
    class Quebra(ControladorFalso):
        def executar_pipeline_ia(self, *a, **k):
            raise RuntimeError("cota esgotada")

    _rodar_ia(tela, qtbot, monkeypatch, Quebra())
    assert "> Erro Fatal IA: cota esgotada" in _texto(tela)
    assert caixas.chamadas == []


def test_ia_salva_o_json_e_vai_direto_ao_robo(tela, caixas, qtbot, monkeypatch):
    dados = [{"METADATA": {"PMIB": "1"}}]
    ctrl = ControladorFalso(resultados=dados)
    pedidos = []
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_save_file",
                        lambda chave, cat, **k: pedidos.append((chave, cat, k)) or "/d/r.json")
    iniciados = []
    monkeypatch.setattr(tela, "_start_web_process", iniciados.append)
    caixas.respostas[:] = [SIM]
    _rodar_ia(tela, qtbot, monkeypatch, ctrl)
    assert pedidos == [("upload_tech_specs.salvar_json", "json",
                        {"titulo": "Salvar JSON de Resultados", "defaultextension": ".json",
                         "filetypes": [("JSON", "*.json")]})]
    assert ctrl.chamadas[-1] == ("salvar", "/d/r.json")
    assert caixas.chamadas == [("pergunta", "Continuar",
                                "Dados salvos! Deseja pular para a Aba 2 e iniciar o Robô Web agora?")]
    assert "> Sucesso! 1 fichas geradas prontas para o robô." in _texto(tela)
    assert tela.dados_em_memoria == dados
    # Lá a tela pula a janela de seleção: vai direto com tudo o que gerou.
    assert tela.tabview.get() == ABA_WEB and iniciados == [dados]


def test_ia_sem_salvar(tela, caixas, qtbot, monkeypatch):
    ctrl = ControladorFalso(resultados=[{"METADATA": {}}], salvou=False)
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_save_file", lambda *a, **k: "/d/r.json")
    _rodar_ia(tela, qtbot, monkeypatch, ctrl)
    assert caixas.chamadas == [] and tela.tabview.get() == ABA_IA


def test_parar_ia(tela, caixas, monkeypatch):
    ctrl = ControladorFalso()
    tela.tech_controller = ctrl
    tela.btn_parar_ia.setEnabled(True)
    caixas.respostas[:] = [SIM]
    tela.btn_parar_ia.click()
    assert ctrl.chamadas == ["cancelar_ia"] and not tela.btn_parar_ia.isEnabled()
    assert caixas.chamadas == [("pergunta", "Confirmar", "Deseja realmente interromper o processo da IA?\n"
                                                         "O que já foi processado será salvo.")]


# ---------------------------------------------------------------------------
# Robô Web (aba 2)
# ---------------------------------------------------------------------------
def test_robo_sem_dados(tela, caixas, selecao):
    tela.btn_web_mem.click()
    assert caixas.chamadas == [("aviso", "Aviso", "Não há dados para iniciar a automação.")]
    assert selecao == []


def test_selecao_de_fichas(tela, selecao, monkeypatch):
    iniciados = []
    monkeypatch.setattr(tela, "_start_web_process", iniciados.append)
    dados = [{"METADATA": {"PMIB": "A", "ARQUIVO_ORIGEM": "a.xlsx"}}, {}]
    tela.dados_em_memoria = dados
    tela.btn_web_mem.click()
    kw = selecao[0].kw
    assert kw["itens"] == ["PMIB: A | a.xlsx", "PMIB: N/A | N/A"]
    assert kw["titulo"] == "Selecione as Fichas para Processar"
    assert kw["instrucao"] == "Selecione quais fichas do JSON deseja enviar para o site:"
    assert kw["geometria"] == "600x450" and kw["modal"] and kw["com_selecionar_todos"]
    assert kw["devolver_indices"] and kw["fonte_lista"] == ("Consolas", 11)
    kw["ao_confirmar"]([1])
    assert iniciados == [[{}]]


def test_robo_completo(tela, qtbot, monkeypatch):
    ctrl = ControladorFalso()
    _backend(monkeypatch, ctrl)
    tela.caminho_status = "/d/s.xlsx"
    tela._start_web_process([{"x": 1}])
    assert not tela.btn_web_mem.isEnabled() and tela.btn_parar_web.isEnabled()
    qtbot.waitUntil(lambda: tela.btn_web_mem.isEnabled() and not tela.btn_parar_web.isEnabled(), timeout=3000)
    qtbot.wait(100)
    assert ctrl.chamadas == [("rpa", [{"x": 1}], "/d/s.xlsx")]
    assert tela.pausas == [(False, MSG_LOGIN_SOLTAR_ROBO), (False, msg_ficha_preenchida("4500063671.0001"))]
    assert _texto(tela).splitlines() == ["> Iniciando fila de 1 fichas no navegador...",
                                         "> Fim do processo de RPA.",
                                         "> Fila de processamento concluída (ou interrompida)."]
    assert tela.avisos == [("info", "Aviso", "A fila de automação foi finalizada!")]


def test_robo_sem_status_avisa_no_log_e_erro_critico(tela, qtbot, monkeypatch):
    _backend(monkeypatch, ControladorFalso(falha_rpa=RuntimeError("sem navegador")))
    tela._start_web_process([{"x": 1}])
    qtbot.waitUntil(lambda: tela.btn_web_file.isEnabled() and not tela.btn_parar_web.isEnabled(), timeout=3000)
    qtbot.wait(100)
    assert _texto(tela).splitlines() == [
        "> Iniciando fila de 1 fichas no navegador...",
        "> Aviso: Arquivo _STATUS_PMIB não selecionado. As fichas NÃO serão marcadas como concluídas.",
        "> Erro Crítico Web: sem navegador",
    ]
    assert tela.avisos == []


def test_parar_robo(tela, caixas):
    ctrl = ControladorFalso()
    tela.tech_controller = ctrl
    tela.btn_parar_web.setEnabled(True)
    caixas.respostas[:] = [NAO, SIM]
    tela.btn_parar_web.click()
    assert ctrl.chamadas == []
    tela.btn_parar_web.click()
    assert ctrl.chamadas == ["cancelar_web"] and not tela.btn_parar_web.isEnabled()
    assert caixas.chamadas[0] == ("pergunta", "Confirmar", "Deseja interromper o robô?\n"
                                  "Ele vai parar de forma segura antes da próxima ficha/ação.")


def test_mensagem_da_pausa():
    assert tela_mod.ModuloUploadTechSpecs._mensagem_da_pausa(LOGIN_NECESSARIO) == MSG_LOGIN_SOLTAR_ROBO
    assert tela_mod.ModuloUploadTechSpecs._mensagem_da_pausa("P1") == msg_ficha_preenchida("P1")


def test_carregar_json(tela, monkeypatch, selecao, tmp_path):
    arquivo = tmp_path / "r.json"
    arquivo.write_text(json.dumps([{"METADATA": {"PMIB": "Z", "ARQUIVO_ORIGEM": "z.xlsx"}}]), encoding="utf-8")
    pedidos = []
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file",
                        lambda chave, cat, **k: pedidos.append((chave, cat, k)) or str(arquivo))
    tela.btn_web_file.click()
    assert pedidos == [("upload_tech_specs.json_resultados", "json",
                        {"titulo": "Selecione JSON de Resultados", "filetypes": [("JSON", "*.json")]})]
    assert selecao[0].kw["itens"] == ["PMIB: Z | z.xlsx"]


def test_carregar_json_quebrado_so_loga(tela, caixas, monkeypatch, selecao, tmp_path, qtbot):
    arquivo = tmp_path / "r.json"
    arquivo.write_text("{quebrado", encoding="utf-8")
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: str(arquivo))
    tela.btn_web_file.click()
    qtbot.waitUntil(lambda: "Erro ao ler JSON" in _texto(tela), timeout=2000)
    assert caixas.chamadas == [] and selecao == []


def test_carregar_json_em_forma_de_dicionario_vai_para_o_console(tela, caixas, monkeypatch, selecao,
                                                                 tmp_path, qtbot):
    # Lá o `_pre_start_web` ficava DENTRO do try: um JSON que não é uma lista
    # de fichas logava "Erro ao ler JSON"; fora dele, a exceção sumia no
    # excepthook e a pessoa não via nada.
    arquivo = tmp_path / "r.json"
    arquivo.write_text(json.dumps({"METADATA": {"PMIB": "Z"}}), encoding="utf-8")
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: str(arquivo))
    tela.btn_web_file.click()
    qtbot.waitUntil(lambda: "Erro ao ler JSON" in _texto(tela), timeout=2000)
    assert _texto(tela).splitlines() == ["> Erro ao ler JSON: 'str' object has no attribute 'get'"]
    assert caixas.chamadas == [] and selecao == []


class ControladorQueEspera(ControladorFalso):
    """O robô fica "preenchendo" até o teste soltar."""

    def __init__(self):
        super().__init__()
        self.liberar = threading.Event()

    def executar_pipeline_rpa(self, dados, caminho_status, callback_log=None, callback_pause=None):
        self.chamadas.append(("rpa", dados, caminho_status))
        self.liberar.wait(5)


def test_um_robo_por_vez(tela, caixas, qtbot, monkeypatch):
    ctrl = ControladorQueEspera()
    _backend(monkeypatch, ctrl)
    tela.caminho_status = "/d/s.xlsx"
    tela._start_web_process([{"x": 1}])
    qtbot.waitUntil(lambda: ("rpa", [{"x": 1}], "/d/s.xlsx") in ctrl.chamadas, timeout=2000)
    # A IA termina enquanto o robô roda: salva, mas nem pergunta o "Continuar"
    # (não haveria como atender o Sim) e não sobe um segundo robô.
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_save_file", lambda *a, **k: "/d/r.json")
    tela._on_ia_finished([{"METADATA": {"PMIB": "B"}}])
    assert caixas.chamadas == []
    assert ("salvar", "/d/r.json") in ctrl.chamadas
    ctrl.liberar.set()
    qtbot.waitUntil(tela.btn_web_mem.isEnabled, timeout=3000)
    qtbot.wait(100)
    assert [c for c in ctrl.chamadas if c[0] == "rpa"] == [("rpa", [{"x": 1}], "/d/s.xlsx")]
    assert _texto(tela).count(MSG_ROBO_OCUPADO) == 1
    # Terminado o primeiro, um novo pode começar.
    tela._start_web_process([{"x": 2}])
    qtbot.waitUntil(lambda: ("rpa", [{"x": 2}], "/d/s.xlsx") in ctrl.chamadas and tela.btn_web_mem.isEnabled(),
                    timeout=3000)


# ---------------------------------------------------------------------------
# Medidas
# ---------------------------------------------------------------------------
def test_medidas_iguais_as_do_customtkinter(qt_interface, qtbot):
    # Medidas da tela CTk (janela 1280x850), relativas à área da tela (277 px
    # à direita, a barra lateral). Ver capturas/e4.45.
    from sigft.app_qt import estilo

    anterior = qt_interface.styleSheet()
    # O Roboto do app (o mesmo da captura): sem ele, a largura do texto
    # dependeria de algum teste anterior ter carregado a fonte.
    estilo.carregar_fontes()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    try:
        t = tela_mod.ModuloUploadTechSpecs()
        qtbot.addWidget(t)
        t.resize(1003, 850)
        t.show()
        qtbot.waitExposed(t)

        def geo(w):
            p = w.mapTo(t, w.rect().topLeft())
            return p.x(), p.y(), w.width(), w.height()

        assert geo(t.rotulo_config.parentWidget()) == (40, 89, 923, 91)
        assert geo(t.rotulo_config)[:2] == (55, 99)
        assert geo(t.btn_status) == (55, 137, 200, 28)
        assert geo(t.lbl_status_status) == (265, 137, 95, 28)
        # 303 lá: o texto do Roboto no Qt sai 4 px mais estreito.
        assert geo(t.switch_completos) == (639, 139, 299, 24)
        assert geo(t.tabview) == (40, 200, 923, 440)
        assert geo(t.rotulo_referencia.parentWidget())[:2] == (62, 259)
        assert geo(t.rotulo_referencia.parentWidget())[3] == 91
        assert geo(t.rotulo_referencia)[:2] == (77, 269)
        assert geo(t.btn_master) == (77, 307, 200, 28)
        assert geo(t.lbl_master_status) == (287, 307, 95, 28)
        cartao = t.fila_fichas.parentWidget()
        assert geo(cartao)[:2] == (62, 365) and geo(cartao)[3] == 253
        assert geo(t.fila_fichas.label_contador)[:2] == (72, 370)
        assert geo(t.fila_fichas)[:2] == (72, 403) and geo(t.fila_fichas)[3] == 210
        # A aba rola (lá também): os botões ficam abaixo da parte visível.
        assert geo(t.btn_ia)[1] - geo(cartao)[1] == 268
        # 202 lá: o negrito do Roboto no Qt sai ~9 px mais largo que o do Tk.
        assert geo(t.btn_ia)[2:] == (212, 40)
        assert geo(t.console) == (40, 670, 923, 150)

        t.tabview.set(ABA_WEB)
        qtbot.wait(20)
        assert geo(t.rotulo_web)[1] == 263
        assert geo(t.btn_web_mem) == (326, 321, 350, 40)
        assert geo(t.btn_web_file) == (326, 381, 350, 40)
        assert geo(t.btn_parar_web) == (326, 451, 350, 40)
    finally:
        qt_interface.setStyleSheet(anterior)
