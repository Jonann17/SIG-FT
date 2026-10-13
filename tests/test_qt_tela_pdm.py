"""Tela "Gerenciador de PDMs" (PDM) na interface Qt.

Backends, serviços e IA são dublês: o que se prova é a TELA -- textos, as três
abas, as validações na ordem da tela antiga, os argumentos que chegam aos
serviços, as mensagens do fim (pela thread da interface), a janela de seleção
dos códigos e a geometria contra o CustomTkinter.
"""
import sys
import threading
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt, QTimer

from sigft.app import backends, theme
from sigft.app_qt.views import pdm as tela_mod

ABAS = ["Processar PDMs", "Criar planilhas PMIB", "Excluir Duplicados"]


# ---------------------------------------------------------------------------
# Dublês e ajudas
# ---------------------------------------------------------------------------
class PdmFalso:
    """O `pdm_backend` de mentira: registra cada chamada."""

    def __init__(self, *, codigos=None, erro_codigos=None, dados_pastas=("d1",), arquivos=("/i/a.xlsx",)):
        self.chamadas = []
        self.codigos, self.erro_codigos = codigos or ["PMIB-1", "PMIB-2", "PMIB-3"], erro_codigos
        self.dados_pastas, self.arquivos = list(dados_pastas), list(arquivos)
        self.threads = []

    def _reg(self, nome, *a, **k):
        self.chamadas.append((nome, a, k))
        self.threads.append(threading.current_thread() is threading.main_thread())

    def pdms_fromItaipu_lista_geral(self, lista, pasta, log_callback=None, retry_lock=None):
        self._reg("from_itaipu", lista, pasta, retry_lock=retry_lock)
        log_callback("fatiando...")
        return "12 PDMs criados"

    def listar_arquivos_excel(self, origem):
        self._reg("listar", origem)
        return list(self.arquivos)

    def processar_arquivo_pdm(self, arq):
        self._reg("processar", arq)
        return None if arq.endswith("ruim.xlsx") else f"tbl:{arq}"

    def salvar_tabela_formatada(self, tbl, arq, destino, force=False, retry_lock=None):
        self._reg("salvar", tbl, arq, destino, force=force, retry_lock=retry_lock)
        return True, f"salvo {arq}"

    def codigos_pmib_da_lista(self, status):
        self._reg("codigos", status)
        if self.erro_codigos:
            raise self.erro_codigos
        return list(self.codigos)

    def processar_pastas_fichas(self, status, destino, lista_sel, criar_subpastas=True):
        self._reg("pastas", status, destino, lista_sel, criar_subpastas=criar_subpastas)
        return list(self.dados_pastas), "3 pastas preparadas"

    def aplicar_templates_fichas(self, dados, pasta, template, log_callback=None, retry_lock=None, idioma="pt"):
        self._reg("templates_pasta", dados, pasta, template, retry_lock=retry_lock, idioma=idioma)
        return "3 fichas montadas", []

    def aplicar_templates_fichas_da_planilha(self, dados, catalogo, template, log_callback=None, retry_lock=None):
        self._reg("templates_planilha", dados, catalogo, template, retry_lock=retry_lock)
        return "3 fichas da planilha", []

    def logica_excluir_duplicados(self, pasta, log_callback=None):
        self._reg("limpeza", pasta)
        log_callback("removido x_v1.xlsx")
        return "1 duplicado removido"


@pytest.fixture
def pdm(monkeypatch):
    falso = PdmFalso()
    monkeypatch.setattr(backends, "pdm_backend", falso)
    return falso


@pytest.fixture
def tela(qt_interface, qtbot, monkeypatch):
    monkeypatch.setattr(tela_mod.prefs, "get_default_dir", lambda chave: None)
    t = tela_mod.ModuloPDM()
    qtbot.addWidget(t)
    t.avisos = []
    monkeypatch.setattr(t, "avisar", lambda ti, m, tipo="info": t.avisos.append(
        (tipo, ti, m, threading.current_thread() is threading.main_thread())))
    return t


def _texto(tela):
    return tela.console.toPlainText()


def _esperar_aviso(tela, qtbot, n=1):
    qtbot.waitUntil(lambda: len(tela.avisos) >= n, timeout=3000)
    return tela.avisos[n - 1]


def _modulo_falso(monkeypatch, nome, **funcoes):
    modulo = SimpleNamespace(**funcoes)
    monkeypatch.setitem(sys.modules, f"sigft.services.{nome}", modulo)
    import sigft.services as servicos
    monkeypatch.setattr(servicos, nome, modulo, raising=False)
    return modulo


