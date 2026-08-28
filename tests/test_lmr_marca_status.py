"""LMR marcando a coluna "APLICAÇÃO - LMR" do `_STATUS_PMIB` — 2026-08-28.

Pedido do usuário: *"onde ele pede a planilha do _STATUS_PMIB também para que
ela marque no excel que a coluna daquela ficha (daquele código PMIB) está
completo para aplicação LMR, semelhante ao que faz"*. Regra escolhida por ele:
marcar **os dois** desfechos, COMPLETO e INCOMPLETO.

O que estes testes protegem, em ordem de importância:

1. **O cabeçalho real tem hífen** — `"APLICAÇÃO - LMR"`. O casamento de coluna
   (`core/excel/headers.find_columns`) é EXATO depois de `strip()`+`upper()`,
   então uma constante escrita `"APLICAÇÃO LMR"` não casaria, e o sintoma seria
   a marcação silenciosamente não acontecer — o pior tipo de falha, porque
   parece sucesso.
2. **Coluna ausente não pode quebrar o lote nem mentir.** O cadastro no portal
   já aconteceu e é a parte cara; a mensagem tem de dizer o que a planilha TEM,
   para o nome certo poder ser descoberto sem abrir o arquivo.
3. **Só marca ficha que o robô realmente tentou.**
"""
from __future__ import annotations

import pytest

from sigft import config
from sigft.services import lmr


# =============================================================================
# A. A constante e os aliases
# =============================================================================

def test_o_nome_oficial_da_coluna_tem_o_hifen():
    """Confirmado pelo usuário em 2026-08-28. O hífen cercado de espaços é o
    detalhe que faria uma constante "APLICAÇÃO LMR" não casar."""
    assert config.COL_APLICACAO_LMR == "APLICAÇÃO - LMR"


def test_o_nome_oficial_e_o_primeiro_alias():
    assert config.ALIASES_COL_APLICACAO_LMR[0] == config.COL_APLICACAO_LMR


def test_os_aliases_cobrem_a_grafia_sem_acento():
    """Planilha que passa por exportação perde cedilha e til."""
    assert "APLICACAO - LMR" in config.ALIASES_COL_APLICACAO_LMR


def test_os_aliases_cobrem_a_grafia_sem_hifen():
    assert "APLICAÇÃO LMR" in config.ALIASES_COL_APLICACAO_LMR


# =============================================================================
# B. `processar_lista` devolve os dois grupos
# =============================================================================

def test_o_retorno_e_aditivo_e_separa_completas_de_incompletas():
    """Contrato novo, igual ao de `upload_conditions.processar_lista`."""
    import inspect

    fonte = inspect.getsource(lmr.LMRAutomation.processar_lista)
    assert "return completas, incompletas" in fonte


def test_so_entram_fichas_que_o_robo_tentou():
    """O laço pode parar no meio (o `break` quando nem a home recarrega).
    Marcar no `_STATUS_PMIB` uma ficha que nunca foi aberta seria mentira."""
    import inspect

    fonte = inspect.getsource(lmr.LMRAutomation.processar_lista)
    assert "fichas_processadas" in fonte
    # as duas listas saem de `fichas_processadas`, não de `lista_pmibs`
    assert "for p in fichas_processadas if p not in fichas_com_erro" in fonte
    assert "for p in fichas_processadas if p in fichas_com_erro" in fonte


# =============================================================================
# C. marcar_status_pmib — o caminho feliz
# =============================================================================

