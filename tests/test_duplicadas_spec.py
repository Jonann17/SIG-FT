r"""
Regras de negócio da ficha duplicada (CP 6.1).

Tudo aqui vem das respostas do usuário em 2026-08-11. O valor de testar isto
ANTES de escrever qualquer RPA é que estas são as decisões que estragam ficha
em silêncio -- referência errada, característica errada, seção copiada que não
devia. Erro de seletor o portal denuncia na hora; erro de regra, não.
"""
import pytest

from sigft.services import duplicadas_spec as spec


# ===========================================================================
# Identificação
# ===========================================================================
@pytest.mark.parametrize("valor", [
    "PDM.9900.000 - FICHA PMIB, DUPLICADA, R0",
    "PDM.9900.000 - FICHA PMIB, DUPLICADA, R1",   # revisão muda
    "PDM.9900.000",                                # só o prefixo
    "  pdm.9900.000 - ficha pmib, duplicada  ",    # caixa e espaço
])
def test_reconhece_a_ficha_duplicada_pelo_prefixo(valor):
    """O sufixo carrega revisão e descrição, que mudam por motivo alheio a
    esta decisão. Prender a identificação ao texto inteiro criaria um jeito de
    o módulo parar de achar fichas depois de uma revisão do PDM."""
    assert spec.e_ficha_duplicada(valor) is True


@pytest.mark.parametrize("valor", [
    "PDM.4320.002 - MOTOBOMBA ACIONAMENTO ELETRICO",
    "", "   ", None, "nan",
    "FICHA PMIB, DUPLICADA",          # a descrição sem o PDM não basta
    "XPDM.9900.000",                  # prefixo tem de ser o COMEÇO
])
def test_nao_confunde_outras_fichas_com_duplicada(valor):
    assert spec.e_ficha_duplicada(valor) is False


def test_celula_vazia_do_pandas_nao_vira_duplicada():
    # `nan` é o que o pandas devolve para célula em branco; tratá-lo como
    # texto faria toda ficha sem PDM entrar no lote de duplicação.
    assert spec.e_ficha_duplicada(float("nan")) is False


# ===========================================================================
# Colunas com grafia variável
# ===========================================================================
@pytest.mark.parametrize("cabecalho", ["PDM usado", "PDMs usados", "PDM USADO", " pdm usado "])
def test_acha_a_coluna_do_pdm_nas_grafias_conhecidas(cabecalho):
    assert spec.achar_coluna([cabecalho, "OUTRA"], spec.COLUNAS_PDM_USADO) == cabecalho


def test_acha_a_referencia_do_fornecedor_por_codigo_cmi_ou_ge():
    """O usuário citou os dois nomes para a MESMA informação."""
    assert spec.achar_coluna(["CÓDIGO CMI"], spec.COLUNAS_REFERENCIA_FORNECEDOR) == "CÓDIGO CMI"
    assert spec.achar_coluna(["CODIGO GE"], spec.COLUNAS_REFERENCIA_FORNECEDOR) == "CODIGO GE"


def test_coluna_ausente_devolve_none_em_vez_de_estourar():
    assert spec.achar_coluna(["A", "B"], spec.COLUNAS_PDM_USADO) is None


def test_a_ordem_das_candidatas_decide_o_empate():
    # Planilha com as duas grafias: vence a declarada primeiro, não a ordem
    # das colunas no arquivo.
    achada = spec.achar_coluna(["PDMs usados", "PDM usado"], spec.COLUNAS_PDM_USADO)

    assert achada == "PDM usado"


# ===========================================================================
# A sequência de referências (a regra do 'D)
# ===========================================================================
def test_tenta_primeiro_o_codigo_cru():
    """A maioria das fichas duplicadas não colide com nada; começar pelo
    sufixo sujaria toda referência sem necessidade."""
    assert spec.sequencia_de_referencias("2904616")[0] == "2904616"


