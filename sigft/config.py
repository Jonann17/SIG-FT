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

import datetime as _dt
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

# Linha (1-based) do cabeçalho da aba "Lista de Materiais" do `_STATUS_PMIB`
# no layout v2 -- e só o valor de RESERVA: quem lê ACHA o cabeçalho com
# `core.excel.headers.find_header_row`, e este número só vale quando a busca
# não acha nada (`duplicadas`, `pdm.ler_lista_materiais`). Também é a linha em
# que `scripts/gerar_dados_de_teste.py` escreve o cabeçalho sintético.
#
# Era 4 até 2026-10-05. Em 04/10/2026 os 47 `_STATUS_PMIB` e o template
# migraram para o layout v2 (`gestao-sobressalentes/07 - Diagnostico/Plano -
# Reestruturacao do STATUS_PMIB.md`): a linha 4 virou a da revisão em uso
# ("REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: 0A - DATA DE ALTERAÇÃO:
# ..."), mesclada e em TEXTO, e o cabeçalho desceu para a 5. As duas leituras
# que fixavam a linha 4 (`skiprows=3` no módulo PDM: a criação das pastas e o
# modo "selecionar códigos") passaram a tratar aquela frase como cabeçalho; a
# T0 do roteiro trocou as duas pela busca, e
# `tests/test_status_pmib_cabecalho_linha5.py` impede leitura fixa nova.
LINHA_STATUS_PMIB = 5


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

# Coluna MARCA/MODELO do `_STATUS_PMIB` (2026-08-13). Guarda os dois juntos,
# separados por barra: `WAGO / 750-362`, `NIDEC / MOD SVTN 3K6 W`.
#
# É a informação MAIS VALIOSA da planilha para a busca web, e o AutoSpec a
# ignorava: as fichas WAGO processadas pelo Luan tinham `fabricante` e
# `texto breve` VAZIOS na própria ficha, então a busca ia com o código
# interno da Itaipu (`1000325606`) -- que não existe na internet -- e voltava
# sem nada. Medido: `WAGO 750-362 datasheet` devolve 10 datasheets reais,
# incluindo o oficial do fabricante.
COL_MARCA_MODELO = "MARCA/MODELO"
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

COL_DOCS_IMAGENS = "DOCUMENTOS E IMAGENS"
# Era literal solto em `frontend._worker_salvar` -- a única das quatro colunas
# de seção que não tinha constante. Ganhou uma em 2026-08-17, quando a marcação
# COMPLETO/INCOMPLETO passou a ser calculada por seção em vez de fixa.

COL_INFO_GERAIS = "INFO. GERAIS"
# upload_ficha_duplicada, pmib_manager_backend (coluna de seção "COMPLETO"
# do STATUS_PMIB).

