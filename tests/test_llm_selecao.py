r"""
Testes do Checkpoint 3.3 (Parte A) — `sigft/core/llm/selecao.py` (ver
docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.3, e
docs/refatoracao/MODELOS_IA.md §5 "sem downgrade silencioso").

Cobre: `carregar()` normalizado (sempre as 2 chaves, entradas malformadas
descartadas) e tolerante a ausência/corrupção do arquivo/seção; `resolver()`
(override da tarefa > global > `None`); `definir_global`/`limpar_global`/
`definir_por_tarefa`/`limpar_por_tarefa` (persistência real, `ValueError` de
tarefa desconhecida); `aplicar_recomendados()` batendo com
`config.LLM_DEFAULT`/`config.LLM_TASKS`; e — CRÍTICO — a preservação MÚTUA
entre as chaves de API e a seleção de modelo no MESMO arquivo (read-modify-
write nos 2 sentidos).

Todos os testes usam `config_path=<tmp_path>/api_config.json` — nunca tocam
no `api_config.json` real do repositório (mesmo padrão de
`tests/test_prefs.py`).
"""
from __future__ import annotations

import inspect
import json

import pytest

from sigft import config
from sigft.core.llm import selecao


@pytest.fixture()
def config_path(tmp_path):
    """`api_config.json` de teste — nunca criado automaticamente (os testes
    de "arquivo ausente" dependem disso); só o CAMINHO, dentro de
    `tmp_path`."""
    return tmp_path / "api_config.json"


def _escrever_json(caminho, dados):
    caminho.write_text(json.dumps(dados), encoding="utf-8")


def _ler_json(caminho):
    return json.loads(caminho.read_text(encoding="utf-8"))


# =============================================================================
# A. carregar() -- normalização + tolerância a ausência/corrupção
# =============================================================================

def test_carregar_arquivo_ausente_devolve_estado_vazio(config_path):
    assert selecao.carregar(config_path=config_path) == {"global": None, "por_tarefa": {}}


def test_carregar_json_corrompido_devolve_estado_vazio(config_path):
    config_path.write_text("{isso nao e json valido", encoding="utf-8")
    assert selecao.carregar(config_path=config_path) == {"global": None, "por_tarefa": {}}


def test_carregar_json_que_nao_e_um_objeto_devolve_estado_vazio(config_path):
    _escrever_json(config_path, [1, 2, 3])
    assert selecao.carregar(config_path=config_path) == {"global": None, "por_tarefa": {}}


def test_carregar_sem_chave_reservada_devolve_estado_vazio(config_path):
    _escrever_json(config_path, {"GEMINI": "chave-existente"})
    assert selecao.carregar(config_path=config_path) == {"global": None, "por_tarefa": {}}


def test_carregar_chave_reservada_com_tipo_inesperado_devolve_estado_vazio(config_path):
    _escrever_json(config_path, {"_modelos_ia": "nao e um dict"})
    assert selecao.carregar(config_path=config_path) == {"global": None, "por_tarefa": {}}


def test_carregar_global_malformado_sem_model_e_descartado(config_path):
    _escrever_json(config_path, {"_modelos_ia": {"global": {"provider": "gemini"}}})
    assert selecao.carregar(config_path=config_path)["global"] is None


def test_carregar_global_malformado_sem_provider_e_descartado(config_path):
    _escrever_json(config_path, {"_modelos_ia": {"global": {"model": "gemini-3-flash-preview"}}})
    assert selecao.carregar(config_path=config_path)["global"] is None


def test_carregar_global_com_model_vazio_e_descartado(config_path):
    _escrever_json(config_path, {"_modelos_ia": {"global": {"provider": "gemini", "model": ""}}})
    assert selecao.carregar(config_path=config_path)["global"] is None


def test_carregar_global_com_tipo_errado_e_descartado(config_path):
    _escrever_json(config_path, {"_modelos_ia": {"global": "gemini/modelo-x"}})
    assert selecao.carregar(config_path=config_path)["global"] is None


def test_carregar_por_tarefa_com_tipo_errado_vira_dict_vazio(config_path):
    _escrever_json(config_path, {"_modelos_ia": {"por_tarefa": "nao e um dict"}})
    assert selecao.carregar(config_path=config_path)["por_tarefa"] == {}


