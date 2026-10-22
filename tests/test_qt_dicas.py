"""Dicas de botão (2026-10-20): toda dica aponta para um botão que existe.

As dicas moram em `sigft/app/textos_dicas.py`, longe das telas. Sem esta
trava, um botão renomeado deixaria a dica órfã -- em silêncio, que é o pior
jeito de uma ajuda sumir.
"""
import pytest

from sigft.app import textos_dicas
from sigft.app_qt import catalogo
from sigft.app_qt import main as qmain
from sigft.app_qt.widgets.module_frame import ModuleFrame


@pytest.fixture
def todas_as_telas(qt_interface, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    janela = qmain.SIG_FT_App()
    qtbot.addWidget(janela)
    for chave in qmain.TELAS:
        if chave in catalogo.TELAS_BLOQUEADAS:
            tela = qmain.TELAS[chave](janela.pilha, janela)
            janela.telas[chave] = tela
            janela.pilha.addWidget(tela)
        else:
            janela.show_frame(chave)
    home = janela.telas["Home"]
    # Sem chave de API o painel de modelos só mostra o aviso, sem botões.
    monkeypatch.setattr(janela, "get_key", lambda _chave: "chave-de-teste")
    home.abrir_janela_chaves_api()
    home.abrir_janela_modelos_ia()
    home.abrir_janela_gastos_ia()
    config = home.abrir_configuracao()
    instancias = {type(home).__name__: home}
    for tela in janela.findChildren(ModuleFrame):
        for classe in type(tela).__mro__:
            instancias.setdefault(classe.__name__, tela)
    instancias["JanelaConfiguracao"] = config
    return janela, instancias


def test_toda_dica_aponta_para_um_botao_que_existe(todas_as_telas):
    _janela, instancias = todas_as_telas
    orfas = []
    for classe, dicas in textos_dicas.DICAS.items():
        tela = instancias.get(classe)
        assert tela is not None, f"nenhuma tela {classe} foi montada"
        orfas += [f"{classe}.{a}" for a in dicas if getattr(tela, a, None) is None]
    assert orfas == []


def test_a_dica_chega_ao_botao(todas_as_telas):
    _janela, instancias = todas_as_telas
    tela = instancias["ModuloCopiaFichas"]
    # A dica crua tem o lugar `{portal}` (2026-10-22): compara com a montada.
    assert tela.btn_robo_novo.toolTip() == textos_dicas.dicas_da_classe(type(tela))["btn_robo_novo"]
    upload = instancias["ModuloUploadConditions"]
    assert upload.btn_ia.toolTip() == textos_dicas.dicas_da_classe(type(upload))["btn_ia"]


def test_painel_da_home_aberto_depois_tambem_ganha_dica(todas_as_telas):
    _janela, instancias = todas_as_telas
    home = instancias["HomeView"]
    assert home.btn_salvar_chaves.toolTip()
    assert home.btn_salvar_selecao_ia.toolTip()
    assert all(b.toolTip() for b in home.botoes_barra.values())
    # 2026-10-22: a caixa de versões de teste foi para a janela Configuração.
    assert instancias["JanelaConfiguracao"].caixa_canal_testes.toolTip()
    assert home.btn_configuracao.toolTip() == "Configuração"


def test_todo_botao_do_menu_lateral_tem_dica(todas_as_telas):
    janela, _ = todas_as_telas
    sem = [alvo for alvo, b in janela.botoes_menu.items() if not b.toolTip()]
    assert sem == []
    assert "Bloqueado" in janela.botoes_menu["CorrecaoPDM"].toolTip()