COL_APLICACAO_LMR = "APLICAÇÃO - LMR"
# Acrescentada em 2026-08-28, a pedido do usuário: a tela de Aplicação LMR
# passa a marcar no `_STATUS_PMIB` se a ficha ficou COMPLETO/INCOMPLETO, como
# as outras quatro seções já faziam.
#
# O nome acima é o que está na planilha real, confirmado pelo usuário em
# 2026-08-28 — com o hífen cercado de espaços, que é o detalhe que faria uma
# constante "APLICAÇÃO LMR" não casar.
#
# ⚠️ Por que ALIASES, se o nome já é conhecido: o casamento de cabeçalho
# (`core/excel/headers.find_columns`) é EXATO depois de `strip()`+`upper()`.
# Uma planilha salva com "APLICACAO - LMR" (sem cedilha/til, o que acontece
# quando o arquivo passa por exportação) ou sem o hífen deixaria de casar, e o
# sintoma seria a marcação silenciosamente não acontecer. A lista cobre as
# variações plausíveis da MESMA coluna; a primeira é a oficial.
ALIASES_COL_APLICACAO_LMR = [
    "APLICAÇÃO - LMR",
    "APLICACAO - LMR",
    "APLICAÇÃO LMR",
    "APLICACAO LMR",
    "APLICAÇÕES LMR",
    "APLICACOES LMR",
    "LMR",
]


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
#
# ⚠️ ISTO NÃO É O CATÁLOGO DE TAREFAS. O catálogo é `LLM_TASKS`, logo abaixo.
#
# Este mapa é uma FOTOGRAFIA de 2026-08: as 5 tarefas que existiam antes do
# CP 3.1, com o modelo que cada módulo tinha hardcoded. Ele NÃO cresce quando
# uma tarefa nova nasce — tarefa nova não tem "modelo de antes" para
# caracterizar, e inventar um faria o baseline mentir (há teste guardando isso
# em `tests/test_config.py`).
#
# PARA QUEM FOR ACRESCENTAR UMA TAREFA DE IA — e isto custou uma pasta de 1192
# arquivos processada errada em 2026-09-03, então leia antes de escrever:
#
#   1. Acrescente em `LLM_TASKS` (o catálogo).
#   2. Acrescente em `_POLITICA_RETRY_POR_TAREFA`, em `core/llm/client.py`.
#   3. NÃO acrescente aqui.
#   4. Rode `pytest tests/test_llm_get_llm_factory.py` — o teste
#      `test_TODA_tarefa_de_LLM_TASKS_e_resolvivel_por_get_llm` é quem cobra
#      o passo 2.
#
# O que aconteceu em 2026-09-03: `traduzir_pdm` foi registrada em `LLM_TASKS`
# e em mais nenhum lugar. `get_llm` usava ESTE mapa como catálogo, e a tarefa
# ficou 100% inalcançável em produção desde o dia em que nasceu — com a suíte
# verde, porque o guard que existia estava ancorado neste mesmo mapa
# incompleto. Um mapa não pode ser, ao mesmo tempo, o objeto testado e a lista
# do que testar.
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
    # [2026-08-28] traducao PT->EN das perguntas dos PDMs Modificados, para a
    # ficha em ingles. Frases curtas, em lote, volume baixo (roda uma vez por
    # pasta e o resultado fica em cache) -- o modelo padrao dá conta.
    "traduzir_pdm": {"provider": PROVIDER_GEMINI, "model": "gemini-3-flash-preview"},
    # [2026-10-08] passada 1 da escolha de PDM (Cria Fichas): diz o que cada
    # material E, no vocabulario do catalogo, antes da busca. Sem catalogo no
    # prompt e saida curta -- o modelo padrao da conta, e a falha so degrada
    # para a busca de hoje (spec 2026-10-08-escolha-de-pdm-em-duas-passadas).
    "interpretar_material": {"provider": PROVIDER_GEMINI, "model": "gemini-3-flash-preview"},
}

# As tarefas que o painel "Modelos de IA" lista no modo avançado (2026-10-16):
# as de antes (`LLM_MODELOS_HOJE`) e as novas que só existem em `LLM_TASKS`
# (`traduzir_pdm`, `interpretar_material`). Fora do painel, uma tarefa nova não
# tinha como ganhar modelo próprio e caía no fallback (Gemini direto).
TAREFAS_DO_PAINEL: tuple[str, ...] = tuple(sorted(set(LLM_MODELOS_HOJE) | set(LLM_TASKS)))

