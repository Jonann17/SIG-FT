"""Colunas lembradas nas tabelas (2026-10-26): arrastar o cabeçalho, a borda e o
menu do botão direito, lembrados pela chave interna de cada coluna."""
from types import SimpleNamespace

from _idioma import em_idioma
from sigft.app.idioma import t
from sigft.app_qt.views import janelas
from sigft.app_qt.widgets import colunas as colunas_mod
from sigft.app_qt.widgets import dialogos_selecao as qd
from sigft.app_qt.widgets import revisao_portal
from sigft.core import prefs
from sigft.core.pmib_regras import Problema

INTERNAS = ("descricao", "original", "alvo")


def _tabela(qtbot, titulos=("Descrição", "PMIB Original", "PMIB Alvo")):
    tabela = qd.tabela_ttk([(titulo, 120, "w") for titulo in titulos])
    qtbot.addWidget(tabela)
    return tabela, colunas_mod.instalar_colunas(tabela, "teste", INTERNAS)


def _ordem(tabela):
    cabecalho = tabela.header()
    return [INTERNAS[cabecalho.logicalIndex(p)] for p in range(cabecalho.count())]


def _acao(menu, chave):
    return next(a for a in menu.actions() if a.data() == INTERNAS.index(chave))


def test_instalar_liga_o_cabecalho(qt_interface, qtbot):
    tabela, colunas = _tabela(qtbot)
    assert tabela.colunas_lembradas is colunas
    assert tabela.header().sectionsMovable()
    assert colunas.colunas == list(INTERNAS)


def test_reordenar_e_alargar_ficam_lembrados(qt_interface, qtbot):
    tabela, colunas = _tabela(qtbot)
    cabecalho = tabela.header()
    cabecalho.moveSection(cabecalho.visualIndex(2), 0)
    cabecalho.resizeSection(0, 333)
    colunas.gravar()
    nova, _ = _tabela(qtbot)
    assert _ordem(nova) == ["alvo", "descricao", "original"]
    assert nova.header().sectionSize(0) == 333
    assert not nova.esticar_colunas.ligado   # vale a largura de quem mexeu
    assert nova.header().stretchLastSection()


def test_esconder_fica_lembrado(qt_interface, qtbot):
    _tabela_velha, colunas = _tabela(qtbot)
    assert colunas.mostrar_coluna("original", False) is True
    nova, _ = _tabela(qtbot)
    assert nova.header().isSectionHidden(1)
    assert not nova.header().isSectionHidden(0)


def test_a_ultima_coluna_visivel_nao_se_esconde(qt_interface, qtbot):
    tabela, colunas = _tabela(qtbot)
    colunas.mostrar_coluna("descricao", False)
    colunas.mostrar_coluna("original", False)
    assert colunas.mostrar_coluna("alvo", False) is False
    assert not tabela.header().isSectionHidden(2)
    menu = colunas.montar_menu()
    assert not _acao(menu, "alvo").isEnabled() and _acao(menu, "alvo").isChecked()
    assert _acao(menu, "descricao").isEnabled() and not _acao(menu, "descricao").isChecked()


def test_menu_tem_cada_coluna_e_restaurar(qt_interface, qtbot):
    _tabela_teste, colunas = _tabela(qtbot)
    textos = [a.text() for a in colunas.montar_menu().actions() if not a.isSeparator()]
    assert textos == ["Descrição", "PMIB Original", "PMIB Alvo", "Restaurar colunas"]


def test_desmarcar_no_menu_esconde(qt_interface, qtbot):
    tabela, colunas = _tabela(qtbot)
    _acao(colunas.montar_menu(), "original").setChecked(False)
    assert tabela.header().isSectionHidden(1)
    assert prefs.ler_colunas("teste")[1]["visivel"] is False


def test_restaurar_volta_ao_padrao(qt_interface, qtbot):
    tabela, colunas = _tabela(qtbot)
    cabecalho = tabela.header()
    cabecalho.moveSection(cabecalho.visualIndex(2), 0)
    colunas.mostrar_coluna("descricao", False)
    menu = colunas.montar_menu()
    next(a for a in menu.actions() if a.text() == "Restaurar colunas").trigger()
    assert _ordem(tabela) == list(INTERNAS)
    assert not any(cabecalho.isSectionHidden(i) for i in range(3))
    assert prefs.ler_colunas("teste") is None
    assert tabela.esticar_colunas.ligado
    assert not cabecalho.stretchLastSection()


