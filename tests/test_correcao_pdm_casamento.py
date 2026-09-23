r"""O CASAMENTO antigo↔novo e a conversão de tipo (E3 do plano).

É o coração do módulo de correção de PDM, e **onde mora o risco de perder dado
em silêncio**. Depois que o portal troca o PDM, a tabela nova está vazia; o que
volta para a ficha é exatamente o que este módulo disser que volta.

Por isso a regra de ouro, e ela é testada linha por linha aqui:

> converter só quando a conversão é **sem perda e sem ambiguidade**; no resto,
> não repor e **listar**.

Repor um valor plausível e errado é pior que deixar vazio — o vazio a pessoa vê
e preenche; o errado ela assina. É a mesma lição do prompt de Condições
(2026-08-18).

POR QUE A MATRIZ DE TIPOS EXISTE
------------------------------------------------------------------------
Medido no Master: **3160 de 8841 características mudam de tipo entre revisões
do mesmo PDM — 35,7%, em 748 PDMs.** A preocupação do usuário (*"antes era NUM
e viraram CHAR na nova revisão"*) não só procede como é um terço das linhas.

E as SEIS direções acontecem: em R0→R1 domina CHAR→NUM, mas na amostra de
R1→R2 — que é a transição que ele está vivendo — aparecem também NUM→CHAR e
INT→CHAR. O módulo não pode apostar em nenhuma.

Plano e matriz completa em `docs/refatoracao/CORRECAO_PDM.md` §11.
"""
from __future__ import annotations

import pytest

from sigft.core.rpa.caracteristicas import Caracteristica
from sigft.services import correcao_pdm_casamento as casamento
from sigft.services.correcao_pdm_retrato import Retrato


def _retrato(*caracteristicas):
    return Retrato(
        pmib="4500063671.0242",
        pdm_antigo="PDM.5920.020 - PROTETOR, SURTO, R1",
        pdm_novo="PDM.5920.020 - PROTETOR, SURTO, R2",
        caracteristicas=tuple(caracteristicas),
    )


def _char(codigo="1171", nome="ACABAMENTO", pt="PINTADO", es="PINTADO",
          unidade="AD"):
    return Caracteristica(codigo=codigo, nome=nome, tipo="CHAR", valor_pt=pt,
                          valor_es=es, unidade=unidade)


def _num(codigo="1230", nome="TENSAO NOMINAL", pt="220", unidade="V"):
    return Caracteristica(codigo=codigo, nome=nome, tipo="NUM", valor_pt=pt,
                          unidade=unidade)


def _int(codigo="1047", nome="FAIXA TEMPERATURA", minimo="-10", maximo="50",
         subtipo="ENTRE", unidade="°C"):
    return Caracteristica(codigo=codigo, nome=nome, tipo="INT", minimo=minimo,
                          maximo=maximo, subtipo=subtipo, unidade=unidade)


def _lista(codigo="1500", nome="MATERIAL", pt="ACO INOX", unidade="AD"):
    return Caracteristica(codigo=codigo, nome=nome, tipo="LISTA", valor_pt=pt,
                          unidade=unidade)


def _vazia(codigo, nome, tipo):
    """Uma linha da ficha NOVA: existe, e está em branco (é o estado logo
    depois da troca de PDM)."""
    return Caracteristica(codigo=codigo, nome=nome, tipo=tipo)


def _uma(plano_lista):
    assert len(plano_lista) == 1, f"esperava 1, veio {len(plano_lista)}"
    return plano_lista[0]


# =============================================================================
# A. O casamento -- por CÓDIGO, com o nome como conferência
# =============================================================================
def test_casa_por_codigo_e_repoe_o_valor():
    plano = casamento.casar(_retrato(_char()), [_vazia("1171", "ACABAMENTO", "CHAR")])

    assert _uma(plano.repor).valor_pt == "PINTADO"
    assert not plano.nao_casou


def test_o_codigo_vence_o_nome_quando_o_nome_mudou():
    """A Itaipu está mexendo em nome de característica agora, e a tela ainda
    alterna PT/ES. O código é imune aos dois."""
    plano = casamento.casar(
        _retrato(_char(codigo="1171", nome="ACABAMENTO")),
        [_vazia("1171", "ACABADO SUPERFICIAL", "CHAR")])

    assert _uma(plano.repor).valor_pt == "PINTADO"


