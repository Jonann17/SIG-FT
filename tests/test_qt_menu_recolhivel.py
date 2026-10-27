"""O menu lateral recolhível (2026-10-26): só os ícones, lembrado, pelo botão do
pé ou pelo Ctrl+K; expandido, todos os nomes inteiros."""
import pytest

from _idioma import em_idioma
from _varredura import cortados
from sigft.app.idioma import t
from sigft.app_qt import catalogo, estilo, letra, tema
from sigft.app_qt import main as qmain
from sigft.core import prefs


@pytest.fixture
def montar(qt_interface, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(letra, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    monkeypatch.setattr(tema, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    anterior = qt_interface.styleSheet()
    tema.aplicar(qt_interface, "escuro", gravar=False)

    def _montar():
        janela = qmain.SIG_FT_App()
        janela.fechar_sem_perguntar = True
        qtbot.addWidget(janela)
        janela.resize(1280, 850)
        janela.show()
        qtbot.waitExposed(janela)
        return janela

    yield _montar
    letra.aplicar(qt_interface, "normal", gravar=False)
    tema.aplicar(qt_interface, tema.PADRAO, gravar=False)
    qt_interface.setStyleSheet(anterior)


def _nomes_do_menu():
    return {t(item[1]) for item in catalogo.MENU if item[0] == "botao"}


def test_nasce_expandido(montar):
    janela = montar()
    assert janela.menu_recolhido is False
    assert janela.barra_lateral.width() == estilo.LARGURA_BARRA_LATERAL
    assert {b.text().strip() for b in janela.botoes_menu.values()} == _nomes_do_menu()


def test_recolher_deixa_so_os_icones_com_o_nome_na_dica(montar, qtbot):
    janela = montar()
    janela.recolher_menu(True)
    qtbot.wait(20)
    assert janela.barra_lateral.width() == estilo.LARGURA_BARRA_RECOLHIDA
    assert janela.pilha.mapTo(janela, janela.pilha.rect().topLeft()).x() == estilo.LARGURA_BARRA_RECOLHIDA
    for item in catalogo.MENU:
        if item[0] != "botao":
            continue
        botao = janela.botoes_menu[item[2]]
        assert botao.text() == ""
        assert not botao.icon().isNull()
        assert botao.toolTip().startswith(t(item[1]))
        assert catalogo.dica_do_menu(item[2]) in botao.toolTip()
        assert botao.accessibleName() == t(item[1])
    assert janela.botao_home.text() == "" and janela.botao_home.toolTip().startswith("Home")
    assert not any(r.isVisible() for r in janela._rotulos_secao)
    assert all(traco.isVisible() for traco in janela._tracos_secao)
    assert not janela.marca.nome.isVisible()
    assert janela.botao_menu.property("icone") == catalogo.ICONE_EXPANDIR_MENU
    assert janela.botao_menu.toolTip() == "Expandir menu"


def test_expandir_volta_os_nomes_e_as_dicas(montar):
    janela = montar()
    janela.recolher_menu(True)
    janela.recolher_menu(False)
    assert janela.barra_lateral.width() == estilo.LARGURA_BARRA_LATERAL
    for alvo, botao in janela.botoes_menu.items():
        assert botao.toolTip() == catalogo.dica_do_menu(alvo)
    assert {b.text().strip() for b in janela.botoes_menu.values()} == _nomes_do_menu()
    assert all(r.isVisible() for r in janela._rotulos_secao)
    assert not any(traco.isVisible() for traco in janela._tracos_secao)
    assert janela.marca.nome.isVisible()
    assert janela.botao_menu.toolTip() == "Recolher menu"


def test_fica_lembrado_para_a_proxima_abertura(montar):
    janela = montar()
    janela.botao_menu.click()
    assert janela.menu_recolhido is True
    assert prefs.get_opcao(qmain.CHAVE_MENU_RECOLHIDO, False) is True
    outra = montar()
    assert outra.menu_recolhido is True
    assert outra.barra_lateral.width() == estilo.LARGURA_BARRA_RECOLHIDA
    outra.botao_menu.click()
    assert prefs.get_opcao(qmain.CHAVE_MENU_RECOLHIDO, True) is False


def test_item_da_tela_aberta_destacado_nos_dois_estados(montar):
    janela = montar()
    janela.show_frame("Analyzer")
    janela.recolher_menu(True)
    assert janela.botoes_menu["Analyzer"].property("ativo") is True
    janela.recolher_menu(False)
    assert janela.botoes_menu["Analyzer"].property("ativo") is True
    janela.show_home()
    janela.recolher_menu(True)
    assert janela.botao_home.property("ativo") is True


def test_ctrl_k_alterna_e_o_texto_acompanha(montar):
    janela = montar()
    textos = {c.chave: c.texto for c in catalogo.comandos(menu_recolhido=False)}
    assert textos["acao:menu"] == "Recolher menu"
    janela.executar_comando("acao:menu")
    assert janela.menu_recolhido is True
    expandir = {c.chave: c for c in catalogo.comandos(menu_recolhido=True)}["acao:menu"]
    assert expandir.texto == "Expandir menu" and expandir.icone == catalogo.ICONE_EXPANDIR_MENU
    paleta = janela.abrir_paleta()
    assert "Expandir menu" in [c.texto for c in paleta._comandos]
    paleta.close()
    janela.executar_comando("acao:menu")
    assert janela.menu_recolhido is False


@pytest.mark.parametrize("codigo", ["es", "en"])
def test_ctrl_k_traduzido_acha_tambem_em_portugues(codigo):
    with em_idioma(codigo):
        lista = catalogo.comandos()
        assert {c.chave: c.texto for c in lista}["acao:menu"] != "Recolher menu"
        for consulta in ("recolher", "menu lateral"):
            assert "acao:menu" in [c.chave for c in catalogo.filtrar(lista, consulta)], consulta


@pytest.mark.parametrize("tamanho", ["normal", "grande"])
@pytest.mark.parametrize("codigo", ["pt", "es", "en"])
def test_expandido_mostra_todos_os_nomes_inteiros(montar, qtbot, qt_interface, codigo, tamanho):
    with em_idioma(codigo):
        letra.aplicar(qt_interface, tamanho, gravar=False)
        janela = montar()
        janela.recolher_menu(True)
        qtbot.wait(20)
        janela.recolher_menu(False)
        qtbot.wait(20)
        assert cortados(janela.barra_lateral) == set()
        assert {b.text().strip() for b in janela.botoes_menu.values()} == _nomes_do_menu()
        assert not janela.barra_lateral.horizontalScrollBar().isVisible()
    letra.aplicar(qt_interface, "normal", gravar=False)


def test_folha_tem_as_regras_do_menu_recolhido():
    folha = estilo.folha_de_estilo()
    assert "#traco_secao" in folha
    assert 'QPushButton[menu="true"][recolhido="true"]' in folha
    assert '#home[recolhido="true"]' in folha
