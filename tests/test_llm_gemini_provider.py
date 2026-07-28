r"""
Testes do Checkpoint 3.1 — `sigft/core/llm/providers/gemini.py`
(`GeminiProvider`).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.1. `GeminiProvider`
é a ÚNICA classe do projeto que importa `google.generativeai` — aqui ela é
testada com um `genai_module` FAKE injetado (nunca o SDK real, nunca rede),
mesmo padrão de injeção já usado para `driver`/`wait` em `SeleniumEngine`.

Cobertura:
  - `system=None` NÃO passa `system_instruction`; `system="X"` passa.
  - `json_mode=False` NÃO passa `generation_config`; `json_mode=True` passa
    `{"response_mime_type": "application/json"}`.
  - `safety_settings` SEMPRE presente e igual ao dict BLOCK_NONE (decisão do
    CP 3.1 — ver docs/refatoracao/PENDENCIAS.md).
  - `api_key` vazio/`None` NÃO chama `.configure(...)` (mesmo guard de hoje).
  - Extração de `tokens_in`/`tokens_out` quando `usage_metadata` existe e
    quando não existe (fallback `None`).
"""
from sigft.core.llm.providers.gemini import SAFETY_SETTINGS_BLOCK_NONE, GeminiProvider


# =============================================================================
# Fakes -- substituem google.generativeai por completo, sem SDK real/rede.
# =============================================================================
class _FakeUsageMetadata:
    def __init__(self, prompt_token_count, candidates_token_count):
        self.prompt_token_count = prompt_token_count
        self.candidates_token_count = candidates_token_count


class _FakeGenerateContentResponse:
    def __init__(self, texto, usage_metadata=None):
        self.text = texto
        if usage_metadata is not None:
            self.usage_metadata = usage_metadata
        # Se `usage_metadata` for `None`, o atributo NEM é definido -- simula
        # um SDK que não expõe `usage_metadata` (getattr com default `None`
        # em `generate_raw` precisa cobrir esse caso).


class _FakeGenerativeModel:
    def __init__(self, resposta_texto, usage_metadata):
        self._resposta_texto = resposta_texto
        self._usage_metadata = usage_metadata
        self.generate_content_chamadas = []

    def generate_content(self, prompt):
        self.generate_content_chamadas.append(prompt)
        return _FakeGenerateContentResponse(self._resposta_texto, self._usage_metadata)


class _FakeGenaiModule:
    """Substitui `google.generativeai` -- grava toda chamada de
    `.configure(...)`/`.GenerativeModel(...)` para inspeção nos testes."""

    def __init__(self, resposta_texto='{"ok": true}', usage_metadata=None):
        self.configure_chamadas = []
        self.generative_model_chamadas = []
        self.modelos_criados: list[_FakeGenerativeModel] = []
        self._resposta_texto = resposta_texto
        self._usage_metadata = usage_metadata

    def configure(self, **kwargs):
        self.configure_chamadas.append(kwargs)

    def GenerativeModel(self, model, **kwargs):
        chamada = {"model": model}
        chamada.update(kwargs)
        self.generative_model_chamadas.append(chamada)
        modelo = _FakeGenerativeModel(self._resposta_texto, self._usage_metadata)
        self.modelos_criados.append(modelo)
        return modelo


# =============================================================================
# api_key / configure()
# =============================================================================
def test_api_key_truthy_chama_configure_com_transport_rest():
    fake = _FakeGenaiModule()
    GeminiProvider("minha-chave", "gemini-3.5-flash", genai_module=fake)

    assert fake.configure_chamadas == [{"api_key": "minha-chave", "transport": "rest"}]


def test_api_key_vazio_nao_chama_configure():
    fake = _FakeGenaiModule()
    GeminiProvider("", "gemini-3.5-flash", genai_module=fake)

    assert fake.configure_chamadas == []


def test_api_key_none_nao_chama_configure():
    fake = _FakeGenaiModule()
    GeminiProvider(None, "gemini-3.5-flash", genai_module=fake)

    assert fake.configure_chamadas == []


# =============================================================================
# system_instruction
# =============================================================================
def test_system_none_nao_passa_system_instruction():
    fake = _FakeGenaiModule()
    provider = GeminiProvider("chave", "modelo-x", genai_module=fake)

    provider.generate_raw("prompt", system=None)

    assert "system_instruction" not in fake.generative_model_chamadas[0]


