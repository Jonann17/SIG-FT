"""Tela "AutoSpec AI" na interface Qt: comportamento com o serviço (AutoSpecCore),
a IA e a web falsos, a seção de conferência de documentos, e as medidas contra o
interface antiga.

A tela é da frente do Rafael: a lógica fica em `sigft/services/autospec.py` e
`autospec_conferencia.py` (intocados); aqui só se prova a fiação da tela. Os
invariantes que `tests/test_autospec_conferencia_tela.py` prova por AST na tela
interface antiga são provados aqui RODANDO a tela (ver os testes marcados "invariante").
"""
import threading
from types import SimpleNamespace

import pytest

from sigft.app import backends
from sigft.app_qt.views import autospec as tela_mod
from sigft.services import autospec_conferencia as conf_mod


# -- dublês -------------------------------------------------------------------------------
class CoreFalso:
    """O `AutoSpecCore` de mentira: registra o que a tela passou e devolve logs."""

    criados = []
    # O que o próximo core faz: conferência a deixar no fim do lote, exceção,
    # e um Event para segurar o lote no meio (testar o botão desligado).
    conferencia_do_lote = None
    erro_ao_criar = None
    erro_no_lote = None
    segurar = None

    def __init__(self, gemini_key, llama_key, google_search_key, google_cse_id):
        if CoreFalso.erro_ao_criar is not None:
            raise CoreFalso.erro_ao_criar
        self.chaves = (gemini_key, llama_key, google_search_key, google_cse_id)
        self.auditar_fornecedor = True
        self.conferencia = None
        self.filas = []
        self.conferidos = []
        CoreFalso.criados.append(self)

    def process_queue(self, queue, status_pmib_path):
        self.filas.append((list(queue), status_pmib_path))
        yield "--- lote AutoSpec ---"
        if CoreFalso.segurar is not None:
            CoreFalso.segurar.wait(5)
        for task in queue:
            yield f"ficha {task['sheet']} com {len(task['refs'])} manual(is)"
        if CoreFalso.erro_no_lote is not None:
            raise CoreFalso.erro_no_lote
        self.conferencia = CoreFalso.conferencia_do_lote

    def processar_conferidos(self, selecao, status_pmib_path):
        self.conferidos.append((selecao, status_pmib_path, self.conferencia))
        yield "--- segunda passada ---"
        if CoreFalso.segurar is not None:
            CoreFalso.segurar.wait(5)
        if CoreFalso.erro_no_lote is not None:
            raise CoreFalso.erro_no_lote


@pytest.fixture(autouse=True)
def _core_limpo():
    CoreFalso.criados = []
    CoreFalso.conferencia_do_lote = None
    CoreFalso.erro_ao_criar = None
    CoreFalso.erro_no_lote = None
    CoreFalso.segurar = None
    yield
    if CoreFalso.segurar is not None:
        CoreFalso.segurar.set()


def _backend(monkeypatch):
    modulo = SimpleNamespace(AutoSpecCore=CoreFalso)
    monkeypatch.setattr(backends, "autospec_backend", modulo)
    return modulo


@pytest.fixture
def tela(qt_interface, qtbot, monkeypatch):
    controlador = SimpleNamespace(get_key=lambda k: f"chave-{k}")
    t = tela_mod.ModuloAutoSpec(None, controlador)
    qtbot.addWidget(t)
    t.avisos = []
    monkeypatch.setattr(t, "avisar", lambda ti, m, tipo="info": t.avisos.append((tipo, ti, m)))
    t.caixas = []
    for nome in ("information", "warning", "critical"):
        monkeypatch.setattr(tela_mod.QMessageBox, nome,
                            staticmethod(lambda *a, _n=nome: t.caixas.append((_n, a[1], a[2]))))
    t.dialogos = []
    t.respostas = []

    def abrir_um(chave, categoria, **kw):
        t.dialogos.append((chave, categoria, kw))
        return t.respostas.pop(0) if t.respostas else ""

    def abrir_varios(chave, categoria, **kw):
        t.dialogos.append((chave, categoria, kw))
        return t.respostas.pop(0) if t.respostas else ()

    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", abrir_um)
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_files", abrir_varios)
    return t


def _conferencia(fichas=("/lote/FICHA_0084.xlsx", "/lote/FICHA_0086.xlsx")):
    c = conf_mod.Conferencia()
    c.registrar(fichas[0], "DISJUNTOR TRIPOLAR 400A",
                [{"url": "https://dist.com/3va.pdf", "title": "3VA Datasheet"},
                 {"url": "https://target.com/minnie", "title": "Minnie Mouse T-shirt"}])
    c.registrar(fichas[1], "RELE DIFERENCIAL", [{"url": "https://ex.org/rele.pdf", "title": ""}])
    return c


def _montar_fila(t, itens=(("/lote/a.xlsx", ("/m/1.pdf", "/m/2.pdf")), ("/lote/b.xlsx", ()))):
    for ficha, manuais in itens:
        t.respostas.append(ficha)
        t.sel_sheet()
        if manuais:
            t.respostas.append(tuple(manuais))
            t.sel_refs()
        t.add_queue()


def _escolher_status(t, caminho="/lote/_STATUS_PMIB.xlsx"):
    t.respostas.append(caminho)
    t.btn_status.click()


def _texto(t):
    return t.console.toPlainText()


def _console(qtbot, t, trecho):
    """O console escreve em lote (a cada 50 ms): espera o trecho e devolve o texto."""
    qtbot.waitUntil(lambda: trecho in _texto(t), timeout=2000)
    return _texto(t)


def _rodar(t, qtbot):
    t.btn_run.click()
    qtbot.waitUntil(lambda: "Processamento Completo!" in _texto(t) or "ERRO FATAL" in _texto(t),
                    timeout=3000)
    qtbot.waitUntil(t.btn_run.isEnabled, timeout=2000)


