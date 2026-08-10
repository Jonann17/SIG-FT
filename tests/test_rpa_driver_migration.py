r"""
Testes do Checkpoint 2.1 — migração das 6 inicializações de driver Chrome
para `create_chrome_driver` (única fábrica, `sigft/core/rpa/selenium_engine.py`).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 2 -> CP 2.1, diagnóstico
seção 1.1: "Iniciar driver Chrome (`webdriver.Chrome()` + maximize +
`WebDriverWait`) | 6×: `cria_fichas`, `lmr`, `apagar_lmr`,
`upload_conditions`, `upload_tech_specs`, `upload_ficha_duplicada`".

Escopo estrito deste checkpoint: SÓ a criação do driver mudou em cada um dos
6 métodos abaixo (`ApagarLMRAutomation.iniciar_driver`,
`LMRAutomation.iniciar_driver`, `AutomacaoPMIB.iniciar_driver`,
`UploadAutomation.iniciar`, `TechSpecsAutomation.iniciar`,
`ExtratorFichaBase.iniciar_driver_silencioso`) -- nada mais em cada classe
foi tocado (`safe_click`/`safe_send_keys`/seletores/fluxo seguem intocados).

Cada teste abaixo:
  1. substitui `create_chrome_driver` (já importado dentro do módulo do
     backend via `from sigft.core.rpa.selenium_engine import
     create_chrome_driver`) por um FAKE que grava os kwargs recebidos e
     devolve uma tupla sentinela `(driver, wait)`;
  2. chama o método de inicialização real;
  3. confirma que `self.driver`/`self.wait` foram atribuídos à tupla
     sentinela, que `wait_timeout`/`download_dir` batem EXATAMENTE com o
     valor ORIGINAL de cada classe (10/15/20 -- divergentes, nenhum foi
     unificado por este checkpoint) e que o valor de retorno do método
     (quando o original tinha `return self.driver`) é preservado.

Não usa Selenium/MagicMock nenhum para a fábrica -- só a substitui por uma
função Python pura, então roda igual com ou sem o pacote `selenium`
instalado (aqui, stubado via tests/conftest.py).
"""
import os
import pytest
from unittest.mock import patch

import apagar_lmr_backend
import cria_fichas_no_pmib_v1_backend
import lmr_backend
import upload_conditions_backend
import upload_ficha_duplicada
import upload_tech_specs_backend


def _fake_factory(chamadas, driver_sentinel, wait_sentinel):
    """Substituto de `create_chrome_driver`: grava os kwargs recebidos e
    devolve a tupla sentinela, sem tocar Selenium nenhum."""

    def _create_chrome_driver(*, wait_timeout, download_dir=None):
        chamadas.append({"wait_timeout": wait_timeout, "download_dir": download_dir})
        return driver_sentinel, wait_sentinel

    return _create_chrome_driver


def test_apagar_lmr_iniciar_driver_pede_o_engine_do_modulo_com_timeout_20():
    """CP 5.1: `apagar_lmr` é o piloto da Fase 5 e não chama mais
    `create_chrome_driver` direto -- pede o motor a `factory.criar_engine`,
    que consulta `config.RPA_ENGINE`. O que este teste continua garantindo é
    o que garantia antes: o timeout de 20s ORIGINAL da classe atravessa
    intacto (e agora vale nos dois motores)."""
    chamadas = []
    engine_sentinel = object()

    def _fake_criar_engine(modulo, *, wait_timeout=20, download_dir=None):
        chamadas.append({"modulo": modulo, "wait_timeout": wait_timeout, "download_dir": download_dir})
        return engine_sentinel

    auto = apagar_lmr_backend.ApagarLMRAutomation()

    with patch.object(apagar_lmr_backend, "criar_engine", _fake_criar_engine):
        retorno = auto.iniciar_driver()

    assert chamadas == [{"modulo": "apagar_lmr", "wait_timeout": 20, "download_dir": None}]
    assert auto.engine is engine_sentinel
    assert retorno is engine_sentinel


def test_lmr_iniciar_driver_pede_o_engine_do_modulo_com_timeout_20():
    """CP 5.2: `lmr` migrado para a fábrica de motor. O timeout de 20s
    ORIGINAL da classe continua atravessando intacto."""
    chamadas = []
    engine_sentinel = object()

    def _fake_criar_engine(modulo, *, wait_timeout=20, download_dir=None):
        chamadas.append({"modulo": modulo, "wait_timeout": wait_timeout, "download_dir": download_dir})
        return engine_sentinel

    auto = lmr_backend.LMRAutomation()

    with patch.object(lmr_backend, "criar_engine", _fake_criar_engine):
        retorno = auto.iniciar_driver()

    assert chamadas == [{"modulo": "lmr", "wait_timeout": 20, "download_dir": None}]
    assert auto.engine is engine_sentinel
    assert retorno is engine_sentinel


