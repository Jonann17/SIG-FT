r"""
Testes do Checkpoint 3.1 — migração dos 4 consumidores diretos de
`google.generativeai` para `LLMClient`/`get_llm()`.

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.1:
`analyzer_backend.DatasheetAnalyzer`, `cria_fichas_no_pmib_v1_backend.
GeminiCategorizer`, `upload_conditions_backend.ConditionsProcessor` e
`upload_tech_specs_backend.TechSpecsProcessor`.

Estratégia (evita mockar `google.generativeai` de novo em cada arquivo):
cada instância é construída normalmente (`get_llm()` real por baixo,
`google.generativeai` já stubado como `MagicMock` em tests/conftest.py) e,
depois, `instancia._llm` é SUBSTITUÍDO por um `_FakeLLM` -- um duplo de
`LLMClient` que grava a chamada recebida e devolve/levanta o que o teste
configurar. Isso testa exatamente o que este checkpoint mudou (a FIAÇÃO
entre cada consumidor e `self._llm`), sem re-testar `LLMClient`/
`GeminiProvider` (já cobertos em tests/test_llm_client.py e
tests/test_llm_gemini_provider.py) nem a leitura de Excel/pandas (fora de
escopo deste checkpoint -- `extrair_dados_brutos_excel` é monkeypatchado
onde precisa, para não depender de pandas/openpyxl reais neste ambiente de
teste, que os tem stubados como MagicMock).
"""
import pytest

import analyzer_backend
import cria_fichas_no_pmib_v1_backend
import upload_conditions_backend
import upload_tech_specs_backend
from sigft import config
from sigft.core.llm.client import LLMClient, LLMResponse


@pytest.fixture(autouse=True)
def _isola_config_file_do_cwd_real(monkeypatch, tmp_path):
    """CP 3.3 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.3):
    `get_llm()` (chamado por dentro do `__init__` das 4 classes abaixo)
    passou a consultar `config.CONFIG_FILE` para resolver a seleção de
    modelo do usuário -- isola estes testes de um `api_config.json` REAL
    que porventura exista no cwd de quem roda a suíte (ex.: máquina de dev
    que já usou o app de verdade e tem uma seleção salva), apontando para um
    caminho garantidamente inexistente. Sem isto, as asserções abaixo (que
    assumem os modelos de `LLM_MODELOS_HOJE`) ficariam sujeitas ao estado
    local da máquina que roda a suíte."""
    monkeypatch.setattr(config, "CONFIG_FILE", str(tmp_path / "api_config_isolado_test.json"))


# =============================================================================
# Helpers
# =============================================================================
class _FakeLLM:
    """Substitui `self._llm` (uma instância de `LLMClient`) nos 4
    consumidores migrados -- grava toda chamada recebida e devolve
    `retorno` ou levanta `excecao` (um dos dois, nunca ambos)."""

    def __init__(self, retorno=None, excecao=None):
        self.retorno = retorno
        self.excecao = excecao
        self.chamadas = []

    def generate(self, prompt, *, system=None, json_mode=False, tags=None):
        self.chamadas.append(
            {"prompt": prompt, "system": system, "json_mode": json_mode, "tags": tags}
        )
        if self.excecao is not None:
            raise self.excecao
        return self.retorno


def _resposta_ok(parsed_json):
    """`LLMResponse` de sucesso mínima, com `parsed_json` = o que o teste
    quiser simular como resultado já limpo/parseado."""
    return LLMResponse(
        text="texto cru da IA",
        parsed_json=parsed_json,
        tokens_in=None,
        tokens_out=None,
        custo_usd=None,
        model="modelo-fake",
        provider="gemini",
        duracao_s=0.0,
    )


class _FakeLocSempreKeyError:
    """`.loc[...]` de um DataFrame fake que SEMPRE levanta `KeyError` --
    simula "PMIB ainda não tem linha/coluna correspondente no status" (o
    cenário que os `except KeyError:`/`except:` de
    `ConditionsProcessor.processar_ia_lote` já tratam hoje), sem depender de
    `pandas.DataFrame`/`pandas.Series` reais (mockados neste ambiente de
    teste -- ver tests/conftest.py)."""

    def __getitem__(self, chave):
        raise KeyError(chave)


