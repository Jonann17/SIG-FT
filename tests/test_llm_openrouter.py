r"""
Testes do Checkpoint 3.2 — `sigft/core/llm/providers/openrouter.py`
(`OpenRouterProvider` + `listar_modelos`).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.2. Nenhum teste
toca rede/tempo real: `http_post`/`http_get` são FAKES injetados,
`cache_path` usa `tmp_path`, e `time_fn` é um relógio FAKE (nunca
`time.time` real).
"""
import json

import pytest

from sigft import config
from sigft.core.llm.client import ProviderResult
from sigft.core.llm.providers.openrouter import OpenRouterProvider, listar_modelos


# =============================================================================
# Fakes de transporte HTTP (mesmo padrão de test_llm_openai_compat.py).
# =============================================================================
class _FakeResponse:
    def __init__(self, payload, status_ok=True):
        self._payload = payload
        self._status_ok = status_ok

    def raise_for_status(self):
        if not self._status_ok:
            raise RuntimeError("HTTP error simulado")

    def json(self):
        return self._payload


class _FakeHttpPost:
    def __init__(self, payload=None, status_ok=True):
        self.chamadas = []
        self._payload = payload if payload is not None else _payload_padrao()
        self._status_ok = status_ok

    def __call__(self, url, *, headers, json, timeout):
        self.chamadas.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return _FakeResponse(self._payload, status_ok=self._status_ok)


class _FakeHttpGet:
    def __init__(self, payload=None, status_ok=True, excecao=None):
        self.chamadas = []
        self._payload = payload if payload is not None else {"data": []}
        self._status_ok = status_ok
        self._excecao = excecao

    def __call__(self, url, *, headers, timeout):
        self.chamadas.append({"url": url, "headers": headers, "timeout": timeout})
        if self._excecao is not None:
            raise self._excecao
        return _FakeResponse(self._payload, status_ok=self._status_ok)


def _payload_padrao(texto="resposta da IA", usage=None):
    payload = {"choices": [{"message": {"content": texto}}]}
    if usage is not None:
        payload["usage"] = usage
    return payload


class _Relogio:
    def __init__(self, inicio=0.0):
        self.agora = inicio

    def time_fn(self):
        return self.agora

    def avancar(self, segundos):
        self.agora += segundos


# =============================================================================
# OpenRouterProvider -- tudo que a base faz + especializações.
# =============================================================================
def test_base_url_default_e_openrouter():
    http_post = _FakeHttpPost()
    provider = OpenRouterProvider("chave", "modelo-x", http_post=http_post)

    provider.generate_raw("prompt")

    assert http_post.chamadas[0]["url"] == f"{config.OPENROUTER_BASE_URL}/chat/completions"


def test_usage_include_true_no_corpo():
    http_post = _FakeHttpPost()
    provider = OpenRouterProvider("chave", "modelo-x", http_post=http_post)

    provider.generate_raw("prompt")

    assert http_post.chamadas[0]["json"]["usage"] == {"include": True}


def test_headers_de_atribuicao_presentes():
    http_post = _FakeHttpPost()
    provider = OpenRouterProvider("chave", "modelo-x", http_post=http_post)

    provider.generate_raw("prompt")

    headers = http_post.chamadas[0]["headers"]
    assert headers["HTTP-Referer"] == config.OPENROUTER_HEADERS_ATRIBUICAO["HTTP-Referer"]
    assert headers["X-Title"] == config.OPENROUTER_HEADERS_ATRIBUICAO["X-Title"]
    assert headers["Authorization"] == "Bearer chave"


def test_extra_headers_do_chamador_mesclam_com_atribuicao():
    http_post = _FakeHttpPost()
    provider = OpenRouterProvider(
        "chave", "modelo-x", extra_headers={"X-Custom": "abc"}, http_post=http_post
    )

    provider.generate_raw("prompt")

    headers = http_post.chamadas[0]["headers"]
    assert headers["X-Custom"] == "abc"
    assert headers["X-Title"] == "SIG-FT"


def test_usage_cost_vira_custo_usd():
    http_post = _FakeHttpPost(
        payload=_payload_padrao(
            "texto", usage={"prompt_tokens": 10, "completion_tokens": 20, "cost": 0.00123}
        )
    )
    provider = OpenRouterProvider("chave", "modelo-x", http_post=http_post)

    resultado = provider.generate_raw("prompt")

    assert isinstance(resultado, ProviderResult)
    assert resultado.custo_usd == 0.00123
    assert resultado.tokens_in == 10
    assert resultado.tokens_out == 20


def test_custo_usd_none_quando_cost_ausente():
    http_post = _FakeHttpPost(payload=_payload_padrao("texto", usage={"prompt_tokens": 10}))
    provider = OpenRouterProvider("chave", "modelo-x", http_post=http_post)

    resultado = provider.generate_raw("prompt")

    assert resultado.custo_usd is None


def test_temperature_e_json_mode_continuam_funcionando_na_especializacao():
    http_post = _FakeHttpPost()
    provider = OpenRouterProvider("chave", "modelo-x", temperature=0.3, http_post=http_post)

    provider.generate_raw("prompt", json_mode=True)

    corpo = http_post.chamadas[0]["json"]
    assert corpo["temperature"] == 0.3
    assert corpo["response_format"] == {"type": "json_object"}


def test_base_url_customizado_sobrescreve_o_default():
    http_post = _FakeHttpPost()
    provider = OpenRouterProvider(
        "chave", "modelo-x", base_url="https://outro-gateway.com/v1", http_post=http_post
    )

    provider.generate_raw("prompt")

    assert http_post.chamadas[0]["url"] == "https://outro-gateway.com/v1/chat/completions"


