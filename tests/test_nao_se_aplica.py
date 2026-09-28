r"""`ficha_layout.e_nao_se_aplica` -- a resposta do fornecedor que nao e valor (2026-09-28).

Pedido do Luan: o fornecedor responde "nao se aplica" por desleixo, e a
caracteristica esta no datasheet. O AutoSpec passa a conferir essas respostas
contra o documento (ver
docs/superpowers/specs/2026-09-28-autospec-conferencia-fornecedor-design.md).
Para isso precisa reconhecer a FAMILIA: "N/A", "nao aplicavel", "nao
informado", "-". E, igualmente importante, NAO pode confundir com resposta de
verdade que so parece negativa ("Nao", "Nenhum", "Nao possui"): essas dizem
alguma coisa sobre o material, e o AutoSpec nunca as substitui.
"""
import pytest

from sigft.core.rpa import ficha_layout

TRAVESSAO = chr(0x2014)
MEIA_RISCA = chr(0x2013)


@pytest.mark.parametrize("valor", [
    "N/A", "n/a", "NA", "N.A.", "n.a", "N/D", "ND", "n.d.", "NSA",
    "-", "--", "---", TRAVESSAO, MEIA_RISCA, " - ",
    "Não se aplica", "NÃO SE APLICA", "nao se aplica.", "Não aplicável",
    "Nao aplicavel", "Não aplica", "Não é aplicável", "No aplica", "No se aplica",
    "No aplicable", "Not applicable", "NOT APPLICABLE", "Does not apply",
    "Não informado", "Não disponível", "Sem informação", "Não consta",
    "Not available", "Not informed", "A definir", "A confirmar",
])
def test_formas_de_nao_se_aplica(valor):
    assert ficha_layout.e_nao_se_aplica(valor)


@pytest.mark.parametrize("valor", [
    "Não se aplica ao modelo",
    "Não se aplica (item mecânico)",
    "N/A - item passivo",
    "Não aplicável, pois é um item passivo",
    "Not applicable for this model",
])
def test_frase_com_complemento_continua_sendo_nao_se_aplica(valor):
    assert ficha_layout.e_nao_se_aplica(valor)


@pytest.mark.parametrize("valor", [
    None, "", "   ",
    "Não", "NAO", "Nenhum", "Nenhuma", "Não possui", "Sem revestimento",
    "0", 0, 24, "24 Vcc", "IP65",
    "Na posição vertical",       # "na" no comeco nao e a sigla N/A
    "Nadir",                     # idem
    "Não aplicado em área classificada",   # "aplicado" nao e "aplicavel"
    "Aço inox - AISI 316",
])
def test_resposta_de_verdade_nao_e_nao_se_aplica(valor):
    assert not ficha_layout.e_nao_se_aplica(valor)
