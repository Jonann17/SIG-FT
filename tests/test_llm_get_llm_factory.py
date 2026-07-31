r"""
Testes do Checkpoint 3.1 — `sigft.core.llm.client.get_llm()` (fábrica).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.1. Cobre
especificamente a DECISÃO deste checkpoint (registrada em
docs/refatoracao/PENDENCIAS.md): `get_llm(tarefa, api_key)` resolve o modelo
via `config.LLM_MODELOS_HOJE` — NÃO via `config.LLM_TASKS` (que contém os
modelos DECIDIDOS/alvo, reservados para o CP 3.3) — e a política de
retry/rate-limit resultante bate com a tabela do checkpoint (`max_retries`,
`retry_sleep_seconds`, `min_interval_seconds` por tarefa).
"""
import pytest

from sigft import config
from sigft.core.llm.client import LLMClient, get_llm
from sigft.core.llm.providers.gemini import GeminiProvider


# =============================================================================
# Resolução de modelo/provider -- via LLM_MODELOS_HOJE, NÃO via LLM_TASKS.
# =============================================================================
@pytest.mark.parametrize(
    "tarefa,provider_esperado,modelo_esperado",
    [
        # Valores == config.LLM_MODELOS_HOJE (baseline de equivalência do
        # CP 3.1 -- ver test_config.py:test_llm_modelos_hoje_preserva_os_...).
        ("categorizar_pdm", "gemini", "gemini-3.1-pro-preview"),
        ("validar_ficha", "gemini", "gemini-3.1-pro-preview"),
        ("condicoes", "gemini", "gemini-3.5-flash"),
        ("tech_specs", "gemini", "gemini-3.5-flash"),
        ("autospec", "gemini", "gemini-3.1-pro-preview"),
    ],
)
def test_get_llm_resolve_modelo_das_5_tarefas_via_llm_modelos_hoje(
    tarefa, provider_esperado, modelo_esperado
):
    llm = get_llm(tarefa, None)

    assert isinstance(llm, LLMClient)
    assert llm.provider_name == provider_esperado
    assert llm.model == modelo_esperado
    # Prova DECISIVA de que a fonte é LLM_MODELOS_HOJE, não LLM_TASKS: os 2
    # dicts concordam em provider/model para estas 5 tarefas (ver
    # `config.py`), então também confirmamos aqui que bate com
    # LLM_MODELOS_HOJE literalmente (não é coincidência de valor igual).
    assert llm.model == config.LLM_MODELOS_HOJE[tarefa]["model"]
    assert llm.provider_name == config.LLM_MODELOS_HOJE[tarefa]["provider"]


def test_get_llm_categorizar_pdm_nao_usa_llm_tasks_grok(monkeypatch):
    # `config.LLM_TASKS["categorizar_pdm"]` aponta para provider "xai"
    # (Grok 4.5) -- NÃO implementado neste checkpoint. Se `get_llm` lesse
    # `LLM_TASKS` em vez de `LLM_MODELOS_HOJE`, esta chamada levantaria
    # `NotImplementedError` (só PROVIDER_GEMINI está implementado no CP
    # 3.1). O fato de ter SUCESSO, com o modelo Gemini de hoje, é a prova
    # decisiva de que a fonte é `LLM_MODELOS_HOJE`.
    assert config.LLM_TASKS["categorizar_pdm"]["provider"] == "xai"  # pré-condição do teste

    llm = get_llm("categorizar_pdm", None)

    assert llm.provider_name == "gemini"
    assert llm.model == "gemini-3.1-pro-preview"


