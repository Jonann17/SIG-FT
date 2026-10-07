---
tags: [plano, lista-de-precos, handoff]
status: pronto-para-execucao (regra de deteccao definida em 31/08/2026)
criado: 2026-08-31
destinatario: outra sessao de chat / desenvolvedor do SIG-FT
---

# Plano — Aba de Listas de Preços na Mapeadora

> [!warning] Documento de trabalho, nao conhecimento permanente
> Contem numeros e situacoes de uma data especifica. O que descreve **como o processo
> funciona** mora no nucleo do cofre (`01` a `06`).


> [!important] Atualização de 01/10/2026 — o código mudou
> A lista de preços passou a ter DCC próprio, **`PB021`** (revisão do ITAIPU-REF-0013), no
> lugar de `código da lista + sequencial` (`PB020-01`). Isso **simplifica a seção 3**: a
> detecção pode ser primeiro **pelo código** (`PB021`), com a descrição (`PRECOS` /
> `VALORIZADA`) só para o legado `PB020-0x`, que convive até as listas serem reemitidas.
> A aba já existe na mapeadora como **Lista de preços Follow-up** (16 linhas, todas `PB020-0x`
> em 01/10). Ver [[Lista de Precos]] e [[Plano - Sistema de Gestao v2]].

> [!info] Este documento e um hand-off
> Foi escrito para ser executado por **outra sessão de chat** ou por um desenvolvedor
> que não participou do levantamento. Ele e auto-contido: contexto, estado atual,
> desenho, critérios de aceite e as dúvidas que precisam ser respondidas antes de
> codar. Não e preciso ler o resto do cofre para executar — mas os links ajudam.

---

## 1. Contexto mínimo

### O que é uma Lista de Preços
No projeto de modernizacao de Itaipu (contrato **4500063671**), cada sistema emite uma
**Lista de Sobressalentes** aprovada pela **EN.DT** (engenharia). Depois, uma segunda
lista — a **Lista de Preços**, também chamada Tabela com Preços Unitarios — e emitida no
**Aconex** e aprovada pela **SM.DT** (manutenção). Ela existe para validar o preço
unitario de cada item **sem depender da nota fiscal**, o que antecipa em meses todo o
ciclo de aprovação das fichas técnicas.

Base contratual: ET Geral `6047-20-T0018-P R1`, Capítulo 18 —
*"Após aprovada a Lista de Peças de reposicao, a CONTRATADA deve apresentar uma tabela
com preços unitarios para cada item, garantindo o fornecimento por no mínimo 10 anos
após a emissão do CAP."*

Base de processo: ata **AR/EN.DT/001/2026** de 23/06/2026, que separou formalmente as
duas listas.

Detalhe completo em [[Lista de Precos]] e [[Ata AR-EN.DT-001-2026 - As Duas Listas]].

### Por que isso trava trabalho
A **[[Secao - Valorizacao|valorização]]** da ficha técnica só pode ser feita depois que a
lista EN.DT está aprovada e a lista de preços existe. Hoje **584 de 1219 fichas (47,9%)**
estão valorizadas. E ninguém consegue responder, sem abrir o Aconex documento por
documento: *quais listas de preço existem, em que revisão, e quais ficaram defasadas
porque a lista de sobressalentes foi revisada depois*.

### O problema, em uma frase
> As Listas de Sobressalentes tem uma planilha mapeadora que descobre listas novas e
> agrega o status de cada uma. **As Listas de Preços não tem equivalente.**

---

## 2. Estado atual

### A mapeadora
`Box/CMI - Consórcio Itaipu/11 - Ger. Engenharia/15 - PDM/SOBRESSALENTES - PMIB/
Mapeamento Listas de Sobressalentes.xlsx`

Três abas hoje:

| Aba | Conteudo |
|---|---|
| **`Acompanhamento Sobressalente`** | a principal — **94 listas x 35 colunas**. Cabeçalho em **duas linhas** (linha 1 = grupos `GERAL` / `FINANCEIRO` / `PMIB`; **linha 2 = os nomes das colunas**); dados a partir da **linha 3** |
| `Dropbox` | lista de validação de `SITUACAO NO PMIB` (7 valores) |
| `Atividades Pendentes` | recorte de listas que precisam de ação (8 colunas) |

