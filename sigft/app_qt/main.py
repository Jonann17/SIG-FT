"""Ponto de entrada da interface Qt:  python -m sigft.app_qt.main

Mesma janela de hoje (barra lateral + conteúdo, splash enquanto os backends
carregam), com três diferenças deliberadas, todas do desenho de 2026-10-07:
* as telas são criadas na PRIMEIRA visita, não as 13 na abertura;
* a splash não tem pausas artificiais (eram ~2 s por abertura);
* tela ainda não migrada mostra um aviso em vez de não existir.
"""
from __future__ import annotations

if __name__ == "__main__":
    from sigft.core.python_minimo import exigir_python_minimo

    exigir_python_minimo()

import json
import os
import sys
import threading
import time
import traceback

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from sigft import _build_info
from sigft.app import backends, theme
from sigft.app_qt import catalogo, estilo, interface
from sigft.app_qt.views.home import HomeView
from sigft.app_qt.views.nao_migrada import TelaNaoMigrada
from sigft.core import instancia

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Registro das telas migradas: nome -> fábrica(parent, controller). Cada plano
# de etapa acrescenta as suas aqui.
TELAS = {
    "Home": lambda parent, controller: HomeView(parent, controller),
}


def resource_path(relativo: str) -> str:
    base = getattr(sys, "_MEIPASS", _RAIZ)
    return os.path.join(base, relativo)


def _arquivo_de_chaves() -> str:
    from sigft.config import caminho_config

    return caminho_config()


