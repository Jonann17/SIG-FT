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

    def contar(self, seletor):
        """Quantos casam. Existe por causa de `esperar_a_ficha_abrir`.

        ⚠️ A ABA DA FICHA SÓ APARECE DEPOIS DO CLIQUE NA FOLHA, e o dublê
        precisa modelar isso -- senão ele afirmaria que a ficha já estava
        aberta antes de o robô clicar, e a espera que este teste protege
        passaria mesmo se alguém a removesse.
        """
        if "Condições" in seletor:
            return 1 if any("-View" in c for c in self.cliques) else 0
        return 1 if self.element_exists(seletor) else 0

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
    """A pausa pós-busca é real no portal e inútil no teste: 7 abas x 2,5s.

    Vale também para a pausa de `esperar_a_ficha_abrir`, que importa `time`
    dentro da função -- por isso o patch é no módulo `time`, não no atributo.
    """
    import time as _time
    monkeypatch.setattr(extrator.time, "sleep", lambda _s: None)
    monkeypatch.setattr(_time, "sleep", lambda _s: None)


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


# ===========================================================================
# A LISTA AINDA NÃO RENDERIZOU — o defeito de 2026-08-21, 16:16
# ===========================================================================
# No log do usuário a primeira ficha do lote saiu com
#
#   [Erro] Ficha 4500063671.1256 não encontrada. Abas tentadas: Para enviar à
#   ITAIPU, Em Análise ITAIPU, Rejeitado pela ITAIPU, Aprovado parcialmente IB,
#   Aprovado pela ITAIPU, Cancelado.
#
# SEIS abas, e falta exatamente a PRIMEIRA -- "Em Elaboração", que é onde a
# segunda ficha do mesmo lote foi encontrada 2 segundos depois.
#
# A causa: `ir_para_lista` só navega se a URL for outra, então na primeira
# ficha ela não faz nada e não espera; `element_exists` é `count() > 0`, uma
# checagem IMEDIATA; e a regra "aba que não existe na tela é pulada em
# silêncio" (perfis diferentes veem abas diferentes) transformou "a tela ainda
# não montou" em "esta aba não existe". Nos milissegundos seguintes o React
# terminou e as outras seis apareceram.
#
# Ou seja: a primeira ficha de todo lote arrisca perder a aba onde a maioria
# das originais está.

class _EngineQueDemoraAMontar(_EngineFalso):
    """A tela só monta depois de `atrasos` consultas -- como o React real."""

    def __init__(self, existentes, atrasos):
        super().__init__(existentes)
        self.restam = atrasos

    def element_exists(self, seletor):
        if self.restam > 0:
            self.restam -= 1
            return False
        return super().element_exists(seletor)


def test_espera_a_lista_montar_antes_de_dizer_que_a_aba_nao_existe():
    """A aba de status só é considerada ausente depois que a LISTA existe."""
    abas = [f"normalize-space()='{a}'" for a in spec.ABAS_DE_STATUS_DA_LISTA]
    engine = _EngineQueDemoraAMontar(abas, atrasos=3)
    portal = _PortalFalso(engine)

    original = engine.element_exists

    def element_exists(seletor):
        if "-View" in seletor or "-Edit" in seletor:
            return bool(engine.cliques) and "'Em Elaboração'" in engine.cliques[-1]
        return original(seletor)

    engine.element_exists = element_exists

    assert extrator.localizar_aba_da_ficha(portal, "4500063671.1256") == \
        "Em Elaboração"


def test_desiste_de_esperar_e_diz_no_log():
    """Tela que nunca monta não pode travar o lote -- mas tem de sair do
    silêncio: hoje a mensagem culpa a ficha ("não encontrada"), quando o
    problema é que nenhuma aba apareceu."""
    engine = _EngineFalso([])          # nada existe, nunca
    portal = _PortalFalso(engine)
    logs = []

    assert extrator.localizar_aba_da_ficha(portal, "4500063671.1256",
                                           logs.append) is None
    assert any("nenhuma aba de status" in linha.lower() for linha in logs)


# ===========================================================================
# A espera pela TELA (2026-08-24)
# ===========================================================================

def test_clique_que_nao_abre_a_ficha_devolve_False_e_nao_True():
    """O defeito que fazia o log culpar o portal por uma corrida do robô.

    Antes desta espera a função devolvia `True` no instante do clique. Quem
    vinha depois -- abrir seção, varrer pares -- rodava contra a LISTA ainda
    na tela e falhava com "a aba 'Condições' não existe nesta tela". O erro
    aparecia três chamadas adiante, no lugar errado.
    """
    portal, engine, pmib = _com_ficha_na_aba("Em Elaboração")
    # A aba da ficha NUNCA aparece: modela o clique que não pegou.
    engine.contar = lambda seletor: 0 if "Condições" in seletor else 1

    mensagens = []
    assert extrator.abrir_original_em_visualizacao(
        portal, pmib, mensagens.append) is False
    assert any("não apareceu" in m for m in mensagens), mensagens
    # E o motivo tem de nomear a ficha, senão o log do lote não serve.
    assert any(pmib in m for m in mensagens), mensagens


def test_a_espera_olha_a_ABA_DA_FICHA_e_nunca_a_url():
    """A URL do OutSystems continua `PMIB_DatasheetList` com a ficha aberta.

    Este teste falharia se alguém trocasse o sinal por `page.url`: o dublê não
    tem URL nenhuma, e o único jeito de `esperar_a_ficha_abrir` responder é
    perguntando pela aba.
    """
    portal, engine, pmib = _com_ficha_na_aba("Em Elaboração")
    perguntado = []
    original = engine.contar

    def contar(seletor):
        perguntado.append(seletor)
        return original(seletor)

    engine.contar = contar
    assert extrator.abrir_original_em_visualizacao(portal, pmib) is True
    assert any("Condições" in s for s in perguntado), perguntado


# ===========================================================================
# Autoconferência (2026-10-20): lista que não montou é RECARREGADA
# ===========================================================================
# Log de 2026-10-19: 1431 e 1432 perdidas com "nenhuma aba de status na tela",
# logo depois de um formulário de imagem preso aberto.
class _EngineQueSoMontaRecarregando(_EngineFalso):
    def __init__(self):
        super().__init__([])
        self.urls = []

    def goto(self, url):
        self.urls.append(url)
        self.existentes = ["'Em Elaboração'", "-View"]


def test_lista_sem_abas_e_RECARREGADA_e_a_ficha_e_achada():
    from sigft import config
    engine = _EngineQueSoMontaRecarregando()
    portal = _PortalFalso(engine)
    logs = []

    achada = extrator.localizar_aba_da_ficha(portal, "4500063671.1240", logs.append)

    assert achada == "Em Elaboração"
    assert engine.urls == [config.PORTAL_URL]
    assert engine.teclas[:2] == ["ESCAPE", "ESCAPE"], "fecha o diálogo antes"
    assert "[Autoconferência]" in "\n".join(logs)


def test_lista_que_monta_sozinha_NAO_recarrega():
    engine = _EngineQueSoMontaRecarregando()
    engine.existentes = ["'Em Elaboração'", "-View"]
    portal = _PortalFalso(engine)

    extrator.localizar_aba_da_ficha(portal, "4500063671.1240")

    assert engine.urls == []


def test_recarregar_que_falha_nao_derruba_o_lote():
    engine = _EngineFalso([])        # sem `goto`: AttributeError
    portal = _PortalFalso(engine)
    logs = []

    assert extrator.localizar_aba_da_ficha(portal, "x", logs.append) is None
    assert "nenhuma aba de status" in "\n".join(logs)
