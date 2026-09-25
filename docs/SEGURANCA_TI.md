# SIG-FT — informações para a revisão de segurança da TI

Documento para a conversa com a equipe de segurança da GE Vernova antes de
instalar o SIG-FT numa máquina corporativa.

Tudo aqui foi levantado do código-fonte, não de memória. Onde há um caminho de
arquivo entre crases, ele é verificável no repositório.

---

## 1. O que o aplicativo é

Aplicativo **desktop**, escrito em Python com interface CustomTkinter, que
automatiza a gestão de fichas técnicas de materiais sobressalentes do projeto
Itaipu. Roda **na estação do usuário**, com as credenciais do próprio usuário.

Não é serviço, não abre porta de escuta, não instala driver, não pede
privilégio de administrador e não roda em background — só enquanto a janela
está aberta.

O código-fonte é auditável por completo: <https://github.com/luanccozer/SIG-FT>

---

## 2. Dois modos de instalação — e qual pedir

| | **`SIG-FT.bat`** (recomendado) | **Executável PyInstaller** |
|---|---|---|
| Pré-requisito | Python 3.10+ instalado | nenhum |
| Origem dos pacotes | PyPI, versões em `requirements.txt` | embutidos no binário |
| Navegador do RPA | Chromium do canal oficial do Playwright, **atualizável** | opcional; se embutido, **congela na versão do build** |
| Auditabilidade | alta — cada dependência é declarada e verificável | baixa — binário opaco |
| Assinatura de código | não se aplica | **não assinado** |

**Peça o `SIG-FT.bat`.** É o caminho que a TI consegue auditar: usa o Python
oficial, instala pacotes declarados e versionados, e o navegador vem do canal
oficial do fornecedor, recebendo atualização como qualquer outro.

O executável existe para o caso de a máquina **não poder** ter Python. Ele tem
duas desvantagens que a equipe de segurança vai (com razão) levantar:

1. **Não é assinado.** PyInstaller sem assinatura é falso positivo frequente de
   antivírus corporativo, e não há cadeia de confiança para validar.
2. **Se gerado com o navegador embutido, carrega um Chromium que não recebe os
   patches da política da empresa** — ele fica fora do inventário gerenciado
   pela TI.

Por causa do item 2, embutir o navegador é **desligado por padrão** desde
2026-08-28. Só acontece se quem gera o build definir explicitamente
`SIGFT_EMBUTIR_NAVEGADOR=1`. Ver `docs/BUILD.md`.

---

## 3. Conexões de rede que o app abre

Todas são **HTTPS de saída**, iniciadas pelo app. Nenhuma porta é aberta para
entrada.

### 3.1 Em uso normal

| Destino | Para quê | Quando |
|---|---|---|
| `apps.itaipu.gov.br` | Portal PMIB — é o sistema que o app automatiza | sempre que um módulo de RPA roda |
| `openrouter.ai` | Gateway de IA (padrão) — análise e preenchimento de fichas | só nos módulos com IA |
| `generativelanguage.googleapis.com` | API do Google Gemini — caminho direto alternativo ao gateway | só se configurado |
| `www.googleapis.com/customsearch/v1` | Google Custom Search — busca de datasheets do módulo AutoSpec | só no AutoSpec, quando a busca web é usada |

O endpoint de IA é **configurável**: o app aceita um endpoint
OpenAI-compatível interno da empresa (`EMPRESA_LLM_BASE_URL`), justamente para
o caso de a política proibir gateway de terceiro. Se a TI preferir, dá para
operar sem nenhuma chamada a IA externa.

### 3.2 Só na instalação

| Destino | Para quê |
|---|---|
| `pypi.org` / `files.pythonhosted.org` | download dos pacotes Python |
| `cdn.playwright.dev` | download do Chromium do Playwright |

Ambos aceitam índice interno/proxy da empresa — ver `pip_corporativo.txt.exemplo`
e a seção "Rede corporativa (Zscaler)" do `README.md`.

---

## 4. Dados: o que sai da máquina

**O que sai:** o conteúdo das fichas técnicas enviado às APIs de IA para
análise/preenchimento, quando um módulo de IA é usado.

Isso é uma decisão de negócio, não um detalhe técnico, e o projeto já a
registra como pendência aberta (`docs/refatoracao/PENDENCIAS.md`, entrada
"Conteúdo sensível trafegando por gateway de terceiro"). **Vale confirmar com a
TI e com o consórcio se as fichas podem trafegar por OpenRouter/Google.** Se
não puderem, os caminhos são: usar o endpoint interno da empresa, ou não usar
os módulos de IA — o resto do app funciona sem eles.

