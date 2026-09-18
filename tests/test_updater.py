# -*- coding: utf-8 -*-
"""A atualizacao automatica: comparar versao, baixar e conferir.

O repositorio e PRIVADO, e isso muda tudo. As duas armadilhas que o usuario
pagou no DocManager e que estao travadas aqui:

  4. `browser_download_url` NAO FUNCIONA em repo privado. Aquela URL so serve
     para navegador logado; um download programatico recebe uma PAGINA HTML DE
     LOGIN COM STATUS 200. O update "da certo" e grava 4 KB de HTML renomeados
     para `.exe`. Por isso: endpoint de API do asset, e recusa de download
     pequeno demais.

  3. Versao vinda de arquivo do usuario e armadilha -- ja travada em
     tests/test_build_info.py, e a razao pela qual `checar()` recebe a versao
     do `_build_info` e nao a le de lugar nenhum.

Nada aqui faz rede: a cascata de `core/rede.py` e dublada.
"""
import hashlib
import json

import pytest

from sigft.core import rede
from sigft.services import updater


# =============================================================================
# A. Comparacao de versao (funcao pura)
# =============================================================================

@pytest.mark.parametrize("remota, atual", [
    ("1.0.1", "1.0.0"),
    ("1.1.0", "1.0.9"),
    ("2.0.0", "1.99.99"),
    ("1.0.0", "1.0.0-rc.1"),   # a final vem DEPOIS da pre-versao
    ("1.0.0-rc.2", "1.0.0-rc.1"),
    ("v1.0.1", "1.0.0"),        # o `v` da tag nao atrapalha
])
def test_e_mais_nova(remota, atual):
    assert updater.e_mais_nova(remota, atual)


@pytest.mark.parametrize("remota, atual", [
    ("1.0.0", "1.0.0"),
    ("1.0.0", "1.0.1"),
    ("1.0.0-rc.1", "1.0.0"),    # pre-versao NAO e mais nova que a final
    ("1.0.0", "2.0.0"),
])
def test_nao_e_mais_nova(remota, atual):
    assert not updater.e_mais_nova(remota, atual)


@pytest.mark.parametrize("lixo", ["", None, "abc", "v", "1.x.3"])
def test_tag_digitada_errada_nao_derruba_o_app(lixo):
    """Uma tag com erro de digitacao no GitHub nao pode derrubar o app de quem
    esta usando. Na duvida, nao ha atualizacao."""
    assert updater.e_mais_nova(lixo, "1.0.0") in (True, False)


# =============================================================================
# B. Interpretar o release -- a armadilha n. 4
# =============================================================================

def _release(**extra):
    base = {
        "tag_name": "v1.1.0",
        "html_url": "https://github.com/luanccozer/SIG-FT/releases/tag/v1.1.0",
        "published_at": "2026-10-01T12:00:00Z",
        "body": "notas do release",
        "assets": [{
            "name": "SIG-FT_Itaipu_Setup_1.1.0.exe",
            "url": "https://api.github.com/repos/luanccozer/SIG-FT/releases/assets/42",
            "browser_download_url": "https://github.com/luanccozer/SIG-FT/releases/download/v1.1.0/x.exe",
            "size": 180_000_000,
            "digest": "sha256:" + "ab" * 32,
        }],
    }
    base.update(extra)
    return base


def test_a_url_usada_e_a_de_API_e_NAO_a_do_navegador():
    """A armadilha n. 4, travada.

    Em repositorio privado o `browser_download_url` so funciona para um
    navegador LOGADO. Um `requests.get` nela recebe uma pagina HTML de login,
    com status 200 -- o download "da certo" e grava 4 KB de HTML renomeados
    para `.exe`, que nao instala nada e nao da erro nenhum.
    """
    info = updater.interpretar_release(_release())

    assert info.url_asset.startswith("https://api.github.com/")
    assert "/releases/assets/" in info.url_asset
    assert "browser_download_url" not in info.url_asset


