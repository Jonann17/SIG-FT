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
| 3.3 | **3. Analyzer (IA)** | Ficha = `dados_de_teste\fichas\4500063671.0001.xlsx` | Roda a análise e devolve pontuação — **precisa de chave de IA** (configure na tela Home). Ver **3.3b** logo abaixo: o módulo mudou bastante em 2026-08-26 |
| 3.4 | **2. Planilhas PMIB** | Ver **3.4b** logo abaixo: mudou em 2026-09-24 | Gera as fichas pela planilha e regenera as pastas |
| 3.5 | **4.2. Tradutor** | Ver **3.5b** logo abaixo: mudou em 2026-09-25 | Traduz no próprio computador, em segundos por ficha |

> Se você **tem** uma ficha real à mão, use ela em vez da sintética no 3.3. As
> planilhas geradas seguem o que o *código* espera; uma ficha real é o único
> jeito de descobrir se o código espera a coisa certa.

**O que anotar:** qualquer erro de "coluna não encontrada", "cabeçalho não
localizado" ou código PMIB saindo diferente do esperado. Esses três são
justamente o que as Fases 1 e 2 unificaram.

---

### 3.3b — O que mudou no Analyzer em 2026-08-26

Sete defeitos corrigidos e quatro decisões suas. O que vale conferir na prática:

| # | O que fazer | Esperado |
|---|---|---|
| 1 | Abrir uma ficha no Excel, **selecionar outra aba** (se houver) e salvar. Analisar | A nota **não** pode mudar. O console diz `Lendo a aba 'X' (a aba ativa nao e a da ficha)`. Antes disso a mesma ficha ia de 100% para 0% |
| 2 | Analisar uma ficha **apagando o Fabricante** | `[REPROVADA] 1 campo(s) OBRIGATORIO(s)...` seguido de `· fabricante`, e o arquivo vai para `FT_bad` **mesmo com nota alta** |
| 3 | Analisar uma ficha **sem a seção de especificações técnicas** | Não recebe nota. Vai para a pasta nova **`FT_nao_concluidas/`**, com o original (sem `%` no nome) |
| 4 | Desligar a internet e analisar | Mesma pasta `FT_nao_concluidas/`, com o motivo da falha da IA no console |
| 5 | Responder **"Não aplicável"** em *Posições/Cuidados com içagem*, *Métodos de limpeza* ou *Ferramentas para preservação* | Aceito. Nos demais campos continua sendo tratado como falta |
| 6 | Terminado o lote, clicar em **GERAR RELATÓRIO PARA O FORNECEDOR (.xlsx)** | Arquivo na pasta de saída, uma linha por ficha com pendência: código PMIB completo, o que corrigir (com a justificativa da IA) e a nota |
| 7 | Analisar uma ficha cujo PMIB **não está** no `_STATUS_PMIB` | Abre uma caixa pedindo a descrição do material. **Cancelar** para de perguntar no resto do lote |

**Erros que valem anotar:**

| Se aparecer | Significa |
|---|---|
| `celula(s) com FORMULA sem valor calculado (L10)` | A ficha tem fórmula que o Excel nunca calculou. Abra no Excel e salve |
| Uma ficha em `FT_good` com campo obrigatório vazio | **Me avise** — é exatamente o que a regra nova existe para impedir |
| Relatório com nomes como `peso_liquido` em vez de `Peso líquido (kg)` | **Me avise**: o rótulo é o que torna o arquivo utilizável pelo fornecedor |

---

### 3.4b — Planilhas PMIB direto da planilha de PDMs (2026-09-24)

As fichas saem direto da planilha de PDMs que a Itaipu exporta (a
`PDMs_SAM-GM_<data>.xlsx`). Desde 2026-10-21 é o único caminho: a tela não tem
mais abas, nem as pastas "From Itaipu" e "PDMs Modificados".

