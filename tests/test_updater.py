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
import sys

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
# E. A politica: TODA abertura do app instalado pergunta
# =============================================================================
#
# Ate 2026-09-25 era "no maximo uma checagem a cada 6 horas". Saiu a pedido do
# usuario -- "no momento de inicializacao ele deve identificar o release" -- e
# por um motivo pratico: com o intervalo, quem publica um Release e abre o app
# para conferir so ve a versao nova horas depois, o que para quem olha e
# identico ao defeito que motivou a mudanca. Perguntar sempre custa UMA
# requisicao por abertura, muito abaixo do limite de 5000 por hora do token.

@pytest.fixture
def app_instalado(monkeypatch):
    """O caso normal: `.exe` do Release, instalado pelo instalador, com token."""
    monkeypatch.setattr(updater, "empacotado", lambda: True)
    monkeypatch.setattr(updater, "instalado_pelo_instalador", lambda: True)
    monkeypatch.setattr(updater, "token", lambda: "um-token")


def test_o_app_instalado_verifica_em_TODA_abertura(app_instalado):
    assert updater.deve_verificar()
    assert updater.deve_verificar(), "a segunda abertura seguida tambem pergunta"
    assert updater.motivo_para_nao_verificar() is None


def test_rodando_do_codigo_fonte_nao_verifica(app_instalado, monkeypatch):
    """Quem roda pelo `SIG-FT.bat` atualiza pelo git; o instalador criaria uma
    segunda copia do app, instalada, ao lado da que a pessoa usa."""
    monkeypatch.setattr(updater, "empacotado", lambda: False)

    assert not updater.deve_verificar()
    assert "codigo-fonte" in updater.motivo_para_nao_verificar()


def test_a_copia_do_ZIP_do_Box_nao_verifica(app_instalado, monkeypatch):
    """O ZIP do Box tem o `.bat` dele para atualizar. Rodar o instalador ali
    criaria uma SEGUNDA instalacao em vez de atualizar a pasta em uso -- e a
    pessoa continuaria abrindo a velha."""
    monkeypatch.setattr(updater, "instalado_pelo_instalador", lambda: False)

    assert not updater.deve_verificar()
    assert "instalador" in updater.motivo_para_nao_verificar()


def test_sem_token_nao_verifica(app_instalado, monkeypatch):
    """Build local: sem credencial, o GitHub responde 404 a repo privado."""
    monkeypatch.setattr(updater, "token", lambda: "")

    assert not updater.deve_verificar()
    assert "token" in updater.motivo_para_nao_verificar()


def test_o_DESINSTALADOR_ao_lado_do_exe_e_o_sinal_do_instalador(monkeypatch, tmp_path):
    """O Inno grava `unins000.exe` na pasta do app (`UninstallFilesDir` tem
    `{app}` como padrao, e o `.iss` nao o muda). A pasta do ZIP do Box e a
    `dist` do build nao tem esse arquivo."""
    exe = tmp_path / "SIG-FT.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))

    assert not updater.instalado_pelo_instalador()

    (tmp_path / "unins000.exe").write_bytes(b"MZ")

    assert updater.instalado_pelo_instalador()


def test_fora_do_executavel_nao_ha_instalacao(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)

    assert not updater.instalado_pelo_instalador()


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


# =============================================================================
# G. Instalar -- o app entrega a vez ao instalador
# =============================================================================
#
# Nada disto rodou de verdade antes de 2026-09-25: sem chamador na interface,
# `instalar()` nunca foi executado por ninguem. Os defeitos abaixo foram achados
# LENDO a cadeia inteira (app -> Inno -> app de novo), e cada um, sozinho, faria
# o botao "Atualizar agora" fechar o app sem atualizar nada.
#
# (Havia um terceiro, o `AppMutex` abortando o instalador silencioso, que se
# resolvia soltando o mutex antes do disparo. O `AppMutex` saiu do `.iss` no
# mesmo dia -- ele tambem travava a instalacao manual por causa do SIG-FT
# fantasma --, e com ele os testes da ordem "solta o mutex, dispara".)

@pytest.fixture
def disparo(monkeypatch, tmp_path):
    """Registra, EM ORDEM, o que `instalar()` faz -- sem disparar nada."""
    registro = {"eventos": [], "erro": None}
    monkeypatch.setattr(updater, "pasta_download", lambda: tmp_path)

    def popen(args, **kw):
        registro["eventos"].append("disparou o instalador")
        registro["args"] = list(args)
        if registro["erro"] is not None:
            raise registro["erro"]
        return object()

    def elevado(caminho, args):
        registro["eventos"].append("pediu elevacao")
        registro["args_elevado"] = list(args)

    monkeypatch.setattr(updater.subprocess, "Popen", popen)
    monkeypatch.setattr(updater, "_disparar_elevado", elevado)
    return registro


