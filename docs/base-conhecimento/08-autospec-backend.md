# AutoSpec Backend (`sigft/services/autospec.py`)

> ⚠️ **Onde o código mora hoje** (atualizado em 2026-08-28)
>
> Este documento foi escrito antes da refatoração e descreve o comportamento do
> módulo, que continua valendo. Mas os CAMINHOS mudaram:
>
> | O que o texto abaixo chama de | Está hoje em |
> |---|---|
> | `autospec_backend.py` | `sigft/services/autospec.py` + `autospec_conferencia.py`, `autospec_embeddings.py`, `autospec_rag.py`, `autospec_unidades.py` |
> | a tela | `sigft/app/views/autospec.py` |
>
> A lógica de negócio descrita aqui continua válida; o que mudou foi onde ela vive. Camadas novas que este texto não menciona: `sigft/core/excel/` (cabeçalho de planilha, código PMIB, gravação com retry), `sigft/core/llm/` (cliente de IA multi-provedor), `sigft/core/rpa/` (portal e motor), `sigft/core/callbacks.py` (o protocolo UI↔serviço).

> **Onde o código mora:** `sigft/services/autospec.py` (580 linhas) desde o CP 4.1.
> `autospec_backend.py` na raiz é só um **shim** que faz `sys.modules[__name__] = _modulo` —
> os dois nomes apontam para o MESMO objeto de módulo, então `monkeypatch` por qualquer um
> dos dois funciona. Não coloque lógica no shim.
>
> **Regras de negócio e o "porquê" do módulo:** [`08b-autospec-contexto-negocio.md`](08b-autospec-contexto-negocio.md).
>
> **Atualizado em 2026-08-11** para refletir os CP 3.1/3.2/4.1/4.4. Os números de linha
> citados abaixo são de `sigft/services/autospec.py` e envelhecem rápido — use-os como pista,
> confirme pelo nome do símbolo.

## Propósito
Automatiza o preenchimento de fichas técnicas padrão via RAG (Retrieval-Augmented Generation). O módulo analisa campos vazios na ficha, recupera contexto de documentos locais e web, consulta um modelo de IA para gerar respostas técnicas inteligentes e preenche a planilha com fonte azul e sufixo `_completed`.

**Qual modelo:** não está mais no código. Vem de `sigft/config.py` → `LLM_TASKS["autospec"]`
(hoje `gemini-3-flash-preview`), com `LLM_MODELOS_HOJE["autospec"]` (`gemini-3.1-pro-preview`)
guardado como baseline de equivalência do CP 3.1. Trocar o modelo é editar config ou usar o
seletor da Home — nunca editar este módulo.

## Entradas e Saídas
- **Entradas**: 
  - Arquivo ficha técnica (aba "Ficha Técnica Padrão") com configuração de células mapeadas em `CONFIG_MAP`
  - Arquivo `_STATUS_PMIB.xlsx` para extração do código PMIB e descrição do material
  - Documentos locais (PDF/HTML) referenciados na fila
  - Chaves de API (Gemini, LlamaParse, Google Custom Search)
- **Saídas**: 
  - Arquivo renomeado com sufixo `_completed` contendo células preenchidas com fonte azul (cor 0000FF)
  - Logs de progresso (msg, etapa)

## Classes e Funções

### `GENERATIVE_FIELDS` (constante, linha 37)
Lista de campos que podem ser gerados por IA com base em boas práticas quando não há dados explícitos. Inclui: empilhamento, embalagem_transporte, transporte, preservacao, metodo_limpeza, ferramentas_para_preservacao, tipo_legislacao, tipo_descarte, protecao, posicao_armazenamento, unidade, tipo.

### `CONFIG_MAP` — ⚠️ **não é mais definido aqui**
Desde o CP 2.4 vem de `sigft/core/rpa/ficha_layout.py` (linha 16:
`from sigft.core.rpa.ficha_layout import CONFIG_MAP, VARIAVEIS_SPECS`). É **fonte única
compartilhada com o `analyzer`** — mexer nele muda os dois módulos ao mesmo tempo. Ver
`docs/refatoracao/TRABALHO_PARALELO.md` §4 antes de alterar; só ACRESCENTE chave, nunca
remova nem renomeie (119 testes de equivalência em `tests/test_ficha_layout.py` guardam isso).

