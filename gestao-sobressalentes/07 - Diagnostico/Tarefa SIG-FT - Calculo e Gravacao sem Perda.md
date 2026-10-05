---
tags: [handoff, sig-ft, status-pmib, mapeadora]
criado: 2026-10-04
atualizado: 2026-10-05
destinatario: sessão Claude Code na nuvem (GitHub), repositório luanccozer/SIG-FT
inicio: 2026-10-05
---

# Tarefa SIG-FT — o Gestão PMIB no tratamento v2 (roteiro completo)

## Prompt para começar a sessão na nuvem

> Leia `gestao-sobressalentes/07 - Diagnostico/Tarefa SIG-FT - Calculo e Gravacao sem Perda.md`
> inteiro antes de mexer em código. Execute as etapas na ordem (T0 → T6), uma por commit, seguindo
> as convenções do repositório. Ao final de cada etapa rode `bash scripts/check.sh`; ao final da T3
> rode também o validador do kit (seção 3) até ele dizer **KIT OK**. Me mostre o que mudou antes de
> passar de uma etapa para a outra.

(Se o Pull Request #2 ainda não foi juntado, abra a sessão no branch `claude/gestao-sobressalentes-v2`,
que é onde a pasta `gestao-sobressalentes/` está. **Nada de `gestao-sobressalentes/` vai para o código
do app** — é material de referência; copie o que precisar para dentro de `sigft/`.)

---

## 1. O que já mudou nas planilhas (feito em 04–05/10/2026, no Box)

### 1.1 Os 47 `_STATUS_PMIB` (e o template)

```
linha 4:  REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: 0A - DATA DE ALTERAÇÃO: 03/09/2026
linha 5:  ... | APLICAÇÃO - LMR | TIPO DE ENTREGA | DATA DO EMAIL COMUNICANDO ENTREGA |
              SITUAÇÃO DA AUTORIZAÇÃO | DIAS DE ATRASO | EQUIPAMENTO ENTREGUE |
              [extras da lista] | FORNECEDOR | PROCUREMENT | OBSERVAÇÕES | [extras]
```

- O cabeçalho está na **linha 5** em todos (era 4 em 42 deles). A linha 4 é mesclada e é **texto**.
- `SITUAÇÃO DA AUTORIZAÇÃO` **substituiu** `APTO PARA ENTREGA` (mesma coluna; SIM virou AUTORIZADO).
- Novas: `TIPO DE ENTREGA` (FÍSICA E DOCUMENTAL · DOCUMENTAL · TÍTULO), `DIAS DE ATRASO`, `FORNECEDOR`, `PROCUREMENT`.
- Listas suspensas por **nome definido** (`lst_status`, `lst_secao`, `lst_simnao`, `lst_tipo_entrega`,
  `lst_procurement`, `lst_situacao`) e nome `versao_layout_status_pmib = "v2"`.
- **Nenhuma fórmula.** SITUAÇÃO e DIAS DE ATRASO são **valores que o SIG-FT grava**.
- Comentários em thread existem em 16 arquivos e **têm de sobreviver** a qualquer gravação.

### 1.2 A mapeadora vira CADASTRO (`Mapeamento Listas de Sobressalentes.xlsx`, aba `Acompanhamento Sobressalente`)

> [!important] Decisão do Luan (05/10/2026): a mapeadora é o cadastro das listas; **as contagens saem de
> cada `_STATUS_PMIB` pelo Power BI v2**. O bloco de contagens da aba (`FICHAS EXISTENTES` … `ÍNDICE DE
> CONCLUSÃO`) **foi retirado em 05/10/2026**, depois de o Power BI v2 ser montado e testado.

Cabeçalho na **linha 2**. O que fica (e é o que o Gestão PMIB mantém):

