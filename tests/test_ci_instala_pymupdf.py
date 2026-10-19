"""O CI instala o PyMuPDF de verdade (2026-10-19).

Os testes de leitura de PDF do AutoSpec usam o pacote real (`importorskip`):
sem ele no CI, eram PULADOS -- e o defeito do PyMuPDF 2.0 nas tabelas so
apareceu no Release da 1.2.1-rc.5, no Windows. Pulo nao e verde.
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def test_o_passo_de_dependencias_do_ci_instala_o_pymupdf():
    texto = (RAIZ / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    passo = texto[texto.index("- name: Instalar dependencias"):]
    passo = passo[:passo.index("- name:", 1)]

    assert "pymupdf" in passo.split("run:", 1)[1]
