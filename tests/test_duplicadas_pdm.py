r"""
O PDM da ficha ALVO decide QUAIS características ela tem (CP 6.4).

Rodada real de 2026-08-20, ficha 4500063671.0922:

    Características: 26 apagada(s), 0 preservada(s).
    [Erro] Nenhuma linha de CODIGO PMIB encontrada. A ficha ficou sem a
           característica da duplicação.

O usuário explicou o que eu não tinha como saber: *"a ficha 922 estava com um
PDM diferente, então as características técnicas não estavam corretas na
ficha"*. Ela estava com `PDM.4820.010 - REGULADOR, PRESSAO`, e o robô apagou
as 26 características DAQUELE PDM procurando uma linha `CODIGO PMIB` que ali
não existe.

Não é um erro de leitura da tabela: é ordem de operações. A ficha duplicada
tem de estar no `PDM.9900.000 - FICHA PMIB, DUPLICADA` ANTES da purga, porque
é o PDM que decide a lista. Trocar depois não desfaz o que foi apagado.
"""
import pytest

from sigft.core.rpa import seletores_duplicada as sel
from sigft.core.rpa.portal import PMIBPortal
from sigft.services import duplicadas_pdm as pdm


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(pdm.time, "sleep", lambda _s: None)


class _EngineComPDM:
    def __init__(self, pdm_atual="", opcoes=(), troca_pega=True,
                 dropdown_trava=False):
        self.pdm = pdm_atual
        self.opcoes = list(opcoes)
        self.troca_pega = troca_pega
        self.filtro = ""
        self.cliques = []
        self.teclas = []
        # A lista abre quando o combo é clicado e fecha ao escolher/ESC.
        # `dropdown_trava=True` modela o combo que NÃO fecha -- o caso de
        # 2026-08-25, em que a lista ficava por cima e todo SALVAR seguinte
        # falhava com TempoEsgotado.
        self.dropdown_aberto = False
        self.dropdown_trava = dropdown_trava

    def press(self, teclas):
        self.teclas.append(teclas)
        if teclas == "ESCAPE" and not self.dropdown_trava:
            self.dropdown_aberto = False

    def contar(self, seletor):
        # A ORDEM DAS PERGUNTAS IMPORTA. O seletor da opção filtrada contém
        # `role='option'` E `vscomp-option-text`; o de "a lista está aberta?"
        # é o do CONTAINER. Testar na ordem errada faria o dublê responder
        # "achei a opção" para a pergunta "a lista fechou?".
        if "vscomp-dropbox-container" in seletor:
            return 1 if self.dropdown_aberto else 0
        if "role='option'" in seletor and "vscomp-option-text" not in seletor:
            return 3 if self.dropdown_aberto else 0
        if "vscomp-option-text" in seletor:
            alvo = self.filtro
            return sum(1 for o in self.opcoes if alvo and o.startswith(alvo))
        if "vscomp-value" in seletor or "vscomp-toggle-button" in seletor:
            return 1 if self.pdm else 0
        return 0

    def texto(self, seletor):
        if "vscomp-value" in seletor:
            return self.pdm
        return ""

    def element_exists(self, seletor):
        return "vscomp-search-input" in seletor

    def click(self, seletor):
        self.cliques.append(seletor)
        if "vscomp-toggle-button" in seletor:
            self.dropdown_aberto = True
        if "vscomp-option-text" in seletor and not self.dropdown_trava:
            self.dropdown_aberto = False
        if "vscomp-option-text" in seletor and self.troca_pega:
            escolhida = next((o for o in self.opcoes if o.startswith(self.filtro)), None)
            if escolhida:
                self.pdm = escolhida

    def fill(self, seletor, texto):
        if "vscomp-search-input" in seletor:
            self.filtro = texto


class _PortalComPDM:
    texto_se_existir = PMIBPortal.texto_se_existir
    valor_se_existir = PMIBPortal.valor_se_existir

    def __init__(self, engine, aba_abre=True, confirma=True):
        self.engine = engine
        self.aba_abre = aba_abre
        self.confirma = confirma
        self.salvos = []
        self.ancoras = []

    def safe_click(self, seletor):
        self.engine.click(seletor)

    def safe_fill(self, seletor, texto):
        self.engine.fill(seletor, texto)

    def salvar_e_confirmar(self, nome="", callback_log=None, ancora=None, **_k):
        self.salvos.append(nome)
        self.ancoras.append(ancora)
        return self.confirma


