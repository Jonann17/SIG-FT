r"""
O clique nas sub-abas de Condições não pode cair no `Title` de outra seção.

`XPATH_CONDICOES_SUBABA` era `//*[contains(@id, 'Title')]/div[{posicao}]`, na
PÁGINA INTEIRA. A ficha tem vários contêineres cujo id termina em `Title`
(cada aba do cabeçalho tem o seu, e as seções também). Se um deles, que não o
de Condições, tiver `div` filhos, o clique em «Armazenamento» (posição 1) pode
cair nele -- e a ficha sai da tela. É o que obrigava a reabrir à mão.

Estes testes avaliam o XPath DE VERDADE (lxml) sobre uma página com DOIS
`Title` com filhos: o de Informações Gerais e o de Condições.
"""
import pytest

from sigft.core.rpa import seletores_duplicada as sel
from sigft.services import duplicadas_condicoes as cond

etree = pytest.importorskip("lxml.etree", reason="lxml e dependencia do projeto")


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(cond.time, "sleep", lambda _s: None)


def _pagina(com_aba_condicoes=True, com_armazenamento=False):
    aba = (
        '<button role="tab" class="osui-tabs__header-item" aria-controls="b10-$b17">'
        '<div id="b10-b8-Title">Condições</div></button>'
    ) if com_aba_condicoes else ""
    campo = '<input id="b10-b17-b1-Input_PackingLength">' if com_armazenamento else ""
    return f"""
<div id="ficha">
  <div class="osui-tabs__header">
    <button role="tab" class="osui-tabs__header-item" aria-controls="b10-$b12">
      <div id="b10-b5-Title">Informações Gerais</div></button>
    {aba}
  </div>
  <div id="b10-$b12">
    <div id="b10-b12-Title">
      <div>Geral 1</div><div>Geral 2</div><div>Geral 3</div>
      <div>Geral 4</div><div>Geral 5</div>
    </div>
  </div>
  <div id="b10-$b17">
    <div id="b10-b17-Title">
      <div>Condições de armazenamento</div><div>Condições financeiras</div>
      <div>Condições de transporte</div><div>Condições de manutenção</div>
      <div>Condições de descarte</div>
    </div>
    {campo}
  </div>
</div>"""


class _EngineLxml:
    def __init__(self, html):
        self.carregar(html)

    def carregar(self, html):
        self.arvore = etree.fromstring(html, etree.HTMLParser())

    def contar(self, seletor):
        return len(self.arvore.xpath(seletor))

    def atributo(self, seletor, nome):
        nos = self.arvore.xpath(seletor)
        return (nos[0].get(nome) or "") if nos else ""


class _Portal:
    def __init__(self, html):
        self.engine = _EngineLxml(html)
        self.cliques = []   # texto do elemento que o clique atingiria

    def safe_click(self, seletor):
        nos = self.engine.arvore.xpath(seletor)
        self.cliques.append(" ".join("".join(nos[0].itertext()).split()) if nos else None)


def test_o_clique_cai_no_title_de_condicoes_e_nunca_no_de_informacoes_gerais():
    portal = _Portal(_pagina())

    assert cond.reabrir_subaba(portal, "Transporte") is True

    assert portal.cliques == ["Condições de transporte"]


def test_sem_o_painel_e_com_varias_coincidencias_NAO_clica_e_diz_quantas():
    portal = _Portal(_pagina(com_aba_condicoes=False))
    linhas = []

    assert cond.reabrir_subaba(portal, "Transporte", linhas.append) is False

    assert portal.cliques == []
    texto = "\n".join(linhas)
    assert "2" in texto and "b10-b12-Title" in texto and "b10-b17-Title" in texto


def test_a_ficha_fora_da_tela_aciona_a_recuperacao_e_tenta_UMA_vez():
    portal = _Portal(_pagina(com_aba_condicoes=False))
    chamadas = []

    def recuperar():
        chamadas.append(1)
        portal.engine.carregar(_pagina())
        return True

    assert cond.reabrir_subaba(portal, "Descarte", recuperar=recuperar) is True

    assert chamadas == [1]
    assert portal.cliques == ["Condições de descarte"]


def test_se_a_recuperacao_falha_nao_clica_e_nao_insiste():
    portal = _Portal(_pagina(com_aba_condicoes=False))
    chamadas = []

    def recuperar():
        chamadas.append(1)
        return False

    assert cond.reabrir_subaba(portal, "Descarte", recuperar=recuperar) is False

    assert chamadas == [1]
    assert portal.cliques == []


def test_com_a_ficha_na_tela_e_clique_ambiguo_nao_se_recupera():
    """Ficha presente mas Title duplicado dentro do painel: reabrir não ajuda."""
    html = _pagina().replace(
        '<div id="b10-b17-Title">',
        '<div id="b10-b17-Title2"><div>x</div></div><div id="b10-b17-Title">')
    portal = _Portal(html)
    chamadas = []

    assert cond.reabrir_subaba(
        portal, "Armazenamento", recuperar=lambda: chamadas.append(1)) is False

    assert chamadas == [] and portal.cliques == []


def test_armazenamento_ja_aberta_NAO_e_clicada_na_ida():
    portal = _Portal(_pagina(com_armazenamento=True))

    cond.abrir_subaba(portal, "Armazenamento")

    assert portal.cliques == []


def test_armazenamento_fechada_e_clicada_na_ida():
    portal = _Portal(_pagina(com_armazenamento=False))

    cond.abrir_subaba(portal, "Armazenamento")

    assert portal.cliques == ["Condições de armazenamento"]


def test_o_repasse_continua_clicando_em_armazenamento():
    portal = _Portal(_pagina(com_armazenamento=True))

    cond.reabrir_subaba(portal, "Armazenamento")

    assert portal.cliques == ["Condições de armazenamento"]


def test_o_seletor_da_subaba_e_escopado_pelo_painel():
    assert "{painel}" in sel.XPATH_CONDICOES_SUBABA_NO_PAINEL


# --- o robô: Documentos e imagens --------------------------------------------
def test_documentos_e_imagens_reabre_a_alvo_se_a_ficha_saiu_da_tela(monkeypatch):
    from sigft.services import duplicadas_robo as robo

    portal = _Portal(_pagina(com_aba_condicoes=False))
    aberturas, reaberturas = [], []

    def abrir_secao(_portal, nome, *_a, **_k):
        aberturas.append(nome)
        return len(aberturas) > 1   # a primeira falha, a segunda pega

    def reabrir(_portal, pmib, _log=None):
        reaberturas.append(pmib)
        portal.engine.carregar(_pagina())
        return True

    monkeypatch.setattr(robo.extrator, "abrir_secao", abrir_secao)
    monkeypatch.setattr(robo, "abrir_alvo_para_edicao", reabrir)

    assert robo.abrir_documentos_e_imagens(portal, "PMIB123") is True
    assert reaberturas == ["PMIB123"] and len(aberturas) == 2


def test_documentos_e_imagens_nao_reabre_se_a_ficha_esta_na_tela(monkeypatch):
    from sigft.services import duplicadas_robo as robo

    portal = _Portal(_pagina())
    monkeypatch.setattr(robo.extrator, "abrir_secao", lambda *_a, **_k: False)
    monkeypatch.setattr(robo, "abrir_alvo_para_edicao",
                        lambda *_a, **_k: pytest.fail("nao devia reabrir"))

    assert robo.abrir_documentos_e_imagens(portal, "PMIB123") is False
