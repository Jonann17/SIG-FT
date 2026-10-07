# -*- coding: utf-8 -*-
"""A atualizacao automatica, do lado do APLICATIVO: a abertura pergunta ao GitHub.

A CAUSA RAIZ que este arquivo trava (2026-09-25)
------------------------------------------------
O usuario publicou a v1.1.0 e nenhum app instalado percebeu. O servico estava
pronto desde 2026-09-18 -- `sigft/services/updater.py` consulta, baixa, confere
o SHA256 e dispara o instalador, com 45 testes verdes --, mas NINGUEM O
CHAMAVA. Nenhuma linha de `sigft/app/` importava o `updater`. Os testes eram
todos do servico, e servico sem chamador passa em todos.

A prova veio do proprio GitHub: o `latest.json` do Release v1.1.0, que o app
baixa na hora de oferecer a versao nova, estava com ZERO downloads.

Por isso o primeiro teste daqui nao olha o servico: ele monta a JANELA
PRINCIPAL de verdade (so as telas sao trocadas por quadros vazios) e exige que
a abertura faca a pergunta. E o teste que teria pego o defeito.
"""
import threading
import time

import customtkinter as ctk
import pytest

from sigft import _build_info
from sigft.services import updater

# As telas que a janela principal instancia. Trocadas por quadros vazios: o que
# se testa aqui e a FIACAO da abertura, nao as telas -- e montar as 12 com os
# dubles exigiria dublar metade do CustomTkinter.
TELAS = [
    "HomeView", "ModuloCriaFichas", "ModuloPDM", "ModuloAnalyzer",
    "ModuloTranslator", "ModuloUploadConditions", "ModuloUploadTechSpecs",
    "ModuloCopiaFichas", "ModuloCorrecaoPDM", "ModuloAutoSpec",
    "ModuloAplicacaoLMR", "ModuloPMIBManager", "ModuloBuscaPMIB",
]


class _TelaVazia(ctk.CTkFrame):
    def __init__(self, parent=None, controller=None, **_kw):
        super().__init__(parent)

    def grid_forget(self):
        pass


def _janela_principal(monkeypatch):
    from sigft.app import main as modulo

    for nome in TELAS:
        monkeypatch.setattr(modulo, nome, _TelaVazia)
    return modulo.SIG_FT_App()


def _esperar(condicao, segundos=5.0):
    """A consulta roda numa thread: espera ela chegar, sem `sleep` fixo."""
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicao():
            return True
        time.sleep(0.01)
    return condicao()


# =============================================================================
# A. A causa raiz
# =============================================================================

def test_abrir_o_app_instalado_PERGUNTA_ao_github_pela_versao_nova(monkeypatch):
    """O defeito de 2026-09-25, reproduzido: publicar um Release nao mudava
    nada, porque a abertura do app nunca consultava o GitHub."""
    perguntas = []
    monkeypatch.setattr(updater, "deve_verificar", lambda *a, **k: True)
    monkeypatch.setattr(updater, "checar",
                        lambda versao, **kw: perguntas.append(versao))

    _janela_principal(monkeypatch)

    assert _esperar(lambda: perguntas), (
        "A janela principal abriu e NINGUEM perguntou ao GitHub se ha versao "
        "nova -- e exatamente o defeito que deixou a v1.1.0 sem chegar a "
        "ninguem.")
    assert perguntas == [_build_info.VERSAO], (
        "A versao comparada tem de ser a do BUILD (`_build_info`), nunca de "
        "arquivo do usuario -- ver o docstring de `sigft/_build_info.py`.")


def test_a_pergunta_NAO_segura_a_abertura(monkeypatch):
    """A consulta passa pela cascata de rede, que pode levar dezenas de
    segundos com a VPN mal configurada. Na thread da interface, isso seria o
    app congelado ao abrir -- pior que nao ter atualizacao nenhuma."""
    liberar = threading.Event()
    comecou = threading.Event()

    def checar_lento(versao, **kw):
        comecou.set()
        liberar.wait(5)

    monkeypatch.setattr(updater, "deve_verificar", lambda *a, **k: True)
    monkeypatch.setattr(updater, "checar", checar_lento)

    inicio = time.monotonic()
    _janela_principal(monkeypatch)
    duracao = time.monotonic() - inicio
    liberar.set()

    assert comecou.wait(5), "a consulta nem comecou"
    assert duracao < 2, f"a janela levou {duracao:.1f}s para montar: a consulta a segurou"


