r"""
SALVAR sem prova era o buraco que sobrou (2026-08-19).

`clicar_salvar_visivel` fazia isto:

    for cada botão SALVAR da tela:
        se visível e habilitado:
            clica, dorme 2,5s e **devolve True**

Três problemas num método de dez linhas, e os três aparecem no relato do
usuário (*"ele não conseguiu salvar a seção de características técnicas,
talvez tenha faltado clicar no botão"*):

1. **`True` não significa "salvou"** -- significa "achei um botão e cliquei".
   Nada na tela é lido depois.
2. **Clica o PRIMEIRO SALVAR visível**, e a ficha tem um por seção. Se o da
   seção errada estiver visível primeiro, ele é o clicado -- e o retorno segue
   `True`.
3. **Os avisos saíam por `print()`**, que no app empacotado não tem console:
   a linha "[Aviso] Botão SALVAR não encontrado" simplesmente não existia para
   quem estava olhando o log. Foi por isso que o log da sessão não trouxe
   nada sobre o salvamento.

O usuário pediu o mesmo tratamento que Condições ganhou: *"tal como fizemos
para upload característica, devemos esperar a mensagem de salvo com sucesso"*.

⚠️ E ESPERAR "uma mensagem de sucesso" NÃO BASTA -- o toast *"aparece
relativamente rápido, fica um tempo e depois some"*. Quando o robô salva a 2ª
seção, o toast da 1ª ainda pode estar na tela, e uma checagem ingênua daria a
2ª por salva sem ter sido. Em Condições isso é resolvido exigindo a palavra da
seção; aqui não dá, porque **não sabemos a redação** do toast de Fabricantes
nem do de Características.

A saída é a mesma que este módulo já usa para achar o campo que nasce: FOTO
DE ANTES. Vale o toast que for de sucesso **e não estava lá antes do clique**.
Funciona sem conhecer a redação, e o texto lido vai para o log -- que é como
a tabela `PALAVRA_DA_SECAO` vai poder ser completada numa próxima sessão.
"""
import pytest

from sigft.core.rpa import portal as portal_mod
from sigft.core.rpa.portal import PMIBPortal


@pytest.fixture(autouse=True)
def _sem_dormir_de_verdade(monkeypatch):
    """`clicar_salvar_visivel` tem `sleep(0,5)` + `sleep(2,5)` embutidos (a
    requisição do OutSystems). São reais no portal e puro tempo morto aqui --
    sem isto, estes 6 testes sozinhos custam 16 segundos da suíte."""
    monkeypatch.setattr(portal_mod.time, "sleep", lambda _s: None)


class _EngineComToast:
    """Tela com N botões SALVAR e uma fila de toasts.

    `toasts` é o que está visível AGORA; `toast_ao_salvar` é o que o portal
    acrescenta quando o clique realmente grava. Um duplo que só acrescentasse
    não reproduziria o problema real -- o toast VELHO continua na lista.
    """

    def __init__(self, botoes=1, visiveis=None, habilitados=None,
                 toasts=(), toast_ao_salvar=None):
        self.botoes = botoes
        self.visiveis = set(range(1, botoes + 1)) if visiveis is None else set(visiveis)
        self.habilitados = set(range(1, botoes + 1)) if habilitados is None else set(habilitados)
        self.toasts = list(toasts)
        self.toast_ao_salvar = toast_ao_salvar
        self.cliques = []

    def _indice(self, seletor):
        import re
        achado = re.search(r"\)\[(\d+)\]", seletor)
        return int(achado.group(1)) if achado else None

    def contar(self, seletor):
        if "feedback-message-text" in seletor:
            return len(self.toasts)
        if "SALVAR" in seletor:
            return self.botoes
        return 0

    def texto(self, seletor):
        if "feedback-message-text" in seletor:
            i = self._indice(seletor)
            return self.toasts[i - 1] if i and i <= len(self.toasts) else ""
        return ""

    def esta_visivel(self, seletor):
        return self._indice(seletor) in self.visiveis

    def esta_habilitado(self, seletor):
        return self._indice(seletor) in self.habilitados

    def scroll_to(self, seletor):
        pass

    def click_raw(self, seletor):
        self.cliques.append(self._indice(seletor))
        if self.toast_ao_salvar:
            self.toasts.append(self.toast_ao_salvar)


def _portal(engine):
    return PMIBPortal(engine)


def _sem_esperar():
    """`sleep`/`monotonic` de mentira: o teste não pode gastar 8 segundos."""
    relogio = {"t": 0.0}

    def dormir(segundos):
        relogio["t"] += segundos

    def agora():
        return relogio["t"]

    return dormir, agora


# =============================================================================
# 1. O toast NOVO é o que confirma
# =============================================================================
def test_salvar_confirma_com_o_toast_que_APARECEU():
    engine = _EngineComToast(
        toast_ao_salvar="As características técnicas foram modificadas com sucesso!")
    dormir, agora = _sem_esperar()

    ok = _portal(engine).salvar_e_confirmar(
        "Características Técnicas", sleep_fn=dormir, agora_fn=agora)

    assert ok is True
    assert engine.cliques == [1]


