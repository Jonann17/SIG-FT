"""`pmib_manager.achar_aba` — achar a aba certa, não a que estava aberta.

Escrito por causa de um erro REAL, em 2026-09-03. O usuário rodou o PMIB
Manager e recebeu:

    [ERRO] Coluna 'N° DOCUMENTO ITAIPU' não encontrada na Mestra.

Causa: o código usava `wb.active` — a aba que estava SELECIONADA quando a
planilha foi salva pela última vez. Ele tinha salvado o arquivo com outra aba
aberta, e o código foi procurar a coluna na aba errada.

`wb.active` nunca foi uma forma de ACHAR uma aba: é só a que o Excel mostra ao
abrir. E a planilha tem 3 abas (4 com a Lista de preços), então a chance de
acertar só diminui.
"""
from __future__ import annotations

from sigft.services.pmib_manager import (
    COLUNA_CHAVE_SOBRESSALENTES,
    NOME_ABA_SOBRESSALENTES,
    achar_aba,
)


class CelulaFalsa:
    def __init__(self, valor):
        self.value = valor


class WsFalsa:
    def __init__(self, titulo, cabecalho=()):
        self.title = titulo
        self._cabecalho = [CelulaFalsa(v) for v in cabecalho]

    def __getitem__(self, linha):
        return self._cabecalho if linha == 2 else []


class WbFalso:
    """Dublê de workbook. `active` é DE PROPÓSITO a aba errada: é o cenário
    que quebrou na mão do usuário."""

    def __init__(self, abas):
        self._abas = {ws.title: ws for ws in abas}
        self.sheetnames = [ws.title for ws in abas]
        self.active = abas[-1]

    def __getitem__(self, nome):
        return self._abas[nome]


CABECALHO = ("N° DOCUMENTO ITAIPU", "N° DOCUMENTO CMI", "DESCRIÇÃO")


def test_acha_pelo_nome_mesmo_com_outra_aba_ativa():
    """O cenário exato do erro de 2026-09-03."""
    wb = WbFalso([
        WsFalsa(NOME_ABA_SOBRESSALENTES, CABECALHO),
        WsFalsa("Dropbox"),
        WsFalsa("Atividades", ("NV", "CÓDIGO ITAIPU")),
    ])
    assert wb.active.title == "Atividades"  # o que `wb.active` daria

    ws, motivo = achar_aba(wb, NOME_ABA_SOBRESSALENTES, COLUNA_CHAVE_SOBRESSALENTES)

    assert ws.title == NOME_ABA_SOBRESSALENTES
    assert NOME_ABA_SOBRESSALENTES in motivo


def test_acha_pelo_CONTEUDO_quando_a_aba_foi_renomeada():
    """O nome da aba é editável pelo usuário; renomeá-la não deve quebrar o
    app enquanto a estrutura continuar lá."""
    wb = WbFalso([
        WsFalsa("Sobressalentes (renomeada)", CABECALHO),
        WsFalsa("Atividades", ("NV",)),
    ])

    ws, motivo = achar_aba(wb, NOME_ABA_SOBRESSALENTES, COLUNA_CHAVE_SOBRESSALENTES)

    assert ws.title == "Sobressalentes (renomeada)"
    assert "achada pela coluna" in motivo


def test_o_nome_vence_o_conteudo():
    """Havendo a aba com o nome esperado, ela ganha — mesmo que outra também
    tenha a coluna."""
    wb = WbFalso([
        WsFalsa("Cópia antiga", CABECALHO),
        WsFalsa(NOME_ABA_SOBRESSALENTES, CABECALHO),
    ])

    ws, _ = achar_aba(wb, NOME_ABA_SOBRESSALENTES, COLUNA_CHAVE_SOBRESSALENTES)

    assert ws.title == NOME_ABA_SOBRESSALENTES


def test_nenhuma_aba_serve_devolve_None_e_LISTA_as_abas():
    """A mensagem tem de dizer o que existe — senão o usuário fica sabendo só
    o que falta, que é o menos útil dos dois."""
    wb = WbFalso([WsFalsa("Dropbox"), WsFalsa("Atividades", ("NV",))])

    ws, motivo = achar_aba(wb, NOME_ABA_SOBRESSALENTES, COLUNA_CHAVE_SOBRESSALENTES)

    assert ws is None
    assert "Dropbox" in motivo and "Atividades" in motivo
    assert COLUNA_CHAVE_SOBRESSALENTES in motivo


def test_comparacao_de_cabecalho_ignora_caixa_e_espaco():
    wb = WbFalso([WsFalsa("qualquer", ("  n° documento itaipu  ",))])

    ws, _ = achar_aba(wb, NOME_ABA_SOBRESSALENTES, COLUNA_CHAVE_SOBRESSALENTES)

    assert ws is not None


def test_a_linha_do_cabecalho_e_configuravel():
    """A aba de sobressalentes tem cabeçalho na linha 2; a de preços, na 1."""
    class WsLinha1(WsFalsa):
        def __getitem__(self, linha):
            return self._cabecalho if linha == 1 else []

    wb = WbFalso([WsLinha1("preços", ("N° DOCUMENTO ITAIPU",))])

    ws, _ = achar_aba(wb, "inexistente", COLUNA_CHAVE_SOBRESSALENTES, linha_cabecalho=1)

    assert ws is not None
