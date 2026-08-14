r"""Renderizar uma página num navegador de verdade — ÚLTIMO recurso.

POR QUE EXISTE
------------------------------------------------------------------------
Duas coisas que o `requests` não resolve, e que apareceram juntas no
primeiro teste real com busca web (2026-08-12, sensor HYDAC):

1. **HTTP 403.** `hydac.com/shop` recusou o download. Um resultado de busca
   correto, perdido.
2. **Página que é aplicação JavaScript.** O HTML estático da loja da HYDAC
   quase não tem texto: as especificações só existem depois que o script
   roda. O documento "chegava", e vinha vazio — o pior dos casos, porque não
   parece falha.

O motivo nº 2 é o que justifica este módulo. O 403 é consequência.

O QUE ELE NÃO É
------------------------------------------------------------------------
**Não é um contornador de bloqueio.** A ordem de uso, cravada em
`autospec.py`, é: tenta o download simples; só se ele falhar, e só se o
`robots.txt` do domínio permitir, abre o navegador. Um site que diz "não" no
`robots.txt` continua recebendo "está bem".

Isso é uma decisão de conduta, não uma limitação técnica — e por isso está
escrita aqui, onde quem for mexer vai ler.

CUSTO
------------------------------------------------------------------------
Segundos por página, contra milissegundos do `requests`. É aceitável
justamente por ser último recurso: numa ficha em que o download simples
funciona, este módulo nunca é chamado.

DEPENDÊNCIA
------------------------------------------------------------------------
`playwright` já está no `requirements.txt` (é o motor novo de RPA do portal),
mas o NAVEGADOR dele é baixado à parte, por
`.venv\Scripts\playwright install chromium` — o `Instalar-Playwright.bat` faz
isso. Sem o navegador instalado, `texto_da_pagina` devolve `None` e o
AutoSpec segue sem ele, como segue sem o reforço semântico.
"""

# Tempo máximo esperando a página assentar. Site de fabricante com muito
# script passa de 10s; além de 25 não vale a pena esperar num lote.
TIMEOUT_MS = 25_000

# Abaixo disto a página não tem conteúdo útil — provavelmente uma casca de
# erro ou um "carregando". Mesmo limite que `retrieve_context` usa para
# decidir se um documento vale como contexto.
MIN_CHARS_UTIL = 100


def disponivel():
    """O Playwright está instalado E com navegador baixado?

    Só verifica o import: descobrir se o navegador foi baixado exige tentar
    abrir, o que é caro. A tentativa real trata a falha.
    """
    try:
        import playwright.sync_api  # noqa: F401

        return True
    except Exception:
        return False


def texto_da_pagina(url, timeout_ms=TIMEOUT_MS, _sync_playwright=None):
    """Texto visível da página depois que o JavaScript rodou.

    `None` quando não deu — sem Playwright, sem navegador baixado, timeout,
    página vazia. Quem chama segue sem, e é por isso que nada aqui levanta
    exceção: este é o caminho de último recurso, e ele falhar não pode custar
    a ficha.

    `_sync_playwright` é ponto de injeção para teste.
    """
    fabrica = _sync_playwright
    if fabrica is None:
        try:
            from playwright.sync_api import sync_playwright as fabrica
        except Exception:
            return None

    navegador = contexto = None
    playwright = None
    try:
        playwright = fabrica().start()
        navegador = playwright.chromium.launch(headless=True)
        contexto = navegador.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            )
        )
        pagina = contexto.new_page()
        pagina.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        try:
            # "Sem requisição de rede há 500ms" é o sinal de que os scripts
            # terminaram. Se não acontecer no tempo, segue com o que já
            # renderizou -- meia página é melhor que nenhuma.
            pagina.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception:
            pass
        texto = pagina.inner_text("body")
    except Exception:
        return None
    finally:
        for recurso in (contexto, navegador):
            try:
                if recurso is not None:
                    recurso.close()
            except Exception:
                pass
        try:
            if playwright is not None:
                playwright.stop()
        except Exception:
            pass

    texto = (texto or "").strip()
    return texto if len(texto) >= MIN_CHARS_UTIL else None
