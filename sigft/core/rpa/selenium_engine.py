r"""
sigft/core/rpa/selenium_engine.py — fábrica de driver Chrome + implementação
Selenium de `RPAEngine` (Checkpoint 2.1 do plano de refatoração).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 2 -> CP 2.1, diagnóstico
seção 1.1: "Iniciar driver Chrome (`webdriver.Chrome()` + maximize +
`WebDriverWait`) | 6×: `cria_fichas`, `lmr`, `apagar_lmr`,
`upload_conditions`, `upload_tech_specs`, `upload_ficha_duplicada`" e
"`safe_click` (scroll + JS click) | 4× idêntico: `apagar_lmr`,
`upload_conditions`, `upload_tech_specs`, `upload_ficha_duplicada`" /
"`safe_send_keys` (Ctrl+A, Backspace, digitar) | 3 variantes".

Duas entregas SEPARADAS neste módulo (ver especificação do CP 2.1):

  1. `create_chrome_driver(*, wait_timeout=20, download_dir=None)` -- fábrica
     de BAIXO NÍVEL que replica EXATAMENTE o que os 6 pontos de criação
     faziam antes deste checkpoint: `webdriver.Chrome(...)` (com
     `options`/`prefs` de download automático SÓ quando `download_dir` é
     passado -- mecânica idêntica à de
     `upload_ficha_duplicada.ExtratorFichaBase.iniciar_driver_silencioso`,
     a ÚNICA das 6 que já usava download automático até este checkpoint) +
     `.maximize_window()` + `WebDriverWait(driver, wait_timeout)`. É o que
     os 6 call sites migrados neste checkpoint passam a chamar, preservando
     `self.driver`/`self.wait` -- e, portanto, TODO O RESTO de cada classe
     (dezenas de outros usos de `self.driver`/`self.wait`, incluindo os
     próprios `safe_click`/`safe_send_keys` de cada backend) continua
     funcionando SEM NENHUMA mudança. A migração desses OUTROS usos para
     `SeleniumEngine`/`PMIBPortal` é trabalho do CP 2.2, fora do escopo
     aqui -- ver docs/refatoracao/PENDENCIAS.md.

  2. `SeleniumEngine(RPAEngine)` -- implementação completa da interface de
     `engine.py`, recebendo um `driver`/`wait` JÁ CRIADOS (injetáveis, para
     testabilidade -- ver abaixo). Usa internamente a mecânica CANÔNICA de
     `safe_click`/`safe_send_keys` (idêntica nas 4/3 cópias hoje espalhadas
     pelos backends -- ver diagnóstico acima), fixando `By.XPATH` já que o
     `seletor` de `RPAEngine` é sempre uma string XPath (ver docstring de
     `engine.py`). `SeleniumEngine.create(...)` combina a fábrica de baixo
     nível + a construção do engine num só passo, para conveniência de quem
     for consumir isto no CP 2.2. NENHUM consumidor de `SeleniumEngine`
     existe neste checkpoint -- só a classe é construída e testada; os 6
     backends continuam usando `self.driver`/`self.wait` crus, como sempre.

Decisões de design NÃO especificadas literalmente pelo checkpoint (por
transparência/reprodutibilidade -- ver docs/refatoracao/PENDENCIAS.md):
  - `click`/`fill` (mecânica de `safe_click`/`safe_send_keys`) preservam o
    `except Exception: pass` da mecânica canônica -- comportamento IDÊNTICO
    ao que já existe hoje nos 4/3 lugares que a inspiram.
  - `wait_visible`/`wait_clickable` e `get_value` NÃO engolem exceção:
    propagam (ex.: `TimeoutException`) para quem chamou -- necessário
    porque `apagar_lmr_backend`/`upload_tech_specs_backend` dependem HOJE
    de capturar `TimeoutException` de uma espera para decidir fim de loop
    (ver docs/base-conhecimento/10-apagar-lmr-backend.md: "TimeoutException
    é esperado e indica sucesso (fim do loop)"); se essas esperas
    engolissem a exceção silenciosamente aqui, esse padrão ficaria
    impossível de portar nos CP 2.2/2.3.
  - `element_exists(seletor)` é uma checagem IMEDIATA via
    `driver.find_elements(...)` (nunca espera) -- ver docstring de
    `engine.py`.
  - `screenshot(caminho)` usa `driver.save_screenshot(caminho)` (API padrão
    do Selenium; nenhuma das 6 classes tem hoje um método de screenshot --
    capacidade NOVA, prevista pelo próprio CP 2.1 e citada na matriz de
    riscos do plano: "Playwright trace/screenshot em falha ajuda
    diagnóstico").
  - `set_download_dir(caminho)` usa o comando Chrome DevTools Protocol
    `Page.setDownloadBehavior` via `driver.execute_cdp_cmd(...)` -- a forma
    padrão de trocar a pasta de download de uma sessão Chrome JÁ ABERTA
    (diferente do parâmetro `download_dir=` de `create_chrome_driver`, que
    só configura a pasta ANTES do Chrome abrir, via `ChromeOptions`/prefs).

Testabilidade (ver especificação do CP 2.1): `driver`/`wait` são
DUCK-TYPED e injetáveis -- os testes usam fakes Python simples, não
Selenium real (que está stubado como `MagicMock` em `tests/conftest.py`;
chamar métodos de um `MagicMock` nunca falha, mas também não verifica
lógica real). Um `wait` FALSO cujo `.until(condicao)` devolve um elemento
falso pré-configurado, IGNORANDO a condição real do Selenium, é suficiente
para testar a MECÂNICA que é NOSSA (ordem de `execute_script`, argumentos,
sequência de `send_keys`) sem depender da integração real de `EC`/`By` --
ver tests/test_selenium_engine.py. `create_chrome_driver` é testável de
verdade neste ambiente porque `webdriver`/`WebDriverWait` já são
`MagicMock`s (via conftest.py): a função real roda sem lançar navegador
nenhum, só invocando métodos mockados -- dá para verificar a LÓGICA da
fábrica (quando `options`/prefs são montados, o que é passado para
`webdriver.Chrome`/`WebDriverWait`).
"""