def test_coluna_que_sumiu_e_ignorada_e_a_nova_entra_no_fim(qt_interface, qtbot):
    prefs.gravar_colunas("teste", [{"chave": "velha", "largura": 50, "visivel": True},
                                   {"chave": "alvo", "largura": 90, "visivel": True},
                                   {"chave": "descricao", "largura": 200, "visivel": False}])
    tabela, _ = _tabela(qtbot)
    assert _ordem(tabela) == ["alvo", "descricao", "original"]
    assert tabela.header().isSectionHidden(0)
    assert not tabela.header().isSectionHidden(1)


def test_preferencia_estragada_vale_o_padrao(qt_interface, qtbot):
    prefs.gravar_colunas("teste", "lixo")
    tabela, _ = _tabela(qtbot)
    assert _ordem(tabela) == list(INTERNAS)
    assert tabela.esticar_colunas.ligado


def test_trocar_o_idioma_nao_perde_o_que_foi_guardado(qt_interface, qtbot):
    _tabela_velha, colunas = _tabela(qtbot)
    colunas.mostrar_coluna("original", False)
    with em_idioma("es"):
        nova, _ = _tabela(qtbot, titulos=(t("Descrição"), "PMIB Original", "PMIB Alvo"))
        assert nova.headerItem().text(0) != "Descrição"
        assert nova.header().isSectionHidden(1)


def test_fechar_a_janela_grava_a_largura_que_esperava(qt_interface, qtbot):
    dlg = qd.TabelaSelecaoDialog(None, colunas=("A", "B"), linhas=[(1, ("x", "y"))], modal=False,
                                 chave_colunas="teste_dialogo", colunas_internas=("a", "b"))
    qtbot.addWidget(dlg)
    dlg.tree.header().resizeSection(0, 250)
    assert dlg.colunas._gravar_depois.isActive()
    dlg.close()
    assert prefs.ler_colunas("teste_dialogo")[0] == {"chave": "a", "largura": 250, "visivel": True}


def test_tabela_sem_chave_nao_lembra_nada(qt_interface, qtbot):
    dlg = qd.TabelaSelecaoDialog(None, colunas=("A",), linhas=[(1, ("x",))], modal=False)
    qtbot.addWidget(dlg)
    assert dlg.colunas is None


def test_selecao_de_duplicadas_usa_a_chave_interna(qt_interface, qtbot):
    fila = [{"descricao": "Bomba", "pmib_original": "1", "pmib_alvo": "2"}]
    dlg = janelas.JanelaSelecaoDuplicadas(None, fila, lambda escolha: None)
    qtbot.addWidget(dlg)
    assert dlg.colunas.chave == "selecao_duplicadas"
    assert dlg.colunas.colunas == ["descricao", "pmib_original", "pmib_alvo"]


def test_selecao_de_itens_usa_o_nome_da_coluna_da_planilha(qt_interface, qtbot):
    class Linha(list):
        def to_numpy(self):
            return SimpleNamespace(tolist=lambda: list(self))

    df = SimpleNamespace(columns=["DESCRIÇÃO", 7],
                         iterrows=lambda: iter([(3, Linha(["p", 1]))]))
    dlg = janelas.JanelaSelecao(None, df, lambda escolha: None)
    qtbot.addWidget(dlg)
    assert dlg.colunas.chave == "selecao_de_itens"
    assert dlg.colunas.colunas == ["DESCRIÇÃO", "7"]


def _revisao(qtbot):
    problema = Problema(ficha="4500.1", campo="Texto breve do material", interno="Input_ShortText",
                        valor="VÁLVULA", regra="regra", mensagem="tem caractere que o portal recusa",
                        indice=0)
    dlg = revisao_portal.RevisaoAntesDoPortalDialog(None, [problema], total=1)
    qtbot.addWidget(dlg)
    return dlg


def test_revisao_antes_do_portal_usa_a_chave_interna(qt_interface, qtbot):
    dlg = _revisao(qtbot)
    assert dlg.colunas.chave == "revisao_portal"
    assert dlg.colunas.colunas == ["ficha", "campo", "valor", "motivo"]
    assert dlg.tabela.colunas_lembradas is dlg.colunas
    assert dlg.tabela.header().sectionsMovable()


