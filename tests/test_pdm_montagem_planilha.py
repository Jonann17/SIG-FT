r"""A ficha montada pela PLANILHA de PDMs, e a escolha por revisão no método antigo.

Com openpyxl REAL (ver `tests/_openpyxl_de_verdade.py`): o que se confere é a
ficha que o fornecedor abre, célula a célula.
"""
from __future__ import annotations

import ast
import inspect
import os
import textwrap

import pytest

from _openpyxl_de_verdade import openpyxl_de_verdade
from sigft.core.pdm_catalogo import PDM, Caracteristica, CatalogoPDM, Identidade
from sigft.services import pdm


@pytest.fixture
def openpyxl_real():
    with openpyxl_de_verdade(pdm) as modulo:
        yield modulo


def _pdm(codigo, titulo, revisao, caracteristicas, base=None, identidades=None):
    base = base or titulo.split()[0]
    return PDM(
        codigo=codigo, classe=codigo.split(".")[1], titulo=titulo, nome_base=base,
        revisao=revisao,
        caracteristicas_em_ordem=tuple(
            Caracteristica(nome=nome, ajuda=ajuda, sequencia=i, linha=6 + i)
            for i, (nome, ajuda) in enumerate(caracteristicas, start=1)),
        identidades=tuple(identidades or (Identidade(revisao, titulo, base),)),
    )


ACUMULADOR = _pdm("PDM.1650.001", "ACUMULADOR", 2, [
    ("DIMENSOES", "Indicar as dimensoes."),
    ("MATERIAL", "Indicar o material."),
    ("PESO", None),
])
DISJUNTOR = _pdm("PDM.5925.001", "DISJUNTOR BAIXA TENSAO", 5, [("TENSAO NOMINAL", "")])


def _catalogo(*pdms):
    return CatalogoPDM(pdms=list(pdms), exportado_em="23/09/2026 11:02:02",
                       origem="/pdms/PDMs_SAM-GM_23.09.26.xlsx")


def _template(pasta, openpyxl):
    caminho = os.path.join(str(pasta), "template.xlsx")
    wb = openpyxl.Workbook()
    wb.active.title = "Ficha Técnica Padrão"
    wb.save(caminho)
    return caminho


def _perguntas_da_ficha(caminho, openpyxl):
    ws = openpyxl.load_workbook(caminho)["Ficha Técnica Padrão"]
    return [ws.cell(row=linha, column=3).value for linha in range(79, ws.max_row + 1)
            if ws.cell(row=linha, column=3).value]


# =============================================================================
# A. A ficha pela planilha
# =============================================================================
def test_ficha_pela_planilha_tem_as_perguntas_da_C79_em_ordem_e_sem_nan(tmp_path, openpyxl_real):
    saida = tmp_path / "fichas"
    saida.mkdir()

    msg, _ = pdm.aplicar_templates_fichas_da_planilha(
        [("4500063671.0071", "PDM.1650.001 - ACUMULADOR, , R2", str(saida))],
        _catalogo(ACUMULADOR), _template(tmp_path, openpyxl_real))

    assert msg == "Fichas geradas: 1"
    assert _perguntas_da_ficha(saida / "4500063671.0071.xlsx", openpyxl_real) == [
        "1 - DIMENSOES (Indicar as dimensoes.):",
        "2 - MATERIAL (Indicar o material.):",
        "3 - PESO:",
    ]


def test_ficha_pela_planilha_tem_a_mesma_geometria_do_metodo_antigo(tmp_path, openpyxl_real):
    saida = tmp_path / "fichas"
    saida.mkdir()

    pdm.aplicar_templates_fichas_da_planilha(
        [("4500063671.0071", "PDM.1650.001 - ACUMULADOR, , R2", str(saida))],
        _catalogo(ACUMULADOR), _template(tmp_path, openpyxl_real))
    ws = openpyxl_real.load_workbook(saida / "4500063671.0071.xlsx")["Ficha Técnica Padrão"]

    mescladas = {str(r) for r in ws.merged_cells.ranges}
    assert {"C79:L79", "M79:V79", "C81:L81", "M81:V81"} <= mescladas
    assert ws["C79"].font.size == 8
    assert ws.row_dimensions[79].height == 32
    assert ws["M79"].value is None   # a resposta fica para o fornecedor


def test_pdm_recusado_vira_falha_e_o_lote_segue(tmp_path, openpyxl_real):
    saida = tmp_path / "fichas"
    saida.mkdir()
    logs = []

    msg, log = pdm.aplicar_templates_fichas_da_planilha(
        [("4500063671.0001", "PDM.9999.001 - NAO EXISTE, , R0", str(saida)),
         ("4500063671.0002", "PDM.1650.001 - ACUMULADOR, , R2", str(saida))],
        _catalogo(ACUMULADOR), _template(tmp_path, openpyxl_real), log_callback=logs.append)
    texto = "\n".join(logs)

    assert msg == "Fichas geradas: 1"
    assert not (saida / "4500063671.0001.xlsx").exists()
    assert (saida / "4500063671.0002.xlsx").exists()
    assert "1 falha(s)" in texto
    assert "PDM.9999.001 nao esta na planilha de PDMs" in texto
    assert log == ["FALHA: 4500063671.0001: PDM.9999.001 nao esta na planilha de PDMs "
                   "(exportada em 23/09/2026 11:02:02)"]