# -- montagem -----------------------------------------------------------------------------
def test_monta_com_os_textos(tela):
    assert tela.label_titulo.text() == "AutoSpec AI (RAG & Geração)"
    assert tela.rotulo_secao1.text() == "1. Arquivo de Referência"
    assert tela.rotulo_secao2.text() == "2. Adicionar Tarefa à Fila"
    assert tela.rotulo_fila.text() == "Fila de Processamento"
    assert tela.rotulo_conf_titulo.text() == "5. Conferência de documentos"
    assert tela.lbl_status.text() == "Nenhum _STATUS_PMIB selecionado"
    assert tela.lbl_sheet.text() == "Ficha: [Nenhuma]"
    assert tela.lbl_refs.text() == "Manuais: 0 arquivos"
    assert tela.btn_status.text() == "Selecionar _STATUS_PMIB"
    assert tela.btn_sheet.text() == "Selecionar Ficha (.xlsx)"
    assert tela.btn_refs.text() == "Adic. Manuais (.pdf)"
    assert tela.btn_add.text().replace("︎", "") == "⬇ Adicionar à Fila ⬇"
    assert tela.btn_run.text() == "INICIAR PROCESSAMENTO DA FILA"
    assert tela.btn_conf_salvar.text() == "SALVAR CONFERÊNCIA (.txt)"
    assert tela.btn_conf_importar.text() == "IMPORTAR CONFERÊNCIA (.txt)"
    assert tela.btn_conf.text() == "PROCESSAR OS DOCUMENTOS MARCADOS"
    assert tela.chk_fornecedor.text() == "Conferir as respostas do fornecedor contra o datasheet"
    assert "a ficha do fornecedor não é alterada" in tela.rotulo_fornecedor.text()
    assert "salve em .txt e importe depois" in tela.rotulo_conf_explicacao.text()
    assert tela.queue == [] and tela.temp_sheet is None and tela.temp_refs == []
    assert tela.status_pmib_path is None


def test_a_conferencia_do_fornecedor_nasce_marcada(tela):
    # Pedido do Luan (2026-09-28): marcada por padrão; desligar é a exceção.
    assert tela.chk_fornecedor.isChecked()
    assert tela._conferir_fornecedor is True
    tela.chk_fornecedor.click()
    assert tela._conferir_fornecedor is False


def test_fila_vazia_e_conferencia_vazia(tela):
    assert tela.rotulo_fila_vazia is not None and tela.rotulo_fila_vazia.text() == "Fila vazia."
    assert tela.conferencia is None and tela.marcados_conf == {}
    assert "Nenhuma conferência pendente." in tela.rotulo_conf_vazia.text()
    assert not tela.btn_conf.isEnabled() and not tela.btn_conf_salvar.isEnabled()
    # O IMPORTAR existe e funciona ANTES de qualquer lote: é quem reabriu o app.
    assert tela.btn_conf_importar.isEnabled()


# -- seletores ----------------------------------------------------------------------------
def test_seletores_usam_a_memoria_de_caminhos(tela):
    tela.respostas[:] = ["/lote/_STATUS_PMIB.xlsx", "/lote/FICHA_0084.xlsx", ("/m/a.pdf", "/m/b.txt")]
    tela.btn_status.click()
    tela.btn_sheet.click()
    tela.btn_refs.click()
    assert tela.dialogos == [
        ("autospec.status_pmib", "excel",
         {"titulo": "Selecione _STATUS_PMIB", "filetypes": [("Excel", "*.xlsx")]}),
        ("autospec.ficha", "excel",
         {"titulo": "Selecione a Ficha Técnica", "filetypes": [("Excel", "*.xlsx")]}),
        ("autospec.manuais", "pdf",
         {"titulo": "Selecione Manuais/PDFs", "filetypes": [("Docs", "*.pdf *.txt")]}),
    ]
    assert tela.status_pmib_path == "/lote/_STATUS_PMIB.xlsx"
    assert tela.lbl_status.text() == "_STATUS_PMIB.xlsx"
    assert tela.temp_sheet == "/lote/FICHA_0084.xlsx"
    assert tela.lbl_sheet.text() == "Ficha: FICHA_0084.xlsx"
    assert tela.temp_refs == ["/m/a.pdf", "/m/b.txt"]
    assert tela.lbl_refs.text() == "Manuais: 2 arquivos"
    for rotulo in (tela.lbl_status, tela.lbl_sheet, tela.lbl_refs):
        assert "#FFFFFF" in rotulo.styleSheet()


def test_cancelar_o_dialogo_nao_muda_nada(tela):
    tela.btn_status.click()
    tela.btn_sheet.click()
    tela.btn_refs.click()
    assert tela.status_pmib_path is None and tela.temp_sheet is None and tela.temp_refs == []
    assert tela.lbl_status.text() == "Nenhum _STATUS_PMIB selecionado"
    assert tela.lbl_sheet.text() == "Ficha: [Nenhuma]"
    assert "#808080" in tela.lbl_sheet.styleSheet()


def test_a_seta_do_adicionar_sai_da_fonte_de_simbolos(tela):
    # O Roboto não tem o "⬇", e o Noto Emoji o desenha como emoji (a seta dentro
    # de um quadrado). O Tk caía numa fonte de símbolos: só a seta. A mesma lista
    # de famílias do "▶" da Criação de Fichas, agora no `estilo`.
    from sigft.app_qt import estilo
    folha = tela.btn_add.styleSheet()
    assert estilo.FAMILIAS_COM_SIMBOLO in folha
    assert folha.index("Segoe UI Symbol") < folha.index("DejaVu Sans") < folha.index("Noto Emoji")


def test_enter_nao_dispara_nenhum_botao(tela, qtbot, monkeypatch):
    # Lá o Tk não ligava tecla nenhuma aos botões da tela: Enter num botão com
    # foco não começa lote, não adiciona, não salva nem processa.
    from PySide6.QtCore import Qt
    _backend(monkeypatch)
    _escolher_status(tela)
    _montar_fila(tela)
    tela._conferencia_mostrar(_conferencia(), {(0, 0): True})
    tela.show()
    botoes = (tela.btn_run, tela.btn_add, tela.btn_conf, tela.btn_conf_salvar, tela.btn_status)
    for botao in botoes:
        botao.setFocus()
        qtbot.keyClick(botao, Qt.Key.Key_Return)
        qtbot.keyClick(botao, Qt.Key.Key_Enter)
    assert CoreFalso.criados == [] and tela.caixas == [] and tela.avisos == []
    assert len(tela.dialogos) == 4                  # só os do preparo (_escolher_status + fila)
    assert all(not b.autoDefault() for b in botoes)


