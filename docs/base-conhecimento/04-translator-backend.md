# Translator Backend (`translator_backend.py`)

## Propósito
Módulo de tradução híbrida de especificações técnicas de português para espanhol usando xlwings (Excel COM no Windows). Lê perguntas e respostas da aba "Ficha Técnica Padrão" a partir da linha 79, traduz via Google Translator com fallback MyMemory, remove caracteres especiais (unidecode) e cria aba "Especificações técnicas copiar" com formatação zebrada e bordas.

## Entradas e Saídas
- **Entradas**:
  - Arquivo Excel COM (Windows) com aba "Ficha Técnica Padrão"
  - Perguntas a partir da linha 79, coluna C (3)
  - Respostas na mesma linha, coluna M (13)
  - Suporta caminho longo (>240 chars) via temp
  
- **Saídas**:
  - Aba "Especificações técnicas copiar" com 3 colunas: Pergunta | Resposta (Espanhol s/ acentos) | Resposta (Português s/ acentos)
  - Formatação: cabeçalho azul escuro com texto branco, linhas zebradas (azul claro alternado), bordas finas, wrap_text, altura 50
  - Larguras: Pergunta=40, Respostas=50
  - Arquivo atualizado in-place ou via temp se caminho >240 chars

## Classes e Funções

### TechnicalTranslator
- **`__init__()`** → inicializa stop_flag=False
- **`request_stop()`** → sinaliza parada (cancela loop de tradução)
- **`_remover_caracteres_especiais(texto)`** → unidecode (remove acentos)
- **`_traduzir_hibrido(texto)`** → GoogleTranslator('pt'→'es') com fallback MyMemory, ignora ["-", "N/A", "NA", ".", "0", 0]
- **`processar_arquivo(caminho_original)`** → Generator que yield logs ("Iniciando...", "Traduzindo item X", "PARADO", "SUCESSO", "ERRO", "ERRO_MOVER"). Gerencia temp, xlwings, formatação

## Fluxo Detalhado

1. **Inicialização e Validação de Caminho** (linha 56–76):
   - Detecta se len(caminho) > 240
   - Se sim: copia para `tempdir/temp_{timestamp}_{nome}`, marca `usando_temp=True`
   - Caso contrário: usa caminho original direto

2. **Abertura Excel COM** (linha 79–96):
   - `xw.App(visible=False)` abre Excel invisível
   - Abre workbook com `app.books.open(caminho_trabalho)`
   - Valida se aba "Ficha Técnica Padrão" existe
   - Se não: fecha, deleta temp, yield erro, retorna

3. **Preparação de Aba Destino** (linha 99–109):
   - Deleta aba "Especificações técnicas copiar" se existir
   - Cria aba nova após última aba
   - Escreve cabeçalho em A1: ["Pergunta", "Resposta (Espanhol s/ caracteres especiais)", "Resposta (Português s/ caracteres especiais)"]

4. **Loop de Tradução** (linha 110–157):
   - `current_row = 79` (fixo)
   - Enquanto True:
     - **Checagem de parada** (linha 118): se `stop_flag=True`, fecha, deleta temp, yield "PARADO", retorna
     - **Leitura pergunta**: `source_sheet.range((current_row, 3)).value` (coluna C)
     - Break se pergunta vazia
     - **Processamento texto**: split por '(', strip, remove ':' e '.'
     - **Leitura resposta**: `source_sheet.range((current_row, 13)).value` (coluna M)
     - **Remove acentos PT**: `_remover_caracteres_especiais(resposta_val)`
     - **Sleep 1.0s** (linha 144): delay de segurança original
     - **Traduz hibrido**: Google → fallback MyMemory
     - **Remove acentos ES**: `_remover_caracteres_especiais(resposta_traduzida)`
     - **Escreve linha destino**: item_counter+1, 3 colunas (pergunta, es, pt)
     - `item_counter++`, `current_row++`