Uma pegadinha do CP 2.4: `range` agora guarda o span COMPLETO da célula mesclada (`"H6:P6"`),
não a primeira célula (`"H6"`). Quem precisa só da primeira faz `.split(":")[0]` — sem isso,
`ws["H6:P6"]` devolve tupla de tuplas e `.value` quebra.

Dicionário de configuração por campo. Cada entrada contém:
- `range` ou `cells`: localização na planilha (ex: H6, ou lista [F10, F12])
- `type`: "cell" (texto) ou "checkbox" (múltiplas opções)
- `validation`: "simple" (texto/número) ou "ai" (requer IA)
- `weight`: importância relativa (1-7)
- `desc`: descrição do campo (cm, kg, opcções, etc.)

Exemplos: `texto_breve_material` em H6, `embalagem_transporte` em M42 (tipo "ai"), `posicao_armazenamento` em G25/G27/G29 (checkboxes).

### `WebSearcher` (linha 60-108)
Realiza buscas na web via Google Custom Search API.
- `__init__(api_key, cse_id)`: inicializa com credenciais
- `search_and_download(query, required_terms=[], max_results=3)`: busca com termos obrigatórios, retorna lista de dicts `{path, url, title}` com PDFs/HTMLs baixados em temp
- `_download_file(url)`: baixa arquivo com timeout de 15s, detecta .pdf ou .html, retorna caminho temp

### `PDFProcessor` (linha 110-151)
Extrai texto de documentos com fallback em cascata.
- `__init__(llama_key)`: configura LlamaParse se chave fornecida
- `extract_text(filepath)`: tenta LlamaParse → PyPDF2 → BeautifulSoup (HTML), retorna tupla `(texto, metodo_usado)`

### `AutoSpecCore` (linha 153-580)
Orquestra o pipeline RAG completo.
- `__init__(gemini_key, llama_key, google_search_key, google_cse_id, *, chaves=None, selecao_resolvida=None)`: valida a chave **do provedor resolvido** (ver "Guard de chave" abaixo), instancia LLM, WebSearcher, PDFProcessor. `chaves`/`selecao_resolvida` são keyword-only com default `None` — pontos de injeção para teste, mesmo contrato de `get_llm`; nenhum call site existente precisou mudar
- `_resolver_selecao(selecao_resolvida)` / `_validar_chave_do_provedor(provider_id, gemini_key, chaves)` (estáticos): a resolução de provedor e o guard, separados para serem testáveis isoladamente
- `extract_pmib_code(input_filepath)`: regex sobre nome arquivo, busca padrão `\d{10}\.(\d{4})`, retorna sufixo de 4 dígitos
- `find_header_columns(pmib_sheet)`: varredura linha 1-10 procurando por "CÓDIGO PMIB", "DESCRIÇÃO", "CÓDIGO MATERIAL", retorna tupla `(pmib_col_idx, desc_col_idx, mat_col_idx, start_row)`
- `get_pmib_data(pmib_path, code_suffix)`: lê planilha _STATUS_PMIB, procura código com sufixo, retorna tupla `(descrição_completa, código_material)` ou `("", "")`
- `is_empty(val)`: célula vazia, em branco, ou cujo texto **INICIA COM** "FORNECER" (`.startswith`, não "contém") — a instrução do formulário conta como pendente, um valor real não
- `analyze_sheet(filepath, status_pmib_path)`: lê ficha, detecta campos vazios (estáticos via CONFIG_MAP e dinâmicos na linha 79+), retorna tupla `(workbook, missing_dict, txt_breve, fabricante, desc_comp, cod_mat)` onde `missing_dict` mapeia campo → `{type, desc, ref}`
- `retrieve_context(txt_brv, fab, cod_mat, refs_locais)`: pipeline RAG de 2 etapas: processa documentos locais via PDFProcessor, depois busca web com 2 queries (por código material + por descrição breve), limita resultado a 50k caracteres por doc, retorna tupla `(contexto_completo, lista_urls)`
- `process_local_documents(paths)`: aplica PDFProcessor a cada caminho, limita a 60k chars/doc
- `generate_ai_response(txt_brv, fab, desc_comp, missing, context)` (linha 321): monta prompt JSON com nome/descrição/fabricante/contexto e instruções (prioriza LOCAL DOC, gera padrão para GENERATIVE_FIELDS, deixa vazio para ESTRITO, checkboxes deduzem melhor opção), chama `self._llm.generate(...)` e retorna dict `{field_id: resposta}`. **LangChain foi removido no CP 3.2** — `self._llm` é um `LLMClient` obtido por `get_llm("autospec", ...)`; o parse de JSON é o `_limpar_e_parsear_json` único do client (tolera fences/prosa ao redor, cobre objeto e lista), e a política de retry (2 retentativas, 5s, rate-limit 60s) passou a valer aqui pela primeira vez — o LangChain não tinha retry nenhum. `temperature=0.1` foi preservada via `_POLITICA_RETRY_POR_TAREFA["autospec"]`
- `fill_save(wb, filepath, ai_data, missing)`: preenche células com fonte azul (0000FF), para checkboxes marca célula com "X", salva com sufixo `_completed`, retorna novo caminho
- `process_queue(queue, status_pmib_path)`: generator que yields logs para UI, processa lista de tarefas `{sheet: path, refs: [paths]}` em sequência (1 a N), chamando analyze_sheet → retrieve_context → generate_ai_response → fill_save

