r"""As regras da montagem da ficha pela planilha de PDMs (`services/pdm_planilha.py`).

Lógica pura: os PDMs são montados em memória, sem planilha nem Excel. As
regras numeradas são as da seção 5 de
docs/superpowers/specs/2026-09-23-planilhas-pmib-da-planilha-design.md.
"""
from __future__ import annotations

import pytest

from sigft.core.pdm_catalogo import PDM, Caracteristica, CatalogoPDM, Identidade
from sigft.services import pdm_planilha as regras


def _pdm(codigo="PDM.5925.001", titulo="DISJUNTOR BAIXA TENSAO", base="DISJUNTOR",
         modificador="BAIXA TENSAO", revisao=5,
         caracteristicas=(("TENSAO NOMINAL", "Indicar a tensao nominal."),
                          ("CORRENTE NOMINAL", "")),
         identidades=None):
    if identidades is None:
        identidades = (Identidade(revisao=revisao, titulo=titulo, nome_base=base),)
    return PDM(
        codigo=codigo, classe=codigo.split(".")[1], titulo=titulo, nome_base=base,
        modificador=modificador, revisao=revisao,
        caracteristicas=tuple(nome for nome, _ in caracteristicas),
        caracteristicas_em_ordem=tuple(
            Caracteristica(nome=nome, ajuda=ajuda, sequencia=i, linha=6 + i)
            for i, (nome, ajuda) in enumerate(caracteristicas, start=1)),
        identidades=tuple(identidades),
    )


def _catalogo(*pdms, exportado_em="23/09/2026 11:02:02",
              origem="C:/PDMs/PDMs_SAM-GM_23.09.26.xlsx"):
    return CatalogoPDM(pdms=list(pdms), exportado_em=exportado_em, origem=origem)


# O código duplicado REAL da planilha de 23/09/2026.
ACOPLAMENTO_OU_FIXADOR = _pdm(
    codigo="PDM.3010.007", titulo="ACOPLAMENTO ROSCADO", base="ACOPLAMENTO",
    modificador="ROSCADO", revisao=1,
    caracteristicas=(("NORMAS TECNICAS APLICAVEIS", "Indicar as normas."),),
    identidades=(Identidade(1, "ACOPLAMENTO ROSCADO", "ACOPLAMENTO"),
                 Identidade(0, "FIXADOR", "FIXADOR")),
)


# =============================================================================
# A. O texto da pergunta (regra 3)
# =============================================================================
def test_pergunta_com_ajuda_leva_a_ajuda_entre_parenteses():
    assert regras.montar_pergunta(1, "DIMENSOES", "Indicar as dimensoes.") == \
        "1 - DIMENSOES (Indicar as dimensoes.):"


@pytest.mark.parametrize("vazia", [None, float("nan"), "", "   ", "nan", "NaN", "None"])
def test_pergunta_sem_ajuda_nao_leva_parenteses_nem_nan(vazia):
    """Caso real: em 68 PDMs da planilha de 23/09/2026 TODAS as perguntas
    saíam como "1 - APLICACAO (nan):"."""
    assert regras.montar_pergunta(3, "APLICACAO", vazia) == "3 - APLICACAO:"


def test_pergunta_mantem_espaco_duplo_e_quebra_de_linha_do_meio():
    assert regras.montar_pergunta(1, " VAZAO  NOMINAL ", " Indicar a vazao.\nObserv: FAD ") == \
        "1 - VAZAO  NOMINAL (Indicar a vazao.\nObserv: FAD):"


def test_o_tradutor_le_os_dois_formatos_do_mesmo_jeito():
    """O Tradutor (4.2) corta no primeiro "(" e tira ":. " do fim
    (`services/translator.py`). Com ajuda ou sem, o nome que chega ao Upload
    Specs (4.3) tem de ser o mesmo."""
    def corte_do_tradutor(texto):
        return str(texto).split("(", 1)[0].strip().rstrip(":. ")

    com_ajuda = regras.montar_pergunta(2, "MATERIAL", "Indicar o material.")
    sem_ajuda = regras.montar_pergunta(2, "MATERIAL", None)

    assert corte_do_tradutor(com_ajuda) == corte_do_tradutor(sem_ajuda) == "2 - MATERIAL"


# =============================================================================
# B. O catálogo inteiro (regra 8) e a linha de início do log
# =============================================================================
def test_catalogo_sem_caracteristica_nenhuma_e_recusado():
    manipulado = CatalogoPDM(pdms=[PDM(codigo="PDM.4820.004", classe="4820",
                                       titulo="VALVULA ESFERA")])

    with pytest.raises(regras.PDMRecusado, match="TEMPLATE_PDM"):
        regras.conferir_catalogo(manipulado)


def test_catalogo_da_planilha_da_itaipu_passa():
    regras.conferir_catalogo(_catalogo(_pdm()))


