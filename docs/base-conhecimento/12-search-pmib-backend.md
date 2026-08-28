# Search PMIB Backend (`search_pmib_backend.py`)

> ⚠️ **Onde o código mora hoje** (atualizado em 2026-08-28)
>
> Este documento foi escrito antes da refatoração e descreve o comportamento do
> módulo, que continua valendo. Mas os CAMINHOS mudaram:
>
> | O que o texto abaixo chama de | Está hoje em |
> |---|---|
> | `search_pmib_backend.py` | `sigft/services/search.py` (serviço) · `sigft/app/views/busca_pmib.py` (tela) |
>
> ⚠️ Atenção aos nomes: o serviço é `search.py` e a tela é `busca_pmib.py` — nenhum dos dois repete o nome antigo.
>
> A lógica de negócio descrita aqui continua válida; o que mudou foi onde ela vive. Camadas novas que este texto não menciona: `sigft/core/excel/` (cabeçalho de planilha, código PMIB, gravação com retry), `sigft/core/llm/` (cliente de IA multi-provedor), `sigft/core/rpa/` (portal e motor), `sigft/core/callbacks.py` (o protocolo UI↔serviço).

## Propósito
Fornece dois modos de busca em arquivos `*_STATUS_PMIB*`: busca direcionada (coluna específica) e busca generalista (normalização agressiva removendo acentos/pontuação, concatenando linha inteira). Varre recursivamente os.walk por arquivos Excel, detecta dinamicamente cabeçalho pela palavra-chave "DESCRIÇÃO", e retorna correspondências com metadados (código Itaipu, arquivo, pasta, coluna match, amostra).

## Entradas e Saídas
- **Entradas**: 
  - Pasta raiz (varredura recursiva)
  - Tipo de busca: 'direcionada' ou 'generalista'
  - Termo de busca (string)
  - Coluna específica (opcional, para direcionada)
  - Callback: `callback_log` (logging de progresso)
- **Saídas**: 
  - Lista de resultados: dicts com código_itaipu, arquivo_nome, caminho_arquivo, caminho_pasta, coluna_match, amostra
  - Logs via callback

## Classes e Funções

### `PMIBSearcher` (linha 8)
Gerenciador de busca em arquivos PMIB.

- `__init__()`: inicializa lista de nomes de aba: ["Lista de Materiais", "LISTA DE MATERIAIS", "Lista de materiais"]
- `_limpar_texto_parrudo(texto)`: normalização agressiva para busca generalista (linha 13-23)
  - Converte para uppercase
  - Remove acentos via unicodedata.normalize('NFD') + ascii encode
  - Remove tudo que não for A-Z ou 0-9 (espaços, hífens, pontuação, etc.)
  - Retorna string "amassada" (ex: "Código-ABC-123" → "CODIGOABC123")
  - Se NaN, retorna ""
- `_extrair_codigo_itaipu(filename)`: extrai prefixo do nome arquivo antes de "_STATUS_PMIB" (linha 25-33)
  - Converte nome para uppercase
  - Split por "_STATUS_PMIB"
  - Retorna primeira parte (strip) ou "DESCONHECIDO" se não encontra padrão
  - Ex: "4500063671.1234_STATUS_PMIB.xlsx" → "4500063671.1234"
- `_encontrar_e_formatar_dataframe(filepath)`: lê arquivo, detecta dinamicamente cabeçalho por "DESCRIÇÃO", retorna DataFrame formatado (linha 35-82)
  - Tenta carregar cada aba em sheet_names (por ordem)
  - Lê primeiras 15 linhas sem header (dtype=str) para procurar "DESCRIÇÃO"
  - Itera linhas, concatena todas as colunas em string, procura "DESCRIÇÃO" ou "DESCRICAO" (line 64-67)
  - Se encontra, salva header_idx
  - Se não encontra na linha 0-9, retorna erro
  - Recarrega arquivo completo com header_idx como header
  - Limpa nomes de coluna: strip, replace \n por espaço, converte para string (linha 79)
  - Retorna tupla `(df_final, "OK")` ou `(None, msg_erro)`
- `executar_busca(pasta_raiz, tipo_busca, termo_busca, coluna_especifica, callback_log)`: varre pasta e executa busca, retorna lista de resultados (linha 84-190)

## Fluxo detalhado

### Inicialização
- Normaliza termo_busca para uppercase (linha 90)
- Callback log: "Iniciando mapeamento de diretórios..."

### Varredura Fase 1: Localizar Arquivos (linha 94-103)
- os.walk recursivo em pasta_raiz
- Procura arquivos com "STATUS_PMIB" no nome (case-insensitive)
- Exclui arquivos temporários (~$*)
- Filtra extensões: .xlsx, .xls, .xlsm
- Coleta lista completa de caminhos
- Se nenhum encontrado, retorna lista vazia com log

