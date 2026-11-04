"""A tela da Etapa 2 do DocPack (Qt): procurar os dossiês vazios, consultar no AMP (sem
escrever) e gravar só com o "sim". O serviço e os clientes são dublês: o serviço tem os testes
dele em `test_docpack_etapa2.py`.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from sigft.app_qt.views import docpack_etapa2 as tela_mod
from sigft.services import docpack_etapa2 as e2

URL = "https://ampworkflow.gevernova.net/webhook/sigft-criacao-status-pmib"
CHAVE = "segredo-do-docpack"
CODIGO = "#ST00=M00MEU10&MPB020"
OUTRO = "#ITA0=U10MKC10&EPB020"


class _Controller:
    def __init__(self, url=URL, chave=CHAVE):
        self.chaves = {"AMP_CRIACAO_STATUS_PMIB_URL": url, "AMP_CRIACAO_STATUS_PMIB_CHAVE": chave}

    def get_key(self, nome):
        return self.chaves.get(nome) or ""

    def save_keys(self, novas):
        self.chaves.update(novas)


class _Cliente:
    def __init__(self, *args, **_kw):
        self.args = args


def _dossie(tmp_path, codigo, *, com_precos=True):
    pasta = tmp_path / codigo[-6:]
    precos = pasta / "p.xlsm" if com_precos else None
    return e2.Dossie(codigo, pasta, pasta / "s.xlsx", precos)


@pytest.fixture
def servico(monkeypatch, tmp_path):
    falso = SimpleNamespace(dossies=[_dossie(tmp_path, CODIGO), _dossie(tmp_path, OUTRO, com_precos=False)],
                            consulta=None, gravados=None, aconex=None)

    def procurar_dossies(raiz):
        return e2.Varredura(list(falso.dossies), ["#X&MPB020"], [("#Y&MPB020", "aba faltando")])

    def consultar(dossies, aconex, amp, *, log_cb, progress_cb=None, cancelado_cb=None):
        falso.consulta, falso.aconex = list(dossies), aconex
        materiais = (e2.Material(1, 2, "pç", "ROLAMENTO"),)
        return [e2.Proposta(dossies[0], "pronta", "1", Path("x.pdf"), "0C", materiais)] + [
            e2.Proposta(d, "falhou", "o AMP não devolveu nenhum material") for d in dossies[1:]]

    def gravar(propostas, *, log_cb, progress_cb=None):
        falso.gravados = list(propostas)
        return [e2.Gravacao(p.dossie, "gravado", "ok") for p in propostas]

    monkeypatch.setattr(tela_mod.etapa2_svc, "procurar_dossies", procurar_dossies)
    monkeypatch.setattr(tela_mod.etapa2_svc, "consultar", consultar)
    monkeypatch.setattr(tela_mod.etapa2_svc, "gravar", gravar)
    monkeypatch.setattr(tela_mod, "ClienteAmp", _Cliente)
    monkeypatch.setattr(tela_mod, "ClienteAconex", _Cliente)
    monkeypatch.setattr(tela_mod, "perfil_do_aconex", lambda _pai: SimpleNamespace(nome="perfil"))
    return falso


@pytest.fixture
def avisos(monkeypatch):
    lista = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a: lista.append(a[2])))
    return lista


def _tela(qtbot, tmp_path, controller=None):
    tela = tela_mod.ModuloDocPackEtapa2(controller=controller or _Controller())
    tela.pasta_raiz = str(tmp_path)
    qtbot.addWidget(tela)
    return tela


def _procurada(tela, qtbot):
    tela._procurar()
    qtbot.waitUntil(lambda: tela.tabela.topLevelItemCount() > 0 and not tela.rodando(), timeout=5000)
    return tela


def test_procurar_mostra_os_dossies_vazios_todos_marcados(qt_interface, qtbot, tmp_path, servico):
    tela = _procurada(_tela(qtbot, tmp_path), qtbot)
    assert tela.tabela.topLevelItemCount() == 2
    assert [d.codigo for d in tela.marcados()] == [CODIGO, OUTRO]
    assert tela.tabela.topLevelItem(1).text(2) == "não está na pasta"
    assert not tela.btn_gravar.isEnabled()
    qtbot.waitUntil(lambda: "aba faltando" in tela.console.toPlainText(), timeout=5000)
    assert "1 já com materiais" in tela.console.toPlainText()


def test_consultar_nao_grava_e_libera_o_gravar(qt_interface, qtbot, tmp_path, servico):
    tela = _procurada(_tela(qtbot, tmp_path), qtbot)
    tela._consultar()
    qtbot.waitUntil(lambda: servico.consulta is not None and not tela.rodando(), timeout=5000)
    qtbot.waitUntil(lambda: tela.btn_gravar.isEnabled(), timeout=5000)
    assert servico.gravados is None and servico.aconex is not None
    assert tela.tabela.topLevelItem(0).text(tela_mod.COL_SITUACAO) == "1 material(is) do AMP"
    assert tela.tabela.topLevelItem(1).text(tela_mod.COL_SITUACAO).startswith("falhou:")


def test_sem_baixar_do_aconex_vai_sem_cliente(qt_interface, qtbot, tmp_path, servico):
    tela = _procurada(_tela(qtbot, tmp_path), qtbot)
    tela.caixa_aconex.setChecked(False)
    tela._consultar()
    qtbot.waitUntil(lambda: servico.consulta is not None and not tela.rodando(), timeout=5000)
    assert servico.aconex is None


def test_gravar_so_com_o_sim(qt_interface, qtbot, tmp_path, servico, monkeypatch):
    tela = _procurada(_tela(qtbot, tmp_path), qtbot)
    tela._consultar()
    qtbot.waitUntil(lambda: tela.btn_gravar.isEnabled(), timeout=5000)
    respostas = [False, True]
    perguntas = []

    def perguntar(_titulo, mensagem, **_kw):
        perguntas.append(mensagem)
        return respostas.pop(0)

    monkeypatch.setattr(tela, "perguntar_sim_nao", perguntar)
    tela._gravar()
    qtbot.waitUntil(lambda: not tela.rodando() and tela.btn_gravar.isEnabled(), timeout=5000)
    assert servico.gravados is None and "ROLAMENTO" in perguntas[0]
    tela._gravar()
    qtbot.waitUntil(lambda: servico.gravados is not None and not tela.rodando(), timeout=5000)
    qtbot.waitUntil(lambda: tela.tabela.topLevelItem(0).text(tela_mod.COL_SITUACAO) == "gravado", timeout=5000)
    assert [p.dossie.codigo for p in servico.gravados] == [CODIGO]
    assert tela.tabela.topLevelItem(0).checkState(0) == Qt.CheckState.Unchecked
    assert not tela.btn_gravar.isEnabled()


def test_sem_webhook_avisa_e_nao_consulta(qt_interface, qtbot, tmp_path, servico, avisos):
    tela = _procurada(_tela(qtbot, tmp_path, controller=_Controller(url="", chave="")), qtbot)
    tela._consultar()
    assert servico.consulta is None and avisos and "Webhook" in avisos[0]
    assert "não configurado" in tela.lbl_webhook.text()


def test_nada_marcado_avisa(qt_interface, qtbot, tmp_path, servico, avisos):
    tela = _procurada(_tela(qtbot, tmp_path), qtbot)
    for i in range(tela.tabela.topLevelItemCount()):
        tela.tabela.topLevelItem(i).setCheckState(0, Qt.CheckState.Unchecked)
    tela._consultar()
    assert servico.consulta is None and avisos


def test_a_chave_nao_aparece_na_tela(qt_interface, qtbot, tmp_path, servico):
    tela = _tela(qtbot, tmp_path)
    assert CHAVE not in tela.lbl_webhook.text() and "chave posta" in tela.lbl_webhook.text()


def test_embutida_usa_o_console_e_a_barra_da_secao(qt_interface, qtbot, tmp_path, servico):
    from sigft.app_qt.widgets import blocos
    from sigft.app_qt.widgets.console import ConsoleFrame

    externo = ConsoleFrame()
    barra = blocos.barra_progresso()
    qtbot.addWidget(externo)
    qtbot.addWidget(barra)
    tela = tela_mod.ModuloDocPackEtapa2(controller=_Controller(), embutida=True, console_externo=externo,
                                        progresso_externo=barra)
    qtbot.addWidget(tela)
    assert tela.console is externo and tela.progress_bar is barra
