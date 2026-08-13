r"""Testes do cache de resposta da IA e do `json_mode` (2026-08-12).
Ver `sigft/services/autospec.py`, bloco "CACHE DE RESPOSTA DA IA".

O cache é a economia de token mais agressiva do módulo: **100% numa
reexecução idêntica**, porque a IA simplesmente não é chamada. Isso o torna
também o mais perigoso, e é isso que estes testes guardam — um cache que serve
resposta em situação errada preenche a ficha com dado de OUTRO material, em
silêncio e de graça. As três garantias, em ordem de gravidade:

  1. **Nunca servir resposta que não é daquele prompt** — seção B.
  2. **Um acerto tem de ser indistinguível de uma chamada real** para quem
     está depois dele (`fill_save` e a rastreabilidade de fonte) — seção D.
  3. **Falhar em cache nunca pode custar a ficha** — seção C.

Isolamento: `tests/conftest.py` (nota 5) redireciona o arquivo do cache para
uma pasta temporária por teste. Sem isso, o acerto de um teste faria o
seguinte pular a chamada de IA, e a suíte passaria a depender da ordem.
"""
import json

import pytest

from sigft import config
from sigft.services import autospec
from sigft.services.autospec import AutoSpecCore


# =============================================================================
# Andaimes
# =============================================================================
class _LLMFake:
    """Conta chamadas e devolve o que mandarem. É o instrumento de medida do
    cache: "não foi chamado" é a própria economia."""

    def __init__(self, parsed=None, excecao=None):
        self.parsed = parsed if parsed is not None else {"empilhamento": "5"}
        self.excecao = excecao
        self.chamadas = []

    def generate(self, prompt, *, system=None, json_mode=False, tags=None):
        self.chamadas.append({"prompt": prompt, "json_mode": json_mode})
        if self.excecao is not None:
            raise self.excecao
        return _Resposta(self.parsed)


class _Resposta:
    def __init__(self, parsed):
        self.parsed_json = parsed
        self.text = json.dumps(parsed)


CAMPO = {"empilhamento": {"type": "text", "desc": "Empilhamento maximo", "ref": "M42"}}


def _core(modelo="modelo-a", provider=None):
    core = AutoSpecCore(
        gemini_key="chave-fake",
        llama_key=None,
        google_search_key=None,
        google_cse_id=None,
        selecao_resolvida={
            "provider": provider or config.PROVIDER_GEMINI,
            "model": modelo,
        },
    )
    core._llm = _LLMFake()
    return core


def _logs():
    registro = []

    class _CB:
        def log(self, msg, nivel="info", contexto=None):
            registro.append((nivel, str(msg)))

    return _CB(), registro


# =============================================================================
# A. json_mode — o formato deixa de depender da boa vontade do modelo
# =============================================================================
def test_a_chamada_de_ia_pede_json_nativo():
    """Antes o prompt só PEDIA JSON em texto. Falha de parse aqui devolve a
    ficha vazia, e a confiabilidade de formato varia muito entre modelos —
    o que passou a importar quando o provedor virou trocável."""
    core = _core()
    core.generate_ai_response("Bomba", "KSB", "Desc", CAMPO, "contexto")
    assert core._llm.chamadas[0]["json_mode"] is True


def test_o_json_mode_ATRAVESSA_o_LLMClient_ate_o_provider():
    """O teste acima usa um `_llm` fake e pararia no `LLMClient`. Este vai até
    o fim da corrente — `generate_ai_response` -> `LLMClient` -> provider —
    porque é lá que o flag vira `response_mime_type`/`response_format`. Um elo
    que engolisse o argumento no meio não apareceria de outro jeito."""
    from sigft.core.llm.client import LLMClient

    recebidos = []

    class _ProviderEspiao:
        def generate_raw(self, prompt, *, system=None, json_mode=False):
            recebidos.append(json_mode)
            return ('{"empilhamento": "5"}', None, None)

    core = _core()
    core._llm = LLMClient(
        _ProviderEspiao(), provider_name="gemini", model="m",
        max_retries=0, retry_sleep_seconds=0,
    )
    core.generate_ai_response("Bomba", "KSB", "Desc", CAMPO, "contexto")

    assert recebidos == [True], "o json_mode nao chegou ao provider"


# =============================================================================
# B. A chave — o que pode e o que NÃO pode ser servido de volta
# =============================================================================
def test_mesmo_prompt_e_mesmo_modelo_dao_a_mesma_chave():
    a = autospec._chave_cache_resposta("prompt X", "gemini", "m1")
    b = autospec._chave_cache_resposta("prompt X", "gemini", "m1")
    assert a == b


@pytest.mark.parametrize(
    "args,caso",
    [
        (("prompt Y", "gemini", "m1"), "prompt diferente"),
        (("prompt X", "gemini", "m2"), "modelo diferente"),
        (("prompt X", "openrouter", "m1"), "provedor diferente"),
    ],
)
def test_qualquer_mudanca_relevante_muda_a_chave(args, caso):
    """Servir a resposta de um modelo como se fosse de outro é o erro que
    tornaria a comparação entre modelos mentira."""
    base = autospec._chave_cache_resposta("prompt X", "gemini", "m1")
    assert autospec._chave_cache_resposta(*args) != base, caso


