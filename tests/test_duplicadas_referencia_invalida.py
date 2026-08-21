r"""
Por que o "+" da referência nunca comitou — respondido pelo log de auditoria.

Três rodadas com o mesmo sintoma e nenhuma explicação. O dump do HTML que o
robô passou a gravar quando a linha não entra (log de 2026-08-20, 09:51:33)
resolveu em duas linhas:

    <input class="form-control OSFillParent not-valid" required=""
           type="text" aria-required="true" maxlength="100" value="FM-9222"
           id="b10-b11-b4-Input_TextVar"
           aria-describedby="b10-b11-b4-Input_TextVar_DescribedBy">

    <a href="#"><i class="icon fa fa-plus-circle fa-2x"></i></a>

O "+" está lá, é um `<a>` normal, e o clique chega nele. O que trava é o
CAMPO:

  * **`not-valid`** -- a classe que o OutSystems põe num campo que FALHOU a
    validação. Enquanto ela está lá, o "+" não adiciona nada. Não era clique
    perdido nem seletor errado: era o formulário recusando.
  * **`aria-describedby="…_DescribedBy"`** -- e o motivo está escrito ali. O
    OutSystems pendura a mensagem de validação num elemento com esse id, e o
    robô nunca olhou para ele.

⚠️ E ISSO EXPLICA UM SEGUNDO DEFEITO, mais caro. `texto_do_aviso_de_colisao`
procura a colisão SÓ no bloco `CoincidenceReference`. Se o portal reporta "a
referência já existe" **no campo**, o robô não vê colisão nenhuma, nunca
avança para `FM-9222'D1`, e desiste na primeira tentativa -- com a regra do
`'D` inteira implementada e nunca usada.

O conserto tem três partes, e a terceira é a que importa:

  1. ler a mensagem que o portal pendurou no campo;
  2. reconhecer `not-valid` como "o portal recusou", e dizer o motivo;
  3. tratar a mensagem de duplicidade como colisão -- somando à checagem do
     bloco, não substituindo.
"""
import pytest

from sigft.core.rpa import seletores_duplicada as sel
from sigft.core.rpa.portal import PMIBPortal
from sigft.services import duplicadas_injetor as injetor


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(injetor.time, "sleep", lambda _s: None)


class _EngineComValidacao:
    """Campo que pode estar `not-valid` e trazer uma mensagem pendurada."""

    ID_DO_CAMPO = "b10-b11-b4-Input_TextVar"
    ID_DA_MENSAGEM = "b10-b11-b4-Input_TextVar_DescribedBy"

    def __init__(self, classe="form-control OSFillParent", mensagem=""):
        self.classe = classe
        self.mensagem = mensagem

    def contar(self, seletor):
        if self.ID_DA_MENSAGEM in seletor:
            return 1 if self.mensagem else 0
        if self.ID_DO_CAMPO in seletor:
            return 1
        return 0

    def atributo(self, seletor, nome):
        if self.ID_DO_CAMPO not in seletor:
            return ""
        if nome == "class":
            return self.classe
        if nome == "aria-describedby":
            return self.ID_DA_MENSAGEM
        return ""

    def texto(self, seletor):
        return self.mensagem if self.ID_DA_MENSAGEM in seletor else ""


class _PortalComValidacao:
    texto_se_existir = PMIBPortal.texto_se_existir

    def __init__(self, engine):
        self.engine = engine


def _campo():
    return sel.XPATH_POR_ID.format(id=f"'{_EngineComValidacao.ID_DO_CAMPO}'")


# =============================================================================
# 1. Ler o que o portal escreveu NO CAMPO
# =============================================================================
def test_le_a_mensagem_pendurada_pelo_aria_describedby():
    engine = _EngineComValidacao(mensagem="A referência já existe!")
    portal = _PortalComValidacao(engine)

    assert injetor.mensagem_de_validacao(portal, _campo()) == "A referência já existe!"


def test_campo_sem_mensagem_devolve_vazio():
    portal = _PortalComValidacao(_EngineComValidacao())

    assert injetor.mensagem_de_validacao(portal, _campo()) == ""


