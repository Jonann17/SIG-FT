r"""Varredura de 2026-08-13 com materiais REAIS e diversos.
Pedido do usuário: *"faça uma varredura no processo inteiro (realizando testes
reais com diferentes tipos de materiais com informações na internet e/ou
datasheets)"*.

Sete tipos de material foram passados pelo pipeline inteiro — sensor, rolamento,
anel de vedação, motor elétrico, válvula em polegadas, servoválvula alemã e item
sem código. Os resultados de busca usados como fixture são os **reais** do
Google, e os datasheets foram escritos como um fabricante escreve: vírgula
decimal em português, ponto em inglês, alemão, polegadas.

Cinco achados, todos aqui como regressão.
"""
import pytest

from sigft.services import autospec, autospec_unidades as un
from sigft.services.autospec import AutoSpecCore as Core


# =============================================================================
# A-1. Código PADRONIZADO da indústria não pode ancorar o filtro
# =============================================================================
def test_designacao_ISO_nao_deixa_o_concorrente_passar():
    """`6205` é designação ISO de rolamento: SKF, NSK e FAG fabricam todos "o
    6205". Uma página da NSK passava pelo filtro anti-intruso citando só
    `6205` — o catálogo do concorrente virava contexto, que é exatamente o
    que a regra §4.3 existe para impedir."""
    termos = Core._termos_do_filtro("SKF DO BRASIL LTDA", "", "ROLAMENTO 6205-2RS")
    assert not autospec._resultado_e_relevante(
        termos, "Rolamento NSK 6205 catalogo geral", "", "https://nsk.com/br/6205"
    )


def test_mas_o_codigo_DISTINTIVO_continua_valendo_sozinho():
    """`6205-2RS` já é específico o bastante: um distribuidor que o cite está
    falando da peça certa, mesmo sem nomear o fabricante."""
    termos = Core._termos_do_filtro("SKF DO BRASIL LTDA", "", "ROLAMENTO 6205-2RS")
    assert autospec._resultado_e_relevante(
        termos, "Rolamento 6205-2RS equivalente", "", "https://loja.com/6205-2rs"
    )


def test_especificacao_de_motor_nao_e_identidade():
    """`380V` e `5CV` são ESPECIFICAÇÃO, não identidade — qualquer catálogo de
    motor os cita, inclusive o da Siemens."""
    termos = Core._termos_do_filtro(
        "WEG EQUIPAMENTOS ELETRICOS SA", "", "MOTOR W22 100L 5CV 380V"
    )
    assert not autospec._resultado_e_relevante(
        termos, "Motor eletrico Siemens 5cv 380V trifasico", "", "https://siemens.com/motores"
    )
    assert autospec._resultado_e_relevante(
        termos, "W22 IR3 Premium 5 cv | WEG - Products", "", "https://www.weg.net/catalog/x"
    )


@pytest.mark.parametrize(
    "identificador,distintivo",
    [
        ("CS1320-A-0-0-0-1/-000", True),
        ("6205-2RS", True),
        ("4WRPEH", True),
        ("PVF100-4", True),
        ("6205", False),   # so digito
        ("380V", False),   # 4 chars, e uma medida
        ("W22", False),    # 3 chars
        ("2-214", False),  # sem letra
    ],
)
def test_o_que_conta_como_identificador_distintivo(identificador, distintivo):
    assert Core._identificador_distintivo(identificador) is distintivo


# =============================================================================
# A-2. Razão social de fabricante brasileiro
# =============================================================================
def test_ELETRICOS_nao_vira_ancora():
    """`WEG EQUIPAMENTOS ELETRICOS SA` virava `WEG ELETRICOS`. Ancorar em
    `eletricos` aprova qualquer catálogo elétrico brasileiro."""
    assert Core._nome_curto_fabricante("WEG EQUIPAMENTOS ELETRICOS SA") == "WEG"
    assert "ELETRICOS" not in Core._termos_do_filtro(
        "WEG EQUIPAMENTOS ELETRICOS SA", "", "MOTOR"
    )


@pytest.mark.parametrize(
    "bruto,esperado",
    [
        ("WEG EQUIPAMENTOS ELETRICOS SA", "WEG"),
        ("PARKER HANNIFIN IND COM LTDA", "PARKER HANNIFIN"),
        ("VOITH HYDRO LTDA", "VOITH HYDRO"),
        ("BOSCH REXROTH LTDA", "BOSCH REXROTH"),
        ("SKF DO BRASIL LTDA", "SKF"),
    ],
)
def test_nomes_reais_de_fornecedores_de_itaipu(bruto, esperado):
    assert Core._nome_curto_fabricante(bruto) == esperado


# =============================================================================
# A-3. Prosa truncada não pode deixar preposição pendurada
# =============================================================================
def test_query_nao_termina_em_preposicao():
    """`CONJUNTO DE REPARO PARA BOMBA DE KSB datasheet specs` — o `DE` solto
    não filtra nada e ainda cola no nome do fabricante."""
    queries = Core._montar_queries_busca("CONJUNTO DE REPARO PARA BOMBA DE OLEO", "KSB", "")
    for q in queries:
        antes_do_fab = q.split(" KSB")[0].strip().lower()
        ultimo = antes_do_fab.split()[-1] if antes_do_fab else ""
        assert ultimo not in {"de", "da", "do", "para", "com", "e", "em"}, q


