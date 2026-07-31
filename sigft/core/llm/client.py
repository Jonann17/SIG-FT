r"""
sigft/core/llm/client.py — `LLMClient`/`LLMResponse` + fábrica `get_llm()`
(Checkpoint 3.1 do plano de refatoração; estendido nos Checkpoints 3.2 e 3.3).

NOTA DO CP 3.3 (o restante deste docstring é histórico dos CP 3.1/3.2,
mantido intacto abaixo): `get_llm(tarefa, ...)` ganha uma CADEIA DE
RESOLUÇÃO de provider/modelo — a seleção do usuário, persistida por
`core/llm/selecao.py` (painel "Modelos de IA" da Home), agora VENCE o
fallback embutido `config.LLM_MODELOS_HOJE` quando existir: (1) override da
TAREFA > (2) seleção GLOBAL > (3) `config.LLM_MODELOS_HOJE[tarefa]` — o
MESMO fallback de antes, preservado por decisão explícita do arquiteto ("sem
downgrade silencioso", docs/refatoracao/MODELOS_IA.md §5): instalar esta
versão NÃO troca o modelo de ninguém que nunca abriu o painel novo. Novo
parâmetro keyword-only `selecao_resolvida: dict | None = None` permite
injetar o resultado já resolvido em teste, pulando a leitura de disco;
quando ausente, lê `config.CONFIG_FILE` — o MESMO arquivo das chaves de
API — via `selecao.resolver(tarefa, config_path=config.CONFIG_FILE)`, ao
vivo, uma vez por chamada (é o que dá o efeito "imediato, sem reiniciar o
app": os 5 consumidores de IA constroem um `LLMClient` novo, via `get_llm`,
a cada execução de módulo — ver docstring de `get_llm()` mais abaixo).
`config.LLM_TASKS`/`LLM_DEFAULT` continuam SEM leitura direta aqui — só
entram em jogo quando o usuário aciona "Aplicar recomendados" na UI, que os
GRAVA como seleção via `selecao.aplicar_recomendados()`; a partir daí passam
a ser lidos pelo passo (2) acima, como qualquer outra seleção salva. Ver
docs/refatoracao/PENDENCIAS.md.

NOTA DO CP 3.2 (histórico, mantido intacto): o contrato de provider foi
GENERALIZADO de uma tupla crua `(texto, tokens_in, tokens_out)` para
`ProviderResult` (`NamedTuple` com `custo_usd` adicional, default `None`) —
ver classe `ProviderResult` abaixo e `providers/openrouter.py` (único
provider que preenche `custo_usd` com valor REAL). `get_llm()` também passou
a rotear 3 providers (`gemini`/`openrouter`/`openai_compat`) e a repassar
`temperature` por tarefa — ver docstring de `get_llm()` e
`_POLITICA_RETRY_POR_TAREFA` mais abaixo, e docs/refatoracao/PENDENCIAS.md.

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.1, diagnóstico
seção 1.3 ("Duplicação e rigidez de IA"): "`genai.configure(transport=
'rest')` + `GenerativeModel` + retry | 5×: `analyzer`, `cria_fichas`,
`upload_conditions`, `tech_specs` (+ `autospec` via LangChain)"; "Limpeza da
resposta JSON (strip de ```` ```json ````, find `{`/`[`) | 4 variantes";
"`safety_settings` BLOCK_NONE | 2× copiado literal"; "**Acoplamento total ao
Gemini**: nomes de modelo hardcoded, sem abstração de provedor, sem medição
de tokens/custo | todos os 5 módulos com IA".

Este módulo é a camada "Nenhum serviço conhece o SDK de um provedor de IA —
só `LLMClient`" (princípio nº 4 da arquitetura-alvo do plano, seção 2).
`LLMClient` não sabe NADA de Gemini/OpenAI/OpenRouter — orquestra retry,
rate-limit OPCIONAL e parse/limpeza de JSON sobre um "provider" INJETADO
(mesmo padrão engine-por-baixo-de-uma-classe-de-orquestração já usado na
Fase 2: `PMIBPortal(engine)` sobre `RPAEngine`/`SeleniumEngine` — ver
`sigft/core/rpa/portal.py`/`engine.py`). O único provider que existe neste
checkpoint é `providers.gemini.GeminiProvider` (CP 3.2 adiciona
`openai_compat`/`openrouter`); o contrato que QUALQUER provider precisa
cumprir é um único método: `generate_raw(prompt, *, system=None,
json_mode=False) -> (texto: str, tokens_in: int | None, tokens_out: int |
None)` — sem `try/except`, sem retry, sem parse de JSON: essas 3
responsabilidades ficam TODAS aqui, uma vez só (é o que o checkpoint pede
explicitamente: "retry, rate-limit opcional, parse/limpeza de JSON e
safety_settings ficam AQUI, uma vez").

IMPORTANTE — isto NÃO é uma refatoração 1:1 ("delega o corpo, mantém tudo
igual") como os checkpoints anteriores da Fase 2: os 4 consumidores diretos
de `google.generativeai` tinham cada um o PRÓPRIO laço de retry (`for _ in
range(3): ... time.sleep(N)`); esses laços são REMOVIDOS dos 4 arquivos (não
apenas "movidos para trás de uma chamada") porque `LLMClient.generate()`
abaixo já retenta sozinho — ver os 4 consumidores migrados
(`analyzer_backend.DatasheetAnalyzer._call_gemini_api`,
`cria_fichas_no_pmib_v1_backend.GeminiCategorizer.processar_lote`,
`upload_conditions_backend.ConditionsProcessor.processar_ia_lote`,
`upload_tech_specs_backend.TechSpecsProcessor._chamar_gemini_specs`).

DECISÃO — `get_llm(tarefa, api_key)` resolve o modelo via
`config.LLM_MODELOS_HOJE`, NÃO via `config.LLM_TASKS` (registrada em
docs/refatoracao/PENDENCIAS.md): o texto do plano diz "Fábrica `get_llm
(tarefa)` resolve provedor/modelo via `config.LLM_TASKS`", mas o PRÓPRIO
*Aceite* deste checkpoint exige "comportamento atual preservado (mesmos
modelos default de hoje)" e que "a troca para os defaults econômicos de
`MODELOS_IA.md` NÃO acontece aqui". `config.LLM_TASKS` já contém os modelos
DECIDIDOS (Gemini 3 Flash Preview padrão; Grok 4.5 em `categorizar_pdm`) —
resolver por ali trocaria de modelo assim que os 4 consumidores fossem
migrados, violando o Aceite. `config.LLM_MODELOS_HOJE` existe especificamente
como "a referência de EQUIVALÊNCIA do CP 3.1" (ver `sigft/config.py`, seção
6) — é o que este módulo lê. `LLM_TASKS`/`LLM_DEFAULT` ficam RESERVADOS para
o CP 3.3 (seleção de modelo na interface, com validação do usuário).

ATUALIZAÇÃO CP 3.3 — o CP 3.3 chegou: `config.LLM_MODELOS_HOJE` CONTINUA
sendo o fallback embutido (ver "NOTA DO CP 3.3" no topo do docstring —
decisão explícita "sem downgrade silencioso" do arquiteto, não uma
reinterpretação do Aceite deste CP 3.1). `config.LLM_TASKS`/`LLM_DEFAULT`
passam a ser lidos, mas nunca DIRETAMENTE por este módulo — só
indiretamente, através de `selecao.aplicar_recomendados()` (que os GRAVA
como seleção quando o usuário clica "Aplicar recomendados" na UI); a partir
daí eles chegam a `get_llm()` pelo MESMO caminho de qualquer seleção salva
manualmente (`selecao.resolver()`), sem tratamento especial.

DECISÃO — `get_llm(tarefa, api_key)` recebe `api_key` como parâmetro
explícito (a assinatura de UM argumento sugerida pelo texto do plano seria
`get_llm(tarefa)`), registrada em docs/refatoracao/PENDENCIAS.md: as 4
classes migradas continuam recebendo a chave via `__init__(self, api_key)`
exatamente como hoje (`self.controller.get_key("GEMINI")` em `frontend.py`,
INTOCADO) — inventar um segundo caminho de carregamento de chave dentro de
`get_llm` duplicaria essa responsabilidade sem necessidade.

TABELA DE POLÍTICA DE RETRY/RATE-LIMIT POR TAREFA (`_POLITICA_RETRY_POR_TAREFA`
abaixo — hardcoded aqui, NÃO em `config.py`, porque é uma decisão de
ORQUESTRAÇÃO da camada de IA, não um dado de configuração de negócio):

    Tarefa            | max_retries | tentativas totais | sleep  | rate-limit
    ------------------|-------------|--------------------|--------|------------
    categorizar_pdm   | 0           | 1 (SEM retry)      | N/A    | não
    validar_ficha     | 2           | 3                  | 5s     | 60s
    condicoes         | 2           | 3                  | 30s    | não
    tech_specs        | 2           | 3                  | 2s     | não
    autospec          | 2           | 3                  | 5s     | 60s (*)

(*) `autospec` usa LangChain hoje (fora de escopo deste CP — ver
docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.2), sem consumidor
real de `get_llm("autospec", ...)` ainda; a política escolhida é a MESMA de
`validar_ficha` (nenhuma informação melhor disponível — ver PENDENCIAS.md),
só para que a chamada não quebre.

`max_retries` é o número de RETENTATIVAS (não o total de tentativas!):
tentativas totais = `max_retries + 1`. `retry_sleep_seconds` é dormido entre
CADA tentativa que falhar (inclusive a penúltima->última) — TODA falha
(exceção de rede/API OU resposta que não parseia como JSON) dorme o mesmo
tempo, de forma UNIFORME. Isso é uma simplificação de baixo impacto e
DOCUMENTADA (ver PENDENCIAS.md) em relação a 2 dos 4 originais: hoje
`upload_tech_specs` NÃO dorme quando a resposta vem VAZIA (só em exceção) e
`upload_conditions` só dorme se NÃO for a última tentativa (otimização que
`LLMClient` também replica adiante — ver `generate()` abaixo — mas de forma
uniforme para os 2 tipos de falha, não só para exceção "de verdade").

DECISÃO — `safety_settings` BLOCK_NONE aplicado UNIFORMEMENTE às 5 tarefas
(registrada em PENDENCIAS.md): hoje só `condicoes`/`tech_specs` configuram
`safety_settings`; `categorizar_pdm`/`validar_ficha`/`autospec` ficam no
default (mais restritivo) do Gemini. O provider (`providers/gemini.py`)
passa a aplicar o MESMO dict BLOCK_NONE em TODA chamada — mudança de UMA
DIREÇÃO SÓ (só pode fazer o modelo bloquear MENOS conteúdo do que hoje,
nunca mais) — ver docstring de `providers/gemini.py` para o dict exato.

Só stdlib (`time`, `json`, `dataclasses`) + `from sigft import config` —
importável no ambiente de teste sem `google-generativeai` instalado (ver
tests/conftest.py); nenhum provider concreto é importado no TOPO deste
módulo (só dentro de `get_llm()`, e só quando o provider resolvido for
`gemini` — ver `get_llm()` abaixo).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Callable, NamedTuple

from sigft import config

SleepFn = Callable[[float], None]
TimeFn = Callable[[], float]


class ProviderResult(NamedTuple):
    """Retorno de `provider.generate_raw(...)` (Checkpoint 3.2 — generaliza o
    contrato que nascia como tupla crua `(texto, tokens_in, tokens_out)` no
    CP 3.1).

    `custo_usd` só é preenchido por providers que informam custo REAL na
    própria resposta da API (`providers/openrouter.py`, via `usage.cost` —
    ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.2); os demais
    providers (`providers/gemini.py`, `providers/openai_compat.py`) deixam
    `None` — ESTIMAR custo por tabela de preços é capacidade do CP 3.4
    (`core/llm/usage.py`), fora de escopo aqui.

    É um `NamedTuple` (não uma `@dataclass`) de propósito: os 3 primeiros
    campos têm defaults `None`, então qualquer código/teste que já construía
    uma tupla de 3 elementos `(texto, tokens_in, tokens_out)` continua
    funcionando via `ProviderResult(*tupla_antiga)` sem precisar nomear
    `custo_usd` — ver `tests/test_llm_client.py::_FakeProvider` e
    `tests/test_llm_gemini_provider.py`.
    """

    text: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    custo_usd: float | None = None


@dataclass
class LLMResponse:
    """Formato de retorno ÚNICO de `LLMClient.generate()` — mesma forma
    para QUALQUER provider/tarefa, é o que permite os 4 consumidores pararem
    de conhecer o formato de resposta específico do SDK do Gemini.

    Campos:
      text: resposta CRUA (`resp.text` do Gemini hoje), antes de qualquer
        limpeza — útil para diagnóstico/log quando `parsed_json` falhar (não
        falha nesta versão: `generate()` propaga a exceção de parse, então
        um `LLMResponse` só existe em caso de SUCESSO — `text` aqui é a
        resposta que efetivamente parseou).
      parsed_json: `text` já limpo (fences ```` ```json ````/````` ``` `````
        removidas) e parseado via `json.loads` — ver `_limpar_e_parsear_json`
        abaixo. É o que os 4 consumidores migrados de fato usam.
      tokens_in / tokens_out: contagem de tokens de entrada/saída, quando o
        provider expuser (capacidade NOVA — nenhum dos 4 consumidores lê
        tokens hoje). `None` quando o provider não souber informar.
      custo_usd: custo REAL da chamada em USD quando o provider informar
        (`ProviderResult.custo_usd`, ver `providers/openrouter.py` — CP 3.2);
        `None` para providers que não expõem custo real (`gemini`,
        `openai_compat`). ESTIMAR custo por tabela de preços para esses
        casos é capacidade do CP 3.4 (`core/llm/usage.py`), fora de escopo
        aqui.
      model / provider: nome do modelo (ex.: `"gemini-3.1-pro-preview"`) e
        do provedor (ex.: `"gemini"`) que de fato atenderam esta chamada —
        ecoam o que `get_llm()` resolveu, para quem só tem o `LLMResponse`
        em mãos (ex.: um log) não precisar guardar isso à parte.
      duracao_s: duração (segundos) só da tentativa que teve SUCESSO (não
        soma o tempo das tentativas anteriores que falharam nem os sleeps
        de retry/rate-limit entre elas) — medida via o `time_fn` injetado em
        `LLMClient` (`time.time` por padrão).
    """

    text: str
    parsed_json: object | None
    tokens_in: int | None
    tokens_out: int | None
    custo_usd: float | None
    model: str
    provider: str
    duracao_s: float


class LLMClient:
    """Orquestra retry, rate-limit opcional e parse de JSON sobre um
    `provider` INJETADO (ver docstring do módulo para o racional completo e
    o paralelo com `PMIBPortal(engine)` da Fase 2).

    `provider` é DUCK-TYPED: só precisa responder a `generate_raw(prompt, *,
    system=None, json_mode=False) -> ProviderResult` (CP 3.2 — generaliza a
    tupla `(texto, tokens_in, tokens_out)` do CP 3.1) — sem
    fazer NENHUM retry/parse por conta própria (essas responsabilidades são
    exclusivamente deste `LLMClient`). Ver `providers/gemini.py` para a
    única implementação real que existe neste checkpoint.
    """

    def __init__(
        self,
        provider: object,
        *,
        provider_name: str,
        model: str,
        max_retries: int = 0,
        retry_sleep_seconds: float = 0,
        min_interval_seconds: float | None = None,
        sleep_fn: SleepFn = time.sleep,
        time_fn: TimeFn = time.time,
    ) -> None:
        """
        Parâmetros:
          provider: objeto com `generate_raw(...)` — ver docstring da classe.
          provider_name / model: só ECOADOS em `LLMResponse.provider`/
            `.model` (ver lá) — este `LLMClient` não usa esses 2 valores
            para NENHUMA decisão de comportamento.
          max_retries: número de RETENTATIVAS após a 1ª tentativa (NÃO o
            total de tentativas!) — total de tentativas = `max_retries + 1`.
            `0` = sem retry nenhum (1 tentativa só, propaga a exceção
            imediatamente em caso de falha, SEM dormir).
          retry_sleep_seconds: segundos dormidos (via `sleep_fn`) entre CADA
            tentativa que falhar e a próxima (nunca dorme depois da ÚLTIMA
            tentativa, já que não há próxima) — ver `generate()`.
          min_interval_seconds: se não `None`, impõe um intervalo MÍNIMO
            entre o INÍCIO de duas chamadas a `generate()` consecutivas
            NESTA instância (rate-limit "global" da tarefa, não por
            tentativa de retry — ver `_aplicar_rate_limit()` e o docstring
            de `generate()` para o racional de por que é medido a partir do
            INÍCIO da chamada anterior, replicando
            `analyzer_backend.DatasheetAnalyzer._call_gemini_api` hoje).
            `None` (default) = sem rate-limit.
          sleep_fn / time_fn: injetáveis para teste (mesmo padrão de
            `sleep_fn` em `core/excel/locking.py` — testes passam funções
            fake em vez de `time.sleep`/`time.time` reais, para rodar em
            milissegundos sem depender de tempo real).
        """
        self._provider = provider
        self._provider_name = provider_name
        self._model = model
        self._max_retries = max_retries
        self._retry_sleep_seconds = retry_sleep_seconds
        self._min_interval_seconds = min_interval_seconds
        self._sleep_fn = sleep_fn
        self._time_fn = time_fn
        self._last_call_time: float | None = None

    # ------------------------------------------------------------------
    # Propriedades read-only -- convenientes para inspeção (ex.: testes de
    # `get_llm()` conferindo a política resolvida; um futuro `usage.py`
    # lendo `model`/`provider_name` sem precisar que cada chamador repasse
    # de novo) -- nenhuma delas afeta o comportamento de `generate()`.
    # ------------------------------------------------------------------
    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model(self) -> str:
        return self._model

    @property
    def max_retries(self) -> int:
        return self._max_retries

    @property
    def retry_sleep_seconds(self) -> float:
        return self._retry_sleep_seconds

    @property
    def min_interval_seconds(self) -> float | None:
        return self._min_interval_seconds

    # ------------------------------------------------------------------
    # Rate-limit opcional -- réplica do padrão de
    # `analyzer_backend.DatasheetAnalyzer._call_gemini_api` de hoje: dorme
    # (se preciso) ANTES da chamada, uma única vez por `generate()` -- NÃO
    # entre as tentativas internas de retry (essas usam
    # `retry_sleep_seconds`, não isto).
    # ------------------------------------------------------------------
    def _aplicar_rate_limit(self) -> None:
        if self._min_interval_seconds is None:
            return
        agora = self._time_fn()
        if self._last_call_time is not None:
            decorrido = agora - self._last_call_time
            faltante = self._min_interval_seconds - decorrido
            if faltante > 0:
                self._sleep_fn(faltante)
        # Timestamp tomado DE NOVO (não reaproveita `agora`) -- mesma
        # sequência do original (`self.last_api_call_time = time.time()`
        # chamado DEPOIS do sleep, não antes): a janela da PRÓXIMA chamada
        # conta a partir de quando esta efetivamente começou a rodar, não
        # de quando foi apenas solicitada.
        self._last_call_time = self._time_fn()

    # ------------------------------------------------------------------
    # generate() -- a API pública citada pelo plano.
    # ------------------------------------------------------------------
    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        json_mode: bool = False,
        tags: dict[str, str] | None = None,
    ) -> LLMResponse:
        """Chama `self._provider.generate_raw(...)`, retentando até
        `max_retries` vezes em caso de QUALQUER exceção (erro de
        rede/API do provider OU resposta que não limpa/parseia como JSON —
        `_limpar_e_parsear_json` levantando conta como falha desta
        tentativa, igual a uma exceção do provider).

        Parâmetros:
          prompt: texto do usuário/instrução principal — repassado tal qual
            para o provider.
          system: system instruction/prompt opcional — repassado tal qual
            (provider decide como aplicá-lo; `None` = não enviar nenhum).
          json_mode: quando `True`, pede ao provider para forçar saída JSON
            nativa (quando o provider suportar — ver `providers/gemini.py`).
            Não substitui `_limpar_e_parsear_json` (que roda sempre, JSON
            mode ligado ou não — resposta em JSON mode também pode vir com
            espaço/formatação ao redor).
          tags: metadados livres (ex.: `{"modulo": ..., "tarefa": ...}`) —
            REPASSADO mas ainda SEM consumidor nesta versão (aceito só para
            já fixar a assinatura pedida pelo plano); o CP 3.4 (`usage.py`)
            é quem vai LER `tags` para gravar módulo/tarefa no registro de
            uso JSONL.

        Fluxo:
          1. `_aplicar_rate_limit()` -- uma vez, ANTES de qualquer
             tentativa (não repetido entre retries).
          2. Até `max_retries + 1` tentativas de
             `self._provider.generate_raw(...)` + `_limpar_e_parsear_json`.
             Na 1ª tentativa que tiver sucesso, retorna imediatamente um
             `LLMResponse` (não tenta as demais).
          3. Entre uma tentativa que falhou e a PRÓXIMA (se houver),
             dorme `retry_sleep_seconds` via `sleep_fn` -- nunca dorme
             depois da ÚLTIMA tentativa (não há para quê).
          4. Se TODAS as tentativas falharem, RE-LEVANTA a exceção da
             ÚLTIMA tentativa (a exceção ORIGINAL — de rede/API ou de
             parse —, não uma exceção genérica/wrapper) para quem chamou
             decidir o que fazer (os 4 consumidores migrados capturam isso
             com `except Exception` fino, preservando as mensagens de erro
             de cada um -- ver os 4 arquivos migrados).
        """
        tags = tags or {}
        self._aplicar_rate_limit()

        ultimo_erro: Exception | None = None
        for tentativa in range(self._max_retries + 1):
            inicio = self._time_fn()
            try:
                resultado = self._provider.generate_raw(
                    prompt, system=system, json_mode=json_mode,
                )
                parsed = _limpar_e_parsear_json(resultado.text)
                duracao = self._time_fn() - inicio
                return LLMResponse(
                    text=resultado.text,
                    parsed_json=parsed,
                    tokens_in=resultado.tokens_in,
                    tokens_out=resultado.tokens_out,
                    custo_usd=resultado.custo_usd,
                    model=self._model,
                    provider=self._provider_name,
                    duracao_s=duracao,
                )
            except Exception as e:  # noqa: BLE001
                # Qualquer falha (rede/API do provider OU parse de JSON)
                # aciona retry da mesma forma -- ver docstring do método.
                ultimo_erro = e
                if tentativa < self._max_retries:
                    self._sleep_fn(self._retry_sleep_seconds)

        assert ultimo_erro is not None  # max_retries >= 0 => loop roda >= 1x
        raise ultimo_erro


# =============================================================================
# _limpar_e_parsear_json -- implementação ÚNICA que substitui as 4 variantes
# divergentes de hoje (ver docstring do módulo). Cobre os 2 formatos que os
# 5 prompts do sistema pedem (objeto `{...}` -- `validar_ficha`/`condicoes`;
# lista `[...]` -- `categorizar_pdm`/`tech_specs`), estritamente MAIS
# ROBUSTA que cada variante isolada (só pode ter SUCESSO em mais casos,
# nunca menos -- ver comparação campo a campo abaixo):
#
#   - `analyzer_backend._call_gemini_api` (hoje): só `replace`+`strip` das
#     fences, SEM busca de colchete/chave nenhuma -- quebra se houver
#     qualquer prosa antes/depois do JSON.
#   - `cria_fichas_no_pmib_v1_backend.processar_lote` (hoje): busca `[`...`]`
#     primeiro; só cai no fallback (`replace`+`strip` de fence, SEM busca de
#     colchete) se não achar -- fallback frágil (`clean[7:-3]` assume um
#     formato exato de fence, sem tolerância a espaço/quebra de linha extra).
#   - `upload_conditions_backend._limpar_resposta_json` (hoje): `replace`+
#     `strip` das fences, DEPOIS busca `{`...`}` -- só cobre objeto, não
#     lista.
#   - `upload_tech_specs_backend._limpar_json_ia` (hoje): `replace`+`strip`
#     das fences, DEPOIS busca `[`...`]` -- só cobre lista, não objeto.
#
# Esta função sempre: (1) remove as fences PRIMEIRO; (2) procura o PRIMEIRO
# `{` OU `[` que aparecer no texto já limpo; (3) usa o fechamento
# correspondente (`}`/`]`) via `rfind` a partir dali. Cobre objeto E lista
# com a MESMA lógica, sem fallback frágil de slice fixo.
# =============================================================================
def _limpar_e_parsear_json(texto: str | None) -> object:
    """Limpa fences markdown (```` ```json ````/````` ``` `````) e recorta o
    primeiro objeto/lista JSON top-level do texto, depois faz `json.loads`.

    Levanta `ValueError` se `texto` for vazio/`None` (equivalente a uma
    resposta "sem conteúdo" da IA — nenhuma das 4 variantes originais tinha
    esse guard explícito de forma uniforme; aqui ele garante que uma
    resposta vazia sempre aciona o mesmo caminho de falha/retry que
    qualquer outro erro de parse, dentro de `LLMClient.generate()`).

    Deixa `json.JSONDecodeError` propagar quando o texto (já recortado) não
    for JSON válido — quem chama (`LLMClient.generate()`) trata isso como
    QUALQUER outra falha de tentativa (aciona retry/re-levanta ao final).
    """
    if not texto:
        raise ValueError("Resposta da IA veio vazia.")

    limpo = texto.replace("```json", "").replace("```", "").strip()

    inicio_obj = limpo.find("{")
    inicio_lista = limpo.find("[")
    candidatos = [i for i in (inicio_obj, inicio_lista) if i != -1]
    if candidatos:
        inicio = min(candidatos)
        fechamento = "}" if limpo[inicio] == "{" else "]"
        fim = limpo.rfind(fechamento)
        if fim != -1 and fim >= inicio:
            limpo = limpo[inicio : fim + 1]

    return json.loads(limpo)


# =============================================================================
# get_llm() -- fábrica citada pelo plano ("Fábrica `get_llm(tarefa)` resolve
# provedor/modelo via `config.LLM_TASKS`" no texto do checkpoint; ver
# docstring do módulo para a decisão de usar `config.LLM_MODELOS_HOJE` em vez
# disso, exigida pelo próprio Aceite do CP 3.1).
#
# CP 3.2: `get_llm` passa a rotear 3 providers (`gemini`/`openrouter`/
# `openai_compat`) -- ver `providers/openrouter.py`/`providers/
# openai_compat.py`. `LLM_MODELOS_HOJE` continua intocado (todas as 5
# tarefas continuam em `gemini` em produção -- ver PENDENCIAS.md); os
# providers novos existem e são testáveis, mas sem consumidor real ainda.
#
# CP 3.3: `get_llm` ganha a CADEIA DE RESOLUÇÃO descrita na "NOTA DO CP 3.3"
# no topo do docstring do módulo -- seleção do usuário (via
# `core/llm/selecao.py`, keyword-only `selecao_resolvida` injetável em
# teste) VENCE `LLM_MODELOS_HOJE[tarefa]` quando existir. `LLM_MODELOS_HOJE`
# continua sendo o FALLBACK (não muda de fonte); a validação de `tarefa`
# continua feita contra `LLM_MODELOS_HOJE` ANTES de qualquer leitura de
# seleção; a política de retry/rate-limit/temperature continua vindo de
# `_POLITICA_RETRY_POR_TAREFA[tarefa]` -- por TAREFA, nunca pela seleção/
# modelo -- ver docstring de `get_llm()` abaixo.
# =============================================================================

# Política de retry/rate-limit/temperature por tarefa -- ver tabela no
# docstring do módulo. Hardcoded AQUI (não em `sigft/config.py`): é uma
# decisão de ORQUESTRAÇÃO da camada de IA (quantas vezes retentar, quanto
# dormir, com que temperatura), não um dado de configuração de negócio como
# modelo/preço/provider (que SIM vivem em `config.py`). Uma entrada por
# tarefa de `config.LLM_MODELOS_HOJE` (as mesmas 5: `categorizar_pdm`,
# `validar_ficha`, `condicoes`, `tech_specs`, `autospec`) -- ver
# `test_llm_get_llm_factory.py`/`test_llm_client.py` para o teste que trava
# esse invariante.
#
# `temperature` (CP 3.2): preserva o `temperature=0.1` que
# `ChatGoogleGenerativeAI(..., temperature=0.1)` aplicava em
# `autospec_backend.AutoSpecCore.__init__` ANTES da remoção do LangChain
# (extração estruturada, baixa aleatoriedade -- escolha deliberada, seria
# PERDIDA numa migração ingênua). `None` nas outras 4 tarefas = não enviar
# nada ao provider (default do SDK/API) -- preserva exatamente o
# comportamento de hoje, que nunca setava temperature. É retirado do dict de
# política ANTES de construir o `LLMClient` (que não aceita esse parâmetro)
# e passado ao construtor do provider.
_POLITICA_RETRY_POR_TAREFA: dict[str, dict[str, object]] = {
    "categorizar_pdm": {
        "max_retries": 0,
        "retry_sleep_seconds": 0,
        "min_interval_seconds": None,
        "temperature": None,
    },
    "validar_ficha": {
        "max_retries": 2,
        "retry_sleep_seconds": 5,
        "min_interval_seconds": 60,
        "temperature": None,
    },
    "condicoes": {
        "max_retries": 2,
        "retry_sleep_seconds": 30,
        "min_interval_seconds": None,
        "temperature": None,
    },
    "tech_specs": {
        "max_retries": 2,
        "retry_sleep_seconds": 2,
        "min_interval_seconds": None,
        "temperature": None,
    },
    # `autospec` (CP 3.2): agora COM consumidor real (`AutoSpecCore.__init__`
    # -- ver autospec_backend.py). `temperature=0.1` preserva o valor
    # deliberado que o LangChain aplicava antes da migração (ver acima).
    "autospec": {
        "max_retries": 2,
        "retry_sleep_seconds": 5,
        "min_interval_seconds": 60,
        "temperature": 0.1,
    },
}


def get_llm(
    tarefa: str,
    api_key: str | None = None,
    *,
    chaves: dict[str, str | None] | None = None,
    selecao_resolvida: dict[str, str] | None = None,
) -> LLMClient:
    """Resolve provider/modelo/política de retry/temperature para `tarefa` e
    devolve um `LLMClient` pronto para uso.

    CADEIA DE RESOLUÇÃO DO MODELO (CP 3.3 — *Aceite* do checkpoint: "trocar
    o modelo na UI muda a próxima chamada"):
      1. `selecao_resolvida`, se passado (não `None`) -- injeção de teste,
         pula a leitura de disco (ver item 2). Deve ter a mesma forma que
         `sigft.core.llm.selecao.resolver()` devolve: `{"provider": ...,
         "model": ...}`.
      2. Senão, `sigft.core.llm.selecao.resolver(tarefa, config_path=
         config.CONFIG_FILE)` -- a seleção que o usuário salvou no painel
         "Modelos de IA" da Home (override da TAREFA > seleção GLOBAL),
         lida do MESMO arquivo das chaves de API (`config.CONFIG_FILE`),
         AO VIVO a cada chamada -- é o que dá o efeito "imediato, sem
         reiniciar o app" (os 5 consumidores de IA constroem um `LLMClient`
         novo, via `get_llm`, a cada execução de módulo).
      3. Se nem 1 nem 2 tiverem nada: `config.LLM_MODELOS_HOJE[tarefa]` --
         o MESMO fallback de antes do CP 3.3 (fonte de equivalência do
         CP 3.1), decisão explícita "sem downgrade silencioso"
         (docs/refatoracao/MODELOS_IA.md §5): quem nunca abriu o painel
         novo continua exatamente no modelo de hoje.

    `config.LLM_TASKS`/`LLM_DEFAULT` (os modelos RECOMENDADOS) não são lidos
    diretamente por esta função -- só entram em jogo quando o usuário aciona
    "Aplicar recomendados" na UI, que os GRAVA como seleção via
    `selecao.aplicar_recomendados()`; a partir daí passam a ser lidos pelo
    passo 2 acima, como qualquer outra seleção salva.

    Política de retry/rate-limit/temperature continua vindo de
    `_POLITICA_RETRY_POR_TAREFA[tarefa]` -- por TAREFA, nunca por modelo/
    seleção (não muda com a cadeia acima).

    Resolução da CHAVE (CP 3.2 — preserva o comportamento exato dos 4/5
    consumidores diretos de hoje, que passam a chave via
    `self.controller.get_key("GEMINI")` em `frontend.py`):
      - se o provider resolvido for `config.PROVIDER_GEMINI` E `api_key` foi
        passado (não `None`): usa `api_key` TAL QUAL, sem consultar `chaves`
        nem `config.carregar_chaves()` -- é o caminho dos 5 consumidores
        migrados no CP 3.1 (`__init__(self, api_key)`); vale mesmo quando o
        provider "gemini" veio de uma SELEÇÃO (não só do fallback), porque
        os 5 consumidores continuam passando a MESMA chave Gemini de sempre.
      - caso contrário (provider não-Gemini, ou Gemini sem `api_key`
        explícito): resolve a chave do provider via `chaves` (default:
        `config.carregar_chaves()`), usando `config.CHAVE_POR_PROVIDER` para
        saber qual chave lógica ler.
      - `PROVIDER_OPENAI_COMPAT` exige também `base_url`, lida de
        `chaves["EMPRESA_LLM_BASE_URL"]`; ausente/vazia levanta `ValueError`
        explicando que essa variável precisa estar configurada.

    Levanta `ValueError` (mensagem lista as tarefas válidas) para `tarefa`
    desconhecida -- mesmo padrão de `config.get_task_config()` -- SEMPRE
    verificado contra `config.LLM_MODELOS_HOJE` ANTES de qualquer leitura de
    seleção (uma tarefa inválida não pode ser "salva" só por existir numa
    seleção malformada). Levanta `NotImplementedError` se o provider
    resolvido não for um dos 3 suportados (`gemini`/`openrouter`/
    `openai_compat`) -- ex.: `"xai"`, que `config.LLM_TASKS` ainda usa
    (`categorizar_pdm`) e que agora É alcançável em produção se o usuário
    clicar "Aplicar recomendados" (o provider nativo `xai`/Grok 4.5 ainda
    não tem implementação real -- gap pré-existente, ver PENDENCIAS.md; a
    lista curada da UI, `config.LLM_FAVORITOS`, evita esse gap oferecendo
    Grok 4.5 via `openrouter`, que É implementado).
    """
    try:
        cfg_hoje = config.LLM_MODELOS_HOJE[tarefa]
    except KeyError:
        tarefas_validas = ", ".join(sorted(config.LLM_MODELOS_HOJE))
        raise ValueError(
            f"Tarefa de IA desconhecida: {tarefa!r}. Tarefas configuradas em "
            f"LLM_MODELOS_HOJE: {tarefas_validas}."
        ) from None

    if selecao_resolvida is not None:
        resolvido = selecao_resolvida
    else:
        from sigft.core.llm import selecao  # import local -- só usado aqui

        resolvido = selecao.resolver(tarefa, config_path=config.CONFIG_FILE)
    cfg = resolvido if resolvido is not None else cfg_hoje

    provider_id = cfg["provider"]
    politica = dict(_POLITICA_RETRY_POR_TAREFA[tarefa])
    temperature = politica.pop("temperature")

    if provider_id == config.PROVIDER_GEMINI:
        from sigft.core.llm.providers.gemini import GeminiProvider  # import local
        # -- ver docstring do módulo ("nenhum provider concreto é importado
        # no TOPO deste módulo") e o mesmo padrão de import preguiçoso já
        # usado por `core/excel/status_sheet.py` para `openpyxl`.

        if api_key is not None:
            chave = api_key
        else:
            chaves_resolvidas = chaves if chaves is not None else config.carregar_chaves()
            chave = chaves_resolvidas.get(config.CHAVE_POR_PROVIDER[provider_id])
        provider = GeminiProvider(chave, cfg["model"], temperature=temperature)

    elif provider_id == config.PROVIDER_OPENROUTER:
        from sigft.core.llm.providers.openrouter import OpenRouterProvider  # import local

        chaves_resolvidas = chaves if chaves is not None else config.carregar_chaves()
        chave = chaves_resolvidas.get(config.CHAVE_POR_PROVIDER[provider_id])
        provider = OpenRouterProvider(chave, cfg["model"], temperature=temperature)

    elif provider_id == config.PROVIDER_OPENAI_COMPAT:
        from sigft.core.llm.providers.openai_compat import OpenAICompatProvider  # import local

        chaves_resolvidas = chaves if chaves is not None else config.carregar_chaves()
        chave = chaves_resolvidas.get(config.CHAVE_POR_PROVIDER[provider_id])
        base_url = chaves_resolvidas.get("EMPRESA_LLM_BASE_URL")
        if not base_url:
            raise ValueError(
                "Provider 'openai_compat' requer EMPRESA_LLM_BASE_URL configurada "
                "(chave ausente/vazia em `chaves`)."
            )
        provider = OpenAICompatProvider(
            chave, cfg["model"], base_url=base_url, temperature=temperature
        )

    else:
        raise NotImplementedError(
            f"Provider {provider_id!r} ainda não implementado "
            f"(suportados: {config.PROVIDER_GEMINI!r}, {config.PROVIDER_OPENROUTER!r}, "
            f"{config.PROVIDER_OPENAI_COMPAT!r})."
        )

    return LLMClient(
        provider,
        provider_name=provider_id,
        model=cfg["model"],
        **politica,
    )