Colunas da aba principal que este plano usa:
`N° DOCUMENTO ITAIPU` · `N° DOCUMENTO CMI` · `ULTIMA REVISAO EMITIDA` ·
`STATUS DA REVISAO` · `STATUS REAL` · `DESCRICAO` · `ESPECIFICACAO TECNICA` ·
`CAPITULO` · `RESPONSAVEL` · `PROCUREMENT` · `EVENTOS DE PAGAMENTOS RELACIONADOS` ·
`VALORIZACAO` · `FICHAS EXISTENTES`

Ver [[Mapeamento das Listas de Sobressalentes]].

### O módulo do SIG-FT
Repo: **https://github.com/luanccozer/SIG-FT** (a copia no Box está desatualizada).

Módulo alvo: **Gestão PMIB** — `sigft/services/pmib_manager.py`,
tela em `sigft/app/views/pmib_manager.py`.
Doc de comportamento: `docs/base-conhecimento/11-pmib-manager-backend.md`.

O que ele **já faz hoje**, e que este plano reaproveita quase inteiro:

1. carrega o export do **Aconex DocManager** (histórico de revisões; colunas
   `No. do Documento`, `Tracking ID`, `Current`, `Titulo`, `Especialidade`, ...);
2. varre uma pasta raiz procurando `*_STATUS_PMIB.xlsx`;
3. `_buscar_rdspp_mais_recente(codigo, df_api)` — acha o código em `No. do Documento`,
   pega o `Tracking ID`, procura a versão com mesmo Tracking ID e `Current = True`,
   devolve o `No. do Documento` novo;
4. `_renomear_arquivo_status_pmib(...)` — renomeia o arquivo para o código novo;
5. `_ler_status_pmib(...)` — lê cada `_STATUS_PMIB` com `dtype=str`, achando o cabeçalho
   dinamicamente pela palavra `DESCRICAO`;
6. atualiza a planilha mestra: metadados, indicadores, cascata de `SITUACAO NO PMIB`,
   hyperlinks, índices percentuais;
7. **inserção interativa** — listas novas encontradas são confirmadas pelo operador via
   `callback_confirm` antes de entrar;
8. `callback_retry_lock` — retry quando a planilha está aberta no Excel;
9. `copiar_estilo_seguro()` — copia font, border, fill, alignment, number_format,
   protection de uma célula para outra.

> [!important] A sacada que torna isso barato
> **O export do Aconex DocManager que o módulo já carrega contém TODOS os documentos do
> projeto — inclusive as Listas de Preços.** Não e preciso uma fonte de dados nova.
> Basta uma regra de reconhecimento para separar, dentro do que já está em memória,
> quais documentos são Lista de Preço e a qual Lista de Sobressalentes cada um pertence.

---

## 3. A regra de reconhecimento — DEFINIDA

> [!success] Resolvido em 31/08/2026
> A detecção **não e pelo código**. E pela **descrição do documento**.

O código da Lista de Preços herda o código Itaipu da Lista de Sobressalentes mais um
sequencial — mas isso **não serve como regra**, porque já existem listas de
sobressalentes que terminam em sequencial (`#ITA0=A01AAM10&EPB020-01`, do SMF). Uma
regra por sufixo classificaria essa lista como lista de preço dela mesma.

### A regra
Procurar, no campo de **descrição/título** do documento no export do Aconex DocManager,
os termos que marcam uma lista de preços:

- **`PRECOS`** / `PREÇOS` / `PRECIOS`
- **`VALORIZADA`** / `VALORIZADO` / `VALORIZACION`

Normalize antes de comparar — maiusculas e sem acento (`unicodedata.normalize('NFD')`),
como `sigft/services/search.py` já faz em `_limpar_texto_parrudo`. O projeto e bilingue
português/espanhol por exigencia da ET, entao **cubra as duas grafias**.

### A vinculacao
Achado o documento de preço, ligue-o a lista-mae **pelo prefixo do código**: o código da
lista de preços começa com o código Itaipu da lista de sobressalentes. Use o código
**mais longo que casa** (evita que `#ST00=B01BDV10&EPB020` capture o documento de
`#ST00=B01BDV10TA010&EPB020`).

Deixe os termos em `sigft/config.py`, não espalhados:

```python
TERMOS_LISTA_PRECOS = ("PRECOS", "PRECIOS", "VALORIZAD")   # ja normalizados
```

### Entrada manual tem precedencia — sempre

> [!danger] Requisito explicito do Luan
> **Os inputs manuais de documentos novos devem ser respeitados.** Se alguém digitou o
> número de uma lista de preços a mao — porque a regra não achou, porque o documento
> não estava no export, ou porque a descrição não seguiu o padrão — **a rotina nunca
> sobrescreve esse valor.**

