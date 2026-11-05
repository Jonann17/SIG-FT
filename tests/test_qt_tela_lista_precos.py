"""A tela "Lista de Preços" (Qt, 2026-11-05): as duas abas, com o serviço dublado (a regra tem
os testes dela em `test_lista_precos_arquivo.py`)."""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from sigft.app_qt.views import lista_precos as tela_mod
from sigft.services import lista_precos_arquivo as lp

CODIGO = "#ST00=M00MEU10&MPB020"
OUTRO = "#ITA0=U10MKC10&EPB020"


def _sistema(tmp_path, codigo, *, lista=False, materiais=3):
    pasta = tmp_path / codigo[-6:]
    return lp.Sistema(codigo, pasta, pasta / "s.xlsx", pasta / "p.xlsm" if lista else None, False, materiais)


@pytest.fixture
def servico(monkeypatch, tmp_path):
    estado = {"criados": None, "atualizou": 0}
    sistemas = [_sistema(tmp_path, CODIGO), _sistema(tmp_path, OUTRO, lista=True)]
    monkeypatch.setattr(tela_mod.lp_svc, "varrer", lambda _raiz: list(sistemas))

    def criar_listas(escolhidos, template, *, titulos=None, log_cb, progress_cb=None, cancelado_cb=None):
        estado["criados"] = [s.codigo for s in escolhidos]
        return []

    monkeypatch.setattr(tela_mod.lp_svc, "criar_listas", criar_listas)
    return estado


def _criar(qtbot, tmp_path):
    tela = tela_mod.ModuloListaPrecosCriar()
    tela.pasta_raiz, tela.template, tela.caminho_mapeadora = str(tmp_path), str(tmp_path / "t.xlsm"), ""
    qtbot.addWidget(tela)
    return tela


def test_procurar_marca_so_os_sem_lista(qt_interface, qtbot, tmp_path, servico):
    tela = _criar(qtbot, tmp_path)
    tela._varrer()
    qtbot.waitUntil(lambda: tela.tabela.topLevelItemCount() == 2 and not tela.rodando(), timeout=5000)
    assert [s.codigo for s in tela.marcados()] == [CODIGO]
    assert tela.tabela.topLevelItem(0).text(2) == "não" and tela.tabela.topLevelItem(1).text(2) == "sim"
    assert not (tela.tabela.topLevelItem(1).flags() & Qt.ItemFlag.ItemIsUserCheckable)
    assert tela.btn_criar.isEnabled()
    assert tela.tabela.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded


def test_criar_so_com_o_sim(qt_interface, qtbot, tmp_path, servico, monkeypatch):
    tela = _criar(qtbot, tmp_path)
    tela._varrer()
    qtbot.waitUntil(lambda: tela.tabela.topLevelItemCount() == 2 and not tela.rodando(), timeout=5000)
    respostas = [False, True]
    monkeypatch.setattr(tela, "perguntar_sim_nao", lambda *_a, **_k: respostas.pop(0))
    tela._criar()
    qtbot.waitUntil(lambda: not tela.rodando(), timeout=5000)
    assert servico["criados"] is None
    tela._criar()
    qtbot.waitUntil(lambda: servico["criados"] is not None and not tela.rodando(), timeout=5000)
    assert servico["criados"] == [CODIGO]


def test_criar_sem_template_avisa(qt_interface, qtbot, tmp_path, servico, monkeypatch):
    tela = _criar(qtbot, tmp_path)
    tela.template = ""
    avisos = []
    monkeypatch.setattr(tela, "avisar", lambda _t, m, *_a, **_k: avisos.append(m))
    tela._criar()
    assert avisos == [tela_mod.t(tela_mod.AVISO_SEM_TEMPLATE)]


def _conferencia(tmp_path, *, valorizada, divergencias=True):
    sistema = _sistema(tmp_path, CODIGO, lista=True)
    preco = 10.0 if valorizada else None
    lista = [lp.Item(codigo_pmib="4500063671.0001", descricao="A", qtd=1, valor=preco)]
    status = [lp.Item(codigo_pmib="4500063671.0001", descricao="A", qtd=2 if divergencias else 1)]
    return lp.Conferencia(sistema, status, lista, lp.comparar(status, lista))