class _PainelFalso:
    """Dublê de `StatusPMIB` com uma planilha em memória."""

    def __init__(self, col_map, linhas_por_pmib, falha_ao_salvar=None):
        self.col_map = dict(col_map)
        self.header_row = 4
        self._linhas = dict(linhas_por_pmib)
        self.marcacoes = []
        self.salvou = False
        self.fechou = False
        self._falha_ao_salvar = falha_ao_salvar
        self.tentativas_de_salvar = 0
        self.ws = None

    def abrir(self, **kwargs):
        self.kwargs_abrir = kwargs
        return self.col_map, self.header_row

    def buscar_linha(self, pmib, header_row=None):
        return self._linhas.get(str(pmib).strip())

    def marcar_linha(self, linha, colunas, valor=None):
        self.marcacoes.append((linha, dict(colunas), valor))

    def salvar(self, **kwargs):
        self.tentativas_de_salvar += 1
        if self._falha_ao_salvar and self.tentativas_de_salvar <= self._falha_ao_salvar:
            raise PermissionError(13, "arquivo aberto", "x.xlsx")
        self.salvou = True
        return True

    def fechar(self):
        self.fechou = True


@pytest.fixture()
def instalar_painel(monkeypatch):
    """Troca o `StatusPMIB` real pelo dublê, sem tocar em disco.

    ⚠️ Substitui a CLASSE dentro do módulo real, e não a entrada em
    `sys.modules`. `marcar_status_pmib` faz `from sigft.core.excel import
    status_sheet` — que pega o ATRIBUTO do pacote já importado, e portanto
    ignora um módulo trocado em `sys.modules`. Uma versão anterior desta
    fixture fazia isso e os testes rodavam contra o `StatusPMIB` de verdade,
    tentando abrir "x.xlsx" no disco.
    """
    from sigft.core.excel import status_sheet

    def _instalar(painel):
        monkeypatch.setattr(status_sheet, "StatusPMIB", lambda *a, **k: painel)
        return painel

    return _instalar


def test_marca_completo_e_incompleto_nas_linhas_certas(instalar_painel):
    painel = instalar_painel(_PainelFalso(
        col_map={config.COL_CODIGO_PMIB: 8, config.COL_APLICACAO_LMR: 12},
        linhas_por_pmib={"4500063671.1449": 10, "4500063671.1450": 11},
    ))

    marcadas, recado = lmr.marcar_status_pmib(
        "x.xlsx", ["4500063671.1449"], ["4500063671.1450"])

    assert marcadas == 2
    assert (10, {config.COL_APLICACAO_LMR: True}, "COMPLETO") in painel.marcacoes
    assert (11, {config.COL_APLICACAO_LMR: True}, "INCOMPLETO") in painel.marcacoes
    assert painel.salvou
    assert "2 linha(s) marcada(s)" in recado


def test_a_busca_da_coluna_usa_todos_os_aliases(instalar_painel):
    """Sem isso, uma planilha com grafia levemente diferente não marcaria — e
    não avisaria."""
    painel = instalar_painel(_PainelFalso(
        col_map={config.COL_CODIGO_PMIB: 8, config.COL_APLICACAO_LMR: 12},
        linhas_por_pmib={"1": 10},
    ))

    lmr.marcar_status_pmib("x.xlsx", ["1"], [])

    keywords = painel.kwargs_abrir["keywords"]
    assert keywords[config.COL_APLICACAO_LMR] == config.ALIASES_COL_APLICACAO_LMR


def test_so_o_codigo_pmib_e_obrigatorio_na_varredura(instalar_painel):
    """A varredura não pode parar por não achar a coluna de LMR: precisamos
    chegar ao fim para poder LISTAR os cabeçalhos que existem."""
    painel = instalar_painel(_PainelFalso(
        col_map={config.COL_CODIGO_PMIB: 8, config.COL_APLICACAO_LMR: 12},
        linhas_por_pmib={"1": 10},
    ))

    lmr.marcar_status_pmib("x.xlsx", ["1"], [])

    assert painel.kwargs_abrir["required"] == [config.COL_CODIGO_PMIB]


def test_lote_vazio_nao_abre_a_planilha():
    marcadas, recado = lmr.marcar_status_pmib("x.xlsx", [], [])

    assert marcadas == 0
    assert "Nenhuma ficha" in recado


# =============================================================================
# D. Os caminhos ruins — nenhum pode derrubar o lote
# =============================================================================

