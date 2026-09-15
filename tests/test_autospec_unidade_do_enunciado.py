r"""O que o log da ficha `4500063671.0070 en-US` revelou (2026-09-15).

O usuário rodou o AutoSpec com as correções da véspera. A busca funcionou: o
datasheet da Cisco foi achado e lido (16 páginas, 24.785 chars). Mas o campo
das dimensões ficou vazio, com esta mensagem:

    14 - DIMENSIONS (Indicate the dimensions of the item in (mm)
      -> a IA respondeu '152 x 91 x 135'
         motivo: nao ha medida para recalcular

A CAUSA, MEDIDA
------------------------------------------------------------------------
O lastro foi testado contra todas as formas plausíveis de o datasheet
escrever a dimensão. Passa em todas — **menos numa**: quando o documento traz
a medida só em POLEGADA.

    5.98 x 25,4 = 151,9 -> 152      3.58 x 25,4 = 90,9 -> 91
    5.31 x 25,4 = 134,9 -> 135

A IA fez a conversão CERTA. E o mecanismo que existe exatamente para aprovar
conversão correta (`autospec_unidades`) não pôde agir, porque a resposta veio
**sem unidade** — a pergunta já dizia `in (mm)`, então a IA não repetiu o
`mm`. Sem unidade não há medida, e sem medida não há conta para conferir.

Provado com a mesma resposta, mudando só isso:

    '152 x 91 x 135'      lastro=False   medidas=[]
    '152 x 91 x 135 mm'   lastro=True    152 mm = 5.98 in; 91 mm = 3.58 in; ...

E NÃO É SÓ A DIMENSÃO
------------------------------------------------------------------------
Vale para todo campo cujo enunciado já declara a unidade — e a ficha está
cheia deles: `em (V)`, `em (A)`, `em (Hz)`, `em grau Celsius (°C)`. Em todos,
uma resposta numérica crua perde a conferência de conversão.
"""
import pytest

from sigft.services import autospec, autospec_unidades as un


# =============================================================================
# 1. A unidade que a PERGUNTA já declara
# =============================================================================
@pytest.mark.parametrize("pergunta,esperada", [
    ("14 - DIMENSIONS (Indicate the dimensions of the item in (mm))", "mm"),
    ("1 - FAIXA DE TEMPERATURA (Indicar a faixa em grau Celsius (°C).)", "c"),
])
def test_a_unidade_sai_do_enunciado(pergunta, esperada):
    assert un.unidade_declarada(pergunta) == esperada


@pytest.mark.parametrize("pergunta", [
    # VOLT e AMPERE ainda NAO sao unidades conhecidas do modulo, e a segunda
    # nao pode virar: `a` e o conector de intervalo em portugues, e aceita-lo
    # como ampere quebraria `0 a 70 °C`, que tem teste proprio. Medido em
    # 2026-09-15 e registrado em PENDENCIAS.md.
    "4 - TENSAO DE ALIMENTACAO (Indicar a tensão de alimentação do item em (V))",
    "16 - CORRENTE NOMINAL (Indicar a corrente nominal do item em (A))",
    # Várias unidades listadas: qual delas? Chutar seria pior que não agir.
    "2 - SINAL DE ENTRADA (Indicar o sinal do item em (mV, V, A, mA) ex.: 4-20mA)",
    # Sem unidade nenhuma.
    "8 - TIPO (Indicar o tipo do item ex: circuito impresso, outros)",
    "9 - TIPO CONSTRUTIVO (Indicar o tipo construtivo do item.)",
    "",
])
def test_enunciado_ambiguo_ou_sem_unidade_nao_declara_nada(pergunta):
    assert un.unidade_declarada(pergunta) is None


def test_o_parenteses_de_prosa_nao_vira_unidade():
    """`(H x W x D)` e `(entrada do cabo)` também estão entre parênteses."""
    assert un.unidade_declarada("Dimensions (H x W x D) do item") is None


