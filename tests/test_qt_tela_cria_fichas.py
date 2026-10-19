"""Tela "Criação de Fichas" (Cria Fichas PMIB) na interface Qt.

Comportamento com backends, IA e robô FALSOS (nada de portal: os seletores e o
fluxo do portal são do serviço, que não muda), e medidas contra a tela antiga.

O conftest dubla o pandas; os testes que dependem de DataFrame de verdade usam
a fixture `pandas_real` (o CI instala o pandas; sem ele, são pulados).
"""
import contextlib
import importlib
import sys
import threading

import pytest
from PySide6.QtWidgets import QApplication, QDialog

from sigft.app import backends, theme
from sigft.app.textos_dialogos import MSG_LOGIN_NOVA_FICHA, MSG_LOGIN_PAGINA_PRINCIPAL
from sigft.app_qt import estilo
from sigft.app_qt.views import cria_fichas as tela_mod
from sigft.app_qt.widgets import controles, revisao_portal
from sigft.app_qt.views.janelas import DecisaoRobo

COLORS = theme.COLORS


# --- pandas de verdade --------------------------------------------------------------

@contextlib.contextmanager
def _pacote_real(nome):
    antes = {k: v for k, v in sys.modules.items() if k == nome or k.startswith(nome + ".")}
    for chave in antes:
        del sys.modules[chave]
    try:
        modulo = importlib.import_module(nome)
    except ImportError:
        sys.modules.update(antes)
        yield None
        return
    try:
        yield modulo
    finally:
        for chave in [k for k in list(sys.modules) if k == nome or k.startswith(nome + ".")]:
            del sys.modules[chave]
        sys.modules.update(antes)


@pytest.fixture
def pd(monkeypatch):
    """O pandas real, também DENTRO da tela (ela fez `import pandas as pd` com o dublê)."""
    with _pacote_real("pandas") as modulo:
        if modulo is None or not isinstance(getattr(modulo, "DataFrame", None), type):
            pytest.skip("pandas real não instalado neste ambiente")
        monkeypatch.setattr(tela_mod, "pd", modulo)
        yield modulo


# --- dublês -------------------------------------------------------------------------

class JanelaFalsa:
    """Registra quem abriu e em que thread; `isVisible`/`raise_` para o resumo."""

    def __init__(self, registro, *args, **kw):
        self.args, self.kw = args, kw
        self.na_interface = threading.current_thread() is threading.main_thread()
        self.visivel = True
        self.levantada = 0
        self.fechada = False
        registro.append(self)

    def isVisible(self):  # noqa: N802 -- API Qt
        return self.visivel

    def raise_(self):
        self.levantada += 1

    def activateWindow(self):  # noqa: N802 -- API Qt
        pass

    def setAttribute(self, atributo, ligado=True):  # noqa: N802 -- API Qt
        self.atributos = getattr(self, "atributos", {})
        self.atributos[atributo] = ligado

    def close(self):
        self.visivel = False
        self.fechada = True


class CategorizadorFalso:
    """O categorizador do serviço, só com o que a tela chama (2026-10-08): as
    duas passadas e a preparação da revisão moram em `classificar_para_revisao`.
    As respostas passam pelo `preparar_para_revisao` DE VERDADE (a guarda contra
    PDM inventado e os avisos no log são do serviço)."""

    modelo_em_uso = "openrouter/google/gemini-2.5-flash"
    modelo_da_interpretacao = "openrouter/google/gemini-2.5-flash-lite"
    respostas = []
    chamadas = []

    def __init__(self, chave):
        self.chave = chave

    def classificar_para_revisao(self, df, catalogo, codigo_projeto, callback_log=None):
        type(self).chamadas.append((self.chave, list(df["DESCRIÇÃO"]), catalogo, codigo_projeto,
                                    threading.current_thread() is threading.main_thread()))
        callback_log("lote 1/1")
        linhas = [linha for _i, linha in df.iterrows()]
        return tela_mod.cria_fichas_svc.preparar_para_revisao(
            list(self.respostas), linhas, catalogo, None, None, codigo_projeto, callback_log)


class RevisaoFalsa(JanelaFalsa):
    """JanelaRevisaoPDM: `finished` é chamado pelo teste (confirmar ou fechar no X)."""

    def __init__(self, registro, parent, df, callback, catalogo=None):
        super().__init__(registro, parent, df, callback, catalogo=catalogo)
        self.df, self.callback, self.catalogo = df, callback, catalogo
        self._ao_terminar = []
        self.finished = self

    def connect(self, funcao):
        self._ao_terminar.append(funcao)

    def confirmar(self, df=None):
        self.callback(self.df if df is None else df)
        for f in self._ao_terminar:
            f(QDialog.DialogCode.Accepted)

    def fechar_no_x(self):
        for f in self._ao_terminar:
            f(QDialog.DialogCode.Rejected)


class DfFalso:
    """Só o `len()` que a tela lê de uma planilha recém-carregada."""

    def __init__(self, linhas):
        self.linhas = linhas

    def __len__(self):
        return self.linhas


class DataManagerFalso:
    respostas = {}
    chamadas = []
    salvamentos = []
    respostas_salvar = []

    @classmethod
    def carregar_planilha_inteligente(cls, path, aba, cols):
        cls.chamadas.append((path, aba, cols))
        return cls.respostas.get(aba, (None, None, f"Aba {aba!r} não encontrada"))

    @classmethod
    def atualizar_excel_final(cls, path, aba, lista):
        cls.salvamentos.append((path, aba, lista))
        return cls.respostas_salvar.pop(0)


class CatalogoFalso:
    def __init__(self, revisoes=None):
        self.revisoes = revisoes or {}

    def __len__(self):
        return 7

    def classes_com_pdm(self):
        return [1, 2, 3]

    def contem(self, texto):
        return texto.startswith("PDM.1111")

    def resolver(self, texto):
        return None

    def por_codigo(self, codigo):
        if codigo not in self.revisoes:
            return None
        return type("P", (), {"revisao": self.revisoes[codigo]})()


@pytest.fixture
def tela(qt_interface, qtbot, monkeypatch):
    t = tela_mod.ModuloCriaFichas(None, None)
    qtbot.addWidget(t)
    t.selecoes, t.revisoes, t.resumos, t.avisos = [], [], [], []
    monkeypatch.setattr(tela_mod, "JanelaSelecao", lambda p, df, cb: t.selecoes.append(
        (df, cb, threading.current_thread() is threading.main_thread())))
    monkeypatch.setattr(tela_mod, "JanelaRevisaoPDM", lambda *a, **k: RevisaoFalsa(t.revisoes, *a, **k))
    monkeypatch.setattr(tela_mod, "JanelaResumo", lambda *a: JanelaFalsa(t.resumos, *a))
    caixas = {}
    for nome in ("warning", "critical", "information"):
        caixas[nome] = (lambda n: lambda parent, titulo, msg, *a: t.avisos.append((n, titulo, msg)))(nome)
        monkeypatch.setattr(tela_mod.QMessageBox, nome, caixas[nome])
    DataManagerFalso.respostas, DataManagerFalso.chamadas = {}, []
    DataManagerFalso.salvamentos, DataManagerFalso.respostas_salvar = [], []
    monkeypatch.setattr(backends, "DataManager", DataManagerFalso)
    return t


def _texto(tela):
    return tela.console.toPlainText()


def _esperar_log(qtbot, tela, trecho, timeout=3000):
    qtbot.waitUntil(lambda: trecho in _texto(tela), timeout=timeout)


def _folha(w):
    return w.styleSheet()


# --- montagem -------------------------------------------------------------------------

def test_monta_com_os_textos_e_estados(tela):
    assert tela.label_titulo.text() == "Módulo de Criação"
    assert list(tela.abas.abas) == ["Criação de Fichas", "Editar código do projeto"]
    assert tela.abas.get() == "Criação de Fichas"
    assert tela.rotulo_etapa1.text() == "1. Configuração Inicial"
    assert tela.rotulo_projeto.text() == "Código do Projeto:"
    assert tela.entry_projeto.placeholderText().startswith("Ex: SERVIÇOS AUXILIARES ELÉTRICOS / CAP.05")
    assert tela.entry_projeto.placeholderText().endswith("Evento de Pagamento: 2835 / 2835 a / 2836")
    assert tela.rotulo_pmib.text() == "Arquivo STATUS_PMIB:"
    assert tela.btn_pmib.text() == "Selecionar Excel (.xlsx)"
    assert tela.lbl_status.text() == "Aguardando..."
    assert tela.chk_pular.text() == "Pular IA (Dados já no Excel)" and not tela.chk_pular.isChecked()
    assert tela.btn_pdm.text() == "Selecionar planilha de PDMs (mestra)" and tela.btn_pdm.isEnabled()
    assert tela.lbl_status_pdm.text() == ""
    assert tela.rotulo_etapa2.text() == "2. Execução"
    assert tela.btn_run_ai.text() == "3. Analisar (IA)"
    assert tela.btn_run_auto.text() == "4. Robô Web"
    assert tela.btn_resumo.text() == "Ver Resumo"
    assert tela.btn_save.text() == "5. Salvar no Excel"
    assert tela.btn_reset.text() == estilo.mono("🗑️\nLimpar")      # emoji fixo: preto e branco
    for b in (tela.btn_run_ai, tela.btn_run_auto, tela.btn_resumo, tela.btn_save):
        assert not b.isEnabled()
    assert tela.btn_reset.isEnabled() and tela.btn_pmib.isEnabled()
    assert tela.progress.fracao == 0.0
    # aba de edição
    assert tela.rotulo_etapa1_edicao.text() == "1. Configuração da Edição"
    assert tela.rotulo_novo_projeto.text() == "Novo Código do Projeto:"
    assert tela.entry_novo_projeto.placeholderText() == "Ex: NOVO CÓDIGO AQUI..."
    assert tela.rotulo_excel_edicao.text() == "Selecionar Fichas (Excel):"
    assert tela.btn_excel_edicao.text() == "Abrir Excel e Selecionar"
    assert tela.lbl_status_edicao.text() == "Nenhum item selecionado."
    assert tela.rotulo_etapa2_edicao.text() == "2. Execução em Massa"
    assert tela.btn_run_edicao.text() == estilo.mono("▶ Iniciar Robô de Edição")
    assert not tela.btn_run_edicao.isEnabled()
    assert tela.progress_edicao.fracao == 0.0