def test_a_chave_nao_carrega_o_prompt_dentro_dela():
    """Privacidade: o prompt tem trecho de datasheet. Só o hash vai a disco."""
    segredo = "PRESSAO MAXIMA 175 bar, cliente Itaipu, material sigiloso"
    chave = autospec._chave_cache_resposta(segredo, "gemini", "m")
    assert segredo not in chave
    assert len(chave) == 64 and all(c in "0123456789abcdef" for c in chave)


# =============================================================================
# C. Ler e gravar — falhar aqui não pode custar a ficha
# =============================================================================
def test_grava_e_le_de_volta():
    autospec._cache_resposta_gravar("k1", {"campo": "valor"})
    assert autospec._cache_resposta_ler("k1") == {"campo": "valor"}


def test_chave_ausente_devolve_None():
    assert autospec._cache_resposta_ler("nunca-gravada") is None


def test_entrada_expirada_e_ignorada():
    autospec._cache_resposta_gravar("k1", {"campo": "v"}, agora=1000.0)
    depois = 1000.0 + autospec.RESPOSTA_IA_CACHE_TTL_S + 1
    assert autospec._cache_resposta_ler("k1", agora=depois) is None


def test_arquivo_corrompido_nao_levanta_excecao(monkeypatch, tmp_path):
    ruim = tmp_path / "corrompido.json"
    ruim.write_text("{isto nao e json", encoding="utf-8")
    monkeypatch.setattr(autospec, "_caminho_cache_resposta", lambda: str(ruim))
    assert autospec._cache_resposta_ler("k") is None


def test_nao_poder_gravar_nao_quebra(monkeypatch):
    """Disco cheio ou pasta somente-leitura custa a economia, não a ficha."""
    monkeypatch.setattr(
        autospec, "_caminho_cache_resposta", lambda: "/caminho/que/nao/existe/x.json"
    )
    autospec._cache_resposta_gravar("k", {"a": 1})  # não pode levantar


@pytest.mark.parametrize("vazia", [{}, [], None, "texto solto", 42])
def test_resposta_vazia_ou_invalida_nao_e_guardada(vazia):
    """Guardar `{}` faria o próximo rerun servir o vazio de volta e nunca mais
    tentar — o erro ficaria congelado."""
    autospec._cache_resposta_gravar("k-vazia", vazia)
    assert autospec._cache_resposta_ler("k-vazia") is None