# =============================================================================
# 2. A resposta crua herda a unidade do enunciado — o defeito do usuário
# =============================================================================
CTX_SO_POLEGADA = "Dimensions (H x W x D): 5.98 x 3.58 x 5.31 in."
PERGUNTA_DIM = "14 - DIMENSIONS (Indicate the dimensions of the item in (mm))"


def test_o_caso_do_usuario_passa_a_ter_lastro():
    """O teste que fecha o pedido."""
    core = autospec.AutoSpecCore.__new__(autospec.AutoSpecCore)
    aprovados = core._filtrar_por_lastro(
        {"var_row_14": "152 x 91 x 135"},
        {"var_row_14": {"desc": PERGUNTA_DIM}}, CTX_SO_POLEGADA)
    assert aprovados.get("var_row_14") == "152 x 91 x 135"


def test_a_conversao_ERRADA_continua_reprovando():
    """A guarda não pode virar "aceita qualquer número". `15 x 9 x 13` é a
    mesma leitura com a vírgula no lugar errado — dez vezes menor."""
    core = autospec.AutoSpecCore.__new__(autospec.AutoSpecCore)
    aprovados = core._filtrar_por_lastro(
        {"var_row_14": "15 x 9 x 13"},
        {"var_row_14": {"desc": PERGUNTA_DIM}}, CTX_SO_POLEGADA)
    assert aprovados.get("var_row_14") != "15 x 9 x 13"


def test_numero_inventado_continua_reprovando():
    core = autospec.AutoSpecCore.__new__(autospec.AutoSpecCore)
    aprovados = core._filtrar_por_lastro(
        {"var_row_14": "900 x 800 x 700"},
        {"var_row_14": {"desc": PERGUNTA_DIM}}, CTX_SO_POLEGADA)
    assert not aprovados.get("var_row_14")


def test_resposta_que_JA_traz_unidade_nao_e_tocada():
    """Só o caso da resposta crua muda. Quem já escreveu a unidade segue pelo
    caminho de sempre."""
    assert un.aplicar_unidade_da_pergunta("152 mm", PERGUNTA_DIM) == "152 mm"


def test_resposta_de_TEXTO_nao_ganha_unidade():
    """`Aço inox 316` não é medida, e grudar `mm` nele seria inventar."""
    p = "3 - MATERIAL (Indicar o material do item em (mm))"
    assert un.aplicar_unidade_da_pergunta("Aço inox 316", p) == "Aço inox 316"


# =============================================================================
# 3. As 26 fontes "que não estão entre os documentos lidos"
# =============================================================================
# O log acusou 26 campos citando `https://www.amplicon.com/.../Doc=1859` como
# fonte inexistente — sendo que é EXATAMENTE o documento que foi lido. O
# marcador do contexto leva o TÍTULO; a IA cita a URL, que está na linha
# seguinte e não era coletada. Aviso falso em 26 campos ensina o usuário a
# ignorar o aviso, e aí o verdadeiro passa junto.

CONTEXTO_WEB = (
    "--- WEB DOC: Cisco Catalyst IE3200 Rugged Series Data Sheet - Amplicon ---\n"
    "URL: https://www.amplicon.com/actions/viewDoc.cfm?Doc=1859\n"
    "Dimensions (H x W x D): 5.98 x 3.58 x 5.31 in.\n"
)


def test_a_URL_do_documento_lido_conta_como_origem():
    origens = autospec.origens_do_contexto(CONTEXTO_WEB)
    assert "https://www.amplicon.com/actions/viewDoc.cfm?Doc=1859" in origens


def test_o_titulo_continua_contando_como_origem():
    origens = autospec.origens_do_contexto(CONTEXTO_WEB)
    assert any("Amplicon" in o for o in origens)


