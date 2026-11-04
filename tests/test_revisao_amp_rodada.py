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
