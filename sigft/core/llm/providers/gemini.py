r"""
sigft/core/llm/providers/gemini.py — `GeminiProvider`: ÚNICA classe do
projeto que importa `google.generativeai` (Checkpoint 3.1 do plano de
refatoração; estendido no Checkpoint 3.2 — `ProviderResult` no lugar de
tupla crua + `temperature` opcional, preservando o `temperature=0.1` que o
LangChain aplicava em `autospec_backend` antes de ser removido — ver
docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.2 e PENDENCIAS.md).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.1: "O provedor
Gemini direto reproduz o comportamento atual (transport REST, mesmos
modelos default) — menor risco na migração e preserva o free tier do AI
Studio"; *Aceite*: "`genai.` só aparece em `providers/gemini.py`". Depois
deste checkpoint, `google.generativeai`/`genai` NÃO aparece mais em
`analyzer_backend.py`, `cria_fichas_no_pmib_v1_backend.py`,
`upload_conditions_backend.py` nem `upload_tech_specs_backend.py` — só aqui.

`GeminiProvider` implementa o único método que `sigft.core.llm.client.
LLMClient` precisa de um provider: `generate_raw(prompt, *, system=None,
json_mode=False) -> (texto, tokens_in, tokens_out)`. NÃO faz retry, NÃO
aplica rate-limit, NÃO faz parse de JSON — todas as 3 responsabilidades já
ficam no `LLMClient` (ver docstring de `core/llm/client.py`); este módulo só
sabe conversar com o SDK do Gemini.

DECISÃO — `safety_settings` BLOCK_NONE aplicado a TODA chamada, para as 5
tarefas (registrada em docs/refatoracao/PENDENCIAS.md como mudança de
comportamento DELIBERADA, não uma "equivalência estrita" — o próprio CP 3.1
aceita isso como "equivalência provável", ver plano linha ~310): hoje só
`upload_conditions_backend`/`upload_tech_specs_backend` configuram
`safety_settings` (BLOCK_NONE nas 4 categorias); `analyzer_backend`
(`validar_ficha`) e `cria_fichas_no_pmib_v1_backend`
(`categorizar_pdm`) ficam no default do Gemini (mais restritivo) hoje. Este
provider aplica o MESMO dict `SAFETY_SETTINGS_BLOCK_NONE` em TODA chamada,
para as 5 tarefas — é exatamente o que "safety_settings ficam AQUI, uma vez"
pede. Mudança de UMA DIREÇÃO SÓ: BLOCK_NONE só pode fazer o modelo bloquear
MENOS conteúdo do que hoje, NUNCA mais — não introduz nenhuma falha nova em
`validar_ficha`/`categorizar_pdm` que não existisse antes (na pior hipótese,
deixa de acontecer um bloqueio raro que já era indesejado, já que o material
processado é sempre ficha técnica de equipamento industrial, nunca conteúdo
que o Gemini bloquearia por SEXUALLY_EXPLICIT/DANGEROUS/etc. em condições
normais).

Testabilidade — import PREGUIÇOSO de `google.generativeai` (mesma convenção
já estabelecida em `core/excel/status_sheet.py` para `openpyxl`: dependência
pesada de produção, importada só dentro do método/`__init__` que precisa
dela, não no topo do módulo) + `genai_module` INJETÁVEL (mesmo padrão de
`driver`/`wait` em `SeleniumEngine`, `dialog_fn` em `app/file_dialogs.py`,
`sleep_fn` em `core/excel/locking.py`): nos testes, um objeto FAKE com
`.configure(...)` e `.GenerativeModel(...)` (devolvendo um objeto fake com
`.generate_content(...)` programável) substitui o SDK real, sem precisar de
`google-generativeai` instalado nem de rede.
"""

from __future__ import annotations

from typing import Any

from sigft.core.llm.client import ProviderResult

# Dict ÚNICO de safety_settings, aplicado a TODA chamada -- ver decisão no
# docstring do módulo. Réplica EXATA do dict já usado hoje em
# `upload_conditions_backend.processar_ia_lote`/
# `upload_tech_specs_backend._chamar_gemini_specs` (4 categorias, todas
# BLOCK_NONE) -- só passa a ser aplicado também às outras 2 tarefas que não
# o tinham.
SAFETY_SETTINGS_BLOCK_NONE: dict[str, str] = {
    "HATE_SPEECH": "BLOCK_NONE",
    "HARASSMENT": "BLOCK_NONE",
    "SEXUALLY_EXPLICIT": "BLOCK_NONE",
    "DANGEROUS": "BLOCK_NONE",
}


