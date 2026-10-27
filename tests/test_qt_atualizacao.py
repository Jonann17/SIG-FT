"""A atualizacao automatica na interface Qt (`sigft/app_qt/atualizacao.py`).

Espelho de `tests/test_atualizacao_na_abertura.py` (a interface antiga):
o mesmo comportamento -- a abertura pergunta calada, o botao "Atualizacoes"
sempre responde, o aviso baixa, instala e so entao fecha o app -- com o canal
thread -> interface do Qt (`interface.na_interface`). Rede e servico dublados:
nenhum teste daqui toca no GitHub.
"""
import threading
import time

import pytest

from sigft import _build_info
from sigft.app import atualizacao_textos as textos
from sigft.app_qt import atualizacao
from sigft.core import rede
from sigft.services import updater


def _sincrono(alvo, *args):
    """No lugar da thread: roda na hora. O que o codigo AGENDA com
    `na_interface` continua na fila ate o laco de eventos rodar -- e isso que
    prova que nada toca em widget fora da thread da interface."""
    alvo(*args)


def _info(**extra):
    base = dict(
        versao="1.2.0",
        notas="- **Upload:** agora salva `sozinho`\n- segundo item",
        nome_arquivo="SIG-FT_Itaipu_Setup_1.2.0.exe",
        url_asset="https://api.github.com/repos/luanccozer/SIG-FT/releases/assets/1",
        tamanho=110_201_576,
        sha256="ab" * 32,
        url_pagina="https://github.com/luanccozer/SIG-FT/releases/tag/v1.2.0",
        publicado_em="2026-09-25",
    )
    base.update(extra)
    return updater.Atualizacao(**base)


@pytest.fixture
def raiz(qt_interface, qtbot):
    from PySide6.QtWidgets import QMainWindow

    janela = QMainWindow()
    qtbot.addWidget(janela)
    return janela


@pytest.fixture
def processar(qt_interface):
    def rodar():
        for _ in range(5):
            qt_interface.processEvents()
    return rodar


@pytest.fixture(autouse=True)
def limpezas(monkeypatch):
    """A limpeza da pasta de downloads, dublada: teste não mexe no %TEMP% real."""
    chamadas = []
    monkeypatch.setattr(updater, "limpar_downloads", lambda **kw: chamadas.append(kw) or 0)
    return chamadas


@pytest.fixture
def caixas(monkeypatch):
    """As caixas de mensagem do Qt sao modais (bloqueiam): dubladas."""
    chamadas = []
    for metodo, tipo in (("information", "info"), ("warning", "warning")):
        monkeypatch.setattr(
            atualizacao.QMessageBox, metodo,
            staticmethod(lambda pai, titulo, msg, *a, _t=tipo: chamadas.append((_t, titulo, msg))))
    return chamadas


@pytest.fixture
def sem_uac(monkeypatch):
    monkeypatch.setattr(updater, "precisa_elevacao", lambda: False)


def _aviso(raiz, qtbot, **kw):
    kw.setdefault("disparar", _sincrono)
    kw.setdefault("fechar_app", lambda janela: pytest.fail("fechou o app"))
    kw.setdefault("tarefas_em_andamento", lambda: [])
    aviso = atualizacao.JanelaAtualizacao(raiz, info=kw.pop("info", _info()),
                                          versao_atual="1.1.0", **kw)
    qtbot.addWidget(aviso)
    return aviso


def _textos(widget):
    from PySide6.QtWidgets import QLabel, QPushButton

    achados = widget.findChildren(QLabel) + widget.findChildren(QPushButton)
    return [w.text() for w in achados if w.text()]


# =============================================================================
# A. A janela principal Qt pergunta na abertura (a causa raiz de 2026-09-25)
# =============================================================================

@pytest.fixture
def chaves_tmp(monkeypatch, tmp_path):
    from sigft.app_qt import main as qmain

    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    return qmain


def test_abrir_o_app_qt_PERGUNTA_ao_github_pela_versao_nova(monkeypatch, qt_interface, qtbot,
                                                             chaves_tmp):
    perguntas = []
    monkeypatch.setattr(updater, "deve_verificar", lambda *a, **k: True)
    monkeypatch.setattr(updater, "checar", lambda versao, **kw: perguntas.append(versao))

    janela = chaves_tmp.SIG_FT_App()
    qtbot.addWidget(janela)

    qtbot.waitUntil(lambda: bool(perguntas), timeout=5000)
    assert perguntas == [_build_info.VERSAO]


def test_a_pergunta_do_app_qt_NAO_segura_a_abertura(monkeypatch, qt_interface, qtbot, chaves_tmp):
    liberar = threading.Event()
    comecou = threading.Event()

    def checar_lento(versao, **kw):
        comecou.set()
        liberar.wait(5)

    monkeypatch.setattr(updater, "deve_verificar", lambda *a, **k: True)
    monkeypatch.setattr(updater, "checar", checar_lento)

    inicio = time.monotonic()
    janela = chaves_tmp.SIG_FT_App()
    qtbot.addWidget(janela)
    duracao = time.monotonic() - inicio
    liberar.set()

    assert comecou.wait(5), "a consulta nem comecou"
    assert duracao < 2, f"a janela levou {duracao:.1f}s para montar: a consulta a segurou"


def test_a_thread_da_consulta_e_DAEMON_e_nao_vira_tarefa(monkeypatch, qt_interface):
    """Fechar a janela encerra o processo; thread comum viva faz o "X"
    perguntar por "tarefa em andamento". A consulta nao e tarefa da pessoa."""
    from sigft.core import instancia

    vista = {}
    liberar = threading.Event()

    def checar(versao, **kw):
        vista["daemon"] = threading.current_thread().daemon
        vista["tarefas"] = instancia.tarefas_em_andamento()
        liberar.wait(5)

    monkeypatch.setattr(updater, "deve_verificar", lambda: True)
    monkeypatch.setattr(updater, "checar", checar)
    try:
        atualizacao.verificar_na_abertura(object())
        limite = time.monotonic() + 5
        while "daemon" not in vista and time.monotonic() < limite:
            time.sleep(0.01)
    finally:
        liberar.set()
    assert vista["daemon"] is True
    assert vista["tarefas"] == []


