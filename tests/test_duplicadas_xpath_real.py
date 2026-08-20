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
from sigft.core.rpa.portal import PMIBPortal
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
  <!-- ⚠️ LINHA HIPOTÉTICA: o usuário nunca mostrou um combo de fornecedor.
       Ela fica porque os testes de "não escolher o combo errado" precisam de
       um segundo combo na tela, e essa propriedade tem de valer exista ela ou
       não. Está marcada para ninguém a confundir com markup observado. -->
  <div data-container="" class="linha-do-fornecedor-HIPOTETICA">
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

  <div data-container="" class="linha-da-ge-vernova">
    <div data-container="" class="margin-left-base ThemeGrid_Width9">
      <label data-label=""><span class="text-primary margin-right-s">Refer&#234;ncia</span></label>
      <div data-block="Content.Tooltip" class="OSBlockWidget" id="b10-b11-b6-$b4">
        <div data-container="" class="osui-tooltip osui-tooltip--is-hover">
          <div class="osui-tooltip__content" role="button">
            <i data-icon="" class="icon icon-info-yellow fa fa-info-circle fa-1x"></i>
          </div>
        </div>
      </div>
      <span class="input-text">
        <input data-input="" class="form-control OSFillParent" required="" type="text"
               maxlength="100" value="" id="b10-b11-b6-Input_TextVar">
      </span>
    </div>
    <div data-container="" class="margin-left-base ThemeGrid_Width2">
      <div data-block="Content.Tooltip" class="OSBlockWidget" id="b10-b11-b6-$b6">
        <div data-container="" class="osui-tooltip osui-tooltip--is-hover">
          <div class="osui-tooltip__content" role="button">
            <div data-container="" class="text-align-center">
              <a data-link="" href="#"><i data-icon="" class="icon fa fa-plus-circle fa-2x"></i></a>
            </div>
          </div>
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


def test_ha_TRES_campos_de_referencia_e_o_generico_pega_o_primeiro():
    """CONTRAPROVA DO DEFEITO DA 1ª SESSÃO: sem âncora, o XPath devolve o
    primeiro em ordem de documento -- que NÃO é o do fabricante."""
    engine = _secao()

    assert engine.contar(sel.XPATH_REFERENCIA_INPUT) == 3
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
    # e os "+" das OUTRAS linhas existem, mas não foram casados
    assert engine.contar("//a[.//i[contains(@class, 'fa-plus-circle')]]") == 3


def test_a_opcao_do_combo_casa_pelo_data_tooltip():
    engine = _secao()
    seletor = sel.XPATH_FABRICANTE_OPCAO.format(texto="'3D SYSTEMS'")

    assert engine.contar(seletor) == 1


# ===========================================================================
# A referência da GE Vernova — o terceiro campo
# ===========================================================================
# *"Quando a coluna CÓDIGO CMI ou CÓDIGO GE estiver preenchida no _STATUS_PMIB
# vale a pena preencher esse campo, com o valor da coluna."*

def test_o_campo_da_GE_se_distingue_pelo_icone_de_informacao():
    """Os três campos de Referência têm o MESMO rótulo e a mesma classe. O que
    separa o da GE Vernova é o ícone de informação entre o rótulo e o campo --
    estrutural, e melhor do que "o terceiro", que muda se o portal reordenar."""
    engine = _secao()

    assert engine.contar(sel.XPATH_REFERENCIA_INPUT) == 3
    assert engine.contar(sel.XPATH_REFERENCIA_GE_INPUT) == 1

    nos = engine._nos(sel.XPATH_REFERENCIA_GE_INPUT)
    assert nos[0].get("id") == "b10-b11-b6-Input_TextVar"


