"""[2026-11-04] Edição em massa do código de projeto: confere, tenta de novo,
e uma ficha que falha não arrasta as seguintes (relato do Jonathan: a 1ª ficha
não carregou e as outras falharam junto)."""
from __future__ import annotations

import pytest

import sigft.services.cria_fichas as cf


@pytest.fixture(autouse=True)
def _sem_sleep(monkeypatch):
    monkeypatch.setattr(cf.time, "sleep", lambda *_a, **_kw: None)


class _PortalFalso:
    """Um portal com o código de projeto de cada ficha. `quebrar` = quantas
    vezes a abertura da ficha falha antes de funcionar (página que não
    carrega); `recusar` = o Salvar não grava (recusa silenciosa)."""

    def __init__(self, codigos, quebrar=None, recusar=()):
        self.codigos = dict(codigos)
        self.quebrar = dict(quebrar or {})
        self.recusar = set(recusar)
        self.aberta = None
        self.digitado = None
        self.gotos = 0

    def goto(self, url):
        self.gotos += 1
        self.aberta = None

    def press(self, teclas):
        pass

    def wait_clickable(self, seletor):
        if seletor == cf.XPATH_CAMPO_PROJETO and self.aberta is None:
            raise TimeoutError("campo do projeto não apareceu")

    def wait_present(self, seletor):
        pmib = self._busca
        if self.quebrar.get(pmib, 0) > 0:
            self.quebrar[pmib] -= 1
            raise TimeoutError("a tabela não filtrou")

    def fill_estrito(self, seletor, texto):
        if seletor == cf.XPATH_BUSCA_MASSA:
            self._busca = texto
        elif seletor == cf.XPATH_CAMPO_PROJETO:
            self.digitado = texto

    def click_raw(self, seletor):
        if seletor == cf.XPATH_SALVAR_PROJETO:
            if self.aberta not in self.recusar:
                self.codigos[self.aberta] = self.digitado
        else:
            self.aberta = self._busca

    def get_value(self, seletor):
        return self.codigos[self.aberta]


def _auto(portal):
    a = cf.AutomacaoPMIB()
    a.engine = portal
    return a


def test_salva_e_confere():
    portal = _PortalFalso({"A": "VELHO"})
    assert _auto(portal).atualizar_projeto_conferido("A", "NOVO") == ("SUCESSO", "Salvo e conferido.")
    assert portal.codigos["A"] == "NOVO"


def test_ja_estava_nao_salva():
    portal = _PortalFalso({"A": "NOVO"})
    estado, _ = _auto(portal).atualizar_projeto_conferido("A", "NOVO")
    assert estado == "JA_ESTAVA"


def test_recusa_silenciosa_vira_erro():
    portal = _PortalFalso({"A": "VELHO"}, recusar={"A"})
    estado, msg = _auto(portal).atualizar_projeto_conferido("A", "NOVO")
    assert estado == "ERRO"
    assert "não guardou" in msg


def test_pagina_que_nao_carrega_na_1a_tentativa_vai_na_2a():
    portal = _PortalFalso({"A": "VELHO"}, quebrar={"A": 1})
    estado, _ = _auto(portal).atualizar_projeto_conferido("A", "NOVO")
    assert estado == "SUCESSO"


def test_ficha_que_falha_sempre_nao_arrasta_as_seguintes():
    portal = _PortalFalso({"A": "VELHO", "B": "VELHO", "C": "VELHO"}, quebrar={"A": 99})
    auto = _auto(portal)
    resultados = [auto.atualizar_projeto_conferido(p, "NOVO")[0] for p in ("A", "B", "C")]
    assert resultados == ["ERRO", "SUCESSO", "SUCESSO"]
    assert portal.codigos["B"] == portal.codigos["C"] == "NOVO"


def test_cada_tentativa_recomeca_pela_lista():
    portal = _PortalFalso({"A": "VELHO"}, quebrar={"A": 1})
    _auto(portal).atualizar_projeto_conferido("A", "NOVO")
    # 1ª abertura falha, 2ª abre, conferência reabre: três idas à lista.
    assert portal.gotos == 3
