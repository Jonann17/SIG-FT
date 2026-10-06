r"""
Testes do Checkpoint 1.3 — `sigft/core/excel/status_sheet.py` (`StatusPMIB`).

`StatusPMIB` é exercitada com um workbook/worksheet FALSOS (duck-typed, em
memória, sem depender do pacote openpyxl instalado — mesmo espírito de
`_FakeWorksheet` em `tests/test_headers.py`, mas com células MUTÁVEIS e
persistentes por coordenada, necessário para testar `marcar_linha`/
`salvar`). Cobre os 3 passos citados no plano (carregar/achar cabeçalho via
`headers`, buscar linha por PMIB via `pmib_codes.normalize_pmib`,
`marcar_completo`) e a composição com `locking.save_with_retry`.
"""
import sys

import pytest

from sigft import config
from sigft.core.excel.status_sheet import StatusPMIB, VALOR_COMPLETO


# ===========================================================================
# Fakes — workbook/worksheet duck-typed, sem openpyxl real.
# ===========================================================================

class _FakeCell:
    def __init__(self, value=None):
        self.value = value


class _FakeWorksheet:
    """Worksheet com células MUTÁVEIS e persistentes por coordenada (ao
    contrário do `_FakeWorksheet` de `test_headers.py`, que é só leitura):
    `ws.cell(row=r, column=c).value = X` deve "colar", igual a uma
    worksheet openpyxl de verdade."""

    def __init__(self, grid, max_row=None, max_column=None):
        self._cells = {}
        for r, row in enumerate(grid, start=1):
            for c, val in enumerate(row, start=1):
                self._cells[(r, c)] = _FakeCell(val)
        self.max_row = max_row if max_row is not None else len(grid)
        self.max_column = max_column if max_column is not None else max(
            (len(r) for r in grid), default=0
        )

    def cell(self, row, column):
        key = (row, column)
        if key not in self._cells:
            self._cells[key] = _FakeCell(None)
        return self._cells[key]


class _FakeWorkbook:
    """`wb` duck-typed: `.save(path)` + `.close()` + `__getitem__` (aba por
    nome). `falhas_antes_do_sucesso` permite simular arquivo bloqueado."""

    def __init__(self, worksheets, falhas_antes_do_sucesso=0):
        self._worksheets = worksheets
        self.falhas_antes_do_sucesso = falhas_antes_do_sucesso
        self.chamadas_save = 0
        self.paths_salvos = []
        self.closed = False

    def __getitem__(self, nome_aba):
        return self._worksheets[nome_aba]

    def save(self, path):
        self.chamadas_save += 1
        if self.chamadas_save <= self.falhas_antes_do_sucesso:
            raise PermissionError("arquivo aberto no Excel")
        self.paths_salvos.append(path)

    def close(self):
        self.closed = True


class _GravadorFalso:
    """Dublê do editor cirúrgico (`core.excel.cirurgico.gravar_celulas`):
    registra o que seria gravado. `falhas_antes_do_sucesso` simula arquivo
    aberto no Excel, como o `_FakeWorkbook` faz para o `wb.save`."""

    def __init__(self, falhas_antes_do_sucesso=0):
        self.falhas_antes_do_sucesso = falhas_antes_do_sucesso
        self.chamadas = []
        self.gravados = []

    def __call__(self, caminho, aba, escritas, *, nomes, formato_geral):
        self.chamadas.append(caminho)
        if len(self.chamadas) <= self.falhas_antes_do_sucesso:
            raise PermissionError("arquivo aberto no Excel")
        self.gravados.append({
            "caminho": caminho, "aba": aba, "escritas": dict(escritas),
            "nomes": dict(nomes), "formato_geral": set(formato_geral),
        })


def _painel_status_pmib_padrao():
    """Grade típica de `_STATUS_PMIB`: cabeçalho na linha 2 (linha 1 é
    título/mesclagem), colunas CÓDIGO PMIB / DESCRIÇÃO / CONDIÇÕES /
    CARACT. TÉCNICAS / INFO. GERAIS, 3 linhas de dados."""
    grid = [
        ["Planilha STATUS_PMIB", None, None, None, None],
        ["CÓDIGO PMIB", "DESCRIÇÃO", "CONDIÇÕES", "CARACT. TÉCNICAS", "INFO. GERAIS"],
        ["4500063671.1000", "Item 1", "", "", ""],
        ["4500063671.1234", "Item 2", "", "", ""],
        ["4500063671.2000", "Item 3", "COMPLETO", "", ""],
    ]
    ws = _FakeWorksheet(grid)
    wb = _FakeWorkbook({config.ABA_LISTA_MATERIAIS: ws})
    return wb, ws