def test_nome_diferente_vira_AVISO_e_nao_impede_a_reposicao():
    """Aviso, e não bloqueio: o nome é conferência, o código é a chave. Mas
    quem revisa a ficha depois precisa ver que os dois nomes não batem."""
    plano = casamento.casar(
        _retrato(_char(codigo="1171", nome="ACABAMENTO")),
        [_vazia("1171", "ACABADO SUPERFICIAL", "CHAR")])

    assert "ACABAMENTO" in _uma(plano.repor).aviso
    assert "ACABADO SUPERFICIAL" in _uma(plano.repor).aviso


def test_nome_igual_a_menos_de_acento_e_caixa_nao_vira_aviso():
    """`TENSAO` e `Tensão` são a mesma característica escrita por telas
    diferentes. Avisar disso seria ruído, e ruído num relatório é como uma
    perda de verdade passa batida."""
    plano = casamento.casar(
        _retrato(_char(codigo="1171", nome="TENSAO MAXIMA")),
        [_vazia("1171", "Tensão  Máxima", "CHAR")])

    assert not _uma(plano.repor).aviso


def test_sem_codigo_reconhecivel_casa_pelo_NOME():
    """`codigo_e_nome` devolve `("", texto)` quando a descrição não tem o
    `<código>-<NOME>`. Cair para o nome é seguro: no Master são 2278 códigos
    e 2278 nomes, bijeção perfeita."""
    plano = casamento.casar(
        _retrato(_char(codigo="", nome="ACABAMENTO")),
        [_vazia("", "ACABAMENTO", "CHAR")])

    assert _uma(plano.repor).valor_pt == "PINTADO"


def test_codigos_diferentes_NAO_casam_mesmo_com_o_nome_igual():
    """Duas características distintas podem carregar o mesmo rótulo depois de
    uma renomeação da Itaipu. Casar pelo nome aqui escreveria o valor na linha
    errada -- e linha errada é pior que linha vazia."""
    plano = casamento.casar(
        _retrato(_char(codigo="1171", nome="ACABAMENTO")),
        [_vazia("2222", "ACABAMENTO", "CHAR")])

    assert not plano.repor
    assert _uma(plano.nao_casou).codigo == "1171"


def test_o_que_o_pdm_novo_nao_tem_vai_para_nao_casou_com_o_valor():
    """A pendência guarda o VALOR e a UNIDADE: é com ela que a pessoa preenche
    à mão o que o módulo não conseguiu devolver.

    Os dois em campos SEPARADOS, e isso saiu de um teste vermelho: colando-os
    num texto só, uma linha `CHAR` com texto `"220 V"` e unidade `A` virava
    `"220 V A"` no relatório, um valor que nunca esteve na ficha. Quem junta
    os dois é a linha do relatório, onde a unidade aparece entre colchetes.
    """
    plano = casamento.casar(_retrato(_num(pt="220", unidade="V")), [])

    perdida = _uma(plano.nao_casou)
    assert perdida.nome == "TENSAO NOMINAL"
    assert perdida.valor == "220"
    assert perdida.unidade == "V"
    assert '"220" [V]' in "\n".join(plano.relatorio())


def test_o_relatorio_nao_repete_a_unidade_que_ja_esta_no_texto():
    """Uma linha `CHAR` guarda o valor inteiro no texto, e a unidade dela é
    quase sempre `AD`. Escrever `"220 V" [AD]` diria à pessoa que a ficha tem
    uma unidade que ela não tem."""
    plano = casamento.casar(
        _retrato(_char(pt="220 V", es="220 V", unidade="AD")),
        [_vazia("1171", "TENSAO", "INT")])

    linha = [x for x in plano.relatorio() if "220 V" in x][0]
    assert "[AD]" not in linha


def test_cada_linha_nova_recebe_no_maximo_uma_do_retrato():
    """Se o retrato tiver o mesmo código duas vezes, a segunda não pode
    sobrescrever a primeira na mesma linha -- e também não pode sumir calada."""
    plano = casamento.casar(
        _retrato(_char(pt="PINTADO"), _char(pt="CROMADO")),
        [_vazia("1171", "ACABAMENTO", "CHAR")])

    assert _uma(plano.repor).valor_pt == "PINTADO"
    assert _uma(plano.nao_casou).valor == "CROMADO"