def test_os_campos_sem_o_icone_sao_os_outros_dois():
    """É essa a lista que o "antes e depois" do fabricante compara. Se o campo
    da GE entrasse nela, ele apareceria como "nascido" numa tela em que fosse
    renderizado depois -- e a referência do fabricante iria para a linha da GE,
    que é exatamente o defeito que estamos consertando."""
    engine = _secao()

    ids = [n.get("id") for n in engine._nos(sel.XPATH_REFERENCIA_INPUT_SEM_GE)]

    assert ids == ["b10-b11-b2-Input_TextVar", "b10-b11-b4-Input_TextVar"]


def test_o_mais_da_GE_sai_do_prefixo_dela_e_nao_do_fabricante():
    engine = _secao()

    da_ge = engine._nos(sel.XPATH_ADICIONAR_DO_BLOCO.format(prefixo="'b10-b11-b6-'"))
    do_fab = engine._nos(sel.XPATH_ADICIONAR_DO_BLOCO.format(prefixo="'b10-b11-b4-'"))

    assert len(da_ge) == 1 and len(do_fab) == 1
    assert da_ge[0] is not do_fab[0]
    # e existem TRÊS "+" na tela: sem a âncora, qualquer um seria clicado
    assert engine.contar("//a[.//i[contains(@class, 'fa-plus-circle')]]") == 3


# ===========================================================================
# Navegação e tabelas — HTML colado pelo usuário em 2026-08-18
# ===========================================================================
# Foi o levantamento que destravou o CP 6.4: até aqui o extrator só sabia ler
# a seção que já estivesse aberta. Vem com uma correção de modelo junto -- a
# seção de Fabricantes/Fornecedores não é bloco de rótulo→valor, são duas
# TABELAS, e a varredura de rótulo→valor não a enxerga.
_HTML_NAVEGACAO = """
<div id="ficha">
  <div class="osui-tabs__header">
    <button data-advancedhtml="" class="osui-tabs__header-item" name="0.4z9qbl6cvoj"
            data-tab="1" role="tab" tabindex="-1" aria-selected="true" aria-controls="b12-$b12">
      <div class="display-contents ph" id="b12-b5-Title">Fabricantes e fornecedores</div>
    </button>
    <button data-advancedhtml="" class="osui-tabs__header-item" name="0.pnxxwyjy3d"
            data-tab="3" role="tab" tabindex="-1" aria-selected="false" aria-controls="b12-$b17">
      <div class="display-contents ph" id="b12-b7-Title">Documentos</div>
    </button>
    <button data-advancedhtml="" class="osui-tabs__header-item" name="0.1b5s62bmf06"
            data-tab="4" role="tab" tabindex="-1" aria-selected="false" aria-controls="b12-$b19">
      <div class="display-contents ph" id="b12-b8-Title">Condições</div>
    </button>
  </div>

  <div class="subabas">
    <div data-container="" class="dummy-active OSInline"
         style="text-align: center; cursor: pointer; width: 20%; padding: 8px;">Armazenamento e transporte</div>
    <div data-container="" class="OSInline"
         style="text-align: center; cursor: pointer; width: 20%; padding: 8px;">Manutenção e descarte</div>
  </div>

  <div data-container="" class="full-fieldset" id="b12-b13-ManufacturerAndProvider"><div data-container="">
    <table class="table" role="grid">
      <thead><tr class="table-header"><th class="" tabindex="0">Nome do Fabricante</th>
      <th class="half-width" tabindex="0">Referência</th></tr></thead>
      <tbody>
        <tr class="table-row">
          <td data-header="Nome do Fabricante"><span data-expression="" class="description-wrap">ENERSYS</span></td>
          <td data-header="Referência"><span data-expression="" class="description-wrap">E24-256-10</span></td>
        </tr>
        <tr class="table-row">
          <td data-header="Nome do Fabricante"><span data-expression="" class="description-wrap">SASSI</span></td>
          <td data-header="Referência"><span data-expression="" class="description-wrap">DGA 0-300V DC</span></td>
        </tr>
      </tbody>
    </table>
    <div data-block="Navigation.Pagination" class="OSBlockWidget" id="b12-b13-$b1">
      <div data-container="" class="pagination-counter OSInline" id="b12-b13-b1-PaginationRecords">
        <span data-expression="" data-testid="Pagination.RecordNumberFrom">1</span>
        <span data-expression="" data-testid="Pagination.RecordsNumber">2</span>
      </div>
    </div>
  </div></div>

  <div data-container="" class="full-fieldset" id="b12-b14-ManufacturerAndProvider"><div data-container="">
    <table class="table" role="grid">
      <thead><tr class="table-header"><th class="" tabindex="0">Nome do Fornecedor</th>
      <th class="half-width" tabindex="0">Referência</th></tr></thead>
      <tbody>
        <tr class="table-row">
          <td data-header="Nome do Fornecedor"><span data-expression="" class="description-wrap">GE ENERGIAS RENOVAVEIS LTDA</span></td>
          <td data-header="Referência"><span data-expression="" class="description-wrap">08934120BTM99-064F</span></td>
        </tr>
      </tbody>
    </table>
  </div></div>
</div>
"""


