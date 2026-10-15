# AutoSpec AI — Contexto de Negócio e Regras de Engenharia

> ⚠️ **Onde o código mora hoje** (atualizado em 2026-08-28)
>
> Este documento foi escrito antes da refatoração e descreve o comportamento do
> módulo, que continua valendo. Mas os CAMINHOS mudaram:
>
> | O que o texto abaixo chama de | Está hoje em |
> |---|---|
> | `autospec_backend.py` | `sigft/services/autospec.py` + os 4 módulos `autospec_*.py` ao lado |
> | a tela | `sigft/app_qt/views/autospec.py` |
>
> A lógica de negócio descrita aqui continua válida; o que mudou foi onde ela vive. Camadas novas que este texto não menciona: `sigft/core/excel/` (cabeçalho de planilha, código PMIB, gravação com retry), `sigft/core/llm/` (cliente de IA multi-provedor), `sigft/core/rpa/` (portal e motor), `sigft/core/callbacks.py` (o protocolo UI↔serviço).

> **O que é este documento.** Enquanto `08-autospec-backend.md` descreve **como o código
> funciona**, este descreve **por que ele existe e quais regras ele precisa obedecer**.
> Fornecido pelo usuário (Rafael) em 2026-08-11, a partir do levantamento feito na concepção
> do módulo. É a fonte de verdade das **regras de negócio** — quando o código divergir daqui,
> o código é que está errado (ou a divergência precisa ser uma decisão registrada).
>
> ⚠️ **Leia o Anexo A no fim**: nem tudo descrito aqui está implementado hoje, e algumas
> partes descrevem tecnologias que já saíram do projeto.

---

## 1. Propósito

### 1.1 Contexto operacional

Módulo de automação integrado ao fluxo de **PDM** (Padrão de Descrição de Materiais) e ao
**SIG-FT**, no ambiente de engenharia de manutenção do Consórcio Itaipu / CMI / GE Vernova.

### 1.2 A dor real

Catalogar e especificar sobressalentes industriais (válvulas, bombas, motores, instrumentação,
componentes elétricos e mecânicos) exige preencher extensas **Fichas Técnicas Padrão** em
Excel. Manualmente isso é lento, repetitivo, caro e sujeito a erro humano — e dado
despadronizado contamina compras, planejamento, almoxarifado, logística reversa e
conformidade normativa (NR 12).

### 1.3 Por que RAG, e não LLM puro

LLMs puros **alucinam severamente** sobre códigos industriais específicos: inventam dimensões,
pesos, tensões nominais, normas.

> **A regra que orienta todo o módulo:** em engenharia de alta confiabilidade,
> **um dado incorreto é pior do que um campo vazio.**

Por isso o AutoSpec é um **agente de pesquisa e extração baseado em evidências**, não um
gerador de texto: ele consulta datasheets, catálogos, desenhos e normas reais.

---

## 2. Ecossistema de dados

```
                  ┌────────────────────────────────────────┐
                  │          Status PMIB (Excel)           │
                  │   Controle Mestre / Extração SAP       │
                  └───────────────────┬────────────────────┘
                                      │ Cruza via Sufixo PMIB
                                      ▼
┌──────────────────────┐    ┌───────────────────┐    ┌──────────────────────────┐
│  Ficha Técnica (.xlsx│───►│    AutoSpec AI    │◄───│ Documentos de Suporte    │
│  "Ficha Técnica Padr"│    │ (Motor Híbrido    │    │ (Manuais PDF, TXT, TIFF, │
└──────────────────────┘    │  Web + Local)     │    │  Web Scraping via CSE)   │
                            └─────────┬─────────┘    └──────────────────────────┘
                                      │
                                      ▼
                            ┌───────────────────┐
                            │ <Ficha>_completed │
                            │ (Dados em Azul)   │
                            └───────────────────┘
```

### 2.1 Planilha "Status PMIB" (cadastro mestre / SAP)

Tabela da verdade e controle de fluxo do cadastro no PMIB.

**Vínculo:** o nome do arquivo da ficha carrega o padrão numérico (ex.:
`1234567890.0042.xlsx`); o script extrai o **sufixo** (`0042`) e busca a linha correspondente.

Dados extraídos: **CÓDIGO PMIB** (chave), **DESCRIÇÃO / Descrição Complementar** (requisitos
técnicos adicionais) e **CÓDIGO DO MATERIAL** (código do item no catálogo/SAP, quando houver).

