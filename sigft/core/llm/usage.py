r"""
sigft/core/llm/usage.py — rastreamento de uso e custo de IA (Checkpoint 3.4
do plano de refatoração).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.4, e
docs/refatoracao/MODELOS_IA.md §2 (tabela "score × preço", semeada em
`sigft.config.LLM_PRECOS_USD_POR_1M` desde o CP 1.1). Este módulo é o
"UsageTracker" citado na arquitetura-alvo do plano (seção 2): cada
`LLMClient.generate()` (CP 3.1/3.2/3.3, `core/llm/client.py`) grava UM
registro JSONL aqui — sucesso ou falha, nunca por tentativa de retry — e
`usage_report()` agrega esses registros para responder as 2 perguntas do
*Aceite* deste checkpoint: "qual modelo gasta mais na MESMA tarefa" e "qual
módulo do SIG-FT gasta mais".

DECISÃO 1 (a mais importante deste checkpoint) — rastreamento NUNCA quebra
uma execução
------------------------------------------------------------------------
`registrar()` (a única função deste módulo que faz I/O de escrita) engole
QUALQUER exceção (disco cheio, permissão negada, pasta inválida/inexistente,
valor não serializável em JSON etc.) — mesmo padrão, mesma justificativa, e
literalmente o MESMO precedente já em produção em
`core/llm/client.py:_capturar_prompt_se_pedido` (captura de prompts do
harness de A/B, também "diagnóstico nunca derruba produção"): um lote de 200
fichas não pode morrer porque o log de custo falhou. Ver os testes
dedicados em `tests/test_llm_usage.py` (`registrar()` com escrita forçada a
falhar — caminho inválido E valor não serializável) e em
`tests/test_llm_client.py` (o MESMO cenário, mas através de
`LLMClient.generate()` — o teste mais importante da extensão daquele
arquivo: uma falha ao gravar o registro de uso NÃO impede `generate()` de
devolver a resposta normalmente).

Rastreamento LIGADO por padrão (é o ponto deste checkpoint — "rodar
qualquer módulo com IA gera registros", *Aceite* do plano). Desligamento
manual via variável de ambiente `SIGFT_DESABILITAR_USAGE=1` (nome/valor
EXATOS — qualquer outro valor, ou a ausência da variável, mantém o
rastreamento LIGADO): para quem precisar (ex.: ambiente restrito sem
permissão de escrita em disco, ou quem quer rodar um lote sem gerar ruído
no relatório de custos). Checado logo no topo de `registrar()`, ANTES de
qualquer trabalho (estimativa de custo, timestamp, I/O) — desligado é um
no-op instantâneo.

DECISÃO 2 — custo REAL vs ESTIMADO, e o casamento de slug
------------------------------------------------------------------------
`LLMResponse.custo_usd` (ver `core/llm/client.py`) já vem preenchido com o
custo REAL quando o provider informa — hoje só `providers/openrouter.py`
faz isso, via `usage.cost` da resposta da API (CP 3.2). Regra aplicada
DENTRO de `registrar()` sobre o `custo_usd` recebido como parâmetro:

  - não-`None` -> é o custo REAL informado pelo provider: grava tal qual,
    `custo_estimado=False`.
  - `None` -> não há custo real disponível: ESTIMA via `estimar_custo()`
    (abaixo), usando a tabela de preços `config.LLM_PRECOS_USD_POR_1M`
    (seed de `MODELOS_IA.md` §2 — preços de **julho/2026**, marcados no
    próprio `sigft/config.py` como "editáveis, reconfirmar na
    implementação"; ver docs/refatoracao/PENDENCIAS.md) — `custo_estimado
    =True` quando a estimativa foi possível.
  - Sem tokens (`tokens_in`/`tokens_out` ausentes = `None`) OU modelo fora
    da tabela de preços -> `estimar_custo()` devolve `(None, None)`: o
    registro grava `custo_usd=None`/`custo_estimado=None`. NUNCA um número
    inventado — `None` é a resposta honesta de "não sei".

**Casamento de slug** (a armadilha real deste checkpoint, tratada
explicitamente em `estimar_custo()`/`_buscar_preco_por_slug()`): a tabela
de preços usa nomes SIMPLES de modelo (ex.: `"grok-4.5"`,
`"minimax-m3"`) porque foi semeada a partir da tabela "score × preço" de
`MODELOS_IA.md` §2 — mas um modelo chamado via OpenRouter chega em
`LLMResponse.model` como um slug `vendor/modelo` (ex.: `"x-ai/grok-4.5"`,
`"minimax/minimax-m3"` — os MESMOS 2 slugs já usados por
`config.LLM_FAVORITOS`, ver `sigft/config.py` §6c). Busca em 2 passos:
  1. Chave EXATA em `LLM_PRECOS_USD_POR_1M` (cobre os providers diretos —
     `gemini`/`gemini-3-flash-preview` etc. — e qualquer slug OpenRouter que
     por acaso já seja exatamente o nome simples).
  2. Se não achar E o nome tiver `"/"`: tenta a parte DEPOIS da ÚLTIMA barra
     (`"x-ai/grok-4.5".rsplit("/", 1)[-1] == "grok-4.5"`) — casa com a
     entrada da tabela.
  Se AINDA assim não achar (modelo genuinamente fora da tabela — ex.: um
  modelo escolhido via "campo livre" da UI do CP 3.3, ou um provider/modelo
  novo que ninguém adicionou a `LLM_PRECOS_USD_POR_1M` ainda):
  `(None, None)` — nunca um chute. Ver PENDENCIAS.md.

DECISÃO 3 — módulo puro, testável, sem I/O escondido
------------------------------------------------------------------------
Só stdlib (`json`, `os`, `datetime`, `typing.Callable`) + `from sigft import
config` — mesma convenção de `core/prefs.py`/`core/llm/selecao.py`. Toda
função pública que faz I/O recebe `caminho` (o arquivo JSONL) parametrizável,
com default `config.ARQUIVO_USO_LLM` (constante ADITIVA de `sigft/config.py`
— `PASTA_LOGS`/`ARQUIVO_USO_LLM`, ver lá) — mesma convenção de
`config_path`/`caminho` em `core/prefs.py`/`core/llm/selecao.py`.
`usage_report(registros=...)` aceita os registros JÁ carregados, para
agregar sem NENHUM I/O em teste.

Nenhum teste deste módulo (nem a extensão de `tests/test_llm_client.py`)
escreve no `logs/` real do repositório: todo teste que exercita escrita
passa `caminho=` explícito para dentro de `tmp_path`. Proteção adicional
para os testes de OUTROS arquivos que constroem um `LLMClient` de verdade e
chamam `.generate()` sem saber deste checkpoint (ex.: `test_llm_client.py`
[demais seções], `test_llm_comparacao.py`, `test_llm_get_llm_factory.py`):
a suíte inteira religa `SIGFT_DESABILITAR_USAGE=1` por padrão via uma
fixture `autouse` em `tests/conftest.py`.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Callable

from sigft import config

# Nome da variável de ambiente que DESLIGA o rastreamento de uso (Decisão 1
# do checkpoint) -- mesma convenção de nomenclatura de
# `core/llm/client.py:ENV_DUMP_PROMPTS`, polaridade OPOSTA: aquela variável
# LIGA uma captura desligada por padrão (custo zero quando ausente); esta
# DESLIGA um rastreamento LIGADO por padrão. Só o valor EXATO "1" desliga --
# qualquer outro valor (ou a ausência da variável) mantém o rastreamento
# ligado -- ver `registrar()`.
ENV_DESABILITAR_USAGE = "SIGFT_DESABILITAR_USAGE"


def _no_lugar_certo(caminho: str | os.PathLike[str]) -> str:
    """Caminho RELATIVO é relativo à pasta de dados do usuário, nunca ao
    diretório de trabalho -- que no app instalado é `Program Files`, onde a
    gravação falhava em silêncio e o painel "Gastos de IA" ficava sempre vazio
    (2026-09-25). `config.ARQUIVO_USO_LLM` é o nome relativo
    `logs/llm_usage.jsonl`; caminho absoluto (os `tmp_path` dos testes) passa
    intocado."""
    bruto = os.fspath(caminho)
    if os.path.isabs(bruto):
        return bruto
    from sigft.core.dados_usuario import pasta_dados

    return str(pasta_dados() / bruto)


# =============================================================================
# estimar_custo() -- função PURA (Decisão 2). Ver docstring do módulo para o
# racional completo do casamento de slug. É a peça mais testada deste
# módulo (`tests/test_llm_usage.py`, seção A).
# =============================================================================
def estimar_custo(
    model: str | None, tokens_in: int | None, tokens_out: int | None
) -> tuple[float | None, bool | None]:
    """Estima o custo (USD) de uma chamada via `config.LLM_PRECOS_USD_POR_1M`.

    Devolve `(custo, estimado)`:
      - `tokens_in`/`tokens_out` ausentes (`None`, em qualquer um dos dois)
        -> `(None, None)` -- sem contagem de tokens não há como estimar NADA
        (cobre também o caminho de FALHA de `LLMClient.generate()`, onde
        tokens sempre vêm `None` -- ver Parte B do checkpoint, em
        `core/llm/client.py:generate()`). `0` é uma contagem VÁLIDA (prompt
        vazio, ou um provider que devolve 0 tokens) -- só a AUSÊNCIA
        (`None`) devolve o par vazio, nunca o valor `0`.
      - Modelo não encontrado na tabela de preços (nem pelo nome exato, nem
        pelo casamento de slug `vendor/modelo` -> `modelo`, via
        `_buscar_preco_por_slug()`) -> `(None, None)` -- nunca inventa um
        preço para um modelo desconhecido.
      - Encontrado -> `(custo, True)`, onde
        `custo = (tokens_in / 1_000_000) * preco["input"] +
        (tokens_out / 1_000_000) * preco["output"]`.

    Função PURA: nenhum I/O, não lê `os.environ`, não levanta para os tipos
    de entrada esperados (`model: str | None`, `tokens_*: int | None`)."""
    if tokens_in is None or tokens_out is None:
        return None, None

    preco = _buscar_preco_por_slug(model)
    if preco is None:
        return None, None

    custo = (tokens_in / 1_000_000) * preco["input"] + (tokens_out / 1_000_000) * preco["output"]
    return custo, True


def _buscar_preco_por_slug(model: str | None) -> dict[str, float] | None:
    """Casamento de slug em 2 passos (Decisão 2 -- ver docstring do módulo):

      1. Chave EXATA em `config.LLM_PRECOS_USD_POR_1M`.
      2. Se não achar E `model` contiver `"/"`: a parte DEPOIS da ÚLTIMA
         barra (formato `vendor/modelo` do catálogo OpenRouter -- ex.:
         `"x-ai/grok-4.5"` -> `"grok-4.5"`, `"minimax/minimax-m3"` ->
         `"minimax-m3"`, os mesmos 2 slugs de `config.LLM_FAVORITOS`).

    `None` para `model` que não seja uma string não-vazia (nunca levanta
    `TypeError` de `"/" in model` sobre `None`/outro tipo)."""
    if not isinstance(model, str) or not model:
        return None

    preco = config.LLM_PRECOS_USD_POR_1M.get(model)
    if preco is not None:
        return preco

    if "/" in model:
        sufixo = model.rsplit("/", 1)[-1]
        if sufixo:
            return config.LLM_PRECOS_USD_POR_1M.get(sufixo)

    return None


# =============================================================================
# registrar() -- ÚNICA função deste módulo que faz I/O de escrita. Decisão 1
# (nunca quebra a execução) + Decisão 2 (real vs. estimado) aplicadas aqui.
# =============================================================================
def registrar(
    *,
    provider: str,
    model: str,
    tarefa: str,
    modulo: str | None,
    tokens_in: int | None,
    tokens_out: int | None,
    custo_usd: float | None,
    duracao_s: float,
    sucesso: bool,
    erro: str | None = None,
    caminho: str | os.PathLike[str] = config.ARQUIVO_USO_LLM,
    agora_fn: Callable[[], datetime] | None = None,
) -> None:
    """Anexa UM registro JSON (uma linha, formato JSONL) a `caminho`, criando
    a pasta se preciso.

    Chamado exatamente 2x por `core/llm/client.py:LLMClient.generate()`
    (Parte B do checkpoint) -- nos 2 pontos de saída do método (sucesso, ou
    falha total após esgotar as retentativas) -- NUNCA por tentativa de
    retry interna: uma tarefa que falha 2x e acerta na 3ª gera 1 registro só
    (o de sucesso), não 3.

    Campos do registro (nesta ordem, por legibilidade de quem abrir o JSONL
    à mão): `timestamp` (ISO 8601 local -- `agora_fn()` se injetado, espera
    um objeto com `.isoformat()`, mesma interface de um `datetime.datetime`
    real -- senão `datetime.now()`), `provider`, `model`, `tarefa`,
    `modulo` (`None`/`null` quando o chamador não informou -- ver
    `tags.get("modulo")` em `client.py`), `tokens_in`, `tokens_out`,
    `custo_usd`/`custo_estimado` (ver Decisão 2 -- calculados AQUI a partir
    do `custo_usd` recebido: não-`None` é tratado como REAL,
    `custo_estimado=False`; `None` aciona `estimar_custo()`), `duracao_s`,
    `sucesso` (bool), `erro` (string ou `null`).

    Respeita `SIGFT_DESABILITAR_USAGE=1` (checado ANTES de qualquer
    trabalho -- desligado é um no-op instantâneo, sem tocar em disco).
    NUNCA levanta (Decisão 1 -- qualquer exceção durante a estimativa de
    custo, resolução do timestamp, criação de pasta, serialização JSON ou
    escrita em disco é engolida; mesmo padrão de
    `core/llm/client.py:_capturar_prompt_se_pedido`)."""
    if os.environ.get(ENV_DESABILITAR_USAGE) == "1":
        return

    try:
        # Os dois ramos atribuem opcionalidades diferentes: o custo REAL vem do
        # provedor (nunca None quando chega aqui) e o ESTIMADO pode ser None
        # quando não há tabela de preço para o modelo.
        custo_final: float | None
        custo_estimado: bool | None
        if custo_usd is not None:
            custo_final, custo_estimado = custo_usd, False
        else:
            custo_final, custo_estimado = estimar_custo(model, tokens_in, tokens_out)

        momento = agora_fn() if agora_fn is not None else datetime.now()
        registro = {
            "timestamp": momento.isoformat(timespec="seconds"),
            "provider": provider,
            "model": model,
            "tarefa": tarefa,
            "modulo": modulo,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "custo_usd": custo_final,
            "custo_estimado": custo_estimado,
            "duracao_s": duracao_s,
            "sucesso": bool(sucesso),
            "erro": erro,
        }

        caminho = _no_lugar_certo(caminho)
        pasta = os.path.dirname(caminho)
        if pasta:
            os.makedirs(pasta, exist_ok=True)
        with open(caminho, "a", encoding="utf-8") as arquivo:
            arquivo.write(json.dumps(registro, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 - Decisão 1: rastreamento nunca derruba produção
        pass


# =============================================================================
# ler_registros() -- tolerante a linha corrompida (ex.: escrita interrompida
# por um processo morto no meio de um lote): pula, não derruba a leitura
# das demais linhas.
# =============================================================================
def ler_registros(*, caminho: str | os.PathLike[str] = config.ARQUIVO_USO_LLM) -> list[dict]:
    """Lê `caminho` como JSONL (uma linha = um registro de `registrar()`).

    Arquivo ausente -> lista vazia (nunca levanta `FileNotFoundError`) --
    caso normal de "o app ainda não rodou nenhuma tarefa de IA". Linha em
    branco -> ignorada. Linha que não parseia como JSON (`registrar()`
    interrompido no meio do `arquivo.write()`, ex.: processo morto/kill -9
    durante um lote) -> PULADA silenciosamente, sem interromper a leitura
    das linhas seguintes -- é um log append-only de processo, não uma
    transação. Uma linha que parseia mas não é um OBJETO JSON (`dict`) --
    ex.: um número ou uma lista soltos numa linha -- também é descartada
    (nunca um registro que não seja um `dict`)."""
    caminho = _no_lugar_certo(caminho)
    if not os.path.exists(caminho):
        return []

    registros: list[dict] = []
    with open(caminho, "r", encoding="utf-8") as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if not linha:
                continue
            try:
                registro = json.loads(linha)
            except json.JSONDecodeError:
                continue
            if isinstance(registro, dict):
                registros.append(registro)
    return registros


# =============================================================================
# usage_report() -- agregação em 5 dimensões. Ver docstring da função para o
# racional de `custo_estimado_parcial` (Decisão 2: "não misture estimado com
# real sem avisar").
# =============================================================================
_TAREFA_DESCONHECIDA = "sem_tarefa"
_MODELO_DESCONHECIDO = "desconhecido"
_MODULO_DESCONHECIDO = "desconhecido"
_DIA_DESCONHECIDO = "desconhecido"


def _bucket_vazio() -> dict[str, Any]:
    """Um "agregado" vazio -- os 5 campos que `usage_report()` promete para
    CADA balde (tarefa+modelo, módulo, modelo, dia, total)."""
    return {
        "chamadas": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "custo_usd": 0.0,
        "custo_estimado_parcial": False,
        "falhas": 0,
    }


def _acumular(bucket: dict[str, Any], registro: dict) -> None:
    """Soma `registro` dentro de `bucket` (mutação in-place).

    Tokens/custo AUSENTES (`None`) não contribuem para a soma -- não são
    tratados como zero, simplesmente não há o que somar (um `custo_usd`
    "0.00" nunca deve parecer uma medição real quando na verdade é "sem
    informação"). `custo_estimado_parcial` vira `True` assim que QUALQUER
    registro que contribuiu com custo for uma estimativa (Decisão 2)."""
    bucket["chamadas"] += 1
    if not registro.get("sucesso"):
        bucket["falhas"] += 1

    tokens_in = registro.get("tokens_in")
    if isinstance(tokens_in, (int, float)):
        bucket["tokens_in"] += tokens_in

    tokens_out = registro.get("tokens_out")
    if isinstance(tokens_out, (int, float)):
        bucket["tokens_out"] += tokens_out

    custo = registro.get("custo_usd")
    if isinstance(custo, (int, float)):
        bucket["custo_usd"] += custo
        if registro.get("custo_estimado"):
            bucket["custo_estimado_parcial"] = True


def _dia_do_timestamp(timestamp: Any) -> str:
    """10 primeiros caracteres do `timestamp` ISO 8601 (`YYYY-MM-DD...`) --
    `_DIA_DESCONHECIDO` para qualquer coisa que não seja uma string com pelo
    menos 10 caracteres (nunca levanta por causa de um registro malformado
    injetado em teste)."""
    if isinstance(timestamp, str) and len(timestamp) >= 10:
        return timestamp[:10]
    return _DIA_DESCONHECIDO


def usage_report(
    *,
    caminho: str | os.PathLike[str] = config.ARQUIVO_USO_LLM,
    registros: list[dict] | None = None,
) -> dict[str, Any]:
    """Agrega os registros de uso em 5 dimensões (chaves do dict devolvido):

      - `"por_tarefa_e_modelo"`: `{tarefa: {model: agregado}}` -- responde
        DIRETO a 1ª pergunta do *Aceite* do plano ("qual modelo gasta mais
        na MESMA tarefa"): olhar `relatorio["por_tarefa_e_modelo"][tarefa]`
        e comparar `["custo_usd"]` entre os modelos daquela tarefa.
      - `"por_modulo"`: `{modulo: agregado}` -- responde DIRETO a 2ª
        pergunta ("qual módulo do SIG-FT gasta mais"): comparar
        `["custo_usd"]` entre os módulos.
      - `"por_modelo"`: `{model: agregado}` (todas as tarefas somadas).
      - `"por_dia"`: `{"YYYY-MM-DD": agregado}` (via `_dia_do_timestamp`).
      - `"total"`: um único `agregado` geral (todos os registros somados).

    Registros com `tarefa`/`model`/`modulo` ausentes/vazios/`None` caem num
    balde `"sem_tarefa"`/`"desconhecido"` (nunca são descartados do
    relatório -- um custo real não pode desaparecer só porque a tag estava
    incompleta).

    Cada `agregado` (ver `_bucket_vazio()`) traz: `chamadas` (total,
    sucesso + falha), `tokens_in`/`tokens_out` (soma, ignorando registros
    sem contagem), `custo_usd` (soma, ignorando registros sem custo
    conhecido), `custo_estimado_parcial` (`bool` -- `True` se algum valor
    somado em `custo_usd` veio de `estimar_custo()`, não do provider --
    honestidade: nunca deixa um total parecer 100% real quando é uma
    mistura de real+estimado) e `falhas` (subconjunto de `chamadas` com
    `sucesso=False`).

    `registros=` (injetável, distinto de `None` mesmo quando é uma lista
    VAZIA `[]`) evita QUALQUER I/O em teste -- quando `None` (default), lê
    de `caminho` via `ler_registros()`."""
    if registros is None:
        registros = ler_registros(caminho=caminho)

    por_tarefa_e_modelo: dict[str, dict[str, dict]] = {}
    por_modulo: dict[str, dict] = {}
    por_modelo: dict[str, dict] = {}
    por_dia: dict[str, dict] = {}
    total = _bucket_vazio()

    for registro in registros:
        if not isinstance(registro, dict):
            continue

        tarefa = registro.get("tarefa") or _TAREFA_DESCONHECIDA
        modelo = registro.get("model") or _MODELO_DESCONHECIDO
        modulo = registro.get("modulo") or _MODULO_DESCONHECIDO
        dia = _dia_do_timestamp(registro.get("timestamp"))

        _acumular(por_tarefa_e_modelo.setdefault(tarefa, {}).setdefault(modelo, _bucket_vazio()), registro)
        _acumular(por_modulo.setdefault(modulo, _bucket_vazio()), registro)
        _acumular(por_modelo.setdefault(modelo, _bucket_vazio()), registro)
        _acumular(por_dia.setdefault(dia, _bucket_vazio()), registro)
        _acumular(total, registro)

    return {
        "por_tarefa_e_modelo": por_tarefa_e_modelo,
        "por_modulo": por_modulo,
        "por_modelo": por_modelo,
        "por_dia": por_dia,
        "total": total,
    }


# =============================================================================
# formatar_relatorio_texto() -- versão legível (texto simples) de
# usage_report(), para o card "Gastos de IA" da Home (Parte C do checkpoint,
# `frontend.py`) e para uso no terminal.
# =============================================================================
def _formatar_bucket(rotulo: str, bucket: dict[str, Any]) -> str:
    custo = bucket.get("custo_usd") or 0.0
    marca = " (inclui estimativa)" if bucket.get("custo_estimado_parcial") else ""
    return (
        f"  {rotulo}: {bucket.get('chamadas', 0)} chamada(s) "
        f"({bucket.get('falhas', 0)} falha(s)) | "
        f"{bucket.get('tokens_in', 0)} tok in / {bucket.get('tokens_out', 0)} tok out | "
        f"US$ {custo:.4f}{marca}"
    )


def formatar_relatorio_texto(relatorio: dict[str, Any]) -> str:
    """Formata `relatorio` (o dict devolvido por `usage_report()`) como
    texto simples, multi-linha, pronto para exibir no card "Gastos de IA"
    da Home (Parte C do checkpoint) ou imprimir no terminal.

    NUNCA levanta para um `relatorio` vazio/incompleto (`{}`, ou um dict sem
    todas as chaves esperadas) -- usa `.get(..., ...)` em toda leitura; um
    relatório sem nenhuma chamada registrada vira só a mensagem "Nenhuma
    chamada de IA registrada ainda." (ver Parte C do checkpoint: "sem
    registros ainda -> mensagem amigável, nunca uma tabela vazia ou erro")."""
    total = relatorio.get("total")
    total = total if isinstance(total, dict) else {}
    chamadas_totais = total.get("chamadas", 0)

    if not chamadas_totais:
        return "Nenhuma chamada de IA registrada ainda."

    por_dia = relatorio.get("por_dia", {}) or {}
    dias = sorted(d for d in por_dia if d != _DIA_DESCONHECIDO)
    periodo = f"{dias[0]} a {dias[-1]}" if dias else "período desconhecido"

    linhas = [
        f"Total gasto: US$ {(total.get('custo_usd') or 0.0):.4f}"
        + (" (inclui estimativa)" if total.get("custo_estimado_parcial") else ""),
        f"Chamadas registradas: {chamadas_totais} ({total.get('falhas', 0)} falha(s))",
        f"Período coberto: {periodo}",
        "",
        "Por módulo:",
    ]
    por_modulo = relatorio.get("por_modulo", {}) or {}
    for rotulo, bucket in sorted(por_modulo.items(), key=lambda kv: kv[1].get("custo_usd", 0.0), reverse=True):
        linhas.append(_formatar_bucket(rotulo, bucket))

    linhas.append("")
    linhas.append("Por modelo:")
    por_modelo = relatorio.get("por_modelo", {}) or {}
    for rotulo, bucket in sorted(por_modelo.items(), key=lambda kv: kv[1].get("custo_usd", 0.0), reverse=True):
        linhas.append(_formatar_bucket(rotulo, bucket))

    return "\n".join(linhas)
