r"""O categorizador em duas passadas (2026-10-08).

Spec: docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md.
"""
from __future__ import annotations

from sigft.core import pdm_catalogo
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


# =============================================================================
# 2. A passada 2 com a interpretação
#    Os candidatos de um item aparecem como "- <PDM>  [classe N]"; a LISTA DE
#    PDMS POR CLASSE traz todo PDM como "- <PDM>", sem o "[classe". É o sufixo
#    que diz se o PDM chegou como CANDIDATO.
# =============================================================================
def _pdm(codigo, base, mod="", caracts=()):
    titulo = f"{base} {mod}".strip()
    return pdm_catalogo.PDM(codigo=codigo, classe=codigo.split(".")[1], titulo=titulo,
                            nome_base=base, modificador=mod, caracteristicas=tuple(caracts))


DISPLAY_CERTO = _pdm("PDM.6685.017", "INDICADOR", "DIGITAL",
                     ["CARACTERISTICAS DO DISPLAY", "FAIXA DE MEDICAO"])


def _catalogo_do_display():
    distratores = []
    for palavra, classe in (("CRISTAL", "5340"), ("LIQUIDO", "6850"),
                            ("VERDE", "6210"), ("BACKLIGHT", "6625"),
                            ("CRISTAL", "4820")):
        for j in range(3):
            distratores.append(_pdm(f"PDM.{classe}.{j:03d}", palavra, f"TIPO{j}"))
    return pdm_catalogo.CatalogoPDM(pdms=[DISPLAY_CERTO] + distratores)


DISPLAY = _linha("DISPLAY CRISTAL LIQUIDO 20X2 BACKLIGHT VERDE")
INTERP_DISPLAY = Interpretacao(e="INDICADOR DIGITAL", sinonimos=("MOSTRADOR", "DISPLAY LCD"))


def test_sem_interpretacao_o_display_nao_chega_como_candidato():
    llm = _LLMFalso([])
    _categorizador(llm=llm).processar_lote(_DataFrameFalso([DISPLAY]), _catalogo_do_display())
    assert "- PDM.6685.017 - INDICADOR DIGITAL  [classe 6685]" not in llm.chamadas[0]["prompt"]


def test_com_interpretacao_o_display_chega_ao_prompt_como_candidato():
    llm = _LLMFalso([])
    _categorizador(llm=llm).processar_lote(_DataFrameFalso([DISPLAY]), _catalogo_do_display(),
                                           interpretacoes=[INTERP_DISPLAY])
    assert "- PDM.6685.017 - INDICADOR DIGITAL  [classe 6685]" in llm.chamadas[0]["prompt"]


def test_o_item_leva_a_linha_da_interpretacao():
    llm = _LLMFalso([])
    interp = Interpretacao(e="PLAQUETA INDICADORA", sinonimos=("PLACA",),
                           serve="VALVULA DUPLOMATIC")
    _categorizador(llm=llm).processar_lote(
        _DataFrameFalso([_linha("PLAQUETA PARA VALVULA")]), _catalogo_do_display(),
        interpretacoes=[interp])
    assert ("- Interpretação: é PLAQUETA INDICADORA · sinônimos: PLACA · "
            "serve a: VALVULA DUPLOMATIC") in llm.chamadas[0]["prompt"]


def test_item_sem_interpretacao_nao_leva_a_linha():
    llm = _LLMFalso([])
    _categorizador(llm=llm).processar_lote(_DataFrameFalso([DISPLAY]), _catalogo_do_display(),
                                           interpretacoes=[None])
    assert "- Interpretação:" not in llm.chamadas[0]["prompt"]


def test_ultimos_candidatos_fica_alinhado_ao_lote():
    cat = _categorizador(llm=_LLMFalso([]))
    cat.processar_lote(_DataFrameFalso([DISPLAY, _linha("ZZZZ")]), _catalogo_do_display(),
                       interpretacoes=[INTERP_DISPLAY, None])
    assert len(cat.ultimos_candidatos) == 2
    assert "PDM.6685.017" in [p.codigo for p in cat.ultimos_candidatos[0]]
    assert cat.ultimos_candidatos[1] == []


# =============================================================================
# 3. Os exemplos vêm do catálogo
# =============================================================================
def test_o_exemplo_da_plaqueta_entra_com_o_titulo_do_master():
    plaqueta = _pdm("PDM.5930.012", "PLAQUETA", "INDICADORA", ["MATERIAL"])
    llm = _LLMFalso([])
    _categorizador(llm=llm).processar_lote(
        _DataFrameFalso([_linha("X")]), pdm_catalogo.CatalogoPDM(pdms=[plaqueta]))
    assert "- PDM: PDM.5930.012 - PLAQUETA INDICADORA" in llm.chamadas[0]["prompt"]


def test_exemplo_cujo_pdm_nao_esta_no_master_carregado_nao_entra():
    llm = _LLMFalso([])
    _categorizador(llm=llm).processar_lote(
        _DataFrameFalso([_linha("X")]), _catalogo_do_display())
    prompt = llm.chamadas[0]["prompt"]
    assert "PDM.7010.018" not in prompt          # SERVIDOR não está neste catálogo
    assert "- PDM: PDM.6685.017 - INDICADOR DIGITAL" in prompt
