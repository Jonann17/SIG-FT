# Levar o SIG-FT para uma máquina da GE Vernova

> **Desde a v1.0.0 há DOIS caminhos, e eles convivem de propósito.** Leia esta
> seção antes do resto do documento, que descreve só o segundo.

| | Instalador (novo) | ZIP no Box (o de sempre) |
|---|---|---|
| Como chega | Release do GitHub, baixado pelo próprio app | você copia o ZIP para o Box |
| Como atualiza | o app avisa e se atualiza com um clique | o `.bat` percebe na próxima abertura |
| Precisa de rede para o GitHub | **sim** | não |
| SmartScreen na primeira vez | **sim** (ver as notas do Release) | não |
| Como se publica | `git tag v1.0.1 && git push origin v1.0.1` | `Gerar-Pacote.bat` + copiar à mão |

## Por que os dois continuam existindo

O caminho do Box **não foi aposentado**, e a razão é concreta: o instalador
ainda **não foi validado numa máquina real**. Nada neste repositório pode
prová-lo — o `.iss` só compila no Windows com o Inno Setup, e que o instalador
instale por cima de si mesmo (fechando o app pelo `AppMutex`) só a instalação de
verdade diz.

Aposentar o único canal que funciona antes de provar o novo seria trocar o certo
pelo não verificado. **Quando você instalar uma versão pelo Release e confirmar
que a atualização automática funciona na rede da empresa**, o Box sai: é apagar
`SIG-FT Itaipu.bat`, `Gerar-Pacote.bat` e `tests/test_distribuicao_box.py`, e
tirar esta seção.

> ⚠️ **[2026-09-25] Essa validação só pode começar na 1.1.1.** Até a 1.1.0 o
> app instalado nunca perguntava ao GitHub: o serviço de atualização existia,
> mas nenhuma tela o chamava. O roteiro:
>
> 1. instale a **1.1.1 à mão**, pelo instalador do Release;
> 2. publique a versão seguinte como Release **normal** (um pré-lançamento não
>    é oferecido a ninguém — nem a você);
> 3. abra o SIG-FT: o aviso tem de aparecer sozinho, em poucos segundos;
> 4. "Atualizar agora": o app fecha, o instalador roda e o SIG-FT **reabre
>    sozinho** com a versão nova na barra de título.
>
> Se o aviso não aparecer, o botão **"Atualizações"** da tela inicial diz por
> quê. Os logs estão listados em [`BUILD.md`](BUILD.md), seção "Como o app
> instalado se atualiza".

