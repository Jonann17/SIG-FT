#!/usr/bin/env bash
#
# scripts/check.sh — portão de verificação do CP 0.2 do plano de refatoração
# (docs/refatoracao/PLANO_REFATORACAO.md, Fase 0 -> CP 0.2 "Smoke de
# importação").
#
# Roda, nesta ordem, a partir da raiz do repositório:
#   1) `"$PY" -m compileall -q -x '[/\\]\.venv[/\\]' .`
#      Verificação de SINTAXE de TODA a árvore do repositório — inclui
#      frontend.py, que fica de fora do passo 2 (não é seguro IMPORTAR
#      frontend.py neste ambiente: ele importa customtkinter/tkinter e o
#      bloco `if __name__ == "__main__":` abre uma janela real; compileall
#      só compila para bytecode, nunca executa o módulo, então é a
#      verificação certa para ele aqui).
#   2) `"$PY" -m pytest -q`
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

# --- Qual interpretador -----------------------------------------------------
# `python3` fixo NAO serve: quando o projeto vive dentro do OneDrive, o
# _bootstrap_venv.bat manda o venv para %LOCALAPPDATA%/SIG-FT/venv (fora da
# pasta sincronizada, para o OneDrive nao subir milhares de arquivos). Nessa
# maquina `python3` e o Python da Windows Store, sem pytest -- e o portao
# morria no passo 2 sem nunca ter rodado um teste.
#
# Mesma ordem de busca do scripts/_bootstrap_venv.bat, para que o portao e o
# aplicativo usem SEMPRE o mesmo interpretador.
_escolher_python() {
    if [ -n "${SIGFT_PY:-}" ] && [ -x "$SIGFT_PY" ]; then
        echo "$SIGFT_PY"; return
    fi
    if [ -n "${SIGFT_VENV:-}" ] && [ -x "$SIGFT_VENV/Scripts/python.exe" ]; then
        echo "$SIGFT_VENV/Scripts/python.exe"; return
    fi
    local candidato nome
    for candidato in ".venv/Scripts/python.exe" ".venv/bin/python" "${LOCALAPPDATA:-}/SIG-FT/venv/Scripts/python.exe"
    do
        if [ -x "$candidato" ]; then echo "$candidato"; return; fi
    done
    for nome in python3 python; do
        if command -v "$nome" >/dev/null 2>&1; then command -v "$nome"; return; fi
    done
    echo ""
}

PY="$(_escolher_python)"
if [ -z "$PY" ]; then
    echo "ERRO: nenhum interpretador Python encontrado." >&2
    echo "      Rode SIG-FT.bat uma vez para criar o ambiente virtual," >&2
    echo "      ou aponte SIGFT_PY para o python.exe do venv." >&2
    exit 1
fi

# pytest ausente e ERRO DE AMBIENTE, nao falha de teste -- dizer isso aqui
# evita a leitura errada de "o portao quebrou" quando so falta instalar.
if ! "$PY" -c "import pytest" >/dev/null 2>&1; then
    echo "ERRO: pytest nao esta instalado no interpretador escolhido:" >&2
    echo "      $PY" >&2
    echo "      Instale com:  \"$PY\" -m pip install -r requirements-dev.txt" >&2
    exit 1
fi

echo "SIG-FT check :: interpretador = $PY"
echo

echo "=================================================================="
echo "SIG-FT check :: [1/2] compileall   (sintaxe)"
echo "=================================================================="
# O venv fica FORA da checagem: nao e codigo do projeto, e o PySide6 traz sob
# `deploy_lib/` um template Jinja com extensao `.py` (`{% for ... %}`) que nao e
# Python valido -- o compileall morria nele. O regex aceita `/` e `\` porque o
# script tambem roda no Git Bash do Windows.
"$PY" -m compileall -q -x '[/\\]\.venv[/\\]' .
echo "OK: compileall não encontrou erro de sintaxe."
echo

echo "=================================================================="
echo "SIG-FT check :: [2/2] pytest   (testes)"
echo "=================================================================="
"$PY" -m pytest -q
echo "OK: pytest passou."
echo

echo "=================================================================="
echo "SIG-FT check :: TUDO OK (compileall + pytest)."
echo "=================================================================="
