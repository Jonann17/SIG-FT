---
tags: [sigft, refatoracao]
---

# SIG-FT — Refatoracao

## Por que refatorar

Do `PLANO_REFATORACAO.md`:
> O sistema **funciona**, mas cresceu por copia: cada módulo novo nasceu clonando o anterior.

O diagnostico e quantitativo, não opinião:

| Camada | Duplicacao encontrada |
|---|---|
| **RPA** | driver Chrome 6x · pesquisar PMIB 6 variantes · `safe_click` 4x idêntico · URL hardcoded 10+ |
| **Excel** | busca de cabeçalho ~10x · normalização de código PMIB 6x · marcar COMPLETO 3x · retry de arquivo aberto 4 variantes |
| **IA** | `genai.configure` + retry 5x · limpeza de JSON 4 variantes · `CONFIG_MAP` duplicado com **ranges divergentes** (`H6:P6` vs `H6`) · prompts gigantes embutidos em 5 módulos |
| **Frontend** | 2.400 linhas · `log()` thread-safe em **3 implementacoes diferentes** · janela de pausa de login 4 copias · seletor de arquivo 20+ copias |

## As decisões de produto (24/07/2026)

1. **`ficha_duplicada` será RECONSTRUIDO**, não refatorado.
2. **Camada de IA plugavel com troca de modelo pela interface**, OpenRouter como gateway
   padrão, com rastreamento de custo. Ver [[SIG-FT - Camada de IA]].
3. **UI**: padronizar mantendo o estilo (paleta GE Vernova, Roboto). Sem redesign.
4. **Logs**: elevar todos os módulos ao mesmo padrão de riqueza.
5. **RPA migra para Playwright**. Ver [[SIG-FT - Motor de RPA]].
6. Duas skills de apoio: `sigft-novo-modulo` e `sigft-melhorar-modulo`.
7. **Memória de caminhos nos dialogos** — cada dialogo abre na última pasta usada
   *para aquele tipo de arquivo*. Com pastas padrão pre-configuradas apontando para o
   Box (`SOBRESSALENTES - PMIB`, `PDMs modificados`, `Templates`), armazenadas
   **relativas ao home** para funcionar em qualquer máquina.

## As fases

| Fase | Tema | Estado |
|---|---|---|
| 1 | fundacoes (`config.py`, prefs, callbacks) | concluída |
| 2 | consolidação Excel + `ficha_layout` | concluída (CP 2.4) |
| 3 | camada de IA multi-provedor | CP 3.1-3.2 concluídos |
| 4 | logs e padronização | CP 4.4 |
| 5 | migração para Playwright | concluída (CP 5.5 removeu o Selenium) |
| 6 | reconstrucao de `ficha_duplicada` | pendente |
| 7 | quebra do `frontend.py` em views | CP 7.3 concluído em 26/08/2026 |
| 8 | — | livre |

## Como se verifica

```bash
bash scripts/check.sh    # compileall + pytest (1.327 testes)
```

**Verde e pre-requisito de qualquer commit.** As dependências pesadas (pandas, openpyxl,
Playwright, google-generativeai, tkinter) são **stubadas** em `tests/conftest.py`, entao
a suite roda em ambiente sem elas.

### Mas `frontend.py` precisa de três verificacoes

`frontend.py` **não pode ser importado** no ambiente de teste (abre janela real):

1. `compileall` — sintaxe
2. `python -m pyflakes frontend.py` — **nome indefinido**, que o `compileall` não vê
3. **abrir o aplicativo** — `python frontend.py` e olhar

> [!danger] Por que as três
> Em 25/08/2026 o CP 5.5 removeu um frame de `ModuloCopiaFichas` e deixou um widget
> filho para tras. `compileall` passou. **2.625 testes passaram.** E o app morria na
> abertura com `NameError: name 'f_novo' is not defined`.
>
> **Editou `frontend.py`? Abra o app antes de dizer que está pronto.**

## O trabalho paralelo

Duas frentes simultaneas desde 11/08/2026. Contrato de fronteiras em
`docs/refatoracao/TRABALHO_PARALELO.md`:

| | |
|---|---|
| **Luan** (`luanccozer`) | refatoracao geral |
| **Rafael** (`rafhagmm`) | **apenas** o AutoSpecAI |

- **Do Rafael**: `services/autospec*.py`, `autospec_backend.py`, `core/web/`,
  `ModuloAutoSpec`, `tests/test_autospec_*.py`, `docs/base-conhecimento/08-*.md`
- **Zonas compartilhadas** (commit isolado + mensagem explicita):
  `core/rpa/ficha_layout.py` -> `CONFIG_MAP`, `config.LLM_TASKS`, `core/llm/prompts.py`
- Conflito em `PENDENCIAS.md`: **mantenha as duas linhas**, nunca escolha um lado

## Convencoes
- **Idioma**: código, commits, comentários e docs em português. Commits **sem acento**.
- **Escopo de checkpoint**: implementar **só** o checkpoint pedido. O que se descobre
  fora do escopo vai para `PENDENCIAS.md` — não se corrige de carona.
- **Nada de reformatacao em massa** de arquivo compartilhado.
- **Testes junto com a mudança.**

## A regra Skill-First
O `CLAUDE.md` do repositorio manda avaliar as skills disponiveis **antes** de qualquer
tarefa, com skills de processo (`systematic-debugging`, `brainstorming`,
`test-driven-development`, `verification-before-completion`) vindo antes das de
implementação.

## Relacionados
[[SIG-FT - Arquitetura]] · [[SIG-FT - Modulos]] · [[SIG-FT - Camada de IA]]
