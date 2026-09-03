# Ficha técnica em inglês — caderno da frente

> Aberta em 2026-08-28. Companheira de
> [`base-conhecimento/13-montagem-da-ficha-tecnica.md`](base-conhecimento/13-montagem-da-ficha-tecnica.md),
> que mapeia **como a ficha nasce**. Aqui está o que muda para ela nascer em
> inglês, o que já está pronto e o que ainda espera.

## O problema

O SIG-FT tem **dois templates** de ficha — PT-BR e inglês —, mas as
características técnicas coladas dentro deles vêm sempre da **mesma** pasta de
PDMs Modificados, que está em português. A tradução era feita **à mão**, ficha
a ficha.

## O desenho (decisões do usuário, 2026-08-28)

| Pergunta | Decisão |
|---|---|
| Como o app sabe o idioma? | **Seletor explícito na tela** (Português / English). Deduzir do nome do arquivo do template quebraria em silêncio no dia em que alguém o renomeasse — e ficha montada no idioma errado não se denuncia sozinha |
| Qual motor de tradução? | **IA primeiro, `deep_translator` de reserva.** A IA entende termo técnico de hidrelétrica; a `deep_translator` é a mesma cadeia (Google → MyMemory) que o fluxo do espanhol já usa |
| Como corrigir termo errado? | **Glossário editável**, consultado antes do motor |
| Onde ficam os traduzidos? | Pasta paralela, escolhida na tela |

## O fluxo, agora

```
PDMs Modificados/                     (português, como sempre)
      │
      │  Aba 1, passo 3: "Traduzir PDMs Modificados para inglês"
      ▼
PDMs Modificados EN/                  + _GLOSSARIO_PT_EN.txt
      │                               + _CACHE_TRADUCAO.json
      │  Aba 2, idioma = English
      ▼
Ficha em inglês
```

O idioma escolhido na aba 2 decide **qual pasta** o montador usa. Em
português, nada muda: quem não tocar no seletor tem exatamente o
comportamento de sempre.

## O que o serviço faz, e por quê

`sigft/services/traducao_pdm.py`. Os arquivos traduzidos mantêm **nome e
geometria** dos originais, e isso não é estética:

- **o nome**, porque o montador acha o PDM por *substring* do id
  (`PDM_1234_001`) no nome do arquivo — renomear quebraria o casamento em
  silêncio;
- **a célula**, porque o montador lê `cell(linha, 1)` — escrever noutra coluna
  geraria fichas em branco, e ninguém perceberia até abrir uma.

Cada arquivo é **copiado** e só a célula da descrição é reescrita: mescla,
bordas, altura 32 e fonte 8 sobrevivem sem precisar ser refeitas.

**Só o miolo da pergunta viaja.** Em `"1 - Pressão de trabalho (bar):"`, o
`"1 - "` é numeração e o `":"` é pontuação — mandar os dois para um tradutor é
pedir para ele inventar. A unidade viaja **junto** com a descrição, de
propósito: `"Pressão (bar)"` dá ao motor o contexto que `"Pressão"` sozinho
não dá.

### Três camadas antes do motor

| Camada | Arquivo | Quem mantém |
|---|---|---|
| **Glossário** — frase inteira que estiver lá é usada verbatim, sem chamar o motor; termo solto vira vocabulário obrigatório no prompt | `_GLOSSARIO_PT_EN.txt` | **você**, editando à mão |
| **Cache** — rerodar a pasta não paga tradução de novo | `_CACHE_TRADUCAO.json` | a máquina |
| **Dedupe** — `Fabricante`, `Modelo`, `Peso` aparecem em dezenas de PDMs e vão ao motor uma vez só | (em memória) | — |

Separar glossário de cache é deliberado: o glossário é **curado por gente** e
vence tudo; o cache é crescido pela máquina. Misturar faria a sua correção se
perder na próxima limpeza de cache.

