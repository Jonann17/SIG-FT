r"""
Achar e abrir a ficha ORIGINAL no portal (CP 6.2).

*"A ficha original é sempre encontrável, mas pode variar dentro do portal se
ela está em Elaboração, ou se está em Análise, ou demais campos."*

O que se testa aqui é a NAVEGAÇÃO -- em qual aba procurou, em que ordem, por
qual porta entrou -- com um portal de mentira. Os seletores em si são
verificados contra HTML real em `test_duplicadas_xpath_real.py`.
"""
import pytest

from sigft.core.rpa import seletores_duplicada as sel
from sigft.services import duplicadas_extrator as extrator
from sigft.services import duplicadas_spec as spec


class _EngineFalso:
    """Responde `element_exists` por uma lista de "o que existe na tela" e
    grava tudo o que foi clicado."""

    def __init__(self, existentes):
        self.existentes = list(existentes)
        self.cliques = []
        self.teclas = []

    def element_exists(self, seletor):
        return any(marca in seletor for marca in self.existentes)

    def click_nativo(self, seletor):
        self.cliques.append(seletor)

    def press(self, teclas):
        self.teclas.append(teclas)


class _PortalFalso:
    def __init__(self, engine):
        self.engine = engine
        self.preenchidos = []
        self.foi_para_lista = 0

    def ir_para_lista(self):
        self.foi_para_lista += 1

    def safe_fill(self, seletor, texto):
        self.preenchidos.append((seletor, texto))


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    """A pausa pós-busca é real no portal e inútil no teste: 7 abas x 2,5s."""
    monkeypatch.setattr(extrator.time, "sleep", lambda _s: None)


def _com_ficha_na_aba(nome_da_aba, pmib="4500063671.1471", todas_as_abas=True):
    """Tela em que TODAS as abas existem, mas a ficha só aparece em uma."""
    abas = spec.ABAS_DE_STATUS_DA_LISTA if todas_as_abas else (nome_da_aba,)
    existentes = [f"normalize-space()='{a}'" for a in abas]

    engine = _EngineFalso(existentes)
    portal = _PortalFalso(engine)

    # A linha da ficha só "existe" depois que a aba certa foi clicada.
    original = engine.element_exists

    def element_exists(seletor):
        if "-View" in seletor or "-Edit" in seletor:
            return engine.cliques and f"'{nome_da_aba}'" in engine.cliques[-1]
        return original(seletor)

    engine.element_exists = element_exists
    return portal, engine, pmib


# ===========================================================================
# Em qual aba está
# ===========================================================================
def test_acha_na_primeira_aba_sem_abrir_as_outras():
    """"Em Elaboração" vem primeiro porque é onde a maioria das originais
    está: o caso comum custa uma aba, não sete."""
    portal, engine, pmib = _com_ficha_na_aba("Em Elaboração")

    assert extrator.localizar_aba_da_ficha(portal, pmib) == "Em Elaboração"
    assert len(engine.cliques) == 1


def test_acha_numa_aba_do_meio_percorrendo_na_ordem_da_tela():
    portal, engine, pmib = _com_ficha_na_aba("Em Análise ITAIPU")

    achada = extrator.localizar_aba_da_ficha(portal, pmib)

    assert achada == "Em Análise ITAIPU"
    assert len(engine.cliques) == 3  # Elaboração, Para enviar, Em Análise


def test_acha_na_ultima_aba():
    portal, engine, pmib = _com_ficha_na_aba("Cancelado")

    assert extrator.localizar_aba_da_ficha(portal, pmib) == "Cancelado"
    assert len(engine.cliques) == len(spec.ABAS_DE_STATUS_DA_LISTA)


def test_aba_que_nao_existe_na_tela_e_pulada_sem_erro():
    """O portal não mostra as 7 abas para todo perfil. Tratar ausência como
    falha faria o módulo depender do perfil de quem está logado."""
    portal, engine, pmib = _com_ficha_na_aba(
        "Aprovado pela ITAIPU", todas_as_abas=False)

    assert extrator.localizar_aba_da_ficha(portal, pmib) == "Aprovado pela ITAIPU"
    assert len(engine.cliques) == 1


