r"""
Conferência das autorizações de entrega no portal PMIB --
`sigft/services/autorizacao_portal.py` (2026-10-14).

Pedido do Luan: um botão no Gestão PMIB que descubra no portal quais fichas a
Itaipu já autorizou, sem esperar o export de autorizados. "Autorizado" é ter o
**código SAP de recebimento**, criado na autorização de entrega (a aprovação
da ficha é outra etapa e não cria o código). É o mesmo critério da consulta
da Itaipu que vem na aba "SQL" do export: solicitação de codificação não
cancelada com `StockCodeSAP` preenchido.

Só RPA (regra do Luan, 2026-10-14): o robô pesquisa na lista e abre a ficha
como uma pessoa; o que ele lê é a resposta que o navegador recebeu.

O portal aqui é de mentira, escrito a partir do código das telas
(docs/PMIB_ENGENHARIA_REVERSA.md). ⚠️ `scripts/check.sh` verde não é prova
de portal: a validação é a primeira execução real, com login.
"""
from __future__ import annotations

import datetime as dt
import shutil
import warnings
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from _openpyxl_de_verdade import openpyxl_de_verdade

from sigft import config
from sigft.core.rpa import respostas
from sigft.core.rpa.seletores_duplicada import XPATH_BUSCA_DA_LISTA
from sigft.services import autorizacao_portal

RAIZ = Path(__file__).resolve().parent.parent
KIT = RAIZ / "gestao-sobressalentes" / "_gestao_v2" / "fixtures" / "kit_gestao_pmib"
T1 = "#ST00=TESTE01&MPB020_STATUS_PMIB.xlsx"

precisa_do_kit = pytest.mark.skipif(not (KIT / "status" / T1).is_file(),
                                    reason="kit de teste do cofre ausente (gestao-sobressalentes/)")

# As fichas físicas ainda sem AUTORIZADO no _STATUS_PMIB TESTE01 do kit. A
# 9010 já está AUTORIZADA; 9017/9035/9047 são DOCUMENTAL; 9020 é TÍTULO; as
# sem tipo não contam; a linha 14 é DUPLICADO da 9003 (mesmo PMIB).
PENDENTES_DO_KIT = {"4500063671.9003", "4500063671.9006", "4500063671.9013",
                    "4500063671.9028", "4500063671.9039", "4500063671.9043"}


@pytest.fixture(autouse=True)
def _sem_esperar(monkeypatch):
    monkeypatch.setattr(autorizacao_portal.time, "sleep", lambda *_a, **_kw: None)


@pytest.fixture
def pasta(tmp_path):
    destino = tmp_path / "status"
    shutil.copytree(KIT / "status", destino)
    return destino


def _aba(caminho):
    from openpyxl import load_workbook

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return load_workbook(caminho)[config.ABA_LISTA_MATERIAIS]


