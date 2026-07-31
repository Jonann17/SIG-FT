r"""
Testes do Checkpoint 3.2 — `sigft/core/llm/providers/openai_compat.py`
(`OpenAICompatProvider`).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.2. `http_post` é
sempre um FAKE injetado -- nenhum teste toca rede nem depende do pacote
`requests` estar instalado (ver decisão de usar `requests` em vez do pacote
`openai`, registrada em docs/refatoracao/PENDENCIAS.md).
"""
import pytest

from sigft.core.llm.client import ProviderResult
from sigft.core.llm.providers.openai_compat import OpenAICompatProvider


# =============================================================================
# Fake de transporte HTTP -- grava toda chamada recebida
# (url/headers/json/timeout) e devolve/levanta o que o teste configurar.
# =============================================================================
class _FakeResponse:
    def __init__(self, payload, status_ok=True):
        self._payload = payload
        self._status_ok = status_ok
        self.raise_for_status_chamado = False

    def raise_for_status(self):
        self.raise_for_status_chamado = True
        if not self._status_ok:
            raise RuntimeError("HTTP error simulado")

    def json(self):
        return self._payload


class _FakeHttpPost:
    def __init__(self, payload=None, status_ok=True, excecao=None):
        self.chamadas = []
        self._payload = payload if payload is not None else _payload_padrao()
        self._status_ok = status_ok
        self._excecao = excecao

    def __call__(self, url, *, headers, json, timeout):
        self.chamadas.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if self._excecao is not None:
            raise self._excecao
        return _FakeResponse(self._payload, status_ok=self._status_ok)


def _payload_padrao(texto="resposta da IA", usage=None):
    payload = {"choices": [{"message": {"content": texto}}]}
    if usage is not None:
        payload["usage"] = usage
    return payload


# =============================================================================
# URL montada -- base_url com e sem "/" final.
# =============================================================================
def test_url_montada_sem_barra_final_no_base_url():
    http_post = _FakeHttpPost()
    provider = OpenAICompatProvider(
        "chave", "modelo-x", base_url="https://exemplo.com/v1", http_post=http_post
    )

    provider.generate_raw("prompt")

    assert http_post.chamadas[0]["url"] == "https://exemplo.com/v1/chat/completions"


def test_url_montada_com_barra_final_no_base_url_nao_duplica_barra():
    http_post = _FakeHttpPost()
    provider = OpenAICompatProvider(
        "chave", "modelo-x", base_url="https://exemplo.com/v1/", http_post=http_post
    )

    provider.generate_raw("prompt")

    assert http_post.chamadas[0]["url"] == "https://exemplo.com/v1/chat/completions"


# =============================================================================
# Header Authorization: Bearer ...
# =============================================================================
def test_header_authorization_bearer():
    http_post = _FakeHttpPost()
    provider = OpenAICompatProvider(
        "minha-chave", "modelo-x", base_url="https://exemplo.com", http_post=http_post
    )

    provider.generate_raw("prompt")

    assert http_post.chamadas[0]["headers"]["Authorization"] == "Bearer minha-chave"
    assert http_post.chamadas[0]["headers"]["Content-Type"] == "application/json"


def test_extra_headers_mesclados():
    http_post = _FakeHttpPost()
    provider = OpenAICompatProvider(
        "chave",
        "modelo-x",
        base_url="https://exemplo.com",
        extra_headers={"X-Custom": "valor"},
        http_post=http_post,
    )

    provider.generate_raw("prompt")

    headers = http_post.chamadas[0]["headers"]
    assert headers["X-Custom"] == "valor"
    assert headers["Authorization"] == "Bearer chave"
    assert headers["Content-Type"] == "application/json"


# =============================================================================
# messages com e sem system.
# =============================================================================
def test_messages_sem_system():
    http_post = _FakeHttpPost()
    provider = OpenAICompatProvider("chave", "modelo-x", base_url="https://exemplo.com", http_post=http_post)

    provider.generate_raw("meu prompt", system=None)

    assert http_post.chamadas[0]["json"]["messages"] == [{"role": "user", "content": "meu prompt"}]


def test_messages_com_system():
    http_post = _FakeHttpPost()
    provider = OpenAICompatProvider("chave", "modelo-x", base_url="https://exemplo.com", http_post=http_post)

    provider.generate_raw("meu prompt", system="instrucao do sistema")

    assert http_post.chamadas[0]["json"]["messages"] == [
        {"role": "system", "content": "instrucao do sistema"},
        {"role": "user", "content": "meu prompt"},
    ]


# =============================================================================
# response_format -- só com json_mode=True.
# =============================================================================
def test_response_format_ausente_sem_json_mode():
    http_post = _FakeHttpPost()
    provider = OpenAICompatProvider("chave", "modelo-x", base_url="https://exemplo.com", http_post=http_post)

    provider.generate_raw("prompt", json_mode=False)

    assert "response_format" not in http_post.chamadas[0]["json"]