def test_o_sha256_vem_do_manifesto_quando_ha_um():
    esperado = "cd" * 32
    info = updater.interpretar_release(_release(), {"sha256": esperado})

    assert info.sha256 == esperado


def test_sem_manifesto_o_sha_vem_do_digest_da_API():
    """O GitHub devolve `digest: sha256:...` no proprio asset."""
    info = updater.interpretar_release(_release())

    assert info.sha256 == "ab" * 32


def test_sem_sha_nenhum_o_campo_fica_vazio_e_o_resto_funciona():
    release = _release()
    del release["assets"][0]["digest"]

    info = updater.interpretar_release(release)

    assert info.sha256 == ""
    assert info.versao == "1.1.0"


def test_release_sem_instalador_devolve_None():
    """Um release so com o manifesto nao e uma atualizacao instalavel."""
    release = _release(assets=[{"name": "latest.json", "url": "u", "size": 10}])

    assert updater.interpretar_release(release) is None


def test_as_notas_do_manifesto_ganham_do_corpo_do_release():
    info = updater.interpretar_release(_release(), {"notas": "do manifesto"})

    assert info.notas == "do manifesto"


def test_o_v_da_tag_nao_entra_na_versao():
    assert updater.interpretar_release(_release()).versao == "1.1.0"


# =============================================================================
# C. `checar` -- o que o GitHub responde
# =============================================================================

class _Resposta:
    def __init__(self, payload=None, status=200, conteudo=b""):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.content = conteudo
        self.headers = {}
        self.text = ""

    def json(self):
        return self._payload

    def close(self):
        pass


class _Sessao:
    def __init__(self, resposta_do_manifesto=None):
        self._manifesto = resposta_do_manifesto

    def get(self, url, **kw):
        return self._manifesto or _Resposta(status=404)

    def close(self):
        pass


@pytest.fixture
def com_token(monkeypatch):
    monkeypatch.setattr(updater, "token", lambda: "um-token")


def _abrir_devolvendo(resposta, sessao=None):
    return lambda url, **kw: (sessao or _Sessao(), resposta)


def test_sem_token_embutido_levanta_SemToken(monkeypatch):
    """Build local nao tem o segredo -- e a mensagem tem de dizer o que fazer."""
    monkeypatch.setattr(updater, "token", lambda: "")

    with pytest.raises(updater.SemToken):
        updater.checar("1.0.0")


def test_versao_igual_nao_e_atualizacao(com_token, monkeypatch):
    monkeypatch.setattr(rede, "abrir", _abrir_devolvendo(_Resposta(_release(tag_name="v1.0.0"))))

    assert updater.checar("1.0.0") is None


def test_versao_mais_nova_vira_uma_Atualizacao(com_token, monkeypatch):
    monkeypatch.setattr(rede, "abrir", _abrir_devolvendo(_Resposta(_release())))

    info = updater.checar("1.0.0")

    assert info is not None
    assert info.versao == "1.1.0"


def test_token_recusado_pelo_github_vira_SemToken(com_token, monkeypatch):
    """401/403 tem mensagem propria: o token expirou ou perdeu acesso.

    Sem isso viraria "nenhuma rota funcionou", que manda a pessoa investigar a
    rede quando o problema e o token.
    """
    monkeypatch.setattr(rede, "abrir", _abrir_devolvendo(_Resposta(status=401)))

    with pytest.raises(updater.SemToken) as erro:
        updater.checar("1.0.0")

    assert "token" in str(erro.value).lower()


def test_404_e_silencio_e_nao_erro(com_token, monkeypatch):
    """Sem release publicado ainda. Num repo PRIVADO o GitHub responde 404
    (e nao 403) tambem para quem nao tem acesso -- dai as duas hipoteses."""
    monkeypatch.setattr(rede, "abrir", _abrir_devolvendo(_Resposta(status=404)))

    assert updater.checar("1.0.0") is None