# ---------------------------------------------------------------------------
# Montagem
# ---------------------------------------------------------------------------
def test_monta_com_os_textos_e_os_padroes(tela):
    assert tela.label_titulo.text() == "Gerenciador de PDMs"
    r = tela._rotulos
    assert r["config"].text() == "Configuração Global"
    assert r["destino"].text() == "Pasta dos PDMs Modificados:"
    assert r["sam_gm"].text() == "Planilha de PDMs (SAM-GM):"
    assert tela.btn_sel_destino.text() == "Selecionar" and tela.btn_sam_gm.text() == "Selecionar"
    assert tela.lbl_sam_gm_status.text() == "Nenhum arquivo selecionado"
    assert list(tela.tabview.abas) == ABAS and tela.tabview.get() == "Processar PDMs"
    # Aba 1
    assert r["itaipu"].text() == "Pasta (PDMs From Itaipu):"
    assert r["regen"].text() == "Regenerar as pastas a partir da planilha"
    assert tela.btn_regenerar.text() == "Executar: Regenerar as pastas"
    assert r["regen_desc"].text() == ("Com a revisão no nome (PDM_1650_001 - ACUMULADOR - R2_formatado.xlsx); "
                                      "a versão antiga vai para _versoes_antigas, nada é apagado.")
    assert r["from"].text() == "1. Fatiar Arquivo Geral (From Itaipu)"
    assert tela.btn_from_itaipu.text() == "Executar: Criar PDMs From Itaipu"
    assert r["from_desc"].text() == "Usa a planilha do painel de cima; só cria os PDMs que faltam na pasta."
    assert r["mod"].text() == "2. Formatar PDMs (Modificados)"
    assert r["mod_desc"].text() == "Utiliza a 'Pasta (PDMs From Itaipu)' como base para leitura."
    assert tela.rb_lote.text() == "Lote (Todos os Novos)" and tela.rb_lote.isChecked()
    assert tela.rb_especifico.text() == "Específico (Escolher 1 arquivo)"
    assert tela.btn_modificados.text() == "Executar: Criar PDMs Modificados"
    assert r["traduzir"].text() == "3. Traduzir para inglês (ficha em inglês)"
    assert r["traduzir_desc"].text() == (
        "Lê a 'Pasta dos PDMs Modificados' e grava a versão em inglês noutra pasta.\n"
        "Rode uma vez; o resultado fica em cache e o glossário editável "
        "(_GLOSSARIO_PT_EN.txt) corrige termo técnico de vez.")
    assert r["en"].text() == "Pasta dos PDMs Modificados (EN):"
    assert tela.btn_traduzir.text() == "Executar: Traduzir PDMs Modificados para inglês"
    # Aba 2
    assert r["fichas"].text() == "Configuração das Fichas PMIB"
    assert r["fonte"].text() == "Fonte das características:"
    assert tela.rb_fonte_planilha.text() == "Planilha de PDMs" and tela.rb_fonte_planilha.isChecked()
    assert tela.rb_fonte_pasta.text() == "Pasta de PDMs Modificados (método antigo)"
    assert tela.btn_pmib.text() == "Selecionar STATUS_PMIB (.xlsx)"
    assert tela.lbl_pmib_status.text() == "Nenhum arquivo selecionado"
    assert r["destino_fichas"].text() == "Pasta Destino das Fichas:"
    assert tela.btn_template.text() == "Selecionar Template (.xlsx)"
    assert tela.lbl_template_status.text() == "Nenhum arquivo selecionado"
    assert r["idioma"].text() == "Idioma da ficha:"
    assert tela.rb_pt.text() == "Português" and tela.rb_pt.isChecked() and tela.rb_en.text() == "English"
    assert r["idioma_dica"].text() == "(English usa a pasta de PDMs traduzidos)"
    assert r["selecao"].text() == "Seleção de Itens:" and r["saida"].text() == "Formato de Saída:"
    assert tela.rb_todos.text() == "Todos da Lista" and tela.rb_todos.isChecked()
    assert tela.rb_selecionar.text() == "Selecionar Manualmente"
    assert tela.rb_apenas.text() == "Apenas Planilhas (Padrão)" and tela.rb_apenas.isChecked()
    assert tela.rb_com_pastas.text() == "Criar Subpastas + Planilhas"
    assert tela.btn_criar_fichas.text() == "Executar: Criar Fichas PMIB"
    # Aba 3
    assert r["limpeza"].text() == "Remove versões antigas de arquivos na pasta (limpeza de versões)."
    assert r["clean"].text() == "Pasta para Limpeza:"
    assert tela.btn_exec_clean.text() == "Executar Limpeza"
    # Os valores dos grupos de rádio (os StringVar de lá)
    assert (tela.modo_proc.get(), tela.fonte_perguntas.get(), tela.idioma_ficha.get(),
            tela.modo_pmib.get(), tela.modo_saida_fichas.get()) == (
        "todos", "planilha", "pt", "todos", "apenas_planilhas")
    for campo in (tela.entry_dest, tela.entry_pdms_itaipu, tela.entry_destino_en,
                  tela.entry_destino_fichas, tela.entry_clean):
        assert campo.text() == ""


def test_radios_trocam_o_valor(tela):
    tela.rb_especifico.click()
    tela.rb_fonte_pasta.click()
    tela.rb_en.click()
    tela.rb_selecionar.click()
    tela.rb_com_pastas.click()
    assert (tela.modo_proc.get(), tela.fonte_perguntas.get(), tela.idioma_ficha.get(),
            tela.modo_pmib.get(), tela.modo_saida_fichas.get()) == (
        "especifico", "pasta", "en", "selecionar", "com_pastas")
    assert not tela.rb_lote.isChecked() and not tela.rb_pt.isChecked()
    tela.idioma_ficha.set("pt")
    assert tela.rb_pt.isChecked() and tela.idioma_ficha.get() == "pt"


def test_pasta_dos_modificados_vem_preenchida_com_a_padrao(qt_interface, qtbot, monkeypatch):
    pedidas = []
    monkeypatch.setattr(tela_mod.prefs, "get_default_dir",
                        lambda chave: pedidas.append(chave) or "/rede/PDMs Modificados")
    t = tela_mod.ModuloPDM()
    qtbot.addWidget(t)
    assert pedidas == ["pdms_modificados"]
    assert t.entry_dest.text() == "/rede/PDMs Modificados"


def test_abas_trocam(tela):
    tela.tabview.botoes["Excluir Duplicados"].click()
    assert tela.tabview.get() == "Excluir Duplicados"
    tela.tabview.set("Criar planilhas PMIB")
    assert tela.tabview.get() == "Criar planilhas PMIB"


