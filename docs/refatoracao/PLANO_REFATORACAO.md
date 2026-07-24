# Plano de Refatoração — SIG-FT

> **Como usar este documento**: cada fase é dividida em checkpoints pequenos e independentes.
> A execução é feita pelo agente `refactor-executor` (modelo Sonnet), um checkpoint por vez:
> *"Execute o Checkpoint 2.1 do plano de refatoração"*. O agente lê este plano, a base de
> conhecimento (`docs/base-conhecimento/`) e implementa. O quadro de status no final registra
> o progresso. **A ordem das fases importa** — não pule fases (exceções indicadas no texto).

---

## 0. Decisões de produto (definidas pelo usuário em 2026-07-24)

Estas decisões orientam todo o plano e prevalecem sobre qualquer regra genérica:

1. **`ficha_duplicada` será RECONSTRUÍDO, não apenas refatorado.** O módulo atual "não
   funciona como deveria e está muito fraco". Comportamento novo é autorizado (Fase 6), com
   testes interativos junto ao usuário contra o portal real.
2. **Camada de IA genérica e plugável, com troca de modelo PELA INTERFACE**: o usuário
   escolhe na UI qual modelo usar (global e por tarefa). **OpenRouter é o gateway padrão** —
   uma única chave dá acesso a Gemini, GPT, Kimi, DeepSeek etc., fornece o catálogo de
   modelos para a UI e devolve o custo REAL de cada chamada. Mantêm-se dois caminhos
   diretos opcionais: Gemini nativo (preserva comportamento e free tier atuais, sem
   intermediário — útil para conteúdo sensível) e endpoint OpenAI-compatível genérico
   (para a futura IA interna da empresa). Estratégia de chaves: todas opcionais, uma
   necessária — no dia a dia basta `OPENROUTER_API_KEY`; a UI só exibe provedores com
   chave configurada. Inclui **rastreamento de gastos** por chamada, modelo e módulo.
3. **UI**: padronizar mantendo o estilo visual já existente (paleta GE Vernova, Roboto,
   layout header/conteúdo/console). Sem redesign.
4. **Logs de saída**: elevar todos os módulos ao mesmo padrão de riqueza (alguns hoje são
   pobres). Ver especificação no CP 4.4.
5. **RPA migra de Selenium para Playwright** (Fase 5) para ganhar estabilidade. A
   consolidação da Fase 2 já é desenhada para tornar essa troca barata.
6. Duas skills de apoio ao desenvolvimento vivem em `.claude/skills/`:
   `sigft-novo-modulo` (criar módulo a partir de uma ideia) e `sigft-melhorar-modulo`
   (evoluir módulo existente). Mantê-las atualizadas quando a arquitetura mudar.

---

## 1. Diagnóstico (por que refatorar)

O sistema funciona, mas cresceu por cópia: cada módulo novo nasceu clonando o anterior.
Inventário concreto de duplicações e problemas (com localização):

### 1.1 Duplicação de RPA (o problema nº 1)

| Lógica | Implementações hoje |
|---|---|
| Iniciar driver Chrome (`webdriver.Chrome()` + maximize + `WebDriverWait`) | 6×: `cria_fichas`, `lmr`, `apagar_lmr`, `upload_conditions`, `upload_tech_specs`, `upload_ficha_duplicada` |
| Pesquisar PMIB na lista + clicar no lápis de edição | 6 variantes: `apagar_lmr._pesquisar_e_abrir`, `tech_specs._pesquisar_e_abrir`, `upload_ficha_duplicada` (2×: Extrator e Injetor, idênticas), `upload_conditions.processar_lista` (inline), `cria_fichas.atualizar_projeto_em_massa`; `lmr` faz o mesmo com 24 TABs cegos |
| `safe_click` (scroll + JS click) | 4× idêntico: `apagar_lmr`, `upload_conditions`, `upload_tech_specs`, `upload_ficha_duplicada` |
| `safe_send_keys` (Ctrl+A, Backspace, digitar) | 3 variantes |
| Loop lixeira + CONFIRMAR (excluir linhas de tabela) | 3×: `apagar_lmr.executar_limpeza`, `tech_specs._excluir_linha_segura`, `InjetorFichaAlvo._limpar_caracteristicas_tecnicas` |
| Flag de parada (`cancel_requested`/`stop_flag` + `solicitar_parada`) | 4× |
| URL do portal hardcoded | 10+ ocorrências da mesma string |

### 1.2 Duplicação de Excel

