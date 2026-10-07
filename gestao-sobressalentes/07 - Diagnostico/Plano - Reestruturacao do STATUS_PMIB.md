---
tags: [plano, status-pmib, migracao, handoff]
status: executado
criado: 2026-10-04
atualizado: 2026-10-04 (layout definitivo do Luan; aplicado nos 47 _STATUS_PMIB e no template)
destinatario: Luan e a próxima conversa
---

# Plano — Reestruturação do `_STATUS_PMIB` (layout v2) — EXECUTADO

> [!success] Aplicado em 04/10/2026, por autorização do Luan
> Os **47 `_STATUS_PMIB`** e o template `Templates/codigo_itaipu_STATUS_PMIB.xlsx` estão no layout v2.
> Conferência automática sem nenhuma perda; os 47 abrem no LibreOffice; o que foi gravado no Box é
> idêntico, byte a byte, às cópias conferidas. Backup dos originais:
> `%LOCALAPPDATA%\Sobressalentes-v2\backup_20261004-2342` (máquina pessoal do Luan) + histórico de versões do Box.

## 1. O layout (definido pelo Luan em 04/10/2026)

Da `APLICAÇÃO - LMR` em diante:

```
... | APLICAÇÃO - LMR | TIPO DE ENTREGA | DATA DO EMAIL COMUNICANDO ENTREGA |
      SITUAÇÃO DA AUTORIZAÇÃO | DIAS DE ATRASO | EQUIPAMENTO ENTREGUE |
      [extras da lista] | FORNECEDOR | PROCUREMENT | OBSERVAÇÕES | [extras]
```

e, acima do cabeçalho (que passou a ficar na **linha 5** em todas as listas):

```
REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: 0A - DATA DE ALTERAÇÃO: 03/09/2026
```

| Coluna | O que é | Quem preenche |
|---|---|---|
| **TIPO DE ENTREGA** (nova) | FÍSICA E DOCUMENTAL · DOCUMENTAL · TÍTULO | pré-preenchida pela lista de preços (598 linhas); o resto, quem cria a ficha |
| **SITUAÇÃO DA AUTORIZAÇÃO** (substituiu o APTO PARA ENTREGA, mesma coluna) | AGUARDANDO ITAIPU · ATRASADO ITAIPU · AUTORIZADO · N/A — **só FÍSICA E DOCUMENTAL precisa de autorização** (DOCUMENTAL/TÍTULO = N/A; tipo vazio = branco, não conta) | **SIG-FT** (15 dias úteis do e-mail); AUTORIZADO também à mão / pelo export de autorizados |
| **DIAS DE ATRASO** (nova) | dias **corridos** além do prazo de 15 dias úteis; congela quando Itaipu autoriza | **SIG-FT** |
| **FORNECEDOR** (nova) | empresa que vendeu ao CMI (não o fabricante) | quem cria a ficha |
| **PROCUREMENT** (nova) | quem compra | pré-preenchida pela mapeadora quando a lista tem uma pessoa só (1.006 linhas) |
| Linha da revisão (nova em 42 listas; 5 já tinham) | revisão da lista de sobressalentes que o arquivo reflete | quem reconcilia o arquivo com a lista nova; o SIG-FT copia para a mapeadora |

O que **não** entrou, por decisão do Luan: DATA DA AUTORIZAÇÃO (impraticável por ora), coluna de
PRAZO (o prazo é regra, não dado), DATA DA ENTREGA, qualquer fórmula, aba de feriados.

Também: vocabulários na aba **Checklist** (`lst_status`, `lst_secao`, `lst_simnao`,
`lst_tipo_entrega`, `lst_procurement`, `lst_situacao`) e **listas suspensas por nome definido** em
STATUS, seções, SITUAÇÃO, EQUIPAMENTO ENTREGUE, TIPO e PROCUREMENT — sobrevivem ao openpyxl do SIG-FT.
Nome definido `versao_layout_status_pmib = "v2"`.

