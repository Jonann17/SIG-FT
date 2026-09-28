r"""
Aplicação LMR: SALVAR -> CONFIRMAR -> só segue com a mensagem do portal
(`sigft/services/lmr.py`, 2026-09-28).

Relato do usuário: *"o SIG-FT está com dificuldade no módulo de aplicação LMR,
ele não está conseguindo subir as informações. Quando ele finalizar de colocar
as tags, ele deve clicar no botão de salvar [...] Depois vai abrir uma telinha
pra clicar em CONFIRMAR, e quando clicar em confirmar, ele só deve ir fazer o
próximo código LMR daquela ficha se apareceu essa mensagem"*:

    <button data-button="" class="btn btn-primary" type="submit">SALVAR</button>
    <button data-button="" class="btn btn-primary" type="button">CONFIRMAR</button>
    <div class="feedback-message-text">As informações da aplicação LMR foram
        adicionadas com sucesso!</div>

O que havia antes: os dois botões eram endereçados por POSIÇÃO dentro de ids
gerados pelo OutSystems (`//*[@id="b10-b19-Form"]/div[2]/button[1]`), e o log
dizia "inserido ✔️" no instante do clique -- sem prova nenhuma de que o portal
tinha gravado.

⚠️ `scripts/check.sh` verde NÃO é prova de portal: estes testes rodam contra um
dublê escrito a partir do HTML do relato. A validação é a execução real.
"""
from __future__ import annotations

import re

import pytest

import sigft.services.lmr as lmr_mod
from sigft import config
from sigft.core.callbacks import UICallbacks
from sigft.core.rpa.portal import PMIBPortal
from sigft.services.lmr import LMRAutomation

MENSAGEM_LMR = "As informações da aplicação LMR foram adicionadas com sucesso!"


@pytest.fixture(autouse=True)
def _sem_esperar(monkeypatch):
    # `time` é o mesmo módulo em `lmr` e em `portal`: anular aqui anula lá.
    monkeypatch.setattr(lmr_mod.time, "sleep", lambda *_a, **_kw: None)
    # A espera pela mensagem é por RELÓGIO (a de `PMIBPortal`); com o `sleep`
    # anulado, zero = olhar uma vez. No dublê a mensagem aparece no clique.
    monkeypatch.setattr(lmr_mod, "TIMEOUT_CONFIRMACAO_LMR_S", 0.0)


