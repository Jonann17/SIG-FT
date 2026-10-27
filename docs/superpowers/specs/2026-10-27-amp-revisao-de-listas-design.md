# Peça 2 — Revisão das listas pelo AMP (n8n)

**Data:** 2026-10-27. **Origem:** o rascunho "Workflow AMP" do Luan (25/10/2026) e a conversa de
27/10, em que ele aprovou o fluxo da §3. **Peça anterior:** o Aconex ao vivo e a Conferência de
Revisões (`docs/superpowers/specs/2026-10-26-aconex-ao-vivo-design.md`). A §5.6 de lá deixou para
cá o formato da passagem entre as peças.

As decisões marcadas *(minha decisão)* são de quem escreveu este desenho, não do Luan.

## 1. Por quê

A dor é atenção. As listas de sobressalentes mudam de revisão e ninguém percebe o que mudou. A
peça 1 aponta as listas com divergência entre a revisão em uso e a última emitida e baixa os PDFs
para a pasta de cada uma. A peça 2 faz a leitura: para cada lista, um agente do AMP compara as duas
revisões e a planilha de controle (`_STATUS_PMIB`), diz o que mudou e o que precisa ser atualizado.

Documento do projeto não pode ir para IA de fora, por isso a leitura fica no AMP, a IA interna da GE.
O Luan já fez esse trabalho à mão no chat do AMP, mandando os três arquivos (as duas revisões da
lista e a planilha de controle), e a revisão saiu boa. A peça 2 automatiza exatamente isso.

## 2. Objetivo, não objetivos e antiobjetivos

**Objetivo:** um botão no SIG-FT que manda ao AMP cada lista com divergência e traz de volta um HTML
por lista. O HTML explica o que mudou entre as revisões e o que diverge do `_STATUS_PMIB`, e traz o
`_STATUS_PMIB` remontado inteiro, pronto para copiar e colar no Excel.

**Não objetivos:**
- aplicar no Excel sozinho (é a peça 3);
- mexer na mapeadora;
- ler PDF que é só imagem: isso é falha da lista, e Itaipu pede revisão.

**Antiobjetivos** (falharia mesmo funcionando):
- texto de documento indo para IA de fora, inclusive dentro do diagnóstico, que vai para o Claude na web;
- uma colagem que apague o andamento da equipe (código PMIB, status, autorização) nas linhas que continuam;
- o agente afirmar uma mudança sem dizer de onde a tirou.

## 3. O fluxo (aprovado pelo Luan em 27/10)

1. **No SIG-FT, depois da Conferência**, o botão "Revisar no AMP" manda ao n8n cada lista com
   divergência. É uma chamada por lista, e o SIG-FT espera a resposta. O SIG-FT faz o papel do
   orquestrador, que não precisa ser IA. Vão a revisão em uso, a revisão atual e o `_STATUS_PMIB` (§4).
2. **No n8n**, um workflow começa por um webhook. O n8n da GE é o padrão do GitHub
   (`docs.n8n.io`). O agente é definido no próprio workflow, ligado a um GEV LLM Model. Ele recebe o
   pedido (o procedimento da equipe e o que se quer de volta, §5) e os três conteúdos, e devolve o
   HTML. Os agentes do AMP já sabem montar HTML: o pedido diz o que se quer, não como montar a página.
3. **De volta ao SIG-FT**, o HTML é gravado na pasta do `_STATUS_PMIB` da lista, e a tela mostra o
   resultado de cada uma.
4. **O Luan confere** o HTML antes de colar. Se o agente delirar, melhora-se o pedido.

O Luan confirmou que o n8n deles aceita os agentes do AMP. O nome `ampworkflow.gevernova.net` só
existe na rede da GE: o workflow é entregue como arquivo para importar, e quem o chama é o SIG-FT
rodando lá.

## 4. O que vai na chamada *(minha decisão)*

O SIG-FT manda **texto em JSON**, não os arquivos. Os motivos:
- o nó de modelo do n8n trabalha com texto;
- o diagnóstico (§8) mostra o tamanho do que foi mandado;
- o n8n não precisa ler o Box, coisa que continua sem prova no AMP (teste S4 da LMR).

Se o texto extraído não bastar, por exemplo numa tabela que sai embaralhada, a saída é mandar os
arquivos para o nó Amp Agent. Isso se decide no teste da GE.

- **PDF:** o texto de cada página, precedido de `--- página N ---`, para o agente citar a página.
- **`_STATUS_PMIB`:** a aba "Lista de Materiais" (com as grafias de `config.ABA_LISTA_MATERIAIS_VARIANTES`)
  e o cabeçalho achado por "CÓDIGO DO MATERIAL" nas 10 primeiras linhas, como o Gestão PMIB faz. Vão
  a linha de revisão ("REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: ..."), que fica acima do
  cabeçalho, e, do cabeçalho até a última linha com valor, todas as colunas, separadas por tabulação
  (é o formato que o Excel cola).

