"""Tela "Analyzer" (IA) na interface Qt: comportamento com backend/IA falsos,
slider, seletores, janela de pesos e medidas contra a interface antiga."""
from types import SimpleNamespace

import pytest

from sigft.app import backends
from sigft.app_qt.views import analyzer as tela_mod


class AnalisadorFalso:
    """O `DatasheetAnalyzer` de mentira: cada ficha devolve o que `resultados` manda."""

    criados = []

    def __init__(self, api_key, resultados=None, perguntar=None):
        self.api_key = api_key
        self.resultados = resultados or {}
        self.perguntar = perguntar or {}
        self.relatorio = None
        self.chamadas = []
        AnalisadorFalso.criados.append(self)

    def processar_planilha(self, **kw):
        self.chamadas.append(kw)
        nome = kw["original_filename"]
        yield f"--- Iniciando Arquivo: {nome} ---"
        if nome in self.perguntar:
            desc = kw["callback_manual_desc"](nome, self.perguntar[nome])
            yield f"desc={desc}"
        r = self.resultados.get(nome, True)
        if isinstance(r, Exception):
            raise r
        if r == "pendencia":
            self.relatorio.registrar(nome)
            return True
        return r


class RelatorioFalso:
    def __init__(self):
        self.itens = []
        self.salvou = []
        self.caminho = "/saida/pendencias.xlsx"

    def registrar(self, nome):
        self.itens.append(nome)

    def __bool__(self):
        return bool(self.itens)

    def __len__(self):
        return len(self.itens)

    def salvar_xlsx(self, destino, retry_lock=None):
        self.salvou.append((destino, retry_lock))
        return self.caminho if self.itens else None


CONFIG_MAP = {"texto_breve_material": {"weight": 1}, "tipo_fabricacao": {"weight": 2}}


def _backend(monkeypatch, resultados=None, perguntar=None):
    AnalisadorFalso.criados = []
    modulo = SimpleNamespace(
        DatasheetAnalyzer=lambda chave: AnalisadorFalso(chave, resultados, perguntar),
        CONFIG_MAP=CONFIG_MAP,
        aba_do_status_pmib=lambda wb: ("aba", wb),
    )
    monkeypatch.setattr(backends, "analyzer_backend", modulo)
    monkeypatch.setattr(tela_mod.analyzer_relatorio, "RelatorioAnalise", RelatorioFalso)
    return modulo


@pytest.fixture
def tela(qt_interface, qtbot, monkeypatch):
    controlador = SimpleNamespace(get_key=lambda k: f"chave-{k}")
    t = tela_mod.ModuloAnalyzer(None, controlador)
    qtbot.addWidget(t)
    t.avisos = []
    monkeypatch.setattr(t, "avisar", lambda ti, m, tipo="info": t.avisos.append((tipo, ti, m)))
    t.textos = []
    t.respostas_texto = []

    def pedir(ti, m):
        t.textos.append((ti, m))
        return t.respostas_texto.pop(0) if t.respostas_texto else None

    monkeypatch.setattr(t, "pedir_texto", pedir)
    t.caixas = []
    for nome in ("information", "warning", "critical"):
        monkeypatch.setattr(tela_mod.QMessageBox, nome,
                            staticmethod(lambda *a, _n=nome: t.caixas.append((_n, a[1], a[2]))))
    return t


def _escolher(t, arquivos=("/d/sub/a.xlsx", "/d/sub/b.xlsx"), saida="/saida"):
    t.picker_files.definir(tuple(arquivos), f"{len(arquivos)} arquivos selecionados")
    t._ao_escolher_fichas(arquivos)
    t.picker_out.definir(saida, "saida")
    t._ao_escolher_saida(saida)


def _rodar(t, qtbot):
    t.btn_run.click()
    qtbot.waitUntil(lambda: "Concluído!" in t.console.toPlainText()
                    or "Erro Fatal" in t.console.toPlainText(), timeout=3000)
    qtbot.waitUntil(t.btn_run.isEnabled, timeout=2000)


