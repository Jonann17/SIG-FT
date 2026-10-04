---
tags: [plano, status-pmib, migracao, handoff]
status: aguardando-aprovacao
criado: 2026-10-04
destinatario: Luan e a próxima conversa que for executar
---

# Plano — Reestruturação do `_STATUS_PMIB` (layout v2)

> [!info] Para quem vai executar
> Este plano é autocontido. Contexto maior em [[README]] e [[Plano - Sistema de Gestao v2]].
> O script já existe: `_gestao_v2/migrar_status_pmib_v2.py`. Nada foi aplicado no Box ainda.

## 0. Em uma frase

Acrescentar a cada `_STATUS_PMIB` as colunas de **tipo de entrega, fornecedor, procurement,
prazo e situação da autorização de Itaipu (15 d.u.) e data da entrega**, por script, **sem
perder nada do que existe** — nem dado, nem histórico de versões no Box, nem comentários, nem
listas suspensas — e impedir que as listas suspensas voltem a sumir.

---

## 1. O que não pode acontecer (requisitos invioláveis)

| # | Requisito | Como o plano garante |
|---|---|---|
| R1 | **Nenhuma célula existente muda** (valor ou fórmula), nem de lugar | colunas novas só **à direita** da tabela; a conferência compara célula a célula, original × migrado |
| R2 | **Histórico de versões do Box preservado** | o arquivo é **salvo no mesmo caminho** (nova versão do mesmo arquivo). O script **nunca** apaga, renomeia ou move arquivo do Box |
| R3 | **Backup antes de tocar** | `--aplicar` copia cada original para `%LOCALAPPDATA%\Sobressalentes-v2\backup_AAAAMMDD-HHMM\` antes de alterar |
| R4 | **Comentários, anotações, formatação condicional e desenhos preservados** | a conferência conta tudo isso antes e depois; arquivo que perderia algo é **pulado intocado** |
| R5 | **Listas suspensas que não somem mais** | recriadas por **nome definido** (`=lst_status` …), formato que o openpyxl do SIG-FT preserva — testado salvando de novo |
| R6 | **SIG-FT continua funcionando** | ele lê por **nome** de coluna; a conferência roda a mesma busca de cabeçalho do SIG-FT (`CÓDIGO DO MATERIAL` nas 10 primeiras linhas) |

---

## 2. O que muda em cada arquivo

**Nada que existe muda de nome ou de lugar.** Bloco novo à direita da última coluna (em geral
começa na coluna **U**; nos 4 arquivos com anotações soltas à direita, começa depois delas):

| Coluna nova | Tipo | Quem preenche |
|---|---|---|
| **TIPO DE ENTREGA** | lista: `FÍSICA E DOCUMENTAL` · `DOCUMENTAL` · `TÍTULO` | pré-preenchido pela lista de preços (por PMIB); o resto, quem cria a ficha |
| **FORNECEDOR** | texto | quem cria a ficha (empresa que vendeu ao CMI, não o fabricante) |
| **PROCUREMENT** | lista que aceita nome novo | pré-preenchido pela mapeadora quando a lista tem uma pessoa só |
| PRAZO AUTORIZAÇÃO ITAIPU (15 D.U.) | **fórmula** | `DIATRABALHO(data do e-mail; 15; Feriados)` |
| **DATA DA AUTORIZAÇÃO ITAIPU** | data | e-mail de autorização, ou o script de aptos (data do export) |
| SITUAÇÃO DA AUTORIZAÇÃO | **fórmula** | AGUARDANDO ITAIPU · ATRASADO ITAIPU · AUTORIZADO NO PRAZO · AUTORIZADO COM ATRASO · AUTORIZADO |
| DIAS ÚTEIS DE ATRASO | **fórmula** | além do prazo, até hoje ou até a autorização |
| **DATA DA ENTREGA** | data | quem confirma a entrega no almoxarifado de Itaipu |

Mais:
- aba **`Feriados`** (nome definido `Feriados`) — datas que os 15 d.u. pulam;
- aba **`Listas`** com os vocabulários e os nomes definidos `lst_status`, `lst_secao`,
  `lst_simnao`, `lst_tipo_entrega`, `lst_procurement`;
- **listas suspensas** em STATUS, nas seis seções, APTO, EQUIPAMENTO ENTREGUE e nas colunas
  novas; datas validadas entre 2024 e 2030;
- **formatação condicional** na situação (vermelho = atrasado Itaipu, amarelo = aguardando,
  verde = autorizado) e no DOCUMENTAL (cinza);
- cabeçalho congelado; nome definido `versao_layout_status_pmib = "v2"`.

> [!important] DUPLICADO continua igual (regra confirmada pelo Luan em 04/10/2026)
> - **STATUS `DUPLICADO`** = o mesmo item repetido **na mesma lista**. A linha repete o PMIB de
>   outra linha e fica sem as seções preenchidas. Não é ficha nova; a **quantidade** dela conta.
> - **Ficha duplicada de outro sistema** = ficha nova, `PDM usado` = `PDM.9900.000 - FICHA PMIB,
>   DUPLICADA, R0`, PMIB da original em **OBSERVAÇÕES**, STATUS no ciclo normal.
>
> A migração não mexe em nenhuma das duas. As fórmulas da linha DUPLICADO ficam em branco
> (ela não tem e-mail próprio) — a situação vale pela linha da ficha.

---

## 3. O que já sabemos que se perde — e por quê

O SIG-FT e este script salvam com **openpyxl**, que não preserva tudo:

| O quê | Arquivos (04/10) | O que acontece no openpyxl | Tratamento |
|---|---|---|---|
| **Comentário em thread** (Revisão › Novo Comentário: autor, data, respostas) | **16** | **apagado** — vira anotação comum com o texto "[Threaded comment] Your version of Excel…", sem autor, data nem respostas | o script **pula** esses arquivos (intocados) → migrar pelo **motor Excel** (seção 4) |
| Lista suspensa que aponta para outra aba (`Checklist!$A$3:$A$8`) | 22 | **apagada** (é gravada como extensão `x14`) | recriada por nome definido — sobrevive |
| Anotação comum (nota) | vários | preservada | — |
| Formatação condicional | 34 | preservada (conferido) | — |
| Contêiner de desenho vazio | 1 (SCADA) | some — não tinha nada dentro | inofensivo |

> [!warning] O SIG-FT já faz essas perdas hoje
> Toda vez que um módulo do SIG-FT grava um `_STATUS_PMIB`, as listas suspensas por outra aba
> e os comentários em thread daquele arquivo somem. A migração resolve as listas; os
> comentários em thread precisam da **etapa 7** (blindar o SIG-FT), senão voltam a sumir.

---

## 4. Dois motores de migração

| Motor | Para quais arquivos | Estado |
|---|---|---|
| **openpyxl** (`migrar_status_pmib_v2.py`) | os **31** sem comentário em thread | **pronto**. Simulado em 04/10: 31/31, nenhuma célula, anotação, formatação ou desenho perdido; 267 TIPO e 669 PROCUREMENT pré-preenchidos |
| **Excel** (automação do próprio Excel) | os **16** com comentário em thread | **a construir** — precisa de Excel licenciado (o do trabalho). O Excel preserva tudo, inclusive comentários em thread |

### Especificação do motor Excel (para a próxima conversa)
- Acrescentar `--motor excel` ao mesmo script, reaproveitando as mesmas constantes (`BLOCO`,
  `LISTAS`, `NOTAS`, `CORES_SITUACAO`) e a mesma `conferir()`.
- `win32com.client.DispatchEx("Excel.Application")`, `Visible=False`, `DisplayAlerts=False`,
  `AskToUpdateLinks=False`, `EnableEvents=False`; `Workbooks.Open(caminho, UpdateLinks=0)`.
- Mesma posição do bloco (à direita), mesmos cabeçalhos, fórmulas em inglês (`.Formula`),
  `Validation.Add(Type=3, Formula1="=lst_status")`, `FormatConditions.Add`, abas `Feriados` e
  `Listas` com nomes definidos (`Names.Add`). Datas escritas como **número serial** (o pywin32
  desloca fuso em `datetime`).
- `CalculateFull()` antes de `Save()` — deixa o valor calculado gravado.
- Encerrar **só** o Excel que o script abriu (linha de comando com `/automation`).
- Testar primeiro com `Visible=True` numa cópia: em 30/09, num Excel sem licença, um diálogo
  "Configurar impressora" travou o `Workbooks.Open`.

**Alternativa sem motor Excel**: o Luan aceita perder a estrutura dos comentários em thread de
alguns arquivos (o texto fica, como anotação) e roda `--aceitar-perda-de-comentarios` só para eles.

---

## 5. Execução, passo a passo

### Etapa 0 — Decisões (Luan)
- [ ] Aprovar o layout da seção 2.
- [ ] Calendário dos 15 d.u. (hoje: feriados nacionais BR + Carnaval e Corpus Christi).
- [ ] Os 16 arquivos com comentário em thread: **motor Excel** (recomendado) ou aceitar a perda?
- [ ] Daqui para frente, nos `_STATUS_PMIB`, usar **Anotação** (nota) em vez de **Comentário**? (recomendado — nota sobrevive ao SIG-FT)

### Etapa 1 — Preparação
- [ ] Avisar a equipe: ninguém com `_STATUS_PMIB` aberto e **SIG-FT parado** durante a migração.
- [ ] Box sincronizado; nenhum arquivo `~$...` (trava do Excel) nas pastas.
- [ ] Arrumar a lista de preços da Sala Segura: hoje só existe `ST00=U01&MPB021 - Copy.xlsm` — sem o
      nome oficial `#ST00=U01&MPB021.xlsm`, o pré-preenchimento de TIPO DE ENTREGA dos 199 itens não acontece.