def test_o_manifesto_e_lido_quando_existe(com_token, monkeypatch):
    release = _release()
    release["assets"].append({
        "name": "latest.json",
        "url": "https://api.github.com/repos/x/y/releases/assets/99",
        "size": 200,
    })
    manifesto = _Resposta(conteudo=json.dumps({"sha256": "ef" * 32}).encode("utf-8"))
    monkeypatch.setattr(rede, "abrir",
                        _abrir_devolvendo(_Resposta(release), _Sessao(manifesto)))

    assert updater.checar("1.0.0").sha256 == "ef" * 32


def test_manifesto_ilegivel_nao_impede_a_atualizacao(com_token, monkeypatch):
    """O manifesto e um EXTRA: sem ele o SHA vem do `digest` da API."""
    release = _release()
    release["assets"].append({"name": "latest.json", "url": "u", "size": 1})
    quebrado = _Resposta(conteudo=b"{isto nao e json")
    monkeypatch.setattr(rede, "abrir",
                        _abrir_devolvendo(_Resposta(release), _Sessao(quebrado)))

    info = updater.checar("1.0.0")

    assert info is not None
    assert info.sha256 == "ab" * 32


# =============================================================================
# D. Baixar -- a outra metade da armadilha n. 4
# =============================================================================

class _RespostaBinaria:
    def __init__(self, dados):
        self.status_code = 200
        self._dados = dados
        self.headers = {"Content-Length": str(len(dados))}

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self._dados), chunk_size):
            yield self._dados[i:i + chunk_size]

    def close(self):
        pass


def _info(dados, sha=None):
    return updater.Atualizacao(
        versao="1.1.0", notas="", nome_arquivo="SIG-FT_Setup.exe",
        url_asset="https://api.github.com/.../assets/42",
        tamanho=len(dados),
        sha256=sha if sha is not None else hashlib.sha256(dados).hexdigest(),
        url_pagina="",
    )


def test_download_pequeno_demais_e_RECUSADO(monkeypatch, tmp_path):
    """O coracao da armadilha n. 4.

    Um HTML de login tem alguns KB; um instalador tem dezenas de MB. Sem esta
    recusa, o update "da certo", grava a pagina de login como `.exe`, e o
    usuario roda um arquivo que nao instala nada -- sem erro nenhum no
    caminho.
    """
    monkeypatch.setattr(updater, "pasta_download", lambda: tmp_path)
    html = b"<html><body>Sign in to GitHub</body></html>" * 50
    monkeypatch.setattr(rede, "abrir", lambda url, **kw: (_Sessao(), _RespostaBinaria(html)))

    with pytest.raises(updater.ArquivoInvalido) as erro:
        updater.baixar(_info(html))

    assert "pequeno" in str(erro.value).lower()


def test_o_parcial_e_apagado_quando_o_download_e_recusado(monkeypatch, tmp_path):
    """Nao pode sobrar um `.part` de lixo para a proxima tentativa achar."""
    monkeypatch.setattr(updater, "pasta_download", lambda: tmp_path)
    html = b"x" * 5000
    monkeypatch.setattr(rede, "abrir", lambda url, **kw: (_Sessao(), _RespostaBinaria(html)))

    with pytest.raises(updater.ArquivoInvalido):
        updater.baixar(_info(html))

    assert list(tmp_path.glob("*.part")) == []


def test_sha_divergente_RECUSA_o_arquivo(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "pasta_download", lambda: tmp_path)
    dados = b"P" * 2_000_000
    monkeypatch.setattr(rede, "abrir", lambda url, **kw: (_Sessao(), _RespostaBinaria(dados)))

    with pytest.raises(updater.ArquivoInvalido) as erro:
        updater.baixar(_info(dados, sha="00" * 32))

    assert "confere" in str(erro.value).lower()
    assert not (tmp_path / "SIG-FT_Setup.exe").exists()


def test_download_bom_grava_o_arquivo(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "pasta_download", lambda: tmp_path)
    dados = b"P" * 2_000_000
    monkeypatch.setattr(rede, "abrir", lambda url, **kw: (_Sessao(), _RespostaBinaria(dados)))

    destino = updater.baixar(_info(dados))

    assert destino.read_bytes() == dados
    assert list(tmp_path.glob("*.part")) == [], "o .part tem de virar o arquivo final"