def test_a_abertura_LIMPA_os_instaladores_de_atualizacoes_anteriores(monkeypatch, raiz, processar,
                                                                    caixas, limpezas):
    # 2026-10-19: cada atualização deixava o instalador (até 326 MB) no %TEMP%.
    monkeypatch.setattr(updater, "deve_verificar", lambda: True)
    monkeypatch.setattr(updater, "checar", lambda versao, **kw: None)

    atualizacao.verificar_na_abertura(raiz, versao_atual="1.1.0", disparar=_sincrono)

    assert len(limpezas) == 1


def test_limpeza_que_falha_nao_impede_a_consulta(monkeypatch, raiz, processar, caixas):
    perguntas = []
    monkeypatch.setattr(updater, "deve_verificar", lambda: True)
    monkeypatch.setattr(updater, "limpar_downloads", lambda **kw: 1 / 0)
    monkeypatch.setattr(updater, "checar", lambda versao, **kw: perguntas.append(versao))

    atualizacao.verificar_na_abertura(raiz, versao_atual="1.1.0", disparar=_sincrono)

    assert perguntas == ["1.1.0"]


def test_sem_permissao_da_politica_a_abertura_nao_toca_na_rede(monkeypatch, raiz):
    monkeypatch.setattr(updater, "deve_verificar", lambda: False)
    disparou = []
    assert not atualizacao.verificar_na_abertura(raiz, disparar=lambda *a: disparou.append(a))
    assert disparou == []


# =============================================================================
# B. A pergunta da abertura: responde so quando ha o que oferecer
# =============================================================================

def test_versao_nova_abre_o_aviso_PELA_thread_da_interface(monkeypatch, raiz, processar, sem_uac):
    monkeypatch.setattr(updater, "deve_verificar", lambda: True)
    monkeypatch.setattr(updater, "checar", lambda versao, **kw: _info())

    assert atualizacao.verificar_na_abertura(raiz, versao_atual="1.1.0", disparar=_sincrono)
    assert getattr(raiz, "_janela_de_atualizacao", None) is None, (
        "o aviso foi criado de dentro da thread da consulta")

    processar()

    aviso = raiz._janela_de_atualizacao
    assert isinstance(aviso, atualizacao.JanelaAtualizacao)
    assert aviso.info.versao == "1.2.0"
    assert aviso.isVisible()


def test_aviso_vindo_de_uma_THREAD_DE_VERDADE(monkeypatch, raiz, qtbot, sem_uac):
    monkeypatch.setattr(updater, "deve_verificar", lambda: True)
    monkeypatch.setattr(updater, "checar", lambda versao, **kw: _info())

    atualizacao.verificar_na_abertura(raiz, versao_atual="1.1.0")

    qtbot.waitUntil(lambda: getattr(raiz, "_janela_de_atualizacao", None) is not None,
                    timeout=5000)


def test_ja_em_dia_a_abertura_fica_CALADA(monkeypatch, raiz, processar, caixas):
    monkeypatch.setattr(updater, "deve_verificar", lambda: True)
    monkeypatch.setattr(updater, "checar", lambda versao, **kw: None)

    atualizacao.verificar_na_abertura(raiz, disparar=_sincrono)
    processar()

    assert caixas == []
    assert getattr(raiz, "_janela_de_atualizacao", None) is None


def test_falha_na_abertura_fica_calada_mas_VAI_PARA_O_LOG(monkeypatch, raiz, processar, caixas,
                                                          capsys):
    def falha(versao, **kw):
        raise rede.FalhaDeRede("Nenhuma rota de rede funcionou.")

    monkeypatch.setattr(updater, "deve_verificar", lambda: True)
    monkeypatch.setattr(updater, "checar", falha)

    atualizacao.verificar_na_abertura(raiz, disparar=_sincrono)
    processar()

    assert caixas == []
    assert "Nenhuma rota de rede funcionou" in capsys.readouterr().out


# =============================================================================
# C. O botao "Atualizacoes": a mesma pergunta, que SEMPRE responde
# =============================================================================

@pytest.fixture
def pode_verificar(monkeypatch):
    monkeypatch.setattr(updater, "motivo_para_nao_verificar", lambda: None)


def test_o_botao_diz_quando_ja_esta_na_mais_recente(monkeypatch, raiz, processar, caixas,
                                                    pode_verificar):
    monkeypatch.setattr(updater, "checar", lambda versao, **kw: None)
    terminou = []

    atualizacao.procurar_agora(raiz, versao_atual="1.2.0", disparar=_sincrono,
                               ao_terminar=lambda: terminou.append(True))
    assert terminou == [], "o ao_terminar roda na thread da interface, nao na da consulta"
    processar()

    assert terminou == [True]
    assert caixas == [("info", textos.TITULO,
                       "Você já está na versão mais recente (v1.2.0).")]


def test_o_botao_MOSTRA_o_erro_que_a_abertura_engole(monkeypatch, raiz, processar, caixas,
                                                     pode_verificar):
    def recusado(versao, **kw):
        raise updater.SemToken("O GitHub recusou o token de atualizacao deste build (HTTP 401).")

    monkeypatch.setattr(updater, "checar", recusado)

    atualizacao.procurar_agora(raiz, disparar=_sincrono)
    processar()

    [(tipo, titulo, mensagem)] = caixas
    assert (tipo, titulo) == ("warning", textos.TITULO)
    assert mensagem.startswith("Não foi possível procurar atualizações.\n\n")
    assert "recusou o token" in mensagem


