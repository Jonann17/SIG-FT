"""
sigft/config.py — fonte única da verdade para constantes, planilhas, portal e
chaves de API do SIG-FT (Checkpoint 1.1 do plano de refatoração).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 1 -> CP 1.1.

ESCOPO DESTE CHECKPOINT (aditivo): este módulo nasce aqui, mas NENHUM
consumidor de produção (`*_backend.py`, `upload_ficha_duplicada.py`,
`frontend.py`) foi migrado para importar dele — isso é dos CP 1.2, 1.3 e, no
caso de `LLM_TASKS`, a partir do CP 3.1 em diante. Os valores abaixo foram
levantados por grep no código de produção hoje; este arquivo CARACTERIZA o
comportamento atual (mesma string, mesmo número), não muda nada.

Organização:
  1. Portal PMIB (URL, endpoint de busca web)
  2. Planilha "Lista de Materiais" (nome canônico + variantes de resiliência)
  3. Prefixo de contrato
  4. Valores mágicos de linha (ficha técnica, STATUS_PMIB)
  5. Colunas-chave mais repetidas entre módulos
  6. Mapa de tarefas de IA (`LLM_TASKS`/`LLM_DEFAULT`) + decisão de modelos
  7. Carregamento de chaves de API (.env + api_config.json)

Exceção à regra de caracterização: a seção 6 (modelos de IA) encoda também as
DECISÕES de `docs/refatoracao/MODELOS_IA.md` (padrão Gemini 3 Flash Preview,
Grok 4.5 em `categorizar_pdm`) em `LLM_DEFAULT`/`LLM_TASKS`; os modelos que o
código roda HOJE ficam preservados à parte em `LLM_MODELOS_HOJE` (baseline de
equivalência do CP 3.1). O resto do arquivo é caracterização pura.
"""

from __future__ import annotations

import json
import os

# `python-dotenv` é dependência de PRODUÇÃO (requirements.txt) — é assim que
# frontend.py popula os.environ a partir de um arquivo `.env` hoje
# (frontend.py:13 `from dotenv import load_dotenv`; frontend.py:4107-4108
# `env_path = resource_path('.env'); load_dotenv(env_path)`). Mas este
# ambiente de TESTE não a tem instalada (só stdlib/requests/pytest — ver
# tests/conftest.py). Import defensivo para que `import sigft.config` nunca
# quebre por isso: se `dotenv` não estiver disponível, `load_dotenv` fica
# `None` e simplesmente não é chamado por ninguém aqui dentro — este módulo
# não precisa dele para nada além de reexportá-lo, porque `carregar_chaves()`
# abaixo lê `os.environ` diretamente (o `.env` só popula o environ ANTES da
# chamada; sem dotenv, variáveis de ambiente já presentes no processo
# continuam funcionando normalmente). Consumidores futuros (ex.: bootstrap da
# app na Fase 7) podem fazer `from sigft.config import load_dotenv` e chamar
# com o caminho que precisarem — a resolução de caminho (incluindo o caso
# PyInstaller `_MEIPASS` de `frontend.resource_path`) é responsabilidade da
# camada de app/empacotamento (CP 7 / CP 8.3), não deste módulo de config.
try:
    from dotenv import load_dotenv  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - ambiente sem python-dotenv instalado
    load_dotenv = None


# =============================================================================
# 1. PORTAL PMIB
# =============================================================================

# URL do portal PMIB (OutSystems). Hoje hardcoded de forma IDÊNTICA em 15+
# ocorrências: apagar_lmr_backend.py:17, lmr_backend.py:19,
# upload_conditions_backend.py:507, cria_fichas_no_pmib_v1_backend.py:404,415,
# upload_tech_specs_backend.py:444,791, upload_ficha_duplicada.py:179,618,
# frontend.py (4 ocorrências). Seletores/URLs do portal são INTOCÁVEIS nas
# Fases 1-4 (ver plano, arquitetura-alvo, princípio 5) — este checkpoint só
# CENTRALIZA o valor; ele continua sendo exatamente o mesmo.
PORTAL_URL = "https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList"

