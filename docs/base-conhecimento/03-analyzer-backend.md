# Analyzer Backend (`analyzer_backend.py`)

> ⚠️ **Onde o código mora hoje** (atualizado em 2026-08-28)
>
> Este documento foi escrito antes da refatoração e descreve o comportamento do
> módulo, que continua valendo. Mas os CAMINHOS mudaram:
>
> | O que o texto abaixo chama de | Está hoje em |
> |---|---|
> | `analyzer_backend.py` | `sigft/services/analyzer.py` (serviço) · `sigft/app/views/analyzer.py` (tela) |
> | relatório de pendências | `sigft/services/analyzer_relatorio.py` |
>
> A lógica de negócio descrita aqui continua válida; o que mudou foi onde ela vive. Camadas novas que este texto não menciona: `sigft/core/excel/` (cabeçalho de planilha, código PMIB, gravação com retry), `sigft/core/llm/` (cliente de IA multi-provedor), `sigft/core/rpa/` (portal e motor), `sigft/core/callbacks.py` (o protocolo UI↔serviço).

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

### 2026-08-26 — as decisões do usuário, e a regra de negócio que corrigiu uma delas

| Decisão | O que passou a acontecer |
|---|---|
| **Fórmula na célula → corrigir** | O arquivo é aberto DUAS vezes: um workbook gravável (guarda a fórmula, recebe o `FORNECER`, vai para o disco) e um `data_only=True` com os valores calculados |
| **`callback_manual_desc` → implementar** | `ModuloAnalyzer._perguntar_descricao` abre a caixa quando o PMIB não está na planilha. **CANCELAR para de perguntar no resto do lote** |
| **IA fora do ar → não gera nota** | A ficha vai para `FT_nao_concluidas/`, com o motivo no console |
| **Ficha sem especificações técnicas → não gera nota** | *(esta substituiu a renormalização decidida horas antes)* A seção é obrigatória; sem ela a ficha não é analisável e volta ao fornecedor. Mesma pasta do caso acima |

**A decisão que foi revertida, e por quê.** Por algumas horas o analyzer renormalizava a nota
quando a ficha não tinha especificações técnicas — 55 pontos fixos viravam 100%. A regra de
negócio mostrou que o caso era outro: *"a ficha técnica não ter os campos de características
técnicas é um problema, já que este deve existir"*. Não era pontuar o que existe; era **recusar
a ficha**. A renormalização foi removida junto com os testes que a descreviam.

### Três destinos, e a diferença entre eles

| Pasta | Quando | O que vai para lá |
|---|---|---|
| `FT_good/` | nota ≥ limiar **e** nenhum obrigatório faltando | o original, com a nota no nome |
| `FT_bad/` | analisada e reprovada | o arquivo **marcado** — é o que se manda ao fornecedor |
| `FT_nao_concluidas/` | o aplicativo **não conseguiu** analisar | o **original**, sem marcação e **sem porcentagem** no nome |

A distinção que importa: `FT_bad` é "analisei e está errado"; `FT_nao_concluidas` é "não deu
para analisar". Nota que não existe não pode aparecer no nome de um arquivo.

### Campos obrigatórios (lista do usuário, 2026-08-26)

24 das 26 entradas do `CONFIG_MAP` têm `"obrigatorio": True`. **Faltar um deles reprova a
ficha, qualquer que seja a nota** — uma ficha com 98% e sem fabricante vai para `FT_bad`, e o
console nomeia os campos que faltaram, um por linha.

Fora da lista: `peso_bruto` e `empilhamento`. Continuam valendo peso — faltar um deles baixa a
nota, não reprova.

**Entrada nova:** `controle_temp_umidade` (M23). A célula não foi chutada —
`services/upload_conditions.py:132` já lia esse endereço.

**"Não aplicável" passou a ser aceito** em `transporte` (içagem), `metodo_limpeza` e
`ferramentas_para_preservacao`. Isso conserta uma contradição do próprio código: a **regra 2 do
prompt** já dizia que "Não aplicável" pode ser VÁLIDO quando a pergunta não se aplica — e
`FORBIDDEN_NA_STRINGS` matava a resposta no analyzer, antes de a IA vê-la.

### Relatório para o fornecedor

Botão *GERAR RELATÓRIO PARA O FORNECEDOR (.xlsx)* na tela, habilitado quando o lote termina.
Uma linha por material: **código PMIB completo**, o que precisa ser corrigido, e a nota.

```
PMIB              | NOTA | O QUE PRECISA SER CORRIGIDO
4500063671.0002   | 98%  | • Fabricante (obrigatório): em branco, precisa ser preenchido.
                  |      | • Peso líquido (kg) (obrigatório): em branco, precisa ser preenchido.
4500063671.0005   | 78%  | • Embalagem para transporte (indicar o TIPO...): Nao diz qual e a
                  |      |   embalagem: informe o tipo (caixa de madeira, engradado...).
                  |      | • Pergunta 2?: Foi informada uma dimensao onde se pedia o material.
```

Duas decisões que atravessam o módulo `analyzer_relatorio.py`, porque **quem lê não é
engenheiro do SIG-FT**:

1. **Rótulo, nunca a chave interna.** `peso_liquido` não diz nada a quem preencheu a ficha.
   Um teste garante que todo campo do `CONFIG_MAP` tem rótulo — campo novo sem rótulo reprova.
2. **A justificativa da IA é repassada literalmente.** O prompt manda escrevê-la *para o
   fornecedor*; reescrevê-la aqui só a afastaria de quem vai lê-la. Resposta sem `motivo`
   (modelo mais fraco, ou cache do formato antigo) ainda diz qual campo falhou.

### Ainda em aberto

| Achado | Destino |
|---|---|
| `AutoSpecCore.MAX_LINHAS_VAZIAS_SEGUIDAS` e `ficha_layout.MAX_LINHAS_VAZIAS_SEGUIDAS` são o mesmo 25 em dois lugares | CP 8.1 |
| `_call_gemini_api` grava o erro em `ultimo_erro_ia` **e** ainda faz `print("API Error")`, porque um teste do CP 3.1 trava o print | CP 8.1 |
