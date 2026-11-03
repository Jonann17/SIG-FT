"""A Conferência de Revisões: lê a mapeadora (só lê), separa as listas com divergência
de revisão pelo STATUS REAL e baixa os PDFs para a pasta do `_STATUS_PMIB`. Desenho:
`docs/superpowers/specs/2026-10-26-aconex-ao-vivo-design.md`, §5.

A mapeadora é real (openpyxl de verdade), com o hyperlink relativo que o Gestão PMIB
grava. O Aconex é um dublê.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest

from _openpyxl_de_verdade import openpyxl_de_verdade
from sigft.core.aconex.cliente import ErroAconex, Versao
from sigft.services import conferencia_revisoes as cr

COLUNAS = ["N° DOCUMENTO ITAIPU", "DESCRIÇÃO", "ÚLTIMA REVISÃO EMITIDA", "STATUS DA REVISÃO",
           "STATUS REAL", "REVISÃO EM USO", "LINK DA PLANILHA"]
CODIGO = "#ITA0=Y01TF001&BPB020"
OUTRO = "#ST00=X01MPB020&MPB020"
LINK = f"Lista A/{CODIGO}_STATUS_PMIB.xlsx"


def _status_pmib(raiz: Path, codigo: str = CODIGO, subpasta: str = "Lista A") -> Path:
    pasta = raiz / subpasta
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / f"{codigo}_STATUS_PMIB.xlsx"
    arquivo.write_bytes(b"planilha")
    return arquivo


def _gravar_mapeadora(pasta: Path, linhas: list[dict], colunas=COLUNAS) -> Path:
    """Cabeçalho na linha 2; `link` vira hyperlink relativo com o texto "Abrir Box", como no Gestão PMIB."""
    with openpyxl_de_verdade(cr) as openpyxl:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Acompanhamento Sobressalente"
        ws.append(["MAPEAMENTO DAS LISTAS DE SOBRESSALENTES"])
        ws.append(colunas)
        for linha in linhas:
            valores = {"N° DOCUMENTO ITAIPU": linha.get("codigo"), "DESCRIÇÃO": "LISTA",
                       "ÚLTIMA REVISÃO EMITIDA": linha.get("ultima"), "STATUS DA REVISÃO": linha.get("status_rev"),
                       "STATUS REAL": linha.get("status_real"), "REVISÃO EM USO": linha.get("em_uso")}
            ws.append([valores.get(c) for c in colunas])
            if linha.get("link") and "LINK DA PLANILHA" in colunas:
                celula = ws.cell(row=ws.max_row, column=colunas.index("LINK DA PLANILHA") + 1)
                celula.value = "Abrir Box"
                celula.hyperlink = linha["link"]
        caminho = pasta / "Mapeamento Listas de Sobressalentes.xlsx"
        wb.save(caminho)
    return caminho


def _ler(caminho):
    with openpyxl_de_verdade(cr):
        return cr.ler_mapeadora(caminho)


def _lista(codigo=CODIGO, ultima="0B", status_rev="Em Processo", status_real="Aprovado", em_uso="0", link=LINK):
    return cr.ListaNaMapeadora(codigo, ultima, status_rev, status_real, em_uso, link)


def _mapeadora(pasta: Path, *listas) -> cr.Mapeadora:
    return cr.Mapeadora(pasta / "Mapeamento Listas de Sobressalentes.xlsx", datetime(2026, 10, 26, 8, 0), list(listas))


# ---------------------------------------------------------------- a mapeadora

def test_ler_mapeadora_le_as_colunas_o_link_e_a_data(tmp_path):
    caminho = _gravar_mapeadora(tmp_path, [
        {"codigo": CODIGO, "ultima": "0B", "status_rev": "Em Processo", "status_real": "Aprovado",
         "em_uso": "0", "link": LINK},
        {"codigo": OUTRO, "ultima": 1, "status_real": "Em Processo", "em_uso": 1},
        {"codigo": None, "ultima": "0"},
    ])
    os.utime(caminho, (1_790_000_000, 1_790_000_000))
    mapeadora = _ler(caminho)
    assert mapeadora.caminho == caminho
    assert mapeadora.salva_em == datetime.fromtimestamp(1_790_000_000)
    assert mapeadora.listas == [
        # A DESCRIÇÃO é uma das colunas opcionais (DocPack, 2026-11-03).
        cr.ListaNaMapeadora(CODIGO, "0B", "Em Processo", "Aprovado", "0", LINK, descricao="LISTA"),
        cr.ListaNaMapeadora(OUTRO, "1", "", "Em Processo", "1", None, descricao="LISTA"),
    ]


def test_ler_mapeadora_sem_uma_coluna_avisa(tmp_path):
    caminho = _gravar_mapeadora(tmp_path, [{"codigo": CODIGO}], colunas=[c for c in COLUNAS if c != "STATUS REAL"])
    with pytest.raises(ValueError, match="STATUS REAL"):
        _ler(caminho)


# ---------------------------------------------------------------- a regra (§5.2)

def test_sem_link_conta_em_sem_status_pmib(tmp_path):
    conferencia = cr.conferir(_mapeadora(tmp_path, _lista(link=None)), None)
    assert (conferencia.sem_status_pmib, conferencia.em_dia, conferencia.itens) == (1, 0, [])


def test_revisao_igual_conta_em_dia(tmp_path):
    _status_pmib(tmp_path)
    conferencia = cr.conferir(_mapeadora(tmp_path, _lista(ultima="0A", em_uso="0a")), None)
    assert (conferencia.em_dia, conferencia.itens) == (1, [])


def test_revisao_em_uso_vazia_e_divergencia(tmp_path):
    _status_pmib(tmp_path)
    conferencia = cr.conferir(_mapeadora(tmp_path, _lista(ultima="0", em_uso="", status_real="Para Assinatura")), None)
    assert conferencia.em_dia == 0
    assert [(i.categoria, i.motivo) for i in conferencia.itens] == [("aprovada", "")]


def test_sem_ultima_revisao_vai_para_outros(tmp_path):
    _status_pmib(tmp_path)
    conferencia = cr.conferir(_mapeadora(tmp_path, _lista(ultima="", status_real="NÃO EMITIDO")), None)
    assert [(i.categoria, i.motivo) for i in conferencia.itens] == [("outros", "sem revisão emitida no Aconex")]


@pytest.mark.parametrize("status_real, esperada", [
    ("Para Assinatura", "aprovada"), ("APROVADO", "aprovada"),
    ("Em Processo", "em_processo"), ("EM PROCESSO", "em_processo"),
    ("Não Aprovado", "nao_aprovada"), ("NÃO APROVADO", "nao_aprovada"),
    ("Cancelado", "outros"), ("NÃO EMITIDO", "outros"), ("", "outros"),
])
def test_categorias_pelo_status_real(tmp_path, status_real, esperada):
    _status_pmib(tmp_path)
    conferencia = cr.conferir(_mapeadora(tmp_path, _lista(status_real=status_real)), None)
    assert [i.categoria for i in conferencia.itens] == [esperada]


@pytest.mark.parametrize("em_uso, ultima, status_real, esperada", [
    ("0", "0B", "Aprovado", "aprovada"),
    ("0C", "1A", "Em Processo", "em_processo"),
    ("0A", "0B", "Não Aprovado", "nao_aprovada"),
    ("", "0", "Para Assinatura", "aprovada"),
    ("0A", "0A", "Aprovado", "em dia"),
])
def test_os_cinco_casos_do_desenho(tmp_path, em_uso, ultima, status_real, esperada):
    """A tabela da §5.3, que fechou a regra com o Luan."""
    _status_pmib(tmp_path)
    conferencia = cr.conferir(_mapeadora(tmp_path, _lista(em_uso=em_uso, ultima=ultima, status_real=status_real)), None)
    obtida = "em dia" if conferencia.em_dia else conferencia.itens[0].categoria
    assert obtida == esperada


def test_pasta_pelo_link_relativo(tmp_path):
    arquivo = _status_pmib(tmp_path)
    assert cr.resolver_pasta(LINK, tmp_path, CODIGO, None) == arquivo.parent


def test_resolver_status_pmib_devolve_o_arquivo(tmp_path):
    arquivo = _status_pmib(tmp_path)
    assert cr.resolver_status_pmib(LINK, tmp_path, CODIGO, None) == arquivo
    movido = _status_pmib(tmp_path / "raiz", subpasta="Movida")
    assert cr.resolver_status_pmib("Antiga/x_STATUS_PMIB.xlsx", tmp_path, CODIGO, tmp_path / "raiz") == movido


def test_pasta_pelo_codigo_quando_o_link_quebrou(tmp_path):
    arquivo = _status_pmib(tmp_path / "raiz", subpasta="Movida")
    assert cr.resolver_pasta("Antiga/x_STATUS_PMIB.xlsx", tmp_path, CODIGO, tmp_path / "raiz") == arquivo.parent


def test_sem_pasta_vai_para_outros(tmp_path):
    conferencia = cr.conferir(_mapeadora(tmp_path, _lista(status_real="Aprovado")), None)
    assert [(i.categoria, i.pasta, i.motivo) for i in conferencia.itens] == [
        ("outros", None, "_STATUS_PMIB não encontrado")]


def test_por_categoria_na_ordem(tmp_path):
    for codigo in ("A", "B", "C"):
        _status_pmib(tmp_path, codigo, subpasta=codigo)
    conferencia = cr.conferir(_mapeadora(
        tmp_path,
        _lista("A", status_real="Não Aprovado", link="A/A_STATUS_PMIB.xlsx"),
        _lista("B", status_real="Em Processo", link="B/B_STATUS_PMIB.xlsx"),
        _lista("C", status_real="Aprovado", link="C/C_STATUS_PMIB.xlsx")), None)
    grupos = conferencia.por_categoria()
    assert list(grupos) == ["aprovada", "em_processo", "nao_aprovada", "outros"]
    assert {c: [i.lista.codigo for i in itens] for c, itens in grupos.items()} == {
        "aprovada": ["C"], "em_processo": ["B"], "nao_aprovada": ["A"], "outros": []}


def test_nome_do_pdf():
    assert cr.nome_do_pdf("#ITA0=Y01TF001&BPB020", "0A") == "#ITA0=Y01TF001&BPB020[0A].pdf"
    assert cr.nome_do_pdf('A/B\\C:D*"E', "1?") == "A_B_C_D__E[1_].pdf"


# ---------------------------------------------------------------- o download (§5.4)

class _Cliente:
    """Dublê do `ClienteAconex`: versões por código e por revisão; guarda o que baixou."""

    def __init__(self, vigentes=None, historico=None, falhas=()):
        self.vigentes = vigentes or {}
        self.historico = historico or {}
        self.falhas = set(falhas)
        self.baixados = []

    def versao_vigente(self, codigo):
        if codigo in self.falhas:
            raise ErroAconex("A busca no Aconex falhou na página 1 após 5 tentativas (HTTP 500).")
        return self.vigentes.get(codigo)

    def versao(self, codigo, revisao):
        return self.historico.get((codigo, revisao))

    def baixar(self, document_id):
        self.baixados.append(document_id)
        return f"%PDF {document_id}".encode()


def _item(pasta, **kw):
    return cr.ItemConferencia(_lista(**kw), "aprovada", pasta)


def _conferencia(*itens):
    return cr.Conferencia(list(itens), em_dia=0, sem_status_pmib=0)


def test_baixa_a_vigente_com_o_nome_da_revisao_baixada(tmp_path):
    cliente = _Cliente(vigentes={CODIGO: Versao("222", CODIGO, "0C", 3, True)},
                       historico={(CODIGO, "0"): Versao("100", CODIGO, "0", 1, False)})
    downloads = cr.baixar(_conferencia(_item(tmp_path, ultima="0B", em_uso="0")), cliente, log_cb=lambda _m: None)
    vigente = downloads[0]
    assert vigente.situacao == "baixado" and vigente.revisao == "0C"
    assert vigente.caminho == tmp_path / f"{CODIGO}[0C].pdf"
    assert vigente.caminho.read_bytes() == b"%PDF 222"
    assert "mapeadora desatualizada" in vigente.detalhe and "0C" in vigente.detalhe


def test_nao_baixa_de_novo_o_que_ja_existe(tmp_path):
    (tmp_path / f"{CODIGO}[0B].pdf").write_bytes(b"antigo")
    (tmp_path / f"{CODIGO}[0].pdf").write_bytes(b"em uso")
    cliente = _Cliente(vigentes={CODIGO: Versao("222", CODIGO, "0B", 2, True)})
    downloads = cr.baixar(_conferencia(_item(tmp_path, ultima="0B", em_uso="0")), cliente, log_cb=lambda _m: None)
    assert [d.situacao for d in downloads] == ["ja_existia", "ja_existia"]
    assert cliente.baixados == []


def test_nunca_sobrescreve(tmp_path):
    existente = tmp_path / f"{CODIGO}[0B].pdf"
    existente.write_bytes(b"o que ja estava")
    cliente = _Cliente(vigentes={CODIGO: Versao("222", CODIGO, "0B", 2, True)})
    cr.baixar(_conferencia(_item(tmp_path, ultima="0B", em_uso="0B")), cliente, log_cb=lambda _m: None)
    assert existente.read_bytes() == b"o que ja estava"


def test_baixa_tambem_a_revisao_em_uso_que_falta(tmp_path):
    cliente = _Cliente(vigentes={CODIGO: Versao("222", CODIGO, "0B", 2, True)},
                       historico={(CODIGO, "0"): Versao("100", CODIGO, "0", 1, False)})
    downloads = cr.baixar(_conferencia(_item(tmp_path, ultima="0B", em_uso="0")), cliente, log_cb=lambda _m: None)
    assert [(d.revisao, d.situacao) for d in downloads] == [("0B", "baixado"), ("0", "baixado")]
    assert (tmp_path / f"{CODIGO}[0].pdf").read_bytes() == b"%PDF 100"


def test_revisao_em_uso_fora_do_historico_avisa_e_segue(tmp_path):
    logs = []
    cliente = _Cliente(vigentes={CODIGO: Versao("222", CODIGO, "0B", 2, True)})
    downloads = cr.baixar(_conferencia(_item(tmp_path, ultima="0B", em_uso="0")), cliente, log_cb=logs.append)
    assert [(d.revisao, d.situacao) for d in downloads] == [("0B", "baixado")]
    assert any("revisão em uso 0" in m for m in logs)


def test_falha_vira_linha_e_o_resto_continua(tmp_path):
    pasta_b = tmp_path / "b"
    pasta_b.mkdir()
    cliente = _Cliente(vigentes={OUTRO: Versao("333", OUTRO, "1", 1, True)}, falhas={CODIGO})
    downloads = cr.baixar(_conferencia(_item(tmp_path, ultima="0B", em_uso="0B"),
                                       _item(pasta_b, codigo=OUTRO, ultima="1", em_uso="1")),
                          cliente, log_cb=lambda _m: None)
    assert [(d.codigo, d.situacao) for d in downloads] == [(CODIGO, "falhou"), (OUTRO, "baixado")]
    assert "HTTP 500" in downloads[0].detalhe


def test_cancelar_para_o_laco(tmp_path):
    pasta_b = tmp_path / "b"
    pasta_b.mkdir()
    cliente = _Cliente(vigentes={CODIGO: Versao("222", CODIGO, "0B", 2, True),
                                 OUTRO: Versao("333", OUTRO, "1", 1, True)})
    pedidos = iter([False, True])
    downloads = cr.baixar(_conferencia(_item(tmp_path, ultima="0B", em_uso="0B"),
                                       _item(pasta_b, codigo=OUTRO, ultima="1", em_uso="1")),
                          cliente, log_cb=lambda _m: None, cancelado_cb=lambda: next(pedidos))
    assert [d.codigo for d in downloads] == [CODIGO]
