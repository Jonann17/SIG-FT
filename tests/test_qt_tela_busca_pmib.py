import threading
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt

from sigft.app import backends
from sigft.app_qt import estilo
from sigft.app_qt.views import busca_pmib as tela_mod

RESULTADOS = [
    {"codigo_itaipu": "4500063671.0012", "coluna_match": "DESCRIÇÃO",
     "amostra": "ROLAMENTO DE ESFERAS 6205-2RS",
     "caminho_arquivo": "/fichas/UG01/4500063671.0012.xlsx", "caminho_pasta": "/fichas/UG01"},
    {"codigo_itaipu": "4500063671.0047", "coluna_match": "MARCA/MODELO", "amostra": "",
     "caminho_arquivo": "/fichas/UG07/" + "x" * 150 + ".xlsx", "caminho_pasta": "/fichas/UG07"},
]


class BuscadorFalso:
    def __init__(self, resultados=None, falha=None):
        self.resultados = RESULTADOS if resultados is None else resultados
        self.falha = falha
        self.chamadas = []
        self.liberar = threading.Event()
        self.liberar.set()

    def executar_busca(self, pasta_raiz, tipo_busca, termo_busca, coluna_especifica=None, callback_log=None):
        self.chamadas.append(dict(pasta_raiz=pasta_raiz, tipo_busca=tipo_busca,
                                  termo_busca=termo_busca, coluna_especifica=coluna_especifica))
        callback_log("Lendo 2 planilhas...")
        self.liberar.wait(3)
        if self.falha:
            raise self.falha
        return self.resultados


@pytest.fixture
def tela(qt_interface, qtbot, monkeypatch):
    t = tela_mod.ModuloBuscaPMIB()
    qtbot.addWidget(t)
    t.janelas = []
    monkeypatch.setattr(t, "_mostrar_janela_resultados", lambda r: t.janelas.append(
        (r, threading.current_thread() is threading.main_thread())))
    return t


def _com_backend(monkeypatch, buscador):
    monkeypatch.setattr(backends, "search_pmib_backend", SimpleNamespace(PMIBSearcher=lambda: buscador))
    return buscador


def _preencher(tela, pasta="/fichas", termo="  rolamento  "):
    tela.entry_pasta.setText(pasta)
    tela.entry_termo.setText(termo)


def test_monta_com_os_textos(tela):
    assert tela.label_titulo.text() == "Search PMIB (Buscador de Sobressalentes)"
    assert tela.rotulo_secao.text() == "1. Parâmetros de Busca"
    assert [r.text() for r in tela.rotulos_linha] == [
        "Pasta Raiz da Busca:", "Modo de Busca:", "Termo Procurado:"]
    assert tela.btn_pasta.text() == "Buscar Pasta"
    assert tela.rb_direc.text() == "Direcionada (Rápida)" and tela.rb_direc.isChecked()
    assert tela.rb_geral.text() == "Generalista (Lenta)" and not tela.rb_geral.isChecked()
    assert tela.rotulo_coluna.text() == "Coluna Alvo:"
    assert [tela.opt_coluna.itemText(i) for i in range(tela.opt_coluna.count())] == [
        "DESCRIÇÃO", "CÓDIGO DO MATERIAL", "CÓDIGO CMI", "MARCA/MODELO", "CÓDIGO PMIB"]
    assert tela.opt_coluna.currentText() == "DESCRIÇÃO"
    assert tela.entry_termo.placeholderText() == "Digite o que deseja encontrar..."
    assert tela.btn_search.text() == estilo.mono("🔍 PESQUISAR")
    assert tela.tipo_busca == "direcionada"


def test_generalista_desliga_a_coluna(tela):
    tela.rb_geral.click()
    assert tela.tipo_busca == "generalista"
    assert not tela.opt_coluna.isEnabled()
    tela.rb_direc.click()
    assert tela.tipo_busca == "direcionada"
    assert tela.opt_coluna.isEnabled()


def test_buscar_pasta_preenche_o_campo(tela, monkeypatch):
    pedidos = []

    def perguntar(chave, categoria, **k):
        pedidos.append((chave, categoria, k))
        return "/srv/fichas"

    monkeypatch.setattr(tela_mod.file_dialogs, "ask_directory", perguntar)
    tela.btn_pasta.click()
    assert tela.entry_pasta.text() == "/srv/fichas"
    assert pedidos == [("search.pasta_raiz", "pasta", {"titulo": "Selecione a Pasta Raiz de Busca"})]