### 2.2 A Ficha Técnica Padrão

Aba rigorosamente nomeada **`Ficha Técnica Padrão`**. Duas regiões:

**1. Campos fixos de metadados (células nominais)**

- *Informações gerais:* texto breve (`H6`), unidade (`H8`), tipo de fabricação (`F10/F12`),
  fabricante (`L10`), origem (`S6/S8`), tipo (`S10/S12`).
- *Armazenamento/embalagem:* dimensões (`H17`, `H19`, `H21`), pesos líquido/bruto
  (`P17`, `P19`), intempéries (`Q21/S21`), posição (`G25/G27/G29`), proteção
  (`S25/S27/S29`), nocivo (`E31/E33`), empilhamento (`J35`).
- *Transporte, manutenção e descarte:* embalagem de transporte (`M42`), procedimento de
  elevação (`M45`), preservação (`M52`), limpeza (`M54`), ferramentas (`M56`), legislação
  (`M63`), descarte (`M65`).
- *Periculosidade / logística reversa:* (`E69/J69` e `P69/T69`).

**2. Especificações variáveis (linha 79 até a última preenchida)**

- Coluna **C**: nome do parâmetro / pergunta técnica.
- Coluna **M**: resposta técnica a preencher.

### 2.3 Documentos de referência

- **Locais:** PDFs de fabricantes, arquivos de texto, desenhos digitalizados (TIFF/PDF).
- **Web:** documentos técnicos públicos, baixados sob demanda via Google Custom Search.

---

## 3. Regras de negócio e governança

### 3.1 Preservação absoluta de dados humanos

O script **NUNCA** sobrescreve o que um analista ou engenheiro já preencheu.

Uma célula só é considerada pendente se estiver **vazia** (`None`), **em branco** (`""`) ou se
o texto **iniciar com** a instrução do formulário `"FORNECER..."` (ex.: `FORNECER DIMENSÕES`).

Se estiver com `"Não aplicável"`, `"N/A"` ou qualquer valor real, **o script não toca**.

> **Refinado em 2026-09-28, por decisão do Luan** — só na tabela de especificações (linha 79
> em diante):
>
> | O fornecedor escreveu | O que o AutoSpec faz |
> |---|---|
> | "Não se aplica" e afins (N/A, não aplicável, não informado, N/D, `-`) | a IA procura no datasheet. **Com a prova conferida** (trecho no documento, na linha do modelo certo, número saindo dele), grava o valor do documento em azul, e a resposta original fica num **comentário da célula**. Sem prova, ou só por dedução: não toca |
> | Um valor | **continua sem tocar.** Se diverge do datasheet, a divergência vai **só para o log** |
>
> Motivo, nas palavras dele: o fornecedor responde "não se aplica" por desleixo, e a
> característica está nitidamente no datasheet. `"Não"`, `"Nenhum"`, `"Não possui"` são
> resposta, não "não se aplica". O arquivo do fornecedor nunca é alterado: tudo sai no
> `_completed`. Spec: `docs/superpowers/specs/2026-09-28-autospec-conferencia-fornecedor-design.md`.

### 3.2 A dicotomia de preenchimento

| Tipo | Definição | Se NÃO achar no manual | Exemplos |
|---|---|---|---|
| **`[ESTRITO]`** | Propriedades físicas, dimensionais e elétricas do modelo exato | **DEVE deixar vazio (`""`)**. Tolerância zero à alucinação | Dimensões (CxLxA), peso líquido/bruto, curvas de pressão, tensão nominal, desenhos |
| **`[INFO TÉCNICA PADRÃO]`** | Requisitos de manuseio, armazenagem, segurança e boas práticas de almoxarifado | **DEVE DEDUZIR** a partir de normas e das características do tipo de equipamento | Preservação, limpeza, descarte, embalagem de transporte, proteção, posição de armazenamento, unidade, tipo (reparável/não reparável) |

