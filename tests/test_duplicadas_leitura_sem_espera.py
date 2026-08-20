r"""
O travamento de 2026-08-20: ler célula que NÃO EXISTE custa 20 s cada.

O log parou aqui e não saiu mais:

    Seção aberta: Documentos
    (nada)

Não é laço infinito -- é espera acumulada, que de fora é indistinguível.
`ler_documentos_da_original` chama `extrator.ler_tabela_de`, que foi escrita
para as tabelas de Fabricante e Fornecedor e lê DOIS campos por linha:

    nome       = _celula(..., "Descrição")     <- existe
    referencia = _celula(..., "Referência")    <- NÃO EXISTE na tabela de
                                                  documentos

E aí a mecânica do Playwright cobra a conta: `Locator.text_content()` e
`Locator.input_value()` AUTO-ESPERAM o elemento. Ausente, esperam o timeout
inteiro (`wait_timeout=20 s`) antes de levantar -- exceção que `_celula`
engole e devolve `""`. Dez documentos = 200 segundos de silêncio; trinta =
dez minutos.

⚠️ O MESMO RISCO ESTAVA EM CONDIÇÕES, e é maior: `duplicadas_condicoes.ler`
percorre 45 campos e nem todos existem em toda ficha. `esta_marcado` já era
seguro (o motor guarda com `contar` antes), mas `get_value` não.

Dois consertos, e os dois são necessários:

  1. **A causa geral** -- ler o que pode não existir passa a checar `contar`
     antes (imediato no Playwright), em vez de esperar. Absente vira `""`/
     `None` na hora.
  2. **A causa local** -- não pedir uma coluna que aquela tabela não tem.
"""
import pytest

from sigft.core.rpa.portal import PMIBPortal
from sigft.services import duplicadas_condicoes as cond
from sigft.services import duplicadas_extrator as extrator
from sigft.services import duplicadas_robo as robo


@pytest.fixture(autouse=True)
def _sem_dormir(monkeypatch):
    """As pausas de Condições (2 s + 1,5 s por sub-aba) são reais no portal e
    puro tempo morto aqui."""
    monkeypatch.setattr(cond.time, "sleep", lambda _s: None)


class _EngineQueEspera:
    """Reproduz a mecânica do Playwright: ler o que não existe ESPERA.

    `esperas` conta quantas vezes o duplo teria queimado o timeout. É o que o
    teste mede -- medir segundos de verdade tornaria a suíte lenta pelo mesmo
    motivo que o robô travou.
    """

    TIMEOUT_S = 20

    def __init__(self, existentes=()):
        self.existentes = set(existentes)
        self.esperas = 0

    def _existe(self, seletor):
        return any(marca in seletor for marca in self.existentes)

    def contar(self, seletor):
        return 1 if self._existe(seletor) else 0

    def texto(self, seletor):
        if not self._existe(seletor):
            self.esperas += 1
            raise TimeoutError(f"esperei {self.TIMEOUT_S}s por {seletor}")
        return "VALOR"

    def get_value(self, seletor):
        if not self._existe(seletor):
            self.esperas += 1
            raise TimeoutError(f"esperei {self.TIMEOUT_S}s por {seletor}")
        return "VALOR"

    def esta_marcado(self, seletor):
        if not self._existe(seletor):
            raise TimeoutError("idem")
        return True


class _PortalQueEspera(PMIBPortal):
    def __init__(self, engine):
        self.engine = engine


# =============================================================================
# 1. O conserto geral: ler o que pode não existir não espera
# =============================================================================
def test_texto_se_existir_nao_queima_o_timeout():
    engine = _EngineQueEspera(existentes=["Descrição"])
    portal = _PortalQueEspera(engine)

    assert portal.texto_se_existir("//td[@data-header='Referência']") == ""
    assert engine.esperas == 0, "o custo do campo ausente tem de ser ZERO espera"


def test_texto_se_existir_devolve_o_texto_quando_existe():
    portal = _PortalQueEspera(_EngineQueEspera(existentes=["Descrição"]))

    assert portal.texto_se_existir("//td[@data-header='Descrição']") == "VALOR"