# ===========================================================================
# Dublê da aba "Aplicação - LMR"
# ===========================================================================
class _TelaDaLMR:
    """A aba na medida do fluxo pedido.

    - o SALVAR do formulário abre o diálogo de confirmação;
    - o CONFIRMAR fecha o diálogo e mostra a mensagem de sucesso;
    - a mensagem SAI da tela sozinha depois de `leituras_ate_sumir` leituras,
      como o `feedback-message-autoclose` do portal (`None` = nunca sai).

    Cada chave desliga uma etapa, para os casos de falha. `acoes` é a linha do
    tempo -- o que o robô digitou, clicou, leu e perguntou, na ordem. É por ela
    que os testes provam QUANDO o próximo código começa.
    """

    def __init__(self, *, dialogo_abre=True, confirma=True, dialogo_fecha=True,
                 mensagem=MENSAGEM_LMR, leituras_ate_sumir=1, aviso_no_salvar=None,
                 com_role_dialog=True):
        self.dialogo_abre = dialogo_abre
        self.confirma = confirma
        self.dialogo_fecha = dialogo_fecha
        self.mensagem = mensagem
        self.leituras_ate_sumir = leituras_ate_sumir
        self.aviso_no_salvar = aviso_no_salvar
        self.com_role_dialog = com_role_dialog

        self.dialogo_aberto = False
        self.toasts = []            # [[texto, leituras que ainda faltam | None]]
        self.avisos = []
        self.acoes = []
        self.toasts_ao_salvar = []  # quantas mensagens de sucesso havia a cada SALVAR

    # --- o tempo passa quando alguém olha --------------------------------
    def _passar_o_tempo(self):
        self.toasts = [t for t in self.toasts if t[1] is None or t[1] > 0]
        for toast in self.toasts:
            if toast[1] is not None:
                toast[1] -= 1

    # --- o diálogo ---------------------------------------------------------
    def _confirmar_na_tela(self, seletor):
        if not self.dialogo_aberto:
            return False
        if "@role='dialog'" in seletor:
            return self.com_role_dialog
        return True

    # --- primitivas de motor usadas pelo serviço e pelo `PMIBPortal` ---------
    def contar(self, seletor):
        if "CONFIRMAR" in seletor:
            return 1 if self._confirmar_na_tela(seletor) else 0
        if "feedback-message-warning" in seletor:
            return len(self.avisos)
        if "feedback-message-success" in seletor:
            self._passar_o_tempo()
            return len(self.toasts)
        if "feedback-message-text" in seletor:
            return len(self.toasts) + len(self.avisos)
        return 1

    def esta_visivel(self, seletor):
        if "CONFIRMAR" in seletor:
            return self._confirmar_na_tela(seletor)
        return True

    def texto(self, seletor):
        achado = re.search(r"\)\[(\d+)\]$", seletor)
        indice = int(achado.group(1)) if achado else 1
        if "feedback-message-warning" in seletor:
            lista = list(self.avisos)
        elif "feedback-message-success" in seletor:
            lista = [t[0] for t in self.toasts]
        else:
            lista = [t[0] for t in self.toasts] + list(self.avisos)
        texto = lista[indice - 1] if indice <= len(lista) else ""
        if "feedback-message-success" in seletor and texto:
            self.acoes.append(("leu", texto))
        return texto

    def click_raw(self, seletor):
        if "SALVAR" in seletor:
            self.acoes.append(("clicou", "SALVAR"))
            self.toasts_ao_salvar.append(len(self.toasts))
            if self.aviso_no_salvar:
                self.avisos.append(self.aviso_no_salvar)
            elif self.dialogo_abre:
                self.dialogo_aberto = True
            return
        if "CONFIRMAR" in seletor:
            if not self._confirmar_na_tela(seletor):
                raise LookupError("não há CONFIRMAR na tela")
            self.acoes.append(("clicou", "CONFIRMAR"))
            if self.dialogo_fecha:
                self.dialogo_aberto = False
            if self.confirma:
                self.toasts.append([self.mensagem, self.leituras_ate_sumir])
            return
        self.acoes.append(("clicou", seletor))

    def clear(self, seletor):
        self.acoes.append(("limpou", seletor))

    def type_text(self, seletor, texto):
        self.acoes.append(("digitou", seletor, texto))

    def press(self, tecla):
        self.acoes.append(("tecla", tecla))

    def scroll_to(self, _seletor):
        pass


# ===========================================================================
# DataFrame falso (o mesmo de tests/test_lmr_no_playwright.py)
# ===========================================================================
class _Linha(dict):
    pass


class _Loc:
    def __init__(self, linhas):
        self._linhas = linhas

    def __getitem__(self, chave):
        if isinstance(chave, tuple):
            indice, coluna = chave
            return self._linhas[indice][coluna]
        return _Linha(self._linhas[chave])


class _ILoc:
    def __init__(self, linhas):
        self._linhas = linhas

    def __getitem__(self, indice):
        return _Linha(self._linhas[indice])


class _FakeDF:
    def __init__(self, linhas):
        self._linhas = linhas
        self.empty = not linhas
        self.shape = (len(linhas), 3)
        self.loc = _Loc(linhas)
        self.iloc = _ILoc(linhas)

    def __len__(self):
        return len(self._linhas)


def _df(*pares):
    return _FakeDF([
        {"PMIB": "4500063671.0001", "Código_PMIB": codigo, "TAG_PMIB": tag}
        for codigo, tag in pares
    ])


def _rodar(tela, df):
    auto = LMRAutomation.__new__(LMRAutomation)
    auto.engine = tela
    auto.portal = PMIBPortal(tela)
    auto.url_inicial = config.PORTAL_URL
    logs, perguntas = [], []

    def _perguntar(pergunta, titulo=None):
        perguntas.append(pergunta)
        tela.acoes.append(("perguntou", pergunta))
        return False

    callbacks = UICallbacks(
        log=lambda msg, nivel="info", contexto=None: logs.append(str(msg)),
        ask=_perguntar,
    )
    erros = auto._processar_ficha_lmr_interna(df, callbacks)
    return erros, "\n".join(logs), perguntas


def _cliques(tela):
    return [a[1] for a in tela.acoes if a[0] == "clicou"]


