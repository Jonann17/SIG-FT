r"""
As fichas ficaram ZERADAS embora o log dissesse "salvo e conferido".

Rodada de 2026-08-20, ficha 4500063671.0922. Cinco salvamentos, e os cinco
imprimiram exatamente a mesma dupla de linhas:

    [Injetor] Cliquei no botão SALVAR 1 de 4 da tela.
    Portal confirmou: A Ficha Técnica 4500063671.0922 foi modificada com sucesso.

A cadeia da prova, sem nenhum passo a completar:

1. São QUATRO botões SALVAR na tela e o robô clicou o **1** nas cinco vezes.
2. A mensagem foi sempre a mesma, e é GENÉRICA -- "a Ficha Técnica foi
   modificada".
3. Só que as mensagens REAIS dessas seções são outras, e o usuário mandou as
   duas: *"As condições de armazenamento foram modificadas com sucesso!"* e
   *"As características técnicas foram salvas com sucesso!"*.
4. Logo, o botão 1 não é o de Condições nem o de Características. É o de
   outra seção -- e a mensagem genérica aponta para Informações Gerais.
5. Portanto os campos foram DIGITADOS e nunca gravados. A ficha ficou vazia,
   que é exatamente o que o usuário viu.

E por que a conferência aprovou? Porque `conferir_subaba` releu **o mesmo
formulário não salvo**, que obviamente ainda tinha o que fora digitado. Reler
formulário sem recarga devolve o que se digitou. A proteção contra isso era o
toast -- e o toast mentiu, porque o clique foi no botão errado.

⚠️ DOIS ERROS MEUS, e os dois estão neste arquivo:

  (a) Eu DOCUMENTEI que `clicar_salvar_visivel` clica "o primeiro SALVAR
      visível, que nem sempre é o da seção" e me limitei a **logar o índice**.
      Logar um defeito não é consertá-lo. O índice serviu para diagnosticar
      depois -- e o preço foram duas fichas gravadas pela metade.

  (b) No commit anterior eu AFROUXEI a exigência da palavra da seção ("veio
      pela classe ⇒ 'novo' já basta"), com o argumento de que exigir a palavra
      amarraria a confirmação ao idioma. O argumento era hipotético; a falha é
      real: foi esse afrouxamento que deixou a mensagem genérica passar por
      confirmação. Com a palavra exigida, as cinco teriam falhado alto.
"""
import pytest

from sigft.core.rpa import portal as portal_mod
from sigft.core.rpa.portal import PMIBPortal


@pytest.fixture(autouse=True)
def _sem_dormir(monkeypatch):
    monkeypatch.setattr(portal_mod.time, "sleep", lambda _s: None)


class _TelaComQuatroSalvar:
    """Quatro seções, cada uma com o seu SALVAR.

    O duplo resolve o XPath ancorado (`.../ancestor-or-self::*[...]//button`)
    devolvendo o botão da seção citada na âncora -- que é o que o portal faz
    pela estrutura do DOM.
    """

    SECOES = ("GeneralInformations", "ManufacturerAndProvider",
              "TechnicalCharacteristics", "Conditions")

    def __init__(self):
        self.cliques = []
        self.toasts = []

    def contar(self, seletor):
        if "feedback-message-success" in seletor:
            return len(self.toasts)
        if "feedback-message-text" in seletor:
            return len(self.toasts)
        if "SALVAR" in seletor:
            return 1 if self._secao_da_ancora(seletor) else len(self.SECOES)
        return 0

    def _secao_da_ancora(self, seletor):
        """Reconhece as DUAS fórmulas de âncora -- a que desce e a que sobe.

        Desde 2026-08-20 o portal é consultado primeiro por
        `{ancora}//button[SALVAR]`; um duplo que só entendesse a subida diria
        "sem âncora" no caminho novo e mandaria clicar o primeiro da tela.
        """
        if "SALVAR" not in seletor:
            return None
        for secao in self.SECOES:
            if secao in seletor:
                return secao
        return None

    def texto(self, seletor):
        if "feedback-message" in seletor:
            import re
            achado = re.search(r"\)\[(\d+)\]", seletor)
            i = int(achado.group(1)) if achado else 1
            return self.toasts[i - 1] if i <= len(self.toasts) else ""
        return ""

    def esta_visivel(self, _seletor):
        return True

    def esta_habilitado(self, _seletor):
        return True

    def scroll_to(self, _seletor):
        pass

    def click_raw(self, seletor):
        secao = self._secao_da_ancora(seletor)
        if secao is None:
            # Sem âncora, XPath devolve o PRIMEIRO da tela -- e o primeiro é
            # Informações Gerais. É o defeito que zerou as fichas.
            secao = self.SECOES[0]
        self.cliques.append(secao)
        self.toasts = [MENSAGEM_DE[secao]]


