r"""Fabricante lido do PDF anexado vira ancora da busca web (pedido de 2026-09-24).

Nas fichas 0084, 0086 e 0088 a planilha nao tinha fabricante, e o log dizia
"Busca web pulada: a ficha nao tem fabricante reconhecivel nem codigo de
peca" -- com o manual da GF Signet anexado e o nome dela escrito nele.
"""
from sigft.services import autospec_documentos as docs
from sigft.services.autospec import AutoSpecCore


def _doc(*paginas, origem="LOCAL"):
    return docs.Documento(nome="x.pdf", origem=origem, paginas=list(paginas))


def test_rotulo_de_marca_da_ficha_de_distribuidor():
    """Texto REAL do `4500063671.0086_b.pdf`."""
    doc = _doc("GF Piping Systems\n159000910\n3-2450-7H\nSpecifications\n"
               "Primary brand\nGeorg Fischer / GF Piping Systems\nMain function\n")
    assert docs.fabricante_dos_documentos([doc]) == "Georg Fischer"


def test_copyright_do_datasheet():
    """Texto REAL do `4500063671.0084.pdf` (ultima pagina)."""
    doc = _doc("Specifications ...", "© Georg Fischer Signet LLC\n3401 Aero Jet Avenue")
    assert docs.fabricante_dos_documentos([doc]) == "Georg Fischer Signet"


def test_rotulo_na_mesma_linha():
    assert docs.fabricante_dos_documentos([_doc("Fabricante: HYDAC\nModelo X")]) == "HYDAC"


def test_manufacturer_product_status_nao_e_fabricante():
    assert docs.fabricante_dos_documentos([_doc("Manufacturer product status\nCommercialized")]) == ""


def test_generico_nao_serve():
    assert docs.fabricante_dos_documentos([_doc("Fabricante: DIVERSOS")]) == ""


def test_so_documento_LOCAL_conta():
    """O da web pode ser do concorrente -- e justamente o que a ancora filtra."""
    assert docs.fabricante_dos_documentos([_doc("© Rexroth AG", origem="WEB")]) == ""


def test_a_busca_web_usa_o_fabricante_do_pdf():
    class _Leitor:
        def ler_paginas(self, caminho, callbacks=None, nome_exibicao=None):
            return ["Datasheet\n© Georg Fischer Signet LLC"], "PyMuPDF"

    class _Buscador:
        def __init__(self):
            self.pedidos = []

        def search_and_download(self, q, required_terms=None, **k):
            self.pedidos.append(required_terms)
            return []

    core = AutoSpecCore.__new__(AutoSpecCore)
    core.pdf_parser, core.searcher = _Leitor(), _Buscador()
    core.google_key, core.cse_id = "k", "cse"
    linhas = []

    class _Cb:
        def log(self, msg, nivel="info", contexto=None):
            linhas.append(str(msg))

    core.retrieve_context("SENSOR DE CONDUTIVIDADE", "", "", ["/tmp/a.pdf"], callbacks=_Cb())
    assert core.searcher.pedidos, "\n".join(linhas)
    assert any("signet" in " ".join(p).lower() or "fischer" in " ".join(p).lower()
               for p in core.searcher.pedidos)
    assert core._fabricante_do_documento == "Georg Fischer Signet"
    assert any("Georg Fischer Signet" in m for m in linhas)
