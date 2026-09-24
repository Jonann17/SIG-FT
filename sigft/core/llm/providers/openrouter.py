r"""
sigft/core/llm/providers/openrouter.py — `OpenRouterProvider`: gateway
PADRÃO de IA do SIG-FT (Checkpoint 3.2 do plano de refatoração).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.2:
"`providers/openrouter.py` como especialização: `base_url=
https://openrouter.ai/api/v1`, headers de atribuição, catálogo de modelos
via `GET /models` (com cache local) e `usage: {include: true}` para receber
o CUSTO REAL de cada chamada na resposta"; decisão de produto nº 2: "OpenRouter
é o gateway padrão — uma única chave dá acesso a Gemini, GPT, Kimi, DeepSeek
etc., fornece o catálogo de modelos para a UI e devolve o custo REAL de cada
chamada."

`OpenRouterProvider` ESPECIALIZA `OpenAICompatProvider`
(`providers/openai_compat.py`) via os 2 hooks de extensão que a base já
expõe (`_montar_corpo_extra`/`_extrair_custo`) -- NÃO duplica
`generate_raw`.

`listar_modelos(...)` é um insumo do CP 3.3 (seleção de modelo na UI) --
NENHUM consumidor de produção ainda neste checkpoint.
"""

from __future__ import annotations

from typing import Any

import json
import os
import time

from sigft import config
from sigft.core.llm.providers.openai_compat import OpenAICompatProvider


# Famílias que LEEM PDF nativamente (2026-09-24). O OpenRouter aceita PDF
# para qualquer modelo, mas nos que não leem ele faz OCR por conta própria --
# e o OCR padrão (`mistral-ocr`) é PAGO por página. O AutoSpec só manda o
# arquivo a quem está nesta lista, e com `engine: native`; os demais recebem
# o texto que o próprio app extraiu, de graça. Prefixo do id do OpenRouter,
# em minúsculas. Família nova que leia PDF entra aqui.
PREFIXOS_COM_PDF_NATIVO = (
    "google/gemini",
    "anthropic/claude",
    "openai/gpt-4o",
    "openai/gpt-4.1",
    "openai/gpt-5",
    "openai/o3",
    "openai/o4",
)


class OpenRouterProvider(OpenAICompatProvider):
    """Especialização de `OpenAICompatProvider` para o OpenRouter:
    `base_url` default, headers de atribuição (`HTTP-Referer`/`X-Title`) e
    custo REAL por chamada (`usage.cost`, habilitado via `"usage":
    {"include": True}` no corpo da requisição).
    """

    def __init__(
        self,
        api_key: str | None,
        model: str,
        *,
        base_url: str = config.OPENROUTER_BASE_URL,
        temperature: float | None = None,
        timeout: float = 120,
        extra_headers: dict[str, str] | None = None,
        http_post: Any | None = None,
    ) -> None:
        """Mesmos parâmetros de `OpenAICompatProvider.__init__`, com
        `base_url` default `config.OPENROUTER_BASE_URL`. `extra_headers`
        recebido aqui é MESCLADO com `config.OPENROUTER_HEADERS_ATRIBUICAO`
        (headers de atribuição do OpenRouter) -- se o chamador passar um
        header com o MESMO nome, o valor do chamador vence (mesclado por
        cima)."""
        headers_atribuicao = dict(config.OPENROUTER_HEADERS_ATRIBUICAO)
        if extra_headers:
            headers_atribuicao.update(extra_headers)
        super().__init__(
            api_key,
            model,
            base_url=base_url,
            temperature=temperature,
            timeout=timeout,
            extra_headers=headers_atribuicao,
            http_post=http_post,
        )

    def _montar_corpo_extra(self) -> dict[str, Any]:
        # `usage: {include: true}` -- pede ao OpenRouter para incluir o
        # custo REAL (USD) da chamada na própria resposta (`usage.cost`) --
        # ver `_extrair_custo` abaixo.
        return {"usage": {"include": True}}

    def _extrair_custo(self, payload: dict[str, Any]) -> float | None:
        # DEFENSIVO -- `None` se `usage`/`cost` ausente (nunca levanta por
        # causa de metadado de custo, mesma disciplina da extração de
        # tokens na classe base).
        usage = payload.get("usage") or {}
        custo = usage.get("cost")
        return float(custo) if custo is not None else None

    def aceita_pdf(self) -> bool:
        modelo = str(self._model or "").lower()
        return modelo.startswith(PREFIXOS_COM_PDF_NATIVO)

    def _corpo_para_anexos(self, anexos: list[Any]) -> dict[str, Any]:
        # Leitura NATIVA, dita explicitamente. Sem o plugin, um modelo que
        # não lê PDF cairia no OCR pago do OpenRouter sem ninguém ter decidido
        # isso -- ver `PREFIXOS_COM_PDF_NATIVO`. Imagem não precisa de plugin.
        if any(getattr(a, "mime", "") == "application/pdf" for a in anexos):
            return {"plugins": [{"id": "file-parser", "pdf": {"engine": "native"}}]}
        return {}


