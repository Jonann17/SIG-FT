"""A tela Conferência de Revisões (Qt). Os serviços são dublês: a regra e os
downloads têm os testes deles em `test_conferencia_revisoes.py`. Desenho:
`docs/superpowers/specs/2026-10-26-aconex-ao-vivo-design.md`, §5.5.
"""
from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path

import pytest

from sigft.app_qt import catalogo
from sigft.app_qt import main as qmain
from sigft.app_qt.views import conferencia_revisoes as tela_mod
from sigft.core import prefs
from sigft.core.aconex.cliente import ErroAconex
from sigft.core.aconex.credenciais import PREFERENCIA_PERFIL, PerfilAconex
from sigft.core.aconex.diagnostico import Sonda
from sigft.services import conferencia_revisoes as svc

ANA = PerfilAconex("Ana", "B", "2", "y")
LUAN = PerfilAconex("Luan Cozer", "A", "1", "s3gr3d0")
AVISO_SEM_CONEXAO = "Sem conexão com o Aconex: as listas aparecem, mas nada foi baixado."


def _lista(codigo, status_real="Aprovado"):
    return svc.ListaNaMapeadora(codigo, "0B", "Em Processo", status_real, "0", f"{codigo}_STATUS_PMIB.xlsx")


class _Servico:
    """Dublê de `services/conferencia_revisoes`: devolve a conferência pronta e guarda os downloads."""

    def __init__(self, pasta: Path):
        self.conferencia = svc.Conferencia([
            svc.ItemConferencia(_lista("#A"), "aprovada", pasta),
            svc.ItemConferencia(_lista("#B"), "aprovada", pasta),
            svc.ItemConferencia(_lista("#C", "Em Processo"), "em_processo", pasta),
            svc.ItemConferencia(_lista("#D", "Cancelado"), "outros", None, "_STATUS_PMIB não encontrado"),
        ], em_dia=5, sem_status_pmib=2)
        self.clientes = []

    def ler_mapeadora(self, caminho):
        return svc.Mapeadora(Path(caminho), datetime.fromtimestamp(os.path.getmtime(caminho)),
                             [item.lista for item in self.conferencia.itens])

    def conferir(self, mapeadora, pasta_raiz):
        return self.conferencia

    def baixar(self, conferencia, cliente, *, log_cb, progress_cb=None, cancelado_cb=None):
        self.clientes.append(cliente)
        return [svc.Download("#A", "0C", Path("x.pdf"), "baixado", "mapeadora desatualizada: o Aconex está na 0C")]


class _Cliente:
    criados: list = []

    def __init__(self, perfil, **_kw):
        self.perfil = perfil
        _Cliente.criados.append(perfil.nome)

    def conectar(self):
        pass


class _ClienteRecusado(_Cliente):
    def conectar(self):
        raise ErroAconex("O Aconex recusou as credenciais do perfil Luan Cozer (HTTP 401).")


@pytest.fixture
def mapeadora(tmp_path):
    caminho = tmp_path / "Mapeamento Listas de Sobressalentes.xlsx"
    caminho.write_bytes(b"planilha")
    prefs.remember_file(prefs.CHAVE_MAPEAMENTO, str(caminho))
    return caminho


@pytest.fixture
def servico(monkeypatch, tmp_path):
    falso = _Servico(tmp_path)
    for nome in ("ler_mapeadora", "conferir", "baixar"):
        monkeypatch.setattr(tela_mod.conferencia_svc, nome, getattr(falso, nome))
    monkeypatch.setattr(tela_mod, "ClienteAconex", _Cliente)
    _Cliente.criados = []
    return falso


@pytest.fixture
def tela(qt_interface, qtbot, mapeadora, servico, monkeypatch):
    monkeypatch.setattr(tela_mod, "ler_perfis", lambda: [LUAN])
    t = tela_mod.ModuloConferenciaRevisoes()
    qtbot.addWidget(t)
    return t


def _conferir(tela, qtbot, esperar):
    tela.btn_conferir.click()
    qtbot.waitUntil(lambda: esperar in tela.console.toPlainText(), timeout=5000)
    qtbot.waitUntil(tela.btn_conferir.isEnabled, timeout=5000)


def test_e_aba_do_pmib_manager_e_nao_tela_do_menu():
    # Correção do Luan (27/10): a Conferência mora numa aba do PMIB Manager
    # (`views/gestao_sobressalentes.py`, testada em `test_qt_tela_gestao_sobressalentes.py`).
    assert "ConferenciaRevisoes" not in qmain.TELAS
    assert all(item[-1] != "ConferenciaRevisoes" for item in catalogo.MENU)


def test_guarda_a_ultima_conferencia_para_a_revisao_no_amp(tela, qtbot, servico, tmp_path):
    assert tela.ultima is None
    tela.pasta_raiz = str(tmp_path)
    _conferir(tela, qtbot, "lista(s) com divergência")
    qtbot.waitUntil(lambda: tela.ultima is not None and bool(tela.ultima.downloads), timeout=5000)
    assert tela.ultima.conferencia is servico.conferencia
    assert tela.ultima.mapeadora.caminho.name == "Mapeamento Listas de Sobressalentes.xlsx"
    assert tela.ultima.pasta_raiz == tmp_path
    assert [d.codigo for d in tela.ultima.downloads] == ["#A"]