> **Refinado em 2026-09-24** (comparação do usuário com o AMP, fichas 0084/0086/0088/0094):
> dentro do `[ESTRITO]`, **MEDIDA e TEXTO passam a ter regras diferentes.**
>
> | Campo `[ESTRITO]` | Sem o dado escrito no documento |
> |---|---|
> | **Medida** — dimensão, peso, tensão, corrente, pressão, vazão, rotação, temperatura, potência, grau de proteção (IP/NEMA) | continua **vazio**. Nenhum número entra por dedução |
> | **Texto** — material, norma, aplicação, uso, tipo construtivo, montagem, acoplamento | pode entrar por **DEDUÇÃO técnica fundamentada**, marcada: justificativa no log e **comentário na célula** para o engenheiro conferir antes de homologar |
>
> Por que a linha passa aí: o AMP preencheu material do contato, material do corpo, normas e
> uso por dedução, e isso foi contado como acerto; o único erro dele nas quatro fichas foi um
> **número** deduzido (pressão máxima de trabalho). O número de uma norma (`IEC 60269-4`) não
> conta como medida. Chave para desligar: `autospec_evidencia.PERMITIR_DEDUCAO_EM_TEXTO`.
>
> E o "achou no manual" passou a ser **provado**: cada valor volta com o trecho do documento
> de onde saiu, e o app confere que o trecho existe e que o número sai dele — ver
> `08-autospec-backend.md`, quadro de 2026-09-24.

### 3.3 Restrições estruturais e de tipo

- **`empilhamento` (`J35`)** é estritamente numérico — quantidade máxima de caixas. Se a IA
  responder *"Máximo 5 caixas"*, grava-se apenas o inteiro `5`. Sem número, a célula fica
  vazia (`None`).
- **Checkboxes:** desmarcar todas as alternativas do grupo e escrever `"X"` apenas na
  vencedora.

### 3.4 Rastreabilidade e auditoria humana

- **Destaque visual:** todo valor escrito pela automação recebe fonte **azul (`#0000FF`)**.
  O que já era humano permanece preto.
- **Logs de transparência:** a interface mostra a URL exata ou o nome do arquivo local de onde
  cada dado veio, para o engenheiro revisar antes de homologar.
- **Preservação do arquivo fonte:** nunca salva no original — gera
  `<nome_original>_completed.xlsx`.

---

## 4. Pipeline lógico

```
[ Usuário monta Fila na tela (Qt) ]
         │
         ▼
[ Extração de Código PMIB + Busca no Status PMIB (Desc + Cod Material) ]
         │
         ▼
[ Ingestão Local: PDF lido por página (PyMuPDF), INTEIRO; OCR só se não houver texto ]
         │
         ▼
[ Busca Web em Cascata (Google CSE + Filtro Anti-Intruso por Fabricante) ]
         │
         ▼
[ Envio à IA: o PRÓPRIO PDF quando o modelo lê PDF; senão o texto inteiro ]
         │
         ▼
[ Prompt com Separação de Regras: ESTRITO (medida x texto) vs INFO PADRÃO, pedindo a PROVA ]
         │
         ▼
[ Conferência pela prova (trecho existe, número sai dele) ]
         │
         ▼
[ Parsing JSON + Sanitização Regex (Empilhamento) + Escrita Excel em Azul + comentário ]
```

Até 2026-09-23 a ingestão cortava cada documento em 60 mil caracteres e o contexto enviado
em 24 mil (RAG); ver `docs/superpowers/specs/2026-09-24-autospec-leitura-integral-design.md`
para os números que motivaram a mudança.

### 4.1 Isolamento de contexto (fila)

Para que o manual de uma "Válvula Reguladora" não contamine o contexto de uma "Bomba
Centrífuga", a fila é estruturada como `[{ 'sheet': path, 'refs': [manuais] }]` e **cada ficha
é processada numa sessão isolada** de LLM e de leitura documental.

### 4.2 Busca web em cascata (fallback progressivo)

1. **Mais específico:** `"{codigo_material}" {fabricante} datasheet specs` (aspas = busca exata).
2. **Intermediário:** `"{texto_breve}" {fabricante} datasheet specs`.
3. **Truncamento:** se não achar, corta progressivamente 4 caracteres do fim do `texto_breve`
   até encontrar ao menos 1 documento confiável ou atingir um tamanho mínimo.

### 4.3 Filtro "anti-intruso"

Para o Google não devolver catálogo de concorrente (ex.: manual da Rexroth quando o material é
Hydac), o script valida **título, URL e snippet** antes de autorizar o download: o
**fabricante** ou o **código do material** precisa estar presente.

---

## 5. Tecnologias