def test_revisao_antes_do_portal_lembra_em_outro_idioma(qt_interface, qtbot):
    dlg = _revisao(qtbot)
    cabecalho = dlg.tabela.header()
    cabecalho.moveSection(cabecalho.visualIndex(3), 0)
    dlg.colunas.mostrar_coluna("valor", False)
    with em_idioma("en"):
        nova = _revisao(qtbot)
        cab = nova.tabela.header()
        assert nova.tabela.headerItem().text(0) != "Ficha"
        assert [nova.colunas.colunas[cab.logicalIndex(p)] for p in range(cab.count())] == [
            "motivo", "ficha", "campo", "valor"]
        assert cab.isSectionHidden(2)


# -- fix round (revisão da Task 3) ---------------------------------------------------------
def _gravacoes(monkeypatch):
    feitas = []
    original = colunas_mod._gravar

    def _registrar(chave, valor):
        feitas.append((chave, valor))
        original(chave, valor)

    monkeypatch.setattr(colunas_mod, "_gravar", _registrar)
    return feitas


def _mostrada(qtbot, largura=1200):
    tabela, colunas = _tabela(qtbot)
    tabela.resize(largura, 300)
    tabela.show()
    qtbot.waitExposed(tabela)
    return tabela, colunas


def test_arrastar_a_com_c_esticando_nao_grava_a_largura_esticada(qt_interface, qtbot, monkeypatch):
    tabela, colunas = _mostrada(qtbot)
    cabecalho = tabela.header()
    cabecalho.resizeSection(0, 200)          # quem usa arrasta a borda de A
    assert cabecalho.stretchLastSection()    # e C passa a esticar
    esticada = cabecalho.sectionSize(2)
    assert esticada > 300
    colunas.gravar()
    guardado = prefs.ler_colunas("teste")
    assert guardado[0]["largura"] == 200
    assert guardado[2]["largura"] is None    # a esticada não é a largura de quem usa
    tabela.close()
    nova, _ = _mostrada(qtbot, largura=700)
    assert nova.header().sectionSize(0) == 200
    # C volta à de nascença (e estica de novo), não aos 500+ da janela larga.
    assert nova.header().sectionSize(2) < esticada
    assert nova.header().stretchLastSection()


def test_redimensionar_a_janela_nao_grava(qt_interface, qtbot, monkeypatch):
    tabela, colunas = _mostrada(qtbot)
    tabela.header().resizeSection(0, 200)
    colunas.gravar()
    feitas = _gravacoes(monkeypatch)
    for largura in (900, 1400, 800, 1300):
        tabela.resize(largura, 300)
        qtbot.wait(20)
        assert not colunas._gravar_depois.isActive()
    qtbot.wait(colunas_mod.MS_PARA_GRAVAR + 100)
    assert feitas == []
    assert prefs.ler_colunas("teste")[2]["largura"] is None


def test_esconder_a_ultima_faz_a_do_meio_ser_a_que_estica(qt_interface, qtbot, monkeypatch):
    tabela, colunas = _mostrada(qtbot)
    tabela.header().resizeSection(0, 200)
    colunas.mostrar_coluna("alvo", False)
    guardado = prefs.ler_colunas("teste")
    assert guardado[1]["largura"] is None    # agora é a "original" que estica
    feitas = _gravacoes(monkeypatch)
    tabela.resize(1500, 300)
    qtbot.wait(colunas_mod.MS_PARA_GRAVAR + 100)
    assert feitas == []


def test_colunas_de_mesmo_nome_marcam_a_coluna_certa(qt_interface, qtbot):
    tabela = qd.tabela_ttk([(titulo, 120, "w") for titulo in ("A", "B", "C")])
    qtbot.addWidget(tabela)
    colunas = colunas_mod.instalar_colunas(tabela, "teste_repetidas", ("x", "y", "x"))
    menu = colunas.montar_menu()
    acoes = [a for a in menu.actions() if a.isCheckable()]
    assert [a.data() for a in acoes] == [0, 1, 2]
    acoes[2].setChecked(False)
    assert tabela.header().isSectionHidden(2)
    assert not tabela.header().isSectionHidden(0)


def test_botao_direito_no_cabecalho_abre_o_menu(qt_interface, qtbot):
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication, QMenu

    tabela, _ = _mostrada(qtbot)
    cabecalho = tabela.header()
    cabecalho.customContextMenuRequested.emit(QPoint(10, 5))
    menu = QApplication.activePopupWidget() or cabecalho.findChild(QMenu)
    assert isinstance(menu, QMenu)
    textos = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert textos == ["Descrição", "PMIB Original", "PMIB Alvo", "Restaurar colunas"]
    menu.close()
    qtbot.wait(10)
