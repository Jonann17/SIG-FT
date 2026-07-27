"""Pacote `sigft.core.excel` — utilitários puros de planilha do SIG-FT.

Checkpoint 1.2 do plano de refatoração
(docs/refatoracao/PLANO_REFATORACAO.md, Fase 1 -> CP 1.2):

  - `pmib_codes.py`: `normalize_pmib()` / `extract_pmib_code()` e variantes —
    ÚNICA implementação da normalização/extração de código PMIB.
  - `headers.py`: `find_header_row()` / `find_columns()` — ÚNICA
    implementação da busca dinâmica de cabeçalho em planilha.

Só stdlib (`re`, `os`) — importável no ambiente de teste, que não tem
pandas/openpyxl instalados (ver tests/conftest.py). Os consumidores de
produção (`*_backend.py`, `upload_ficha_duplicada.py`, `frontend.py`) fazem a
ponte com DataFrame/openpyxl NELES MESMOS (via adaptadores como
`headers.rows_from_worksheet`); este pacote nunca importa pandas/openpyxl.
"""
