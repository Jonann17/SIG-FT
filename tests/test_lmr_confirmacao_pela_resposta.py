r"""
Aplicação LMR mais rápida (2026-10-14): a gravação confirmada pela RESPOSTA do
servidor, e cada TAG pela saída dela do campo -- `sigft/services/lmr.py`.

Pedido do Luan: "faça a melhoria do RPA para aplicação LMR, que você disse que
ficaria mais rápido" (docs/PMIB_ENGENHARIA_REVERSA.md, R1 e R8).

O que custava tempo, medido no código:
  - antes de salvar cada código, o robô esperava até 15 s a mensagem de
    sucesso do código ANTERIOR sair da tela, porque a do atual tem o mesmo
    texto (`esperar_confirmacao_anterior_sumir`). A resposta da ação de salvar
    (`ActionApplicationMRL_CreateOrUpdate`) é única por gravação e traz o Id da
    aplicação, ou a recusa do servidor: com ela, a espera some;
  - cada TAG custava TAB + 0,5 s + ENTER + 0,5 s. Adicionar tag não fala com o
    servidor: o portal põe a tag numa lista local e ESVAZIA o campo. A segunda
    pausa vira "esperar o campo esvaziar" -- que de quebra prova que a tag
    entrou.

Sem resposta (endereço que mudou numa versão nova do portal), a mensagem na
tela decide aquele código e o resto do lote volta ao modo de antes.

Só RPA (regra do Luan, 2026-10-14): o robô clica como uma pessoa; a resposta é
a que o navegador recebeu. ⚠️ `scripts/check.sh` verde não é prova de portal.
"""
from __future__ import annotations

import re

import pytest

import sigft.services.lmr as lmr_mod
from sigft import config
from sigft.core.callbacks import UICallbacks
from sigft.core.rpa import respostas
from sigft.core.rpa.portal import PMIBPortal
from sigft.services.lmr import XPATH_CAMPO_TAG, LMRAutomation

MENSAGEM_LMR = "As informações da aplicação LMR foram adicionadas com sucesso!"
GRAVOU = {"versionInfo": {}, "data": {"ApplicationMRLId": "5501"}}


@pytest.fixture
def pausas(monkeypatch):
    feitas = []
    monkeypatch.setattr(lmr_mod.time, "sleep", lambda s=0, *_a, **_kw: feitas.append(s))
    monkeypatch.setattr(lmr_mod, "TIMEOUT_CONFIRMACAO_LMR_S", 0.0)
    return feitas


class _TelaComResposta:
    """A aba "Aplicação - LMR" com o que o motor novo lê.

    - `resposta`: o JSON que a ação de salvar devolve (`None` = não chegou);
    - `toast_antigo`: a mensagem de sucesso do código anterior está na tela e
      não sai (o pior caso do modo de antes);
    - `tag_entra`: o ENTER adiciona a tag e o portal esvazia o campo.
    """

    captura_respostas_disponivel = True

    def __init__(self, *, resposta=GRAVOU, toast_antigo=False, tag_entra=True, toast_no_confirmar=True):
        self.resposta = resposta
        # [texto, leituras que ainda faltam para sair | None = nunca sai]: o
        # toast de sucesso do portal tem `feedback-message-autoclose`.
        self.toasts = [[MENSAGEM_LMR, None]] if toast_antigo else []
        self.tag_entra = tag_entra
        self.toast_no_confirmar = toast_no_confirmar
        self.dialogo_aberto = False
        self.campos = {}
        self.capturas = []
        self.acoes = []

    def _passar_o_tempo(self):
        self.toasts = [t for t in self.toasts if t[1] is None or t[1] > 0]
        for toast in self.toasts:
            if toast[1] is not None:
                toast[1] -= 1

    # --- leitura ---
    def contar(self, seletor):
        if "CONFIRMAR" in seletor:
            return 1 if self.dialogo_aberto else 0
        if "feedback-message-warning" in seletor:
            return 0
        if "feedback-message-success" in seletor:
            self._passar_o_tempo()
            return len(self.toasts)
        if "feedback-message-text" in seletor:
            return len(self.toasts)
        return 1

    def esta_visivel(self, seletor):
        return self.dialogo_aberto if "CONFIRMAR" in seletor else True

    def texto(self, seletor):
        if "feedback-message-warning" in seletor:
            return ""
        achado = re.search(r"\)\[(\d+)\]$", seletor)
        indice = int(achado.group(1)) if achado else 1
        return self.toasts[indice - 1][0] if indice <= len(self.toasts) else ""

    def get_value(self, seletor):
        return self.campos.get(seletor, "")

    # --- ação ---
    def clear(self, seletor):
        self.campos[seletor] = ""

    def type_text(self, seletor, texto):
        self.campos[seletor] = self.campos.get(seletor, "") + texto

    def press(self, tecla):
        self.acoes.append(("tecla", tecla))
        if tecla == "ENTER" and self.tag_entra:
            self.campos[XPATH_CAMPO_TAG] = ""

    def click_raw(self, seletor):
        if "SALVAR" in seletor:
            self.acoes.append(("clicou", "SALVAR"))
            self.dialogo_aberto = True
            return
        if "CONFIRMAR" in seletor:
            self.acoes.append(("clicou", "CONFIRMAR"))
            self.dialogo_aberto = False
            if self.toast_no_confirmar:
                self.toasts.append([MENSAGEM_LMR, 1])
            return
        self.acoes.append(("clicou", seletor))

    def scroll_to(self, _seletor):
        pass

    def capturar_respostas(self, trecho_url, acao, *, quantas=1, ate=None, timeout_s=20.0):
        self.capturas.append(trecho_url)
        acao()
        return [self.resposta] if self.resposta is not None else []


