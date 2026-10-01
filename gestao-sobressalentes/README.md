---
tags: [handoff, leia-primeiro]
criado: 2026-10-01
autor: sessão Claude Code de 30/09–01/10/2026, a pedido do Luan
---

# LEIA PRIMEIRO — Gestão dos Sobressalentes: o que foi descoberto e como continuar

Este pacote é o **cofre de conhecimento** do processo de sobressalentes do Consórcio de
Modernização de Itaipu (CMI, contrato 4500063671) mais o trabalho da sessão de
30/09–01/10/2026 ("Gestão v2"). Ele foi feito para que **qualquer conversa nova** — com o
Luan ou com um assistente de IA — continue de onde parou, sem acesso ao computador onde foi
criado.

> [!info] Onde este pacote está
> - **GitHub**: repositório privado `luanccozer/SIG-FT`, pasta `gestao-sobressalentes/`
>   (branch `claude/gestao-sobressalentes-v2`, Pull Request #2 para o branch principal).
> - **Box**: `15 - PDM/SECOND BRAIN/` (cópia para a equipe, sincronizada em 01/10/2026).
> - Original: cofre Obsidian no OneDrive do computador pessoal do Luan.

> [!danger] Conteúdo sensível do Consórcio
> Números, códigos de lista, códigos PMIB, valores e nomes de pessoas. **Não publicar**, não
> colar em ferramenta pública, não tornar o repositório público.

---

## 0. Como começar uma conversa nova

Cole isto no início do chat:

> Leia `README.md` desta pasta e depois `07 - Diagnostico/Plano - Sistema de Gestao v2.md`.
> Sou o Luan, coordeno a entrega dos sobressalentes. Quero trabalhar na tarefa **N** da
> seção 5 do README.

Se o chat **não tiver acesso ao Box**, ele não consegue ler as planilhas: anexe os arquivos de
que a tarefa precisa (um `_STATUS_PMIB`, a mapeadora, uma lista de preços) ou rode os scripts
na máquina que tem o Box.

### Mapa do pacote

| Onde | O quê |
|---|---|
| `00 - Inicio.md` | índice do cofre (notas permanentes sobre o processo) |
| `01` a `06` | contexto, normas, processo, codificação, gerenciamento, SIG-FT |
| `07 - Diagnostico/` | documentos de trabalho datados; **`Plano - Sistema de Gestao v2.md`** é o plano desta sessão |
| `_scripts/regras_sobressalentes.py` | **as regras de negócio** em código (15 d.u., PMIB, situação da autorização, LMR, pendência) |
| `_scripts/gerar_prototipo_dashboard.py` | gera `_gerado/prototipo-dashboard.html` a partir do Box |
| `_gestao_v2/template/` | template `_STATUS_PMIB` v2 |
| `_gestao_v2/migrar_status_pmib_v2.py` | migração dos `_STATUS_PMIB` para o v2 |
| `_gestao_v2/powerbi/` | consultas Power Query, medidas DAX e o roteiro (`LEIA-ME.md`) |
| `_planejamento/` | `findings.md` (achados e divergências) e `progress.md` (histórico) |

---

## 1. Contexto em dez linhas

- Cada sistema da modernização emite uma **Lista de Sobressalentes** (Aconex, aprovada pela EN.DT).
  Cada material vira uma **ficha técnica no portal PMIB** (código `4500063671.NNNN`).
- O controle item a item é o **`_STATUS_PMIB`**: uma planilha por lista, uma linha por material.
- A **mapeadora** (`SOBRESSALENTES - PMIB/Mapeamento Listas de Sobressalentes.xlsx`) tem uma linha
  por lista; o **SIG-FT** (app Python do Luan, repositório `luanccozer/SIG-FT`) lê os `_STATUS_PMIB`
  e escreve as contagens nela.
- A **Lista de Preços** (SM.DT) valida o preço sem nota fiscal. Código novo: DCC **`PB021`**.
- Entrega física: e-mail de intenção → **Itaipu tem 15 dias úteis para autorizar** → etiqueta MTA →
  almoxarifado de Itaipu → evento de pagamento de entrega (80%). Aprovação das fichas → evento de
  aprovação (20%).
- Compromisso do CMI: **Aplicação LMR** em até 3 meses do e-mail de intenção.
- Box: `C:\Users\<usuário>\Box\CMI - Consórcio Itaipu\11 - Ger. Engenharia\15 - PDM\`.
  **Regra do Luan: o Box é somente leitura** — escrever lá só com ordem explícita.

---

## 2. As descobertas (em 01/10/2026) — e o que fazer com cada uma

### D1. O Power BI lê só a aba principal da mapeadora
- **Evidência**: `SOBRESSALENTES - PMIB/Sobressalentes - Dashboard.pbix` descompactado: uma
  consulta (`Acompanhamento Sobressalente`), 4 medidas de soma, nenhum relacionamento, caminho fixo
  `C:\Users\560083605\Box\...`. A 2ª página é cópia da 1ª, com um gráfico "listas com preço"
  apontando para `STATUS REAL`.
- **Impacto**: não mostra item, prazo, procurement nem tipo de entrega; herda o atraso da mapeadora,
  que só acerta depois de o SIG-FT rodar — **4 listas** com `FICHAS EXISTENTES` diferente do
  `_STATUS_PMIB` (ex.: Refrigeração QM903: mapeadora 1 × arquivo 9). A medida `AptoEntrega`
  (apto − entregue) subtrai duas vezes, porque a coluna da mapeadora já é "apto e não entregue".
- **Fazer**: montar o Power BI v2 com `_gestao_v2/powerbi/` (roteiro em `LEIA-ME.md`): tabela fato
  `Itens` lida direto dos `_STATUS_PMIB`, parâmetro `PastaPMIB` por máquina, dois relatórios
  (interno e Itaipu). O desenho-alvo, com dados reais, é `_gerado/prototipo-dashboard.html`.
- **Pronto quando**: os cartões batem com o protótipo (1.355 fichas, 612 emitidas, 53 atrasadas
  em 01/10) e o arquivo atualiza em qualquer máquina só trocando o parâmetro.

### D2. O SIG-FT calcula o atraso de Itaipu com 14 dias corridos
- **Evidência**: `sigft/services/pmib_manager.py`, função `_calcula_fichas` (≈ linha 319, inclusive na
  versão mais nova do GitHub): `data_limite = df_com_data['DATA INFORME'] + pd.to_timedelta(14, unit='D')`.
- **Impacto**: a regra vigente é **15 dias úteis**. Por ela, em 01/10: **53 fichas atrasadas** (a mais
  antiga com 307 d.u.), **142 aguardando no prazo**. A coluna `ATRASO DE AUTORIZAÇÃO DE ENTREGA ITAIPU`
  conta **fichas** (PMIB distinto, sem DUPLICADO), não dias.
- **Fazer** (testado: idêntico ao `DIATRABALHO` do Excel em 1.500 datas seguidas):

  ```python
  import numpy as np
  # mesma lista de _scripts/regras_sobressalentes.py (FERIADOS) — idealmente em sigft/config.py
  FERIADOS = np.array([...], dtype="datetime64[D]")

  datas = df_com_data['DATA INFORME'].values.astype("datetime64[D]")
  data_limite = np.busday_offset(datas, 15, roll="backward", holidays=FERIADOS)
  hoje = np.datetime64(datetime.now().date(), "D")
  cond_atraso = (data_limite < hoje) & (df_com_data['APTO PARA ENTREGA'] != 'SIM') & (df_com_data['ENTREGUE'] != 'SIM')
  ```

  > [!warning] `roll="backward"`, não `"forward"`
  > Com `"forward"`, e-mail enviado em fim de semana ou feriado ganha um dia a mais — diverge do
  > Excel em 468 das 1.500 datas testadas.
- Escrever teste (o repositório tem suíte pytest): 15/09/2026 → prazo 06/10/2026; 04/09/2026 + 1 d.u.
  → 08/09/2026 (07/09 é feriado). Rodar `bash scripts/check.sh`.
- **Pronto quando**: a coluna da mapeadora bate com a SITUAÇÃO DA AUTORIZAÇÃO do `_STATUS_PMIB` v2.

### D3. As listas suspensas do `_STATUS_PMIB` somem quando o SIG-FT salva
- **Evidência**: a validação da coluna STATUS aponta para outra aba (`Checklist!$A$3:$A$8`); o Excel
  grava esse tipo como **extensão** (`x14:dataValidation`) e o **openpyxl apaga extensões ao salvar**
  ("Data Validation extension is not supported and will be removed"). Em 01/10, **21 arquivos** ainda
  tinham a lista; os demais já a tinham perdido. Por isso o vocabulário de status saiu do controle.
- **Também**: no template `Templates/codigo_itaipu_STATUS_PMIB.xlsx` o nome `dados_validos` aponta para
  `A5:A11` (pula FICHA CRIADA e DUPLICADO) e há 32 nomes definidos quebrados (`#REF!`).
- **Fazer**: a migração v2 recria todas as listas por **nome definido** (`=lst_status`, `lst_secao`,
  `lst_simnao`, `lst_tipo_entrega`, `lst_procurement`, na aba `Listas`) — esse formato sobrevive ao
  openpyxl (conferido: salvar de novo pelo openpyxl mantém as validações). No SIG-FT, nunca criar
  validação apontando para outra aba.

### D4. A lista de preços mudou para `PB021`
- **Evidência**: 9 arquivos `...PB021` já nas pastas (ex.: `#ST00=M00MEU10&MPB021`); a aba
  **"Lista de preços Follow-up"** da mapeadora tem 16 linhas, **todas no código antigo `PB020-0x`**.
  A troca vem da nova revisão do ITAIPU-REF-0013 (atividade "Atualizar o RDS-PP de todas as listas de
  preços com o DCC correto" na aba Atividades).
- **Fazer**: atualizar o follow-up para PB021; no SIG-FT, reconhecer lista de preço **pelo DCC**
  (`PB021`), com a regra por descrição (`PRECOS`/`VALORIZADA`) só para o legado; vincular à lista de
  sobressalentes trocando `PB021`→`PB020` no código (e, quando o RDS-PP mudou, pelo follow-up).
  Plano detalhado: `07 - Diagnostico/Plano - Aba de Listas de Precos.md`.

### D5. O gargalo é o que só o CMI fecha
- **Retrato de 01/10**: 1.355 fichas (42 listas com ficha; 27 listas aprovadas ainda sem ficha);
  612 emitidas (45%); 64 aprovadas. Seções concluídas: fornecedor 55–68%; **valorização 46%;
  LMR 24%**. **269 fichas** comunicadas a Itaipu há mais de 3 meses sem LMR.
- **Fazer**: plano de ação da LMR por lista (começar pelas que têm mais fichas em análise em
  Itaipu); ver `07 - Diagnostico/Plano de Acao - Aplicacao LMR.md`.

### Outros achados (qualidade dos dados, 01/10)

| # | Achado | Onde corrigir |
|---|---|---|
| 169 | fichas com STATUS `N/A` ou vazio — quase todas componentes explodidos da Sala Segura (criados em 29/09) | `_STATUS_PMIB` da Sala Segura: provável `FICHA CRIADA` |
| 161 | fichas APTAS sem data do e-mail de intenção (histórico) | aceitar; não reconstruir |
| 39 | células de VALORIZAÇÃO com **número** (preço) em vez de COMPLETO/INCOMPLETO | RV parte hidráulica, Refrigeração QM903 |
| 630 | fichas sem tipo de entrega (sem lista de preços com a coluna) | classificar no `_STATUS_PMIB` v2 |
| 25 | itens físicos sem código GE na lista de preços | RV parte digital (`MEU10&EPB021`), SMF |
| 9 | cópias de trabalho misturadas às planilhas vivas (`_STATUS_PMIB_.xlsx`, `- Copy.xlsm`, `corrigido.xlsm`, `testes_autospec/`) | mover para `_obsoleto/` |
| 39 | listas sem responsável na mapeadora | mapeadora |
| — | anotações soltas à direita da tabela em 4 `_STATUS_PMIB` (preço/câmbio, XLOOKUP, um nome de procurement em `U6`) | decidir se vira coluna |
| — | a regra "código GE preenchido ⟺ FÍSICA E DOCUMENTAL" vale num sentido só | por isso TIPO DE ENTREGA é coluna própria |

---

## 3. O que já foi construído

| Entregável | Estado |
|---|---|
| `_scripts/regras_sobressalentes.py` | testado (prazos, PMIB, situações, pendência) |
| Template `_gestao_v2/template/codigo_itaipu_STATUS_PMIB_v2.xlsx` | fórmulas recalculadas no LibreOffice batem com o Python (10 casos + 3 planilhas reais) |
| `_gestao_v2/migrar_status_pmib_v2.py` | **simulado** em cópias: 47/47, nenhum dado existente alterado, 818 TIPO e 1.006 PROCUREMENT pré-preenchidos. **NÃO aplicado no Box** |
| `_gestao_v2/powerbi/*.pq` + `05 - Medidas.dax` | escritos; **ainda não montados** no Power BI Desktop |
| `_gerado/prototipo-dashboard.html` | protótipo das duas visões com dados de 01/10 (abrir no navegador; `#itaipu` no fim da URL abre a visão do cliente) |
| Notas do cofre | atualizadas: Lista de Precos (PB021), Planilha STATUS_PMIB, Organizacao das Pastas, Mapeamento, Indicadores, findings, progress |

**`_STATUS_PMIB` v2** = nada existente muda de lugar; bloco novo à direita: TIPO DE ENTREGA ·
FORNECEDOR · PROCUREMENT · PRAZO AUTORIZAÇÃO ITAIPU (15 D.U.) *(fórmula)* · DATA DA AUTORIZAÇÃO
ITAIPU · SITUAÇÃO DA AUTORIZAÇÃO *(fórmula)* · DIAS ÚTEIS DE ATRASO *(fórmula)* · DATA DA ENTREGA;
abas `Feriados` e `Listas`.

---

## 4. Como rodar (na máquina que tem o Box)

```bash
pip install openpyxl pandas
# protótipo do painel (só lê o Box)
python _scripts/gerar_prototipo_dashboard.py
# migração: primeiro simular (cópias numa pasta temporária, não toca no Box)
python _gestao_v2/migrar_status_pmib_v2.py --simular
# aplicar NO BOX (faz backup antes em %LOCALAPPDATA%\Sobressalentes-v2) — só com as planilhas fechadas
python _gestao_v2/migrar_status_pmib_v2.py --aplicar
```

Os scripts acham o Box em `~/Box/CMI - Consórcio Itaipu/11 - Ger. Engenharia/15 - PDM`
(funciona em qualquer usuário do Windows). Requisitos: Python 3.12, openpyxl, pandas
(o código trata o pandas 3: `NaT` e `NaN` são "verdadeiros" num `if`).

---

## 5. Próximas tarefas, em ordem

| N | Tarefa | Precisa de | Referência |
|---|---|---|---|
| 1 | Decidir as pendências da seção 6 | Luan | — |
| 2 | Aplicar a migração v2 e trocar o template em `Templates/` | máquina com Box, autorização | seção 4 |
| 3 | Montar o Power BI v2 (interno, depois Itaipu) | Power BI Desktop | `_gestao_v2/powerbi/LEIA-ME.md` |
| 4 | SIG-FT: 15 d.u. (D2) | repositório SIG-FT | seção 2, D2 |
| 5 | SIG-FT: script de aptos grava a **DATA DA AUTORIZAÇÃO** (a data do export `sobressalentes_autorizados_AAAAMMDDhhmm`) ao virar APTO = SIM | repositório SIG-FT | `apto_para_entrega_att.py` |
| 6 | Follow-up de preços em PB021 (D4) | mapeadora / SIG-FT | seção 2, D4 |
| 7 | Classificar TIPO DE ENTREGA das 630 fichas | `_STATUS_PMIB` v2 | começar pelas listas com material entregue |
| 8 | Corrigir a qualidade dos dados (tabela da seção 2) | `_STATUS_PMIB` | — |
| 9 | Plano de ação da LMR (D5) | — | `Plano de Acao - Aplicacao LMR.md` |

## 6. Decisões pendentes (do Luan)

| Decisão | Padrão adotado até decidir |
|---|---|
| Calendário dos 15 d.u.: só feriados nacionais do Brasil? Paraguai? Foz? Pontos facultativos? | nacionais BR + Carnaval e Corpus Christi |
| Mostrar a Itaipu os pedidos de autorização além de 15 d.u. | sim, com data do pedido e prazo |
| Mostrar valor (US$) na visão do cliente | não |
| Prioridade da fila: entregar material autorizado antes da LMR | sim (dispara o evento de 80%) |

## 7. Cuidados

- **Box somente leitura.** Só `migrar_status_pmib_v2.py --aplicar` escreve lá, e só com ordem do Luan.
- Fórmulas do `_STATUS_PMIB` v2 são **para quem lê no Excel**; o Power BI e os scripts recalculam
  a partir das datas (o openpyxl do SIG-FT apaga o valor calculado ao salvar).
- No computador pessoal do Luan o Excel está sem licença (automação COM trava); no trabalho o Excel é
  licenciado. Para testar fórmulas sem Excel: LibreOffice `soffice --headless --convert-to xlsx`.
- A cópia `15 - PDM/SECOND BRAIN/` no Box foi sincronizada em 01/10/2026, por ordem do Luan
  (o backup da versão de 04/09 ficou no computador pessoal, em `%LOCALAPPDATA%\Sobressalentes-v2\`).
  Mudou o cofre? Atualize as duas cópias — elas não se sincronizam sozinhas.

## Relacionados
[[00 - Inicio]] · [[Plano - Sistema de Gestao v2]] · [[findings]] · [[progress]]