PDM_CERTO = "PDM.9900.000 - FICHA PMIB, DUPLICADA, R0"
PDM_ERRADO = "PDM.4820.010 - REGULADOR, PRESSAO, R1"


def _tela(monkeypatch, pdm_atual, opcoes=(PDM_CERTO,), aba_abre=True,
          confirma=True, troca_pega=True, dropdown_trava=False):
    monkeypatch.setattr(pdm.extrator, "abrir_secao",
                        lambda *_a, **_k: aba_abre)
    engine = _EngineComPDM(pdm_atual, opcoes, troca_pega, dropdown_trava)
    return _PortalComPDM(engine, aba_abre, confirma), engine


# =============================================================================
# 1. O caso da 0922
# =============================================================================
def test_pdm_errado_e_TROCADO_e_salvo(monkeypatch):
    portal, engine = _tela(monkeypatch, PDM_ERRADO)

    resultado = pdm.garantir_pdm(portal, lambda _m: None)

    assert resultado.ok is True
    assert engine.pdm == PDM_CERTO
    assert portal.salvos == [sel.NOME_DA_ABA_INFO_GERAIS]


def test_o_salvamento_do_PDM_vai_ANCORADO(monkeypatch):
    """Informações Gerais tem o seu SALVAR; clicar "o primeiro da tela" foi o
    defeito que zerou duas fichas no mesmo dia."""
    portal, _ = _tela(monkeypatch, PDM_ERRADO)

    pdm.garantir_pdm(portal, lambda _m: None)

    assert portal.ancoras == [sel.XPATH_INFO_GERAIS_SECAO]


def test_pdm_ja_certo_NAO_salva(monkeypatch):
    """Salvar à toa custa uma recarga e um toast a mais na tela -- e o toast a
    mais é justamente o que confunde a confirmação da seção seguinte."""
    portal, _ = _tela(monkeypatch, PDM_CERTO)

    resultado = pdm.garantir_pdm(portal, lambda _m: None)

    assert resultado.ok is True
    assert portal.salvos == []


# =============================================================================
# 2. A revisão pode mudar
# =============================================================================
@pytest.mark.parametrize("texto", [
    "PDM.9900.000 - FICHA PMIB, DUPLICADA, R0",
    "PDM.9900.000 - FICHA PMIB, DUPLICADA, R1",
    "PDM.9900.000 - FICHA PMIB, DUPLICADA, R12",
])
def test_qualquer_revisao_do_PDM_da_duplicada_serve(texto):
    """*"A revisão R0 pode mudar."* Casar o texto inteiro faria o robô parar de
    achar o PDM no dia em que a revisão virasse R1 -- e o sintoma seria "não
    achei no combo", que ninguém liga a uma revisão nova."""
    assert pdm.e_o_pdm_da_duplicada(texto) is True


def test_outro_PDM_nao_passa():
    assert pdm.e_o_pdm_da_duplicada(PDM_ERRADO) is False
    assert pdm.e_o_pdm_da_duplicada("") is False


# =============================================================================
# 3. Quando não dá para garantir, NÃO seguir
# =============================================================================
def test_aba_que_nao_abre_reprova(monkeypatch):
    portal, _ = _tela(monkeypatch, PDM_ERRADO, aba_abre=False)

    assert pdm.garantir_pdm(portal, lambda _m: None).ok is False


def test_combo_ausente_reprova(monkeypatch):
    """Sem saber o PDM, purgar característica é chute -- e chute aqui apaga
    ficha."""
    portal, _ = _tela(monkeypatch, "")
    linhas = []

    resultado = pdm.garantir_pdm(portal, linhas.append)

    assert resultado.ok is False
    assert any("purgar é chute" in l for l in linhas)


def test_PDM_da_duplicada_ausente_do_combo_reprova(monkeypatch):
    portal, engine = _tela(monkeypatch, PDM_ERRADO, opcoes=())

    resultado = pdm.garantir_pdm(portal, lambda _m: None)

    assert resultado.ok is False
    assert engine.pdm == PDM_ERRADO, "não mexeu no que não sabia trocar"