def test_cria_fichas_automacao_pmib_iniciar_driver_pede_o_engine_do_modulo_com_timeout_10():
    """CP 5.2/5.4: `cria_fichas` migrado por inteiro. Timeout de 10s (o único
    dos 6 pontos originais com esse valor) preservado.

    CP 5.4 tirou o `self.driver`/`self.wait` que ainda existiam para o fluxo
    de criação individual -- junto com a guarda que avisava que aquele fluxo
    só rodava em Selenium, agora desnecessária."""
    chamadas = []
    engine_sentinel = object()

    def _fake_criar_engine(modulo, *, wait_timeout=20, download_dir=None):
        chamadas.append({"modulo": modulo, "wait_timeout": wait_timeout, "download_dir": download_dir})
        return engine_sentinel

    auto = cria_fichas_no_pmib_v1_backend.AutomacaoPMIB()

    with patch.object(cria_fichas_no_pmib_v1_backend, "criar_engine", _fake_criar_engine):
        retorno = auto.iniciar_driver()

    assert chamadas == [{"modulo": "cria_fichas", "wait_timeout": 10, "download_dir": None}]
    assert auto.engine is engine_sentinel
    assert retorno is engine_sentinel
    assert not hasattr(auto, "driver"), "CP 5.4: `driver` nao existe mais nesta classe"


def test_cria_fichas_roda_o_fluxo_de_criacao_em_qualquer_motor():
    """Substitui o teste da guarda do CP 5.2.

    Aquele teste garantia que, com um motor SEM `.driver` (Playwright), a
    criação de ficha individual falhava com mensagem explicando que o fluxo
    ainda era só Selenium. O CP 5.4 portou o fluxo, então a guarda saiu -- e
    o que se garante agora é o oposto: um motor sem `.driver` roda o fluxo
    normalmente, sem AttributeError e sem a mensagem antiga.
    """
    class _EngineNeutro:
        """Sem `driver`/`wait` -- como o PlaywrightEngine."""

        def __init__(self):
            self.chamadas = []

        def __getattr__(self, nome):
            if nome in ("driver", "wait"):
                raise AttributeError(nome)

            def _registrar(*args):
                self.chamadas.append((nome, *args))
                return ""

            return _registrar

    engine = _EngineNeutro()
    auto = cria_fichas_no_pmib_v1_backend.AutomacaoPMIB()

    with patch.object(cria_fichas_no_pmib_v1_backend, "criar_engine", lambda *a, **k: engine):
        auto.iniciar_driver()

    with patch.object(cria_fichas_no_pmib_v1_backend.time, "sleep", lambda *a, **k: None):
        estado, _ = auto.processar_item_individual({"pdm_escolhido": "PDM.1234"})

    assert estado == "SUCESSO"
    # E de fato tocou o browser pelas primitivas neutras.
    nomes = {chamada[0] for chamada in engine.chamadas}
    assert {"wait_clickable", "click_raw", "digitar_no_foco", "press"} <= nomes


def test_upload_conditions_iniciar_pede_o_engine_do_modulo_com_timeout_20():
    """CP 5.3: migrado para a fabrica de motor. O timeout de 20s ORIGINAL
    da classe continua atravessando intacto, e o portal (que ja existia desde
    o `__init__`) recebe o engine."""
    chamadas = []
    engine_sentinel = object()

    def _fake_criar_engine(modulo, *, wait_timeout=20, download_dir=None):
        chamadas.append({"modulo": modulo, "wait_timeout": wait_timeout, "download_dir": download_dir})
        return engine_sentinel

    auto = upload_conditions_backend.UploadAutomation()

    with patch.object(upload_conditions_backend, "criar_engine", _fake_criar_engine):
        retorno = auto.iniciar()

    assert chamadas == [{"modulo": "upload_conditions", "wait_timeout": 20, "download_dir": None}]
    assert auto.engine is engine_sentinel
    assert auto.portal.engine is engine_sentinel
    assert retorno is engine_sentinel


def test_tech_specs_iniciar_pede_o_engine_do_modulo_com_timeout_20():
    """CP 5.3: migrado para a fabrica de motor. O timeout de 20s ORIGINAL
    da classe continua atravessando intacto, e o portal (que ja existia desde
    o `__init__`) recebe o engine."""
    chamadas = []
    engine_sentinel = object()

    def _fake_criar_engine(modulo, *, wait_timeout=20, download_dir=None):
        chamadas.append({"modulo": modulo, "wait_timeout": wait_timeout, "download_dir": download_dir})
        return engine_sentinel

    auto = upload_tech_specs_backend.TechSpecsAutomation()

    with patch.object(upload_tech_specs_backend, "criar_engine", _fake_criar_engine):
        retorno = auto.iniciar()

    assert chamadas == [{"modulo": "tech_specs", "wait_timeout": 20, "download_dir": None}]
    assert auto.engine is engine_sentinel
    assert auto.portal.engine is engine_sentinel
    assert retorno is None  # este metodo nunca teve `return`


def test_upload_ficha_duplicada_iniciar_driver_silencioso_usa_download_dir_timeout_15(tmp_path):
    # A ÚNICA das 6 classes que já passava download_dir -- preservado tal
    # qual (`self.dir_download`, resolvido para caminho absoluto pelo
    # PRÓPRIO `ExtratorFichaBase.__init__`, ANTES da fábrica).
    chamadas = []
    driver_sentinel, wait_sentinel = object(), object()
    dir_download = tmp_path / "temp_downloads"
    extrator = upload_ficha_duplicada.ExtratorFichaBase(dir_download_temp=str(dir_download))

    assert extrator.dir_download == os.path.abspath(str(dir_download))

    with patch.object(
        upload_ficha_duplicada, "create_chrome_driver",
        _fake_factory(chamadas, driver_sentinel, wait_sentinel),
    ):
        retorno = extrator.iniciar_driver_silencioso()

    assert chamadas == [{"wait_timeout": 15, "download_dir": extrator.dir_download}]
    assert extrator.driver is driver_sentinel
    assert extrator.wait is wait_sentinel
    assert retorno is driver_sentinel
