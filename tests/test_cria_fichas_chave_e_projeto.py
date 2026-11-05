"""Cria Fichas, duas correções de 2026-11-05 (pedido do Luan).

1. A chave do Gemini só é exigida quando a IA do módulo É o Gemini direto. A tela passa
   `get_key("GEMINI")`; o OpenRouter e o Workflow AMP têm a credencial deles, e o lote parava
   com "API Key não configurada." mesmo sem usar o Gemini.
2. O código do projeto é a linha ABAIXO do título "GERENCIAMENTO DOS MATERIAIS SOBRESSALENTES
   CADASTRADOS NO PMIB". Era a linha acima do cabeçalho, e no layout v2 essa linha é a da
   revisão em uso ("REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: ...").
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from sigft import config
from sigft.services import cria_fichas


class _LLMFalso:
    """O `LLMClient` do categorizador, com o provedor que o teste escolher."""

    def __init__(self, provider_name):
        self.provider_name = provider_name
        self.model = "um-modelo"
        self.chamadas = []

    def generate(self, prompt, *, system=None, json_mode=False, tags=None):
        self.chamadas.append(tags)
        return SimpleNamespace(parsed_json=[{"item_processado": 1, "pdm_escolhido": "NENHUM"}])


class _UmItem:
    _LINHA = {"DESCRIÇÃO": "BOMBA KSB", "MARCA/MODELO": "KSB", "CÓDIGO DO MATERIAL": "1", "UNID.": "PC"}

    def iterrows(self):
        return iter([(0, self._LINHA)])

    def __len__(self):
        return 1


class _Catalogo:
    def lista_por_classe(self):
        return ""

    def manual_de_regras(self, numeros=None):
        return ""

    def candidatos(self, texto, limite=None):
        return []

    def bloco_de_candidatos(self, pdms):
        return ""


def _categorizador(monkeypatch, provider_name, chave=""):
    llm = _LLMFalso(provider_name)
    monkeypatch.setattr(cria_fichas, "get_llm", lambda *_a, **_k: llm)
    return cria_fichas.GeminiCategorizer(chave), llm


# -- 1. a chave do Gemini ---------------------------------------------------------------

@pytest.mark.parametrize("provider", [config.PROVIDER_OPENROUTER, config.PROVIDER_AMP_WORKFLOW])
def test_fora_do_gemini_o_lote_roda_sem_a_chave_do_gemini(monkeypatch, provider):
    cat, llm = _categorizador(monkeypatch, provider)
    resultado = cat.processar_lote(_UmItem(), _Catalogo())
    assert len(resultado) == 1 and len(llm.chamadas) == 1


def test_no_gemini_direto_sem_a_chave_o_lote_para_antes_da_ia(monkeypatch):
    cat, llm = _categorizador(monkeypatch, config.PROVIDER_GEMINI)
    with pytest.raises(ValueError, match="^API Key não configurada"):
        cat.processar_lote(_UmItem(), _Catalogo())
    assert llm.chamadas == []


def test_no_gemini_direto_com_a_chave_o_lote_roda(monkeypatch):
    cat, llm = _categorizador(monkeypatch, config.PROVIDER_GEMINI, chave="uma-chave")
    cat.processar_lote(_UmItem(), _Catalogo())
    assert len(llm.chamadas) == 1


def test_as_duas_passadas_no_workflow_rodam_sem_a_chave_do_gemini(monkeypatch):
    cat, _llm = _categorizador(monkeypatch, config.PROVIDER_AMP_WORKFLOW)
    monkeypatch.setattr(cat, "interpretar_lote", lambda df, callback_log=None: [None])
    monkeypatch.setattr(cat, "processar_lote", lambda *a, **k: [{"pdm_escolhido": "NENHUM"}])
    monkeypatch.setattr(cria_fichas, "preparar_para_revisao", lambda *a, **k: ("linhas", {"contagem": 0}))
    assert cat.classificar_para_revisao(_UmItem(), _Catalogo(), "PROJ") == ("linhas", {"contagem": 0})


def test_fora_do_gemini_nao_avisa_que_falta_a_chave(monkeypatch, capsys):
    _categorizador(monkeypatch, config.PROVIDER_OPENROUTER)
    assert "Nenhuma API Key" not in capsys.readouterr().out


# -- 2. o código do projeto --------------------------------------------------------------

TITULO = "GERENCIAMENTO DOS MATERIAS SOBRESSALENTES CADASTRADOS NO PMIB"
PROJETO = "03 - EBOP / 09 / AR COMPRIMIDO | #ITA0=Y01TF001&BPB020 / 4500063671 | Evento 12"
REVISAO = "REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: 0A - DATA DE ALTERAÇÃO: 03/09/2026"
NAN = float("nan")
CABECALHO = ["ITEM", "QTD.", "DESCRIÇÃO", "CÓDIGO PMIB"]


def test_v2_o_projeto_e_o_de_baixo_do_titulo_e_nao_a_revisao():
    linhas = [[NAN] * 4, [TITULO] + [NAN] * 3, [PROJETO] + [NAN] * 3, [REVISAO] + [NAN] * 3, CABECALHO]
    assert cria_fichas.codigo_do_projeto_sugerido(linhas, 4) == PROJETO


def test_sem_o_titulo_continua_a_celula_acima_do_item():
    """Planilha sem o título (fora do template): o jeito de antes."""
    linhas = [["OUTRA COISA", NAN, NAN, NAN], [NAN, "PROJ-ANTIGO", NAN, NAN], [NAN, "ITEM", "DESCRIÇÃO", "CÓDIGO PMIB"]]
    assert cria_fichas.codigo_do_projeto_sugerido(linhas, 2) == "PROJ-ANTIGO"


def test_sem_o_titulo_a_linha_da_revisao_nunca_vira_projeto():
    """v2 sem o título (a fixture anonimizada): a linha acima do cabeçalho é a da revisão, e o
    projeto está na de cima dela."""
    linhas = [["OUTRA COISA", NAN], ["PROJ-V2", NAN], [REVISAO, NAN], ["ITEM", "DESCRIÇÃO"]]
    assert cria_fichas.codigo_do_projeto_sugerido(linhas, 3) == "PROJ-V2"


def test_cabecalho_na_primeira_linha_sem_titulo_nao_sugere_nada():
    assert cria_fichas.codigo_do_projeto_sugerido([CABECALHO, [1, 2, "X", "Y"]], 0) == ""


def test_carregar_planilha_sugere_o_projeto_de_baixo_do_titulo(monkeypatch):
    """O fio da tela: `carregar_planilha_inteligente` devolve o projeto da linha certa."""
    previa = [[NAN] * 4, [TITULO] + [NAN] * 3, [PROJETO] + [NAN] * 3, [REVISAO] + [NAN] * 3, CABECALHO, [1, 2, "BOMBA", "X"]]

    def ler(arquivo, sheet_name=None, header=None, nrows=None, dtype=None):
        if header is None:
            return SimpleNamespace(values=SimpleNamespace(tolist=lambda: previa))
        assert header == 4
        return MagicMock()

    monkeypatch.setattr(cria_fichas.pd, "read_excel", ler)
    df, sugerido, erro = cria_fichas.DataManager.carregar_planilha_inteligente(
        "x.xlsx", "Lista de Materiais", ["DESCRIÇÃO", "CÓDIGO PMIB"])
    assert (sugerido, erro) == (PROJETO, None) and df is not None
