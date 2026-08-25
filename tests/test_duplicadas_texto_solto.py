r"""O TERCEIRO padrão da visualização — valor como texto solto.

Todo o HTML deste arquivo foi **copiado do portal em 2026-08-24**, na primeira
sessão local com o navegador ligado (ficha original `4500063671.1240`). Não há
markup inventado aqui, e a distinção importa: o que quebrou este módulo por uma
semana passava em 2700 testes escritos contra dublês.

O que estes testes protegem, em uma frase: o bloco «Proteção» tem de sair da
leitura com valor. Ele é o campo obrigatório cuja ausência fazia o portal
recusar a seção INTEIRA com "Por favor, verifique os campos" -- mensagem que
não nomeia campo nenhum e que custou sete hipóteses.
"""
import pytest

etree = pytest.importorskip("lxml.etree", reason="lxml e opcional; ver requirements-dev")

from sigft.core.rpa import seletores_duplicada as sel  # noqa: E402
from sigft.services import duplicadas_condicoes as condicoes  # noqa: E402
from sigft.services import duplicadas_extrator as extrator  # noqa: E402


# HTML REAL, do "inspecionar elemento" da ficha 4500063671.1240.
_HTML = """
<div id="ficha">
  <fieldset data-advancedhtml="">
    <legend data-advancedhtml=""><div id="b12-b20-b1-b6-Legend">
      <span class="text-primary font-size-base">Temperatura, Umidade e Clima</span>
    </div></legend>
    <div id="b12-b20-b1-b6-Content">
      <div data-container="" class="margin-top-s">
        <div data-container="">
          <span class="text-primary font-size-base">Necessidade de controle de temperatura e umidade</span>
        </div>Sem necessidade</div>
    </div>
  </fieldset>

  <fieldset data-advancedhtml="">
    <legend data-advancedhtml=""><div id="b12-b20-b1-b14-Legend">
      <span class="text-primary font-size-base">Proteção</span>
    </div></legend>
    <div id="b12-b20-b1-b14-Content">
      <div data-container="" class="margin-top-s">
        <div data-container="" style="margin-bottom: var(--space-s);">Sem necessidade</div>
      </div>
    </div>
  </fieldset>

  <fieldset data-advancedhtml="">
    <legend data-advancedhtml=""><div id="b12-b20-b1-b16-Legend">
      <span class="text-primary font-size-base">Armazenamento e Empilhamento Máximo</span>
    </div></legend>
    <div id="b12-b20-b1-b16-Content">
      <div data-block="Adaptive.Columns2" id="b12-b20-b1-$b17">
        <div data-container="" class="columns columns2">
          <div class="columns-item" id="b12-b20-b1-b17-Column1">
            <div data-container="" id="b12-b20-b1-StoragePosition">
              <label data-label="" class="OSFillParent"><span class="text-primary">Posição de armazenamento</span></label>
              <div data-container="" class="margin-top-s">Horizontal</div>
            </div>
          </div>
          <div class="columns-item" id="b12-b20-b1-b17-Column2">
            <div data-container="" id="b12-b20-b1-Stacking">
              <label data-label="" class="OSFillParent"><span class="text-primary">Empilhamento Máximo</span></label>
              <div data-container="" class="margin-top-s">
                <div data-block="PMIB_DataSheetView.Block_Expression" id="b12-b20-b1-$b19">
                  <span data-expression="">1</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </fieldset>

  <fieldset data-advancedhtml="">
    <legend data-advancedhtml=""><div id="b12-b20-b1-b20-Legend">
      <span class="text-primary font-size-base">Nocivos ou Outros Cuidados </span>
    </div></legend>
    <div id="b12-b20-b1-b20-Content">
      <span class="text-primary font-size-base">Nocivo</span>
      <div data-container="" class="margin-left-m margin-bottom-m">
        <div data-container="" class="margin-top-s">
          <div data-container="" class="custom">
            <span><input data-checkbox="" class="radio-button" disabled="" type="checkbox" checked="" id="b12-b20-b1-Checkbox1"></span>
            <label data-label="" class="margin-left-s">Não contém agentes nocivos</label>
          </div>
        </div>
      </div>
      <span class="text-primary font-size-base">Outros cuidados</span>
      <div data-container="" class="margin-left-m">
        <div data-container="" class="margin-top-s">
          <div data-container="" class="custom">
            <span><input data-checkbox="" class="radio-button" disabled="" type="checkbox" checked="" id="b12-b20-b1-Checkbox2"></span>
            <label data-label="" class="margin-left-s">Sem necessidade</label>
          </div>
        </div>
      </div>
    </div>
  </fieldset>

  <fieldset data-advancedhtml="">
    <legend data-advancedhtml=""><div id="b12-Legend">
      <span class="text-primary font-size-base">Volume (cm3)</span>
    </div></legend>
    <div id="b12-Content">
      <div data-container="">
        <label data-label=""><span class="text-primary">Comprimento da embalagem unitária</span></label>
        <div data-container="" class="margin-top-s">
          <div data-block="PMIB_DataSheetView.Block_Expression" id="b12-b20-b1-$b3">
            <span data-expression="">3,8</span>
          </div>
        </div>
      </div>
    </div>
  </fieldset>
</div>
"""

