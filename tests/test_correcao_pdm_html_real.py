r"""Os seletores do leitor contra o HTML **REAL** do portal.

⚠️ ESTE ARQUIVO É O ÚNICO DO MÓDULO QUE VÊ O PORTAL. O recorte em
`tests/fixtures/portal/ficha_caracteristicas.html` foi colado pelo usuário do
"inspecionar elemento", em 2026-09-23, depois da primeira execução real ter
falhado. Todo o resto da suíte testa a ideia que o Claude tem do portal.

`tests/test_correcao_pdm_xpath_real.py` já prova que as expressões são VÁLIDAS,
sobre um HTML reconstruído. Este aqui prova que elas casam **o que o portal
manda de verdade** -- e foi ele que achou três coisas que o outro não podia
achar: o formato da unidade, o id da seção que aparece duas vezes e o rótulo
de paginação compartilhado entre abas.

`lxml` é opcional (ver `requirements-dev.txt`): sem ele o arquivo é pulado.
"""
from __future__ import annotations

import pathlib

import pytest

etree = pytest.importorskip("lxml.etree", reason="lxml e opcional; ver docstring")

from sigft.core.rpa import caracteristicas as carac  # noqa: E402
from sigft.core.rpa import seletores_duplicada as sel  # noqa: E402

RECORTE = (pathlib.Path(__file__).resolve().parent
           / "fixtures" / "portal" / "ficha_caracteristicas.html")


class _MotorSobreOHtmlReal:
    """Dublê de `RPAEngine` que interpreta XPath sobre o recorte do portal.

    ⚠️ `texto_selecionado` emula o NAVEGADOR, não o XPath: nenhuma `<option>`
    do portal tem o atributo `selected` (o valor vivo do OutSystems mora na
    propriedade), e um navegador sem atributo nenhum seleciona a PRIMEIRA
    opção. É por isso que o motor de verdade vai por `selectedIndex`.
    """

    def __init__(self):
        fonte = RECORTE.read_text(encoding="utf-8")
        # `encoding="utf-8"` explícito: sem ele o lxml lê o arquivo como
        # latin-1 e todo seletor com acento ("Descrição", "página seguinte")
        # deixa de casar. Isso já me fez "consertar" um seletor que estava bom.
        self.doc = etree.fromstring(fonte, etree.HTMLParser(encoding="utf-8"))

    def _achar(self, seletor):
        return self.doc.xpath(seletor)

    def contar(self, seletor):
        return len(self._achar(seletor))

    def element_exists(self, seletor):
        return bool(self._achar(seletor))

    def texto(self, seletor):
        achados = self._achar(seletor)
        return "".join(achados[0].itertext()) if achados else ""

    def get_value(self, seletor):
        achados = self._achar(seletor)
        if not achados:
            return ""
        no = achados[0]
        return "".join(no.itertext()) if no.tag == "textarea" else (no.get("value") or "")

    def texto_selecionado(self, seletor):
        achados = self._achar(seletor)
        if not achados:
            return ""
        opcoes = achados[0].xpath(".//option")
        escolhidas = [o for o in opcoes if o.get("selected") is not None]
        alvo = escolhidas[0] if escolhidas else (opcoes[0] if opcoes else None)
        return "".join(alvo.itertext()).strip() if alvo is not None else ""

    def esta_habilitado(self, seletor):
        achados = self._achar(seletor)
        return bool(achados) and achados[0].get("disabled") is None

    def click_raw(self, _seletor):
        pass


@pytest.fixture
def motor():
    return _MotorSobreOHtmlReal()


# =============================================================================
# A. A PAGINAÇÃO -- um botão por tabela, sem depender da ordem da página
# =============================================================================
def test_o_botao_de_proxima_pagina_e_UNICO(motor):
    """⚠️ ACHADO DE 2026-09-23, medido no recorte real.

    O botão "próxima página" não é só da tabela de características: a aba
    "Aplicação - LMR" tem a sua própria paginação, com o MESMO `aria-label`.
    O seletor de página inteira casa os DOIS.

    Isto hoje **não quebra**, e a diferença importa: `PlaywrightEngine._loc`
    usa `.first` de propósito, então um seletor ambíguo não levanta -- ele age
    sobre o primeiro em ordem de documento, que nesta página é o certo.

    O que este teste tranca é a dependência de ordem. A ficha do usuário tem
    37 características em 4 páginas; no dia em que um painel renderizado antes
    mostrasse a paginação dele, "está habilitado?" passaria a falar de outra
    tabela, a leitura pararia cedo e a troca de PDM apagaria o que o retrato
    não pegou.
    """
    assert motor.contar(carac.XPATH_PROXIMA_PAGINA) == 1