# Endpoint da Google Custom Search API, usado pela busca web do AutoSpec
# (`WebSearcher.search_url`, autospec_backend.py:73). Constante separada do
# portal PMIB porque é uma API externa distinta (não OutSystems/Itaipu).
GOOGLE_CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"


# =============================================================================
# 2. PLANILHA "LISTA DE MATERIAIS"
# =============================================================================

# Nome "canônico" da aba onde vive a lista de materiais / status PMIB dentro
# dos arquivos `_STATUS_PMIB`. É também o default de `GerenciadorFilaPMIB` e
# `AtualizadorStatusPMIB` (`nome_aba="Lista de Materiais"`,
# upload_ficha_duplicada.py:17 e :673).
ABA_LISTA_MATERIAIS = "Lista de Materiais"

# Variantes toleradas por resiliência — mesma lista, mesma ordem, de
# `PMIBSearcher.__init__` (search_pmib_backend.py:11:
# `self.sheet_names = ["Lista de Materiais", "LISTA DE MATERIAIS",
# "Lista de materiais"]`), usada para tentar múltiplas grafias da aba.
ABA_LISTA_MATERIAIS_VARIANTES = (
    "Lista de Materiais",
    "LISTA DE MATERIAIS",
    "Lista de materiais",
)


# =============================================================================
# 3. PREFIXO DE CONTRATO
# =============================================================================

# Prefixo fixo dos contratos processados hoje. Hardcoded em regex ao menos em
# upload_conditions_backend.py:147 (`re.compile(r'(4500063671\.\d{4})')`),
# usado para validar/extrair código PMIB de nomes de arquivo. "Vira
# configurável" no sentido em que o plano descreve: passa a existir em UM
# lugar só (esta constante) em vez de espalhado como literal — nenhum
# consumidor foi migrado neste checkpoint (aditivo).
PREFIXO_CONTRATO = "4500063671"


# =============================================================================
# 4. VALORES MÁGICOS DE LINHA (diagnóstico do plano, seção 1.5)
# =============================================================================

# Linha (1-based, como aparece no Excel) onde começam as "Especificações
# Técnicas" variáveis (perguntas/respostas) dentro da aba "Ficha Técnica
# Padrão" de cada ficha individual. Hoje hardcoded como literal em:
#   - analyzer_backend.py:52  -> VARIAVEIS_SPECS["start_row"]
#   - analyzer_backend.py:377 -> fallback de _find_variable_specs_start_row
#     quando o texto "ESPECIFICAÇÕES TÉCNICAS..." não é achado dinamicamente
#   - autospec_backend.py:60  -> VARIAVEIS_SPECS["start_row"]
#   - pdm_backend.py:239      -> comentário "Linha 79 fixo" + start_row = 79
#   - translator_backend.py:111 -> current_row = 79
#   - frontend.py:1374        -> comentário "a partir da linha 79" (log)
LINHA_SPECS_FICHA = 79

# "Linha 4 do STATUS" (diagnóstico do plano, seção 1.5): linha (1-based)
# onde o cabeçalho da aba "Lista de Materiais" do arquivo `_STATUS_PMIB`
# aparece na variante de leitura FIXA (não dinâmica) usada por
# `pdm_backend.processar_pastas_fichas`:
#   - pdm_backend.py:169 -> `pd.read_excel(..., skiprows=3)`: `skiprows` do
#     pandas é 0-based, então `skiprows=3` pula as 3 primeiras linhas e trata
#     a 4ª linha do arquivo como cabeçalho.
#   - pdm_backend.py:176 -> mensagem de erro cita "(linha 4)" explicitamente.
#   - docs/base-conhecimento/02-pdm-backend.md:9 documenta o mesmo valor.
# Outros módulos (ex.: `upload_conditions_backend.carregar_lookup_status`,
# `search_pmib_backend._encontrar_e_formatar_dataframe`) buscam esse
# cabeçalho DINAMICAMENTE nas primeiras N linhas em vez de fixar a linha 4 —
# unificar essas buscas é o CP 1.2 (`core/excel/headers.py`); aqui só se
# nomeia o valor mágico usado pela variante fixa do `pdm_backend`.
LINHA_STATUS_PMIB = 4


