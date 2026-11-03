"""O webhook de um workflow do AMP dentro do módulo (`sigft/app_qt/widgets/webhook_amp.py`): os
nomes de cada módulo no `api_config.json`, a adoção dos nomes antigos e a janela que confere o
endereço. Desenho: `docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`, §5.5.
"""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLineEdit

from sigft.app_qt.widgets import webhook_amp

URL = "https://ampworkflow.gevernova.net/webhook/sigft-revisao-listas"
CHAVES = webhook_amp.ChavesDoWebhook("AMP_REVISAO_LISTAS_URL", "AMP_REVISAO_LISTAS_CHAVE",
                                     antigas=("AMP_WEBHOOK_URL", "AMP_WEBHOOK_CHAVE"))


class _Controller:
    def __init__(self, **chaves):
        self.chaves = dict(chaves)
        self.gravadas = []

    def get_key(self, nome):
        return self.chaves.get(nome) or ""

    def save_keys(self, novas):
        self.gravadas.append(dict(novas))
        self.chaves.update(novas)


def test_le_os_nomes_do_modulo():
    controller = _Controller(AMP_REVISAO_LISTAS_URL=URL, AMP_REVISAO_LISTAS_CHAVE=" segredo ")
    assert webhook_amp.ler(controller, CHAVES) == (URL, "segredo")
    assert controller.gravadas == []


def test_adota_os_nomes_antigos_uma_vez():
    controller = _Controller(AMP_WEBHOOK_URL=URL, AMP_WEBHOOK_CHAVE="segredo")
    assert webhook_amp.ler(controller, CHAVES) == (URL, "segredo")
    assert controller.gravadas == [{"AMP_REVISAO_LISTAS_URL": URL, "AMP_REVISAO_LISTAS_CHAVE": "segredo"}]
    assert webhook_amp.ler(controller, CHAVES) == (URL, "segredo")
    assert len(controller.gravadas) == 1


def test_nada_configurado():
    assert webhook_amp.ler(_Controller(), CHAVES) == ("", "")
    assert webhook_amp.ler(None, CHAVES) == ("", "")


def test_gravar_tira_os_espacos():
    controller = _Controller()
    webhook_amp.gravar(controller, CHAVES, f" {URL} ", " segredo\n")
    assert controller.gravadas == [{"AMP_REVISAO_LISTAS_URL": URL, "AMP_REVISAO_LISTAS_CHAVE": "segredo"}]


def test_endereco_precisa_de_https_e_nao_pode_ser_o_de_teste():
    assert webhook_amp.problema_do_endereco(URL) == ""
    assert webhook_amp.problema_do_endereco("http://x/webhook/a") == "O endereço precisa começar por https://."
    assert webhook_amp.problema_do_endereco("") == "O endereço precisa começar por https://."
    assert "Production URL" in webhook_amp.problema_do_endereco("https://x/webhook-test/sigft-revisao-listas")


def test_janela_salva_os_valores(qt_interface, qtbot):
    janela = webhook_amp.JanelaDoWebhook(None, titulo="Webhook da Revisão no AMP")
    qtbot.addWidget(janela)
    assert janela.windowTitle() == "Webhook da Revisão no AMP"
    assert janela.campo_chave.echoMode() == QLineEdit.EchoMode.Password
    janela.campo_url.setText(f"  {URL} ")
    janela.campo_chave.setText(" segredo ")
    janela.botao_salvar.click()
    assert janela.result() == QDialog.DialogCode.Accepted
    assert janela.valores() == (URL, "segredo")


def test_janela_nao_salva_endereco_ruim(qt_interface, qtbot):
    janela = webhook_amp.JanelaDoWebhook(None, titulo="x", url="https://x/webhook-test/a", chave="s")
    qtbot.addWidget(janela)
    janela.botao_salvar.click()
    assert janela.result() != QDialog.DialogCode.Accepted
    assert "Production URL" in janela.lbl_problema.text()


def test_janela_comeca_com_o_que_ja_existe(qt_interface, qtbot):
    janela = webhook_amp.JanelaDoWebhook(None, titulo="x", url=URL, chave="segredo")
    qtbot.addWidget(janela)
    assert (janela.campo_url.text(), janela.campo_chave.text()) == (URL, "segredo")


def test_cancelar_nao_aceita(qt_interface, qtbot):
    janela = webhook_amp.JanelaDoWebhook(None, titulo="x", url=URL, chave="segredo")
    qtbot.addWidget(janela)
    janela.botao_cancelar.click()
    assert janela.result() == QDialog.DialogCode.Rejected
