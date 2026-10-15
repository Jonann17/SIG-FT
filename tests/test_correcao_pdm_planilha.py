r"""A lista de fichas da tela de correção de PDM, e a PRÉVIA (E5, parte 1).

Esta é a camada que a tela usa e que **não pode morar nela**: ler o
`_STATUS_PMIB`, montar as linhas e calcular a prévia são regras, e regra de
negócio não vive em Tk (princípio 2 da arquitetura).

⚠️ O PONTO DELICADO É A PRÉVIA, e ele é sobre o que ela **não pode dizer**.

O catálogo guarda só a revisão VIGENTE de cada PDM. Numa atualização de
revisão o código é o mesmo dos dois lados, então comparar catálogo com
catálogo daria 100% sempre -- um número bonito que não significa nada, porque
o que a ficha tem é a revisão ANTIGA, que o catálogo não tem.

Prévia que mente é pior que prévia ausente: ela é exatamente o que o usuário
vai olhar antes de autorizar uma operação que apaga características.

Plano em `docs/refatoracao/CORRECAO_PDM.md` (etapa E5).
"""
from __future__ import annotations

from sigft.core.pdm_catalogo import PDM, CatalogoPDM
from sigft.services import correcao_pdm_planilha as planilha


# =============================================================================
# Dublês
# =============================================================================
class _Aba:
    """Worksheet duck-typed, do mesmo jeito que `tests/test_status_sheet.py`
    faz -- assim a leitura é testada sem openpyxl instalado."""

    def __init__(self, linhas):
        self.linhas = linhas
        self.max_row = len(linhas)
        self.max_column = max((len(x) for x in linhas), default=0)

    def cell(self, row, column):
        class _C:
            pass
        c = _C()
        linha = self.linhas[row - 1] if 1 <= row <= len(self.linhas) else []
        c.value = linha[column - 1] if 1 <= column <= len(linha) else None
        return c


def _aba_padrao():
    return _Aba([
        ["Planilha de controle", None, None],
        ["CÓDIGO PMIB", "TEXTO BREVE", "PDM usado"],
        ["4500063671.0242", "PROTETOR DE SURTO", "PDM.5920.020 - PROTETOR, SURTO, R1"],
        ["4500063671.0243", "CHAVE SECCIONADORA", "PDM.5925.001 - CHAVE, SECCIONADORA, R1"],
    ])


def _catalogo(*pdms):
    return CatalogoPDM(list(pdms))


def _pdm(codigo, titulo, caracteristicas, classe="5920"):
    return PDM(codigo=codigo, classe=classe, titulo=titulo,
               nome_base=titulo.split(",")[0], modificador="",
               caracteristicas=tuple(caracteristicas), revisao=1)


# =============================================================================
# A. Ler o STATUS_PMIB
# =============================================================================
def test_le_pmib_descricao_e_pdm_atual():
    fichas = planilha.ler_fichas(_aba_padrao())

    assert [f.pmib for f in fichas] == ["4500063671.0242", "4500063671.0243"]
    assert fichas[0].descricao == "PROTETOR DE SURTO"
    assert fichas[0].pdm_atual == "PDM.5920.020 - PROTETOR, SURTO, R1"


def test_o_cabecalho_nao_precisa_estar_na_primeira_linha():
    """As planilhas reais trazem título e linhas em branco em cima. Quem acha o
    cabeçalho é `core.excel.headers`, e não uma contagem fixa."""
    fichas = planilha.ler_fichas(_Aba([
        [None, None, None],
        ["Relatório de fichas", None, None],
        [None, None, None],
        ["CÓDIGO PMIB", "TEXTO BREVE", "PDM usado"],
        ["4500063671.0242", "X", "PDM.5920.020"],
    ]))

    assert len(fichas) == 1


def test_linha_sem_pmib_e_ignorada():
    """Planilha real tem linha em branco no meio e total no fim."""
    fichas = planilha.ler_fichas(_Aba([
        ["CÓDIGO PMIB", "TEXTO BREVE", "PDM usado"],
        ["4500063671.0242", "X", "PDM.5920.020"],
        [None, None, None],
        ["", "TOTAL", ""],
    ]))

    assert len(fichas) == 1


def test_planilha_sem_a_coluna_de_pmib_devolve_vazio():
    """Devolver vazio em vez de levantar: a tela mostra "nenhuma ficha" e a
    pessoa escolhe outro arquivo."""
    assert planilha.ler_fichas(_Aba([["A", "B"], [1, 2]])) == []


def test_planilha_sem_a_coluna_de_pdm_ainda_lista_as_fichas():
    """Sem o PDM atual dá para escolher o novo à mão; sem a lista de fichas não
    dá para nada."""
    fichas = planilha.ler_fichas(_Aba([
        ["CÓDIGO PMIB", "TEXTO BREVE"],
        ["4500063671.0242", "X"],
    ]))

    assert len(fichas) == 1 and fichas[0].pdm_atual == ""


# =============================================================================
# B. A prévia -- e o que ela se RECUSA a dizer
# =============================================================================
def test_previa_de_troca_entre_codigos_diferentes_conta_o_que_casa():
    cat = _catalogo(
        _pdm("PDM.3010.001", "ACOPLAMENTO", ["MATERIAL", "DIAMETRO", "PESO"]),
        _pdm("PDM.4320.031", "COLUNA FLANGE, ACOPLAMENTO",
             ["MATERIAL", "DIAMETRO", "ALTURA", "NORMA"]),
    )

    texto = planilha.previa(cat, "PDM.3010.001 - ACOPLAMENTO, R1", "PDM.4320.031")

    assert "2 de 3" in texto