Regra de precedencia na coluna 12 (`N° DOCUMENTO LISTA DE PRECOS`):

| Estado da célula | O que a rotina faz |
|---|---|
| vazia | preenche com o que a regra achou (ou deixa vazia e loga) |
| preenchida **e igual** ao que a regra achou | mantém |
| preenchida **e diferente** do que a regra achou | **mantém o valor manual** e escreve no log a divergência, para conferencia humana |
| preenchida e a regra **não achou nada** | mantém, sem alarme |

Isso vale também para as colunas 13-15 quando tiverem sido digitadas a mao. A forma
mais simples e segura de implementar: uma coluna técnica oculta `ORIGEM DO VINCULO`
com valor `AUTO` ou `MANUAL`, escrita pela rotina quando ela mesma preenche. Célula
marcada `MANUAL` (ou sem marca, vinda de digitacao) e **somente leitura** para a rotina.

Ver também a seção 6.4 — o mesmo cuidado vale para as colunas 16 e 20.

## 4. O desenho — aba `Acompanhamento Listas de Precos`

Nova aba na mesma pasta de trabalho da mapeadora. **Uma linha por Lista de Sobressalentes**
(não por lista de preço), porque a pergunta gerencial e *"esta lista tem preço em dia?"*.

### Colunas

#### Bloco VINCULO — herdado da aba principal
| # | Coluna | Origem | Nota |
|---|---|---|---|
| 1 | `N° DOCUMENTO ITAIPU` | aba principal | **chave de ligação entre as duas abas** |
| 2 | `N° DOCUMENTO CMI` | aba principal | |
| 3 | `DESCRICAO` | aba principal | |
| 4 | `ESPECIFICACAO TECNICA` | aba principal | permite filtrar por área |
| 5 | `CAPITULO` | aba principal | |
| 6 | `RESPONSAVEL` | aba principal | |
| 7 | `PROCUREMENT` | aba principal | |
| 8 | `EVENTOS DE PAGAMENTOS RELACIONADOS` | aba principal | prioriza pelo dinheiro |

#### Bloco SOBRESSALENTES — o estado da lista-mae
| # | Coluna | Origem |
|---|---|---|
| 9 | `REVISAO ATUAL DA LISTA SOBRESSALENTES` | aba principal, `ULTIMA REVISAO EMITIDA` |
| 10 | `STATUS REAL DA LISTA SOBRESSALENTES` | aba principal, `STATUS REAL` |
| 11 | `FICHAS EXISTENTES` | aba principal |

#### Bloco PREÇOS — o que não existe hoje
| # | Coluna | Origem | Nota |
|---|---|---|---|
| 12 | `N° DOCUMENTO LISTA DE PRECOS` | DocManager, pela regra da seção 3 | vazio = **nunca emitida** |
| 13 | `REVISAO DA LISTA DE PRECOS` | DocManager | |
| 14 | `STATUS DA REVISAO (ACONEX)` | DocManager | |
| 15 | `DATA DE EMISSAO` | DocManager | |
| 16 | **`REVISAO SOBRESSALENTES A QUE SE REFERE`** | **manual** | **o campo que não existe em lugar nenhum hoje** |
| 17 | `DEFASADA?` | **calculada** | ver seção 5 |
| 18 | `ITENS VALORIZADOS / ITENS DA LISTA` | `_STATUS_PMIB`, coluna `VALORIZACAO` | cobertura real |
| 19 | `% VALORIZACAO` | calculada | |
| 20 | `OBSERVACAO` | manual | |
| 21 | `LINK` | hyperlink | mesmo padrão já usado na aba principal |

> [!important] A coluna 16 e o coracao deste plano
> Todo o resto e conveniencia. **`REVISAO SOBRESSALENTES A QUE SE REFERE`** e o único
> dado que hoje não existe em nenhum lugar do projeto — nem na mapeadora, nem no
> `_STATUS_PMIB`, nem no Aconex. Sem ele não ha como saber que uma lista de preço
> envelheceu, e a defasagem só aparece quando Itaipu reclama.
>
> Ela e **preenchida a mao** pela pessoa que emite a lista de preço. E um campo, uma
> vez por emissão. O retorno e o alerta automático da coluna 17.

---

## 5. A regra de defasagem

E a única lógica de negocio nova. Comparar a coluna 16 com a coluna 9:

| Situação | `DEFASADA?` | Cor sugerida |
|---|---|---|
| Coluna 12 vazia **e** `STATUS REAL` da lista-mae = `APROVADO` | **`SEM LISTA DE PRECO`** | vermelho |
| Coluna 12 vazia **e** lista-mae não aprovada | `AGUARDANDO APROVACAO EN.DT` | cinza — não e problema, e a ordem correta |
| Coluna 16 **=** coluna 9 | `EM DIA` | verde |
| Coluna 16 **<** coluna 9 | **`DEFASADA`** | laranja |
| Coluna 16 vazia com coluna 12 preenchida | `A CONFERIR` | amarelo |

> [!note] Por que `AGUARDANDO APROVACAO EN.DT` não e vermelho
> A ata de 23/06/2026 e a nota 3 do slide 12 da apresentação PMIB estabelecem a ordem:
> **lista EN.DT aprovada -> lista de preços -> valorização**. Uma lista sem preço cuja
> mae ainda não foi aprovada esta **correta**. Pintar de vermelho gera alarme falso e
> ensina a equipe a ignorar a coluna.

### Comparacao de revisão
As revisões não são números: `0`, `0A`, `0C`, `1`, `1A`. Implemente um comparador
próprio (número, depois letra) e **teste com os valores reais da coluna
`ULTIMA REVISAO EMITIDA`** — todos os 94 existem na mapeadora hoje.

---

## 6. As mudanças no SIG-FT

Módulo **Gestão PMIB**, mesma tela. Não criar módulo novo.

### 6.1 Serviço
Em `sigft/services/pmib_manager.py`:

```
_localizar_lista_precos(codigo_sobressalentes, df_docmanager) -> dict | None
    Filtra o DocManager ja carregado por TERMOS_LISTA_PRECOS na DESCRICAO
    (texto normalizado: maiusculas, sem acento) e vincula pelo prefixo do
    codigo, escolhendo o codigo mais longo que casa. Devolve
    {documento, revisao, status, data} da versao Current=True, ou None.
    Deve LOGAR quando nao acha — nunca descartar em silencio (ver secao 8).

_preservar_manual(valor_atual, valor_encontrado, origem) -> (valor, aviso)
    A tabela de precedencia da secao 3. Funcao pura. Teste primeiro.

_contar_valorizacao(caminho_status_pmib) -> (valorizados, total)
    Le a coluna VALORIZACAO do _STATUS_PMIB. Reaproveitar _ler_status_pmib,
    que ja acha o cabecalho dinamicamente e le com dtype=str.

_comparar_revisao(rev_a, rev_b) -> int
    Comparador de "0", "0A", "0C", "1", "1A". Puro, facil de testar.

_calcular_defasagem(linha) -> str
    A tabela da secao 5. Funcao pura.

atualizar_aba_listas_precos(caminho_mapeadora, df_docmanager, raiz_status,
                            callback_log, callback_retry_lock) -> resumo
    Orquestra. Cria a aba se nao existir.
```

### 6.2 Configuracao
Em `sigft/config.py`:
```
TERMOS_LISTA_PRECOS = ("PRECOS", "PRECIOS", "VALORIZAD")  # ja normalizados
ABA_LISTAS_PRECOS = "Acompanhamento Listas de Precos"
```

### 6.3 UI
Um botao ou checkbox na tela de Gestão PMIB: **"Atualizar aba de Listas de Preços"**.
Pode rodar junto da atualização normal ou separado.

### 6.4 Preservacao do trabalho manual

> [!danger] Não sobrescreva as colunas manuais
> As colunas **16 (`REVISAO SOBRESSALENTES A QUE SE REFERE`)** e
> **20 (`OBSERVACAO`)** são preenchidas por pessoas. A rotina de atualização **lê e
> reescreve** o resto da linha — mas essas duas tem que ser **lidas antes e devolvidas
> intactas**.
>
> Este e o erro mais provavel desta implementação, e o mais caro: apagaria em silêncio o
> único dado que o plano existe para criar. Escreva o teste desse comportamento
> **antes** do código.

Use `copiar_estilo_seguro()` para manter a formatação, como o módulo já faz.

---

## 7. Critérios de aceite

- [ ] A aba e criada se não existir, e **atualizada sem perder** as colunas 16 e 20 se existir.
- [ ] Toda lista da aba `Acompanhamento Sobressalente` com `FICHAS EXISTENTES > 0` tem
      linha correspondente na aba nova.
- [ ] Lista de preço encontrada no DocManager preenche colunas 12-15 automaticamente.
- [ ] Lista de preço **não** encontrada deixa 12-15 vazias **e escreve no log** o código
      procurado e os termos aplicados.
