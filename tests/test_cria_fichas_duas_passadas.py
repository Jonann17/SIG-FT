r"""O categorizador em duas passadas (2026-10-08).

Spec: docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md.
"""
from __future__ import annotations

import pytest

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


# =============================================================================
# 4. preparar_para_revisao -- 1º o comportamento que o laço da TELA tinha
#    (views/cria_fichas.py, antes de 2026-10-08), depois o novo
# =============================================================================
PLAQUETA = _pdm("PDM.5930.012", "PLAQUETA", "INDICADORA", ["MATERIAL", "TEXTO GRAVADO"])
CAT_REVISAO = pdm_catalogo.CatalogoPDM(pdms=[DISPLAY_CERTO, PLAQUETA])


def _preparar(respostas, linhas, interpretacoes=None, candidatos=None):
    logs = []
    saida, contagem = cria_fichas.preparar_para_revisao(
        respostas, linhas, CAT_REVISAO,
        interpretacoes or [None] * len(linhas),
        candidatos or [[] for _ in linhas],
        "PROJ-1", callback_log=logs.append)
    return saida, contagem, logs


def test_CARACTERIZACAO_item_sem_resposta_vira_nenhum_e_e_contado():
    saida, contagem, logs = _preparar([None], [_linha("PLAQUETA DE TESTE")])
    assert saida[0]["pdm_escolhido"] == "NENHUM"
    assert contagem["sem_resposta"] == 1
    assert logs == [" -> ⚠️ Item 1 sem resposta da IA. Marcado 'NENHUM' "
                    "para revisão: PLAQUETA DE TESTE"]


def test_CARACTERIZACAO_pdm_inventado_vira_nenhum_e_e_contado():
    saida, contagem, logs = _preparar(
        [{"pdm_escolhido": "PDM.0000.000 - INVENTADO"}], [_linha("X")])
    assert saida[0]["pdm_escolhido"] == "NENHUM"
    assert contagem["fora_do_catalogo"] == 1
    assert logs == [" -> ⚠️ Item 1: PDM fora do catalogo: 'PDM.0000.000 - INVENTADO'. "
                    "Marcado 'NENHUM'."]


def test_CARACTERIZACAO_codigo_certo_com_titulo_errado_e_consertado():
    saida, _, _ = _preparar([{"pdm_escolhido": "PDM.5930.012 - PLAQUETA, INDICADORA"}],
                            [_linha("X")])
    assert saida[0]["pdm_escolhido"] == "PDM.5930.012 - PLAQUETA INDICADORA"


def test_CARACTERIZACAO_leva_projeto_e_descricao_original():
    saida, _, _ = _preparar([{"pdm_escolhido": "NENHUM"}], [_linha("DESC ORIGINAL")])
    assert saida[0]["codigo_projeto"] == "PROJ-1"
    assert saida[0]["descricao_original"] == "DESC ORIGINAL"


def test_a_resposta_original_nao_e_alterada():
    respostas = [{"pdm_escolhido": "PDM.5930.012 - PLAQUETA, INDICADORA"}]
    _preparar(respostas, [_linha("X")])
    assert respostas[0]["pdm_escolhido"] == "PDM.5930.012 - PLAQUETA, INDICADORA"


# --- o novo ------------------------------------------------------------------
def test_alta_sem_conferencia_e_rebaixada():
    saida, _, _ = _preparar([{"pdm_escolhido": "PDM.5930.012", "confianca": "ALTA"}],
                            [_linha("X")])
    assert saida[0]["confianca"] == "ALTA"
    assert saida[0]["confianca_final"] == "MEDIA"
    assert saida[0]["rebaixada"] is True


def test_alta_confirmada_continua_alta():
    resposta = {"pdm_escolhido": "PDM.5930.012", "confianca": "ALTA",
                "caracteristicas_que_confirmam": ["TEXTO GRAVADO"]}
    saida, _, _ = _preparar(
        [resposta], [_linha("PLAQUETA PARA VALVULA")],
        interpretacoes=[Interpretacao(e="PLAQUETA INDICADORA")], candidatos=[[PLAQUETA]])
    assert saida[0]["sinais"] == {"na_busca": True, "nome_base": True, "caracteristicas": True}
    assert saida[0]["confianca_final"] == "ALTA"
    assert saida[0]["rebaixada"] is False


def test_nenhum_da_ia_nao_tem_confianca_e_guarda_a_origem():
    saida, _, _ = _preparar([{"pdm_escolhido": "NENHUM", "confianca": "ALTA"}], [_linha("X")])
    assert saida[0]["confianca"] == ""
    assert saida[0]["confianca_final"] == ""
    assert saida[0]["origem_do_nenhum"] == "ia"


def test_origem_do_nenhum_distingue_as_tres_causas():
    saida, _, _ = _preparar(
        [None, {"pdm_escolhido": "PDM.0000.000"}, {"pdm_escolhido": "PDM.5930.012"}],
        [_linha("A"), _linha("B"), _linha("C")])
    assert [s["origem_do_nenhum"] for s in saida] == ["sem_resposta", "fora_do_catalogo", ""]


