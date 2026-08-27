r"""
sigft/core/llm/providers/openai_compat.py — `OpenAICompatProvider`: base
para QUALQUER endpoint OpenAI-compatível (Checkpoint 3.2 do plano de
refatoração).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.2: "O adaptador
genérico cobre a futura IA interna da empresa (`EMPRESA_LLM_BASE_URL` +
`EMPRESA_LLM_API_KEY`) e qualquer provedor direto OpenAI-compatível."
`providers/openrouter.py` (mesmo checkpoint) ESPECIALIZA esta classe.

DECISÃO — `requests`, NÃO o pacote `openai` (divergência do texto do plano,
registrada em docs/refatoracao/PENDENCIAS.md): a superfície usada é um único
`POST /chat/completions`, que não justifica instalar o SDK oficial. `requests`
já é dependência de PRODUÇÃO (`requirements.txt`, usado por
`autospec_backend.WebSearcher`/`_download_file`) — não adiciona peso novo ao
empacotamento PyInstaller, ao contrário do que instalar mais um SDK faria
(o próprio CP 3.2 descarta o LangChain por essa mesma razão de peso).

Contrato com `LLMClient` (ver `core/llm/client.py`): `generate_raw(prompt, *,
system=None, json_mode=False) -> ProviderResult`. NÃO faz retry, NÃO faz
parse de JSON -- essas responsabilidades ficam no `LLMClient` (mesmo padrão
de `providers/gemini.py`). `safety_settings` NÃO tem equivalente no
protocolo OpenAI-compatível -- diferença registrada em PENDENCIAS.md (é
exatamente o que o Aceite deste checkpoint pede: "comportamento de safety
... com diferenças registradas em PENDENCIAS").

Testabilidade -- import PREGUIÇOSO de `requests` (mesma convenção já
estabelecida em `core/excel/status_sheet.py` para `openpyxl` e em
`core/llm/providers/gemini.py` para `google.generativeai`) + `http_post`
INJETÁVEL (mesmo padrão de `genai_module` em `GeminiProvider`, `dialog_fn`
em `app/file_dialogs.py`, `sleep_fn` em `core/excel/locking.py`): nos testes,
uma função FAKE que grava a chamada (`url`/`headers`/`json`) e devolve um
objeto com `.raise_for_status()`/`.json()` substitui `requests.post`, sem
precisar de rede nem do pacote `requests` instalado.
"""

from __future__ import annotations

from typing import Any

from sigft.core.llm.client import ProviderResult


