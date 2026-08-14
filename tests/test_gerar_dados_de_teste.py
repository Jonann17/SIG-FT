r"""
Testes do gerador de dados sintéticos (`scripts/gerar_dados_de_teste.py`).

O gerador existe para exercitar o app sem ter ficha real em mãos. O risco dele
é silencioso: gerar arquivos que ABREM no Excel mas que o código de produção
não consegue ler — aí o usuário testa, vê erro, e não sabe se o defeito é do
módulo ou do arquivo falso. Estes testes fecham essa porta verificando que os
arquivos gerados são consumidos pelos LEITORES DE PRODUÇÃO, não por leitores
escritos aqui.

Precisam do `openpyxl` REAL (o `tests/conftest.py` o stuba com `MagicMock`), e
`pandas` real para os leitores que o usam. Quando faltar qualquer um dos dois,
os testes se marcam como `skip` em vez de falhar — este arquivo não pode
derrubar a suíte num ambiente que roda sem as dependências pesadas, que é
justamente o ambiente onde o resto dos testes vive.
"""
from __future__ import annotations

import importlib
import os
import sys
from contextlib import contextmanager

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@contextmanager
def _pacote_real(nome):
    """Coloca o pacote REAL em `sys.modules` durante o bloco e devolve os stubs
    depois -- exatamente os que estavam antes.

    O cuidado com a restauração não é zelo excessivo: no CP 4.3 um probe que
    trocava o stub do `openpyxl` deixou submódulos reais vazados em
    `sys.modules` e quebrou `test_status_sheet.py` só quando a suíte inteira
    rodava (passava sozinho). Por isso a limpeza remove TUDO o que o import
    real tiver deixado, e não apenas o pacote de topo.

    Devolve `None` quando o pacote não está instalado -- cabe a quem chama
    decidir pular o teste.
    """
    antes = {k: v for k, v in sys.modules.items() if k == nome or k.startswith(nome + ".")}
    for chave in antes:
        del sys.modules[chave]
    try:
        modulo = importlib.import_module(nome)
    except ImportError:
        sys.modules.update(antes)
        yield None
        return
    try:
        yield modulo
    finally:
        for chave in [k for k in list(sys.modules) if k == nome or k.startswith(nome + ".")]:
            del sys.modules[chave]
        sys.modules.update(antes)


@pytest.fixture
def openpyxl_real():
    with _pacote_real("openpyxl") as modulo:
        if modulo is None:
            pytest.skip("openpyxl real não instalado neste ambiente")
        yield modulo


@pytest.fixture
def pandas_real(monkeypatch):
    """Além de colocar o pandas real em `sys.modules`, aponta o `pd` DE DENTRO
    dos serviços para ele: `services/search.py` e `services/lmr.py` fazem
    `import pandas as pd` no topo, então já carregaram o stub quando este
    módulo de teste foi importado -- trocar só o `sys.modules` não os
    alcançaria, e eles "leriam" a planilha devolvendo MagicMocks."""
    with _pacote_real("pandas") as modulo:
        if modulo is None:
            pytest.skip("pandas real não instalado neste ambiente")
        for nome_servico in ("sigft.services.search", "sigft.services.lmr"):
            servico = sys.modules.get(nome_servico)
            if servico is not None:
                monkeypatch.setattr(servico, "pd", modulo)
        yield modulo


@pytest.fixture(scope="module")
def gerador():
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
    try:
        return importlib.import_module("gerar_dados_de_teste")
    finally:
        sys.path.pop(0)


@pytest.fixture
def gerados(tmp_path, gerador, openpyxl_real, monkeypatch):
    """Gera os arquivos COM o openpyxl real em vigor -- com o stub, `wb.save()`
    seria uma chamada de MagicMock e nenhum arquivo apareceria no disco."""
    monkeypatch.setattr(sys, "argv", ["gerar_dados_de_teste.py", str(tmp_path)])
    assert gerador.main() == 0
    return tmp_path


# ===========================================================================
# Os arquivos existem e têm a cara certa
# ===========================================================================
def test_gera_os_cinco_arquivos(gerados):
    from sigft import config

    for numero in (1, 2):
        pmib = f"{config.PREFIXO_CONTRATO}.{numero:04d}"
        assert (gerados / f"{pmib}_STATUS_PMIB.xlsx").is_file()
        assert (gerados / "fichas" / f"{pmib}.xlsx").is_file()
    assert (gerados / "LMR_aplicacoes.xlsx").is_file()


def test_nome_do_status_segue_a_convencao_que_o_search_procura(gerados):
    # `search.executar_busca` varre a pasta por "STATUS_PMIB" no nome, e
    # `_extrair_codigo_itaipu` corta no "_STATUS_PMIB" -- se o gerador mudar a
    # convenção de nome, o módulo simplesmente não acha os arquivos.
    from sigft.services.search import PMIBSearcher

    arquivos = [p.name for p in gerados.glob("*.xlsx")]
    status = [n for n in arquivos if "STATUS_PMIB" in n.upper()]
    assert len(status) == 2

    codigo = PMIBSearcher()._extrair_codigo_itaipu(status[0])
    assert codigo.startswith("4500063671.")