def test_sem_permissao_da_politica_a_abertura_nao_toca_na_rede(monkeypatch):
    """Rodando do codigo-fonte, do ZIP do Box ou sem token, nao ha o que
    perguntar -- e bater na rede a toa so atrasaria e poluiria o log."""
    monkeypatch.setattr(updater, "deve_verificar", lambda *a, **k: False)
    monkeypatch.setattr(
        updater, "checar",
        lambda *a, **k: pytest.fail("perguntou ao GitHub sem a politica deixar"))

    _janela_principal(monkeypatch)
    time.sleep(0.05)   # tempo para uma thread indevida aparecer


# =============================================================================
# Apoio das secoes B em diante
# =============================================================================

from tkinter import messagebox as caixa  # noqa: E402 -- o duble do conftest

from sigft.app import atualizacao  # noqa: E402
from sigft.core import rede  # noqa: E402


def _sincrono(alvo, *args):
    """No lugar da thread: roda na hora. O que o codigo AGENDA com `after`
    continua enfileirado ate `processar_eventos()` -- e e isso que prova que
    nada toca em widget fora da thread da interface."""
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
def raiz():
    return ctk.CTk()


@pytest.fixture(autouse=True)
def _caixas_limpas():
    caixa.chamadas.clear()
    yield
    caixa.chamadas.clear()


def _textos(widget):
    """Todo texto de rotulo/botao abaixo de `widget`, na ordem de criacao."""
    achados = []
    for filho in getattr(widget, "filhos", []):
        texto = filho.kwargs.get("text")
        if isinstance(texto, str) and texto:
            achados.append(texto)
        achados.extend(_textos(filho))
    return achados


# =============================================================================
# B. A pergunta da abertura: responde so quando ha o que oferecer
# =============================================================================

def test_versao_nova_abre_o_aviso_PELA_thread_da_interface(monkeypatch, raiz):
    monkeypatch.setattr(updater, "deve_verificar", lambda: True)
    monkeypatch.setattr(updater, "checar", lambda versao, **kw: _info())

    assert atualizacao.verificar_na_abertura(raiz, versao_atual="1.1.0",
                                             disparar=_sincrono)

    assert getattr(raiz, "_janela_de_atualizacao", None) is None, (
        "o aviso foi criado de dentro da thread da consulta -- widget fora da "
        "thread do Tk e o defeito que o CP 7.1 tirou do console")

    raiz.processar_eventos()

    aviso = raiz._janela_de_atualizacao
    assert isinstance(aviso, atualizacao.JanelaAtualizacao)
    assert aviso.info.versao == "1.2.0"


def test_ja_em_dia_a_abertura_fica_CALADA(monkeypatch, raiz):
    """Abrir o app todo dia e ouvir "voce esta na versao mais recente" seria
    ruido; ninguem pediu."""
    monkeypatch.setattr(updater, "deve_verificar", lambda: True)
    monkeypatch.setattr(updater, "checar", lambda versao, **kw: None)

    atualizacao.verificar_na_abertura(raiz, disparar=_sincrono)
    raiz.processar_eventos()

    assert caixa.chamadas == []
    assert getattr(raiz, "_janela_de_atualizacao", None) is None


def test_falha_na_abertura_fica_calada_mas_VAI_PARA_O_LOG(monkeypatch, raiz, capsys):
    """Sem rede (VPN desligada, GitHub fora) o app abre igual. Mas a falha
    tem de estar escrita no `sigft.log` -- e o unico lugar onde quem cuida do
    SIG-FT consegue descobrir por que uma maquina parou de se atualizar."""
    def falha(versao, **kw):
        raise rede.FalhaDeRede("Nenhuma rota de rede funcionou.")

    monkeypatch.setattr(updater, "deve_verificar", lambda: True)
    monkeypatch.setattr(updater, "checar", falha)

    atualizacao.verificar_na_abertura(raiz, disparar=_sincrono)
    raiz.processar_eventos()

    assert caixa.chamadas == []
    assert "Nenhuma rota de rede funcionou" in capsys.readouterr().out


