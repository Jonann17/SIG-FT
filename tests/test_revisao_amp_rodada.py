"""A rodada da revisão no AMP: o ping antes, uma lista por vez, o log de cada uma (o que vai,
o que voltou, a execução do n8n e o batimento da espera), o HTML gravado sem sobrescrever, a
falha de uma lista que não para as outras e o diagnóstico que pode ir para o Claude na web: sem
conteúdo de documento e sem a chave. Desenho:
`docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`, §5.3, §5.4 e §5.6.
"""
from __future__ import annotations

import json
import time

from sigft.core import dados_usuario
from sigft.core.amp.cliente import RespostaAmp
from sigft.services import conferencia_revisoes as cr
from sigft.services import revisao_amp as ra

CODIGO = "#ITA0=Y01TF001&BPB020"
OUTRO = "#ST00=X01MPB020&MPB020"
URL = "https://ampworkflow.gevernova.net/webhook/sigft-revisao-listas"
CHAVE = "chave-que-nao-pode-aparecer"
DOCUMENTO = "CONTEUDO_DO_DOCUMENTO_QUE_NAO_PODE_SAIR"
HTML = f"<!doctype html><html><table><tr><td>{DOCUMENTO}</td></tr></table></html>"


def _lista(tmp_path, codigo=CODIGO, falta="", em_uso="0A"):
    pasta = tmp_path / codigo[-6:]
    pasta.mkdir(parents=True, exist_ok=True)
    for nome, conteudo in (("a.pdf", b"%PDF" + b"a" * 2044), ("b.pdf", b"%PDF"), ("s.xlsx", b"PK")):
        (pasta / nome).write_bytes(conteudo)
    dados = cr.ListaNaMapeadora(codigo, "0B", "Em Processo", "Aprovado", em_uso, "x")
    return ra.ListaParaAmp(cr.ItemConferencia(dados, "aprovada", pasta), pasta / "s.xlsx",
                           pasta / "a.pdf" if em_uso else None, pasta / "b.pdf", "0B", falta)


def _ping_ok():
    return RespostaAmp(True, "ping", 200, 0.8, "{}", {"ok": True, "versao_workflow": "2026-11-03", "execucao": "100"})


class _Cliente:
    def __init__(self, *respostas, ping=None):
        self.respostas = list(respostas)
        self.envios = []
        self._ping = ping or _ping_ok()

    def ping(self):
        return self._ping

    def enviar(self, campos, arquivos):
        self.envios.append((dict(campos), dict(arquivos)))
        return self.respostas.pop(0)

    buscas: list = []

    def buscar(self, pedido):
        self.perguntas = getattr(self, "perguntas", []) + [pedido]
        return self.buscas.pop(0)


def _ok(html=HTML, arquivos=None, execucao="101"):
    dados = {"ok": True, "modo": "revisar", "html": html, "execucao": execucao}
    if arquivos is not None:
        dados["arquivos"] = arquivos
    return RespostaAmp(True, "revisar", 200, 192.4, json.dumps(dados), dados)


def _falha(erro="model timeout", http=502, dados=None):
    dados = dados if dados is not None else {"ok": False, "modo": "revisar", "etapa": "agente", "erro": erro,
                                             "execucao": "77"}
    return RespostaAmp(False, "revisar", http, 47.2, json.dumps(dados), dados, erro)


def _rodar(listas, cliente, linhas=None, **kw):
    kw.setdefault("batimento", 0)
    kw.setdefault("espera", 0)
    kw.setdefault("dormir", lambda _s: None)
    log = linhas.append if linhas is not None else (lambda _m: None)
    return ra.revisar_listas(listas, cliente, versao_sigft="1.3.3-rc.1", url=URL, chave_posta=True, log_cb=log, **kw)


# ------------------------------------------------------------------ o HTML