| Lógica | Implementações hoje |
|---|---|
| Busca dinâmica da linha de cabeçalho | ~10×: `DataManager.carregar_planilha_inteligente`, `analyzer._find_header_columns`, `autospec.find_header_columns`, `upload_conditions.carregar_lookup_status` e `atualizar_status_excel`, `tech_specs.encontrar_header`, `search._encontrar_e_formatar_dataframe`, `GerenciadorFilaPMIB._encontrar_cabecalho`, `AtualizadorStatusPMIB`, `pmib_manager._ler_status_pmib` |
| Normalização do código PMIB (apóstrofo, zeros à direita `.ljust(4,'0')`, float→`:.4f`) | 6×: `upload_conditions` (2 lugares), `upload_ficha_duplicada` (2 lugares), `pdm_backend.processar_pastas_fichas`, `frontend` (`_start_web_from_file` e `_op2_executar`) |
| Marcar seção "COMPLETO" no `_STATUS_PMIB` | 3×: `upload_conditions.atualizar_status_excel`, `tech_specs.executar_pipeline_rpa` (inline), `AtualizadorStatusPMIB` |
| Retry de `PermissionError` (arquivo aberto no Excel) | 4 variantes de laço, cada uma com UX diferente |

### 1.3 Duplicação e rigidez de IA

