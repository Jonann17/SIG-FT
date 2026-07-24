# Documentação do SIG-FT

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

## Refatoração (`refatoracao/`)

- `PLANO_REFATORACAO.md` — diagnóstico, arquitetura-alvo e plano em 6 fases / 22 checkpoints,
  com critérios de aceite e quadro de status. **Documento mestre da refatoração.**
- `PENDENCIAS.md` — itens fora de escopo descobertos durante a execução.

## Como executar a refatoração

Em uma nova sessão do Claude Code neste repositório, os agentes de `.claude/agents/` estarão
disponíveis. Peça, por exemplo:

> Use o agente refactor-executor para executar o Checkpoint 0.1 do plano de refatoração.

Um checkpoint por vez, na ordem das fases. Para atualizar a documentação após mudanças:

> Use o agente doc-writer para atualizar docs/base-conhecimento/02-pdm-backend.md.
