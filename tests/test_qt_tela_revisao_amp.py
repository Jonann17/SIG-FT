"""A aba "Revisão no AMP" do PMIB Manager (Qt): as listas marcáveis (todas marcadas; a que tem
falta, sem caixa), o webhook dentro da aba e o log em arquivo. O serviço e o cliente são dublês:
a rodada tem os testes dela em `test_revisao_amp_rodada.py`. Desenho:
`docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`, §5.
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from sigft.app_qt.views import revisao_amp as tela_mod
from sigft.app_qt.views.conferencia_revisoes import UltimaConferencia
from sigft.core import dados_usuario
from sigft.services import conferencia_revisoes as cr
from sigft.services import revisao_amp as ra

URL = "https://ampworkflow.gevernova.net/webhook/sigft-revisao-listas"
CHAVE = "segredo-do-webhook"
CODIGO = "#ITA0=Y01TF001&BPB020"
OUTRO = "#ST00=X01MPB020&MPB020"
TERCEIRO = "#ST00=Z01MPB020&MPB020"
TITULO = "Revisão no AMP"
AVISO_SEM_CHAVE = "Configure o endereço e a chave do webhook no botão Webhook…, nesta aba."
AVISO_TABELA_REFEITA = ("A conferência mudou: a tabela foi refeita com as listas dela. Confira as marcas e "
                        "clique em Revisar no AMP de novo.")


class _Controller:
    def __init__(self, url=URL, chave=CHAVE, **outras):
        self.chaves = {"AMP_REVISAO_LISTAS_URL": url, "AMP_REVISAO_LISTAS_CHAVE": chave, **outras}
        self.gravadas = []

    def get_key(self, nome):
        return self.chaves.get(nome) or ""

    def save_keys(self, novas):
        self.gravadas.append(dict(novas))
        self.chaves.update(novas)


class _ClienteAmp:
    def __init__(self, url, chave, **_kw):
        self.url, self.chave = url, chave


def _lista(tmp_path, codigo, falta=""):
    pasta = tmp_path / codigo[-6:]
    pasta.mkdir(parents=True, exist_ok=True)
    dados = cr.ListaNaMapeadora(codigo, "0B", "Em Processo", "Aprovado", "0A", "x")
    return ra.ListaParaAmp(cr.ItemConferencia(dados, "aprovada", pasta), pasta / "s.xlsx", pasta / "a.pdf",
                           pasta / "b.pdf", "0B", falta)


@pytest.fixture
def ultima(tmp_path):
    mapeadora = cr.Mapeadora(tmp_path / "mapa" / "Mapeamento.xlsx", datetime.now(), [])
    return UltimaConferencia(mapeadora, cr.Conferencia([], em_dia=0, sem_status_pmib=0), [], tmp_path / "raiz")


@pytest.fixture
def servico(monkeypatch, tmp_path):
    """Dublê do serviço: as listas, a rodada e o teste. Guarda o que a tela pediu."""
    falso = SimpleNamespace(listas=[_lista(tmp_path, CODIGO), _lista(tmp_path, OUTRO, "falta: PDF da revisão atual"),
                                    _lista(tmp_path, TERCEIRO)],
                            resultados=None, chamadas=[], testes=[], cancelado=None, rodada=None)

    def listas_para_amp(conferencia, downloads, pasta_mapeadora, pasta_raiz):
        falso.chamadas.append(("listas", pasta_mapeadora, pasta_raiz))
        return falso.listas

    def revisar_listas(listas, cliente, *, versao_sigft, url, chave_posta, log_cb, progress_cb=None,
                       cancelado_cb=None, resultado_cb=None, desmarcadas=(), com_falta=(), **_kw):
        falso.rodada = SimpleNamespace(listas=list(listas), desmarcadas=list(desmarcadas),
                                       com_falta=list(com_falta), url=cliente.url, chave=cliente.chave,
                                       chave_posta=chave_posta)
        falso.cancelado = cancelado_cb
        log_cb("linha da rodada")
        resultados = falso.resultados if falso.resultados is not None else [
            ra.ResultadoAmp(lista, "pronto", lista.item.pasta / "x.html", "x.html") for lista in listas]
        for resultado in resultados:
            resultado_cb(resultado)
        return list(resultados)

    def testar_conexao(cliente):
        falso.testes.append((cliente.url, cliente.chave))
        return ["OK      Ping: workflow 2026-11-03 (HTTP 200, 0,3 s, execução 4)"]

    monkeypatch.setattr(tela_mod.revisao_amp_svc, "listas_para_amp", listas_para_amp)
    monkeypatch.setattr(tela_mod.revisao_amp_svc, "revisar_listas", revisar_listas)
    monkeypatch.setattr(tela_mod.revisao_amp_svc, "testar_conexao", testar_conexao)
    def buscar_pendentes(criar_cliente, log_cb):
        cliente = criar_cliente(URL)
        falso.pendentes_buscados.append((cliente.url, cliente.chave))
        log_cb("pendentes buscados")
        return 1

    falso.pendentes = []
    falso.pendentes_buscados = []
    monkeypatch.setattr(tela_mod.revisao_amp_svc, "ler_pendentes", lambda: list(falso.pendentes))
    monkeypatch.setattr(tela_mod.revisao_amp_svc, "buscar_pendentes", buscar_pendentes)
    monkeypatch.setattr(tela_mod, "ClienteAmp", _ClienteAmp)
    return falso


@pytest.fixture
def avisos(monkeypatch):
    """Os QMessageBox.warning do clique (thread da interface)."""
    lista = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a: lista.append(a[1:])))
    return lista


def _tela(qtbot, *, controller=None, ultima=None, rodando=False):
    fonte = SimpleNamespace(ultima=ultima, rodando=lambda: rodando)
    tela = tela_mod.ModuloRevisaoAmp(controller=controller or _Controller(), fonte=fonte)
    qtbot.addWidget(tela)
    return tela


def _carregada(tela, qtbot):
    tela.atualizar_listas()
    qtbot.waitUntil(lambda: tela.tabela.topLevelItemCount() > 0 and not tela.rodando(), timeout=5000)
    return tela


def _caixas(tela):
    """O estado da caixa de cada linha: True ou False, ou None quando a linha não tem caixa (sem
    estado de marca, o Qt não desenha a caixa)."""
    estados = []
    for i in range(tela.tabela.topLevelItemCount()):
        item = tela.tabela.topLevelItem(i)
        tem_caixa = item.data(0, Qt.ItemDataRole.CheckStateRole) is not None
        estados.append(item.checkState(0) == Qt.CheckState.Checked if tem_caixa else None)
    return estados


def _marcavel(tela, linha):
    return bool(tela.tabela.topLevelItem(linha).flags() & Qt.ItemFlag.ItemIsUserCheckable)


def _coluna_amp(tela):
    return [tela.tabela.topLevelItem(i).text(4) for i in range(tela.tabela.topLevelItemCount())]


def _revisar(tela, qtbot, n):
    tela.btn_amp.click()
    qtbot.waitUntil(lambda: tela.btn_amp.isEnabled() and len(tela.resultados_amp) == n and not tela.rodando(),
                    timeout=5000)


def _no_console(tela, qtbot, texto):
    qtbot.waitUntil(lambda: texto in tela.console.toPlainText(), timeout=5000)


# ------------------------------------------------------------------ as listas

def test_listas_aparecem_todas_marcadas_e_a_com_falta_sem_caixa(qt_interface, qtbot, servico, ultima):
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    assert _caixas(tela) == [True, None, True]
    assert [_marcavel(tela, i) for i in range(3)] == [True, False, True]
    assert _coluna_amp(tela)[1] == "falta: PDF da revisão atual"
    assert servico.chamadas == [("listas", ultima.mapeadora.caminho.parent, ultima.pasta_raiz)]
    _no_console(tela, qtbot, "3 lista(s) na conferência; 2 podem ir ao AMP, 1 com falta")


def test_marcar_e_desmarcar_todas(qt_interface, qtbot, servico, ultima):
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    tela.btn_desmarcar.click()
    assert _caixas(tela) == [False, None, False]
    tela.btn_marcar.click()
    assert _caixas(tela) == [True, None, True]


def test_a_tabela_nao_enche_com_a_conferencia_rodando(qt_interface, qtbot, servico, ultima):
    tela = _tela(qtbot, ultima=ultima, rodando=True)
    tela.atualizar_listas()
    assert servico.chamadas == [] and tela.tabela.topLevelItemCount() == 0


# ------------------------------------------------------------------ a rodada

def test_so_as_marcadas_vao(qt_interface, qtbot, servico, ultima):
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    tela.tabela.topLevelItem(2).setCheckState(0, Qt.CheckState.Unchecked)
    _revisar(tela, qtbot, 1)
    assert [lista.item.lista.codigo for lista in servico.rodada.listas] == [CODIGO]
    assert (servico.rodada.desmarcadas, servico.rodada.com_falta) == ([TERCEIRO], [OUTRO])
    assert (servico.rodada.url, servico.rodada.chave, servico.rodada.chave_posta) == (URL, CHAVE, True)


def test_as_caixas_travam_durante_a_rodada(qt_interface, qtbot, servico, ultima):
    # A tabela diz o que foi mandado: no meio da rodada, nada se marca nem se desmarca. O fim da
    # rodada (`_terminar`) só roda quando o laço da interface anda, depois destas linhas.
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    tela.btn_amp.click()
    assert not tela.btn_marcar.isEnabled() and not tela.btn_desmarcar.isEnabled()
    assert not _marcavel(tela, 0) and not _marcavel(tela, 2)
    qtbot.waitUntil(lambda: tela.btn_amp.isEnabled() and len(tela.resultados_amp) == 2 and not tela.rodando(),
                    timeout=5000)
    assert tela.btn_marcar.isEnabled() and _marcavel(tela, 0) and not _marcavel(tela, 1)


def test_nenhuma_marcada_avisa_e_nao_chama(qt_interface, qtbot, servico, avisos, ultima):
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    tela.btn_desmarcar.click()
    tela.btn_amp.click()
    assert avisos == [(TITULO, "Marque ao menos uma lista para mandar ao AMP.")]
    assert servico.rodada is None


def test_a_pronta_e_desmarcada_ao_fim(qt_interface, qtbot, servico, ultima):
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    _revisar(tela, qtbot, 2)
    assert _caixas(tela) == [False, None, False]
    assert _coluna_amp(tela) == ["HTML pronto: x.html", "falta: PDF da revisão atual", "HTML pronto: x.html"]
    assert not tela.btn_copiar_diag.isEnabled()


def test_a_que_falhou_continua_marcada_e_liga_o_copiar(qt_interface, qtbot, servico, ultima):
    a, _b, c = servico.listas
    servico.resultados = [ra.ResultadoAmp(a, "falhou", None, "model timeout (etapa agente)", "DIAGNOSTICO-A\n"),
                          ra.ResultadoAmp(c, "pronto", c.item.pasta / "x.html", "x.html")]
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    _revisar(tela, qtbot, 2)
    assert _caixas(tela) == [True, None, False]
    assert _coluna_amp(tela)[0] == "falhou: model timeout (etapa agente)"
    assert tela.btn_copiar_diag.isEnabled()
    tela.btn_copiar_diag.click()
    texto = QApplication.clipboard().text()
    assert texto == ra.diagnosticos_para_copiar(tela.resultados_amp) and "DIAGNOSTICO-A" in texto


def test_conferencia_nova_refaz_a_tabela_e_nao_manda(qt_interface, qtbot, servico, avisos, ultima, tmp_path):
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    tela.fonte.ultima = UltimaConferencia(ultima.mapeadora, ultima.conferencia, [], tmp_path / "outra")
    tela.btn_amp.click()
    assert avisos == [(TITULO, AVISO_TABELA_REFEITA)]
    assert servico.rodada is None
    qtbot.waitUntil(lambda: len(servico.chamadas) == 2 and not tela.rodando(), timeout=5000)
    assert _caixas(tela) == [True, None, True]


def test_parar_vale_para_a_rodada(qt_interface, qtbot, servico, ultima):
    servico.resultados = [ra.ResultadoAmp(servico.listas[0], "parado", None, "parado antes de ir ao AMP")]
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    _revisar(tela, qtbot, 1)
    assert servico.cancelado() is False
    tela.btn_parar.click()
    assert servico.cancelado() is True
    assert _coluna_amp(tela)[0] == "parado"


def test_dois_cliques_abrem_o_html(qt_interface, qtbot, servico, ultima, monkeypatch):
    abertos = []
    monkeypatch.setattr(tela_mod.plataforma, "abrir_no_sistema", abertos.append)
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    _revisar(tela, qtbot, 2)
    tela.tabela.itemDoubleClicked.emit(tela.tabela.topLevelItem(0), 0)
    tela.tabela.itemDoubleClicked.emit(tela.tabela.topLevelItem(1), 0)
    assert abertos == [servico.listas[0].item.pasta / "x.html"]


def test_o_botao_da_pasta_abre_a_pasta_da_lista(qt_interface, qtbot, servico, ultima, monkeypatch):
    abertos = []
    monkeypatch.setattr(tela_mod.plataforma, "abrir_no_sistema", abertos.append)
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    botoes = [tela.tabela.itemWidget(tela.tabela.topLevelItem(i), tela_mod.COLUNA_PASTA) for i in range(3)]
    assert all(b is not None and b.text() == "Abrir Pasta" for b in botoes)
    botoes[2].click()
    assert abertos == [servico.listas[2].item.pasta]


def test_conferencia_rodando_avisa_e_nao_chama(qt_interface, qtbot, servico, avisos, ultima):
    tela = _tela(qtbot, ultima=ultima, rodando=True)
    tela.btn_amp.click()
    assert avisos == [(TITULO, "A conferência ainda está rodando: espere ela terminar.")]
    assert servico.rodada is None


def test_sem_conferencia_avisa(qt_interface, qtbot, servico, avisos):
    tela = _tela(qtbot, ultima=None)
    tela.btn_amp.click()
    assert avisos == [(TITULO, "Confira as revisões antes.")]
    assert servico.rodada is None


def test_rodada_grava_o_log_em_arquivo(qt_interface, qtbot, servico, ultima):
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    _revisar(tela, qtbot, 2)
    [arquivo] = list((dados_usuario.pasta_logs() / "amp").glob("amp_revisao_*.log"))
    texto = arquivo.read_text(encoding="utf-8")
    assert "linha da rodada" in texto and URL in texto and CHAVE not in texto
    _no_console(tela, qtbot, f"Log em arquivo: {arquivo}")
    assert CHAVE not in tela.console.toPlainText()


# ------------------------------------------------------------------ o webhook

@pytest.mark.parametrize("url, chave", [("", "segredo"), (URL, ""), ("", "")])
def test_sem_webhook_avisa_e_nao_chama(qt_interface, qtbot, servico, avisos, ultima, url, chave):
    tela = _tela(qtbot, controller=_Controller(url, chave), ultima=ultima)
    tela.btn_amp.click()
    tela.btn_testar_amp.click()
    assert avisos == [(TITULO, AVISO_SEM_CHAVE)] * 2
    assert servico.rodada is None and servico.testes == []


def test_mostra_o_endereco_e_nunca_a_chave(qt_interface, qtbot, ultima):
    tela = _tela(qtbot, ultima=ultima)
    assert URL in tela.lbl_webhook.text() and CHAVE not in tela.lbl_webhook.text()
    sem = _tela(qtbot, controller=_Controller("", ""), ultima=ultima)
    assert sem.lbl_webhook.text() == "Webhook do AMP não configurado: clique em Webhook…, nesta aba."


def test_adota_o_webhook_de_antes(qt_interface, qtbot, ultima):
    controller = _Controller("", "", AMP_WEBHOOK_URL=URL, AMP_WEBHOOK_CHAVE=CHAVE)
    tela = _tela(qtbot, controller=controller, ultima=ultima)
    assert URL in tela.lbl_webhook.text()
    assert controller.gravadas == [{"AMP_REVISAO_LISTAS_URL": URL, "AMP_REVISAO_LISTAS_CHAVE": CHAVE}]


class _Janela:
    """Dublê da `JanelaDoWebhook`: guarda como foi aberta e responde o que o teste pôs."""
    resposta = QDialog.DialogCode.Accepted
    valores_novos = ("https://ampworkflow.gevernova.net/webhook/outro", "nova-chave")
    aberta = None

    def __init__(self, parent, *, titulo, url="", chave=""):
        type(self).aberta = (titulo, url, chave)

    def exec(self):
        return type(self).resposta

    def valores(self):
        return type(self).valores_novos


def test_janela_do_webhook_grava_no_modulo(qt_interface, qtbot, ultima, monkeypatch):
    monkeypatch.setattr(tela_mod.webhook_amp, "JanelaDoWebhook", _Janela)
    monkeypatch.setattr(_Janela, "resposta", QDialog.DialogCode.Accepted)
    controller = _Controller()
    tela = _tela(qtbot, controller=controller, ultima=ultima)
    tela.btn_webhook.click()
    assert _Janela.aberta == ("Webhook da Revisão no AMP", URL, CHAVE)
    assert controller.gravadas == [{"AMP_REVISAO_LISTAS_URL": "https://ampworkflow.gevernova.net/webhook/outro",
                                    "AMP_REVISAO_LISTAS_CHAVE": "nova-chave"}]
    assert "webhook/outro" in tela.lbl_webhook.text()
    _no_console(tela, qtbot, "Webhook da Revisão no AMP salvo: https://ampworkflow.gevernova.net/webhook/outro "
                             "· chave posta")
    assert "nova-chave" not in tela.console.toPlainText()


def test_janela_cancelada_nao_grava(qt_interface, qtbot, ultima, monkeypatch):
    monkeypatch.setattr(tela_mod.webhook_amp, "JanelaDoWebhook", _Janela)
    monkeypatch.setattr(_Janela, "resposta", QDialog.DialogCode.Rejected)
    controller = _Controller()
    tela = _tela(qtbot, controller=controller, ultima=ultima)
    tela.btn_webhook.click()
    assert controller.gravadas == []


# ------------------------------------------------------------------ o teste de conexão

def test_testar_conexao_escreve_e_grava(qt_interface, qtbot, servico):
    tela = _tela(qtbot, ultima=None)
    tela.btn_testar_amp.click()
    _no_console(tela, qtbot, "OK      Ping: workflow 2026-11-03")
    assert f"Testando o AMP: {URL} · chave posta" in tela.console.toPlainText()
    assert servico.testes == [(URL, CHAVE)]
    qtbot.waitUntil(lambda: not tela.rodando(), timeout=5000)
    [arquivo] = list((dados_usuario.pasta_logs() / "amp").glob("amp_teste_*.log"))
    texto = arquivo.read_text(encoding="utf-8")
    assert "OK      Ping" in texto and CHAVE not in texto


# ------------------------------------------------------------------ os resultados que ficaram no AMP

def test_a_aba_busca_os_pendentes_e_nao_repete_logo_em_seguida(qt_interface, qtbot, servico, ultima):
    servico.pendentes = [{"pedido": "700"}]
    tela = _tela(qtbot, ultima=ultima)
    tela.buscar_pendentes()
    qtbot.waitUntil(lambda: servico.pendentes_buscados and not tela.rodando(), timeout=5000)
    assert servico.pendentes_buscados == [(URL, CHAVE)]
    tela.buscar_pendentes()
    assert servico.pendentes_buscados == [(URL, CHAVE)]


def test_sem_pendentes_nao_pergunta(qt_interface, qtbot, servico, ultima):
    tela = _tela(qtbot, ultima=ultima)
    tela.buscar_pendentes()
    assert servico.pendentes_buscados == [] and not tela.rodando()


def test_a_que_ficou_no_amp_se_desmarca(qt_interface, qtbot, servico, ultima):
    a, _b, c = servico.listas
    servico.resultados = [ra.ResultadoAmp(a, "pendente", None, "no AMP: o HTML é buscado depois (pedido 700)"),
                          ra.ResultadoAmp(c, "falhou", None, "model timeout", "D\n")]
    tela = _carregada(_tela(qtbot, ultima=ultima), qtbot)
    _revisar(tela, qtbot, 2)
    assert _caixas(tela) == [False, None, True]
    assert _coluna_amp(tela)[0] == "no AMP: o HTML é buscado depois (pedido 700)"