def test_salvamento_nao_confirmado_reprova(monkeypatch):
    portal, _ = _tela(monkeypatch, PDM_ERRADO, confirma=False)
    linhas = []

    resultado = pdm.garantir_pdm(portal, linhas.append)

    assert resultado.ok is False
    assert any("do PDM antigo" in l for l in linhas)


def test_combo_que_nao_pega_a_troca_reprova(monkeypatch):
    """A releitura DEPOIS de salvar: um SALVAR confirmado não garante que o
    combo ficou com o valor escolhido."""
    portal, _ = _tela(monkeypatch, PDM_ERRADO, troca_pega=False)
    linhas = []

    resultado = pdm.garantir_pdm(portal, linhas.append)

    assert resultado.ok is False
    assert any("continua" in l for l in linhas)


# =============================================================================
# 4. A linha do CÓDIGO PMIB: espanhol, português e unidade adimensional
# =============================================================================
# *"A 3626 - CODIGO PMIB deve ser preenchida com a ficha original, tanto no
# campo de espanhol quanto no de português, e colocar a unidade adimensional."*
from sigft.services import duplicadas_injetor as injetor  # noqa: E402


@pytest.mark.parametrize("opcoes,esperada", [
    (["AD", "mm", "kg"], "AD"),
    (["Adimensional", "Milímetro"], "Adimensional"),
    (["(AD) Adimensional", "(mm) Milímetro"], "(AD) Adimensional"),
    (["ADIMENSIONAL", "KG"], "ADIMENSIONAL"),
    (["mm", "kg"], ""),
])
def test_a_opcao_adimensional_e_reconhecida_em_varias_redacoes(opcoes, esperada):
    """Não sabemos o texto exato que o `<select>` do portal mostra. Em vez de
    chutar um e falhar em silêncio, reconhecemos os casamentos plausíveis --
    e, quando nenhum serve, o injetor LISTA as opções no log, que é o que
    permite acertar na próxima rodada sem inspecionar a tela."""
    assert injetor._opcao_adimensional(opcoes) == esperada


class _EngineDeUnidade:
    def __init__(self, opcoes=(), tem_dropdown=True):
        self._opcoes = list(opcoes)
        self.tem_dropdown = tem_dropdown
        self.selecionado = None

    def contar(self, _seletor):
        return 1 if self.tem_dropdown else 0

    def opcoes(self, _seletor):
        return list(self._opcoes)

    def selecionar_por_texto(self, _seletor, texto):
        self.selecionado = texto


class _PortalDeUnidade:
    def __init__(self, engine):
        self.engine = engine


def test_unidade_adimensional_e_selecionada():
    engine = _EngineDeUnidade(opcoes=["mm", "AD", "kg"])

    ok = injetor.selecionar_unidade_adimensional(
        _PortalDeUnidade(engine), "//tr[1]", lambda _m: None)

    assert ok is True
    assert engine.selecionado == "AD"


def test_linha_sem_dropdown_de_unidade_nao_e_falha():
    """Característica de texto livre não tem unidade -- é normal, não erro."""
    engine = _EngineDeUnidade(tem_dropdown=False)

    assert injetor.selecionar_unidade_adimensional(
        _PortalDeUnidade(engine), "//tr[1]") is False


def test_dropdown_sem_adimensional_LISTA_as_opcoes_no_log():
    engine = _EngineDeUnidade(opcoes=["mm", "kg", "V"])
    linhas = []

    injetor.selecionar_unidade_adimensional(
        _PortalDeUnidade(engine), "//tr[1]", linhas.append)

    texto = "\n".join(linhas)
    assert "mm" in texto and "kg" in texto, (
        "listar o que EXISTE é o que permite acertar o texto certo depois"
    )


# ===========================================================================
# O COMBO QUE NÃO ABRIU — defeito de 2026-08-21, 16:17
# ===========================================================================
# No log do usuário:
#
#   [16:17:08] PDM atual: PDM.5999.007 - BLOCO, CONTATOS, R1 — trocando para
#              PDM.9900.000.
#   [16:17:30] [Erro] PDM.9900.000 não apareceu no combo depois de filtrar.
#              Nada foi selecionado.
#
# VINTE E DOIS SEGUNDOS entre as duas linhas, para uma função cujas pausas
# somam 1,2 s. Os 20 s que faltam são o timeout do motor sendo ENGOLIDO por
# `safe_fill` -- `engine.fill` não levanta por contrato. O dropdown nunca
# abriu, escrevemos o filtro no vazio, e a mensagem final culpou o CATÁLOGO
# ("não apareceu no combo") por um problema que era da tela.
#
# A diferença importa para quem lê: "o PDM não existe na lista" manda conferir
# o catálogo; "o combo não abriu" manda olhar a tela. Uma das duas faz perder
# a tarde.

