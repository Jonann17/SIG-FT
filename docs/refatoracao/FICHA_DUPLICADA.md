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

### Divergência com o módulo antigo — e por que ela ficou visível

⚠️ **Corrigido em 2026-08-17, depois de ler a TELA e não só a função.**
`ficha_duplicada.montar_fila_processamento` tem `marcador_duplicada` como
parâmetro, com default `"DUPLICADA"` — mas `ModuloCopiaFichas` **sempre passou
`"PDM.9900.000"`**. Ou seja, o default nunca rodou em produção: a regra antiga
real é **substring do código**, não a palavra. A primeira versão desta seção
comparava contra o default e exagerava a divergência.

| Célula | Regra antiga (a que rodava) | Regra nova (do usuário) |
|---|---|---|
| `PDM.9900.000 - FICHA PMIB, DUPLICADA, R0` | duplicada | duplicada |
| `PDM.4320.002 - MOTOBOMBA DUPLICADA` | não | não |
| `FICHA PMIB, DUPLICADA, R0` (sem o código) | não | não |
| `usado PDM.9900.000 - R0` (código no meio) | duplicada | **não** ❌ única divergência |

A regra que vale é a do usuário. Mas **"pegar de menos" é o erro caro**: a
ficha some da lista sem sintoma nenhum, e ninguém procura o que não apareceu.
Por isso `localizar_duplicadas` passa as linhas NÃO casadas por
`parece_duplicada_sem_o_pdm` e **avisa no log**, com número de linha e o valor
lido, sem mudar a regra. A decisão continua sendo do usuário — agora com a
informação na tela.

Duas outras diferenças, ambas a favor do módulo novo:

- o antigo aceitava só os cabeçalhos `PDM USADO` e `PDM`; `PDMs usados` (a
  variação que o próprio usuário citou) fazia o módulo achar **zero** fichas;
- o antigo **descartava em silêncio** a ficha sem PMIB base ou sem alvo
  (`if pmib_base and pmib_alvo_raw`); o novo a mantém marcada como impedida,
  com o motivo, para a tela de seleção mostrar.

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

**Fornecedor e GE Vernova — são DUAS linhas, e confundi-las foi o defeito
mais caro do módulo (corrigido em 2026-08-18).**

A seção tem **três** linhas de Referência, com **três valores diferentes**:

| Linha | Como se chega nela | O que recebe |
|---|---|---|
| **Fabricante** | combo (`placeholder` diz "fabricante"); o campo **nasce** ao escolher | `CÓDIGO DO MATERIAL` (regra do `'D`) |
| **Fornecedor** | combo (`placeholder` diz "fornecedor"); o campo **nasce** ao escolher | `CÓDIGO DO MATERIAL` — o **mesmo** valor |
| **GE Vernova** | campo **fixo**, já na tela, com ícone `fa-info-circle` | `CÓDIGO CMI` / `CÓDIGO GE`, só se preenchido |

> *"O CÓDIGO DO MATERIAL deve ser preenchido no campo de fornecedor que
> devemos selecionar. E qual fornecedor? Vem da ficha original, lendo qual
> fornecedor foi preenchido. O CÓDIGO CMI / CÓDIGO GE deve ser preenchido
> somente se tiver no `_STATUS_PMIB`, e deve ser preenchido no campo do
> fornecimento da GE, que é fixo."* (2026-08-18)

⚠️ **O que estava errado.** A leitura anterior — construída sobre a frase
*"no campo do fornecedor, GE ENERGIAS RENOVÁVEIS (…) é sempre fixo"* —
tratava **Fornecedor** e **GE Vernova** como a mesma linha. Consequência
observada pelo usuário: *"ele não está conseguindo nem colocar a referência
correta do fornecedor correto, ele está fazendo no campo de fornecimento da
GE"*. O combo do fornecedor estava mapeado desde 2026-08-17
(`PLACEHOLDER_COMBO_FORNECEDOR`) e **nunca era usado por ninguém**.

O nome da função era parte da causa, não um detalhe dela:
`escrever_referencia_do_fornecedor` escrevia no campo da GE — chamar aquela
linha de "fornecedor" fazia o valor errado parecer que ia para o lugar certo.
Hoje são `escolher_fornecedor` + `escrever_referencia_da_ge`.