def test_politica_negando_a_abertura_nao_dispara_nada(monkeypatch, raiz):
    monkeypatch.setattr(updater, "deve_verificar", lambda: False)

    disparou = []
    assert not atualizacao.verificar_na_abertura(
        raiz, disparar=lambda *a: disparou.append(a))
    assert disparou == []


# =============================================================================
# C. O botao "Atualizacoes": a mesma pergunta, que SEMPRE responde
# =============================================================================

@pytest.fixture
def pode_verificar(monkeypatch):
    monkeypatch.setattr(updater, "motivo_para_nao_verificar", lambda: None)


def test_o_botao_diz_quando_ja_esta_na_mais_recente(monkeypatch, raiz, pode_verificar):
    monkeypatch.setattr(updater, "checar", lambda versao, **kw: None)
    terminou = []

    atualizacao.procurar_agora(raiz, versao_atual="1.2.0", disparar=_sincrono,
                               ao_terminar=lambda: terminou.append(True))
    raiz.processar_eventos()

    assert terminou == [True]
    [(tipo, _titulo, mensagem)] = caixa.chamadas
    assert tipo == "info"
    assert "mais recente" in mensagem and "v1.2.0" in mensagem


def test_o_botao_MOSTRA_o_erro_que_a_abertura_engole(monkeypatch, raiz, pode_verificar):
    """Token expirado deixa TODOS os apps sem atualizacao, calados. Sem um
    caminho que mostre o motivo, isso so seria descoberto por acaso."""
    def recusado(versao, **kw):
        raise updater.SemToken("O GitHub recusou o token de atualizacao deste build (HTTP 401).")

    monkeypatch.setattr(updater, "checar", recusado)

    atualizacao.procurar_agora(raiz, disparar=_sincrono)
    raiz.processar_eventos()

    [(tipo, _titulo, mensagem)] = caixa.chamadas
    assert tipo == "warning"
    assert "recusou o token" in mensagem


def test_o_botao_explica_por_que_esta_copia_nao_se_atualiza(monkeypatch, raiz):
    """Sem o motivo, "nao aconteceu nada" nao se distingue de defeito."""
    monkeypatch.setattr(updater, "motivo_para_nao_verificar",
                        lambda: "Este SIG-FT roda pelo codigo-fonte (SIG-FT.bat).")
    monkeypatch.setattr(updater, "checar",
                        lambda *a, **k: pytest.fail("perguntou ao GitHub sem poder instalar"))
    terminou = []

    atualizacao.procurar_agora(raiz, versao_atual="1.2.0", disparar=_sincrono,
                               ao_terminar=lambda: terminou.append(True))

    assert terminou == [True]
    [(tipo, _titulo, mensagem)] = caixa.chamadas
    assert tipo == "info"
    assert "codigo-fonte" in mensagem and "v1.2.0" in mensagem


def test_o_botao_volta_ao_normal_ANTES_da_mensagem(monkeypatch, raiz, pode_verificar):
    """A caixa do Tk e modal: com a ordem trocada, o botao ficaria dizendo
    "Procurando..." enquanto ela estivesse aberta."""
    ordem = []
    monkeypatch.setattr(updater, "checar", lambda versao, **kw: None)
    monkeypatch.setattr(caixa, "showinfo",
                        lambda *a, **k: ordem.append("mensagem"))

    atualizacao.procurar_agora(raiz, disparar=_sincrono,
                               ao_terminar=lambda: ordem.append("botao"))
    raiz.processar_eventos()

    assert ordem == ["botao", "mensagem"]


def test_com_versao_nova_o_botao_abre_o_MESMO_aviso(monkeypatch, raiz, pode_verificar):
    monkeypatch.setattr(updater, "checar", lambda versao, **kw: _info())

    atualizacao.procurar_agora(raiz, disparar=_sincrono)
    raiz.processar_eventos()

    assert isinstance(raiz._janela_de_atualizacao, atualizacao.JanelaAtualizacao)
    assert caixa.chamadas == []