def test_carregar_por_tarefa_entradas_malformadas_sao_descartadas_individualmente(config_path):
    _escrever_json(
        config_path,
        {
            "_modelos_ia": {
                "por_tarefa": {
                    "condicoes": {"provider": "openrouter", "model": "modelo-valido"},
                    "tech_specs": {"provider": "openrouter"},  # falta "model" -- descartado
                    "autospec": "nao e um dict",  # descartado
                    "validar_ficha": {"provider": "", "model": "x"},  # provider vazio -- descartado
                }
            }
        },
    )
    estado = selecao.carregar(config_path=config_path)
    assert estado["por_tarefa"] == {"condicoes": {"provider": "openrouter", "model": "modelo-valido"}}


def test_carregar_estado_valido_completo(config_path):
    _escrever_json(
        config_path,
        {
            "_modelos_ia": {
                "global": {"provider": "gemini", "model": "gemini-3-flash-preview"},
                "por_tarefa": {
                    "categorizar_pdm": {"provider": "openrouter", "model": "x-ai/grok-4.5"},
                },
            }
        },
    )
    assert selecao.carregar(config_path=config_path) == {
        "global": {"provider": "gemini", "model": "gemini-3-flash-preview"},
        "por_tarefa": {"categorizar_pdm": {"provider": "openrouter", "model": "x-ai/grok-4.5"}},
    }


def test_carregar_sempre_devolve_as_2_chaves_mesmo_com_secao_vazia(config_path):
    _escrever_json(config_path, {"_modelos_ia": {}})
    estado = selecao.carregar(config_path=config_path)
    assert set(estado) == {"global", "por_tarefa"}


# =============================================================================
# B. resolver() -- override da tarefa > global > None
# =============================================================================

def test_resolver_sem_nada_salvo_devolve_none(config_path):
    assert selecao.resolver("condicoes", config_path=config_path) is None


def test_resolver_usa_o_global_quando_nao_ha_override(config_path):
    selecao.definir_global("gemini", "modelo-global", config_path=config_path)
    assert selecao.resolver("condicoes", config_path=config_path) == {
        "provider": "gemini",
        "model": "modelo-global",
    }


def test_resolver_override_de_tarefa_vence_o_global(config_path):
    selecao.definir_global("gemini", "modelo-global", config_path=config_path)
    selecao.definir_por_tarefa("condicoes", "openrouter", "modelo-so-condicoes", config_path=config_path)

    assert selecao.resolver("condicoes", config_path=config_path) == {
        "provider": "openrouter",
        "model": "modelo-so-condicoes",
    }
    # outra tarefa sem override continua vendo só o global.
    assert selecao.resolver("tech_specs", config_path=config_path) == {
        "provider": "gemini",
        "model": "modelo-global",
    }


def test_interpretacao_segue_o_modelo_do_cria_fichas_sem_global(config_path):
    """O caso do Luan (2026-10-16): modo avançado com o Cria Fichas no
    OpenRouter e nenhum global. A passada 1 (`interpretar_material`) caía no
    Gemini DIRETO do `LLM_MODELOS_HOJE` -- que a VPN da empresa derruba
    ("Connection aborted") -- enquanto o resto do lote ia pelo OpenRouter."""
    selecao.definir_por_tarefa("categorizar_pdm", "openrouter", "google/gemini-3.8-flash",
                               config_path=config_path)

    assert selecao.resolver("interpretar_material", config_path=config_path) == {
        "provider": "openrouter", "model": "google/gemini-3.8-flash"}


def test_interpretacao_segue_o_cria_fichas_antes_do_global(config_path):
    # Quem escolheu um modelo SÓ para o Cria Fichas escolheu para as duas
    # passadas dele; o global é para as tarefas sem escolha própria.
    selecao.definir_global("gemini", "modelo-global", config_path=config_path)
    selecao.definir_por_tarefa("categorizar_pdm", "openrouter", "modelo-cria-fichas",
                               config_path=config_path)

    assert selecao.resolver("interpretar_material", config_path=config_path) == {
        "provider": "openrouter", "model": "modelo-cria-fichas"}


