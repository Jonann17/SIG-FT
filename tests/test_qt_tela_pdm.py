"""Tela "Planilhas PMIB" (PDM) na interface Qt.

Backends, serviços e IA são dublês: o que se prova é a TELA -- textos, a
forma (sem abas desde 2026-10-21: a planilha de PDMs em cima e a criação das
planilhas PMIB embaixo), as validações, os argumentos que chegam aos serviços,
as mensagens do fim (pela thread da interface), a janela de seleção dos
códigos e a geometria.
"""
import sys
import threading
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel

from sigft.app import backends
from sigft.app_qt.views import pdm as tela_mod


# ---------------------------------------------------------------------------
# Dublês e ajudas
# ---------------------------------------------------------------------------
class PdmFalso:
    """O `pdm_backend` de mentira: registra cada chamada."""

    def __init__(self, *, codigos=None, erro_codigos=None, dados_pastas=("d1",)):
        self.chamadas = []
        self.codigos, self.erro_codigos = codigos or ["PMIB-1", "PMIB-2", "PMIB-3"], erro_codigos
        self.dados_pastas = list(dados_pastas)
        self.threads = []
        self.segurar = None   # threading.Event: segura `processar_pastas_fichas`

    def _reg(self, nome, *a, **k):
        self.chamadas.append((nome, a, k))
        self.threads.append(threading.current_thread() is threading.main_thread())

    def codigos_pmib_da_lista(self, status):
        self._reg("codigos", status)
        if self.erro_codigos:
            raise self.erro_codigos
        return list(self.codigos)

    def processar_pastas_fichas(self, status, destino, lista_sel, criar_subpastas=True):
        self._reg("pastas", status, destino, lista_sel, criar_subpastas=criar_subpastas)
        if self.segurar is not None:
            self.segurar.wait(3)
        return list(self.dados_pastas), "3 pastas preparadas"

    def aplicar_templates_fichas_da_planilha(self, dados, catalogo, template, log_callback=None, retry_lock=None,
                                             idioma="pt", traduzir=None, pasta_traducao=None):
        self._reg("templates_planilha", dados, catalogo, template, retry_lock=retry_lock, idioma=idioma,
                  traduzir=traduzir)
        log_callback("montando...")
        return "3 fichas da planilha", []


@pytest.fixture
def pdm(monkeypatch):
    falso = PdmFalso()
    monkeypatch.setattr(backends, "pdm_backend", falso)
    return falso


@pytest.fixture
def tela(qt_interface, qtbot, monkeypatch):
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
    assert r["sam_gm"].text() == "Planilha de PDMs (SAM-GM):"
    assert tela.btn_sam_gm.text() == "Selecionar"
    assert tela.lbl_sam_gm_status.text() == "Nenhum arquivo selecionado"
    assert r["fichas"].text() == "Configuração das Fichas PMIB"
    assert tela.btn_pmib.text() == "Selecionar STATUS_PMIB (.xlsx)"
    assert tela.lbl_pmib_status.text() == "Nenhum arquivo selecionado"
    assert r["destino_fichas"].text() == "Pasta Destino das Fichas:"
    assert tela.btn_template.text() == "Selecionar Template (.xlsx)"
    assert tela.lbl_template_status.text() == "Nenhum arquivo selecionado"
    assert r["idioma"].text() == "Idioma da ficha:"
    assert tela.rb_pt.text() == "Português" and tela.rb_pt.isChecked() and tela.rb_en.text() == "English"
    assert r["idioma_dica"].text() == IDIOMA_DICA
    assert r["selecao"].text() == "Seleção de Itens:" and r["saida"].text() == "Formato de Saída:"
    assert tela.rb_todos.text() == "Todos da Lista" and tela.rb_todos.isChecked()
    assert tela.rb_selecionar.text() == "Selecionar Manualmente"
    assert tela.rb_apenas.text() == "Apenas Planilhas (Padrão)" and tela.rb_apenas.isChecked()
    assert tela.rb_com_pastas.text() == "Criar Subpastas + Planilhas"
    assert tela.btn_criar_fichas.text() == "Executar: Criar Fichas PMIB"
    # Os valores dos grupos de rádio (os StringVar de lá)
    assert (tela.idioma_ficha.get(), tela.modo_pmib.get(), tela.modo_saida_fichas.get()) == (
        "pt", "todos", "apenas_planilhas")
    assert tela.entry_destino_fichas.text() == ""


