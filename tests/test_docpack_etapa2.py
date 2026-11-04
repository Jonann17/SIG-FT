"""DocPack, Etapa 2: a lista de materiais do PDF, lida pelo AMP, no `_STATUS_PMIB` e na lista
com preço. Os templates de verdade (os do repositório, em `gestao-sobressalentes/`), o Aconex
e o AMP falsos: nada vai à rede. O que se trava aqui: só planilha vazia recebe, o preço nunca
entra, o VBA do `.xlsm` sai byte a byte, e o PDF que já está na pasta nunca é sobrescrito.
"""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pytest
from _openpyxl_de_verdade import openpyxl_de_verdade

from sigft.core.aconex.cliente import ErroAconex, Versao
from sigft.core.amp.cliente import RespostaAmp
from sigft.services import docpack_etapa2 as e2

XL = None   # o openpyxl de verdade, durante cada teste (`_openpyxl`)


@pytest.fixture(autouse=True)
def _openpyxl():
    global XL
    with openpyxl_de_verdade(e2) as real:
        XL = real
        yield
    XL = None


def load_workbook(*args, **kw):
    return XL.load_workbook(*args, **kw)


RAIZ_REPO = Path(__file__).resolve().parents[1]
TEMPLATE_STATUS = RAIZ_REPO / "gestao-sobressalentes/_gestao_v2/template/codigo_itaipu_STATUS_PMIB_v2.xlsx"
TEMPLATE_PRECOS = (RAIZ_REPO / "gestao-sobressalentes/_gestao_v2/fixtures/kit_lista_precos/"
                   "Lista de Sobressalentes com preço.xlsm")
CODIGO = "#ST00=M00MEU10&MPB020"
PRECOS = "#ST00=M00MEU10&MPB021"

CABECALHO = ("PÁGINA", "ITEM", "QTD.", "UNID.", "DESCRIÇÃO", "CÓDIGO DO MATERIAL", "CÓDIGO CMI",
             "MARCA/MODELO", "CÓDIGO PMIB", "PDM usado", "STATUS", "TIPO DE ENTREGA")
LINHAS = (
    ("1", "1", "2", "pç", "ROLAMENTO 6205", "123", "CMI-1", "SKF / 6205-2RS", "", "", "", "Física e documental"),
    ("2", "2", "1,5", "m", "CABO<br>4MM", "456", "", "", "", "", "A CONFERIR", "DOCUMENTAL"),
    ("2", "", "", "", "", "", "", "", "", "", "", ""),
)


def _html(cabecalho=CABECALHO, linhas=LINHAS, extra=""):
    def tr(celulas, tag="td"):
        return "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in celulas) + "</tr>"
    resumo = "<table><tr><td>Lista</td><td>3 itens</td></tr></table>"
    return ("<!DOCTYPE html><html><body><h2>Resumo</h2>" + resumo + "<h2>Controle</h2><table>"
            + tr(cabecalho, "th") + "".join(tr(l) for l in linhas) + "</table>" + extra
            + "<button onclick='copiar()'>Copiar</button></body></html>")


def _dossie(tmp_path, *, com_precos=True) -> Path:
    pasta = tmp_path / "RAIZ" / "03 - EBOP" / "GERADOR DIESEL"
    pasta.mkdir(parents=True)
    shutil.copyfile(TEMPLATE_STATUS, pasta / f"{CODIGO}_STATUS_PMIB.xlsx")
    if com_precos:
        shutil.copyfile(TEMPLATE_PRECOS, pasta / f"{PRECOS}.xlsm")
    return tmp_path / "RAIZ"


def _ping_ok():
    return RespostaAmp(True, "ping", 200, 0.5, "{}", {"ok": True, "versao_workflow": "2026-11-04", "execucao": "1"})


class _Amp:
    def __init__(self, *respostas, ping=None):
        self.respostas = list(respostas)
        self.envios = []
        self._ping = ping or _ping_ok()

    def ping(self):
        return self._ping

    def enviar(self, campos, arquivos):
        self.envios.append((dict(campos), dict(arquivos)))
        return self.respostas.pop(0)


def _resposta(html=None, **extra):
    dados = {"ok": True, "modo": "criar", "html": _html() if html is None else html, "execucao": "77", **extra}
    return RespostaAmp(True, "criar", 200, 42.0, json.dumps(dados), dados)


class _Aconex:
    def __init__(self, vigente=None, erro=None):
        self.vigente, self.erro, self.baixados = vigente, erro, []

    def versao_vigente(self, codigo):
        if self.erro:
            raise self.erro
        return self.vigente

    def baixar(self, document_id):
        self.baixados.append(document_id)
        return b"%PDF-1.4 lista"


