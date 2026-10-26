"""O diagnóstico do Aconex: prova, numa máquina com o cofre do DocManager, quais
buscas funcionam (portão G1 do plano). Cada sonda lê só a página 1 e o `TotalResults`,
como a sonda `tools/probe_download_aconex.py` do DocManager; o register inteiro é a
referência para dizer se uma sintaxe filtrou. Só conta: nenhum título nem dado de
documento sai no `detalhe`. Desenho: `docs/superpowers/specs/2026-10-26-aconex-ao-vivo-design.md`, §4.2.
"""
from __future__ import annotations

from sigft.core.aconex import diagnostico
from sigft.core.aconex.cliente import ErroAconex, Pagina
from sigft.core.aconex.credenciais import PerfilAconex

CODIGO = "#ITA0=Y01TF001&BPB020"
TITULO = "TITULO_QUE_NAO_PODE_VAZAR"
TOTAL = 12000


def _reg(codigo, tracking, titulo=TITULO):
    return {"DocumentNumber": codigo, "TrackingId": tracking, "Title": titulo}


class _Cliente:
    """Dublê do `ClienteAconex`: responde por consulta e guarda as consultas feitas."""

    def __init__(self, *, login_ok=True, respostas=None):
        self.login_ok = login_ok
        self.respostas = respostas or {}
        self.consultas = []

    def conectar(self):
        if not self.login_ok:
            raise ErroAconex("O Aconex recusou as credenciais do perfil Luan Cozer (HTTP 401).")

    def primeira_pagina(self, consulta, *, historico, campos=None, page_size=None):
        self.consultas.append(consulta)
        resposta = self.respostas.get(consulta, Pagina([], 0))
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


def _respostas_boas():
    return {
        "": Pagina([_reg("#A", "1")], TOTAL),
        f'"{CODIGO}"': Pagina([_reg(CODIGO, "777"), _reg(CODIGO, "777")], 2),
        "trackingid:777": Pagina([_reg(CODIGO, "777"), _reg("#ITA0=Y01TF009&BPB020", "777")], 3),
        'trackingid:"777"': Pagina([], 0),
        "title:SOBRESSALENTES": Pagina([_reg(CODIGO, "777")], 140),
        "docno:*PB020*": ErroAconex("A busca no Aconex falhou na página 1 após 5 tentativas (HTTP 500)."),
    }


def test_sonda_ok_e_falha_por_etapa():
    sondas = diagnostico.sondar(_Cliente(respostas=_respostas_boas()), CODIGO)
    assert [(s.nome, s.ok) for s in sondas] == [
        ("Login no Aconex", True),
        ("Register inteiro (busca vazia)", True),
        ("Busca exata do código, com histórico", True),
        ("Busca pelo Tracking ID (trackingid:<id>)", True),
        ('Busca pelo Tracking ID (trackingid:"<id>")', False),
        ("Busca por título (title:SOBRESSALENTES)", True),
        ("Busca por código (docno:*PB020*)", False),
    ]
    detalhes = {s.nome: s.detalhe for s in sondas}
    assert detalhes["Register inteiro (busca vazia)"] == "12000 documentos"
    assert detalhes["Busca exata do código, com histórico"] == "2 versões"
    assert detalhes["Busca pelo Tracking ID (trackingid:<id>)"] == "3 versões (a busca exata trouxe 2)"
    assert detalhes['Busca pelo Tracking ID (trackingid:"<id>")'] == "nenhum documento"
    assert detalhes["Busca por título (title:SOBRESSALENTES)"] == "140 de 12000 documentos"
    assert "HTTP 500" in detalhes["Busca por código (docno:*PB020*)"]


def test_sintaxe_que_nao_filtra_e_falha():
    """O Aconex ignorou a sintaxe e devolveu o register inteiro: a sonda não passa."""
    respostas = _respostas_boas()
    respostas["title:SOBRESSALENTES"] = Pagina([_reg(CODIGO, "777")], TOTAL)
    sondas = diagnostico.sondar(_Cliente(respostas=respostas), CODIGO)
    sonda = {s.nome: s for s in sondas}["Busca por título (title:SOBRESSALENTES)"]
    assert not sonda.ok
    assert sonda.detalhe == "12000 de 12000 documentos: a sintaxe não filtrou"