def test_os_sufixos_seguem_a_ordem_ditada_pelo_usuario():
    sequencia = spec.sequencia_de_referencias("2904616")

    assert sequencia[1] == "2904616'D1"
    assert sequencia[2] == "2904616'D2"
    assert sequencia[3] == "2904616'D3"


def test_a_sequencia_tem_teto():
    """Sem teto, um portal que rejeite TUDO (campo travado, sessão expirada,
    outra mensagem de erro lida como colisão) faz o robô tentar para sempre,
    escrevendo no campo a cada volta."""
    sequencia = spec.sequencia_de_referencias("X")

    assert len(sequencia) == spec.MAX_TENTATIVAS_REFERENCIA + 1
    assert sequencia[-1] == f"X'D{spec.MAX_TENTATIVAS_REFERENCIA}"


def test_codigo_vazio_nao_gera_tentativa_nenhuma():
    # Sem código do material não há o que digitar; gerar "'D1" sozinho
    # escreveria lixo no portal.
    for vazio in ("", "   ", None):
        assert spec.sequencia_de_referencias(vazio) == []


def test_espaco_em_volta_do_codigo_e_removido():
    assert spec.sequencia_de_referencias("  2904616 ")[0] == "2904616"


# ===========================================================================
# Reconhecer a mensagem de colisão (e só ela)
# ===========================================================================
@pytest.mark.parametrize("mensagem", [
    "A referência já existe!",
    "a referencia ja existe",
    "La referencia ya existe",   # a tela alterna de idioma
])
def test_reconhece_a_mensagem_de_referencia_repetida(mensagem):
    assert spec.e_erro_de_referencia_repetida(mensagem) is True


@pytest.mark.parametrize("mensagem", [
    "Campo obrigatório!", "Sessão expirada", "", None, "Erro ao salvar",
])
def test_outro_erro_nao_e_tratado_como_colisao(mensagem):
    """Se qualquer erro virasse colisão, o robô gastaria 20 tentativas com
    sufixo escondendo o problema de verdade -- e ainda deixaria a referência
    suja no campo."""
    assert spec.e_erro_de_referencia_repetida(mensagem) is False


# ===========================================================================
# A ficha original, lida das OBSERVAÇÕES
# ===========================================================================
def test_extrai_o_codigo_quando_a_celula_tem_so_ele():
    assert spec.extrair_ficha_original("4500063671.1471") == "4500063671.1471"


def test_extrai_o_codigo_de_dentro_de_um_texto():
    assert spec.extrair_ficha_original(
        "Duplicada da ficha 4500063671.1471 conforme e-mail"
    ) == "4500063671.1471"


def test_celula_vazia_devolve_none():
    for vazio in ("", "   ", None, "nan"):
        assert spec.extrair_ficha_original(vazio) is None


def test_texto_sem_codigo_atravessa_para_o_rpa_tentar():
    # Melhor tentar e o log mostrar o que foi digitado do que descartar em
    # silêncio uma observação que talvez seja o código em outro formato.
    assert spec.extrair_ficha_original("ver ficha do motor") == "ver ficha do motor"


# ===========================================================================
# O bloqueio das Condições
# ===========================================================================
def test_condicoes_esta_bloqueada_ate_a_lista_financeira_ser_confirmada():
    """O usuário disse "copiar tudo, exceto a parte financeira" -- mas não
    disse QUAIS campos são a parte financeira. Copiar dado financeiro de uma
    ficha para outra é erro caro e silencioso; até a lista existir campo a
    campo, esta seção não roda sozinha."""
    assert "condicoes" in spec.SECOES_BLOQUEADAS_ATE_CONFIRMACAO
    assert "condicoes" in spec.SECOES_A_REPLICAR  # continua no escopo, só não liberada


def test_as_outras_tres_secoes_nao_estao_bloqueadas():
    liberadas = set(spec.SECOES_A_REPLICAR) - set(spec.SECOES_BLOQUEADAS_ATE_CONFIRMACAO)

    assert liberadas == {"fabricantes_fornecedores", "caracteristicas_tecnicas", "documentos_imagens"}
