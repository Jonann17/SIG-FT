r"""O categorizador em duas passadas (2026-10-08).

Spec: docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md.
"""
from __future__ import annotations

from sigft.core.llm.client import LLMResponse
from sigft.services import cria_fichas
from sigft.services.cria_fichas_escolha import Interpretacao


class _LLMFalso:
    """Grava cada chamada e devolve as respostas em sequência (a última se
    repete). Uma `Exception` na sequência é levantada naquela chamada."""

    provider_name = "falso"
    model = "falso-1"

    def __init__(self, *respostas):
        self.respostas = list(respostas) or [[]]
        self.chamadas = []

    def generate(self, prompt, *, system=None, json_mode=False, tags=None):
        self.chamadas.append({"prompt": prompt, "tags": tags})
        resposta = self.respostas[min(len(self.chamadas), len(self.respostas)) - 1]
        if isinstance(resposta, Exception):
            raise resposta
        return LLMResponse(text="", parsed_json=resposta, tokens_in=None,
                           tokens_out=None, custo_usd=None, model=self.model,
                           provider="gemini", duracao_s=0.0)


class _DataFrameFalso:
    """`iterrows` mínimo -- a suíte roda sem pandas real."""

    def __init__(self, linhas):
        self._linhas = linhas

    def iterrows(self):
        return enumerate(self._linhas)

    def __len__(self):
        return len(self._linhas)


def _linha(descricao, marca=""):
    return {"DESCRIÇÃO": descricao, "MARCA/MODELO": marca,
            "CÓDIGO DO MATERIAL": "1", "UNID.": "PC"}


def _categorizador(llm_interpretacao=None, llm=None):
    cat = cria_fichas.GeminiCategorizer("uma-chave")
    if llm_interpretacao is not None:
        cat._llm_interpretacao = llm_interpretacao
    if llm is not None:
        cat._llm = llm
    return cat


# =============================================================================
# 1. A passada 1
# =============================================================================
def test_interpretar_lote_devolve_uma_interpretacao_por_item():
    llm = _LLMFalso([{"item": 1, "e": "PLAQUETA INDICADORA", "sinonimos": [],
                      "serve": "VALVULA DUPLOMATIC"}])
    cat = _categorizador(llm_interpretacao=llm)

    lidas = cat.interpretar_lote(_DataFrameFalso([
        _linha("PLAQUETA EM ALUMINIO PARA VALVULA DUPLOMATIC", "DUPLOMATIC")]))

    assert lidas == [Interpretacao(e="PLAQUETA INDICADORA", serve="VALVULA DUPLOMATIC")]
    assert llm.chamadas[0]["tags"] == {"modulo": "cria_fichas_no_pmib_v1_backend",
                                       "tarefa": "interpretar_material"}
    assert "PLAQUETA EM ALUMINIO PARA VALVULA DUPLOMATIC" in llm.chamadas[0]["prompt"]


def test_interpretar_lote_e_uma_chamada_so_para_lote_pequeno():
    llm = _LLMFalso([])
    _categorizador(llm_interpretacao=llm).interpretar_lote(
        _DataFrameFalso([_linha(f"ITEM {i}") for i in range(30)]))
    assert len(llm.chamadas) == 1


def test_interpretar_lote_fatia_acima_de_60_itens():
    llm = _LLMFalso([])
    lidas = _categorizador(llm_interpretacao=llm).interpretar_lote(
        _DataFrameFalso([_linha(f"ITEM {i}") for i in range(61)]))
    assert len(llm.chamadas) == 2
    assert len(lidas) == 61


def test_interpretar_lote_que_falha_NAO_derruba_o_lote():
    logs = []
    cat = _categorizador(llm_interpretacao=_LLMFalso(RuntimeError("sem chave")))

    lidas = cat.interpretar_lote(_DataFrameFalso([_linha("A"), _linha("B")]),
                                 callback_log=logs.append)

    assert lidas == [None, None]
    assert logs == ["IA: interpretação indisponível (sem chave). "
                    "Seguindo só com a busca por palavras."]


def test_interpretar_lote_que_falha_na_2a_fatia_guarda_a_1a():
    logs = []
    llm = _LLMFalso([{"item": 1, "e": "BOMBA"}], RuntimeError("rede"))

    lidas = _categorizador(llm_interpretacao=llm).interpretar_lote(
        _DataFrameFalso([_linha(f"ITEM {i}") for i in range(61)]), callback_log=logs.append)

    assert len(lidas) == 61
    assert lidas[0] == Interpretacao(e="BOMBA")
    assert lidas[60] is None
    assert len(logs) == 1


def test_modelo_da_interpretacao_descreve_o_cliente_da_passada_1():
    assert _categorizador(llm_interpretacao=_LLMFalso()).modelo_da_interpretacao == "falso/falso-1"


def test_PDM_NENHUM_continua_importavel_pelo_nome_antigo():
    assert cria_fichas.PDM_NENHUM == "NENHUM"
