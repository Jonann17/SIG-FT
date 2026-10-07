# Gerar o executável do SIG-FT

> Checkpoint 8.3 do plano de refatoração.

---

## Publicar uma versão (o caminho normal, desde a v1.0.0)

**São dois passos, e o resto é com a máquina:**

```bash
# 1. escreva o bloco da versão no CHANGELOG.md e faça commit
git commit -am "v1.0.1"

# 2. crie a tag
git tag v1.0.1 && git push origin v1.0.1
```

O `.github/workflows/release.yml` faz o resto no Windows do GitHub: roda lint e
testes como portão, compila com o PyInstaller, **abre o próprio `.exe`** para
conferir que a janela monta (`--smoke`) e que o bundle importa o que precisa
(`--conferir-pacote`), monta o instalador com o Inno Setup, calcula o SHA256 e
publica o Release. Os apps já instalados avisam sozinhos na próxima abertura.

> ⚠️ **Só da 1.1.1 em diante.** A 1.0.0 e a 1.1.0 nunca perguntavam ao GitHub
> (o serviço existia, mas nenhuma tela o chamava — o `latest.json` da v1.1.0
> ficou com zero downloads). Quem está nelas precisa instalar a 1.1.1, ou a
> mais nova, **à mão, uma vez**.

### Qual número usar

Regra do Luan (2026-09-25), com o passo a passo na skill
`.claude/skills/sigft-lancar-versao/`:

- **correção ou melhoria** de algo que já existe, mesmo reescrito por dentro →
  PATCH: `1.1.0` → `1.1.1` → `1.1.2`;
- **algo novo**, que não existia (módulo, tela) → MINOR: `1.2.0`;
- **mudança muito grande** → MAJOR: `2.0.0`.

Na dúvida, PATCH. O número não é enfeite: o app compara versões, e quem instala
uma versão com número alto demais, mesmo um pré-lançamento, para de receber as
seguintes pela atualização automática.

### Como o app instalado se atualiza (desde a 1.1.1)

1. **Toda abertura** pergunta ao GitHub pelo último Release, numa thread — a
   janela não espera. Pré-lançamento não conta (`/releases/latest` o ignora).
   Só pergunta o app **empacotado, instalado pelo instalador e com token**:
   rodando do código-fonte, do ZIP do Box ou de um build local, não há o que
   instalar por aqui (`updater.motivo_para_nao_verificar`).
2. Havendo versão nova, abre o aviso: versão atual → nova, data, tamanho e
   **o bloco do CHANGELOG** daquela versão (vem do `latest.json`). "Agora não"
   fecha; na próxima abertura ele volta.
3. **"Atualizar agora"** baixa pela API do asset, confere o SHA256, dispara o
   instalador em `/SILENT` com `/REABRIR=1` e encerra o app. O instalador
   troca os arquivos e **reabre o SIG-FT** na conta de quem estava usando
   (`[Run]` com `runasoriginaluser`, só quando recebe `/REABRIR=1`).

### Atualização pequena: só o que mudou (desde a 1.2.0)

Até a 1.1.1, toda atualização baixava e reinstalava o pacote inteiro (316 MB na
1.1.1, o tradutor sozinho com 218). Spec:
`docs/superpowers/specs/2026-10-07-atualizacao-incremental-design.md`.

- **No Release.** Além do instalador completo, o workflow publica o
  `arquivos.json` (cada arquivo instalado, com SHA256) e, contra o `arquivos.json`
  das versões anteriores (as 3 mais recentes que o publicaram, e a última normal
  sempre), um **instalador pequeno** por versão de origem:
  `SIG-FT_Itaipu_Atualizacao_<de>_para_<para>.bin`, com só os arquivos que
  mudaram. É o mesmo `installer/sigft.iss` em modo atualização
  (`/DAtualizacao=1 /DVersaoDe=...`): mesmo `AppId`, fecha e reabre o app como o
  completo, e **recusa** instalar se a versão instalada não for a `de` dele. A
  lista entra no `latest.json` (`atualizacoes`). Lógica em
  `tools/gerar_atualizacao.py`.