# ---------------------------------------------------------------------------
# Seletores
# ---------------------------------------------------------------------------
def test_seletores_de_arquivo(tela, monkeypatch):
    chamadas = []
    respostas = iter(["/d/PDMs SAM-GM.xlsx", "/d/_STATUS_PMIB.xlsx", "/d/Template FT.xlsx"])

    def falso(chave, categoria, **k):
        chamadas.append((chave, categoria, k))
        return next(respostas)

    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", falso)
    tela.btn_sam_gm.click()
    tela.btn_pmib.click()
    tela.btn_template.click()
    excel = [("Excel", "*.xlsx *.xls")]
    assert chamadas == [
        ("pdm.sam_gm", "excel", {"titulo": "Selecione o PDM's SAM-GM", "filetypes": excel}),
        ("pdm.status_pmib", "excel", {"titulo": "Selecione o STATUS_PMIB", "filetypes": excel}),
        ("pdm.template", "excel", {"titulo": "Selecione o Template", "filetypes": excel}),
    ]
    assert (tela.path_sam_gm, tela.path_status_pmib, tela.path_template) == (
        "/d/PDMs SAM-GM.xlsx", "/d/_STATUS_PMIB.xlsx", "/d/Template FT.xlsx")
    assert tela.lbl_sam_gm_status.text() == "PDMs SAM-GM.xlsx"
    assert tela.lbl_pmib_status.text() == "_STATUS_PMIB.xlsx"
    assert tela.lbl_template_status.text() == "Template FT.xlsx"
    for rotulo in (tela.lbl_sam_gm_status, tela.lbl_pmib_status, tela.lbl_template_status):
        assert theme.COLORS["accent"] in rotulo.styleSheet()
    for botao in (tela.btn_sam_gm, tela.btn_pmib, tela.btn_template):
        assert theme.COLORS["primary"] in botao.styleSheet()


def test_cancelar_o_seletor_de_arquivo_nao_mexe_em_nada(tela, monkeypatch):
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "")
    for botao in (tela.btn_sam_gm, tela.btn_pmib, tela.btn_template):
        botao.click()
    assert tela.path_sam_gm == tela.path_status_pmib == tela.path_template == ""
    assert tela.lbl_pmib_status.text() == "Nenhum arquivo selecionado"
    assert theme.COLORS["primary"] not in tela.btn_pmib.styleSheet()


def test_seletores_de_pasta(tela, monkeypatch):
    chamadas = []

    def falso(chave, categoria, **k):
        chamadas.append((chave, categoria, k.get("titulo")))
        return f"/escolhida/{chave}"

    monkeypatch.setattr(tela_mod.file_dialogs, "ask_directory", falso)
    pares = [(tela.btn_sel_destino, tela.entry_dest), (tela.btn_buscar_itaipu, tela.entry_pdms_itaipu),
             (tela.btn_buscar_en, tela.entry_destino_en), (tela.btn_buscar_fichas, tela.entry_destino_fichas),
             (tela.btn_buscar_clean, tela.entry_clean)]
    for botao, _campo in pares:
        botao.click()
    assert chamadas == [
        ("pdm.caminho_destino", "pasta", None),
        ("pdm.pdms_itaipu", "pasta", "Pasta de Origem dos PDMs"),
        ("pdm.pdms_modificados_en", "pasta", "Pasta dos PDMs Modificados em INGLÊS"),
        ("pdm.destino_fichas", "pasta", "Pasta onde as fichas serão criadas"),
        ("pdm.clean_dir", "pasta", "Selecione a pasta para limpar duplicatas"),
    ]
    assert [c.text() for _b, c in pares] == [f"/escolhida/{ch}" for ch, _c, _t in chamadas]


def test_cancelar_a_pasta_mantem_o_caminho_escolhido(tela, monkeypatch):
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_directory", lambda *a, **k: "")
    tela.entry_pdms_itaipu.setText("/ja/escolhida")
    tela.entry_dest.setText("/modificados")
    tela.btn_buscar_itaipu.click()
    tela.btn_sel_destino.click()
    assert tela.entry_pdms_itaipu.text() == "/ja/escolhida" and tela.entry_dest.text() == "/modificados"


# ---------------------------------------------------------------------------
# Aba 1: From Itaipu, Modificados, Tradução, Regeneração
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("lista, pasta, mensagem", [
    ("", "/i", "Por favor, selecione a Planilha de PDMs no painel de cima."),
    ("/d/s.xlsx", "", "Por favor, selecione a Pasta (PDMs From Itaipu) na tela."),
])
def test_from_itaipu_valida(tela, pdm, lista, pasta, mensagem):
    tela.path_sam_gm = lista
    tela.entry_pdms_itaipu.setText(pasta)
    tela.btn_from_itaipu.click()
    assert tela.avisos == [("aviso", "Aviso", mensagem, True)] and pdm.chamadas == []


def test_from_itaipu_roda_em_thread_e_mostra_o_relatorio(tela, qtbot, pdm):
    tela.path_sam_gm = "/d/PDMs SAM-GM.xlsx"
    tela.entry_pdms_itaipu.setText("/i")
    tela.btn_from_itaipu.click()
    assert _esperar_aviso(tela, qtbot) == ("info", "Relatório", "12 PDMs criados", False)
    assert pdm.chamadas == [("from_itaipu", ("/d/PDMs SAM-GM.xlsx", "/i"),
                             {"retry_lock": tela.perguntar_retry_excel})]
    assert pdm.threads == [False]
    qtbot.waitUntil(lambda: "> 12 PDMs criados" in _texto(tela), timeout=2000)
    texto = _texto(tela)
    ordem = ["> Fatiando a lista geral: PDMs SAM-GM.xlsx...", "> fatiando...", "> 12 PDMs criados"]
    assert [texto.index(x) for x in ordem] == sorted(texto.index(x) for x in ordem)
    qtbot.waitUntil(tela.btn_from_itaipu.isEnabled, timeout=2000)


def test_sem_backend_avisa_e_nao_roda(tela, monkeypatch):
    monkeypatch.setattr(backends, "pdm_backend", None)
    monkeypatch.setattr(backends, "motivo_da_falha", lambda nome: "faltou o pandas")
    avisos = []
    monkeypatch.setattr(tela_mod.ModuleFrame, "backend",
                        lambda self, nome: avisos.append(nome))
    tela.path_sam_gm = "/d/s.xlsx"
    tela.entry_pdms_itaipu.setText("/i")
    tela.btn_from_itaipu.click()
    assert avisos == ["pdm_backend"] and tela.btn_from_itaipu.isEnabled()