@pytest.fixture(scope="module")
def nav():
    return etree.HTML(_HTML_NAVEGACAO)


def _lit(texto):
    return f"'{texto}'"


# --- as abas da ficha -------------------------------------------------------

@pytest.mark.parametrize("rotulo", [
    "Fabricantes e fornecedores", "Documentos", "Condições",
])
def test_cada_aba_da_ficha_e_achada_pelo_texto(nav, rotulo):
    achados = nav.xpath(sel.XPATH_ABA_DA_FICHA.format(texto=_lit(rotulo)))

    assert len(achados) == 1, f"esperava 1 aba {rotulo!r}, achei {len(achados)}"


def test_a_aba_ativa_e_distinguida_por_aria_selected(nav):
    """Sem esta conferência, um clique que não pegou faria o extrator ler a
    seção ANTERIOR e devolver dados plausíveis da seção errada."""
    ativa = nav.xpath(sel.XPATH_ABA_DA_FICHA_ATIVA.format(
        texto=_lit("Fabricantes e fornecedores")))
    inativa = nav.xpath(sel.XPATH_ABA_DA_FICHA_ATIVA.format(texto=_lit("Condições")))

    assert len(ativa) == 1
    assert inativa == []


def test_os_atributos_gerados_das_abas_nao_entram_no_seletor():
    """`name="0.4z9qbl6cvoj"` é aleatório, `aria-controls="b12-$b12"` é id
    gerado, e `data-tab` é ORDINAL -- posição é o que muda quando o portal
    reordena a tela (§6.5c decidiu contra posição, e vale igual aqui)."""
    for seletor in (sel.XPATH_ABA_DA_FICHA, sel.XPATH_ABA_DA_FICHA_ATIVA):
        assert "@name" not in seletor
        assert "aria-controls" not in seletor
        assert "data-tab" not in seletor


# --- as sub-abas de Condições ----------------------------------------------

def test_as_subabas_de_condicoes_nao_sao_role_tab(nav):
    """São `<div class="OSInline">` com `cursor: pointer`. Supor que fossem o
    mesmo componente das abas de cima era plausível -- e errado. Este teste
    existe para que a suposição não volte."""
    como_aba = nav.xpath(sel.XPATH_ABA_DA_FICHA.format(
        texto=_lit("Armazenamento e transporte")))

    assert como_aba == [], "a sub-aba casou como se fosse aba de cima"


@pytest.mark.parametrize("rotulo", ["Armazenamento e transporte", "Manutenção e descarte"])
def test_cada_subaba_de_condicoes_e_achada_pelo_texto(nav, rotulo):
    assert len(nav.xpath(sel.XPATH_SUBABA_CONDICOES.format(texto=_lit(rotulo)))) == 1


