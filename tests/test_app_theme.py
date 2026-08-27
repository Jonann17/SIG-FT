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

from sigft.app import theme


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
    assert theme.COLORS["primary"] == "#035D67"
    assert theme.COLORS["accent"] == "#00C975"
    assert theme.COLORS["sidebar"] == "#161616"
    assert theme.COLORS["background"] == "#212121"


def test_demais_cores_nao_mudaram():
    assert theme.COLORS["primary_hover"] == "#047A83"
    assert theme.COLORS["accent_hover"] == "#00E085"
    assert theme.COLORS["danger"] == "#D32F2F"
    assert theme.COLORS["warning"] == "#FFA726"
    assert theme.COLORS["text_light"] == "#E0E0E0"
    assert theme.COLORS["text_white"] == "#FFFFFF"


def test_toda_cor_e_hexadecimal_de_6_digitos():
    for chave, valor in theme.COLORS.items():
        assert valor.startswith("#"), chave
        assert len(valor) == 7, chave
        int(valor[1:], 16)  # levanta ValueError se não for hexadecimal


def test_cor_do_cartao_interno_e_a_que_o_frontend_repetia():
    assert theme.COR_CARTAO == "#2B2B2B"


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

def test_theme_nao_importa_customtkinter():
    """`sigft.app.theme` tem de ser consultável por quem não desenha nada.

    O teste analisa os IMPORTS por AST, não o texto do arquivo: o conftest
    instala um dublê de `customtkinter` para a suíte inteira, então checar
    `sys.modules` não provaria nada — e uma busca por substring acusaria
    falsamente o docstring, que explica justamente por que este módulo não
    importa Tk.
    """
    import ast
    import inspect

    arvore = ast.parse(inspect.getsource(theme))

    importados: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.update(alias.name.split(".")[0] for alias in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module.split(".")[0])

    assert "customtkinter" not in importados
    assert "tkinter" not in importados
    # `__future__` é o único import esperado hoje.
    assert importados <= {"__future__"}, importados