| Coluna | Quem escreve |
|---|---|
| cadastro: `N° DOCUMENTO ITAIPU`, `N° DOCUMENTO CMI`, `ÚLTIMA REVISÃO EMITIDA`, `STATUS DA REVISÃO`, `DATA DE ATUALIZAÇÃO`, `DESCRIÇÃO`, `ESPECIFICAÇÃO TÉCNICA`, `CAPÍTULO` | Gestão PMIB, do DocManager (como hoje, passo "D. Atualizar Metadados") |
| `REVISÃO EM USO` | **Gestão PMIB, da linha de revisão do `_STATUS_PMIB`** (T3-f, novo) |
| `SITUAÇÃO NO PMIB` | Gestão PMIB (a "cascata" de hoje — continua) |
| `LINK DA PLANILHA` | Gestão PMIB (como hoje, sem `testes_autospec` — T3-a) |
| `CAMPO "CÓDIGO DO PROJETO PARA O PMIB"` | fórmula da planilha — não tocar |
| `STATUS REAL`, `RESPONSÁVEL`, `PROCUREMENT`, `ELABORADOR…`, `ORIGEM…`, `ENTREGA`, `OBSERVAÇÃO`, `EVENTOS…` | pessoas — nunca sobrescrever |

**O SIG-FT não grava mais contagem nenhuma na mapeadora.** As colunas são achadas pelo nome da linha 2;
coluna que não existe é pulada (o código atual já faz isso) — então nada quebra quando o bloco sair.

### 1.3 O que quebra até esta tarefa estar pronta (tudo visível, nenhum dado errado gravado)

| Onde | Sintoma |
|---|---|
| Gestão PMIB (`pmib_manager`) | as colunas de contagem não existem mais na mapeadora: ele as pula (nada quebra); as contagens antigas (14 dias) e o "Atualizar template" só somem do código na T3 |
| Módulo PDM, modo "selecionar códigos" | lê o cabeçalho fixo na linha 4 → "Coluna 'CÓDIGO PMIB' não encontrada" |
| `apto_para_entrega_att.py` (fora do repositório) | "Falta coluna APTO", não grava |
| Qualquer `save` de `_STATUS_PMIB` pelo openpyxl | **apaga os comentários em thread** do arquivo |

---

## 2. A regra (decisões do Luan, 04–05/10/2026)

### 2.1 SITUAÇÃO DA AUTORIZAÇÃO e DIAS DE ATRASO — por linha do `_STATUS_PMIB`

Avaliar **nesta ordem** (a primeira que casar vale):

| # | Condição | SITUAÇÃO | DIAS DE ATRASO |
|---|---|---|---|
| 1 | STATUS = `DUPLICADO` e a SITUAÇÃO atual não é AUTORIZADO | *(branco)* | *(branco)* |
| 2 | SITUAÇÃO atual = `AUTORIZADO` (ou `SIM`, arquivo antigo) | `AUTORIZADO` | **mantém o que estiver** (congelado) |
| 3 | TIPO DE ENTREGA = `DOCUMENTAL` ou `TÍTULO` | `N/A` | *(branco)* |
| 4 | EQUIPAMENTO ENTREGUE = `SIM` | `AUTORIZADO` | mantém |
| 5 | TIPO DE ENTREGA vazio (ou desconhecido) | *(branco)* | *(branco)* |
| 6 | (FÍSICA E DOCUMENTAL) sem DATA DO EMAIL | *(branco)* | *(branco)* |
| 7 | hoje > prazo | `ATRASADO ITAIPU` | `(hoje − prazo).days` — **dias corridos** |
| 8 | senão | `AGUARDANDO ITAIPU` | *(branco)* |

- **Só FÍSICA E DOCUMENTAL precisa de autorização de Itaipu.** DOCUMENTAL é o componente explodido (só
  tem ficha; a entrega física é a do pai); TÍTULO é agrupamento; tipo vazio não conta até alguém classificar.
- **prazo** = DATA DO EMAIL + **15 dias úteis**, igual ao `WORKDAY` do Excel: avança dia a dia e conta os
  que não são sábado, domingo nem `FERIADOS`. Implementação de referência, só stdlib:
  `somar_dias_uteis()` em `gestao-sobressalentes/_scripts/regras_sobressalentes.py`.
  Ex.: 15/09/2026 → 06/10/2026; 04/09/2026 → 28/09/2026 (07/09 é feriado); 01/10/2026 → 23/10/2026 (12/10).