def test_duas_linhas_novas_IGUAIS_sao_tratadas_como_DUAS():
    """Uma linha repetida na tabela nova não é uma linha só.

    ⚠️ A primeira versão disto identificava as linhas por `id()`. Duas linhas
    iguais viravam a mesma: uma recebia o valor e a outra, invisível, escapava
    do "apagar as que ficaram em branco". Endereçar pela POSIÇÃO não depende
    de o portal devolver objetos distintos, que nunca foi contrato de ninguém.
    """
    linha = _vazia("1171", "ACABAMENTO", "CHAR")

    plano = casamento.casar(_retrato(_char(pt="PINTADO")), [linha, linha])

    assert len(plano.repor) == 1
    assert len(plano.sem_valor) == 1


def test_caracteristica_VAZIA_no_retrato_nao_entra_em_lugar_nenhum():
    """Ela não foi perdida: não havia nada. Listá-la como perda encheria o
    relatório de linhas que a pessoa não precisa conferir."""
    plano = casamento.casar(
        _retrato(Caracteristica(codigo="1171", nome="ACABAMENTO", tipo="CHAR",
                                unidade="AD")),
        [_vazia("1171", "ACABAMENTO", "CHAR")])

    assert not plano.repor
    assert not plano.converter
    assert not plano.nao_casou


# =============================================================================
# B. A matriz de tipos -- uma linha da §11 por teste
# =============================================================================
def test_tipo_igual_repoe_direto_CHAR():
    plano = casamento.casar(
        _retrato(_char(pt="PINTADO", es="PINTADO")),
        [_vazia("1171", "ACABAMENTO", "CHAR")])

    posta = _uma(plano.repor)
    assert (posta.valor_pt, posta.valor_es, posta.tipo) == ("PINTADO", "PINTADO", "CHAR")
    assert not plano.converter


def test_tipo_igual_repoe_direto_NUM():
    plano = casamento.casar(_retrato(_num()), [_vazia("1230", "TENSAO NOMINAL", "NUM")])

    posta = _uma(plano.repor)
    assert (posta.valor_pt, posta.unidade) == ("220", "V")


def test_tipo_igual_repoe_direto_INT_com_os_tres_campos():
    """Intervalo sem o subtipo vira uma faixa sem sentido: `-10` e `50` não
    dizem se é ENTRE, MAIOR QUE ou MENOR QUE."""
    plano = casamento.casar(_retrato(_int()), [_vazia("1047", "FAIXA TEMPERATURA", "INT")])

    posta = _uma(plano.repor)
    assert (posta.minimo, posta.maximo, posta.subtipo) == ("-10", "50", "ENTRE")


def test_tipo_igual_repoe_direto_LISTA():
    plano = casamento.casar(_retrato(_lista()), [_vazia("1500", "MATERIAL", "LISTA")])

    assert _uma(plano.repor).valor_pt == "ACO INOX"


def test_NUM_para_CHAR_converte_juntando_valor_e_unidade():
    """Sem perda: o número e o símbolo cabem inteiros num texto. A unidade
    passa a `AD` porque o símbolo JÁ está no texto -- deixá-la em `V` faria a
    ficha dizer "220 V" na coluna de unidade "V"."""
    plano = casamento.casar(_retrato(_num(pt="220", unidade="V")),
                            [_vazia("1230", "TENSAO NOMINAL", "CHAR")])

    convertida = _uma(plano.converter)
    assert convertida.valor_pt == "220 V"
    assert convertida.unidade == "AD"
    assert not plano.nao_casou


def test_NUM_para_CHAR_preenche_TAMBEM_o_espanhol():
    """A linha `NUM` só tem um valor, e a linha `CHAR` tem dois campos. Deixar
    o espanhol vazio perderia metade da ficha -- e número não tem idioma."""
    plano = casamento.casar(_retrato(_num(pt="220", unidade="V")),
                            [_vazia("1230", "TENSAO NOMINAL", "CHAR")])

    assert _uma(plano.converter).valor_es == "220 V"


def test_INT_para_CHAR_converte_com_minimo_maximo_e_subtipo():
    plano = casamento.casar(_retrato(_int()),
                            [_vazia("1047", "FAIXA TEMPERATURA", "CHAR")])

    assert _uma(plano.converter).valor_pt == "-10 / 50 °C (ENTRE)"


