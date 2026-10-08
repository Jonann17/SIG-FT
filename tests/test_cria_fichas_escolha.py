r"""Regras puras da escolha de PDM em duas passadas (2026-10-08).

Spec: docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md.
Sem IA, sem tkinter, sem pandas: listas e dicionários.
"""
from __future__ import annotations

import pytest

from sigft.core.pdm_catalogo import Caracteristica, CatalogoPDM, PDM
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


# =============================================================================
# 2. Confiança, alternativas e sinais
# =============================================================================
INDICADOR = PDM(codigo="PDM.6685.017", classe="6685", titulo="INDICADOR DIGITAL",
                nome_base="INDICADOR", modificador="DIGITAL",
                caracteristicas=("CARACTERISTICAS DO DISPLAY", "FAIXA DE MEDICAO"),
                caracteristicas_em_ordem=(Caracteristica(nome="Alimentação"),))
VALVULAS = PDM(codigo="PDM.4820.004", classe="4820", titulo="VALVULAS ESFERA",
               nome_base="VALVULAS", modificador="ESFERA")
PLAQUETA = PDM(codigo="PDM.5930.012", classe="5930", titulo="PLAQUETA INDICADORA",
               nome_base="PLAQUETA", modificador="INDICADORA")
CATALOGO = CatalogoPDM(pdms=[INDICADOR, VALVULAS, PLAQUETA])


@pytest.mark.parametrize("bruto,esperado", [
    ("ALTA", "ALTA"), ("media", "MEDIA"), ("MÉDIA", "MEDIA"), (" baixa ", "BAIXA"),
    ("", "BAIXA"), (None, "BAIXA"), ("certeza", "BAIXA"), (0.9, "BAIXA"),
])
def test_normalizar_confianca(bruto, esperado):
    assert escolha.normalizar_confianca(bruto) == esperado


def test_alternativas_resolvidas_pelo_catalogo_com_motivo():
    validas, recusadas = escolha.alternativas_validas(
        {"alternativas": [{"pdm": "PDM.4820.004 - VALVULAS ESFERA", "motivo": "se for válvula"},
                          {"pdm": "PDM.5930.012", "motivo": ""}]},
        CATALOGO, escolhido=INDICADOR)
    assert validas == [
        {"pdm": "PDM.4820.004 - VALVULAS ESFERA", "motivo": "se for válvula"},
        {"pdm": "PDM.5930.012 - PLAQUETA INDICADORA", "motivo": ""},
    ]
    assert recusadas == []


def test_alternativa_fora_do_catalogo_e_recusada():
    validas, recusadas = escolha.alternativas_validas(
        {"alternativas": [{"pdm": "PDM.0000.000 - INVENTADO"}]}, CATALOGO, escolhido=None)
    assert validas == []
    assert recusadas == ["PDM.0000.000 - INVENTADO"]


def test_alternativa_igual_a_escolhida_ou_repetida_sai_sem_ser_recusa():
    validas, recusadas = escolha.alternativas_validas(
        {"alternativas": ["PDM.6685.017 - INDICADOR DIGITAL", "PDM.5930.012",
                          "PDM.5930.012 - PLAQUETA INDICADORA"]},
        CATALOGO, escolhido=INDICADOR)
    assert [v["pdm"] for v in validas] == ["PDM.5930.012 - PLAQUETA INDICADORA"]
    assert recusadas == []


def test_no_maximo_duas_alternativas():
    validas, _ = escolha.alternativas_validas(
        {"alternativas": ["PDM.4820.004", "PDM.5930.012", "PDM.6685.017"]},
        CATALOGO, escolhido=None)
    assert len(validas) == 2


def test_alternativas_ausentes_ou_mal_formadas():
    assert escolha.alternativas_validas({}, CATALOGO, None) == ([], [])
    assert escolha.alternativas_validas({"alternativas": "x"}, CATALOGO, None) == ([], [])