def test_previa_de_ATUALIZACAO_DE_REVISAO_nao_inventa_um_numero():
    """⚠️ O catálogo só tem a revisão vigente. Numa atualização o código é o
    mesmo dos dois lados, então comparar catálogo com catálogo daria 100%
    sempre -- e o que a ficha tem é a revisão ANTIGA, que o catálogo não tem.

    Prévia que mente é pior que prévia ausente: é justamente ela que o usuário
    vai olhar antes de autorizar uma operação que apaga características.
    """
    cat = _catalogo(_pdm("PDM.5920.020", "PROTETOR, SURTO", ["A", "B", "C"]))

    texto = planilha.previa(cat, "PDM.5920.020 - PROTETOR, SURTO, R1",
                            "PDM.5920.020")

    assert "100" not in texto
    assert "3 de 3" not in texto
    assert "revis" in texto.lower()


def test_previa_sem_pdm_novo_nao_diz_nada():
    cat = _catalogo(_pdm("PDM.5920.020", "PROTETOR, SURTO", ["A"]))

    assert planilha.previa(cat, "PDM.5920.020 - X, R1", "") == ""


def test_previa_com_pdm_fora_do_catalogo_diz_que_nao_sabe():
    """Silêncio aqui viraria "0 de N", que a pessoa leria como "não recupera
    nada" -- e o certo é "não sei dizer"."""
    cat = _catalogo(_pdm("PDM.5920.020", "PROTETOR, SURTO", ["A"]))

    texto = planilha.previa(cat, "PDM.5920.020 - X, R1", "PDM.9999.999")

    assert "0 de" not in texto
    assert texto


def test_previa_sem_catalogo_nao_quebra():
    """O catálogo é opcional na tela: sem a planilha-mestra carregada, a
    correção ainda tem de rodar."""
    assert planilha.previa(None, "PDM.1", "PDM.2") == ""


def test_previa_nao_usa_travessao():
    cat = _catalogo(
        _pdm("PDM.3010.001", "ACOPLAMENTO", ["MATERIAL"]),
        _pdm("PDM.4320.031", "COLUNA", ["MATERIAL", "NORMA"]),
    )

    for atual, novo in (("PDM.3010.001 - X, R1", "PDM.4320.031"),
                        ("PDM.3010.001 - X, R1", "PDM.3010.001"),
                        ("PDM.3010.001 - X, R1", "PDM.9999.999")):
        assert "—" not in planilha.previa(cat, atual, novo)


# =============================================================================
# C. A ação em massa "só atualizar a revisão"
# =============================================================================
def test_so_atualizar_a_revisao_devolve_o_CODIGO_do_pdm_atual():
    """*"Um clique resolve as 25 fichas"*: o portal já atribui a revisão
    vigente sozinho, então o destino é o próprio código."""
    assert planilha.so_a_revisao(
        "PDM.5920.020 - PROTETOR, SURTO, R1") == "PDM.5920.020"


def test_so_atualizar_a_revisao_de_ficha_sem_pdm_devolve_vazio():
    """Sem PDM atual não há código para copiar, e inventar um seria escolher um
    PDM no lugar do usuário."""
    assert planilha.so_a_revisao("") == ""
    assert planilha.so_a_revisao("SEM CODIGO NENHUM") == ""


# =============================================================================
# D. O que sai da tela para o serviço
# =============================================================================
def test_so_as_fichas_COM_pdm_novo_entram_no_lote():
    """Uma linha sem destino não é erro: é uma ficha que o usuário não quis
    mexer nesta rodada."""
    fichas = [planilha.FichaParaCorrigir("1", "A", "PDM.1", "PDM.2"),
              planilha.FichaParaCorrigir("2", "B", "PDM.3", "")]

    assert planilha.lote(fichas) == [("1", "PDM.2")]


def test_lote_vazio_quando_ninguem_escolheu_nada():
    fichas = [planilha.FichaParaCorrigir("1", "A", "PDM.1", "")]

    assert planilha.lote(fichas) == []


# =============================================================================
# E. A borda -- abrir o arquivo
# =============================================================================
class _Workbook:
    def __init__(self, abas):
        self.abas = abas
        self.sheetnames = list(abas)
        self.fechado = False

    def __getitem__(self, nome):
        return self.abas[nome]

    def close(self):
        self.fechado = True


def test_acha_a_aba_mesmo_com_a_grafia_diferente(monkeypatch):
    """Planilhas reais escrevem "LISTA DE MATERIAIS" e "Lista de materiais".
    Cair fora por causa da caixa seria "nenhuma ficha" num arquivo cheio."""
    wb = _Workbook({"Capa": _Aba([]), "LISTA DE MATERIAIS": _aba_padrao()})

    assert planilha._escolher_aba(wb) is wb.abas["LISTA DE MATERIAIS"]


def test_sem_nenhuma_variante_fica_com_a_PRIMEIRA_aba():
    """Melhor palpite do que desistir: a planilha do usuário pode ter a aba
    renomeada, e a lista de fichas costuma ser a primeira."""
    wb = _Workbook({"Materiais": _aba_padrao()})

    assert planilha._escolher_aba(wb) is wb.abas["Materiais"]


def test_arquivo_sem_aba_nenhuma_devolve_vazio():
    assert planilha._escolher_aba(_Workbook({})) is None
