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


# =============================================================================
# 6c. LLM_FAVORITOS — lista CURADA para o seletor de modelo na UI (CP 3.3)
# =============================================================================
# Fonte: docs/refatoracao/MODELOS_IA.md §2/§3 (tabela aimultiple, jul/2026).
# Consumida pelo painel "Modelos de IA" da Home (`frontend.py`) para montar
# as opções dos `CTkOptionMenu` (modo simples/avançado) — é a lista "curada"
# que o *Aceite* do CP 3.3 pede ("filtrado por uma lista curada de favoritos
# em config, para não exibir 400+ modelos [do catálogo do OpenRouter]").
# `aditivo` — nenhuma constante/função existente deste arquivo foi alterada.
#
# `provider`/`model`: SEMPRE um dos 3 providers que `core/llm/client.py:
# get_llm()` de fato IMPLEMENTA (`PROVIDER_GEMINI`/`PROVIDER_OPENROUTER`/
# `PROVIDER_OPENAI_COMPAT`) — nunca um provider "nativo" não implementado
# (ex.: `PROVIDER_XAI`, usado só por `LLM_TASKS["categorizar_pdm"]` — ver
# docs/refatoracao/PENDENCIAS.md, gap pré-existente desde o CP 1.1/3.1/3.2).
# Por isso Grok 4.5/MiniMax M3 entram aqui via `PROVIDER_OPENROUTER` (o
# único caminho REAL até esses modelos hoje — decisão de produto nº 2:
# "OpenRouter é o gateway padrão... dá acesso a Gemini, GPT, Kimi, DeepSeek
# etc."), enquanto os 2 modelos Gemini usam o provider NATIVO
# (`PROVIDER_GEMINI`), preservando o caminho direto/free tier — MESMO
# provider+model já usados por `LLM_DEFAULT`/`LLM_MODELOS_HOJE` (nenhum
# valor inventado para esses 3).
#
# `model` dos 2 favoritos NÃO-Gemini é um SLUG ILUSTRATIVO no formato
# `vendor/modelo` do catálogo OpenRouter (mesmo formato de exemplo do
# MODELOS_IA.md §3: "google/gemini-3-flash-preview", "x-ai/grok-4.5",
# "minimax/minimax-m3") — RECONFIRMAR o id EXATO no catálogo real do
# OpenRouter (`core/llm/providers/openrouter.py:listar_modelos`) antes do
# uso em produção; ver PENDENCIAS.md.
#
# `tier`: um de `"economia"`, `"padrao"`, `"poder"` (MODELOS_IA.md §3:
# "Três posições, todas trocáveis na UI"). Os 2 modelos "usados hoje" não
# fazem parte da decisão de 3 tiers, mas GANHAM um tier aqui (exigido pela
# forma da entrada) por proximidade de papel: `gemini-3.1-pro-preview`
# (score 77, caro) ~ "poder" (era o tier de "poder" antes do Grok 4.5
# dominá-lo, MODELOS_IA.md §3); `gemini-3.5-flash` (workhorse de
# `condicoes`/`tech_specs` hoje) ~ "padrao" (papel que `gemini-3-flash-
# preview` assume daqui pra frente). Julgamento do executor, sem
# consequência funcional (`tier` só orienta o texto exibido na UI).
#
# `score`/`preco_input`/`preco_output` (US$/1M): só para EXIBIÇÃO no painel
# (não usados por nenhuma lógica de negócio) — mesma fonte/seed de
# `LLM_PRECOS_USD_POR_1M` acima para os 3 modelos novos (Gemini 3 Flash
# Preview/Grok 4.5/MiniMax M3) e para os 2 já existentes lá.
#
# Escopo deliberadamente MÍNIMO: só os 5 exigidos pelo checkpoint (os 3 da
# decisão + os 2 modelos de hoje, "para que o usuário consiga voltar atrás
# pela UI") — a tabela completa de MODELOS_IA.md §2 tem mais candidatos
# (ex.: GPT-5 Mini, Claude Sonnet 5, Kimi K3 — citados em §3 "Espectro na
# interface") que podem entrar aqui numa iteração futura; ver PENDENCIAS.md.
LLM_FAVORITOS: list[dict[str, object]] = [
    {
        "provider": PROVIDER_GEMINI,
        "model": "gemini-3-flash-preview",
        "rotulo": "Gemini 3 Flash Preview",
        "score": 67,
        "preco_input": 0.50,
        "preco_output": 3.00,
        "tier": "padrao",
    },
    {
        "provider": PROVIDER_OPENROUTER,
        "model": "minimax/minimax-m3",
        "rotulo": "MiniMax M3",
        "score": 66,
        "preco_input": 0.30,
        "preco_output": 1.20,
        "tier": "economia",
    },
    {
        "provider": PROVIDER_OPENROUTER,
        "model": "x-ai/grok-4.5",
        "rotulo": "Grok 4.5",
        "score": 86,
        "preco_input": 2.00,
        "preco_output": 6.00,
        "tier": "poder",
    },
    {
        "provider": PROVIDER_GEMINI,
        "model": "gemini-3.1-pro-preview",
        "rotulo": "Gemini 3.1 Pro Preview (usado hoje)",
        "score": 77,
        "preco_input": 2.00,
        "preco_output": 12.00,
        "tier": "poder",
    },
    {
        "provider": PROVIDER_GEMINI,
        "model": "gemini-3.5-flash",
        "rotulo": "Gemini 3.5 Flash (usado hoje)",
        "score": 59,
        "preco_input": 1.50,
        "preco_output": 9.00,
        "tier": "padrao",
    },
]


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