def test_INT_para_CHAR_sem_maximo_nao_deixa_barra_solta():
    """`MAIOR QUE 10` tem mínimo e não tem máximo. `"10 / "` seria um texto
    quebrado escrito na ficha do usuário."""
    plano = casamento.casar(
        _retrato(_int(minimo="10", maximo="", subtipo="MAIOR QUE", unidade="A")),
        [_vazia("1047", "FAIXA TEMPERATURA", "CHAR")])

    assert _uma(plano.converter).valor_pt == "10 A (MAIOR QUE)"


def test_LISTA_para_CHAR_converte_a_opcao_em_texto():
    plano = casamento.casar(_retrato(_lista(pt="ACO INOX")),
                            [_vazia("1500", "MATERIAL", "CHAR")])

    assert _uma(plano.converter).valor_pt == "ACO INOX"


def test_CHAR_para_NUM_converte_quando_o_texto_e_numero_puro():
    plano = casamento.casar(_retrato(_char(pt="220", es="220", unidade="V")),
                            [_vazia("1171", "TENSAO", "NUM")])

    convertida = _uma(plano.converter)
    assert convertida.valor_pt == "220"
    assert convertida.unidade == "V"


def test_CHAR_para_NUM_aceita_virgula_decimal():
    """O portal é pt/es: `1,5` é como o número aparece escrito na tela."""
    plano = casamento.casar(_retrato(_char(pt="1,5", es="1,5", unidade="MM")),
                            [_vazia("1171", "ESPESSURA", "NUM")])

    assert _uma(plano.converter).valor_pt == "1,5"


def test_CHAR_para_NUM_NAO_converte_texto_que_nao_e_numero():
    """*"Aço inox" não vira número.* Listar é a resposta certa."""
    plano = casamento.casar(_retrato(_char(pt="ACO INOX")),
                            [_vazia("1171", "MATERIAL", "NUM")])

    assert not plano.converter
    perdida = _uma(plano.nao_casou)
    assert perdida.valor == "ACO INOX"
    assert "CHAR" in perdida.motivo and "NUM" in perdida.motivo


def test_CHAR_para_NUM_desfaz_o_recuo_de_2026_08_18():
    """`"220 V"` com unidade `AD` é EXATAMENTE o que `juntar_para_char`
    escreve quando o robô recua de NUM para CHAR. Se a revisão nova devolve a
    linha para `NUM`, o caminho de volta é determinístico: o `AD` não carrega
    informação nenhuma, então trocá-lo por `V` não perde nada."""
    plano = casamento.casar(_retrato(_char(pt="220 V", es="220 V", unidade="AD")),
                            [_vazia("1171", "TENSAO", "NUM")])

    convertida = _uma(plano.converter)
    assert convertida.valor_pt == "220"
    assert convertida.unidade == "V"


def test_CHAR_para_NUM_aceita_o_simbolo_que_ja_esta_na_unidade():
    plano = casamento.casar(_retrato(_char(pt="220 V", es="220 V", unidade="V")),
                            [_vazia("1171", "TENSAO", "NUM")])

    assert _uma(plano.converter).valor_pt == "220"


def test_CHAR_para_NUM_NAO_converte_quando_o_simbolo_CONTRADIZ_a_unidade():
    """Texto `"220 V"` numa linha cuja unidade gravada é `A`: os dois não podem
    estar certos. Escolher um seria escolher no escuro."""
    plano = casamento.casar(_retrato(_char(pt="220 V", es="220 V", unidade="A")),
                            [_vazia("1171", "TENSAO", "NUM")])

    assert not plano.converter
    assert _uma(plano.nao_casou).valor == "220 V"


def test_CHAR_para_LISTA_vira_TENTATIVA_com_os_dois_idiomas():
    """Quais opções a lista tem só a TELA sabe, e esta camada não fala com o
    portal. Então o plano entrega os dois idiomas como candidatos e quem
    escreve decide -- é o mesmo arranjo de `_preencher_linha`, que já tenta a
    resposta ES como alternativa."""
    plano = casamento.casar(
        _retrato(_char(pt="ACO INOX", es="ACERO INOXIDABLE")),
        [_vazia("1171", "MATERIAL", "LISTA")])

    convertida = _uma(plano.converter)
    assert convertida.valor_pt == "ACO INOX"
    assert convertida.valor_es == "ACERO INOXIDABLE"
    assert convertida.tentativa is True


