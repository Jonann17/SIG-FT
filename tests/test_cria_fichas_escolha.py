r"""Regras puras da escolha de PDM em duas passadas (2026-10-08).

Spec: docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md.
Sem IA, sem tkinter, sem pandas: listas e dicionários.
"""
from __future__ import annotations

from sigft.services import cria_fichas_escolha as escolha
from sigft.services.cria_fichas_escolha import Interpretacao


# =============================================================================
# 1. A passada 1: o que vai, o que volta
# =============================================================================
def test_itens_para_interpretar_numera_e_leva_descricao_e_marca():
    texto = escolha.itens_para_interpretar([
        {"DESCRIÇÃO": "PLAQUETA EM ALUMINIO", "MARCA/MODELO": "DUPLOMATIC"},
        {"DESCRIÇÃO": "DISPLAY LCD", "MARCA/MODELO": None},
    ])
    assert "### ITEM 1\n- Descrição: PLAQUETA EM ALUMINIO\n- Marca/Modelo: DUPLOMATIC" in texto
    assert "### ITEM 2\n- Descrição: DISPLAY LCD\n- Marca/Modelo: " in texto


def test_itens_para_interpretar_nao_escreve_nan():
    """`NaN` do pandas vira o texto "nan" ao passar por `str`."""
    texto = escolha.itens_para_interpretar([{"DESCRIÇÃO": "X", "MARCA/MODELO": float("nan")}])
    assert "nan" not in texto.lower()


def test_ler_interpretacoes_casa_pelo_numero_e_nao_pela_ordem():
    lidas = escolha.ler_interpretacoes([
        {"item": 2, "e": "INDICADOR DIGITAL", "sinonimos": ["MOSTRADOR"], "serve": ""},
        {"item": 1, "e": "PLAQUETA INDICADORA", "sinonimos": [], "serve": "VALVULA DUPLOMATIC"},
    ], total=2)
    assert lidas[0] == Interpretacao(e="PLAQUETA INDICADORA", serve="VALVULA DUPLOMATIC")
    assert lidas[1] == Interpretacao(e="INDICADOR DIGITAL", sinonimos=("MOSTRADOR",))


def test_ler_interpretacoes_deixa_buraco_onde_faltou():
    lidas = escolha.ler_interpretacoes([{"item": 1, "e": "BOMBA"}], total=3)
    assert lidas[0] is not None and lidas[1] is None and lidas[2] is None


def test_ler_interpretacoes_descarta_e_vazio_numero_ruim_e_lixo():
    lidas = escolha.ler_interpretacoes(
        [{"item": 1, "e": "  "}, {"item": 99, "e": "X"}, {"item": "a", "e": "Y"}, "lixo"],
        total=2)
    assert lidas == [None, None]


def test_ler_interpretacoes_aceita_resposta_que_nao_e_lista():
    assert escolha.ler_interpretacoes({"erro": "x"}, total=2) == [None, None]
    assert escolha.ler_interpretacoes(None, total=1) == [None]


def test_ler_interpretacoes_limita_e_limpa_os_sinonimos():
    lidas = escolha.ler_interpretacoes(
        [{"item": 1, "e": "X", "sinonimos": ["A", "", None, "B", "C", "D", "E"]}], total=1)
    assert lidas[0].sinonimos == ("A", "B", "C", "D")


def test_ler_interpretacoes_tolera_sinonimos_que_nao_sao_lista():
    lidas = escolha.ler_interpretacoes([{"item": 1, "e": "X", "sinonimos": "A, B"}], total=1)
    assert lidas[0].sinonimos == ()


def test_a_consulta_leva_o_que_a_peca_e_e_os_sinonimos_mas_nao_o_que_ela_serve():
    """É o "serve" fora da consulta que tira as válvulas da vaga da plaqueta."""
    interp = Interpretacao(e="PLAQUETA INDICADORA", sinonimos=("PLACA IDENTIFICACAO",),
                           serve="VALVULA DUPLOMATIC")
    consulta = escolha.consulta_da_interpretacao(interp)
    assert consulta == "PLAQUETA INDICADORA PLACA IDENTIFICACAO"
    assert "VALVULA" not in consulta


def test_sem_interpretacao_a_consulta_e_vazia():
    assert escolha.consulta_da_interpretacao(None) == ""


def test_como_dict_e_o_formato_da_revisao():
    assert Interpretacao(e="X", sinonimos=("A",), serve="S").como_dict() == {
        "e": "X", "sinonimos": ["A"], "serve": "S"}
