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
7. **Memória de caminhos nos diálogos de arquivo + pastas padrão configuráveis** (definida
   em 2026-07-24, ver CP 1.5): cada diálogo abre na última pasta usada PARA AQUELE TIPO DE
   ARQUIVO/CAMPO (ex.: no AutoSpec, o seletor de ficha Excel abre na pasta do último Excel;
   o de manuais abre na pasta do último PDF — sem vai-e-vem entre pastas). Além disso,
   pastas de trabalho conhecidas vêm pré-configuradas como padrão, editáveis pela UI:
   `<home>/Box/CMI - Consórcio Itaipu/11 - Ger. Engenharia/15 - PDM/SOBRESSALENTES - PMIB`
   (fichas/STATUS), `.../15 - PDM/PDMs modificados` (PDMs modificados) e
   `.../15 - PDM/Templates` (template da ficha) — armazenadas relativas ao home do usuário
   para funcionar em qualquer máquina com Box.

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
│   │   ├── callbacks.py        # protocolo UI↔serviço: log estruturado/pause/ask/progress
│   │   └── prefs.py            # user_prefs.json: memória de últimos caminhos + pastas padrão
│   ├── services/               # lógica de negócio (os atuais backends, magros)
│   └── app/                    # UI (mesmo estilo visual de hoje)
│       ├── main.py / splash.py / theme.py
│       ├── file_dialogs.py     # wrappers do filedialog com memória de caminho (CP 1.5)
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
  model}` + `LLM_DEFAULT` — consumido de fato na Fase 3, mas já nasce aqui). Os valores de
  `LLM_DEFAULT`/`LLM_TASKS` e a tabela de preços seguem **`docs/refatoracao/MODELOS_IA.md`**
  (padrão global: Gemini 3 Flash Preview; override pré-semeado: `categorizar_pdm` em Grok 4.5).
  *Aceite*: módulo importável + testes de carga de config.

- **CP 1.2 — `core/excel/pmib_codes.py` + `headers.py`.**
  Implementar `normalize_pmib()` e `find_header_row()`/`find_columns()` cobrindo os
  comportamentos das ~10 variantes. Migrar todos os consumidores. Inclui a unificação de
  `extract_pmib_code(caminho)` com **`os.path.basename()` antes do regex** — decisão do
  arquiteto para o bug latente encontrado no CP 0.1 (o comportamento correto é o do
  `autospec`; o teste de caracterização do analyzer é atualizado INTENCIONALMENTE aqui,
  documentando a correção).
  *Aceite*: testes do CP 0.1 passam contra a nova implementação (com a exceção intencional
  acima); grep não encontra regex/ljust de PMIB fora de `pmib_codes.py`.

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

- **CP 1.5 — Memória de caminhos + pastas padrão (decisão de produto nº 7).**
  Dois módulos novos:
  1. `sigft/core/prefs.py` (puro, sem tkinter): estado persistido em `user_prefs.json` na
     raiz (**gitignored** — é por usuário/máquina). API: `get_initial_dir(chave, categoria)`,
     `remember_dir(chave, categoria, caminho)`, `get_default_dir(nome)`,
     `set_default_dir(nome, caminho)`. Ordem de resolução do diretório inicial:
     último da CHAVE específica (ex.: `autospec.manuais`) → último da CATEGORIA
     (`excel`/`pdf`/`json`/`pasta`) → pasta padrão mapeada para a chave → comportamento
     atual do sistema. Após seleção bem-sucedida, grava chave + categoria.
  2. `sigft/app/file_dialogs.py` (lado UI): wrappers `ask_open_file`, `ask_open_files`,
     `ask_save_file`, `ask_directory` que envelopam o `filedialog` aplicando a resolução
     acima e o `remember` na saída.
  Pastas padrão semeadas RELATIVAS AO HOME (`Path.home() / "Box" / "CMI - Consórcio
  Itaipu" / "11 - Ger. Engenharia" / "15 - PDM" / ...`): `sobressalentes_pmib`
  (SOBRESSALENTES - PMIB → STATUS/fichas), `pdms_modificados` (PDMs modificados) e
  `templates_ficha` (Templates). Só são usadas se existirem no disco; editáveis num painel
  "Pastas padrão" na Home (mesmo estilo dos cards). Aplicação imediata no frontend atual
  (plano): substituir TODAS as chamadas diretas de `filedialog.*` pelos wrappers, com
  chave por campo; pré-preencher os campos de pasta do `ModuloPDM` (`caminho_destino` ←
  `pdms_modificados`; diálogo de template ← `templates_ficha`; STATUS/fichas ←
  `sobressalentes_pmib`) quando as pastas existirem.
  *Aceite*: grep de `filedialog.` zerado fora de `file_dialogs.py`; cenário AutoSpec
  validado (Excel abre na pasta do último Excel, PDF na do último PDF, na mesma sessão e
  após reiniciar o app); campos do ModuloPDM pré-preenchidos quando os padrões existem;
  `user_prefs.json` no `.gitignore`; testes de resolução de diretório em `tests/`.

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
  `config.py`; comportamento atual preservado (mesmos modelos default de hoje —
  gemini-3.5-flash / gemini-3.1-pro-preview). **A troca para os defaults econômicos de
  `MODELOS_IA.md` NÃO acontece aqui** — este CP é refatoração pura (equivalência provável);
  a mudança de modelo é feita e validada no CP 3.3.

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
  imediato, sem reiniciar o app. Provedores sem chave configurada não aparecem. **A lista
  curada de favoritos e os defaults aplicados aqui vêm de `MODELOS_IA.md`** (padrão global
  Gemini 3 Flash Preview; `categorizar_pdm` em Grok 4.5; MiniMax M3 como economia máxima
  opt-in). Como isto substitui os modelos premium do
  CP 3.1 por opções mais baratas, o checkpoint só é dado por concluído após o usuário validar
  a qualidade num punhado de fichas (A/B contra o modelo anterior) — sem downgrade silencioso.
  *Aceite*: trocar o modelo na UI muda a próxima chamada (verificável no registro de uso);
  seleção sobrevive a reinício do app; usuário confirmou a qualidade dos defaults econômicos
  numa amostra.

