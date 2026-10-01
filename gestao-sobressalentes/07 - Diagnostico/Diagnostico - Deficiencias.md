---
tags: [diagnostico, core]
data_base: 2026-08-31
---

# Diagnostico — Deficiencias

> [!warning] Documento de trabalho, nao conhecimento permanente
> Contem numeros e situacoes de uma data especifica. O que descreve **como o processo
> funciona** mora no nucleo do cofre (`01` a `06`).


Levantamento com base nos números de **31/08/2026** ([[Panorama Quantitativo]]) e nos
documentos do processo. Cada item traz a **evidência**, não só a impressão.

---

## D1. Aplicação LMR — o gargalo declarado

| Evidência | |
|---|---|
| Cobertura | **93 de 1219 fichas (7,6%)** |
| Esforço por ficha | ~150 pontos de aplicação (aba de exemplo do RTA: 8.557 linhas / 57 fichas) |
| Lastro contratual | **nenhum** — não está na [[ET Geral 6047-20-T0018\|ET Geral]] |
| Template | **em negociação** — [[Revisao da Aplicacao LMR - Agosto 2026]] |
| Fichas já emitidas sem a seção | existem; universo ainda não levantado |

**O que faz doer**: e a única seção que depende de **desenho de projeto** e de
**engenharia do sistema**, não do fornecedor. Quando o item não está nos desenhos, o
fluxo manda "buscar suporte da engenharia do sistema" — uma dependência sem prazo.

**O agravante**: Itaipu pediu em 20/08/2026 **uma linha por ponto de aplicação** e a
**quantidade aplicada**. Se aceito, isso multiplica o volume do que já e o menor
indicador — e pode obrigar a **refazer o que já foi feito**.

> Existe um módulo dedicado a **apagar** todas as aplicações de uma ficha
> ([[SIG-FT - Modulos|Apagar LMR]]). Ter isso é a assinatura de um processo cujo
> critério ainda muda.

---

## D2. Gestão das Listas de Preços sem instrumento

| Evidência | |
|---|---|
| Mapeadora de listas de preço | **não existe** |
| Fluxo Aconex de aprovação SM.DT | **"a definir"** na ata de 23/06/2026 |
| Cobertura de valorização | **584 de 1219 (47,9%)** |

**Três problemas empilhados:**
1. Sem fluxo Aconex próprio, não ha estado de documento para rastrear.
2. Sem mapeadora, não se sabe **quais listas de preço existem, em que revisão, e quais
   faltam**. A rastreabilidade e só o código (código da lista + sequencial).
3. Quando a [[Lista de Sobressalentes|lista de sobressalentes]] muda de revisão, a
   lista de preços correspondente **deveria** ser revisada — e **não ha gatilho**.

**Multiplicador**: a valorização envolve **outra área da GE**. Quem preenche o resto da
ficha não controla essa etapa e não tem visibilidade dela.

Ver [[Lista de Precos]] e [[Secao - Valorizacao]].

---

## D3. Listas de sobressalentes sem padrão de formato

**Evidência direta**, slide 21 da apresentação R5:
> As listas de sobressalentes **não estão seguindo um padrão** de formato e informações.

**Evidência indireta, e mais cara**: o `PLANO_REFATORACAO.md` do SIG-FT lista
**~10 implementacoes diferentes de "busca dinâmica da linha de cabeçalho"** como a
duplicacao número 1 da camada Excel.

> [!important] Isso não e divida técnica — e divida de processo
> O código esta complicado **porque a entrada e imprevisivel**. Padronizar a lista na
> origem elimina 10 pedacos de código defensivo de uma vez. Atacar pelo código trata o
> sintoma.

---

## D4. A lista se move e nada avisa

A nota 1 do slide 12 obriga: *"Toda atualização da lista de sobressalentes após a
aprovação deverá ter seus itens atualizados conforme a última versão."*
E o [[Capitulo 18 - Pecas de Reposicao e Sobressalentes|Capítulo 18]] obriga rever
quantidade e tecnologia se houver mudança tecnológica.