**O fornecedor não é fixo.** Ele vem da ficha original. Quem é fixo é a linha
da GE Vernova — e ela sequer tem combo. Por isso a 2ª estratégia de
`achar_combo_do_fabricante` ("elimine o combo que contém o fornecedor fixo")
se apoia numa premissa hoje sabidamente falsa; o lado do fornecedor **não** a
repete: sem o placeholder, recusa e vira pendência manual.

**Escrever o mesmo `CÓDIGO DO MATERIAL` em duas linhas** parece estranho e não
é: a regra do sufixo `'D` é resolvida pelo **portal**, uma linha de cada vez.
Se ele considerar as duas uma colisão, a segunda recebe `'D1` —
`escrever_referencia` lê a resposta da tela e se adapta, em vez de o código
supor qual das duas deve mudar.

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
| Leitura do `_STATUS_PMIB` (quais fichas, com que dados) | `services/duplicadas.py` | ✅ CP 6.2, 22 testes |
| Listagem para conferência sem portal | `scripts/listar_duplicadas.py` | ✅ CP 6.2 |
| Abrir a original em visualização (varre as 7 abas) | `services/duplicadas_extrator.py` | ✅ CP 6.2, 13 testes |
| Ler a tela como pares rótulo→valor | `services/duplicadas_extrator.py` | ✅ CP 6.2, 16 testes com XPath real |
| Navegar entre as SEÇÕES internas da ficha | `services/duplicadas_extrator.py` | ✅ 2026-08-18 (HTML real) |
| Ler Fabricantes/Fornecedores (duas TABELAS) | `services/duplicadas_extrator.py` | ✅ 2026-08-18 (HTML real) |
| Tela de seleção das fichas | `frontend.py` (`ModuloCopiaFichas`) | ✅ CP 6.2 — usa a identificação nova |
| Fabricante (combo com busca) | `services/duplicadas_injetor.py` | ✅ CP 6.3 |
| Referência com a regra do `'D` | `services/duplicadas_injetor.py` | ✅ CP 6.3 |
| Purga das características (preserva CÓDIGO PMIB) | `services/duplicadas_injetor.py` | ✅ CP 6.3, 18 testes |
| Robô: amarra ler-original → escrever-alvo | `services/duplicadas_robo.py` | ✅ CP 6.3, 15 testes |
| Botão na tela ("2b. Robô NOVO") | `frontend.py` (`ModuloCopiaFichas`) | ✅ CP 6.3 |
| Fornecedor (combo + referência) | `services/duplicadas_injetor.py` | ✅ CP 6.3 (corrigido 2026-08-18) |
| GE Vernova (referência CMI/GE) | `services/duplicadas_injetor.py` | ✅ CP 6.3 |
| Documentos (associar datasheet) | `services/duplicadas_documentos.py` | ✅ CP 6.4 |
| Imagens (blob → FilePond, espera o upload) | `services/duplicadas_imagens.py` | ✅ CP 6.4 — validado no portal 2026-08-21 |
| PDM da alvo antes das características | `services/duplicadas_pdm.py` | ✅ CP 6.4 |
| COMPLETO/INCOMPLETO por coluna no `_STATUS_PMIB` | `services/duplicadas_robo.py` | ✅ CP 6.4 |
| Condições — ESCREVER na alvo | `services/duplicadas_condicoes.py` | ✅ CP 6.4 (mecânica pronta) |
| Condições — LER da original em visualização | `services/duplicadas_extrator.py` | ✅ **2026-08-24, validado no portal** — ver §5.2 e §5.3 |
| Condições — conferir se a alvo já está preenchida | `services/duplicadas_condicoes.py` | ✅ 2026-08-21 |
| Abas de Condições (exclui a Financeira) | `services/duplicadas_spec.py` | ✅ CP 6.1 |
| Modo de leitura + abas de status | `services/duplicadas_spec.py` | ✅ CP 6.1 |
| Descrição/limite das imagens | `services/duplicadas_spec.py` | ✅ CP 6.1 |

### Fase 6 — o que fechou em 2026-08-21 (tarde)

A leitura das Condições da ficha ORIGINAL pela **visualização** está pronta, e
com ela a Fase 6 não tem mais buraco estrutural. O caminho:

| Peça | Onde |
|---|---|
| Abrir a seção e as sub-abas em visualização | `robo.ler_condicoes_da_original` |
| Varrer os pares rótulo→valor | `extrator.ler_secao_visivel` |
| Normalizar o rótulo (sem acento, sem `:`, caixa e espaço) | `condicoes.chave_de_rotulo` |
| Converter para `{sub-aba: {sufixo: valor}}` | `condicoes.converter_da_visualizacao` |
| **A tabela `rótulo → (sub-aba, sufixo)`** | `seletores_duplicada.CONDICOES_ROTULO_PARA_CAMPO` |
| Escrever, salvar e conferir na alvo | `condicoes.escrever` |

**Como a tabela se preencheu:** ela nasceu vazia de manhã, com a conversão
logando o texto integral de todo rótulo desconhecido. A rodada das 16:16 na
ficha `4500063671.1257` imprimiu os 17 rótulos da tela, e a tabela é
transcrição daquela lista — não tradução dos nomes em inglês.

**12 mapeados, 5 fora.** Ficaram de fora dois rádios (`Necessidade de controle
de temperatura e umidade`, `Posição de armazenamento`), dois checkboxes
(`Nocivo`, `Outros cuidados`) e `Classificação conforme NBR 10004`. Na
visualização os quatro primeiros são texto (`Horizontal`, `Sem necessidade`);
na edição são `RadioButtonN-input`/`CheckboxN`, e **qual número é qual pergunta
não está documentado em lugar nenhum** — ⚠️ **contestado em 2026-08-24;
ver §5.1 abaixo**. Marcar o rádio errado é pior do que
deixar vazio — rádio errado parece resposta. Os cinco continuam saindo no log.


#### 5.1 ⚠️ O mapa dos rádios PODE já estar no repositório (2026-08-24)

A frase acima — *"qual número é qual pergunta não está documentado em lugar
nenhum"* — foi escrita por uma sessão que **não conseguia olhar o portal** e
que também não procurou no próprio repositório. A primeira sessão local
procurou, e achou: `services/upload_conditions.py` escreve nesses mesmos
rádios, **em produção, contra o portal real**, e sabe o que cada um significa.

| Pergunta da tela | Valor | Sufixo do id | Onde está |
|---|---|---|---|
| Necessidade de controle de temperatura e umidade | SIM | `RadioButton5-input` | `upload_conditions.py:811` |
| | NÃO | `RadioButton4-input` | `:843` |
| Posição de armazenamento | Vertical | `RadioButton-input` | `:849` |
| | Horizontal | `RadioButton7-input` | `:850` |
| | Indiferente | `RadioButton8-input` | `:851` |
| Nocivo | contém agentes nocivos | `RadioButton2-input` | `:861` |
| | não contém | `RadioButton1-input` | `:867` |
| Outros cuidados | SIM | `RadioButton6-input` | `:908` |
| | NÃO | `RadioButton3-input` | `:914` |
| Classificação conforme NBR 10004 | perigoso | `b5-RadioButton1-input` | `:971` |
| | não perigoso | `b5-RadioButton2-input` | `:973` |
| Climatização / Umidade | marcar | `Checkbox4` / `Checkbox5` | `:423-424` |
| Sujeito a intempérie | marcar | `Checkbox3` | `:881` |
| Proteção SN / UV / EL | marcar | `Checkbox6` / `7` / `8` | `:887-889` |

São **os cinco rótulos que faltavam**, e mais os checkboxes.
`seletores_duplicada.CONDICOES_POR_SUBABA` já lista exatamente esses sufixos em
`booleanos` — o que faltava lá não era o sufixo, era **a qual pergunta ele
pertence**. Essa metade estava a um `grep` de distância o tempo todo.

**Por que isto NÃO fecha a seção sozinho — a forma do mapa muda.** Para campo
de texto, `CONDICOES_ROTULO_PARA_CAMPO` é `rótulo → (sub-aba, sufixo)` e o
valor é digitado. Para rádio, **o valor lido decide QUAL sufixo clicar**:

```python
"posicao de armazenamento": ("Armazenamento", {
    "vertical":    "RadioButton-input",
    "horizontal":  "RadioButton7-input",
    "indiferente": "RadioButton8-input",
}),
```

Ou seja, a entrada vira `rótulo → (sub-aba, {valor normalizado: sufixo})`, e
`converter_da_visualizacao` precisa de um ramo novo. Não é preencher tabela; é
um tipo a mais.

**E o que ainda falta é PROVA, não dedução.** Duas coisas só o portal responde:

1. **O texto exato que a VISUALIZAÇÃO mostra como valor.** A tabela acima liga
   pergunta → id, mas a chave do mapa novo é o que a tela de leitura escreve
   (`Horizontal`? `Sem necessidade`? `Não contém agentes nocivos`?). Casar por
   texto inventado é a falha silenciosa que este arquivo inteiro combate.
