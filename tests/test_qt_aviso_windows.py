"""Aviso do Windows fora de foco: fim da tarefa e esperas (2026-10-21, etapa 1b)."""
import os
import threading

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QWidget

from sigft.app_qt import aviso_windows as aviso


class _Mostrados(list):
    """(título, texto) de cada aviso; `na_thread_da_interface`, um bool por aviso."""

    def __init__(self):
        super().__init__()
        self.na_thread_da_interface = []


@pytest.fixture
def mostrados(monkeypatch, tmp_path):
    """O aviso ligado, o SIG-FT fora de foco e o `_mostrar` trocado por uma lista:
    nem com isto o Windows mostra nada num teste."""
    monkeypatch.delenv(aviso.ENV_DESLIGAR, raising=False)
    monkeypatch.setattr(aviso, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    monkeypatch.setattr(aviso, "_em_foco", lambda janela: False)
    lista = _Mostrados()

    def falso(janela, titulo, texto):
        # Guarda onde o aviso saiu: o Qt só aceita a bandeja na thread da interface.
        lista.na_thread_da_interface.append(threading.current_thread() is threading.main_thread())
        lista.append((titulo, texto))
        return True

    monkeypatch.setattr(aviso, "_mostrar", falso)
    return lista


def test_os_testes_rodam_com_o_aviso_desligado():
    assert os.environ.get(aviso.ENV_DESLIGAR) == "1"   # tests/conftest.py


def test_desligado_pelo_ambiente_nunca_mostra(qt_interface, qtbot, monkeypatch):
    chamados = []
    monkeypatch.setattr(aviso, "_mostrar", lambda *a: chamados.append(a) or True)
    monkeypatch.setattr(aviso, "_em_foco", lambda janela: False)
    janela = QWidget()
    qtbot.addWidget(janela)
    assert aviso.avisar(janela, "terminou") is False
    assert chamados == []


def test_fora_de_foco_mostra(qt_interface, qtbot, mostrados):
    janela = QWidget()
    qtbot.addWidget(janela)
    assert aviso.avisar(janela, "Upload duplicadas terminou sem erro nem aviso.")
    assert mostrados == [(aviso.TITULO_FIM, "Upload duplicadas terminou sem erro nem aviso.")]


def test_em_foco_nao_mostra(qt_interface, qtbot, mostrados, monkeypatch):
    monkeypatch.setattr(aviso, "_em_foco", lambda janela: True)
    janela = QWidget()
    qtbot.addWidget(janela)
    assert not aviso.avisar(janela, "x")
    assert mostrados == []


def test_ligado_por_padrao_e_desligar_cala(qt_interface, qtbot, mostrados):
    assert aviso.ligado() is True
    aviso.ligar(False)
    assert aviso.ligado() is False
    janela = QWidget()
    qtbot.addWidget(janela)
    assert not aviso.avisar(janela, "x")


def test_primeira_linha():
    assert aviso.primeira_linha("\n  Faça o login no portal\ne aperte Continuar") == "Faça o login no portal"
    assert len(aviso.primeira_linha("x" * 500)) == aviso.LIMITE_DO_TEXTO
    assert aviso.primeira_linha(None) == ""


def test_sem_bandeja_no_sistema_nao_faz_nada(qt_interface, qtbot, monkeypatch):
    """Sem área de notificação (`isSystemTrayAvailable` falso): calado, sem ícone."""
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: False))
    janela = QWidget()
    qtbot.addWidget(janela)
    assert aviso._mostrar(janela, aviso.TITULO_FIM, "x") is False
    assert getattr(janela, "_bandeja_do_aviso", None) is None


def test_mostrar_acende_o_icone_e_a_volta_ao_sigft_apaga(qt_interface, qtbot, monkeypatch):
    """O ícone da bandeja só fica aceso enquanto há aviso que a pessoa não viu:
    clicar nele (ou no aviso) ou voltar ao SIG-FT o apaga."""
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    mensagens = []
    monkeypatch.setattr(QSystemTrayIcon, "showMessage", lambda self, *a: mensagens.append(a[:2]))
    janela = QWidget()
    qtbot.addWidget(janela)
    assert aviso._mostrar(janela, aviso.TITULO_FIM, "terminou") is True
    bandeja = aviso.bandeja_da(janela)
    assert mensagens == [(aviso.TITULO_FIM, "terminou")]
    assert bandeja.isVisible()
    aviso._ao_mudar_estado(Qt.ApplicationState.ApplicationInactive)
    assert bandeja.isVisible()
    aviso._ao_mudar_estado(Qt.ApplicationState.ApplicationActive)
    assert not bandeja.isVisible()
    aviso._mostrar(janela, aviso.TITULO_FIM, "de novo")
    bandeja.messageClicked.emit()
    assert not bandeja.isVisible()