- [ ] Na máquina: Python 3.12 com `openpyxl` e `pandas`; cópia deste pacote (GitHub ou Box).

### Etapa 2 — Simular (não toca no Box)
```bash
python _gestao_v2/migrar_status_pmib_v2.py --simular
```
- [ ] Ler `relatorio_migracao.csv` (na pasta temporária indicada): coluna `problemas` toda "—".
- [ ] Abrir 2 ou 3 cópias migradas no Excel e olhar: bloco novo, listas suspensas, cores, fórmulas.

### Etapa 3 — Piloto numa lista
```bash
python _gestao_v2/migrar_status_pmib_v2.py --aplicar --so "B03BDV10UC012"
```
(Gerador Diesel › PDG: pequeno, com e-mails e atrasos reais, sem comentário em thread.)
- [ ] Abrir no Excel; conferir o bloco e as listas suspensas.
- [ ] Rodar o SIG-FT (Gestão PMIB) e depois reabrir: **as listas suspensas continuam?**
- [ ] No Box (web), o arquivo mostra uma **versão nova** e as anteriores continuam lá.

### Etapa 4 — Aplicar nos demais sem comentário em thread
```bash
python _gestao_v2/migrar_status_pmib_v2.py --aplicar
```
Os 16 com comentário em thread saem como **PULADO (intocado)** no relatório.

