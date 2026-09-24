r"""
Testes do Checkpoint 3.1 — `sigft.core.llm.client.get_llm()` (fábrica).
Estendido no Checkpoint 3.3 (seção final deste arquivo) com a CADEIA DE
RESOLUÇÃO do modelo (seleção do usuário via `core/llm/selecao.py` vencendo
o fallback embutido).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.1. Cobre
especificamente a DECISÃO deste checkpoint (registrada em
docs/refatoracao/PENDENCIAS.md): `get_llm(tarefa, api_key)` resolve o modelo
via `config.LLM_MODELOS_HOJE` — NÃO via `config.LLM_TASKS` (que contém os
modelos DECIDIDOS/alvo, consumidos só INDIRETAMENTE a partir do CP 3.3, via
`selecao.aplicar_recomendados()` — ver seção final) — e a política de
retry/rate-limit resultante bate com a tabela do checkpoint (`max_retries`,
`retry_sleep_seconds`, `min_interval_seconds` por tarefa).
"""
import json

import pytest

from sigft import config
from sigft.core.llm.client import LLMClient, get_llm
from sigft.core.llm.providers.gemini import GeminiProvider


@pytest.fixture(autouse=True)
def _isola_config_file_do_cwd_real(monkeypatch, tmp_path):
    """CP 3.3: `get_llm()` passa a consultar `config.CONFIG_FILE` (via
    `sigft.core.llm.selecao.resolver`, quando `selecao_resolvida` não é
    passado) para resolver a seleção de modelo do usuário -- isola TODOS os
    testes deste módulo de um `api_config.json` REAL que porventura exista
    no cwd de quem roda a suíte (ex.: uma máquina de dev que já usou o app
    de verdade e tem uma seleção salva), apontando por padrão para um
    caminho garantidamente inexistente dentro de `tmp_path`. Os testes que
    exercitam a seleção de propósito (seção final deste arquivo) reapontam
    `config.CONFIG_FILE` para um arquivo seu, ainda dentro de um `tmp_path`
    isolado -- nunca o `api_config.json` real do repositório."""
    monkeypatch.setattr(config, "CONFIG_FILE", str(tmp_path / "api_config_isolado_test.json"))


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
        # 1, e nao 2, desde 2026-09-24: cada tentativa passou a esperar 300 s
        # (documento inteiro), ver tests/test_autospec_falha_da_ia.py.
        ("autospec", 1, 5, 60),
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


# -----------------------------------------------------------------------------
# O invariante que FALTAVA (2026-09-03)
# -----------------------------------------------------------------------------
# O teste acima existe desde o CP 3.1 e é bom — mas está ancorado em
# `LLM_MODELOS_HOJE`, e foi exatamente o mapa incompleto que virou a âncora.
# Uma tarefa registrada em `LLM_TASKS` DEPOIS do CP 3.1 (`traduzir_pdm`) não
# aparecia em `LLM_MODELOS_HOJE`, então o laço nunca a visitava, e a suíte
# ficou verde enquanto a tarefa era 100% inalcançável em produção:
#
#     ValueError: Tarefa de IA desconhecida: 'traduzir_pdm'.
#
# O usuário só descobriu rodando 1192 arquivos. Um mapa não pode ser, ao mesmo
# tempo, o objeto testado e a lista do que testar.
#
# `LLM_TASKS` é o catálogo VIVO de tarefas — é ele que diz o que o aplicativo
# se propõe a fazer com IA. Toda tarefa que está lá tem de ser resolvível.

@pytest.mark.parametrize("tarefa", sorted(config.LLM_TASKS))
def test_TODA_tarefa_de_LLM_TASKS_e_resolvivel_por_get_llm(tarefa):
    """Registrar a tarefa em `LLM_TASKS` e esquecer dos mapas que `get_llm`
    consulta produz um recurso que não roda uma única vez — e nada acusa.

    Este é o teste que teria pego o defeito de `traduzir_pdm`."""
    llm = get_llm(tarefa, None)
    assert llm.max_retries is not None
    assert llm._provider is not None  # noqa: SLF001


def test_a_politica_de_retry_cobre_LLM_TASKS_e_nao_so_o_baseline():
    """O mesmo invariante, dito sobre o mapa em vez de sobre a fábrica: é o
    que dá a mensagem legível quando alguém acrescenta uma tarefa."""
    from sigft.core.llm.client import _POLITICA_RETRY_POR_TAREFA

    faltando = sorted(set(config.LLM_TASKS) - set(_POLITICA_RETRY_POR_TAREFA))
    assert not faltando, (
        f"tarefa(s) em LLM_TASKS sem politica de retry: {faltando}. "
        "get_llm levanta KeyError ao resolve-las."
    )


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


# =============================================================================
# CP 3.3 — cadeia de resolução: seleção do usuário (`core/llm/selecao.py`)
# vence `LLM_MODELOS_HOJE`. Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase
# 3 -> CP 3.3, *Aceite*: "trocar o modelo na UI muda a próxima chamada".
# =============================================================================
from sigft.core.llm import selecao


