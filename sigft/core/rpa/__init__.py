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

Módulos futuros, fora do escopo do CP 2.1 (ver docs/refatoracao/PENDENCIAS.md
para o que cada um herda deste checkpoint):
  - `portal.py` / `PMIBPortal` (CP 2.2) — move `safe_click`/`safe_fill`/
    `pesquisar_e_abrir`/etc. dos 6 backends para cima de `RPAEngine`.
  - `playwright_engine.py` (Fase 5) — segunda implementação de `RPAEngine`.
  - `ficha_layout.py` (CP 2.4).
"""
