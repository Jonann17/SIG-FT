# -*- coding: utf-8 -*-
"""A rede da empresa: PAC, proxy e a cascata de rotas.

O caso real que motivou este modulo (maquina da CMI, registro do Windows):

    ProxyEnable     REG_DWORD  0x0
    AutoConfigURL   REG_SZ     http://127.0.0.1:9999/4049_gpproxy.pac

Nao ha proxy estatico -- so um arquivo PAC, servido pelo proprio agente do
GlobalProtect. E o `urllib.request.getproxies()` do Python le SOMENTE
`ProxyEnable`/`ProxyServer`: com `ProxyEnable=0` ele conclui "sem proxy", o app
sai direto, e a VPN descarta os pacotes em silencio. O navegador funciona
porque navegador executa PAC.

O QUE ESTES TESTES PROVAM e o que NAO provam
--------------------------------------------
Provam: a analise do formato do PAC, a ORDEM da cascata, o desembrulho da
cadeia de excecoes, e que fora do Windows nada estoura.

NAO provam -- e nenhum teste em Linux pode: que o `winhttp.dll` responda o
proxy certo com a VPN ligada. Isso so a maquina do usuario diz. Ver
`docs/BUILD.md`.
"""
import os

import pytest

from sigft.core import rede


# =============================================================================
# A. `normalizar_proxies` -- o formato do PAC
# =============================================================================
#
# Um PAC responde `PROXY host:porta; DIRECT`. Sem tirar o verbo, o app tenta
# conectar num host chamado "PROXY". E um erro que ja foi cometido.

@pytest.mark.parametrize("bruto, esperado", [
    # o formato classico do PAC
    ("PROXY 10.0.0.1:8080; DIRECT", ["10.0.0.1:8080"]),
    # o WinHTTP costuma devolver ja sem o verbo
    ("10.0.0.1:8080", ["10.0.0.1:8080"]),
    # varios proxies, na ordem de preferencia do PAC
    ("PROXY a:8080; PROXY b:8080; DIRECT", ["a:8080", "b:8080"]),
    # separador por virgula tambem existe
    ("a:8080,b:8080", ["a:8080", "b:8080"]),
    # SOCKS e um verbo valido de PAC
    ("SOCKS 10.0.0.1:1080", ["10.0.0.1:1080"]),
    # verbo em minuscula
    ("proxy 10.0.0.1:8080", ["10.0.0.1:8080"]),
    # repetido nao vira duas rotas
    ("PROXY a:1; PROXY a:1", ["a:1"]),
    # espaco sobrando
    ("  PROXY   a:1  ;  DIRECT  ", ["a:1"]),
])
def test_formatos_de_resposta_do_pac(bruto, esperado):
    assert rede.normalizar_proxies(bruto) == esperado


@pytest.mark.parametrize("bruto", ["DIRECT", "direct", "", "   ", None, ";;;"])
def test_respostas_que_significam_conexao_direta(bruto):
    """`DIRECT` e ausencia sao a mesma coisa: nenhum proxy a acrescentar."""
    assert rede.normalizar_proxies(bruto) == []


def test_a_palavra_PROXY_sozinha_nunca_vira_endereco():
    """O erro exato que o usuario relatou ter cometido.

    Um verbo sem endereco depois nao e um host. Deixar passar faria o app
    tentar resolver o nome "PROXY" -- e o sintoma seria um erro de DNS
    aparentemente absurdo no meio de uma rede que funciona.
    """
    assert "PROXY" not in rede.normalizar_proxies("PROXY")
    assert "DIRECT" not in rede.normalizar_proxies("PROXY host:80; DIRECT")


# =============================================================================
# B. `estrategias` -- a ORDEM da cascata
# =============================================================================

def _nomes(rotas):
    return [nome for nome, _proxies, _trust in rotas]


