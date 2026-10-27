# Revisão das listas pelo AMP (n8n): plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o botão "Revisar no AMP" do SIG-FT. Ele manda cada lista com divergência para um workflow do n8n da GE e grava o HTML que o agente devolve. Quando a chamada falha, sai um diagnóstico copiável.

**Architecture:**
- O workflow do n8n é gerado em Python a partir do `pedido.md` e versionado em `amp/revisao_de_listas/`.
- No SIG-FT, `core/amp/cliente.py` fala com o webhook pelo `core/rede.py`.
- `services/revisao_amp.py` monta o pedido (o texto dos PDFs e o `_STATUS_PMIB` separado por tabulação), roda as listas uma a uma, grava o HTML e escreve o diagnóstico.
- A tela da Conferência ganha os botões e a coluna "AMP".

**Tech Stack:** Python 3.10+, PySide6, PyMuPDF (`fitz`), openpyxl, pytest e pytest-qt. No workflow: os nós Webhook, If, Code, Respond to Webhook e Basic LLM Chain do n8n.

**Spec:** `docs/superpowers/specs/2026-10-27-amp-revisao-de-listas-design.md`

## Global Constraints

- **Português:** código, docs e mensagens em português; commit sem acento; texto de tela em `t()` / `marcar()`, com tradução em `es.json` e `en.json`.
- **Verificação antes de cada commit:** `python -m ruff check .` limpo e `bash scripts/check.sh` verde, menos as 2 falhas conhecidas do tradutor (`test_caminho_longo_*`).
- **Chaves:** `AMP_WEBHOOK_URL` → `SIGFT_AMP_WEBHOOK_URL` e `AMP_WEBHOOK_CHAVE` → `SIGFT_AMP_WEBHOOK_CHAVE`.
- **Cabeçalho da chave:** `X-SIGFT-Chave`. O caminho do webhook é `sigft-revisao-listas`.
- **Limites por chamada:** `ping` 30 s, `eco` 120 s, `revisar` 900 s.
- **Nome do HTML:** `<código>[<em uso>-<atual>] revisao AMP.html`. Nunca sobrescreve; com o nome ocupado, acrescenta " (2)", " (3)"...
- **Diagnóstico:**
  - sem a chave e sem texto de documento;
  - corpo da resposta até 1500 caracteres;
  - gravado em `pasta_logs() / "amp"`.
- **Fronteiras:** nada importado dos módulos do AutoSpec, que são da frente do Rafael (`CLAUDE.md`).
- **Tipos de nó no workflow:**
  - `n8n-nodes-base.webhook` v2, `n8n-nodes-base.if` v2 e `n8n-nodes-base.code` v2;
  - `n8n-nodes-base.respondToWebhook` v1.1 e `n8n-nodes-base.stickyNote` v1;
  - `@n8n/n8n-nodes-langchain.chainLlm` v1.5. O GEV LLM Model é ligado à mão.

## Review Focus

1. **O webhook devolve HTML, não JSON** (página de login, de proxy, ou o workflow sem o nó de resposta). Esperado: a lista falha com o diagnóstico, e a rodada segue. Teste na Tarefa 3.
2. **HTTP 200 sem HTML** (o agente respondeu texto). Esperado: a lista falha com "o agente não devolveu HTML", e o diagnóstico mostra o corpo. Teste na Tarefa 3.
3. **`_STATUS_PMIB` sem a aba ou sem o cabeçalho, ou PDF só com imagem.** Esperado: a lista sai como "falta: ..." e não é chamada. Teste na Tarefa 2.
4. **Queda de rede no meio da rodada.** Esperado: só aquela lista falha, as outras são chamadas, e o diagnóstico traz `rede.resumo_erro`. Teste na Tarefa 4.
5. **Chave ou endereço não configurados.** Esperado: os botões avisam onde configurar e não chamam nada. Teste na Tarefa 5.

---

### Task 1: o workflow do n8n

**Files:**
- Create: `amp/revisao_de_listas/pedido.md`: o pedido da §5 do desenho, em português, curto. Os conteúdos entram depois do pedido, com os títulos `## REVISÃO EM USO`, `## REVISÃO ATUAL` e `## _STATUS_PMIB`.
- Create: `amp/revisao_de_listas/gerar_workflow.py`
- Create: `amp/revisao_de_listas/workflow_revisao_de_listas.json`, gerado.
- Create: `amp/revisao_de_listas/LEIA-ME.md`, com estas seções:
  - o passo a passo da §6 do desenho;
  - como achar a execução pelo número;
  - "Se der errado: o que colar numa conversa nova".
