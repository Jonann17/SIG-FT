"""
Testes de carga de config (CP 1.1 do plano de refatoração — ver
docs/refatoracao/PLANO_REFATORACAO.md, Fase 1 -> CP 1.1) para
`sigft/config.py`.

Este checkpoint é ADITIVO: `sigft/config.py` é um módulo NOVO, nenhum
consumidor de produção foi migrado para importar dele ainda. Os testes
abaixo verificam:
  A. as constantes centralizadas têm os valores REAIS de hoje (levantados por
     grep no código de produção — ver comentários em `sigft/config.py`);
  B. `LLM_TASKS` tem as 5 tarefas do CP 3.1 com provider/model esperados, e
     `get_task_config()` resolve/trata tarefa desconhecida;
  C. o carregamento de chaves (`carregar_chaves`/`get_key`) replica
     `SIG_FT_App.load_keys()`/`get_key()` (frontend.py:4254-4282): env vars
     como defaults, `api_config.json` sobrescrevendo, arquivo ausente/JSON
     corrompido caindo para defaults, chave ausente -> "".

`sigft/config.py` NÃO importa nenhuma dependência pesada (pandas, selenium,
google-generativeai etc.) — só stdlib e, defensivamente, `python-dotenv` (que
também não é necessário para nada testado aqui, pois `carregar_chaves()` lê
`os.environ` diretamente). Por isso este arquivo não depende de nenhum stub
de `tests/conftest.py` além do `sys.path` com a raiz do repo (para "import
sigft.config" funcionar).
"""
import json

import pytest

import sigft.config as sigft_config


@pytest.fixture(autouse=True)
def limpar_env_vars_de_chaves(monkeypatch):
    """Baseline limpo: remove as 4 env vars de chave antes de cada teste
    deste módulo, independente do que já esteja no ambiente real (uma
    máquina de dev pode ter `API_GEMINI_LUAN_GMAIL` etc. exportada no shell;
    os testes não podem depender/ser afetados por isso)."""
    for env_var_name in sigft_config.ENV_VAR_POR_CHAVE.values():
        monkeypatch.delenv(env_var_name, raising=False)
    yield


# =============================================================================
# A. Constantes
# =============================================================================

def test_portal_url_e_o_dominio_pmib_da_itaipu():
    assert sigft_config.PORTAL_URL == "https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList"


def test_google_cse_endpoint():
    assert sigft_config.GOOGLE_CSE_ENDPOINT == "https://www.googleapis.com/customsearch/v1"


def test_aba_lista_materiais_nome_canonico():
    assert sigft_config.ABA_LISTA_MATERIAIS == "Lista de Materiais"


def test_aba_lista_materiais_variantes_igual_a_search_pmib_backend():
    # Mesma lista/ordem de PMIBSearcher.__init__ (search_pmib_backend.py:11).
    assert sigft_config.ABA_LISTA_MATERIAIS_VARIANTES == (
        "Lista de Materiais",
        "LISTA DE MATERIAIS",
        "Lista de materiais",
    )


def test_nome_canonico_esta_entre_as_variantes():
    assert sigft_config.ABA_LISTA_MATERIAIS in sigft_config.ABA_LISTA_MATERIAIS_VARIANTES


def test_prefixo_contrato():
    assert sigft_config.PREFIXO_CONTRATO == "4500063671"


def test_linha_specs_ficha_e_79():
    # analyzer_backend.py:52/377, autospec_backend.py:60, pdm_backend.py:239,
    # translator_backend.py:111, frontend.py:1374.
    assert sigft_config.LINHA_SPECS_FICHA == 79


def test_linha_status_pmib_e_5():
    # Layout v2 do `_STATUS_PMIB` (04/10/2026): a linha 4 é a da revisão em
    # uso e o cabeçalho está na 5. É só o valor de reserva -- quem lê acha o
    # cabeçalho pela busca (ver tests/test_status_pmib_cabecalho_linha5.py).
    assert sigft_config.LINHA_STATUS_PMIB == 5


def test_colunas_chave_principais():
    assert sigft_config.COL_CODIGO_PMIB == "CÓDIGO PMIB"
    assert sigft_config.COL_DESCRICAO == "DESCRIÇÃO"
    assert sigft_config.COL_PDM_USADO == "PDM usado"
    assert sigft_config.COL_CONDICOES == "CONDIÇÕES"
    assert sigft_config.COL_CARACT_TECNICAS == "CARACT. TÉCNICAS"
    assert sigft_config.COL_INFO_GERAIS == "INFO. GERAIS"


def test_config_file_e_api_config_json():
    assert sigft_config.CONFIG_FILE == "api_config.json"


