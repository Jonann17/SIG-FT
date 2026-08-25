r"""
sigft/core/rpa/factory.py — ponto único que decide QUAL motor de browser subir
(Checkpoint 5.1 do plano de refatoração).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 5 -> CP 5.1: "Config
`RPA_ENGINE = "selenium" | "playwright"` por módulo (permitia migração gradual e
rollback imediato)".

⚠️ O mapa `RPA_ENGINE` e o Selenium saíram no CP 5.5 (2026-08-25), quando a
Fase 6 fechou validada no portal. A REGRA abaixo é o que sobreviveu, e é a
razão de a fábrica continuar existindo com um motor só.

Um serviço NÃO importa `playwright_engine`: pede
`criar_engine("apagar_lmr")` e recebe um `RPAEngine`. É essa indireção que
transforma "migrar um módulo" em "trocar uma linha de `config.RPA_ENGINE`" e,
principalmente, "voltar atrás" em trocar a mesma linha de volta -- que é o que
a validação assistida da Fase 5 exige, já que o julgamento acontece com o
usuário na frente do portal real e pode dar errado.

Os dois imports concretos são PREGUIÇOSOS (dentro da função), pelo mesmo motivo
em cada caso, com sinais opostos:
  - `playwright_engine` importa `playwright.sync_api` só dentro de `criar()`,
    mas o próprio módulo é leve; ainda assim, importá-lo aqui só quando pedido
    mantém a fábrica utilizável num ambiente sem Playwright.
  - `selenium_engine` importa `selenium` no TOPO. Um import ansioso aqui
    obrigaria quem já estivesse 100% em Playwright a continuar com Selenium
    instalado -- exatamente o que o CP 5.5 vai querer eliminar.
"""

from __future__ import annotations

from sigft import config
from sigft.core.rpa.engine import RPAEngine


def criar_engine(
    modulo: str,
    *,
    wait_timeout: int = 20,
    download_dir: str | None = None,
) -> RPAEngine:
    """Sobe e devolve o motor configurado para `modulo`.

    `modulo` é o nome do arquivo em `sigft/services/` (ex.: `"apagar_lmr"`) --
    a mesma chave de `config.RPA_ENGINE`.

    `wait_timeout` (segundos) e `download_dir` têm o mesmo significado nos dois
    motores; cada um preserva o valor que o call site já usava antes da Fase 5
    (10, 15 ou 20 — divergem entre módulos e NÃO são unificados aqui).
    """
    # CP 5.5: havia um `if` aqui, escolhendo entre os dois motores por
    # `config.RPA_ENGINE`. O Selenium saiu do projeto em 2026-08-25, depois de
    # a Fase 6 fechar validada no portal -- a flag existia para permitir
    # rollback durante a migração, e migração terminada não tem rollback.
    #
    # A função CONTINUA existindo, e não por inércia: é ela que mantém a regra
    # "nenhum serviço importa um motor concreto". O dia em que houver um motor
    # novo, o `if` volta aqui e em lugar nenhum mais.
    from sigft.core.rpa.playwright_engine import PlaywrightEngine

    return PlaywrightEngine.criar(wait_timeout=wait_timeout, download_dir=download_dir)