2. **Se `upload_conditions` e as Condições da duplicada são a MESMA tela.**
   O prefixo `b10-b17-b1-` bate com o que `XPATH_CONDICOES_CAMPO` procura por
   `contains(@id, …)` — indício forte, mas indício.

Enquanto as duas não forem lidas no portal com a ficha alvo em edição, a tabela
acima é **hipótese com evidência**, e não entra em `CONDICOES_ROTULO_PARA_CAMPO`.
Rádio errado parece resposta certa: é o erro que esta seção mais teme.


#### 5.2 A sessão local de 2026-08-24 — o que ficou PROVADO no portal

Tudo abaixo foi medido com o navegador na tela, na ficha original
`4500063671.1240` e na alvo `4500063671.0928` (HIGROSTATO, Em Elaboração).
Nada aqui é dedução.

##### ✅ ARMAZENAMENTO FECHOU — a seção inteira, automática

Ler a original → converter → escrever → salvar → conferir, tudo pelo código do
projeto (`robo.ler_condicoes_da_original` + `condicoes.escrever`). O portal
respondeu *"As condições de armazenamento foram adicionadas com sucesso!"* e a
releitura em visualização mostra os **11 campos**, incluindo os três que a
leitura antiga não enxergava.

##### 🎯 A causa raiz da semana: um TERCEIRO padrão de renderização

Na visualização há valores que são **nó de texto solto** — sem
`Block_Expression`, sem `label[@data-label]`. Os dois seletores conhecidos não
os alcançam e o campo volta `""` sem erro. Atinge `Posição de armazenamento`,
`Necessidade de controle de temperatura e umidade` e — o que importava —
**`Proteção`**, cujo rótulo é a própria `<legend>`.

E `Proteção` é **obrigatório**: o grupo carrega
`<div class="div-not-valid">Selecione pelo menos um elemento!</div>`. Sem ele
marcado, o portal recusa a sub-aba inteira com a mensagem genérica *"Por favor,
verifique os campos"*, que não nomeia campo nenhum.

**Experimento controlado que prova a cadeia:** com os quatro rádios certos e
sem `Checkbox6`, recusou. Marcando `Checkbox6` e mais nada, salvou.

Conserto em `seletores_duplicada.XPATH_VIEW_VALOR_SOLTO` (§7b-bis),
`extrator._resgatar_texto_ao_lado` e `extrator._rotular_pela_legenda`.

##### 🎯 O ESPANHOL EXISTE — era seletor quebrado, não dado ausente

O módulo vinha reportando *"nem a visualização nem o balão do tooltip tinham o
que copiar"* e devolvendo CONDIÇÕES incompleta por isso. **Falso.** A ficha
1240 tem o espanhol de todos os textos longos:

| PT (visível) | ES (no balão) |
|---|---|
| Manter na embalagem original ou envolto em material protetor… | Conservar en el embalaje original o envuelto en material protector… |
| não aplicável | no aplicable |
| Manter em ambiente limpo, seco, livre de poeira… | Mantener en un ambiente limpio, seco, libre de polvo… |
| pano seco | paño seco |

O defeito é `XPATH_TOOLTIP_DO_ROTULO`: ele sobe do rótulo por
`following::div[…osui-tooltip__content][1]` e cai no tooltip do **clipe de
anexos** (`ViewAttachmentByDataSheetAndSection`), que vem um bloco ANTES do
texto. `texto_se_existir` devolve `'0'` (a contagem de anexos) e o balão devolve
*"Documentos associados"*.

A estrutura certa, do HTML real:

```html
<div data-block="…Block_ExpressionBothLenguage" id="b12-b20-b1-$b25">
  <div data-block="Content.Tooltip">
    <div class="osui-tooltip" id="…b25-b2-TooltipWrapper">
      <div class="osui-tooltip__content" id="…b25-b2-Content"
           aria-describedby="b12-b20-b1-b25-b2-Tooltip">   <!-- aponta o balão -->
        <span data-expression="">TEXTO EM PORTUGUÊS</span>
</div></div></div></div>

<div class="osui-tooltip__balloon-wrapper__balloon" id="b12-b20-b1-b25-b2-Tooltip">
  <span data-expression="">TEXTO EM ESPANHOL</span>       <!-- fora do bloco -->
</div>
```

