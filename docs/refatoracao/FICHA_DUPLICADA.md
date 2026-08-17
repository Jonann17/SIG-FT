# Ficha duplicada — especificação (Fase 6)

Levantada com o usuário em **2026-08-11**, com as telas do portal à vista.
Substitui o entendimento implícito no módulo antigo
(`sigft/services/ficha_duplicada.py`), que o diagnóstico do plano classifica
como *"frágil por concepção"* e que a Fase 6 reconstrói.

> **Como ler.** O que está em citação é palavra do usuário. O que está marcado
> como ⚠️ **leitura minha** é interpretação que ainda não foi confirmada — e
> que não deve virar comportamento automático antes de ser.

---

## 1. Objetivo

Uma ficha duplicada é uma ficha nova no PMIB que **repete o conteúdo de uma
ficha original já existente**, para um material que a Itaipu cadastra duas
vezes. O módulo preenche a ficha duplicada a partir da original, no portal.

---

## 2. Identificação — quais fichas são duplicadas

> *"A duplicidade é marcada pela coluna 'PDM usado', que às vezes pode ter
> alguma variação como 'PDMs usados'. Toda ficha que tiver o PDM como
> `PDM.9900.000 - FICHA PMIB, DUPLICADA, R0` significa que ela é uma
> duplicação. No caso, pra dar correspondência, seria bom apenas a primeira
> parte: `PDM.9900.000`."*

**Implementado** em `services/duplicadas_spec.py`:

- casamento por **prefixo** `PDM.9900.000`, ignorando caixa e espaço;
- o sufixo (`- FICHA PMIB, DUPLICADA, R0`) é **ignorado de propósito**: ele
  carrega revisão e descrição, que mudam sem aviso e por motivo alheio a esta
  decisão. Prender a identificação ao texto inteiro criaria um jeito de o
  módulo parar de achar fichas depois de uma revisão do PDM;
- a coluna é procurada por várias grafias (`PDM usado`, `PDMs usados`, …).

### Seleção pelo usuário

> *"Poderia aparecer a telinha de todos que achou e quais queremos selecionar
> para fazer os campos. E ter a opção de selecionar todos, semelhante ao que
> temos nos módulos de upload."*

→ Reaproveitar o diálogo de seleção que `ModuloLMR` já usa (lista com
checkbox + "selecionar todos"). **CP 6.2.**

---

## 3. Seções a replicar

### 3.1 Fabricantes e fornecedores

**Fabricante:**
1. ler o fabricante da ficha original;
2. abrir o dropdown (é um combo com busca — ver tela) e escolher **o mesmo**;
3. preencher a **Referência**, que vem do `_STATUS_PMIB`, coluna
   **`CÓDIGO DO MATERIAL`**.

**A regra do sufixo `'D` — a mais delicada do módulo:**

> *"Se aparecer 'a referência já existe', devemos colocar o partnumber dele
> `2904616` com o `'D1` no final, ficando `2904616'D1`; e se ainda não
> existir, deve colocar o `'D2`; e se não existir, colocar `D3`, assim por
> diante, até ele conseguir."*

Quem decide se parou é **o portal**, pela mensagem sob o campo
(*"A referência já existe!"*). O código não tem como saber de antemão qual
sufixo passa, então:

- `sequencia_de_referencias()` gera `2904616`, `2904616'D1`, `2904616'D2`…;
- o RPA consome uma a uma, **conferindo a tela entre elas**;
- `e_erro_de_referencia_repetida()` existe para **não** tratar qualquer erro
  como colisão — se o portal reclamar de outra coisa, tentar mais 20 sufixos
  esconde o erro de verdade e deixa lixo no campo;
- há **teto de 20 tentativas** (⚠️ **decisão minha**, não do usuário): sem
  teto, um portal que rejeite tudo faz o robô tentar para sempre;
- **esgotado o teto**: *"apenas notificar que não foi possível colocar a
  referência"* — não aborta a ficha nem desfaz o que já foi preenchido; vira
  pendência manual, como os campos rejeitados de `tech_specs`.

**Fornecedor:**

