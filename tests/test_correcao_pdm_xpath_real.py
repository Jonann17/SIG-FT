r"""Os XPath do leitor de características, avaliados de VERDADE.

⚠️ ESTE ARQUIVO EXISTE POR CAUSA DE UMA FALHA CONCRETA, em 2026-09-23. A
primeira execução do módulo de correção de PDM no portal real gravou um retrato
com **todas as características vazias**:

    { "codigo": "", "nome": "", "tipo": "", "valor_pt": "", ... }

...e assim as dezenas de linhas da ficha. A tabela foi encontrada (havia uma
entrada por linha), e nenhum campo dentro dela.

**A causa:** `ler_linha` endereça um campo somando o seletor da linha com o
relativo, e os relativos nasceram com `.//`:

    "(//div[...]//table/tbody/tr)[3]" + ".//td[@data-header='Descrição']"

Isso **não é XPath válido** -- não existe `.` depois de `]` sem uma barra. O
`lxml` diz `XPathEvalError: Invalid expression`, e o Playwright levanta igual.
Os `try/except` de `_texto`, `_valor` e `_existe` engoliam a exceção (eles
existem para que ler a tela não derrube a ficha) e devolviam `""`/`False` para
tudo. Daí: linha contada, campo nenhum, tipo nenhum.

`tech_specs` e `duplicadas_injetor` fazem a mesma soma e funcionam no portal
hoje, por duas rotas diferentes: o primeiro guarda os relativos já com `//`, o
segundo corta o ponto na hora (`XPATH_REL_..._DESCRICAO[1:]`). Só o módulo novo
somava o ponto.

**E por que a suíte não pegou:** o dublê de motor dos outros arquivos casa o
seletor com uma expressão regular e consulta um dicionário -- ele nunca
interpreta XPath, então uma expressão inválida "funciona" nele. E o guard que
comparava os três lugares normalizava o `.` inicial antes de comparar, tratando
como cosmética exatamente a diferença que quebra.

Aqui quem responde é um avaliador de XPath de verdade. É o único lugar do
módulo onde um erro DENTRO da string do seletor aparece. Mesmo papel de
`tests/test_duplicadas_xpath_real.py`, que já existia para a ficha duplicada.

`lxml` é opcional (ver `requirements-dev.txt`): sem ele o arquivo é pulado.
Por isso ele COMPLEMENTA os testes de regra, nunca os substitui.
"""
from __future__ import annotations

import pytest

etree = pytest.importorskip("lxml.etree", reason="lxml e opcional; ver docstring")

from sigft.core.rpa import caracteristicas as carac  # noqa: E402
from sigft.core.rpa import seletores_duplicada as sel  # noqa: E402
from sigft.services import tech_specs  # noqa: E402


# ⚠️ HTML RECONSTRUÍDO a partir do contrato dos seletores (os ids e o
# `data-header` que `seletores_duplicada` e `tech_specs` documentam do portal
# real), e NÃO colado do "inspecionar elemento". Ele prova que as expressões
# são válidas e casam a estrutura esperada; não prova que a estrutura do portal
# é esta. Quem prova isso é a etapa E6 -- e o roteiro pede o HTML de uma linha
# justamente para trocar este bloco pelo de verdade.
_HTML = """
<html><body>
<div id="b12-TechnicalCharacteristics_Content">
  <table><tbody>
    <tr>
      <td data-header="Descrição">1171-ACABAMENTO</td>
      <td><textarea id="b12-b3-TextArea_ValuePT">PINTADO</textarea></td>
      <td><textarea id="b12-b3-TextArea_ValueES">PINTADO</textarea></td>
      <td><select id="b12-b3-DropdownTCUnitsOfMeasurement">
            <option value="1">Metro (M)</option>
            <option value="2" selected="selected">Adimensional (AD)</option>
          </select></td>
    </tr>
    <tr>
      <td data-header="Descrição">1230-TENSAO NOMINAL</td>
      <td><input id="b12-b4-NumberValue_Input" value="220"/></td>
      <td><select id="b12-b4-DropdownTCUnitsOfMeasurement">
            <option value="1" selected="selected">Volt (V)</option>
          </select></td>
    </tr>
    <tr>
      <td data-header="Descrição">1047-FAIXA TEMPERATURA</td>
      <td><select id="b12-b5-Dropdown_IntervalOptions">
            <option value="1" selected="selected">ENTRE</option>
          </select></td>
      <td><input id="b12-b5-MinValue_Input" value="-10"/></td>
      <td><input id="b12-b5-MaxValue_Input" value="50"/></td>
      <td><select id="b12-b5-DropdownTCUnitsOfMeasurement">
            <option value="1" selected="selected">Grau Celsius (C)</option>
          </select></td>
    </tr>
    <tr>
      <td data-header="Descrição">1500-MATERIAL</td>
      <td><select id="b12-b6-Dropdown1">
            <option value="1">ACO CARBONO</option>
            <option value="2" selected="selected">ACO INOX</option>
          </select></td>
    </tr>
  </tbody></table>
</div>
</body></html>
"""


