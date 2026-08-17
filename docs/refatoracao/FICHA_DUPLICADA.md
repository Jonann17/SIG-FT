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
  teto, um portal que rejeite tudo faz o robô tentar para sempre.

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

⚠️ **Leitura minha:** o usuário não disse se a célula de `OBSERVAÇÕES` contém
**só** o código ou um texto com o código no meio. `extrair_ficha_original()`
aceita os dois (procura o padrão `##########.####` em qualquer posição) porque
o primeiro caso é subconjunto do segundo. **Se a célula puder ter dois
códigos, a função devolve o primeiro** — confirmar antes de rodar em lote.

### 3.3 Documentos e imagens

> *"Na parte da imagem, devemos copiar os dados da ficha original e colar as
> imagens. No documento, como já está criando um objeto dentro do portal pra
> ficha original, basta chamá-lo nesta ficha e associar: então clicar em
> associar os documentos e digitar exatamente o que foi anexado na ficha
> original."*

- **imagens**: copiar da original e colar (⚠️ o mecanismo — download/upload ou
  clipboard — precisa ser visto na tela; muda completamente a implementação);
- **documentos**: não se sobe arquivo. O documento **já existe** como objeto
  no portal; associa-se pelo diálogo *"Selecionar Documentos"*, buscando pela
  descrição exata da original. A busca é textual e o diálogo é paginado (809
  itens, 162 páginas na tela levantada) — a busca é obrigatória, paginar não
  é opção.

### 3.4 Condições

> *"Na seção de condições, copiar todos os dados em todas as seções, com
> exceção da parte financeira."*

🔴 **BLOQUEADA até especificação campo a campo.** O usuário disse o que **não**
copiar, mas não disse **quais campos** compõem "a parte financeira" na tela de
Condições. Copiar dado financeiro de uma ficha para outra é erro caro e
**silencioso** — a ficha fica plausível e errada.

`SECOES_BLOQUEADAS_ATE_CONFIRMACAO` mantém isso explícito no código, com teste.

---

## 4. Perguntas abertas

Nenhuma impede começar; todas impedem **rodar em lote sem conferir**.

1. **Condições — quais campos são "a parte financeira"?** Lista campo a campo,
   contra a tela. É a única que bloqueia uma seção inteira.
2. **Imagens — como se copia?** Baixar da original e subir na duplicada, ou
   existe "copiar/colar" no portal? Muda a implementação inteira do 6.4.
3. **`OBSERVAÇÕES` pode ter mais de um código?** Se sim, qual vale.
4. **O que fazer quando as 20 tentativas de referência se esgotam?** Hoje o
   plano é: parar, registrar pendência manual e seguir para a próxima ficha —
   nunca salvar com referência errada. Confirmar.
5. **A ficha original é sempre encontrável pelo código de `OBSERVAÇÕES`?**
   E se ela não existir mais no portal?

---

## 5. Estado da implementação

| Parte | Onde | Estado |
|---|---|---|
| Identificação por PDM + colunas | `services/duplicadas_spec.py` | ✅ CP 6.1, 24 testes |
| Sequência `'D` + detecção de colisão | `services/duplicadas_spec.py` | ✅ CP 6.1 |
| Código da ficha original | `services/duplicadas_spec.py` | ✅ CP 6.1 |
| Tela de seleção das fichas | `frontend.py` | ☐ CP 6.2 |
| Extração da ficha original | novo serviço | ☐ CP 6.2 |
| Injeção (fabricante, características) | novo serviço | ☐ CP 6.3 |
| Documentos e imagens | novo serviço | ☐ CP 6.4 |
| Condições | — | 🔴 bloqueada (pergunta 1) |

O módulo antigo (`services/ficha_duplicada.py`) continua **intocado e
funcionando em Selenium** até a reconstrução terminar. É também o último
consumidor de Selenium do projeto — por isso o CP 5.5 só acontece depois desta
fase.
