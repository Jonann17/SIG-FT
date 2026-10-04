---
tags: [handoff, sig-ft, status-pmib]
criado: 2026-10-04
destinatario: sessão Claude Code na nuvem (GitHub), repositório luanccozer/SIG-FT
---

# Tarefa SIG-FT — calcular a autorização de Itaipu e gravar sem apagar nada

## Prompt para começar a sessão na nuvem

> Leia `gestao-sobressalentes/07 - Diagnostico/Tarefa SIG-FT - Calculo e Gravacao sem Perda.md`
> e execute a etapa **T1**. Siga as convenções do repositório. Quando terminar e os testes
> passarem, me mostre o que mudou antes de seguir para a T2.

(Se o Pull Request #2 ainda não foi juntado, abra a sessão no branch
`claude/gestao-sobressalentes-v2`, que é onde a pasta `gestao-sobressalentes/` está.)

## Contexto em cinco linhas

- O `_STATUS_PMIB` (um por lista de sobressalentes) ganha um bloco de colunas v2 — ver
  [[Plano - Reestruturacao do STATUS_PMIB]].
- **Decisão do Luan (04/10/2026): nenhum cálculo no Excel.** Prazo, situação e atraso da
  autorização de Itaipu são **valores gravados pelo SIG-FT** quando roda. Sem fórmula, sem aba de feriados.
- **O openpyxl apaga** comentários em thread (autor, data, respostas) e listas suspensas gravadas
  como extensão (x14) ao salvar. Hoje o SIG-FT salva os `_STATUS_PMIB` com openpyxl → cada rodada
  apaga isso. Os comentários são importantes para o Luan.
- Solução já testada: `xlsx_cirurgico.py`, que altera só as partes necessárias do `.xlsx` e
  regrava o resto byte a byte.
- A sessão na nuvem **não tem acesso ao Box**: use as fixtures sintéticas abaixo.

## Material de referência (nesta pasta do repositório)

| Arquivo | Para quê |
|---|---|
| `_gestao_v2/xlsx_cirurgico.py` | o editor: `PlanilhaXlsx(caminho)`, `parte_da_aba()`, `escrever()`, `salvar()` |
| `_scripts/regras_sobressalentes.py` | `situacao_autorizacao()`, `somar_dias_uteis()`, `FERIADOS`, `normalizar_pmib()` |
| `_gestao_v2/migrar_status_pmib_v2.py` | `gravar_calculos()` (modelo da T2), `inventario()` e `conferir()` (modelo dos testes) |
| `_gestao_v2/fixtures/status_pmib_v1_sintetico.xlsx` | layout ATUAL: 3 comentários em thread, 2 listas suspensas x14 — textos trocados por "TEXTO DE TESTE" |
| `_gestao_v2/fixtures/status_pmib_v2_sintetico.xlsx` | a mesma, migrada para o v2 (listas por nome definido, comentários intactos) |

### Nomes exatos das colunas v2 (com acento — o SIG-FT procura por nome)
`TIPO DE ENTREGA` · `FORNECEDOR` · `PROCUREMENT` · `DATA DA AUTORIZAÇÃO ITAIPU` ·
`PRAZO AUTORIZAÇÃO ITAIPU (15 D.U.)` · `SITUAÇÃO DA AUTORIZAÇÃO` · `DIAS ÚTEIS DE ATRASO`

### Valores de SITUAÇÃO DA AUTORIZAÇÃO
`AGUARDANDO ITAIPU` · `ATRASADO ITAIPU` · `AUTORIZADO NO PRAZO` · `AUTORIZADO COM ATRASO` · `AUTORIZADO`
(em branco: sem e-mail de intenção, ou linha `DUPLICADO`).

> [!important] DUPLICADO
> STATUS `DUPLICADO` = o mesmo item repetido **na mesma lista** (repete o PMIB de outra linha):
> não é ficha nova e fica em branco no cálculo. Ficha duplicada **de outro sistema** =
> `PDM.9900.000` + PMIB da original em OBSERVAÇÕES — ficha normal.

---

## T1 — Gravar `_STATUS_PMIB` sem apagar nada (prioridade 1)

**Onde** (conferido no commit `f0ebbc3`; confirmar no atual):
- `sigft/core/excel/status_sheet.py` — classe `StatusPMIB`: abre com `openpyxl.load_workbook` e salva
  delegando a `locking.save_with_retry(self.wb, self.caminho_excel)` (≈ linhas 275–283). **É o ponto central.**
- Gravações diretas: `sigft/services/cria_fichas.py` (≈ 136, `locking.save_with_retry(wb, filepath)`) e
  `sigft/services/upload_conditions.py` (≈ 413) — confirmar se o alvo é `_STATUS_PMIB`.
- Script de aptos (`apto_para_entrega_att.py`), se estiver no repositório.
- Procurar qualquer outro `wb.save` / `save_with_retry` / `salvar_perguntando` cujo alvo seja `*_STATUS_PMIB.xlsx`.