class _MotorDeXPathReal:
    """Dublê de `RPAEngine` que **interpreta o XPath**, em vez de casá-lo com
    uma expressão regular.

    É a diferença entre este arquivo e os outros: aqui uma expressão inválida
    levanta, como levantaria no Playwright, em vez de cair num `else` do dublê.
    """

    def __init__(self, html):
        self.doc = etree.fromstring(html, etree.HTMLParser())

    def _achar(self, seletor):
        # NÃO engole `XPathEvalError`: seletor inválido tem de aparecer.
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
        if no.tag == "textarea":
            return "".join(no.itertext())
        return no.get("value") or ""

    def texto_selecionado(self, seletor):
        achados = self._achar(seletor)
        if not achados:
            return ""
        for opcao in achados[0].xpath(".//option[@selected]"):
            return "".join(opcao.itertext()).strip()
        return ""

    def esta_habilitado(self, _seletor):
        return False

    def click_raw(self, _seletor):
        pass


@pytest.fixture
def motor():
    return _MotorDeXPathReal(_HTML)


# =============================================================================
# A. O defeito de 2026-09-23, no ponto exato
# =============================================================================
def test_o_seletor_de_um_campo_DENTRO_da_linha_e_xpath_valido(motor):
    """O teste que faltava. `(linhas)[1]` + `.//td` levanta `Invalid
    expression`; é assim que todo campo virava string vazia."""
    linha = carac.seletor_da_linha(1)

    for relativo in (carac.REL_DESCRICAO, carac.REL_VALOR_PT, carac.REL_VALOR_ES,
                     carac.REL_INPUT_NUM, carac.REL_INPUT_MIN, carac.REL_INPUT_MAX,
                     carac.REL_SELECT_LISTA, carac.REL_SELECT_INTERVALO,
                     carac.REL_SELECT_UNIDADE):
        expressao = carac.dentro_da_linha(linha, relativo)
        motor.contar(expressao)   # levanta se a expressao nao for valida


def test_a_tabela_e_lida_com_VALOR_e_nao_vazia(motor):
    """O sintoma como o usuário o viu: o retrato saiu com uma entrada por linha
    e todos os campos em branco."""
    lidas = carac.ler_tabela(motor)

    assert len(lidas) == 4
    assert not all(c.esta_vazia for c in lidas), (
        "todas as linhas vieram vazias: e o defeito de 2026-09-23")
    assert [c.codigo for c in lidas] == ["1171", "1230", "1047", "1500"]


def test_cada_TIPO_e_reconhecido_na_tela(motor):
    """Tipo vazio foi o outro rastro do defeito: nenhum dos quatro campos era
    encontrado, então `tipo_da_linha` caía no `return ""`."""
    assert [c.tipo for c in carac.ler_tabela(motor)] == ["CHAR", "NUM", "INT", "LISTA"]