def test_citar_a_URL_do_documento_lido_NAO_e_suspeito():
    core = autospec.AutoSpecCore.__new__(autospec.AutoSpecCore)
    core.ultimas_fontes_por_campo = {
        "peso_liquido": "https://www.amplicon.com/actions/viewDoc.cfm?Doc=1859"}
    avisos = []

    class _Cb:
        def log(self, msg, nivel=None):
            avisos.append(msg)

    core._conferir_fontes_citadas(CONTEXTO_WEB, _Cb())
    assert not avisos, avisos


def test_citar_documento_que_ninguem_leu_continua_suspeito():
    """A guarda que não pode afrouxar: citar fonte inexistente é sinal de
    invenção, e quem homologa precisa saber."""
    core = autospec.AutoSpecCore.__new__(autospec.AutoSpecCore)
    core.ultimas_fontes_por_campo = {"peso_liquido": "https://www.inventado.com/x.pdf"}
    avisos = []

    class _Cb:
        def log(self, msg, nivel=None):
            avisos.append(msg)

    core._conferir_fontes_citadas(CONTEXTO_WEB, _Cb())
    assert avisos


# =============================================================================
# 4. A mensagem de reprovação tem de dizer O QUE faltou
# =============================================================================
def test_o_motivo_nomeia_os_numeros_que_nao_estao_no_documento():
    """`motivo: nao ha medida para recalcular` não diz nada a quem lê. Dizer
    QUAL número não foi achado é o que transforma o aviso em ação — e é o que
    teria dado este diagnóstico em dez segundos."""
    core = autospec.AutoSpecCore.__new__(autospec.AutoSpecCore)
    reprovados = []
    core._filtrar_por_lastro(
        {"var_row_14": "900 x 800 x 700"},
        {"var_row_14": {"desc": PERGUNTA_DIM}}, CTX_SO_POLEGADA,
        callbacks=_coletor(reprovados))
    texto = "\n".join(reprovados)
    assert "900" in texto, texto


def _coletor(destino):
    class _Cb:
        def log(self, msg, nivel=None):
            destino.append(str(msg))
    return _Cb()


# =============================================================================
# 5. O recorte por modelo não pode cortar TUDO
# =============================================================================
def test_recorte_que_nao_encontra_o_meu_modelo_nao_corta_nada():
    """Guarda de segurança do recorte que entrou ontem.

    Se o modelo da planilha estiver escrito de um jeito que não casa com
    nenhuma linha, o recorte cortaria todas as linhas de modelo e deixaria a
    ficha sem os dados que estão bem ali. Nesse caso é mais provável que o
    modelo esteja grafado diferente do que o documento inteiro ser de outro
    produto — então não corta."""
    doc = ("UCECH1: 168 x 150 x 85 mm\n"
           "UCECH2: 168 x 150 x 90 mm\n"
           "Operating temperature: -40 to 70 °C")
    assert autospec.contexto_do_modelo(doc, "PVF100-4") == doc


def test_recorte_continua_cortando_quando_acha_o_meu():
    doc = ("UCSCH1: 168 x 150 x 55 mm\n"
           "UCECH1: 168 x 150 x 85 mm")
    recorte = autospec.contexto_do_modelo(doc, "UCSCH1")
    assert "55 mm" in recorte and "85 mm" not in recorte


# =============================================================================
# 6. O rótulo `cm`, `cm`, `cm`, `kg` no log
# =============================================================================
def test_o_log_nomeia_o_campo_quando_a_descricao_e_so_a_unidade():
    """No log da ficha do usuário, quatro campos apareceram como `cm`, `cm`,
    `cm`, `kg`. O log era FIEL: no `CONFIG_MAP`, o `desc` desses campos é
    literalmente a unidade. Mas `cm` não diz a ninguém qual campo preencher.

    Testado por AST porque a linha mora dentro do gerador do lote, que só roda
    com planilha e chave de IA."""
    import ast
    import inspect
    from sigft.services import autospec as mod

    fonte = inspect.getsource(mod)
    arvore = ast.parse(fonte)
    textos = [n.value for n in ast.walk(arvore)
              if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert any("_chave" in t or "{rotulo" in t for t in textos), \
        "o log voltou a mostrar so a descricao"