def test_proxy_informado_pelo_usuario_curto_circuita_tudo():
    """Escolha explicita da pessoa ganha de qualquer descoberta."""
    rotas = rede.estrategias(proxy="http://meu:8080", url="https://x.com")

    assert len(rotas) == 1
    assert rotas[0][1] == {"http": "http://meu:8080", "https": "http://meu:8080"}


def test_a_conexao_direta_e_SEMPRE_a_ultima(monkeypatch):
    """E a que funciona fora da VPN -- tem de existir, e por ultimo.

    Se viesse antes, numa rede com PAC ela seria tentada primeiro, levaria o
    timeout inteiro da VPN descartando pacotes, e so entao o app tentaria o
    proxy certo. O usuario veria o programa "travado" por 20 segundos a cada
    chamada.
    """
    monkeypatch.setattr(rede, "proxies_do_windows_para", lambda *a, **k: ["p:8080"])
    monkeypatch.setenv("HTTPS_PROXY", "http://env:3128")

    rotas = rede.estrategias(url="https://x.com")

    assert rotas[-1][0] == "conexao direta"
    assert rotas[-1][1] == {}


def test_o_proxy_do_PAC_vem_antes_dos_outros(monkeypatch):
    """E o unico que sabe a resposta certa POR DESTINO."""
    monkeypatch.setattr(rede, "proxies_do_windows_para", lambda *a, **k: ["pac:8080"])

    rotas = rede.estrategias(url="https://x.com")

    assert "pac:8080" in rotas[0][0]


def test_sem_PAC_a_cascata_antiga_fica_intacta(monkeypatch):
    """A via nova so ACRESCENTA. Onde nao ha PAC, nada muda.

    Importa porque o SIG-FT ja funciona fora da VPN hoje: uma mudanca que
    'conserta' a rede da empresa e quebra a de casa nao e conserto.
    """
    monkeypatch.setattr(rede, "proxies_do_windows_para", lambda *a, **k: [])
    for v in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(rede.urllib.request, "getproxies", lambda: {})

    assert _nomes(rede.estrategias(url="https://x.com")) == ["conexao direta"]


def test_endereco_repetido_nao_vira_duas_rotas(monkeypatch):
    """Tentar o mesmo proxy duas vezes so dobra o tempo ate a falha."""
    monkeypatch.setattr(rede, "proxies_do_windows_para",
                        lambda *a, **k: ["p:8080", "p:8080", "q:8080"])

    rotas = rede.estrategias(url="https://x.com")
    do_pac = [n for n in _nomes(rotas) if "Windows" in n]

    assert len(do_pac) == 2


def test_a_rota_de_variaveis_de_ambiente_so_aparece_quando_ha_variavel(monkeypatch):
    monkeypatch.setattr(rede, "proxies_do_windows_para", lambda *a, **k: [])
    monkeypatch.setattr(rede.urllib.request, "getproxies", lambda: {})
    for v in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        monkeypatch.delenv(v, raising=False)

    assert not any("ambiente" in n for n in _nomes(rede.estrategias(url="https://x.com")))

    monkeypatch.setenv("HTTPS_PROXY", "http://env:3128")

    assert any("ambiente" in n for n in _nomes(rede.estrategias(url="https://x.com")))


def test_sem_url_nao_consulta_o_PAC(monkeypatch):
    """Consultar o PAC exige o destino: a resposta MUDA por destino."""
    chamou = []
    monkeypatch.setattr(rede, "proxies_do_windows_para",
                        lambda *a, **k: chamou.append(1) or [])

    rede.estrategias(url="")

    assert not chamou


# =============================================================================
# C. `resumo_erro` -- a causa raiz, nao o embrulho
# =============================================================================
#
# O `requests` embrulha o `urllib3`, que embrulha o socket. O texto de fora
# ("Max retries exceeded") e IDENTICO para timeout, DNS e conexao recusada --
# que sao diagnosticos opostos.

