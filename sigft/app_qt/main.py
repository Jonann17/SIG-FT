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

from dotenv import load_dotenv
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from sigft import _build_info
from sigft.app import backends, theme
from sigft.app_qt import atualizacao, catalogo, estilo, interface
from sigft.app_qt.views.aplicacao_lmr import ModuloAplicacaoLMR
from sigft.app_qt.views.home import HomeView
from sigft.app_qt.views.nao_migrada import TelaComErro, TelaNaoMigrada
from sigft.app_qt.views.translator import ModuloTranslator
from sigft.core import instancia
from sigft.core.saida_log import desviar_saida_para_arquivo

# Sem console (o .exe), `print` e traceback vão para `logs/sigft.log`: é o canal
# de diagnóstico da primeira execução em máquina nova. Na mesma posição do app
# CustomTkinter -- no import, antes de qualquer coisa imprimir.
desviar_saida_para_arquivo()

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# As telas das etapas 3 a 5 importam na PRIMEIRA visita, dentro da fábrica:
# abrir o app não paga o import de todas, e uma tela que não importa (falta
# uma dependência) vira a tela de erro DELA em `show_frame`, em vez de impedir
# a janela de abrir. O import fica escrito por extenso (não `importlib`) para o
# PyInstaller enxergar o módulo.
def _cria_fichas(parent, controller):
    from sigft.app_qt.views.cria_fichas import ModuloCriaFichas
    return ModuloCriaFichas(parent, controller)


def _pdm(parent, controller):
    from sigft.app_qt.views.pdm import ModuloPDM
    return ModuloPDM(parent, controller)


def _analyzer(parent, controller):
    from sigft.app_qt.views.analyzer import ModuloAnalyzer
    return ModuloAnalyzer(parent, controller)


def _upload_conditions(parent, controller):
    from sigft.app_qt.views.upload_conditions import ModuloUploadConditions
    return ModuloUploadConditions(parent, controller)


def _upload_specs(parent, controller):
    from sigft.app_qt.views.upload_tech_specs import ModuloUploadTechSpecs
    return ModuloUploadTechSpecs(parent, controller)


def _correcao_pdm(parent, controller):
    # Continua bloqueada no menu (`catalogo.TELAS_BLOQUEADAS`); registrada para
    # abrir assim que for liberada.
    from sigft.app_qt.views.correcao_pdm import ModuloCorrecaoPDM
    return ModuloCorrecaoPDM(parent, controller)


def _copia_fichas(parent, controller):
    from sigft.app_qt.views.copia_fichas import ModuloCopiaFichas
    return ModuloCopiaFichas(parent, controller)


def _autospec(parent, controller):
    # Tela da frente do Rafael (TRABALHO_PARALELO.md); a lógica é do serviço.
    from sigft.app_qt.views.autospec import ModuloAutoSpec
    return ModuloAutoSpec(parent, controller)


def _pmib_manager(parent, controller):
    from sigft.app_qt.views.pmib_manager import ModuloPMIBManager
    return ModuloPMIBManager(parent, controller)


def _busca_pmib(parent, controller):
    from sigft.app_qt.views.busca_pmib import ModuloBuscaPMIB
    return ModuloBuscaPMIB(parent, controller)


# Registro das telas migradas: nome -> fábrica(parent, controller). O teste
# `tests/test_qt_registro_telas.py` cobra que todo item do menu esteja aqui.
TELAS = {
    "Home": lambda parent, controller: HomeView(parent, controller),
    # Etapa 2 (pilotos): Tradutor e a seção Aplicação LMR (Upload + Exclusão).
    "Translator": lambda parent, controller: ModuloTranslator(parent, controller),
    "LMR": lambda parent, controller: ModuloAplicacaoLMR(parent, controller),
    # Etapas 3 a 5.
    "CriaFichas": _cria_fichas,
    "PDM": _pdm,
    "Analyzer": _analyzer,
    "UploadConditions": _upload_conditions,
    "UploadSpecs": _upload_specs,
    "CorrecaoPDM": _correcao_pdm,
    "CopiaFichas": _copia_fichas,
    "AutoSpec": _autospec,
    "PMIBManager": _pmib_manager,
    "SearchPMIB": _busca_pmib,
}