def test_env_var_por_chave_usa_os_nomes_atuais_exatos():
    # Nomes de env var preservados por compatibilidade/free-tier — ver
    # frontend.py:4255-4258 e docs/refatoracao/PENDENCIAS.md. As 3 últimas
    # entradas são do CP 3.2 (gateway OpenRouter + endpoint OpenAI-
    # compatível genérico da futura IA interna da empresa).
    assert sigft_config.ENV_VAR_POR_CHAVE == {
        "GEMINI": "API_GEMINI_LUAN_GMAIL",
        "GOOGLE_SEARCH": "GOOGLE_SEARCH_API",
        "GOOGLE_CSE": "GOOGLE_CSE_API",
        "LLAMA": "LLAMA_CLOUD_API",
        "OPENROUTER": "OPENROUTER_API_KEY",
        "EMPRESA_LLM_BASE_URL": "EMPRESA_LLM_BASE_URL",
        "EMPRESA_LLM_API_KEY": "EMPRESA_LLM_API_KEY",
        # 2026-10-27: o webhook do workflow "Revisão das listas" no n8n da GE (o AMP).
        "AMP_WEBHOOK_URL": "SIGFT_AMP_WEBHOOK_URL",
        "AMP_WEBHOOK_CHAVE": "SIGFT_AMP_WEBHOOK_CHAVE",
    }


# =============================================================================
# A2. CP 3.2 — providers novos (OpenRouter/OpenAI-compatível) + CHAVE_POR_PROVIDER
# =============================================================================

def test_provider_openrouter_e_openai_compat():
    assert sigft_config.PROVIDER_OPENROUTER == "openrouter"
    assert sigft_config.PROVIDER_OPENAI_COMPAT == "openai_compat"


def test_openrouter_base_url():
    assert sigft_config.OPENROUTER_BASE_URL == "https://openrouter.ai/api/v1"


def test_openrouter_headers_atribuicao():
    assert sigft_config.OPENROUTER_HEADERS_ATRIBUICAO == {
        "HTTP-Referer": "https://github.com/luanccozer/SIG-FT",
        "X-Title": "SIG-FT",
    }


def test_openrouter_catalogo_cache_e_caminho_relativo():
    assert sigft_config.OPENROUTER_CATALOGO_CACHE == "openrouter_models_cache.json"


def test_chave_por_provider_mapeia_os_3_providers():
    assert sigft_config.CHAVE_POR_PROVIDER == {
        sigft_config.PROVIDER_GEMINI: "GEMINI",
        sigft_config.PROVIDER_OPENROUTER: "OPENROUTER",
        sigft_config.PROVIDER_OPENAI_COMPAT: "EMPRESA_LLM_API_KEY",
    }


def test_chave_por_provider_todas_as_chaves_existem_em_env_var_por_chave():
    # Invariante: toda chave lógica citada em CHAVE_POR_PROVIDER precisa
    # existir em ENV_VAR_POR_CHAVE (senão `carregar_chaves()` nunca a
    # popularia) -- `core/llm/client.py:get_llm()` depende disso.
    for chave_logica in sigft_config.CHAVE_POR_PROVIDER.values():
        assert chave_logica in sigft_config.ENV_VAR_POR_CHAVE


# =============================================================================
# B. LLM_TASKS / get_task_config
# =============================================================================

# As 5 tarefas caracterizadas pelo CP 3.1, e o que foi acrescentado DEPOIS.
# Cada acrescimo entra nesta lista junto com o commit que o adiciona -- e o
# que separa "tarefa nova, decidida" de "tarefa inventada por engano", que e o
# que este teste sempre protegeu. Afirmar igualdade EXATA quebrava em
# qualquer acrescimo, inclusive nos legitimos.
TAREFAS_DO_CP_3_1 = {
    "categorizar_pdm",
    "validar_ficha",
    "condicoes",
    "tech_specs",
    "autospec",
}
#   traduzir_pdm (2026-08-28): traducao PT->EN das perguntas dos PDMs
#   Modificados, para a ficha em ingles.
#   interpretar_material (2026-10-08): passada 1 da escolha de PDM do Cria
#   Fichas -- diz o que o material E, antes da busca no catalogo.
#   docpack_pasta (2026-11-03): sugestao de pasta do DocPack.
TAREFAS_ACRESCENTADAS_DEPOIS = {"traduzir_pdm", "interpretar_material", "docpack_pasta"}


def test_llm_tasks_tem_exatamente_as_5_tarefas_do_cp_3_1():
    assert TAREFAS_DO_CP_3_1 <= set(sigft_config.LLM_TASKS), "tarefa do CP 3.1 sumiu"
    assert (set(sigft_config.LLM_TASKS) - TAREFAS_DO_CP_3_1
            == TAREFAS_ACRESCENTADAS_DEPOIS), "tarefa nova nao declarada"


