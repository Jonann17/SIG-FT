# Upload de Especificações Técnicas (`upload_tech_specs_backend.py`)

> ⚠️ **Onde o código mora hoje** (atualizado em 2026-08-28)
>
> Este documento foi escrito antes da refatoração e descreve o comportamento do
> módulo, que continua valendo. Mas os CAMINHOS mudaram:
>
> | O que o texto abaixo chama de | Está hoje em |
> |---|---|
> | `upload_tech_specs_backend.py` | `sigft/services/tech_specs.py` (serviço) · `sigft/app/views/upload_tech_specs.py` (tela) |
>
> ⚠️ Atenção ao nome: o serviço chama-se `tech_specs.py`, sem o prefixo `upload_`.
>
> A lógica de negócio descrita aqui continua válida; o que mudou foi onde ela vive. Camadas novas que este texto não menciona: `sigft/core/excel/` (cabeçalho de planilha, código PMIB, gravação com retry), `sigft/core/llm/` (cliente de IA multi-provedor), `sigft/core/rpa/` (portal e motor), `sigft/core/callbacks.py` (o protocolo UI↔serviço).

## Propósito

Processa características técnicas cruzando `_STATUS_PMIB` + Master PDM com IA (Gemini 3.5-flash em modo JSON) e system prompt de regras CHAR/INT/NUM/LISTA com auditorias de tipo, unidade e paginação. Automatiza preenchimento de tabelas de características no portal com exclusão segura, auditoria de rejeição e pendências manuais.

## Entradas e Saídas

**Entradas:**
- Planilha `_STATUS_PMIB` (aba "Lista de Materiais"): colunas CÓDIGO PMIB, PDM usado, CARACT. TÉCNICAS
- Master PDM (aba "TEMPLATE_PDM"): CÓDIGO PDM, CARACTERÍSTICA - DESCRIPCIÓN PT, TEXTO DE AYUDA PT, TIPO DE CARACTERÍSTICA, VALORES PT, SÍMBOLO
- Fichas individuais (aba "Especificações técnicas copiar"): colunas Pergunta, Resposta (Espanhol), Resposta (Português)

**Saídas:**
- JSON estruturado com METADATA (PMIB, PDM, ARQUIVO_ORIGEM) e DADOS_TRATADOS (lista de características com ACAO PREENCHER/REMOVER)
- Preenchimento da tabela de características técnicas no portal (loop paginação, linhas por página)
- Atualização coluna "CARACT. TÉCNICAS" em `_STATUS_PMIB` para "COMPLETO" após sucesso RPA
- Relatório de pendências manuais (campos que site rejeitou em auditoria)

## Classes e Funções

### TechSpecsProcessor
**`__init__(api_key)`**: Inicializa Gemini com transporte REST, flag cancel_requested.

**`solicitar_parada()`**: Define cancel_requested = True.

**`normalizar_texto(texto)`**: Remove acentos via NFD, converte maiúsculas, normaliza espaços.

**`limpar_pergunta(texto_pergunta)`**: Extrai texto após número + hífen via regex `^\d+\s*-\s*(.*)`.

**`extrair_codigo_pmib_arquivo(nome_arquivo)`**: Regex `\d{10}\.\d+` extrai código.

**`formatar_pdm(pdm_raw)`**: Pega primeira palavra antes de espaço.

**`encontrar_header(df, coluna_chave, limite_linhas=15)`**: Busca coluna em primeiras 15 linhas, promove a índice, retorna DataFrame a partir dali.

**`preparar_dados_ia(lista_arquivos, path_status, path_master, processar_completos=False, callback_log=None)`**: Loop principal—lê status + master, itera arquivos, valida PMIB, verifica status "CARACT. TÉCNICAS" = "COMPLETO" (pula se não processar_completos), lê aba "Especificações técnicas copiar", mapeia respostas PT/ES por pergunta, cruza com Master PDM para montar contexto com TIPO_DADO/VALORES_POSSIVEIS/SÍMBOLO, chama `_chamar_gemini_specs`, retorna lista de resultados.

