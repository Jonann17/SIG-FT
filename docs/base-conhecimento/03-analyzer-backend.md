# Analyzer Backend (`analyzer_backend.py`)

## Propósito
Módulo de análise inteligente de fichas técnicas que valida campos fixos, variáveis técnicas e normaliza pontuação (0–100%) via Gemini. Classifica fichas em `FT_good` (acima do threshold) ou `FT_bad` (marcadas com erros em vermelho/RichText).

## Entradas e Saídas
- **Entradas**:
  - Arquivo Excel com aba desconhecida (detecta automaticamente), células fixas conforme CONFIG_MAP (H6, F10, S6, S25, E31, M42–V58, M63–V66, etc.)
  - Aba opcional PMIB com descrição de material
  - Variáveis técnicas a partir da linha 79 (colunas C–L: pergunta, M–V: resposta)
  
- **Saídas**:
  - Arquivo original copiado se `final_score >= threshold`
  - Arquivo marcado com "FORNECER" em vermelho (RichText) em células vazias ou inválidas se score < threshold
  - Arquivo salvo em pasta `{root}/{FT_good|FT_bad}/{subfolder}/{nome}_{percentual}%.xlsx`
  - Log de validação por callback

## Classes e Funções

### Configuração
- **`CONFIG_MAP`** (linha 23–49): Mapa de células fixas com validação simples/IA, pesos (1–7), type (cell/checkbox), error_target para marcação de erro
- **`VARIAVEIS_SPECS`** (linha 51–55): start_row=79, pergunta_range="C:L", resposta_range="M:V"
- **`FORBIDDEN_NA_STRINGS`** (linha 15): lista de N/A que marcam campos como vazios

### DatasheetAnalyzer
- **`__init__(api_key)`** → configura Gemini com transport='rest' (redes corporativas), min_seconds_between_calls=60
- **`processar_planilha(input_filepath, root_output_dir, subfolder_name, original_filename, pmib_sheet, score_threshold, custom_weights, max_variable_points=45.0, callback_manual_desc)`** → Generator que yield logs e retorna True/False. Pipeline: carregar → validação simples → validação IA → normalizar → salvar

### Métodos de Marcação (Excel)
- **`get_cell_from_range(ws, range_str)`** → primeira célula do range (ex: "H6:P6" → H6)
- **`set_blank_error(cell)`** → escreve "FORNECER" em vermelho (Font color "FF0000" bold)
- **`set_invalid_error(cell, old_value)`** → CellRichText: "FORNECER (" + valor_tachado + ")" em vermelho

### Métodos de Busca
- **`extract_pmib_code(filename)`** → regex `\d{10}\.(\d{4})` extrai últimos 4 dígitos do PMIB
- **`_find_header_columns(ws)`** → busca colunas "CÓDIGO PMIB" e "DESCRIÇÃO" (até linha 10)
- **`_find_pmib_description(code_4, ws)`** → busca descrição material no worksheet PMIB
- **`_find_variable_specs_start_row(ws)`** → busca "ESPECIFICAÇÕES TÉCNICAS..." (default 79)

### Métodos IA
- **`_build_gemini_prompt(context, fixed, variable)`** → constrói prompt com regras de validação (Relevância, Aplicabilidade, Fornecimento de Info, Regra de Ouro). Context: texto_breve_material + fabricante
- **`_call_gemini_api(prompt)`** → chama Gemini 3.1 Pro Preview, retry 3x com sleep(5) entre tentativas, retorna JSON parsed ou None

## Fluxo Detalhado

1. **Carregamento** (linha 122–139):
   - Abre arquivo com openpyxl
   - Extrai código PMIB de filename via regex `\d{10}\.(\d{4})`
   - Se pmib_sheet fornecido: busca descrição complementar
   - Se não encontrado: chama callback_manual_desc para input manual

2. **Validação Simples** (linha 147–210):
   - Itera CONFIG_MAP
   - Para cada campo:
     - **type="cell"**: lê célula, valida se não em FORBIDDEN_NA_STRINGS, marca com set_blank_error se vazio
     - **type="checkbox"**: verifica se alguma das células em config["cells"] tem valor não-None
   - Acumula `total_possible_fixed` (soma dos pesos configurados)
   - Soma `total_score_earned` se passou validação

3. **Mapeamento Dinâmico de Variáveis** (linha 217–255):
   - Detecta linha de início (padrão 79)
   - Conta total de variáveis (enquanto coluna C tem valor)
   - Calcula pontos por variável: `max_variable_points / total_vars`
   - Lê cada pergunta (coluna C) e resposta (coluna M)
   - Marca vazias com set_blank_error

