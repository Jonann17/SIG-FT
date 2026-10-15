r"""
Testes do guard de chave de `AutoSpecCore.__init__` — pendência reaberta em
2026-08-11 (ver docs/refatoracao/PENDENCIAS.md).

O guard antigo era `if not gemini_key: raise ValueError("Chave Gemini é
obrigatória.")`, escrito quando o AutoSpec só sabia falar com o Gemini.
Depois do CP 3.2 o módulo roda por `LLMClient` e o provedor vem da seleção
do usuário — então quem tinha só `OPENROUTER_API_KEY` era barrado por falta
de uma chave que o fluxo nem usaria.

Contrato depois da correção:
  - a chave exigida é sempre a DO PROVEDOR RESOLVIDO
    (`config.CHAVE_POR_PROVIDER`); só a ORIGEM muda (Gemini vem do argumento
    `gemini_key`, os demais de `config.carregar_chaves()`);
  - a MENSAGEM é uma só, com provedor e chave interpolados -- nenhum
    provedor é caso especial no texto (decisão de 2026-08-11, olhando para
    a migração para OpenRouter: mensagem que cita "Gemini" envelhece no dia
    em que o provedor padrão mudar);
  - provedor sem chave mapeada -> não valida nada aqui, deixa `get_llm`
    levantar o `NotImplementedError` dele.

`google.generativeai` já está stubado como `MagicMock` em
`tests/conftest.py`, então `AutoSpecCore(...)` é construído normalmente.
"""
import pytest

import autospec_backend
from sigft import config


@pytest.fixture(autouse=True)
def _isola_config_file_do_cwd_real(monkeypatch, tmp_path):
    """Mesma fixture de tests/test_llm_autospec_migration.py: impede que um
    `api_config.json` real no cwd de quem roda a suíte vaze para dentro do
    `selecao.resolver()` que `AutoSpecCore.__init__` agora consulta."""
    monkeypatch.setattr(
        config, "CONFIG_FILE", str(tmp_path / "api_config_isolado_test.json")
    )


def _core(gemini_key="chave-fake-de-teste", *, chaves=None, selecao=None):
    return autospec_backend.AutoSpecCore(
        gemini_key=gemini_key,
        llama_key=None,
        google_search_key=None,
        google_cse_id=None,
        chaves=chaves,
        selecao_resolvida=selecao,
    )


def _sel(provider, model="modelo-qualquer"):
    return {"provider": provider, "model": model}


# =============================================================================
# A. Caminho Gemini — a chave do argumento continua valendo
# =============================================================================
def test_gemini_sem_chave_levanta_citando_provedor_e_chave():
    with pytest.raises(ValueError) as exc:
        _core(gemini_key="", selecao=_sel(config.PROVIDER_GEMINI))
    msg = str(exc.value)
    assert config.PROVIDER_GEMINI in msg
    assert "GEMINI" in msg


def test_mensagem_nao_trata_nenhum_provedor_como_especial():
    """A mensagem tem a MESMA forma para Gemini e para OpenRouter — só o
    provedor e o nome da chave mudam. É o que impede o texto de envelhecer
    quando o provedor padrão virar OpenRouter."""
    with pytest.raises(ValueError) as exc_gemini:
        _core(gemini_key="", selecao=_sel(config.PROVIDER_GEMINI))
    with pytest.raises(ValueError) as exc_or:
        _core(gemini_key="", chaves={}, selecao=_sel(config.PROVIDER_OPENROUTER))

    molde_gemini = str(exc_gemini.value).replace(config.PROVIDER_GEMINI, "«P»").replace("GEMINI", "«K»")
    molde_or = str(exc_or.value).replace(config.PROVIDER_OPENROUTER, "«P»").replace("OPENROUTER", "«K»")
    assert molde_gemini == molde_or


@pytest.mark.parametrize("vazio", ["", None])
def test_gemini_trata_vazio_e_none_igual(vazio):
    with pytest.raises(ValueError, match="GEMINI"):
        _core(gemini_key=vazio, selecao=_sel(config.PROVIDER_GEMINI))


def test_gemini_com_chave_constroi_normalmente():
    core = _core(gemini_key="uma-chave", selecao=_sel(config.PROVIDER_GEMINI))
    assert core.gemini_key == "uma-chave"
    assert core._llm is not None


def test_gemini_e_o_provedor_do_fallback_quando_nao_ha_selecao_salva():
    """Sem `api_config.json` (fixture aponta para caminho inexistente), a
    resolução cai em `LLM_MODELOS_HOJE["autospec"]` — que é Gemini em
    produção. É o que garante que o comportamento default não mudou."""
    assert config.LLM_MODELOS_HOJE["autospec"]["provider"] == config.PROVIDER_GEMINI
    with pytest.raises(ValueError, match="GEMINI"):
        _core(gemini_key="")


# =============================================================================
# B. O bug: outro provedor não pode mais exigir chave do Gemini
# =============================================================================
def test_openrouter_sem_chave_gemini_funciona():
    """O caso da pendência: usuário só tem OPENROUTER_API_KEY."""
    core = _core(
        gemini_key="",
        chaves={"OPENROUTER": "chave-openrouter"},
        selecao=_sel(config.PROVIDER_OPENROUTER),
    )
    assert core._llm is not None


