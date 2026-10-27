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

    # `python -m sigft.app_qt.main --conferir-pacote`: antes do PySide6, pelo
    # mesmo motivo do `frontend.py` (a conferência tem de responder num
    # ambiente quebrado).
    from sigft.app.conferencia import despachar_cedo

    despachar_cedo()

import json
import os
import sys
import threading
import time
import traceback

from dotenv import load_dotenv
from PySide6.QtCore import QEvent, Qt, QtMsgType, Signal, qInstallMessageHandler
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)
from shiboken6 import isValid

from sigft import _build_info
from sigft.app import backends, idioma, tokens
from sigft.app.idioma import t
from sigft.app_qt import (
    atualizacao, catalogo, cursor, escolha_de_idioma, estilo, icones, interface, letra, novidades,
    pasta_de_logs, tema,
)
from sigft.app_qt import nome as nome_da_pessoa
from sigft.app_qt.views.aplicacao_lmr import ModuloAplicacaoLMR
from sigft.app_qt.views.home import HomeView
from sigft.app_qt.views.nao_migrada import TelaComErro, TelaNaoMigrada
from sigft.app_qt.views.translator import ModuloTranslator
from sigft.app_qt.widgets import blocos
from sigft.app_qt.widgets.marca import Marca
from sigft.app_qt.widgets.paleta import PaletaDeComandos
from sigft.core import diario, instancia
from sigft.core.saida_log import desviar_saida_para_arquivo
from sigft.app_qt import propriedades

# Sem console (o .exe), `print` e traceback vão para `logs/sigft.log`: é o canal
# de diagnóstico da primeira execução em máquina nova. No import, antes de
# qualquer coisa imprimir.
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