def test_llm_tasks_provider_por_tarefa_segue_a_decisao():
    # MODELOS_IA.md §3: Grok 4.5 (xai) em categorizar_pdm; Gemini nas demais.
    providers = {t: cfg["provider"] for t, cfg in sigft_config.LLM_TASKS.items()}
    assert providers == {
        "categorizar_pdm": sigft_config.PROVIDER_XAI,
        "validar_ficha": sigft_config.PROVIDER_GEMINI,
        "condicoes": sigft_config.PROVIDER_GEMINI,
        "tech_specs": sigft_config.PROVIDER_GEMINI,
        "autospec": sigft_config.PROVIDER_GEMINI,
        # acrescentadas depois do CP 3.1 -- ver TAREFAS_ACRESCENTADAS_DEPOIS
        "traduzir_pdm": sigft_config.PROVIDER_GEMINI,
        "interpretar_material": sigft_config.PROVIDER_GEMINI,
        "docpack_pasta": sigft_config.PROVIDER_GEMINI,
    }
    assert sigft_config.PROVIDER_XAI == "xai"
    assert sigft_config.PROVIDER_GEMINI == "gemini"


@pytest.mark.parametrize(
    "tarefa,modelo_esperado",
    [
        # MODELOS_IA.md §3 — modelos DECIDIDOS (alvo), NÃO os de hoje (esses
        # ficam em LLM_MODELOS_HOJE, testados à parte).
        ("categorizar_pdm", "grok-4.5"),
        ("validar_ficha", "gemini-3-flash-preview"),
        ("condicoes", "gemini-3-flash-preview"),
        ("tech_specs", "gemini-3-flash-preview"),
        ("autospec", "gemini-3-flash-preview"),
    ],
)
def test_llm_tasks_modelo_decidido_por_tarefa(tarefa, modelo_esperado):
    assert sigft_config.LLM_TASKS[tarefa]["model"] == modelo_esperado


def test_llm_tasks_cada_entrada_tem_so_provider_e_model():
    for cfg in sigft_config.LLM_TASKS.values():
        assert set(cfg) == {"provider", "model"}


def test_get_task_config_resolve_provider_e_model():
    assert sigft_config.get_task_config("condicoes") == {
        "provider": "gemini",
        "model": "gemini-3-flash-preview",
    }


def test_get_task_config_retorna_copia_independente_do_dict_global():
    resultado = sigft_config.get_task_config("autospec")
    resultado["model"] = "outro-modelo-qualquer"
    # Mutar o retorno não pode afetar LLM_TASKS (get_task_config devolve cópia).
    assert sigft_config.LLM_TASKS["autospec"]["model"] == "gemini-3-flash-preview"


def test_get_task_config_tarefa_desconhecida_levanta_erro_claro():
    with pytest.raises(ValueError, match="Tarefa de IA desconhecida"):
        sigft_config.get_task_config("tarefa_que_nao_existe")


def test_get_task_config_erro_lista_as_tarefas_validas():
    with pytest.raises(ValueError) as exc_info:
        sigft_config.get_task_config("bogus")
    mensagem = str(exc_info.value)
    for tarefa in sigft_config.LLM_TASKS:
        assert tarefa in mensagem


def test_llm_default_e_gemini_3_flash_preview():
    # Padrão global decidido em MODELOS_IA.md §3.
    assert sigft_config.LLM_DEFAULT == {
        "provider": "gemini",
        "model": "gemini-3-flash-preview",
    }


def test_llm_modelos_hoje_preserva_os_modelos_atuais_caracterizados():
    # Baseline de EQUIVALÊNCIA do CP 3.1: os modelos EXATOS que o código roda
    # hoje, preservados à parte de LLM_TASKS (que já aponta para os alvos).
    assert sigft_config.LLM_MODELOS_HOJE == {
        "categorizar_pdm": {"provider": "gemini", "model": "gemini-3.1-pro-preview"},
        "validar_ficha": {"provider": "gemini", "model": "gemini-3.1-pro-preview"},
        "condicoes": {"provider": "gemini", "model": "gemini-3.5-flash"},
        "tech_specs": {"provider": "gemini", "model": "gemini-3.5-flash"},
        "autospec": {"provider": "gemini", "model": "gemini-3.1-pro-preview"},
    }


def test_llm_modelos_hoje_tem_as_mesmas_5_tarefas_que_llm_tasks():
    """`LLM_MODELOS_HOJE` é a CARACTERIZAÇÃO do que cada módulo hardcodava
    ANTES do CP 3.1 — é baseline de equivalência, não catálogo de tarefas.

    Uma tarefa criada depois (`traduzir_pdm`, 2026-08-28) **não tem** "modelo
    de antes" para caracterizar, e inventar um só para o mapa ficar simétrico
    faria o baseline mentir. O que este teste guarda continua de pé: nenhuma
    das 5 tarefas caracterizadas sumiu de `LLM_TASKS`, e tudo que está no
    baseline existe no mapa vivo.
    """
    assert set(sigft_config.LLM_MODELOS_HOJE) == TAREFAS_DO_CP_3_1
    assert set(sigft_config.LLM_MODELOS_HOJE) <= set(sigft_config.LLM_TASKS)