# -- montagem ---------------------------------------------------------------------------
def test_monta_com_os_textos(tela):
    assert tela.label_titulo.text() == "Technical Datasheet Analyzer"
    assert tela.lbl_subtitulo.text() == "Validação e Pontuação de Fichas Técnicas via IA"
    assert tela.lbl_score.text() == "Nota Mínima: 90%"
    assert tela.slider.value() == 90 and (tela.slider.minimum(), tela.slider.maximum()) == (0, 100)
    # Revisão final: a engrenagem vai em preto e branco, como nas outras telas.
    assert tela.btn_config.text() == tela_mod.estilo.mono("⚙️ Configurar Pesos")
    assert "\ufe0f" not in tela.btn_config.text()
    assert tela.btn_run.text() == "INICIAR PROCESSAMENTO"
    assert tela.btn_relatorio.text() == "GERAR RELATÓRIO PARA O FORNECEDOR (.xlsx)"
    assert not tela.btn_relatorio.isEnabled()
    assert tela.relatorio_analise is None
    assert tela.picker_pmib.label_status.text() == "Não selecionado (Padrão: sem contexto)"
    assert tela.picker_files.botao.text() == "Selecionar Fichas (.xlsx)"
    assert tela.picker_out.botao.text() == "Pasta de Saída"
    assert tela.picker_pmib.botao.text() == "STATUS_PMIB (Opcional)"
    assert tela.custom_weights == {} and tela.max_var_points == 45.0
    assert tela.api_key == "chave-GEMINI"


def test_slider_atualiza_rotulo_e_nota(tela):
    tela.slider.setValue(73)
    assert tela.lbl_score.text() == "Nota Mínima: 73%"
    assert tela.score_value == 73


def test_pickers_usam_a_memoria_de_caminhos(tela, monkeypatch):
    chamadas = []
    monkeypatch.setattr(tela_mod.app_pickers.file_dialogs, "ask_open_files",
                        lambda chave, cat, **k: chamadas.append(chave) or ("/x/a.xlsx",))
    monkeypatch.setattr(tela_mod.app_pickers.file_dialogs, "ask_directory",
                        lambda chave, cat, **k: chamadas.append(chave) or "/x/saida")
    monkeypatch.setattr(tela_mod.app_pickers.file_dialogs, "ask_open_file",
                        lambda chave, cat, **k: chamadas.append(chave) or "/x/STATUS.xlsx")
    tela.picker_files.botao.click()
    tela.picker_out.botao.click()
    tela.picker_pmib.botao.click()
    assert chamadas == ["analyzer.fichas", "analyzer.saida", "analyzer.status_pmib"]
    assert tela.selected_files == ["/x/a.xlsx"]
    assert tela.selected_output == "/x/saida"
    assert tela.selected_pmib == "/x/STATUS.xlsx"


# -- validação --------------------------------------------------------------------------
def test_sem_fichas_avisa(tela, monkeypatch):
    _backend(monkeypatch)
    tela.btn_run.click()
    assert tela.caixas == [("warning", "Faltam Dados", "Selecione as Fichas.")]


def test_sem_pasta_avisa(tela, monkeypatch):
    _backend(monkeypatch)
    tela._ao_escolher_fichas(["/a.xlsx"])
    tela.btn_run.click()
    assert tela.caixas == [("warning", "Faltam Dados", "Selecione a Pasta de Saída.")]


def test_backend_que_nao_carregou_nao_roda(tela, monkeypatch):
    monkeypatch.setattr(backends, "analyzer_backend", None)
    monkeypatch.setattr(backends, "falhas", {"analyzer_backend": ImportError("sem openpyxl")})
    monkeypatch.setattr(tela_mod.ModuleFrame, "backend",
                        lambda self, nome: tela.caixas.append(("indisponivel", nome, "")) and None)
    _escolher(tela)
    tela.btn_run.click()
    tela.btn_config.click()
    assert [c[0] for c in tela.caixas] == ["indisponivel", "indisponivel"]
    assert "Iniciando" not in tela.console.toPlainText()


# -- lote -------------------------------------------------------------------------------
def test_lote_completo(tela, qtbot, monkeypatch):
    _backend(monkeypatch)
    _escolher(tela)
    tela.slider.setValue(80)
    _rodar(tela, qtbot)
    qtbot.waitUntil(lambda: bool(tela.avisos), timeout=2000)
    texto = tela.console.toPlainText()
    assert "> Iniciando análise de 2 arquivos..." in texto
    assert ">>> Usando PESOS PADRÃO." in texto
    assert "--- Iniciando Arquivo: a.xlsx ---" in texto
    assert "Concluído! 2 de 2 ficha(s) processada(s)." in texto
    assert tela.avisos == [("info", "Sucesso", "Análise finalizada.")]
    analisador = AnalisadorFalso.criados[0]
    assert analisador.api_key == "chave-GEMINI"
    kw = analisador.chamadas[0]
    assert kw["input_filepath"] == "/d/sub/a.xlsx" and kw["root_output_dir"] == "/saida"
    assert kw["subfolder_name"] == "sub" and kw["original_filename"] == "a.xlsx"
    assert kw["pmib_sheet"] is None and kw["score_threshold"] == 80
    assert kw["custom_weights"] == {} and kw["max_variable_points"] == 45.0
    assert kw["retry_lock"] == tela.perguntar_retry_excel
    assert kw["callback_manual_desc"] == tela._perguntar_descricao
    assert not tela.btn_relatorio.isEnabled()