# ===========================================================================
# 1. Só é "inserido" com a mensagem do portal
# ===========================================================================
def test_o_codigo_so_e_inserido_com_a_mensagem_de_sucesso_da_lmr():
    tela = _TelaDaLMR()

    erros, logs, perguntas = _rodar(tela, _df(("COD-1", "TAG-A")))

    assert erros == []
    assert perguntas == []
    assert "inserido ✔️" in logs
    assert _cliques(tela) == ["SALVAR", "CONFIRMAR"]


def test_sem_a_mensagem_o_codigo_NAO_conta_como_inserido():
    """Era o defeito: o log dizia "inserido ✔️" no instante do clique."""
    tela = _TelaDaLMR(confirma=False)

    erros, logs, _ = _rodar(tela, _df(("COD-1", "TAG-A")))

    assert [e["codigo_pmib"] for e in erros] == ["COD-1"]
    assert "inserido ✔️" not in logs
    assert "mensagem de sucesso" in erros[0]["erro"]


def test_so_vai_para_o_proximo_codigo_DEPOIS_de_ler_a_mensagem():
    tela = _TelaDaLMR()

    erros, _, _ = _rodar(tela, _df(("COD-1", "TAG-A"), ("COD-2", "TAG-B")))

    assert erros == []
    leu = tela.acoes.index(("leu", MENSAGEM_LMR))
    comecou_o_2 = tela.acoes.index(("digitou", lmr_mod.XPATH_CAMPO_CODIGO, "COD-2"))
    assert leu < comecou_o_2


def test_sem_a_mensagem_a_pessoa_e_chamada_ANTES_do_proximo_codigo():
    """*"Ele só deve ir fazer o próximo código LMR daquela ficha se apareceu
    essa mensagem."* Sem ela o robô para e pergunta, e o próximo código só
    começa depois da resposta."""
    tela = _TelaDaLMR(confirma=False)

    _rodar(tela, _df(("COD-1", "TAG-A"), ("COD-2", "TAG-B")))

    perguntou = next(i for i, a in enumerate(tela.acoes) if a[0] == "perguntou")
    comecou_o_2 = tela.acoes.index(("digitou", lmr_mod.XPATH_CAMPO_CODIGO, "COD-2"))
    assert perguntou < comecou_o_2
    assert "NÃO confirmou" in tela.acoes[perguntou][1]
    assert "COD-1" in tela.acoes[perguntou][1]


# ===========================================================================
# 2. A MESMA frase a cada código
# ===========================================================================
def test_a_mensagem_do_codigo_anterior_precisa_SUMIR_antes_do_proximo_salvar():
    """A frase é idêntica a cada código. Com a do COD-1 ainda na tela, a do
    COD-2 seria dada por velha -- a "foto de antes" já a tinha. O robô espera
    ela sair (é `autoclose`) antes do SALVAR, e aí a do COD-2 conta."""
    tela = _TelaDaLMR(leituras_ate_sumir=3)

    erros, logs, _ = _rodar(tela, _df(("COD-1", "TAG-A"), ("COD-2", "TAG-B")))

    assert erros == []
    assert logs.count("inserido ✔️") == 2
    assert tela.toasts_ao_salvar == [0, 0]


def test_mensagem_que_nao_sai_da_tela_nao_vira_confirmacao_falsa():
    """Se a do código anterior não sair, a do atual é indistinguível. O lado
    seguro é NÃO confirmar: pendência a conferir, nunca "inserido" sem prova."""
    tela = _TelaDaLMR(leituras_ate_sumir=None)     # nunca sai

    erros, logs, _ = _rodar(tela, _df(("COD-1", "TAG-A"), ("COD-2", "TAG-B")))

    assert [e["codigo_pmib"] for e in erros] == ["COD-2"]
    assert "não saiu da tela" in logs


# ===========================================================================
# 3. Quando o SALVAR não chega ao diálogo, ou o CONFIRMAR não chega à mensagem
# ===========================================================================
def test_salvar_que_nao_abre_o_dialogo_falha_com_motivo_e_sem_clicar_confirmar():
    tela = _TelaDaLMR(dialogo_abre=False)

    erros, _, _ = _rodar(tela, _df(("COD-1", "TAG-A")))

    assert "diálogo" in erros[0]["erro"]
    assert _cliques(tela) == ["SALVAR"]


