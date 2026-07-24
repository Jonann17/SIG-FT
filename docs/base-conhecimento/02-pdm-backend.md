# PDM Backend (`pdm_backend.py`)

## Propósito
Módulo de funções soltas que gerencia o ciclo de vida de Planilhas de Dados de Materiais (PDM): extração de dados de arquivos Excel, fatia de listas gerais em arquivos individuais, preenchimento de fichas técnicas com informações de PDM e exclusão de duplicatas.

## Entradas e Saídas
- **Entradas**: 
  - Arquivos Excel com aba `TEMPLATE_PDM` (colunas Q e S contêm descrição e unidade)
  - Planilha STATUS_PMIB com aba "Lista de Materiais" (colunas "CÓDIGO PMIB" e "PDM usado" detectadas dinamicamente a partir da linha 4)
  - Template de ficha técnica com aba "Ficha Técnica Padrão" (dados injetados a partir da linha 79)
  
- **Saídas**: 
  - Arquivos `_formatado.xlsx` com tabelas normalizadas (2 colunas: Descrição + Resposta)
  - Arquivos individuais por código PDM extraídos da lista geral (preservam estilos)
  - Fichas PMIB com especificações técnicas preenchidas
  - Mensagens de log via callback

## Classes e Funções

### Funções de Leitura
- **`listar_arquivos_excel(caminho_pasta)`** → lista todos os `.xls*` no diretório
- **`extrair_pdm_id(nome_arquivo)`** → regex `PDM_\d{4}_\d{3}` ou None

### Processamento de Arquivo PDM
- **`processar_arquivo_pdm(caminho_arquivo_pdm)`** → lê aba `TEMPLATE_PDM` (skiprows=6, colunas Q e S), retorna DataFrame com "Descrição" + "Resposta" ou None se erro
- **`salvar_tabela_formatada(nova_tabela, caminho_arquivo_original, pasta_destino, force=False)`** → (sucesso, msg_tuple). Formata com bordas, fonte 8pt, wrap_text, height 32, merge cells (cols 1-10 e 11-20)

### Fatiamento de Lista Geral
- **`pdms_fromItaipu_lista_geral(path_lista_geral_pdms, pasta_destino, log_callback=None)`** → extrai cada código único da aba `TEMPLATE_PDM` (linha 7+, coluna A), cria arquivo individual preservando estilos (fonte, borda, fill, number_format, alignment), retorna string de resumo

### Criação de Fichas PMIB
- **`processar_pastas_fichas(arquivo_STATUS_PMIB, destino_fichas, lista_selecionados=None, criar_subpastas=True)`** → (lista_dados, msg). Lê STATUS_PMIB, formata CÓDIGO PMIB com zeros à esquerda (ex: "1234.5000"), retorna tuplas (cod_fmt, pdm_val, path_dir) para cada item
- **`aplicar_templates_fichas(lista_dados, pasta_pdms_modificados, path_template, log_callback=None)`** → (resumo, log_list). Para cada PMIB: busca arquivo PDM fonte, copia template em memória, injeta Descrição (coluna 1 do PDM) na coluna C (merge 3-12) e Resposta (coluna 2) na coluna M (merge 13-22) a partir da linha 79, formata com bordas/fonte 8pt/height 32
- **`mover_fichas_para_raiz(lista_dados)`** → move arquivos `{pmib}.xlsx` das subpastas para pasta raiz, retorna msg com contador

### Limpeza
- **`logica_excluir_duplicados(pasta_alvo, log_callback=None)`** → agrupa por PDM ID (regex do nome), ordena por (tamanho DESC, modificação ASC), exclui primeiro da lista, retorna contador e log

## Fluxo Detalhado

1. **`processar_arquivo_pdm`** (linha 26–44):
   - Abre arquivo com pandas (aba `TEMPLATE_PDM`, skiprows=6)
   - Valida mínimo 19 colunas (até coluna S)
   - Extrai colunas Q (índice 16) e S (índice 18)
   - Cria DataFrame com linhas numeradas: "1 - Descrição_Q (Unidade_S):"

