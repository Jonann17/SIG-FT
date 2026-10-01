---
tags: [processo, ficha, secao]
---

# Seção — Condições

Quatro abas no portal, todas alimentadas pelo fornecedor via [[Planilha PMIB]].
Base normativa: [[Anexo I - Classificacao de Materiais Sobressalentes]] item **1.1.3**.

## 1. Condições de Armazenamento (template linhas 15-36)

| Campo | Célula | Origem no Anexo I |
|---|---|---|
| Comprimento / Largura / Altura da embalagem unitaria | H17, H19, H21 | 1.1.2 dimensões |
| Peso liquido / bruto (kg) | P17, P19 | 1.1.2 |
| Sujeito a intemperies? | R21/T21 | 1.1.3-g |
| Necessidade de controle de temperatura e umidade | M23 | 1.1.3-a e 1.1.3-b |
| Posição de armazenamento | G25/G27/G29 — Vertical / Horizontal / Indiferente | 1.1.3-e |
| Proteção | T25/T27/T29 — Sem necessidade / Raios Ultravioletas / Eletrostatica | 1.1.3-c e 1.1.3-f |
| Nocivo | F31 / F33 — não contém agentes nocivos / prejudicial (descrever cuidados) | 1.1.3-f |
| Empilhamento (qtd. maxima) | C35 | 1.1.3-i |
| Outros cuidados | C36 | — |

## 2. Condições de Transporte e Movimentacao (linhas 40-45)
- **Embalagem para transporte** — tipo e cuidados (1.1.3-h)
- **Posições e cuidados com icagem** — posição e procedimento sumario

## 3. Condições de Manutenção (linhas 50-56)
- **Cuidados durante a preservacao**
- **Métodos de limpeza ou secagem**
- **Ferramentas e equipamentos necessarios para preservacao**

## 4. Condições de Descarte (linhas 61-70)
Base: Anexo I 1.1.3-j (legislacao ambiental brasileira e paraguaia).

- **Tipo de legislacao e/ou Norma aplicada** (brasileira e paraguaia) ou melhores praticas
- **Tipo de descarte** segundo a legislacao aplicada
- **Classificação conforme NBR 10004**: Classe I (Perigoso) / Classe II (Não perigoso)
- **Logistica reversa**: Aplica / Não se aplica. Se aplica, explicar.

## A regra que a IA quase quebrou

> [!warning] REGRA 0 — fidelidade ao fornecedor
> O prompt de IA do módulo de Condições **mudou em 18-19/08/2026**. A versão antiga
> mandava *"enriquecer com legislacao"* e auto-corrigir a classificação NBR 10004.
> Resultado: **a IA inventou norma que o fornecedor não escreveu.**
>
> Hoje vale a **REGRA 0 (fidelidade ao fornecedor)**, soberana: a IA normaliza e
> formata o que o fornecedor disse, **não acrescenta o que ele não disse**.
> Fonte de verdade: `sigft/core/llm/prompts.py` -> `SYSTEM_CONDICOES`.

E o exemplo mais claro no projeto de por que automação com IA precisa de politica
explicita de fidelidade a fonte. Ver [[Diagnostico - Riscos]].

## Coluna de controle
No [[Planilha STATUS_PMIB]]: coluna **`CONDICOES`**.

## Automação
Módulo **Upload Condições**: extrai as células fixas da ficha, manda a IA estruturar,
e preenche as 4 abas no portal. Marca `COMPLETO` no `_STATUS_PMIB` ao terminar.
Ver [[SIG-FT - Modulos]].

## Relacionados
[[Anexo I - Classificacao de Materiais Sobressalentes]] · [[Secao - Valorizacao]]
