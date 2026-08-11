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

### P-02 🟡 Busca web: o passo 3 da cascata não existe

As regras de negócio (§4.2) descrevem **três** passos, sendo o terceiro o truncamento
progressivo do `texto_breve` (corta 4 caracteres do fim até achar documento ou atingir tamanho
mínimo). `retrieve_context` implementa só dois:

```python
queries = []
if cod_mat: queries.append(f'"{cod_mat}" {fab} datasheet specs')
queries.append(f"{txt_brv} {fab} datasheet specs")
```

Efeito: descrições longas e muito específicas ("BOMBA CENTRIFUGA MULTIESTAGIO 5CV 380V IP55")
tendem a não retornar nada, e o AutoSpec fica sem contexto web — cai só no manual local, ou em
nada. É provavelmente a causa mais comum de ficha voltando vazia.

**Decisão pendente:** implementar como descrito, ou trocar por uma estratégia melhor? Cortar
4 caracteres cegos pode partir a descrição no meio de uma palavra. Alternativa: remover o
último *token* a cada rodada, o que preserva o sentido.

---

### P-03 🟡 Formatos de imagem não são tratados (objetivo declarado em §6.1)

`PDFProcessor.extract_text` só distingue `.pdf` de "resto", e o resto vai para o BeautifulSoup
como se fosse HTML. Um `.tif`/`.png`/`.jpg` (catálogo antigo digitalizado, citado nas regras
de negócio como caso real) vira texto-lixo silenciosamente — ou nada.

O LlamaParse já faz OCR de imagem; hoje ele só é chamado quando `is_pdf` é verdadeiro.

---

### P-04 🟡 Rastreabilidade campo→fonte não existe

As regras (§3.4) pedem que a interface mostre **de onde cada dado veio**. Hoje o módulo junta
todo o contexto num blob (`--- WEB DOC ---` / `--- LOCAL DOC ---`), e a IA devolve só
`{campo: valor}`. O engenheiro vê a lista de fontes do lote, não a origem de cada valor —
então a revisão antes da homologação é mais cara do que precisaria.

Caminho possível: pedir à IA um campo `fonte` junto de cada resposta, e logar/gravar isso.
Mexe no prompt (`core/llm/prompts.py` → 🔴 **zona compartilhada**, exige commit isolado).

---

### P-05 🟡 Silêncio em falha de rede e de parsing

- `WebSearcher.search_and_download`: `except Exception: return []` — busca web que falhou é
  indistinguível de busca que não achou nada.
- `PDFProcessor.extract_text`: três `except ... pass` em cascata. Se o LlamaParse falhar por
  chave inválida, cai no PyPDF2 sem dizer nada; se o PDF for escaneado, o PyPDF2 devolve vazio
  e o documento some do contexto sem aviso.
- `generate_ai_response`: `except Exception as e: print(f"Erro IA: {e}")` — vai para o
  **stdout**, ou seja, a janela preta que ninguém olha. O CP 4.4 padronizou os logs pelo
  console da UI; este ponto ficou de fora.

O último é o mais barato de consertar e o de maior retorno.

---

### P-06 🔵 `analyze_sheet` varre até `ws.max_row`

```python
r = VARIAVEIS_SPECS["start_row"]     # 79
while r <= ws.max_row:
```

`max_row` no openpyxl conta linhas com **formatação**, não só com conteúdo. Numa ficha cujo
template tenha estilo aplicado até o fim, isso vira dezenas de milhares de iterações inúteis
por ficha. As regras de negócio dizem "linha 79 até a **última linha preenchida**".

Conserto natural: parar após N linhas consecutivas sem pergunta na coluna C.

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