def test_poda_expirados_na_gravacao():
    autospec._cache_resposta_gravar("velha", {"a": 1}, agora=1000.0)
    muito_depois = 1000.0 + autospec.RESPOSTA_IA_CACHE_TTL_S + 10
    autospec._cache_resposta_gravar("nova", {"b": 2}, agora=muito_depois)

    with open(autospec._caminho_cache_resposta(), encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    assert "velha" not in dados, "expirada devia ter sido podada"
    assert "nova" in dados


def test_teto_de_entradas_mantem_as_mais_recentes(monkeypatch):
    monkeypatch.setattr(autospec, "RESPOSTA_IA_CACHE_MAX_ENTRADAS", 3)
    for i in range(6):
        autospec._cache_resposta_gravar(f"k{i}", {"i": i}, agora=1000.0 + i)

    with open(autospec._caminho_cache_resposta(), encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    assert len(dados) == 3
    assert set(dados) == {"k3", "k4", "k5"}, "as mais recentes é que ficam"


# =============================================================================
# D. Integração — a economia, e o que ela NÃO pode custar
# =============================================================================
def test_a_segunda_execucao_identica_NAO_chama_a_ia():
    """A economia de 100%: mesma ficha, mesmo contexto, mesmo modelo."""
    core = _core()
    core.generate_ai_response("Bomba", "KSB", "Desc", CAMPO, "contexto")
    assert len(core._llm.chamadas) == 1

    core.generate_ai_response("Bomba", "KSB", "Desc", CAMPO, "contexto")
    assert len(core._llm.chamadas) == 1, "a 2a execucao gastou token de novo"


def test_o_acerto_devolve_o_MESMO_valor_da_chamada_real():
    core = _core()
    vivo = core.generate_ai_response("Bomba", "KSB", "Desc", CAMPO, "contexto")
    do_cache = core.generate_ai_response("Bomba", "KSB", "Desc", CAMPO, "contexto")
    assert do_cache == vivo


def test_o_acerto_passa_pela_MESMA_normalizacao():
    """`ultimas_fontes_por_campo` é efeito colateral da normalização, e
    `fill_save` depende dele. Guardar o resultado já normalizado pareceria
    mais simples e perderia isto em silêncio."""
    core = _core()
    core._llm = _LLMFake(parsed={"empilhamento": {"valor": "5", "fonte": "manual.pdf"}})

    core.generate_ai_response("Bomba", "KSB", "Desc", CAMPO, "ctx")
    fontes_vivas = dict(core.ultimas_fontes_por_campo)

    core.ultimas_fontes_por_campo = {}
    core.generate_ai_response("Bomba", "KSB", "Desc", CAMPO, "ctx")
    assert core.ultimas_fontes_por_campo == fontes_vivas
    assert fontes_vivas.get("empilhamento") == "manual.pdf"


def test_o_acerto_descarta_campo_nao_pedido_igual_ao_caminho_vivo():
    core = _core()
    core._llm = _LLMFake(parsed={"empilhamento": "5", "campo_inventado": "x"})

    vivo = core.generate_ai_response("Bomba", "KSB", "Desc", CAMPO, "ctx")
    do_cache = core.generate_ai_response("Bomba", "KSB", "Desc", CAMPO, "ctx")
    assert "campo_inventado" not in vivo
    assert "campo_inventado" not in do_cache


def test_o_acerto_avisa_no_console_que_nao_gastou_token():
    """Uma ficha que volta instantânea sem explicação parece bug."""
    core = _core()
    core.generate_ai_response("Bomba", "KSB", "Desc", CAMPO, "ctx")

    cb, registro = _logs()
    core.generate_ai_response("Bomba", "KSB", "Desc", CAMPO, "ctx", callbacks=cb)
    assert any("cache" in msg.lower() for _, msg in registro)
    assert any("token" in msg.lower() for _, msg in registro)


def test_trocar_de_modelo_forca_nova_chamada():
    """Comparar dois modelos na mesma ficha é um uso REAL (é como se decide
    qual modelo usar). Servir a resposta do primeiro ao segundo tornaria a
    comparação uma mentira."""
    core_a = _core(modelo="modelo-a")
    core_a.generate_ai_response("Bomba", "KSB", "Desc", CAMPO, "ctx")

    core_b = _core(modelo="modelo-b")
    core_b.generate_ai_response("Bomba", "KSB", "Desc", CAMPO, "ctx")
    assert len(core_b._llm.chamadas) == 1, "resposta do modelo A servida ao B"


def test_contexto_diferente_forca_nova_chamada():
    """Anexar um manual novo muda o contexto — e tem de mudar a resposta."""
    core = _core()
    core.generate_ai_response("Bomba", "KSB", "Desc", CAMPO, "contexto antigo")
    core.generate_ai_response("Bomba", "KSB", "Desc", CAMPO, "contexto NOVO")
    assert len(core._llm.chamadas) == 2


def test_material_diferente_forca_nova_chamada():
    """O erro mais grave que um cache pode cometer: responder a ficha B com
    o dado da ficha A."""
    core = _core()
    core.generate_ai_response("Bomba KSB", "KSB", "Desc", CAMPO, "ctx")
    core.generate_ai_response("Valvula HYDAC", "HYDAC", "Desc", CAMPO, "ctx")
    assert len(core._llm.chamadas) == 2


def test_desligar_o_cache_faz_a_ia_responder_de_novo():
    core = _core()
    core.generate_ai_response("Bomba", "KSB", "Desc", CAMPO, "ctx")
    core.usar_cache_resposta = False
    core.generate_ai_response("Bomba", "KSB", "Desc", CAMPO, "ctx")
    assert len(core._llm.chamadas) == 2


def test_falha_da_ia_nao_vai_para_o_cache():
    """Congelar a falha faria o rerun — que é justamente o que se faz depois
    de um erro — devolver o mesmo vazio para sempre."""
    core = _core()
    core._llm = _LLMFake(excecao=RuntimeError("API fora do ar"))
    assert core.generate_ai_response("Bomba", "KSB", "Desc", CAMPO, "ctx") == {}

    core._llm = _LLMFake(parsed={"empilhamento": "5"})
    resultado = core.generate_ai_response("Bomba", "KSB", "Desc", CAMPO, "ctx")
    assert resultado == {"empilhamento": "5"}
    assert len(core._llm.chamadas) == 1, "devia ter tentado a IA de novo"


def test_sem_campo_faltante_nao_chama_ia_nem_cache():
    core = _core()
    assert core.generate_ai_response("Bomba", "KSB", "Desc", {}, "ctx") == {}
    assert core._llm.chamadas == []


# =============================================================================
# E. Privacidade — o que realmente chega ao disco
# =============================================================================
def test_o_arquivo_do_cache_nao_guarda_o_texto_do_prompt():
    """A decisão de arquitetura é mandar o mínimo para fora; guardar o
    datasheet inteiro num .json ao lado do app seria contradizê-la em casa."""
    core = _core()
    core.generate_ai_response(
        "Bomba", "KSB", "Desc", CAMPO, "SEGREDO: pressao 175 bar, projeto Itaipu"
    )
    with open(autospec._caminho_cache_resposta(), encoding="utf-8") as arquivo:
        bruto = arquivo.read()
    assert "SEGREDO" not in bruto
    assert "175 bar" not in bruto
    assert "Assistente Técnico Industrial" not in bruto, "preambulo do prompt vazou"