def test_buscar_pasta_cancelado_nao_apaga(tela, monkeypatch):
    tela.entry_pasta.setText("/antes")
    monkeypatch.setattr(tela_mod.file_dialogs, "ask_directory", lambda *a, **k: "")
    tela.btn_pasta.click()
    assert tela.entry_pasta.text() == "/antes"


@pytest.mark.parametrize("pasta, termo, mensagem", [
    ("", "rolamento", "Selecione a pasta raiz antes de pesquisar."),
    ("/fichas", "   ", "Digite o termo que deseja pesquisar."),
])
def test_campos_vazios_avisam(tela, monkeypatch, pasta, termo, mensagem):
    buscador = _com_backend(monkeypatch, BuscadorFalso())
    avisos = []
    monkeypatch.setattr(tela_mod.QMessageBox, "warning", staticmethod(lambda *a: avisos.append(a[1:])))
    _preencher(tela, pasta, termo)
    tela.btn_search.click()
    assert avisos == [("Atenção", mensagem)]
    assert buscador.chamadas == [] and tela.btn_search.isEnabled()


def test_busca_completa(tela, qtbot, monkeypatch):
    buscador = BuscadorFalso()
    buscador.liberar.clear()
    _com_backend(monkeypatch, buscador)
    tela.console.appendPlainText("> busca anterior")
    _preencher(tela)
    tela.rb_geral.click()
    tela.opt_coluna.setCurrentText("MARCA/MODELO")
    tela.btn_search.click()
    assert not tela.btn_search.isEnabled()          # desabilita NO CLIQUE
    assert "busca anterior" not in tela.console.toPlainText()
    buscador.liberar.set()
    qtbot.waitUntil(lambda: bool(tela.janelas), timeout=3000)
    qtbot.waitUntil(tela.btn_search.isEnabled, timeout=2000)
    assert buscador.chamadas == [dict(pasta_raiz="/fichas", tipo_busca="generalista",
                                      termo_busca="rolamento", coluna_especifica="MARCA/MODELO")]
    # A janela abre na thread da interface, com os resultados do serviço.
    assert tela.janelas == [(RESULTADOS, True)]
    qtbot.waitUntil(lambda: "> Lendo 2 planilhas..." in tela.console.toPlainText(), timeout=2000)


def test_erro_do_servico_vira_log(tela, qtbot, monkeypatch):
    _com_backend(monkeypatch, BuscadorFalso(falha=OSError("pasta sumiu")))
    _preencher(tela)
    tela.btn_search.click()
    qtbot.waitUntil(lambda: "> Erro Crítico: pasta sumiu" in tela.console.toPlainText(), timeout=3000)
    qtbot.waitUntil(tela.btn_search.isEnabled, timeout=2000)
    assert tela.janelas == []


def test_backend_que_nao_carregou_nao_comeca(tela, monkeypatch):
    monkeypatch.setattr(backends, "search_pmib_backend", None)
    monkeypatch.setattr(backends, "falhas", {"search_pmib_backend": ImportError("sem pandas")})
    avisos = []
    monkeypatch.setattr(tela_mod.ModuloBuscaPMIB, "backend",
                        lambda self, nome: avisos.append(nome))
    _preencher(tela)
    tela.btn_search.click()
    assert avisos == ["search_pmib_backend"]
    assert tela.btn_search.isEnabled()


# --- janela de resultados ------------------------------------------------------------
@pytest.fixture
def janela(qt_interface, qtbot):
    t = tela_mod.ModuloBuscaPMIB()
    qtbot.addWidget(t)
    t._mostrar_janela_resultados(RESULTADOS)
    j = t.janela_resultados
    j.tela = t
    return j


def test_sem_resultados_avisa(qt_interface, qtbot, monkeypatch):
    t = tela_mod.ModuloBuscaPMIB()
    qtbot.addWidget(t)
    infos = []
    monkeypatch.setattr(tela_mod.QMessageBox, "information", staticmethod(lambda *a: infos.append(a[1:])))
    t._mostrar_janela_resultados([])
    assert infos == [("Resultados", "Nenhum material encontrado com esses parâmetros.")]
    assert t.janela_resultados is None


