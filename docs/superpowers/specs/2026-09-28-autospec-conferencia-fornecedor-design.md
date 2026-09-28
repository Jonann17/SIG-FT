# AutoSpec: a IA confere as respostas do fornecedor contra o datasheet

**Data:** 2026-09-28 · **Frente:** AutoSpecAI (código do Rafael, pedido do Luan)
**Status:** implementado, validado pelo usuário numa ficha real em 2026-09-28 e publicado na 1.1.1.

> *"Algumas características técnicas respondidas pelo fornecedor são duvidáveis, e muitas vezes
> por preguiça ou desleixo eles respondem que determinada característica técnica não se aplica, o
> que não é verdade, e essa característica está nitidamente no datasheet que eu forneci do item.
> [...] Se estiver escrito não se aplica ou suas variações, você verifica se ela realmente não se
> aplica. Se estiver algum dado que responde a pergunta e você encontrar alguma divergência com o
> mesmo dado do datasheet, você apenas traz isso no log de saída, mas não sobrescreva excluindo a
> informação preenchida pelo fornecedor."*

---

## 1. Como é hoje

- `analyze_sheet` só põe em `missing` a célula **vazia** ou com o marcador `FORNECER`
  (`is_empty`). Tudo o que o fornecedor escreveu, inclusive "Não se aplica", fica de fora
  e nunca é olhado.
- É a regra de negócio §3.1 do `08b`: *"Se estiver com 'Não aplicável', 'N/A' ou qualquer valor
  real, o script não toca."*
- Ficha 100% preenchida pelo fornecedor termina em `"Ficha já está completa."`, sem nem ler o
  datasheet.

## 2. Decisões do usuário (2026-09-28)

| # | Pergunta | Decisão |
|---|---|---|
| 1 | "Não se aplica" com o valor no datasheet | **Grava o valor do documento**, em azul, **só com a prova conferida**. A resposta original do fornecedor fica num **comentário da célula**. O arquivo do fornecedor nunca é alterado (sai o `_completed`) |
| 2 | Escopo | **Só a tabela de especificações** (linha 79 em diante). Os campos fixos ficam de fora: dimensões e pesos são da embalagem, e os campos de preservação/descarte são boa prática, não dado de datasheet |
| 3 | Uma chamada ou duas | **Chamada separada, enxuta**, com um **interruptor na tela** (ligado por padrão). *"Não podemos perder o que já temos, que seria a qualidade com que está respondendo agora."* O preenchimento fica byte a byte igual |

Divergência de valor preenchido: **só no log**, como o pedido diz. Nada é gravado.

## 3. Abordagens consideradas

**A. Chamada separada, enxuta (escolhida).** O preenchimento não muda (mesmo prompt, mesma
chamada, mesma chave de cache), e a conferência é uma chamada própria com prompt próprio.
*Contra:* a conferência reenvia o documento; numa ficha que tem as duas coisas, o custo de IA
sobe algo como 50–70% (entrada igual à do preenchimento, saída bem menor).

**B. Tudo numa chamada só.** Economiza a releitura do documento. *Contra:* mexe no prompt do
preenchimento, que foi calibrado contra o AMP em 2026-09-24, mistura dois formatos de resposta
no mesmo JSON e acopla as falhas. Descartada pelo usuário.

**Onde a A economiza token:**

1. Só chama a IA quando **há resposta do fornecedor na tabela de especificações E há
   documento**. Ficha só com campo vazio: nenhum custo a mais.
2. **Resposta curta:** `confere` e `nao_consta` voltam numa palavra; só a divergência (e o
   "não se aplica" errado) traz a prova. Token de saída é o mais caro.
3. **Cache** de resposta, igual ao do preenchimento: reprocessar a mesma ficha com o mesmo
   documento não gasta nada.
4. **Interruptor** "Conferir as respostas do fornecedor contra o datasheet" na tela: lote em
   que só se quer preencher desliga e não paga.

Possibilidade futura, não feita (não dá para medir daqui): o cache implícito de prefixo dos
provedores. O Gemini direto já manda o PDF antes do texto, e aí a segunda leitura do mesmo PDF
pode sair com desconto; o OpenRouter manda o texto antes. Medir no painel **Gastos de IA**
antes de mexer na camada de IA.

## 4. Desenho

### 4.1 O que é "não se aplica" — `ficha_layout.e_nao_se_aplica(valor)`

Uma implementação só, ao lado de `e_marcador_de_faltante` (o outro "valor que não é resposta").
Compara depois de tirar acento, caixa, espaço e pontuação de borda.

- **Formas exatas** (curtas, só sozinhas na célula): `N/A`, `NA`, `N.A.`, `N/D`, `ND`, `N.D.`,
  `NSA`, `-`, `--`, `---` (e os traços tipográficos).