# -- fila ---------------------------------------------------------------------------------
def test_adicionar_sem_ficha_avisa(tela):
    tela.btn_add.click()
    assert tela.caixas == [("warning", "Aviso", "Selecione pelo menos a Ficha Técnica (.xlsx).")]
    assert tela.queue == []


def test_adicionar_a_fila_e_remover(tela):
    _montar_fila(tela)
    assert tela.queue == [{"sheet": "/lote/a.xlsx", "refs": ["/m/1.pdf", "/m/2.pdf"]},
                          {"sheet": "/lote/b.xlsx", "refs": []}]
    # Os temporários voltam ao começo depois de cada "Adicionar".
    assert tela.temp_sheet is None and tela.temp_refs == []
    assert tela.lbl_sheet.text() == "Ficha: [Nenhuma]" and "#808080" in tela.lbl_sheet.styleSheet()
    assert tela.lbl_refs.text() == "Manuais: 0 arquivos"
    assert tela.rotulo_fila_vazia is None
    assert [r.text() for r, _ in tela.linhas_fila] == ["#1: a.xlsx (+2 manuais)", "#2: b.xlsx (+0 manuais)"]
    tela.linhas_fila[0][1].click()                       # o "X" do #1
    assert tela.queue == [{"sheet": "/lote/b.xlsx", "refs": []}]
    assert [r.text() for r, _ in tela.linhas_fila] == ["#1: b.xlsx (+0 manuais)"]
    tela.linhas_fila[0][1].click()
    assert tela.queue == [] and tela.rotulo_fila_vazia.text() == "Fila vazia."


def test_nome_de_arquivo_com_simbolo_nao_e_alterado(tela):
    # `estilo.mono` só no emoji fixo da tela, nunca no dado da pessoa.
    _montar_fila(tela, ((r"/lote/Ficha → nova ⚙.xlsx", ()),))
    assert tela.linhas_fila[0][0].text() == "#1: Ficha → nova ⚙.xlsx (+0 manuais)"


# -- lote ---------------------------------------------------------------------------------
def test_iniciar_sem_status_avisa(tela, monkeypatch):
    _backend(monkeypatch)
    _montar_fila(tela)
    tela.btn_run.click()
    assert tela.caixas == [("critical", "Erro", "Selecione o arquivo _STATUS_PMIB.")]
    assert CoreFalso.criados == []


def test_iniciar_sem_fila_avisa(tela, monkeypatch):
    _backend(monkeypatch)
    _escolher_status(tela)
    tela.btn_run.click()
    assert tela.caixas == [("critical", "Erro", "Adicione itens à fila.")]


def test_backend_que_nao_carregou_nao_roda(tela, monkeypatch):
    monkeypatch.setattr(tela_mod.ModuleFrame, "backend",
                        lambda self, nome: tela.caixas.append(("indisponivel", nome, "")) and None)
    _escolher_status(tela)
    _montar_fila(tela)
    tela.btn_run.click()
    tela._conferencia_mostrar(_conferencia(), {(0, 0): True})
    tela.btn_conf.click()
    assert tela.caixas == [("indisponivel", "autospec_backend", ""),
                           ("indisponivel", "autospec_backend", "")]
    assert CoreFalso.criados == []
    assert tela.btn_run.isEnabled()


def test_lote_completo(tela, qtbot, monkeypatch):
    _backend(monkeypatch)
    _escolher_status(tela)
    _montar_fila(tela)
    fila = list(tela.queue)
    _rodar(tela, qtbot)
    qtbot.waitUntil(lambda: bool(tela.avisos), timeout=2000)
    texto = _texto(tela)
    assert "> --- lote AutoSpec ---" in texto
    assert "> ficha /lote/a.xlsx com 2 manual(is)" in texto
    assert "> Processamento Completo!" in texto
    assert tela.avisos == [("info", "Sucesso", "Todas as tarefas da fila foram processadas.")]
    core = CoreFalso.criados[0]
    assert core.chaves == ("chave-GEMINI", "chave-LLAMA", "chave-GOOGLE_SEARCH", "chave-GOOGLE_CSE")
    assert core.auditar_fornecedor is True
    assert core.filas == [(fila, "/lote/_STATUS_PMIB.xlsx")]
    assert tela.queue == [] and tela.rotulo_fila_vazia.text() == "Fila vazia."
    # Sem conferência no fim: a seção continua com o estado vazio, sem .txt.
    assert not tela.conferencia
    assert "Conferencia salva" not in texto


def test_desmarcar_a_conferencia_do_fornecedor_vale_para_o_lote(tela, qtbot, monkeypatch):
    _backend(monkeypatch)
    _escolher_status(tela)
    _montar_fila(tela)
    tela.chk_fornecedor.click()
    _rodar(tela, qtbot)
    assert CoreFalso.criados[0].auditar_fornecedor is False


def test_o_botao_fica_desligado_durante_o_lote(tela, qtbot, monkeypatch):
    _backend(monkeypatch)
    _escolher_status(tela)
    _montar_fila(tela)
    CoreFalso.segurar = threading.Event()
    tela.btn_run.click()
    assert not tela.btn_run.isEnabled()
    qtbot.waitUntil(lambda: "lote AutoSpec" in _texto(tela), timeout=2000)
    tela.btn_run.click()                                  # clique a mais: nada
    assert len(CoreFalso.criados) == 1 and not tela.btn_run.isEnabled()
    CoreFalso.segurar.set()
    qtbot.waitUntil(tela.btn_run.isEnabled, timeout=3000)


def test_o_lote_e_a_fila_do_clique(tela, qtbot, monkeypatch):
    # Lá o `process_queue` percorria a lista VIVA (`self.queue`, mexida pela
    # interface): o que se acrescentava DURANTE o laço entrava no mesmo lote, e
    # o que entrava depois dele (com o "Sucesso" aberto, por exemplo) era
    # apagado pelo `self.queue = []` sem ser processado. Aqui o lote é a cópia
    # do clique (a thread não lê estado da interface): o que entra durante o
    # lote fica na fila para o próximo, e só saem dela os itens processados.
    _backend(monkeypatch)
    _escolher_status(tela)
    _montar_fila(tela)
    CoreFalso.segurar = threading.Event()
    tela.btn_run.click()
    qtbot.waitUntil(lambda: "lote AutoSpec" in _texto(tela), timeout=2000)
    _montar_fila(tela, (("/lote/c.xlsx", ()),))
    CoreFalso.segurar.set()
    qtbot.waitUntil(lambda: "Processamento Completo!" in _texto(tela), timeout=3000)
    qtbot.waitUntil(tela.btn_run.isEnabled, timeout=2000)
    assert [item["sheet"] for item in CoreFalso.criados[0].filas[0][0]] == [
        "/lote/a.xlsx", "/lote/b.xlsx"]
    assert tela.queue == [{"sheet": "/lote/c.xlsx", "refs": []}]
    assert [r.text() for r, _ in tela.linhas_fila] == ["#1: c.xlsx (+0 manuais)"]