def test_janela_de_resultados(janela):
    assert janela.windowTitle() == "Resultados da Busca: 2 encontrados"
    assert janela.isVisible()
    assert janela.windowModality() == Qt.WindowModality.ApplicationModal
    assert (janela.width(), janela.height()) == (900, 650)
    assert janela.rotulo_titulo.text() == "Resultados Encontrados"
    assert len(janela.cartoes) == 2
    c1, c2 = janela.cartoes
    assert c1.campo_pmib.text() == "PMIB: 4500063671.0012" and c1.campo_pmib.isReadOnly()
    assert c1.rotulo_coluna.text() == "| Match na coluna: DESCRIÇÃO"
    assert c1.texto_caminho.toPlainText() == estilo.mono("📂 Caminho:") + "\n/fichas/UG01/4500063671.0012.xlsx"
    assert c1.texto_amostra.toPlainText() == estilo.mono("🔎 Amostra: ") + "ROLAMENTO DE ESFERAS 6205-2RS"
    assert c1.texto_caminho.isReadOnly() and c1.texto_amostra.isReadOnly()
    # Sem amostra, sem a caixa da amostra.
    assert c2.texto_amostra is None
    assert c1.botao_arquivo.text() == estilo.mono("📄 Abrir Arquivo")
    assert c1.botao_pasta.text() == estilo.mono("📁 Abrir Pasta")
    assert janela.botao_fechar.text() == "Fechar"


def test_altura_das_caixas_e_a_da_tela_antiga(janela):
    c1, c2 = janela.cartoes
    # _altura_do_textbox: 20 px por linha (90 caracteres) + 12 de folga, mínimo 35.
    assert c1.texto_caminho.height() == 52
    assert c1.texto_amostra.height() == 35
    assert c2.texto_caminho.height() == 3 * 20 + 12
    assert tela_mod._altura_do_textbox("a" * 91) == 52
    assert tela_mod._altura_do_textbox("") == 35


def test_campos_vazios_viram_na(janela, qtbot):
    janela.tela._mostrar_janela_resultados([{}])
    j = janela.tela.janela_resultados
    c = j.cartoes[0]
    assert c.campo_pmib.text() == "PMIB: N/A"
    assert c.rotulo_coluna.text() == "| Match na coluna: N/A"
    assert c.texto_amostra is None


def test_abrir_arquivo_e_pasta(janela, monkeypatch, qtbot):
    abertos = []
    monkeypatch.setattr(tela_mod.os.path, "exists", lambda c: True)
    monkeypatch.setattr(tela_mod.plataforma, "abrir_no_sistema", abertos.append)
    c1 = janela.cartoes[0]
    c1.botao_arquivo.click()
    c1.botao_pasta.click()
    assert abertos == ["/fichas/UG01/4500063671.0012.xlsx", "/fichas/UG01"]
    qtbot.waitUntil(lambda: "> Abrindo pasta: /fichas/UG01" in janela.tela.console.toPlainText(),
                    timeout=2000)
    assert "> Abrindo arquivo: 4500063671.0012.xlsx" in janela.tela.console.toPlainText()


def test_arquivo_ou_pasta_que_sumiu(janela, monkeypatch):
    erros, abertos = [], []
    monkeypatch.setattr(tela_mod.os.path, "exists", lambda c: False)
    monkeypatch.setattr(tela_mod.plataforma, "abrir_no_sistema", abertos.append)
    monkeypatch.setattr(tela_mod.QMessageBox, "critical", staticmethod(lambda *a: erros.append(a[1:])))
    janela.cartoes[1].botao_arquivo.click()
    janela.cartoes[1].botao_pasta.click()
    assert erros == [("Erro", "Arquivo não encontrado."), ("Erro", "Pasta não encontrada.")]
    assert abertos == []


def test_fechar(janela, qtbot):
    tela = janela.tela
    janela.botao_fechar.click()
    assert not janela.isVisible()
    # WA_DeleteOnClose: a tela não fica apontando para uma janela destruída.
    qtbot.waitUntil(lambda: tela.janela_resultados is None, timeout=2000)


def test_dados_da_ficha_nao_ganham_seletor_de_texto(qt_interface, qtbot):
    # `mono` só nos rótulos com emoji: "≤", "→" e "⌀" da ficha chegam intactos
    # (quem copia a amostra não leva caractere invisível) e a altura é a da conta antiga.
    t = tela_mod.ModuloBuscaPMIB()
    qtbot.addWidget(t)
    amostra = "TORQUE ≤ 40 N·m → ⌀ 25 MM"
    caminho = "/fichas/≤ 2020/→ ficha.xlsx"
    t._mostrar_janela_resultados([{"amostra": amostra, "caminho_arquivo": caminho}])
    c = t.janela_resultados.cartoes[0]
    assert c.texto_amostra.toPlainText().endswith(amostra)
    assert c.texto_caminho.toPlainText().endswith("\n" + caminho)
    assert "\ufe0e" not in c.texto_amostra.toPlainText().split(": ", 1)[1]
    assert "\ufe0e" not in c.texto_caminho.toPlainText().split("\n", 1)[1]
    assert c.texto_amostra.height() == tela_mod._altura_do_textbox(f"🔎 Amostra: {amostra}")


