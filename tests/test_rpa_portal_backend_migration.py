r"""
Testes do Checkpoint 2.2 — migração dos 6 backends de automação para
`PMIBPortal` (ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 2 -> CP 2.2).

Escopo destes testes (mesmo escopo definido pela especificação do
checkpoint — "sem tentar exercitar o fluxo Selenium completo"):

  1. RESOLUÇÃO de `self.portal`: depois de `iniciar_driver()`/`iniciar()`
     (com `create_chrome_driver` substituído por um fake, mesmo padrão de
     tests/test_rpa_driver_migration.py), `self.portal` é uma instância de
     `PMIBPortal` cujo `.engine` é um `SeleniumEngine` sobre os MESMOS
     `driver`/`wait` sentinela devolvidos pela fábrica fake.
  2. DELEGAÇÃO: os métodos delegadores (`safe_click`/`safe_send_keys`/
     `check_or_uncheck`/`_pesquisar_e_abrir`/etc.) chamam `self.portal` com
     o argumento CERTO -- em especial, a string XPath extraída da tupla
     `(By.XPATH, xpath)` que os call sites internos ainda usam, e os
     overrides de seletor exatos de `pesquisar_e_abrir` por módulo. Um
     `_PortalEspiao` duck-typed (nunca `PMIBPortal`/Selenium reais) grava
     as chamadas recebidas.

Não tenta reproduzir o fluxo Selenium real (scroll/clique/paginação/etc.) --
isso já é coberto, para a MECÂNICA em si, por tests/test_portal.py
(`PMIBPortal` isolado) e tests/test_selenium_engine.py (`SeleniumEngine`
isolado).
"""
from unittest.mock import patch

import pytest

import apagar_lmr_backend
import cria_fichas_no_pmib_v1_backend
import lmr_backend
import upload_conditions_backend
import upload_tech_specs_backend
from sigft import config
from sigft.core.callbacks import UICallbacks
from sigft.core.rpa.portal import PMIBPortal


@pytest.fixture(autouse=True)
def _isola_config_file_do_cwd_real(monkeypatch, tmp_path):
    """CP 3.3 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.3):
    `ConditionsProcessor.__init__`/`TechSpecsProcessor.__init__` (abaixo)
    chamam `get_llm()`, que agora consulta `config.CONFIG_FILE` -- isola
    estes testes de um `api_config.json` REAL que porventura exista no cwd
    de quem roda a suíte (com uma seleção apontando para um provider não
    implementado, por exemplo, o que faria a construção destas 2 classes
    levantar `NotImplementedError` em vez de só testar o wiring do
    `PMIBPortal`, que é o que este arquivo cobre)."""
    monkeypatch.setattr(config, "CONFIG_FILE", str(tmp_path / "api_config_isolado_test.json"))


def _fake_factory(chamadas, driver_sentinel, wait_sentinel):
    """Mesmo fake de tests/test_rpa_driver_migration.py: substitui
    `create_chrome_driver` sem tocar Selenium nenhum."""

    def _create_chrome_driver(*, wait_timeout, download_dir=None):
        chamadas.append({"wait_timeout": wait_timeout, "download_dir": download_dir})
        return driver_sentinel, wait_sentinel

    return _create_chrome_driver


class _PortalEspiao:
    """Duck-typed -- grava toda chamada recebida, nunca levanta (a não ser
    que o teste configure `pesquisar_e_abrir_retorno` como uma exceção, o
    que nenhum teste faz aqui)."""

    def __init__(self, pesquisar_e_abrir_retorno=True):
        self.safe_click_chamadas = []
        self.safe_fill_chamadas = []
        self.check_or_uncheck_chamadas = []
        self.pesquisar_e_abrir_chamadas = []
        self.excluir_linha_chamadas = []
        self.pesquisar_e_abrir_retorno = pesquisar_e_abrir_retorno

    def safe_click(self, seletor):
        self.safe_click_chamadas.append(seletor)

    def safe_fill(self, seletor, texto):
        self.safe_fill_chamadas.append((seletor, texto))

    def check_or_uncheck(self, seletor, should_check):
        self.check_or_uncheck_chamadas.append((seletor, should_check))

    def excluir_linha_com_confirmacao(self, row):
        self.excluir_linha_chamadas.append(row)
        return True

    def pesquisar_e_abrir(self, pmib, **kwargs):
        self.pesquisar_e_abrir_chamadas.append((pmib, kwargs))
        return self.pesquisar_e_abrir_retorno

    def deve_parar(self):
        return False


