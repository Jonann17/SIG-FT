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

**As duas técnicas também foram respondidas**, com HTML do DOM real — ver §6.

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

---

## 6. Seletores levantados do DOM real

O usuário inspecionou os três componentes no portal. Estão em
`sigft/core/rpa/seletores_duplicada.py`, no inventário de auditoria, com
15 constantes e 13 testes.

### 6.1 O `<input type=file>` das imagens **é** alcançável

```html
<input class="filepond--browser" type="file" id="filepond--browser-h1d4zvekk"
       accept="image/jpeg,image/png" multiple="">
```

É **FilePond**, e a resposta muda o CP 6.4 para o caminho fácil:

- **existe input de arquivo de verdade** → `set_input_files` (Playwright) ou
  `send_keys(caminho)` (Selenium). **Confirmada** a recomendação de baixar da
  original e subir na duplicada, em vez de reproduzir o copiar/colar humano;
- o input é **escondido** pelo FilePond, e isso não é problema: preencher input
  de arquivo escondido é exatamente o que essas APIs fazem. ⚠️ **Não clique no
  rótulo "Adicione"** — abriria o diálogo de arquivo do sistema operacional,
  que o navegador não controla e que travaria o robô;
- `accept="image/jpeg,image/png"` → **só JPEG e PNG**. Imagem baixada em webp
  ou gif é recusada no envio;
- `multiple` + "Máximo 10 arquivos" → até 10 por vez.

### 6.2 Duas armadilhas de id, e é o achado mais valioso deste levantamento

| Id no DOM | Por que **não** usar |
|---|---|
| `filepond--browser-h1d4zvekk` | sufixo **aleatório por renderização** (o mesmo aparece em `filepond--drop-label-…` e `filepond--assistant-…`) |
| `vscomp-search-input-3940` | número **sequencial do widget** |

O erro é atraente: o id aparece no inspecionar elemento, parece o seletor mais
preciso possível e **funciona na primeira tentativa**. A falha vem noutra
sessão, parecendo mudança de portal. Os seletores casam por **classe**
(`filepond--browser`, `vscomp-search-input`), e `IDS_GERADOS_NAO_USAR` +
teste impedem que alguém volte a amarrá-los.

Já `Input_DescriptionES` / `Input_DescriptionPT` / `Input_SearchFilter` são
nomes de campo — estáveis. O que se descarta ali é o **prefixo** `b10-b15-`,
que é o caminho do bloco no OutSystems e muda se o formulário for
reorganizado. Daí `contains(@id, 'Input_DescriptionES')`.

### 6.3 Combo de fabricante — `virtual-select`

Confirmado pelo usuário: *"é melhor por digitando texto, que daí filtra"*.
Fluxo: clicar em `.vscomp-toggle-button` → digitar em `.vscomp-search-input` →
escolher a opção filtrada.

É a **mesma família de widget** que `cria_fichas.XPATH_PDM_FINAL` já usa
(`div.vscomp-value[data-tooltip^='PDM']`) — o padrão de seletor já foi validado
contra o portal em outro módulo, o que reduz o risco do CP 6.3.

### 6.4 Documentos

`Associar documentos` → `Input_SearchFilter` → `button.search-button` (a lupa)
→ marcar a linha → `ASSOCIAR`. A busca textual é obrigatória: 809 itens em 162
páginas.

### 6.5 Segunda rodada de HTML — o que ela acrescentou

| Componente | Achado |
|---|---|
| **Opção do combo** | casar por `@data-tooltip` do `span.vscomp-option-text`, não pelo texto do `<div>` (que vem com quebras de linha em volta). `role="option"` como âncora semântica. `data-value="1533"` seria o casamento mais forte, mas não temos o id interno — a ficha original dá o **nome** |
| **Checkbox do documento** | `id="…-l1_0-521_0-Checkbox1"` traz o **índice da linha**, que muda a cada busca. Âncora boa: `@data-header='Selecionar'` — o mesmo atributo que `tech_specs` já usa |
| **Campo de Referência** | `Input_TextVar` é nome **genérico**; o seletor ancora no **rótulo** "Referência" |
| **Aviso de colisão** | 🎯 tem bloco próprio, com id semântico `CoincidenceReference` — não é texto solto na página |
| **Abas de status** | `role="tab"` + texto; o **badge** permite pular direto para a aba com contagem > 0 em vez de abrir as 7 |
| **Coluna Ações** | sufixos `-View` / `-Edit` / `-Delete` são semânticos; os ícones `fa-file-o` (visualizar) e `fa-pencil-square-o` (editar) confirmam. O seletor exige **os dois** |

**O `CoincidenceReference` melhora a detecção de colisão.** A alternativa era
varrer a tela atrás da frase *"A referência já existe!"*, frágil em três
frentes: **idioma** (a tela alterna PT/ES), **redação** (o portal pode
reescrever) e **escopo** (outra mensagem parecida daria falso positivo — e
falso positivo aqui gasta as 20 tentativas de sufixo escondendo o erro real).
Com o bloco, a pergunta vira *"este bloco tem conteúdo?"*. As duas checagens
**se somam**, não se substituem.

**Quatro tipos de id gerado** já catalogados em `IDS_GERADOS_NAO_USAR`:
sufixo aleatório do FilePond, número de instância do `vscomp`, índice de opção
do `vscomp` e **índice de linha do OutSystems** (`-l1_0-`) — este último
apareceu em **duas telas diferentes**, então é padrão da plataforma, não
coincidência.

---

## 7. O que ainda falta levantar