def test_alternativa_recusada_e_logada_e_contada():
    saida, contagem, logs = _preparar(
        [{"pdm_escolhido": "PDM.5930.012",
          "alternativas": [{"pdm": "PDM.9999.999 - NAO EXISTE", "motivo": "x"}]}],
        [_linha("X")])
    assert saida[0]["alternativas"] == []
    assert contagem["alternativas_recusadas"] == 1
    assert logs == [" -> ⚠️ Item 1: alternativa fora do catálogo descartada: "
                    "'PDM.9999.999 - NAO EXISTE'"]


def test_caracteristica_citada_que_o_pdm_nao_tem_e_logada():
    saida, _, logs = _preparar(
        [{"pdm_escolhido": "PDM.5930.012", "caracteristicas_que_confirmam": ["TORQUE"]}],
        [_linha("X")])
    assert saida[0]["sinais"]["caracteristicas"] is False
    assert logs == [" -> ⚠️ Item 1: característica citada que o PDM não tem: 'TORQUE'"]


def test_guarda_o_que_a_ia_disse_para_a_calibracao():
    saida, _, _ = _preparar(
        [{"pdm_escolhido": "PDM.6685.017", "confianca": "baixa", "justificativa": " é um display "}],
        [_linha("DISPLAY", marca="ACME")],
        interpretacoes=[Interpretacao(e="INDICADOR DIGITAL", sinonimos=("MOSTRADOR",))])
    linha = saida[0]
    assert linha["pdm_ia"] == "PDM.6685.017 - INDICADOR DIGITAL"
    assert linha["confianca"] == "BAIXA"
    assert linha["justificativa"] == "é um display"
    assert linha["marca_modelo"] == "ACME"
    assert linha["interpretacao"] == {"e": "INDICADOR DIGITAL",
                                      "sinonimos": ["MOSTRADOR"], "serve": ""}


# =============================================================================
# 5. As duas passadas de ponta a ponta
# =============================================================================
def test_classificar_para_revisao_de_ponta_a_ponta():
    llm1 = _LLMFalso([{"item": 1, "e": "INDICADOR DIGITAL", "sinonimos": ["MOSTRADOR"]}])
    llm2 = _LLMFalso([{"item_processado": 1, "pdm_escolhido": "PDM.6685.017",
                       "confianca": "ALTA",
                       "caracteristicas_que_confirmam": ["CARACTERISTICAS DO DISPLAY"]}])
    cat = _categorizador(llm_interpretacao=llm1, llm=llm2)
    logs = []

    linhas, contagem = cat.classificar_para_revisao(
        _DataFrameFalso([DISPLAY]), _catalogo_do_display(), "PROJ-1", callback_log=logs.append)

    assert linhas[0]["pdm_escolhido"] == "PDM.6685.017 - INDICADOR DIGITAL"
    assert linhas[0]["confianca_final"] == "ALTA"
    assert linhas[0]["sinais"]["na_busca"] is True
    assert contagem["sem_resposta"] == 0
    assert "IA: 1 de 1 itens interpretados." in logs


def test_classificar_sem_chave_nao_chama_ia_nenhuma():
    """No Gemini direto. Desde 2026-11-05, fora dele (OpenRouter, Workflow AMP) a chave do Gemini
    não é cobrada: ver `test_cria_fichas_chave_e_projeto.py`."""
    llm1, llm2 = _LLMFalso([]), _LLMFalso([])
    llm2.provider_name = "gemini"
    cat = cria_fichas.GeminiCategorizer("")
    cat._llm_interpretacao, cat._llm = llm1, llm2
    with pytest.raises(ValueError):
        cat.classificar_para_revisao(_DataFrameFalso([DISPLAY]), _catalogo_do_display(), "P")
    assert llm1.chamadas == [] and llm2.chamadas == []


def test_classificar_com_passada_1_caida_ainda_classifica():
    llm2 = _LLMFalso([{"item_processado": 1, "pdm_escolhido": "PDM.6685.017"}])
    cat = _categorizador(llm_interpretacao=_LLMFalso(RuntimeError("rede")), llm=llm2)
    linhas, _ = cat.classificar_para_revisao(
        _DataFrameFalso([DISPLAY]), _catalogo_do_display(), "P")
    assert linhas[0]["pdm_escolhido"] == "PDM.6685.017 - INDICADOR DIGITAL"
    assert linhas[0]["interpretacao"] == {}


def test_passada_1_caida_manda_a_passada_2_igual_a_de_hoje():
    """Spec §4.8: sem a passada 1, o lote segue exatamente como hoje."""
    hoje = _LLMFalso([])
    _categorizador(llm=hoje).processar_lote(_DataFrameFalso([DISPLAY]), _catalogo_do_display())

    com_falha = _LLMFalso([])
    _categorizador(llm_interpretacao=_LLMFalso(RuntimeError("rede")), llm=com_falha) \
        .classificar_para_revisao(_DataFrameFalso([DISPLAY]), _catalogo_do_display(), "P")

    assert com_falha.chamadas[0]["prompt"] == hoje.chamadas[0]["prompt"]
