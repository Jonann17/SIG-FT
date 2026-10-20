"""Tela "Upload de Condições no PMIB" na interface Qt.

Os backends são dublês (o portal não se testa daqui): o que se prova é a TELA
-- textos, validações, a ordem das mensagens, quem habilita o quê, e que o
worker só fala com a pessoa pela thread da interface (pausa de login, Excel
travado, aviso do fim).
"""
import threading
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QMessageBox

from sigft.app import backends, theme
from sigft.app.textos_dialogos import LOGIN_NECESSARIO, MSG_LOGIN_SOLTAR_ROBO, msg_falha_ao_salvar
from sigft.app_qt.views import upload_conditions as tela_mod
from sigft.app_qt.views._upload_comum import MSG_ROBO_OCUPADO
from sigft.app_qt.widgets import revisao_portal

ABA_IA = "Processamento IA (Gerar Excel)"
ABA_WEB = "Robô Web (Preencher Portal)"
SIM, NAO, CANCELAR = (QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No,
                      QMessageBox.StandardButton.Cancel)


# ---------------------------------------------------------------------------
# Dublês
# ---------------------------------------------------------------------------
class ProcessadorFalso:
    """`ConditionsProcessor` de mentira."""

    def __init__(self, api_key, *, status=("DF", "Status carregado: 3 linhas."), resultados=None,
                 salvar=(True, "Salvo em /d/novo.xlsx"), anexar=(True, "Anexado.")):
        self.api_key, self.status, self.resultados = api_key, status, resultados
        self.salvar, self.anexar = salvar, anexar
        self.chamadas, self.parou = [], False

    def carregar_lookup_status(self, caminho):
        self.chamadas.append(("status", caminho))
        return self.status

    def processar_ia_lote(self, files, df_status, callback_log=None, processar_completos=False):
        self.chamadas.append(("lote", list(files), df_status, processar_completos))
        callback_log("processando...")
        return self.resultados

    def solicitar_parada(self):
        self.parou = True

    def salvar_novo_arquivo(self, resultados, caminho):
        self.chamadas.append(("novo", caminho))
        return self.salvar

    def anexar_a_arquivo_existente(self, resultados, caminho):
        self.chamadas.append(("anexar", caminho))
        return self.anexar


class AutomacaoFalsa:
    """`UploadAutomation` de mentira: chama a pausa e a pergunta no meio da lista."""

    def __init__(self, *, falha=None):
        self.falha, self.chamadas, self.parou = falha, [], False

    def iniciar(self):
        self.chamadas.append("iniciar")

    def abrir_portal(self, url):
        self.chamadas.append(("portal", url))

    def processar_lista(self, dados, status, callback_ask=None, callback_log=None, callback_pause=None):
        self.chamadas.append(("lista", dados, status))
        if self.falha:
            raise self.falha
        callback_pause("Dimensões")
        self.repetir = callback_ask("travado")
        callback_log("ficha ok")

    def solicitar_parada(self):
        self.parou = True

    def fechar(self):
        self.chamadas.append("fechar")


def _ficha(pmib):
    """Uma ficha que passa na revisão antes do portal (R2): o robô sempre recebe
    as chaves do JSON da IA, e a Descarte é obrigatória no portal. Os testes do
    robô usavam `{"pmib_codigo": "A"}`, que hoje a revisão barra (o robô
    digitaria a Legislação e o Descarte vazios): o dado mudou, não a regra."""
    return {"pmib_codigo": pmib, "legislacao_es": "ley", "legislacao_pt": "lei",
            "descarte_es": "reciclaje", "descarte_pt": "reciclagem"}


def _backend(monkeypatch, processador=None, automacao=None):
    criados = SimpleNamespace(processador=None)

    def novo_processador(api_key):
        processador.api_key = api_key
        criados.processador = processador
        return processador

    monkeypatch.setattr(backends, "upload_conditions_backend", SimpleNamespace(
        ConditionsProcessor=novo_processador, UploadAutomation=lambda: automacao))
    return criados


@pytest.fixture
def tela(qt_interface, qtbot, monkeypatch):
    controller = SimpleNamespace(get_key=lambda k: {"GEMINI": "chave-123"}.get(k, ""))
    t = tela_mod.ModuloUploadConditions(None, controller)
    qtbot.addWidget(t)
    t.avisos, t.pausas, t.retries = [], [], []
    monkeypatch.setattr(t, "avisar", lambda ti, m, tipo="info": t.avisos.append((tipo, ti, m)))

    def pausar(msg, texto_botao=None):
        t.pausas.append((threading.current_thread() is threading.main_thread(), msg))

    def retry(caminho=None):
        t.retries.append(threading.current_thread() is threading.main_thread())
        return True

    monkeypatch.setattr(t, "pausar_e_esperar", pausar)
    monkeypatch.setattr(t, "perguntar_retry_excel", retry)
    return t


