# Gerador de Fichas PMIB (`cria_fichas_no_pmib_v1_backend.py`)

> ⚠️ **Onde o código mora hoje** (atualizado em 2026-08-28)
>
> Este documento foi escrito antes da refatoração e descreve o comportamento do
> módulo, que continua valendo. Mas os CAMINHOS mudaram:
>
> | O que o texto abaixo chama de | Está hoje em |
> |---|---|
> | `cria_fichas_no_pmib_v1_backend.py` | `sigft/services/cria_fichas.py` (serviço) · `sigft/app_qt/views/cria_fichas.py` (tela) |
>
> A lógica de negócio descrita aqui continua válida; o que mudou foi onde ela vive. Camadas novas que este texto não menciona: `sigft/core/excel/` (cabeçalho de planilha, código PMIB, gravação com retry), `sigft/core/llm/` (cliente de IA multi-provedor), `sigft/core/rpa/` (portal e motor), `sigft/core/callbacks.py` (o protocolo UI↔serviço).

## ⚠️ A escolha de PDM mudou em 2026-09-22 — leia antes do resto

O texto deste documento descreve o fluxo **como ele era**. A etapa de escolha de
PDM foi reescrita; o resto (leitura da planilha, RPA no portal, edição em massa)
continua valendo.

### O que estava errado

Diagnóstico medido contra a planilha-mestra real (`PDMs SAM-GM`, 32.655 linhas,
**1.193 PDMs** válidos, 165 classes FSC no manual e **124 com PDM**):

| # | Defeito | Evidência |
|---|---|---|
| 1 | **2 dos 8 exemplos few-shot do prompt apontavam PDMs errados** | `PDM.4020.001 - BOMBA CENTRIFUGA` não existe (nem o código, nem o título, sob código nenhum); `PDM.6145.011 - CABO, TRANSMISSAO DADOS` tem vírgula que o título real não tem — e é essa string que é digitada no filtro do portal |
| 2 | Um 4º exemplo contrariava as notas do próprio catálogo | a câmera AXIS apontava a classe 6720 ("CÁMARAS FOTOGRÁFICAS"); a classe 6710 exclui câmeras de vídeo remetendo à **5836** |
| 3 | **O elo entre o manual e a lista nunca era dito** | o prompt mandava "ache a classe, escolha o PDM dela", e a lista plana não dizia a classe de ninguém — apesar de o código embuti-la (`PDM.XXXX.YYY`) |
| 4 | **O manual descrevia 41 classes sem nenhum PDM** | armadilha ativa: a IA raciocinava até a classe e não havia o que escolher lá |
| 5 | **Nada validava o PDM escolhido** | IA → revisão de texto livre → digitado no portal, sem nunca conferir pertinência ao catálogo |
| 6 | **Casamento por posição** | `res_json[i]` → `df.iloc[i]`: um item pulado pela IA deslocava todas as linhas seguintes, e cada material recebia o PDM de outro — em silêncio |
| 7 | **As características não entravam na escolha** | 17,5 por PDM em média, lidas só depois para montar o template. São elas que separam `VALVULA GAVETA` (MATERIAL DA CUNHA) de `VALVULA ESFERA` (TIPO DE PASSAGEM, NUMERO DE VIAS) |
| 8 | Lote inteiro numa chamada, sem retry | `max_retries=0`: uma falha de API derrubava os 40 itens juntos |