def test_desembrulha_o_atributo_reason():
    class ErroDeRetentativa(Exception):
        def __init__(self, motivo):
            super().__init__("Max retries exceeded")
            self.reason = motivo

    erro = Exception(ErroDeRetentativa(TimeoutError("tempo esgotado")))

    assert "TimeoutError" in rede.resumo_erro(erro)
    assert "tempo esgotado" in rede.resumo_erro(erro)


def test_desembrulha_a_cadeia_de_causas():
    try:
        try:
            raise OSError("o nome nao resolve")
        except OSError as raiz:
            raise RuntimeError("sem conexao") from raiz
    except RuntimeError as e:
        resumo = rede.resumo_erro(e)

    assert "OSError" in resumo
    assert "o nome nao resolve" in resumo


def test_timeout_e_conexao_recusada_dao_resumos_DIFERENTES():
    """E a razao de ser da funcao: um e firewall, o outro e servico parado."""
    class Embrulho(Exception):
        def __init__(self, motivo):
            super().__init__("Max retries exceeded")
            self.reason = motivo

    tempo = rede.resumo_erro(Exception(Embrulho(TimeoutError("timed out"))))
    recusada = rede.resumo_erro(Exception(Embrulho(ConnectionRefusedError("recusada"))))

    assert tempo != recusada


def test_mensagem_gigante_e_cortada_com_reticencia():
    resumo = rede.resumo_erro(ValueError("x" * 500), limite=60)

    assert len(resumo) <= 60
    assert resumo.endswith("…")


def test_cadeia_circular_nao_prende_o_programa():
    """Cadeias circulares existem, e um `while` ingenuo trava o app."""
    a = ValueError("a")
    b = ValueError("b")
    a.__cause__ = b
    b.__cause__ = a

    assert rede.resumo_erro(a)  # termina, e isso ja e o teste


# =============================================================================
# D. Fora do Windows -- nada pode estourar
# =============================================================================

@pytest.mark.skipif(os.name == "nt", reason="este e o comportamento fora do Windows")
def test_consulta_de_proxy_fora_do_windows_devolve_lista_vazia():
    assert rede.proxies_do_windows_para("https://x.com") == []


@pytest.mark.skipif(os.name == "nt", reason="este e o comportamento fora do Windows")
def test_diagnostico_fora_do_windows_nao_estoura():
    linhas = rede.diagnostico("localhost")

    assert isinstance(linhas, list)
    assert all(isinstance(x, str) for x in linhas)


def test_injetar_certificados_sem_truststore_nao_derruba(monkeypatch):
    """Sem o pacote, a cascata ainda pode salvar -- entao so avisa."""
    import builtins

    real = builtins.__import__

    def sem_truststore(nome, *a, **k):
        if nome == "truststore":
            raise ImportError("nao instalado")
        return real(nome, *a, **k)

    monkeypatch.setattr(builtins, "__import__", sem_truststore)
    avisos = []

    assert rede.injetar_certificados_windows(avisos.append) is False
    assert avisos, "a ausencia do truststore tem de aparecer no log"


def test_o_cache_de_proxy_pode_ser_esquecido():
    """Ligar/desligar a VPN muda a resposta do PAC."""
    rede.esquecer_proxy_descoberto()  # nao deve estourar

    assert rede._cache_proxy == {}


# =============================================================================
# E. `abrir` -- a cascata em acao
# =============================================================================


class _RespostaFalsa:
    def __init__(self, status=200, texto="ok"):
        self.status_code = status
        self.text = texto

    def close(self):
        pass


class _SessaoFalsa:
    """Dublê de `requests.Session` que registra como foi configurada."""

    def __init__(self, roteiro, registro):
        self._roteiro = roteiro
        self._registro = registro
        self.trust_env = True
        self.proxies = {}
        self.verify = True

    def request(self, metodo, url, **kwargs):
        self._registro.append({
            "metodo": metodo, "proxies": dict(self.proxies),
            "trust_env": self.trust_env, "verify": self.verify,
            "json": kwargs.get("json"), "data": kwargs.get("data"),
        })
        resultado = self._roteiro.pop(0)
        if isinstance(resultado, Exception):
            raise resultado
        return resultado

    def close(self):
        pass