def test_o_botao_explica_por_que_esta_copia_nao_se_atualiza(monkeypatch, raiz, caixas):
    monkeypatch.setattr(updater, "motivo_para_nao_verificar",
                        lambda: "Este SIG-FT roda pelo codigo-fonte (SIG-FT.bat).")
    monkeypatch.setattr(updater, "checar",
                        lambda *a, **k: pytest.fail("perguntou ao GitHub sem poder instalar"))
    terminou = []

    atualizacao.procurar_agora(raiz, versao_atual="1.2.0", disparar=_sincrono,
                               ao_terminar=lambda: terminou.append(True))

    assert terminou == [True]
    assert caixas == [("info", textos.TITULO,
                       "Você está na v1.2.0.\n\nEste SIG-FT roda pelo codigo-fonte (SIG-FT.bat).")]


def test_o_botao_volta_ao_normal_ANTES_da_mensagem(monkeypatch, raiz, processar, pode_verificar):
    ordem = []
    monkeypatch.setattr(updater, "checar", lambda versao, **kw: None)
    monkeypatch.setattr(atualizacao.QMessageBox, "information",
                        staticmethod(lambda *a, **k: ordem.append("mensagem")))

    atualizacao.procurar_agora(raiz, disparar=_sincrono,
                               ao_terminar=lambda: ordem.append("botao"))
    processar()

    assert ordem == ["botao", "mensagem"]


def test_com_versao_nova_o_botao_abre_o_MESMO_aviso(monkeypatch, raiz, processar, caixas,
                                                    pode_verificar, sem_uac):
    monkeypatch.setattr(updater, "checar", lambda versao, **kw: _info())

    atualizacao.procurar_agora(raiz, disparar=_sincrono)
    processar()

    assert isinstance(raiz._janela_de_atualizacao, atualizacao.JanelaAtualizacao)
    assert caixas == []


def test_o_aviso_NAO_abre_duas_vezes(raiz, sem_uac, qtbot):
    primeiro = atualizacao._mostrar_aviso(raiz, _info(), "1.1.0")
    segundo = atualizacao._mostrar_aviso(raiz, _info(), "1.1.0")

    assert segundo is primeiro

    primeiro.agora_nao()
    terceiro = atualizacao._mostrar_aviso(raiz, _info(), "1.1.0")

    assert terceiro is not primeiro, "fechado o aviso, a proxima resposta abre outro"
    terceiro.agora_nao()


# =============================================================================
# D. A janela do aviso
# =============================================================================

def test_o_aviso_mostra_a_versao_nova_a_atual_e_o_que_mudou(raiz, qtbot, sem_uac):
    aviso = _aviso(raiz, qtbot)
    todos = " | ".join(_textos(aviso))

    assert "Nova versão disponível: v1.2.0" in todos
    assert "v1.1.0" in todos
    assert "25/09/2026" in todos
    assert textos.MSG_COMO_FUNCIONA in todos
    assert aviso.windowTitle() == textos.TITULO
    assert aviso.caixa_notas.toPlainText() == textos.notas_para_exibir(_info().notas)
    assert aviso.caixa_notas.isReadOnly(), "as notas sao para ler, nao para editar"
    assert aviso.botao_atualizar.text() == "Atualizar agora"
    assert aviso.botao_agora_nao.text() == "Agora não"


def test_versao_de_teste_e_dita_no_titulo(raiz, qtbot, sem_uac):
    aviso = _aviso(raiz, qtbot, info=_info(versao="1.2.0-rc.3", prerelease=True))

    assert "Nova versão de teste disponível: v1.2.0-rc.3" in _textos(aviso)


def test_o_aviso_e_MODAL_e_fica_por_cima(raiz, qtbot, sem_uac):
    """Atualizar FECHA o app: com o aviso aberto, nada de comecar um lote na
    tela de tras."""
    from PySide6.QtCore import Qt

    aviso = _aviso(raiz, qtbot)

    assert aviso.windowModality() == Qt.WindowModality.ApplicationModal
    assert aviso.parent() is raiz
    assert aviso.windowFlags() & Qt.WindowType.WindowStaysOnTopHint


def test_agora_nao_e_o_X_e_o_Esc_fecham_SEM_baixar(monkeypatch, raiz, qtbot, sem_uac):
    monkeypatch.setattr(updater, "baixar", lambda *a, **k: pytest.fail("baixou sem ninguem pedir"))

    aviso = _aviso(raiz, qtbot)
    aviso.show()
    aviso.botao_agora_nao.click()
    assert aviso.fechada and not aviso.isVisible()

    outro = _aviso(raiz, qtbot)
    outro.show()
    outro.close()
    assert outro.fechada and not outro.isVisible()

    terceiro = _aviso(raiz, qtbot)
    terceiro.show()
    terceiro.reject()   # o Esc
    assert terceiro.fechada and not terceiro.isVisible()


def test_atualizar_BAIXA_INSTALA_e_so_entao_FECHA_o_app(monkeypatch, raiz, qtbot, processar,
                                                        sem_uac, tmp_path):
    eventos = []
    baixado = tmp_path / "SIG-FT_Itaipu_Setup_1.2.0.exe"

    def baixar(info, *, progresso_cb, log_cb, ao_cair_no_completo):
        eventos.append("baixou")
        progresso_cb(0.5)
        progresso_cb(1.0)
        return baixado

    monkeypatch.setattr(updater, "baixar", baixar)
    monkeypatch.setattr(updater, "instalar",
                        lambda caminho, **kw: eventos.append(("instalou", caminho)))

    aviso = _aviso(raiz, qtbot, fechar_app=lambda janela: eventos.append(("fechou", janela)))
    aviso.botao_atualizar.click()
    assert aviso.botao_atualizar.text() == "Atualizando..."
    assert not aviso.botao_atualizar.isEnabled() and not aviso.botao_agora_nao.isEnabled()
    processar()

    assert eventos == ["baixou", ("instalou", baixado), ("fechou", raiz)]
    assert aviso.barra.value() == 100
    assert aviso.rotulo_status.text() == textos.MSG_DOWNLOAD_CONFERIDO