### Varredura Fase 2: Processar Cada Arquivo (linha 107-183)
- Para cada arquivo (índice i de total):
  - Extrai nome arquivo e diretório
  - Chama `_extrair_codigo_itaipu(nome_arquivo)`
  - Callback log: "[i/total] Analisando: {nome}..."
  - Chama `_encontrar_e_formatar_dataframe(caminho_completo)`
  - Se erro (df=None), callback log com status_msg e continua
  - Inicializa match_encontrado = False

### Lógica de Busca — Tipo DIRECIONADA (linha 125-146)
- Requer coluna_especifica (ex: "DESCRIÇÃO")
- Procura coluna real em df.columns: nome contém coluna_especifica (uppercase)
- Se coluna não existe, callback log "Coluna não existe" e continua
- Se existe:
  - Cria máscara: coluna.fillna('').astype(str).str.upper().str.contains(termo_busca, regex=False)
  - Filtra linhas que match
  - Se não vazio:
    - match_encontrado = True
    - Extrai 3 primeiras amostras (linhas do match)
    - Concatena com " | "
    - Adiciona resultado dict: {codigo_itaipu, arquivo_nome, caminho_arquivo, caminho_pasta, coluna_match: col_real, amostra}

### Lógica de Busca — Tipo GENERALISTA (linha 148-180)
- Normaliza termo_busca via `_limpar_texto_parrudo()` → termo_normalizado
- Se termo_normalizado vazio, salta (linha 154)
- Para cada linha do DataFrame:
  - Concatena todas as colunas em string (df.fillna('').astype(str).agg(' '.join, axis=1))
  - Normaliza linha (uppercase → remove acentos via Pandas native → remove não-alpanuméricos com regex)
  - Busca termo_normalizado (exato, sem regex)
  - Se match:
    - match_encontrado = True
    - Adiciona resultado dict: {codigo_itaipu, arquivo_nome, caminho_arquivo, caminho_pasta, coluna_match: "Múltiplas (Busca Super Geral)", amostra: "{N} linha(s) encontrada(s)"}
    - **Break** após primeiro match (linha 180 implícita) — não busca mais no arquivo

### Pós-Processamento de Cada Arquivo (linha 182-183)
- Se match_encontrado, callback log: "✅ Match Encontrado no PMIB {codigo}!"

### Finalização (linha 189-190)
- Callback log: "Busca finalizada! {N} correspondência(s) encontrada(s)."
- Retorna lista completa de resultados

## Integrações
- **Arquivos**: lê recursivamente `*_STATUS_PMIB*.xlsx/.xls/.xlsm` de pasta_raiz
- **Frontend**: callback_log para progresso em tempo real
- **Saída**: lista de dicts com metadados (caminho absoluto, relativo, código Itaipu, amostras)

## Pontos de atenção
- Nomes de aba hardcoded em `__init__` (linha 11) — se aba tiver nome diferente, não encontra cabeçalho (ex: "LISTA DE MATERIAIS" vs "Lista de Materiais")
- Cabeçalho procurado nas linhas 0-9; se verdadeiro header após linha 9, arquivo ignorado (linha 62-70)
- Detecção de cabeçalho procura por "DESCRIÇÃO" ou "DESCRICAO" (diacríticos normalizados) — se coluna tem nome totalmente diferente, falha (linha 65)
- dtype=str em read_excel previne conversão automática, mas torna todas as colunas string; comparações case-insensitive requerem .upper() (linha 76)
- Busca direcionada: procura primeiro coluna cujo nome contém termo_especifico; se múltiplas colunas match, usa primeira (next()) (linha 126)
- Busca generalista: normalização via `_limpar_texto_parrudo()` remove TUDO que não for A-Z/0-9 — buscas por "CEP-12.345" devem ser digitadas como "CEP12345" (linha 152)
- Busca generalista usa `.str.normalize()` do Pandas que pode ser mais lenta que apply lambda em dataframes grandes (linha 159-165)
- Busca direcionada retorna até 3 amostras; busca generalista retorna contagem (não amostras individuais) (linha 134-135 vs 179)
- Nenhuma validação se pasta_raiz existe; os.walk em pasta inexistente retorna lista vazia (sem erro) (linha 95)
- Callback_log é genérico; se callback não implementa robustamente, logs podem ser perdidos (linha 92, 105, 113, etc.)
- Arquivo Excel aberto (lock) durante leitura levanta exceção genérica — não tratada especificamente (linha 59, 81)
- Match em busca direcionada é case-insensitive (str.upper()), mas em generalista usa normalização agressiva — comportamentos diferentes (linha 129 vs 152)
- Amostra em generalista é apenas contagem, não textos reais — usuário não sabe o que foi encontrado (linha 179)
- Tratamento de erro em try-except genérico (linha 124-186) engole detalhes; traceback.print_exc() vai apenas ao console (linha 187)