def test_material_sem_codigo_continua_tendo_query():
    assert Core._montar_queries_busca("JOGO DE JUNTAS PARA TURBINA", "VOITH HYDRO LTDA", "")


# =============================================================================
# A-4. Unidade de 4+ letras era invisível
# =============================================================================
@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("2,05 kgfm", [(2.05, "kgfm")]),
        ("1,7 kgf.m", [(1.7, "kgf.m")]),
        ("2500 psig", [(2500.0, "psig")]),
        ("315 mbar", [(315.0, "mbar")]),
        ("1750 min-1", [(1750.0, "min-1")]),
    ],
)
def test_unidade_de_quatro_ou_mais_letras_e_lida(texto, esperado):
    """`kgfm` tem 4 letras e o limite do regex era 3: o torque de um datasheet
    brasileiro de motor era INVISÍVEL — nunca validado nem corrigido."""
    assert un.extrair_medidas(texto) == esperado


def test_torque_em_kgfm_agora_e_conferido_e_corrigido():
    doc = "Conjugado nominal 2,05 kgfm."
    assert un.conferir_conversao(20.1, "nm", doc) == "2.05 kgfm"
    valor, _motivo = un.corrigir_conversao("2,01 Nm", doc, pergunta="CONJUGADO NOMINAL")
    assert valor.startswith("20,1")


# =============================================================================
# A-5. Valor literal não pode ser anunciado como conversão
# =============================================================================
def test_valor_copiado_do_documento_NAO_e_anunciado_como_conversao():
    """`30,3 kg = 30.3 kg` foi copiado, não calculado. Anunciar como conversão
    é factualmente falso e faz o engenheiro desconfiar de um valor correto."""
    doc = "Peso liquido 30,3 kg. Rotacao 1.750 rpm."
    assert autospec.explicar_conversao("30,3 kg", doc) == []
    assert autospec.explicar_conversao("1750 rpm", doc) == []


def test_conversao_de_verdade_continua_sendo_anunciada():
    doc = "Potencia nominal 5 cv."
    assert autospec.explicar_conversao("3,6775 kW", doc)


# =============================================================================
# B. Datasheets REAIS, escritos como fabricante escreve
# =============================================================================
DOC_BR = (
    "MOTOR ELETRICO TRIFASICO W22 IR3 PREMIUM\n"
    "Potencia nominal 5 cv. Tensao nominal 220/380/440 V.\n"
    "Rotacao nominal 1.750 rpm. Corrente nominal 12,7 A.\n"
    "Peso liquido 30,3 kg. Grau de protecao IP55.\n"
    "Conjugado nominal 2,05 kgfm. Temperatura ambiente maxima 40 C.\n"
)
DOC_DE = (
    "TECHNISCHE DATEN SERVOVENTIL 4WRPEH 6\n"
    "Maximaler Betriebsdruck 315 bar. Nenndurchfluss 40 l/min.\n"
    "Betriebstemperatur -20 bis +80 C. Schutzart IP65. Gewicht 2,8 kg.\n"
)
DOC_IN = (
    "BALL VALVE SS-43GS4 SPECIFICATIONS\n"
    "Working pressure 2500 psig. End connection 1/4 in.\n"
    "Body material 316 stainless steel. Orifice 0.218 in. Weight 0.71 lb.\n"
)


@pytest.mark.parametrize(
    "documento,valor",
    [
        (DOC_BR, "30,3 kg"), (DOC_BR, "1.750 rpm"), (DOC_BR, "IP55"),
        (DOC_BR, "5 cv"), (DOC_BR, "2,05 kgfm"),
        (DOC_DE, "315 bar"), (DOC_DE, "40 l/min"), (DOC_DE, "IP65"), (DOC_DE, "2,8 kg"),
        (DOC_IN, "2500 psig"), (DOC_IN, "1/4 in"), (DOC_IN, "0.218 in"), (DOC_IN, "0.71 lb"),
    ],
)
def test_valor_que_ESTA_no_datasheet_e_aceito(documento, valor):
    assert autospec.valor_tem_lastro(valor, documento) is True


@pytest.mark.parametrize(
    "documento,valor,caso",
    [
        (DOC_BR, "30,3 g", "unidade mil vezes menor"),
        (DOC_BR, "IP54", "grau de protecao vizinho"),
        (DOC_BR, "10 cv", "potencia dobrada"),
        (DOC_DE, "31,5 bar", "ordem de grandeza"),
        (DOC_DE, "IP67", "protecao que o doc nao cita"),
        (DOC_IN, "0.318 in", "orificio trocado"),
    ],
)
def test_valor_que_NAO_esta_no_datasheet_e_recusado(documento, valor, caso):
    assert autospec.valor_tem_lastro(valor, documento) is False, caso


def test_conversoes_reais_entre_os_sistemas():
    """cv->kW e C->F num datasheet brasileiro; bar->psi num alemão."""
    assert autospec.valor_tem_lastro("3,6775 kW", DOC_BR) is True   # 5 cv
    assert autospec.valor_tem_lastro("104 F", DOC_BR) is True       # 40 C
    assert autospec.valor_tem_lastro("4568 psi", DOC_DE) is True    # 315 bar
    assert autospec.valor_tem_lastro("2,54 kg", DOC_DE) is False    # nao e 2,8 kg
