r"""
Os 16 campos que sumiam entre a IA e o portal.

Caso REAL de 2026-08-11, ficha 4500063671.1471 (PDM.4320.002): a IA devolveu
**37 PREENCHER — exatamente os 37 campos que o fornecedor preencheu na
ficha** — e só 21 chegaram ao portal. A leitura natural foi "o modelo é
fraco". Não era: os outros 16 foram apagados pelo nosso próprio código, e
ainda por cima viraram EXCLUSÃO de linha no portal.

A cadeia inteira:

  1. o Master (SAM) é filtrado só por CÓDIGO PDM, e guarda uma linha por
     característica POR REVISÃO -- 106 linhas em 3 revisões para 51
     características reais;
  2. o contexto enviado à IA levava as 106, então a IA respondia a mesma
     característica 2-3 vezes: PREENCHER (revisão vigente) e REMOVER
     (revisões antigas, que não têm resposta do fornecedor);
  3. o RPA montava o índice com um dict comprehension, onde o ÚLTIMO vence --
     e o último era sempre o REMOVER da revisão velha.

Duas correções independentes, e as duas precisam existir: deduplicar o
contexto ataca a causa, e a precedência no índice é a rede para quando um
modelo repetir chave por conta própria.
"""
import pytest

from sigft.services.tech_specs import deduplicar_contexto, indexar_por_caracteristica


def _norm(texto):
    return str(texto).strip().upper()


# ===========================================================================
# Índice: PREENCHER vence REMOVER
# ===========================================================================
def test_remover_depois_de_preencher_nao_apaga_a_resposta():
    """A ORDEM do caso real: a revisão vigente vem primeiro, as antigas
    depois. Com "o último vence", o REMOVER da revisão velha ganhava."""
    dados = [
        {"CARACTERISTICA_CHAVE": "TENSAO NOMINAL", "ACAO": "PREENCHER",
         "TIPO": "NUM", "RESPOSTA_PT_FINAL": "440"},
        {"CARACTERISTICA_CHAVE": "TENSAO NOMINAL", "ACAO": "REMOVER"},
    ]

    indice = indexar_por_caracteristica(dados, _norm)

    assert indice["TENSAO NOMINAL"]["ACAO"] == "PREENCHER"
    assert indice["TENSAO NOMINAL"]["RESPOSTA_PT_FINAL"] == "440"


def test_preencher_depois_de_remover_tambem_vence():
    # A ordem inversa não pode depender da sorte: o critério é a AÇÃO, não a
    # posição.
    dados = [
        {"CARACTERISTICA_CHAVE": "VAZAO", "ACAO": "REMOVER"},
        {"CARACTERISTICA_CHAVE": "VAZAO", "ACAO": "PREENCHER",
         "TIPO": "NUM", "RESPOSTA_PT_FINAL": "145"},
    ]

    assert indexar_por_caracteristica(dados, _norm)["VAZAO"]["RESPOSTA_PT_FINAL"] == "145"


def test_dois_preencher_na_mesma_chave_fica_o_primeiro():
    # No Master a revisão vigente vem antes; ela é a que tem o TIPO e a ajuda
    # corretos.
    dados = [
        {"CARACTERISTICA_CHAVE": "X", "ACAO": "PREENCHER", "TIPO": "NUM", "RESPOSTA_PT_FINAL": "vigente"},
        {"CARACTERISTICA_CHAVE": "X", "ACAO": "PREENCHER", "TIPO": "CHAR", "RESPOSTA_PT_FINAL": "antiga"},
    ]

    assert indexar_por_caracteristica(dados, _norm)["X"]["RESPOSTA_PT_FINAL"] == "vigente"


def test_so_remover_continua_removendo():
    """A correção não pode transformar exclusão legítima em preenchimento:
    característica sem resposta do fornecedor TEM de sair da ficha."""
    dados = [
        {"CARACTERISTICA_CHAVE": "FATOR DE POTENCIA", "ACAO": "REMOVER"},
        {"CARACTERISTICA_CHAVE": "FATOR DE POTENCIA", "ACAO": "REMOVER"},
    ]

    assert indexar_por_caracteristica(dados, _norm)["FATOR DE POTENCIA"]["ACAO"] == "REMOVER"


def test_a_normalizacao_da_chave_continua_sendo_a_do_chamador():
    # O casamento com a tela usa `normalizar_texto` do processador; o índice
    # não pode ter uma segunda regra de normalização.
    dados = [{"CARACTERISTICA_CHAVE": "  tensao nominal  ", "ACAO": "REMOVER"}]

    assert list(indexar_por_caracteristica(dados, _norm)) == ["TENSAO NOMINAL"]


