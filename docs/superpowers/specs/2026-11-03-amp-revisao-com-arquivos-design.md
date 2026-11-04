# Peça 2, versão 2: a revisão das listas pelo agente do AMP, com os arquivos

**Data:** 2026-11-03. **Origem:** a conversa de 03/11 com o Luan, em que ele corrigiu o desenho de
27/10 e validou, no n8n da GE, cada parte do caminho novo (§2). **Aprovado pelo Luan em 03/11:**
- o caminho (§4);
- o que muda no SIG-FT (§5);
- o webhook dentro de cada módulo, por um botão que abre uma janela (§5.5);
- o foco nos logs (§5.6).

**O que este desenho substitui** em `2026-10-27-amp-revisao-de-listas-design.md`:
- a §3, passo 2 (o agente montado dentro do workflow);
- a §4 (texto em JSON);
- a §5 (o pedido embutido no workflow);
- a §6 (o workflow);
- o `eco` da §7 e da §9;
- a leitura do PDF da §10.

**O que continua valendo de lá:**
- o porquê (§1) e os antiobjetivos (§2);
- quais listas e quais arquivos vão (§7, "Quais listas", e §10);
- a gravação do HTML sem sobrescrever (§7);
- o ritmo: uma lista por vez, 15 min de limite, "Parar" entre as listas (§7).

As decisões marcadas *(minha decisão)* são de quem escreveu este desenho, não do Luan.

## 1. Por que uma versão 2

O Luan corrigiu dois pontos do desenho de 27/10. Os dois tinham sido decisões tomadas sem conhecer o
AMP por dentro:

1. **O agente é criado no AMP e o workflow só o chama**, pelo nó **AMP Agent**. O desenho de 27/10
   montava o agente dentro do workflow (*Basic LLM Chain* com o GEV LLM Model ligado à mão).
2. **O agente recebe os arquivos como estão:** o PDF da revisão em uso, o da revisão atual e o
   `_STATUS_PMIB.xlsx`. É o que o Luan fazia no chat do AMP, e foi o que deu certo. O desenho de 27/10
   mandava o texto extraído, em JSON. A extração embaralha a tabela do PDF e perde a estrutura do Excel.

O que o agente devolve: o que mudou entre as revisões e as ações no controle, linha a linha. As ações
são criar, excluir (mover para a `SEM_LISTA_STATUS_PMIB`) e substituir.

## 2. O que os testes na GE provaram (03/11)

| Teste | Montagem no n8n | Resultado |
|---|---|---|
| 1 | Manual Trigger → AMP Agent | Erro: *"Prompt is empty. Provide a prompt value or pass chatInput from an On chat message node."* O nó lê a mensagem do campo `chatInput` do item que chega. |
| 2 | Manual Trigger → Edit Fields (`chatInput`) → AMP Agent | O agente responde pelo goal e pelo system prompt. A saída tem `sessionId`, `output` (o texto) e `files` (vazio). |
| 3 | Chat (*Allow File Uploads*) → AMP Agent, com os 3 arquivos | O agente lê os dois PDFs e a planilha e devolve o HTML pedido. Levou 3 min 13 s. |
| 4 | Webhook (multipart, `curl.exe`) → Edit Fields → AMP Agent → Respond to Webhook | Os arquivos chegam ao Webhook (1,85 MB), mas o Edit Fields só os leva adiante com *Include Other Input Fields = All*. Com isso, o resultado é o mesmo do teste 3. |
| Produção | O workflow da §4, pela Production URL, com a chave | Voltou com o HTML. A chamada esperou o agente terminar, que leva minutos, e a rede da GE não a cortou, embora o n8n fique atrás de um balanceador da Amazon (`x-amzn-trace-id`). |

Também se viu:
- **Cada execução é uma conversa nova.** O `sessionId` mudou a cada teste, então uma lista não se
  mistura com a anterior.
- **Os códigos voltaram intactos**, por exemplo `4500063671.0715` e `CA10-A722.600.FT2`. O eco de
  27/10 existia para pegar mascaramento no texto extraído. Agora o agente lê o arquivo original, e o
  eco sai (§5.1).
- **O agente narra antes do HTML** ("Vou carregar a planilha e indexar os PDFs."), mesmo instruído a
  não fazer. Ele também escreve `100\%` no CSS. O workflow corrige as duas coisas (§4).