# ===========================================================================
# O portal de mentira
# ===========================================================================
class _PortalDeMentira:
    """`fichas`: {pmib: (id, aba 0-6, solicitação | None)}; a solicitação é
    `(codigo_sap, status_pt)`. Uma pesquisa devolve as sete abas, e a ficha só
    aparece na dela. `sem_resposta=True`: nada responde (sessão expirada)."""

    captura_respostas_disponivel = True

    def __init__(self, fichas, *, sem_resposta=False, lista_abre=True, atrasadas=0):
        self.fichas = fichas
        self.sem_resposta = sem_resposta
        self.lista_abre = lista_abre
        # Quantas pesquisas recebem, no lugar das suas, respostas atrasadas de
        # uma carga anterior da lista (sem a ficha pesquisada).
        self.atrasadas = atrasadas
        self.url = ""
        self.campo = ""
        self.pesquisas = []
        self.fichas_abertas = []

    # primitivas usadas na conferência
    def goto(self, url):
        self.url = url

    def clear(self, seletor):
        assert seletor == XPATH_BUSCA_DA_LISTA
        self.campo = ""

    def type_text(self, seletor, texto):
        assert seletor == XPATH_BUSCA_DA_LISTA
        self.campo += texto

    def press(self, tecla):
        if tecla == "ENTER":
            self.pesquisas.append(self.campo)

    def fechar(self):
        pass

    # as respostas que a página recebe
    def _abas(self):
        abas = [[] for _ in range(respostas.ABAS_DA_LISTA)]
        busca = self.pesquisas[-1] if self.pesquisas else ""
        for pmib, (ident, aba, _sol) in self.fichas.items():
            if busca and busca == pmib:
                numero, sequencial = pmib.split(".")
                abas[aba].append({"Id": ident, "DSNumber": numero, "DSNumberSec": int(sequencial),
                                  "NameES": "X", "NamePT": "X", "WasInApproval": True})
        return [{"data": {"List": {"List": linhas}, "Count": str(len(linhas))}} for linhas in abas]

    def _codificacao(self):
        ident = parse_qs(urlparse(self.url).query).get("PMIB_DataSheetId", [""])[0]
        for _pmib, (id_ficha, _aba, solicitacao) in self.fichas.items():
            if id_ficha != ident:
                continue
            if solicitacao is None:
                return {"data": {"List": {"List": []}, "Count": "0"}}
            codigo, status = solicitacao
            item = {"RequestStatus": {"DescriptionPt": status, "DescriptionEs": status},
                    "CodificationRequest": {"Id": "9" + id_ficha, "StockCodeSAP": codigo,
                                            "RequestNumberSAP": "", "SAPSendInProgress": False}}
            return {"data": {"List": {"List": [item]}, "Count": "1"}}
        return None

    def capturar_respostas(self, trecho_url, acao, *, quantas=1, ate=None, timeout_s=20.0):
        acao()
        if self.sem_resposta:
            return []
        if trecho_url == respostas.URL_LISTA_DE_FICHAS:
            if not self.lista_abre:
                return []
            abas = self._abas()
            if self.pesquisas and self.atrasadas:
                self.atrasadas -= 1
                abas = [{"data": {"List": {"List": []}, "Count": "0"}}] * respostas.ABAS_DA_LISTA
            chegaram = []
            for corpo in abas:
                chegaram.append(corpo)
                if (ate and ate(corpo)) or len(chegaram) >= quantas:
                    break
            return chegaram
        if trecho_url == respostas.URL_CODIFICACAO_DA_FICHA:
            self.fichas_abertas.append(self.url)
            corpo = self._codificacao()
            return [corpo] if corpo else []
        return []


def _conferir(motor, pasta, hoje=dt.date(2026, 10, 9)):
    conferencia = autorizacao_portal.ConferenciaNoPortal(motor)
    with openpyxl_de_verdade():
        return list(conferencia.executar(pasta, hoje=hoje))


# ===========================================================================
# Quais fichas são conferidas
# ===========================================================================
@precisa_do_kit
def test_confere_so_as_fichas_fisicas_ainda_sem_autorizado(pasta):
    with openpyxl_de_verdade():
        pmibs, avisos = autorizacao_portal.fichas_a_conferir(pasta)

    assert pmibs == PENDENTES_DO_KIT
    # TESTE02 está no layout antigo, sem SITUAÇÃO DA AUTORIZAÇÃO: não é conferido, e o log diz.
    assert any("TESTE02" in aviso for aviso in avisos)


# ===========================================================================
# A conferência inteira
# ===========================================================================
@precisa_do_kit
def test_ficha_com_codigo_sap_vira_autorizado_com_a_data_da_conferencia(pasta):
    pytest.importorskip("lxml")
    portal = _PortalDeMentira({
        "4500063671.9003": ("48213", 2, ("721164", "Aprovado")),
        "4500063671.9006": ("48214", 0, ("", "Em elaboração")),
        "4500063671.9028": ("48215", 3, None),
        "4500063671.9039": ("48216", 1, ("730001", "Cancelado")),
        "4500063671.9043": ("48217", 5, ("730002", "Aprovado")),
        # a 9013 não está no portal
    })

    linhas = _conferir(portal, pasta)
    with openpyxl_de_verdade():
        ws = _aba(pasta / T1)

        # 9003 (linha 6): e-mail 15/09 -> prazo 06/10; conferida em 09/10 -> 3 dias
        assert (ws["S6"].value, ws["T6"].value) == ("AUTORIZADO", 3)
        # a linha DUPLICADO do mesmo PMIB acompanha
        assert ws["S14"].value == "AUTORIZADO"
        # 9043 (linha 17) estava ATRASADO com 30 dias: vira AUTORIZADO e os dias ficam
        assert (ws["S17"].value, ws["T17"].value) == ("AUTORIZADO", 30)
        # sem código (9006), sem solicitação (9028), cancelada (9039), fora do portal (9013): nada muda
        assert ws["S7"].value is None
        assert ws["S13"].value is None
        assert ws["S16"].value is None
        assert ws["S9"].value is None

    log = "\n".join(linhas)
    assert "721164" in log and "730002" in log
    assert any("4500063671.9013" in linha and "não encontrad" in linha for linha in linhas)