def test_openrouter_sem_a_propria_chave_levanta_citando_openrouter():
    with pytest.raises(ValueError) as exc:
        _core(gemini_key="", chaves={}, selecao=_sel(config.PROVIDER_OPENROUTER))
    msg = str(exc.value)
    assert config.PROVIDER_OPENROUTER in msg
    assert "OPENROUTER" in msg
    assert "Gemini" not in msg  # o erro antigo não pode reaparecer aqui
    assert "GEMINI" not in msg


def test_openrouter_ignora_chave_gemini_presente_mas_inutil():
    """Ter chave do Gemini não compra acesso ao OpenRouter."""
    with pytest.raises(ValueError, match="OPENROUTER"):
        _core(
            gemini_key="chave-gemini-que-nao-serve",
            chaves={"GEMINI": "chave-gemini-que-nao-serve"},
            selecao=_sel(config.PROVIDER_OPENROUTER),
        )


def test_openai_compat_exige_a_chave_da_empresa():
    with pytest.raises(ValueError) as exc:
        _core(gemini_key="", chaves={}, selecao=_sel(config.PROVIDER_OPENAI_COMPAT))
    assert config.CHAVE_POR_PROVIDER[config.PROVIDER_OPENAI_COMPAT] in str(exc.value)


def test_openai_compat_com_chave_passa_do_guard_e_para_no_base_url():
    """Com a chave presente, o guard libera — e quem reclama passa a ser o
    `get_llm`, por falta de `EMPRESA_LLM_BASE_URL`. Prova que o guard não
    está mascarando a validação seguinte."""
    chaves = {config.CHAVE_POR_PROVIDER[config.PROVIDER_OPENAI_COMPAT]: "chave-empresa"}
    with pytest.raises(ValueError, match="EMPRESA_LLM_BASE_URL"):
        _core(gemini_key="", chaves=chaves, selecao=_sel(config.PROVIDER_OPENAI_COMPAT))


def test_provedor_sem_chave_mapeada_nao_e_barrado_pelo_guard():
    """`xai` não está em CHAVE_POR_PROVIDER. O guard não inventa erro: deixa
    o `get_llm` levantar o `NotImplementedError` dele, que é mais
    informativo (lista os provedores suportados)."""
    assert "xai" not in config.CHAVE_POR_PROVIDER
    with pytest.raises(NotImplementedError):
        _core(gemini_key="", chaves={}, selecao=_sel("xai"))


# =============================================================================
# C. Guard e cliente concordam sobre o provedor (resolução única)
# =============================================================================
def test_selecao_resolvida_uma_vez_so_e_repassada_ao_get_llm(monkeypatch):
    """`selecao.resolver` não pode ser chamado duas vezes: se o disco mudar
    entre a checagem do guard e a construção do cliente, o guard validaria a
    chave de um provedor e o cliente sairia com outro."""
    from sigft.core.llm import selecao

    chamadas = []

    def _resolver_espiao(tarefa, *, config_path=None):
        chamadas.append(tarefa)
        return {"provider": config.PROVIDER_OPENROUTER, "model": "modelo-x"}

    monkeypatch.setattr(selecao, "resolver", _resolver_espiao)

    core = _core(gemini_key="", chaves={"OPENROUTER": "chave-openrouter"})

    assert chamadas == ["autospec"], "resolver() deve ser consultado uma vez só"
    assert core._selecao_autospec["provider"] == config.PROVIDER_OPENROUTER


def test_selecao_do_usuario_vence_o_fallback():
    """Seleção salva apontando para OpenRouter faz o guard cobrar a chave do
    OpenRouter, mesmo com o fallback de produção sendo Gemini."""
    with pytest.raises(ValueError, match="OPENROUTER"):
        _core(gemini_key="", chaves={}, selecao=_sel(config.PROVIDER_OPENROUTER))


def test_chaves_injetado_nao_consulta_o_disco(monkeypatch):
    """Com `chaves` explícito, `config.carregar_chaves()` não é chamado —
    é o que torna o teste independente do ambiente de quem roda a suíte."""
    def _explode():
        raise AssertionError("carregar_chaves() não deveria ser chamado")

    monkeypatch.setattr(config, "carregar_chaves", _explode)
    core = _core(
        gemini_key="",
        chaves={"OPENROUTER": "chave-openrouter"},
        selecao=_sel(config.PROVIDER_OPENROUTER),
    )
    assert core._llm is not None


# =============================================================================
# D. A assinatura antiga continua valendo (a tela não muda)
# =============================================================================
def test_assinatura_posicional_de_hoje_continua_funcionando():
    """A tela (`sigft/app_qt/views/autospec.py`, `_novo_core`) chama com 4
    keywords e nada mais; os parâmetros novos
    são keyword-only COM default, então nenhum call site existente quebra."""
    core = autospec_backend.AutoSpecCore(
        gemini_key="uma-chave",
        llama_key=None,
        google_search_key=None,
        google_cse_id=None,
    )
    assert core._llm is not None
