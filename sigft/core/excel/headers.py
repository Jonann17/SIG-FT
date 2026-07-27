r"""
sigft/core/excel/headers.py — busca dinâmica de cabeçalho em planilha
(Checkpoint 1.2 do plano de refatoração).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 1 -> CP 1.2, diagnóstico
seção 1.2: "Busca dinâmica da linha de cabeçalho — ~10×:
`DataManager.carregar_planilha_inteligente`, `analyzer._find_header_columns`,
`autospec.find_header_columns`, `upload_conditions.carregar_lookup_status` e
`atualizar_status_excel`, `tech_specs.encontrar_header`,
`search._encontrar_e_formatar_dataframe`,
`GerenciadorFilaPMIB._encontrar_cabecalho`, `AtualizadorStatusPMIB`,
`pmib_manager._ler_status_pmib`". Este checkpoint também migra um 11º site
equivalente não listado explicitamente no diagnóstico:
`DataManager.atualizar_excel_final` (cria_fichas_no_pmib_v1_backend.py) —
mesmo padrão duplicado, incluído por consistência ("uma implementação por
conceito").

Só stdlib — importável no ambiente de teste, que não tem pandas/openpyxl
instalados (ver tests/conftest.py). Por isso a lógica opera sobre uma
ABSTRAÇÃO PURA: `rows` é qualquer iterável de "linhas", e cada linha é
qualquer sequência de valores de célula (lista, tupla, `pandas.Series`,
resultado de `ws.iter_rows()` já convertido, etc.) — nunca um DataFrame nem
uma worksheet openpyxl diretamente. Cada consumidor adapta sua fonte real
para essa forma:
  - pandas: `df.values.tolist()` (ou equivalente) vira `rows`.
  - openpyxl: usar o adaptador `rows_from_worksheet(ws, ...)` deste módulo
    (não importa openpyxl — funciona com qualquer objeto "duck-typed" que
    responda a `.max_row`, `.max_column` e `.cell(row=, column=).value`).

DUAS funções, DUAS convenções de índice deliberadamente diferentes (cada uma
casa com a família de consumidores que a usa, minimizando conversões nos ~11
call sites):

  - `find_header_row()`: devolve a posição 0-BASED da linha encontrada
    DENTRO de `rows` (ou seja, `rows[0]` -> posição 0). Casa diretamente com
    os 6 consumidores que promovem a linha a cabeçalho via pandas
    (`header=N` / `skiprows=N` são 0-based nesses métodos).
  - `find_columns()`: devolve índices de COLUNA e a linha de cabeçalho
    1-BASED ("estilo Excel": coluna A = 1, primeira linha da planilha = 1).
    Casa diretamente com os 5 consumidores que usam openpyxl
    (`ws.cell(row=, column=)` e `cell.row`/`cell.column` já são 1-based).

Ambas retornam `None` quando a busca não encontra o que precisa dentro do
limite de linhas — cada consumidor decide seu próprio fallback (alguns
zeram tudo, outros usam um valor default; ver o corpo de cada método
migrado), exatamente como cada implementação original já fazia.
"""

from __future__ import annotations

from typing import Callable, Iterable, Mapping, Sequence

CellValue = object
Row = Sequence[CellValue]


def _default_normalize(valor: CellValue) -> str:
    """Normalização padrão para comparação de célula com palavra-chave:
    `None` -> `""`; qualquer outra coisa -> `str(valor).strip().upper()`.

    É a normalização (strip + upper, à prova de `None`) que a MAIORIA das
    ~11 variantes unificadas aqui já usava. Algumas variantes originais eram
    um pouco mais "picky" (ex.: `upload_conditions_backend.carregar_lookup_status`
    comparava o valor cru, sem strip/upper; `upload_tech_specs_backend.encontrar_header`
    fazia só `.strip()`, sem `.upper()`) — usar esta normalização comum para
    todos os sites é estritamente MAIS TOLERANTE (nunca deixa de casar um
    cabeçalho que antes casava) e não muda o resultado para nenhum
    `_STATUS_PMIB`/ficha real (cujos cabeçalhos já são escritos exatamente
    como as palavras-chave, em maiúsculas, sem espaços extras) — mesmo
    espírito da unificação de `normalize_pmib` (ver pmib_codes.py):
    diferença só visível em cabeçalho malformado. Registrado em
    docs/refatoracao/PENDENCIAS.md.
    """
    if valor is None:
        return ""
    return str(valor).strip().upper()


