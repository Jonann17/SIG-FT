# Atualização automática só com o que mudou (instalador pequeno) e canal de testes

**Data:** 2026-10-07 · **Frente:** refatoração geral (Luan)
**Origem:** *"verifique a questão do autoupdate (está funcionando, mas sempre que precisa atualizar
está precisando instalar ele completamente do zero, quero tipo uma atualização apenas do que foi
modificado para ser mais rápido)"*

**Decisões do Luan (2026-10-07):**
- **instalador pequeno**: cada versão publica, além do instalador completo, um instalador de
  atualização só com os arquivos que mudaram; o app usa o pequeno quando ele serve para a versão
  instalada e, senão, o completo;
- **canal de testes** opcional, desligado por padrão, para o app dele receber pré-lançamentos e
  testar a atualização pequena antes de ela chegar a todo mundo.

---

## 1. O que acontece hoje

O app pergunta ao GitHub pelo último Release normal (`/releases/latest`), baixa o
`SIG-FT_Itaipu_Setup_X.exe` (316 MB na 1.1.1: lzma2 sólido do pacote inteiro, com o tradutor de
218 MB), confere o SHA256 e roda o instalador em `/SILENT`, que regrava a pasta inteira.

Entre duas versões, quase tudo é igual: Python, pandas, numpy, ctranslate2, o modelo do tradutor,
as DLLs. O que muda é o `SIG-FT.exe` (no onedir do PyInstaller, o código Python vai embutido nele)
e, às vezes, um ou outro arquivo de `_internal\`.

## 2. O desenho

### 2.1 No build (`release.yml` + `tools/gerar_atualizacao.py`)

1. Depois do PyInstaller, o **manifesto de arquivos** `arquivos.json`: cada arquivo da pasta
   instalada (`dist\SIG-FT\` + `CHANGELOG.md`), com SHA256 e tamanho. Vai para o Release.
2. O workflow baixa o `arquivos.json` dos **até 3 Releases mais recentes** que o publicaram
   (normais ou pré-lançamentos). Para cada um, a **diferença**: arquivos novos ou com hash
   diferente, e arquivos que sumiram.
3. Para cada diferença, um **instalador de atualização** pelo mesmo `installer/sigft.iss`, em modo
   atualização (`/DAtualizacao=1`): só os arquivos da diferença em `[Files]`, os que sumiram em
   `[InstallDelete]` (um por um, nunca a pasta `_internal` inteira como no completo), mesmo
   `AppId`, mesmo `CloseApplications=force`, mesmo `/REABRIR=1`. Sai como
   `SIG-FT_Itaipu_Atualizacao_<de>_para_<para>.bin`.
4. O `latest.json` ganha a lista `atualizacoes`: `de`, `arquivo`, `sha256`, `tamanho` de cada um.

Por que `.bin` e não `.exe`: o app 1.1.1 escolhe "o primeiro `.exe` do Release". Com dois `.exe`,
ele poderia baixar o pequeno, que não serve para ele. Com `.bin`, o 1.1.1 continua achando só o
completo. O app novo baixa o `.bin`, confere o SHA256 e o renomeia para `.exe` antes de rodar.

Por que reaproveitar o Inno e não um aplicador próprio: o instalador já resolve o que custou caro
acertar — fechar o app em uso, pedir administrador quando a instalação é para todos os usuários,
reabrir o app **na conta de quem estava usando** (`runasoriginaluser`), atualizar a versão em
Programas e Recursos e o registro do desinstalador. Um aplicador próprio teria de refazer tudo.

### 2.2 No app (`services/updater.py`)

- A `Atualizacao` passa a dizer **qual arquivo baixar**: o instalador pequeno quando o
  `latest.json` traz um `de` igual à versão instalada (e o arquivo está no Release); senão, o
  completo. A janela mostra o tamanho do que vai baixar ("12,3 MB: só o que mudou").
- O instalador pequeno confere, antes de copiar, que a versão instalada é a `de` dele (registro do
  desinstalador). Se não for, não copia nada e reabre o app; a próxima abertura oferece de novo, e
  aí o app escolhe pela versão real.
- Quem já está na 1.1.1 recebe a próxima versão ainda pelo instalador completo: quem escolhe o
  arquivo é o app instalado. A economia começa na versão seguinte à que trouxer isto.

### 2.3 Canal de testes

- Opção `atualizacao.canal_testes` nas preferências (desligada). Caixa **"Versões de teste"** ao
  lado do botão "Atualizações" da tela inicial.
- Ligada, o app procura em `/releases` (pré-lançamentos inclusive) e oferece o mais novo; desligada,
  `/releases/latest`, como hoje. A janela marca "(versão de teste)".

### 2.4 Como o Luan testa

1. Instala à mão a primeira rc com a novidade (completo) e liga "Versões de teste".
2. Sai a rc seguinte: o Release traz o instalador pequeno `de` a anterior. O aviso aparece com o
   tamanho pequeno; "Atualizar agora" troca só o que mudou e reabre o app na versão nova.

## 3. Fora do escopo

- Diferença binária dentro de um arquivo (bsdiff/xdelta): o `SIG-FT.exe` vai inteiro. Ganho
  pequeno perto do resto, e mais uma ferramenta no build e no app.
- Pular versões encadeando instaladores pequenos: com 3 versões de base, quem ficou mais para trás
  recebe o completo.

## 4. Como se prova

- `tests/test_gerar_atualizacao.py`: manifesto (hash e tamanho de cada arquivo, caminho com `\`),
  diferença (novo, mudado, sumido, igual), includes do Inno (escapes de aspas, `DestDir` certo,
  `dirifempty` das pastas que somem), escolha das bases e o `latest.json`.
- `tests/test_updater.py` (seção nova): escolhe o pequeno quando `de` bate, o completo quando não
  bate ou o arquivo falta, `.bin` vira `.exe` depois do SHA256, canal de testes consulta
  `/releases` e pega o mais novo.
- `tests/test_instalador.py` (seção nova): o `.iss` em modo atualização não apaga `_internal`,
  confere a versão `de`, mantém `CloseApplications` e o `/REABRIR`.
- O build de verdade é o Release no Windows: a rc com a novidade sai só com `arquivos.json` (não há
  base ainda); a seguinte já traz o instalador pequeno — e a prova final é o Luan atualizando por
  ele, com o canal de testes ligado.