# ===========================================================================
# abrir() — carregar workbook/worksheet + achar colunas via headers
# ===========================================================================

def test_abrir_com_ws_injetada_nao_precisa_de_wb():
    _, ws = _painel_status_pmib_padrao()
    painel = StatusPMIB("qualquer_caminho.xlsx")

    col_map, header_row = painel.abrir(ws=ws)

    assert header_row == 2
    assert col_map == {config.COL_CODIGO_PMIB: 1}  # keywords default: só a âncora
    assert painel.wb is None  # nenhum wb foi passado nem criado
    assert painel.ws is ws


def test_abrir_aceita_wb_e_ws_prontos_e_guarda_os_dois():
    wb, ws = _painel_status_pmib_padrao()
    painel = StatusPMIB("qualquer.xlsx")

    painel.abrir(wb=wb, ws=ws)

    assert painel.wb is wb
    assert painel.ws is ws


def test_abrir_usa_nome_aba_do_wb_quando_so_wb_e_passado():
    wb, ws = _painel_status_pmib_padrao()
    painel = StatusPMIB("qualquer.xlsx", nome_aba=config.ABA_LISTA_MATERIAIS)

    painel.abrir(wb=wb)  # sem ws -- deve resolver via wb[self.nome_aba]

    assert painel.ws is ws


def test_abrir_com_keywords_customizadas_e_required_parcial():
    _, ws = _painel_status_pmib_padrao()
    painel = StatusPMIB("c.xlsx")

    keywords = {
        config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB,
        "INFO. GERAIS": "INFO. GERAIS",
        "CONDIÇÕES": "CONDIÇÕES",
    }
    col_map, header_row = painel.abrir(keywords=keywords, ws=ws, required=[config.COL_CODIGO_PMIB])

    assert header_row == 2
    assert col_map == {config.COL_CODIGO_PMIB: 1, "CONDIÇÕES": 3, "INFO. GERAIS": 5}


def test_abrir_max_row_limita_a_busca_de_cabecalho():
    _, ws = _painel_status_pmib_padrao()
    painel = StatusPMIB("c.xlsx")

    col_map, header_row = painel.abrir(ws=ws, max_row=1)  # cabeçalho está na linha 2

    assert header_row is None
    assert col_map == {}


def test_abrir_max_col_limita_quais_colunas_sao_encontradas():
    _, ws = _painel_status_pmib_padrao()
    painel = StatusPMIB("c.xlsx")
    keywords = {config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB, "CARACT. TÉCNICAS": "CARACT. TÉCNICAS"}

    col_map, header_row = painel.abrir(ws=ws, keywords=keywords, max_col=2)

    # "CARACT. TÉCNICAS" está na coluna 4, fora do limite max_col=2.
    assert header_row is None
    assert col_map == {config.COL_CODIGO_PMIB: 1}


def test_abrir_com_normalize_casa_cabecalho_sem_acento():
    # Planilha que perdeu os acentos numa exportação: o cabeçalho diz
    # "SITUACAO DA AUTORIZACAO" e a chave é "SITUAÇÃO DA AUTORIZAÇÃO".
    from sigft.services.autorizacao import normalizar

    grid = [
        ["CÓDIGO PMIB", "SITUACAO DA AUTORIZACAO"],
        ["4500063671.1000", ""],
    ]
    ws = _FakeWorksheet(grid)
    painel = StatusPMIB("c.xlsx")
    chaves = {config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB,
              config.COL_SITUACAO_AUTORIZACAO: config.COL_SITUACAO_AUTORIZACAO}

    sem, _ = painel.abrir(ws=ws, keywords=chaves, required=[config.COL_CODIGO_PMIB])
    com, _ = painel.abrir(ws=ws, keywords=chaves, required=[config.COL_CODIGO_PMIB], normalize=normalizar)

    assert config.COL_SITUACAO_AUTORIZACAO not in sem
    assert com[config.COL_SITUACAO_AUTORIZACAO] == 2


