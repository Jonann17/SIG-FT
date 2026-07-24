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


def test_linha_status_pmib_e_4():
    # pdm_backend.py:169 (`skiprows=3`, 0-based) e :176 ("... (linha 4).").
    assert sigft_config.LINHA_STATUS_PMIB == 4


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
    # frontend.py:4255-4258 e docs/refatoracao/PENDENCIAS.md.
    assert sigft_config.ENV_VAR_POR_CHAVE == {
        "GEMINI": "API_GEMINI_LUAN_GMAIL",
        "GOOGLE_SEARCH": "GOOGLE_SEARCH_API",
        "GOOGLE_CSE": "GOOGLE_CSE_API",
        "LLAMA": "LLAMA_CLOUD_API",
    }


# =============================================================================
# B. LLM_TASKS / get_task_config
# =============================================================================

def test_llm_tasks_tem_exatamente_as_5_tarefas_do_cp_3_1():
    assert set(sigft_config.LLM_TASKS) == {
        "categorizar_pdm",
        "validar_ficha",
        "condicoes",
        "tech_specs",
        "autospec",
    }


def test_llm_tasks_provider_e_gemini_em_todas_hoje():
    # Hoje tudo é Gemini direto (google.generativeai ou, no autospec, o mesmo
    # modelo via LangChain ChatGoogleGenerativeAI) — ver plano, CP 3.1/3.2.
    for tarefa, cfg in sigft_config.LLM_TASKS.items():
        assert cfg["provider"] == "gemini", tarefa
        assert cfg["provider"] == sigft_config.PROVIDER_GEMINI, tarefa


@pytest.mark.parametrize(
    "tarefa,modelo_esperado",
    [
        # cria_fichas_no_pmib_v1_backend.py:131 (GeminiCategorizer.processar_lote)
        ("categorizar_pdm", "gemini-3.1-pro-preview"),
        # analyzer_backend.py:451 (DatasheetAnalyzer._call_gemini_api)
        ("validar_ficha", "gemini-3.1-pro-preview"),
        # upload_conditions_backend.py:363 (ConditionsProcessor.processar_ia_lote)
        ("condicoes", "gemini-3.5-flash"),
        # upload_tech_specs_backend.py:285-286 (TechSpecsProcessor._chamar_gemini_specs)
        ("tech_specs", "gemini-3.5-flash"),
        # autospec_backend.py:173 (AutoSpecCore.__init__ -> ChatGoogleGenerativeAI)
        ("autospec", "gemini-3.1-pro-preview"),
    ],
)
def test_llm_tasks_modelo_exato_por_tarefa(tarefa, modelo_esperado):
    assert sigft_config.LLM_TASKS[tarefa]["model"] == modelo_esperado


def test_llm_tasks_cada_entrada_tem_so_provider_e_model():
    for cfg in sigft_config.LLM_TASKS.values():
        assert set(cfg) == {"provider", "model"}


def test_get_task_config_resolve_provider_e_model():
    assert sigft_config.get_task_config("condicoes") == {
        "provider": "gemini",
        "model": "gemini-3.5-flash",
    }


def test_get_task_config_retorna_copia_independente_do_dict_global():
    resultado = sigft_config.get_task_config("autospec")
    resultado["model"] = "outro-modelo-qualquer"
    # Mutar o retorno não pode afetar LLM_TASKS (get_task_config devolve cópia).
    assert sigft_config.LLM_TASKS["autospec"]["model"] == "gemini-3.1-pro-preview"


def test_get_task_config_tarefa_desconhecida_levanta_erro_claro():
    with pytest.raises(ValueError, match="Tarefa de IA desconhecida"):
        sigft_config.get_task_config("tarefa_que_nao_existe")


def test_get_task_config_erro_lista_as_tarefas_validas():
    with pytest.raises(ValueError) as exc_info:
        sigft_config.get_task_config("bogus")
    mensagem = str(exc_info.value)
    for tarefa in sigft_config.LLM_TASKS:
        assert tarefa in mensagem


# =============================================================================
# C. Carregamento de chaves (carregar_chaves / get_key)
# =============================================================================

CAMINHO_INEXISTENTE = "/caminho/que/definitivamente/nao/existe/api_config.json"


def test_carregar_chaves_le_das_variaveis_de_ambiente(monkeypatch):
    monkeypatch.setenv("API_GEMINI_LUAN_GMAIL", "chave-gemini-env")
    monkeypatch.setenv("GOOGLE_SEARCH_API", "chave-search-env")
    monkeypatch.setenv("GOOGLE_CSE_API", "chave-cse-env")
    monkeypatch.setenv("LLAMA_CLOUD_API", "chave-llama-env")

    chaves = sigft_config.carregar_chaves(CAMINHO_INEXISTENTE)

    assert chaves == {
        "GEMINI": "chave-gemini-env",
        "GOOGLE_SEARCH": "chave-search-env",
        "GOOGLE_CSE": "chave-cse-env",
        "LLAMA": "chave-llama-env",
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
    }


def test_json_vazio_tambem_e_tratado_como_corrompido(tmp_path):
    caminho_config = tmp_path / "api_config.json"
    caminho_config.write_text("", encoding="utf-8")

    # Arquivo existe mas está vazio -> json.load levanta JSONDecodeError,
    # cai no mesmo except -> defaults (todas None, sem env setada).
    chaves = sigft_config.carregar_chaves(caminho_config)
    assert chaves == {"GEMINI": None, "GOOGLE_SEARCH": None, "GOOGLE_CSE": None, "LLAMA": None}


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