def resource_path(relativo: str) -> str:
    base = getattr(sys, "_MEIPASS", _RAIZ)
    return os.path.join(base, relativo)


load_dotenv(resource_path(".env"))


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

        # Só o --smoke liga: ele fecha a janela sem ninguém para responder a
        # pergunta de "tarefa em andamento" (offscreen, no CI).
        self.fechar_sem_perguntar = False
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

        # Toda abertura do app instalado pergunta ao GitHub se há versão nova,
        # numa thread (a abertura não espera). Ver `sigft/app_qt/atualizacao.py`.
        atualizacao.verificar_na_abertura(self)

    # -- barra lateral --------------------------------------------------------
    def _montar_sidebar(self) -> QScrollArea:
        area = QScrollArea(objectName="sidebar")
        # A largura total da barra do CustomTkinter (277), para os módulos
        # começarem no mesmo x. Lá, 17 desses px são a faixa da barra de rolagem,
        # SEMPRE visível (um traço cinza que não rola nada quando tudo cabe).
        # Aqui a faixa fica vazia -- margem direita maior --, e a barra do Qt só
        # aparece quando há o que rolar: a mesma largura sem o traço inútil, e os
        # botões com a largura que já tinham (246).
        area.setFixedWidth(estilo.LARGURA_BARRA_LATERAL)
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        interno = QWidget(objectName="sidebar_interno")
        lay = QVBoxLayout(interno)
        lay.setContentsMargins(12, 26, 19, 12)  # 19 = 12 + os 7 px da faixa vazia
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
            if fabrica is None:
                tela = TelaNaoMigrada(nome)
            else:
                try:
                    tela = fabrica(self.pilha, self)
                except Exception as erro:  # noqa: BLE001 -- vira tela de erro
                    traceback.print_exc()
                    erro_tela = TelaComErro(nome, erro)
                    self.pilha.addWidget(erro_tela)
                    self.pilha.setCurrentWidget(erro_tela)
                    return  # sem cache: a próxima visita tenta montar de novo
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
        if not self.fechar_sem_perguntar and instancia.tarefas_em_andamento():
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


def _instalar_traducao(app) -> bool:
    """Botões dos diálogos do Qt em português ("Sim", "Não", "Cancelar").
    Sem isto o QMessageBox mostra "Yes"/"No"/"Cancel"."""
    from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator

    tradutor = QTranslator(app)
    pasta = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if tradutor.load(QLocale("pt_BR"), "qtbase", "_", pasta):
        app.installTranslator(tradutor)
        app._tradutor_qt = tradutor  # segura a referência
        return True
    return False


def _preparar_qt() -> QApplication:
    app = QApplication.instance() or QApplication(sys.argv)
    _instalar_traducao(app)
    interface.instalar()
    estilo.carregar_fontes()
    app.setStyleSheet(estilo.folha_de_estilo())
    return app


def main() -> None:
    instancia.preparar()

    # Traz `api_config.json`, `user_prefs.json` e o `.env` da pasta do programa
    # para `Documentos\SIG-FT\`, uma vez. Silenciosa quando não há o que
    # migrar, e nunca levanta. Ver `sigft/core/dados_usuario.py`.
    from sigft.core.dados_usuario import migrar_se_preciso

    if (trazidos := migrar_se_preciso()):
        print(f"[SIG-FT] Configuracao importada para a pasta de dados: "
              f"{', '.join(trazidos)}")

    # Acha o Chrome/Edge da máquina para o RPA e repassa o certificado da
    # empresa ao processo Node do Playwright. `None` é resultado válido: o app
    # abre igual, e só o robô reclama quando for usado. Ver
    # `sigft/core/rpa/navegador.py`.
    from sigft.core.rpa.navegador import preparar_ambiente_do_rpa

    if (navegador_do_rpa := preparar_ambiente_do_rpa()):
        print(f"[SIG-FT] Navegador do RPA: {navegador_do_rpa}")
    else:
        print("[SIG-FT] Nenhum Chrome/Edge encontrado. O app abre normalmente; "
              "so o robo do portal vai reclamar de navegador quando for usado.")

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