from __future__ import annotations

import time
from contextlib import contextmanager

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from sigft.core.rpa.engine import (
    ElementoObsoleto,
    RPAEngine,
    TempoEsgotado,
)

# Nome da classe de exceção do Selenium -> exceção NEUTRA de `engine.py`
# (CP 5.1). Só as falhas que algum laço de produção DISCRIMINA POR TIPO
# entram aqui (ver o comentário sobre exceções neutras em `engine.py`);
# qualquer outra sobe como veio, preservando o diagnóstico original.
_TRADUCAO_POR_NOME = {
    "TimeoutException": TempoEsgotado,
    "StaleElementReferenceException": ElementoObsoleto,
}


def _traduzir(excecao: BaseException) -> BaseException:
    """Converte uma exceção do SDK do Selenium na exceção neutra equivalente.

    O casamento é pelo NOME da classe ao longo da MRO, não por `isinstance`,
    de propósito. Duas razões, nesta ordem:

      1. `tests/conftest.py` stuba `selenium` inteiro com `MagicMock` -- e
         `selenium.common.exceptions.TimeoutException` vira então um
         MagicMock, não uma classe. `isinstance(e, <MagicMock>)` levanta
         `TypeError: isinstance() arg 2 must be a type`, ou seja: a tradução
         quebraria justamente no ambiente onde ela é testada.
      2. Não é preciso importar `selenium.common.exceptions` aqui só para
         comparar tipos.

    Percorrer a MRO (não só `type(e).__name__`) faz subclasses das exceções
    do Selenium traduzirem igual às classes-base.
    """
    for classe in type(excecao).__mro__:
        neutra = _TRADUCAO_POR_NOME.get(classe.__name__)
        if neutra is not None:
            return neutra(str(excecao) or classe.__name__)
    return excecao


@contextmanager
def _traduzindo():
    """Roda o bloco e, se ele falhar, relança a exceção já traduzida.

    `raise ... from excecao` preserva a exceção do Selenium encadeada
    (`__cause__`): o consumidor decide o fluxo pelo tipo NEUTRO, mas o
    traceback continua mostrando qual falha do SDK originou tudo.
    """
    try:
        yield
    except BaseException as excecao:  # noqa: BLE001 -- relançamos sempre
        traduzida = _traduzir(excecao)
        if traduzida is excecao:
            raise
        raise traduzida from excecao


