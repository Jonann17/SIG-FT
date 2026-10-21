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


# =============================================================================
# C. A ficha em inglês pela planilha (2026-10-21)
# =============================================================================
# O tradutor é injetado (`traduzir: list[str] -> list[str]`), sempre: o motor
# de verdade (IA, ou o que o dono escolher depois) não entra na suíte.
def _motor(chamadas=None, falhar=False, mudo=()):
    def traduzir(textos):
        if chamadas is not None:
            chamadas.append(list(textos))
        if falhar:
            raise OSError("rede bloqueada")
        return [None if t in mudo else f"EN {t}" for t in textos]
    return traduzir


def _em_ingles(tmp_path, openpyxl, lista, traduzir, **kw):
    saida = tmp_path / "fichas"
    saida.mkdir(exist_ok=True)
    lista = [(pmib, pdm_usado, str(saida)) for pmib, pdm_usado in lista]
    resultado = pdm.aplicar_templates_fichas_da_planilha(
        lista, _catalogo(ACUMULADOR, DISJUNTOR), _template(tmp_path, openpyxl),
        idioma="en", traduzir=traduzir, pasta_traducao=str(tmp_path / "traducao"), **kw)
    return saida, resultado


def _perguntas_em_ingles(caminho, openpyxl):
    ws = openpyxl.load_workbook(caminho)[pdm.NOME_DA_ABA_EM_INGLES]
    return [ws.cell(row=linha, column=3).value for linha in range(79, ws.max_row + 1)
            if ws.cell(row=linha, column=3).value]


def test_em_ingles_as_perguntas_da_planilha_saem_traduzidas(tmp_path, openpyxl_real):
    saida, (msg, _) = _em_ingles(tmp_path, openpyxl_real,
                                 [("4500063671.0071", "PDM.1650.001 - ACUMULADOR, , R2")], _motor())

    assert msg == "Fichas geradas: 1"
    # O número e os dois-pontos não vão ao tradutor; a instrução vai junto.
    assert _perguntas_em_ingles(saida / "4500063671.0071.xlsx", openpyxl_real) == [
        "1 - EN DIMENSOES (Indicar as dimensoes.):",
        "2 - EN MATERIAL (Indicar o material.):",
        "3 - EN PESO:",
    ]


def test_em_ingles_cada_pergunta_vai_uma_vez_ao_tradutor_no_lote_todo(tmp_path, openpyxl_real):
    """Duas fichas do mesmo PDM: as 3 perguntas viajam uma vez, antes de
    montar a primeira ficha."""
    chamadas = []
    _em_ingles(tmp_path, openpyxl_real,
               [("4500063671.0001", "PDM.1650.001 - ACUMULADOR, , R2"),
                ("4500063671.0002", "PDM.1650.001 - ACUMULADOR, , R2")], _motor(chamadas))

    assert chamadas == [["DIMENSOES (Indicar as dimensoes.)", "MATERIAL (Indicar o material.)", "PESO"]]


def test_em_portugues_o_tradutor_nao_e_chamado(tmp_path, openpyxl_real):
    saida = tmp_path / "fichas"
    saida.mkdir()

    def proibido(textos):
        pytest.fail("ficha em portugues nao traduz")

    msg, _ = pdm.aplicar_templates_fichas_da_planilha(
        [("4500063671.0071", "PDM.1650.001 - ACUMULADOR, , R2", str(saida))],
        _catalogo(ACUMULADOR), _template(tmp_path, openpyxl_real), traduzir=proibido,
        pasta_traducao=str(tmp_path / "traducao"))

    assert msg == "Fichas geradas: 1"
    assert not (tmp_path / "traducao").exists()


def test_tradutor_fora_do_ar_deixa_em_portugues_avisa_e_NAO_para(tmp_path, openpyxl_real):
    logs = []
    saida, (msg, _) = _em_ingles(tmp_path, openpyxl_real,
                                 [("4500063671.0071", "PDM.1650.001 - ACUMULADOR, , R2")],
                                 _motor(falhar=True), log_callback=logs.append)
    texto = "\n".join(logs)

    assert msg == "Fichas geradas: 1"
    assert _perguntas_em_ingles(saida / "4500063671.0071.xlsx", openpyxl_real) == [
        "1 - DIMENSOES (Indicar as dimensoes.):",
        "2 - MATERIAL (Indicar o material.):",
        "3 - PESO:",
    ]
    assert "rede bloqueada" in texto
    assert "4500063671.0071: 3 pergunta(s) sem traducao" in texto
    assert "ficaram em portugues" in texto


def test_so_a_pergunta_que_nao_traduziu_fica_em_portugues(tmp_path, openpyxl_real):
    logs = []
    saida, _ = _em_ingles(tmp_path, openpyxl_real,
                          [("4500063671.0071", "PDM.1650.001 - ACUMULADOR, , R2")],
                          _motor(mudo={"PESO"}), log_callback=logs.append)

    assert _perguntas_em_ingles(saida / "4500063671.0071.xlsx", openpyxl_real) == [
        "1 - EN DIMENSOES (Indicar as dimensoes.):",
        "2 - EN MATERIAL (Indicar o material.):",
        "3 - PESO:",
    ]
    assert "4500063671.0071: 1 pergunta(s) sem traducao" in "\n".join(logs)


def test_o_glossario_vence_o_tradutor_e_o_cache_evita_a_segunda_viagem(tmp_path, openpyxl_real):
    pasta = tmp_path / "traducao"
    pasta.mkdir()
    (pasta / "_GLOSSARIO_PT_EN.txt").write_text("PESO = WEIGHT\n", encoding="utf-8")
    chamadas = []
    lista = [("4500063671.0071", "PDM.1650.001 - ACUMULADOR, , R2")]

    saida, _ = _em_ingles(tmp_path, openpyxl_real, lista, _motor(chamadas))
    assert _perguntas_em_ingles(saida / "4500063671.0071.xlsx", openpyxl_real)[2] == "3 - WEIGHT:"
    assert ["PESO"] not in chamadas and len(chamadas) == 1

    _em_ingles(tmp_path, openpyxl_real, lista, _motor(chamadas))
    assert len(chamadas) == 1, "a segunda rodada deveria sair do cache"


def test_sem_glossario_a_pasta_ganha_o_de_exemplo(tmp_path, openpyxl_real):
    _em_ingles(tmp_path, openpyxl_real, [("4500063671.0071", "PDM.1650.001 - ACUMULADOR, , R2")], _motor())
    assert (tmp_path / "traducao" / "_GLOSSARIO_PT_EN.txt").exists()
    assert (tmp_path / "traducao" / "_CACHE_TRADUCAO.json").exists()


def test_em_ingles_sem_motor_usa_o_motor_padrao(tmp_path, openpyxl_real, monkeypatch):
    from sigft.services import traducao_pdm

    pedidos = []
    monkeypatch.setattr(traducao_pdm, "motor_padrao",
                        lambda **k: pedidos.append(k) or _motor())
    saida, _ = _em_ingles(tmp_path, openpyxl_real,
                          [("4500063671.0071", "PDM.1650.001 - ACUMULADOR, , R2")], None)

    assert len(pedidos) == 1 and "callbacks" in pedidos[0]
    assert _perguntas_em_ingles(saida / "4500063671.0071.xlsx", openpyxl_real)[0].startswith("1 - EN ")
