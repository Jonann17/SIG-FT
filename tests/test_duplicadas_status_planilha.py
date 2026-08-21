r"""
COMPLETO / INCOMPLETO no `_STATUS_PMIB` (CP 6.3).

> *"Se por fim você não conseguir, deixa em branco e daí na hora de completar o
> _STATUS_PMIB você coloca na coluna de Informações Gerais como INCOMPLETO para
> a ficha. Para as colunas que você conseguir preencher tudo, você coloca como
> COMPLETO."*

O fluxo antigo marcava as QUATRO colunas como COMPLETO para toda ficha que não
tivesse estourado, sem olhar seção nenhuma. Planilha que diz COMPLETO no que
ficou pela metade é pior do que planilha vazia: ninguém volta a conferir o que
está marcado como pronto.
"""
import pytest

from sigft import config
from sigft.core.excel import status_sheet
from sigft.services import duplicadas_injetor as injetor
from sigft.services import duplicadas_robo as robo


def _ficha_com(**secoes):
    resultado = robo.ResultadoDaFicha("4500063671.1418", "4500063671.1263")
    for nome, ok in secoes.items():
        resultado.registrar(injetor.ResultadoDaSecao(nome, ok, ""))
    return resultado


# ===========================================================================
# Qual valor vai em qual coluna
# ===========================================================================
def test_tudo_certo_marca_completo_nas_duas_colunas():
    resultado = _ficha_com(fabricante=True, referencia=True, fornecedor=True,
                           caracteristicas=True)

    assert robo.status_por_secao(resultado) == {
        config.COL_INFO_GERAIS: status_sheet.VALOR_COMPLETO,
        config.COL_CARACT_TECNICAS: status_sheet.VALOR_COMPLETO,
    }


def test_uma_secao_falha_e_a_COLUNA_dela_vira_incompleto():
    """A coluna é a unidade: basta uma das seções que a alimentam falhar."""
    resultado = _ficha_com(fabricante=True, referencia=False, fornecedor=True,
                           caracteristicas=True)

    marcas = robo.status_por_secao(resultado)

    assert marcas[config.COL_INFO_GERAIS] == status_sheet.VALOR_INCOMPLETO
    assert marcas[config.COL_CARACT_TECNICAS] == status_sheet.VALOR_COMPLETO


def test_colunas_que_o_robo_nem_tentou_ficam_de_fora():
    """Condições e Documentos são o CP 6.4. Escrever COMPLETO nelas seria
    mentira; escrever INCOMPLETO seria ruído, porque a ficha ainda vai passar
    pelo robô antigo ou pela mão."""
    marcas = robo.status_por_secao(_ficha_com(caracteristicas=True))

    assert set(marcas) == {config.COL_CARACT_TECNICAS}
    assert config.COL_CONDICOES not in marcas


def test_ficha_que_estourou_antes_de_qualquer_secao_nao_marca_nada():
    """Sem seção nenhuma não há o que afirmar sobre a planilha."""
    resultado = robo.ResultadoDaFicha("X", "Y")
    resultado.erro_fatal = "não achei a ficha original"

    assert robo.status_por_secao(resultado) == {}


# ===========================================================================
# A escrita na planilha
# ===========================================================================
class _PainelFalso:
    instancias = []

    def __init__(self, caminho, aba=None):
        self.caminho = caminho
        self.marcacoes = []
        self.salvou = False
        self.fechou = False
        self.linha_encontrada = 7
        _PainelFalso.instancias.append(self)

    def abrir(self, **_kwargs):
        pass

    def buscar_linha(self, _pmib):
        return self.linha_encontrada

    def marcar_linha(self, linha, colunas, valor=status_sheet.VALOR_COMPLETO):
        self.marcacoes.append((linha, sorted(colunas), valor))

    def salvar(self, **_kwargs):
        self.salvou = True
        return True

    def fechar(self):
        self.fechou = True


@pytest.fixture(autouse=True)
def _painel(monkeypatch):
    _PainelFalso.instancias = []
    monkeypatch.setattr(robo.status_sheet, "StatusPMIB", _PainelFalso)
    return _PainelFalso


def test_escreve_valores_DIFERENTES_em_colunas_diferentes():
    """INFO. GERAIS incompleta e CARACT. TÉCNICAS completa é o caso NORMAL
    enquanto o CP 6.4 não fecha -- uma chamada só, com um valor só, marcaria as
    duas igual."""
    resultado = _ficha_com(fabricante=True, referencia=True, fornecedor=False,
                           caracteristicas=True)

    marcadas, falhas = robo.marcar_status_na_planilha(
        "x.xlsx", [resultado], callback_log=lambda _m: None)

    painel = _PainelFalso.instancias[0]
    valores = {valor: colunas for _linha, colunas, valor in painel.marcacoes}
    assert valores[status_sheet.VALOR_COMPLETO] == [config.COL_CARACT_TECNICAS]
    assert valores[status_sheet.VALOR_INCOMPLETO] == [config.COL_INFO_GERAIS]
    assert (marcadas, falhas) == (1, [])