def test_html_gravado_com_o_nome_do_padrao(tmp_path):
    lista = _lista(tmp_path)
    [resultado] = _rodar([lista], _Cliente(_ok("<html><table>OK</table></html>")))
    assert resultado.situacao == "pronto"
    assert resultado.html == lista.item.pasta / f"{CODIGO}[0A-0B] revisao AMP.html"
    assert resultado.html.read_text(encoding="utf-8") == "<html><table>OK</table></html>"


def test_nunca_sobrescreve(tmp_path):
    lista = _lista(tmp_path)
    existente = lista.item.pasta / f"{CODIGO}[0A-0B] revisao AMP.html"
    existente.write_text("antigo", encoding="utf-8")
    [resultado] = _rodar([lista], _Cliente(_ok()))
    assert resultado.html.name == f"{CODIGO}[0A-0B] revisao AMP (2).html"
    assert existente.read_text(encoding="utf-8") == "antigo"


def test_nome_do_html():
    assert ra.nome_do_html(CODIGO, "", "0") == f"{CODIGO}[-0] revisao AMP.html"
    assert ra.nome_do_html('A/B:C', "0", "1") == "A_B_C[0-1] revisao AMP.html"


# ------------------------------------------------------------------ o que vai e o que volta

def test_cada_lista_manda_a_mensagem_e_os_arquivos(tmp_path):
    lista = _lista(tmp_path)
    cliente = _Cliente(_ok())
    _rodar([lista], cliente)
    [(campos, arquivos)] = cliente.envios
    assert campos["modo"] == "revisar" and campos["mensagem"].endswith("Faça a revisão.")
    assert arquivos == {"revisao_em_uso": lista.pdf_em_uso, "revisao_atual": lista.pdf_atual,
                        "status_pmib": lista.status_pmib}


def test_falta_nao_chama(tmp_path):
    cliente = _Cliente()
    [resultado] = _rodar([_lista(tmp_path, falta="falta: PDF da revisão atual")], cliente)
    assert (resultado.situacao, resultado.detalhe) == ("falta", "falta: PDF da revisão atual")
    assert cliente.envios == []


def test_defeito_ao_montar_vira_falha_e_as_outras_seguem(tmp_path):
    def defeito(lista):
        if lista.item.lista.codigo == CODIGO:
            raise RuntimeError("defeito do SIG-FT")
        return ra.montar_pedido(lista)

    resultados = _rodar([_lista(tmp_path), _lista(tmp_path, OUTRO)], _Cliente(_ok()), montar=defeito)
    assert [r.situacao for r in resultados] == ["falhou", "pronto"]
    assert "RuntimeError: defeito do SIG-FT" in resultados[0].diagnostico


def test_ping_falho_nao_manda_nada(tmp_path):
    falho = RespostaAmp(False, "ping", 403, 0.2, "", {}, "o AMP recusou a chave (HTTP 403)")
    cliente = _Cliente(ping=falho)
    linhas = []
    resultados = _rodar([_lista(tmp_path), _lista(tmp_path, OUTRO)], cliente, linhas)
    assert [r.situacao for r in resultados] == ["falhou", "falhou"]
    assert resultados[0].detalhe == "o ping falhou: o AMP recusou a chave (HTTP 403)"
    assert resultados[0].diagnostico and resultados[1].diagnostico == ""
    assert cliente.envios == []
    assert "FALHOU  Ping: o AMP recusou a chave (HTTP 403)" in linhas


def test_falha_de_rede_numa_lista_e_as_outras_seguem(tmp_path):
    rede = RespostaAmp(False, "revisar", None, 30.0, "", {}, "Sem conexão com o AMP: nenhuma rota respondeu")
    resultados = _rodar([_lista(tmp_path), _lista(tmp_path, OUTRO)], _Cliente(rede, _ok()))
    assert [r.situacao for r in resultados] == ["falhou", "pronto"]
    assert "Sem conexão com o AMP: nenhuma rota respondeu" in resultados[0].diagnostico


