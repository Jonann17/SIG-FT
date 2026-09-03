# Lista de preços Follow-up — controle documental da lista com preços

**Data:** 2026-09-03 · **Frente:** refatoração geral (Luan) · **Módulo:** PMIB Manager
**Origem:** *"Devemos criar o gerenciamento da lista de preços tal como temos para a de
sobressalentes, mas aqui será unicamente um controle documental, contendo as informações
disponíveis do Aconex, mais uma coluna de AÇÃO... e uma coluna de comentários ou observações...
e preciso de um indicador de quando o rds-pp da lista a qual ela se refere mudar."*

---

## 1. O que é a lista de preços

Documento emitido no Aconex que copia o conteúdo da lista de sobressalentes de um sistema e
acrescenta informação que só existe depois de outro processo. Cada lista de preços **se refere
a uma** lista de sobressalentes.

O SIG-FT já acompanha as listas de sobressalentes na aba `Acompanhamento Sobressalente`. Esta
aba nova faz o mesmo para as de preços — mas **só controle documental**: nada de fichas, nada
de portal PMIB. É uma agenda de "o que precisa ser emitido ou reemitido".

## 2. Tudo aqui foi medido, não suposto

Validado em 2026-09-03 contra `Aconex_Historico_03.09.26_12h01m.xlsx` (86.789 linhas, 9.374
documentos vigentes):

| Medida | Valor |
|---|---|
| Títulos com "SOBRESSALENTES" vigentes | 94 |
| Destes, listas **de preços** (título contém "PREÇO") | **16** |
| Listas de sobressalentes | 78 |
| Sequencial das listas de preços | 14 em `-01`, **2 em `-02`** |

E, com a regra de pareamento da §4, as 16 se classificam **sem sobra**:

| Desfecho | Quantas |
|---|---|
| Par encontrado | **12** |
| **RDS-PP divergente** (o alerta que o usuário pediu) | 3 |
| Órfã (sem lista correspondente em revisão nenhuma) | **1** |

