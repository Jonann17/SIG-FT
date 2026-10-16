"""O pydantic chega ao usuário? (2026-10-16, R2: as regras do portal antes do navegador)

`sigft/core/pmib_regras.py` descreve as regras do portal com o pydantic. Ele já
vinha no pacote puxado por llama-index e google-generativeai, mas passou a ser
dependência DIRETA: se um dia aqueles dois o largarem, as quatro telas de robô
deixam de conferir. Os mesmos elos de `test_lxml_empacotamento.py`.
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _requisitos(nome):
    return [linha.split(";")[0].split(">")[0].split("=")[0].strip().lower()
            for linha in (RAIZ / nome).read_text(encoding="utf-8").splitlines()
            if linha.strip() and not linha.strip().startswith("#")]


def test_requirements_de_producao_instala_o_pydantic():
    assert "pydantic" in _requisitos("requirements.txt")


def test_requirements_dev_tambem_porque_o_ci_so_instala_ele():
    assert "pydantic" in _requisitos("requirements-dev.txt")


def test_a_conferencia_do_pacote_procura_o_pydantic_e_as_regras():
    from sigft.app import conferencia

    assert "pydantic" in conferencia.MODULOS_ESSENCIAIS
    assert "pydantic_core" in conferencia.MODULOS_ESSENCIAIS
    assert "sigft.core.pmib_regras" in conferencia.MODULOS_ESSENCIAIS


def test_o_pydantic_da_suite_e_o_de_verdade():
    # Se o conftest um dia dublar o pydantic, as regras passariam a testar o dublê.
    import pydantic

    assert isinstance(pydantic.BaseModel, type) and pydantic.VERSION.startswith("2.")
