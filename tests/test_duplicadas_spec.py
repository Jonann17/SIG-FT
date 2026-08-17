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


def test_fracao_com_mais_de_4_digitos_e_encontrada():
    r"""CONTRAPROVA DE UM DEFEITO MEU, corrigido em 2026-08-17.

    A primeira versão de `extrair_ficha_original` tinha `re.search` próprio,
    com o padrão `\d{10}\.\d{4}` -- fração de EXATAMENTE 4 dígitos. O extrator
    canônico do projeto (`pmib_codes.find_pmib_code_in_text`, CP 1.2, réplica
    do `montar_fila_processamento` do módulo antigo) aceita `\d{10}\.\d+`.

    Com o meu, `4500063671.11651` casaria os 4 primeiros dígitos da fração e
    devolveria `4500063671.1165` -- uma ficha DIFERENTE e EXISTENTE. O robô
    copiaria da ficha errada sem nenhum sintoma. Este teste falha se alguém
    reintroduzir a implementação própria.
    """
    assert spec.extrair_ficha_original(
        "Duplicada da 4500063671.11651"
    ) == "4500063671.11651"


def test_extracao_delega_no_extrator_canonico():
    """Uma implementação por conceito (princípio nº 1): "achar código PMIB em
    texto livre" é um conceito só, e ele já existe em `core.excel.pmib_codes`.

    O teste é de DELEGAÇÃO, não de resultado: troca o canônico por um duplo e
    exige que o resultado dele apareça. Uma reimplementação passa nos testes
    de resultado acima e falha neste.
    """
    chamadas = []

    class _CanonicoFalso:
        @staticmethod
        def find_pmib_code_in_text(texto):
            chamadas.append(texto)
            return "SENTINELA"

    original = spec.pmib_codes
    spec.pmib_codes = _CanonicoFalso
    try:
        assert spec.extrair_ficha_original("qualquer coisa") == "SENTINELA"
    finally:
        spec.pmib_codes = original

    assert chamadas == ["qualquer coisa"]


# ===========================================================================
# Condições: a exclusão é uma ABA, não uma lista de campos
# ===========================================================================
# Esclarecido em 2026-08-11: "Condições financeira é uma seção interna dentro
# das condições". Isso desbloqueou a seção -- a primeira leitura era "existe
# uma lista de campos financeiros espalhados", que exigiria levantamento campo
# a campo.

@pytest.mark.parametrize("nome", [
    "Condições financeiras",   # nome no modo EDIÇÃO
    "Financeira",              # nome no modo VISUALIZAÇÃO
    "financeiras", "FINANCEIRA", "Condicoes financeiras",  # sem acento, caixa
])
def test_reconhece_a_aba_financeira_nos_dois_modos(nome):
    assert spec.e_aba_financeira(nome) is True


@pytest.mark.parametrize("nome", [
    "Condições de armazenamento", "Armazenamento e transporte",
    "Condições de manutenção", "Manutenção e descarte",
    "Condições de descarte", "", None,
])
def test_nao_confunde_as_outras_abas_com_a_financeira(nome):
    """Um falso positivo deixa de copiar uma aba; um falso NEGATIVO copia dado
    financeiro de uma ficha para outra -- e esse fica plausível na tela e
    ninguém confere. Por isso a lista das outras abas é testada nominalmente."""
    assert spec.e_aba_financeira(nome) is False


def test_a_financeira_fica_fora_da_copia_no_modo_visualizacao():
    copiar = spec.abas_de_condicoes_a_copiar("visualizacao")

    assert copiar == ("Armazenamento e transporte", "Manutenção e descarte")
    assert spec.ABA_CONDICOES_FINANCEIRA_VISUALIZACAO not in copiar


def test_a_financeira_fica_fora_da_copia_no_modo_edicao():
    copiar = spec.abas_de_condicoes_a_copiar("edicao")

    assert len(copiar) == 4
    assert spec.ABA_CONDICOES_FINANCEIRA_EDICAO not in copiar


def test_os_dois_modos_tem_contagem_de_abas_DIFERENTE():
    """Não é erro de levantamento: o portal agrupa as Condições em 5 abas na
    edição e em 3 na visualização. O extrator lê de um lado e o injetor
    escreve no outro, então confundir os dois conjuntos daria "aba não
    encontrada" no meio do fluxo."""
    assert len(spec.ABAS_CONDICOES_EDICAO) == 5
    assert len(spec.ABAS_CONDICOES_VISUALIZACAO) == 3