# =============================================================================
# 5. COLUNAS-CHAVE
# =============================================================================
# Literais de coluna mais repetidos entre módulos, levantados por grep
# (não exaustivo — só os que aparecem em 3+ arquivos de produção).

COL_CODIGO_PMIB = "CÓDIGO PMIB"
# ~10 módulos: cria_fichas_no_pmib_v1_backend, analyzer_backend,
# autospec_backend, upload_conditions_backend, upload_tech_specs_backend,
# upload_ficha_duplicada, pdm_backend, pmib_manager_backend, frontend.

COL_DESCRICAO = "DESCRIÇÃO"
# cria_fichas_no_pmib_v1_backend, analyzer_backend, autospec_backend,
# upload_conditions_backend, search_pmib_backend, pmib_manager_backend,
# frontend.

COL_PDM_USADO = "PDM usado"
# cria_fichas_no_pmib_v1_backend, pdm_backend, upload_tech_specs_backend,
# upload_ficha_duplicada (também usada como campo do marcador "DUPLICADA").

COL_CONDICOES = "CONDIÇÕES"
# upload_conditions_backend, upload_ficha_duplicada, pmib_manager_backend
# (coluna de seção "COMPLETO" do STATUS_PMIB).

COL_CARACT_TECNICAS = "CARACT. TÉCNICAS"
# upload_tech_specs_backend, upload_ficha_duplicada, pmib_manager_backend
# (coluna de seção "COMPLETO" do STATUS_PMIB).

COL_INFO_GERAIS = "INFO. GERAIS"
# upload_ficha_duplicada, pmib_manager_backend (coluna de seção "COMPLETO"
# do STATUS_PMIB).


# =============================================================================
# 6. MAPA DE TAREFAS DE IA (LLM_TASKS) + DECISÃO DE MODELOS (MODELOS_IA.md)
# =============================================================================
# Consumido "de fato" a partir da Fase 3 (`core/llm/client.py:get_llm(tarefa)`
# resolve provider/modelo via `config.LLM_TASKS`, ver plano Fase 3) — nasce
# aqui porque é config, não lógica de IA.
#
# DOIS conjuntos de modelos, de propósito (elimina a ambiguidade "hoje" × "alvo"):
#   - LLM_MODELOS_HOJE  = os modelos EXATOS hardcoded em cada módulo HOJE
#     (caracterização). É a referência de EQUIVALÊNCIA do CP 3.1 ("comportamento
#     atual preservado — mesmos modelos default de hoje").
#   - LLM_DEFAULT / LLM_TASKS = os modelos DECIDIDOS (padrão global + overrides
#     por tarefa) conforme docs/refatoracao/MODELOS_IA.md. A TROCA para eles NÃO
#     acontece no CP 3.1; é aplicada e validada (A/B na UI) no CP 3.3, sem
#     downgrade silencioso. Os slugs são ILUSTRATIVOS — confirmar os ids reais
#     no catálogo do OpenRouter na implementação (ex.:
#     `google/gemini-3-flash-preview`, `x-ai/grok-4.5`, `minimax/minimax-m3`).

PROVIDER_GEMINI = "gemini"
PROVIDER_XAI = "xai"
# CP 3.2: 2 providers novos (`core/llm/providers/openrouter.py`/
# `openai_compat.py`) -- ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3
# -> CP 3.2. `LLM_MODELOS_HOJE` continua intocado (nenhuma tarefa aponta
# para eles em produção ainda -- ver PENDENCIAS.md).
PROVIDER_OPENROUTER = "openrouter"
PROVIDER_OPENAI_COMPAT = "openai_compat"