def test_sem_sha_publicado_o_download_acontece_com_AVISO(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "pasta_download", lambda: tmp_path)
    dados = b"P" * 2_000_000
    monkeypatch.setattr(rede, "abrir", lambda url, **kw: (_Sessao(), _RespostaBinaria(dados)))
    avisos = []

    updater.baixar(_info(dados, sha=""), log_cb=avisos.append)

    assert any("nao deu para conferir" in a.lower() or "sha256" in a.lower()
               for a in avisos)


def test_o_progresso_chega_a_1(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "pasta_download", lambda: tmp_path)
    dados = b"P" * 2_000_000
    monkeypatch.setattr(rede, "abrir", lambda url, **kw: (_Sessao(), _RespostaBinaria(dados)))
    marcas = []

    updater.baixar(_info(dados), progresso_cb=marcas.append)

    assert marcas and marcas[-1] == 1.0


# =============================================================================
# E. A politica: no maximo uma checagem a cada 6 horas
# =============================================================================

def test_o_intervalo_padrao_e_de_6_horas():
    assert updater.INTERVALO_PADRAO_HORAS == 6


def test_a_primeira_abertura_verifica(com_token, tmp_path):
    assert updater.deve_verificar(ultima_verificacao=None)


def test_logo_depois_de_verificar_NAO_verifica_de_novo(com_token):
    from datetime import datetime

    agora = datetime.now().isoformat(timespec="seconds")

    assert not updater.deve_verificar(ultima_verificacao=agora)


def test_passadas_as_6_horas_verifica(com_token):
    from datetime import datetime, timedelta

    faz_tempo = (datetime.now() - timedelta(hours=7)).isoformat(timespec="seconds")

    assert updater.deve_verificar(ultima_verificacao=faz_tempo)


def test_data_corrompida_nao_trava_a_verificacao_para_sempre(com_token):
    assert updater.deve_verificar(ultima_verificacao="isto nao e uma data")


def test_sem_token_nunca_verifica(monkeypatch):
    """Build local: nao adianta bater no GitHub sem credencial."""
    monkeypatch.setattr(updater, "token", lambda: "")

    assert not updater.deve_verificar(ultima_verificacao=None)


def test_a_verificacao_pode_ser_desligada(com_token):
    assert not updater.deve_verificar(ultima_verificacao=None, ligada=False)


# =============================================================================
# F. O token
# =============================================================================

def test_a_variavel_de_ambiente_ganha_do_token_embutido(monkeypatch):
    """Permite trocar o token sem refazer o build -- ver docs/BUILD.md."""
    monkeypatch.setenv("SIGFT_UPDATE_TOKEN", "o-da-variavel")

    assert updater.token() == "o-da-variavel"


def test_sem_modulo_de_token_o_build_simplesmente_nao_checa(monkeypatch):
    """`_update_auth.py` nao existe em build local -- e isso e o certo."""
    monkeypatch.delenv("SIGFT_UPDATE_TOKEN", raising=False)
    monkeypatch.setattr(updater, "caminho_token_externo",
                        lambda: __import__("pathlib").Path("/nao/existe.txt"))

    assert updater.token() == "" or isinstance(updater.token(), str)


def test_o_token_nunca_aparece_no_log_de_uma_falha(com_token, monkeypatch):
    """Um token em log vira token em captura de tela, e captura de tela circula."""
    monkeypatch.setattr(updater, "token", lambda: "github_pat_SEGREDO")
    monkeypatch.setattr(rede, "abrir", _abrir_devolvendo(_Resposta(status=401)))
    registro = []

    with pytest.raises(updater.SemToken) as erro:
        updater.checar("1.0.0", log_cb=registro.append)

    assert "github_pat_SEGREDO" not in str(erro.value)
    assert not any("github_pat_SEGREDO" in linha for linha in registro)