def test_get_llm_le_llm_modelos_hoje_ao_vivo_nao_llm_tasks(monkeypatch):
    # Monkeypatch de UM valor dentro de LLM_MODELOS_HOJE (restaurado
    # automaticamente ao fim do teste) -- confirma que `get_llm` lê o dict
    # DE VERDADE (não uma cópia congelada em import-time), e que o valor
    # (propositalmente diferente do que está em LLM_TASKS) se reflete no
    # `LLMClient` resolvido.
    monkeypatch.setitem(config.LLM_MODELOS_HOJE["condicoes"], "model", "modelo-fake-de-teste")

    llm = get_llm("condicoes", None)

    assert llm.model == "modelo-fake-de-teste"
    assert config.LLM_TASKS["condicoes"]["model"] != "modelo-fake-de-teste"  # LLM_TASKS intocado


def test_get_llm_provider_resolvido_e_uma_instancia_de_geminiprovider():
    llm = get_llm("condicoes", None)

    # Acesso ao atributo "privado" só para confirmar QUAL classe de
    # provider foi instanciada por dentro de get_llm() -- não faz parte do
    # contrato público de LLMClient, só uma checagem de integração.
    assert isinstance(llm._provider, GeminiProvider)  # noqa: SLF001


# =============================================================================
# Tarefa desconhecida -- ValueError claro.
# =============================================================================
def test_get_llm_tarefa_desconhecida_levanta_value_error_claro():
    with pytest.raises(ValueError, match="tarefa_que_nao_existe"):
        get_llm("tarefa_que_nao_existe", None)


def test_get_llm_erro_lista_as_tarefas_validas_de_llm_modelos_hoje():
    with pytest.raises(ValueError) as exc_info:
        get_llm("bogus", None)

    mensagem = str(exc_info.value)
    for tarefa in config.LLM_MODELOS_HOJE:
        assert tarefa in mensagem


# =============================================================================
# Política de retry/rate-limit por tarefa (tabela do checkpoint).
# =============================================================================
@pytest.mark.parametrize(
    "tarefa,max_retries,retry_sleep_seconds,min_interval_seconds",
    [
        ("categorizar_pdm", 0, 0, None),
        ("validar_ficha", 2, 5, 60),
        ("condicoes", 2, 30, None),
        ("tech_specs", 2, 2, None),
        ("autospec", 2, 5, 60),
    ],
)
def test_get_llm_politica_de_retry_por_tarefa(
    tarefa, max_retries, retry_sleep_seconds, min_interval_seconds
):
    llm = get_llm(tarefa, None)

    assert llm.max_retries == max_retries
    assert llm.retry_sleep_seconds == retry_sleep_seconds
    assert llm.min_interval_seconds == min_interval_seconds


def test_get_llm_todas_as_tarefas_de_llm_modelos_hoje_tem_politica_definida():
    # Invariante: nenhuma tarefa de LLM_MODELOS_HOJE pode ficar sem política
    # de retry (get_llm quebraria com KeyError ao tentar resolver).
    for tarefa in config.LLM_MODELOS_HOJE:
        get_llm(tarefa, None)  # não deve levantar


def test_get_llm_api_key_e_repassada_tal_qual_sem_ler_outra_fonte(monkeypatch):
    # get_llm NÃO lê nenhuma fonte de chave por conta própria -- só repassa
    # o `api_key` recebido para o provider. Confirmamos indiretamente: uma
    # `api_key` vazia/None não deveria configurar o SDK (comportamento já
    # coberto por test_llm_gemini_provider.py); aqui só garantimos que
    # `get_llm(tarefa, api_key=None)` não levanta por causa da ausência de
    # chave (a validação de "API key ausente" é responsabilidade dos
    # CONSUMIDORES, não de get_llm/LLMClient/GeminiProvider).
    llm = get_llm("condicoes", None)
    assert isinstance(llm, LLMClient)

    llm2 = get_llm("condicoes", "uma-chave-qualquer")
    assert isinstance(llm2, LLMClient)


# =============================================================================
# CP 3.2 — roteamento de 3 providers, resolução de chave por provider,
# `EMPRESA_LLM_BASE_URL` ausente e `NotImplementedError` de provider
# desconhecido (ex.: "xai", que `config.LLM_TASKS` ainda usa).
# =============================================================================
from sigft.core.llm.providers.openai_compat import OpenAICompatProvider
from sigft.core.llm.providers.openrouter import OpenRouterProvider


