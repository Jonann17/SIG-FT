r"""
O ESPANHOL das Condições sai do balão do tooltip (2026-08-24).

Como este arquivo nasceu, porque a história é o próprio teste: no dump da ficha
4500063671.1277 eu procurei espanhol por dois padrões -- um id `..._ES` e um
segundo `Block_Expression` -- não achei nenhum dos dois, e concluí que a
visualização não trazia espanhol. **Concluí mais do que a evidência
sustentava.** O usuário corrigiu na hora: *"a página tem espanhol sim, só que
ele só aparece quando passamos o mouse por cima da versão em português, como um
balão"*, e mandou o HTML:

    <div class="osui-tooltip__content" id="b12-b20-b4-b3-b2-Content"
         role="button" aria-describedby="b12-b20-b4-b3-b2-Tooltip" tabindex="0">
      <div data-block="PMIB_DataSheetView.Block_Expression" ...>
        <span data-expression="">Aplicam-se as normas ...</span>

O gatilho carrega o PORTUGUÊS e aponta, por `aria-describedby`, para o balão
com o espanhol. E o balão não está no DOM até alguém apontar para ele
(`osui-tooltip--is-hover`) -- é por isso que ele não aparecia na foto da seção:
a foto é do HTML como está, e naquele instante o elemento não existia.

A consequência prática é grande: a seção de Condições fecha COMPLETA sem abrir
a ficha original em edição, que é a regra que o usuário fixou em 2026-08-20.
"""
import pytest

from sigft.core.rpa import seletores_duplicada as sel
from sigft.core.rpa.portal import PMIBPortal
from sigft.services import duplicadas_condicoes as cond


# ===========================================================================
# 1. `PMIBPortal.texto_do_balao` — a mecânica
# ===========================================================================

class _EngineDeTooltip:
    """Tela com um gatilho e um balão que só nasce quando alguém aponta.

    `nasce_no_hover=False` simula o portal que já montou o balão -- o caminho
    barato, em que ninguém deve pagar hover nenhum.
    """

    def __init__(self, describedby="b12-Tooltip", espanhol="Se aplican las normas",
                 nasce_no_hover=True, hover_estoura=False):
        self.describedby = describedby
        self.espanhol = espanhol
        self.montado = not nasce_no_hover
        self.hover_estoura = hover_estoura
        self.hovers = []
        self.focos = []

    def atributo(self, _seletor, nome):
        return self.describedby if nome == "aria-describedby" else ""

    def contar(self, seletor):
        if "b12-Tooltip" in seletor:
            return 1 if self.montado else 0
        return 1

    def texto(self, seletor):
        if "b12-Tooltip" in seletor:
            return self.espanhol if self.montado else ""
        return ""

    def passar_o_mouse(self, seletor):
        if self.hover_estoura:
            raise RuntimeError("motor sem ponteiro")
        self.hovers.append(seletor)
        self.montado = True

    def focar(self, seletor):
        self.focos.append(seletor)
        self.montado = True


class _PortalDeTooltip:
    # A implementação REAL, emprestada: testar uma cópia deixaria o conserto
    # envelhecer sozinho aqui dentro.
    texto_se_existir = PMIBPortal.texto_se_existir
    texto_do_balao = PMIBPortal.texto_do_balao
    XPATH_POR_ID = PMIBPortal.XPATH_POR_ID
    PAUSA_DO_BALAO = PMIBPortal.PAUSA_DO_BALAO

    def __init__(self, engine):
        self.engine = engine


def _portal(**kwargs):
    engine = _EngineDeTooltip(**kwargs)
    return _PortalDeTooltip(engine), engine


def _sem_dormir(_s):
    return None


def test_le_o_balao_apontando_o_mouse_no_gatilho():
    portal, engine = _portal()
    assert portal.texto_do_balao("//gatilho", sleep_fn=_sem_dormir) == \
        "Se aplican las normas"
    assert engine.hovers == ["//gatilho"]


