r"""
Os XPath da ficha duplicada, avaliados de VERDADE contra o HTML real do portal.

O resto da suíte testa a REGRA (`parear_rotulos_e_valores` recebendo tokens já
classificados). Aqui quem classifica é um avaliador de XPath de verdade, sobre
o markup que o usuário colou do "inspecionar elemento" -- ou seja, é o único
lugar do projeto onde um erro DENTRO da string do seletor aparece.

`lxml` **não** é dependência do projeto e não está no ambiente de todo mundo:
sem ele o arquivo inteiro é pulado. Por isso ele COMPLEMENTA os testes de
regra, nunca os substitui -- o que estes protegem não pode depender de um
pacote opcional.
"""
import pytest

etree = pytest.importorskip("lxml.etree", reason="lxml e opcional; ver docstring")

from sigft.core.rpa import seletores_duplicada as sel  # noqa: E402
from sigft.services import duplicadas_extrator as extrator  # noqa: E402


# HTML colado do portal em 2026-08-11/12, com os três casos que importam:
# padrão A (Volume), padrão B invertido (Nocivos) e a armadilha do badge
# (Logística de reversa).
_HTML = """
<div id="ficha">
  <fieldset>
    <legend><div id="b12-Legend">
      <span class="text-primary font-size-base">Volume (cm3)</span>
    </div></legend>
    <div id="b12-Content">
      <div data-container="">
        <label data-label=""><span class="text-primary">Comprimento da embalagem unitaria</span></label>
        <div data-container="" class="margin-top-s">
          <div data-block="PMIB_DataSheetView.Block_Expression" id="b12-b20-b1-$b3">
            <span data-expression="">6</span>
          </div>
        </div>
      </div>
      <div data-container="">
        <label data-label=""><span class="text-primary">Largura da embalagem unitaria</span></label>
        <div data-container="">
          <div data-block="PMIB_DataSheetView.Block_Expression" id="b12-b20-b1-$b4">
            <span data-expression="">4</span>
          </div>
        </div>
      </div>
      <div data-container="">
        <label data-label=""><span class="text-primary">Altura da embalagem unitaria</span></label>
        <div data-container="">
          <div data-block="PMIB_DataSheetView.Block_Expression" id="b12-b20-b1-$b5">
            <span data-expression=""></span>
          </div>
        </div>
      </div>
    </div>
  </fieldset>

  <fieldset>
    <legend><div id="b13-Legend">
      <span class="text-primary font-size-base">Nocivos ou Outros Cuidados</span>
    </div></legend>
    <div id="b13-Content">
      <div>
        <span class="text-primary font-size-base">Nocivo</span>
        <div class="custom">
          <span><input class="radio-button" disabled type="checkbox" checked id="b13-Checkbox1"></span>
          <label data-label="">Nao contem agentes nocivos</label>
        </div>
      </div>
      <div>
        <span class="text-primary font-size-base">Outros cuidados</span>
        <div class="custom">
          <span><input class="radio-button" disabled type="checkbox" checked id="b13-Checkbox2"></span>
          <label data-label="">Nao se&nbsp;aplica</label>
        </div>
      </div>
    </div>
  </fieldset>

  <fieldset>
    <legend><div id="b14-Legend">
      <span class="text-primary font-size-base">Logistica de reversa</span>
    </div></legend>
    <div id="b14-Content">
      <div>
        <span class="text-primary font-size-base">Logistica de reversa</span>
        <div class="custom">
          <span><input class="radio-button" disabled type="checkbox" checked id="b14-Checkbox1"></span>
          <label data-label="">Nao aplica</label>
        </div>
      </div>
      <div data-block="Numbers.Badge" class="badge">
        <span data-expression="" class="OSFillParent">0</span>
      </div>
    </div>
  </fieldset>
</div>
"""


class _EngineLxml:
    """Motor de mentira que avalia XPath DE VERDADE sobre `_HTML`.

    Implementa só os três métodos do contrato que o extrator usa -- e o fato
    de serem três é, por si, um resultado: a leitura inteira da ficha cabe em
    `contar` + `texto` + `element_exists`.
    """

    def __init__(self, html=_HTML):
        self.arvore = etree.fromstring(html, etree.HTMLParser())
        self.consultas = []

    def _nos(self, seletor):
        self.consultas.append(seletor)
        return self.arvore.xpath(seletor)

    def contar(self, seletor):
        return len(self._nos(seletor))

    def element_exists(self, seletor):
        return bool(self._nos(seletor))

    def texto(self, seletor):
        nos = self._nos(seletor)
        if not nos:
            return ""
        return " ".join("".join(nos[0].itertext()).split())