@pytest.mark.parametrize("destino, origem, mensagem", [
    ("", "/i", "Selecione a Pasta dos PDMs Modificados primeiro."),
    ("/m", "", "Por favor, selecione a 'Pasta (PDMs From Itaipu)' na tela."),
])
def test_modificados_valida(tela, pdm, destino, origem, mensagem):
    tela.entry_dest.setText(destino)
    tela.entry_pdms_itaipu.setText(origem)
    tela.btn_modificados.click()
    assert tela.avisos == [("aviso", "Aviso", mensagem, True)] and pdm.chamadas == []


def test_modificados_em_lote(tela, qtbot, pdm):
    pdm.arquivos = ["/i/a.xlsx", "/i/ruim.xlsx", "/i/b.xlsx"]
    tela.entry_dest.setText("/m")
    tela.entry_pdms_itaipu.setText("/i")
    tela.btn_modificados.click()
    # O destino é lido no clique: mudar o campo depois não muda o lote.
    tela.entry_dest.setText("/outro")
    assert _esperar_aviso(tela, qtbot) == ("info", "Fim", "2 arquivos processados com sucesso.", False)
    salvos = [c for c in pdm.chamadas if c[0] == "salvar"]
    assert salvos == [
        ("salvar", ("tbl:/i/a.xlsx", "/i/a.xlsx", "/m"), {"force": False, "retry_lock": tela.perguntar_retry_excel}),
        ("salvar", ("tbl:/i/b.xlsx", "/i/b.xlsx", "/m"), {"force": False, "retry_lock": tela.perguntar_retry_excel}),
    ]
    qtbot.waitUntil(lambda: "Fim: 2 arquivos" in _texto(tela), timeout=2000)
    texto = _texto(tela)
    ordem = ["> Processando todos em: /i", "> salvo /i/a.xlsx", "> salvo /i/b.xlsx",
             "> Fim: 2 arquivos processados com sucesso."]
    assert [texto.index(x) for x in ordem] == sorted(texto.index(x) for x in ordem)


def test_modificados_especifico(tela, qtbot, pdm, monkeypatch):
    pedidos = []
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file",
                        lambda chave, cat, **k: pedidos.append((chave, cat, k)) or "/i/PDM_1.xlsx")
    tela.entry_dest.setText("/m")
    tela.entry_pdms_itaipu.setText("/i")
    tela.rb_especifico.click()
    tela.btn_modificados.click()
    assert pedidos == [("pdm.arquivo_especifico", "excel", {
        "titulo": "Selecione o arquivo PDM específico", "filetypes": [("Excel", "*.xlsx *.xls")],
        "initialdir": "/i"})]
    assert _esperar_aviso(tela, qtbot) == ("info", "Status", "salvo /i/PDM_1.xlsx", False)
    assert ("salvar", ("tbl:/i/PDM_1.xlsx", "/i/PDM_1.xlsx", "/m"),
            {"force": True, "retry_lock": tela.perguntar_retry_excel}) in pdm.chamadas


def test_modificados_especifico_cancelado(tela, qtbot, pdm, monkeypatch):
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "")
    tela.entry_dest.setText("/m")
    tela.entry_pdms_itaipu.setText("/i")
    tela.rb_especifico.click()
    tela.btn_modificados.click()
    qtbot.waitUntil(lambda: "> Seleção de arquivo específico cancelada." in _texto(tela), timeout=2000)
    assert pdm.chamadas == [] and tela.avisos == [] and tela.btn_modificados.isEnabled()


@pytest.mark.parametrize("origem, destino, aviso", [
    ("", "/en", ("aviso", "Aviso", "Selecione a 'Pasta dos PDMs Modificados' primeiro.", True)),
    ("/m", "", ("aviso", "Aviso", "Selecione a pasta de destino dos PDMs Modificados em INGLÊS.", True)),
    ("/m", "/m/", ("erro", "Erro", "A pasta de destino não pode ser a mesma da origem.\n"
                                    "Os arquivos em português seriam sobrescritos.", True)),
])
def test_traduzir_valida(tela, monkeypatch, origem, destino, aviso):
    chamadas = []
    _modulo_falso(monkeypatch, "traducao_pdm", traduzir_pasta=lambda *a, **k: chamadas.append(a) or [],
                  motor_padrao=lambda **k: None)
    tela.entry_dest.setText(origem)
    tela.entry_destino_en.setText(destino)
    tela.btn_traduzir.click()
    assert tela.avisos == [aviso] and chamadas == []


def test_traduzir(tela, qtbot, monkeypatch):
    chamadas = []

    def motor_padrao(api_key=None, callbacks=None):
        chamadas.append(("motor", api_key, callbacks))
        callbacks.log("motor pronto")
        return "MOTOR"

    def traduzir_pasta(origem, destino, traduzir=None, retry_lock=None):
        chamadas.append(("pasta", origem, destino, traduzir, retry_lock))
        yield "traduzido PDM_1"

    _modulo_falso(monkeypatch, "traducao_pdm", traduzir_pasta=traduzir_pasta, motor_padrao=motor_padrao)
    tela.entry_dest.setText("/m")
    tela.entry_destino_en.setText("/en")
    tela.btn_traduzir.click()
    assert _esperar_aviso(tela, qtbot) == ("info", "Tradução", "Tradução concluída.\n\nPasta: /en", False)
    assert chamadas[0][0] == "motor" and chamadas[0][1] is None  # sem api_key: a do provedor escolhido
    assert chamadas[1] == ("pasta", "/m", "/en", "MOTOR", tela.perguntar_retry_excel)
    qtbot.waitUntil(lambda: "> traduzido PDM_1" in _texto(tela), timeout=2000)
    texto = _texto(tela)
    assert texto.index("> Traduzindo PDMs Modificados para inglês...") < texto.index("> traduzido PDM_1")
    assert "motor pronto" in texto


def test_traduzir_com_erro(tela, qtbot, monkeypatch):
    def traduzir_pasta(*a, **k):
        raise RuntimeError("sem chave da IA")

    _modulo_falso(monkeypatch, "traducao_pdm", traduzir_pasta=traduzir_pasta, motor_padrao=lambda **k: None)
    tela.entry_dest.setText("/m")
    tela.entry_destino_en.setText("/en")
    tela.btn_traduzir.click()
    assert _esperar_aviso(tela, qtbot) == ("erro", "Erro", "Falha na tradução:\nsem chave da IA", False)
    qtbot.waitUntil(lambda: "> ERRO na tradução: sem chave da IA" in _texto(tela), timeout=2000)


