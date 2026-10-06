r"""Ninguém mais grava `_STATUS_PMIB` pelo `wb.save` do openpyxl (T1 do roteiro
do Gestão PMIB v2, 2026-10-05).

O `wb.save` regrava o arquivo inteiro com o que o openpyxl entende e apaga o
resto -- os comentários em thread e as listas suspensas de extensão. Toda
gravação de `_STATUS_PMIB` passa pelo `StatusPMIB`, que grava com o editor
cirúrgico. Este guarda olha o FONTE (AST): os escritores conhecidos não podem
voltar a chamar `.save(...)` / `save_with_retry(wb, ...)` de um workbook.

A mapeadora (`pmib_manager`) continua sendo gravada pelo openpyxl de propósito
-- não tem comentário em thread nem lista de extensão; ver o comentário lá.
"""
import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _funcao(arquivo, nome):
    arvore = ast.parse((RAIZ / arquivo).read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name == nome:
            return no
    raise AssertionError(f"{arquivo}: função {nome} não encontrada")


def _chamadas(no):
    for filho in ast.walk(no):
        if isinstance(filho, ast.Call):
            alvo = filho.func
            if isinstance(alvo, ast.Attribute):
                yield alvo.attr, filho
            elif isinstance(alvo, ast.Name):
                yield alvo.id, filho


def _grava_workbook_pelo_openpyxl(no):
    """`algo.save(...)` ou `save_with_retry(<wb>, ...)` / `salvar_perguntando(<wb>, ...)`."""
    achados = []
    for nome, chamada in _chamadas(no):
        if nome == "save":
            achados.append(f"linha {chamada.lineno}: .save(...)")
        if nome in ("save_with_retry", "salvar_perguntando") and chamada.args:
            primeiro = chamada.args[0]
            if not (isinstance(primeiro, ast.Name) and primeiro.id == "gravacao"):
                achados.append(f"linha {chamada.lineno}: {nome}({ast.unparse(primeiro)}, ...)")
    return achados


def test_o_statuspmib_nao_salva_pelo_openpyxl():
    salvar = _funcao("sigft/core/excel/status_sheet.py", "salvar")
    assert _grava_workbook_pelo_openpyxl(salvar) == []


def test_o_cria_fichas_grava_o_status_pmib_pelo_statuspmib():
    funcao = _funcao("sigft/services/cria_fichas.py", "atualizar_excel_final")
    assert _grava_workbook_pelo_openpyxl(funcao) == []
    assert any(nome == "salvar" for nome, _ in _chamadas(funcao))


def test_o_guarda_reconhece_o_padrao_proibido():
    fonte = "def f(wb, caminho):\n    locking.save_with_retry(wb, caminho, max_attempts=1)\n    wb.save(caminho)\n"
    funcao = ast.parse(fonte).body[0]
    assert len(_grava_workbook_pelo_openpyxl(funcao)) == 2
