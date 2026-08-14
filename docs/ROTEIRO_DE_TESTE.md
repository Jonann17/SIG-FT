# Roteiro de teste — Fases 1 a 5 da refatoração

Este roteiro existe porque **nada do que foi refatorado nas Fases 1 a 5 jamais
rodou contra o portal PMIB real**. Os testes automatizados (1559 em 2026-08-12)
provam que a lógica está coerente e que os dois motores de RPA fazem a mesma
sequência de ações — não provam que o portal responde bem a elas.

A **Etapa 3b** entra pelo mesmo motivo, para outra frente: o AutoSpec passou a
ler PDF na própria máquina e a recortar o contexto antes de mandar para a IA, e
nada disso rodou contra um PDF de verdade nem contra a internet de verdade.

Tempo estimado: **40 a 60 minutos** para o roteiro inteiro (75 com a Etapa 3b).
Dá para parar em qualquer etapa; cada uma tem valor sozinha.

> **Antes de tudo**: use uma **ficha de teste**, não uma ficha real de trabalho.
> Três módulos deste roteiro escrevem no portal e um APAGA dados. Se você não
> tem uma ficha descartável, crie uma na Etapa 6 (que é justamente o teste de
> criação) e use ela nas etapas seguintes.

---

## Como registrar o resultado

Copie a tabela do fim deste arquivo e vá preenchendo. O que mais ajuda quando
algo falha:

1. **a mensagem exata** do console (a janela preta) — copie o texto, não
   descreva;
2. **em que etapa** parou;
3. **qual motor** estava ativo (Selenium ou Playwright);
4. um **print da tela do portal** no momento do erro — o robô deixa a tela
   parada de propósito quando falha, justamente para isso.

---

## Etapa 0 — Pré-requisitos (5 min)