# CP 3.3: `LLM_DEFAULT`/`LLM_TASKS` (a decisão de produto do MODELOS_IA.md)
# citam modelos por PROVIDER NATIVO, e um deles — Grok 4.5, em
# `categorizar_pdm` — usa `PROVIDER_XAI`, que `core/llm/client.py:get_llm()`
# NÃO roteia (só os 3 de `CHAVE_POR_PROVIDER` existem; ver CP 3.2). O
# OpenRouter é exatamente o gateway para esses casos (decisão de produto
# nº 2: "uma chave, catálogo amplo"), e é assim que `LLM_FAVORITOS` acima já
# expõe o Grok 4.5 na UI.
#
# Este mapa traduz um par (provider nativo, modelo) recomendado para a forma
# ROTEÁVEL equivalente. É consumido por
# `core/llm/selecao.py:aplicar_recomendados()`, para que o botão "Aplicar
# recomendados" da Home NUNCA grave uma seleção que `get_llm()` não consegue
# construir — sem isto, um clique no botão fazia `categorizar_pdm` levantar
# `NotImplementedError` na execução seguinte do módulo "Criar Fichas".
# Modelo recomendado sem provider roteável e sem entrada aqui é um erro de
# configuração: `aplicar_recomendados()` levanta `ValueError` na hora do
# clique, em vez de deixar a falha para o meio de um lote.
MODELO_RECOMENDADO_ROTEAVEL: dict[tuple[str, str], dict[str, str]] = {
    (PROVIDER_XAI, "grok-4.5"): {"provider": PROVIDER_OPENROUTER, "model": "x-ai/grok-4.5"},
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
    defaults: dict[str, str | None] = _limpar_chaves({
        chave_id: os.environ.get(env_var_name)
        for chave_id, env_var_name in ENV_VAR_POR_CHAVE.items()
    })

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
            return _limpar_chaves({**defaults, **saved})
    except Exception:
        return defaults


def _limpar_chaves(chaves: dict) -> dict:
    """Tira espaço/quebra de linha das pontas de cada chave.

    Parece detalhe e não é. Uma chave colada com um espaço ou um `\n` no fim
    -- o que acontece o tempo todo ao copiar do Google AI Studio, de um e-mail
    ou de um `.env` editado à mão -- chega ao Google TAL QUAL e volta como
    `400 API_KEY_INVALID`. A mensagem culpa a chave, o usuário confere e a
    chave está certa; o que está errado é invisível. Custou uma sessão inteira
    de diagnóstico para aparecer.

    Só mexe em `str`: um valor `None` (env var ausente) continua `None`, que é
    o que o resto do código espera para distinguir "não configurada" de
    "configurada vazia". A chave reservada `_modelos_ia` (CP 3.3) guarda um
    dicionário, não uma string, e por isso passa intacta.
    """
    return {
        nome: (valor.strip() if isinstance(valor, str) else valor)
        for nome, valor in chaves.items()
    }


def get_key(chaves: dict[str, str | None], key_id: str) -> str:
    """Réplica de `SIG_FT_App.get_key()` (frontend.py:4281-4282).

    `chaves.get(key_id, "")`: string vazia é o default só quando `key_id`
    está AUSENTE do dicionário. Se a chave existir mas seu valor for `None`
    (ex.: env var não configurada e sem override em `api_config.json`), o
    retorno é `None` — mesma peculiaridade do código original, preservada de
    propósito aqui (não é este checkpoint que decide corrigi-la).
    """
    return chaves.get(key_id, "")


# =============================================================================
# 8. LOGS / RASTREAMENTO DE USO DE IA (Checkpoint 3.4)
# =============================================================================
# Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.4, e
# `sigft/core/llm/usage.py` (UsageTracker: cada `LLMClient.generate()` grava
# um registro JSONL aqui — tokens, custo real/estimado, módulo, tarefa,
# duração, sucesso/erro). `logs/` já está listado no `.gitignore` (saída de
# execução por máquina, não versionada — mesmo espírito de `user_prefs.json`/
# `api_config.json`).

PASTA_LOGS = "logs"

# Caminho relativo (resolvido a partir do cwd do processo — raiz do
# repo/instalação), mesma convenção de `CONFIG_FILE`/`prefs.CONFIG_FILE`.
ARQUIVO_USO_LLM = os.path.join(PASTA_LOGS, "llm_usage.jsonl")


# =============================================================================
# 9. MOTOR DE RPA POR MÓDULO (Checkpoint 5.1)
# =============================================================================
# Ver docs/refatoracao/PLANO_REFATORACAO.md, decisão de produto nº 5 e Fase 5 ->
# CP 5.1: "Config `RPA_ENGINE = "selenium" | "playwright"` por módulo (permite
# migração gradual e rollback imediato)".
#
# A migração para Playwright é validada MÓDULO A MÓDULO contra o portal real
# (não há como testar offline). Uma chave por módulo é o que permite promover
# um módulo de cada vez e, se ele se comportar mal na sessão de validação,
# voltar o valor para "selenium" -- sem tocar em código, sem reverter commit.

ENGINE_SELENIUM = "selenium"
ENGINE_PLAYWRIGHT = "playwright"

# Enquanto a Fase 5 não termina (CP 5.5 descomissiona o Selenium), o padrão é o
# motor que já roda em produção há tempo. Um módulo ausente do mapa abaixo
# resolve por aqui.
RPA_ENGINE_PADRAO = ENGINE_SELENIUM

# Chave = nome do módulo em `sigft/services/`. Trocar para ENGINE_PLAYWRIGHT
# depois que o módulo for validado com o usuário no portal real.
RPA_ENGINE: dict[str, str] = {
    # Migrados (código pronto, aguardando a sessão de validação com o usuário):
    "apagar_lmr": ENGINE_SELENIUM,      # piloto do CP 5.1 -- fluxo completo
    "lmr": ENGINE_SELENIUM,             # CP 5.2 -- fluxo completo
    # CP 5.2 (atualização em massa) + CP 5.4 (criação de ficha individual):
    # o módulo inteiro roda nos dois motores.
    "cria_fichas": ENGINE_SELENIUM,
    "upload_conditions": ENGINE_SELENIUM,  # CP 5.3 -- fluxo completo
    "tech_specs": ENGINE_SELENIUM,      # CP 5.3 -- fluxo completo
    # Ainda não migrado:
    "ficha_duplicada": ENGINE_SELENIUM,  # Fase 6 (reconstruído já em Playwright)
}

# Override global por variável de ambiente, para o usuário experimentar o motor
# novo (ou voltar atrás) sem editar arquivo nenhum:
#
#     set SIGFT_RPA_ENGINE=playwright   &&  SIG-FT.bat
#
# Vence o mapa acima em TODOS os módulos -- é a alavanca de rollback imediato
# que o CP 5.1 pede, e também a forma mais rápida de rodar a sessão de
# validação de um checkpoint.
ENV_RPA_ENGINE = "SIGFT_RPA_ENGINE"


def get_rpa_engine(modulo: str) -> str:
    """Motor de RPA a usar em `modulo` — `ENGINE_SELENIUM` ou
    `ENGINE_PLAYWRIGHT`.

    Ordem de resolução: variável de ambiente `SIGFT_RPA_ENGINE` (global) ->
    `RPA_ENGINE[modulo]` -> `RPA_ENGINE_PADRAO`.

    Um valor desconhecido (erro de digitação na variável de ambiente, por
    exemplo) levanta `ValueError` em vez de cair no padrão em silêncio: um
    `SIGFT_RPA_ENGINE=playwrigth` que silenciosamente rodasse Selenium faria o
    usuário reportar como resultado do motor novo o que na verdade é o antigo
    — e é justamente esse tipo de confusão que invalidaria a sessão de
    validação de um checkpoint da Fase 5.
    """
    escolhido = os.environ.get(ENV_RPA_ENGINE) or RPA_ENGINE.get(modulo, RPA_ENGINE_PADRAO)
    escolhido = escolhido.strip().lower()
    if escolhido not in (ENGINE_SELENIUM, ENGINE_PLAYWRIGHT):
        raise ValueError(
            f"Motor de RPA desconhecido: {escolhido!r}. "
            f"Use {ENGINE_SELENIUM!r} ou {ENGINE_PLAYWRIGHT!r} "
            f"(verifique a variável de ambiente {ENV_RPA_ENGINE})."
        )
    return escolhido
