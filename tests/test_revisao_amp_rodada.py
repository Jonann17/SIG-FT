"""A rodada da revisão no AMP: uma lista por vez, o HTML gravado sem sobrescrever, a falha de
uma lista que não para as outras e o diagnóstico que pode ir para o Claude na web: sem texto de
documento e sem a chave. Desenho: `docs/superpowers/specs/2026-10-27-amp-revisao-de-listas-design.md`,
§7 e §8.
"""
from __future__ import annotations

import json

from sigft.core import dados_usuario
from sigft.core.amp.cliente import RespostaAmp
from sigft.services import conferencia_revisoes as cr
from sigft.services import revisao_amp as ra

CODIGO = "#ITA0=Y01TF001&BPB020"
OUTRO = "#ST00=X01MPB020&MPB020"
URL = "https://ampworkflow.gevernova.net/webhook/sigft-revisao-listas"
DOCUMENTO = "TEXTO_DO_DOCUMENTO_QUE_NAO_PODE_SAIR"


def _lista(tmp_path, codigo=CODIGO, falta="", em_uso="0A"):
    pasta = tmp_path / codigo[-6:]
    pasta.mkdir(parents=True, exist_ok=True)
    dados = cr.ListaNaMapeadora(codigo, "0B", "Em Processo", "Aprovado", em_uso, "x")
    return ra.ListaParaAmp(cr.ItemConferencia(dados, "aprovada", pasta), pasta / "s.xlsx",
                           pasta / "a.pdf", pasta / "b.pdf", "0B", falta)


def _montar(lista, _versao):
    return {"modo": "revisar", "lista": {"codigo": lista.item.lista.codigo},
            "revisao_em_uso": {"arquivo": "a.pdf", "paginas": 2, "texto": DOCUMENTO},
            "revisao_atual": {"arquivo": "b.pdf", "paginas": 3, "texto": DOCUMENTO * 2},
            "status_pmib": {"arquivo": "s.xlsx", "aba": "Lista de Materiais", "linha_de_revisao": DOCUMENTO,
                            "linhas": 5, "tsv": DOCUMENTO}}


class _Cliente:
    def __init__(self, *respostas, ping=None, eco=None):
        self.respostas = list(respostas)
        self.pedidos = []
        self._ping, self._eco = ping, eco
        self.ecos = []

    def revisar(self, pedido):
        self.pedidos.append(pedido)
        return self.respostas.pop(0)

    def ping(self):
        return self._ping

    def eco(self, codigos):
        self.ecos.append(list(codigos))
        return self._eco


def _ok(html="<!doctype html><html><table></table></html>"):
    return RespostaAmp(True, "revisar", 200, 12.3, "{}", {"ok": True, "html": html, "execucao": "9"})


def _falha(erro="model timeout", http=502, dados=None):
    dados = dados if dados is not None else {"ok": False, "etapa": "agente", "erro": erro, "execucao": "77"}
    return RespostaAmp(False, "revisar", http, 47.2, json.dumps(dados), dados, erro)


def _rodar(listas, cliente, **kw):
    kw.setdefault("montar", _montar)
    return ra.revisar_listas(listas, cliente, versao_sigft="1.3.1-rc.2", url=URL, chave_posta=True,
                             log_cb=lambda _m: None, **kw)


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


def test_falta_nao_chama(tmp_path):
    cliente = _Cliente()
    [resultado] = _rodar([_lista(tmp_path, falta="falta: PDF da revisão atual")], cliente)
    assert (resultado.situacao, resultado.detalhe) == ("falta", "falta: PDF da revisão atual")
    assert cliente.pedidos == []


def test_erro_ao_ler_vira_falta(tmp_path):
    def quebra(_lista, _versao):
        raise ValueError("PDF sem texto (só imagem)")

    [resultado] = _rodar([_lista(tmp_path)], _Cliente(), montar=quebra)
    assert (resultado.situacao, resultado.detalhe) == ("falta", "falta: PDF sem texto (só imagem)")


def test_defeito_ao_montar_vira_falha_e_as_outras_seguem(tmp_path):
    # Um PDF corrompido (o PyMuPDF levanta RuntimeError) ou um defeito do SIG-FT: diagnóstico.
    def defeito(lista, versao):
        if lista.item.lista.codigo == CODIGO:
            raise RuntimeError("cannot open broken document")
        return _montar(lista, versao)

    resultados = _rodar([_lista(tmp_path), _lista(tmp_path, OUTRO)], _Cliente(_ok()), montar=defeito)
    assert [r.situacao for r in resultados] == ["falhou", "pronto"]
    assert "RuntimeError: cannot open broken document" in resultados[0].diagnostico


def test_falha_de_rede_numa_lista_e_as_outras_seguem(tmp_path):
    rede = RespostaAmp(False, "revisar", None, 30.0, "", {}, "Sem conexão com o AMP: nenhuma rota respondeu")
    resultados = _rodar([_lista(tmp_path), _lista(tmp_path, OUTRO)], _Cliente(rede, _ok()))
    assert [r.situacao for r in resultados] == ["falhou", "pronto"]
    assert "Sem conexão com o AMP: nenhuma rota respondeu" in resultados[0].diagnostico