MENSAGEM_DE = {
    "GeneralInformations": "A Ficha Técnica 4500063671.0922 foi modificada com sucesso.",
    "ManufacturerAndProvider": "Os fabricantes foram modificados com sucesso!",
    "TechnicalCharacteristics": "As características técnicas foram salvas com sucesso!",
    "Conditions": "As condições de armazenamento foram modificadas com sucesso!",
}


def _relogio():
    marca = {"t": 0.0}
    return (lambda s: marca.__setitem__("t", marca["t"] + s)), (lambda: marca["t"])


# =============================================================================
# 1. O SALVAR da SEÇÃO, não o primeiro da tela
# =============================================================================
def test_sem_ancora_clica_o_primeiro_e_e_o_ERRADO():
    """CONTRAPROVA: reproduz o defeito. Se este teste um dia passar a clicar
    a seção certa sem âncora, é o duplo que quebrou, não o código."""
    engine = _TelaComQuatroSalvar()

    PMIBPortal(engine).clicar_salvar_visivel("Características Técnicas")

    assert engine.cliques == ["GeneralInformations"]


def test_com_ancora_clica_o_SALVAR_da_secao():
    engine = _TelaComQuatroSalvar()
    dormir, agora = _relogio()

    ok = PMIBPortal(engine).salvar_e_confirmar(
        "Características Técnicas",
        ancora="//div[contains(@id, 'TechnicalCharacteristics')]",
        sleep_fn=dormir, agora_fn=agora)

    assert engine.cliques == ["TechnicalCharacteristics"]
    assert ok is True


def test_ancora_de_condicoes_clica_o_SALVAR_de_condicoes():
    engine = _TelaComQuatroSalvar()
    dormir, agora = _relogio()

    ok = PMIBPortal(engine).salvar_e_confirmar(
        "Armazenamento",
        ancora="//*[contains(@id, 'Conditions')]",
        sleep_fn=dormir, agora_fn=agora)

    assert engine.cliques == ["Conditions"]
    assert ok is True


# =============================================================================
# 2. A palavra da seção volta a ser exigida
# =============================================================================
def test_mensagem_GENERICA_nao_confirma_uma_secao_que_tem_palavra():
    """O defeito de (b), isolado: a mensagem de Informações Gerais não
    confirma Características, por mais que traga a classe de sucesso."""
    engine = _TelaComQuatroSalvar()
    dormir, agora = _relogio()

    # sem âncora => clica o botão errado => toast genérico
    ok = PMIBPortal(engine).salvar_e_confirmar(
        "Características Técnicas", sleep_fn=dormir, agora_fn=agora)

    assert ok is False, (
        "a mensagem genérica não nomeia a seção -- aceitá-la foi o que "
        "deixou cinco salvamentos errados passarem por certos"
    )


def test_secao_SEM_palavra_mapeada_ainda_aceita_a_classe():
    """A relaxação continua valendo onde ela era legítima: seção cuja redação
    o projeto não conhece não tem como exigir palavra nenhuma."""
    engine = _TelaComQuatroSalvar()
    dormir, agora = _relogio()

    ok = PMIBPortal(engine).salvar_e_confirmar(
        "Fabricantes e Fornecedores",
        ancora="//div[contains(@id, 'ManufacturerAndProvider')]",
        sleep_fn=dormir, agora_fn=agora)

    assert ok is True


# =============================================================================
# 3. Âncora que não casa nada não pode calar
# =============================================================================
def test_ancora_que_nao_acha_botao_avisa_antes_de_cair_no_generico():
    """Cair no comportamento antigo em silêncio recriaria o defeito sem
    deixar rastro. Se a âncora falhar, o log diz."""
    class _SemBotaoAncorado(_TelaComQuatroSalvar):
        def contar(self, seletor):
            # Nenhuma das duas fórmulas de âncora acha nada.
            if self._secao_da_ancora(seletor):
                return 0
            return super().contar(seletor)

    engine = _SemBotaoAncorado()
    linhas = []

    PMIBPortal(engine).clicar_salvar_do_bloco(
        "//div[contains(@id, 'TechnicalCharacteristics')]",
        "Características Técnicas", linhas.append)

    assert any("âncora" in l.lower() for l in linhas)
    assert engine.cliques == ["GeneralInformations"], "caiu na varredura antiga"