# ===========================================================================
# A varredura devolve os nós certos, na ordem certa
# ===========================================================================
def test_a_varredura_de_um_bloco_nao_vaza_para_os_outros():
    """`A/.//x | .//y` seriam DUAS expressões, e a segunda varreria a página
    inteira -- campo de outro bloco apareceria no meio deste."""
    engine = _EngineLxml()
    uniao = extrator._ancorar_no_bloco("(//fieldset)[1]")

    # 3 rótulos + 3 valores do bloco de Volume, e nada dos outros dois blocos.
    assert engine.contar(uniao) == 6


def test_a_legenda_do_fieldset_nao_entra_como_rotulo():
    """A legenda usa a MESMA classe `text-primary` do rótulo do padrão B; sem
    `not(ancestor::legend)` ela viraria um campo chamado "Volume (cm3)"."""
    engine = _EngineLxml()
    _titulo, campos = extrator.ler_bloco(engine, 1)

    assert "Volume (cm3)" not in campos


# ===========================================================================
# Padrão A — Volume
# ===========================================================================
def test_bloco_de_volume_sai_com_os_tres_campos():
    engine = _EngineLxml()

    titulo, campos = extrator.ler_bloco(engine, 1)

    assert titulo == "Volume (cm3)"
    assert campos == {
        "Comprimento da embalagem unitaria": "6",
        "Largura da embalagem unitaria": "4",
        "Altura da embalagem unitaria": "",  # campo vazio na tela CONTINUA na saída
    }


# ===========================================================================
# Padrão B — a inversão
# ===========================================================================
def test_bloco_de_opcoes_marcadas_nao_inverte_rotulo_e_valor():
    """Sem o discriminador, "Nao contem agentes nocivos" viria como RÓTULO e o
    campo "Nocivo" sumiria da ficha copiada -- em silêncio."""
    engine = _EngineLxml()

    titulo, campos = extrator.ler_bloco(engine, 2)

    assert titulo == "Nocivos ou Outros Cuidados"
    assert campos == {
        "Nocivo": "Nao contem agentes nocivos",
        "Outros cuidados": "Nao se aplica",  # &nbsp; normalizado
    }


# ===========================================================================
# A armadilha do contador de anexos
# ===========================================================================
def test_o_badge_de_anexo_nao_vira_valor_de_campo():
    """O clipe de papel também é `span[@data-expression]`. O que o separa é o
    namespace do bloco (`Numbers.Badge` != `PMIB_DataSheetView.Block_Expression`).
    Sem isso, "Logistica de reversa" viria como "0": plausível e errado."""
    engine = _EngineLxml()

    _titulo, campos = extrator.ler_bloco(engine, 3)

    assert campos == {"Logistica de reversa": "Nao aplica"}
    assert "0" not in campos.values()


def test_varredura_do_bloco_do_badge_tem_so_dois_nos():
    engine = _EngineLxml()

    assert engine.contar(extrator._ancorar_no_bloco("(//fieldset)[3]")) == 2


# ===========================================================================
# A classificação valor/rótulo, nó a nó
# ===========================================================================
@pytest.mark.parametrize("indice, esperado", [
    (1, False),  # <span> dentro do <label>  -> rótulo (padrão A)
    (2, True),   # <span data-expression>    -> valor  (padrão A)
    (3, False),
    (4, True),
])
def test_predicado_separa_valor_de_rotulo_no_padrao_a(indice, esperado):
    engine = _EngineLxml()
    uniao = extrator._ancorar_no_bloco("(//fieldset)[1]")

    assert extrator._e_valor(engine, uniao, indice) is esperado


@pytest.mark.parametrize("indice, esperado", [
    (1, False),  # <span class=text-primary> solto -> rótulo (padrão B)
    (2, True),   # <label data-label> sem span     -> valor  (padrão B)
])
def test_predicado_separa_valor_de_rotulo_no_padrao_b(indice, esperado):
    engine = _EngineLxml()
    uniao = extrator._ancorar_no_bloco("(//fieldset)[2]")

    assert extrator._e_valor(engine, uniao, indice) is esperado


# ===========================================================================
# A seção inteira
# ===========================================================================
def test_ler_secao_visivel_devolve_os_tres_blocos():
    engine = _EngineLxml()

    blocos = extrator.ler_secao_visivel(engine)

    assert [titulo for titulo, _campos in blocos] == [
        "Volume (cm3)", "Nocivos ou Outros Cuidados", "Logistica de reversa",
    ]