IDIOMA_DICA = "(English traduz as características da planilha)"

# O que saiu em 2026-10-21 (pedido do Luan): as abas "Processar PDMs" e
# "Excluir Duplicados", a pasta de PDMs Modificados e a escolha da fonte.
REMOVIDOS = ("tabview", "entry_dest", "btn_sel_destino", "entry_pdms_itaipu", "btn_buscar_itaipu",
             "btn_regenerar", "btn_from_itaipu", "btn_modificados", "modo_proc", "btn_traduzir",
             "entry_destino_en", "btn_buscar_en", "fonte_perguntas", "rb_fonte_pasta",
             "entry_clean", "btn_exec_clean")


def test_a_tela_nao_tem_abas_nem_nada_dos_pdms_modificados(tela):
    from sigft.app_qt.widgets.abas import Abas

    assert [nome for nome in REMOVIDOS if hasattr(tela, nome)] == []
    assert tela.findChildren(Abas) == []
    textos = " ".join(w.text() for w in tela.findChildren(QLabel))
    for proibido in ("Modificados", "From Itaipu", "Duplicados", "Limpeza"):
        assert proibido not in textos


def test_a_criacao_fica_num_cartao_abaixo_da_planilha(tela):
    """Sem abas, a criação das planilhas PMIB vem logo abaixo do painel da
    planilha, num cartão com os dois quadros (configuração e execução)."""
    corpo = tela.cartao_config.parentWidget().layout()
    ordem = [corpo.itemAt(i).widget() for i in range(corpo.count()) if corpo.itemAt(i).widget()]
    assert ordem == [tela.cartao_config, tela.cartao_fichas]
    for quadro in (tela.quadro_fichas, tela.quadro_exec):
        assert quadro.parentWidget() is tela.cartao_fichas


def test_a_tela_nao_preenche_pasta_padrao_nenhuma(tela):
    """A pasta padrão que vinha preenchida era a dos PDMs Modificados."""
    assert not hasattr(tela_mod, "prefs")


def test_radios_trocam_o_valor(tela):
    tela.rb_en.click()
    tela.rb_selecionar.click()
    tela.rb_com_pastas.click()
    assert (tela.idioma_ficha.get(), tela.modo_pmib.get(), tela.modo_saida_fichas.get()) == (
        "en", "selecionar", "com_pastas")
    assert not tela.rb_pt.isChecked()
    tela.idioma_ficha.set("pt")
    assert tela.rb_pt.isChecked() and tela.idioma_ficha.get() == "pt"


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
        assert rotulo.property("papel") == "ok"  # cor da folha pelo papel (2026-10-20)
    for botao in (tela.btn_sam_gm, tela.btn_pmib, tela.btn_template):
        assert botao.property("variante") == "primario"


def test_cancelar_o_seletor_de_arquivo_nao_mexe_em_nada(tela, monkeypatch):
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "")
    for botao in (tela.btn_sam_gm, tela.btn_pmib, tela.btn_template):
        botao.click()
    assert tela.path_sam_gm == tela.path_status_pmib == tela.path_template == ""
    assert tela.lbl_pmib_status.text() == "Nenhum arquivo selecionado"
    assert tela.btn_pmib.property("variante") != "primario"

def test_seletor_de_pasta(tela, monkeypatch):
    chamadas = []

    def falso(chave, categoria, **k):
        chamadas.append((chave, categoria, k.get("titulo")))
        return f"/escolhida/{chave}"

    monkeypatch.setattr(tela_mod.file_dialogs, "ask_directory", falso)
    tela.btn_buscar_fichas.click()
    assert chamadas == [("pdm.destino_fichas", "pasta", "Pasta onde as fichas serão criadas")]
    assert tela.entry_destino_fichas.text() == "/escolhida/pdm.destino_fichas"


def test_cancelar_a_pasta_mantem_o_caminho_escolhido(tela, monkeypatch):
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_directory", lambda *a, **k: "")
    tela.entry_destino_fichas.setText("/ja/escolhida")
    tela.btn_buscar_fichas.click()
    assert tela.entry_destino_fichas.text() == "/ja/escolhida"


