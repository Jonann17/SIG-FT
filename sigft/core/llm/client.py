r"""
sigft/core/llm/client.py — `LLMClient`/`LLMResponse` + fábrica `get_llm()`
(Checkpoint 3.1 do plano de refatoração; estendido nos Checkpoints 3.2, 3.3
e 3.4).

NOTA DO CP 3.4 (o restante deste docstring é histórico dos CP 3.1/3.2/3.3,
mantido intacto abaixo): `LLMClient.generate()` passa a gravar UM registro
de uso/custo (`sigft.core.llm.usage.registrar()`, `core/llm/usage.py`) em
CADA UM dos 2 pontos de saída do método — o `return LLMResponse(...)` de
sucesso (dentro do `try`) e o `raise ultimo_erro` de falha total (depois de
esgotar as retentativas) — NUNCA por tentativa de retry interna. `tarefa`/
`modulo` saem de `tags` (mesmo dict já repassado desde o CP 3.1, agora com
consumidor real — fallback `"sem_tarefa"`/`None`, mesmo espírito de
`_capturar_prompt_se_pedido` abaixo); os demais campos (`provider`/`model`/
tokens/`custo_usd`/`duracao_s`) vêm do `LLMResponse`/da política de retry já
resolvidos por este módulo — `LLMClient` NÃO conhece a tarefa por nenhum
outro caminho, só via `tags`. A chamada a `usage.registrar(...)` é feita SEM
nenhum `try/except` extra ao redor aqui: a garantia de "nunca levanta" é
INTEIRAMENTE de `registrar()` (Decisão 1 do CP 3.4, ver `core/llm/usage.py`)
— o mesmo padrão de confiança já usado para `_capturar_prompt_se_pedido`
(chamada "nua", sem wrapper, porque a função chamada já se protege
sozinha). Nenhuma mudança de comportamento observável para quem só olha
`LLMResponse`/exceções/retry: mesma resposta, mesma exceção, mesma política
de retry — só um efeito colateral NOVO (gravação em `logs/llm_usage.jsonl`,
desligável via `SIGFT_DESABILITAR_USAGE=1`) some em paralelo. Import de
`sigft.core.llm.usage` no TOPO deste módulo (não preguiçoso, ao contrário
dos providers concretos) — `usage.py` é só stdlib (`json`/`os`/`datetime`)
+ `config`, sem SDK pesado nem import de volta para `client.py` (sem
ciclo). Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.4, e
docs/refatoracao/PENDENCIAS.md.

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

import itertools
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, NamedTuple

from sigft import config
from sigft.core.llm import usage

# Nome da variável de ambiente que liga a CAPTURA DE PROMPTS para o A/B de
# modelos (ver `scripts/ab_modelos.py` e `core/llm/comparacao.py`). Quando
# aponta para uma pasta, cada chamada de `LLMClient.generate()` grava ali um
# JSON com o prompt REAL enviado — é assim que se obtém material de teste
# fiel sem remontar à mão os prompts gigantes de cada módulo. Desligado por
# padrão (variável ausente = nenhuma escrita, custo zero).
ENV_DUMP_PROMPTS = "SIGFT_DUMP_PROMPTS"

_contador_dump = itertools.count(1)

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


_MIME_POR_EXTENSAO = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


@dataclass(frozen=True)
class Anexo:
    """Um ARQUIVO que vai junto com o prompt (2026-09-24): o próprio PDF, e
    não o texto extraído dele.

    Existe porque o modelo que LÊ o PDF vê o que o texto perde -- desenho
    cotado, tabela com a unidade só no cabeçalho, curva de desempenho. Na
    comparação do usuário com o AMP (que manda o PDF inteiro), essa diferença
    valeu 78 achados contra 43.

    Só o consumidor sabe SE vale mandar (tamanho, número de páginas); o
    provider só sabe COMO -- ver `generate_raw(..., anexos=...)` em cada um,
    e `LLMClient.aceita_pdf`.
    """

    nome: str
    mime: str
    dados: bytes

    @classmethod
    def de_arquivo(cls, caminho: str) -> "Anexo":
        nome = os.path.basename(str(caminho))
        extensao = os.path.splitext(nome)[1].lower()
        with open(caminho, "rb") as arquivo:
            dados = arquivo.read()
        return cls(nome, _MIME_POR_EXTENSAO.get(extensao, "application/octet-stream"), dados)


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
        provider: Any,
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

    @property
    def aceita_pdf(self) -> bool:
        """O provider/modelo desta instância lê PDF nativamente?

        Provider sem o método (os dublês de teste, e qualquer provider escrito
        antes de 2026-09-24) responde `False`: quem pergunta manda o texto
        extraído, que é o comportamento de sempre.
        """
        pergunta = getattr(self._provider, "aceita_pdf", None)
        return bool(pergunta()) if callable(pergunta) else False

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
        anexos: list[Anexo] | None = None,
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
          tags: metadados livres (ex.: `{"modulo": ..., "tarefa": ...}`) --
            desde o CP 3.4, é DAQUI que saem `tarefa`/`modulo` do registro
            de uso gravado por `usage.registrar()` (ver "Fluxo" item 5,
            abaixo, e `sigft/core/llm/usage.py`): `tags.get("tarefa",
            "sem_tarefa")` / `tags.get("modulo")` -- MESMO fallback de
            `_capturar_prompt_se_pedido` (`tarefa` nunca fica `None` no
            registro; `modulo` fica `None`/`null` quando o chamador não
            informou). `LLMClient` não conhece a tarefa por nenhum outro
            caminho -- depende inteiramente de `tags`.
          anexos (2026-09-24): arquivos (`Anexo`) que vão JUNTO com o
            prompt -- o PDF em si, para o modelo ler. Só repassado ao
            provider quando não vazio; pergunte `aceita_pdf` antes de mandar.

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
          5. [CP 3.4] EM AMBOS os desfechos (retorno de sucesso no item 2,
             ou exceção re-levantada no item 4) -- e SÓ nesses 2 pontos,
             nunca por tentativa de retry interna --, grava UM registro de
             uso via `usage.registrar()` ANTES de retornar/re-levantar:
             sucesso leva os campos do `LLMResponse` recém-montado (mesmos
             tokens/custo/duração que o CHAMADOR também recebe -- nenhum
             valor novo inventado aqui) + `sucesso=True`; falha total leva
             `tokens_in=tokens_out=custo_usd=None` (não há resposta de onde
             tirar isso), a duração decorrida desde o INÍCIO deste
             `generate()` (soma de todas as tentativas + sleeps de retry,
             já que não existe uma "tentativa que teve sucesso" para medir
             como no item 2) e `erro=f"{type(ultimo_erro).__name__}:
             {ultimo_erro}"` + `sucesso=False`. `usage.registrar()` NUNCA
             levanta (Decisão 1 do CP 3.4) -- chamada aqui sem `try/except`
             extra, mesmo padrão de confiança de `_capturar_prompt_se_pedido`.
        """
        tags = tags or {}
        usage_tarefa = tags.get("tarefa", "sem_tarefa")
        usage_modulo = tags.get("modulo")
        _capturar_prompt_se_pedido(
            prompt,
            system=system,
            json_mode=json_mode,
            tags=tags,
            provider=self._provider_name,
            model=self._model,
        )
        self._aplicar_rate_limit()

        ultimo_erro: Exception | None = None
        inicio_chamada = self._time_fn()
        for tentativa in range(self._max_retries + 1):
            inicio = self._time_fn()
            try:
                # `anexos` só vai quando há anexo: provider de assinatura
                # antiga (os dublês de teste do app inteiro) continua valendo
                # para toda chamada que não manda arquivo.
                extras = {"anexos": anexos} if anexos else {}
                resultado = self._provider.generate_raw(
                    prompt, system=system, json_mode=json_mode, **extras,
                )
                parsed = _limpar_e_parsear_json(resultado.text)
                duracao = self._time_fn() - inicio
                usage.registrar(
                    provider=self._provider_name,
                    model=self._model,
                    tarefa=usage_tarefa,
                    modulo=usage_modulo,
                    tokens_in=resultado.tokens_in,
                    tokens_out=resultado.tokens_out,
                    custo_usd=resultado.custo_usd,
                    duracao_s=duracao,
                    sucesso=True,
                    caminho=config.ARQUIVO_USO_LLM,
                )
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
        usage.registrar(
            provider=self._provider_name,
            model=self._model,
            tarefa=usage_tarefa,
            modulo=usage_modulo,
            tokens_in=None,
            tokens_out=None,
            custo_usd=None,
            duracao_s=self._time_fn() - inicio_chamada,
            sucesso=False,
            erro=f"{type(ultimo_erro).__name__}: {ultimo_erro}",
            caminho=config.ARQUIVO_USO_LLM,
        )
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
def _capturar_prompt_se_pedido(
    prompt: str,
    *,
    system: str | None,
    json_mode: bool,
    tags: dict[str, str],
    provider: str,
    model: str,
) -> None:
    """Grava o prompt REAL desta chamada em disco, se `SIGFT_DUMP_PROMPTS`
    apontar para uma pasta (ver `ENV_DUMP_PROMPTS` no topo do módulo).

    Existe para viabilizar o A/B de modelos exigido pelo Aceite do CP 3.3
    ("o usuário valida a qualidade num punhado de fichas... A/B contra o
    modelo anterior"): rodando um módulo UMA vez com a variável ligada, os
    prompts de verdade — que são gigantes e dependem de ler Excel/PDF —
    ficam salvos e podem ser reexecutados em vários modelos por
    `scripts/ab_modelos.py`, sem remontar nada à mão.

    NUNCA quebra a chamada real: qualquer falha ao gravar (pasta inválida,
    disco cheio, permissão) é engolida de propósito. Uma ferramenta de
    diagnóstico não pode derrubar um lote de fichas em produção.
    """
    pasta = os.environ.get(ENV_DUMP_PROMPTS)
    if not pasta:
        return
    try:
        os.makedirs(pasta, exist_ok=True)
        tarefa = tags.get("tarefa", "sem_tarefa")
        sequencial = next(_contador_dump)
        nome = f"{time.strftime('%Y%m%d-%H%M%S')}_{tarefa}_{sequencial:03d}.json"
        conteudo = {
            "tarefa": tarefa,
            "modulo": tags.get("modulo"),
            "provider_na_captura": provider,
            "model_na_captura": model,
            "json_mode": json_mode,
            "system": system,
            "prompt": prompt,
        }
        with open(os.path.join(pasta, nome), "w", encoding="utf-8") as arquivo:
            json.dump(conteudo, arquivo, ensure_ascii=False, indent=2)
    except Exception:  # noqa: BLE001 - diagnóstico nunca derruba produção
        pass


