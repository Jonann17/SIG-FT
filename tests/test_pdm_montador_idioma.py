r"""O montador da ficha e o template em inglês (2026-08-28).

O montador fazia `wb_target["Ficha Técnica Padrão"]` — nome de
aba **fixo**. Um template cuja aba se chame outra coisa levanta `KeyError`
dentro do laço, e o `except` genérico transforma isso em
`"ERRO ao gerar ficha {pmib}"` — **uma vez por ficha**, sem dizer em momento
nenhum que o problema é a aba. Num lote de 200 materiais, são 200 linhas de
erro idênticas e inúteis.

Isto vale independentemente do idioma: é a diferença entre "o aplicativo não
conseguiu" e "o aplicativo não conseguiu, e é por isto".
"""
import pytest

from sigft.services import pdm


@pytest.fixture
def openpyxl_real():
    """A suíte stuba o openpyxl; aqui precisamos do de verdade.

    Trocar `sys.modules` não basta: `sigft/services/pdm.py` faz
    `from openpyxl import load_workbook` no topo, e esse nome foi LIGADO ao
    stub no momento do import. Sem religá-lo, o serviço continua conversando
    com o MagicMock — cujo `worksheets` itera vazio, o que fazia o teste
    reprovar por um motivo que não era o dele.
    """
    import importlib
    import sys
    guardados = {n: m for n, m in sys.modules.items() if n.startswith("openpyxl")}
    for nome in guardados:
        del sys.modules[nome]

    ligados = {
        "load_workbook": pdm.load_workbook,
        "Border": pdm.Border, "Side": pdm.Side,
        "Alignment": pdm.Alignment, "Font": pdm.Font,
    }
    try:
        modulo = importlib.import_module("openpyxl")
        if not hasattr(modulo, "Workbook") or "Mock" in type(modulo).__name__:
            pytest.skip("openpyxl real nao disponivel")
        estilos = importlib.import_module("openpyxl.styles")
        pdm.load_workbook = modulo.load_workbook
        pdm.Border, pdm.Side = estilos.Border, estilos.Side
        pdm.Alignment, pdm.Font = estilos.Alignment, estilos.Font
        yield modulo
    finally:
        for nome in [n for n in list(sys.modules) if n.startswith("openpyxl")]:
            del sys.modules[nome]
        sys.modules.update(guardados)
        for nome, valor in ligados.items():
            setattr(pdm, nome, valor)


def _workbook(nomes_de_aba):
    import openpyxl
    wb = openpyxl.Workbook()
    wb.active.title = nomes_de_aba[0]
    for nome in nomes_de_aba[1:]:
        wb.create_sheet(nome)
    return wb


def test_a_aba_canonica_continua_sendo_a_primeira_escolha(openpyxl_real):
    wb = _workbook(["Instruções", "Ficha Técnica Padrão", "Anexos"])
    assert pdm.nome_da_aba_da_ficha(wb) == "Ficha Técnica Padrão"


def test_template_com_a_aba_em_INGLES_e_aceito(openpyxl_real):
    """O template EN pode ter a aba com nome traduzido. Hoje isso derruba o
    lote inteiro com uma mensagem que não diz por quê."""
    wb = _workbook(["Instructions", "Standard Datasheet"])
    assert pdm.nome_da_aba_da_ficha(wb) == "Standard Datasheet"


@pytest.mark.parametrize("nome", [
    "Ficha Tecnica Padrao",      # sem acento
    "FICHA TÉCNICA PADRÃO",      # maiúsculas
    "Ficha Técnica Padrão ",     # espaço sobrando
    "Technical Datasheet",
    "Datasheet",
    # 2026-09-03: este NÃO é hipótese minha. É o nome da aba na ficha em
    # inglês que o usuário entregou (`4500063671.0052_enUS.xlsx`) — enquanto
    # o template `Technical_Sheet_of_PDM-R3.xlsx` ainda traz a aba com o nome
    # em português. Os dois nomes circulam na prática, e um template com dois
    # nomes de aba que eu não reconheço para o lote inteiro.
    "Standard Technical Sheet",
])
def test_variacoes_de_nome_que_o_montador_deve_aceitar(nome, openpyxl_real):
    # A aba-chamariz "Instruções" NÃO é decoração. Sem ela o workbook tem uma
    # aba só, e aba única é aceita por atalho (`len(nomes) == 1`) — a
    # normalização de nome nunca rodava, e esta parametrização inteira passava
    # sem testar nada. Descoberto em 2026-09-03, ao acrescentar
    # "Standard Technical Sheet": o caso novo passou ANTES de eu escrever a
    # linha que o faz passar.
    assert pdm.nome_da_aba_da_ficha(_workbook(["Instruções", nome])) == nome


def test_workbook_de_UMA_aba_usa_ela(openpyxl_real):
    """Template de aba única não tem ambiguidade nenhuma para resolver."""
    wb = _workbook(["QualquerNome"])
    assert pdm.nome_da_aba_da_ficha(wb) == "QualquerNome"