def test_interpretacao_com_escolha_propria_usa_a_propria(config_path):
    selecao.definir_por_tarefa("categorizar_pdm", "openrouter", "modelo-cria-fichas",
                               config_path=config_path)
    # O painel não lista a passada 1 (não é tarefa de `LLM_MODELOS_HOJE`); um
    # override dela só existe escrito à mão no arquivo -- e aí vale.
    bruto = json.loads(config_path.read_text(encoding="utf-8"))
    bruto["_modelos_ia"]["por_tarefa"]["interpretar_material"] = {
        "provider": "gemini", "model": "modelo-da-passada-1"}
    _escrever_json(config_path, bruto)

    assert selecao.resolver("interpretar_material", config_path=config_path) == {
        "provider": "gemini", "model": "modelo-da-passada-1"}


def test_so_a_interpretacao_herda_do_cria_fichas(config_path):
    selecao.definir_por_tarefa("categorizar_pdm", "openrouter", "modelo-cria-fichas",
                               config_path=config_path)
    assert selecao.resolver("condicoes", config_path=config_path) is None


def test_resolver_tarefa_desconhecida_nao_levanta_so_nao_acha_override(config_path):
    selecao.definir_global("gemini", "modelo-global", config_path=config_path)
    # `resolver()` não valida `tarefa` -- uma tarefa que não existe em
    # LLM_MODELOS_HOJE simplesmente não tem override salvo -- cai pro global.
    assert selecao.resolver("tarefa_inventada", config_path=config_path) == {
        "provider": "gemini",
        "model": "modelo-global",
    }


def test_resolver_sem_nada_salvo_e_tarefa_desconhecida_devolve_none(config_path):
    assert selecao.resolver("tarefa_inventada", config_path=config_path) is None


def test_resolver_selecao_malformada_no_disco_e_ignorada_cai_no_proximo_nivel(config_path):
    _escrever_json(
        config_path,
        {
            "_modelos_ia": {
                "global": {"provider": "gemini", "model": "modelo-global-valido"},
                "por_tarefa": {"condicoes": {"provider": "openrouter"}},  # sem "model"
            }
        },
    )
    assert selecao.resolver("condicoes", config_path=config_path) == {
        "provider": "gemini",
        "model": "modelo-global-valido",
    }


# =============================================================================
# C. definir_global / limpar_global
# =============================================================================

def test_definir_global_e_lido_de_volta(config_path):
    selecao.definir_global("openrouter", "meu-modelo", config_path=config_path)
    assert selecao.carregar(config_path=config_path)["global"] == {
        "provider": "openrouter",
        "model": "meu-modelo",
    }


def test_definir_global_sobrescreve_valor_anterior(config_path):
    selecao.definir_global("gemini", "modelo-1", config_path=config_path)
    selecao.definir_global("openrouter", "modelo-2", config_path=config_path)
    assert selecao.carregar(config_path=config_path)["global"] == {
        "provider": "openrouter",
        "model": "modelo-2",
    }


def test_definir_global_preserva_overrides_por_tarefa_ja_salvos(config_path):
    selecao.definir_por_tarefa("condicoes", "openrouter", "modelo-condicoes", config_path=config_path)
    selecao.definir_global("gemini", "modelo-global", config_path=config_path)

    estado = selecao.carregar(config_path=config_path)
    assert estado["global"] == {"provider": "gemini", "model": "modelo-global"}
    assert estado["por_tarefa"] == {
        "condicoes": {"provider": "openrouter", "model": "modelo-condicoes"}
    }


def test_limpar_global_volta_a_none(config_path):
    selecao.definir_global("gemini", "modelo-x", config_path=config_path)
    selecao.limpar_global(config_path=config_path)
    assert selecao.carregar(config_path=config_path)["global"] is None


def test_limpar_global_sem_nada_salvo_e_no_op_silencioso(config_path):
    selecao.limpar_global(config_path=config_path)  # não levanta
    assert selecao.carregar(config_path=config_path)["global"] is None