def test_o_x_durante_o_lote_nao_muda_o_lote(tela, qtbot, monkeypatch):
    # Lá o laço percorria a lista VIVA: tirar um item já processado puxava os de
    # trás uma casa, e o seguinte era pulado. Aqui o lote é a cópia do clique: o
    # "X" tira o item da fila na hora, mas o lote em andamento não muda.
    _backend(monkeypatch)
    _escolher_status(tela)
    _montar_fila(tela, (("/lote/a.xlsx", ()), ("/lote/b.xlsx", ()), ("/lote/c.xlsx", ())))
    CoreFalso.segurar = threading.Event()
    tela.btn_run.click()
    qtbot.waitUntil(lambda: "lote AutoSpec" in _texto(tela), timeout=2000)
    tela.linhas_fila[0][1].click()                       # o "X" do #1 com o lote andando
    assert [item["sheet"] for item in tela.queue] == ["/lote/b.xlsx", "/lote/c.xlsx"]
    CoreFalso.segurar.set()
    texto = _console(qtbot, tela, "Processamento Completo!")
    qtbot.waitUntil(tela.btn_run.isEnabled, timeout=2000)
    for nome in ("a", "b", "c"):
        assert f"> ficha /lote/{nome}.xlsx com 0 manual(is)" in texto
    assert tela.queue == []


def test_erro_no_fim_do_lote_vai_para_o_console_sem_sucesso(tela, qtbot, monkeypatch):
    # O fim do lote (lista nova, .txt automático) roda na thread da interface;
    # um erro ali sai no console como "ERRO FATAL", e o "Sucesso" não aparece.
    _backend(monkeypatch)
    _escolher_status(tela)
    _montar_fila(tela)

    def quebra(*_a, **_k):
        raise RuntimeError("lista quebrada")

    monkeypatch.setattr(tela, "_conferencia_mostrar", quebra)
    tela.btn_run.click()
    _console(qtbot, tela, "> ERRO FATAL: lista quebrada")
    qtbot.waitUntil(tela.btn_run.isEnabled, timeout=2000)
    assert tela.avisos == []


def test_erro_fatal_mantem_a_fila(tela, qtbot, monkeypatch):
    _backend(monkeypatch)
    _escolher_status(tela)
    _montar_fila(tela)
    CoreFalso.erro_ao_criar = ValueError("Chave do provedor ausente")
    _rodar(tela, qtbot)
    assert "> ERRO FATAL: Chave do provedor ausente" in _texto(tela)
    assert tela.avisos == []
    assert len(tela.queue) == 2


def test_erro_no_meio_do_lote(tela, qtbot, monkeypatch):
    _backend(monkeypatch)
    _escolher_status(tela)
    _montar_fila(tela)
    CoreFalso.erro_no_lote = RuntimeError("planilha corrompida")
    _rodar(tela, qtbot)
    assert "> ERRO FATAL: planilha corrompida" in _texto(tela)
    assert "Processamento Completo!" not in _texto(tela)
    assert len(tela.queue) == 2


def test_lote_com_conferencia_mostra_a_lista_e_salva_sozinho(tela, qtbot, monkeypatch, tmp_path):
    _backend(monkeypatch)
    status = tmp_path / "_STATUS_PMIB.xlsx"
    status.write_text("x")
    _escolher_status(tela, str(status))
    _montar_fila(tela)
    CoreFalso.conferencia_do_lote = _conferencia()
    _rodar(tela, qtbot)
    qtbot.waitUntil(lambda: "Conferencia salva em:" in _texto(tela), timeout=2000)
    assert tela.conferencia is CoreFalso.conferencia_do_lote
    assert len(tela.cabecalhos_conf) == 2 and len(tela.marcados_conf) == 3
    assert tela.btn_conf.isEnabled() and tela.btn_conf_salvar.isEnabled()
    salvos = list(tmp_path.glob("CONFERENCIA_AUTOSPEC_*.txt"))
    assert len(salvos) == 1
    # O automático não abre caixa: roda no fim do lote, sem ninguém para dar OK.
    assert tela.caixas == []
    assert tela.avisos == [("info", "Sucesso", "Todas as tarefas da fila foram processadas.")]


def test_invariante_o_automatico_salva_a_lista_NOVA(tela, qtbot, monkeypatch, tmp_path):
    # `_conferencia_mostrar` zera as marcações; salvar antes dele gravaria as
    # marcas do lote ANTERIOR (arquivo plausível e errado).
    _backend(monkeypatch)
    status = tmp_path / "_STATUS_PMIB.xlsx"
    status.write_text("x")
    _escolher_status(tela, str(status))
    tela._conferencia_mostrar(_conferencia(), {(0, 0): True, (0, 1): True, (1, 0): True})
    _montar_fila(tela)
    CoreFalso.conferencia_do_lote = _conferencia()
    _rodar(tela, qtbot)
    qtbot.waitUntil(lambda: "Conferencia salva em:" in _texto(tela), timeout=2000)
    (salvo,) = tmp_path.glob("CONFERENCIA_AUTOSPEC_*.txt")
    conferencia, marcados = conf_mod.carregar_txt(str(salvo))
    assert conferencia.total_documentos == 3
    assert not any(marcados.values())


