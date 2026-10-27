# Revisão das listas pelo AMP (n8n)

O workflow que o SIG-FT chama no **PMIB Manager**, aba **Revisão no AMP** → **Revisar no AMP**. Para
cada lista com divergência da última conferência (aba **Conferência de Revisões**), o agente lê:
- o texto das duas revisões do PDF;
- o `_STATUS_PMIB`.

Ele devolve um HTML que diz o que mudou e traz o `_STATUS_PMIB` remontado inteiro, pronto para colar
no Excel.

Desenho: `docs/superpowers/specs/2026-10-27-amp-revisao-de-listas-design.md`.

| Arquivo | O quê |
|---|---|
| `pedido.md` | o pedido ao agente: o que fazer, as regras da equipe e o que devolver. **É aqui que se melhora o agente.** |
| `gerar_workflow.py` | gera o `.json` a partir do `pedido.md`: `python amp/revisao_de_listas/gerar_workflow.py` |
| `workflow_revisao_de_listas.json` | o workflow para importar no n8n (não edite à mão: rode o gerador) |

## Ligar (uma vez)

1. **Importar.** No n8n (`https://ampworkflow.gevernova.net`): **Create workflow** → menu **⋯** →
   **Import from File...** → `workflow_revisao_de_listas.json`.
2. **Credencial.** Abra o nó **Webhook do SIG-FT**. Em *Credential for Header Auth*, crie uma nova:
   - **Name:** `X-SIGFT-Chave`;
   - **Value:** um valor longo e aleatório, por exemplo 40 letras e números.

   Guarde o valor: ele vai no SIG-FT, no passo 6.
3. **Modelo.** No nó **Agente da revisão**, clique no **+** de **Model** e escolha **GEV LLM Model**
   (sugestão: Claude Sonnet 5.5). O arquivo não traz esse nó porque ele é da GE.
4. **Publicar.** Salve e **publique** o workflow (*Publish* ou *Active*, conforme a versão).
5. **Endereço.** No nó **Webhook do SIG-FT**, aba *Production URL*, copie o endereço. Ele termina em
   `/webhook/sigft-revisao-listas`.
6. **No SIG-FT.** Na engrenagem (Configuração) → **Chaves de API**:
   - **AMP Webhook (URL):** o endereço do passo 5;
   - **AMP Webhook (chave):** o valor do passo 2.
7. **Testar.** No PMIB Manager, aba **Revisão no AMP**, clique em **Testar conexão com o AMP**. O eco
   usa os códigos da última conferência: rode a aba **Conferência de Revisões** antes (sem ela, só o
   ping vai):
   - o **ping** prova a rede, a chave e o workflow publicado;
   - o **eco** manda códigos das listas ao modelo e confere se voltaram iguais. Esse é o teste de
     mascaramento: se voltar `FALHOU ... mascarado`, o AMP está escondendo códigos, e a tabela
     remontada não é confiável.

## Melhorar o agente

Se o agente delirar (inventar item, errar página, apagar o andamento da equipe):
1. corrija o `pedido.md`;
2. rode `python amp/revisao_de_listas/gerar_workflow.py`;
3. importe de novo, ou cole o novo `pedido.md` no nó **Monta o pedido**, na constante `PEDIDO`.

Mantenha o pedido curto: os agentes do AMP já sabem montar o HTML.

## Se der errado

Cada lista que falha gera um **diagnóstico**:
- o console mostra a falha e onde o diagnóstico foi gravado;
- fica gravado em `Documentos\SIG-FT\logs\amp\`;
- o botão **Copiar diagnóstico** junta o de todas as falhas da rodada, já com uma abertura que diz ao
  Claude o que é o texto.

O diagnóstico **não leva texto de documento nem a chave**. Leva:
- a versão do SIG-FT;
- a lista e as revisões;
- o tamanho do que foi mandado;
- o HTTP e o tempo;
- a resposta;
- o **número da execução do n8n**. No n8n, menu **Executions**, essa execução mostra em que nó parou
  e por quê.

Para pedir ajuda numa conversa nova (o Claude na web, no PC da GE, com o repositório do SIG-FT),
cole isto e, embaixo, o diagnóstico:

```text
Estou testando a revisão das listas pelo AMP no SIG-FT (PMIB Manager, aba Revisão no AMP). A
chamada ao workflow do n8n falhou. Leia, no repositório:
- amp/revisao_de_listas/LEIA-ME.md e docs/superpowers/specs/2026-10-27-amp-revisao-de-listas-design.md
- sigft/core/amp/cliente.py e sigft/services/revisao_amp.py
Diga a causa provável e o que eu faço: no n8n, no SIG-FT ou no código. Não peça os documentos:
eles não podem sair da GE. O diagnóstico do SIG-FT está abaixo.
```

Se o que falhou foi o **Testar conexão com o AMP**, cole as duas linhas do console (`Ping` e `Eco`)
no lugar do diagnóstico. Se o SIG-FT nem abriu a aba, cole o fim de `Documentos\SIG-FT\logs\sigft.log`.

| Sintoma no diagnóstico | Onde olhar |
|---|---|
| "Sem conexão com o AMP" | a rede da máquina: ela precisa alcançar `ampworkflow.gevernova.net` |
| HTTP 401 ou 403 | a chave no SIG-FT é diferente da credencial `X-SIGFT-Chave` do workflow |
| HTTP 404 | o workflow não está publicado, ou o endereço no SIG-FT não é a Production URL |
| HTTP 502, `etapa: agente` | o modelo falhou: veja a execução no n8n; confira se o GEV LLM Model está ligado |
| "o AMP não respondeu JSON" | algo no caminho devolveu uma página (login, proxy): a resposta está no diagnóstico |
| "o agente não devolveu HTML" | o modelo respondeu texto: melhore o pedido ou troque o modelo |