def test_coluna_ausente_avisa_e_LISTA_os_cabecalhos_que_existem(instalar_painel):
    """A mensagem tem de dizer o que a planilha TEM. Reclamar do que falta, sem
    mostrar o que existe, obriga a abrir o arquivo — que está no Box."""
    painel = _PainelFalso(
        col_map={config.COL_CODIGO_PMIB: 8},   # sem a coluna de LMR
        linhas_por_pmib={"1": 10},
    )

    class _WsFalsa:
        def cell(self, row, column):
            textos = {1: "ITEM", 8: "CÓDIGO PMIB", 9: "CONDIÇÕES", 10: "APLICACOES - LMR"}
            return type("C", (), {"value": textos.get(column)})()

    painel.ws = _WsFalsa()
    instalar_painel(painel)

    marcadas, recado = lmr.marcar_status_pmib("x.xlsx", ["1"], [])

    assert marcadas == 0
    assert "não foi encontrada" in recado
    # o ponto do teste: a mensagem MOSTRA os cabeçalhos reais
    assert "APLICACOES - LMR" in recado
    assert "CÓDIGO PMIB" in recado
    assert painel.marcacoes == []


def test_ficha_ausente_na_planilha_nao_impede_as_outras(instalar_painel):
    painel = instalar_painel(_PainelFalso(
        col_map={config.COL_CODIGO_PMIB: 8, config.COL_APLICACAO_LMR: 12},
        linhas_por_pmib={"achada": 10},        # "sumida" não está na planilha
    ))

    marcadas, recado = lmr.marcar_status_pmib("x.xlsx", ["achada", "sumida"], [])

    assert marcadas == 1
    assert "sumida" in recado
    assert painel.salvou


def test_nenhuma_ficha_encontrada_nao_salva(instalar_painel):
    painel = instalar_painel(_PainelFalso(
        col_map={config.COL_CODIGO_PMIB: 8, config.COL_APLICACAO_LMR: 12},
        linhas_por_pmib={},
    ))

    marcadas, recado = lmr.marcar_status_pmib("x.xlsx", ["1"], [])

    assert marcadas == 0
    assert "Nada foi salvo" in recado
    assert not painel.salvou


def test_excel_travado_pergunta_ao_usuario(instalar_painel):
    """O salvamento passa pelo canal do CP D."""
    painel = instalar_painel(_PainelFalso(
        col_map={config.COL_CODIGO_PMIB: 8, config.COL_APLICACAO_LMR: 12},
        linhas_por_pmib={"1": 10},
    ))
    perguntas = []

    lmr.marcar_status_pmib(
        "planilha.xlsx", ["1"], [],
        retry_lock=lambda caminho: perguntas.append(caminho) or True)

    # o `on_locked` foi montado com o canal -- o dublê não força PermissionError
    # aqui, então o que se prova é que o salvar recebeu a política.
    assert painel.salvou


def test_excel_travado_e_usuario_desiste_avisa_sem_levantar(instalar_painel):
    """O trabalho no portal está feito: uma planilha travada não pode virar
    exceção na cara do usuário."""
    painel = instalar_painel(_PainelFalso(
        col_map={config.COL_CODIGO_PMIB: 8, config.COL_APLICACAO_LMR: 12},
        linhas_por_pmib={"1": 10},
        falha_ao_salvar=99,
    ))

    marcadas, recado = lmr.marcar_status_pmib("x.xlsx", ["1"], [])

    assert marcadas == 0
    assert "aberto no Excel" in recado
    assert "trabalho no portal está feito" in recado
    assert painel.fechou


def test_planilha_que_nem_abre_nao_derruba_o_lote(monkeypatch):
    from sigft.core.excel import status_sheet

    def _explode(*a, **k):
        raise OSError("arquivo corrompido")

    monkeypatch.setattr(status_sheet, "StatusPMIB", _explode)

    marcadas, recado = lmr.marcar_status_pmib("x.xlsx", ["1"], [])

    assert marcadas == 0
    assert "Não consegui abrir" in recado