def test_a_subaba_aberta_e_a_que_tem_dummy_active(nav):
    """As três sub-abas ficam TODAS no DOM. Sem checar qual está ativa, o
    extrator lê a primeira e acha que leu a que pediu."""
    aberta = sel.XPATH_SUBABA_CONDICOES_ATIVA.format(texto=_lit("Armazenamento e transporte"))
    fechada = sel.XPATH_SUBABA_CONDICOES_ATIVA.format(texto=_lit("Manutenção e descarte"))

    assert len(nav.xpath(aberta)) == 1
    assert nav.xpath(fechada) == []


# --- as duas tabelas --------------------------------------------------------

def test_a_varredura_de_rotulo_e_valor_NAO_enxerga_estas_tabelas(nav):
    """O achado que corrige o modelo do extrator.

    `XPATH_VIEW_VALOR` exige o ancestral `PMIB_DataSheetView.Block_Expression`,
    e as células da tabela não o têm. Ou seja, `achar_fabricante` e
    `achar_fornecedor` lendo de `blocos` devolvem VAZIO para esta ficha -- a
    seção precisa de leitor próprio, e é por isso que ele existe.
    """
    assert nav.xpath(sel.XPATH_VIEW_VALOR) == []


def test_a_tabela_do_fabricante_traz_as_DUAS_linhas(nav):
    """"Nesse caso ele tem 2 fornecedores (a gente comprou de um que comprou
    do fabricante)" -- ENERSYS fabrica, SASSI revende. Ler só a primeira
    perderia a segunda sem avisar."""
    linhas = nav.xpath(sel.XPATH_LINHAS_DA_TABELA_DE.format(
        coluna=_lit(sel.COLUNA_NOME_FABRICANTE)))

    assert len(linhas) == 2


def test_a_tabela_do_fornecedor_nao_arrasta_as_linhas_do_fabricante(nav):
    """Os dois contêineres têm o MESMO sufixo de id
    (`-ManufacturerAndProvider`); quem separa é o `@data-header`. Se o
    `ancestor::table[1]` perdesse o `[1]`, as duas tabelas viriam juntas."""
    linhas = nav.xpath(sel.XPATH_LINHAS_DA_TABELA_DE.format(
        coluna=_lit(sel.COLUNA_NOME_FORNECEDOR)))

    assert len(linhas) == 1


def test_os_valores_das_celulas_saem_certos(nav):
    def _ler(coluna_tabela, indice, coluna_celula):
        base = f"({sel.XPATH_LINHAS_DA_TABELA_DE.format(coluna=_lit(coluna_tabela))})[{indice}]"
        return nav.xpath(base + sel.XPATH_REL_CELULA.format(coluna=_lit(coluna_celula)))[0].text

    assert _ler(sel.COLUNA_NOME_FABRICANTE, 1, sel.COLUNA_NOME_FABRICANTE) == "ENERSYS"
    assert _ler(sel.COLUNA_NOME_FABRICANTE, 1, sel.COLUNA_REFERENCIA) == "E24-256-10"
    assert _ler(sel.COLUNA_NOME_FABRICANTE, 2, sel.COLUNA_NOME_FABRICANTE) == "SASSI"
    assert _ler(sel.COLUNA_NOME_FABRICANTE, 2, sel.COLUNA_REFERENCIA) == "DGA 0-300V DC"
    assert _ler(sel.COLUNA_NOME_FORNECEDOR, 1, sel.COLUNA_NOME_FORNECEDOR) == "GE ENERGIAS RENOVAVEIS LTDA"
    assert _ler(sel.COLUNA_NOME_FORNECEDOR, 1, sel.COLUNA_REFERENCIA) == "08934120BTM99-064F"