# Ctrl+K (etapa 1b, 2026-10-21): o método da Home que cada `acao:` chama, das
# listas únicas de `catalogo` (a barra, a engrenagem e a janela Configuração). As
# outras ações (`inicio`, `logs`, `tema_*`, `letra_*`) estão em `executar_comando`.
ACAO_NA_HOME = {acao.chave: acao.metodo for acao in catalogo.ACOES_QUE_A_HOME_FAZ}


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

        # Ctrl+K: a caixa de busca dos módulos e das ações (etapa 1b, 2026-10-21).
        # Contexto de janela (o padrão): vale em qualquer tela. Campo de texto
        # que usa o Ctrl+K como "apagar até o fim da linha" (Qt no Linux e no
        # Mac; no Windows não há essa tecla) ganha dele quando tem o foco: o Qt
        # pergunta ao campo antes (ShortcutOverride), e decidimos não roubar.
        self._paleta = None
        self.atalho_paleta = QShortcut(QKeySequence("Ctrl+K"), self)
        self.atalho_paleta.activated.connect(self.abrir_paleta)

        # Toda abertura do app instalado pergunta ao GitHub se há versão nova,
        # numa thread (a abertura não espera). Ver `sigft/app_qt/atualizacao.py`.
        atualizacao.verificar_na_abertura(self)
        # Primeira abertura de uma versão nova: "O que mudou na vX", uma vez,
        # depois de a janela aparecer. Pelo código-fonte não faz nada. Ver
        # `sigft/app_qt/novidades.py` (tela) e `core/novidades.py` (regra).
        novidades.agendar_na_abertura(self)

    # -- barra lateral --------------------------------------------------------
    def _montar_sidebar(self) -> QScrollArea:
        area = QScrollArea(objectName="sidebar")
        # A largura total da barra da interface antiga (277), para os módulos
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

        # O logo da GE Vernova e o nome do SIG-FT viraram um botão só: brilham
        # sob o mouse e voltam à Home (sistema visual, 2026-10-20). Mesmas
        # medidas dos dois rótulos de antes (`widgets/marca.py`).
        self.marca = Marca(resource_path(os.path.join("assets", "logo.png")))
        blocos.sem_tecla(self.marca)
        self.marca.clicked.connect(self.show_home)
        lay.addWidget(self.marca)
        lay.addSpacing(22)
        # O emoji virou ícone (Lucide, na cor do tema: sistema visual, 2026-10-20).
        home = QPushButton(f" {t('Home')}", objectName="home")
        # O ícone acompanha o texto do item escolhido (e sob o mouse): a marca
        # no claro (2026-10-20).
        icones.aplicar(home, catalogo.ICONE_DA_TELA["Home"], tamanho=16,
                       papel_cor_ativo=estilo.PAPEL_MENU_ESCOLHIDO)
        self.botao_home = home
        blocos.sem_tecla(home)   # os botões da barra (CTkButton) nunca pegam o foco
        home.clicked.connect(self.show_home)
        home.setToolTip(t("Volta à tela inicial: os módulos, a engrenagem da configuração e os gastos de IA."))
        lay.addWidget(home)
        lay.addSpacing(6)

        self.botoes_menu: dict[str, QPushButton] = {}
        for item in catalogo.MENU:
            if item[0] == "secao":
                lay.addSpacing(20)
                lay.addWidget(QLabel(t(item[1]).upper(), objectName="secao"))
                lay.addSpacing(5)
                continue
            _tipo, texto, alvo = item
            botao = QPushButton(f" {t(texto)}")
            blocos.sem_tecla(botao)
            botao.setProperty("menu", True)
            icones.aplicar(botao, catalogo.ICONE_DA_TELA[alvo], tamanho=16,
                           papel_cor_ativo=estilo.PAPEL_MENU_ESCOLHIDO)
            botao.setEnabled(alvo not in catalogo.TELAS_BLOQUEADAS)
            botao.setToolTip(catalogo.dica_do_menu(alvo))
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
                    self._marcar_no_menu(nome)  # o menu marca a tela que falhou, não a anterior
                    return  # sem cache: a próxima visita tenta montar de novo
            self.telas[nome] = tela
            self.pilha.addWidget(tela)
        # [2026-10-20] A saudação segue o relógio: recalcula a cada volta à Home.
        if hasattr(tela, "atualizar_saudacao"):
            tela.atualizar_saudacao()
        self.pilha.setCurrentWidget(tela)
        self._marcar_no_menu(nome)

    def _marcar_no_menu(self, nome: str) -> None:
        """O item da tela aberta fica marcado no menu (`ativo`, que a folha pinta
        com a marca a 25%: sistema visual, 2026-10-20). A Home marca o botão dela."""
        botoes = {**self.botoes_menu, "Home": self.botao_home}
        for alvo, botao in botoes.items():
            ativo = alvo == nome
            if bool(propriedades.ler(botao, "ativo")) == ativo:
                continue
            botao.setProperty("ativo", ativo)
            # Propriedade dinâmica não repinta sozinha: a folha é reaplicada,
            # e o ícone, que segue o `ativo`, é repintado.
            botao.style().unpolish(botao)
            botao.style().polish(botao)
            icones.reaplicar(botao)

    def show_modulo(self, nome: str) -> None:
        self.show_frame(nome)

    def show_home(self) -> None:
        self.show_frame("Home")

    # -- Ctrl+K ------------------------------------------------------------------
    def abrir_paleta(self) -> PaletaDeComandos:
        """Abre a caixa do Ctrl+K; já aberta, devolve a mesma."""
        if self._paleta is not None and isValid(self._paleta) and self._paleta.isVisible():
            self._paleta.raise_()
            return self._paleta
        paleta = PaletaDeComandos(self, catalogo.comandos())
        paleta.escolheu.connect(self.executar_comando)
        self._paleta = paleta
        paleta.abrir_sobre(self)
        return paleta

    def _home_view(self):
        home = self.telas.get("Home")
        return home if isinstance(home, HomeView) else None

    def executar_comando(self, chave: str) -> None:
        """Faz o comando `chave` do Ctrl+K (`catalogo.comandos`). Desconhecido: nada."""
        tipo, _, alvo = chave.partition(":")
        if tipo == "tela":
            if alvo:
                self.show_frame(alvo)
            return
        if tipo != "acao":
            return
        home = self._home_view()
        if alvo == "inicio":
            self.show_home()
        elif alvo in ACAO_NA_HOME:
            if home is not None:
                getattr(home, ACAO_NA_HOME[alvo])()
        elif alvo.startswith("tema_"):
            # Pela Home, que chama `tema.aplicar` e marca o seletor dela.
            escolha = alvo.removeprefix("tema_")
            if home is not None:
                home.escolher_tema(escolha)
            else:
                tema.aplicar(QApplication.instance(), escolha)
        elif alvo.startswith("letra_"):
            # Pela Home, como o tema: ela chama `letra.aplicar` e marca o seletor.
            escolha = alvo.removeprefix("letra_")
            if home is not None:
                home.escolher_letra(escolha)
            else:
                letra.aplicar(QApplication.instance(), escolha)
        elif alvo == "logs":
            self.abrir_pasta_de_logs()

    def abrir_pasta_de_logs(self) -> None:
        """`Documentos\\SIG-FT\\logs\\` no explorador (criada se faltar)."""
        pasta_de_logs.abrir(self)

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
                self, t("Fechar o SIG-FT"), t(catalogo.MSG_TAREFA_EM_ANDAMENTO),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if resposta != QMessageBox.StandardButton.Yes:
                evento.ignore()
                return
        evento.accept()
        # [2026-10-26] O diário de quedas: esta sessão fechou pela janela. O "Não"
        # da pergunta acima não chega aqui. Sem diário aberto, não faz nada.
        diario.registrar_fechamento()


