r"""
Condições da ficha duplicada (CP 6.4) — cópia literal, salva e CONFERIDA.

A cópia é por XPATH, não por significado: o que está em `Input_PackingLength`
na original vai para `Input_PackingLength` na alvo. Isso é o que dispensa
interpretar rótulo, converter unidade ou traduzir radio -- e é legítimo aqui
porque a operação é DUPLICAR, não preencher.

O que estes testes trancam, além da cópia em si, é o pedido do usuário de
2026-08-19: *"antes de sair de cada uma das páginas, quero que você valide se
de fato conseguiu colocar os dados"*. Salvar com o toast prova que o portal
aceitou; só a releitura prova que o valor ficou.
"""
import pytest

from sigft.core.rpa.portal import PMIBPortal
from sigft.core.rpa import seletores_duplicada as sel
from sigft.services import duplicadas_condicoes as cond


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(cond.time, "sleep", lambda _s: None)


class _EngineDeCondicoes:
    """Tela de Condições: cada campo é endereçado pelo SUFIXO do id.

    O duplo resolve o XPath `//*[contains(@id, 'X')]` de volta para `X`, que é
    exatamente o que o portal faz -- casar o sufixo com o campo cujo id
    gerado termina nele.
    """

    def __init__(self, valores=None, marcados=(), some_ao_ler=(),
                 nao_aceita=(), esvazia_ao_salvar=()):
        self.valores = dict(valores or {})
        self.marcados = set(marcados)
        self.some_ao_ler = set(some_ao_ler)
        self.nao_aceita = set(nao_aceita)
        self.esvazia_ao_salvar = set(esvazia_ao_salvar)
        self.escritas = []
        self.cliques = []

    @staticmethod
    def _sufixo(seletor):
        import re
        achado = re.search(r"contains\(@id, '([^']+)'\)", seletor)
        return achado.group(1) if achado else seletor

    def get_value(self, seletor):
        sufixo = self._sufixo(seletor)
        if sufixo in self.some_ao_ler:
            raise RuntimeError("campo não está na tela")
        return self.valores.get(sufixo, "")

    def fill(self, seletor, texto):
        sufixo = self._sufixo(seletor)
        self.escritas.append((sufixo, texto))
        if sufixo not in self.nao_aceita:
            self.valores[sufixo] = texto

    def esta_marcado(self, seletor):
        sufixo = self._sufixo(seletor)
        if sufixo in self.some_ao_ler:
            raise RuntimeError("campo não está na tela")
        return sufixo in self.marcados

    def click(self, seletor):
        sufixo = self._sufixo(seletor)
        self.cliques.append(sufixo)
        self.marcados ^= {sufixo}   # clicar alterna o estado

    def click_dom(self, seletor):
        self.click(seletor)

    def contar(self, seletor):
        """Existe na tela? É o que `valor_se_existir` pergunta ANTES de ler --
        o conserto do travamento de 2026-08-20. `some_ao_ler` é justamente
        "não está na tela", então tem de contar zero aqui também; se contasse
        um, o duplo diria que o campo existe e a leitura seguinte estouraria,
        que é o comportamento antigo."""
        return 0 if self._sufixo(seletor) in self.some_ao_ler else 1

    def texto(self, _seletor):
        return ""


class _PortalDeCondicoes:
    # Emprestados do PMIBPortal REAL: os dois só usam `self.engine`, então
    # ligá-los aqui testa a implementação de verdade em vez de uma cópia
    # que envelhece sozinha. São o conserto do travamento de 2026-08-20 --
    # ler o que pode não existir sem pagar o timeout do motor.
    texto_se_existir = PMIBPortal.texto_se_existir
    valor_se_existir = PMIBPortal.valor_se_existir

    def __init__(self, engine, confirma=True):
        self.engine = engine
        self.confirma = confirma
        self.salvos = []

    def safe_click(self, seletor):
        self.engine.cliques.append(seletor)

    def safe_fill(self, seletor, texto):
        self.engine.fill(seletor, texto)

    def check_or_uncheck(self, seletor, deve_marcar, callback_log=None):
        return PMIBPortal.check_or_uncheck(self, seletor, deve_marcar, callback_log)

    def salvar_e_confirmar(self, nome_secao="", callback_log=None, **_kwargs):
        self.salvos.append(nome_secao)
        for sufixo in self.engine.esvazia_ao_salvar:
            self.engine.valores[sufixo] = ""
        return self.confirma


def _tela(**kwargs):
    engine = _EngineDeCondicoes(**{k: v for k, v in kwargs.items()
                                   if k != "confirma"})
    return _PortalDeCondicoes(engine, kwargs.get("confirma", True)), engine


UM_CAMPO_DE_CADA = {
    "Armazenamento": {"Input_PackingLength": "40", "Checkbox4": True},
    "Transporte": {"TextArea_TransportPackagingPT": "Caixa de papelão"},
    "Manutenção": {"TextArea_CleaningMethodPT": "Pano seco"},
    "Descarte": {"TextArea_DiscardTypePT": "Sucata"},
}


# =============================================================================
# 1. Ler a original
# =============================================================================
def test_ler_traz_texto_e_booleano_com_o_tipo_certo():
    """O TIPO é o que diz, na escrita, se o campo se digita ou se clica."""
    portal, _ = _tela(valores={"Input_PackingLength": "40"}, marcados=["Checkbox4"])

    lido = cond.ler(portal)

    assert lido["Armazenamento"]["Input_PackingLength"] == "40"
    assert lido["Armazenamento"]["Checkbox4"] is True
    assert lido["Armazenamento"]["Checkbox5"] is False