def test_system_definido_passa_system_instruction():
    fake = _FakeGenaiModule()
    provider = GeminiProvider("chave", "modelo-x", genai_module=fake)

    provider.generate_raw("prompt", system="Você é um assistente.")

    assert fake.generative_model_chamadas[0]["system_instruction"] == "Você é um assistente."


# =============================================================================
# json_mode / generation_config
# =============================================================================
def test_json_mode_false_nao_passa_generation_config():
    fake = _FakeGenaiModule()
    provider = GeminiProvider("chave", "modelo-x", genai_module=fake)

    provider.generate_raw("prompt", json_mode=False)

    assert "generation_config" not in fake.generative_model_chamadas[0]


def test_json_mode_true_passa_generation_config_response_mime_type_json():
    fake = _FakeGenaiModule()
    provider = GeminiProvider("chave", "modelo-x", genai_module=fake)

    provider.generate_raw("prompt", json_mode=True)

    assert fake.generative_model_chamadas[0]["generation_config"] == {
        "response_mime_type": "application/json"
    }


# =============================================================================
# safety_settings -- SEMPRE presente, igual ao dict BLOCK_NONE, em qualquer
# combinação de system/json_mode.
# =============================================================================
def test_safety_settings_sempre_presente_sem_system_sem_json_mode():
    fake = _FakeGenaiModule()
    provider = GeminiProvider("chave", "modelo-x", genai_module=fake)

    provider.generate_raw("prompt")

    assert fake.generative_model_chamadas[0]["safety_settings"] == SAFETY_SETTINGS_BLOCK_NONE


def test_safety_settings_sempre_presente_com_system_e_json_mode():
    fake = _FakeGenaiModule()
    provider = GeminiProvider("chave", "modelo-x", genai_module=fake)

    provider.generate_raw("prompt", system="instrucao", json_mode=True)

    assert fake.generative_model_chamadas[0]["safety_settings"] == SAFETY_SETTINGS_BLOCK_NONE


def test_safety_settings_bloqueia_nenhuma_categoria():
    assert SAFETY_SETTINGS_BLOCK_NONE == {
        "HATE_SPEECH": "BLOCK_NONE",
        "HARASSMENT": "BLOCK_NONE",
        "SEXUALLY_EXPLICIT": "BLOCK_NONE",
        "DANGEROUS": "BLOCK_NONE",
    }


# =============================================================================
# Repasse de model/prompt + retorno (texto, tokens_in, tokens_out)
# =============================================================================
def test_model_e_prompt_repassados_corretamente():
    fake = _FakeGenaiModule(resposta_texto="resposta qualquer")
    provider = GeminiProvider("chave", "gemini-3.1-pro-preview", genai_module=fake)

    provider.generate_raw("meu prompt aqui")

    assert fake.generative_model_chamadas[0]["model"] == "gemini-3.1-pro-preview"
    assert len(fake.modelos_criados) == 1  # 1 GenerativeModel NOVO por chamada
    # O prompt chegou ao `.generate_content(...)` do modelo criado por ESTA chamada:
    assert fake.modelos_criados[0].generate_content_chamadas == ["meu prompt aqui"]


def test_generate_raw_devolve_texto_da_resposta():
    fake = _FakeGenaiModule(resposta_texto="texto da resposta")
    provider = GeminiProvider("chave", "modelo-x", genai_module=fake)

    texto, _, _ = provider.generate_raw("prompt")

    assert texto == "texto da resposta"


# =============================================================================
# tokens_in / tokens_out
# =============================================================================
def test_extracao_de_tokens_quando_usage_metadata_existe():
    fake = _FakeGenaiModule(
        resposta_texto="{}",
        usage_metadata=_FakeUsageMetadata(prompt_token_count=42, candidates_token_count=7),
    )
    provider = GeminiProvider("chave", "modelo-x", genai_module=fake)

    texto, tokens_in, tokens_out = provider.generate_raw("prompt")

    assert texto == "{}"
    assert tokens_in == 42
    assert tokens_out == 7


def test_extracao_de_tokens_none_quando_usage_metadata_ausente():
    fake = _FakeGenaiModule(resposta_texto="{}", usage_metadata=None)
    provider = GeminiProvider("chave", "modelo-x", genai_module=fake)

    _, tokens_in, tokens_out = provider.generate_raw("prompt")

    assert tokens_in is None
    assert tokens_out is None
