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
  Condições, Upload Specs e Planilhas PMIB (tradução do PDM). Ficam de fora, por ora:
  AutoSpec (tela do Rafael; aviso no mural), DocPack, Conferência e Revisão no AMP
  (estão sendo reorganizados em paralelo).

## Fora do escopo

A IA Interna de verdade (quando o AMP tiver API), o teste do webhook pela tela e a
estimativa de custo do workflow.
