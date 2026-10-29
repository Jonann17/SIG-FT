"""A boas-vindas na tela (2026-10-28): a página da pilha, no lugar da Home, só na
primeira abertura de quem nunca usou o SIG-FT.

Desenho: `docs/superpowers/specs/2026-10-28-ajuda-para-quem-comeca-design.md`,
parte 2. A regra (quem nunca usou) está em `tests/test_boas_vindas.py`; a
varredura de corte (pt, es, en e letra Grande) passa pela página em
`tests/_varredura.py`.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from sigft.app import boas_vindas as regra
from sigft.app_qt import catalogo, icones
from sigft.app_qt import main as qmain
from sigft.app_qt.views import boas_vindas as pagina
from sigft.core import dados_usuario


@pytest.fixture(autouse=True)
def _ligada(monkeypatch):
    # O conftest desliga a boas-vindas em todo teste que não a testa.
    monkeypatch.delenv(regra.ENV_DESLIGAR, raising=False)


@pytest.fixture
def montar(qt_interface, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))

    def _montar():
        janela = qmain.SIG_FT_App()
        janela.fechar_sem_perguntar = True
        qtbot.addWidget(janela)
        return janela
    return _montar


def _na_boas_vindas(janela) -> bool:
    return janela.pilha.currentWidget() is janela.telas.get(qmain.CHAVE_BOAS_VINDAS)


def _cartao(janela, alvo):
    return janela.telas[qmain.CHAVE_BOAS_VINDAS].cartoes[alvo]


# --- quando aparece ------------------------------------------------------------------

def test_primeira_abertura_mostra_a_boas_vindas_no_lugar_da_home(montar):
    janela = montar()
    assert _na_boas_vindas(janela)
    # A Home existe (o tema, a letra e o Ctrl+K passam por ela), só não está à vista.
    assert "Home" in janela.telas
    # Fora do menu lateral, e nenhum item marcado.
    assert qmain.CHAVE_BOAS_VINDAS not in janela.botoes_menu
    assert not any(b.property("ativo") for b in [janela.botao_home, *janela.botoes_menu.values()])


def test_so_na_primeira_vez(montar):
    primeira = montar()
    primeira.telas[qmain.CHAVE_BOAS_VINDAS].ir_para_o_inicio()
    segunda = montar()
    assert segunda.pilha.currentWidget() is segunda.telas["Home"]
    assert qmain.CHAVE_BOAS_VINDAS not in segunda.telas


def test_quem_ja_usava_e_atualiza_nao_ve(montar):
    (dados_usuario.pasta_dados() / "user_prefs.json").write_text(
        '{"ultimos": {"cria_fichas.lista": "C:/Box"}}', encoding="utf-8")
    janela = montar()
    assert janela.pilha.currentWidget() is janela.telas["Home"]


def test_mostrar_nao_marca_como_vista(montar):
    # Quem fecha o app sem escolher nada a vê de novo.
    montar()
    assert regra.deve_mostrar_boas_vindas() is True


# --- o que tem -------------------------------------------------------------------------

def test_titulo_frase_e_os_tres_caminhos(montar):
    tela = montar().telas[qmain.CHAVE_BOAS_VINDAS]
    assert tela.titulo.text() == "Bem-vindo ao SIG-FT"
    assert tela.frase.text()
    assert list(tela.cartoes) == ["CriaFichas", "UploadConditions", "PMIBManager"]
    assert [c.titulo.text() for c in tela.cartoes.values()] == [
        "Criar fichas novas", "Completar fichas que já existem",
        "Acompanhar as listas de sobressalentes"]
    for alvo, cartao in tela.cartoes.items():
        assert cartao.icone.property("icone") == catalogo.ICONE_DA_TELA[alvo]
        assert cartao.toolTip() == catalogo.dica_do_menu(alvo)
    # Os caminhos levam a telas de verdade do menu.
    menu = {item[2] for item in catalogo.MENU if item[0] == "botao"}
    assert set(tela.cartoes) <= menu


def test_lembra_do_como_funciona_e_do_ctrl_k(montar):
    tela = montar().telas[qmain.CHAVE_BOAS_VINDAS]
    texto = " ".join(r.text() for r in tela.lembretes)
    assert "Como funciona" in texto and "Ctrl+K" in texto


def test_icones_desenham(montar):
    tela = montar().telas[qmain.CHAVE_BOAS_VINDAS]
    assert tela.btn_inicio.property("icone") == "house" and not tela.btn_inicio.icon().isNull()
    assert all(nome in icones.NOMES for nome in (c.icone.property("icone") for c in tela.cartoes.values()))


# --- o que cada clique faz -------------------------------------------------------------

@pytest.mark.parametrize("alvo", ["CriaFichas", "UploadConditions", "PMIBManager"])
def test_cada_caminho_abre_a_tela_certa_e_marca_vista(montar, qtbot, alvo):
    janela = montar()
    qtbot.mouseClick(_cartao(janela, alvo), Qt.MouseButton.LeftButton)
    assert janela.pilha.currentWidget() is janela.telas[alvo]
    assert janela.botoes_menu[alvo].property("ativo") is True
    assert regra.ja_vista() is True


def test_ir_para_o_inicio_marca_vista_e_mostra_a_home(montar, qtbot):
    janela = montar()
    tela = janela.telas[qmain.CHAVE_BOAS_VINDAS]
    assert tela.btn_inicio.text() == "Ir para o início"
    qtbot.mouseClick(tela.btn_inicio, Qt.MouseButton.LeftButton)
    assert janela.pilha.currentWidget() is janela.telas["Home"]
    assert janela.botao_home.property("ativo") is True
    assert regra.ja_vista() is True


def test_caminho_bloqueado_vem_apagado_com_a_dica_do_menu(montar, qtbot, monkeypatch):
    monkeypatch.setattr(catalogo, "TELAS_BLOQUEADAS", frozenset({"UploadConditions"}))
    janela = montar()
    cartao = _cartao(janela, "UploadConditions")
    assert not cartao.isEnabled()
    assert cartao.toolTip() == catalogo.dica_do_menu("UploadConditions")
    assert "Bloqueado nesta versão." in cartao.toolTip()
    qtbot.mouseClick(cartao, Qt.MouseButton.LeftButton)
    assert _na_boas_vindas(janela)
    assert regra.ja_vista() is False
    assert _cartao(janela, "CriaFichas").isEnabled()


def test_sair_pelo_menu_nao_marca_vista(montar, qtbot):
    # Fecha sem escolher vê de novo: o menu lateral não é escolha de caminho.
    janela = montar()
    qtbot.mouseClick(janela.botoes_menu["Translator"], Qt.MouseButton.LeftButton)
    assert janela.pilha.currentWidget() is janela.telas["Translator"]
    assert regra.ja_vista() is False


# --- pelo teclado (fix round 2026-10-28) -----------------------------------------------------

def test_cartao_recebe_foco_pelo_tab_e_pelo_clique(montar):
    janela = montar()
    for alvo in ("CriaFichas", "UploadConditions", "PMIBManager"):
        assert _cartao(janela, alvo).focusPolicy() == Qt.FocusPolicy.StrongFocus


@pytest.mark.parametrize("tecla", [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space])
def test_enter_e_espaco_fazem_o_mesmo_que_o_clique(montar, qtbot, tecla):
    janela = montar()
    qtbot.keyClick(_cartao(janela, "UploadConditions"), tecla)
    assert janela.pilha.currentWidget() is janela.telas["UploadConditions"]
    assert regra.ja_vista() is True


def test_outra_tecla_nao_escolhe(montar, qtbot):
    janela = montar()
    qtbot.keyClick(_cartao(janela, "CriaFichas"), Qt.Key.Key_A)
    assert _na_boas_vindas(janela)
    assert regra.ja_vista() is False


def test_caminho_bloqueado_nao_escolhe_pelo_teclado(montar, qtbot, monkeypatch):
    monkeypatch.setattr(catalogo, "TELAS_BLOQUEADAS", frozenset({"UploadConditions"}))
    janela = montar()
    cartao = _cartao(janela, "UploadConditions")
    cartao.keyPressEvent(_tecla(Qt.Key.Key_Return))
    assert _na_boas_vindas(janela)
    assert regra.ja_vista() is False


def _tecla(codigo):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent

    return QKeyEvent(QEvent.Type.KeyPress, codigo, Qt.KeyboardModifier.NoModifier)


@pytest.mark.parametrize("nome_tema", ["escuro", "claro"])
def test_foco_visivel_pelo_papel_da_cor(nome_tema):
    # O foco usa os papéis do tema (borda `primaria`, fundo `superficie_alta`),
    # nunca cor crua: a regra mora no `estilo`.
    from sigft.app import tokens
    from sigft.app_qt import estilo

    folha = estilo.folha_de_estilo(nome_tema)
    p = tokens.paleta(nome_tema)
    regra_foco = next(linha for linha in folha.splitlines() if '#card[caminho="true"]:focus' in linha)
    assert p["primaria"] in regra_foco and p["superficie_alta"] in regra_foco


# --- reabre --------------------------------------------------------------------------------

def test_ctrl_k_reabre(montar):
    janela = montar()
    janela.telas[qmain.CHAVE_BOAS_VINDAS].ir_para_o_inicio()
    janela.executar_comando("acao:boas_vindas")
    assert _na_boas_vindas(janela)


@pytest.mark.parametrize("consulta", ["boas", "bem-vindo", "comecar"])
def test_ctrl_k_acha_em_portugues(consulta):
    achados = [c.chave for c in catalogo.filtrar(catalogo.comandos(), consulta)]
    assert "acao:boas_vindas" in achados


def test_ctrl_k_acha_em_portugues_em_outro_idioma():
    from _idioma import em_idioma

    with em_idioma("en"):
        achados = [c.chave for c in catalogo.filtrar(catalogo.comandos(), "boas-vindas")]
        assert "acao:boas_vindas" in achados
        texto = next(c.texto for c in catalogo.comandos() if c.chave == "acao:boas_vindas")
        assert texto == "Welcome"


def test_configuracao_reabre(montar, qtbot):
    janela = montar()
    janela.telas[qmain.CHAVE_BOAS_VINDAS].ir_para_o_inicio()
    config = janela.telas["Home"].abrir_configuracao()
    config.show()
    assert "ajuda" in config.secoes
    qtbot.mouseClick(config.btn_boas_vindas, Qt.MouseButton.LeftButton)
    assert _na_boas_vindas(janela)
    assert not config.isVisible()


def test_desligada_pela_variavel_abre_na_home(montar, monkeypatch):
    monkeypatch.setenv(regra.ENV_DESLIGAR, "1")
    janela = montar()
    assert janela.pilha.currentWidget() is janela.telas["Home"]


def test_pagina_nao_tem_lambda_com_self(montar):
    # A armadilha medida no CMI Suite (segfault ao fechar): nada de lambda que
    # capture `self` no sinal de um filho. Os cliques vão para métodos.
    import ast
    import inspect

    arvore = ast.parse(inspect.getsource(pagina))
    assert not [n for n in ast.walk(arvore) if isinstance(n, ast.Lambda)]
