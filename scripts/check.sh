#!/usr/bin/env bash
#
# scripts/check.sh — portão de verificação do CP 0.2 do plano de refatoração
# (docs/refatoracao/PLANO_REFATORACAO.md, Fase 0 -> CP 0.2 "Smoke de
# importação").
#
# Roda, nesta ordem, a partir da raiz do repositório:
#   1) `python3 -m compileall -q .`
#      Verificação de SINTAXE de TODA a árvore do repositório — inclui
#      frontend.py, que fica de fora do passo 2 (não é seguro IMPORTAR
#      frontend.py neste ambiente: ele importa customtkinter/tkinter e o
#      bloco `if __name__ == "__main__":` abre uma janela real; compileall
#      só compila para bytecode, nunca executa o módulo, então é a
#      verificação certa para ele aqui).
#   2) `python3 -m pytest -q`
#      Testes de caracterização de funções puras (CP 0.1) + smoke de
#      importação dos 12 módulos `*_backend.py` / `upload_ficha_duplicada.py`
#      (CP 0.2, tests/test_smoke_imports.py) — as dependências pesadas
#      ausentes neste ambiente (pandas, openpyxl, selenium,
#      google-generativeai, langchain*, llama_parse, PyPDF2, bs4, xlwings,
#      deep_translator, unidecode) são stubadas por tests/conftest.py.
#
# Uso:
#   bash scripts/check.sh
#   ./scripts/check.sh        (após `chmod +x`, já aplicado neste repo)
#
# Saída: encerra com o primeiro código de saída != 0 (graças a
# `set -euo pipefail`) assim que uma das duas etapas falhar; 0 se as duas
# passarem.

set -euo pipefail

cd "$(dirname "$0")/.."

echo "=================================================================="
echo "SIG-FT check :: [1/2] python3 -m compileall -q .   (sintaxe)"
echo "=================================================================="
python3 -m compileall -q .
echo "OK: compileall não encontrou erro de sintaxe."
echo

echo "=================================================================="
echo "SIG-FT check :: [2/2] python3 -m pytest -q   (testes)"
echo "=================================================================="
python3 -m pytest -q
echo "OK: pytest passou."
echo

echo "=================================================================="
echo "SIG-FT check :: TUDO OK (compileall + pytest)."
echo "=================================================================="
