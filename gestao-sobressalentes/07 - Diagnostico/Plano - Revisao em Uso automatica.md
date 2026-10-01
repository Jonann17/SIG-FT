---
tags: [plano, gerenciamento, mapeadora, status-pmib]
status: desenho-definido-pelo-luan
criado: 2026-09-02
---

# Plano — `REVISÃO EM USO` automática

## O que já existe e funciona

Na [[Mapeamento das Listas de Sobressalentes|mapeadora]], aba
`Acompanhamento Sobressalente`:

| Coluna | Nome | Como é preenchida hoje |
|---|---|---|
| **C** | `ÚLTIMA REVISÃO EMITIDA` | **automática** — vem do extrato do Aconex |
| **D** | `STATUS DA REVISÃO` | automática, mesma fonte |
| **G** | `REVISÃO EM USO` | **à mão** |

E já existe a formatação condicional que acusa a divergência:

```
G3<>C3   →   pinta de vermelho
```

A atualização do RDS-PP quando o código do documento muda também já funciona.

---

## O que muda

**Uma peça só se move: onde a pessoa digita.**

| | Hoje | Depois |
|---|---|---|
| Quem sabe a revisão conferida | a coluna `G` da mapeadora | o próprio `_STATUS_PMIB` |
| Quem preenche `G` | a pessoa, à mão | o **Gestão PMIB**, lendo o arquivo |
| Regra `G<>C` | já funciona | continua igual, sem tocar |

O trabalho manual não desaparece — ele **muda de lugar**, e passa a ficar junto do arquivo
que ele descreve. Quem reconcilia o `_STATUS_PMIB` com a lista nova carimba ali mesmo,
sem trocar de planilha.

> [!note] Por que no arquivo e não na mapeadora
> O `_STATUS_PMIB` é renomeado quando o código do documento muda, é copiado entre pastas e
> sobrevive a reorganizações. A informação de qual revisão ele reflete **é dele**, e viaja
> junto. Na mapeadora, ela é um dado sobre outro arquivo — e se perde na primeira
> movimentação.

---

## A marca no `_STATUS_PMIB`

A **linha 1 está vazia** em todos os arquivos: o conteúdo começa na linha 2 (título), 3
(sistema) e 4 (cabeçalho da tabela). A marca cabe ali sem empurrar nada.

```
A1: REVISÃO EM USO:   B1: 0C
```

> [!important] Ler pelo rótulo, nunca por coordenada
> O módulo já acha o cabeçalho da tabela procurando a palavra `DESCRIÇÃO`, justamente
> porque as planilhas não são idênticas entre si. A marca merece o mesmo cuidado: procurar
> a célula cujo texto é `REVISÃO EM USO`, não ler `B1`.
>
> Quem inserir uma linha no topo quebraria a leitura por coordenada — e ninguém saberia,
> porque o resultado seria uma célula vazia, que parece "ainda não conferido".

---

## O risco da virada

> [!danger] Ao ligar a automação, `G` passa a refletir o arquivo — e o que estiver digitado
> lá é substituído
>
> Hoje a coluna `G` guarda trabalho manual acumulado. No primeiro dia em que o Gestão PMIB
> passar a escrevê-la, todo `_STATUS_PMIB` sem a marca produz `G` vazia — e a mapeadora
> acusa vermelho em massa, com o histórico perdido.

**Semear antes de ligar.** Uma rotina de uma execução só:

1. lê a coluna `G` de cada linha da mapeadora;
2. escreve esse valor na linha 1 do `_STATUS_PMIB` correspondente;
3. só depois disso o módulo passa a ler na direção contrária.

Assim nada se perde e ninguém precisa reconferir 94 listas para voltar ao ponto de partida.

---

## Detalhes de implementação

- **Marca vazia**: `G` fica vazia, e a regra `G<>C` já acusa vermelho. É o comportamento
  correto — arquivo sem marca é arquivo não conferido.
- **Comparação é de igualdade**, não de ordem: a regra existente compara texto. Não é
  preciso comparador de revisão para este plano. *(A
  [[Plano - Aba de Listas de Precos|aba de listas de preços]] precisa de um comparador de
  ordem para outra finalidade — são coisas diferentes.)*
- **Planilha aberta**: reaproveitar o `callback_retry_lock` que o módulo já tem.
- **Escrita no `_STATUS_PMIB`**: o módulo hoje só lê esses arquivos e renomeia; passar a
  escrever dentro deles é capacidade nova. Preservar o resto da planilha intacto.

---

## O passo seguinte, quando fizer sentido

Acusar a divergência também na lista de atividades pendentes do Gestão PMIB — como o Luan
já anotou, é melhoria separada.

E, mais adiante, dizer **o que** mudou entre as revisões, não só que mudou: comparar os
códigos PMIB do `_STATUS_PMIB` com os da lista nova produz "itens novos, removidos, com
quantidade alterada", que é a lista de trabalho de verdade. Nesse caso, contar por **código
PMIB distinto** — o mesmo item aparece em várias linhas quando entra em conjuntos
diferentes, e [[Entrega Documental e Explosao de Itens|itens explodidos]] multiplicam
linhas sem multiplicar fichas.

## Relacionados
[[Planilha STATUS_PMIB]] · [[Mapeamento das Listas de Sobressalentes]] ·
[[Lista de Sobressalentes]] · [[SIG-FT - Modulos]] · [[Aba de Atividades e Cronograma]]
