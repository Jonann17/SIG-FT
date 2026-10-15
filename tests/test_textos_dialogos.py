"""Os textos dos diálogos (`sigft/app/textos_dialogos.py`).

Portado da seção A de `tests/test_app_dialogs.py` (os diálogos da interface
antiga, que saiu em 2026-10-15): texto de interface é aparência, e quem o
muda tem de mudar de propósito. Os diálogos Qt usam estes mesmos objetos
(`sigft/app_qt/widgets/dialogs.py`, `espera.py`, `dialogos_selecao.py`).
"""
from __future__ import annotations

import pytest

from sigft.app import textos_dialogos as textos


def test_sentinela_de_login_e_a_string_que_as_telas_ja_comparavam():
    assert textos.LOGIN_NECESSARIO == "LOGIN_NECESSARIO"


def test_mensagens_de_login_mantem_os_tres_passos():
    for msg in (textos.MSG_LOGIN_SOLTAR_ROBO, textos.MSG_LOGIN_LOTE):
        assert "O navegador foi aberto." in msg
        assert "1. Faça o LOGIN no site." in msg
        assert "2. Navegue até a tela inicial do PMIB." in msg
        assert msg.count("\n") >= 4


def test_as_duas_mensagens_de_login_diferem_so_no_desfecho():
    assert textos.MSG_LOGIN_SOLTAR_ROBO.endswith("soltar o robô.")
    assert textos.MSG_LOGIN_LOTE.endswith("iniciar a automação em lote.")


def test_mensagem_de_falha_ao_salvar_nomeia_a_secao():
    msg = textos.msg_falha_ao_salvar("INFO. GERAIS")
    assert "'INFO. GERAIS'" in msg
    assert "Clique em SALVAR no site" in msg


def test_mensagem_de_ficha_preenchida_nomeia_o_pmib():
    msg = textos.msg_ficha_preenchida("4500063671.0929")
    assert "4500063671.0929" in msg
    assert "pendências" in msg


def test_mensagem_de_excel_bloqueado_diz_o_que_fazer():
    assert "_STATUS_PMIB" in textos.MSG_EXCEL_BLOQUEADO
    assert "FECHE O ARQUIVO" in textos.MSG_EXCEL_BLOQUEADO


@pytest.mark.parametrize("momento, repetir, seguir", [
    ("antes", "Repetir", "Seguir sem eles"),
    ("depois", "Repetir só estes", "Seguir"),
    ("na_hora", "Repetir", "Seguir sem ele"),
])
def test_os_botoes_dos_travados_dizem_o_que_acontece_em_cada_momento(momento, repetir, seguir):
    assert textos.TEXTOS_TRAVADOS[momento]["repetir"] == repetir
    assert textos.TEXTOS_TRAVADOS[momento]["seguir"] == seguir


def test_textos_dos_travados_sem_travessao():
    for momento, valores in textos.TEXTOS_TRAVADOS.items():
        for chave, texto in valores.items():
            assert "—" not in texto, (momento, chave)