def test_botao_desliga_durante_o_lote(tela, qtbot, monkeypatch):
    import threading
    solta = threading.Event()
    _backend(monkeypatch)

    def lento(**kw):
        yield "lendo"
        solta.wait(3)
        return True

    monkeypatch.setattr(AnalisadorFalso, "processar_planilha", lambda self, **kw: lento(**kw))
    _escolher(tela, arquivos=("/d/a.xlsx",))
    tela.btn_run.click()
    assert not tela.btn_run.isEnabled()
    solta.set()
    qtbot.waitUntil(tela.btn_run.isEnabled, timeout=3000)


def test_valores_lidos_no_clique_valem_para_o_lote_inteiro(tela, qtbot, monkeypatch):
    """Revisão final: seletores, régua e pesos seguem ligados durante o lote;
    mexer neles no meio não muda as fichas que faltam."""
    import threading
    solta = threading.Event()
    _backend(monkeypatch)

    def lento(**kw):
        yield "lendo"
        if kw["original_filename"] == "a.xlsx":
            solta.wait(3)
        return True

    monkeypatch.setattr(AnalisadorFalso, "processar_planilha",
                        lambda self, **kw: (self.chamadas.append(kw), lento(**kw))[1])
    tela.custom_weights = {"tipo_fabricacao": 5.0}
    tela.max_var_points = 30.0
    _escolher(tela, arquivos=("/d/sub/a.xlsx", "/d/sub/b.xlsx"))
    tela.slider.setValue(80)
    tela.btn_run.click()
    qtbot.waitUntil(lambda: "lendo" in tela.console.toPlainText(), timeout=3000)
    # No meio do lote: outra régua, outra pasta, outros pesos, outra lista.
    tela.slider.setValue(10)
    tela._ao_escolher_saida("/outra")
    tela.custom_weights.update({"tipo_fabricacao": 1.0})
    tela.max_var_points = 99.0
    tela._ao_escolher_fichas(("/d/x.xlsx", "/d/y.xlsx", "/d/z.xlsx"))
    solta.set()
    qtbot.waitUntil(lambda: "Concluído!" in tela.console.toPlainText(), timeout=3000)
    qtbot.waitUntil(tela.btn_run.isEnabled, timeout=2000)

    chamadas = AnalisadorFalso.criados[0].chamadas
    assert [kw["original_filename"] for kw in chamadas] == ["a.xlsx", "b.xlsx"]
    segunda = chamadas[1]
    assert segunda["root_output_dir"] == "/saida" and segunda["score_threshold"] == 80
    assert segunda["custom_weights"] == {"tipo_fabricacao": 5.0}
    assert segunda["max_variable_points"] == 30.0
    assert "Concluído! 2 de 2 ficha(s) processada(s)." in tela.console.toPlainText()


def test_falhas_e_excecao_nao_derrubam_o_lote(tela, qtbot, monkeypatch):
    _backend(monkeypatch, resultados={"a.xlsx": False, "b.xlsx": RuntimeError("quebrou")})
    _escolher(tela, arquivos=("/d/a.xlsx", "/d/b.xlsx", "/d/c.xlsx"))
    _rodar(tela, qtbot)
    qtbot.waitUntil(lambda: bool(tela.avisos), timeout=2000)
    texto = tela.console.toPlainText()
    assert "[ERRO] b.xlsx: quebrou" in texto
    assert "Concluído! 1 de 3 ficha(s) processada(s)." in texto
    assert "NAO concluidas (2): a.xlsx, b.xlsx" in texto
    assert tela.avisos == [("aviso", "Análise finalizada com pendências",
                            "2 de 3 ficha(s) não foram processadas.\n"
                            "Veja o console para o motivo de cada uma.")]