# ---------------------------------------------------------------------------
# Criar planilhas PMIB
# ---------------------------------------------------------------------------
def _preencher(tela, *, planilha="/d/s.xlsx", status="/d/_STATUS_PMIB.xlsx", destino="/fichas",
               template="/d/T.xlsx"):
    tela.path_sam_gm = planilha
    tela.path_status_pmib = status
    tela.entry_destino_fichas.setText(destino)
    tela.path_template = template


@pytest.mark.parametrize("campos, mensagem", [
    ({"planilha": ""}, "Selecione a planilha de PDMs no painel de cima."),
    ({"status": ""}, "Por favor, busque o arquivo STATUS_PMIB na tela."),
    ({"destino": ""}, "Por favor, busque a Pasta Destino das Fichas na tela."),
    ({"template": ""}, "Por favor, busque o Template Ficha Técnica na tela."),
])
def test_criar_fichas_valida(tela, pdm, campos, mensagem):
    _preencher(tela, **campos)
    tela.btn_criar_fichas.click()
    assert tela.avisos == [("aviso", "Aviso", mensagem, True)] and pdm.chamadas == []


def test_criar_fichas_da_planilha(tela, qtbot, pdm, monkeypatch):
    carregados = []
    monkeypatch.setattr(tela_mod.pdm_catalogo, "carregar", lambda p: carregados.append(p) or "CATALOGO")
    _preencher(tela)
    tela.btn_criar_fichas.click()
    assert _esperar_aviso(tela, qtbot) == (
        "info", "Fim", "Processo de criação de fichas finalizado.\n\n3 fichas da planilha", False)
    assert carregados == ["/d/s.xlsx"]
    assert pdm.chamadas == [
        ("pastas", ("/d/_STATUS_PMIB.xlsx", "/fichas", None), {"criar_subpastas": False}),
        ("templates_planilha", (["d1"], "CATALOGO", "/d/T.xlsx"),
         {"retry_lock": tela.perguntar_retry_excel, "idioma": "pt", "traduzir": None}),
    ]
    assert pdm.threads == [False, False]
    qtbot.waitUntil(lambda: ">>> Processo de criação de fichas finalizado!" in _texto(tela), timeout=2000)
    texto = _texto(tela)
    ordem = ["> Lendo a planilha de PDMs...", "> Preparando diretórios (Modo: Apenas Planilhas)...",
             "> 3 pastas preparadas", "> 3 fichas da planilha", "> >>> Processo de criação de fichas finalizado!"]
    assert [texto.index(x) for x in ordem] == sorted(texto.index(x) for x in ordem)


def test_criar_fichas_em_ingles_traduz_pela_planilha(tela, qtbot, pdm, monkeypatch):
    """[2026-10-21] Sem aviso: a ficha em inglês sai da planilha, e a tela
    entrega ao serviço o motor de tradução padrão (trocável)."""
    pedidos = []

    def motor_padrao(api_key=None, callbacks=None):
        pedidos.append((api_key, threading.current_thread() is threading.main_thread()))
        callbacks.log("motor pronto")
        return "MOTOR"

    _modulo_falso(monkeypatch, "traducao_pdm", motor_padrao=motor_padrao)
    monkeypatch.setattr(tela_mod.pdm_catalogo, "carregar", lambda p: "CAT")
    _preencher(tela)
    tela.rb_en.click()
    tela.btn_criar_fichas.click()
    tela.rb_pt.click()  # mudar depois do clique não muda o lote
    assert _esperar_aviso(tela, qtbot)[:3] == (
        "info", "Fim", "Processo de criação de fichas finalizado.\n\n3 fichas da planilha")
    assert pedidos == [(None, False)]   # sem api_key: a do provedor escolhido; na tarefa
    assert pdm.chamadas[1] == ("templates_planilha", (["d1"], "CAT", "/d/T.xlsx"),
                               {"retry_lock": tela.perguntar_retry_excel, "idioma": "en", "traduzir": "MOTOR"})
    qtbot.waitUntil(lambda: "motor pronto" in _texto(tela), timeout=2000)


