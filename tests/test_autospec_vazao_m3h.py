r"""`164 m, 190 m` no log da ficha 0094 (2026-09-24): vazao lida como METRO.

O usuario nao conseguiu anexar o PDF de 166 paginas, entao a causa foi
reproduzida pelo mecanismo. O PyMuPDF extrai o expoente de `m³/h` como um
caractere SEPARADO (outra linha, ou com espaco antes), e o texto chega como
`164 m\n3\n/h` ou `164 m ³/h`. O modulo lia so o `m`: 164 METROS. Pior: mesmo
`164 m³/h` bem escrito nunca era vazao, porque o regex de unidade nao aceitava
digito depois do `m` -- o `m3/h` da tabela de vazao era inalcancavel.
"""
import pytest

from sigft.services import autospec_unidades as un


@pytest.mark.parametrize("escrito", [
    "164 m³/h", "164 m3/h", "164 m\n3\n/h", "Luftleistung 164 m ³/h", "164 m³ / h",
])
def test_vazao_em_m3_por_hora_e_vazao(escrito):
    assert un.extrair_medidas(escrito) == [(164.0, "m3/h")]


def test_o_caso_do_log_nao_vira_comprimento():
    """A mensagem do log: 'o documento tem 2 medidas de comprimento (164 m, 190 m)'."""
    medidas = un.extrair_medidas("164 m\n3\n/h\n190 m\n3\n/h")
    assert all(u == "m3/h" for _v, u in medidas)


def test_m3_por_hora_confere_contra_litros_por_minuto():
    assert un.conferir_conversao(2733.3, "l/min", "164 m³/h") == "164 m3/h"


def test_expoente_de_area_solto_vira_m2():
    assert un.extrair_medidas("Area 12 m ²") == [(12.0, "m2")]


@pytest.mark.parametrize("escrito,esperado", [
    ("cabo 10 m 3 condutores", [(10.0, "m")]),    # o 3 e outra coisa
    ("velocidade 5 m/s", []),                      # m/s nao e vazao
    ("comprimento 250 mm", [(250.0, "mm")]),
])
def test_metro_de_verdade_continua_metro(escrito, esperado):
    assert un.extrair_medidas(escrito) == esperado
