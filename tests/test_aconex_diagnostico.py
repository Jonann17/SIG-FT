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
        self.pedidos = {}

    def conectar(self):
        if not self.login_ok:
            raise ErroAconex("O Aconex recusou as credenciais do perfil Luan Cozer (HTTP 401).")

    def primeira_pagina(self, consulta, *, historico, campos=None, page_size=None):
        self.consultas.append(consulta)
        self.pedidos[consulta] = {"campos": campos, "page_size": page_size}
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
        "title:SOBRESSALENTES": Pagina(_titulos(), 4),
    }


def _titulos():
    """A busca por título traz listas, a lista de preços e uma planilha de
    comissionamento: só as duas primeiras são listas novas (`e_lista_de_sobressalentes`)."""
    return [_reg(CODIGO, "777", f"LISTA DE SOBRESSALENTES {TITULO}"),
            _reg("#ITA0=Y01TF002&BPB020-01", "778", f"LISTA DE SOBRESSALENTES {TITULO}"),
            _reg("#ITA0=Y01TF001&BPB020-02", "779", f"LISTA DE SOBRESSALENTES COM PREÇOS {TITULO}"),
            _reg("#ITA0=Y01TF001&BTB010", "780", f"PLANILHA DE COMISSIONAMENTO SOBRESSALENTES {TITULO}")]


def test_sonda_ok_e_falha_por_etapa():
    sondas = diagnostico.sondar(_Cliente(respostas=_respostas_boas()), CODIGO)
    assert [(s.nome, s.ok) for s in sondas] == [
        ("Login no Aconex", True),
        ("Register inteiro (busca vazia)", True),
        ("Busca exata do código, com histórico", True),
        ("Busca pelo Tracking ID (trackingid:<id>)", True),
        ('Busca pelo Tracking ID (trackingid:"<id>")', False),
        ("Busca por título (title:SOBRESSALENTES)", True),
        (diagnostico.SONDA_LISTAS_NOVAS, True),
    ]
    detalhes = {s.nome: s.detalhe for s in sondas}
    assert detalhes["Register inteiro (busca vazia)"] == "12000 documentos"
    assert detalhes["Busca exata do código, com histórico"] == "2 versões"
    assert detalhes["Busca pelo Tracking ID (trackingid:<id>)"] == "3 versões (a busca exata trouxe 2)"
    assert detalhes['Busca pelo Tracking ID (trackingid:"<id>")'] == "nenhum documento"
    assert detalhes["Busca por título (title:SOBRESSALENTES)"] == "4 de 12000 documentos"
    assert detalhes[diagnostico.SONDA_LISTAS_NOVAS] == "2 de 4 com título de sobressalentes"


def test_nao_pede_mais_a_busca_por_codigo_com_coringa():
    """[2026-10-27] `docno:*PB020*` volta HTTP 500 do Aconex (log do Luan, 5 de 5):
    o PB020 se confere no SIG-FT, sobre a busca por título."""
    cliente = _Cliente(respostas=_respostas_boas())
    diagnostico.sondar(cliente, CODIGO)
    assert not any(c.startswith("docno:") for c in cliente.consultas)


def test_busca_por_titulo_pede_o_titulo_e_a_pagina_grande():
    cliente = _Cliente(respostas=_respostas_boas())
    diagnostico.sondar(cliente, CODIGO)
    pedido = cliente.pedidos["title:SOBRESSALENTES"]
    assert "title" in pedido["campos"].split(",") and "docno" in pedido["campos"].split(",")
    assert pedido["page_size"] == 500


def test_listas_novas_alem_da_primeira_pagina_avisa():
    respostas = _respostas_boas()
    respostas["title:SOBRESSALENTES"] = Pagina(_titulos(), 900)
    sondas = diagnostico.sondar(_Cliente(respostas=respostas), CODIGO)
    detalhe = {s.nome: s.detalhe for s in sondas}[diagnostico.SONDA_LISTAS_NOVAS]
    assert detalhe == "2 de 4 com título de sobressalentes (só a 1ª página: 900 no total)"


def test_nenhuma_lista_nova_falha():
    respostas = _respostas_boas()
    respostas["title:SOBRESSALENTES"] = Pagina(_titulos()[2:], 2)
    sondas = diagnostico.sondar(_Cliente(respostas=respostas), CODIGO)
    sonda = {s.nome: s for s in sondas}[diagnostico.SONDA_LISTAS_NOVAS]
    assert not sonda.ok and sonda.detalhe == "0 de 2 com título de sobressalentes"


def test_busca_por_titulo_que_falha_nao_inventa_listas_novas():
    respostas = _respostas_boas()
    respostas["title:SOBRESSALENTES"] = ErroAconex("A busca no Aconex falhou na página 1 após 2 tentativas (HTTP 500).")
    sondas = diagnostico.sondar(_Cliente(respostas=respostas), CODIGO)
    sonda = {s.nome: s for s in sondas}[diagnostico.SONDA_LISTAS_NOVAS]
    assert not sonda.ok and sonda.detalhe == "sem a busca por título"


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
        (diagnostico.SONDA_LISTAS_NOVAS, True),
    ]
    assert not any(c.startswith("trackingid") for c in cliente.consultas)


def test_main_imprime_uma_linha_por_sonda(monkeypatch, capsys):
    perfil = PerfilAconex("Luan Cozer", "A", "1", "s3gr3d0")
    monkeypatch.setattr(diagnostico, "ler_perfis", lambda: [perfil])
    criados = []
    monkeypatch.setattr(diagnostico, "ClienteAconex",
                        lambda p, **kw: criados.append(kw) or _Cliente(respostas=_respostas_boas()))
    assert diagnostico.main([CODIGO]) == 0
    assert criados == [{"tentativas": diagnostico.TENTATIVAS_DO_DIAGNOSTICO}]
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