# -- "Atualizar agora" com um robo rodando -----------------------------------
# O app fecha sozinho quando o download termina (`instancia.encerrar`), e um
# robo no meio do lote morre ali, com uma planilha que pode estar sendo
# gravada. O "X" da janela principal ja pergunta; o "Atualizar agora" tambem.

def _pergunta(monkeypatch, resposta):
    from PySide6.QtWidgets import QMessageBox

    perguntas = []

    def question(pai, titulo, msg, botoes, padrao):
        perguntas.append((pai, titulo, msg, padrao))
        return resposta
    monkeypatch.setattr(atualizacao.QMessageBox, "question", staticmethod(question))
    return perguntas, QMessageBox.StandardButton


def test_com_tarefa_em_andamento_atualizar_PERGUNTA_e_o_nao_nao_baixa(
        monkeypatch, raiz, qtbot, sem_uac):
    from PySide6.QtWidgets import QMessageBox

    perguntas, botao = _pergunta(monkeypatch, QMessageBox.StandardButton.No)
    disparos = []
    aviso = _aviso(raiz, qtbot, disparar=lambda *a: disparos.append(a),
                   tarefas_em_andamento=lambda: ["robo-upload"])
    aviso.show()
    aviso.botao_atualizar.click()

    assert len(perguntas) == 1
    pai, titulo, msg, padrao = perguntas[0]
    assert pai is aviso and titulo == textos.TITULO
    assert msg == textos.MSG_TAREFA_AO_ATUALIZAR
    assert padrao == botao.No, "acao que interrompe trabalho: Enter responde Nao"
    assert disparos == [], "respondeu Nao e o download comecou mesmo assim"
    assert aviso.botao_atualizar.isEnabled() and aviso.botao_agora_nao.isEnabled()
    assert aviso.botao_atualizar.text() == textos.TEXTO_ATUALIZAR
    assert not aviso._baixando and aviso.isVisible()


def test_com_tarefa_em_andamento_o_sim_baixa_como_antes(monkeypatch, raiz, qtbot, sem_uac):
    from PySide6.QtWidgets import QMessageBox

    perguntas, _ = _pergunta(monkeypatch, QMessageBox.StandardButton.Yes)
    disparos = []
    aviso = _aviso(raiz, qtbot, disparar=lambda alvo, *a: disparos.append(alvo),
                   tarefas_em_andamento=lambda: ["robo-upload"])
    aviso.show()
    aviso.botao_atualizar.click()

    assert len(perguntas) == 1
    assert disparos == [aviso._baixar_e_instalar]
    assert aviso.botao_atualizar.text() == textos.TEXTO_ATUALIZANDO
    aviso._baixando = False


def test_sem_tarefa_em_andamento_atualizar_NAO_pergunta(monkeypatch, raiz, qtbot, sem_uac):
    perguntas, _ = _pergunta(monkeypatch, None)
    disparos = []
    aviso = _aviso(raiz, qtbot, disparar=lambda alvo, *a: disparos.append(alvo))
    aviso.show()
    aviso.botao_atualizar.click()

    assert perguntas == []
    assert disparos == [aviso._baixar_e_instalar]
    aviso._baixando = False


def test_por_padrao_o_aviso_olha_as_tarefas_da_instancia(monkeypatch, raiz, qtbot, sem_uac):
    from PySide6.QtWidgets import QMessageBox

    from sigft.core import instancia

    monkeypatch.setattr(instancia, "tarefas_em_andamento", lambda: ["robo"])
    perguntas, _ = _pergunta(monkeypatch, QMessageBox.StandardButton.No)
    aviso = atualizacao.JanelaAtualizacao(raiz, info=_info(), versao_atual="1.1.0",
                                          disparar=lambda *a: pytest.fail("baixou"))
    qtbot.addWidget(aviso)
    aviso.show()
    aviso.botao_atualizar.click()

    assert len(perguntas) == 1


def test_o_status_diz_o_que_esta_baixando(raiz, qtbot, sem_uac):
    aviso = _aviso(raiz, qtbot, disparar=lambda *a: None)
    aviso.botao_atualizar.click()

    assert aviso.rotulo_status.text() == "Baixando a v1.2.0 (105,1 MB)..."


def test_download_que_falha_NAO_fecha_o_app_e_deixa_tentar_de_novo(monkeypatch, raiz, qtbot,
                                                                  processar, sem_uac):
    def falha(*a, **k):
        raise updater.ArquivoInvalido("O arquivo baixado e pequeno demais para ser o instalador")

    monkeypatch.setattr(updater, "baixar", falha)
    monkeypatch.setattr(updater, "instalar",
                        lambda *a, **k: pytest.fail("instalou um download que falhou"))

    aviso = _aviso(raiz, qtbot)
    aviso.show()
    aviso.botao_atualizar.click()
    processar()

    assert "pequeno demais" in aviso.rotulo_status.text()
    assert aviso.botao_atualizar.isEnabled()
    assert aviso.botao_atualizar.text() == "Tentar de novo"
    assert aviso.botao_agora_nao.isEnabled()
    assert aviso.barra.value() == 0
    aviso.close()
    assert aviso.fechada, "depois da falha, o X volta a fechar o aviso"


def test_quando_o_pequeno_falha_a_janela_DIZ_que_baixa_o_completo(monkeypatch, raiz, qtbot,
                                                                 processar, sem_uac, tmp_path):
    completo = _info(tamanho=316_197_094)
    vistos = []

    def baixar(info, *, progresso_cb, log_cb, ao_cair_no_completo):
        progresso_cb(0.97)
        ao_cair_no_completo(completo)
        progresso_cb(0.0)
        processar()
        vistos.append((aviso.rotulo_status.text(), aviso.barra.value()))
        return tmp_path / "Setup.exe"

    monkeypatch.setattr(updater, "baixar", baixar)
    monkeypatch.setattr(updater, "instalar", lambda *a, **k: None)
    aviso = _aviso(raiz, qtbot, fechar_app=lambda janela: None,
                   info=_info(nome_arquivo="SIG-FT_Itaipu_Atualizacao_1.1.0_para_1.2.0.bin",
                              tamanho=38_518_933, incremental=True, tamanho_completo=316_197_094))
    aviso.botao_atualizar.click()
    processar()

    texto, barra = vistos[0]
    assert "pequena falhou" in texto
    assert "instalador completo (301,5 MB)" in texto
    assert barra == 0