- Test: `tests/test_amp_workflow.py`

**Interfaces:**
- Produces: `montar_workflow(pedido: str, versao: str) -> dict`; `VERSAO_WORKFLOW: str` (data, `"2026-10-27"`); `main(argv=None) -> int`, que grava o `.json` ao lado com `indent=2` e `ensure_ascii=False`.
- O contrato de resposta, que a Tarefa 3 consome:
  - `ping` → `{"ok": true, "modo": "ping", "versao_workflow", "execucao"}`;
  - `eco` → `{"ok": true, "modo": "eco", "texto", "versao_workflow", "execucao"}`;
  - `revisar` → `{"ok": bool, "modo": "revisar", "html", "versao_workflow", "execucao", "erro"?}`;
  - erro do agente → HTTP 502 `{"ok": false, "modo", "etapa": "agente", "erro", "execucao"}`.

- [ ] **Passo 1: Escreva os testes que falham.**
  - `test_o_json_versionado_e_o_que_o_gerador_produz`: o `json.load` do arquivo é igual a `montar_workflow(pedido.md, VERSAO_WORKFLOW)`.
  - `test_webhook_com_header_auth_e_resposta_por_no`: um nó `n8n-nodes-base.webhook` com `httpMethod="POST"`, `path="sigft-revisao-listas"`, `authentication="headerAuth"` e `responseMode="responseNode"`.
  - `test_ping_nao_passa_pelo_agente`: a saída verdadeira do If chega a um respondToWebhook sem passar pelo `chainLlm`.
  - `test_erro_do_agente_responde_502`: o `chainLlm` tem `onError="continueErrorOutput"`, e a saída 1 vai para um respondToWebhook com `options.responseCode == 502`.
  - `test_toda_conexao_aponta_para_no_que_existe`.
  - `test_o_pedido_carrega_as_regras_da_equipe`: o `jsCode` de "Monta o pedido" contém `SEM_LISTA_STATUS_PMIB`, `OBSERVAÇÕES`, `DOCUMENTAL`, `a conferir` e `tabulação`.
- [ ] **Passo 2:** Rode. Esperado: FAIL (módulo ausente).
- [ ] **Passo 3:** Implemente o gerador:
  - os nós da tabela da §6 do desenho, com `id` e `webhookId` fixos (UUIDs constantes, para o JSON não mudar a cada geração);
  - uma nota adesiva com os 5 passos de ligar o GEV LLM Model e a credencial;
  - o pedido entra no `jsCode` como `const PEDIDO = <json.dumps do pedido>;`;
  - para importar o gerador, o teste usa `importlib` pelo caminho do arquivo, porque `amp/` não é pacote;
  - gere o `.json` com `python amp/revisao_de_listas/gerar_workflow.py` e escreva o `LEIA-ME.md`.
- [ ] **Passo 4:** Rode `pytest tests/test_amp_workflow.py` (PASS) e o `ruff`.
- [ ] **Passo 5:** Commit: `Workflow do n8n da revisao das listas (pedido, gerador e leia-me)`.

### Task 2: o pedido de cada lista

**Files:**
- Modify: `sigft/services/conferencia_revisoes.py`: `resolver_status_pmib(link, pasta_mapeadora, codigo, pasta_raiz, *, levantamento=None) -> Path | None` devolve o ARQUIVO, e `resolver_pasta` passa a ser `resolver_status_pmib(...).parent`.
- Create: `sigft/services/revisao_amp.py` (a parte de leitura).
- Test: `tests/test_revisao_amp_pedido.py` e, no `tests/test_conferencia_revisoes.py`, `test_resolver_status_pmib_devolve_o_arquivo`.