@pytest.mark.parametrize("planilha, modificados, mensagem", [
    ("", "/m", "Selecione a planilha de PDMs no painel de cima."),
    ("/d/s.xlsx", "", "Selecione a 'Pasta dos PDMs Modificados' no painel de cima."),
])
def test_regenerar_valida(tela, monkeypatch, planilha, modificados, mensagem):
    chamadas = []
    _modulo_falso(monkeypatch, "pdm_regeneracao", regenerar_pastas=lambda *a, **k: chamadas.append(a))
    tela.path_sam_gm = planilha
    tela.entry_dest.setText(modificados)
    tela.btn_regenerar.click()
    assert tela.avisos == [("aviso", "Aviso", mensagem, True)] and chamadas == []


@pytest.mark.parametrize("itaipu, esperado", [("", None), ("/i", "/i")])
def test_regenerar(tela, qtbot, monkeypatch, itaipu, esperado):
    chamadas = []

    def regenerar(planilha, modificados, pasta_itaipu, log_callback=None, retry_lock=None):
        chamadas.append((planilha, modificados, pasta_itaipu, retry_lock))
        log_callback("PDM_1650_001 regenerado")
        return "40 PDMs regenerados"

    _modulo_falso(monkeypatch, "pdm_regeneracao", regenerar_pastas=regenerar)
    tela.path_sam_gm = "/d/s.xlsx"
    tela.entry_dest.setText("/m")
    tela.entry_pdms_itaipu.setText(itaipu)
    tela.btn_regenerar.click()
    assert _esperar_aviso(tela, qtbot) == ("info", "Regeneração", "40 PDMs regenerados", False)
    assert chamadas == [("/d/s.xlsx", "/m", esperado, tela.perguntar_retry_excel)]
    qtbot.waitUntil(lambda: "> 40 PDMs regenerados" in _texto(tela), timeout=2000)
    texto = _texto(tela)
    assert (texto.index("> Regenerando as pastas a partir da planilha de PDMs...")
            < texto.index("> PDM_1650_001 regenerado") < texto.index("> 40 PDMs regenerados"))


def test_regenerar_com_erro(tela, qtbot, monkeypatch):
    def regenerar(*a, **k):
        raise ValueError("as duas pastas são a mesma")

    _modulo_falso(monkeypatch, "pdm_regeneracao", regenerar_pastas=regenerar)
    tela.path_sam_gm = "/d/s.xlsx"
    tela.entry_dest.setText("/m")
    tela.btn_regenerar.click()
    assert _esperar_aviso(tela, qtbot) == (
        "erro", "Erro", "A regeneração não foi feita:\nas duas pastas são a mesma", False)
    qtbot.waitUntil(lambda: "> ERRO na regeneração: as duas pastas são a mesma" in _texto(tela), timeout=2000)


def test_botao_fica_desligado_enquanto_a_tarefa_roda(tela, qtbot, monkeypatch):
    solta = threading.Event()

    def regenerar(*a, **k):
        solta.wait(3)
        return "ok"

    _modulo_falso(monkeypatch, "pdm_regeneracao", regenerar_pastas=regenerar)
    tela.path_sam_gm = "/d/s.xlsx"
    tela.entry_dest.setText("/m")
    tela.btn_regenerar.click()
    assert not tela.btn_regenerar.isEnabled()
    solta.set()
    qtbot.waitUntil(tela.btn_regenerar.isEnabled, timeout=3000)


# ---------------------------------------------------------------------------
# Aba 2: Criar fichas
# ---------------------------------------------------------------------------
def _preencher_aba2(tela, *, planilha="/d/s.xlsx", modificados="/m", en="/en", status="/d/_STATUS_PMIB.xlsx",
                    destino="/fichas", template="/d/T.xlsx"):
    tela.path_sam_gm = planilha
    tela.entry_dest.setText(modificados)
    tela.entry_destino_en.setText(en)
    tela.path_status_pmib = status
    tela.entry_destino_fichas.setText(destino)
    tela.path_template = template


@pytest.mark.parametrize("fonte, idioma, campos, mensagem", [
    ("planilha", "en", {}, "A ficha em inglês usa a pasta traduzida. Escolha a fonte "
                           "'Pasta de PDMs Modificados' ou o idioma Português."),
    ("planilha", "pt", {"planilha": ""}, "Selecione a planilha de PDMs no painel de cima."),
    ("pasta", "en", {"en": ""}, "Idioma da ficha = English, mas a 'Pasta dos PDMs Modificados "
                                "(EN)' não foi selecionada.\n\nEla fica na aba 1, no passo 3 "
                                "(Traduzir para inglês)."),
    ("pasta", "pt", {"modificados": ""}, "Selecione a 'Pasta dos PDMs Modificados' primeiro."),
    ("planilha", "pt", {"status": ""}, "Por favor, busque o arquivo STATUS_PMIB na tela."),
    ("pasta", "pt", {"destino": ""}, "Por favor, busque a Pasta Destino das Fichas na tela."),
    ("planilha", "pt", {"template": ""}, "Por favor, busque o Template Ficha Técnica na tela."),
])
def test_criar_fichas_valida(tela, pdm, fonte, idioma, campos, mensagem):
    _preencher_aba2(tela, **campos)
    tela.fonte_perguntas.set(fonte)
    tela.idioma_ficha.set(idioma)
    tela.btn_criar_fichas.click()
    assert tela.avisos == [("aviso", "Aviso", mensagem, True)] and pdm.chamadas == []


