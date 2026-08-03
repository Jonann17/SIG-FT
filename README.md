# SIG-FT — Sistema Integrado de Gestão de Fichas Técnicas

Aplicativo desktop (Python + CustomTkinter) para gerenciar o sistema de entrega de materiais
sobressalentes do projeto de Itaipu: criação de fichas técnicas no Portal PMIB, geração de
planilhas para fornecedores, automação RPA (Selenium) no portal oficial e gestão do processo
por planilhas Excel.

## Como executar

### Windows (uso normal)

1. Baixe o repositório em **Code → Download ZIP** e extraia a pasta.
2. Dê **dois cliques em `SIG-FT.bat`**.

Na primeira execução ele cria o ambiente virtual e instala as dependências
(alguns minutos, com uma janela preta mostrando o progresso). Nas execuções
seguintes ele apenas abre o aplicativo. Só é preciso ter o **Python 3.10 ou mais
novo** instalado ([python.org/downloads](https://www.python.org/downloads/) —
marque *"Add python.exe to PATH"* na primeira tela do instalador).

Para conferir se a instalação está sã, `Testar-SIG-FT.bat` roda a suíte de
testes automatizados: é offline, não abre navegador, não chama IA e não toca no
portal PMIB.

Detalhes de comportamento dos dois `.bat`:

| Situação | O que acontece |
|---|---|
| Ambiente virtual já existe | Abre direto, sem reinstalar nada |
| `requirements.txt` mudou (ex.: você baixou um ZIP novo) | Reinstala só o que mudou, comparando o hash guardado dentro do venv |
| Projeto dentro de OneDrive/Box/Dropbox/Google Drive | Cria o venv em `%LOCALAPPDATA%\SIG-FT\venv`, para o serviço não sincronizar milhares de arquivos |
| Quer apontar para um venv específico | Defina a variável de ambiente `SIGFT_VENV` |
| Quer recomeçar do zero | Apague a pasta `.venv` (ou `%LOCALAPPDATA%\SIG-FT\venv`) e rode de novo |

### Linha de comando (qualquer sistema)

```bash
pip install -r requirements.txt
python frontend.py
```

- **Entry point**: `frontend.py` (abre a Splash Screen, que carrega os backends dinamicamente e abre o app).
- **Windows**: os módulos Tradutor (`xlwings`, exige Excel instalado) e alguns recursos (`os.startfile`) só funcionam em Windows.
- **Logo**: coloque `assets/logo.png` (não versionado) para exibir a marca na splash e sidebar. O app funciona sem ela.

## Rede corporativa (Zscaler)

Redes com inspeção SSL (Zscaler, Netskope, Blue Coat…) substituem o certificado
de todo site HTTPS pelo certificado da própria empresa. Isso atrapalha em **dois
momentos diferentes** — e resolver um não resolve o outro:

**1. Na instalação (o `pip` não baixa os pacotes).** Sintoma: `SSLError`,
`CERTIFICATE_VERIFY_FAILED` ou `Could not fetch URL`. Os `.bat` já usam
`--index-url https://pypi.org/simple --trusted-host pypi.org --trusted-host
files.pythonhosted.org`, que cobre o caso comum. Se a sua rede exigir outra
coisa (índice interno, proxy autenticado, certificado da empresa), copie
`pip_corporativo.txt.exemplo` para `pip_corporativo.txt` e ajuste — o arquivo é
ignorado pelo git, é configuração da sua máquina. A variável de ambiente
`SIGFT_PIP_ARGS` tem prioridade sobre ele.

**2. Em uso (as chamadas do próprio app falham).** Gemini, OpenRouter e Google
CSE são HTTPS e passam pelo mesmo proxy. O `requirements.txt` já instala
[`pip-system-certs`](https://pypi.org/project/pip-system-certs/) no Windows, que
faz o Python usar o repositório de certificados do sistema — onde a TI
normalmente já instalou a raiz do Zscaler. Isso costuma bastar.

Se ainda assim aparecer `CERTIFICATE_VERIFY_FAILED` ao usar a IA, exporte o
certificado raiz da empresa (`certmgr.msc` → *Autoridades de Certificação Raiz
Confiáveis* → exportar como Base-64 `.cer`) e aponte o Python para ele:

```bat
setx REQUESTS_CA_BUNDLE C:\certs\zscaler-root.pem
setx SSL_CERT_FILE      C:\certs\zscaler-root.pem
```

Feche e reabra o terminal depois do `setx`. Se o arquivo só tiver a raiz da
empresa, sites fora do proxy podem parar de validar — nesse caso concatene o
bundle do `certifi` com o certificado da empresa em um único `.pem`:

```bat
.venv\Scripts\python -c "import certifi,shutil,sys; shutil.copy(certifi.where(), 'C:\\certs\\bundle.pem')"
type C:\certs\zscaler-root.pem >> C:\certs\bundle.pem
```

e aponte as duas variáveis para `C:\certs\bundle.pem`.

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
- `docs/refatoracao/PLANO_REFATORACAO.md` — decisões de produto, arquitetura-alvo e plano de
  refatoração em fases/checkpoints (inclui IA multi-provedor com rastreamento de custos,
  migração para Playwright e reconstrução do módulo de fichas duplicadas).
- `.claude/agents/` — agentes (modelos mais baratos) usados para documentação e execução da refatoração.
- `.claude/skills/` — skills `sigft-novo-modulo` e `sigft-melhorar-modulo` para desenvolvimento guiado.
