r"""
Testes do Checkpoint 3.1 — `sigft/core/llm/client.py`
(`_limpar_e_parsear_json`, `LLMClient`, `LLMResponse`).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.1. Este é o bloco
de MAIOR prioridade da suíte deste checkpoint (código novo, maior risco):

  A. `_limpar_e_parsear_json` -- direto, sem `LLMClient` nenhum: objeto
     com/sem fence, lista com/sem fence, texto com prosa antes/depois dos
     colchetes/chaves, string vazia/`None` levanta, JSON inválido levanta.
     Inclui casos que demonstram a robustez ESTRITAMENTE MAIOR desta
     implementação única em relação às 4 variantes divergentes de hoje (ver
     docstring de `_limpar_e_parsear_json` em `client.py`).
  B. `LLMClient.generate` com um PROVIDER FAKE injetado (nenhuma dependência
     de `google.generativeai`/rede): retry (`max_retries`), rate-limit
     (`min_interval_seconds`), sleep entre tentativas (`retry_sleep_seconds`),
     propagação da exceção ORIGINAL em falha total, preenchimento de
     `LLMResponse`. `sleep_fn`/`time_fn` SEMPRE injetados como fakes -- nenhum
     teste usa `time.sleep`/`time.time` reais (rodam em milissegundos).
  C. [Checkpoint 3.4] Instrumentação de uso/custo -- `LLMClient.generate()`
     grava um registro via `sigft.core.llm.usage.registrar()` nos MESMOS 2
     pontos de saída cobertos na seção B: 1 registro por `generate()` mesmo
     com retry; registro de falha após esgotar as retentativas; `tarefa`/
     `modulo` vindos de `tags`; custo REAL preservado quando o provider
     informa; e o teste mais importante da Decisão 1 do CP 3.4 -- falha ao
     GRAVAR o registro de uso não impede `generate()` de devolver a
     resposta normalmente. `tests/conftest.py` religa
     `SIGFT_DESABILITAR_USAGE=1` por padrão para TODA a suíte (protegendo
     as seções A/B acima, que nunca ouviram falar deste checkpoint); os
     testes da seção C reabilitam explicitamente (primeira linha do corpo
     do teste) e sempre redirecionam `sigft.config.ARQUIVO_USO_LLM` para
     dentro de `tmp_path` -- nunca escrevem no `logs/` real.

`get_llm()` (fábrica) é testada à parte, em `test_llm_get_llm_factory.py`.
`GeminiProvider` é testado à parte, em `test_llm_gemini_provider.py`.
"""
import json

import pytest

from sigft import config
from sigft.core.llm import usage
from sigft.core.llm.client import LLMClient, LLMResponse, ProviderResult, _limpar_e_parsear_json