| | |
|---|---|
| **Python 3.10 ou mais novo** | [python.org/downloads](https://www.python.org/downloads/) — marque *"Add python.exe to PATH"* na primeira tela |
| **Acesso ao portal PMIB** | logar no `apps.itaipu.gov.br/PMIB` pelo navegador, normalmente |
| **Uma ficha de teste** | ver aviso acima |

Confira o Python abrindo o Prompt de Comando e digitando `py -V`. Se responder
com um número de versão, está pronto.

---

## Etapa 1 — Baixar o código (2 min)

**Atenção ao passo 2** — foi exatamente aqui que deu errado da última vez.

1. Abra: `https://github.com/luanccozer/sig-ft`
2. **Troque a branch** no seletor do canto superior esquerdo (o botão com o
   ícone de bifurcação) para:
   ```
   claude/checkpoint-01-refactor-executor-5lawtu
   ```
   Ou vá direto pelo link:
   `https://github.com/luanccozer/sig-ft/tree/claude/checkpoint-01-refactor-executor-5lawtu`
3. **Só depois de trocar a branch**, clique em **Code → Download ZIP**.
4. Extraia numa pasta **fora** do OneDrive/Box, por exemplo `C:\SIG-FT`.

**Como saber se pegou a branch certa:** a pasta extraída tem que conter os
arquivos `SIG-FT.bat`, `Testar-SIG-FT.bat` e `Instalar-Playwright.bat`. Se não
tiver, você baixou a branch antiga — volte ao passo 2.

---

## Etapa 2 — Instalação e suíte de testes (10 min, offline)

Dois cliques em **`Testar-SIG-FT.bat`**.

Na primeira vez ele cria o ambiente e baixa as dependências (alguns minutos, com
a janela preta mostrando o progresso). Depois roda os testes.

**Resultado esperado:**
```
1559 passed, 3 skipped
[SIG-FT] Tudo passou.
```

> O número cresce a cada checkpoint (era 1288 quando este roteiro foi escrito;
> são 1559 em 2026-08-12). **Ver um número maior é bom sinal, não erro** — o que
> importa é `[SIG-FT] Tudo passou.` e nenhum `failed`. Os `skipped` são testes
> que dependem de pacote que o ambiente não tem; podem variar.

| O que aconteceu | O que significa | O que fazer |
|---|---|---|
| `... passed` e nenhum `failed` | Instalação sã | Siga para a Etapa 3 |
| Alguns testes falharam | Bug real ou diferença de ambiente | Copie a saída inteira e me mande — **não siga adiante** |
| Erro `SSLError` / `CERTIFICATE_VERIFY_FAILED` durante a instalação | Zscaler bloqueando o `pip` | Ver **Etapa 2b** |
| `Python 3 nao foi encontrado` | Python ausente ou fora do PATH | Reinstale marcando *"Add python.exe to PATH"* |

### Etapa 2b — Se o Zscaler bloquear a instalação

1. Copie `pip_corporativo.txt.exemplo` para `pip_corporativo.txt` (mesma pasta).
2. Abra o novo arquivo e deixe **uma** linha não-comentada. Comece pela opção
   (b) do exemplo, apontando o certificado da empresa:
   ```
   --isolated --cert C:\certs\zscaler-root.pem --index-url https://pypi.org/simple
   ```
   Para exportar esse certificado: `certmgr.msc` → *Autoridades de Certificação
   Raiz Confiáveis* → ache o do Zscaler → exportar como **Base-64 (.cer)** →
   renomeie para `.pem`.
3. Rode o `.bat` de novo.

Se a TI mantiver um índice interno (Artifactory/Nexus), a opção (c) do arquivo
de exemplo é o caminho — peça a URL para eles.

---

## Etapa 3 — Módulos que só leem Excel (10 min, sem portal)

Estes não tocam o PMIB. Servem para confirmar que as Fases 1 a 4 (planilhas,
cabeçalhos, código PMIB, IA) não quebraram nada.

Dois cliques em **`Gerar-Dados-de-Teste.bat`** — ele cria a pasta
`dados_de_teste\` com planilhas sintéticas. Depois abra o app com
**`SIG-FT.bat`**.

| # | Tela | O que fazer | Esperado |
|---|---|---|---|
| 3.1 | **9. Search** | Pasta = `dados_de_teste`. Buscar por `Rolamento` | Encontra linhas nos dois `_STATUS_PMIB` |
| 3.2 | **8. PMIB Manager** | Apontar para `dados_de_teste` e listar/gerar KPIs | Lê os arquivos sem erro |
| 3.3 | **3. Analyzer (IA)** | Ficha = `dados_de_teste\fichas\4500063671.0001.xlsx` | Roda a análise e devolve pontuação — **precisa de chave Gemini** (configure na tela Home) |
| 3.4 | **2. Planilhas PMIB** | Um PDM qualquer seu, se tiver | Gera a planilha |

> Se você **tem** uma ficha real à mão, use ela em vez da sintética no 3.3. As
> planilhas geradas seguem o que o *código* espera; uma ficha real é o único
> jeito de descobrir se o código espera a coisa certa.

**O que anotar:** qualquer erro de "coluna não encontrada", "cabeçalho não
localizado" ou código PMIB saindo diferente do esperado. Esses três são
justamente o que as Fases 1 e 2 unificaram.

---

## Etapa 3b — AutoSpec AI (15 min, sem portal)

Etapa separada porque o AutoSpec **não é refatoração**: é a frente paralela do
Rafael (ver `docs/AUTOSPEC_MELHORIAS.md`). Ele lê a ficha, procura o que falta
em manuais e na web, pergunta para a IA e escreve de volta no `.xlsx`. Não toca
o portal — dá para rodar sem estar logado.

Entre 2026-08-11 e 12 o módulo mudou em três pontos que **nunca rodaram contra
um PDF de verdade nem contra a internet de verdade**, e é exatamente isso que
esta etapa existe para descobrir:

| Mudou | Antes | Agora |
|---|---|---|
| Leitura de PDF | subia o arquivo para a nuvem (LlamaParse) | lê **na sua máquina** (PyMuPDF); a nuvem virou último recurso |
| Prova de leitura | nenhuma — meia leitura passava por completa | informa quantas páginas de quantas foram lidas |
| Contexto para a IA | mandava o documento inteiro | manda só os trechos que respondem os campos |

### O que você precisa antes

| | |
|---|---|
| **Chave de IA** | configure na tela Home. O erro, se faltar, diz o nome do provedor e da chave — leia a mensagem, ela é literal |
| **Chave do Google Search + CSE ID** | opcional. Sem elas o módulo avisa e segue só com os documentos locais |
| **Um `_STATUS_PMIB.xlsx`** | serve o de `dados_de_teste\` |
| **Uma ficha com campos EM BRANCO** | se estiver toda preenchida não há o que a IA responder, e a etapa não testa nada |
| **Um manual em PDF** | o do fabricante do item da ficha. **É a parte mais importante desta etapa** |

### Os passos

1. Abra o app (`SIG-FT.bat`) e vá em **6. AutoSpec AI (RAG)** no menu da esquerda.
2. *1. Arquivo de Referência* → selecione o `_STATUS_PMIB.xlsx`.
3. *2. Adicionar Tarefa à Fila* → selecione a ficha, depois **Adic. Manuais
   (.pdf)** e escolha o manual.
4. **⬇ Adicionar à Fila ⬇** e então **INICIAR PROCESSAMENTO DA FILA**.
5. Acompanhe o **console dentro do app** (a caixa preta na parte de baixo da
   tela, não a janela do Windows).

### As 4 linhas que interessam no console

Estas quatro linhas são novas. Elas são o resultado do teste — mais do que o
"deu certo / deu errado".

**1. Leitura do PDF** — quantas páginas o computador conseguiu ler:
```
manual_hydac.pdf: 30 pagina(s), 30 lida(s) (100%), 11381 chars [PyMuPDF]
```
| Se aparecer | Significa | O que fazer |
|---|---|---|
| `(100%)` e `[PyMuPDF]` | Leu inteiro, **sem sair da sua máquina** | Perfeito, é o caso esperado |
| `LEITURA INCOMPLETA` + lista de páginas | O PDF tem páginas digitalizadas (foto de papel) | **Anote quantas** — é o número que decide se vale instalar OCR |
| `recorrendo ao LlamaParse (o arquivo SAI da rede)` | Nada local leu; o PDF foi para a nuvem | Anote **qual arquivo**. Era justamente o que se queria evitar |
| `precisa de OCR ... documento ignorado` | PDF só de imagem e sem chave LlamaParse | Anote o nome do arquivo |

**2. Busca na web** — qual pergunta rendeu documento:
```
Busca 3/7 rendeu 2 documento(s): "PVF100-4" HYDAC datasheet pdf
```
| Se aparecer | Significa | O que fazer |
|---|---|---|
| `rendeu N documento(s)` | Achou. **Anote o número da busca** (o `3/7`) | Se for sempre 4, 5 ou mais, as primeiras queries estão erradas e dá para consertar |
| `sem resultado util` em todas | Nenhuma query funcionou | Copie **as 7 linhas** e mande. É o dado que faltava para atacar a busca |
| `Busca em cache (nao gastou cota da CSE)` | Repetiu uma busca já feita | Normal, e é economia de cota |
| `Busca web desativada` | Faltou chave do Google/CSE | Só configure se quiser testar a busca |

**3. Recorte do contexto** — quanto foi economizado de token:
```
Contexto recortado: 5 de 12 trecho(s), 5955 de 11411 chars (48% a menos enviado a IA)
```
| Se aparecer | Significa |
|---|---|
| `N% a menos` | Funcionou — esse é o dinheiro economizado por ficha |
| `recortar nao economizaria` | Documento pequeno, mandado inteiro de propósito |
| `Nenhum trecho ... casou com os campos pedidos` | **Me avise.** Quer dizer que o vocabulário da sua ficha não está no glossário |

**4. Reforço semântico** — aparece uma vez só:
```
Reforco semantico INATIVO — retrieval rodando so com BM25 + glossario PT/EN
```
`INATIVO` é o **esperado** e não é defeito: é o caminho padrão, e ele é que foi
medido. Não instale nada para mudar isso.

### Depois que terminar

Abra a ficha `.xlsx` e confira, nessa ordem:

1. **Os campos preenchidos estão nas células certas?** É o único jeito de pegar
   valor escrito na linha errada.
2. **Os valores batem com o manual?** Pegue 3 ou 4 e confira no PDF. Valor
   plausível e errado é pior que campo vazio.
3. **Algum campo que estava preenchido foi apagado?** Não pode acontecer.
4. **Os dropdowns** (Origem, Tipo, Unidade) ficaram com opção válida?

---

## Etapa 4 — Portal, motor ATUAL (Selenium) — 15 min

**Esta é a etapa mais importante do roteiro**, e a ordem importa.

As Fases 1 a 4 mudaram muita coisa no código que fala com o portal — e nada
disso rodou lá ainda. Se você for direto para o Playwright e algo quebrar, não
dá para saber se o culpado é o motor novo ou a refatoração. Testando primeiro no
motor de sempre, isso fica separado.

Abra o app com **`SIG-FT.bat`** (sem definir variável nenhuma — o padrão já é
Selenium).

Ordem deliberada: começa pelo que só lê, termina pelo que apaga.

| # | Tela | O que fazer | Esperado | Risco |
|---|---|---|---|---|
| 4.1 | **4.3. Upload Specs** | Rodar sobre 1 ficha de teste, com 2–3 características | Preenche as características; o resumo no fim mostra sucessos/falhas | escreve |
| 4.2 | **4.1. Upload Condições** | Rodar sobre a mesma ficha | Preenche as 4 abas de condições | escreve |
| 4.3 | **7.1. LMR (Upload)** | Planilha de LMR com 2 códigos, sendo 1 com duas TAGs | Cadastra as aplicações; resumo no fim | escreve |
| 4.4 | **1. Cria Fichas PMIB** | Criar **1** ficha de teste | Devolve o código PMIB novo e o PDM final | **cria dado** |
| 4.5 | **7.2. Apagar LMR** | Sobre a ficha do 4.3 | Apaga todas as aplicações e diz "Todas as aplicações visíveis foram apagadas" | **apaga dado** |

### O que conferir com atenção especial

Estes são os pontos onde a migração pode ter mudado algo sutil — todos estão
registrados em `docs/refatoracao/PENDENCIAS.md`:

- **4.1 (Upload Specs)** — confira se **cada valor caiu na linha certa** da
  tabela de características. A migração trocou "o campo dentro deste elemento
  de linha" por "o campo dentro da linha número N". Se um valor aparecer na
  linha vizinha, é isso.
- **4.1** — se alguma característica numérica tiver **aspas ou barra** no valor
  (`5' 1/2"`, por exemplo), confira se entrou. Havia um bug aí que corrigi de
  passagem: o valor era injetado dentro de um script JavaScript e as aspas
  quebravam tudo em silêncio.
- **4.4 (Cria Fichas)** — este é o **mais frágil do sistema**. Confira campo por
  campo na ficha criada: Origem, Tipo, Unidade e Fabricação são alcançados
  *contando TABs*. Se um valor caiu no campo vizinho, é a diferença que
  registrei: o código antigo mandava as teclas para um elemento guardado, e
  agora manda para quem está com o foco.
- **4.4** — confira se o **código PMIB gravado na planilha** bate com o que
  apareceu na tela. A leitura mudou de "texto visível" para "conteúdo do
  elemento".
- **4.5 (Apagar LMR)** — se o laço não parar sozinho, **feche o app**. É o
  cenário de laço infinito que mais me preocupou; existe teste para ele, mas o
  teste usa um navegador falso.

---

## Etapa 5 — Portal, motor NOVO (Playwright) — 15 min

Só faça esta etapa **se a Etapa 4 passou**. Se algo falhou lá, o problema é da
refatoração e não do motor — me mande antes.

### 5.1 Instalar o navegador

Dois cliques em **`Instalar-Playwright.bat`** (uma vez só, ~150 MB).

Se falhar com erro de certificado, o download não passa pelo `pip` — quem baixa
é o processo Node do Playwright, que só respeita `NODE_EXTRA_CA_CERTS`:

```bat
setx NODE_EXTRA_CA_CERTS C:\certs\zscaler-root.pem
```
Feche e reabra o Prompt, e rode o `.bat` de novo.

Se a TI bloquear o download de vez, dá para usar um Chrome/Edge que já esteja
instalado:
```bat
setx SIGFT_PLAYWRIGHT_EXECUTABLE "C:\Program Files\Google\Chrome\Application\chrome.exe"
```

### 5.2 Conferir o motor sem o portal

Dois cliques em **`Smoke-Playwright.bat`**. Uma janela de navegador abre, faz
algumas coisas sozinha e fecha.

**Esperado:** `TUDO OK: 13 verificacoes.`

Isto responde *"o Playwright funciona nesta máquina?"* — separado de *"o portal
responde bem a ele?"*. Se falhar aqui, nem tente o portal: é ambiente/rede.

A última linha é uma checagem **opcional** de internet. Se ela disser que o
navegador não alcançou a internet, o smoke ainda conta como OK — mas o portal é
remoto, então anote: pode ser preciso configurar proxy para o Chromium.

### 5.3 Rodar os módulos no motor novo

Abra o **Prompt de Comando** na pasta do projeto e digite:

```bat
set SIGFT_RPA_ENGINE=playwright
SIG-FT.bat
```

> A variável vale só para essa janela. Fechou o Prompt, voltou ao Selenium.
> **É este o caminho de volta se algo der errado** — não precisa desfazer nada.

Repita **as mesmas 5 tarefas da Etapa 4**, na mesma ordem. O que comparar:

- o **resultado** tem que ser o mesmo (mesmos campos preenchidos, mesmo resumo);
- a **velocidade** deve ser igual ou melhor — o motor novo espera de forma
  inteligente em vez de dormir um tempo fixo;
- na **segunda** execução, o login deve ser dispensado: o motor novo guarda a
  sessão num perfil persistente. Esse é um ganho concreto, vale confirmar.

Se algum módulo se comportar mal no motor novo mas tiver funcionado na Etapa 4,
**é do motor** — e é uma informação ótima, porque o rollback é imediato: feche o
Prompt e siga trabalhando no Selenium.

---

## Etapa 6 — Me mandar o resultado

Copie e preencha:

```
ETAPA 0-1  Download e pré-requisitos ....... [ OK / falhou: ______ ]
ETAPA 2    Suíte de testes ................. [ ___ passed / falhou: ______ ]
ETAPA 2b   Precisou de ajuste de Zscaler? .. [ não / sim: ______ ]

ETAPA 3 — Excel (sem portal)
  3.1 Search .............................. [ OK / falhou: ______ ]
  3.2 PMIB Manager ........................ [ OK / falhou: ______ ]
  3.3 Analyzer ............................ [ OK / falhou: ______ ]
  3.4 Planilhas PMIB ...................... [ OK / não testei / falhou: ______ ]

ETAPA 3b — AutoSpec AI (sem portal)
  rodou até o fim? ........................ [ OK / falhou: ______ ]
  LEITURA DO PDF
    páginas lidas / total ................. [ ____ / ____  = ____% ]
    algum arquivo foi para o LlamaParse? .. [ não / sim: ______ ]
  BUSCA WEB
    qual busca rendeu documento? .......... [ ____ de ____ / nenhuma ]
    se nenhuma, colei as linhas abaixo ..... [ sim / não usei chave de busca ]
  RECORTE
    quanto economizou? .................... [ ____% / recorte dispensado ]
  FICHA DEPOIS DE PREENCHIDA
    valores nas células certas? ........... [ sim / não: ______ ]
    valores batem com o manual? ........... [ ___ de ___ conferidos ]
    apagou algum campo já preenchido? ..... [ não / SIM: ______ ]
    dropdowns com opção válida? ........... [ sim / não: ______ ]

ETAPA 4 — Portal, motor Selenium
  4.1 Upload Specs ........................ [ OK / falhou: ______ ]
      valores na linha certa? ............. [ sim / não ]
  4.2 Upload Condições .................... [ OK / falhou: ______ ]
  4.3 LMR (Upload) ........................ [ OK / falhou: ______ ]
  4.4 Cria Fichas ......................... [ OK / falhou: ______ ]
      Origem/Tipo/Unidade/Fabricação ok? .. [ sim / não: ______ ]
      código PMIB na planilha bate? ....... [ sim / não ]
  4.5 Apagar LMR .......................... [ OK / falhou: ______ ]
      parou sozinho? ...................... [ sim / não ]

ETAPA 5 — Portal, motor Playwright
  5.1 Instalar navegador .................. [ OK / falhou: ______ ]
  5.2 Smoke ............................... [ 13 OK / falhou: ______ ]
  5.3 Mesmas 5 tarefas .................... [ OK / falhou: ______ ]
      login foi dispensado na 2ª vez? ..... [ sim / não ]
      mais rápido, igual ou mais lento? ... [ ______ ]
```

---

## Se der errado no meio

Nada aqui é irreversível do lado do código: o motor antigo continua no
repositório e é o padrão. Em ordem de esforço:

1. **Um módulo se comportou mal no Playwright** → feche o Prompt de Comando. A
   variável some e tudo volta ao Selenium.
2. **Um módulo se comportou mal no Selenium também** → é da refatoração. Me
   mande a mensagem e a etapa; não tente contornar.
3. **Quer voltar ao app antigo por completo** → o código anterior à refatoração
   está na branch `claude/itaipu-delivery-refactor-vh0n67`, congelado. Baixe o
   ZIP dela como na Etapa 1.