**O que falta**: um gatilho. Quando a lista muda de revisão, ninguém e avisado de que
o `_STATUS_PMIB` daquela lista ficou defasado, nem de quais itens sairam, entraram ou
mudaram de quantidade.

O SIG-FT resolve **meio** problema: o módulo Gestão PMIB renomeia o arquivo pelo
Tracking ID do Aconex quando o código muda. Mas **não compara o conteudo** da lista
nova com o da anterior.

---

## D5. Mais da metade das listas não começou

| `SITUACAO NO PMIB` | Listas |
|---|---|
| **INICIAR** | **54 de 94 (57%)** |
| EM ANÁLISE ITAIPU | 11 |
| FICHAS CRIADAS | 8 |
| EM PROCESSO DE PREENCHIMENTO | 8 |
| demais | 13 |
| **FINALIZADO** | **1** |

Ao mesmo tempo, **54 listas tem `STATUS REAL = APROVADO`**. Ou seja: ha lista aprovada
pela engenharia esperando o trabalho de ficha começar.

E o slide 19 registra a pergunta que ainda não tem dono:
> Necessário definir prioridade na criação das Fichas Técnicas. **Quem indica a prioridade?**

Sem critério de prioridade, a fila e atendida por pressão, não por valor.

---

## D6. Campos de gestão em branco na mapeadora

De 94 listas:

| Coluna | Em branco |
|---|---|
| `ENTREGA` | **64** (68%) |
| `ORIGEM FORNECEDOR` | 48 vazias + 22 com `-` = **70** |
| `RESPONSAVEL` | **37** (39%) |

E entre as preenchidas, `ENTREGA` traz valores que são **lembrete, não dado**:
`Atualizar data` (11), `Informar data` (8), `Reprogramar` (1).

> [!warning] O efeito
> A mapeadora e a fonte da visão macro. Campo em branco não e "sem informação" — na
> prática vira **"não sabemos"**, e some do radar. Uma lista sem responsável e uma
> lista que ninguém esta puxando.

---

## D7. Sem revisão independente das fichas

Do slide 20:
> Fica acordado que **o elaborador das FICHAS TÉCNICAS deve também fazer a emissão para
> ITAIPU**.

A decisão foi consciente, tomada por volume. O custo aparece do outro lado:
- fichas devolvidas por Itaipu (`FICHAS EM CORRECAO`)
- observacoes na mapeadora como *"Fichas pendentes para devolucao e ajuste"*,
  *"71/77 fichas reenviadas para o fornecedor complementar"*
- **taxa de aprovação de 12,7%** (57 aprovadas contra 449 em análise)

O módulo [[SIG-FT - Modulos|Analyzer]] existe justamente para cobrir esse buraco com
validação automática — mas não substitui um segundo par de olhos sobre critério.

---

## D8. O vocabulario de status cresceu além do controle

A aba `Dropbox` da mapeadora define **7 valores** validos para `SITUACAO NO PMIB`.
Na coluna real aparecem **10**, e nenhum deles bate exatamente com a lista:

| No dropdown | Na coluna |
|---|---|
| INICIAR, PRE-CADASTRO EM PROCESSO, PRE-CADASTRO COMPLETO, PARCIALMENTE EM ANÁLISE IB, EM ANÁLISE IB, FASE DE CORREÇÃO, APROVADO | INICIAR, EM ANÁLISE ITAIPU, FICHAS CRIADAS, EM PROCESSO DE PREENCHIMENTO, FORNECEDOR / ELABORAÇÃO, FICHAS COM O FORNECEDOR, EM PROCESSO / ANÁLISE ITAIPU, FINALIZADO, CORREÇÃO / ELABORAÇÃO, SEM LISTA |

Consequência: **filtro e contagem por status não são confiaveis**, e comparacao entre
periodos fica ambigua.

---

## D9. Fichas órfãs