class SplashScreen(QWidget):
    """A splash, sem as pausas artificiais: o progresso é o real.

    Sistema visual (2026-10-20): fundo `fundo`, o logo da GE Vernova no centro,
    "SIG-FT" 22 em negrito, a versão em `texto_suave` e uma barra de 4 px em
    `primaria`, num cartão de cantos 10. Ela aparece ANTES da janela principal:
    a paleta vem do tema guardado (`tema.escolhido`), lido aqui mesmo, para quem
    usa o claro não ver a abertura escura (o `_preparar_qt`, que roda antes,
    aplica o mesmo tema à folha do app).
    """

    pronta = Signal()

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.SplashScreen)
        self.setFixedSize(500, 350)
        # O fundo é desenhado no `paintEvent` (os cantos arredondados): fora
        # do cartão, a janela é transparente.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._paleta = tokens.paleta(tema.efetivo(tema.escolhido()))
        self.setObjectName("splash")
        # Folha própria, por cima da do app: a cor de cada peça é a do tema
        # guardado, qualquer que seja a folha aplicada (`estilo.folha_da_splash`).
        self.setStyleSheet(estilo.folha_da_splash(tema.efetivo(tema.escolhido())))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(50, 50, 50, 30)
        lay.setSpacing(tokens.ESPACO[1])
        lay.addStretch()
        logo = QLabel()
        caminho = resource_path(os.path.join("assets", "logo.png"))
        if os.path.exists(caminho):
            logo.setPixmap(QPixmap(caminho).scaledToWidth(
                260, Qt.TransformationMode.SmoothTransformation))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(logo)
        lay.addSpacing(tokens.ESPACO[3])
        self.titulo = QLabel("SIG-FT")
        self.titulo.setObjectName("splash_titulo")
        self.titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.titulo)
        self.versao = QLabel(_texto_da_versao())
        self.versao.setObjectName("splash_versao")
        self.versao.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.versao)
        lay.addStretch()
        self.status = QLabel(t("Iniciando..."))
        self.status.setObjectName("splash_status")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.status)
        self.barra = QProgressBar()
        self.barra.setRange(0, 1000)
        self.barra.setTextVisible(False)
        self.barra.setFixedHeight(4)
        lay.addWidget(self.barra)

    def paintEvent(self, _evento) -> None:  # noqa: N802 -- nome do Qt
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(QColor(self._paleta["fundo"]))
        raio = tokens.RAIO["cartao"]
        pintor.drawRoundedRect(self.rect(), raio, raio)
        pintor.end()

    def carregar(self) -> None:
        threading.Thread(target=self._carregar, name="splash", daemon=True).start()

    def _carregar(self) -> None:
        inicio = time.time()

        def progredir(exibido, fracao):
            interface.na_interface(self.status.setText, t("Carregando: {nome}...", nome=exibido))
            interface.na_interface(self.barra.setValue, int(fracao * 1000))

        def falhar(exibido, erro):
            print(f"Erro ao carregar {exibido}: {erro}")
            interface.na_interface(self.status.setText, t("Erro em {nome}", nome=exibido))

        try:
            backends.carregar_todos(ao_progredir=progredir, ao_falhar=falhar)
            interface.na_interface(self.status.setText,
                                   t("Concluído em {segundos}s", segundos=f"{time.time() - inicio:.1f}"))
        except BaseException:  # noqa: BLE001 -- inclui SystemExit de um backend no import
            traceback.print_exc()
        finally:
            # Sempre segue adiante: a splash que não some deixa o processo vivo
            # e sem janela. Tela com backend ausente mostra o motivo sozinha
            # (`backends.falhas`).
            interface.na_interface(self.pronta.emit)


