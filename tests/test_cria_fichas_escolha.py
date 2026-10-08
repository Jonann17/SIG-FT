r"""Regras puras da escolha de PDM em duas passadas (2026-10-08).

Spec: docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md.
Sem IA, sem tkinter, sem pandas: listas e dicionários.
"""
from __future__ import annotations

import json

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


# =============================================================================
# 3. O que a tela de revisão mostra
# =============================================================================
def _linha_rev(pdm="PDM.5930.012 - PLAQUETA INDICADORA", final="ALTA", **extra):
    """Uma linha como o `preparar_para_revisao` devolve: tem `pdm_ia`."""
    linha = {"pdm_escolhido": pdm, "pdm_ia": pdm, "confianca_final": final}
    linha.update(extra)
    return linha


def test_ordem_poe_o_que_precisa_de_olho_primeiro():
    linhas = [_linha_rev(final="ALTA"), _linha_rev(final="BAIXA"),
              _linha_rev(pdm="NENHUM", final=""), _linha_rev(final="MEDIA"),
              _linha_rev(final="BAIXA")]
    assert escolha.ordem_para_revisao(linhas) == [2, 1, 4, 3, 0]


def test_ordem_sem_ia_mantem_a_planilha():
    """Modo "Pular IA": o PDM vem da planilha, NENHUM inclusive, e a ordem
    não muda."""
    linhas = [{"pdm_escolhido": "PDM.1"}, {"pdm_escolhido": "NENHUM"}]
    assert escolha.ordem_para_revisao(linhas) == [0, 1]


@pytest.mark.parametrize("linha,esperado", [
    (_linha_rev(final="ALTA"), "ALTA"),
    (_linha_rev(final="MEDIA"), "MÉDIA"),
    (_linha_rev(final="MEDIA", rebaixada=True), "MÉDIA ↓"),
    (_linha_rev(final="BAIXA"), "BAIXA"),
    (_linha_rev(pdm="NENHUM", final="", origem_do_nenhum="ia"), "PDM NOVO?"),
    (_linha_rev(pdm="NENHUM", final="", origem_do_nenhum="sem_resposta"), "SEM RESPOSTA"),
    (_linha_rev(pdm="NENHUM", final="", origem_do_nenhum="fora_do_catalogo"), "FORA DO CATÁLOGO"),
    ({"pdm_escolhido": "PDM.1"}, ""),
    ({"pdm_escolhido": "NENHUM"}, ""),  # "Pular IA": não foi a IA que disse NENHUM
])
def test_rotulo_de_confianca(linha, esperado):
    assert escolha.rotulo_de_confianca(linha) == esperado


class _BoolDoNumpy:
    """`numpy.True_ is True` é falso, e é o que a linha do pandas pode
    entregar numa coluna só de booleanos."""

    def __bool__(self):
        return True

    def __str__(self):
        return "True"


def test_rebaixada_vale_tambem_para_o_booleano_do_numpy():
    linha = _linha_rev(final="MEDIA", rebaixada=_BoolDoNumpy())
    assert escolha.rotulo_de_confianca(linha) == "MÉDIA ↓"


def test_texto_do_porque_junta_justificativa_conferencias_e_leitura():
    texto = escolha.texto_do_porque({
        "justificativa": "é um display",
        "sinais": {"na_busca": True, "nome_base": False, "caracteristicas": True},
        "interpretacao": {"e": "INDICADOR DIGITAL"},
    })
    assert texto == ("Por quê: é um display\n"
                     "Conferências: na busca ✓ · nome base ✗ · características ✓\n"
                     "A IA leu: INDICADOR DIGITAL")
    assert "—" not in texto


def test_texto_do_porque_vazio_sem_dados():
    assert escolha.texto_do_porque({"pdm_escolhido": "PDM.1"}) == ""


def test_sugestoes_sao_o_2o_e_o_3o_lugar_com_motivo():
    sugestoes = escolha.sugestoes_da_linha(
        {"alternativas": [{"pdm": "PDM.4820.004 - VALVULAS ESFERA", "motivo": "se for válvula"},
                          {"pdm": "PDM.5930.012 - PLAQUETA INDICADORA", "motivo": ""}]},
        CATALOGO)
    assert [(p.codigo, r) for p, r in sugestoes] == [
        ("PDM.4820.004", "2º lugar: se for válvula"), ("PDM.5930.012", "3º lugar")]


def test_sugestoes_sem_alternativas_ou_sem_catalogo():
    assert escolha.sugestoes_da_linha({}, CATALOGO) == []
    assert escolha.sugestoes_da_linha({"alternativas": [{"pdm": "PDM.5930.012"}]}, None) == []


def test_juntar_sugestoes_fixa_no_topo_sem_repetir():
    juntos = escolha.juntar_sugestoes([(PLAQUETA, "2º lugar")], [INDICADOR, PLAQUETA], 40)
    assert [p.codigo for p in juntos] == ["PDM.5930.012", "PDM.6685.017"]