def test_comeca_com_a_mapeadora_e_a_pasta_do_gestao(qt_interface, qtbot, mapeadora, servico, tmp_path):
    raiz = tmp_path / "raiz"
    raiz.mkdir()
    prefs.remember_dir("pmib_manager.pasta_raiz", "pasta", str(raiz))
    t = tela_mod.ModuloConferenciaRevisoes()
    qtbot.addWidget(t)
    assert t.caminho_mapeadora == str(mapeadora)
    assert t.pasta_raiz == str(raiz)


def test_mostra_os_totais_por_categoria(tela, qtbot, servico):
    # 2026-10-27: as categorias são `widgets/abas.Abas`, a convenção do app (a folha não
    # tem regra de QTabWidget, e o nome das abas sumia no tema escuro); a contagem fica
    # nos totais.
    from sigft.app_qt.widgets.abas import Abas

    _conferir(tela, qtbot, "lista(s) com divergência")
    assert isinstance(tela.abas, Abas)
    assert list(tela.abas.abas) == ["Aprovadas", "Em processo", "Não aprovadas", "Outros"]
    assert tela.abas.get() == "Aprovadas"
    assert tela.lbl_totais.text() == ("Aprovadas: 2  ·  Em processo: 1  ·  Não aprovadas: 0  ·  Outros: 1  ·  "
                                      "Em dia: 5  ·  Sem _STATUS_PMIB: 2")
    aprovadas = tela.tabelas["aprovada"]
    assert aprovadas.topLevelItemCount() == 2
    assert [aprovadas.topLevelItem(0).text(i) for i in range(5)] == ["#A", "0", "0B", "Em Processo", "Aprovado"]
    assert tela.tabelas["outros"].topLevelItem(0).text(5) == "_STATUS_PMIB não encontrado"
    # A lista com pasta tem o botão "Abrir Pasta"; a sem pasta, não (2026-11-04).
    assert aprovadas.itemWidget(aprovadas.topLevelItem(0), tela_mod.COLUNA_PASTA).text() == "Abrir Pasta"
    assert tela.tabelas["outros"].itemWidget(tela.tabelas["outros"].topLevelItem(0), tela_mod.COLUNA_PASTA) is None


def test_com_perfil_baixa_e_mostra_o_pdf(tela, qtbot, servico):
    _conferir(tela, qtbot, "lista(s) com divergência")
    qtbot.waitUntil(lambda: "baixado" in tela.tabelas["aprovada"].topLevelItem(0).text(5), timeout=5000)
    assert tela.tabelas["aprovada"].topLevelItem(0).text(5).startswith("[0C] baixado")
    assert _Cliente.criados == ["Luan Cozer"] and len(servico.clientes) == 1


def test_sem_perfil_nao_baixa_e_avisa(tela, qtbot, servico, monkeypatch):
    monkeypatch.setattr(tela_mod, "ler_perfis", lambda: [])
    _conferir(tela, qtbot, AVISO_SEM_CONEXAO)
    assert servico.clientes == []
    assert tela.tabelas["aprovada"].topLevelItemCount() == 2


def test_erro_no_login_avisa_e_nao_baixa(tela, qtbot, servico, monkeypatch):
    monkeypatch.setattr(tela_mod, "ClienteAconex", _ClienteRecusado)
    _conferir(tela, qtbot, AVISO_SEM_CONEXAO)
    assert "HTTP 401" in tela.console.toPlainText()
    assert servico.clientes == []


def test_dois_perfis_pergunta_e_grava_a_escolha(tela, qtbot, servico, monkeypatch):
    monkeypatch.setattr(tela_mod, "ler_perfis", lambda: [ANA, LUAN])
    perguntas = []

    def escolher(pai, titulo, texto, nomes, *a, **k):
        perguntas.append(list(nomes))
        return "Luan Cozer", True

    monkeypatch.setattr(tela_mod.QInputDialog, "getItem", staticmethod(escolher))
    _conferir(tela, qtbot, "lista(s) com divergência")
    assert perguntas == [["Ana", "Luan Cozer"]]
    assert prefs.ler_preferencia(PREFERENCIA_PERFIL, "") == "Luan Cozer"
    assert _Cliente.criados == ["Luan Cozer"]


def test_aviso_de_mapeadora_antiga(qt_interface, qtbot, mapeadora, servico, tela):
    assert tela.lbl_salva_em.text().startswith("Mapeadora salva em ")
    assert tela.lbl_antiga.isHidden()
    ontem = time.time() - 2 * 24 * 3600
    os.utime(mapeadora, (ontem, ontem))
    antiga = tela_mod.ModuloConferenciaRevisoes()
    qtbot.addWidget(antiga)
    assert antiga.lbl_salva_em.text() == "Mapeadora salva em " + datetime.fromtimestamp(ontem).strftime("%d/%m/%Y %H:%M")
    assert not antiga.lbl_antiga.isHidden()
    assert antiga.lbl_antiga.text() == ("A mapeadora não foi atualizada hoje. Rode o Gestão PMIB antes "
                                        "para ver as revisões mais recentes.")


def test_testar_conexao_escreve_as_sondas(tela, qtbot, servico, monkeypatch):
    sondados = []

    def sondar(cliente, codigo):
        sondados.append((cliente.perfil.nome, codigo))
        return [Sonda("Login no Aconex", True, "token recebido"),
                Sonda("Busca exata do código, com histórico", False, "nenhum documento")]

    monkeypatch.setattr(tela_mod, "sondar", sondar)
    tela.btn_testar.click()
    qtbot.waitUntil(lambda: "FALHOU  Busca exata do código" in tela.console.toPlainText(), timeout=5000)
    assert "OK      Login no Aconex: token recebido" in tela.console.toPlainText()
    assert sondados == [("Luan Cozer", "#A")]
