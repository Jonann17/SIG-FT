"""Testes de `sigft/core/plataforma.py` — Checkpoint 8.4 (Fase 8).

O módulo concentra o que depende do sistema operacional. O que ele conserta,
além de tirar 3 cópias do caminho:

* a detecção passou a ser pelo SISTEMA (`sys.platform`) e não pelo SINTOMA
  (`except AttributeError` porque `os.startfile` não existe fora do Windows);
* o Linux entrou na conta. As cópias antigas caíam em ``open``, que é comando
  do macOS — no Linux o efeito era "não acontece nada", sem erro visível.

Os testes forçam cada sistema por `monkeypatch` em vez de depender de onde a
suíte roda: um teste de portabilidade que só exercita a plataforma atual não
testa portabilidade nenhuma.
"""
from __future__ import annotations


import pytest

from sigft.core import plataforma


@pytest.fixture()
def registrar_subprocess(monkeypatch):
    """Captura o que seria passado ao `subprocess.call`."""
    chamadas = []
    monkeypatch.setattr(plataforma.subprocess, "call", lambda args: chamadas.append(args))
    return chamadas


# =============================================================================
# A. Identificação do sistema
# =============================================================================

def test_as_flags_sao_mutuamente_coerentes():
    # Nunca as duas ao mesmo tempo.
    assert not (plataforma.EH_WINDOWS and plataforma.EH_MAC)


def test_descricao_nomeia_windows(monkeypatch):
    monkeypatch.setattr(plataforma, "EH_WINDOWS", True)
    monkeypatch.setattr(plataforma, "EH_MAC", False)
    assert plataforma.descricao() == "Windows"


def test_descricao_nomeia_mac(monkeypatch):
    monkeypatch.setattr(plataforma, "EH_WINDOWS", False)
    monkeypatch.setattr(plataforma, "EH_MAC", True)
    assert plataforma.descricao() == "macOS"


def test_descricao_devolve_o_sys_platform_no_resto(monkeypatch):
    monkeypatch.setattr(plataforma, "EH_WINDOWS", False)
    monkeypatch.setattr(plataforma, "EH_MAC", False)
    monkeypatch.setattr(plataforma.sys, "platform", "linux")
    assert plataforma.descricao() == "linux"


# =============================================================================
# B. abrir_no_sistema — um caminho por sistema
# =============================================================================

def test_no_windows_usa_startfile(monkeypatch):
    monkeypatch.setattr(plataforma, "EH_WINDOWS", True)
    abertos = []
    monkeypatch.setattr(plataforma.os, "startfile", abertos.append, raising=False)

    plataforma.abrir_no_sistema(r"C:\fichas\4500.xlsx")

    assert abertos == [r"C:\fichas\4500.xlsx"]


def test_no_mac_usa_open(monkeypatch, registrar_subprocess):
    monkeypatch.setattr(plataforma, "EH_WINDOWS", False)
    monkeypatch.setattr(plataforma, "EH_MAC", True)

    plataforma.abrir_no_sistema("/tmp/ficha.xlsx")

    assert registrar_subprocess == [["open", "/tmp/ficha.xlsx"]]


def test_no_linux_usa_xdg_open(monkeypatch, registrar_subprocess):
    """O conserto: as 3 cópias antigas mandavam `open` no Linux também.

    `open` no Linux não é o abridor de arquivos (é um comando de terminal
    virtual, quando existe). O efeito era o botão não fazer nada, sem erro.
    """
    monkeypatch.setattr(plataforma, "EH_WINDOWS", False)
    monkeypatch.setattr(plataforma, "EH_MAC", False)

    plataforma.abrir_no_sistema("/home/luan/ficha.xlsx")

    assert registrar_subprocess == [["xdg-open", "/home/luan/ficha.xlsx"]]


def test_aceita_pathlike(monkeypatch, tmp_path):
    """As telas passam `str`, mas `Path` é o tipo natural do resto do projeto."""
    monkeypatch.setattr(plataforma, "EH_WINDOWS", True)
    abertos = []
    monkeypatch.setattr(plataforma.os, "startfile", abertos.append, raising=False)

    plataforma.abrir_no_sistema(tmp_path / "x.xlsx")

    assert abertos == [str(tmp_path / "x.xlsx")]