def test_limpar_global_preserva_overrides_por_tarefa(config_path):
    selecao.definir_por_tarefa("tech_specs", "openrouter", "modelo-x", config_path=config_path)
    selecao.definir_global("gemini", "modelo-global", config_path=config_path)
    selecao.limpar_global(config_path=config_path)

    estado = selecao.carregar(config_path=config_path)
    assert estado["global"] is None
    assert estado["por_tarefa"] == {"tech_specs": {"provider": "openrouter", "model": "modelo-x"}}


# =============================================================================
# D. definir_por_tarefa / limpar_por_tarefa
# =============================================================================

@pytest.mark.parametrize("tarefa", sorted(config.LLM_MODELOS_HOJE))
def test_definir_por_tarefa_aceita_as_5_tarefas_validas(tarefa, config_path):
    selecao.definir_por_tarefa(tarefa, "openrouter", "modelo-x", config_path=config_path)
    assert selecao.carregar(config_path=config_path)["por_tarefa"][tarefa] == {
        "provider": "openrouter",
        "model": "modelo-x",
    }


def test_definir_por_tarefa_tarefa_desconhecida_levanta_value_error(config_path):
    with pytest.raises(ValueError, match="tarefa_que_nao_existe"):
        selecao.definir_por_tarefa("tarefa_que_nao_existe", "gemini", "modelo", config_path=config_path)


def test_definir_por_tarefa_erro_lista_as_tarefas_validas(config_path):
    with pytest.raises(ValueError) as exc_info:
        selecao.definir_por_tarefa("bogus", "gemini", "modelo", config_path=config_path)
    mensagem = str(exc_info.value)
    for tarefa in config.LLM_MODELOS_HOJE:
        assert tarefa in mensagem


def test_definir_por_tarefa_tarefa_desconhecida_nao_grava_nada_no_disco(config_path):
    with pytest.raises(ValueError):
        selecao.definir_por_tarefa("bogus", "gemini", "modelo", config_path=config_path)
    assert not config_path.exists()


def test_definir_por_tarefa_preserva_outras_tarefas_ja_salvas(config_path):
    selecao.definir_por_tarefa("condicoes", "openrouter", "modelo-condicoes", config_path=config_path)
    selecao.definir_por_tarefa("tech_specs", "gemini", "modelo-tech-specs", config_path=config_path)

    estado = selecao.carregar(config_path=config_path)
    assert estado["por_tarefa"] == {
        "condicoes": {"provider": "openrouter", "model": "modelo-condicoes"},
        "tech_specs": {"provider": "gemini", "model": "modelo-tech-specs"},
    }


def test_definir_por_tarefa_preserva_o_global_ja_salvo(config_path):
    selecao.definir_global("gemini", "modelo-global", config_path=config_path)
    selecao.definir_por_tarefa("autospec", "openrouter", "modelo-autospec", config_path=config_path)

    assert selecao.carregar(config_path=config_path)["global"] == {
        "provider": "gemini",
        "model": "modelo-global",
    }


def test_limpar_por_tarefa_remove_o_override(config_path):
    selecao.definir_por_tarefa("condicoes", "openrouter", "modelo-x", config_path=config_path)
    selecao.limpar_por_tarefa("condicoes", config_path=config_path)
    assert "condicoes" not in selecao.carregar(config_path=config_path)["por_tarefa"]


def test_limpar_por_tarefa_sem_override_e_no_op_silencioso(config_path):
    selecao.limpar_por_tarefa("condicoes", config_path=config_path)  # não levanta
    assert selecao.carregar(config_path=config_path)["por_tarefa"] == {}


def test_limpar_por_tarefa_tarefa_desconhecida_levanta_value_error(config_path):
    with pytest.raises(ValueError, match="tarefa_que_nao_existe"):
        selecao.limpar_por_tarefa("tarefa_que_nao_existe", config_path=config_path)


def test_limpar_por_tarefa_preserva_outras_tarefas(config_path):
    selecao.definir_por_tarefa("condicoes", "openrouter", "modelo-condicoes", config_path=config_path)
    selecao.definir_por_tarefa("tech_specs", "gemini", "modelo-tech-specs", config_path=config_path)
    selecao.limpar_por_tarefa("condicoes", config_path=config_path)

    estado = selecao.carregar(config_path=config_path)
    assert estado["por_tarefa"] == {"tech_specs": {"provider": "gemini", "model": "modelo-tech-specs"}}