def test_ficha_inexistente_devolve_none_e_lista_o_que_tentou():
    """Quando falhar, o usuário vai querer saber que as sete foram mesmo
    tentadas -- senão a suspeita cai sobre a busca, não sobre a ficha."""
    engine = _EngineFalso([f"'{a}'" for a in spec.ABAS_DE_STATUS_DA_LISTA])
    portal = _PortalFalso(engine)
    logs = []

    achada = extrator.localizar_aba_da_ficha(portal, "4500063671.9999", logs.append)

    assert achada is None
    juntos = "\n".join(logs)
    for aba in spec.ABAS_DE_STATUS_DA_LISTA:
        assert aba in juntos


def test_sem_nenhuma_aba_na_tela_a_mensagem_diz_isso():
    """Zero abas e "ficha não existe" são problemas diferentes, e confundi-los
    manda o usuário procurar no lugar errado."""
    engine = _EngineFalso([])
    portal = _PortalFalso(engine)
    logs = []

    assert extrator.localizar_aba_da_ficha(portal, "x", logs.append) is None
    assert "nenhuma aba de status" in "\n".join(logs)


def test_a_busca_e_refeita_em_cada_aba():
    """Trocar de aba recarrega a lista; buscar uma vez só encontraria a ficha
    filtrada na aba errada -- ou nenhuma."""
    portal, _engine, pmib = _com_ficha_na_aba("Rejeitado pela ITAIPU")

    extrator.localizar_aba_da_ficha(portal, pmib)

    assert len(portal.preenchidos) == 4
    assert all(texto == pmib for _seletor, texto in portal.preenchidos)


# ===========================================================================
# Por qual porta entra
# ===========================================================================
def test_abre_pela_folha_de_visualizacao_e_nunca_pelo_lapis():
    """Abrir para EDIÇÃO uma ficha já enviada à ITAIPU é efeito colateral em
    ficha de terceiro. A duplicação só precisa ler."""
    portal, engine, pmib = _com_ficha_na_aba("Aprovado pela ITAIPU")

    assert extrator.abrir_original_em_visualizacao(portal, pmib) is True
    ultimo = engine.cliques[-1]
    assert "-View" in ultimo and "fa-file-o" in ultimo
    assert not any("-Edit" in clique for clique in engine.cliques)


def test_ficha_nao_encontrada_nao_clica_em_nada_de_abrir():
    """Clicar sem ter achado abriria uma ficha QUALQUER da lista -- e o robô
    seguiria copiando dela."""
    engine = _EngineFalso([f"'{a}'" for a in spec.ABAS_DE_STATUS_DA_LISTA])
    portal = _PortalFalso(engine)

    assert extrator.abrir_original_em_visualizacao(portal, "4500063671.9999") is False
    assert not any("-View" in clique for clique in engine.cliques)


def test_vai_para_a_lista_antes_de_procurar():
    portal, _engine, pmib = _com_ficha_na_aba("Em Elaboração")

    extrator.abrir_original_em_visualizacao(portal, pmib)

    assert portal.foi_para_lista == 1


def test_a_busca_usa_o_campo_de_filtro_da_lista():
    portal, _engine, pmib = _com_ficha_na_aba("Em Elaboração")

    extrator.abrir_original_em_visualizacao(portal, pmib)

    assert portal.preenchidos[0][0] == sel.XPATH_BUSCA_DA_LISTA


# ===========================================================================
# Literal XPath
# ===========================================================================
def test_nome_de_aba_comum_vira_literal_com_aspas_simples():
    assert extrator._literal_xpath("Em Elaboração") == "'Em Elaboração'"


def test_nome_com_apostrofo_nao_quebra_o_xpath():
    """XPath 1.0 não tem escape dentro do literal; a saída é `concat`."""
    resultado = extrator._literal_xpath("Aprovado d'ITAIPU")

    assert resultado.startswith("concat(") or resultado.startswith('"')
    assert "\\'" not in resultado