- **Sem os arquivos, o agente não inventa:** devolve um HTML que diz "Não foi possível fazer a
  revisão". Isso é bom, mas o SIG-FT gravaria essa página como se fosse uma revisão. Por isso o
  workflow confere os arquivos antes de chamar o agente (§4).
- **O conteúdo da revisão ainda não está bom para o Luan.** Melhorar o system prompt é a próxima
  frente, no AMP, depois desta peça (§8).

## 3. O agente no AMP

- **Nome:** Spare Parts Document Reviewer.
- **Modelo:** `bedrock-claude-sonnet-5.5`. **Tom:** professional.
- **Data sources:** nenhum. Os arquivos chegam a cada pedido.
- **Goal e system prompt:** a cópia fica em `amp/revisao_de_listas/agente.md`.

**A fonte é o AMP** (Luan, 03/11: "qualquer melhoria do agente deve acontecer no AMP"). Melhora-se o
agente lá, e depois a cópia do repositório é atualizada à mão, para o `git log` mostrar o que mudou e
quando. O `pedido.md` sai, porque o workflow não leva mais pedido. A primeira cópia é feita a partir do
texto que está hoje no AMP, colado pelo Luan.

## 4. O workflow do n8n

É o workflow colado no n8n da GE em 03/11. O `gerar_workflow.py` passa a produzir exatamente ele, e o
`tests/test_amp_workflow.py` continua travando que o `.json` versionado é o que o gerador produz.

| Nó | Tipo | O quê |
|---|---|---|
| Webhook do SIG-FT | Webhook (POST, `sigft-revisao-listas`) | Header Auth `X-SIGFT-Chave`; resposta por nó |
| É ping? | If | `modo = ping` responde sem chamar o agente |
| Responde ping | Respond to Webhook | `{ok, modo, versao_workflow, execucao}` |
| Monta a mensagem | Edit Fields | `chatInput = body.mensagem`, levando os outros campos (e com eles os arquivos) |
| Chegaram os arquivos? | If | menos de 2 arquivos: não chama o agente |
| Responde sem arquivos | Respond to Webhook (400) | `etapa: arquivos` e quantos chegaram |
| AMP Agent | AMP Agent (*Spare Parts Document Reviewer*) | saída de erro ligada |
| Prepara a resposta | Code | corta o que vem antes do `<!DOCTYPE` e depois do `</html>`; troca `\%` por `%`; `ok` falso se não veio HTML; lista os arquivos recebidos |
| Responde | Respond to Webhook | o objeto `resposta` |
| Responde erro | Respond to Webhook (502) | `etapa: agente`, o erro e a execução |
| Como ligar | nota | o passo a passo de uma vez só |

**O pedido** é `multipart/form-data`, com a chave no cabeçalho `X-SIGFT-Chave`:

| Campo | O quê |
|---|---|
| `modo` | `revisar`. O `ping` pode vir assim ou em JSON (`{"modo": "ping"}`), que é como o SIG-FT 1.3.2 já manda. |
| `mensagem` | o texto da §5.2 |
| `revisao_em_uso` | o PDF; só quando a lista tem revisão em uso |
| `revisao_atual` | o PDF |
| `status_pmib` | o `.xlsx` |

**A resposta:**

| Caso | HTTP | Corpo |
|---|---|---|
| ping | 200 | `{ok: true, modo: "ping", versao_workflow, execucao}` |
| HTML pronto | 200 | `{ok: true, modo: "revisar", html, arquivos, versao_workflow, execucao}` |
| o agente não devolveu HTML | 200 | o mesmo, com `ok: false` e `erro` |
| menos de 2 arquivos | 400 | `{ok: false, etapa: "arquivos", erro, versao_workflow, execucao}` |
| o agente falhou | 502 | `{ok: false, etapa: "agente", erro, versao_workflow, execucao}` |
| chave errada | 401 ou 403 | do próprio n8n |
| workflow não publicado | 404 | do próprio n8n |

`arquivos` é a lista dos nomes de arquivo que chegaram ao agente. `versao_workflow` é `2026-11-03`.

**O que é da instância da GE:** o `agentId` e a credencial do AMP Agent (`AMP account 1859`) vão no
arquivo como estão no n8n da GE. Numa outra instância, escolhem-se de novo no nó.