@pytest.fixture
def caixas(monkeypatch):
    """Os QMessageBox da thread da interface: registra e responde da fila `respostas`."""
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
    """O SelecaoMultiplaDialog: registra os argumentos sem abrir janela."""
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
# Montagem
# ---------------------------------------------------------------------------
def test_monta_com_os_textos(tela):
    assert tela.label_titulo.text() == "Upload de Condições no PMIB"
    assert tela.rotulo_config.text() == "Configuração Global (Requerido para IA e Web)"
    assert tela.btn_status.text() == "Selecionar _STATUS_PMIB"
    assert tela.lbl_status_status.text() == "Não selecionado"
    assert tela.switch_completos.text() == "Forçar processamento de fichas com status 'COMPLETO'"
    assert not tela.switch_completos.isChecked()
    assert list(tela.tabview.abas) == [ABA_IA, ABA_WEB]
    assert tela.tabview.get() == ABA_IA
    assert tela.fila_fichas.label_contador.text() == "Planilhas PMIB Selecionadas (0)"
    assert tela.fila_fichas.botao_adicionar.text() == "Adicionar Fichas"
    assert tela.btn_ia.text() == "INICIAR PROCESSAMENTO IA" and tela.btn_ia.isEnabled()
    assert tela.btn_parar_ia.text() == "PARAR" and not tela.btn_parar_ia.isEnabled()
    assert tela.rotulo_web.text() == (
        "Lê um arquivo Excel com os resultados e inicia o Selenium para preencher o Portal.")
    assert tela.btn_web_mem.text() == "Usar Dados Recém Processados (Memória)"
    assert tela.btn_web_file.text() == "Carregar 'resultados_api_pmib.xlsx'"
    assert tela.btn_parar_web.text() == "PARAR ROBÔ WEB" and not tela.btn_parar_web.isEnabled()
    assert tela.caminho_status == "" and tela.dados_em_memoria == []
    assert tela.api_key == "chave-123"


def test_abre_sem_controller_e_sem_backend(qt_interface, qtbot, monkeypatch):
    # O backend só é pedido no clique: a tela abre mesmo se ele não carregou.
    monkeypatch.setattr(backends, "upload_conditions_backend", None)
    t = tela_mod.ModuloUploadConditions()
    qtbot.addWidget(t)
    assert t.api_key == ""


def test_selecionar_status(tela, monkeypatch):
    chamadas = []

    def falso(chave, categoria, **k):
        chamadas.append((chave, categoria, k))
        return "/d/pasta/_STATUS_PMIB.xlsx"

    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", falso)
    tela.btn_status.click()
    assert chamadas == [("upload_conditions.status_pmib", "excel",
                         {"titulo": "Selecione _STATUS_PMIB", "filetypes": [("Excel", "*.xlsx;*.xlsm")]})]
    assert tela.caminho_status == "/d/pasta/_STATUS_PMIB.xlsx"
    assert tela.lbl_status_status.text() == "_STATUS_PMIB.xlsx"
    assert theme.COLORS["accent"] in tela.lbl_status_status.styleSheet()
    assert theme.COLORS["primary"] in tela.btn_status.styleSheet()


def test_cancelar_o_seletor_de_status_nao_mexe(tela, monkeypatch):
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "")
    tela.btn_status.click()
    assert tela.caminho_status == "" and tela.lbl_status_status.text() == "Não selecionado"


def test_fila_usa_a_chave_da_tela_e_loga_so_a_adicao(tela, monkeypatch, qtbot):
    pedidos = []

    def falso(chave, categoria, **k):
        pedidos.append((chave, categoria, k["titulo"], k["filetypes"]))
        return ["/d/a.xlsx", "/d/b.xlsx"]

    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_files", falso)
    tela.fila_fichas.botao_adicionar.click()
    assert pedidos == [("upload_conditions.fichas", "excel", "Selecione as Fichas PMIB",
                        [("Excel", "*.xlsx;*.xls")])]
    assert tela.lista_fichas_paths == ["/d/a.xlsx", "/d/b.xlsx"]
    tela.fila_fichas.limpar()
    qtbot.waitUntil(lambda: "Total na fila" in _texto(tela), timeout=2000)
    qtbot.wait(100)
    assert _texto(tela) == "> 2 arquivos selecionados. Total na fila: 2"


# ---------------------------------------------------------------------------
# IA (aba 1)
# ---------------------------------------------------------------------------
def test_iniciar_ia_exige_status_e_fichas(tela, caixas, monkeypatch):
    tela.btn_ia.click()
    tela.caminho_status = "/d/_STATUS_PMIB.xlsx"
    tela.btn_ia.click()
    assert caixas.chamadas == [
        ("aviso", "Aviso", "Por favor, selecione a planilha de _STATUS_PMIB na Configuração Global."),
        ("aviso", "Aviso", "Por favor, adicione pelo menos uma ficha à lista."),
    ]
    assert tela.btn_ia.isEnabled() and not tela.btn_parar_ia.isEnabled()