def test_toast_VELHO_de_outra_secao_nao_confirma():
    """O caso que a mecânica do toast cria: salvei Fabricantes, o toast dela
    ainda está na tela, e agora salvo Características. Sem a foto de antes,
    esse toast remanescente daria a 2ª seção por salva."""
    engine = _EngineComToast(
        toasts=["Os fabricantes foram modificados com sucesso!"],
        toast_ao_salvar=None)          # o SALVAR não produziu toast nenhum
    dormir, agora = _sem_esperar()

    ok = _portal(engine).salvar_e_confirmar(
        "Características Técnicas", sleep_fn=dormir, agora_fn=agora)

    assert ok is False, "o toast que já estava na tela não prova nada"


def test_toast_que_nao_e_de_sucesso_nao_confirma():
    engine = _EngineComToast(
        toast_ao_salvar="Preencha os campos obrigatórios antes de continuar.")
    dormir, agora = _sem_esperar()

    ok = _portal(engine).salvar_e_confirmar("Características Técnicas",
                                            sleep_fn=dormir, agora_fn=agora)

    assert ok is False


def test_a_mensagem_lida_vai_para_o_log():
    """É o que permite descobrir a redação real sem o usuário inspecionar a
    tela -- e completar `PALAVRA_DA_SECAO` numa próxima sessão."""
    engine = _EngineComToast(
        toast_ao_salvar="Erro ao gravar: a referência já existe.")
    dormir, agora = _sem_esperar()
    linhas = []

    _portal(engine).salvar_e_confirmar("Características Técnicas", linhas.append,
                                       sleep_fn=dormir, agora_fn=agora)

    assert any("Erro ao gravar" in l for l in linhas)


# =============================================================================
# 2. Qual botão foi clicado, e o log dizendo
# =============================================================================
def test_botao_SALVAR_ausente_e_reportado_pelo_CALLBACK_e_nao_por_print():
    """No app empacotado não há console: `print` some. Era por isso que o log
    da sessão real não dizia nada sobre o salvamento."""
    engine = _EngineComToast(botoes=1, visiveis=[], habilitados=[])
    linhas = []

    ok = _portal(engine).clicar_salvar_visivel("Características Técnicas",
                                               linhas.append)

    assert ok is False
    assert any("SALVAR" in l for l in linhas)


def test_o_log_diz_QUAL_botao_de_quantos_foi_clicado():
    """A ficha tem um SALVAR por seção. Saber que foi clicado "o 2 de 3" é a
    diferença entre diagnosticar e adivinhar quando a seção errada é salva."""
    engine = _EngineComToast(botoes=3, visiveis=[2, 3], habilitados=[2, 3])
    linhas = []

    _portal(engine).clicar_salvar_visivel("Características Técnicas", linhas.append)

    assert engine.cliques == [2]
    assert any("2" in l and "3" in l for l in linhas), (
        "o log tem de trazer o índice do botão e o total na tela"
    )


# =============================================================================
# 3. Conferir a página ANTES de sair dela
# =============================================================================
# *"Antes de sair de cada uma das páginas, quero que você valide se de fato
# conseguiu colocar os dados"* (usuário, 2026-08-19).
#
# O toast prova que o portal ACEITOU o salvamento. Não prova que a tabela
# ficou como se queria -- uma exclusão que falhou, uma linha que voltou na
# recarga, uma paginação que escondeu duas linhas: tudo isso convive com um
# toast de sucesso. A releitura depois do save é a única coisa que fecha.
from sigft.services import duplicadas_injetor as injetor  # noqa: E402
from tests.test_duplicadas_injetor import _com_tabela  # noqa: E402


@pytest.fixture(autouse=True)
def _injetor_sem_espera(monkeypatch):
    monkeypatch.setattr(injetor.time, "sleep", lambda _s: None)


def test_depois_de_salvar_a_tabela_e_RELIDA():
    """Uma característica que sobreviveu à purga impede o salvamento das
    próximas fichas -- *"se tiver mais características, estas devem ser
    excluídas, pois se não, não vai conseguir salvar"*. Se sobrou linha depois
    do save, a seção não está pronta."""
    portal, engine = _com_tabela(["CODIGO PMIB"])
    # O portal "recarrega" e traz de volta uma característica que a purga
    # tinha apagado -- é o que a releitura existe para pegar.
    portal.linhas_apos_salvar = ["CODIGO PMIB", "TENSÃO NOMINAL"]
    logs = []

    resultado = injetor.limpar_caracteristicas(portal, "4500063671.1263",
                                               callback_log=logs.append)

    assert resultado.ok is False
    assert any("sobrou" in l.lower() or "sobraram" in l.lower() for l in logs)


def test_tabela_com_so_o_CODIGO_PMIB_depois_de_salvar_passa():
    portal, engine = _com_tabela(["CODIGO PMIB"])
    portal.linhas_apos_salvar = ["CODIGO PMIB"]

    resultado = injetor.limpar_caracteristicas(portal, "4500063671.1263",
                                               callback_log=lambda _m: None)

    assert resultado.ok is True