def _texto_da_versao() -> str:
    """"versão X.Y.Z" do `_build_info` (o Release reescreve; do código-fonte
    é o padrão commitado). `_build_info` sem `VERSAO`: um texto que não
    quebra a abertura."""
    versao = getattr(_build_info, "VERSAO", "") or ""
    return t("versão {versao}", versao=versao) if versao else t("versão de desenvolvimento")


# A tradução dos botões padrão do Qt ("Sim", "Não", "Cancelar") de cada idioma da
# interface (2026-10-22). O inglês não tem: o Qt já é inglês. O `SIG-FT.spec`
# leva estas e a `--conferir-pacote` confere (`conferencia.TRADUCOES_DA_QT`).
LOCALE_DO_QT = {"pt": "pt_BR", "es": "es"}


def _instalar_traducao(app) -> bool:
    """Botões dos diálogos do Qt no idioma da sessão (`idioma.atual()`). Troca a
    instalada antes, se houver. `True` se instalou uma."""
    from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator

    anterior = getattr(app, "_tradutor_qt", None)
    if anterior is not None:
        app.removeTranslator(anterior)
        app._tradutor_qt = None
    local = LOCALE_DO_QT.get(idioma.atual())
    if local is None:
        return False
    tradutor = QTranslator(app)
    pasta = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if tradutor.load(QLocale(local), "qtbase", "_", pasta):
        app.installTranslator(tradutor)
        app._tradutor_qt = tradutor  # segura a referência
        return True
    return False


def _a_qt_nao_subiu(texto: str) -> None:
    """Um erro FATAL do Qt na criação da QApplication (o plugin da plataforma
    que falta é o caso clássico). O Qt aborta o processo logo depois de
    avisar -- código 134, sem exceção nenhuma para o `frontend.py` tratar, e
    no `.exe` sem console a pessoa via o app simplesmente não abrir.

    Aqui o aviso vira o mesmo do `frontend.py` quando a Qt não importa: o
    relatório do `--smoke`, ou a caixa do sistema com o caminho do `sigft.log`.
    E sai com 1 antes do `abort` do Qt.
    """
    if "--smoke" in sys.argv:
        from sigft.app.conferencia import ARQUIVO_JANELA, gravar_relatorio

        relatorio = f"[smoke] FALHOU: a interface Qt nao abriu: {texto}"
        gravar_relatorio(ARQUIVO_JANELA, relatorio)
        print(relatorio, flush=True)
    else:
        from sigft.core.erro_de_abertura import avisar

        avisar(f"A Qt não conseguiu iniciar:\n{texto}")
    os._exit(1)