def test_backend_indisponivel_avisa_e_nao_comeca(tela, caixas, monkeypatch):
    monkeypatch.setattr(backends, "upload_conditions_backend", None)
    tela.caminho_status = "/d/s.xlsx"
    _com_fila(tela, monkeypatch)
    tela.btn_ia.click()
    assert caixas.chamadas and caixas.chamadas[-1][:2] == ("aviso", "Módulo indisponível")
    assert tela.btn_ia.isEnabled() and not tela.btn_parar_ia.isEnabled()


def _rodar_ia(tela, qtbot, monkeypatch, processador, *, completos=False):
    _backend(monkeypatch, processador=processador)
    tela.caminho_status = "/d/_STATUS_PMIB.xlsx"
    _com_fila(tela, monkeypatch)
    tela.switch_completos.setChecked(completos)
    tela.btn_ia.click()
    assert not tela.btn_ia.isEnabled() and tela.btn_parar_ia.isEnabled()
    qtbot.waitUntil(lambda: tela.btn_ia.isEnabled() and not tela.btn_parar_ia.isEnabled(), timeout=3000)
    qtbot.wait(100)


def test_ia_sem_resultados_avisa(tela, caixas, qtbot, monkeypatch):
    proc = ProcessadorFalso(None, resultados=[])
    _rodar_ia(tela, qtbot, monkeypatch, proc, completos=True)
    assert proc.api_key == "chave-123"
    assert proc.chamadas == [("status", "/d/_STATUS_PMIB.xlsx"),
                             ("lote", ["/d/a.xlsx", "/d/b.xlsx"], "DF", True)]
    assert _texto(tela).splitlines()[1:] == [
        "> Iniciando processamento de 2 arquivos...",
        "> Status carregado: 3 linhas.",
        "> Forçar processamento LIGADO: fichas já COMPLETO também serão reprocessadas.",
        "> processando...",
    ]
    assert caixas.chamadas == [("info", "Aviso", "Nenhum dado gerado. Verifique o console.")]
    assert tela.processor_ativo is None


def test_ia_status_que_nao_carrega(tela, caixas, qtbot, monkeypatch):
    proc = ProcessadorFalso(None, status=(None, "aba não encontrada"))
    _rodar_ia(tela, qtbot, monkeypatch, proc)
    assert "> Erro no Status: aba não encontrada" in _texto(tela)
    assert [c[0] for c in proc.chamadas] == ["status"]
    assert caixas.chamadas == []


def test_ia_erro_fatal(tela, caixas, qtbot, monkeypatch):
    class Quebra(ProcessadorFalso):
        def processar_ia_lote(self, *a, **k):
            raise RuntimeError("cota esgotada")

    _rodar_ia(tela, qtbot, monkeypatch, Quebra(None))
    assert "> Erro Fatal IA: cota esgotada" in _texto(tela)
    assert "Forçar" not in _texto(tela)


def test_ia_salva_em_arquivo_novo_e_pula_para_o_robo(tela, caixas, qtbot, monkeypatch, selecao):
    dados = [{"pmib_codigo": "4500063671.0001"}, {"pmib_codigo": "4500063671.0002"}]
    proc = ProcessadorFalso(None, resultados=dados)
    pedidos = []
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_save_file",
                        lambda chave, cat, **k: pedidos.append((chave, cat, k)) or "/d/novo.xlsx")
    caixas.respostas[:] = [SIM, SIM]
    _rodar_ia(tela, qtbot, monkeypatch, proc)
    assert pedidos == [("upload_conditions.salvar_novo", "excel",
                        {"titulo": "Salvar Novo Arquivo", "defaultextension": ".xlsx",
                         "filetypes": [("Excel", "*.xlsx")]})]
    assert proc.chamadas[-1] == ("novo", "/d/novo.xlsx")
    assert caixas.chamadas == [
        ("pergunta", "Salvar Resultados", "Como deseja salvar as fichas processadas?\n\n"
                                          "SIM = Novo Arquivo Excel\nNÃO = Anexar a um Excel Existente"),
        ("pergunta", "Continuar", "Dados salvos! Deseja pular para a Aba 2 e iniciar o Robô Web agora?"),
    ]
    assert "> Sucesso! 2 fichas processadas." in _texto(tela)
    assert "> Salvo em /d/novo.xlsx" in _texto(tela)
    assert tela.dados_em_memoria == dados
    assert tela.tabview.get() == ABA_WEB
    assert len(selecao) == 1 and selecao[0].kw["itens"] == [" Ficha PMIB: 4500063671.0001",
                                                            " Ficha PMIB: 4500063671.0002"]