def test_limpar_por_tarefa_preserva_o_global(config_path):
    selecao.definir_global("gemini", "modelo-global", config_path=config_path)
    selecao.definir_por_tarefa("condicoes", "openrouter", "modelo-condicoes", config_path=config_path)
    selecao.limpar_por_tarefa("condicoes", config_path=config_path)

    assert selecao.carregar(config_path=config_path)["global"] == {
        "provider": "gemini",
        "model": "modelo-global",
    }


# =============================================================================
# E. aplicar_recomendados()
# =============================================================================

def test_aplicar_recomendados_grava_llm_default_como_global(config_path):
    selecao.aplicar_recomendados(config_path=config_path)
    assert selecao.carregar(config_path=config_path)["global"] == config.LLM_DEFAULT


def test_aplicar_recomendados_grava_llm_tasks_como_overrides_por_tarefa(config_path):
    # Grava a forma ROTEÁVEL de cada recomendado (ver `tornar_roteavel`): é
    # igual ao que está em `config.LLM_TASKS` para todo provider que
    # `get_llm()` já constrói, e o equivalente via OpenRouter para os que não
    # (hoje só `categorizar_pdm`/Grok 4.5, cujo provider nativo é "xai").
    selecao.aplicar_recomendados(config_path=config_path)
    estado = selecao.carregar(config_path=config_path)
    for tarefa, cfg in config.LLM_TASKS.items():
        esperado = selecao.tornar_roteavel(cfg, origem=f"LLM_TASKS[{tarefa!r}]")
        assert estado["por_tarefa"][tarefa] == esperado


def test_aplicar_recomendados_cobre_exatamente_as_5_tarefas_de_llm_tasks(config_path):
    selecao.aplicar_recomendados(config_path=config_path)
    estado = selecao.carregar(config_path=config_path)
    assert set(estado["por_tarefa"]) == set(config.LLM_TASKS)


def test_aplicar_recomendados_sobrescreve_selecao_manual_anterior(config_path):
    selecao.definir_global("openrouter", "modelo-manual-anterior", config_path=config_path)
    selecao.definir_por_tarefa(
        "condicoes", "openrouter", "override-manual-anterior", config_path=config_path
    )

    selecao.aplicar_recomendados(config_path=config_path)

    estado = selecao.carregar(config_path=config_path)
    assert estado["global"] == config.LLM_DEFAULT
    assert estado["por_tarefa"]["condicoes"] == config.LLM_TASKS["condicoes"]


def test_aplicar_recomendados_preserva_chaves_de_api_ja_salvas(config_path):
    _escrever_json(config_path, {"GEMINI": "chave-real", "OPENROUTER": "outra-chave"})
    selecao.aplicar_recomendados(config_path=config_path)

    bruto = _ler_json(config_path)
    assert bruto["GEMINI"] == "chave-real"
    assert bruto["OPENROUTER"] == "outra-chave"


# =============================================================================
# F. Preservação MÚTUA entre chaves de API e seleção (crítico -- exigido
#    explicitamente pelo checkpoint: "gravar seleção preserva as chaves de
#    API que já estavam no arquivo, e vice-versa").
# =============================================================================

def test_gravar_selecao_preserva_chaves_de_api_ja_presentes(config_path):
    _escrever_json(
        config_path,
        {
            "GEMINI": "chave-gemini-real",
            "OPENROUTER": "chave-openrouter-real",
            "GOOGLE_SEARCH": "chave-google-search",
        },
    )

    selecao.definir_global("openrouter", "algum-modelo", config_path=config_path)

    bruto = _ler_json(config_path)
    assert bruto["GEMINI"] == "chave-gemini-real"
    assert bruto["OPENROUTER"] == "chave-openrouter-real"
    assert bruto["GOOGLE_SEARCH"] == "chave-google-search"
    assert bruto[selecao.CHAVE_RESERVADA]["global"] == {"provider": "openrouter", "model": "algum-modelo"}