def test_abrir_sem_wb_nem_ws_importa_openpyxl_de_forma_preguicosa():
    """`abrir()` só toca `openpyxl` quando NÃO recebe `wb`/`ws` prontos --
    e só DENTRO do método (não no topo do módulo, nem no topo deste
    arquivo de teste, que já importou `StatusPMIB` sem erro no topo). Este
    ambiente de teste não tem o pacote openpyxl REAL instalado (só o stub
    `unittest.mock.MagicMock` que `tests/conftest.py` injeta em
    `sys.modules`) -- removendo o stub temporariamente, confirmamos que o
    `ModuleNotFoundError` só aparece ao CHAMAR `abrir()` sem `wb`/`ws`,
    nunca antes disso."""
    sentinela = object()
    anterior = sys.modules.pop("openpyxl", sentinela)
    try:
        painel = StatusPMIB("arquivo_que_nao_existe.xlsx")
        with pytest.raises(ModuleNotFoundError):
            painel.abrir()
    finally:
        if anterior is not sentinela:
            sys.modules["openpyxl"] = anterior


# ===========================================================================
# buscar_linha() — comparação via pmib_codes.normalize_pmib
# ===========================================================================

def test_buscar_linha_encontra_pmib_exato():
    _, ws = _painel_status_pmib_padrao()
    painel = StatusPMIB("c.xlsx")
    painel.abrir(ws=ws)

    assert painel.buscar_linha("4500063671.1234") == 4


def test_buscar_linha_normaliza_apostrofo_e_zeros_faltando():
    grid = [
        ["CÓDIGO PMIB"],
        ["'4500063671.123"],  # apóstrofo + falta 1 zero -> normaliza p/ .1230
    ]
    ws = _FakeWorksheet(grid)
    painel = StatusPMIB("c.xlsx")
    painel.abrir(ws=ws)

    assert painel.buscar_linha("4500063671.1230") == 2
    assert painel.buscar_linha("4500063671.123") == 2  # o alvo também é normalizado


def test_buscar_linha_normaliza_float_com_4f():
    grid = [["CÓDIGO PMIB"], [4500063671.1165]]
    ws = _FakeWorksheet(grid)
    painel = StatusPMIB("c.xlsx")
    painel.abrir(ws=ws)

    assert painel.buscar_linha("4500063671.1165") == 2


def test_buscar_linha_retorna_none_quando_nao_encontra():
    _, ws = _painel_status_pmib_padrao()
    painel = StatusPMIB("c.xlsx")
    painel.abrir(ws=ws)

    assert painel.buscar_linha("4500063671.9999") is None


def test_buscar_linha_pula_celulas_none_sem_quebrar():
    grid = [["CÓDIGO PMIB"], [None], ["4500063671.1234"]]
    ws = _FakeWorksheet(grid)
    painel = StatusPMIB("c.xlsx")
    painel.abrir(ws=ws)

    assert painel.buscar_linha("4500063671.1234") == 3


def test_buscar_linha_retorna_none_sem_coluna_pmib_resolvida():
    _, ws = _painel_status_pmib_padrao()
    painel = StatusPMIB("c.xlsx")
    painel.abrir(ws=ws, keywords={"CONDIÇÕES": "CONDIÇÕES"})  # sem CÓDIGO PMIB no col_map

    assert painel.buscar_linha("4500063671.1234") is None


def test_buscar_linha_aceita_col_pmib_e_header_row_explicitos_fallback():
    # Padrão de upload_conditions.atualizar_status_excel: quando a busca
    # dinâmica falha, usa colunas fixas (8/10) e header_row=1 -- sem
    # depender do que `abrir()` encontrou.
    grid = [[None] * 8, [None] * 7 + ["4500063671.5555"]]
    ws = _FakeWorksheet(grid)
    painel = StatusPMIB("c.xlsx")
    painel.abrir(ws=ws)  # não acha nada (não há "CÓDIGO PMIB" na grade)

    assert painel.header_row is None
    assert painel.buscar_linha("4500063671.5555", col_pmib=8, header_row=1) == 2


# ===========================================================================
# marcar_linha() — escrita em memória
# ===========================================================================

