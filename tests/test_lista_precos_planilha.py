"""`services/lista_precos_planilha.py` — a aba do follow-up.

O que dá para provar aqui, e o que não dá
------------------------------------------
A CRIAÇÃO da aba (fonte, cor de tema, bordas, larguras) precisa de openpyxl de
verdade, e o `conftest.py` o substitui por um MagicMock para a suíte rodar em
ambiente sem ele. Então a formatação foi verificada FORA da suíte, numa cópia
da planilha real, comparando atributo a atributo com a aba
`Acompanhamento Sobressalente` — fonte, negrito, cor `FF002060`, tema 3, tint
0.7998, alinhamento, borda e altura saíram idênticos.

O que se prova aqui é o que não depende de Excel: as colunas e a ordem delas,
quais são do app e quais são do usuário, e a leitura de uma aba existente.
"""
from __future__ import annotations

from sigft.services import lista_precos_planilha as lpp


class CelulaFalsa:
    def __init__(self, valor=None):
        self.value = valor


class WorksheetFalsa:
    """Dublê de worksheet: só `cell()`, `max_row` e `max_column`."""

    def __init__(self, grade):
        self._grade = grade
        self.max_row = max((r for r, _ in grade), default=0)
        self.max_column = max((c for _, c in grade), default=0)

    def cell(self, row, column, value=None):
        return CelulaFalsa(self._grade.get((row, column)))


# =============================================================================
# A. As colunas
# =============================================================================

def test_sao_doze_colunas():
    assert len(lpp.COLUNAS) == 12


def test_as_oito_primeiras_seguem_a_ordem_da_aba_de_sobressalentes():
    """O usuário pediu 'seguindo a mesma ordem que está no mapeamento dos
    sobressalentes'."""
    assert lpp.COLUNAS[:8] == [
        "N° DOCUMENTO ITAIPU",
        "N° DOCUMENTO CMI",
        "ÚLTIMA REVISÃO EMITIDA",
        "STATUS DA REVISÃO",
        "DATA DE ATUALIZAÇÃO",
        "DESCRIÇÃO",
        "ESPECIFICAÇÃO TÉCNICA",
        "CAPÍTULO",
    ]


def test_as_quatro_ultimas_sao_as_desta_aba():
    assert lpp.COLUNAS[8:] == [
        "LISTA DE SOBRESSALENTES",
        "ALERTA RDS-PP",
        "AÇÃO",
        "OBSERVAÇÕES",
    ]


def test_acao_e_observacoes_NAO_sao_escritas_pelo_app():
    """O requisito que decide se a aba é usável: elas carregam a decisão do
    usuário, e sobrescrevê-las apagaria o trabalho dele."""
    assert "AÇÃO" not in lpp.COLUNAS_DO_APP
    assert "OBSERVAÇÕES" not in lpp.COLUNAS_DO_APP


def test_o_app_escreve_as_dez_primeiras():
    assert lpp.COLUNAS_DO_APP == lpp.COLUNAS[:10]


def test_toda_coluna_tem_largura_definida():
    """Coluna sem largura sai com a padrão do Excel e destoa das outras."""
    for coluna in lpp.COLUNAS:
        assert coluna in lpp.LARGURAS, coluna


def test_a_descricao_e_a_coluna_mais_larga():
    """O título do Aconex é longo; é a mesma proporção da aba existente."""
    assert lpp.LARGURAS["DESCRIÇÃO"] == max(lpp.LARGURAS.values())


# =============================================================================
# B. O cabeçalho vai na LINHA 1
# =============================================================================

def test_cabecalho_na_linha_1():
    """Decisão do usuário em 2026-09-03. A aba de sobressalentes usa a linha 2;
    esta usa a 1."""
    assert lpp.LINHA_CABECALHO == 1


def test_o_nome_da_aba_e_o_que_o_usuario_pediu():
    assert lpp.NOME_ABA == "Lista de preços Follow-up"


def test_o_estilo_do_cabecalho_e_o_da_aba_existente():
    """Valores lidos da planilha real, não escolhidos."""
    assert lpp.COR_FONTE_CABECALHO == "FF002060"
    assert lpp.TEMA_FUNDO_CABECALHO == 3
    assert round(lpp.TINT_FUNDO_CABECALHO, 4) == 0.7998
    assert lpp.ALTURA_CABECALHO == 55.5


# =============================================================================
# C. Ler uma aba que já existe
# =============================================================================

def test_mapa_de_colunas_le_o_cabecalho():
    ws = WorksheetFalsa({(1, i): t for i, t in enumerate(lpp.COLUNAS, start=1)})

    mapa = lpp.mapa_de_colunas(ws)

    assert mapa["N° DOCUMENTO ITAIPU"] == 1
    assert mapa["OBSERVAÇÕES"] == 12


def test_mapa_de_colunas_ignora_celula_vazia():
    ws = WorksheetFalsa({(1, 1): "A", (1, 3): "C"})

    assert lpp.mapa_de_colunas(ws) == {"A": 1, "C": 3}


def test_linha_por_documento_indexa_o_que_ja_esta_na_aba():
    """É o que permite ATUALIZAR a linha existente em vez de recriar a aba —
    e é por isso que AÇÃO e OBSERVAÇÕES sobrevivem."""
    ws = WorksheetFalsa(
        {
            (1, 1): "N° DOCUMENTO ITAIPU",
            (2, 1): "#A=1&X-01",
            (3, 1): "#B=2&X-01",
        }
    )

    existentes = lpp.linha_por_documento(ws, lpp.mapa_de_colunas(ws))

    assert existentes == {"#A=1&X-01": 2, "#B=2&X-01": 3}


def test_linha_por_documento_sem_a_coluna_de_codigo_devolve_vazio():
    """Aba com cabeçalho errado não pode explodir no meio do lote."""
    ws = WorksheetFalsa({(1, 1): "OUTRA COISA"})

    assert lpp.linha_por_documento(ws, lpp.mapa_de_colunas(ws)) == {}


def test_linha_por_documento_ignora_linha_sem_codigo():
    ws = WorksheetFalsa(
        {(1, 1): "N° DOCUMENTO ITAIPU", (2, 1): "#A=1&X-01", (3, 1): None}
    )

    assert lpp.linha_por_documento(ws, lpp.mapa_de_colunas(ws)) == {"#A=1&X-01": 2}


# =============================================================================
# D. O módulo não decide REGRA — só escreve
# =============================================================================

def test_a_regra_de_pareamento_nao_mora_aqui():
    """`lista_precos.py` tem a regra e se prova sem Excel; este módulo tem a
    escrita. Misturar tornaria a regra intestável sem planilha — e a regra é a
    parte que erra."""
    import inspect

    fonte = inspect.getsource(lpp)
    assert "Tracking ID" not in fonte
    assert "def parear" not in fonte
