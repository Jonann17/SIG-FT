"""Tela "Upload de Fotos" (2026-10-30). A regra está em `test_upload_fotos.py`;
aqui, só a conversa da tela com a pessoa e com o robô."""
import threading

import pytest

from sigft.app_qt.views import upload_fotos as tela_mod
from sigft.services import upload_fotos as svc


class RoboFalso:
    def __init__(self):
        self.passos = []

    def iniciar_driver(self):
        self.passos.append("driver")

    def abrir_portal(self):
        self.passos.append("portal")

    def processar(self, fichas, modo, perguntar, callback_log=None):
        self.passos.append(("processar", len(fichas), modo))
        return [svc.ResultadoDaFicha(p, q, ok=True) for p, q, _c in fichas]

    def fechar_driver(self):
        self.passos.append("fechou")


@pytest.fixture
def tela(qt_interface, qtbot, monkeypatch):
    t = tela_mod.ModuloUploadFotos()
    qtbot.addWidget(t)
    t.pasta, t.caminho_status = "/fotos", "/status.xlsx"
    t.avisos, t.perguntas, t.resposta = [], [], True
    t.robo = RoboFalso()
    t.threads_da_leitura = []
    monkeypatch.setattr(t, "avisar", lambda ti, m, tipo="info", **_k: t.avisos.append((tipo, m)))
    monkeypatch.setattr(t, "pausar_e_esperar", lambda *_a, **_k: None)

    def perguntar(ti, m, **_k):
        t.perguntas.append(m)
        return t.resposta
    monkeypatch.setattr(t, "perguntar_sim_nao", perguntar)

    def ler_codigos(_caminho):
        t.threads_da_leitura.append(threading.current_thread() is threading.main_thread())
        return ["4500063671.0071"]
    monkeypatch.setattr(svc, "ler_codigos", ler_codigos)
    monkeypatch.setattr(svc, "agrupar_fotos", lambda _p: ({"0071": ["/fotos/0071.jpg"]}, []))
    t.esperas_do_robo = []

    def criar_robo(esperas=None):
        t.esperas_do_robo.append(esperas)
        return t.robo
    monkeypatch.setattr(svc, "UploadFotosAutomation", criar_robo)
    monkeypatch.setattr(svc, "marcar_status", lambda *_a, **_k: (1, "1 linha(s) marcada(s) no _STATUS_PMIB."))
    # A janela de escolha das fichas: por padrão, a pessoa marca todas.
    t.escolha = None
    monkeypatch.setattr(t, "_escolher_fichas", lambda fichas: fichas if t.escolha is None else t.escolha(fichas))
    return t


def test_a_planilha_e_lida_fora_da_thread_da_interface(tela, qtbot):
    # Lida na thread da interface, uma planilha grande congelava a janela.
    tela.btn_run.click()
    qtbot.waitUntil(lambda: "fechou" in tela.robo.passos, timeout=3000)

    assert tela.threads_da_leitura == [False]
    assert ("processar", 1, svc.MODO_SUBSTITUIR) in tela.robo.passos
    assert "1 ficha(s) e 1 foto(s)" in tela.perguntas[0]


def test_desistir_no_comecar_nao_abre_o_navegador(tela, qtbot):
    tela.resposta = False

    tela.btn_run.click()
    qtbot.waitUntil(tela.btn_run.isEnabled, timeout=3000)

    assert tela.perguntas and tela.robo.passos == []


def test_a_velocidade_do_portal_chega_ao_robo(tela, qtbot):
    # Portal lento (2026-11-03): "Lento" é o padrão, e "Muito lento" espera 4x.
    assert tela.menu_velocidade.currentIndex() == 1
    tela.menu_velocidade.setCurrentIndex(2)

    tela.btn_run.click()
    qtbot.waitUntil(lambda: "fechou" in tela.robo.passos, timeout=3000)

    assert tela.esperas_do_robo == [svc.Esperas(fator=4)]


# --- escolher as fichas (2026-11-03) ------------------------------------------
def _duas_fichas(monkeypatch):
    monkeypatch.setattr(svc, "agrupar_fotos", lambda _p: (
        {"0071": ["/fotos/0071.jpg"], "0072": ["/fotos/0072.jpg", "/fotos/0072a.jpg"]}, []))
    monkeypatch.setattr(svc, "ler_codigos", lambda _c: ["4500063671.0071", "4500063671.0072"])


def test_so_as_fichas_escolhidas_vao_para_o_robo(tela, qtbot, monkeypatch):
    _duas_fichas(monkeypatch)
    tela.escolha = lambda fichas: [fichas[1]]

    tela.btn_run.click()
    qtbot.waitUntil(lambda: "fechou" in tela.robo.passos, timeout=3000)

    assert ("processar", 1, svc.MODO_SUBSTITUIR) in tela.robo.passos
    assert "1 ficha(s) e 2 foto(s)" in tela.perguntas[0]


def test_nenhuma_ficha_escolhida_nao_abre_o_navegador(tela, qtbot, monkeypatch):
    _duas_fichas(monkeypatch)
    tela.escolha = lambda _fichas: []

    tela.btn_run.click()
    qtbot.waitUntil(tela.btn_run.isEnabled, timeout=3000)

    assert tela.robo.passos == [] and tela.perguntas == []


def test_a_janela_das_fichas_tem_selecionar_todos(tela):
    fichas = [("4500063671.0071", "0071", ["a"]), ("4500063671.0072", "0072", ["b", "c"])]
    escolhidas = []

    dialogo = tela._dialogo_de_fichas(fichas, escolhidas.extend)
    assert "4500063671.0072" in dialogo.listbox.item(1).text()
    dialogo.botao_todos.click()
    dialogo.botao_confirmar.click()

    assert escolhidas == [0, 1]


# --- a prévia do lote (2026-11-04) ---------------------------------------------
def test_previa_vazia_explica_o_que_fazer(qt_interface, qtbot):
    t = tela_mod.ModuloUploadFotos()
    qtbot.addWidget(t)
    assert t.rotulo_previa.text() == tela_mod.TEXTO_PREVIA_VAZIA
    assert not t.tabela_previa.isVisibleTo(t)


def test_previa_mostra_as_fichas_e_os_problemas(tela, qtbot, monkeypatch):
    monkeypatch.setattr(svc, "agrupar_fotos", lambda _p: (
        {"0071": ["/fotos/0071.jpg", "/fotos/0071a.jpg"], "9999": ["/fotos/9999.jpg"]}, ["leia-me.txt"]))
    tela.atualizar_previa()
    qtbot.waitUntil(lambda: tela.numeros["fotos"].text() == "3", timeout=3000)
    assert tela.numeros["fora"].text() == "1"
    assert tela.numeros["fichas"].text() == "1"
    assert tela.numeros["sem_ficha"].text() == "1"
    assert tela.tabela_previa.topLevelItemCount() == 1
    assert tela.tabela_previa.topLevelItem(0).text(2) == "0071.jpg, 0071a.jpg"
    assert "9999" in tela.rotulo_previa.text() and "leia-me.txt" in tela.rotulo_previa.text()
    assert "1" in tela.btn_run.text()


def test_previa_com_erro_de_leitura_diz_o_motivo(tela, qtbot, monkeypatch):
    def quebra(_c):
        raise ValueError("a coluna 'CÓDIGO PMIB' não foi encontrada")
    monkeypatch.setattr(svc, "ler_codigos", quebra)
    tela.atualizar_previa()
    qtbot.waitUntil(lambda: "não foi encontrada" in tela.rotulo_previa.text(), timeout=3000)