def test_cores_dos_botoes_e_rotulos(tela):
    for b in (tela.btn_pmib, tela.btn_pdm, tela.btn_resumo, tela.btn_excel_edicao):
        assert b.property("variante") == "cinza"
    for b in (tela.btn_run_ai, tela.btn_run_auto, tela.btn_save, tela.btn_run_edicao):
        assert b.property("variante") == "primario"
    assert tela.btn_reset.property("variante") == "perigo"
    for b in (tela.btn_run_ai, tela.btn_run_auto, tela.btn_resumo, tela.btn_save, tela.btn_reset,
              tela.btn_run_edicao):
        assert f"color: {COLORS['text_white']}" in _folha(b)
    assert "font-size: 14px" in _folha(tela.btn_run_ai) and "bold" in _folha(tela.btn_run_ai)
    assert "font-size: 12px" in _folha(tela.btn_resumo) and "font-size: 12px" in _folha(tela.btn_save)
    for r in (tela.rotulo_etapa1, tela.rotulo_etapa2, tela.rotulo_etapa1_edicao, tela.rotulo_etapa2_edicao):
        assert COLORS["accent"] in _folha(r) and "16px" in _folha(r)
    assert "#808080" in _folha(tela.lbl_status) and "#808080" in _folha(tela.lbl_status_edicao)
    # CTkLabel sem text_color: o gray84 do tema (#D6D6D6), não o text_light do app.
    for r in (tela.rotulo_projeto, tela.rotulo_pmib, tela.rotulo_novo_projeto, tela.rotulo_excel_edicao):
        assert f"color: {controles.COR_TEXTO_CTK}" in _folha(r), r.text()
    assert controles.COR_TEXTO_CTK == "#D6D6D6"
    assert COLORS["accent"] in tela.progress.styleSheet()
    assert COLORS["accent"] in tela.progress_edicao.styleSheet()
    # O "▶" sai da fonte de símbolos (só o triângulo, como no Tk), não do Noto
    # Emoji (o "play" dentro de um quadrado).
    familias = _folha(tela.btn_run_edicao)
    assert familias.index("Segoe UI Symbol") < familias.index("DejaVu Sans") < familias.index("Noto Emoji")
    assert tela.chk_pular._cor_marcada == COLORS["primary"]
    assert tela.chk_pular._cor_hover == COLORS["primary_hover"]


def test_enter_nao_dispara_nenhum_botao(tela):
    # Lá o Tk não ligava tecla nenhuma aos botões da tela.
    for b in (tela.btn_pmib, tela.btn_pdm, tela.btn_run_ai, tela.btn_run_auto, tela.btn_resumo,
              tela.btn_save, tela.btn_reset, tela.btn_excel_edicao, tela.btn_run_edicao):
        assert not b.autoDefault() and not b.isDefault()


# --- Pular IA ---------------------------------------------------------------------------

def test_pular_ia_desliga_o_pdm_e_liga_o_processar(tela):
    tela.chk_pular.click()
    assert tela.chk_pular.isChecked()
    assert not tela.btn_pdm.isEnabled() and "background: #2B2B2B" in _folha(tela.btn_pdm)
    assert tela.btn_run_ai.isEnabled() and tela.btn_run_ai.text() == "3. Processar (Direto)"
    tela.chk_pular.click()
    assert tela.btn_pdm.isEnabled() and "background: #3A3A3A" in _folha(tela.btn_pdm)
    # Desmarcar não desliga o botão (como lá): só volta o texto.
    assert tela.btn_run_ai.isEnabled() and tela.btn_run_ai.text() == "3. Analisar (IA)"


# --- planilha do STATUS_PMIB --------------------------------------------------------------

def test_cancelar_o_dialogo_nao_faz_nada(tela, monkeypatch):
    pedidos = []
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: pedidos.append((a, k)) or "")
    tela.btn_pmib.click()
    assert pedidos == [(("cria_fichas.excel_pmib", "excel"), {"filetypes": [("Excel", "*.xlsx")]})]
    assert tela.file_path_excel is None and DataManagerFalso.chamadas == []


def test_sem_o_backend_avisa_antes_do_dialogo(tela, monkeypatch):
    monkeypatch.setattr(backends, "DataManager", None)
    pedidos = []
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: pedidos.append(a) or "")
    monkeypatch.setattr(tela_mod.QMessageBox, "warning", lambda *a: tela.avisos.append(a[1]))
    tela.selecionar_excel_pmib()
    assert pedidos == []
    assert tela.avisos == ["Módulo indisponível"]


def test_planilha_carregada_preenche_o_projeto_e_abre_a_selecao(tela, qtbot, monkeypatch):
    df = DfFalso(12)
    DataManagerFalso.respostas = {"Lista de Materiais": (df, "PROJ-123", None)}
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "/d/_STATUS_PMIB.xlsx")
    tela.selecionar_excel_pmib()
    assert DataManagerFalso.chamadas == [("/d/_STATUS_PMIB.xlsx", "Lista de Materiais", ["DESCRIÇÃO", "CÓDIGO PMIB"])]
    assert tela.file_path_excel == "/d/_STATUS_PMIB.xlsx" and tela.df_data_completo is df
    assert tela.entry_projeto.text() == "PROJ-123"
    assert tela.selecoes == [(df, tela.pos_selecao, True)]
    _esperar_log(qtbot, tela, "> Código de Projeto preenchido automaticamente.")
    assert "> Carregado: 12 linhas." in _texto(tela)


def test_planilha_sem_a_aba_cai_na_primeira_e_sem_codigo_nao_mexe_no_projeto(tela, monkeypatch):
    df = DfFalso(3)
    DataManagerFalso.respostas = {0: (df, None, None)}
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "/d/x.xlsx")
    tela.entry_projeto.setText("JA DIGITADO")
    tela.selecionar_excel_pmib()
    assert [c[1] for c in DataManagerFalso.chamadas] == ["Lista de Materiais", 0]
    assert tela.entry_projeto.text() == "JA DIGITADO"
    assert len(tela.selecoes) == 1


def test_planilha_que_nao_abre_mostra_o_erro(tela, monkeypatch):
    DataManagerFalso.respostas = {0: (None, None, "Colunas não encontradas")}
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "/d/x.xlsx")
    tela.selecionar_excel_pmib()
    assert tela.avisos == [("critical", "Erro", "Colunas não encontradas")]
    assert tela.selecoes == []


def test_pos_selecao_numera_do_zero_e_marca_o_botao(tela, qtbot, pd):
    tela.df_data_completo = pd.DataFrame({"DESCRIÇÃO": [f"ITEM {i}" for i in range(6)],
                                          "CÓDIGO PMIB": [""] * 6})
    tela.pos_selecao([2, 4, 5])
    assert list(tela.df_data_selecionado.index) == [0, 1, 2]
    assert list(tela.df_data_selecionado["DESCRIÇÃO"]) == ["ITEM 2", "ITEM 4", "ITEM 5"]
    assert tela.lbl_status.text() == "3 itens selecionados"
    assert COLORS["accent"] in _folha(tela.lbl_status)
    assert f"background: {COLORS['primary']}" in _folha(tela.btn_pmib)
    assert "#454545" in _folha(tela.btn_pmib)          # o hover continua o de antes
    assert "background: #3A3A3A" in _folha(tela.btn_pdm)
    _esperar_log(qtbot, tela, "> Selecionado: 3 itens.")


def test_planilha_de_pdms(tela, qtbot, monkeypatch):
    pedidos = []
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file",
                        lambda *a, **k: pedidos.append((a, k)) or "/d/pdms/PDM_MASTER.xlsx")
    tela.btn_pdm.click()
    assert pedidos == [(("cria_fichas.excel_pdm", "excel"), {"filetypes": [("Arquivos Excel", "*.xlsx;*.xls")]})]
    assert tela.file_path_pdm == "/d/pdms/PDM_MASTER.xlsx"
    assert tela.btn_run_ai.isEnabled()
    assert f"background: {COLORS['primary']}" in _folha(tela.btn_pdm)
    assert tela.lbl_status_pdm.text() == "Selecionado: PDM_MASTER.xlsx"
    assert COLORS["accent"] in _folha(tela.lbl_status_pdm)
    _esperar_log(qtbot, tela, "> PDMs carregados: PDM_MASTER.xlsx")


def test_planilha_de_pdms_cancelada(tela, monkeypatch):
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "")
    tela.selecionar_excel_pdm()
    assert tela.file_path_pdm is None and not tela.btn_run_ai.isEnabled()


# --- IA ---------------------------------------------------------------------------------

def test_ia_sem_projeto_ou_sem_pdms_avisa(tela):
    tela.btn_run_ai.setEnabled(True)
    tela.run_ai_thread()
    assert tela.avisos == [("warning", "Aviso", "Preencha o Código do Projeto.")]
    tela.entry_projeto.setText("PROJ")
    tela.run_ai_thread()
    assert tela.avisos[1] == ("warning", "Aviso", "Selecione o arquivo de PDMs antes de iniciar a IA.")
    assert tela.revisoes == [] and tela.btn_run_ai.isEnabled()


def _selecionar_pular_ia(tela, pd):
    tela.df_data_completo = pd.DataFrame({
        "DESCRIÇÃO": ["VALVULA ESFERA 2 POL", "MOTOR ELETRICO TRIFASICO 50 CV"],
        "CÓDIGO PMIB": ["", ""],
        "PDM": ["PDM.1111.001 - VALVULA", "PDM.2222.002 - MOTOR"],
        "UNIDADE": ["Peça", "Unidade"],
    })
    tela.pos_selecao([0, 1])
    tela.entry_projeto.setText("PROJ-9")
    tela.chk_pular.click()


def test_pular_ia_le_o_excel_e_abre_a_revisao(tela, qtbot, pd):
    _selecionar_pular_ia(tela, pd)
    tela.btn_run_ai.click()
    # Desligado NO CLIQUE e com a barra andando (modo indeterminado).
    assert not tela.btn_run_ai.isEnabled()
    qtbot.waitUntil(lambda: bool(tela.revisoes), timeout=3000)
    revisao = tela.revisoes[0]
    assert revisao.na_interface and revisao.catalogo is None
    df = revisao.df
    assert list(df["item_processado"]) == [0, 1]
    assert list(df["codigo_projeto"]) == ["PROJ-9", "PROJ-9"]
    assert list(df["pdm_escolhido"]) == ["PDM.1111.001 - VALVULA", "PDM.2222.002 - MOTOR"]
    assert list(df["descricao_curta"]) == ["VALVULA ESFERA 2 POL", "MOTOR ELETRICO TRIFASICO 50 CV"[:40]]
    assert list(df["origem"]) == ["Nacional"] * 2 and list(df["tipo"]) == ["Não Reparável"] * 2
    assert list(df["unidade"]) == ["Peça", "Unidade"]
    assert list(df["tipo de fabricação"]) == ["Catálogo"] * 2
    _esperar_log(qtbot, tela, "> Abrindo janela de Revisão...")
    texto = _texto(tela)
    assert "> Modo 'Pular IA'. Lendo dados do Excel..." in texto
    assert "> Processados 2 itens." in texto
    # A barra parou e voltou a zero; o botão continua desligado enquanto a
    # revisão está aberta (a cadeia é uma tarefa só).
    qtbot.waitUntil(lambda: tela.progress.maximum() == 1000, timeout=2000)
    assert tela.progress.fracao == 0.0
    assert not tela.btn_run_ai.isEnabled()