A pasta `09 - SEM LISTA ASSOCIADO` contém `Fichas_criadas/` e `Fichas_recebidas/`,
e a mapeadora tem uma linha inteira com `SEM LISTA`.

São fichas que existem **sem lista de sobressalentes correspondente** — criadas antes
ou fora do processo formal. Como o [[Codigo PMIB]] delas já pode ter ido para o MTA,
desfazer não e trivial.

---

## D10. Material parado no almoxarifado errado

A regra e explicita (slide 16 e Capítulo 18): sobressalente vai **direto ao almoxarifado
de Itaipu**, sem passar pelo do CMI.

Na mapeadora, **5 listas** estão com `ENTREGA = ALMOXARIFADO CMI`, com observacoes como
*"O material está no almoxarifado do CMI esperando..."*.

Não e violacao deliberada — e material aguardando **autorização de entrega**, que
depende da ficha estar completa. Mas o efeito e estoque parado fora do lugar previsto,
e **93 fichas em `ATRASO DE AUTORIZACAO DE ENTREGA ITAIPU`**.

---

## D11. Concentracao de conhecimento

| Ativo | Quem sustenta |
|---|---|
| SIG-FT (13 módulos, 36k linhas) | 1 dono + 1 colaborador em 1 módulo |
| Mapeadora e sua lógica de agregação | equipe PDM |
| Critério da Aplicação LMR | conhecimento tacito, em negociação |
| Leitura do RDS-PP | engenharia dos sistemas |

Este cofre e a primeira mitigacao. Mas o SIG-FT contínua sendo um app desktop com
**um** mantenedor principal, operando um portal que muda sem aviso.

---

## D12. Divergencias de fonte de verdade

| Divergência | Onde |
|---|---|
| Catalogo de PDM: `1174` vs `1193` | dois arquivos na raiz de `15 - PDM` |
| Prazo de autorização: 14 / 19 / 15 d.u. | slides 9, 10-11 e 12 da mesma apresentação |
| Motor de RPA: Selenium x Playwright | `README.md` diz fallback Selenium; `docs/base-conhecimento/09-motor-de-rpa.md` (28/08) diz removido no CP 5.5; **o código não tem `selenium_engine.py`** |
| `ATRASO DE AUTORIZACAO`: fichas ou dias? | não documentado |
| Dashboard Power BI x mapeadora | duas visões macro, sem garantia de mesma fonte |

Cada uma dessas e pequena. Juntas, corroem a confianca no número — e quando o número
não e confiável, a decisão volta a ser por impressão.

---

## Ranking por impacto

| # | Deficiencia | Impacto | Esforço de correção |
|---|---|---|---|
| 1 | [[#D1. Aplicação LMR — o gargalo declarado\|D1 — LMR]] | **alto** — trava emissão e pode gerar devolucao em massa | alto |
| 2 | [[#D2. Gestão das Listas de Preços sem instrumento\|D2 — Listas de Preço]] | **alto** — trava valorização, sem visibilidade | **baixo** |
| 3 | [[#D5. Mais da metade das listas não começou\|D5 — 57% em INICIAR]] | alto — cronograma | medio (e decisão, não trabalho) |
| 4 | [[#D3. Listas de sobressalentes sem padrão de formato\|D3 — sem padrão]] | medio — custo contínuo | medio |
| 5 | [[#D6. Campos de gestão em branco na mapeadora\|D6 — campos em branco]] | medio — cegueira gerencial | **baixo** |
| 6 | [[#D4. A lista se move e nada avisa\|D4 — lista movel]] | medio — retrabalho silencioso | medio |
| 7 | [[#D8. O vocabulario de status cresceu além do controle\|D8 — vocabulario]] | baixo-medio | **baixo** |
| 8 | [[#D12. Divergencias de fonte de verdade\|D12 — divergencias]] | baixo-medio | **baixo** |

O plano está em [[Diagnostico - Plano de Melhoria]].

## Relacionados
[[Diagnostico - Riscos]] · [[Panorama Quantitativo]] · [[Indicadores e Como Ler]]