**`_chamar_gemini_specs(contexto_json, callback_log=None)`**: Chama gemini-3.5-flash com response_mime_type="application/json", system_instruction com 4 regras de integridade (sem duplicar, obediência tipo dado), formatação (vírgula decimal, ponto-vírgula para listas), conversão unidades (l/min → m³/h), retenção/exclusão (N/A, traços). Retry 3x com sleep 2s se falha. Retorna JSON parseado ou None.

### TechSpecsAutomation
**`__init__()`**: Inicializa sem driver, flag cancel_requested.

**`solicitar_parada()`**: Define cancel_requested = True.

**`iniciar()`**: Abre Chrome com WebDriverWait(20s).

**`fechar()`**: driver.quit().

**`abrir_portal(url)`**: driver.get(url).

**`safe_click(locator)`**: Scroll + wait presence + JS click (sem exception propagation).

**`safe_send_keys_elem(element, text)`**: Scroll + click + Ctrl+A + Backspace + send_keys + TAB.

**`safe_send_keys_locator(locator, text)`**: Wrapper que obtém elemento e chama `safe_send_keys_elem`.

**`normalizar_texto(texto)`**: Mesmo método de TechSpecsProcessor.

**`selecionar_dropdown_lista(element, texto)`**: Tenta select_by_visible_text, fallback normaliza e busca em options.

**`selecionar_dropdown_unidade(element, texto)`**: Busca opção contendo `(TEXTO_MAIÚSCULO)`.

**`_preencher_input_com_auditoria(element, valor_alvo, elem_neutro, nome_campo="", callback_log=None)`**: Preenche via Selenium, clica fora (elem_neutro), audita se valor ficou 0 ou vazio (site rejeitou), se sim tenta injeção JS (dispatchEvent input/change/blur), sleep 1.5s antes da 2ª tentativa, retorna True/False.

**`_pesquisar_e_abrir(pmib)`**: Navega URL_lista, preenche campo pesquisa, Enter, aguarda 4s, clica lápis de edição com retry 3x StaleElement.

**`processar_lista(lista_fichas, callback_log=None, callback_pause=None)`**: Loop principal—para cada ficha com metadata PMIB, busca/abre ficha, clica aba "Características técnicas", normaliza chaves características em dict O(1), loop paginação (while True), loop linhas (row_index), extrai descrição, busca em dict, se ACAO="REMOVER" chama `_excluir_linha_segura` (não incrementa row_index se sucesso), se ACAO="PREENCHER" chama `_preencher_linha` com auditoria, coleta falhas em pendencias_manuais, navega página seguinte se botão habilitado, pausa manual callback_pause no final, retorna lista pmibs_finalizados.

**`_excluir_linha_segura(row, chave_limpa, callback_log=None)`**: Encontra lixeira, clica via JS, clica CONFIRMAR popup, sleep 2.5s, retorna True/False.

**`_preencher_linha(row, dado, callback_log=None)`**: Despacha por TIPO (CHAR/NUM/LISTA/INT), para CHAR preenche textareas PT/ES direto, para NUM chama `_preencher_input_com_auditoria`, para LISTA seleciona dropdown, para INT seleciona subtipo (MINIMO/MAXIMO, etc.), preenche min/max com auditoria, preenche SIMBOLO em dropdown unidade, retorna sucesso_auditoria booleano.

### TechSpecsController
**`__init__()`**: Inicializa dados_em_memoria (lista vazia), processor_ativo, automacao_ativa (None).

**`cancelar_processo_ia()`**: Chama solicitar_parada() em processor_ativo.

**`cancelar_processo_web()`**: Chama solicitar_parada() em automacao_ativa.

**`executar_pipeline_ia(api_key, lista_arquivos, path_status, path_master, processar_completos=False, callback_log=None)`**: Instancia TechSpecsProcessor, chama preparar_dados_ia, armazena resultados em dados_em_memoria, limpa referência, retorna resultados.