def test_llm_precos_cobre_os_modelos_referenciados_hoje_e_alvo():
    # Todo modelo citado em LLM_TASKS/LLM_MODELOS_HOJE precisa ter preço-seed
    # para o UsageTracker (CP 3.4) estimar custo de provedor direto.
    modelos = {cfg["model"] for cfg in sigft_config.LLM_TASKS.values()}
    modelos |= {cfg["model"] for cfg in sigft_config.LLM_MODELOS_HOJE.values()}
    for modelo in modelos:
        assert modelo in sigft_config.LLM_PRECOS_USD_POR_1M, modelo


def test_llm_precos_valores_de_referencia():
    # Amostra dos valores de MODELOS_IA.md §2 (US$ por 1M tokens).
    assert sigft_config.LLM_PRECOS_USD_POR_1M["gemini-3-flash-preview"] == {"input": 0.50, "output": 3.00}
    assert sigft_config.LLM_PRECOS_USD_POR_1M["grok-4.5"] == {"input": 2.00, "output": 6.00}


# =============================================================================
# B2. LLM_FAVORITOS (CP 3.3 — lista curada para o seletor de modelo na UI)
# =============================================================================

_TIERS_VALIDOS = {"economia", "padrao", "poder"}
_CHAVES_MINIMAS_FAVORITO = {"provider", "model", "rotulo", "score", "preco_input", "preco_output", "tier"}
_PROVIDERS_IMPLEMENTADOS = {
    sigft_config.PROVIDER_GEMINI,
    sigft_config.PROVIDER_OPENROUTER,
    sigft_config.PROVIDER_OPENAI_COMPAT,
}


def test_llm_favoritos_e_uma_lista_nao_vazia():
    assert isinstance(sigft_config.LLM_FAVORITOS, list)
    assert len(sigft_config.LLM_FAVORITOS) >= 5  # os 3 da decisão + os 2 usados hoje


def test_llm_favoritos_cada_entrada_tem_as_chaves_minimas_exigidas_pelo_checkpoint():
    for fav in sigft_config.LLM_FAVORITOS:
        assert _CHAVES_MINIMAS_FAVORITO.issubset(set(fav))


def test_llm_favoritos_provider_e_model_sao_strings_nao_vazias():
    for fav in sigft_config.LLM_FAVORITOS:
        assert isinstance(fav["provider"], str) and fav["provider"]
        assert isinstance(fav["model"], str) and fav["model"]
        assert isinstance(fav["rotulo"], str) and fav["rotulo"]


def test_llm_favoritos_provider_e_sempre_um_dos_3_providers_implementados_por_get_llm():
    # `get_llm()` (core/llm/client.py) só roteia gemini/openrouter/
    # openai_compat -- um favorito com outro provider (ex.: "xai", usado só
    # por LLM_TASKS["categorizar_pdm"], gap pré-existente) apareceria na UI
    # mas quebraria com NotImplementedError na primeira chamada real.
    for fav in sigft_config.LLM_FAVORITOS:
        assert fav["provider"] in _PROVIDERS_IMPLEMENTADOS, fav


def test_llm_favoritos_tiers_sao_validos():
    for fav in sigft_config.LLM_FAVORITOS:
        assert fav["tier"] in _TIERS_VALIDOS, fav


def test_llm_favoritos_score_e_precos_sao_numericos_e_nao_negativos():
    for fav in sigft_config.LLM_FAVORITOS:
        assert isinstance(fav["score"], (int, float))
        assert isinstance(fav["preco_input"], (int, float))
        assert isinstance(fav["preco_output"], (int, float))
        assert fav["score"] >= 0
        assert fav["preco_input"] >= 0
        assert fav["preco_output"] >= 0


def test_llm_favoritos_contem_os_3_tiers_da_decisao_do_modelos_ia():
    tiers_presentes = {fav["tier"] for fav in sigft_config.LLM_FAVORITOS}
    assert _TIERS_VALIDOS.issubset(tiers_presentes)