5. **Formatação Visual** (linha 159–200):
   - **Larguras**: coluna A=40, B–C=50 (via `range('A:A').column_width`)
   - **Altura de linhas**: 50 para linhas 2 até `item_counter`
   - **Alinhamento geral**: wrap_text=True, vertical=xlCenter
   - **Cabeçalho**: bold, horizontal center, cor RGB(47, 117, 181) (azul escuro), texto branco (0xFFFFFF)
   - **Zebrado** (linhas 183–199):
     - Se i % 2 == 0: RGB(221, 235, 247) (azul muito claro)
     - Senão: RGB(189, 215, 238) (azul claro)
     - **Checagem de parada** durante zebrado (linha 185): retorna se stop_flag=True
     - **Bordas**: LineStyle=1, Weight=2 (thin, com try/except silencioso)

6. **Salvamento e Restauração** (linha 202–227):
   - `wb.save()` atualiza arquivo
   - `wb.close()` fecha workbook
   - Se `usando_temp=True`:
     - Copia temp de volta para original: `shutil.copy2(temp, original)`
     - Deleta arquivo temp
     - Se erro: yield "ERRO_MOVER", retorna
   - Yield "[SUCESSO]" e "SUCESSO"

7. **Tratamento de Exceção** (linha 220–227):
   - Except geral: yield "[ERRO FATAL]", tenta fechar workbook
   - Se usado temp: deleta arquivo temporário
   - Yield "ERRO"

8. **Finalização** (linha 230–232):
   - Finally: se `app.books.count == 0`, fecha Excel COM via `app.quit()`

## Integrações

- **Frontend**: Classe `ModuloTranslator` (frontend.py:1659) instancia `TechnicalTranslator()`, expõe botão "Processar" que chama `backend.processar_arquivo()` em thread, itera sobre yields para log, oferece botão "Parar" que chama `backend.request_stop()`
- **Planilhas**:
  - Lê: Aba "Ficha Técnica Padrão" (colunas C e M, linha 79+)
  - Escreve: Aba "Especificações técnicas copiar" com tradução + limpeza de acentos

- **Dependências**: xlwings (Excel COM, Windows only), deep_translator (GoogleTranslator, MyMemoryTranslator), unidecode (remoção de acentos)

## Pontos de Atenção

- **xlwings + Excel COM (Windows-only)**: Não roda em Linux/Mac sem Wine/Parallels. Sem tratamento de fallback para ambiente sem Excel.
- **Caminho longo hardcoded em 240 chars** (linha 64): limite anterior a Windows MAX_PATH (260). Se arquivo em path >240 chars e não é temp, cria cópia desnecessária mesmo se não ajuda.
- **Temp via `tempfile.gettempdir()`** (linha 67): pode estar cheio ou com restrições de escrita. Sem validação de espaço em disco.
- **Delay hardcoded 1.0s** (linha 144): entre cada item traduzido. 100 itens = 100s mínimo. Sem configuração externalizável.
- **MyMemory fallback silencioso** (linha 43–48): se ambas (Google + MyMemory) falham, retorna texto original. Usuário não sabe que tradução falhou.
- **Linha 79 fixo** (linha 111): não detecta dinamicamente onde começam as especificações. Se template foi editado, começa traduzir de lugar errado.
- **Coluna C e M hardcoded** (linha 128, 137): índices fixos. Se coluna foi inserida/deletada, busca dados errados.
- **Aba "Especificações técnicas copiar" hardcoded** (linha 100): se template usa nome diferente, gera aba nova com nome fixo.
- **Stop flag durante formatação** (linha 185): interrupção é possível, mas workbook já foi lido. Se usuário clica "Parar" durante zebrado, arquivo é deixado parcialmente formatado.
- **Except silencioso em bordas** (linha 194): `try/except: pass` ignora erros de aplicação de estilos. Linhas podem ficar sem borda se API xlwings falha.
- **Restauração não-atômica** (linha 209): se falha ao copiar temp de volta, arquivo original fica intacto, mas temp pode não ser deletado (except silencioso linha 210). Acumula lixo em temp.
- **Google + MyMemory sem auth**: Não configura chaves de API. Dependem de endpoints públicos (rate-limited, podem retornar 429/403 em alto volume).