def find_header_row(
    rows: Iterable[Row],
    keywords: str | Iterable[str],
    *,
    max_rows: int | None = None,
    mode: str = "cell",
    require: str = "all",
    normalize: Callable[[CellValue], str] | None = None,
) -> int | None:
    """Varre `rows` procurando a primeira linha que contém `keywords`.

    Parâmetros:
      rows: iterável de linhas (cada linha uma sequência de valores de
        célula). A busca considera `rows[0]` como a posição 0 do resultado
        retornado — ou seja, `rows` deve começar na primeira linha real da
        planilha para o índice devolvido bater com `header=N`/`skiprows=N`
        do pandas.
      keywords: uma palavra-chave (`str`) ou um iterável delas.
      max_rows: para de varrer após este número de linhas (`None` = varre
        `rows` inteiro).
      mode:
        - `"cell"` (default): uma palavra-chave "casa" quando é IGUAL (após
          `normalize`) a algum valor de célula da linha — o padrão de
          `DataManager.carregar_planilha_inteligente`,
          `upload_conditions.carregar_lookup_status`,
          `tech_specs.encontrar_header`,
          `GerenciadorFilaPMIB._encontrar_cabecalho` e
          `pmib_manager._ler_status_pmib`.
        - `"text"`: uma palavra-chave "casa" quando é SUBSTRING do texto
          formado juntando (com espaço) os valores normalizados de todas as
          células da linha — o padrão de
          `search_pmib_backend._encontrar_e_formatar_dataframe` (que junta a
          linha inteira antes de procurar "DESCRIÇÃO"/"DESCRICAO").
      require:
        - `"all"` (default): a linha só "casa" se TODAS as `keywords`
          forem encontradas nela (independente de ordem/posição).
        - `"any"`: a linha "casa" se AO MENOS UMA `keyword` for encontrada.
      normalize: função `valor -> str` usada para comparar células e
        palavras-chave; default: `_default_normalize` (ver acima).

    Retorna a posição 0-based (relativa a `rows`) da primeira linha que
    satisfaz a condição, ou `None` se nenhuma linha satisfizer dentro de
    `max_rows`.
    """
    normalize_fn = normalize or _default_normalize
    keyword_list = [keywords] if isinstance(keywords, str) else list(keywords)
    normalized_keywords = [normalize_fn(kw) for kw in keyword_list]

    for row_idx, row in enumerate(rows):
        if max_rows is not None and row_idx >= max_rows:
            break

        if mode == "text":
            texto_linha = " ".join(normalize_fn(valor) for valor in row)
            achados = [kw in texto_linha for kw in normalized_keywords]
        else:
            valores_linha = {normalize_fn(valor) for valor in row}
            achados = [kw in valores_linha for kw in normalized_keywords]

        linha_casa = all(achados) if require == "all" else any(achados)
        if linha_casa:
            return row_idx

    return None