2. **`pdms_fromItaipu_lista_geral`** (linha 90–160):
   - Carrega lista geral com openpyxl
   - Mapeia cada código único (coluna A, linha 7+) e suas linhas
   - Para cada código novo: busca descrição em coluna D, cria nome `{CODIGO} - {DESC}.xlsx`
   - Copia header (6 primeiras linhas) + linhas do código, preserva todos os estilos (font, border, fill, alignment, number_format) via copy()

3. **`processar_pastas_fichas`** (linha 166–207):
   - Lê STATUS_PMIB (aba "Lista de Materiais", skip 3 linhas)
   - Detecta dinamicamente colunas "CÓDIGO PMIB" e "PDM usado"
   - Normaliza CÓDIGO PMIB: formata com 4 dígitos após o ponto (ex: "1.0000")
   - Retorna lista de (código_formatado, pdm_nome, pasta_destino)

4. **`aplicar_templates_fichas`** (linha 210–281):
   - Para cada PMIB, extrai ID PDM do nome (tira "." e converte para "_")
   - Busca arquivo PDM fonte em `pasta_pdms_modificados`
   - Reabre template limpo do disco
   - Itera linhas do PDM (coluna 1: descrição, coluna 2: resposta)
   - Insere na aba "Ficha Técnica Padrão" a partir da linha 79
   - Merge: descrição em colunas C-L, resposta em colunas M-V
   - Salva como `{pmib}.xlsx` em pasta_destino

5. **`logica_excluir_duplicados`** (linha 308–341):
   - Agrupa arquivos por PDM ID (regex `PDM_\d{4}_\d{3}`)
   - Ordena cada grupo: maior tamanho primeiro, depois mais recente
   - Exclui primeiro arquivo da lista ordenada (comportamento original: excluir o maior)

## Integrações

- **Frontend**: Classe `ModuloPDM` (frontend.py:1040) expõe botões para:
  - Selecionar arquivo de lista geral PDM
  - Selecionar pasta de destino
  - Selecionar arquivo STATUS_PMIB e folder de fichas
  - Gerar fichas PMIB
  - Mover fichas para raiz
  - Limpar duplicados

- **Planilhas**:
  - Lê: `TEMPLATE_PDM` (colunas A-S a partir da linha 7), STATUS_PMIB (aba "Lista de Materiais")
  - Escreve: fichas formatadas, fichas PMIB, arquivos fatiados

- **Outros módulos**: Complementa fluxo de `analyzer_backend.py` (análise de fichas) e `translator_backend.py` (tradução de specs)

## Pontos de Atenção

- **Skiprows=6** em `processar_arquivo_pdm` ignora primeiras 6 linhas de `TEMPLATE_PDM` (linha 29). Estrutura do header pode variar se arquivo foi editado manualmente.
- **Colunas Q e S hardcoded** (índices 16 e 18). Se usuário inserir coluna antes de Q, lógica quebra.
- **Double-check de duplicatas** (linha 120): verifica DUAS vezes se código já existe em pasta_destino antes de criar arquivo. Pode deixar falhas silenciosas se I/O lento.
- **Excepção silenciosa** (linha 300): `except: pass` em `mover_fichas_para_raiz` ignora erros de move. Se arquivo estiver travado, usuário não sabe.
- **Reabertura de template** (linha 235): para cada PMIB, reabre `path_template` do disco (I/O lento). Não reutiliza objeto workbook em memória.
- **Merge hardcoded** (linhas 253–254): colunas 3-12 e 13-22. Se template foi editado com coluna adicional, merge fica errado.
- **Linha 79 fixo** (linha 239): não busca dinamicamente a linha de início. Se template mudar, dados vão para local errado.
- **CÓDIGO PMIB normalização** (linha 182): formata com regex split('.') e ljust(4, '0'). Se formato for diferente (sem ponto), pode gerar código inválido.
