# Documentação do SIG-FT

## Portal PMIB — leia antes de mexer em RPA

| Doc | Para quê |
|---|---|
| [`PORTAL_COMO_ELE_SE_COMPORTA.md`](PORTAL_COMO_ELE_SE_COMPORTA.md) | **como o portal se comporta de verdade** — as armadilhas medidas na tela, e o checklist antes do commit |
| [`PMIB_ENGENHARIA_REVERSA.md`](PMIB_ENGENHARIA_REVERSA.md) | **o que está por trás da tela**, lido no código do próprio portal: status, regras de validação, modelo de dados, endpoints, nomes internos dos campos — e a lista priorizada do que isso muda no SIG-FT |
| [`OLHAR_O_PORTAL.md`](OLHAR_O_PORTAL.md) | como abrir o navegador e enxergar o portal numa sessão local |
| [`ROTEIRO_DE_TESTE.md`](ROTEIRO_DE_TESTE.md) | validação manual, do ZIP até o portal |

## Base de conhecimento (`base-conhecimento/`)

O que cada módulo faz hoje, em detalhe — gerada por agentes (Haiku) a partir da leitura do
código e revisada. Um arquivo por módulo:

| Doc | Módulo |
|---|---|
| `00-frontend.md` | UI completa (`frontend.py`) |
| `01-cria-fichas-backend.md` | `cria_fichas_no_pmib_v1_backend.py` |
| `02-pdm-backend.md` | `pdm_backend.py` |
| `03-analyzer-backend.md` | `analyzer_backend.py` |
| `04-translator-backend.md` | `translator_backend.py` |
| `05-upload-conditions-backend.md` | `upload_conditions_backend.py` |
| `06-upload-tech-specs-backend.md` | `upload_tech_specs_backend.py` |
| `07-upload-ficha-duplicada.md` | `upload_ficha_duplicada.py` |
| `08-autospec-backend.md` | `autospec_backend.py` |
| `09-lmr-backend.md` | `lmr_backend.py` |
| `10-apagar-lmr-backend.md` | `apagar_lmr_backend.py` |
| `11-pmib-manager-backend.md` | `pmib_manager_backend.py` |
| `12-search-pmib-backend.md` | `search_pmib_backend.py` |
| `13-montagem-da-ficha-tecnica.md` | a ficha técnica do PMIB, seção a seção |
| `14-aconex-e-conferencia-de-revisoes.md` | Aconex, Conferência de Revisões e Revisão no AMP |
| `15-upload-fotos.md` | `sigft/services/upload_fotos.py` (Upload de Fotos) |

## Refatoração (`refatoracao/`)

- `PLANO_REFATORACAO.md` — decisões de produto, diagnóstico, arquitetura-alvo e plano em
  9 fases (0–8) / 36 checkpoints, com critérios de aceite e quadro de status.
  **Documento mestre da refatoração.** Destaques: camada de IA multi-provedor com OpenRouter
  como gateway padrão, seleção de modelo pela interface e rastreamento de custos reais
  (Fase 3), migração Selenium→Playwright (Fase 5) e reconstrução do módulo de fichas
  duplicadas com testes interativos (Fase 6).
- `MODELOS_IA.md` — decisão de qual LLM usar: perfil de cada tarefa e tabela score×preço
  (aimultiple, jul/2026). **Padrão: Gemini 3 Flash Preview; poder de decisão: Grok 4.5;
  economia máxima opt-in: MiniMax M3.** Alimenta `config.LLM_TASKS`, o seletor da UI (CP 3.3)
  e a tabela de custos (CP 3.4).
- `PENDENCIAS.md` — itens fora de escopo descobertos durante a execução.
- `ESPEC_FICHA_DUPLICADA.md` — criado no CP 6.1 (especificação do módulo reconstruído).

## Agentes e Skills

- `.claude/agents/doc-writer.md` (Haiku) — escreve/atualiza a base de conhecimento.
- `.claude/agents/refactor-executor.md` (Sonnet) — executa um checkpoint do plano por vez.
- `.claude/skills/sigft-novo-modulo/` — guia para criar um módulo novo a partir de uma ideia.
- `.claude/skills/sigft-melhorar-modulo/` — guia para evoluir um módulo existente com segurança.
- `.claude/skills/sigft-lancar-versao/` — número da versão, pré-lançamento para testar e release.

## Como executar a refatoração

Em uma nova sessão do Claude Code neste repositório, os agentes e skills acima estarão
disponíveis. Peça, por exemplo:

> Use o agente refactor-executor para executar o Checkpoint 0.1 do plano de refatoração.

Um checkpoint por vez, na ordem das fases (checkpoints das Fases 5 e 6 terminam em validação
sua contra o portal real). Para atualizar a documentação após mudanças:

> Use o agente doc-writer para atualizar docs/base-conhecimento/02-pdm-backend.md.

Para desenvolvimento fora da refatoração:

> /sigft-novo-modulo — quero um módulo que ...
> /sigft-melhorar-modulo — o módulo X deveria ...
> /sigft-lancar-versao — solta um pré-lançamento pra testar