- **Frontend:** a tela Qt `sigft/app_qt/views/autospec.py` (tema escuro, fila interativa com deleção individual; até 2026-10-15 era CustomTkinter).
- **Planilhas:** `openpyxl` (fórmulas, valores puros via `data_only=True`, escrita estilizada
  com `Font(color="0000FF")`).
- **Web search:** Google Custom Search JSON API.
- **Parsers documentais:** `llama-parse` (OCR profundo, tabelas de engenharia),
  `PyPDF2` (fallback local para PDF vetorial), `BeautifulSoup4` (HTML limpo).

---

## 6. Objetivos típicos de evolução

1. **Robustez de OCR e formatos:** tratar imagens técnicas (`.tif`, `.tiff`, `.png`, `.jpg`)
   de catálogos antigos digitalizados.
2. **Eficiência de rede e tokens:** otimizar o envio de contexto para não estourar limite de
   token nem inflar latência.
3. **Resiliência a layouts:** lidar com variações de cabeçalho e coordenadas entre versões da
   Ficha Técnica.
4. **Qualidade do scraping:** tratar sites de fornecedor com renderização dinâmica (JS/SPA).

---

# Anexo A — Onde este documento e o código divergem (auditado em 2026-08-11)

Levantamento feito lendo `sigft/services/autospec.py` linha a linha contra as seções acima.
**Não corrija nada só por causa desta tabela** — ela existe para que ninguém leia o documento
como se fosse descrição do código de hoje.

| Seção | O documento diz | O código faz | Natureza |
|---|---|---|---|
| §5 | Orquestração via `langchain` / `langchain-google-genai` | LangChain foi **removido no CP 3.2**; hoje é `LLMClient` (`sigft/core/llm/`) | Documento desatualizado — o projeto evoluiu |
| §5 | "Modelo principal: Gemini 2.5 Flash / Pro" | Modelo vem de `config.LLM_TASKS["autospec"]` (`gemini-3-flash-preview`), com `LLM_MODELOS_HOJE` (`gemini-3.1-pro-preview`) como baseline | Documento desatualizado |
| §4.2 passo 3 | Truncamento progressivo do `texto_breve` até achar documento | **Não implementado.** `retrieve_context` monta 2 queries e para na primeira que retorna algo | **Funcionalidade descrita e ausente** |
| §6.1 | Tratar `.tif`, `.tiff`, `.png`, `.jpg` | `PDFProcessor` só distingue `.pdf` de "resto"; o resto vai para o BeautifulSoup como se fosse HTML — uma imagem vira texto-lixo | **Gap conhecido** (é um objetivo declarado, não uma regressão) |
| §2.2 | Coluna C = pergunta, M = resposta | ✅ Confere (`VARIAVEIS_SPECS`: `pergunta_col_idx=3` → C, `resposta_col_idx=13` → M) | OK |
| §3.1 | Pendente só se vazio ou **iniciar com** "FORNECER" | ✅ Confere (`is_empty` usa `.startswith("FORNECER")`) | OK |
| §3.3 | `empilhamento` extrai só o inteiro; sem número, `None` | ✅ Confere (`re.search(r'\d+', ...)`) | OK |
| §3.4 | Fonte azul, clone `_completed`, nunca salva no original | ✅ Confere | OK |
| §3.4 | "Logs de transparência: a interface exibe a URL exata ou o nome do arquivo local de onde cada dado foi recuperado" | Parcial: `retrieve_context` coleta `sources` (URLs) e o contexto marca `--- WEB DOC ---` / `--- LOCAL DOC ---`, mas **não há vínculo campo→fonte**. O engenheiro vê a lista de fontes do lote, não de onde saiu cada valor | **Divergência de grau** — ver `docs/AUTOSPEC_MELHORIAS.md` |
| §4.3 | Filtro anti-intruso valida título, URL e snippet | ✅ Confere — mas basta **um** dos termos casar em **um** dos três campos (`break` no primeiro match) | OK, com ressalva de rigor |

---

# Anexo B — O que a ficha real ensinou (`4500063671.0662`, POWER PACKS / Hydac)

Levantado em 2026-08-11 a partir de uma ficha real fornecida pelo usuário. Segundo ele,
**todas as fichas seguem este mesmo formato** — o que varia é a quantidade e o tipo das
características técnicas do bloco final, conforme o **PDM** (grupo do material no PMIB).

## B.1 Geometria confirmada

