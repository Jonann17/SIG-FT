r"""O corretor que transformou a rotacao CERTA em errada (ficha 0094, 2026-09-24).

O log do usuario:

    2 campo(s) tiveram a CONTA REFEITA: a IA leu o numero certo do documento
    e converteu errado. O valor gravado e o recalculado:
      · 7 - ROTACAO ...: a IA disse '2860 rpm', gravei '3600 rpm'
        -- 2860 -> 3600 rpm (de 60 hz)

A IA estava certa. O motor e de 2 polos, 2860 rpm a 50 Hz; o `60 Hz` do
documento e a frequencia da REDE ELETRICA. A tabela de unidades tinha
`"hz": 60.0` dentro de `rotacao` -- 1 Hz = 60 rpm --, entao o corretor achou
"a unica medida de rotacao do documento" e reescreveu o valor a partir dela.
Os dois unicos erros do AutoSpec nas quatro fichas comparadas com o AMP sao
estes, e sao do aplicativo, nao da IA.

Tres defeitos, um teste cada:

1. `Hz` num datasheet de motor e frequencia eletrica, nunca rotacao mecanica.
   A relacao entre as duas depende do numero de polos e do escorregamento --
   nao e conversao de unidade.
2. `1/min`, `min⁻¹`, `r/min`, `U/min` (alemao), `tr/min` (frances) e
   `rev/min` SAO rpm, e o modulo nao via nenhum deles. Era por isso que o
   `2860` do documento nao contava como rotacao, e o corretor ia buscar outra.
3. Numero que esta ESCRITO no documento nao e erro de conta. Reescreve-lo e
   fabricar dado.
"""
import pytest

from sigft.services import autospec_unidades as un

PERGUNTA_ROTACAO = "7 - ROTACAO (Indicar a rotação do ventilador rotação por minuto)"


# =============================================================================
# 1. Hz nao e rotacao
# =============================================================================
def test_o_caso_do_usuario_nao_vira_3600():
    """O teste que fecha o defeito: o log mostrava exatamente esta conta."""
    contexto = "Motor 3~ 400 V 60 Hz  Drehzahl 2860"
    corrigido, _motivo = un.corrigir_conversao("2860 rpm", contexto, pergunta=PERGUNTA_ROTACAO)
    assert corrigido != "3600 rpm"
    assert corrigido is None


def test_60_hz_nao_confere_como_3600_rpm():
    """O lastro tambem nao pode aceitar `3600 rpm` a partir de `60 Hz`."""
    assert un.conferir_conversao(3600, "rpm", "Rede: 60 Hz") is None


def test_hz_continua_sendo_medida_de_frequencia():
    """Tirar `Hz` da rotacao nao pode tirar a FREQUENCIA do lastro: a ficha
    tem campo `FREQUENCIA NOMINAL`, e `60 Hz` contra `60 Hz` tem de conferir."""
    assert un.extrair_medidas("Frequencia 60 Hz") == [(60.0, "hz")]
    assert un.conferir_conversao(60, "hz", "Supply: 60 Hz") == "60 hz"


# =============================================================================
# 2. As grafias de rpm que o modulo nao via
# =============================================================================
@pytest.mark.parametrize("escrito", [
    "2860 1/min",
    "n = 2860 min⁻¹",
    "2860 min-1",
    "2860 r/min",
    "2860 U/min",
    "2860 tr/min",
    "2860 rev/min",
    "2860 RPM",
])
def test_toda_grafia_de_rpm_vira_rpm(escrito):
    medidas = un.extrair_medidas(escrito)
    assert len(medidas) == 1, medidas
    valor, unidade = medidas[0]
    assert valor == 2860
    assert un._para_base(valor, unidade) == (2860.0, "rotacao")


def test_rpm_do_documento_em_1_por_min_confere_a_resposta_em_rpm():
    assert un.conferir_texto("2860 rpm", "Nenndrehzahl: 2860 1/min") == (
        True, ["2860 rpm = 2860 rpm"])


# =============================================================================
# 3. Numero escrito no documento nao e reescrito
# =============================================================================
def test_numero_que_esta_no_documento_nao_e_reescrito():
    """`2.5` esta escrito no documento. A resposta `2.5 kW` pode ate estar
    mal rotulada, mas nao e conta errada -- e reescreve-la a partir de outra
    medida (`3.4 hp`) produzia `2,53537966 kW`, um numero que nao existe em
    lugar nenhum."""
    corrigido, motivo = un.corrigir_conversao(
        "2.5 kW", "Motor power: 2.5 (3.4 hp)", pergunta="POTENCIA")
    assert corrigido is None
    assert "2.5" in motivo


def test_a_conta_errada_de_verdade_continua_sendo_refeita():
    """A guarda nao pode matar o corretor: `3,5 MPa` a partir de `350 bar` e
    erro de conta de verdade -- o `3,5` nao esta no documento."""
    corrigido, _motivo = un.corrigir_conversao(
        "3,5 MPa", "Maximum operating pressure: 350 bar", pergunta="PRESSAO")
    assert corrigido == "35 MPa"
