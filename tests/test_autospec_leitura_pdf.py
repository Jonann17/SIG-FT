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


# =============================================================================
# Tabelas como tabelas  [2026-10-19]
# =============================================================================
# O `get_text()` entrega a tabela de especificacoes uma celula por linha
# ("Tensao nominal\n220\nV\nCorrente\n..."): a IA lendo texto perde qual valor
# e de qual parametro. A pagina passa a levar, DEPOIS do texto de sempre, cada
# tabela detectada em Markdown. Depois, e nao no lugar: a prova que a IA cita e
# conferida contra o texto, e o texto antigo continua inteiro nele. Ideia do
# RAG-Anything (HKUDS, MIT): `format_table_body`.

def _pdf_com_tabela(caminho, linhas):
    doc = pymupdf.open()
    pagina = doc.new_page()
    pagina.insert_text((72, 60), "Datasheet XYZ-100. Especificacoes tecnicas do produto abaixo.")
    x0, y0, largura, altura = 72, 90, 150, 22
    for i, linha in enumerate(linhas):
        for j, celula in enumerate(linha):
            r = pymupdf.Rect(x0 + j * largura, y0 + i * altura, x0 + (j + 1) * largura, y0 + (i + 1) * altura)
            pagina.draw_rect(r, color=(0, 0, 0), width=0.8)
            pagina.insert_text((r.x0 + 4, r.y1 - 7), celula, fontsize=10)
    doc.save(str(caminho))
    doc.close()
    return str(caminho)


_LINHAS = [("Parametro", "Valor", "Unidade"), ("Tensao nominal", "220", "V"),
           ("Corrente", "5,5", "A"), ("Peso", "12", "kg")]


def test_tabela_do_pdf_vai_tambem_como_tabela_markdown(tmp_path):
    texto, rel = autospec_backend._ler_pdf_local(_pdf_com_tabela(tmp_path / "t.pdf", _LINHAS))

    assert "| Tensao nominal | 220 | V |" in texto
    assert "| Parametro | Valor | Unidade |" in texto
    assert "| --- | --- | --- |" in texto
    assert "| Tensao nominal | 220 | V |" in rel.paginas[0]


def test_a_tabela_vem_DEPOIS_do_texto_de_sempre_que_continua_inteiro(tmp_path):
    texto, rel = autospec_backend._ler_pdf_local(_pdf_com_tabela(tmp_path / "t.pdf", _LINHAS))

    assert "Tensao nominal\n220\nV" in texto          # a prova antiga continua achavel
    assert texto.index("Tensao nominal\n220") < texto.index("| Tensao nominal |")


def test_pagina_sem_tabela_fica_como_era(tmp_path):
    texto, rel = autospec_backend._ler_pdf_local(_pdf(tmp_path / "s.pdf", {0}, total=1))

    assert "|" not in texto and "[tabela" not in texto


def test_falha_na_deteccao_de_tabela_nao_derruba_a_leitura(tmp_path, monkeypatch):
    caminho = _pdf_com_tabela(tmp_path / "t.pdf", _LINHAS)
    monkeypatch.setattr(pymupdf.Page, "find_tables", lambda self, *a, **k: 1 / 0)

    texto, rel = autospec_backend._ler_pdf_local(caminho)

    assert rel.paginas_lidas == 1 and "Tensao nominal" in texto and "| Tensao" not in texto


@pytest.mark.parametrize("linhas, esperado", [
    ([["a", "b"], ["1", "2"]], "| a | b |\n| --- | --- |\n| 1 | 2 |"),
    ([["a|x", None], ["linha\nquebrada", " 2 "]], "| a\\|x |  |\n| --- | --- |\n| linha quebrada | 2 |"),
    ([["so", "uma"]], ""),                       # uma linha so nao e tabela
    ([["a"], ["b"]], ""),                        # uma coluna so nao e tabela
    ([[None, None], ["", ""]], ""),              # tudo vazio
])
def test_tabela_em_markdown(linhas, esperado):
    from sigft.services import autospec_documentos

    assert autospec_documentos.tabela_em_markdown(linhas) == esperado


def test_o_texto_da_celula_vem_do_get_text_da_pagina_e_nao_do_extract():
    """2026-10-19, Release da 1.2.1-rc.5: o `extract()` do PyMuPDF 2.0 devolveu
    "Tensaonominal" e "55\\n," para "Tensao nominal" e "5,5". O texto de cada
    celula passa a vir do `get_text` da pagina, recortado na celula; do
    `find_tables` fica so a posicao. Este teste vale em qualquer versao."""
    from sigft.services import autospec_documentos

    class _Linha:
        def __init__(self, celulas):
            self.cells = celulas

    class _Tabela:
        rows = [_Linha([(0, 0, 1, 1), (1, 0, 2, 1)]), _Linha([(0, 1, 1, 2), None])]

        def extract(self):
            return [["Tensaonominal", "55\n,"]]          # o que o 2.0 devolveu

    class _Pagina:
        texto = {(0, 0, 1, 1): "Tensao nominal", (1, 0, 2, 1): "5,5", (0, 1, 1, 2): " Peso\n"}

        def find_tables(self):
            return type("T", (), {"tables": [_Tabela()]})()

        def get_text(self, modo, clip):
            return self.texto[clip]

    markdown = autospec_documentos.tabelas_da_pagina(_Pagina())

    assert "| Tensao nominal | 5,5 |" in markdown and "| Peso |  |" in markdown
    assert "Tensaonominal" not in markdown