def test_sem_html_e_falha(tmp_path):
    [resultado] = _rodar([_lista(tmp_path)], _Cliente(_ok(html="Não consegui ler.")))
    assert (resultado.situacao, resultado.detalhe) == ("falhou", "o agente não devolveu HTML")


def test_workflow_que_recebeu_menos_arquivos_e_falha(tmp_path):
    [resultado] = _rodar([_lista(tmp_path)], _Cliente(_ok(arquivos=["b.pdf"])))
    assert (resultado.situacao, resultado.detalhe) == ("falhou", "o workflow recebeu 1 de 3 arquivo(s)")


# ------------------------------------------------------------------ o log

def test_o_log_diz_o_que_vai_e_o_que_voltou(tmp_path):
    linhas = []
    _rodar([_lista(tmp_path), _lista(tmp_path, OUTRO, falta="falta: PDF da revisão atual")],
           _Cliente(_ok(arquivos=["a.pdf", "b.pdf", "s.xlsx"])), linhas, desmarcadas=["#AAA"], com_falta=["#DDD"])
    assert linhas[:4] == ["Revisão no AMP: 2 lista(s) marcada(s)", "  desmarcadas, ficam fora: 1 (#AAA)",
                          "  com falta, ficam fora: 1 (#DDD)", f"Webhook: {URL} · chave posta"]
    assert "Ping: workflow 2026-11-03 (0,8 s, execução 100)" in linhas
    assert f"[1/2] {CODIGO} · em uso 0A → atual 0B" in linhas
    assert "    vai: a.pdf (2 KB), b.pdf (4 B), s.xlsx (2 B)" in linhas
    assert "    enviado; o agente está lendo (costuma levar alguns minutos)" in linhas
    assert "    resposta: HTTP 200 em 3:12 · execução 101 · o workflow recebeu 3 arquivo(s)" in linhas
    assert any(linha.startswith(f"    ✓ HTML gravado: {CODIGO}[0A-0B] revisao AMP.html (") for linha in linhas)
    assert f"[2/2] {OUTRO} · em uso 0A → atual 0B" in linhas
    assert "    - falta: PDF da revisão atual" in linhas
    assert linhas[-1].startswith("Fim: 1 HTML pronto(s), 0 falha(s), 1 com falta, 0 parada(s), em 0:0")
    texto = "\n".join(linhas)
    assert DOCUMENTO not in texto and CHAVE not in texto


def test_falha_no_log_traz_o_http_a_etapa_e_a_execucao(tmp_path):
    linhas = []
    _rodar([_lista(tmp_path)], _Cliente(_falha()), linhas, gravar_diagnostico=False)
    assert "    resposta: HTTP 502 em 47,2 s · execução 77" in linhas
    assert "    ✗ falhou: model timeout (etapa agente)" in linhas


def test_lista_sem_revisao_em_uso_no_log(tmp_path):
    linhas = []
    _rodar([_lista(tmp_path, em_uso="")], _Cliente(_ok()), linhas)
    assert f"[1/1] {CODIGO} · sem revisão em uso → atual 0B" in linhas
    assert "    vai: b.pdf (4 B), s.xlsx (2 B)" in linhas


def test_a_espera_tem_batimento(tmp_path):
    class _Lento(_Cliente):
        def enviar(self, campos, arquivos):
            time.sleep(0.25)
            return super().enviar(campos, arquivos)

    linhas = []
    _rodar([_lista(tmp_path)], _Lento(_ok()), linhas, batimento=0.05)
    batidas = [linha for linha in linhas if linha.endswith("esperando o AMP")]
    assert len(batidas) >= 2 and batidas[0] == "    … 0:00 esperando o AMP"
    # O batimento para quando a resposta chega: nada dele depois da linha da resposta.
    resposta = next(i for i, linha in enumerate(linhas) if linha.startswith("    resposta:"))
    assert not any(linha.endswith("esperando o AMP") for linha in linhas[resposta:])


# ------------------------------------------------------------------ o diagnóstico

