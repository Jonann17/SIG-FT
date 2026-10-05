---
tags: [handoff, sig-ft, status-pmib]
criado: 2026-10-04
atualizado: 2026-10-04
destinatario: sessão Claude Code na nuvem (GitHub), repositório luanccozer/SIG-FT
inicio: 2026-10-05
---

# Tarefa SIG-FT — o SIG-FT no layout v2 do `_STATUS_PMIB`

## Prompt para começar a sessão na nuvem

> Leia `gestao-sobressalentes/07 - Diagnostico/Tarefa SIG-FT - Calculo e Gravacao sem Perda.md`
> e execute a etapa **T0**. Siga as convenções do repositório. Quando terminar e os testes
> passarem, me mostre o que mudou antes de seguir para a próxima etapa.

(Se o Pull Request #2 ainda não foi juntado, abra a sessão no branch
`claude/gestao-sobressalentes-v2`, que é onde a pasta `gestao-sobressalentes/` está.)

## O que mudou nas planilhas (04/10/2026) — já aplicado nos 47 `_STATUS_PMIB`

Da `APLICAÇÃO - LMR` em diante, a tabela ficou assim:

```
... | APLICAÇÃO - LMR | TIPO DE ENTREGA | DATA DO EMAIL COMUNICANDO ENTREGA |
      SITUAÇÃO DA AUTORIZAÇÃO | DIAS DE ATRASO | EQUIPAMENTO ENTREGUE |
      [extras da lista] | FORNECEDOR | PROCUREMENT | OBSERVAÇÕES | [extras]
```

e, **acima do cabeçalho**, uma linha (mesclada) que diz qual revisão da lista de
sobressalentes o arquivo reflete:

```
REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: 0A - DATA DE ALTERAÇÃO: 03/09/2026
```

| Mudança | Consequência para o SIG-FT |
|---|---|
| `APTO PARA ENTREGA` **virou** `SITUAÇÃO DA AUTORIZAÇÃO` (mesma coluna; SIM → `AUTORIZADO`) | todo código que lê/escreve `APTO PARA ENTREGA` passa a usar a SITUAÇÃO |
| Colunas novas `TIPO DE ENTREGA`, `DIAS DE ATRASO`, `FORNECEDOR`, `PROCUREMENT` | o SIG-FT acha coluna **pelo nome** — nada quebra; DIAS DE ATRASO passa a ser gravada por ele |
| Linha da revisão: o cabeçalho desceu da linha 4 para a **5** | quem lê com linha fixa quebra (ver T0); a revisão em uso passa a vir daqui (T3) |
| Não existe coluna de data de autorização nem de prazo | o prazo é regra (15 dias úteis do e-mail), calculado na hora; não é gravado |

Como foi feito: `_gestao_v2/migrar_status_pmib_v2.py` (inserção de colunas/linha como o Excel,
com comentários, listas suspensas e formatação acompanhando). Backup dos originais na máquina
pessoal do Luan (`%LOCALAPPDATA%\Sobressalentes-v2\backup_*`) e no histórico de versões do Box.

### Regra da autorização (decisão do Luan, 04/10/2026)

| SITUAÇÃO DA AUTORIZAÇÃO | Quando | DIAS DE ATRASO |
|---|---|---|
| *(em branco)* | sem DATA DO EMAIL; ou linha `DUPLICADO` não autorizada | em branco |
| `N/A` | `TIPO DE ENTREGA` = `DOCUMENTAL` (componente explodido: só tem ficha; a entrega física — e a autorização — é a do pai, `FÍSICA E DOCUMENTAL`) | em branco |
| `AGUARDANDO ITAIPU` | e-mail enviado, hoje ≤ prazo | em branco |
| `ATRASADO ITAIPU` | hoje > prazo, sem autorização | **dias corridos** desde o prazo: `(hoje − prazo).days` |
| `AUTORIZADO` | Itaipu autorizou (export de autorizados, ou marcado à mão, ou EQUIPAMENTO ENTREGUE = SIM) | **congelado**: o atraso que houve até a autorização (em branco se veio no prazo) |