**`salvar_json(dados, caminho_arquivo, modo_anexar=False, callback_log=None)`**: Se modo_anexar e arquivo existe, lê JSON antigo e concatena; senão usa dados direto. Salva com json.dump (ensure_ascii=False, indent=4).

**`executar_pipeline_rpa(dados_json, caminho_status="", callback_log=None, callback_pause=None)`**: Instancia TechSpecsAutomation, inicializa driver, abre portal, pausa para login manual (callback_pause "LOGIN_NECESSARIO"), chama processar_lista, recebe pmibs_finalizados, atualiza Excel com openpyxl (busca dinâmico colunas "CÓDIGO PMIB"/"CARACT. TÉCNICAS", marca "COMPLETO" para cada PMIB sucesso), loop retry se PermissionError.

## Fluxo Detalhado

1. **Preparação de Dados IA**:
   - Lê _STATUS_PMIB (aba "Lista de Materiais") com header dinâmico
   - Lê Master PDM (aba "TEMPLATE_PDM") com header dinâmico
   - Para cada arquivo PMIB: extrai código via regex, valida existência em status, verifica coluna "CARACT. TÉCNICAS" (pula se "COMPLETO" e não processar_completos)
   - Lê ficha (aba "Especificações técnicas copiar"), normaliza nomes de colunas
   - Monta lista de contexto: para cada característica do Master, busca resposta PT/ES na ficha, inclui TIPO_DADO/VALORES_POSSIVEIS/SÍMBOLO/TEXTO_AJUDA
   - Prepara JSON com CODIGO_PMIB, PDM, CARACTERISTICAS
   - Chama Gemini com response_mime_type JSON, retry 3x com sleep 2s

2. **Processamento IA (System Prompt 4 Regras)**:
   - **Regra 1**: Sem duplicação de CARACTERISTICA_CHAVE, obediência estrita a TIPO_DADO
   - **Regra 2**: Vírgula decimal (,) para NUM/INT, ponto-vírgula (;) para LISTA; sem ponto (.)
   - **Regra 3**: Conversão unidades (l/min → m³/h via cálculo matemático)
   - **Regra 4**: Retenção/exclusão por contexto (N/A, traços, "Idem" sem resolução → ACAO="REMOVER")
   - Output JSON: array com CARACTERISTICA_CHAVE, TIPO, VALORES_PT, SUBTIPO_INTERVALO, RESPOSTA_PT_FINAL, RESPOSTA_ES_FINAL, SIMBOLO, ACAO

3. **Automação Web (Selenium Paginação)**:
   - Busca/abre ficha alvo via `_pesquisar_e_abrir(pmib)` com retry 3x StaleElement
   - Clica aba "Características técnicas"
   - Aguarda tabela carregar
   - Monta dict O(1) com chaves normalizadas → dados
   - Loop **paginação**:
     - Loop **linhas** da página:
       - Extrai descrição coluna, normaliza
       - Busca em dict de dados
       - Se encontrado:
         - Se ACAO="REMOVER": chama `_excluir_linha_segura` (lixeira + CONFIRMAR popup), não incrementa row_index
         - Se ACAO="PREENCHER": chama `_preencher_linha`, audita, coleta falhas em pendencias_manuais, incrementa row_index
       - Se StaleElement: continue (tenta pegar linha novamente)
     - Tenta botão "Ir para a página seguinte", se habilitado clica + sleep 3s + aguarda tabela, senão break
   - Exibe pendências manuais via callback_log (site bloqueou digitação)
   - Chama callback_pause(pmib) para pausa manual/inspeção
   - Adiciona pmib a pmibs_finalizados

4. **Atualização Status**:
   - Abre openpyxl _STATUS_PMIB
   - Busca dinâmico colunas "CÓDIGO PMIB" e "CARACT. TÉCNICAS" (15 linhas)
   - Para cada pmib_finalizado: encontra primeira ocorrência, marca "COMPLETO"
   - Trata PermissionError com retry automático

