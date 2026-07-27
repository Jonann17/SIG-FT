r"""
Testes do Checkpoint 1.2 — `sigft/core/excel/pmib_codes.py`.

Cobre `normalize_pmib()` (os 3 casos citados explicitamente no CP 0.1 +
bordas, espelhando `tests/test_pmib_normalization_characterization.py` —
ver docstring daquele arquivo para o "porquê" de cada caso) e
`extract_pmib_code()` (+ as 3 variantes auxiliares:
`extract_pmib_code_full`, `find_pmib_code_in_text`,
`extract_contract_pmib_code`).

Este arquivo testa a IMPLEMENTAÇÃO NOVA e ÚNICA diretamente (função pura,
sem precisar instanciar nenhuma classe de backend) — é o complemento dos
testes de caracterização do CP 0.1, que continuam validando que os MÉTODOS
antigos (`AtualizadorStatusPMIB._blindar_numero_pmib`,
`DatasheetAnalyzer.extract_pmib_code`, `AutoSpecCore.extract_pmib_code`)
passaram a DELEGAR para cá sem quebrar (exceto a correção intencional do
analyzer — ver tests/test_analyzer_backend_characterization.py).
"""
from sigft.core.excel.pmib_codes import (
    extract_contract_pmib_code,
    extract_pmib_code,
    extract_pmib_code_full,
    find_pmib_code_in_text,
    normalize_pmib,
)


# ===========================================================================
# normalize_pmib — os 3 casos do plano (CP 0.1) + bordas
# ===========================================================================

def test_string_com_3_casas_decimais_ganha_zero_a_direita():
    # Caso 1 do CP 0.1: '4500063671.105' -> '4500063671.1050'
    assert normalize_pmib("4500063671.105") == "4500063671.1050"


def test_float_com_4_casas_decimais_mantem_precisao():
    # Caso 2 do CP 0.1: float 4500063671.1165 -> string com 4 casas exatas.
    assert normalize_pmib(4500063671.1165) == "4500063671.1165"


def test_string_com_apostrofo_e_virgula_decimal():
    # Caso 3 do CP 0.1 (apóstrofo): Excel força texto com apóstrofo à
    # frente; aqui combinado com vírgula como separador decimal.
    assert normalize_pmib("'4500063671,1235") == "4500063671.1235"


def test_none_retorna_string_vazia():
    assert normalize_pmib(None) == ""


def test_inteiro_puro_vira_float_formatado_com_4_zeros():
    assert normalize_pmib(4500063671) == "4500063671.0000"


def test_mais_de_4_casas_decimais_nao_e_truncado():
    # Decisão canônica do CP 1.2: NÃO trunca (diverge de pdm_backend.py:182
    # e frontend.py:1322-1323, que faziam `.ljust(4, '0')[:4]`).
    assert normalize_pmib("4500063671.12345") == "4500063671.12345"


def test_prefixo_com_menos_de_10_digitos_nao_e_alterado():
    assert normalize_pmib("123.45") == "123.45"


def test_texto_sem_ponto_e_devolvido_sem_alteracao():
    assert normalize_pmib("SEM_PONTO_NENHUM") == "SEM_PONTO_NENHUM"


def test_espacos_ao_redor_sao_removidos():
    assert normalize_pmib("  4500063671.5  ") == "4500063671.5000"


def test_string_com_apenas_1_casa_decimal_faltando():
    # Cobertura de borda que upload_conditions_backend.py:67-70 e
    # frontend.py:2082-2085 NÃO cobriam (só tratavam exatamente 3 casas).
    assert normalize_pmib("4500063671.1") == "4500063671.1000"


def test_string_com_2_casas_decimais_faltando():
    assert normalize_pmib("4500063671.12") == "4500063671.1200"


def test_apostrofo_sem_virgula():
    assert normalize_pmib("'4500063671.5") == "4500063671.5000"


def test_multiplos_pontos_nao_e_alterado():
    # Mais de um ponto -> `partes` tem mais de 2 elementos -> devolve só o
    # texto limpo, sem tentar completar zeros (mesma regra do canônico
    # original: `len(partes) == 2` é condição estrita).
    assert normalize_pmib("1.2.3") == "1.2.3"


def test_float_negativo_ou_zero_nao_quebra():
    assert normalize_pmib(0) == "0.0000"


# ===========================================================================
# extract_pmib_code — fix do CP 1.2 (basename ANTES do regex)
# ===========================================================================

def test_extrai_4_ultimos_digitos_do_codigo_pmib():
    assert extract_pmib_code("4500063671.1234_STATUS_PMIB.xlsx") == "1234"