def test_o_automatico_vai_para_a_pasta_do_status_do_clique(tela, qtbot, monkeypatch, tmp_path):
    """Revisão final: outro `_STATUS_PMIB` escolhido no meio do lote não leva o
    `.txt` automático deste lote para a outra pasta."""
    import threading

    _backend(monkeypatch)
    pasta_a, pasta_b = tmp_path / "a", tmp_path / "b"
    pasta_a.mkdir()
    pasta_b.mkdir()
    (pasta_a / "_STATUS_PMIB.xlsx").write_text("x")
    (pasta_b / "_STATUS_PMIB.xlsx").write_text("x")
    _escolher_status(tela, str(pasta_a / "_STATUS_PMIB.xlsx"))
    _montar_fila(tela)
    CoreFalso.conferencia_do_lote = _conferencia()
    segurar = threading.Event()
    monkeypatch.setattr(CoreFalso, "segurar", segurar)
    tela.btn_run.click()
    try:
        qtbot.waitUntil(lambda: "--- lote AutoSpec ---" in _texto(tela), timeout=2000)
        tela.status_pmib_path = str(pasta_b / "_STATUS_PMIB.xlsx")   # trocado no meio
    finally:
        segurar.set()
    qtbot.waitUntil(lambda: "Conferencia salva em:" in _texto(tela), timeout=3000)
    assert len(list(pasta_a.glob("CONFERENCIA_AUTOSPEC_*.txt"))) == 1
    assert list(pasta_b.glob("CONFERENCIA_AUTOSPEC_*.txt")) == []


# -- conferência: lista -------------------------------------------------------------------
def test_mostrar_a_conferencia_com_as_marcacoes(tela):
    tela._conferencia_mostrar(_conferencia(), {(0, 1): True})
    cab = [r.text() for r in tela.cabecalhos_conf]
    assert cab[0].endswith(" FICHA_0084.xlsx  —  DISJUNTOR TRIPOLAR 400A")
    assert cab[0].replace("︎", "").startswith("📄 ")
    links = {k: b.text().replace("︎", "") for k, b in tela.links_conf.items()}
    assert links == {(0, 0): "🔗 3VA Datasheet", (0, 1): "🔗 Minnie Mouse T-shirt",
                     (1, 0): "🔗 https://ex.org/rele.pdf"}       # sem título: a URL
    assert {k: c.isChecked() for k, c in tela.marcados_conf.items()} == {
        (0, 0): False, (0, 1): True, (1, 0): False}
    assert tela.rotulo_conf_vazia is None
    assert tela.btn_conf.isEnabled() and tela.btn_conf_salvar.isEnabled()


def test_material_e_titulo_cortados_e_sem_mono_no_dado(tela):
    c = conf_mod.Conferencia()
    material = "M" * 59 + "→" + "Z" * 10
    titulo = "T" * 68 + "⚙" + "W" * 10
    c.registrar("/lote/x.xlsx", material, [{"url": "https://a.b/c", "title": titulo}])
    tela._conferencia_mostrar(c)
    assert tela.cabecalhos_conf[0].text().endswith("  —  " + material[:60])
    assert tela.links_conf[(0, 0)].text().endswith(" " + titulo[:70])


def test_o_link_abre_no_navegador(tela, monkeypatch):
    abertos = []
    monkeypatch.setattr(tela_mod.webbrowser, "open", lambda u: abertos.append(u))
    tela._conferencia_mostrar(_conferencia())
    tela.links_conf[(0, 1)].click()
    assert abertos == ["https://target.com/minnie"]


def test_mostrar_de_novo_troca_a_lista(tela):
    tela._conferencia_mostrar(_conferencia(), {(0, 0): True})
    tela._conferencia_mostrar(None)
    assert tela.conferencia is None and tela.marcados_conf == {} and tela.cabecalhos_conf == []
    assert "Nenhuma conferência pendente." in tela.rotulo_conf_vazia.text()
    assert not tela.btn_conf.isEnabled() and not tela.btn_conf_salvar.isEnabled()


def test_invariante_a_secao_nunca_se_esconde(tela):
    tela.show()
    for conferencia in (None, _conferencia(), None):
        tela._conferencia_mostrar(conferencia)
        assert tela.frm_conf.isVisibleTo(tela) and tela.btn_conf_importar.isVisibleTo(tela)


def test_titulo_com_e_comercial_aparece_inteiro_e_sem_atalho(tela):
    # "&" no texto de um QPushButton é o mnemônico do Qt: some do que se vê e o
    # botão ganha um atalho Alt (com este título, Alt+Espaço -- o menu da janela
    # no Windows). O título é o que a pessoa lê para julgar o documento.
    from PySide6.QtCore import Qt
    from sigft.app_qt import estilo
    titulo = "Products & Solutions | R&S"
    c = conf_mod.Conferencia()
    c.registrar("/lote/x.xlsx", "MATERIAL", [{"url": "https://r-s.com/a", "title": titulo}])
    tela._conferencia_mostrar(c)
    link = tela.links_conf[(0, 0)]
    assert link.shortcut().isEmpty()
    # O texto como o Qt o desenha (mnemônicos processados) é o título inteiro.
    fm = link.fontMetrics()
    assert (fm.size(Qt.TextFlag.TextShowMnemonic, link.text())
            == fm.size(0, estilo.mono("🔗") + " " + titulo))


def test_rotulos_com_dado_da_pessoa_sao_texto_puro(tela):
    # Um QLabel no formato automático lê "<b>...</b>" como HTML: o material
    # "CABO <b>X</b>" apareceria com o X em negrito e sem as marcas.
    from PySide6.QtCore import Qt
    c = conf_mod.Conferencia()
    c.registrar("/lote/x.xlsx", "CABO <b>X</b> 3x2,5", [{"url": "https://a.b/c", "title": "t"}])
    tela._conferencia_mostrar(c)
    assert tela.cabecalhos_conf[0].textFormat() == Qt.TextFormat.PlainText
    assert tela.cabecalhos_conf[0].text().endswith("  —  CABO <b>X</b> 3x2,5")
    _montar_fila(tela, (("/lote/a.xlsx", ()),))
    for rotulo in (tela.linhas_fila[0][0], tela.lbl_sheet, tela.lbl_refs, tela.lbl_status):
        assert rotulo.textFormat() == Qt.TextFormat.PlainText