def test_o_aviso_NAO_abre_duas_vezes(monkeypatch, raiz):
    """A pergunta da abertura e o botao podem responder quase juntos: dois
    avisos seriam dois "Atualizar agora", e dois downloads do instalador."""
    primeiro = atualizacao._mostrar_aviso(raiz, _info(), "1.1.0")
    segundo = atualizacao._mostrar_aviso(raiz, _info(), "1.1.0")

    assert segundo is primeiro

    primeiro.agora_nao()
    terceiro = atualizacao._mostrar_aviso(raiz, _info(), "1.1.0")

    assert terceiro is not primeiro, "fechado o aviso, a proxima resposta abre outro"


# =============================================================================
# D. A janela do aviso
# =============================================================================

@pytest.fixture
def sem_uac(monkeypatch):
    monkeypatch.setattr(updater, "precisa_elevacao", lambda: False)


def _aviso(raiz, **kw):
    kw.setdefault("disparar", _sincrono)
    kw.setdefault("fechar_app", lambda janela: pytest.fail("fechou o app"))
    return atualizacao.JanelaAtualizacao(raiz, info=kw.pop("info", _info()),
                                         versao_atual="1.1.0", **kw)


def test_o_aviso_mostra_a_versao_nova_a_atual_e_o_que_mudou(raiz, sem_uac):
    aviso = _aviso(raiz)
    textos = " | ".join(_textos(aviso))

    assert "v1.2.0" in textos
    assert "v1.1.0" in textos, "sem a versao atual, a pessoa nao sabe o salto"
    assert "25/09/2026" in textos
    assert aviso.caixa_notas.texto == atualizacao.notas_para_exibir(_info().notas)
    assert aviso.caixa_notas.kwargs.get("state") == "disabled", (
        "as notas sao para ler, nao para editar")


def test_o_aviso_e_MODAL(raiz, sem_uac):
    """Atualizar FECHA o app. Sem o grab, dava para comecar um lote na tela de
    tras com o aviso aberto -- e o "Atualizar agora" mataria o robo no meio."""
    aviso = _aviso(raiz)

    assert getattr(aviso, "chamou_grab_set", False)
    assert aviso.dono_transiente is raiz


def test_agora_nao_e_o_X_fecham_SEM_baixar(monkeypatch, raiz, sem_uac):
    monkeypatch.setattr(updater, "baixar",
                        lambda *a, **k: pytest.fail("baixou sem ninguem pedir"))

    aviso = _aviso(raiz)
    aviso.botao_agora_nao.kwargs["command"]()
    assert aviso.destruido and aviso.fechada

    outro = _aviso(raiz)
    outro.protocolos["WM_DELETE_WINDOW"]()
    assert outro.destruido


def test_atualizar_BAIXA_INSTALA_e_so_entao_FECHA_o_app(monkeypatch, raiz, sem_uac, tmp_path):
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

    aviso = _aviso(raiz, fechar_app=lambda janela: eventos.append(("fechou", janela)))
    aviso.botao_atualizar.kwargs["command"]()
    raiz.processar_eventos()

    assert eventos == ["baixou", ("instalou", baixado), ("fechou", raiz)]
    assert aviso.barra.valor == 1.0


def test_download_que_falha_NAO_fecha_o_app_e_deixa_tentar_de_novo(monkeypatch, raiz, sem_uac):
    def falha(*a, **k):
        raise updater.ArquivoInvalido("O arquivo baixado e pequeno demais para ser o instalador")

    monkeypatch.setattr(updater, "baixar", falha)
    monkeypatch.setattr(updater, "instalar",
                        lambda *a, **k: pytest.fail("instalou um download que falhou"))

    aviso = _aviso(raiz)
    aviso.botao_atualizar.kwargs["command"]()
    raiz.processar_eventos()

    assert "pequeno demais" in aviso.rotulo_status.kwargs["text"]
    assert aviso.botao_atualizar.kwargs["state"] == "normal"
    assert aviso.botao_atualizar.kwargs["text"] == "Tentar de novo"
    assert aviso.botao_agora_nao.kwargs["state"] == "normal"
    aviso.protocolos["WM_DELETE_WINDOW"]()
    assert aviso.destruido, "depois da falha, o X volta a fechar o aviso"