def _visitar_telas(janela: SIG_FT_App) -> tuple[list[str], list[tuple[str, BaseException]]]:
    """Abre cada tela de `TELAS` pelo funil de sempre (`show_frame`).

    As telas nascem na primeira visita: sem isto, um módulo de tela que ficou
    fora do pacote só apareceria quando alguém clicasse no menu. As bloqueadas
    ficam de fora -- `show_frame` as recusa de propósito.
    """
    linhas: list[str] = []
    quebradas: list[tuple[str, BaseException]] = []
    for chave in TELAS:
        if chave in catalogo.TELAS_BLOQUEADAS:
            continue
        janela.show_frame(chave)
        tela = janela.pilha.currentWidget()
        if isinstance(tela, TelaComErro):
            quebradas.append((chave, tela.erro))
            linhas.append(f"  FALHOU  {chave}: {type(tela.erro).__name__}: {tela.erro}")
        else:
            linhas.append(f"  OK      {chave}")
    return linhas, quebradas


def _smoke() -> int:
    """Monta a janela, visita as telas e sai, sem laço de eventos (Release e CI).

    O relatório é GRAVADO, e não só impresso: o `.exe` é `console=False`, e o
    que ele imprime não chega ao passo do Release, que lê o arquivo. Mesma
    lição do `_smoke` de `sigft/app/main.py` (run #3 de 2026-09-21), com os
    avisos de backend nos dois caminhos.
    """
    from sigft.app.conferencia import ARQUIVO_JANELA, gravar_relatorio

    avisos: list[str] = []
    try:
        _preparar_qt()
        backends.carregar_todos(
            ao_falhar=lambda nome, erro: avisos.append(
                f"[smoke] AVISO: o backend '{nome}' nao carregou: "
                f"{type(erro).__name__}: {erro}"))
        janela = SIG_FT_App()
        janela.fechar_sem_perguntar = True
        linhas, quebradas = _visitar_telas(janela)
        janela.close()
    except Exception as erro:  # noqa: BLE001 -- é o que se quer relatar
        relatorio = "\n".join(avisos + [
            f"[smoke] FALHOU: {type(erro).__name__}: {erro}", "",
            traceback.format_exc()])
        gravar_relatorio(ARQUIVO_JANELA, relatorio)
        print(relatorio)
        return 1

    partes = avisos + ["[smoke] telas visitadas:", *linhas]
    if (bloqueadas := [chave for chave in TELAS if chave in catalogo.TELAS_BLOQUEADAS]):
        partes.append(f"[smoke] bloqueadas no menu (nao visitadas): {', '.join(bloqueadas)}")
    if quebradas:
        partes.append(f"[smoke] FALHOU: telas que nao abriram ({len(quebradas)}): "
                      + ", ".join(chave for chave, _ in quebradas))
        for chave, erro in quebradas:
            partes += ["", f"--- {chave} ---",
                       "".join(traceback.format_exception(erro)).rstrip()]
    else:
        partes.append(f"[smoke] a janela principal Qt montou, as {len(linhas)} telas "
                      "abriram e ela fechou sem erro.")
    relatorio = "\n".join(partes)
    gravar_relatorio(ARQUIVO_JANELA, relatorio)
    print(relatorio)
    return 1 if quebradas else 0


def executar_da_linha_de_comando() -> None:
    if "--smoke" in sys.argv:
        sys.exit(_smoke())
    main()


if __name__ == "__main__":
    executar_da_linha_de_comando()
