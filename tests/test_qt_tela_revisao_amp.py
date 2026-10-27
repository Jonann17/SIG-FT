"""A aba "Revisão no AMP" do PMIB Manager (Qt). O serviço e o cliente são dublês: a rodada
tem os testes dela em `test_revisao_amp_rodada.py`. Desenho:
`docs/superpowers/specs/2026-10-27-amp-revisao-de-listas-design.md`, §7 e §8.
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from sigft.app_qt.views import revisao_amp as tela_mod
from sigft.app_qt.views.conferencia_revisoes import UltimaConferencia
from sigft.services import conferencia_revisoes as cr
from sigft.services import revisao_amp as ra

URL = "https://ampworkflow.gevernova.net/webhook/sigft-revisao-listas"
CODIGO = "#ITA0=Y01TF001&BPB020"
OUTRO = "#ST00=X01MPB020&MPB020"
AVISO_SEM_CHAVE = "Configure o endereço e a chave do webhook do AMP em Configuração → Chaves de API."


class _Controller:
    def __init__(self, url=URL, chave="segredo-do-webhook"):
        self.chaves = {"AMP_WEBHOOK_URL": url, "AMP_WEBHOOK_CHAVE": chave}

    def get_key(self, nome):
        return self.chaves.get(nome, "")


class _ClienteAmp:
    def __init__(self, url, chave, **_kw):
        self.url, self.chave = url, chave


def _lista(tmp_path, codigo, falta=""):
    pasta = tmp_path / codigo[-6:]
    pasta.mkdir(parents=True, exist_ok=True)
    dados = cr.ListaNaMapeadora(codigo, "0B", "Em Processo", "Aprovado", "0A", "x")
    return ra.ListaParaAmp(cr.ItemConferencia(dados, "aprovada", pasta), pasta / "s.xlsx", pasta / "a.pdf",
                           pasta / "b.pdf", "0B", falta)


@pytest.fixture
def ultima(tmp_path):
    mapeadora = cr.Mapeadora(tmp_path / "mapa" / "Mapeamento.xlsx", datetime.now(), [])
    return UltimaConferencia(mapeadora, cr.Conferencia([], em_dia=0, sem_status_pmib=0), [], tmp_path / "raiz")


@pytest.fixture
def servico(monkeypatch, tmp_path):
    """Dublê do serviço: as listas e a rodada. Guarda o que a tela pediu."""
    falso = SimpleNamespace(listas=[_lista(tmp_path, CODIGO), _lista(tmp_path, OUTRO, "falta: PDF da revisão atual")],
                            resultados=[], chamadas=[], testes=[], cancelado=None)

    def listas_para_amp(conferencia, downloads, pasta_mapeadora, pasta_raiz):
        falso.chamadas.append(("listas", pasta_mapeadora, pasta_raiz))
        return falso.listas

    def revisar_listas(listas, cliente, *, versao_sigft, url, chave_posta, log_cb, progress_cb=None,
                       cancelado_cb=None, resultado_cb=None, **_kw):
        falso.chamadas.append(("revisar", cliente.url, cliente.chave, url, chave_posta))
        falso.cancelado = cancelado_cb
        for resultado in falso.resultados:
            resultado_cb(resultado)
        return list(falso.resultados)

    def testar_conexao(cliente, listas):
        falso.testes.append(list(listas))
        return ["OK      Ping: workflow 2026-10-27 (0.3 s, execução 4)",
                "FALHOU  Eco: 1 de 2 códigos não voltaram iguais (mascarado pelo AMP?): X"]

    monkeypatch.setattr(tela_mod.revisao_amp_svc, "listas_para_amp", listas_para_amp)
    monkeypatch.setattr(tela_mod.revisao_amp_svc, "revisar_listas", revisar_listas)
    monkeypatch.setattr(tela_mod.revisao_amp_svc, "testar_conexao", testar_conexao)
    monkeypatch.setattr(tela_mod, "ClienteAmp", _ClienteAmp)
    return falso


@pytest.fixture
def avisos(monkeypatch):
    """Os QMessageBox.warning do clique (thread da interface)."""
    lista = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a: lista.append(a[1:])))
    return lista


def _tela(qtbot, *, controller=None, ultima=None):
    t = tela_mod.ModuloRevisaoAmp(controller=controller or _Controller(), fonte=SimpleNamespace(ultima=ultima))
    qtbot.addWidget(t)
    return t


def _revisar(t, qtbot, n):
    t.btn_amp.click()
    qtbot.waitUntil(lambda: t.btn_amp.isEnabled() and len(t.resultados_amp) == n, timeout=5000)


def _coluna_amp(t):
    return [t.tabela.topLevelItem(i).text(4) for i in range(t.tabela.topLevelItemCount())]


@pytest.mark.parametrize("url, chave", [("", "segredo"), (URL, ""), ("", "")])
def test_sem_chave_avisa_e_nao_chama(qt_interface, qtbot, servico, avisos, ultima, url, chave):
    t = _tela(qtbot, controller=_Controller(url, chave), ultima=ultima)
    t.btn_amp.click()
    t.btn_testar_amp.click()
    assert avisos == [("Revisão no AMP", AVISO_SEM_CHAVE)] * 2
    assert servico.chamadas == [] and servico.testes == []


def test_sem_conferencia_avisa(qt_interface, qtbot, servico, avisos):
    t = _tela(qtbot, ultima=None)
    t.btn_amp.click()
    assert avisos == [("Revisão no AMP", "Confira as revisões antes.")]
    assert servico.chamadas == []


def test_mostra_o_endereco_e_nunca_a_chave(qt_interface, qtbot, ultima):
    t = _tela(qtbot, ultima=ultima)
    assert URL in t.lbl_webhook.text() and "segredo" not in t.lbl_webhook.text()
    sem = _tela(qtbot, controller=_Controller("", ""), ultima=ultima)
    assert sem.lbl_webhook.text() == "Webhook do AMP não configurado: Configuração → Chaves de API."


def test_revisar_mostra_o_resultado_na_coluna_amp(qt_interface, qtbot, servico, ultima):
    a, b = servico.listas
    html = a.item.pasta / f"{CODIGO}[0A-0B] revisao AMP.html"
    servico.resultados = [ra.ResultadoAmp(a, "pronto", html, html.name), ra.ResultadoAmp(b, "falta", None, b.falta)]
    t = _tela(qtbot, ultima=ultima)
    _revisar(t, qtbot, 2)
    linhas = [[t.tabela.topLevelItem(i).text(c) for c in range(5)] for i in range(t.tabela.topLevelItemCount())]
    assert linhas == [[CODIGO, "0A", "0B", "Aprovado", f"HTML pronto: {html.name}"],
                      [OUTRO, "0A", "0B", "Aprovado", "falta: PDF da revisão atual"]]
    assert servico.chamadas == [("listas", ultima.mapeadora.caminho.parent, ultima.pasta_raiz),
                                ("revisar", URL, "segredo-do-webhook", URL, True)]
    assert not t.btn_copiar_diag.isEnabled()


def test_falha_liga_o_copiar_e_copia_os_diagnosticos(qt_interface, qtbot, servico, ultima):
    a, b = servico.listas
    servico.resultados = [ra.ResultadoAmp(a, "falhou", None, "o AMP recusou a chave (HTTP 403)", "DIAGNOSTICO-A\n"),
                          ra.ResultadoAmp(b, "falta", None, b.falta)]
    t = _tela(qtbot, ultima=ultima)
    assert not t.btn_copiar_diag.isEnabled()
    _revisar(t, qtbot, 2)
    assert t.btn_copiar_diag.isEnabled()
    assert _coluna_amp(t)[0] == "falhou: o AMP recusou a chave (HTTP 403)"
    t.btn_copiar_diag.click()
    texto = QApplication.clipboard().text()
    assert texto == ra.diagnosticos_para_copiar(t.resultados_amp) and "DIAGNOSTICO-A" in texto


def test_rodada_nova_comeca_sem_o_diagnostico_da_anterior(qt_interface, qtbot, servico, ultima):
    a, b = servico.listas
    servico.resultados = [ra.ResultadoAmp(a, "falhou", None, "model timeout", "DIAGNOSTICO-A\n")]
    t = _tela(qtbot, ultima=ultima)
    _revisar(t, qtbot, 1)
    servico.resultados = [ra.ResultadoAmp(a, "pronto", a.item.pasta / "x.html", "x.html"),
                          ra.ResultadoAmp(b, "falta", None, b.falta)]
    _revisar(t, qtbot, 2)
    assert not t.btn_copiar_diag.isEnabled()
    assert _coluna_amp(t) == ["HTML pronto: x.html", "falta: PDF da revisão atual"]


def test_parar_vale_para_a_rodada(qt_interface, qtbot, servico, ultima):
    servico.resultados = [ra.ResultadoAmp(servico.listas[0], "parado", None, "parado antes de ir ao AMP")]
    t = _tela(qtbot, ultima=ultima)
    _revisar(t, qtbot, 1)
    assert servico.cancelado() is False
    t.btn_parar.click()
    assert servico.cancelado() is True
    assert _coluna_amp(t)[0] == "parado"


def test_dois_cliques_abrem_o_html(qt_interface, qtbot, servico, ultima, monkeypatch):
    abertos = []
    monkeypatch.setattr(tela_mod.plataforma, "abrir_no_sistema", abertos.append)
    a, b = servico.listas
    html = a.item.pasta / "x.html"
    servico.resultados = [ra.ResultadoAmp(a, "pronto", html, html.name), ra.ResultadoAmp(b, "falta", None, b.falta)]
    t = _tela(qtbot, ultima=ultima)
    _revisar(t, qtbot, 2)
    t.tabela.itemDoubleClicked.emit(t.tabela.topLevelItem(0), 0)
    t.tabela.itemDoubleClicked.emit(t.tabela.topLevelItem(1), 0)
    assert abertos == [html]


def test_testar_conexao_amp_escreve_as_linhas(qt_interface, qtbot, servico, ultima):
    t = _tela(qtbot, ultima=ultima)
    t.btn_testar_amp.click()
    qtbot.waitUntil(lambda: "FALHOU  Eco:" in t.console.toPlainText(), timeout=5000)
    assert "OK      Ping: workflow 2026-10-27" in t.console.toPlainText()
    assert servico.testes == [servico.listas]


def test_testar_conexao_sem_conferencia_vai_sem_listas(qt_interface, qtbot, servico):
    t = _tela(qtbot, ultima=None)
    t.btn_testar_amp.click()
    qtbot.waitUntil(lambda: bool(servico.testes), timeout=5000)
    assert servico.testes == [[]]


def test_conferencia_rodando_avisa_e_nao_chama(qt_interface, qtbot, servico, avisos, ultima):
    # Ainda baixando: a última conferência está sem os downloads, e um PDF pode estar pela
    # metade (revisão final do ramo, 2026-10-27).
    t = tela_mod.ModuloRevisaoAmp(controller=_Controller(), fonte=SimpleNamespace(ultima=ultima, rodando=lambda: True))
    qtbot.addWidget(t)
    t.btn_amp.click()
    assert avisos == [("Revisão no AMP", "A conferência ainda está rodando: espere ela terminar.")]
    assert servico.chamadas == []