def _limpar_e_parsear_json(texto: str | None) -> Any:
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

    try:
        return json.loads(limpo)
    except json.JSONDecodeError as erro_estrito:
        # [2026-10-19] Leitura tolerante, SO quando a estrita falha: cada
        # falha aqui custa uma chamada inteira de novo (retry), ou a resposta
        # vazia. Se nada der certo, sobe o erro da leitura estrita, como antes.
        resultado = _json_tolerante(texto)
        if resultado is _NADA:
            raise erro_estrito
        return resultado


# Sentinela de `_json_tolerante`: `None` e um JSON valido (`null`).
_NADA = object()

_BLOCO_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _sem_virgula_sobrando(texto: str) -> str:
    """Tira a virgula antes de `}`/`]` (`{"a": 1,}`), fora das strings."""
    saida, em_string, escape = [], False, False
    for i, c in enumerate(texto):
        if em_string:
            saida.append(c)
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                em_string = False
            continue
        if c == '"':
            em_string = True
        elif c == ",":
            resto = texto[i + 1:].lstrip()
            if resto[:1] in ("}", "]"):
                continue
        saida.append(c)
    return "".join(saida)


def _fim_do_bloco(texto: str, inicio: int) -> int | None:
    """Onde fecha o trecho `{...}`/`[...]` que abre em `inicio`, contando as
    chaves fora das strings; `None` se ele nao fecha (resposta truncada) ou
    fecha com o sinal trocado."""
    pilha, em_string, escape = [], False, False
    for fim in range(inicio, len(texto)):
        d = texto[fim]
        if em_string:
            if escape:
                escape = False
            elif d == "\\":
                escape = True
            elif d == '"':
                em_string = False
            continue
        if d == '"':
            em_string = True
        elif d in "{[":
            pilha.append("}" if d == "{" else "]")
        elif d in "}]":
            if not pilha or pilha.pop() != d:
                return None
            if not pilha:
                return fim
    return None