def test_o_contador_de_paginacao_nao_vira_valor_de_celula(nav):
    """Mesma armadilha do badge de anexos (§8.2): o bloco de paginação também
    tem `<span data-expression>` com número dentro. Aqui o que separa é a
    exigência de `td[@data-header]` -- o contador não está numa célula."""
    linhas = nav.xpath(sel.XPATH_LINHAS_DA_TABELA_DE.format(
        coluna=_lit(sel.COLUNA_NOME_FABRICANTE)))
    textos = [c.text for l in linhas
              for c in l.xpath(".//td[@data-header]//span[@data-expression]")]

    assert "1" not in textos and "2" not in textos, f"contador vazou: {textos}"


# ===========================================================================
# O extrator rodando de VERDADE sobre o HTML real
# ===========================================================================
# Os testes acima provam os seletores; estes provam o CÓDIGO que os usa, com
# um engine mínimo por cima do `lxml`. É a diferença entre "o XPath casa" e
# "a função devolve o que o usuário vê na tela".

# ⚠️ REUSA `_EngineLxml` (definida no topo deste arquivo). A primeira versão
# deste bloco declarava uma classe com o MESMO NOME, que sobrescrevia a de
# cima -- e derrubou 25 testes que passavam, todos com `TypeError` no
# construtor. O `pytest` roda o arquivo inteiro num namespace só; nome
# repetido aqui não é estilo, é bug.
class _PortalLxml:
    # Emprestados do PMIBPortal REAL: os dois só usam `self.engine`, então
    # ligá-los aqui testa a implementação de verdade em vez de uma cópia
    # que envelhece sozinha. São o conserto do travamento de 2026-08-20 --
    # ler o que pode não existir sem pagar o timeout do motor.
    texto_se_existir = PMIBPortal.texto_se_existir
    valor_se_existir = PMIBPortal.valor_se_existir

    """Portal mínimo sobre `_EngineLxml` -- só o que a navegação usa."""

    def __init__(self, html):
        self.engine = _EngineLxml(html)
        self.cliques = []

    def safe_click(self, seletor):
        self.cliques.append(seletor)


@pytest.fixture
def portal_real():
    return _PortalLxml(_HTML_NAVEGACAO)


def test_ler_fabricantes_e_fornecedores_devolve_o_que_esta_na_tela(portal_real):
    """O teste que fecha o CP 6.4 do lado da leitura: as duas tabelas, todas
    as linhas, com a referência de cada uma."""
    tabelas = extrator.ler_fabricantes_e_fornecedores(portal_real)

    assert tabelas["fabricantes"] == [
        ("ENERSYS", "E24-256-10"),
        ("SASSI", "DGA 0-300V DC"),
    ]
    assert tabelas["fornecedores"] == [
        ("GE ENERGIAS RENOVAVEIS LTDA", "08934120BTM99-064F"),
    ]


def test_o_fabricante_nao_arrasta_a_linha_da_GE(portal_real):
    """Os dois contêineres têm o mesmo sufixo de id; se o `ancestor::table[1]`
    perdesse o `[1]`, a GE apareceria como fabricante."""
    tabelas = extrator.ler_fabricantes_e_fornecedores(portal_real)
    nomes = [n for n, _r in tabelas["fabricantes"]]

    assert "GE ENERGIAS RENOVAVEIS LTDA" not in nomes


def test_abrir_secao_confirma_pelo_aria_selected(portal_real):
    """No HTML levantado, "Fabricantes e fornecedores" já está ativa."""
    assert extrator.abrir_secao(portal_real, sel.ABA_FABRICANTES_E_FORNECEDORES) is True


def test_abrir_secao_RECUSA_quando_o_portal_nao_marca_a_aba(portal_real):
    """Clicar em "Condições" neste HTML estático não muda `aria-selected` --
    é exatamente o cenário de um clique que não pegou. O extrator tem de
    recusar, e não ler a seção anterior achando que é esta."""
    linhas = []

    assert extrator.abrir_secao(portal_real, sel.ABA_CONDICOES, linhas.append) is False
    assert any("não marcou a aba como ativa" in l for l in linhas)


