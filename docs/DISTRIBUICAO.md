# Levar o SIG-FT para uma máquina da GE Vernova

O esquema é o mesmo que o **DocManager Itaipu** já usa: o app compilado vive
num ZIP no Box, e um `.bat` cuida de baixar, atualizar e abrir. Quem usa o
aplicativo não compila nada, não instala Python e não precisa de permissão de
administrador.

---

## Os dois arquivos que ficam no Box

Em `%USERPROFILE%\Box\SIG-FT Itaipu\`:

| Arquivo | O que é |
|---|---|
| `SIG-FT Itaipu.bat` | O que o usuário clica. Copie da raiz do repositório. |
| `SIG-FT.zip` | O app compilado. Gerado pelo `Gerar-Pacote.bat`. |

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