# Índice (1-based) de cada fieldset dentro de `_HTML`.
TEMPERATURA, PROTECAO, ARMAZENAMENTO, NOCIVOS, VOLUME = 1, 2, 3, 4, 5


class _EngineLxml:
    """Motor de mentira que avalia XPath DE VERDADE sobre `_HTML`."""

    def __init__(self, html=_HTML):
        self.arvore = etree.fromstring(html, etree.HTMLParser())

    def _nos(self, seletor):
        return self.arvore.xpath(seletor)

    def contar(self, seletor):
        return len(self._nos(seletor))

    def element_exists(self, seletor):
        return bool(self._nos(seletor))

    def texto(self, seletor):
        nos = self._nos(seletor)
        return " ".join("".join(nos[0].itertext()).split()) if nos else ""


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    """`_esperar_os_blocos_de_idioma` espera os balões renderizarem.

    Isso é necessário no portal e puro custo aqui: o DOM de teste é estático.
    Anular o `sleep` é o jeito certo -- o contrário (fazer a produção desistir
    cedo para o teste correr) já foi tentado em 2026-08-25 e quebrou a leitura
    do espanhol do Descarte.
    """
    monkeypatch.setattr(extrator.time, "sleep", lambda _s: None)


@pytest.fixture
def engine():
    return _EngineLxml()


# ===========================================================================
# 1. O bloco que travava tudo
# ===========================================================================

def test_protecao_sai_da_leitura_com_valor(engine):
    """O bloco obrigatório. Antes deste conserto saía VAZIO, e o vazio é o que
    fazia o portal recusar a seção inteira."""
    titulo, campos = extrator.ler_bloco(engine, PROTECAO)
    assert titulo == "Proteção"
    assert campos == {"Proteção": "Sem necessidade"}


def test_protecao_chega_no_checkbox_certo():
    convertido = condicoes.converter_da_visualizacao(
        [("Proteção", "Sem necessidade")])
    assert convertido == {"Armazenamento": {"Checkbox6": True}}


def test_protecao_com_mais_de_uma_marca_nao_perde_nenhuma():
    """`Checkbox6/7/8` são checkboxes: o portal aceita várias. Ficar com a
    primeira perderia as outras em silêncio."""
    convertido = condicoes.converter_da_visualizacao(
        [("Proteção", "Raios ultravioleta | Eletrostática")])
    assert convertido == {"Armazenamento": {"Checkbox7": True, "Checkbox8": True}}


def test_opcao_que_o_mapa_nao_conhece_e_DENUNCIADA_e_nao_engolida():
    mensagens = []
    convertido = condicoes.converter_da_visualizacao(
        [("Proteção", "Blindagem antimagnética")], mensagens.append)
    assert convertido == {}
    assert any("não conhece essa opção" in m for m in mensagens), mensagens


# ===========================================================================
# 2. As outras duas variantes do texto solto
# ===========================================================================

def test_posicao_de_armazenamento_e_lida_com_o_empilhamento_junto(engine):
    """Padrão C com rótulo em `label>span` e valor em `div` folha irmã.

    O `Empilhamento Máximo` no mesmo bloco é `Block_Expression` (padrão A):
    o teste vale porque prova que os dois convivem sem se atrapalhar."""
    _titulo, campos = extrator.ler_bloco(engine, ARMAZENAMENTO)
    assert campos == {
        "Posição de armazenamento": "Horizontal",
        "Empilhamento Máximo": "1",
    }


def test_temperatura_e_resgatada_do_texto_irmao(engine):
    """Variante em que o valor não tem elemento nenhum -- é nó de texto direto
    da mesma caixa do rótulo. Não há seletor de elemento que o alcance."""
    _titulo, campos = extrator.ler_bloco(engine, TEMPERATURA)
    assert campos == {
        "Necessidade de controle de temperatura e umidade": "Sem necessidade",
    }


