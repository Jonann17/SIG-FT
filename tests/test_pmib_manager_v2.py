r"""
O Gestão PMIB no tratamento v2 -- T3 do roteiro
(`gestao-sobressalentes/07 - Diagnostico/Tarefa SIG-FT - Calculo e Gravacao sem Perda.md`).

  A. a cascata da SITUAÇÃO NO PMIB, agora função pura (mesma lógica);
  B. `_atualizar_autorizacao` sobre os `_STATUS_PMIB` do KIT DE TESTE, com
     openpyxl e lxml de verdade -- recalcula e grava SITUAÇÃO e DIAS DE ATRASO,
     lê a revisão em uso, não toca no layout antigo;
  C. o fluxo inteiro (`executar_fluxo`) sobre uma cópia do kit, conferido pelo
     VALIDADOR do kit (`validar_kit_gestao_pmib.py`) -- o critério de pronto da
     T3 é ele dizer KIT OK. Precisa também do pandas de verdade.

O kit e o validador moram no cofre (`gestao-sobressalentes/_gestao_v2/`), e
não foram copiados de propósito: são a especificação escrita com o Luan, e uma
cópia aqui envelheceria sem ninguém ver. Sem o cofre, B e C são PULADOS -- e o
motivo aparece no relatório do pytest.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import shutil
import warnings
import zipfile
from pathlib import Path

import pytest

from _openpyxl_de_verdade import openpyxl_de_verdade
from _pandas_de_verdade import pandas_de_verdade

from sigft import config
from sigft.services import pmib_manager
from sigft.services.pmib_manager import PMIBManager, situacao_no_pmib

RAIZ = Path(__file__).resolve().parent.parent
GESTAO_V2 = RAIZ / "gestao-sobressalentes" / "_gestao_v2"
KIT = GESTAO_V2 / "fixtures" / "kit_gestao_pmib"
T1 = "#ST00=TESTE01&MPB020_STATUS_PMIB.xlsx"
T2 = "#ST00=TESTE02&MPB020_STATUS_PMIB.xlsx"
HOJE = dt.date(2026, 10, 10)


def _sem_kit():
    return not (KIT / "esperado.json").is_file()


precisa_do_kit = pytest.mark.skipif(_sem_kit(), reason="kit de teste do cofre ausente (gestao-sobressalentes/)")


@pytest.fixture
def kit(tmp_path):
    destino = tmp_path / "kit"
    shutil.copytree(KIT, destino)
    return destino


def _esperado():
    return json.loads((KIT / "esperado.json").read_text(encoding="utf-8"))


def _partes(caminho):
    with zipfile.ZipFile(caminho) as z:
        return {n: z.read(n) for n in z.namelist()}


def _aba(caminho):
    from openpyxl import load_workbook

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return load_workbook(caminho)[config.ABA_LISTA_MATERIAIS]


def _consumir(gerador):
    """Roda um generator até o fim: (linhas de log, valor do `return`)."""
    linhas = []
    while True:
        try:
            linhas.append(next(gerador))
        except StopIteration as fim:
            return linhas, fim.value


# ===========================================================================
# A. A cascata da SITUAÇÃO NO PMIB (função pura)
# ===========================================================================
@pytest.mark.parametrize("dados, status_revisao, esperado", [
    ({}, "", "INICIAR"),
    ({"total_fichas": 3}, "LISTA NÃO EMITIDA", "LISTA NÃO EMITIDA"),
    ({"total_fichas": 3}, "SEM LISTA", "SEM LISTA"),
    ({"total_fichas": 3, "fichas_para_iniciar": 1, "fichas_criadas": 2}, "", "CRIAÇÃO DAS FICHAS EM PROCESSO"),
    ({"total_fichas": 3, "fichas_criadas": 3}, "", "FICHAS CRIADAS"),
    ({"total_fichas": 2, "fichas_aprovadas": 1, "fichas_na": 1}, "", "FINALIZADO"),
    ({"total_fichas": 2, "fichas_em_correcao": 1, "fichas_em_elaboracao": 1}, "", "CORREÇÃO / ELABORAÇÃO"),
    ({"total_fichas": 2, "fichas_em_analise_ib": 2}, "", "EM ANÁLISE ITAIPU"),
    ({"total_fichas": 2, "fichas_com_fornecedor": 2}, "", "FICHAS COM O FORNECEDOR"),
    ({"total_fichas": 3, "fichas_criadas": 1, "fichas_aprovadas": 1, "fichas_com_fornecedor": 1}, "", "EM ANDAMENTO"),
])
def test_cascata_da_situacao_no_pmib(dados, status_revisao, esperado):
    assert situacao_no_pmib(dados, status_revisao) == esperado


# ===========================================================================
# B. Recalcular e gravar o `_STATUS_PMIB` (openpyxl + lxml de verdade)
# ===========================================================================
@precisa_do_kit
def test_recalcula_os_13_casos_do_kit_e_grava(kit):
    pytest.importorskip("lxml")
    t1 = kit / "status" / T1
    antes = _partes(t1)

    with openpyxl_de_verdade():
        linhas, resultado = _consumir(PMIBManager()._atualizar_autorizacao(str(t1), HOJE))
        ws = _aba(t1)

        for linha, v in _esperado()["status_pmib"]["#ST00=TESTE01&MPB020"]["linhas"].items():
            assert (ws[f"S{linha}"].value or "") == v["situacao"], f"linha {linha}: {v['por_que']}"
            dias = ws[f"T{linha}"].value
            assert (int(dias) if dias not in (None, "") else None) == v["dias"], f"linha {linha}"

    assert resultado == {"revisao_em_uso": "1", "calculado": True, "gravado": True,
                         "pendente": True, "falha": None, "nao_lido": False}
    assert any("célula(s)" in linha for linha in linhas)
    depois = _partes(t1)
    for parte in ("xl/comments1.xml", "xl/threadedComments/threadedComment1.xml", "xl/persons/person.xml"):
        assert depois[parte] == antes[parte], parte
    assert b'name="sigft_calculado_em">"2026-10-10"' in depois["xl/workbook.xml"]


@precisa_do_kit
def test_o_layout_antigo_nao_e_gravado_e_o_log_diz_por_que(kit):
    pytest.importorskip("lxml")
    t2 = kit / "status" / T2
    antes = t2.read_bytes()

    with openpyxl_de_verdade():
        linhas, resultado = _consumir(PMIBManager()._atualizar_autorizacao(str(t2), HOJE))

    assert t2.read_bytes() == antes
    assert resultado["gravado"] is False and resultado["calculado"] is False
    assert any("sem layout v2" in linha for linha in linhas)


@precisa_do_kit
def test_rodar_de_novo_no_mesmo_dia_nao_regrava(kit):
    pytest.importorskip("lxml")
    t1 = kit / "status" / T1

    with openpyxl_de_verdade():
        _consumir(PMIBManager()._atualizar_autorizacao(str(t1), HOJE))
        primeira = t1.read_bytes()
        _linhas, resultado = _consumir(PMIBManager()._atualizar_autorizacao(str(t1), HOJE))

    assert t1.read_bytes() == primeira
    assert resultado == {"revisao_em_uso": "1", "calculado": True, "gravado": False,
                         "pendente": False, "falha": None, "nao_lido": False}


@precisa_do_kit
def test_no_dia_seguinte_os_dias_de_atraso_andam(kit):
    pytest.importorskip("lxml")
    t1 = kit / "status" / T1

    with openpyxl_de_verdade():
        _consumir(PMIBManager()._atualizar_autorizacao(str(t1), HOJE))
        _consumir(PMIBManager()._atualizar_autorizacao(str(t1), HOJE + dt.timedelta(days=1)))
        ws = _aba(t1)

    assert (ws["S6"].value, ws["T6"].value) == ("ATRASADO ITAIPU", 5)
    assert (ws["S16"].value, ws["T16"].value) == ("ATRASADO ITAIPU", 13)
    assert ws["T8"].value == 2  # AUTORIZADO: congelado


@precisa_do_kit
def test_dias_com_formato_de_data_herdado_vira_formato_geral(kit):
    # O defeito dos 33 arquivos: DIAS DE ATRASO com o formato de data da
    # coluna vizinha mostra 4 como 04/01/1900. Ao gravar, o formato vira Geral
    # -- inclusive no AUTORIZADO (linha 8), cujo número não muda.
    pytest.importorskip("lxml")
    from sigft.core.excel import cirurgico

    t1 = kit / "status" / T1
    planilha = cirurgico.PlanilhaXlsx(t1)
    parte = planilha.parte_da_aba(config.ABA_LISTA_MATERIAIS)
    estilo_data = planilha.estilo(parte, "R6")  # DATA DO EMAIL
    planilha.escrever(parte, "T6", None, estilo=estilo_data)
    planilha.escrever(parte, "T8", 2, estilo=estilo_data)
    planilha.salvar()

    with openpyxl_de_verdade():
        assert _aba(t1)["T8"].is_date  # o problema montado
        _consumir(PMIBManager()._atualizar_autorizacao(str(t1), HOJE))
        ws = _aba(t1)

        assert (ws["T6"].value, ws["T6"].is_date) == (4, False)
        assert (ws["T8"].value, ws["T8"].is_date) == (2, False)


@precisa_do_kit
def test_arquivo_aberto_no_excel_nao_pergunta_devolve_a_falha_e_nao_estraga(kit, monkeypatch):
    # [2026-10-06] Antes, uma janela por arquivo, no meio da etapa. Agora a
    # falha volta com o motivo e quem pergunta, uma vez, no fim da etapa, é o
    # fluxo (tests/test_pmib_manager_travados.py).
    pytest.importorskip("lxml")
    from sigft.core.excel import cirurgico, travas

    t1 = kit / "status" / T1
    antes = t1.read_bytes()

    def _aberto(self, destino=None):
        raise PermissionError(13, "aberto no Excel")

    monkeypatch.setattr(cirurgico.PlanilhaXlsx, "salvar", _aberto)
    with openpyxl_de_verdade():
        linhas, resultado = _consumir(PMIBManager()._atualizar_autorizacao(str(t1), HOJE))

    assert t1.read_bytes() == antes
    assert resultado["gravado"] is False
    assert resultado["falha"].caminho == str(t1)  # nomeia o arquivo
    assert resultado["falha"].diagnostico.tipo == travas.EM_USO  # sem `~$` ao lado
    assert any(T1 in linha and "em uso por outro programa" in linha for linha in linhas)


def test_xls_antigo_e_avisado_e_nao_quebra(tmp_path):
    arquivo = tmp_path / "#ST00=X&MPB020_STATUS_PMIB.xls"
    arquivo.write_bytes(b"")

    linhas, resultado = _consumir(PMIBManager()._atualizar_autorizacao(str(arquivo), HOJE))

    assert resultado["gravado"] is False
    assert linhas and linhas[0].startswith("[AVISO]") and ".xls" in linhas[0]


# ===========================================================================
# C. O fluxo inteiro, conferido pelo validador do kit
# ===========================================================================
def _validador():
    spec = importlib.util.spec_from_file_location("validar_kit_gestao_pmib", GESTAO_V2 / "validar_kit_gestao_pmib.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@precisa_do_kit
def test_fluxo_inteiro_sobre_o_kit_da_kit_ok(kit, monkeypatch):
    pytest.importorskip("lxml")
    with openpyxl_de_verdade(pmib_manager) as openpyxl_real, pandas_de_verdade(pmib_manager):
        # `import openpyxl` no topo do serviço: o `openpyxl.styles.Font` do
        # link "Abrir Box" tem de ser o de verdade.
        monkeypatch.setattr(pmib_manager, "openpyxl", openpyxl_real)
        log = [m if isinstance(m, str) else m[0] for m in PMIBManager().executar_fluxo(
            str(kit / "docmanager_sintetico.xlsx"), str(kit / "status"), str(kit / "mapeadora_sintetica.xlsx"),
            hoje=HOJE)]

        erros = _validador().validar(kit)

    assert erros == [], "\n".join(erros)
    assert any("Ignorado" in linha and "testes_autospec" in linha for linha in log)
    assert any("sem layout v2" in linha for linha in log)
    assert not [linha for linha in log if "[ERRO]" in linha]


# ===========================================================================
# D. O que saiu do código (critério de pronto da T3)
# ===========================================================================
def test_a_regra_dos_14_dias_corridos_e_o_atualizar_template_sairam():
    fonte = (RAIZ / "sigft" / "services" / "pmib_manager.py").read_text(encoding="utf-8")
    assert "to_timedelta(14" not in fonte
    assert '"Atualizar template"' not in fonte


def test_a_mapeadora_nao_recebe_mais_contagem():
    # As colunas de contagem saíram da mapeadora em 05/10/2026: o serviço não
    # pode voltar a gravá-las (o validador confere que nenhuma é CRIADA).
    fonte = (RAIZ / "sigft" / "services" / "pmib_manager.py").read_text(encoding="utf-8")
    for coluna in ("'FICHAS EXISTENTES'", "'ÍNDICE DE EMISSAO'", "'ÍNDICE DE CONCLUSÃO'",
                   "'ATRASO DE AUTORIZAÇÃO DE ENTREGA ITAIPU'", "'APTO PARA ENTREGA': 'fichas_aptas"):
        assert coluna not in fonte, coluna