def test_importar_durante_a_2a_passada_nao_religa_o_processar(tela, qtbot, monkeypatch, tmp_path):
    # Lá o `_conferencia_mostrar` religava o PROCESSAR sem olhar se havia uma 2ª
    # passada rodando: importar (ou o fim de um lote) no meio dela deixava clicar
    # de novo, e duas passadas regravavam os mesmos `_completed`.
    _backend(monkeypatch)
    _escolher_status(tela)
    tela._conferencia_mostrar(_conferencia(), {(0, 0): True})
    CoreFalso.segurar = threading.Event()
    tela.btn_conf.click()
    qtbot.waitUntil(lambda: "segunda passada" in _texto(tela), timeout=2000)
    arquivo = conf_mod.salvar_txt(_conferencia(), None, {(0, 1): True}, pasta=str(tmp_path))
    tela.respostas.append(arquivo)
    tela.btn_conf_importar.click()
    assert tela.conferencia is not None and len(tela.marcados_conf) == 3
    assert not tela.btn_conf.isEnabled()
    tela.btn_conf.click()
    assert len(CoreFalso.criados) == 1
    CoreFalso.segurar.set()
    qtbot.waitUntil(tela.btn_conf.isEnabled, timeout=3000)      # a lista importada pode seguir
    assert len(CoreFalso.criados) == 1


def test_fim_da_2a_passada_sem_lista_deixa_o_processar_desligado(tela, qtbot, monkeypatch):
    # O fim de um lote sem conferência esvazia a lista no meio da 2ª passada: ao
    # terminar, ela não religa um PROCESSAR que não tem o que processar.
    _backend(monkeypatch)
    _escolher_status(tela)
    tela._conferencia_mostrar(_conferencia(), {(0, 0): True})
    CoreFalso.segurar = threading.Event()
    tela.btn_conf.click()
    qtbot.waitUntil(lambda: "segunda passada" in _texto(tela), timeout=2000)
    tela._conferencia_mostrar(None)
    CoreFalso.segurar.set()
    qtbot.waitUntil(lambda: bool(tela.avisos), timeout=3000)
    qtbot.waitUntil(lambda: not tela._conf_em_andamento, timeout=2000)
    assert not tela.btn_conf.isEnabled()


# -- conferência: salvar / importar --------------------------------------------------------
def test_salvar_sem_conferencia_avisa(tela):
    assert tela._conferencia_salvar() is None
    assert tela.caixas == [("information", "Conferência", "Não há conferência para salvar.")]


def test_salvar_grava_com_as_marcacoes(tela, qtbot, tmp_path):
    status = tmp_path / "_STATUS_PMIB.xlsx"
    status.write_text("x")
    tela.status_pmib_path = str(status)
    tela._conferencia_mostrar(_conferencia(), {(0, 1): True})
    tela.marcados_conf[(1, 0)].click()
    tela.btn_conf_salvar.click()
    (salvo,) = tmp_path.glob("CONFERENCIA_AUTOSPEC_*.txt")
    assert tela.caixas == [("information", "Conferência", f"Conferência salva em:\n{salvo}")]
    assert f"> Conferencia salva em: {salvo}" in _console(qtbot, tela, "Conferencia salva")
    _, marcados = conf_mod.carregar_txt(str(salvo))
    assert marcados == {(0, 0): False, (0, 1): True, (1, 0): True}


def test_salvar_com_erro(tela, qtbot, monkeypatch):
    def falha(*a, **k):
        raise OSError("disco cheio")

    monkeypatch.setattr(tela_mod.conferencia_txt, "salvar_txt", falha)
    tela._conferencia_mostrar(_conferencia())
    tela.btn_conf_salvar.click()
    assert tela.caixas == [("critical", "Conferência", "Não consegui salvar:\ndisco cheio")]
    assert "> Nao consegui salvar o .txt da conferencia: disco cheio" in _console(
        qtbot, tela, "Nao consegui")


def test_salvar_automatico_com_erro_nao_abre_caixa(tela, qtbot, monkeypatch):
    def falha(*a, **k):
        raise OSError("disco cheio")

    monkeypatch.setattr(tela_mod.conferencia_txt, "salvar_txt", falha)
    tela._conferencia_mostrar(_conferencia())
    assert tela._conferencia_salvar(automatico=True) is None
    assert tela.caixas == []
    assert "> Nao consegui salvar o .txt da conferencia: disco cheio" in _console(
        qtbot, tela, "Nao consegui")


def test_importar_retoma_com_as_marcacoes(tela, qtbot, tmp_path):
    fichas = [tmp_path / "FICHA_0084.xlsx", tmp_path / "FICHA_0086.xlsx"]
    for f in fichas:
        f.write_text("x")
    original = _conferencia(tuple(str(f) for f in fichas))
    arquivo = conf_mod.salvar_txt(original, None, {(0, 1): True}, pasta=str(tmp_path))
    tela.respostas.append(arquivo)
    tela.btn_conf_importar.click()
    assert tela.dialogos == [("autospec.conferencia", "txt",
                              {"titulo": "Selecione o .txt da conferência",
                               "filetypes": [("Texto", "*.txt"), ("Todos", "*.*")]})]
    assert tela.conferencia.total_documentos == 3
    assert {k: c.isChecked() for k, c in tela.marcados_conf.items()} == {
        (0, 0): False, (0, 1): True, (1, 0): False}
    texto = _console(qtbot, tela, "ficha(s).")
    assert f"> Conferencia importada de: {arquivo}" in texto
    assert ">  -> 3 documento(s) em 2 ficha(s)." in texto
    assert "AVISO" not in texto and tela.caixas == []


def test_importar_com_fichas_ausentes_avisa(tela, qtbot, tmp_path):
    arquivo = conf_mod.salvar_txt(_conferencia(), None, {}, pasta=str(tmp_path))
    tela.respostas.append(arquivo)
    tela.btn_conf_importar.click()
    texto = _console(qtbot, tela, "FICHA_0086.xlsx")
    assert ">  -> AVISO: nao encontrei a ficha /lote/FICHA_0084.xlsx" in texto
    assert ">  -> AVISO: nao encontrei a ficha /lote/FICHA_0086.xlsx" in texto
    assert tela.caixas == [("warning", "Conferência",
                            "2 ficha(s) não estão mais no caminho gravado no arquivo.\n"
                            "Elas vão falhar no processamento — veja o console.")]