| # | O que fazer | Esperado |
|---|---|---|
| 1 | Tela **2. Planilhas PMIB**, painel de cima: **Planilha de PDMs (SAM-GM)** → escolher a exportação da Itaipu | O nome do arquivo aparece ao lado do botão. Logo abaixo, sem abas, a **Configuração das Fichas PMIB** |
| 2 | Um `_STATUS_PMIB` real, o template PT, idioma Português. **Executar: Criar Fichas PMIB** | O log traz `Planilha de PDMs: <arquivo>, exportada em <data>: <n> PDM(s).` e cada ficha diz `(PDM.xxxx.xxx R<n>, <k> perguntas)` |
| 3 | Abrir uma ficha gerada no passo 2 | A partir da linha 79, as perguntas na ordem do PDM (a da coluna SECUENCIA da planilha) e **nenhuma com "(nan)"**. Pergunta sem texto de ajuda sai como `3 - PESO:` |
| 4 | Olhar o fim do log do passo 2 | Se algum PDM do STATUS estiver numa revisão diferente da planilha, aparece a lista `PDM precisa subir de revisao no portal (n):` (ou `Planilha atras do portal, exporte uma nova da Itaipu (n):`). A ficha sai mesmo assim, com a revisão da planilha |
| 5 | Idioma **English**, o template em inglês | Ver a etapa 3c: as perguntas saem traduzidas da planilha |

**Erros que valem anotar:**

| Se aparecer | Significa |
|---|---|
| `... aparece na planilha com mais de um nome base ...` | A exportação traz dois PDMs com o mesmo código (na de 23/09/2026: `PDM.3010.007` e `PDM.5945.026`). A ficha não sai, para não misturar os dois. É esperado; vale levar à Itaipu |
| `... nao esta na planilha de PDMs ...` | O PDM do STATUS não existe na exportação. Confira o código; se estiver certo, a planilha está velha |
| Uma ficha com pergunta `(nan)` ou fora da ordem do PDM | **Me avise**: é exatamente o que a fonte nova existe para impedir |
| A regeneração demorando vários minutos | **Me avise** com o tempo que levou: no ambiente de desenvolvimento, as duas pastas (1.199 PDMs cada) levaram 45 s |

---

### 3.5b — Tradutor Técnico 4.2: tradução local (2026-09-25)

A tradução PT -> ES das respostas deixou de usar o Google Tradutor: roda num
modelo que vem dentro do instalador, sem internet. Precisa do Excel instalado,
como antes. Use fichas REAIS já respondidas (de preferência de PDMs
diferentes); uma cópia, não o original.

| # | O que fazer | Esperado |
|---|---|---|
| 1 | Tela **4.2. Tradutor**, **Selecionar Arquivos e Iniciar** com 3 a 5 fichas | O log começa com `Tradução local de N ficha(s): nada sai deste computador.` e termina com `Tradução concluída: N de N ficha(s) em X s`. **Anote o X**: antes eram ~80 s por ficha |
| 2 | Abrir uma ficha traduzida, aba **Especificações técnicas copiar** | Mesmas 3 colunas de antes. Número sem `.0` (`220`, não `220.0`). Nenhuma resposta em português na coluna do espanhol |
| 3 | Conferir 10 respostas de texto da coluna do espanhol | Vocabulário técnico certo: `cojinete` (mancal), `tuerca` (porca), `arandela` (arruela), `empaquetadura` (gaxeta). Anote as que estiverem erradas |
| 4 | Linhas `[CONFERIR]` no log | Cada uma diz a pergunta e o motivo. Confira essas respostas na aba |
| 5 | **Abrir glossário**, acrescentar uma linha `termo errado = termo certo` para algo que o tradutor errou no passo 3, salvar, e traduzir a mesma ficha de novo | A resposta sai com o termo que você escreveu |
| 6 | Traduzir a ficha e, **no meio do lote**, clicar **PARAR AGORA** | Para na ficha seguinte. No Gerenciador de Tarefas, **nenhum `EXCEL.EXE` sobrando** (antes ficava um por ficha) |
| 7 | Uma ficha com característica cujo nome tem parênteses (`FAIXA DE TENSAO DE ALIMENTACAO (CA)`) | Na coluna Pergunta, o nome sai **com** o `(CA)` |
| 8 | Rodar o **4.3. Upload de características** numa ficha traduzida aqui | Funciona como antes: o 4.3 lê a mesma aba |

**Erros que valem anotar:**