- **No app.** Se o `latest.json` traz um pequeno feito a partir da versão
  instalada, o aviso oferece **ele** ("12,3 MB: só o que mudou"); senão, o
  completo. Quem decide é o app instalado: a 1.1.1 só conhece o completo, então
  a primeira atualização a partir dela ainda vem inteira.
- **`.bin`, e não `.exe`**: o app 1.1.1 baixa "o primeiro `.exe` do Release". O
  app novo confere o SHA256 e o renomeia antes de rodar.
- Pequeno que não compensa (copiaria mais de 60% do pacote) ou que o ISCC não
  compilou **não sai**, com `::warning` no run: o completo serve para todos.
- A primeira versão com isto não tem base (ninguém publicou `arquivos.json`
  antes): ela sai só com o completo, e a seguinte já traz o pequeno.

### Canal de testes (desde a 1.2.0)

Caixa **"Versões de teste"** ao lado do botão "Atualizações" da tela inicial
(desmarcada por padrão; fica em `Documentos\SIG-FT\user_prefs.json`). Marcada, o
app consulta `/releases` em vez de `/releases/latest` e oferece também
**pré-lançamentos**. É como se testa uma rc pela atualização automática --
inclusive o instalador pequeno -- antes de ela chegar a todo mundo.

### "O instalador detectou que o SIG-FT Itaipu está em execução", com ele fechado

Visto ao instalar a 1.1.1-rc.1, em 2026-09-25. **Era um `SIG-FT.exe` vivo e sem
janela**: até a 1.1.1, fechar o app no meio de uma pausa do robô (esperando o
login, por exemplo) deixava o processo rodando escondido, e o `AppMutex` do
instalador acusava esse fantasma como "em execução" — sem oferecer fechá-lo.

- **Instalando por cima da 1.1.0 ou mais velha** (que ainda criam o fantasma):
  *Gerenciador de Tarefas* (Ctrl+Shift+Esc) → aba **Detalhes** → `SIG-FT.exe`
  → **Finalizar tarefa**, e depois OK no instalador. Ou, num prompt:
  `taskkill /F /IM SIG-FT.exe`.
- **Da 1.1.1 em diante** não acontece mais, pelos dois lados: fechar a janela
  encerra o processo (com tarefa em andamento, o app pergunta antes); e o
  instalador não usa mais `AppMutex` — o Restart Manager
  (`CloseApplications=force`) mostra o SIG-FT na tela "Preparando para
  instalar" e o fecha, inclusive o fantasma de uma versão antiga.

Sem conexão ou com o token recusado, a abertura fica **calada** — o motivo vai
só para o log. Para ver o motivo, use o botão **"Atualizações"** da tela
inicial: ele faz a mesma pergunta e sempre responde.

**Onde olhar quando uma máquina não atualiza:**