def test_ia_anexa_e_falha_ao_salvar(tela, caixas, qtbot, monkeypatch):
    proc = ProcessadorFalso(None, resultados=[{"pmib_codigo": "1"}], anexar=(False, "Arquivo aberto"))
    pedidos = []
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file",
                        lambda chave, cat, **k: pedidos.append((chave, cat, k)) or "/d/velho.xlsx")
    caixas.respostas[:] = [NAO]
    _rodar_ia(tela, qtbot, monkeypatch, proc)
    assert pedidos == [("upload_conditions.anexar", "excel",
                        {"titulo": "Selecionar arquivo para ANEXAR", "filetypes": [("Excel", "*.xlsx")]})]
    assert proc.chamadas[-1] == ("anexar", "/d/velho.xlsx")
    assert caixas.chamadas[-1] == ("erro", "Erro ao Salvar", "Arquivo aberto")
    assert tela.tabview.get() == ABA_IA


def test_ia_cancelar_o_salvamento(tela, caixas, qtbot, monkeypatch):
    proc = ProcessadorFalso(None, resultados=[{"pmib_codigo": "1"}])
    caixas.respostas[:] = [CANCELAR]
    _rodar_ia(tela, qtbot, monkeypatch, proc)
    assert [c[0] for c in proc.chamadas] == ["status", "lote"]
    assert len(caixas.chamadas) == 1
    assert tela.dados_em_memoria == [{"pmib_codigo": "1"}]


def test_parar_ia(tela, caixas):
    proc = ProcessadorFalso(None)
    tela.processor_ativo = proc
    tela.btn_parar_ia.setEnabled(True)
    caixas.respostas[:] = [NAO, SIM]
    tela.btn_parar_ia.click()
    assert not proc.parou and tela.btn_parar_ia.isEnabled()
    tela.btn_parar_ia.click()
    assert proc.parou and not tela.btn_parar_ia.isEnabled()
    assert caixas.chamadas[0] == ("pergunta", "Confirmar",
                                  "Deseja interromper a IA?\nO que já foi processado será mantido.")


# ---------------------------------------------------------------------------
# Robô Web (aba 2)
# ---------------------------------------------------------------------------
def test_robo_exige_status_e_dados(tela, caixas, selecao):
    tela.btn_web_mem.click()
    tela.caminho_status = "/d/s.xlsx"
    tela.btn_web_mem.click()
    assert caixas.chamadas == [
        ("aviso", "Aviso", "Selecione o _STATUS_PMIB na Configuração Global antes de iniciar o Robô."),
        ("aviso", "Aviso", "Não há dados para iniciar a automação."),
    ]
    assert selecao == []


def test_selecao_de_fichas(tela, selecao, monkeypatch):
    iniciados = []
    monkeypatch.setattr(tela, "_start_web_process", iniciados.append)
    dados = [{"pmib_codigo": "A"}, {}, {"pmib_codigo": "C"}]
    tela.caminho_status = "/d/s.xlsx"
    tela.dados_em_memoria = dados
    tela.btn_web_mem.click()
    kw = selecao[0].kw
    assert kw["itens"] == [" Ficha PMIB: A", " Ficha PMIB: N/A", " Ficha PMIB: C"]
    assert kw["titulo"] == "Selecione as Fichas para Processar"
    assert kw["instrucao"] == "Selecione quais PMIBs deseja preencher no portal:"
    assert kw["geometria"] == "500x400" and kw["modal"] and kw["com_selecionar_todos"]
    assert kw["devolver_indices"] and kw["fonte_lista"] == ("Consolas", 12)
    assert kw["fonte_instrucao"] == ("Roboto", 14, "bold")
    assert kw["estilo_lista"]["bg"] == "#1E1E1E"
    assert kw["estilo_lista"]["selectbackground"] == theme.COLORS["primary"]
    kw["ao_confirmar"]([2, 0])
    assert iniciados == [[{"pmib_codigo": "C"}, {"pmib_codigo": "A"}]]
    kw["ao_confirmar"]([])
    assert iniciados == [[{"pmib_codigo": "C"}, {"pmib_codigo": "A"}]]


def test_selecao_vazia_loga(tela, selecao, qtbot):
    tela.caminho_status = "/d/s.xlsx"
    tela._pre_start_web([{"pmib_codigo": "A"}])
    selecao[0].kw["ao_confirmar"]([])
    qtbot.waitUntil(lambda: "cancelada" in _texto(tela), timeout=2000)
    assert _texto(tela) == "> Nenhuma ficha selecionada. Operação cancelada."


