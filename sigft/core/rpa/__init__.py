"""Pacote `sigft.core.rpa` — camada de automação de browser do SIG-FT.

Checkpoint 2.1 do plano de refatoração
(docs/refatoracao/PLANO_REFATORACAO.md, Fase 2 -> CP 2.1):

  - `engine.py`: `RPAEngine` — interface mínima do motor de browser, definida
    em termos de INTENÇÃO (`goto`, `click`, `fill`, `press`, `wait_visible`,
    `wait_clickable`, `element_exists`, `get_value`, `screenshot`,
    `set_download_dir`), agnóstica a Selenium/Playwright. Só stdlib.
  - `selenium_engine.py`: `create_chrome_driver()` (fábrica de driver,
    substitui as 6 inicializações de `webdriver.Chrome()` do diagnóstico) +
    `SeleniumEngine` — implementação de `RPAEngine` sobre Selenium,
    reproduzindo a mecânica atual (`safe_click`/`safe_send_keys`: scroll +
    clique/preenchimento via JavaScript).

Ver a nota introdutória da Fase 2 no plano: "a Fase 2 ainda roda sobre
Selenium, mas a API pública do `PMIBPortal` é definida em termos de intenção
... não de Selenium. É o contrato que a Fase 5 reimplementa em Playwright."

Acrescentado depois do CP 2.1:
  - `portal.py` / `PMIBPortal` (CP 2.2) — move `safe_click`/`safe_fill`/
    `pesquisar_e_abrir`/etc. dos 6 backends para cima de `RPAEngine`.
  - `ficha_layout.py` (CP 2.4) — `CONFIG_MAP` unificado.
  - `playwright_engine.py` (CP 5.1) — a segunda implementação de `RPAEngine`,
    com contexto persistente (o login manual sobrevive entre execuções) e modo
    headed. Junto com ela, `engine.py` ganhou as exceções NEUTRAS
    (`TempoEsgotado`/`ElementoObsoleto`) e 8 primitivas novas, que existem para
    o `PMIBPortal` largar o `self.engine.driver`/`.wait` cru — enquanto ele não
    largava, trocar de motor era impossível.
  - `factory.py` (CP 5.1) — `criar_engine(modulo)`: ponto único que lê
    `config.RPA_ENGINE` e decide qual motor subir. É o que torna "migrar um
    módulo" (e desfazer) uma troca de configuração, não de código.
"""