- [ ] **Valor digitado a mao na coluna 12 sobrevive a uma rodada de atualização**, mesmo
      quando a regra encontra um documento diferente (nesse caso, loga a divergência).
      Escreva este teste primeiro.
- [ ] `DEFASADA?` produz os 5 valores da seção 5, com os casos de fronteira testados
      (`0` vs `0A`, `0C` vs `1`, revisão vazia).
- [ ] `% VALORIZACAO` bate com a contagem manual em pelo menos 3 listas conferidas a mao.
- [ ] Planilha aberta no Excel dispara `callback_retry_lock`, não exceção.
- [ ] Testes cobrindo: `_comparar_revisao`, `_calcular_defasagem`, e a preservacao das
      colunas manuais. As três são funções puras ou quase — são baratas de testar.
- [ ] `bash scripts/check.sh` verde.

---

## 8. Restricoes do projeto que valem para esta tarefa

- **Idioma**: código, comentários, commits e docs em **português**. Commits **sem acento**.
- **Escopo de checkpoint**: implemente **só** isto. O que descobrir fora do escopo vai
  para `docs/refatoracao/PENDENCIAS.md` — não corrija de carona.
- **Trabalho paralelo**: o Rafael (`rafhagmm`) mexe **apenas** no AutoSpecAI. Este plano
  não toca nada dele. Zonas compartilhadas que exigem commit isolado:
  `core/rpa/ficha_layout.py`, `config.LLM_TASKS`, `core/llm/prompts.py`. **Este plano só
  acrescenta constantes novas ao `config.py`** — sem conflito esperado.
- **Nada de reformatacao em massa** de arquivo compartilhado.
- **Falha silenciosa e pior que falha ruidosa.** Ha precedente caro no próprio projeto:
  o `GerenciadorFilaPMIB` descartava fichas duplicadas sem log, e o defeito passou
  despercebido por meses porque a ficha simplesmente sumia da fila. Foi corrigido em
  17/08/2026 exatamente trocando "descarta" por "entra na lista com o motivo no log".
  **Aplique o mesmo critério aqui**: lista de preço não encontrada aparece com aviso,
  nunca some.
- **Escrita**: a mapeadora vive no Box. Escrever **nela** e o proposito da tarefa e esta
  autorizado. Não alterar mais nada dentro do Box.

---

## 9. Perguntas a responder antes de começar

1. ~~Formato do código da Lista de Preços~~ — **RESOLVIDO em 31/08/2026**: a detecção
   e pela **descrição** do documento (`PRECOS` / `VALORIZADA`), não pelo código, e
   entrada manual tem precedencia. Ver seção 3.
2. **[BLOQUEANTE]** O export do **Aconex DocManager** já traz as listas de preço, ou o filtro de
   exportacao exclui a especialidade delas? Se excluir, ajustar a exportacao **antes**
   de codar — sem isso a seção 4 bloco PREÇOS nunca preenche.
3. A aba nova vai na **mesma pasta de trabalho** da mapeadora ou em arquivo separado?
   (Recomendação: mesma pasta — a chave de ligação e o `N° DOCUMENTO ITAIPU`, e separar
   arquivos recria o problema de duas verdades.)
4. Existe uma lista de preço por **lista de sobressalentes**, ou uma pode cobrir várias?
   O desenho atual assume 1:1. Se for N:1, a coluna 12 vira lista de códigos.
5. O `Sobressalentes - Dashboard.pbix` deve passar a ler esta aba também?

---

## 10. Por que vale a pena

Esforço **baixo** — a fonte de dados já esta carregada, o módulo já escreve na
mapeadora, já trata planilha travada, já copia estilo. O que se acrescenta e uma regra
de reconhecimento, um comparador de revisão e uma aba.

Impacto **alto** — hoje ninguém consegue responder "quais listas de preço faltam" nem
"quais envelheceram" sem varrer o Aconex a mao. Com a coluna 17, uma lista de preço
defasada acende sozinha, no dia em que a lista de sobressalentes muda de revisão.

E a ação **M1** de [[Diagnostico - Plano de Melhoria]], a de melhor razão
impacto/esforço do diagnostico inteiro.

## Relacionados
[[Lista de Precos]] · [[Secao - Valorizacao]] · [[Mapeamento das Listas de Sobressalentes]] ·
[[SIG-FT - Modulos]] · [[Diagnostico - Deficiencias]]