Dois ganhos: **não precisa de `hover`** (o balão já está no DOM), e o id do
balão é derivável — é o id do `…-Content` com `Content` trocado por `Tooltip`.

⚠️ **Consequência para a decisão registrada acima ("copiar o PT e devolver a
seção incompleta"):** ela foi tomada sobre uma premissa falsa. Não é preciso
inventar tradução nenhuma — o espanhol da própria ficha original está lá.

##### ⚠️ O espanhol é OBRIGATÓRIO, e não pelo atributo `required`

Depois de um SALVAR recusado no Transporte, os dois campos aparecem assim:

```
<textarea id="b10-b17-b3-TextArea_TransportPackagingES" class="… not-valid">
<textarea id="b10-b17-b3-TextArea_PositionCareES"       class="… not-valid">
```

`required` é `false` no HTML deles — quem exige é a validação do OutSystems.
Ou seja, **conferir `el.required` não basta** para saber o que o portal cobra;
o oráculo é a classe `not-valid` DEPOIS de tentar salvar. (Em Descarte, aí sim,
`TextArea_TypeLegislationES` e `TextArea_DiscardTypeES` também trazem
`required=true`.)

Juntando com o achado anterior: com o espanhol lido do balão, **Transporte,
Manutenção e Descarte passam a ter tudo o que o portal exige.**

##### Defeitos de silêncio encontrados de passagem

Todos da mesma família — a função diz que deu certo sem conferir:

| Onde | O que faz | O que deveria |
|---|---|---|
| `extrator.abrir_original_em_visualizacao` | devolve `True` logo após o clique | esperar a navegação; a URL vira `PMIB_DataSheetView?...` |
| `extrator.abrir_secao` | devolveu `True` para três seções seguidas sem a tela mudar | conferir que a seção pedida é a que está aberta |
| `portal.ir_para_lista` | não voltou para a lista estando dentro de uma ficha | esperar as abas de status (`//button[@role='tab']`) |
| `sel.XPATH_CONDICOES_SUBABA` | `contains(@id,'Title')` casa ~20 elementos da página | o container real é `b10-b17-Title`, com exatamente 5 filhas |
| `condicoes.conferir_subaba` | compara `'3,8'` com o que o portal normalizou para `'3.8'` | comparar por número, não por string |

##### Onde a ficha 0928 ficou

`Armazenamento` salvo e conferido. `Transporte`, `Manutenção` e `Descarte` com
o texto em português escrito no formulário mas **não salvos** (o portal recusa
enquanto o `_ES` estiver vazio). Nenhuma outra seção da ficha foi tocada.


#### 5.3 ✅ CONDIÇÕES FECHOU — as quatro sub-abas, no portal (2026-08-24)

```
>>> RESULTADO: <condicoes: ok 4 sub-abas>

[Armazenamento] 11 campo(s), salvo e conferido.
[Transporte]     4 campo(s), salvo e conferido.
[Manutenção]     6 campo(s), salvo e conferido.
[Descarte]       6 campo(s), salvo e conferido.
```

Ciclo inteiro pelo código do projeto (`robo.ler_condicoes_da_original` +
`condicoes.escrever`), da original `4500063671.1240` para a alvo
`4500063671.0928`, com o portal confirmando cada sub-aba e a releitura em
visualização mostrando português **e** espanhol.

O que faltava era, em ordem: o terceiro padrão de leitura (§5.2), o grupo
obrigatório «Proteção» (§5.2), o espanhol que estava no balão errado (§5.2) e
— o último — **esperar a tela em vez do endereço**.

##### ⚠️ A URL do OutSystems não é sinal de navegação

Custou três tentativas silenciosas antes de eu perceber. O portal é uma SPA: o
clique no ícone de visualizar abre a ficha e **o endereço continua
`PMIB_DatasheetList`** por tempo indeterminado — às vezes nunca muda. Quem
espera `"PMIB_DataSheetView" in url` conclui "não abriu" com a ficha aberta na
frente.

O sinal confiável é a TELA: as abas da própria ficha (`Condições`,
`Informações gerais`, …) aparecendo, ou `page.title() == "Ficha Técnica"`.

Isto explica, em retrospecto, por que `abrir_original_em_visualizacao` nunca
esperou nada: não havia sinal óbvio para esperar. A correção é conferir a aba,
não a URL.

##### O que o `escrever` gravou

| Sub-aba | Campos | Inclui |
|---|---|---|
| Armazenamento | 11 | 6 números + 4 rádios + `Checkbox6` (Proteção) |
| Transporte | 4 | 2 textos PT + 2 ES |
| Manutenção | 6 | 3 textos PT + 3 ES |
| Descarte | 6 | 2 textos PT + 2 ES + Classificação NBR + Logística de reversa |


#### 5.4 Rodada de ponta a ponta na ficha 0929 (2026-08-25)

Ficha LIMPA (`4500063671.0929` ← `4500063671.1277`), robô inteiro, 78 s:

```
<fabricante:      ok PRABOX>          <pdm:           ok PDM.9900.000>
<referencia:      ok RTC-45'D3>       <caracteristicas: ok 1 preservada>
<fornecedor:      ok linha fixa>      <documentos:    ok 1 associado(s)>
<ge_vernova:      ok vazia>           <imagens:       ok 1 imagem(ns)>
<condicoes:  FALHOU Descarte>
```

Oito das nove seções fecham. O que resta está isolado e descrito abaixo.

##### A regra do `'D`: o portal não diz que colidiu

Levantado escrevendo `RTC-45`, `RTC-45'D1` e `RTC-45'D2` em sequência:

| Referência | Entrou? | `not-valid` | mensagem | `CoincidenceReference` |
|---|---|---|---|---|
| `RTC-45` | não | `False` | `''` | **1** |
| `RTC-45'D1` | não | `False` | `''` | **1** |
| `RTC-45'D2` | **sim** | `False` | `''` | **0** |

Numa colisão o portal **fica calado** — nem mensagem de validação, nem
`not-valid`, nem toast. A única coisa que muda é o bloco
`CoincidenceReference` estar na tela.

`escrever_referencia` decidia a escalada lendo o TEXTO desse aviso, que vem
vazio: `e_mensagem_de_duplicidade("")` é falso, o laço desistia na segunda
tentativa e a ficha saía sem referência. Agora quem decide é a **presença**
do elemento (`injetor.houve_colisao`).

##### ☐ O que ainda falta: `TextArea_TypeLegislationES`

Descarte não fecha porque esse campo chega vazio, e lá o `..._ES` é
obrigatório — o portal recusa a sub-aba inteira com "Por favor, verifique os
campos", e junto dela ficam sem gravar campos que nada tinham a ver (a
**Logística de reversa**, observada pelo usuário).