```json
{
  "modo": "revisar",
  "lista": {"codigo": "#ITA0=Y01TF001&BPB020", "revisao_em_uso": "0A", "revisao_atual": "0B",
            "status_real": "Aprovado", "status_da_revisao": "Em Processo", "categoria": "aprovada"},
  "revisao_em_uso": {"arquivo": "#ITA0=Y01TF001&BPB020[0A].pdf", "paginas": 12, "texto": "--- página 1 ---\n..."},
  "revisao_atual":  {"arquivo": "#ITA0=Y01TF001&BPB020[0B].pdf", "paginas": 13, "texto": "--- página 1 ---\n..."},
  "status_pmib": {"arquivo": "#ITA0=Y01TF001&BPB020_STATUS_PMIB.xlsx", "aba": "Lista de Materiais",
                  "linha_de_revisao": "REVISÃO DA LISTA ... EM USO: 0A - DATA DE ALTERAÇÃO: 01/09/2026",
                  "linhas": 214, "tsv": "ITEM\tQTD.\t..."},
  "origem": {"sigft": "1.3.1-rc.2"}
}
```

Sem revisão em uso (lista que nunca teve `_STATUS_PMIB` conferido), `revisao_em_uso` vai `null`, e o
agente compara só a revisão atual com o `_STATUS_PMIB`.

Os outros dois modos servem para testar a ligação (§7): `{"modo": "ping"}` e
`{"modo": "eco", "codigos": [...]}`.

## 5. O pedido ao agente

O texto mora em `amp/revisao_de_listas/pedido.md`, e o gerador o embute no workflow. É curto, de
propósito: diz o papel, as entradas, a tarefa, as regras da equipe e o que se quer de volta.

- **Tarefa:** comparar as duas revisões da lista (o que entrou, o que saiu, o que mudou: quantidade,
  descrição, código do material, marca e modelo...) e comparar a revisão atual com o `_STATUS_PMIB`,
  dizendo o que precisa ser atualizado.
- **Regras da equipe** (do Luan, 25/10):
  - o `_STATUS_PMIB` fica idêntico à lista;
  - o item que sai da lista vai para a `SEM_LISTA_STATUS_PMIB`, com a origem em OBSERVAÇÕES;
  - as linhas a mais vindas de entrega DOCUMENTAL são explosão pedida por Itaipu, não erro;
  - no fim, a linha de revisão passa à revisão nova e à data.
- **Preservar o andamento:** nas linhas que continuam, mantém-se o que a equipe preencheu (código
  PMIB, status, autorização).
- **O que se quer de volta** (do Luan, 27/10): um único HTML, com:
  - um resumo no topo;
  - o que mudou entre as revisões, cada mudança com a página do PDF de onde saiu;
  - as divergências com o `_STATUS_PMIB` e as ações;
  - o `_STATUS_PMIB` remontado inteiro, com as mesmas colunas na mesma ordem e um botão que copia a
    tabela como texto separado por tabulação, que cola direto no Excel;
  - as linhas que vão para a `SEM_LISTA_STATUS_PMIB`, também copiáveis;
  - a linha de revisão nova.

  O que o agente não tiver certeza, ele marca "a conferir", sem inventar. A resposta é só o HTML.

## 6. O workflow do n8n

Fica em `amp/revisao_de_listas/workflow_revisao_de_listas.json`, gerado por
`amp/revisao_de_listas/gerar_workflow.py` a partir do `pedido.md`. Um teste trava que o `.json`
versionado é o que o gerador produz.

