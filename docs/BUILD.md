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
- **Pequeno que falha cai no completo** (`updater.baixar`, desde a 1.2.0-rc.5).
  Na rede da empresa, o Zscaler cortou o fim do `.bin` da rc.4 duas vezes
  (`IncompleteRead`: faltaram 883 bytes, depois 636 KB), e o completo, de 316 MB,
  passa pelo mesmo caminho. Corte, arquivo que não confere ou rota que não
  responde: o app baixa o completo do mesmo Release e diz isso na janela. Erro
  de disco não troca de arquivo. O log diz quanto chegou e quanto tempo a
  conexão ficou parada antes do corte.
- **O app não remenda o download cortado** (pedido parcial só do que faltou),
  de propósito: se o proxy segura o fim do arquivo para analisá-lo, pedir só o
  resto seria contornar a análise da empresa. Se o Zscaler barrar o pequeno
  sempre, o caminho é a TI liberar o endereço dos Releases ou o instalador
  passar a ter assinatura digital.
- Pequeno que não compensa (copiaria mais de 60% do pacote) ou que o ISCC não
  compilou **não sai**, com `::warning` no run: o completo serve para todos.
- A primeira versão com isto não tem base (ninguém publicou `arquivos.json`
  antes): ela sai só com o completo, e a seguinte já traz o pequeno.
- **Medido na 1.2.0-rc.4** (a partir da rc.3, mesmo código): **38,5 MB** contra
  316 MB do completo, 4 arquivos de 2048. O piso é o `SIG-FT.exe` (~38 MB): no
  onedir do PyInstaller ele leva TODO o código Python, o do SIG-FT e o das
  bibliotecas, e por isso muda em toda versão. Os `RECORD` do numpy e do tqdm
  também mudam a cada build (os lançadores `.exe` que o pip gera), mas são KB.

### Atualização por arquivos e o `/SINAL` (desde a 1.3.1)

Pedido do Jonathan depois de a pequena da 1.3.1-rc.1 cair no completo na
máquina do Luan: o método do CMI Suite. Spec:
`docs/superpowers/specs/2026-10-27-atualizacao-como-cmi-design.md`.

- **No Release**, ao lado de cada pequeno, o `.zip` só com os arquivos:
  `SIG-FT_Itaipu_Arquivos_<de>_para_<para>.zip` (`manifesto.json` +
  `arquivos/<caminho>`, `sigft/services/pacote_arquivos.py`), na chave
  `arquivos` da mesma entrada do `latest.json` (`arquivo`, `sha256`,
  `tamanho`). O `arquivos.json` de todo Release é o manifesto da versão nova.
