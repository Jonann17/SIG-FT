"""Testes de `sigft/app/theme.py` — Checkpoint 7.1 (Fase 7 do plano).

A regra da fase é ZERO REDESIGN, e um teste de tema só tem uma coisa útil a
fazer: travar os valores contra mudança acidental. Se um destes testes ficar
vermelho, a pergunta certa não é "como conserto o teste?" e sim "por que a
paleta mudou?".

A referência é o dict `COLORS` do `frontend.py`, que continua existindo lá
enquanto a Fase 7 não termina — o teste de coerência entre os dois está em
`test_app_theme_bate_com_frontend.py`.
"""
from __future__ import annotations

from sigft.app import theme, tokens


# =============================================================================
# A. Paleta — os valores exatos da identidade GE Vernova
# =============================================================================

def test_paleta_tem_as_10_chaves_esperadas():
    assert set(theme.COLORS) == {
        "primary",
        "primary_hover",
        "accent",
        "accent_hover",
        "danger",
        "warning",
        "sidebar",
        "background",
        "text_light",
        "text_white",
    }


def test_cores_da_identidade_ge_vernova_nao_mudaram():
    # Os quatro valores citados nominalmente na regra da Fase 7 do plano.
    # 2026-10-20: a fidelidade à CTk caiu em 2026-10-15; o valor vem do token.
    assert theme.COLORS["primary"] == tokens.ESCURO["marca"]
    assert theme.COLORS["accent"] == tokens.ESCURO["sucesso"]
    assert theme.COLORS["sidebar"] == tokens.ESCURO["superficie"]
    assert theme.COLORS["background"] == tokens.ESCURO["fundo"]


def test_demais_cores_nao_mudaram():
    assert theme.COLORS["primary_hover"] == "#047A83"
    # 2026-10-20: os demais valores também vêm dos tokens (a CTk saiu em 10-15).
    assert theme.COLORS["accent_hover"] == tokens.ESCURO["primaria_hover"]
    assert theme.COLORS["danger"] == tokens.ESCURO["perigo_fundo"]
    assert theme.COLORS["warning"] == tokens.ESCURO["aviso"]
    assert theme.COLORS["text_light"] == tokens.ESCURO["texto"]
    assert theme.COLORS["text_white"] == "#FFFFFF"


def test_toda_cor_e_hexadecimal_de_6_digitos():
    for chave, valor in theme.COLORS.items():
        assert valor.startswith("#"), chave
        assert len(valor) == 7, chave
        int(valor[1:], 16)  # levanta ValueError se não for hexadecimal


def test_cor_do_cartao_interno_e_a_que_o_frontend_repetia():
    # 2026-10-20: o cartão deixou de repetir o #2B2B2B da CTk; vem do token.
    assert theme.COR_CARTAO == tokens.ESCURO["superficie"]


# =============================================================================
# B. Fontes
# =============================================================================

def test_fonte_do_titulo_de_modulo():
    assert theme.FONTE_TITULO_MODULO == ("Roboto", 24, "bold")


def test_console_e_a_unica_monoespacada():
    assert theme.FONTE_CONSOLE == ("Consolas", 12)
    # Todas as outras são Roboto — a identidade visual do app.
    for nome in dir(theme):
        if nome.startswith("FONTE_") and nome != "FONTE_CONSOLE":
            assert getattr(theme, nome)[0] == "Roboto", nome


def test_toda_fonte_e_tupla_familia_tamanho():
    for nome in dir(theme):
        if not nome.startswith("FONTE_"):
            continue
        valor = getattr(theme, nome)
        assert isinstance(valor, tuple), nome
        assert len(valor) in (2, 3), nome
        assert isinstance(valor[0], str), nome
        assert isinstance(valor[1], int), nome


# =============================================================================
# C. Medidas do esqueleto
# =============================================================================

def test_medidas_dominantes_do_frontend():
    assert theme.ALTURA_HEADER == 50
    assert theme.ALTURA_CONSOLE == 150
    assert theme.PADDING_X == 20
    assert theme.PADDING_Y == 10


# =============================================================================
# D. O módulo é puro — precisa importar sem Tk
# =============================================================================

def test_theme_e_biblioteca_padrao_pura():
    """`sigft.app.theme` tem de ser consultável por quem não desenha nada:
    nenhum import além de `__future__` (por AST: o docstring explica por que
    o módulo não importa biblioteca gráfica, e uma busca por texto acusaria
    falsamente a explicação)."""
    import ast
    import inspect

    arvore = ast.parse(inspect.getsource(theme))

    importados: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.update(alias.name.split(".")[0] for alias in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module.split(".")[0])

    # 2026-10-20: theme deriva de tokens (também puro, sem biblioteca gráfica).
    assert importados <= {"__future__", "sigft"}, importados
