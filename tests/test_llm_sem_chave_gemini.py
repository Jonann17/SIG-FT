"""[2026-11-05] Sem escolha salva e sem a chave do Gemini, o padrão vai pelo
OpenRouter quando a chave dele está posta (pedido do Luan)."""
from sigft import config
from sigft.core.llm.client import _padrao_pela_chave

GEMINI = {"provider": config.PROVIDER_GEMINI, "model": "gemini-3-flash-preview"}


def test_sem_gemini_com_openrouter_vai_pelo_openrouter():
    cfg = _padrao_pela_chave(GEMINI, "", {"GEMINI": None, "OPENROUTER": "sk-or"})
    assert cfg == {"provider": config.PROVIDER_OPENROUTER, "model": "google/gemini-3-flash-preview"}


def test_com_a_chave_do_gemini_nada_muda():
    assert _padrao_pela_chave(GEMINI, "AIza", {"OPENROUTER": "sk-or"}) is GEMINI
    assert _padrao_pela_chave(GEMINI, None, {"GEMINI": "AIza", "OPENROUTER": "sk-or"}) is GEMINI


def test_sem_chave_nenhuma_fica_o_de_sempre():
    assert _padrao_pela_chave(GEMINI, "", {"GEMINI": None, "OPENROUTER": None}) is GEMINI


def test_outro_provedor_nao_e_tocado():
    outro = {"provider": config.PROVIDER_OPENROUTER, "model": "x/y"}
    assert _padrao_pela_chave(outro, "", {}) is outro