def test_sem_selecao_alguma_continua_resolvendo_via_llm_modelos_hoje_nada_mudou_em_producao():
    # Mesmo teste "de sempre" (topo do arquivo), repetido aqui de propósito
    # para deixar explícito, ao lado dos testes de seleção abaixo, que o
    # caminho DEFAULT (sem `config.CONFIG_FILE` apontando pra nada real, sem
    # `selecao_resolvida`) continua batendo com LLM_MODELOS_HOJE nas 5
    # tarefas -- prova de que instalar o CP 3.3 não troca modelo nenhum.
    for tarefa, cfg_hoje in config.LLM_MODELOS_HOJE.items():
        llm = get_llm(tarefa, None)
        assert llm.provider_name == cfg_hoje["provider"]
        assert llm.model == cfg_hoje["model"]


def test_get_llm_selecao_resolvida_injetada_e_usada_sem_tocar_o_disco(monkeypatch, tmp_path):
    # Aponta CONFIG_FILE para um arquivo que, se fosse lido, devolveria um
    # modelo DIFERENTE do injetado -- prova que `selecao_resolvida` realmente
    # pula a leitura de disco (não é só "o disco concorda por acaso").
    caminho = tmp_path / "api_config.json"
    selecao.definir_global("gemini", "modelo-do-disco-nao-deveria-ser-usado", config_path=str(caminho))
    monkeypatch.setattr(config, "CONFIG_FILE", str(caminho))

    llm = get_llm(
        "condicoes",
        None,
        chaves={},
        selecao_resolvida={"provider": "openrouter", "model": "modelo-injetado-no-teste"},
    )

    assert llm.provider_name == "openrouter"
    assert llm.model == "modelo-injetado-no-teste"


def test_get_llm_selecao_global_no_disco_e_usada_quando_nao_ha_override_de_tarefa(monkeypatch, tmp_path):
    caminho = tmp_path / "api_config.json"
    selecao.definir_global("openrouter", "modelo-global-da-ui", config_path=str(caminho))
    monkeypatch.setattr(config, "CONFIG_FILE", str(caminho))

    llm = get_llm("condicoes", None, chaves={"OPENROUTER": "chave"})

    assert llm.provider_name == "openrouter"
    assert llm.model == "modelo-global-da-ui"


def test_get_llm_override_de_tarefa_no_disco_vence_a_selecao_global(monkeypatch, tmp_path):
    caminho = tmp_path / "api_config.json"
    selecao.definir_global("gemini", "modelo-global", config_path=str(caminho))
    selecao.definir_por_tarefa(
        "tech_specs", "openrouter", "modelo-so-de-tech-specs", config_path=str(caminho)
    )
    monkeypatch.setattr(config, "CONFIG_FILE", str(caminho))

    llm_tech_specs = get_llm("tech_specs", None, chaves={})
    llm_condicoes = get_llm("condicoes", None, chaves={})

    assert llm_tech_specs.provider_name == "openrouter"
    assert llm_tech_specs.model == "modelo-so-de-tech-specs"
    # "condicoes" não tem override -- cai para o GLOBAL.
    assert llm_condicoes.provider_name == "gemini"
    assert llm_condicoes.model == "modelo-global"


def test_get_llm_selecao_malformada_no_disco_e_ignorada_cai_no_llm_modelos_hoje(monkeypatch, tmp_path):
    caminho = tmp_path / "api_config.json"
    caminho.write_text(
        json.dumps({"_modelos_ia": {"global": {"provider": "openrouter"}}}),  # falta "model"
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "CONFIG_FILE", str(caminho))

    llm = get_llm("condicoes", None, chaves={})

    assert llm.provider_name == config.LLM_MODELOS_HOJE["condicoes"]["provider"]
    assert llm.model == config.LLM_MODELOS_HOJE["condicoes"]["model"]


def test_get_llm_politica_de_retry_e_temperature_continuam_da_tarefa_mesmo_com_selecao(
    monkeypatch, tmp_path
):
    caminho = tmp_path / "api_config.json"
    selecao.definir_por_tarefa("autospec", "openrouter", "outro-modelo-qualquer", config_path=str(caminho))
    monkeypatch.setattr(config, "CONFIG_FILE", str(caminho))

    llm = get_llm("autospec", None, chaves={})

    assert llm.model == "outro-modelo-qualquer"  # o modelo mudou...
    # ...mas a política continua sendo a de "autospec" (tabela por TAREFA,
    # nunca por modelo/seleção) -- mesmos valores de
    # test_get_llm_politica_de_retry_por_tarefa acima.
    assert llm.max_retries == 1
    assert llm.retry_sleep_seconds == 5
    assert llm.min_interval_seconds == 60
    assert llm._provider._temperature == 0.1  # noqa: SLF001