# ===========================================================================
# 1. Resolução de self.portal após iniciar_driver()/iniciar() -- os 6 pontos
#    de criação já migrados no CP 2.1 (mesmos 6 de
#    tests/test_rpa_driver_migration.py).
# ===========================================================================
class _EngineFalso:
    """CP 5.2: substitui o par `_FakeDriverComGet`/`_WaitQueLevantaAoUsar`.
    `goto` registra a URL (é como o serviço volta para a home depois de um
    ERRO FATAL); qualquer outra primitiva levanta `erro`, o que faz o fluxo
    parar no ponto observado por cada teste."""

    def __init__(self, erro=None):
        self.urls = []
        self._erro = erro or RuntimeError("engine falso: primitiva não configurada")

    def goto(self, url):
        self.urls.append(url)

    def __getattr__(self, nome):
        def _levanta(*_a, **_kw):
            raise self._erro
        return _levanta


def test_apagar_lmr_iniciar_driver_resolve_portal_sobre_o_engine_da_fabrica():
    """CP 5.1: o piloto da Fase 5 monta o `PMIBPortal` sobre o motor que a
    fábrica devolver -- Selenium ou Playwright, conforme `config.RPA_ENGINE`.
    O que se garante aqui é o mesmo de antes: o portal fica sobre EXATAMENTE
    o motor criado, sem construir um segundo browser por baixo."""
    engine_sentinel = object()
    auto = apagar_lmr_backend.ApagarLMRAutomation()

    with patch.object(apagar_lmr_backend, "criar_engine", lambda *a, **k: engine_sentinel):
        auto.iniciar_driver()

    assert isinstance(auto.portal, PMIBPortal)
    assert auto.portal.engine is engine_sentinel


def test_lmr_iniciar_driver_resolve_portal_sobre_o_engine_da_fabrica():
    """CP 5.2: `lmr` migrado -- pede o motor a `criar_engine("lmr")` e monta o
    portal sobre ele, sem construir um segundo browser por baixo."""
    engine_sentinel = object()
    auto = lmr_backend.LMRAutomation()

    with patch.object(lmr_backend, "criar_engine", lambda *a, **k: engine_sentinel):
        auto.iniciar_driver()

    assert isinstance(auto.portal, PMIBPortal)
    assert auto.portal.engine is engine_sentinel


def test_cria_fichas_automacao_pmib_iniciar_driver_resolve_portal():
    """CP 5.2: o portal é montado sobre o motor que a fábrica devolver."""
    engine_sentinel = object()
    auto = cria_fichas_no_pmib_v1_backend.AutomacaoPMIB()

    with patch.object(cria_fichas_no_pmib_v1_backend, "criar_engine", lambda *a, **k: engine_sentinel):
        auto.iniciar_driver()

    assert isinstance(auto.portal, PMIBPortal)
    assert auto.portal.engine is engine_sentinel


def test_upload_conditions_iniciar_anexa_engine_a_portal_ja_existente_desde_init():
    """CP 5.3: o portal ja existe desde o `__init__` (por causa da stop-flag);
    `iniciar()` so anexa a ele o motor que a fabrica devolver -- sem trocar a
    INSTANCIA do portal, senao a flag de parada ja setada se perderia."""
    engine_sentinel = object()
    auto = upload_conditions_backend.UploadAutomation()
    portal_antes = auto.portal

    with patch.object(upload_conditions_backend, "criar_engine", lambda *a, **k: engine_sentinel):
        auto.iniciar()

    assert auto.portal is portal_antes  # MESMA instancia
    assert auto.portal.engine is engine_sentinel


def test_upload_conditions_solicitar_parada_funciona_antes_de_iniciar():
    # Cenário real citado no código: o botão "Parar" do frontend pode
    # disparar entre a atribuição da instância a `self.automacao_ativa` e a
    # thread de trabalho chegar a `iniciar()` -- `solicitar_parada()` NUNCA
    # pode levantar AttributeError nesse meio-tempo.
    auto = upload_conditions_backend.UploadAutomation()
    auto.solicitar_parada()  # não levanta, mesmo sem engine
    assert auto.portal.deve_parar() is True


def test_upload_tech_specs_iniciar_anexa_engine_a_portal_ja_existente_desde_init():
    """CP 5.3: o portal ja existe desde o `__init__` (por causa da stop-flag);
    `iniciar()` so anexa a ele o motor que a fabrica devolver -- sem trocar a
    INSTANCIA do portal, senao a flag de parada ja setada se perderia."""
    engine_sentinel = object()
    auto = upload_tech_specs_backend.TechSpecsAutomation()
    portal_antes = auto.portal

    with patch.object(upload_tech_specs_backend, "criar_engine", lambda *a, **k: engine_sentinel):
        auto.iniciar()

    assert auto.portal is portal_antes  # MESMA instancia
    assert auto.portal.engine is engine_sentinel