def test_nenhuma_aba_reconhecida_LEVANTA_com_os_nomes_encontrados(openpyxl_real):
    """A mensagem tem de dizer o que o usuário precisa fazer. 'ERRO ao gerar
    ficha' repetido 200 vezes não diz."""
    wb = _workbook(["Plan1", "Plan2"])
    with pytest.raises(ValueError) as erro:
        pdm.nome_da_aba_da_ficha(wb)
    mensagem = str(erro.value)
    assert "Plan1" in mensagem and "Plan2" in mensagem
    assert "aba" in mensagem.lower()


# O lote pela planilha de PDMs (desde 2026-10-21 a única fonte das perguntas).
from sigft.core.pdm_catalogo import PDM, Caracteristica, CatalogoPDM, Identidade  # noqa: E402

PMIB = "4500063671.0071"
PDM_USADO = "PDM.1234.001 - BOMBA, , R1"


def _catalogo(pergunta="Vazão", ajuda="l/min"):
    pdm_ = PDM(codigo="PDM.1234.001", classe="1234", titulo="BOMBA", nome_base="BOMBA", revisao=1,
               caracteristicas_em_ordem=(Caracteristica(nome=pergunta, ajuda=ajuda, sequencia=1, linha=7),),
               identidades=(Identidade(1, "BOMBA", "BOMBA"),))
    return CatalogoPDM(pdms=[pdm_], exportado_em="23/09/2026", origem="/pdms/PDMs_SAM-GM.xlsx")


def test_o_lote_PARA_quando_o_template_nao_serve(tmp_path, openpyxl_real):
    """Template errado é problema do template, não de cada ficha: falhar 200
    vezes esconde a causa. Uma mensagem, e para."""
    # DUAS abas irreconhecíveis: com uma só, `aba_da_ficha` usa ela de
    # propósito (não há ambiguidade a resolver) — ver o teste acima. É com
    # duas que o montador precisa de fato escolher, e não consegue.
    template = tmp_path / "template.xlsx"
    _workbook(["Plan1", "Plan2"]).save(template)

    resumo, log = pdm.aplicar_templates_fichas_da_planilha(
        [(PMIB, PDM_USADO, str(tmp_path))], _catalogo(), str(template))

    texto = resumo + "\n".join(log)
    assert "aba" in texto.lower()
    assert "Plan1" in texto


def test_template_bom_continua_gerando_a_ficha(tmp_path, openpyxl_real):
    """A guarda acima não pode custar o caminho feliz."""
    import openpyxl
    template = tmp_path / "template.xlsx"
    _workbook(["Ficha Técnica Padrão"]).save(template)
    destino = tmp_path / "saida"
    destino.mkdir()

    resumo, _ = pdm.aplicar_templates_fichas_da_planilha(
        [(PMIB, PDM_USADO, str(destino))], _catalogo(), str(template))

    assert "1" in resumo
    gerada = openpyxl.load_workbook(destino / f"{PMIB}.xlsx")["Ficha Técnica Padrão"]
    assert gerada.cell(row=79, column=3).value == "1 - Vazão (l/min):"


def test_template_com_a_aba_em_ingles_tambem_gera_a_ficha(tmp_path, openpyxl_real):
    """O template EN pode ter a aba com nome traduzido: as perguntas vão para
    ela, na mesma célula de sempre."""
    import openpyxl
    template = tmp_path / "template_en.xlsx"
    _workbook(["Standard Datasheet"]).save(template)
    destino = tmp_path / "saida"
    destino.mkdir()

    pdm.aplicar_templates_fichas_da_planilha(
        [(PMIB, PDM_USADO, str(destino))], _catalogo(), str(template))

    gerada = openpyxl.load_workbook(destino / f"{PMIB}.xlsx")["Standard Datasheet"]
    assert gerada.cell(row=79, column=3).value == "1 - Vazão (l/min):"


def test_o_nome_escolhido_e_o_que_a_Itaipu_usa():
    """Não é invenção: é o nome da aba na ficha que o usuário entregou."""
    assert pdm.NOME_DA_ABA_EM_INGLES == "Standard Technical Sheet"


# =============================================================================
# O NOME DA ABA NA SAÍDA (decisão do usuário, 2026-09-03)
# =============================================================================
# O template `Technical_Sheet_of_PDM-R3.xlsx` traz a aba com o nome em
# PORTUGUÊS. A ficha em inglês que o usuário entrega ao fornecedor
# (`4500063671.0052_enUS.xlsx`) tem "Standard Technical Sheet" — ou seja, ele
# renomeia à mão, ficha a ficha. Perguntado, respondeu: renomear
# automaticamente.
#
# A regra "inglês -> qual nome" mora no SERVIÇO, não na tela: a tela passa o
# IDIOMA (que é o que o usuário escolheu) e o serviço decide o nome. Princípio
# nº 2 do projeto — UI não contém regra de negócio. [2026-10-21] A ficha em
# inglês sai da planilha, com as perguntas traduzidas por um motor injetado.

