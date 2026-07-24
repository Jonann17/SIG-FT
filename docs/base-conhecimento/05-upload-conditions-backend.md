# Upload de Condições (`upload_conditions_backend.py`)

## Propósito

Processa as fichas de condições de armazenamento, transporte, manutenção e descarte via IA (Gemini 3.5-flash) com sistema prompt de 15 regras obrigatórias (tradução PT/ES, validação de unidades, enriquecimento com legislação). Automatiza o preenchimento das 4 abas de condições no portal PMIB via Selenium com retry de arquivo aberto.

## Entradas e Saídas

**Entradas:**
- Planilha `_STATUS_PMIB` (aba "Lista de Materiais"): colunas CÓDIGO PMIB, DESCRIÇÃO, CONDIÇÕES
- Arquivos Excel de fichas técnicas individuais nomeadas com padrão PMIB (ex: `4500063671.1234.xlsx`)
- Aba "Ficha Técnica Padrão" com células fixas: H6 (descrição breve), H17-H21 (dimensões), P17-P19 (peso), M23 (temperatura), G25-G29 (posição armazenamento), etc.

**Saídas:**
- JSON com dados processados pela IA (novo arquivo ou anexado ao existente)
- Preenchimento no portal PMIB de 4 abas de Condições (Armazenamento b10-b17-b1, Transporte b10-b17-b3, Manutenção b10-b17-b4, Descarte b10-b17-b5)
- Atualização de status na planilha `_STATUS_PMIB` coluna "CONDIÇÕES" para "COMPLETO"

## Classes e Funções

### ConditionsProcessor
**`__init__(api_key)`**: Inicializa o processador com chave Gemini, flag de parada e transporte REST.

**`solicitar_parada()`**: Define flag `cancel_requested = True` para interromper loop principal.

**`carregar_lookup_status(caminho_status_pmib)`**: Lê aba "Lista de Materiais" (força dtype=str), localiza dinâmico de cabeçalho, limpa códigos PMIB (remove apóstrofos, corrige zeros perdidos via regex `^\d{10}\.\d{3}$`). Retorna DataFrame indexado por CÓDIGO PMIB.

**`extrair_dados_brutos_excel(caminho_planilha)`**: Abre "Ficha Técnica Padrão", lê células fixas (H6, H17-H21, P17-P19, M23, etc.), retorna dict com dimensões, peso, temperatura, intempérie, posição, proteção (UV/EL/SN), nocivo, empilhamento, cuidados, 7 campos de texto (embalagem, icagem, preservação, limpeza, ferramentas, legislação, descarte), perigoso_10004, logística reversa.

**`processar_ia_lote(lista_caminhos, df_status, callback_log=None)`**: Loop principal—para cada arquivo com PMIB válido (regex `4500063671\.\d{4}`), extrai dados brutos, valida se já "COMPLETO" no status, monta JSON com contexto da IA, chama gemini-3.5-flash com system prompt de 15 regras, retry 3x com sleep 30s. Retorna fichas processadas.

**`salvar_excel_intermediario(fichas, caminho_salvar)`**: Converte lista de dicts para DataFrame, salva Excel.

**`salvar_novo_arquivo(fichas_novas, caminho_destino)`**: Cria novo Excel com dados processados.

**`anexar_a_arquivo_existente(fichas_novas, caminho_existente)`**: Lê Excel, concatena novos dados, remove duplicatas (keep='last'), salva no mesmo local. Captura PermissionError se arquivo aberto.

### UploadAutomation
**`__init__()`**: Inicializa sem driver, flag cancel_requested.

**`solicitar_parada()`**: Define cancel_requested = True.

**`iniciar()`**: Abre Chrome com WebDriverWait(20s).

**`abrir_portal(url)`**: Executa driver.get(url).

**`fechar()`**: Encerra driver.quit().

**`safe_click(locator)`**: Scroll + wait presence + JS click.

**`safe_send_keys(locator, text)`**: Scroll + wait visibility + click + Ctrl+A + Backspace + send_keys.

**`check_or_uncheck(locator, should_check)`**: Verifica atributo 'checked', clica se diferente do esperado.

**`processar_lista(lista_fichas, caminho_status, callback_ask=None, callback_log=None, callback_pause=None)`**: Loop principal—busca PMIB via input + Enter, clica lápis de edição, preenche 4 abas (Armazenamento/Transporte/Manutenção/Descarte) com XPaths fixos b10-b17-*, salva cada aba com pause callback, atualiza Excel status_pmib coluna "CONDIÇÕES".

**`safe_save_with_pause(locator, section_name, callback_log=None, callback_pause=None)`**: Tenta safe_click em botão Salvar, se falhar chama callback_pause para travamento manual.

**`atualizar_status_excel(caminho, pmib, status, callback_log=None, callback_ask=None)`**: Abre openpyxl, busca dinâmico de colunas "CÓDIGO PMIB"/"CONDIÇÕES" (15 primeiras linhas), blindagem numérica com formato `.4f`, loop retry se PermissionError com callback_ask.

## Fluxo Detalhado

1. **Carregamento de Status**: Lê `_STATUS_PMIB` com dtype=str, força índice por CÓDIGO PMIB com remoção de apóstrofos e correção de zeros.

