r"""
Testes do Checkpoint 3.2 — migração de `autospec_backend.AutoSpecCore` para
`LLMClient` (remoção do LangChain residual).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.2. `google.
generativeai` já está stubado como `MagicMock` em `tests/conftest.py`, então
`AutoSpecCore(...)` pode ser construído NORMALMENTE (não precisa de
`__new__` como em `tests/test_ficha_layout.py`) -- `get_llm("autospec", ...)`
por baixo cria um `GeminiProvider` de verdade, sobre o `MagicMock`.
"""
import autospec_backend
from sigft.core.llm.client import LLMClient, LLMResponse


def _make_autospec_core(gemini_key="chave-fake-de-teste"):
    return autospec_backend.AutoSpecCore(
        gemini_key=gemini_key, llama_key=None, google_search_key=None, google_cse_id=None
    )


# =============================================================================
# `self._llm` é um `LLMClient` com o mesmo modelo/temperature de hoje.
# =============================================================================
def test_llm_e_uma_instancia_de_llmclient():
    core = _make_autospec_core()

    assert isinstance(core._llm, LLMClient)  # noqa: SLF001


def test_llm_usa_o_modelo_gemini_3_1_pro_preview_equivalente_ao_langchain():
    core = _make_autospec_core()

    assert core._llm.model == "gemini-3.1-pro-preview"  # noqa: SLF001
    assert core._llm.provider_name == "gemini"  # noqa: SLF001


def test_temperature_0_1_chega_ao_provider_preservando_o_langchain():
    # `ChatGoogleGenerativeAI(..., temperature=0.1)` (LangChain, removido
    # neste checkpoint) aplicava temperature=0.1 -- preservada via
    # `_POLITICA_RETRY_POR_TAREFA["autospec"]["temperature"]` em
    # `core/llm/client.py`, chegando ao `GeminiProvider._temperature`.
    core = _make_autospec_core()

    provider = core._llm._provider  # noqa: SLF001
    assert provider._temperature == 0.1  # noqa: SLF001


def test_autospec_ganha_retry_que_antes_nao_tinha():
    core = _make_autospec_core()

    # Política de "autospec" -- mesma tabela usada por get_llm() -- concede
    # 2 retentativas (3 tentativas totais); o LangChain de antes não tinha
    # NENHUM retry.
    assert core._llm.max_retries == 2  # noqa: SLF001


# =============================================================================
# AutoSpecCore não tem mais atributo `llm` (público) -- só `_llm`.
# =============================================================================
def test_autospec_core_nao_tem_mais_atributo_llm_publico():
    core = _make_autospec_core()

    assert not hasattr(core, "llm")


# =============================================================================
# generate_ai_response com `_llm` substituído por um fake.
# =============================================================================
class _FakeLLM:
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
    return LLMResponse(
        text="texto cru da IA",
        parsed_json=parsed_json,
        tokens_in=None,
        tokens_out=None,
        custo_usd=None,
        model="gemini-3.1-pro-preview",
        provider="gemini",
        duracao_s=0.0,
    )


def test_generate_ai_response_devolve_parsed_json_no_sucesso():
    core = _make_autospec_core()
    fake = _FakeLLM(retorno=_resposta_ok({"empilhamento": "3"}))
    core._llm = fake  # noqa: SLF001

    resultado = core.generate_ai_response(
        "Motor X", "Fabricante Y", "Descrição completa", {"empilhamento": {"type": "text", "desc": "Empilhamento", "ref": "M42"}}, "contexto qualquer",
    )

    assert resultado == {"empilhamento": "3"}
    assert len(fake.chamadas) == 1
    assert fake.chamadas[0]["tags"] == {"modulo": "autospec_backend", "tarefa": "autospec"}


def test_generate_ai_response_devolve_dict_vazio_e_printa_erro_na_falha(capsys):
    core = _make_autospec_core()
    fake = _FakeLLM(excecao=RuntimeError("IA indisponível"))
    core._llm = fake  # noqa: SLF001

    resultado = core.generate_ai_response(
        "Motor X", "Fabricante Y", "Descrição completa", {"empilhamento": {"type": "text", "desc": "Empilhamento", "ref": "M42"}}, "contexto qualquer",
    )

    assert resultado == {}
    saida = capsys.readouterr().out
    assert "Erro IA:" in saida
    assert "IA indisponível" in saida


def test_generate_ai_response_sem_missing_nao_chama_a_ia():
    core = _make_autospec_core()
    fake = _FakeLLM(retorno=_resposta_ok({}))
    core._llm = fake  # noqa: SLF001

    resultado = core.generate_ai_response("Motor X", "Fabricante Y", "Descrição", {}, "contexto")

    assert resultado == {}
    assert fake.chamadas == []


# =============================================================================
# Nenhum import de langchain no módulo.
# =============================================================================
def test_nenhum_import_de_langchain_no_modulo():
    # Checa só LINHAS DE IMPORT reais (não comentários/docstrings que citam
    # "LangChain" como histórico da remoção, ex.: "[CP 3.2] LangChain
    # removido -- ...", presentes de propósito no módulo).
    import inspect

    codigo_fonte = inspect.getsource(autospec_backend)
    linhas_de_import = [
        linha.strip()
        for linha in codigo_fonte.splitlines()
        if linha.strip().startswith("import ") or linha.strip().startswith("from ")
    ]
    assert not any("langchain" in linha.lower() for linha in linhas_de_import)