def test_nao_valida_existencia(monkeypatch):
    """Quem chama decide a mensagem — as telas já dizem "não encontrado"."""
    monkeypatch.setattr(plataforma, "EH_WINDOWS", True)
    abertos = []
    monkeypatch.setattr(plataforma.os, "startfile", abertos.append, raising=False)

    plataforma.abrir_no_sistema("nao_existe_em_lugar_nenhum.xlsx")

    assert abertos == ["nao_existe_em_lugar_nenhum.xlsx"]


# =============================================================================
# C. abrir_pasta_criando_se_preciso
# =============================================================================

def test_cria_a_pasta_que_ainda_nao_existe(monkeypatch, tmp_path):
    """O botão "abrir logs": a pasta só nasce depois da 1ª tarefa de IA."""
    monkeypatch.setattr(plataforma, "EH_WINDOWS", True)
    abertos = []
    monkeypatch.setattr(plataforma.os, "startfile", abertos.append, raising=False)

    pasta = tmp_path / "logs"
    assert not pasta.exists()

    plataforma.abrir_pasta_criando_se_preciso(pasta)

    assert pasta.is_dir()
    assert abertos == [str(pasta)]


def test_pasta_existente_nao_da_erro(monkeypatch, tmp_path):
    monkeypatch.setattr(plataforma, "EH_WINDOWS", True)
    monkeypatch.setattr(plataforma.os, "startfile", lambda _c: None, raising=False)

    pasta = tmp_path / "ja_existe"
    pasta.mkdir()

    plataforma.abrir_pasta_criando_se_preciso(pasta)  # não deve levantar


# =============================================================================
# D. Excel COM — o que realmente prende o app ao Windows
# =============================================================================

def test_fora_do_windows_nao_ha_excel_com(monkeypatch):
    monkeypatch.setattr(plataforma, "EH_WINDOWS", False)
    assert plataforma.tem_excel_com() is False


def test_o_motivo_fora_do_windows_nomeia_o_sistema(monkeypatch):
    monkeypatch.setattr(plataforma, "EH_WINDOWS", False)
    monkeypatch.setattr(plataforma, "EH_MAC", True)

    motivo = plataforma.motivo_sem_excel_com()

    assert motivo is not None
    assert "macOS" in motivo
    assert "Windows" in motivo


def test_o_motivo_diz_que_excel_online_nao_serve(monkeypatch):
    """A confusão previsível: o usuário tem "Excel", mas o do navegador."""
    monkeypatch.setattr(plataforma, "EH_WINDOWS", True)
    monkeypatch.setattr(
        plataforma, "tem_excel_com", lambda: False
    )
    import builtins

    real_import = builtins.__import__

    def sem_xlwings(nome, *args, **kwargs):
        if nome == "xlwings":
            raise ImportError("sem Excel registrado no COM")
        return real_import(nome, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", sem_xlwings)

    motivo = plataforma.motivo_sem_excel_com()

    assert motivo is not None
    assert "Excel Online" in motivo
    assert "LibreOffice" in motivo


def test_com_tudo_disponivel_o_motivo_e_none(monkeypatch):
    monkeypatch.setattr(plataforma, "EH_WINDOWS", True)
    # `xlwings` é stubado pelo conftest, então o import funciona.
    assert plataforma.motivo_sem_excel_com() is None
    assert plataforma.tem_excel_com() is True


# =============================================================================
# E. A fronteira é de fato única
# =============================================================================

def test_nenhuma_view_chama_os_startfile_diretamente():
    """O ponto do checkpoint: a dependência do SO fica num lugar só.

    Uma tela nova que copie o padrão antigo (`os.startfile` + `except
    AttributeError`) reintroduz o bug do Linux e volta a espalhar a
    dependência. Este teste reprova isso na revisão, não em produção.
    """
    import pathlib

    raiz = pathlib.Path(__file__).resolve().parent.parent
    ofensores = []

    for caminho in (raiz / "sigft").rglob("*.py"):
        if caminho.name == "plataforma.py":
            continue  # é a casa dele
        fonte = caminho.read_text(encoding="utf-8")
        for numero, linha in enumerate(fonte.split("\n"), start=1):
            if "os.startfile" in linha and not linha.strip().startswith("#"):
                ofensores.append(f"{caminho.relative_to(raiz)}:{numero}")

    assert ofensores == [], (
        "`os.startfile` fora de core/plataforma.py:\n  " + "\n  ".join(ofensores)
        + "\n\nUse `plataforma.abrir_no_sistema(...)`."
    )