def test_importar_arquivo_sem_documentos(tela, tmp_path):
    vazio = tmp_path / "vazio.txt"
    vazio.write_text("# nada aqui\n", encoding="utf-8")
    tela.respostas.append(str(vazio))
    tela.btn_conf_importar.click()
    assert tela.caixas == [("warning", "Conferência",
                            "Não encontrei nenhum documento neste arquivo.\n\n"
                            "Ele precisa ter as linhas 'FICHA:' e os links marcados com [ ] ou [x].")]
    assert tela.conferencia is None


def test_importar_arquivo_ilegivel(tela, tmp_path):
    tela.respostas.append(str(tmp_path / "nao_existe.txt"))
    tela.btn_conf_importar.click()
    (caixa,) = tela.caixas
    assert caixa[:2] == ("critical", "Conferência")
    assert caixa[2].startswith("Não consegui ler o arquivo:\n")


def test_importar_cancelado_nao_faz_nada(tela):
    tela.btn_conf_importar.click()
    assert tela.caixas == [] and tela.conferencia is None


# -- conferência: processar ---------------------------------------------------------------
def test_processar_exige_o_status(tela, monkeypatch):
    _backend(monkeypatch)
    tela._conferencia_mostrar(_conferencia(), {(0, 0): True})
    tela.btn_conf.click()
    assert tela.caixas == [("critical", "Erro", "Selecione o arquivo _STATUS_PMIB (seção 1) antes de "
                                                "processar a conferência.")]
    assert CoreFalso.criados == []


def test_processar_sem_nada_marcado(tela, monkeypatch):
    _backend(monkeypatch)
    _escolher_status(tela)
    tela._conferencia_mostrar(_conferencia())
    tela.btn_conf.click()
    assert tela.caixas == [("information", "Conferência",
                            "Marque ao menos um documento antes de processar.")]
    assert CoreFalso.criados == []


def test_processar_os_documentos_marcados(tela, qtbot, monkeypatch):
    _backend(monkeypatch)
    _escolher_status(tela)
    conferencia = _conferencia()
    tela._conferencia_mostrar(conferencia, {(0, 1): True})
    tela.marcados_conf[(1, 0)].click()
    tela.chk_fornecedor.click()
    tela.btn_conf.click()
    assert not tela.btn_conf.isEnabled()
    qtbot.waitUntil(lambda: "Conferência processada!" in _texto(tela), timeout=3000)
    qtbot.waitUntil(tela.btn_conf.isEnabled, timeout=2000)
    core = CoreFalso.criados[0]
    assert core.conferidos == [({"/lote/FICHA_0084.xlsx": ["https://target.com/minnie"],
                                 "/lote/FICHA_0086.xlsx": ["https://ex.org/rele.pdf"]},
                                "/lote/_STATUS_PMIB.xlsx", conferencia)]
    assert core.auditar_fornecedor is False
    texto = _texto(tela)
    assert "> --- segunda passada ---" in texto
    assert ("> Os documentos nao marcados continuam na lista. Se for parar agora, use "
            "SALVAR CONFERENCIA (.txt).") in texto
    assert tela.avisos == [("info", "Sucesso", "Documentos conferidos processados.")]
    # A lista FICA: o que não foi marcado continua duvidoso.
    assert tela.conferencia is conferencia and len(tela.marcados_conf) == 3


def test_processar_com_erro(tela, qtbot, monkeypatch):
    _backend(monkeypatch)
    _escolher_status(tela)
    tela._conferencia_mostrar(_conferencia(), {(0, 0): True})
    CoreFalso.erro_no_lote = RuntimeError("sem rede")
    tela.btn_conf.click()
    qtbot.waitUntil(lambda: "ERRO na conferência" in _texto(tela), timeout=3000)
    qtbot.waitUntil(tela.btn_conf.isEnabled, timeout=2000)
    assert "> ERRO na conferência: sem rede" in _texto(tela)
    assert tela.avisos == []


# -- caixa de 18 px (CTkCheckBox com checkbox_width/height=18) ------------------------------
def test_caixa_de_marcar_de_18(qt_interface, qtbot):
    from sigft.app_qt.widgets import controles
    caixa = controles.CaixaDeMarcar("", lado=18)
    qtbot.addWidget(caixa)
    assert caixa.sizeHint().width() == 18 + controles.VAO_TEXTO_CAIXA
    assert caixa.sizeHint().height() == 18
    padrao = controles.CaixaDeMarcar("")
    qtbot.addWidget(padrao)
    assert padrao.sizeHint().height() == controles.LADO_CAIXA


# -- medidas ------------------------------------------------------------------------------
@pytest.fixture
def tela_medida(qt_interface, qtbot):
    from sigft.app_qt import estilo

    anterior = qt_interface.styleSheet()
    estilo.carregar_fontes()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    t = tela_mod.ModuloAutoSpec(None, None)
    qtbot.addWidget(t)
    t.resize(1003, 850)
    t.show()
    qtbot.waitExposed(t)
    yield t
    qt_interface.setStyleSheet(anterior)


def _r(t, w):
    p = w.mapTo(t, w.rect().topLeft())
    return (p.x(), p.y(), w.width(), w.height())


