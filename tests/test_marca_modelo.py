r"""
A coluna `MARCA/MODELO` do `_STATUS_PMIB`, separada em fabricante e modelo.

Cópia fiel do comportamento de `autospec.separar_marca_modelo` -- ver o
docstring do módulo para por que existem duas implementações hoje e onde a
fusão está registrada.
"""
import pytest

from sigft.core.excel import marca_modelo


@pytest.mark.parametrize("bruto, esperado", [
    ("WAGO / 750-362", ("WAGO", "750-362")),
    ("NIDEC / MOD SVTN 3K6 W", ("NIDEC", "MOD SVTN 3K6 W")),
    ("CISCO / IE-3200-8T2S-E", ("CISCO", "IE-3200-8T2S-E")),
])
def test_separa_no_formato_da_planilha(bruto, esperado):
    assert marca_modelo.separar(bruto) == esperado


def test_sem_barra_o_texto_inteiro_e_a_marca():
    """É o caso de quem só anotou o fabricante, e é comum."""
    assert marca_modelo.separar("SCHNEIDER") == ("SCHNEIDER", "")


def test_quebra_na_PRIMEIRA_barra():
    """`750-362/000-001` tem barra dentro do modelo; quebrar em todas partiria
    o código de peça ao meio."""
    assert marca_modelo.separar("WAGO / 750-362/000-001") == ("WAGO", "750-362/000-001")


@pytest.mark.parametrize("vazio", ["", "   ", None, "nan", "NaN"])
def test_celula_vazia_devolve_dois_vazios(vazio):
    """Nunca `None`: o chamador não deve precisar checar duas coisas."""
    assert marca_modelo.separar(vazio) == ("", "")


def test_espaco_em_volta_e_removido_dos_dois_lados():
    assert marca_modelo.separar("  WAGO  /  750-362  ") == ("WAGO", "750-362")


def test_atalhos_devolvem_cada_metade():
    assert marca_modelo.fabricante("WAGO / 750-362") == "WAGO"
    assert marca_modelo.modelo("WAGO / 750-362") == "750-362"


def test_bate_com_a_implementacao_original_do_autospec():
    """CONTRA-DUPLICAÇÃO: enquanto as duas existirem, elas têm de concordar.
    Este teste é o que denuncia a divergência antes de ela virar dois
    fabricantes diferentes para a mesma célula."""
    from sigft.services.autospec import AutoSpecCore

    for bruto in ("WAGO / 750-362", "SCHNEIDER", "", None,
                  "WAGO / 750-362/000-001", "  A  /  B  "):
        assert marca_modelo.separar(bruto) == AutoSpecCore.separar_marca_modelo(bruto)