def test_quando_o_pequeno_falha_a_janela_DIZ_que_baixa_o_completo(monkeypatch, raiz, sem_uac,
                                                                 tmp_path):
    """[2026-10-07] O pequeno da 1.2.0-rc.4 chegou cortado na rede da empresa,
    e o servico cai no completo. A janela tem de dizer que o download agora e
    o de 300 MB -- em vez de seguir com "Baixando a v1.2.0 (36,7 MB)" -- e a
    barra recomeca do zero."""
    completo = _info(tamanho=316_197_094)
    vistos = []

    def baixar(info, *, progresso_cb, log_cb, ao_cair_no_completo):
        progresso_cb(0.97)
        ao_cair_no_completo(completo)
        progresso_cb(0.0)
        raiz.processar_eventos()
        vistos.append((aviso.rotulo_status.kwargs["text"], aviso.barra.valor))
        return tmp_path / "Setup.exe"

    monkeypatch.setattr(updater, "baixar", baixar)
    monkeypatch.setattr(updater, "instalar", lambda *a, **k: None)
    aviso = _aviso(raiz, fechar_app=lambda janela: None,
                   info=_info(nome_arquivo="SIG-FT_Itaipu_Atualizacao_1.1.0_para_1.2.0.bin",
                              tamanho=38_518_933, incremental=True, tamanho_completo=316_197_094))
    aviso.botao_atualizar.kwargs["command"]()
    raiz.processar_eventos()

    texto, barra = vistos[0]
    assert "pequena falhou" in texto
    assert "instalador completo (301,5 MB)" in texto
    assert barra == 0


def test_instalador_que_NAO_SOBE_nao_fecha_o_app(monkeypatch, raiz, sem_uac, tmp_path):
    """Fechar o app sem o instalador de pe deixaria a pessoa sem SIG-FT."""
    monkeypatch.setattr(updater, "baixar", lambda *a, **k: tmp_path / "Setup.exe")

    def recusado(*a, **k):
        raise RuntimeError("Voce recusou o pedido do Windows.")

    monkeypatch.setattr(updater, "instalar", recusado)

    aviso = _aviso(raiz)
    aviso.botao_atualizar.kwargs["command"]()
    raiz.processar_eventos()

    assert "recusou" in aviso.rotulo_status.kwargs["text"]


def test_o_X_no_meio_do_download_NAO_fecha(raiz, sem_uac):
    """O download nao tem como parar no meio; fechar o aviso nao cancelaria
    nada, e o app fecharia do mesmo jeito ao terminar -- sem aviso na tela."""
    pendente = []
    aviso = _aviso(raiz, disparar=lambda alvo, *a: pendente.append(alvo))

    aviso.botao_atualizar.kwargs["command"]()
    aviso.protocolos["WM_DELETE_WINDOW"]()

    assert not aviso.destruido
    assert pendente, "o download devia ter sido disparado"
    assert aviso.botao_atualizar.kwargs["state"] == "disabled"


def test_a_barra_so_aparece_quando_o_download_comeca(raiz, sem_uac):
    aviso = _aviso(raiz, disparar=lambda *a: None)

    assert aviso.barra.chamadas_pack == [], "parada em zero, parece download travado"

    aviso.botao_atualizar.kwargs["command"]()

    [empacotamento] = aviso.barra.chamadas_pack
    assert empacotamento.get("side") == "bottom"
    assert empacotamento.get("after") is aviso.quadro_botoes, (
        "sem `after=`, o pack poe a barra fora do lugar: ela vai logo ACIMA "
        "dos botoes, que estao presos embaixo")


@pytest.fixture
def ordem_de_empacotamento(monkeypatch):
    """Registra a ordem GLOBAL dos `pack()` -- o duble so guarda por widget."""
    base = ctk.CTkFrame.__mro__[1]
    original = base.pack
    ordem = []

    def pack(self, **kwargs):
        ordem.append((self, kwargs))
        original(self, **kwargs)

    monkeypatch.setattr(base, "pack", pack)
    return ordem