def test_os_valores_chegam_inteiros(motor):
    char, num, intervalo, lista = carac.ler_tabela(motor)

    assert (char.nome, char.valor_pt, char.valor_es) == ("ACABAMENTO", "PINTADO", "PINTADO")
    assert (num.valor_pt, num.unidade) == ("220", "V")
    assert (intervalo.minimo, intervalo.maximo, intervalo.subtipo) == ("-10", "50", "ENTRE")
    assert lista.valor_pt == "ACO INOX"


def test_a_unidade_vem_da_opcao_ESCOLHIDA_e_nao_da_primeira(motor):
    """A linha `CHAR` do HTML tem "Metro (M)" antes de "Adimensional (AD)". Ler
    a primeira opção em vez da escolhida daria `"M"` -- unidade errada é o
    defeito que mais passa batido numa revisão visual, porque o número aparece
    certo e só a coluna de unidade denuncia."""
    assert carac.ler_tabela(motor)[0].unidade == "AD"


# =============================================================================
# B. Os três lugares, agora comparados por COMPORTAMENTO
# =============================================================================
def test_o_relativo_do_leitor_acha_o_MESMO_no_que_o_do_tech_specs(motor):
    """⚠️ O guard antigo comparava os três conjuntos como TEXTO, normalizando o
    `.` inicial -- ou seja, tratava como cosmética exatamente a diferença que
    tornava a expressão inválida. Ele passava verde com o módulo inutilizável.

    Comparar por texto não serve: o que importa é se as duas expressões, DEPOIS
    de concatenadas, acham o mesmo elemento.
    """
    linha = carac.seletor_da_linha(1)
    pares = (
        (carac.REL_DESCRICAO, tech_specs.XPATH_REL_COL_DESCRICAO),
        (carac.REL_VALOR_PT, tech_specs.XPATH_REL_TEXTAREA_PT),
        (carac.REL_VALOR_ES, tech_specs.XPATH_REL_TEXTAREA_ES),
        (carac.REL_SELECT_UNIDADE, tech_specs.XPATH_REL_SELECT_UNIDADE),
    )
    for do_leitor, do_tech_specs in pares:
        meus = motor._achar(carac.dentro_da_linha(linha, do_leitor))
        deles = motor._achar(linha + do_tech_specs)
        assert meus and meus == deles, (do_leitor, do_tech_specs)


def test_o_relativo_do_leitor_acha_o_mesmo_que_o_da_ficha_duplicada(motor):
    """O terceiro lugar. `duplicadas_injetor` corta o ponto na hora
    (`[1:]`) -- rota diferente, resultado que tem de ser o mesmo."""
    linha = carac.seletor_da_linha(1)

    meus = motor._achar(carac.dentro_da_linha(linha, carac.REL_DESCRICAO))
    deles = motor._achar(linha + sel.XPATH_REL_CARACTERISTICA_DESCRICAO[1:])

    assert meus and meus == deles


def test_nenhum_relativo_do_leitor_comeca_com_ponto():
    """A regra estrutural, que roda mesmo sem `lxml` instalado em outro lugar.

    Um relativo com `.` só é utilizável se quem concatena cortar o ponto, e
    depender disso em treze pontos de chamada é como o defeito nasceu.
    """
    relativos = [v for k, v in vars(carac).items()
                 if k.startswith("REL_") and isinstance(v, str)]

    assert relativos
    for relativo in relativos:
        assert not relativo.startswith("."), relativo


def test_dentro_da_linha_aguenta_o_relativo_com_ponto():
    """Defesa em profundidade: a função corta o ponto de qualquer jeito. Se
    alguém copiar um relativo de `seletores_duplicada` (que os guarda com `.`)
    direto para cá, continua funcionando."""
    assert carac.dentro_da_linha("(//tr)[1]", ".//td") == "(//tr)[1]//td"
    assert carac.dentro_da_linha("(//tr)[1]", "//td") == "(//tr)[1]//td"


# =============================================================================
# C. A paginação, com o XPath de verdade
# =============================================================================
def test_uma_pagina_so_nao_entra_em_laco(motor):
    """`esta_habilitado` devolve `False`: a leitura tem de terminar na
    primeira página em vez de girar até o teto."""
    assert len(carac.ler_tabela(motor)) == 4


