# Busca web de datasheet — por que não achava, e o que mudou

**Data:** 2026-08-12 · **Frente:** AutoSpecAI (Rafael) · **Origem:** ficha real 4500063671.1188

---

## 1. O sintoma

O Luan rodou o AutoSpec no sensor de contaminação **HYDAC `CS1320-A-0-0-0-1/-000`**,
**sem manual anexado**, com dois modelos de IA. Da tabela de 22 especificações técnicas:

| Modelo | Preenchidos | Vazios |
|---|---|---|
| minimax | 3 de 22 | 19 |
| grok | 0 de 22 | 22 |

Com PDF anexado, o mesmo módulo preenche quase tudo. O problema é exclusivo do caminho web.

**O grok preencher zero não foi burrice — foi obediência.** É o modelo mais forte dos dois. O
prompt manda não inventar; ele não recebeu contexto nenhum e obedeceu. Os 3 campos do minimax
vieram do conhecimento paramétrico dele, não de documento — e por isso são piores que vazios:
não têm fonte conferível.

**O erro estava antes da IA.** Trocar de modelo nunca resolveria.

## 2. Causa raiz

Investigado com `superpowers:systematic-debugging`. As duas causas foram **medidas**, não
deduzidas — e a primeira hipótese, plausível, estava errada.

### A hipótese que caiu

Suspeita inicial: a razão social `HYDAC TECNOLOGIA LTDA` polui a query e derruba o resultado.

**Teste:** rodar a query exata do script numa busca real.
**Resultado: a busca funciona.** A página certa vem em 1º e 3º lugar. Hipótese descartada.

Sem o teste, essa "correção óbvia" teria sido implementada e não resolveria nada.

### D1 — o filtro anti-intruso era uma guilhotina

O filtro da regra de negócio §4.3 exigia a string **inteira** do fabricante como substring do
título/snippet/link:

```python
term_clean = str(term).lower().strip()          # "hydac tecnologia ltda"
if term_clean in title or term_clean in snippet or term_clean in link
```

A planilha do PMIB guarda a **razão social brasileira**. As páginas reais dizem `HYDAC` ou
`HYDAC Technology Corporation`. **Nenhuma diz `HYDAC TECNOLOGIA LTDA`.** O segundo termo,
`cod_mat`, é o código **interno** do PMIB — não existe na internet.

Medido contra os 4 primeiros resultados reais: **0 de 4 sobreviviam**. Nada era baixado, nada
era extraído, a IA recebia contexto vazio.

### D2 — a cascata procurava o SKU, não o datasheet

A busca usava só o código de **configuração** completo, `CS1320-A-0-0-0-1/-000`. Esse código
identifica um item de loja. O datasheet é publicado para a **família** — `ContaminationSensor
CS 1000 Series`.

Medido:

| Query | Resultado |
|---|---|
| `HYDAC TECNOLOGIA LTDA CS1320-A-0-0-0-1/-000 datasheet` | páginas de e-commerce em HTML |
| `HYDAC CS1000 series CS1320 filetype:pdf` | **10 datasheets reais** |

### Achado colateral, também medido

A razão social **degrada** a busca sem quebrá-la:

| Query | Relevantes |
|---|---|
| `HYDAC TECNOLOGIA LTDA CS1320 datasheet filetype:pdf` | 1 de 7 (o 1º era datasheet de bateria de lítio) |
| `HYDAC CS1000 series contamination sensor CS1320 filetype:pdf` | 10 de 10 |

A hipótese inicial não estava errada — estava **incompleta**. Não era a causa raiz, mas é um
problema real, e agora tem evidência para ser corrigido junto.

## 3. Abordagens consideradas

**A — afrouxar o filtro para "qualquer palavra do fabricante".** Simples, mas joga fora a
proteção §4.3: um catálogo de concorrente que cite "Hydac" numa comparação passaria.

**B — remover o filtro e confiar na IA.** O prompt já manda conferir se o documento é do
material (instrução 2) e declarar a fonte (instrução 7). Rejeitada: transfere para o modelo uma
decisão que o código resolve de graça, e o custo do erro (ficha preenchida com dado de outra
peça) é alto demais para depender de uma instrução em texto.

**C — corrigir o casamento e ampliar a cascata (adotada).** O filtro continua existindo e
continua barrando concorrente; o que muda é *contra o quê* ele compara. E a cascata ganha as
duas etapas que a medição mostrou funcionar.