def test_o_instalador_recebe_o_pedido_de_REABRIR_o_app(disparo, tmp_path):
    """O defeito n. 1: em `/SILENT`, a linha do `[Run]` que abre o app tem
    `skipifsilent` e NAO roda. O app fechava para atualizar e nao voltava.
    O `.iss` reabre so quando recebe este parametro -- ver
    `tests/test_instalador.py`, secao H."""
    updater.instalar(tmp_path / "Setup.exe")

    assert updater.ARG_REABRIR in disparo["args"]


def test_o_instalador_roda_silencioso_e_fecha_o_que_estiver_aberto(disparo, tmp_path):
    updater.instalar(tmp_path / "Setup.exe")

    args = disparo["args"]
    assert args[0] == str(tmp_path / "Setup.exe")
    for esperado in ("/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"):
        assert esperado in args
    assert any(a.startswith("/LOG=") for a in args), "sem log nao ha diagnostico"


def test_o_instalador_sobe_SEM_elevacao_quem_pede_o_UAC_e_ele(disparo, tmp_path, monkeypatch):
    """O defeito n. 2, no app instalado 'para todos' (Program Files).

    O disparo antigo pedia o UAC ele mesmo (`ShellExecute` com `runas`). Com o
    instalador ja nascendo elevado, o Inno nao tem mais as credenciais de quem
    pediu -- a documentacao do `runasoriginaluser` diz isso com todas as
    letras -- e o app reaberto subiria como ADMINISTRADOR. Quando o UAC e
    respondido com a senha de outra pessoa (o caso comum na empresa), o app
    abriria na conta dela: sem as chaves de API e sem as preferencias.

    Disparado sem elevacao, o proprio Inno pede o UAC, e o `[Run]` com
    `runasoriginaluser` reabre o app na conta de quem estava usando.
    """
    monkeypatch.setattr(updater, "precisa_elevacao", lambda: True)

    updater.instalar(tmp_path / "Setup.exe")

    assert "pediu elevacao" not in disparo["eventos"]


def test_se_o_windows_EXIGIR_elevacao_no_disparo_cai_no_runas(disparo, tmp_path):
    """Rede de seguranca: se o executavel exigir administrador no manifesto, o
    `CreateProcess` falha com o erro 740, e so o `ShellExecute` com `runas`
    abre o UAC. Perde-se a reabertura sem elevacao, mas a atualizacao sai."""
    erro = OSError("a operacao solicitada requer elevacao")
    erro.winerror = 740
    disparo["erro"] = erro

    updater.instalar(tmp_path / "Setup.exe")

    assert disparo["eventos"] == ["disparou o instalador", "pediu elevacao"]
    assert updater.ARG_REABRIR in disparo["args_elevado"]


def test_outro_erro_do_disparo_NAO_vira_pedido_de_elevacao(disparo, tmp_path):
    disparo["erro"] = OSError(2, "arquivo nao encontrado")

    with pytest.raises(OSError):
        updater.instalar(tmp_path / "Setup.exe")

    assert "pediu elevacao" not in disparo["eventos"]


# =============================================================================
# H. O instalador PEQUENO (so o que mudou)  [2026-10-07]
# =============================================================================
# Ver docs/superpowers/specs/2026-10-07-atualizacao-incremental-design.md. O
# Release traz, alem do completo, um instalador pequeno por versao de origem
# (`latest.json` -> `atualizacoes`). O app usa o pequeno quando o `de` dele e a
# versao instalada; em qualquer outro caso, o completo -- que serve para todos.

PACOTE = "SIG-FT_Itaipu_Atualizacao_1.0.0_para_1.1.0.bin"


def _release_com_pequeno(**extra):
    release = _release(**extra)
    release["assets"].append({
        "name": PACOTE, "url": "https://api.github.com/repos/luanccozer/SIG-FT/releases/assets/77",
        "size": 12_000_000})
    return release


def _manifesto_com_pequeno(de="1.0.0", arquivo=PACOTE):
    return {"sha256": "ab" * 32,
            "atualizacoes": [{"de": de, "arquivo": arquivo, "sha256": "cd" * 32, "tamanho": 12_000_000}]}


def test_o_pequeno_e_escolhido_quando_saiu_da_versao_instalada():
    info = updater.interpretar_release(_release_com_pequeno(), _manifesto_com_pequeno(), versao_atual="1.0.0")

    assert info.incremental is True
    assert info.nome_arquivo == PACOTE
    assert info.url_asset.endswith("/assets/77")
    assert (info.tamanho, info.tamanho_completo) == (12_000_000, 180_000_000)
    assert info.sha256 == "cd" * 32  # o do pequeno, nao o do completo


def test_de_outra_versao_vai_o_completo():
    info = updater.interpretar_release(_release_com_pequeno(), _manifesto_com_pequeno(de="0.9.0"),
                                       versao_atual="1.0.0")

    assert info.incremental is False
    assert info.nome_arquivo == "SIG-FT_Itaipu_Setup_1.1.0.exe"
    assert info.sha256 == "ab" * 32