def test_criar_fichas_da_planilha(tela, qtbot, pdm, monkeypatch):
    carregados = []
    monkeypatch.setattr(tela_mod.pdm_catalogo, "carregar", lambda p: carregados.append(p) or "CATALOGO")
    _preencher_aba2(tela)
    tela.btn_criar_fichas.click()
    assert _esperar_aviso(tela, qtbot) == (
        "info", "Fim", "Processo de criação de fichas finalizado.\n\n3 fichas da planilha", False)
    assert carregados == ["/d/s.xlsx"]
    assert pdm.chamadas == [
        ("pastas", ("/d/_STATUS_PMIB.xlsx", "/fichas", None), {"criar_subpastas": False}),
        ("templates_planilha", (["d1"], "CATALOGO", "/d/T.xlsx"), {"retry_lock": tela.perguntar_retry_excel}),
    ]
    qtbot.waitUntil(lambda: ">>> Processo de criação de fichas finalizado!" in _texto(tela), timeout=2000)
    texto = _texto(tela)
    ordem = ["> Lendo a planilha de PDMs...", "> Preparando diretórios (Modo: Apenas Planilhas)...",
             "> 3 pastas preparadas", "> 3 fichas da planilha", "> >>> Processo de criação de fichas finalizado!"]
    assert [texto.index(x) for x in ordem] == sorted(texto.index(x) for x in ordem)


def test_criar_fichas_da_pasta_em_ingles_com_subpastas(tela, qtbot, pdm, monkeypatch):
    monkeypatch.setattr(tela_mod.pdm_catalogo, "carregar", lambda p: pytest.fail("não lê a planilha"))
    _preencher_aba2(tela)
    tela.rb_fonte_pasta.click()
    tela.rb_en.click()
    tela.rb_com_pastas.click()
    tela.btn_criar_fichas.click()
    tela.rb_pt.click()  # mudar depois do clique não muda o lote
    assert _esperar_aviso(tela, qtbot)[:3] == (
        "info", "Fim", "Processo de criação de fichas finalizado.\n\n3 fichas montadas")
    assert pdm.chamadas == [
        ("pastas", ("/d/_STATUS_PMIB.xlsx", "/fichas", None), {"criar_subpastas": True}),
        ("templates_pasta", (["d1"], "/en", "/d/T.xlsx"), {"retry_lock": tela.perguntar_retry_excel,
                                                            "idioma": "en"}),
    ]
    qtbot.waitUntil(lambda: "a partir da linha 79" in _texto(tela), timeout=2000)
    assert "> Preparando diretórios (Modo: Com Pastas)..." in _texto(tela)


def test_criar_fichas_da_pasta_em_portugues(tela, qtbot, pdm):
    _preencher_aba2(tela)
    tela.rb_fonte_pasta.click()
    tela.btn_criar_fichas.click()
    _esperar_aviso(tela, qtbot)
    assert pdm.chamadas[1] == ("templates_pasta", (["d1"], "/m", "/d/T.xlsx"),
                               {"retry_lock": tela.perguntar_retry_excel, "idioma": "pt"})


def test_criar_fichas_planilha_ilegivel_para_antes_das_pastas(tela, qtbot, pdm, monkeypatch):
    def carregar(p):
        raise ValueError("aba SAM-GM não encontrada")

    monkeypatch.setattr(tela_mod.pdm_catalogo, "carregar", carregar)
    _preencher_aba2(tela)
    tela.btn_criar_fichas.click()
    assert _esperar_aviso(tela, qtbot) == (
        "erro", "Erro", "Não consegui ler a planilha de PDMs:\naba SAM-GM não encontrada", False)
    assert pdm.chamadas == []
    qtbot.waitUntil(lambda: "> ERRO ao ler a planilha de PDMs: aba SAM-GM" in _texto(tela), timeout=2000)


def test_criar_fichas_sem_codigo_processado(tela, qtbot, pdm, monkeypatch):
    monkeypatch.setattr(tela_mod.pdm_catalogo, "carregar", lambda p: "CAT")
    pdm.dados_pastas = []
    _preencher_aba2(tela)
    tela.btn_criar_fichas.click()
    assert _esperar_aviso(tela, qtbot) == ("info", "Aviso", "Nenhum código foi processado.", False)
    assert [c[0] for c in pdm.chamadas] == ["pastas"]


class SelecaoFalsa:
    """`SelecaoMultiplaDialog` de mentira: confirma `escolha` (ou fecha, com None)."""
    criadas = []

    def __init__(self, parent=None, *, escolha, **kw):
        self.kw, self.escolha = kw, escolha
        SelecaoFalsa.criadas.append(self)

    def esperar(self):
        if self.escolha is not None:
            self.kw["ao_confirmar"](self.escolha)
        return self.escolha


def _selecao_falsa(monkeypatch, escolha):
    SelecaoFalsa.criadas = []
    monkeypatch.setattr(tela_mod, "_SelecaoDeCodigos",
                        lambda parent=None, **kw: SelecaoFalsa(parent, escolha=escolha, **kw))


def test_criar_fichas_selecionando_os_codigos(tela, qtbot, pdm, monkeypatch):
    monkeypatch.setattr(tela_mod.pdm_catalogo, "carregar", lambda p: "CAT")
    _selecao_falsa(monkeypatch, ["PMIB-2"])
    _preencher_aba2(tela)
    tela.rb_selecionar.click()
    tela.btn_criar_fichas.click()
    _esperar_aviso(tela, qtbot)
    dlg, = SelecaoFalsa.criadas
    assert dlg.kw == {
        "itens": ["PMIB-1", "PMIB-2", "PMIB-3"], "titulo": "Selecione os Códigos PMIB",
        "instrucao": "Selecione um ou mais códigos:", "geometria": "400x500",
        "fonte_instrucao": ("Roboto", 14), "fonte_lista": ("Consolas", 11), "modal": True,
        "ao_confirmar": dlg.kw["ao_confirmar"]}
    assert pdm.chamadas[0] == ("codigos", ("/d/_STATUS_PMIB.xlsx",), {})
    assert pdm.chamadas[1] == ("pastas", ("/d/_STATUS_PMIB.xlsx", "/fichas", ["PMIB-2"]),
                               {"criar_subpastas": False})


