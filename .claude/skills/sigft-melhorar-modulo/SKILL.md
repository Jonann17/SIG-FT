---
name: sigft-melhorar-modulo
description: Melhorar/evoluir um módulo existente do SIG-FT (nova opção, correção de comportamento, robustez, log melhor, campo novo). Usar quando o usuário pedir mudanças em um módulo que já existe ("o módulo X deveria...", "adicionar opção Y no...", "corrigir o comportamento de..."). Garante que a mudança respeite as convenções e não colida com a refatoração em andamento.
---

# Melhorar um módulo existente do SIG-FT

## Passo 1 — Situar-se (sempre, nesta ordem)

1. Identifique o módulo-alvo e leia o doc dele em `docs/base-conhecimento/` — é o mapa do
   comportamento atual (células, colunas, seletores, fluxo, pontos de atenção).
2. Leia `docs/refatoracao/PLANO_REFATORACAO.md` §6 (quadro de status) e
   `docs/refatoracao/PENDENCIAS.md`:
   - A melhoria pedida já está prevista em algum checkpoint? → proponha executar o checkpoint
     (via `refactor-executor`) em vez de fazer uma versão paralela.
   - O módulo está no meio de uma migração (ex.: engine RPA)? → implemente na camada nova,
     não na antiga.
3. Leia o código-fonte atual do módulo (serviço + view correspondente).

## Passo 2 — Alinhar a mudança

Confirme com o usuário, em uma frase cada: o comportamento desejado, o que NÃO deve mudar,
e como ele vai validar (especialmente se envolver o portal PMIB — RPA só é validável por ele,
em sessão real). Se a mudança for ambígua, pergunte antes de codar; se for clara, siga.

## Passo 3 — Implementar

- Mudança mínima que atende o pedido; não "aproveite" para refatorar fora do escopo — se
  encontrar algo que mereça, registre em `docs/refatoracao/PENDENCIAS.md`.
- Respeite as convenções do projeto (ver skill `sigft-novo-modulo`, Passo 3: callbacks,
  threading com `self.after`, normalização de PMIB, cabeçalho dinâmico, retry de arquivo
  aberto, padrão de logs início/por-item/resumo, estilo visual GE Vernova).
- Se existir implementação única em `sigft/core/` para o que você precisa, use-a; nunca crie
  a 2ª cópia de algo que o plano de refatoração está unificando.
- Seletores do portal: só altere com autorização explícita do usuário e teste dele no portal
  real. Prefira adicionar em vez de modificar fluxos calibrados.
- Se tocar em prompt de IA: preserve o formato de resposta esperado pelo parser; qualquer
  mudança de estrutura JSON exige ajustar o parser junto e avisar o usuário.

## Passo 4 — Verificar e fechar

1. `python -m py_compile` em todos os arquivos tocados; rode `tests/` se existirem; se a
   mudança for em função pura, adicione/ajuste teste.
2. Atualize o doc do módulo em `docs/base-conhecimento/` (pode delegar ao agente
   `doc-writer`: "atualize docs/base-conhecimento/<doc>.md refletindo a mudança X").
3. Commit: `Melhoria em <módulo>: <resumo>`.
4. Reporte ao usuário: o que mudou, o que foi preservado, e o roteiro de teste manual quando
   envolver portal/planilhas reais.
