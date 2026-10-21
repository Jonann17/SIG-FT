r"""A ficha montada pela PLANILHA de PDMs.

Com openpyxl REAL (ver `tests/_openpyxl_de_verdade.py`): o que se confere é a
ficha que o fornecedor abre, célula a célula.
"""
from __future__ import annotations

import os

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


def test_ficha_pela_planilha_tem_a_geometria_da_ficha(tmp_path, openpyxl_real):
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
# B. O template é lido do disco uma vez só (CP 4.3)
# =============================================================================
def test_o_template_e_lido_do_disco_uma_unica_vez(tmp_path, openpyxl_real, monkeypatch):
    """Cada ficha reabre o template de `BytesIO`: com 3 fichas, nenhuma
    leitura dele vem do disco (os bytes foram lidos antes do laço)."""
    saida = tmp_path / "fichas"
    saida.mkdir()
    template = _template(tmp_path, openpyxl_real)
    origens = []
    real = pdm.load_workbook

    def espiao(fonte, *args, **kwargs):
        origens.append("disco" if isinstance(fonte, (str, os.PathLike)) else "memoria")
        return real(fonte, *args, **kwargs)

    monkeypatch.setattr(pdm, "load_workbook", espiao)
    lista = [(f"4500063671.000{i}", "PDM.1650.001 - ACUMULADOR, , R2", str(saida)) for i in range(3)]

    msg, _ = pdm.aplicar_templates_fichas_da_planilha(lista, _catalogo(ACUMULADOR), template)

    assert msg == "Fichas geradas: 3"
    assert origens == ["memoria"] * 3


def test_template_que_nao_abre_vira_mensagem_e_nao_excecao(tmp_path):
    msg, log = pdm.aplicar_templates_fichas_da_planilha(
        [], _catalogo(ACUMULADOR), str(tmp_path / "nao_existe.xlsx"))

    assert "Erro ao abrir template" in msg
    assert log and "Erro ao abrir template" in log[0]