> *"No campo do fornecedor, GE ENERGIAS RENOVÁVEIS, como o fornecedor é a
> gente, que é sempre fixo (tipo intermediador), nós colocamos a informação
> que está no STATUS PMIB na coluna `CÓDIGO CMI` ou por vezes `CÓDIGO GE`. Se
> estiver vazio, só ignorar."*

- o fornecedor em si é **fixo** — não se escolhe;
- a referência vem de `CÓDIGO CMI` / `CÓDIGO GE`;
- **vazio ⇒ pular**, sem erro e sem pendência.

### 3.2 Características técnicas

> *"Vai haver 4 seções; devemos apagar 3 e deixar somente a da imagem anexa.
> Nesse campo devemos preencher o código da ficha original, o qual estamos nos
> baseando, que vem da coluna de OBSERVAÇÕES."*

- manter só **`3626 - CODIGO PMIB`**, apagar as outras 3;
- preencher com o código da ficha **original**, lido de `OBSERVAÇÕES`.

✅ **Confirmado:** *"Haverá sempre só um código nessa estrutura; às vezes pode
ter mais texto, mas haverá apenas um código se o PDM for o correto."*
`extrair_ficha_original()` procura o padrão `##########.####` em qualquer
posição do texto, que é exatamente esse caso.

### 3.3 Documentos e imagens

> *"Na parte da imagem, devemos copiar os dados da ficha original e colar as
> imagens. No documento, como já está criando um objeto dentro do portal pra
> ficha original, basta chamá-lo nesta ficha e associar: então clicar em
> associar os documentos e digitar exatamente o que foi anexado na ficha
> original."*

- **imagens** — mecanismo confirmado: *"clicar na figura, dar copiar na figura,
  ir na ficha que você quer, clicar em adicionar imagem e colar no campo que
  abre"*. Descrição (ES e PT): a **descrição do item**, do `_STATUS_PMIB`, a
  mesma nos dois idiomas.

  ⚠️ **Para o robô a recomendação é OUTRA, e o motivo é técnico.** Colar imagem
  da área de transferência num campo de upload é a operação menos confiável de
  automação de navegador — depende do sistema operacional, do foco da janela e
  de o navegador aceitar `paste` sintético. O diálogo "Adicionar Imagens" aceita
  **arquivo** (*"Arraste e solte arquivos aqui ou Adicione"*) e toda imagem no
  portal tem URL. Então: **baixar da original e subir na duplicada** — mesmo
  resultado, sem clipboard no caminho. Limite declarado pelo próprio diálogo:
  **10 arquivos por envio**;
- **documentos**: não se sobe arquivo. O documento **já existe** como objeto
  no portal; associa-se pelo diálogo *"Selecionar Documentos"*, buscando pela
  descrição exata da original. A busca é textual e o diálogo é paginado (809
  itens, 162 páginas na tela levantada) — a busca é obrigatória, paginar não
  é opção.

### 3.4 Condições

> *"Copiar todos os dados em todas as seções, com exceção da parte
> financeira."* + *"Condições financeira é uma seção interna dentro das
> condições."*

✅ **Desbloqueada.** A segunda frase mudou tudo: "Financeira" é uma **aba**, não
um conjunto de campos espalhados. A exclusão é nomeável e verificável — o robô
simplesmente não entra naquela aba, e não existe lista para levantar.

**As abas têm nomes e CONTAGEM diferentes nos dois modos**, e isso não é
detalhe de levantamento:

| Modo | Abas |
|---|---|
| **Edição** (5) | Condições de armazenamento · **Condições financeiras** · Condições de transporte e movimentação · Condições de manutenção · Condições de descarte |
| **Visualização** (3) | Armazenamento e transporte · **Financeira** · Manutenção e descarte |

O extrator lê do modo **visualização** (§3.5) e o injetor escreve no modo
**edição**, então os dois conjuntos existem no código. `e_aba_financeira()`
reconhece as duas grafias por substring (`financeir`), porque errar para o lado
de reconhecer é o lado seguro: um falso positivo deixa de copiar uma aba; um
falso negativo **copia dado financeiro** — e esse erro fica plausível na tela.

