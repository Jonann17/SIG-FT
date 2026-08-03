r"""
Smoke test do motor Playwright — roda contra um site PÚBLICO, não contra o PMIB.

    python scripts/smoke_playwright.py

Para que serve: separar DUAS perguntas que, juntas, viram um debugging confuso.

    1. "O Playwright funciona nesta máquina?"  -- navegador baixado, contexto
       persistente criando perfil, modo headed abrindo janela, rede corporativa
       deixando passar. Esta pergunta se responde em QUALQUER computador, sem
       ficha nenhuma e sem acesso ao portal.
    2. "O portal PMIB responde bem a este motor?" -- é o aceite dos CP 5.1/5.2,
       e só a sessão real na máquina da empresa responde.

Se a (1) falhar na máquina corporativa, saber que ela passava na máquina pessoal
já aponta o dedo para a rede/Zscaler em vez de para o código.

O que este script exercita, do `PlaywrightEngine` de verdade (nenhum fake):
`criar` (com contexto persistente e headed), `goto`, `current_url`,
`wait_present`, `wait_visible`, `element_exists`, `clear`, `type_text`,
`fill_estrito`, `get_value`, `press`, `click_raw`, `scroll_to`, `screenshot` e
`fechar` -- ou seja, as mesmas primitivas que `apagar_lmr`, `lmr` e a
atualização em massa de `cria_fichas` usam no portal.

Alvo: uma página `data:` gerada aqui mesmo. O smoke é 100% OFFLINE de
propósito -- nenhuma requisição sai da máquina. Uma versão anterior abria o
`example.com`, e isso se mostrou uma má ideia: numa rede que bloqueia o site (ou
atrás de um proxy que o robô não conhece), o smoke falharia por causa da REDE e
pareceria defeito do motor -- exatamente a confusão que ele existe para evitar.
Há uma checagem de internet OPCIONAL no fim, claramente separada, que não conta
como falha.
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sigft.core.rpa.engine import TempoEsgotado  # noqa: E402
from sigft.core.rpa.playwright_engine import PlaywrightEngine  # noqa: E402

# Página de formulário embutida: um input, um textarea e um botão que copia o
# input para um parágrafo. Dá para exercitar digitar, ler de volta, teclar e
# clicar sem depender de nenhum site externo se comportar de um jeito.
_PAGINA_FORMULARIO = (
    "data:text/html;charset=utf-8,"
    "<html><body>"
    "<h1 id='titulo'>SIG-FT smoke</h1>"
    "<input id='campo' value='valor inicial'>"
    "<textarea id='area'>texto antigo</textarea>"
    "<button id='botao' onclick=\"document.getElementById('eco').textContent="
    "document.getElementById('campo').value\">Copiar</button>"
    "<p id='eco'></p>"
    "<div style='height:1500px'></div>"
    "<p id='rodape'>fim</p>"
    "</body></html>"
)

_resultados: list[tuple[str, bool, str]] = []


def verificar(descricao, condicao, detalhe=""):
    _resultados.append((descricao, bool(condicao), detalhe))
    marca = "OK  " if condicao else "FALHOU"
    print(f"  [{marca}] {descricao}" + (f" -- {detalhe}" if detalhe and not condicao else ""))


def main() -> int:
    perfil = os.path.join(tempfile.gettempdir(), "sigft-smoke-perfil")
    print("SIG-FT -- smoke do motor Playwright")
    print(f"  perfil temporario: {perfil}")
    print("  (uma janela do navegador vai abrir; ela fecha sozinha no fim)\n")

    # Sem tela (servidor, CI, WSL sem X) da para rodar invisivel:
    #     set SIGFT_SMOKE_HEADLESS=1
    # No uso normal, em maquina com monitor, deixe desligado -- ver a janela
    # abrir e fechar faz parte do que este script confere.
    headless = os.environ.get("SIGFT_SMOKE_HEADLESS", "").strip().lower() in ("1", "true", "sim")

    try:
        engine = PlaywrightEngine.criar(wait_timeout=15, perfil=perfil, headless=headless)
    except ImportError:
        print("\nERRO: o pacote `playwright` nao esta instalado neste ambiente.")
        print("      Rode:  python -m pip install playwright")
        return 2
    except Exception as erro:
        print(f"\nERRO ao subir o navegador: {type(erro).__name__}: {erro}\n")
        print("Causa mais comum: o navegador nunca foi baixado. Rode:")
        print("      python -m playwright install chromium")
        print("(no Windows, o atalho e o Instalar-Playwright.bat)")
        print("\nEm rede corporativa com Zscaler, o download precisa de")
        print("NODE_EXTRA_CA_CERTS -- ver README.md, secao 'Rede corporativa'.")
        return 2

    try:
        print("1. Navegacao e leitura")
        engine.goto(_PAGINA_FORMULARIO)
        verificar("goto + current_url", engine.current_url().startswith("data:text/html"))
        engine.wait_visible("//*[@id='titulo']")
        verificar("wait_visible achou o titulo", True)
        verificar("element_exists diz SIM para o que existe", engine.element_exists("//*[@id='titulo']") is True)
        verificar(
            "element_exists diz NAO para o que nao existe",
            engine.element_exists("//*[@id='nao-existe-em-lugar-nenhum']") is False,
        )

        print("\n2. Formulario (digitar, ler de volta, teclar, clicar)")
        engine.wait_present("//*[@id='campo']")

        verificar("get_value le o valor inicial", engine.get_value("//*[@id='campo']") == "valor inicial")

        engine.clear("//*[@id='campo']")
        verificar("clear esvazia o campo", engine.get_value("//*[@id='campo']") == "")

        engine.type_text("//*[@id='campo']", "4500063671.0001")
        verificar(
            "type_text digita tecla a tecla",
            engine.get_value("//*[@id='campo']") == "4500063671.0001",
            engine.get_value("//*[@id='campo']"),
        )

        engine.fill_estrito("//*[@id='area']", "texto novo")
        verificar(
            "fill_estrito limpa e preenche",
            engine.get_value("//*[@id='area']") == "texto novo",
            engine.get_value("//*[@id='area']"),
        )

        # `press` vai para o elemento COM FOCO -- o mesmo padrao que o `lmr`
        # usa depois de digitar uma TAG.
        engine.type_text("//*[@id='campo']", "X")
        engine.press("BACKSPACE")
        verificar(
            "press('BACKSPACE') chega no campo que acabou de ser digitado",
            engine.get_value("//*[@id='campo']") == "4500063671.0001",
            engine.get_value("//*[@id='campo']"),
        )

        engine.click_raw("//*[@id='botao']")
        eco = engine.page.locator("xpath=//*[@id='eco']").first.text_content()
        verificar("click_raw disparou o onclick", eco == "4500063671.0001", repr(eco))

        print("\n3. Rolagem e timeout")
        engine.scroll_to("//*[@id='rodape']")
        verificar("scroll_to chegou no rodape (1500px abaixo)", True)

        # O timeout tem de virar `TempoEsgotado` -- e disso que os lacos de
        # producao dependem para saber que um lote acabou.
        engine.timeout_ms = 1500
        try:
            engine.wait_visible("//*[@id='jamais-vai-existir']")
            verificar("timeout vira TempoEsgotado", False, "nao levantou nada")
        except TempoEsgotado:
            verificar("timeout vira TempoEsgotado", True)
        except Exception as erro:
            verificar("timeout vira TempoEsgotado", False, f"veio {type(erro).__name__}")

        print("\n4. Screenshot")
        destino = os.path.join(tempfile.gettempdir(), "sigft-smoke.png")
        engine.screenshot(destino)
        verificar("screenshot gravou o arquivo", os.path.getsize(destino) > 0, destino)
        print(f"       -> {destino}")

        print("\n5. Internet (OPCIONAL -- nao conta como falha)")
        # Separado de proposito: se a rede bloquear, o motor continua sadio.
        # O que isto responde e outra coisa -- "este navegador consegue sair
        # para a internet daqui?" -- e a resposta importa para o portal, que e
        # remoto, mas nao diz nada sobre o codigo.
        try:
            engine.timeout_ms = 10_000
            engine.goto("https://example.com")
            print(f"  [OK  ] o navegador alcancou a internet ({engine.current_url()})")
        except Exception as erro:
            print(f"  [nota] o navegador NAO alcancou a internet: {type(erro).__name__}")
            print("         Sem problema para este smoke -- mas o portal PMIB e remoto.")
            print("         Se acontecer na maquina da empresa, e proxy/Zscaler: o")
            print("         Chromium do Playwright nao herda o proxy do Windows")
            print("         automaticamente em toda configuracao.")

    except Exception:
        print("\nErro inesperado durante o smoke:\n")
        traceback.print_exc()
        _resultados.append(("execucao sem erro inesperado", False, ""))
    finally:
        engine.fechar()

    falhas = [descricao for descricao, ok, _ in _resultados if not ok]
    print("\n" + "=" * 60)
    if falhas:
        print(f"FALHOU: {len(falhas)} de {len(_resultados)} verificacoes")
        for descricao in falhas:
            print(f"  - {descricao}")
        print("=" * 60)
        return 1

    print(f"TUDO OK: {len(_resultados)} verificacoes.")
    print("O motor Playwright funciona nesta maquina. O que ele ainda NAO")
    print("prova e se o portal PMIB responde bem a ele -- isso e a sessao de")
    print("validacao dos CP 5.1/5.2, na maquina da empresa.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