def test_llm_favoritos_contem_gemini_3_flash_preview_como_padrao_global():
    # MODELOS_IA.md §3: padrão global -- MESMO provider+model de LLM_DEFAULT.
    candidatos = [
        fav
        for fav in sigft_config.LLM_FAVORITOS
        if fav["provider"] == sigft_config.PROVIDER_GEMINI and fav["model"] == "gemini-3-flash-preview"
    ]
    assert len(candidatos) == 1
    assert candidatos[0]["tier"] == "padrao"
    assert (candidatos[0]["provider"], candidatos[0]["model"]) == (
        sigft_config.LLM_DEFAULT["provider"],
        sigft_config.LLM_DEFAULT["model"],
    )


def test_llm_favoritos_contem_minimax_m3_como_economia_via_openrouter():
    candidatos = [fav for fav in sigft_config.LLM_FAVORITOS if "minimax" in fav["model"].lower()]
    assert len(candidatos) == 1
    assert candidatos[0]["provider"] == sigft_config.PROVIDER_OPENROUTER
    assert candidatos[0]["tier"] == "economia"


def test_llm_favoritos_contem_grok_4_5_como_poder_via_openrouter():
    candidatos = [fav for fav in sigft_config.LLM_FAVORITOS if "grok" in fav["model"].lower()]
    assert len(candidatos) == 1
    assert candidatos[0]["provider"] == sigft_config.PROVIDER_OPENROUTER
    assert candidatos[0]["tier"] == "poder"
    # MODELOS_IA.md §3: mesmo modelo (Grok 4.5) que LLM_TASKS["categorizar_pdm"]
    # decide, ainda que por um provider DIFERENTE (openrouter, implementado,
    # em vez de xai, gap pré-existente -- ver PENDENCIAS.md).
    assert sigft_config.LLM_TASKS["categorizar_pdm"]["provider"] == sigft_config.PROVIDER_XAI


def test_llm_favoritos_contem_os_2_modelos_usados_hoje_para_o_usuario_poder_reverter():
    # "para que o usuário consiga voltar atrás pela UI" -- exigência
    # explícita do checkpoint: os 2 modelos de LLM_MODELOS_HOJE devem
    # aparecer como favoritos, com o provider NATIVO (gemini), do jeito que
    # rodam em produção hoje.
    modelos_hoje = {cfg["model"] for cfg in sigft_config.LLM_MODELOS_HOJE.values()}
    modelos_favoritos = {
        fav["model"] for fav in sigft_config.LLM_FAVORITOS if fav["provider"] == sigft_config.PROVIDER_GEMINI
    }
    assert modelos_hoje.issubset(modelos_favoritos)


def test_llm_favoritos_precos_batem_com_llm_precos_usd_por_1m():
    # Mesma fonte/seed -- nenhum valor de preço inventado à parte da tabela.
    for fav in sigft_config.LLM_FAVORITOS:
        preco_seed = sigft_config.LLM_PRECOS_USD_POR_1M.get(fav["model"])
        if preco_seed is None:
            continue  # modelo fora da tabela LLM_PRECOS_USD_POR_1M (ex.: slug OpenRouter "vendor/modelo")
        assert fav["preco_input"] == preco_seed["input"]
        assert fav["preco_output"] == preco_seed["output"]


def test_llm_favoritos_sem_entradas_duplicadas_de_provider_model():
    pares = [(fav["provider"], fav["model"]) for fav in sigft_config.LLM_FAVORITOS]
    assert len(pares) == len(set(pares))


# =============================================================================
# C. Carregamento de chaves (carregar_chaves / get_key)
# =============================================================================

CAMINHO_INEXISTENTE = "/caminho/que/definitivamente/nao/existe/api_config.json"


def test_carregar_chaves_le_das_variaveis_de_ambiente(monkeypatch):
    monkeypatch.setenv("API_GEMINI_LUAN_GMAIL", "chave-gemini-env")
    monkeypatch.setenv("GOOGLE_SEARCH_API", "chave-search-env")
    monkeypatch.setenv("GOOGLE_CSE_API", "chave-cse-env")
    monkeypatch.setenv("LLAMA_CLOUD_API", "chave-llama-env")
    # CP 3.2: gateway OpenRouter + endpoint OpenAI-compatível genérico.
    monkeypatch.setenv("OPENROUTER_API_KEY", "chave-openrouter-env")
    monkeypatch.setenv("EMPRESA_LLM_BASE_URL", "https://ia.empresa.exemplo/v1")
    monkeypatch.setenv("EMPRESA_LLM_API_KEY", "chave-empresa-env")
    monkeypatch.setenv("SIGFT_AMP_WEBHOOK_URL", "https://ampworkflow.exemplo/webhook/sigft")
    monkeypatch.setenv("SIGFT_AMP_WEBHOOK_CHAVE", "chave-amp-env")

    chaves = sigft_config.carregar_chaves(CAMINHO_INEXISTENTE)

    assert chaves == {
        "GEMINI": "chave-gemini-env",
        "GOOGLE_SEARCH": "chave-search-env",
        "GOOGLE_CSE": "chave-cse-env",
        "LLAMA": "chave-llama-env",
        "OPENROUTER": "chave-openrouter-env",
        "EMPRESA_LLM_BASE_URL": "https://ia.empresa.exemplo/v1",
        "EMPRESA_LLM_API_KEY": "chave-empresa-env",
        "AMP_WEBHOOK_URL": "https://ampworkflow.exemplo/webhook/sigft",
        "AMP_WEBHOOK_CHAVE": "chave-amp-env",
    }


