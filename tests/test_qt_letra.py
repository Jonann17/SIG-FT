"""Letra Normal / Grande, aplicada na hora como o tema (2026-10-21, etapa 1b)."""
import re

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

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
    folha = "a { font-size: 12px; } b { font-size: 9pt; }"
    assert estilo.ajustar_tamanhos(folha, 2) == "a { font-size: 14px; } b { font-size: 11pt; }"
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


def test_escolha_invalida_e_normal(tmp_path, monkeypatch):
    monkeypatch.setattr(letra, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    (tmp_path / "p.json").write_text('{"preferencias": {"letra": "enorme"}}', encoding="utf-8")
    assert letra.escolhido() == "normal"


def test_seletor_de_letra_num_lugar_so():
    # Como o de tema (2026-10-21): a Home e o Ctrl+K saem de `catalogo.SELETOR_LETRA`.
    from sigft.app_qt.views import home as home_mod

    assert home_mod.SELETOR_LETRA is catalogo.SELETOR_LETRA
    assert tuple(e for e, *_ in catalogo.SELETOR_LETRA) == letra.TAMANHOS
    na_paleta = {a[0]: a[1] for a in catalogo.ACOES}
    for escolha, texto, _dica in catalogo.SELETOR_LETRA:
        assert na_paleta[f"letra_{escolha}"] == f"Letra: {texto}"


def test_seletor_na_home_marca_e_aplica(letra_temporaria, qtbot):
    from sigft.app_qt.views import home as home_mod

    tela = home_mod.HomeView(controller=Controller())
    qtbot.addWidget(tela)
    assert set(tela.botoes_letra) == set(letra.TAMANHOS)
    assert tela.botoes_letra["normal"].property("ativo") is True
    tela.botoes_letra["grande"].click()
    assert estilo.AUMENTO_LETRA == tokens.AUMENTO_DA_LETRA["grande"]
    assert tela.botoes_letra["grande"].property("ativo") is True
    assert tela.botoes_letra["normal"].property("ativo") is False


@pytest.mark.parametrize("escolha", ["normal", "grande"])
def test_seletores_cabem_na_linha_do_titulo(letra_temporaria, qtbot, escolha):
    # A barra de botões já ocupa quase toda a Home a 1280 px: tema e letra ficam
    # na linha do título, à direita, sem rolagem horizontal nem mexer no título.
    from sigft.app_qt.views import home as home_mod

    letra.aplicar(letra_temporaria, escolha, gravar=False)
    tela = home_mod.HomeView(controller=Controller())
    qtbot.addWidget(tela)
    tela.resize(1280 - estilo.LARGURA_BARRA_LATERAL, 850)
    tela.show()
    qtbot.waitExposed(tela)
    corpo = tela.widget()
    assert corpo.minimumSizeHint().width() <= tela.viewport().width()
    qtbot.waitUntil(lambda: corpo.width() == tela.viewport().width(), timeout=1000)
    # Com a letra grande o vigia refaz as folhas no `Polish`, e o primeiro layout
    # se acerta depois: vale o estado assentado (sobram 8 px a 1280, 2026-10-21).
    qtbot.waitUntil(lambda: not tela.horizontalScrollBar().isVisible(), timeout=1000)
    titulo = tela.label_titulo.geometry()
    if escolha == "normal":
        assert (titulo.x(), titulo.y(), titulo.height()) == (46, 46, 38)
    for botao in [*tela.botoes_tema.values(), *tela.botoes_letra.values()]:
        topo = botao.mapTo(corpo, QPoint(0, 0))
        assert topo.y() >= titulo.y() and topo.y() + botao.height() <= titulo.y() + titulo.height()
        assert topo.x() + botao.width() <= corpo.width() - 57
    # Nenhum botão da barra espremido abaixo do texto (o `min-width` de 140 deixa
    # o layout cortar o texto em vez de rolar): com a letra grande o "Versões de
    # teste" desce para a linha de baixo e a barra cabe inteira.
    for botao in tela.botoes_barra.values():
        assert botao.width() >= botao.sizeHint().width()
    caixa = tela.caixa_canal_testes
    assert caixa.width() >= caixa.sizeHint().width()
    assert caixa.mapTo(corpo, QPoint(0, 0)).x() + caixa.width() <= corpo.width() - 57
    abaixo = caixa.mapTo(corpo, QPoint(0, 0)).y() >= \
        tela.btn_atualizacoes.mapTo(corpo, QPoint(0, 0)).y() + tela.btn_atualizacoes.height()
    assert abaixo is (escolha == "grande")


def test_troca_na_hora_leva_a_caixa_e_traz_de_volta(letra_temporaria, qtbot):
    from sigft.app_qt.views import home as home_mod

    letra.aplicar(letra_temporaria, "normal", gravar=False)   # a folha do app, como na abertura
    tela = home_mod.HomeView(controller=Controller())
    qtbot.addWidget(tela)
    tela.resize(1280 - estilo.LARGURA_BARRA_LATERAL, 850)
    tela.show()
    qtbot.waitExposed(tela)
    caixa = tela.caixa_canal_testes
    antes = caixa.geometry()
    tela.escolher_letra("grande")
    qtbot.waitUntil(lambda: caixa.y() > tela.btn_atualizacoes.y() + tela.btn_atualizacoes.height(),
                    timeout=1000)
    tela.escolher_letra("normal")
    qtbot.waitUntil(lambda: caixa.geometry() == antes, timeout=1000)


def test_seletor_marca_a_letra_que_esta_valendo(letra_temporaria, qtbot):
    # `--smoke --letra grande` não grava: o seletor marca a que vale, não a das prefs.
    from sigft.app_qt.views import home as home_mod

    letra.aplicar(letra_temporaria, "grande", gravar=False)
    assert letra.escolhido() == "normal" and letra.atual() == "grande"
    tela = home_mod.HomeView(controller=Controller())
    qtbot.addWidget(tela)
    assert tela.botoes_letra["grande"].property("ativo") is True


def test_opcao_da_linha_de_comando():
    from sigft.app_qt import main as qmain

    assert qmain._opcao_da_linha_de_comando(["f", "--smoke", "--letra", "grande"], "--letra") == "grande"
    assert qmain._opcao_da_linha_de_comando(["f", "--letra=grande"], "--letra") == "grande"
    assert qmain._opcao_da_linha_de_comando(["f", "--smoke"], "--letra") is None
    assert qmain._tema_da_linha_de_comando(["f", "--tema", "claro"]) == "claro"
