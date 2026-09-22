r"""Testes de `sigft/core/pdm_catalogo.py` -- o catálogo de PDMs que passa a
alimentar a escolha de PDM do módulo *cria fichas*.

POR QUE ESTE MÓDULO EXISTE
------------------------------------------------------------------------
Até 2026-09-22 a IA recebia, para escolher entre 1194 PDMs, exatamente DUAS
das 24 colunas da planilha-mestra: o código e o título. A classe FSC, o nome
base, o modificador e -- principalmente -- as 27,3 características por PDM
(média medida no `PDMs_SAM-GM_1193.xlsx`) eram lidas pelo app só depois, para
montar o template da ficha, e nunca entravam na ESCOLHA.

O diagnóstico que originou este módulo está em
`docs/base-conhecimento/01-cria-fichas-backend.md`. Os dois números que
justificam o pré-filtro:

  - 178 dos 467 nomes base cobrem mais de um PDM (VALVULA 44x, RELE 40x);
  - 13 títulos são compartilhados por 2 PDMs, e em 4 desses pares os dois
    PDMs estão na MESMA classe -- ali só a característica desempata.

DUAS FRENTES, como em `tests/test_pdm_io.py`
------------------------------------------------------------------------
  A. LÓGICA PURA (roda sempre) -- pertinência, ranqueamento, formatação. O
     catálogo é construído a partir de registros em memória, sem tocar disco
     nem `openpyxl`, que `tests/conftest.py` substitui por um `MagicMock`.
  B. LEITURA DE PLANILHA (só com openpyxl REAL, senão pula) -- o parse do
     layout da mestra e o fallback para o formato manipulado.
"""
from __future__ import annotations

import os

import pytest

from sigft.core import pdm_catalogo


# =============================================================================
# Fixtures de registros -- um recorte FIEL do `PDMs_SAM-GM_1193.xlsx`, com os
# casos difíceis de verdade (os dois irmãos da classe 4820 e o par de títulos
# iguais em classes diferentes).
# =============================================================================
def _pdm(codigo, classe, titulo, base, modificador, caracteristicas=()):
    return pdm_catalogo.PDM(
        codigo=codigo,
        classe=classe,
        titulo=titulo,
        nome_base=base,
        modificador=modificador,
        caracteristicas=tuple(caracteristicas),
    )


VALVULA_GAVETA = _pdm(
    "PDM.4820.002", "4820", "VALVULA GAVETA", "VALVULA", "GAVETA",
    ["MATERIAL DA CUNHA", "MATERIAL DA HASTE", "CLASSE DE PRESSAO",
     "DIAMETRO NOMINAL", "MATERIAL DO VOLANTE"],
)
VALVULA_ESFERA = _pdm(
    "PDM.4820.004", "4820", "VALVULA ESFERA", "VALVULA", "ESFERA",
    ["MATERIAL DA SEDE", "TIPO DE PASSAGEM", "NUMERO DE VIAS",
     "DIAMETRO NOMINAL", "FLUIDO"],
)
VALVULA_SOLENOIDE = _pdm(
    "PDM.4810.001", "4810", "VALVULA SOLENOIDE", "VALVULA", "SOLENOIDE",
    ["TENSAO DE ALIMENTACAO", "DIAMETRO NOMINAL"],
)
BOMBA = _pdm(
    "PDM.4320.007", "4320", "BOMBA", "BOMBA", "",
    ["VAZAO", "ALTURA MANOMETRICA", "ROTACAO"],
)
BOMBA_VACUO = _pdm(
    "PDM.4310.004", "4310", "BOMBA VACUO", "BOMBA", "VACUO",
    ["VAZAO", "PRESSAO FINAL"],
)
CABO_DADOS = _pdm(
    "PDM.6145.011", "6145", "CABO TRANSMISSAO DADOS", "CABO",
    "TRANSMISSAO DADOS", ["NUMERO DE PARES", "BITOLA"],
)
SWITCH = _pdm(
    "PDM.5895.003", "5895", "SWITCH", "SWITCH", "",
    ["NUMERO DE PORTAS", "TAXA DE TRANSMISSAO"],
)
ACCESS_POINT = _pdm(
    "PDM.5895.015", "5895", "ACCESS POINT", "ACCESS", "POINT",
    ["PADRAO DE REDE", "NUMERO DE ANTENAS"],
)
# Os dois `CAMERA VIDEO` -- títulos idênticos, classes diferentes.
CAMERA_5836 = _pdm("PDM.5836.000", "5836", "CAMERA VIDEO", "CAMERA", "VIDEO",
                   ["RESOLUCAO", "TIPO DE SENSOR"])
