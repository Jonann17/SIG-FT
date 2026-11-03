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
    monkeypatch.setattr(svc, "UploadFotosAutomation", lambda: t.robo)
    monkeypatch.setattr(svc, "marcar_status", lambda *_a, **_k: (1, "1 linha(s) marcada(s) no _STATUS_PMIB."))
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