class OpenAICompatProvider:
    """Provider genérico para QUALQUER endpoint `POST {base_url}/chat/
    completions` no formato OpenAI (`messages`, `choices[0].message.content`,
    `usage.prompt_tokens`/`completion_tokens`).
    """

    def __init__(
        self,
        api_key: str | None,
        model: str,
        *,
        base_url: str,
        temperature: float | None = None,
        timeout: float = 120,
        extra_headers: dict[str, str] | None = None,
        http_post: Any | None = None,
    ) -> None:
        """
        Parâmetros:
          api_key: chave `Bearer` do endpoint. Repassada tal qual no header
            `Authorization` (sem guard de "não configurar nada" como o
            `GeminiProvider` -- este provider não tem um `.configure(...)`
            de SDK para pular; uma chave `None`/vazia ainda monta o header
            `Authorization: Bearer <vazio>`, e é o endpoint remoto quem
            decide se rejeita).
          model: nome do modelo, vai no corpo (`"model": self._model`) --
            vem de `config.LLM_MODELOS_HOJE`/`LLM_TASKS` via `get_llm()`,
            nunca hardcoded aqui.
          base_url: raiz do endpoint (ex.: `"https://openrouter.ai/api/v1"`
            ou a URL da futura IA interna da empresa,
            `EMPRESA_LLM_BASE_URL`). `/` final tolerado (removido via
            `.rstrip("/")` antes de montar a URL final).
          temperature (keyword-only): quando não `None`, entra no corpo da
            requisição (`"temperature": self._temperature`). `None`
            (default) = não enviar nada, deixando o default do endpoint.
          timeout: segundos repassados a `requests.post(..., timeout=...)`.
          extra_headers: headers ADICIONAIS mesclados aos 2 padrão
            (`Authorization`/`Content-Type`) -- usado por
            `OpenRouterProvider` para os headers de atribuição
            (`HTTP-Referer`/`X-Title`).
          http_post: injeção de dependência para teste -- se `None`
            (default, uso real), importa `requests` de forma PREGUIÇOSA (só
            neste método, nunca no topo do módulo) e usa `requests.post`.
        """
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._temperature = temperature
        self._timeout = timeout
        self._extra_headers = dict(extra_headers) if extra_headers else {}
        self._http_post = http_post

    # ------------------------------------------------------------------
    # Hooks de extensão para subclasses (ver `providers/openrouter.py`) --
    # evita que `OpenRouterProvider` precise duplicar `generate_raw` inteiro
    # só para trocar o corpo da requisição/a leitura do custo.
    # ------------------------------------------------------------------
    def _montar_corpo_extra(self) -> dict[str, Any]:
        """Campos ADICIONAIS mesclados ao corpo da requisição, além de
        `model`/`messages`/`temperature`/`response_format` (que a base já
        monta). Base devolve `{}` (nenhum campo extra); `OpenRouterProvider`
        sobrescreve para incluir `"usage": {"include": True}`."""
        return {}

    def _extrair_custo(self, payload: dict[str, Any]) -> float | None:
        """Lê o custo REAL (USD) da resposta JSON já decodificada, quando o
        endpoint informar. Base devolve sempre `None` (nenhum endpoint
        OpenAI-compatível genérico garante isso); `OpenRouterProvider`
        sobrescreve para ler `usage.cost`."""
        return None

    # ------------------------------------------------------------------
    def generate_raw(
        self, prompt: str, *, system: str | None = None, json_mode: bool = False
    ) -> ProviderResult:
        """Monta e envia UM `POST {base_url}/chat/completions` (SEM retry --
        responsabilidade do `LLMClient` chamador) e devolve um
        `ProviderResult`.

        `messages`: `[{"role": "system", "content": system}]` SÓ quando
        `system is not None`, seguido sempre de
        `{"role": "user", "content": prompt}` (mesma convenção "só passa se
        não for `None`" já usada por `GeminiProvider.generate_raw` para
        `system_instruction`).

        `response_format: {"type": "json_object"}` -- equivalente OpenAI-
        compatível do `response_mime_type` do Gemini -- SÓ quando
        `json_mode=True`.

        `resp.raise_for_status()` é chamado ANTES de ler o corpo: deixa
        erro HTTP virar exceção, propagada para o `LLMClient` chamador
        tratar como qualquer outra falha de tentativa (retry/re-raise) --
        este provider NÃO faz retry por conta própria.

        Extração de tokens (`usage.prompt_tokens`/`usage.completion_tokens`)
        é DEFENSIVA (`.get(...)` encadeado, `None` se ausente) -- NUNCA
        levanta por causa de metadado de uso ausente/incompleto.
        """
        messages: list[dict[str, str]] = []
        if system is not None:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body: dict[str, Any] = {"model": self._model, "messages": messages}
        if self._temperature is not None:
            body["temperature"] = self._temperature
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        body.update(self._montar_corpo_extra())

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        headers.update(self._extra_headers)

        if self._http_post is not None:
            post = self._http_post
        else:
            import requests  # import preguiçoso -- ver docstring do módulo

            post = requests.post

        url = f"{self._base_url.rstrip('/')}/chat/completions"
        resp = post(url, headers=headers, json=body, timeout=self._timeout)
        resp.raise_for_status()
        payload = resp.json()

        texto = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage") or {}
        tokens_in = usage.get("prompt_tokens")
        tokens_out = usage.get("completion_tokens")
        custo_usd = self._extrair_custo(payload)

        return ProviderResult(texto, tokens_in, tokens_out, custo_usd)