def test_secao_inexistente_nao_e_confundida_com_clique_que_falhou(portal_real):
    linhas = []

    assert extrator.abrir_secao(portal_real, "Aba Que Nao Existe", linhas.append) is False
    assert any("não existe nesta tela" in l for l in linhas)


def test_abrir_subaba_de_condicoes_confirma_pela_classe_dummy_active(portal_real):
    assert extrator.abrir_subaba_de_condicoes(
        portal_real, "Armazenamento e transporte") is True


def test_subaba_que_nao_fica_ativa_e_recusada(portal_real):
    """As três sub-abas ficam TODAS no DOM: sem a checagem de `dummy-active`,
    o extrator leria a aberta e diria que leu a pedida."""
    linhas = []

    ok = extrator.abrir_subaba_de_condicoes(
        portal_real, "Manutenção e descarte", linhas.append)

    assert ok is False
    assert any("dummy-active" in l for l in linhas)


def test_a_secao_nao_lida_devolve_vazio_e_nao_levanta(portal_real):
    """Aba que não abre não pode derrubar a ficha -- vira "não sei", e quem
    chama decide. Nunca "não tem"."""
    portal_vazio = _PortalLxml("<div id='ficha'></div>")

    tabelas = extrator.ler_fabricantes_e_fornecedores(portal_vazio)

    assert tabelas == {"fabricantes": [], "fornecedores": []}


# ===========================================================================
# Documentos e Condições — HTML colado pelo usuário em 2026-08-18 (2ª rodada)
# ===========================================================================
# A descrição do documento vem dentro de um TOOLTIP -- terceiro padrão de
# aninhamento do valor, depois do bloco de leitura (§8) e da célula rasa da
# tabela (§13).
_HTML_DOCUMENTOS_EDICAO = """
<div id="dialogo">
  <table class="table" role="grid">
    <tbody>
      <tr class="table-row">
        <td data-header="Selecionar">
          <div data-container="" class="display-flex justify-content-center" style="text-align: right;">
            <span><input data-checkbox="" class="checkbox" type="checkbox"
                         id="b10-b15-b19-l1_0-227_0-Checkbox1"></span>
          </div>
        </td>
        <td data-header="Descrição">
          <div data-block="Content.Tooltip" class="OSBlockWidget" id="b10-b15-b19-l1_0-227_0-$b6">
            <div data-container="" class="osui-tooltip osui-tooltip--is-hover" name="0.2r2d7ttp763"
                 id="b10-b15-b19-l1_0-227_0-b6-TooltipWrapper">
              <div class="osui-tooltip__content" id="b10-b15-b19-l1_0-227_0-b6-Content"
                   role="button" aria-describedby="b10-b15-b19-l1_0-227_0-b6-Tooltip" tabindex="0">
                <span data-expression="">1188 web replaced</span>
              </div></div></div>
        </td>
      </tr>
      <tr class="table-row">
        <td data-header="Selecionar">
          <div data-container="" class="display-flex justify-content-center">
            <span><input data-checkbox="" class="checkbox" type="checkbox"
                         id="b10-b15-b19-l1_0-228_0-Checkbox1"></span>
          </div>
        </td>
        <td data-header="Descrição">
          <div data-block="Content.Tooltip" class="OSBlockWidget">
            <div class="osui-tooltip"><div class="osui-tooltip__content">
              <span data-expression="">1188 web replaced v2</span>
            </div></div></div>
        </td>
      </tr>
    </tbody>
  </table>
  <button data-button="" class="btn btn-primary" type="button">ASSOCIAR</button>
</div>
"""