def test_juntar_sugestoes_respeita_o_limite():
    assert len(escolha.juntar_sugestoes([(PLAQUETA, "x")], [INDICADOR, VALVULAS], 2)) == 2


# =============================================================================
# 4. Calibração: o que a IA disse x o que o usuário escolheu (spec §4.7)
# =============================================================================
def _linha_cal(final, **extra):
    linha = {
        "pdm_ia": "PDM.6685.017 - INDICADOR DIGITAL", "pdm_escolhido": final,
        "alternativas": [{"pdm": "PDM.5930.012 - PLAQUETA INDICADORA", "motivo": "x"},
                         {"pdm": "PDM.4820.004 - VALVULAS ESFERA", "motivo": "y"}],
        "confianca": "ALTA", "confianca_final": "MEDIA",
        "sinais": {"na_busca": True, "nome_base": False, "caracteristicas": False},
        "interpretacao": {"e": "INDICADOR DIGITAL"},
        "descricao_original": "DISPLAY", "marca_modelo": "ACME",
    }
    linha.update(extra)
    return linha


@pytest.mark.parametrize("final,posicao,trocou", [
    ("PDM.6685.017 - INDICADOR DIGITAL", 1, False),
    ("PDM.5930.012 - PLAQUETA INDICADORA", 2, True),
    ("PDM.4820.004 - VALVULAS ESFERA", 3, True),
    ("PDM.1111.111 - OUTRO", 0, True),
])
def test_posicao_do_final(final, posicao, trocou):
    registro = escolha.registro_de_calibracao(_linha_cal(final), "2026-10-08T10:00:00")
    assert registro["posicao_do_final"] == posicao
    assert registro["trocou"] is trocou


def test_nenhum_mantido_conta_como_primeiro_lugar():
    registro = escolha.registro_de_calibracao(
        _linha_cal("NENHUM", pdm_ia="NENHUM", alternativas=[]), "d")
    assert registro["posicao_do_final"] == 1
    assert registro["trocou"] is False


def test_linha_sem_pdm_ia_nao_entra():
    """Modo "Pular IA": não há o que calibrar."""
    assert escolha.registro_de_calibracao({"pdm_escolhido": "PDM.1"}, "d") is None
    assert escolha.registro_de_calibracao({"pdm_ia": float("nan")}, "d") is None


def test_alternativa_em_texto_tambem_conta_na_posicao():
    registro = escolha.registro_de_calibracao(
        _linha_cal("PDM.5930.012 - PLAQUETA INDICADORA",
                   alternativas=["PDM.5930.012 - PLAQUETA INDICADORA"]), "d")
    assert registro["posicao_do_final"] == 2


def test_o_registro_diz_por_que_a_ia_ficou_em_nenhum():
    """Item que a IA nem respondeu não é um NENHUM dela: a conta de acerto
    precisa poder separar os dois."""
    registro = escolha.registro_de_calibracao(
        _linha_cal("PDM.1111.111 - OUTRO", pdm_ia="NENHUM", alternativas=[],
                   origem_do_nenhum="sem_resposta"), "d")
    assert registro["ia"]["origem_do_nenhum"] == "sem_resposta"
    assert escolha.registro_de_calibracao(_linha_cal("X"), "d")["ia"]["origem_do_nenhum"] == ""


def test_gravar_calibracao_acrescenta_uma_linha_json_por_item(tmp_path):
    destino = tmp_path / "escolha_pdm.jsonl"
    n = escolha.gravar_calibracao(
        [_linha_cal("PDM.5930.012 - PLAQUETA INDICADORA"), {"pdm_escolhido": "PDM.1"}],
        modelos={"passada_1": "m1", "passada_2": "m2"}, caminho=destino, data="D")
    n2 = escolha.gravar_calibracao([_linha_cal("PDM.6685.017 - INDICADOR DIGITAL")],
                                   caminho=destino, data="D")
    linhas = destino.read_text(encoding="utf-8").splitlines()
    assert (n, n2, len(linhas)) == (1, 1, 2)
    primeiro = json.loads(linhas[0])
    assert primeiro["final"] == "PDM.5930.012 - PLAQUETA INDICADORA"
    assert primeiro["ia"]["confianca_final"] == "MEDIA"
    assert primeiro["modelos"] == {"passada_1": "m1", "passada_2": "m2"}
    assert primeiro["marca"] == "ACME"


def test_gravar_calibracao_nunca_levanta(tmp_path):
    """Um diretório no lugar do arquivo: o registro não pode travar a automação."""
    assert escolha.gravar_calibracao([_linha_cal("X")], caminho=tmp_path, data="D") == 0


def test_gravar_calibracao_sem_nada_para_gravar(tmp_path):
    destino = tmp_path / "x.jsonl"
    assert escolha.gravar_calibracao([{"pdm_escolhido": "PDM.1"}], caminho=destino) == 0
    assert not destino.exists()