def test_o_botao_de_proxima_pagina_e_o_DA_TABELA_certa(motor):
    """Não basta ser um: tem de ser o da seção de características."""
    achado = motor._achar(carac.XPATH_PROXIMA_PAGINA)[0]

    ancestrais = [a.get("id") or "" for a in achado.iterancestors()]
    assert any("TechnicalCharacteristics" in x for x in ancestrais), ancestrais


def test_a_pagina_seguinte_DESABILITADA_e_reconhecida(motor):
    """No recorte a ficha está na última página (31 a 37 de 37), e o botão vem
    com `disabled`. Ler isso errado faria o laço girar até o teto."""
    assert motor.esta_habilitado(carac.XPATH_PROXIMA_PAGINA) is False


def test_a_leitura_termina_na_ultima_pagina(motor):
    """Fecha o ciclo: com o botão desabilitado, `ler_tabela` para."""
    assert len(carac.ler_tabela(motor)) == 2


# =============================================================================
# B. A UNIDADE -- o formato é `(SIGLA) NOME`, e não `Nome (SIGLA)`
# =============================================================================
def test_o_rotulo_da_unidade_no_portal_e_SIGLA_primeiro(motor):
    """O recorte mostra `(AD) ADIMENSIONAL`. A docstring de
    `tech_specs.selecionar_dropdown_unidade` dá o exemplo `"Milímetro (MM)"`,
    que está desatualizado -- ela só funciona porque procura `"(AD)"` como
    SUBSTRING, e não no fim."""
    opcoes = motor._achar(carac.dentro_da_linha(carac.seletor_da_linha(1),
                                                carac.REL_SELECT_UNIDADE))[0]
    rotulos = ["".join(o.itertext()).strip() for o in opcoes.xpath(".//option")]

    assert "(AD) ADIMENSIONAL" in rotulos


def test_o_simbolo_sai_do_rotulo_REAL():
    """⚠️ A primeira versão de `simbolo_da_unidade` procurava os parênteses no
    FIM do texto, e devolvia `"(AD) ADIMENSIONAL"` inteiro. Isso iria para o
    retrato, para o texto da conversão NUM->CHAR (`"220 (V) VOLT"`) e para o
    relatório."""
    assert carac.simbolo_da_unidade("(AD) ADIMENSIONAL") == "AD"
    assert carac.simbolo_da_unidade("(MM) MILIMETRO") == "MM"


def test_o_simbolo_tambem_sai_do_formato_do_combo_de_ESTOQUE():
    """O outro combo da mesma tela escreve ao contrário (`UNIDADE - (UN)`).
    Aguentar as duas formas custa uma linha."""
    assert carac.simbolo_da_unidade("UNIDADE - (UN)") == "UN"
    assert carac.simbolo_da_unidade("CENTÍMETRO QUADRADO - (CM2)") == "CM2"


def test_o_placeholder_do_dropdown_NAO_vira_unidade():
    """A primeira `<option>` é `Selecionar`, e nenhuma opção traz o atributo
    `selected`. Uma linha sem unidade escolhida devolveria `"Selecionar"` como
    unidade -- que iria para o retrato e depois seria escrita na ficha."""
    assert carac.simbolo_da_unidade("Selecionar") == ""
    assert carac.simbolo_da_unidade("Selecione a origem") == ""


# =============================================================================
# C. A SEÇÃO -- `TechnicalCharacteristics` casa o cabeçalho TAMBÉM
# =============================================================================
def test_a_secao_da_tabela_e_UMA(motor):
    """`contains(@id, 'TechnicalCharacteristics')` casa o painel
    (`..._Content`) **e o cabeçalho da aba** (`..._Header`). Hoje sobrevive
    porque o cabeçalho não tem tabela dentro; é sorte, não desenho."""
    assert motor.contar(carac.XPATH_SECAO) == 1


def test_as_linhas_sao_so_as_da_tabela_de_caracteristicas(motor):
    """A aba "Aplicação - LMR" tem outra `<table>` com `<tr class="table-row">`.
    Se o escopo escorregar, o leitor fotografa linhas de outra seção."""
    assert motor.contar(carac.XPATH_LINHAS) == 2


