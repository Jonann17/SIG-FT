---
tags: [codificacao]
---

# Código CMI e Código Itaipu

Todo documento do projeto carrega **dois códigos em paralelo**. Confundi-los e a
origem de boa parte do retrabalho de rastreabilidade.

## Código Itaipu (RDS-PP)

Formato: `#ST00=B01BMU10&EPB020`
Ver [[RDS-PP e KKS]]. E o código pelo qual **Itaipu** conhece o documento.

## Código CMI

Formato observado: `08934100BAX00-FS00PB-51`

```
0893410 0BAX00 - FS00PB - 51
└──┬──┘ └──┬─┘   └──┬──┘  └┬┘
   │       │        │      └── variante / setor (01, 02, 11, 51, 61, 95...)
   │       │        └── tipo de documento
   │       └── sistema / objeto
   └── raiz do projeto
```

Outros exemplos reais:
```
0893410CYU20-224FPD-95     lista de sobressalentes do RTA
08934120SAA11-FS00PB-01    50 Hz
08934120SAA11-FS00PB-11    60 Hz  ← mesmo documento, outro setor
0893410CYU20-220FTL-56     desenho de bayface
```

> [!tip] O sufixo carrega o setor
> Pares `-01`/`-11` e `-51`/`-61` correspondem aos setores **50 Hz** e **60 Hz**.
> Confirmavel na mapeadora: linhas com mesma descrição, códigos Itaipu `#ST50=` e
> `#ST60=`, e códigos CMI diferindo só no sufixo.

## Onde a amarracao entre os dois vive

| Lugar | Como |
|---|---|
| **[[Mapeamento das Listas de Sobressalentes\|Mapeadora]]** | colunas `N° DOCUMENTO ITAIPU` e `N° DOCUMENTO CMI`, lado a lado |
| **Template de Aplicação LMR** | aba `DESCRICAO DOCUMENTOS`: `CODIGO ITAIPU` \| `CODIGO CMI` \| `DESCRICAO` |
| **Lista de sobressalentes SM.DT** | tem coluna `Codigo CMI` (decisão da ata de 23/06/2026) |
| **`_STATUS_PMIB`** | coluna `CODIGO CMI` por item |

## O terceiro código: Tracking ID do Aconex

O Aconex mantém um **Tracking ID** estável por documento, e o `No. do Documento` pode
mudar entre revisões. E por isso que o módulo **Gestão PMIB** do SIG-FT:
1. procura o código do arquivo em `No. do Documento` na base do Aconex DocManager;
2. pega o **Tracking ID** correspondente;
3. procura a versão com o mesmo Tracking ID e `Current = True`;
4. **renomeia o arquivo `_STATUS_PMIB`** para o código novo.

Sem isso, um arquivo `_STATUS_PMIB` fica orfao quando a lista muda de código na revisão.
Ver [[SIG-FT - Modulos]].

## Relacionados
[[RDS-PP e KKS]] · [[Mapeamento das Listas de Sobressalentes]] · [[Lista de Sobressalentes]]
