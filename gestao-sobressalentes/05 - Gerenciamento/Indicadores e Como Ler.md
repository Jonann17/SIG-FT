---
tags: [gerenciamento, indicadores]
---

# Indicadores e Como Ler

Como interpretar os números da [[Mapeamento das Listas de Sobressalentes|mapeadora]]
sem tirar conclusão errada. Os valores atuais estão em [[Panorama Quantitativo]].

## O funil

Os indicadores de ficha formam um funil, mas **não e um funil limpo** — as etapas
correm em paralelo e um item pode estar em várias colunas ao mesmo tempo.

```
FICHAS EXISTENTES                 ← denominador de tudo
  ├─ FICHAS COM O FORNECEDOR      ← esperando terceiro
  ├─ FICHAS RECEBIDAS             ← fornecedor devolveu
  ├─ FICHAS EM ELABORACAO         ← CMI trabalhando
  │   ├─ INFO. DO FORNECEDOR COMPLETO
  │   ├─ VALORIZACAO                        ← depende de outra area + lista aprovada
  │   └─ FICHAS COM APLICACAO-LMR FINALIZADA ← depende de desenho
  ├─ FICHAS EM ANALISE DE ITAIPU  ← emitidas
  ├─ FICHAS EM CORRECAO           ← devolvidas
  └─ FICHAS APROVADAS             ← fim da trilha documental

APTO PARA ENTREGA                 ← trilha logistica, paralela
ATRASO DE AUTORIZACAO DE ENTREGA  ← estouro de prazo na trilha logistica
```

## As três leituras que enganam

### 1. `FICHAS RECEBIDAS` > `FICHAS EM ELABORACAO` não e contradicao
"Recebidas" e cumulativo (o fornecedor já devolveu alguma vez); "em elaboração" e o
estado atual. Uma ficha recebida e já emitida sai de "em elaboração" mas contínua
contada em "recebidas".

### 2. `FICHAS EM ANALISE DE ITAIPU` alto não e necessariamente bom
E trabalho **entregue**, mas também e **capital parado**: cada ficha em análise fica
2 a 3 meses fora do controle do CMI. Um número alto aqui significa que o gargalo
mudou de lado — o que e bom para o CMI e ruim para o cronograma.

### 3. `VALORIZACAO` e `APLICACAO - LMR` são os indicadores de saude real
São as duas seções que **só o CMI pode fechar** e que **não dependem do fornecedor**.
Quando elas ficam para tras, a ficha não avanca por responsabilidade interna.

> [!important] O indicador que mais importa hoje
> **`FICHAS COM APLICACAO - LMR FINALIZADA` sobre `FICHAS EXISTENTES`.**
> E o menor da cadeia. Ver [[Panorama Quantitativo]] e [[Diagnostico - Deficiencias]].

## Indicadores derivados que valem calcular

| Indicador | Fórmula | Lê o que |
|---|---|---|
| **Cobertura de LMR** | `LMR finalizada / fichas existentes` | o gargalo declarado |
| **Cobertura de valorização** | `valorizacao / fichas existentes` | dependência de outra área |
| **Taxa de devolucao** | `em correcao / em analise` | qualidade do que se emite |
| **Taxa de aprovação** | `aprovadas / em analise` | velocidade de Itaipu |
| **Pendência de fornecedor** | `com o fornecedor / existentes` | dependência externa |
| **Listas não iniciadas** | `SITUACAO = INICIAR / total de listas` | trabalho ainda não comecado |

## Cuidado com `ATRASO DE AUTORIZACAO DE ENTREGA ITAIPU`

> [!success] Conta fichas (confirmado no código do SIG-FT, 30/09/2026)
> Cada célula é a **quantidade de fichas** (PMIB distinto, sem DUPLICADO) com e-mail de
> intenção enviado, sem APTO e sem entrega, além do prazo.
>
> **Mas o prazo está na regra antiga**: o SIG-FT soma **14 dias corridos** à data do e-mail;
> a regra vigente é **15 dias úteis**. Até o SIG-FT ser corrigido, use o número do
> `_STATUS_PMIB` v2 (coluna SITUAÇÃO DA AUTORIZAÇÃO) ou do painel v2.
> Ver [[Plano - Sistema de Gestao v2]].

## Onde os números nascem

```
_STATUS_PMIB (por item)
      ↓  modulo Gestao PMIB do SIG-FT le e conta
Mapeamento Listas de Sobressalentes (por lista)
      ↓  script deste cofre le e agrega
_gerado/Panorama Quantitativo (por projeto)
```

Cada nível e uma agregação do anterior. **Se um `_STATUS_PMIB` esta desatualizado, o
erro se propaga até o topo em silêncio.** Ver [[Diagnostico - Riscos]].

## Relacionados
[[Panorama Quantitativo]] · [[Mapeamento das Listas de Sobressalentes]] · [[Diagnostico - Deficiencias]]