**O que NÃO sai:** o app não faz telemetria, não envia relatório de uso, não
"liga para casa". As únicas conexões de saída são as quatro da tabela acima.

**A tradução PT -> ES do Tradutor Técnico (tela 4.2) não sai da máquina**
desde a versão 1.2.0: ela roda num modelo embutido no instalador (OPUS-MT, da
Universidade de Helsinque, licença CC-BY 4.0), na CPU, sem rede. Até a 1.1.0
cada resposta de ficha ia para o Google Tradutor e para o MyMemory (serviços
públicos gratuitos, sem contrato), endereços que esta tabela nem listava.

**Credenciais do portal:** o app **não coleta, não armazena e não transmite** a
senha do PMIB. O login é feito pelo próprio usuário, à mão, na janela do
navegador — o app pausa e espera (é o diálogo "Ação Manual Necessária").

---

## 5. O que o app grava em disco

| Caminho | Conteúdo |
|---|---|
| `api_config.json` (pasta da instalação) | chaves de API de IA, se o usuário optar por salvá-las aqui em vez de variável de ambiente |
| `user_prefs.json` (pasta da instalação) | últimas pastas usadas nos diálogos de arquivo |
| `logs/` (pasta da instalação) | log de execução e `llm_usage.jsonl` (consumo/custo das chamadas de IA) |
| `%LOCALAPPDATA%\SIG-FT\perfil-navegador` | perfil do Chromium, para o login no portal sobreviver entre execuções |
| pastas escolhidas pelo usuário | as planilhas Excel que o app gera |

Nada é gravado em `Program Files`, no registro do Windows ou em área de outro
usuário.

O `api_config.json` guarda chaves em texto. Se a política exigir, elas podem
ser fornecidas por **variável de ambiente** (`.env` ou variável do sistema) em
vez do arquivo — o app aceita os dois.

---

## 6. Dependências

Declaradas em `requirements.txt`, todas do PyPI:

`customtkinter`, `pillow` (interface) · `pandas`, `openpyxl`, `xlwings`
(Excel) · `playwright` (automação do navegador) · `google-generativeai`,
`llama-parse` (IA) · `pymupdf`, `PyPDF2`, `beautifulsoup4`, `requests`,
`python-dotenv`, `unidecode`, `deep-translator` (utilidades) ·
`ctranslate2`, `sentencepiece` (tradutor local, sem rede) ·
`pip-system-certs` (só Windows — ver abaixo)

**`pip-system-certs` merece nota**, porque é o único cuja finalidade é mexer em
validação de TLS: ele faz o Python usar o **repositório de certificados do
Windows** em vez do bundle fixo do `certifi`. O efeito é o oposto de enfraquecer
segurança — é o que permite ao app **confiar no certificado raiz do Zscaler que
a própria TI instalou**, em vez de o usuário desligar a verificação. Sem ele, o
caminho comum seria alguém contornar o erro de certificado da forma errada.

`xlwings` automatiza o Excel instalado (COM) e só é usado pelo módulo de
tradução.

---

## 7. Perguntas que a TI costuma fazer

**Precisa de administrador?** Não, para rodar. A instalação do Python pode
precisar, dependendo de como for feita.

**Abre porta / aceita conexão de entrada?** Não.

**Roda em background / na inicialização?** Não. Só enquanto a janela está
aberta.

**Coleta senha do usuário?** Não. O login no portal é manual, feito pelo
usuário na janela do navegador.

**O que o Chromium do Playwright faz?** É o navegador que o robô controla para
preencher o portal PMIB — as mesmas ações que o usuário faria à mão. Ele abre
**visível** (modo headed), então o usuário vê tudo o que o robô está fazendo.

**Dá para restringir só ao portal, sem IA?** Dá. Os módulos de IA são telas
separadas; sem chave de API configurada, elas não funcionam e o resto continua
funcionando.

**Como atualizo?** No caminho `.bat`, `git pull` (ou substituir a pasta) e
rodar de novo — o script reinstala o que mudou.

---

## 8. Resumo de uma linha

Aplicativo desktop que roda com as credenciais do próprio usuário, automatiza
um portal web interno que ele já acessa manualmente, e opcionalmente envia
conteúdo de fichas técnicas para APIs de IA — este último ponto sendo o único
que merece decisão de política, e é configurável (inclusive para endpoint
interno da empresa).