def test_gravar_varias_selecoes_em_sequencia_preserva_chaves_de_api_o_tempo_todo(config_path):
    _escrever_json(config_path, {"GEMINI": "chave-gemini-real"})

    selecao.definir_global("gemini", "modelo-1", config_path=config_path)
    assert _ler_json(config_path)["GEMINI"] == "chave-gemini-real"

    selecao.definir_por_tarefa("condicoes", "openrouter", "modelo-2", config_path=config_path)
    assert _ler_json(config_path)["GEMINI"] == "chave-gemini-real"

    selecao.limpar_global(config_path=config_path)
    assert _ler_json(config_path)["GEMINI"] == "chave-gemini-real"

    selecao.limpar_por_tarefa("condicoes", config_path=config_path)
    assert _ler_json(config_path)["GEMINI"] == "chave-gemini-real"


def test_atualizar_chaves_de_api_por_read_modify_write_preserva_a_selecao(config_path):
    """"Vice-versa" exigido pelo checkpoint: simula o MESMO algoritmo de
    read-modify-write que `frontend.SIG_FT_App.save_keys` passa a usar
    depois da Parte C deste checkpoint (lê o JSON inteiro, atualiza só as
    chaves de API recebidas, regrava tudo) -- prova que gravar uma NOVA
    leva de chaves de API não apaga a sub-árvore "_modelos_ia"."""
    selecao.definir_global("gemini", "modelo-escolhido-pelo-usuario", config_path=config_path)

    # Réplica do algoritmo fixado em SIG_FT_App.save_keys (Parte C deste
    # checkpoint) -- não importa frontend.py (sem Tk neste ambiente).
    novas_chaves_de_api = {"GEMINI": "nova-chave-gemini", "OPENROUTER": "nova-chave-openrouter"}
    bruto = _ler_json(config_path) if config_path.exists() else {}
    bruto.update(novas_chaves_de_api)
    _escrever_json(config_path, bruto)

    estado = selecao.carregar(config_path=config_path)
    assert estado["global"] == {"provider": "gemini", "model": "modelo-escolhido-pelo-usuario"}
    bruto_final = _ler_json(config_path)
    assert bruto_final["GEMINI"] == "nova-chave-gemini"
    assert bruto_final["OPENROUTER"] == "nova-chave-openrouter"


def test_naive_overwrite_sem_read_modify_write_destruiria_a_selecao(config_path):
    """NÃO testa `selecao.py` (que nunca escreve desta forma) -- documenta,
    por contraste, POR QUE o read-modify-write do teste acima é obrigatório:
    um "save_keys" ingênuo (só `json.dump(new_keys, f)` -- o bug que existia
    em `frontend.SIG_FT_App.save_keys` antes da Parte C deste checkpoint)
    destruiria a seleção salva."""
    selecao.definir_global("gemini", "modelo-que-seria-perdido", config_path=config_path)

    # Simula o bug ANTIGO: sobrescreve o arquivo inteiro só com as chaves.
    _escrever_json(config_path, {"GEMINI": "nova-chave"})

    estado = selecao.carregar(config_path=config_path)
    assert estado["global"] is None  # a seleção FOI perdida -- por isso o fix importa


# =============================================================================
# G. Forma no disco / constantes / assinatura pública
# =============================================================================

def test_chave_reservada_e_o_valor_esperado():
    assert selecao.CHAVE_RESERVADA == "_modelos_ia"


def test_forma_no_disco_e_a_documentada(config_path):
    selecao.definir_global("gemini", "modelo-x", config_path=config_path)
    selecao.definir_por_tarefa("condicoes", "openrouter", "modelo-y", config_path=config_path)

    bruto = _ler_json(config_path)
    assert bruto["_modelos_ia"] == {
        "global": {"provider": "gemini", "model": "modelo-x"},
        "por_tarefa": {"condicoes": {"provider": "openrouter", "model": "modelo-y"}},
    }


@pytest.mark.parametrize(
    "funcao",
    [
        selecao.carregar,
        selecao.resolver,
        selecao.definir_global,
        selecao.limpar_global,
        selecao.definir_por_tarefa,
        selecao.limpar_por_tarefa,
        selecao.aplicar_recomendados,
    ],
)
def test_todas_as_funcoes_publicas_tem_config_path_keyword_only_com_default_config_config_file(funcao):
    parametros = inspect.signature(funcao).parameters
    assert "config_path" in parametros
    assert parametros["config_path"].kind == inspect.Parameter.KEYWORD_ONLY
    assert parametros["config_path"].default == config.CONFIG_FILE


