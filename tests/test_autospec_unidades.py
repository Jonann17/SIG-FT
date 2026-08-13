r"""Conversão de unidade conferida (2026-08-13).
Ver `sigft/services/autospec_unidades.py`.

Decisão do usuário: o lastro documental não deve reprovar uma conversão
CORRETA — mas conversão errada continua reprovando. A diferença entre
"aceitar conversão" e "CONFERIR conversão" é a diferença entre confiar no
modelo e verificar o modelo.

O erro que estes testes existem para pegar é o de **ordem de grandeza**:
`3,5 MPa` a partir de `350 bar` é 10x errado e ninguém percebe olhando.
"""
import pytest

from sigft.services import autospec_unidades as un
from sigft.services import autospec


CONTEXTO = (
    "--- WEB DOC: cs1000.pdf ---\n"
    "Maximum operating pressure 350 bar. Weight 41 kg.\n"
    "Operating temperature 0 to +70 C. Shaft diameter 25.4 mm.\n"
    "Flow range 50 to 400 ml/min. Rated power 7.5 kW. Speed 1450 rpm.\n"
)


# =============================================================================
# A. Extração de medidas
# =============================================================================
@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("350 bar", [(350.0, "bar")]),
        ("35MPa", [(35.0, "mpa")]),
        ("25,4 mm", [(25.4, "mm")]),
        ("0 a +70 C", [(0.0, "c"), (70.0, "c")]),
        ("50 l/min", [(50.0, "l/min")]),
        ("sem medida nenhuma", []),
        ("IP55", []),
    ],
)
def test_extracao(texto, esperado):
    assert un.extrair_medidas(texto) == esperado


# =============================================================================
# B. Conversão CORRETA passa
# =============================================================================
@pytest.mark.parametrize(
    "valor,unidade,origem,caso",
    [
        (35, "mpa", "350 bar", "bar -> MPa"),
        (35000, "kpa", "350 bar", "bar -> kPa"),
        (5076, "psi", "350 bar", "bar -> psi (arredondado)"),
        (1.0, "in", "25.4 mm", "mm -> polegada"),
        (0.0254, "m", "25.4 mm", "mm -> metro"),
        (41000, "g", "41 kg", "kg -> grama"),
        (158, "f", "70 c", "Celsius -> Fahrenheit"),
        (0.4, "l/min", "400 ml/min", "ml/min -> l/min"),
        (7500, "w", "7.5 kw", "kW -> W"),
    ],
)
def test_conversao_correta_e_reconhecida(valor, unidade, origem, caso):
    assert un.conferir_conversao(valor, unidade, CONTEXTO) is not None, caso


def test_a_explicacao_diz_de_onde_veio():
    """É a "forma de verificação" pedida: o engenheiro precisa poder refazer
    a conta de cabeça."""
    assert un.conferir_conversao(35, "mpa", CONTEXTO) == "350 bar"


# =============================================================================
# C. Conversão ERRADA continua reprovando — o ponto do módulo
# =============================================================================
@pytest.mark.parametrize(
    "valor,unidade,caso",
    [
        (3.5, "mpa", "ordem de grandeza: 10x menor que o certo"),
        (350, "mpa", "confundiu a unidade, nao converteu"),
        (999, "bar", "numero que nao existe no documento"),
        (100, "kg", "massa que nao esta la"),
        (200, "c", "temperatura inventada"),
    ],
)
def test_conversao_errada_e_reprovada(valor, unidade, caso):
    assert un.conferir_conversao(valor, unidade, CONTEXTO) is None, caso


def test_numero_de_nome_de_arquivo_NAO_vira_medida():
    """Regressão de um falso positivo real, achado ao implementar a herança
    de unidade em intervalo: o `1000` de `cs1000.pdf` herdava o `bar` de
    `350 bar` sete palavras adiante, e `999 bar` passava a conferir contra
    ele dentro da tolerância de 1%. A herança é local por causa disto."""
    assert (1000.0, "bar") not in un.extrair_medidas(CONTEXTO)
    assert un.conferir_conversao(999, "bar", CONTEXTO) is None