def test_medidas_iguais_as_do_interface_antiga(tela_medida):
    # Tela antiga 1280x850 (winfo_*), x relativo à área da tela (a barra lateral
    # tem 277 px). Header (40, 30); quadro rolável em (40, 79) 923x601 com o
    # conteúdo recuado 6 (900 de largura); console de 120 em y=700.
    t = tela_medida
    assert _r(t, t.label_titulo)[:2] == (40, 30)
    assert _r(t, t.area) == (40, 79, 923, 601)
    assert _r(t, t.console) == (40, 700, 923, 120)
    # 1. Arquivo de Referência
    assert _r(t, t.cartao_status) == (46, 95, 900, 91)
    assert _r(t, t.rotulo_secao1)[:2] == (61, 105) and _r(t, t.rotulo_secao1)[3] == 28
    assert _r(t, t.lbl_status)[:2] == (61, 143) and _r(t, t.lbl_status)[3] == 28
    x, y, w, h = _r(t, t.btn_status)
    assert (y, h, x + w) == (143, 28, 931) and abs(w - 157) <= 6
    # 2. Adicionar Tarefa à Fila (borda de 1 px que não empurra o conteúdo)
    assert _r(t, t.cartao_job) == (46, 206, 900, 182)
    assert _r(t, t.rotulo_secao2)[:2] == (61, 216)
    assert _r(t, t.lbl_sheet)[:2] == (61, 259) and _r(t, t.btn_sheet) == (751, 259, 180, 28)
    assert _r(t, t.lbl_refs)[:2] == (61, 297) and _r(t, t.btn_refs) == (751, 297, 180, 28)
    assert _r(t, t.btn_add) == (66, 345, 860, 28)
    # Fila de Processamento: quadro rolável interno de 870x212 (a barra mede 200)
    assert _r(t, t.cartao_fila) == (46, 408, 900, 275)
    assert _r(t, t.rotulo_fila)[:2] == (61, 418)
    assert _r(t, t.queue_frame) == (61, 456, 870, 212)
    x, y, w, h = _r(t, t.rotulo_fila_vazia)
    assert (y, h) == (472, 28) and abs((x + w / 2) - 490.5) <= 1
    # Conferência do fornecedor e INICIAR
    assert _r(t, t.chk_fornecedor)[:2] == (76, 708) and _r(t, t.chk_fornecedor)[3] == 24
    assert _r(t, t.rotulo_fornecedor)[:2] == (104, 734) and _r(t, t.rotulo_fornecedor)[3] == 42
    assert _r(t, t.btn_run) == (76, 796, 840, 50)
    # 5. Conferência de documentos
    assert _r(t, t.frm_conf) == (46, 876, 900, 407)
    assert _r(t, t.rotulo_conf_titulo)[:2] == (61, 886)
    assert _r(t, t.rotulo_conf_explicacao)[:2] == (61, 916) and _r(t, t.rotulo_conf_explicacao)[3] == 42
    assert _r(t, t.lista_conf) == (61, 966, 870, 212)
    assert _r(t, t.rotulo_conf_vazia)[:2] == (77, 982) and _r(t, t.rotulo_conf_vazia)[3] == 42
    # SALVAR/IMPORTAR: pack(side="left", expand) -- a SOBRA é repartida igual,
    # não a largura (lá 418 e 432 para pedidos de 171 e 185).
    xs, ys, ws, hs = _r(t, t.btn_conf_salvar)
    xi, yi, wi, hi = _r(t, t.btn_conf_importar)
    assert (xs, ys, hs, yi, hi) == (66, 1188, 32, 1188, 32)
    assert xi == xs + ws + 10 and xi + wi == 926
    pedido_s = t.btn_conf_salvar.sizeHint().width()
    pedido_i = t.btn_conf_importar.sizeHint().width()
    assert abs((ws - pedido_s) - (wi - pedido_i)) <= 1
    assert _r(t, t.btn_conf) == (66, 1228, 860, 40)
    # Rolagem: o conteúdo tem 1208 de altura, como lá (619 para rolar).
    assert t.area.verticalScrollBar().maximum() == 1208 - 589


def test_o_que_rola_some_6_px_antes_da_borda_como_no_ctk(tela_medida):
    # O canvas do CTkScrollableFrame fica 6 px para dentro do quadro: o que rola
    # é cortado ali (lá o 1º cartão, rolado, não aparece entre y=79 e 85). A
    # barra continua com a altura toda.
    t = tela_medida
    for area, altura in ((t.area, 601), (t.queue_frame, 212), (t.lista_conf, 212)):
        vista = area.viewport()
        assert (vista.y(), vista.height()) == (6, altura - 12)
        barra = area.verticalScrollBar()
        assert (barra.mapTo(area, barra.rect().topLeft()).y(), barra.height()) == (0, altura)


def test_salvar_e_importar_nao_encolhem_abaixo_do_pedido(tela_medida):
    # Como o `pack` do Tk: cada botão tem ao menos o que pede (texto + folga),
    # e a linha não deixa o layout espremê-la abaixo disso.
    linha = tela_medida._linha_botoes_conf
    pedido = (tela_medida.btn_conf_salvar.sizeHint().width() + linha.VAO
              + tela_medida.btn_conf_importar.sizeHint().width())
    assert linha.minimumSizeHint().width() == pedido
    linha.resize(pedido, linha.height())
    linha.arrumar()
    assert tela_medida.btn_conf_salvar.width() == tela_medida.btn_conf_salvar.sizeHint().width()
    assert tela_medida.btn_conf_importar.width() == tela_medida.btn_conf_importar.sizeHint().width()


def test_medidas_das_linhas_da_fila_e_da_conferencia(tela_medida, qtbot):
    # interface antiga: linha da fila 2 abaixo do topo do quadro interno (462 + 2), rótulo com
    # padx 5, "X" 30x25 a 5 da barra; conferência: cabeçalho a (6, 8) do quadro
    # interno (h28), linhas de 24 com a caixa de 25 e o link de 22 (810).
    t = tela_medida
    t.queue = [{"sheet": "/lote/FICHA_0084.xlsx", "refs": ["a", "b"]},
               {"sheet": "/lote/FICHA_0086.xlsx", "refs": []}]
    t.update_queue_ui()
    (r1, x1), (r2, _x2) = t.linhas_fila
    # O layout novo se arruma no laço de eventos: espera a 1ª linha chegar lá.
    qtbot.waitUntil(lambda: _r(t, r1)[:2] == (72, 464), timeout=2000)
    assert _r(t, r1)[:2] == (72, 464) and _r(t, r1)[3] == 28
    assert _r(t, x1) == (879, 465, 30, 25)
    assert _r(t, r2)[1] == 496
    t._conferencia_mostrar(_conferencia())
    base_y = 972
    c1, c2 = t.cabecalhos_conf
    qtbot.waitUntil(lambda: _r(t, c1)[1] == base_y + 8, timeout=2000)
    assert _r(t, c1) == (73, base_y + 8, 835, 28)
    assert _r(t, t.marcados_conf[(0, 0)]) == (73, base_y + 39, 25, 24)
    assert _r(t, t.links_conf[(0, 0)]) == (98, base_y + 40, 810, 22)
    assert _r(t, t.marcados_conf[(0, 1)])[1] == base_y + 65
    assert _r(t, c2)[1] == base_y + 98
    assert _r(t, t.marcados_conf[(1, 0)])[1] == base_y + 129