def test_condicoes_nao_esta_mais_bloqueada():
    assert spec.SECOES_BLOQUEADAS_ATE_CONFIRMACAO == ()
    assert "condicoes" in spec.SECOES_A_REPLICAR


# ===========================================================================
# Ler a original em modo VISUALIZAÇÃO
# ===========================================================================
def test_a_leitura_da_original_e_no_modo_visualizacao():
    """Decisão de arquitetura, não conveniência: a ficha original raramente
    está "Em Elaboração" (na tela levantada estava "Em Análise ITAIPU"), e
    nesse estado o portal mostra os valores como TEXTO, não como campo. Um
    extrator que procure `input[value]`, como faz o `upload_conditions`, não
    acha nada e devolve ficha vazia SEM ERRO."""
    assert spec.MODO_LEITURA_ORIGINAL == "visualizacao"


def test_a_busca_nao_pode_assumir_uma_aba_de_status():
    # A original pode estar em qualquer um dos 7 status da lista.
    assert len(spec.ABAS_DE_STATUS_DA_LISTA) == 7
    for status in ("Em Elaboração", "Em Análise ITAIPU", "Aprovado pela ITAIPU", "Cancelado"):
        assert status in spec.ABAS_DE_STATUS_DA_LISTA


# ===========================================================================
# Imagens
# ===========================================================================
def test_imagens_vao_por_ARQUIVO_e_nao_por_area_de_transferencia():
    """O fluxo manual é copiar/colar a figura. Para o robô a recomendação é
    outra, e o motivo é técnico: colar imagem da área de transferência num
    campo de upload depende do sistema operacional, do foco da janela e de o
    navegador aceitar `paste` sintético. O diálogo aceita arquivo e toda imagem
    do portal tem URL -- baixar e subir dá o mesmo resultado sem clipboard no
    caminho."""
    assert spec.IMAGENS_VIA_ARQUIVO is True


def test_o_limite_de_arquivos_por_envio_e_o_que_o_dialogo_declara():
    assert spec.MAX_IMAGENS_POR_ENVIO == 10


def test_a_descricao_da_imagem_e_a_mesma_nos_dois_idiomas():
    """Foi o que o usuário especificou: a descrição do item, que no
    `_STATUS_PMIB` é UMA coluna. Traduzir por conta própria seria inventar
    dado."""
    assert spec.descricao_das_imagens("FONTE, ALIMENTACAO") == {
        "es": "FONTE, ALIMENTACAO", "pt": "FONTE, ALIMENTACAO",
    }


def test_descricao_vazia_devolve_none():
    for vazio in ("", "   ", None, "nan"):
        assert spec.descricao_das_imagens(vazio) is None


# ===========================================================================
# Divergência com a regra do módulo antigo
# ===========================================================================
# O antigo procurava a palavra "DUPLICADA" em qualquer posição; o novo casa o
# prefixo `PDM.9900.000`, como o usuário pediu. Concordam na planilha real, e
# a diferença só aparece nas bordas -- que é exatamente onde tem de aparecer,
# em vez de sumir.

def test_pdm_correto_nao_e_suspeito():
    """Já entrou na lista pela regra boa; avisar de novo seria ruído."""
    assert spec.parece_duplicada_sem_o_pdm(
        "PDM.9900.000 - FICHA PMIB, DUPLICADA, R0") is False


def test_texto_duplicada_sem_o_codigo_do_pdm_e_suspeito():
    """A regra antiga pegaria; a nova não. Ficar de fora em silêncio é o erro
    caro -- ninguém procura o que não apareceu na lista."""
    assert spec.parece_duplicada_sem_o_pdm("FICHA PMIB, DUPLICADA, R0") is True


def test_outro_pdm_com_duplicada_na_descricao_e_suspeito():
    """Aqui a regra antiga é que erra (pega demais). O aviso deixa o usuário
    ver que a divergência existe, sem mudar a regra dele."""
    assert spec.parece_duplicada_sem_o_pdm("PDM.4320.002 - MOTOBOMBA DUPLICADA") is True


def test_suspeita_tolera_acento_e_caixa():
    assert spec.parece_duplicada_sem_o_pdm("ficha duplicáda") is True


@pytest.mark.parametrize("valor", ["PDM.4320.002 - MOTOBOMBA", "", "   ", None, "nan"])
def test_pdm_normal_nao_e_suspeito(valor):
    assert spec.parece_duplicada_sem_o_pdm(valor) is False