def test_pesos_personalizados_vao_ao_backend(tela, qtbot, monkeypatch):
    _backend(monkeypatch)
    tela.custom_weights = {"tipo_fabricacao": 5.0}
    tela.max_var_points = 30.0
    _escolher(tela, arquivos=("/d/a.xlsx",))
    _rodar(tela, qtbot)
    assert ">>> Usando PESOS PERSONALIZADOS nesta análise." in tela.console.toPlainText()
    kw = AnalisadorFalso.criados[0].chamadas[0]
    assert kw["custom_weights"] == {"tipo_fabricacao": 5.0} and kw["max_variable_points"] == 30.0


def test_status_pmib_carregado(tela, qtbot, monkeypatch):
    _backend(monkeypatch)
    monkeypatch.setattr(tela_mod.openpyxl, "load_workbook", lambda c, data_only: f"wb:{c}:{data_only}",
                        raising=False)
    _escolher(tela, arquivos=("/d/a.xlsx",))
    tela._ao_escolher_pmib("/d/STATUS.xlsx")
    _rodar(tela, qtbot)
    assert "STATUS_PMIB carregada." in tela.console.toPlainText()
    assert AnalisadorFalso.criados[0].chamadas[0]["pmib_sheet"] == ("aba", "wb:/d/STATUS.xlsx:True")


def test_erro_no_status_pmib_so_loga(tela, qtbot, monkeypatch):
    _backend(monkeypatch)

    def falha(*a, **k):
        raise OSError("travado")

    monkeypatch.setattr(tela_mod.openpyxl, "load_workbook", falha, raising=False)
    _escolher(tela, arquivos=("/d/a.xlsx",))
    tela._ao_escolher_pmib("/d/STATUS.xlsx")
    _rodar(tela, qtbot)
    assert "Erro STATUS_PMIB: travado" in tela.console.toPlainText()
    assert "Concluído! 1 de 1" in tela.console.toPlainText()


def test_erro_fatal_loga_e_devolve_o_botao(tela, qtbot, monkeypatch):
    modulo = _backend(monkeypatch)

    def explode(chave):
        raise ValueError("sem chave")

    modulo.DatasheetAnalyzer = explode
    _escolher(tela)
    _rodar(tela, qtbot)
    assert "Erro Fatal: sem chave" in tela.console.toPlainText()
    assert tela.btn_run.isEnabled()


# -- descrição manual (chamada pelo backend, de dentro do worker) -------------------------
def test_pergunta_descricao_e_cancelar_para_de_perguntar(tela, qtbot, monkeypatch):
    _backend(monkeypatch, perguntar={"a.xlsx": "123", "b.xlsx": "456", "c.xlsx": "789"})
    tela.respostas_texto = ["  Bomba centrífuga  ", None]
    _escolher(tela, arquivos=("/d/a.xlsx", "/d/b.xlsx", "/d/c.xlsx"))
    _rodar(tela, qtbot)
    texto = tela.console.toPlainText()
    assert len(tela.textos) == 2  # a terceira não pergunta: Cancelar parou
    titulo, msg = tela.textos[0]
    assert titulo == "Descrição do material"
    assert msg == ("A ficha a.xlsx tem o código PMIB 123, que não está no _STATUS_PMIB.\n\n"
                   "Se você souber a descrição do material, digite abaixo. Ela entra no "
                   "contexto que vai para a IA.\n\n"
                   "CANCELAR segue sem descrição e não pergunta mais nesta rodada.")
    assert "Descricao informada a mao: Bomba centrífuga" in texto
    assert "desc=Bomba centrífuga" in texto
    assert "Sem descricao manual; nao vou perguntar de novo nesta rodada." in texto
    assert texto.count("desc=None") == 2


def test_ok_vazio_segue_perguntando(tela, qtbot, monkeypatch):
    _backend(monkeypatch, perguntar={"a.xlsx": "1", "b.xlsx": "2"})
    tela.respostas_texto = ["   ", "x"]
    _escolher(tela)
    _rodar(tela, qtbot)
    assert len(tela.textos) == 2
    assert "desc=x" in tela.console.toPlainText()


def test_nova_rodada_volta_a_perguntar(tela, qtbot, monkeypatch):
    _backend(monkeypatch, perguntar={"a.xlsx": "1"})
    _escolher(tela, arquivos=("/d/a.xlsx",))
    _rodar(tela, qtbot)
    tela.console._descarregar()
    _rodar(tela, qtbot)
    assert len(tela.textos) == 2