**Interfaces:**
- Consumes: `Conferencia`, `ItemConferencia`, `Download`, `nome_do_pdf` e `resolver_status_pmib` (`conferencia_revisoes`); `revisao_acima_do_cabecalho` (`status_pmib_arquivos`); `headers.find_header_row`; `config.ABA_LISTA_MATERIAIS_VARIANTES`.
- Produces:
  - `@dataclass(frozen=True) TextoPdf`: `paginas: int` e `texto: str`;
  - `texto_do_pdf(caminho: Path, *, abrir=None) -> TextoPdf`: `abrir` é `fitz.open` por padrão. Monta `"--- página N ---\n<texto>"` por página. Página nenhuma com texto → `ValueError("PDF sem texto (só imagem)")`;
  - `@dataclass(frozen=True) TabelaStatus`: `aba`, `linha_de_revisao`, `linhas: int`, `tsv: str` e `codigos_material: list[str]`;
  - `status_pmib_em_tsv(caminho: Path) -> TabelaStatus`: openpyxl `read_only` e `data_only`; o cabeçalho é achado por `"CÓDIGO DO MATERIAL"` nas 10 primeiras linhas; vai do cabeçalho até a última linha com valor; células vazias viram `""`; números inteiros sem `.0`. Sem aba ou sem cabeçalho → `ValueError` com o motivo;
  - `@dataclass(frozen=True) ListaParaAmp`: `item: ItemConferencia`, `status_pmib: Path | None`, `pdf_em_uso: Path | None`, `pdf_atual: Path | None`, `revisao_atual: str` e `falta: str = ""`;
  - `listas_para_amp(conferencia, downloads: list[Download], pasta_mapeadora: Path, pasta_raiz: Path | None) -> list[ListaParaAmp]`. Usa as listas com pasta, na ordem de `por_categoria()`. A regra dos PDFs é a da §10 do desenho. O `falta` diz o que falta: `"falta: PDF da revisão atual"`, `"falta: PDF da revisão em uso"` ou `"falta: _STATUS_PMIB"`;
  - `montar_pedido(lista: ListaParaAmp, versao_sigft: str, *, ler_pdf=texto_do_pdf, ler_status=status_pmib_em_tsv) -> dict`: o JSON da §4 do desenho.

- [ ] **Passo 1: Escreva os testes que falham.** Use PDF falso (um `abrir` que devolve páginas com `get_text`) e `_STATUS_PMIB` real pelo `openpyxl_de_verdade`, com o título, a linha de revisão e o cabeçalho na linha 5.
  - `test_texto_do_pdf_marca_as_paginas` (`"--- página 2 ---"` no texto, `paginas == 2`);
  - `test_pdf_so_imagem_e_falta`;
  - `test_status_em_tsv_tem_a_linha_de_revisao_e_o_cabecalho` (a 1ª linha do `tsv` começa por `ITEM\t`, `linhas == 3`, `"1"` e não `"1.0"`);
  - `test_status_sem_cabecalho_avisa`;
  - `test_listas_usam_os_pdfs_baixados_na_sessao` (a revisão atual 0C, vinda do `Download`, vence a 0B da mapeadora);
  - `test_listas_sem_download_procuram_pelo_nome`;
  - `test_lista_sem_revisao_em_uso_nao_exige_esse_pdf`;
  - `test_o_que_falta_aparece_e_a_ordem_e_a_das_categorias`;
  - `test_pedido_tem_os_tres_conteudos_e_a_lista` (`modo == "revisar"`, `revisao_em_uso is None` quando não há).
- [ ] **Passo 2:** Rode. Esperado: FAIL.
- [ ] **Passo 3:** Implemente.
- [ ] **Passo 4:** Rode os testes (PASS), o `ruff` e o `check.sh`.
- [ ] **Passo 5:** Commit: `Pedido de cada lista para o AMP (texto dos PDFs e STATUS_PMIB em tabulacao)`.

### Task 3: o cliente do webhook

**Files:**
- Create: `sigft/core/amp/__init__.py` e `sigft/core/amp/cliente.py`.
- Test: `tests/test_amp_cliente.py`

**Interfaces:**
- Consumes: `rede.abrir(url, metodo="POST", json=..., headers=..., timeout=..., status_ok=None, log_cb=...)`, `rede.FalhaDeRede` e `rede.resumo_erro`.
- Produces:
  - `CABECALHO_CHAVE = "X-SIGFT-Chave"`; `TEMPOS = {"ping": 30, "eco": 120, "revisar": 900}`;
  - `@dataclass(frozen=True) RespostaAmp`: `ok: bool`, `modo: str`, `http: int | None`, `segundos: float`, `corpo: str`, `dados: dict`, `erro: str = ""`, e as propriedades `html`, `texto`, `execucao` e `versao_workflow`, lidas de `dados`;
  - `ClienteAmp(url: str, chave: str, *, abrir=None, relogio=time.monotonic, log_cb=lambda _m: None)`;
  - os métodos `ping() -> RespostaAmp`, `eco(codigos: list[str]) -> RespostaAmp` e `revisar(pedido: dict) -> RespostaAmp`.
  - **Nunca levanta exceção.** A falha volta em `ok=False` com `erro` legível:
    - `FalhaDeRede` → `erro = "Sem conexão com o AMP: " + resumo_erro`;
    - resposta que não é JSON → "o AMP não respondeu JSON (HTTP N)";
    - HTTP ≥ 400 → o `erro` do JSON ou "HTTP N";
    - `revisar` sem `<html` nem `<table` no `html` → "o agente não devolveu HTML".