def test_criar_fichas_em_portugues_nao_monta_o_motor(tela, qtbot, pdm, monkeypatch):
    _modulo_falso(monkeypatch, "traducao_pdm", motor_padrao=lambda **k: pytest.fail("nao traduz"))
    monkeypatch.setattr(tela_mod.pdm_catalogo, "carregar", lambda p: "CAT")
    _preencher(tela)
    tela.btn_criar_fichas.click()
    _esperar_aviso(tela, qtbot)
    assert pdm.chamadas[1][2]["traduzir"] is None and pdm.chamadas[1][2]["idioma"] == "pt"


def test_criar_fichas_com_subpastas(tela, qtbot, pdm, monkeypatch):
    monkeypatch.setattr(tela_mod.pdm_catalogo, "carregar", lambda p: "CAT")
    _preencher(tela)
    tela.rb_com_pastas.click()
    tela.btn_criar_fichas.click()
    tela.rb_apenas.click()  # mudar depois do clique não muda o lote
    _esperar_aviso(tela, qtbot)
    assert pdm.chamadas[0] == ("pastas", ("/d/_STATUS_PMIB.xlsx", "/fichas", None), {"criar_subpastas": True})
    qtbot.waitUntil(lambda: "> Preparando diretórios (Modo: Com Pastas)..." in _texto(tela), timeout=2000)


def test_sem_backend_avisa_e_nao_roda(tela, monkeypatch):
    monkeypatch.setattr(backends, "pdm_backend", None)
    avisos = []
    monkeypatch.setattr(tela_mod.ModuleFrame, "backend", lambda self, nome: avisos.append(nome))
    _preencher(tela)
    tela.btn_criar_fichas.click()
    assert avisos == ["pdm_backend"] and tela.btn_criar_fichas.isEnabled()


def test_botao_fica_desligado_enquanto_a_tarefa_roda(tela, qtbot, pdm, monkeypatch):
    monkeypatch.setattr(tela_mod.pdm_catalogo, "carregar", lambda p: "CAT")
    pdm.segurar = threading.Event()
    _preencher(tela)
    tela.btn_criar_fichas.click()
    assert not tela.btn_criar_fichas.isEnabled()
    pdm.segurar.set()
    qtbot.waitUntil(tela.btn_criar_fichas.isEnabled, timeout=3000)


def test_criar_fichas_planilha_ilegivel_para_antes_das_pastas(tela, qtbot, pdm, monkeypatch):
    def carregar(p):
        raise ValueError("aba SAM-GM não encontrada")

    monkeypatch.setattr(tela_mod.pdm_catalogo, "carregar", carregar)
    _preencher(tela)
    tela.btn_criar_fichas.click()
    assert _esperar_aviso(tela, qtbot) == (
        "erro", "Erro", "Não consegui ler a planilha de PDMs:\naba SAM-GM não encontrada", False)
    assert pdm.chamadas == []
    qtbot.waitUntil(lambda: "> ERRO ao ler a planilha de PDMs: aba SAM-GM" in _texto(tela), timeout=2000)


def test_criar_fichas_sem_codigo_processado(tela, qtbot, pdm, monkeypatch):
    monkeypatch.setattr(tela_mod.pdm_catalogo, "carregar", lambda p: "CAT")
    pdm.dados_pastas = []
    _preencher(tela)
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
    monkeypatch.setattr(tela_mod.dialogos_selecao, "SelecaoMultiplaDialog",
                        lambda parent=None, **kw: SelecaoFalsa(parent, escolha=escolha, **kw))


def test_criar_fichas_selecionando_os_codigos(tela, qtbot, pdm, monkeypatch):
    monkeypatch.setattr(tela_mod.pdm_catalogo, "carregar", lambda p: "CAT")
    _selecao_falsa(monkeypatch, ["PMIB-2"])
    _preencher(tela)
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
    _preencher(tela)
    tela.rb_selecionar.click()
    tela.btn_criar_fichas.click()
    qtbot.waitUntil(lambda: "> Seleção manual de códigos cancelada." in _texto(tela), timeout=2000)
    assert [c[0] for c in pdm.chamadas] == ["codigos"] and tela.avisos == []
    assert tela.btn_criar_fichas.isEnabled()