- **prazo** = 15 dias úteis a partir do e-mail: `np.busday_offset(data_email, 15, roll="backward", holidays=FERIADOS)`.
  `roll="backward"` (com `"forward"` o prazo sai um dia maior para e-mail em fim de semana/feriado —
  diverge do Excel em 468 de 1.500 datas testadas). Feriados: `FERIADOS` de
  `_scripts/regras_sobressalentes.py` (nacionais + Carnaval + Corpus Christi, 2024–2028; o Luan
  ainda vai confirmar se entram os do Paraguai/Foz).
- `AUTORIZADO` **nunca volta** para AGUARDANDO/ATRASADO/N/A (é marcação de fato, não cálculo).
- Ordem: AUTORIZADO (fato) → DOCUMENTAL vira `N/A` → sem e-mail fica em branco → prazo. `TIPO DE ENTREGA`
  vazio conta como físico (precisa de autorização) — conservador. `TÍTULO` também precisa.
  (Correção do Luan em 05/10/2026: ficha documental não precisa de autorização de Itaipu.)
- Implementação de referência: `situacao_autorizacao()` e `dias_de_atraso_na_autorizacao()` em
  `_scripts/regras_sobressalentes.py`.

> [!important] DUPLICADO
> STATUS `DUPLICADO` = o mesmo item repetido **na mesma lista** (repete o PMIB de outra linha):
> não é ficha nova; fica em branco no cálculo (a situação vale pela linha da ficha). Ficha
> duplicada **de outro sistema** = `PDM.9900.000` + PMIB da original em OBSERVAÇÕES — ficha normal.

## Material de referência (nesta pasta do repositório)

| Arquivo | Para quê |
|---|---|
| `_gestao_v2/xlsx_cirurgico.py` | o editor: `PlanilhaXlsx(caminho)`, `parte_da_aba()`, `escrever()`, `salvar()` (e `deslocar()`, não necessário aqui) |
| `_scripts/regras_sobressalentes.py` | `situacao_autorizacao()`, `dias_de_atraso_na_autorizacao()`, `somar_dias_uteis()`, `FERIADOS`, `normalizar_pmib()` |
| `_gestao_v2/migrar_status_pmib_v2.py` | `inventario()` e `conferir()` (modelo dos testes); `TEXTO_REVISAO` (formato da linha) |
| `_gestao_v2/fixtures/status_pmib_v1_sintetico.xlsx` | layout ANTIGO: 3 comentários em thread, 2 listas suspensas x14 — textos trocados por "TEXTO DE TESTE" |
| `_gestao_v2/fixtures/status_pmib_v2_sintetico.xlsx` | a mesma, migrada para o layout v2 (linha de revisão, colunas novas, comentários intactos) |

A sessão na nuvem **não tem acesso ao Box**: use as fixtures.

---

## T0 — Cabeçalho na linha 5 (urgente, pequeno)

**Onde**: `sigft/app/views/pdm.py` ≈ linha 438, modo "selecionar códigos":
`pd.read_excel(status_pmib, sheet_name="Lista de Materiais", skiprows=3)` — cabeçalho fixo na
linha 4. Com a linha de revisão, lê a linha errada e mostra "Coluna 'CÓDIGO PMIB' não encontrada"
(falha visível, sem dano — e já acontecia nas 5 listas que tinham a linha).

**Como**: a mesma busca dinâmica dos outros módulos (`core.excel.headers.find_header_row` nas
10 primeiras linhas, procurando `CÓDIGO PMIB`), como em `services/duplicadas.py` ≈ 139.
Revisar `config.LINHA_STATUS_PMIB = 4`: hoje só serve de *fallback*; documentar que o cabeçalho
real está na linha 5 (o fallback pode ir para 5) e ajustar `scripts/gerar_dados_de_teste.py`
para gerar a linha de revisão (os testes que fixam 4 mudam junto).

**Pronto quando**: `grep -rn "skiprows=3"` não acha leitura de `_STATUS_PMIB`; teste com a fixture v2.

## T1 — Gravar `_STATUS_PMIB` sem apagar nada (prioridade 1)

O **openpyxl apaga** comentários em thread (autor, data, respostas) e listas suspensas gravadas
como extensão (x14) ao salvar. Hoje todo salvamento do SIG-FT faz isso.

