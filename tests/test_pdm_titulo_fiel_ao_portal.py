r"""O título do PDM tem que continuar EXATAMENTE o que o portal aceita.

POR QUE ESTE ARQUIVO EXISTE
------------------------------------------------------------------------
A string `PDM.XXXX.YYY - TITULO` não é rótulo: ela é **digitada** no campo de
busca de PDM do portal (`services/cria_fichas.processar_item_individual` ->
`engine.digitar_no_foco(pdm)`), e logo em seguida vem um ENTER. Se o texto não
casar, o filtro não mostra nada, o ENTER não seleciona nada, e **a automação
quebra com o PDM certo já escolhido** -- o pior tipo de falha, porque a escolha
estava correta e o erro aparece três passos adiante.

Foi o usuário quem levantou isso, em 2026-09-22, depois da reescrita do
catálogo: *"antes ele retornava o nome correto do PDM [...] se digitar errado,
nao vai aparecer dai embora tenha escolhido o pdm correto, vai quebrar a
automação"*. E a checagem achou um defeito real, descrito abaixo.

A FIXTURE SÃO DADOS SABIDAMENTE BONS
------------------------------------------------------------------------
Os 27 títulos abaixo foram fornecidos pelo usuário como exemplos do que o
módulo **produzia antes** e que **funcionava no portal**. Não são inventados
nem derivados do código que eles testam -- é a única amostra de verdade-campo
que existe sobre esse formato, e por isso vale como trava de regressão.

O DEFEITO QUE ELES QUASE NÃO PEGARAM
------------------------------------------------------------------------
Os 27 passavam mesmo com o leitor defeituoso, porque em 1.146 dos 1.193 PDMs a
primeira linha do arquivo JÁ é a revisão vigente. O defeito só aparecia nos 47
em que não é, e mudava o título em 4 deles -- entre eles `PDM.7010.018`, que é
"SERVIDOR CONSOLE" na revisão 0 e **"SERVIDOR"** na vigente. Uma amostra que
passa não prova a regra: é por isso que
`tests/test_pdm_catalogo.py::test_carregar_usa_o_titulo_da_revisao_vigente`
existe ao lado desta, montando o caso difícil de propósito.
"""
from __future__ import annotations

from sigft.core import pdm_catalogo


# Fornecidos pelo usuário em 2026-09-22 como "o que saía antes, e funcionava".
TITULOS_QUE_O_PORTAL_ACEITA = [
    "PDM.6115.903 - PLACA CONEXAO HIDRAULICA",
    "PDM.6115.904 - VEDACAO CONEXAO HIDRAULICA",
    "PDM.6115.905 - BRACO PROTECAO DE LINHA",
    "PDM.6115.906 - GUIA",
    "PDM.6120.001 - MOTO-VENTILADOR",
    "PDM.6120.002 - COMUTADOR TENSAO",
    "PDM.6120.003 - TRANSFORMADOR POTENCIA",
    "PDM.6120.004 - TRANSFORMADOR ATERRAMENTO",
    "PDM.6120.005 - BOLSA BORRACHA",
    "PDM.6125.000 - COMPENSADOR SINCRONO",
    "PDM.6130.001 - FONTE ALIMENTACAO",
    "PDM.6130.002 - CONVERSOR SINAL",
    "PDM.6130.003 - PLACA SOLAR",
    "PDM.6130.004 - REGULADOR CARGA BATERIA",
    "PDM.6130.005 - MONITOR CARGA BATERIA",
    "PDM.6130.800 - PLACA SOLAR",
    "PDM.6135.001 - BATERIA ELETRICA",
    "PDM.6140.001 - ELEMENTO ALCALINO BATERIA",
    "PDM.5330.025 - CABECA ROTATIVA",
    "PDM.5330.026 - DISCO",
    "PDM.5330.028 - SEDE",
    "PDM.5330.031 - JUNTA DESLIZAMENTO",
    "PDM.5330.032 - JUNTA VALVULA COMANDO",
    "PDM.5330.033 - MEMBRANA EXPANSAO",
    "PDM.5330.034 - KIT GAXETA",
    "PDM.5330.035 - JOGO VEDACOES",
    "PDM.5330.800 - KIT VEDACAO",
]


def _catalogo_dos_exemplos():
    """Monta o catálogo a partir dos próprios títulos-verdade, separando
    código e título como o leitor da planilha faz. Assim o teste roda sem
    `openpyxl` real e sem a planilha de 4,7 MB, e ainda assim prova o formato
    de `completo`, que é o que chega ao portal."""
    pdms = []
    for linha in TITULOS_QUE_O_PORTAL_ACEITA:
        codigo, titulo = linha.split(" - ", 1)
        palavras = titulo.split()
        pdms.append(pdm_catalogo.PDM(
            codigo=codigo,
            classe=codigo.split(".")[1],
            titulo=titulo,
            nome_base=palavras[0],
            modificador=" ".join(palavras[1:]),
        ))
    return pdm_catalogo.CatalogoPDM(pdms=pdms)