def _fabrica(roteiro, registro):
    return lambda: _SessaoFalsa(roteiro, registro)


@pytest.fixture
def so_direta(monkeypatch):
    """Ambiente sem proxy nenhum: a cascata tem uma rota so."""
    monkeypatch.setattr(rede, "proxies_do_windows_para", lambda *a, **k: [])
    monkeypatch.setattr(rede.urllib.request, "getproxies", lambda: {})
    monkeypatch.setattr(rede, "injetar_certificados_windows", lambda *a, **k: True)
    for v in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        monkeypatch.delenv(v, raising=False)


def test_abrir_devolve_a_resposta_da_primeira_rota_que_funciona(so_direta):
    registro = []
    resposta = _RespostaFalsa()

    _sessao, obtida = rede.abrir("https://x.com", _fabrica_sessao=_fabrica(
        [resposta], registro))

    assert obtida is resposta
    assert len(registro) == 1


def test_abrir_tenta_a_rota_seguinte_quando_a_primeira_nao_conecta(monkeypatch):
    import requests

    monkeypatch.setattr(rede, "proxies_do_windows_para", lambda *a, **k: ["pac:8080"])
    monkeypatch.setattr(rede.urllib.request, "getproxies", lambda: {})
    monkeypatch.setattr(rede, "injetar_certificados_windows", lambda *a, **k: True)
    registro = []
    boa = _RespostaFalsa()

    _s, obtida = rede.abrir("https://x.com", _fabrica_sessao=_fabrica(
        [requests.exceptions.ConnectionError("proxy morto"), boa], registro))

    assert obtida is boa
    assert registro[0]["proxies"]["https"] == "http://pac:8080"
    assert registro[1]["proxies"] == {}, "a segunda tem de ser a conexao direta"


def test_quando_nenhuma_rota_funciona_levanta_FalhaDeRede(so_direta):
    import requests

    with pytest.raises(rede.FalhaDeRede) as erro:
        rede.abrir("https://x.com", _fabrica_sessao=_fabrica(
            [requests.exceptions.ConnectionError("sem rede")], []))

    assert "conexao direta" in str(erro.value)


def test_status_inesperado_NAO_faz_a_cascata_continuar(monkeypatch):
    """404 nao e problema de rota: trocar de proxy nao muda a resposta.

    Continuar a cascata aqui gastaria o timeout de cada rota para receber o
    mesmo 404 -- e o log culparia a rede por um erro da requisicao.
    """
    monkeypatch.setattr(rede, "proxies_do_windows_para", lambda *a, **k: ["p:1", "q:2"])
    monkeypatch.setattr(rede.urllib.request, "getproxies", lambda: {})
    monkeypatch.setattr(rede, "injetar_certificados_windows", lambda *a, **k: True)
    registro = []

    with pytest.raises(rede.FalhaDeRede) as erro:
        rede.abrir("https://x.com", _fabrica_sessao=_fabrica(
            [_RespostaFalsa(status=404, texto="nao achei")], registro))

    assert "404" in str(erro.value)
    assert len(registro) == 1, "parou na primeira rota, como deve"


def test_sem_erro_de_certificado_o_TLS_nunca_e_relaxado(so_direta):
    """Quem ja funciona nao e rebaixado.

    Uma falha de CONEXAO nao justifica desligar a verificacao de TLS. Se
    desligasse, um app com rede instavel passaria a aceitar certificado de
    qualquer um na segunda tentativa.
    """
    import requests

    registro = []
    with pytest.raises(rede.FalhaDeRede):
        rede.abrir("https://x.com", _fabrica_sessao=_fabrica(
            [requests.exceptions.ConnectionError("sem rede")], registro))

    assert all(t["verify"] is True for t in registro)