**Não é preciso mapear todos os campos do modo de visualização** — seria
trabalho grande e frágil. A tela de visualização renderiza **rótulo acima,
valor abaixo**, um padrão uniforme; um extrator que leia pares
rótulo→valor cobre a seção inteira sem enumerar campo nenhum, e não quebra
quando o portal acrescentar um campo.

✅ **Resolvido** — o bloco "Volume (cm3)" foi levantado e confirmou a
estrutura. Ver §8.

---

## 8. Modo de visualização: a estrutura que dispensa mapear campo a campo

HTML real de um bloco:

```html
<fieldset>
  <legend>…<span class="text-primary font-size-base">Volume (cm3)</span></legend>
  <div>
    <div data-container="">
      <label data-label=""><span class="text-primary">Comprimento da embalagem unitária</span></label>
      <div data-container="">
        <div data-block="PMIB_DataSheetView.Block_Expression" id="b12-b20-b1-$b3">
          <span data-expression="">6</span>
        </div>
      </div>
    </div>
    …repete…
  </div>
</fieldset>
```

**`data-block="PMIB_DataSheetView.Block_Expression"` é a peça central**: marcador
semântico de *"aqui há um valor exibido em modo de leitura"*, namespaceado pelo
módulo OutSystems. Distingue o valor de qualquer outro `<span>` da página sem
depender de classe de layout.

| Papel | Onde |
|---|---|
| nome do agrupamento | `fieldset > legend > span` |
| rótulo do campo | `label[@data-label] > span` |
| valor do campo | `div[@data-block='PMIB_DataSheetView.Block_Expression'] > span[@data-expression]` |

⚠️ `id="b12-b20-b1-$b3"` é gerado e **sequencial** (`$b3`, `$b4`, `$b5`) — o `$`
já denuncia. É o 5º tipo catalogado em `IDS_GERADOS_NAO_USAR`.

### Por que UMA varredura e não duas

Não há id ligando rótulo a valor — **o que liga é a ordem de documento**. Então
o extrator pede os dois na mesma consulta (`XPATH_VIEW_ROTULOS_E_VALORES`, um
`|` de XPath, que devolve em ordem de documento) e pareia em
`parear_rotulos_e_valores()`.

Duas varreduras separadas obrigariam a casar **por índice**, e bastaria um campo
sem valor para desalinhar tudo dali para baixo — erro que produz ficha
**plausível e errada**, o pior tipo.

Regras do pareamento, cada uma de um caso da tela real:

- cada valor pertence ao rótulo **imediatamente anterior**;
- **rótulo sem valor** vira `""` e não some — sumir impediria o injetor de
  distinguir "não existe esse campo" de "existe e está vazio";
- **valor sem rótulo antes** é descartado — atribuí-lo ao rótulo *seguinte*
  inverteria o pareamento da aba inteira;
- **rótulo repetido** fica com o primeiro valor.

**Testado contra o HTML real do portal**, não contra markup inventado
(`tests/test_duplicadas_leitura_view.py`, 14 testes): o bloco colado do
"inspecionar elemento" produz exatamente os três campos da tela, e a legenda
"Volume (cm3)" não vira par.

### 8.1 O segundo padrão — opções marcadas, e ele é INVERTIDO

Levantado depois, e foi o que justificou pedir o HTML em vez de generalizar a
partir de um exemplo só:

```html
<span class="text-primary font-size-base">Nocivo</span>          <!-- RÓTULO -->
<div class="custom">
  <span><input class="radio-button" disabled type="checkbox" checked></span>
  <label data-label="">Não contém agentes nocivos</label>          <!-- VALOR -->
</div>
```

**Duas inversões, e as duas quebrariam a leitura em silêncio:**

1. o **rótulo** do campo não é um `<label>` — é um `<span class="text-primary">`,
   a **mesma classe da legenda** do fieldset;
2. o **valor** está **dentro de um `<label data-label>`** — exatamente o seletor
   que no outro padrão significa *rótulo*.

Sem discriminar, o extrator leria "Não contém agentes nocivos" como rótulo de
campo com valor vazio, e **o campo "Nocivo" sumiria** da ficha copiada.

O discriminador é a presença de `<span>` **dentro** do label:

| Estrutura | Papel |
|---|---|
| `label[@data-label]/span` | rótulo (padrão do Volume) |
| `label[@data-label]` sem span | valor (opção marcada) |
| `span.text-primary` fora de `label` e de `legend` | rótulo de seção |

O `@checked` do input é o que diz qual opção está selecionada (`disabled` é só o
modo de leitura). A tela levantada renderiza apenas a marcada, mas o seletor
exige `@checked` de qualquer forma — se um dia renderizar todas, ler a errada
seria pior que não ler nenhuma.

### 8.2 A armadilha do contador de anexos

O bloco "Logística de reversa" revelou que o **clipe de papel** também tem um
`<span data-expression>0</span>` — o mesmo seletor do valor de campo:

```html
<div data-block="Numbers.Badge">…<span data-expression="">0</span>
```

Só não é lido **por causa do namespace**: `XPATH_VIEW_VALOR` exige o ancestral
`data-block='PMIB_DataSheetView.Block_Expression'`, e o badge está sob
`Numbers.Badge`. Ou seja, exigir o nome completo do bloco não é preciosismo — é
o que separa **valor** de **contador**. Sem ele, "Logística de reversa" viria
como `"0"`: plausível, errado e sem erro nenhum.

Também confirmado: `&nbsp;` (`Não se&nbsp;aplica`) é normalizado — `str.split()`
do Python trata `\xa0` como espaço.

**O CP 6.2 está fechado do lado da leitura.** Os dois padrões de campo estão
cobertos e testados contra markup real.
