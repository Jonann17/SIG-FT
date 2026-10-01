---
tags: [processo, entrega]
---

# MTA, Etiquetas e Entrega no Almoxarifado

## O MTA e o Código PMIB

Do slide 15 da apresentação R5:

> Depois de criadas no PMIB todas as fichas técnicas dos materiais da lista, e
> necessário entregar para **Procurement** uma lista com os **códigos PMIB** de cada
> material para inserir nos cadastros dos materiais no **MTA**.

### Onde o código entra
O [[Codigo PMIB]] vai no campo **"Supplier Code"** do MTA, **junto com o código do
fornecedor**, no formato:

```
/ CÓD. PMIB 4500063671.0066
```

> [!important] O texto "CÓD. PMIB" e obrigatório
> Itaipu solicita explicitamente que se inclua o texto **"CÓD. PMIB"** para que fique
> claramente identificado na etiqueta.

### Por que isso acontece cedo
Do slide 13: *"Apenas com a criação da ficha e suficiente para a geração do código PMIB
necessário para incluir no MTA."* — ou seja, **não e preciso esperar a ficha estar
preenchida** para alimentar o MTA. Só criada já basta.

Isso desacopla duas frentes que costumam ser confundidas:

```
criar ficha  ->  codigo PMIB  ->  MTA  ->  etiqueta   (trilha logistica)
criar ficha  ->  preencher    ->  emitir ->  aprovar   (trilha documental)
```

## A entrega física

Do slide 16:

> Os materiais sobressalentes devem ser entregues **diretamente no ALMOXARIFADO DE
> ITAIPU** e **não devem passar pelo ALMOXARIFADO DO CMI**.
> Cada material deve ter uma **etiqueta colada junto a sua embalagem** contendo os
> dados cadastrados no MTA.

Confirmado também pelo [[Capitulo 18 - Pecas de Reposicao e Sobressalentes]]:
*"As peças de reposicao devem ser enviadas diretamente aos armazens (almoxarifados) da ITAIPU."*

### Temporario e definitivo — são dois

> [!important] Itaipu recebe material com ficha ainda não aprovada
> Quando o material e entregue mas a **ficha ainda não foi aprovada** — os dois ramos do
> fluxo correm em velocidades diferentes — o material fica com Itaipu num
> **almoxarifado temporario**. Ele só vai para o **almoxarifado definitivo** depois que
> a ficha técnica for aprovada.
>
> Isso importa muito para a discussão de fluxo: **Itaipu já tem um mecanismo para
> segurar material cuja documentação não está fechada.** Ver
> [[Plano de Acao - Aplicacao LMR]], seção de negociação.

> [!warning] Realidade x regra
> A mapeadora mostra 5 listas com `ENTREGA = ALMOXARIFADO CMI` e observacoes como
> *"O material está no almoxarifado do CMI esperando..."*. Ou seja: material que
> deveria ter ido direto para Itaipu esta parado no almoxarifado do CMI, aguardando
> autorização de entrega. Ver [[Diagnostico - Deficiencias]].

## A sequência de entrega

```
1. Ficha preenchida (valorizacao incluida)
2. E-MAIL a Itaipu — intencao de entrega        ← comeca o relogio dos 2/3 meses
3. Itaipu autoriza  ......................  15 dias uteis
4. E-MAIL de autorizacao para Procurement responsavel
5. Imprimir etiquetas MTA
6. Entrega no ALMOXARIFADO TEMPORARIO de Itaipu
7. Libera Evento de Entrega dos Sobressalentes
```

E, no outro ramo:
```
8.  CMI sobe a APLICACAO LMR  ............  2 a 3 meses apos o passo 2
9.  E-MAIL: fichas atualizadas, prontas para analise
10. Itaipu verifica e aprova
11. Libera Evento de Aprovacao dos Sobressalentes
12. Material passa ao ALMOXARIFADO DEFINITIVO
```

## Colunas de controle no `_STATUS_PMIB`
- `DATA DO EMAIL COMUNICANDO ENTREGA`
- `APTO PARA ENTREGA` (SIM / NÃO)
- `EQUIPAMENTO ENTREGUE`

Na mapeadora: `APTO PARA ENTREGA` e
`ATRASO DE AUTORIZACAO DE ENTREGA ITAIPU`.

## Relacionados
[[Fluxo Macro de Entrega]] · [[Codigo PMIB]] · [[Planilha STATUS_PMIB]]