def test_completo_reproduz_exatamente_o_titulo_que_o_portal_aceita():
    """Trava o FORMATO: `codigo`, espaço, hífen, espaço, título. Um separador
    diferente (dois espaços, travessão, sem espaço) não filtraria nada."""
    catalogo = _catalogo_dos_exemplos()

    produzidos = [p.completo for p in catalogo.pdms]

    assert produzidos == TITULOS_QUE_O_PORTAL_ACEITA


def test_contem_reconhece_todos_os_titulos_bons():
    """A guarda `conferir_pdm` reprova o que `contem` não reconhece. Se ela
    recusasse um título bom, o item viraria "NENHUM" e a ficha não seria
    criada -- uma falha nova, no lugar da antiga."""
    catalogo = _catalogo_dos_exemplos()

    for linha in TITULOS_QUE_O_PORTAL_ACEITA:
        assert catalogo.contem(linha) is True, linha


def test_resolver_devolve_o_mesmo_texto_que_entrou():
    """`conferir_pdm` canoniza pelo código quando o título diverge. Para um
    título JÁ correto, canonizar não pode alterar nada."""
    catalogo = _catalogo_dos_exemplos()

    for linha in TITULOS_QUE_O_PORTAL_ACEITA:
        assert catalogo.resolver(linha).completo == linha, linha


def test_o_hifen_do_titulo_nao_confunde_o_separador():
    """`PDM.6120.001 - MOTO-VENTILADOR` tem hífen DENTRO do título. Quebrar
    no primeiro hífen em vez de no separador produziria "MOTO" e o portal não
    acharia nada."""
    catalogo = _catalogo_dos_exemplos()

    achado = catalogo.por_codigo("PDM.6120.001")

    assert achado.titulo == "MOTO-VENTILADOR"
    assert achado.completo == "PDM.6120.001 - MOTO-VENTILADOR"


def test_codigos_repetidos_de_titulo_continuam_distinguiveis():
    """`PDM.6130.003` e `PDM.6130.800` são os dois "PLACA SOLAR" -- mesmo
    título, mesma classe. O que os separa é o código, e ele está no texto
    digitado."""
    catalogo = _catalogo_dos_exemplos()

    a = catalogo.por_codigo("PDM.6130.003")
    b = catalogo.por_codigo("PDM.6130.800")

    assert a.titulo == b.titulo == "PLACA SOLAR"
    assert a.completo != b.completo


# =============================================================================
# Espaço anômalo no Master -- a decisão e o seu limite
# =============================================================================
# 22 PDMs têm espaço duplo ou TAB no título da revisão vigente. O catálogo
# COLAPSA tudo para um espaço só, e para os 4 com TAB isso é inequívoco: a
# string é entregue a `engine.digitar_no_foco`, e um TAB digitado num
# formulário web MOVE O FOCO -- o `press("ENTER")` seguinte cairia noutro
# campo. Preservar seria pior que colapsar, com certeza.
#
# Para os outros 18 (espaço duplo simples, ex.: 'DESUMIDIFICADOR  AR') a
# escolha é defensável mas NÃO verificada: só o portal diz se ele guarda um
# espaço ou dois, e esta sessão não o alcança (ver CLAUDE.md). Estão
# registrados em PENDENCIAS.md para a próxima sessão local.
def test_tab_no_titulo_nunca_chega_ao_que_e_digitado():
    """`PDM.4710.005` é 'TUBO     \\t\\t\\t\\t RIGIDO' no Master. Um TAB digitado
    tira o foco do campo de busca, e o ENTER seguinte age noutro lugar."""
    pdm = pdm_catalogo.PDM(
        codigo="PDM.4710.005", classe="4710",
        titulo=pdm_catalogo._txt("TUBO     \t\t\t\t RIGIDO"),
    )

    assert "\t" not in pdm.completo
    assert pdm.completo == "PDM.4710.005 - TUBO RIGIDO"


def test_espaco_duplo_do_master_vira_espaco_simples():
    """Decisão registrada, não descoberta: o Master traz
    'DESUMIDIFICADOR  AR' com dois espaços. Se a conferência no portal mostrar
    que ele guarda os dois, é AQUI que a mudança começa."""
    assert pdm_catalogo._txt("DESUMIDIFICADOR  AR") == "DESUMIDIFICADOR AR"