# Tarefa que SEGUE a escolha de outra no painel "Modelos de IA" quando não
# tem escolha própria (2026-10-16). A passada 1 do Cria Fichas não aparece no
# painel: sem isto ela caía no fallback (Gemini direto) mesmo com o Cria
# Fichas apontado para o OpenRouter -- e a VPN da empresa derruba o Gemini
# direto. Ordem: escolha da tarefa > escolha da tarefa que ela segue > global.
LLM_TAREFA_SEGUE: dict[str, str] = {
    "interpretar_material": "categorizar_pdm",
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

# NOME do arquivo de cache do catálogo `GET /models` — a pasta vem de
# `core/dados_usuario` (`Documentos\SIG-FT\`), como a de `CONFIG_FILE`. Nunca
# relativo ao cwd: no app instalado ele é `Program Files`, que não grava.
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


def caminho_config() -> str:
    """Onde o `api_config.json` mora DE VERDADE: `Documentos\\SIG-FT\\`.

    Era um nome relativo, resolvido a partir do diretório de trabalho — ou
    seja, da pasta do programa. Com o instalador o padrão passa a ser
    `Program Files`, onde usuário comum não escreve: as chaves sumiriam a
    cada abertura. E a atualização reescreve a pasta do programa, então elas
    seriam apagadas a cada versão nova.

    `CONFIG_FILE` continua existindo como NOME do arquivo — é o default do
    parâmetro `config_path` de `carregar_chaves`, que os testes sobrescrevem
    com `tmp_path`. Quem quer o caminho real chama esta função.
    """
    from sigft.core.dados_usuario import caminho

    return str(caminho(CONFIG_FILE))

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


def carregar_chaves(config_path: str | os.PathLike[str] | None = None) -> dict[str, str | None]:
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
    # `None` -> o caminho real, resolvido AGORA. Tardio de propósito: se o
    # default fosse `caminho_config()`, ele seria avaliado no import e a pasta
    # de dados ficaria congelada antes de `SIGFT_DADOS_DIR` poder apontá-la.
    if config_path is None:
        config_path = caminho_config()

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

# NOMES relativos: quem grava resolve na pasta de dados (`Documentos\SIG-FT\`,
# `usage._no_lugar_certo` e `dados_usuario.pasta_logs`), nunca no cwd — que no
# app instalado é `Program Files` e não grava (2026-09-25).
ARQUIVO_USO_LLM = os.path.join(PASTA_LOGS, "llm_usage.jsonl")


# =============================================================================
# 9. MOTOR DE RPA POR MÓDULO (Checkpoint 5.1)
# =============================================================================
# Ver docs/refatoracao/PLANO_REFATORACAO.md, decisão de produto nº 5 e Fase 5 ->
# CP 5.5 (2026-08-25): aqui morava a escolha de motor -- `ENGINE_SELENIUM`, o
# mapa `RPA_ENGINE` por módulo, a variável `SIGFT_RPA_ENGINE`,
# `get_rpa_engine()` e `resumo_dos_motores()`. Tudo isso existia para uma
# coisa só: permitir voltar um módulo para o Selenium se ele se comportasse
# mal na sessão de validação do checkpoint.
#
# A Fase 6 fechou validada no portal real e o Selenium saiu do projeto.
# Migração terminada não tem rollback -- e uma flag que só aceita um valor
# não é configuração, é entulho que faz o leitor procurar uma alternativa
# que não existe.
#
# Quem sobe o motor é `core/rpa/factory.criar_engine`, e a regra que ele
# guarda continua de pé: nenhum serviço importa um motor concreto.
ENGINE_PLAYWRIGHT = "playwright"

# =============================================================================
# PLANILHA DE APLICAÇÕES LMR
# =============================================================================
# Nomes NOVOS, pedidos pelo usuário em 2026-08-11 -- "FICHA PMIB",
# "CÓDIGO LMR" e "TAG LMR" dizem o que a coluna é; os antigos (`PMIB`,
# `Código_PMIB`, `TAG_PMIB`) confundiam código de ficha com código de LMR.
#
# Os antigos continuam ACEITOS, e isso não é zelo excessivo: existem
# planilhas em uso hoje com o cabeçalho velho, e uma renomeação que quebra
# o arquivo de quem está no meio de um lote é pior do que não renomear. A
# lista é ordenada por preferência -- o primeiro nome encontrado vence.
LMR_COLUNAS = {
    "pmib": ("FICHA PMIB", "PMIB"),
    "codigo": ("CÓDIGO LMR", "CODIGO LMR", "Código_PMIB", "Codigo_PMIB"),
    "tag": ("TAG LMR", "TAG_PMIB", "TAG PMIB"),
}

# Abas candidatas, na ordem de preferência. Se nenhuma existir, a leitura
# procura em TODAS as abas do arquivo qual tem as colunas -- é o que o
# usuário chamou de "leitura automática": não ter de acertar o nome da aba.
LMR_ABAS = ("LMR", "GERAL", "Aplicações", "Aplicacoes")

# =============================================================================
# 10. AUTORIZAÇÃO DE ENTREGA DE ITAIPU (Gestão PMIB no tratamento v2)
# =============================================================================
# Itaipu tem 15 DIAS ÚTEIS, contados do e-mail de intenção de entrega, para
# autorizar a entrega física (decisão do Luan, 04-05/10/2026). Até 2026-10-05 o
# Gestão PMIB contava 14 dias CORRIDOS -- ver `services/autorizacao.py`, que é a
# ÚNICA implementação da regra (o Gestão PMIB grava, o painel HTML lê).
PRAZO_AUTORIZACAO_DIAS_UTEIS = 15

# Colunas do `_STATUS_PMIB` v2 (layout de 04/10/2026) que a regra lê e grava.
# Achadas pelo NOME na linha do cabeçalho, nunca pela letra da coluna: as listas
# têm colunas extras em posições diferentes.
COL_STATUS = "STATUS"
COL_TIPO_ENTREGA = "TIPO DE ENTREGA"
COL_DATA_EMAIL_ENTREGA = "DATA DO EMAIL COMUNICANDO ENTREGA"
COL_SITUACAO_AUTORIZACAO = "SITUAÇÃO DA AUTORIZAÇÃO"
COL_DIAS_ATRASO = "DIAS DE ATRASO"
COL_EQUIPAMENTO_ENTREGUE = "EQUIPAMENTO ENTREGUE"
# A coluna que a SITUAÇÃO substituiu (SIM virou AUTORIZADO). Só existe nos
# arquivos que ainda não migraram -- que são lidos, nunca gravados.
COL_APTO_PARA_ENTREGA = "APTO PARA ENTREGA"

# O começo do texto da linha ACIMA do cabeçalho que diz a revisão da lista em
# uso: "REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: 0A - DATA DE
# ALTERAÇÃO: 03/09/2026". Achada pelo texto, nunca pela coordenada.
TEXTO_LINHA_REVISAO = "REVISÃO DA LISTA DE SOBRESSALENTES"

# Nome definido que o Gestão PMIB grava em cada `_STATUS_PMIB` v2 que calculou:
# a data do cálculo, como texto "AAAA-MM-DD".
NOME_CALCULADO_EM = "sigft_calculado_em"

# Feriados que não contam como dia útil no prazo acima: nacionais do Brasil +
# os pontos facultativos de Carnaval e Corpus Christi, 2024-2028. Cópia do
# dicionário de `gestao-sobressalentes/_scripts/regras_sobressalentes.py`, que
# é também o que o Power BI v2 usa -- se mudar aqui, mude lá.
#
# DECISÃO EM ABERTO (do Luan): confirmar com Itaipu se entram os feriados do
# Paraguai e os municipais de Foz. Para tirar uma data, apague a linha; para
# acrescentar, uma linha nova. Num lugar só, de propósito.
FERIADOS: dict[_dt.date, str] = {
    _dt.date(2024, 1, 1): "Confraternização Universal",
    _dt.date(2024, 2, 12): "Carnaval (ponto facultativo)",
    _dt.date(2024, 2, 13): "Carnaval (ponto facultativo)",
    _dt.date(2024, 3, 29): "Sexta-feira Santa",
    _dt.date(2024, 4, 21): "Tiradentes",
    _dt.date(2024, 5, 1): "Dia do Trabalho",
    _dt.date(2024, 5, 30): "Corpus Christi (ponto facultativo)",
    _dt.date(2024, 9, 7): "Independência",
    _dt.date(2024, 10, 12): "Nossa Senhora Aparecida",
    _dt.date(2024, 11, 2): "Finados",
    _dt.date(2024, 11, 15): "Proclamação da República",
    _dt.date(2024, 11, 20): "Consciência Negra",
    _dt.date(2024, 12, 25): "Natal",
    _dt.date(2025, 1, 1): "Confraternização Universal",
    _dt.date(2025, 3, 3): "Carnaval (ponto facultativo)",
    _dt.date(2025, 3, 4): "Carnaval (ponto facultativo)",
    _dt.date(2025, 4, 18): "Sexta-feira Santa",
    _dt.date(2025, 4, 21): "Tiradentes",
    _dt.date(2025, 5, 1): "Dia do Trabalho",
    _dt.date(2025, 6, 19): "Corpus Christi (ponto facultativo)",
    _dt.date(2025, 9, 7): "Independência",
    _dt.date(2025, 10, 12): "Nossa Senhora Aparecida",
    _dt.date(2025, 11, 2): "Finados",
    _dt.date(2025, 11, 15): "Proclamação da República",
    _dt.date(2025, 11, 20): "Consciência Negra",
    _dt.date(2025, 12, 25): "Natal",
    _dt.date(2026, 1, 1): "Confraternização Universal",
    _dt.date(2026, 2, 16): "Carnaval (ponto facultativo)",
    _dt.date(2026, 2, 17): "Carnaval (ponto facultativo)",
    _dt.date(2026, 4, 3): "Sexta-feira Santa",
    _dt.date(2026, 4, 21): "Tiradentes",
    _dt.date(2026, 5, 1): "Dia do Trabalho",
    _dt.date(2026, 6, 4): "Corpus Christi (ponto facultativo)",
    _dt.date(2026, 9, 7): "Independência",
    _dt.date(2026, 10, 12): "Nossa Senhora Aparecida",
    _dt.date(2026, 11, 2): "Finados",
    _dt.date(2026, 11, 15): "Proclamação da República",
    _dt.date(2026, 11, 20): "Consciência Negra",
    _dt.date(2026, 12, 25): "Natal",
    _dt.date(2027, 1, 1): "Confraternização Universal",
    _dt.date(2027, 2, 8): "Carnaval (ponto facultativo)",
    _dt.date(2027, 2, 9): "Carnaval (ponto facultativo)",
    _dt.date(2027, 3, 26): "Sexta-feira Santa",
    _dt.date(2027, 4, 21): "Tiradentes",
    _dt.date(2027, 5, 1): "Dia do Trabalho",
    _dt.date(2027, 5, 27): "Corpus Christi (ponto facultativo)",
    _dt.date(2027, 9, 7): "Independência",
    _dt.date(2027, 10, 12): "Nossa Senhora Aparecida",
    _dt.date(2027, 11, 2): "Finados",
    _dt.date(2027, 11, 15): "Proclamação da República",
    _dt.date(2027, 11, 20): "Consciência Negra",
    _dt.date(2027, 12, 25): "Natal",
    _dt.date(2028, 1, 1): "Confraternização Universal",
    _dt.date(2028, 2, 28): "Carnaval (ponto facultativo)",
    _dt.date(2028, 2, 29): "Carnaval (ponto facultativo)",
    _dt.date(2028, 4, 14): "Sexta-feira Santa",
    _dt.date(2028, 4, 21): "Tiradentes",
    _dt.date(2028, 5, 1): "Dia do Trabalho",
    _dt.date(2028, 6, 15): "Corpus Christi (ponto facultativo)",
    _dt.date(2028, 9, 7): "Independência",
    _dt.date(2028, 10, 12): "Nossa Senhora Aparecida",
    _dt.date(2028, 11, 2): "Finados",
    _dt.date(2028, 11, 15): "Proclamação da República",
    _dt.date(2028, 11, 20): "Consciência Negra",
    _dt.date(2028, 12, 25): "Natal",
}