_HTML_DOCUMENTOS_VISUALIZACAO = """
<div id="ficha">
  <table class="table" role="grid"><tbody><tr class="table-row">
    <td data-header="Descrição">
      <div data-block="Content.Tooltip" class="OSBlockWidget" id="b12-b18-l1_0-452_0-$b2">
        <div data-container="" class="osui-tooltip osui-tooltip--is-hover" name="0.fucvq6a3y4"
             id="b12-b18-l1_0-452_0-b2-TooltipWrapper">
          <div class="osui-tooltip__content" id="b12-b18-l1_0-452_0-b2-Content"
               role="button" aria-describedby="b12-b18-l1_0-452_0-b2-Tooltip" tabindex="0">
            <span data-expression="">4500063671.1469 e 4500063671.1470</span>
          </div></div></div>
    </td>
  </tr></tbody></table>
</div>
"""

# Captura NOVA do mesmo bloco "Volume (cm3)" que a §8 já cobria -- com ids
# diferentes e `class="OSFillParent"` no label. Serve de regressão: prova que
# o leitor de Condições continua valendo numa tela recapturada, e não só no
# markup que existia quando ele foi escrito.
_HTML_CONDICOES_RECAPTURA = """
<fieldset data-advancedhtml=""><legend data-advancedhtml=""><div id="b12-b20-b1-b2-Legend">
<span class="text-primary font-size-base">Volume (cm3)</span></div></legend>
<div id="b12-b20-b1-b2-Content"><div data-container="" id="b12-b20-b1-Volume">
<div data-container="" class="margin-top-s">
<div data-container=""><label data-label="" class="OSFillParent"><span class="text-primary">Comprimento da embalagem unitária</span></label>
<div data-container="" class="margin-top-s"><div data-block="PMIB_DataSheetView.Block_Expression" class="OSBlockWidget" id="b12-b20-b1-$b3"><span data-expression="">6</span></div></div></div>
<div data-container=""><label data-label="" class="OSFillParent"><span class="text-primary">Largura da embalagem unitária</span></label>
<div data-container="" class="margin-top-s"><div data-block="PMIB_DataSheetView.Block_Expression" class="OSBlockWidget" id="b12-b20-b1-$b4"><span data-expression="">6</span></div></div></div>
<div data-container=""><label data-label="" class="OSFillParent"><span class="text-primary">Altura da embalagem unitária</span></label>
<div data-container="" class="margin-top-s"><div data-block="PMIB_DataSheetView.Block_Expression" class="OSBlockWidget" id="b12-b20-b1-$b5"><span data-expression="">5</span></div></div></div>
</div></div></div></fieldset>
"""


# --- documentos, modo de edição --------------------------------------------

def test_a_linha_do_documento_e_achada_pela_descricao_exata():
    arvore = etree.HTML(_HTML_DOCUMENTOS_EDICAO)

    linhas = arvore.xpath(sel.XPATH_DOCUMENTO_LINHA_POR_DESCRICAO.format(
        texto=_lit("1188 web replaced")))

    assert len(linhas) == 1, "a descrição exata tem de casar UMA linha"


def test_descricao_parecida_nao_arrasta_a_linha_errada():
    """"1188 web replaced" x "1188 web replaced v2": o casamento por SUBSTRING
    de `XPATH_DOCUMENTOS_LINHA` pegaria as duas, e associar o documento errado
    não dá sintoma -- o diálogo fecha igual."""
    arvore = etree.HTML(_HTML_DOCUMENTOS_EDICAO)

    exato = arvore.xpath(sel.XPATH_DOCUMENTO_LINHA_POR_DESCRICAO.format(
        texto=_lit("1188 web replaced")))
    por_substring = arvore.xpath(sel.XPATH_DOCUMENTOS_LINHA.format(
        texto=_lit("1188 web replaced")))

    assert len(exato) == 1
    assert len(por_substring) == 2, (
        "se o seletor antigo deixar de ser ambíguo, esta nota pode sair"
    )