# ===========================================================================
# 3. O que NÃO pode ter mudado
# ===========================================================================

def test_o_padrao_A_continua_igual(engine):
    _titulo, campos = extrator.ler_bloco(engine, VOLUME)
    assert campos == {"Comprimento da embalagem unitária": "3,8"}


def test_o_padrao_B_nao_inverteu_rotulo_e_valor(engine):
    _titulo, campos = extrator.ler_bloco(engine, NOCIVOS)
    assert campos == {
        "Nocivo": "Não contém agentes nocivos",
        "Outros cuidados": "Sem necessidade",
    }


def test_o_ramo_novo_nao_acrescenta_no_em_bloco_que_ja_funcionava(engine):
    """Medido também no portal: Volume, Peso, Nocivos e Transporte casam ZERO
    nós no ramo novo. É o que autoriza mexer numa varredura compartilhada."""
    for indice in (VOLUME, NOCIVOS):
        base = f"({sel.XPATH_VIEW_BLOCO})[{indice}]"
        soltos = base + sel.XPATH_VIEW_VALOR_SOLTO.lstrip(".")
        assert engine.contar(soltos) == 0


def test_a_legenda_so_vira_rotulo_quando_o_bloco_ficaria_vazio(engine):
    """A regra de resgate não pode roubar o rótulo de bloco que já tem um."""
    for indice in (VOLUME, NOCIVOS, ARMAZENAMENTO, TEMPERATURA):
        titulo, campos = extrator.ler_bloco(engine, indice)
        assert titulo not in campos, f"a legenda «{titulo}» virou campo"


# ===========================================================================
# 4. A ambiguidade que obrigou o mapa a mudar de forma
# ===========================================================================

def test_sem_necessidade_vai_para_controles_DIFERENTES_conforme_a_pergunta():
    """'Sem necessidade' responde três perguntas desta mesma tela. Um mapa
    indexado pelo VALOR marcaria o controle errado -- e rádio errado parece
    resposta certa."""
    convertido = condicoes.converter_da_visualizacao([
        ("Necessidade de controle de temperatura e umidade", "Sem necessidade"),
        ("Outros cuidados", "Sem necessidade"),
        ("Proteção", "Sem necessidade"),
    ])
    assert convertido == {"Armazenamento": {
        "RadioButton4-input": True,
        "RadioButton3-input": True,
        "Checkbox6": True,
    }}


def test_a_ficha_1240_inteira_vira_o_dicionario_que_o_portal_ACEITOU():
    """Os valores são os da ficha original 4500063671.1240 e o resultado é
    exatamente o que foi escrito na alvo 4500063671.0928 em 2026-08-24, quando
    o portal respondeu "As condições de armazenamento foram adicionadas com
    sucesso!". É o teste mais forte deste arquivo: não descreve a minha ideia
    do portal, descreve uma gravação que aconteceu."""
    convertido = condicoes.converter_da_visualizacao([
        ("Comprimento da embalagem unitária", "3,8"),
        ("Largura da embalagem unitária", "5"),
        ("Altura da embalagem unitária", "6,7"),
        ("Necessidade de controle de temperatura e umidade", "Sem necessidade"),
        ("Peso líquido", "0,04"),
        ("Peso bruto", "0,04"),
        ("Proteção", "Sem necessidade"),
        ("Posição de armazenamento", "Horizontal"),
        ("Empilhamento Máximo", "1"),
        ("Nocivo", "Não contém agentes nocivos"),
        ("Outros cuidados", "Sem necessidade"),
    ])
    assert convertido["Armazenamento"] == {
        "Input_PackingLength": "3,8",
        "Input_PackagingWidth": "5",
        "Input_PackagingHeight": "6,7",
        "RadioButton4-input": True,
        "Input_LiquidWeight": "0,04",
        "Input_GrossWeight": "0,04",
        "Checkbox6": True,
        "RadioButton7-input": True,
        "Input_Stacking": "1",
        "RadioButton1-input": True,
        "RadioButton3-input": True,
    }


# ===========================================================================
# 5. A segunda forma da tabela não pode quebrar quem a percorre
# ===========================================================================