def test_bloco_sem_campo_nenhum_e_descartado():
    """O portal usa `<fieldset>` também como caixa de layout; um bloco vazio na
    saída viraria seção fantasma para o injetor tentar preencher."""
    engine = _EngineLxml(
        "<div><fieldset><legend><span class='text-primary'>Vazio</span></legend>"
        "<div>nada aqui</div></fieldset></div>"
    )

    assert extrator.ler_secao_visivel(engine) == []


def test_bloco_sem_legenda_nao_derruba_a_extracao():
    """Trocar ficha incompleta por NENHUMA ficha seria pior."""
    engine = _EngineLxml(
        "<div><fieldset><div data-container>"
        "<label data-label><span class='text-primary'>Peso</span></label>"
        "<div data-block='PMIB_DataSheetView.Block_Expression'>"
        "<span data-expression>12</span></div>"
        "</div></fieldset></div>"
    )

    assert extrator.ler_secao_visivel(engine) == [("", {"Peso": "12"})]


# ===========================================================================
# O que REALMENTE resolve a inversão do padrão B
# ===========================================================================
def test_o_discriminador_da_inversao_e_o_span_exigido_no_ramo_do_rotulo():
    r"""ACHADO DE 2026-08-17, e ele corrige a minha própria documentação.

    A especificação diz que o discriminador dos dois padrões é a presença de
    `<span>` dentro do `<label>`, e cita os dois lados:
    `label[@data-label]/span` -> rótulo, `label[@data-label]` sem span -> valor.
    A primeira metade é load-bearing; a segunda (`[not(span)]` em
    `XPATH_VIEW_OPCAO_MARCADA`) **não é**: sabotá-la não quebra teste nenhum
    contra o HTML real, porque o ramo do rótulo já exige `//span` e o label da
    opção marcada não tem nenhum.

    Tentei escrever markup hipotético em que a guarda fosse necessária (um
    label COM span dentro de um bloco de checkbox marcado) e o resultado foi o
    oposto do esperado: **com** a guarda o campo perde o valor; **sem** ela, o
    par sai certo e sobra um campo de lixo. A guarda ficou -- é inerte na tela
    real e o custo é zero -- mas ninguém deve contar com ela: quem impede a
    inversão é a exigência de `<span>` no ramo do RÓTULO, e é isso que este
    teste prende.
    """
    engine = _EngineLxml()
    ramo_rotulo = ".//label[@data-label]//span"

    # No bloco de Volume (padrão A) o ramo casa os três rótulos...
    assert len(engine._nos(f"(//fieldset)[1]{ramo_rotulo[1:]}")) == 3
    # ...e no bloco de opções marcadas (padrão B), NENHUM. É aqui que a
    # inversão morre: os labels do padrão B não entram como rótulo.
    assert len(engine._nos(f"(//fieldset)[2]{ramo_rotulo[1:]}")) == 0


# ===========================================================================
# Fabricante x fornecedor — HTML real da seção em EDIÇÃO (2026-08-17)
# ===========================================================================
# Colado pelo usuário depois que o robô escreveu na linha da GE. É o markup que
# decide se a referência vai para a linha certa.
_HTML_FABRICANTE = """
<div id="secao">
  <div data-container="" class="linha-do-fornecedor">
    <div class="vscomp-toggle-button">
      <div class="vscomp-value" data-tooltip="Selecione um fornecedor">Selecione um fornecedor</div>
      <div class="vscomp-arrow"></div>
    </div>
    <div data-container="" class="margin-left-base ThemeGrid_Width9">
      <label data-label=""><span class="text-primary margin-right-s">Refer&#234;ncia</span></label>
      <span class="input-text">
        <input data-input="" class="form-control OSFillParent" required="" type="text"
               maxlength="100" value="" id="b10-b11-b2-Input_TextVar">
      </span>
    </div>
    <div data-container="" class="margin-left-base ThemeGrid_Width2">
      <div data-block="Content.Tooltip" class="OSBlockWidget" id="b10-b11-b2-$b6">
        <div data-container="" class="text-align-center">
          <a data-link="" href="#"><i data-icon="" class="icon fa fa-plus-circle fa-2x"></i></a>
        </div>
      </div>
    </div>
  </div>

  <div data-container="" class="linha-do-fabricante">
    <div class="vscomp-toggle-button">
      <div class="vscomp-value" data-tooltip="Selecione um fabricante">Selecione um fabricante</div>
      <div class="vscomp-arrow"></div>
      <div class="vscomp-clear-button toggle-button-child" data-tooltip="Clear">
        <i class="vscomp-clear-icon"></i>
      </div>
    </div>
    <div class="vscomp-search-container">
      <label for="vscomp-search-input-4614" class="vscomp-search-label">Search</label>
      <input type="text" class="vscomp-search-input"
             placeholder="Pesquisar um fabricante " id="vscomp-search-input-4614">
      <span class="vscomp-search-clear">&#215;</span>
    </div>
    <div role="option" aria-selected="false" id="vscomp-option-4614-2"
         class="vscomp-option focused" data-value="7" data-index="2">
      <span class="vscomp-option-text" data-tooltip="3D SYSTEMS">3D SYSTEMS</span>
    </div>
    <div data-container="" class="margin-left-base ThemeGrid_Width9">
      <label data-label=""><span class="text-primary margin-right-s">Refer&#234;ncia</span></label>
      <span class="input-text">
        <input data-input="" class="form-control OSFillParent" required="" type="text"
               maxlength="100" value="" id="b10-b11-b4-Input_TextVar">
      </span>
    </div>
    <div data-container="" class="margin-left-base ThemeGrid_Width2">
      <div data-block="Content.Tooltip" class="OSBlockWidget" id="b10-b11-b4-$b6">
        <div data-container="" class="text-align-center">
          <a data-link="" href="#"><i data-icon="" class="icon fa fa-plus-circle fa-2x"></i></a>
        </div>
      </div>
    </div>
  </div>
</div>
"""