def test_so_apos_erro_de_CERTIFICADO_a_segunda_volta_sem_verificar(so_direta):
    import requests

    registro = []
    boa = _RespostaFalsa()
    avisos = []

    _s, obtida = rede.abrir(
        "https://x.com",
        log_cb=avisos.append,
        _fabrica_sessao=_fabrica([requests.exceptions.SSLError("cert ruim"), boa],
                                 registro),
    )

    assert obtida is boa
    assert registro[0]["verify"] is True
    assert registro[1]["verify"] is False
    assert any("certificado" in a.lower() for a in avisos), (
        "relaxar o TLS tem de aparecer no log, sempre"
    )


def test_abrir_faz_POST_quando_pedido(so_direta):
    """O `openai_compat` manda POST -- a cascata precisa cobrir os dois."""
    registro = []

    rede.abrir("https://x.com", metodo="POST", json={"a": 1},
               _fabrica_sessao=_fabrica([_RespostaFalsa()], registro))

    assert registro[0]["metodo"] == "POST"
    assert registro[0]["json"] == {"a": 1}


def test_abrir_repassa_data_do_formulario(so_direta):
    """O token do Aconex vai num formulario urlencoded (`data`), nao em JSON."""
    registro = []

    rede.abrir("https://x.com", metodo="POST", data={"grant_type": "client_credentials"},
               _fabrica_sessao=_fabrica([_RespostaFalsa()], registro))

    assert registro[0]["data"] == {"grant_type": "client_credentials"}


def test_o_status_esperado_pode_ser_outro(so_direta):
    """Um 302 pode ser a resposta certa, dependendo de quem se chama."""
    registro = []

    _s, resp = rede.abrir("https://x.com", status_ok=(302,),
                          _fabrica_sessao=_fabrica([_RespostaFalsa(status=302)],
                                                   registro))

    assert resp.status_code == 302


# =============================================================================
# F. `get`/`post` -- a porta que os chamadores usam
# =============================================================================
#
# Os pontos de HTTPS do SIG-FT ja tratam o status por conta propria
# (`resp.raise_for_status()` seguido de `except` com mensagem propria). Se a
# cascata julgasse o status, um 401 do OpenRouter viraria `FalhaDeRede` e a
# mensagem util ("chave invalida") sumiria. Dai o `status_ok=None`: a cascata
# decide QUAL ROTA usar; o que o status SIGNIFICA continua com quem chamou.

def test_status_ok_None_aceita_qualquer_status_que_chegou_ao_servidor(so_direta):
    registro = []

    _s, resp = rede.abrir("https://x.com", status_ok=None,
                          _fabrica_sessao=_fabrica([_RespostaFalsa(status=404)],
                                                   registro))

    assert resp.status_code == 404


def test_get_devolve_so_a_resposta(so_direta):
    resposta = _RespostaFalsa()

    assert rede.get("https://x.com",
                    _fabrica_sessao=_fabrica([resposta], [])) is resposta


def test_get_nao_julga_o_status(so_direta):
    """`raise_for_status()` continua sendo de quem chamou."""
    resp = rede.get("https://x.com",
                    _fabrica_sessao=_fabrica([_RespostaFalsa(status=401)], []))

    assert resp.status_code == 401


def test_post_manda_o_corpo_em_json(so_direta):
    registro = []

    rede.post("https://x.com", json={"modelo": "x"},
              _fabrica_sessao=_fabrica([_RespostaFalsa()], registro))

    assert registro[0]["metodo"] == "POST"
    assert registro[0]["json"] == {"modelo": "x"}


def test_falha_de_rota_continua_levantando_em_get(so_direta):
    """Sem rota nenhuma, `FalhaDeRede` -- isso o chamador precisa ver."""
    import requests

    with pytest.raises(rede.FalhaDeRede):
        rede.get("https://x.com", _fabrica_sessao=_fabrica(
            [requests.exceptions.ConnectionError("sem rede")], []))
