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


def test_apagar_lmr_iniciar_driver_usa_create_chrome_driver_timeout_20():
    chamadas = []
    driver_sentinel, wait_sentinel = object(), object()
    auto = apagar_lmr_backend.ApagarLMRAutomation()

    with patch.object(
        apagar_lmr_backend, "create_chrome_driver",
        _fake_factory(chamadas, driver_sentinel, wait_sentinel),
    ):
        retorno = auto.iniciar_driver()

    assert chamadas == [{"wait_timeout": 20, "download_dir": None}]
    assert auto.driver is driver_sentinel
    assert auto.wait is wait_sentinel
    assert retorno is driver_sentinel  # `return self.driver` preservado


def test_lmr_iniciar_driver_usa_create_chrome_driver_timeout_20():
    chamadas = []
    driver_sentinel, wait_sentinel = object(), object()
    auto = lmr_backend.LMRAutomation()

    with patch.object(
        lmr_backend, "create_chrome_driver",
        _fake_factory(chamadas, driver_sentinel, wait_sentinel),
    ):
        retorno = auto.iniciar_driver()

    assert chamadas == [{"wait_timeout": 20, "download_dir": None}]
    assert auto.driver is driver_sentinel
    assert auto.wait is wait_sentinel
    assert retorno is driver_sentinel


def test_cria_fichas_automacao_pmib_iniciar_driver_usa_create_chrome_driver_timeout_10():
    # O único dos 6 pontos originais com wait_timeout=10 (os outros 5 usam
    # 15 ou 20) -- classe real é `AutomacaoPMIB` (o prompt do checkpoint
    # sinalizava "DataManager?" com incerteza; confirmado lendo o arquivo).
    chamadas = []
    driver_sentinel, wait_sentinel = object(), object()
    auto = cria_fichas_no_pmib_v1_backend.AutomacaoPMIB()

    with patch.object(
        cria_fichas_no_pmib_v1_backend, "create_chrome_driver",
        _fake_factory(chamadas, driver_sentinel, wait_sentinel),
    ):
        retorno = auto.iniciar_driver()

    assert chamadas == [{"wait_timeout": 10, "download_dir": None}]
    assert auto.driver is driver_sentinel
    assert auto.wait is wait_sentinel
    assert retorno is driver_sentinel


def test_upload_conditions_iniciar_usa_create_chrome_driver_timeout_20():
    chamadas = []
    driver_sentinel, wait_sentinel = object(), object()
    auto = upload_conditions_backend.UploadAutomation()

    with patch.object(
        upload_conditions_backend, "create_chrome_driver",
        _fake_factory(chamadas, driver_sentinel, wait_sentinel),
    ):
        retorno = auto.iniciar()

    assert chamadas == [{"wait_timeout": 20, "download_dir": None}]
    assert auto.driver is driver_sentinel
    assert auto.wait is wait_sentinel
    assert retorno is driver_sentinel


def test_upload_tech_specs_iniciar_usa_create_chrome_driver_timeout_20_sem_retorno():
    # `TechSpecsAutomation.iniciar` NUNCA teve `return self.driver` no
    # original -- preservado sem retorno (None implícito).
    chamadas = []
    driver_sentinel, wait_sentinel = object(), object()
    auto = upload_tech_specs_backend.TechSpecsAutomation()

    with patch.object(
        upload_tech_specs_backend, "create_chrome_driver",
        _fake_factory(chamadas, driver_sentinel, wait_sentinel),
    ):
        retorno = auto.iniciar()

    assert chamadas == [{"wait_timeout": 20, "download_dir": None}]
    assert auto.driver is driver_sentinel
    assert auto.wait is wait_sentinel
    assert retorno is None


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