## Fluxo detalhado

1. **Análise da Ficha** (analyze_sheet)
   - Abre workbook, valida aba "Ficha Técnica Padrão"
   - Extrai código PMIB do nome arquivo (último 4 dígitos)
   - Se status_pmib_path fornecido, busca descrição completa e código material nele
   - Verifica células fixas em CONFIG_MAP: se vazia, adiciona a `missing`
   - Verifica checkboxes: se todas vazias, adiciona a `missing`
   - Itera linhas 79+ procurando perguntas na coluna C (idx 3), respostas na coluna M (idx 13)

2. **Recuperação de Contexto** (retrieve_context)
   - Processa documentos locais: PDFProcessor extrai texto (max 60k chars cada)
   - Busca web: se Google API disponível, monta 2 queries ordenadas por especificidade (código material primeiro, depois descrição breve)
   - Filtra resultados por required_terms (fabricante, código material)
   - Baixa e processa PDFs/HTMLs encontrados (max 50k chars cada)
   - Concatena local + web, retorna tupla (contexto_total, lista_urls)

3. **Geração IA** (generate_ai_response)
   - Monta prompt com: dados (nome, descrição, fabricante), contexto, instruções
   - Para cada campo faltante, adiciona linha com ID, descrição, tipo (INFO TÉCNICA PADRÃO vs ESTRITO)
   - Envia via `LLMClient.generate()` (`get_llm("autospec", ...)`) — provedor e modelo vêm de `config.LLM_TASKS`
   - Parse do JSON pelo `_limpar_e_parsear_json` do client; retry conforme a política da tarefa
   - Retorna dict: `{field_id: valor_gerado}`

4. **Preenchimento e Salvamento** (fill_save)
   - Para campos de texto: escreve valor em célula, aplica Font(color=0000FF)
   - Para campos dinâmicos (linha 79+): extrai número com regex se necessário (ex: empilhamento)
   - Para checkboxes: limpa todas as opções, marca a célula com "X" em azul
   - Salva workbook com nome `{base}_completed.xlsx`

5. **Fila de Processamento** (process_queue)
   - Generator que yields strings de log ou tuplas (msg, progresso)
   - Para cada tarefa: lê, analisa, coleta contexto, consulta IA, preenche, salva
   - Se erro, registra e continua