### 3.5 De onde se LÊ a ficha original — decisão de arquitetura

> *"A ficha original é sempre encontrável, mas pode variar dentro do portal se
> ela está em Elaboração, ou se está em Análise, ou demais campos."* +
> *"acho que é melhor sempre fazermos o webscraping de como abrimos a ficha no
> modo de visualização (pq nem sempre estará em Em Elaboração)."*

**É o que separa este módulo do `upload_conditions`.** Aquele lê e escreve na
ficha em **edição**, com `<input>`/`<textarea>`/`<select>`. A ficha original de
uma duplicação raramente está em elaboração — na tela levantada estava *"Em
Análise ITAIPU"* — e nesse estado o portal mostra os valores como **texto**.

Um extrator que procure `input[value]` **não acha nada e devolve ficha vazia,
sem erro**. Por isso `MODO_LEITURA_ORIGINAL = "visualizacao"` está no código,
com teste — é uma armadilha silenciosa e barata de cair.

A busca da original também **não pode assumir aba de status**: o portal separa
a lista em 7 (`Em Elaboração`, `Para enviar à ITAIPU`, `Em Análise ITAIPU`,
`Rejeitado pela ITAIPU`, `Aprovado parcialmente IB`, `Aprovado pela ITAIPU`,
`Cancelado`) e a original pode estar em qualquer uma.

---

## 4. Perguntas abertas

Nenhuma impede começar; todas impedem **rodar em lote sem conferir**.

**As 5 de 2026-08-11 foram respondidas** e estão incorporadas acima:

| # | Pergunta | Resposta |
|---|---|---|
| 1 | Quais campos são "a parte financeira"? | É uma **aba** — §3.4 |
| 2 | Como se copiam as imagens? | Copiar/colar a figura; para o robô, baixar+subir — §3.3 |
| 3 | `OBSERVAÇÕES` pode ter mais de um código? | *"Haverá sempre só um código nessa estrutura"* |
| 4 | Esgotadas as 20 tentativas? | *"Apenas notificar que não foi possível colocar a referência"* — não aborta |
| 5 | A original é sempre encontrável? | Sim, mas em **qualquer status** — §3.5 |

Ficam duas, agora técnicas e não de negócio:

1. **O `<input type=file>` do diálogo "Adicionar Imagens" é alcançável?** Se
   sim, o Playwright preenche direto com `set_input_files`, sem simular
   arraste. Se estiver escondido atrás de um componente próprio, o CP 6.4
   precisa de outra abordagem.
2. **Os seletores do combo de fabricante e do diálogo de documentos.** São os
   dois componentes com comportamento próprio (busca embutida, paginação de
   162 páginas). `playwright codegen` no fluxo real resolve em minutos e vale
   mais que qualquer descrição.

---

## 5. Estado da implementação

| Parte | Onde | Estado |
|---|---|---|
| Identificação por PDM + colunas | `services/duplicadas_spec.py` | ✅ CP 6.1, 58 testes |
| Sequência `'D` + detecção de colisão | `services/duplicadas_spec.py` | ✅ CP 6.1 |
| Código da ficha original | `services/duplicadas_spec.py` | ✅ CP 6.1 |
| Tela de seleção das fichas | `frontend.py` | ☐ CP 6.2 |
| Extração da ficha original | novo serviço | ☐ CP 6.2 |
| Injeção (fabricante, características) | novo serviço | ☐ CP 6.3 |
| Documentos e imagens | novo serviço | ☐ CP 6.4 |
| Abas de Condições (exclui a Financeira) | `services/duplicadas_spec.py` | ✅ CP 6.1 |
| Modo de leitura + abas de status | `services/duplicadas_spec.py` | ✅ CP 6.1 |
| Descrição/limite das imagens | `services/duplicadas_spec.py` | ✅ CP 6.1 |

O módulo antigo (`services/ficha_duplicada.py`) continua **intocado e
funcionando em Selenium** até a reconstrução terminar. É também o último
consumidor de Selenium do projeto — por isso o CP 5.5 só acontece depois desta
fase.
