"""Botão sem cor própria (2026-10-20): quem decide a cor é a folha do tema."""
import ast
import pathlib

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


def _chamadas_de_botao_com_cor_fundo(fonte: str) -> list[int]:
    """Linhas com uma chamada a `...botao(...)` que passa `cor_fundo=`.

    Pela árvore do Python, e não por regex: `botao\\([^)]*cor_fundo=` parava no
    primeiro ")" e deixava passar `botao(mono("x"), cor_fundo=...)`."""
    linhas = []
    for no in ast.walk(ast.parse(fonte)):
        if not isinstance(no, ast.Call):
            continue
        func = no.func
        nome = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if nome.endswith("botao") and any(k.arg == "cor_fundo" for k in no.keywords):
            linhas.append(no.lineno)
    return linhas


def test_ninguem_passa_cor_fundo_novo():
    """Uso novo de cor crua no botão reprova: use `variante=`."""
    usos = [f"{p}:{n}" for p in pathlib.Path("sigft/app_qt").rglob("*.py")
            for n in _chamadas_de_botao_com_cor_fundo(p.read_text(encoding="utf-8"))]
    assert usos == []


def test_guarda_de_cor_fundo_ve_parenteses_dentro_da_chamada():
    assert _chamadas_de_botao_com_cor_fundo('blocos.botao(mono("x"), cor_fundo="#3A3A3A")') == [1]
    assert _chamadas_de_botao_com_cor_fundo('_botao(f(g("y")), largura=3, cor_fundo=c)') == [1]
    assert _chamadas_de_botao_com_cor_fundo('blocos.botao("x", variante="primario")') == []


def test_link_tem_contraste_nos_dois_temas():
    for paleta in (tokens.ESCURO, tokens.CLARO):
        assert tokens.contraste(paleta["info"], paleta["fundo"]) >= 4.5
    assert '[papel="link"]' in estilo.folha_de_estilo("escuro")