def _rodar_robo(tela, qtbot, monkeypatch, auto, dados):
    _backend(monkeypatch, automacao=auto)
    tela.caminho_status = "/d/_STATUS_PMIB.xlsx"
    tela._start_web_process(dados)
    assert not tela.btn_web_mem.isEnabled() and not tela.btn_web_file.isEnabled()
    assert tela.btn_parar_web.isEnabled()
    qtbot.waitUntil(lambda: tela.btn_web_mem.isEnabled() and tela.btn_web_file.isEnabled()
                    and not tela.btn_parar_web.isEnabled(), timeout=3000)
    qtbot.wait(100)


def test_robo_completo(tela, qtbot, monkeypatch):
    auto = AutomacaoFalsa()
    dados = [_ficha("A")]
    _rodar_robo(tela, qtbot, monkeypatch, auto, dados)
    assert auto.chamadas == ["iniciar", ("portal", "https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList"),
                             ("lista", dados, "/d/_STATUS_PMIB.xlsx"), "fechar"]
    # A pausa e o Excel travado: do worker (fora da thread da interface).
    assert tela.pausas == [(False, MSG_LOGIN_SOLTAR_ROBO), (False, msg_falha_ao_salvar("Dimensões"))]
    assert tela.retries == [False] and auto.repetir is True
    assert _texto(tela).splitlines() == [
        "> Iniciando fila de 1 fichas no navegador...",
        "> Iniciando navegador...",
        "> Carregando portal PMIB...",
        "> Login confirmado. Iniciando preenchimento...",
        "> ficha ok",
        "> Fila de processamento web concluída.",
    ]
    assert tela.avisos == [("info", "Aviso", "A fila de automação foi finalizada!")]
    assert tela.automacao_ativa is None


def test_robo_erro_critico_fecha_o_navegador(tela, qtbot, monkeypatch):
    auto = AutomacaoFalsa(falha=RuntimeError("portal fora do ar"))
    _rodar_robo(tela, qtbot, monkeypatch, auto, [_ficha("A")])
    assert "> Erro Crítico Web: portal fora do ar" in _texto(tela)
    assert auto.chamadas[-1] == "fechar"
    assert tela.avisos == []


def test_parar_robo(tela, caixas):
    auto = AutomacaoFalsa()
    tela.automacao_ativa = auto
    tela.btn_parar_web.setEnabled(True)
    caixas.respostas[:] = [SIM]
    tela.btn_parar_web.click()
    assert auto.parou and not tela.btn_parar_web.isEnabled()
    assert caixas.chamadas == [("pergunta", "Confirmar",
                                "Deseja interromper o robô?\nEle vai parar antes da próxima ficha.")]


def test_mensagem_da_pausa():
    assert tela_mod.ModuloUploadConditions._mensagem_da_pausa(LOGIN_NECESSARIO) == MSG_LOGIN_SOLTAR_ROBO
    assert tela_mod.ModuloUploadConditions._mensagem_da_pausa("Peso") == msg_falha_ao_salvar("Peso")


def test_carregar_excel_de_resultados(tela, caixas, monkeypatch, selecao):
    pedidos = []
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file",
                        lambda chave, cat, **k: pedidos.append((chave, cat, k)) or "/d/resultados.xlsx")
    lidos = []
    monkeypatch.setattr(tela_mod, "ler_resultados_excel",
                        lambda c: lidos.append(c) or [{"pmib_codigo": "X"}])
    tela.caminho_status = "/d/s.xlsx"
    tela.btn_web_file.click()
    assert pedidos == [("upload_conditions.excel_resultados", "excel",
                        {"titulo": "Selecione Excel de Resultados", "filetypes": [("Excel", "*.xlsx;*.xls")]})]
    assert lidos == ["/d/resultados.xlsx"]
    assert selecao[0].kw["itens"] == [" Ficha PMIB: X"]


def test_carregar_excel_que_falha(tela, caixas, monkeypatch, qtbot):
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "/d/r.xlsx")

    def quebra(c):
        raise ValueError("planilha corrompida")

    monkeypatch.setattr(tela_mod, "ler_resultados_excel", quebra)
    tela.btn_web_file.click()
    assert caixas.chamadas == [("erro", "Erro de Leitura", "Falha ao ler Excel: planilha corrompida")]
    qtbot.waitUntil(lambda: "corrompida" in _texto(tela), timeout=2000)
    assert _texto(tela).splitlines() == ["> Lendo arquivo Excel, convertendo strings em dicionários...",
                                         "> Erro ao ler Excel: planilha corrompida"]


def test_cancelar_o_excel_de_resultados(tela, caixas, monkeypatch, selecao):
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "")
    tela.btn_web_file.click()
    assert caixas.chamadas == [] and selecao == []


