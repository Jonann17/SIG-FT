r"""
O painel HTML de sobressalentes gerado pelo Gestão PMIB -- T7 do roteiro
(`sigft/services/painel.py`).

Regra de ouro do roteiro: os números têm de ser os mesmos do Power BI v2 (o
painel oficial). A prova é o validador do kit (`validar_painel.py`, no cofre):
roda a implementação de referência no MESMO kit e na mesma data e compara os
dados embutidos na página, campo a campo -- fichas, listas, listas de preços,
atividades e achados de qualidade -- e confere que a página abre sem rede e tem
os filtros de ET, Capítulo e Lista.

  A. funções puras (nomes de exibição, datas, PMIB estrito, `limpar`);
  B. o template é cópia SEM MUDANÇA do protótipo do cofre, e vai no .exe;
  C. o painel sobre o kit dá PAINEL OK (pandas e openpyxl de verdade).
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import shutil
from pathlib import Path

import pytest

from _openpyxl_de_verdade import openpyxl_de_verdade
from _pandas_de_verdade import pandas_de_verdade

from sigft.services import painel, pmib_manager

RAIZ = Path(__file__).resolve().parent.parent
COFRE = RAIZ / "gestao-sobressalentes"
KIT = COFRE / "_gestao_v2" / "fixtures" / "kit_gestao_pmib"
HOJE = dt.date(2026, 10, 10)

precisa_do_kit = pytest.mark.skipif(not (KIT / "esperado.json").is_file(),
                                    reason="kit de teste do cofre ausente (gestao-sobressalentes/)")


# ===========================================================================
# A. Funções puras
# ===========================================================================
@pytest.mark.parametrize("sistema, nome", [
    ("05 - UNIDADE GERADORA › 01-SISTEMA DE EXCITAÇÃO", "SISTEMA DE EXCITAÇÃO"),
    ("ELETRICA › REGULAÇÃO VEL E POT › PARTE DIGITAL", "REGULAÇÃO DE VELOCIDADE › PARTE DIGITAL"),
    ("ELETRICA › SISTEMA X › R0A", "ELETRICA › SISTEMA X"),
    ("MECANICA › BOMBAS", "MECANICA › BOMBAS"),  # última curta demais sozinha
    ("TRANSFORMADORES ELEVADORES PRINCIPAIS - 50 Hz e 60 Hz", "TRAFOS ELEVADORES"),
])
def test_nome_de_exibicao(sistema, nome):
    assert painel.nome_exibicao(sistema) == nome


def test_sem_prefixo_e_nome_curto():
    assert painel.sem_prefixo("05 - UNIDADE GERADORA") == "UNIDADE GERADORA"
    assert painel.sem_prefixo(None) == ""
    assert painel.nome_curto("ENG. ELÉTRICA - EXCITAÇÃO - LISTA DE SOBRESSALENTES", "#ST00=X") == "EXCITAÇÃO"
    assert painel.nome_curto(None, "#ST00=X") == "#ST00=X"


@pytest.mark.parametrize("valor, esperado", [
    (dt.date(2026, 9, 15), "2026-09-15"),
    (dt.datetime(2026, 9, 15, 13, 0), "2026-09-15"),
    ("15/09/2026", "2026-09-15"),
    ("2026-09-15", None),
    (None, None),
    (45000, None),
])
def test_iso(valor, esperado):
    assert painel.iso(valor) == esperado


@pytest.mark.parametrize("valor, pmib", [
    ("4500063671.0156", "4500063671.0156"),
    (" 4500063671.015 ", "4500063671.0150"),
    ("45000636710156", "4500063671.0156"),
    ("4500063671156", None),          # sem ponto, sequencial de 3: ambíguo
    ("N/A", None),
    ("", None),
    (None, None),
    ("123.4567", None),
])
def test_pmib_estrito_do_painel(valor, pmib):
    # Decide O QUE É FICHA -- a mesma definição do fxPMIB do Power BI.
    assert painel.normalizar_pmib(valor) == pmib


def test_pendencia_na_ordem_da_fila():
    ok = {s: True for s in painel.SECOES}
    assert painel.pendencia(False, "INICIAR", "", ok, False, False, "") == "—"
    assert painel.pendencia(True, "EM CORREÇÃO", "ATRASADO ITAIPU", ok, False, False, "") == "Responder comentários de Itaipu"
    assert painel.pendencia(True, "EM ANÁLISE IB", "ATRASADO ITAIPU", ok, False, False, "") == "Cobrar autorização de Itaipu"
    assert painel.pendencia(True, "EM ANÁLISE IB", "AUTORIZADO", ok, True, False,
                            "FÍSICA E DOCUMENTAL") == "Entregar no almoxarifado"
    sem_lmr = dict(ok, **{"APLICACAO - LMR": False})
    assert painel.pendencia(True, "EM ANÁLISE IB", "", sem_lmr, False, False, "") == "Aplicação LMR"
    assert painel.pendencia(True, "EM ELABORAÇÃO", "", ok, False, False, "") == "Emitir para Itaipu"


def test_situacao_lmr():
    assert painel.situacao_lmr(dt.date(2026, 9, 1), "COMPLETO", HOJE) == "LMR CONCLUÍDA"
    assert painel.situacao_lmr(None, "", HOJE) == "SEM PEDIDO"
    assert painel.situacao_lmr(dt.date(2026, 9, 1), "", HOJE) == "LMR NO PRAZO"
    assert painel.situacao_lmr(dt.date(2026, 7, 1), "", HOJE) == "LMR FORA DO COMPROMISSO"
    assert painel.situacao_lmr(dt.date(2026, 8, 1), "", HOJE) == "LMR EM ATENÇÃO"


def test_limpar_troca_nan_por_null_e_numpy_por_python():
    numpy = pytest.importorskip("numpy")
    with pandas_de_verdade(painel):
        assert painel.limpar({"a": float("nan"), "b": [1, numpy.int64(2)], "c": "x"}) == {"a": None, "b": [1, 2], "c": "x"}


def _mapeadora_com_atividades(caminho, colunas_atividades):
    import openpyxl

    wb = openpyxl.Workbook()
    principal = wb.active
    principal.title = "Acompanhamento Sobressalente"
    principal.append(["título"])
    principal.append(["N DOCUMENTO ITAIPU"])
    principal.append(["LISTA-1"])
    atv = wb.create_sheet("Atividades")
    atv.append(colunas_atividades)
    atv.append(["x"] * len(colunas_atividades))
    wb.save(caminho)


def test_aba_atividades_com_outras_colunas_nao_derruba_o_painel(tmp_path):
    """Pendência do Luan de 2026-10-15: sem a aba o painel já seguia sem a
    seção, mas uma aba com OUTRAS colunas dava `KeyError` em NV ou CODIGO
    ITAIPU e o painel não saía. Agora segue sem a seção, como sem a aba."""
    pytest.importorskip("pandas")
    pytest.importorskip("openpyxl")
    caminho = tmp_path / "mapeadora.xlsx"
    with openpyxl_de_verdade(painel), pandas_de_verdade(painel):
        _mapeadora_com_atividades(caminho, ["ATIVIDADE", "RESPONSAVEL", "PRAZO"])
        dados = painel.ler_mapeadora(caminho)

    assert len(dados["listas"]) == 1
    assert dados["atividades"].empty


# ===========================================================================
# B. O template
# ===========================================================================
def test_o_template_esta_no_pacote_e_e_achado():
    assert painel.caminho_do_template() == RAIZ / "sigft" / "assets" / "painel_template.html"


@pytest.mark.skipif(not (COFRE / "_scripts" / "prototipo_template.html").is_file(), reason="cofre ausente")
def test_o_template_e_copia_sem_mudanca_do_prototipo():
    # Regra do roteiro: mudança no desenho vale para os dois painéis.
    assert painel.caminho_do_template().read_bytes() == (COFRE / "_scripts" / "prototipo_template.html").read_bytes()


def test_template_conta_lista_aprovada_pela_marca_do_servico():
    """[2026-10-26] O STATUS REAL passou a distinguir Aprovado, Aprovado com
    Comentários e Para Assinatura: comparar com o texto "APROVADO" deixaria de
    contar as duas últimas. A conta usa a marca `aprov` que o serviço calcula."""
    html = painel.caminho_do_template().read_text(encoding="utf-8")
    assert 'l.sr === "APROVADO"' not in html
    assert "l.aprov" in html


def test_o_template_nao_depende_de_rede():
    import re

    html = painel.caminho_do_template().read_text(encoding="utf-8")
    assert not re.findall(r'<(?:script|link|img)[^>]+(?:src|href)="(?:https?:)?//', html)
    assert "/*__DADOS__*/" in html


def test_o_spec_leva_o_template_para_o_exe():
    spec = (RAIZ / "SIG-FT.spec").read_text(encoding="utf-8")
    assert '"painel_template.html"' in spec


def test_gerar_html_escapa_o_fechamento_de_script():
    html = painel.gerar_html({"itens": [{"d": "texto </script> malicioso"}]})
    assert "texto <\\/script> malicioso" in html
    assert html.count("</script>") == painel.caminho_do_template().read_text(encoding="utf-8").count("</script>")


# ===========================================================================
# C. O painel sobre o kit: PAINEL OK
# ===========================================================================
def _validador_do_painel():
    spec = importlib.util.spec_from_file_location("validar_painel", COFRE / "_gestao_v2" / "validar_painel.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@precisa_do_kit
def test_lista_aprovada_pela_familia_de_aprovacao(tmp_path):
    """[2026-10-26] Para Assinatura e o antigo APROVADO contam como lista
    aprovada; Em Processo, não. Antes só o texto "APROVADO" contava."""
    pytest.importorskip("pandas")
    pytest.importorskip("openpyxl")
    kit = tmp_path / "kit"
    shutil.copytree(KIT, kit)
    valores = {"#ST00=TESTE01&MPB020": "Para Assinatura", "#ST00=TESTE02&MPB020": "APROVADO",
               "#ST00=TESTE03&MPB020": "Em Processo"}

    with openpyxl_de_verdade(painel) as openpyxl_real, pandas_de_verdade(painel):
        livro = openpyxl_real.load_workbook(kit / "mapeadora_sintetica.xlsx")
        aba = livro["Acompanhamento Sobressalente"]
        cabecalho = [c.value for c in aba[2]]
        col_doc, col_sr = cabecalho.index("N° DOCUMENTO ITAIPU") + 1, cabecalho.index("STATUS REAL") + 1
        for linha in range(3, aba.max_row + 1):
            aba.cell(linha, col_sr).value = valores[aba.cell(linha, col_doc).value]
        livro.save(kit / "mapeadora_sintetica.xlsx")
        dados = painel.montar(HOJE, kit / "status", kit / "mapeadora_sintetica.xlsx")

    aprovadas = {lista["l"]: lista["aprov"] for lista in dados["listas"] if lista["l"] in valores}
    assert aprovadas == {"#ST00=TESTE01&MPB020": True, "#ST00=TESTE02&MPB020": True, "#ST00=TESTE03&MPB020": False}


@precisa_do_kit
def test_painel_do_kit_bate_com_a_referencia(tmp_path, monkeypatch):
    pytest.importorskip("lxml")
    kit = tmp_path / "kit"
    shutil.copytree(KIT, kit)
    saida = kit / "painel.html"
    linhas = []

    with openpyxl_de_verdade(pmib_manager) as openpyxl_real, pandas_de_verdade(painel, pmib_manager):
        monkeypatch.setattr(pmib_manager, "openpyxl", openpyxl_real)
        # Como na tela: primeiro o Gestão PMIB grava, depois o painel lê.
        for _ in pmib_manager.PMIBManager().executar_fluxo(
                str(kit / "docmanager_sintetico.xlsx"), str(kit / "status"), str(kit / "mapeadora_sintetica.xlsx"),
                hoje=HOJE):
            pass
        devolvido = painel.gerar_painel(kit / "status", kit / "mapeadora_sintetica.xlsx", saida, hoje=HOJE,
                                        callback_log=linhas.append)

        validador = _validador_do_painel()
        html = saida.read_text(encoding="utf-8")
        erros = validador.comparar(validador.referencia(kit), validador.dados_do_html(html), html)

    assert erros == [], "\n".join(erros)
    assert devolvido == saida
    assert any("Painel gravado" in linha for linha in linhas)


@precisa_do_kit
def test_painel_com_arquivo_bloqueado_levanta_para_a_tela_decidir(tmp_path, monkeypatch):
    kit = tmp_path / "kit"
    shutil.copytree(KIT, kit)

    def _bloqueado(self, *a, **k):
        raise PermissionError(13, "bloqueado")

    with openpyxl_de_verdade(), pandas_de_verdade(painel):
        monkeypatch.setattr(Path, "write_text", _bloqueado)
        with pytest.raises(PermissionError):
            painel.gerar_painel(kit / "status", kit / "mapeadora_sintetica.xlsx", kit / "painel.html", hoje=HOJE)
