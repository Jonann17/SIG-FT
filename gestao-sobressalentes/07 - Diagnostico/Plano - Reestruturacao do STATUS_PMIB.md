---
tags: [plano, status-pmib, migracao, handoff]
status: aguardando-aprovacao
criado: 2026-10-04
atualizado: 2026-10-04 (decisões do Luan: sem data da entrega, sem fórmulas, sem aba de feriados, comentários preservados)
destinatario: Luan e a próxima conversa que for executar
---

# Plano — Reestruturação do `_STATUS_PMIB` (layout v2)

> [!info] Para quem vai executar
> Autocontido. Contexto maior em [[README]] e [[Plano - Sistema de Gestao v2]].
> Scripts prontos em `_gestao_v2/`: `migrar_status_pmib_v2.py` (a migração) e
> `xlsx_cirurgico.py` (o editor que não apaga nada). **Nada foi aplicado no Box ainda.**

## 0. Em uma frase

Acrescentar a cada `_STATUS_PMIB` as colunas de **tipo de entrega, fornecedor, procurement,
data da autorização e situação da autorização de Itaipu** — **sem perder nada** (dado,
comentários, histórico de versões no Box, listas suspensas) — e passar ao **SIG-FT** todo o
cálculo, que hoje não existe no Excel e não vai existir.

## 1. Decisões do Luan (04/10/2026)

| Decisão | Consequência |
|---|---|
| **Sem DATA DA ENTREGA** — quase nunca se sabe | coluna fora; continua o `EQUIPAMENTO ENTREGUE` (SIM/NÃO) |
| **Nenhum cálculo no Excel** — todo cálculo vem do SIG-FT quando roda | PRAZO, SITUAÇÃO e DIAS DE ATRASO são **valores** gravados pelo SIG-FT; nada de fórmula |
| **Sem aba de feriados** — o calendário é do SIG-FT | feriados em `sigft/config.py`; o Power BI também não calcula dias úteis, só lê |
| **Comentários são importantes** | nada de salvar com openpyxl: edição cirúrgica do arquivo (seção 3) |
| DUPLICADO (status) = item repetido **na mesma lista**; ficha duplicada de outro sistema = `PDM.9900.000` + PMIB da original em OBSERVAÇÕES | a migração não mexe em nenhum dos dois |

## 2. O que muda em cada arquivo

**Nada que existe muda de nome ou de lugar.** Bloco novo à direita da última coluna (em geral
a partir da **U**; nos 4 arquivos com anotações soltas à direita, depois delas):

| Coluna nova | Quem preenche | Lista suspensa / regra |
|---|---|---|
| **TIPO DE ENTREGA** | pré-preenchido pela lista de preços (por PMIB); o resto, quem cria a ficha | `FÍSICA E DOCUMENTAL` · `DOCUMENTAL` · `TÍTULO` |
| **FORNECEDOR** | quem cria a ficha (empresa que vendeu ao CMI, não o fabricante) | texto |
| **PROCUREMENT** | pré-preenchido pela mapeadora quando a lista tem uma pessoa só | lista que aceita nome novo |
| **DATA DA AUTORIZAÇÃO ITAIPU** | e-mail de autorização, ou o script de aptos (data do export) | data |
| PRAZO AUTORIZAÇÃO ITAIPU (15 D.U.) | **SIG-FT** | valor: data do e-mail + 15 dias úteis |
| SITUAÇÃO DA AUTORIZAÇÃO | **SIG-FT** | AGUARDANDO ITAIPU · ATRASADO ITAIPU · AUTORIZADO NO PRAZO · AUTORIZADO COM ATRASO · AUTORIZADO |
| DIAS ÚTEIS DE ATRASO | **SIG-FT** | dias úteis além do prazo (até a data do cálculo, ou até a autorização) |

As três do SIG-FT mostram, ao clicar, a mensagem "Preenchido pelo SIG-FT — não digitar".

Mais:
- **vocabulários** das listas suspensas na aba **Checklist**, à direita do que já existe, com os
  nomes definidos `lst_status`, `lst_secao`, `lst_simnao`, `lst_tipo_entrega`, `lst_procurement`;
- **listas suspensas por nome definido** em STATUS, nas seis seções, APTO, EQUIPAMENTO ENTREGUE e
  nas colunas novas (as antigas, que apontavam para outra aba, são substituídas);
- título mesclado estendido até o fim do bloco; nome definido `versao_layout_status_pmib = "v2"`.

Sem aba nova, sem fórmula, sem formatação condicional nova.

## 3. Como não perder nada — o editor cirúrgico