def test_excel_com_linhas_estranhas_vai_para_o_console(tela, caixas, monkeypatch, selecao, qtbot):
    # Lá o `_pre_start_web` ficava DENTRO do try: dados num formato inesperado
    # viram "Erro ao ler Excel" no console e o aviso, não uma exceção solta.
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "/d/r.xlsx")
    monkeypatch.setattr(tela_mod, "ler_resultados_excel", lambda c: ["linha solta"])
    tela.caminho_status = "/d/s.xlsx"
    tela.btn_web_file.click()
    erro = "'str' object has no attribute 'get'"
    assert caixas.chamadas == [("erro", "Erro de Leitura", f"Falha ao ler Excel: {erro}")]
    qtbot.waitUntil(lambda: "Erro ao ler Excel" in _texto(tela), timeout=2000)
    assert _texto(tela).splitlines() == ["> Lendo arquivo Excel, convertendo strings em dicionários...",
                                         f"> Erro ao ler Excel: {erro}"]
    assert selecao == []


def test_robo_que_nao_nasce_devolve_os_botoes(tela, qtbot, monkeypatch):
    # Lá `UploadAutomation()` ficava fora do try: a exceção derrubava a thread
    # e os botões do robô nunca mais voltavam.
    def quebra():
        raise RuntimeError("chromedriver ausente")

    monkeypatch.setattr(backends, "upload_conditions_backend", SimpleNamespace(UploadAutomation=quebra))
    tela.caminho_status = "/d/s.xlsx"
    tela._start_web_process([_ficha("A")])
    qtbot.waitUntil(lambda: tela.btn_web_mem.isEnabled() and tela.btn_web_file.isEnabled()
                    and not tela.btn_parar_web.isEnabled(), timeout=3000)
    qtbot.waitUntil(lambda: "Erro Crítico Web" in _texto(tela), timeout=2000)
    assert _texto(tela).splitlines() == ["> Iniciando fila de 1 fichas no navegador...",
                                         "> Erro Crítico Web: chromedriver ausente"]
    assert tela.automacao_ativa is None and tela.avisos == []


def test_fechar_que_falha_loga_e_devolve_os_botoes(tela, qtbot, monkeypatch):
    class FechaQuebrando(AutomacaoFalsa):
        def fechar(self):
            super().fechar()
            raise OSError("navegador já fechado")

    auto = FechaQuebrando()
    _rodar_robo(tela, qtbot, monkeypatch, auto, [_ficha("A")])
    assert auto.chamadas[-1] == "fechar"
    assert _texto(tela).splitlines()[-2:] == ["> Fila de processamento web concluída.",
                                              "> Erro Crítico Web: navegador já fechado"]
    assert tela.avisos == [("info", "Aviso", "A fila de automação foi finalizada!")]
    assert tela.automacao_ativa is None


class AutomacaoQueEspera(AutomacaoFalsa):
    """Fica "preenchendo" até o teste soltar."""

    def __init__(self):
        super().__init__()
        self.liberar = threading.Event()

    def processar_lista(self, dados, status, **k):
        self.chamadas.append(("lista", dados, status))
        self.liberar.wait(5)


def test_um_robo_por_vez(tela, caixas, qtbot, monkeypatch, selecao):
    auto = AutomacaoQueEspera()
    criados = []
    monkeypatch.setattr(backends, "upload_conditions_backend",
                        SimpleNamespace(UploadAutomation=lambda: criados.append(1) or auto))
    tela.caminho_status = "/d/s.xlsx"
    tela._start_web_process([_ficha("A")])
    qtbot.waitUntil(lambda: any(c[0] == "lista" for c in auto.chamadas if isinstance(c, tuple)),
                    timeout=2000)
    # A IA termina enquanto o robô roda: salva, mas nem pergunta o "Continuar"
    # (não haveria como atender o Sim) e não abre a seleção.
    proc = ProcessadorFalso(None, resultados=[{"pmib_codigo": "B"}])
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_save_file", lambda *a, **k: "/d/novo.xlsx")
    caixas.respostas[:] = [SIM]
    tela._on_ia_finished([{"pmib_codigo": "B"}], proc)
    assert [c[1] for c in caixas.chamadas] == ["Salvar Resultados"]
    assert proc.chamadas[-1] == ("novo", "/d/novo.xlsx")
    assert selecao == []
    # Nem uma seleção antiga confirmada agora.
    tela._start_web_process([_ficha("C")])
    auto.liberar.set()
    qtbot.waitUntil(tela.btn_web_mem.isEnabled, timeout=3000)
    qtbot.wait(100)
    assert criados == [1]
    assert _texto(tela).count(MSG_ROBO_OCUPADO) == 2
    # Terminado o primeiro, um novo pode começar.
    auto.liberar = threading.Event()
    auto.liberar.set()
    tela._start_web_process([_ficha("D")])
    qtbot.waitUntil(lambda: criados == [1, 1] and tela.btn_web_mem.isEnabled(), timeout=3000)