- [ ] **Passo 1: Escreva os testes que falham.** Use o `abrir` dublê do `test_aconex_cliente.py`.
  - `test_a_chave_vai_no_cabecalho_e_nao_no_corpo`;
  - `test_ping_le_a_versao_e_a_execucao`;
  - `test_resposta_que_nao_e_json_vira_erro_com_o_corpo`;
  - `test_502_do_agente_traz_etapa_e_erro`;
  - `test_200_sem_html_e_falha`;
  - `test_falha_de_rede_nao_levanta`;
  - `test_tempo_por_modo` (o `timeout` passado ao `abrir` segue `TEMPOS`).
- [ ] **Passo 2:** Rode. Esperado: FAIL.
- [ ] **Passo 3:** Implemente.
- [ ] **Passo 4:** Rode os testes (PASS), o `ruff` e o `check.sh`.
- [ ] **Passo 5:** Commit: `Cliente do webhook do AMP (ping, eco e revisar sobre core/rede)`.

### Task 4: a rodada, a gravação e o diagnóstico

**Files:**
- Modify: `sigft/services/revisao_amp.py` (a parte da rodada).
- Test: `tests/test_revisao_amp_rodada.py`

**Interfaces:**
- Consumes: Tarefas 2 e 3; `dados_usuario.pasta_logs()`.
- Produces:
  - `nome_do_html(codigo: str, em_uso: str, atual: str) -> str`: os reservados do Windows viram `_`; sem revisão em uso, fica `[-<atual>]`;
  - `gravar_html(pasta: Path, nome: str, html: str) -> Path`: grava com `open(..., "x")` em UTF-8 e acrescenta " (2)", " (3)"... se o nome existir;
  - `@dataclass(frozen=True) ResultadoAmp`: `lista: ListaParaAmp`, `situacao: Literal["pronto", "falhou", "falta", "parado"]`, `html: Path | None`, `detalhe: str` e `diagnostico: str = ""`;
  - `diagnostico(lista: ListaParaAmp, pedido: dict | None, resposta: RespostaAmp | None, *, url: str, chave_posta: bool, versao_sigft: str, erro: str = "") -> str`. O texto leva:
    - o cabeçalho "SIG-FT · Revisão no AMP · diagnóstico";
    - os números do pedido (páginas e caracteres dos textos, linhas do `_STATUS_PMIB`), nunca o texto;
    - a resposta (HTTP, segundos, execução, corpo até 1500 caracteres);
    - o endereço e se a chave está posta;
    - os arquivos do repositório envolvidos.
  - `revisar_listas(listas, cliente, *, versao_sigft, url, chave_posta, log_cb, progress_cb=None, cancelado_cb=None, gravar_diagnostico=True) -> list[ResultadoAmp]`. Uma por vez:
    - a lista com `falta` vira `"falta"` e não é chamada;
    - erro ao ler (`ValueError`, `OSError`) vira `"falta"` com o motivo;
    - o `cancelado_cb` é lido entre as listas (`"parado"`);
    - cada falha grava o diagnóstico em `pasta_logs() / "amp" / f"{AAAAMMDD-HHMMSS} {codigo}.txt"`, sem os reservados.
  - `codigos_para_eco(listas: list[ListaParaAmp]) -> list[str]`: os códigos das listas e até 10 CÓDIGOS DO MATERIAL do primeiro `_STATUS_PMIB` legível.
  - `testar_conexao(cliente, listas) -> list[str]`: as linhas para o console, `OK`/`FALHOU` de `ping` e `eco`. O `eco` passa quando todo código volta igual no texto.

- [ ] **Passo 1: Escreva os testes que falham.**
  - `test_html_gravado_com_o_nome_do_padrao`;
  - `test_nunca_sobrescreve`;
  - `test_falta_nao_chama`;
  - `test_falha_de_rede_numa_lista_e_as_outras_seguem`;
  - `test_diagnostico_sem_texto_de_documento_e_sem_chave` (o texto do PDF falso e a chave falsa não aparecem; os números aparecem);
  - `test_diagnostico_vai_para_a_pasta_de_logs`;
  - `test_cancelar_entre_as_listas`;
  - `test_eco_acusa_codigo_mascarado` (o modelo devolve `"#ITA0=***"` → `FALHOU ... mascarado`).
