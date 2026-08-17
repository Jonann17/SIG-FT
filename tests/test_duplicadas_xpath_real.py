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
