---
tags: [codificacao]
---

# RDS-PP e KKS

## Os dois sistemas

- **RDS-PP** (*Reference Designation System for Power Plants*, ISO/IEC 81346 aplicado a
  usinas) — o sistema **oficial do projeto**. Toda documentação emitida para Itaipu
  segue esta codificação.
- **KKS** (*Kraftwerk-Kennzeichensystem*) — o sistema classico de identificação de
  usinas, que serve de **base ao código interno do CMI**.

O RDS-PP e o sucessor conceitual do KKS. O projeto usa RDS-PP para fora (Itaipu) e um
código derivado de KKS para dentro (CMI). Ver [[Codigo CMI e Codigo Itaipu]].

> [!warning] Este cofre não tem a chave completa do RDS-PP
> O que segue e **padrão observado nos códigos reais do projeto**, não a norma.
> Para decodificar com segurança, consulte a especificação de codificação do projeto
> ou a engenharia do sistema. Anotado como pendência em [[findings]].

## Anatomia observada

```
#ST50=Y01YCQ10-UH001&ETC010
│└┬─┘ └──────┬──────┘ └──┬─┘
│ │          │           └── tipo de documento / funcao
│ │          └── designacao funcional do objeto
│ └── prefixo de local / instalacao
└── marcador de inicio do codigo
```

### Prefixos de local observados

| Prefixo | Onde aparece |
|---|---|
| `#ITA0` | códigos de abrangencia geral da usina (equipamentos, listas RTA) |
| `#ST00` | comum aos dois setores |
| `#ST50` / `#ST60` | par de códigos que sempre aparecem juntos para o mesmo objeto |
| `#BA00` | barragem |
| `#SEMD` | subestacao / área específica |
| `#Q01`, `#X00`, `#B01`, `#B03`, `#U01` | designacoes funcionais de sistema |

> [!tip] Por que `ST50` e `ST60` vem sempre em par
> A usina de Itaipu tem duas metades eletricas: **50 Hz** (lado Paraguai) e
> **60 Hz** (lado Brasil). Os documentos e as listas se duplicam por setor.
> Isso aparece na prática: a pasta do RTA tem `CASA DE FORCA 50HZ.pdf` e
> `CASA DE FORCA 60HZ.pdf`, e a mapeadora tem pares como
> `#ST50=X00XAA11&MPB020` e `#ST60=X00XAA11&MPB020`, mesma descrição, códigos CMI
> terminados em `-01` e `-11`.
>
> **Consequência operacional**: uma lista de sobressalentes de um sistema que existe
> nos dois setores vira **duas listas**, dois `_STATUS_PMIB`, e dois conjuntos de
> fichas — ou fichas duplicadas. Ver [[Fichas Duplicadas]].

### Sufixos após `&` observados

| Sufixo | Aparente significado |
|---|---|
| `EPB020` | documento de engenharia elétrica — lista |
| `MPB020` | documento de engenharia mecânica — lista |
| `BPB020` | documento de engenharia (RTA / telecom) |
| `ETC010` | desenho / bayface |
| `ELD020` | diagrama elétrico |

## Onde o RDS-PP e usado no processo de sobressalentes

| Uso | Exemplo |
|---|---|
| **Código da lista de sobressalentes** | `#ITA0=Y01TF001&BPB020` — vira o nome do arquivo `_STATUS_PMIB` |
| **Código do documento de referência** | `#ST50=Y01YCQ10-UH001&ETC010` — aba `DOCS DE REFERENCIA` do template LMR |
| **Código do equipamento na TAG LMR** | `#ITA0=Y01YCQ11KF111-KF001` — dentro do `TAG_LMR` |
| **Código na ficha duplicada** | código RDS-PP do documento da lista, na Informação Geral |

## Relacionados
[[Codigo CMI e Codigo Itaipu]] · [[Secao - Aplicacao LMR]] · [[Planilha STATUS_PMIB]]