## Integrações
- **Planilhas**: arquivo ficha técnica (aba "Ficha Técnica Padrão"), arquivo _STATUS_PMIB.xlsx (opcional, para enriquecimento de contexto)
- **IA**: sempre via `sigft/core/llm/` (`LLMClient` + provider). O módulo **não conhece SDK de provedor** — modelo/provedor vêm de `config.LLM_TASKS["autospec"]`, e cada chamada é registrada pelo `UsageTracker` em `logs/llm_usage.jsonl` (CP 3.4)
- **APIs externas diretas**: Google Custom Search (`WebSearcher`), LlamaParse (parsing de PDF)
- **Frontend**: chamado via `process_queue()` com callbacks de UI para logs
- **Documentos**: PDFs/HTMLs locais referenciados em fila, baixados da web dinamicamente

## Pontos de atenção

> ### 🔴 Duas pendências REAIS e ainda abertas (confirmadas no código em 2026-08-11)
>
> As duas foram registradas em `PENDENCIAS.md`, endereçadas a um checkpoint que **fechou sem
> resolvê-las**. Quem for evoluir o AutoSpecAI encosta nelas — são os primeiros candidatos a
> trabalho no módulo:
>
> **1. `fill_save` — checkbox depende da IA devolver uma referência de célula.**
> Em `sigft/services/autospec.py:369-372`:
> ```python
> clean = str(val).strip().upper()
> ...
> ws[clean].value = "X"
> ```
> `val` é a **resposta da IA**. O código a usa direto como endereço de célula, então só
> funciona se o modelo devolver literalmente `"G25"`. Qualquer outra coisa (`"Sim"`,
> `"Vertical"`, `"g25 "`) vira um endereço inválido. Registrada no bootstrap com destino
> "Fase 3"; a Fase 3 fechou e ela continua lá. **Precisa de validação contra execução real**
> antes de qualquer conserto — não dá para adivinhar o que o modelo devolve hoje.
>
> **2. ~~`__init__` exigia chave do Gemini num mundo multi-provedor.~~ ✅ CORRIGIDO em
> 2026-08-11.** Ver "Guard de chave" abaixo.

### Guard de chave (corrigido em 2026-08-11)

`__init__` falha cedo quando a IA não tem como rodar — mas agora cobra a chave **do provedor
que vai de fato ser usado**, não a do Gemini sempre:

| Provedor resolvido | O que é exigido |
|---|---|
| `gemini` | o argumento `gemini_key`. Mensagem inalterada: `"Chave Gemini é obrigatória."` |
| `openrouter` / `openai_compat` | a chave correspondente em `config.CHAVE_POR_PROVIDER`, lida de `config.carregar_chaves()`. A mensagem nomeia o provedor e a chave que falta |
| qualquer outro (ex.: `xai`) | nada — deixa `get_llm` levantar o `NotImplementedError` dele, que lista os provedores suportados |

A cadeia de resolução é a mesma de `get_llm` (seleção por tarefa → seleção global →
`config.LLM_MODELOS_HOJE["autospec"]`), e é executada **uma única vez**: o resultado vai para
o guard e é repassado ao `get_llm` como `selecao_resolvida`. Resolver duas vezes abriria uma
janela para o guard validar a chave de um provedor e o cliente sair com outro, se a seleção
mudasse no disco no meio. Coberto por `tests/test_autospec_guard_chave.py` (15 testes).

- Chaves de API devem ser passadas exclusivamente via `__init__`, não hardcoded (linha 22-23 menciona remoção)
- WebSearcher ignora silenciosamente erros de rede (linha 103-104, except genérico)
- PDFProcessor cascata de fallback sem logging — se LlamaParse falha, tenta PyPDF2 silenciosamente (linha 134-135)
- Regex para extração de código PMIB assume formato `\d{10}.\d{4}` (linha 180); nomes fora disso retornam None
- BeautifulSoup remove tags script, style, nav, footer, header — pode perder informações estruturais (linha 151)
- Limite de contexto é fixo: 60k local, 50k por doc web, 50k total — textos maiores são truncados
- Google Custom Search API tem limite de 100 queries/dia free tier; sem API key retorna array vazio (linha 77-78)
- Prompt para Gemini é em português; temperatura 0.1 (baixa criatividade) — mudanças podem afetar qualidade
- Sufixo `_completed` é fixo; se arquivo original já termina com `_completed`, cria duplicata (linha 370)
- Função `is_empty()` considera qualquer célula com "FORNECER" como vazia (linha 221), mesmo que parcialmente preenchida