- **Frases** (sozinhas ou seguidas de um complemento, ex. *"Não se aplica ao modelo"*):
  não se aplica, não aplicável, não aplica, não é aplicável, no aplica, no se aplica,
  no aplicable, not applicable, does not apply, não informado, não disponível, sem informação,
  não consta, not available, not informed, a definir, a confirmar.
- **Não são** "não se aplica" (são resposta de verdade): `Não`, `Nenhum`, `Não possui`, `0`,
  `Sem revestimento`. Uma resposta assim é conferida como qualquer valor (divergência só no log).

As outras três listas de "N/A" do projeto (`analyzer.FORBIDDEN_NA_STRINGS`,
`upload_conditions.campos_em_branco_na_origem`, `traducao_respostas._NAO_HA`) ficam como
estão: unificar mudaria nota de ficha e upload, e está fora deste pedido. Vai para o
`PENDENCIAS.md`.

### 4.2 Coleta — `analyze_sheet`

No mesmo laço das especificações variáveis: a linha **com pergunta e com resposta** (a que hoje
é pulada) vai para `self.respostas_do_fornecedor`:

```python
{"var_row_85": {"desc": "7 - TENSAO NOMINAL (...)", "ref": "M85",
                "resposta": "Não se aplica", "nao_se_aplica": True}}
```

Zerado no começo de cada `analyze_sheet`. A tupla de 7 elementos que o método devolve **não
muda** (há teste e chamador que desempacotam 7).

### 4.3 A chamada — `AutoSpecCore.auditar_respostas_do_fornecedor(...)`

- **Documento:** a MESMA política do preenchimento (PDF nativo quando o modelo lê PDF, texto
  inteiro, recorte só acima de 300 mil caracteres). Para isso o bloco que decide o envio sai de
  `generate_ai_response` para um método próprio, `_preparar_envio`, que os dois usam — extração
  pura, sem mudar o que o preenchimento manda.
- **Prompt:** `prompts.montar_autospec_auditoria(...)`, novo, em `core/llm/prompts.py` (zona
  compartilhada: commit isolado). `montar_autospec` não é tocado.
- **Resposta pedida:**
  `{"ID": {"situacao": "confere" | "diverge" | "nao_consta", "valor_documento", "tipo", "fonte",
  "pagina", "trecho", "justificativa"}}` — a prova só em `diverge`. "Não se aplica" com o valor
  no documento é `diverge`. Dedução e conhecimento geral são proibidos.
- **Cache:** o mesmo arquivo do preenchimento; a chave é o prompt (+ os bytes dos anexos), que
  já é outra.
- **Recusa do PDF** cai para o texto; **timeout não** (mesma regra do preenchimento).
- **Falha** (IA fora, formato errado): aviso no log e segue. No lote, a ficha que só tinha
  conferência conta como falha; a que também tinha preenchimento é salva normalmente.
- **Sem documento nenhum:** não chama a IA; aviso no log.

### 4.4 A decisão, campo a campo

Pura onde dá (`services/autospec_auditoria.py`: ler a resposta, comparar valores, montar o
log); o que precisa da conferência pela prova fica no `AutoSpecCore`, reaproveitando
`_conferir_pela_prova`, `achar_trecho`, `valor_sai_do_trecho` e `contexto_do_modelo`.

**Resposta "não se aplica" (e afins):**

| A IA disse | Acontece |
|---|---|
| `nao_consta`, ou valor vazio / também "N/A" | fica o do fornecedor; conta como "confirmado" |
| valor por dedução, ou sem trecho | fica o do fornecedor; apontamento descartado, com o motivo no log |
| valor com trecho, e `_conferir_pela_prova` aprova (trecho existe na linha do modelo, número sai dele, ou conta refeita) | **grava o valor do documento em azul** + comentário: *o fornecedor respondeu 'N/A', o documento traz (fonte, pág.): "trecho"* |
| trecho só em página sem texto, ou prova reprovada | fica o do fornecedor; descartado, com o motivo |

**Resposta com valor:**

| A IA disse | Acontece |
|---|---|
| `confere` / `nao_consta` | só conta |
| `diverge` sem valor ou sem trecho | descartado |
| trecho da linha de OUTRO modelo, ou que não existe no documento | descartado |
| valor do documento não sai do trecho citado | descartado |
| fornecedor e documento dizem o mesmo em outra unidade/forma (`24 Vcc` × `24 VDC`, `0,5 kW` × `500 W`, mesmo texto sem acento/caixa) | conta como `confere` — o app refaz a conta |
| sobrou | **divergência no log**, com os dois valores, a fonte, a página e o trecho. **Nada é gravado** |
| trecho em página sem texto (PDF-imagem) | divergência no log, marcada "confira na página" |

A equivalência numérica é simétrica: todo número de um lado sai do outro (literal ou por
conversão refeita pelo `autospec_unidades`). `220 V` × `220/380 V` continua divergência: o
documento diz mais do que o fornecedor.