def test_carregar_chaves_sem_env_e_sem_arquivo_retorna_none_em_todas():
    # Nenhuma env var setada (fixture autouse limpa) e caminho não existe:
    # os.getenv(...) sem default retorna None, igual ao original
    # (frontend.py:4255-4258 -> defaults com valores possivelmente None).
    chaves = sigft_config.carregar_chaves(CAMINHO_INEXISTENTE)
    assert chaves == {
        "GEMINI": None,
        "GOOGLE_SEARCH": None,
        "GOOGLE_CSE": None,
        "LLAMA": None,
        "OPENROUTER": None,
        "EMPRESA_LLM_BASE_URL": None,
        "EMPRESA_LLM_API_KEY": None,
        "AMP_WEBHOOK_URL": None,
        "AMP_WEBHOOK_CHAVE": None,
    }


def test_arquivo_ausente_retorna_apenas_defaults_do_env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_GEMINI_LUAN_GMAIL", "chave-gemini-env")
    caminho_ausente = tmp_path / "nao_existe" / "api_config.json"

    chaves = sigft_config.carregar_chaves(caminho_ausente)

    assert chaves["GEMINI"] == "chave-gemini-env"
    assert chaves["GOOGLE_SEARCH"] is None


def test_api_config_json_sobrescreve_env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_GEMINI_LUAN_GMAIL", "chave-gemini-env")
    monkeypatch.setenv("GOOGLE_SEARCH_API", "chave-search-env")

    caminho_config = tmp_path / "api_config.json"
    caminho_config.write_text(
        json.dumps({"GEMINI": "chave-gemini-SALVA", "GOOGLE_SEARCH": "chave-search-SALVA"}),
        encoding="utf-8",
    )

    chaves = sigft_config.carregar_chaves(caminho_config)

    # Valores salvos em api_config.json SOBRESCREVEM os das env vars.
    assert chaves["GEMINI"] == "chave-gemini-SALVA"
    assert chaves["GOOGLE_SEARCH"] == "chave-search-SALVA"


def test_api_config_json_sobrescreve_so_a_chave_presente_resto_vem_do_env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_GEMINI_LUAN_GMAIL", "chave-gemini-env")
    monkeypatch.setenv("LLAMA_CLOUD_API", "chave-llama-env")

    caminho_config = tmp_path / "api_config.json"
    # Só sobrescreve GEMINI; GOOGLE_SEARCH/GOOGLE_CSE/LLAMA não aparecem no
    # arquivo salvo -> devem continuar vindo do merge com os defaults do env.
    caminho_config.write_text(json.dumps({"GEMINI": "chave-gemini-SALVA"}), encoding="utf-8")

    chaves = sigft_config.carregar_chaves(caminho_config)

    assert chaves["GEMINI"] == "chave-gemini-SALVA"
    assert chaves["LLAMA"] == "chave-llama-env"
    assert chaves["GOOGLE_SEARCH"] is None
    assert chaves["GOOGLE_CSE"] is None


def test_json_corrompido_retorna_apenas_defaults_do_env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_GEMINI_LUAN_GMAIL", "chave-gemini-env")

    caminho_config = tmp_path / "api_config.json"
    caminho_config.write_text("{isso nao é json valido!!!", encoding="utf-8")

    # Comportamento original: `except:` nu (frontend.py:4271-4272) cai para
    # defaults; aqui `except Exception:` produz o mesmo resultado observável.
    chaves = sigft_config.carregar_chaves(caminho_config)

    assert chaves == {
        "GEMINI": "chave-gemini-env",
        "GOOGLE_SEARCH": None,
        "GOOGLE_CSE": None,
        "LLAMA": None,
        "OPENROUTER": None,
        "EMPRESA_LLM_BASE_URL": None,
        "EMPRESA_LLM_API_KEY": None,
        "AMP_WEBHOOK_URL": None,
        "AMP_WEBHOOK_CHAVE": None,
    }


