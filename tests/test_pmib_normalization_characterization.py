r"""
Teste de caracterização (CP 0.1) — normalização de código PMIB.

Ainda NÃO existe uma função única de normalização de PMIB no código atual —
essa unificação é o próprio objetivo do CP 1.2 (`core/excel/pmib_codes.py:
normalize_pmib()`). Por instrução do CP 0.1, caracterizamos aqui a
implementação single-value mais completa hoje, adotada como normalizador PMIB
"canônico" de referência para a migração:

    AtualizadorStatusPMIB._blindar_numero_pmib (upload_ficha_duplicada.py:677-690)

    def _blindar_numero_pmib(self, valor_celula):
        if valor_celula is None:
            return ""
        if isinstance(valor_celula, (float, int)):
            return f"{float(valor_celula):.4f}"
        texto_limpo = str(valor_celula).replace("'", "").replace(",", ".").strip()
        partes = texto_limpo.split('.')
        if len(partes) == 2 and len(partes[0]) == 10:
            return f"{partes[0]}.{partes[1].ljust(4, '0')}"
        return texto_limpo

Ela cobre os 3 casos citados explicitamente no CP 0.1:
  1. string com zeros faltantes: '4500063671.105' -> '4500063671.1050'
  2. float: 4500063671.1165 -> '4500063671.1165'
  3. apóstrofo (Excel força texto): "'4500063671,1235" -> '4500063671.1235'

DIVERGÊNCIAS registradas (outras variantes INLINE de normalização de PMIB no
código hoje — candidatas a unificação no CP 1.2, NÃO testadas neste arquivo
pois não são funções isoláveis/reaproveitáveis como esta):
  - upload_conditions_backend.py:67-70 — só acrescenta UM '0' e só quando o
    valor já tem exatamente 3 casas decimais (regex `^\d{10}\.\d{3}$`); não
    usa .ljust, não cobre 1 ou 2 casas faltando.
  - pdm_backend.py:182 — usa `.ljust(4, '0')[:4]`: TRUNCA para 4 dígitos se
    houver mais (diferente de _blindar_numero_pmib, que NÃO trunca — ver
    test_mais_de_4_casas_decimais_nao_e_truncado abaixo).
  - frontend.py:1322-1323 (seleção de códigos PMIB, modo "selecionar") — usa
    a mesma lógica de pdm_backend.py:182 (ljust + truncamento [:4]).

Instância criada via `__new__` (o método não usa nenhum atributo de `self`).
"""
from upload_ficha_duplicada import AtualizadorStatusPMIB


def _make_atualizador():
    return AtualizadorStatusPMIB.__new__(AtualizadorStatusPMIB)


def test_string_com_3_casas_decimais_ganha_zero_a_direita():
    # Caso 1 do CP 0.1: '4500063671.105' -> '4500063671.1050'
    atualizador = _make_atualizador()
    resultado = atualizador._blindar_numero_pmib("4500063671.105")
    assert resultado == "4500063671.1050"


def test_float_com_4_casas_decimais_mantem_precisao():
    # Caso 2 do CP 0.1: float 4500063671.1165 -> string com 4 casas, sem os
    # artefatos de ponto flutuante que o valor tem "por baixo dos panos" (em
    # IEEE-754 double, 4500063671.1165 é armazenado como
    # 4500063671.11649990081787109375 — o formatador ':.4f' arredonda
    # corretamente para a representação decimal esperada).
    atualizador = _make_atualizador()
    resultado = atualizador._blindar_numero_pmib(4500063671.1165)
    assert resultado == "4500063671.1165"


def test_string_com_apostrofo_e_virgula_decimal():
    # Caso 3 do CP 0.1 (apóstrofo): Excel força texto com apóstrofo à frente;
    # aqui combinado com vírgula como separador decimal — ambos removidos
    # antes do split em partes inteira/decimal.
    atualizador = _make_atualizador()
    resultado = atualizador._blindar_numero_pmib("'4500063671,1235")
    assert resultado == "4500063671.1235"


def test_none_retorna_string_vazia():
    atualizador = _make_atualizador()
    assert atualizador._blindar_numero_pmib(None) == ""


def test_inteiro_puro_vira_float_formatado_com_4_zeros():
    atualizador = _make_atualizador()
    resultado = atualizador._blindar_numero_pmib(4500063671)
    assert resultado == "4500063671.0000"


def test_mais_de_4_casas_decimais_nao_e_truncado():
    # Peculiaridade importante: `.ljust(4, '0')` só PREENCHE quando a string é
    # mais curta que 4 caracteres; se já tiver mais de 4 dígitos, o valor NÃO
    # é truncado (todos os dígitos originais são preservados). Diverge de
    # pdm_backend.py:182 e frontend.py:1322-1323, que fazem
    # `.ljust(4, '0')[:4]` e TRUNCAM neste mesmo cenário.
    atualizador = _make_atualizador()
    resultado = atualizador._blindar_numero_pmib("4500063671.12345")
    assert resultado == "4500063671.12345"


def test_prefixo_com_menos_de_10_digitos_nao_e_alterado():
    # A blindagem só entra em ação quando a parte antes do ponto tem
    # EXATAMENTE 10 dígitos; caso contrário devolve o texto só limpo (sem
    # apóstrofo/vírgula), sem tentar completar zeros.
    atualizador = _make_atualizador()
    assert atualizador._blindar_numero_pmib("123.45") == "123.45"


def test_texto_sem_ponto_e_devolvido_sem_alteracao():
    atualizador = _make_atualizador()
    resultado = atualizador._blindar_numero_pmib("SEM_PONTO_NENHUM")
    assert resultado == "SEM_PONTO_NENHUM"


def test_espacos_ao_redor_sao_removidos():
    atualizador = _make_atualizador()
    resultado = atualizador._blindar_numero_pmib("  4500063671.5  ")
    assert resultado == "4500063671.5000"