- **CP 3.4 — `core/llm/usage.py` (rastreamento de uso e custos).**
  Cada `generate()` grava um registro JSONL em `logs/llm_usage.jsonl`: timestamp, provedor,
  modelo, módulo (tag), tarefa, tokens de entrada/saída, custo (REAL vindo do OpenRouter
  quando disponível; senão ESTIMADO pela tabela de preços editável em `config.py` — seed
  inicial na seção 2 de `MODELOS_IA.md`, marcado como estimativa), duração, sucesso/erro.
  Relatório agregado: `usage_report()` (por
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
  `Janela*` e as cópias). Mesmo comportamento e aparência atuais. Os pickers usam
  nativamente a memória de caminhos do CP 1.5 (cada `FilePickerRow` declara sua
  chave/categoria — a memória vira comportamento embutido, não chamada manual).
  *Aceite*: as 4 cópias da janela de login e as 2 do FileQueueList substituídas; estilo
  preservado; nenhuma view chama `file_dialogs` diretamente para campos que usam picker.

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
| 0.1 Testes de caracterização | ✅ concluído | 2026-07-24 | 50 testes em `tests/` (6 arquivos) cobrindo `extrair_pdm_id`, `_limpar_texto_parrudo`, `normalizar_texto`/`limpar_pergunta` (2 classes), `extract_pmib_code` (analyzer + autospec, com divergência documentada) e `_blindar_numero_pmib` (normalizador PMIB canônico, 3 casos do plano); imports pesados (pandas/openpyxl/selenium/google-generativeai/langchain*/llama_parse/PyPDF2/bs4) stubados via `unittest.mock` em `tests/conftest.py`; `pytest -q` verde (50 passed); nenhuma linha de produção alterada |
| 0.2 Smoke de importação | ✅ concluído | 2026-07-24 | smoke importa os 12 módulos backend via conftest stubado; scripts/check.sh roda compileall + pytest; script verde |
| 1.1 config.py (+ mapa LLM_TASKS) | ✅ concluído | 2026-07-24 | `sigft/config.py` criado (aditivo — nenhum consumidor migrado): `PORTAL_URL`, `GOOGLE_CSE_ENDPOINT`, `ABA_LISTA_MATERIAIS`(+3 variantes), `PREFIXO_CONTRATO`, `LINHA_SPECS_FICHA`=79, `LINHA_STATUS_PMIB`=4, 6 colunas-chave (`COL_CODIGO_PMIB` etc.), `carregar_chaves()`/`get_key()` replicando `SIG_FT_App.load_keys()` (.env + api_config.json; `ENV_VAR_POR_CHAVE`), import de `dotenv` defensivo. Modelos de IA reconciliados com `MODELOS_IA.md`: `LLM_DEFAULT` (Gemini 3 Flash Preview) + `LLM_TASKS` decididos (`categorizar_pdm` em Grok 4.5) + `LLM_MODELOS_HOJE` (baseline de equivalência do CP 3.1: gemini-3.5-flash/3.1-pro-preview) + `LLM_PRECOS_USD_POR_1M` (seed do CP 3.4); `get_task_config()` com erro claro p/ tarefa desconhecida. 40 testes em `tests/test_config.py`; `scripts/check.sh` verde. (Reconciliação de 2 sessões: mantido este `config.py` de caracterização + puxadas as decisões/`MODELOS_IA.md`/CP 1.5 da branch `itaipu-delivery-refactor`.) |
| 1.2 pmib_codes + headers | ✅ concluído | 2026-07-24 | `sigft/core/{__init__,excel/__init__}.py` + `core/excel/pmib_codes.py` (`normalize_pmib` canônico = `_blindar_numero_pmib`, sem truncar; `extract_pmib_code` com `os.path.basename()` antes do regex — corrige o bug do analyzer; + `extract_pmib_code_full`/`find_pmib_code_in_text`/`extract_contract_pmib_code` p/ zerar todo regex de PMIB fora do módulo) + `core/excel/headers.py` (`find_header_row` 0-based/pandas, `find_columns` 1-based/openpyxl com aliases e chaves opcionais, `rows_from_worksheet`) — só stdlib. Migrados os 10 consumidores de produção (`analyzer_backend`, `autospec_backend`, `upload_conditions_backend`, `upload_tech_specs_backend`, `upload_ficha_duplicada`, `search_pmib_backend`, `pmib_manager_backend`, `cria_fichas_no_pmib_v1_backend`, `pdm_backend`, `frontend`), cobrindo as ~11 buscas de cabeçalho e os 6 sites de normalização PMIB do diagnóstico (+ `DataManager.atualizar_excel_final`, não listado explicitamente). Testes do CP 0.1 passam intactos, exceto os 2 atualizados intencionalmente (bug do analyzer corrigido → convergência com autospec, mesmo cenário de entrada). 60 testes novos (`test_pmib_codes.py` 33 + `test_headers.py` 27); suíte total 162 passed (102 do CP 0.1/0.2/1.1 + 60); `scripts/check.sh` verde; grep de `ljust(4`/regex de PMIB (`\d{10}\.`) fora de `pmib_codes.py` limpo em toda a árvore (só comentários/docstrings citando o histórico, em `tests/`). |
| 1.3 locking + status_sheet | ✅ concluído | 2026-07-24 | `sigft/core/excel/locking.py` (`save_with_retry(wb, path, on_locked=, max_attempts=, sleep_seconds=, sleep_fn=, logger=)`, só stdlib) unifica os 4 laços/7 ocorrências de `PermissionError` do diagnóstico (INTERATIVO via `callback_ask`; INTERATIVO via `callback_retry_lock`; AUTO-RETRY sleep fixo sem limite; LOG+SAI sem retry) — contrato: `on_locked` decide por tentativa (`True`=retenta já, `False`/falsy=RE-LEVANTA `PermissionError` p/ o `except` original do chamador, `None`=política default log+sleep_fn); `max_attempts` é teto de segurança checado ANTES de `on_locked`. `sigft/core/excel/status_sheet.py` (`StatusPMIB`: `abrir`/`buscar_linha`/`marcar_linha`/`salvar`/`fechar`/`marcar_completo`, openpyxl só via import preguiçoso dentro de `abrir()` ou `ws` injetada) unifica achar coluna (via `headers` do CP 1.2), achar linha por PMIB (via `pmib_codes.normalize_pmib` do CP 1.2) e marcar "COMPLETO". Migrados: `upload_conditions_backend` (`atualizar_status_excel` INTERATIVO + `anexar_a_arquivo_existente` LOG+SAI via adaptador `SimpleNamespace` p/ `df.to_excel`), `upload_tech_specs_backend` (`executar_pipeline_rpa` ganhou retry pela 1ª vez — não tinha nenhum antes), `upload_ficha_duplicada` (`AtualizadorStatusPMIB.atualizar_ficha_concluida` AUTO-RETRY), `cria_fichas_no_pmib_v1_backend` (`atualizar_excel_final` LOG+SAI), `pmib_manager_backend` (2 laços INTERATIVOS unificados num helper `_salvar_com_retry_interativo`); `GerenciadorFilaPMIB.montar_fila_processamento` (upload_ficha_duplicada) mantido intocado — protege uma LEITURA, não um save (documentado). 42 testes novos (`test_locking.py` 13 + `test_status_sheet.py` 29; smoke de importação dos 5 backends migrados já existente desde o CP 0.2 continua verde); suíte total 162 (CP 0.1-1.2) + 42 = 204 passed; `scripts/check.sh` verde; dry-run funcional (fora da suíte) validou fiação real das 5 migrações com workbook/worksheet falsos. 6 pendências novas registradas em PENDENCIAS.md (nota de comportamento carrega-1x/retenta-N do save_with_retry, escopo de `montar_fila_processamento` não migrado, escopo de `carregar_lookup_status`/`_ler_status_pmib` não migrados p/ StatusPMIB, laço de retry duplicado descoberto em `frontend.ModuloCriaFichas.salvar_excel` fora de escopo, `wb.close()` novo em tech_specs, normalização mais tolerante do PMIB em tech_specs). |
| 1.4 callbacks + protocolo de log | ✅ concluído | 2026-07-24 | `sigft/core/callbacks.py` criado (só stdlib): dataclass `UICallbacks(log, pause, ask, progress)` — `log(msg, nivel="info", contexto=None)` obrigatório; `pause`/`ask`/`progress` viram no-op seguros via `__post_init__` quando ausentes (`ask()` sem provedor devolve `False`, reproduzindo o comportamento de hoje quando `callback_ask` está ausente) — corpo dos serviços chama `callbacks.log/ask/pause/progress(...)` sem nenhum `if callback_x:` espalhado. `from_legacy(callback_log=, callback_ask=, callback_pause=, callback_progress=)` adapta as assinaturas antigas (inclui a inversão de ordem `callback_ask(titulo, pergunta)` → `ask(pergunta, *, titulo=)`); `callback_input` (texto livre) FICA DE FORA do protocolo por decisão do arquiteto (pendência registrada). 2 pilotos migrados: `apagar_lmr_backend.executar_limpeza` e `lmr_backend.processar_lista`/`_processar_ficha_lmr_interna` (+ novo método privado `_resolver_linha_inicial`, extraído para isolar em teste o único trecho do fluxo alcançável sem Selenium) ganham `callbacks: UICallbacks \| None = None` mantendo os kwargs antigos como alias retrocompatível (`callbacks = callbacks or from_legacy(...)`); nenhum seletor/URL/ordem de interação do RPA foi tocado. `frontend.py` NÃO foi modificado e continua chamando exatamente como antes (`auto.processar_lista(selecionados, df_completo, callback_log=cb_log, callback_ask=cb_ask, callback_input=cb_input)` e `auto.executar_limpeza(pmib, callback_log=cb_log)`). 32 testes novos (`test_callbacks.py` 12 + `test_lmr_backend_migration.py` 15 + `test_apagar_lmr_backend_migration.py` 5); suíte total 204 (CP 1.3) + 32 = 236 passed; `scripts/check.sh` verde (compileall + pytest, smoke de importação dos 12 backends continua passando). |
| 1.5 memória de caminhos + pastas padrão | ✅ concluído | 2026-07-27 | **1ª metade (aditiva)**: `sigft/core/prefs.py` (só stdlib — `json`/`os`/`pathlib`) e `sigft/app/file_dialogs.py` (novo pacote `sigft/app/`, com `__init__.py`) prontos e testados; **migração de `frontend.py` pendente (próxima etapa)**. `prefs.py`: estado `user_prefs.json` na raiz (`.gitignore` já cobria), estrutura `{"ultimos": {chave: pasta}, "categorias": {categoria: pasta}, "pastas_padrao": {nome: pasta_custom}}`, `config_path` parametrizável em toda função pública (`tmp_path`-testável, espelha `config.CONFIG_FILE`), arquivo ausente/corrompido/seção com tipo inesperado -> estado vazio sem exceção. `get_initial_dir(chave, categoria, *, config_path=)` resolve ultimos[chave] -> categorias[categoria] -> pasta padrão da chave (via `PASTAS_PADRAO_POR_CHAVE`) -> `None`, validando `os.path.isdir` em CADA camada (candidato morto é pulado, cai pra próxima). `remember_dir(chave, categoria, caminho, *, config_path=)` grava nas 2 seções. `get_default_dir(nome, *, config_path=)`/`set_default_dir(nome, caminho, *, config_path=)`: override do usuário > pasta semeada > `None`. `PASTAS_PADRAO_SEED` com as 3 pastas da decisão nº 7 (`sobressalentes_pmib`, `pdms_modificados`, `templates_ficha`, relativas a `Path.home() / "Box" / "CMI - Consórcio Itaipu" / "11 - Ger. Engenharia" / "15 - PDM"`, nomes de subpasta literais confirmados contra o texto da decisão). `PASTAS_PADRAO_POR_CHAVE` semeado com as 3 chaves do `ModuloPDM` que a etapa seguinte vai usar (`pdm.caminho_destino`, `pdm.template`, `pdm.status_pmib` — já alinhadas aos atributos reais `caminho_destino`/`path_template`/`path_status_pmib` de `frontend.ModuloPDM`). `file_dialogs.py`: `ask_open_file`/`ask_open_files`/`ask_save_file`/`ask_directory(chave, categoria, *, titulo=, filetypes=, defaultextension=, config_path=, dialog_fn=)`; tkinter só via import preguiçoso DENTRO de cada função (nunca no topo do módulo — ambiente de teste não tem tkinter instalado); `dialog_fn` injetável cobre 100% dos testes; cancelamento devolve vazio no tipo certo (`""` singular, `()` para `ask_open_files`, normalizando quirks históricos do Tk) sem chamar `remember_dir`; sucesso grava a PASTA (dirname para arquivo; a própria pasta para diretório; dirname do PRIMEIRO arquivo em `ask_open_files`) na chave+categoria. 76 testes novos (`test_prefs.py` 40 + `test_file_dialogs.py` 36); suíte total 236 (CP 1.4) + 76 = 312 passed; `scripts/check.sh` verde. `frontend.py` NÃO foi tocado (zero linhas) — migração dos ~34 call sites de `filedialog.*`, pré-preenchimento do `ModuloPDM` e painel "Pastas padrão" da Home ficam para a etapa seguinte (registrado em PENDENCIAS.md). **2ª metade (conclui o checkpoint, mesma data)**: Parte A — parâmetro `initialdir: str \| os.PathLike[str] \| None = None` (keyword-only) adicionado às 4 funções de `file_dialogs.py` via helper novo `_resolver_initialdir`: um override CONTEXTUAL de quem chama (não é memória entre sessões) que VENCE a resolução via `prefs.get_initial_dir` quando aponta para uma pasta que existe de fato (`os.path.isdir`); se ausente/`None`/inválido (pasta inexistente, string vazia, ou um arquivo em vez de pasta) cai integralmente para a resolução normal via `prefs`, sem exceção; `remember_dir` na saída continua gravando a pasta REALMENTE escolhida pelo usuário, qualquer que seja a origem do `initialdir` de entrada. 26 testes novos na seção F de `test_file_dialogs.py` (override válido tem prioridade; override inválido cai pra resolução normal; ausente/`None`/string vazia idênticos ao comportamento anterior à esta etapa; convive com os demais kwargs; não afeta o `remember_dir` da saída); `test_prefs.py` inalterado (Parte A não tocou `prefs.py`, só `file_dialogs.py`, por restrição explícita do checkpoint). Parte B — migrados os 34 call sites de `frontend.py` (cada um confirmado lendo o método real antes de editar): `ModuloCriaFichas` (3), `ModuloPDM` (8 — inclui o caso especial `_op1_modificados`, que agora usa `initialdir=origem` via o override da Parte A para abrir na pasta "PDMs From Itaipu" escolhida segundos antes na mesma tela), `ModuloAnalyzer` (3), `ModuloTranslator` (1), `ModuloUploadConditions` (5), `ModuloUploadTechSpecs` (5), `ModuloCopiaFichas` (1), `ModuloAutoSpec` (3, incluindo a chave `autospec.manuais`/`pdf` citada como exemplo no texto do plano), `ModuloLMR` (1), `ModuloPMIBManager` (3), `ModuloBuscaPMIB` (1) — replace cirúrgico (só a expressão da chamada mudou; variável de destino, `if`/labels/cores de botão seguintes permanecem idênticos); import `from sigft.app import file_dialogs` (+ `from sigft.core import prefs`, usado na Parte C) adicionados junto de `from sigft.core.excel.pmib_codes import normalize_pmib`. Confirmado por grep: 0 `filedialog.` remanescente em `frontend.py`; 34 chamadas `file_dialogs.ask_*` (7 `ask_directory` + 20 `ask_open_file` + 5 `ask_open_files` + 2 `ask_save_file`); 0 `filedialog.` fora de `sigft/app/file_dialogs.py` em todo o resto do repositório (o único hit remanescente é um comentário histórico em `prefs.py`, não uma chamada). `from tkinter import filedialog` permanece na linha de import original (agora sem uso — `messagebox`/`ttk`/`simpledialog` da mesma linha continuam usados); remover o import morto fica para uma limpeza de lint futura (CP 8.1), fora do escopo cirúrgico desta etapa. Parte C — pré-preenchimento do `ModuloPDM.__init__`: só `self.caminho_destino` (único campo de PASTA com `Entry`/`StringVar` visível e mapeado em `PASTAS_PADRAO_POR_CHAVE`) recebe `prefs.get_default_dir("pdms_modificados")` quando não `None`. **Decisão registrada**: `path_template`/`path_status_pmib` (chaves `pdm.template`/`pdm.status_pmib`) NÃO são pré-preenchidos como valor de `StringVar` — são caminhos de um ARQUIVO Excel específico (sem `Entry` visível ligado a eles), e `get_default_dir` devolve uma PASTA; pré-preencher quebraria a leitura posterior (`pd.read_excel(pasta, ...)` falharia se o usuário não trocasse o valor). Em vez disso, os DIÁLOGOS desses 2 campos (`_sel_template`/`_sel_status_pmib`, já migrados na Parte B com essas mesmas chaves) já abrem na pasta padrão certa via `get_initial_dir` → `PASTAS_PADRAO_POR_CHAVE` → `get_default_dir` — efeito prático equivalente ao "pré-preenchimento" citado no critério de aceite do plano para um campo de arquivo (o usuário ainda clica "Selecionar", mas o diálogo já abre no lugar certo); detalhado em PENDENCIAS.md. `frontend.py` não pôde ser importado/executado neste ambiente (sem `customtkinter`/`tkinter`): verificação via `python3 -m compileall`/`ast.parse` (sintaxe OK) + revisão manual linha a linha dos 34 sites contra o conteúdo real do arquivo antes de cada edição; validação funcional em ambiente real (painel "Pastas padrão" editável na Home e o cenário AutoSpec do critério de aceite do plano — Excel abre na pasta do último Excel, PDF na do último PDF) depende de UI ainda não construída (`widgets/pickers.py`, CP 7.2) e fica pendente para quando essa UI existir, ou para o usuário confirmar manualmente rodando o app hoje (ambos registrados em PENDENCIAS.md). 26 testes novos; suíte total 236 (CP 1.4) + 76 (1ª metade) + 26 (2ª metade) = 338 passed; `scripts/check.sh` verde (compileall cobre `frontend.py` sem erro de sintaxe). |
| 2.1 engine + selenium_engine | ✅ concluído | 2026-07-27 | `sigft/core/rpa/{__init__,engine}.py`: `RPAEngine` (`abc.ABC`, só stdlib) com os 10 métodos do checkpoint — `goto`, `click`, `fill`, `press`, `wait_visible`, `wait_clickable`, `element_exists`, `get_value`, `screenshot`, `set_download_dir` — todo `seletor` é string XPath pura (139/140 usos de `By.*` hoje já são XPath). `sigft/core/rpa/selenium_engine.py`: `create_chrome_driver(*, wait_timeout=20, download_dir=None) -> (driver, wait)` — fábrica de baixo nível que reproduz EXATAMENTE os 6 pontos de criação (incl. `ChromeOptions`+4 prefs de download quando `download_dir` é passado, mecânica de `upload_ficha_duplicada`); `SeleniumEngine(RPAEngine)` recebe `driver`/`wait` injetáveis — `click`/`fill` usam a mecânica canônica de `safe_click`/`safe_send_keys` (scroll + JS click / Ctrl+A+Backspace+texto, com `except Exception: pass` preservado), `wait_visible`/`wait_clickable`/`get_value` NÃO engolem exceção (preserva o padrão `TimeoutException`=fim-de-loop de `apagar_lmr`/`upload_tech_specs`), `element_exists` via `find_elements` imediato (sem esperar), `screenshot`/`set_download_dir` são capacidades NOVAS (`save_screenshot`/CDP `Page.setDownloadBehavior`); `SeleniumEngine.create(...)` combina fábrica+construção (sem consumidor de produção ainda — começa no CP 2.2). Migrados os 6 pontos de criação, SÓ A CRIAÇÃO (nada de `safe_click`/seletores/fluxo tocado): `apagar_lmr_backend.ApagarLMRAutomation.iniciar_driver` (20s), `lmr_backend.LMRAutomation.iniciar_driver` (20s), `cria_fichas_no_pmib_v1_backend.AutomacaoPMIB.iniciar_driver` (10s), `upload_conditions_backend.UploadAutomation.iniciar` (20s), `upload_tech_specs_backend.TechSpecsAutomation.iniciar` (20s, sem `return self.driver` — preservado sem retorno), `upload_ficha_duplicada.ExtratorFichaBase.iniciar_driver_silencioso` (15s + `download_dir=self.dir_download`) — os 3 timeouts divergentes (10/15/20) preservados, nenhum unificado. Grep confirma `webdriver.Chrome(` só em `selenium_engine.py` (demais ocorrências são comentários/docstrings citando o histórico). 44 testes novos (`test_rpa_engine.py` 13 + `test_selenium_engine.py` 25 + `test_rpa_driver_migration.py` 6); suíte total 338 (CP 1.5) + 44 = 382 passed; `scripts/check.sh` verde (smoke de importação dos 12 backends continua passando). Pendências: exceção `By.CSS_SELECTOR` de `cria_fichas_no_pmib_v1_backend.py:396` fora de escopo (CP 2.2); migração de `safe_click`/`safe_send_keys`/`pesquisar_e_abrir`/etc. dos 6 backends para `SeleniumEngine`/`PMIBPortal` é CP 2.2 (nada migrado agora além da criação); imports `webdriver`/`WebDriverWait` viram código morto nos 6 backends migrados (deixados intactos, candidato a CP 8.1/ruff). |
| 2.2 PMIBPortal | ✅ concluído | 2026-07-27 | `sigft/core/rpa/portal.py`: `PMIBPortal(engine=None)` consolida 9 mecânicas antes duplicadas em 6 classes. `safe_click`/`safe_fill` delegam para `engine.click`/`.fill` (mecânica real já em `SeleniumEngine` desde o CP 2.1). `check_or_uncheck`/`clicar_salvar_visivel` só existiam em 1 lugar cada (upload_conditions/upload_ficha_duplicada) — só "movidos". `excluir_linha_com_confirmacao(row)` unifica a mecânica central de `upload_tech_specs`/`upload_ficha_duplicada` (recebe uma linha já localizada); `apagar_lmr.executar_limpeza` tem uma 3ª variante estruturalmente diferente (busca lixeira na tabela inteira, sem "linha"), não usa este método. `pesquisar_e_abrir(pmib, *, busca_xpath=, lapis_xpath_template=, ir_para_lista=True)` adota a estrutura de robustez de `upload_tech_specs` (retry 3x, trata StaleElement/Timeout, retorna bool) para todos, com SELETORES PARAMETRIZADOS por módulo (default = apagar_lmr/tech_specs/lmr; overrides exatos para upload_conditions e upload_ficha_duplicada — divergências reais de ícone/estratégia de casamento, ver docstring do método e PENDENCIAS.md). `solicitar_parada`/`deve_parar` (stop-flag) migrados só nas 4 ocorrências reais (2 classes × 2 arquivos: upload_conditions/upload_tech_specs) — não inventado para os outros 4 backends; `engine=None` permite reusar o portal só para stop-flag nas 2 classes de IA sem browser. `aguardar_login_manual(callback_pause)` é capacidade NOVA, sem consumidor ainda (mesmo espírito do CP 2.1). `ir_para_lista()` usa `config.PORTAL_URL` (CP 1.1). EXCEÇÃO AUTORIZADA: o fluxo de 24 TABs cegos do `lmr_backend.processar_lista` foi substituído por `portal.pesquisar_e_abrir` (mesmo alvo final). Migração de baixo risco nos 6 backends: cada classe mantém o NOME dos seus próprios métodos (`safe_click` etc.), só o CORPO passa a delegar — nenhum dos (possivelmente centenas de) call sites internos precisou mudar. Descoberta durante a execução: uma 6ª variante de "pesquisar+lápis" em `cria_fichas.atualizar_projeto_em_massa`, com seletores não cobertos pelo levantamento — não migrada, registrada em PENDENCIAS.md. 52 testes novos (`test_portal.py` 29 + `test_rpa_portal_backend_migration.py` 23); suíte total 382 (CP 2.1) + 52 = 434 passed; `scripts/check.sh` verde. Aceite parcial de "não importar selenium diretamente": `By` continua importado nos 6 arquivos (usado pelos call sites internos não migrados); migração completa fica para CP 2.3+. 9 pendências detalhadas registradas em PENDENCIAS.md (seletores/timing/mensagens com pequenas divergências documentadas, todas sem efeito funcional observável ou já verificadas contra o único consumidor real). |
| 2.3 sleeps → waits | ✅ concluído | 2026-07-27 | `sigft/core/rpa/portal.py` ganha 32 constantes `PAUSA_*` (módulo, não atributos de `PMIBPortal`), nomeadas por CONTEXTO/PROPÓSITO (não só pelo valor numérico — ex.: `PAUSA_ANIMACAO`/`PAUSA_AUDITORIA` são ambas 0,5s mas com propósitos distintos), reaproveitadas entre arquivos só quando o propósito é genuinamente o mesmo. Migrados os 72 `time.sleep(<literal numérico>)` levantados nos 6 arquivos RPA (`apagar_lmr_backend.py` 3, `lmr_backend.py` 5, `upload_tech_specs_backend.py` 10, `upload_conditions_backend.py` 11, `upload_ficha_duplicada.py` 18, `cria_fichas_no_pmib_v1_backend.py` 25): 71 viraram constante nomeada (valor preservado tal qual — nenhum tempo de espera mudou, só ganhou nome), 1 foi ELIMINADO por critério estrito (`apagar_lmr.executar_limpeza`: sleep redundante com um `wait.until` explícito adjacente para o MESMO elemento, loop já dependia de `TimeoutException`). Critério conservador aplicado: só elimina quando a espera explícita adjacente comprovadamente cobre a MESMA transição (um caso — paginação de `upload_tech_specs` — foi considerado e mantido como constante por dúvida legítima: elemento "visível" não prova conteúdo AJAX atualizado). Fora do escopo (não são sleeps de RPA/Selenium): `analyzer_backend.py`/`translator_backend.py` (rate-limiting de API) e `frontend.py` (pacing da splash screen). Nenhum seletor/URL/lógica de negócio alterado. 41 testes novos (`test_rpa_sleep_constants.py`) confirmam os 32 valores exatos e a ausência de `time.sleep(` com literal cru nos 6 arquivos; suíte total 434 (CP 2.2) + 41 = 475 passed; `scripts/check.sh` verde. 2 valores (`PAUSA_ABERTURA_FICHA`=5s, `PAUSA_GERACAO_PMIB`=6s) registrados em PENDENCIAS.md como candidatos a validação futura contra o portal real (valores empíricos preservados, sem 100% de certeza do racional exato). |
| 2.4 ficha_layout unificado | ✅ concluído | 2026-07-28 | `sigft/core/rpa/ficha_layout.py` (só stdlib + `from sigft import config`, sem `import openpyxl` — dicts puros, testável sem dependências pesadas) unifica os 2 `CONFIG_MAP` (`analyzer_backend.py` linhas 25-51, `autospec_backend.py` linhas 34-60) e os 2 `VARIAVEIS_SPECS` (linhas 53-57/62-66) numa fonte única, 25 chaves na mesma ordem. Levantamento campo a campo confirmou `type`/`validation`/`weight`/`cells` idênticos nos 2 mapas originais; únicas diferenças reais: `range` (analyzer guardava o span COMPLETO da célula mesclada, ex. "H6:P6"; autospec só a 1ª célula, ex. "H6" — sempre a mesma célula, conferido célula a célula nas 16 entradas "cell"), `error_target` (só no analyzer, 7 das 9 entradas checkbox — ausente em `classificacao_periculosidade`/`logistica_reversa`) e `desc` (só no autospec, 22 das 25 entradas — ausente em `texto_breve_material`/`unidade`/`fabricante`). `CONFIG_MAP` unificado é a UNIÃO das 2 versões (cada entrada ganha todas as chaves que tinha em QUALQUER um dos originais); decisão canônica do `range`: valor COMPLETO do analyzer (mais informativo, documenta o span real da célula mesclada). `VARIAVEIS_SPECS` unificado é a união das 4 chaves DISJUNTAS (`pergunta_range`/`resposta_range` do analyzer + `pergunta_col_idx`/`resposta_col_idx` do autospec) + `start_row` deduplicado via `config.LINHA_SPECS_FICHA` (=79, já existia desde o CP 1.1 — este checkpoint conecta os 2 lugares que o hardcodavam). Migrados os 2 consumidores: `analyzer_backend.py` (import nomeado direto `from sigft.core.rpa.ficha_layout import CONFIG_MAP, VARIAVEIS_SPECS`; `CONFIG_MAP`/`VARIAVEIS_SPECS` locais removidos; fallback de `_find_variable_specs_start_row` trocado de `return 79` para `return config.LINHA_SPECS_FICHA` — mesmo valor numérico, só deixa de ser literal solto; o loop `for key, config in CONFIG_MAP.items():` que sombreia `from sigft import config` DENTRO de `processar_planilha` foi deliberadamente MANTIDO — comportamento pré-existente inofensivo, fora do escopo) e `autospec_backend.py` (mesmo padrão de import; `GENERATIVE_FIELDS` intocado; ÚNICA mudança de comportamento potencial do checkpoint: as 2 leituras diretas de `texto_breve_material`/`fabricante` em `analyze_sheet` ganharam `.split(":")[0]`, porque o `range` canônico agora é o span completo — sem o split, `ws["H6:P6"]` no openpyxl devolveria uma tupla de tuplas em vez de um `Cell`, quebrando `.value`; os demais pontos que já faziam split — mapeamento estático de `analyze_sheet` e `fill_save` — seguem inalterados e continuam corretos com o range completo, confirmado por teste). `frontend.py:1556` (`analyzer_backend.CONFIG_MAP`, tela "Configurar Pesos") não precisou de nenhuma mudança. 119 testes novos (`tests/test_ficha_layout.py`): as 2 versões antigas de `CONFIG_MAP`/`VARIAVEIS_SPECS` congeladas como fixture (`_OLD_ANALYZER_*`/`_OLD_AUTOSPEC_*`), testes de estrutura (25 chaves), equivalência por chave parametrizada (type/validation/weight/cells/range), presença/ausência de `error_target`/`desc`, `VARIAVEIS_SPECS` completo, identidade de OBJETO entre `analyzer_backend.CONFIG_MAP`/`autospec_backend.CONFIG_MAP`/`ficha_layout.CONFIG_MAP` (fonte única de verdade, não só igualdade), fallback de `_find_variable_specs_start_row` com worksheet fake, e `analyze_sheet`/`fill_save` rodados DE VERDADE (via `openpyxl.load_workbook` monkeypatchado) contra uma worksheet fake que LEVANTA `AssertionError` se receber um endereço de range sem split — canário direto contra regressão do fix. Suíte total 475 (CP 2.3) + 119 = 594 passed; `scripts/check.sh` verde. 2 pendências novas registradas em PENDENCIAS.md (decisão canônica do `range` + fix associado no autospec; `pdm_backend`/`translator_backend`/comentário de `sigft/config.py` fora de escopo). |
| 3.1 LLMClient + Gemini direto | ✅ concluído | 2026-07-28 | `sigft/core/llm/{__init__,client}.py` + `sigft/core/llm/providers/{__init__,gemini}.py` criados (só stdlib em `client.py` — `time`/`json`/`dataclasses` + `from sigft import config`; `google.generativeai` só em `providers/gemini.py`, import PREGUIÇOSO dentro de `GeminiProvider.__init__`, mesma convenção de `openpyxl` em `core/excel/status_sheet.py`). `LLMResponse` (dataclass: `text`/`parsed_json`/`tokens_in`/`tokens_out`/`custo_usd` = sempre `None` neste CP (CP 3.4)/`model`/`provider`/`duracao_s`). `LLMClient(provider, *, provider_name, model, max_retries=0, retry_sleep_seconds=0, min_interval_seconds=None, sleep_fn=time.sleep, time_fn=time.time)` centraliza retry (`max_retries` = RETENTATIVAS, total de tentativas = `max_retries+1`), rate-limit OPCIONAL (aplicado 1x por `generate()`, não por tentativa de retry — réplica do padrão de `analyzer_backend` de hoje) e `_limpar_e_parsear_json` (implementação ÚNICA que substitui as 4 variantes divergentes de hoje — cobre objeto E lista, estritamente mais robusta que cada uma isoladamente, testada com casos que demonstram a robustez extra). `GeminiProvider(api_key, model, *, genai_module=None)` — ÚNICA classe do projeto que importa `genai`; aplica `safety_settings` BLOCK_NONE (4 categorias) em TODA chamada, para as 5 tarefas (decisão deliberada de baixo risco, ver PENDENCIAS.md); `system_instruction`/`generation_config` (JSON mode) só quando `system`/`json_mode` pedidos; extrai `tokens_in`/`tokens_out` de `usage_metadata` de forma defensiva (capacidade nova, `None` se ausente). `get_llm(tarefa, api_key)` resolve provider/modelo via `config.LLM_MODELOS_HOJE` (NÃO `LLM_TASKS` — decisão exigida pelo próprio Aceite do checkpoint, registrada em PENDENCIAS.md) e a política de retry/rate-limit via `_POLITICA_RETRY_POR_TAREFA` hardcoded em `client.py` (não em `config.py`): `categorizar_pdm` 0 retentativas/sem rate-limit; `validar_ficha` 2 retentativas/5s/rate-limit 60s; `condicoes` 2/30s/sem rate-limit; `tech_specs` 2/2s/sem rate-limit; `autospec` (sem consumidor real ainda) igual a `validar_ficha`. Migrados os 4 consumidores diretos: `analyzer_backend.DatasheetAnalyzer` (`_call_gemini_api` vira try/except fino sobre `self._llm.generate(...)`; `last_api_call_time`/`min_seconds_between_calls` REMOVIDOS), `cria_fichas_no_pmib_v1_backend.GeminiCategorizer` (`processar_lote` perde `model = genai.GenerativeModel(...)` e o parse manual de `[`...`]`, preserva o `ValueError` proativo sem chave e `raise Exception(f"Erro na IA: {e}")` sem retry — política de `categorizar_pdm` é 1 tentativa só, como hoje), `upload_conditions_backend.ConditionsProcessor` (`processar_ia_lote` perde o laço `for tentativa in range(MAX_TENTATIVAS)`/`safety_settings` local/`_limpar_resposta_json` — REMOVIDO, não só deixado morto — vira 1 chamada com try/except preservando os logs POR FICHA; import de `PAUSA_RETRY_IA_LONGA` removido do arquivo, constante intocada em `portal.py`), `upload_tech_specs_backend.TechSpecsProcessor` (`_chamar_gemini_specs` perde o laço `for i in range(3)`/`safety_settings` local/`_limpar_json_ia` — REMOVIDO — vira 1 chamada com `json_mode=True`; import de `PAUSA_RETRY_IA_CURTA` removido). `genai.` confirmado por grep em todo o repo: só aparece em `providers/gemini.py` (demais ocorrências são comentários/docstrings citando o histórico, e o parâmetro `genai_module=` dos testes). `autospec_backend.py` (LangChain, CP 3.2), `translator_backend.py`, `frontend.py` e `sigft/config.py` INTOCADOS (fora de escopo — ver PENDENCIAS.md). 79 testes novos (`test_llm_client.py` 32 + `test_llm_gemini_provider.py` 14 + `test_llm_get_llm_factory.py` 17 + `test_llm_backend_migration.py` 16); suíte total 594 (CP 2.4) + 79 = 673 passed; `scripts/check.sh` verde. 6 pendências novas registradas em PENDENCIAS.md (fonte `LLM_MODELOS_HOJE` ≠ `LLM_TASKS` + `api_key` explícito em `get_llm`; `safety_settings` uniforme nas 5 tarefas; perda de granularidade de log por tentativa de retry; simplificação do sleep uniforme entre exceção/resposta-vazia; remoção deliberada dos 2 métodos de limpeza de JSON já mortos após a migração; `import time` morto em `analyzer_backend.py`). |
| 3.2 OpenRouter (gateway padrão) + endpoint empresa | ✅ concluído | 2026-07-31 | **Contrato de provider generalizado** (`core/llm/client.py`): `ProviderResult` (`NamedTuple` — `text`/`tokens_in=None`/`tokens_out=None`/`custo_usd=None`) substitui a tupla crua `(texto, tokens_in, tokens_out)` do CP 3.1; `LLMClient.generate` lê `resultado.text/.tokens_in/.tokens_out/.custo_usd` (este último agora alimenta `LLMResponse.custo_usd`, que deixa de ser fixo `None`). `GeminiProvider.generate_raw` devolve `ProviderResult` (sem custo). **`providers/openai_compat.py`** (`OpenAICompatProvider`, NOVO): base para QUALQUER endpoint `POST {base_url}/chat/completions` no formato OpenAI — `requests` puro via `http_post` injetável (import preguiçoso), NÃO o pacote `openai` (divergência deliberada do texto do plano, ver PENDENCIAS.md); `messages` com/sem `system`, `response_format`/`temperature` condicionais, `raise_for_status()` propaga (retry é do `LLMClient`), tokens extraídos defensivamente, `custo_usd` sempre `None`; hooks `_montar_corpo_extra`/`_extrair_custo` para especialização sem duplicar `generate_raw`. **`providers/openrouter.py`** (`OpenRouterProvider(OpenAICompatProvider)`, NOVO): `base_url` default `config.OPENROUTER_BASE_URL`, headers de atribuição (`HTTP-Referer`/`X-Title`, mesclados com os do chamador), `usage: {include: true}` no corpo + `usage.cost` → `custo_usd` REAL (via os 2 hooks); `listar_modelos(api_key, *, cache_path=, ttl_segundos=86400, http_get=, time_fn=)` — catálogo `GET /models` com cache JSON local (`config.OPENROUTER_CATALOGO_CACHE`), degradação graciosa (erro de rede COM cache devolve o cache; SEM cache levanta), insumo do CP 3.3 sem consumidor ainda. **`temperature`** (achado do levantamento, preserva o `temperature=0.1` do LangChain): providers ganham `temperature: float \| None = None` (keyword-only); `GeminiProvider` mescla `temperature`/`response_mime_type` no mesmo `generation_config` (nunca sobrescreve); `_POLITICA_RETRY_POR_TAREFA` ganha a chave `"temperature"` (`0.1` só em `autospec`, `None` nas outras 4); `get_llm` retira `temperature` da política antes de construir o `LLMClient` e passa ao provider. **`get_llm` roteia 3 providers** (`gemini`/`openrouter`/`openai_compat`) via `config.CHAVE_POR_PROVIDER`: Gemini com `api_key` explícito usa-a tal qual (preserva os 5 consumidores de hoje); demais casos resolvem via `chaves` (default `config.carregar_chaves()`); `openai_compat` exige `chaves["EMPRESA_LLM_BASE_URL"]` (`ValueError` claro se ausente); provider desconhecido (ex. `"xai"`) continua `NotImplementedError`; assinatura vira `get_llm(tarefa, api_key=None, *, chaves=None)`. **`sigft/config.py`** (aditivo): `PROVIDER_OPENROUTER`/`PROVIDER_OPENAI_COMPAT`, `OPENROUTER_BASE_URL`/`OPENROUTER_HEADERS_ATRIBUICAO`/`OPENROUTER_CATALOGO_CACHE`, 3 entradas novas em `ENV_VAR_POR_CHAVE` (`OPENROUTER`/`EMPRESA_LLM_BASE_URL`/`EMPRESA_LLM_API_KEY`) e `CHAVE_POR_PROVIDER` novo; `LLM_TASKS`/`LLM_DEFAULT`/`LLM_MODELOS_HOJE` INTOCADOS (troca de modelo continua CP 3.3 — `LLM_MODELOS_HOJE` continua a fonte de `get_llm`, decisão do CP 3.1). **LangChain removido de `autospec_backend.py`**: os 3 imports saem; `self.llm = ChatGoogleGenerativeAI(...)` vira `self._llm = get_llm("autospec", gemini_key)` (guard `if not gemini_key: raise ValueError(...)` preservado tal qual); `generate_ai_response` troca `PromptTemplate(...) \| self.llm \| JsonOutputParser()` por `self._llm.generate(prompt, tags={...}).parsed_json` dentro do MESMO `try/except` (`print(f"Erro IA: {e}")` + `return {}` preservados) — `autospec` ganha retry (2 tentativas) que antes não tinha; `langchain-google-genai`/`langchain-core` removidos de `requirements.txt` e de `tests/conftest.py::_HEAVY_MODULES`. **`frontend.py`** (aditivo, cirúrgico): `keys_info` (+3 tuplas: `OPENROUTER`/`EMPRESA_LLM_BASE_URL`/`EMPRESA_LLM_API_KEY`) e `SIG_FT_App.load_keys` (+3 `os.getenv`/entradas em `defaults`, mesmo padrão das 4 existentes). `.gitignore` ganha `openrouter_models_cache.json`. 64 testes novos (`test_llm_openai_compat.py` 18 + `test_llm_openrouter.py` 16 + `test_llm_autospec_migration.py` 9 + `test_llm_gemini_provider.py` +5 [temperature × 4 combinações + `custo_usd` sempre `None`] + `test_llm_get_llm_factory.py` +10 [roteamento de provider, resolução de chave, `EMPRESA_LLM_BASE_URL` ausente, `NotImplementedError` de `"xai"`, aceite "≥2 modelos via OpenRouter mudando só config"] + `test_config.py` +6); `test_llm_client.py`/`test_llm_gemini_provider.py` (existentes) atualizados para o novo contrato de `ProviderResult` (edições cirúrgicas, nenhum caso de teste removido); suíte total 673 (CP 3.1) + 64 = 737 passed; `scripts/check.sh` verde. 9 pendências novas registradas em PENDENCIAS.md (`requests` em vez de `openai`; sem equivalente a `safety_settings` no protocolo OpenAI-compatível; `temperature` preservada via política por tarefa; `autospec` ganha retry + troca `JsonOutputParser`→`_limpar_e_parsear_json`; guard "Chave Gemini é obrigatória" mantido; `EMPRESA_LLM_BASE_URL` mascarado na UI por reaproveitar o mecanismo de chaves; providers novos sem consumidor de produção — `LLM_MODELOS_HOJE` intocado; `listar_modelos` insumo do CP 3.3 sem consumidor). |
| 3.3 seletor de modelo na interface | ✅ concluído | 2026-07-31 | **Parte A — `sigft/core/llm/selecao.py`** (novo, só stdlib: `json`/`os` + `from sigft import config`, espelha `core/prefs.py`): persistência da seleção de modelo em `config.CONFIG_FILE` (api_config.json) sob a chave RESERVADA `_modelos_ia` (`{"global": {"provider":.., "model":..} \| None, "por_tarefa": {tarefa: {...}}}`); `carregar()` normaliza (sempre as 2 chaves, entradas malformadas descartadas); `resolver(tarefa)` = override da tarefa > global > `None`; `definir_global`/`limpar_global`/`definir_por_tarefa`/`limpar_por_tarefa` (`ValueError` de tarefa desconhecida contra `LLM_MODELOS_HOJE`, mesmo padrão de `get_llm`); `aplicar_recomendados()` grava `LLM_DEFAULT` como global e `LLM_TASKS` (as 5 tarefas) como overrides — SUBSTITUI, não mescla. TODA escrita é read-modify-write do JSON inteiro (`_salvar_secao`), nunca sobrescreve as chaves de API que já estavam no arquivo — provado nos 2 sentidos em `tests/test_llm_selecao.py` (seção F). **Parte B — `core/llm/client.py:get_llm()`** ganha cadeia de resolução: (1) `selecao_resolvida` (novo parâmetro keyword-only, injeção de teste) > (2) `selecao.resolver(tarefa, config_path=config.CONFIG_FILE)` (lido AO VIVO a cada chamada) > (3) `config.LLM_MODELOS_HOJE[tarefa]` — o MESMO fallback de sempre (decisão "sem downgrade silencioso", ver PENDENCIAS.md); validação de tarefa continua contra `LLM_MODELOS_HOJE` ANTES de tocar a seleção; política de retry/rate-limit/temperature continua vindo de `_POLITICA_RETRY_POR_TAREFA[tarefa]` — por TAREFA, nunca por modelo. `config.LLM_TASKS`/`LLM_DEFAULT` só chegam a `get_llm` INDIRETAMENTE, via `selecao.aplicar_recomendados()`. **`sigft/config.py`** (aditivo): `LLM_FAVORITOS` — lista curada de 5 entradas (Gemini 3 Flash Preview = padrão, MiniMax M3 = economia, Grok 4.5 = poder — os 2 últimos via `PROVIDER_OPENROUTER`, já que os providers nativos `xai`/`minimax` não são implementados — + os 2 modelos usados hoje via `PROVIDER_GEMINI`, "para o usuário voltar atrás pela UI"), cada entrada com `provider`/`model`/`rotulo`/`score`/`preco_input`/`preco_output`/`tier`. **Parte C — `frontend.py`** (cirúrgico): `HomeView.criar_painel_modelos_ia(row=4)` inserido logo após `criar_area_config_api(row=3)`, com as 6 rows dos cards + a do espaçador deslocadas +1 (7 edições no total, 4→5/5→6/6→7/7→8/8→9/9→10/10→11, conferidas uma a uma); painel com modo simples (`CTkOptionMenu` global), modo avançado (`CTkCheckBox` + 5 `CTkOptionMenu` por tarefa), campo livre (`CTkEntry`+`CTkOptionMenu` de provider) para id manual, botão "Atualizar catálogo" (OpenRouter, em thread, degrada em silêncio) e botões "Aplicar recomendados"/"Salvar seleção"; filtra favoritos por `controller.get_key(...)` via `config.CHAVE_POR_PROVIDER` (provider sem chave configurada não aparece; painel mostra aviso se NENHUM provider tiver chave). `SIG_FT_App.save_keys` corrigido para read-modify-write (antes apagava a sub-árvore `_modelos_ia` a cada "Salvar Chaves" — bug real, corrigido). `frontend.py` não é importável neste ambiente (sem tkinter/customtkinter) — verificado por `compileall` + revisão manual das 7 rows + AST (confirma os 16 métodos novos dentro de `HomeView`) + simulação STANDALONE da lógica pura (`_montar_opcoes_modelo_ia`, `_salvar_selecao_modelos_ia`, `save_keys`) contra o `selecao` real, fora do tkinter. 80 testes novos (`test_llm_selecao.py` 58 + `test_config.py` +13 [`LLM_FAVORITOS`] + `test_llm_get_llm_factory.py` +9 [cadeia de resolução, incl. o Aceite "trocar na UI muda a próxima chamada" e um canário do gap `xai`/`categorizar_pdm`]); fixture de isolamento de `config.CONFIG_FILE` (autouse) adicionada em 4 arquivos de teste que exercitam `get_llm()`/os 5 consumidores (`test_llm_get_llm_factory.py`, `test_llm_backend_migration.py`, `test_llm_autospec_migration.py`, `test_rpa_portal_backend_migration.py`) para não depender de um `api_config.json` real no cwd de quem roda a suíte; suíte total 737 (CP 3.2) + 80 = 817 passed; `scripts/check.sh` verde. 7 pendências novas registradas em PENDENCIAS.md (decisão do fallback "sem downgrade silencioso" + o que falta para promover os recomendados; chave reservada `_modelos_ia` convivendo com chaves de API + fix de `save_keys`; slugs ilustrativos do OpenRouter em `LLM_FAVORITOS` a reconfirmar; gap pré-existente `xai`/`categorizar_pdm` agora alcançável por "Aplicar recomendados"; julgamento de `tier` dos 2 modelos "hoje"; escopo do campo livre + filtro de chave sem live-refresh; validação funcional da UI pendente do usuário). **Aceite do plano — 2 de 3 itens verificados por teste automatizado**: "trocar o modelo na UI muda a próxima chamada" ✅ (`test_aceite_selecao_via_definir_global_muda_a_proxima_chamada_de_get_llm`); "seleção sobrevive a reinício do app" ✅ (`test_aceite_selecao_sobrevive_a_releitura_simulando_reinicio_do_app`, simula reinício via 2 chamadas independentes de `get_llm()` que releem o disco do zero); o 3º item — **"usuário confirmou a qualidade dos defaults econômicos numa amostra" — FICA PENDENTE, depende de ação humana externa** (único item de aceite deste checkpoint não verificável por teste automatizado nem por revisão de código; harness de A/B é uma tarefa FUTURA SEPARADA, fora do escopo deste checkpoint). |
| 3.4 UsageTracker (custo real/estimado) | ✅ concluído | 2026-08-01 | **Parte A — `sigft/core/llm/usage.py`** (novo, só stdlib: `json`/`os`/`datetime`/`typing.Callable` + `from sigft import config`, mesma convenção de `core/prefs.py`/`core/llm/selecao.py`): `registrar(*, provider, model, tarefa, modulo, tokens_in, tokens_out, custo_usd, duracao_s, sucesso, erro=None, caminho=config.ARQUIVO_USO_LLM, agora_fn=None)` anexa UMA linha JSONL (cria a pasta via `os.makedirs(exist_ok=True)`), respeita `SIGFT_DESABILITAR_USAGE` (só o valor EXATO `"1"` desliga) e NUNCA levanta — corpo inteiro num único `try/except Exception: pass`, mesmo padrão de `client.py:_capturar_prompt_se_pedido` (Decisão 1 do brief, a mais importante do checkpoint). `estimar_custo(model, tokens_in, tokens_out) -> (custo, estimado)` — função PURA — implementa a Decisão 2: `tokens_in`/`tokens_out` ausentes (`None`) -> `(None, None)` (`0` é válido, diferente de ausente); modelo resolvido via `_buscar_preco_por_slug()` em 2 passos (chave exata em `config.LLM_PRECOS_USD_POR_1M`; senão, se houver `"/"`, a parte após a ÚLTIMA barra — casamento de slug OpenRouter `vendor/modelo`, ex. `"x-ai/grok-4.5"` -> `"grok-4.5"`); modelo fora da tabela -> `(None, None)`, nunca um número inventado. `registrar()` decide real-vs-estimado: `custo_usd` (parâmetro) não-`None` -> grava tal qual com `custo_estimado=False`; `None` -> chama `estimar_custo()` e usa o resultado. `ler_registros(*, caminho=...)` lê o JSONL tolerando arquivo ausente (lista vazia), linhas em branco e linha corrompida no MEIO do arquivo (pulada via `except json.JSONDecodeError`, não derruba as demais — log append-only de processo que pode morrer no meio). `usage_report(*, caminho=..., registros=None)` agrega em 5 dimensões (`por_tarefa_e_modelo` — responde "qual modelo gasta mais NA MESMA tarefa"; `por_modulo` — responde "qual módulo do SIG-FT gasta mais"; `por_modelo`; `por_dia` via 10 primeiros chars do timestamp; `total`), cada balde com `chamadas`/`tokens_in`/`tokens_out`/`custo_usd`/`custo_estimado_parcial` (`True` se QUALQUER custo somado ali veio de estimativa — nunca mistura real+estimado em silêncio)/`falhas`; `registros=` injetável evita I/O em teste (`registros=[]` explicitamente DIFERENTE de `None`). `formatar_relatorio_texto(relatorio)` — texto simples (total gasto/chamadas/período coberto + blocos "Por módulo"/"Por modelo" ordenados por custo decrescente) — nunca levanta, mesmo com relatório `{}`; relatório sem chamadas vira só "Nenhuma chamada de IA registrada ainda." **Parte B — `core/llm/client.py:LLMClient.generate()`** instrumentado nos 2 pontos de saída exatos da recon: `usage.registrar(...)` chamado (sem `try/except` extra — confia inteiramente na garantia de `registrar()`) uma vez no sucesso (dentro do `try`, com os MESMOS `tokens_in`/`tokens_out`/`custo_usd`/`duracao_s` que vão para o `LLMResponse` devolvido) e uma vez na falha total (após esgotar as retentativas, antes do `raise ultimo_erro`, com `tokens_in=tokens_out=custo_usd=None`, `erro=f"{type(ultimo_erro).__name__}: {ultimo_erro}"` e a duração decorrida desde o INÍCIO do `generate()` — soma de todas as tentativas+sleeps de retry); `tarefa`/`modulo` vêm de `tags.get("tarefa", "sem_tarefa")`/`tags.get("modulo")` (mesmo fallback de `_capturar_prompt_se_pedido`); UM registro por `generate()`, nunca por tentativa de retry interna (testado explicitamente: 2 falhas + 1 sucesso grava só 1 registro). Import de `sigft.core.llm.usage` no TOPO de `client.py` — confirmado sem ciclo (`usage.py` não importa `client.py`). Nenhum comportamento pré-existente alterado (mesma resposta, mesma exceção, mesma política de retry) — só o efeito colateral novo (gravação em `logs/llm_usage.jsonl`). **`sigft/config.py`** (aditivo): `PASTA_LOGS = "logs"` + `ARQUIVO_USO_LLM = os.path.join(PASTA_LOGS, "llm_usage.jsonl")`. **Parte C — `frontend.py`** (cirúrgico): `HomeView.criar_painel_gastos_ia(row=5)` inserido logo após `criar_painel_modelos_ia(row=4)`, com as 7 rows seguintes deslocadas +1 (5→6 cards 1-6, 11→12 espaçador — conferidas uma a uma); painel com mesmo padrão visual dos 2 painéis existentes (`CTkFrame`, `fg_color=("gray90","gray16")`, `corner_radius=10`, título "💰 Gastos de IA"), conteúdo via `_atualizar_texto_gastos_ia` (chama `usage.usage_report()`+`formatar_relatorio_texto()` SÍNCRONO, dentro de `try/except` — o painel nunca impede a Home de abrir, degrada para mensagem amigável em caso de falha de leitura) e botões "Atualizar" (recalcula) e "Abrir pasta de logs" (`os.startfile`/fallback `subprocess.call(['open',...])` — mesmo precedente de `_mostrar_janela_resultados`/`abrir_pasta`; cria a pasta se ausente; try/except). `frontend.py` não pôde ser importado/executado neste ambiente (sem tkinter/customtkinter — nem o tkinter da stdlib está presente aqui): verificado por `py_compile` + checagem estrutural via `ast` (3 métodos novos dentro de `HomeView`, 7 edições de `row=` conferidas uma a uma) + toda a lógica de dados consumida pelo painel já coberta por 51 testes que não dependem de tkinter. 59 testes novos (`tests/test_llm_usage.py` 51 + extensão de `tests/test_llm_client.py` +8, incluindo o teste mais importante: falha REAL de escrita do registro — `caminho` apontando para uma pasta existente, `IsADirectoryError` de verdade — não impede `generate()` de devolver a resposta/relevantar a exceção original); `tests/conftest.py` ganhou uma fixture `autouse` (`_desliga_rastreamento_de_uso_de_ia_por_padrao`) que religa `SIGFT_DESABILITAR_USAGE=1` por padrão para TODA a suíte, protegendo dezenas de testes de outros arquivos que constroem `LLMClient` real e chamam `.generate()` sem saber deste checkpoint; suíte total 874 (baseline medido no início deste checkpoint — CP 3.3 + harness de A/B, ver PENDENCIAS.md) + 59 = 933 passed; `scripts/check.sh` verde; confirmado que a suíte inteira não cria `logs/` no repositório real. **Aceite do plano — os 3 itens verificados por teste automatizado**: "rodar qualquer módulo com IA gera registros" ✅ (instrumentação vive no ÚNICO `LLMClient.generate()` que os 5 consumidores de IA já usam desde CP 3.1-3.3); "o relatório responde as 2 perguntas" ✅ (`test_aceite_qual_modelo_gasta_mais_na_mesma_tarefa`/`test_aceite_qual_modulo_do_sigft_gasta_mais`); "chamadas via OpenRouter registram custo real (não estimado)" ✅ (`test_generate_preserva_custo_real_do_provider_sem_estimar`/`test_custo_usd_nao_none_e_gravado_como_real_sem_estimar`). 4 pendências novas registradas em PENDENCIAS.md (disciplina "nunca derruba produção" + env var; heurística de casamento de slug + modelo fora da tabela; preços de jul/2026 precisando reconfirmação agora que têm consumidor real; validação real da UI do card "Gastos de IA" pendente do usuário). |
| 3.5 prompts.py | ✅ concluído | 2026-08-01 | `sigft/core/llm/prompts.py` criado (novo, só stdlib, sem import de nenhum `*_backend.py` — evita import circular e acoplamento errado): 2 constantes estáticas (`SYSTEM_CONDICOES` = antigo `system_prompt` de `upload_conditions_backend`, 135 linhas; `SYSTEM_TECH_SPECS` = antigo `system_instruction` de `upload_tech_specs_backend`, 68 linhas) + 5 funções de montagem (`montar_validar_ficha`/`montar_categorizar_pdm`/`montar_condicoes_user`/`montar_tech_specs_user`/`montar_autospec`) que devolvem a f-string ORIGINAL MOVIDA INTEIRA, byte a byte (extraída PROGRAMATICAMENTE dos 5 arquivos-fonte via fatiamento de string exato entre os delimitadores `"""`, nunca retypada à mão — texto em português com acentuação pesada, risco real de erro de transcrição), preservando a indentação original de cada um (3 dos 7 textos carregavam 8 espaços herdados do corpo do método onde nasceram — `cria_fichas`, `upload_tech_specs` ×2, `autospec`; 2 não carregavam nenhuma — `analyzer`, `upload_conditions` — ambos os casos preservados tal qual, sem `textwrap.dedent`, ver PENDENCIAS.md). Migrados os 5 sítios: `analyzer_backend._build_gemini_prompt` (mantém extração de `mat`/`fab` + laços de `str_fixed`/`str_vars`, delega só o TEXTO), `cria_fichas_no_pmib_v1_backend.GeminiCategorizer.processar_lote` (mantém `_formatar_itens`), `upload_conditions_backend.processar_ia_lote` (`system_prompt` vira `prompts.SYSTEM_CONDICOES`; `user_prompt` vira `prompts.montar_condicoes_user(json.dumps(...))`, serialização mantida no backend), `upload_tech_specs_backend._chamar_gemini_specs` (mesmo padrão, `SYSTEM_TECH_SPECS`/`montar_tech_specs_user`), `autospec_backend.generate_ai_response` (mantém o laço que monta `desc_list` — consulta `GENERATIVE_FIELDS`, constante do próprio módulo, evitando import circular — `montar_autospec` recebe `desc_list_texto` já concatenado). **Disciplina "snapshot antes do refactor" seguida, com autocorreção de um desvio de ordem detectado durante a própria execução (ver PENDENCIAS.md)**: `tests/test_llm_prompts_snapshot.py` + 7 fixtures em `tests/fixtures/prompts/*.txt` capturadas via `_FakeLLM` (técnica de `tests/test_llm_backend_migration.py`) contra os 5 backends no estado 100% pré-refactor (recuperado com `git stash` depois do desvio), com entradas fixas e determinísticas; suíte confirmada verde ANTES de criar `prompts.py`/migrar qualquer backend, e continua verde DEPOIS da migração dos 5, sem qualquer edição de fixture. Verificação semântica adicional (fora da suíte — script de bootstrap via `eval()` real do texto extraído cru comparado byte a byte com a saída de `prompts.py`, múltiplas entradas por sítio, incluindo o marcador `"<<<...>>>"`) confirma equivalência além do que as fixtures fixas cobrem. `tests/test_llm_prompts.py` (10 testes novos): `SYSTEM_CONDICOES`/`SYSTEM_TECH_SPECS` batem byte a byte com a fixture; cada `montar_*` interpola corretamente (marcador `"<<<...>>>"` + trechos fixos do texto, incluindo o caso `context` falsy do autospec); invariante de Aceite via AST (`ast.walk` sobre `ast.Constant` de `str`, cobrindo os pedaços de texto literal dentro de f-strings) — nenhum literal de string com mais de 15 quebras de linha nos 5 arquivos migrados (maiores encontrados: 14 em `upload_conditions_backend.py`, 13 em `upload_tech_specs_backend.py`, ambos docstrings pré-existentes não relacionados a este checkpoint; `prompts.py`, fora do invariante por design, tem um literal de 135 linhas, confirmado por um teste de contraste). Suíte total 933 (CP 3.4) + 5 (snapshot) + 10 (prompts) = 948 passed; `scripts/check.sh` verde. 5 pendências novas registradas em PENDENCIAS.md (decisão de preservar indentação byte a byte + metodologia de extração programática; decisão de mover a f-string inteira em vez de `.format()`; pré-processamento mantido em cada backend + motivo; confirmação de que os 5 sítios são exaustivos; desvio de processo autocorrigido durante a execução). |
| 4.1 backends -> services/ | ✅ concluído | 2026-08-02 | Os 12 backends saíram da raiz para `sigft/services/`, na ordem do plano, um commit por módulo: `apagar_lmr`, `lmr`, `search`, `pdm`, `translator`, `analyzer` (1ª metade) + `autospec`, `cria_fichas`, `upload_conditions`, `tech_specs`, `ficha_duplicada`, `pmib_manager` (2ª metade). Conteúdo movido byte a byte nos 12 (verificado por `diff` contra o blob de HEAD, um a um) — nenhum módulo precisou de ajuste interno, porque todos já usavam imports absolutos `sigft.*` e nenhum backend importa outro. **Formato do shim: aliasing de módulo** (`sys.modules[__name__] = _modulo`), NÃO `from ... import *` — assim o nome antigo e o novo são literalmente o mesmo objeto, e um `monkeypatch.setattr(<nome_antigo>, ...)` continua atingindo o código real; com `import *` seriam namespaces distintos e a alteração ficaria só na cópia da raiz, uma classe inteira de bug silencioso com ~15 arquivos de teste importando pelos nomes antigos. `frontend.py` NÃO foi tocado: o splash carrega por nome via `importlib.import_module` e o `upload_ficha_duplicada` entra por `import ... as backend` (linha 41) — os shims cobrem os dois. *Aceite* verificado: smoke de importação verde sem edição; simulação do mecanismo real do splash resolve os 11 da tabela `modulos_para_carregar` + o `getattr` das 3 classes de `mixed_classes`. 2 arquivos de teste tiveram caminhos reapontados (leem o arquivo por CAMINHO, não por import — apontados para a raiz passariam a auditar o shim: um ficaria VAZIO, o outro FALHARIA); nenhum outro teste precisou de edição. 66 testes novos (`test_services_shims.py`), incluindo identidade de objeto nos 12 e um invariante de que nenhum arquivo da raiz volte a ter código de verdade. Suíte 948 -> 1014 passed. Próximo passo natural (fora deste checkpoint): `frontend.py` passar a importar de `sigft.services.*` direto, aposentando os shims — Fase 7. |
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