## Integrações

- **Planilhas**: `_STATUS_PMIB`, Master PDM, fichas individuais (aba "Especificações técnicas copiar")
- **IA**: Gemini 3.5-flash com response_mime_type JSON, system prompt 4 regras (integridade, formatação, conversão, retenção)
- **Portal**: PMIB (https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList), paginação de características
- **Frontend**: TechSpecsController orquestra pipeline IA + RPA, callbacks callback_log/callback_pause
- **Módulos relacionados**: `upload_conditions_backend.py` padrão similar (Gemini, retry, XPaths)

## Pontos de Atenção

- **response_mime_type JSON obrigatório**: Linha 289 `generation_config={"response_mime_type": "application/json"}` garante output JSON; sem isso Gemini retorna texto livre e `_limpar_json_ia` falha.
- **Normalizacão crítica em O(1)**: Dict `dict_dados` (linha 526) indexado por chave normalizada essencial para performance em 100+ características; sem isso seria O(n) por linha.
- **StaleElementReferenceException**: Recarrega `rows` a cada iteração (linha 536) para evitar captura pré-paginação; exceção inner loop continua sem incrementar row_index.
- **XPaths dinâmicos com contains()**: Linhas 452, 514, 516 usam `contains()` para ignorar prefixo dinâmico de IDs; mudança structure HTML quebra.
- **Paginação assume botão "Ir para a página seguinte"**: Xpath hardcoded (linha 587), XPath alternativo para botão Próximo não mapeado.
- **Auditoria 2-tentativa de input**: `_preencher_input_com_auditoria` digita normal (1ª), se site zera (0 ou vazio) tenta injeção JS com dispatchEvent (2ª), sleep 1.5s entre—sem fallback se ambas falharem.
- **Callback_pause obrigatório**: RPA não continua até usuário confirmar (pause na line 610 é blocking), essencial para inspeção manual antes de salvar.
- **Pendências manuais coletadas não resolvidas**: Relatório mostra campos que site rejeitou, mas não tenta fill automático; usuário deve preencher na UI.
- **Duplicação com módulo 1**: Mesmo pattern safe_click, mesma estrutura de callback (log, pause), system prompt base com tradução PT/ES.
- **Master PDM merge**: Cruzamento faz inner join (não inclui características da ficha sem match em Master), perda de dados customizados.
- **Cancel_requested**: Flag verifica início loop (linha 96), não interrompe chamada Gemini em andamento (pode demorar).

---

## 2026-09-23 — limpeza das em branco, SALVAR validado, e o fim da pausa obrigatória

Três mudanças pedidas pelo usuário, todas no fim do processamento de cada ficha.

### 1. As linhas em branco que o JSON não menciona são APAGADAS

Quando a ficha (a planilha traduzida) foi feita numa revisão **antiga** do PDM e
o portal já está numa mais nova, a tabela traz linhas que não existiam na
origem. Até aqui o robô as deixava lá com um `·  ignorada (não veio no JSON)`.

`TechSpecsAutomation.apagar_em_branco_fora_do_json(dict_dados, callback_log)`
roda **depois** do preenchimento e antes do salvamento, percorre todas as
páginas e apaga. O log diz o porquê, característica a característica.

⚠️ **As três condições são todas necessárias**, e cada uma protege um caso:

| Condição | O que ela impede |
|---|---|
| **em branco** | uma linha COM valor fora do JSON pode ter sido preenchida à mão; apagá-la destruiria trabalho humano |
| **fora do JSON** | uma linha em branco que o JSON MENCIONA é um preenchimento que falhou; apagá-la esconderia o que falta corrigir |
| **a mesma chave do preenchimento** | chaves diferentes fariam a limpeza apagar exatamente o que acabou de ser preenchido |

A chave passou a ter **uma definição só**, `chave_da_caracteristica`, usada
pelas duas rotinas — e há teste comparando as duas com os formatos reais do
portal (`1650 - COMPONENTES`, com espaços em volta do hífen).

