# Pendências da Refatoração

Registro de itens descobertos durante a execução dos checkpoints que estavam fora do escopo
do checkpoint em andamento. O `refactor-executor` adiciona entradas aqui; o arquiteto decide
em qual fase/checkpoint cada uma entra.

| Data | Descoberto em | Descrição | Destino proposto |
|---|---|---|---|
| 2026-07-24 | Bootstrap | Chaves API expostas no código original — precisam ser **rotacionadas** pelo usuário | Ação do usuário |
| 2026-07-24 | Bootstrap | `lmr_backend._processar_ficha_lmr_interna`: no `except`, o índice não avança — risco de loop infinito se o erro persistir | Fase 4 (CP 4.2) |
| 2026-07-24 | Bootstrap | `pdm_backend.logica_excluir_duplicados` exclui o MAIOR arquivo do grupo (ordenação decrescente por tamanho) — confirmar com o usuário se essa é a intenção antes de manter | Confirmar com usuário |
| 2026-07-24 | Bootstrap | `autospec_backend.fill_save`: checkboxes usam `ws[clean]` onde `clean` é o VALOR da resposta da IA em maiúsculas — só funciona se a IA devolver exatamente a referência da célula (ex: "G25"); validar comportamento real | Fase 3 |
| 2026-07-24 | Decisões de produto | `upload_ficha_duplicada` declarado "fraco/não funciona como deveria" pelo usuário — coberto pela Fase 6 (reconstrução) do plano | Fase 6 |
| 2026-07-24 | Decisões de produto | ~~Definir se o `autospec` mantém LangChain~~ **RESOLVIDO (2026-07-24)**: LangChain avaliado e descartado como camada central; uso residual no `autospec` será removido no CP 3.2 (racional registrado no plano, Fase 3) | CP 3.2 |
| 2026-07-24 | Decisão OpenRouter | Validar no CP 3.2, por tarefa: `response_format` (JSON mode) nos modelos escolhidos, equivalência do comportamento de safety do Gemini via OpenRouter, e impacto do markup (~5% sobre créditos) no relatório de custos | CP 3.2 |
| 2026-07-24 | Decisão OpenRouter | Conteúdo sensível (fichas técnicas GE Vernova) trafegando por gateway de terceiro: usuário decide por tarefa qual caminho usar (OpenRouter × direto); revisar política antes de tornar OpenRouter default em produção | Decisão do usuário no CP 3.3 |
