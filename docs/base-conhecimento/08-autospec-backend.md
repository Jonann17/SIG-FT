# AutoSpec Backend (`autospec_backend.py`)

## Propósito
Automatiza o preenchimento de fichas técnicas padrão via RAG (Retrieval-Augmented Generation) com o Gemini. O módulo analisa campos vazios na ficha, recupera contexto de documentos locais e web, consulta o Gemini 3.1 Pro Preview para gerar respostas técnicas inteligentes e preenche a planilha com fonte azul e sufixo `_completed`.

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

### `GENERATIVE_FIELDS` (constante, linha 25-29)
Lista de campos que podem ser gerados por IA com base em boas práticas quando não há dados explícitos. Inclui: empilhamento, embalagem_transporte, transporte, preservacao, metodo_limpeza, ferramentas_para_preservacao, tipo_legislacao, tipo_descarte, protecao, posicao_armazenamento, unidade, tipo.

### `CONFIG_MAP` (constante, linha 31-57)
Dicionário de configuração por campo. Cada entrada contém:
- `range` ou `cells`: localização na planilha (ex: H6, ou lista [F10, F12])
- `type`: "cell" (texto) ou "checkbox" (múltiplas opções)
- `validation`: "simple" (texto/número) ou "ai" (requer IA)
- `weight`: importância relativa (1-7)
- `desc`: descrição do campo (cm, kg, opcções, etc.)

Exemplos: `texto_breve_material` em H6, `embalagem_transporte` em M42 (tipo "ai"), `posicao_armazenamento` em G25/G27/G29 (checkboxes).

### `WebSearcher` (linha 69-116)
Realiza buscas na web via Google Custom Search API.
- `__init__(api_key, cse_id)`: inicializa com credenciais
- `search_and_download(query, required_terms=[], max_results=3)`: busca com termos obrigatórios, retorna lista de dicts `{path, url, title}` com PDFs/HTMLs baixados em temp
- `_download_file(url)`: baixa arquivo com timeout de 15s, detecta .pdf ou .html, retorna caminho temp

### `PDFProcessor` (linha 119-156)
Extrai texto de documentos com fallback em cascata.
- `__init__(llama_key)`: configura LlamaParse se chave fornecida
- `extract_text(filepath)`: tenta LlamaParse → PyPDF2 → BeautifulSoup (HTML), retorna tupla `(texto, metodo_usado)`

### `AutoSpecCore` (linha 162-415)
Orquestra o pipeline RAG completo.
- `__init__(gemini_key, llama_key, google_search_key, google_cse_id)`: valida Gemini (obrigatório), instancia LLM, WebSearcher, PDFProcessor
- `extract_pmib_code(input_filepath)`: regex sobre nome arquivo, busca padrão `\d{10}\.(\d{4})`, retorna sufixo de 4 dígitos
- `find_header_columns(pmib_sheet)`: varredura linha 1-10 procurando por "CÓDIGO PMIB", "DESCRIÇÃO", "CÓDIGO MATERIAL", retorna tupla `(pmib_col_idx, desc_col_idx, mat_col_idx, start_row)`
- `get_pmib_data(pmib_path, code_suffix)`: lê planilha _STATUS_PMIB, procura código com sufixo, retorna tupla `(descrição_completa, código_material)` ou `("", "")`
- `is_empty(val)`: verifica se célula está vazia ou contém "FORNECER"
- `analyze_sheet(filepath, status_pmib_path)`: lê ficha, detecta campos vazios (estáticos via CONFIG_MAP e dinâmicos na linha 79+), retorna tupla `(workbook, missing_dict, txt_breve, fabricante, desc_comp, cod_mat)` onde `missing_dict` mapeia campo → `{type, desc, ref}`
- `retrieve_context(txt_brv, fab, cod_mat, refs_locais)`: pipeline RAG de 2 etapas: processa documentos locais via PDFProcessor, depois busca web com 2 queries (por código material + por descrição breve), limita resultado a 50k caracteres por doc, retorna tupla `(contexto_completo, lista_urls)`
- `process_local_documents(paths)`: aplica PDFProcessor a cada caminho, limita a 60k chars/doc
- `generate_ai_response(txt_brv, fab, desc_comp, missing, context)`: monta prompt JSON com nome/descrição/fabricante/contexto e instruções (prioriza LOCAL DOC, gera padrão para GENERATIVE_FIELDS, deixa vazio para ESTRITO, checkboxes deduzem melhor opção), invoca `gemini-3.1-pro-preview` via LangChain JsonOutputParser, retorna dict `{field_id: resposta}`
- `fill_save(wb, filepath, ai_data, missing)`: preenche células com fonte azul (0000FF), para checkboxes marca célula com "X", salva com sufixo `_completed`, retorna novo caminho
- `process_queue(queue, status_pmib_path)`: generator que yields logs para UI, processa lista de tarefas `{sheet: path, refs: [paths]}` em sequência (1 a N), chamando analyze_sheet → retrieve_context → generate_ai_response → fill_save

## Fluxo detalhado

1. **Análise da Ficha** (analyze_sheet)
   - Abre workbook, valida aba "Ficha Técnica Padrão"
   - Extrai código PMIB do nome arquivo (último 4 dígitos)
   - Se status_pmib_path fornecido, busca descrição completa e código material nele
   - Verifica células fixas em CONFIG_MAP: se vazia, adiciona a `missing`
   - Verifica checkboxes: se todas vazias, adiciona a `missing`
   - Itera linhas 79+ procurando perguntas na coluna D (idx 3), respostas na coluna M (idx 13)

2. **Recuperação de Contexto** (retrieve_context)
   - Processa documentos locais: PDFProcessor extrai texto (max 60k chars cada)
   - Busca web: se Google API disponível, monta 2 queries ordenadas por especificidade (código material primeiro, depois descrição breve)
   - Filtra resultados por required_terms (fabricante, código material)
   - Baixa e processa PDFs/HTMLs encontrados (max 50k chars cada)
   - Concatena local + web, retorna tupla (contexto_total, lista_urls)

3. **Geração IA** (generate_ai_response)
   - Monta prompt com: dados (nome, descrição, fabricante), contexto, instruções
   - Para cada campo faltante, adiciona linha com ID, descrição, tipo (INFO TÉCNICA PADRÃO vs ESTRITO)
   - Envia via LangChain → Gemini 3.1 Pro Preview com JsonOutputParser
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
- **APIs**: Gemini 3.1 Pro Preview (LangChain), Google Custom Search, LlamaParse (PDF parsing)
- **Frontend**: chamado via `process_queue()` com callbacks de UI para logs
- **Documentos**: PDFs/HTMLs locais referenciados em fila, baixados da web dinamicamente

## Pontos de atenção
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