def create_chrome_driver(*, wait_timeout: int = 20, download_dir: str | None = None):
    """Fábrica de baixo nível: cria e devolve `(driver, wait)` -- substitui
    as 6 inicializações de driver do diagnóstico (ver docstring do módulo).

    Reproduz EXATAMENTE o comportamento de hoje:
      - sem `download_dir` (5 dos 6 pontos originais -- `apagar_lmr`, `lmr`,
        `cria_fichas`, `upload_conditions`, `upload_tech_specs`):
        `webdriver.Chrome()` sem nenhum argumento.
      - com `download_dir` (só `ExtratorFichaBase.iniciar_driver_silencioso`,
        em `upload_ficha_duplicada.py`, até este checkpoint):
        `webdriver.ChromeOptions()` com os 4 prefs de download automático
        (`download.default_directory`, `download.prompt_for_download=False`,
        `download.directory_upgrade=True`, `safebrowsing.enabled=True`),
        passado como `options=` para `webdriver.Chrome`.
    Em ambos os casos, na sequência: `.maximize_window()` e
    `WebDriverWait(driver, wait_timeout)`.

    `wait_timeout` preserva o valor ORIGINAL de cada um dos 6 call sites
    (10, 15 ou 20 -- DIVERGEM entre si; nenhum é unificado por este
    checkpoint -- ver call sites migrados nos 6 backends).
    """
    if download_dir:
        options = webdriver.ChromeOptions()
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        }
        options.add_experimental_option("prefs", prefs)
        driver = webdriver.Chrome(options=options)
    else:
        driver = webdriver.Chrome()

    driver.maximize_window()
    wait = WebDriverWait(driver, wait_timeout)
    return driver, wait