def find_columns(
    rows: Iterable[Row],
    keywords: Mapping[str, str | Iterable[str]],
    *,
    required: Iterable[str] | None = None,
    max_rows: int | None = None,
    normalize: Callable[[CellValue], str] | None = None,
) -> tuple[dict[str, int], int | None]:
    """Varre `rows` (1-based: `rows[0]` = linha 1 da planilha) procurando,
    célula a célula, colunas nomeadas por palavra-chave — o padrão usado
    pelos consumidores openpyxl que acessam `ws.cell(row=, column=)`
    diretamente (sem "promover" uma linha a cabeçalho de DataFrame).

    Parâmetros:
      rows: iterável de linhas (cada linha uma sequência de valores de
        célula, posição 0 == coluna 1 == "A"). Ver `rows_from_worksheet()`
        para adaptar uma worksheet openpyxl a este formato.
      keywords: dict `{chave_de_saida: palavra_chave_ou_lista_de_aliases}`.
        Suporta MAIS DE UMA grafia mapeando para a MESMA chave de saída
        (ex.: `{"PDM usado": ["PDM USADO", "PDM"]}}` — igual a
        `DataManager.atualizar_excel_final`, que aceita tanto "PDM USADO"
        quanto "PDM" como o mesmo campo).
      required: subconjunto de chaves de `keywords` que precisam ser TODAS
        encontradas (cumulativamente, ao longo das linhas já varridas) para
        a varredura parar; default `None` = toda chave em `keywords` (a
        maioria dos consumidores exige todas). Chaves de `keywords` fora de
        `required` são coletadas de forma OPORTUNISTA (se aparecerem, entram
        no resultado; se não aparecerem, a varredura não trava por causa
        delas) — o padrão de `autospec.find_header_columns` (coluna
        "CÓDIGO MATERIAL" é opcional) e de `AtualizadorStatusPMIB` (as
        colunas de `secoes_concluidas` são coletadas mas só "CÓDIGO PMIB" é
        obrigatória).
      max_rows: para de varrer após este número de linhas.
      normalize: função `valor -> str`; default: `_default_normalize`.

    Algoritmo: para cada linha (em ordem), atualiza `col_map[chave] =
    coluna` (1-based) para toda palavra-chave encontrada nessa linha
    (ocorrência mais recente vence, igual às implementações originais, que
    também sobrescrevem sem checar se a chave já tinha sido vista); depois
    de processar a linha INTEIRA, se todas as chaves de `required` já
    estiverem em `col_map`, a varredura para e essa linha vira `header_row`.

    Retorna `(col_map, header_row)`:
      col_map: dict `chave_de_saida -> coluna (1-based)` — TODAS as chaves
        encontradas até a parada (pode ser um superconjunto de `required`,
        incluindo chaves opcionais; pode estar PARCIAL se a varredura
        terminou sem satisfazer `required` — quem chama decide o que fazer
        com esse resultado parcial, exatamente como cada implementação
        original tinha seu próprio fallback).
      header_row: linha 1-based (relativa a `rows`, ou seja, `rows[0]` é a
        linha 1) em que `required` foi satisfeito, ou `None` se a varredura
        terminou sem satisfazer `required` dentro de `max_rows`.
    """
    normalize_fn = normalize or _default_normalize

    alias_to_key: dict[str, str] = {}
    for chave_saida, aliases in keywords.items():
        alias_list = [aliases] if isinstance(aliases, str) else list(aliases)
        for alias in alias_list:
            alias_to_key[normalize_fn(alias)] = chave_saida

    required_keys = set(keywords) if required is None else set(required)

    col_map: dict[str, int] = {}
    header_row: int | None = None

    for row_idx, row in enumerate(rows, start=1):
        if max_rows is not None and row_idx > max_rows:
            break

        for col_idx, valor in enumerate(row, start=1):
            chave = alias_to_key.get(normalize_fn(valor))
            if chave is not None:
                col_map[chave] = col_idx

        if required_keys.issubset(col_map):
            header_row = row_idx
            break

    return col_map, header_row


def rows_from_worksheet(
    ws: object,
    *,
    max_row: int | None = None,
    max_col: int | None = None,
) -> Iterable[list[CellValue]]:
    """Adapta uma worksheet openpyxl (ou qualquer objeto "duck-typed"
    equivalente) para o formato `rows` esperado por `find_header_row()` e
    `find_columns()`: um iterável de linhas, cada linha uma lista de valores
    de célula começando na coluna 1 ("A").

    NÃO importa openpyxl — usa só `ws.max_row`, `ws.max_column` e
    `ws.cell(row=, column=).value`, então este módulo continua stdlib-only
    (a função só é de fato chamada em produção, nunca durante os testes
    puros deste pacote, que passam listas Python).

    `max_row`/`max_col` (1-based, inclusive) delimitam a varredura; por
    padrão usam `ws.max_row`/`ws.max_column` (a extensão real da planilha).
    Equivalente a `ws.iter_rows(min_row=1, max_row=max_row)` quando
    `max_col` é omitido (mesmo alcance de colunas que o iter_rows padrão).
    """
    limite_linha = ws.max_row if max_row is None else max_row
    limite_coluna = ws.max_column if max_col is None else max_col
    if not limite_linha or not limite_coluna:
        return
    for r in range(1, limite_linha + 1):
        yield [ws.cell(row=r, column=c).value for c in range(1, limite_coluna + 1)]