### O problema
O SIG-FT e o primeiro script gravavam com **openpyxl**, que reescreve o arquivo inteiro com o
que entende e **apaga** o resto. Testado: um salvamento pelo openpyxl apaga os **comentários em
thread** (autor, data, respostas — 16 arquivos têm) e as **listas suspensas que apontam para outra
aba** (22 arquivos ainda têm; as dos outros já sumiram assim).

### A solução: `_gestao_v2/xlsx_cirurgico.py`
Um `.xlsx` é um pacote (zip) de partes XML. O editor abre o pacote, **altera só três partes** —
a aba "Lista de Materiais", a aba "Checklist" e a lista de nomes (`xl/workbook.xml`) — e regrava
**todas as outras exatamente como estavam, byte a byte**: comentários em thread, pessoas,
anotações, desenhos, estilos, configurações de impressão. Usa `lxml`; não precisa de Excel, roda
em qualquer máquina.

| Garantia | Como é conferida (automático, arquivo por arquivo) |
|---|---|
| Partes não editadas idênticas | comparação byte a byte com o original |
| Nenhuma célula existente mudou | comparação célula a célula (valor e fórmula) |
| Comentários em thread, anotações, formatação condicional e desenhos | contados antes e depois — têm de ser iguais |
| O SIG-FT ainda acha o cabeçalho | mesma busca que ele faz (`CÓDIGO DO MATERIAL` nas 10 primeiras linhas) |
| As listas suspensas sobrevivem ao SIG-FT de hoje | o arquivo migrado é salvo de novo pelo openpyxl e as listas continuam lá |
| Arquivo íntegro | aberto e reconvertido pelo LibreOffice (`--libreoffice`) |
| Histórico do Box | grava **por cima do mesmo arquivo** (nunca apaga, renomeia ou move): o Box registra versão nova |

### Simulação de 04/10/2026 (cópias, fora do Box)
**47 de 47 migrados, nenhuma perda**, inclusive os 16 com comentário em thread; todos abrem no
LibreOffice; 598 TIPO DE ENTREGA e 1.006 PROCUREMENT pré-preenchidos. Com `--calcular`, a
gravação de prazo/situação/atraso como valores foi conferida em Inversores e PDE (32 atrasadas,
16 autorizadas; linhas DUPLICADO em branco).

> [!warning] Falta um teste que só o Excel faz
> O LibreOffice é mais tolerante que o Excel. O **piloto (Etapa 3) tem de abrir o arquivo no
> Excel** e confirmar que não aparece "Encontramos um problema em algum conteúdo".

## 4. O SIG-FT passa a fazer o cálculo — e a gravar sem apagar

| # | Mudança no SIG-FT | Detalhe |
|---|---|---|
| S1 | **Calcular e gravar** PRAZO, SITUAÇÃO e DIAS DE ATRASO em cada `_STATUS_PMIB` quando o Gestão PMIB roda | regra: `_scripts/regras_sobressalentes.py` → `situacao_autorizacao()`; modelo pronto de gravação: `gravar_calculos()` em `migrar_status_pmib_v2.py`. Linha DUPLICADO fica em branco |
| S2 | **Feriados em `sigft/config.py`** | prazo = `np.busday_offset(data, 15, roll="backward", holidays=FERIADOS)` — testado igual ao Excel em 1.500 datas; com `roll="forward"` erra |
| S3 | **Gravar a data do cálculo** | nome definido `sigft_calculado_em` no próprio arquivo (o Power BI mostra "calculado em") |
| S4 | **Parar de salvar `_STATUS_PMIB` com openpyxl** em todos os módulos que escrevem nele (Criar Fichas, Upload Condições, Upload Specs, Cadastro LMR, Ficha Duplicada, script de aptos) | trocar o `wb.save()` por `PlanilhaXlsx.escrever()` + `salvar()` do editor cirúrgico. Ler com openpyxl continua permitido |
| S5 | Script de aptos: ao virar APTO = SIM, gravar **DATA DA AUTORIZAÇÃO ITAIPU** | data do export `sobressalentes_autorizados_AAAAMMDDhhmm` |
| S6 | Coluna `ATRASO` da mapeadora com a mesma regra | contar SITUAÇÃO = ATRASADO ITAIPU |

Até S4 estar feito, **cada salvamento do SIG-FT continua apagando os comentários em thread**
daquele arquivo (as listas suspensas, não mais — depois da migração elas sobrevivem). Enquanto
isso, a regra de processo sugerida é usar **Anotação** (nota) em vez de **Comentário**.

## 5. Execução, passo a passo

### Etapa 0 — Decisões pendentes
- [ ] Aprovar o layout da seção 2.
- [ ] Calendário dos 15 d.u. no SIG-FT: feriados nacionais BR + Carnaval e Corpus Christi? Paraguai? Foz?
- [ ] Até o S4: usar Anotação em vez de Comentário nos `_STATUS_PMIB`?