O índice **não avança** quando a linha é apagada (a de baixo sobe para o
lugar), e há o guard de "apaguei não é prova de que sumiu": se a contagem não
cair, o robô avisa e segue, em vez de girar para sempre na mesma linha.

### 2. O SALVAR é do robô, e validado pela mensagem do portal

`salvar_caracteristicas()` clica o SALVAR **da seção de características**
(ancorado em `TechnicalCharacteristics_Content`; sem âncora a busca varreria a
tela, que é o defeito de 2026-08-20) e devolve `(ok, mensagem)`.

`ok` só é `True` com o toast de sucesso **novo** na tela. Quando não confirma,
lê o aviso (`feedback-message-warning` → *"Por favor, verifique os campos"*).

⚠️ O toast de sucesso tem `feedback-message-autoclose`; o de aviso **não**. O
aviso fica na tela, e é isso que torna seguro lê-lo depois da falha.

### 3. QUAIS campos o portal recusou

`caracteristicas_com_erro()` devolve `[{"chave", "campos", "mensagem"}, ...]`.
O portal marca o campo culpado com a classe `not-valid` e escreve embaixo dele
um `<span class="text-error">`. Numa linha `CHAR` o aviso aparece **por
idioma**, então o log diz se o problema está no PT, no ES ou nos dois:

```
⛔ 4500063671.0242: o portal NAO confirmou o salvamento (Por favor, verifique os campos).
   ✋ CERTIFICADO [PT/ES]: Caracter inválido!
```

O marcador é a **classe**, nunca o texto: a mensagem muda conforme o motivo.

### O que mudou no fluxo, e o que você precisa saber

| Antes | Agora |
|---|---|
| pausava em **toda** ficha para a pessoa conferir e salvar | salva sozinho; **pausa só na ficha que não salvou** |
| toda ficha entrava em `pmibs_finalizados` | **só a ficha confirmada** entra |

A segunda linha é a que exige atenção: `pmibs_finalizados` é o que marca
**COMPLETO** no `_STATUS_PMIB`. Marcar uma ficha que o portal não gravou seria
declarar pronto o que não está.

### 3. A reconferência depois da pausa

Pergunta do usuário: *"se eu precisar salvar na mão e clicar no botão de
continuar a automação, ele marcará como completo se aparecer a mensagem de
salvo com sucesso?"*

Até 2026-09-23 a resposta era **não** — o robô decidia pela 1ª tentativa e
nunca mais olhava, então a ficha consertada à mão ficava pendente na planilha.
Agora, **depois** que `callback_pause(pmib)` retorna, `processar_lista` chama
`salvar_caracteristicas()` outra vez:

- confirmou → a ficha entra em `pmibs_finalizados` e vira **COMPLETO**;
- não confirmou → fica pendente, e o log diz "continua sem confirmar".

O clique extra no SALVAR é deliberado e barato: o portal só devolve o toast
verde se gravou **agora**, então ele é a única evidência de que o problema
saiu. Uma ficha já salva à mão simplesmente salva de novo.

`lote.aviso(...)` migrou para depois da pausa, sob `if not salvou` — antes ele
registrava o aviso na 1ª recusa e a ficha consertada saía no relatório como
problema mesmo tendo dado certo.

### 4. Interromper no meio da lista não desfaz nada

O **"PARAR ROBÔ WEB"** da própria tela chega aqui como `solicitar_parada()`,
que `processar_lista` lê no `deve_parar()` e trata com `break`. As fichas já
concluídas seguem em `pmibs_finalizados` e são marcadas COMPLETO normalmente
— parar no meio custa a lista, nunca o que já foi feito.

⚠️ **Nada disso rodou contra o portal.** Os seletores do aviso e do campo
inválido vieram do HTML que o usuário colou, e há teste avaliando-os com `lxml`
contra esse recorte; o fluxo inteiro só se prova em execução real.
