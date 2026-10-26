"""O motor do STATUS REAL copiado do DocManager continua dando os mesmos vereditos.

Portados de `luanccozer/DocManager@c9683d2`, `tests/test_status_engine.py`: só os
casos com o valor esperado escrito. Os que comparam com o `DataManager` legado
ficaram no DocManager (o legado não veio para cá). Se um destes falhar, a cópia
em `sigft/core/aconex/_docmanager/` divergiu do DocManager.
"""
from __future__ import annotations

import importlib

import pytest

import _historico_aconex
from _historico_aconex import HistoricoBuilder
from _pandas_de_verdade import pandas_de_verdade
from sigft.core.aconex._docmanager import (
    comissionamento,
    constants,
    excecoes,
    normalize,
    status_engine,
    truth_line,
)

# Ordem de dependência: quem é importado vem antes de quem importa.
MODULOS_COPIADOS = (constants, normalize, excecoes, comissionamento, truth_line, status_engine)


@pytest.fixture(autouse=True)
def _pandas_real():
    """O `constants.py` calcula `DATA_CORTE_FLUXO = pd.Timestamp(...)` ao ser
    importado: com o dublê do conftest, a constante nasceria dublê. Recarregar
    dentro do bloco faz as constantes de módulo nascerem com o pandas real."""
    with pandas_de_verdade(_historico_aconex):
        for modulo in MODULOS_COPIADOS:
            importlib.reload(modulo)
        yield


def _real(builder, rev):
    return status_engine.calcular_status_real(builder.build(), rev)


@pytest.mark.parametrize("status_bruto", ["Cancelado", "Anulado", "VOID", "Void", "void", "Issued for Annulment"])
def test_anulacao_vira_sempre_cancelado(status_bruto):
    b = HistoricoBuilder("T", "IT", "CMI").evento("0A", 1, status_bruto, "01/03/2024", current=True)
    assert _real(b, "0A") == "Cancelado"


def test_aprovado_direto():
    b = HistoricoBuilder("T", "IT", "CMI").evento("0A", 1, "Aprovado", "01/03/2024", current=True)
    assert _real(b, "0A") == "Aprovado"


def test_revisao_vigente_inexistente_nao_emitido():
    b = HistoricoBuilder("T", "IT", "CMI").evento("0A", 1, "Aprovado", "01/03/2024")
    assert _real(b, "0B") == "NÃO EMITIDO"


def test_fantasma_com_salvamento_na_propria_revisao():
    b = (HistoricoBuilder("T", "IT", "CMI")
         .evento("0A", 1, "Aprovado", "01/03/2024")
         .evento("0A", 2, "Em Integração", "05/03/2024", current=True))
    assert _real(b, "0A") == "Aprovado"


def test_fantasma_resgatando_fantasma_vira_nao_emitido():
    b = (HistoricoBuilder("T", "IT", "CMI")
         .evento("0A", 1, "Integrado", "01/03/2024")
         .evento("0B", 1, "Em Integração", "05/03/2024", current=True))
    assert _real(b, "0B") == "NÃO EMITIDO"


def test_mudanca_de_familia_reseta_aprovacao():
    b = (HistoricoBuilder("T", "IT", "CMI")
         .evento("0", 1, "Aprovado", "01/03/2024")
         .evento("1A", 1, "Em Processo", "05/04/2024", current=True))
    assert _real(b, "1A") == "Em Processo"


def test_reprovado_vence_com_atual_fantasma():
    b = (HistoricoBuilder("T", "IT", "CMI")
         .evento("0A", 1, "Não Aprovado", "01/03/2024")
         .evento("0B", 1, "Em Integração", "05/04/2024", current=True))
    assert _real(b, "0B") == "Não Aprovado"


def test_reprovado_com_atual_em_processo_vira_em_processo():
    b = (HistoricoBuilder("T", "IT", "CMI")
         .evento("0A", 1, "Não Aprovado", "01/03/2024")
         .evento("0B", 1, "Em Processo", "05/04/2024", current=True))
    assert _real(b, "0B") == "Em Processo"


def test_reprovacao_em_revisao_numerica_ignorada():
    b = (HistoricoBuilder("T", "IT", "CMI")
         .evento("0A", 1, "Aprovado", "01/03/2024")
         .evento("0", 1, "Não Aprovado", "05/04/2024")
         .evento("1A", 1, "Em Integração", "10/05/2024", current=True))
    assert _real(b, "1A") == "Aprovado"
