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

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from sigft.core.rpa.engine import RPAEngine


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
        self.wait.until(EC.visibility_of_element_located((By.XPATH, seletor)))

    def wait_clickable(self, seletor: str) -> None:
        self.wait.until(EC.element_to_be_clickable((By.XPATH, seletor)))

    # -- Leitura ---------------------------------------------------------
    def element_exists(self, seletor: str) -> bool:
        return len(self.driver.find_elements(By.XPATH, seletor)) > 0

    def get_value(self, seletor: str) -> str:
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