4. **Validação Semântica (IA)** (linha 259–264):
   - Se há campos fixos para IA OU variáveis: constrói prompt
   - Chama `_call_gemini_api` com rate-limit de 60s (sleep se chamada anterior foi recente)
   - Gemini retorna JSON: `{campos_fixos: {key: {status: "VALIDO"|"INVALIDO"}}, campos_variaveis: [{status: ...}]}`

5. **Aplicação de Retorno IA** (linha 270–287):
   - Para cada campo_fixo com status="INVALIDO": chama set_invalid_error
   - Para cada variável com status="INVALIDO": chama set_invalid_error

6. **Somatória de Pontos** (linha 290–304):
   - Simples + IA: se passou, soma weight
   - Normaliza: `final_percentage = (total_score_earned / grand_total_possible) * 100`
   - `grand_total_possible = total_possible_fixed + max_variable_points`
   - `final_score = int(round(final_percentage, 0))`

7. **Decisão e Salvamento** (linha 308–330):
   - Folder: "FT_good" se score >= threshold, senão "FT_bad"
   - Nome saída: `{original}_{final_score}%.xlsx`
   - Se score >= threshold: copia original intacto
   - Se score < threshold: salva workbook marcado com erros em vermelho/RichText

## Integrações

- **Frontend**: Classe `ModuloAnalyzer` (frontend.py:1619) instancia `DatasheetAnalyzer`, executa pipeline em thread, oferece botão "Configurar Pesos" que lê CONFIG_MAP e permite override por campo
- **Planilhas**:
  - Lê: Células fixas (CONFIG_MAP), variáveis (linha 79+), PMIB (descrição de material)
  - Escreve: Arquivo marcado OU original copiado, reorganizado em pasta FT_good/FT_bad

- **API Gemini**: `gemini-3.1-pro-preview` com system message em português, validação via regras semânticas

## Pontos de Atenção

