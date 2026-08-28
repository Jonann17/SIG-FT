# Upload de Condições (`upload_conditions_backend.py`)

> ⚠️ **Onde o código mora hoje** (atualizado em 2026-08-28)
>
> Este documento foi escrito antes da refatoração e descreve o comportamento do
> módulo, que continua valendo. Mas os CAMINHOS mudaram:
>
> | O que o texto abaixo chama de | Está hoje em |
> |---|---|
> | `upload_conditions_backend.py` | `sigft/services/upload_conditions.py` (serviço) · `sigft/app/views/upload_conditions.py` (tela) |
>
> ⚠️ Esta tela escreve o log **só no console da janela** — ele some quando a janela fecha. O log em arquivo (`sigft/core/log_execucao.py`) existe desde 2026-08-18, mas hoje só o módulo de Cópia de Fichas o liga. Ver `PENDENCIAS.md`.
>
> A lógica de negócio descrita aqui continua válida; o que mudou foi onde ela vive. Camadas novas que este texto não menciona: `sigft/core/excel/` (cabeçalho de planilha, código PMIB, gravação com retry), `sigft/core/llm/` (cliente de IA multi-provedor), `sigft/core/rpa/` (portal e motor), `sigft/core/callbacks.py` (o protocolo UI↔serviço).

## Propósito

Processa as fichas de condições de armazenamento, transporte, manutenção e descarte via IA e automatiza o preenchimento das 4 abas de condições no portal PMIB.

> ⚠️ **A política do prompt MUDOU em 2026-08-18/19 e este doc descrevia a antiga.** O texto > antigo mandava "enriquecer com legislação" e auto-corrigir `perigoso_10004` — foi > exatamente isso que fez a IA inventar norma que o fornecedor não escreveu. Hoje vale a > **REGRA 0 (fidelidade ao fornecedor)**, soberana. Ver a seção *Política do prompt* abaixo, > e `sigft/core/llm/prompts.py` → `SYSTEM_CONDICOES` como fonte de verdade.

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

3. **Processamento IA** (ver *Política do prompt*):
   - Entrada: JSON com PMIB, **duas descrições do material** (a do `_STATUS_PMIB`, melhor, e a da célula H6 da ficha), dimensões, peso, temperatura, e os campos de texto livre
   - Saída: JSON normalizado com campos `*_pt` / `*_es`
   - Retry 3 tentativas com sleep 30s se falha (hoje dentro de `LLMClient`)

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

## Política do prompt (`SYSTEM_CONDICOES`)

Duas decisões do usuário, ambas de 2026-08, governam o texto. Elas parecem
opostas e não são — é importante entender por quê antes de mexer.

### 1. REGRA 0 — fidelidade ao fornecedor (soberana)

A ficha é do fornecedor; a IA **traduz e padroniza**, nunca melhora. Nada de
citar norma, lei ou cuidado que não esteja na entrada. Correção só quando o
erro é demonstrável **a partir da própria entrada** — o teste está escrito no
prompt: *"se você precisa saber algo sobre o material que a entrada não diz
para concluir que está errado, então não é evidente"*.

Campo em branco não pode ficar em branco (o portal recusa a gravação), então
sai `No aplicable` / `Não aplicável` — por extenso e em cada idioma, não a
sigla. Campo de escolha sem informação recebe a opção **negativa/neutra**.

Testes: `tests/test_prompt_condicoes_fidelidade.py`.

### 2. A UNIDADE DE MEDIDA é a exceção declarada

Cinco campos numéricos — comprimento, largura, altura, peso líquido, peso
bruto — são o **único** lugar onde a IA deve usar o que sabe sobre o material.
Pedido do usuário: *"a maioria das fichas não virá unidade, mas sabendo o tipo
de material (...) se a embalagem está 400 e estamos falando de um equipamento
que não é muito grande, então a sugestão é que seja 40 cm"*.

A razão de não ser contradição: **a fidelidade é ao tamanho real da coisa, não
ao dígito.** Uma caixa de relé anotada "400" e gravada como 400 cm não é fiel a
nada — é uma caixa de 4 metros que não existe.

Como a dedução é ancorada (regra 3 do prompt):

| | |
|---|---|
| unidade declarada | vence sempre; e uma unidade declarada em UMA das três medidas vale para as três |
| instrumento (a) | o que é o material — `Descrição do material` (do `_STATUS_PMIB`) e `Descrição breve da ficha` (H6) |
| instrumento (b) | o peso, como aferidor: `densidade = peso_kg ÷ (C × L × A em cm) × 1000` |
| faixa plausível | 0,1 a 2 g/cm³ numa caixa embalada; nada real abaixo de ~0,02 nem acima de ~8 |
| densidade baixa demais | a caixa suposta é grande demais ⇒ era **mm**, dividir por 10 |
| densidade alta demais | a caixa é pequena demais ⇒ era **m**, multiplicar por 100 |
| densidade na faixa | já estava em cm — **não mexer** |

Limites, que são a parte que se esquece: a licença é **só da unidade** e só
desses cinco campos; número que não veio não se inventa (dimensão vazia
continua vazia); o mesmo fator vale para as três medidas; peso líquido nunca
passa do bruto; na dúvida genuína, fica como veio. E **não arredondar** — o
campo do portal não tem limite de casas decimais (`maxlength="30"`, sem
máscara: `data-os-pattern=""`).

Testes: `tests/test_prompt_condicoes_unidades.py`.

### Fixtures

`tests/fixtures/prompts/upload_conditions_{system,user}.txt` travam o texto
contra mudança **acidental**. Elas já foram regeneradas duas vezes de
propósito (2026-08-18 e 2026-08-19), e por isso não provam mais "igual ao de
antes da refatoração" — quem prova a política é o par de arquivos de teste
acima, que checa conteúdo. Uma fixture regerada não se auto-aprova.


## Integrações

- **Planilhas**: `_STATUS_PMIB`, arquivos individuais de fichas (aba "Ficha Técnica Padrão")
- **IA**: `LLMClient` (provedor e modelo vêm de `config.LLM_TASKS`, tarefa `condicoes`); o texto do prompt está em `sigft/core/llm/prompts.py` → `SYSTEM_CONDICOES`
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
