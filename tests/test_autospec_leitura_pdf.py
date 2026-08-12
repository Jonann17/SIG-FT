r"""
Testes da leitura local de PDF e da prova de leitura completa (2026-08-11).
Ver docs/AUTOSPEC_MELHORIAS.md, frente 2.

Até esta data a única aferição de "consegui ler" era `if t and len(t) > 100`.
Cem caracteres: um datasheet de 40 páginas do qual se leu uma linha da capa
passava, e entrava no contexto como se fosse o documento inteiro. A IA
respondia "não encontrei" para tudo e o log não dizia que o problema tinha
sido a LEITURA.

Decisões do usuário aplicadas aqui:
  1a — só a camada LOCAL por enquanto (PyMuPDF). Sem Tesseract (exige binário
       de sistema, fora do alcance do `pip` que o SIG-FT.bat usa) e sem
       Docling (baixa ~500 MB e puxa torch).
  2a — leitura incompleta AVISA e SEGUE com o que leu.

Os PDFs são construídos aqui mesmo, com o próprio PyMuPDF: nenhum binário
entra no repositório e o teste não depende de arquivo do usuário.
"""
import pytest

import autospec_backend
from sigft import config
from sigft.core.callbacks import UICallbacks

pymupdf = pytest.importorskip("pymupdf", reason="leitura local de PDF exige pymupdf")


@pytest.fixture(autouse=True)
def _isola_config_file_do_cwd_real(monkeypatch, tmp_path):
    monkeypatch.setattr(
        config, "CONFIG_FILE", str(tmp_path / "api_config_isolado_test.json")
    )


@pytest.fixture
def registro():
    linhas = []
    cb = UICallbacks(
        log=lambda msg, nivel="info", contexto=None: linhas.append((str(msg), nivel))
    )
    cb.linhas = linhas
    cb.texto = lambda: "\n".join(m for m, _ in linhas)
    cb.niveis = lambda: {n for _, n in linhas}
    return cb


def _pdf(caminho, paginas_com_texto, total):
    """PDF com `total` páginas, das quais só as de índice em
    `paginas_com_texto` (0-based) recebem texto. Página sem texto simula a
    digitalizada: existe, ocupa espaço, e não rende caractere nenhum."""
    doc = pymupdf.open()
    for i in range(total):
        pagina = doc.new_page()
        if i in paginas_com_texto:
            pagina.insert_text((72, 100), f"Pagina {i+1} " + ("Dados do datasheet. " * 30))
    doc.save(str(caminho))
    doc.close()
    return str(caminho)


# =============================================================================
# A. O relatório de leitura
# =============================================================================
def test_pdf_inteiro_legivel_reporta_cobertura_total(tmp_path):
    caminho = _pdf(tmp_path / "bom.pdf", paginas_com_texto={0, 1, 2, 3, 4}, total=5)
    texto, rel = autospec_backend._ler_pdf_local(caminho)

    assert rel.paginas_total == 5
    assert rel.paginas_lidas == 5
    assert rel.cobertura == 1.0
    assert rel.completa is True
    assert rel.nivel_log() == "info"
    assert texto and "Pagina 1" in texto


def test_pdf_parcialmente_legivel_e_marcado_como_INCOMPLETO(tmp_path):
    """O caso que motivou tudo: parte do documento não rendeu texto."""
    caminho = _pdf(tmp_path / "misto.pdf", paginas_com_texto={0, 1, 3}, total=5)
    texto, rel = autospec_backend._ler_pdf_local(caminho)

    assert rel.paginas_lidas == 3 and rel.paginas_total == 5
    assert rel.completa is False
    assert rel.nivel_log() == "warn"
    assert texto, "as 3 páginas boas continuam sendo aproveitadas (decisão 2a)"


def test_relatorio_diz_QUAIS_paginas_ficaram_de_fora(tmp_path):
    """Não basta dizer que faltou: o engenheiro precisa saber onde olhar."""
    caminho = _pdf(tmp_path / "misto.pdf", paginas_com_texto={0, 1, 3}, total=5)
    _, rel = autospec_backend._ler_pdf_local(caminho)

    assert rel.paginas_sem_texto == [3, 5], "1-based, como o usuário conta"
    resumo = rel.resumo("misto.pdf")
    assert "3, 5" in resumo
    assert "INCOMPLETA" in resumo


def test_pdf_totalmente_escaneado_reporta_zero(tmp_path):
    caminho = _pdf(tmp_path / "escaneado.pdf", paginas_com_texto=set(), total=3)
    texto, rel = autospec_backend._ler_pdf_local(caminho)

    assert texto == ""
    assert rel.paginas_lidas == 0 and rel.cobertura == 0.0
    assert rel.completa is False
    assert "OCR" in rel.resumo("escaneado.pdf")