def _versao(revisao="0C"):
    campos = Versao.__dataclass_fields__
    valores = {nome: "" for nome in campos}
    valores.update({"document_id": "DOC1", "revisao": revisao})
    return Versao(**valores)


# ------------------------------------------------------------------ a varredura

def test_acha_o_dossie_vazio_com_a_lista_com_preco(tmp_path):
    raiz = _dossie(tmp_path)
    varredura = e2.procurar_dossies(raiz)
    assert [d.codigo for d in varredura.vazios] == [CODIGO]
    dossie = varredura.vazios[0]
    assert dossie.lista_precos.name == f"{PRECOS}.xlsm" and dossie.precos_vazia
    assert varredura.com_materiais == []


def test_status_com_material_fica_fora(tmp_path):
    raiz = _dossie(tmp_path)
    dossie = e2.procurar_dossies(raiz).vazios[0]
    e2.gravar_planilha(dossie.status_pmib, [e2.Material(1, 1, "pç", "PECA")], e2.COLUNAS_STATUS)
    varredura = e2.procurar_dossies(raiz)
    assert varredura.vazios == [] and varredura.com_materiais == [CODIGO]


def test_sem_lista_com_preco_o_dossie_entra_assim_mesmo(tmp_path):
    dossie = e2.procurar_dossies(_dossie(tmp_path, com_precos=False)).vazios[0]
    assert dossie.lista_precos is None


def test_o_cabecalho_se_acha_pelo_texto(tmp_path):
    raiz = _dossie(tmp_path)
    dossie = e2.procurar_dossies(raiz).vazios[0]
    numero, colunas = e2.achar_cabecalho(e2._ler_aba(dossie.status_pmib), e2.COLUNAS_STATUS)
    assert numero == 5 and colunas["DESCRICAO"] == 4 and colunas["TIPO DE ENTREGA"] == 17
    numero, colunas = e2.achar_cabecalho(e2._ler_aba(dossie.lista_precos), e2.COLUNAS_PRECOS)
    assert numero == 4 and colunas["CODIGO GE"] == 7 and colunas["VALOR UNITARIO"] == 9


# ------------------------------------------------------------------ a resposta do AMP

def test_le_a_tabela_do_controle_pelos_nomes_do_template():
    materiais, avisos = e2.ler_materiais(_html())
    assert [m.descricao for m in materiais] == ["ROLAMENTO 6205", "CABO 4MM"]
    primeiro = materiais[0]
    assert (primeiro.item, primeiro.qtd, primeiro.codigo_cmi, primeiro.fabricante_modelo) == (
        1, 2, "CMI-1", "SKF / 6205-2RS")
    assert primeiro.tipo_entrega == "FÍSICA E DOCUMENTAL" and materiais[1].qtd == 1.5
    assert avisos == []   # a linha toda vazia não é aviso


def test_coluna_de_preco_na_tabela_e_ignorada_com_aviso():
    cabecalho = CABECALHO + ("VALOR UNITÁRIO",)
    linhas = tuple(linha + ("99,90",) for linha in LINHAS)
    materiais, avisos = e2.ler_materiais(_html(cabecalho, linhas))
    assert len(materiais) == 2 and any("preço" in a for a in avisos)
    assert all(not hasattr(m, "valor_unitario") for m in materiais)


def test_html_sem_a_tabela_do_controle_avisa():
    materiais, avisos = e2.ler_materiais("<!DOCTYPE html><html><table><tr><td>x</td></tr></table></html>")
    assert materiais == [] and avisos


def test_o_pedido_e_o_do_workflow_da_criacao(tmp_path):
    from datetime import date

    dossie = e2.procurar_dossies(_dossie(tmp_path)).vazios[0]
    pdf = dossie.pasta / f"{CODIGO}[0C].pdf"
    pedido = e2.montar_pedido(dossie, pdf, "0C", hoje=date(2026, 11, 4))
    assert pedido.campos == {"modo": "criar", "mensagem": (
        f"Lista: {CODIGO}. Revisão: 0C (arquivo {pdf.name}). Template: {dossie.status_pmib.name}. "
        f"Data de hoje: 04/11/2026. Crie o controle.")}
    assert pedido.arquivos == {"lista": pdf, "template": dossie.status_pmib}


def test_o_gerador_do_workflow_da_criacao_pede_lista_e_template():
    texto = (RAIZ_REPO / "amp/criacao_status_pmib/gerar_workflow.py").read_text(encoding="utf-8")
    assert "`lista`" in texto and "`template`" in texto and "'criar'" in texto


# ------------------------------------------------------------------ a gravação