# -- relatório para o fornecedor ---------------------------------------------------------
def test_relatorio_liga_o_botao_e_grava(tela, qtbot, monkeypatch):
    _backend(monkeypatch, resultados={"a.xlsx": "pendencia"})
    _escolher(tela)
    _rodar(tela, qtbot)
    qtbot.waitUntil(tela.btn_relatorio.isEnabled, timeout=2000)
    assert ("1 ficha(s) com pendencia. Use GERAR RELATORIO PARA O FORNECEDOR (.xlsx)."
            in tela.console.toPlainText())
    tela.btn_relatorio.click()
    rel = tela.relatorio_analise
    assert rel.salvou == [("/saida", tela.perguntar_retry_excel)]
    assert tela.caixas[-1] == ("information", "Relatório",
                               "1 ficha(s) com pendência.\n\nArquivo:\n/saida/pendencias.xlsx")


def test_relatorio_sem_analise(tela):
    tela._gerar_relatorio()
    assert tela.caixas == [("information", "Relatório",
                            "Rode uma análise primeiro. Ainda não há pendências para relatar.")]


def test_relatorio_sem_pendencia(tela):
    rel = RelatorioFalso()
    rel.itens = ["x"]
    rel.caminho = None
    tela.relatorio_analise = rel
    tela._gerar_relatorio()
    assert tela.caixas == [("information", "Relatório",
                            "Nenhuma ficha ficou com pendência. Não há o que relatar.")]


def test_relatorio_que_falha_vira_erro(tela):
    rel = RelatorioFalso()
    rel.itens = ["x"]

    def falha(destino, retry_lock=None):
        raise PermissionError("negado")

    rel.salvar_xlsx = falha
    tela.relatorio_analise = rel
    tela._gerar_relatorio()
    assert tela.caixas == [("critical", "Relatório", "Não consegui gerar o arquivo:\nnegado")]


# -- janela de pesos ---------------------------------------------------------------------
def test_janela_de_pesos(tela, qtbot, monkeypatch):
    _backend(monkeypatch)
    tela.custom_weights = {"tipo_fabricacao": 7.0}
    tela.btn_config.click()
    win = tela.janela_pesos
    qtbot.addWidget(win)
    assert win.windowTitle() == "Configuração de Pesos"
    assert (win.width(), win.height()) == (500, 700)
    assert not win.isModal()
    assert list(tela.entries_pesos) == ["texto_breve_material", "tipo_fabricacao"]
    assert [e.text() for e in tela.entries_pesos.values()] == ["1", "7.0"]
    assert [r.text() for r in win.rotulos] == ["Texto Breve Material", "Tipo Fabricacao"]
    assert tela.entry_max_vars.text() == "45.0"
    tela.entries_pesos["texto_breve_material"].setText("2.5")
    tela.entry_max_vars.setText("40")
    win.btn_salvar.click()
    assert tela.custom_weights == {"texto_breve_material": 2.5, "tipo_fabricacao": 7.0}
    assert tela.max_var_points == 40.0
    assert tela.caixas == [("information", "Sucesso", "Pesos atualizados para esta sessão.")]
    assert not win.isVisible()


def test_janela_de_pesos_com_texto_invalido(tela, qtbot, monkeypatch):
    _backend(monkeypatch)
    tela.btn_config.click()
    win = tela.janela_pesos
    qtbot.addWidget(win)
    tela.entries_pesos["tipo_fabricacao"].setText("dois")
    win.btn_salvar.click()
    assert tela.caixas == [("critical", "Erro",
                            "Certifique-se de usar apenas números (ponto para decimais).")]
    assert win.isVisible()