def _motor_falso(textos):
    return [{"Vazão (l/min)": "Flow rate (l/min)"}.get(t, t) for t in textos]


def _montar(tmp_path, nome_da_aba, **kw):
    template = tmp_path / "template.xlsx"
    _workbook([nome_da_aba]).save(template)
    destino = tmp_path / "saida"
    destino.mkdir()
    resultado = pdm.aplicar_templates_fichas_da_planilha(
        [(PMIB, PDM_USADO, str(destino))], _catalogo(), str(template),
        pasta_traducao=str(tmp_path / "traducao"), **kw)
    return destino / f"{PMIB}.xlsx", resultado


def test_em_INGLES_a_aba_da_ficha_gerada_e_renomeada(tmp_path, openpyxl_real):
    import openpyxl
    gerada, _ = _montar(tmp_path, "Ficha Técnica Padrão", idioma="en", traduzir=_motor_falso)

    wb = openpyxl.load_workbook(gerada)
    assert pdm.NOME_DA_ABA_EM_INGLES in wb.sheetnames
    assert "Ficha Técnica Padrão" not in wb.sheetnames


def test_em_PORTUGUES_o_nome_da_aba_NAO_e_tocado(tmp_path, openpyxl_real):
    """O caminho de sempre não pode mudar por causa disto."""
    import openpyxl
    gerada, _ = _montar(tmp_path, "Ficha Técnica Padrão")   # sem `idioma`: português

    assert openpyxl.load_workbook(gerada).sheetnames == ["Ficha Técnica Padrão"]


def test_o_conteudo_traduzido_fica_na_aba_renomeada(tmp_path, openpyxl_real):
    """Renomear não pode custar a ficha: as perguntas, já em inglês, ficam
    na mesma célula de sempre."""
    import openpyxl
    gerada, _ = _montar(tmp_path, "Ficha Técnica Padrão", idioma="en", traduzir=_motor_falso)

    ws = openpyxl.load_workbook(gerada)[pdm.NOME_DA_ABA_EM_INGLES]
    assert ws.cell(row=79, column=3).value == "1 - Flow rate (l/min):"


def test_template_que_JA_esta_em_ingles_nao_quebra(tmp_path, openpyxl_real):
    """Se alguém consertar o template, o rename vira no-op — e não um erro de
    'já existe uma aba com esse nome'."""
    import openpyxl
    gerada, (resumo, log) = _montar(tmp_path, pdm.NOME_DA_ABA_EM_INGLES, idioma="en",
                                    traduzir=_motor_falso)

    assert "1" in resumo, log
    assert openpyxl.load_workbook(gerada).sheetnames == [pdm.NOME_DA_ABA_EM_INGLES]


# =============================================================================
# A tela (por AST — a tela Qt, `sigft/app_qt/views/pdm.py`)
# =============================================================================
import ast  # noqa: E402
import pathlib  # noqa: E402

VIEW = pathlib.Path(__file__).resolve().parents[1] / "sigft" / "app_qt" / "views" / "pdm.py"


def _metodo(nome):
    for no in ast.walk(ast.parse(VIEW.read_text(encoding="utf-8"))):
        if isinstance(no, ast.ClassDef) and no.name == "ModuloPDM":
            for item in no.body:
                if isinstance(item, ast.FunctionDef) and item.name == nome:
                    return item
    pytest.fail(f"metodo {nome} nao existe na tela do PDM")


def test_a_tela_passa_o_IDIOMA_e_o_motor_e_nao_o_nome_da_aba():
    """A tela não pode saber como se chama a aba em inglês, nem traduzir por
    conta própria: passa o idioma escolhido e o motor de tradução."""
    chamadas = [
        no for no in ast.walk(_metodo("_tarefa_fichas"))
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
        and no.func.attr == "aplicar_templates_fichas_da_planilha"
    ]
    assert chamadas, "a tela nao chama mais o montador?"
    nomeados = {k.arg for c in chamadas for k in c.keywords}
    assert {"idioma", "traduzir"} <= nomeados, f"argumentos repassados: {sorted(nomeados)}"
    fonte = VIEW.read_text(encoding="utf-8")
    assert "Standard Technical Sheet" not in fonte
    assert "GoogleTranslator" not in fonte and "traduzir_textos" not in fonte


def test_a_tela_NAO_amarra_a_traducao_a_chave_do_Gemini():
    """`traduzir_pdm` nasceu depois do multi-provedor. Sem `api_key`, `get_llm`
    resolve a chave do provedor REALMENTE escolhido em "Modelos de IA";
    a tela passar `get_key("GEMINI")` mandaria a chave ao provedor errado."""
    assert "get_key" not in ast.dump(_metodo("_tarefa_fichas"))
    assert "get_key" not in ast.dump(_metodo("_op2_executar"))
