r"""O interruptor "Conferir as respostas do fornecedor" na tela do AutoSpec (2026-09-28).

Por AST, pelo mesmo motivo de tests/test_autospec_conferencia_tela.py: montar
a tela exige um root Tk. O que se prova e a FIACAO, que quebra em silencio:

1. a caixa existe e nasce marcada (o usuario pediu a conferencia; desligar e
   a excecao, para o lote em que so se quer preencher);
2. o `command` da caixa grava um atributo COMUM (`self._conferir_fornecedor`)
   -- `_novo_core` roda dentro da thread do worker, e ler a variavel do Tk
   dali seria acesso fora da thread do Tk;
3. `_novo_core` repassa o atributo ao core (`auditar_fornecedor`), para os
   DOIS workers (fila e conferencia de documentos).
"""
import ast
import pathlib

import pytest

TELA = pathlib.Path(__file__).resolve().parents[1] / "sigft" / "app" / "views" / "autospec.py"


@pytest.fixture(scope="module")
def classe():
    arvore = ast.parse(TELA.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.ClassDef) and no.name == "ModuloAutoSpec":
            return no
    pytest.fail("class ModuloAutoSpec sumiu")


def _metodo(classe, nome):
    for no in classe.body:
        if isinstance(no, ast.FunctionDef) and no.name == nome:
            return no
    pytest.fail(f"metodo {nome} nao existe em ModuloAutoSpec")


def _atribuicoes_a_self(funcao):
    return {alvo.attr for no in ast.walk(funcao) if isinstance(no, ast.Assign)
            for alvo in no.targets
            if isinstance(alvo, ast.Attribute) and isinstance(alvo.value, ast.Name)
            and alvo.value.id == "self"}


def test_a_caixa_existe_com_o_texto_do_fornecedor(classe):
    fonte = ast.unparse(_metodo(classe, "_build_ui"))
    assert "CTkCheckBox" in fonte
    assert "Conferir as respostas do fornecedor contra o datasheet" in fonte


def test_a_caixa_nasce_marcada(classe):
    build = _metodo(classe, "_build_ui")
    atribuicoes = [no for no in ast.walk(build) if isinstance(no, ast.Assign)]
    assert any(
        isinstance(alvo, ast.Attribute) and alvo.attr == "_conferir_fornecedor"
        and isinstance(no.value, ast.Constant) and no.value.value is True
        for no in atribuicoes for alvo in no.targets)
    assert ".select()" in ast.unparse(build)


def test_o_command_da_caixa_grava_o_atributo_comum(classe):
    assert "_conferir_fornecedor" in _atribuicoes_a_self(
        _metodo(classe, "_ao_marcar_conferencia_fornecedor"))


def test_novo_core_repassa_o_interruptor(classe):
    fonte = ast.unparse(_metodo(classe, "_novo_core"))
    assert "auditar_fornecedor" in fonte and "_conferir_fornecedor" in fonte
