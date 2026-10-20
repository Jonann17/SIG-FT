"""Cor só no estilo (2026-10-20): uma cor escrita numa tela fica escura no tema claro.

Toda cor da interface sai de `estilo.py` (a folha do tema, por objectName e pelas
propriedades `papel`/`variante`) ou, para as peças desenhadas com QPainter, da
paleta do tema atual (`estilo.paleta_atual()`). Este teste varre `sigft/app_qt`
e acusa o que escapa: hexadecimal, cinza do Tk, as constantes de cor da CTk e o
`theme.COLORS`/`COR_CARTAO` pintando direto.
"""
import pathlib
import re

COR = re.compile(r"#[0-9A-Fa-f]{6}\b|cinza_tk\(")
# As cores da interface antiga pelo NOME: escapavam da varredura por hexadecimal.
# `tokens.ESCURO`/`CLARO` direto também: a paleta vem de `estilo.paleta_atual()`,
# o único lugar que a troca de tema (Task 7) vai mudar.
NOME_DE_COR = re.compile(
    r"\b(AZUL_CTK|AZUL_CTK_HOVER|TEXTO_BOTAO_CTK|BORDA_CTK|TRILHO_CTK|PERCORRIDO_SLIDER_CTK"
    r"|TEXTO_DESABILITADO_CTK|FUNDO_QUADRO_CTK|FUNDO_QUADRO_INTERNO_CTK|COR_CARTAO"
    r"|COR_TEXTO_APOIO\w*)\b|\bCOLORS\b|\btokens\.(ESCURO|CLARO)\b"
    r"|[\"'](white|black|gr[ae]y\d{0,3})[\"']"
    # Cor por nome ou por variável numa folha local: `color: gray`, `color: {cor}`.
    r"|\b(?:color|background)\s*:\s*(?!transparent\b)[a-z#{]")
PERMITIDOS = {"sigft/app_qt/estilo.py"}


def _linhas_de_codigo():
    for p in sorted(pathlib.Path("sigft/app_qt").rglob("*.py")):
        if str(p).replace("\\", "/") in PERMITIDOS:
            continue
        for n, linha in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            # A linha que é só comentário não conta.
            if not linha.lstrip().startswith("#"):
                yield f"{p}:{n}", linha


def test_nenhuma_tela_tem_cor_propria():
    achados = [onde for onde, linha in _linhas_de_codigo() if COR.search(linha)]
    assert achados == []


def test_nenhuma_tela_pinta_com_a_cor_antiga_pelo_nome():
    achados = [f"{onde}: {linha.strip()}" for onde, linha in _linhas_de_codigo()
               if NOME_DE_COR.search(linha)]
    assert achados == []


def test_a_varredura_pega_o_que_deve():
    assert COR.search('r.setStyleSheet("color: #A0A0A0;")')
    assert COR.search("cor=estilo.cinza_tk(theme.COR_TEXTO_APOIO)")
    assert not COR.search("#cartao_resultado { }")
    assert NOME_DE_COR.search("cor=theme.COLORS['accent']")
    assert NOME_DE_COR.search("fundo: str = estilo.TRILHO_CTK")
    assert NOME_DE_COR.search('"fg": "white"')
    assert NOME_DE_COR.search('titulo.setStyleSheet("color: gray; font-size: 16px;")')
    assert NOME_DE_COR.search('r.setStyleSheet(f"font-size: 13px; color: {cor};")')
    assert not NOME_DE_COR.search('r.setStyleSheet("font-size: 13px; background: transparent;")')
    assert not NOME_DE_COR.search("p = estilo.paleta_atual()")


# --- As cores de texto que esta varredura levou para a folha (2026-10-20) -----------

import pytest  # noqa: E402

from sigft.app import tokens  # noqa: E402
from sigft.app_qt import estilo  # noqa: E402


@pytest.mark.parametrize("tema", ["escuro", "claro"])
@pytest.mark.parametrize("fundo", ["fundo", "superficie", "superficie_alta"])
def test_destaque_se_le_onde_aparece(tema, fundo):
    # O título de seção verde (`papel="destaque"`) vai no fundo, no cartão e no
    # quadro de dentro das abas do PDM.
    p = tokens.paleta(tema)
    assert f'QLabel[papel="destaque"] {{ color: {p["primaria"]}; }}' in estilo.folha_de_estilo(tema)
    assert tokens.contraste(p["primaria"], p[fundo]) >= 4.5


@pytest.mark.parametrize("tema", ["escuro", "claro"])
def test_cores_do_mural_se_leem_no_fundo_e_no_cartao(tema):
    p = tokens.paleta(tema)
    folha = estilo.folha_de_estilo(tema)
    for faixa, cor in estilo.COR_DA_FAIXA[tema].items():
        assert f'QLabel[faixa="{faixa}"] {{ color: {cor}; }}' in folha
        for fundo in ("fundo", "superficie"):
            assert tokens.contraste(cor, p[fundo]) >= 4.5, (faixa, fundo)


def test_texto_da_aba_escolhida_se_le_na_marca():
    for tema in ("escuro", "claro"):
        assert tokens.contraste(estilo.TEXTO_SOBRE_MARCA, tokens.paleta(tema)["marca"]) >= 4.5
    assert tokens.contraste(estilo.TEXTO_SOBRE_MARCA, estilo.MARCA_HOVER) >= 4.5


def test_paleta_atual_e_a_do_tema_valendo():
    assert estilo.paleta_atual() is tokens.paleta(estilo.TEMA_ATUAL)