def test_salva_e_fecha_a_planilha():
    robo.marcar_status_na_planilha("x.xlsx", [_ficha_com(caracteristicas=True)],
                                   callback_log=lambda _m: None)

    painel = _PainelFalso.instancias[0]
    assert painel.salvou is True and painel.fechou is True


def test_ficha_que_nao_esta_na_planilha_vira_falha_e_nao_para_o_resto():
    """Perder o registro de 14 fichas porque a 15ª sumiu da planilha seria
    trocar um problema pequeno por um grande."""
    ausente = _ficha_com(caracteristicas=True)
    presente = _ficha_com(caracteristicas=True)

    chamadas = {"n": 0}
    original = _PainelFalso.buscar_linha

    def buscar_linha(self, pmib):
        chamadas["n"] += 1
        return None if chamadas["n"] == 1 else original(self, pmib)

    _PainelFalso.buscar_linha = buscar_linha
    try:
        marcadas, falhas = robo.marcar_status_na_planilha(
            "x.xlsx", [ausente, presente], callback_log=lambda _m: None)
    finally:
        _PainelFalso.buscar_linha = original

    assert marcadas == 1
    assert len(falhas) == 1 and "não achei a linha" in falhas[0]


def test_erro_ao_abrir_a_planilha_nao_derruba_o_lote():
    def abrir_que_estoura(self, **_kwargs):
        raise OSError("arquivo aberto no Excel")

    _PainelFalso.abrir = abrir_que_estoura
    try:
        marcadas, falhas = robo.marcar_status_na_planilha(
            "x.xlsx", [_ficha_com(caracteristicas=True)], callback_log=lambda _m: None)
    finally:
        _PainelFalso.abrir = lambda self, **_k: None

    assert marcadas == 0
    assert len(falhas) == 1 and "OSError" in falhas[0]


def test_ficha_sem_secao_nenhuma_nem_abre_a_planilha():
    resultado = robo.ResultadoDaFicha("X", "Y")
    resultado.erro_fatal = "estourou"

    robo.marcar_status_na_planilha("x.xlsx", [resultado], callback_log=lambda _m: None)

    assert _PainelFalso.instancias == []


# ===========================================================================
# As seções que o robô AINDA NÃO faz
# ===========================================================================
def test_secao_pendente_marca_a_coluna_como_INCOMPLETO():
    """⚠️ REVERSÃO DE UMA DECISÃO MINHA, motivada por um relato do usuário.

    Eu tinha escrito que seção não tentada NÃO devia ser escrita na planilha,
    "para não fazer ruído". Em 2026-08-17 ele reportou que "documentos e
    condições já estão preenchendo" testando pelo botão do robô NOVO -- que não
    tem uma linha de código para nenhum dos dois; o que ele viu era resíduo de
    uma rodada anterior do robô antigo na mesma ficha.

    Coluna em branco não diz nada. Coluna escrita INCOMPLETO teria dito a
    verdade antes de a ficha ser considerada pronta. O "ruído" que eu quis
    evitar era exatamente a informação que faltou.
    """
    resultado = robo.ResultadoDaFicha("A", "B")
    resultado.registrar(injetor.ResultadoDaSecao("caracteristicas", True))
    resultado.registrar(injetor.ResultadoDaSecao("condicoes", False, pendente=True))
    resultado.registrar(injetor.ResultadoDaSecao("documentos", False, pendente=True))
    resultado.registrar(injetor.ResultadoDaSecao("imagens", False, pendente=True))

    marcas = robo.status_por_secao(resultado)

    assert marcas[config.COL_CARACT_TECNICAS] == status_sheet.VALOR_COMPLETO
    assert marcas[config.COL_CONDICOES] == status_sheet.VALOR_INCOMPLETO
    assert marcas[config.COL_DOCS_IMAGENS] == status_sheet.VALOR_INCOMPLETO


def test_documentos_e_imagens_juntos_na_mesma_coluna():
    """A coluna é uma só; basta um dos dois faltar para ela não estar completa."""
    resultado = robo.ResultadoDaFicha("A", "B")
    resultado.registrar(injetor.ResultadoDaSecao("documentos", True))
    resultado.registrar(injetor.ResultadoDaSecao("imagens", False))

    assert robo.status_por_secao(resultado)[config.COL_DOCS_IMAGENS] == \
        status_sheet.VALOR_INCOMPLETO