def test_instalador_que_NAO_SOBE_nao_fecha_o_app(monkeypatch, raiz, qtbot, processar, sem_uac,
                                                 tmp_path):
    monkeypatch.setattr(updater, "baixar", lambda *a, **k: tmp_path / "Setup.exe")

    def recusado(*a, **k):
        raise RuntimeError("Voce recusou o pedido do Windows.")

    monkeypatch.setattr(updater, "instalar", recusado)

    aviso = _aviso(raiz, qtbot)
    aviso.botao_atualizar.click()
    processar()

    assert "recusou" in aviso.rotulo_status.text()


def test_o_X_e_o_Esc_no_meio_do_download_NAO_fecham(raiz, qtbot, sem_uac):
    pendente = []
    aviso = _aviso(raiz, qtbot, disparar=lambda alvo, *a: pendente.append(alvo))
    aviso.show()

    aviso.botao_atualizar.click()
    aviso.close()
    aviso.reject()

    assert aviso.isVisible() and not aviso.fechada
    assert pendente, "o download devia ter sido disparado"
    assert not aviso.botao_atualizar.isEnabled()


def test_a_barra_so_aparece_quando_o_download_comeca(raiz, qtbot, sem_uac):
    aviso = _aviso(raiz, qtbot, disparar=lambda *a: None)
    aviso.show()

    assert not aviso.barra.isVisible(), "parada em zero, parece download travado"

    aviso.botao_atualizar.click()

    assert aviso.barra.isVisible()


def test_erro_enorme_e_ENCURTADO_na_tela_e_aponta_o_log(raiz, qtbot, sem_uac):
    aviso = _aviso(raiz, qtbot)

    aviso._falhou(RuntimeError("Nenhuma rota de rede funcionou. " + "x" * 3000))

    texto = aviso.rotulo_status.text()
    assert "Nenhuma rota de rede funcionou." in texto
    assert len(texto) < 900
    assert "log" in texto


def test_o_progresso_so_vai_para_a_tela_quando_o_PERCENTUAL_muda(monkeypatch, raiz, qtbot,
                                                                 sem_uac):
    aviso = _aviso(raiz, qtbot, disparar=lambda *a: None)
    aviso.botao_atualizar.click()
    agendados = []
    monkeypatch.setattr(atualizacao.interface, "na_interface",
                        lambda func, *a: agendados.append(func))

    for i in range(1000):
        aviso._ao_progredir(i / 100_000)      # de 0% a 0,99%: sempre "0%"

    assert len(agendados) == 1


def test_o_aviso_do_UAC_so_aparece_quando_vai_ser_pedido(monkeypatch, raiz, qtbot):
    monkeypatch.setattr(updater, "precisa_elevacao", lambda: True)
    com = _aviso(raiz, qtbot)
    assert com.rotulo_uac is not None
    assert com.rotulo_uac.text() == textos.MSG_UAC

    monkeypatch.setattr(updater, "precisa_elevacao", lambda: False)
    sem = _aviso(raiz, qtbot)
    assert sem.rotulo_uac is None


def test_fechar_o_app_ENCERRA_o_processo(monkeypatch, raiz):
    """O mesmo encerramento do "X" da janela principal: `instancia.encerrar`.
    Sem perguntar por "tarefa em andamento" -- o aviso e modal, nao ha lote."""
    from sigft.core import instancia

    codigos = []
    monkeypatch.setattr(instancia, "encerrar", codigos.append)
    raiz.show()

    atualizacao._fechar_o_app(raiz)

    assert codigos == [0]
    assert not raiz.isVisible()


def test_fechar_o_app_grava_o_fechamento_no_diario(monkeypatch, raiz, tmp_path):
    """O `instancia.encerrar` nao passa pelo `closeEvent`: sem gravar aqui, a
    sessao seguinte a toda atualizacao avisaria "encerrado de fora" (2026-10-27)."""
    from sigft.core import diario, instancia

    class _FaultFalso:
        def enable(self, arquivo, all_threads=True):
            pass

        def disable(self):
            pass

    monkeypatch.delenv(diario.ENV_DESLIGAR, raising=False)
    monkeypatch.setattr(diario, "faulthandler", _FaultFalso())
    monkeypatch.setattr(instancia, "encerrar", lambda codigo=0: None)
    diario.esquecer()
    try:
        diario.abrir(versao="1.3.1", idioma="pt", pasta=tmp_path, ganchos=False)
        atualizacao._fechar_o_app(raiz)
        ultima = (tmp_path / diario.ARQUIVO).read_text(encoding="utf-8").splitlines()[-1]
        assert ultima.endswith(diario.FECHAMENTO)
    finally:
        diario.esquecer()


# =============================================================================
# E. Paridade visual com a JanelaAtualizacao da interface antiga
# =============================================================================

@pytest.fixture
def com_estilo(qt_interface):
    from sigft.app_qt import estilo

    anterior = qt_interface.styleSheet()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    yield
    qt_interface.setStyleSheet(anterior)


def _pos(aviso, w):
    p = w.mapTo(aviso, w.rect().topLeft())
    return p.x(), p.y()


def _base(aviso, w):
    return _pos(aviso, w)[1] + w.height()