### Valores gravados na migração
- `APTO = SIM` → `AUTORIZADO` (636 linhas — todas).
- Com e-mail e sem autorização: regra dos 15 d.u. em 04/10/2026 → 149 `AGUARDANDO ITAIPU`,
  55 `ATRASADO ITAIPU` (53 fichas) com DIAS DE ATRASO. Nenhuma delas consta no export de autorizados
  de 18/08/2026. A mais antiga: e-mail de 24/06/2025 (3 fichas de #ST00=M00MEU10&MPB020, 446 dias).
- Linha DUPLICADO não autorizada: em branco (a situação vale pela linha da ficha).
- **Correção de 05/10/2026** (Luan): ficha **DOCUMENTAL** não precisa de autorização de Itaipu — só o pai
  (FÍSICA E DOCUMENTAL) é entregue. Em #ST00=M00MEU10&MPB020, 61 linhas "AGUARDANDO ITAIPU" + 1 em branco
  passaram a `N/A` (`--recalcular --apenas-documental`; backup `backup_20261005-0808`; só essa lista tinha
  documentais com situação). Nenhuma das 53 atrasadas era documental; aguardando caiu de 149 para 88.
- **Correção 2 de 05/10/2026** (Luan): TÍTULO (agrupamento) e TIPO vazio também **não contam** — só FÍSICA E
  DOCUMENTAL. Nenhum dado gravado mudou (todas as AGUARDANDO/ATRASADO já eram físicas; nenhum TÍTULO nos arquivos).
- **Defeito corrigido em 05/10/2026**: a coluna DIAS DE ATRASO herdou o formato de **data** da vizinha (o antigo
  APTO) em 33 arquivos — 4 dias apareceriam como 04/01/1900. As 884 células passaram ao formato Geral (valor
  intocado; `--corrigir-formato-dias`, backup `backup_20261005-0829`, template incluído). A migração já faz isso.
- Linha da revisão: semeada com a `REVISÃO EM USO` da mapeadora; DATA DE ALTERAÇÃO = "—" (não se sabe).
- `#ST00=M00MEU10&MPB020`: a coluna "Fornecedor" que existia à direita de OBSERVAÇÕES (99 valores)
  foi **movida** para a FORNECEDOR nova; a coluna antiga ficou vazia.

## 2. Como foi feito sem perder nada

`_gestao_v2/xlsx_cirurgico.py` edita o pacote do `.xlsx` diretamente (lxml), sem openpyxl:

- **`deslocar()`** insere colunas e linhas como o "Inserir" do Excel: andam junto as células, as
  fórmulas (inclusive compartilhadas — conferidas e, se preciso, tornadas explícitas), mesclagens
  (o título cresce), validações (inclusive as de extensão x14), formatação condicional, filtro e
  ordenação, painel congelado, seleção, nomes definidos (área de impressão, títulos, filtro),
  comentários em thread + anotações + a caixa do comentário (VML), desenhos e a cadeia de cálculo.
  O que não souber deslocar, **recusa** (nunca desloca pela metade).
- Coluna inserida recebe a formatação da coluna à esquerda, como no Excel.
- Partes do arquivo não relacionadas saem byte a byte; comentários/VML/desenhos só têm os números de
  posição trocados. Grava **por cima do mesmo arquivo** (o Box registra versão nova).

### Conferência (automática, arquivo por arquivo — `conferir()`)
| Garantia | Como |
|---|---|
| Toda célula do original está no lugar novo, com o mesmo valor | célula a célula (fórmula: a deslocada); exceção prevista: APTO → SITUAÇÃO |
| Nada a mais | só as colunas novas, a SITUAÇÃO e a linha da revisão podem ter conteúdo novo |
| Ordem do cabeçalho | `LMR, TIPO, EMAIL, SITUAÇÃO, DIAS, ENTREGUE, …, FORNECEDOR, PROCUREMENT, OBSERVAÇÕES` |
| Mesclagens, formatação condicional, nomes definidos | o original deslocado = o migrado; sem mesclagens sobrepostas |
| Comentários e anotações | posições deslocadas; texto, autores e respostas idênticos |
| calcChain | toda entrada aponta para célula com fórmula |
| XML válido para o Excel | linhas e células em ordem crescente |
| O SIG-FT acha o cabeçalho e as colunas | mesma busca do `pmib_manager` (pandas, 10 primeiras linhas) |
| Listas suspensas sobrevivem ao SIG-FT de hoje | salva de novo com openpyxl e confere `lst_status`, `lst_tipo_entrega`, `lst_situacao` |
| Integridade | os 47 abertos e reconvertidos pelo LibreOffice |

## 3. Enquanto o SIG-FT não é corrigido (roteiro em [[Tarefa SIG-FT - Calculo e Gravacao sem Perda]])

| Situação | Efeito | Gravidade |
|---|---|---|
| Gestão PMIB não acha mais `APTO PARA ENTREGA` | escreve "Atualizar template" nas colunas APTO e ATRASO da mapeadora (é o aviso que ele já tinha) | visível, sem dano |
| Módulo PDM, modo "selecionar códigos", lê o cabeçalho fixo na linha 4 | "Coluna 'CÓDIGO PMIB' não encontrada" (já acontecia nas 5 listas com a linha de revisão) | visível, sem dano — T0 |
| `apto_para_entrega_att.py` (Box, `_python_pdm/SIG-FT/`) procura `APTO PARA ENTREGA` | "Falta coluna APTO" e não grava; marcar AUTORIZADO à mão até a T4 | visível, sem dano |
| Qualquer salvamento do SIG-FT com openpyxl | **continua apagando os comentários em thread** daquele arquivo — as listas suspensas, não mais | T1 resolve; até lá, preferir Anotação a Comentário |
| SITUAÇÃO / DIAS DE ATRASO | ficam com o valor de 04/10 até o SIG-FT recalcular (T2) | o Power BI mostra o que está gravado |

Tudo o mais no SIG-FT acha coluna pelo nome e o cabeçalho dinamicamente — inserir colunas no meio não
o faz gravar na coluna errada.

## 4. Como desfazer (um arquivo ou todos)

1. **Pelo Box** (qualquer máquina): arquivo › Versões › restaurar a anterior a 04/10/2026 23:42.
2. **Pelo backup** (máquina pessoal): copiar de `%LOCALAPPDATA%\Sobressalentes-v2\backup_20261004-2342\`
   **por cima** do arquivo no Box — mesmo nome, mesmo lugar. O template está lá como `TEMPLATE_codigo_itaipu_STATUS_PMIB.xlsx`.

Nunca apagar o arquivo migrado para "pôr o antigo no lugar": quebra o histórico de versões.

## 5. Para repetir / para uma lista nova

```bash
python _gestao_v2/migrar_status_pmib_v2.py --simular --libreoffice   # cópias locais, não toca no Box
python _gestao_v2/migrar_status_pmib_v2.py --aplicar --so "TEXTO"     # só com ordem do Luan
```
Arquivo que já está no v2 é reconhecido (tem `SITUAÇÃO DA AUTORIZAÇÃO`) e fica como está.
Lista nova: nasce do template, que já está no v2.

## 6. Pendências

| Pendência | Onde / quem |
|---|---|
| Conferir no Excel do trabalho 2 ou 3 listas (uma com comentário em thread, ex.: Ventilação das Salas de Baterias U9) | Luan |
| Arquivo de teste antigo `10- TESTES/TESTE_V2_Banco_de_Baterias_STATUS_PMIB_migrado.xlsx` (layout do 1º teste) pode ser apagado | Luan |
| DATA DE ALTERAÇÃO da linha de revisão ("—" em 42 listas) | quem reconciliar cada lista |
| 53 fichas ATRASADO ITAIPU — conferir com o export de autorizados mais recente | Luan / T4 |
| Lista de preços vigente da Sala Segura só existe como `- Copy` (199 itens sem TIPO pré-preenchido) | `02 - INFRAESTRUTURA COMPLEMENTAR/SALA SEGURA/` |
| 2 linhas `DUPLICADO` sem a linha original; 3 fichas `PDM.9900.000` sem o PMIB da original | ver protótipo, "qualidade dos dados" |
| Feriados do Paraguai/Foz entram nos 15 d.u.? | Luan |
| Cópia `SECOND BRAIN` do Box está na versão de 01/10 | só com nova ordem |
| Mapeadora levada ao tratamento v2 em 05/10 (3 colunas novas, APTO/ATRASO pela regra nova) | ver [[Mapeamento das Listas de Sobressalentes]]; backup `backup_mapeadora_20261005-0824` |

## Relacionados
[[README]] · [[Tarefa SIG-FT - Calculo e Gravacao sem Perda]] · [[Plano - Sistema de Gestao v2]] ·
[[Planilha STATUS_PMIB]] · [[Plano - Revisao em Uso automatica]] · [[findings]]
