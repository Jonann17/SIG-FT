r"""Propriedades do prompt da passada 1 (`interpretar_material`, 2026-10-08).

Spec: docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md §4.1.
"""
from __future__ import annotations

from sigft.core.llm import prompts


def _prompt():
    return prompts.montar_interpretar_material("<<<ITENS>>>")


def test_interpola_os_itens():
    assert "<<<ITENS>>>" in _prompt()


def test_pede_as_quatro_chaves_do_contrato():
    texto = _prompt()
    for chave in ("item", "e", "sinonimos", "serve"):
        assert f'"{chave}"' in texto, chave


def test_separa_o_que_a_peca_e_do_que_ela_serve():
    texto = _prompt()
    assert "PLAQUETA EM ALUMINIO PARA VALVULA DUPLOMATIC" in texto
    assert "nunca o equipamento que ela serve" in texto


def test_pede_vocabulario_de_catalogo_sem_marca():
    assert "sem marca" in _prompt().lower()


def test_nao_pede_codigo_de_pdm():
    """A passada 1 não vê o catálogo: um código vindo dela seria inventado."""
    assert "PDM." not in _prompt()


def test_amarra_a_resposta_ao_numero_do_item():
    assert "### ITEM N" in _prompt()


def test_manda_responder_so_o_json():
    assert "Responda APENAS com a lista JSON" in _prompt()
