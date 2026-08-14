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


# =============================================================================
# E. Correção da conta errada, em vez de descarte (2026-08-13)
# =============================================================================
r"""Pedido do usuário: quando a IA converte errado, o dado de origem é REAL —
o que está errado é só a aritmética, e aritmética é o que um computador faz
sem errar. Descartar joga fora informação boa."""

CTX_UMA_PRESSAO = "Maximum operating pressure 350 bar. Weight 41 kg."
CTX_DUAS_PRESSOES = "Maximum operating pressure 350 bar. Peak pressure 210 bar."


def test_conta_errada_e_REFEITA_quando_a_origem_e_unica():
    valor, motivo = un.corrigir_conversao("3,5 MPa", CTX_UMA_PRESSAO)
    assert valor == "35 MPa"
    assert "350 bar" in motivo


def test_origem_AMBIGUA_nao_e_chutada():
    """Com duas pressões no documento, o erro deixa de ser aritmético e passa
    a ser de LEITURA: qual delas o campo pedia? Chutar trocaria um erro
    visível por um invisível."""
    valor, motivo = un.corrigir_conversao("3,5 MPa", CTX_DUAS_PRESSOES)
    assert valor is None
    assert "350 bar" in motivo and "210 bar" in motivo, "precisa listar as opcoes"


def test_grandeza_ausente_no_documento_nao_e_inventada():
    valor, motivo = un.corrigir_conversao("50 Nm", CTX_UMA_PRESSAO)
    assert valor is None
    assert "torque" in motivo


def test_a_precisao_e_a_MAIS_COMPLETA_possivel():
    """Decisão do usuário (2026-08-13): preferir a informação mais completa.

    A versão anterior arredondava pela precisão da fonte (`41 kg` -> `90,4
    lb`). Arredondar DESCARTA informação, e quem lê a ficha pode arredondar
    depois — o caminho inverso é impossível."""
    valor, _ = un.corrigir_conversao("100 lb", CTX_UMA_PRESSAO, pergunta="Peso")
    assert valor == "90,3895275 lb", valor


def test_nao_sobra_ruido_de_ponto_flutuante():
    """`90.38950000000001` seria precisão falsa de outro tipo."""
    valor, _ = un.corrigir_conversao("100 lb", CTX_UMA_PRESSAO, pergunta="Peso")
    assert "0000000" not in valor


def test_valor_ja_correto_nao_e_mexido():
    assert un.corrigir_conversao("35 MPa", CTX_UMA_PRESSAO)[0] is None


def test_o_lastro_grava_o_valor_CORRIGIDO():
    registro = []

    class _CB:
        def log(self, msg, nivel="info", contexto=None):
            registro.append(str(msg))

    core = autospec.AutoSpecCore.__new__(autospec.AutoSpecCore)
    core.ultimas_fontes_por_campo = {}
    campos = {"c1": {"type": "text", "desc": "6 - PRESSAO (MPa)", "ref": "M1"}}
    valores = core._filtrar_por_lastro({"c1": "3,5 MPa"}, campos, CTX_UMA_PRESSAO, _CB())

    assert valores == {"c1": "35 MPa"}, "devia ter gravado o valor recalculado"
    assert any("CONTA REFEITA" in m for m in registro)
    assert any("3,5" in m and "35 MPa" in m for m in registro), "precisa mostrar antes e depois"


def test_quando_nao_da_para_corrigir_o_motivo_aparece_no_console():
    registro = []

    class _CB:
        def log(self, msg, nivel="info", contexto=None):
            registro.append(str(msg))

    core = autospec.AutoSpecCore.__new__(autospec.AutoSpecCore)
    core.ultimas_fontes_por_campo = {}
    campos = {"c1": {"type": "text", "desc": "6 - PRESSAO (MPa)", "ref": "M1"}}
    valores = core._filtrar_por_lastro({"c1": "3,5 MPa"}, campos, CTX_DUAS_PRESSOES, _CB())

    assert valores == {}
    assert any("nao diz qual" in m for m in registro)


# =============================================================================
# F. Bugs achados auditando este módulo (2026-08-13)
# =============================================================================
def test_codigo_alfanumerico_NAO_e_conferido_so_pelos_digitos():
    """Bug real e grave: `IP65` era APROVADO contra um documento que dizia
    `IP67`, porque o `65` aparecia noutro lugar (`65 mm`). O grau de proteção
    errado entrava na ficha pelo caminho que existe para impedir isso."""
    ctx = "Protection class IP67. Cable length 65 mm."
    assert autospec.valor_tem_lastro("IP67", ctx) is True
    assert autospec.valor_tem_lastro("IP65", ctx) is False


def test_separador_de_milhar_e_ambiguo_e_as_DUAS_leituras_valem():
    """`2.500` vale 2,5 em datasheet inglês e 2500 em documento português.
    Adivinhar errado aqui é um erro de MIL VEZES."""
    assert un.leituras("2.500") == [2.5, 2500.0]
    assert un.leituras("25.4") == [25.4], "3 digitos e o gatilho; 1 nao"
    assert autospec.valor_tem_lastro("2.500 mm", "Overall length 2500 mm.") is True
    assert autospec.valor_tem_lastro("2.500 mm", "Cable 2.5 mm.") is True
    assert autospec.valor_tem_lastro("2.500 mm", "Length 900 mm.") is False


