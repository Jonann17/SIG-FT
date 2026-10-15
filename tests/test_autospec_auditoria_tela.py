r"""O interruptor "Conferir as respostas do fornecedor" na tela do AutoSpec (2026-09-28).

[2026-10-15] A tela agora e a Qt (`sigft/app_qt/views/autospec.py`): a
interface antiga saiu do SIG-FT, e este teste passou a olhar a porta Qt com
as MESMAS invariantes. Continua por AST, como o
tests/test_autospec_conferencia_tela.py: o que se prova e a FIACAO, que quebra
em silencio (o comportamento rodando esta em tests/test_qt_tela_autospec.py):

1. a caixa existe e nasce marcada (o usuario pediu a conferencia; desligar e
   a excecao, para o lote em que so se quer preencher);
2. o sinal da caixa grava um atributo COMUM (`self._conferir_fornecedor`)
   -- o worker roda noutra thread, e ler o widget dali seria acesso fora da
   thread da interface;
3. o interruptor chega ao core (`auditar_fornecedor`) pelos DOIS workers
   (fila e conferencia de documentos): cada clique le o atributo e o entrega
   ao seu worker, e `_novo_core` -- a unica construcao do core -- o repassa.
"""
import ast
import pathlib

import pytest

TELA = pathlib.Path(__file__).resolve().parents[1] / "sigft" / "app_qt" / "views" / "autospec.py"


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
    assert "CaixaDeMarcar" in fonte
    assert "Conferir as respostas do fornecedor contra o datasheet" in fonte


def test_a_caixa_nasce_marcada(classe):
    build = _metodo(classe, "_build_ui")
    atribuicoes = [no for no in ast.walk(build) if isinstance(no, ast.Assign)]
    assert any(
        isinstance(alvo, ast.Attribute) and alvo.attr == "_conferir_fornecedor"
        and isinstance(no.value, ast.Constant) and no.value.value is True
        for no in atribuicoes for alvo in no.targets)
    assert "self.chk_fornecedor.setChecked(True)" in ast.unparse(build)


def test_o_sinal_da_caixa_grava_o_atributo_comum(classe):
    assert "self.chk_fornecedor.toggled.connect(self._ao_marcar_conferencia_fornecedor)" in (
        ast.unparse(_metodo(classe, "_build_ui")))
    assert "_conferir_fornecedor" in _atribuicoes_a_self(
        _metodo(classe, "_ao_marcar_conferencia_fornecedor"))


def test_novo_core_repassa_o_interruptor(classe):
    fonte = ast.unparse(_metodo(classe, "_novo_core"))
    assert "core.auditar_fornecedor = auditar_fornecedor" in fonte


@pytest.mark.parametrize("clique, worker", [
    ("run_process", "_worker"),
    ("_conferencia_processar", "_conferencia_worker"),
])
def test_os_dois_workers_recebem_o_interruptor_do_clique(classe, clique, worker):
    """Cada clique entrega `self._conferir_fornecedor` ao seu worker, e o
    worker constroi o core com ele."""
    chamada = [no for no in ast.walk(_metodo(classe, clique))
               if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
               and no.func.attr == "iniciar_tarefa"]
    assert chamada, f"{clique} nao inicia o worker"
    argumentos = [ast.unparse(a) for a in chamada[0].args]
    assert argumentos[0] == f"self.{worker}"
    assert "self._conferir_fornecedor" in argumentos
    assert "self._novo_core(auditar_fornecedor)" in ast.unparse(_metodo(classe, worker))
