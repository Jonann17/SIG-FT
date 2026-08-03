r"""
Testes do Checkpoint 5.1 — `config.get_rpa_engine` e
`sigft/core/rpa/factory.py` (`criar_engine`).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 5 -> CP 5.1: "Config
`RPA_ENGINE = "selenium" | "playwright"` por módulo (permite migração gradual
e rollback imediato)".

Esta é a peça que torna a Fase 5 reversível. O aceite de cada checkpoint da
fase é uma sessão de validação com o usuário no portal real -- que pode dar
errado. Sem um interruptor por módulo, "dar errado" viraria "reverter commit";
com ele, vira "trocar uma linha de config" (ou exportar `SIGFT_RPA_ENGINE`, sem
tocar em arquivo nenhum). Por isso o interruptor merece teste próprio.

Nenhum motor é realmente construído aqui: as duas classes concretas são
substituídas por sentinelas, então estes testes rodam sem Selenium, sem
Playwright e sem browser.
"""
from __future__ import annotations

import pytest

import sigft.core.rpa.factory as factory_mod
from sigft import config


# ===========================================================================
# config.get_rpa_engine -- resolução
# ===========================================================================
def test_modulo_mapeado_devolve_o_motor_do_mapa(monkeypatch):
    monkeypatch.setitem(config.RPA_ENGINE, "apagar_lmr", config.ENGINE_PLAYWRIGHT)
    monkeypatch.delenv(config.ENV_RPA_ENGINE, raising=False)

    assert config.get_rpa_engine("apagar_lmr") == config.ENGINE_PLAYWRIGHT


def test_modulo_ausente_do_mapa_cai_no_padrao(monkeypatch):
    monkeypatch.delenv(config.ENV_RPA_ENGINE, raising=False)

    assert config.get_rpa_engine("modulo_que_nao_existe") == config.RPA_ENGINE_PADRAO


def test_variavel_de_ambiente_vence_o_mapa(monkeypatch):
    # A alavanca de rollback imediato: vale para TODOS os módulos de uma vez.
    monkeypatch.setitem(config.RPA_ENGINE, "apagar_lmr", config.ENGINE_SELENIUM)
    monkeypatch.setenv(config.ENV_RPA_ENGINE, "playwright")

    assert config.get_rpa_engine("apagar_lmr") == config.ENGINE_PLAYWRIGHT


def test_variavel_de_ambiente_tolera_caixa_e_espaco(monkeypatch):
    monkeypatch.setenv(config.ENV_RPA_ENGINE, "  PlayWright \n")

    assert config.get_rpa_engine("apagar_lmr") == config.ENGINE_PLAYWRIGHT


def test_variavel_de_ambiente_vazia_e_ignorada(monkeypatch):
    # `set SIGFT_RPA_ENGINE=` no Windows deixa a variável vazia, não ausente.
    monkeypatch.setenv(config.ENV_RPA_ENGINE, "")
    monkeypatch.setitem(config.RPA_ENGINE, "apagar_lmr", config.ENGINE_SELENIUM)

    assert config.get_rpa_engine("apagar_lmr") == config.ENGINE_SELENIUM


def test_motor_desconhecido_levanta_em_vez_de_cair_no_padrao(monkeypatch):
    # Um `SIGFT_RPA_ENGINE=playwrigth` (typo) que silenciosamente rodasse
    # Selenium faria o usuário reportar como resultado do motor NOVO o que na
    # verdade é o antigo -- e invalidaria a sessão de validação inteira.
    monkeypatch.setenv(config.ENV_RPA_ENGINE, "playwrigth")

    with pytest.raises(ValueError) as capturado:
        config.get_rpa_engine("apagar_lmr")

    assert "playwrigth" in str(capturado.value)
    assert config.ENV_RPA_ENGINE in str(capturado.value)


def test_padrao_da_fase_5_ainda_e_selenium():
    # Trava deliberada: enquanto o CP 5.5 não descomissiona o Selenium, o
    # motor de produção continua sendo o que já roda há tempo. Se alguém
    # promover o padrão sem passar pela validação de cada módulo, este teste
    # obriga a decisão a ser explícita.
    assert config.RPA_ENGINE_PADRAO == config.ENGINE_SELENIUM