def test_pular_ia_durante_a_tarefa_nao_religa_o_botao(tela, qtbot, pd):
    _selecionar_pular_ia(tela, pd)
    tela.btn_run_ai.click()
    qtbot.waitUntil(lambda: bool(tela.revisoes), timeout=3000)
    tela.chk_pular.click()
    tela.chk_pular.click()
    assert not tela.btn_run_ai.isEnabled()
    assert tela.btn_run_ai.text() == "3. Processar (Direto)"


def test_revisao_confirmada_libera_o_robo(tela, qtbot, pd):
    _selecionar_pular_ia(tela, pd)
    tela.btn_run_ai.click()
    qtbot.waitUntil(lambda: bool(tela.revisoes), timeout=3000)
    revisado = pd.DataFrame({"descricao_original": ["A", "B", "C"]})
    tela.revisoes[0].confirmar(revisado)
    assert tela.df_processed is revisado
    assert tela.btn_run_auto.isEnabled()
    assert f"background: {COLORS['accent']}" in _folha(tela.btn_run_auto)
    assert not tela.btn_run_ai.isEnabled() and tela.btn_run_ai.text() == "3. Analisar (OK)"
    _esperar_log(qtbot, tela, "> Revisão OK. 3 itens prontos.")
    # Depois da cadeia, o "Pular IA" volta a religar o botão (como lá).
    tela.chk_pular.click()
    tela.chk_pular.click()
    assert tela.btn_run_ai.isEnabled()


def test_revisao_fechada_no_x_devolve_o_botao(tela, qtbot, pd):
    _selecionar_pular_ia(tela, pd)
    tela.btn_run_ai.click()
    qtbot.waitUntil(lambda: bool(tela.revisoes), timeout=3000)
    tela.revisoes[0].fechar_no_x()
    assert tela.btn_run_ai.isEnabled() and tela.btn_run_ai.text() == "3. Processar (Direto)"
    assert not tela.btn_run_auto.isEnabled()


def test_ia_falhando_vira_log_e_devolve_o_botao(tela, qtbot):
    tela.entry_projeto.setText("PROJ")
    tela.chk_pular.click()           # sem planilha selecionada: o worker estoura no None
    tela.btn_run_ai.click()
    _esperar_log(qtbot, tela, "> Erro no processamento:")
    qtbot.waitUntil(tela.btn_run_ai.isEnabled, timeout=2000)
    assert tela.revisoes == []
    assert tela.progress.maximum() == 1000


def test_ia_com_catalogo(tela, qtbot, pd, monkeypatch):
    class Categorizador(CategorizadorFalso):
        chamadas = []
        respostas = [{"pdm_escolhido": "PDM.1111.001 - VALVULA", "item_processado": 1,
                      "confianca": "alta", "justificativa": "é válvula"},
                     None,
                     {"pdm_escolhido": "PDM.9999.999 - INVENTADO", "item_processado": 3}]

    catalogo = CatalogoFalso()
    carregados = []
    monkeypatch.setattr(backends, "GeminiCategorizer", Categorizador)
    monkeypatch.setattr(tela_mod.pdm_catalogo, "carregar", lambda p: carregados.append(p) or catalogo)
    tela.controller = type("C", (), {"get_key": lambda self, k: f"chave-{k}"})()
    tela.df_data_completo = pd.DataFrame({"DESCRIÇÃO": ["VALVULA", "PARAFUSO SEXTAVADO M8", "CABO"],
                                          "CÓDIGO PMIB": ["", "", ""]})
    tela.pos_selecao([0, 1, 2])
    tela.entry_projeto.setText("PROJ-1")
    tela.file_path_pdm = "/d/PDM_MASTER.xlsx"
    tela.btn_run_ai.setEnabled(True)
    tela.btn_run_ai.click()
    qtbot.waitUntil(lambda: bool(tela.revisoes), timeout=3000)
    assert carregados == ["/d/PDM_MASTER.xlsx"]
    # As duas passadas e a guarda vêm do serviço, no worker, com o projeto do clique.
    assert Categorizador.chamadas == [("chave-GEMINI", ["VALVULA", "PARAFUSO SEXTAVADO M8", "CABO"],
                                       catalogo, "PROJ-1", False)]
    df = tela.revisoes[0].df
    # A revisão abre com o catálogo novo; o da tela (o do robô) só muda no CONFIRMAR.
    assert tela.revisoes[0].catalogo is catalogo and tela.catalogo is None
    assert list(df["pdm_escolhido"]) == ["PDM.1111.001 - VALVULA", "NENHUM", "NENHUM"]
    assert list(df["codigo_projeto"]) == ["PROJ-1"] * 3
    assert list(df["descricao_original"]) == ["VALVULA", "PARAFUSO SEXTAVADO M8", "CABO"]
    # O que a revisão mostra (confiança, origem do NENHUM, "por quê") vai junto.
    assert list(df["origem_do_nenhum"]) == ["", "sem_resposta", "fora_do_catalogo"]
    assert list(df["pdm_ia"]) == ["PDM.1111.001 - VALVULA", "NENHUM", "NENHUM"]
    assert df["justificativa"][0] == "é válvula"
    _esperar_log(qtbot, tela, "> Abrindo janela de Revisão...")
    texto = _texto(tela)
    assert "> Processando com IA (openrouter/google/gemini-2.5-flash)..." in texto
    assert "> Catálogo: 7 PDMs, 3 classes com PDM." in texto
    assert "> lote 1/1" in texto
    assert (">  -> ⚠️ Item 2 sem resposta da IA. Marcado 'NENHUM' para revisão: "
            "PARAFUSO SEXTAVADO M8") in texto
    assert ">  -> ⚠️ Item 3: PDM fora do catalogo: 'PDM.9999.999 - INVENTADO'. Marcado 'NENHUM'." in texto
    assert "> IA Finalizada. 3 itens | sem resposta: 1 | PDM fora do catálogo: 1" in texto
    tela.revisoes[0].confirmar()
    assert tela.catalogo is catalogo and tela.df_processed is df


def test_ia_e_revisao_confirmada_grava_a_calibracao_com_os_modelos_do_lote(tela, qtbot, pd, monkeypatch):
    # 2026-10-08: o que a IA disse x o que a revisão decidiu, para a confiança
    # virar medição. Os modelos são os da rodada que gerou ESTE lote (viajam
    # com ele até o CONFIRMAR, como o catálogo e o Excel).
    gravados = []
    monkeypatch.setattr(tela_mod.cria_fichas_escolha, "gravar_calibracao",
                        lambda linhas, modelos=None: gravados.append((linhas, modelos)) or 2)

    class Categorizador(CategorizadorFalso):
        chamadas = []
        respostas = [{"pdm_escolhido": "PDM.1111.001 - A"}, {"pdm_escolhido": "NENHUM"}]

    monkeypatch.setattr(backends, "GeminiCategorizer", Categorizador)
    monkeypatch.setattr(tela_mod.pdm_catalogo, "carregar", lambda p: CatalogoFalso())
    tela.controller = type("C", (), {"get_key": lambda self, k: "chave"})()
    tela.df_data_completo = pd.DataFrame({"DESCRIÇÃO": ["A", "B"], "CÓDIGO PMIB": ["", ""]})
    tela.pos_selecao([0, 1])
    tela.entry_projeto.setText("PROJ")
    tela.file_path_pdm = "/d/PDM_MASTER.xlsx"
    tela.btn_run_ai.setEnabled(True)
    tela.btn_run_ai.click()
    qtbot.waitUntil(lambda: bool(tela.revisoes), timeout=3000)
    assert gravados == []                       # nada antes do CONFIRMAR
    revisado = tela.revisoes[0].df.copy()
    revisado.loc[1, "pdm_escolhido"] = "PDM.1111.002 - B"
    tela.revisoes[0].confirmar(revisado)
    (linhas, modelos), = gravados
    assert [linha["pdm_escolhido"] for linha in linhas] == ["PDM.1111.001 - A", "PDM.1111.002 - B"]
    assert [linha["pdm_ia"] for linha in linhas] == ["PDM.1111.001 - A", "NENHUM"]
    assert modelos == {"passada_1": "openrouter/google/gemini-2.5-flash-lite",
                       "passada_2": "openrouter/google/gemini-2.5-flash"}
    _esperar_log(qtbot, tela, "> Revisão OK. 2 itens prontos.")
    texto = _texto(tela)
    assert texto.index("> Calibração: 2 itens registrados.") < texto.index("> Revisão OK.")


def test_pular_ia_nao_leva_modelos_para_a_calibracao(tela, qtbot, pd, monkeypatch):
    gravados = []
    monkeypatch.setattr(tela_mod.cria_fichas_escolha, "gravar_calibracao",
                        lambda linhas, modelos=None: gravados.append(modelos) or 0)
    _selecionar_pular_ia(tela, pd)
    tela.btn_run_ai.click()
    qtbot.waitUntil(lambda: bool(tela.revisoes), timeout=3000)
    tela.revisoes[0].confirmar()
    assert gravados == [None]
    _esperar_log(qtbot, tela, "> Revisão OK. 2 itens prontos.")
    assert "Calibração" not in _texto(tela)    # 0 registrados: nada no log, como lá


def test_calibracao_que_falha_nao_trava_a_automacao(tela, qtbot, pd, monkeypatch):
    def quebrada(linhas, modelos=None):
        raise OSError("disco cheio")

    monkeypatch.setattr(tela_mod.cria_fichas_escolha, "gravar_calibracao", quebrada)
    tela._pos_revisao_concluida(pd.DataFrame({"descricao_original": ["A"]}))
    _esperar_log(qtbot, tela, "> Revisão OK. 1 itens prontos.")
    assert "> Calibração não registrada: disco cheio" in _texto(tela)
    assert tela.btn_run_auto.isEnabled()