def test_numero_errado_na_MESMA_unidade_nao_e_corrigido():
    """Bug real, achado na varredura de 2026-08-13: a IA respondeu `0 bar` e
    o código devolvia `350 bar`. Nenhuma aritmética leva de 0 a 350 — aquilo
    era um palpite ruim virando dado.

    Correção só vale quando houve de fato uma CONVERSÃO. Mesma unidade e
    número diferente não é erro de conta: é número errado, e "corrigir"
    seria inventar."""
    valor, _motivo = un.corrigir_conversao("0 bar", "Pressure 350 bar.")
    assert valor is None
    valor, _motivo = un.corrigir_conversao("999 bar", "Pressure 350 bar.")
    assert valor is None


def test_mas_a_conversao_entre_unidades_continua_sendo_corrigida():
    assert un.corrigir_conversao("3,5 MPa", "Pressure 350 bar.")[0] == "35 MPa"


@pytest.mark.parametrize("entrada", [None, "", "   ", "\x00\x01", "a" * 3000])
def test_entrada_estranha_nao_quebra(entrada):
    autospec.valor_tem_lastro(entrada, CONTEXTO)
    un.corrigir_conversao(entrada, CONTEXTO)


@pytest.mark.parametrize("ctx", [None, "", "sem numero nenhum"])
def test_contexto_estranho_nao_quebra(ctx):
    assert autospec.valor_tem_lastro("35 MPa", ctx) is False
    assert un.corrigir_conversao("35 MPa", ctx)[0] is None


# =============================================================================
# G. Varredura de 2026-08-13 (pedido do usuário: "abre a possibilidade de mais
#    bugs estarem possibilitados")
# =============================================================================
CTX_UNIDADES = "Weight 41 kg. Pressure 350 bar. Shaft 25.4 mm."


@pytest.mark.parametrize(
    "valor,esperado,caso",
    [
        ("41 kg", True, "literal"),
        ("41 g", False, "MESMO numero, unidade MIL VEZES menor"),
        ("41000 g", True, "conversao correta"),
        ("0,041 t", True, "conversao correta para cima"),
        ("350 bar", True, "literal"),
        ("350 kPa", False, "mesmo numero, prefixo errado"),
        ("35 MPa", True, "conversao correta"),
        ("25,4 mm", True, "literal"),
        ("25,4 cm", False, "mesmo numero, ordem de grandeza errada"),
        ("1 in", True, "25,4 mm = 1 polegada"),
    ],
)
def test_numero_com_unidade_e_conferido_como_MEDIDA(valor, esperado, caso):
    """Bug real da varredura: `41 g` era APROVADO contra um documento que diz
    `41 kg`, porque o `41` estava lá e o caminho literal nunca olhava a
    unidade. Mil vezes de diferença — o mesmo tipo de erro do separador de
    milhar, por outro caminho."""
    assert autospec.valor_tem_lastro(valor, CTX_UNIDADES) is esperado, caso


# --- desempate pela pergunta -------------------------------------------------
CTX_TRES_PRESSOES = (
    "Maximum operating pressure 350 bar. Peak pressure 210 bar. "
    "Burst pressure 700 bar."
)


@pytest.mark.parametrize(
    "pergunta,esperado",
    [
        ("6 - PRESSAO DE TRABALHO", "35 MPa"),
        ("8 - PRESSAO DE PICO", "21 MPa"),
        ("9 - PRESSAO DE RUPTURA", "70 MPa"),
    ],
)
def test_o_enunciado_do_campo_desempata(pergunta, esperado):
    """Pedido do usuário: duas medidas da mesma grandeza não é motivo para
    descartar — o campo DIZ qual quer. `PRESSAO DE TRABALHO` casa com
    "Maximum **operating** pressure" pelo glossário multilíngue que o
    retrieval já usa."""
    valor, _motivo = un.corrigir_conversao("3,5 MPa", CTX_TRES_PRESSOES, pergunta=pergunta)
    assert valor == esperado


def test_pergunta_que_NAO_desempata_continua_devolvendo_vazio():
    """Escolher sem ter como saber seria trocar erro visível por invisível."""
    valor, motivo = un.corrigir_conversao("3,5 MPa", CTX_TRES_PRESSOES, pergunta="PRESSAO")
    assert valor is None
    assert "350 bar" in motivo and "210 bar" in motivo


def test_empate_na_pontuacao_tambem_devolve_vazio():
    ctx = "Operating pressure 350 bar. Operating pressure 210 bar."
    valor, _m = un.corrigir_conversao("3,5 MPa", ctx, pergunta="PRESSAO DE TRABALHO")
    assert valor is None


def test_a_janela_e_a_FRASE_e_nao_um_numero_de_caracteres():
    """A 1ª versão pegava 90 caracteres para trás, e as duas medidas
    enxergavam a palavra `operating` — pontuavam igual e o desempate nunca
    acontecia. O limite tem de ser semântico, não métrico."""
    janelas = {v: j for v, _u, j in un._medidas_com_janela(CTX_TRES_PRESSOES)}
    assert "peak" not in janelas[350.0]
    assert "operating" not in janelas[210.0]