def test_o_aviso_do_portal_no_lugar_do_dialogo_vai_para_o_motivo():
    tela = _TelaDaLMR(aviso_no_salvar="Por favor, verifique os campos")

    erros, _, _ = _rodar(tela, _df(("COD-1", "TAG-A")))

    assert "Por favor, verifique os campos" in erros[0]["erro"]


def test_aviso_VELHO_na_tela_nao_e_confundido_com_recusa_deste_codigo():
    """O aviso não tem `autoclose`: um que sobrou de antes continua lá, e não
    pode passar por recusa do código atual."""
    tela = _TelaDaLMR()
    tela.avisos.append("Por favor, verifique os campos")

    erros, _, _ = _rodar(tela, _df(("COD-1", "TAG-A")))

    assert erros == []


def test_mensagem_de_sucesso_de_OUTRA_secao_nao_confirma_a_lmr():
    """"A Ficha Técnica X foi modificada com sucesso." é de Informações gerais
    -- foi ela que confirmou salvamentos errados em 2026-08-20. Para a LMR, a
    mensagem tem de falar em LMR."""
    tela = _TelaDaLMR(mensagem="A Ficha Técnica 4500063671.0001 foi modificada com sucesso.")

    erros, _, _ = _rodar(tela, _df(("COD-1", "TAG-A")))

    assert [e["codigo_pmib"] for e in erros] == ["COD-1"]


def test_dialogo_que_continua_aberto_entra_no_motivo():
    """Modal aberto trava a página inteira (§3 de
    docs/PORTAL_COMO_ELE_SE_COMPORTA.md): quem for conferir precisa saber que
    é ele que está no caminho."""
    tela = _TelaDaLMR(confirma=False, dialogo_fecha=False)

    erros, _, _ = _rodar(tela, _df(("COD-1", "TAG-A")))

    assert "continua aberto" in erros[0]["erro"]


def test_dialogo_sem_role_dialog_usa_o_confirmar_de_reserva():
    """Não sabemos se o diálogo da LMR se declara `role="dialog"`. A reserva é
    o seletor com que `apagar_lmr` já confirma a exclusão nesta mesma aba."""
    tela = _TelaDaLMR(com_role_dialog=False)

    erros, _, _ = _rodar(tela, _df(("COD-1", "TAG-A")))

    assert erros == []
    assert _cliques(tela) == ["SALVAR", "CONFIRMAR"]


# ===========================================================================
# 4. `PMIBPortal.esperar_confirmacao_anterior_sumir`
# ===========================================================================
def test_sem_mensagem_na_tela_nao_espera_nada():
    dormidas = []

    assert PMIBPortal(_TelaDaLMR()).esperar_confirmacao_anterior_sumir(
        lmr_mod.SECAO_LMR, sleep_fn=dormidas.append) is True
    assert dormidas == []


def test_espera_a_mensagem_sair_e_devolve_True():
    tela = _TelaDaLMR()
    tela.toasts.append([MENSAGEM_LMR, 2])
    dormidas = []

    assert PMIBPortal(tela).esperar_confirmacao_anterior_sumir(
        lmr_mod.SECAO_LMR, sleep_fn=dormidas.append) is True
    assert 1 <= len(dormidas) <= 3


def test_conta_TENTATIVAS_e_desiste_sem_girar_para_sempre():
    """§0, regra 7: contar tentativas, não segundos -- com o `sleep` anulado,
    um laço por relógio giraria em vazio."""
    tela = _TelaDaLMR()
    tela.toasts.append([MENSAGEM_LMR, None])     # nunca sai
    dormidas = []

    assert PMIBPortal(tela).esperar_confirmacao_anterior_sumir(
        lmr_mod.SECAO_LMR, tentativas=5, sleep_fn=dormidas.append) is False
    assert len(dormidas) == 5


def test_mensagem_de_outra_secao_nao_segura_a_espera():
    tela = _TelaDaLMR()
    tela.toasts.append(["A característica técnica foi salva com sucesso!", None])
    dormidas = []

    assert PMIBPortal(tela).esperar_confirmacao_anterior_sumir(
        lmr_mod.SECAO_LMR, sleep_fn=dormidas.append) is True
    assert dormidas == []