def test_o_log_comeca_dizendo_a_planilha_e_a_data(tmp_path, openpyxl_real):
    logs = []

    pdm.aplicar_templates_fichas_da_planilha(
        [], _catalogo(ACUMULADOR), _template(tmp_path, openpyxl_real), log_callback=logs.append)

    assert logs[0] == ("Planilha de PDMs: PDMs_SAM-GM_23.09.26.xlsx, exportada em "
                       "23/09/2026 11:02:02: 1 PDM(s).")


def test_as_revisoes_diferentes_sao_listadas_no_fim_nos_dois_sentidos(tmp_path, openpyxl_real):
    saida = tmp_path / "fichas"
    saida.mkdir()
    logs = []

    msg, _ = pdm.aplicar_templates_fichas_da_planilha(
        [("4500063671.0001", "PDM.5925.001 - DISJUNTOR, BAIXA TENSAO, R1", str(saida)),
         ("4500063671.0002", "PDM.1650.001 - ACUMULADOR, , R3", str(saida))],
        _catalogo(ACUMULADOR, DISJUNTOR), _template(tmp_path, openpyxl_real),
        log_callback=logs.append)
    texto = "\n".join(logs)
    fim = texto[texto.index("── Resumo:"):]

    assert msg == "Fichas geradas: 2 (2 com revisao diferente do portal)"
    assert "PDM precisa subir de revisao no portal (1):" in fim
    assert "4500063671.0001: PDM.5925.001 esta na R1 no portal e na R5 na planilha" in fim
    assert "Planilha atras do portal, exporte uma nova da Itaipu (1):" in fim
    assert "4500063671.0002: PDM.1650.001 esta na R3 no portal, mas a planilha so tem a R2" in fim


def test_planilha_sem_caracteristicas_para_antes_de_comecar(tmp_path, openpyxl_real):
    saida = tmp_path / "fichas"
    saida.mkdir()
    manipulado = CatalogoPDM(pdms=[PDM(codigo="PDM.1650.001", classe="1650", titulo="ACUMULADOR")])

    msg, log = pdm.aplicar_templates_fichas_da_planilha(
        [("4500063671.0001", "PDM.1650.001 - ACUMULADOR, , R2", str(saida))],
        manipulado, _template(tmp_path, openpyxl_real))

    assert "TEMPLATE_PDM" in msg
    assert log == [msg]
    assert os.listdir(saida) == []


# =============================================================================
# B. Método antigo: mais de um arquivo do mesmo PDM na pasta
# =============================================================================
def _pdm_formatado(caminho, openpyxl, pergunta):
    wb = openpyxl.Workbook()
    wb.active.cell(row=1, column=1, value=pergunta)
    wb.save(caminho)


def test_metodo_antigo_usa_o_arquivo_de_revisao_mais_alta(tmp_path, openpyxl_real):
    """A pasta EN traduzida antes e depois de uma regeneração fica com as duas
    versões do mesmo PDM. Antes, a escolha dependia da ordem do disco."""
    pasta = tmp_path / "modificados"
    pasta.mkdir()
    _pdm_formatado(pasta / "PDM_1650_001 - ACUMULADOR_formatado.xlsx", openpyxl_real, "1 - VELHA:")
    _pdm_formatado(pasta / "PDM_1650_001 - ACUMULADOR - R2_formatado.xlsx", openpyxl_real, "1 - NOVA:")
    _pdm_formatado(pasta / "PDM_1650_001 - ACUMULADOR - R1_formatado.xlsx", openpyxl_real, "1 - MEIO:")
    saida = tmp_path / "fichas"
    saida.mkdir()
    logs = []

    pdm.aplicar_templates_fichas(
        [("4500063671.0071", "PDM.1650.001 - ACUMULADOR", str(saida))],
        str(pasta), _template(tmp_path, openpyxl_real), log_callback=logs.append)

    assert _perguntas_da_ficha(saida / "4500063671.0071.xlsx", openpyxl_real) == ["1 - NOVA:"]
    assert "3 arquivos do PDM_1650_001 na pasta" in "\n".join(logs)


# =============================================================================
# C. Uma implementação por conceito
# =============================================================================
def _chama(funcao, nome):
    arvore = ast.parse(textwrap.dedent(inspect.getsource(funcao)))
    return any(isinstance(no, ast.Call)
               and getattr(no.func, "attr", getattr(no.func, "id", None)) == nome
               for no in ast.walk(arvore))


def test_o_passo_formatar_monta_a_pergunta_pela_mesma_regra():
    """O "(nan)" saía de `processar_arquivo_pdm`; a regra da pergunta é uma só."""
    assert _chama(pdm.processar_arquivo_pdm, "montar_pergunta")


def test_o_passo_formatar_usa_a_mesma_tabela_da_regeneracao():
    assert _chama(pdm.salvar_tabela_formatada, "formatar_tabela_de_perguntas")
