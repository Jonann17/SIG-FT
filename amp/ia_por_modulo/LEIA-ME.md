# IA por módulo pelo AMP (n8n)

O modo **Workflow AMP** de uma tela: em vez do OpenRouter, a IA daquela tela é um agente do AMP,
chamado por um workflow do n8n. A escolha é por tarefa, no botão **Configurar IA** da tela (ou na
janela **Modelos de IA**, na engrenagem da Home; o AutoSpec, que não tem o botão, só por ela). A IA
Externa continua lá: trocar de modo é um clique, nos dois sentidos.

**Diferente da revisão das listas:** aqui o SIG-FT manda o **prompt inteiro**, o mesmo que vai ao
OpenRouter (`sigft/core/llm/prompts.py`). O agente de cada módulo tem só um system prompt curto
(quem ele é e "responda só o JSON"), e as regras continuam num lugar só, no SIG-FT. Melhorar a
resposta é mudar o prompt no SIG-FT, e as duas IAs ganham juntas.

| Arquivo | O quê |
|---|---|
| `gerar_workflow.py` | gera o `.json` de cada módulo: `python amp/ia_por_modulo/gerar_workflow.py` |
| `<módulo>/agente.md` | a cópia do agente no AMP: nome, descrição, goal e system prompt |
| `<módulo>/workflow_<módulo>.json` | o workflow para importar ou colar no n8n. Não edite à mão: rode o gerador |

Módulos prontos:
- **Cria Fichas** (`cria_fichas/`): testado na GE em 2026-11-05, as duas passadas;
- **AutoSpec** (`autospec/`): leva os documentos ao agente; precisa de uma versão **depois da
  1.4.0-rc.2** (a que traz, nas novidades, "AutoSpec: pode rodar no Workflow AMP").

Um módulo por vez, cada um testado antes do seguinte (decisão do Luan, 2026-11-05).

## Contrato (o que o SIG-FT manda e o que espera)

O SIG-FT (`sigft/core/llm/providers/amp_workflow.py`) faz um POST com o cabeçalho `X-SIGFT-Chave`:
- antes do primeiro pedido, o **ping**: `{"modo": "ping"}`, que responde sem chamar o agente;
- cada pedido, em formulário: `modo=ia`, `tarefa` (ex.: `categorizar_pdm`), `prompt`, `system`
  (quando há) e `json=sim` (quando a tarefa espera JSON);
- quando a tarefa leva documentos (o AutoSpec), também os arquivos `anexo_1`, `anexo_2`... e o
  campo `arquivos`, com quantos são.