### Etapa 5 — Os 16 com comentário em thread
Construir o motor Excel (seção 4) → simular → piloto em 1 → os 16.

### Etapa 6 — Template
- [ ] Copiar `_gestao_v2/template/codigo_itaipu_STATUS_PMIB_v2.xlsx` para `Templates/` com o nome
      oficial; o antigo vai para `Templates/Obsoleto/`.

### Etapa 7 — Blindar o SIG-FT (para não voltar a perder)
- [ ] Antes de salvar um `_STATUS_PMIB`, medir o inventário (a função `inventario()` do script):
      se o arquivo tem **comentário em thread**, avisar e não salvar pelo openpyxl.
- [ ] Nunca criar validação apontando para outra aba; usar os nomes `lst_*`.
- [ ] `pmib_manager.py`: 15 d.u. no lugar de 14 dias corridos (código testado no [[README]], D2).
- [ ] Script de aptos: ao virar APTO = SIM, gravar **DATA DA AUTORIZAÇÃO ITAIPU** com a data do export.
- [ ] Ler as colunas novas por nome (PROCUREMENT, TIPO DE ENTREGA) onde fizer sentido.

### Etapa 8 — Preencher o que ficou vazio
- [ ] TIPO DE ENTREGA: 831 fichas sem tipo em 04/10 (199 só por causa da Sala Segura, Etapa 1).
- [ ] PROCUREMENT e FORNECEDOR nas listas com mais de um fornecedor.
- [ ] Daqui para frente: DATA DA AUTORIZAÇÃO e DATA DA ENTREGA no lugar do "SIM" (o SIM continua).

---

## 6. Como desfazer

1. **Pelo backup**: copiar o arquivo de `%LOCALAPPDATA%\Sobressalentes-v2\backup_...\` **por cima**
   do arquivo no Box — mesmo nome, mesmo lugar (assim o Box registra como nova versão, sem quebrar o histórico).
2. **Pelo Box**: no navegador, arquivo › Versões › restaurar a anterior.

Nunca apagar o arquivo migrado para "colocar o antigo no lugar": isso quebra o histórico de versões.

---

## 7. Critérios de pronto

- [ ] Relatório sem `problemas` em todos os arquivos migrados; pulados listados.
- [ ] Nenhuma célula existente alterada (conferência automática) e conferência visual em 3 arquivos.
- [ ] Listas suspensas presentes **depois** de o SIG-FT salvar o arquivo.
- [ ] Comentários em thread intactos nos 16 (motor Excel) — ou perda aceita por escrito pelo Luan.
- [ ] Versões anteriores visíveis no Box.
- [ ] O protótipo (`_scripts/gerar_prototipo_dashboard.py`) e o Power BI leem as colunas novas.
- [ ] Template v2 em `Templates/`.

---

## 8. Pendências encontradas na simulação de 04/10

| Pendência | Onde |
|---|---|
| Lista de preços vigente da Sala Segura só existe como `- Copy` | `02 - INFRAESTRUTURA COMPLEMENTAR/SALA SEGURA/` |
| 2 linhas `DUPLICADO` sem a linha original (1 sem PMIB) | SFC HF-01/02 (item 39), RV parte hidráulica (item 15, `.0794`) |
| 3 fichas `PDM.9900.000` sem o PMIB da original em OBSERVAÇÕES | PVA (`.1237`), HPU da comporta (`.1180`) e mais 1 |
| 127 fichas com STATUS `N/A` (126 na Sala Segura) | provável `FICHA CRIADA` |
| Anotações soltas à direita da tabela em 4 arquivos (preço/câmbio, XLOOKUP, procurement) | o bloco v2 começa depois delas |

## Relacionados
[[README]] · [[Plano - Sistema de Gestao v2]] · [[Planilha STATUS_PMIB]] · [[Ciclo de Vida de um Item]] · [[findings]]