def test_medidas_iguais_as_do_interface_antiga(raiz, qtbot, sem_uac, com_estilo):
    # Medidas da JanelaAtualizacao interface antiga (580x560, sondadas com winfo_* sob Xvfb):
    # titulo y=20; resumo y=52; notas (20, 126) 540 de largura; status 10 abaixo
    # das notas e 14 acima dos botoes; botoes 170x40 em (120, 500) e 150x40 em
    # (310, 500), 20 px da borda de baixo.
    aviso = _aviso(raiz, qtbot, disparar=lambda *a: None)
    aviso.show()
    qtbot.waitExposed(aviso)

    assert (aviso.width(), aviso.height()) == (580, 560)
    assert _pos(aviso, aviso.rotulo_titulo) == (20, 20)
    assert _pos(aviso, aviso.rotulo_resumo) == (20, 52)
    assert _pos(aviso, aviso.caixa_notas) == (20, 126)
    assert aviso.caixa_notas.width() == 540
    assert _pos(aviso, aviso.botao_atualizar) == (120, 500)
    assert (aviso.botao_atualizar.width(), aviso.botao_atualizar.height()) == (170, 40)
    assert _pos(aviso, aviso.botao_agora_nao) == (310, 500)
    assert (aviso.botao_agora_nao.width(), aviso.botao_agora_nao.height()) == (150, 40)
    assert _pos(aviso, aviso.rotulo_status)[1] - _base(aviso, aviso.caixa_notas) == 10
    assert 500 - _base(aviso, aviso.rotulo_status) == 14

    # Baixando: a barra (530x8, centrada) entra 4 px abaixo do status e 16 acima
    # dos botoes, que nao saem do lugar.
    aviso.botao_atualizar.click()
    qtbot.wait(10)
    assert _pos(aviso, aviso.barra) == (25, 476)
    assert (aviso.barra.width(), aviso.barra.height()) == (530, 8)
    assert _pos(aviso, aviso.barra)[1] - _base(aviso, aviso.rotulo_status) == 4
    assert _pos(aviso, aviso.botao_atualizar) == (120, 500)


def test_medidas_com_o_aviso_do_UAC(monkeypatch, raiz, qtbot, com_estilo):
    monkeypatch.setattr(updater, "precisa_elevacao", lambda: True)
    aviso = _aviso(raiz, qtbot)
    aviso.show()
    qtbot.waitExposed(aviso)

    assert _pos(aviso, aviso.rotulo_uac)[1] - _base(aviso, aviso.caixa_notas) == 10
    assert _pos(aviso, aviso.rotulo_status)[1] - _base(aviso, aviso.rotulo_uac) == 10
    assert _pos(aviso, aviso.botao_atualizar) == (120, 500)


def test_os_botoes_NUNCA_somem_com_mensagem_longa(monkeypatch, raiz, qtbot, com_estilo):
    """Defeito visto no ensaio da interface antiga (2026-09-25): com o UAC e um erro de rede
    longo, os botoes saiam da janela. Aqui quem encolhe e a caixa de notas."""
    monkeypatch.setattr(updater, "precisa_elevacao", lambda: True)
    aviso = _aviso(raiz, qtbot, disparar=lambda *a: None)
    aviso.show()
    qtbot.waitExposed(aviso)
    aviso.botao_atualizar.click()
    aviso._falhou(RuntimeError("Nenhuma rota de rede funcionou.\n" + "\n".join(
        f"rota {i}: recusada (HTTP 403)" for i in range(12))))
    qtbot.wait(10)

    assert _base(aviso, aviso.botao_atualizar) <= aviso.height() - 20
    assert aviso.caixa_notas.height() < 300


def test_aviso_fechado_e_apagado_e_nao_so_escondido(raiz, qtbot, sem_uac):
    # Como o `destroy()` da janela antiga: fechado ("Agora não", "X" ou Esc), o
    # aviso é apagado -- antes ficava escondido, vivo, até o app fechar.
    from shiboken6 import isValid

    for fechar in ("agora_nao", "close", "reject"):
        aviso = atualizacao._mostrar_aviso(raiz, _info(), "1.1.0")
        getattr(aviso, fechar)()
        qtbot.waitUntil(lambda a=aviso: not isValid(a), timeout=1000)
    # A próxima resposta abre outro, sem tocar no apagado.
    novo = atualizacao._mostrar_aviso(raiz, _info(), "1.1.0")
    assert isValid(novo) and novo.isVisible()
    novo.agora_nao()


def test_baixando_o_x_nao_fecha_nem_apaga(raiz, qtbot, sem_uac):
    from shiboken6 import isValid

    aviso = _aviso(raiz, qtbot, disparar=lambda *a: None)
    aviso.show()
    aviso.atualizar()
    aviso.close()
    aviso.reject()
    qtbot.wait(20)
    assert isValid(aviso) and aviso.isVisible()
    aviso._baixando = False
    aviso.agora_nao()


def test_caixa_de_notas_e_barra_com_o_estilo_compartilhado(raiz, qtbot, sem_uac):
    # A cara da caixa de notas (CTkTextbox) mora na folha do app, e a barra é a
    # CTkProgressBar de `blocos.barra_progresso` -- nada de folha escrita aqui.
    from sigft.app_qt import estilo

    aviso = _aviso(raiz, qtbot)
    assert aviso.caixa_notas.styleSheet() == ""
    assert "#notas_atualizacao" in estilo.folha_de_estilo()
    assert aviso.barra.styleSheet() == blocos_barra_folha()
    assert (aviso.barra.minimum(), aviso.barra.maximum()) == (0, 100)


def blocos_barra_folha():
    from sigft.app_qt.widgets import blocos

    # 2026-10-20: sem `cor` -- o progresso é a `primaria` da folha.
    return blocos.barra_progresso(largura=530, altura=8).styleSheet()


# =============================================================================
# H. A atualizacao por ARQUIVOS, e o instalador que avisa que subiu  [2026-10-27]
# =============================================================================
# Ver docs/superpowers/specs/2026-10-27-atualizacao-como-cmi-design.md.

