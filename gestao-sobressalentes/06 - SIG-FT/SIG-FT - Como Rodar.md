---
tags: [sigft, operacao]
---

# SIG-FT — Como Rodar

## Windows, uso normal

1. Baixe o repositorio em **Code -> Download ZIP** e extraia.
2. **Dois cliques em `SIG-FT.bat`.**

Na primeira execução ele cria o ambiente virtual e instala as dependências (alguns
minutos, com janela preta mostrando o progresso). Depois só abre.

Requisito: **Python 3.10+**, com *"Add python.exe to PATH"* marcado na instalacao.

### Comportamento dos `.bat`

| Situação | O que acontece |
|---|---|
| Venv já existe | abre direto |
| `requirements.txt` mudou | reinstala só o que mudou, comparando o hash guardado no venv |
| **Projeto dentro de OneDrive/Box/Dropbox/Drive** | cria o venv em `%LOCALAPPDATA%\SIG-FT\venv`, para o serviço não sincronizar milhares de arquivos |
| Quer apontar um venv específico | variável `SIGFT_VENV` |
| Quer recomecar do zero | apague `.venv` (ou `%LOCALAPPDATA%\SIG-FT\venv`) e rode de novo |

## Os outros `.bat`

| Arquivo | Para que |
|---|---|
| `Testar-SIG-FT.bat` | roda a suite. **Offline** — não abre navegador, não chama IA, não toca no portal |
| `Gerar-Dados-de-Teste.bat` | cria `dados_de_teste/` com planilhas **sinteticas** |
| `Instalar-Playwright.bat` | baixa o navegador (~150 MB). Uma vez só |
| `Smoke-Playwright.bat` | exercita o Playwright contra página local offline |
| `Gerar-Executavel.bat` / `Gerar-Pacote.bat` | build |
| `Diagnostico-Erro.bat` | coleta ambiente para depuracao |
| `Listar-Duplicadas.bat` | lista as fichas duplicadas de um `_STATUS_PMIB` |

> [!warning] O que os dados de teste NÃO provam
> A estrutura das planilhas sinteticas vem de `sigft/config.py` e
> `sigft/core/rpa/ficha_layout.py` — ou seja, **do que o código espera**. Se a ficha
> real da Itaipu divergir disso, o gerador reproduz a expectativa do código e a
> divergência contínua invisivel.
>
> Servem para *"o módulo roda e a tela funciona"*, não para *"o layout está certo"*.
> Para isso, **só uma ficha real**.

## Linha de comando

```bash
pip install -r requirements.txt
python frontend.py
```

`frontend.py` abre a splash, que carrega os backends dinamicamente e abre o app.

> Tradutor (`xlwings`, exige Excel instalado) e alguns recursos (`os.startfile`)
> **só funcionam no Windows**.

## Chaves de API

**Não são versionadas.** Duas opções:

1. Arquivo `.env` na raiz (via `python-dotenv`):
   ```
   API_GEMINI_LUAN_GMAIL=...
   GOOGLE_SEARCH_API=...
   GOOGLE_CSE_API=...
   LLAMA_CLOUD_API=...
   ```
2. Pela tela **Home** do app, que grava em `api_config.json` (ignorado pelo git).

## Rede corporativa (Zscaler)

Redes com inspecao SSL trocam o certificado de todo site HTTPS. Isso atrapalha em
**três momentos diferentes**, e resolver um não resolve os outros:

### 1. Na instalacao — o `pip` não baixa
Sintoma: `SSLError`, `CERTIFICATE_VERIFY_FAILED`, `Could not fetch URL`.
Os `.bat` já usam `--index-url https://pypi.org/simple --trusted-host pypi.org
--trusted-host files.pythonhosted.org`. Se a rede exigir mais, copie
`pip_corporativo.txt.exemplo` para `pip_corporativo.txt` e ajuste
(a variável `SIGFT_PIP_ARGS` tem prioridade).

### 2. Em uso — as chamadas de IA falham
O `requirements.txt` já instala **`pip-system-certs`** no Windows, que faz o Python usar
o repositorio de certificados do sistema. Costuma bastar.

Se ainda falhar, exporte a raiz da empresa (`certmgr.msc` -> Autoridades de
Certificacao Raiz Confiaveis -> Base-64 `.cer`) e:
```bat
setx REQUESTS_CA_BUNDLE C:\certs\zscaler-root.pem
setx SSL_CERT_FILE      C:\certs\zscaler-root.pem
```
Feche e reabra o terminal. Se só a raiz da empresa estiver no arquivo, sites fora do
proxy podem parar de validar — nesse caso concatene o bundle do `certifi` com o
certificado da empresa num único `.pem`.

### 3. No download do navegador do Playwright
Esse download **não passa pelo pip** — quem baixa e o processo Node do Playwright, que
**ignora** `REQUESTS_CA_BUNDLE`/`SSL_CERT_FILE`. A variável que ele respeita e:
```bat
setx NODE_EXTRA_CA_CERTS C:\certs\zscaler-root.pem
```

Se a rede bloquear o Chromium e a TI mantiver Chrome ou Edge instalado:
```bat
set SIGFT_PLAYWRIGHT_EXECUTABLE=C:\Program Files\Google\Chrome\Application\chrome.exe
```

## O que exige rede da empresa
Os módulos de RPA (Criar Fichas, LMR, Apagar LMR, Condições, Características Técnicas,
Ficha Duplicada) precisam do **portal PMIB**, que só responde de dentro da rede.

Os módulos que só mexem em Excel — **Buscar Material, PDM, Analyzer, AutoSpec e Gestão
PMIB** — rodam em qualquer máquina.

## Relacionados
[[SIG-FT - Motor de RPA]] · [[SIG-FT - Modulos]] · [[SIG-FT - Visao Geral]]