# --- DataFrame falso, o mesmo de tests/test_lmr_salvar_com_confirmacao.py ---
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
    return _FakeDF([{"PMIB": "4500063671.0001", "Código_PMIB": codigo, "TAG_PMIB": tag}
                    for codigo, tag in pares])


def _rodar(tela, df):
    auto = LMRAutomation.__new__(LMRAutomation)
    auto.engine = tela
    auto.portal = PMIBPortal(tela)
    auto.url_inicial = config.PORTAL_URL
    logs = []
    callbacks = UICallbacks(log=lambda msg, nivel="info", contexto=None: logs.append(str(msg)),
                            ask=lambda pergunta, titulo=None: False)
    erros = auto._processar_ficha_lmr_interna(df, callbacks)
    return erros, "\n".join(logs)


# ===========================================================================
# 1. A resposta do servidor confirma a gravação
# ===========================================================================
def test_a_resposta_do_servidor_confirma_sem_esperar_a_mensagem_anterior_sair(pausas):
    tela = _TelaComResposta(toast_antigo=True)

    erros, logs = _rodar(tela, _df(("COD-1", "TAG-A")))

    assert erros == []
    assert "inserido ✔️" in logs
    assert "A mensagem de sucesso do código anterior não saiu da tela" not in logs
    assert tela.capturas == [respostas.URL_GRAVAR_APLICACAO_LMR]


def test_a_recusa_do_servidor_vai_para_o_erro_com_o_motivo_dele(pausas):
    recusa = {"versionInfo": {}, "exception": {"message": "The value does not match the number of tags added"}}
    tela = _TelaComResposta(resposta=recusa)

    erros, logs = _rodar(tela, _df(("COD-1", "TAG-A")))

    assert [e["codigo_pmib"] for e in erros] == ["COD-1"]
    assert "The value does not match the number of tags added" in erros[0]["erro"]
    assert "inserido ✔️" not in logs


def test_sem_resposta_a_mensagem_na_tela_decide_e_o_lote_volta_ao_modo_de_antes(pausas):
    tela = _TelaComResposta(resposta=None)

    erros, logs = _rodar(tela, _df(("COD-1", "TAG-A"), ("COD-2", "TAG-B")))

    # o 1º código: sem resposta, a mensagem de sucesso na tela confirmou
    assert erros == []
    assert logs.count("inserido ✔️") == 2
    # o 2º já não tentou ler a resposta: o lote voltou ao modo de antes
    assert tela.capturas == [respostas.URL_GRAVAR_APLICACAO_LMR]
    assert "mensagem na tela" in logs


# ===========================================================================
# 2. Cada TAG: esperar o campo esvaziar, e não a pausa fixa
# ===========================================================================
def test_cada_tag_espera_o_campo_esvaziar_em_vez_da_segunda_pausa(pausas):
    tela = _TelaComResposta()

    erros, _ = _rodar(tela, _df(("COD-1", "TAG-A"), ("COD-1", "TAG-B"), ("COD-1", "TAG-C")))

    assert erros == []
    # Antes: duas pausas de 0,5 s por tag (6). Agora só a do TAB -> ENTER (3).
    assert pausas.count(0.5) == 3


def test_tag_que_nao_sai_do_campo_vira_aviso_no_log(pausas):
    tela = _TelaComResposta(tag_entra=False)

    _, logs = _rodar(tela, _df(("COD-1", "TAG-A")))

    assert "TAG-A" in logs and "não saiu do campo" in logs


def test_motor_que_nao_le_o_campo_volta_a_pausa_fixa(pausas):
    tela = _TelaComResposta()
    del tela.campos  # get_value passa a falhar, como num motor que não lê o campo

    def _sem_leitura(_seletor):
        raise AttributeError("sem leitura de campo")

    tela.get_value = _sem_leitura
    tela.campos = {}

    erros, _ = _rodar(tela, _df(("COD-1", "TAG-A")))

    assert erros == []
    assert pausas.count(0.5) == 2