def test_json_valido_mas_nao_e_objeto_tambem_cai_para_defaults(monkeypatch, tmp_path):
    # Caso sutil: o original faz `self.api_keys = {**defaults, **saved}`
    # DENTRO do mesmo try/except (frontend.py:4267-4272). Se `saved` for JSON
    # válido mas não um objeto (ex.: uma lista), `**saved` levanta TypeError,
    # que o `except:` nu também captura -> cai para defaults. Replicado aqui
    # com o merge dentro do try (ver comentário em carregar_chaves).
    monkeypatch.setenv("API_GEMINI_LUAN_GMAIL", "chave-gemini-env")

    caminho_config = tmp_path / "api_config.json"
    caminho_config.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    chaves = sigft_config.carregar_chaves(caminho_config)

    assert chaves == {
        "GEMINI": "chave-gemini-env",
        "GOOGLE_SEARCH": None,
        "GOOGLE_CSE": None,
        "LLAMA": None,
        "OPENROUTER": None,
        "EMPRESA_LLM_BASE_URL": None,
        "EMPRESA_LLM_API_KEY": None,
        "AMP_WEBHOOK_URL": None,
        "AMP_WEBHOOK_CHAVE": None,
    }


def test_json_vazio_tambem_e_tratado_como_corrompido(tmp_path):
    caminho_config = tmp_path / "api_config.json"
    caminho_config.write_text("", encoding="utf-8")

    # Arquivo existe mas está vazio -> json.load levanta JSONDecodeError,
    # cai no mesmo except -> defaults (todas None, sem env setada).
    chaves = sigft_config.carregar_chaves(caminho_config)
    assert chaves == {
        "GEMINI": None,
        "GOOGLE_SEARCH": None,
        "GOOGLE_CSE": None,
        "LLAMA": None,
        "OPENROUTER": None,
        "EMPRESA_LLM_BASE_URL": None,
        "EMPRESA_LLM_API_KEY": None,
        "AMP_WEBHOOK_URL": None,
        "AMP_WEBHOOK_CHAVE": None,
    }


def test_get_key_de_chave_ausente_retorna_string_vazia():
    chaves = {"GEMINI": "abc123"}
    assert sigft_config.get_key(chaves, "NAO_EXISTE") == ""


def test_get_key_de_chave_presente_retorna_o_valor():
    chaves = {"GEMINI": "abc123"}
    assert sigft_config.get_key(chaves, "GEMINI") == "abc123"


def test_get_key_integrado_com_carregar_chaves(monkeypatch, tmp_path):
    monkeypatch.setenv("LLAMA_CLOUD_API", "chave-llama-env")
    chaves = sigft_config.carregar_chaves(tmp_path / "api_config.json")

    assert sigft_config.get_key(chaves, "LLAMA") == "chave-llama-env"
    assert sigft_config.get_key(chaves, "CHAVE_INEXISTENTE") == ""


# =============================================================================
# D. Import defensivo do dotenv (GOTCHA do ambiente)
# =============================================================================

def test_modulo_e_importavel_mesmo_sem_python_dotenv_instalado():
    # Este ambiente de teste não tem python-dotenv instalado (ver
    # tests/conftest.py) — o import defensivo em sigft/config.py garante que
    # `import sigft.config` não quebra por isso. Se dotenv não estiver
    # instalado, `load_dotenv` fica None; se estiver, é a função real.
    assert sigft_config.load_dotenv is None or callable(sigft_config.load_dotenv)


# ===========================================================================
# Limpeza das chaves (2026-08-11) — descoberto num teste real do usuário
# ===========================================================================
# Sintoma: `400 API_KEY_INVALID` em TODAS as tarefas de IA, com uma chave que
# o usuário conferiu e estava certa. Causa provável: um espaço ou `\n` colado
# junto (copiar do Google AI Studio, de um e-mail, de um `.env` editado à mão)
# — invisível na tela, fatal no cabeçalho HTTP.

def test_chave_do_env_perde_espaco_e_quebra_de_linha(monkeypatch, tmp_path):
    monkeypatch.setenv("API_GEMINI_LUAN_GMAIL", "  AIzaSyChaveDeTeste123  \n")

    chaves = sigft_config.carregar_chaves(config_path=tmp_path / "nao-existe.json")

    assert chaves["GEMINI"] == "AIzaSyChaveDeTeste123"


def test_chave_do_arquivo_perde_espaco_e_quebra_de_linha(tmp_path):
    caminho = tmp_path / "api_config.json"
    caminho.write_text(json.dumps({"GEMINI": "\tAIzaSyChaveDeTeste123\n"}), encoding="utf-8")

    chaves = sigft_config.carregar_chaves(config_path=caminho)

    assert chaves["GEMINI"] == "AIzaSyChaveDeTeste123"


def test_limpeza_nao_transforma_ausente_em_vazia(monkeypatch, tmp_path):
    # `None` (env var ausente) tem de continuar `None`: o resto do código usa
    # essa diferença para distinguir "não configurada" de "configurada vazia".
    monkeypatch.delenv("API_GEMINI_LUAN_GMAIL", raising=False)

    chaves = sigft_config.carregar_chaves(config_path=tmp_path / "nao-existe.json")

    assert chaves["GEMINI"] is None


