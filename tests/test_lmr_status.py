"""`services/lmr_status.py` — a coluna "APLICAÇÃO - LMR", nos dois sentidos.

Os dois módulos de LMR escrevem na MESMA coluna em sentidos opostos: a
aplicação marca `COMPLETO`/`INCOMPLETO`, a exclusão LIMPA. O que estes testes
protegem:

1. **A exclusão escreve vazio, não "INCOMPLETO".** Foi a decisão do usuário, e
   ela tem razão de ser: uma ficha cujas aplicações foram apagadas não está
   incompleta — está por fazer, igual a uma que nunca foi tocada.
2. **Falha de planilha nunca levanta.** O trabalho no portal é caro e não
   repetível; um erro de Excel não pode derrubar o resultado dele.
3. **O alias do cabeçalho funciona.** O nome real é "APLICAÇÃO - LMR", com
   hífen cercado de espaços — e o casamento é EXATO depois de strip+upper, então
   uma variação de acento faria a marcação sumir em silêncio.
"""
from __future__ import annotations

import pytest

from sigft import config
from sigft.services import lmr_status


class PainelFalso:
    """Dublê de `StatusPMIB` — registra o que seria escrito na planilha."""

    def __init__(self, *, colunas=None, linhas_por_pmib=None, erro_ao_salvar=None):
        self._colunas = (
            colunas
            if colunas is not None
            else {config.COL_CODIGO_PMIB: 1, config.COL_APLICACAO_LMR: 7}
        )
        self._linhas = linhas_por_pmib if linhas_por_pmib is not None else {}
        self._erro_ao_salvar = erro_ao_salvar
        self.col_map = {}
        self.header_row = 4
        self.escritas = []
        self.salvou = False
        self.fechou = False
        self.ws = None

    def abrir(self, **_kwargs):
        self.col_map = dict(self._colunas)
        return self.col_map, self.header_row

    def buscar_linha(self, pmib, header_row=None):
        return self._linhas.get(str(pmib))

    def marcar_linha(self, linha, colunas, valor=None):
        self.escritas.append((linha, valor))

    def salvar(self, on_locked=None):
        if self._erro_ao_salvar is not None:
            erro = self._erro_ao_salvar
            self._erro_ao_salvar = None  # a 2ª tentativa passa
            if on_locked is not None and on_locked(1, erro):
                self.salvou = True
                return
            raise erro
        self.salvou = True

    def fechar(self):
        self.fechou = True


@pytest.fixture()
def instalar_painel(monkeypatch):
    """Troca o `StatusPMIB` real pelo dublê, sem tocar em Excel nenhum."""

    def _instalar(painel):
        import sigft.core.excel.status_sheet as modulo

        monkeypatch.setattr(modulo, "StatusPMIB", lambda *a, **k: painel)
        return painel

    return _instalar


# =============================================================================
# A. Os dois sentidos
# =============================================================================

def test_aplicacao_marca_completo_e_incompleto(instalar_painel):
    painel = instalar_painel(
        PainelFalso(linhas_por_pmib={"4500.0001": 10, "4500.0002": 11})
    )

    n, recado = lmr_status.marcar_aplicacao(
        "/x/status.xlsx", ["4500.0001"], ["4500.0002"]
    )

    assert n == 2
    assert painel.escritas == [(10, "COMPLETO"), (11, "INCOMPLETO")]
    assert painel.salvou
    assert "2 linha(s)" in recado


def test_exclusao_escreve_VAZIO_e_nao_incompleto(instalar_painel):
    """A decisão do usuário: apagou com sucesso -> a célula fica em branco.

    Escrever "INCOMPLETO" seria diferente: diria que alguém tentou e falhou,
    quando na verdade a ficha voltou a estar por fazer.
    """
    painel = instalar_painel(PainelFalso(linhas_por_pmib={"4500.0001": 10}))

    n, _ = lmr_status.limpar_aplicacao("/x/status.xlsx", ["4500.0001"])

    assert n == 1
    assert painel.escritas == [(10, "")]


def test_o_valor_de_limpar_e_string_vazia():
    assert lmr_status.LIMPAR == ""
    assert lmr_status.COMPLETO == "COMPLETO"
    assert lmr_status.INCOMPLETO == "INCOMPLETO"


def test_lista_vazia_nao_abre_a_planilha(instalar_painel):
    painel = instalar_painel(PainelFalso())

    n, recado = lmr_status.limpar_aplicacao("/x/status.xlsx", [])

    assert n == 0
    assert not painel.salvou
    assert "Nenhuma ficha" in recado


# =============================================================================
# B. A coluna não encontrada — a mensagem precisa AJUDAR
# =============================================================================