**Onde** (conferido no commit `f0ebbc3`; confirmar no atual):
- `sigft/core/excel/status_sheet.py` — classe `StatusPMIB`: abre com `openpyxl.load_workbook` e salva
  delegando a `locking.save_with_retry(self.wb, self.caminho_excel)` (≈ linhas 275–283). **É o ponto central.**
- Gravações diretas: `sigft/services/cria_fichas.py` (≈ 136) e `sigft/services/upload_conditions.py`
  (≈ 413) — confirmar se o alvo é `_STATUS_PMIB`.
- Procurar qualquer outro `wb.save` / `save_with_retry` / `salvar_perguntando` cujo alvo seja `*_STATUS_PMIB.xlsx`.

**Como**:
1. Trazer `xlsx_cirurgico.py` para `sigft/core/excel/cirurgico.py` (com testes próprios).
2. `StatusPMIB` continua **lendo** com openpyxl, mas as **escritas** passam por um método
   (ex.: `escrever(linha, coluna, valor)`) que as registra; o `salvar()` abre o arquivo com
   `PlanilhaXlsx`, aplica as escritas (mantendo o estilo da célula) e grava por cima do mesmo arquivo.
3. Arquivo aberto no Excel: manter o retry de `locking` — um adaptador com `.save(path)` que chama
   `PlanilhaXlsx.salvar(path)` resolve.
4. Trocar nos serviços as atribuições diretas (`ws.cell(...).value = x` + save) pelo método novo.

**Testes** (fixtures v1 e v2): escrever `COMPLETO` numa seção, salvar e conferir — partes
`xl/threadedComments/*`, `xl/persons/*`, `xl/comments*` **idênticas byte a byte**; listas x14 da v1
continuam; `inventario()` igual antes e depois; o valor escrito é lido de volta. Arquivo travado → retry.

**Pronto quando**: não sobra salvamento de `_STATUS_PMIB` pelo openpyxl (grep) e os testes passam.

## T2 — Gestão PMIB: situação e dias de atraso (prioridade 2)

**Onde**: `sigft/services/pmib_manager.py`.
- `_ler_status_pmib` (≈ 160): `colunas_desejadas` mapeia `'APTO PARA ENTREGA'`. Acrescentar
  `'SITUAÇÃO DA AUTORIZAÇÃO'` e `'DIAS DE ATRASO'`; manter `'APTO PARA ENTREGA'` só como leitura de
  arquivo antigo (SIM = AUTORIZADO).
- `_calcula_fichas` (≈ 287–330): hoje conta APTO = SIM e o atraso com **14 dias corridos**
  (`data_limite = DATA INFORME + 14 dias`) e, sem a coluna APTO, escreve "Atualizar template" na mapeadora.

**Como**:
1. Para cada linha de cada `_STATUS_PMIB` v2, calcular SITUAÇÃO e DIAS DE ATRASO pela regra acima
   (preservando AUTORIZADO e o DIAS DE ATRASO congelado) e **gravar** com o editor da T1, só nas
   células que mudaram. Gravar também o nome definido `sigft_calculado_em` (data do cálculo).
2. Mapeadora (as colunas da mapeadora **não** mudam de nome):
   - `APTO PARA ENTREGA` = fichas (PMIB distinto, sem DUPLICADO) com SITUAÇÃO = `AUTORIZADO` e EQUIPAMENTO ENTREGUE ≠ SIM;
   - `ATRASO DE AUTORIZAÇÃO DE ENTREGA ITAIPU` = fichas com SITUAÇÃO = `ATRASADO ITAIPU`.
3. Arquivo sem `SITUAÇÃO DA AUTORIZAÇÃO` (layout antigo): logar "arquivo sem layout v2" e contar pelo
   APTO, sem gravar nada — nunca falhar em silêncio.
4. `FERIADOS` em `sigft/config.py` (só constante nova).

