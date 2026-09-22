r"""A busca do PDM no portal, com as três tentativas em cascata.

O PROBLEMA
------------------------------------------------------------------------
O fluxo antigo digitava a string completa no combo de PDM, esperava um
segundo e apertava ENTER **sem nunca perguntar se o filtro achou algo**. Se o
texto não casasse, o ENTER caía no vazio e a automação quebrava três passos
adiante -- com o PDM certo já escolhido.

E texto que não casa não é hipótese: o título vem do Master, que tem acento em
5 PDMs, espaço duplo em 18 e muda entre revisões em 179.

O QUE O USUÁRIO PEDIU (2026-09-22), e o sinal que ele forneceu
------------------------------------------------------------------------
*"se não der certo de colocar o pdm [...] temos que ter a opção de colocar
apenas os números do pdm tipo PDM.6120.003 [...] e se nao der certo de novo
TRANSFORMADOR POTENCIA"*.

E o sinal de fracasso, colado da tela por ele:

    <div class="vscomp-no-search-results" tabindex="0"
         aria-hidden="false">PDM não encontrado</div>

Ou seja: a recusa é **silenciosa**, e o único sinal é um elemento mudar de
`aria-hidden`. É exatamente a regra 6 de `docs/PORTAL_COMO_ELE_SE_COMPORTA.md`.

⚠️ ESTES TESTES NÃO SÃO PROVA DE PORTAL. Eles rodam contra um dublê de
`RPAEngine` e provam a LÓGICA da cascata -- a ordem das tentativas, a limpeza
entre elas, e que o ENTER só é apertado quando o portal não está dizendo "não
encontrado". Se o seletor estiver errado, todos passam e nada funciona. A
validação é de sessão local, com o navegador ligado (ver CLAUDE.md).
"""
from __future__ import annotations

import pytest

import sigft.services.cria_fichas as cf


@pytest.fixture(autouse=True)
def _sem_sleep(monkeypatch):
    monkeypatch.setattr(cf.time, "sleep", lambda *_a, **_kw: None)


# =============================================================================
# A. As tentativas -- lógica pura, sem portal nenhum
# =============================================================================
def test_a_primeira_tentativa_e_o_texto_completo():
    """O que funciona hoje na maioria dos casos continua sendo o primeiro a
    ser tentado. A cascata é rede, não substituição."""
    assert cf.tentativas_de_busca("PDM.6120.003 - TRANSFORMADOR POTENCIA")[0] == (
        "PDM.6120.003 - TRANSFORMADOR POTENCIA"
    )


def test_a_segunda_tentativa_e_so_o_codigo():
    """O código é imune a acento, espaço duplo e mudança de revisão -- é a
    parte estável da string."""
    assert cf.tentativas_de_busca("PDM.6120.003 - TRANSFORMADOR POTENCIA")[1] == (
        "PDM.6120.003"
    )


def test_a_terceira_tentativa_e_so_o_titulo():
    assert cf.tentativas_de_busca("PDM.6120.003 - TRANSFORMADOR POTENCIA")[2] == (
        "TRANSFORMADOR POTENCIA"
    )


def test_sao_exatamente_tres_tentativas():
    assert len(cf.tentativas_de_busca("PDM.6120.003 - TRANSFORMADOR POTENCIA")) == 3


def test_pdm_so_com_codigo_nao_gera_tentativa_repetida():
    """Repetir a mesma busca gasta uma rodada no portal e não descobre nada."""
    assert cf.tentativas_de_busca("PDM.6120.003") == ["PDM.6120.003"]


def test_o_hifen_do_titulo_nao_vira_separador():
    """`MOTO-VENTILADOR` tem hífen DENTRO do título. Partir no primeiro hífen
    daria o título "MOTO" e a terceira tentativa procuraria por nada."""
    tentativas = cf.tentativas_de_busca("PDM.6120.001 - MOTO-VENTILADOR")

    assert tentativas[1] == "PDM.6120.001"
    assert tentativas[2] == "MOTO-VENTILADOR"


def test_texto_sem_codigo_de_pdm_e_tentado_como_veio():
    assert cf.tentativas_de_busca("TRANSFORMADOR POTENCIA") == [
        "TRANSFORMADOR POTENCIA"
    ]


def test_texto_vazio_nao_gera_tentativa():
    assert cf.tentativas_de_busca("") == []


# =============================================================================
# B. A cascata contra um dublê de motor
# =============================================================================
class _EngineFalso:
    """O mínimo de `RPAEngine` que a busca de PDM usa.

    `nao_encontrado_para` diz em quais textos o "portal" responde
    `PDM não encontrado` -- é o que permite montar cada cenário sem browser.
    """

    def __init__(self, nao_encontrado_para=()):
        self.nao_encontrado_para = set(nao_encontrado_para)
        self.digitado = []
        self.teclas = []
        self.buscado = ""

    # -- o que a busca usa --------------------------------------------------
    def digitar_no_foco(self, texto):
        self.digitado.append(texto)
        self.buscado = texto

    def press(self, teclas):
        self.teclas.extend([teclas] if isinstance(teclas, str) else list(teclas))

    def esta_visivel(self, _seletor):
        return self.buscado in self.nao_encontrado_para

    # -- o resto do fluxo, que estes testes não exercitam -------------------
    def wait_clickable(self, _seletor):
        pass

    def click_nativo(self, _seletor):
        pass