- `FERIADOS`: copiar o dicionário de `regras_sobressalentes.py` (nacionais + Carnaval + Corpus Christi,
  2024–2028). O Luan ainda vai confirmar se entram os do Paraguai/Foz — deixe num só lugar (`config.py`).
- Estados calculados (AGUARDANDO, ATRASADO, N/A, branco) **são recalculados** a cada rodada; AUTORIZADO
  nunca é desfeito pelo cálculo.
- Comparações de texto normalizadas (maiúsculas, sem acento, sem espaços extras):
  `FISICA E DOCUMENTAL` = `FÍSICA E DOCUMENTAL`; `TITULO`/`CONJUNTO` = `TÍTULO`; `APENAS DOCUMENTAL` = `DOCUMENTAL`
  (tabela `TIPO_CANONICO` em `regras_sobressalentes.py`).
- Implementação de referência completa: `situacao_autorizacao()` (regras 2–8) e, para o arquivo inteiro
  (com a regra 1 e "só grava o que mudou"), `recalcular_situacao()` em `_gestao_v2/migrar_status_pmib_v2.py`.

### 2.2 Contagens — quem faz é o Power BI v2, não o SIG-FT

Fichas existentes, aprovadas, aptas, aguardando, atrasadas, maior atraso etc. são **medidas do Power BI v2**,
calculadas item a item dos `_STATUS_PMIB` (pacote `gestao-sobressalentes/_gestao_v2/powerbi/`). Por isso o
SIG-FT tem de **gravar certo, em cada `_STATUS_PMIB`, a SITUAÇÃO e os DIAS DE ATRASO** (T3-c) — é deles que o
painel conta. O `_calcula_fichas` continua contando por status **só para a cascata da `SITUAÇÃO NO PMIB`**;
não grava contagem.

---

## 3. Kit de teste e validador (a nuvem não enxerga o Box)

Em `gestao-sobressalentes/_gestao_v2/fixtures/kit_gestao_pmib/` — tudo sintético:

| Arquivo | Para quê |
|---|---|
| `status/#ST00=TESTE01&MPB020_STATUS_PMIB.xlsx` | layout v2; **linhas 6–18 = os 13 casos da regra** (tabela em `gerar_kit_teste_sigft.py`, `CASOS`); 3 comentários em thread |
| `status/#ST00=TESTE02&MPB020_STATUS_PMIB.xlsx` | layout antigo (APTO PARA ENTREGA): só leitura, **não pode ser gravado** |
| `status/testes_autospec/#ST00=TESTE01&MPB020_STATUS_PMIB.xlsx` | **isca**: mesmo código, outros números — tem de ser **ignorada** (T3-a) |
| `mapeadora_sintetica.xlsx` | `Acompanhamento Sobressalente` só com o cadastro + SITUAÇÃO NO PMIB + LINK + CÓDIGO DO PROJETO (REVISÃO EM USO de TESTE01 = "0", velho) + abas vazias |
| `docmanager_sintetico.xlsx` | export do DocManager com as 3 listas (Current = True) |
| `esperado.json` | o resultado certo com **hoje = 2026-10-10** |

**Como validar (ponta a ponta)** — o openpyxl/pandas da suíte `tests/` é dublê (`tests/conftest.py`
stuba sempre), então este teste roda **fora** da suíte, com as bibliotecas reais:

```bash
python -m pip install -r requirements.txt lxml          # openpyxl, pandas, lxml reais
rm -rf /tmp/kit && cp -r gestao-sobressalentes/_gestao_v2/fixtures/kit_gestao_pmib /tmp/kit
python - <<'EOF'
from datetime import date
from sigft.services.pmib_manager import PMIBManager
for _ in PMIBManager().executar_fluxo("/tmp/kit/docmanager_sintetico.xlsx", "/tmp/kit/status",
                                       "/tmp/kit/mapeadora_sintetica.xlsx", hoje=date(2026, 10, 10)):
    pass
EOF
python gestao-sobressalentes/_gestao_v2/validar_kit_gestao_pmib.py /tmp/kit      # tem de dizer: KIT OK
```

