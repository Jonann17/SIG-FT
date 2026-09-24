# AutoSpec: a IA lê o documento inteiro, e prova o que respondeu

**Data:** 2026-09-24 · **Frente:** AutoSpecAI (Rafael)
**Origem:** comparação do usuário entre o AutoSpec e o AMP (Gemini 3.5 flash-lite, PDF inteiro)
nas fichas 0084, 0086, 0088 e 0094. O AMP achou 78 informações; o AutoSpec, 43, e errou 3.

> *"Na maioria dos casos o AMP conseguiu um resultado melhor, o que preocupa na forma que esta
> tarefa está sendo feita pelo Autospec."*

---

## 1. O que os quatro casos mostraram — medido, não suposto

A hipótese de partida era o OCR. **Não é.** Os seis PDFs enviados têm camada de texto, o
PyMuPDF lê 100% das páginas, e os logs confirmam `[PyMuPDF]` em todos — o OCR nem foi chamado.
O texto extraído é limpo: `Storage Temperature -20 °C to 85 °C` (0084), `Accuracy ±0.5% of
full scale` (0086), `ø 36` e `36x250` (0088) estão lá, legíveis.

As perdas vêm de quatro etapas **depois** da leitura, cada uma criada para evitar alucinação, e
que nestes quatro casos custaram muito mais acerto do que o erro que evitavam:

| # | Etapa | O que fez | Onde apareceu | Reproduzido aqui |
|---|---|---|---|---|
| 1 | **Corte do documento** | cada PDF local é cortado em 60.000 caracteres antes de tudo (web: 50.000), e o recorte por relevância (RAG) manda no máximo 24.000 à IA | 0094: 177.273 chars lidos, 60.041 indexados, 23.259 enviados — **87% do manual nunca chegou à IA**. 0086: 3 documentos, 28,5 mil chars, acima do teto | sim, pelo código e pelo log |
| 2 | **Prompt** | todo campo técnico é `[ESTRITO]`: "se não houver dados, deixe vazio". Proíbe a dedução fundamentada que o AMP usou | 0088: material do contato, do corpo, normas, uso, tipo construtivo; 0094: aplicação, acoplamento, nº de pás | sim, pelo texto do prompt |
| 3 | **Lastro por número** | exige que o número apareça no documento **com unidade**, e a palavra da resposta escrita no documento | 0088: `36 mm` e `250 mm` **certos** reprovados (o desenho cota `ø 36` e `250` sem "mm"; o único mm do PDF é `20 mm`). `OUTROS` reprovado por não estar escrito no PDF | sim: mesma mensagem do log, palavra por palavra |
| 4 | **Corretor de conversão** | trata `Hz` como rotação (1 Hz = 60 rpm) e "corrige" | 0094: a IA leu **2860 rpm (certo)**; o app gravou **3600 rpm** "de 60 hz". Os dois únicos erros do AutoSpec nas quatro fichas são do app, não da IA | sim: `('3600 rpm', '2860 -> 3600 rpm (de 60 hz)')` |

E um quinto, fora da coleta: na 1ª rodada da 0088 a chamada da IA estourou o tempo três vezes
(`ReadTimeout`, 120 s cada — os 6 min 12 s do log) e a ficha foi **contada como sucesso** e
salva sem nada.

## 2. Abordagens consideradas

**A. A IA lê o PDF inteiro, nativamente (escolhida).** O arquivo vai para o modelo como
anexo (OpenRouter `file`, Gemini `inline_data`); o modelo vê texto, tabela, desenho cotado e
gráfico, do jeito que o AMP faz. Para cada campo devolve o valor **e a prova**: documento,
página e o trecho copiado. O app confere a prova contra o texto que ele mesmo extraiu.
*Contra:* depende de o modelo aceitar PDF; arquivo gigante não cabe numa chamada.

**B. Texto inteiro, sem corte.** Mantém a extração local, mas manda o documento todo.
*A favor:* funciona igual em qualquer provedor. *Contra:* o modelo não vê desenho nem gráfico
(a vazão e a pressão de um ventilador costumam estar numa curva).

**C. B + segunda passada nativa só para os vazios.** Melhor cobertura, mas duas chamadas,
mais espera numa etapa que já leva 4–6 minutos, e dois caminhos para manter.

**Escolha: A, com B como rede automática.** A é o que o AMP faz e o que venceu a comparação;
B entra sozinho quando o modelo não aceita PDF, quando o arquivo passa do limite, ou quando o
provedor recusa o anexo. C é YAGNI enquanto A não mostrar lacuna.

## 3. Desenho

### 3.1 Leitura: nada é cortado

- Os documentos são lidos **inteiros**, página a página, com marcador `[pág. N]` no texto. O
  corte de 60 mil / 50 mil caracteres sai.
- O recorte por relevância (RAG) só entra quando o texto total passa de **300 mil
  caracteres** (~75 mil tokens) — um manual de mil páginas, não um datasheet de seis.
- O texto extraído continua existindo mesmo quando a IA lê o PDF: é contra ele que a prova é
  conferida.

### 3.2 Envio: PDF nativo quando dá, texto quando não dá

| Provedor | PDF nativo? |
|---|---|
| Gemini direto | sim (todo Gemini lê PDF) |
| OpenRouter | sim para famílias que leem PDF nativamente (`google/gemini*`, `anthropic/claude*`, `openai/gpt-4o/4.1/5`, `o3/o4`), com `file-parser` em `engine: native` — nunca cai no OCR pago do OpenRouter sem avisar |
| Endpoint da empresa | não (texto) |