- **Rate-limit 60s hardcoded** (linha 65, 444): entre chamadas Gemini. Se múltiplos arquivos processados em sequência, cada um aguarda 60s. Sem configuração externa.
- **Skiprows=6 implícito em pdm_backend**: Se PDM foi processado com skip incorreto, colunas de entrada podem estar desalinhadas.
- **Colunas fixas CONFIG_MAP hardcoded**: H6, F10, L10, S6, P17, M42–V58, etc. Se template foi customizado (coluna inserida), endereços quebram.
- **Retry 3x Gemini** (linha 449): loop silencioso, sem logging detalhado. Se API fora por >15s (3*5), falha sem avisar usuário.
- **Transport='rest'** (linha 69): para redes corporativas com proxy. Pode não funcionar em redes abertas se proxy retornar 407.
- **Normalização 0–100% recente**: Antes somava pontos absolutos. Agora divide por `grand_total_possible`. Se custom_weights mudar total, scores de arquivos antigos não são comparáveis.
- **Callback manual_desc opcional**: Se não fornecido e PMIB não encontrado, descrição complementar = None. Prompt Gemini recebe material sem context.
- **Linha 79 hardcoded** (linha 376): busca por "ESPECIFICAÇÕES TÉCNICAS" como fallback. Se cabeçalho foi traduzido ou editado, volta para linha 79 fixa.
- **JSON parsing strict** (linha 454): se Gemini retorna JSON inválido (com ```json, espaços), tenta strip de backticks. Se JSON está genuinamente quebrado, retorna None e valida como "tudo válido" (linha 267–268).

---

## Auditoria de 2026-08-26 — 7 defeitos medidos e corrigidos

> Frente do Rafael. Cada item foi **medido** com um `.xlsx` construído e lido (openpyxl real),
> nunca deduzido da leitura do código. Testes em `tests/test_analyzer_planilha.py`.

**Correção deste documento antes de tudo:** onde acima se lê *"Arquivo Excel com aba
desconhecida (detecta automaticamente)"*, o código fazia `wb.active`, que **não detecta nada** —
é a aba que estava selecionada quando o arquivo foi salvo. O doc descrevia a intenção, não o
comportamento. Hoje detecta de verdade (item 1).

| # | O que estava errado | O que foi medido | Como ficou |
|---|---|---|---|
| 1 | `ws = wb.active` na ficha | a MESMA ficha valia **100% ou 0%** conforme a aba salva como ativa | `_aba_da_ficha` escolhe pela evidência (âncoras do `CONFIG_MAP` preenchidas); empate ou nenhum sinal → `wb.active` |
| 2 | `pmib_sheet = wb.active` (frontend) | com uma capa como aba ativa, **nenhuma** ficha do lote achava descrição | `aba_do_status_pmib` procura a aba que tem os cabeçalhos |
| 3 | `if not p_val: break` nas specs | 5 perguntas em 6 linhas viravam **2**, e os pontos por spec **inflavam** (22,50 contra 9,00) | `_ler_specs`, uma passada só, tolerando buraco até `MAX_LINHAS_VAZIAS_SEGUIDAS` |
| 4 | código PMIB comparado como texto cru | `4500063671.1050` volta do Excel como `4500063671.105` e a busca **nunca** casava | delega a `pmib_codes.normalize_pmib` (implementação única do CP 1.2) |
| 5 | `if not c_desc.value: break` no `_STATUS_PMIB` | uma linha vazia escondia **todo** o resto da planilha | mesma tolerância do item 3 |
| 6 | `nome.replace(".xlsx", ...)` | `ficha.xlsx.revisao.xlsx` → `ficha_100%.xlsx.revisao_100%.xlsx` | `nome_com_a_nota`, só a extensão final |
| 7 | `if not ai_res:` | alarme de "nota INFLADA" disparava na ficha que **não tinha nada** para a IA validar | só dispara se a IA foi mesmo consultada, e diz o motivo (`ultimo_erro_ia`) |

**No `frontend.py` (`ModuloAnalyzer._run_backend`)**, ainda:

- Uma exceção numa ficha derrubava o **lote inteiro**; as seguintes nem eram tentadas.
- O `return True/False` do backend era descartado. Num generator ele vai para
  `StopIteration.value` e **nunca é "yieldado"** — então o `if not isinstance(log_msg, bool)`
  que estava ali filtrava um bool que nunca chegava, e a tela dizia *"Análise finalizada"*
  mesmo com todas as fichas falhando. Agora conta e nomeia as que não concluíram.

### As 4 decisões do usuário, tomadas em 2026-08-26

Estavam em aberto porque mudavam comportamento de produto, não porque eram difíceis. O
usuário decidiu as quatro no mesmo dia:

| Decisão | O que passou a acontecer |
|---|---|
| **Fórmula na célula → corrigir** | O arquivo é aberto DUAS vezes: um workbook gravável (guarda a fórmula, recebe o `FORNECER`, vai para o disco) e um `data_only=True` com os valores calculados. `=1+1` não conta mais como texto |
| **Teto de 55% → renormalizar** | Sem especificações técnicas, os 45 pontos delas saem do denominador: a nota é calculada só sobre os campos fixos, com aviso no console. Uma ficha sem specs mas completa no resto chega a 100% |
| **`callback_manual_desc` → implementar** | `ModuloAnalyzer._perguntar_descricao` abre a caixa de diálogo quando o PMIB não está na planilha. **CANCELAR para de perguntar no resto do lote** — 50 fichas desconhecidas não podem virar 50 diálogos obrigatórios |
| **IA fora do ar → abortar a ficha** | Nada é salvo. Sem o julgamento da IA os campos dela contariam como válidos e a nota sairia inflada; um arquivo com nota que não vale é pior que arquivo nenhum. A ficha entra na lista de "não concluídas", com o motivo |

**A armadilha da leitura dupla, e como ela está travada por teste:** se o `FORNECER` for
escrito no workbook `data_only`, o arquivo salvo sai **sem marcação nenhuma** e o módulo perde
o sentido. `test_a_marcacao_FORNECER_vai_no_workbook_QUE_SERA_SALVO` existe só para isso.

**O caso que não dá para resolver sozinho:** `data_only=True` devolve o valor em CACHE, e ficha
nunca aberta no Excel não tem cache — a fórmula existe e o valor é `None`. Tratar como célula
vazia escreveria `FORNECER` por cima de uma fórmula do usuário, o que é pior que o problema
original. Nesse caso o comportamento antigo é mantido (o texto cru) e o console avisa,
**nomeando as células**: *"1 celula(s) com FORMULA sem valor calculado (L10). Abra a ficha no
Excel e salve"*.

### Ainda em aberto

| Achado | Destino |
|---|---|
| `AutoSpecCore.MAX_LINHAS_VAZIAS_SEGUIDAS` e `ficha_layout.MAX_LINHAS_VAZIAS_SEGUIDAS` são o mesmo 25 em dois lugares (o analyzer já usa o do `ficha_layout`; o autospec ainda não) | CP 8.1 |
| `_call_gemini_api` grava o erro em `ultimo_erro_ia` **e** ainda faz `print("API Error")`, porque um teste do CP 3.1 trava o print como caracterização | CP 8.1 |
