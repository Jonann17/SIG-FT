"""O webhook de um workflow do AMP, dentro do módulo que o usa (2026-11-03).

Cada workflow do AMP (o n8n da GE) tem o seu endereço e a sua chave: a Revisão no AMP usa o da
revisão de listas, e os próximos módulos, os deles (o Luan, em 03/11). Os dois ficam no
`api_config.json` (`controller.get_key`/`save_keys`), com os nomes que o módulo escolhe
(`ChavesDoWebhook`). A janela mostra a chave mascarada e confere o endereço antes de salvar.
Desenho: `docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`, §5.5.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QVBoxLayout

from sigft.app.idioma import marcar, t
from sigft.app_qt.widgets import blocos

EXPLICACAO = marcar("Cada workflow do AMP tem o seu endereço e a sua chave. Eles ficam neste computador, "
                    "em Documentos\\SIG-FT, e a chave nunca aparece no log.")
ROTULO_ENDERECO = marcar("Endereço (a Production URL do webhook no n8n):")
ROTULO_CHAVE = marcar("Chave (o valor da credencial X-SIGFT-Chave):")
ENDERECO_SEM_HTTPS = marcar("O endereço precisa começar por https://.")
ENDERECO_DE_TESTE = marcar("Esse é o endereço de teste (/webhook-test/), que só funciona com o n8n "
                           "escutando. Use a Production URL (/webhook/).")
TEXTO_SALVAR = marcar("Salvar")
TEXTO_CANCELAR = marcar("Cancelar")


@dataclass(frozen=True)
class ChavesDoWebhook:
    """Os nomes do endereço e da chave no `api_config.json`; `antigas`, os de antes, adotados
    uma vez (`ler`)."""
    url: str
    chave: str
    antigas: tuple[str, str] | None = None


def _valor(controller, nome: str) -> str:
    return (controller.get_key(nome) or "").strip()


def gravar(controller, chaves: ChavesDoWebhook, url: str, chave: str) -> None:
    controller.save_keys({chaves.url: url.strip(), chaves.chave: chave.strip()})


def ler(controller, chaves: ChavesDoWebhook) -> tuple[str, str]:
    """(endereço, chave). Com os nomes do módulo vazios e os antigos postos, adota os antigos e
    os grava nos nomes do módulo: na próxima leitura, eles já estão lá."""
    if controller is None:
        return "", ""
    url, chave = _valor(controller, chaves.url), _valor(controller, chaves.chave)
    if url or chave or not chaves.antigas:
        return url, chave
    url_antiga, chave_antiga = (_valor(controller, nome) for nome in chaves.antigas)
    if url_antiga or chave_antiga:
        gravar(controller, chaves, url_antiga, chave_antiga)
    return url_antiga, chave_antiga


def problema_do_endereco(url: str) -> str:
    """O que impede salvar o endereço (já traduzido), ou "" quando ele está bom."""
    url = url.strip()
    if not url.startswith("https://"):
        return t(ENDERECO_SEM_HTTPS)
    if "/webhook-test/" in url:
        return t(ENDERECO_DE_TESTE)
    return ""


class JanelaDoWebhook(QDialog):
    """Endereço e chave (mascarada), "Salvar" e "Cancelar". Não grava nada: quem abre lê
    `valores()` quando ela volta aceita."""

    def __init__(self, parent=None, *, titulo: str, url: str = "", chave: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setModal(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(6)
        lay.addWidget(blocos.rotulo(t(EXPLICACAO), alinhar="esquerda", papel="legenda"))
        lay.addSpacing(8)
        lay.addWidget(blocos.rotulo(t(ROTULO_ENDERECO), alinhar="esquerda"))
        self.campo_url = QLineEdit(url)
        self.campo_url.setMinimumWidth(520)
        self.campo_url.returnPressed.connect(self._salvar)
        lay.addWidget(self.campo_url)
        lay.addWidget(blocos.rotulo(t(ROTULO_CHAVE), alinhar="esquerda"))
        self.campo_chave = QLineEdit(chave)
        self.campo_chave.setEchoMode(QLineEdit.EchoMode.Password)
        # O caractere da máscara é o asterisco, como nas chaves da Configuração.
        self.campo_chave.setStyleSheet("lineedit-password-character: 42;")
        self.campo_chave.returnPressed.connect(self._salvar)
        lay.addWidget(self.campo_chave)
        self.lbl_problema = blocos.rotulo("", alinhar="esquerda", papel="erro")
        lay.addWidget(self.lbl_problema)
        lay.addSpacing(10)
        botoes = QHBoxLayout()
        botoes.setSpacing(10)
        botoes.addStretch()
        self.botao_cancelar = blocos.botao(t(TEXTO_CANCELAR), variante="secundario", largura=120)
        self.botao_cancelar.clicked.connect(self.reject)
        self.botao_salvar = blocos.botao(t(TEXTO_SALVAR), variante="primario", largura=120, negrito=True)
        self.botao_salvar.clicked.connect(self._salvar)
        botoes.addWidget(self.botao_cancelar)
        botoes.addWidget(self.botao_salvar)
        lay.addLayout(botoes)
        self.campo_url.setFocus()

    def _salvar(self) -> None:
        problema = problema_do_endereco(self.campo_url.text())
        if problema:
            self.lbl_problema.setText(problema)
            return
        self.accept()

    def valores(self) -> tuple[str, str]:
        return self.campo_url.text().strip(), self.campo_chave.text().strip()