**Como**:
1. Trazer `xlsx_cirurgico.py` para `sigft/core/excel/cirurgico.py` (com testes próprios).
2. `StatusPMIB` continua **lendo** com openpyxl (achar cabeçalho, linhas, valores), mas as
   **escritas** passam por um método (ex.: `escrever(linha, coluna, valor)`) que as registra; o
   `salvar()` abre o arquivo com `PlanilhaXlsx`, aplica as escritas (mantendo o estilo da célula) e
   grava por cima do mesmo arquivo.
3. Arquivo aberto no Excel: manter o retry de `locking` — ele aceita qualquer objeto com
   `.save(path)`; um adaptador que chama `PlanilhaXlsx.salvar(path)` resolve.
4. Trocar nos serviços as atribuições diretas (`ws.cell(...).value = x` seguido de save) pelo método novo.

**Testes** (com a fixture v1 e a v2):
- escrever `COMPLETO` numa seção e o `CÓDIGO PMIB` numa linha, salvar, e conferir: as partes
  `xl/threadedComments/*`, `xl/persons/*`, `xl/comments*` saem **idênticas byte a byte**; as listas x14
  da v1 continuam; `inventario()` igual antes e depois; o valor escrito é lido de volta pelo openpyxl.
- arquivo travado → retry, não exceção.

**Pronto quando**: não sobra nenhum salvamento de `_STATUS_PMIB` pelo openpyxl (grep) e os testes passam.

## T2 — Calcular e gravar a autorização (prioridade 2)

**Onde**: Gestão PMIB — `sigft/services/pmib_manager.py`, no laço que lê cada `_STATUS_PMIB`
(`_ler_status_pmib` / `_calcula_fichas`). A regra antiga está em `_calcula_fichas`
(≈ linha 319): `data_limite = df_com_data['DATA INFORME'] + pd.to_timedelta(14, unit='D')`.

**Como**:
- `FERIADOS` em `sigft/config.py` (copiar de `regras_sobressalentes.py`; o Luan ainda vai confirmar
  se entram feriados do Paraguai/Foz).
- `prazo = np.busday_offset(datas, 15, roll="backward", holidays=FERIADOS)` — **`roll="backward"`**:
  com `"forward"` o prazo sai um dia maior para e-mail enviado em fim de semana/feriado (testado:
  diverge do Excel em 468 de 1.500 datas).
- Situação e atraso: mesma lógica de `situacao_autorizacao()`. Linha `DUPLICADO` em branco.
- Só para arquivos com o layout v2 (cabeçalho com `SITUAÇÃO DA AUTORIZAÇÃO`); nos outros, logar
  "arquivo sem layout v2" — nunca falhar em silêncio.
- Gravar com o editor da T1 as três colunas e o nome definido `sigft_calculado_em` (data do cálculo).
- A coluna `ATRASO DE AUTORIZAÇÃO DE ENTREGA ITAIPU` da mapeadora passa a contar fichas
  (PMIB distinto, sem DUPLICADO) com SITUAÇÃO = `ATRASADO ITAIPU`.

**Testes**: e-mail 15/09/2026 → prazo 06/10/2026; 04/09/2026 + 1 d.u. → 08/09/2026 (07/09 feriado);
ATRASADO quando hoje > prazo e sem autorização; AUTORIZADO quando APTO = SIM sem data;
AUTORIZADO COM ATRASO quando a data de autorização passa do prazo; DUPLICADO em branco;
arquivo v1 → log e nada gravado.

## T3 — Data da autorização no script de aptos

Ao virar APTO = SIM pelo export `sobressalentes_autorizados_AAAAMMDDhhmm.xlsx`, gravar (com o
editor da T1) `DATA DA AUTORIZAÇÃO ITAIPU` = data do export, só se a célula estiver vazia.

## T4 — Listas de preços em `PB021` (depois)

Reconhecer lista de preços pelo DCC `PB021` (o `PB020-0x` é legado). Ver
[[Plano - Aba de Listas de Precos]] e [[Lista de Precos]].

## Convenções do repositório (valem para todas)

- Código, comentários e documentação em português; **commits sem acento**.
- Uma etapa por vez; o que achar fora do escopo vai para `docs/refatoracao/PENDENCIAS.md`.
- Zonas do Rafael (`rafhagmm`, AutoSpecAI): `core/rpa/ficha_layout.py`, `config.LLM_TASKS`,
  `core/llm/prompts.py` — não tocar; `config.py` só ganha constantes novas.
- `bash scripts/check.sh` verde.
- **Falha silenciosa é pior que falha ruidosa**: arquivo que não pôde ser processado aparece no log.
- Nada de fórmula nas planilhas; não renomear colunas existentes.

## Relacionados
[[Plano - Reestruturacao do STATUS_PMIB]] · [[README]] · [[Planilha STATUS_PMIB]]
