r"""
Teste de caracterização (CP 0.1) — pdm_backend.extrair_pdm_id.

`extrair_pdm_id` é uma função de MÓDULO (não depende de estado de instância),
definida em pdm_backend.py:18-20:

    def extrair_pdm_id(nome_arquivo):
        match = re.search(r'PDM_\d{4}_\d{3}', nome_arquivo)
        return match.group() if match else None

Estes testes capturam o comportamento ATUAL do regex — não corrigem nem
"melhoram" nada; documentam o que o código faz hoje, peculiaridades incluídas.
"""
from pdm_backend import extrair_pdm_id


def test_extrai_id_pdm_de_nome_de_arquivo_tipico():
    nome = "PDM_2024_001 - Valvula Industrial.xlsx"
    assert extrair_pdm_id(nome) == "PDM_2024_001"


def test_extrai_id_pdm_mesmo_recebendo_caminho_completo():
    nome = "pasta/subpasta/PDM_2024_001 - Valvula Industrial.xlsx"
    assert extrair_pdm_id(nome) == "PDM_2024_001"


def test_retorna_none_quando_nao_ha_padrao_pdm():
    assert extrair_pdm_id("ficha_generica_sem_pdm.xlsx") is None


def test_retorna_none_para_string_vazia():
    assert extrair_pdm_id("") is None


def test_e_case_sensitive_minusculo_nao_casa():
    # Peculiaridade: o regex não usa re.IGNORECASE, então "pdm_..." em
    # minúsculas não é reconhecido como PDM válido.
    assert extrair_pdm_id("pdm_2024_001.xlsx") is None


def test_retorna_primeiro_match_quando_ha_mais_de_um_id_pdm_no_nome():
    nome = "PDM_2024_001 (copia) e tambem PDM_2025_002.xlsx"
    assert extrair_pdm_id(nome) == "PDM_2024_001"


def test_digitos_insuficientes_nao_casam():
    # "PDM_24_1" tem menos dígitos que o padrão exige (4 e 3) -> não casa.
    assert extrair_pdm_id("PDM_24_1.xlsx") is None


def test_digitos_extras_apos_o_padrao_ainda_casam_parcialmente():
    # Peculiaridade: o regex não é ancorado ao fim (sem "$"), então dígitos
    # extras logo após o padrão de 3 dígitos são simplesmente ignorados — o
    # match para assim que os 3 dígitos exigidos são consumidos.
    assert extrair_pdm_id("PDM_2024_0011_extra.xlsx") == "PDM_2024_001"