def test_campo_que_nao_esta_na_tela_NAO_entra_no_dicionario():
    """Entrar com "" faria a escrita APAGAR um campo da alvo por causa de uma
    leitura que falhou -- o pior desfecho possível numa duplicação."""
    portal, _ = _tela(some_ao_ler=["Input_PackingLength", "Checkbox4"])

    lido = cond.ler(portal)

    assert "Input_PackingLength" not in lido["Armazenamento"]
    assert "Checkbox4" not in lido["Armazenamento"]


def test_ler_percorre_as_QUATRO_subabas():
    portal, _ = _tela()

    lido = cond.ler(portal)

    assert set(lido) == set(sel.CONDICOES_POR_SUBABA)


# =============================================================================
# 2. Escrever na alvo
# =============================================================================
def test_cada_subaba_e_salva_separadamente():
    """Cada aba tem o seu SALVAR no portal -- é assim que a seção funciona."""
    portal, _ = _tela()

    cond.escrever(portal, UM_CAMPO_DE_CADA)

    # O nome vai CRU (e não "Condições / Armazenamento") porque é a chave de
    # `PALAVRA_DA_SECAO` no portal -- é com ela que o toast é casado pela
    # palavra da seção, e um toast remanescente de outra sub-aba não confirma
    # esta.
    assert portal.salvos == ["Armazenamento", "Transporte",
                             "Manutenção", "Descarte"]


def test_texto_vazio_nao_e_escrito():
    """A alvo nasce vazia: escrever "" não acrescenta nada e é mais uma chance
    de disparar validação do portal sem motivo."""
    portal, engine = _tela()

    cond.escrever(portal, {"Transporte": {"TextArea_PositionCarePT": "   "}})

    assert engine.escritas == []


def test_booleano_FALSO_nao_marca_o_campo():
    portal, engine = _tela()

    cond.escrever(portal, {"Armazenamento": {"Checkbox4": False}})

    assert "Checkbox4" not in engine.marcados


def test_booleano_VERDADEIRO_marca_o_campo():
    portal, engine = _tela()

    cond.escrever(portal, {"Armazenamento": {"Checkbox4": True}})

    assert "Checkbox4" in engine.marcados


# =============================================================================
# 3. A conferência antes de sair da página
# =============================================================================
def test_campo_que_nao_ficou_gravado_vira_PENDENCIA_com_o_nome():
    """*"Antes de sair de cada uma das páginas, quero que você valide se de
    fato conseguiu colocar os dados."* O salvamento confirmou; o valor não
    ficou. Sem a releitura, isso sai como sucesso."""
    portal, _ = _tela(esvazia_ao_salvar=["Input_PackingLength"])
    linhas = []

    resultado = cond.escrever(portal, UM_CAMPO_DE_CADA, linhas.append)

    assert resultado.ok is False
    assert "Input_PackingLength" in "\n".join(linhas)


def test_tudo_conferido_devolve_sucesso():
    portal, _ = _tela()

    resultado = cond.escrever(portal, UM_CAMPO_DE_CADA, lambda _m: None)

    assert resultado.ok is True


def test_salvamento_nao_confirmado_reprova_a_subaba():
    portal, _ = _tela(confirma=False)

    resultado = cond.escrever(portal, UM_CAMPO_DE_CADA, lambda _m: None)

    assert resultado.ok is False
    assert "não confirmou" in resultado.detalhe


def test_uma_subaba_ruim_nao_impede_as_outras():
    """Ficha meio preenchida com o log dizendo o que faltou é melhor do que
    ficha vazia com erro genérico."""
    portal, engine = _tela(confirma=True, esvazia_ao_salvar=["Input_PackingLength"])

    cond.escrever(portal, UM_CAMPO_DE_CADA, lambda _m: None)

    assert len(portal.salvos) == 4, "as 4 sub-abas foram tentadas"
    assert engine.valores.get("TextArea_DiscardTypePT") == "Sucata"


def test_origem_vazia_e_PENDENTE_e_nao_ok():
    """⚠️ MUDOU EM 2026-08-21, pelo log do usuário: CONDIÇÕES saía COMPLETO em
    TODA ficha, para uma seção que ninguém tentou copiar.

    O extrator ainda não lê as Condições do modo de visualização -- ele mesmo
    escreve isso no log, duas linhas antes ("Condições NÃO serão copiadas:
    falta o mapa RÓTULO→campo"). Ou seja, a origem chega vazia SEMPRE, e
    `ok=True` aqui virava COMPLETO na planilha.

    `pendente` diz a verdade nos dois lados: não conta como falha no resumo do
    lote (não é falha, é etapa que falta) e não deixa a coluna fechar."""
    portal, _ = _tela()

    resultado = cond.escrever(portal, {}, lambda _m: None)

    assert resultado.ok is False
    assert resultado.pendente is True
    assert portal.salvos == []   # e continua sem escrever nada no portal


# =============================================================================
# 4. O mapa em si
# =============================================================================
def test_armazenamento_e_a_aba_que_ja_vem_aberta():
    """Posição `None` = não clica em nada. Clicar numa aba já aberta não é
    inofensivo em toda tela do OutSystems."""
    assert sel.CONDICOES_POR_SUBABA["Armazenamento"]["posicao"] is None


def test_nenhum_id_gerado_no_mapa():
    """`b10-b17-b1-` é gerado e muda de sessão -- a regra do projeto
    (`IDS_GERADOS_NAO_USAR`) vale aqui como em todo o resto do arquivo."""
    import re
    for nome, mapa in sel.CONDICOES_POR_SUBABA.items():
        for sufixo in tuple(mapa["textos"]) + tuple(mapa["booleanos"]):
            assert not re.match(r"^b\d+-", sufixo), f"{nome}/{sufixo} é id gerado"