def test_upload_tech_specs_solicitar_parada_funciona_antes_de_iniciar():
    auto = upload_tech_specs_backend.TechSpecsAutomation()
    auto.solicitar_parada()
    assert auto.portal.deve_parar() is True


def test_conditions_processor_e_tech_specs_processor_tem_stop_flag_sem_engine():
    # As 2 classes de IA (sem driver/browser nenhum) -- stop-flag via
    # PMIBPortal() sem engine.
    proc1 = upload_conditions_backend.ConditionsProcessor(api_key="")
    assert isinstance(proc1.portal, PMIBPortal)
    assert proc1.portal.engine is None
    proc1.solicitar_parada()
    assert proc1.portal.deve_parar() is True

    proc2 = upload_tech_specs_backend.TechSpecsProcessor(api_key="")
    assert isinstance(proc2.portal, PMIBPortal)
    assert proc2.portal.engine is None
    proc2.solicitar_parada()
    assert proc2.portal.deve_parar() is True


# ===========================================================================
# 2. Delegação -- métodos delegadores chamam self.portal com o argumento
#    certo (string XPath extraída da tupla).
# ===========================================================================
def test_apagar_lmr_safe_click_extrai_xpath_da_tupla_e_delega():
    auto = apagar_lmr_backend.ApagarLMRAutomation()
    espiao = _PortalEspiao()
    auto.portal = espiao

    # CP 5.1: `By` saiu dos imports de `apagar_lmr` (o piloto não fala mais
    # Selenium). O delegador continua aceitando a tupla `(By, xpath)` que os
    # call sites internos usam -- só o 1º elemento é ignorado, então qualquer
    # sentinela serve para o teste.
    auto.safe_click(("xpath", "//button[@id='x']"))

    assert espiao.safe_click_chamadas == ["//button[@id='x']"]


def test_upload_conditions_safe_click_e_safe_send_keys_e_check_or_uncheck_delegam():
    auto = upload_conditions_backend.UploadAutomation()
    espiao = _PortalEspiao()
    auto.portal = espiao

    auto.safe_click("//a[@id='y']")
    auto.safe_send_keys("//textarea[@id='z']", "valor")
    auto.check_or_uncheck("//input[@id='c']", True)

    assert espiao.safe_click_chamadas == ["//a[@id='y']"]
    assert espiao.safe_fill_chamadas == [("//textarea[@id='z']", "valor")]
    assert espiao.check_or_uncheck_chamadas == [("//input[@id='c']", True)]


def test_upload_tech_specs_safe_click_delega():
    auto = upload_tech_specs_backend.TechSpecsAutomation()
    espiao = _PortalEspiao()
    auto.portal = espiao

    auto.safe_click("//button[@id='salvar']")

    assert espiao.safe_click_chamadas == ["//button[@id='salvar']"]


# ===========================================================================
# 3. _pesquisar_e_abrir -- overrides de seletor exatos por módulo + adaptação
#    do retorno bool do portal para o contrato de cada classe.
# ===========================================================================
def test_apagar_lmr_pesquisar_e_abrir_usa_defaults_do_portal_e_adapta_retorno_para_tupla():
    auto = apagar_lmr_backend.ApagarLMRAutomation()
    espiao = _PortalEspiao(pesquisar_e_abrir_retorno=True)
    auto.portal = espiao

    sucesso, msg = auto._pesquisar_e_abrir("4500063671.1234")

    assert sucesso is True
    assert msg == "Ficha aberta."
    assert espiao.pesquisar_e_abrir_chamadas == [("4500063671.1234", {})]  # sem overrides -- defaults do portal


def test_apagar_lmr_pesquisar_e_abrir_falha_adapta_retorno_para_tupla_de_erro():
    auto = apagar_lmr_backend.ApagarLMRAutomation()
    auto.portal = _PortalEspiao(pesquisar_e_abrir_retorno=False)

    sucesso, msg = auto._pesquisar_e_abrir("999")

    assert sucesso is False
    assert "999" in msg


def test_upload_tech_specs_pesquisar_e_abrir_delega_direto_bool():
    auto = upload_tech_specs_backend.TechSpecsAutomation()
    espiao = _PortalEspiao(pesquisar_e_abrir_retorno=True)
    auto.portal = espiao

    assert auto._pesquisar_e_abrir("123") is True
    assert espiao.pesquisar_e_abrir_chamadas == [("123", {})]

    espiao.pesquisar_e_abrir_retorno = False
    assert auto._pesquisar_e_abrir("123") is False


