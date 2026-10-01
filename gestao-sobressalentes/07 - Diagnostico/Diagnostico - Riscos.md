---
tags: [diagnostico, riscos]
---

# Diagnostico — Riscos

> [!warning] Documento de trabalho, nao conhecimento permanente
> Contem numeros e situacoes de uma data especifica. O que descreve **como o processo
> funciona** mora no nucleo do cofre (`01` a `06`).


Diferente das [[Diagnostico - Deficiencias|deficiencias]] (que já doem), estes são
eventos que **ainda não aconteceram** ou aconteceram uma vez e podem repetir.

---

## R1. Retroatividade do critério de Aplicação LMR — ~~ATIVO~~ ENCERRADO
**Encerrado em 31/08/2026**

> [!success] Itaipu aceitou o modelo do CMI
> O critério está fechado. O risco de ter que refazer LMR por mudança de definição
> deixou de existir, e o trabalho já feito esta preservado.

Registro do que era: a revisão de 20/08/2026 pedia uma linha por ponto de aplicação e a
quantidade aplicada; havia o risco de as 93 fichas já finalizadas terem de ser refeitas.
**Não se materializou.**

O risco que sobra e de **capacidade**, não de critério — ver R2 e
[[Levantamento - Fichas sem Aplicacao LMR]].

---

## R2. Devolucao em massa de fichas emitidas sem LMR
**Probabilidade: ALTA · Impacto: alto · agora quantificado**

**413 fichas já foram emitidas a Itaipu sem Aplicação LMR completa, em 14 listas.**
Com o critério agora **aceito** (R1 encerrado), a exigencia esta consolidada — o que
aumenta, não diminui, a chance de essas fichas serem apontadas.

Com 2-3 meses de ciclo de análise, uma devolucao em bloco custa um trimestre e atinge
eventos de pagamento de **2823 a 2842**.

**Mitigacao em andamento**: universo levantado em
[[Levantamento - Fichas sem Aplicacao LMR]]. Falta o plano de ação com prazos, que será
apresentado a Itaipu **antes** de ser cobrado.

---

## R3. A IA preencher o que a fonte não disse
**Probabilidade: média · Impacto: alto · JÁ ACONTECEU**

Até 18/08/2026 o prompt de Condições mandava enriquecer com legislacao. A IA
**preencheu norma ambiental (NBR 10004) que o fornecedor não declarou**.

Num processo onde a ficha e documento contratual entregue a um cliente binacional e a
seção de descarte referência legislacao brasileira e paraguaia, isso é material.

**Mitigacao já aplicada**: **REGRA 0 — fidelidade ao fornecedor**, soberana.
**Mitigacao a manter**: todo prompt novo deve declarar explicitamente o que a IA **não**
pode inventar. Ver [[SIG-FT - Camada de IA]].

---

## R4. Requisitos da ET que a operação não cumpre como escrito
**Probabilidade: baixa de cobranca · Impacto: alto se cobrado**

| Requisito da ET | O que se faz |
|---|---|
| Dados **extraidos do modelo 3D BIM** (Cap. 18 e Anexo I 1.1) | dados vem do fornecedor pela [[Planilha PMIB]] |
| Informar **quantidade instalada na Usina** (Anexo I 1.1) | e o que a LMR tenta responder — cobertura de 7,6% |
| PDMs novos submetidos a **ETIM e bSDD no início do projeto** (Anexo III) | solicitados item a item, ao longo do projeto |
| Lista **única por Unidade Funcional** (Cap. 18) | uma lista por sistema; idênticos tratados depois como [[Fichas Duplicadas\|duplicadas]] |

Nenhum desses foi cobrado formalmente até hoje. Mas estão escritos, e a Aplicação LMR
— que **não** esta escrita — já e cobrada. **O que não está na ET pode ser exigido;
o que esta pode voltar.**

**Mitigacao**: registrar por escrito o entendimento acordado sobre cada um, para não
depender de memória de reunião.

---

## R5. Excel como banco de dados
**Probabilidade: alta · Impacto: medio**

Todo o controle vive em `.xlsx`: `_STATUS_PMIB` por lista, mapeadora por projeto.

Fragilidades já materializadas no código:
- **`PermissionError`** quando alguém está com a planilha aberta — o SIG-FT tem retry
  em 4 variantes diferentes
- **zeros perdidos** no [[Codigo PMIB]] — normalização em 6 lugares
- **cabeçalho em linha variável** — busca dinâmica em ~10 lugares
- **sem controle de concorrencia**: duas pessoas editando o mesmo `_STATUS_PMIB`, a
  última gravacao vence, em silêncio

**Mitigacao de curto prazo**: convencao de quem edita o que, e sempre fechar a planilha.
**De medio prazo**: ver [[Diagnostico - Plano de Melhoria]] M6.

---

## R6. O portal PMIB muda sem aviso
**Probabilidade: média · Impacto: alto**

O PMIB e OutSystems, do cliente. Não ha API, não ha contrato de interface, não ha
changelog. Toda a automação de RPA depende de seletores.

O `docs/PORTAL_COMO_ELE_SE_COMPORTA.md` já cataloga sete comportamentos que custaram
rodadas de desenvolvimento — incluindo a **recusa silenciosa**, em que o portal aceita
o clique e não grava.

**Mitigacao já aplicada**: `PMIBPortal` isola todo o conhecimento do portal num arquivo.
**A manter**: nunca declarar módulo de RPA pronto sem execução real. Suite verde não e
prova de portal.

---

## R7. Bus factor
**Probabilidade: média · Impacto: alto**

O SIG-FT tem 36 mil linhas e **um** mantenedor principal. A lógica da mapeadora, o
critério de LMR e a leitura do RDS-PP são, em boa parte, conhecimento tacito.

**Mitigacao em curso**: este cofre + a `docs/base-conhecimento/` do repositorio.
**Faltando**: um segundo operador treinado nos módulos de RPA.

---

## R8. Duas visões macro divergindo
**Probabilidade: média · Impacto: baixo-medio**

Existem a mapeadora e o `Sobressalentes - Dashboard.pbix`. Se o Power BI lê os
`_STATUS_PMIB` diretamente em vez da mapeadora, as duas visões podem divergir sem que
ninguém perceba — e reunião com dois números diferentes queima credibilidade do dado.

**Mitigacao**: confirmar a fonte do `.pbix` e, se for o caso, aponta-lo para a mapeadora.

## Relacionados
[[Diagnostico - Deficiencias]] · [[Diagnostico - Plano de Melhoria]]
