# AutoSpecAI — caderno de melhorias

Documento de trabalho da frente do **Rafael** (`rafhagmm`). Registra o que foi encontrado,
o que já foi feito e o que **não pode ser esquecido antes de dar a frente por encerrada**.

- Regras de negócio: [`docs/base-conhecimento/08b-autospec-contexto-negocio.md`](base-conhecimento/08b-autospec-contexto-negocio.md)
- Como o código funciona: [`docs/base-conhecimento/08-autospec-backend.md`](base-conhecimento/08-autospec-backend.md)
- Fronteiras com a refatoração: [`docs/refatoracao/TRABALHO_PARALELO.md`](refatoracao/TRABALHO_PARALELO.md)

---

## 🛑 NÃO FECHAR A FRENTE SEM RESOLVER

> Checklist obrigatório. Antes de declarar o AutoSpecAI concluído, passar por cada item.

- [ ] **Checkbox: `fill_save` falha em silêncio quando a IA não devolve o endereço da célula.**
      *Adiado a pedido do usuário em 2026-08-11 — precisa de execução real para decidir.*
      Detalhe em [P-01](#p-01) abaixo. **Este é o lembrete que o usuário pediu explicitamente.**
- [ ] Rodar o roteiro de `docs/ROTEIRO_DE_TESTE.md` na parte do AutoSpec
- [ ] `bash scripts/check.sh` verde
- [ ] Merge na linha oficial seguindo `TRABALHO_PARALELO.md` §6

---

## Achados em aberto

### <a id="p-01"></a>P-01 🔴 `fill_save`: checkbox falha em silêncio — **ADIADO, não esquecer**

`sigft/services/autospec.py`, em `fill_save`:

```python
clean = str(val).strip().upper()
if clean in info['options']:      # options = ["G25", "G27", "G29"]
    for o in info['options']: ws[o].value = None
    ws[clean].value = "X"
```

`val` é a **resposta da IA**. O código a trata como endereço de célula. Comportamento real,
verificado:

| A IA devolve | Acontece |
|---|---|
| `"G25"` | ✅ marca a célula certa |
| `"g25"` | ✅ marca (o `.upper()` cobre) |
| `"Vertical"` | ❌ **nada** — campo fica vazio, **sem aviso nenhum** |
| `"Sim"` | ❌ **nada**, sem aviso |

**Correção do diagnóstico original:** a pendência registrada no bootstrap dizia que isso
"quebraria". Não quebra — o `if clean in info['options']` protege. **Falha em silêncio**, que
para o usuário é pior: a ficha volta com o campo vazio e nada indica que a IA respondeu e a
resposta foi descartada.

**Por que não corrigi:** depende de saber o que o modelo devolve **hoje**, de verdade, para os
9 campos checkbox. Se ele já devolve `"G25"`, o conserto é só logar o descarte; se devolve o
rótulo (`"Vertical"`), é preciso mapear rótulo→célula, e esse mapa não existe (o `CONFIG_MAP`
guarda só as células). Chutar aqui troca um bug por outro.

**O que preciso de você:** rodar o AutoSpec numa ficha real que tenha checkbox pendente e me
mandar o log (ou o JSON que a IA devolveu). Com isso o conserto é direto.

> Zona: 🟢 `sigft/services/autospec.py`. Não encosta em nada do Luan.

---

### P-07 🔵 `analyze_sheet` abre o workbook sem `data_only=True`

`get_pmib_data` usa `data_only=True`; `analyze_sheet` não. Se a ficha tiver célula com
fórmula, `is_empty` enxerga o texto da fórmula (`"=A1"`) e considera preenchida.

**Cuidado:** não é um bug de uma linha. O `wb` de `analyze_sheet` é o mesmo que o `fill_save`
salva — e `data_only=True` faz o openpyxl **descartar as fórmulas ao salvar**. Corrigir exige
abrir duas vezes (uma para ler valores, outra para escrever) ou aceitar a limitação. Precisa
de decisão antes de código.

---

## Resolvido

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