def test_criar_fichas_selecao_cancelada(tela, qtbot, pdm, monkeypatch):
    _selecao_falsa(monkeypatch, None)
    _preencher_aba2(tela)
    tela.rb_selecionar.click()
    tela.btn_criar_fichas.click()
    qtbot.waitUntil(lambda: "> Seleção manual de códigos cancelada." in _texto(tela), timeout=2000)
    assert [c[0] for c in pdm.chamadas] == ["codigos"] and tela.avisos == []
    assert tela.btn_criar_fichas.isEnabled()


def test_criar_fichas_status_pmib_sem_coluna(tela, pdm):
    pdm.erro_codigos = ValueError("Coluna 'CÓDIGO PMIB' não encontrada")
    _preencher_aba2(tela)
    tela.rb_selecionar.click()
    tela.btn_criar_fichas.click()
    assert tela.avisos == [("erro", "Erro", "Coluna 'CÓDIGO PMIB' não encontrada", True)]
    assert [c[0] for c in pdm.chamadas] == ["codigos"]


def test_criar_fichas_status_pmib_ilegivel(tela, pdm):
    pdm.erro_codigos = OSError("arquivo corrompido")
    _preencher_aba2(tela)
    tela.rb_selecionar.click()
    tela.btn_criar_fichas.click()
    assert tela.avisos == [("erro", "Erro", "Ocorreu um erro ao ler o STATUS_PMIB:\narquivo corrompido", True)]


def test_janela_real_de_selecao_confirma_e_esc_nao_descarta(tela, qtbot, pdm, monkeypatch):
    """A janela de verdade: Esc não fecha (não perde os códigos marcados, e o Tk
    não tinha tecla), "Confirmar Seleção" devolve os marcados."""
    monkeypatch.setattr(tela_mod.pdm_catalogo, "carregar", lambda p: "CAT")
    _preencher_aba2(tela)
    tela.rb_selecionar.click()
    vistos = {}

    def mexer():
        dlg = next(w for w in tela.findChildren(tela_mod._SelecaoDeCodigos) if w.isVisible())
        vistos["modal"] = dlg.isModal()
        dlg.listbox.item(0).setSelected(True)
        dlg.listbox.item(2).setSelected(True)
        qtbot.keyClick(dlg, Qt.Key.Key_Escape)
        vistos["depois_do_esc"] = dlg.isVisible()
        dlg.botao_confirmar.click()

    QTimer.singleShot(50, mexer)
    tela.btn_criar_fichas.click()
    _esperar_aviso(tela, qtbot)
    assert vistos == {"modal": True, "depois_do_esc": True}
    assert pdm.chamadas[1][1][2] == ["PMIB-1", "PMIB-3"]


def test_janela_real_de_selecao_fechada_no_x_cancela(tela, qtbot, pdm):
    _preencher_aba2(tela)
    tela.rb_selecionar.click()

    def fechar():
        dlg = next(w for w in tela.findChildren(tela_mod._SelecaoDeCodigos) if w.isVisible())
        dlg.listbox.item(0).setSelected(True)
        dlg.close()

    QTimer.singleShot(50, fechar)
    tela.btn_criar_fichas.click()
    qtbot.waitUntil(lambda: "> Seleção manual de códigos cancelada." in _texto(tela), timeout=2000)
    assert [c[0] for c in pdm.chamadas] == ["codigos"]


# ---------------------------------------------------------------------------
# Aba 3: Limpeza
# ---------------------------------------------------------------------------
def test_limpeza_valida(tela, pdm):
    tela.btn_exec_clean.click()
    assert tela.avisos == [("aviso", "Aviso", "Por favor, selecione a pasta para limpeza primeiro.", True)]
    assert pdm.chamadas == []


def test_limpeza(tela, qtbot, pdm):
    tela.entry_clean.setText("/fichas")
    tela.btn_exec_clean.click()
    assert _esperar_aviso(tela, qtbot) == ("info", "Resultado", "Limpeza concluída.", False)
    assert pdm.chamadas == [("limpeza", ("/fichas",), {})]
    qtbot.waitUntil(lambda: "> 1 duplicado removido" in _texto(tela), timeout=2000)
    texto = _texto(tela)
    assert (texto.index("> Iniciando varredura por duplicados em: /fichas...")
            < texto.index("> removido x_v1.xlsx") < texto.index("> 1 duplicado removido"))


# ---------------------------------------------------------------------------
# Geometria contra o CustomTkinter
# ---------------------------------------------------------------------------
@pytest.fixture
def tela_medida(qt_interface, qtbot, monkeypatch):
    from sigft.app_qt import estilo

    monkeypatch.setattr(tela_mod.prefs, "get_default_dir", lambda chave: None)
    anterior = qt_interface.styleSheet()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    t = tela_mod.ModuloPDM()
    qtbot.addWidget(t)
    t.resize(1003, 850)
    t.show()
    qtbot.waitExposed(t)
    yield t
    qt_interface.setStyleSheet(anterior)


def _geo(t, w):
    p = w.mapTo(t, w.rect().topLeft())
    return p.x(), p.y(), w.width(), w.height()