**Timeout do AMP Agent.** O valor é posto à mão, no máximo, como diz o LEIA-ME. Ele entra no gerador
quando se souber o nome e a unidade do parâmetro: o Luan copia o nó com o Timeout posto *(pendente)*.

## 5. No SIG-FT

### 5.1 A aba Revisão no AMP

- **As listas aparecem antes de mandar.** Ao abrir a aba, se há uma conferência que a tabela ainda
  não mostra, o SIG-FT levanta as listas e os arquivos (`listas_para_amp`, numa tarefa em segundo
  plano, como hoje) e enche a tabela. Hoje a tabela só se enche depois do clique em Revisar.
- **Cada lista tem uma caixa de marcar**, na coluna do código. As listas vêm **todas marcadas**, e o
  Luan desmarca as que não quer (Luan, 03/11).
- **A lista com falta** (sem `_STATUS_PMIB`, sem o PDF da revisão atual ou sem o da revisão em uso)
  aparece sem caixa, com a falta escrita na coluna AMP.
- **Marcar todas** e **Desmarcar todas** valem só para as listas que podem ir.
- **Revisar no AMP** manda só as marcadas, na ordem da tabela, uma por vez. Sem nenhuma marcada, o
  SIG-FT avisa e não chama nada. Durante a rodada, as caixas ficam travadas.
- **Ao fim da rodada, as listas com HTML pronto são desmarcadas.** Um segundo clique manda só as que
  falharam ou pararam *(minha decisão)*.
- **Conferência nova:** a tabela é refeita, e as listas vêm todas marcadas de novo. Se o clique em
  Revisar encontrar a tabela com uma conferência mais velha que a última, ela é refeita e nada é
  mandado: o SIG-FT pede para conferir as marcas e clicar de novo. Com a Conferência ainda rodando, o
  aviso é o de hoje.
- **Testar conexão com o AMP** faz só o `ping`. O eco sai do cliente, do serviço e da tela.
- **O botão Webhook…** abre a janela do endereço e da chave deste workflow (§5.5).
- **Ficam como estão:** "Copiar diagnóstico", "Parar", a coluna AMP e os dois cliques que abrem o
  HTML.

### 5.2 O pedido de cada lista

Os arquivos vão como estão na pasta da lista, cada um com o próprio nome. São os mesmos arquivos que o
SIG-FT já escolhe hoje (§10 do desenho de 27/10).

O SIG-FT monta a mensagem sozinho, com o que a conferência já sabe. É o mesmo texto do teste de 03/11:

```text
Lista: <código>. Revisão em uso: <rev> (arquivo <nome do PDF>). Revisão atual: <rev> (arquivo
<nome do PDF>). Controle: <nome do _STATUS_PMIB>. Data de hoje: <dd/mm/aaaa>. Faça a revisão.
```

Sem revisão em uso, vão só dois arquivos, e o trecho da revisão em uso fica assim: `Revisão em uso:
nenhuma (a lista ainda não tem revisão em uso: compare só a revisão atual com o controle).`

**O SIG-FT não lê mais o conteúdo dos arquivos.** Saem a extração do texto do PDF (`texto_do_pdf`, com
o PyMuPDF), a planilha em texto separado por tabulação (`status_pmib_em_tsv`) e o pedido em JSON
(`montar_pedido`). Com isso, o PDF que é só imagem deixa de ser barrado no SIG-FT: ele vai ao agente,
e o agente diz o que não conseguiu ler *(minha decisão)*.

### 5.3 A chamada

- **`ClienteAmp.enviar(campos, arquivos)`** manda o POST multipart pela rota que o `ping` achou, uma
  vez só, com 15 min de limite, como hoje. Na primeira vez, o `ping` vai antes, também como hoje. Os
  arquivos são abertos na hora de mandar e fechados em seguida. O cliente não sabe o que é uma lista
  (§5.5): quem monta os campos e escolhe os arquivos é o serviço da revisão.
- **O `ping` continua em JSON.** O workflow novo o entende, e o SIG-FT 1.3.2 já passa no "Testar
  conexão".
- **A resposta é conferida como hoje:** `ok` verdadeiro e HTML presente. Há uma conferência a mais:
  se o workflow listar menos arquivos recebidos do que os mandados, a lista falha com "o workflow
  recebeu N de M arquivos" *(minha decisão)*.