def test_marcar_linha_com_dict_marca_so_as_chaves_truthy():
    _, ws = _painel_status_pmib_padrao()
    painel = StatusPMIB("c.xlsx")
    painel.abrir(
        ws=ws,
        keywords={
            config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB,
            "CONDIÇÕES": "CONDIÇÕES",
            "INFO. GERAIS": "INFO. GERAIS",
        },
    )

    marcadas = painel.marcar_linha(3, {"CONDIÇÕES": True, "INFO. GERAIS": False})

    assert marcadas == ["CONDIÇÕES"]
    assert ws.cell(row=3, column=3).value == VALOR_COMPLETO  # CONDIÇÕES
    assert ws.cell(row=3, column=5).value == ""  # INFO. GERAIS não tocada


def test_marcar_linha_com_iteravel_marca_todas():
    _, ws = _painel_status_pmib_padrao()
    painel = StatusPMIB("c.xlsx")
    painel.abrir(
        ws=ws,
        keywords={
            config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB,
            "CONDIÇÕES": "CONDIÇÕES",
            "CARACT. TÉCNICAS": "CARACT. TÉCNICAS",
        },
    )

    marcadas = painel.marcar_linha(3, ["CONDIÇÕES", "CARACT. TÉCNICAS"])

    assert set(marcadas) == {"CONDIÇÕES", "CARACT. TÉCNICAS"}
    assert ws.cell(row=3, column=3).value == VALOR_COMPLETO
    assert ws.cell(row=3, column=4).value == VALOR_COMPLETO


def test_marcar_linha_ignora_secao_sem_coluna_resolvida():
    _, ws = _painel_status_pmib_padrao()
    painel = StatusPMIB("c.xlsx")
    painel.abrir(ws=ws, keywords={config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB})

    marcadas = painel.marcar_linha(3, ["CONDIÇÕES"])  # não está em col_map

    assert marcadas == []


def test_marcar_linha_aceita_valor_customizado():
    _, ws = _painel_status_pmib_padrao()
    painel = StatusPMIB("c.xlsx")
    painel.abrir(ws=ws, keywords={"CONDIÇÕES": "CONDIÇÕES"})

    painel.marcar_linha(3, ["CONDIÇÕES"], valor="PENDENTE")

    assert ws.cell(row=3, column=3).value == "PENDENTE"


def test_marcar_linha_procura_por_upper_quando_chave_nao_bate_exata():
    # Padrão de AtualizadorStatusPMIB: `secoes_concluidas` pode vir com
    # grafia livre; a chave de col_map é sempre .upper().
    _, ws = _painel_status_pmib_padrao()
    painel = StatusPMIB("c.xlsx")
    painel.abrir(ws=ws, keywords={"CONDIÇÕES": "CONDIÇÕES"})

    marcadas = painel.marcar_linha(3, {"condições": True})

    assert marcadas == ["condições"]
    assert ws.cell(row=3, column=3).value == VALOR_COMPLETO


# ===========================================================================
# salvar() / fechar() — editor cirúrgico + locking.save_with_retry
# ===========================================================================
# T1 do roteiro do Gestão PMIB v2 (2026-10-05): o `salvar()` não chama mais
# `wb.save` -- o openpyxl apagava os comentários em thread do `_STATUS_PMIB`.
# As escritas são anotadas e gravadas pelo editor cirúrgico; aqui ele é o
# `_GravadorFalso`, e `tests/test_status_pmib_gravacao_real.py` prova o
# caminho com o arquivo de verdade.

def _painel_com_gravador(falhas=0, caminho="caminho/real.xlsx"):
    wb, ws = _painel_status_pmib_padrao()
    gravador = _GravadorFalso(falhas_antes_do_sucesso=falhas)
    painel = StatusPMIB(caminho, gravar=gravador)
    painel.abrir(wb=wb, ws=ws, keywords={
        config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB, "CONDIÇÕES": "CONDIÇÕES"})
    return painel, wb, ws, gravador


