# Plano de Refatoração — SIG-FT

> **Como usar este documento**: cada fase é dividida em checkpoints pequenos e independentes.
> A execução é feita pelo agente `refactor-executor` (modelo Sonnet), um checkpoint por vez:
> *"Execute o Checkpoint 2.1 do plano de refatoração"*. O agente lê este plano, a base de
> conhecimento (`docs/base-conhecimento/`) e implementa. O quadro de status no final registra
> o progresso. **A ordem das fases importa** — não pule fases.

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

### 1.3 Duplicação de IA

| Lógica | Implementações hoje |
|---|---|
| `genai.configure(transport='rest')` + `GenerativeModel` + retry | 5×: `analyzer`, `cria_fichas`, `upload_conditions`, `tech_specs` (+ `autospec` via LangChain) |
| Limpeza da resposta JSON (strip de ```` ```json ````, find `{`/`[`) | 4 variantes |
| `safety_settings` BLOCK_NONE | 2× copiado literal |
| Prompts gigantes embutidos em strings no meio do código | 5 módulos |
| `CONFIG_MAP` do layout da ficha técnica | **duplicado** em `analyzer_backend` e `autospec_backend` (ranges divergem: "H6:P6" vs "H6") — risco de desalinhamento silencioso |

### 1.4 Frontend monolítico

- `frontend.py` com ~2.400 linhas: 12 telas + 6 janelas + splash + app.
- Padrões repetidos ~12×: console + `log()` thread-safe (3 variantes de implementação!),
  janela de pausa de login (4 cópias), listbox de fichas com Adicionar/Remover/Limpar (2 cópias
  idênticas), seletor de arquivo com label de status e mudança de cor (20+ cópias), popup de
  seleção múltipla (4 variantes).
- Estado global de backends via `globals()` + splash com `importlib`.

### 1.5 Más otimizações e fragilidades

- `time.sleep()` fixo como sincronização primária do RPA (dezenas de ocorrências, 0.2s a 6s) —
  lento no caso bom, frágil no caso ruim. O correto é `WebDriverWait` com condição.
- `pdm_backend.pdms_fromItaipu_lista_geral`: reabre a planilha geral INTEIRA para cada código
  novo (O(n·m) de I/O); `aplicar_templates_fichas` reabre o template por ficha.
- `except: pass` silencioso em dezenas de pontos — falhas do RPA somem sem registro.
- Contrato `4500063671` hardcoded em regex (`upload_conditions`).
- Datas/valores mágicos: linha 79 da ficha, linha 4 do STATUS, aba "Lista de Materiais" —
  espalhados como literais em 8 arquivos.
- `lmr_backend`: no `except` do loop interno o índice não avança → risco de loop infinito.
- Dependência de Windows não isolada (`xlwings`, `os.startfile`).
- Sem testes automatizados de nenhum tipo.

---

## 2. Arquitetura-alvo

```
SIG-FT/
├── sigft/
│   ├── __init__.py
│   ├── config.py               # chaves API, URL do portal, contrato, constantes de layout
│   ├── core/
│   │   ├── excel/
│   │   │   ├── headers.py      # find_header_row(), find_columns() — ÚNICA implementação
│   │   │   ├── pmib_codes.py   # normalize_pmib() — ÚNICA implementação
│   │   │   ├── locking.py      # save_with_retry(wb, path, on_locked=callback)
│   │   │   └── status_sheet.py # classe StatusPMIB: carregar, lookup, marcar_completo(seções)
│   │   ├── ai/
│   │   │   ├── gemini.py       # GeminiClient: retry, rate-limit, parse_json, safety
│   │   │   └── prompts.py      # todos os prompts como constantes nomeadas
│   │   ├── rpa/
│   │   │   ├── browser.py      # create_driver(download_dir=None) — ÚNICA fábrica
│   │   │   ├── portal.py       # PMIBPortal(base): safe_click, safe_send_keys,
│   │   │   │                   #   check_or_uncheck, pesquisar_e_abrir, clicar_salvar_visivel,
│   │   │   │                   #   excluir_linha_com_confirmacao, stop-flag, waits
│   │   │   └── ficha_layout.py # CONFIG_MAP unificado (fonte única do layout da ficha)
│   │   └── callbacks.py        # protocolo padrão UI↔serviço: log/pause/ask/progress
│   ├── services/               # lógica de negócio (os atuais backends, magros)
│   │   ├── cria_fichas.py      ├── pdm.py            ├── analyzer.py
│   │   ├── translator.py       ├── upload_conditions.py
│   │   ├── upload_tech_specs.py├── ficha_duplicada.py├── autospec.py
│   │   ├── lmr.py              ├── apagar_lmr.py     ├── pmib_manager.py
│   │   └── search.py
│   └── app/                    # UI
│       ├── main.py             # entry point
│       ├── splash.py
│       ├── theme.py            # COLORS, fontes
│       ├── widgets/
│       │   ├── console.py      # ConsoleFrame (log thread-safe único)
│       │   ├── pickers.py      # FilePickerRow, FolderPickerRow, FileQueueList
│       │   ├── dialogs.py      # PausaLoginDialog, RetryLockDialog, SelecaoMultiplaDialog,
│       │   │                   #   DataFrameSelecaoDialog (substitui as 6 Janelas*)
│       │   └── module_frame.py # ModuleFrame base: header + content + console + progresso
│       └── views/              # 12 telas finas (1 arquivo cada), só montam UI e chamam services
├── tests/                      # pytest para core/ (funções puras)
├── frontend.py                 # shim de compatibilidade → sigft.app.main (até Fase 5)
├── *_backend.py                # shims de compatibilidade → sigft.services.* (até Fase 5)
└── docs/
```

**Princípios**:
1. **Uma implementação por conceito** — cabeçalho, código PMIB, driver, portal, Gemini.
2. **UI nunca contém regra de negócio; serviço nunca importa tkinter.** Comunicação só por
   callbacks (`log`, `pause`, `ask`, `progress`) definidos em `core/callbacks.py`.
3. **XPaths e fluxos Selenium são intocáveis** durante a migração — só mudam de arquivo.
4. **Compatibilidade por shims**: os nomes antigos continuam importáveis até a Fase 5, então o
   app funciona em qualquer ponto intermediário da refatoração.

---

## 3. Fases e Checkpoints

### Fase 0 — Salvaguardas (pré-requisito de tudo)

**Objetivo**: poder refatorar com rede de proteção mínima.

- **CP 0.1 — Estrutura e testes das funções puras.**
  Criar pacote `sigft/` vazio com `__init__.py`, pasta `tests/` e `pytest` no requirements
  (dev). Escrever testes caracterizando o comportamento ATUAL (copiando a lógica existente
  como oráculo) de: normalização de PMIB (casos: `'4500063671.105'`→`.1050`, float
  `4500063671.1165`, apóstrofo), extração `extrair_pdm_id`, `extract_pmib_code` (regex de 4
  dígitos), `limpar_pergunta`, `normalizar_texto`, `_limpar_texto_parrudo`.
  *Aceite*: `pytest -q` verde; nenhuma linha de produção alterada.

- **CP 0.2 — Smoke de importação.**
  Teste que importa todos os módulos `*_backend.py` (com mock de display/imports pesados
  quando preciso) e `python -m compileall .` no CI local (script `scripts/check.sh`).
  *Aceite*: script roda e passa.

### Fase 1 — Fundações core (Excel, config, callbacks)

- **CP 1.1 — `sigft/config.py`.**
  Centralizar: URL do portal, nome da aba "Lista de Materiais", linha inicial 79 das specs,
  prefixo de contrato (hoje `4500063671`, vira configurável), nomes de colunas-chave
  ("CÓDIGO PMIB", "PDM usado", seções de status), carregamento de chaves (.env +
  api_config.json). Nenhum consumidor migra ainda.
  *Aceite*: módulo importável + testes de carga de config.

- **CP 1.2 — `core/excel/pmib_codes.py` + `headers.py`.**
  Implementar `normalize_pmib(valor) -> str` e `find_header_row(df|ws, colunas_chave)` /
  `find_columns(ws, nomes)` cobrindo os comportamentos das 10 variantes (documentados na base
  de conhecimento). Migrar consumidores: `upload_conditions`, `upload_ficha_duplicada`,
  `pdm_backend`, `frontend` (2 pontos), `tech_specs`, `search`, `pmib_manager`, `analyzer`,
  `autospec`, `cria_fichas`.
  *Aceite*: testes do CP 0.1 passam contra a nova implementação; zero regex/ljust de PMIB
  fora de `pmib_codes.py` (verificar com grep).

- **CP 1.3 — `core/excel/locking.py` + `status_sheet.py`.**
  `save_with_retry` unifica os 4 laços de PermissionError (recebe callback `on_locked` que
  devolve retry/cancel). `StatusPMIB` unifica: carregar lookup, buscar linha por PMIB,
  `marcar_completo(pmib, secoes: dict)`. Migrar os 3 escritores de COMPLETO e os 4 laços de
  lock.
  *Aceite*: `upload_conditions`, `tech_specs`, `upload_ficha_duplicada` e `pmib_manager`
  usam `StatusPMIB`/`save_with_retry`; comportamento de UX preservado (mesmos callbacks).

- **CP 1.4 — `core/callbacks.py`.**
  Definir dataclass/protocolo `UICallbacks(log, pause, ask, progress)` com implementações
  no-op. Padronizar a assinatura dos serviços (parâmetro único `callbacks` em vez de 3-4
  parâmetros `callback_*` soltos), mantendo aliases retrocompatíveis.
  *Aceite*: pelo menos 2 serviços migrados como piloto (`lmr`, `apagar_lmr`).

### Fase 2 — Camada RPA unificada (maior ganho)

- **CP 2.1 — `core/rpa/browser.py`.**
  `create_driver(download_dir=None, timeout=20)` substitui as 6 inicializações. Parâmetro
  `download_dir` cobre o caso do `ExtratorFichaBase`.
  *Aceite*: os 6 módulos usam a fábrica; nenhuma chamada direta a `webdriver.Chrome()` fora
  de `browser.py`.

- **CP 2.2 — `core/rpa/portal.py` (classe base `PMIBPortal`).**
  Mover, SEM alterar seletores: `safe_click`, `safe_send_keys`, `check_or_uncheck`,
  `clicar_salvar_visivel`, `excluir_linha_com_confirmacao`, `pesquisar_e_abrir(pmib)`
  (a variante mais robusta: a de `tech_specs`, com retry de StaleElement), stop-flag
  (`solicitar_parada`/`cancelado`), e `ir_para_lista()`. Exceção: o fluxo de 24 TABs do
  `lmr_backend` é SUBSTITUÍDO por `pesquisar_e_abrir` (isso é a única mudança de
  comportamento autorizada da fase — o alvo final é o mesmo botão de edição).
  *Aceite*: as 6 classes de automação herdam/compõem `PMIBPortal`; grep não encontra mais
  `execute_script("arguments[0].click()` fora de `portal.py`; `safe_click` existe em um único
  lugar.

- **CP 2.3 — Sincronização: sleeps → waits.**
  Trocar `time.sleep` por `WebDriverWait`/expected_conditions onde há condição observável
  (elemento clicável, linha presente, tabela visível). Sleeps sem condição observável
  (animações OutSystems) viram constantes nomeadas em `portal.py` (`PAUSA_ANIMACAO = 0.5`)
  para calibração central. Fazer módulo a módulo, um commit por módulo.
  *Aceite*: nenhum `time.sleep(` com literal numérico dentro de `services/`; contagem de
  sleeps reduzida e centralizada.

- **CP 2.4 — `core/rpa/ficha_layout.py`.**
  Unificar os dois `CONFIG_MAP` (analyzer × autospec) em uma fonte única com os ranges
  completos, e os dois consumidores passam a derivar o que precisam dela. Incluir
  `VARIAVEIS_SPECS` e a linha 79 (importada de `config.py`).
  *Aceite*: `CONFIG_MAP` definido uma única vez; testes comparando o mapa unificado com os
  dois antigos (guardados no teste como fixture) para provar equivalência.

### Fase 3 — Camada IA unificada

- **CP 3.1 — `core/ai/gemini.py`.**
  `GeminiClient(api_key, model, system_instruction=None, json_mode=False)` com:
  `generate(prompt) -> str|dict`, retry configurável, rate-limit opcional, limpeza/parse de
  JSON única, safety_settings padrão. Migrar `analyzer`, `cria_fichas`, `upload_conditions`,
  `tech_specs`. `autospec` (LangChain) apenas recebe a chave pelo mesmo caminho.
  *Aceite*: `genai.configure`/`GenerativeModel` só aparecem em `gemini.py`; os nomes de
  modelo saem do código e vão para `config.py`.

- **CP 3.2 — `core/ai/prompts.py`.**
  Extrair os 5 prompts gigantes para constantes nomeadas (ou arquivos `.txt` em
  `core/ai/prompts/`), com funções de montagem que recebem os dados.
  *Aceite*: nenhum prompt multilinha (>15 linhas) dentro de `services/`; diff dos prompts
  gerados é vazio versus os antigos (teste de snapshot).

### Fase 4 — Serviços

- **CP 4.1 — Mover backends para `sigft/services/` com shims.**
  Um commit por módulo, na ordem: `apagar_lmr` → `lmr` → `search` → `pdm` → `translator` →
  `analyzer` → `autospec` → `cria_fichas` → `upload_conditions` → `tech_specs` →
  `ficha_duplicada` → `pmib_manager`. Cada `*_backend.py` da raiz vira
  `from sigft.services.X import *` (shim).
  *Aceite*: app abre pela splash normalmente (os imports dinâmicos continuam resolvendo);
  smoke de importação verde.

- **CP 4.2 — Limpeza de exceções e logging.**
  Substituir `except: pass` por `except Exception as e: callbacks.log(...)` ou exceção
  específica, serviço a serviço, usando a base de conhecimento para decidir onde silêncio era
  intencional (ex.: `driver.quit()`).
  *Aceite*: grep de `except: pass`/`except Exception: pass` zerado em `services/` e `core/`
  (exceções documentadas em PENDENCIAS.md quando mantidas de propósito).

- **CP 4.3 — Otimizações de I/O do `pdm`.**
  `pdms_fromItaipu_lista_geral`: abrir a origem 1× e gerar os N arquivos a partir de uma
  única leitura. `aplicar_templates_fichas`: carregar o template 1× e clonar em memória
  (`copy.deepcopy` do workbook ou reabrir de bytes em `BytesIO`).
  *Aceite*: saída byte-idêntica em um caso de teste sintético (criar mini-planilha em
  `tests/fixtures/`); tempo medido menor.

### Fase 5 — UI

- **CP 5.1 — `app/theme.py` + `app/widgets/console.py` + `module_frame.py`.**
  `ConsoleFrame` com `log()` thread-safe único; `ModuleFrame` base (header/content/console/
  progresso). Migrar 2 telas piloto (`ApagarLMR`, `Translator`).
  *Aceite*: telas piloto idênticas visualmente; `frontend.py` reduzido.

- **CP 5.2 — `widgets/pickers.py` + `widgets/dialogs.py`.**
  `FilePickerRow` (botão+label+cor), `FolderPickerRow`, `FileQueueList` (listbox com
  adicionar/remover/limpar), `PausaLoginDialog`, `RetryLockDialog`,
  `SelecaoMultiplaDialog`, `DataFrameSelecaoDialog`. Migrar as 6 `Janela*` e os padrões
  repetidos.
  *Aceite*: as 4 cópias da janela de login e as 2 cópias do FileQueueList substituídas.

- **CP 5.3 — Quebrar `frontend.py` em `app/views/*.py`.**
  Uma view por arquivo; `app/main.py` monta sidebar e registra views; splash simplificada
  (imports normais — o lazy-load por importlib deixa de ser necessário com o pacote).
  *Aceite*: `python -m sigft.app.main` abre o app; `frontend.py` vira shim de ~5 linhas.

### Fase 6 — Qualidade contínua

- **CP 6.1 — Lint e formatação**: `ruff` configurado (`pyproject.toml`), correções
  automáticas aplicadas. *Aceite*: `ruff check .` verde.
- **CP 6.2 — Type hints nas APIs públicas de `core/` e `services/`.** *Aceite*: `mypy`
  (modo leniente) verde em `core/`.
- **CP 6.3 — Empacotamento**: spec do PyInstaller versionado, README de build.
- **CP 6.4 — Isolamento Windows**: `xlwings`/`os.startfile` atrás de `core/platform.py`
  com mensagens claras em outros SOs.

---

## 4. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| RPA não é testável offline (portal OutSystems real) | XPaths/fluxos intocáveis nas Fases 1-4; toda mudança de sincronização (CP 2.3) preserva a condição de espera equivalente; validação manual pelo usuário por módulo antes de avançar de fase |
| Regressão silenciosa no Excel | Testes de caracterização (CP 0.1) escritos ANTES de mover; fixtures sintéticas em `tests/fixtures/` |
| App quebrar no meio da migração | Shims de compatibilidade mantêm todos os nomes antigos importáveis até o CP 5.3 |
| IDs OutSystems (`b10-...`) mudarem em deploy do portal | Fora do escopo da refatoração; centralizar os XPaths em `portal.py`/páginas facilita o conserto futuro |

## 5. Fora de escopo (registrar, não fazer agora)

- Trocar Selenium por Playwright.
- Banco de dados no lugar das planilhas.
- Login automático no portal (hoje manual, por design).
- Internacionalização da UI.

---

## 6. Status dos Checkpoints

| Checkpoint | Status | Data | Observações |
|---|---|---|---|
| 0.1 Testes de caracterização | ☐ pendente | | |
| 0.2 Smoke de importação | ☐ pendente | | |
| 1.1 config.py | ☐ pendente | | |
| 1.2 pmib_codes + headers | ☐ pendente | | |
| 1.3 locking + status_sheet | ☐ pendente | | |
| 1.4 callbacks | ☐ pendente | | |
| 2.1 browser.py | ☐ pendente | | |
| 2.2 PMIBPortal | ☐ pendente | | |
| 2.3 sleeps → waits | ☐ pendente | | |
| 2.4 ficha_layout unificado | ☐ pendente | | |
| 3.1 GeminiClient | ☐ pendente | | |
| 3.2 prompts.py | ☐ pendente | | |
| 4.1 services + shims | ☐ pendente | | |
| 4.2 exceções e logging | ☐ pendente | | |
| 4.3 otimizações pdm | ☐ pendente | | |
| 5.1 theme/console/module_frame | ☐ pendente | | |
| 5.2 pickers + dialogs | ☐ pendente | | |
| 5.3 views + main | ☐ pendente | | |
| 6.1 ruff | ☐ pendente | | |
| 6.2 type hints | ☐ pendente | | |
| 6.3 PyInstaller | ☐ pendente | | |
| 6.4 isolamento Windows | ☐ pendente | | |

## 7. Notas da transcrição inicial (já aplicadas no Checkpoint 1 do bootstrap)

- As 4 chaves de API que estavam hardcoded na `HomeView` foram removidas (usar `.env` /
  `api_config.json`). **As chaves expostas devem ser rotacionadas.**
- `ModuloCriaFichas` tinha um par morto de `run_edicao_thread`/`_edicao_worker` (referenciava
  `self.text_lista_pmibs`, inexistente, e era sobrescrito pela definição posterior). Apenas a
  versão operante foi mantida na transcrição.