O workflow junta `system` e `prompt` no `chatInput` (o AMP Agent só lê esse campo), chama o agente
e devolve `{"ok": true, "modo": "ia", "tarefa": ..., "texto": "<a resposta>", "json_valido": ...,
"execucao": ...}`. Se a resposta deve ser JSON, o nó **Prepara a resposta** recorta o JSON do meio da
narração do agente (texto antes, ```json em volta). Sem JSON válido, vai o texto todo e
`json_valido: false`: o SIG-FT ainda tenta a leitura tolerante.

Com documentos, o workflow confere que todos chegaram antes de chamar o agente, e a resposta diz
quantos ele recebeu (`arquivos_recebidos`). Sem essa conta, ou com menos arquivos do que foram, o
SIG-FT não aceita a resposta: o agente respondeu sem ver os documentos.

**Sem repetição:** o SIG-FT não repete um pedido que falhou, porque cada repetição seria outra
execução do agente no AMP.

## Ligar o Cria Fichas (uma vez)

### 1. O agente, no AMP

1. Crie o agente com o texto de `cria_fichas/agente.md`: **Agent Name**, **Description**,
   **Customized Goal**, **Tone** `professional` e **System Prompt**.
2. **Data sources:** nenhum.
3. Não use o **Add Optimized Query**: ele reescreve o prompt e pode amolecer "não invente".

### 2. O workflow, no n8n (`https://ampworkflow.gevernova.net`)

1. **Importar:** **Create workflow** → menu **⋯** → **Import from File...** →
   `cria_fichas/workflow_cria_fichas.json` (ou copie o conteúdo e cole no canvas vazio com **Ctrl+V**).
2. **Credencial:** no nó **Webhook do SIG-FT**, em *Credential for Header Auth*, **Create new**:
   - **Name:** `X-SIGFT-Chave`;
   - **Value:** um valor longo e aleatório (40 letras e números, por exemplo), **diferente** do dos
     workflows das listas. Guarde: ele vai no SIG-FT no passo 3.
3. **O agente:** no nó **AMP Agent**, escolha **Spare Parts PDM Classifier** na lista (se não
   aparecer, recarregue a página; **By ID** é a saída), confira a credencial do AMP e, em
   **Add option** → **Timeout**, ponha o máximo.
4. **Publicar:** salve e publique.
5. **Endereço:** no nó **Webhook do SIG-FT**, aba **Production URL** (não a *Test URL*). Ele termina
   em `/webhook/sigft-ia-cria-fichas`.

### 3. No SIG-FT

1. **Cria Fichas** → **Configurar IA**. A tela tem duas tarefas:
   - **Interpretar material** (passada 1);
   - **Categorizar PDM**.
2. Em **cada uma**, escolha **Workflow AMP** e preencha o **mesmo** endereço e a **mesma** chave.
   Dá para ligar só uma e deixar a outra na IA Externa (por exemplo, testar primeiro só a
   interpretação, que é mais curta).

## Testar o Cria Fichas

1. Comece com um **lote pequeno** (3 a 5 itens). Cada bloco de 15 itens do *Categorizar PDM* leva
   a lista inteira de PDMs (cerca de 1.200) e o manual podado, ou seja, dezenas de milhares de
   caracteres por chamada. Ainda não sabemos o limite do AMP para uma mensagem desse tamanho.
2. Compare com a IA Externa: rode o mesmo lote nos dois modos e confira a revisão.
3. Se algo falhar, o console mostra o erro do workflow; com o número da execução, o n8n mostra o
   que o agente respondeu (nó **Prepara a resposta**: o `texto` e o `json_valido`).
4. O tempo de cada chamada aparece no n8n, em **Executions** (o console não mostra). Um lote de
   63 itens são 2 chamadas de interpretação (60 itens por chamada) e 5 de categorização (15 por
   bloco): 7 execuções no n8n.

### As duas chamadas do Cria Fichas

O botão da IA faz duas passadas, uma depois da outra, e as duas vão ao mesmo workflow e ao mesmo
agente. O campo `tarefa` diz qual é qual, e o prompt de cada uma traz as próprias instruções.

**Por que um agente só:** o agente não guarda as instruções de nenhuma das passadas. Elas chegam no
prompt de cada pedido. Se as instruções morassem no AMP, como na revisão das listas, seriam dois
agentes, um por passada. Quem orquestra é o SIG-FT, e cada chamada é uma execução nova do mesmo
workflow, como cada lista marcada na Revisão no AMP:

```text
SIG-FT                                                   workflow (n8n) -> agente (AMP)
1. "o que é cada item?"  (interpretar_material, até 60 itens)   -> execução 1 -> JSON
2. busca no catálogo de PDMs com essas palavras  (no SIG-FT, sem IA)
3. "qual o PDM dos itens 1 a 15?"  (categorizar_pdm)           -> execução 2 -> JSON
4. o passo 3 de novo, para os itens 16 a 30, 31 a 45...         -> execuções 3, 4...
5. a janela de Revisão abre com tudo
```

Cada chamada espera a resposta da anterior e leva tudo de que o agente precisa: ele não depende de
lembrar do pedido anterior. Dois agentes continuam possíveis (um modelo diferente em cada passada,
ou o uso de cada uma separado no AMP): outro agente, outro workflow e outro endereço na tarefa, no
**Configurar IA**. O SIG-FT já aceita um endereço por tarefa.

| | 1ª: *Interpretar material* | 2ª: *Categorizar PDM* |
|---|---|---|
| O que pede | o que cada material É, em palavras de catálogo, sem código | o PDM de cada item, entre os candidatos |
| Itens por chamada | até 60 | 15 |
| Tamanho | curto: só os itens | grande: os itens, os candidatos, a lista de ~1.200 PDMs e o manual |
| Se falhar | o lote **segue**, só com a busca por palavras (o console avisa) | o lote **para** ("Erro no processamento: Erro na IA: ..."), e os blocos que já voltaram se perdem |

Por isso, a ordem de teste mais segura é ligar primeiro só a *Interpretar material* no Workflow
AMP: uma falha dela não derruba o lote.

## Ligar o AutoSpec (uma vez)

Precisa de uma versão **depois da 1.4.0-rc.2**, a que traz nas novidades "AutoSpec: pode rodar no
Workflow AMP": é nela que o Workflow AMP passa a levar os documentos ao agente. Antes dela, o AutoSpec
no Workflow AMP mandaria só o texto e perderia as páginas escaneadas.

1. **O agente, no AMP:** crie o **Spare Parts Datasheet Reader** com o texto de `autospec/agente.md`,
   como o do Cria Fichas (sem data source e sem *Add Optimized Query*).
2. **O workflow, no n8n:** os mesmos passos do Cria Fichas, com `autospec/workflow_autospec.json`:
   importe, crie a credencial `X-SIGFT-Chave` com um valor **novo**, escolha o agente no nó **AMP
   Agent** com o **Timeout** no máximo (ele lê PDFs inteiros: pode levar minutos), publique e copie a
   **Production URL**, que termina em `/webhook/sigft-ia-autospec`. Não mexa no **Monta a mensagem**:
   ele já vem com *Include Other Input Fields* ligado, que é o que leva os arquivos ao agente.
3. **No SIG-FT:** a tela do AutoSpec não tem o botão **Configurar IA**. Vá na engrenagem da Home →
   **Modelos de IA** → na lista "IA por módulo", **AutoSpec (RAG)** → **Workflow AMP**, e preencha o
   endereço e a chave.

### Como o AutoSpec usa o workflow

- Cada ficha faz uma chamada para **preencher** os campos vazios. Se a ficha tem respostas do
  fornecedor e a opção "Conferir as respostas do fornecedor" está ligada, faz outra para
  **conferi-las**. As duas vão ao mesmo workflow e ao mesmo agente.
- Os PDFs da ficha vão **como arquivo**, até 15 MB e 500 páginas somados por chamada; o que passar
  disso vai como texto. As páginas escaneadas vão como imagem (até 8 por ficha). O agente lê o PDF
  inteiro, como no chat do AMP.
- Se faltar arquivo no caminho, a ficha é refeita com o texto extraído dos documentos, o mesmo
  caminho de quando um provedor recusa o PDF, e o console avisa ("O provedor recusou o(s) PDF(s)
  anexado(s)...").
- O AutoSpec guarda a resposta de cada ficha: rodar o mesmo lote de novo no mesmo modo não chama o
  agente de novo. A IA Externa e o Workflow AMP guardam separado.

### Testar o AutoSpec

1. Uma ou duas fichas que tenham o PDF do fabricante na pasta.
2. No console, a linha **"A IA vai ler N documento(s) no proprio PDF (...)"** mostra que o PDF foi
   como arquivo.
3. No n8n, em **Executions**, o nó **Prepara a resposta** mostra o `arquivos_recebidos` e o `texto`.
4. Compare com as mesmas fichas pela IA Externa (se já rodaram nela, a resposta guardada volta sem
   custo).

## Se der errado

| Sintoma | Onde olhar |
|---|---|
| "o endereço do webhook não foi configurado" | **Configurar IA** da tela: a tarefa está no Workflow AMP sem endereço |
| "API Key não configurada." | o Cria Fichas ainda pede a chave da IA Externa mesmo no Workflow AMP: preencha a chave (vale até a correção no SIG-FT) |
| "Sem conexão com o AMP" | a rede da máquina precisa alcançar `ampworkflow.gevernova.net` |
| HTTP 401 ou 403 | a chave do **Configurar IA** é diferente da credencial `X-SIGFT-Chave` do workflow |
| HTTP 404 | o workflow não está publicado, ou o endereço é a Test URL (`/webhook-test/`) |
| HTTP 400, etapa `prompt` | o pedido chegou sem prompt: veja o nó **Webhook do SIG-FT** na execução |
| HTTP 502, etapa `agente` | o agente falhou (mensagem grande demais? timeout?): veja a execução no n8n |
| "a resposta veio sem o campo texto" / JSON inválido | veja o `texto` da execução, no nó **Prepara a resposta**, e aperte o system prompt no AMP |
| AutoSpec: "o workflow não confirmou que recebeu os arquivos anexados" | o endereço do AutoSpec é o de outro workflow (o do Cria Fichas não leva arquivos): use o que termina em `/webhook/sigft-ia-autospec` |
| AutoSpec: "recebeu X de N arquivo(s)", ou HTTP 400, etapa `arquivos` | algum arquivo se perdeu: veja a aba Binary do **Webhook do SIG-FT** na execução, e se o **Monta a mensagem** tem *Include Other Input Fields* |
| AutoSpec: HTTP 413 | os documentos passaram do limite de tamanho do n8n: a ficha é refeita com o texto, sozinha |

Com o número da execução (`execucao`), o n8n mostra em que nó ela parou (menu **Executions**).

## Módulo novo

1. Em `gerar_workflow.py`, acrescente o módulo em `MODULOS` (título, caminho do webhook, nome do
   agente, tarefas da tela, onde se escolhe o modo, `sempre_json` e `com_arquivos`, se a tarefa
   manda documentos) e rode o gerador.
2. Crie `<módulo>/agente.md` no molde do `cria_fichas/agente.md`: o system prompt é curto, e as
   regras ficam no prompt do SIG-FT.
3. `tests/test_amp_workflow_ia_por_modulo.py` já cobre o módulo novo: o `.json` igual ao gerador,
   o contrato e os ids sem repetição.
