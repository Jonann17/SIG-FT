"""O prompt do AutoSpec, 2026-11-06 (pedido do Luan): o trecho em lista, um por lugar do
documento, e as regras de CERTIFICADO (as aprovações do produto) e PROTEÇÃO (a isolação conta).
A conferência dos vários trechos está em `test_autospec_varios_trechos.py`; o texto inteiro, no
snapshot (`tests/fixtures/prompts/autospec_prompt.txt`).
"""
from __future__ import annotations

from sigft.core.llm import prompts


# -- o prompt -----------------------------------------------------------------------------

def _prompt():
    return prompts.montar_autospec("ACOPLADOR 750-362", "WAGO", "Acoplador Modbus TCP", "CONTEXTO", "CAMPOS")


def test_o_prompt_explica_a_lista_de_trechos():
    texto = _prompt()
    assert "Todo número do valor tem de aparecer no trecho" in texto
    assert '"trecho": ["...", "..."]' in texto


def test_o_prompt_diz_que_certificado_sao_as_aprovacoes_do_produto():
    texto = _prompt()
    assert "Campo de CERTIFICADO" in texto
    assert "aprovações e certificações que o documento dá ao produto" in texto


def test_o_prompt_diz_que_a_isolacao_conta_como_protecao():
    texto = _prompt()
    assert "Campo de PROTEÇÃO" in texto
    assert "isolação" in texto