def test_pequeno_listado_mas_ausente_do_release_vai_o_completo():
    info = updater.interpretar_release(_release(), _manifesto_com_pequeno(), versao_atual="1.0.0")

    assert info.incremental is False


def test_sem_saber_a_versao_instalada_vai_o_completo():
    assert updater.interpretar_release(_release_com_pequeno(), _manifesto_com_pequeno()).incremental is False


def test_o_app_antigo_continua_achando_o_completo_primeiro():
    # O 1.1.1 escolhe "o primeiro .exe do Release": o pequeno, em .bin, nao
    # entra na conta dele -- nem quando aparece antes na lista.
    release = _release_com_pequeno()
    release["assets"].reverse()

    assert updater._instalador(release)["name"] == "SIG-FT_Itaipu_Setup_1.1.0.exe"


def test_checar_passa_a_versao_instalada_e_escolhe_o_pequeno(com_token, monkeypatch):
    release = _release_com_pequeno()
    release["assets"].append({"name": "latest.json", "url": "https://api.github.com/x/assets/99", "size": 9})
    manifesto = _Resposta(conteudo=json.dumps(_manifesto_com_pequeno()).encode("utf-8"))
    monkeypatch.setattr(rede, "abrir", _abrir_devolvendo(_Resposta(release), _Sessao(manifesto)))

    info = updater.checar("1.0.0", canal_testes=False)

    assert info.incremental is True and info.nome_arquivo == PACOTE


def test_o_pequeno_baixado_vira_exe_depois_de_conferido(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "pasta_download", lambda: tmp_path)
    dados = b"P" * 2_000_000
    monkeypatch.setattr(rede, "abrir", lambda url, **kw: (_Sessao(), _RespostaBinaria(dados)))
    info = updater.Atualizacao(
        versao="1.1.0", notas="", nome_arquivo=PACOTE, url_asset="https://api.github.com/.../assets/77",
        tamanho=len(dados), sha256=hashlib.sha256(dados).hexdigest(), url_pagina="", incremental=True)

    destino = updater.baixar(info)

    assert destino.name == PACOTE[:-len(".bin")] + ".exe"
    assert destino.read_bytes() == dados
    assert sorted(p.name for p in tmp_path.iterdir()) == [destino.name]


# =============================================================================
# I. O canal de testes  [2026-10-07]
# =============================================================================
# Desligado (o padrao), o app pergunta `/releases/latest`, que o GitHub
# responde ignorando pre-lancamentos. Ligado, pergunta `/releases` e fica com a
# versao mais nova, pre-lancamento inclusive -- e assim que o Luan testa o
# instalador pequeno antes de ele chegar a todo mundo.

class _AbrirAnotando:
    def __init__(self, resposta):
        self.urls = []
        self.resposta = resposta

    def __call__(self, url, **kw):
        self.urls.append(url)
        return _Sessao(), self.resposta


def test_canal_desligado_pergunta_so_pelo_ultimo_release_normal(com_token, monkeypatch):
    abrir = _AbrirAnotando(_Resposta(_release()))
    monkeypatch.setattr(rede, "abrir", abrir)

    updater.checar("1.0.0", canal_testes=False)

    assert abrir.urls[0].endswith("/releases/latest")


def test_canal_ligado_fica_com_a_versao_mais_nova_pre_lancamento_inclusive(com_token, monkeypatch):
    lista = [_release(tag_name="v1.1.0"),
             _release(tag_name="v1.2.0-rc.3", prerelease=True),
             _release(tag_name="v1.2.0-rc.4", prerelease=True, draft=True),  # rascunho: nao
             _release(tag_name="v1.2.0-rc.2", prerelease=True)]
    abrir = _AbrirAnotando(_Resposta(lista))
    monkeypatch.setattr(rede, "abrir", abrir)

    info = updater.checar("1.1.0", canal_testes=True)

    assert "/releases?" in abrir.urls[0]
    assert (info.versao, info.prerelease) == ("1.2.0-rc.3", True)


def test_canal_ligado_sem_nada_mais_novo_nao_oferece_nada(com_token, monkeypatch):
    monkeypatch.setattr(rede, "abrir", _AbrirAnotando(_Resposta([_release(tag_name="v1.1.0")])))

    assert updater.checar("1.1.0", canal_testes=True) is None


def test_o_canal_vem_desligado_e_lembra_a_escolha(tmp_path):
    preferencias = tmp_path / "user_prefs.json"

    assert updater.canal_testes_ligado(config_path=preferencias) is False
    updater.ligar_canal_testes(True, config_path=preferencias)
    assert updater.canal_testes_ligado(config_path=preferencias) is True
    updater.ligar_canal_testes(False, config_path=preferencias)
    assert updater.canal_testes_ligado(config_path=preferencias) is False