class _FakeDfStatusSempreKeyError:
    def __init__(self):
        self.loc = _FakeLocSempreKeyError()


# =============================================================================
# 1. analyzer_backend.DatasheetAnalyzer (tarefa "validar_ficha")
# =============================================================================
def test_datasheet_analyzer_init_resolve_llm_client_via_get_llm():
    analyzer = analyzer_backend.DatasheetAnalyzer("uma-chave")

    assert isinstance(analyzer._llm, LLMClient)
    assert analyzer._llm.model == "gemini-3.1-pro-preview"
    assert analyzer._llm.provider_name == "gemini"


def test_datasheet_analyzer_nao_tem_mais_atributos_de_rate_limit_proprios():
    analyzer = analyzer_backend.DatasheetAnalyzer("uma-chave")

    assert not hasattr(analyzer, "last_api_call_time")
    assert not hasattr(analyzer, "min_seconds_between_calls")


def test_call_gemini_api_sucesso_devolve_parsed_json():
    analyzer = analyzer_backend.DatasheetAnalyzer("uma-chave")
    fake_llm = _FakeLLM(retorno=_resposta_ok({"campos_fixos": {}}))
    analyzer._llm = fake_llm

    resultado = analyzer._call_gemini_api("meu prompt")

    assert resultado == {"campos_fixos": {}}
    assert len(fake_llm.chamadas) == 1
    assert fake_llm.chamadas[0]["prompt"] == "meu prompt"
    assert fake_llm.chamadas[0]["tags"] == {"modulo": "analyzer_backend", "tarefa": "validar_ficha"}


def test_call_gemini_api_falha_total_devolve_none_sem_propagar(capsys):
    analyzer = analyzer_backend.DatasheetAnalyzer("uma-chave")
    analyzer._llm = _FakeLLM(excecao=RuntimeError("API fora do ar"))

    resultado = analyzer._call_gemini_api("meu prompt")

    assert resultado is None  # preserva o "return None em falha total" de hoje
    saida = capsys.readouterr().out
    assert "API Error" in saida  # preserva o print de erro de hoje


# =============================================================================
# 2. cria_fichas_no_pmib_v1_backend.GeminiCategorizer (tarefa "categorizar_pdm")
# =============================================================================
def test_gemini_categorizer_init_resolve_llm_client_via_get_llm():
    cat = cria_fichas_no_pmib_v1_backend.GeminiCategorizer("uma-chave")

    assert isinstance(cat._llm, LLMClient)
    assert cat._llm.model == "gemini-3.1-pro-preview"
    assert cat._llm.max_retries == 0  # SEM retry, política de categorizar_pdm


def test_gemini_categorizer_init_sem_api_key_ainda_imprime_aviso(capsys):
    cria_fichas_no_pmib_v1_backend.GeminiCategorizer("")

    saida = capsys.readouterr().out
    assert "AVISO" in saida


def test_gemini_categorizer_init_com_api_key_nao_imprime_aviso(capsys):
    cria_fichas_no_pmib_v1_backend.GeminiCategorizer("uma-chave")

    saida = capsys.readouterr().out
    assert "AVISO" not in saida


def test_processar_lote_sem_api_key_levanta_value_error_antes_de_chamar_llm():
    cat = cria_fichas_no_pmib_v1_backend.GeminiCategorizer("")
    fake_llm = _FakeLLM(retorno=_resposta_ok([]))
    cat._llm = fake_llm

    try:
        cat.processar_lote(df_itens=None, lista_pdms="lista", instrucoes="regras")
        assert False, "deveria ter levantado ValueError"
    except ValueError as e:
        assert str(e) == "API Key não configurada."

    assert fake_llm.chamadas == []  # nunca chegou a chamar a IA


def test_processar_lote_sucesso_devolve_parsed_json_sem_retry():
    cat = cria_fichas_no_pmib_v1_backend.GeminiCategorizer("uma-chave")
    cat._formatar_itens = lambda df: "### ITEM 1 formatado"
    fake_llm = _FakeLLM(retorno=_resposta_ok([{"pdm_escolhido": "PDM.4020.001"}]))
    cat._llm = fake_llm

    resultado = cat.processar_lote(df_itens=object(), lista_pdms="PDM.4020.001 - BOMBA", instrucoes="MANUAL")

    assert resultado == [{"pdm_escolhido": "PDM.4020.001"}]
    assert len(fake_llm.chamadas) == 1
    prompt_enviado = fake_llm.chamadas[0]["prompt"]
    assert "### ITEM 1 formatado" in prompt_enviado
    assert "PDM.4020.001 - BOMBA" in prompt_enviado
    assert "MANUAL" in prompt_enviado
    assert fake_llm.chamadas[0]["tags"] == {
        "modulo": "cria_fichas_no_pmib_v1_backend",
        "tarefa": "categorizar_pdm",
    }