def test_diagnostico_sem_documento_e_sem_chave(tmp_path):
    dados = {"ok": False, "modo": "revisar", "html": f"Não consegui: {DOCUMENTO}", "execucao": "77",
             "erro": "o agente não devolveu HTML"}
    [resultado] = _rodar([_lista(tmp_path)], _Cliente(_falha("o agente não devolveu HTML", 200, dados)))
    texto = resultado.diagnostico
    assert DOCUMENTO not in texto and CHAVE not in texto
    assert "SIG-FT · Revisão no AMP · diagnóstico" in texto
    assert "1.3.3-rc.1" in texto and CODIGO in texto and URL in texto and "chave: posta" in texto
    assert "  revisao_em_uso: a.pdf, 2 KB" in texto
    assert "  revisao_atual: b.pdf, 4 B" in texto and "  status_pmib: s.xlsx, 2 B" in texto
    assert "  mensagem: " in texto and " caracteres" in texto
    assert "HTTP 200" in texto and "execução do n8n: 77" in texto
    assert "o agente não devolveu HTML" in texto
    assert "amp/revisao_de_listas/agente.md" in texto


def test_erro_longo_vai_cortado(tmp_path):
    erro = "Could not parse output: " + "y" * 1000
    [resultado] = _rodar([_lista(tmp_path)], _Cliente(_falha(erro)))
    assert "Could not parse output" in resultado.diagnostico
    assert "y" * 400 not in resultado.diagnostico


def test_corpo_que_nao_e_json_aparece_cortado(tmp_path):
    pagina = "<html>login do proxy</html>" + "x" * 5000
    resposta = RespostaAmp(False, "revisar", 200, 1.0, pagina, {}, "o AMP não respondeu JSON (HTTP 200)")
    [resultado] = _rodar([_lista(tmp_path)], _Cliente(resposta))
    assert "login do proxy" in resultado.diagnostico
    assert "x" * 1501 not in resultado.diagnostico


def test_diagnostico_vai_para_a_pasta_de_logs(tmp_path):
    [resultado] = _rodar([_lista(tmp_path)], _Cliente(_falha()))
    arquivos = list((dados_usuario.pasta_logs() / "amp").glob("*.txt"))
    assert len(arquivos) == 1
    assert arquivos[0].read_text(encoding="utf-8") == resultado.diagnostico


# ------------------------------------------------------------------ o ritmo

def test_cancelar_entre_as_listas(tmp_path):
    pedidos = iter([False, True])
    cliente = _Cliente(_ok())
    resultados = _rodar([_lista(tmp_path), _lista(tmp_path, OUTRO)], cliente, cancelado_cb=lambda: next(pedidos))
    assert [r.situacao for r in resultados] == ["pronto", "parado"]
    assert len(cliente.envios) == 1


def test_cada_resultado_sai_antes_da_proxima_lista(tmp_path):
    # A tela mostra cada lista quando ela volta: são até 45 minutos por lista.
    vistos, ja_vistos_na_chamada = [], []
    cliente = _Cliente(_ok(), _falha())
    enviar = cliente.enviar

    def espiar(campos, arquivos):
        ja_vistos_na_chamada.append(len(vistos))
        return enviar(campos, arquivos)

    cliente.enviar = espiar
    resultados = _rodar([_lista(tmp_path), _lista(tmp_path, OUTRO)], cliente, resultado_cb=vistos.append,
                        gravar_diagnostico=False)
    assert vistos == resultados and ja_vistos_na_chamada == [0, 1]


def test_diagnosticos_para_copiar_juntam_so_as_falhas(tmp_path):
    terceira = _lista(tmp_path / "c", "#ST00=Z01MPB020&MPB020")
    resultados = _rodar([_lista(tmp_path), terceira, _lista(tmp_path, OUTRO)],
                        _Cliente(_falha("model timeout"), _ok(), _falha("o AMP recusou a chave (HTTP 403)")),
                        gravar_diagnostico=False)
    texto = ra.diagnosticos_para_copiar(resultados)
    assert texto.startswith("SIG-FT · Revisão no AMP: 2 lista(s) falharam nesta rodada.")
    assert "conversa nova com o Claude" in texto and "luanccozer/SIG-FT" in texto
    assert texto.index(resultados[0].diagnostico) < texto.index(resultados[2].diagnostico)
    assert ra.diagnosticos_para_copiar([resultados[1]]) == ""