- **O HTML é gravado como hoje:** `<código>[<em uso>-<atual>] revisao AMP.html`, na pasta da lista,
  sem sobrescrever.

### 5.4 O diagnóstico

- **O que foi mandado:** o nome e o tamanho de cada arquivo e o tamanho da mensagem.
- **A resposta, como hoje:** o HTTP, o tempo, a execução do n8n, o erro e o corpo com só os campos do
  workflow. O `arquivos` passa a ser um desses campos. O `html` continua fora: vai só o tamanho.
- **Sai a limpeza de trechos do documento** (`_trechos_do_documento` e `_sem_trechos`). O SIG-FT não
  extrai mais texto, então não há trecho para procurar. A regra continua a mesma: o diagnóstico nunca
  leva conteúdo de documento. O conteúdo só existe no `html`, que fica de fora.
- **"Onde está o código"** passa a apontar para `agente.md` e para este desenho.

### 5.5 O webhook de cada módulo

O Luan, em 03/11: o endereço e a chave ficam **dentro de cada módulo**. Este é o workflow da revisão
de listas, e outros workflows virão para chamar outros agentes, cada um com o seu par.

- **Na aba:** a linha de hoje continua mostrando `Webhook do AMP: <endereço> · chave posta` (ou
  `sem chave`, ou "não configurado"). Ao lado dos botões entra **Webhook…**, que abre uma janela
  pequena com:
  - **Endereço:** a Production URL do workflow;
  - **Chave:** o valor da credencial `X-SIGFT-Chave`, mascarado;
  - **Salvar** e **Cancelar**.
- **A janela confere o endereço antes de salvar** *(minha decisão)*:
  - se não começar por `https://`, ela avisa e não salva;
  - se tiver `/webhook-test/`, ela avisa que esse é o endereço de teste, que só funciona com o n8n
    escutando, e pede a Production URL. Foi o 404 do teste 4.
- **Onde fica guardado:** no mesmo `Documentos\SIG-FT\api_config.json` das outras chaves, com nomes
  deste workflow: `AMP_REVISAO_LISTAS_URL` e `AMP_REVISAO_LISTAS_CHAVE`. Um módulo futuro usa o seu
  próprio par, sem tocar neste.
- **Configuração → Chaves de API perde os dois campos do AMP** (`AMP Webhook (URL)` e
  `AMP Webhook (chave)`).
- **O que já foi configurado não se perde.** Se os nomes antigos (`AMP_WEBHOOK_URL` e
  `AMP_WEBHOOK_CHAVE`) tiverem valor e os do módulo estiverem vazios, a aba adota os valores antigos e
  os grava nos nomes novos, uma vez só.
- **A chave nunca aparece:** nem no console, nem no log em arquivo, nem no diagnóstico. Só se diz se
  está posta.
- **Peças reaproveitáveis**, para os próximos módulos:
  - a janela do webhook, que recebe o título e os dois nomes de chave;
  - o `ClienteAmp`, que só sabe fazer o `ping` e o `enviar(campos, arquivos)`.

  O que é da revisão de listas (a mensagem, os três arquivos, o HTML) fica no serviço dela,
  `services/revisao_amp.py`.

### 5.6 Os logs: ver o que está acontecendo

O Luan, em 03/11: "uma coisa que devemos focar muito bem é nos logs, precisamos ver o que está
acontecendo". O agente leva minutos por lista, e hoje o console fica mudo enquanto ele trabalha.

**No console**, uma rodada se lê assim (exemplo):

```text
Revisão no AMP: 3 lista(s) marcada(s) de 5; ficaram fora 2: #AAA, #BBB
Webhook: https://ampworkflow.gevernova.net/webhook/sigft-revisao-listas · chave posta
Log desta rodada: Documentos\SIG-FT\logs\amp\amp_revisao_2026-11-03_14-32-05.log
Ping: workflow 2026-11-03 (0,8 s, execução 369100)
[1/3] #ST00=B04BMA10TB020&EPB020 · em uso 0C → atual 0
    vai: #ST00=…[0C].pdf (412 KB), #ST00=…[0].pdf (455 KB), #ST00=…_STATUS_PMIB.xlsx (980 KB)
    enviado; o agente está lendo (costuma levar alguns minutos)
    … 0:30 esperando o AMP
    … 1:00 esperando o AMP
    resposta: HTTP 200 em 3:12 · execução 369101 · o workflow recebeu 3 arquivo(s)
    ✓ HTML gravado: #ST00=B04BMA10TB020&EPB020[0C-0] revisao AMP.html (48 KB)
[2/3] #CCC · em uso 0A → atual 0B
    ✗ falhou: HTTP 502 (etapa agente): <erro do workflow> · execução 369102
    diagnóstico em Documentos\SIG-FT\logs\amp\20261103-143910 #CCC.txt
[3/3] #DDD · em uso 0 → atual 1
    - falta: PDF da revisão atual
Fim: 1 HTML pronto, 1 falha, 1 com falta, 0 parada(s), em 7:40
```

