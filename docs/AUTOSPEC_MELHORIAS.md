# AutoSpecAI — caderno de melhorias

Documento de trabalho da frente do **Rafael** (`rafhagmm`). Registra o que foi encontrado,
o que já foi feito e o que **não pode ser esquecido antes de dar a frente por encerrada**.

- Regras de negócio: [`docs/base-conhecimento/08b-autospec-contexto-negocio.md`](base-conhecimento/08b-autospec-contexto-negocio.md)
- Como o código funciona: [`docs/base-conhecimento/08-autospec-backend.md`](base-conhecimento/08-autospec-backend.md)
- Fronteiras com a refatoração: [`docs/refatoracao/TRABALHO_PARALELO.md`](refatoracao/TRABALHO_PARALELO.md)

---

## 🛑 NÃO FECHAR A FRENTE SEM RESOLVER

> Checklist obrigatório. Antes de declarar o AutoSpecAI concluído, passar por cada item.

- [x] ~~Checkbox: `fill_save` falha em silêncio~~ — **RESOLVIDO em 2026-08-11**, ver R-09.
- [ ] Rodar o roteiro de `docs/ROTEIRO_DE_TESTE.md` na parte do AutoSpec
- [ ] `bash scripts/check.sh` verde
- [ ] Merge na linha oficial seguindo `TRABALHO_PARALELO.md` §6

---

## Achados em aberto

> Nenhum achado em aberto no momento. Os 8 mapeados na revisão de 2026-08-11 foram
> resolvidos — ver abaixo.

## Resolvido

### ✅ R-09 🔴 P-01: checkbox por RÓTULO, e descarte deixou de ser mudo *(2026-08-11)*

**O diagnóstico mudou depois de olhar a ficha real.** A pergunta não era "o que a IA
responde?" — era por que o prompt oferecia `['G25','G27','G29']`. Endereço de célula não diz
nada a um modelo de linguagem: mesmo um acerto era **chute entre 3 opções**. Não é um problema
de qualidade a ser medido, é defeito de projeto — e por isso deu para corrigir sem a execução
real que eu tinha pedido.

O rótulo legível está na própria planilha, ao lado da marcação. `_rotulos_do_checkbox` o lê nas
duas disposições existentes (à direita na mesma linha; na linha de cabeçalho acima, para os 2
grupos da linha 69), ignorando células que são marcação de OUTRO grupo — sem isso, varrer à
direita de `J69` alcança `P69` e devolve `"x"` como rótulo.

**Validado na ficha real: 20/20 rótulos extraídos, 0 falhas.** O prompt passou de
`(Opções: ['G25','G27','G29'])` para `(Escolha UMA: ['Vertical','Horizontal','Indiferente'])`.

`_resolver_celula_checkbox` aceita **endereço** (forma antiga, preservada), **rótulo** (sem
acento, sem caixa) e **rótulo dentro de frase** — só quando um único rótulo casa, para não
escolher no chute. E o que não casar agora **gera aviso**, com resumo no fim: a falha
silenciosa que era o coração do P-01 deixou de existir.

Ficha sem rótulo encontrável continua funcionando pelo endereço — compatibilidade total.

### ✅ R-10 🔵 P-07: leitura com `data_only`, escrita sem *(2026-08-11)*

Decisão do usuário: abrir o arquivo duas vezes. `analyze_sheet` mantém o workbook SEM
`data_only` (é o que `fill_save` salva — `data_only=True` descartaria as fórmulas na gravação)
e abre um segundo, COM `data_only=True`, só para leitura. Sem isso, `is_empty` enxergava o
texto da fórmula (`"=A1"`) e tratava como preenchida uma célula cujo valor calculado é vazio.

Fallback: planilha nunca aberta no Excel não tem valor em cache e `data_only=True` devolve
`None` em toda fórmula — nesse caso volta à leitura direta, melhor que tratar a ficha inteira
como vazia.

### ✅ R-04 🟡 P-02: cascata de busca web ganhou o passo 3 *(2026-08-11)*

As regras de negócio (§4.2) descrevem 3 passos; o código tinha 2. Descrição longa e específica
não retorna nada no Google, e a ficha ficava sem contexto web — provável causa nº 1 de ficha
voltando vazia. `_montar_queries_busca` implementa o truncamento progressivo **por PALAVRA**
(decisão do usuário; cortar 4 caracteres, como o texto original sugeria, parte o token no meio
— `"PVF100-4"` → `"PVF10"` — e produz query pior que a anterior), com piso de 2 tokens e o
fabricante preservado em todas as rodadas (é ele que ancora o filtro anti-intruso).

Validado contra a ficha real `4500063671.0662`, que gera 6 queries degradando bem:

```
1. CONJUNTO REPARO PARA BOMBA 3527528 PVF100-4 NBR Hydac datasheet specs
2. CONJUNTO REPARO PARA BOMBA 3527528 PVF100-4 Hydac datasheet specs
...
6. CONJUNTO REPARO Hydac datasheet specs
```

Corrigido junto um defeito que só apareceu ao mexer aqui: o `break` da cascata disparava
quando a busca **devolvia arquivos**, não quando algum arquivo **virava contexto**. Três PDFs
ilegíveis encerravam a cascata e as queries mais genéricas nunca eram tentadas.

### ✅ R-05 🟡 P-03: imagens vão para o OCR *(2026-08-11)*

