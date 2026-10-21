"""A janela de resumo do fim do lote e o gancho no ModuleFrame (2026-10-21, etapa 1b)."""
import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from sigft.app import resumo_lote as r
from sigft.app_qt import estilo, tema
from sigft.app_qt.widgets import resumo_lote as janela_mod
from sigft.app_qt.widgets.module_frame import ModuleFrame


class Tela(ModuleFrame):
    def _build_ui(self):
        pass


@pytest.fixture
def abertos(monkeypatch):
    lista = []
    monkeypatch.setattr(janela_mod, "abrir_resumo",
                        lambda tela, titulo, pares: lista.append((titulo, pares)))
    return lista


def _rodar(qtbot, tela, linhas):
    def alvo():
        for msg, nivel in linhas:
            tela.log(msg, nivel)
    tela.iniciar_tarefa(alvo).join(3)
    qtbot.waitUntil(lambda: tela._tarefas_rodando == 0, timeout=2000)


def test_tarefa_com_erro_abre_o_resumo_so_com_as_linhas_dela(qt_interface, qtbot, monkeypatch, abertos):
    monkeypatch.delenv(r.ENV_DESLIGAR)
    tela = Tela(titulo="Upload duplicadas")
    qtbot.addWidget(tela)
    tela.log("[Erro] de uma tarefa anterior")
    _rodar(qtbot, tela, [("começou", "info"), ("[Erro] Ficha 4500063671.0001 não encontrada", "info")])
    assert abertos == [("Upload duplicadas", [("começou", "info"),
                                              ("[Erro] Ficha 4500063671.0001 não encontrada", "erro")])]


def test_tarefa_limpa_nao_abre(qt_interface, qtbot, monkeypatch, abertos):
    monkeypatch.delenv(r.ENV_DESLIGAR)
    tela = Tela(titulo="x")
    qtbot.addWidget(tela)
    _rodar(qtbot, tela, [("tudo certo", "info")])
    assert abertos == []


def test_nos_testes_nao_abre_sem_pedir(qt_interface, qtbot, abertos):
    tela = Tela(titulo="x")
    qtbot.addWidget(tela)
    _rodar(qtbot, tela, [("[ERRO] ruim", "info")])
    assert abertos == []


def test_defeito_no_resumo_nao_prende_o_fim_da_tarefa(qt_interface, qtbot, monkeypatch):
    monkeypatch.delenv(r.ENV_DESLIGAR)

    def quebra(*_a):
        raise ValueError("defeito de proposito")
    monkeypatch.setattr(janela_mod, "abrir_resumo", quebra)
    tela = Tela(titulo="x")
    qtbot.addWidget(tela)
    _rodar(qtbot, tela, [("[ERRO] ruim", "info")])
    assert tela._tarefas_rodando == 0


def test_janela_agrupa_copia_e_abre_o_log(qt_interface, qtbot, monkeypatch, tmp_path):
    abertos_no_sistema = []
    monkeypatch.setattr(janela_mod.plataforma, "abrir_no_sistema", abertos_no_sistema.append)
    monkeypatch.setattr(janela_mod, "pasta_logs", lambda: tmp_path)
    pares = [("tudo certo", "info"), ("[Erro] Ficha 4500063671.0001 não encontrada", "erro"),
             ("[Aviso] sem código", "aviso")]
    j = janela_mod.JanelaResumoDoLote(None, "Upload duplicadas", pares)
    qtbot.addWidget(j)
    assert j.windowTitle() == "Resumo: Upload duplicadas"
    assert j.rotulo.text() == "Terminou com 1 erro e 1 aviso."
    topo = [j.arvore.topLevelItem(i).text(0) for i in range(j.arvore.topLevelItemCount())]
    assert topo == ["4500063671.0001 (1)", "Sem código PMIB (1)"]
    j.botao_copiar.click()
    assert QApplication.clipboard().text() == r.texto_para_copiar("Upload duplicadas", r.agrupar(pares))
    assert j.botao_copiar.text() == janela_mod.TEXTO_COPIADO
    j.botao_log.click()
    assert len(abertos_no_sistema) == 1
    assert abertos_no_sistema[0].parent == tmp_path / janela_mod.PASTA_DOS_RESUMOS
    assert "> tudo certo" in abertos_no_sistema[0].read_text(encoding="utf-8")


def test_cor_das_linhas_segue_o_tema(qt_interface, qtbot, monkeypatch):
    monkeypatch.setattr(estilo, "TEMA_ATUAL", "escuro")
    j = janela_mod.JanelaResumoDoLote(None, "x", [("[Erro] a", "erro"), ("[Aviso] b", "aviso")])
    qtbot.addWidget(j)
    grupo = j.arvore.topLevelItem(0)

    def cores():
        return [grupo.child(i).foreground(0).color().name() for i in range(grupo.childCount())]
    assert cores() == [QColor(estilo.cor_do_papel("perigo")).name(),
                       QColor(estilo.cor_do_papel("aviso")).name()]
    monkeypatch.setattr(estilo, "TEMA_ATUAL", "claro")
    tema.mudou.emit("claro")
    assert cores() == [QColor(estilo.cor_do_papel("perigo")).name(),
                       QColor(estilo.cor_do_papel("aviso")).name()]


def test_abrir_resumo_mostra_a_janela(qt_interface, qtbot):
    tela = Tela(titulo="x")
    qtbot.addWidget(tela)
    j = janela_mod.abrir_resumo(tela, "x", [("[Erro] a", "erro")])
    assert j.isVisible()
    j.close()
