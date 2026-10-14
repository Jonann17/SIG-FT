r"""
Leitura das respostas que a página recebe -- `capturar_respostas` (2026-10-14).

É a base de duas melhorias: a conferência das autorizações de entrega no
portal (Gestão PMIB) e a confirmação da aplicação LMR pela resposta do
servidor, em vez da mensagem na tela. Ver docs/PMIB_ENGENHARIA_REVERSA.md, R1.

Continua sendo RPA: o motor NÃO faz requisição nenhuma. O robô clica ou navega
como uma pessoa, e o motor só lê o que o navegador recebeu por causa disso.
Regra do Luan (2026-10-14): a Itaipu proíbe contato com o banco de dados dela,
e o SIG-FT não chama o servidor por fora da tela.

A página é falsa e duck-typed, como em tests/test_playwright_engine.py: a ação
do robô agenda respostas, e elas só "chegam" quando o motor espera
(`wait_for_timeout`), que é como o Playwright síncrono entrega eventos.
"""
from __future__ import annotations

import pytest

from sigft.core.rpa.playwright_engine import PlaywrightEngine

URL_LISTA = ("https://apps.itaipu.gov.br/PMIB/screenservices/PMIB_DataSheet_CW/PMIB_DatasheetList/"
             "PMIB_DatasheetListTable/ScreenDataSetGetPMIBDataSheetsByCreateBy")
URL_OUTRA = ("https://apps.itaipu.gov.br/PMIB/screenservices/PMIB_DataSheet_CW/PMIB_DatasheetList/"
             "PMIB_DatasheetListTabHeader/DataActionGetCountDatasheetByStatus")
TRECHO = "PMIB_DatasheetListTable/ScreenDataSetGetPMIBDataSheetsByCreateBy"


class _Resposta:
    def __init__(self, url, corpo=None, erro=None):
        self.url = url
        self._corpo = corpo
        self._erro = erro

    def json(self):
        if self._erro is not None:
            raise self._erro
        return self._corpo


class _PaginaQueRecebe:
    def __init__(self):
        self.ouvintes = {}
        self.a_chegar = []
        self.esperas = 0
        self.removidos = []

    def chegam(self, *respostas):
        self.a_chegar.extend(respostas)

    def on(self, evento, ouvinte):
        self.ouvintes.setdefault(evento, []).append(ouvinte)

    def remove_listener(self, evento, ouvinte):
        self.ouvintes[evento].remove(ouvinte)
        self.removidos.append(evento)

    def wait_for_timeout(self, _ms):
        self.esperas += 1
        if self.a_chegar:
            resposta = self.a_chegar.pop(0)
            for ouvinte in list(self.ouvintes.get("response", [])):
                ouvinte(resposta)


def _motor():
    pagina = _PaginaQueRecebe()
    return PlaywrightEngine(pagina), pagina


def test_o_motor_playwright_anuncia_que_le_as_respostas():
    motor, _ = _motor()
    assert motor.captura_respostas_disponivel is True


def test_pagina_que_nao_entrega_respostas_nao_anuncia_a_leitura():
    # Quem usa decide pelo anúncio: anunciar sem poder ler faria a aplicação
    # LMR clicar o CONFIRMAR e dar o código por não confirmado.
    class _PaginaSoComDownload:
        def on(self, evento, ouvinte):
            pass

    assert PlaywrightEngine(_PaginaSoComDownload()).captura_respostas_disponivel is False


def test_devolve_so_as_respostas_do_endereco_pedido():
    motor, pagina = _motor()

    respostas = motor.capturar_respostas(
        TRECHO,
        lambda: pagina.chegam(_Resposta(URL_OUTRA, {"data": "contagem"}),
                              _Resposta(URL_LISTA, {"data": "lista"})),
        quantas=1)

    assert respostas == [{"data": "lista"}]


def test_para_quando_chegam_as_respostas_pedidas_e_nao_espera_as_outras():
    motor, pagina = _motor()

    respostas = motor.capturar_respostas(
        TRECHO,
        lambda: pagina.chegam(*(_Resposta(URL_LISTA, {"n": i}) for i in (1, 2, 3))),
        quantas=2)

    assert respostas == [{"n": 1}, {"n": 2}]
    assert pagina.a_chegar, "a terceira resposta não devia ter sido esperada"


def test_para_antes_quando_uma_resposta_ja_basta():
    motor, pagina = _motor()

    respostas = motor.capturar_respostas(
        TRECHO,
        lambda: pagina.chegam(*(_Resposta(URL_LISTA, {"n": i}) for i in (1, 2, 3))),
        quantas=3, ate=lambda corpo: corpo["n"] == 2)

    assert respostas == [{"n": 1}, {"n": 2}]
    assert len(pagina.a_chegar) == 1


def test_sem_resposta_devolve_lista_vazia_depois_de_um_numero_contado_de_esperas():
    # Regra 7 de docs/PORTAL_COMO_ELE_SE_COMPORTA.md: conte tentativas, não
    # segundos. Aqui a espera não dorme de verdade; um laço por relógio giraria
    # milhares de vezes em 0,3 s.
    motor, pagina = _motor()

    respostas = motor.capturar_respostas(TRECHO, lambda: None, quantas=1, timeout_s=0.3)

    assert respostas == []
    assert pagina.esperas == 3


def test_resposta_que_nao_e_json_conta_mas_nao_volta():
    motor, pagina = _motor()

    respostas = motor.capturar_respostas(
        TRECHO,
        lambda: pagina.chegam(_Resposta(URL_LISTA, erro=ValueError("corpo vazio")),
                              _Resposta(URL_LISTA, {"data": "ok"})),
        quantas=2)

    assert respostas == [{"data": "ok"}]


def test_o_ouvinte_sai_da_pagina_mesmo_quando_a_acao_falha():
    motor, pagina = _motor()

    def _acao():
        raise RuntimeError("o clique falhou")

    with pytest.raises(RuntimeError):
        motor.capturar_respostas(TRECHO, _acao)

    assert pagina.removidos == ["response"]
    assert pagina.ouvintes["response"] == []