O espanhol **existe** na original: `ler_espanhol_visivel` lido à mão na 1277
devolve os cinco pares da sub-aba, incluindo `Lei nº 12.305/2010`. Dentro do
robô ele devolve dois.

⚠️ **A pista, e ela é boa:** `XPATH_VIEW_BLOCO_DOIS_IDIOMAS` é um seletor de
PÁGINA (`//div[…BothLenguage]`), não da sub-aba aberta. Ao trocar de sub-aba
os blocos da anterior ainda estão no DOM, então a leitura "estabiliza" na
contagem ANTIGA e relê os pares da sub-aba passada. Eles casam com campos já
casados, e o `TypeLegislation` fica órfão.

**O conserto é escopar a leitura no painel da sub-aba aberta**, como
`ler_secao_visivel` já faz por `<fieldset>`. Enquanto isso, o robô nomeia o
campo no log e a seção sai incompleta — não inventa tradução.

#### ⚠️ A metade em espanhol, e por que CONDIÇÕES não fecha COMPLETO

Cada texto longo tem par na edição (`TextArea_XxxPT` / `TextArea_XxxES`) e a
visualização mostra **um** valor: o bloco é o `Block_ExpressionBothLenguage`, e
o visível é o português — o espanhol, se existe, está atrás do tooltip.

Copiar o texto português para dentro do campo espanhol seria inventar uma
tradução na ficha de outra pessoa. Então o robô copia o PT, nomeia no log os
`..._ES` que ficaram para trás e devolve a seção **incompleta**. É decisão
reversível: se o usuário disser que o mesmo texto vale nos dois idiomas, muda
uma regra em `condicoes.sufixos_em_espanhol_nao_copiados` e CONDIÇÕES passa a
fechar.

Depois disso, o CP 5.5 (remover o Selenium) destrava — `ficha_duplicada.py` é o
último consumidor.

---

O módulo antigo (`services/ficha_duplicada.py`) continua **intocado e
funcionando em Selenium** até a reconstrução terminar. É também o último
consumidor de Selenium do projeto — por isso o CP 5.5 só acontece depois desta
fase.