# ------------------------------------------------------------------ o teste de conexão

def test_testar_conexao_ok():
    assert ra.testar_conexao(_Cliente()) == ["OK      Ping: workflow 2026-11-03 (HTTP 200, 0,8 s, execução 100)"]


def test_testar_conexao_falha():
    falho = RespostaAmp(False, "ping", 403, 0.2, "", {}, "o AMP recusou a chave (HTTP 403)")
    assert ra.testar_conexao(_Cliente(ping=falho)) == ["FALHOU  Ping: o AMP recusou a chave (HTTP 403) (0,2 s)"]


# ------------------------------------------------------------------ a resposta que chega depois
# 2026-11-04: uma lista levou 17 min. O workflow responde na hora com o pedido (a execução do n8n)
# e guarda o resultado; o SIG-FT pergunta até ficar pronto. O pedido fica anotado em
# `amp_pendentes.json`, na pasta de dados, até o HTML ser gravado: com o SIG-FT fechado no meio,
# a aba busca o resultado na próxima vez.

def _aceito(pedido="700", arquivos=("a.pdf", "b.pdf", "s.xlsx")):
    dados = {"ok": True, "modo": "revisar", "estado": "aceito", "pedido": pedido, "execucao": pedido,
             "arquivos": list(arquivos)}
    return RespostaAmp(True, "revisar", 200, 1.1, json.dumps(dados), dados)


def _pendente(pedido="700"):
    dados = {"ok": True, "modo": "buscar", "estado": "pendente", "pedido": pedido}
    return RespostaAmp(True, "buscar", 200, 0.4, json.dumps(dados), dados)


def _pronto(pedido="700", html=HTML):
    dados = {"ok": True, "modo": "revisar", "estado": "pronto", "pedido": pedido, "execucao": pedido, "html": html,
             "arquivos": ["a.pdf", "b.pdf", "s.xlsx"]}
    return RespostaAmp(True, "buscar", 200, 0.5, json.dumps(dados), dados)


def _erro_guardado(pedido="700"):
    dados = {"ok": False, "modo": "revisar", "estado": "erro", "etapa": "agente", "erro": "model timeout",
             "pedido": pedido, "execucao": pedido}
    return RespostaAmp(False, "buscar", 200, 0.5, json.dumps(dados), dados, "model timeout")


def _cliente_com_buscas(*buscas, envio=None):
    cliente = _Cliente(envio or _aceito())
    cliente.buscas = list(buscas)
    return cliente


def test_aceito_pergunta_ate_ficar_pronto_e_grava(tmp_path):
    lista = _lista(tmp_path)
    linhas = []
    cliente = _cliente_com_buscas(_pendente(), _pendente(), _pronto())
    [resultado] = _rodar([lista], cliente, linhas)
    assert resultado.situacao == "pronto" and resultado.html.read_text(encoding="utf-8") == HTML
    assert cliente.perguntas == ["700", "700", "700"]
    assert "    aceito: o agente está lendo (pedido 700); pergunto pelo resultado a cada 0 s" in linhas
    assert sum(1 for linha in linhas if linha.endswith("esperando o AMP (pedido 700)")) == 2
    assert ra.ler_pendentes() == []


def test_erro_do_agente_guardado_e_falha_e_sai_dos_pendentes(tmp_path):
    [resultado] = _rodar([_lista(tmp_path)], _cliente_com_buscas(_erro_guardado()), gravar_diagnostico=False)
    assert (resultado.situacao, resultado.detalhe) == ("falhou", "model timeout (etapa agente)")
    assert ra.ler_pendentes() == []


