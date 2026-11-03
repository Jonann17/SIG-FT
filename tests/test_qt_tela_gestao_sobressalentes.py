"""A seção do PMIB Manager (Qt): Gestão PMIB, Conferência de Revisões e Revisão no AMP em abas,
com um console e uma barra de progresso. Correção do Luan (27/10): as duas telas novas são abas
do PMIB Manager, não módulos novos no menu.
"""
from sigft.app_qt import catalogo
from sigft.app_qt import main as qmain
from sigft.app_qt.views.gestao_sobressalentes import ModuloGestaoSobressalentes

ABAS = ["Gestão PMIB", "Conferência de Revisões", "Revisão no AMP", "DocPack"]


def test_quatro_abas_com_um_console_e_uma_barra(qt_interface, qtbot):
    secao = ModuloGestaoSobressalentes()
    qtbot.addWidget(secao)
    assert secao.label_titulo.text() == "Gestão de Sobressalentes"
    assert list(secao.abas.abas) == ABAS
    assert secao.abas.get() == "Gestão PMIB"
    telas = (secao.tela_gestao, secao.tela_conferencia, secao.tela_amp, secao.tela_docpack)
    for nome, tela in zip(ABAS, telas):
        assert secao.abas.tab(nome).isAncestorOf(tela), nome
        assert tela.header is None, nome
        assert tela.console is secao.console and tela.progress_bar is secao.progress_bar, nome
    # A Revisão no AMP parte da última conferência da aba ao lado.
    assert secao.tela_amp.fonte is secao.tela_conferencia


def test_as_abas_escrevem_no_mesmo_console(qt_interface, qtbot):
    secao = ModuloGestaoSobressalentes()
    qtbot.addWidget(secao)
    secao.tela_gestao.log("vindo da gestão")
    secao.abas.botoes["Revisão no AMP"].click()
    secao.tela_amp.log("vindo do AMP")
    qtbot.waitUntil(lambda: "vindo do AMP" in secao.console.toPlainText(), timeout=2000)
    texto = secao.console.toPlainText()
    assert texto.index("vindo da gestão") < texto.index("vindo do AMP")


def test_as_tabelas_cabem_na_aba(qt_interface, qtbot):
    # As colunas esticam mas não encolhem, e as tabelas não têm barra de lado: o que passa
    # da largura some. A 1280x850 a tela tem 1003 de largura (sem o menu).
    secao = ModuloGestaoSobressalentes()
    qtbot.addWidget(secao)
    secao.resize(1003, 850)
    secao.show()
    qtbot.waitExposed(secao)
    for nome, tabela in (("Conferência de Revisões", secao.tela_conferencia.tabelas["aprovada"]),
                         ("Revisão no AMP", secao.tela_amp.tabela), ("DocPack", secao.tela_docpack.tabela)):
        secao.abas.set(nome)
        qtbot.wait(20)
        soma = sum(tabela.columnWidth(i) for i in range(tabela.columnCount()))
        assert soma <= tabela.viewport().width(), nome


def test_o_menu_pmib_manager_abre_a_secao(qt_interface, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    janela = qmain.SIG_FT_App()
    qtbot.addWidget(janela)
    janela.show_frame("PMIBManager")
    assert isinstance(janela.pilha.currentWidget(), ModuloGestaoSobressalentes)


def test_a_conferencia_saiu_do_menu_e_dos_cards():
    telas_do_menu = [item[2] for item in catalogo.MENU if item[0] == "botao"]
    for lugar in (telas_do_menu, [m[0] for m in catalogo.MODULOS], catalogo.ICONE_DA_TELA, qmain.TELAS):
        assert "ConferenciaRevisoes" not in lugar
    assert len(catalogo.MODULOS) == 12


def test_a_tela_diz_se_tem_tarefa_rodando(qt_interface, qtbot):
    # A Revisão no AMP pergunta isso à Conferência antes de começar.
    import threading

    secao = ModuloGestaoSobressalentes()
    qtbot.addWidget(secao)
    conferencia = secao.tela_conferencia
    assert conferencia.rodando() is False
    liberar = threading.Event()
    conferencia.iniciar_tarefa(liberar.wait)
    assert conferencia.rodando() is True
    liberar.set()
    qtbot.waitUntil(lambda: not conferencia.rodando(), timeout=3000)