# =============================================================================
# 2. `not-valid` é "o portal recusou"
# =============================================================================
def test_reconhece_a_classe_not_valid():
    engine = _EngineComValidacao(classe="form-control OSFillParent not-valid")

    assert injetor.campo_recusado(_PortalComValidacao(engine), _campo()) is True


def test_campo_valido_nao_e_recusado():
    engine = _EngineComValidacao(classe="form-control OSFillParent")

    assert injetor.campo_recusado(_PortalComValidacao(engine), _campo()) is False


def test_not_valid_nao_casa_por_substring_de_outra_classe():
    """`not-validated` NÃO é `not-valid`. Casar por substring transformaria
    qualquer classe parecida num campo recusado."""
    engine = _EngineComValidacao(classe="form-control not-validated-yet")

    assert injetor.campo_recusado(_PortalComValidacao(engine), _campo()) is False


# =============================================================================
# 3. A mensagem do CAMPO conta como colisão -- e é o que faz o 'D voltar a valer
# =============================================================================
@pytest.mark.parametrize("mensagem", [
    "A referência já existe!",
    "Referencia ja existente para este material",
    "Valor duplicado",
    "Referência repetida",
])
def test_mensagem_de_duplicidade_no_campo_conta_como_colisao(mensagem):
    """Sem isto, o robô não vê colisão nenhuma, nunca avança para `'D1` e
    desiste na primeira tentativa -- com a regra do `'D` inteira implementada
    e jamais usada."""
    assert injetor.e_mensagem_de_duplicidade(mensagem) is True


@pytest.mark.parametrize("mensagem", [
    "Campo obrigatório",
    "Máximo de 100 caracteres",
    "",
])
def test_outra_recusa_NAO_vira_tentativa_de_sufixo(mensagem):
    """Gastar 20 sufixos num campo obrigatório vazio esconderia o erro real."""
    assert injetor.e_mensagem_de_duplicidade(mensagem) is False


def test_o_aviso_de_colisao_soma_o_bloco_E_o_campo():
    """*"As duas checagens se somam, não se substituem"* -- é o que o próprio
    arquivo já dizia sobre o bloco `CoincidenceReference`. O campo é a
    terceira fonte, e a que funcionou na ficha real."""
    class _SemBloco(_EngineComValidacao):
        def contar(self, seletor):
            if "CoincidenceReference" in seletor:
                return 0
            return super().contar(seletor)

        def element_exists(self, seletor):
            return "CoincidenceReference" not in seletor

    engine = _SemBloco(classe="form-control not-valid",
                       mensagem="A referência já existe!")
    portal = _PortalComValidacao(engine)

    aviso = injetor.texto_do_aviso_de_colisao(portal, _campo())

    assert "já existe" in aviso


# =============================================================================
# 4. O modo de auditoria não fotografava nada
# =============================================================================
def test_a_foto_tem_um_alvo_pelo_id_do_container():
    """O log de 2026-08-20 trouxe, nas QUATRO seções:

        (nada casou para: //div[contains(@class, 'osui-tabs__content')],
                          //form | //div[@id='b12'])

    Ou seja: a auditoria estava ligada e não fotografava nada -- a ferramenta
    que existe para mapear o portal sem acesso a ele não mapeava. Foi sorte o
    dump do "+" ser por seletor explícito, senão a causa da referência
    continuaria desconhecida.

    Os HTMLs que o usuário mandou revelam o padrão: as abas apontam para o
    container por `aria-controls`, e o id termina em `_Content`.
    """
    from sigft.services import duplicadas_extrator as extrator

    assert "_Content" in extrator.XPATH_CONTEUDO_POR_ID


def test_a_foto_nao_depende_mais_de_um_id_gerado():
    """`//div[@id='b12']` era id GERADO -- o que este projeto proíbe. Ele
    mudou, e a foto passou a devolver vazio."""
    from sigft.services import duplicadas_extrator as extrator

    assert "b12" not in extrator.XPATH_FICHA_INTEIRA


def test_a_foto_tem_um_ultimo_recurso_que_sempre_casa():
    """Foto grande demais ainda é infinitamente melhor que "(nada casou)":
    pelo menos contém a resposta."""
    from sigft.services import duplicadas_extrator as extrator

    assert "//body" in extrator.XPATH_FICHA_INTEIRA