def _conferir(qtbot, tmp_path, monkeypatch, conferencia):
    monkeypatch.setattr(tela_mod.lp_svc, "conferir", lambda _p: conferencia)
    tela = tela_mod.ModuloListaPrecosConferir()
    qtbot.addWidget(tela)
    tela.definir_pasta(str(tmp_path))
    tela._conferir()
    qtbot.waitUntil(lambda: tela.conferencia is not None and not tela.rodando(), timeout=5000)
    return tela


def test_conferir_mostra_divergencias_e_o_aviso_de_valorizada(qt_interface, qtbot, tmp_path, monkeypatch):
    tela = _conferir(qtbot, tmp_path, monkeypatch, _conferencia(tmp_path, valorizada=True))
    assert tela.tabela.topLevelItemCount() == 1
    assert tela.tabela.topLevelItem(0).text(0) == "diferente" and tela.tabela.topLevelItem(0).text(2) == "QTD."
    assert tela.lbl_aviso.text() == tela_mod.t(tela_mod.AVISO_VALORIZADA)
    assert tela.lbl_aviso.property("papel") == "aviso"
    assert tela.btn_atualizar.isEnabled() and tela.btn_abrir.isEnabled()


def test_em_dia_nao_libera_atualizar(qt_interface, qtbot, tmp_path, monkeypatch):
    tela = _conferir(qtbot, tmp_path, monkeypatch, _conferencia(tmp_path, valorizada=False, divergencias=False))
    assert tela.lbl_aviso.text() == tela_mod.t(tela_mod.EM_DIA)
    assert not tela.btn_atualizar.isEnabled()


def test_atualizar_valorizada_pergunta_com_atencao(qt_interface, qtbot, tmp_path, monkeypatch):
    conferencia = _conferencia(tmp_path, valorizada=True)
    tela = _conferir(qtbot, tmp_path, monkeypatch, conferencia)
    perguntas, chamadas = [], []
    respostas = [False, True]

    def perguntar(_titulo, mensagem, **_k):
        perguntas.append(mensagem)
        return respostas.pop(0)

    monkeypatch.setattr(tela, "perguntar_sim_nao", perguntar)
    monkeypatch.setattr(tela_mod.lp_svc, "atualizar", lambda c, **_k: chamadas.append(c))
    tela._atualizar()
    qtbot.waitUntil(lambda: not tela.rodando(), timeout=5000)
    assert chamadas == [] and perguntas[0].startswith("ATENÇÃO")
    tela._atualizar()
    qtbot.waitUntil(lambda: chamadas and not tela.rodando(), timeout=5000)
    assert chamadas == [conferencia]


def test_erro_da_conferencia_aparece_na_tela(qt_interface, qtbot, tmp_path, monkeypatch):
    def falha(_p):
        raise lp.ErroListaDePrecos("a pasta X não tem lista com preço")
    monkeypatch.setattr(tela_mod.lp_svc, "conferir", falha)
    tela = tela_mod.ModuloListaPrecosConferir()
    qtbot.addWidget(tela)
    tela.definir_pasta(str(tmp_path))
    tela._conferir()
    qtbot.waitUntil(lambda: "não tem lista com preço" in tela.lbl_aviso.text(), timeout=5000)
    assert not tela.btn_atualizar.isEnabled()


def test_abrir_a_pasta_usa_o_sistema(qt_interface, qtbot, tmp_path, monkeypatch):
    abertos = []
    monkeypatch.setattr(tela_mod.plataforma, "abrir_no_sistema", abertos.append)
    tela = tela_mod.ModuloListaPrecosConferir()
    qtbot.addWidget(tela)
    tela.definir_pasta(str(tmp_path))
    tela._abrir_pasta()
    assert abertos == [str(tmp_path)]


def test_secao_tem_as_duas_abas_com_um_console(qt_interface, qtbot):
    secao = tela_mod.ModuloListaPrecos()
    qtbot.addWidget(secao)
    assert secao.tela_criar.console is secao.console and secao.tela_conferir.console is secao.console
    assert isinstance(secao.tela_criar, tela_mod.ModuloListaPrecosCriar)
    assert Path(tela_mod.__file__).name == "lista_precos.py"