def test_clicar_no_aviso_traz_a_janela(qt_interface, qtbot, monkeypatch):
    trazidas = []
    monkeypatch.setattr(aviso, "trazer_para_frente", trazidas.append)
    janela = QWidget()
    qtbot.addWidget(janela)
    bandeja = aviso.bandeja_da(janela)
    assert aviso.bandeja_da(janela) is bandeja          # uma por janela
    bandeja.messageClicked.emit()
    assert trazidas == [janela]


def test_em_foco_de_verdade_minimizada_ou_escondida_nao_conta(qt_interface, qtbot):
    """O `_em_foco` real, sem troca. Só os casos negativos: offscreen o
    `applicationState` não fica `ApplicationActive` de forma confiável."""
    minimizada = QWidget()
    qtbot.addWidget(minimizada)
    minimizada.show()
    minimizada.setWindowState(Qt.WindowState.WindowMinimized)
    assert minimizada.isMinimized()
    assert aviso._em_foco(minimizada) is False
    escondida = QWidget()
    qtbot.addWidget(escondida)
    assert aviso._em_foco(escondida) is False


def test_trazer_para_frente_tira_o_minimizado(qt_interface, qtbot):
    janela = QWidget()
    qtbot.addWidget(janela)
    janela.show()
    janela.setWindowState(Qt.WindowState.WindowMinimized)
    aviso.trazer_para_frente(janela)
    assert not janela.isMinimized()


def test_fim_da_tarefa_avisa_com_a_contagem(qt_interface, qtbot, mostrados):
    from sigft.app_qt.widgets.module_frame import ModuleFrame

    class Tela(ModuleFrame):
        def _build_ui(self):
            pass

    tela = Tela(titulo="Upload duplicadas")
    qtbot.addWidget(tela)
    tela.iniciar_tarefa(tela.log, "[Erro] Ficha 4500063671.0001 não encontrada").join(3)
    qtbot.waitUntil(lambda: bool(mostrados), timeout=2000)
    assert mostrados == [(aviso.TITULO_FIM, "Upload duplicadas terminou com 1 erro.")]


def test_defeito_no_resumo_nao_cala_o_aviso(qt_interface, qtbot, mostrados, monkeypatch):
    # 2026-10-21: o resumo e o aviso tinham um try só; o resumo quebrando
    # levava o aviso junto. Cada um tem o seu, e o aviso vem antes.
    from sigft.app import resumo_lote as regras
    from sigft.app_qt.widgets import resumo_lote as janela_mod
    from sigft.app_qt.widgets.module_frame import ModuleFrame

    monkeypatch.delenv(regras.ENV_DESLIGAR, raising=False)

    def quebra(*_a, **_k):
        raise ValueError("defeito de proposito")
    monkeypatch.setattr(janela_mod, "abrir_resumo", quebra)

    class Tela(ModuleFrame):
        def _build_ui(self):
            pass

    tela = Tela(titulo="Upload duplicadas")
    qtbot.addWidget(tela)
    tela.iniciar_tarefa(tela.log, "[Erro] Ficha 4500063671.0001 não encontrada").join(3)
    qtbot.waitUntil(lambda: bool(mostrados), timeout=2000)
    assert mostrados == [(aviso.TITULO_FIM, "Upload duplicadas terminou com 1 erro.")]


def test_fim_da_tarefa_tira_o_modulo_do_titulo(qt_interface, qtbot, mostrados):
    from sigft.app_qt.widgets.module_frame import ModuleFrame

    class Tela(ModuleFrame):
        def _build_ui(self):
            pass

    tela = Tela(titulo="Módulo: Upload duplicadas")
    qtbot.addWidget(tela)
    tela.iniciar_tarefa(tela.log, "tudo certo").join(3)
    qtbot.waitUntil(lambda: bool(mostrados), timeout=2000)
    assert mostrados == [(aviso.TITULO_FIM, "Upload duplicadas terminou sem erro nem aviso.")]