def _fixar_tarefa_bogus(monkeypatch, provider, model="modelo-de-teste"):
    """Monkeypatch de uma tarefa NOVA em `LLM_MODELOS_HOJE` (restaurado
    automaticamente ao fim do teste) -- evita tocar nas 5 tarefas reais."""
    monkeypatch.setitem(config.LLM_MODELOS_HOJE, "_bogus", {"provider": provider, "model": model})
    monkeypatch.setitem(
        __import__("sigft.core.llm.client", fromlist=["_POLITICA_RETRY_POR_TAREFA"])
        ._POLITICA_RETRY_POR_TAREFA,
        "_bogus",
        {"max_retries": 0, "retry_sleep_seconds": 0, "min_interval_seconds": None, "temperature": None},
    )


def test_get_llm_roteia_para_geminiprovider(monkeypatch):
    _fixar_tarefa_bogus(monkeypatch, config.PROVIDER_GEMINI)

    llm = get_llm("_bogus", "chave-explicita")

    assert isinstance(llm._provider, GeminiProvider)  # noqa: SLF001


def test_get_llm_roteia_para_openrouterprovider(monkeypatch):
    _fixar_tarefa_bogus(monkeypatch, config.PROVIDER_OPENROUTER)
    monkeypatch.setenv("OPENROUTER_API_KEY", "chave-openrouter")

    llm = get_llm("_bogus")

    assert isinstance(llm._provider, OpenRouterProvider)  # noqa: SLF001


def test_get_llm_roteia_para_openaicompatprovider(monkeypatch):
    _fixar_tarefa_bogus(monkeypatch, config.PROVIDER_OPENAI_COMPAT)
    monkeypatch.setenv("EMPRESA_LLM_API_KEY", "chave-empresa")
    monkeypatch.setenv("EMPRESA_LLM_BASE_URL", "https://ia.empresa.exemplo/v1")

    llm = get_llm("_bogus")

    assert isinstance(llm._provider, OpenAICompatProvider)  # noqa: SLF001
    assert llm._provider._base_url == "https://ia.empresa.exemplo/v1"  # noqa: SLF001


def test_get_llm_gemini_com_api_key_explicito_nao_consulta_chaves(monkeypatch):
    _fixar_tarefa_bogus(monkeypatch, config.PROVIDER_GEMINI)

    chamou_carregar_chaves = {"valor": False}

    def _carregar_chaves_espiao(*args, **kwargs):
        chamou_carregar_chaves["valor"] = True
        return config.carregar_chaves(*args, **kwargs)

    monkeypatch.setattr(config, "carregar_chaves", _carregar_chaves_espiao)

    get_llm("_bogus", "chave-explicita")

    assert chamou_carregar_chaves["valor"] is False


def test_get_llm_gemini_sem_api_key_explicito_resolve_via_chaves(monkeypatch):
    _fixar_tarefa_bogus(monkeypatch, config.PROVIDER_GEMINI)

    chaves = {"GEMINI": "chave-vinda-de-chaves"}
    llm = get_llm("_bogus", None, chaves=chaves)

    assert isinstance(llm._provider, GeminiProvider)  # noqa: SLF001


def test_get_llm_openrouter_resolve_chave_via_chaves_por_config_chave_por_provider(monkeypatch):
    _fixar_tarefa_bogus(monkeypatch, config.PROVIDER_OPENROUTER)

    chaves = {"OPENROUTER": "chave-openrouter-de-teste"}
    llm = get_llm("_bogus", None, chaves=chaves)

    assert isinstance(llm._provider, OpenRouterProvider)  # noqa: SLF001