# ===========================================================================
# 5. Os seletores, contra o HTML que o usuário mandou
# ===========================================================================
# ⚠️ Os BOTÕES e a MENSAGEM são o HTML do relato, verbatim. O que está em volta
# -- o `<form>`, os ids, a seção de Informações gerais antes, o diálogo -- é
# MONTAGEM para o teste, tirada dos seletores antigos do módulo
# (`b10-b19-Form`, `b10-b19-b22-b1-Footer`) e da §3 do documento do portal. É
# exatamente o que só a execução real confirma.
_HTML_DA_FICHA = """
<html><body>
<div id="b8-GeneralInformation"><form data-form="" id="b8-Form">
  <input id="b8-Input_Description"/>
  <div><button data-button="" class="btn btn-primary" type="submit">SALVAR</button></div>
</form></div>
<div id="b10-ApplicationMRL_Content"><form data-form="" id="b10-b19-Form">
  <div>
    <input id="b10-b19-Input_EquipmentCode"/>
    <input id="b10-b19-Input_QuantityInstalled"/>
    <input id="b10-b19-Input_Tag"/>
  </div>
  <div><button data-button="" class="btn btn-primary" type="submit">SALVAR</button></div>
</form></div>
<div class="popup-dialog" role="dialog"><div id="b10-b19-b22-b1-Footer"><div>
  <button data-button="" class="btn btn-primary" type="button">CONFIRMAR</button>
  <button data-button="" class="btn" type="button">CANCELAR</button>
</div></div></div>
<div class="feedback-message feedback-message-success feedback-message-autoclose" role="alert"><i></i>
  <div class="feedback-message-text">As informações da aplicação LMR foram adicionadas com sucesso!</div>
</div>
</body></html>
"""


def _doc(html):
    etree = pytest.importorskip("lxml.etree", reason="lxml é opcional")
    return etree.fromstring(html, etree.HTMLParser(encoding="utf-8"))


def test_o_salvar_e_o_do_formulario_da_lmr_e_nao_o_primeiro_da_tela():
    """A ficha tem um SALVAR por seção, e o primeiro do documento é o de
    Informações gerais -- o defeito de 2026-08-20."""
    achados = _doc(_HTML_DA_FICHA).xpath(lmr_mod.XPATH_BOTAO_SALVAR)

    assert len(achados) == 1
    assert achados[0].xpath("ancestor::form[1]/@id") == ["b10-b19-Form"]


def test_os_dois_seletores_de_confirmar_casam_so_o_botao_do_relato():
    doc = _doc(_HTML_DA_FICHA)

    for xpath in (lmr_mod.XPATH_BOTAO_CONFIRMAR, lmr_mod.XPATH_BOTAO_CONFIRMAR_RESERVA):
        assert ["".join(b.itertext()).strip() for b in doc.xpath(xpath)] == ["CONFIRMAR"]


def test_a_mensagem_do_relato_e_lida_como_sucesso_E_como_da_lmr():
    from sigft.core.rpa.portal import XPATH_MENSAGEM_DE_SUCESSO, mensagem_confirma_secao

    textos = ["".join(x.itertext()).strip()
              for x in _doc(_HTML_DA_FICHA).xpath(XPATH_MENSAGEM_DE_SUCESSO)]

    assert textos == [MENSAGEM_LMR]
    assert mensagem_confirma_secao(MENSAGEM_LMR, lmr_mod.SECAO_LMR)


@pytest.mark.parametrize("de_outra_secao", [
    "A Ficha Técnica 4500063671.0922 foi modificada com sucesso.",
    "A característica técnica foi salva com sucesso!",
    "As condições de armazenamento foram modificadas com sucesso!",
])
def test_mensagem_de_outra_secao_nao_confirma_a_lmr(de_outra_secao):
    from sigft.core.rpa.portal import mensagem_confirma_secao

    assert not mensagem_confirma_secao(de_outra_secao, lmr_mod.SECAO_LMR)


def test_os_botoes_nao_dependem_mais_de_posicao_dentro_de_id_gerado():
    """`b19`, `b22` e `b1` são numeração de bloco do OutSystems, e
    `div[2]/button[1]` é "o primeiro botão da segunda div": um botão novo antes
    do SALVAR e o clique ia para outro lugar."""
    assert "div[2]/button[1]" not in lmr_mod.XPATH_BOTAO_SALVAR
    assert "b22" not in lmr_mod.XPATH_BOTAO_CONFIRMAR
    assert "@type='submit'" in lmr_mod.XPATH_BOTAO_SALVAR