| | |
|---|---|
| Abas | `Ficha Técnica Padrão` (alvo) + `Planilha1` |
| Extensão da planilha | `max_row=132`, `max_column=23`, **129 células mescladas** |
| Cabeçalho fixo | linhas 2 a 76 |
| Especificações variáveis | **linhas 79 a 103** nesta ficha (25 perguntas) |
| Depois da última pergunta | **29 linhas vazias até `max_row`** ← origem do P-06 |

`max_row` maior que a última linha preenchida é a **regra, não a exceção**: o template
carrega formatação além do conteúdo. Por isso a varredura precisa parar por contagem de
linhas sem pergunta, e não em `ws.max_row`.

## B.2 As perguntas são numeradas e auto-descritivas

```
79   1 - APLICACAO (Indicar a aplicação do item ex.: Fixação...)
80   2 - MATERIAL (Indicar o material do item (ex.: Borracha...))
...
103  25 - CERTIFICADO (Indicar o tipo de certificado necessá...)
```

Duas consequências boas:

- A numeração sequencial confirma que um vão grande significa **fim da lista**, não lacuna —
  é o que torna o critério do P-06 seguro.
- O texto da pergunta **já traz a instrução e um exemplo**, e é ele que vai para o prompt
  como `desc`. O modelo recebe um enunciado rico sem que o código precise construir nada.

## B.3 Estrutura de checkbox — marca numa célula, rótulo na vizinha

**Este é o achado que resolve o P-01 no papel.** Em 7 dos 9 grupos, o rótulo legível está na
célula imediatamente à direita da célula de marcação:

| Campo | Célula da marca → rótulo |
|---|---|
| `tipo_fabricacao` | `F10`→"Série", `F12`→"Especial" |
| `origem` | `S6`→"Brasil ou Paraguai", `S8`→"Outros" |
| `tipo` | `S10`→"Reparável", `S12`→"Não reparável" |
| `sujeito_intemperies` | `Q21`→"Sim", `S21`→"Não" |
| `posicao_armazenamento` | `G25`→"Vertical", `G27`→"Horizontal", `G29`→"Indiferente" |
| `protecao` | `S25`→"Sem necessidade", `S27`→"Raios Ultravioletas", `S29`→"Eletrostática" |
| `nocivo` | `E31`→"Não contém agentes nocivos", `E33`→"Prejudicial…" |

Os **2 restantes** têm o rótulo na linha **68**, acima da linha de marcação (69):

| Célula da marca | Rótulo |
|---|---|
| `E69` | `D68` = "Classe I - Perigoso" |
| `J69` | `H68` = "Classe II – Não perigoso" |
| `P69` | `O68` = "Não se aplica" |
| `T69` | `S68` = "Aplica" |

**Por que importa:** hoje o prompt manda a IA escolher entre `['G25','G27','G29']` — endereços
de célula, que não significam nada para um modelo de linguagem. O natural é ele responder
`"Horizontal"`. Com este mapa, dá para oferecer os RÓTULOS no prompt e traduzir a resposta de
volta para a célula. Ver P-01 em `docs/AUTOSPEC_MELHORIAS.md`.

## B.4 Convenção de nome de arquivo

`4500063671.0662__POWER_PACKS_98.xlsx` — prefixo de contrato, ponto, sufixo de 4 dígitos, dois
underscores, descrição. Confirmado que `pmib_codes.extract_pmib_code` extrai `'0662'` deste e
das variantes (`… - POWER PACKS.xlsx`, `…_completed.xlsx`, `….xlsx`).

## B.5 Outras observações

- **`empilhamento` (`J35`) pode conter TEXTO.** Nesta ficha, um humano escreveu
  `"não empilhar"`. As regras dizem que o campo é numérico e o código extrai o inteiro com
  regex — mas como a célula já está preenchida, `is_empty` a considera preenchida e o módulo
  não encosta. Comportamento correto; vale saber que o dado real nem sempre é número.
- **`texto_breve_material` (`H6`) vem com espaço duplo e sobra no fim**
  (`'CONJUNTO REPARO PARA BOMBA 3527528  PVF100-4 NBR  '`). A montagem de query normaliza via
  `.split()` desde o P-02 — antes isso ia cru para o Google.
- **A ficha de exemplo está 100% preenchida**: `analyze_sheet` detectou **0 campos faltantes**.
  Boa contraprova de que o `is_empty` não gera falso positivo (nada foi marcado como pendente
  numa ficha completa).