> ⚠️ **Um terceiro exemplo foi acusado e absolvido no mesmo dia.**
> `PDM.7010.018 - SERVIDOR` estava **certo**. A acusação ("o título real é
> `SERVIDOR CONSOLE`") nasceu de um defeito do leitor novo, que pegava o título
> da PRIMEIRA linha do código em vez do da revisão VIGENTE — e na revisão 0 esse
> PDM se chamava assim mesmo. Na vigente (rev 2, 28/02/2025) ele é `SERVIDOR`.
> Fica registrado porque a lição vale para o módulo inteiro: **no Master, o campo
> certo depende da revisão, e isso inclui o TÍTULO** — que é a string digitada no
> filtro do portal. Título de revisão antiga não filtra nada, e a automação
> quebra com o PDM certo já escolhido.

Por que a ambiguidade é real: **178 dos 467 nomes base cobrem mais de um PDM**
(VALVULA 44×, RELE 40×, CONJUNTO 27×), e **13 títulos são compartilhados por 2
PDMs** — em 4 desses pares os dois estão na **mesma classe**, onde só a
característica desempata.

### Como é agora

`sigft/core/pdm_catalogo.py` é a fonte única do catálogo. Ele:

1. **Lê a planilha-mestra da Itaipu direto** (abas `TEMPLATE_PDM` e
   `GRUPOS_CLASES`), sem manipulação. O formato manipulado antigo (abas `PDMs` +
   `Instruções PDMs`) continua aceito, mas não tem característica.
2. **Fica só com a revisão vigente de cada PDM — características E título.**
   1.023 dos 1.194 PDMs têm mais de uma revisão; unir as revisões trazia de
   volta característica que já saiu do PDM (o "lixo de REMOVER" registrado em
   `PENDENCIAS.md`), o que seria sinal FALSO no desempate. No título o dano é
   pior: ele é a string **digitada** no filtro de PDM do portal. Em 47 PDMs a
   primeira linha do arquivo não é a vigente, e em 4 deles o título difere.
3. **Pré-filtra ~12 candidatos por item**, por ranqueamento léxico que pesa cada
   palavra pela informação que ela carrega (espírito do IDF) e pesa mais o
   casamento no nome base/modificador do que na característica. Tem glossário
   EN→PT (as descrições de fornecedor chegam em inglês; o catálogo é PT/ES),
   singularização e penalidade para palavra do título que a descrição não
   confirmou — é o que faz `BOMBA` vencer `BOMBA VACUO` num "Bomba KSB 123-ABC".
4. **Manda a lista completa agrupada por classe como REDE.** Não é luxo: medido,
   uma descrição como `IE4010 w/ 12GE SFP uplink ports` não tem nenhuma palavra
   que nomeie o equipamento, e nenhum ranqueamento léxico a alcança.

No prompt (`core/llm/prompts.montar_categorizar_pdm`): os 8 exemplos agora
existem no catálogo (conferidos um a um), a regra código↔classe está enunciada,
o manual vai podado às classes dos candidatos do bloco, e há regra de **lista
fechada** ("escolha uma string que aparece literalmente na lista, ou NENHUM").

No serviço (`services/cria_fichas.py`): `processar_lote(df_itens, catalogo,
callback_log=None)` — mudou de assinatura, e o manual de regras deixou de ser
montado **dentro da view** (era regra de negócio na UI). O lote é fatiado em
blocos de `ITENS_POR_BLOCO`; `alinhar_resposta` casa a resposta pelo
`item_processado`; `conferir_pdm` valida contra o catálogo e **canoniza** pelo
código quando só o título divergiu; `codigo_do_pdm` permite comparar o PDM
pedido com o que o portal gravou.

No portal: a busca do PDM virou uma **cascata de três tentativas**
(`AutomacaoPMIB._buscar_pdm`) — texto completo, depois só o código, depois só o
título. Entre uma e outra ela confere `XPATH_PDM_NAO_ENCONTRADO`
(`div.vscomp-no-search-results[aria-hidden='false']`, o "PDM não encontrado"
que o portal mostra no lugar da lista). Antes o fluxo digitava, esperava um
segundo e apertava ENTER **sem perguntar se o filtro achou algo** — e um texto
que não casasse quebrava a automação três passos adiante, com o PDM certo já
escolhido. Quando as três falham, o item vira um ERRO com as buscas tentadas no
texto, que abre a `JanelaAcaoRobo` para a pessoa decidir.
⚠️ Essa cascata **ainda não rodou contra o portal real** — ver `PENDENCIAS.md`.

Na tela: a seleção passou a fazer `reset_index`, a revisão ganhou
`JanelaEscolherPDM` (busca sobre o catálogo, com classe e características, no
lugar do `askstring` de texto livre), e uma divergência entre o PDM pedido e o
que o portal gravou passa a aparecer no log.

**O orçamento de contexto ficou no mesmo patamar** (~25 mil tokens por bloco,
contra ~23,8 mil do prompt antigo), agora com classe e característica dentro.

## ⚠️ E mudou de novo em 2026-10-08 — a escolha em duas passadas

Spec: `docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md`.
Motivo: NENHUM demais, com PDM bom no catálogo. Dois casos reais: o
`PDM.6685.017` (INDICADOR DIGITAL) de um "DISPLAY CRISTAL LIQUIDO" nem chegava
às 12 vagas da busca (só casava pela característica, peso 1,0), e o
`PDM.5930.012` (PLAQUETA INDICADORA) chegava em 1º e a IA respondia NENHUM
(a Regra B, "o fabricante restringe a família antes de qualquer outra
coisa", empurrava para válvulas).

1. **Passada 1** (`GeminiCategorizer.interpretar_lote`, tarefa `interpretar_material`):
   uma chamada por lote (fatias de 60), sem catálogo, devolve por item o que o
   material É (`e`), sinônimos e a que ele serve. Falhou → o lote segue com a
   busca de hoje e uma linha de log; nunca derruba.
2. **Busca** (`CatalogoPDM.candidatos_em_duas_frentes`): 8 vagas pela
   interpretação ("é" + sinônimos, nunca o "serve"), 4 pela descrição crua (a
   de hoje, intacta); uma frente que rende pouco cede a vaga à outra.
3. **Passada 2** (`categorizar_pdm`): cada item leva a linha "Interpretação";
   a resposta traz `confianca`, `alternativas` (`{"pdm", "motivo"}`),
   `justificativa` e `caracteristicas_que_confirmam`. NENHUM só para "PDM
   novo". Lista e exemplos vêm antes do manual (prefixo igual em todos os
   blocos, para o cache do provedor), e o título dos exemplos sai do Master
   carregado.
4. **Revisão** (`preparar_para_revisao`, no serviço — o laço saiu da tela):
   guarda contra PDM inventado, três sinais (na busca, nome base,
   características) e o rebaixamento do ALTA que nada confirma. A tela mostra
   a coluna Confiança (o NENHUM diz a causa: PDM NOVO?, SEM RESPOSTA ou FORA DO
   CATÁLOGO), ordena NENHUM → BAIXA → MÉDIA → ALTA, explica o "por quê" da
   linha selecionada e abre o seletor com o 2º e o 3º lugar no topo. No modo
   "Pular IA" nada disso aparece, e a ordem é a da planilha.
5. **Calibração**: ao confirmar a revisão, uma linha por item em
   `Documentos\SIG-FT\logs\escolha_pdm.jsonl` (o que a IA disse × o que ficou).
   Nada lê o arquivo ainda: é a matéria-prima para medir quanto ALTA acerta.

Regras puras em `sigft/services/cria_fichas_escolha.py`; a orquestração é
`GeminiCategorizer.classificar_para_revisao`.

---

## Propósito

O módulo implementa a lógica de negócio completa para criação de fichas técnicas no portal PMIB da Itaipu. Orquestra três operações: (1) leitura inteligente de planilhas Excel com detecção automática de cabeçalho e sugestão de código de projeto, (2) classificação em lote de itens usando Gemini com manual de regras customizado, e (3) automação de preenchimento de formulários via Selenium com tratamento de erros interativo.

## Entradas e Saídas

- **Entradas**:
  - Planilha STATUS_PMIB com aba "Lista de Materiais" (colunas: DESCRIÇÃO, CÓDIGO DO MATERIAL, MARCA/MODELO, UNID., opcionais)
  - Arquivo de PDMs com abas "PDMs" (coluna "PDM COMPLETO") e "Instruções PDMs" (GRUPO/CLASSE com descrições)
  - Portal PMIB (https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList) acessível via Chrome + login manual
  
- **Saídas**:
  - Excel STATUS_PMIB atualizado com colunas "CÓDIGO PMIB" (ex: 12345) e "PDM usado" (ex: PDM.1650.001 - ACUMULADOR)
  - Fichas criadas no portal PMIB com campos preenchidos: PDM, Contrato, Código Projeto, Descrição Breve, Origem, Tipo, Unidade, Fabricação
  - JSON intermediário com campos classificados pela IA: pdm_escolhido, descricao_curta, origem, tipo, tipo de fabricação, unidade

## Classes e Funções

### DataManager

Responsável por leitura/escrita de planilhas Excel com inteligência de localização automática de headers.

**`carregar_planilha_inteligente(arquivo, nome_da_aba, colunas_desejadas) → (DataFrame, str_codigo_projeto, str_erro)`**
- Lê arquivo em chunks de 30 linhas (header=None) para encontrar linha com todas as `colunas_desejadas`
- Ao localizar header row, extrai opcionalmente `codigo_projeto_sugerido` (`codigo_do_projeto_sugerido`): a célula logo **abaixo** do título "GERENCIAMENTO DOS MATERIAIS SOBRESSALENTES CADASTRADOS NO PMIB" (o template escreve "MATERIAS"; as duas grafias valem), achada pelo texto em `status_pmib_arquivos.projeto_abaixo_do_titulo`. Sem o título, o jeito antigo: a célula acima de "ITEM", pulando a linha da revisão em uso. Desde 2026-11-05: a linha acima do cabeçalho, no layout v2, é a da revisão, que ia para o campo no lugar do projeto
- Retorna tupla: (df_final com header correto, codigo_sugerido, None) ou (None, "", mensagem_erro)
- Trata: arquivo não encontrado, aba não existe, colunas não encontradas

**`atualizar_excel_final(filepath, nome_aba, lista_resultados) → (bool, str_mensagem)`**
- Recebe lista de tuplas: [(descricao_original, pmib_criado, pdm_revisao), ...]
- Localiza header row procurando em primeiras 20 linhas por células contendo ("DESCRIÇÃO", "CÓDIGO PMIB", "PDM" ou "PDM usado")
- Itera linhas a partir de header+1, faz match case-insensitive de descricao_original, escreve pmib_criado e pdm_revisao nas colunas encontradas
- Retorna (True, f"{linhas_atualizadas} linhas atualizadas.") ou (False, "Erro: arquivo aberto" / "Erro: colunas não encontradas" / erro_genérico)
- **Captura PermissionError** explicitamente para feedback de arquivo bloqueado

### GeminiCategorizer

Orquestra chamada à Gemini 3.1 Pro para classificação em lote.

**`__init__(api_key)`** — Configura cliente Gemini com `genai.configure(api_key, transport='rest')`. Se api_key vazia, aviso em stdout.

> **2026-11-05:** a `api_key` é a do Gemini (`get_key("GEMINI")`) e só é cobrada quando a IA do módulo é o **Gemini direto**: aí o aviso aparece, e `processar_lote`/`classificar_para_revisao` levantam `ValueError` ("API Key não configurada: ...") antes de chamar a IA. No OpenRouter e no Workflow AMP o lote roda sem ela; cada provedor cobra a própria credencial.

**`_formatar_itens(df) → str_texto_formatado`** — Monta bloco de texto:
```
### ITEM 1
- Descrição: ...
- Marca/Modelo: ...
- Código do Material: ...
- Unidade: ...
### ITEM 2
...
```
Trata células vazias com "NÃO ESPECIFICADA" para campos de unidade.

**`processar_lote(df_itens, lista_pdms, instrucoes) → list_de_json`**
- Formata itens via `_formatar_itens()`
- Monta prompt extenso:
  - Instruções: "Você é especialista em catalogação..."
  - Manual de Regras: conteúdo da param `instrucoes` (grupos/classes)
  - Lista de PDMs Finais: todos os PDMs disponíveis
  - 8 exemplos concretos de classificação correta (Bomba, Câmera, Switch, Cabo, etc.)
  - ITENS PARA ANALISAR: bloco formatado
  - Formato esperado: array JSON com chaves obrigatórias (item_processado, pdm_escolhido, descricao_curta, origem, tipo de fabricação, tipo, unidade)
- Chama `genai.GenerativeModel('gemini-3.1-pro-preview').generate_content(prompt_template)`
- Parse robusto: procura `[` e `]` dentro do response, limpa markers markdown (```json) se presentes
- **Retorna** list[dict] — cada dict é um item classificado
- **Levanta Exception** se JSON inválido ou API falha

### AutomacaoPMIB

Automação de preenchimento de formulário PMIB via Selenium/Chrome.

**`__init__()`** — Inicializa `self.driver = None`, `self.wait = None`.

**`iniciar_driver()`** — Cria `webdriver.Chrome()`, maximiza janela, configura `WebDriverWait(driver, 10)`.

**`abrir_portal(url)`** — Sanitiza URL (adiciona `https://` se não tiver), navega via `driver.get()`.

**`processar_item_individual(dados_item) → (status_str, retval)`**

Fluxo de preenchimento automático de ficha (resume aqui, detalhes inline no código):

1. Extrai campos: pdm, desc_curta, origem, tipo, tipo_fabricacao, cod_projeto, unidade
2. Se pdm == "NENHUM": retorna ("PULAR", ("VERIFICAR (PULADO)", "VERIFICAR (PULADO)"))
3. Clica botão "Nova Ficha" (XPath: `//*[@id="b1-Actions"]/button`)
4. Espera 5s, clica div container PDM (XPath: `//div[@data-tooltip="Pesquisar PDM"]`)
5. Pega active_element, envia keys do PDM completo + ENTER
6. Preenche Contrato via clique + TAB + ENTER (automático via OutSystems)
7. **Salvar 1** (XPath: `//*[@id="b10-b7-Button"]/button`) — primeiro save para gerar PMIB
8. Espera 6s, captura CÓDIGO PMIB (XPath: `//*[@id="b8-b1-Content"]/span`, split por espaço)
9. Preenche Código do Projeto (XPath: `//*[@id="b10-b9-TextArea_ProjectCode"]`) com click + send_keys
10. Via TABs navegados: Descrição Breve, Origem (i/n), Tipo (r/n), Unidade (lookup), Fabricação (e/s)
11. **Salvar Final** (XPath: `//*[@id="b10-b9-Form1"]/div[6]/button[1]`)
12. Captura PDM Final via CSS Selector `div.vscomp-value[data-tooltip^='PDM']` (tooltip contém PDM)
13. Navega de volta para URL: `https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList`
14. **Retorna** ("SUCESSO", (codigo_pmib, pdm_revisao)) ou ("ERRO", str_exception)

**Detalhes de navegação**:
- Usa `driver.switch_to.active_element` após cliques para capturar foco automático
- Sleeps fixos de 0.5s a 5s para sincronizar com OutSystems (frágeis)
- XPaths hardcoded ao DOM (IDs tipo `b10-b7-Button`, `b8-b1-Content` — provavelmente gerados por OutSystems)

**`atualizar_projeto_em_massa(pmib, novo_codigo_projeto) → (status_str, msg_str)`**

Edição de código de projeto em ficha já criada:

1. Navega para URL: `https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList`
2. Localiza barra de pesquisa (XPath contains `InputDatasheetFilter`), limpa com Ctrl+A + DELETE
3. Digita PMIB, ENTER
4. **Espera inteligente**: aguarda `//tr[contains(., '{pmib}')]` aparecer na tabela (garante filtro terminou)
5. Clica ícone lápis dentro da linha (XPath: `.//a[.//i[contains(@class, 'fa-pencil-square-o')]]`)
6. Localiza campo Código Projeto, clica, limpa com Ctrl+A + DELETE
7. Envia novo código
8. Clica Salvar
9. Espera 3s
10. **Retorna** ("SUCESSO", "Salvo.") ou ("ERRO", str_exception)

## Fluxo Detalhado

### Fluxo de Criação de Fichas (Frontend → Backend)

**Inicialização** (frontend:ModuloCriaFichas._ai_worker)
1. Frontend lê Excel STATUS_PMIB → `DataManager.carregar_planilha_inteligente()` retorna df + codigo_projeto_sugerido
2. Usuário seleciona itens em `JanelaSelecao`
3. Se NOT "Pular IA":
   - Frontend lê arquivo PDMs: abas "PDMs" (coluna "PDM COMPLETO") e "Instruções PDMs"
   - Monta manual de regras formatado (GRUPO/CLASSE com INCLUI/NÃO INCLUI/NOTAS)
   - Cria `GeminiCategorizer(api_key_gemini)`
   - Chama `cat.processar_lote(df_selecionado, lista_pdms, instrucoes)`
   - Recebe array JSON com fields: pdm_escolhido, descricao_curta, origem, tipo, tipo de fabricacao, unidade
4. Se "Pular IA": Frontend lê diretamente colunas do Excel (PDM, DESC_CURTA, ORIGEM, TIPO, UNIDADE, FABRICACAO) — assume dados já existem

**Revisão Pré-Automação**
- Frontend abre `JanelaRevisaoPDM(df_processed, callback)` → usuário pode editar PDMs individualmente
- Callback retorna df atualizado

**Automação PMIB**
1. Frontend thread chama `AutomacaoPMIB.iniciar_driver()` → Chrome headless/full
2. `abrir_portal('https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList')`
3. Frontend exibe `messagebox.showinfo()` pedindo login manual
4. Loop iterativo:
   - Frontend chama `self.bot.processar_item_individual(row)` para cada item
   - Backend: preenche formulário via Selenium (14 passos de navegação)
   - Retorna PMIB criado + PDM final do portal
   - Frontend: se erro, abre `JanelaAcaoRobo` para intervenção do usuário
5. Frontend: agrupa resultados → DataFrame com colunas (descricao_original, PMIB_CRIADO, PDM_COM_REVISAO)

**Salvamento no Excel**
- Frontend chama `DataManager.atualizar_excel_final(filepath, "Lista de Materiais", lista_resultados)`
- Backend: localiza colunas, faz match por descrição original, escreve PMIB + PDM
- Loop askretrycancel no frontend se arquivo bloqueado

### Exemplo Prático de Classificação (GeminiCategorizer)

**Entrada** (df com 2 itens):
```
| DESCRIÇÃO | MARCA/MODELO | CÓDIGO DO MATERIAL | UNID. |
|-----------|--------------|-------------------|-------|
| Bomba Centrifuga | KSB | 123-ABC | Unidade |
| Cabo de Transmissão | Cisco | AC-001 | metro |
```

**Prompt gerado**:
```
Você é um especialista em catalogação...

MANUAL DE REGRAS (GRUPOS E CLASSES):
### GRUPO 40: HIDRÁULICA E BOMBAS
  - CLASSE 4020: Bombas Centrifugas
    - Inclui: Bombas de até 100kW
    - Não inclui: Bombas de parafuso
### GRUPO 50: REDES E COMUNICAÇÕES
  - CLASSE 5895: Cabos
    - Inclui: Cabos de dados, cabos de potência

LISTA DE PDMS FINAIS:
- PDM.4020.001 - BOMBA CENTRIFUGA
- PDM.5895.011 - CABO, TRANSMISSAO DADOS
- ...

EXEMPLOS:
Exemplo 1: Bomba KSB 123-ABC → PDM.4020.001 - BOMBA CENTRIFUGA

ITENS PARA ANALISAR:
### ITEM 1
- Descrição: Bomba Centrifuga
- Marca/Modelo: KSB
- Código do Material: 123-ABC
- Unidade: Unidade

### ITEM 2
- Descrição: Cabo de Transmissão
- Marca/Modelo: Cisco
- Código do Material: AC-001
- Unidade: metro
```

**Resposta esperada** (JSON):
```json
[
  {
    "item_processado": 1,
    "pdm_escolhido": "PDM.4020.001 - BOMBA CENTRIFUGA",
    "descricao_curta": "BOMBA - KSB 123-ABC",
    "origem": "Importado",
    "tipo de fabricação": "Catálogo",
    "tipo": "Reparável",
    "unidade": "Unidade"
  },
  {
    "item_processado": 2,
    "pdm_escolhido": "PDM.5895.011 - CABO, TRANSMISSAO DADOS",
    "descricao_curta": "CABO DADOS - AC-001",
    "origem": "Importado",
    "tipo de fabricação": "Catálogo",
    "tipo": "Não Reparável",
    "unidade": "metro - (m)"
  }
]
```

### Exemplo de Preenchimento PMIB

Item: pdm_escolhido="PDM.4020.001 - BOMBA CENTRIFUGA", codigo_projeto="SERV. AUX / CAP.5", ...

**Passo-a-passo Selenium**:
1. Clique botão "Nova Ficha" → modal abre
2. Clique div "Pesquisar PDM" → input ganha foco automático
3. Send: "PDM.4020.001 - BOMBA CENTRIFUGA" + ENTER → dropdown selection
4. Clique "Contrato" → TAB → ENTER (auto-seleciona primeiro)
5. Save 1 → server gera PMIB, ex: "12345"
6. Espera 6s, captura "12345" de elemento HTML
7. Clique "Código Projeto", clear, send "SERV. AUX / CAP.5"
8. TAB → send "BOMBA - KSB 123-ABC" (descrição curta)
9. TAB, TAB, TAB → send "i" (Importado) + ENTER
10. TAB → send "r" (Reparável) + ENTER
11. TAB → ENTER (dropdown abre), send "un" (Unidade) + ENTER
12. TAB x5 → send "e" (Especial) + ENTER
13. Save Final → portal retorna PDM revisado, ex: "PDM.4020.001 - BOMBA CENTRIFUGA (REVISADA)"
14. Captura via tooltip → retorna ("SUCESSO", ("12345", "PDM.4020.001 - BOMBA CENTRIFUGA (REVISADA)"))

## Integrações

- **Com frontend.py**:
  - `ModuloCriaFichas` (linhas ~443) instancia `DataManager`, `GeminiCategorizer`, `AutomacaoPMIB`
  - Frontend chama `DataManager.carregar_planilha_inteligente()` no evento "Selecionar Excel"
  - Frontend chama `GeminiCategorizer.processar_lote()` no evento "Analisar (IA)" em thread
  - Frontend chama `AutomacaoPMIB.processar_item_individual()` em loop thread da automação

- **Com arquivo externo**: `upload_ficha_duplicada.py` (importado como `backend` no frontend linha 33)

- **Com Portal PMIB**: Selenium Chrome driver comunica com https://apps.itaipu.gov.br/PMIB via OutSystems (IDs HTML dinâmicos, XPaths frágeis)

- **Com Gemini API**: Chaves via .env (`API_GEMINI_LUAN_GMAIL`) ou `api_config.json`, chamada REST via `google.generativeai` SDK

## Pontos de Atenção

- **Sleeps fixos em Selenium**: `time.sleep(1.5)` após clique (linha 286), `time.sleep(5)` após save 1 (linha 291), `time.sleep(0.5)` entre TABs. Frágil a latência variável; OutSystems renderização não é determinística. Melhor usar `WebDriverWait + expected_conditions`.

- **XPaths hardcoded**: IDs tipo `b10-b7-Button`, `b8-b1-Content`, `b10-b9-TextArea_ProjectCode` — provavelmente gerados dinamicamente por OutSystems. Mudança no portal quebra automação sem aviso.

- **active_element sem verificação**: Linha 300 `self.driver.switch_to.active_element` assume que foco mudou após clique. Se não mudar (ex: erro de rede), envia keys para lugar errado.

- **Parse JSON frágil**: Linha 238-246 procura `[` e `]` dentro do response, remove ```json markers. Se Gemini retornar JSON com caracteres de escape incorretos ou wrap, falha silenciosa → lista vazia retornada.

- **Except broad em AutomacaoPMIB**: `except Exception as e: return "ERRO", str(e)` captura tudo, não faz logging de stack trace. Frontend apenas exibe string de erro curta; dificulta debug de Selenium.

- **Numero magico 6s**: Linha 322 `time.sleep(6)` para "cobrir latência da 1ª ficha" — comentário sugere empirismo. Primeira ficha é mais lenta que subsequentes; sleep deveria escalar ou ser removido em favor de WebDriverWait.

- **Permissão e exceção implícita**: Linha 100-103 captura `PermissionError` explicitamente, mas linha 102 trata genérico com `f"Erro ao salvar: {e}"`. Se for erro de escrita (disco cheio), mensagem genérica confunde usuário.

- **Regex em atualizar_projeto_em_massa**: Linha 432 XPath com `.contains(., '{pmib}')` assume PMIB está no texto visível da linha. Se PMIB é renderizado dynamicamente em JavaScript, XPath não acha.

- **Coluna "PDM usado" vs "PDM"**: Linha 74-75 detecta ambos (`"PDM USADO" or val_str == "PDM"`). Se coluna for "PDM (REVISADO)" ou variante, não acha → mensagem "coluna não encontrada".

- **Descrição original case-sensitive**: Linha 86-91 faz `str(desc_original).strip() == str(cell_desc).strip()`. Se original é "Bomba KSB" e Excel tem "BOMBA KSB", match falha → linha não atualizada.

- **Unidade não mapeada**: Linha 367-374 lookup de unidade; se valor recebido da IA for "Quilograma" (não listado), cai no default "un". Sem erro ou log.

- **Gemini model hardcoded**: Linha 131 `genai.GenerativeModel('gemini-3.1-pro-preview')` — modelo pode deprecar ou mudar custo. Melhor config centralizável em `api_config.json`.

- **Falta de context para Gemini**: Prompt não inclui exemplos de items que NÃO devem ser selecionados (negative examples). Classificação pode ter falsos positivos.

- **Sem timeout de Selenium**: `WebDriverWait(driver, 10)` timeout padrão 10s pode não ser suficiente em conexões lentas. Sem configuração de retry ou backoff exponencial.