**O módulo novo nasceu direto em Playwright**, a pedido do usuário em
2026-08-17: *"o ficha duplicada podemos fazer direto em Playwright, pois o de
antes não funcionava muito bem"*. É o primeiro módulo do projeto que nunca teve
versão Selenium — `config.RPA_ENGINE["duplicadas"] = playwright`, e um teste de
AST garante que nenhum dos três arquivos novos importe Selenium.

Na tela os dois convivem: o botão **2** é o robô antigo (fluxo completo) e o
**2b** é o novo (fabricante, referência e características). Lado a lado porque
o antigo funciona hoje — se o novo se comportar mal na validação, o trabalho do
dia não para. O botão 2 sai quando o CP 6.4 fechar.

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

### 6.5b Terceira rodada — como separar fabricante de fornecedor (2026-08-17)

Levantada depois que o robô escreveu a referência **na linha da GE**. São três
achados, e o terceiro é o que resolve de verdade:

| Achado | Onde | Por que resolve |
|---|---|---|
| O combo se identifica sozinho | `<div class="vscomp-value" data-tooltip="Selecione um fabricante">` | Enquanto vazio, o **placeholder nomeia o campo**. O do fornecedor diz "fornecedor" no mesmo lugar |
| A busca também nomeia | `placeholder="Pesquisar um fabricante "` | (com espaço no fim — daí `contains`, não igualdade) |
| 🎯 **O campo de Referência SÓ NASCE ao escolher o fabricante** | *"daí quando seleciona uma caixa do dropdown aparece o campo de referência à direita"* | Transforma *"qual dos campos é o certo?"* — que não tem resposta boa pelo DOM — em *"qual apareceu agora?"*, que é objetiva |

O terceiro é o mais valioso porque **não depende de estrutura**: o robô tira uma
foto dos ids de `Input_TextVar` antes de escolher, outra depois, e o que
apareceu é o campo daquela linha. Nenhum `ancestor::`, nenhum índice, nenhuma
suposição sobre `<div>` que não vimos.

E o `+` da mesma linha sai do **prefixo do bloco**, lido em tempo de execução:

```
<input id="b10-b11-b4-Input_TextVar">              (referência)
<div data-block="Content.Tooltip" id="b10-b11-b4-$b6">   (o "+")
```

`b10-b11-b4-` é id gerado e **não é escrito no código** — é *lido* do campo que
acabou de nascer e usado para achar o irmão. É a diferença entre depender de um
id e usar a estrutura que ele revela.

A mesma mecânica vale para o **fornecedor**, do outro lado da seção. E a
garantia é simétrica: se o combo não for identificado, ou se o campo não
nascer, o robô **não escreve** — pendência manual é barata, referência na linha
errada não é.

### 6.5c Quarta rodada — a referência da GE Vernova (2026-08-17)

> *"Outro botão que eu havia esquecido, é o de referência da GE Vernova; quando
> a coluna CÓDIGO CMI ou CÓDIGO GE estiver preenchida no _STATUS_PMIB vale a
> pena preencher esse campo, com o valor da coluna."*

⚠️ **Corrige uma suposição minha.** Eu tinha implementado a referência do
fornecedor como *"seleciona a GE num combo e escreve no campo que nascer"* —
por **simetria** com o fabricante. O HTML mostra que **não há combo** nessa
linha: o campo é fixo e já está na tela, com um `+` próprio. Simetria é
hipótese, não evidência.

A seção tem **três** campos de Referência, com o mesmo rótulo e a mesma classe:

| Linha | Bloco | Como se distingue |
|---|---|---|
| Fabricante | `b10-b11-b4-` | **nasce** quando o fabricante é escolhido |
| GE Vernova | `b10-b11-b6-` | tem **ícone de informação** (`fa-info-circle`) entre o rótulo e o campo |
| (outra) | `b10-b11-b2-` | o que sobra |

Casar pelo ícone é melhor do que casar por posição (*"o terceiro campo"*):
posição muda quando o portal reordena a tela, e um campo a mais na seção faria
o robô escrever no lugar errado **sem nenhum aviso**.