CAMERA_6710 = _pdm("PDM.6710.001", "6710", "CAMERA VIDEO", "CAMERA", "VIDEO",
                   ["BITOLA DO FILME"])

CLASSE_4820 = pdm_catalogo.ClasseFSC(
    numero="4820", descricao="VALVULAS, EXCETO PARA AERONAVES",
    inclui="VALVULAS DE RETENCAO", nao_inclui="VALVULAS PARA AERONAVES",
    notas="",
)
CLASSE_4810 = pdm_catalogo.ClasseFSC(
    numero="4810", descricao="VALVULAS ACIONADAS POR ENERGIA",
    inclui="VALVULAS SOLENOIDE", nao_inclui="", notas="",
)
CLASSE_4320 = pdm_catalogo.ClasseFSC(
    numero="4320", descricao="BOMBAS E COMPRESSORES", inclui="BOMBAS DE AGUA",
    nao_inclui="", notas="",
)
CLASSE_5895 = pdm_catalogo.ClasseFSC(
    numero="5895", descricao="EQUIPAMENTOS DE COMUNICACAO DIVERSOS",
    inclui="SWITCHES", nao_inclui="", notas="",
)
# A classe-armadilha: existe no manual e NAO tem nenhum PDM. No arquivo real
# são 41 delas, de 165 -- o prompt de hoje descreve todas as 165.
CLASSE_2805_SEM_PDM = pdm_catalogo.ClasseFSC(
    numero="2805", descricao="MOTORES ALTERNATIVOS DE GASOLINA",
    inclui="MOTORES A GAS", nao_inclui="", notas="",
)


def _catalogo():
    return pdm_catalogo.CatalogoPDM(
        # BOMBA_VACUO vem ANTES de BOMBA de propósito: no empate, a ordem do
        # catálogo é o desempate final, então essa ordem faz o teste do
        # "título genérico vence" provar a REGRA em vez da ordem da fixture.
        # É também a ordem do arquivo real (PDM.4310.004 < PDM.4320.007).
        pdms=[VALVULA_GAVETA, VALVULA_ESFERA, VALVULA_SOLENOIDE, BOMBA_VACUO,
              BOMBA, CABO_DADOS, SWITCH, ACCESS_POINT,
              CAMERA_5836, CAMERA_6710],
        classes=[CLASSE_4820, CLASSE_4810, CLASSE_4320, CLASSE_5895,
                 CLASSE_2805_SEM_PDM],
    )


# =============================================================================
# A. O registro PDM
# =============================================================================
def test_completo_e_a_string_que_o_portal_recebe():
    """`completo` é o que vai ser DIGITADO no filtro de PDM do portal
    (`services/cria_fichas.py` -> `digitar_no_foco`). Formato de hoje:
    "PDM.4820.004 - VALVULA ESFERA"."""
    assert VALVULA_ESFERA.completo == "PDM.4820.004 - VALVULA ESFERA"


def test_pdm_sem_modificador_nao_deixa_sobra_no_completo():
    assert BOMBA.completo == "PDM.4320.007 - BOMBA"


# =============================================================================
# B. Pertinência -- a guarda que hoje não existe
# =============================================================================
def test_contem_aceita_o_pdm_que_existe():
    assert _catalogo().contem("PDM.4820.004 - VALVULA ESFERA") is True


def test_contem_recusa_codigo_que_nao_existe():
    """O caso do `PDM.4020.001 - BOMBA CENTRIFUGA`: por 8 meses o prompt
    ensinou, no Exemplo 1, um código que NÃO EXISTE no catálogo."""
    assert _catalogo().contem("PDM.4020.001 - BOMBA CENTRIFUGA") is False


def test_contem_ignora_caixa_e_espaco_sobrando():
    assert _catalogo().contem("  pdm.4820.004  -  valvula esfera ") is True