| Problema | Onde |
|---|---|
| `genai.configure(transport='rest')` + `GenerativeModel` + retry | 5×: `analyzer`, `cria_fichas`, `upload_conditions`, `tech_specs` (+ `autospec` via LangChain) |
| Limpeza da resposta JSON (strip de ```` ```json ````, find `{`/`[`) | 4 variantes |
| `safety_settings` BLOCK_NONE | 2× copiado literal |
| Prompts gigantes embutidos em strings no meio do código | 5 módulos |
| `CONFIG_MAP` do layout da ficha técnica | **duplicado** em `analyzer_backend` e `autospec_backend` (ranges divergem: "H6:P6" vs "H6") |
| **Acoplamento total ao Gemini**: nomes de modelo hardcoded, sem abstração de provedor, sem medição de tokens/custo | todos os 5 módulos com IA |

### 1.4 Frontend monolítico

- `frontend.py` com ~2.400 linhas: 12 telas + 6 janelas + splash + app.
- Padrões repetidos ~12×: console + `log()` thread-safe (3 variantes de implementação!),
  janela de pausa de login (4 cópias), listbox de fichas com Adicionar/Remover/Limpar (2 cópias
  idênticas), seletor de arquivo com label de status e mudança de cor (20+ cópias), popup de
  seleção múltipla (4 variantes).
- Estado global de backends via `globals()` + splash com `importlib`.

### 1.5 Más otimizações e fragilidades

- `time.sleep()` fixo como sincronização primária do RPA (dezenas de ocorrências, 0.2s a 6s) —
  lento no caso bom, frágil no caso ruim. Playwright resolve isso nativamente (auto-wait).
- `pdm_backend.pdms_fromItaipu_lista_geral`: reabre a planilha geral INTEIRA para cada código
  novo (O(n·m) de I/O); `aplicar_templates_fichas` reabre o template por ficha.
- `except: pass` silencioso em dezenas de pontos — falhas do RPA somem sem registro.
- **Logs desiguais entre módulos**: `upload_tech_specs` e `pmib_manager` logam bem;
  `autospec`, `pdm` e `apagar_lmr` são lacônicos (sem resumo final, sem contexto do item,
  sem duração). Ver CP 4.4.
- Contrato `4500063671` hardcoded em regex (`upload_conditions`).
- Valores mágicos: linha 79 da ficha, linha 4 do STATUS, aba "Lista de Materiais" —
  espalhados como literais em 8 arquivos.
- `lmr_backend`: no `except` do loop interno o índice não avança → risco de loop infinito.
- **`upload_ficha_duplicada` frágil por concepção** (ver Fase 6): scraping de condições por
  listas de XPaths genéricos (`RadioButton1-input` aparece em mais de uma aba), injeção sem
  verificação de leitura de volta, documentos/imagens com fluxo incompleto (botão de modal
  comentado no código), sem retomada nem relatório por seção.
- Dependência de Windows não isolada (`xlwings`, `os.startfile`).
- Sem testes automatizados de nenhum tipo.

---

## 2. Arquitetura-alvo

```
SIG-FT/
├── sigft/
│   ├── __init__.py
│   ├── config.py               # chaves/planilhas/portal/constantes + mapa tarefa→modelo LLM
│   ├── core/
│   │   ├── excel/
│   │   │   ├── headers.py      # find_header_row(), find_columns() — ÚNICA implementação
│   │   │   ├── pmib_codes.py   # normalize_pmib() — ÚNICA implementação
│   │   │   ├── locking.py      # save_with_retry(wb, path, on_locked=callback)
│   │   │   └── status_sheet.py # classe StatusPMIB: carregar, lookup, marcar_completo(seções)
│   │   ├── llm/                # camada de IA MULTI-PROVEDOR (decisão de produto nº 2)
│   │   │   ├── client.py       # interface LLMClient + LLMResponse + factory get_llm(tarefa)
│   │   │   ├── providers/
│   │   │   │   ├── openai_compat.py  # base OpenAI-compatível (chat completions, base_url)
│   │   │   │   ├── openrouter.py     # GATEWAY PADRÃO: especializa openai_compat com
│   │   │   │   │                     #   catálogo GET /models + custo real por chamada
│   │   │   │   └── gemini.py         # caminho direto Google (free tier/comportamento atual)
│   │   │   ├── usage.py        # UsageTracker: tokens, custo real/estimado, módulo, tarefa
│   │   │   └── prompts.py      # todos os prompts como constantes nomeadas
│   │   ├── rpa/
│   │   │   ├── engine.py       # interface do motor de browser (agnóstica Selenium/Playwright)
│   │   │   ├── selenium_engine.py    # implementação atual (transitória)
│   │   │   ├── playwright_engine.py  # implementação-alvo (Fase 5)
│   │   │   ├── portal.py       # PMIBPortal: safe_click, safe_fill, pesquisar_e_abrir,
│   │   │   │                   #   clicar_salvar_visivel, excluir_linha_com_confirmacao,
│   │   │   │                   #   stop-flag, espera de login manual
│   │   │   └── ficha_layout.py # CONFIG_MAP unificado (fonte única do layout da ficha)
│   │   └── callbacks.py        # protocolo UI↔serviço: log estruturado/pause/ask/progress
│   ├── services/               # lógica de negócio (os atuais backends, magros)
│   └── app/                    # UI (mesmo estilo visual de hoje)
│       ├── main.py / splash.py / theme.py
│       ├── widgets/            # console.py, pickers.py, dialogs.py, module_frame.py
│       └── views/              # 12 telas finas
├── tests/                      # pytest para core/ (funções puras)
├── logs/                       # saída do UsageTracker e logs de execução (gitignored)
├── frontend.py                 # shim de compatibilidade → sigft.app.main (até Fase 7)
├── *_backend.py                # shims de compatibilidade → sigft.services.* (até Fase 7)
├── .claude/agents/             # doc-writer, refactor-executor
├── .claude/skills/             # sigft-novo-modulo, sigft-melhorar-modulo
└── docs/
```

**Princípios**:
1. **Uma implementação por conceito** — cabeçalho, código PMIB, portal, LLM.
2. **UI nunca contém regra de negócio; serviço nunca importa tkinter.** Comunicação só por
   callbacks (`log`, `pause`, `ask`, `progress`) definidos em `core/callbacks.py`.
3. **Nenhum serviço conhece Selenium/Playwright diretamente** — só `PMIBPortal`. É isso que
   torna a Fase 5 (Playwright) uma troca de motor, não uma reescrita dos serviços.
4. **Nenhum serviço conhece o SDK de um provedor de IA** — só `LLMClient`. Modelo/provedor
   vêm de `config.py` (mapa `tarefa → provedor+modelo`), trocáveis sem tocar no serviço.
5. **Seletores e fluxos do portal são intocáveis nas Fases 1–4.** Nas Fases 5–6 mudanças são
   permitidas, sempre validadas com o usuário contra o portal real.
6. **Compatibilidade por shims**: os nomes antigos continuam importáveis até a Fase 7.

---

## 3. Fases e Checkpoints

### Fase 0 — Salvaguardas (pré-requisito de tudo)

- **CP 0.1 — Estrutura e testes das funções puras.**
  Criar pacote `sigft/` vazio com `__init__.py`, pasta `tests/` e `pytest` no requirements
  (dev). Escrever testes caracterizando o comportamento ATUAL de: normalização de PMIB
  (casos: `'4500063671.105'`→`.1050`, float `4500063671.1165`, apóstrofo), `extrair_pdm_id`,
  `extract_pmib_code`, `limpar_pergunta`, `normalizar_texto`, `_limpar_texto_parrudo`.
  *Aceite*: `pytest -q` verde; nenhuma linha de produção alterada.

- **CP 0.2 — Smoke de importação.**
  Teste que importa todos os módulos `*_backend.py` (com mock de imports pesados quando
  preciso) e `python -m compileall .` num script `scripts/check.sh`.
  *Aceite*: script roda e passa.

### Fase 1 — Fundações core (Excel, config, callbacks)

- **CP 1.1 — `sigft/config.py`.**
  Centralizar: URL do portal, aba "Lista de Materiais", linha 79 das specs, prefixo de
  contrato (hoje `4500063671`, vira configurável), colunas-chave, carregamento de chaves
  (.env + api_config.json) **e o mapa de tarefas de IA** (`LLM_TASKS: tarefa → {provider,
  model}` — consumido de fato na Fase 3, mas já nasce aqui).
  *Aceite*: módulo importável + testes de carga de config.

- **CP 1.2 — `core/excel/pmib_codes.py` + `headers.py`.**
  Implementar `normalize_pmib()` e `find_header_row()`/`find_columns()` cobrindo os
  comportamentos das ~10 variantes. Migrar todos os consumidores.
  *Aceite*: testes do CP 0.1 passam contra a nova implementação; grep não encontra
  regex/ljust de PMIB fora de `pmib_codes.py`.

- **CP 1.3 — `core/excel/locking.py` + `status_sheet.py`.**
  `save_with_retry` unifica os 4 laços de PermissionError. `StatusPMIB` unifica: carregar
  lookup, buscar linha por PMIB, `marcar_completo(pmib, secoes)`. Migrar os 3 escritores de
  COMPLETO e os 4 laços de lock.
  *Aceite*: `upload_conditions`, `tech_specs`, `upload_ficha_duplicada` e `pmib_manager`
  usam a implementação única; UX preservada.

- **CP 1.4 — `core/callbacks.py` (inclui protocolo de log).**
  Dataclass/protocolo `UICallbacks(log, pause, ask, progress)`. O `log` já nasce estruturado:
  `log(msg, nivel="info", contexto=None)` — a UI atual imprime como hoje (`> msg`), mas o
  nível/contexto ficam disponíveis para o CP 4.4 e para gravação em arquivo. Padronizar a
  assinatura dos serviços (parâmetro único `callbacks`), com aliases retrocompatíveis.
  *Aceite*: 2 serviços migrados como piloto (`lmr`, `apagar_lmr`).

### Fase 2 — Camada RPA unificada (desenhada para a troca de motor)

> A Fase 2 ainda roda sobre Selenium, mas a API pública do `PMIBPortal` é definida em termos
> de intenção (`clicar`, `preencher`, `esperar_linha`, `pesquisar_e_abrir`), não de Selenium.
> É o contrato que a Fase 5 reimplementa em Playwright.

- **CP 2.1 — `core/rpa/engine.py` + `selenium_engine.py` + fábrica de driver.**
  Interface mínima do motor: `goto(url)`, `click(seletor)`, `fill(seletor, texto)`,
  `press(teclas)`, `wait_visible/clickable(seletor)`, `element_exists`, `get_value`,
  `screenshot`, `set_download_dir`. `selenium_engine` implementa com o comportamento atual
  (scroll + JS click etc.). Substitui as 6 inicializações de driver.
  *Aceite*: nenhuma chamada direta a `webdriver.Chrome()` fora de `selenium_engine.py`.

- **CP 2.2 — `core/rpa/portal.py` (classe `PMIBPortal` sobre o engine).**
  Mover, SEM alterar seletores: `safe_click`, `safe_fill` (ex-`safe_send_keys`),
  `check_or_uncheck`, `clicar_salvar_visivel`, `excluir_linha_com_confirmacao`,
  `pesquisar_e_abrir(pmib)` (variante mais robusta: a de `tech_specs`), stop-flag,
  `aguardar_login_manual(callback_pause)` e `ir_para_lista()`. Exceção autorizada: o fluxo
  de 24 TABs do `lmr_backend` é substituído por `pesquisar_e_abrir` (mesmo alvo final).
  *Aceite*: as 6 classes de automação usam `PMIBPortal`; `safe_click` existe em um único
  lugar; serviços não importam `selenium` diretamente (exceto exceptions, temporariamente).

- **CP 2.3 — Sincronização: sleeps → waits.**
  Trocar `time.sleep` por esperas com condição observável via o engine. Sleeps sem condição
  observável (animações OutSystems) viram constantes nomeadas em `portal.py`
  (`PAUSA_ANIMACAO = 0.5`). Módulo a módulo, um commit por módulo.
  *Aceite*: nenhum `time.sleep(` com literal numérico em `services/`; sleeps restantes
  centralizados e nomeados. (Na Fase 5 o auto-wait do Playwright elimina a maioria.)

- **CP 2.4 — `core/rpa/ficha_layout.py`.**
  Unificar os dois `CONFIG_MAP` (analyzer × autospec) em fonte única; consumidores derivam o
  que precisam. Incluir `VARIAVEIS_SPECS` e a linha 79 (de `config.py`).
  *Aceite*: `CONFIG_MAP` definido uma única vez; teste de equivalência com os dois mapas
  antigos (guardados como fixture).

### Fase 3 — Camada de IA multi-provedor + rastreamento de custos

> Objetivo (decisão de produto nº 2): o usuário troca o modelo **pela interface**; o
> OpenRouter é o gateway padrão (uma chave, catálogo amplo, custo real por chamada);
> Gemini direto e endpoint interno da empresa continuam disponíveis por config.
> Chaves: todas opcionais, uma necessária — `OPENROUTER_API_KEY` basta no dia a dia; a UI
> exibe apenas provedores com chave configurada.

- **CP 3.1 — `core/llm/client.py` + provedor Gemini direto.**
  Interface: `LLMClient.generate(prompt, *, system=None, json_mode=False, tags={}) ->
  LLMResponse(text, parsed_json, tokens_in, tokens_out, custo_usd|None, model, provider,
  duracao_s)`. Fábrica `get_llm(tarefa)` resolve provedor/modelo via `config.LLM_TASKS`
  (tarefas: `categorizar_pdm`, `validar_ficha`, `condicoes`, `tech_specs`, `autospec`).
  Retry, rate-limit opcional, parse/limpeza de JSON e safety_settings ficam AQUI, uma vez.
  O provedor Gemini direto reproduz o comportamento atual (transport REST, mesmos modelos
  default) — menor risco na migração e preserva o free tier do AI Studio.
  Migrar os 4 consumidores diretos do `google.generativeai`.
  *Aceite*: `genai.` só aparece em `providers/gemini.py`; nomes de modelo apenas em
  `config.py`; comportamento atual preservado (mesmos modelos default de hoje).

- **CP 3.2 — Gateway OpenRouter (padrão) + endpoint OpenAI-compatível genérico.**
  `providers/openai_compat.py` (pacote `openai`, `base_url` configurável) e
  `providers/openrouter.py` como especialização: `base_url=https://openrouter.ai/api/v1`,
  headers de atribuição, catálogo de modelos via `GET /models` (com cache local) e
  `usage: {include: true}` para receber o CUSTO REAL de cada chamada na resposta.
  O adaptador genérico cobre a futura IA interna da empresa (`EMPRESA_LLM_BASE_URL` +
  `EMPRESA_LLM_API_KEY`) e qualquer provedor direto OpenAI-compatível. Campos de chave na
  Home (mesmo padrão visual das atuais).
  **Decisão (2026-07-24): LangChain foi avaliado como camada central e descartado** — o
  padrão de uso do SIG-FT é chamada única prompt→JSON (sem chains/agentes/memória); o
  mapeamento das ações de IA é garantido pelo funil único `LLMClient`+`UsageTracker` (com
  custo real via OpenRouter, que o LangChain não fornece); e o framework encareceria o
  empacotamento PyInstaller. Portanto, neste checkpoint o uso residual de LangChain no
  `autospec` é REMOVIDO (substituído por chamada direta via `LLMClient`), junto com as
  dependências `langchain-*` do requirements. LangChain/LangGraph fica reservado como
  opção futura APENAS se surgirem fluxos agênticos multi-etapas — a fábrica `get_llm()`
  isola essa porta.
  *Aceite*: a mesma tarefa roda em ≥2 modelos distintos via OpenRouter mudando apenas
  config; recursos usados hoje no Gemini validados no caminho OpenRouter (JSON mode via
  `response_format`, system prompt, comportamento de safety) com diferenças registradas
  em PENDENCIAS.

- **CP 3.3 — Seleção de modelo NA INTERFACE.**
  Painel "Modelos de IA" na Home (mesmo estilo dos cards existentes): dropdown de
  provedor/modelo GLOBAL (default para todas as tarefas) + modo avançado com override POR
  TAREFA (as 5 tarefas de `LLM_TASKS`). Fonte da lista: catálogo do OpenRouter quando a
  chave existir, filtrado por uma lista curada de favoritos em config (para não exibir
  400+ modelos), com campo livre para id manual. Persistência em `api_config.json`; efeito
  imediato, sem reiniciar o app. Provedores sem chave configurada não aparecem.
  *Aceite*: trocar o modelo na UI muda a próxima chamada (verificável no registro de uso);
  seleção sobrevive a reinício do app.

- **CP 3.4 — `core/llm/usage.py` (rastreamento de uso e custos).**
  Cada `generate()` grava um registro JSONL em `logs/llm_usage.jsonl`: timestamp, provedor,
  modelo, módulo (tag), tarefa, tokens de entrada/saída, custo (REAL vindo do OpenRouter
  quando disponível; senão ESTIMADO pela tabela de preços editável em `config.py`, marcado
  como estimativa), duração, sucesso/erro. Relatório agregado: `usage_report()` (por
  módulo, por modelo, por dia) + card "Gastos de IA" na Home.
  *Aceite*: rodar qualquer módulo com IA gera registros; o relatório responde "qual modelo
  gasta mais na mesma tarefa" e "qual módulo do SIG-FT gasta mais"; chamadas via OpenRouter
  registram custo real (não estimado).

- **CP 3.5 — `core/llm/prompts.py`.**
  Extrair os 5 prompts gigantes para constantes nomeadas com funções de montagem.
  *Aceite*: nenhum prompt >15 linhas dentro de `services/`; teste de snapshot prova que o
  prompt gerado é idêntico ao antigo.

### Fase 4 — Serviços

- **CP 4.1 — Mover backends para `sigft/services/` com shims.**
  Um commit por módulo, na ordem: `apagar_lmr` → `lmr` → `search` → `pdm` → `translator` →
  `analyzer` → `autospec` → `cria_fichas` → `upload_conditions` → `tech_specs` →
  `ficha_duplicada` (como está — a reconstrução é na Fase 6) → `pmib_manager`.
  *Aceite*: app abre pela splash normalmente; smoke de importação verde.

- **CP 4.2 — Limpeza de exceções.**
  Substituir `except: pass` por `except Exception as e: callbacks.log(..., nivel="warn")` ou
  exceção específica, usando a base de conhecimento para decidir onde silêncio era
  intencional. Corrigir o não-incremento de índice do `lmr` no except (com `ask` ao usuário).
  *Aceite*: grep de `except: pass` zerado em `services/` e `core/` (exceções mantidas de
  propósito documentadas em PENDENCIAS.md).

- **CP 4.3 — Otimizações de I/O do `pdm`.**
  `pdms_fromItaipu_lista_geral`: abrir a origem 1×; `aplicar_templates_fichas`: carregar o
  template 1× (reabrir de `BytesIO`).
  *Aceite*: saída byte-idêntica em fixture sintética; tempo medido menor.

- **CP 4.4 — Padronização e enriquecimento dos logs de saída (decisão de produto nº 4).**
  Todo serviço passa a logar segundo o padrão único:
  1. **Início de lote**: o que vai fazer, com quantos itens, com quais arquivos/config.
  2. **Por item**: identificador (PMIB/arquivo), etapa atual, resultado (✅/⚠️/❌ + motivo),
     duração quando relevante.
  3. **Avisos** sempre com causa e consequência ("campo X rejeitado pelo site → preencher
     manualmente").
  4. **Resumo final obrigatório**: N sucessos, N falhas (listadas), N pulados (com motivo),
     tempo total.
  5. Espelho opcional em arquivo `logs/sigft_YYYYMMDD.log` (útil para auditoria).
  Prioridade para os módulos hoje pobres: `autospec`, `pdm`, `apagar_lmr`, `translator`,
  `search`. Usar o `log(msg, nivel, contexto)` do CP 1.4.
  *Aceite*: os 12 serviços emitem início/por-item/resumo; revisão manual de uma execução
  simulada de cada um (dry-run onde couber).

### Fase 5 — Migração do RPA para Playwright (decisão de produto nº 5)

> Pré-requisito: Fase 2 completa. Estratégia: implementar `playwright_engine.py` com a MESMA
> interface do engine; migrar módulo a módulo com **validação assistida pelo usuário** contra
> o portal real (não há como testar offline). Seletores XPath atuais são reaproveitados no
> primeiro momento (Playwright aceita XPath); melhorias de seletor (role/text/css) só depois
> que o módulo estiver estável no motor novo.

- **CP 5.1 — `playwright_engine.py` + login manual + piloto.**
  Adicionar `playwright` ao requirements; engine com contexto persistente e modo headed;
  `aguardar_login_manual` mantém o fluxo atual (janela da UI libera o robô). Config
  `RPA_ENGINE = "selenium" | "playwright"` por módulo (permite migração gradual e rollback
  imediato). Piloto: `apagar_lmr` (menor risco, fluxo simples e reversível de testar).
  *Aceite*: `apagar_lmr` roda em Playwright de ponta a ponta, **validado pelo usuário em
  sessão real**; rollback por config demonstrado.

- **CP 5.2 — Migrar leitura/edição simples: `lmr` e `cria_fichas` (edição em massa).**
  *Aceite*: validação assistida pelo usuário; flag de engine por módulo atualizada.

- **CP 5.3 — Migrar uploads: `upload_conditions` e `upload_tech_specs`.**
  Atenção especial ao `_preencher_input_com_auditoria` (injeção JS) — em Playwright usar
  `fill` + verificação de valor; manter o fallback de aviso de pendência manual.
  *Aceite*: validação assistida pelo usuário nas 4 abas de condições e na tabela de
  características (com paginação).

- **CP 5.4 — Migrar criação de fichas (`cria_fichas.processar_item_individual`).**
  O fluxo por TAB/active_element é o mais frágil do sistema; reimplementar com seletores
  diretos onde o usuário confirmar que o alvo é estável, mantendo a sequência atual como
  referência de comportamento.
  *Aceite*: criação de 1 ficha de teste real acompanhada pelo usuário, com resumo comparado
  (PMIB criado, PDM final capturado).

- **CP 5.5 — Descomissionar Selenium.**
  Remover `selenium_engine.py`, dependência do requirements e a flag por módulo (Playwright
  vira único motor). Atualizar docs e skills.
  *Aceite*: grep de `selenium` zerado no código; app completo funcional.

### Fase 6 — Reconstrução do módulo `ficha_duplicada` (decisão de produto nº 1)

> Não é refatoração: é redesenho com comportamento novo autorizado. Construído já sobre
> Playwright (pré-requisito: CP 5.1; ideal: Fase 5 completa). O modo de trabalho aqui é
> **iterativo com o usuário**: cada checkpoint termina numa sessão de teste conjunta no
> portal real, e o feedback vira insumo do checkpoint seguinte.

**Fluxo-alvo (descrito pelo usuário)**: no `_STATUS_PMIB`, identificar quais fichas são
duplicadas e qual é a ficha de referência original de cada uma; no portal PMIB, coletar as
informações necessárias da ficha original; replicar essas informações na ficha duplicada.

- **CP 6.1 — Especificação executável + revisão da identificação.**
  Escrever `docs/refatoracao/ESPEC_FICHA_DUPLICADA.md` respondendo com o usuário: (a) como a
  duplicidade é marcada hoje na planilha (marcador `PDM.9900.000`? coluna própria? padronizar?);
  (b) quais seções replicar e em que ordem (Info Gerais, Fornecedores, Condições,
  Características, Documentos, Imagens); (c) o que NUNCA copiar (código PMIB próprio, projeto?);
  (d) política de conflito quando a ficha alvo já tem dados. Implementar SÓ a identificação
  da fila (parser do `_STATUS_PMIB`) com tela de revisão/edição (aproveitar
  `JanelaSelecaoDuplicadas`/`JanelaRevisaoEdicao` padronizadas).
  *Aceite*: dry-run (sem portal) sobre o `_STATUS_PMIB` real do usuário lista a fila correta,
  confirmada por ele.

- **CP 6.2 — Extração robusta da ficha original.**
  Reescrever o extrator sobre `PMIBPortal`/Playwright: leitura seção a seção com seletores
  ancorados por aba (eliminar a ambiguidade atual de `RadioButton1-input` repetido entre
  abas), log rico do que foi lido, e **modo inspeção**: opção de pausar após cada seção para
  o usuário conferir na tela o que foi capturado.
  *Aceite*: sessão real com o usuário extraindo 1–2 fichas; dump JSON do extraído conferido.

- **CP 6.3 — Injeção com verificação (read-back) e modo passo a passo.**
  Replicar seção a seção; após salvar cada seção, reler os campos e comparar com o extraído;
  divergências viram pendências no log. Modo passo a passo opcional (pausa entre seções para
  o usuário validar/ajustar), além do modo contínuo.
  *Aceite*: clonagem completa de 1 ficha real com o usuário acompanhando; relatório de
  divergências vazio ou justificado.

- **CP 6.4 — Documentos, imagens e conclusão.**
  Resolver o fluxo hoje incompleto de associar documentos (fechar modal/confirmar) e upload
  de imagens (FilePond) — mapear com o usuário na tela real. Atualizar `_STATUS_PMIB`
  (seções COMPLETO via `StatusPMIB`) e emitir o resumo final padrão (CP 4.4). Retomada: fila
  persiste progresso para continuar de onde parou.
  *Aceite*: lote pequeno (2–3 fichas) processado de ponta a ponta com o usuário; base de
  conhecimento (`07-upload-ficha-duplicada.md`) reescrita para o módulo novo.

### Fase 7 — UI (padronizar mantendo o estilo existente — decisão de produto nº 3)

> Regra da fase: **zero redesign**. A referência visual é o app de hoje: paleta `COLORS`
> (GE Vernova: primary #035D67, accent #00C975, sidebar #161616, background #212121),
> fonte Roboto, módulos com header + conteúdo + console, botões de arquivo que ficam verdes
> quando selecionados. Onde houver variação entre módulos, padronizar para o padrão
> dominante — não inventar um novo.

- **CP 7.1 — `app/theme.py` + `widgets/console.py` + `module_frame.py`.**
  `ConsoleFrame` com `log()` thread-safe único (conectado ao protocolo do CP 1.4);
  `ModuleFrame` base (header/content/console/progresso). Migrar 2 telas piloto
  (`ApagarLMR`, `Translator`).
  *Aceite*: comparação lado a lado com screenshots — telas piloto visualmente idênticas.

- **CP 7.2 — `widgets/pickers.py` + `widgets/dialogs.py`.**
  `FilePickerRow`, `FolderPickerRow`, `FileQueueList`, `PausaLoginDialog`,
  `RetryLockDialog`, `SelecaoMultiplaDialog`, `DataFrameSelecaoDialog` (substituem as 6
  `Janela*` e as cópias). Mesmo comportamento e aparência atuais.
  *Aceite*: as 4 cópias da janela de login e as 2 do FileQueueList substituídas; estilo
  preservado.

- **CP 7.3 — Quebrar `frontend.py` em `app/views/*.py`.**
  Uma view por arquivo; `app/main.py` monta sidebar e registra views; splash simplificada.
  *Aceite*: `python -m sigft.app.main` abre o app idêntico ao atual; `frontend.py` vira shim.

### Fase 8 — Qualidade contínua

- **CP 8.1 — Lint (`ruff`)**: *Aceite*: `ruff check .` verde.
- **CP 8.2 — Type hints** nas APIs públicas de `core/` e `services/`; `mypy` leniente verde
  em `core/`.
- **CP 8.3 — Empacotamento**: spec do PyInstaller versionado (incluindo browsers do
  Playwright no bundle — atenção: `playwright install` no build), README de build.
- **CP 8.4 — Isolamento Windows**: `xlwings`/`os.startfile` atrás de `core/platform.py`.

---

## 4. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| RPA não testável offline (portal OutSystems real) | Fases 1–4 não tocam seletores; Fases 5–6 têm validação assistida pelo usuário como critério de aceite formal de CADA checkpoint |
| Migração Playwright quebrar módulo em produção | Flag `RPA_ENGINE` por módulo (CP 5.1) permite rollback instantâneo para Selenium até o CP 5.5 |
| IDs OutSystems (`b10-...`) mudarem em deploy do portal | Seletores centralizados em `portal.py`/serviços facilitam conserto; Playwright trace/screenshot em falha ajuda diagnóstico |
| Custo de IA divergir do real | Via OpenRouter o custo REAL vem na resposta de cada chamada; tabela de preços editável só para provedores diretos, com custo marcado como "estimado" |
| Dados técnicos passando por intermediário (OpenRouter) | Caminhos diretos (Gemini nativo / IA da empresa) continuam disponíveis por config — a escolha por tarefa é do usuário para conteúdo sensível |
| Recursos do Gemini se comportarem diferente via OpenRouter (JSON mode, safety) | CP 3.2 valida recurso a recurso antes de virar padrão; divergências em PENDENCIAS; rollback por config para o provedor direto |
| Dependência de disponibilidade do OpenRouter | Provedor direto Gemini permanece implementado como contingência; troca é uma linha de config/UI |
| Regressão silenciosa no Excel | Testes de caracterização (CP 0.1) antes de mover; fixtures sintéticas |
| App quebrar no meio da migração | Shims mantêm todos os nomes antigos importáveis até o CP 7.3 |

## 5. Fora de escopo (registrar, não fazer agora)

- Banco de dados no lugar das planilhas.
- Login automático no portal (continua manual, por design — Playwright mantém a pausa).
- Internacionalização da UI.

---

## 6. Status dos Checkpoints

| Checkpoint | Status | Data | Observações |
|---|---|---|---|
| 0.1 Testes de caracterização | ☐ pendente | | |
| 0.2 Smoke de importação | ☐ pendente | | |
| 1.1 config.py (+ mapa LLM_TASKS) | ☐ pendente | | |
| 1.2 pmib_codes + headers | ☐ pendente | | |
| 1.3 locking + status_sheet | ☐ pendente | | |
| 1.4 callbacks + protocolo de log | ☐ pendente | | |
| 2.1 engine + selenium_engine | ☐ pendente | | |
| 2.2 PMIBPortal | ☐ pendente | | |
| 2.3 sleeps → waits | ☐ pendente | | |
| 2.4 ficha_layout unificado | ☐ pendente | | |
| 3.1 LLMClient + Gemini direto | ☐ pendente | | |
| 3.2 OpenRouter (gateway padrão) + endpoint empresa | ☐ pendente | | |
| 3.3 seletor de modelo na interface | ☐ pendente | | |
| 3.4 UsageTracker (custo real/estimado) | ☐ pendente | | |
| 3.5 prompts.py | ☐ pendente | | |
| 4.1 services + shims | ☐ pendente | | |
| 4.2 limpeza de exceções | ☐ pendente | | |
| 4.3 otimizações pdm | ☐ pendente | | |
| 4.4 padronização de logs | ☐ pendente | | |
| 5.1 Playwright engine + piloto apagar_lmr | ☐ pendente | | validação com usuário |
| 5.2 Playwright: lmr + edição em massa | ☐ pendente | | validação com usuário |
| 5.3 Playwright: uploads | ☐ pendente | | validação com usuário |
| 5.4 Playwright: criação de fichas | ☐ pendente | | validação com usuário |
| 5.5 remover Selenium | ☐ pendente | | |
| 6.1 espec ficha_duplicada + identificação | ☐ pendente | | sessão com usuário |
| 6.2 extração robusta | ☐ pendente | | sessão com usuário |
| 6.3 injeção com read-back | ☐ pendente | | sessão com usuário |
| 6.4 documentos/imagens + conclusão | ☐ pendente | | sessão com usuário |
| 7.1 theme/console/module_frame | ☐ pendente | | estilo atual preservado |
| 7.2 pickers + dialogs | ☐ pendente | | estilo atual preservado |
| 7.3 views + main | ☐ pendente | | |
| 8.1 ruff | ☐ pendente | | |
| 8.2 type hints | ☐ pendente | | |
| 8.3 PyInstaller (+ Playwright no bundle) | ☐ pendente | | |
| 8.4 isolamento Windows | ☐ pendente | | |

## 7. Notas da transcrição inicial (já aplicadas no bootstrap)

- As 4 chaves de API que estavam hardcoded na `HomeView` foram removidas (usar `.env` /
  `api_config.json`). **As chaves expostas devem ser rotacionadas.**
- `ModuloCriaFichas` tinha um par morto de `run_edicao_thread`/`_edicao_worker` (referenciava
  `self.text_lista_pmibs`, inexistente, e era sobrescrito pela definição posterior). Apenas a
  versão operante foi mantida na transcrição.