def test_criar_fichas_status_pmib_sem_coluna(tela, pdm):
    pdm.erro_codigos = ValueError("Coluna 'CÓDIGO PMIB' não encontrada")
    _preencher(tela)
    tela.rb_selecionar.click()
    tela.btn_criar_fichas.click()
    assert tela.avisos == [("erro", "Erro", "Coluna 'CÓDIGO PMIB' não encontrada", True)]
    assert [c[0] for c in pdm.chamadas] == ["codigos"]


def test_criar_fichas_status_pmib_ilegivel(tela, pdm):
    pdm.erro_codigos = OSError("arquivo corrompido")
    _preencher(tela)
    tela.rb_selecionar.click()
    tela.btn_criar_fichas.click()
    assert tela.avisos == [("erro", "Erro", "Ocorreu um erro ao ler o STATUS_PMIB:\narquivo corrompido", True)]


def test_janela_real_de_selecao_confirma_e_esc_nao_descarta(tela, qtbot, pdm, monkeypatch):
    """A janela de verdade: Esc não fecha (não perde os códigos marcados, e o Tk
    não tinha tecla), "Confirmar Seleção" devolve os marcados."""
    monkeypatch.setattr(tela_mod.pdm_catalogo, "carregar", lambda p: "CAT")
    _preencher(tela)
    tela.rb_selecionar.click()
    vistos = {}

    def mexer():
        dlg = next(w for w in tela.findChildren(tela_mod.dialogos_selecao.SelecaoMultiplaDialog) if w.isVisible())
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
    # Revisão final: o bloqueio do Esc mora no diálogo compartilhado.
    assert not hasattr(tela_mod, "_SelecaoDeCodigos")


def test_janela_real_de_selecao_fechada_no_x_cancela(tela, qtbot, pdm):
    _preencher(tela)
    tela.rb_selecionar.click()

    def fechar():
        dlg = next(w for w in tela.findChildren(tela_mod.dialogos_selecao.SelecaoMultiplaDialog) if w.isVisible())
        dlg.listbox.item(0).setSelected(True)
        dlg.close()

    QTimer.singleShot(50, fechar)
    tela.btn_criar_fichas.click()
    qtbot.waitUntil(lambda: "> Seleção manual de códigos cancelada." in _texto(tela), timeout=2000)
    assert [c[0] for c in pdm.chamadas] == ["codigos"]



# ---------------------------------------------------------------------------
# Geometria
# ---------------------------------------------------------------------------
@pytest.fixture
def tela_medida(qt_interface, qtbot, monkeypatch):
    from sigft.app_qt import estilo

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


# A única altura que depende da FONTE é a do título (Roboto 24 negrito: 29 px
# aqui e na interface antiga), e ela empurra tudo o que vem abaixo. As outras alturas, as
# larguras e os x são fixos (rótulos de 28, campos e botões com altura dada).
# Os testes de medida descontam do `y` o que o título passar de 29 -- no
# máximo 2 px --, e a tolerância fica só aí (e na altura da área, que cede o
# mesmo tanto para o console, preso embaixo).
ALTURA_TITULO_CTK = 29


def _desvio_do_titulo(t):
    desvio = t.label_titulo.height() - ALTURA_TITULO_CTK
    assert abs(desvio) <= 2, f"título com {t.label_titulo.height()} px de altura"
    return desvio


def _medidor(t):
    """`_geo` de quem fica abaixo do título, com o `y` sem o desvio da fonte dele."""
    desvio = _desvio_do_titulo(t)

    def g(w):
        x, y, largura, altura = _geo(t, w)
        return x, y - desvio, largura, altura
    return g, desvio