def test_processar_lote_falha_e_relevantada_envolta_em_erro_na_ia():
    cat = cria_fichas_no_pmib_v1_backend.GeminiCategorizer("uma-chave")
    cat._formatar_itens = lambda df: "itens"
    cat._llm = _FakeLLM(excecao=RuntimeError("json invalido"))

    try:
        cat.processar_lote(df_itens=object(), lista_pdms="pdms", instrucoes="regras")
        assert False, "deveria ter levantado Exception"
    except Exception as e:
        assert str(e) == "Erro na IA: json invalido"


# =============================================================================
# 3. upload_conditions_backend.ConditionsProcessor (tarefa "condicoes")
# =============================================================================
def test_conditions_processor_init_resolve_llm_client_via_get_llm():
    processor = upload_conditions_backend.ConditionsProcessor("uma-chave")

    assert isinstance(processor._llm, LLMClient)
    assert processor._llm.model == "gemini-3.5-flash"
    assert processor._llm.max_retries == 2
    assert processor._llm.retry_sleep_seconds == 30
    assert processor._llm.min_interval_seconds is None


def test_processar_ia_lote_sucesso_chama_llm_com_system_e_marca_pmib_codigo():
    processor = upload_conditions_backend.ConditionsProcessor("uma-chave")
    fake_llm = _FakeLLM(retorno=_resposta_ok({"legislacao_pt": "texto"}))
    processor._llm = fake_llm
    processor.extrair_dados_brutos_excel = lambda caminho: {"descricao_breve": "Bomba"}

    logs = []
    resultado = processor.processar_ia_lote(
        ["4500063671.1234.xlsx"], _FakeDfStatusSempreKeyError(), callback_log=logs.append
    )

    assert len(resultado) == 1
    assert resultado[0]["pmib_codigo"] == "4500063671.1234"
    assert resultado[0]["legislacao_pt"] == "texto"
    assert len(fake_llm.chamadas) == 1
    assert fake_llm.chamadas[0]["system"]  # system_prompt (15 regras) foi passado
    assert fake_llm.chamadas[0]["tags"] == {
        "modulo": "upload_conditions_backend",
        "tarefa": "condicoes",
    }
    assert any("Sucesso API" in msg for msg in logs)


def test_processar_ia_lote_falha_definitiva_loga_e_nao_quebra_o_loop():
    processor = upload_conditions_backend.ConditionsProcessor("uma-chave")
    processor._llm = _FakeLLM(excecao=RuntimeError("API fora do ar"))
    processor.extrair_dados_brutos_excel = lambda caminho: {"descricao_breve": "Bomba"}

    logs = []
    resultado = processor.processar_ia_lote(
        ["4500063671.9999.xlsx"], _FakeDfStatusSempreKeyError(), callback_log=logs.append
    )

    assert resultado == []
    assert any("Falha definitiva no PMIB 4500063671.9999" in msg for msg in logs)


# =============================================================================
# 4. upload_tech_specs_backend.TechSpecsProcessor (tarefa "tech_specs")
# =============================================================================
def test_tech_specs_processor_init_resolve_llm_client_via_get_llm():
    processor = upload_tech_specs_backend.TechSpecsProcessor("uma-chave")

    assert isinstance(processor._llm, LLMClient)
    assert processor._llm.model == "gemini-3.5-flash"
    assert processor._llm.max_retries == 2
    assert processor._llm.retry_sleep_seconds == 2
    assert processor._llm.min_interval_seconds is None


