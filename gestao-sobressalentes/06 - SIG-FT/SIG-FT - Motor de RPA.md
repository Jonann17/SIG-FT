---
tags: [sigft, rpa]
---

# SIG-FT — Motor de RPA

## Por que existe RPA aqui

O portal PMIB não tem API. Tudo que a equipe faz nele e clique. Com
mais de mil fichas e, num caso extremo como o RTA, ~150 aplicações LMR por ficha,
automatizar o
navegador deixou de ser conveniencia.

`PORTAL_URL = https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList` — **só acessivel da
rede da empresa**.

## Selenium -> Playwright

A migração foi a **Fase 5** da refatoracao, validada contra o portal real em
**11/08/2026**. O Playwright virou padrão dos módulos portados.

> [!warning] Divergência de documentação no repositorio
> O `README.md` ainda descreve um fallback para Selenium (`SIG-FT-Motor-Antigo.bat`) e
> diz que `ficha_duplicada` contínua em Selenium. Mas o
> `docs/base-conhecimento/09-motor-de-rpa.md`, atualizado em **28/08/2026**, afirma que
> **o Selenium foi REMOVIDO no CP 5.5** — e o diretorio `sigft/core/rpa/` de fato **não
> tem `selenium_engine.py`**, só `playwright_engine.py`.
>
> **O código e a fonte de verdade: o motor e Playwright, único.** O README esta
> desatualizado nesse ponto. Vale corrigir.

### O ganho prático
Perfil de navegador persistente em `%LOCALAPPDATA%\SIG-FT\perfil-navegador` — o login
manual no PMIB **contínua valendo na execução seguinte**, em vez de recomecar do zero.

## O contrato `engine`

`sigft/core/rpa/engine.py` define **32 operacoes**. Nenhum serviço chama o Playwright
direto:

```python
# antes (Selenium, espalhado em 6 modulos)
self.wait.until(EC.element_to_be_clickable((By.XPATH, "//botao"))).click()

# hoje
self.engine.wait_clickable("//botao")
self.engine.click_nativo("//botao")
```

Acima do `engine` fica **`PMIBPortal`** (`core/rpa/portal.py`), que conhece o portal:
pesquisar um PMIB, abrir a ficha pelo lapis, navegar entre abas, excluir linha de
tabela com confirmacao.

## O que a duplicacao custava antes

Diagnostico do `PLANO_REFATORACAO.md`:

| Lógica | Implementacoes antes |
|---|---|
| Iniciar driver Chrome | **6x** |
| Pesquisar PMIB + clicar no lapis | **6 variantes** (uma delas com 24 TABs cegos) |
| `safe_click` (scroll + JS click) | **4x idêntico** |
| `safe_send_keys` | 3 variantes |
| Loop lixeira + CONFIRMAR | 3x |
| Flag de parada | 4x |
| URL do portal hardcoded | **10+ ocorrencias** |

## As sete regras do portal

`docs/PORTAL_COMO_ELE_SE_COMPORTA.md` §0 — cada uma paga com pelo menos uma rodada
perdida de desenvolvimento:
- **a URL que não muda** (SPA OutSystems: navegar não muda o endereco, entao não da
  para esperar por URL)
- **o modal que trava tudo**
- **o `required=False` que não e opcional**
- **a recusa silenciosa** (o portal aceita o clique e não grava)

> [!danger] `scripts/check.sh` verde não e prova de portal
> Os testes rodam contra **dubles escritos pelo próprio desenvolvedor** — eles provam a
> *ideia* que se tem do portal, não o portal. **Nada de RPA se declara pronto sem uma
> execução real.**

E o corolario organizacional: **trabalho de portal exige sessão local**, com o
navegador ligado. Um ambiente sem acesso a rede da empresa recebe `403` do PMIB — foi o
que travou o módulo de ficha duplicada por uma semana em agosto/2026.

## Verificação sem o portal

`Smoke-Playwright.bat` exercita as mesmas operacoes (digitar, ler de volta, teclar,
clicar, rolar, print) **contra uma página local, offline**. Serve para separar duas
perguntas que juntas viram depuracao confusa:
- *"O Playwright funciona nesta máquina?"* — o smoke responde em qualquer computador.
- *"O portal responde bem a ele?"* — só a sessão real responde.

Se o smoke passa em casa e falha no trabalho, o dedo aponta para a rede/Zscaler.

## Relacionados
[[SIG-FT - Arquitetura]] · [[SIG-FT - Como Rodar]] · [[SIG-FT - Modulos]]