- Limite por chamada: **15 MB e 500 páginas** somados. O que não couber vai como texto,
  na mesma chamada.
- Se o provedor **recusar** o anexo (erro que não seja timeout), a ficha é refeita pelo
  caminho de texto e o log diz isso. Timeout não cai para texto: dobraria a espera.
- Interruptor `ler_pdf_nativo` na instância, como os outros (`usar_retrieval`, `exigir_lastro`).

### 3.3 O prompt pede a prova

Cada campo volta como `{valor, tipo, fonte, pagina, trecho, justificativa}`:

- `tipo`: `documento` (copiado), `calculo` (convertido — o trecho traz o original) ou `deducao`;
- `trecho`: o pedaço do documento, **copiado literalmente**, de onde o valor saiu;
- regras novas explícitas: temperatura de **operação** × do **processo** × de **armazenamento**
  são coisas diferentes (o erro da 0084); o documento pode trazer outros modelos ou outro
  produto (a 0088 veio com dois fusíveis diferentes); campo com lista de opções responde uma
  delas; resposta na unidade que o campo pede.

### 3.4 A conferência passa a ser pela prova

Vale para os campos da tabela de especificações (`var_row_*`), como o lastro de hoje.

| O valor tem medida? | A prova | Resultado |
|---|---|---|
| sim | trecho achado no documento, e todo número do valor sai dele (literal, ou conversão refeita pelo app) | **grava** |
| sim | trecho achado, número não sai dele | refaz a conta **só dentro do trecho**; se não der, **vazio** com o motivo |
| sim | trecho não achado | regra antiga, no documento inteiro; se não passar, **vazio** |
| sim | trecho numa página sem texto (imagem, lida pela IA no PDF nativo) | **grava + aviso** "conferir" |
| sim | `tipo = deducao` | **vazio** — número só com documento |
| não (texto, material, norma, opção) | trecho achado | **grava** (código como `IP65` precisa estar no trecho) |
| não | sem trecho, ou dedução com justificativa | **grava como DEDUÇÃO**, com a justificativa |

- **Dedução é para texto; número só com documento.** O número de uma norma (`IEC 60269-4`) não
  conta como medida. `IP65`, `NEMA 4X`, `DN50` contam: são propriedade do modelo, e foi
  exatamente um número deduzido que o AMP alucinou (pressão máxima de trabalho, 0084).
- O **recorte por modelo** continua valendo: trecho que só existe na linha de OUTRO modelo do
  mesmo datasheet é reprovado.
- Por que isto resolve a 0088: a prova de `36 mm` é `ø 36` — o 36 está no trecho, sem unidade
  que o contradiga. O lastro antigo procurava "36 mm" no documento inteiro, e o desenho não
  escreve "mm".

### 3.5 Correções pontuais

- `Hz` sai da tabela de rotação; `1/min`, `min⁻¹`, `r/min`, `U/min`, `tr/min` entram como rpm.
- O corretor não reescreve número que está **literalmente** no documento — se está lá, não
  foi erro de conta.
- Falha da IA (timeout, erro de rede, resposta ilegível) vira **falha da ficha**: nada é salvo,
  o resumo do lote conta ❌ e diz o motivo.
- Tempo limite do AutoSpec: **300 s**, com **1** nova tentativa (antes: 120 s, 2 novas
  tentativas). O documento inteiro é mais texto para ler.
- "Origem dos dados" deixa de listar campo que voltou vazio.

### 3.6 Rastreabilidade na ficha

Célula preenchida por **dedução** ou lida de **página-imagem** ganha um comentário do Excel
(`AutoSpec: dedução técnica. <justificativa>` / `AutoSpec: lido de página sem texto,
conferir`). O log some; o arquivo fica. Cor azul de sempre para tudo que a automação escreveu.

## 4. O que sai, o que fica

| Sai | Fica |
|---|---|
| corte de 60 mil / 50 mil por documento | PyMuPDF (texto local, para conferir a prova e para o caminho de texto) |
| teto de 24 mil caracteres no recorte | RAG + glossário, só acima de 300 mil caracteres |
| lastro por número no documento inteiro como regra principal | ele mesmo, como rede quando o trecho não é achado |
| `Hz` como rotação | corretor de conversão, restrito ao trecho |
| — | LlamaParse, só no caminho de texto de PDF escaneado (no nativo, quem lê a imagem é o modelo) |

## 5. O que dá para provar aqui, e o que só na máquina do usuário

**Aqui (contêiner sem acesso ao OpenRouter e sem chave):** montagem da requisição com anexo
(dublê de HTTP), queda para texto quando o provedor recusa, conferência por prova contra o
texto real dos PDFs enviados (0084, 0086, 0088), correções de rpm, contagem de falha.

**Só lá:** a resposta real do modelo lendo o PDF. O critério de aceite é rodar de novo as
quatro fichas e refazer a comparação com o AMP.

## 6. Riscos

- **Custo:** o PDF inteiro custa mais tokens que 24 mil caracteres. No Gemini 3 Flash, um
  datasheet de 6 páginas sai por frações de centavo; o manual de 166 páginas, por volta de
  US$ 0,05–0,10. Aceitável frente a uma ficha que volta pela metade.
- **Proxy corporativo** barrando corpo grande: vira erro de rede, que cai para o texto.
- **Privacidade:** o texto desses mesmos PDFs já ia para o provedor; o anexo acrescenta as
  imagens das páginas. Nenhuma nuvem nova entra no caminho.