class SIG_FT_App(QMainWindow):  # noqa: N801 -- mesmo nome da interface atual
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"SIG-FT v{_build_info.VERSAO} - GE Vernova")
        self.resize(1280, 850)
        icone = resource_path(os.path.join("assets", "icone-sig-ft.png"))
        if os.path.exists(icone):
            self.setWindowIcon(QIcon(icone))

        self.api_keys: dict = {}
        self.load_keys()

        central = QWidget()
        linha = QHBoxLayout(central)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(0)
        linha.addWidget(self._montar_sidebar())
        self.pilha = QStackedWidget(objectName="conteudo")
        linha.addWidget(self.pilha, 1)
        self.setCentralWidget(central)

        self.telas: dict[str, QWidget] = {}
        self.show_frame("Home")

    # -- barra lateral --------------------------------------------------------
    def _montar_sidebar(self) -> QScrollArea:
        area = QScrollArea(objectName="sidebar")
        area.setFixedWidth(270)
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        interno = QWidget(objectName="sidebar_interno")
        lay = QVBoxLayout(interno)
        lay.setContentsMargins(12, 26, 12, 12)
        lay.setSpacing(estilo.ESPACO_MENU)

        logo = QLabel()
        caminho_logo = resource_path(os.path.join("assets", "logo.png"))
        if os.path.exists(caminho_logo):
            logo.setPixmap(QPixmap(caminho_logo).scaledToWidth(
                180, Qt.TransformationMode.SmoothTransformation))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(logo)
        nome = QLabel("SIG-FT System", objectName="app_nome")
        nome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(nome)
        lay.addSpacing(22)
        home = QPushButton(estilo.mono("  🏠  Home"), objectName="home")
        home.clicked.connect(self.show_home)
        lay.addWidget(home)
        lay.addSpacing(6)

        self.botoes_menu: dict[str, QPushButton] = {}
        for item in catalogo.MENU:
            if item[0] == "secao":
                lay.addSpacing(20)
                lay.addWidget(QLabel(item[1].upper(), objectName="secao"))
                lay.addSpacing(5)
                continue
            _tipo, texto, alvo = item
            botao = QPushButton(f"  {texto}")
            botao.setProperty("menu", True)
            botao.setEnabled(alvo not in catalogo.TELAS_BLOQUEADAS)
            botao.clicked.connect(lambda _=False, a=alvo: self.show_frame(a))
            self.botoes_menu[alvo] = botao
            lay.addWidget(botao)
        lay.addStretch()
        area.setWidget(interno)
        return area

    # -- navegação ------------------------------------------------------------
    def show_frame(self, nome: str) -> None:
        """Funil único de navegação: barra lateral e cards passam por aqui."""
        if nome in catalogo.TELAS_BLOQUEADAS:
            return
        tela = self.telas.get(nome)
        if tela is None:
            fabrica = TELAS.get(nome)
            tela = fabrica(self.pilha, self) if fabrica else TelaNaoMigrada(nome)
            self.telas[nome] = tela
            self.pilha.addWidget(tela)
        self.pilha.setCurrentWidget(tela)

    def show_modulo(self, nome: str) -> None:
        self.show_frame(nome)

    def show_home(self) -> None:
        self.show_frame("Home")

    # -- chaves de API ----------------------------------------------------------
    def load_keys(self) -> None:
        from sigft.config import carregar_chaves

        self.api_keys = carregar_chaves(_arquivo_de_chaves())

    def save_keys(self, novas: dict) -> None:
        """Lê o JSON inteiro, troca só as chaves de API e grava de forma atômica.

        Atômica (arquivo temporário + `os.replace`): um corte no meio da
        gravação não pode deixar o `api_config.json` pela metade, que faria as
        chaves "sumirem" na próxima abertura.
        """
        arquivo = _arquivo_de_chaves()
        dados: dict = {}
        try:
            with open(arquivo, encoding="utf-8") as f:
                carregado = json.load(f)
            if isinstance(carregado, dict):
                dados = carregado
        except (OSError, ValueError):
            dados = {}
        dados.update(novas)
        temporario = arquivo + ".tmp"
        with open(temporario, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=4)
        os.replace(temporario, arquivo)
        self.api_keys = {**self.api_keys, **novas}

    def get_key(self, key_id: str) -> str:
        return self.api_keys.get(key_id) or ""

    # -- fechar -------------------------------------------------------------------
    def closeEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        if instancia.tarefas_em_andamento():
            resposta = QMessageBox.question(
                self, "Fechar o SIG-FT", catalogo.MSG_TAREFA_EM_ANDAMENTO,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if resposta != QMessageBox.StandardButton.Yes:
                evento.ignore()
                return
        evento.accept()


class SplashScreen(QWidget):
    """A splash de hoje, sem as pausas artificiais: o progresso é o real."""

    pronta = Signal()

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.SplashScreen)
        self.setFixedSize(500, 350)
        self.setObjectName("conteudo")
        self.setStyleSheet(f"background: {theme.COLORS['background']};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(50, 50, 50, 20)
        logo = QLabel()
        caminho = resource_path(os.path.join("assets", "logo.png"))
        if os.path.exists(caminho):
            logo.setPixmap(QPixmap(caminho).scaledToWidth(
                300, Qt.TransformationMode.SmoothTransformation))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(logo)
        titulo = QLabel("SIG-FT System")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        titulo.setStyleSheet("color: gray; font-size: 16px;")
        lay.addWidget(titulo)
        lay.addStretch()
        self.status = QLabel("Iniciando...")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet(f"color: {theme.COLORS['accent']}; font-size: 12px;")
        lay.addWidget(self.status)
        self.barra = QProgressBar()
        self.barra.setRange(0, 1000)
        self.barra.setTextVisible(False)
        self.barra.setStyleSheet(f"QProgressBar::chunk {{ background: {theme.COLORS['accent']}; }}")
        lay.addWidget(self.barra)

    def carregar(self) -> None:
        threading.Thread(target=self._carregar, name="splash", daemon=True).start()

    def _carregar(self) -> None:
        inicio = time.time()

        def progredir(exibido, fracao):
            interface.na_interface(self.status.setText, f"Carregando: {exibido}...")
            interface.na_interface(self.barra.setValue, int(fracao * 1000))

        def falhar(exibido, erro):
            print(f"Erro ao carregar {exibido}: {erro}")
            interface.na_interface(self.status.setText, f"Erro em {exibido}")

        try:
            backends.carregar_todos(ao_progredir=progredir, ao_falhar=falhar)
            interface.na_interface(self.status.setText, f"Concluído em {time.time() - inicio:.1f}s")
        except BaseException:  # noqa: BLE001 -- inclui SystemExit de um backend no import
            traceback.print_exc()
        finally:
            # Sempre segue adiante: a splash que não some deixa o processo vivo
            # e sem janela. Tela com backend ausente mostra o motivo sozinha
            # (`backends.falhas`).
            interface.na_interface(self.pronta.emit)


def _preparar_qt() -> QApplication:
    app = QApplication.instance() or QApplication(sys.argv)
    interface.instalar()
    estilo.carregar_fontes()
    app.setStyleSheet(estilo.folha_de_estilo())
    return app


def main() -> None:
    instancia.preparar()
    app = _preparar_qt()
    splash = SplashScreen()
    janela: list[SIG_FT_App] = []

    def abrir_principal() -> None:
        try:
            principal = SIG_FT_App()
        except Exception as erro:  # noqa: BLE001 -- vira aviso, e não fantasma
            traceback.print_exception(erro)
            QMessageBox.critical(None, "SIG-FT", catalogo.MSG_ABERTURA_FALHOU.format(
                erro=f"{type(erro).__name__}: {erro}"))
            instancia.encerrar(1)
            return
        janela.append(principal)
        principal.show()
        splash.close()

    splash.pronta.connect(abrir_principal)
    splash.show()
    splash.carregar()
    app.exec()
    instancia.encerrar(0)


def _smoke() -> int:
    """Monta a janela principal e sai, sem laço de eventos (para o CI)."""
    avisos: list[str] = []
    try:
        _preparar_qt()
        backends.carregar_todos(
            ao_falhar=lambda nome, erro: avisos.append(
                f"[smoke] AVISO: o backend '{nome}' nao carregou: "
                f"{type(erro).__name__}: {erro}"))
        janela = SIG_FT_App()
        janela.close()
    except Exception as erro:  # noqa: BLE001 -- é o que se quer relatar
        for aviso in avisos:
            print(aviso)
        print(f"[smoke] FALHOU: {type(erro).__name__}: {erro}")
        traceback.print_exc()
        return 1
    for aviso in avisos:
        print(aviso)
    print("[smoke] a janela principal Qt montou e fechou sem erro.")
    return 0


def executar_da_linha_de_comando() -> None:
    if "--smoke" in sys.argv:
        sys.exit(_smoke())
    main()


if __name__ == "__main__":
    executar_da_linha_de_comando()