def test_salvar_grava_pelo_editor_com_retry_e_repassa_kwargs():
    painel, wb, _ws, gravador = _painel_com_gravador(falhas=2)
    painel.marcar_linha(4, [config.COL_CONDICOES])

    tentativas = []
    resultado = painel.salvar(on_locked=lambda a, e: tentativas.append(a) or True)

    assert resultado is True
    assert tentativas == [1, 2]
    # Cada tentativa chama o gravador de novo -- é ele quem RELÊ o arquivo.
    assert gravador.chamadas == ["caminho/real.xlsx"] * 3
    assert gravador.gravados == [{
        "caminho": "caminho/real.xlsx", "aba": config.ABA_LISTA_MATERIAIS,
        "escritas": {(4, 3): VALOR_COMPLETO}, "nomes": {}, "formato_geral": set(),
    }]


def test_salvar_nunca_chama_o_wb_save_do_openpyxl():
    # É o que apagava os comentários em thread: o openpyxl regrava o arquivo
    # inteiro com o que entende.
    painel, wb, _ws, _gravador = _painel_com_gravador()
    painel.marcar_linha(4, [config.COL_CONDICOES])

    painel.salvar()

    assert wb.chamadas_save == 0


def test_salvar_sem_nada_anotado_nao_toca_no_arquivo():
    painel, _wb, _ws, gravador = _painel_com_gravador()

    assert painel.salvar() is True
    assert gravador.chamadas == []


def test_salvar_limpa_o_que_gravou():
    painel, _wb, _ws, gravador = _painel_com_gravador()
    painel.marcar_linha(4, [config.COL_CONDICOES])
    painel.salvar()

    painel.salvar()  # nada novo: não grava de novo

    assert len(gravador.chamadas) == 1
    assert painel.escritas_pendentes == {}


def test_salvar_propaga_permission_error_quando_on_locked_aborta():
    painel, _wb, _ws, _gravador = _painel_com_gravador(falhas=5, caminho="c.xlsx")
    painel.marcar_linha(4, [config.COL_CONDICOES])

    with pytest.raises(PermissionError):
        painel.salvar(max_attempts=1)


def test_desistencia_mantem_o_que_estava_anotado():
    # Quem chama pode tentar de novo mais tarde (a pessoa fechou o Excel).
    painel, _wb, _ws, _gravador = _painel_com_gravador(falhas=1)
    painel.marcar_linha(4, [config.COL_CONDICOES])

    with pytest.raises(PermissionError):
        painel.salvar(max_attempts=1)

    assert painel.escritas_pendentes == {(4, 3): VALOR_COMPLETO}


def test_escrever_muda_a_celula_em_memoria_e_anota():
    painel, _wb, ws, _gravador = _painel_com_gravador()

    painel.escrever(5, 2, "Item 3 revisto")

    assert ws.cell(row=5, column=2).value == "Item 3 revisto"  # a leitura seguinte vê
    assert painel.escritas_pendentes == {(5, 2): "Item 3 revisto"}


def test_a_mesma_celula_escrita_duas_vezes_grava_o_ultimo_valor():
    painel, _wb, _ws, gravador = _painel_com_gravador()

    painel.escrever(4, 3, "INCOMPLETO")
    painel.escrever(4, 3, VALOR_COMPLETO)
    painel.salvar()

    assert gravador.gravados[0]["escritas"] == {(4, 3): VALOR_COMPLETO}


def test_formato_geral_e_nome_definido_vao_para_o_gravador():
    painel, _wb, _ws, gravador = _painel_com_gravador()

    painel.escrever(4, 5, 4, formato_geral=True)
    painel.definir_nome("sigft_calculado_em", '"2026-10-10"')
    painel.salvar()

    assert gravador.gravados[0]["formato_geral"] == {(4, 5)}
    assert gravador.gravados[0]["nomes"] == {"sigft_calculado_em": '"2026-10-10"'}


def test_so_um_nome_definido_tambem_e_gravado():
    painel, _wb, _ws, gravador = _painel_com_gravador()

    painel.definir_nome("sigft_calculado_em", '"2026-10-10"')
    painel.salvar()

    assert gravador.gravados[0]["escritas"] == {}


def test_salvar_usa_o_nome_real_da_aba_aberta():
    # Quem chama pode ter aberto outra aba (o Cria Fichas cai na aba ativa
    # quando a "Lista de Materiais" não existe): grava-se na que foi LIDA.
    wb, ws = _painel_status_pmib_padrao()
    ws.title = "Lista de materiais"
    gravador = _GravadorFalso()
    painel = StatusPMIB("c.xlsx", gravar=gravador)
    painel.abrir(wb=wb, ws=ws)

    painel.escrever(4, 3, VALOR_COMPLETO)
    painel.salvar()

    assert gravador.gravados[0]["aba"] == "Lista de materiais"


