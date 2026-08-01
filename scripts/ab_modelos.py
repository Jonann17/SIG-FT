#!/usr/bin/env python3
r"""
scripts/ab_modelos.py — roda o MESMO prompt em vários modelos e monta um
relatório comparativo (A/B de modelos de IA do SIG-FT).

Existe para atender o Aceite do CP 3.3 do plano de refatoração
(docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.3): "o usuário valida
a qualidade num punhado de fichas (A/B contra o modelo anterior)" antes de
adotar os modelos econômicos do MODELOS_IA.md. Sem isto, a validação
dependeria de rodar o módulo inteiro duas vezes e comparar planilhas na mão.

═══════════════════════════════════════════════════════════════════════════
COMO USAR (o passo a passo completo)
═══════════════════════════════════════════════════════════════════════════

PASSO 1 — capturar prompts REAIS de uma execução normal.

Os prompts do SIG-FT são grandes e dependem de ler Excel/PDF, então não se
remonta um à mão. Ligue a captura e rode o módulo que quer validar UMA vez,
normalmente, pelo app:

    # Windows (PowerShell)
    $env:SIGFT_DUMP_PROMPTS = "C:\temp\prompts_ab"
    python frontend.py

    # Linux/macOS
    SIGFT_DUMP_PROMPTS=/tmp/prompts_ab python frontend.py

Cada chamada de IA grava um `.json` nessa pasta (prompt, system, json_mode,
tarefa, e qual modelo atendeu na captura). Rode em ~5 fichas para ter
amostra. Depois é só apagar a variável — a captura fica desligada por padrão
e não custa nada quando ausente.

PASSO 2 — comparar modelos num prompt capturado.

    python scripts/ab_modelos.py \
        --prompt /tmp/prompts_ab/20260731-101500_tech_specs_001.json \
        --modelos gemini:gemini-3.5-flash openrouter:google/gemini-3-flash-preview \
        --saida relatorio_ab.md

O PRIMEIRO modelo da lista é o BASELINE (ponha o que você usa hoje); os
demais são comparados contra ele. As chaves de API vêm do `.env`/
`api_config.json` de sempre (`sigft.config.carregar_chaves`).

PASSO 3 — ler o relatório.

`relatorio_ab.md` traz: tabela-resumo (JSON válido, tokens, custo real,
duração, nº de diferenças), as diferenças campo a campo contra o baseline,
e as respostas completas lado a lado. Ele resolve sozinho a parte objetiva
(campo que sumiu, valor que mudou); o julgamento de texto livre em PT/ES
continua sendo seu — o relatório diz isso no rodapé.

Dica: `--repeticoes 3` roda cada modelo N vezes. Se o MESMO modelo divergir
de si mesmo entre repetições, o que você está vendo é aleatoriedade do
modelo, não superioridade de um sobre o outro.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

# Permite rodar como `python scripts/ab_modelos.py` a partir da raiz do repo.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sigft import config  # noqa: E402
from sigft.core.llm.client import _limpar_e_parsear_json  # noqa: E402
from sigft.core.llm.comparacao import montar_relatorio_markdown  # noqa: E402


def construir_provider(provider_id: str, model: str, chaves: dict[str, str | None], temperature):
    """Constrói o provider concreto para um par `provider:modelo` explícito.

    Não usa `get_llm()` de propósito: `get_llm` resolve o modelo a partir da
    tarefa/seleção do usuário, e aqui o objetivo é justamente FORÇAR um par
    específico, sem mexer na seleção salva de quem está testando.
    """
    if provider_id not in config.CHAVE_POR_PROVIDER:
        raise SystemExit(
            f"Provider {provider_id!r} desconhecido. "
            f"Use um de: {', '.join(sorted(config.CHAVE_POR_PROVIDER))}."
        )

    chave = chaves.get(config.CHAVE_POR_PROVIDER[provider_id])

    if provider_id == config.PROVIDER_GEMINI:
        from sigft.core.llm.providers.gemini import GeminiProvider

        return GeminiProvider(chave, model, temperature=temperature)

    if provider_id == config.PROVIDER_OPENROUTER:
        from sigft.core.llm.providers.openrouter import OpenRouterProvider

        return OpenRouterProvider(chave, model, temperature=temperature)

    from sigft.core.llm.providers.openai_compat import OpenAICompatProvider

    base_url = chaves.get("EMPRESA_LLM_BASE_URL")
    if not base_url:
        raise SystemExit("Provider 'openai_compat' exige EMPRESA_LLM_BASE_URL configurada.")
    return OpenAICompatProvider(chave, model, base_url=base_url, temperature=temperature)


def rodar_um(provider, rotulo: str, prompt: str, system, json_mode: bool) -> dict:
    """Uma chamada, SEM retry (queremos ver a falha crua de cada modelo, não
    a resiliência do `LLMClient`) e sem deixar exceção derrubar o lote — um
    modelo que falha vira uma linha 'falhou' no relatório, e os outros
    continuam."""
    inicio = time.time()
    try:
        resultado = provider.generate_raw(prompt, system=system, json_mode=json_mode)
    except Exception as erro:  # noqa: BLE001 - relatório precisa das falhas
        return {"rotulo": rotulo, "ok": False, "erro": f"{type(erro).__name__}: {erro}"}

    duracao = time.time() - inicio
    try:
        parsed = _limpar_e_parsear_json(resultado.text)
    except Exception:  # noqa: BLE001 - "não parseou" é um RESULTADO, não um erro fatal
        parsed = None

    return {
        "rotulo": rotulo,
        "ok": True,
        "texto": resultado.text,
        "parsed": parsed,
        "tokens_in": resultado.tokens_in,
        "tokens_out": resultado.tokens_out,
        "custo_usd": resultado.custo_usd,
        "duracao_s": duracao,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Roda o mesmo prompt em vários modelos e gera um relatório comparativo.",
        epilog="Veja o docstring do arquivo para o passo a passo completo (captura de prompts).",
    )
    parser.add_argument(
        "--prompt", required=True,
        help="Arquivo .json capturado com SIGFT_DUMP_PROMPTS (ver docstring).",
    )
    parser.add_argument(
        "--modelos", required=True, nargs="+", metavar="PROVIDER:MODELO",
        help="Pares provider:modelo. O PRIMEIRO é o baseline. "
             "Ex.: gemini:gemini-3.5-flash openrouter:x-ai/grok-4.5",
    )
    parser.add_argument("--saida", default="relatorio_ab.md", help="Arquivo .md de saída.")
    parser.add_argument(
        "--repeticoes", type=int, default=1,
        help="Roda cada modelo N vezes (detecta aleatoriedade do próprio modelo).",
    )
    parser.add_argument(
        "--temperature", type=float, default=None,
        help="Temperature aplicada a TODOS os modelos (default: a do provider).",
    )
    args = parser.parse_args(argv)

    with open(args.prompt, "r", encoding="utf-8") as arquivo:
        capturado = json.load(arquivo)

    prompt = capturado["prompt"]
    system = capturado.get("system")
    json_mode = bool(capturado.get("json_mode"))
    chaves = config.carregar_chaves()

    resultados = []
    for par in args.modelos:
        if ":" not in par:
            raise SystemExit(f"Formato inválido: {par!r}. Use provider:modelo.")
        provider_id, model = par.split(":", 1)
        provider = construir_provider(provider_id, model, chaves, args.temperature)

        for repeticao in range(1, args.repeticoes + 1):
            rotulo = par if args.repeticoes == 1 else f"{par} (rodada {repeticao})"
            print(f"-> {rotulo}...", flush=True)
            resultados.append(rodar_um(provider, rotulo, prompt, system, json_mode))

    relatorio = montar_relatorio_markdown(
        resultados,
        contexto={
            "Prompt": os.path.basename(args.prompt),
            "Tarefa": capturado.get("tarefa", "?"),
            "Módulo": capturado.get("modulo") or "?",
            "Modelo na captura": (
                f"{capturado.get('provider_na_captura')}/{capturado.get('model_na_captura')}"
            ),
            "JSON mode": "sim" if json_mode else "não",
        },
    )
    with open(args.saida, "w", encoding="utf-8") as arquivo:
        arquivo.write(relatorio)

    print(f"\nRelatório escrito em: {args.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