def test_descricao_do_catalogo_traz_arquivo_data_e_total():
    assert regras.descrever_catalogo(_catalogo(_pdm(), ACOPLAMENTO_OU_FIXADOR)) == \
        "Planilha de PDMs: PDMs_SAM-GM_23.09.26.xlsx, exportada em 23/09/2026 11:02:02: 2 PDM(s)."


def test_descricao_sem_data_nao_inventa_data():
    assert regras.descrever_catalogo(_catalogo(_pdm(), exportado_em="")) == \
        "Planilha de PDMs: PDMs_SAM-GM_23.09.26.xlsx: 1 PDM(s)."


# =============================================================================
# C. As perguntas de um material (regras 1, 2, 3, 7)
# =============================================================================
def test_perguntas_saem_numeradas_na_ordem_do_catalogo():
    resultado = regras.perguntas_do_pdm(
        _catalogo(_pdm()), "PDM.5925.001 - DISJUNTOR, BAIXA TENSAO, R5")

    assert resultado.linhas == (
        "1 - TENSAO NOMINAL (Indicar a tensao nominal.):",
        "2 - CORRENTE NOMINAL:",
    )
    assert resultado.pdm.codigo == "PDM.5925.001"
    assert resultado.divergencia == ""


def test_status_sem_codigo_e_recusado():
    with pytest.raises(regras.PDMRecusado, match="sem codigo de PDM"):
        regras.perguntas_do_pdm(_catalogo(_pdm()), "NENHUM")


def test_pdm_fora_da_planilha_e_recusado_com_a_data_da_planilha():
    with pytest.raises(regras.PDMRecusado,
                       match=r"PDM\.9999\.001 nao esta na planilha de PDMs \(exportada em 23/09/2026"):
        regras.perguntas_do_pdm(_catalogo(_pdm()), "PDM.9999.001 - X, , R0")


def test_pdm_sem_caracteristica_e_recusado():
    with pytest.raises(regras.PDMRecusado, match="nenhuma caracteristica"):
        regras.perguntas_do_pdm(_catalogo(_pdm(caracteristicas=())),
                                "PDM.5925.001 - DISJUNTOR, BAIXA TENSAO, R5")


# =============================================================================
# D. Revisão diferente do portal (regras 4, 5, 9)
# =============================================================================
def test_portal_atras_da_planilha_gera_e_avisa():
    """O relatório da Itaipu de 23/09/2026 pede "su nueva revisión" para o
    PDM.5925.001; na planilha nova ele está na R5."""
    resultado = regras.perguntas_do_pdm(
        _catalogo(_pdm()), "PDM.5925.001 - DISJUNTOR, BAIXA TENSAO, R1")

    assert resultado.linhas
    assert resultado.divergencia == regras.PORTAL_ATRAS
    assert resultado.causa == "PDM.5925.001 esta na R1 no portal e na R5 na planilha"
    assert resultado.consequencia == \
        "a ficha saiu com a R5; o PDM precisa subir de revisao no portal"


def test_planilha_atras_do_portal_gera_e_avisa():
    """Decisão do usuário (2026-09-23): gera e avisa, não recusa."""
    resultado = regras.perguntas_do_pdm(
        _catalogo(_pdm()), "PDM.5925.001 - DISJUNTOR, BAIXA TENSAO, R6")

    assert resultado.linhas
    assert resultado.divergencia == regras.PLANILHA_ATRAS
    assert resultado.causa == "PDM.5925.001 esta na R6 no portal, mas a planilha so tem a R5"
    assert resultado.consequencia == \
        "a ficha saiu com a R5; exporte uma planilha nova da Itaipu"


def test_status_sem_revisao_nao_confere_nada():
    resultado = regras.perguntas_do_pdm(_catalogo(_pdm()), "PDM.5925.001 - DISJUNTOR BAIXA TENSAO")

    assert resultado.divergencia == ""


def test_r0_no_portal_e_revisao_de_verdade():
    resultado = regras.perguntas_do_pdm(
        _catalogo(_pdm(revisao=1)), "PDM.5925.001 - DISJUNTOR, BAIXA TENSAO, R0")

    assert resultado.divergencia == regras.PORTAL_ATRAS


# =============================================================================
# E. Código com mais de um nome base (regra 6)
# =============================================================================
def test_codigo_duplicado_com_o_titulo_da_vigente_gera():
    resultado = regras.perguntas_do_pdm(
        _catalogo(ACOPLAMENTO_OU_FIXADOR), "PDM.3010.007 - ACOPLAMENTO, ROSCADO, R1")

    assert resultado.linhas == ("1 - NORMAS TECNICAS APLICAVEIS (Indicar as normas.):",)