def test_o_checkbox_sai_da_linha_ja_escolhida():
    arvore = etree.HTML(_HTML_DOCUMENTOS_EDICAO)
    linha = arvore.xpath(sel.XPATH_DOCUMENTO_LINHA_POR_DESCRICAO.format(
        texto=_lit("1188 web replaced")))[0]

    pelo_cabecalho = linha.xpath(sel.XPATH_DOCUMENTOS_CHECKBOX_DA_LINHA)
    semantico = linha.xpath(sel.XPATH_DOCUMENTO_CHECKBOX_SEMANTICO)
    qualquer = linha.xpath(sel.XPATH_DOCUMENTO_CHECKBOX_QUALQUER)

    assert len(pelo_cabecalho) == 1, "a âncora de §6.5 continua valendo"
    assert len(semantico) == 1
    assert len(qualquer) == 1
    assert pelo_cabecalho[0] is semantico[0] is qualquer[0], "os três acham o MESMO input"


def test_o_id_do_checkbox_nao_entra_em_seletor_nenhum():
    """`b10-b15-b19-l1_0-227_0-Checkbox1` traz `-l1_0-`, que é índice de linha
    e muda a cada busca -- já catalogado."""
    assert any("-l1_0-" in f for f in sel.IDS_GERADOS_NAO_USAR)
    for nome, valor in vars(sel).items():
        if nome.startswith("XPATH") and isinstance(valor, str):
            assert "-l1_0-" not in valor, nome


def test_o_botao_associar_e_achado_pelo_texto():
    arvore = etree.HTML(_HTML_DOCUMENTOS_EDICAO)

    assert len(arvore.xpath(sel.XPATH_DOCUMENTOS_ASSOCIAR)) == 1


# --- documentos, modo de visualização --------------------------------------

def test_a_varredura_de_rotulo_e_valor_TAMBEM_nao_enxerga_documentos():
    """Terceira seção que o padrão de §8 não cobre (depois de Fabricantes e
    Fornecedores). O bloco aqui é `Content.Tooltip`, não
    `PMIB_DataSheetView.Block_Expression`."""
    arvore = etree.HTML(_HTML_DOCUMENTOS_VISUALIZACAO)

    assert arvore.xpath(sel.XPATH_VIEW_VALOR) == []


def test_a_MESMA_celula_le_o_valor_raso_e_o_aninhado_em_tooltip():
    """🎯 O `//span` de `XPATH_REL_CELULA` é o que faz um seletor só servir
    para os dois. `/td[…]/span` funcionaria no fabricante (raso) e falharia no
    documento (dentro de 3 divs) -- em silêncio. Este teste existe para o `//`
    não virar `/` numa "simplificação"."""
    celula = sel.XPATH_REL_CELULA.format(coluna=_lit(sel.COLUNA_DESCRICAO))

    doc = etree.HTML(_HTML_DOCUMENTOS_VISUALIZACAO)
    aninhado = doc.xpath("//tr" + celula)
    assert [n.text for n in aninhado] == ["4500063671.1469 e 4500063671.1470"]

    raso = etree.HTML(_HTML_NAVEGACAO).xpath(
        "//tr" + sel.XPATH_REL_CELULA.format(coluna=_lit(sel.COLUNA_REFERENCIA)))
    assert "E24-256-10" in [n.text for n in raso]


# --- Condições: a recaptura não quebrou o leitor ---------------------------

def test_o_leitor_de_condicoes_continua_valendo_na_recaptura():
    """Regressão contra tela recapturada: mesmos três campos, ids diferentes,
    `class="OSFillParent"` a mais no label. Se o leitor dependesse de id ou de
    classe de layout, quebraria aqui."""
    engine = _EngineLxml(_HTML_CONDICOES_RECAPTURA)

    blocos = extrator.ler_secao_visivel(engine)

    assert blocos == [("Volume (cm3)", {
        "Comprimento da embalagem unitária": "6",
        "Largura da embalagem unitária": "6",
        "Altura da embalagem unitária": "5",
    })]