O validador confere: SITUAÇÃO e DIAS linha a linha; DIAS sem formato de data; comentários byte a byte;
`sigft_calculado_em`; TESTE02 e isca intocados; na mapeadora, SITUAÇÃO NO PMIB, REVISÃO EM USO, o link apontando
para o arquivo real (não a isca) e **nenhuma coluna de contagem criada**.
`python validar_kit_gestao_pmib.py --referencia` roda a implementação de referência e dá KIT OK — prova
que o esperado é atingível. Sugestão: transformar esse roteiro num teste em `tests_integracao/` (pasta
própria, sem o `conftest` que stuba) ou num `scripts/validar_kit.sh`.

Para os testes **unitários** da regra (dentro da suíte, só stdlib): use os 13 casos de `CASOS`.

---

## 4. Etapas

### T0 — Cabeçalho na linha 5 (pequeno)
**Onde**: `sigft/app/views/pdm.py` ≈ linha 438 — `pd.read_excel(status_pmib, sheet_name="Lista de Materiais", skiprows=3)`.
**Como**: busca dinâmica como em `sigft/services/duplicadas.py` ≈ 139 (`headers.find_header_row` nas 10–30
primeiras linhas, procurando `CÓDIGO PMIB`). `config.LINHA_STATUS_PMIB` (4) é só *fallback* — passar a 5 e
ajustar `scripts/gerar_dados_de_teste.py` e `tests/test_config.py`/`test_gerar_dados_de_teste.py` (a linha 4
passa a ser a da revisão).
**Pronto quando**: nenhuma leitura de `_STATUS_PMIB` com `skiprows`/`header` fixo (grep).

### T1 — Gravar `_STATUS_PMIB` sem apagar nada (pré-requisito da T3)
O openpyxl apaga comentários em thread e listas suspensas x14 ao salvar.
1. Trazer `gestao-sobressalentes/_gestao_v2/xlsx_cirurgico.py` para `sigft/core/excel/cirurgico.py`
   (precisa de `lxml` — mover de `requirements-dev.txt` para `requirements.txt`). Só `PlanilhaXlsx`,
   `escrever`, `estilo_formato_geral`, `definir_nome`, `salvar` e auxiliares; o `deslocar` não é necessário.
2. `sigft/core/excel/status_sheet.py` (`StatusPMIB`): continua **lendo** com openpyxl, mas as **escritas** são
   registradas (`escrever(linha, coluna, valor)`) e aplicadas no `salvar()` com `PlanilhaXlsx`, por cima do
   mesmo arquivo, mantendo o estilo da célula. Arquivo aberto no Excel: manter o retry de `core.excel.locking`
   (um adaptador com `.save(path)` que chama `PlanilhaXlsx.salvar(path)`).
3. Trocar as gravações diretas em `services/cria_fichas.py` (≈ 136), `services/upload_conditions.py` (≈ 413) e
   qualquer outro `wb.save`/`save_with_retry` cujo alvo seja `*_STATUS_PMIB.xlsx`.
**Testes**: fixture `_gestao_v2/fixtures/status_pmib_v2_sintetico.xlsx` — escrever `COMPLETO` numa seção,
salvar e conferir `xl/threadedComments/*`, `xl/persons/*`, `xl/comments*` idênticos byte a byte.
**Pronto quando**: grep não acha salvamento de `_STATUS_PMIB` pelo openpyxl.

### T2 — A regra como módulo puro
`sigft/services/autorizacao.py`, **só stdlib** (a suíte não tem numpy/pandas reais):
`somar_dias_uteis()`, `situacao_autorizacao(email, situacao_atual, entregue, hoje, dias_atual, tipo, status)`
→ `(situacao, dias)` seguindo a tabela 2.1 inteira (inclusive a regra 1), `dias_de_atraso_na_autorizacao()`,
normalização de tipo. `FERIADOS` em `sigft/config.py` (constante nova).
**Testes** (`tests/test_autorizacao.py`): os 13 casos de `CASOS` com hoje = 2026-10-10, mais os três prazos
da seção 2.1. **Pronto quando**: testes verdes.