| Se aparecer | Significa |
|---|---|
| `Nao achei o modelo do tradutor local` | O instalador saiu sem o modelo. **Me avise**: a conferência do Release deveria ter barrado |
| `esta ficha e a versao em ingles` | A ficha está em inglês; o tradutor traduz respostas em português. É esperado |
| Tradução claramente errada de um termo que se repete | Vale uma linha no glossário (passo 5), e **me mande o termo**: se for comum, ele entra no glossário que vem no programa |

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

> **Desde 2026-09-24 esta linha só aparece para documento acima de 300 mil caracteres.**
> O normal agora é `A IA vai ler N documento(s) no proprio PDF` ou `Documento(s) enviado(s)
> INTEIROS a IA como texto`. Ver **3b.3** abaixo.
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
3. **Algum campo que estava preenchido foi apagado?** Não pode acontecer. A única troca
   permitida é a do "não se aplica" (e afins) que o documento prova — ver 3b.4 —, e ela
   sempre deixa um comentário na célula com o que o fornecedor tinha escrito.
4. **Os dropdowns** (Origem, Tipo, Unidade) ficaram com opção válida?

### 3b.3 — Leitura integral e prova por valor (2026-09-24)

Depois da comparação com o AMP (fichas 0084, 0086, 0088, 0094), a IA passou a receber o
documento INTEIRO — com Gemini, o próprio PDF — e a devolver, para cada valor, o trecho do
documento de onde ele saiu. **O teste de aceite é rodar de novo essas quatro fichas e refazer
a comparação com o AMP.** O que olhar:

| Linha no console | Significa |
|---|---|
| `A IA vai ler N documento(s) no proprio PDF (...)` | o modelo recebeu os arquivos: vê desenho, tabela e gráfico |
| `Documento(s) enviado(s) INTEIROS a IA como texto` | o modelo não lê PDF (ou o arquivo passou de 15 MB): foi o texto, sem corte |
| `O provedor recusou o(s) PDF(s) anexado(s) ... Refazendo ... com o texto` | **anote o erro**: a ficha saiu, mas pelo texto |
| `N campo(s) preenchidos por DEDUCAO TECNICA` + `porque: ...` | material, norma, uso, tipo: não estão escritos no documento. **Confira cada um** |
| `N campo(s) lidos pela IA em pagina SEM TEXTO` | PDF escaneado: a prova não tem como ser conferida no texto |
| `a IA DEDUZIU um valor com numero` | número deduzido não entra — é de propósito |
| `o trecho citado pela IA (...) nao esta no documento lido` | possível invenção barrada |
| `❌ ... a IA nao respondeu (...)` | falha de verdade: a ficha não gerou `_completed`; rode de novo |

Na ficha `.xlsx`: as células preenchidas por **dedução** ou lidas de **página-imagem** têm um
**comentário** (triângulo vermelho no canto) assinado "AutoSpec", com a justificativa.

### 3b.4 — A conferência das respostas do fornecedor (2026-09-28)

A IA passou a conferir o que o **fornecedor** escreveu na tabela de especificações contra o
datasheet. Monte uma ficha de teste a partir de uma já preenchida pelo fornecedor, com o
datasheet anexado, e garanta nela:

- uma resposta **"Não se aplica"** (ou N/A, "não informado", "-") numa característica que
  **está** no datasheet;
- uma resposta **"Não se aplica"** numa característica que o datasheet **não** traz;
- uma resposta com **valor diferente** do datasheet (ex.: `IP54` onde o documento diz `IP65`);
- uma resposta **igual** ao datasheet, escrita de outro jeito (ex.: `24 Vcc` × `24 VDC`).

| # | O que fazer | Esperado |
|---|---|---|
| 1 | Rodar a ficha com a caixa **"Conferir as respostas do fornecedor contra o datasheet"** marcada | No console: `Conferindo N resposta(s) do fornecedor...` |
| 2 | Ler o console | `... ESTAO no documento: gravei o valor do documento` listando o 1º caso; `divergencia(s) ... NADA foi alterado na ficha` listando o 3º, com o trecho; o 2º e o 4º só entram nas contagens |
| 3 | Abrir o `_completed` | 1º caso: o valor do documento **em azul**, com comentário "AutoSpec: o fornecedor respondeu 'Não se aplica'..." ; 2º, 3º e 4º casos: **exatamente** o que o fornecedor escreveu |
| 4 | Rodar de novo a mesma ficha | `Conferencia do fornecedor reaproveitada do cache: nenhum token gasto` |
| 5 | Desmarcar a caixa e rodar uma ficha sem campo vazio | `Ficha já está completa.`, como antes |
| 6 | Painel **Gastos de IA** | quanto a conferência custou (entra como tarefa "autospec") |