def test_ler_resultados_excel_normaliza_o_pmib_e_os_dicionarios(monkeypatch):
    from tests._pandas_de_verdade import pandas_de_verdade

    with pandas_de_verdade() as pd:
        lidos = []

        def ler(caminho, dtype=None):
            lidos.append((caminho, dtype))
            return pd.DataFrame({"pmib_codigo": ["450006367.1", "'4500063671.0002"],
                                 "dimensoes": ["{'altura': 2}", None], "outro": [1, 2]})

        monkeypatch.setattr(pd, "read_excel", ler)
        dados = tela_mod.ler_resultados_excel("/d/r.xlsx")
    assert lidos == [("/d/r.xlsx", {"pmib_codigo": str})]
    from sigft.core.excel.pmib_codes import normalize_pmib
    assert [d["pmib_codigo"] for d in dados] == [normalize_pmib("450006367.1"),
                                                  normalize_pmib("'4500063671.0002")]
    assert [d["dimensoes"] for d in dados] == [{"altura": 2}, {}]
    assert [d["outro"] for d in dados] == [1, 2]


# ---------------------------------------------------------------------------
# Medidas
# ---------------------------------------------------------------------------
def test_medidas_iguais_as_do_interface_antiga(qt_interface, qtbot):
    # 2026-10-20: medida do sistema visual (botão/campo 32, título 22, borda 1); a CTk saiu em 2026-10-15.
    # Medidas da tela antiga (janela 1280x850, winfo_*), relativas à área da tela,
    # que começa 277 px à direita (a barra lateral). Ver capturas/e4.45.
    from sigft.app_qt import estilo

    anterior = qt_interface.styleSheet()
    # O Roboto do app (o mesmo da captura): sem ele, a largura do texto
    # dependeria de algum teste anterior ter carregado a fonte.
    estilo.carregar_fontes()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    try:
        t = tela_mod.ModuloUploadConditions()
        qtbot.addWidget(t)
        t.resize(1003, 850)
        t.show()
        qtbot.waitExposed(t)

        def geo(w):
            p = w.mapTo(t, w.rect().topLeft())
            return p.x(), p.y(), w.width(), w.height()

        assert geo(t.label_titulo)[:2] == (40, 30)
        assert geo(t.rotulo_config.parentWidget()) == (40, 87, 923, 86)
        assert geo(t.rotulo_config)[:2] == (55, 97) and geo(t.rotulo_config)[3] == 28
        assert geo(t.btn_status) == (55, 135, 200, 28)
        assert geo(t.lbl_status_status) == (265, 135, 95, 28)
        # 370 lá: o texto do Roboto no Qt sai 4 px mais estreito.
        assert geo(t.switch_completos) == (572, 137, 366, 24)
        assert geo(t.tabview) == (40, 193, 923, 447)
        assert geo(t.tabview.tab(ABA_IA))[:2] == (46, 236)
        cartao = t.fila_fichas.parentWidget()
        # A barra do CTkScrollableFrame fica sempre à vista (polimento A4): o
        # cartão tem os 868 de lá (era 884 com a barra só quando havia o que rolar).
        assert geo(cartao) == (62, 252, 868, 258)
        assert geo(t.fila_fichas.label_contador)[:2] == (72, 262)
        assert geo(t.fila_fichas)[:2] == (72, 295) and geo(t.fila_fichas)[3] == 210
        # O botão cresce até caber o texto: 202 lá; o negrito do Roboto no Qt sai
        # ~8 px mais largo que o do Tk, por isso 210 (o par fica centrado igual).
        # Sintetizado do Regular, o único registrado; era 212 medido com o
        # Roboto-Medium do ~/.fonts do contêiner, que o app não tem
        # (tests/test_qt_fontes_dos_testes.py).
        assert geo(t.btn_ia)[1:] == (525, 212, 40)
        assert geo(t.btn_parar_ia)[1:] == (525, 100, 40)
        assert geo(t.console) == (40, 670, 923, 150)

        t.tabview.set(ABA_WEB)
        qtbot.wait(20)
        assert geo(t.rotulo_web)[1] == 256 and geo(t.rotulo_web)[3] == 28
        assert geo(t.btn_web_mem) == (326, 314, 350, 40)
        assert geo(t.btn_web_file) == (326, 374, 350, 40)
        assert geo(t.btn_parar_web) == (326, 444, 350, 40)
    finally:
        qt_interface.setStyleSheet(anterior)