def test_limpeza_nao_toca_na_selecao_de_modelos(tmp_path):
    # A chave reservada `_modelos_ia` (CP 3.3) guarda um DICIONÁRIO, não uma
    # string. Um `.strip()` cego ali estouraria com AttributeError e derrubaria
    # o carregamento inteiro das chaves.
    caminho = tmp_path / "api_config.json"
    caminho.write_text(
        json.dumps({"GEMINI": " k ", "_modelos_ia": {"global": {"provider": "gemini", "model": "x"}}}),
        encoding="utf-8",
    )

    chaves = sigft_config.carregar_chaves(config_path=caminho)

    assert chaves["GEMINI"] == "k"
    assert chaves["_modelos_ia"] == {"global": {"provider": "gemini", "model": "x"}}


# =============================================================================
# B3. O filtro do painel "Modelos de IA" — provedor sem chave não aparece
# =============================================================================
# A regra vive em `frontend.py:criar_painel_modelos_ia` ("Provedores sem chave
# configurada não aparecem"), que NÃO é importável neste ambiente (abre janela
# real). O que dá para travar aqui é a outra metade da regra, que mora em
# `config`: que a lista curada TENHA o que oferecer a cada provedor. Sem isso,
# quem configura só o OpenRouter abre o painel e vê um dropdown vazio, sem
# entender por quê.
#
# Contexto: em 2026-08-11 o usuário colou a chave do OpenRouter, salvou, e o
# painel continuou só com Gemini -- o filtro era calculado uma vez, na
# construção da Home, e "Salvar Chaves" não remontava o painel. Corrigido no
# `frontend.py`; este teste guarda o lado dos dados.

def _favoritos_visiveis(chaves_configuradas):
    """Reproduz o filtro do painel: um favorito só entra se o provedor dele
    tiver chave AGORA."""
    providers_com_chave = {
        provider
        for provider, chave in sigft_config.CHAVE_POR_PROVIDER.items()
        if chave in chaves_configuradas
    }
    return [f for f in sigft_config.LLM_FAVORITOS if f["provider"] in providers_com_chave]


def test_quem_tem_so_a_chave_do_openrouter_tem_modelos_para_escolher():
    visiveis = _favoritos_visiveis({"OPENROUTER"})

    assert visiveis, "painel ficaria vazio para quem só configurou o OpenRouter"
    assert all(f["provider"] == sigft_config.PROVIDER_OPENROUTER for f in visiveis)


def test_quem_tem_so_a_chave_do_gemini_nao_ve_modelo_de_provedor_sem_chave():
    visiveis = _favoritos_visiveis({"GEMINI"})

    assert visiveis
    assert all(f["provider"] == sigft_config.PROVIDER_GEMINI for f in visiveis)


def test_sem_chave_nenhuma_nao_sobra_favorito():
    assert _favoritos_visiveis(set()) == []


def test_com_as_duas_chaves_o_painel_mostra_os_dois_provedores():
    providers = {f["provider"] for f in _favoritos_visiveis({"GEMINI", "OPENROUTER"})}

    assert providers == {sigft_config.PROVIDER_GEMINI, sigft_config.PROVIDER_OPENROUTER}


def test_existe_favorito_openrouter_mais_barato_que_todo_favorito_gemini():
    """O motivo de o usuário ter ido atrás do OpenRouter foi preço.

    Se a lista curada só oferecesse OpenRouter caro, configurar a chave não
    resolveria o problema dele -- e o painel estaria dando uma escolha que não
    é escolha.
    """
    por_provider = {}
    for fav in sigft_config.LLM_FAVORITOS:
        por_provider.setdefault(fav["provider"], []).append(fav["preco_input"])

    mais_barato_openrouter = min(por_provider[sigft_config.PROVIDER_OPENROUTER])
    mais_barato_gemini = min(por_provider[sigft_config.PROVIDER_GEMINI])

    assert mais_barato_openrouter < mais_barato_gemini


# =============================================================================
# B4. Motor de RPA — CP 5.5 (2026-08-25)
# =============================================================================
# Aqui havia cinco testes travando as duas metades da promoção do Playwright:
# quais módulos rodavam nele, que `ficha_duplicada` continuava em Selenium, e
# que `SIGFT_RPA_ENGINE=selenium` devolvia tudo ao motor antigo.
#
# Os cinco descreviam uma ESCOLHA, e a escolha acabou: o Selenium saiu do
# projeto quando a Fase 6 fechou validada no portal. O que resta a testar
# sobre motor não é mais de config -- é de `core/rpa/factory`, e está em
# `tests/test_rpa_factory.py`.