def test_fechar_chama_close_do_wb():
    wb, ws = _painel_status_pmib_padrao()
    painel = StatusPMIB("c.xlsx")
    painel.abrir(wb=wb, ws=ws)

    painel.fechar()

    assert wb.closed is True


def test_fechar_e_no_op_silencioso_sem_wb():
    painel = StatusPMIB("c.xlsx")
    _, ws = _painel_status_pmib_padrao()
    painel.abrir(ws=ws)  # sem wb

    painel.fechar()  # não deve levantar


# ===========================================================================
# marcar_completo() — fluxo de conveniência ponta a ponta
# ===========================================================================

def test_marcar_completo_encontra_marca_salva_e_fecha():
    painel, wb, ws, gravador = _painel_com_gravador(caminho="c.xlsx")

    resultado = painel.marcar_completo("4500063671.1234", [config.COL_CONDICOES])

    assert resultado is True
    assert ws.cell(row=4, column=3).value == VALOR_COMPLETO
    assert gravador.gravados[0]["escritas"] == {(4, 3): VALOR_COMPLETO}
    assert wb.chamadas_save == 0
    assert wb.closed is True


def test_marcar_completo_pmib_nao_encontrado_retorna_false_sem_salvar():
    painel, wb, _ws, gravador = _painel_com_gravador(caminho="c.xlsx")

    resultado = painel.marcar_completo("4500063671.0000", [config.COL_CONDICOES])

    assert resultado is False
    assert gravador.chamadas == []
    assert wb.closed is True  # fechar() ainda acontece


def test_marcar_completo_salvar_false_nao_grava():
    painel, wb, ws, gravador = _painel_com_gravador(caminho="c.xlsx")

    resultado = painel.marcar_completo("4500063671.1234", [config.COL_CONDICOES], salvar=False)

    assert resultado is True
    assert ws.cell(row=4, column=3).value == VALOR_COMPLETO  # marcado em memória
    assert gravador.chamadas == []  # mas não gravado
    assert painel.escritas_pendentes == {(4, 3): VALOR_COMPLETO}
    assert wb.closed is True


def test_marcar_completo_fechar_false_mantem_wb_aberto():
    painel, wb, _ws, _gravador = _painel_com_gravador(caminho="c.xlsx")

    painel.marcar_completo("4500063671.1234", [config.COL_CONDICOES], fechar=False)

    assert wb.closed is False


def test_marcar_completo_abre_sozinho_quando_ainda_nao_foi_aberto(monkeypatch):
    # NÃO chama painel.abrir() manualmente antes -- marcar_completo() deve
    # abrir sozinho (defaults: busca só a coluna-âncora). Testa a fiação
    # REAL de `abrir()` sem wb/ws, monkeypatchando só `openpyxl.load_workbook`
    # (o stub de `openpyxl` que tests/conftest.py injeta em `sys.modules`).
    wb, ws = _painel_status_pmib_padrao()
    chamadas = []

    def _fake_load_workbook(caminho, **kwargs):
        chamadas.append((caminho, kwargs))
        return wb

    monkeypatch.setattr(sys.modules["openpyxl"], "load_workbook", _fake_load_workbook)

    gravador = _GravadorFalso()
    painel = StatusPMIB("c.xlsx", gravar=gravador)
    resultado = painel.marcar_completo("4500063671.1000", [config.COL_CODIGO_PMIB])

    assert resultado is True
    assert chamadas == [("c.xlsx", {})]
    assert painel.wb is wb
    assert painel.ws is ws
    assert gravador.gravados[0]["escritas"] == {(3, 1): VALOR_COMPLETO}


def test_marcar_completo_fecha_mesmo_quando_salvar_levanta_permission_error():
    painel, wb, _ws, _gravador = _painel_com_gravador(falhas=99, caminho="c.xlsx")

    with pytest.raises(PermissionError):
        painel.marcar_completo("4500063671.1234", [config.COL_CONDICOES], max_attempts=1)

    assert wb.closed is True  # finally garantiu o fechar() mesmo com exceção