def test_os_botoes_NUNCA_somem_com_mensagem_longa(raiz, ordem_de_empacotamento, monkeypatch):
    """Defeito visto no ensaio sob xvfb, 2026-09-25: com o aviso do UAC e o
    erro de rede (uma linha por rota tentada), "Tentar de novo" e "Agora nao"
    saiam da janela, cortados embaixo.

    O `pack` reparte a altura NA ORDEM em que os widgets foram empacotados, e
    corta os ultimos. Os botoes vinham por ultimo. Empacotados primeiro, presos
    embaixo, quem encolhe e a caixa de notas -- que rola."""
    monkeypatch.setattr(updater, "precisa_elevacao", lambda: True)
    aviso = _aviso(raiz)
    posicao = {id(w): i for i, (w, _kw) in enumerate(ordem_de_empacotamento)}

    kw_botoes = next(kw for w, kw in ordem_de_empacotamento if w is aviso.quadro_botoes)
    assert kw_botoes.get("side") == "bottom"
    for widget in (aviso.rotulo_status, aviso.rotulo_uac):
        assert posicao[id(aviso.quadro_botoes)] < posicao[id(widget)] < posicao[id(aviso.caixa_notas)], (
            "a parte de baixo (botoes, status, UAC) tem de ser empacotada ANTES "
            "das notas, para ser ela a ganhar a altura")


def test_erro_enorme_e_ENCURTADO_na_tela_e_aponta_o_log(raiz, sem_uac):
    """O `FalhaDeRede` traz o diagnostico de cada rota: na janela, o comeco
    basta; o resto ja esta no `sigft.log` (`_consultar`/`_baixar_e_instalar`
    registram o erro inteiro)."""
    aviso = _aviso(raiz)

    aviso._falhou(RuntimeError("Nenhuma rota de rede funcionou. " + "x" * 3000))

    texto = aviso.rotulo_status.kwargs["text"]
    assert "Nenhuma rota de rede funcionou." in texto
    assert len(texto) < 900
    assert "log" in texto


def test_o_progresso_so_vai_para_a_tela_quando_o_PERCENTUAL_muda(raiz, sem_uac):
    """~400 blocos num instalador de 100 MB: cada agendamento e uma ida e
    volta a thread do Tk."""
    aviso = _aviso(raiz, disparar=lambda *a: None)
    aviso.botao_atualizar.kwargs["command"]()
    raiz.processar_eventos()

    for i in range(1000):
        aviso._ao_progredir(i / 100_000)      # de 0% a 0,99%: sempre "0%"

    assert len(raiz.pendentes) == 1


def test_o_aviso_do_UAC_so_aparece_quando_vai_ser_pedido(monkeypatch, raiz):
    monkeypatch.setattr(updater, "precisa_elevacao", lambda: True)
    com = _aviso(raiz)
    assert com.rotulo_uac is not None
    assert com.rotulo_uac.kwargs["text"] == atualizacao.MSG_UAC

    monkeypatch.setattr(updater, "precisa_elevacao", lambda: False)
    sem = _aviso(raiz)
    assert sem.rotulo_uac is None


# =============================================================================
# E. As notas e o resumo -- funcoes puras
# =============================================================================

def test_as_notas_perdem_o_markdown_e_ganham_marcador():
    texto = atualizacao.notas_para_exibir(
        "- **Upload:** agora salva `sozinho`\n* segundo item\n")

    assert texto == "• Upload: agora salva sozinho\n\n• segundo item"


def test_o_rodape_como_instalar_do_corpo_do_release_e_cortado():
    """Sem o `latest.json`, as notas vem do corpo do Release -- que termina
    com as instrucoes de instalacao manual, inuteis para quem atualiza pelo app."""
    corpo = ("## O que mudou na v1.2.0\n\n- item\n\n---\n\n### Como instalar\n\n"
             "Baixe o SIG-FT_Itaipu_Setup_*.exe abaixo")

    texto = atualizacao.notas_para_exibir(corpo)

    assert "Como instalar" not in texto
    assert texto == "O que mudou na v1.2.0\n\n• item"


@pytest.mark.parametrize("vazio", [None, "", "   \n  "])
def test_notas_vazias_viram_uma_frase(vazio):
    assert atualizacao.notas_para_exibir(vazio) == "(Esta versão não trouxe notas.)"


def test_o_resumo_diz_de_onde_para_onde_com_data_e_tamanho_brasileiros():
    resumo = atualizacao.resumo_da_versao(_info(), "1.1.0")

    assert resumo == "Você está na v1.1.0. A v1.2.0 saiu em 25/09/2026 e tem 105,1 MB."


def test_o_resumo_sem_data_nem_tamanho_nao_inventa():
    resumo = atualizacao.resumo_da_versao(_info(publicado_em="", tamanho=0), "1.1.0")

    assert resumo == "Você está na v1.1.0. A v1.2.0."