def _criar_qapplication() -> QApplication:
    """A QApplication, com os erros fatais do Qt virando aviso (ver
    `_a_qt_nao_subiu`). O tratador vale só durante a criação: depois dela, as
    mensagens do Qt voltam ao caminho padrão."""
    avisos: list[str] = []

    def _ao_avisar(modo, _contexto, texto) -> None:
        if modo == QtMsgType.QtFatalMsg:
            _a_qt_nao_subiu("\n".join([*avisos, texto]))
        avisos.append(texto)
        if sys.stderr is not None:
            print(texto, file=sys.stderr)

    anterior = qInstallMessageHandler(_ao_avisar)
    try:
        return QApplication(sys.argv)
    finally:
        qInstallMessageHandler(anterior)


def _preparar_qt(escolha_tema: str | None = None, escolha_letra: str | None = None,
                 escolha_idioma: str | None = None) -> QApplication:
    """A QApplication pronta: idioma, tradução do Qt, fontes, cursor, a letra e o tema.

    Idioma, letra e tema são os guardados nas preferências, ou os da linha de
    comando (`--smoke --idioma es --tema claro --letra grande`), sem gravar: a
    abertura só lê. O idioma vem primeiro (a tradução do Qt e a largura das
    peças dependem dele); a letra antes do tema (a folha que o tema aplica já
    sai com o aumento)."""
    app = QApplication.instance() or _criar_qapplication()
    idioma.definir(escolha_idioma or idioma.escolhido() or idioma.PADRAO)
    _instalar_traducao(app)
    interface.instalar()
    estilo.carregar_fontes()
    letra.aplicar(app, escolha_letra or letra.escolhido(), gravar=False)
    tema.aplicar(app, escolha_tema or tema.escolhido(), gravar=False)
    tema.seguir_o_sistema(app)
    cursor.instalar(app)
    return app


def _aplicar_idioma(app, codigo: str) -> None:
    """O idioma escolhido na primeira abertura, antes de a janela principal
    existir: a sessão, a tradução do Qt e a largura das peças (`letra`)."""
    idioma.definir(codigo)
    _instalar_traducao(app)
    letra.aplicar(app, letra.atual(), gravar=False)


def _opcao_da_linha_de_comando(argv: list[str], nome: str) -> str | None:
    """O valor de `nome X` (ou `nome=X`) da linha de comando, se houver."""
    for i, arg in enumerate(argv):
        if arg == nome and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith(nome + "="):
            return arg.split("=", 1)[1]
    return None


def _tema_da_linha_de_comando(argv: list[str]) -> str | None:
    """O `--tema X` (ou `--tema=X`) da linha de comando, se houver."""
    return _opcao_da_linha_de_comando(argv, "--tema")


