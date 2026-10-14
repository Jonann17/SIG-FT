from sigft.core import python_minimo as pm


def test_versao_suficiente_nao_faz_nada():
    chamadas = []
    pm.exigir_python_minimo((3, 10, 0), sair=chamadas.append, avisar=chamadas.append)
    assert chamadas == []


def test_versao_antiga_avisa_e_sai_com_codigo_1():
    avisos, saidas = [], []
    pm.exigir_python_minimo((3, 9, 6), sair=saidas.append, avisar=avisos.append)
    assert saidas == [1]
    assert "3.9.6" in avisos[0] and "3.10" in avisos[0]


def test_arquivo_compila_em_sintaxe_antiga():
    # O modulo roda ANTES de saber se o Python serve: nada de `X | None`,
    # `match` ou walrus fora de string.
    import ast
    import inspect

    fonte = inspect.getsource(pm)
    ast.parse(fonte, feature_version=(3, 6))