def test_balao_ja_montado_nao_paga_hover():
    """O hover custa meio segundo por campo. Quando o balão já está no DOM, a
    leitura direta resolve -- e são dois campos por sub-aba, quatro sub-abas,
    em toda ficha do lote."""
    portal, engine = _portal(nasce_no_hover=False)
    assert portal.texto_do_balao("//gatilho", sleep_fn=_sem_dormir) == \
        "Se aplican las normas"
    assert engine.hovers == []


def test_sem_aria_describedby_devolve_vazio_sem_tocar_na_tela():
    """Nem todo texto tem par de idioma. Sem o `aria-describedby` não há balão,
    e insistir seria pagar hover num campo que não tem o que mostrar."""
    portal, engine = _portal(describedby="")
    assert portal.texto_do_balao("//gatilho", sleep_fn=_sem_dormir) == ""
    assert engine.hovers == []


def test_motor_sem_ponteiro_cai_no_foco():
    """O gatilho é `role="button" tabindex="0"`: responde ao teclado também.
    É a porta que sobra num motor que não move ponteiro."""
    portal, engine = _portal(hover_estoura=True)
    assert portal.texto_do_balao("//gatilho", sleep_fn=_sem_dormir) == \
        "Se aplican las normas"
    assert engine.focos == ["//gatilho"]


def test_balao_que_nunca_nasce_devolve_vazio_em_vez_de_estourar():
    class _Mudo(_EngineDeTooltip):
        def passar_o_mouse(self, seletor):
            self.hovers.append(seletor)   # aponta e nada acontece

        def focar(self, seletor):
            self.focos.append(seletor)

    portal = _PortalDeTooltip(_Mudo())
    assert portal.texto_do_balao("//gatilho", sleep_fn=_sem_dormir) == ""


def test_atributo_que_estoura_nao_derruba_a_ficha():
    class _Explode:
        def atributo(self, _s, _n):
            raise RuntimeError("elemento sumiu")

    portal = _PortalDeTooltip(_Explode())
    assert portal.texto_do_balao("//gatilho", sleep_fn=_sem_dormir) == ""


# ===========================================================================
# 2. `espanhol_dos_baloes` — a leitura ligada às Condições
# ===========================================================================

class _PortalDeSecao:
    """Responde por RÓTULO: `{rótulo: (português no gatilho, espanhol)}`."""

    def __init__(self, baloes):
        self.baloes = dict(baloes)
        self.hovers = []

    @staticmethod
    def _rotulo(seletor):
        import re
        achado = re.search(r"normalize-space\(\)='([^']*)'", seletor)
        return achado.group(1) if achado else None

    def texto_se_existir(self, seletor):
        par = self.baloes.get(self._rotulo(seletor))
        return par[0] if par else ""

    def texto_do_balao(self, seletor, sleep_fn=None):
        rotulo = self._rotulo(seletor)
        self.hovers.append(rotulo)
        par = self.baloes.get(rotulo)
        return par[1] if par else ""


@pytest.fixture
def mapa(monkeypatch):
    monkeypatch.setattr(sel, "CONDICOES_ROTULO_PARA_CAMPO", {
        "embalagem para transporte": ("Transporte", "TextArea_TransportPackagingPT"),
        "peso liquido": ("Armazenamento", "Input_LiquidWeight"),
    })


def test_espanhol_do_balao_vira_o_campo_ES(mapa):
    portal = _PortalDeSecao({
        "Embalagem para transporte": ("Caixa de papelão", "Caja de cartón")})

    achado = cond.espanhol_dos_baloes(
        portal, [("Embalagem para transporte", "Caixa de papelão")])

    assert achado == {"Transporte": {"TextArea_TransportPackagingES": "Caja de cartón"}}


def test_campo_que_nao_e_texto_longo_nao_paga_hover(mapa):
    """Número e radio não têm par de idioma. Apontar para cada um deles
    cobraria meio segundo por campo sem nada em troca."""
    portal = _PortalDeSecao({})

    cond.espanhol_dos_baloes(portal, [("Peso líquido", "12,5")])

    assert portal.hovers == []


