r"""O montador da ficha e o template em inglês (2026-08-28).

`aplicar_templates_fichas` fazia `wb_target["Ficha Técnica Padrão"]` — nome de
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


def test_o_lote_PARA_quando_o_template_nao_serve(tmp_path, openpyxl_real):
    """Template errado é problema do template, não de cada ficha: falhar 200
    vezes esconde a causa. Uma mensagem, e para."""
    # DUAS abas irreconhecíveis: com uma só, `aba_da_ficha` usa ela de
    # propósito (não há ambiguidade a resolver) — ver o teste acima. É com
    # duas que o montador precisa de fato escolher, e não consegue.
    template = tmp_path / "template.xlsx"
    _workbook(["Plan1", "Plan2"]).save(template)
    pasta_pdms = tmp_path / "pdms"
    pasta_pdms.mkdir()
    # O PDM fonte precisa EXISTIR: sem ele o laço para em "PDM fonte não
    # encontrado" e nunca chega a abrir o template.
    import openpyxl
    openpyxl.Workbook().save(pasta_pdms / "PDM_1234_001_formatado.xlsx")

    resumo, log = pdm.aplicar_templates_fichas(
        [("4500063671.0071", "PDM.1234.001 - X", str(tmp_path))],
        str(pasta_pdms), str(template))

    texto = resumo + "\n".join(log)
    assert "aba" in texto.lower()
    assert "Plan1" in texto


def test_template_bom_continua_gerando_a_ficha(tmp_path, openpyxl_real):
    """A guarda acima não pode custar o caminho feliz."""
    import openpyxl
    template = tmp_path / "template.xlsx"
    _workbook(["Ficha Técnica Padrão"]).save(template)

    pasta_pdms = tmp_path / "pdms"
    pasta_pdms.mkdir()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.cell(row=1, column=1, value="1 - Vazão (l/min):")
    wb.save(pasta_pdms / "PDM_1234_001_formatado.xlsx")

    destino = tmp_path / "saida"
    destino.mkdir()
    resumo, _ = pdm.aplicar_templates_fichas(
        [("4500063671.0071", "PDM.1234.001 - X", str(destino))],
        str(pasta_pdms), str(template))

    assert "1" in resumo
    gerada = openpyxl.load_workbook(destino / "4500063671.0071.xlsx")["Ficha Técnica Padrão"]
    assert gerada.cell(row=79, column=3).value == "1 - Vazão (l/min):"


def test_a_ficha_em_INGLES_e_montada_com_os_PDMs_traduzidos(tmp_path, openpyxl_real):
    """O teste que fecha o pedido: template EN + pasta EN = ficha com as
    perguntas em inglês, na mesma célula de sempre."""
    import openpyxl
    template = tmp_path / "template_en.xlsx"
    _workbook(["Standard Datasheet"]).save(template)

    pasta_en = tmp_path / "pdms_en"
    pasta_en.mkdir()
    wb = openpyxl.Workbook()
    wb.active.cell(row=1, column=1, value="1 - Flow rate (l/min):")
    wb.save(pasta_en / "PDM_1234_001_formatado.xlsx")

    destino = tmp_path / "saida"
    destino.mkdir()
    pdm.aplicar_templates_fichas(
        [("4500063671.0071", "PDM.1234.001 - X", str(destino))],
        str(pasta_en), str(template))

    gerada = openpyxl.load_workbook(destino / "4500063671.0071.xlsx")["Standard Datasheet"]
    assert gerada.cell(row=79, column=3).value == "1 - Flow rate (l/min):"


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
# nº 2 do projeto — UI não contém regra de negócio.

def _template_e_pdm(tmp_path, nome_da_aba):
    import openpyxl
    template = tmp_path / "template.xlsx"
    _workbook([nome_da_aba]).save(template)
    pasta = tmp_path / "pdms"
    pasta.mkdir()
    wb = openpyxl.Workbook()
    wb.active.cell(row=1, column=1, value="1 - Flow rate (l/min):")
    wb.save(pasta / "PDM_1234_001_formatado.xlsx")
    destino = tmp_path / "saida"
    destino.mkdir()
    return template, pasta, destino


def test_em_INGLES_a_aba_da_ficha_gerada_e_renomeada(tmp_path, openpyxl_real):
    import openpyxl
    template, pasta, destino = _template_e_pdm(tmp_path, "Ficha Técnica Padrão")

    pdm.aplicar_templates_fichas(
        [("4500063671.0071", "PDM.1234.001 - X", str(destino))],
        str(pasta), str(template), idioma="en")

    wb = openpyxl.load_workbook(destino / "4500063671.0071.xlsx")
    assert pdm.NOME_DA_ABA_EM_INGLES in wb.sheetnames
    assert "Ficha Técnica Padrão" not in wb.sheetnames


def test_em_PORTUGUES_o_nome_da_aba_NAO_e_tocado(tmp_path, openpyxl_real):
    """O caminho de sempre não pode mudar por causa disto."""
    import openpyxl
    template, pasta, destino = _template_e_pdm(tmp_path, "Ficha Técnica Padrão")

    pdm.aplicar_templates_fichas(
        [("4500063671.0071", "PDM.1234.001 - X", str(destino))],
        str(pasta), str(template))          # sem `idioma`: o padrão é português

    wb = openpyxl.load_workbook(destino / "4500063671.0071.xlsx")
    assert wb.sheetnames == ["Ficha Técnica Padrão"]


def test_o_conteudo_continua_na_aba_depois_de_renomeada(tmp_path, openpyxl_real):
    """Renomear não pode custar a ficha: as perguntas têm de continuar lá,
    na mesma célula."""
    import openpyxl
    template, pasta, destino = _template_e_pdm(tmp_path, "Ficha Técnica Padrão")

    pdm.aplicar_templates_fichas(
        [("4500063671.0071", "PDM.1234.001 - X", str(destino))],
        str(pasta), str(template), idioma="en")

    gerada = openpyxl.load_workbook(destino / "4500063671.0071.xlsx")[pdm.NOME_DA_ABA_EM_INGLES]
    assert gerada.cell(row=79, column=3).value == "1 - Flow rate (l/min):"


def test_template_que_JA_esta_em_ingles_nao_quebra(tmp_path, openpyxl_real):
    """Se alguém consertar o template, o rename vira no-op — e não um erro de
    'já existe uma aba com esse nome'."""
    import openpyxl
    template, pasta, destino = _template_e_pdm(tmp_path, pdm.NOME_DA_ABA_EM_INGLES)

    resumo, log = pdm.aplicar_templates_fichas(
        [("4500063671.0071", "PDM.1234.001 - X", str(destino))],
        str(pasta), str(template), idioma="en")

    assert "1" in resumo, log
    wb = openpyxl.load_workbook(destino / "4500063671.0071.xlsx")
    assert wb.sheetnames == [pdm.NOME_DA_ABA_EM_INGLES]


def test_o_nome_escolhido_e_o_que_a_Itaipu_usa():
    """Não é invenção: é o nome da aba na ficha que o usuário entregou."""
    assert pdm.NOME_DA_ABA_EM_INGLES == "Standard Technical Sheet"


def test_a_tela_passa_o_IDIOMA_e_nao_o_nome_da_aba():
    """A tela não pode saber como se chama a aba em inglês — isso é regra de
    negócio, e regra de negócio duplicada é regra que diverge.

    Procura o argumento nomeado NA CHAMADA, e não a palavra "idioma" solta no
    método: `idioma_ficha` já aparece ali por outro motivo (escolher a pasta),
    e um `in` sobre o dump inteiro passaria sem que nada fosse repassado."""
    chamadas = [
        no for no in ast.walk(_metodo("_tarefa_fichas"))
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Attribute)
        and no.func.attr == "aplicar_templates_fichas"
    ]
    assert chamadas, "a tela nao chama mais o montador?"
    nomeados = {k.arg for c in chamadas for k in c.keywords}
    assert "idioma" in nomeados, f"argumentos repassados: {sorted(nomeados)}"
    assert "Standard Technical Sheet" not in VIEW.read_text(encoding="utf-8")


# =============================================================================
# A tela (por AST — a tela Qt, `sigft/app_qt/views/pdm.py`)
# =============================================================================
import ast
import pathlib

VIEW = pathlib.Path(__file__).resolve().parents[1] / "sigft" / "app_qt" / "views" / "pdm.py"


def _classe_pdm():
    arvore = ast.parse(VIEW.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.ClassDef) and no.name.startswith("Modulo"):
            return no
    pytest.fail("a classe da tela do PDM sumiu")


def _metodo(nome):
    for no in _classe_pdm().body:
        if isinstance(no, ast.FunctionDef) and no.name == nome:
            return no
    pytest.fail(f"metodo {nome} nao existe na tela do PDM")


def test_a_tela_tem_o_seletor_de_idioma_e_o_botao_de_traduzir():
    fonte = VIEW.read_text(encoding="utf-8")
    assert "idioma_ficha" in fonte
    assert "_op1_traduzir" in fonte


def test_o_montador_recebe_a_pasta_do_IDIOMA_escolhido():
    """O erro que isto impede é o pior possível aqui: ficha em inglês montada
    com as perguntas em português, que não se denuncia sozinha."""
    fonte = ast.unparse(_metodo("_op2_executar"))
    assert "self.entry_destino_en.text() if em_ingles else self.entry_dest.text()" in fonte
    assert "self.idioma_ficha.get()" in fonte


def test_traduzir_recusa_gravar_por_cima_da_pasta_de_origem():
    """Origem == destino apagaria os PDMs em português — e eles são a fonte
    de tudo, inclusive de uma retradução futura."""
    fonte = ast.dump(_metodo("_op1_traduzir"))
    assert "abspath" in fonte


def test_a_tela_usa_o_servico_e_nao_traduz_por_conta_propria():
    """Princípio nº 2: a tela escolhe pasta e mostra log; quem traduz é o
    serviço."""
    fonte = VIEW.read_text(encoding="utf-8")
    assert "traducao_pdm.traduzir_pasta" in fonte
    assert "GoogleTranslator" not in fonte
