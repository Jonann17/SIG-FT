# Revisão das listas pelo AMP (n8n)

O workflow que o SIG-FT chama no **PMIB Manager**, aba **Revisão no AMP**, botão **Revisar no AMP**.
Para cada lista marcada na aba, ele leva ao agente *Spare Parts Document Reviewer*, criado no AMP:
- o PDF da revisão em uso;
- o PDF da revisão atual;
- o `_STATUS_PMIB.xlsx`.

Os arquivos vão como estão na pasta da lista. O agente devolve um HTML com o que mudou entre as
revisões e as ações no controle (criar, excluir ou substituir linhas). O SIG-FT grava esse HTML na
pasta da lista. Nada é aplicado no Excel.

Desenho: `docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`.

| Arquivo | O quê |
|---|---|
| `agente.md` | a cópia do agente no AMP: nome, descrição, goal e system prompt. **O agente se melhora no AMP**, e a cópia é atualizada depois |
| `gerar_workflow.py` | gera o `.json`: `python amp/revisao_de_listas/gerar_workflow.py` |
| `workflow_revisao_de_listas.json` | o workflow para importar ou colar no n8n. Não edite à mão: rode o gerador |

## Ligar (uma vez)

### 1. O agente, no AMP

1. Crie o agente, com o texto do `agente.md`:
   - **Customized Goal:** o goal;
   - **Agent Name** e **Description**;
   - **Tone:** `professional`;
   - **System Prompt:** o system prompt.
2. **Data sources:** nenhum. Os arquivos chegam a cada pedido.
3. Não use o **Add Optimized Query**: ele reescreve o prompt e pode amolecer regras como "não invente".

### 2. O workflow, no n8n (`https://ampworkflow.gevernova.net`)

1. **Importar.** Use **Create workflow** → menu **⋯** → **Import from File...** →
   `workflow_revisao_de_listas.json`. Ou abra o arquivo, copie tudo e cole no canvas vazio com
   **Ctrl+V**.
2. **Credencial.** Abra o nó **Webhook do SIG-FT**. Em *Credential for Header Auth*, escolha
   **Create new**:
   - **Name:** `X-SIGFT-Chave`;
   - **Value:** um valor longo e aleatório. No PowerShell:

     ```powershell
     -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 40 | % {[char]$_})
     ```

   Guarde o valor: ele vai no SIG-FT no passo 3.
3. **O agente.** No nó **AMP Agent**:
   - escolha **Spare Parts Document Reviewer** na lista. Se ele não aparecer, confira se foi salvo
     no AMP e recarregue a página; **By ID** é a saída;
   - confira a credencial do AMP;
   - em **Add option** → **Timeout**, ponha o máximo.
4. **Publicar.** Salve e publique o workflow (*Publish* ou *Active*, conforme a versão).
5. **Endereço.** No nó **Webhook do SIG-FT**, aba **Production URL** (não a *Test URL*), copie o
   endereço. Ele termina em `/webhook/sigft-revisao-listas`.

### 3. No SIG-FT

1. Vá em **PMIB Manager** → aba **Revisão no AMP** → **Webhook…**:
   - **Endereço:** a Production URL;
   - **Chave:** o valor da credencial.

   Clique em **Salvar**. Cada workflow do AMP tem o seu endereço e a sua chave, e eles ficam na aba
   que os usa, não em Configuração.
2. Clique em **Testar conexão com o AMP**. O console deve mostrar
   `OK      Ping: workflow 2026-11-03 (HTTP 200, ...)`. O ping prova três coisas: a rede, a chave e
   o workflow publicado. Ele não chama o agente.

## Testar sem o SIG-FT (PowerShell)

Serve para separar um problema do SIG-FT de um problema do AMP. Copie os três arquivos de uma lista
para `C:\temp\amp`: o `curl.exe` costuma falhar com acento no caminho, e a cópia também traz do Box
o arquivo que estava só na nuvem. Troque o `XXXXXX` pela chave e os nomes pelos da lista. Depois
cole no PowerShell:

```powershell
$url   = "https://ampworkflow.gevernova.net/webhook/sigft-revisao-listas"
$chave = "XXXXXX"
$teste = "C:\temp\amp"
$emUso = "$teste\<código>[<rev em uso>].pdf"
$atual = "$teste\<código>[<rev atual>].pdf"
$plan  = "$teste\<código>_STATUS_PMIB.xlsx"
$msg   = "Lista: <código>. Revisão em uso: <rev> (arquivo <nome>). Revisão atual: <rev> (arquivo <nome>). Controle: <nome>. Data de hoje: <dd/mm/aaaa>. Faça a revisão."
curl.exe -sS -w "`nHTTP %{http_code} em %{time_total} s`n" -H "X-SIGFT-Chave: $chave" --form-string "modo=ping" $url
curl.exe -sS --max-time 900 -o "$teste\resposta_amp.json" -w "HTTP %{http_code} em %{time_total} s`n" -H "X-SIGFT-Chave: $chave" --form-string "modo=revisar" --form-string "mensagem=$msg" -F "revisao_em_uso=@$emUso" -F "revisao_atual=@$atual" -F "status_pmib=@$plan" $url
(Get-Content "$teste\resposta_amp.json" -Raw -Encoding UTF8 | ConvertFrom-Json).html | Set-Content "$teste\resposta_amp.html" -Encoding UTF8
Start-Process "$teste\resposta_amp.html"
```

- **O ping** responde em cerca de 1 s.
- **A revisão** leva alguns minutos: em 03/11, uma lista de 7 folhas levou cerca de 3 min.
- **Se o HTTP não for 200,** rode `Get-Content C:\temp\amp\resposta_amp.json`: o corpo diz a etapa
  e o erro.

## Melhorar o agente

**As instruções moram no AMP, não no workflow.** Se o agente errar (item inventado, página errada,
andamento da equipe apagado):
1. Corrija o system prompt no AMP: o agente → Configure.
2. Copie o texto novo para o `agente.md`, num commit que diga o porquê.

Não precisa reimportar o workflow: ele só chama o agente.

## A resposta chega depois (desde 2026-11-04)

Uma lista levou 17 minutos no AMP. Por isso o workflow não segura a chamada até o agente terminar:
1. **O envio responde na hora** com o número do pedido, que é a execução do n8n. O SIG-FT escreve
   `aceito: o agente está lendo (pedido N)`.
2. **O agente roda em seguida.** O resultado, HTML ou erro, fica guardado nos dados do próprio
   workflow por 7 dias. Ficam os 30 mais novos.
3. **O SIG-FT pergunta pelo resultado a cada 30 s** (`modo=buscar`), até 60 min. Cada pergunta é
   uma execução curta no n8n, que não chama o agente.
4. **Se o SIG-FT fechar, se você clicar em Parar ou se passar de 60 min,** a lista fica "no AMP". O
   pedido fica anotado em `Documentos\SIG-FT\amp_pendentes.json`, e a aba **Revisão no AMP**, ao
   abrir, pergunta pelos pendentes e grava cada HTML pronto na pasta da lista.

**O resultado só fica guardado nas execuções de produção** (workflow publicado, Production URL).
Pela Test URL, a busca devolve sempre `pendente`.

**Para buscar à mão** um resultado que o SIG-FT não pegou: no n8n, menu **Executions**, abra a
execução e veja o nó **Prepara a resposta**. No **Output**, o campo `html` tem o relatório.

## O que os testes de 03/11 ensinaram

- **O AMP Agent lê a mensagem do campo `chatInput`** do item que chega. Sem ele, o erro é *"Prompt is
  empty. Provide a prompt value or pass chatInput from an On chat message node."* O nó **Monta a
  mensagem** existe por isso.
- **Os arquivos só passam do Edit Fields com *Include Other Input Fields = All*.** Sem isso, o nó
  entrega só o `chatInput`, e o agente responde que não recebeu arquivo. O nó **Chegaram os
  arquivos?** pega esse caso antes de gastar uma execução do agente.
- **O *Listen for test event* de dentro de um nó roda só aquele nó.** Para testar o workflow
  inteiro, use **Execute workflow**, no canvas.
- **A Test URL (`/webhook-test/`) só responde enquanto o n8n está escutando.** Fora isso, ela dá
  404. O SIG-FT usa a Production URL, e a janela do Webhook… recusa a de teste.
- **O agente escreve uma frase antes do HTML** ("Vou carregar a planilha...") e `100\%` no CSS,
  mesmo instruído a não fazer. O nó **Prepara a resposta** corrige as duas coisas.

## Se der errado

O que se vê de cada lista:
- **O console da aba** mostra cada passo: o que vai (nome e tamanho de cada arquivo), a espera, de
  30 em 30 s, e o que voltou (HTTP, tempo, **número da execução do n8n** e quantos arquivos o
  workflow recebeu).
- **As mesmas linhas ficam gravadas** em `Documentos\SIG-FT\logs\amp\amp_revisao_*.log`, com a hora,
  e o teste de conexão em `amp_teste_*.log`.
- **Cada lista que falha** gera um diagnóstico em `Documentos\SIG-FT\logs\amp\`.
- **O botão Copiar diagnóstico** junta os diagnósticos da rodada, sem conteúdo de documento e sem a
  chave.
- **Com o número da execução,** o n8n mostra em que nó a execução parou (menu **Executions**).

Para pedir ajuda numa conversa nova (o Claude na web, no PC da GE, com o repositório do SIG-FT), cole
isto e, embaixo, o diagnóstico ou as linhas do log:

```text
Estou testando a revisão das listas pelo AMP no SIG-FT (PMIB Manager, aba Revisão no AMP). A
chamada ao workflow do n8n falhou. Leia, no repositório:
- amp/revisao_de_listas/LEIA-ME.md e docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md
- sigft/core/amp/cliente.py e sigft/services/revisao_amp.py
Diga a causa provável e o que eu faço: no AMP, no n8n, no SIG-FT ou no código. Não peça os
documentos: eles não podem sair da GE. O diagnóstico do SIG-FT está abaixo.
```

| Sintoma | Onde olhar |
|---|---|
| "Sem conexão com o AMP" | a rede da máquina: ela precisa alcançar `ampworkflow.gevernova.net` |
| HTTP 401 ou 403 | a chave do **Webhook…** é diferente da credencial `X-SIGFT-Chave` do workflow |
| HTTP 404 | o workflow não está publicado, ou o endereço é a Test URL (`/webhook-test/`) |
| HTTP 400, etapa `arquivos` | os arquivos não chegaram ao agente: o **Monta a mensagem** precisa de *Include Other Input Fields = All* |
| "falhou: ... (etapa agente)" | o agente falhou: veja a execução no n8n e confira se o **AMP Agent** tem o agente e a credencial |
| "o agente não devolveu HTML" | o agente respondeu texto: melhore o system prompt no AMP |
| "o workflow recebeu N de M arquivo(s)" | algum arquivo se perdeu no caminho: veja a aba Binary do Webhook na execução |
| "o AMP não respondeu JSON" | algo no caminho devolveu uma página (login, proxy): a resposta está no diagnóstico |
| "a conexão com o AMP caiu depois de N s" | algo no caminho corta a chamada longa; o n8n pode ter seguido (veja a execução). Em 03/11 a rede segurou uma chamada de minutos |
| "no AMP: o HTML é buscado depois" | o agente passou de 60 min, ou você clicou em Parar: o resultado fica guardado no n8n por 7 dias, e a aba o busca sozinha ao abrir |

**A revisão de cada lista vai uma vez só.** O SIG-FT não repete a chamada sozinho, porque cada
repetição seria outra execução do agente no AMP. Para tentar de novo, clique em **Revisar no AMP**
outra vez: as listas que já voltaram com HTML se desmarcaram sozinhas, então vão só as que faltaram.