**Erros que valem anotar:** um valor do fornecedor (não "não se aplica") alterado na ficha —
**me avise na hora**, é justamente o que não pode acontecer; uma divergência que é só unidade
ou tradução (`Aço inox` × `Stainless steel`); e a linha
`A conferencia das respostas do fornecedor falhou (...)`, com o erro.

### 3b.2 — A conferência de documentos, e o `.txt` que a salva

A seção **5. Conferência de documentos** lista os links que citam o fabricante
**ou** o código, mas não os dois. O programa não tem como decidir: pode ser o
datasheet certo num distribuidor, pode ser outro produto. Quem decide é você,
abrindo o link.

**O que testar** (é o que mudou em 2026-08-17, depois do seu relato de que
fechar o app perdia a conferência):

| # | O que fazer | Esperado |
|---|---|---|
| 1 | Terminar um lote que gere duvidosos | No console: `Conferencia salva em: ...\CONFERENCIA_AUTOSPEC_<data>_<hora>.txt` — **ele salva sozinho**, sem você clicar |
| 2 | Abrir esse `.txt` (fica na pasta do `_STATUS_PMIB`) | Cabeçalho explicando o uso, e um bloco por ficha com `FICHA:`, `MATERIAL:` e os links em `[ ]` |
| 3 | Marcar alguns com `[x]` no Bloco de Notas e salvar | — |
| 4 | **Fechar o aplicativo inteiro** e abrir de novo | A seção 5 aparece vazia, dizendo para importar |
| 5 | Seção 1 → escolher o `_STATUS_PMIB`; seção 5 → **IMPORTAR CONFERÊNCIA (.txt)** | Os links voltam **já com as suas marcações** |
| 6 | **PROCESSAR OS DOCUMENTOS MARCADOS** | Só os marcados são baixados; a ficha é preenchida e salva |

**Erros que valem anotar:**

| Se aparecer | Significa |
|---|---|
| `AVISO: nao encontrei a ficha ...` | O `.txt` é de outra máquina, ou a planilha mudou de pasta |
| `Selecione o arquivo _STATUS_PMIB (seção 1)` ao processar | Esperado depois de reabrir o app — o `.txt` traz os links, não a planilha de status |
| Marcações voltando **desmarcadas** na importação | **Me avise**: é o bug que este recurso existe para não ter |
| Um `.txt` sobrescrevendo o anterior | **Me avise**: o nome leva data e hora justamente para não acontecer |

---

### 3c — A ficha em INGLÊS (10 min, sem portal)

**Por que esta etapa existe.** É a única parte da frente da ficha em inglês que
o contêiner do Claude na web **não consegue rodar**: ele não tem
`deep_translator` nem chave de IA. Tudo o mais foi verificado ponta a ponta
contra o template real (`Technical_Sheet_of_PDM-R3.xlsx`) — geometria, mesclas,
célula, glossário, cache. **O que falta é julgar a qualidade da tradução**, e
isso só quem conhece o vocabulário da casa julga.

**Passos**

1. Tela **2. Planilhas PMIB**: a planilha de PDMs no painel de cima, um
   `_STATUS_PMIB` com 2 ou 3 materiais, a pasta de destino e o **template em
   inglês**. Idioma da ficha: **English**. **Executar: Criar Fichas PMIB**.
2. No log: `Traduzindo as perguntas para ingles (glossario e cache em ...)`,
   com a pasta `Documentos\SIG-FT\traducao_pdm`. Se o tradutor falhar, a
   linha `AVISO: o tradutor falhou ...` diz por quê, e cada ficha com pergunta
   em português ganha o aviso `N pergunta(s) sem traducao`. O lote não para.
3. Abra `_GLOSSARIO_PT_EN.txt` nessa pasta. Ele já vem com os termos tirados
   das suas próprias fichas (`NORMAS TECNICAS APLICAVEIS =
   APPLICABLE TECHNICAL STANDARDS` e mais 6).