| Nó | Tipo | O quê |
|---|---|---|
| Webhook do SIG-FT | Webhook (POST, `sigft-revisao-listas`) | autenticação Header Auth (`X-SIGFT-Chave`), resposta por nó |
| É ping? | If | `ping` responde sem chamar o modelo |
| Responde ping | Respond to Webhook | `{ok, modo, versao_workflow, execucao}` |
| Monta o pedido | Code | o pedido (§5) e os conteúdos, ou o pedido do eco |
| Agente da revisão | Basic LLM Chain | **o GEV LLM Model é ligado à mão** (o JSON não sabe o tipo do nó da GE); sugestão: Claude Sonnet 5.5 *(minha decisão)* |
| Prepara a resposta | Code | tira o HTML de dentro de ```` ``` ````, se vier; `ok` falso se não veio HTML |
| Responde | Respond to Webhook | `{ok, modo, html \| texto, versao_workflow, execucao}` |
| Responde erro | Respond to Webhook (502) | saída de erro do agente: `{ok: false, etapa, erro, execucao}` |

O `LEIA-ME.md` da pasta ensina a fazer, nesta ordem:
1. importar o workflow;
2. criar a credencial Header Auth (`X-SIGFT-Chave` e um valor longo e aleatório);
3. ligar o GEV LLM Model;
4. publicar;
5. copiar a URL de produção do webhook.

## 7. No SIG-FT

> **Atualização de 27/10 (correção do Luan, na execução):** a Conferência de Revisões e a Revisão no
> AMP viraram **abas do PMIB Manager** (Gestão PMIB, Conferência de Revisões, Revisão no AMP), no
> padrão da Aplicação LMR, e não telas do menu. Os botões abaixo moram na aba **Revisão no AMP**, com
> uma tabela própria (a coluna "AMP" é dela). Os rótulos das chaves ficaram "AMP Webhook (URL)" e
> "AMP Webhook (chave)", que cabem na coluna de rótulos do painel.

- **Configuração → Chaves de API:** "AMP (endereço do webhook)" e "AMP (chave do webhook)", no mesmo
  mecanismo das outras chaves (`ENV_VAR_POR_CHAVE`; variáveis `SIGFT_AMP_WEBHOOK_URL` e
  `SIGFT_AMP_WEBHOOK_CHAVE`). A chave nunca vai para o repositório, o log ou o diagnóstico.
- **Tela "Conferência de Revisões":**
  - **"Revisar no AMP"**: manda as listas da última conferência;
  - **"Testar conexão com o AMP"**: faz o `ping` (rede, chave e workflow publicado) e o `eco`;
  - **"Copiar diagnóstico"**: fica ligado quando alguma chamada falhou;
  - **uma coluna "AMP"** nas tabelas: HTML pronto, falhou ou o que falta.

  O `eco` manda os códigos das listas e confere se o modelo os devolve iguais. É o teste S6 da LMR
  (mascaramento) com dados reais *(minha decisão)*.
- **Quais listas:** as da última conferência que têm pasta, na ordem das categorias (aprovadas
  primeiro). Cada uma precisa do PDF da revisão atual, do PDF da revisão em uso (quando há revisão em
  uso) e do `_STATUS_PMIB`. Faltando um deles, a linha diz o que falta, e a lista não é chamada.
- **Gravação:** `<código>[<em uso>-<atual>] revisao AMP.html`, na pasta do `_STATUS_PMIB`. Nunca
  sobrescreve: se o nome existir, acrescenta " (2)", " (3)"... *(minha decisão)*
- **Ritmo:** uma chamada por vez, pela rede do `core/rede.py`, com 15 min de limite por lista *(minha
  decisão)*. "Parar" vale entre as listas.

## 8. Quando dá errado: o diagnóstico

Cada falha gera um texto pronto para colar numa conversa nova (o Claude na web, no PC da GE, com o
repositório do SIG-FT). O texto traz:
- a versão do SIG-FT e a hora;
- a lista e as revisões;
- o endereço chamado, sem a chave (diz só se a chave está posta);
- o que foi mandado, só em números: páginas e caracteres de cada texto, linhas do `_STATUS_PMIB`;
- o HTTP e o tempo;
- o corpo da resposta, até 1500 caracteres. O do workflow é `{ok, etapa, erro, execucao}`, e com o
  número da execução se acha o detalhe no n8n;
- o erro da rede (`rede.resumo_erro`);
- onde está o código no repositório.

**Nunca vai texto de documento.** O texto também é gravado em `Documentos\SIG-FT\logs\amp\`, e o
botão "Copiar diagnóstico" junta o de todas as falhas da rodada.

## 9. Validação

- **pytest, sem rede:** o cliente com um `abrir` dublê; o pedido montado com PDF e planilha de mentira;
  a gravação sem sobrescrever; o diagnóstico sem texto de documento; a tela com o serviço trocado.
- **Na GE** (roteiro de teste, Etapa 5c):
  1. importar e publicar o workflow, e pôr o endereço e a chave no SIG-FT;
  2. "Testar conexão com o AMP": o `ping` passa, e o `eco` devolve os códigos iguais;
  3. "Revisar no AMP" numa lista real;
  4. conferir o HTML contra os PDFs e colar numa cópia do `_STATUS_PMIB`.

## 10. Detalhes resolvidos na checagem do desenho *(minhas decisões)*

- **Os PDFs de cada lista:**
  - primeiro, os desta sessão: o `Download` da Conferência, baixado ou que já existia, com a revisão
    que o Aconex devolveu;
  - sem download na sessão (sem perfil do Aconex), os da pasta, pelo nome do padrão
    (`conferencia_revisoes.nome_do_pdf`): a revisão atual com a ÚLTIMA REVISÃO EMITIDA da mapeadora,
    e a revisão em uso com a REVISÃO EM USO.
- **O arquivo do `_STATUS_PMIB`:** a mesma resolução da pasta (o link da mapeadora e, quebrado, o
  levantamento da pasta raiz), devolvendo o arquivo em vez da pasta.
- **A leitura do PDF:** pelo PyMuPDF (`fitz`), que já vai no instalador. O código fica num módulo
  desta peça, sem importar nada do AutoSpec, que é da frente do Rafael. PDF sem texto em nenhuma página
  vira "falta: PDF sem texto (só imagem)", e a lista não é chamada.
- **O eco:** os códigos das listas da conferência e até dez CÓDIGOS DO MATERIAL do primeiro
  `_STATUS_PMIB` disponível, os campos que a LMR temia ver mascarados.

## 11. Fora desta peça

A peça 3 (aplicar sozinho), a mapeadora, PDF em imagem e passar outros módulos de IA do SIG-FT pelo
n8n, que é projeto à parte.