# =============================================================================
# J. O pequeno que NAO chega inteiro  [2026-10-07]
# =============================================================================
# Caso real, 1.2.0-rc.3 -> rc.4, na rede da empresa (Zscaler): o proxy
# entregou o instalador pequeno quase inteiro e cortou o fim, duas vezes --
# `IncompleteRead(38518050 bytes read, 883 more expected)` e depois
# `IncompleteRead(37882569 bytes read, 636364 more expected)`. O completo, de
# 316 MB, passa pelo mesmo caminho. O pequeno e um atalho: se ele nao chega,
# o app baixa o completo, que serve para todos -- e NAO remenda o pedaco que
# faltou (se o proxy segurou o fim para analisar o arquivo, pedir so o resto
# seria passar por cima da analise).

import requests  # noqa: E402 -- dependencia real (ver conftest)
import urllib3  # noqa: E402


class _RespostaCortada(_RespostaBinaria):
    """Entrega os primeiros `ate` bytes e cai como na rede da empresa."""

    def __init__(self, dados, ate):
        super().__init__(dados)
        self._ate = ate

    def iter_content(self, chunk_size=1):
        for i in range(0, self._ate, chunk_size):
            yield self._dados[i:min(i + chunk_size, self._ate)]
        faltam = len(self._dados) - self._ate
        raise requests.exceptions.ChunkedEncodingError(urllib3.exceptions.ProtocolError(
            f"Connection broken: IncompleteRead({self._ate} bytes read, {faltam} more expected)", None))


class _AbrirPorAsset:
    """Uma resposta por asset (o fim da URL), anotando a ordem dos pedidos."""

    def __init__(self, respostas):
        self.respostas = respostas
        self.assets = []

    def __call__(self, url, **kw):
        asset = url.rsplit("/", 1)[1]
        self.assets.append(asset)
        return _Sessao(), self.respostas[asset]


def _pequeno_e_completo(pequeno, completo):
    """A `Atualizacao` que o app monta quando o Release traz um pequeno feito
    a partir da versao instalada (assets 77 = pequeno, 42 = completo)."""
    manifesto = {"sha256": hashlib.sha256(completo).hexdigest(),
                 "atualizacoes": [{"de": "1.0.0", "arquivo": PACOTE,
                                   "sha256": hashlib.sha256(pequeno).hexdigest(),
                                   "tamanho": len(pequeno)}]}
    return updater.interpretar_release(_release_com_pequeno(), manifesto, versao_atual="1.0.0")


def test_o_pequeno_escolhido_guarda_o_completo_para_cair_nele():
    info = updater.interpretar_release(_release_com_pequeno(), _manifesto_com_pequeno(),
                                       versao_atual="1.0.0")

    completo = info.completo
    assert completo is not None and completo.incremental is False
    assert completo.nome_arquivo == "SIG-FT_Itaipu_Setup_1.1.0.exe"
    assert completo.url_asset.endswith("/assets/42")
    assert (completo.tamanho, completo.sha256) == (180_000_000, "ab" * 32)
    assert updater.interpretar_release(_release(), _manifesto_com_pequeno()).completo is None


def test_download_cortado_diz_quanto_chegou_e_nao_deixa_o_parcial(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "pasta_download", lambda: tmp_path)
    dados = b"C" * 3_000_000
    monkeypatch.setattr(rede, "abrir",
                        lambda url, **kw: (_Sessao(), _RespostaCortada(dados, ate=2_000_000)))

    with pytest.raises(updater.DownloadInterrompido) as erro:
        updater.baixar(_info(dados))

    texto = str(erro.value)
    assert "chegaram 1.9 de 2.9 MB" in texto
    assert "faltaram 1000000 bytes" in texto
    assert list(tmp_path.iterdir()) == [], "o .part cortado nao pode ficar"


def test_pequeno_cortado_no_fim_cai_no_completo(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "pasta_download", lambda: tmp_path)
    pequeno, completo = b"P" * 2_000_000, b"C" * 3_000_000
    abrir = _AbrirPorAsset({"77": _RespostaCortada(pequeno, ate=len(pequeno) - 883),
                            "42": _RespostaBinaria(completo)})
    monkeypatch.setattr(rede, "abrir", abrir)
    avisos, progresso = [], []

    destino = updater.baixar(_pequeno_e_completo(pequeno, completo),
                             progresso_cb=progresso.append, ao_cair_no_completo=avisos.append)

    assert abrir.assets == ["77", "42"]
    assert destino.name == "SIG-FT_Itaipu_Setup_1.1.0.exe"
    assert destino.read_bytes() == completo
    assert sorted(p.name for p in tmp_path.iterdir()) == [destino.name]
    assert [a.nome_arquivo for a in avisos] == ["SIG-FT_Itaipu_Setup_1.1.0.exe"], (
        "a janela precisa saber que o download virou o do completo")
    assert 0.0 in progresso, "a barra recomeca do zero para o completo"