O glossário lê UTF-8 **e cp1252** — o arquivo é para ser editado à mão, e o
Bloco de Notas ainda oferece ANSI no "Salvar como". Mesma lição do `.txt` da
conferência do AutoSpec.

## Um defeito antigo que saiu junto

`aplicar_templates_fichas` fazia `wb_target["Ficha Técnica Padrão"]` — **nome
de aba fixo**. Um template com a aba noutro nome levantava `KeyError` dentro
do laço, e o `except` genérico transformava isso em `"ERRO ao gerar ficha
{pmib}"` **uma vez por ficha**: num lote de 200 materiais, 200 linhas
idênticas, nenhuma delas dizendo que o problema era a aba.

Agora `nome_da_aba_da_ficha` aceita variações (sem acento, maiúsculas, e os
nomes em inglês), usa a aba única quando só há uma, e — quando de fato não
reconhece nenhuma — **para o lote com os nomes encontrados na mensagem**.
Template errado é problema do template, não de cada ficha.

## O template em inglês — conferido (2026-09-03)

O usuário entregou dois arquivos: o template `Technical_Sheet_of_PDM-R3.xlsx`
e uma ficha já preenchida, `4500063671.0052_enUS.xlsx`. As três incógnitas
foram medidas, não deduzidas:

| O quê | Resultado |
|---|---|
| **Nome da aba** | O template traz `Ficha Técnica Padrão` — em **português**, herança do template do qual foi derivado. A ficha preenchida traz `Standard Technical Sheet`. Os dois circulam; os dois passaram a ser reconhecidos |
| **Linha inicial** | **79**, idêntica ao PT-BR. O título da seção está na linha 75 nos dois idiomas |
| **Colunas C e M** | Idênticas: mescla `C{n}:L{n}` para a pergunta, `M{n}:V{n}` para a resposta |
| **Abaixo da injeção** | Nada. O template acaba na linha 76 e vai vazio até a 156 — não há rodapé para sobrescrever, por mais perguntas que o PDM tenha |

E a ficha montada no template real foi conferida por inteiro: cabeçalho da
seção, `Function of the material`, as condições de armazenagem, as mesclas, e
a coluna da resposta em branco para o fornecedor.

### Três coisas que o arquivo real desmentiu

**1. A forma da pergunta.** Eu tinha desenhado tudo em cima de
`"1 - Pressão de trabalho (bar):"` — rótulo curto com a unidade entre
parênteses. A forma real é outra:

```
9 - TIPO CONSTRUTIVO (Indicar o tipo construtivo do item. Nota: Material
especifico de compra com (Número de desenho, referência, nome usual, outros)):
```

De 100 a 200 caracteres, com a **instrução de preenchimento inteira** dentro
dos parênteses e outros parênteses aninhados nela. O prompt mandava
*"PRESERVE a unidade entre parênteses exatamente como está"* — regra escrita
para `(bar)`, que aplicada a isto manda o modelo devolver a instrução em
português. Ficha metade em cada idioma, e nenhum teste reclamaria: todos os
meus exemplos casavam com a suposição errada.

`partes_da_pergunta` sobreviveu ao teste: as **17 perguntas reais remontam
byte a byte**. O que estava errado era o prompt, não a divisão.

**2. O analyzer só procurava o título em português.** `TECHNICAL SPECIFICATIONS
- INDICATE...` não casava, e a busca caía no valor de reserva 79 — que **por
coincidência** é a linha certa, porque o template EN também põe o título na 75.
Funcionava pelo motivo errado. O preço aparecia exatamente no caso que a busca
dinâmica existe para resolver: fornecedor que insere linhas acima da seção. A
ficha PT se conserta sozinha; a EN passava a ler da linha errada em silêncio.

**3. Um teste meu passava por acaso.** `test_variacoes_de_nome_que_o_montador_
deve_aceitar` montava o workbook com **uma aba só** — e aba única é aceita por
atalho, sem passar pela normalização. A parametrização inteira nunca testou
nada. Descoberto porque o caso novo (`Standard Technical Sheet`) passou
**antes** de eu escrever a linha que o faz passar.