def test_o_caso_real_recupera_os_16_campos():
    """Reprodução do JSON real (resumida): 3 características que existem em
    mais de uma revisão do PDM."""
    dados = []
    for chave, valor in [("TENSAO NOMINAL", "440"), ("VAZAO", "145"), ("GRAU DE PROTECAO", "IP65")]:
        dados.append({"CARACTERISTICA_CHAVE": chave, "ACAO": "PREENCHER",
                      "TIPO": "CHAR", "RESPOSTA_PT_FINAL": valor})
    # ... e as revisões antigas, todas REMOVER, DEPOIS.
    for chave in ("TENSAO NOMINAL", "VAZAO", "GRAU DE PROTECAO", "TENSAO NOMINAL"):
        dados.append({"CARACTERISTICA_CHAVE": chave, "ACAO": "REMOVER"})

    indice = indexar_por_caracteristica(dados, _norm)

    preenchidos = [k for k, v in indice.items() if v["ACAO"] == "PREENCHER"]
    assert sorted(preenchidos) == ["GRAU DE PROTECAO", "TENSAO NOMINAL", "VAZAO"]


# ===========================================================================
# Contexto: uma característica por nome
# ===========================================================================
def _linha(nome, tipo="NUM", ajuda="ajuda boa"):
    return {"CARACTERISTICA_DESC_PT": nome, "TIPO_DADO": tipo, "TEXTO_AJUDA": ajuda}


def test_contexto_manda_cada_caracteristica_uma_vez():
    contexto = [_linha("TENSAO NOMINAL"), _linha("VAZAO"), _linha("TENSAO NOMINAL")]

    assert [e["CARACTERISTICA_DESC_PT"] for e in deduplicar_contexto(contexto)] == [
        "TENSAO NOMINAL", "VAZAO",
    ]


def test_fica_a_linha_da_revisao_vigente_que_vem_primeiro():
    """As revisões antigas trazem TIPO_DADO e ajuda DEGRADADOS -- na revisão 0
    do PDM.4320.002 tudo é "CHAR" e a ajuda é vazia. Ficar com a errada
    empurraria a IA para o tipo errado."""
    contexto = [
        _linha("TENSAO NOMINAL", tipo="NUM", ajuda="Indique a tensão nominal em (V)"),
        _linha("TENSAO NOMINAL", tipo="CHAR", ajuda=""),
    ]

    unico = deduplicar_contexto(contexto)[0]
    assert unico["TIPO_DADO"] == "NUM"
    assert unico["TEXTO_AJUDA"]


def test_comparacao_ignora_espaco_e_caixa():
    contexto = [_linha("Tensao Nominal"), _linha("  TENSAO NOMINAL  ")]

    assert len(deduplicar_contexto(contexto)) == 1


def test_contexto_sem_repeticao_atravessa_intacto():
    contexto = [_linha("A"), _linha("B"), _linha("C")]

    assert deduplicar_contexto(contexto) == contexto


def test_contexto_vazio_nao_levanta():
    assert deduplicar_contexto([]) == []


@pytest.mark.parametrize("faltando", [{}, {"CARACTERISTICA_DESC_PT": ""}])
def test_entrada_sem_nome_nao_derruba_a_deduplicacao(faltando):
    # Master com célula vazia existe; virar exceção aqui mataria a ficha
    # inteira por causa de uma linha.
    assert len(deduplicar_contexto([faltando, _linha("A")])) == 2


# ===========================================================================
# Falha de dropdown deixa de ser silenciosa
# ===========================================================================
# Pedido do usuário: "quando o campo estava PREENCHER e no portal não
# conseguiu colocar a unidade, ou não conseguiu colocar o valor, que apareça
# no log de saída, pois antes de salvar poderia ser preenchido na mão".
#
# Os três dropdowns da linha (lista, intervalo, unidade) viviam dentro de um
# `except Exception: pass` e voltavam como se tivessem selecionado. O campo
# ficava em branco no portal -- e "em branco" numa lista é indistinguível de
# "não se aplica".
from sigft.services.tech_specs import TechSpecsAutomation  # noqa: E402


class _EngineDropdown:
    def __init__(self, opcoes, aceita_exato=()):
        self._opcoes = list(opcoes)
        self._aceita_exato = set(aceita_exato)
        self.selecionado = None

    def opcoes(self, _seletor):
        return list(self._opcoes)

    def selecionar_por_texto(self, _seletor, texto):
        if texto not in self._aceita_exato:
            raise RuntimeError("opção inexistente")
        self.selecionado = texto

    def selecionar_por_indice(self, _seletor, indice):
        self.selecionado = self._opcoes[indice]


def _proc(engine):
    """Os dropdowns são da classe de RPA (`TechSpecsAutomation`), não da de
    IA -- é ela que mexe no `<select>` da tela."""
    proc = TechSpecsAutomation()
    proc.engine = engine
    return proc


def test_lista_encontra_a_opcao_em_espanhol_quando_a_tela_esta_em_espanhol():
    """O `<select>` da linha é UM só e as opções vêm ora em PT ora em ES.
    Mandar só o texto PT fazia o casamento falhar -- o "ele tenta a opção
    espanhol na caixa de português" que o usuário relatou."""
    engine = _EngineDropdown(["Cerrado", "Abierto"], aceita_exato=["Cerrado", "Abierto"])
    proc = _proc(engine)

    assert proc.selecionar_dropdown_lista("//sel", "Fechado", alternativas=("Cerrado",)) is True
    assert engine.selecionado == "Cerrado"


