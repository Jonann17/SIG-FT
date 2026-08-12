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
- [x] ~~`bash scripts/check.sh` verde~~ — verde desde 2026-08-11
- [x] ~~Merge na linha oficial~~ — feito em 2026-08-11 (commit `75e0988`)

---

## Achados em aberto

> Nenhum achado em aberto no momento. Os 8 mapeados na revisão de 2026-08-11 foram
> resolvidos — ver abaixo.

## Resolvido

### ✅ R-12 🔴 Frente 2 (camada 1): leitura local de PDF, com prova de que foi lido inteiro *(2026-08-11)*

**Decisões do usuário:** `1a` — só a camada local por enquanto; `2a` — leitura incompleta
avisa e segue.

**O problema que isto fecha.** A única aferição de "consegui ler" era:

```python
if t and len(t) > 100:
```

Cem caracteres. Um datasheet de 40 páginas do qual se leu **uma linha da capa** passava nesse
teste e entrava no contexto como se fosse o documento inteiro. A IA respondia "não encontrei"
para tudo, e nada no log dizia que o problema tinha sido a **leitura**, não o documento.

**PyMuPDF como primeira camada** (`_ler_pdf_local`). Preferido ao PyPDF2 por dois motivos:
preserva a ordem de leitura do layout — o PyPDF2 entrega texto corrido e **desmancha tabelas**,
e datasheet é quase só tabela — e entrega o texto **página a página**, que é o que permite
medir cobertura. Wheel pura, instala pelo `pip` sem binário de sistema, o que importa porque o
`SIG-FT.bat` só resolve o que o `pip` resolve.

**`RelatorioLeitura`** mede e o console mostra:

```
manual.pdf: 5 pagina(s), 5 lida(s) (100%), 594 chars [PyMuPDF]

misto.pdf: 5 pagina(s), 3 lida(s) (60%) — LEITURA INCOMPLETA. Sem texto nas
paginas: 3, 5. Provavelmente escaneadas; precisariam de OCR. Seguindo com o
que foi lido — confira os campos que dependiam dessas paginas.
```

Página com menos de 40 caracteres não conta como lida (número de página solto não é
conteúdo); cobertura abaixo de 80% marca o documento como incompleto. As páginas faltantes são
numeradas **1-based**, como o usuário conta.

**Inversão de privacidade, de brinde:** a nuvem (LlamaParse) era tentada **primeiro** sempre
que houvesse chave — o arquivo inteiro subia para a LlamaCloud mesmo quando o PDF tinha camada
de texto e podia ser lido aqui, de graça e sem sair da máquina. Agora a ordem é
**PyMuPDF → PyPDF2 → LlamaParse**, e ao recorrer à nuvem o log diz explicitamente que
*"o arquivo SAI da rede"*. Alinhado à decisão de privacidade registrada acima.

**O que continua faltando (consciente):** página realmente escaneada não é lida sem OCR. O
relatório diz quais são — é com esse número na mão que se decide se vale pagar o custo de
implantação do Tesseract (binário de sistema) ou do Docling (~500 MB + torch). 11 testes,
com os PDFs construídos no próprio teste pelo PyMuPDF (nenhum binário entra no repositório).

### ✅ R-11 🔴 Frente 1: a query se auto-sabotava *(2026-08-11)*

**Causa raiz de "o script não acha o que eu acho no Google em 5 segundos".**
O CSE do usuário estava correto (web inteira, sem sites) — o problema era a query.

O script mandava a **descrição inteira, em português**:

```
CONJUNTO REPARO PARA BOMBA 3527528 PVF100-4 NBR Hydac datasheet specs
```

O Google trata cada palavra como termo. `CONJUNTO`, `REPARO`, `PARA`, `BOMBA`, `NBR` são
prosa PT-BR e **não existem num datasheet da Hydac, escrito em inglês** — cada uma empurrava o
documento certo para baixo. E o truncamento do P-02 cortava do FIM, descartando primeiro
`PVF100-4` e `3527528`, os tokens que valem, e preservando a prosa.

