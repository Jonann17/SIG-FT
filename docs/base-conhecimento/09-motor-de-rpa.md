# O motor de RPA — Playwright explicado para quem escreveu o Selenium

> ⚠️ **Onde o código mora hoje** (atualizado em 2026-08-28)
>
> Este documento foi escrito antes da refatoração e descreve o comportamento do
> módulo, que continua valendo. Mas os CAMINHOS mudaram:
>
> | O que o texto abaixo chama de | Está hoje em |
> |---|---|
> | o motor de RPA | `sigft/core/rpa/` (engine, portal, factory, seletores) |
>
> Este documento já foi atualizado em 2026-08-14 e está em dia. Lembrete: o **Selenium foi REMOVIDO no CP 5.5** — o Playwright é o motor único desde então.
>
> A lógica de negócio descrita aqui continua válida; o que mudou foi onde ela vive. Camadas novas que este texto não menciona: `sigft/core/excel/` (cabeçalho de planilha, código PMIB, gravação com retry), `sigft/core/llm/` (cliente de IA multi-provedor), `sigft/core/rpa/` (portal e motor), `sigft/core/callbacks.py` (o protocolo UI↔serviço).

> **Por que este documento existe.** Na validação de 2026-08-11 o Playwright
> passou nos três módulos testados contra o portal real, e mesmo assim a
> reação foi: *"sinto que é meio perigoso, pois não entendo como o Playwright
> funciona; não fui eu quem escrevi, o com Selenium sim"*.
>
> Essa é a objeção certa. Código que funciona mas ninguém entende é dívida,
> não patrimônio — no dia em que o portal mudar, quem conserta precisa saber
> o que está lendo. Este documento existe para fechar essa distância, e é
> escrito a partir do que você já sabe: cada conceito aparece como
> **"o que era em Selenium → o que é agora"**.

---

## 1. A ideia que organiza tudo: nenhum serviço conhece o motor

Antes, `cria_fichas.py` (e os outros 5) chamava o Selenium direto:

```python
self.wait.until(EC.element_to_be_clickable((By.XPATH, "//botao"))).click()
```

Hoje, o mesmo trecho é:

```python
self.engine.wait_clickable("//botao")
self.engine.click_nativo("//botao")
```

`self.engine` é um **contrato** (`sigft/core/rpa/engine.py`) — uma lista de 32
operações, todas recebendo XPath. Duas implementações cumprem esse contrato:

| Arquivo | O que é |
|---|---|
| `core/rpa/selenium_engine.py` | o Selenium que você escreveu, empacotado |
| `core/rpa/playwright_engine.py` | a mesma lista de operações, em Playwright |

**Os seletores não mudaram.** São os mesmos XPaths de sempre — foi decisão
explícita da Fase 5 não tocar em nenhum. Se um botão do portal mudar de id, o
conserto é o mesmo de antes, no mesmo lugar.

---

## 2. Tradução direta

| Selenium (o que você escreveu) | Playwright (o que roda hoje) | Comentário |
|---|---|---|
| `driver.get(url)` | `page.goto(url)` | igual |
| `driver.find_element(By.XPATH, x)` | `page.locator(f"xpath={x}").first` | o `.first` preserva "o primeiro casamento", que é o que o Selenium faz |
| `WebDriverWait(...).until(EC.element_to_be_clickable(...))` | embutido em `locator.click()` | **o Playwright espera sozinho antes de agir** |
| `element.click()` | `locator.click()` | os dois são clique de mouse real |
| `element.send_keys(txt)` | `locator.fill(txt)` / `press_sequentially(txt)` | `fill` substitui, `press_sequentially` digita tecla a tecla |
| `Select(el).select_by_visible_text(t)` | `locator.select_option(label=t)` | igual |
| `driver.switch_to.active_element` | `page.keyboard` | teclado do navegador, sem precisar do elemento |
| `execute_script("arguments[0].click()")` | `locator.evaluate(...)` | usado só onde o original usava |
| `StaleElementReferenceException` | **não existe** | ver §3 |

---

## 3. As três diferenças de comportamento que importam

Estas são as que mudam o que acontece na tela. O resto é sintaxe.