def _candidatos_balanceados(texto: str):
    """Cada trecho `{...}`/`[...]` balanceado DE FORA do texto, na ordem.

    Um trecho que nao e o JSON (a prosa "o formato {campo: valor}") e pulado
    INTEIRO: nunca vira candidato um pedaco de DENTRO dele. [2026-11-06] Antes
    cada `{` era um comeco, e com o objeto da resposta quebrado a leitura
    devolvia um campo de dentro dele: no AutoSpec pelo Workflow AMP, a ficha
    voltou em branco (o `\\%` do agente, ver `_sem_escape_invalido`). Um
    trecho que nao fecha (resposta truncada) encerra a busca: o resto do texto
    esta dentro dele."""
    inicio = 0
    while inicio < len(texto):
        if texto[inicio] not in "{[":
            inicio += 1
            continue
        fim = _fim_do_bloco(texto, inicio)
        if fim is None:
            return
        yield texto[inicio:fim + 1]
        inicio = fim + 1


# As sequências de escape que o JSON aceita depois da barra.
_ESCAPES_DO_JSON = frozenset('"\\/bfnrtu')


def _sem_escape_invalido(texto: str) -> str:
    """A barra antes de um caractere que o JSON nao aceita como escape sai, e
    a barra escrita (`\\\\`) fica. [2026-11-06] O agente do AMP escreve
    `95\\%` dentro do JSON, como escrevia `100\\%` no CSS da revisao das
    listas."""
    return re.sub(r"\\(.)", lambda m: m.group(0) if m.group(1) in _ESCAPES_DO_JSON else m.group(1),
                  texto, flags=re.DOTALL)


