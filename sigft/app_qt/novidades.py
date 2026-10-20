"""A janela de novidades -- "O que mudou na vX", uma vez por versão nova.

Pendência de 2026-09-25: o `CHANGELOG.md` ia no pacote "para a janela de
novidades" e a janela não existia. A REGRA (quando mostrar, gravar a versão
como vista) mora em `sigft/core/novidades.para_mostrar_na_abertura`; aqui só
o que é de tela:

* `agendar_na_abertura(janela)` -- chamada pela janela principal ao montar.
  Pelo código-fonte não faz nada; no app empacotado agenda a decisão para
  DEPOIS de a janela aparecer (a abertura não espera, e a janela não nasce
  na frente da principal ainda vazia);
* `mostrar_se_houver(janela, ...)` -- decide (pelo core) e abre a janela;
* `JanelaNovidades` -- o bloco do CHANGELOG em texto e um botão "OK".

Não compete com o aviso de atualização: se ele estiver aberto, as novidades
ficam para a próxima abertura (sem gravar a versão como vista). E a janela é
NÃO-modal: um aviso de atualização que chegue depois fica por cima dela.
"""
from __future__ import annotations

from functools import partial

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QLabel, QTextEdit, QVBoxLayout
from shiboken6 import isValid

from sigft import _build_info
from sigft.app.atualizacao_textos import data_br, notas_para_exibir
from sigft.app_qt import nome as nome_da_pessoa
from sigft.app_qt.widgets import blocos
from sigft.core import novidades
from sigft.services import updater

__all__ = ["JanelaNovidades", "agendar_na_abertura", "mostrar_se_houver"]

TITULO = "Novidades do SIG-FT"
TEXTO_OK = "OK"

# Quanto esperar depois de montar a janela principal: tempo de ela aparecer
# e pintar. Não é pausa da abertura -- o timer roda no laço de eventos.
ATRASO_MS = 1500

_LARGURA_DO_TEXTO = 530


def titulo_da_janela(bloco: novidades.Bloco) -> str:
    return f"O que mudou na v{bloco.versao}"


def subtitulo_da_janela(bloco: novidades.Bloco) -> str:
    texto = f"Você está usando a versão {bloco.versao} do SIG-FT"
    if bloco.data:
        texto += f", publicada em {data_br(bloco.data)}"
    return texto + "."


def _log(msg: object) -> None:
    print(f"[novidades] {msg}")


def agendar_na_abertura(janela, *, versao_atual: str | None = None,
                        atraso_ms: int = ATRASO_MS, agendar=None) -> bool:
    """Agenda a janela de novidades para depois da abertura. `True` se agendou.

    `agendar(ms, funcao)` é a costura do teste; a produção usa um
    `QTimer.singleShot` preso à janela (se ela morrer antes, nada roda).
    """
    if not updater.empacotado():
        return False
    funcao = partial(mostrar_se_houver, janela,
                     versao_atual=versao_atual or _build_info.VERSAO, empacotado=True)
    if agendar is None:
        QTimer.singleShot(atraso_ms, janela, funcao)
    else:
        agendar(atraso_ms, funcao)
    return True


def _aviso_de_atualizacao_aberto(janela) -> bool:
    aberta = getattr(janela, "_janela_de_atualizacao", None)
    return aberta is not None and isValid(aberta) and not getattr(aberta, "fechada", False)


def mostrar_se_houver(janela, *, versao_atual: str, empacotado: bool,
                      config_path=None):
    """Abre a janela de novidades se o core mandar. Devolve a janela ou `None`.

    Nunca levanta: um defeito aqui vai para o `sigft.log` e o app segue.
    """
    try:
        if not janela.isVisible() or _aviso_de_atualizacao_aberto(janela):
            return None
        # [2026-10-20] A pergunta do nome vem antes (`app_qt/nome.py`): com ela
        # na tela, as novidades esperam a resposta em vez de abrir por cima.
        if (pergunta := nome_da_pessoa.pergunta_aberta(janela)) is not None:
            pergunta.finished.connect(partial(_mostrar_depois_da_pergunta, janela,
                                              versao_atual, empacotado, config_path))
            return None
        bloco = novidades.para_mostrar_na_abertura(
            versao_atual, empacotado=empacotado, config_path=config_path)
        if bloco is None:
            return None
        dialogo = JanelaNovidades(janela, bloco=bloco)
        janela._janela_de_novidades = dialogo
        dialogo.show()
        dialogo.raise_()
        dialogo.activateWindow()
        return dialogo
    except Exception as erro:  # noqa: BLE001 -- novidade não derruba o app
        _log(f"nao foi possivel mostrar as novidades: {erro}")
        return None


def _mostrar_depois_da_pergunta(janela, versao_atual, empacotado, config_path, _codigo=None):
    if isValid(janela):
        mostrar_se_houver(janela, versao_atual=versao_atual, empacotado=empacotado,
                          config_path=config_path)


def _rotulo(texto: str, *, tamanho: int, papel: str | None = None, negrito: bool = False) -> QLabel:
    rotulo = blocos.rotulo(texto, tamanho=tamanho, negrito=negrito, papel=papel, alinhar="esquerda")
    rotulo.setWordWrap(True)
    rotulo.setMaximumWidth(_LARGURA_DO_TEXTO)
    return rotulo


class JanelaNovidades(QDialog):
    """"O que mudou na vX": o bloco do CHANGELOG da versão instalada e um "OK".

    Mesma cara do aviso de atualização (`app_qt/atualizacao.py`): título,
    resumo, caixa de texto só de leitura com a regra `#notas_atualizacao` da
    folha do app. Não-modal (o contrário do aviso, que fecha o app): ler as
    novidades não impede de trabalhar na janela de trás.
    """

    def __init__(self, master, *, bloco: novidades.Bloco):
        super().__init__(master)
        self.bloco = bloco
        self.setWindowTitle(TITULO)
        self.resize(580, 480)
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(0)

        lay.addSpacing(20)
        self.rotulo_titulo = _rotulo(titulo_da_janela(bloco), tamanho=16, negrito=True)
        lay.addWidget(self.rotulo_titulo)
        lay.addSpacing(4)
        self.rotulo_resumo = _rotulo(subtitulo_da_janela(bloco), tamanho=13,
                                     papel="legenda")
        lay.addWidget(self.rotulo_resumo)
        lay.addSpacing(14)

        self.caixa_texto = QTextEdit(objectName="notas_atualizacao")
        self.caixa_texto.setAcceptRichText(False)
        self.caixa_texto.setPlainText(notas_para_exibir(bloco.markdown()))
        self.caixa_texto.setReadOnly(True)
        self.caixa_texto.setMinimumHeight(40)
        lay.addWidget(self.caixa_texto, 1)

        lay.addSpacing(16)
        self.botao_ok = blocos.botao(TEXTO_OK, variante="primario", largura=150, altura=40,
                                     tamanho_fonte=14, negrito=True)
        self.botao_ok.clicked.connect(self.close)
        lay.addWidget(self.botao_ok, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(20)
        self.botao_ok.setFocus()
