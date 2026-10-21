"""Tokens do sistema visual (2026-10-20): cada cor tem um papel, e o texto se lê."""
import pytest

from sigft.app import tokens

PAPEIS = {"fundo", "superficie", "superficie_alta", "borda", "texto", "texto_suave",
          "primaria", "primaria_hover", "texto_sobre_primaria", "marca", "sucesso",
          "aviso", "perigo", "perigo_fundo", "info", "console_fundo", "console_texto"}


@pytest.mark.parametrize("tema", ["escuro", "claro"])
def test_os_dois_temas_tem_os_mesmos_papeis(tema):
    assert set(tokens.paleta(tema)) == PAPEIS


def test_contraste_conhecido():
    assert tokens.contraste("#FFFFFF", "#000000") == pytest.approx(21.0, abs=0.01)
    assert tokens.contraste("#FFFFFF", "#00A86B") < 4.5   # o verde que reprovou na spec


PARES = [("texto", "fundo"), ("texto", "superficie"), ("texto", "superficie_alta"),
         ("texto_suave", "fundo"), ("texto_suave", "superficie"),
         ("texto_sobre_primaria", "primaria"), ("texto_sobre_primaria", "primaria_hover"),
         ("perigo", "superficie"), ("aviso", "superficie"), ("sucesso", "superficie"),
         ("info", "superficie")]


@pytest.mark.parametrize("tema", ["escuro", "claro"])
@pytest.mark.parametrize("texto,fundo", PARES)
def test_texto_se_le_nos_dois_temas(tema, texto, fundo):
    p = tokens.paleta(tema)
    assert tokens.contraste(p[texto], p[fundo]) >= 4.5, (tema, texto, fundo)


def test_botao_de_perigo_tem_texto_branco_legivel():
    for tema in ("escuro", "claro"):
        assert tokens.contraste("#FFFFFF", tokens.paleta(tema)["perigo_fundo"]) >= 4.5


def test_console_e_escuro_nos_dois_temas():
    assert tokens.ESCURO["console_fundo"] == tokens.CLARO["console_fundo"] == "#0E1012"


def test_tema_desconhecido_cai_no_escuro():
    assert tokens.paleta("roxo") is tokens.ESCURO


def test_colors_antigo_vem_dos_tokens():
    from sigft.app import theme
    assert theme.COLORS["background"] == tokens.ESCURO["fundo"]
    assert theme.COLORS["accent"] == tokens.ESCURO["sucesso"]
    assert theme.COLORS["danger"] == tokens.ESCURO["perigo_fundo"]
    assert theme.COR_CARTAO == tokens.ESCURO["superficie"]
