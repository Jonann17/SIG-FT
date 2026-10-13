"""Toda tela do menu abre a tela Qt de verdade, não o aviso de "ainda não migrada".

Rede de segurança do corte: o menu (`catalogo.MENU`) e o registro (`main.TELAS`)
moram em arquivos diferentes, e uma tela portada que ninguém registrou passaria
despercebida -- o app abriria normalmente e mostraria o aviso.
"""
from __future__ import annotations

import pytest

from sigft.app_qt import catalogo
from sigft.app_qt import main as qmain
from sigft.app_qt.views.nao_migrada import TelaComErro, TelaNaoMigrada

# Telas ainda em porte. Esvaziar quando a última entrar em `TELAS`.
PENDENTES = set()

CHAVES_DO_MENU = [item[2] for item in catalogo.MENU if item[0] == "botao"]


def test_menu_e_cards_falam_das_mesmas_telas():
    assert set(CHAVES_DO_MENU) == {chave for chave, *_ in catalogo.MODULOS}


@pytest.mark.parametrize("chave", [c for c in CHAVES_DO_MENU if c not in PENDENTES])
def test_tela_do_menu_esta_registrada(chave):
    assert chave in qmain.TELAS


def test_pendentes_ainda_nao_registradas():
    # Se uma pendente entrou em `TELAS`, tire-a de `PENDENTES` (o teste acima
    # passa a cobri-la).
    assert not PENDENTES & set(qmain.TELAS)


@pytest.fixture
def janela(qt_interface, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    j = qmain.SIG_FT_App()
    qtbot.addWidget(j)
    return j


@pytest.mark.parametrize("chave", [c for c in CHAVES_DO_MENU
                                   if c not in PENDENTES and c not in catalogo.TELAS_BLOQUEADAS])
def test_tela_registrada_monta_sem_erro(janela, chave):
    janela.show_frame(chave)
    tela = janela.pilha.currentWidget()
    assert not isinstance(tela, (TelaNaoMigrada, TelaComErro)), chave


def test_tela_bloqueada_continua_fechada(janela):
    antes = janela.pilha.currentWidget()
    for chave in catalogo.TELAS_BLOQUEADAS:
        janela.show_frame(chave)
        assert janela.pilha.currentWidget() is antes
        assert not janela.botoes_menu[chave].isEnabled()