def test_grava_no_status_e_na_lista_com_preco_sem_preco(tmp_path):
    dossie = e2.procurar_dossies(_dossie(tmp_path)).vazios[0]
    materiais, _ = e2.ler_materiais(_html())
    proposta = e2.Proposta(dossie, "pronta", "", None, "0C", tuple(materiais))
    [resultado] = e2.gravar([proposta], log_cb=lambda _m: None)
    assert resultado.situacao == "gravado"
    ws = load_workbook(dossie.status_pmib)["Lista de Materiais"]
    assert [ws.cell(6, c).value for c in (1, 2, 3, 4, 5, 6, 7, 17)] == [
        1, 2, "pç", "ROLAMENTO 6205", "123", "CMI-1", "SKF / 6205-2RS", "FÍSICA E DOCUMENTAL"]
    assert ws.cell(7, 10).value is None   # STATUS: da equipe, mesmo que o agente escreva
    assert ws.cell(7, 2).value == 1.5 and ws.cell(7, 4).value == "CABO 4MM"
    assert ws.cell(6, 8).value is None   # CÓDIGO PMIB: da pessoa
    wp = load_workbook(dossie.lista_precos, keep_vba=True)["Lista de Materiais"]
    assert [wp.cell(5, c).value for c in (4, 5, 6, 7, 10)] == [
        "ROLAMENTO 6205", "SKF / 6205-2RS", "123", None, "FÍSICA E DOCUMENTAL"]
    assert wp.cell(5, 9).value is None and wp.cell(6, 9).value is None   # VALOR UNITÁRIO nunca


def test_o_vba_e_o_resto_do_pacote_saem_byte_a_byte(tmp_path):
    dossie = e2.procurar_dossies(_dossie(tmp_path)).vazios[0]
    with zipfile.ZipFile(dossie.lista_precos) as z:
        antes = {n: z.read(n) for n in z.namelist()}
    e2.gravar_planilha(dossie.lista_precos, [e2.Material(1, 1, "pç", "PECA")], e2.COLUNAS_PRECOS)
    with zipfile.ZipFile(dossie.lista_precos) as z:
        depois = {n: z.read(n) for n in z.namelist()}
    assert "xl/vbaProject.bin" in antes and depois["xl/vbaProject.bin"] == antes["xl/vbaProject.bin"]
    mudaram = {n for n in antes if depois.get(n) != antes[n]}
    assert mudaram and all(n.startswith("xl/worksheets/") or n == "xl/workbook.xml" for n in mudaram), mudaram


def test_planilha_preenchida_entre_a_previa_e_o_sim_e_recusada(tmp_path):
    dossie = e2.procurar_dossies(_dossie(tmp_path)).vazios[0]
    e2.gravar_planilha(dossie.status_pmib, [e2.Material(1, 1, "pç", "DA PESSOA")], e2.COLUNAS_STATUS)
    proposta = e2.Proposta(dossie, "pronta", "", None, "0C", (e2.Material(1, 1, "pç", "DO AMP"),))
    [resultado] = e2.gravar([proposta], log_cb=lambda _m: None)
    assert resultado.situacao == "recusado"
    assert load_workbook(dossie.status_pmib)["Lista de Materiais"].cell(6, 4).value == "DA PESSOA"


def test_lista_com_preco_ja_preenchida_vira_parcial(tmp_path):
    dossie = e2.procurar_dossies(_dossie(tmp_path)).vazios[0]
    e2.gravar_planilha(dossie.lista_precos, [e2.Material(1, 1, "pç", "DA PESSOA")], e2.COLUNAS_PRECOS)
    [resultado] = e2.gravar([e2.Proposta(dossie, "pronta", "", None, "0C", (e2.Material(1, 1, "pç", "X"),))],
                            log_cb=lambda _m: None)
    assert resultado.situacao == "parcial" and "já tem materiais" in resultado.detalhe


def test_arquivo_aberto_no_excel_nao_derruba(tmp_path, monkeypatch):
    dossie = e2.procurar_dossies(_dossie(tmp_path)).vazios[0]

    def aberto(*_a, **_k):
        raise PermissionError("em uso")

    monkeypatch.setattr(e2, "gravar_planilha", aberto)
    [resultado] = e2.gravar([e2.Proposta(dossie, "pronta", "", None, "0C", (e2.Material(1, 1, "pç", "X"),))],
                            log_cb=lambda _m: None)
    assert resultado.situacao == "falhou" and "aberto no Excel" in resultado.detalhe


# ------------------------------------------------------------------ a consulta