def _json_tolerante(texto: str):
    """A resposta que a leitura estrita recusou, com quatro consertos: tira o
    bloco de raciocinio (`<think>...</think>` dos modelos que pensam em voz
    alta), acha o JSON de verdade no meio da prosa (o primeiro trecho
    balanceado DE FORA que e JSON), tira a virgula sobrando antes de fechar e
    tira a barra de escape que o JSON nao aceita (2026-11-06). Devolve
    `_NADA` se nada der certo. Ideia do `_robust_json_parse` do RAG-Anything
    (HKUDS, licenca MIT). JSON truncado continua falhando: completar o que a IA
    nao mandou esconderia campos perdidos."""
    limpo = _BLOCO_THINK.sub("", texto).replace("```json", "").replace("```", "")
    for candidato in _candidatos_balanceados(limpo):
        sem_virgula = _sem_virgula_sobrando(candidato)
        for versao in (candidato, sem_virgula, _sem_escape_invalido(candidato), _sem_escape_invalido(sem_virgula)):
            try:
                return json.loads(versao)
            except json.JSONDecodeError:
                continue
    return _NADA


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
# continua sendo o FALLBACK (não muda de fonte) DAS 5 TAREFAS DO CP 3.1; a
# validação de `tarefa` é feita ANTES de qualquer leitura de seleção.
#
# ⚠️ CORRIGIDO EM 2026-09-03: a validação era feita contra `LLM_MODELOS_HOJE`,
# usando o baseline histórico como CATÁLOGO de tarefas. Tarefa nascida depois
# do CP 3.1 (`traduzir_pdm`) não entra nesse mapa por decisão de projeto — e
# ficava inalcançável em produção. Agora o catálogo é `LLM_TASKS`, e
# `LLM_MODELOS_HOJE` é o fallback de quem tem baseline. Ver `get_llm()` e o
# aviso longo em `sigft/config.py`, seção 6.
#
# A política de retry/rate-limit/temperature continua vindo de
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
_POLITICA_RETRY_POR_TAREFA: dict[str, dict[str, Any]] = {
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
    #
    # `timeout_s` e `max_retries: 1` (2026-09-24, frente do AutoSpec): a IA
    # passou a receber o documento INTEIRO (ou o proprio PDF), e 120 s por
    # tentativa ficou curto -- a ficha 0088 bateu tres `ReadTimeout` seguidos,
    # 6 min 12 s. Com 300 s, tres tentativas seriam 15 min presos numa ficha;
    # uma nova tentativa basta para o soluco passageiro do provedor.
    "autospec": {
        "max_retries": 1,
        "retry_sleep_seconds": 5,
        "min_interval_seconds": 60,
        "temperature": 0.1,
        "timeout_s": 300,
    },
    # `traduzir_pdm` (2026-08-28): traducao PT->EN das perguntas dos PDMs
    # Modificados. Entrou em `LLM_TASKS` e NAO aqui -- e por isso a tarefa era
    # 100% inalcancavel em producao ate 2026-09-03, quando o usuario rodou
    # 1192 arquivos e viu "Tarefa de IA desconhecida" a cada um deles.
    #
    # SEM `min_interval_seconds`, ao contrario de `validar_ficha`/`autospec`:
    # esta tarefa roda em LOTE GRANDE (uma pasta tipica tem ~1200 PDMs), e um
    # intervalo minimo de 60 s entre chamadas transformaria o trabalho em 20
    # horas de espera. Traducao errada se conserta no glossario; lote que nao
    # termina nao se conserta.
    "traduzir_pdm": {
        "max_retries": 2,
        "retry_sleep_seconds": 5,
        "min_interval_seconds": None,
        "temperature": None,
    },
    # `interpretar_material` (2026-10-08): passada 1 da escolha de PDM. UMA
    # retentativa: se ainda assim falhar, o lote segue com a busca de hoje
    # (`GeminiCategorizer.interpretar_lote` degrada sem levantar) -- nada se
    # perde, entao nao vale prender o usuario esperando mais.
    "interpretar_material": {
        "max_retries": 1,
        "retry_sleep_seconds": 2,
        "min_interval_seconds": None,
        "temperature": None,
    },
    # `docpack_pasta` (2026-11-03): a sugestao de pasta do DocPack. A pedido, uma
    # lista por vez; falhou, os campos ficam como estavam e a pessoa digita.
    "docpack_pasta": {
        "max_retries": 1,
        "retry_sleep_seconds": 2,
        "min_interval_seconds": None,
        "temperature": None,
    },
}