def test_upload_conditions_processar_lista_chama_pesquisar_e_abrir_com_overrides_exatos():
    # Seletores EXATOS de upload_conditions -- placeholder completo do campo
    # de busca + ícone `fa-pencil-square-o` (diferente de `fa-pencil`).
    auto = upload_conditions_backend.UploadAutomation()
    espiao = _PortalEspiao(pesquisar_e_abrir_retorno=True)
    auto.portal = espiao
    auto.driver = _DriverQueNuncaEChamado()
    auto.wait = _DriverQueNuncaEChamado()

    ficha = {
        "pmib_codigo": "4500063671.5555",
        "dimensoes": {"comprimento": "", "largura": "", "altura": ""},
        "controle_temperatura": {"necessidade": "NÃO"},
        "nocivo": {"status": ""},
        "peso": {"liquido": "", "bruto": ""},
        "outros_cuidados": {"status": ""},
    }

    auto.processar_lista([ficha], caminho_status="")

    assert len(espiao.pesquisar_e_abrir_chamadas) == 1
    pmib_chamado, kwargs = espiao.pesquisar_e_abrir_chamadas[0]
    assert pmib_chamado == "4500063671.5555"
    assert kwargs["busca_xpath"] == (
        "//input[@placeholder='Código, Nome ES/PT pela Ficha Técnica, "
        "Código do projeto e/ou contrato']"
    )
    assert kwargs["lapis_xpath_template"] == (
        "//span[text()='{pmib}']/ancestor::tr//a[.//i[contains(@class, 'fa-pencil-square-o')]]"
    )


# ===========================================================================
# 4. lmr -- EXCEÇÃO AUTORIZADA (24 TABs substituídos por pesquisar_e_abrir).
# ===========================================================================
class _DriverQueNuncaEChamado:
    """Duck-typed -- qualquer atributo/chamada usada É um erro de teste
    (usado para garantir que o caminho de FALHA de `processar_lista` não
    toca `self.wait` nenhuma vez -- só `self.driver.get(...)`, coberto por
    `_FakeDriverComGet` abaixo)."""

    def __getattr__(self, nome):
        raise AssertionError(f"self.wait não deveria ser tocado neste cenário (acesso a {nome!r})")


class _FakeDriverComGet:
    def __init__(self):
        self.get_chamadas = []

    def get(self, url):
        self.get_chamadas.append(url)


def test_lmr_processar_lista_chama_pesquisar_e_abrir_com_defaults():
    # CP 5.2: `self.driver`/`self.wait` deram lugar a `self.engine`. O engine
    # falso abaixo levanta em QUALQUER primitiva de interação -- assim o fluxo
    # para logo depois da pesquisa, que é o que este teste observa.
    auto = lmr_backend.LMRAutomation()
    espiao = _PortalEspiao(pesquisar_e_abrir_retorno=False)
    auto.portal = espiao
    auto.engine = _EngineFalso()

    logs = []
    perguntas = []
    callbacks = UICallbacks(log=logs.append, ask=lambda *a, **k: perguntas.append((a, k)) or True)

    auto.processar_lista(["4500063671.1111"], df_completo=None, callbacks=callbacks)

    assert espiao.pesquisar_e_abrir_chamadas == [("4500063671.1111", {})]  # sem overrides -- defaults
    # Caminho de falha: RuntimeError interno -> "ERRO FATAL" -> ask -> tenta
    # recarregar a home pelo engine.
    assert any("ERRO FATAL" in msg for msg in logs)
    assert len(perguntas) == 1
    assert auto.engine.urls == [auto.url_inicial]


def test_lmr_processar_lista_sucesso_nao_levanta_erro_fatal():
    # Sucesso na pesquisa: o próximo passo real (clicar na aba LMR) usa o
    # engine -- aqui verificamos só que a falha NÃO é reportada quando
    # pesquisar_e_abrir tem sucesso (o clique da aba pode falhar com uma
    # exceção sintética, que cai no MESMO except genérico -- não é o foco
    # deste teste, só confirma que o RuntimeError do CP 2.2 não é levantado
    # indevidamente em caso de sucesso).
    auto = lmr_backend.LMRAutomation()
    espiao = _PortalEspiao(pesquisar_e_abrir_retorno=True)
    auto.portal = espiao
    auto.engine = _EngineFalso(erro=RuntimeError("aba LMR não encontrada (esperado neste teste sintético)"))

    logs = []
    callbacks = UICallbacks(log=logs.append, ask=lambda *a, **k: True)

    auto.processar_lista(["4500063671.2222"], df_completo=None, callbacks=callbacks)

    assert espiao.pesquisar_e_abrir_chamadas == [("4500063671.2222", {})]
    # A falha reportada é a da aba LMR (RuntimeError sintético do teste), não
    # "Não foi possível pesquisar/abrir" -- prova que pesquisar_e_abrir teve
    # sucesso e o fluxo prosseguiu.
    msgs_erro = [m for m in logs if "ERRO FATAL" in m]
    assert len(msgs_erro) == 1
    assert "não encontrada (esperado neste teste sintético)" in msgs_erro[0]