# =============================================================================
# tornar_roteavel() / providers_exigidos_pelos_recomendados()
#
# Correção feita na revisão do CP 3.3: `aplicar_recomendados()` gravava
# `config.LLM_TASKS` VERBATIM, incluindo `categorizar_pdm` -> provider "xai",
# que `core/llm/client.py:get_llm()` não roteia. Um clique em "Aplicar
# recomendados" na Home quebrava o módulo "Criar Fichas" na execução
# seguinte (NotImplementedError). Estas 2 funções fecham esse buraco.
# =============================================================================

def test_tornar_roteavel_devolve_inalterado_quando_o_provider_ja_e_roteavel():
    cfg = {"provider": config.PROVIDER_GEMINI, "model": "gemini-3-flash-preview"}

    assert selecao.tornar_roteavel(cfg, origem="teste") == cfg


def test_tornar_roteavel_nao_devolve_o_mesmo_objeto_do_chamador():
    # Devolve CÓPIA: quem chamar pode alterar o resultado sem contaminar
    # `config.LLM_DEFAULT`/`LLM_TASKS` (mesma disciplina de
    # `config.get_task_config`).
    cfg = {"provider": config.PROVIDER_GEMINI, "model": "m"}

    assert selecao.tornar_roteavel(cfg, origem="teste") is not cfg


def test_tornar_roteavel_traduz_grok_nativo_para_openrouter():
    cfg = {"provider": config.PROVIDER_XAI, "model": "grok-4.5"}

    assert selecao.tornar_roteavel(cfg, origem="teste") == {
        "provider": config.PROVIDER_OPENROUTER,
        "model": "x-ai/grok-4.5",
    }


def test_tornar_roteavel_levanta_para_provider_irroteavel_sem_equivalente():
    cfg = {"provider": "provedor-inexistente", "model": "modelo-x"}

    with pytest.raises(ValueError) as exc_info:
        selecao.tornar_roteavel(cfg, origem="LLM_TASKS['bogus']")

    mensagem = str(exc_info.value)
    assert "provedor-inexistente" in mensagem
    assert "LLM_TASKS['bogus']" in mensagem  # a origem entra na mensagem


def test_aplicar_recomendados_nao_grava_nada_se_algum_recomendado_for_irroteavel(
    monkeypatch, config_path
):
    # A validação acontece ANTES da escrita: uma seleção anterior válida não
    # pode ser destruída por uma tentativa de aplicar recomendados inválidos.
    selecao.definir_global("gemini", "modelo-anterior", config_path=config_path)
    monkeypatch.setitem(config.LLM_TASKS, "condicoes", {"provider": "inexistente", "model": "m"})

    with pytest.raises(ValueError):
        selecao.aplicar_recomendados(config_path=config_path)

    assert selecao.carregar(config_path=config_path)["global"] == {
        "provider": "gemini",
        "model": "modelo-anterior",
    }


def test_aplicar_recomendados_grava_so_providers_roteaveis(config_path):
    selecao.aplicar_recomendados(config_path=config_path)
    estado = selecao.carregar(config_path=config_path)

    assert estado["global"]["provider"] in config.CHAVE_POR_PROVIDER
    for tarefa, cfg in estado["por_tarefa"].items():
        assert cfg["provider"] in config.CHAVE_POR_PROVIDER, tarefa


def test_providers_exigidos_pelos_recomendados_reflete_o_que_seria_gravado(config_path):
    exigidos = selecao.providers_exigidos_pelos_recomendados()

    selecao.aplicar_recomendados(config_path=config_path)
    estado = selecao.carregar(config_path=config_path)
    gravados = {estado["global"]["provider"]} | {
        cfg["provider"] for cfg in estado["por_tarefa"].values()
    }

    assert exigidos == gravados


def test_providers_exigidos_inclui_openrouter_por_causa_do_grok_em_categorizar_pdm():
    # É o que faz a UI avisar "falta OPENROUTER_API_KEY" ANTES de aplicar.
    assert config.PROVIDER_OPENROUTER in selecao.providers_exigidos_pelos_recomendados()