@precisa_do_kit
def test_pesquisa_cada_ficha_pendente_e_so_abre_as_que_achou(pasta):
    portal = _PortalDeMentira({"4500063671.9003": ("48213", 4, ("", "Em elaboração"))})

    _conferir(portal, pasta)

    assert set(portal.pesquisas) == PENDENTES_DO_KIT
    assert portal.fichas_abertas == [respostas.url_da_ficha("48213")]


@precisa_do_kit
def test_ficha_que_nao_veio_na_primeira_pesquisa_e_pesquisada_de_novo(pasta):
    # Respostas atrasadas de uma carga anterior da lista podem completar a
    # contagem da pesquisa: antes de dizer "não encontrada", pesquisa de novo.
    portal = _PortalDeMentira({"4500063671.9003": ("48213", 6, ("721164", "Aprovado"))}, atrasadas=1)

    linhas = _conferir(portal, pasta)

    assert portal.pesquisas[:2] == ["4500063671.9003", "4500063671.9003"]
    assert any("4500063671.9003" in linha and "721164" in linha for linha in linhas)


@precisa_do_kit
def test_sem_nenhum_codigo_novo_nada_e_gravado(pasta):
    antes = (pasta / T1).read_bytes()
    portal = _PortalDeMentira({"4500063671.9003": ("48213", 0, ("", "Em elaboração"))})

    linhas = _conferir(portal, pasta)

    assert (pasta / T1).read_bytes() == antes
    assert not any("[ERRO]" in linha for linha in linhas)


# ===========================================================================
# Quando o portal não colabora
# ===========================================================================
@precisa_do_kit
def test_lista_que_nao_responde_ao_abrir_para_tudo_antes_de_pesquisar(pasta):
    portal = _PortalDeMentira({}, lista_abre=False)

    linhas = _conferir(portal, pasta)

    assert portal.pesquisas == []
    assert any("[ERRO]" in linha and "login" in linha.lower() for linha in linhas)


@precisa_do_kit
def test_fichas_seguidas_sem_resposta_param_a_conferencia_e_nada_e_gravado(pasta):
    antes = (pasta / T1).read_bytes()
    portal = _PortalDeMentira({}, sem_resposta=True)
    portal.lista_abre = True

    # A carga da lista responde; depois o portal para de responder.
    original = portal.capturar_respostas
    estado = {"carregou": False}

    def _capturar(trecho_url, acao, **kw):
        if not estado["carregou"]:
            estado["carregou"] = True
            portal.sem_resposta = False
            corpo = original(trecho_url, acao, **kw)
            portal.sem_resposta = True
            return corpo
        return original(trecho_url, acao, **kw)

    portal.capturar_respostas = _capturar

    linhas = _conferir(portal, pasta)

    assert len(portal.pesquisas) == autorizacao_portal.SEGUIDAS_SEM_RESPOSTA_PARA_PARAR
    assert any("[AVISO]" in linha and "parei" in linha.lower() for linha in linhas)
    assert (pasta / T1).read_bytes() == antes


@precisa_do_kit
def test_motor_que_nao_le_respostas_nao_confere_e_explica(pasta):
    class _MotorAntigo:
        pass

    linhas = _conferir(_MotorAntigo(), pasta)

    assert any("[ERRO]" in linha for linha in linhas)
