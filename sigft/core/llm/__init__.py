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

Só stdlib em `client.py` (`time`, `json`, `dataclasses`) — importável no
ambiente de teste sem `google-generativeai` instalado (ver
tests/conftest.py); o SDK pesado fica isolado em `providers/gemini.py`, via
import preguiçoso (mesma convenção de `core/excel/status_sheet.py` para
`openpyxl`).

Módulos futuros, fora do escopo do CP 3.1 (ver
docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.2+, e
docs/refatoracao/PENDENCIAS.md): `providers/openai_compat.py`/
`providers/openrouter.py` (gateway padrão multi-modelo, CP 3.2), `usage.py`
(rastreamento de custo real/estimado, CP 3.4) e `prompts.py` (extração dos 5
prompts gigantes, CP 3.5).
"""
