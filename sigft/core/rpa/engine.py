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


# =============================================================================
# Exceções NEUTRAS de motor (Checkpoint 5.1)
# =============================================================================
# Sem elas a Fase 5 não sai do papel. Hoje vários laços de produção decidem o
# que fazer OLHANDO O TIPO da exceção do Selenium:
#
#   `apagar_lmr.executar_limpeza`: `except TimeoutException` = "não há mais
#   lixeiras, o lote acabou" (fim NORMAL, não erro); `except
#   StaleElementReferenceException` = "a tabela se reconstruiu, tenta de novo".
#
# `selenium.common.exceptions.TimeoutException` e o
# `playwright.sync_api.TimeoutError` não têm parentesco nenhum: um serviço que
# capture o primeiro simplesmente NÃO enxerga o segundo, e o laço acima viraria
# um loop infinito silencioso ao trocar de motor. Por isso cada engine traduz a
# exceção do seu SDK para uma destas, e os consumidores capturam só estas.
#
# `ElementoObsoleto` não tem equivalente em Playwright (que reavalia o seletor a
# cada ação, em vez de guardar uma referência que "envelhece"). Isso é esperado
# e não é um buraco: os `except ElementoObsoleto: continue` viram ramos que
# nunca disparam no motor novo — que é exatamente o ganho de estabilidade que a
# decisão de produto nº 5 busca.
class ErroRPA(Exception):
    """Base de todas as falhas traduzidas de um motor de browser."""


class TempoEsgotado(ErroRPA):
    """Uma espera estourou o tempo limite. Traduz
    `selenium.common.exceptions.TimeoutException` e
    `playwright.sync_api.TimeoutError`."""


class ElementoObsoleto(ErroRPA):
    """A referência ao elemento envelheceu porque a página se reconstruiu
    embaixo dela. Traduz `selenium.common.exceptions.
    StaleElementReferenceException`; em Playwright não ocorre."""


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

    # =====================================================================
    # Primitivas acrescentadas pelo Checkpoint 5.1
    # =====================================================================
    # Os 10 métodos acima (CP 2.1) cobriam a INTENÇÃO dos serviços, mas não
    # o suficiente para o `PMIBPortal` largar o `self.engine.driver`/`.wait`
    # cru -- e enquanto ele não larga, trocar de motor é impossível, porque
    # um `PlaywrightEngine` não tem `.driver` nem `.wait` nenhum.
    #
    # Cada primitiva abaixo corresponde a UMA operação Selenium que hoje
    # está escrita à mão dentro de `portal.py`/`services/apagar_lmr.py`; a
    # implementação em `SeleniumEngine` é a MESMA LINHA, movida, não
    # reescrita. Isso é o que garante que o motor Selenium continue se
    # comportando exatamente como antes deste checkpoint (o caminho de
    # rollback do CP 5.1) enquanto o Playwright ganha um caminho próprio.
    #
    # A separação `click` vs `click_estrito` merece nota: `click` ENGOLE
    # exceção desde o CP 2.1 (é a mecânica do antigo `safe_click`, e é o que
    # `PMIBPortal.safe_click` promete). Num LAÇO que decide continuar ou
    # parar pelo resultado do clique -- o laço de exclusão de `apagar_lmr` é
    # exatamente isso -- engolir a falha faria o clique virar um no-op
    # silencioso e o laço girar sem fim. Daí a variante estrita.

    @abstractmethod
    def click_estrito(self, seletor: str) -> None:
        """Igual a `click`, mas PROPAGA a falha (`TempoEsgotado`,
        `ElementoObsoleto`) em vez de engoli-la. Para laços que decidem o
        que fazer a partir do resultado do clique."""

    @abstractmethod
    def fill_estrito(self, seletor: str, texto: str) -> None:
        """Igual a `fill` (limpa e preenche), mas PROPAGA a falha em vez de
        engoli-la -- o mesmo par que `click`/`click_estrito` forma.

        Necessário onde o chamador REPORTA o resultado:
        `cria_fichas.atualizar_projeto_em_massa` devolve `("SUCESSO", ...)` /
        `("ERRO", ...)`. Se o preenchimento falhasse em silêncio, a função
        seguiria para o botão salvar, salvaria a ficha sem o novo código de
        projeto e devolveria SUCESSO -- um resultado errado, e pior que um
        erro, porque ninguém vai conferir."""

    @abstractmethod
    def scroll_to(self, seletor: str) -> None:
        """Rola a página até o elemento ficar centralizado na viewport, sem
        clicar nem esperar por condição nenhuma."""

    @abstractmethod
    def click_raw(self, seletor: str) -> None:
        """Clica SEM a espera de "clicável" e sem rolar a tela antes.

        Existe porque `scroll_to` + `click_raw` é a sequência EXATA de dois
        pontos de produção que o CP 5.1 porta (o clique no lápis de
        `pesquisar_e_abrir` e o da lixeira em `apagar_lmr`), e ambos têm
        entre o scroll e o clique um `time.sleep` PRÓPRIO, de valor
        diferente. Espremer os dois dentro de `click_estrito` obrigaria a
        escolher um dos sleeps e a acrescentar ao lápis uma espera de
        "clicável" que ele nunca teve -- ou seja, mudaria o comportamento de
        4 módulos que continuam no Selenium. A decomposição mantém a
        orquestração (e os sleeps) no consumidor, onde ela sempre esteve."""

    @abstractmethod
    def wait_present(self, seletor: str) -> None:
        """Bloqueia até o elemento existir no DOM -- sem exigir que esteja
        visível ou clicável. Levanta `TempoEsgotado` no timeout."""

    @abstractmethod
    def clear(self, seletor: str) -> None:
        """Esvazia o campo localizado por `seletor`, sem digitar nada."""

    @abstractmethod
    def type_text(self, seletor: str, texto: str) -> None:
        """Digita `texto` NO FIM do conteúdo atual do campo (não limpa
        antes) -- diferente de `fill`, que limpa. Propaga falhas."""

    @abstractmethod
    def current_url(self) -> str:
        """URL da página aberta agora."""

    @abstractmethod
    def fechar(self) -> None:
        """Encerra o browser e libera os recursos do motor. Idempotente:
        chamar duas vezes não levanta."""