def test_chamar_gemini_specs_sucesso_devolve_parsed_json_com_json_mode():
    # A carga é um item COMPLETO (chave + ação + tipo + resposta) porque
    # desde 2026-08-11 `_chamar_gemini_specs` valida o contrato antes de
    # devolver (`normalizar_resposta_specs`). O que este teste do CP 3.1
    # afere continua sendo a FIAÇÃO -- json_mode, system, tags --, e para
    # isso o conteúdo do item é indiferente; o que não pode é ser um item
    # que o RPA aceitaria e depois preencheria a ficha em branco.
    item = {"CARACTERISTICA_CHAVE": "Vazão", "ACAO": "PREENCHER",
            "TIPO": "NUM", "RESPOSTA_PT_FINAL": "80"}
    processor = upload_tech_specs_backend.TechSpecsProcessor("uma-chave")
    fake_llm = _FakeLLM(retorno=_resposta_ok([item]))
    processor._llm = fake_llm

    resultado = processor._chamar_gemini_specs({"CODIGO_PMIB": "1234"})

    assert resultado == [item]
    assert len(fake_llm.chamadas) == 1
    assert fake_llm.chamadas[0]["json_mode"] is True
    assert fake_llm.chamadas[0]["system"]  # system_instruction (4 regras) foi passado
    assert fake_llm.chamadas[0]["tags"] == {
        "modulo": "upload_tech_specs_backend",
        "tarefa": "tech_specs",
    }


def test_chamar_gemini_specs_falha_total_devolve_none_e_loga():
    processor = upload_tech_specs_backend.TechSpecsProcessor("uma-chave")
    processor._llm = _FakeLLM(excecao=RuntimeError("erro 500"))

    logs = []
    resultado = processor._chamar_gemini_specs({"CODIGO_PMIB": "1234"}, callback_log=logs.append)

    assert resultado is None
    assert any("Erro ao chamar IA" in msg for msg in logs)


# =============================================================================
# 2b. `modelo_em_uso` — o log da UI tem que dizer o modelo que de fato rodou
# =============================================================================
# Em 2026-08-11 o usuário selecionou MiniMax M3 no painel "Modelos de IA",
# rodou um lote inteiro, e o console do módulo escreveu "Processando com IA
# (Gemini)..." -- texto fixo, escrito antes do CP 3.3 existir. O lote saiu
# certo e barato (o log de custos provou: `minimax/minimax-m3`), mas a tela
# afirmava outra coisa. A única forma de descobrir o que rodou era abrir
# `logs/llm_usage.jsonl` depois.
#
# `modelo_em_uso` pergunta ao `LLMClient` JÁ CONSTRUÍDO -- o mesmo objeto que
# vai fazer a chamada. É o que torna impossível o log divergir da chamada.

def test_modelo_em_uso_descreve_o_provider_e_o_modelo_resolvidos():
    cat = cria_fichas_no_pmib_v1_backend.GeminiCategorizer("uma-chave")

    assert cat.modelo_em_uso == f"{cat._llm.provider_name}/{cat._llm.model}"


def test_modelo_em_uso_acompanha_a_selecao_salva_no_painel(tmp_path, monkeypatch):
    """O caso REAL: painel apontando para OpenRouter/MiniMax.

    Se `modelo_em_uso` fosse texto fixo (ou lesse `LLM_MODELOS_HOJE` em vez
    do cliente), este teste passaria mostrando "gemini" -- exatamente o bug
    que ele existe para impedir.
    """
    from sigft.core.llm import selecao

    config_path = tmp_path / "api_config.json"
    selecao.definir_global("openrouter", "minimax/minimax-m3", config_path=str(config_path))
    monkeypatch.setattr(config, "CONFIG_FILE", str(config_path))

    cat = cria_fichas_no_pmib_v1_backend.GeminiCategorizer("uma-chave")

    assert cat.modelo_em_uso == "openrouter/minimax/minimax-m3"
    assert "gemini" not in cat.modelo_em_uso


def test_modelo_em_uso_sem_selecao_mostra_o_padrao_do_sistema(tmp_path, monkeypatch):
    # Contraste do teste acima: sem nada salvo no painel, continua valendo o
    # modelo de hoje -- e o log passa a dizer QUAL é, o que antes ninguém via.
    monkeypatch.setattr(config, "CONFIG_FILE", str(tmp_path / "vazio.json"))

    cat = cria_fichas_no_pmib_v1_backend.GeminiCategorizer("uma-chave")

    assert cat.modelo_em_uso == "gemini/gemini-3.1-pro-preview"