def _perto(a, b, tol):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def test_medidas_iguais_as_do_customtkinter(tela_medida, qtbot):
    # Medidas da tela antiga (CustomTkinter, janela 1280x850, winfo_* -- aqui
    # relativas à área da tela, 277 px à direita da barra lateral). Ver
    # capturas/e4.6. Larguras de texto: ±8 (Roboto do Qt × do Tk; o hinting
    # muda com a ordem dos testes, que mexem na fonte do app).
    t, r = tela_medida, tela_medida._rotulos
    g = lambda w: _geo(t, w)  # noqa: E731
    assert g(t.label_titulo)[:2] == (40, 30)
    assert g(t.area) == (40, 79, 923, 571)
    assert g(t.console) == (40, 670, 923, 150)
    # Configuração global
    assert g(t.cartao_config) == (46, 95, 900, 119)
    assert g(r["config"])[:2] == (61, 105)
    assert g(r["destino"]) == (61, 138, 190, 28)
    assert g(t.entry_dest) == (256, 138, 350, 28)
    assert g(t.btn_sel_destino) == (611, 138, 100, 28)
    assert g(r["sam_gm"]) == (61, 171, 190, 28)
    assert g(t.btn_sam_gm) == (256, 171, 100, 28)
    assert g(t.lbl_sam_gm_status)[:2] == (376, 171)
    # Abas: a barra 10 px abaixo do topo, o quadro da aba em (6, 43)
    assert g(t.tabview) == (46, 234, 900, 571)
    assert g(t.tabview.barra)[1] == 244
    centro_barra = g(t.tabview.barra)[0] + g(t.tabview.barra)[2] / 2
    assert abs(centro_barra - (46 + 450)) <= 1
    # Aba 1
    assert g(r["itaipu"]) == (72, 287, 240, 28)
    assert g(t.entry_pdms_itaipu) == (317, 287, 280, 28)
    assert g(t.btn_buscar_itaipu) == (602, 287, 80, 28)
    assert g(t.quadro_regen) == (72, 321, 848, 70)
    assert g(r["regen"])[:2] == (82, 327)
    assert _perto(g(t.btn_regenerar), (720, 327, 190, 28), 8) and sum(g(t.btn_regenerar)[::2]) == 910
    assert g(r["regen_desc"])[:2] == (82, 355)
    assert g(t.quadro_from) == (72, 403, 848, 70)
    assert _perto(g(t.btn_from_itaipu), (705, 409, 205, 28), 8) and sum(g(t.btn_from_itaipu)[::2]) == 910
    assert g(r["from_desc"])[:2] == (82, 437)
    assert g(t.quadro_mod) == (72, 485, 848, 308)
    assert g(r["mod"])[:2] == (82, 490)
    assert g(r["mod_desc"])[:2] == (82, 523)
    assert _perto(g(t.rb_lote), (92, 556, 158, 22), 4)
    assert _perto(g(t.rb_especifico), (270, 556, 206, 22), 4)
    assert _perto(g(t.btn_modificados), (390, 593, 211, 28), 8)
    assert g(r["traduzir"])[:2] == (82, 646)
    assert g(r["traduzir_desc"])[:2] == (82, 679)
    assert g(r["en"]) == (82, 712, 240, 28)
    assert g(t.entry_destino_en) == (327, 712, 280, 28)
    assert g(t.btn_buscar_en) == (612, 712, 80, 28)
    assert _perto(g(t.btn_traduzir), (347, 755, 298, 28), 8)
    for b in (t.btn_modificados, t.btn_traduzir):  # centrados no quadro
        assert abs(g(b)[0] + g(b)[2] / 2 - (72 + 424)) <= 1


def test_medidas_da_aba_2(tela_medida, qtbot):
    t, r = tela_medida, tela_medida._rotulos
    g = lambda w: _geo(t, w)  # noqa: E731
    t.tabview.set("Criar planilhas PMIB")
    qtbot.waitUntil(lambda: g(t.tabview)[3] == 481, timeout=2000)
    assert g(t.quadro_fichas) == (72, 287, 848, 258)
    assert g(r["fichas"])[:2] == (82, 292)
    assert g(r["fonte"]) == (82, 333, 240, 28)
    assert _perto(g(t.rb_fonte_planilha), (332, 336, 128, 22), 4)
    assert _perto(g(t.rb_fonte_pasta), (480, 336, 284, 22), 4)
    assert g(t.btn_pmib) == (82, 377, 240, 28)
    assert g(t.lbl_pmib_status)[:2] == (337, 377)
    assert g(r["destino_fichas"]) == (82, 421, 240, 28)
    assert g(t.entry_destino_fichas) == (327, 421, 280, 28)
    assert g(t.btn_buscar_fichas) == (612, 421, 80, 28)
    assert g(t.btn_template) == (82, 465, 240, 28)
    assert g(t.lbl_template_status)[:2] == (337, 465)
    assert g(r["idioma"]) == (82, 509, 240, 28)
    assert _perto(g(t.rb_pt), (332, 512, 100, 22), 4)
    assert _perto(g(t.rb_en), (452, 512, 100, 22), 4)
    assert _perto(g(r["idioma_dica"])[:2], (572, 509), 4)
    assert g(t.quadro_exec) == (72, 565, 848, 134)
    assert g(r["selecao"]) == (82, 575, 120, 28)
    assert _perto(g(t.rb_todos), (212, 578, 112, 22), 4)
    assert _perto(g(t.rb_selecionar), (344, 578, 170, 22), 4)
    assert g(r["saida"]) == (82, 613, 120, 28)
    assert _perto(g(t.rb_apenas), (212, 616, 181, 22), 4)
    assert _perto(g(t.rb_com_pastas), (413, 616, 185, 22), 4)
    assert _perto(g(t.btn_criar_fichas), (409, 661, 174, 28), 8)


def test_medidas_da_aba_3(tela_medida, qtbot):
    t, r = tela_medida, tela_medida._rotulos
    g = lambda w: _geo(t, w)  # noqa: E731
    t.tabview.botoes["Excluir Duplicados"].click()
    qtbot.waitUntil(lambda: g(t.tabview)[3] == 261, timeout=2000)
    # Rótulo centrado (lá 431 de largura; o texto do Qt sai uns px mais curto).
    x, y, w, h = g(r["limpeza"])
    assert (y, h) == (297, 28) and abs(w - 431) <= 16 and abs(x + w / 2 - (280 + 431 / 2)) <= 1
    assert g(r["clean"]) == (62, 353, 240, 28)
    assert g(t.entry_clean) == (307, 353, 280, 28)
    assert g(t.btn_buscar_clean) == (592, 353, 80, 28)
    assert g(t.btn_exec_clean) == (346, 419, 300, 40)
    # E volta ao tamanho da aba 1
    t.tabview.set("Processar PDMs")
    qtbot.waitUntil(lambda: g(t.tabview)[3] == 571, timeout=2000)