# ===========================================================================
# Os leitores DE PRODUÇÃO conseguem ler
# ===========================================================================
def test_status_pmib_e_lido_pelo_statuspmib_de_producao(gerados):
    from sigft import config
    from sigft.core.excel.status_sheet import StatusPMIB

    caminho = gerados / f"{config.PREFIXO_CONTRATO}.0001_STATUS_PMIB.xlsx"
    status = StatusPMIB(str(caminho))
    status.abrir()
    try:
        # O cabeçalho tem de cair na linha que `config.LINHA_STATUS_PMIB`
        # define, senão `headers.find_columns` não acha coluna nenhuma.
        linha = status.buscar_linha("100100")
        assert linha == config.LINHA_STATUS_PMIB + 1
    finally:
        status.fechar()


def test_marcar_completo_funciona_sobre_o_arquivo_gerado(gerados):
    from sigft import config
    from sigft.core.excel.status_sheet import StatusPMIB

    caminho = gerados / f"{config.PREFIXO_CONTRATO}.0001_STATUS_PMIB.xlsx"
    status = StatusPMIB(str(caminho))
    status.abrir()
    try:
        # Se as colunas de seção não existissem com o nome exato de
        # `config.COL_*`, isto não teria onde escrever.
        status.marcar_completo("100104", [config.COL_CONDICOES])
    finally:
        status.fechar()


def test_search_monta_o_dataframe_do_arquivo_gerado(gerados, pandas_real):
    from sigft import config
    from sigft.services.search import PMIBSearcher

    caminho = gerados / f"{config.PREFIXO_CONTRATO}.0001_STATUS_PMIB.xlsx"
    df, msg = PMIBSearcher()._encontrar_e_formatar_dataframe(str(caminho))

    assert df is not None, msg
    assert len(df) == 6
    assert config.COL_CODIGO_PMIB in df.columns


def test_lmr_carrega_a_planilha_gerada_e_agrupa_tags(gerados, pandas_real):
    from sigft.services.lmr import LMRAutomation

    ok, df, pmibs, msg = LMRAutomation().carregar_dados_excel(str(gerados / "LMR_aplicacoes.xlsx"), "LMR")

    assert ok, msg
    assert len(pmibs) == 2
    # O 1º código de cada ficha tem 2 TAGs de propósito: é o que exercita o
    # agrupamento de TAGs consecutivas de `_processar_ficha_lmr_interna`.
    assert len(df[df["Código_PMIB"] == "100100"]) == 2


# ===========================================================================
# A ficha respeita o layout que o código lê
# ===========================================================================
def test_ficha_tem_valor_nas_celulas_que_o_config_map_define(gerados, openpyxl_real):
    from sigft import config
    from sigft.core.rpa import ficha_layout

    caminho = gerados / "fichas" / f"{config.PREFIXO_CONTRATO}.0001.xlsx"
    ws = openpyxl_real.load_workbook(str(caminho)).active

    for chave in ("texto_breve_material", "unidade", "fabricante"):
        referencia = ficha_layout.CONFIG_MAP[chave]["range"].split(":")[0]
        assert ws[referencia].value, f"{chave} vazio em {referencia}"


def test_ficha_marca_uma_opcao_de_cada_checkbox(gerados, openpyxl_real):
    from sigft import config
    from sigft.core.rpa import ficha_layout

    caminho = gerados / "fichas" / f"{config.PREFIXO_CONTRATO}.0001.xlsx"
    ws = openpyxl_real.load_workbook(str(caminho)).active

    for chave, spec in ficha_layout.CONFIG_MAP.items():
        if spec.get("type") != "checkbox":
            continue
        marcadas = [c for c in spec["cells"] if ws[c].value]
        assert len(marcadas) == 1, f"{chave}: esperado 1 marcada, veio {marcadas}"


def test_ficha_tem_specs_a_partir_da_linha_que_o_config_define(gerados, openpyxl_real):
    from sigft import config
    from sigft.core.rpa import ficha_layout

    caminho = gerados / "fichas" / f"{config.PREFIXO_CONTRATO}.0001.xlsx"
    ws = openpyxl_real.load_workbook(str(caminho)).active
    specs = ficha_layout.VARIAVEIS_SPECS

    assert specs["start_row"] == config.LINHA_SPECS_FICHA
    pergunta = ws.cell(row=specs["start_row"], column=specs["pergunta_col_idx"]).value
    resposta = ws.cell(row=specs["start_row"], column=specs["resposta_col_idx"]).value
    assert pergunta and resposta


def test_gerador_e_deterministico(tmp_path, gerador, openpyxl_real, pandas_real, monkeypatch):
    # `random.seed(42)` fixo: comparar duas execuções (antes/depois de uma
    # mudança) só é útil se a entrada for idêntica.
    saidas = []
    for nome in ("a", "b"):
        destino = tmp_path / nome
        monkeypatch.setattr(sys, "argv", ["gerar_dados_de_teste.py", str(destino)])
        gerador.main()
        saidas.append((destino / "LMR_aplicacoes.xlsx").read_bytes())

    # O .xlsx é um ZIP com timestamp, então os bytes brutos divergem; o que
    # tem de bater é o CONTEÚDO.
    from sigft.services.lmr import LMRAutomation

    _, df_a, _, _ = LMRAutomation().carregar_dados_excel(str(tmp_path / "a" / "LMR_aplicacoes.xlsx"), "LMR")
    _, df_b, _, _ = LMRAutomation().carregar_dados_excel(str(tmp_path / "b" / "LMR_aplicacoes.xlsx"), "LMR")
    assert list(df_a["TAG_PMIB"]) == list(df_b["TAG_PMIB"])