# -- medidas -----------------------------------------------------------------------------
def test_medidas_iguais_as_do_interface_antiga(qt_interface, qtbot):
    # 2026-10-20: medida do sistema visual (botão/campo 32, título 22, borda 1); a CTk saiu em 2026-10-15.
    # Medidas da tela antiga (1280x850, winfo_*), com x relativo à área da tela (a
    # barra lateral tem 277 px), como no Tradutor: título (40, 30); área rolável
    # em y=79 com o conteúdo recuado 6 (y=85, largura 900); subtítulo h28;
    # cartão 1 em y=143 (h81: título +10, controles +48, slider 300x16 a +124);
    # cartão 2 20 abaixo (h167, seletores em 292/330/368); INICIAR 300x50 40
    # abaixo do cartão 2, centrado; relatório 300x36 8 abaixo; console 150 em 670.
    from sigft.app_qt import estilo

    anterior = qt_interface.styleSheet()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    try:
        t = tela_mod.ModuloAnalyzer(None, None)
        qtbot.addWidget(t)
        t.resize(1003, 850)
        t.show()
        qtbot.waitExposed(t)

        def r(w):
            p = w.mapTo(t, w.rect().topLeft())
            return (p.x(), p.y(), w.width(), w.height())

        assert r(t.label_titulo)[:2] == (40, 30)
        assert r(t.area)[:2] == (40, 77) and r(t.area)[2] == 923
        assert r(t.lbl_subtitulo)[1] == 83 and r(t.lbl_subtitulo)[3] == 28
        assert r(t.cartao_criterios) == (46, 141, 900, 81)
        assert r(t.cartao_arquivos) == (46, 242, 900, 179)
        assert r(t.lbl_score)[:2] == (61, 189) and r(t.lbl_score)[3] == 28
        assert r(t.slider) == (61 + r(t.lbl_score)[2] + 20, 195, 300, 16)
        assert r(t.btn_config) == (781, 189, 150, 28)
        assert r(t.picker_files.botao) == (61, 290, 200, 32)
        assert r(t.picker_out.botao)[1] == 332 and r(t.picker_pmib.botao)[1] == 374
        assert r(t.picker_files.label_status)[0] == 276
        assert r(t.btn_run) == (346, 461, 300, 50)
        assert r(t.btn_relatorio) == (346, 519, 300, 36)
        assert r(t.console) == (40, 670, 923, 150)
    finally:
        qt_interface.setStyleSheet(anterior)


def test_medidas_da_janela_de_pesos(qt_interface, qtbot, monkeypatch):
    # 2026-10-20: medida do sistema visual (botão/campo 32, título 22, borda 1); a CTk saiu em 2026-10-15.
    # interface antiga: quadro rolável em (10,10) 480x632, conteúdo recuado 6 (largura 457);
    # título h28 a +10; linhas de 28 a cada 32 (rótulo 250, campo 80 encostado à
    # direita); "Salvar Pesos" 140x28 em (180, 662).
    from sigft.app_qt import estilo

    _backend(monkeypatch)
    anterior = qt_interface.styleSheet()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    try:
        t = tela_mod.ModuloAnalyzer(None, None)
        qtbot.addWidget(t)
        t.abrir_config_pesos()
        win = t.janela_pesos
        qtbot.addWidget(win)
        qtbot.waitExposed(win)

        def r(w):
            p = w.mapTo(win, w.rect().topLeft())
            return (p.x(), p.y(), w.width(), w.height())

        assert r(win.area) == (10, 10, 480, 632)
        assert r(win.titulo)[1] == 26
        assert r(win.rotulos[0])[:2] == (16, 66) and r(win.rotulos[0])[2] == 250
        assert r(win.rotulos[1])[1] == 102
        campo = t.entries_pesos["texto_breve_material"]
        assert r(campo) == (393, 66, 80, 32)
        assert r(win.btn_salvar) == (180, 662, 140, 28)
        # "Pontos Totais": 121 abaixo da última linha (866 -> 987 na interface antiga);
        # 125 desde 2026-10-20 (campo e botão de 32 no sistema visual).
        assert r(t.entry_max_vars)[1] == r(win.rotulos[-1])[1] + 125
    finally:
        qt_interface.setStyleSheet(anterior)


def test_esc_e_enter_nao_fecham_nem_salvam_a_janela_de_pesos(tela, qtbot, monkeypatch):
    # No Tk, nem Esc nem Enter faziam nada: o que foi digitado só sai pelo "Salvar".
    from PySide6.QtCore import Qt
    _backend(monkeypatch)
    tela.btn_config.click()
    win = tela.janela_pesos
    qtbot.addWidget(win)
    campo = tela.entries_pesos["texto_breve_material"]
    campo.setText("9")
    qtbot.keyClick(campo, Qt.Key.Key_Return)
    qtbot.keyClick(win, Qt.Key.Key_Escape)
    assert win.isVisible()
    assert campo.text() == "9"
    assert tela.caixas == []
    assert "texto_breve_material" not in tela.custom_weights


def test_segundo_clique_traz_a_mesma_janela_de_pesos(tela, qtbot, monkeypatch):
    _backend(monkeypatch)
    tela.btn_config.click()
    primeira = tela.janela_pesos
    qtbot.addWidget(primeira)
    tela.btn_config.click()
    assert tela.janela_pesos is primeira