# =============================================================================
# D. A unidade volta como SIMBOLO, nao como rotulo
# =============================================================================
# ⚠️ ACHADO AO VERIFICAR O CONSERTO DE 2026-09-23, e ele é da mesma família:
# "o leitor não lê o que devia". Com os XPath válidos, a unidade passou a vir
# como o RÓTULO da opção -- `"Adimensional (AD)"` em vez de `"AD"`.
#
# Parece cosmético e não é. Três regras a jusante esperam o SÍMBOLO:
#
#   1. `juntar_para_char` escreve o símbolo dentro do texto quando a linha cai
#      de NUM para CHAR: com o rótulo, a ficha receberia `"220 Volt (V)"`;
#   2. `correcao_pdm_casamento._como_numero` só desfaz o recuo de 2026-08-18
#      quando a unidade gravada é `AD` -- com o rótulo, o caminho de volta
#      NUM->CHAR->NUM deixa de funcionar;
#   3. o relatório omite a unidade quando ela é `AD` (ela não carrega
#      informação); com o rótulo, imprimiria `[Adimensional (AD)]` em toda
#      linha CHAR.
#
# E quem ESCREVE de volta (`tech_specs.selecionar_dropdown_unidade`) casa
# `"(AD)"` dentro do texto da opção: o símbolo é a forma que fecha o ciclo.
def test_a_unidade_volta_como_SIMBOLO(motor):
    lidas = carac.ler_tabela(motor)

    assert [c.unidade for c in lidas[:3]] == ["AD", "V", "C"]


def test_o_simbolo_sai_dos_parenteses():
    assert carac.simbolo_da_unidade("Milímetro (MM)") == "MM"
    assert carac.simbolo_da_unidade("Adimensional (AD)") == "AD"


def test_opcao_sem_parenteses_volta_inteira():
    """Nem toda opção do portal tem o símbolo entre parênteses. Devolver vazio
    perderia a unidade; devolver o texto inteiro ao menos deixa o
    `selecionar_dropdown_unidade` tentar o casamento por sigla solta."""
    assert carac.simbolo_da_unidade("MM") == "MM"
    assert carac.simbolo_da_unidade("") == ""


def test_parenteses_no_MEIO_do_rotulo_nao_confundem():
    """`"Tonelada (curta) (TC)"` tem dois pares. O símbolo é o ÚLTIMO."""
    assert carac.simbolo_da_unidade("Tonelada (curta) (TC)") == "TC"


# =============================================================================
# E. A varredura -- nenhuma constante pode ser XPath inválido
# =============================================================================
def test_todo_xpath_do_leitor_e_uma_expressao_valida(motor):
    """Varredura barata sobre a classe inteira de defeito.

    Uma expressão inválida não dá erro na cara de ninguém: ela levanta dentro
    dos `try/except` que existem para que ler a tela não derrube a ficha, e o
    campo vira string vazia. Um seletor errado de verdade (que casa nada) tem o
    mesmo sintoma e é caso da E6; um seletor que nem PARSEIA é pegável aqui.
    """
    constantes = {k: v for k, v in vars(carac).items()
                  if k.startswith(("XPATH_", "REL_")) and isinstance(v, str)}

    assert constantes
    for nome, expressao in constantes.items():
        alvo = carac.dentro_da_linha(carac.seletor_da_linha(1), expressao) \
            if nome.startswith("REL_") else expressao
        try:
            motor.contar(alvo)
        except etree.XPathEvalError as erro:
            raise AssertionError(f"{nome} nao e XPath valido: {erro}") from erro


def test_a_varredura_reprovaria_o_defeito_de_2026_09_23(motor):
    """Um guard que nunca reprova não protege nada: aqui está a expressão
    exata que rodou no portal do usuário."""
    quebrada = carac.seletor_da_linha(1) + ".//td[contains(@data-header, 'Descrição')]"

    with pytest.raises(etree.XPathEvalError):
        motor.contar(quebrada)