### 3.1 Espera automática (o fim do `sleep` como muleta)

No Selenium, um elemento que ainda não apareceu dá erro na hora, e por isso o
código antigo é cheio de `time.sleep(2)` — dorme um tempo fixo torcendo para
dar. Se a rede estiver lenta, falha; se estiver rápida, desperdiça.

No Playwright, `click()` **espera o elemento existir, estar visível, estar
habilitado e parar de se mover** antes de clicar, com um limite de tempo. Não
há torcida.

> **Os `sleep` do código continuam lá.** A Fase 5 não removeu nenhum, de
> propósito: mexer em espera e em motor ao mesmo tempo tornaria impossível
> saber qual dos dois causou um problema. Eles hoje são redundantes na maior
> parte, e limpá-los é trabalho de outra fase — com o portal na frente.

### 3.2 Elemento "obsoleto" deixou de existir

`StaleElementReferenceException` acontecia quando você guardava um elemento
numa variável e a página se redesenhava. Era a fonte do laço que recarregava a
tabela inteira a cada linha, em `tech_specs`.

Um `Locator` do Playwright **não é o elemento** — é a *receita* de como
encontrá-lo. Ele é reavaliado a cada ação, então nunca envelhece. Foi o que
permitiu trocar "guardar a linha" por "endereçar a linha por posição"
(`(//linhas)[3]`).

### 3.3 Perfil persistente (o login que fica)

O Selenium abria um navegador limpo a cada execução — daí ter de logar no PMIB
toda vez. O Playwright aqui usa `launch_persistent_context` apontando para
`%LOCALAPPDATA%\SIG-FT\perfil-navegador`: cookies e sessão sobrevivem.

**É o teste mais confiável de qual motor está rodando:** se o portal pede login
toda vez, é Selenium.

---

## 4. Quando algo quebrar

**O primeiro movimento é voltar ao motor antigo**, e ele não exige entender
nada de Playwright:

- abra o `SIG-FT.bat` de sempre com a variável `SIGFT_RPA_ENGINE=selenium`, ou
- edite `sigft/config.py`, dicionário `RPA_ENGINE`, e troque o módulo para
  `ENGINE_SELENIUM`.

Os dois motores continuam completos e testados. **Enquanto isso for verdade,
nenhum problema no Playwright pode parar o trabalho** — e é por isso que o
CP 5.5 (apagar o Selenium) está adiado para depois da Fase 6, não por
cronograma.

Depois de voltar, para descobrir o que houve:

1. `Smoke-Playwright.bat` — responde "o Playwright funciona nesta máquina?"
   offline, sem portal. Se falhar aqui, é ambiente/rede, não código.
2. `python scripts/auditar_seletores.py` — responde "os seletores ainda casam
   com a tela?". Se o portal mudou, é aqui que aparece.
3. Se os dois passarem e só um módulo falhar, é comportamento — e aí o
   comparativo motor a motor (rodar a mesma ficha nos dois) isola em minutos.

---

## 5. O que ainda é Selenium

`sigft/services/ficha_duplicada.py`, e só ele. É o único módulo nunca portado —
usa `webdriver`, `By` e `Select` direto — e a **Fase 6 vai reconstruí-lo**, já
no motor novo. Portá-lo agora seria trabalho descartado na reescrita.

---

## 6. Onde ler o código

| Quero entender... | Arquivo |
|---|---|
| o que um serviço pode pedir ao navegador | `sigft/core/rpa/engine.py` (é só a lista, com o porquê de cada uma) |
| como o Playwright cumpre isso | `sigft/core/rpa/playwright_engine.py` |
| como o Selenium cumpre isso | `sigft/core/rpa/selenium_engine.py` |
| quem escolhe o motor | `sigft/config.py` → `RPA_ENGINE` / `get_rpa_engine()` |
| operações compostas do portal | `sigft/core/rpa/portal.py` (`PMIBPortal`) |

O `engine.py` é o melhor ponto de partida: são 32 assinaturas com docstring
explicando **por que** cada uma existe e de qual trecho do código antigo ela
veio. Ler ele de cabo a rabo leva uns 15 minutos e cobre o vocabulário inteiro
dos dois motores.