class GeminiProvider:
    """Provider Gemini direto -- `transport='rest'` (redes corporativas com
    proxy, mesma configuração de hoje nas 4 classes migradas), um
    `GenerativeModel` NOVO por chamada (mesmo padrão de hoje: nenhuma das 4
    classes reaproveitava a instância de `GenerativeModel` entre chamadas).
    """

    def __init__(
        self,
        api_key: str | None,
        model: str,
        *,
        genai_module: Any | None = None,
        temperature: float | None = None,
    ) -> None:
        """
        Parâmetros:
          api_key: chave da API Gemini. Réplica do guard já usado hoje nas 4
            classes (`if self.api_key: genai.configure(...)`): só chama
            `.configure(...)` se `api_key` for truthy -- uma chave
            vazia/`None` NÃO configura o SDK (mesmo comportamento de
            `GeminiCategorizer.__init__` hoje, que só emite um aviso em
            stdout nesse caso -- aviso esse que continua vivendo no
            CONSUMIDOR, não neste provider).
          model: nome do modelo (ex.: `"gemini-3.1-pro-preview"`) -- vem de
            `config.LLM_MODELOS_HOJE` via `get_llm()`, nunca hardcoded aqui.
          genai_module: injeção de dependência para teste -- se `None`
            (default, uso real), importa `google.generativeai` de forma
            PREGUIÇOSA (só neste `__init__`, nunca no topo do módulo -- ver
            docstring do módulo).
          temperature (CP 3.2, keyword-only): quando não `None`, entra em
            `generation_config` de TODA chamada de `generate_raw` (mesclado
            com `response_mime_type` quando `json_mode=True` -- ver
            `generate_raw` abaixo). `None` (default) = não enviar nada,
            preservando o comportamento de hoje das 4 tarefas que nunca
            setavam temperature; só `autospec` passa `0.1` (via
            `get_llm`/`_POLITICA_RETRY_POR_TAREFA`), reproduzindo o
            `temperature=0.1` que `ChatGoogleGenerativeAI` aplicava antes da
            remoção do LangChain (ver docs/refatoracao/PENDENCIAS.md).
        """
        if genai_module is not None:
            self._genai = genai_module
        else:
            import google.generativeai as genai  # import preguiçoso -- ver docstring do módulo

            self._genai = genai
        self._model = model
        self._temperature = temperature
        if api_key:
            self._genai.configure(api_key=api_key, transport="rest")

    def generate_raw(
        self, prompt: str, *, system: str | None = None, json_mode: bool = False
    ) -> ProviderResult:
        """Chama `GenerativeModel(...).generate_content(prompt)` uma única
        vez (SEM retry -- responsabilidade do `LLMClient` chamador) e
        devolve um `ProviderResult` (CP 3.2 -- `custo_usd` sempre `None`
        aqui: Gemini direto não informa custo por chamada).

        `system_instruction` só é passado ao `GenerativeModel` quando
        `system` não é `None` (nenhuma das 4 chamadas de hoje passa uma
        system instruction "vazia" propositalmente -- `analyzer_backend`/
        `cria_fichas_no_pmib_v1_backend` nunca passavam nenhuma;
        `upload_conditions_backend`/`upload_tech_specs_backend` sempre
        passavam a sua). `safety_settings` (`SAFETY_SETTINGS_BLOCK_NONE`) é
        SEMPRE passado -- ver decisão no docstring do módulo.

        `generation_config` (CP 3.2 -- MESCLADO, nunca sobrescrito): recebe
        `{"response_mime_type": "application/json"}` quando `json_mode=True`
        (réplica exata de `upload_tech_specs_backend._chamar_gemini_specs`,
        a única das 4 chamadas que usa JSON mode nativo hoje) e/ou
        `{"temperature": self._temperature}` quando `self._temperature` não
        é `None` -- as 4 combinações (com/sem temperature × com/sem
        json_mode) são cobertas em `tests/test_llm_gemini_provider.py`.
        `generation_config` só é passado ao `GenerativeModel` se pelo menos
        uma das 2 chaves estiver presente (dict vazio nunca é enviado).

        `tokens_in`/`tokens_out`: capacidade NOVA (nenhum dos 4 consumidores
        de hoje lê tokens) -- lidos de forma DEFENSIVA via
        `resp.usage_metadata` (`prompt_token_count`/`candidates_token_count`);
        `None` para qualquer um dos dois (ou ambos) se `usage_metadata` não
        existir ou não tiver o atributo esperado, sem levantar exceção por
        causa disso -- a resposta de texto em si nunca é sacrificada por uma
        falha ao ler metadados de uso.
        """
        kwargs: dict[str, Any] = {"safety_settings": SAFETY_SETTINGS_BLOCK_NONE}
        if system is not None:
            kwargs["system_instruction"] = system

        generation_config: dict[str, Any] = {}
        if json_mode:
            generation_config["response_mime_type"] = "application/json"
        if self._temperature is not None:
            generation_config["temperature"] = self._temperature
        if generation_config:
            kwargs["generation_config"] = generation_config

        modelo = self._genai.GenerativeModel(self._model, **kwargs)
        resp = modelo.generate_content(prompt)

        texto = resp.text
        usage = getattr(resp, "usage_metadata", None)
        tokens_in = getattr(usage, "prompt_token_count", None) if usage is not None else None
        tokens_out = getattr(usage, "candidates_token_count", None) if usage is not None else None
        return ProviderResult(texto, tokens_in, tokens_out)