def test_reposicao_de_tipo_igual_NAO_e_tentativa():
    plano = casamento.casar(_retrato(_char()), [_vazia("1171", "ACABAMENTO", "CHAR")])

    assert _uma(plano.repor).tentativa is False


def test_CHAR_para_INT_e_LISTADO():
    """*"de -10 a 50" exige interpretar; não é determinístico.*"""
    plano = casamento.casar(_retrato(_char(pt="DE -10 A 50")),
                            [_vazia("1171", "FAIXA", "INT")])

    assert not plano.converter
    assert _uma(plano.nao_casou).valor == "DE -10 A 50"


def test_NUM_para_INT_e_LISTADO():
    """Um valor só não define uma faixa: não dá para saber se 220 é o mínimo
    ou o máximo."""
    plano = casamento.casar(_retrato(_num(pt="220")),
                            [_vazia("1230", "FAIXA TENSAO", "INT")])

    assert not plano.converter
    assert _uma(plano.nao_casou).motivo


def test_INT_para_NUM_e_LISTADO():
    """Dois valores não cabem num campo só; escolher o mínimo ou o máximo
    perderia o outro sem dizer."""
    plano = casamento.casar(_retrato(_int()),
                            [_vazia("1047", "TEMPERATURA", "NUM")])

    assert not plano.converter
    perdida = _uma(plano.nao_casou)
    assert "-10" in perdida.valor and "50" in perdida.valor


def test_NUM_para_LISTA_vira_tentativa():
    plano = casamento.casar(_retrato(_num(pt="220", unidade="V")),
                            [_vazia("1230", "TENSAO", "LISTA")])

    convertida = _uma(plano.converter)
    assert convertida.tentativa is True
    assert "220" in convertida.valor_pt


def test_LISTA_para_NUM_converte_quando_a_opcao_e_numero_puro():
    plano = casamento.casar(_retrato(_lista(pt="60")),
                            [_vazia("1500", "FREQUENCIA", "NUM")])

    assert _uma(plano.converter).valor_pt == "60"


def test_tipo_NOVO_desconhecido_e_LISTADO():
    """*Tipo novo do portal não pode virar palpite.* `""` é o que
    `tipo_da_linha` devolve quando a linha não se parece com nenhum dos
    quatro -- e uma linha que não se reconhece não se preenche."""
    plano = casamento.casar(_retrato(_char()), [_vazia("1171", "ACABAMENTO", "")])

    assert not plano.repor and not plano.converter
    assert _uma(plano.nao_casou).motivo


def test_tipo_ANTIGO_desconhecido_e_LISTADO():
    """Se nem na hora do retrato se soube o tipo da linha, não se sabe o que
    se está segurando."""
    antiga = Caracteristica(codigo="1171", nome="ACABAMENTO", tipo="",
                            valor_pt="PINTADO")

    plano = casamento.casar(_retrato(antiga), [_vazia("1171", "ACABAMENTO", "CHAR")])

    assert not plano.repor and not plano.converter
    assert _uma(plano.nao_casou).valor == "PINTADO"


@pytest.mark.parametrize("de,para", [
    ("CHAR", "CHAR"), ("NUM", "NUM"), ("INT", "INT"), ("LISTA", "LISTA"),
    ("NUM", "CHAR"), ("INT", "CHAR"), ("LISTA", "CHAR"),
    ("CHAR", "NUM"), ("CHAR", "LISTA"), ("CHAR", "INT"),
    ("NUM", "INT"), ("NUM", "LISTA"), ("INT", "NUM"), ("INT", "LISTA"),
    ("LISTA", "NUM"), ("LISTA", "INT"),
    ("CHAR", ""), ("", "CHAR"), ("", ""),
])
def test_toda_direcao_tem_destino_e_nenhuma_some(de, para):
    """As 6 direções acontecem, e o silêncio é o único resultado inaceitável:
    cada característica com valor termina em UMA das listas. Uma direção
    esquecida na matriz sumiria sem erro nenhum."""
    antiga = Caracteristica(codigo="1", nome="X", tipo=de, valor_pt="7",
                            valor_es="7", minimo="7", maximo="9",
                            subtipo="ENTRE", unidade="AD")

    plano = casamento.casar(_retrato(antiga), [_vazia("1", "X", para)])

    assert len(plano.repor) + len(plano.converter) + len(plano.nao_casou) == 1