def test_ia_usa_a_selecao_e_a_planilha_do_clique(tela, qtbot, pd, monkeypatch):
    # Correção 1 (revisão E4.9): a IA leva minutos e "Selecionar Excel" continua
    # ligado. Trocar as linhas (ou a planilha de PDMs) no meio não pode pôr as
    # descrições novas sob as respostas que a IA deu para as antigas.
    segurar, entrou, lotes, carregados = threading.Event(), threading.Event(), [], []

    class Categorizador(CategorizadorFalso):
        respostas = [{"pdm_escolhido": "PDM.1111.001 - A"}, {"pdm_escolhido": "PDM.1111.002 - B"}]

        def __init__(self, chave):
            super().__init__(chave)
            entrou.set()
            segurar.wait(3)          # a pessoa mexe na tela enquanto isto espera

        def classificar_para_revisao(self, df, catalogo, codigo_projeto, callback_log=None):
            lotes.append((self.chave, list(df["DESCRIÇÃO"])))
            return super().classificar_para_revisao(df, catalogo, codigo_projeto, callback_log)

    monkeypatch.setattr(backends, "GeminiCategorizer", Categorizador)
    monkeypatch.setattr(tela_mod.pdm_catalogo, "carregar", lambda p: carregados.append(p) or CatalogoFalso())
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "/d/OUTRO_MASTER.xlsx")
    tela.controller = type("C", (), {"get_key": lambda self, k: "chave-do-clique"})()
    tela.df_data_completo = pd.DataFrame({"DESCRIÇÃO": ["A", "B", "C", "D"], "CÓDIGO PMIB": [""] * 4})
    tela.pos_selecao([0, 1])
    tela.entry_projeto.setText("PROJ")
    tela.file_path_pdm = "/d/PDM_MASTER.xlsx"
    tela.btn_run_ai.setEnabled(True)
    tela.btn_run_ai.click()
    assert entrou.wait(3)
    tela.pos_selecao([2, 3])                 # outras linhas, com a IA rodando
    tela.selecionar_excel_pdm()              # e outra planilha de PDMs
    tela.controller = type("C", (), {"get_key": lambda self, k: "outra-chave"})()
    segurar.set()
    qtbot.waitUntil(lambda: bool(tela.revisoes), timeout=3000)
    assert carregados == ["/d/PDM_MASTER.xlsx"]
    assert lotes == [("chave-do-clique", ["A", "B"])]
    df = tela.revisoes[0].df
    assert list(zip(df["descricao_original"], df["pdm_escolhido"])) == [
        ("A", "PDM.1111.001 - A"), ("B", "PDM.1111.002 - B")]


def test_falha_ao_abrir_a_revisao_devolve_o_botao(tela, qtbot, pd, monkeypatch, capsys):
    # Correção 2: a continuação na thread da interface não pode morrer calada
    # (a ponte engole a exceção) e deixar "3. Analisar" desligado para sempre.
    def quebrada(*a, **k):
        raise RuntimeError("janela quebrada")

    monkeypatch.setattr(tela_mod, "JanelaRevisaoPDM", quebrada)
    _selecionar_pular_ia(tela, pd)
    tela.btn_run_ai.click()
    _esperar_log(qtbot, tela, "> Erro ao abrir a revisão: RuntimeError: janela quebrada")
    assert tela.btn_run_ai.isEnabled() and not tela._ia_em_andamento
    assert tela.progress.maximum() == 1000
    assert "janela quebrada" in capsys.readouterr().err       # o traceback vai para o log de erros


def test_robo_so_aponta_para_dados_revisados(tela, qtbot, pd):
    # Herdado da interface antiga (achado 6a): o resultado da IA ia para `df_processed` antes
    # da revisão; com "4. Robô Web" ligado de um lote anterior, fechar a revisão
    # nova no "X" deixava o robô apontado para dados que ninguém conferiu.
    _selecionar_pular_ia(tela, pd)
    revisado = pd.DataFrame({"descricao_original": ["LOTE ANTERIOR"]})
    tela._pos_revisao_concluida(revisado)
    assert tela.btn_run_auto.isEnabled()
    tela.chk_pular.click()
    tela.chk_pular.click()                     # religa o "3. Processar", como lá
    tela.btn_run_ai.click()
    qtbot.waitUntil(lambda: bool(tela.revisoes), timeout=3000)
    assert tela.df_processed is revisado       # a revisão nova ainda está aberta
    tela.revisoes[0].fechar_no_x()
    assert tela.df_processed is revisado       # e foi recusada


def test_ia_sem_o_backend_nao_comeca(tela, monkeypatch):
    monkeypatch.setattr(backends, "GeminiCategorizer", None)
    monkeypatch.setattr(tela_mod.QMessageBox, "warning", lambda *a: tela.avisos.append(a[1]))
    tela.entry_projeto.setText("PROJ")
    tela.file_path_pdm = "/d/p.xlsx"
    tela.btn_run_ai.setEnabled(True)
    tela.run_ai_thread()
    assert tela.avisos == ["Módulo indisponível"]
    assert tela.btn_run_ai.isEnabled() and tela.progress.maximum() == 1000


def test_revisao_sem_dados_avisa_e_devolve_o_botao(tela, pd):
    tela.abrir_revisao_pdm(pd.DataFrame([]), None)
    assert tela.avisos == [("critical", "Erro", "Nenhum dado processado.")]
    assert tela.btn_run_ai.isEnabled() and tela.revisoes == []


# --- robô de criação ----------------------------------------------------------------------

class RoboFalso:
    """AutomacaoPMIB: respostas por descrição, na ordem em que são pedidas."""

    instancias = []
    roteiro = {}

    def __init__(self):
        self.portais = []
        self.itens = []
        self.driver = self
        self.saiu = False
        self.threads = set()
        RoboFalso.instancias.append(self)

    def iniciar_driver(self):
        self.threads.add(threading.current_thread() is threading.main_thread())

    def abrir_portal(self, url):
        self.portais.append(url)

    def processar_item_individual(self, row):
        self.itens.append((row["descricao_original"], row["pdm_escolhido"]))
        return RoboFalso.roteiro[row["descricao_original"]].pop(0)

    def quit(self):
        self.saiu = True

    def atualizar_projeto_em_massa(self, pmib, novo):
        self.itens.append((pmib, novo))
        return RoboFalso.roteiro.get(pmib, ("SUCESSO", ""))


@pytest.fixture
def robo(tela, monkeypatch, pd):
    RoboFalso.instancias, RoboFalso.roteiro = [], {}
    estado = {"pausas": [], "decisoes": [], "perguntas": [], "preparos": []}
    monkeypatch.setattr(backends, "AutomacaoPMIB", RoboFalso)
    monkeypatch.setattr(tela, "pausar_e_esperar", lambda msg, **k: estado["pausas"].append(
        (msg, threading.current_thread() is threading.main_thread())))

    def acao(parent, msg_erro, pdm_atual):
        estado["perguntas"].append((msg_erro, pdm_atual, threading.current_thread() is threading.main_thread()))
        return estado["decisoes"].pop(0)

    monkeypatch.setattr(tela_mod, "JanelaAcaoRobo", acao)
    original = tela.avisar

    def avisar(titulo, msg, tipo="info", *, esperar=False):
        if titulo == "Preparo":
            estado["preparos"].append((msg, esperar))
            return
        original(titulo, msg, tipo, esperar=esperar)

    monkeypatch.setattr(tela, "avisar", avisar)
    # `descricao_curta` e `codigo_projeto`: o que a IA sempre devolve, e que a
    # revisão antes do portal (R2) exige -- sem eles o portal recusa o Salvar.
    tela.df_processed = pd.DataFrame([
        {"descricao_original": "VALVULA ESFERA 2 POL INOX", "pdm_escolhido": "PDM.1111.001 - VALVULA"},
        {"descricao_original": "MOTOR 50CV", "pdm_escolhido": "NENHUM"},
        {"descricao_original": "CABO FLEXIVEL", "pdm_escolhido": "PDM.3333.003 - CABO"},
        {"descricao_original": "PARAFUSO", "pdm_escolhido": "PDM.4444.004 - PARAFUSO"},
    ]).assign(descricao_curta="ITEM", codigo_projeto="PRJ-1")
    tela._pos_revisao_concluida(tela.df_processed)
    return estado


# --- revisão antes do portal (R2) -------------------------------------------------------

@pytest.fixture
def revisao(monkeypatch):
    registro = {"chamadas": [], "resposta": revisao_portal.SEM_ERROS}

    def perguntar(parent, problemas, total):
        registro["chamadas"].append((parent, [(p.ficha, p.interno) for p in problemas], total))
        return registro["resposta"]

    monkeypatch.setattr(revisao_portal, "perguntar_revisao", perguntar)
    return registro


def _lote_com_um_erro(tela, pd):
    tela.df_processed = pd.DataFrame([
        {"descricao_original": "VALVULA", "pdm_escolhido": "PDM.1 - V", "descricao_curta": "VALVULA",
         "codigo_projeto": "P1"},
        {"descricao_original": "CONEXÃO", "pdm_escolhido": "PDM.2 - C", "descricao_curta": "CONEXÃO",
         "codigo_projeto": "P1"},
        {"descricao_original": "CABO", "pdm_escolhido": "PDM.3 - C", "descricao_curta": "CABO",
         "codigo_projeto": "P1"},
    ])
    tela._pos_revisao_concluida(tela.df_processed)


def test_revisao_tira_as_fichas_com_erro(tela, robo, qtbot, pd, revisao):
    _lote_com_um_erro(tela, pd)
    RoboFalso.roteiro = {"VALVULA": [("SUCESSO", ("45.1", "PDM.1 - V, R0"))],
                         "CABO": [("SUCESSO", ("45.3", "PDM.3 - C, R0"))]}
    tela.btn_run_auto.click()
    qtbot.waitUntil(lambda: bool(tela.resumos), timeout=3000)
    assert revisao["chamadas"] == [(tela, [("CONEXÃO", "Input_ShortText")], 3)]
    assert [i[0] for i in RoboFalso.instancias[0].itens] == ["VALVULA", "CABO"]
    assert list(tela.df_resumo_final["descricao_original"]) == ["VALVULA", "CABO"]
    _esperar_log(qtbot, tela, "> Processando Item 2/2: CABO...")   # índice refeito: 2 de 2
    texto = _texto(tela)
    assert "> Revisão antes do portal: 1 problema(s) em 1 ficha(s) de 3." in texto
    assert "> [!] CONEXÃO · Texto breve do material (Input_ShortText) · 'CONEXÃO' · " in texto
    # O lote confirmado continua inteiro: só o que foi ao robô é que encolheu.
    assert len(tela.df_processed) == 3


def test_revisao_cancelar_nao_abre_o_robo(tela, robo, qtbot, pd, revisao):
    revisao["resposta"] = None
    _lote_com_um_erro(tela, pd)
    tela.btn_run_auto.click()
    _esperar_log(qtbot, tela, "> Cancelado na revisão antes do portal.")
    assert RoboFalso.instancias == [] and tela.btn_run_auto.isEnabled() and not tela._robo_ativo