def test_response_format_presente_com_json_mode():
    http_post = _FakeHttpPost()
    provider = OpenAICompatProvider("chave", "modelo-x", base_url="https://exemplo.com", http_post=http_post)

    provider.generate_raw("prompt", json_mode=True)

    assert http_post.chamadas[0]["json"]["response_format"] == {"type": "json_object"}


# =============================================================================
# temperature -- só quando não None.
# =============================================================================
def test_temperature_ausente_quando_none():
    http_post = _FakeHttpPost()
    provider = OpenAICompatProvider(
        "chave", "modelo-x", base_url="https://exemplo.com", temperature=None, http_post=http_post
    )

    provider.generate_raw("prompt")

    assert "temperature" not in http_post.chamadas[0]["json"]


def test_temperature_presente_quando_definida():
    http_post = _FakeHttpPost()
    provider = OpenAICompatProvider(
        "chave", "modelo-x", base_url="https://exemplo.com", temperature=0.1, http_post=http_post
    )

    provider.generate_raw("prompt")

    assert http_post.chamadas[0]["json"]["temperature"] == 0.1


def test_model_repassado_no_corpo():
    http_post = _FakeHttpPost()
    provider = OpenAICompatProvider(
        "chave", "gpt-modelo-x", base_url="https://exemplo.com", http_post=http_post
    )

    provider.generate_raw("prompt")

    assert http_post.chamadas[0]["json"]["model"] == "gpt-modelo-x"


# =============================================================================
# Extração de texto e tokens.
# =============================================================================
def test_extracao_de_texto_e_tokens():
    http_post = _FakeHttpPost(
        payload=_payload_padrao("texto de resposta", usage={"prompt_tokens": 10, "completion_tokens": 20})
    )
    provider = OpenAICompatProvider("chave", "modelo-x", base_url="https://exemplo.com", http_post=http_post)

    resultado = provider.generate_raw("prompt")

    assert isinstance(resultado, ProviderResult)
    assert resultado.text == "texto de resposta"
    assert resultado.tokens_in == 10
    assert resultado.tokens_out == 20


def test_tokens_none_quando_usage_ausente():
    http_post = _FakeHttpPost(payload=_payload_padrao("texto"))
    provider = OpenAICompatProvider("chave", "modelo-x", base_url="https://exemplo.com", http_post=http_post)

    resultado = provider.generate_raw("prompt")

    assert resultado.tokens_in is None
    assert resultado.tokens_out is None


def test_tokens_none_quando_usage_incompleto():
    http_post = _FakeHttpPost(payload=_payload_padrao("texto", usage={"prompt_tokens": 5}))
    provider = OpenAICompatProvider("chave", "modelo-x", base_url="https://exemplo.com", http_post=http_post)

    resultado = provider.generate_raw("prompt")

    assert resultado.tokens_in == 5
    assert resultado.tokens_out is None


# =============================================================================
# custo_usd -- SEMPRE None na classe base.
# =============================================================================
def test_custo_usd_sempre_none_na_classe_base():
    http_post = _FakeHttpPost(
        payload=_payload_padrao("texto", usage={"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.001})
    )
    provider = OpenAICompatProvider("chave", "modelo-x", base_url="https://exemplo.com", http_post=http_post)

    resultado = provider.generate_raw("prompt")

    assert resultado.custo_usd is None


# =============================================================================
# raise_for_status levantando -- propaga (LLMClient é quem retenta).
# =============================================================================
def test_raise_for_status_propaga_a_excecao():
    http_post = _FakeHttpPost(status_ok=False)
    provider = OpenAICompatProvider("chave", "modelo-x", base_url="https://exemplo.com", http_post=http_post)

    with pytest.raises(RuntimeError, match="HTTP error simulado"):
        provider.generate_raw("prompt")


def test_excecao_de_transporte_propaga():
    erro = ConnectionError("rede fora do ar")
    http_post = _FakeHttpPost(excecao=erro)
    provider = OpenAICompatProvider("chave", "modelo-x", base_url="https://exemplo.com", http_post=http_post)

    with pytest.raises(ConnectionError) as exc_info:
        provider.generate_raw("prompt")
    assert exc_info.value is erro


# =============================================================================
# timeout repassado.
# =============================================================================
def test_timeout_repassado_ao_http_post():
    http_post = _FakeHttpPost()
    provider = OpenAICompatProvider(
        "chave", "modelo-x", base_url="https://exemplo.com", timeout=42, http_post=http_post
    )

    provider.generate_raw("prompt")

    assert http_post.chamadas[0]["timeout"] == 42