def test_gatilho_de_OUTRO_campo_e_recusado_e_logado(mapa):
    """⚠️ O RISCO DO `following::[1]`. Um campo sem tooltip faz o "primeiro
    balão depois do rótulo" cair no campo SEGUINTE -- e a ficha alvo receberia
    o espanhol de outro texto sem nada no log. Espanhol faltando é pendência;
    espanhol trocado é erro que ninguém vê."""
    portal = _PortalDeSecao({
        # o gatilho mostra o texto de OUTRO campo
        "Embalagem para transporte": ("Manter na horizontal", "Mantener horizontal")})
    linhas = []

    achado = cond.espanhol_dos_baloes(
        portal, [("Embalagem para transporte", "Caixa de papelão")],
        callback_log=linhas.append)

    assert achado == {}
    assert any("Embalagem para transporte" in l for l in linhas)


def test_gatilho_confere_ignorando_acento_e_caixa(mapa):
    """O portal reescreve espaço e caixa entre a varredura e o gatilho; exigir
    igualdade crua reprovaria campo bom."""
    portal = _PortalDeSecao({
        "Embalagem para transporte": ("  CAIXA  DE PAPELAO ", "Caja de cartón")})

    achado = cond.espanhol_dos_baloes(
        portal, [("Embalagem para transporte", "Caixa de papelão")])

    assert achado["Transporte"]["TextArea_TransportPackagingES"] == "Caja de cartón"


def test_sem_balao_nenhum_devolve_vazio_e_nao_loga_erro(mapa):
    """Ficha só com números é o caso comum, e não pode encher o log de aviso."""
    portal = _PortalDeSecao({})
    linhas = []

    achado = cond.espanhol_dos_baloes(
        portal, [("Embalagem para transporte", "Caixa de papelão")],
        callback_log=linhas.append)

    assert achado == {}
    assert linhas == []


def test_rotulo_fora_do_mapa_e_ignorado(mapa):
    portal = _PortalDeSecao({"Cor da etiqueta": ("azul", "azul")})
    assert cond.espanhol_dos_baloes(portal, [("Cor da etiqueta", "azul")]) == {}


# ===========================================================================
# 3. `fundir` — as duas leituras num dicionário só
# ===========================================================================

def test_fundir_junta_as_duas_leituras():
    assert cond.fundir(
        {"Transporte": {"TextArea_TransportPackagingPT": "Caixa"}},
        {"Transporte": {"TextArea_TransportPackagingES": "Caja"}},
    ) == {"Transporte": {"TextArea_TransportPackagingPT": "Caixa",
                         "TextArea_TransportPackagingES": "Caja"}}


def test_fundir_aceita_subaba_que_so_existe_num_dos_lados():
    assert cond.fundir({"Armazenamento": {"Input_LiquidWeight": "1"}},
                       {"Descarte": {"TextArea_DiscardTypeES": "Chatarra"}}) == {
        "Armazenamento": {"Input_LiquidWeight": "1"},
        "Descarte": {"TextArea_DiscardTypeES": "Chatarra"}}


def test_fundir_NAO_sobrescreve_o_que_ja_estava_lido():
    """Os dois conjuntos de sufixo são disjuntos hoje (`...PT` × `...ES`). Se
    um dia deixarem de ser, o que já estava lido ganha: o duplicado aparece
    como campo faltando, que é visível, em vez de sobrescrita silenciosa."""
    assert cond.fundir({"Transporte": {"X": "original"}},
                       {"Transporte": {"X": "do balão"}}) == \
        {"Transporte": {"X": "original"}}


def test_fundir_com_lados_vazios_nao_estoura():
    assert cond.fundir({}, {}) == {}
    assert cond.fundir(None, None) == {}


def test_fundir_nao_muda_o_dicionario_de_entrada():
    entrada = {"Transporte": {"A": "1"}}
    cond.fundir(entrada, {"Transporte": {"B": "2"}})
    assert entrada == {"Transporte": {"A": "1"}}