def test_medidas(tela_medida, qtbot):
    # [2026-10-21] Sem abas: o painel da planilha em cima e, 20 px abaixo, o
    # cartão da criação das planilhas PMIB, com os dois quadros dentro (20 px
    # de cada lado, como dentro da aba). Janela 1003x850.
    t, r = tela_medida, tela_medida._rotulos
    g, desvio = _medidor(t)
    assert _geo(t, t.label_titulo)[:2] == (40, 30)
    x, y, largura, altura = g(t.area)
    assert (x, y, largura, altura + desvio) == (40, 79, 923, 571)
    assert _geo(t, t.console) == (40, 670, 923, 150)
    # Painel da planilha
    assert g(t.cartao_config) == (46, 95, 900, 86)
    assert g(r["config"])[:2] == (61, 105)
    assert g(r["sam_gm"]) == (61, 138, 190, 28)
    assert g(t.btn_sam_gm) == (256, 138, 100, 28)
    assert g(t.lbl_sam_gm_status)[:2] == (376, 138)
    # Criação das planilhas PMIB
    assert g(t.cartao_fichas) == (46, 201, 900, 392)
    assert g(t.quadro_fichas) == (66, 211, 860, 218)
    assert g(r["fichas"])[:2] == (76, 216)
    assert g(t.btn_pmib) == (76, 257, 240, 28)
    assert g(t.lbl_pmib_status)[:2] == (331, 257)
    assert g(r["destino_fichas"]) == (76, 301, 240, 32)
    assert g(t.entry_destino_fichas) == (321, 301, 280, 32)
    assert g(t.btn_buscar_fichas) == (606, 303, 80, 28)
    assert g(t.btn_template) == (76, 349, 240, 28)
    assert g(t.lbl_template_status)[:2] == (331, 349)
    assert g(r["idioma"]) == (76, 393, 240, 28)
    assert _perto(g(t.rb_pt), (326, 396, 100, 22), 4)
    assert _perto(g(t.rb_en), (446, 396, 100, 22), 4)
    assert _perto(g(r["idioma_dica"])[:2], (566, 393), 4)
    assert g(t.quadro_exec) == (66, 449, 860, 134)
    assert g(r["selecao"]) == (76, 459, 120, 28)
    assert _perto(g(t.rb_todos), (206, 462, 111, 22), 4)
    assert _perto(g(t.rb_selecionar), (337, 462, 169, 22), 4)
    assert g(r["saida"]) == (76, 497, 120, 28)
    assert _perto(g(t.rb_apenas), (206, 500, 178, 22), 4)
    assert _perto(g(t.rb_com_pastas), (404, 500, 183, 22), 4)
    assert _perto(g(t.btn_criar_fichas), (410, 545, 172, 28), 8)
    b = t.btn_criar_fichas  # centrado no quadro
    assert abs(g(b)[0] + g(b)[2] / 2 - (66 + 430)) <= 1


NOME_LONGO = ("Lista de PDMs SAM-GM revisao final aprovada pelo cliente em setembro de 2026 "
              "- versao definitiva para fatiamento geral.xlsx")



def test_nome_de_arquivo_longo_nao_alarga_o_formulario(tela_medida, qtbot, monkeypatch):
    # Um nome de ~85 caracteres ou mais empurrava o formulário além da janela.
    # Agora o nome é elidido no rótulo e o caminho completo fica no tooltip.
    t = tela_medida
    caminho = "/dados/" + NOME_LONGO
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: caminho)
    t.btn_sam_gm.click()
    t.btn_pmib.click()
    t.btn_template.click()
    qtbot.wait(50)
    assert _geo(t, t.cartao_config)[2] == 900 and _geo(t, t.cartao_fichas)[2] == 900
    assert t.area.widget().width() == t.area.viewport().width()
    for rotulo in (t.lbl_sam_gm_status, t.lbl_pmib_status, t.lbl_template_status):
        assert rotulo.text() == NOME_LONGO and rotulo.toolTip() == caminho
        assert "…" in rotulo.texto_visivel()
        quadro = rotulo.parentWidget()
        assert rotulo.mapTo(quadro, rotulo.rect().topRight()).x() < quadro.width()


def test_escolher_de_novo_nao_acumula_folha(tela, monkeypatch):
    # Cada escolha reconstrói a folha a partir da base (não soma regra a regra).
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_open_file", lambda *a, **k: "/d/a.xlsx")
    tela.btn_sam_gm.click()
    folhas = (tela.btn_sam_gm.styleSheet(), tela.lbl_sam_gm_status.styleSheet())
    tela.btn_sam_gm.click()
    tela.btn_sam_gm.click()
    assert (tela.btn_sam_gm.styleSheet(), tela.lbl_sam_gm_status.styleSheet()) == folhas