def test_pagina_com_migalha_de_texto_NAO_conta_como_lida(tmp_path):
    """Número de página solto ou cabeçalho não é conteúdo. O limiar existe
    para não inflar a cobertura com lixo."""
    doc = pymupdf.open()
    pagina = doc.new_page()
    pagina.insert_text((72, 100), "7")  # só o número da página
    caminho = str(tmp_path / "migalha.pdf")
    doc.save(caminho)
    doc.close()

    _, rel = autospec_backend._ler_pdf_local(caminho)
    assert rel.paginas_lidas == 0
    assert autospec_backend.MIN_CHARS_PAGINA_UTIL > 1


def test_arquivo_ilegivel_devolve_relatorio_None(tmp_path):
    """Quem chama cai para o PyPDF2 — não pode explodir."""
    ruim = tmp_path / "nao_e_pdf.pdf"
    ruim.write_bytes(b"isto nao e um PDF")
    texto, rel = autospec_backend._ler_pdf_local(str(ruim))
    assert texto == "" and rel is None


# =============================================================================
# B. Integração com o `extract_text`: avisa e segue (decisão 2a)
# =============================================================================
def test_extract_text_usa_o_leitor_LOCAL_e_loga_o_relatorio(tmp_path, registro):
    caminho = _pdf(tmp_path / "bom.pdf", paginas_com_texto={0, 1}, total=2)
    proc = autospec_backend.PDFProcessor(llama_key=None)

    texto, metodo = proc.extract_text(caminho, callbacks=registro)

    assert metodo == "PyMuPDF"
    assert texto
    assert "2 pagina(s), 2 lida(s)" in registro.texto()


def test_leitura_incompleta_AVISA_mas_devolve_o_que_leu(tmp_path, registro):
    """Decisão 2a: 37 páginas boas valem mais que o descarte por 3 ruins."""
    caminho = _pdf(tmp_path / "misto.pdf", paginas_com_texto={0}, total=4)
    proc = autospec_backend.PDFProcessor(llama_key=None)

    texto, metodo = proc.extract_text(caminho, callbacks=registro)

    assert texto, "não pode descartar o documento inteiro"
    assert "warn" in registro.niveis()
    assert "INCOMPLETA" in registro.texto()


def test_pdf_com_texto_NAO_sobe_para_a_nuvem_mesmo_com_chave(tmp_path, monkeypatch, registro):
    """Inversão de 2026-08-11: a nuvem era tentada PRIMEIRO sempre que
    houvesse chave, e o arquivo subia mesmo quando dava para ler aqui, de
    graça. Agora local vem antes — a nuvem é último recurso."""
    caminho = _pdf(tmp_path / "bom.pdf", paginas_com_texto={0, 1}, total=2)

    def _explode(*a, **k):
        raise AssertionError("nao pode chamar a nuvem com o PDF legivel localmente")

    monkeypatch.setattr(autospec_backend, "LlamaParse", _explode)
    proc = autospec_backend.PDFProcessor(llama_key="tenho-chave")

    texto, metodo = proc.extract_text(caminho, callbacks=registro)
    assert metodo == "PyMuPDF" and texto


def test_pdf_escaneado_sem_chave_avisa_que_precisa_de_OCR(tmp_path, registro):
    caminho = _pdf(tmp_path / "escaneado.pdf", paginas_com_texto=set(), total=3)
    proc = autospec_backend.PDFProcessor(llama_key=None)

    texto, metodo = proc.extract_text(caminho, callbacks=registro)

    assert texto == "" and metodo == ""
    assert "OCR" in registro.texto()
    assert "warn" in registro.niveis()


def test_pdf_escaneado_COM_chave_recorre_a_nuvem_avisando_que_o_arquivo_sai(
    tmp_path, monkeypatch, registro
):
    """A nuvem continua disponível como último recurso — mas o usuário é
    avisado de que o arquivo está saindo da rede."""
    caminho = _pdf(tmp_path / "escaneado.pdf", paginas_com_texto=set(), total=2)

    class _DocFake:
        text = "TEXTO VINDO DO OCR"

    class _ParserFake:
        def __init__(self, **kw): pass
        def load_data(self, c): return [_DocFake()]

    monkeypatch.setattr(autospec_backend, "LlamaParse", _ParserFake)
    proc = autospec_backend.PDFProcessor(llama_key="chave")

    texto, metodo = proc.extract_text(caminho, callbacks=registro)

    assert texto == "TEXTO VINDO DO OCR" and metodo == "LlamaParse"
    assert "SAI da rede" in registro.texto()