def test_resolver_conserta_o_titulo_quando_o_codigo_esta_certo():
    """O caso do `PDM.6145.011 - CABO, TRANSMISSAO DADOS`: o código existe, o
    título real não tem a vírgula. Perder o item inteiro por causa de um
    caractere de pontuação é pior do que canonizar pelo código -- e a vírgula
    é exatamente o que o filtro do portal não casaria."""
    achado = _catalogo().resolver("PDM.4820.004 - VALVULA, ESFERA")
    assert achado is VALVULA_ESFERA


def test_resolver_devolve_none_quando_o_codigo_nao_existe():
    assert _catalogo().resolver("PDM.9999.999 - INVENTADO") is None


def test_resolver_nao_aceita_nenhum_como_pdm():
    """"NENHUM" é a resposta legítima da IA para "não há PDM adequado"
    (`services/cria_fichas.py` trata como PULAR). Não é um código."""
    assert _catalogo().resolver("NENHUM") is None


# =============================================================================
# C. O pré-filtro -- o coração da mudança
# =============================================================================
def test_candidatos_poe_o_irmao_certo_na_frente():
    """VALVULA cobre 44 PDMs no arquivo real. O que desempata é o
    modificador, e é isso que o ranqueamento tem que enxergar."""
    achados = _catalogo().candidatos("VALVULA ESFERA 3 VIAS PASSAGEM PLENA")
    assert achados[0] is VALVULA_ESFERA


def test_candidatos_usam_as_caracteristicas_para_desempatar():
    """Sem olhar característica, "NUMERO DE VIAS" não diz nada. Com, ele
    aponta para a VALVULA ESFERA -- que é o único dos dois irmãos que tem
    essa característica. Este é o sinal que hoje é jogado fora."""
    achados = _catalogo().candidatos("VALVULA COM NUMERO DE VIAS MULTIPLO")
    assert achados[0] is VALVULA_ESFERA


def test_candidatos_respeitam_o_limite():
    assert len(_catalogo().candidatos("VALVULA", limite=2)) == 2


def test_candidatos_de_texto_vazio_e_lista_vazia():
    assert _catalogo().candidatos("") == []


def test_token_generico_pesa_menos_que_token_raro():
    """"VALVULA" aparece em 3 dos 7 PDMs desta fixture; "SOLENOIDE" em 1. Uma
    descrição com os dois tem que cair na SOLENOIDE, senão o ranqueamento está
    contando palavra em vez de informação."""
    achados = _catalogo().candidatos("VALVULA SOLENOIDE 24VDC")
    assert achados[0] is VALVULA_SOLENOIDE


def test_candidatos_nao_enchem_a_lista_com_uma_familia_so():
    """Caso real da Itaipu, 2026-09-23: `COUPLING LANTERN, WITH WIRE MESH
    OPENING` (NETZSCH). A palavra "COUPLING" casa o nome base de SETE PDMs de
    acoplamento, e eles ocupavam 6 das 12 vagas de candidato -- empurrando para
    fora o `PDM.4320.031 - COLUNA FLANGE ACOPLAMENTO`, que era o certo (ele
    ficava em 15o).

    Variedade de CLASSE vale mais que profundidade numa classe só: depois que
    o modelo viu 3 acoplamentos, o 4o nao acrescenta informacao nenhuma -- e a
    vaga que ele ocupa poderia estar mostrando outra familia."""
    catalogo = pdm_catalogo.CatalogoPDM(
        pdms=[VALVULA_GAVETA, VALVULA_ESFERA, VALVULA_SOLENOIDE, BOMBA],
        classes=[CLASSE_4820, CLASSE_4810, CLASSE_4320],
    )

    # VALVULA_GAVETA e VALVULA_ESFERA sao ambos da classe 4820, e os dois
    # pontuam igual. `limite=2` com teto 1 obriga a segunda vaga a ir para
    # OUTRA classe -- se sobrasse vaga, o adiado voltaria (e deve mesmo:
    # test_o_teto_por_classe_nao_encolhe_a_lista_sem_necessidade).
    achados = catalogo.candidatos("VALVULA", limite=2, max_por_classe=1)

    classes = [p.classe for p in achados]
    assert classes == ["4820", "4810"]