def test_revisao_sem_problema_nada_aparece(tela, robo, qtbot, revisao):
    RoboFalso.roteiro = {"VALVULA ESFERA 2 POL INOX": [("SUCESSO", ("1", "P"))], "MOTOR 50CV": [("PULAR", None)],
                         "CABO FLEXIVEL": [("SUCESSO", ("3", "P"))], "PARAFUSO": [("SUCESSO", ("4", "P"))]}
    tela.btn_run_auto.click()
    qtbot.waitUntil(lambda: bool(tela.resumos), timeout=3000)
    assert revisao["chamadas"] == [] and "Revisão antes do portal" not in _texto(tela)


def test_robo_completo(tela, robo, qtbot):
    RoboFalso.roteiro = {
        "VALVULA ESFERA 2 POL INOX": [("SUCESSO", ("4500001.0001", "PDM.1111.001 - VALVULA, R1"))],
        "MOTOR 50CV": [("PULAR", None)],
        "CABO FLEXIVEL": [("ERRO", "Timeout no combo"), ("ERRO", "de novo"),
                          ("SUCESSO", ("4500001.0003", "PDM.5555.005 - CABO NOVO, R0"))],
        "PARAFUSO": [("ERRO", "Botão não achado")],
    }
    robo["decisoes"] = [DecisaoRobo("RETRY"), DecisaoRobo("CHANGE_PDM", "PDM.5555.005 - CABO NOVO"),
                        DecisaoRobo("SKIP")]
    tela.btn_run_auto.click()
    assert not tela.btn_run_auto.isEnabled()                       # desligado NO CLIQUE
    qtbot.waitUntil(lambda: bool(tela.resumos), timeout=3000)
    qtbot.waitUntil(tela.btn_run_auto.isEnabled, timeout=2000)

    bot = RoboFalso.instancias[0]
    assert bot.threads == {False}
    assert robo["pausas"] == [(MSG_LOGIN_NOVA_FICHA, False)]
    url = "https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList"
    assert bot.portais == [url, url]                                 # abriu + reset do SKIP
    assert bot.itens == [
        ("VALVULA ESFERA 2 POL INOX", "PDM.1111.001 - VALVULA"),
        ("MOTOR 50CV", "NENHUM"),
        ("CABO FLEXIVEL", "PDM.3333.003 - CABO"),
        ("CABO FLEXIVEL", "PDM.3333.003 - CABO"),
        ("CABO FLEXIVEL", "PDM.5555.005 - CABO NOVO"),
        ("PARAFUSO", "PDM.4444.004 - PARAFUSO"),
    ]
    assert robo["perguntas"] == [("Timeout no combo", "PDM.3333.003 - CABO", False),
                                 ("de novo", "PDM.3333.003 - CABO", False),
                                 ("Botão não achado", "PDM.4444.004 - PARAFUSO", False)]
    msg = "Certifique-se de que a tela do navegador está na lista principal antes de clicar em OK."
    assert robo["preparos"] == [(msg, True), (msg, True)]          # RETRY e CHANGE_PDM ESPERAM o OK
    assert bot.saiu

    resumo = tela.df_resumo_final
    assert list(resumo["descricao_original"]) == ["VALVULA ESFERA 2 POL INOX", "MOTOR 50CV", "CABO FLEXIVEL",
                                                  "PARAFUSO"]
    assert list(resumo["PMIB_CRIADO"]) == ["4500001.0001", "VERIFICAR (PULADO)", "4500001.0003",
                                           "VERIFICAR (PULADO)"]
    assert tela.resumos[0].args == (tela, resumo) and tela.resumos[0].na_interface
    assert tela.btn_save.isEnabled() and tela.btn_resumo.isEnabled()

    _esperar_log(qtbot, tela, "> Montando resumo final...")
    texto = _texto(tela)
    for linha in (
        "> Iniciando Robô...",
        "> Processando Item 1/4: VALVULA ESFERA 2 POL INOX...",
        ">  -> ✅ SUCESSO: PMIB 4500001.0001 | PDM PDM.1111.001 - VALVULA, R1",
        ">  -> ⏭️ PULADO automaticamente (PDM era 'NENHUM').",
        ">  -> ❌ ERRO no Selenium: Timeout no combo",
        ">  -> 🔄 Retentativa solicitada pelo usuário.",
        ">  -> ✏️ PDM alterado pelo usuário para: PDM.5555.005 - CABO NOVO",
        ">  -> ⏭️ Item PULADO pelo usuário.",
        "> Montando resumo final...",
    ):
        assert linha in texto, linha
    # O progresso do último item (4/4) chegou à barra pela thread da interface.
    qtbot.waitUntil(lambda: tela.progress.fracao == 1.0, timeout=2000)


def test_robo_parar_salva_o_parcial(tela, robo, qtbot):
    RoboFalso.roteiro = {
        "VALVULA ESFERA 2 POL INOX": [("SUCESSO", ("4500001.0001", "PDM.1111.001 - VALVULA, R1"))],
        "MOTOR 50CV": [("ERRO", "falhou")],
    }
    robo["decisoes"] = [DecisaoRobo("STOP")]
    tela.run_automation_thread()
    qtbot.waitUntil(lambda: bool(tela.resumos), timeout=3000)
    assert [i[0] for i in RoboFalso.instancias[0].itens] == ["VALVULA ESFERA 2 POL INOX", "MOTOR 50CV"]
    assert list(tela.df_resumo_final["PMIB_CRIADO"]) == ["4500001.0001", "INTERROMPIDO"]
    _esperar_log(qtbot, tela, ">  -> 🛑 Automação interrompida pelo usuário. Salvando progresso parcial...")


def test_robo_erro_fatal_vira_log_e_devolve_o_botao(tela, robo, qtbot):
    RoboFalso.roteiro = {}                                     # KeyError no primeiro item
    tela.run_automation_thread()
    _esperar_log(qtbot, tela, "> Erro Fatal na Thread do Robô:")
    qtbot.waitUntil(tela.btn_run_auto.isEnabled, timeout=2000)
    assert tela.resumos == [] and not tela.btn_save.isEnabled()
    # Pendência de 2026-10-11: como o robô de edição, o erro fatal fecha o
    # navegador (antes ele ficava aberto).
    assert RoboFalso.instancias[0].saiu


def test_robo_sem_o_backend_nao_comeca(tela, robo, monkeypatch):
    monkeypatch.setattr(backends, "AutomacaoPMIB", None)
    monkeypatch.setattr(tela_mod.QMessageBox, "warning", lambda *a: tela.avisos.append(a[1]))
    tela.run_automation_thread()
    assert tela.avisos == ["Módulo indisponível"] and tela.btn_run_auto.isEnabled()


@pytest.mark.parametrize("pedido, gravado, revisoes, esperado", [
    ("PDM.1111.001 - VALVULA", "PDM.2222.002 - OUTRO, R1", {},
     ">  -> ⚠️ DIVERGÊNCIA no PMIB 45.1: pedimos PDM.1111.001 e o portal gravou PDM.2222.002. Confira a ficha."),
    ("PDM.1111.001 - VALVULA", "PDM.1111.001 - VALVULA, R0", {"PDM.1111.001": 2},
     ">  -> ⚠️ PMIB 45.1: a ficha ficou na revisão R0 do PDM.1111.001, mas o catálogo já tem R2. "
     "A Itaipu costuma pedir a revisão mais nova."),
    ("PDM.1111.001 - VALVULA", "PDM.1111.001 - VALVULA, R3", {"PDM.1111.001": 1},
     ">  -> ℹ️ PMIB 45.1: o portal usou R3 do PDM.1111.001 e a sua planilha de PDMs só tem até R1. "
     "Vale pedir um Master atualizado à Itaipu."),
    ("PDM.1111.001 - VALVULA", "PDM.1111.001 - VALVULA, R1", {"PDM.1111.001": 1}, None),
    ("NENHUM", "PDM.1111.001 - VALVULA, R1", {}, None),
])
def test_conferencia_do_pdm_gravado(tela, qtbot, pedido, gravado, revisoes, esperado):
    tela._conferir_pdm_do_portal(pedido=pedido, gravado=gravado, pmib="45.1", catalogo=CatalogoFalso(revisoes))
    tela.log("fim")
    _esperar_log(qtbot, tela, "> fim")
    if esperado is None:
        assert _texto(tela) == "> fim"
    else:
        assert esperado in _texto(tela)


# --- resumo e salvar ---------------------------------------------------------------------

def test_ver_resumo_nao_abre_duas_janelas(tela):
    tela.abrir_resumo_manual()
    assert tela.resumos == []
    df = object()
    tela.df_resumo_final = df
    tela.btn_resumo.setEnabled(True)
    tela.btn_resumo.click()
    tela.btn_resumo.click()
    assert len(tela.resumos) == 1 and tela.resumos[0].levantada == 1
    tela.resumos[0].visivel = False                    # a pessoa fechou: abre de novo
    tela.btn_resumo.click()
    assert len(tela.resumos) == 2
    tela.df_resumo_final = object()                    # lote novo: a janela velha dá lugar à nova
    tela.btn_resumo.click()
    assert len(tela.resumos) == 3 and tela.resumos[1].fechada


def _resumo(pd):
    return pd.DataFrame({"descricao_original": ["A", "B"], "PMIB_CRIADO": ["45.1", "VERIFICAR (PULADO)"],
                         "PDM_COM_REVISAO": ["PDM.1, R1", "VERIFICAR (PULADO)"]})


def test_resumos_fechados_nao_se_acumulam(tela, qtbot, pd, monkeypatch):
    # Correção 3: cada "Ver Resumo" depois de fechar cria uma janela nova; a
    # fechada (com a tabela inteira) não pode ficar escondida como filha da tela.
    # O `destroy()` da interface antiga a liberava.
    from PySide6.QtCore import QCoreApplication, QEvent

    from sigft.app_qt.views import janelas

    monkeypatch.setattr(tela_mod, "JanelaResumo", janelas.JanelaResumo)
    tela.df_resumo_final = _resumo(pd)
    for _ in range(3):
        tela.abrir_resumo_manual()
        janela = tela.janela_resumo
        assert janela.isVisible() and janela.tree.topLevelItemCount() == 2
        janela.botao_fechar.click()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert tela.findChildren(janelas.JanelaResumo) == []
    tela.abrir_resumo_manual()                 # a referência velha (apagada) não atrapalha
    assert len(tela.findChildren(janelas.JanelaResumo)) == 1
    tela.janela_resumo.close()