INTERP_DISPLAY = Interpretacao(e="INDICADOR DIGITAL", sinonimos=("MOSTRADOR",))


def test_os_tres_sinais_confirmados():
    sinais = escolha.calcular_sinais(INDICADOR, [INDICADOR], INTERP_DISPLAY,
                                     ["CARACTERISTICAS DO DISPLAY"])
    assert sinais == {"na_busca": True, "nome_base": True, "caracteristicas": True}


def test_na_busca_e_falso_quando_veio_da_lista_completa():
    assert escolha.calcular_sinais(INDICADOR, [PLAQUETA], None, [])["na_busca"] is False


def test_nome_base_aceita_plural_e_acento():
    sinais = escolha.calcular_sinais(VALVULAS, [], Interpretacao(e="VÁLVULA ESFERA"), [])
    assert sinais["nome_base"] is True


def test_nome_base_falha_sem_interpretacao_ou_com_outra_peca():
    assert escolha.calcular_sinais(INDICADOR, [], None, [])["nome_base"] is False
    assert escolha.calcular_sinais(
        INDICADOR, [], Interpretacao(e="PLAQUETA"), [])["nome_base"] is False


def test_caracteristica_citada_tem_de_existir_no_pdm():
    """Inclusive as da revisão vigente, e com prefixo numérico ("5279 - ...")."""
    assert escolha.calcular_sinais(
        INDICADOR, [], None, ["5279 - Caracteristicas do display", "ALIMENTACAO"]
    )["caracteristicas"] is True
    assert escolha.calcular_sinais(
        INDICADOR, [], None, ["CARACTERISTICAS DO DISPLAY", "TORQUE"])["caracteristicas"] is False


def test_sem_caracteristica_citada_o_sinal_e_falso():
    assert escolha.calcular_sinais(INDICADOR, [], None, [])["caracteristicas"] is False
    assert escolha.calcular_sinais(INDICADOR, [], None, None)["caracteristicas"] is False


def test_o_prefixo_numerico_sai_dos_dois_lados():
    """Se o Master um dia trouxer "5279 - NOME", a conferência não pode quebrar."""
    com_prefixo = PDM(codigo="PDM.6685.017", classe="6685", titulo="INDICADOR DIGITAL",
                      nome_base="INDICADOR", caracteristicas=("5279 - CARACTERISTICAS DO DISPLAY",))
    assert escolha.calcular_sinais(
        com_prefixo, [], None, ["CARACTERISTICAS DO DISPLAY"])["caracteristicas"] is True


def test_caracteristicas_inexistentes_lista_so_as_que_o_pdm_nao_tem():
    assert escolha.caracteristicas_inexistentes(
        INDICADOR, ["CARACTERISTICAS DO DISPLAY", " TORQUE ", "", None]) == ["TORQUE"]
    assert escolha.caracteristicas_inexistentes(None, ["TORQUE"]) == []
    assert escolha.caracteristicas_inexistentes(INDICADOR, "TORQUE") == []


def test_sem_pdm_escolhido_nenhum_sinal():
    assert escolha.calcular_sinais(None, [INDICADOR], INTERP_DISPLAY, ["X"]) == {
        "na_busca": False, "nome_base": False, "caracteristicas": False}


@pytest.mark.parametrize("confianca,confirmados,esperado", [
    ("ALTA", 3, ("ALTA", False)),
    ("ALTA", 2, ("ALTA", False)),
    ("ALTA", 1, ("MEDIA", True)),
    ("ALTA", 0, ("MEDIA", True)),
    ("MEDIA", 0, ("MEDIA", False)),
    ("BAIXA", 3, ("BAIXA", False)),
])
def test_confianca_final(confianca, confirmados, esperado):
    chaves = ("na_busca", "nome_base", "caracteristicas")
    sinais = {c: i < confirmados for i, c in enumerate(chaves)}
    assert escolha.confianca_final(confianca, sinais) == esperado