### 4.5 No lote

- Ficha **com** campo vazio: preenche como hoje; depois confere; o que a conferência grava
  entra no MESMO `fill_save` (um `_completed` só). As notas da conferência somam às do
  preenchimento.
- Ficha **sem** campo vazio e **com** resposta do fornecedor: coleta os documentos (local +
  web, como hoje) e confere. Se gravou algo → `_completed`. Se não → **nenhum arquivo**, o log
  diz que a ficha do fornecedor não foi alterada; no resumo do lote, sucesso ("conferida, nada
  gravado"). Documentos duvidosos entram na conferência humana como sempre. Sem documento
  nenhum lido, a ficha conta como **pulada** ("sem documento para conferir as respostas do
  fornecedor").
- Ficha sem campo vazio e sem resposta (ou interruptor desligado): `"Ficha já está completa."`,
  como hoje.
- **2ª passada** (documentos aprovados na conferência humana): confere também — ela regrava o
  `_completed`, e sem a conferência os "N/A" corrigidos na 1ª passada se perderiam.

### 4.6 O log

```
 -> Conferindo 18 resposta(s) do fornecedor contra o(s) documento(s)...
 2 resposta(s) "nao se aplica" do fornecedor ESTAO no documento: gravei o valor do
 documento (em azul), e a resposta original ficou no comentario da celula:
      · 7 - TENSAO NOMINAL: fornecedor 'N/A' -> documento '24 Vcc' (datasheet.pdf, pag. 2)
 1 divergencia entre a resposta do fornecedor e o documento. NADA foi alterado na ficha; confira:
      · 12 - GRAU DE PROTECAO: fornecedor 'IP54' x documento 'IP65' (datasheet.pdf, pag. 1)
        trecho: "Degree of protection IP65"
 3 resposta(s) "nao se aplica" conferida(s): o documento nao traz o dado, ficou o do fornecedor.
 11 resposta(s) conferem com o documento; 1 o documento nao traz.
```

Sem travessão em texto de log e de tela (`tests/test_texto_da_ui.py`).

### 4.7 A tela

Em `sigft/app/views/autospec.py`, acima do botão INICIAR: caixa de seleção **"Conferir as
respostas do fornecedor contra o datasheet"**, marcada, com uma linha cinza explicando o que ela
faz e que gasta uma chamada de IA a mais por ficha com resposta do fornecedor. O valor vai para
um atributo comum pelo `command` da caixa (thread principal) e o `_novo_core()` o repassa ao
core (`core.auditar_fornecedor`), para os dois workers. Ler a variável do Tk de dentro da thread
do worker seria acesso fora da thread do Tk.

## 5. O que NÃO muda

- O prompt, a chamada, a chave de cache e a conferência do preenchimento.
- Nenhuma célula com valor do fornecedor é gravada, em caso nenhum. Só "não se aplica" e afins,
  e só com prova conferida.
- Os campos fixos e os checkboxes.
- O contrato de `analyze_sheet` (7 elementos) e o de `generate_ai_response` (`{campo: valor}`).

## 6. Testes

- `e_nao_se_aplica`: as formas, as frases com complemento, e as respostas que NÃO são.
- `analyze_sheet`: coleta as respostas da tabela, com a marca de "não se aplica", sem tirar
  nada do `missing`.
- Prompt: pede a prova só na divergência, proíbe dedução, diz que unidade/tradução não é
  divergência, diz que "N/A" com valor é divergência, termina na lista.
- Leitura da resposta: envelope, situação escrita de outro jeito, item sem prova.
- Equivalência: `24 Vcc` × `24 VDC`, `0,5 kW` × `500 W`, `IP54` × `IP65`, texto igual sem
  acento, `220 V` × `220/380 V`.
- Decisão: cada linha das duas tabelas da §4.4.
- Chamada: sem resposta ou sem documento não chama a IA; recusa do PDF cai para o texto;
  timeout não; falha vira aviso; cache.
- Lote: ficha completa conferida (com e sem gravação); gravação mesclada no mesmo `fill_save`;
  interruptor desligado = comportamento de hoje; falha da conferência não derruba o
  preenchimento; 2ª passada confere; **nenhuma resposta com valor chega ao `fill_save`**.
- `_preparar_envio`: os testes de `tests/test_autospec_documentos.py` continuam verdes sem
  mudança (é a prova de que o preenchimento manda o mesmo).
- Tela, por AST: a caixa existe, o `command` grava o atributo comum, o `_novo_core` o repassa.

## 7. O que só a máquina do usuário prova

Este contêiner não alcança a IA. A resposta real do modelo ao prompt novo só aparece rodando
uma ficha de verdade: uma ficha do fornecedor com um "Não se aplica" que está no datasheet e
um valor divergente, com o datasheet anexado. Roteiro: `docs/ROTEIRO_DE_TESTE.md`, Etapa 3b.
