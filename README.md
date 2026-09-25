# SIG-FT — Sistema Integrado de Gestão de Fichas Técnicas

Aplicativo desktop (Python + CustomTkinter) para gerenciar o sistema de entrega de materiais
sobressalentes do projeto de Itaipu: criação de fichas técnicas no Portal PMIB, geração de
planilhas para fornecedores, automação RPA (Selenium) no portal oficial e gestão do processo
por planilhas Excel.

> **Vai validar a refatoração?** Siga o roteiro passo a passo em
> [`docs/ROTEIRO_DE_TESTE.md`](docs/ROTEIRO_DE_TESTE.md) — do download do ZIP
> até os módulos no portal, com o que conferir em cada etapa.

## Como executar

### Windows (uso normal, desde a v1.0.0)

**Baixe o instalador** na [página de Releases](https://github.com/luanccozer/SIG-FT/releases)
e execute. Ele pergunta se quer instalar para todos os usuários (pede senha de
administrador) ou só para você (não pede, e as atualizações rodam sem popup).

Depois disso o app **se atualiza sozinho**: toda vez que abre, ele confere se
saiu versão nova e, se saiu, avisa, mostra o que mudou e instala com um clique
(e abre de novo, já atualizado). O botão **"Atualizações"** da tela inicial faz
a mesma pergunta na hora.

> **Está na 1.0.0 ou na 1.1.0?** Instale a 1.1.1 (ou mais nova) à mão, uma
> vez: aquelas duas versões não procuravam atualização. Da 1.1.1 em diante, as
> próximas chegam pelo aviso.

> **"O Windows protegeu o computador"** aparece na primeira vez, e não é vírus:
> o SmartScreen reclama de todo programa recém-compilado sem assinatura digital
> paga. Clique em **"Mais informações"** — é um link pequeno e cinza, e o botão
> **"Executar assim mesmo"** só aparece depois dele.

As chaves de API e as suas preferências ficam em `Documentos\SIG-FT\`, fora da
pasta do programa, então a atualização não encosta nelas. Quem já usava o SIG-FT
tem as chaves antigas importadas sozinhas na primeira abertura.

### Windows, a partir do código (para quem desenvolve)

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

### Testar sem ter dados reais em mãos

`Gerar-Dados-de-Teste.bat` cria a pasta `dados_de_teste/` com planilhas
**sintéticas** — duas fichas técnicas, dois `_STATUS_PMIB` e uma planilha de
aplicações LMR. Com elas dá para abrir o app e rodar de ponta a ponta os módulos
que só mexem em Excel: **Buscar Material, PDM, Analyzer, AutoSpec e Gestão
PMIB**.

O que essas planilhas **não** provam: a estrutura delas vem de `sigft/config.py`
e `sigft/core/rpa/ficha_layout.py`, ou seja, do que o *código* espera. Se a
ficha real da Itaipu divergir disso em algum ponto, o gerador reproduz a
expectativa do código e a divergência continua invisível. Servem para *"o módulo
roda e a tela funciona"*, não para *"o layout está certo"* — para isso, só uma
ficha real.

Os módulos de RPA (Criar Fichas, LMR, Condições, Características Técnicas,
Apagar LMR, Ficha Duplicada) continuam precisando do portal PMIB, que só é
acessível da rede da empresa.

Detalhes de comportamento dos `.bat`:

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

## Motor de RPA (Selenium ou Playwright)

**Use sempre o `SIG-FT.bat`.** Ele é o único atalho do dia a dia.

Quem escolhe o motor é a configuração, por módulo — `sigft/config.py`,
dicionário `RPA_ENGINE`. Desde a validação de **2026-08-11 o Playwright é o
padrão** dos cinco módulos portados; só `ficha_duplicada` continua em Selenium,
e ele nem consulta a configuração (constrói o driver direto) — some quando a
Fase 6 o reconstruir.

Ao abrir, a janela preta imprime qual motor cada módulo está usando. O texto é
**derivado do `RPA_ENGINE`**, não escrito à mão, então não tem como divergir:

```
[SIG-FT] Motor de automacao do portal:
[SIG-FT]    playwright: apagar_lmr, cria_fichas, lmr, tech_specs, upload_conditions
[SIG-FT]    selenium: ficha_duplicada (modulo antigo -- ignora esta configuracao)
```

Uma vez só, antes do primeiro uso do motor novo:

```bat
Instalar-Playwright.bat          REM baixa o navegador (~150 MB)
```

### Se o motor novo se comportar mal

**Dois cliques em `SIG-FT-Motor-Antigo.bat`.** Volta tudo para o Selenium, que
rodou em produção por meses. A janela preta avisa em letras claras que você
está no motor antigo, e nada fica gravado: fechou, acabou.

> Ele substituiu o antigo `SIG-FT-Playwright.bat`, que **não fazia diferença
> nenhuma** depois que o Playwright virou padrão — abria exatamente o mesmo
> aplicativo que o `SIG-FT.bat`, dando a impressão de ser uma escolha quando
> não era. Descoberto em 2026-08-17, quando o usuário rodou os dois na mesma
> planilha e obteve o mesmo resultado, sem saber se era coincidência.

> **Por que um arquivo próprio, e não "defina uma variável".** A instrução
> `set SIGFT_RPA_ENGINE=selenium` só funciona no **Prompt de Comando (cmd)**.
> No **PowerShell** — o terminal que o Windows abre por padrão hoje — `set` é
> outro comando (`Set-Variable`) e **não define variável de ambiente**: o app
> abriria no motor errado sem nenhum aviso. No PowerShell, o equivalente seria
> `$env:SIGFT_RPA_ENGINE = "selenium"` seguido de `.\SIG-FT.bat` (com o `.\`,
> que o PowerShell exige para rodar arquivo da pasta atual).

A variável vale para todos os módulos que aceitam a configuração e some quando
você fecha a janela. Um valor com erro de digitação (`playwrigth`) faz o app
parar com mensagem clara em vez de rodar o motor errado em silêncio.

O que já roda no motor novo:

| Módulo | Estado |
|---|---|
| Apagar LMR | migrado, fluxo completo |
| Cadastro LMR | migrado, fluxo completo |
| Criar Fichas (criação individual e atualização em massa) | migrado, fluxo completo |
| Upload Condições | migrado, fluxo completo |
| Upload Specs (Características Técnicas) | migrado, fluxo completo |
| Upload duplicadas (Ficha Duplicada) | **só Selenium** — será reconstruído na Fase 6 |

Nada disso foi validado contra o portal real ainda — é justamente o que a
sessão de teste vai dizer.

Um ganho prático do motor novo: ele usa um **perfil de navegador persistente**
(em `%LOCALAPPDATA%\SIG-FT\perfil-navegador`), então o login manual no PMIB
continua valendo na execução seguinte, em vez de recomeçar do zero toda vez.

### Conferir o motor sem o portal

`Smoke-Playwright.bat` abre um navegador e exercita as mesmas operações que os
módulos usam no PMIB — digitar, ler de volta, teclar, clicar, rolar, print de
tela — mas **contra uma página local, offline**. Serve para separar duas
perguntas que juntas viram uma depuração confusa:

- *"O Playwright funciona nesta máquina?"* — o smoke responde, em **qualquer**
  computador, sem ficha e sem acesso ao portal.
- *"O portal PMIB responde bem a ele?"* — só a sessão real, na máquina da
  empresa, responde.

Se o smoke passar em casa e falhar no trabalho, o dedo já aponta para a
rede/Zscaler em vez de para o código.

Se a rede bloquear o download do Chromium e a TI mantiver um Chrome ou Edge
instalado, dá para usar esse:

```bat
set SIGFT_PLAYWRIGHT_EXECUTABLE=C:\Program Files\Google\Chrome\Application\chrome.exe
```

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

**3. No download do navegador do Playwright.** Esse download não passa pelo
`pip`: quem baixa é o processo Node do Playwright, que ignora
`REQUESTS_CA_BUNDLE`/`SSL_CERT_FILE`. A variável que ele respeita é
`NODE_EXTRA_CA_CERTS`. O `Instalar-Playwright.bat` já reaproveita seu
`SSL_CERT_FILE` quando ele existe; se ainda falhar:

```bat
setx NODE_EXTRA_CA_CERTS C:\certs\zscaler-root.pem
```

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
- `.claude/skills/` — skills `sigft-novo-modulo` e `sigft-melhorar-modulo` para desenvolvimento guiado, e `sigft-lancar-versao` para numerar e publicar versões.