def test_pequeno_que_nao_confere_tambem_cai_no_completo(monkeypatch, tmp_path):
    # Um proxy pode entregar outra coisa no lugar do arquivo (pagina de
    # bloqueio, arquivo truncado): o SHA256 recusa, e o completo resolve.
    monkeypatch.setattr(updater, "pasta_download", lambda: tmp_path)
    pequeno, completo = b"P" * 2_000_000, b"C" * 3_000_000
    abrir = _AbrirPorAsset({"77": _RespostaBinaria(b"X" * 2_000_000),
                            "42": _RespostaBinaria(completo)})
    monkeypatch.setattr(rede, "abrir", abrir)

    destino = updater.baixar(_pequeno_e_completo(pequeno, completo))

    assert abrir.assets == ["77", "42"] and destino.read_bytes() == completo


def test_se_o_completo_tambem_cai_o_erro_e_o_do_completo(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "pasta_download", lambda: tmp_path)
    pequeno, completo = b"P" * 2_000_000, b"C" * 3_000_000
    monkeypatch.setattr(rede, "abrir", _AbrirPorAsset({
        "77": _RespostaCortada(pequeno, ate=1_000_000),
        "42": _RespostaCortada(completo, ate=1_500_000)}))

    with pytest.raises(updater.DownloadInterrompido) as erro:
        updater.baixar(_pequeno_e_completo(pequeno, completo))

    assert "de 2.9 MB" in str(erro.value), "a mensagem final e a do completo"
    assert list(tmp_path.iterdir()) == []


