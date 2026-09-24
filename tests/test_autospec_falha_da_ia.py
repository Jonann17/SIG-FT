r"""A ficha cuja IA nao respondeu era contada como SUCESSO (ficha 0088, 2026-09-24).

O log da primeira rodada do usuario:

    > Chamada de IA falhou (ReadTimeout: ... Read timed out. (read timeout=120)).
    >  -> Salvo: 4500063671.0088_completed.xlsx
    > ✅ 4500063671.0088.xlsx — salvo como 4500063671.0088_completed.xlsx
    > ✅ 1 sucesso(s) · ❌ 0 falha(s) · ⏭️ 0 pulado(s)
    >    Tempo total: 6min 12s

Seis minutos (tres tentativas de 120 s) para, no fim, gravar um
`_completed.xlsx` igual ao original e dizer "sucesso". Quem roda um lote de
cinquenta fichas le o resumo, nao cada linha -- e o resumo mentia.

O contrato de `generate_ai_response` (devolver `{}` na falha) FICA: ha
testes e chamadores que dependem dele. O que muda e que a falha passa a ser
registrada em `ultima_falha_ia`, e quem conta o lote (`process_queue`,
`processar_conferidos`) le esse registro antes de salvar.
"""
import json

from sigft import config
from sigft.core.llm.client import get_llm
from sigft.services.autospec import AutoSpecCore


class _LLMFake:
    def __init__(self, parsed=None, excecao=None):
        self.parsed = parsed if parsed is not None else {"empilhamento": "5"}
        self.excecao = excecao
        self.chamadas = []

    def generate(self, prompt, **kwargs):
        self.chamadas.append(prompt)
        if self.excecao is not None:
            raise self.excecao
        return _Resposta(self.parsed)


class _Resposta:
    def __init__(self, parsed):
        self.parsed_json = parsed
        self.text = json.dumps(parsed)


CAMPO = {"empilhamento": {"type": "text", "desc": "Empilhamento maximo", "ref": "M42"}}


def _core(llm):
    core = AutoSpecCore(
        gemini_key="chave-fake", llama_key=None, google_search_key=None,
        google_cse_id=None,
        selecao_resolvida={"provider": config.PROVIDER_GEMINI, "model": "m"},
    )
    core._llm = llm
    core.usar_cache_resposta = False
    return core


# =============================================================================
# 1. A falha fica registrada -- e o sucesso limpa o registro
# =============================================================================
def test_a_falha_da_IA_fica_registrada_com_o_motivo():
    core = _core(_LLMFake(excecao=TimeoutError("Read timed out. (read timeout=120)")))
    assert core.generate_ai_response("Fusivel", "", "Desc", CAMPO, "ctx") == {}
    assert "Read timed out" in (core.ultima_falha_ia or "")


def test_uma_resposta_boa_limpa_a_falha_anterior():
    """A instancia processa o lote inteiro: a falha da ficha 3 nao pode
    contaminar a ficha 4."""
    core = _core(_LLMFake(excecao=RuntimeError("fora do ar")))
    core.generate_ai_response("Fusivel", "", "Desc", CAMPO, "ctx")
    core._llm = _LLMFake(parsed={"empilhamento": "5"})
    core.generate_ai_response("Fusivel", "", "Desc", CAMPO, "ctx")
    assert core.ultima_falha_ia is None


# =============================================================================
# 2. O lote conta falha, e nao salva
# =============================================================================
def _core_de_lote(salvos):
    core = AutoSpecCore.__new__(AutoSpecCore)
    core.analyze_sheet = lambda *a, **k: (
        "wb", {"campo_x": {"type": "text", "desc": "Campo X", "ref": "H1"}},
        "txt", "fab", "desc", "cod")
    core.retrieve_context = lambda *a, **k: ("contexto", [])

    def _falha(*a, **k):
        core.ultima_falha_ia = "ReadTimeout: Read timed out. (read timeout=120)"
        return {}

    core.generate_ai_response = _falha
    core.fill_save = lambda wb, ficha, *a, **k: salvos.append(ficha) or "x_completed.xlsx"
    return core


def test_ficha_sem_resposta_da_IA_e_FALHA_no_resumo_do_lote():
    salvos = []
    core = _core_de_lote(salvos)
    texto = "\n".join(core.process_queue([{"sheet": "A.xlsx", "refs": []}], None))
    assert "0 sucesso(s)" in texto and "1 falha(s)" in texto, texto
    assert "Read timed out" in texto


def test_ficha_sem_resposta_da_IA_nao_gera_completed():
    """Um `_completed.xlsx` igual ao original e pior que nenhum: parece
    trabalho feito."""
    salvos = []
    core = _core_de_lote(salvos)
    list(core.process_queue([{"sheet": "A.xlsx", "refs": []}], None))
    assert salvos == []


def test_a_segunda_passada_tambem_conta_a_falha():
    salvos = []
    core = _core_de_lote(salvos)
    core.contexto_das_urls = lambda *a, **k: "--- WEB DOC: x ---\ntexto"
    texto = "\n".join(core.processar_conferidos({"A.xlsx": ["https://x"]}, None))
    assert "1 falha(s)" in texto, texto
    assert salvos == []


# =============================================================================
# 3. Tempo de espera: documento inteiro e mais texto para ler
# =============================================================================
def test_autospec_espera_ate_300s_por_tentativa_e_tenta_so_mais_uma_vez():
    """120 s x 3 tentativas foram os 6 min 12 s do log. Com o documento
    inteiro indo para a IA, 120 s e pouco para uma tentativa -- e tres
    tentativas de 300 s seriam 15 minutos presos numa ficha."""
    llm = get_llm(
        "autospec", chaves={"OPENROUTER": "k"},
        selecao_resolvida={"provider": config.PROVIDER_OPENROUTER, "model": "google/x"},
    )
    assert llm.max_retries == 1
    assert llm._provider._timeout == 300


def test_as_outras_tarefas_continuam_com_120s():
    llm = get_llm(
        "condicoes", chaves={"OPENROUTER": "k"},
        selecao_resolvida={"provider": config.PROVIDER_OPENROUTER, "model": "google/x"},
    )
    assert llm._provider._timeout == 120


def test_o_gemini_direto_tambem_recebe_o_tempo_limite():
    chamadas = []

    class _Modelo:
        def generate_content(self, conteudo, **kwargs):
            chamadas.append(kwargs)

            class _R:
                text = "{}"
                usage_metadata = None
            return _R()

    class _Genai:
        def configure(self, **k):
            pass

        def GenerativeModel(self, *a, **k):
            return _Modelo()

    from sigft.core.llm.providers.gemini import GeminiProvider

    GeminiProvider("k", "m", genai_module=_Genai(), timeout=300).generate_raw("oi")
    assert chamadas[0].get("request_options") == {"timeout": 300}