**Uma armadilha de XPath, pega pelo teste contra o HTML real:** escrito como
`//div[tem Referência][tem ícone]//input`, o seletor casa **qualquer `<div>`
ancestral** que contenha as duas coisas em qualquer lugar — inclusive o da
seção inteira, que contém as três linhas. Resultado: 3 "campos da GE" em vez de
1. O certo é `ancestor::div[…][1]`, que diz *"o container mais próximo"* — e é
esse que representa a linha.

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

## 6.6 Quinta rodada — navegação e as duas tabelas (2026-08-18)

Levantada a pedido, e trouxe **uma correção de modelo** junto.

### Abas da ficha (visualização)

```html
<button class="osui-tabs__header-item" name="0.4z9qbl6cvoj" data-tab="1"
        role="tab" aria-selected="false" aria-controls="b12-$b12">
  <div class="display-contents ph" id="b12-b5-Title">Fabricantes e fornecedores</div>
</button>
```

Três atributos desse markup **parecem** âncora e não são: `name` é aleatório
(o `0.` denuncia), `aria-controls` é id gerado com `$`, e `data-tab` é
**ordinal** — posição é o que muda quando o portal reordena a tela, e §6.5c já
decidiu contra posição. Sobra o **texto** do `<div>`, que é o que a pessoa lê.

`aria-selected="true"` confirma que o clique pegou. Sem a conferência, um
clique que falhou deixa o extrator lendo a seção **anterior** e devolvendo
dados plausíveis da seção errada.

### Sub-abas de Condições — outro componente

```html
<div data-container="" class="dummy-active OSInline" style="cursor: pointer">Armazenamento e transporte</div>
<div data-container="" class="OSInline" style="cursor: pointer">Manutenção e descarte</div>
```

**Não são `role="tab"`** — são `<div>` clicáveis, e a aberta ganha
`dummy-active`. Supor que fossem o mesmo componente das abas de cima era
plausível e estava errado; há teste contra o HTML real para a suposição não
voltar. Confirma a tabela de §3.4: visualização tem 3 sub-abas, edição tem 5.

### 🎯 Fabricantes e fornecedores são duas TABELAS, não pares rótulo→valor

```html
<div class="full-fieldset" id="b12-b13-ManufacturerAndProvider">
  <table><thead><tr><th>Nome do Fabricante</th><th>Referência</th></tr></thead>
  <tbody><tr><td data-header="Nome do Fabricante"><span data-expression>ENERSYS</span></td>
             <td data-header="Referência"><span data-expression>E24-256-10</span></td></tr>
         <tr><td data-header="Nome do Fabricante"><span data-expression>SASSI</span></td>…
<div class="full-fieldset" id="b12-b14-ManufacturerAndProvider">
  <table><thead><tr><th>Nome do Fornecedor</th>…
    <td data-header="Nome do Fornecedor"><span data-expression>GE ENERGIAS RENOVAVEIS LTDA</span></td>
    <td data-header="Referência"><span data-expression>08934120BTM99-064F</span></td>
```

**Isto derruba uma suposição do extrator.** `XPATH_VIEW_VALOR` (§8) exige o
ancestral `PMIB_DataSheetView.Block_Expression`; estas células **não o têm**.
Ou seja, a varredura de rótulo→valor **não enxerga esta seção**, e
`achar_fornecedor` lendo dela devolvia `""` para uma ficha real, sem erro
nenhum. Provado em `tests/test_duplicadas_xpath_real.py`, avaliando o XPath
contra este markup.

Os dois contêineres têm o **mesmo sufixo de id** (`-ManufacturerAndProvider`),
mudando só o prefixo gerado — então o id não separa fabricante de fornecedor.
Quem separa é `@data-header`, o mesmo atributo que `tech_specs` já usa: é
padrão da plataforma, agora confirmado numa segunda tela.

E a tabela do fabricante tem **duas linhas** nesta ficha: *"a gente comprou de
um que comprou do fabricante"* — ENERSYS fabrica, SASSI revende. Ler só a
primeira perderia a segunda em silêncio.

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

⚠️ **Correção de 2026-08-17, achada tentando sabotar o próprio seletor:** das
duas primeiras linhas, **só a primeira é load-bearing**. Quem impede a inversão
é o ramo do rótulo exigir `//span` — o `<label>` da opção marcada não tem
nenhum, logo nunca entra como rótulo. O `[not(span)]` de
`XPATH_VIEW_OPCAO_MARCADA` é a segunda tranca da mesma porta: removê-lo não
quebra nenhum teste contra o HTML real. Ficou (custa zero), mas está registrado
que **ninguém deve contar com ele**.

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