def _padrao_pela_chave(cfg: dict[str, str], api_key: str | None,
                      chaves: dict[str, str | None] | None) -> dict[str, str]:
    """[2026-11-05] O padrão de quem NÃO escolheu modelo é Gemini direto
    (`LLM_MODELOS_HOJE`/`LLM_TASKS`), e sem a chave do Gemini o módulo morria
    mesmo com a do OpenRouter posta (pedido do Luan: "tirar que dependa sim ou sim
    da chave do Gemini"). Sem chave do Gemini e COM a do OpenRouter, o mesmo modelo
    vai pelo OpenRouter (`google/<modelo>`). Com a chave do Gemini, nada muda:
    ninguém troca de caminho por acidente."""
    if cfg.get("provider") != config.PROVIDER_GEMINI or api_key:
        return cfg
    chaves_resolvidas = chaves if chaves is not None else config.carregar_chaves()
    if chaves_resolvidas.get(config.CHAVE_POR_PROVIDER[config.PROVIDER_GEMINI]):
        return cfg
    if not chaves_resolvidas.get(config.CHAVE_POR_PROVIDER[config.PROVIDER_OPENROUTER]):
        return cfg
    modelo = cfg["model"]
    return {"provider": config.PROVIDER_OPENROUTER,
            "model": modelo if "/" in modelo else f"google/{modelo}"}


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
    # O FALLBACK EMBUTIDO, e o que fazer com tarefa nascida DEPOIS do CP 3.1.
    #
    # `LLM_MODELOS_HOJE` e a caracterizacao do que cada modulo hardcodava
    # ANTES do CP 3.1 -- baseline de equivalencia, e a razao de ser o fallback
    # aqui e "sem downgrade silencioso": ninguem troca de modelo por acidente.
    #
    # Uma tarefa criada DEPOIS nao tem "modelo de antes" para caracterizar, e
    # inventar um so para o mapa ficar simetrico faria o baseline mentir --
    # `tests/test_config.py` guarda isso, com razao. Mas ate 2026-09-03 esta
    # funcao usava o baseline tambem como CATALOGO DE TAREFAS, e a
    # consequencia era grave: `traduzir_pdm`, registrada em `LLM_TASKS` em
    # 28/08, era 100% inalcancavel em producao. O usuario descobriu rodando
    # 1192 arquivos e recebendo "Tarefa de IA desconhecida" em cada um.
    #
    # A separacao correta: `LLM_TASKS` e o CATALOGO (o que o app se propoe a
    # fazer com IA); `LLM_MODELOS_HOJE` e o BASELINE de quem existia antes.
    # Para tarefa nova o fallback e a propria entrada de `LLM_TASKS` -- e nao
    # ha "downgrade silencioso" possivel, porque nao existe comportamento
    # anterior a preservar.
    cfg_hoje = config.LLM_MODELOS_HOJE.get(tarefa) or config.LLM_TASKS.get(tarefa)
    if cfg_hoje is None:
        tarefas_validas = ", ".join(sorted(set(config.LLM_MODELOS_HOJE) | set(config.LLM_TASKS)))
        raise ValueError(
            f"Tarefa de IA desconhecida: {tarefa!r}. Tarefas configuradas: "
            f"{tarefas_validas}."
        ) from None

    # `resolvido` pode vir da selecao do usuario (nunca None) ou da consulta
    # ao arquivo de configuracao (que devolve None quando nao ha escolha
    # salva). O `cfg = ... if ... else cfg_hoje` logo abaixo e quem resolve.
    resolvido: dict[str, str] | None
    if selecao_resolvida is not None:
        resolvido = selecao_resolvida
    else:
        from sigft.core.llm import selecao  # import local -- só usado aqui

        resolvido = selecao.resolver(tarefa, config_path=config.CONFIG_FILE)
    cfg = resolvido if resolvido is not None else cfg_hoje
    if resolvido is None:
        cfg = _padrao_pela_chave(cfg, api_key, chaves)

    provider_id = cfg["provider"]
    try:
        politica = dict(_POLITICA_RETRY_POR_TAREFA[tarefa])
    except KeyError:
        # `KeyError: 'traduzir_pdm'` nao diz a ninguem o que fazer. Esta e a
        # segunda metade da armadilha de 2026-09-03: a tarefa passou pela
        # validacao logo acima (esta em `LLM_TASKS`) e morria AQUI, tres linhas
        # depois. Quem previne de verdade e o teste
        # `test_TODA_tarefa_de_LLM_TASKS_e_resolvivel_por_get_llm`; esta
        # mensagem e a rede para quando alguem nao rodou a suite.
        raise ValueError(
            f"A tarefa {tarefa!r} existe em LLM_TASKS mas nao tem politica de "
            "retry. Acrescente uma entrada em `_POLITICA_RETRY_POR_TAREFA`, "
            "neste arquivo (sigft/core/llm/client.py) -- veja as vizinhas para "
            "o formato."
        ) from None
    temperature = politica.pop("temperature")
    # Opcional, ao contrario de `temperature`: so a tarefa que precisa de mais
    # (ou menos) que o default de 120 s do provedor declara. Ausente, o
    # provedor e construido exatamente como antes.
    timeout = politica.pop("timeout_s", None)
    extras_do_provedor: dict[str, Any] = {} if timeout is None else {"timeout": timeout}

    # [CP 8.2] Declarados antes do `if` porque os três ramos atribuem a mesma
    # variável classes DIFERENTES (Gemini/OpenRouter/OpenAICompat). Sem isto o
    # mypy fixa o tipo no primeiro ramo e acusa os outros dois.
    #
    # `Any` no provider, e não uma classe base: não existe uma. Os três
    # provedores cumprem o mesmo contrato de fato (`gerar(...) -> ProviderResult`)
    # sem herdar de nada -- é duck typing, como o resto da camada. Criar a
    # classe base agora seria mudança de arquitetura, não anotação de tipo.
    #
    # `chave` é `str | None` de propósito: chave ausente é caso NORMAL aqui (o
    # usuário pode não ter configurado aquele provedor), e quem valida é o
    # próprio provider, com mensagem própria.
    provider: Any
    chave: str | None
    # `dict[str, str | None]`: e o que `config.carregar_chaves()` devolve --
    # a chave EXISTE no dicionario mesmo quando a env var nao esta
    # configurada, e o valor e None (ver o docstring de `get_key`).
    chaves_resolvidas: dict[str, str | None]

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
        provider = GeminiProvider(
            chave, cfg["model"], temperature=temperature, **extras_do_provedor
        )

    elif provider_id == config.PROVIDER_OPENROUTER:
        from sigft.core.llm.providers.openrouter import OpenRouterProvider  # import local

        chaves_resolvidas = chaves if chaves is not None else config.carregar_chaves()
        chave = chaves_resolvidas.get(config.CHAVE_POR_PROVIDER[provider_id])
        provider = OpenRouterProvider(
            chave, cfg["model"], temperature=temperature, **extras_do_provedor
        )

    elif provider_id == config.PROVIDER_OPENAI_COMPAT:
        from sigft.core.llm.providers.openai_compat import OpenAICompatProvider  # import local

        chaves_resolvidas = chaves if chaves is not None else config.carregar_chaves()
        chave = chaves_resolvidas.get(config.CHAVE_POR_PROVIDER[provider_id])
        # `base_url` pode vir None/vazio; o `if not base_url` logo abaixo e
        # quem trata. A anotacao larga evita fingir que ja e `str` aqui.
        base_url: str | None = chaves_resolvidas.get("EMPRESA_LLM_BASE_URL")
        if not base_url:
            raise ValueError(
                "Provider 'openai_compat' requer EMPRESA_LLM_BASE_URL configurada "
                "(chave ausente/vazia em `chaves`)."
            )
        provider = OpenAICompatProvider(
            chave, cfg["model"], base_url=base_url, temperature=temperature,
            **extras_do_provedor,
        )

    elif provider_id == config.PROVIDER_AMP_WORKFLOW:
        # 2026-11-04: o Workflow AMP do módulo ("IA por módulo"). O endereço e a
        # chave do webhook são os da TAREFA (`modo.chaves_do_webhook`). Sem
        # repetição: cada repetição seria uma execução nova do agente no AMP.
        from sigft.core.llm import modo  # import local
        from sigft.core.llm.providers.amp_workflow import AmpWorkflowProvider  # import local

        chaves_resolvidas = chaves if chaves is not None else config.carregar_chaves()
        nome_url, nome_chave = modo.chaves_do_webhook(tarefa)
        provider = AmpWorkflowProvider(
            str(chaves_resolvidas.get(nome_url) or ""), str(chaves_resolvidas.get(nome_chave) or ""),
            tarefa=tarefa,
        )
        politica["max_retries"] = 0

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