# Modelos que o código roda HOJE, por tarefa (caracterização — strings exatas
# hardcoded em cada módulo, referências arquivo:linha abaixo). NÃO são o alvo;
# são o baseline de equivalência do CP 3.1.
LLM_MODELOS_HOJE: dict[str, dict[str, str]] = {
    # GeminiCategorizer.processar_lote (cria_fichas_no_pmib_v1_backend.py:131)
    "categorizar_pdm": {"provider": PROVIDER_GEMINI, "model": "gemini-3.1-pro-preview"},
    # DatasheetAnalyzer._call_gemini_api (analyzer_backend.py:451)
    "validar_ficha": {"provider": PROVIDER_GEMINI, "model": "gemini-3.1-pro-preview"},
    # ConditionsProcessor.processar_ia_lote (upload_conditions_backend.py:363)
    "condicoes": {"provider": PROVIDER_GEMINI, "model": "gemini-3.5-flash"},
    # TechSpecsProcessor._chamar_gemini_specs (upload_tech_specs_backend.py:285-286)
    "tech_specs": {"provider": PROVIDER_GEMINI, "model": "gemini-3.5-flash"},
    # AutoSpecCore.__init__ -> ChatGoogleGenerativeAI (autospec_backend.py:173)
    "autospec": {"provider": PROVIDER_GEMINI, "model": "gemini-3.1-pro-preview"},
}

# Padrão GLOBAL decidido (MODELOS_IA.md §3): default de todas as tarefas na UI
# (CP 3.3); overrides por tarefa ficam em LLM_TASKS.
LLM_DEFAULT: dict[str, str] = {"provider": PROVIDER_GEMINI, "model": "gemini-3-flash-preview"}

# Modelos DECIDIDOS por tarefa (MODELOS_IA.md §3): Gemini 3 Flash Preview em
# quase tudo; Grok 4.5 em `categorizar_pdm` (raciocínio, lote raro → custo
# absoluto irrisório).
LLM_TASKS: dict[str, dict[str, str]] = {
    # raciocínio (classificar itens contra o vocabulário PDM); lote raro
    "categorizar_pdm": {"provider": PROVIDER_XAI, "model": "grok-4.5"},
    # juiz semântico VALIDO/INVALIDO; rate-limit de 60s por design → baixo volume
    "validar_ficha": {"provider": PROVIDER_GEMINI, "model": "gemini-3-flash-preview"},
    # alto volume (1 por ficha); PT/ES + JSON são função central do SIG-FT
    "condicoes": {"provider": PROVIDER_GEMINI, "model": "gemini-3-flash-preview"},
    # alto volume, mais mecânico; economia máxima opt-in = minimax-m3 (CP 3.3)
    "tech_specs": {"provider": PROVIDER_GEMINI, "model": "gemini-3-flash-preview"},
    # RAG (contexto longo); subir p/ modelo forte se a geração exigir
    "autospec": {"provider": PROVIDER_GEMINI, "model": "gemini-3-flash-preview"},
}

# Tabela de preços (US$ por 1M tokens) — SEED do UsageTracker (CP 3.4) para
# ESTIMAR custo dos provedores diretos (via OpenRouter o custo vem REAL na
# resposta). Fonte: docs/refatoracao/MODELOS_IA.md §2 (aimultiple, jul/2026) —
# valores EDITÁVEIS, reconfirmar na implementação. Só os modelos que este
# config referencia (hoje + decididos); a tabela completa está no MODELOS_IA.md.
LLM_PRECOS_USD_POR_1M: dict[str, dict[str, float]] = {
    "gemini-3-flash-preview": {"input": 0.50, "output": 3.00},   # padrão global
    "grok-4.5": {"input": 2.00, "output": 6.00},                 # poder de decisão
    "minimax-m3": {"input": 0.30, "output": 1.20},               # economia máxima (opt-in)
    "gemini-3.1-pro-preview": {"input": 2.00, "output": 12.00},  # usado hoje (3 tarefas)
    "gemini-3.5-flash": {"input": 1.50, "output": 9.00},         # usado hoje (2 tarefas)
}


