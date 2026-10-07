---
tags: [contexto, estrutura]
---

# Estrutura ET, Capítulo e Sistema

## A hierarquia

```
Projeto de Atualizacao Tecnologica
└── Especificacao Tecnica (ET)        ← delimita a area
    └── Capitulo                       ← recorte dentro da area
        └── Sistema                    ← tem equipe de engenharia propria
            └── Subsistema             ← quando o sistema e grande
                └── Lista de Sobressalentes  ← 1 lista, 1 documento Aconex
                    └── Ficha Tecnica  ← 1 por material, no PMIB
```

Cada **sistema** tem uma equipe de engenharia que desenvolve o projeto para atender
os requisitos do edital, em conjunto com o cliente, que avalia.

## As ETs do projeto, como aparecem na mapeadora

| ET | Exemplos de capítulo / sistema |
|---|---|
| **Controle Centralizado** | SCADA; RTA e sistemas de comunicacao; Serviços Auxiliares Essenciais |
| **Serviços Auxiliares Eletricos** | Conversores Estaticos de Frequência (SFC); Grupo Gerador Diesel; Transformadores Auxiliares a Óleo; Painéis de Manutenção |
| **Serviços Auxiliares Mecanicos** | Sistema de detecção e combate a incendio dos transformadores |
| **Infraestrutura Complementar** | Sala Segura |
| **Unidade Geradora** | Auxiliares da UG (Água Pura, aeração axial do eixo da turbina, selo do eixo mecânico); Auxiliares Essenciais; Comporta e Bypass; Regulação de Velocidade e Potencia; Sistema Digital de Supervisão e Controle; Sistema de Alimentacao Elétrica da Unidade; Sistema de Excitacao; Sistema de Proteção; Transformadores Elevadores Principais; Válvulas Bypass e Conduto Forcado |
| **Sistema de Medição de Faturamento (SMF)** | — |
| **Vertedouro** | — |
| **GIS** | — |

> [!note] EBOP e MBOP
> As pastas usam também **EBOP** (Electrical Balance of Plant) e **MBOP**
> (Mechanical Balance of Plant) como agrupadores fisicos. Eles não aparecem com esse
> nome na mapeadora, que usa a nomenclatura de ET. Ver [[Organizacao das Pastas]].

## Distribuição real de listas por ET
Ver [[Panorama Quantitativo]] para os números atualizados. Em 31/08/2026 a
concentracao era: Unidade Geradora (53 listas), Serviços Auxiliares Eletricos (27),
Controle Centralizado (8).

## Por que a hierarquia importa para a ficha
Duas consequências praticas:

1. **A [[Secao - Aplicacao LMR]] e feita por sistema, não por material.**
   Se um switch também cabe no rack de outro sistema, isso é ignorado — a ficha só
   documenta os racks **daquele** sistema a que ela pertence.
2. **O mesmo material em duas listas diferentes vira ficha duplicada.**
   Ver [[Procedimento de Fichas Duplicadas]].

## Relacionados
[[Projeto de Modernizacao de Itaipu]] · [[Lista de Sobressalentes]] · [[Organizacao das Pastas]]