def test_o_balao_do_espanhol_ignora_grupo_de_opcao():
    """`espanhol_dos_baloes` varre a MESMA tabela e assumia destino string.

    Quando a tabela ganhou a forma `{valor: sufixo}`, a leitura inteira passou
    a morrer com `AttributeError: 'dict' object has no attribute 'endswith'`
    -- e morria DEPOIS de ler a ficha toda, o que é o pior momento. Achado
    rodando contra o portal em 2026-08-24, não pela suíte: nenhum teste
    percorria a tabela por este caminho.
    """
    class _PortalMudo:
        def texto_se_existir(self, _seletor):
            return ""

    achado = condicoes.espanhol_dos_baloes(_PortalMudo(), [
        ("Proteção", "Sem necessidade"),
        ("Posição de armazenamento", "Horizontal"),
        ("Classificação conforme NBR 10004", "Classe II – Não perigoso"),
    ])
    assert achado == {}


def test_o_travessao_e_o_hifen_dao_na_MESMA_chave():
    """O portal usa hífen em "Classe I - Perigoso" e travessão em "Classe II –
    Não perigoso", na mesma lista de opções. Se a chave dependesse do traço, a
    segunda opção viraria "opção desconhecida" estando escrita certa."""
    assert (condicoes.chave_de_rotulo("Classe II – Não perigoso")
            == "classe ii - nao perigoso")
    assert (condicoes.chave_de_rotulo("Classe I - Perigoso")
            == "classe i - perigoso")
    convertido = condicoes.converter_da_visualizacao(
        [("Classificação conforme NBR 10004", "Classe II – Não perigoso")])
    assert convertido == {"Descarte": {"RadioButton2-input": True}}


# ===========================================================================
# 6. O espanhol — ele estava no DOM o tempo todo
# ===========================================================================

_HTML_DOIS_IDIOMAS = """
<div id="raiz">
  <!-- No portal os blocos de dois idiomas ficam DENTRO de um <fieldset>, e o
       seletor se ancora nisso de propósito: sem a âncora ele é de página e
       relê os blocos da sub-aba anterior. O dublê tem de ter o fieldset,
       senão testa um DOM que não existe. -->
  <fieldset><legend><span class="text-primary">Transporte</span></legend>
  <div id="secao">
    <div data-block="PMIB_DataSheetView.Block_ExpressionBothLenguage" id="b12-$b25">
      <div data-block="Content.Tooltip" id="b12-b25-$b2">
        <div class="osui-tooltip osui-tooltip--is-hover" id="b12-b25-b2-TooltipWrapper">
          <div class="osui-tooltip__content" id="b12-b25-b2-Content"
               aria-describedby="b12-b25-b2-Tooltip">
            <div data-block="PMIB_DataSheetView.Block_Expression">
              <span data-expression="">Manter na embalagem original</span>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div data-block="PMIB_DataSheetView.Block_ExpressionBothLenguage" id="b12-$b27">
      <div data-block="Content.Tooltip" id="b12-b27-$b2">
        <div class="osui-tooltip" id="b12-b27-b2-TooltipWrapper">
          <div class="osui-tooltip__content" id="b12-b27-b2-Content"
               aria-describedby="b12-b27-b2-Tooltip">
            <div data-block="PMIB_DataSheetView.Block_Expression">
              <span data-expression="">n&#227;o aplic&#225;vel</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  </fieldset>

  <!-- Os balões ficam LONGE do campo, pendurados no alto da árvore.
       Repare que eles NÃO estão dentro do fieldset -- é assim no portal. -->
  <div id="reactContainer">
    <div class="osui-tooltip__balloon-wrapper" id="b12-b25-b2-TooltipBallonWrapper">
      <div class="osui-tooltip__balloon-wrapper__balloon OSInline" id="b12-b25-b2-Tooltip">
        <div data-block="PMIB_DataSheetView.Block_Expression">
          <span data-expression="">Conservar en el embalaje original</span>
        </div>
      </div>
    </div>
    <div class="osui-tooltip__balloon-wrapper" id="b12-b27-b2-TooltipBallonWrapper">
      <div class="osui-tooltip__balloon-wrapper__balloon OSInline" id="b12-b27-b2-Tooltip">
        <div data-block="PMIB_DataSheetView.Block_Expression">
          <span data-expression="">no aplicable</span>
        </div>
      </div>
    </div>
  </div>
</div>
"""


def test_o_espanhol_e_lido_sem_hover_e_sem_js():
    """O balão já está no DOM (47 deles numa página recém-aberta do portal), e
    o casamento é por `aria-describedby` -- não por eixo, porque o balão não é
    vizinho nem descendente do campo."""
    motor = _EngineLxml(_HTML_DOIS_IDIOMAS)
    assert extrator.ler_espanhol_visivel(motor) == [
        ("Manter na embalagem original", "Conservar en el embalaje original"),
        ("não aplicável", "no aplicable"),
    ]