> **Correção de 2026-09-03, durante a implementação.** Este quadro dizia
> 11/3/**2**. O usuário duvidou das 2 órfãs — *"é bem simples, basta pegar o
> XXXXX, achar qualquer um que tenha o tracking ID, filtrar o histórico por ele
> e pegar a última"* — e estava certo: uma delas não era órfã.
>
> `#ST00=B04BMA10TB020&EPB020-01` tem a sua lista **vigente, com a raiz
> idêntica**, e 13 revisões no histórico. O algoritmo não a achava porque
> procurava o par **entre os títulos com "SOBRESSALENTES"**, e o título dela
> não tem essa palavra. O furo era o filtro, não a busca.
>
> O algoritmo passou a procurar pela RAIZ no histórico inteiro e a usar o
> título só para saber qual família é a de preços. Ver §4.2.

## 3. A aba `Lista de preços Follow-up`

Vai no mesmo arquivo do mapeamento (`Mapeamento Listas de Sobressalentes.xlsx`), ao lado de
`Acompanhamento Sobressalente`, `Dropbox` e `Atividades`.

Cabeçalho na **linha 1** — decisão do usuário em 2026-09-03.

A aba `Acompanhamento Sobressalente` usa a linha 2, e uma versão anterior deste documento
propunha seguir aquele padrão. O usuário preferiu a linha 1, e a divergência não custa nada
aqui: `_ler_status_pmib` e o `col_indices` do `executar_fluxo` leem `ws[2]` da aba DELES, e a
aba nova tem leitura própria (`lista_precos_planilha.mapa_de_colunas`), que respeita
`LINHA_CABECALHO`.

| # | Coluna | Origem | Quem escreve |
|---|---|---|---|
| 1 | `N° DOCUMENTO ITAIPU` | `No. do Documento` | app |
| 2 | `N° DOCUMENTO CMI` | `Controle do Emissor` | app |
| 3 | `ÚLTIMA REVISÃO EMITIDA` | `Revisão` | app |
| 4 | `STATUS DA REVISÃO` | `Status` | app |
| 5 | `DATA DE ATUALIZAÇÃO` | `Data de Alteração` | app |
| 6 | `DESCRIÇÃO` | `Título` | app |
| 7 | `ESPECIFICAÇÃO TÉCNICA` | `Especialidade` | app |
| 8 | `CAPÍTULO` | `Subespecialidade` | app |
| 9 | `LISTA DE SOBRESSALENTES` | o par (§4) | app |
| 10 | `ALERTA RDS-PP` | §5 | app |
| 11 | `AÇÃO` | "Não" / "Emitir" / "Reemitir" | **usuário** |
| 12 | `OBSERVAÇÕES` | texto livre | **usuário** |

As colunas 1 a 8 saem do **mesmo `mapeamento_colunas`** que `executar_fluxo` já usa para a aba
de sobressalentes (`pmib_manager.py`, ~linha 344). Ele deixa de ser um dicionário local e passa
a ser constante compartilhada — a mesma decisão que o `lmr_status.py` tomou para a coluna de
LMR. Duas cópias divergiriam no primeiro ajuste de nome de coluna.

A ordem 1–8 é a da aba de sobressalentes, com as colunas que o usuário não pediu (`STATUS
REAL`, `REVISÃO EM USO`) omitidas.

## 4. Como achar a lista de sobressalentes correspondente

**A regra pela RAIZ**: tira-se o sequencial final (`-01`, `-02`, …) dos **dois** lados e
comparam-se as raízes.

```
#ITA0=C01CUC01&EPB020-02   (preços)  ->  raiz  #ITA0=C01CUC01&EPB020
#ITA0=C01CUC01&EPB020      (lista)   ->  raiz  #ITA0=C01CUC01&EPB020    ✓ par
```

### 4.1 Por que dos DOIS lados, e não só do lado dos preços

A descrição inicial era "a lista de preços sempre termina com sequencial; sem o sequencial,
acha-se a lista de sobressalentes". **Isso não vale sempre**, e os dados mostram o
contra-exemplo:

```
preços  #ITA0=A01AAM10&EPB020-02
lista   #ITA0=A01AAM10&EPB020-01     <- a LISTA também tem sequencial
```

Tirar o sequencial só do lado dos preços procuraria `#ITA0=A01AAM10&EPB020`, que hoje não é
vigente — e o par seria perdido. Tirando dos dois, casa. Foi o que subiu o pareamento de 10
para 11.

### 4.2 O algoritmo, em passos

1. da lista de preços, tira-se o sequencial → a **raiz**;
2. procuram-se no histórico INTEIRO os documentos com aquela raiz — qualquer
   revisão, qualquer sequencial;
3. descartam-se os que têm o `Tracking ID` da própria lista de preços;
4. do tracking restante, pega-se a revisão `Current` **procurando pelo
   tracking, não pela raiz**;
5. se a raiz do código vigente for outra → RDS-PP mudou.

> ⚠️ O passo 4 é o que uma primeira versão errou. Ela procurava a revisão
> vigente *entre as linhas da raiz antiga* — mas quando o RDS-PP muda, a
> revisão vigente tem raiz DIFERENTE por definição, e nunca estaria ali. O
> resultado eram as 3 divergentes classificadas como órfãs. O `Tracking ID` é
> o que atravessa a mudança de código: ele não muda quando o RDS-PP muda.

### 4.3 O que distingue uma da outra

Não é o sequencial (as duas podem ter). É o **título**: a lista de preços contém "PREÇO"; a de
sobressalentes, não. Essa distinção já está codificada em `executar_fluxo`, no filtro que hoje
**exclui** as listas de preços da aba de sobressalentes. A aba nova consome exatamente o que
aquele filtro descarta — por isso o filtro vira função nomeada, usada pelos dois lados, em vez
de um `if` no meio do fluxo.

> ⚠️ **Defeito encontrado no filtro atual, e que este trabalho corrige.** Ele exclui
> `endswith('-01')`, mas há listas de preços em `-02`. Hoje elas são barradas só pelo título
> conter "PREÇO"; se um título fugir do padrão, uma lista de preços entra na aba de
> sobressalentes como se fosse uma lista comum. Passa a excluir qualquer `-\d{1,2}` final.

## 5. O alerta de RDS-PP

Quando a raiz não casa com nenhuma lista **vigente**, o app pergunta ao histórico o que
aconteceu com aquele código, usando o mecanismo que já existe
(`_buscar_rdspp_mais_recente`): acha o `Tracking ID` do código e devolve a versão
`Current == True` daquele tracking.

| Situação | `ALERTA RDS-PP` | `OBSERVAÇÕES` |
|---|---|---|
| Par encontrado | vazio | intocada |
| O tracking existe e o código mudou | `Atualizar código Itaipu` | app **acrescenta** uma linha: `[SIG-FT dd/mm] a lista mudou de <antigo> para <novo>` |
| Nenhuma revisão daquele código | `Sem lista correspondente` | acrescenta: `[SIG-FT dd/mm] não achei lista de sobressalentes para esta lista de preços` |

Os 3 divergentes medidos hoje:

```
#ST00=B01BDV10-MS000UC004&EPB020-01  ->  lista virou #ST00=B03BDV10UC012-UC001&EPB020
#ST00=Q01GDB00&MPB020-01             ->  lista virou #ST00=B01BDV10&MPB020
#ST00=Q01PAC01GP030-GP900&MPB020-01  ->  lista virou #ST00=B01BDV10EQ010-GP901&MPB020
```

**Por que coluna própria E texto na observação** (decisão do usuário): a coluna é filtrável e
ordenável na planilha — dá para ver "quais têm alerta" numa olhada. O texto diz *qual* código
virou *qual*, que é o que se precisa para agir. Só a coluna não informa; só o texto não filtra.

### 5.1 O app acrescenta na Observação, nunca substitui

`OBSERVAÇÕES` é do usuário. O app **acrescenta uma linha ao fim**, prefixada com `[SIG-FT
dd/mm]`, e nunca reescreve o que já está lá. Se a mesma linha já existir (mesma origem e mesmo
destino), não duplica a cada execução — senão, um documento parado com alerta acumularia uma
linha por rodada até a célula virar ilegível.

`ALERTA RDS-PP`, ao contrário, é do app: ele reescreve a cada execução, porque o alerta reflete
o estado de hoje. Um alerta que persiste depois de resolvido é pior que nenhum.

## 6. O que NUNCA é sobrescrito

Este é o requisito que decide se a aba é usável ou não. `AÇÃO` e `OBSERVAÇÕES` carregam o
trabalho de decisão do usuário; perdê-las numa atualização inutilizaria a aba.

Por isso a atualização **casa por `N° DOCUMENTO ITAIPU`** e escreve célula a célula nas colunas
1–10 da linha existente. Ela **não** recria a aba, não apaga linhas e não reordena.

* documento novo no Aconex → **linha nova** no fim, com `AÇÃO` e `OBSERVAÇÕES` vazias;
* documento que sumiu do Aconex (deixou de ser vigente) → a linha **permanece**, e o app
  acrescenta o alerta `Não está mais vigente no Aconex`. Apagar a linha levaria junto a
  observação que o usuário escreveu, e sumir com informação sem avisar é o pior desfecho
  possível aqui.

## 7. Onde isso roda

Dentro do `executar_fluxo` do PMIB Manager, **depois** da etapa que atualiza a aba de
sobressalentes — o usuário pediu que "sempre na atualização do PMIB manager devemos atualizar
essa aba".

O `df_api` já está carregado nesse ponto; a aba nova não lê o Aconex de novo.

**A aba precisa existir.** Se não existir, o app **não a cria**: emite um aviso dizendo o nome
exato esperado (`Lista de preços Follow-up`) e segue com o resto do fluxo. Criar aba com
formatação em planilha compartilhada do consórcio é o tipo de escrita estrutural que deve
partir do usuário — e o resto da atualização não pode parar por causa disso.

## 8. Riscos

**~~A planilha aberta no LibreOffice~~ — risco RETIRADO em 2026-09-03.** Uma versão anterior
deste documento tratava a detecção do arquivo-sentinela do LibreOffice como pré-requisito, por
causa da sobrescrita que aconteceu em 2026-08-28. O usuário decidiu que **o LibreOffice não
será mais usado**, então a trava não será implementada e este deixa de ser um risco desta
frente. Com o Excel, o `save_with_retry` já dispara normalmente e a janela "feche o arquivo"
aparece.

**O título é a única coisa que distingue lista de preços de lista comum.** Um documento cujo
título fuja do padrão ("PREÇO"/"PREÇOS") cai no lado errado. O filtro por sequencial ajuda mas
não decide sozinho — ver §4.2. Mitigação: o resumo do lote informa quantas listas de preços
foram identificadas, e uma queda brusca nesse número é sinal de título fora do padrão.

**16 documentos é uma amostra pequena.** As regras foram validadas contra o histórico inteiro,
mas 16 casos não cobrem tudo o que o Aconex pode produzir. Os dois casos de borda encontrados
(par com sequencial dos dois lados; órfã genuína) já entraram no desenho.

## 9. Fora de escopo

- As outras três frentes que o usuário levantou junto: automação da aba `Atividades` (B), mural
  de atividades na Home (C) e a redução de densidade da Home (A). Cada uma terá spec próprio.
- A mudança futura do template do `_STATUS_PMIB` para carregar a revisão da lista — o usuário
  a descreveu como "futura modificação".
- Qualquer leitura de ficha ou acesso ao portal PMIB: esta aba é **só** controle documental.

## 10. Verificação

1. `bash scripts/check.sh` verde;
2. testes com um `df_api` sintético cobrindo os **quatro** desfechos: par direto, par com
   sequencial dos dois lados, RDS-PP divergente e órfã — os quatro existem nos dados reais e
   estão nomeados neste documento;
3. teste de que `AÇÃO` e `OBSERVAÇÕES` sobrevivem a duas execuções seguidas;
4. teste de que a linha do alerta não duplica quando a mesma execução roda duas vezes;
5. **execução real** contra o `Mapeamento Listas de Sobressalentes.xlsx` do usuário,
   conferindo que as 16 listas aparecem e que os 3 alertas de RDS-PP são os
   três nomeados na §5.

O item 5 é o único que prova o resultado de ponta a ponta, e só o usuário pode fazê-lo — a
planilha vive no Box do consórcio.
