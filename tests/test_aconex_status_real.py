"""A fachada do STATUS REAL: o status de UMA lista a partir do histórico dela, e
as regras que a mapeadora, os painéis e a Conferência de Revisões usam.

Os casos da §5.3 de `docs/superpowers/specs/2026-10-26-aconex-ao-vivo-design.md`
estão aqui com o valor escrito à mão: o status real (sem o consolidado do
DocManager) distingue Aprovado, Aprovado com Comentários e Para Assinatura.
"""
from __future__ import annotations

import importlib

import pytest

import _historico_aconex
from _historico_aconex import HistoricoBuilder
from _pandas_de_verdade import pandas_de_verdade
from sigft.core.aconex import status_real
from sigft.core.aconex._docmanager import (
    comissionamento,
    constants,
    excecoes,
    normalize,
    status_engine,
    truth_line,
)

MODULOS = (constants, normalize, excecoes, comissionamento, truth_line, status_engine, status_real)


@pytest.fixture
def pandas_real():
    """As constantes de módulo do DocManager (`DATA_CORTE_FLUXO`) precisam nascer
    com o pandas real: recarregar dentro do bloco."""
    with pandas_de_verdade(_historico_aconex):
        for modulo in MODULOS:
            importlib.reload(modulo)
        yield


def _h():
    return HistoricoBuilder("T", "#ITA0=Y01TF001&BPB020", "CMI-1")


def test_0a_aprovada_e_0b_em_processo_da_aprovado(pandas_real):
    h = (_h().evento("0", 1, "Aprovado", "01/03/2026").evento("0A", 1, "Aprovado", "01/05/2026")
         .evento("0B", 1, "Em Processo", "01/09/2026", current=True).build())
    assert status_real.status_real_do_documento(h) == "Aprovado"


def test_familia_nova_em_processo_da_em_processo(pandas_real):
    h = (_h().evento("0B", 1, "Aprovado", "01/03/2026").evento("0C", 1, "Aprovado", "01/05/2026")
         .evento("1A", 1, "Em Processo", "01/09/2026", current=True).build())
    assert status_real.status_real_do_documento(h) == "Em Processo"


def test_0b_nao_aprovada_vigente(pandas_real):
    h = (_h().evento("0A", 1, "Aprovado", "01/03/2026")
         .evento("0B", 1, "Não Aprovado", "01/09/2026", current=True).build())
    assert status_real.status_real_do_documento(h) == "Não Aprovado"


def test_para_assinatura_vigente(pandas_real):
    h = _h().evento("0", 1, "Para Assinatura", "01/09/2026", current=True).build()
    assert status_real.status_real_do_documento(h) == "Para Assinatura"


def test_aprovado_com_comentarios_mantem_o_texto(pandas_real):
    h = _h().evento("0A", 1, "Aprovado com Comentários", "01/09/2026", current=True).build()
    assert status_real.status_real_do_documento(h) == "Aprovado com Comentários"


def test_sem_revisao_vigente_da_nao_emitido(pandas_real):
    # Só uma revisão terminada (0A, <= 0A): a linha da verdade diz "nunca emitido".
    h = _h().evento("0A", 1, "Aprovado", "01/03/2026", current=True, terminated=True).build()
    assert status_real.status_real_do_documento(h) == "NÃO EMITIDO"


@pytest.mark.parametrize("status, esperado", [
    ("Aprovado", True), ("APROVADO", True), ("Aprovado com Comentários", True),
    ("aprovado com comentarios", True), ("Para Assinatura", True), ("  para   assinatura ", True),
    ("Em Processo", False), ("Não Aprovado", False), ("Informativo", False), ("", False), (None, False)])
def test_eh_aprovacao(status, esperado):
    assert status_real.eh_aprovacao(status) is esperado


@pytest.mark.parametrize("status, esperado", [
    ("NÃO EMITIDO", True), ("Não Emitido", True), ("  nao   emitido ", True),
    ("Aprovado", False), ("Em Processo", False), ("Cancelado", False), ("", False), (None, False)])
def test_eh_nao_emitido(status, esperado):
    assert status_real.eh_nao_emitido(status) is esperado


@pytest.mark.parametrize("status, esperado", [
    ("Cancelado", True), ("CANCELADO", True), ("Anulado", True), ("VOID", True), ("Issued for Annulment", True),
    ("NÃO EMITIDO", False), ("Aprovado", False), ("Não Aprovado", False), ("", False), (None, False)])
def test_eh_cancelado(status, esperado):
    assert status_real.eh_cancelado(status) is esperado


@pytest.mark.parametrize("status, esperado", [
    ("Para Assinatura", "aprovada"), ("APROVADO", "aprovada"), ("Aprovado com Comentários", "aprovada"),
    ("EM PROCESSO", "em_processo"), ("Em Processo", "em_processo"),
    ("Não Aprovado", "nao_aprovada"), ("NÃO APROVADO", "nao_aprovada"), ("NAO APROVADO", "nao_aprovada"),
    ("Cancelado", "outros"), ("NÃO EMITIDO", "outros"), ("Informativo", "outros"), ("", "outros"), (None, "outros")])
def test_categoria(status, esperado):
    assert status_real.categoria(status) == esperado


def test_ordem_das_categorias_poe_as_aprovadas_primeiro():
    assert status_real.ORDEM_DAS_CATEGORIAS == ("aprovada", "em_processo", "nao_aprovada", "outros")


@pytest.mark.parametrize("a, b, esperado", [
    ("0a", "0A ", True), ("0A", "0A", True), ("1", "1", True),
    ("0", "0A", False), ("0B", "0C", False), ("", "", False), (None, "0", False), ("0", None, False)])
def test_revisoes_iguais(a, b, esperado):
    assert status_real.revisoes_iguais(a, b) is esperado


def test_colunas_que_faltam_para_a_batalha(pandas_real):
    completo = _h().evento("0", 1, "Aprovado", "01/03/2026", current=True).build()
    assert status_real.colunas_que_faltam(completo) == []
    assert status_real.colunas_que_faltam(completo.drop(columns=["Versão", "Status da Revisão"])) == [
        "Versão", "Status da Revisão"]