# =============================================================================
# C. O que fica em branco -- requisito 6 do usuário
# =============================================================================
def test_linha_nova_sem_reposicao_entra_em_sem_valor():
    """*"Temos que apagar todas as características que ficaram em branco e se
    possível colocar num relatório."*"""
    plano = casamento.casar(_retrato(_char()),
                            [_vazia("1171", "ACABAMENTO", "CHAR"),
                             _vazia("9999", "CARACTERISTICA NOVA", "NUM")])

    assert [c.codigo for c in plano.sem_valor] == ["9999"]


def test_linha_que_VAI_receber_valor_nao_entra_em_sem_valor():
    """Apagar uma linha que ia ser preenchida seria destruir o trabalho no
    passo seguinte. (A ordem -- repor ANTES de apagar -- é do serviço; esta
    lista já nasce certa.)"""
    plano = casamento.casar(_retrato(_char()), [_vazia("1171", "ACABAMENTO", "CHAR")])

    assert not plano.sem_valor


def test_linha_que_JA_tem_valor_nao_entra_em_sem_valor():
    """Logo depois da troca a tabela nova está vazia, mas o módulo também roda
    no modo "só repor", sobre uma ficha em que alguém já digitou algo. Apagar
    isso seria apagar trabalho humano."""
    ja_preenchida = Caracteristica(codigo="9999", nome="OUTRA", tipo="CHAR",
                                   valor_pt="DIGITADO A MAO")

    plano = casamento.casar(_retrato(_char()),
                            [_vazia("1171", "ACABAMENTO", "CHAR"), ja_preenchida])

    assert not plano.sem_valor


def test_linha_que_so_recebe_TENTATIVA_nao_entra_em_sem_valor():
    """A tentativa pode falhar (a opção não existe na lista) -- mas quem
    descobre isso é o serviço, com a tela na frente. Marcá-la para apagar
    agora seria decidir a falha antes de tentar."""
    plano = casamento.casar(_retrato(_char(pt="ACO INOX")),
                            [_vazia("1171", "MATERIAL", "LISTA")])

    assert not plano.sem_valor


# =============================================================================
# D. O relatório -- o que a pessoa lê quando algo não voltou
# =============================================================================
def test_o_motivo_diz_de_que_tipo_para_que_tipo():
    """Sem os dois tipos, o relatório vira "não deu" -- e quem lê não sabe se
    corrige à mão ou se é defeito do robô."""
    plano = casamento.casar(_retrato(_char(pt="ACO INOX")),
                            [_vazia("1171", "MATERIAL", "INT")])

    assert "CHAR" in _uma(plano.nao_casou).motivo
    assert "INT" in _uma(plano.nao_casou).motivo


def test_o_motivo_de_quem_nao_existe_no_pdm_novo_diz_isso():
    plano = casamento.casar(_retrato(_char()), [])

    assert _uma(plano.nao_casou).tipo_novo == ""
    assert _uma(plano.nao_casou).motivo


def test_o_relatorio_nao_usa_travessao():
    """Regra da casa desde 2026-09-18 (`tests/test_texto_da_ui.py`): travessão
    fora do texto que o usuário lê."""
    plano = casamento.casar(
        _retrato(_char(pt="ACO INOX"), _char(codigo="1230", nome="OUTRA", pt="X")),
        [_vazia("1171", "MATERIAL", "INT")])

    for linha in plano.relatorio():
        assert "—" not in linha


def test_o_relatorio_lista_o_que_nao_voltou_e_o_que_ficou_em_branco():
    plano = casamento.casar(
        _retrato(_char(pt="ACO INOX")),
        [_vazia("1171", "MATERIAL", "INT"), _vazia("9999", "SOBRANDO", "CHAR")])

    texto = "\n".join(plano.relatorio())
    assert "ACO INOX" in texto
    assert "SOBRANDO" in texto


def test_o_relatorio_de_um_plano_perfeito_diz_que_nada_se_perdeu():
    """Relatório vazio num arquivo de saída se confunde com relatório que não
    rodou."""
    plano = casamento.casar(_retrato(_char()), [_vazia("1171", "ACABAMENTO", "CHAR")])

    assert plano.relatorio()