class SeleniumEngine(RPAEngine):
    """Implementação de `RPAEngine` sobre Selenium -- ver docstring do
    módulo para o racional de cada decisão de design."""

    def __init__(self, driver, wait) -> None:
        self.driver = driver
        self.wait = wait

    @classmethod
    def create(cls, *, wait_timeout: int = 20, download_dir: str | None = None) -> "SeleniumEngine":
        """Conveniência: `create_chrome_driver(...)` + construção do engine
        num só passo. Consumido a partir do CP 2.2 -- nenhum call site de
        produção usa isto ainda neste checkpoint."""
        driver, wait = create_chrome_driver(wait_timeout=wait_timeout, download_dir=download_dir)
        return cls(driver, wait)

    # -- Navegação -----------------------------------------------------
    def goto(self, url: str) -> None:
        self.driver.get(url)

    # -- Interação (mecânica canônica de safe_click/safe_send_keys) ----
    def click(self, seletor: str) -> None:
        locator = (By.XPATH, seletor)
        try:
            el = self.wait.until(EC.presence_of_element_located(locator))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
            time.sleep(0.5)
            self.wait.until(EC.element_to_be_clickable(locator))
            self.driver.execute_script("arguments[0].click();", el)
        except Exception:
            pass

    def fill(self, seletor: str, texto: str) -> None:
        locator = (By.XPATH, seletor)
        try:
            el = self.wait.until(EC.presence_of_element_located(locator))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
            time.sleep(0.5)
            self.wait.until(EC.visibility_of_element_located(locator))
            self.driver.execute_script("arguments[0].click();", el)
            el.send_keys(Keys.CONTROL, "a")
            el.send_keys(Keys.BACKSPACE)
            el.send_keys(str(texto))
        except Exception:
            pass

    def press(self, teclas: str | list[str]) -> None:
        sequencia = [teclas] if isinstance(teclas, str) else list(teclas)
        actions = ActionChains(self.driver)
        for tecla in sequencia:
            actions.send_keys(getattr(Keys, tecla))
        actions.perform()

    # -- Espera (NÃO engole exceção -- ver docstring do módulo) ---------
    def wait_visible(self, seletor: str) -> None:
        with _traduzindo():
            self.wait.until(EC.visibility_of_element_located((By.XPATH, seletor)))

    def wait_clickable(self, seletor: str) -> None:
        with _traduzindo():
            self.wait.until(EC.element_to_be_clickable((By.XPATH, seletor)))

    # -- Leitura ---------------------------------------------------------
    def element_exists(self, seletor: str) -> bool:
        return len(self.driver.find_elements(By.XPATH, seletor)) > 0

    def get_value(self, seletor: str) -> str:
        with _traduzindo():
            el = self.wait.until(EC.presence_of_element_located((By.XPATH, seletor)))
        return el.get_attribute("value")

    # -- Diagnóstico / configuração ---------------------------------------
    def screenshot(self, caminho: str) -> None:
        self.driver.save_screenshot(caminho)

    def set_download_dir(self, caminho: str) -> None:
        self.driver.execute_cdp_cmd(
            "Page.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": caminho},
        )

    # =====================================================================
    # Primitivas do CP 5.1 -- linhas MOVIDAS de portal.py/apagar_lmr.py
    # =====================================================================
    # Cada corpo abaixo é a operação Selenium que já existia escrita à mão no
    # consumidor, transplantada sem alteração de mecânica nem de `time.sleep`
    # (os sleeps ficaram no consumidor, que é onde eles significam alguma
    # coisa). É isso que mantém o motor Selenium idêntico ao de antes deste
    # checkpoint -- o caminho de rollback exigido pelo CP 5.1.

    def click_estrito(self, seletor: str) -> None:
        """Mesma mecânica de `click` (scroll + espera + clique via JS), mas
        propagando a falha traduzida. Ver `engine.py` para por que as duas
        variantes precisam coexistir."""
        locator = (By.XPATH, seletor)
        with _traduzindo():
            el = self.wait.until(EC.presence_of_element_located(locator))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
            time.sleep(0.5)
            self.wait.until(EC.element_to_be_clickable(locator))
            self.driver.execute_script("arguments[0].click();", el)

    def scroll_to(self, seletor: str) -> None:
        with _traduzindo():
            el = self.wait.until(EC.presence_of_element_located((By.XPATH, seletor)))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)

    def click_raw(self, seletor: str) -> None:
        """Clique via JS, sem espera de "clicável" e sem rolar antes.

        JS (`arguments[0].click()`) e não `el.click()` nativo: é a mecânica
        canônica do projeto -- `safe_click`, `clicar_salvar_visivel`,
        `excluir_linha_com_confirmacao` e o clique no lápis de
        `pesquisar_e_abrir` já usam todos essa forma. O único ponto que
        clicava nativamente é o laço de exclusão de `apagar_lmr`; ao ser
        portado neste checkpoint ele passa a usar esta -- mudança
        DELIBERADA e registrada em docs/refatoracao/PENDENCIAS.md (o clique
        via JS não é interceptado por overlay, então o ramo
        `ElementClickIntercepted -> falha + break` daquele laço deixa de
        disparar; é o piloto do CP 5.1, validado com o usuário no portal
        real)."""
        with _traduzindo():
            el = self.wait.until(EC.presence_of_element_located((By.XPATH, seletor)))
            self.driver.execute_script("arguments[0].click();", el)

    def wait_present(self, seletor: str) -> None:
        with _traduzindo():
            self.wait.until(EC.presence_of_element_located((By.XPATH, seletor)))

    def clear(self, seletor: str) -> None:
        """`wait.until(element_to_be_clickable(...))` + `.clear()` -- o par
        que abria a etapa de busca de `PMIBPortal.pesquisar_e_abrir`."""
        with _traduzindo():
            el = self.wait.until(EC.element_to_be_clickable((By.XPATH, seletor)))
            el.clear()

    def type_text(self, seletor: str, texto: str) -> None:
        """`.send_keys(texto)` SEM limpar antes -- o `campo.send_keys(pmib)`
        de `pesquisar_e_abrir`. Deixa o campo com o foco, que é o que faz o
        `press("ENTER")` seguinte chegar nele."""
        with _traduzindo():
            el = self.wait.until(EC.element_to_be_clickable((By.XPATH, seletor)))
            el.send_keys(str(texto))

    def current_url(self) -> str:
        return self.driver.current_url

    def fechar(self) -> None:
        """`driver.quit()`, tolerando browser já fechado -- o `try/except`
        que os chamadores de `fechar_driver` faziam por fora."""
        if self.driver is None:
            return
        try:
            self.driver.quit()
        except Exception:
            pass
        self.driver = None