def test_o_teto_por_classe_nao_encolhe_a_lista_sem_necessidade():
    """Se nao houver candidato de outra classe, a vaga nao pode ficar vazia --
    seria trocar um vies por uma lista curta."""
    catalogo = pdm_catalogo.CatalogoPDM(
        pdms=[VALVULA_GAVETA, VALVULA_ESFERA], classes=[CLASSE_4820],
    )

    achados = catalogo.candidatos("VALVULA", limite=5, max_por_classe=1)

    assert len(achados) == 2


def test_wire_nao_vira_fio_no_glossario():
    """No caso da Itaipu, "WIRE MESH" (tela de arame) era traduzido para
    "FIO" e trazia `FIO ELETRICO NU` e `FIO ELETRICO ISOLADO` como 1o e 2o
    candidatos -- ruido no topo, num item que nao tem nada de eletrico."""
    assert "WIRE" not in pdm_catalogo.GLOSSARIO


def test_candidatos_nao_repetem_pdm():
    achados = _catalogo().candidatos("VALVULA VALVULA VALVULA ESFERA")
    assert len(achados) == len(set(p.codigo for p in achados))


# -- cobertura: os casos que o arquivo real reprovou em 2026-09-22 -----------
# As quatro asserções abaixo nasceram de medição, não de imaginação: rodando o
# pré-filtro contra as 8 descrições dos exemplos do próprio prompt, QUATRO
# devolviam lista VAZIA. Um pré-filtro que não acha candidato entrega ao
# modelo uma folha em branco -- pior que a lista de 1194.
def test_candidatos_acham_o_pdm_quando_a_descricao_esta_no_plural():
    """"CAMERAS DOME FIZ AXIS P1375-E" -- descrição real, do Exemplo 2 do
    prompt. "CAMERAS" não casava "CAMERA" e o item ficava sem candidato."""
    achados = _catalogo().candidatos("CAMERAS DOME FIZ AXIS P1375-E")
    assert CAMERA_5836 in achados


def test_candidatos_atravessam_ingles_e_portugues():
    """"5 ft LOW LOSS CABLE ASSEMBLY W/N CONNECTORS" -- descrição real, do
    Exemplo 5. O catálogo da Itaipu é PT/ES e as descrições de fornecedor
    chegam em inglês; sem glossário, "CABLE" não encontra "CABO"."""
    achados = _catalogo().candidatos("5 ft LOW LOSS CABLE ASSEMBLY")
    assert CABO_DADOS in achados


def test_candidatos_preferem_o_titulo_generico_quando_so_ele_casou():
    """"Bomba KSB 123-ABC" -- só a palavra BOMBA casa. Nesse empate o PDM
    genérico (`BOMBA`) tem que vencer o específico (`BOMBA VACUO`): a palavra
    "VACUO" não apareceu na descrição, então afirmá-la é invenção."""
    achados = _catalogo().candidatos("Bomba KSB 123-ABC")
    assert achados[0] is BOMBA


def test_candidatos_entendem_sigla_curta_conhecida():
    """"Wi-Fi 6 Outdoor AP, External Ant" -- descrição real, do Exemplo 8.
    "AP" tem 2 letras e o corte por tamanho o descartava, deixando o item
    sem nenhum candidato."""
    achados = _catalogo().candidatos("Wi-Fi 6 Outdoor AP External Ant")
    assert ACCESS_POINT in achados


# -- busca para a pessoa, na janela de revisao -------------------------------
def test_buscar_acha_por_pedaco_do_titulo():
    """A revisao humana era um `askstring` de texto livre: a pessoa tinha que
    digitar "PDM.4820.004 - VALVULA ESFERA" de cabeca, sem busca e sem
    validacao. Buscar por pedaco e o que uma pessoa faz."""
    achados = _catalogo().buscar("esfera")

    assert VALVULA_ESFERA in achados


def test_buscar_acha_pelo_codigo():
    achados = _catalogo().buscar("4820.004")

    assert achados[0] is VALVULA_ESFERA


def test_buscar_sem_texto_devolve_o_comeco_do_catalogo():
    """Janela abrindo vazia nao ajuda ninguem a escolher."""
    achados = _catalogo().buscar("")

    assert achados


def test_buscar_respeita_o_limite():
    assert len(_catalogo().buscar("valvula", limite=2)) == 2


def test_buscar_nao_repete_pdm():
    achados = _catalogo().buscar("valvula esfera")

    assert len(achados) == len({p.codigo for p in achados})