def _secao():
    return _EngineLxml(_HTML_FABRICANTE)


def test_o_placeholder_separa_o_combo_do_fabricante_do_de_fornecedor():
    """Os dois combos são `.vscomp-toggle-button` idênticos em classe. O que os
    distingue é o `data-tooltip` do `.vscomp-value`, que NOMEIA o campo."""
    engine = _secao()
    todos = sel.XPATH_FABRICANTE_TOGGLE
    so_fabricante = sel.XPATH_COMBO_POR_PLACEHOLDER.format(texto="'fabricante'")

    assert engine.contar(todos) == 2
    assert engine.contar(so_fabricante) == 1
    assert "fabricante" in engine.texto(f"({so_fabricante})[1]")


def test_a_caixa_de_busca_tambem_se_identifica_pelo_placeholder():
    """`placeholder="Pesquisar um fabricante "` -- com espaço no fim, daí
    `contains` em vez de igualdade."""
    engine = _secao()
    seletor = sel.XPATH_BUSCA_POR_PLACEHOLDER.format(texto="'fabricante'")

    assert engine.contar(seletor) == 1


def test_ha_DOIS_campos_de_referencia_e_o_generico_pega_o_da_GE():
    """CONTRAPROVA DO DEFEITO DA 1ª SESSÃO: sem âncora, o XPath devolve o
    primeiro em ordem de documento -- que é o do FORNECEDOR."""
    engine = _secao()

    assert engine.contar(sel.XPATH_REFERENCIA_INPUT) == 2
    primeiro = engine._nos(f"({sel.XPATH_REFERENCIA_INPUT})[1]")[0]
    assert primeiro.get("id") == "b10-b11-b2-Input_TextVar"  # a linha do fornecedor


def test_com_o_id_do_campo_a_escrita_vai_para_a_linha_certa():
    engine = _secao()
    seletor = sel.XPATH_POR_ID.format(id="'b10-b11-b4-Input_TextVar'")

    nos = engine._nos(seletor)

    assert len(nos) == 1 and nos[0].get("id") == "b10-b11-b4-Input_TextVar"


def test_o_mais_da_mesma_linha_sai_do_prefixo_do_bloco():
    """`b10-b11-b4-Input_TextVar` e `b10-b11-b4-$b6` compartilham o caminho do
    bloco. É o que amarra o "+" ao campo sem depender da estrutura de `<div>`
    em volta, que não conhecemos."""
    engine = _secao()
    seletor = sel.XPATH_ADICIONAR_DO_BLOCO.format(prefixo="'b10-b11-b4-'")

    nos = engine._nos(seletor)

    assert len(nos) == 1
    # e o "+" da OUTRA linha existe, mas não foi casado
    assert engine.contar("//a[.//i[contains(@class, 'fa-plus-circle')]]") == 2


def test_a_opcao_do_combo_casa_pelo_data_tooltip():
    engine = _secao()
    seletor = sel.XPATH_FABRICANTE_OPCAO.format(texto="'3D SYSTEMS'")

    assert engine.contar(seletor) == 1