def test_o_resumo_do_instalador_pequeno_compara_com_o_completo():
    # [2026-10-07] O que a pessoa ganha com o pequeno tem de aparecer.
    info = _info(nome_arquivo="SIG-FT_Itaipu_Atualizacao_1.1.0_para_1.2.0.bin", tamanho=12_900_000,
                 incremental=True, tamanho_completo=316_017_517)

    resumo = atualizacao.resumo_da_versao(info, "1.1.0")

    assert resumo == ("Você está na v1.1.0. A v1.2.0 saiu em 25/09/2026. A atualização tem 12,3 MB: "
                      "só o que mudou (o instalador completo tem 301,4 MB).")


def test_versao_de_teste_e_dita_no_titulo(raiz, sem_uac):
    aviso = _aviso(raiz, info=_info(versao="1.2.0-rc.3", prerelease=True))

    assert "Nova versão de teste disponível: v1.2.0-rc.3" in _textos(aviso)


# =============================================================================
# F. O botao na Home
# =============================================================================

def test_a_home_tem_o_botao_e_ele_PERGUNTA_AGORA(monkeypatch, raiz):
    from sigft.app.views import home

    pedidos = []
    monkeypatch.setattr(atualizacao, "procurar_agora",
                        lambda janela, **kw: pedidos.append((janela, kw)))

    # So a barra de botoes: montar a Home inteira exigiria dublar o `bind`.
    tela = home.HomeView.__new__(home.HomeView)
    ctk.CTkScrollableFrame.__init__(tela, raiz)
    tela.controller = raiz
    tela._criar_barra_de_botoes(row=3)

    botao = tela.btn_atualizacoes
    assert botao.kwargs["text"] == home.TEXTO_BOTAO_ATUALIZACOES

    botao.kwargs["command"]()

    assert botao.kwargs["state"] == "disabled", "dois cliques seriam duas consultas"
    assert "Procurando" in botao.kwargs["text"]
    [(janela, kw)] = pedidos
    assert janela is raiz, "o aviso nasce da janela principal, nao da Home"

    kw["ao_terminar"]()

    assert botao.kwargs["state"] == "normal"
    assert botao.kwargs["text"] == home.TEXTO_BOTAO_ATUALIZACOES


def test_a_home_tem_a_caixa_do_canal_de_testes_e_ela_lembra(monkeypatch, raiz):
    # [2026-10-07] Desligada por padrao; marcar grava a escolha na hora.
    from sigft.app.views import home

    escolhas = []
    monkeypatch.setattr(updater, "canal_testes_ligado", lambda **kw: False)
    monkeypatch.setattr(updater, "ligar_canal_testes", lambda ligado, **kw: escolhas.append(ligado))
    tela = home.HomeView.__new__(home.HomeView)
    ctk.CTkScrollableFrame.__init__(tela, raiz)
    tela.controller = raiz
    tela._criar_barra_de_botoes(row=3)

    caixa = tela.caixa_canal_testes
    assert caixa.kwargs["text"] == home.TEXTO_CANAL_TESTES
    assert tela.var_canal_testes.get() is False

    tela.var_canal_testes.set(True)
    caixa.kwargs["command"]()

    assert escolhas == [True]


# =============================================================================
# G. O que o Release PROMETE a quem esta nas versoes antigas
# =============================================================================

def test_as_notas_do_release_NAO_prometem_atualizacao_a_quem_esta_na_1_0_ou_1_1():
    """O rodape fixo das notas dizia "quem ja tem o SIG-FT instalado nao
    precisa baixar nada" -- falso para a 1.0.0 e a 1.1.0, que nunca
    perguntaram ao GitHub. Quem acreditasse ficaria esperando um aviso que
    nao vem."""
    import importlib.util
    import pathlib

    caminho = pathlib.Path(__file__).resolve().parent.parent / "tools" / "gerar_manifesto.py"
    spec = importlib.util.spec_from_file_location("gerar_manifesto", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)

    rodape = " ".join(modulo.COMO_INSTALAR.split())
    assert "1.0.0" in rodape and "1.1.0" in rodape, (
        "o rodape tem de dizer que a 1.0.0 e a 1.1.0 precisam instalar a mao")