def test_valor_se_existir_devolve_None_para_campo_ausente():
    """`None` e não `""`: quem lê Condições precisa distinguir "o campo não
    está na tela" de "o campo está vazio". Confundir os dois faria a escrita
    APAGAR um campo da ficha alvo."""
    engine = _EngineQueEspera(existentes=["Input_PackingLength"])
    portal = _PortalQueEspera(engine)

    assert portal.valor_se_existir("//*[contains(@id, 'Input_Sumido')]") is None
    assert portal.valor_se_existir("//*[contains(@id, 'Input_PackingLength')]") == "VALOR"
    assert engine.esperas == 0


# =============================================================================
# 2. A tabela de documentos não tem coluna de Referência
# =============================================================================
def test_ler_tabela_de_sem_segunda_coluna_nao_espera_por_ela():
    engine = _EngineQueEspera(
        existentes=["ancestor::table", "'Descrição'"])
    portal = _PortalQueEspera(engine)

    itens = extrator.ler_tabela_de(portal, "Descrição", coluna_referencia=None)

    assert engine.esperas == 0
    assert itens and itens[0][0] == "VALOR"
    assert itens[0][1] == "", "sem 2ª coluna, a referência é vazia -- não é erro"


def test_documentos_da_original_nao_pede_a_coluna_de_referencia(monkeypatch):
    """A causa local. Pedir "Referência" numa tabela que não a tem era o que
    multiplicava o timeout por linha."""
    pedidos = []
    monkeypatch.setattr(robo.extrator, "abrir_secao", lambda *_a, **_k: True)
    monkeypatch.setattr(
        robo.extrator, "ler_tabela_de",
        lambda _p, coluna, _log=None, coluna_referencia="?": (
            pedidos.append(coluna_referencia) or []))

    robo.ler_documentos_da_original(_PortalQueEspera(_EngineQueEspera()),
                                    lambda _m: None)

    assert pedidos == [None], (
        "a tabela de documentos só tem Descrição; pedir Referência custa o "
        "timeout inteiro por linha"
    )


# =============================================================================
# 3. Condições: 45 campos, e nem todos existem em toda ficha
# =============================================================================
def test_ler_condicoes_nao_espera_por_campo_ausente():
    """O mesmo risco, maior: são 45 campos por ficha. Sem o conserto, uma
    ficha a que faltem 10 deles custa 200 segundos de nada."""
    engine = _EngineQueEspera(existentes=["Input_PackingLength"])
    portal = _PortalQueEspera(engine)
    portal.safe_click = lambda _s: None

    lido = cond.ler(portal, lambda _m: None)

    assert engine.esperas == 0
    assert lido["Armazenamento"]["Input_PackingLength"] == "VALOR"
    assert "TextArea_StorageCareES" not in lido["Armazenamento"], (
        "campo ausente continua fora do dicionário -- entrar com \"\" faria a "
        "escrita apagar o campo da ficha alvo"
    )


# =============================================================================
# 4. O caminho FELIZ da referência também pagava o timeout
# =============================================================================
def test_linha_entrou_na_tabela_nao_espera_pelo_campo_que_SUMIU():
    """`linha_entrou_na_tabela` prova o commit justamente pelo campo TER
    SUMIDO da tela -- e é o desfecho BOM. Lendo com `engine.get_value`, cada
    referência escrita com sucesso custava 20 segundos de espera por um
    elemento que a gente mesmo esperava não achar.

    Não era travamento; era o robô ficando lento no caminho certo, que é pior
    de diagnosticar: ninguém investiga o que está funcionando.
    """
    from sigft.services import duplicadas_injetor as injetor

    engine = _EngineQueEspera(existentes=[])      # o campo sumiu: commit feito
    portal = _PortalQueEspera(engine)

    assert injetor.linha_entrou_na_tabela(portal, "//*[@id='sumiu']", "2904616") is True
    assert engine.esperas == 0


def test_linha_NAO_entrou_quando_o_campo_ainda_tem_o_valor():
    from sigft.services import duplicadas_injetor as injetor

    engine = _EngineQueEspera(existentes=["Input_TextVar"])
    portal = _PortalQueEspera(engine)

    # o duplo devolve "VALOR" -- diferente do que se pediu, logo o portal
    # levou o texto embora
    assert injetor.linha_entrou_na_tabela(
        portal, "//*[@id='b1-Input_TextVar']", "VALOR") is False