### O glossário nasce com as traduções da casa

As duas fichas dão pares de tradução reais — não invenção minha. O
`_GLOSSARIO_PT_EN.txt` já vem semeado com eles:

| PT | EN |
|---|---|
| `NORMAS TECNICAS APLICAVEIS` | `APPLICABLE TECHNICAL STANDARDS` |
| `CARACTERISTICAS ADICIONAIS` | `ADDITIONAL CHARACTERISTICS` |
| `TIPO CONSTRUTIVO` | `TYPE OF CONSTRUCTION` |
| `CERTIFICADO` | `CERTIFICATE` |
| `Indicar` / `do item` / `outros` | `Indicate` / `of the item` / `others` |

E o estilo da casa virou **exemplo trabalhado dentro do prompt**, que vale mais
que três regras: nome em MAIÚSCULAS, instrução em caixa normal começando por
`Indicate`.

⚠️ **Limite do glossário de termo solto:** no caminho reserva
(`deep_translator`), um termo só conserta o que o tradutor tiver **deixado em
português**. Se ele já traduziu mal, o português não está mais lá para ser
trocado. Para consertar uma tradução ruim com certeza, ponha a **pergunta
inteira** no glossário — essa nem passa pelo tradutor. Está escrito no
cabeçalho do próprio arquivo.

### Uma decisão que ficou com o usuário

A ficha gerada sai com a aba chamada `Ficha Técnica Padrão`, porque é assim que
o template está. A ficha em inglês que o usuário entregou tem
`Standard Technical Sheet` — ou seja, **hoje ele renomeia à mão**. Renomear
automaticamente quando o idioma for inglês é seguro (o analyzer escolhe a aba
por evidência, não por nome — `_aba_da_ficha`), mas muda um entregável que vai
para o fornecedor, então não foi feito por conta própria.

## Verificação

- **72 testes** (46 do serviço de tradução, 18 do montador/idioma, 8 do
  layout/analyzer nos dois idiomas). Suíte inteira: **2889 passando**.
- **Ponta a ponta com o template EN REAL** (`e2e`, openpyxl de verdade): as 17
  perguntas reais da ficha 0071 viraram um PDM Modificado, foram traduzidas e
  montadas dentro do `Technical_Sheet_of_PDM-R3.xlsx`. Conferido: numeração
  não vai ao motor, instrução entre parênteses vai junto, remontagem exata,
  primeira pergunta em C79, décima sétima em C95, nada escrito em C96, mesclas
  `C79:L79` e `M79:V79`, coluna da resposta vazia, e todo o miolo do template
  real intacto (cabeçalho, `Function of the material`, armazenagem).
- O e2e anterior usava um template **sintético que eu mesmo montei** — ele
  provava a minha ideia do template, não o template.
- O motor de tradução continua **injetado** nos testes: testar o Google
  Tradutor seria medir a rede, não o código.

## Ainda em aberto

| Item | Nota |
|---|---|
| Rodar com o **motor de verdade** (IA/`deep_translator`) | o contêiner do Claude na web não tem `deep_translator` nem chave de IA; a qualidade da tradução técnica só dá para julgar na sua máquina. É o único item que sobrou do desenho |
| Renomear a aba para `Standard Technical Sheet` no idioma inglês | decisão do usuário — ver acima |
| Semear o glossário com os termos do AutoSpec | o `GLOSSARIO_MULTILINGUE` do AutoSpec tem 71 termos PT/EN/DE/ES/FR/IT que serviriam de partida |
| **Analisar** ficha em inglês de volta | o título da seção já é reconhecido nos dois idiomas, e os campos fixos são lidos por endereço de célula (independente de idioma). O que ainda não foi medido é o comportamento do validador de IA diante de respostas em inglês — `"Not applicable"` em vez de `"Não aplicável"`. Registrado em `PENDENCIAS.md` |
