"""O AutoSpec lê PDF no instalador (2026-10-20).

Da 1.2.1-rc.5 à rc.7, no `.exe`, `import pymupdf` levantava
`FileNotFoundError: ...pymupdf/layout/resources/onnx/layout_rf2.4.1+imf1.yaml`:
o PyMuPDF 2.0 traz o `pymupdf-layout` como dependência, ele carrega um modelo
ONNX no import, e o PyInstaller não levava os arquivos do modelo. O conserto
é não levar o pacote (`excludes` do `SIG-FT.spec`); estes testes provam que
o PyMuPDF e a leitura de tabelas aguentam a falta dele, e que o AutoSpec não
derruba a ficha quando o import do PyMuPDF quebra com algo que não é
`ImportError`.
"""
import pathlib
import subprocess
import sys
import textwrap

import pytest

from sigft.services import autospec_documentos

RAIZ = pathlib.Path(__file__).resolve().parent.parent
FORA_DO_PACOTE = ("pymupdf.layout", "pymupdf4llm", "onnxruntime")


def test_o_instalador_nao_leva_o_layout_do_pymupdf():
    spec = (RAIZ / "SIG-FT.spec").read_text(encoding="utf-8")
    for modulo in FORA_DO_PACOTE:
        assert f'"{modulo}"' in spec, f"{modulo} tem de estar nos excludes"


def test_pymupdf_sem_o_layout_le_a_tabela():
    """Num processo à parte, como no `.exe`: os três módulos não existem."""
    pytest.importorskip("pymupdf")
    codigo = textwrap.dedent(f"""
        import sys
        for m in {FORA_DO_PACOTE!r}:
            sys.modules[m] = None
        import pymupdf
        assert pymupdf._get_layout is None
        doc = pymupdf.open(); p = doc.new_page()
        y = 72
        for a, b in (("Parametro", "Valor"), ("Tensao nominal", "220 V")):
            p.insert_text((72, y), a); p.insert_text((250, y), b); y += 20
        for yy in (60, 80, 100):
            p.draw_line((70, yy), (400, yy))
        for xx in (70, 240, 400):
            p.draw_line((xx, 60), (xx, 100))
        from sigft.services import autospec_documentos as d
        print(d.tabelas_da_pagina(p))
    """)
    saida = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ,
                           capture_output=True, text=True, timeout=120)
    assert saida.returncode == 0, saida.stderr
    assert "| Tensao nominal | 220 V |" in saida.stdout


def test_tabela_sem_a_analise_de_layout():
    """`use_layout=False`: a mesma tabela com e sem o `pymupdf-layout`."""
    chamadas = []

    class _Pagina:
        def find_tables(self, **kw):
            chamadas.append(kw)
            return type("T", (), {"tables": []})()

    autospec_documentos.tabelas_da_pagina(_Pagina())
    assert chamadas == [{"use_layout": False}]


def test_pymupdf_antigo_sem_o_parametro_continua_servindo():
    chamadas = []

    class _PaginaAntiga:
        def find_tables(self):
            chamadas.append("sem parametro")
            return type("T", (), {"tables": []})()

    assert autospec_documentos.tabelas_da_pagina(_PaginaAntiga()) == ""
    assert chamadas == ["sem parametro"]


def test_import_do_pymupdf_que_quebra_nao_derruba_a_leitura(monkeypatch, tmp_path):
    """O erro do log: `FileNotFoundError` no import. Vira "sem PyMuPDF"."""
    import builtins
    from sigft.services import autospec

    original = builtins.__import__

    def importar(nome, *a, **k):
        if nome in ("pymupdf", "fitz"):
            raise FileNotFoundError("layout_rf2.4.1+imf1.yaml")
        return original(nome, *a, **k)

    monkeypatch.setattr(builtins, "__import__", importar)
    pdf = tmp_path / "manual.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    assert autospec._ler_pdf_local(str(pdf)) == ("", None)