- [ ] **Passo 2:** Rode. Esperado: FAIL.
- [ ] **Passo 3:** Implemente.
- [ ] **Passo 4:** Rode os testes (PASS), o `ruff` e o `check.sh`.
- [ ] **Passo 5:** Commit: `Rodada da revisao no AMP: grava o HTML sem sobrescrever e diagnostico copiavel`.

### Task 5: as chaves e a tela

**Files:**
- Modify:
  - `sigft/config.py` (`ENV_VAR_POR_CHAVE`);
  - `api_config.example.json`;
  - `sigft/app_qt/views/home.py` (`CHAVES_API`: `("AMP_WEBHOOK_URL", marcar("AMP (endereço do webhook):"))` e `("AMP_WEBHOOK_CHAVE", marcar("AMP (chave do webhook):"))`);
  - `sigft/app_qt/views/conferencia_revisoes.py`;
  - `sigft/app/idiomas/es.json` e `en.json`;
  - os testes que travam esses valores: `tests/test_config.py`, `tests/test_qt_home_paineis.py` (a lista e a medida do painel de chaves).
- Test: `tests/test_qt_tela_conferencia_revisoes.py`

**Interfaces:**
- Consumes: Tarefas 2 a 4; `config.carregar_chaves()` e `config.get_key(...)`; `QApplication.clipboard()`.
- Produces na tela:
  - `btn_amp` ("Revisar no AMP"), `btn_testar_amp` ("Testar conexão com o AMP") e `btn_copiar_diag` ("Copiar diagnóstico", ligado só com falhas);
  - a coluna `marcar("AMP")` em `COLUNAS`;
  - `self.resultados_amp: list[ResultadoAmp]`.
  - A tela guarda a última `Conferencia`, os `Download` e a `Mapeadora` da rodada de "Conferir revisões".
  - Sem conferência na sessão: aviso "Confira as revisões antes."
  - Sem endereço ou sem chave: aviso "Configure o endereço e a chave do webhook do AMP em Configuração → Chaves de API." Nada é chamado.

- [ ] **Passo 1: Escreva os testes que falham**, com o serviço e o cliente trocados por monkeypatch:
  - `test_sem_chave_avisa_e_nao_chama`;
  - `test_sem_conferencia_avisa`;
  - `test_revisar_mostra_o_resultado_na_coluna_amp`;
  - `test_falha_liga_o_copiar_e_copia_os_diagnosticos`;
  - `test_testar_conexao_amp_escreve_as_linhas`;
  - os testes de chave e painel atualizados.
- [ ] **Passo 2:** Rode. Esperado: FAIL.
- [ ] **Passo 3:** Implemente a tela e as traduções (`tools/textos_da_interface.py --faltando es|en` vazio).
- [ ] **Passo 4:** Rode os testes (PASS); `ruff`; `check.sh`; `QT_QPA_PLATFORM=offscreen python frontend.py --smoke` (13 telas).
- [ ] **Passo 5:** Commit: `Tela: Revisar no AMP, Testar conexao com o AMP e Copiar diagnostico`.

### Task 6: documentos

**Files:**
- Modify:
  - `CHANGELOG.md`: itens no bloco `## 1.3.1` em aberto, um por linha, com "Conferência de Revisões:" na frente;
  - `docs/ROTEIRO_DE_TESTE.md`: a Etapa 5c, os passos da §9 do desenho, e as linhas dela no quadro de resultado;
  - `docs/base-conhecimento/14-aconex-e-conferencia-de-revisoes.md`: a seção "Peça 2: revisão no AMP";
  - `docs/ACONEX_AO_VIVO.md`: onde parou e como continuar a peça 2;
  - `docs/refatoracao/PENDENCIAS.md`:
    - a atualização automática para a 1.3.1-rc.1 que não funcionou na GE (relato do Luan em 27/10; pedir o `sigft.log` e o `instalacao.log`);
    - os testes S4 e S5 do AMP;
  - `CLAUDE.md`: a pasta `amp/` na tabela de documentação.

- [ ] **Passo 1:** Escreva os documentos.
- [ ] **Passo 2:** Rode `bash scripts/check.sh` (verde) e o ensaio das notas, `python tools/gerar_manifesto.py ... --versao 1.3.1-rc.N`, com o bloco 1.3.1.
- [ ] **Passo 3:** Commit: `Documentos da revisao no AMP: changelog, roteiro, base de conhecimento e pendencias`.
