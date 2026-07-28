"""Pacote `sigft.core.llm.providers` — implementações concretas de provedor
de IA, uma por SDK/API (Checkpoint 3.1 do plano de refatoração).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.1. Cada módulo
aqui dentro implementa o único método que `sigft.core.llm.client.LLMClient`
precisa de um provider — `generate_raw(prompt, *, system=None,
json_mode=False) -> (texto, tokens_in, tokens_out)` — e é o ÚNICO lugar do
projeto autorizado a importar o SDK pesado correspondente:

  - `gemini.py`: `GeminiProvider` importa `google.generativeai` (caminho
    direto Google, preserva comportamento/free tier atuais).

Módulos futuros (CP 3.2, fora de escopo aqui): `openai_compat.py` (base
OpenAI-compatível) e `openrouter.py` (especialização — gateway padrão da
decisão de produto nº 2, catálogo de modelos + custo real por chamada).
"""
