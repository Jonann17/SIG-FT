# SIG-FT — Sistema Integrado de Gestão de Fichas Técnicas

Aplicativo desktop (Python + CustomTkinter) para gerenciar o sistema de entrega de materiais
sobressalentes do projeto de Itaipu: criação de fichas técnicas no Portal PMIB, geração de
planilhas para fornecedores, automação RPA (Selenium) no portal oficial e gestão do processo
por planilhas Excel.

## Como executar

```bash
pip install -r requirements.txt
python frontend.py
```

- **Entry point**: `frontend.py` (abre a Splash Screen, que carrega os backends dinamicamente e abre o app).
- **Windows**: os módulos Tradutor (`xlwings`, exige Excel instalado) e alguns recursos (`os.startfile`) só funcionam em Windows.
- **Logo**: coloque `assets/logo.png` (não versionado) para exibir a marca na splash e sidebar. O app funciona sem ela.

## Configuração de chaves API

As chaves **não são versionadas**. Configure por um dos meios:

1. Arquivo `.env` na raiz (carregado via `python-dotenv`):
   ```
   API_GEMINI_LUAN_GMAIL=...
   GOOGLE_SEARCH_API=...
   GOOGLE_CSE_API=...
   LLAMA_CLOUD_API=...
   ```
2. Pela tela Home do app ("Configuração de Chaves API"), que grava em `api_config.json` (ignorado pelo git).

## Estrutura atual (pré-refatoração)

| Arquivo | Papel |
|---|---|
| `frontend.py` | UI completa: 12 módulos + Home + Splash + App principal |
| `cria_fichas_no_pmib_v1_backend.py` | Criação de fichas no PMIB (Excel + IA Gemini + RPA) |
| `pdm_backend.py` | Fatiamento/formatação de PDMs e geração de planilhas de fichas |
| `analyzer_backend.py` | Validação e pontuação de fichas técnicas via IA |
| `translator_backend.py` | Tradução PT→ES das especificações (xlwings) |
| `upload_conditions_backend.py` | IA + RPA para aba de Condições no portal |
| `upload_tech_specs_backend.py` | IA + RPA para Características Técnicas no portal |
| `upload_ficha_duplicada.py` | Clonagem de fichas (extrator + injetor RPA) |
| `autospec_backend.py` | AutoSpec AI: RAG (PDFs locais + busca web) para preencher fichas |
| `lmr_backend.py` | Cadastro de aplicações LMR no portal |
| `apagar_lmr_backend.py` | Exclusão em massa de aplicações LMR |
| `pmib_manager_backend.py` | Gestão macro: renomeação, planilha mestra, KPIs |
| `search_pmib_backend.py` | Busca de materiais nos arquivos `_STATUS_PMIB` |

## Documentação

- `docs/base-conhecimento/` — o que cada módulo faz, em detalhe.
- `docs/refatoracao/PLANO_REFATORACAO.md` — arquitetura-alvo e plano de refatoração em fases/checkpoints.
- `.claude/agents/` — agentes (modelos mais baratos) usados para documentação e execução da refatoração.