def test_consulta_baixa_o_vigente_manda_lista_e_template_e_guarda_o_html(tmp_path):
    dossie = e2.procurar_dossies(_dossie(tmp_path)).vazios[0]
    aconex = _Aconex()
    aconex.vigente = _versao("0C")
    amp = _Amp(_resposta())
    linhas = []
    [proposta] = e2.consultar([dossie], aconex, amp, log_cb=linhas.append, batimento=0)
    assert proposta.situacao == "pronta" and proposta.revisao == "0C" and len(proposta.materiais) == 2
    pdf = dossie.pasta / f"{CODIGO}[0C].pdf"
    assert pdf.read_bytes() == b"%PDF-1.4 lista"
    campos, arquivos = amp.envios[0]
    assert campos["modo"] == "criar" and arquivos == {"lista": pdf, "template": dossie.status_pmib}
    guardado = dossie.pasta / f"{CODIGO}[0C] criacao AMP.html"
    assert "ROLAMENTO 6205" in guardado.read_text(encoding="utf-8")
    # Nada foi escrito nas planilhas: é só a proposta.
    assert e2.planilha_vazia(dossie.status_pmib, e2.COLUNAS_STATUS)


def test_o_pdf_que_ja_esta_na_pasta_nao_e_sobrescrito(tmp_path):
    dossie = e2.procurar_dossies(_dossie(tmp_path)).vazios[0]
    pdf = dossie.pasta / f"{CODIGO}[0C].pdf"
    pdf.write_bytes(b"%PDF da pessoa")
    aconex = _Aconex()
    aconex.vigente = _versao("0C")
    [proposta] = e2.consultar([dossie], aconex, _Amp(_resposta()), log_cb=lambda _m: None, batimento=0)
    assert proposta.situacao == "pronta" and pdf.read_bytes() == b"%PDF da pessoa" and aconex.baixados == []


def test_sem_aconex_usa_o_pdf_da_pasta(tmp_path):
    dossie = e2.procurar_dossies(_dossie(tmp_path)).vazios[0]
    (dossie.pasta / f"{CODIGO}[0B].pdf").write_bytes(b"%PDF")
    [proposta] = e2.consultar([dossie], None, _Amp(_resposta()), log_cb=lambda _m: None, batimento=0)
    assert proposta.situacao == "pronta" and proposta.revisao == "0B"


def test_sem_aconex_e_sem_pdf_falha_sem_chamar_o_amp(tmp_path):
    dossie = e2.procurar_dossies(_dossie(tmp_path)).vazios[0]
    amp = _Amp()
    [proposta] = e2.consultar([dossie], None, amp, log_cb=lambda _m: None, batimento=0)
    assert proposta.situacao == "falhou" and amp.envios == []


def test_erro_do_aconex_vira_falha_e_os_outros_seguem(tmp_path):
    dossie = e2.procurar_dossies(_dossie(tmp_path)).vazios[0]
    aconex = _Aconex(erro=ErroAconex("token recusado"))
    [proposta] = e2.consultar([dossie], aconex, _Amp(), log_cb=lambda _m: None, batimento=0)
    assert proposta.situacao == "falhou" and "token recusado" in proposta.detalhe


def test_ping_falhou_nada_vai(tmp_path):
    dossie = e2.procurar_dossies(_dossie(tmp_path)).vazios[0]
    amp = _Amp(ping=RespostaAmp(False, "ping", 401, 0.2, "", erro="o AMP recusou a chave (HTTP 401)"))
    [proposta] = e2.consultar([dossie], _Aconex(), amp, log_cb=lambda _m: None, batimento=0)
    assert proposta.situacao == "falhou" and amp.envios == [] and "recusou" in proposta.detalhe


def test_parar_deixa_os_que_faltam_parados(tmp_path):
    dossie = e2.procurar_dossies(_dossie(tmp_path)).vazios[0]
    [proposta] = e2.consultar([dossie], None, _Amp(), log_cb=lambda _m: None, cancelado_cb=lambda: True,
                              batimento=0)
    assert proposta.situacao == "parado"


def test_o_resumo_da_confirmacao(tmp_path):
    dossie = e2.procurar_dossies(_dossie(tmp_path)).vazios[0]
    materiais = tuple(e2.Material(i, 1, "pç", f"PECA {i}") for i in range(1, 6))
    texto = e2.resumo_da_proposta([e2.Proposta(dossie, "pronta", "", None, "0C", materiais),
                                   e2.Proposta(dossie, "falhou", "x")])
    assert texto == f"{CODIGO} [0C]: 5 material(is) (PECA 1; PECA 2; PECA 3; +2)"


@pytest.mark.parametrize("valor,esperado", [("2", 2), ("2,5", 2.5), (3.0, 3), ("1 jogo", "1 jogo"), (None, "")])
def test_quantidade(valor, esperado):
    assert e2._numero(valor) == esperado
