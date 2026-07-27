r"""
sigft/core/rpa/engine.py — interface mínima do motor de automação de browser
(Checkpoint 2.1 do plano de refatoração).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 2 (nota introdutória) e
CP 2.1: "a Fase 2 ainda roda sobre Selenium, mas a API pública do
`PMIBPortal` é definida em termos de intenção (`clicar`, `preencher`,
`esperar_linha`, `pesquisar_e_abrir`), não de Selenium. É o contrato que a
Fase 5 reimplementa em Playwright."

`RPAEngine` é essa camada mais BAIXA (abaixo de `PMIBPortal`, que chega no
CP 2.2): um punhado de operações de INTENÇÃO sobre um browser -- navegar,
clicar, preencher, esperar, ler, tirar print, configurar pasta de download
-- sem NENHUMA palavra "Selenium"/"Playwright" neste arquivo. Isso é
DELIBERADO: é o que permite a Fase 5 (`playwright_engine.py`) implementar
esta MESMA interface sem tocar em nenhum consumidor (serviço/`PMIBPortal`).

Interface exigida pelo CP 2.1: `goto(url)`, `click(seletor)`,
`fill(seletor, texto)`, `press(teclas)`, `wait_visible(seletor)`,
`wait_clickable(seletor)`, `element_exists(seletor)`, `get_value(seletor)`,
`screenshot(caminho)`, `set_download_dir(caminho)`.

Decisões de contrato (ver especificação do CP 2.1):
  - Todo `seletor` é uma STRING XPATH pura (não uma tupla `(By, valor)`).
    Levantamento do CP 2.1 por grep: 139 dos 140 usos de `By.*` no
    repositório hoje já são `By.XPATH` (a única exceção -- um
    `By.CSS_SELECTOR` de leitura de tooltip "PDM Final" em
    `cria_fichas_no_pmib_v1_backend.py:396` -- fica fora do escopo deste
    checkpoint: não é criação de driver, e migrar esse uso de leitura é
    trabalho do CP 2.2; ver docs/refatoracao/PENDENCIAS.md). XPath também é
    o que a nota da Fase 5 cita como reaproveitável em Playwright
    ("Seletores XPath atuais são reaproveitados... Playwright aceita
    XPath").
  - `press(teclas)` NÃO recebe seletor: envia a(s) tecla(s) nomeada(s)
    (ex.: `"ENTER"`, `["TAB", "TAB", "ENTER"]`) ao elemento que estiver COM
    FOCO no momento -- é o mesmo padrão de hoje via
    `driver.switch_to.active_element` (ex.:
    `cria_fichas_no_pmib_v1_backend.AutomacaoPMIB.processar_item_individual`,
    `lmr_backend.LMRAutomation.processar_lista`).
  - `element_exists(seletor)` é uma checagem IMEDIATA ("existe agora, sem
    esperar?"), DIFERENTE de `wait_visible`/`wait_clickable` (que BLOQUEIAM
    até a condição ser satisfeita ou o timeout do motor estourar). Ver
    `selenium_engine.py` para a implementação concreta de cada um.
  - `get_value(seletor)` lê o valor atual de um campo de formulário (mesmo
    papel do `_ler_input`/`get_attribute("value")` de hoje em
    `upload_ficha_duplicada.ExtratorFichaBase`).

Só biblioteca padrão (`abc`) -- importável em `tests/` sem NENHUM stub (ver
tests/conftest.py): nenhuma implementação concreta (Selenium, Playwright)
vive aqui, só o contrato abstrato. É isso que torna este arquivo estável
através da troca de motor da Fase 5: `playwright_engine.PlaywrightEngine`
herdará de `RPAEngine` sem que uma linha aqui precise mudar.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class RPAEngine(ABC):
    """Contrato único que um serviço de automação (hoje `*_backend.py`
    diretamente; `PMIBPortal` a partir do CP 2.2) usa para falar com um
    browser, sem conhecer se por trás roda Selenium
    (`selenium_engine.SeleniumEngine`, Fases 1-4) ou Playwright
    (`playwright_engine.PlaywrightEngine`, Fase 5)."""

    @abstractmethod
    def goto(self, url: str) -> None:
        """Navega para `url`."""

    @abstractmethod
    def click(self, seletor: str) -> None:
        """Clica no elemento localizado por `seletor` (XPath)."""

    @abstractmethod
    def fill(self, seletor: str, texto: str) -> None:
        """Limpa e preenche o campo localizado por `seletor` (XPath) com
        `texto`."""

    @abstractmethod
    def press(self, teclas: str | list[str]) -> None:
        """Envia a(s) tecla(s) nomeada(s) (ex.: `"ENTER"`,
        `["TAB", "TAB", "ENTER"]`) ao elemento que estiver com foco no
        momento -- não recebe seletor."""

    @abstractmethod
    def wait_visible(self, seletor: str) -> None:
        """Bloqueia até o elemento localizado por `seletor` ficar
        visível."""

    @abstractmethod
    def wait_clickable(self, seletor: str) -> None:
        """Bloqueia até o elemento localizado por `seletor` ficar
        clicável."""

    @abstractmethod
    def element_exists(self, seletor: str) -> bool:
        """Checagem IMEDIATA (sem esperar): `seletor` existe na página
        agora?"""

    @abstractmethod
    def get_value(self, seletor: str) -> str:
        """Lê o valor atual (`value`) do campo de formulário localizado por
        `seletor`."""

    @abstractmethod
    def screenshot(self, caminho: str) -> None:
        """Salva uma captura de tela em `caminho`."""

    @abstractmethod
    def set_download_dir(self, caminho: str) -> None:
        """Redireciona downloads subsequentes (da sessão já aberta) para a
        pasta `caminho`."""