def test_codigo_duplicado_com_o_titulo_do_outro_pdm_e_recusado():
    with pytest.raises(regras.PDMRecusado) as erro:
        regras.perguntas_do_pdm(_catalogo(ACOPLAMENTO_OU_FIXADOR), "PDM.3010.007 - FIXADOR, , R0")

    assert "ACOPLAMENTO ROSCADO (R1), FIXADOR (R0)" in str(erro.value)
    assert "O STATUS pede 'FIXADOR'" in str(erro.value)


def test_codigo_duplicado_sem_titulo_no_status_e_recusado():
    with pytest.raises(regras.PDMRecusado):
        regras.perguntas_do_pdm(_catalogo(ACOPLAMENTO_OU_FIXADOR), "PDM.3010.007")


def test_so_o_modificador_mudar_entre_revisoes_nao_recusa():
    """PDM.7010.018 é SERVIDOR CONSOLE na R0 e SERVIDOR na R2: histórico
    legítimo, mesmo nome base. Recusar aqui travaria toda ficha antiga."""
    servidor = _pdm(
        codigo="PDM.7010.018", titulo="SERVIDOR", base="SERVIDOR", modificador="",
        revisao=2, caracteristicas=(("NUMERO DE PROCESSADORES", ""),),
        identidades=(Identidade(2, "SERVIDOR", "SERVIDOR"),
                     Identidade(0, "SERVIDOR CONSOLE", "SERVIDOR")))

    resultado = regras.perguntas_do_pdm(_catalogo(servidor), "PDM.7010.018 - SERVIDOR, CONSOLE, R0")

    assert resultado.linhas == ("1 - NUMERO DE PROCESSADORES:",)
    assert resultado.divergencia == regras.PORTAL_ATRAS


def test_outras_identidades_so_as_de_outro_nome_base():
    assert [i.titulo for i in regras.outras_identidades(ACOPLAMENTO_OU_FIXADOR)] == ["FIXADOR"]
    assert regras.outras_identidades(_pdm()) == []


@pytest.mark.parametrize("texto, esperado", [
    ("PDM.3010.007 - ACOPLAMENTO, ROSCADO, R1", "ACOPLAMENTO ROSCADO"),
    ("PDM.4120.000 - UNIDADE EVAPORADORA, , R1", "UNIDADE EVAPORADORA"),
    ("PDM.4820.004 - VÁLVULA ESFERA", "VALVULA ESFERA"),
    ("PDM.3010.007", ""),
])
def test_titulo_do_pdm_usado(texto, esperado):
    assert regras.titulo_do_pdm_usado(texto) == esperado


# =============================================================================
# F. Nome de arquivo com a revisão
# =============================================================================
def test_nome_de_arquivo_leva_codigo_titulo_e_revisao():
    acumulador = _pdm(codigo="PDM.1650.001", titulo="ACUMULADOR", revisao=2)

    assert regras.nome_de_arquivo(acumulador) == "PDM_1650_001 - ACUMULADOR - R2.xlsx"
    assert regras.nome_de_arquivo(acumulador, sufixo="_formatado") == \
        "PDM_1650_001 - ACUMULADOR - R2_formatado.xlsx"


def test_barra_do_titulo_vira_hifen_no_nome():
    """3 títulos da planilha de 23/09/2026 têm "/": no Windows a barra é
    separador de pasta, e é por eles que o fatiamento antigo falha."""
    pdm = _pdm(codigo="PDM.5445.007", titulo="EXTENSAO/TRONCO TORRE", revisao=1)

    assert regras.nome_de_arquivo(pdm) == "PDM_5445_007 - EXTENSAO-TRONCO TORRE - R1.xlsx"


def test_tab_e_espaco_duplo_do_titulo_viram_um_espaco_no_nome():
    pdm = _pdm(codigo="PDM.4310.026", titulo="TUBO \t\t RIGIDO", revisao=0)

    assert regras.nome_de_arquivo(pdm) == "PDM_4310_026 - TUBO RIGIDO - R0.xlsx"


def test_nome_de_arquivo_sem_revisao_legivel():
    pdm = _pdm(codigo="PDM.1650.001", titulo="ACUMULADOR", revisao=None)

    assert regras.nome_de_arquivo(pdm) == "PDM_1650_001 - ACUMULADOR.xlsx"


@pytest.mark.parametrize("nome, revisao", [
    ("PDM_1650_001 - ACUMULADOR - R2.xlsx", 2),
    ("PDM_1650_001 - ACUMULADOR - R12_formatado.xlsx", 12),
    ("/pasta/PDM_1650_001 - ACUMULADOR - R3_formatado.xlsx", 3),
    ("PDM_1650_001 - ACUMULADOR_formatado.xlsx", None),
    ("PDM_1650_001 - ACUMULADOR.xlsx", None),
    ("PDM_1650_001 - R2D2_formatado.xlsx", None),
])
def test_revisao_no_nome(nome, revisao):
    assert regras.revisao_no_nome(nome) == revisao