def test_sem_total_conta_a_pagina_e_avisa():
    respostas = _respostas_boas()
    respostas[""] = Pagina([_reg("#A", "1")], None)
    sondas = diagnostico.sondar(_Cliente(respostas=respostas), CODIGO)
    assert {s.nome: s.detalhe for s in sondas}["Register inteiro (busca vazia)"] == \
        "1 documento (sem TotalResults: só a 1ª página)"


def test_detalhe_nao_vaza_titulo():
    sondas = diagnostico.sondar(_Cliente(respostas=_respostas_boas()), CODIGO)
    assert all(TITULO not in s.detalhe for s in sondas)


def test_erro_inesperado_nao_vaza_a_mensagem():
    respostas = _respostas_boas()
    respostas["title:SOBRESSALENTES"] = ValueError(TITULO)
    sondas = diagnostico.sondar(_Cliente(respostas=respostas), CODIGO)
    detalhe = {s.nome: s.detalhe for s in sondas}["Busca por título (title:SOBRESSALENTES)"]
    assert "ValueError" in detalhe and TITULO not in detalhe


def test_token_recusado_para_as_outras_sondas():
    cliente = _Cliente(login_ok=False, respostas=_respostas_boas())
    sondas = diagnostico.sondar(cliente, CODIGO)
    assert [(s.nome, s.ok) for s in sondas] == [("Login no Aconex", False)]
    assert "HTTP 401" in sondas[0].detalhe
    assert cliente.consultas == []


def test_codigo_que_nao_existe_pula_so_o_tracking_id():
    respostas = _respostas_boas()
    del respostas[f'"{CODIGO}"']
    cliente = _Cliente(respostas=respostas)
    sondas = diagnostico.sondar(cliente, CODIGO)
    assert [(s.nome, s.ok) for s in sondas] == [
        ("Login no Aconex", True),
        ("Register inteiro (busca vazia)", True),
        ("Busca exata do código, com histórico", False),
        ("Busca por título (title:SOBRESSALENTES)", True),
        ("Busca por código (docno:*PB020*)", False),
    ]
    assert not any(c.startswith("trackingid") for c in cliente.consultas)


def test_main_imprime_uma_linha_por_sonda(monkeypatch, capsys):
    perfil = PerfilAconex("Luan Cozer", "A", "1", "s3gr3d0")
    monkeypatch.setattr(diagnostico, "ler_perfis", lambda: [perfil])
    monkeypatch.setattr(diagnostico, "ClienteAconex", lambda p, **kw: _Cliente(respostas=_respostas_boas()))
    assert diagnostico.main([CODIGO]) == 0
    linhas = capsys.readouterr().out.strip().splitlines()
    assert linhas[0] == "OK      Login no Aconex: token recebido"
    assert linhas[4] == 'FALHOU  Busca pelo Tracking ID (trackingid:"<id>"): nenhum documento'
    assert len(linhas) == 7
    assert "s3gr3d0" not in "\n".join(linhas)


def test_main_sem_perfil_avisa_e_sai_com_erro(monkeypatch, capsys):
    monkeypatch.setattr(diagnostico, "ler_perfis", lambda: [])
    assert diagnostico.main([CODIGO]) == 1
    assert "credenciais.json" in capsys.readouterr().out


def test_main_com_dois_perfis_pede_o_perfil(monkeypatch, capsys):
    perfis = [PerfilAconex("Ana", "A", "1", "x"), PerfilAconex("Luan Cozer", "B", "2", "y")]
    usados = []
    monkeypatch.setattr(diagnostico, "ler_perfis", lambda: perfis)
    monkeypatch.setattr(diagnostico, "ClienteAconex",
                        lambda p, **kw: usados.append(p.nome) or _Cliente(respostas=_respostas_boas()))
    assert diagnostico.main([CODIGO]) == 1
    saida = capsys.readouterr().out
    assert "--perfil" in saida and "Ana" in saida and "Luan Cozer" in saida
    assert diagnostico.main([CODIGO, "--perfil", "Luan Cozer"]) == 0
    assert usados == ["Luan Cozer"]