As regras desse log:
- **Cada lista diz o que vai** (o nome e o tamanho de cada arquivo) e **o que voltou**: o HTTP, o
  tempo, o **número da execução do n8n** e quantos arquivos o workflow recebeu. O número da execução
  vai também nas que deram certo: com ele se acha a execução no n8n, no menu Executions.
- **A espera tem batimento:** uma linha a cada 30 s enquanto o AMP não responde. Assim se vê que o
  SIG-FT não travou *(minha decisão)*.
- **O começo diz o que vai e o que fica de fora:** as marcadas, as desmarcadas e onde está o log em
  arquivo. O fim faz a conta e diz o tempo total.
- **O Testar conexão** escreve o endereço, se a chave está posta, e o resultado do `ping` com o HTTP,
  o tempo e a execução.
- **Salvar o webhook** escreve `Webhook da Revisão no AMP salvo: <endereço> · chave posta`.
- **A aba, ao se encher,** escreve quantas listas a conferência trouxe, quantas podem ir e quantas
  têm falta.

**Em arquivo:** cada rodada e cada teste de conexão gravam as mesmas linhas, com a hora, em
`Documentos\SIG-FT\logs\amp\`. A gravação é a do `core/log_execucao.py` (`LogDeExecucao`), a mesma do
robô de duplicadas: linha a linha, com flush, e sem nunca derrubar a rodada. O diagnóstico de cada
falha continua num arquivo próprio, na mesma pasta, e o "Copiar diagnóstico" continua igual.

**Nunca vão para o log:** a chave e o conteúdo dos documentos. O `html` não aparece; vai só o
tamanho.

## 6. Documentação e textos

- **`amp/revisao_de_listas/LEIA-ME.md`**, reescrito. Ele cobre:
  - criar o agente no AMP, com os campos da tela;
  - colar ou importar o workflow;
  - a credencial, o Timeout e a publicação;
  - a URL e a chave no SIG-FT, pelo botão **Webhook…** da aba;
  - testar pelo SIG-FT;
  - testar sem o SIG-FT, com o `curl.exe`, os comandos de 03/11;
  - melhorar o agente: no AMP, e depois atualizar o `agente.md`;
  - a tabela de sintomas, com o 400 de arquivos.
- **`amp/revisao_de_listas/agente.md`** entra, e o `pedido.md` sai.
- **Textos da tela:**
  - a explicação da aba e o aviso de webhook não configurado, que passa a apontar para o botão
    Webhook…;
  - a janela do webhook;
  - o "Como funciona" (`PMIBManager.amp`);
  - as dicas dos botões (`textos_dicas.py`), com o "Testar conexão" sem o eco e os botões novos;
  - as traduções em `es.json` e `en.json`.
- **Outros documentos a atualizar:**
  - `docs/base-conhecimento/14-aconex-e-conferencia-de-revisoes.md` (a peça 2);
  - `docs/ROTEIRO_DE_TESTE.md` (a etapa 5c);
  - `docs/ACONEX_AO_VIVO.md`;
  - a linha de `amp/revisao_de_listas/` na tabela de documentação do `CLAUDE.md`.
- **`docs/refatoracao/PENDENCIAS.md`:** a linha de 2026-10-27 (S5) se fecha, porque o agente do AMP
  chamado por webhook foi provado em 03/11. Fica uma pendência nova: o limite de tamanho dos arquivos.
  O n8n aceita 16 MB por pedido no padrão, e o limite do agente não é conhecido. O teste de 03/11
  mandou 1,85 MB.
- **`CHANGELOG.md`:** no bloco da versão que levar esta peça.

## 7. Validação

**pytest, sem rede:**
- o cliente: os campos e os arquivos do multipart, os nomes dos arquivos, a chave no cabeçalho, uma
  tentativa só e o limite de tempo;
- o webhook do módulo:
  - a janela salva nos nomes do módulo;
  - ela recusa endereço sem `https://` e avisa do `/webhook-test/`;
  - os valores antigos são adotados uma vez;
  - Configuração → Chaves de API não tem mais os campos do AMP;