### T3 — `sigft/services/pmib_manager.py` (o centro da tarefa)

**a) Ignorar pastas de teste e cópias** — **defeito encontrado em 05/10**: o `os.walk` de `executar_fluxo`
(≈ 363) pega também `testes_autospec/`; para `#ST00=B01BMU10&EPB020` o link "Abrir Box" da mapeadora aponta
para a cópia de teste, e as contagens podem vir dela (a última encontrada sobrescreve). Pular pastas cujo
caminho contenha `00 - OBSOLETO`, `OBSOLETO`, `10- TESTES`, `TESTES_AUTOSPEC`, `\DATASHEETS\`, `BACKUP`
(sem acento/maiúsculas) e arquivos com `~$`, ` - COPY`, `- CÓPIA`, `COPIA`, `COMENT`, `RESPOSTA` no nome —
mesma lista de `IGNORAR_PASTAS`/`IGNORAR_ARQUIVOS` em `regras_sobressalentes.py`. Se dois arquivos vivos tiverem
o mesmo código, logar e usar o modificado por último — nunca em silêncio.

**b) `hoje` injetável**: `executar_fluxo(..., hoje: date | None = None)` (padrão `date.today()`), repassado a
quem calcula. Sem isso o kit não é testável.

**c) Recalcular e gravar o `_STATUS_PMIB`** — novo método (ex.: `_atualizar_autorizacao(caminho, hoje)`), chamado
no passo 5 **antes** de `_ler_status_pmib`, para cada arquivo vivo (já com o caminho pós-renomeação):
- achar o cabeçalho (linha com `CÓDIGO DO MATERIAL`/`CÓDIGO PMIB` nas 10 primeiras) e as colunas **pelo nome**;
- sem `SITUAÇÃO DA AUTORIZAÇÃO` → log "arquivo sem layout v2" e **não gravar nada**;
- linha a linha, `autorizacao.situacao_autorizacao(...)`; gravar com o editor da T1 **só as células que mudaram**;
- **DIAS DE ATRASO é número**: se a célula vier como data (formato herdado da vizinha), o openpyxl entrega
  `datetime` — converter com `openpyxl.utils.datetime.to_excel()`; ao gravar, se o estilo da célula tiver formato
  de data, usar `PlanilhaXlsx.estilo_formato_geral(s)` (senão 4 aparece como 04/01/1900);
- gravar o nome definido `sigft_calculado_em` = data do cálculo (texto `"AAAA-MM-DD"`);
- arquivo aberto no Excel → retry de `locking`; falhou → log com o nome do arquivo e segue.

**d) `_ler_status_pmib`** (≈ 160): em `colunas_desejadas` acrescentar `'TIPO DE ENTREGA'`,
`'SITUAÇÃO DA AUTORIZAÇÃO'`, `'DIAS DE ATRASO'`; manter `'APTO PARA ENTREGA'` (arquivo antigo).

**e) `_calcula_fichas`** (≈ 213–339): **apagar** o bloco "Novas Regras: Apto para Entrega e Atraso Itaipu" (o dos
**14 dias corridos** e do "Atualizar template") e as contagens que só serviam à mapeadora; manter só o que a
cascata da `SITUAÇÃO NO PMIB` usa (total de fichas e contagem por STATUS).

**f) Revisão em uso → mapeadora** (no mesmo laço): ler, nas linhas **acima do cabeçalho**, a célula cujo texto
começa com `REVISÃO DA LISTA DE SOBRESSALENTES` (pelo texto, nunca pela coordenada) e extrair
`EM USO:\s*(.+?)\s*-\s*DATA DE ALTERA` (pode ser `SEM LISTA`). Gravar em `REVISÃO EM USO` da linha da lista.
Sem a linha, ou revisão `—`/vazia: **não mexer** em G e logar. A formatação condicional G≠C fica como está.

**g) Gravação na mapeadora** (passo 6, ≈ 535): o `gerenciadora_map` fica só com `'LINK DA PLANILHA'`; apagar a
gravação dos `ÍNDICE DE …`; manter a cascata da `SITUAÇÃO NO PMIB` e acrescentar a `REVISÃO EM USO` (f). Colunas
achadas pelo nome da linha 2; coluna inexistente é pulada sem erro. A mapeadora pode continuar sendo gravada pelo
openpyxl (não tem comentário em thread nem lista x14; as mensagens de validação são padrão e sobrevivem) — mas
registre isso num comentário, porque deixa de valer se alguém comentar na mapeadora.

**Pronto quando**: validador do kit **KIT OK**; `check.sh` verde; grep sem `to_timedelta(14` e sem
`"Atualizar template"`.

### T4 — Export de autorizados grava SITUAÇÃO
`apto_para_entrega_att.py` **não está no código do app** (vive no Box em `15 - PDM/_python_pdm/SIG-FT/`); cópia
de referência em `gestao-sobressalentes/_gestao_v2/referencia_sigft/apto_para_entrega_att.py` (versão de 28/07/2026).
Traga para `sigft/services/autorizados.py` (caminhos vindos da tela/config, não fixos no código; o `os.walk`
com as mesmas exclusões da T3-a — hoje ele também entra em `testes_autospec/`). Para cada PMIB do
`sobressalentes_autorizados_AAAAMMDDhhmm.xlsx`: SITUAÇÃO := `AUTORIZADO` (é fato — vale para qualquer tipo); se
DIAS DE ATRASO estiver vazio, DIAS := `dias_de_atraso_na_autorizacao(email, data do export)` (data tirada do
nome do arquivo; vazio se veio no prazo). Gravar com o editor da T1. Layout antigo: APTO := SIM, como hoje.

### T5 — Listas de preços em `PB021` (depois)
Reconhecer lista de preços pelo DCC `PB021` (o `PB020-0x` é legado). Ver [[Plano - Aba de Listas de Precos]].

### T6 — Gerar a Lista de Preços **revisão 0A** a partir do `_STATUS_PMIB` (ideia do Luan, 05/10/2026)

> [!important] Como esta etapa é validada
> Não houve protótipo antes (decisão do Luan). Implemente contra o **template oficial** e o kit
> `fixtures/kit_lista_precos/`; a validação final é **prática**: o Luan gera listas reais no trabalho e abre no
> Excel. Se algo do formato não bater, os ajustes virão desses exemplos — registre cada um e ajuste aqui.
> **Não use a lista do PDG (`#ST00=B03BDV10UC012-UC001&EPB021`) como modelo**: pode ter desvios do padrão
> (colunas a mais, `CÓDIGO CMI` no lugar de `CÓDIGO GE`, fórmulas auxiliares). O modelo é o template.

> [!danger] A macro é inegociável
> O template `15 - PDM/Templates/Lista de Sobressalentes com preço.xlsm` tem a macro `ConfigurarRodapeCompleto`
> (módulo `Módulo1`), disparada pelo `Worksheet_Change` da Capa quando muda `D37`, `F37` ou `I37`: ela escreve os
> rodapés da `Contracapa` e da `Lista de Materiais` (código do emitente, código de Itaipu com `&`→`&&`, folha,
> revisão). **O arquivo gerado continua `.xlsm` com a macro intacta, e o rodapé é feito PELA MACRO** — não
> escrever rodapé por fora. Se não for possível manter a macro, a T6 está cancelada (palavra do Luan).

**O quê**: tela nova (ex.: "Lista de Preços 0A") onde se escolhe o `_STATUS_PMIB` e o template (caminho lembrado
em config); gera `{código Itaipu da lista de preços}.xlsm` na pasta do `_STATUS_PMIB`. **Só revisão 0A**.

**Recusar (mensagem clara, nada gravado)**: `_STATUS_PMIB` sem a coluna TIPO DE ENTREGA; linha com CÓDIGO PMIB e
TIPO DE ENTREGA vazio (listar as linhas — classificar primeiro; a mesma classificação serve à autorização);
arquivo de saída já existe (nunca sobrescrever uma lista de preços).

**Campos da tela** (pré-preenchidos, editáveis):

| Campo | Pré-preenchimento | Vai para |
|---|---|---|
| código Itaipu da lista de preços | código da lista com `PB020` → `PB021` (`…&EPB020` → `…&EPB021`); código fora do padrão (sufixo `-0x`, `EBP020`): em branco e obrigatório | nome do arquivo, `Capa!F37` |
| controle do emitente | vazio, obrigatório (não há regra segura para deduzir o código CMI da lista de preços) | `Capa!D37` |
| disciplina / sistema / título | da DESCRIÇÃO da lista na mapeadora (título do Aconex) cortada em " - ": o pedaço `ENG. …` → disciplina; o seguinte → sistema; o resto até `LISTA DE SOBRESSALENTES` → título | `Capa!E25`, `E26`, `E27` (= título + ` - LISTA DE SOBRESSALENTE COM PREÇO`) |
| autoria / verificação / aprovação | os últimos usados | `Capa!B31`, `B33`, `B35`; iniciais (sem DE/DA/DO/DAS/DOS/E) em `Contracapa!E12:G12` |
| data | hoje | `Capa!B37`, `Contracapa!H12` |
| incluir linhas DUPLICADO | sim (a lista de preços espelha a de sobressalentes linha a linha — **confirmar no teste prático**) | — |

**Aba `Lista de Materiais`** — cabeçalho na linha 4; itens a partir da **linha 5**, uma por linha do `_STATUS_PMIB`
que tenha DESCRIÇÃO, **na mesma ordem**; colunas do `_STATUS_PMIB` achadas **pelo nome**:

| Col. | Lista de preços | Vem de | Regra |
|---|---|---|---|
| A | ITEM | ITEM | como está (pode ser `11.1`) |
| B | QTD. | QTD. | |
| C | UNID. | UNID. | |
| D | DESCRIÇÃO | DESCRIÇÃO | |
| E | FABRICANTE / MODELO | MARCA/MODELO | |
| F | CÓDIGO DE MATERIAL | CÓDIGO DO MATERIAL | |
| G | CÓDIGO GE | CÓDIGO CMI | vazio em DOCUMENTAL (componente não tem código GE); DOCUMENTAL com código no `_STATUS_PMIB` → **aviso** |
| H | CÓDIGO PMIB | CÓDIGO PMIB | normalizado `4500063671.NNNN`, sem espaços; texto que não é PMIB copiado como está |
| I | VALOR UNITÁRIO | — | **sempre vazio** (quem monta preenche; DOCUMENTAL não tem preço) |
| J | TIPO DE ENTREGA | TIPO DE ENTREGA | texto canônico: `FÍSICA E DOCUMENTAL` · `DOCUMENTAL` · `TÍTULO` |

- **Nunca copiar**: OBSERVAÇÕES (notas internas), STATUS, PDM usado, seções, DATA DO EMAIL, SITUAÇÃO, DIAS,
  ENTREGUE, FORNECEDOR, PROCUREMENT.
- Template: linhas 5–41 pré-formatadas e numeradas 1–37; exemplos em `J5`/`J6` e instrução em `K5`. Escrever por
  cima; **limpar** A..K das linhas numeradas que sobrarem e o `K5`. Mais de 37 itens: criar as linhas 42+ com os
  estilos da linha 6 (os logotipos ficam na linha 2 — não há nada a deslocar).
- Área de impressão da aba (hoje `$A$2:$J$45`) → `$A$2:$J$<última linha de item>`.
- `A3` (texto da cotação do dólar) fica como está — **conferir no teste prático** se a data dele muda.

**Contracapa** linha 12: `A12 = 0A`, `B12 = -`, `D12 = PRIMEIRA EMISSÃO`, `E12:G12` = iniciais, `H12` = data.

**Como gravar — dois passos**:
1. **Preencher** uma cópia do template com o editor cirúrgico (T1) — nunca openpyxl: o arquivo tem macro
   (`xl/vbaProject.bin`), o carimbo de Itaipu embutido (objeto Word), imagens e metadados; tudo sai idêntico, e o
   `.xlsm` continua `.xlsm`. Os rodapés **não** são tocados aqui.
2. **Deixar a macro fazer o rodapé**, no Excel do computador do trabalho, via `xlwings` (o SIG-FT já usa no módulo
   de tradução): abrir o arquivo num Excel **visível**, com `Application.EnableEvents = True`, e **regravar** em
   `Capa!D37`, `F37` e `I37` os mesmos valores — é o gatilho documentado da macro (o mesmo que a pessoa digitando).
   A macro termina com `MsgBox "Rodapés configurados nas planilhas."`: a pessoa clica OK (é a confirmação). Salvar
   pelo próprio Excel (preserva a macro) e fechar. Excel indisponível ou falhou → log claro + instrução na tela:
   "abra o arquivo e redigite D37, F37 e I37 da Capa (ou Alt+F8 → ConfigurarRodapeCompleto)".

**Testes**: kit `fixtures/kit_lista_precos/` — o template oficial, um `_STATUS_PMIB` sintético com os quatro casos
de tipo, um DOCUMENTAL com código CMI (aviso), um PMIB com espaços e uma OBSERVAÇÃO "NOTA INTERNA" que não pode
vazar. Gerar com os `parametros` do `esperado_lista_precos.json` e rodar
`python gestao-sobressalentes/_gestao_v2/validar_lista_precos_0a.py "<saída>.xlsm"` até **LISTA OK**:
- na nuvem (sem Excel) confere o passo 1, inclusive a macro **byte a byte**;
- no trabalho, depois do passo 2, com `--com-excel` confere também os **rodapés feitos pela macro**.
Recusas: o `_STATUS_PMIB` do `kit_gestao_pmib` (TIPO vazio nas linhas 12, 19–22) tem de ser recusado; gerar duas
vezes → a segunda recusa.

### T6b — Conferir lista de preços × `_STATUS_PMIB` (0B em diante; só relatório)
Depois da 0A a lista de preços tem histórico próprio — **não regerar**. Comparar a aba `Lista de Materiais` de uma
lista de preços com o `_STATUS_PMIB` (pelo CÓDIGO PMIB) e listar: item de um lado que falta no outro; QTD. ou TIPO
diferente; FÍSICA sem CÓDIGO GE ou sem VALOR; DOCUMENTAL com CÓDIGO GE ou VALOR. Só relatório, nada gravado.

---

## 5. Convenções e cuidados

- Código, comentários e documentação em português; **commits sem acento**; uma etapa por commit.
- Zonas do Rafael (`rafhagmm`, AutoSpecAI): `core/rpa/ficha_layout.py`, `config.LLM_TASKS`,
  `core/llm/prompts.py` — não tocar; `config.py` só ganha constantes novas.
- **Falha silenciosa é pior que falha ruidosa**: todo arquivo não processado aparece no log com o motivo.
- Não criar fórmula em planilha; não renomear coluna da mapeadora nem do `_STATUS_PMIB`.
- O que achar fora do escopo vai para `docs/refatoracao/PENDENCIAS.md`.

## 6. Depois do merge (o Luan, no computador do trabalho)
Rodar o Gestão PMIB uma vez e conferir: na mapeadora, REVISÃO EM USO e SITUAÇÃO NO PMIB preenchidas e o link
"Abrir Box" de `#ST00=B01BMU10&EPB020` apontando para o arquivo real (não `testes_autospec`); num `_STATUS_PMIB`,
SITUAÇÃO e DIAS DE ATRASO atualizados e o comentário em thread intacto; o Power BI v2 atualizando com os números
novos. Para a T6: gerar a 0A de uma lista real, clicar OK no aviso da macro e conferir capa, itens e rodapé no PDF.

## Relacionados
[[Plano - Reestruturacao do STATUS_PMIB]] · [[Mapeamento das Listas de Sobressalentes]] ·
[[Plano - Revisao em Uso automatica]] · [[Planilha STATUS_PMIB]] · [[README]]