def test_salvar_sem_dados_avisa(tela):
    tela.salvar_excel()
    assert tela.avisos == [("warning", "Aviso", "Não há dados processados para salvar.")]


def test_salvar_ok(tela, qtbot, pd):
    tela._excel_do_resumo = "/d/_STATUS_PMIB.xlsx"
    tela.df_resumo_final = _resumo(pd)
    DataManagerFalso.respostas_salvar = [(True, "2 linhas")]
    tela.salvar_excel()
    assert DataManagerFalso.salvamentos == [("/d/_STATUS_PMIB.xlsx", "Lista de Materiais", [
        ("A", "45.1", "PDM.1, R1"), ("B", "VERIFICAR (PULADO)", "VERIFICAR (PULADO)")])]
    assert tela.avisos == [("information", "Sucesso", "Planilha atualizada!\n2 linhas")]
    _esperar_log(qtbot, tela, "> ✅ Excel salvo com sucesso: 2 linhas")


def test_salvar_com_o_arquivo_aberto_pergunta_e_repete(tela, qtbot, pd, monkeypatch):
    tela._excel_do_resumo = "/d/_STATUS_PMIB.xlsx"
    tela.df_resumo_final = _resumo(pd)
    DataManagerFalso.respostas_salvar = [(False, "Arquivo aberto"), (False, "PermissionError"),
                                         (True, "ok")]
    perguntas = []
    respostas = [tela_mod.QMessageBox.StandardButton.Retry, tela_mod.QMessageBox.StandardButton.Retry]
    monkeypatch.setattr(tela_mod.QMessageBox, "warning",
                        lambda parent, titulo, msg, botoes=None, *a: perguntas.append((titulo, msg, botoes))
                        or respostas.pop(0))
    tela.salvar_excel()
    assert len(DataManagerFalso.salvamentos) == 3
    titulo, msg, botoes = perguntas[0]
    assert titulo == "Arquivo Aberto"
    assert msg == ("O arquivo Excel está ABERTO ou bloqueado.\n\nPor favor, FECHE o arquivo _STATUS_PMIB "
                   "no Excel e clique em 'Repetir' para tentar salvar novamente.")
    assert botoes == tela_mod.QMessageBox.StandardButton.Retry | tela_mod.QMessageBox.StandardButton.Cancel
    assert tela.avisos == [("information", "Sucesso", "Planilha atualizada!\nok")]


def test_salvar_cancelado(tela, qtbot, pd, monkeypatch):
    tela._excel_do_resumo = "/d/x.xlsx"
    tela.df_resumo_final = _resumo(pd)
    DataManagerFalso.respostas_salvar = [(False, "arquivo ABERTO")]
    monkeypatch.setattr(tela_mod.QMessageBox, "warning",
                        lambda *a: tela_mod.QMessageBox.StandardButton.Cancel)
    tela.salvar_excel()
    _esperar_log(qtbot, tela, "> ⚠️ Salvamento cancelado pelo usuário. Os dados não foram gravados no Excel.")
    assert len(DataManagerFalso.salvamentos) == 1


def test_salvar_outro_erro(tela, qtbot, pd):
    tela._excel_do_resumo = "/d/x.xlsx"
    tela.df_resumo_final = _resumo(pd)
    DataManagerFalso.respostas_salvar = [(False, "Aba não encontrada")]
    tela.salvar_excel()
    assert tela.avisos == [("critical", "Erro ao Salvar", "Aba não encontrada")]
    _esperar_log(qtbot, tela, "> ❌ Erro ao salvar Excel: Aba não encontrada")


# --- limpar --------------------------------------------------------------------------------

def test_limpar_volta_tudo_ao_comeco(tela, qtbot, pd):
    bot = RoboFalso()
    tela.bot = bot
    tela.file_path_excel, tela.file_path_pdm = "/d/a.xlsx", "/d/p.xlsx"
    tela.df_resumo_final = _resumo(pd)
    tela.entry_projeto.setText("PROJ")
    tela.lbl_status.setText("3 itens selecionados")
    tela.lbl_status_pdm.setText("Selecionado: p.xlsx")
    for b in (tela.btn_run_ai, tela.btn_run_auto, tela.btn_resumo, tela.btn_save, tela.btn_run_edicao):
        b.setEnabled(True)
    tela.btn_run_ai.setText("3. Analisar (OK)")
    tela._pos_revisao_concluida(_resumo(pd), catalogo=CatalogoFalso())
    tela.progress.definir(0.5)
    tela.progress_edicao.definir(0.5)
    tela.entry_novo_projeto.setText("NOVO")
    tela.log("linha velha")
    _esperar_log(qtbot, tela, "linha velha")

    tela.btn_reset.click()
    assert bot.saiu and tela.bot is None
    assert tela.file_path_excel is None and tela.file_path_pdm is None
    assert tela.df_processed is None and tela.df_resumo_final is None
    # O catálogo anda com o lote (os dois mudam no CONFIRMAR da revisão): sem o
    # lote e com a planilha de PDMs esquecida, ele também sai.
    assert tela.catalogo is None
    assert tela.df_edicao_completo is None and tela.df_edicao_selecionado is None
    assert tela.entry_projeto.text() == "" and tela.entry_novo_projeto.text() == ""
    assert tela.lbl_status.text() == "Aguardando..." and "#808080" in _folha(tela.lbl_status)
    assert tela.lbl_status_pdm.text() == ""
    assert "background: #3A3A3A" in _folha(tela.btn_pmib) and "background: #3A3A3A" in _folha(tela.btn_pdm)
    assert tela.btn_run_ai.text() == "3. Analisar (IA)"
    for b in (tela.btn_run_ai, tela.btn_run_auto, tela.btn_resumo, tela.btn_save, tela.btn_run_edicao):
        assert not b.isEnabled()
    assert f"background: {COLORS['primary']}" in _folha(tela.btn_run_auto)
    assert tela.progress.fracao == 0.0 and tela.progress_edicao.fracao == 0.0
    assert tela.lbl_status_edicao.text() == "Nenhum item selecionado."
    _esperar_log(qtbot, tela, "> Sistema limpo. Pronto para iniciar um novo lote.")
    assert "linha velha" not in _texto(tela)


# --- aba de edição -------------------------------------------------------------------------

def test_edicao_filtra_as_linhas_sem_pmib(tela, qtbot, pd, monkeypatch):
    df = pd.DataFrame({"DESCRIÇÃO": ["A", "B", "C", "D"],
                       "CÓDIGO PMIB": ["4500.1", "  ", None, "4500.4"]})
    DataManagerFalso.respostas = {"Lista de Materiais": (df, "PROJ-SUGERIDO", None)}
    pedidos = []
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file",
                        lambda *a, **k: pedidos.append((a, k)) or "/d/fichas.xlsx")
    tela.btn_excel_edicao.click()
    assert pedidos == [(("cria_fichas.excel_edicao", "excel"), {"filetypes": [("Excel", "*.xlsx")]})]
    assert list(tela.df_edicao_completo["DESCRIÇÃO"]) == ["A", "D"]
    assert list(tela.df_edicao_completo.index) == [0, 1]
    assert tela.entry_novo_projeto.text() == "PROJ-SUGERIDO"
    assert tela.selecoes[0][1] == tela.pos_selecao_edicao
    _esperar_log(qtbot, tela, "> Aba Edição: Carregado 2 itens válidos com PMIB.")


def test_edicao_sem_pmib_avisa(tela, pd, monkeypatch):
    df = pd.DataFrame({"DESCRIÇÃO": ["A"], "CÓDIGO PMIB": [""]})
    DataManagerFalso.respostas = {"Lista de Materiais": (df, None, None)}
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "/d/f.xlsx")
    tela.selecionar_excel_edicao()
    assert tela.avisos == [("warning", "Aviso", "Nenhum CÓDIGO PMIB encontrado nesta planilha. "
                                                "Certifique-se de que as fichas já foram criadas.")]
    assert tela.selecoes == []


def test_edicao_planilha_com_erro(tela, monkeypatch):
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "/d/f.xlsx")
    tela.selecionar_excel_edicao()
    assert tela.avisos == [("critical", "Erro", "Aba 0 não encontrada")]


def test_pos_selecao_edicao(tela, qtbot, pd):
    tela.df_edicao_completo = pd.DataFrame({"DESCRIÇÃO": ["A", "B", "C"], "CÓDIGO PMIB": ["1", "2", "3"]})
    tela.pos_selecao_edicao([0, 2])
    assert tela.lbl_status_edicao.text() == "2 fichas selecionadas"
    assert COLORS["accent"] in _folha(tela.lbl_status_edicao)
    assert f"background: {COLORS['primary']}" in _folha(tela.btn_excel_edicao)
    assert tela.btn_run_edicao.isEnabled()
    _esperar_log(qtbot, tela, "> Aba Edição: Selecionado 2 fichas para editar.")
    tela.pos_selecao_edicao([])
    assert not tela.btn_run_edicao.isEnabled()


def test_edicao_valida_antes_de_comecar(tela, pd):
    tela.btn_run_edicao.setEnabled(True)
    tela.run_edicao_thread()
    assert tela.avisos == [("warning", "Aviso", "Preencha o Novo Código do Projeto.")]
    tela.entry_novo_projeto.setText("  NOVO  ")
    tela.run_edicao_thread()
    assert tela.avisos[1] == ("warning", "Aviso", "Selecione ao menos uma ficha no Excel para editar.")


def test_robo_de_edicao(tela, robo, qtbot, pd, monkeypatch):
    avisos = []
    # O aviso chega ANTES de o navegador fechar: lá o showinfo segurava o worker
    # antes do `finally` (que fecha o navegador e devolve o botão).
    monkeypatch.setattr(tela, "avisar", lambda *a, **k: avisos.append((a, k, threading.current_thread()
                                                                        is threading.main_thread(),
                                                                        RoboFalso.instancias[0].saiu)))
    tela.df_edicao_completo = pd.DataFrame({"DESCRIÇÃO": ["A", "B", "C"],
                                            "CÓDIGO PMIB": [" 4500.1 ", "4500.2", "nan"]})
    tela.pos_selecao_edicao([0, 1, 2])
    tela.entry_novo_projeto.setText("  NOVO PROJ  ")
    RoboFalso.roteiro = {"4500.2": ("ERRO", "ficha travada")}
    tela.btn_run_edicao.click()
    assert not tela.btn_run_edicao.isEnabled()
    _esperar_log(qtbot, tela, "> Edição em massa concluída!")
    qtbot.waitUntil(tela.btn_run_edicao.isEnabled, timeout=2000)
    bot = RoboFalso.instancias[0]
    assert bot.itens == [("4500.1", "NOVO PROJ"), ("4500.2", "NOVO PROJ")]
    assert bot.portais == ["https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList"] and bot.saiu
    assert robo["pausas"] == [(MSG_LOGIN_PAGINA_PRINCIPAL, False)]
    texto = _texto(tela)
    assert "> Iniciando Edição em Massa de 2 fichas..." in texto
    assert "> Editando PMIB [1/2]: 4500.1..." in texto
    assert ">  -> ✅ SUCESSO: Projeto do 4500.1 atualizado." in texto
    assert ">  -> ❌ ERRO no 4500.2: ficha travada" in texto
    assert avisos == [(("Concluído", "Processo de edição em massa finalizado. Verifique o log."),
                       {"esperar": True}, False, False)]
    qtbot.waitUntil(lambda: tela.progress_edicao.fracao == 1.0, timeout=2000)