4. Abra 2 ou 3 das fichas geradas e **leia as perguntas**. É aqui que você é
   insubstituível.
5. Achou tradução ruim? Ponha a **pergunta inteira** no glossário (sem o
   número e sem os dois pontos), apague o `_CACHE_TRADUCAO.json` e gere de
   novo. A sua linha vence o tradutor, hoje e sempre.

**O que conferir na ficha gerada**

| Onde | O que tem de estar |
|---|---|
| **C79** | a primeira pergunta, em inglês |
| A instrução entre parênteses | **em inglês também**. Se vier em português, é o defeito que mais me preocupa: a ficha sai metade em cada idioma e não se denuncia sozinha |
| Coluna **M** | vazia — é onde o fornecedor responde |
| Numeração `1 - `, `2 - ` | intacta e na ordem |
| O resto do template | cabeçalho, armazenagem, transporte: tudo em inglês, como no template |

**Me avise se:**

- alguma pergunta vier com a instrução em português;
- o número da pergunta aparecer traduzido ou fora de ordem (`1 - ` virou
  `1 -`, ou sumiu);
- uma unidade mudar (`(V)`, `(A)`, `(°C)`, `4-20mA` têm de passar intactas);
- uma norma mudar (`ABNT NBR IEC 60749-1` não se traduz);
- a segunda rodada demorar igual à primeira — o cache não estaria pegando.

> **A aba da ficha gerada já sai como `Standard Technical Sheet`** quando o
> idioma é inglês, mesmo o template trazendo o nome em português — era o passo
> que você fazia à mão, ficha a ficha. Em português, nada muda. Confira numa
> ficha gerada: se a aba vier `Ficha Técnica Padrão` com o idioma em English,
> **me avise**.

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

**Dois cliques em `SIG-FT.bat`** — o de sempre. Desde 2026-08-11 o Playwright
é o **padrão** dos módulos portados; não há atalho especial a usar. A janela
preta confirma, logo na abertura, qual motor cada módulo está usando:

```
[SIG-FT] Motor de automacao do portal:
[SIG-FT]    playwright: apagar_lmr, cria_fichas, lmr, tech_specs, upload_conditions
[SIG-FT]    selenium: ficha_duplicada (modulo antigo -- ignora esta configuracao)
```

> **Caminho de volta:** `SIG-FT-Motor-Antigo.bat`, que força tudo em Selenium.
> Nada fica gravado — fechou, acabou.

> O antigo `SIG-FT-Playwright.bat` **foi removido**: depois que o Playwright
> virou padrão, ele abria exatamente o mesmo aplicativo que o `SIG-FT.bat`.
> Parecia uma escolha e não era.

⚠️ **Não use `set SIGFT_RPA_ENGINE=...` no PowerShell.** No **Prompt de
Comando (cmd)** funciona; no **PowerShell** — o terminal que o Windows abre por
padrão hoje — `set` é outro comando (`Set-Variable`) e **não define variável de
ambiente**. O app abre no motor errado, sem nenhum aviso, e o teste inteiro
mede a coisa errada. Aconteceu na validação de 2026-08-11. Se ainda assim
quiser fazer pela linha de comando no PowerShell:

```powershell
$env:SIGFT_RPA_ENGINE = "selenium"
.\SIG-FT.bat
```