# =============================================================================
# 4. A âncora tem de olhar PARA DENTRO antes de subir
# =============================================================================
# Log de 2026-08-20, 14h08 -- com a âncora já implementada:
#
#     [Injetor] SALVAR da seção Características Técnicas (ancorado, não o 1º
#               da tela).
#     [!] Não vi a confirmação de 'Características Técnicas'. A última
#         mensagem na tela foi: 'A Ficha Técnica 4500063671.1418 foi
#         modificada com sucesso.'
#
# A mensagem genérica de novo -- ou seja, o botão clicado continuou sendo o de
# Informações Gerais, apesar da âncora. A explicação está na fórmula:
#
#     {ancora}/ancestor-or-self::*[.//button[SALVAR]][1]//button[SALVAR]
#
# Ela SOBE até achar um ancestral que contenha um SALVAR. Se a `div` da âncora
# não contém o seu (por ser uma div interna, ou por o botão ficar num rodapé
# irmão), a subida não para na seção: vai até o container que contém TODOS os
# botões, e `//button[SALVAR]` de lá devolve o primeiro do documento.
#
# O conserto é olhar PARA DENTRO primeiro. Quando o container da seção tem o
# seu próprio SALVAR -- o caso normal --, `{ancora}//button[SALVAR]` é exato e
# não há subida nenhuma. A subida vira o plano B, e a varredura da tela o C.

class _SecaoComSalvarDentro:
    """A seção CONTÉM o seu SALVAR. Subir daqui erra; descer acerta."""

    def __init__(self):
        self.cliques = []
        self.toasts = []

    def contar(self, seletor):
        if "feedback-message-success" in seletor:
            return len(self.toasts)
        if "feedback-message-text" in seletor:
            return len(self.toasts)
        if "SALVAR" not in seletor:
            return 0
        if "ancestor-or-self" in seletor:
            # A subida encontra o container de TODOS os botões.
            return 4
        if "TechnicalCharacteristics" in seletor:
            return 1        # o SALVAR de dentro da seção
        return 4

    def texto(self, seletor):
        if "feedback-message" in seletor:
            import re
            achado = re.search(r"\)\[(\d+)\]", seletor)
            i = int(achado.group(1)) if achado else 1
            return self.toasts[i - 1] if i <= len(self.toasts) else ""
        return ""

    def esta_visivel(self, _s):
        return True

    def esta_habilitado(self, _s):
        return True

    def scroll_to(self, _s):
        pass

    def click_raw(self, seletor):
        subiu = "ancestor-or-self" in seletor
        self.cliques.append("GeneralInformations" if subiu else "TechnicalCharacteristics")
        self.toasts = [MENSAGEM_DE[self.cliques[-1]]]


def test_a_ancora_desce_antes_de_subir():
    engine = _SecaoComSalvarDentro()
    dormir, agora = _relogio()

    ok = PMIBPortal(engine).salvar_e_confirmar(
        "Características Técnicas",
        ancora="//div[contains(@id, 'TechnicalCharacteristics')]",
        sleep_fn=dormir, agora_fn=agora)

    assert engine.cliques == ["TechnicalCharacteristics"], (
        "subir a partir da âncora encontra o container de TODOS os botões e "
        "clica o primeiro -- foi o que manteve o defeito depois da 1ª correção"
    )
    assert ok is True


def test_sem_SALVAR_dentro_da_secao_a_subida_continua_valendo():
    """O plano B não some: seção cujo botão fica fora do container ainda é
    salva, e o log diz que foi por subida."""
    class _SemSalvarDentro(_SecaoComSalvarDentro):
        def contar(self, seletor):
            if "SALVAR" in seletor and "TechnicalCharacteristics" in seletor \
                    and "ancestor-or-self" not in seletor:
                return 0
            return super().contar(seletor)

    engine = _SemSalvarDentro()
    dormir, agora = _relogio()
    linhas = []

    PMIBPortal(engine).salvar_e_confirmar(
        "Fabricantes e Fornecedores",
        ancora="//div[contains(@id, 'TechnicalCharacteristics')]",
        callback_log=linhas.append, sleep_fn=dormir, agora_fn=agora)

    assert engine.cliques == ["GeneralInformations"]
    assert any("subindo" in l.lower() for l in linhas)