def test_aceite_selecao_via_definir_global_muda_a_proxima_chamada_de_get_llm(monkeypatch, tmp_path):
    # *Aceite* literal do CP 3.3: "trocar o modelo na UI muda a próxima
    # chamada (verificável no registro de uso)". `selecao.definir_global` é
    # o que o botão "Salvar seleção" do painel "Modelos de IA" chama por
    # baixo (Parte C do checkpoint).
    caminho = tmp_path / "api_config.json"
    monkeypatch.setattr(config, "CONFIG_FILE", str(caminho))

    # ANTES de qualquer seleção: get_llm resolve o modelo de hoje (nenhum
    # arquivo em `caminho` existe ainda).
    antes = get_llm("validar_ficha", "uma-chave")
    assert antes.provider_name == "gemini"
    assert antes.model == config.LLM_MODELOS_HOJE["validar_ficha"]["model"]

    # Usuário troca o modelo pela UI -- sem reiniciar o app, sem passar
    # `selecao_resolvida` (o caminho de PRODUÇÃO, não o de teste).
    selecao.definir_global("openrouter", "novo-modelo-escolhido-na-ui", config_path=str(caminho))

    depois = get_llm("validar_ficha", None, chaves={"OPENROUTER": "chave-openrouter"})
    assert depois.provider_name == "openrouter"
    assert depois.model == "novo-modelo-escolhido-na-ui"
    # Política continua vindo da TAREFA (validar_ficha), idêntica antes/depois.
    assert depois.max_retries == antes.max_retries == 2
    assert depois.retry_sleep_seconds == antes.retry_sleep_seconds == 5
    assert depois.min_interval_seconds == antes.min_interval_seconds == 60


def test_aceite_selecao_sobrevive_a_releitura_simulando_reinicio_do_app(monkeypatch, tmp_path):
    # "seleção sobrevive a reinício do app" (*Aceite* do CP 3.3): já que
    # `get_llm()` lê o disco do zero em toda chamada (sem cache em memória
    # entre chamadas), 2 chamadas independentes -- simulando "antes" e
    # "depois de reiniciar o app" -- devem concordar.
    caminho = tmp_path / "api_config.json"
    selecao.definir_por_tarefa("condicoes", "gemini", "modelo-persistente", config_path=str(caminho))
    monkeypatch.setattr(config, "CONFIG_FILE", str(caminho))

    llm_sessao_1 = get_llm("condicoes", "uma-chave")
    llm_sessao_2 = get_llm("condicoes", "uma-chave")  # "reinício" simulado

    assert llm_sessao_1.model == llm_sessao_2.model == "modelo-persistente"


@pytest.mark.parametrize("tarefa", sorted(config.LLM_MODELOS_HOJE))
def test_aplicar_recomendados_deixa_todas_as_5_tarefas_construiveis_por_get_llm(
    monkeypatch, tmp_path, tarefa
):
    # REGRESSÃO (corrigida durante a revisão do CP 3.3): "Aplicar
    # recomendados" gravava `config.LLM_TASKS` VERBATIM, e
    # `LLM_TASKS["categorizar_pdm"]["provider"]` é "xai" (Grok 4.5 nativo),
    # que `get_llm()` não roteia -- um clique no botão da Home fazia o módulo
    # "Criar Fichas" levantar NotImplementedError na execução seguinte.
    # `selecao.tornar_roteavel()` passou a traduzir esses casos para o
    # equivalente via OpenRouter (config.MODELO_RECOMENDADO_ROTEAVEL).
    # Este teste trava o INVARIANTE geral: depois de aplicar os recomendados,
    # NENHUMA das 5 tarefas pode ficar inconstruível.
    caminho = tmp_path / "api_config.json"
    selecao.aplicar_recomendados(config_path=str(caminho))
    monkeypatch.setattr(config, "CONFIG_FILE", str(caminho))

    llm = get_llm(tarefa, "chave-qualquer")  # não deve levantar

    assert llm.provider_name in config.CHAVE_POR_PROVIDER


def test_aplicar_recomendados_traduz_grok_nativo_para_o_equivalente_via_openrouter(
    monkeypatch, tmp_path
):
    # O caso concreto que motivou a correção acima: a decisão de produto
    # (MODELOS_IA.md §3) pede Grok 4.5 em `categorizar_pdm`, e o único
    # caminho real até ele hoje é o OpenRouter (mesma forma que
    # `config.LLM_FAVORITOS` já expõe na UI).
    assert config.LLM_TASKS["categorizar_pdm"]["provider"] == "xai"  # pré-condição

    caminho = tmp_path / "api_config.json"
    selecao.aplicar_recomendados(config_path=str(caminho))
    monkeypatch.setattr(config, "CONFIG_FILE", str(caminho))

    llm = get_llm("categorizar_pdm", "chave-qualquer")

    assert llm.provider_name == config.PROVIDER_OPENROUTER
    assert llm.model == "x-ai/grok-4.5"
    # A política de retry continua vindo da TAREFA, não do modelo.
    assert llm.max_retries == 0