# =============================================================================
# Helpers de teste (nenhum usa rede, tempo real, ou google.generativeai).
# =============================================================================
class _FakeProvider:
    """Provider FAKE injetável em `LLMClient` -- grava toda chamada recebida
    (`prompt`/`system`/`json_mode`) e devolve/levanta o próximo item de
    `respostas`, na ordem (uma entrada consumida por chamada). Uma entrada
    que seja uma instância de `BaseException` é LEVANTADA em vez de
    devolvida -- simula uma tentativa que falha (erro de rede/API real ou
    qualquer outra exceção)."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def generate_raw(self, prompt, *, system=None, json_mode=False):
        self.chamadas.append({"prompt": prompt, "system": system, "json_mode": json_mode})
        resultado = self.respostas.pop(0)
        if isinstance(resultado, BaseException):
            raise resultado
        # CP 3.2: contrato do provider generalizado para `ProviderResult`
        # (`NamedTuple` com `custo_usd` adicional, default `None`) -- as
        # tuplas de 3 elementos que os testes deste arquivo já usavam
        # continuam funcionando tal qual, sem precisar nomear `custo_usd`.
        return ProviderResult(*resultado)


class _Relogio:
    """Par `(time_fn, sleep_fn)` que anda em conjunto -- `sleep_fn` avança o
    relógio pelo tempo "dormido" (sem esperar de verdade), necessário para
    testar rate-limit (`min_interval_seconds`) de forma determinística e
    instantânea. `sonos` grava cada chamada de `sleep_fn`, na ordem."""

    def __init__(self, inicio: float = 0.0):
        self.agora = inicio
        self.sonos: list[float] = []

    def time_fn(self) -> float:
        return self.agora

    def sleep_fn(self, segundos: float) -> None:
        self.sonos.append(segundos)
        self.agora += segundos

    def avancar(self, segundos: float) -> None:
        """Avança o relógio SEM registrar como sono (simula tempo real
        decorrido entre chamadas de `generate()`, sem que o `LLMClient`
        tenha dormido para isso)."""
        self.agora += segundos


class _ErroCustomizado(Exception):
    """Exceção de teste distinta de `Exception`/`RuntimeError` -- usada para
    confirmar que `LLMClient.generate` propaga a exceção ORIGINAL (mesmo
    tipo/mensagem), não uma genérica."""


# =============================================================================
# A. _limpar_e_parsear_json
# =============================================================================
def test_objeto_com_fence_markdown_e_limpo_e_parseado():
    assert _limpar_e_parsear_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_objeto_sem_fence_e_parseado_direto():
    assert _limpar_e_parsear_json('{"a": 1}') == {"a": 1}


def test_lista_com_fence_markdown_e_limpa_e_parseada():
    assert _limpar_e_parsear_json('```json\n[1, 2, 3]\n```') == [1, 2, 3]


def test_lista_sem_fence_e_parseada_direto():
    assert _limpar_e_parsear_json("[1, 2, 3]") == [1, 2, 3]


def test_lista_de_objetos_com_fence_e_parseada_como_lista_nao_como_objeto():
    # Caso real de `tech_specs`: resposta é uma LISTA de objetos -- o
    # primeiro colchete "[" precisa vencer o primeiro "{" (que está DENTRO
    # da lista) na escolha de qual par de delimitadores usar.
    texto = '```json\n[{"CARACTERISTICA_CHAVE": "A"}, {"CARACTERISTICA_CHAVE": "B"}]\n```'
    assert _limpar_e_parsear_json(texto) == [
        {"CARACTERISTICA_CHAVE": "A"},
        {"CARACTERISTICA_CHAVE": "B"},
    ]


def test_objeto_com_prosa_antes_e_depois_e_recortado():
    texto = 'Aqui está o resultado: {"a": 1} -- espero que ajude!'
    assert _limpar_e_parsear_json(texto) == {"a": 1}


def test_lista_com_prosa_antes_e_depois_e_recortada():
    texto = "Segue a lista solicitada:\n[1, 2, 3]\nFim da resposta."
    assert _limpar_e_parsear_json(texto) == [1, 2, 3]


def test_texto_vazio_levanta_value_error():
    with pytest.raises(ValueError):
        _limpar_e_parsear_json("")


def test_texto_none_levanta_value_error():
    with pytest.raises(ValueError):
        _limpar_e_parsear_json(None)


def test_json_sem_chave_nem_colchete_propaga_json_decode_error():
    with pytest.raises(json.JSONDecodeError):
        _limpar_e_parsear_json("isso não é JSON nenhum")


def test_json_malformado_dentro_dos_colchetes_propaga_json_decode_error():
    with pytest.raises(json.JSONDecodeError):
        _limpar_e_parsear_json("[1, 2,")


# --- Robustez ESTRITAMENTE MAIOR que as 4 variantes divergentes de hoje ---
def test_mais_robusto_que_analyzer_tolera_prosa_ao_redor_do_objeto():
    # `analyzer_backend._call_gemini_api` (hoje) faz só replace+strip das
    # fences, SEM busca de colchete/chave -- QUEBRARIA com prosa ao redor
    # (json.loads receberia o texto inteiro, não só o objeto). A função
    # unificada tolera.
    texto = "Segundo minha análise, seguem os resultados:\n" '{"campos_fixos": {}}' "\nAtenciosamente."
    assert _limpar_e_parsear_json(texto) == {"campos_fixos": {}}


def test_mais_robusto_que_cria_fichas_objeto_com_texto_extra_apos_fence():
    # `cria_fichas_no_pmib_v1_backend.processar_lote` (hoje) só busca
    # `[`...`]`; se não achar, cai num fallback FRÁGIL (`clean[7:-3]`) que
    # assume que os 3 ÚLTIMOS caracteres do texto (já stripado) são a fence
    # de fechamento -- quebra se houver QUALQUER coisa depois da fence (ex.:
    # uma frase de encerramento da IA). A função unificada remove as fences
    # onde quer que apareçam (não só nas pontas) e recorta pelo delimitador
    # de JSON de verdade (aqui, um OBJETO -- o fallback antigo nem procurava
    # chave, só colchete).
    texto = '```json\n{"a": 1}\n```\nEspero que ajude!'
    assert _limpar_e_parsear_json(texto) == {"a": 1}


def test_mais_robusto_que_upload_conditions_tolera_lista_com_prosa():
    # `upload_conditions_backend._limpar_resposta_json` (hoje) só busca
    # `{`...`}` -- uma resposta em formato de LISTA com prosa ao redor
    # quebraria (nem acharia chave, nem removeria a prosa). A função
    # unificada cobre objeto E lista com a mesma lógica.
    texto = "Aqui está:\n```json\n[1, 2, 3]\n```\nObrigado."
    assert _limpar_e_parsear_json(texto) == [1, 2, 3]


def test_mais_robusto_que_upload_tech_specs_tolera_objeto_com_prosa():
    # `upload_tech_specs_backend._limpar_json_ia` (hoje) só busca `[`...`]`
    # -- uma resposta em formato de OBJETO com prosa ao redor quebraria. A
    # função unificada cobre objeto E lista com a mesma lógica.
    texto = "Segue o objeto:\n```json\n{\"x\": 10}\n```\nQualquer dúvida, avise."
    assert _limpar_e_parsear_json(texto) == {"x": 10}


# --- Leitura tolerante, so quando a estrita falha  [2026-10-19] ---
# Ideia do `_robust_json_parse` do RAG-Anything (HKUDS, MIT). Cada falha de
# parse aqui custa uma chamada inteira de novo (retry) ou devolve a ficha
# vazia. JSON truncado continua falhando: completar o que a IA nao mandou
# esconderia campos perdidos.

def test_bloco_de_raciocinio_think_antes_do_json_e_ignorado():
    texto = '<think>O formato pedido e {"campo": valor}... vou montar.</think>\n{"a": 1}'
    assert _limpar_e_parsear_json(texto) == {"a": 1}


@pytest.mark.parametrize("texto, esperado", [
    ('{"a": 1, "b": 2,}', {"a": 1, "b": 2}),
    ('[1, 2, ]', [1, 2]),
    ('{"a": [1, 2,], "b": {"c": 3,},}', {"a": [1, 2], "b": {"c": 3}}),
])
def test_virgula_sobrando_antes_de_fechar_e_tolerada(texto, esperado):
    assert _limpar_e_parsear_json(texto) == esperado


def test_virgula_com_fecha_chave_DENTRO_de_um_texto_nao_e_mexida():
    assert _limpar_e_parsear_json('{"nota": "lista: a, b,}", "x": 1,}') == {"nota": "lista: a, b,}", "x": 1}


def test_prosa_com_chaves_antes_do_json_acha_o_objeto_de_verdade():
    texto = 'Usei o formato {campo: valor} pedido. Resposta: {"a": "x {y}", "b": 2} Fim.'
    assert _limpar_e_parsear_json(texto) == {"a": "x {y}", "b": 2}


def test_json_valido_nao_passa_pelo_conserto():
    # Texto cujo conteudo tem ",}" -- a leitura estrita resolve, e o conserto
    # nunca roda (ele mexeria em nada aqui, mas a regra e: estrita primeiro).
    assert _limpar_e_parsear_json('{"a": "x,}"}') == {"a": "x,}"}


def test_json_truncado_continua_falhando_mesmo_com_o_conserto():
    with pytest.raises(json.JSONDecodeError):
        _limpar_e_parsear_json('{"a": 1, "b": [1, 2')


# =============================================================================
# B. LLMClient.generate — retry, rate-limit, sleep, propagação de exceção,
#    preenchimento de LLMResponse. Tudo com provider/sleep_fn/time_fn FAKES.
# =============================================================================
def test_sucesso_de_primeira_nao_dorme_nem_faz_retry():
    provider = _FakeProvider([('{"ok": true}', 3, 5)])
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="modelo-x",
        max_retries=2, retry_sleep_seconds=5,
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    resp = client.generate("prompt qualquer")

    assert isinstance(resp, LLMResponse)
    assert resp.text == '{"ok": true}'
    assert resp.parsed_json == {"ok": True}
    assert resp.tokens_in == 3
    assert resp.tokens_out == 5
    assert resp.custo_usd is None
    assert resp.model == "modelo-x"
    assert resp.provider == "gemini"
    assert resp.duracao_s == 0.0  # relógio fake não anda durante a tentativa
    assert len(provider.chamadas) == 1
    assert relogio.sonos == []  # nenhum sleep -- sucesso de primeira


def test_max_retries_2_tenta_ate_3_vezes_e_para_no_primeiro_sucesso():
    provider = _FakeProvider(
        [RuntimeError("falha 1"), RuntimeError("falha 2"), ('{"ok": 1}', None, None)]
    )
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="m",
        max_retries=2, retry_sleep_seconds=5,
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    resp = client.generate("prompt")

    assert resp.parsed_json == {"ok": 1}
    assert len(provider.chamadas) == 3  # 2 falhas + 1 sucesso = 3 tentativas TOTAIS
    # Dorme ENTRE tentativas que falharam (2x), nunca depois da última
    # tentativa (que teve sucesso, não haveria "próxima" mesmo).
    assert relogio.sonos == [5, 5]


def test_max_retries_2_falha_total_dorme_so_2x_nao_3x():
    # 3 tentativas TOTAIS (max_retries=2 => 2 retentativas), todas falham:
    # dorme só ENTRE tentativas (tentativa 1->2, tentativa 2->3) -- nunca
    # depois da 3ª (última) tentativa, que não tem para onde retentar.
    erro_final = RuntimeError("falha final")
    provider = _FakeProvider([RuntimeError("falha 1"), RuntimeError("falha 2"), erro_final])
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="m",
        max_retries=2, retry_sleep_seconds=7,
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    with pytest.raises(RuntimeError) as exc_info:
        client.generate("prompt")

    assert exc_info.value is erro_final  # a exceção ORIGINAL da ÚLTIMA tentativa
    assert len(provider.chamadas) == 3
    assert relogio.sonos == [7, 7]  # 2 sonos, não 3


def test_max_retries_0_faz_1_tentativa_e_propaga_sem_dormir():
    erro = _ErroCustomizado("sem chave configurada")
    provider = _FakeProvider([erro])
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="m",
        max_retries=0, retry_sleep_seconds=99,  # nunca deveria ser usado
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    with pytest.raises(_ErroCustomizado) as exc_info:
        client.generate("prompt")

    assert exc_info.value is erro
    assert len(provider.chamadas) == 1
    assert relogio.sonos == []  # nenhum sleep -- não há "próxima tentativa"


def test_falha_total_relevanta_a_excecao_original_nao_uma_generica():
    erro = _ErroCustomizado("mensagem bem específica")
    provider = _FakeProvider([erro, erro])
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="m",
        max_retries=1, retry_sleep_seconds=1,
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    with pytest.raises(_ErroCustomizado) as exc_info:
        client.generate("prompt")

    assert exc_info.value is erro
    assert str(exc_info.value) == "mensagem bem específica"


def test_resposta_que_nao_parseia_como_json_conta_como_falha_e_aciona_retry():
    # Uma resposta que `_limpar_e_parsear_json` não consegue parsear conta
    # como falha desta tentativa (mesmo caminho de exceção que um erro de
    # rede/API do provider) -- aciona retry da mesma forma.
    provider = _FakeProvider([("não é json", None, None), ('{"ok": true}', None, None)])
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="m",
        max_retries=1, retry_sleep_seconds=3,
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    resp = client.generate("prompt")

    assert resp.parsed_json == {"ok": True}
    assert len(provider.chamadas) == 2
    assert relogio.sonos == [3]


def test_retry_sleep_seconds_e_repassado_exatamente_para_sleep_fn():
    provider = _FakeProvider([RuntimeError("x"), ("[1]", None, None)])
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="m",
        max_retries=1, retry_sleep_seconds=12.5,
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    client.generate("prompt")

    assert relogio.sonos == [12.5]


def test_sem_rate_limit_por_padrao_chamadas_consecutivas_nao_dormem():
    provider = _FakeProvider([("[1]", None, None), ("[2]", None, None)])
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="m",
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )  # min_interval_seconds default = None

    client.generate("prompt 1")
    client.generate("prompt 2")

    assert relogio.sonos == []


def test_rate_limit_primeira_chamada_nunca_dorme():
    provider = _FakeProvider([("[1]", None, None)])
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="m",
        min_interval_seconds=60,
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    client.generate("prompt")

    assert relogio.sonos == []


def test_rate_limit_segunda_chamada_logo_em_seguida_dorme_o_restante_da_janela():
    provider = _FakeProvider([("[1]", None, None), ("[2]", None, None)])
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="m",
        min_interval_seconds=60,
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    client.generate("prompt 1")
    relogio.avancar(10)  # só 10s decorridos "de verdade" entre as chamadas
    client.generate("prompt 2")

    assert relogio.sonos == [50.0]  # 60 - 10 = 50s restantes


def test_rate_limit_chamada_apos_janela_cheia_nao_dorme():
    provider = _FakeProvider([("[1]", None, None), ("[2]", None, None)])
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="m",
        min_interval_seconds=60,
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    client.generate("prompt 1")
    relogio.avancar(60)  # janela cheia decorrida
    client.generate("prompt 2")

    assert relogio.sonos == []


def test_rate_limit_e_aplicado_1x_por_generate_nao_1x_por_tentativa_de_retry():
    # `_aplicar_rate_limit` roda uma vez ANTES do laço de retry -- as
    # tentativas internas (falha 1 -> retry -> sucesso) usam
    # `retry_sleep_seconds`, NÃO o rate-limit de novo.
    provider = _FakeProvider([RuntimeError("falha"), ("[1]", None, None)])
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="m",
        max_retries=1, retry_sleep_seconds=9,
        min_interval_seconds=60,
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    client.generate("prompt")  # 1ª chamada: sem rate-limit (1ª vez); 1 retry (9s)

    assert relogio.sonos == [9]  # só o sleep de retry, nenhum rate-limit extra


def test_system_e_json_mode_sao_repassados_ao_provider():
    provider = _FakeProvider([("{}", None, None)])
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="m",
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    client.generate("meu prompt", system="minha instrucao", json_mode=True)

    assert provider.chamadas == [
        {"prompt": "meu prompt", "system": "minha instrucao", "json_mode": True}
    ]


def test_system_none_e_json_mode_false_sao_o_default_repassado():
    provider = _FakeProvider([("{}", None, None)])
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="m",
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    client.generate("meu prompt")

    assert provider.chamadas == [{"prompt": "meu prompt", "system": None, "json_mode": False}]


def test_tags_e_aceito_mas_nao_afeta_o_resultado_ainda_sem_consumidor():
    provider = _FakeProvider([("{}", None, None)])
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="m",
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    resp_com_tags = client.generate("p", tags={"modulo": "x", "tarefa": "y"})

    assert resp_com_tags.parsed_json == {}


def test_tokens_none_quando_provider_nao_informa():
    provider = _FakeProvider([("[1]", None, None)])
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="m",
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    resp = client.generate("prompt")

    assert resp.tokens_in is None
    assert resp.tokens_out is None
    assert resp.custo_usd is None


# --- Propriedades read-only (inspeção de política resolvida) ---
def test_propriedades_read_only_refletem_o_construtor():
    provider = _FakeProvider([])
    client = LLMClient(
        provider, provider_name="gemini", model="gemini-3.5-flash",
        max_retries=2, retry_sleep_seconds=30, min_interval_seconds=None,
    )

    assert client.provider_name == "gemini"
    assert client.model == "gemini-3.5-flash"
    assert client.max_retries == 2
    assert client.retry_sleep_seconds == 30
    assert client.min_interval_seconds is None


# =============================================================================
# C. Instrumentação de uso/custo (Checkpoint 3.4) -- ver docstring do módulo.
# =============================================================================
def test_generate_sucesso_grava_exatamente_1_registro_de_uso(tmp_path, monkeypatch):
    monkeypatch.delenv(usage.ENV_DESABILITAR_USAGE, raising=False)
    caminho = tmp_path / "llm_usage.jsonl"
    monkeypatch.setattr(config, "ARQUIVO_USO_LLM", str(caminho))

    provider = _FakeProvider([('{"ok": true}', 10, 20)])
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="gemini-3-flash-preview",
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    client.generate("prompt", tags={"modulo": "upload_conditions_backend", "tarefa": "condicoes"})

    registros = usage.ler_registros(caminho=caminho)
    assert len(registros) == 1
    registro = registros[0]
    assert registro["provider"] == "gemini"
    assert registro["model"] == "gemini-3-flash-preview"
    assert registro["tarefa"] == "condicoes"
    assert registro["modulo"] == "upload_conditions_backend"
    assert registro["tokens_in"] == 10
    assert registro["tokens_out"] == 20
    assert registro["sucesso"] is True
    assert registro["erro"] is None
    assert registro["custo_estimado"] is True  # sem custo_usd do provider -> estimado pela tabela


def test_generate_com_retry_e_sucesso_na_ultima_tentativa_grava_1_registro_so(tmp_path, monkeypatch):
    monkeypatch.delenv(usage.ENV_DESABILITAR_USAGE, raising=False)
    caminho = tmp_path / "llm_usage.jsonl"
    monkeypatch.setattr(config, "ARQUIVO_USO_LLM", str(caminho))

    # Falha 2x, acerta na 3ª -- "UM registro por generate(), não por
    # tentativa de retry" (texto explícito do checkpoint).
    provider = _FakeProvider(
        [RuntimeError("falha 1"), RuntimeError("falha 2"), ('{"ok": 1}', 5, 5)]
    )
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="m",
        max_retries=2, retry_sleep_seconds=0,
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    client.generate("prompt")

    registros = usage.ler_registros(caminho=caminho)
    assert len(registros) == 1
    assert registros[0]["sucesso"] is True


def test_generate_falha_total_apos_retentativas_grava_1_registro_de_falha(tmp_path, monkeypatch):
    monkeypatch.delenv(usage.ENV_DESABILITAR_USAGE, raising=False)
    caminho = tmp_path / "llm_usage.jsonl"
    monkeypatch.setattr(config, "ARQUIVO_USO_LLM", str(caminho))

    erro = RuntimeError("indisponível")
    provider = _FakeProvider([erro, erro])
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="m",
        max_retries=1, retry_sleep_seconds=0,
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    with pytest.raises(RuntimeError):
        client.generate("prompt", tags={"tarefa": "tech_specs", "modulo": "upload_tech_specs_backend"})

    registros = usage.ler_registros(caminho=caminho)
    assert len(registros) == 1
    registro = registros[0]
    assert registro["sucesso"] is False
    assert registro["erro"] == "RuntimeError: indisponível"
    assert registro["tokens_in"] is None
    assert registro["tokens_out"] is None
    assert registro["custo_usd"] is None
    assert registro["custo_estimado"] is None
    assert registro["tarefa"] == "tech_specs"
    assert registro["modulo"] == "upload_tech_specs_backend"


def test_generate_sem_tags_usa_fallback_sem_tarefa_e_modulo_none(tmp_path, monkeypatch):
    monkeypatch.delenv(usage.ENV_DESABILITAR_USAGE, raising=False)
    caminho = tmp_path / "llm_usage.jsonl"
    monkeypatch.setattr(config, "ARQUIVO_USO_LLM", str(caminho))

    provider = _FakeProvider([("{}", None, None)])
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="m",
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    client.generate("prompt")  # sem tags=

    registro = usage.ler_registros(caminho=caminho)[0]
    assert registro["tarefa"] == "sem_tarefa"
    assert registro["modulo"] is None


def test_generate_preserva_custo_real_do_provider_sem_estimar(tmp_path, monkeypatch):
    monkeypatch.delenv(usage.ENV_DESABILITAR_USAGE, raising=False)
    caminho = tmp_path / "llm_usage.jsonl"
    monkeypatch.setattr(config, "ARQUIVO_USO_LLM", str(caminho))

    provider = _FakeProvider([('{"ok": true}', 100, 200, 0.0042)])
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="openrouter", model="x-ai/grok-4.5",
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    client.generate("prompt")

    registro = usage.ler_registros(caminho=caminho)[0]
    assert registro["custo_usd"] == 0.0042
    assert registro["custo_estimado"] is False


def test_generate_com_usage_desabilitado_nao_grava_nada(tmp_path, monkeypatch):
    monkeypatch.setenv(usage.ENV_DESABILITAR_USAGE, "1")
    caminho = tmp_path / "llm_usage.jsonl"
    monkeypatch.setattr(config, "ARQUIVO_USO_LLM", str(caminho))

    provider = _FakeProvider([("{}", None, None)])
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="m",
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    resp = client.generate("prompt")

    assert resp.parsed_json == {}  # generate() continua funcionando normalmente
    assert usage.ler_registros(caminho=caminho) == []


def test_generate_falha_ao_gravar_registro_de_uso_nao_impede_resposta_normal(tmp_path, monkeypatch):
    # O teste MAIS IMPORTANTE da extensão deste arquivo (Decisão 1 do
    # CP 3.4): mesmo se a ESCRITA do registro de uso falhar de VERDADE (aqui,
    # `ARQUIVO_USO_LLM` aponta para uma PASTA existente -- `open(pasta, "a")`
    # levanta `IsADirectoryError` de verdade) -- `usage.registrar()` engole
    # a exceção e `generate()` continua intocado: mesma resposta, sem
    # levantar nada por causa do rastreamento de uso.
    monkeypatch.delenv(usage.ENV_DESABILITAR_USAGE, raising=False)
    monkeypatch.setattr(config, "ARQUIVO_USO_LLM", str(tmp_path))  # pasta, não arquivo

    provider = _FakeProvider([('{"ok": true}', 1, 1)])
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="m",
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    resp = client.generate("prompt")  # não deve levantar por causa do usage

    assert isinstance(resp, LLMResponse)
    assert resp.parsed_json == {"ok": True}


def test_generate_falha_total_com_falha_ao_gravar_uso_ainda_relevanta_a_excecao_original(tmp_path, monkeypatch):
    # Mesma ideia do teste anterior, mas no caminho de FALHA TOTAL: a falha
    # de escrita do registro de uso não pode mascarar/trocar a exceção
    # ORIGINAL que `generate()` deveria relevantar.
    monkeypatch.delenv(usage.ENV_DESABILITAR_USAGE, raising=False)
    monkeypatch.setattr(config, "ARQUIVO_USO_LLM", str(tmp_path))  # pasta, não arquivo

    erro = RuntimeError("indisponível de verdade")
    provider = _FakeProvider([erro])
    relogio = _Relogio()
    client = LLMClient(
        provider, provider_name="gemini", model="m",
        max_retries=0,
        sleep_fn=relogio.sleep_fn, time_fn=relogio.time_fn,
    )

    with pytest.raises(RuntimeError) as exc_info:
        client.generate("prompt")

    assert exc_info.value is erro