2. **Extração de Dados Brutos**: Para cada arquivo PMIB na fila:
   - Valida nome com regex `4500063671\.\d{4}`
   - Verifica se status "CONDIÇÕES" já é "COMPLETO" (pula se sim)
   - Lê células fixas de "Ficha Técnica Padrão" (H6, H17-H21, P17-P19, M23, G25-G29, S25/27/29, E31/33, J35-J36, M42/45/52/54/56/63/65, E69/J69/T69, N71)
   - Extrai lista de proteção (SN/UV/EL) via checkboxes

3. **Processamento IA com 15 Regras**:
   - System prompt obrigatório com tradução PT/ES, validação de unidades (cm, kg, °C), enriquecimento legislativo (Lei 12.305/2010, Lei 3956/09), auto-correção perigoso_10004 por contexto
   - Entrada: JSON com PMIB, Descrição, dimensões, temperatura, etc.
   - Saída: JSON normalizado com campos `*_pt` / `*_es`, auto-geração de textos técnicos para descarte/legislação se genéricos
   - Retry 3 tentativas com sleep 30s se falha

4. **Preenchimento Web (RPA Selenium)**:
   - Busca PMIB via XPath input + Enter
   - Clica lápis de edição
   - **Aba Armazenamento** (click `//*[@id="b10-Conditions_Header"]/button`):
     - Preenche dimensões b10-b17-b1-Input_Packing* (comprimento/largura/altura)
     - Controle temperatura: radio b10-b17-b1-RadioButton5/4, checkboxes b10-b17-b1-Checkbox4/5, TAB-navegação entre campos
     - Posição: radios b10-b17-b1-RadioButton/7/8
     - Nocivo: radio + textareas b10-b17-b1-TextArea_StorageCareES/PT
     - Pesos liquido/bruto b10-b17-b1-Input_*Weight
     - Intempérie checkbox b10-b17-b1-Checkbox3 (apenas se temp="NÃO")
     - Proteção checkboxes b10-b17-b1-Checkbox6/7/8 (SN/UV/EL)
     - Empilhamento input b10-b17-b1-Input_Stacking
     - Cuidados radio + textareas b10-b17-b1-TextArea_OtherCareES/PT
   - **Aba Transporte**: click div[3] de Title, preenche TextArea_TransportPackaging/PositionCare ES/PT
   - **Aba Manutenção**: click div[4], preenche PreservationCare/CleaningMethod/ToolPreservation ES/PT
   - **Aba Descarte**: click div[5], preenche Legislation ES/PT, radio perigoso_10004, Discard ES/PT, radio Applies/DoesNotApply, ReserveLogistic ES/PT
   - Salva cada aba com pause callback se erro

5. **Atualização Status**: Abre `_STATUS_PMIB`, busca dinâmico de coluna "CONDIÇÕES", encontra PMIB com blindagem .4f, marca "COMPLETO", retry se arquivo aberto.

## Integrações

- **Planilhas**: `_STATUS_PMIB`, arquivos individuais de fichas (aba "Ficha Técnica Padrão")
- **IA**: Gemini 3.5-flash com system prompt de 15 regras customizado
- **Portal**: PMIB (https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList)
- **Frontend**: Callbacks `callback_log`, `callback_ask` (PermissionError), `callback_pause` (manual intervention)
- **Módulos relacionados**: `frontend.py` dispara via botão, `upload_tech_specs_backend.py` segue fluxo similar

## Pontos de Atenção

- **Regex hardcoded**: Contrato fixo `4500063671\.\d{4}` na linha 147—impossível processar outros PMIBs sem edição.
- **Blindagem numérica crítica**: Formato `.4f` em `atualizar_status_excel` (linhas 759, 762) é essencial para evitar perda de precisão (ex: .11649999 → .1165).
- **Sleep fixos**: 30s entre retries de IA (linha 383), 0.5s + 1s em interações Selenium; sem ajuste automático.
- **Except silencioso**: `safe_click`, `safe_send_keys`, `check_or_uncheck` capturam exceção genérica e passam sem log (linhas 474-481, 483-494, 500-504).
- **XPaths fixos**: Toda navegação RPA depende de ID/class específicos do portal (b10-b17-*, b10-Conditions_Header); mudança UI quebra automação.
- **Tab-navigation**: Controle de temperatura usa `send_keys(Keys.TAB)` em sequência (linhas 553-576) sem fallback se ordem HTML mudar.
- **Duplicação com módulo 2**: Mesmos patterns de `safe_click`/`safe_send_keys`, mesmo system prompt base (tradução PT/ES, enriquecimento legislativo).
- **Cancel_requested**: Flag de parada verifica no início do loop (linha 294), mas não interrompe retry IA em andamento (pode travar 30s).
- **PermissionError retry**: `atualizar_status_excel` loop infinito até sucesso ou usuário rejeitar via callback_ask (linhas 783-792).
- **Dependência Windows**: Normalização de nome de arquivo sanitiza caracteres (linha 163, removidos em ExtratorFichaBase do módulo 3, mas UploadAutomation não usa).