# =============================================================================
# listar_modelos() -- catálogo de modelos do OpenRouter, com cache local em
# disco (insumo do CP 3.3, sem consumidor de produção ainda). `GET
# {base_url}/models` -- devolve a lista de dicts de modelo (id/name/pricing/
# etc., o que a API devolver).
# =============================================================================
def listar_modelos(
    api_key: str | None,
    *,
    base_url: str = config.OPENROUTER_BASE_URL,
    cache_path: str | os.PathLike[str] | None = None,
    ttl_segundos: float = 86400,
    http_get: Any | None = None,
    time_fn: Any | None = None,
) -> list[dict[str, Any]]:
    """Devolve o catálogo de modelos do OpenRouter (`GET {base_url}/models`),
    com cache local em disco.

    Parâmetros:
      api_key: chave `Bearer` -- repassada no header `Authorization` (o
        endpoint de catálogo do OpenRouter não exige autenticação hoje, mas
        o header é enviado por uniformidade/futuro-proofing; `None`/vazio
        ainda monta `Authorization: Bearer <vazio>`, o endpoint decide).
      base_url: raiz do endpoint -- default `config.OPENROUTER_BASE_URL`.
      cache_path: caminho do arquivo JSON de cache -- default
        `config.OPENROUTER_CATALOGO_CACHE` (caminho relativo, mesmo padrão
        de `config.CONFIG_FILE`).
      ttl_segundos: tempo de vida do cache -- default 1 dia (86400s).
      http_get: injeção de dependência para teste -- se `None` (default,
        uso real), importa `requests` de forma PREGUIÇOSA e usa
        `requests.get`. Assinatura esperada: `http_get(url, headers=...,
        timeout=...) -> objeto com .raise_for_status()/.json()`.
      time_fn: injeção de dependência para teste (relógio) -- se `None`,
        usa `time.time`.

    Comportamento de cache/degradação:
      - cache AUSENTE ou EXPIRADO (mais velho que `ttl_segundos`): tenta
        `GET /models`. Em caso de SUCESSO, grava o cache (lista + carimbo de
        tempo) e devolve a lista nova.
      - cache DENTRO do TTL: devolve o cache SEM tocar na rede.
      - falha de rede (qualquer exceção do `http_get`/`.raise_for_status()`)
        COM cache disponível (mesmo expirado): DEGRADA graciosamente --
        devolve o cache, sem levantar.
      - falha de rede SEM nenhum cache disponível: levanta a exceção
        original (não há nada para degradar para).
    """
    caminho = cache_path if cache_path is not None else config.OPENROUTER_CATALOGO_CACHE
    agora_fn = time_fn if time_fn is not None else time.time

    cache = _ler_cache(caminho)
    if cache is not None and (agora_fn() - cache["timestamp"]) < ttl_segundos:
        return cache["modelos"]

    try:
        modelos = _buscar_modelos_da_rede(api_key, base_url, http_get)
    except Exception:
        if cache is not None:
            return cache["modelos"]
        raise

    _gravar_cache(caminho, modelos, agora_fn())
    return modelos


def _buscar_modelos_da_rede(
    api_key: str | None, base_url: str, http_get: Any | None
) -> list[dict[str, Any]]:
    if http_get is not None:
        get = http_get
    else:
        # `rede.get`, e não `requests.get`: com a VPN ligada a chamada direta
        # morre por timeout (a rede só publica PAC). Import preguiçoso -- ver
        # docstring do módulo.
        from sigft.core import rede

        get = rede.get

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{base_url.rstrip('/')}/models"
    resp = get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    return payload.get("data", []) if isinstance(payload, dict) else list(payload)


def _ler_cache(caminho: str | os.PathLike[str]) -> dict[str, Any] | None:
    if not os.path.exists(caminho):
        return None
    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            conteudo = json.load(arquivo)
        return {"timestamp": float(conteudo["timestamp"]), "modelos": conteudo["modelos"]}
    except Exception:
        return None


def _gravar_cache(
    caminho: str | os.PathLike[str], modelos: list[dict[str, Any]], timestamp: float
) -> None:
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump({"timestamp": timestamp, "modelos": modelos}, arquivo, ensure_ascii=False)