def test_pergunta_que_falha_tenta_de_novo(tmp_path):
    caiu = RespostaAmp(False, "buscar", None, 1.0, "", {}, "Falha ao perguntar ao AMP: ConnectionError: caiu")
    linhas = []
    [resultado] = _rodar([_lista(tmp_path)], _cliente_com_buscas(caiu, _pronto()), linhas)
    assert resultado.situacao == "pronto"
    assert any("a pergunta ao AMP falhou" in linha for linha in linhas)


def test_parar_na_espera_deixa_a_lista_no_amp(tmp_path):
    lista = _lista(tmp_path)
    pedidos = iter([False, True])
    [resultado] = _rodar([lista], _cliente_com_buscas(_pendente()), cancelado_cb=lambda: next(pedidos, True))
    assert resultado.situacao == "pendente"
    assert resultado.detalhe == "no AMP: o HTML é buscado depois (pedido 700)"
    [pendente] = ra.ler_pendentes()
    assert (pendente["pedido"], pendente["url"], pendente["codigo"]) == ("700", URL, CODIGO)
    assert pendente["pasta"] == str(lista.item.pasta)
    assert pendente["nome"] == f"{CODIGO}[0A-0B] revisao AMP.html"


def test_passou_do_maximo_fica_no_amp(tmp_path):
    linhas = []
    [resultado] = _rodar([_lista(tmp_path)], _cliente_com_buscas(_pendente()), linhas, espera_maxima=0)
    assert resultado.situacao == "pendente"
    assert linhas[-1].startswith("Fim: 0 HTML pronto(s), 0 falha(s), 0 com falta, 0 parada(s), 1 no AMP, em")
    assert len(ra.ler_pendentes()) == 1


def test_workflow_antigo_que_devolve_o_html_na_hora_continua_valendo(tmp_path):
    cliente = _Cliente(_ok())
    [resultado] = _rodar([_lista(tmp_path)], cliente)
    assert resultado.situacao == "pronto" and getattr(cliente, "perguntas", []) == []


def test_buscar_pendentes_recupera_o_html(tmp_path):
    lista = _lista(tmp_path)
    pedidos = iter([False, True])
    _rodar([lista], _cliente_com_buscas(_pendente()), cancelado_cb=lambda: next(pedidos, True))
    criados = []

    def criar_cliente(url):
        cliente = _cliente_com_buscas(_pronto())
        criados.append(url)
        return cliente

    linhas = []
    assert ra.buscar_pendentes(criar_cliente, linhas.append) == 1
    assert criados == [URL]
    html = lista.item.pasta / f"{CODIGO}[0A-0B] revisao AMP.html"
    assert html.read_text(encoding="utf-8") == HTML
    assert ra.ler_pendentes() == []
    assert any(linha.startswith(f"  ✓ {CODIGO}: HTML recuperado") for linha in linhas)


def test_buscar_pendentes_ainda_no_amp_fica_e_o_antigo_sai(tmp_path):
    from datetime import datetime, timedelta

    ra.registrar_pendente(_lista(tmp_path), "800", URL)
    ra.registrar_pendente(_lista(tmp_path, OUTRO), "801", URL, agora=datetime.now() - timedelta(days=8))
    respostas = {"800": _pendente("800"), "801": _pendente("801")}

    class _Busca:
        def buscar(self, pedido):
            return respostas[pedido]

    linhas = []
    assert ra.buscar_pendentes(lambda _url: _Busca(), linhas.append) == 0
    assert [p["pedido"] for p in ra.ler_pendentes()] == ["800"]
    assert any("ainda no AMP" in linha for linha in linhas)
    assert any("desisti" in linha for linha in linhas)


def test_sem_pendentes_nao_pergunta_nada():
    assert ra.buscar_pendentes(lambda _url: (_ for _ in ()).throw(AssertionError("não devia criar")),
                               lambda _m: None) == 0