### Etapa 1 — Preparação
- [ ] Avisar a equipe: ninguém com `_STATUS_PMIB` aberto e **SIG-FT parado** durante a migração.
- [ ] Box sincronizado; nenhum `~$...` (trava do Excel) nas pastas.
- [ ] Sala Segura: a lista de preços vigente só existe como `ST00=U01&MPB021 - Copy.xlsm` — voltar ao
      nome oficial `#ST00=U01&MPB021.xlsm`, senão os 199 itens ficam sem TIPO DE ENTREGA pré-preenchido.
- [ ] Python 3.12 com `openpyxl`, `pandas`, `lxml`; cópia deste pacote (GitHub ou Box).

### Etapa 2 — Simular (não toca no Box)
```bash
python _gestao_v2/migrar_status_pmib_v2.py --simular --libreoffice
```
- [ ] `relatorio_migracao.csv`: coluna `problemas` toda "—".
- [ ] Abrir no **Excel** 3 cópias migradas, uma delas com comentário em thread (ex.: Banco de
      Baterias): sem aviso de reparo; comentários com autor e respostas; listas suspensas funcionando.

### Etapa 3 — Piloto numa lista
```bash
python _gestao_v2/migrar_status_pmib_v2.py --aplicar --so "B03BDV10UC012"
```
(Gerador Diesel › PDG: pequeno, com e-mails e atrasos reais.)
- [ ] Abrir no Excel; conferir bloco, listas suspensas, nada de aviso de reparo.
- [ ] Rodar o SIG-FT (Gestão PMIB) e reabrir: as listas suspensas continuam?
- [ ] No Box (web): versão nova registrada, anteriores disponíveis.

### Etapa 4 — Aplicar nos demais
```bash
python _gestao_v2/migrar_status_pmib_v2.py --aplicar
```

### Etapa 5 — Template
- [ ] Copiar `_gestao_v2/template/codigo_itaipu_STATUS_PMIB_v2.xlsx` para `Templates/` com o nome
      oficial; o antigo vai para `Templates/Obsoleto/`.

### Etapa 6 — SIG-FT (seção 4: S1 a S6)
Até S1 existir, dá para preencher as colunas uma vez com `--calcular` (mesma regra), sabendo que
ficam paradas até a próxima rodada.

### Etapa 7 — Preencher o que ficou vazio
- [ ] TIPO DE ENTREGA das fichas sem lista de preços com a coluna.
- [ ] FORNECEDOR e PROCUREMENT nas listas com mais de um fornecedor.
- [ ] DATA DA AUTORIZAÇÃO daqui para frente (ou automática, S5).

## 6. Como desfazer

1. **Pelo backup**: copiar o arquivo de `%LOCALAPPDATA%\Sobressalentes-v2\backup_...\` **por cima**
   do arquivo no Box — mesmo nome, mesmo lugar.
2. **Pelo Box**: no navegador, arquivo › Versões › restaurar a anterior.

Nunca apagar o arquivo migrado para "pôr o antigo no lugar": quebra o histórico de versões.

## 7. Critérios de pronto

- [ ] Relatório sem `problemas` em todos os arquivos.
- [ ] Piloto aberto no **Excel** sem aviso de reparo; comentários em thread intactos.
- [ ] Listas suspensas presentes depois de o SIG-FT salvar o arquivo.
- [ ] Versões anteriores visíveis no Box.
- [ ] Template v2 em `Templates/`.
- [ ] SIG-FT gravando prazo/situação/atraso (S1) sem openpyxl (S4).
- [ ] Power BI lendo as colunas do SIG-FT (`_gestao_v2/powerbi/03 - Itens.pq`).

## 8. Pendências encontradas na simulação

| Pendência | Onde |
|---|---|
| Lista de preços vigente da Sala Segura só existe como `- Copy` | `02 - INFRAESTRUTURA COMPLEMENTAR/SALA SEGURA/` |
| 2 linhas `DUPLICADO` sem a linha original (1 sem PMIB) | SFC HF-01/02 (item 39); RV parte hidráulica (item 15, `.0794`) |
| 3 fichas `PDM.9900.000` sem o PMIB da original em OBSERVAÇÕES | PVA (`.1237`), HPU da comporta (`.1180`) e mais 1 |
| 127 fichas com STATUS `N/A` (126 na Sala Segura) | provável `FICHA CRIADA` |
| Anotações soltas à direita da tabela em 4 arquivos | o bloco v2 começa depois delas |

## Relacionados
[[README]] · [[Plano - Sistema de Gestao v2]] · [[Planilha STATUS_PMIB]] · [[Ciclo de Vida de um Item]] · [[findings]]
