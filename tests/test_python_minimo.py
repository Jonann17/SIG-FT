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


def test_python_3_12_0_exato_avisa_mas_abre():
    """Pendência de 2026-10-14 (máquina do Luan): no 3.12.0 EXATO o PySide6
    quebra ao importar o pandas (`six.moves`), e as telas Qt que usam pandas
    não abrem. É defeito do 3.12.0, corrigido nas versões seguintes: o app
    avisa o que fazer e abre do mesmo jeito (o resto funciona)."""
    from sigft.core import python_minimo

    avisos, saidas = [], []
    python_minimo.exigir_python_minimo((3, 12, 0), sair=saidas.append, avisar=avisos.append)

    assert saidas == []
    assert len(avisos) == 1 and "3.12.0" in avisos[0] and "python.org" in avisos[0]


def test_outras_versoes_nao_avisam():
    from sigft.core import python_minimo

    for versao in ((3, 12, 1), (3, 12, 10), (3, 13, 0), (3, 10, 0), (3, 11, 9)):
        avisos = []
        python_minimo.exigir_python_minimo(versao, sair=lambda c: None, avisar=avisos.append)
        assert avisos == [], versao