# =============================================================================
# D. O que vai para o prompt
# =============================================================================
def test_manual_de_regras_omite_classe_que_nao_tem_pdm():
    """As 41 classes sem PDM do arquivo real são armadilha ativa: a IA raciocina
    até a classe e não há PDM para escolher."""
    manual = _catalogo().manual_de_regras()
    assert "4820" in manual
    assert "2805" not in manual
    assert "MOTORES ALTERNATIVOS DE GASOLINA" not in manual


def test_manual_de_regras_leva_o_inclui_e_o_nao_inclui():
    manual = _catalogo().manual_de_regras()
    assert "VALVULAS DE RETENCAO" in manual
    assert "VALVULAS PARA AERONAVES" in manual


def test_lista_por_classe_agrupa_o_pdm_sob_a_classe_dele():
    """A lista plana de hoje não diz a classe de ninguém, apesar de o código
    embuti-la. Agrupar é o que liga a lista ao manual de regras -- e custa
    quase nada: medido no arquivo real, a lista agrupada com a descrição da
    classe no cabeçalho substitui a lista plana MAIS um índice de classes."""
    lista = _catalogo().lista_por_classe()
    assert "CLASSE 4820" in lista
    assert "VALVULAS, EXCETO PARA AERONAVES" in lista
    assert "PDM.4820.004 - VALVULA ESFERA" in lista


def test_lista_por_classe_traz_todos_os_pdms():
    """Ela é a REDE do pré-filtro: medido contra o arquivo real, uma descrição
    como "IE4010 w/ 12GE SFP ... uplink ports" não tem nenhuma palavra que
    nomeie o equipamento, então nenhum pré-filtro léxico a alcança. Sem a
    lista inteira no prompt, esse item ficaria cego."""
    lista = _catalogo().lista_por_classe()
    for p in _catalogo().pdms:
        assert p.completo in lista


def test_lista_por_classe_nao_inventa_classe_sem_pdm():
    assert "2805" not in _catalogo().lista_por_classe()


def test_bloco_de_candidatos_mostra_codigo_classe_e_caracteristicas():
    """A IA só consegue usar a característica se ela CHEGAR nela."""
    bloco = _catalogo().bloco_de_candidatos([VALVULA_ESFERA])
    assert "PDM.4820.004 - VALVULA ESFERA" in bloco
    assert "4820" in bloco
    assert "TIPO DE PASSAGEM" in bloco


def test_bloco_de_candidatos_desempata_titulos_iguais_pela_classe():
    """Os dois `CAMERA VIDEO` têm a MESMA string de "PDM COMPLETO". Sem a
    classe no bloco, a IA não tem como escolher entre eles."""
    bloco = _catalogo().bloco_de_candidatos([CAMERA_5836, CAMERA_6710])
    assert "5836" in bloco and "6710" in bloco


# =============================================================================
# E. Leitura de planilha -- só com openpyxl REAL
# =============================================================================
def _openpyxl_real():
    try:
        import openpyxl
    except Exception:
        return False
    # conftest.py troca openpyxl por MagicMock no contêiner enxuto.
    return type(getattr(openpyxl, "Workbook", None)).__name__ == "type"


requer_openpyxl = pytest.mark.skipif(
    not _openpyxl_real(), reason="openpyxl real ausente (stub do conftest)"
)