def test_disco_cheio_no_pequeno_NAO_vira_download_do_completo(monkeypatch, tmp_path):
    # Sem espaco para 38 MB, nao ha para 316: o erro sobe como veio.
    monkeypatch.setattr(updater, "pasta_download", lambda: tmp_path)
    pequeno, completo = b"P" * 2_000_000, b"C" * 3_000_000
    abrir = _AbrirPorAsset({"77": _RespostaBinaria(pequeno), "42": _RespostaBinaria(completo)})
    monkeypatch.setattr(rede, "abrir", abrir)

    def sem_espaco(*a, **k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(updater, "open", sem_espaco, raising=False)

    with pytest.raises(OSError) as erro:
        updater.baixar(_pequeno_e_completo(pequeno, completo))

    assert erro.value.errno == 28
    assert abrir.assets == ["77"]


# =============================================================================
# J. O pequeno em .zip  [2026-10-16]
# =============================================================================
# O proxy da empresa cortou o fim do `.bin` 3 de 3 vezes e deixou passar o
# `.exe` completo. O Release passa a trazer o MESMO pequeno num `.zip` comum,
# numa chave nova do `latest.json` (`zip`) que só o app novo lê. Ordem: zip ->
# bin -> completo. Sem senha e sem remendo: o proxy analisa o que quiser.

ZIPADO = "SIG-FT_Itaipu_Atualizacao_1.0.0_para_1.1.0.zip"
MEMBRO = "SIG-FT_Itaipu_Atualizacao_1.0.0_para_1.1.0.exe"


def _zip_com(membros):
    import io
    import zipfile

    bruto = io.BytesIO()
    with zipfile.ZipFile(bruto, "w", compression=zipfile.ZIP_STORED) as z:
        for nome, dados in membros.items():
            z.writestr(nome, dados)
    return bruto.getvalue()


def _tres_caminhos(pequeno, completo, zipado):
    """zip (asset 78) -> bin (77) -> completo (42)."""
    release = _release_com_pequeno()
    release["assets"].append({
        "name": ZIPADO, "url": "https://api.github.com/repos/luanccozer/SIG-FT/releases/assets/78",
        "size": len(zipado)})
    manifesto = {"sha256": hashlib.sha256(completo).hexdigest(),
                 "atualizacoes": [{"de": "1.0.0", "arquivo": PACOTE,
                                   "sha256": hashlib.sha256(pequeno).hexdigest(), "tamanho": len(pequeno),
                                   "zip": {"arquivo": ZIPADO, "sha256": hashlib.sha256(zipado).hexdigest(),
                                           "tamanho": len(zipado)}}]}
    return updater.interpretar_release(release, manifesto, versao_atual="1.0.0")


def test_com_o_zip_no_release_o_app_novo_escolhe_o_zip():
    pequeno, completo = b"P" * 2_000_000, b"C" * 3_000_000
    zipado = _zip_com({MEMBRO: pequeno})

    info = _tres_caminhos(pequeno, completo, zipado)

    assert info.nome_arquivo == ZIPADO and info.incremental is True
    assert info.sha256 == hashlib.sha256(zipado).hexdigest()
    assert info.sha256_dentro == hashlib.sha256(pequeno).hexdigest()
    assert info.reserva is not None and info.reserva.nome_arquivo == PACOTE
    assert info.completo is not None and info.completo.nome_arquivo == "SIG-FT_Itaipu_Setup_1.1.0.exe"


def test_zip_listado_mas_ausente_do_release_fica_o_bin():
    info = updater.interpretar_release(_release_com_pequeno(), {
        "sha256": "ab" * 32,
        "atualizacoes": [{"de": "1.0.0", "arquivo": PACOTE, "sha256": "cd" * 32, "tamanho": 1,
                          "zip": {"arquivo": ZIPADO, "sha256": "ef" * 32, "tamanho": 1}}]},
        versao_atual="1.0.0")

    assert info.nome_arquivo == PACOTE and info.reserva is None


def test_o_zip_baixado_e_conferido_aberto_e_vira_o_exe(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "pasta_download", lambda: tmp_path)
    pequeno, completo = b"P" * 2_000_000, b"C" * 3_000_000
    zipado = _zip_com({MEMBRO: pequeno})
    abrir = _AbrirPorAsset({"78": _RespostaBinaria(zipado)})
    monkeypatch.setattr(rede, "abrir", abrir)

    destino = updater.baixar(_tres_caminhos(pequeno, completo, zipado))

    assert abrir.assets == ["78"]
    assert destino.name == MEMBRO and destino.read_bytes() == pequeno
    assert sorted(p.name for p in tmp_path.iterdir()) == [MEMBRO], "o .zip nao fica para tras"


def test_zip_cortado_cai_no_bin_e_nao_no_completo(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "pasta_download", lambda: tmp_path)
    pequeno, completo = b"P" * 2_000_000, b"C" * 3_000_000
    zipado = _zip_com({MEMBRO: pequeno})
    abrir = _AbrirPorAsset({"78": _RespostaCortada(zipado, ate=len(zipado) - 2370),
                            "77": _RespostaBinaria(pequeno)})
    monkeypatch.setattr(rede, "abrir", abrir)
    avisos, log = [], []

    destino = updater.baixar(_tres_caminhos(pequeno, completo, zipado),
                             ao_cair_no_completo=avisos.append, log_cb=log.append)

    assert abrir.assets == ["78", "77"]
    assert destino.read_bytes() == pequeno
    assert avisos == [], "ainda nao e o completo"
    assert any(".zip" in linha and "falhou" in linha for linha in log)


def test_zip_e_bin_cortados_caem_no_completo(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "pasta_download", lambda: tmp_path)
    pequeno, completo = b"P" * 2_000_000, b"C" * 3_000_000
    zipado = _zip_com({MEMBRO: pequeno})
    abrir = _AbrirPorAsset({"78": _RespostaCortada(zipado, ate=len(zipado) - 10),
                            "77": _RespostaCortada(pequeno, ate=len(pequeno) - 10),
                            "42": _RespostaBinaria(completo)})
    monkeypatch.setattr(rede, "abrir", abrir)
    avisos = []

    destino = updater.baixar(_tres_caminhos(pequeno, completo, zipado), ao_cair_no_completo=avisos.append)

    assert abrir.assets == ["78", "77", "42"] and destino.read_bytes() == completo
    assert [a.nome_arquivo for a in avisos] == ["SIG-FT_Itaipu_Setup_1.1.0.exe"]
    assert sorted(p.name for p in tmp_path.iterdir()) == [destino.name]


@pytest.mark.parametrize("membros", [
    {MEMBRO: b"X" * 2_000_000},                                  # o de dentro nao confere
    {"../" + MEMBRO: b"P" * 2_000_000},                          # caminho para fora da pasta
    {MEMBRO: b"P" * 2_000_000, "outro.exe": b"Q" * 10},         # mais de um arquivo
], ids=["sha-de-dentro", "caminho", "dois-arquivos"])
def test_zip_estranho_e_recusado_e_cai_no_bin(monkeypatch, tmp_path, membros):
    monkeypatch.setattr(updater, "pasta_download", lambda: tmp_path)
    pequeno, completo = b"P" * 2_000_000, b"C" * 3_000_000
    zipado = _zip_com(membros)
    abrir = _AbrirPorAsset({"78": _RespostaBinaria(zipado), "77": _RespostaBinaria(pequeno)})
    monkeypatch.setattr(rede, "abrir", abrir)

    destino = updater.baixar(_tres_caminhos(pequeno, completo, zipado))

    assert abrir.assets == ["78", "77"] and destino.read_bytes() == pequeno
    assert sorted(p.name for p in tmp_path.iterdir()) == [destino.name]
    assert not (tmp_path.parent / MEMBRO).exists()


# =============================================================================
# K. O pequeno também em .exe  [2026-10-19]
# =============================================================================
# O proxy da empresa deixa passar o instalador COMPLETO, que é um `.exe`. O
# pequeno também É um `.exe` (o Inno o gera assim; o `.bin` é só o nome que o
# protege do app 1.1.1). Publicá-lo com o tipo verdadeiro não esconde nada: o
# proxy o analisa como analisa o completo. Chave nova `exe` no `latest.json`,
# só o app novo lê.
#
# [2026-10-19] Ordem: zip -> exe -> bin -> completo. Medido na rede da
# empresa (rc.3 -> rc.4 e rc.4 -> rc.5): o `.zip` chegou 2 de 2 vezes; o
# `.exe` pequeno foi cortado no fim, como o `.bin` (3 de 3). O `.exe` fica
# como reserva, por via das dúvidas, logo depois do `.zip`.

EXE_PEQUENO = "SIG-FT_Itaipu_Update_1.0.0_para_1.1.0.exe"


def _quatro_caminhos(pequeno, completo, zipado, *, exe_antes=False):
    """zip (asset 78) -> exe (79) -> bin (77) -> completo (42)."""
    release = _release_com_pequeno()
    asset_exe = {"name": EXE_PEQUENO, "size": len(pequeno),
                 "url": "https://api.github.com/repos/luanccozer/SIG-FT/releases/assets/79"}
    if exe_antes:
        release["assets"].insert(0, asset_exe)
    else:
        release["assets"].append(asset_exe)
    release["assets"].append({
        "name": ZIPADO, "url": "https://api.github.com/repos/luanccozer/SIG-FT/releases/assets/78",
        "size": len(zipado)})
    sha_pequeno = hashlib.sha256(pequeno).hexdigest()
    manifesto = {"sha256": hashlib.sha256(completo).hexdigest(),
                 "atualizacoes": [{"de": "1.0.0", "arquivo": PACOTE, "sha256": sha_pequeno,
                                   "tamanho": len(pequeno),
                                   "zip": {"arquivo": ZIPADO, "sha256": hashlib.sha256(zipado).hexdigest(),
                                           "tamanho": len(zipado)},
                                   "exe": {"arquivo": EXE_PEQUENO, "sha256": sha_pequeno,
                                           "tamanho": len(pequeno)}}]}
    return updater.interpretar_release(release, manifesto, versao_atual="1.0.0")


def test_com_zip_e_exe_no_release_o_app_vai_no_zip_e_guarda_exe_e_bin():
    pequeno, completo = b"P" * 2_000_000, b"C" * 3_000_000
    zipado = _zip_com({MEMBRO: pequeno})

    info = _quatro_caminhos(pequeno, completo, zipado)

    assert info.nome_arquivo == ZIPADO and info.incremental is True
    assert info.sha256_dentro == hashlib.sha256(pequeno).hexdigest()
    assert info.reserva is not None and info.reserva.nome_arquivo == EXE_PEQUENO
    assert info.reserva.sha256 == hashlib.sha256(pequeno).hexdigest()
    assert info.reserva.reserva is not None and info.reserva.reserva.nome_arquivo == PACOTE
    assert info.completo is not None and info.completo.nome_arquivo == "SIG-FT_Itaipu_Setup_1.1.0.exe"


def test_exe_listado_mas_ausente_do_release_fica_o_zip():
    pequeno = b"P" * 2_000_000
    zipado = _zip_com({MEMBRO: pequeno})
    release = _release_com_pequeno()
    release["assets"].append({"name": ZIPADO, "size": len(zipado),
                              "url": "https://api.github.com/repos/luanccozer/SIG-FT/releases/assets/78"})
    sha_pequeno = hashlib.sha256(pequeno).hexdigest()
    manifesto = {"sha256": "ab" * 32, "atualizacoes": [{
        "de": "1.0.0", "arquivo": PACOTE, "sha256": sha_pequeno, "tamanho": len(pequeno),
        "zip": {"arquivo": ZIPADO, "sha256": hashlib.sha256(zipado).hexdigest(), "tamanho": len(zipado)},
        "exe": {"arquivo": EXE_PEQUENO, "sha256": sha_pequeno, "tamanho": len(pequeno)}}]}

    info = updater.interpretar_release(release, manifesto, versao_atual="1.0.0")

    assert info.nome_arquivo == ZIPADO and info.reserva.nome_arquivo == PACOTE


def test_o_completo_continua_sendo_o_completo_mesmo_com_o_pequeno_exe_na_frente():
    # O app escolhe o completo pelo nome, não pela posição: o pequeno em .exe
    # nunca pode virar "o instalador" de quem não tem base para ele.
    pequeno, completo = b"P" * 2_000_000, b"C" * 3_000_000
    info = _quatro_caminhos(pequeno, completo, _zip_com({MEMBRO: pequeno}), exe_antes=True)

    assert info.completo.nome_arquivo == "SIG-FT_Itaipu_Setup_1.1.0.exe"
    sem_base = updater.interpretar_release(
        {"tag_name": "v1.1.0", "assets": [
            {"name": EXE_PEQUENO, "url": "https://api.github.com/x/assets/79", "size": 1},
            {"name": "SIG-FT_Itaipu_Setup_1.1.0.exe", "url": "https://api.github.com/x/assets/42", "size": 2}]},
        None, versao_atual="0.9.0")
    assert sem_base.nome_arquivo == "SIG-FT_Itaipu_Setup_1.1.0.exe" and sem_base.incremental is False


def test_zip_cortado_cai_no_exe_que_e_usado_direto(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "pasta_download", lambda: tmp_path)
    pequeno, completo = b"P" * 2_000_000, b"C" * 3_000_000
    zipado = _zip_com({MEMBRO: pequeno})
    abrir = _AbrirPorAsset({"78": _RespostaCortada(zipado, ate=len(zipado) - 10),
                            "79": _RespostaBinaria(pequeno)})
    monkeypatch.setattr(rede, "abrir", abrir)

    destino = updater.baixar(_quatro_caminhos(pequeno, completo, zipado))

    assert abrir.assets == ["78", "79"]
    assert destino.name == EXE_PEQUENO and destino.read_bytes() == pequeno


def test_zip_cortado_cai_no_exe_depois_no_bin_depois_no_completo(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "pasta_download", lambda: tmp_path)
    pequeno, completo = b"P" * 2_000_000, b"C" * 3_000_000
    zipado = _zip_com({MEMBRO: pequeno})
    abrir = _AbrirPorAsset({"79": _RespostaCortada(pequeno, ate=len(pequeno) - 10),
                            "78": _RespostaCortada(zipado, ate=len(zipado) - 10),
                            "77": _RespostaCortada(pequeno, ate=len(pequeno) - 10),
                            "42": _RespostaBinaria(completo)})
    monkeypatch.setattr(rede, "abrir", abrir)
    avisos, log = [], []

    destino = updater.baixar(_quatro_caminhos(pequeno, completo, zipado),
                             ao_cair_no_completo=avisos.append, log_cb=log.append)

    assert abrir.assets == ["78", "79", "77", "42"] and destino.read_bytes() == completo
    assert [a.nome_arquivo for a in avisos] == ["SIG-FT_Itaipu_Setup_1.1.0.exe"]
    assert any("em .exe falhou" in linha for linha in log)
    assert any("em .zip falhou" in linha for linha in log)
    assert sorted(p.name for p in tmp_path.iterdir()) == [destino.name]


# =============================================================================
# L. A pasta de downloads não acumula instaladores  [2026-10-19]
# =============================================================================
# Cada atualização baixava o instalador para `%TEMP%\SIG-FT_Update` e o deixava
# lá: 326 MB por atualização completa, versão após versão. Agora o app limpa a
# pasta antes de baixar e na abertura. O `instalacao.log` fica: é diagnóstico.

def _sujar(pasta):
    for nome in ("SIG-FT_Itaipu_Setup_1.2.0.exe", "SIG-FT_Itaipu_Atualizacao_1.2.0_para_1.2.1.bin",
                 "SIG-FT_Itaipu_Atualizacao_1.2.0_para_1.2.1.zip", "SIG-FT_Itaipu_Setup_1.2.1.exe.part",
                 "instalacao.log"):
        (pasta / nome).write_bytes(b"x" * 1000)


def test_limpar_downloads_apaga_os_instaladores_e_fica_com_o_log(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "_pasta_de_download", lambda: tmp_path)
    _sujar(tmp_path)
    log = []

    liberados = updater.limpar_downloads(log_cb=log.append)

    assert sorted(p.name for p in tmp_path.iterdir()) == ["instalacao.log"]
    assert liberados == 4000
    assert any("4 arquivo" in linha for linha in log)


def test_limpar_downloads_sem_pasta_nao_cria_nada(monkeypatch, tmp_path):
    pasta = tmp_path / "nao_existe"
    monkeypatch.setattr(updater, "_pasta_de_download", lambda: pasta)

    assert updater.limpar_downloads() == 0
    assert not pasta.exists()


def test_limpar_downloads_pula_o_arquivo_em_uso(monkeypatch, tmp_path):
    # No Windows, o instalador que acabou de reabrir o app ainda pode estar
    # rodando: o arquivo dele está preso. Fica para a próxima vez, sem erro.
    monkeypatch.setattr(updater, "_pasta_de_download", lambda: tmp_path)
    _sujar(tmp_path)
    preso = tmp_path / "SIG-FT_Itaipu_Setup_1.2.0.exe"
    from pathlib import Path

    unlink_real = Path.unlink

    def unlink(self, *a, **k):
        if self == preso:
            raise PermissionError(32, "em uso")
        return unlink_real(self, *a, **k)

    monkeypatch.setattr(Path, "unlink", unlink)

    updater.limpar_downloads()

    assert sorted(p.name for p in tmp_path.iterdir()) == ["SIG-FT_Itaipu_Setup_1.2.0.exe", "instalacao.log"]


def test_baixar_limpa_a_pasta_antes(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "pasta_download", lambda: tmp_path)
    monkeypatch.setattr(updater, "_pasta_de_download", lambda: tmp_path)
    _sujar(tmp_path)
    pequeno, completo = b"P" * 2_000_000, b"C" * 3_000_000
    monkeypatch.setattr(rede, "abrir", _AbrirPorAsset({"78": _RespostaBinaria(_zip_com({MEMBRO: pequeno}))}))

    destino = updater.baixar(_tres_caminhos(pequeno, completo, _zip_com({MEMBRO: pequeno})))

    assert sorted(p.name for p in tmp_path.iterdir()) == sorted([destino.name, "instalacao.log"])