Adotada a C porque as outras duas trocam um problema medido por um risco não medido.

## 4. Desenho

### 4.1 Casamento de termo

Três funções de módulo, sem estado:

| Função | O que faz |
|---|---|
| `_normalizar_texto_busca` | minúsculas, sem acento |
| `_compactar_codigo` | só letras e dígitos: `CS 1000 Series` → `cs1000series` |
| `_resultado_e_relevante` | o filtro §4.3, agora casando por texto normalizado **ou** por código compactado |

O casamento compactado exige **3+ caracteres**, senão um termo curto (`SA`, `GE`) viraria
coringa que aprova qualquer página.

### 4.2 Nome do fabricante

`_nome_curto_fabricante` remove palavras de razão social (`LTDA`, `S.A.`, `TECNOLOGIA`,
`INDUSTRIA`, `DO BRASIL`, `GMBH`, `INC`…). `HYDAC TECNOLOGIA LTDA` → `HYDAC`.

Se a limpeza não sobrar nada, **devolve o nome original** — ficar sem fabricante seria pior, é
ele que ancora o filtro.

### 4.3 Família do produto

`_familia_do_identificador` corta no primeiro separador: `CS1320-A-0-0-0-1/-000` → `CS1320`.
Exige dígito e 3+ caracteres na sobra, senão `ABC-1` viraria a família `ABC`.

### 4.4 A cascata

```
1. "{cod_mat}" {fab_curto} datasheet
2. {fab_curto} {ids} datasheet filetype:pdf     <- NOVA
3. {fab_curto} {ids} datasheet
4. {fab_curto} {familia} datasheet filetype:pdf <- NOVA
5. {fab_curto} {familia} datasheet              <- NOVA
6. {fab_curto} {id mais longo} datasheet
7+. prosa truncada (fallback para material sem identificador)
```

**A família vem depois do código exato, nunca antes.** A cascata para na primeira query que
rende documento: o datasheet da família certa com a configuração errada é melhor que nada, mas
pior que o exato.

Custo de cota: a cascata só avança enquanto não acha. No caso bom termina em 1–2 queries, e o
cache de busca (TTL 7 dias) cobre reexecução.

### 4.5 O diagnóstico que faltava

Descartar **100%** dos resultados deixa de ser linha `info` no meio das outras e vira `warn`
listando os termos usados. Foi essa linha silenciosa que escondeu a falha e custou uma
investigação inteira.

### 4.6 Corrigido de passagem

`_baixar_resultados` baixava `item['link'].lower()`. Caminho de URL é sensível a caixa em boa
parte dos servidores — arquivo com maiúscula no nome dava 404. Agora a normalização acontece na
comparação, não no dado.

## 5. Verificação

`tests/test_autospec_busca_web_falha_real.py`, 24 testes, com os resultados **reais** do Google
para este material como fixture. Ciclo red-green conferido revertendo o código-fonte:

```
sem a correcao: 22 failed, 2 passed
com a correcao: 24 passed
```

Antes/depois contra os 4 resultados reais:

```
ANTES:  0/4 sobreviveram ao filtro
DEPOIS: 3/4
Parker (concorrente): BARRADO nos dois  <- a protecao §4.3 continua de pe
```

O 4º é um datasheet de distribuidor cujo título e URL não citam o fabricante; passa a depender
do snippet. É o comportamento correto: documento que não cita nem fabricante nem código em
lugar nenhum é legitimamente suspeito.

## 6. O que isto NÃO resolve

- **Página de fabricante em JavaScript.** `hydac.com/shop` é uma aplicação JS; o HTML estático
  tem pouco texto útil. Por isso as queries `filetype:pdf` vêm antes das que aceitam HTML — mas
  quando só sobra HTML, o conteúdo pode continuar magro.
- **Seguir o link do PDF dentro da página do produto.** A página do SKU costuma ter "Product
  information (PDF)". Segui-lo seria um mini-crawler — mais código, mais risco, e não dá para
  validar neste ambiente (o proxy bloqueia `catalog.hydac.com`). Fica proposto, não feito.
- **A prova final.** Isto tudo foi medido contra resultados reais de busca, mas **não** contra a
  Google CSE do usuário com a chave dele. A CSE pode ranquear diferente. A validação de verdade
  é rodar a ficha 4500063671.1188 de novo, sem PDF, e comparar.