def _bot(engine):
    bot = cf.AutomacaoPMIB.__new__(cf.AutomacaoPMIB)
    bot.engine = engine
    return bot


def test_quando_o_completo_acha_nao_tenta_mais_nada():
    engine = _EngineFalso()

    usado = _bot(engine)._buscar_pdm("PDM.6120.003 - TRANSFORMADOR POTENCIA")

    assert usado == "PDM.6120.003 - TRANSFORMADOR POTENCIA"
    assert engine.digitado == ["PDM.6120.003 - TRANSFORMADOR POTENCIA"]
    assert "ENTER" in engine.teclas


def test_cai_para_o_codigo_quando_o_completo_nao_e_encontrado():
    engine = _EngineFalso(
        nao_encontrado_para={"PDM.6120.003 - TRANSFORMADOR POTENCIA"}
    )

    usado = _bot(engine)._buscar_pdm("PDM.6120.003 - TRANSFORMADOR POTENCIA")

    assert usado == "PDM.6120.003"
    assert engine.digitado == [
        "PDM.6120.003 - TRANSFORMADOR POTENCIA",
        "PDM.6120.003",
    ]


def test_cai_para_o_titulo_quando_o_codigo_tambem_falha():
    engine = _EngineFalso(nao_encontrado_para={
        "PDM.6120.003 - TRANSFORMADOR POTENCIA", "PDM.6120.003",
    })

    usado = _bot(engine)._buscar_pdm("PDM.6120.003 - TRANSFORMADOR POTENCIA")

    assert usado == "TRANSFORMADOR POTENCIA"
    assert engine.digitado[-1] == "TRANSFORMADOR POTENCIA"


def test_o_campo_e_limpo_entre_uma_tentativa_e_a_seguinte():
    """Sem limpar, a segunda tentativa vira
    "PDM.6120.003 - TRANSFORMADOR POTENCIAPDM.6120.003" -- que não acha nada,
    e faria a cascata inteira falhar por um motivo que não é o do portal."""
    completo = "PDM.6120.003 - TRANSFORMADOR POTENCIA"
    engine = _EngineFalso(nao_encontrado_para={completo})

    _bot(engine)._buscar_pdm(completo)

    assert engine.teclas.count("BACKSPACE") >= len(completo)


def test_quando_nenhuma_tentativa_acha_devolve_none_e_nao_aperta_enter():
    """ENTER no vazio é o que quebrava a automação três passos adiante. Sem
    resultado, a função tem que RECUSAR -- o chamador transforma isso num erro
    com nome, que abre a janela de decisão do robô."""
    completo = "PDM.6120.003 - TRANSFORMADOR POTENCIA"
    engine = _EngineFalso(nao_encontrado_para={
        completo, "PDM.6120.003", "TRANSFORMADOR POTENCIA",
    })

    usado = _bot(engine)._buscar_pdm(completo)

    assert usado is None
    assert "ENTER" not in engine.teclas


def test_as_tres_tentativas_sao_feitas_antes_de_desistir():
    completo = "PDM.6120.003 - TRANSFORMADOR POTENCIA"
    engine = _EngineFalso(nao_encontrado_para={
        completo, "PDM.6120.003", "TRANSFORMADOR POTENCIA",
    })

    _bot(engine)._buscar_pdm(completo)

    assert engine.digitado == [completo, "PDM.6120.003", "TRANSFORMADOR POTENCIA"]


def test_o_item_falha_com_mensagem_que_nomeia_as_tentativas():
    """`processar_item_individual` devolve ("ERRO", texto), e esse texto vai
    para a `JanelaAcaoRobo`. Ele precisa dizer o que foi tentado, senão a
    pessoa decide no escuro."""
    completo = "PDM.6120.003 - TRANSFORMADOR POTENCIA"
    engine = _EngineFalso(nao_encontrado_para={
        completo, "PDM.6120.003", "TRANSFORMADOR POTENCIA",
    })
    bot = _bot(engine)

    status, motivo = bot.processar_item_individual({
        "pdm_escolhido": completo, "descricao_curta": "X", "origem": "Nacional",
        "tipo": "Não Reparável", "tipo de fabricação": "Catálogo",
        "codigo_projeto": "P1", "unidade": "Unidade",
    })

    assert status == "ERRO"
    assert "PDM.6120.003" in motivo
    assert "TRANSFORMADOR POTENCIA" in motivo