# --- geometria -------------------------------------------------------------------------
@pytest.fixture
def com_folha(qt_interface):
    anterior = qt_interface.styleSheet()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    yield
    qt_interface.setStyleSheet(anterior)


def test_medidas_iguais_as_do_interface_antiga(com_folha, qtbot):
    # 2026-10-20: medida do sistema visual (botão/campo 32, título 22, borda 1); a CTk saiu em 2026-10-15.
    # Medidas da tela antiga (interface antiga, janela 1280x850, sondadas com
    # winfo_*), já na origem da tela Qt (que começa no x=277 da janela e inclui
    # o padx/pady=20 do `show_frame`): título em (40, 30); quadro dos parâmetros
    # em (40, 79) com 167 de altura; linhas em y 127/165/203; console de 271 a 810.
    t = tela_mod.ModuloBuscaPMIB()
    qtbot.addWidget(t)
    t.resize(1003, 850)
    t.show()
    qtbot.waitExposed(t)

    def geo(w):
        p = w.mapTo(t, w.rect().topLeft())
        return p.x(), p.y(), w.width(), w.height()

    assert geo(t.label_titulo)[:2] == (40, 30)
    assert geo(t.content)[1] == 72
    cartao = t.rotulo_secao.parentWidget()
    assert geo(cartao) == (40, 77, 923, 179)
    assert geo(t.rotulo_secao)[:2] == (55, 87)
    assert [geo(r)[:3] for r in t.rotulos_linha] == [(55, 127, 150), (55, 169, 150), (55, 211, 150)]
    assert geo(t.entry_pasta) == (210, 125, 400, 32)
    assert geo(t.btn_pasta) == (615, 127, 100, 28)
    assert geo(t.rb_direc)[0] == 205
    assert geo(t.opt_coluna)[1:] == (167, 140, 32)
    assert geo(t.entry_termo) == (210, 209, 400, 32)
    assert geo(t.btn_search) == (625, 211, 150, 28)
    assert geo(t.console) == (40, 281, 923, 529)


def test_medidas_da_janela_de_resultados(com_folha, qtbot):
    # interface antiga: título (y 15, 28 de altura, centrado); quadro rolável (20, 48) de 860x539;
    # cartões a partir de (36, 62) com 817 de largura; "Fechar" (375, 602) 150x28.
    t = tela_mod.ModuloBuscaPMIB()
    qtbot.addWidget(t)
    t._mostrar_janela_resultados(RESULTADOS * 2)
    j = t.janela_resultados
    qtbot.waitExposed(j)
    # Quatro cartões não cabem: a barra de rolagem aparece (depois do layout).
    qtbot.waitUntil(j.area.verticalScrollBar().isVisible, timeout=2000)

    def geo(w):
        p = w.mapTo(j, w.rect().topLeft())
        return p.x(), p.y(), w.width(), w.height()

    assert geo(j.rotulo_titulo)[1] == 15
    assert geo(j.area) == (20, 48, 860, 539)
    assert geo(j.botao_fechar) == (375, 602, 150, 28)
    c1, c2 = j.cartoes[:2]
    assert geo(c1)[:3] == (36, 62, 817)
    assert geo(c1.campo_pmib) == (46, 72, 450, 28)
    assert geo(c1.rotulo_coluna)[:2] == (501, 72)
    assert geo(c1.texto_caminho) == (46, 107, 797, 52)
    assert geo(c1.texto_amostra)[:2] == (46, 163)
    assert geo(c1.botao_arquivo) == (51, 203, 120, 28)
    assert geo(c1.botao_pasta) == (181, 203, 120, 28)
    assert geo(c1)[3] == 179
    assert geo(c2)[1] == 257
    assert geo(c2.botao_arquivo)[1] == geo(c2.texto_caminho)[1] + 72 + 2


def test_menu_de_coluna_pinta_com_a_paleta_do_tema(qt_interface, qtbot):
    # 2026-10-20: o menu não tem mais cor própria (era o #3A3A3A/#454545 da tela
    # antiga): o da coluna e o padrão pintam igual, com a paleta do tema.
    from sigft.app_qt.widgets import controles

    t = tela_mod.ModuloBuscaPMIB()
    qtbot.addWidget(t)
    padrao = controles.MenuDeOpcoes(["a"])
    qtbot.addWidget(padrao)
    fundo = estilo.paleta_atual()["superficie_alta"].lower()
    for menu in (t.opt_coluna, padrao):
        menu.resize(140, 28)
        img = menu.grab().toImage()
        assert img.pixelColor(20, 3).name() == fundo
        assert img.pixelColor(menu.width() - 4, 3).name() == fundo