@pytest.fixture
def por_arquivos(monkeypatch):
    """Pasta gravavel com pacote de arquivos: `aplicar_por_arquivos` e `reabrir` dublados."""
    eventos = []
    monkeypatch.setattr(updater, "pode_por_arquivos", lambda info: True)
    monkeypatch.setattr(updater, "reabrir", lambda exe: eventos.append(("reabriu", exe)))
    return eventos


def test_por_arquivos_aplica_REABRE_e_fecha_sem_instalador(monkeypatch, raiz, qtbot, processar,
                                                           sem_uac, tmp_path, por_arquivos):
    exe = tmp_path / "SIG-FT.exe"
    vistos = []

    def aplicar(info, *, progresso_cb, log_cb):
        processar()
        vistos.append(aviso.rotulo_status.text())
        progresso_cb(1.0)
        por_arquivos.append("aplicou")
        return exe

    monkeypatch.setattr(updater, "aplicar_por_arquivos", aplicar)
    monkeypatch.setattr(updater, "baixar", lambda *a, **k: pytest.fail("baixou o instalador"))
    monkeypatch.setattr(updater, "instalar", lambda *a, **k: pytest.fail("rodou o instalador"))

    aviso = _aviso(raiz, qtbot, fechar_app=lambda janela: por_arquivos.append(("fechou", janela)))
    aviso.botao_atualizar.click()
    processar()

    assert vistos == [textos.MSG_APLICANDO]
    assert por_arquivos == ["aplicou", ("reabriu", exe), ("fechou", raiz)]
    assert aviso.rotulo_status.text() == textos.MSG_REABRINDO


def test_por_arquivos_que_falha_cai_no_instalador(monkeypatch, raiz, qtbot, processar, sem_uac,
                                                  tmp_path, por_arquivos):
    from sigft.services import pacote_arquivos

    def falha(info, **kw):
        raise pacote_arquivos.ErroPacote("SIG-FT.exe nao confere com a versao 1.2.0")

    log = []
    monkeypatch.setattr(atualizacao, "_log", log.append)
    monkeypatch.setattr(updater, "aplicar_por_arquivos", falha)
    monkeypatch.setattr(updater, "baixar", lambda info, **kw: por_arquivos.append("baixou")
                        or tmp_path / "Setup.exe")
    monkeypatch.setattr(updater, "instalar", lambda caminho, **kw: por_arquivos.append("instalou"))

    aviso = _aviso(raiz, qtbot, fechar_app=lambda janela: por_arquivos.append("fechou"))
    aviso.botao_atualizar.click()
    processar()

    assert por_arquivos == ["baixou", "instalou", "fechou"]
    assert any("nao confere" in str(linha) for linha in log), "o motivo vai para o log"


def test_sem_poder_por_arquivos_nem_tenta(monkeypatch, raiz, qtbot, processar, sem_uac, tmp_path):
    eventos = []
    monkeypatch.setattr(updater, "pode_por_arquivos", lambda info: False)
    monkeypatch.setattr(updater, "aplicar_por_arquivos",
                        lambda *a, **k: pytest.fail("aplicou sem poder"))
    monkeypatch.setattr(updater, "baixar", lambda info, **kw: tmp_path / "Setup.exe")
    monkeypatch.setattr(updater, "instalar", lambda caminho, **kw: eventos.append("instalou"))

    aviso = _aviso(raiz, qtbot, fechar_app=lambda janela: eventos.append("fechou"))
    aviso.botao_atualizar.click()
    processar()

    assert eventos == ["instalou", "fechou"]


def test_instalador_que_nao_iniciou_deixa_o_app_ABERTO_com_o_erro(monkeypatch, raiz, qtbot,
                                                                 processar, sem_uac, tmp_path):
    monkeypatch.setattr(updater, "pode_por_arquivos", lambda info: False)
    monkeypatch.setattr(updater, "baixar", lambda info, **kw: tmp_path / "Setup.exe")

    def nao_subiu(caminho, **kw):
        raise updater.InstaladorNaoIniciou(
            f"O instalador terminou antes de comecar (codigo 1223). Detalhes em "
            f"{tmp_path / 'instalacao.log'}.", codigo=1223,
            log=tmp_path / "instalacao.log")

    monkeypatch.setattr(updater, "instalar", nao_subiu)

    aviso = _aviso(raiz, qtbot)   # fechar_app falha o teste
    aviso.show()
    aviso.botao_atualizar.click()
    processar()

    status = aviso.rotulo_status.text()
    assert "1223" in status and "instalacao.log" in status
    assert status.startswith(textos.msg_instalador_nao_iniciou(
        updater.InstaladorNaoIniciou("x", log=tmp_path / "instalacao.log")).split("\n")[0])
    assert aviso.rotulo_status.property("papel") == "erro"
    assert aviso.botao_atualizar.isEnabled() and aviso.botao_atualizar.text() == "Tentar de novo"


def test_a_abertura_limpa_os_restos_da_atualizacao_por_arquivos(monkeypatch, raiz, processar,
                                                                caixas, tmp_path):
    limpos = []
    monkeypatch.setattr(updater, "deve_verificar", lambda: True)
    monkeypatch.setattr(updater, "checar", lambda versao, **kw: None)
    monkeypatch.setattr(updater, "empacotado", lambda: True)
    monkeypatch.setattr(updater, "pasta_instalacao", lambda: tmp_path)
    from sigft.services import pacote_arquivos

    monkeypatch.setattr(pacote_arquivos, "limpar_restos", lambda pasta: limpos.append(pasta) or 0)

    atualizacao.verificar_na_abertura(raiz, versao_atual="1.1.0", disparar=_sincrono)

    assert limpos == [tmp_path]


