"""Pacote `sigft.core.llm` — camada de IA multi-provedor do SIG-FT.

Checkpoint 3.1 do plano de refatoração
(docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.1), diagnóstico
seção 1.3 ("Duplicação e rigidez de IA"): `genai.configure(transport='rest')`
+ `GenerativeModel` + retry (5x: `analyzer`, `cria_fichas`,
`upload_conditions`, `tech_specs` + `autospec` via LangChain), limpeza da
resposta JSON (4 variantes), `safety_settings` BLOCK_NONE (2x copiado
literal) e acoplamento total ao Gemini (nomes de modelo hardcoded, sem
abstração de provedor).

  - `client.py`: `LLMClient` (retry + rate-limit opcional + parse/limpeza de
    JSON, injetado sobre um "provider"), `LLMResponse` (formato único de
    retorno) e a fábrica `get_llm(tarefa, api_key)`.
  - `providers/gemini.py`: `GeminiProvider` — ÚNICO módulo do projeto que
    importa `google.generativeai`, reproduzindo o comportamento direto do
    Google (transport REST, free tier do AI Studio).
  - `providers/openai_compat.py`/`providers/openrouter.py` (CP 3.2):
    provider genérico OpenAI-compatível e sua especialização OpenRouter
    (gateway padrão, catálogo de modelos + custo real por chamada).
  - `selecao.py` (CP 3.3): persistência da seleção de modelo feita pelo
    usuário no painel "Modelos de IA" da Home (`carregar`/`resolver`/
    `definir_global`/`definir_por_tarefa`/`aplicar_recomendados`) — o que
    `get_llm()` consulta ANTES do fallback embutido `config.LLM_MODELOS_HOJE`.
  - `usage.py` (CP 3.4): "UsageTracker" — `registrar()`/`ler_registros()`/
    `usage_report()`/`formatar_relatorio_texto()`. `LLMClient.generate()`
    grava um registro JSONL por chamada (`logs/llm_usage.jsonl`, via
    `config.ARQUIVO_USO_LLM`) nos 2 pontos de saída (sucesso/falha total);
    custo REAL do provider (hoje só OpenRouter) ou ESTIMADO pela tabela de
    preços `config.LLM_PRECOS_USD_POR_1M`. Rastreamento nunca derruba uma
    execução (qualquer falha de escrita é engolida) — desligável via
    `SIGFT_DESABILITAR_USAGE=1`.

Só stdlib em `client.py`/`selecao.py`/`usage.py` (`time`, `json`,
`dataclasses`, `os`, `datetime`) — importáveis no ambiente de teste sem
`google-generativeai` instalado (ver tests/conftest.py); o SDK pesado fica
isolado em `providers/gemini.py`, via import preguiçoso (mesma convenção de
`core/excel/status_sheet.py` para `openpyxl`).

Módulo futuro, fora do escopo do CP 3.4 (ver
docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.5, e
docs/refatoracao/PENDENCIAS.md): `prompts.py` (extração dos 5 prompts
gigantes, CP 3.5).
"""
