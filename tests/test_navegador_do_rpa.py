# -*- coding: utf-8 -*-
"""Achar o navegador do RPA -- o que o `SIG-FT Itaipu.bat` fazia e o app nao.

O buraco que este modulo fecha
------------------------------
O SIG-FT nao empacota o Chromium, de proposito (docs/SEGURANCA_TI.md: um
navegador embutido congela na versao do dia do build e fica fora do que a TI
atualiza -- a objecao mais forte numa revisao de seguranca corporativa). Em vez
disso ele usa o Chrome ou o Edge que a propria empresa ja instala e mantem.

So que quem ACHAVA esse navegador era o `SIG-FT Itaipu.bat`: ele sondava os
caminhos e definia `SIGFT_PLAYWRIGHT_EXECUTABLE`. O
`sigft/core/rpa/playwright_engine.py` so LE a variavel (`os.environ.get`).

Com o instalador, o `.bat` deixa de existir na maquina do usuario. Ninguem
define a variavel, e o RPA fica sem navegador -- em TODA maquina. E o sintoma
so aparece quando a pessoa aciona um modulo de portal, no meio do trabalho,
depois de o app ter aberto normalmente.

Por isso a sondagem muda de casa: sai do `.bat` e entra aqui.
"""
import os

import pytest

from sigft.core.rpa import navegador


@pytest.fixture
def sem_variavel(monkeypatch):
    monkeypatch.delenv("SIGFT_PLAYWRIGHT_EXECUTABLE", raising=False)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)


def _criar(raiz, *relativos):
    """Cria arquivos vazios e devolve o primeiro caminho."""
    criados = []
    for relativo in relativos:
        destino = raiz / relativo
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text("", encoding="utf-8")
        criados.append(str(destino))
    return criados


# =============================================================================
# A. A escolha explicita ganha de tudo
# =============================================================================

def test_a_variavel_de_ambiente_ganha_da_sondagem(monkeypatch, tmp_path):
    """Quem definiu `SIGFT_PLAYWRIGHT_EXECUTABLE` mandou -- e continua mandando.

    E documentado no README como a saida para quem tem o navegador em lugar
    fora do padrao. Uma sondagem que atropelasse isso quebraria quem ja
    resolveu o problema na mao.
    """
    (escolhido,) = _criar(tmp_path, "meu-chrome.exe")
    monkeypatch.setenv("SIGFT_PLAYWRIGHT_EXECUTABLE", escolhido)

    assert navegador.encontrar_navegador() == escolhido


def test_variavel_apontando_para_arquivo_inexistente_e_ignorada(monkeypatch, tmp_path):
    """Caminho errado numa variavel e tipo de erro, nao escolha.

    Respeita-lo cegamente faria o Playwright estourar com "executable doesn't
    exist" -- quando havia um Chrome instalado ali do lado.
    """
    monkeypatch.setenv("SIGFT_PLAYWRIGHT_EXECUTABLE", str(tmp_path / "nao-existe.exe"))
    (chrome,) = _criar(tmp_path, "Chrome/chrome.exe")
    monkeypatch.setattr(navegador, "_candidatos", lambda: [chrome])

    assert navegador.encontrar_navegador() == chrome


# =============================================================================
# B. A ordem de busca -- a mesma do `SIG-FT Itaipu.bat`
# =============================================================================

def test_chrome_vem_antes_do_edge(sem_variavel, monkeypatch, tmp_path):
    """Mesma ordem do `.bat` que isto substitui. O Chrome e o mais testado
    contra o portal PMIB; trocar a preferencia seria mudanca de comportamento
    disfarcada de refatoracao."""
    chrome, edge = _criar(tmp_path, "Google/Chrome/chrome.exe", "Edge/msedge.exe")
    monkeypatch.setattr(navegador, "_candidatos", lambda: [chrome, edge])

    assert navegador.encontrar_navegador() == chrome


def test_sem_chrome_o_edge_serve(sem_variavel, monkeypatch, tmp_path):
    (edge,) = _criar(tmp_path, "Edge/msedge.exe")
    monkeypatch.setattr(navegador, "_candidatos",
                        lambda: [str(tmp_path / "nao-existe.exe"), edge])

    assert navegador.encontrar_navegador() == edge