# =============================================================================
# 6b. OPENROUTER (gateway padrão de IA — CP 3.2)
# =============================================================================
# Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.2 e decisão de
# produto nº 2. Consumido por `core/llm/providers/openrouter.py`.

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Headers de "atribuição" recomendados pelo OpenRouter (aparecem no
# dashboard de uso do OpenRouter, não são segredo). `HTTP-Referer` aponta
# para o repositório do projeto (neutro e honesto — não é um site do
# produto, só a origem do código).
OPENROUTER_HEADERS_ATRIBUICAO: dict[str, str] = {
    "HTTP-Referer": "https://github.com/luanccozer/SIG-FT",
    "X-Title": "SIG-FT",
}

# Caminho do cache local do catálogo `GET /models` — relativo, mesmo padrão
# de `CONFIG_FILE` (resolvido a partir do cwd do processo).
OPENROUTER_CATALOGO_CACHE = "openrouter_models_cache.json"


def get_task_config(tarefa: str) -> dict[str, str]:
    """Resolve `{provider, model}` para uma tarefa de IA via `LLM_TASKS`.

    Fábrica consumidora real (`core/llm/client.py:get_llm(tarefa)`) chega no
    CP 3.1 — aqui só nasce a resolução da config, para já existir uma única
    fonte da verdade quando esse checkpoint vier.

    Fallback CLARO para tarefa desconhecida: levanta `ValueError` com
    mensagem listando as tarefas configuradas, em vez de (a) devolver um
    provider/modelo "chute" silenciosamente errado — o que poderia gerar
    custo ou comportamento incorreto sem aviso — ou (b) deixar vazar um
    `KeyError` sem contexto.

    Retorna uma CÓPIA do dict (o chamador pode alterá-la livremente sem
    afetar `LLM_TASKS`).
    """
    try:
        config = LLM_TASKS[tarefa]
    except KeyError:
        tarefas_validas = ", ".join(sorted(LLM_TASKS))
        raise ValueError(
            f"Tarefa de IA desconhecida: {tarefa!r}. Tarefas configuradas em "
            f"LLM_TASKS: {tarefas_validas}."
        ) from None
    return dict(config)


# =============================================================================
# 7. CARREGAMENTO DE CHAVES DE API (.env + api_config.json)
# =============================================================================
# Replica FIELMENTE `SIG_FT_App.load_keys()` / `get_key()`
# (frontend.py:4254-4282) e `CONFIG_FILE = "api_config.json"`
# (frontend.py:39).

CONFIG_FILE = "api_config.json"

# Nome da variável de ambiente que popula cada chave lógica — nomes
# preservados EXATAMENTE por compatibilidade/free-tier (ver
# docs/refatoracao/PENDENCIAS.md: `API_GEMINI_LUAN_GMAIL` é um nome pessoal,
# candidato a padronização numa fase futura, fora do escopo deste
# checkpoint).
ENV_VAR_POR_CHAVE: dict[str, str] = {
    "GEMINI": "API_GEMINI_LUAN_GMAIL",
    "GOOGLE_SEARCH": "GOOGLE_SEARCH_API",
    "GOOGLE_CSE": "GOOGLE_CSE_API",
    "LLAMA": "LLAMA_CLOUD_API",
    # CP 3.2 (gateway OpenRouter + endpoint OpenAI-compatível genérico da
    # futura IA interna da empresa) — ver PLANO_REFATORACAO.md, Fase 3 -> CP
    # 3.2 e decisão de produto nº 2 ("todas opcionais, uma necessária — no
    # dia a dia basta OPENROUTER_API_KEY").
    "OPENROUTER": "OPENROUTER_API_KEY",
    "EMPRESA_LLM_BASE_URL": "EMPRESA_LLM_BASE_URL",
    "EMPRESA_LLM_API_KEY": "EMPRESA_LLM_API_KEY",
}

# CP 3.2: mapa provider -> chave LÓGICA de `ENV_VAR_POR_CHAVE` (consumido por
# `core/llm/client.py:get_llm()` para resolver a chave certa por provider,
# quando `api_key` não é passado explicitamente — ver decisão de resolução
# de chave no docstring de `get_llm()`).
CHAVE_POR_PROVIDER: dict[str, str] = {
    PROVIDER_GEMINI: "GEMINI",
    PROVIDER_OPENROUTER: "OPENROUTER",
    PROVIDER_OPENAI_COMPAT: "EMPRESA_LLM_API_KEY",
}


def carregar_chaves(config_path: str | os.PathLike[str] = CONFIG_FILE) -> dict[str, str | None]:
    """Carrega as 4 chaves de API, replicando `SIG_FT_App.load_keys()`.

    Lógica (idêntica à de frontend.py:4254-4274):
      1. Lê os `defaults` das 4 variáveis de ambiente (`ENV_VAR_POR_CHAVE`);
         cada valor pode ser `None` se a env var não estiver definida (mesmo
         comportamento de `os.getenv(...)` sem segundo argumento).
      2. Se `config_path` existir E for um JSON válido: `{**defaults,
         **saved}` — os valores salvos em `api_config.json` SOBRESCREVEM os
         das variáveis de ambiente.
      3. Se `config_path` NÃO existir OU o JSON estiver corrompido/ilegível:
         usa só os `defaults`. O código original captura isso com um
         `except:` nu (frontend.py:4271-4272); aqui usamos `except
         Exception:` — mesmo resultado observável para os casos reais que
         este comportamento cobre (JSON corrompido, arquivo sem permissão de
         leitura), sem engolir `KeyboardInterrupt`/`SystemExit` como o `except:`
         nu faria.

    Testável por design: `config_path` é parâmetro (testes usam `tmp_path`
    em vez do `api_config.json` real do cwd) e a leitura das env vars é feita
    em `os.environ` NO MOMENTO DA CHAMADA (não no import do módulo), então
    testes usam `monkeypatch.setenv`/`monkeypatch.delenv` normalmente.
    """
    defaults: dict[str, str | None] = {
        chave_id: os.environ.get(env_var_name)
        for chave_id, env_var_name in ENV_VAR_POR_CHAVE.items()
    }

    if not os.path.exists(config_path):
        return defaults

    try:
        # NOTA: o original abre com `open(CONFIG_FILE, 'r')` (encoding padrão
        # da plataforma); aqui fixamos `encoding="utf-8"` por robustez
        # multiplataforma. Não muda o resultado para o conteúdo real hoje
        # (chaves de API em ASCII) nem o fluxo de fallback caracterizado.
        #
        # O merge `{**defaults, **saved}` fica DENTRO do try de propósito —
        # mesma estrutura de frontend.py:4267-4272 (`self.api_keys =
        # {**defaults, **saved}` está dentro do `with`/`try`). Isso importa:
        # se `saved` for um JSON válido mas que não é um objeto (ex.: uma
        # lista `[1, 2, 3]`), `**saved` levanta `TypeError`, que também deve
        # cair no fallback para `defaults` — não só falhas de parsing.
        with open(config_path, "r", encoding="utf-8") as arquivo:
            saved = json.load(arquivo)
            return {**defaults, **saved}
    except Exception:
        return defaults


def get_key(chaves: dict[str, str | None], key_id: str) -> str:
    """Réplica de `SIG_FT_App.get_key()` (frontend.py:4281-4282).

    `chaves.get(key_id, "")`: string vazia é o default só quando `key_id`
    está AUSENTE do dicionário. Se a chave existir mas seu valor for `None`
    (ex.: env var não configurada e sem override em `api_config.json`), o
    retorno é `None` — mesma peculiaridade do código original, preservada de
    propósito aqui (não é este checkpoint que decide corrigi-la).
    """
    return chaves.get(key_id, "")