def test_robo_de_edicao_erro_fatal(tela, robo, qtbot, pd, monkeypatch):
    def quebra(self):
        raise RuntimeError("chrome não abriu")

    monkeypatch.setattr(RoboFalso, "iniciar_driver", quebra)
    tela.df_edicao_completo = pd.DataFrame({"DESCRIÇÃO": ["A"], "CÓDIGO PMIB": ["4500.1"]})
    tela.pos_selecao_edicao([0])
    tela.entry_novo_projeto.setText("NOVO")
    tela.run_edicao_thread()
    _esperar_log(qtbot, tela, "> Erro Fatal na Edição: chrome não abriu")
    qtbot.waitUntil(tela.btn_run_edicao.isEnabled, timeout=2000)
    assert RoboFalso.instancias[0].saiu


def _robos_vivos():
    return [t for t in threading.enumerate() if t.name.startswith("tarefa:ModuloCriaFichas")]


def test_um_robo_por_vez(tela, robo, qtbot, pd, monkeypatch):
    # Herdado da interface antiga (achado 6b): uma revisão confirmada no meio religava o
    # "4. Robô Web" (segundo robô), e o resumo do primeiro saía do lote NOVO.
    liberar = threading.Event()
    lote_a = list(tela.df_processed["descricao_original"])
    RoboFalso.roteiro = {d: [("SUCESSO", (f"PMIB-{i}", "PDM.1111.001 - VALVULA, R1"))]
                         for i, d in enumerate(lote_a)}
    monkeypatch.setattr(RoboFalso, "iniciar_driver", lambda self: liberar.wait(3))
    try:
        tela.btn_run_auto.click()
        assert not tela.btn_run_auto.isEnabled()

        lote_b = pd.DataFrame([{"descricao_original": "LOTE NOVO", "pdm_escolhido": "NENHUM"}])
        tela._pos_revisao_concluida(lote_b)           # revisão nova confirmada com o robô rodando
        assert tela.df_processed is lote_b
        assert not tela.btn_run_auto.isEnabled()      # o segundo robô não fica à mão
        tela.run_automation_thread()                  # nem à força
        tela.df_edicao_completo = pd.DataFrame({"DESCRIÇÃO": ["A"], "CÓDIGO PMIB": ["4500.1"]})
        tela.pos_selecao_edicao([0])
        tela.entry_novo_projeto.setText("NOVO")
        tela.btn_run_edicao.click()                   # nem o da aba de edição
        qtbot.waitUntil(lambda: _texto(tela).count(tela_mod.MSG_ROBO_OCUPADO) == 2, timeout=2000)
        assert len(RoboFalso.instancias) == 1

        liberar.set()
        qtbot.waitUntil(lambda: bool(tela.resumos), timeout=3000)
        # O resumo é do lote que ESTE robô levou ao portal.
        assert list(tela.df_resumo_final["descricao_original"]) == lote_a
        qtbot.waitUntil(tela.btn_run_auto.isEnabled, timeout=2000)
        assert not tela._robo_ativo
        assert tela.btn_run_edicao.isEnabled()        # o botão da edição nunca foi desligado
    finally:
        # Falhando no meio, nenhum robô pode sobrar esperando (o processo não sairia).
        liberar.set()
        qtbot.waitUntil(lambda: not _robos_vivos(), timeout=5000)


def test_revisao_confirmada_com_a_edicao_rodando_devolve_o_robo_web(tela, robo, qtbot, pd, monkeypatch):
    # Rodada 2 (re-revisão E4.9): confirmada a revisão com o robô de EDIÇÃO
    # rodando, o "4. Robô Web" não liga na hora (um robô por vez) -- e tem de
    # voltar no fim dele: o `iniciar_tarefa` da edição só devolve o botão dela.
    liberar = threading.Event()
    monkeypatch.setattr(RoboFalso, "iniciar_driver", lambda self: liberar.wait(5))
    tela.resetar_processo()                       # tela limpa: sem lote, "4. Robô Web" desligado
    try:
        tela.df_edicao_completo = pd.DataFrame({"DESCRIÇÃO": ["A"], "CÓDIGO PMIB": ["4500.1"]})
        tela.pos_selecao_edicao([0])
        tela.entry_novo_projeto.setText("NOVO")
        tela.btn_run_edicao.click()               # o robô de edição fica preso no navegador
        assert tela._robo_ativo

        _selecionar_pular_ia(tela, pd)            # a aba 1 está livre: IA + revisão
        tela.btn_run_ai.click()
        qtbot.waitUntil(lambda: bool(tela.revisoes), timeout=3000)
        tela.revisoes[0].confirmar()
        assert tela.df_processed is not None
        assert not tela.btn_run_auto.isEnabled()  # com a edição rodando, não liga

        liberar.set()
        qtbot.waitUntil(tela.btn_run_edicao.isEnabled, timeout=3000)
        qtbot.waitUntil(tela.btn_run_auto.isEnabled, timeout=2000)  # e volta no fim dela
        assert not tela._robo_ativo
    finally:
        liberar.set()
        qtbot.waitUntil(lambda: not _robos_vivos(), timeout=5000)


def test_fim_da_edicao_sem_lote_nao_liga_o_robo_web(tela, robo, qtbot, pd):
    # Sem lote confirmado (tela limpa), o fim do robô de edição não inventa um
    # "4. Robô Web" ligado apontando para nada.
    tela.resetar_processo()
    tela.df_edicao_completo = pd.DataFrame({"DESCRIÇÃO": ["A"], "CÓDIGO PMIB": ["4500.1"]})
    tela.pos_selecao_edicao([0])
    tela.entry_novo_projeto.setText("NOVO")
    tela.run_edicao_thread()
    _esperar_log(qtbot, tela, "> Edição em massa concluída!")
    qtbot.waitUntil(tela.btn_run_edicao.isEnabled, timeout=3000)
    qtbot.waitUntil(lambda: not tela._robo_ativo, timeout=2000)
    assert tela.df_processed is None and not tela.btn_run_auto.isEnabled()


def test_tarefas_em_thread_comum(tela, robo, qtbot):
    # Thread comum (não daemon): é tarefa da pessoa, o "X" pergunta antes de fechar.
    liberar = threading.Event()
    RoboFalso.roteiro = {}
    original = RoboFalso.iniciar_driver
    RoboFalso.iniciar_driver = lambda self: liberar.wait(3)
    try:
        antes = set(threading.enumerate())
        tela.run_automation_thread()
        novas = [t for t in threading.enumerate() if t not in antes]
        assert novas and not any(t.daemon for t in novas)
    finally:
        liberar.set()
        RoboFalso.iniciar_driver = original
    qtbot.waitUntil(tela.btn_run_auto.isEnabled, timeout=3000)


# --- medidas --------------------------------------------------------------------------------

def _medir(qt_interface, qtbot, altura=850):
    from sigft.app_qt import estilo

    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    t = tela_mod.ModuloCriaFichas(None, None)
    qtbot.addWidget(t)
    t.resize(1003, altura)
    t.show()
    qtbot.waitExposed(t)
    return t


def _r(t, w):
    p = w.mapTo(t, w.rect().topLeft())
    return (p.x(), p.y(), w.width(), w.height())


def test_medidas_iguais_as_do_interface_antiga(qt_interface, qtbot):
    # Medidas da tela antiga (janela 1280x850, winfo_*, x menos os 277 da barra
    # lateral): título (40, 30) h29; Tabview (40, 69) 923x471, aba (46, 112)
    # 911x422; área rolável recuada 6 (largura 888), barra em x=940;
    # cartão 1 (52, 128) 888x172: título (67, 138) h28, "Código do Projeto:"
    # 150 de largura, campo (217, 181) 698x28, botão 200x28 em (217, 219),
    # rótulo em x=427, caixa (67, 264) h24, botão de PDMs 20 depois dela;
    # cartão 2 (52, 320) 888x196: botões 374/359x40 em y=378 e 428, Limpar
    # 100x90 em (825, 378), barra 858x8 em (67, 493); console (40, 550) 923x270.
    anterior = qt_interface.styleSheet()
    try:
        t = _medir(qt_interface, qtbot)
        qtbot.waitUntil(lambda: t.abas.height() == 471, timeout=1000)
        assert _r(t, t.label_titulo)[:2] == (40, 30) and _r(t, t.label_titulo)[3] == 29
        assert _r(t, t.abas) == (40, 69, 923, 471)
        assert _r(t, t.abas.tab("Criação de Fichas")) == (46, 112, 911, 422)
        assert _r(t, t.area_criacao.verticalScrollBar())[0] == 940
        assert _r(t, t.cartao_config) == (52, 128, 888, 172)
        assert _r(t, t.rotulo_etapa1)[:2] == (67, 138) and _r(t, t.rotulo_etapa1)[3] == 28
        assert _r(t, t.rotulo_projeto) == (67, 181, 150, 28)
        assert _r(t, t.entry_projeto) == (217, 181, 698, 28)
        assert _r(t, t.rotulo_pmib) == (67, 219, 150, 28)
        assert _r(t, t.btn_pmib) == (217, 219, 200, 28)
        assert _r(t, t.lbl_status)[:2] == (427, 219) and _r(t, t.lbl_status)[3] == 28
        x, y, w, h = _r(t, t.chk_pular)
        assert (x, y, h) == (67, 264, 24)
        xb, yb, wb, hb = _r(t, t.btn_pdm)
        assert (xb, yb, hb) == (x + w + 20, 262, 28)
        assert abs(wb - 231) <= 6                                  # texto + 7 de cada lado
        assert _r(t, t.lbl_status_pdm)[0] == xb + wb + 20
        assert _r(t, t.cartao_acoes) == (52, 320, 888, 196)
        assert _r(t, t.rotulo_etapa2)[:2] == (67, 330)
        assert _r(t, t.btn_run_ai) == (67, 378, 374, 40)
        assert _r(t, t.btn_run_auto) == (451, 378, 359, 40)
        assert _r(t, t.btn_resumo) == (67, 428, 374, 40)
        assert _r(t, t.btn_save) == (451, 428, 359, 40)
        assert _r(t, t.btn_reset) == (825, 378, 100, 90)
        assert _r(t, t.progress) == (67, 493, 858, 8)
        assert t.progress.value() == 9                             # set(0): o ponto de 8 px
        assert _r(t, t.console) == (40, 550, 923, 270)
    finally:
        qt_interface.setStyleSheet(anterior)