`.tif/.tiff/.png/.jpg/.jpeg/.bmp/.webp` passam pelo LlamaParse (que faz OCR) em vez de caírem
no BeautifulSoup como se fossem HTML. Sem chave do LlamaParse, o documento é ignorado **com
aviso**, em vez de virar texto-lixo em silêncio. O `_sufixo_para_url` também deixou de errar
com URL de PDF com query string (`.../datasheet.pdf?download=1`) e passou a olhar o
`Content-Type` da resposta.

### ✅ R-06 🟡 P-04: rastreabilidade campo→fonte *(2026-08-11)*

O prompt passou a pedir `{ID: {"valor": ..., "fonte": ...}}`, e o `process_queue` lista a
origem de cada campo no console — as regras §3.4 pedem isso para o engenheiro revisar antes de
homologar.

**Compatibilidade, que era o risco real desta mudança:** `_normalizar_resposta_ia` aceita as
DUAS formas. Se o modelo ignorar a instrução (modelo mais fraco, prompt truncado), a resposta
antiga `{campo: valor}` continua funcionando e só a fonte se perde. O **contrato de retorno de
`generate_ai_response` não mudou** — `fill_save` recebe o mesmo dicionário achatado de sempre e
não foi tocado.

Dependentes atualizados junto (era o cuidado pedido): a fixture congelada
`tests/fixtures/prompts/autospec_prompt.txt` (regenerada a partir da saída real, diff conferido
linha a linha), `tests/test_llm_prompts_snapshot.py`, `tests/test_llm_prompts.py`.

> ⚠️ `core/llm/prompts.py` é **zona compartilhada** — a mudança foi num commit isolado, com
> mensagem explícita e registro em `PENDENCIAS.md`, conforme `TRABALHO_PARALELO.md` §4.

### ✅ R-07 🟡 P-05: falhas deixaram de ser silenciosas *(2026-08-11)*

- Busca web: `except Exception: return []` mudo → log de erro com tipo e query. Cota diária do
  CSE estourada era indistinguível de "não achei nada".
- `PDFProcessor`: os três `except ... pass` agora dizem qual etapa falhou e por quê; PDF sem
  camada de texto (escaneado) é avisado explicitamente.
- `generate_ai_response`: `print(f"Erro IA: {e}")` ia para o **stdout** — a janela preta que
  ninguém olha. Agora vai pelos callbacks, como o CP 4.4 padronizou.
- Documento web descartado por texto insuficiente e resultado barrado pelo filtro anti-intruso
  passaram a aparecer no console.
- `" -> Consultando Gemini..."` virou `" -> Consultando a IA..."`: o provedor vem da seleção do
  usuário e a mensagem envelheceria igual à do guard de chave.

### ✅ R-08 🔵 P-06: varredura para na última linha preenchida *(2026-08-11)*

O laço ia até `ws.max_row`, que no openpyxl conta linha com **formatação**. Na ficha real as
perguntas acabam na 103 e `max_row` é 132; num template formatado até o fim, dezenas de
milhares de iterações inúteis por ficha. Agora encerra após
`MAX_LINHAS_VAZIAS_SEGUIDAS = 25` linhas sem pergunta — folgado para atravessar um bloco de
layout no meio da lista, curto para não varrer a planilha inteira. Seguro porque as perguntas
são numeradas em sequência (ver Anexo B do doc de contexto de negócio).

### ✅ R-01 🔴 `get_pmib_data` casava com o material errado *(2026-08-11)*

A comparação era `if code_suffix in val_pmib` — substring do sufixo de 4 dígitos contra o
código inteiro, **prefixo de contrato incluído**. Como `PREFIXO_CONTRATO` (`"4500063671"`)
contém ele mesmo sequências de 4 dígitos, **7 sufixos** (`0006`, `0063`, `0636`, `3671`,
`4500`, `5000`, `6367`) casavam com **qualquer** linha da planilha — e a função devolvia
descrição e código de material da **primeira linha**, de um material diferente.

Como o retorno alimenta o contexto RAG **e** as queries de busca web, a IA pesquisava e
preenchia a ficha inteira com base no material errado, em silêncio. É literalmente o cenário
que as regras de negócio (§1.3) classificam como pior que campo vazio.

Corrigido comparando sufixo com sufixo, via `core.excel.pmib_codes` (implementação única do
CP 1.2). De quebra conserta um **falso negativo**: quando o Excel guarda o código como número,
`4500063671.1050` vira o float `4500063671.105` e a busca antiga falhava — `normalize_pmib`
restaura o zero à direita. Casos legítimos preservados: apóstrofo do Excel, coluna só com o
sufixo, código no meio de texto livre. 22 testes em `tests/test_autospec_match_pmib.py`.

### ✅ R-02 🟡 Google CSE sem timeout *(2026-08-11)*

`search_and_download` chamava `requests.get(...)` sem `timeout`, então uma chamada pendurada
travava o módulo inteiro por tempo indefinido. `_download_file`, logo abaixo, já usava
`timeout=15`. Alinhado ao mesmo valor.

### ✅ R-03 🟡 Guard de chave preso ao Gemini *(2026-08-11)*

`__init__` exigia `gemini_key` mesmo quando o provedor resolvido era OpenRouter — quem
configurasse só `OPENROUTER_API_KEY` não conseguia usar o módulo. Agora o guard resolve o
provedor da tarefa (mesma cadeia do `get_llm`, resolvida uma vez só) e cobra a chave daquele
provedor. A mensagem é uma só, com provedor e chave interpolados, sem nenhum provedor
hardcoded no texto — decisão tomada olhando para a migração para OpenRouter.
16 testes em `tests/test_autospec_guard_chave.py`.