def test_get_llm_openai_compat_sem_empresa_llm_base_url_levanta_value_error(monkeypatch):
    _fixar_tarefa_bogus(monkeypatch, config.PROVIDER_OPENAI_COMPAT)

    chaves = {"EMPRESA_LLM_API_KEY": "chave", "EMPRESA_LLM_BASE_URL": ""}

    with pytest.raises(ValueError, match="EMPRESA_LLM_BASE_URL"):
        get_llm("_bogus", None, chaves=chaves)


def test_get_llm_openai_compat_sem_empresa_llm_base_url_ausente_do_dict_levanta_value_error(monkeypatch):
    _fixar_tarefa_bogus(monkeypatch, config.PROVIDER_OPENAI_COMPAT)

    chaves = {"EMPRESA_LLM_API_KEY": "chave"}  # sem a chave "EMPRESA_LLM_BASE_URL" nenhuma

    with pytest.raises(ValueError, match="EMPRESA_LLM_BASE_URL"):
        get_llm("_bogus", None, chaves=chaves)


def test_get_llm_provider_desconhecido_levanta_not_implemented_error(monkeypatch):
    # "xai" -- provider que `config.LLM_TASKS["categorizar_pdm"]` ainda usa
    # (Grok 4.5), mas que nenhuma tarefa de LLM_MODELOS_HOJE aponta hoje, e
    # que não é um dos 3 providers implementados neste checkpoint.
    _fixar_tarefa_bogus(monkeypatch, "xai")

    with pytest.raises(NotImplementedError) as exc_info:
        get_llm("_bogus", "chave-qualquer")

    mensagem = str(exc_info.value)
    assert "xai" in mensagem
    assert "gemini" in mensagem
    assert "openrouter" in mensagem
    assert "openai_compat" in mensagem


# =============================================================================
# Aceite do CP 3.2: "a mesma tarefa roda em ≥2 modelos distintos via
# OpenRouter mudando apenas config". Prova via `http_post` fake injetado
# DEPOIS que `get_llm()` já resolveu o provider -- só o `model` de
# `LLM_MODELOS_HOJE` muda entre as 2 chamadas, nada mais no código.
# =============================================================================
class _FakeHttpPostRespostaFixa:
    def __init__(self):
        self.chamadas = []

    def __call__(self, url, *, headers, json, timeout):
        self.chamadas.append({"url": url, "headers": headers, "json": json, "timeout": timeout})

        class _Resp:
            def raise_for_status(self_inner):
                pass

            def json(self_inner):
                return {"choices": [{"message": {"content": '{"ok": true}'}}]}

        return _Resp()


def test_aceite_mesma_tarefa_roda_em_2_modelos_distintos_via_openrouter_mudando_so_config(
    monkeypatch,
):
    _fixar_tarefa_bogus(monkeypatch, config.PROVIDER_OPENROUTER, model="modelo-a")
    llm_a = get_llm("_bogus", None, chaves={"OPENROUTER": "chave"})
    http_post_a = _FakeHttpPostRespostaFixa()
    llm_a._provider._http_post = http_post_a  # noqa: SLF001
    llm_a.generate("mesmo prompt")
    assert http_post_a.chamadas[0]["json"]["model"] == "modelo-a"

    _fixar_tarefa_bogus(monkeypatch, config.PROVIDER_OPENROUTER, model="modelo-b")
    llm_b = get_llm("_bogus", None, chaves={"OPENROUTER": "chave"})
    http_post_b = _FakeHttpPostRespostaFixa()
    llm_b._provider._http_post = http_post_b  # noqa: SLF001
    llm_b.generate("mesmo prompt")
    assert http_post_b.chamadas[0]["json"]["model"] == "modelo-b"

    # Só o `model` mudou entre as 2 chamadas -- provider/tarefa/prompt idênticos.
    assert http_post_a.chamadas[0]["json"]["messages"] == http_post_b.chamadas[0]["json"]["messages"]
    assert llm_a.provider_name == llm_b.provider_name == config.PROVIDER_OPENROUTER