def test_medidas_da_aba_de_edicao(qt_interface, qtbot):
    # interface antiga: cartões com padx=10 -> (62, 128) 868x134 e (62, 282) 868x146;
    # "Novo Código do Projeto:" 180 de largura, campo (257, 181) 648x28;
    # botão (257, 224) 200x28, rótulo em x=467; Iniciar (77, 340) 838x40;
    # barra (77, 405) 838x8.
    anterior = qt_interface.styleSheet()
    try:
        t = _medir(qt_interface, qtbot)
        t.abas.botoes["Editar código do projeto"].click()
        assert t.abas.get() == "Editar código do projeto"
        qtbot.waitUntil(lambda: t.cartao_config_edicao.width() == 868, timeout=1000)
        assert _r(t, t.cartao_config_edicao) == (62, 128, 868, 134)
        assert _r(t, t.rotulo_etapa1_edicao)[:2] == (77, 138)
        assert _r(t, t.rotulo_novo_projeto) == (77, 181, 180, 28)
        assert _r(t, t.entry_novo_projeto) == (257, 181, 648, 28)
        assert _r(t, t.rotulo_excel_edicao) == (77, 224, 180, 28)
        assert _r(t, t.btn_excel_edicao) == (257, 224, 200, 28)
        assert _r(t, t.lbl_status_edicao)[:2] == (467, 224)
        assert _r(t, t.cartao_acoes_edicao) == (62, 282, 868, 146)
        assert _r(t, t.rotulo_etapa2_edicao)[:2] == (77, 292)
        assert _r(t, t.btn_run_edicao) == (77, 340, 838, 40)
        assert _r(t, t.progress_edicao) == (77, 405, 838, 8)
        assert _r(t, t.area_edicao.verticalScrollBar())[0] == 940
    finally:
        qt_interface.setStyleSheet(anterior)


@pytest.mark.parametrize("altura_janela, abas, console", [
    (850, 471, 270), (700, 358, 233), (600, 283, 208), (1000, 583, 308), (640, 313, 218), (500, 209, 182),
])
def test_abas_e_console_dividem_a_altura_como_o_grid_do_tk(qt_interface, qtbot, altura_janela, abas, console):
    # grid do Tk: linha 1 (Tabview, weight=3, pede 261) e linha 2 (console,
    # weight=1, pede 200) repartem a SOBRA 3:1. Medido na interface antiga em seis alturas.
    anterior = qt_interface.styleSheet()
    try:
        t = _medir(qt_interface, qtbot, altura_janela)
        qtbot.waitUntil(lambda: (t.abas.height(), t.console.height()) == (abas, console), timeout=1000)
    finally:
        qt_interface.setStyleSheet(anterior)


# --- revisão final: o lote leva o robô e o Excel dele ------------------------------

def test_limpar_com_o_robo_rodando_deixa_o_robo_web_desligado(tela, robo, qtbot, monkeypatch):
    """Sem lote não há robô: o `iniciar_tarefa` religava o "4. Robô Web" no fim
    do robô mesmo depois do Limpar, e o clique seguinte dava `len(None)`."""
    liberar = threading.Event()
    monkeypatch.setattr(RoboFalso, "iniciar_driver", lambda self: liberar.wait(3))
    try:
        tela.btn_run_auto.click()
        assert not tela.btn_run_auto.isEnabled()
        tela.resetar_processo()
    finally:
        liberar.set()
    qtbot.waitUntil(lambda: not tela._robo_ativo, timeout=3000)
    qtbot.waitUntil(lambda: not _robos_vivos(), timeout=3000)
    QApplication.processEvents()
    assert tela.df_processed is None
    assert not tela.btn_run_auto.isEnabled()
    tela.run_automation_thread()                    # nem à força
    assert len(RoboFalso.instancias) == 1


def test_o_excel_do_lote_vem_do_clique_da_ia(tela, qtbot, pd):
    _selecionar_pular_ia(tela, pd)
    tela.file_path_excel = "/d/A.xlsx"
    tela.btn_run_ai.click()
    tela.file_path_excel = "/d/B.xlsx"              # outro Excel escolhido durante a IA
    qtbot.waitUntil(lambda: bool(tela.revisoes), timeout=3000)
    tela.revisoes[0].confirmar(pd.DataFrame({"descricao_original": ["A"]}))
    assert tela._excel_do_lote == "/d/A.xlsx"


def test_salvar_grava_no_excel_do_lote_e_nao_no_escolhido_depois(tela, robo, qtbot, pd, monkeypatch):
    """Escolher outro Excel com o robô rodando (para preparar o próximo lote)
    não pode mandar os PMIBs deste lote para a planilha nova."""
    tela._pos_revisao_concluida(tela.df_processed, excel="/d/A.xlsx")
    RoboFalso.roteiro = {d: [("SUCESSO", (f"PMIB-{i}", "PDM.1111.001 - VALVULA, R1"))]
                         for i, d in enumerate(tela.df_processed["descricao_original"])}
    liberar = threading.Event()
    monkeypatch.setattr(RoboFalso, "iniciar_driver", lambda self: liberar.wait(3))
    try:
        tela.btn_run_auto.click()
        tela.file_path_excel = "/d/B.xlsx"
        tela._pos_revisao_concluida(tela.df_processed.copy(), excel="/d/B.xlsx")  # próximo lote
    finally:
        liberar.set()
    qtbot.waitUntil(lambda: bool(tela.resumos), timeout=3000)
    qtbot.waitUntil(lambda: not _robos_vivos(), timeout=3000)
    DataManagerFalso.respostas_salvar = [(True, "ok")]
    tela.salvar_excel()
    assert [s[0] for s in DataManagerFalso.salvamentos] == ["/d/A.xlsx"]


def test_nome_longo_da_planilha_de_pdms_nao_alarga_a_tela(tela, qtbot, monkeypatch):
    tela.resize(1080, 800)
    tela.show()
    antes = tela.area_criacao.widget().minimumSizeHint().width()
    nome = ("PDMs_SAM-GM_planilha_mestra_revisao_2026_versao_final_corrigida_pelo_luan"
            "_e_rafael_v12.xlsx")
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "/x/" + nome)
    tela.selecionar_excel_pdm()
    QApplication.processEvents()
    assert tela.area_criacao.widget().minimumSizeHint().width() <= antes
    assert tela.lbl_status_pdm.text() == f"Selecionado: {nome}"
    assert tela.lbl_status_pdm.toolTip() == "/x/" + nome


# --- a regra da revisão mora no serviço (equivalente Qt de
# `test_tela_cria_fichas_duas_passadas.py`, lido por AST) ------------------------------

def _chamadas_na_tela():
    import ast
    import pathlib
    arvore = ast.parse(pathlib.Path(tela_mod.__file__).read_text(encoding="utf-8"))
    return {no.func.attr for no in ast.walk(arvore)
            if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)}


def test_a_tela_nao_confere_pdm_sozinha():
    assert "conferir_pdm" not in _chamadas_na_tela()
    assert "processar_lote" not in _chamadas_na_tela()


def test_a_tela_delega_as_duas_passadas_ao_servico():
    assert {"classificar_para_revisao", "gravar_calibracao"} <= _chamadas_na_tela()


# --- o mesmo lote de novo ao portal (decisão de 2026-10-19) -------------------------
# Pendência de 2026-10-11: o "4. Robô Web" volta ligado no fim do robô, com o
# MESMO lote, e um segundo clique criaria as mesmas fichas outra vez. Decisão
# (Jonathan, com a liberdade que o Luan deu): o botão continua ligado -- o robô
# pode ter caído antes de criar qualquer coisa, e desligá-lo obrigaria a refazer
# a análise da IA, que custa --, mas mandar o MESMO lote de novo PERGUNTA antes,
# com "Não" como padrão.

def _rodar_um_lote(tela, robo, qtbot):
    RoboFalso.roteiro = {d: [("PULAR", None)] for d in tela.df_processed["descricao_original"]}
    tela.run_automation_thread()
    qtbot.waitUntil(lambda: bool(tela.resumos), timeout=3000)
    qtbot.waitUntil(tela.btn_run_auto.isEnabled, timeout=2000)


def _responder(monkeypatch, resposta):
    perguntas = []

    def pergunta(parent, titulo, msg, botoes=None, padrao=None):
        perguntas.append((titulo, msg, padrao))
        return resposta

    monkeypatch.setattr(tela_mod.QMessageBox, "question", pergunta)
    return perguntas


def test_o_mesmo_lote_de_novo_pergunta_e_o_nao_nao_abre_o_robo(tela, robo, qtbot, monkeypatch):
    _rodar_um_lote(tela, robo, qtbot)
    perguntas = _responder(monkeypatch, tela_mod.QMessageBox.StandardButton.No)

    tela.run_automation_thread()

    assert len(perguntas) == 1 and "já foi enviado" in perguntas[0][1]
    assert perguntas[0][2] == tela_mod.QMessageBox.StandardButton.No      # o padrão é Não
    assert len(RoboFalso.instancias) == 1 and tela.btn_run_auto.isEnabled()
    _esperar_log(qtbot, tela, "não foi enviado de novo")


def test_o_mesmo_lote_de_novo_com_sim_roda_outra_vez(tela, robo, qtbot, monkeypatch):
    _rodar_um_lote(tela, robo, qtbot)
    _responder(monkeypatch, tela_mod.QMessageBox.StandardButton.Yes)
    tela.resumos.clear()

    _rodar_um_lote(tela, robo, qtbot)

    assert len(RoboFalso.instancias) == 2


def test_lote_novo_depois_de_outra_revisao_nao_pergunta(tela, robo, qtbot, monkeypatch, pd):
    _rodar_um_lote(tela, robo, qtbot)
    perguntas = _responder(monkeypatch, tela_mod.QMessageBox.StandardButton.No)
    tela._pos_revisao_concluida(tela.df_processed.copy())
    tela.resumos.clear()

    _rodar_um_lote(tela, robo, qtbot)

    assert perguntas == [] and len(RoboFalso.instancias) == 2