def test_coluna_ausente_nao_levanta_e_lista_o_que_existe(instalar_painel):
    """Sem a coluna, a mensagem tem de dizer o que a planilha TEM — é assim
    que se descobre o nome certo sem abrir o arquivo, que vive no Box."""

    class WsFalsa:
        def cell(self, row, column):
            nomes = {1: "CÓDIGO PMIB", 2: "DESCRIÇÃO", 3: "CONDIÇÕES"}
            return type("C", (), {"value": nomes.get(column)})()

    painel = PainelFalso(colunas={config.COL_CODIGO_PMIB: 1})
    painel.ws = WsFalsa()
    instalar_painel(painel)

    n, recado = lmr_status.marcar_aplicacao("/x/status.xlsx", ["4500.0001"], [])

    assert n == 0
    assert "não foi encontrada" in recado
    assert "'CÓDIGO PMIB'" in recado and "'CONDIÇÕES'" in recado
    assert painel.fechou, "a planilha precisa ser fechada mesmo no caminho de erro"


def test_ficha_ausente_na_planilha_e_reportada(instalar_painel):
    instalar_painel(PainelFalso(linhas_por_pmib={"4500.0001": 10}))

    n, recado = lmr_status.marcar_aplicacao(
        "/x/status.xlsx", ["4500.0001", "4500.9999"], []
    )

    assert n == 1
    assert "4500.9999" in recado


def test_nenhuma_ficha_encontrada_nao_salva(instalar_painel):
    painel = instalar_painel(PainelFalso(linhas_por_pmib={}))

    n, recado = lmr_status.marcar_aplicacao("/x/status.xlsx", ["4500.0001"], [])

    assert n == 0
    assert not painel.salvou
    assert "Nada foi salvo" in recado


# =============================================================================
# C. Nunca levantar por causa da planilha
# =============================================================================

def test_erro_ao_abrir_devolve_mensagem_em_vez_de_levantar(monkeypatch):
    import sigft.core.excel.status_sheet as modulo

    def explode(*_a, **_k):
        raise OSError("arquivo corrompido")

    monkeypatch.setattr(modulo, "StatusPMIB", explode)

    n, recado = lmr_status.limpar_aplicacao("/x/status.xlsx", ["4500.0001"])

    assert n == 0
    assert "Não consegui abrir" in recado


def test_excel_travado_pergunta_e_retenta(instalar_painel):
    """O canal do CP D: com a planilha aberta, o usuário decide."""
    painel = instalar_painel(
        PainelFalso(
            linhas_por_pmib={"4500.0001": 10},
            erro_ao_salvar=PermissionError(13, "aberto no Excel"),
        )
    )
    perguntas = []

    n, _ = lmr_status.limpar_aplicacao(
        "/x/status.xlsx",
        ["4500.0001"],
        retry_lock=lambda caminho: perguntas.append(caminho) or True,
    )

    assert perguntas == ["/x/status.xlsx"]
    assert painel.salvou
    assert n == 1


def test_excel_travado_sem_canal_devolve_recado_claro(instalar_painel):
    painel = instalar_painel(
        PainelFalso(
            linhas_por_pmib={"4500.0001": 10},
            erro_ao_salvar=PermissionError(13, "aberto no Excel"),
        )
    )

    n, recado = lmr_status.limpar_aplicacao("/x/status.xlsx", ["4500.0001"])

    assert n == 0
    assert "aberto no Excel" in recado
    assert "trabalho no portal está feito" in recado
    assert painel.fechou


# =============================================================================
# D. O alias do cabeçalho — o nome real tem hífen cercado de espaços
# =============================================================================

def test_o_nome_oficial_da_coluna_e_o_da_planilha_do_usuario():
    assert config.COL_APLICACAO_LMR == "APLICAÇÃO - LMR"


def test_o_nome_oficial_e_o_primeiro_dos_aliases():
    assert config.ALIASES_COL_APLICACAO_LMR[0] == config.COL_APLICACAO_LMR


def test_os_aliases_cobrem_a_variacao_sem_acento():
    """Uma planilha que passou por exportação perde cedilha e til; o casamento
    é exato, então sem o alias a marcação sumiria em silêncio."""
    assert "APLICACAO - LMR" in config.ALIASES_COL_APLICACAO_LMR


def test_os_dois_servicos_usam_o_mesmo_modulo():
    """Guarda contra a 2ª implementação: se alguém reescrever a marcação
    dentro de um dos serviços, os dois divergem no primeiro detalhe que mudar."""
    import inspect

    from sigft.services import apagar_lmr, lmr

    assert "lmr_status" in inspect.getsource(lmr.marcar_status_pmib)
    assert "lmr_status" in inspect.getsource(apagar_lmr.limpar_status_pmib)