# =============================================================================
# D. A LEITURA INTEIRA, sobre o markup do portal
# =============================================================================
def test_as_duas_linhas_reais_sao_lidas_com_valor(motor):
    lidas = carac.ler_tabela(motor)

    assert [c.codigo for c in lidas] == ["1650", "8267"]
    assert [c.nome for c in lidas] == ["COMPONENTES", "CERTIFICADO"]
    assert [c.tipo for c in lidas] == ["CHAR", "CHAR"]
    assert lidas[0].valor_pt == "BOMBA+BASE"
    assert lidas[0].valor_es == "BOMBA+BASE"


def test_o_espanhol_e_o_portugues_saem_DIFERENTES_quando_sao(motor):
    """A segunda linha do recorte tem os dois idiomas escritos de verdade. Se o
    leitor trocasse os dois textareas, isso passaria batido numa linha em que
    PT e ES são iguais -- e a ficha sairia com o espanhol em português."""
    certificado = carac.ler_tabela(motor)[1]

    assert certificado.valor_pt.startswith("CERTIFICADOS DE MATERIAIS")
    assert certificado.valor_es.startswith("CERTIFICADOS DE MATERIALES")


def test_a_descricao_sai_do_FLIP_CONTENT_sem_o_tooltip(motor):
    """A célula da descrição tem um `osui-flip-content` e um tooltip dentro. O
    `textContent` traz tudo junto; o que interessa é o `<código> - <NOME>`."""
    primeira = carac.ler_tabela(motor)[0]

    assert (primeira.codigo, primeira.nome) == ("1650", "COMPONENTES")


def test_a_descricao_do_portal_tem_ESPACOS_em_volta_do_hifen(motor):
    """`1650 - COMPONENTES`, e não `1650-COMPONENTES`. O regex precisa dos dois
    `\\s*`; sem eles, código e nome saem vazios em toda a ficha."""
    texto = motor.texto(carac.dentro_da_linha(carac.seletor_da_linha(1),
                                              carac.REL_DESCRICAO))

    assert "1650 - COMPONENTES" in " ".join(texto.split())
    assert carac.codigo_e_nome(texto)[0] == "1650"


def test_nenhuma_linha_desta_ficha_e_NUM_INT_ou_LISTA(motor):
    """Honestidade sobre o limite do recorte: as sete linhas da ficha real são
    todas "Texto livre". Os outros três tipos continuam sem prova de portal --
    é o que a etapa E6 tem de trazer."""
    assert {c.tipo for c in carac.ler_tabela(motor)} == {"CHAR"}


# =============================================================================
# E. O COMBO DO PDM -- por que a troca falhou
# =============================================================================
def test_o_combo_do_pdm_E_encontravel_com_outra_aba_na_frente(motor):
    """⚠️ Isto inocenta o seletor. O painel de "Informações gerais" fica no DOM
    com `aria-hidden="true"` enquanto a aba de características está aberta, e
    `XPATH_PDM_VALOR` acha o combo assim mesmo.

    Ou seja, o `PAROU em troca (combo de PDM nao encontrado)` não foi seletor
    errado: foi LEITURA CEDO DEMAIS, com o painel ainda remontando depois da
    volta de aba. Quem conserta é `esperar_o_combo`.
    """
    achados = motor._achar(sel.XPATH_PDM_VALOR)

    assert len(achados) == 1
    assert achados[0].get("data-tooltip").startswith("PDM.")


def test_o_texto_do_combo_traz_a_REVISAO(motor):
    """É o que permite decidir "já é o vigente?" sem comparar códigos."""
    texto = motor.texto(sel.XPATH_PDM_VALOR).strip()

    assert texto == "PDM.4320.002 - MOTOBOMBA, ACIONAMENTO ELETRICO, R2"
    assert texto.endswith("R2")


def test_o_seletor_do_pdm_nao_pega_o_combo_de_UNIDADE_DE_ESTOQUE(motor):
    """A mesma aba tem outro `vscomp-value` (`UNIDADE - (UN)`). O que separa os
    dois é o `data-tooltip` começar com `PDM.`."""
    todos = motor._achar(
        "//div[contains(concat(' ', normalize-space(@class), ' '), ' vscomp-value ')]")

    assert len(todos) == 2, "o recorte precisa dos dois para o teste valer"
    assert motor.contar(sel.XPATH_PDM_VALOR) == 1