def test_limpar_restos_que_falha_nao_impede_a_consulta(monkeypatch, raiz, processar, caixas,
                                                       tmp_path):
    perguntas = []
    monkeypatch.setattr(updater, "deve_verificar", lambda: True)
    monkeypatch.setattr(updater, "checar", lambda versao, **kw: perguntas.append(versao))
    monkeypatch.setattr(updater, "empacotado", lambda: True)
    monkeypatch.setattr(updater, "pasta_instalacao", lambda: tmp_path)
    from sigft.services import pacote_arquivos

    monkeypatch.setattr(pacote_arquivos, "limpar_restos", lambda pasta: 1 / 0)

    atualizacao.verificar_na_abertura(raiz, versao_atual="1.1.0", disparar=_sincrono)

    assert perguntas == ["1.1.0"]


# =============================================================================
# I. O diario de quem fecha para atualizar  [2026-10-27]
# =============================================================================
# Na thread, logo antes de mandar fechar: uma linha ATUALIZACAO (o caminho, as
# versoes e, no instalador, o .exe e o log dele) e o FECHAMENTO -- antes de a
# thread da interface rodar, porque o `CloseApplications=force` pode matar o
# app primeiro. O `_fechar_o_app` grava de novo, e o diario nao repete.

@pytest.fixture
def diario_aberto(monkeypatch, tmp_path):
    from sigft.core import diario, instancia

    class _FaultFalso:
        def enable(self, arquivo, all_threads=True):
            pass

        def disable(self):
            pass

    monkeypatch.delenv(diario.ENV_DESLIGAR, raising=False)
    monkeypatch.setattr(diario, "faulthandler", _FaultFalso())
    monkeypatch.setattr(instancia, "encerrar", lambda codigo=0: None)
    monkeypatch.setattr(updater, "_pasta_de_download", lambda: tmp_path / "downloads")
    diario.esquecer()
    diario.abrir(versao="1.1.0", idioma="pt", pasta=tmp_path, ganchos=False)

    def linhas():
        return (tmp_path / diario.ARQUIVO).read_text(encoding="utf-8").splitlines()

    yield linhas
    diario.esquecer()


def _sem_abertura(linhas):
    return [linha.split(" ", 2)[2] for linha in linhas() if "ABERTURA" not in linha]


def test_por_arquivos_grava_ATUALIZACAO_e_FECHAMENTO_antes_de_reabrir(
        monkeypatch, raiz, qtbot, processar, sem_uac, tmp_path, por_arquivos, diario_aberto):
    vistos = []
    monkeypatch.setattr(updater, "aplicar_por_arquivos", lambda info, **kw: tmp_path / "SIG-FT.exe")
    monkeypatch.setattr(updater, "reabrir", lambda exe: vistos.append(_sem_abertura(diario_aberto)))

    aviso = _aviso(raiz, qtbot, fechar_app=atualizacao._fechar_o_app)
    aviso.botao_atualizar.click()
    processar()

    from sigft.core import diario

    esperado = [f"{diario.ATUALIZACAO} por arquivos v1.1.0 -> v1.2.0", diario.FECHAMENTO]
    assert vistos == [esperado], "o novo processo abre lendo um fechamento normal"
    assert _sem_abertura(diario_aberto) == esperado, "o _fechar_o_app nao repete o FECHAMENTO"


@pytest.mark.parametrize("caiu, caminho", [(False, "pelo instalador pequeno"),
                                           (True, "pelo instalador completo")])
def test_instalador_grava_o_caminho_o_exe_e_o_log(monkeypatch, raiz, qtbot, processar, sem_uac,
                                                  tmp_path, diario_aberto, caiu, caminho):
    exe = tmp_path / ("Setup.exe" if caiu else "SIG-FT_Itaipu_Atualizacao_1.1.0_para_1.2.0.exe")
    vistos = []

    def baixar(info, *, progresso_cb, log_cb, ao_cair_no_completo):
        if caiu:
            ao_cair_no_completo(_info())
        return exe

    monkeypatch.setattr(updater, "pode_por_arquivos", lambda info: False)
    monkeypatch.setattr(updater, "baixar", baixar)
    monkeypatch.setattr(updater, "instalar", lambda c, **kw: None)
    aviso = _aviso(raiz, qtbot, info=_info(incremental=True),
                   fechar_app=lambda janela: vistos.append(_sem_abertura(diario_aberto)))
    aviso.botao_atualizar.click()
    processar()

    from sigft.core import diario

    log = updater.caminho_log_instalacao()
    assert vistos == [[f"{diario.ATUALIZACAO} {caminho} v1.1.0 -> v1.2.0 "
                       f"(exe={exe.name}, log={log})", diario.FECHAMENTO]]


def test_completo_desde_o_inicio_e_o_completo(monkeypatch, raiz, qtbot, processar, sem_uac,
                                              tmp_path, diario_aberto):
    monkeypatch.setattr(updater, "pode_por_arquivos", lambda info: False)
    monkeypatch.setattr(updater, "baixar", lambda info, **kw: tmp_path / "Setup.exe")
    monkeypatch.setattr(updater, "instalar", lambda c, **kw: None)
    aviso = _aviso(raiz, qtbot, fechar_app=lambda janela: None)
    aviso.botao_atualizar.click()
    processar()

    assert "pelo instalador completo" in _sem_abertura(diario_aberto)[0]


def test_instalador_que_nao_subiu_nao_grava_nada(monkeypatch, raiz, qtbot, processar, sem_uac,
                                                 tmp_path, diario_aberto):
    monkeypatch.setattr(updater, "pode_por_arquivos", lambda info: False)
    monkeypatch.setattr(updater, "baixar", lambda info, **kw: tmp_path / "Setup.exe")

    def nao_subiu(caminho, **kw):
        raise updater.InstaladorNaoIniciou("saiu antes", codigo=1)

    monkeypatch.setattr(updater, "instalar", nao_subiu)
    aviso = _aviso(raiz, qtbot)
    aviso.botao_atualizar.click()
    processar()

    assert _sem_abertura(diario_aberto) == []
