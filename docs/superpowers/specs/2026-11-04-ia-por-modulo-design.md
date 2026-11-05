# IA por módulo: IA Externa, IA Interna e Workflow AMP (2026-11-04)

Pedido do Luan (Teams, 04/11, item 1), trazido pelo Jonathan: com o workflow do AMP
no ar, a escolha da IA passa a ser **por módulo**, com três opções:

- **IA Externa**: o OpenRouter, com o catálogo, o botão de atualizá-lo, o filtro de
  busca e o botão para configurar a chave do OpenRouter;
- **IA Interna (AMP)**: aparece, mas desligada (ainda não há a API do AMP);
- **Workflow AMP**: o endereço do webhook e a chave (credencial) daquele módulo.

Cada tela que usa IA ganha o botão **"Configurar IA"**, que abre a MESMA configuração,
só daquele módulo. As duas portas (a central e a da tela) gravam no mesmo lugar, e uma
aberta enquanto a outra muda se redesenha.

## Onde mora a escolha (uma fonte só)

- O modo e o modelo continuam na seleção por tarefa de `core/llm/selecao.py`
  (`_modelos_ia.por_tarefa` do `api_config.json`). A IA Externa grava
  `{"provider": "openrouter", "model": <id>}`; o Workflow AMP grava
  `{"provider": "amp_workflow", "model": "workflow"}`. Não há campo novo: o modo é
  derivado do provedor (`core/llm/modo.py`).
- **Compatibilidade**: o que já estava salvo (qualquer provedor que não seja
  `amp_workflow`) é IA Externa, e continua rodando igual. A seleção global e o painel
  antigo de "Modelos de IA" continuam valendo para a tarefa sem escolha por módulo; o
  painel antigo fica na mesma janela, abaixo, como "modelo padrão".
- O webhook de cada módulo fica nas chaves, com os nomes `AMP_IA_<TAREFA>_URL` e
  `AMP_IA_<TAREFA>_CHAVE` (o mesmo esquema de `widgets/webhook_amp.py`).

## Na hora de rodar

`get_llm(tarefa)` vê o provedor `amp_workflow` e monta o `AmpWorkflowProvider`
(`core/llm/providers/amp_workflow.py`), que manda o prompt ao webhook pelo
`core/amp/cliente.ClienteAmp` (um transporte só) e devolve o texto. Sem repetição
(`max_retries=0`): cada repetição seria uma execução nova do agente no AMP.

Contrato com o workflow do n8n (POST, formulário):

| campo | valor |
|---|---|
| `modo` | `ia` |
| `tarefa` | o nome da tarefa (`validar_ficha`, `condicoes`...) |
| `prompt` | o prompt inteiro |
| `system` | a instrução de sistema, quando há |
| `json` | `sim` quando a tarefa espera JSON |

Resposta: `{"ok": true, "texto": "<resposta do agente>"}` (aceita `resposta` no lugar
de `texto`). Falha vira erro legível, sem a chave.

## Telas

- Central: a janela "Modelos de IA" abre com a seção **"IA por módulo"** em cima: a
  lista dos módulos à esquerda; clicou, à direita os três modos e o conteúdo do modo.
- Nas telas: "Configurar IA" no cabeçalho de Cria Fichas, Analyzer, Upload
  Condições, Upload Specs, Planilhas PMIB (tradução do PDM) e DocPack (a sugestão de
  pasta da Etapa 1; o botão fica no cabeçalho da seção, porque as abas são telas
  embutidas, sem cabeçalho). Fica de fora, por ora, o AutoSpec (tela do Rafael; aviso
  no mural). A Conferência de Listas e a Etapa 2 do DocPack não passam pelo `get_llm`:
  falam com o AMP pelo webhook da própria aba, e não ganham o botão.

## Fora do escopo

A IA Interna de verdade (quando o AMP tiver API), o teste do webhook pela tela e a
estimativa de custo do workflow.

## 2026-11-05: os workflows, os anexos e o AutoSpec

Os workflows do n8n que respondem a este contrato moram em `amp/ia_por_modulo/` (um gerador, um
workflow e um agente por tela; o LEIA-ME tem o passo a passo). Decisão do Luan: o agente de cada
módulo tem um system prompt **curto**, porque o prompt inteiro vai do SIG-FT; as regras continuam em
`core/llm/prompts.py`. Um módulo por vez, testado antes do seguinte. O Cria Fichas (as duas
passadas, no mesmo workflow) passou no teste real na GE em 2026-11-05.

**Os anexos.** O AutoSpec manda o próprio PDF (e as páginas escaneadas como imagem) por
`generate(..., anexos=...)`, e o provedor descartava os anexos sem avisar. Desde esta data:

| campo | valor |
|---|---|
| `anexo_1`, `anexo_2`... | os arquivos, com o nome e o tipo de cada um |
| `arquivos` | quantos são (só quando há) |

A resposta passa a trazer `arquivos_recebidos` (e os nomes, em `arquivos`). Sem essa conta, ou com
menos arquivos do que foram, o provedor levanta erro: o agente respondeu sem ver os documentos, e
quem chama decide (o AutoSpec refaz a ficha com o texto extraído, como quando um provedor recusa o
PDF). `aceita_pdf` do provedor é verdadeiro: o agente do AMP lê o PDF anexado, como na revisão das
listas. O `ClienteAmp.enviar` aceita arquivo em memória (`nome`, `dados`, `mime`) além do caminho.

**O AutoSpec** se liga pela central ("Modelos de IA"), porque a tela dele (do Rafael) não tem o
botão. O código do AutoSpec não mudou: ele já perguntava `aceita_pdf` e já caía para o texto.