- **No app** (`updater.pode_por_arquivos`): com o pacote no Release, o app
  empacotado e a pasta do programa **gravável de verdade** (instalação "só
  para mim", em `AppData\Local\Programs`), `updater.aplicar_por_arquivos`
  baixa o `arquivos.json` (conferido pelo `digest` da API) e o zip (conferido
  pelo SHA256 do `latest.json`), aplica com o app aberto (renomeia o antigo
  para `.sigft-old`, escreve o novo, confere a pasta contra o `arquivos.json`
  novo, desfaz tudo se algo falhar), regrava `DisplayVersion`/`DisplayName` no
  HKCU (a chave `ChaveDesinstalar` do `.iss`: o pequeno seguinte confere ali),
  **reabre** o `.exe` desacoplado e fecha. Os `.sigft-old` são apagados na
  abertura seguinte. Qualquer falha vai para o `sigft.log` e cai na corrente
  de sempre (zip → exe → bin → completo).
- **Pelo instalador**, `updater.instalar` passa `/SINAL=<%TEMP%\SIG-FT_Update\instalador_pronto.txt>`
  e **espera** o `InitializeSetup` do `.iss` criar o arquivo (até 10 min). Se
  o instalador sair antes, `InstaladorNaoIniciou` com o código de saída e o
  `instalacao.log`, e o app fica aberto com o erro na janela. No disparo
  elevado (erro 740 → `ShellExecute`) não há o processo: só o sinal e o tempo
  limite contam.
- Os apps já instalados ignoram a chave `arquivos` e o `/SINAL` sem efeito: o
  `.iss` só cria o arquivo quando recebe o parâmetro.

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

**A Qt vai, e só o que a interface usa (E6.2).** A plataforma e o estilo como
plugins, uma tradução, sem o QtNetwork e sem o OpenGL por software: a parte do
Qt no pacote do Windows cai de 78,4 para 43,2 MB. As licenças (LGPLv3) vão em
`_internal\licencas`. Ver "A interface Qt dentro do pacote".

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

## A interface Qt dentro do pacote (desde a E6.2)

Desde o corte (E6.1) o `.exe` abre a interface Qt (`sigft/app_qt/`), e desde
2026-10-15 só ela: a CustomTkinter saiu do SIG-FT, e o `SIG-FT.spec` exclui
`tkinter`, `_tkinter` e `customtkinter` (sem a exclusão, import opcional de
terceiros ainda traria o `_tkinter`, a libtcl/libtk e os dados do Tcl/Tk;
medido no Linux, saíram 334 arquivos e 9,2 MB). Até a E6.2 o `SIG-FT.spec`
deixava a Qt de fora de propósito; agora ela vai, e só o que a interface usa.

**O que vai:** o PySide6 e o shiboken6 -- as DLLs do Qt (`Qt6Core`, `Qt6Gui`,
`Qt6Widgets`), os `.pyd` e o runtime do MSVC que vem no wheel --, em
`_internal\PySide6` e `_internal\shiboken6`; dois tipos de plugin, a plataforma
(`qwindows`, mais as sem tela `qoffscreen` e `qminimal`) e o estilo nativo
(`qmodernwindowsstyle`: "windows11" e "windowsvista"); as traduções
`qtbase_pt_BR` e `qtbase_es` (os "Sim"/"Não"/"Cancelar" dos diálogos, no idioma
escolhido; o inglês é o do próprio Qt, 2026-10-22); as fontes, em
`_internal\assets\fonts`; e as licenças, em `_internal\licencas`.

**O que fica de fora, e quanto pesa** -- medido no wheel 6.12 do Windows, que é o
que vai no instalador (o PyInstaller não compila para outro sistema, então o
número sai do fecho das dependências de cada DLL, como o PyInstaller faz):

| Fora | Windows | Por quê |
|---|---|---|
| `opengl32sw.dll` | 20,6 MB | OpenGL por software, do Qt Quick e do QOpenGLWidget; a interface é QtWidgets puro, que desenha sem OpenGL |
| traduções do Qt, menos a `qtbase_pt_BR` e a `qtbase_es` | 6,7 MB | o app carrega a do idioma escolhido (`_instalar_traducao`, em `sigft/app_qt/main.py`) |
| plugins de imagem, SVG, toque, `qdirect2d`... | ~4 MB | o app carrega PNG, que o QtGui lê sem plugin; os ícones SVG são desenhados pelo módulo QtSvg (`QSvgRenderer`), que não precisa dos plugins. O `Qt6Svg.dll` VOLTOU ao pacote em 2026-10-20 (ícones do sistema visual), via `hiddenimports` |
| o módulo QtNetwork, o `Qt6Network.dll` e os plugins de TLS e de rede | 3,6 MB | ninguém o importa; quem o puxava era um import condicional do `PySide6/__init__.py` |
| **a Qt no pacote** | **78,4 → 43,2 MB** | |

Onde cada corte mora: os plugins no hook `empacotamento/hooks/hook-PySide6.QtGui.py`
(antes da análise, para não deixar órfãs as bibliotecas que eles puxam); o
QtNetwork nos `excludes` do `Analysis`; as traduções e o `opengl32sw.dll` num
filtro no fim do spec. `tests/test_qt_no_pacote.py` executa o spec e o hook com
dublês do PyInstaller.

No build de Linux usado para validar (2026-10-11, PySide6 6.12, só para medir --
não há Release de Linux): sem a Qt, 562,5 MB; com a Qt do jeito que o PyInstaller
a coleta, 693,9 MB (+131,4: no Linux entram também o ICU, 39 MB, e as
bibliotecas de X11, Wayland, EGL e GTK do sistema); com os cortes, 653,9 MB --
40 MB a menos, e nenhum arquivo do QtNetwork. O ICU não existe no wheel do
Windows.

**Precisa de algo que ficou de fora?** Um formato de imagem novo na interface
(SVG, JPEG...): acrescente a família `imageformats` no hook (e, se for SVG, o
`Qt6Svg` vem junto). Rede pelo Qt: tire o `PySide6.QtNetwork` dos `excludes` --
o teste reprova enquanto alguém importar o QtNetwork com ele lá. Outra tradução:
o filtro do fim do spec.

**Como o Release confere.** A `--conferir-pacote` carrega a Qt de verdade dentro
do `.exe` (`conferir_qt`, em `sigft/app/conferencia.py`), sem criar janela.
Esperado no Windows:

```
  OK     Qt carrega: PySide6 6.x, Qt 6.x (QtCore, QtGui, QtWidgets)
  OK     Qt: plataforma 'windows' (...\_internal\PySide6\plugins\platforms\qwindows.dll)
  OK     Qt: estilo nativo 'windowsvista'
  OK     Qt: traducao pt_BR (...\_internal\PySide6\translations\qtbase_pt_BR.qm)
  OK     Qt: traducao es (...\_internal\PySide6\translations\qtbase_es.qm)
  OK     Qt: fontes Roboto-Regular.ttf, NotoEmoji-Regular.ttf (...\_internal\assets\fonts)
```

O plugin da plataforma é **carregado**, e não só procurado: sem ele (ou sem uma
DLL de que ele depende) a linha sai FALHA ali, em vez de o Qt mostrar a caixa
modal "no Qt platform plugin could be initialized" e pendurar o passo `--smoke`
até o tempo-limite. Com `QT_QPA_PLATFORM` definida (o `--smoke` sem tela, os
testes), a plataforma conferida é a dela. Faltando o estilo nativo, o Qt cairia
no estilo "Windows" clássico sem avisar ninguém -- só esta conferência vê. E o
passo "Conferir que o pacote ficou completo" exige as três licenças.

**Licenças.** O Qt for Python vai sob a LGPLv3, que pede o aviso de que a
biblioteca está no programa, os textos da LGPL e da GPL junto, e a biblioteca
trocável. O wheel **não traz o texto da LGPL**: medido no 6.12, o do Windows tem
o `METADATA` (que declara `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`) e um
`LicenseRef-Qt-Commercial.txt` sobre a licença comercial; o de Linux, só o
`METADATA`. Por isso o aviso (`LEIA-ME-Qt.txt`) e os textos oficiais da FSF
(`LGPL-3.0.txt`, `GPL-3.0.txt`; o SHA-256 é conferido nos testes) moram em
`empacotamento/licencas/`, e os arquivos do wheel vêm do ambiente do build, na
versão que vai no pacote. Tudo cai em `_internal\licencas\`. As DLLs do Qt ficam
em arquivos separados -- mais um motivo para o `--onedir`: no `--onefile` elas
iriam dentro do `.exe`, e trocá-las deixaria de ser simples.

**A atualização pequena** da primeira versão com a Qt leva a Qt inteira (para
uma base CustomTkinter, são arquivos novos) além do `SIG-FT.exe` de sempre:
estimados uns 80 MB descompactados, bem acima dos 38,5 MB da rc.4, mas longe do
limite de 60% do pacote -- ela sai.

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

**Aparece "O SIG-FT não conseguiu abrir a janela" e o app não abre.** A Qt não
importou ou não subiu (desde 2026-10-15 não há mais interface antiga para cair).
A caixa traz o motivo, que também vai para `Documentos\SIG-FT\logs\sigft.log`.
Para ver o que falta no pacote, rode `SIG-FT.exe --conferir-pacote` de uma pasta
onde se possa gravar e leia as linhas `Qt` do `conferencia-do-pacote.txt`.

**Os diálogos aparecem em inglês ("Yes"/"No"/"Cancel") com o SIG-FT em
português ou espanhol.** A tradução `qtbase_pt_BR.qm` (ou `qtbase_es.qm`) não
entrou no pacote: as linhas `Qt: traducao pt_BR` e `Qt: traducao es` da
`--conferir-pacote` dizem onde ela foi procurada.

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