def test_diagnostico_sem_texto_de_documento_e_sem_chave(tmp_path):
    dados = {"ok": False, "modo": "revisar", "html": f"Não consegui: {DOCUMENTO}", "execucao": "77",
             "erro": "o agente não devolveu HTML"}
    [resultado] = _rodar([_lista(tmp_path)], _Cliente(_falha("o agente não devolveu HTML", 200, dados)))
    texto = resultado.diagnostico
    assert DOCUMENTO not in texto
    assert "SIG-FT · Revisão no AMP · diagnóstico" in texto
    assert "1.3.1-rc.2" in texto and CODIGO in texto and URL in texto
    assert "chave: posta" in texto
    assert "2 páginas" in texto and "3 páginas" in texto and "5 linhas" in texto
    assert "HTTP 200" in texto and "execução do n8n: 77" in texto
    assert "o agente não devolveu HTML" in texto
    assert "sigft/services/revisao_amp.py" in texto


def test_diagnostico_tira_trecho_do_documento_que_volta_no_erro(tmp_path):
    # O erro do nó de modelo pode repetir a saída do modelo, e ela, o documento.
    erro = f"Could not parse LLM output: {DOCUMENTO}"
    dados = {"ok": False, "etapa": "agente", "erro": erro, "execucao": "78"}
    [resultado] = _rodar([_lista(tmp_path)], _Cliente(_falha(erro, 502, dados)))
    assert DOCUMENTO not in resultado.diagnostico and DOCUMENTO not in resultado.detalhe
    assert "Could not parse LLM output" in resultado.diagnostico


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


def test_cancelar_entre_as_listas(tmp_path):
    pedidos = iter([False, True])
    cliente = _Cliente(_ok())
    resultados = _rodar([_lista(tmp_path), _lista(tmp_path, OUTRO)], cliente, cancelado_cb=lambda: next(pedidos))
    assert [r.situacao for r in resultados] == ["pronto", "parado"]
    assert len(cliente.pedidos) == 1


def test_cada_resultado_sai_antes_da_proxima_lista(tmp_path):
    # A tela mostra cada lista quando ela volta: são até 15 minutos por lista.
    vistos, ja_vistos_na_chamada = [], []
    cliente = _Cliente(_ok(), _falha())
    revisar = cliente.revisar

    def espiar(pedido):
        ja_vistos_na_chamada.append(len(vistos))
        return revisar(pedido)

    cliente.revisar = espiar
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


def test_codigos_para_eco_junta_listas_e_materiais(tmp_path):
    tabela = ra.TabelaStatus("Lista de Materiais", "", 15, "", [f"MAT-{i}" for i in range(15)])
    codigos = ra.codigos_para_eco([_lista(tmp_path), _lista(tmp_path, OUTRO)], ler_status=lambda _c: tabela)
    assert codigos == [CODIGO, OUTRO] + [f"MAT-{i}" for i in range(10)]


def _eco_ok(texto):
    return RespostaAmp(True, "eco", 200, 2.0, "{}", {"ok": True, "texto": texto, "execucao": "5"})


def _ping_ok():
    return RespostaAmp(True, "ping", 200, 0.3, "{}", {"ok": True, "versao_workflow": "2026-10-27", "execucao": "4"})


def _tabela_vazia(_c):
    return ra.TabelaStatus("a", "", 0, "", [])


def test_testar_conexao_ok(tmp_path):
    cliente = _Cliente(ping=_ping_ok(), eco=_eco_ok(f"{CODIGO}\n"))
    linhas = ra.testar_conexao(cliente, [_lista(tmp_path)], ler_status=_tabela_vazia)
    assert linhas[0].startswith("OK      Ping: workflow 2026-10-27")
    assert linhas[1].startswith("OK      Eco: os 1 códigos voltaram iguais")


def test_eco_acusa_codigo_mascarado(tmp_path):
    cliente = _Cliente(ping=_ping_ok(), eco=_eco_ok("#ITA0=***\n"))
    linhas = ra.testar_conexao(cliente, [_lista(tmp_path)], ler_status=_tabela_vazia)
    assert linhas[1].startswith("FALHOU  Eco:") and "mascarado" in linhas[1]


def test_eco_sem_codigos_nao_e_mandado():
    cliente = _Cliente(ping=_ping_ok())
    linhas = ra.testar_conexao(cliente, [], ler_status=_tabela_vazia)
    assert linhas[0].startswith("OK      Ping:")
    assert linhas[1].startswith("--      Eco: não mandado")
    assert cliente.ecos == []


def test_ping_falho_para_o_teste(tmp_path):
    falho = RespostaAmp(False, "ping", 403, 0.2, "", {}, "o AMP recusou a chave (HTTP 403)")
    cliente = _Cliente(ping=falho)
    linhas = ra.testar_conexao(cliente, [_lista(tmp_path)], ler_status=_tabela_vazia)
    assert linhas == ["FALHOU  Ping: o AMP recusou a chave (HTTP 403)"]
    assert cliente.ecos == []