def test_o_balao_do_CLIPE_DE_ANEXOS_nao_e_confundido_com_o_do_idioma():
    """O defeito que fez o módulo declarar "a original não tem espanhol".

    O portal põe um tooltip no clipe de anexos ANTES do texto, e o caminho
    antigo (`following::div[…osui-tooltip__content][1]` a partir do rótulo)
    caía nele -- devolvia "Documentos associados" e a contagem `0`.
    """
    html = _HTML_DOIS_IDIOMAS.replace('<div id="secao">', '''<div id="secao">
      <div data-block="PMIB_DataSheetView.ViewAttachmentByDataSheetAndSection">
        <div class="osui-tooltip__content" id="b12-b24-b1-Content"
             aria-describedby="b12-b24-b1-Tooltip">
          <span data-expression="">0</span>
        </div>
      </div>''')
    html = html.replace('<div id="reactContainer">', '''<div id="reactContainer">
      <div class="osui-tooltip__balloon-wrapper__balloon" id="b12-b24-b1-Tooltip">
        <span data-expression="">Documentos associados</span>
      </div>''')
    lidos = extrator.ler_espanhol_visivel(_EngineLxml(html))
    assert lidos == [
        ("Manter na embalagem original", "Conservar en el embalaje original"),
        ("não aplicável", "no aplicable"),
    ]
    assert all("Documentos associados" not in es for _pt, es in lidos)


def test_portugues_repetido_nao_recebe_o_mesmo_espanhol():
    """"não aplicável" é o valor de vários campos da mesma ficha, e o espanhol
    de cada um pode diferir. Quem desempata é a ORDEM de documento."""
    achado = condicoes.espanhol_por_texto(
        [("não aplicável", "no aplicable"),
         ("pano seco", "paño seco"),
         ("não aplicável", "no aplica")],
        {"Transporte": {"TextArea_PositionCarePT": "não aplicável"},
         "Manutenção": {"TextArea_CleaningMethodPT": "pano seco",
                        "TextArea_ToolPreservationPT": "não aplicável"}})
    assert achado == {
        "Transporte": {"TextArea_PositionCareES": "no aplicable"},
        "Manutenção": {"TextArea_CleaningMethodES": "paño seco",
                       "TextArea_ToolPreservationES": "no aplica"},
    }


def test_campo_sem_espanhol_e_NOMEADO_no_log():
    """Separar "a original não tinha" de "eu não achei" é o que faltou por uma
    semana: o módulo dizia a primeira quando a verdade era a segunda."""
    mensagens = []
    achado = condicoes.espanhol_por_texto(
        [], {"Transporte": {"TextArea_PositionCarePT": "não aplicável"}},
        mensagens.append)
    assert achado == {}
    assert any("TextArea_PositionCarePT" in m for m in mensagens), mensagens


def test_o_espanhol_entra_pelo_fundir_sem_pisar_no_portugues():
    juntos = condicoes.fundir(
        {"Transporte": {"TextArea_PositionCarePT": "não aplicável"}},
        {"Transporte": {"TextArea_PositionCareES": "no aplicable"}})
    assert juntos == {"Transporte": {
        "TextArea_PositionCarePT": "não aplicável",
        "TextArea_PositionCareES": "no aplicable",
    }}


def test_um_PT_sem_par_e_um_espanhol_orfao_sao_casados_pela_ordem():
    """O caso que travava o Descarte inteiro.

    Os balões entram no DOM depois dos campos e a varredura às vezes pega a
    foto pela metade; um pareamento perdido deixa `..._ES` vazio, e em
    Descarte esse campo é obrigatório -- o portal recusa a sub-aba toda.
    Com um de cada lado não há escolha a fazer.
    """
    achado = condicoes.espanhol_por_texto(
        [("Lei nº 12.305/2010", "Ley nº 12.305/2010")],
        {"Descarte": {"TextArea_TypeLegislationPT": "Lei n 12.305/2010 /"}})
    assert achado == {"Descarte": {"TextArea_TypeLegislationES": "Ley nº 12.305/2010"}}


def test_dois_sem_par_continuam_sem_chute():
    """Ambíguo não se resolve por ordem: espanhol trocado entre campos é
    ficha plausível e errada, que é o erro mais caro deste módulo."""
    mensagens = []
    achado = condicoes.espanhol_por_texto(
        [("outro texto", "otro texto"), ("mais um", "uno mas")],
        {"Descarte": {"TextArea_TypeLegislationPT": "A",
                      "TextArea_DiscardTypePT": "B"}},
        mensagens.append)
    assert achado == {}
    assert any("sem espanhol" in m for m in mensagens), mensagens