def _escrever_mestra(caminho):
    """Reproduz o layout REAL do `PDMs_SAM-GM_1193.xlsx`: 6 linhas de
    preâmbulo/cabeçalho em `TEMPLATE_PDM` (dados a partir da 7ª) e uma linha
    por (PDM, característica)."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "TEMPLATE_PDM"
    for _ in range(6):
        ws.append([])
    # cols: A codigo, B classe, C tit ES, D tit PT, E base ES, F base PT,
    #       G modif ES, H modif PT, ... Q caract PT (indice 17, 1-based)
    linhas = [
        ("PDM.4820.004", 4820, "VALVULA ESFERA", "VALVULA ESFERA",
         "VALVULA", "VALVULA", "ESFERA", "ESFERA", "TIPO DE PASSAGEM"),
        ("PDM.4820.004", 4820, "VALVULA ESFERA", "VALVULA ESFERA",
         "VALVULA", "VALVULA", "ESFERA", "ESFERA", "NUMERO DE VIAS"),
        ("PDM.4320.007", 4320, "BOMBA", "BOMBA", "BOMBA", "BOMBA",
         None, None, "VAZAO"),
    ]
    for lin in linhas:
        ws.append([lin[0], lin[1], lin[2], lin[3], lin[4], lin[5], lin[6],
                   lin[7], None, None, None, None, None, None, None, None,
                   lin[8]])

    wsg = wb.create_sheet("GRUPOS_CLASES")
    wsg.append([])
    wsg.append([])
    # cols: A grupo, ... F classe(idx6), H classe desc PT(idx8),
    #       J inclui PT(10), L nao inclui PT(12), N notas PT(14)
    wsg.append([48, "VALVULAS", "VALVULAS", None, None, 4820,
                "VALVULAS ES", "VALVULAS, EXCETO PARA AERONAVES",
                "INC ES", "VALVULAS DE RETENCAO", "NAOINC ES",
                "VALVULAS PARA AERONAVES", "NOTAS ES", ""])
    wb.save(caminho)


@requer_openpyxl
def test_carregar_mestra_agrupa_as_linhas_em_um_pdm_por_codigo(tmp_path):
    """32 655 linhas viram 1194 PDMs no arquivo real -- uma linha por
    (PDM, característica)."""
    caminho = os.path.join(str(tmp_path), "mestra.xlsx")
    _escrever_mestra(caminho)

    cat = pdm_catalogo.carregar(caminho)

    assert len(cat) == 2
    esfera = cat.resolver("PDM.4820.004 - VALVULA ESFERA")
    assert esfera is not None
    assert esfera.caracteristicas == ("TIPO DE PASSAGEM", "NUMERO DE VIAS")


@requer_openpyxl
def test_carregar_mestra_le_classe_nome_base_e_modificador(tmp_path):
    caminho = os.path.join(str(tmp_path), "mestra.xlsx")
    _escrever_mestra(caminho)

    esfera = pdm_catalogo.carregar(caminho).resolver("PDM.4820.004 - VALVULA ESFERA")

    assert esfera.classe == "4820"
    assert esfera.nome_base == "VALVULA"
    assert esfera.modificador == "ESFERA"


@requer_openpyxl
def test_carregar_mestra_traz_o_manual_de_regras_da_aba_de_classes(tmp_path):
    caminho = os.path.join(str(tmp_path), "mestra.xlsx")
    _escrever_mestra(caminho)

    manual = pdm_catalogo.carregar(caminho).manual_de_regras()

    assert "VALVULAS DE RETENCAO" in manual


@requer_openpyxl
def test_carregar_fica_so_com_a_revisao_vigente_do_pdm(tmp_path):
    """O Master acumula uma linha por (PDM, caracteristica, REVISAO) -- e
    1.023 dos 1.194 PDMs do arquivo real tem mais de uma revisao
    (`docs/refatoracao/PENDENCIAS.md`, entrada de 2026-08-18). Unir as
    revisoes traz de volta caracteristica que saiu do PDM: o caso medido la e
    o PDM.4820.015, com 42 caracteristicas na r0 e 20 na r1 -- a uniao da 44.

    Aqui isso contamina a ESCOLHA: uma caracteristica obsoleta e um sinal
    falso no desempate entre irmaos."""
    import openpyxl

    caminho = os.path.join(str(tmp_path), "revisoes.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "TEMPLATE_PDM"
    for _ in range(6):
        ws.append([])

    def linha(revisao, caract):
        # col J (indice 9) = REVISION
        return ["PDM.4820.015", 4820, "VALVULA X", "VALVULA X", "VALVULA",
                "VALVULA", "X", "X", None, revisao, None, None, None, None,
                None, None, caract]

    ws.append(linha(0, "CARACTERISTICA OBSOLETA"))
    ws.append(linha(0, "DIAMETRO NOMINAL"))
    ws.append(linha(1, "DIAMETRO NOMINAL"))
    ws.append(linha(1, "CLASSE DE PRESSAO"))
    wb.save(caminho)

    pdm = pdm_catalogo.carregar(caminho).resolver("PDM.4820.015 - VALVULA X")

    assert pdm.caracteristicas == ("DIAMETRO NOMINAL", "CLASSE DE PRESSAO")


@requer_openpyxl
def test_carregar_usa_o_titulo_da_revisao_vigente(tmp_path):
    """O TITULO tambem muda entre revisoes, nao so as caracteristicas -- e o
    titulo e a string DIGITADA no filtro de PDM do portal. Digitar o titulo de
    uma revisao antiga faz o portal nao achar nada, e a automacao quebra com o
    PDM certo escolhido.

    Caso real, medido no arquivo do usuario: `PDM.7010.018` e
    'SERVIDOR CONSOLE' na revisao 0 e **'SERVIDOR'** na vigente (rev 2,
    28/02/2025). Sao 4 PDMs em que o titulo da primeira linha do arquivo
    difere do da vigente, e em 47 PDMs a primeira linha nem e a vigente."""
    import openpyxl

    caminho = os.path.join(str(tmp_path), "titulo_por_revisao.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "TEMPLATE_PDM"
    for _ in range(6):
        ws.append([])

    def linha(revisao, titulo, caract):
        return ["PDM.7010.018", 7010, titulo, titulo, "SERVIDOR", "SERVIDOR",
                None, None, None, revisao, None, None, None, None, None,
                None, caract]

    # a revisao ANTIGA vem primeiro, como acontece em 47 PDMs do arquivo real
    ws.append(linha(0, "SERVIDOR CONSOLE", "CARACTERISTICA ANTIGA"))
    ws.append(linha(2, "SERVIDOR", "NUMERO DE PROCESSADORES"))
    wb.save(caminho)

    cat = pdm_catalogo.carregar(caminho)

    assert cat.pdms[0].titulo == "SERVIDOR"
    assert cat.pdms[0].completo == "PDM.7010.018 - SERVIDOR"
    assert cat.pdms[0].caracteristicas == ("NUMERO DE PROCESSADORES",)


@requer_openpyxl
def test_carregar_descarta_codigo_sujo_da_planilha(tmp_path):
    """A linha 32661 do arquivo real tem `CÓDIGO PDM = 1192.999999999937`
    -- artefato de float. Sem descarte, vira uma entrada falsa no catálogo."""
    import openpyxl

    caminho = os.path.join(str(tmp_path), "mestra.xlsx")
    _escrever_mestra(caminho)
    wb = openpyxl.load_workbook(caminho)
    wb["TEMPLATE_PDM"].append([1192.999999999937])
    wb.save(caminho)

    cat = pdm_catalogo.carregar(caminho)

    assert len(cat) == 2


@requer_openpyxl
def test_carregar_aceita_o_formato_manipulado_antigo(tmp_path):
    """Compatibilidade: as planilhas que o usuário já entregava têm as abas
    `PDMs` (coluna "PDM COMPLETO") e `Instruções PDMs`. Sem características,
    mas o catálogo tem que subir -- quebrar os arquivos antigos seria pior
    do que não ter característica."""
    import openpyxl

    caminho = os.path.join(str(tmp_path), "manipulada.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "PDMs"
    ws.append(["PDM COMPLETO"])
    ws.append(["PDM.4820.004 - VALVULA ESFERA"])
    ws.append(["PDM.4320.007 - BOMBA"])
    wsi = wb.create_sheet("Instruções PDMs")
    wsi.append(["N° GRUPO", "GRUPO DESCRIÇÃO PT", "GRUPO NOTAS PT",
                "N° CLASSE", "CLASSE DESCRIÇÃO PT", "CLASSE INCLUI PT",
                "CLASSE NÃO INCLUI PT", "CLASSE NOTAS PT"])
    wsi.append([48, "VALVULAS", "", 4820, "VALVULAS, EXCETO PARA AERONAVES",
                "VALVULAS DE RETENCAO", "", ""])
    wb.save(caminho)

    cat = pdm_catalogo.carregar(caminho)

    assert len(cat) == 2
    assert cat.contem("PDM.4820.004 - VALVULA ESFERA") is True
    assert "VALVULAS DE RETENCAO" in cat.manual_de_regras()


@requer_openpyxl
def test_carregar_arquivo_sem_aba_conhecida_levanta_erro_claro(tmp_path):
    import openpyxl

    caminho = os.path.join(str(tmp_path), "qualquer.xlsx")
    wb = openpyxl.Workbook()
    wb.active.title = "Planilha1"
    wb.save(caminho)

    with pytest.raises(ValueError, match="TEMPLATE_PDM"):
        pdm_catalogo.carregar(caminho)
