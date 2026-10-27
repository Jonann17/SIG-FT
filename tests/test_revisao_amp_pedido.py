"""O pedido de cada lista para o AMP: o texto dos PDFs (com a página marcada), o `_STATUS_PMIB`
separado por tabulação e quais listas têm o que precisa. Desenho:
`docs/superpowers/specs/2026-10-27-amp-revisao-de-listas-design.md`, §4 e §10.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from _openpyxl_de_verdade import openpyxl_de_verdade
from sigft.services import conferencia_revisoes as cr
from sigft.services import revisao_amp as ra

CODIGO = "#ITA0=Y01TF001&BPB020"
LINHA_DE_REVISAO = "REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: 0A - DATA DE ALTERAÇÃO: 01/09/2026"
CABECALHO = ["ITEM", "QTD.", "UNID.", "DESCRIÇÃO", "CÓDIGO DO MATERIAL", "CÓDIGO PMIB", "STATUS"]


class _Pagina:
    def __init__(self, texto):
        self._texto = texto

    def get_text(self, _modo="text"):
        return self._texto


class _Documento(list):
    def __enter__(self):
        return self

    def __exit__(self, *_erro):
        return False


def _abrir(*paginas):
    return lambda _caminho: _Documento(_Pagina(p) for p in paginas)


def _status(pasta: Path, *, com_cabecalho=True, aba="Lista de Materiais") -> Path:
    caminho = pasta / f"{CODIGO}_STATUS_PMIB.xlsx"
    with openpyxl_de_verdade(ra) as openpyxl:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = aba
        ws.append(["LISTA DE SOBRESSALENTES"])
        ws.append([])
        ws.append([])
        ws.append([LINHA_DE_REVISAO])
        if com_cabecalho:
            ws.append(CABECALHO)
        ws.append([1, 2.0, "PC", "BOMBA\tCENTRÍFUGA", "MAT-1", "100001", "COMPLETO"])
        ws.append([2, 1, "PC", "VÁLVULA", "MAT-2", None, None])
        ws.append([3, 4, "M", "CABO", "MAT-3", "100003", "INICIAR"])
        ws.append([])
        wb.save(caminho)
    return caminho


def _ler_status(caminho):
    with openpyxl_de_verdade(ra):
        return ra.status_pmib_em_tsv(caminho)


# ------------------------------------------------------------------ o PDF

def test_texto_do_pdf_marca_as_paginas():
    texto = ra.texto_do_pdf(Path("x.pdf"), abrir=_abrir("ITEM 1 BOMBA", "ITEM 2 VÁLVULA"))
    assert texto.paginas == 2
    assert texto.texto.startswith("--- página 1 ---\nITEM 1 BOMBA")
    assert "--- página 2 ---\nITEM 2 VÁLVULA" in texto.texto


def test_pdf_so_imagem_e_falta():
    with pytest.raises(ValueError, match="só imagem"):
        ra.texto_do_pdf(Path("x.pdf"), abrir=_abrir("", "   "))


# ------------------------------------------------------------------ o _STATUS_PMIB

def test_status_em_tsv_tem_a_linha_de_revisao_e_o_cabecalho(tmp_path):
    tabela = _ler_status(_status(tmp_path))
    assert tabela.aba == "Lista de Materiais"
    assert tabela.linha_de_revisao == LINHA_DE_REVISAO
    linhas = tabela.tsv.split("\n")
    assert linhas[0] == "\t".join(CABECALHO)
    assert linhas[1] == "1\t2\tPC\tBOMBA CENTRÍFUGA\tMAT-1\t100001\tCOMPLETO"
    assert linhas[2] == "2\t1\tPC\tVÁLVULA\tMAT-2\t\t"
    assert tabela.linhas == 3
    assert tabela.codigos_material == ["MAT-1", "MAT-2", "MAT-3"]


def test_status_sem_cabecalho_avisa(tmp_path):
    with pytest.raises(ValueError, match="cabeçalho"):
        _ler_status(_status(tmp_path, com_cabecalho=False))


def test_status_sem_a_aba_avisa(tmp_path):
    with pytest.raises(ValueError, match="aba"):
        _ler_status(_status(tmp_path, aba="Outra"))


# ------------------------------------------------------------------ quais listas vão

def _lista(codigo=CODIGO, ultima="0B", em_uso="0A", status_real="Aprovado"):
    return cr.ListaNaMapeadora(codigo, ultima, "Em Processo", status_real, em_uso,
                               f"Lista {codigo[-3:]}/{codigo}_STATUS_PMIB.xlsx")


def _pasta(raiz: Path, codigo=CODIGO, pdfs=(), com_status=True) -> Path:
    pasta = raiz / f"Lista {codigo[-3:]}"
    pasta.mkdir(parents=True, exist_ok=True)
    if com_status:
        (pasta / f"{codigo}_STATUS_PMIB.xlsx").write_bytes(b"planilha")
    for revisao in pdfs:
        (pasta / cr.nome_do_pdf(codigo, revisao)).write_bytes(b"%PDF")
    return pasta


def _conferencia(*itens):
    return cr.Conferencia(list(itens), em_dia=0, sem_status_pmib=0)


def test_listas_usam_os_pdfs_baixados_na_sessao(tmp_path):
    pasta = _pasta(tmp_path, pdfs=("0A",))
    baixado = pasta / cr.nome_do_pdf(CODIGO, "0C")
    baixado.write_bytes(b"%PDF")
    downloads = [cr.Download(CODIGO, "0C", baixado, "baixado", "mapeadora desatualizada: o Aconex está na 0C"),
                 cr.Download(CODIGO, "0A", pasta / cr.nome_do_pdf(CODIGO, "0A"), "ja_existia")]
    [lista] = ra.listas_para_amp(_conferencia(cr.ItemConferencia(_lista(), "aprovada", pasta)),
                                 downloads, tmp_path, None)
    assert (lista.revisao_atual, lista.pdf_atual, lista.falta) == ("0C", baixado, "")
    assert lista.pdf_em_uso == pasta / cr.nome_do_pdf(CODIGO, "0A")
    assert lista.status_pmib == pasta / f"{CODIGO}_STATUS_PMIB.xlsx"


def test_listas_sem_download_procuram_pelo_nome(tmp_path):
    pasta = _pasta(tmp_path, pdfs=("0A", "0B"))
    [lista] = ra.listas_para_amp(_conferencia(cr.ItemConferencia(_lista(), "aprovada", pasta)), [], tmp_path, None)
    assert (lista.revisao_atual, lista.pdf_atual.name, lista.pdf_em_uso.name, lista.falta) == (
        "0B", cr.nome_do_pdf(CODIGO, "0B"), cr.nome_do_pdf(CODIGO, "0A"), "")


def test_lista_sem_revisao_em_uso_nao_exige_esse_pdf(tmp_path):
    pasta = _pasta(tmp_path, pdfs=("0",))
    [lista] = ra.listas_para_amp(_conferencia(cr.ItemConferencia(_lista(ultima="0", em_uso=""), "aprovada", pasta)),
                                 [], tmp_path, None)
    assert (lista.pdf_em_uso, lista.falta) == (None, "")


def test_o_que_falta_aparece_e_a_ordem_e_a_das_categorias(tmp_path):
    outro = "#ST00=X01MPB020&MPB020"
    pasta_ok = _pasta(tmp_path, outro, pdfs=("0A", "0B"))
    pasta_sem = _pasta(tmp_path, pdfs=("0A",))
    pasta_sem_status = _pasta(tmp_path / "s", "#ZZ00=1&MPB020", pdfs=("0A", "0B"), com_status=False)
    listas = ra.listas_para_amp(_conferencia(
        cr.ItemConferencia(_lista(outro, status_real="Em Processo"), "em_processo", pasta_ok),
        cr.ItemConferencia(_lista(), "aprovada", pasta_sem),
        cr.ItemConferencia(_lista("#ZZ00=1&MPB020"), "outros", pasta_sem_status)), [], tmp_path, None)
    assert [(lst.item.lista.codigo, lst.falta) for lst in listas] == [
        (CODIGO, "falta: PDF da revisão atual"),
        (outro, ""),
        ("#ZZ00=1&MPB020", "falta: _STATUS_PMIB"),
    ]


def test_lista_sem_pasta_fica_de_fora(tmp_path):
    item = cr.ItemConferencia(_lista(), "outros", None, cr.MOTIVO_SEM_PASTA)
    assert ra.listas_para_amp(_conferencia(item), [], tmp_path, None) == []


# ------------------------------------------------------------------ o pedido

def test_pedido_tem_os_tres_conteudos_e_a_lista(tmp_path):
    pasta = _pasta(tmp_path, pdfs=("0A", "0B"))
    [lista] = ra.listas_para_amp(_conferencia(cr.ItemConferencia(_lista(), "aprovada", pasta)), [], tmp_path, None)
    tabela = ra.TabelaStatus("Lista de Materiais", LINHA_DE_REVISAO, 3, "ITEM\tQTD.", ["MAT-1"])
    pedido = ra.montar_pedido(lista, "1.3.1-rc.2", ler_pdf=lambda c: ra.TextoPdf(2, f"--- página 1 ---\n{c.name}"),
                              ler_status=lambda _c: tabela, hoje=datetime(2026, 10, 27).date())
    assert pedido["modo"] == "revisar"
    # A data de hoje vai junto: a linha de revisão nova leva a DATA DE ALTERAÇÃO, e o modelo
    # não sabe que dia é (revisão final do ramo, 2026-10-27).
    assert pedido["lista"] == {"codigo": CODIGO, "revisao_em_uso": "0A", "revisao_atual": "0B",
                               "status_real": "Aprovado", "status_da_revisao": "Em Processo", "categoria": "aprovada",
                               "data_de_hoje": "27/10/2026"}
    assert pedido["revisao_em_uso"]["arquivo"] == cr.nome_do_pdf(CODIGO, "0A")
    assert pedido["revisao_atual"] == {"arquivo": cr.nome_do_pdf(CODIGO, "0B"), "paginas": 2,
                                       "texto": f"--- página 1 ---\n{cr.nome_do_pdf(CODIGO, '0B')}"}
    assert pedido["status_pmib"] == {"arquivo": f"{CODIGO}_STATUS_PMIB.xlsx", "aba": "Lista de Materiais",
                                     "linha_de_revisao": LINHA_DE_REVISAO, "linhas": 3, "tsv": "ITEM\tQTD."}
    assert pedido["origem"] == {"sigft": "1.3.1-rc.2"}


def test_pedido_sem_revisao_em_uso_manda_null(tmp_path):
    pasta = _pasta(tmp_path, pdfs=("0",))
    [lista] = ra.listas_para_amp(_conferencia(cr.ItemConferencia(_lista(ultima="0", em_uso=""), "aprovada", pasta)),
                                 [], tmp_path, None)
    pedido = ra.montar_pedido(lista, "x", ler_pdf=lambda _c: ra.TextoPdf(1, "t"),
                              ler_status=lambda _c: ra.TabelaStatus("a", "", 0, "", []))
    assert pedido["revisao_em_uso"] is None


def test_data_vira_dd_mm_aaaa():
    assert ra._celula(datetime(2026, 9, 1, 0, 0)) == "01/09/2026"