def test_retorna_none_sem_padrao_pmib():
    assert extract_pmib_code("ficha_sem_codigo.xlsx") is None


def test_retorna_none_para_string_vazia():
    assert extract_pmib_code("") is None


def test_decimal_com_menos_de_4_digitos_nao_casa():
    assert extract_pmib_code("4500063671.12_curto.xlsx") is None


def test_decimal_com_mais_de_4_digitos_usa_so_os_4_primeiros():
    assert extract_pmib_code("4500063671.123456_longo.xlsx") == "1234"


def test_usa_basename_do_caminho_recebido():
    caminho = "C:/pasta/qualquer/4500063671.1234_STATUS_PMIB.xlsx"
    assert extract_pmib_code(caminho) == "1234"


def test_ignora_pmib_presente_apenas_no_diretorio():
    # O CASO CENTRAL do fix do CP 1.2: o diretório "parece" outro PMIB
    # (9999999999.8888), mas o código correto é o do ARQUIVO (1234) — ver
    # docs/refatoracao/PENDENCIAS.md e
    # tests/test_analyzer_backend_characterization.py /
    # tests/test_autospec_backend_characterization.py.
    caminho = "pasta_saida/9999999999.8888/4500063671.1234_STATUS_PMIB.xlsx"
    assert extract_pmib_code(caminho) == "1234"


def test_caminho_so_com_pmib_no_diretorio_e_arquivo_sem_padrao_retorna_none():
    caminho = "pasta_saida/9999999999.8888/relatorio_final.xlsx"
    assert extract_pmib_code(caminho) is None


# ===========================================================================
# extract_pmib_code_full — código completo, fração de tamanho livre
# (upload_tech_specs_backend.extrair_codigo_pmib_arquivo)
# ===========================================================================

def test_extract_pmib_code_full_captura_fracao_de_4_digitos():
    assert extract_pmib_code_full("4500063671.1234_STATUS_PMIB.xlsx") == "4500063671.1234"


def test_extract_pmib_code_full_captura_fracao_maior_que_4_digitos():
    assert extract_pmib_code_full("4500063671.123456_longo.xlsx") == "4500063671.123456"


def test_extract_pmib_code_full_usa_basename():
    caminho = "pasta_saida/9999999999.8888/4500063671.1234_STATUS_PMIB.xlsx"
    assert extract_pmib_code_full(caminho) == "4500063671.1234"


def test_extract_pmib_code_full_retorna_none_sem_padrao():
    assert extract_pmib_code_full("sem_codigo.xlsx") is None


# ===========================================================================
# find_pmib_code_in_text — texto livre, SEM basename
# (GerenciadorFilaPMIB.montar_fila_processamento, coluna OBSERVAÇÕES)
# ===========================================================================

def test_find_pmib_code_in_text_encontra_no_meio_da_frase():
    texto = "Cópia da ficha original 4500063671.1234, revisar antes de salvar."
    assert find_pmib_code_in_text(texto) == "4500063671.1234"


def test_find_pmib_code_in_text_nao_aplica_basename():
    # Diferente de extract_pmib_code_full: aqui um "/" no texto NÃO deve
    # truncar a busca (não é um caminho de arquivo) -- o PMIB aparece ANTES
    # da barra e ainda assim precisa ser encontrado.
    texto = "Ver PMIB base 4500063671.1234 / conferir pasta compartilhada"
    assert find_pmib_code_in_text(texto) == "4500063671.1234"


def test_find_pmib_code_in_text_retorna_none_sem_padrao():
    assert find_pmib_code_in_text("Sem nenhum código aqui.") is None


# ===========================================================================
# extract_contract_pmib_code — gated pelo prefixo de contrato (config.py)
# ===========================================================================

def test_extract_contract_pmib_code_aceita_prefixo_configurado():
    assert extract_contract_pmib_code("4500063671.1234_ficha.xlsx") == "4500063671.1234"


def test_extract_contract_pmib_code_rejeita_prefixo_diferente():
    # Formato "PMIB" válido, mas contrato diferente do configurado -> None
    # (diferente de extract_pmib_code_full, que aceitaria qualquer prefixo).
    assert extract_contract_pmib_code("9999999999.1234_ficha.xlsx") is None


def test_extract_contract_pmib_code_exige_exatamente_4_digitos():
    assert extract_contract_pmib_code("4500063671.123_ficha.xlsx") is None


def test_extract_contract_pmib_code_usa_basename():
    caminho = "pasta/9999999999.9999/4500063671.1234_ficha.xlsx"
    assert extract_contract_pmib_code(caminho) == "4500063671.1234"