def _redesenhar_saudacao(principal: SIG_FT_App):
    """O que roda quando a pessoa responde a pergunta do nome: a Home (se já
    montada) refaz a saudação."""
    def redesenhar() -> None:
        home = principal.telas.get("Home")
        if home is not None and hasattr(home, "atualizar_saudacao"):
            home.atualizar_saudacao()
    return redesenhar


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
    # [2026-10-22] Sem idioma escolhido (instalação nova ou atualização): a pergunta,
    # antes da splash e da janela principal, que já nascem no idioma escolhido.
    if (escolhido := escolha_de_idioma.perguntar_na_abertura()) is not None:
        _aplicar_idioma(app, escolhido)
    # [2026-10-26] O diário de quedas (`sigft/core/diario.py`): lê como a sessão
    # anterior acabou (a Home avisa se caiu ou foi encerrada de fora), marca esta
    # abertura e liga os ganchos de erro e o `faulthandler`. Depois do idioma (a
    # linha da abertura o leva) e antes da janela. Nunca levanta.
    diario.abrir(versao=_build_info.VERSAO, idioma=idioma.atual())
    splash = SplashScreen()
    janela: list[SIG_FT_App] = []

    def abrir_principal() -> None:
        try:
            principal = SIG_FT_App()
        except Exception as erro:  # noqa: BLE001 -- vira aviso, e não fantasma
            traceback.print_exception(erro)
            # Sai com 1: o `SIG-FT.bat` e o `.command` esperam este processo e
            # deixam a janela preta aberta com "Encerrado com erro".
            QMessageBox.critical(None, "SIG-FT", t(
                catalogo.MSG_ABERTURA_FALHOU, erro=f"{type(erro).__name__}: {erro}"))
            instancia.encerrar(1)
            return
        janela.append(principal)
        # [2026-10-23] Abre maximizada (a tela inteira, com a barra do Windows à
        # vista); o "restaurar" volta ao 1280x850 do `resize`.
        principal.showMaximized()
        splash.close()
        # [2026-10-20] "Como podemos te chamar?", uma vez, logo depois de a
        # janela aparecer (antes das novidades, que esperam a resposta). Daqui,
        # e não do `SIG_FT_App`, para nenhum teste que monta a janela travar
        # na pergunta. Ver `sigft/app_qt/nome.py`.
        nome_da_pessoa.perguntar_na_abertura(principal, depois=_redesenhar_saudacao(principal))

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

    # [2026-10-21] O smoke nunca solta o aviso do Windows (`aviso_windows`):
    # roda no Release e no CI, e numa máquina com bandeja a notificação sairia.
    from sigft.app_qt import aviso_windows

    os.environ[aviso_windows.ENV_DESLIGAR] = "1"
    avisos: list[str] = []
    try:
        # `--smoke --tema claro --letra grande --idioma es`: o smoke também no
        # claro, com a letra grande e em outro idioma (`--idioma es`), sem gravar
        # a escolha.
        _preparar_qt(_tema_da_linha_de_comando(sys.argv),
                     _opcao_da_linha_de_comando(sys.argv, "--letra"),
                     _opcao_da_linha_de_comando(sys.argv, "--idioma"))
        # Os ícones desenham? Um SVG ou o QtSvg fora do `.exe` daria botões em
        # branco SEM erro (2026-10-20: a mesma classe do pymupdf-layout, um
        # arquivo que faltava só no pacote). Aqui o Release reprova.
        if (sem_desenho := icones.conferir()):
            relatorio = (f"[smoke] FALHOU: icones que nao desenham ({len(sem_desenho)}): "
                         f"{', '.join(sem_desenho)} (pasta {icones.PASTA})")
            gravar_relatorio(ARQUIVO_JANELA, relatorio)
            print(relatorio)
            return 1
        # Os catálogos de idioma se leem? Fora do `.exe`, o app abriria só em
        # português, sem erro: a mesma classe dos ícones (2026-10-22).
        if (sem_catalogo := idioma.conferir()):
            relatorio = (f"[smoke] FALHOU: catalogos de idioma que nao se leem: "
                         f"{', '.join(sem_catalogo)} (pasta {idioma.PASTA_CATALOGOS})")
            gravar_relatorio(ARQUIVO_JANELA, relatorio)
            print(relatorio)
            return 1
        backends.carregar_todos(
            ao_falhar=lambda nome, erro: avisos.append(
                f"[smoke] AVISO: o backend '{nome}' nao carregou: "
                f"{type(erro).__name__}: {erro}"))
        janela = SIG_FT_App()
        janela.fechar_sem_perguntar = True
        linhas, quebradas = _visitar_telas(janela)
        janela.close()
        # [2026-10-23] Fechar só esconde: a janela (~700 peças) ficava viva. Nos
        # testes, que rodam o smoke várias vezes na mesma sessão, cada troca de
        # folha do app repintava todas as que sobraram, e no Release (Windows) o
        # processo caiu pintando uma delas. Aqui ela sai de vez.
        janela.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
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
