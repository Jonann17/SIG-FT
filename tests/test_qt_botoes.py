"""Botão sem cor própria (2026-10-20): quem decide a cor é a folha do tema."""
import pathlib
import re

from sigft.app import tokens
from sigft.app.theme import COLORS
from sigft.app_qt import estilo
from sigft.app_qt.widgets import blocos


def test_cor_vira_variante():
    assert blocos.variante_da_cor(COLORS["primary"]) == "primario"
    assert blocos.variante_da_cor(COLORS["danger"]) == "perigo"
    assert blocos.variante_da_cor("transparent") == "fantasma"
    assert blocos.variante_da_cor("#3A3A3A") == "secundario"
    assert blocos.variante_da_cor(None) is None


def test_botao_nao_guarda_cor(qapp):
    b = blocos.botao("Salvar", cor_fundo=COLORS["primary"])
    assert b.property("variante") == "primario"
    assert "background" not in b.styleSheet()


def test_ninguem_passa_cor_fundo_novo():
    """Uso novo de cor crua no botão reprova: use `variante=`."""
    usos = [p for p in pathlib.Path("sigft/app_qt").rglob("*.py")
            if re.search(r"botao\([^)]*cor_fundo=", p.read_text(encoding="utf-8"))]
    assert usos == []


def test_link_tem_contraste_nos_dois_temas():
    for paleta in (tokens.ESCURO, tokens.CLARO):
        assert tokens.contraste(paleta["info"], paleta["fundo"]) >= 4.5
    assert '[papel="link"]' in estilo.folha_de_estilo("escuro")
