---
tags: [processo, core, ficha]
---

# Anatomia de uma Ficha Técnica

## O que é uma ficha

A **parte documental do equipamento**. Cada material sobressalente entregue precisa
ter uma ficha técnica no **PMIB** (Portal de Materiais da Itaipu Binacional).

A ficha e criada **a partir de um PDM**. O PDM define quais características técnicas
aquele tipo de material exige — e cada tipo exige coisas diferentes. Ver
[[PDM - Padrao de Descricao de Material]].

## As duas metades da ficha

```
FICHA TECNICA
├── Comum a todo tipo de material  (as "secoes")
│   ├── Informacoes Gerais  (+ Fabricantes e Fornecedores)
│   ├── Condicoes           (armazenamento, transporte, manutencao, descarte)
│   ├── Valorizacao         (condicoes financeiras)
│   ├── Documentos e Imagens
│   └── Aplicacao LMR
└── Especifico do tipo de material
    └── Caracteristicas Tecnicas  ← vem do PDM, muda a cada tipo
```

> [!note] Por que "Valorização" e uma seção separada aqui
> No portal, as condições financeiras aparecem **dentro** da seção de Condições.
> Neste cofre elas são tratadas a parte porque, no processo do CMI, essa parte
> **envolve outra área da GE** e não vem do fornecedor. Separar reflete a realidade
> operacional, não a tela do portal. Ver [[Secao - Valorizacao]].

## As seções, em detalhe
- [[Secao - Informacoes Gerais]]
- [[Secao - Caracteristicas Tecnicas]]
- [[Secao - Condicoes]]
- [[Secao - Valorizacao]]
- [[Secao - Documentos e Imagens]]
- [[Secao - Aplicacao LMR]]

## O ciclo de criação

1. **Criar a ficha no portal.** Operação simples. O slide 13 e explicito:
   *"Apenas com a criação da ficha e suficiente para a geração do código PMIB
   necessário para incluir no MTA."* — ou seja, o [[Codigo PMIB]] nasce cedo, antes
   do preenchimento.
2. **Gerar a [[Planilha PMIB]]** — extrato em Excel dos campos daquele PDM.
3. **Enviar ao fornecedor**, que preenche e devolve com datasheets, catalogos e fotos.
4. **Subir o conteudo ao portal** — manualmente ou pelos módulos RPA do
   [[SIG-FT - Visao Geral|SIG-FT]].
5. **Valorização** e **Aplicação LMR** — feitas pelo CMI, não pelo fornecedor.
6. **Emitir para Itaipu**, que verifica e aprova.

## Quem verifica e aprova, do lado CMI

Do slide 20 da apresentação R5:
> Fica acordado que **o elaborador das FICHAS TÉCNICAS deve também fazer a emissão
> para ITAIPU**.

O slide reconhece o motivo: *"A verificação e aprovação das fichas técnicas pode se
transformar numa tarefa pesada assim como a própria criação"*. Ou seja, não ha uma
etapa de revisão independente formalizada — decisão consciente, tomada por volume.

> [!warning] O que isso custa
> Sem revisão independente, o erro do elaborador chega em Itaipu. As 3 fichas em
> `FICHAS EM CORRECAO` e as devolucoes registradas em observacoes da mapeadora
> ("Fichas pendentes para devolucao e ajuste") são o sintoma.
> O módulo **Analyzer** do SIG-FT existe para cobrir esse buraco com validação
> automática. Ver [[SIG-FT - Modulos]].

## Prioridade de criação — questão aberta

O slide 19 registra, marcado como *"em discussão com Itaipu"*:
> O trabalho de criação e preenchimento das fichas técnicas e pesado.
> Necessário definir prioridade na criação das Fichas Técnicas. **Quem indica a prioridade?**

Segue sem resposta. Ver [[Diagnostico - Deficiencias]].

## O template Excel

`Box/15 - PDM/Templates/Ficha Tecnica do PDM-R3.xlsx`, aba **"Ficha Técnica Padrão"**.
Existe versão em espanhol: `Technical Sheet of PDM-R3.xlsx`.

Layout (posições que o SIG-FT usa como contrato — ver `sigft/core/rpa/ficha_layout.py`):

| Linha | Bloco |
|---|---|
| 4 | INFORMAÇÕES GERAIS |
| 6 | Texto Breve do Material (H6) · Origem |
| 8 | Un. medida de estoque |
| 10-12 | Tipo de Fabricacao (Série/Especial) · Fabricante · Tipo (Reparavel/Não reparavel) · Vida útil |
| 15 | CONDIÇÕES DE ARMAZENAMENTO |
| 17-21 | Dimensões da embalagem unitaria · Peso liquido e bruto · Sujeito a intemperies |
| 23 | Controle de temperatura e umidade |
| 25-29 | Posição (Vertical/Horizontal/Indiferente) · Proteção (Sem necessidade / UV / Eletrostatica) |
| 31-33 | Nocivo · cuidados |
| 35-36 | Empilhamento (qtd. maxima) · outros cuidados |
| 40 | CONDIÇÕES DE TRANSPORTE E MOVIMENTACAO |
| 42, 45 | Embalagem para transporte · Posições e cuidados com icagem |
| 50 | CONDIÇÕES DE MANUTENÇÃO |
| 52-56 | Preservacao · Métodos de limpeza/secagem · Ferramentas necessarias |
| 61 | CONDIÇÕES DE DESCARTE |
| 63-70 | Legislacao/Norma · Tipo de descarte · **NBR 10004** (Classe I Perigoso / Classe II Não perigoso) · Logistica reversa |
| 75-76 | ESPECIFICAÇÕES TÉCNICAS · Função do material |
| **79+** | **as perguntas do PDM** — coluna C-L pergunta, M-V resposta |

A linha **79** e o marco: dali para baixo o conteudo **muda conforme o PDM**.

## Relacionados
[[PDM - Padrao de Descricao de Material]] · [[Planilha STATUS_PMIB]] · [[SIG-FT - Modulos]]