def test_nome_de_arquivo_longo_nao_alarga_a_tela(tela, monkeypatch):
    # Com um nome de ~120 caracteres a janela inteira passava de 1280 para
    # 1682 px. Agora o nome é elidido e o caminho completo fica no tooltip.
    nome = ("Lista de PDMs SAM-GM revisao final aprovada pelo cliente em setembro de 2026 "
            "- versao definitiva para fatiamento geral.xlsx")
    largura = tela.minimumSizeHint().width()
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "/d/" + nome)
    tela.btn_status.click()
    assert tela.minimumSizeHint().width() <= largura
    assert tela.lbl_status_status.text() == nome
    assert tela.lbl_status_status.toolTip() == "/d/" + nome


def test_escolher_de_novo_nao_acumula_folha(tela, monkeypatch):
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "/d/a.xlsx")
    tela.btn_status.click()
    folhas = (tela.btn_status.styleSheet(), tela.lbl_status_status.styleSheet())
    tela.btn_status.click()
    tela.btn_status.click()
    assert (tela.btn_status.styleSheet(), tela.lbl_status_status.styleSheet()) == folhas


# ---------------------------------------------------------------------------
# Revisão antes do portal (R2)
# ---------------------------------------------------------------------------
@pytest.fixture
def revisao(monkeypatch):
    """A janela da revisão: registra o que ela recebeu e responde `resposta`."""
    registro = SimpleNamespace(chamadas=[], resposta=revisao_portal.SEM_ERROS)

    def perguntar(parent, problemas, total):
        registro.chamadas.append((parent, [(p.ficha, p.interno) for p in problemas], total,
                                  threading.current_thread() is threading.main_thread()))
        return registro.resposta

    monkeypatch.setattr(revisao_portal, "perguntar_revisao", perguntar)
    return registro


def test_revisao_tira_as_fichas_com_erro(tela, qtbot, monkeypatch, revisao):
    auto = AutomacaoFalsa()
    boa, ruim = _ficha("A"), {**_ficha("B"), "legislacao_pt": " "}
    _rodar_robo(tela, qtbot, monkeypatch, auto, [ruim, boa])
    assert revisao.chamadas == [(tela, [("B", "TextArea_TypeLegislationPT")], 2, True)]
    assert auto.chamadas[2] == ("lista", [boa], "/d/_STATUS_PMIB.xlsx")
    linhas = _texto(tela).splitlines()
    assert linhas[:4] == [
        "> Revisão antes do portal: 1 problema(s) em 1 ficha(s) de 2.",
        "> [!] B · Legislação (PT) (TextArea_TypeLegislationPT) · '' · "
        "está vazio; o portal não aceita este campo vazio",
        "> Seguindo sem as 1 ficha(s) com erro: 1 vão ao portal.",
        "> Iniciando fila de 1 fichas no navegador...",
    ]


def test_revisao_seguir_com_todas(tela, qtbot, monkeypatch, revisao):
    revisao.resposta = revisao_portal.TODAS
    auto = AutomacaoFalsa()
    dados = [{**_ficha("B"), "descarte_pt": ""}, _ficha("A")]
    _rodar_robo(tela, qtbot, monkeypatch, auto, dados)
    assert auto.chamadas[2] == ("lista", dados, "/d/_STATUS_PMIB.xlsx")


def test_revisao_sem_problema_nada_aparece(tela, qtbot, monkeypatch, revisao):
    auto = AutomacaoFalsa()
    _rodar_robo(tela, qtbot, monkeypatch, auto, [_ficha("A")])
    assert revisao.chamadas == []
    assert "Revisão antes do portal" not in _texto(tela)


def test_revisao_cancelar_nao_abre_o_robo(tela, qtbot, monkeypatch, revisao):
    revisao.resposta = None
    criados = []
    monkeypatch.setattr(backends, "upload_conditions_backend",
                        SimpleNamespace(UploadAutomation=lambda: criados.append(1)))
    tela.caminho_status = "/d/s.xlsx"
    tela._start_web_process([{**_ficha("A"), "descarte_es": ""}])
    assert criados == [] and tela.btn_web_mem.isEnabled() and not tela.btn_parar_web.isEnabled()
    qtbot.waitUntil(lambda: _texto(tela).endswith("> Cancelado na revisão antes do portal."), timeout=2000)
    assert "Iniciando fila" not in _texto(tela)


def test_revisao_todas_com_erro_nao_abre_o_robo(tela, qtbot, monkeypatch, revisao, caixas):
    criados = []
    monkeypatch.setattr(backends, "upload_conditions_backend",
                        SimpleNamespace(UploadAutomation=lambda: criados.append(1)))
    tela._start_web_process([{"pmib_codigo": "A"}])
    assert criados == [] and tela.btn_web_mem.isEnabled()
    qtbot.waitUntil(lambda: _texto(tela).endswith("> " + revisao_portal.MSG_NADA_SOBROU), timeout=2000)
    assert caixas.chamadas[-1][0] == "aviso"