def test_lista_prefere_o_portugues_quando_as_duas_linguas_servem():
    engine = _EngineDropdown(["Fechado", "Cerrado"], aceita_exato=["Fechado", "Cerrado"])
    proc = _proc(engine)

    proc.selecionar_dropdown_lista("//sel", "Fechado", alternativas=("Cerrado",))

    assert engine.selecionado == "Fechado"


def test_lista_tenta_exato_de_todos_antes_de_substring_de_qualquer_um():
    """Substring é frouxa: "60" casa "50/60". Se ela competisse cedo,
    trocaria o acerto exato de um candidato pelo aproximado de outro."""
    engine = _EngineDropdown(["50/60", "60"], aceita_exato=["60"])
    proc = _proc(engine)

    proc.selecionar_dropdown_lista("//sel", "60", alternativas=("50/60",))

    assert engine.selecionado == "60"


def test_lista_sem_casamento_devolve_false_e_diz_o_que_havia_na_tela():
    logs = []
    engine = _EngineDropdown(["Horizontal", "Vertical"])
    proc = _proc(engine)

    ok = proc.selecionar_dropdown_lista(
        "//sel", "Inclinado", nome_campo="POSICAO", callback_log=logs.append,
    )

    assert ok is False
    texto = " ".join(logs)
    assert "POSICAO" in texto
    assert "Inclinado" in texto      # o que tentou...
    assert "Horizontal" in texto     # ...e o que existia. Sem os dois, o log não resolve nada.


def test_lista_vazia_nao_e_considerada_falha():
    # Característica sem valor de lista é caso normal; virar pendência
    # encheria o relatório de ruído e escondia as falhas reais.
    assert _proc(_EngineDropdown([])).selecionar_dropdown_lista("//sel", "") is True


def test_unidade_fora_do_dropdown_devolve_false_e_lista_as_opcoes():
    """Medido no lote real: a IA devolveu SIMBOLO "kW" para POTENCIA BOMBA,
    característica que o Master só admite em "CV, HP"."""
    logs = []
    engine = _EngineDropdown(["Cavalo-vapor (CV)", "Horsepower (HP)"])
    proc = _proc(engine)

    ok = proc.selecionar_dropdown_unidade(
        "//sel", "kW", nome_campo="POTENCIA BOMBA", callback_log=logs.append,
    )

    assert ok is False
    assert "kW" in " ".join(logs) and "CV" in " ".join(logs)


def test_unidade_casa_o_simbolo_entre_parenteses():
    engine = _EngineDropdown(["Milímetro (MM)", "Metro (M)"])
    proc = _proc(engine)

    assert proc.selecionar_dropdown_unidade("//sel", "mm") is True
    assert engine.selecionado == "Milímetro (MM)"


def test_unidade_nao_casa_prefixo_por_engano():
    """"V" não pode selecionar "kV": o parêntese é o que torna o casamento
    inequívoco, e o fallback sem parênteses exige igualdade EXATA."""
    engine = _EngineDropdown(["Quilovolt (KV)", "Milivolt (MV)"])
    proc = _proc(engine)

    assert proc.selecionar_dropdown_unidade("//sel", "V") is False
    assert engine.selecionado is None


def test_sem_dropdown_de_unidade_nao_vira_pendencia():
    """Caso REAL do 2º lote: FREQUENCIA NOMINAL (tipo LISTA) teve o valor
    selecionado corretamente e mesmo assim saiu como "campo rejeitado", só
    porque a linha não tem dropdown de unidade.

    Nenhuma opção lida significa "não há dropdown aqui" ou "ainda não
    carregou" -- nunca "a IA errou o símbolo". Tratar isso como falha manda o
    usuário conferir à mão um campo que está certo, e o ruído mata a
    utilidade da lista de pendências.
    """
    logs = []
    proc = _proc(_EngineDropdown([]))

    ok = proc.selecionar_dropdown_unidade(
        "//sel", "Hz", nome_campo="FREQUENCIA NOMINAL", callback_log=logs.append,
    )

    assert ok is True
    assert "sem dropdown de unidade" in " ".join(logs)


def test_simbolo_errado_com_dropdown_presente_continua_sendo_falha():
    """Contraste do teste acima: quando o dropdown EXISTE e o símbolo não
    está nele, é falha de verdade e tem de virar pendência."""
    logs = []
    proc = _proc(_EngineDropdown(["Cavalo-vapor (CV)", "Horsepower (HP)"]))

    ok = proc.selecionar_dropdown_unidade(
        "//sel", "kW", nome_campo="POTENCIA BOMBA", callback_log=logs.append,
    )

    assert ok is False
    assert "não existe no dropdown" in " ".join(logs)
