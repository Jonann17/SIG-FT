---
tags: [sigft, arquitetura]
---

# SIG-FT — Arquitetura

## O desenho atual

```
frontend.py              # ponto de entrada compativel (92 linhas) — era 2.400
*_backend.py             # shims de compatibilidade -> sigft/services/*
sigft/
├── config.py            # constantes, chaves, LLM_TASKS (tarefa -> provedor+modelo)
├── core/
│   ├── excel/           # headers, pmib_codes, locking, status_sheet, marca_modelo
│   ├── llm/             # client + providers (OpenRouter padrao), usage, prompts,
│   │                    #   catalogo, selecao, comparacao
│   ├── rpa/             # engine, playwright_engine, factory, portal,
│   │                    #   ficha_layout, inventario, seletores_duplicada
│   ├── web/             # navegador, robots (busca web do AutoSpec)
│   ├── callbacks.py     # protocolo UI <-> servico (log / pause / ask / progress)
│   ├── prefs.py         # memoria de caminhos dos dialogos
│   ├── log_execucao.py  # log estruturado
│   ├── relatorio_lote.py
│   └── plataforma.py
├── services/            # a logica de negocio (backends magros)
└── app/                 # UI
    ├── views/           # uma tela por arquivo (13)
    ├── widgets/         # console, dialogs, espera, module_frame, pickers
    ├── theme.py         # paleta GE Vernova, Roboto
    ├── file_dialogs.py
    ├── backends.py
    └── main.py
```

## Os cinco principios inegociaveis

Do `CLAUDE.md` do repositorio:

1. **Uma implementação por conceito** — cabeçalho de planilha, código PMIB, portal, LLM.
2. **UI nunca contém regra de negocio; serviço nunca importa tkinter.**
   A comunicacao e só por callbacks (`core/callbacks.py`).
3. **Nenhum serviço conhece Playwright** — só `PMIBPortal`.
   E o que torna a troca de motor barata.
4. **Nenhum serviço conhece o SDK de um provedor de IA** — só `LLMClient`.
   Modelo e provedor vem de `config.py`.
5. **Compatibilidade por shims** — os nomes antigos continuam importaveis.

> [!tip] Por que o principio 3 e 4 importam para o negocio, não só para o código
> O portal PMIB **e do cliente e muda sem aviso**. Modelos de IA mudam de preço e
> qualidade. Isolar os dois num único ponto significa que uma mudança externa custa
> **um arquivo**, não treze.

## O protocolo UI <-> serviço

`core/callbacks.py` define quatro canais:

| Callback | Para que |
|---|---|
| `log` | mensagens para o console da tela |
| `progress` | fracao 0.0-1.0 para a barra |
| `ask` | pergunta sim/não ao operador no meio do fluxo |
| `pause` / `input` | pedir ação manual (login no portal) ou texto |

isso é o que permite o **login manual no PMIB** no meio de uma automação: o serviço
pausa e pede ao operador que entre, e segue.

## As duas camadas que mais evitaram retrabalho

### `core/excel/`
Concentra o que estava espalhado:
- **busca dinâmica da linha de cabeçalho** — antes em ~10 lugares
- **normalização do código PMIB** (apostrofo, zeros, float) — antes em 6
- **retry de `PermissionError`** quando a planilha está aberta no Excel — antes 4 variantes
- **marcar seção COMPLETO** no `_STATUS_PMIB` — antes 3

Ver [[Planilha STATUS_PMIB]] e [[Codigo PMIB]] para entender *por que* cada um desses
era necessário.

### `core/rpa/ficha_layout.py`
O `CONFIG_MAP` — o mapa de qual célula do template Excel corresponde a qual campo.
E **compartilhado** entre `analyzer` e `autospec`; mexer nele muda os dois.
119 testes de equivalencia em `tests/test_ficha_layout.py` guardam isso.

> [!warning] A pegadinha do CONFIG_MAP
> Desde o CP 2.4 o campo `range` guarda o span **completo** da célula mesclada
> (`"H6:P6"`), não a primeira célula (`"H6"`). Quem precisa só da primeira faz
> `.split(":")[0]` — sem isso, `ws["H6:P6"]` devolve tupla de tuplas e `.value` quebra.

## Relacionados
[[SIG-FT - Motor de RPA]] · [[SIG-FT - Camada de IA]] · [[SIG-FT - Refatoracao]]