def _tela_de_espera(qtbot):
    from sigft.app_qt.widgets.espera import DialogosDeEspera

    class Tela(DialogosDeEspera, QWidget):
        pass

    tela = Tela()
    qtbot.addWidget(tela)
    return tela


def _aberto(tipo):
    return next(w for w in QApplication.topLevelWidgets() if isinstance(w, tipo) and w.isVisible())


def test_pausa_avisa_com_a_primeira_linha(qt_interface, qtbot, mostrados):
    from sigft.app_qt.widgets import dialogs as qd

    tela = _tela_de_espera(qtbot)
    t = threading.Thread(target=tela.pausar_e_esperar,
                         args=("Faça o login no portal e aperte Continuar.\nDetalhe",), daemon=True)
    t.start()
    qtbot.waitUntil(lambda: bool(mostrados), timeout=2000)
    assert mostrados == [(aviso.TITULO_ESPERA, "Faça o login no portal e aperte Continuar.")]
    assert mostrados.na_thread_da_interface == [True]     # chamada veio do worker
    qtbot.waitUntil(lambda: any(isinstance(w, qd.PausaLoginDialog) and w.isVisible()
                                for w in QApplication.topLevelWidgets()), timeout=2000)
    _aberto(qd.PausaLoginDialog).botao.click()
    t.join(3)


def test_excel_travado_avisa(qt_interface, qtbot, mostrados):
    from sigft.app_qt.widgets import dialogs as qd
    from sigft.app_qt.widgets import espera

    tela = _tela_de_espera(qtbot)
    t = threading.Thread(target=tela.perguntar_retry_excel, daemon=True)
    t.start()
    qtbot.waitUntil(lambda: bool(mostrados), timeout=2000)
    assert mostrados == [(aviso.TITULO_ESPERA, espera.TEXTO_ESPERA_EXCEL)]
    assert mostrados.na_thread_da_interface == [True]     # chamada veio do worker
    qtbot.waitUntil(lambda: any(isinstance(w, qd.RetryLockDialog) and w.isVisible()
                                for w in QApplication.topLevelWidgets()), timeout=2000)
    _aberto(qd.RetryLockDialog).close()
    t.join(3)


def test_sim_nao_avisa(qt_interface, qtbot, mostrados, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a: QMessageBox.StandardButton.Yes))
    tela = _tela_de_espera(qtbot)
    assert tela.perguntar_sim_nao("Gravar relatório", "Gravar?") is True
    assert mostrados == [(aviso.TITULO_ESPERA, "Gravar relatório: responda Sim ou Não.")]


def test_textos_do_aviso_sem_travessao():
    from sigft.app_qt.widgets import espera

    for texto in (aviso.TITULO_FIM, aviso.TITULO_ESPERA, espera.TEXTO_ESPERA_EXCEL,
                  espera.TEXTO_ESPERA_TRAVADOS):
        assert "—" not in texto and "–" not in texto


def test_caixa_da_home_liga_e_desliga(qt_interface, qtbot, tmp_path, monkeypatch):
    from sigft.app_qt.views import home as home_mod

    class Controller:
        api_keys: dict = {}

    monkeypatch.setattr(aviso, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    tela = home_mod.HomeView(controller=Controller())
    qtbot.addWidget(tela)
    assert tela.caixa_avisos_windows.text() == home_mod.TEXTO_AVISOS_WINDOWS
    assert tela.caixa_avisos_windows.isChecked()
    tela.caixa_avisos_windows.setChecked(False)
    assert aviso.ligado() is False


def test_o_smoke_desliga_o_aviso(monkeypatch):
    """O `--smoke` (Release e CI) nunca avisa, nem numa máquina com bandeja."""
    from sigft.app_qt import main as qmain

    class Parou(BaseException):
        pass

    def parar(*_a):
        raise Parou

    monkeypatch.delenv(aviso.ENV_DESLIGAR, raising=False)
    monkeypatch.setattr(qmain, "_preparar_qt", parar)
    with pytest.raises(Parou):
        qmain._smoke()
    assert os.environ.get(aviso.ENV_DESLIGAR) == "1"