# =============================================================================
# E. A chave, compartilhada com quem escreve
# =============================================================================
def test_a_chave_e_a_mesma_para_o_retrato_e_para_a_tela():
    """O serviço (E4) reencontra a linha na tela por esta chave. Se ele
    calculasse a dele, uma diferença de normalização faria a reposição pular
    linhas EM SILÊNCIO."""
    do_retrato = casamento.chave(_char(codigo="1171", nome="ACABAMENTO"))
    da_tela = casamento.chave(_vazia("1171", "Acabamento", "CHAR"))

    assert do_retrato == da_tela


def test_a_chave_sem_codigo_cai_no_nome_normalizado():
    assert casamento.chave(_vazia("", "Tensão  Máxima", "CHAR")) == casamento.chave(
        _vazia("", "TENSAO MAXIMA", "CHAR"))


def test_o_plano_indexa_as_escritas_pela_chave():
    """É como o serviço pergunta "o que eu escrevo nesta linha?" enquanto
    caminha a tabela nova."""
    plano = casamento.casar(
        _retrato(_char(), _num()),
        [_vazia("1171", "ACABAMENTO", "CHAR"), _vazia("1230", "TENSAO NOMINAL", "NUM")])

    escritas = plano.por_chave()

    assert escritas[casamento.chave(_char())].valor_pt == "PINTADO"
    assert escritas[casamento.chave(_num())].valor_pt == "220"


# =============================================================================
# F. Os casos com a forma dos reais
# =============================================================================
def test_atualizacao_de_revisao_devolve_a_maioria():
    """O caso das 25 fichas: mesmo PDM, revisão nova. A maior parte dos
    códigos sobrevive, alguns trocam de tipo, um ou outro sai e entra.

    ⚠️ Os números medidos no Master (`PDM.5920.020` R0->R1: 13 de 17;
    `PDM.5925.001`: 36 de 63) estão no plano, em
    `docs/refatoracao/CORRECAO_PDM.md`. Aqui se reproduz a FORMA do caso, não
    o conteúdo daqueles PDMs: a planilha-mestra não vive no repositório.
    """
    antigas = [
        _char(codigo="1171", nome="ACABAMENTO", pt="PINTADO", es="PINTADO"),
        _num(codigo="1230", nome="TENSAO NOMINAL", pt="220", unidade="V"),
        _int(codigo="1047", nome="FAIXA TEMPERATURA"),
        _lista(codigo="1500", nome="MATERIAL", pt="ACO INOX"),
        _char(codigo="1900", nome="SO NO PDM VELHO", pt="SE PERDE"),
    ]
    novas = [
        _vazia("1171", "ACABAMENTO", "CHAR"),      # igual
        _vazia("1230", "TENSAO NOMINAL", "CHAR"),  # NUM -> CHAR, converte
        _vazia("1047", "FAIXA TEMPERATURA", "INT"),  # igual
        _vazia("1500", "MATERIAL", "CHAR"),        # LISTA -> CHAR, converte
        _vazia("2600", "SO NO PDM NOVO", "NUM"),   # nasce vazia
    ]

    plano = casamento.casar(_retrato(*antigas), novas)

    assert [c.codigo for c in plano.repor] == ["1171", "1047"]
    assert [c.codigo for c in plano.converter] == ["1230", "1500"]
    assert [c.codigo for c in plano.nao_casou] == ["1900"]
    assert [c.codigo for c in plano.sem_valor] == ["2600"]


def test_troca_de_pdm_entre_codigos_diferentes_devolve_pouco_e_diz_isso():
    """Numa troca de PDM de verdade o módulo NÃO devolve tudo (medido: 30 a
    50%). O que ele garante é que nada do reaproveitável se perde e que o
    resto sai em lista explícita, em vez de sumir calado."""
    antigas = [_char(codigo=str(1000 + i), nome=f"C{i}", pt=f"V{i}") for i in range(10)]
    novas = [_vazia("1000", "C0", "CHAR"), _vazia("1003", "C3", "CHAR")]

    plano = casamento.casar(_retrato(*antigas), novas)

    assert len(plano.repor) == 2
    assert len(plano.nao_casou) == 8
    assert not plano.sem_valor
