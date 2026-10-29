"""Letra Normal / Grande, aplicada na hora como o tema (2026-10-21, etapa 1b)."""
import re

import pytest
from PySide6.QtWidgets import QApplication

from _varredura import varrer
from sigft.app import tokens
from sigft.app_qt import catalogo, estilo, letra
from sigft.app_qt.widgets import blocos


class Controller:
    api_keys: dict = {}


@pytest.fixture
def letra_temporaria(qt_interface, tmp_path, monkeypatch):
    monkeypatch.setattr(letra, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    anterior = qt_interface.styleSheet()
    yield qt_interface
    letra.aplicar(qt_interface, "normal", gravar=False)
    qt_interface.setStyleSheet(anterior)


def _tamanhos(folha):
    return [int(t) for t in re.findall(r"font-size:\s*(\d+)px", folha)]


def test_ajustar_tamanhos():
    # Só px (fix round 1, 2026-10-21): o aumento é de 2 PIXELS; um pt fica como está.
    folha = "a { font-size: 12px; } b { font-size: 9pt; }"
    assert estilo.ajustar_tamanhos(folha, 2) == "a { font-size: 14px; } b { font-size: 9pt; }"
    assert estilo.ajustar_tamanhos(folha, 0) == folha


def test_normal_e_a_folha_de_sempre():
    # No Normal nada muda: a folha do app é a mesma de antes da letra existir.
    assert estilo.AUMENTO_LETRA == 0
    assert estilo.folha_de_estilo("escuro") == estilo._folha_base("escuro")


def test_grande_soma_2_em_toda_a_escala_da_folha(letra_temporaria):
    normal = estilo.folha_de_estilo()
    letra.aplicar(letra_temporaria, "grande")
    assert _tamanhos(letra_temporaria.styleSheet()) == \
        [t + tokens.AUMENTO_DA_LETRA["grande"] for t in _tamanhos(normal)]
    assert letra.escolhido() == "grande"


def test_peca_com_folha_propria_cresce_e_volta(letra_temporaria, qtbot):
    rotulo = blocos.rotulo("Olá", tamanho=13)
    qtbot.addWidget(rotulo)
    letra.aplicar(letra_temporaria, "grande")
    assert "font-size: 15px" in rotulo.styleSheet()
    letra.aplicar(letra_temporaria, "normal")
    assert "font-size: 13px" in rotulo.styleSheet()


def test_peca_criada_depois_nasce_grande(letra_temporaria, qtbot):
    letra.aplicar(letra_temporaria, "grande")
    botao = blocos.botao("Salvar", tamanho_fonte=12)
    qtbot.addWidget(botao)
    botao.show()
    qtbot.waitExposed(botao)
    assert "font-size: 14px" in botao.styleSheet()


def test_pintar_depois_nao_soma_duas_vezes(letra_temporaria, qtbot):
    botao = blocos.botao("Salvar", tamanho_fonte=12)
    qtbot.addWidget(botao)
    botao.show()
    qtbot.waitExposed(botao)
    letra.aplicar(letra_temporaria, "grande")
    blocos.pintar(botao, "QPushButton { font-weight: bold; }")
    QApplication.processEvents()
    assert "font-size: 14px" in botao.styleSheet()
    assert "font-size: 16px" not in botao.styleSheet()


def test_normal_nao_deixa_vigia(letra_temporaria):
    letra.aplicar(letra_temporaria, "grande")
    assert len(letra._vigia) == 1
    letra.aplicar(letra_temporaria, "normal")
    assert letra._vigia == []


def test_preferencia_que_nao_se_le_e_normal(monkeypatch):
    from sigft.core import prefs

    def quebra(*_a, **_k):
        raise OSError("disco fora")

    monkeypatch.setattr(prefs, "ler_preferencia", quebra)
    assert letra.escolhido() == "normal"


def test_letra_e_tema_juntos(letra_temporaria, tmp_path, monkeypatch):
    # O tema regera a folha do app: a letra grande tem de continuar nela.
    from sigft.app_qt import tema

    monkeypatch.setattr(tema, "_arquivo_de_prefs", lambda: tmp_path / "t.json")
    atual = estilo.TEMA_ATUAL
    try:
        letra.aplicar(letra_temporaria, "grande")
        tema.aplicar(letra_temporaria, "claro")
        grande = tokens.AUMENTO_DA_LETRA["grande"]
        assert _tamanhos(letra_temporaria.styleSheet()) == \
            [t + grande for t in _tamanhos(estilo._folha_base("claro"))]
        letra.aplicar(letra_temporaria, "normal")
        assert letra_temporaria.styleSheet() == estilo._folha_base("claro")
    finally:
        estilo.TEMA_ATUAL = atual


def test_largura_fixa_alarga_no_grande_e_volta_igual(letra_temporaria, qtbot):
    # Botão de largura fixa: com a letra grande, o texto não pode ser cortado;
    # no normal, a largura de sempre, ao pixel (fix round 1, 2026-10-21).
    letra.aplicar(letra_temporaria, "normal", gravar=False)
    botao = blocos.botao("APLICAR AUTORIZAÇÕES", largura=200, tamanho_fonte=12, negrito=True)
    rotulo = blocos.rotulo("Pasta dos PDMs Modificados:", tamanho=13)
    rotulo.setFixedWidth(190)
    for w in (botao, rotulo):
        qtbot.addWidget(w)
        w.show()
        qtbot.waitExposed(w)
    letra.aplicar(letra_temporaria, "grande")
    for w in (botao, rotulo):
        assert w.width() >= w.sizeHint().width()
        assert w.minimumWidth() == w.maximumWidth()
    letra.aplicar(letra_temporaria, "normal")
    assert (botao.minimumWidth(), botao.maximumWidth()) == (200, 200)
    assert (rotulo.minimumWidth(), rotulo.maximumWidth()) == (190, 190)


def test_rotulo_elidido_nao_alarga(letra_temporaria, qtbot):
    rotulo = blocos.RotuloElidido("um_nome_de_arquivo_bem_comprido_mesmo.xlsx")
    rotulo.setFixedWidth(80)
    qtbot.addWidget(rotulo)
    letra.aplicar(letra_temporaria, "grande")
    assert rotulo.width() == 80


def test_regra_somada_depois_nao_dobra_o_aumento(letra_temporaria, qtbot):
    # A busca e o AutoSpec somam uma regra à folha do botão: por `blocos.pintar`,
    # que parte da folha de antes do aumento (fix round 1, 2026-10-21). Somada à
    # mão sobre a folha já aumentada, um novo aumento a contaria duas vezes.
    from sigft.app_qt.views import busca_pmib

    botao = busca_pmib._botao_cinza("Abrir Pasta", 120)
    assert botao.property("_folha_base") is not None        # feita por `pintar`
    assert botao.styleSheet().endswith("QPushButton { padding: 0; }")
    link = blocos.botao("Datasheet", tamanho_fonte=11)
    qtbot.addWidget(link)
    qtbot.addWidget(botao)
    link.show()
    qtbot.waitExposed(link)
    letra.aplicar(letra_temporaria, "grande")
    blocos.pintar(link, "QPushButton { text-align: left; }")
    letra.aplicar(letra_temporaria, "normal")
    letra.aplicar(letra_temporaria, "grande")
    QApplication.processEvents()
    assert "font-size: 13px" in link.styleSheet() and "15px" not in link.styleSheet()


def test_escolha_invalida_e_normal(tmp_path, monkeypatch):
    monkeypatch.setattr(letra, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    (tmp_path / "p.json").write_text('{"preferencias": {"letra": "enorme"}}', encoding="utf-8")
    assert letra.escolhido() == "normal"


def test_seletor_de_letra_num_lugar_so():
    # Como o de tema: a janela Configuração e o Ctrl+K saem de `catalogo.SELETOR_LETRA`.
    from sigft.app_qt.views import configuracao as config_mod

    assert config_mod.SELETOR_LETRA is catalogo.SELETOR_LETRA
    assert tuple(e for e, *_ in catalogo.SELETOR_LETRA) == letra.TAMANHOS
    # O texto do Ctrl+K é "Letra: {nome}" traduzido em `comandos()` (idioma, 2026-10-22).
    na_paleta = {c.chave: c.texto for c in catalogo.comandos()}
    for escolha, texto, _dica in catalogo.SELETOR_LETRA:
        assert na_paleta[f"acao:letra_{escolha}"] == f"Letra: {texto}"


def _configuracao(qtbot):
    from sigft.app_qt.views import home as home_mod

    tela = home_mod.HomeView(controller=Controller())
    qtbot.addWidget(tela)
    return tela.abrir_configuracao()


def test_seletor_da_configuracao_marca_e_aplica(letra_temporaria, qtbot):
    config = _configuracao(qtbot)
    assert set(config.botoes_letra) == set(letra.TAMANHOS)
    assert config.botoes_letra["normal"].property("ativo") is True
    config.botoes_letra["grande"].click()
    assert estilo.AUMENTO_LETRA == tokens.AUMENTO_DA_LETRA["grande"]
    assert config.botoes_letra["grande"].property("ativo") is True
    assert config.botoes_letra["normal"].property("ativo") is False


def test_seletor_marca_a_letra_que_esta_valendo(letra_temporaria, qtbot):
    # `--smoke --letra grande` não grava: o seletor marca a que vale, não a das prefs.
    letra.aplicar(letra_temporaria, "grande", gravar=False)
    assert letra.escolhido() == "normal" and letra.atual() == "grande"
    config = _configuracao(qtbot)
    assert config.botoes_letra["grande"].property("ativo") is True


def test_opcao_da_linha_de_comando():
    from sigft.app_qt import main as qmain

    assert qmain._opcao_da_linha_de_comando(["f", "--smoke", "--letra", "grande"], "--letra") == "grande"
    assert qmain._opcao_da_linha_de_comando(["f", "--letra=grande"], "--letra") == "grande"
    assert qmain._opcao_da_linha_de_comando(["f", "--smoke"], "--letra") is None
    assert qmain._tema_da_linha_de_comando(["f", "--tema", "claro"]) == "claro"


# --- as 12 telas com a letra grande (fix round 1, 2026-10-21) -----------------

def test_nenhuma_tela_corta_texto_nem_rola_de_lado_com_a_letra_grande(
        letra_temporaria, qtbot, tmp_path, monkeypatch):
    from sigft.app_qt import main as qmain

    monkeypatch.delenv("SIGFT_SEM_COMO_FUNCIONA", raising=False)   # as telas com o "Como funciona"

    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    letra.aplicar(letra_temporaria, "normal", gravar=False)
    janela = qmain.SIG_FT_App()
    janela.fechar_sem_perguntar = True
    qtbot.addWidget(janela)
    janela.resize(1280, 850)
    janela.show()
    qtbot.waitExposed(janela)
    normal, rolando_normal = varrer(janela, qtbot)
    letra.aplicar(letra_temporaria, "grande", gravar=False)
    grande, rolando_grande = varrer(janela, qtbot)
    assert rolando_normal == [] and rolando_grande == []
    # O que já ficava apertado no normal (o "Limpar" de 100 px da Criação de
    # Fichas, travado pelo teste de medidas) não conta; o resto, nada cortado.
    assert {alvo: textos - normal[alvo] for alvo, textos in grande.items() if textos - normal[alvo]} == {}
    letra.aplicar(letra_temporaria, "normal", gravar=False)
    de_volta, _ = varrer(janela, qtbot)
    assert de_volta == normal


# --- fora do português (2026-10-22) ------------------------------------------

def test_largura_fixa_alarga_em_outro_idioma_com_a_letra_normal(letra_temporaria, qtbot):
    # As larguras fixas foram medidas no português; em espanhol e inglês o texto
    # tem outro tamanho. O mesmo ajuste da letra grande vale fora do português.
    from sigft.app import idioma

    try:
        idioma.definir("es")
        letra.aplicar(letra_temporaria, "normal", gravar=False)
        assert len(letra._vigia) == 1
        botao = blocos.botao("APLICAR LAS AUTORIZACIONES DE ENTREGA", largura=200, tamanho_fonte=12,
                             negrito=True)
        qtbot.addWidget(botao)
        botao.show()
        qtbot.waitExposed(botao)
        qtbot.waitUntil(lambda: botao.width() >= botao.sizeHint().width(), timeout=1000)
        assert botao.minimumWidth() == botao.maximumWidth()
    finally:
        idioma.definir("pt")
        letra.aplicar(letra_temporaria, "normal", gravar=False)
    assert letra._vigia == []


def test_em_portugues_com_a_letra_normal_a_largura_fixa_e_a_de_sempre(letra_temporaria, qtbot):
    letra.aplicar(letra_temporaria, "normal", gravar=False)
    assert letra._vigia == []
    botao = blocos.botao("APLICAR LAS AUTORIZACIONES DE ENTREGA", largura=200, tamanho_fonte=12, negrito=True)
    qtbot.addWidget(botao)
    botao.show()
    qtbot.waitExposed(botao)
    assert (botao.minimumWidth(), botao.maximumWidth()) == (200, 200)


def test_reavaliar_o_vigia_segue_o_idioma(letra_temporaria):
    from sigft.app import idioma

    letra.aplicar(letra_temporaria, "normal", gravar=False)
    idioma.definir("en")
    letra.reavaliar_vigia(letra_temporaria)
    assert len(letra._vigia) == 1
    idioma.definir("pt")
    letra.reavaliar_vigia(letra_temporaria)
    assert letra._vigia == []