**Testes**: e-mail 15/09/2026 → prazo 06/10/2026; 04/09/2026 + 1 d.u. → 08/09/2026 (07/09 feriado);
hoje 10/10/2026 com e-mail 15/09 → ATRASADO, 4 dias; AUTORIZADO continua AUTORIZADO e mantém o
DIAS DE ATRASO; ENTREGUE = SIM → AUTORIZADO; TIPO DOCUMENTAL com e-mail vencido → `N/A`, sem dias;
DOCUMENTAL já AUTORIZADO continua AUTORIZADO; DUPLICADO não autorizado → em branco; sem e-mail → em
branco; fixture v1 → log e nada gravado. Referência pronta: `recalcular_situacao()` em
`_gestao_v2/migrar_status_pmib_v2.py` (faz exatamente isto num arquivo).

## T3 — Revisão em uso vem do `_STATUS_PMIB` (prioridade 2)

A coluna `REVISÃO EM USO` (G) da aba `Acompanhamento Sobressalente` da mapeadora era digitada à mão.
**A semeadura já foi feita**: a migração escreveu o valor de G na linha de revisão de cada
`_STATUS_PMIB`. Agora inverte: quem mantém é o arquivo (quem reconcilia o `_STATUS_PMIB` com a lista
nova carimba ali), e o Gestão PMIB copia para a mapeadora.

**Como** (no mesmo laço do `pmib_manager` que já abre cada `_STATUS_PMIB`):
1. Procurar, nas linhas **acima do cabeçalho**, a célula cujo texto começa com
   `REVISÃO DA LISTA DE SOBRESSALENTES` (pelo texto, nunca pela coordenada) e extrair a revisão:
   `EM USO:\s*(.+?)\s*-\s*DATA DE ALTERA` (pode ser `SEM LISTA`; `—` = não informado).
2. Escrever em `REVISÃO EM USO` da linha da lista na mapeadora (achar a coluna pelo nome na linha 2,
   como os outros campos). A regra `G<>C` (pinta de vermelho quando difere da última emitida) não muda.
3. Arquivo **sem** a linha, ou revisão `—`: **não apagar** o que está em G; logar.

**Testes**: fixture v2 → lê `0` (ou o que a fixture tiver); texto com espaços extras; linha ausente → None e log.

## T4 — Export de autorizados grava SITUAÇÃO (prioridade 3)

**Onde**: `apto_para_entrega_att.py` — **não está no repositório**; vive no Box em
`15 - PDM/_python_pdm/SIG-FT/` (e uma cópia antiga em `AMP/`). Procura `APTO PARA ENTREGA` pelo nome:
nas planilhas migradas responde "Falta coluna APTO" e não grava (sem dano). Também salva com openpyxl.
O Luan traz o arquivo para o repositório (ex.: `sigft/services/autorizados.py`) antes desta etapa.

**Como**: para cada PMIB do `sobressalentes_autorizados_AAAAMMDDhhmm.xlsx`:
SITUAÇÃO DA AUTORIZAÇÃO := `AUTORIZADO`; se DIAS DE ATRASO estiver vazio,
DIAS DE ATRASO := `dias_de_atraso_na_autorizacao(data_email, data do export)` (data tirada do nome do
arquivo; em branco se veio no prazo). Gravar com o editor da T1. Layout antigo: APTO := SIM, como hoje.

## T5 — Listas de preços em `PB021` (depois)

Reconhecer lista de preços pelo DCC `PB021` (o `PB020-0x` é legado). Ver
[[Plano - Aba de Listas de Precos]] e [[Lista de Precos]].

## Convenções do repositório (valem para todas)

- Código, comentários e documentação em português; **commits sem acento**.
- Uma etapa por vez; o que achar fora do escopo vai para `docs/refatoracao/PENDENCIAS.md`.
- Zonas do Rafael (`rafhagmm`, AutoSpecAI): `core/rpa/ficha_layout.py`, `config.LLM_TASKS`,
  `core/llm/prompts.py` — não tocar; `config.py` só ganha constantes novas.
- `bash scripts/check.sh` verde.
- **Falha silenciosa é pior que falha ruidosa**: arquivo que não pôde ser processado aparece no log.
- Nada de fórmula nas planilhas; não renomear colunas existentes (além do APTO, já renomeado pela migração).

## Relacionados
[[Plano - Reestruturacao do STATUS_PMIB]] · [[Plano - Revisao em Uso automatica]] · [[README]] · [[Planilha STATUS_PMIB]]