> ⚠️ **Uma diferença que importa enquanto os dois existem:** quem instala pelo
> instalador tem as chaves de API em `Documentos\SIG-FT\`, e elas **não vêm no
> pacote** — o `.exe` publicado no GitHub não pode carregar segredo. Quem já
> usava o SIG-FT não sente nada (as chaves antigas são importadas sozinhas na
> primeira abertura); quem é novo precisa recebê-las por outro caminho. O Box
> serve: é um arquivo de 1 KB, não mais um ZIP de 415 MB.

---

## O esquema do Box (o segundo caminho)

O esquema é o mesmo que o **DocManager Itaipu** já usa: o app compilado vive
num ZIP no Box, e um `.bat` cuida de baixar, atualizar e abrir. Quem usa o
aplicativo não compila nada, não instala Python e não precisa de permissão de
administrador.

---

## Os dois arquivos que ficam no Box

Em `%USERPROFILE%\Box\CMI - Consórcio Itaipu	 - Ger. Engenharia
 - PDM\_python_pdm\`
(escolha do usuário em 2026-09-04):

| Arquivo | O que é |
|---|---|
| `SIG-FT Itaipu.bat` | O que o usuário clica. Copie da raiz do repositório. Só uma vez. |
| `SIG-FT.zip` | O app compilado. Gerado pelo `Gerar-Pacote.bat`. Trocado a cada versão. |

### O acento de "Consórcio", e por que o `.bat` não o contém

Um `.bat` é lido na **página de código do console** (850 ou 437 no Windows em
português), nunca em UTF-8. Um `ó` gravado no arquivo chega lá como bytes de
lixo: o caminho deixa de casar e o `if exist` falha **em silêncio** — o script
segue pelo galho errado sem erro nenhum, e o usuário cai no seletor de pasta
sem entender por quê.

Por isso o launcher resolve a pasta por curinga:

```bat
for /d %%D in ("%USERPROFILE%\Box\CMI - Cons*rcio Itaipu") do (
    set "REDE=%%D	 - Ger. Engenharia
 - PDM\_python_pdm"
)
```

O acento existe na **pasta**, nunca no arquivo. `tests/test_distribuicao_box.py`
falha se algum `.bat` do projeto ganhar um byte fora do ASCII.

---

## As chaves de API viajam no pacote

Decisão do usuário: *"quero que todos quem usa tenha acesso às mesmas chaves"*.
O `Gerar-Pacote.bat` copia o `api_config.json` para dentro do ZIP, ao lado do
`.exe` — que é onde o app o procura.

> ⚠️ **O `SIG-FT.zip` passa a conter segredo em texto claro.** Quem abrir o ZIP
> lê as chaves, e elas ficam também em texto claro no `%LOCALAPPDATA%` de cada
> máquina que rodar o app. A **permissão da pasta do Box passa a ser, sozinha,
> o controle de acesso às chaves.**
>
> Consequência prática: se alguém sair do time ou o ZIP vazar, a única saída é
> **rotacionar as chaves no provedor**. Vale mantê-las onde isso seja rápido.

O `.env` **não** é o canal: dentro do executável ele seria lido de dentro do
bundle (`resource_path`), não da pasta do `.exe`. O `api_config.json` é o
mecanismo único — e é o que a própria tela "Chaves de API" da Home grava.

---

## O diretório de trabalho: `start /d`

O launcher abre o app com `start "" /d "%LOCAL%\SIG-FT" ...`, e o `/d` não é
detalhe.

Sem ele o `.exe` herda o diretório de onde o `.bat` foi clicado — **a pasta do
Box**. Como `api_config.json` e `user_prefs.json` são resolvidos a partir do
diretório de trabalho, o estrago seria duplo: o app procuraria as chaves no
Box (e não acharia), e gravaria o `user_prefs.json` de cada usuário lá, **um
por cima do outro**.

---

## Tamanho do pacote, e o navegador que não pode entrar

Medido em 2026-09-04, compilando de verdade: **415 MB** em `dist\SIG-FT`.

Se der muito mais que isso, quase certamente entrou o Chromium do Playwright.
Foi o que aconteceu na primeira compilação: **1150 MB**, com o script
anunciando "Navegador NAO embutido (padrao)".

**Por que a variável de ambiente não bastava.** `SIGFT_EMBUTIR_NAVEGADOR`
decide se o `.bat` **instala** o navegador dentro do pacote `playwright`. Mas
qualquer coleta do pacote leva junto o que uma execução ANTERIOR deixou em
`.local-browsers` — uma vez embutido, ficava embutido para sempre. E não há
hook de playwright nem no PyInstaller nem no `pyinstaller-hooks-contrib`
(procurados os dois), então a entrada vinha por caminho que o `.spec` não
controlava na origem.

A solução foi filtrar o **resultado**: depois do `Analysis`, tudo o que cita
`.local-browsers` sai de `a.datas` e `a.binaries` — o único ponto por onde
todo arquivo empacotado passa. O build imprime quantos removeu:

```
[SIG-FT] navegador fora do pacote: 610 arquivos removidos
```

**Três motivos para isso importar, e o tamanho é o menor deles:**

1. a posição de segurança documentada em `SEGURANCA_TI.md` ("o pacote não leva
   navegador") virava falsa sem ninguém perceber;
2. os caminhos internos do Chromium passam dos **260 caracteres** do Windows —
   nem o PowerShell os lista, e o `tar` que extrai o ZIP na máquina de destino
   falha ali: o build "funciona" e a instalação sai quebrada;
3. o ZIP para o Box triplicava.

---

## O ícone

| Arquivo | Papel | Onde aparece |
|---|---|---|
| `assets/SIG-FT-logo-2.ico` | **ícone** | Barra de tarefas, barra de título, o arquivo `.exe` |
| `assets/logo.png` | **imagem** | Splash e barra lateral — o símbolo da GE Vernova, dentro da tela |

São coisas diferentes e trocá-las é o erro fácil. Decisão do usuário: o ícone
é o do SIG-FT; **dentro** do app continua a GE Vernova.

O `.ico` do repositório tem um tamanho só (256×256). O `Gerar-Executavel.bat`
gera `build/SIG-FT.ico` com 16, 24, 32, 48, 64, 128 e 256 — sem as medidas
pequenas o Windows reduz o 256 na hora e o ícone sai borrado na barra de
título.

---

## Partindo do download do GitHub

A branch `claude/checkpoint-01-refactor-executor-5lawtu` é a **padrão do
repositório**, então o botão *Code → Download ZIP* entrega exatamente o código
atual. São ~7 MB, e tudo o que o build precisa vem junto (`SIG-FT.spec`,
`scripts/_bootstrap_venv.bat`, `requirements.txt`, os `.bat` e o `assets/`).

1. Baixe e **extraia** o ZIP.
2. **Copie o seu `api_config.json` para a pasta extraída.** Ver abaixo.
   Não tem um? Copie o `api_config.example.json` como `api_config.json` e
   preencha — ele lista os campos e a variável de ambiente de cada um.
3. Rode `Gerar-Pacote.bat`. Ele cria o venv, instala as dependências, compila
   e produz o `SIG-FT.zip`.

> ⚠️ **O `api_config.json` NÃO vem no download, e isso é de propósito** — ele é
> ignorado pelo git para que chave nunca suba ao repositório. Quem compila a
> partir de um download novo e não copia o arquivo gera um pacote **sem
> chaves**, e só descobre na máquina de destino. O `Gerar-Pacote.bat` avisa e
> pára para você confirmar.

---

## Na sua máquina: gerar e publicar

```bat
Gerar-Pacote.bat
```

Ele compila (chamando o `Gerar-Executavel.bat`, que cuida do venv e do
PyInstaller) e produz `SIG-FT.zip` na raiz. Depois é só copiar esse ZIP para a
pasta do Box, por cima do anterior.

**Atualizar a versão na empresa = trocar o ZIP no Box.** Nada além disso: na
próxima abertura, o `.bat` percebe que há versão nova e se atualiza sozinho.

---

## Na máquina da GE Vernova: usar

Clicar em `SIG-FT Itaipu.bat`. Ele:

1. procura o `SIG-FT.zip` no Box (se não achar, abre um seletor de pasta);
2. compara as datas com `robocopy /XO /FFT` e **só baixa se houver versão
   mais nova**;
3. extrai em `%LOCALAPPDATA%\SIG-FT_CMI` — o app **nunca roda de dentro do
   Box**, que é pasta sincronizada;
4. aponta o RPA para o Chrome/Edge já instalado (ver abaixo);
5. abre o aplicativo.

### A trava de segurança do antivírus

Se o `.exe` sumir da pasta local, o script **força a reextração** mesmo sem
download novo. Isso não é zelo excessivo: executável gerado por PyInstaller sem
assinatura digital é falso positivo frequente de antivírus corporativo, e sem
essa trava o app simplesmente nunca mais abriria — com o `robocopy` insistindo
que está tudo em dia. É a mesma proteção que o `DocManager Itaipu.bat` tem.

---

## O navegador do RPA: usa o que a empresa já instala

**O pacote não leva navegador dentro**, e isso é decisão, não esquecimento.

Um Chromium embutido congela na versão do dia do build e fica fora do que a TI
atualiza — é a objeção mais forte numa revisão de segurança corporativa, e ela
é justa (ver [`SEGURANCA_TI.md`](SEGURANCA_TI.md)).

Em vez disso, o `SIG-FT Itaipu.bat` procura, nesta ordem:

1. `%ProgramFiles%\Google\Chrome\Application\chrome.exe`
2. o mesmo em `Program Files (x86)` e em `%LOCALAPPDATA%`
3. `msedge.exe` (Edge), nos dois `Program Files`

e define `SIGFT_PLAYWRIGHT_EXECUTABLE` com o que encontrar. O Chrome
corporativo é mantido atualizado pela própria TI — resolve tamanho do pacote,
segurança e atualização de uma vez.

**Verificado em 2026-08-28**: `scripts/smoke_playwright.py` rodou com o Chrome
instalado da máquina e passou nas 13 verificações, inclusive alcançando a
internet. Ou seja, o motor de RPA funciona sem o Chromium do Playwright.

Se nenhum navegador for encontrado, o app **abre normalmente** — só o robô do
portal é que vai reclamar quando for usado. As telas de planilha e de IA não
dependem dele.

---

## Se algo der errado lá

**O app abre e fecha sozinho, rápido demais para ler.** Use o
`Diagnostico-Erro.bat`: ele roda o app gravando tudo em
`logs\erro_<data>_<hora>.txt` e mostra as últimas linhas na tela. O arquivo tem
só o que o Python escreveu — sem ficha, sem planilha, sem chave de API.

**O antivírus apagou o executável.** É o caso previsto na trava acima: clicar
no `.bat` de novo resolve na hora. Se voltar a acontecer, peça a liberação à
TI — o argumento está no `SEGURANCA_TI.md`.

**Erro de certificado nas chamadas de IA.** Rede com inspeção SSL. O
`requirements.txt` já inclui o `pip-system-certs`, que faz o Python usar o
repositório de certificados do Windows — onde a TI normalmente já instalou a
raiz do Zscaler. Se persistir, ver a seção "Rede corporativa (Zscaler)" do
[`README.md`](../README.md).

**O RPA não acha navegador.** Confirme que há Chrome ou Edge instalado, ou
defina você mesmo antes de abrir:

```bat
set SIGFT_PLAYWRIGHT_EXECUTABLE=C:\caminho\para\chrome.exe
```

---

## Por que não um `.exe` único

O build é `--onedir` (uma pasta) de propósito. Com `--onefile`, o executável
descompacta tudo num diretório temporário **novo a cada execução** — e o
`api_config.json` com as chaves de API, que fica ao lado do executável, se
perderia toda vez. O racional completo está no cabeçalho do `SIG-FT.spec`.

---

## O ícone antigo continua aparecendo depois de atualizar

É **cache do Windows**, não defeito do build. Ele guarda o ícone por caminho de
arquivo, e a atualização grava o `.exe` novo no mesmo caminho de sempre
(`...\SIG-FT Itaipu\SIG-FT.exe`) — então o desenho velho pode ficar na barra de
tarefas e no atalho mesmo com o `.exe` já trocado.

Aconteceu de verdade na troca de ícone de 2026-09-22, e custou uma rodada de
diagnóstico.

**Como separar cache de defeito, em 5 segundos:** olhe o ícone do instalador
que você acabou de baixar (`SIG-FT_Itaipu_Setup_*.exe`, na pasta Downloads).
Esse arquivo tem nome e caminho novos, então não existe cache possível para
ele. Se ele mostra o ícone certo, o pacote está bom e o resto é cache.

**Como limpar:** reiniciar o Explorer (Gerenciador de Tarefas → Windows Explorer
→ Reiniciar) ou rodar `ie4uinit.exe -show`. Sair e entrar na sessão também
resolve.