| O quê | Onde |
|---|---|
| a pergunta, o download e o erro | `Documentos\SIG-FT\logs\sigft.log` (linhas `[atualizacao]`) |
| o que o instalador fez | `%TEMP%\SIG-FT_Update\instalacao.log` |
| o instalador baixado (o completo ou o pequeno, já como `.exe`) | `%TEMP%\SIG-FT_Update\` |
| por que o pequeno não instalou (versão de origem diferente) | `%TEMP%\SIG-FT_Update\instalacao.log`, linha `Atualizacao recusada` |

### Sem permissão para criar tag?

Aba **Actions → Release → Run workflow**, e preencha o campo *versão*. Por esse
caminho quem cria a tag é o próprio runner, com o `GITHUB_TOKEN`. (Nem toda
credencial que empurra uma branch consegue empurrar uma tag; algumas recebem
403 em `refs/tags/`.)

### Testar sem ninguém receber

Publique um pré-lançamento: `1.1.0-rc.1` pelo botão, com a caixa
*pré-lançamento* marcada. O app consulta `/releases/latest`, que **por definição
do GitHub ignora pré-lançamentos** — então ninguém é avisado, e você instala o
`.exe` do Release à mão para testar. Da 1.2.0 em diante, quem marcou **"Versões
de teste"** na tela inicial recebe o pré-lançamento pelo aviso, como uma versão
normal.

### O CHANGELOG é obrigatório

`tests/test_novidades.py` reprova um commit em que `_build_info.VERSAO` não
tenha bloco correspondente no `CHANGELOG.md`, e o CI repete a checagem. Sem
isso, o defeito só apareceria **com a tag já criada**: o Release sairia com o
corpo vazio, e desfazer exige apagar o Release e a tag.

---

## Rotação do token de atualização

O repositório é **privado**, então o app precisa de um token para ler os
Releases. Ele é embutido no build pelo workflow, a partir do segredo
`UPDATE_TOKEN` (*Settings → Secrets and variables → Actions*).

> ### ⚠️ Um token embutido num `.exe` é extraível
>
> A ofuscação de `sigft/_ofuscacao.py` é um XOR com chave fixa, e a chave está
> no próprio arquivo. Ela serve para o token não aparecer num
> `strings SIG-FT.exe`, e para mais nada.
>
> **Por isso ele tem de ser, sem exceção:**
>
> - um PAT **fine-grained** (não um clássico);
> - **somente leitura** — `Contents: Read-only`, e nada além disso;
> - **restrito a este repositório**, nunca à conta inteira.
>
> Com essas três, o pior caso é alguém conseguir ler o código que essa pessoa
> já recebeu junto com o app.

**Para trocar o token:**

1. GitHub → *Settings → Developer settings → Personal access tokens →
   Fine-grained tokens* → **Generate new token**;
2. *Repository access* → **Only select repositories** → `luanccozer/SIG-FT`;
3. *Permissions → Repository permissions → Contents* → **Read-only**. Mais
   nada;
4. copie o valor e grave em *Settings → Secrets and variables → Actions →
   `UPDATE_TOKEN`*;
5. **revogue o token antigo** na mesma tela de tokens;
6. publique uma versão nova. Só os builds feitos a partir daí carregam o token
   novo.

### Enquanto a versão nova não sai

Os apps já instalados ficam sem atualização automática. A abertura não avisa
(ela é calada de propósito); o botão **"Atualizações"** da tela inicial mostra
"o GitHub recusou o token de atualização deste build". Dá para consertar **sem
refazer o build**, máquina a máquina: grave o token novo em

```
Documentos\SIG-FT\update_token.txt
```

Esse arquivo tem precedência sobre o token embutido. A variável de ambiente
`SIGFT_UPDATE_TOKEN` tem precedência sobre os dois.

### Build sem token

Um build local (pelo `Gerar-Executavel.bat`) não tem o segredo, e **isso é o
certo**: ele simplesmente não procura atualizações. O workflow avisa com um
`::warning::` quando o segredo não está configurado; nada quebra.

---

## Duas formas de rodar o SIG-FT

Duas formas de rodar o SIG-FT, e a escolha é sobre a **máquina de destino**:

| | `SIG-FT.bat` | `Gerar-Executavel.bat` |
|---|---|---|
| Precisa de Python na máquina | **sim** (3.10+) | não |
| Precisa rodar `pip` | sim | não |
| Atualizar para uma versão nova | `git pull` | gerar e copiar de novo |
| Tamanho | ~poucos MB + venv | ~700 MB (pasta) |
| Quando usar | seu computador, quem desenvolve | máquina travada, sem Python, sem permissão de instalar |

**Se a máquina de destino permite instalar Python, use o `SIG-FT.bat`.** É mais
rápido de atualizar e muito menor. O executável existe para o caso em que isso
não é possível.

> ### ⚠️ Antes de gerar isto para uma máquina corporativa
>
> Um executável PyInstaller **não assinado** é o artefato mais difícil de passar
> por uma revisão de segurança, e por dois motivos legítimos:
>
> 1. **sem assinatura de código**, é falso positivo frequente de antivírus
>    corporativo e não há cadeia de confiança para a TI validar;
> 2. **com o navegador embutido**, ele carrega um Chromium que **não recebe os
>    patches de segurança da política da empresa** — congela na versão do dia do
>    build e fica fora do inventário gerenciado pela TI.
>
> Por causa do item 2, **embutir o navegador virou opt-in em 2026-08-28**
> (`SIGFT_EMBUTIR_NAVEGADOR=1`). O padrão passou a ser o build SEM navegador.
>
> O caminho `SIG-FT.bat` é muito mais fácil de aprovar: Python oficial, pacotes
> do PyPI com versão declarada em `requirements.txt`, e Chromium do canal
> oficial do Playwright — atualizável como qualquer outro software.
>
> **Leia [`SEGURANCA_TI.md`](SEGURANCA_TI.md) antes da conversa com a TI.** Ele
> reúne o que costumam perguntar: conexões de saída, o que sai da máquina, o que
> é gravado em disco e por quê.

---

## Como gerar

```bat
Gerar-Executavel.bat
```

**Demora.** São centenas de MB (pandas, playwright, o Chromium). Da primeira
vez, conte vários minutos.

Sai em `dist\SIG-FT\SIG-FT.exe`.

---

## Como distribuir

**Copie a PASTA `dist\SIG-FT` inteira.** O `.exe` sozinho não funciona — ele
depende dos arquivos ao lado dele.

### Onde colocar a pasta na máquina de destino

Num lugar onde o usuário tenha **permissão de escrita**: a Área de Trabalho ou
a pasta Documentos servem. `C:\Program Files` **não serve**.

O motivo é concreto: as chaves de API (`api_config.json`), as preferências de
pasta (`user_prefs.json`), os logs e os caches de modelo são gravados **ao lado
do `.exe`**, não dentro dele. Isso é deliberado — dado de usuário precisa ser
gravável e precisa sobreviver a uma atualização do app.

---

## O navegador do Playwright, e por que ele é o ponto crítico

O RPA (todo módulo que mexe no portal PMIB) precisa do Chromium do Playwright.

O pacote `playwright` do pip **não traz o navegador**: ele baixa depois, de
`cdn.playwright.dev`. E esse download é feito por um processo **Node**, que
ignora as variáveis de certificado do Python — ele só respeita
`NODE_EXTRA_CA_CERTS`. Numa rede com inspeção SSL (Zscaler, Netskope, Blue
Coat), é o passo que mais falha.

**O build PODE resolver isso embutindo o navegador no pacote — mas não faz
mais isso por padrão.**

```bat
set SIGFT_EMBUTIR_NAVEGADOR=1
Gerar-Executavel.bat
```

Com a variável definida, o `Gerar-Executavel.bat` define
`PLAYWRIGHT_BROWSERS_PATH=0` antes do `playwright install`, o que faz o Chromium
ser instalado *dentro* do pacote `playwright` em vez de em
`%LOCALAPPDATA%\ms-playwright` — e daí o `SIG-FT.spec` o leva junto. Quem roda o
`.exe` não baixa nada.

**Por que isso deixou de ser o padrão:** um Chromium embutido não recebe os
patches de segurança da política da empresa. Ele congela na versão do dia do
build e fica fora do inventário que a TI gerencia — que é a objeção mais forte,
e mais justa, numa revisão de segurança corporativa. Trocar um problema de
instalação por um navegador desatualizado permanente não é um bom negócio, e
essa decisão não cabe a quem gera o build sozinho.

**O caminho padrão, sem embutir:** a máquina de destino instala o Chromium à
parte, com o `Instalar-Playwright.bat` (que já trata `NODE_EXTRA_CA_CERTS`). O
`.exe` sai bem menor e o navegador continua recebendo atualização.

> ⚠️ Se o download falhar **na máquina onde você GERA o executável**, o build
> continua e avisa. O `.exe` sai funcionando para tudo, menos o RPA. Isso é de
> propósito: parar o build deixaria você sem nada, e as outras telas funcionam.
> Para resolver, veja a seção "Rede corporativa (Zscaler)" do
> [`README.md`](../README.md), item 3.

---

## Rede corporativa: o que o executável resolve e o que não resolve

| Problema | O `.exe` resolve? |
|---|---|
| Não pode instalar Python | ✅ sim |
| `pip` bloqueado pelo proxy | ✅ sim (nada é instalado no destino) |
| Download do Chromium bloqueado | ⚠️ só com `SIGFT_EMBUTIR_NAVEGADOR=1` — leia a ressalva de segurança acima |
| **Chamadas de IA com `CERTIFICATE_VERIFY_FAILED`** | ⚠️ **provavelmente sim** — ver abaixo |
| Portal PMIB inacessível pela rede | ❌ não (é questão de acesso, não do app) |

Sobre as chamadas de IA: o `SIG-FT.spec` inclui `pip_system_certs` no bundle.
Esse pacote não é importado por ninguém — ele age no import do Python e faz o
SSL usar o **repositório de certificados do Windows**, onde a TI normalmente já
instalou a raiz do Zscaler. É o que faz Gemini, OpenRouter e Google CSE
funcionarem atrás do proxy.

Se mesmo assim aparecer `CERTIFICATE_VERIFY_FAILED`, o caminho é o mesmo do
modo `.bat`: exportar o certificado raiz da empresa e apontar
`REQUESTS_CA_BUNDLE`/`SSL_CERT_FILE` para ele. Ver
[`README.md`](../README.md), seção "Rede corporativa (Zscaler)".

---

## Decisões do build, e o porquê de cada uma

Estão comentadas no [`SIG-FT.spec`](../SIG-FT.spec); o resumo:

**Pasta (`--onedir`), não arquivo único (`--onefile`).** O `--onefile`
descompacta tudo num diretório temporário a cada execução. Aqui isso custaria
caro em três frentes: a abertura ficaria lenta (o splash existe justamente para
encurtar a espera), um `.exe` que se descompacta sozinho em `%TEMP%` é o padrão
que mais dispara heurística de antivírus corporativo, e o Chromium precisa de
um caminho estável.

**Console ligado (`console=True`), mesmo sendo app de janela.** É o canal de
diagnóstico real: o splash imprime "Erro ao carregar &lt;módulo&gt;" ali. Numa
primeira execução em máquina nova — que é o caso da GE Vernova — esconder o
console troca uma mensagem clara (`CERTIFICATE_VERIFY_FAILED`) por "não
funciona". Quando o app estiver estável lá, vale reconsiderar.

**Sem UPX.** Compressão de executável é outro gatilho clássico de antivírus.

**`hiddenimports` com os 11 backends.** O splash os importa por NOME
(`importlib.import_module`, ver `sigft/app/backends.py`), e import dinâmico é
invisível para a análise estática do PyInstaller. Sem declarar, o `.exe` abre e
os 11 falham um por um na barra de progresso.

**O modelo do tradutor local vai dentro (2026-09-25).** A tela 4.2 traduz na
própria máquina com o OPUS-MT `tc-big-itc-itc` (Helsinki-NLP, CC-BY 4.0)
convertido para CTranslate2 int8. O `SIG-FT.spec` embute
`recursos/tradutor_pt_es` como `modelos/tradutor_pt_es` (~218 MB; o
instalador cresce ~200 MB). Ver a seção seguinte.

---

## O tradutor local: de onde vem o modelo

A pasta `recursos/tradutor_pt_es/` **não está no Git** (é pesada). Quem a gera
é `tools/preparar_tradutor.py`, que baixa do Hugging Face a revisão **fixa**
no script e converte para CTranslate2:

```
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install "transformers<5" huggingface_hub ctranslate2 sentencepiece
python tools/preparar_tradutor.py
python tools/preparar_tradutor.py --verificar      # 0 = pronta
```

- **No Release** isso é automático: o passo "Preparar o tradutor local" roda
  ANTES dos testes (os testes com o modelo de verdade rodam no Windows) e do
  PyInstaller, num venv à parte (o `torch` nunca chega ao ambiente do build;
  o spec ainda exclui `torch` e `transformers`, por garantia), com cache pela
  revisão. A `--conferir-pacote` traduz "Aço inoxidável" DENTRO do `.exe`: se
  o modelo não entrou ou a DLL do CTranslate2 não carrega, o Release para antes
  de publicar.
- **No `Gerar-Executavel.bat`** (build local): rode o script acima antes. Sem
  a pasta o build segue, avisa, e só a tela 4.2 fica sem traduzir.
- **Rodando pelo código-fonte**: o mesmo script, ou copie a pasta
  `_internal\modelos\tradutor_pt_es` de uma instalação para
  `Documentos\SIG-FT\modelos\`.
- **Trocar o modelo** é decisão, não atualização: mude `REVISAO` no script e
  refaça a medição do spec `docs/superpowers/specs/2026-09-25-tradutor-local-design.md`.
- **Licença**: CC-BY 4.0 pede atribuição. Ela vai no `LEIA-ME.txt` e no
  `README.md` do autor, dentro da própria pasta do modelo.

---

## ⚠️ O limite de 260 caracteres do Windows (MAX_PATH)

**Este é o problema que mais provavelmente vai aparecer**, e o
`Gerar-Executavel.bat` já o contorna — mas vale saber por quê, porque o sintoma
engana.

O Windows limita caminho a 260 caracteres, e por padrão esse limite está
**ligado** (`HKLM\SYSTEM\CurrentControlSet\Control\FileSystem` →
`LongPathsEnabled = 0`; confirmado como `0` na máquina onde isto foi escrito).

A árvore interna do Chromium sozinha gasta ~157 caracteres:

```
_internal/playwright/driver/package/.local-browsers/chromium_headless_shell-1234/chrome-headless-shell-win64/...
```

Com o projeto dentro do OneDrive, a raiz já consome ~93. Soma: estoura.

**O sintoma engana:** o PyInstaller morre no meio da cópia com

```
FileNotFoundError: [WinError 206] O nome do arquivo ou a extensão é muito grande
```

e deixa uma pasta `dist/` **pela metade, que parece pronta** — o `.exe` está
lá, abre, e só falha na hora do RPA.

**A solução, já embutida no `.bat`:** o build acontece em
`%LOCALAPPDATA%\SIG-FT\dist-exe` (caminho curto, onde o venv já mora) e o
resultado é copiado de volta para `dist\SIG-FT`. Se até a cópia estourar, o
`.bat` avisa e diz para distribuir direto da pasta curta — o executável está
pronto de qualquer forma.

**Se você tiver direito de administrador** e quiser resolver de vez na sua
máquina, dá para liberar caminhos longos:

```bat
reg add "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f
```

Exige reiniciar. Numa máquina corporativa isso normalmente não é permitido — e
não é preciso, porque o `.bat` já contorna.

---

## Problemas comuns

**"Failed to execute script" ao abrir o `.exe`.**
Rode pelo terminal (`cd` até a pasta e `SIG-FT.exe`) para ver a mensagem. Quase
sempre é um módulo faltando em `hiddenimports` no `SIG-FT.spec`.

**O app abre mas todos os módulos falham no splash.**
Falta de `hiddenimports`. Confira se o backend novo entrou na lista da spec.

**Antivírus apagou o `.exe`.**
Executável não assinado gerado por PyInstaller é falso positivo frequente. Peça
à TI para liberar a pasta. Assinar o executável resolve de vez, mas exige um
certificado de code signing.

**O `.exe` abre sem ícone/logo.**
`assets/` não entrou no bundle. Confira a linha `("assets", "assets")` em
`datas` na spec — e veja `tests/test_app_recursos.py`, que existe por causa de
um defeito exatamente assim.

**O RPA diz que o navegador não foi encontrado.**
O Chromium não entrou no bundle. Refaça o build garantindo que
`PLAYWRIGHT_BROWSERS_PATH=0` está definido **antes** do `playwright install` —
é o que o `Gerar-Executavel.bat` faz. Alternativa na máquina de destino:
apontar para um Chrome/Edge já instalado, com
`SIGFT_PLAYWRIGHT_EXECUTABLE=C:\Program Files\Google\Chrome\Application\chrome.exe`.