(o `.\` é obrigatório: o PowerShell não roda arquivo da pasta atual sem ele —
foi o segundo erro daquela sessão.)

**Como confirmar que está mesmo no motor novo**, sem depender da janela preta:
a primeira execução de qualquer módulo de RPA abre um navegador que **pede
login** e, a partir da segunda, **não pede mais** (o Playwright usa perfil
persistente; o Selenium não). Se o login for pedido toda vez, você está no
motor antigo.

Repita **as mesmas 5 tarefas da Etapa 4**, na mesma ordem. O que comparar:

- o **resultado** tem que ser o mesmo (mesmos campos preenchidos, mesmo resumo);
- a **velocidade** deve ser igual ou melhor — o motor novo espera de forma
  inteligente em vez de dormir um tempo fixo;
- na **segunda** execução, o login deve ser dispensado: o motor novo guarda a
  sessão num perfil persistente. Esse é um ganho concreto, vale confirmar.

Se algum módulo se comportar mal no motor novo mas tiver funcionado na Etapa 4,
**é do motor** — e é uma informação ótima, porque o rollback é imediato: feche o
Prompt e siga trabalhando no Selenium.

### 5.4 — O SIG-FT lendo as respostas do portal (2026-10-14)

Duas melhorias leem a resposta que o navegador recebe enquanto o robô clica
(continua sendo RPA). Os testes rodam contra um portal de mentira, escrito a
partir do código das telas: **a prova é esta etapa**.

**Conferir autorizações no portal** (Gestão PMIB → CONFERIR NO PORTAL):

1. Pasta Raiz = a dos `_STATUS_PMIB`; clique em CONFERIR NO PORTAL e faça o
   login quando a janela pedir.
2. O log deve passar por "Abrindo a lista de fichas do portal...", "Etapa 1 de
   2" e "Etapa 2 de 2". Um `[ERRO]` logo depois de abrir a lista quer dizer que
   ela não respondeu (login, ou o endereço mudou).
3. **Prova de aceite:** os PMIBs do último `sobressalentes_autorizados_*.xlsx`
   que ainda não estavam AUTORIZADO precisam sair como "código SAP de
   recebimento ... -> AUTORIZADO", com o mesmo código do arquivo.
4. Muitas "não encontrada(s) no portal" seguidas de fichas que existem: a
   pesquisa pode não estar recarregando as sete abas — mande o log.

**Aplicação LMR:** rode uma ficha de teste com 2 ou 3 códigos. O log de cada
código deve dizer "Portal confirmou: aplicação LMR gravada (id ...)". Se
aparecer "[!] Não vi a resposta do portal", o resto do lote voltou ao modo de
antes — mande o log. Anote o tempo da ficha para comparar com uma rodada antiga.

---

## Etapa 5b — Aconex ao vivo e Conferência de Revisões (2026-10-26, sem portal)

A partir da **1.3.1-rc.1**; desde a **1.3.1-rc.2**, a Conferência é a aba **Conferência de Revisões**
do PMIB Manager (na rc.1 era o item 10 do menu). É a validação na GE do desenho
`docs/superpowers/specs/2026-10-26-aconex-ao-vivo-design.md` (portões G1 e G2,
§10), e o que ela responder decide a Tarefa 11 do plano (ver
`docs/ACONEX_AO_VIVO.md`). Nada aqui toca o portal.

**Antes de começar:**

- o SIG-FT 1.3.1-rc.1 instalado (caixa "Versões de teste" marcada, ou o
  instalador do Release, à mão);
- o **DocManager com o seu perfil do Aconex cadastrado nesta conta do
  Windows**: o SIG-FT lê o mesmo `Documentos\DocManager_Itaipu\credenciais.json`;
- a planilha de mapeamento e a pasta raiz dos `_STATUS_PMIB`, as mesmas do
  Gestão PMIB.

**5b.1 — Testar conexão (G1).** Abra o **PMIB Manager**, aba **Conferência de Revisões**. A mapeadora
e a pasta raiz já vêm as do Gestão PMIB. Clique em **"Testar conexão com o
Aconex"**. O console escreve 7 linhas, `OK` ou `FALHOU`:

| Sonda | O que prova |
|---|---|
| Login no Aconex | o perfil do DocManager funciona nesta máquina |
| Register inteiro (busca vazia) | quantos documentos o projeto tem: é a referência das outras |
| Busca exata do código, com histórico | a busca que o download usa |
| Busca pelo Tracking ID (duas sintaxes) | se dá para seguir uma lista renomeada sem baixar o histórico inteiro |
| Busca por título | se dá para achar as listas de sobressalentes no servidor (`title:SOBRESSALENTES`) |
| Listas novas | das que vieram pelo título, quantas têm PB020 no código e não são de preços (conferido no SIG-FT: o Aconex devolve HTTP 500 ao coringa no código) |

Uma sintaxe que o Aconex ignora devolve o register inteiro e aparece como
`FALHOU ... a sintaxe não filtrou`. **Copie as 7 linhas e mande**: elas decidem
a Tarefa 11.

**5b.2 — Gestão PMIB com o STATUS REAL.** Numa **cópia** da mapeadora, rode o
Gestão PMIB com o extrato do dia, como sempre.

1. O log deve trazer linhas "STATUS REAL de <código>: <antes> → <depois>".
2. Escolha 3 listas (uma Aprovado, uma Para Assinatura e uma Em Processo) e
   confira o STATUS REAL contra o status real que o DocManager mostra.
3. Lista nova: só aparece a com PB020 no código; planilha de comissionamento
   com "sobressalentes" no título não aparece.
4. Power BI: atualize e confira "Listas Aprovadas" antes e depois (na base de
   26/10: 93 listas, 67 aprovadas, 25 aprovadas sem fichas).

**5b.3 — Conferência no Box de verdade.** Clique em **"Conferir revisões"**.

1. Os totais por categoria batem com a mapeadora (na leitura de 26/10: 4
   aprovadas e 1 não aprovada com divergência, 42 em dia, 48 sem
   `_STATUS_PMIB`; os números mudam com a mapeadora).
2. Os PDFs vão para a pasta do `_STATUS_PMIB` de cada lista, com o nome
   `<código>[<revisão>].pdf`.
3. **Rode de novo**: a segunda rodada não baixa nada (tudo "já existia").

**5b.4 — Sem cofre.** Numa conta do Windows sem o DocManager: "Conferir
revisões" mostra as listas e avisa "Sem conexão com o Aconex: as listas
aparecem, mas nada foi baixado."

O "Gestão PMIB ao vivo" (sem o extrato) chega com a Tarefa 11 e ganha os
passos dele aqui.

---

## Etapa 5c — Revisão das listas no AMP (2026-10-27, sem portal)

A partir da **1.3.1-rc.2**. É a validação na GE da peça 2
(`docs/superpowers/specs/2026-10-27-amp-revisao-de-listas-design.md`, §9). O AMP só
existe dentro da rede da GE: estes passos são no PC da GE. Nenhum arquivo é alterado:
o resultado é um HTML novo na pasta de cada lista.

**Antes de começar:**

- o SIG-FT 1.3.1-rc.2 instalado;
- o workflow `amp/revisao_de_listas/workflow_revisao_de_listas.json` importado e
  **publicado** no n8n do AMP, com a credencial e o modelo ligados (passo a passo em
  `amp/revisao_de_listas/LEIA-ME.md`);
- em Configuração → Chaves de API: **AMP Webhook (URL)** com a *Production URL* do
  webhook e **AMP Webhook (chave)** com o mesmo valor da credencial `X-SIGFT-Chave`;
- a 5b.3 feita **nesta sessão do SIG-FT**: a Revisão no AMP parte da última conferência.

**5c.1 — Testar conexão.** PMIB Manager → aba **Revisão no AMP** → **"Testar conexão com
o AMP"**. O console escreve duas linhas:

| Linha | O que prova |
|---|---|
| `OK      Ping: workflow 2026-10-27 ...` | a rede, a chave e o workflow publicado |
| `OK      Eco: os N códigos voltaram iguais` | o AMP não mascara os códigos das listas nem os CÓDIGOS DO MATERIAL |

`HTTP 401/403` é chave diferente da credencial; `HTTP 404`, workflow não publicado ou
a URL de teste no lugar da *Production URL*. **`FALHOU  Eco: ... (mascarado pelo AMP?)`:
pare aqui e mande as duas linhas**: com código mascarado, a tabela remontada não serve.

**5c.2 — Uma lista.** Clique em **"Revisar no AMP"**. A rodada manda as listas da
conferência uma por vez (até 15 minutos cada); para o primeiro teste, clique em
**"Parar"** logo que a primeira lista for ao AMP: as outras ficam "parado".

1. A coluna **AMP** da lista vira "HTML pronto: ...", e o arquivo
   `<código>[<em uso>-<atual>] revisao AMP.html` aparece na pasta do `_STATUS_PMIB`.
   Dois cliques na linha abrem o HTML.
2. O HTML traz o resumo, o que mudou (com a página e o item de origem), as
   divergências e o `_STATUS_PMIB` inteiro remontado.
3. Anote o tempo: o console diz os segundos da lista.

**5c.3 — Conferir o HTML.** Com os dois PDFs e o `_STATUS_PMIB` abertos, confira 5
itens do "que mudou" contra as páginas citadas. Copie a tabela remontada e cole numa
**cópia** do `_STATUS_PMIB` (nunca no original nesta fase): as colunas caem no lugar?

**5c.4 — Se falhar.** A coluna AMP diz "falhou: ..." e o botão **"Copiar
diagnóstico"** liga. Copie, abra uma conversa nova com o Claude (com o repositório
luanccozer/SIG-FT) e cole: o texto traz os números do pedido, a resposta do n8n, o
número da execução e onde está o código, sem texto de documento e sem a chave. O
mesmo texto fica em `Documentos\SIG-FT\logs\amp\`, e a tabela de sintomas está no
`amp/revisao_de_listas/LEIA-ME.md`. Com o número da execução, o n8n mostra (menu
*Executions*) em que nó parou.

---

## Etapa 5d — Atualização automática (2026-10-27, sem portal)

A partir da **1.3.1-rc.6**, com a caixa **"Versões de teste"** marcada. Só no
Windows. O caminho de cada atualização fica no `Documentos\SIG-FT\logs\diario.log`,
na linha `ATUALIZACAO` (por arquivos ou pelo instalador completo), e
os detalhes no `sigft.log` (linhas `[atualizacao]`).

**5d.1 — Por arquivos (rc instalada só para você).** Com uma rc instalada em
`AppData\Local\Programs\SIG-FT Itaipu`, atualize para a rc seguinte. A janela diz
"Aplicando a atualização…", o SIG-FT fecha e abre sozinho, sem instalador e sem
pedido de permissão. Confira: a versão nova na Home, a linha
`ATUALIZACAO por arquivos v<de> -> v<para>` no diário, e em Configurações >
Aplicativos o SIG-FT Itaipu com a versão nova.

**5d.2 — Program Files: a migração.** Numa máquina com o SIG-FT instalado
**para todos** (Program Files):

1. Atualize pelo app. Vem o **instalador completo** (desde a 1.3.2 não há mais
   o instalador pequeno): ele instala a cópia só sua e pede a senha de
   administrador uma vez, para remover a de Program Files. Confira: a pasta de
   Program Files sumiu, o SIG-FT abre de `AppData\Local\Programs`, e
   Documentos\SIG-FT (chaves, preferências) continua igual. Recusando a senha:
   a cópia nova funciona, e a caixa (só no instalador aberto à mão) diz como
   remover a antiga.
2. **Fixe de novo o atalho na barra de tarefas**: o fixado apontava para Program
   Files e deixa de abrir. Desafixe o velho e fixe o SIG-FT aberto.

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
  3.4 Planilhas PMIB (planilha e pasta) .. [ OK / não testei / falhou: ______ ]
  3.4b Regenerar as pastas ............... [ OK / não testei / falhou: ______ ]

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

ETAPA 5b — Aconex ao vivo e Conferência de Revisões
  5b.1 Testar conexão ..................... [ colei as 7 linhas / falhou: ______ ]
  5b.2 STATUS REAL igual ao do DocManager . [ ___ de 3 / falhou: ______ ]
       lista nova só com PB020? ........... [ sim / não: ______ ]
       Power BI igual antes e depois? ..... [ sim / não: ______ ]
  5b.3 Categorias conferem? ............... [ sim / não: ______ ]
       PDFs nas pastas certas? ............ [ sim / não: ______ ]
       2ª rodada não baixou nada? ......... [ sim / não ]
  5b.4 Sem cofre: avisou e não baixou? .... [ sim / não testei ]

ETAPA 5c — Revisão das listas no AMP
  5c.1 Ping .............................. [ OK / falhou: ______ ]
       Eco: códigos voltaram iguais? ..... [ sim / mascarado: ______ ]
  5c.2 HTML gravado na pasta? ............ [ sim / falhou: ______ ]
       tempo da lista .................... [ ____ s ]
  5c.3 5 itens conferem com os PDFs? ..... [ ___ de 5 ]
       tabela colou no lugar? ............ [ sim / não: ______ ]
  5c.4 Falhou? colei o diagnóstico ....... [ não falhou / colei na conversa ]
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