- os logs:
  - as linhas de cada lista (o que vai, o que voltou, a execução);
  - o batimento durante a espera;
  - o arquivo em `logs\amp\`;
  - a chave nunca aparece, nem no console nem no arquivo;
- a mensagem, com e sem revisão em uso;
- a conferência dos arquivos recebidos;
- o diagnóstico, com os tamanhos e sem o `html`;
- a tela:
  - as listas vêm marcadas por padrão;
  - a lista com falta não tem caixa;
  - Marcar todas e Desmarcar todas;
  - só as marcadas vão;
  - a lista pronta é desmarcada;
  - uma conferência nova refaz a tabela;
- o `.json` igual ao que o gerador produz.

**O aplicativo:** `QT_QPA_PLATFORM=offscreen python frontend.py --smoke`.

**Na GE** (etapa 5c do roteiro, reescrita):
1. Webhook… com a Production URL e a chave; "Testar conexão com o AMP": o `ping` passa.
2. Uma lista marcada: o HTML aparece na pasta da lista.
3. Uma rodada com duas ou três listas, uma desmarcada, que não vai.
4. Um segundo clique depois da rodada manda só as que falharam.

## 8. Fora desta peça

- **Melhorar o system prompt.** É a próxima frente, no AMP: o Luan não gostou do conteúdo de 03/11.
- **A peça 3:** aplicar as ações no Excel sozinho.
- **Esperar a resposta por consulta** (o workflow responde na hora e o SIG-FT busca depois). Só se a
  rede passar a cortar chamadas longas, o que hoje não acontece (§2).
- **Listas com arquivos grandes:** fica como pendência (§6).

## 9. Atualização de 2026-11-04: a resposta chega depois

**O que mudou.** No primeiro teste pelo SIG-FT, uma lista levou 17 minutos no AMP, e o SIG-FT
desistia aos 15. O resultado também se perdia quando o SIG-FT era fechado no meio. O Luan aprovou:
- o workflow responde na hora;
- o SIG-FT busca o resultado depois.

**No workflow:**
- **O envio** responde `{estado: "aceito", pedido, arquivos}`. O pedido é a execução do n8n.
- **O agente roda em seguida,** e o resultado fica nos dados estáticos do workflow
  (`$getWorkflowStaticData`): `estado` `pronto` ou `erro`, os 30 mais novos, por 7 dias. Os dados
  estáticos só persistem em produção.
- **Sai o "Responde erro" (502).** O erro do agente vira um resultado guardado.
- **`modo=buscar`** devolve o resultado guardado, ou `pendente`.

**No SIG-FT:**
- **`ClienteAmp.buscar(pedido)`.**
- **A espera:** a rodada pergunta a cada 30 s, até 60 min, e o batimento passa a ser essas
  perguntas. O pedido fica em `Documentos\SIG-FT\amp_pendentes.json` até o HTML ser gravado.
- **Parar ou passar do máximo** deixa a lista "no AMP" (`pendente`), e ela se desmarca.
- **Ao abrir, a aba busca os pendentes,** no máximo a cada 5 min, e grava cada HTML pronto na pasta
  da lista.
- **O limite de um envio** subiu para 45 min, para o caso do workflow antigo, que ainda devolve o
  HTML na mesma chamada e continua aceito.

**O que segue igual:**
- o envio vai uma vez só, pela rota do ping;
- a busca pode repetir à vontade, porque não chama o agente;
- o workflow da criação do `_STATUS_PMIB` usa o mesmo gerador (`montar_workflow`).

**Risco conhecido:** duas rodadas ao mesmo tempo, de dois SIG-FT, podem sobrescrever os dados
estáticos uma da outra, porque o n8n grava esses dados no fim de cada execução. O SIG-FT manda uma
lista por vez, então isso não acontece numa rodada só.