class _EngineComComboQueNaoAbre(_EngineComPDM):
    """O toggle não responde: nenhuma caixa de busca aparece."""

    def element_exists(self, _seletor):
        return False


def test_diz_que_o_combo_nao_abriu_em_vez_de_culpar_o_catalogo():
    engine = _EngineComComboQueNaoAbre(
        pdm_atual="PDM.5999.007 - BLOCO, CONTATOS, R1",
        opcoes=("PDM.9900.000 - FICHA PMIB, DUPLICADA",))
    portal = _PortalComPDM(engine)
    logs = []

    assert pdm._escolher_pdm_da_duplicada(portal, logs.append) is False
    texto = "\n".join(logs)
    assert "não abriu" in texto
    assert "não apareceu no combo" not in texto


def test_nao_escreve_o_filtro_quando_o_combo_nao_abriu():
    """Escrever no vazio é o que custa os 20 s do timeout engolido."""
    engine = _EngineComComboQueNaoAbre(
        pdm_atual="PDM.5999.007 - BLOCO, CONTATOS, R1",
        opcoes=("PDM.9900.000 - FICHA PMIB, DUPLICADA",))
    portal = _PortalComPDM(engine)

    pdm._escolher_pdm_da_duplicada(portal)

    assert engine.filtro == ""


# ===========================================================================
# A lista que fica aberta cobre a página (2026-08-25)
# ===========================================================================

def test_dropdown_que_nao_fecha_REPROVA_em_vez_de_seguir(monkeypatch):
    """O defeito que trocou "o PDM não troca" por "nada mais salva".

    O `vscomp` pendura a lista em `<body>` e ela cobre a página inteira.
    Com ela aberta, o Playwright recusa clicar em qualquer coisa embaixo --
    e na rodada de 2026-08-25 isso derrubou CINCO salvamentos seguidos (o de
    Informações gerais e os quatro de Condições), cada um reclamando do
    próprio botão, nenhum do combo que ficara aberto seções atrás.

    Reprovar aqui é o que impede o robô de seguir cego e produzir uma ficha
    meio gravada com cinco mensagens que apontam para o lugar errado.
    """
    portal, engine = _tela(monkeypatch, PDM_ERRADO, dropdown_trava=True)

    mensagens = []
    resultado = pdm.garantir_pdm(portal, mensagens.append)

    assert resultado.ok is False
    assert any("não fechou" in m for m in mensagens), mensagens
    # E não pode ter tentado salvar com a lista por cima.
    assert portal.salvos == [], portal.salvos


def test_o_dropdown_e_fechado_com_ESC_antes_de_salvar(monkeypatch):
    portal, engine = _tela(monkeypatch, PDM_ERRADO)

    resultado = pdm.garantir_pdm(portal)

    assert resultado.ok is True
    assert engine.dropdown_aberto is False


def test_o_dialogo_trocar_pdm_e_CONFIRMADO(monkeypatch):
    """O modal que cobria a página e derrubava cinco salvamentos.

    Trocar o PDM abre "Trocar PDM / Todos os dados de Características Técnicas
    serão removidos". Enquanto ele está aberto nenhum clique passa -- e o log
    só dizia qual BOTÃO falhou, nunca que havia um modal. Três rodadas foram
    gastas numa hipótese errada (o dropdown do combo) até o usuário mandar um
    print da tela.
    """
    portal, engine = _tela(monkeypatch, PDM_ERRADO)
    engine.dialogos = 1

    def contar(seletor, _orig=engine.contar):
        if "CONFIRMAR" in seletor:
            return engine.dialogos
        return _orig(seletor)

    def click_estrito(seletor):
        if "CONFIRMAR" in seletor:
            engine.dialogos = 0
            return
        engine.click(seletor)

    engine.contar = contar
    engine.click_estrito = click_estrito

    resultado = pdm.garantir_pdm(portal)

    assert resultado.ok is True
    assert engine.dialogos == 0, "o diálogo tinha de ter sido confirmado"
