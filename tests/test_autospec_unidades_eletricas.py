"""Corrente e tensão na conferência de unidade (2026-11-06).

Rodada da 1.4.0-rc.5 pelo Workflow AMP, acoplador WAGO 750-362: a IA leu "Input current (typ.) at
nominal load (24 V) 280 mA", converteu para `0.28 A` e a conferência reprovou ("nao ha medida para
recalcular"): a tabela de `autospec_unidades` não tinha corrente nem tensão, e o 0.28 era procurado
como número solto. Conta certa, campo vazio.

O cuidado é o "a" do português: `0 a 55 °C` é faixa, `750 à rede` é preposição. Ampere só com A
MAIÚSCULO depois de um número, e nunca quando vem outro número logo depois (`0 A 55` em caixa
alta continua faixa).
"""
from __future__ import annotations

import pytest

from sigft.services import autospec_evidencia as ev
from sigft.services import autospec_unidades as un
from sigft.services.autospec import AutoSpecCore

TRECHO = "Input current (typ.) at nominal load (24 V)\n280 mA"
VALOR = "0.28 A (corrente de entrada típica a 24 V, carga nominal)"
PERGUNTA = "16 - CORRENTE NOMINAL (Indicar a corrente nominal do item em (A))"


# -- A. corrente e tensão são medidas -------------------------------------------------------
@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("280 mA", [(280.0, "mA")]),
        ("0.28 A", [(0.28, "A")]),
        ("16A", [(16.0, "A")]),
        ("10 kA", [(10.0, "kA")]),
        ("24 V", [(24.0, "v")]),
        ("0,5 kV", [(0.5, "kv")]),
        ("100 a 240 V", [(100.0, "v"), (240.0, "v")]),
    ],
)
def test_corrente_e_tensao_sao_medidas(texto, esperado):
    assert un.extrair_medidas(texto) == esperado


# -- B. o "a" do português continua não sendo unidade ---------------------------------------
@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("0 a +55 °C", [(0.0, "c"), (55.0, "c")]),
        ("0 A 55 °C", [(0.0, "c"), (55.0, "c")]),
        ("sistema WAGO I/O 750 à rede", []),
        ("2 a 4 polos", []),
        ("24 VDC (-25 … +30 %)", []),
    ],
)
def test_o_a_da_faixa_e_da_preposicao_nao_e_ampere(texto, esperado):
    assert un.extrair_medidas(texto) == esperado


# -- C. a conta conferida -------------------------------------------------------------------
def test_280_mA_confere_com_0_28_A():
    assert un.conferir_conversao(0.28, "A", TRECHO) == "280 mA"


def test_corrente_dez_vezes_errada_continua_reprovando():
    assert un.conferir_conversao(2.8, "A", TRECHO) is None


def test_kV_confere_com_V():
    assert un.conferir_conversao(0.5, "kv", "Isolation 500 V system/field") == "500 v"


def test_o_valor_da_rodada_sai_do_trecho_com_a_conta_explicada():
    assert ev.valor_sai_do_trecho(VALOR, TRECHO) == (True, ["0.28 A = 280 mA"])


def test_a_tensao_que_ja_passava_continua_passando():
    trecho = "Supply voltage (system) 24 VDC, SELV/PELV (-25 … +30 %)"
    assert ev.valor_sai_do_trecho("24 VDC (-25 … +30 %)", trecho)[0]


def test_a_unidade_do_enunciado_e_o_ampere():
    assert un.unidade_declarada(PERGUNTA) == "A"
    assert un.aplicar_unidade_da_pergunta("0,28", PERGUNTA) == "0,28 A"


# -- D. a rodada da rc.5 --------------------------------------------------------------------
def test_corrente_nominal_da_rodada_entra_como_conversao():
    core = AutoSpecCore.__new__(AutoSpecCore)
    core._modelo_do_item = "750-362"
    core.ultimas_evidencias_por_campo = {"var_row_94": ev.Evidencia(
        tipo="calculo", fonte="Data sheet 750-362.pdf", pagina=2,
        trecho="Input current (typ.) at nominal load (24 V) 280 mA",
        justificativa="280 mA convertido para A.")}
    linhas = []

    class _Cb:
        def log(self, msg, nivel="info", contexto=None):
            linhas.append(str(msg))

    documento = "--- LOCAL DOC: Data sheet 750-362.pdf ---\n[página 2]\n" + TRECHO + "\n"
    aprovados = core._filtrar_por_lastro(
        {"var_row_94": VALOR}, {"var_row_94": {"desc": PERGUNTA}}, documento, _Cb())
    assert aprovados == {"var_row_94": VALOR}
    assert any("0.28 A = 280 mA" in linha for linha in linhas)