# =============================================================================
# listar_modelos -- catálogo com cache local.
# =============================================================================
def test_cache_miss_faz_get_grava_cache_e_devolve(tmp_path):
    cache_path = tmp_path / "cache.json"
    http_get = _FakeHttpGet(payload={"data": [{"id": "modelo-a"}, {"id": "modelo-b"}]})
    relogio = _Relogio(inicio=1000.0)

    modelos = listar_modelos(
        "chave", cache_path=cache_path, http_get=http_get, time_fn=relogio.time_fn
    )

    assert modelos == [{"id": "modelo-a"}, {"id": "modelo-b"}]
    assert len(http_get.chamadas) == 1
    assert cache_path.exists()
    gravado = json.loads(cache_path.read_text(encoding="utf-8"))
    assert gravado["timestamp"] == 1000.0
    assert gravado["modelos"] == modelos


def test_cache_fresco_dentro_do_ttl_nao_chama_rede(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(
        json.dumps({"timestamp": 1000.0, "modelos": [{"id": "modelo-cache"}]}), encoding="utf-8"
    )
    http_get = _FakeHttpGet()
    relogio = _Relogio(inicio=1000.0 + 3600)  # 1h depois, TTL default = 1 dia

    modelos = listar_modelos(
        "chave", cache_path=cache_path, http_get=http_get, time_fn=relogio.time_fn
    )

    assert modelos == [{"id": "modelo-cache"}]
    assert http_get.chamadas == []


def test_cache_expirado_chama_a_rede(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(
        json.dumps({"timestamp": 1000.0, "modelos": [{"id": "modelo-velho"}]}), encoding="utf-8"
    )
    http_get = _FakeHttpGet(payload={"data": [{"id": "modelo-novo"}]})
    relogio = _Relogio(inicio=1000.0 + 999999)  # muito além do TTL default

    modelos = listar_modelos(
        "chave", cache_path=cache_path, http_get=http_get, time_fn=relogio.time_fn
    )

    assert modelos == [{"id": "modelo-novo"}]
    assert len(http_get.chamadas) == 1


def test_ttl_customizado_e_respeitado(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(
        json.dumps({"timestamp": 1000.0, "modelos": [{"id": "modelo-cache"}]}), encoding="utf-8"
    )
    http_get = _FakeHttpGet(payload={"data": [{"id": "modelo-novo"}]})
    relogio = _Relogio(inicio=1000.0 + 100)

    modelos = listar_modelos(
        "chave", cache_path=cache_path, http_get=http_get, time_fn=relogio.time_fn, ttl_segundos=50
    )

    assert modelos == [{"id": "modelo-novo"}]
    assert len(http_get.chamadas) == 1


def test_erro_de_rede_com_cache_valido_devolve_o_cache_sem_levantar(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(
        json.dumps({"timestamp": 1000.0, "modelos": [{"id": "modelo-cache"}]}), encoding="utf-8"
    )
    http_get = _FakeHttpGet(excecao=ConnectionError("rede fora do ar"))
    relogio = _Relogio(inicio=1000.0 + 999999)  # cache expirado, mas ainda existe

    modelos = listar_modelos(
        "chave", cache_path=cache_path, http_get=http_get, time_fn=relogio.time_fn
    )

    assert modelos == [{"id": "modelo-cache"}]


def test_erro_de_rede_sem_cache_nenhum_levanta(tmp_path):
    cache_path = tmp_path / "cache.json"  # nunca criado
    erro = ConnectionError("rede fora do ar")
    http_get = _FakeHttpGet(excecao=erro)
    relogio = _Relogio()

    with pytest.raises(ConnectionError) as exc_info:
        listar_modelos("chave", cache_path=cache_path, http_get=http_get, time_fn=relogio.time_fn)
    assert exc_info.value is erro


def test_erro_http_com_cache_valido_tambem_degrada_graciosamente(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(
        json.dumps({"timestamp": 1000.0, "modelos": [{"id": "modelo-cache"}]}), encoding="utf-8"
    )
    http_get = _FakeHttpGet(status_ok=False)  # raise_for_status levanta
    relogio = _Relogio(inicio=1000.0 + 999999)

    modelos = listar_modelos(
        "chave", cache_path=cache_path, http_get=http_get, time_fn=relogio.time_fn
    )

    assert modelos == [{"id": "modelo-cache"}]


def test_cache_corrompido_e_tratado_como_ausente_e_busca_na_rede(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text("isto não é json valido{{{", encoding="utf-8")
    http_get = _FakeHttpGet(payload={"data": [{"id": "modelo-novo"}]})
    relogio = _Relogio()

    modelos = listar_modelos(
        "chave", cache_path=cache_path, http_get=http_get, time_fn=relogio.time_fn
    )

    assert modelos == [{"id": "modelo-novo"}]


def test_falha_ao_gravar_o_cache_nao_descarta_a_lista_que_chegou(tmp_path):
    """Cache é conveniência: não conseguir gravá-lo não apaga o que a rede trouxe.

    Foi o que escondeu o catálogo do OpenRouter no app instalado (2026-09-25):
    a lista chegava, a gravação do cache levantava, e a lista ia junto com a
    exceção. Ver `test_pasta_do_programa_somente_leitura.py`, seção E.
    """
    cache_path = tmp_path / "cache.json"
    # Uma PASTA com o nome do arquivo faz o `open(..., "w")` levantar -- chmod
    # não serve, a suíte roda como root no CI.
    cache_path.mkdir()
    http_get = _FakeHttpGet(payload={"data": [{"id": "modelo-novo"}]})

    modelos = listar_modelos(
        "chave", cache_path=cache_path, http_get=http_get, time_fn=_Relogio().time_fn
    )

    assert modelos == [{"id": "modelo-novo"}]