`_identificadores` isola os tokens que parecem código de peça ou modelo (contêm dígito, 3+
caracteres) e a cascata passou a começar por eles — fabricante + identificador, curto, igual
ao que uma pessoa digita à mão. A prosa virou **fallback**, não a primeira tentativa:

```
1. Hydac 3527528 PVF100-4 datasheet     <- a query "humana"
2. Hydac PVF100-4 datasheet             <- só o modelo, mais reconhecível
3+. a prosa truncada (comportamento antigo, para descrição sem identificador)
```

Junto, duas decisões do usuário:

- **`gl=br`/`hl=pt` removidos.** Pediam ao Google resultado BRASILEIRO em PORTUGUÊS —
  exatamente o viés que derruba datasheet estrangeiro. O navegador dele, onde acha em 5
  segundos, não tem esse viés.
- **`num` de 3 para 10.** O CSE cobra a MESMA cota (1 query) para 3 ou 10 resultados; pedir 3
  jogava fora 70% do que já estava pago.

**Cache de busca** (`busca_web_cache.json`, TTL 7 dias, gitignored, mesmo padrão dos caches de
catálogo de modelo): guarda query → resposta crua da CSE. Reprocessar o mesmo lote — o normal
quando se ajusta um manual e roda de novo — deixou de queimar a cota inteira. Guarda as URLs,
não os arquivos: caminho de temporário não sobrevive à execução, mas a URL sim, e é ela que
custou cota.

24 testes novos. Fica em aberto medir, com o usuário, se a taxa de acerto subiu de fato —
é o próximo passo de validação real.

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

---

## 🔒 Decisão de arquitetura — postura de privacidade (2026-08-11)

**Decidido pelo usuário (Rafael).** Vale para todo o trabalho de melhoria daqui em diante.

### Alvo: cenário 2 — só a IA interna da empresa

Nenhum conteúdo de datasheet vai para Google, OpenRouter, Anthropic ou qualquer provedor
público. A IA usada é exclusivamente o endpoint OpenAI-compatível da empresa, já previsto em
`config.PROVIDER_OPENAI_COMPAT` (`EMPRESA_LLM_BASE_URL` + `EMPRESA_LLM_API_KEY`).

### Realidade de hoje: a chave ainda não existe

Por isso o cenário 2 **não pode ser o único caminho** — o módulo ficaria inutilizável até a
empresa liberar a chave. O combinado é uma **cadeia com degradação automática**:

```
1. IA interna da empresa (openai_compat)          ← alvo, preferido sempre que der
       │  falha: chave ausente, base_url ausente, endpoint fora do ar, erro na chamada
       ▼
2. OCR local + só os TRECHOS relevantes para a nuvem   ← fallback automático
```

**O que "falha" significa, explicitamente:** `EMPRESA_LLM_API_KEY` ausente ou vazia,
`EMPRESA_LLM_BASE_URL` ausente ou vazia, endpoint inalcançável, ou qualquer erro na chamada
depois dos retries da política da tarefa.

**Regras que o fallback tem de respeitar:**

1. **Nunca silencioso.** Cair para o cenário 3 muda para onde o dado vai — o usuário precisa
   ver no console, em `nivel="warn"`, qual caminho está sendo usado e por quê.
2. **Mesmo no fallback, o mínimo sai.** O cenário 3 pressupõe OCR local (sem LlamaCloud) e
   envio apenas dos trechos recuperados, nunca do documento inteiro. O fallback reduz a
   proteção, não a abandona.
3. **A escolha é registrada por ficha**, junto da rastreabilidade campo→fonte do P-04, para
   auditoria posterior.

### Consequências para o desenho das melhorias

- O **OCR tem de ser local** nos dois cenários — é o que elimina o LlamaCloud, que hoje é a
  maior exposição (recebe o arquivo inteiro).
- **Embeddings/seleção de trechos também locais** — no cenário 2 por coerência, no cenário 3
  por necessidade.
- A busca web (Google CSE) é assunto separado: ela expõe a *query*, não o datasheet. Fica
  fora desta decisão, mas vale confirmar com a empresa se a descrição do material pode ir
  para o Google.