def test_sem_nenhum_navegador_devolve_None(sem_variavel, monkeypatch, tmp_path):
    """O app tem de ABRIR mesmo assim.

    As telas de planilha e de IA nao dependem do navegador. Derrubar a
    abertura por causa do RPA tiraria do usuario tudo o que funciona.
    """
    monkeypatch.setattr(navegador, "_candidatos",
                        lambda: [str(tmp_path / "nada.exe")])

    assert navegador.encontrar_navegador() is None


def test_a_lista_cobre_TODOS_os_lugares_que_o_bat_sondava():
    """O guard forte desta frente: compara com o `SIG-FT Itaipu.bat` DE VERDADE.

    Nao basta "tem chrome.exe na lista". O que importa e que nenhum dos
    caminhos que o `.bat` sondava se perdeu na mudanca de casa -- um caminho
    perdido significa: o app deixa de achar o navegador numa configuracao que
    ANTES funcionava, e so na maquina de quem tem o Chrome naquele lugar.

    A comparacao inclui a RAIZ (ProgramFiles, ProgramFiles(x86), LOCALAPPDATA)
    e nao so a cauda. A primeira versao deste teste apagava a variavel de
    ambiente antes de comparar -- e com isso os TRES caminhos do Chrome viravam
    a mesma tupla. Ele dava verde por acidente, "cobrindo" o que nao cobria.

    Roda em qualquer sistema (as raizes sao parametros, nao `os.environ`): o
    CI e Linux, e guard que so roda no Windows nao guarda nada.
    """
    import pathlib
    import re

    bat = pathlib.Path(__file__).resolve().parent.parent / "SIG-FT Itaipu.bat"
    if not bat.is_file():
        pytest.skip("o launcher do Box ja foi aposentado")

    MARCADOR = {
        "%ProgramFiles%": "<PF>",
        "%ProgramFiles(x86)%": "<PF86>",
        "%LOCALAPPDATA%": "<LOCAL>",
    }

    def _tupla(caminho, marcadores):
        for bruto, marca in marcadores.items():
            caminho = caminho.replace(bruto, marca)
        return tuple(p for p in re.split(r"[\\/]+", caminho.lower()) if p)

    texto = bat.read_text(encoding="ascii", errors="ignore")
    do_bat = re.findall(r'if exist "([^"]*(?:chrome|msedge)\.exe)"', texto, re.I)
    assert len(do_bat) >= 5, f"so achei {len(do_bat)} sondagens no .bat"

    nossos = {
        _tupla(c, {})
        for c in navegador.candidatos_do_windows(
            programas="<PF>", programas_x86="<PF86>", local="<LOCAL>")
    }

    faltando = [c for c in do_bat if _tupla(c, MARCADOR) not in nossos]

    assert not faltando, (
        "estes caminhos o `SIG-FT Itaipu.bat` sondava e o app NAO sonda:\n  "
        + "\n  ".join(faltando)
        + "\n\nQuem tiver o navegador ali perde o RPA sem nenhum aviso."
    )


def test_chrome_e_edge_estao_os_dois_na_lista():
    candidatos = " ".join(navegador.candidatos_do_windows()).lower()

    assert "chrome.exe" in candidatos
    assert "msedge.exe" in candidatos


# =============================================================================
# C. Fora do Windows
# =============================================================================

@pytest.mark.skipif(os.name == "nt", reason="este e o comportamento fora do Windows")
def test_fora_do_windows_a_sondagem_nao_estoura(sem_variavel):
    """Desenvolvimento em Linux/macOS: devolve `None` e segue."""
    assert navegador.encontrar_navegador() is None


# =============================================================================
# D. O Chromium empacotado, quando houver
# =============================================================================
#
# Modelo do Corella Suite: se o build levar um `ms-playwright/` ao lado do
# `.exe`, o app aponta o Playwright para la. Hoje o SIG-FT NAO empacota o
# navegador (SEGURANCA_TI.md), entao a pasta nao existe e nada acontece -- mas
# a via fica pronta, e e a rede de seguranca para a maquina onde nao ha
# Chrome nem Edge.

