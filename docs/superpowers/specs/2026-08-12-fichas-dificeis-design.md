# Fichas difíceis — o que vai quebrar depois que a 1188 passou

**Data:** 2026-08-12 · **Frente:** AutoSpecAI (Rafael) · **Origem:** console do 1º teste bem-sucedido

---

## 1. Ponto de partida

A ficha 4500063671.1188 (sensor HYDAC) passou: 28 de 29 campos preenchidos, 21 deles com URL de
origem. Mas ela é o caso **fácil** — fabricante conhecido, código de peça limpo, datasheet
público, página indexada.

Este documento mapeia o que o `_STATUS_PMIB` real também contém, e que só apareceria quebrado na
frente do usuário. **Cada item foi reproduzido rodando o código**, não deduzido.

## 2. O que o console do teste bem-sucedido já denunciou

| # | Linha do console | Problema |
|---|---|---|
| C-1 | `tmp1wgju9r5.pdf: 6 pagina(s), 6 lida(s)` | nome do arquivo TEMPORÁRIO. É a linha que o usuário precisa ler para decidir se confia no resultado, e ela não diz de qual documento se trata |
| C-2 | `Download recusado (HTTP 403)` | o site do fabricante bloqueou o robô. Escrito assim parece defeito do SIG-FT |
| C-3 | 29 faltantes → 28 origens | o 29º (`var_row_88`, "10 - PRECISAO") **não aparece em lugar nenhum**. A IA não respondeu e ninguém ficou sabendo |

## 3. Modos de falha reproduzidos

Rodando `_termos_do_filtro` e `_montar_queries_busca` com entradas realistas:

```
CASO                          TERMOS DO FILTRO                 1a QUERY
fabricante VAZIO              ['1/2']                          1/2 datasheet filetype:pdf
fabricante DIVERSOS           ['DIVERSOS', '6205']             DIVERSOS 6205 datasheet
razao social so ruido         ['INDUSTRIA','COMERCIO','LTDA']  ...
tudo vazio                    []                               (nenhuma)
```

| # | Falha | Dano |
|---|---|---|
| **F-1** | **Sem âncora, o filtro aceita TUDO.** `_termos_do_filtro('','','')` devolvia `[]`, e lista vazia significa "não filtre" | **Grave.** A proteção §4.3 falhava *aberta*, justamente na ficha em que menos se pode confiar. Catálogo de concorrente entraria como contexto e o engenheiro homologaria dado de outra peça |
| **F-2** | `DIVERSOS`, `N/A`, `SEM MARCA` viravam nome de fabricante | Query inútil e âncora que aprova qualquer página que diga "diversos" |
| **F-3** | `INDUSTRIA E COMERCIO LTDA` virava os termos `['INDUSTRIA','COMERCIO','LTDA']` | Qualquer página industrial brasileira contém "industria" — âncora sem valor. **Defeito introduzido por mim** na correção anterior: o fallback "se limpar tudo, use o original" é certo para BUSCAR e errado para FILTRAR |
| **F-4** | `1/2` e `110` entravam como código de peça | `1/2 datasheet filetype:pdf` virou a **primeira** query da cascata, queimando cota da CSE numa busca sem sentido |
| **F-5** | Termo numérico casava por substring | `123` casava dentro de `123456` em página irrelevante |
| **F-6** | `response.content` sem teto de tamanho | Catálogo de centenas de MB (existem) trava o app na máquina do usuário, sem mensagem. O `timeout=15` não protege: o download *avança*, só não acaba |

## 4. Decisões

### 4.1 Sem âncora, não busca (F-1)

Quando não há fabricante reconhecível **nem** código de peça, a busca web **não acontece**, e o
console diz por quê e o que fazer (preencher o fabricante ou anexar o manual).

Alternativa rejeitada: buscar assim mesmo e confiar na IA para conferir. O prompt já pede isso
(instrução 2), mas transferir a decisão para o modelo troca uma garantia por uma probabilidade —
e o custo do erro é uma ficha da Itaipu com dado de outra peça.

**Campo vazio é ruim; campo preenchido com dado de outro material é pior.** É o que a §4.3 já
dizia, agora aplicado ao caso degenerado.

Basta **uma** das duas âncoras: identificador sem fabricante serve, fabricante sem identificador
serve.

### 4.2 Buscar e filtrar são decisões diferentes (F-2, F-3)

Duas funções em vez de uma:

| Função | Usada para | Se sobrar vazio |
|---|---|---|
| `_nome_curto_fabricante` | montar a **query** | devolve o original — nome ruim busca melhor que nome nenhum |
| `_tokens_ancora_fabricante` | montar o **filtro** | devolve `[]` — âncora ruim é pior que âncora nenhuma, porque parece que tem |

Confundir as duas foi exatamente o que produziu F-3.

### 4.3 O que é código de peça (F-4)

Uma de duas coisas: mistura letra e dígito (`PVF100-4`, `DN50`, `IP55`), **ou** é numérico com
4+ dígitos (`3527528`, `6205`). Medida solta raramente passa de 3 dígitos, e é isso que exclui
`1/2`, `3/4` e `110`.

### 4.4 Fronteira de palavra para termo curto (F-5)

Termo puramente numérico, ou com menos de 4 caracteres, casa só com fronteira de palavra.

Isto resolve **os dois lados de uma tensão**: `123` deixa de casar dentro de `123456`, e marcas
curtas legítimas — `3M`, `GE`, `NSK`, `FAG` — deixam de precisar ser descartadas por serem
curtas. A primeira tentativa cortava tokens de até 2 caracteres e apagou `3M` inteiro; o teste
pegou.

### 4.5 Teto de download (F-6)

`stream=True` com corte em 40 MB, o temporário é apagado no aborto, e o console explica.

## 5. Verificação

`tests/test_autospec_fichas_dificeis.py`, 30 testes. Ciclo red-green: 22 falharam antes da
implementação, 30 passam depois. Suíte completa: 1644 passed, 3 skipped.

Reconferido que o caso real não regrediu:

```
termos: ['HYDAC', '3332066', 'CS1320-A-0-0-0-1/-000', 'CS1320']
1a query: "3332066" HYDAC datasheet
resultados reais que passam: 2 de 2
```

## 6. Não resolvido

- **Site que bloqueia robô (403).** Agora explica, mas não contorna. Contornar seria fingir ser
  navegador — muda a natureza do que o programa faz, e é decisão do usuário, não minha.
- **Densidade de fonte.** Na 1188, 21 campos técnicos saíram de **uma** página HTML de 3.677
  chars. É plausível para uma tabela de especificações, mas concentra risco: um erro naquela
  página vira 21 campos errados. O console mostra a origem por campo — a conferência humana
  continua sendo a rede.
- **Documento em idioma fora de PT/EN.** O glossário do retrieval só cobre PT→EN. Datasheet em
  alemão ou chinês passa pelo BM25 sem expansão.