def test_intervalo_com_conector_herda_a_unidade():
    """`0 a +70 C`: só o segundo número carrega a unidade, e o primeiro
    precisa ser conferido também — senão bastaria acertar um dos limites."""
    assert un.extrair_medidas("0 a +70 C") == [(0.0, "c"), (70.0, "c")]
    assert un.extrair_medidas("-20 ate +85 C") == [(-20.0, "c"), (85.0, "c")]


def test_intervalo_convertido_confere_os_DOIS_limites():
    ok, _ = un.conferir_texto("32 a 158 F", CONTEXTO)   # 0 C e 70 C
    assert ok is True
    ruim, _ = un.conferir_texto("50 a 158 F", CONTEXTO)  # 10 C nao existe
    assert ruim is False


def test_a_explicacao_aponta_o_numero_CERTO_do_documento():
    """Regressão de um bug real, visto na saída antes de existir este teste:
    `0,4 l/min` era explicado como `= 50 ml/min` (o certo é 400). A causa era
    comparar na unidade BASE: a base da vazão é m³/s, onde `0,4 l/min` e
    `50 ml/min` valem 6,7e-6 e 8,3e-7 — pequenos o bastante para a tolerância
    absoluta aprovar qualquer par. A comparação passou a ser feita na unidade
    da resposta, que é como uma pessoa confere."""
    assert un.conferir_conversao(0.4, "l/min", CONTEXTO) == "400 ml/min"
    assert un.conferir_conversao(0.05, "l/min", CONTEXTO) == "50 ml/min"


def test_vazao_errada_nao_passa_mais():
    """Consequência do mesmo bug: antes, QUALQUER vazão casava."""
    assert un.conferir_conversao(9.9, "l/min", CONTEXTO) is None


def test_grandeza_diferente_nao_casa_por_acaso():
    """`41 kg` no documento não pode aprovar `41 bar` na resposta."""
    assert un.conferir_conversao(41, "bar", CONTEXTO) is None


def test_texto_com_uma_medida_certa_e_uma_errada_reprova():
    ok, _ = un.conferir_texto("de 35 MPa a 999 MPa", CONTEXTO)
    assert ok is False


def test_texto_sem_medida_nenhuma_nao_e_conversao():
    ok, _ = un.conferir_texto("aco inoxidavel", CONTEXTO)
    assert ok is False


# =============================================================================
# D. Integração com o lastro
# =============================================================================
def test_o_lastro_agora_ACEITA_conversao_correta():
    """Era o falso negativo que o usuário apontou: `35 MPa` a partir de
    `350 bar` é certo e estava sendo descartado."""
    assert autospec.valor_tem_lastro("35 MPa", CONTEXTO) is True


def test_o_lastro_continua_recusando_conversao_errada():
    assert autospec.valor_tem_lastro("3,5 MPa", CONTEXTO) is False


def test_o_lastro_continua_recusando_numero_inventado():
    assert autospec.valor_tem_lastro("999 bar", CONTEXTO) is False


def test_valor_literal_continua_passando_sem_precisar_de_conversao():
    assert autospec.valor_tem_lastro("350 bar", CONTEXTO) is True


def test_conversao_de_temperatura_funciona_no_lastro():
    assert autospec.valor_tem_lastro("158 F", CONTEXTO) is True
    assert autospec.valor_tem_lastro("300 F", CONTEXTO) is False


def test_a_conversao_e_ANUNCIADA_no_console():
    """Aprovar em silêncio seria pior que reprovar: o engenheiro precisa
    saber que aquele número foi CALCULADO, não copiado."""
    registro = []

    class _CB:
        def log(self, msg, nivel="info", contexto=None):
            registro.append(str(msg))

    core = autospec.AutoSpecCore.__new__(autospec.AutoSpecCore)
    core.ultimas_fontes_por_campo = {}
    campos = {"var_row_84": {"type": "text", "desc": "6 - PRESSAO", "ref": "M84"}}
    valores = core._filtrar_por_lastro({"var_row_84": "35 MPa"}, campos, CONTEXTO, _CB())

    assert valores == {"var_row_84": "35 MPa"}, "conversao correta tinha de passar"
    assert any("convers" in m.lower() for m in registro), "a conversao passou calada"
    assert any("350 bar" in m for m in registro), "precisa dizer de onde veio"