def test_todo_modulo_do_mapa_tem_motor_valido():
    for modulo, motor in config.RPA_ENGINE.items():
        assert motor in (config.ENGINE_SELENIUM, config.ENGINE_PLAYWRIGHT), modulo


def test_o_mapa_cobre_os_seis_modulos_de_rpa():
    # Os 6 pontos de criação de driver levantados no diagnóstico (seção 1.1).
    assert set(config.RPA_ENGINE) == {
        "apagar_lmr",
        "lmr",
        "cria_fichas",
        "upload_conditions",
        "tech_specs",
        "ficha_duplicada",
    }


# ===========================================================================
# factory.criar_engine -- despacho
# ===========================================================================
class _EngineFalso:
    def __init__(self, marca, **kwargs):
        self.marca = marca
        self.kwargs = kwargs


def _interceptar(monkeypatch, marca):
    """Substitui a classe concreta que `criar_engine` importaria, no módulo
    de origem -- o import dentro da função resolve pelo `sys.modules`, então
    trocar o atributo lá basta."""
    criados = []

    def _criar(**kwargs):
        engine = _EngineFalso(marca, **kwargs)
        criados.append(engine)
        return engine

    if marca == "selenium":
        import sigft.core.rpa.selenium_engine as se

        monkeypatch.setattr(se.SeleniumEngine, "create", staticmethod(_criar))
    else:
        import sigft.core.rpa.playwright_engine as pe

        monkeypatch.setattr(pe.PlaywrightEngine, "criar", staticmethod(_criar))
    return criados


def test_criar_engine_sobe_selenium_quando_configurado(monkeypatch):
    monkeypatch.delenv(config.ENV_RPA_ENGINE, raising=False)
    monkeypatch.setitem(config.RPA_ENGINE, "apagar_lmr", config.ENGINE_SELENIUM)
    criados = _interceptar(monkeypatch, "selenium")

    engine = factory_mod.criar_engine("apagar_lmr", wait_timeout=20)

    assert engine.marca == "selenium"
    assert criados[0].kwargs == {"wait_timeout": 20, "download_dir": None}


def test_criar_engine_sobe_playwright_quando_configurado(monkeypatch):
    monkeypatch.delenv(config.ENV_RPA_ENGINE, raising=False)
    monkeypatch.setitem(config.RPA_ENGINE, "apagar_lmr", config.ENGINE_PLAYWRIGHT)
    criados = _interceptar(monkeypatch, "playwright")

    engine = factory_mod.criar_engine("apagar_lmr", wait_timeout=20)

    assert engine.marca == "playwright"
    assert criados[0].kwargs == {"wait_timeout": 20, "download_dir": None}


def test_criar_engine_repassa_timeout_e_download_dir_aos_dois_motores(monkeypatch):
    monkeypatch.delenv(config.ENV_RPA_ENGINE, raising=False)

    for marca, valor in (("selenium", config.ENGINE_SELENIUM), ("playwright", config.ENGINE_PLAYWRIGHT)):
        monkeypatch.setitem(config.RPA_ENGINE, "ficha_duplicada", valor)
        criados = _interceptar(monkeypatch, marca)

        factory_mod.criar_engine("ficha_duplicada", wait_timeout=15, download_dir="/tmp/dl")

        assert criados[0].kwargs == {"wait_timeout": 15, "download_dir": "/tmp/dl"}, marca


def test_criar_engine_respeita_a_variavel_de_ambiente(monkeypatch):
    # Rollback imediato de ponta a ponta: o mapa diz Playwright, a variável
    # diz Selenium, e é o Selenium que sobe.
    monkeypatch.setitem(config.RPA_ENGINE, "apagar_lmr", config.ENGINE_PLAYWRIGHT)
    monkeypatch.setenv(config.ENV_RPA_ENGINE, "selenium")
    _interceptar(monkeypatch, "selenium")

    assert factory_mod.criar_engine("apagar_lmr").marca == "selenium"


def test_criar_engine_propaga_o_erro_de_motor_desconhecido(monkeypatch):
    monkeypatch.setenv(config.ENV_RPA_ENGINE, "chrome")

    with pytest.raises(ValueError):
        factory_mod.criar_engine("apagar_lmr")