def test_a_pasta_empacotada_e_apontada_quando_existe(monkeypatch, tmp_path):
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    (tmp_path / "ms-playwright" / "chromium-1234").mkdir(parents=True)

    navegador.apontar_navegador_empacotado(pasta_do_programa=tmp_path)

    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == str(tmp_path / "ms-playwright")


def test_sem_a_pasta_nada_e_definido(monkeypatch, tmp_path):
    """E o caso NORMAL do SIG-FT hoje: o pacote nao leva navegador."""
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)

    navegador.apontar_navegador_empacotado(pasta_do_programa=tmp_path)

    assert "PLAYWRIGHT_BROWSERS_PATH" not in os.environ


def test_quem_ja_definiu_a_variavel_continua_mandando(monkeypatch, tmp_path):
    """`setdefault`, nunca atribuicao.

    Quem definiu `PLAYWRIGHT_BROWSERS_PATH` na maquina -- porque tem navegador
    proprio, ou porque a TI padronizou um caminho -- nao pode ser atropelado
    por uma pasta que o build deixou ali.
    """
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", "/o/que/eu/escolhi")
    (tmp_path / "ms-playwright" / "chromium-1234").mkdir(parents=True)

    navegador.apontar_navegador_empacotado(pasta_do_programa=tmp_path)

    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == "/o/que/eu/escolhi"


def test_apontar_nunca_estoura(monkeypatch):
    """Roda no bootstrap: uma excecao aqui impede o app de abrir."""
    navegador.apontar_navegador_empacotado(pasta_do_programa="/caminho/que/nao/existe")


# =============================================================================
# E. O certificado da empresa para o processo Node do Playwright
# =============================================================================

def test_o_node_herda_o_SSL_CERT_FILE(monkeypatch, tmp_path):
    """O que o `.bat` fazia, e que tambem se perderia com o instalador.

    O processo Node do Playwright ignora `REQUESTS_CA_BUNDLE`/`SSL_CERT_FILE`;
    a variavel que ele respeita e `NODE_EXTRA_CA_CERTS`. Sem esta ponte, numa
    rede com Zscaler o Playwright falha no download do navegador com erro de
    certificado.
    """
    (cert,) = _criar(tmp_path, "zscaler.pem")
    monkeypatch.setenv("SSL_CERT_FILE", cert)
    monkeypatch.delenv("NODE_EXTRA_CA_CERTS", raising=False)

    navegador.propagar_certificado_para_o_node()

    assert os.environ["NODE_EXTRA_CA_CERTS"] == cert


def test_sem_SSL_CERT_FILE_nada_e_definido(monkeypatch):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("NODE_EXTRA_CA_CERTS", raising=False)

    navegador.propagar_certificado_para_o_node()

    assert "NODE_EXTRA_CA_CERTS" not in os.environ


def test_NODE_EXTRA_CA_CERTS_ja_definido_nao_e_sobrescrito(monkeypatch, tmp_path):
    (cert,) = _criar(tmp_path, "zscaler.pem")
    monkeypatch.setenv("SSL_CERT_FILE", cert)
    monkeypatch.setenv("NODE_EXTRA_CA_CERTS", "/ja/escolhido.pem")

    navegador.propagar_certificado_para_o_node()

    assert os.environ["NODE_EXTRA_CA_CERTS"] == "/ja/escolhido.pem"


# =============================================================================
# F. O engine usa o que foi achado
# =============================================================================

def test_o_engine_recebe_o_navegador_encontrado(sem_variavel, monkeypatch, tmp_path):
    """A ponta que fecha a frente.

    Achar o navegador nao serve de nada se o `playwright_engine` continuar
    olhando so para a variavel de ambiente que ninguem define mais.
    """
    (chrome,) = _criar(tmp_path, "chrome.exe")
    monkeypatch.setattr(navegador, "_candidatos", lambda: [chrome])

    navegador.preparar_ambiente_do_rpa()

    assert os.environ["SIGFT_PLAYWRIGHT_EXECUTABLE"] == chrome
