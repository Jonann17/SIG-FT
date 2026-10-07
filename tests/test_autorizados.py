r"""
O export de autorizados de Itaipu gravando nos `_STATUS_PMIB` -- T4 do roteiro
do Gestão PMIB v2 (`sigft/services/autorizados.py`).

Porte de `gestao-sobressalentes/_gestao_v2/referencia_sigft/apto_para_entrega_att.py`
(o script que vivia no Box, com os caminhos fixos no código). O que mudou:

  - os caminhos vêm da tela, não do código;
  - as mesmas exclusões de pasta/cópia do Gestão PMIB (o script também entrava
    em `testes_autospec/`);
  - layout v2: SITUAÇÃO := AUTORIZADO (é fato, vale para qualquer tipo) e, se
    DIAS DE ATRASO estiver vazio, o atraso que houve até a autorização -- a
    data do export sai do NOME do arquivo;
  - layout antigo: APTO := SIM, como antes;
  - grava pelo editor cirúrgico (o script salvava pelo openpyxl e apagava os
    comentários em thread).

Os arquivos são os do kit do cofre (`gestao-sobressalentes/_gestao_v2/fixtures/kit_gestao_pmib/`).
"""
from __future__ import annotations

import datetime as dt
import shutil
import warnings
import zipfile
from pathlib import Path

import pytest

from _excel_de_mentira import ExcelDeMentira, TelaDeMentira, depois_da_conferencia, resumo_do_log
from _openpyxl_de_verdade import openpyxl_de_verdade

from sigft import config
from sigft.core.excel import travas
from sigft.services import autorizados

RAIZ = Path(__file__).resolve().parent.parent
KIT = RAIZ / "gestao-sobressalentes" / "_gestao_v2" / "fixtures" / "kit_gestao_pmib"
T1 = "#ST00=TESTE01&MPB020_STATUS_PMIB.xlsx"
T2 = "#ST00=TESTE02&MPB020_STATUS_PMIB.xlsx"
NOME_EXPORT = "sobressalentes_autorizados_202610090948.xlsx"

precisa_do_kit = pytest.mark.skipif(not (KIT / "status" / T1).is_file(),
                                    reason="kit de teste do cofre ausente (gestao-sobressalentes/)")


# ===========================================================================
# A. Peças puras
# ===========================================================================
@pytest.mark.parametrize("nome, data", [
    ("sobressalentes_autorizados_202607210948.xlsx", dt.date(2026, 7, 21)),
    ("C:/Box/SOBRESSALENTES - PMIB/sobressalentes_autorizados_202610090948.xlsx", dt.date(2026, 10, 9)),
    ("SOBRESSALENTES_AUTORIZADOS_202610091200 (1).xlsx", dt.date(2026, 10, 9)),
    ("sobressalentes_autorizados.xlsx", None),
    ("sobressalentes_autorizados_202613011200.xlsx", None),  # mês 13
    ("outra coisa.xlsx", None),
])
def test_data_do_export_vem_do_nome_do_arquivo(nome, data):
    assert autorizados.data_do_export(nome) == data


# ===========================================================================
# B. Com arquivos de verdade
# ===========================================================================
def _export(pasta, pmibs, nome=NOME_EXPORT):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["ITEM", "PMIB", "DESCRIÇÃO"])
    for i, pmib in enumerate(pmibs, start=1):
        ws.append([i, pmib, f"TEXTO DE TESTE {i}"])
    caminho = pasta / nome
    wb.save(caminho)
    return caminho


def _aba(caminho):
    from openpyxl import load_workbook

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return load_workbook(caminho)[config.ABA_LISTA_MATERIAIS]


def _partes(caminho):
    with zipfile.ZipFile(caminho) as z:
        return {n: z.read(n) for n in z.namelist()}


@pytest.fixture
def pasta(tmp_path):
    destino = tmp_path / "status"
    shutil.copytree(KIT / "status", destino)
    return destino


def test_le_os_pmibs_do_export_normalizados(tmp_path):
    with openpyxl_de_verdade():
        caminho = _export(tmp_path, ["4500063671.9003", " 4500063671.9006 ", 4500063671.901, None, "nan"])

        assert autorizados.ler_autorizados(caminho) == {"4500063671.9003", "4500063671.9006", "4500063671.9010"}


def test_export_sem_coluna_pmib_e_recusado_com_mensagem(tmp_path):
    with openpyxl_de_verdade():
        from openpyxl import Workbook

        wb = Workbook()
        wb.active.append(["ITEM", "CODIGO"])
        wb.save(tmp_path / "x.xlsx")

        with pytest.raises(ValueError, match="PMIB"):
            autorizados.ler_autorizados(tmp_path / "x.xlsx")


@precisa_do_kit
def test_layout_v2_vira_autorizado_e_congela_o_atraso_ate_a_data_do_export(pasta, tmp_path):
    pytest.importorskip("lxml")
    t1 = pasta / T1
    antes = _partes(t1)
    with openpyxl_de_verdade():
        export = _export(tmp_path, ["4500063671.9003", "4500063671.9006"])
        linhas = list(autorizados.executar(export, pasta))
        ws = _aba(t1)

        # linha 6: e-mail 15/09 -> prazo 06/10; export de 09/10 -> 3 dias de atraso
        assert (ws["S6"].value, ws["T6"].value) == ("AUTORIZADO", 3)
        # linha 7: e-mail 01/10 -> prazo 23/10; autorizado no prazo -> dias em branco
        assert (ws["S7"].value, ws["T7"].value) == ("AUTORIZADO", None)
        # linha 14 (DUPLICADO da 6) tem o mesmo PMIB: também vira AUTORIZADO
        assert ws["S14"].value == "AUTORIZADO"
        # quem não está no export fica como estava
        assert ws["S9"].value is None

    depois = _partes(t1)
    for parte in ("xl/comments1.xml", "xl/threadedComments/threadedComment1.xml", "xl/persons/person.xml"):
        assert depois[parte] == antes[parte], parte
    assert any("TESTE01" in linha and "atualizad" in linha.lower() for linha in linhas)


@precisa_do_kit
def test_dias_ja_preenchido_nao_e_recalculado(pasta, tmp_path):
    # Linha 8 do kit: AUTORIZADO com 2 dias -- congelado; a linha 17 tem 30
    # dias de um estado calculado antigo e, pela regra do roteiro, "se DIAS DE
    # ATRASO estiver vazio" -- não está, então fica.
    pytest.importorskip("lxml")
    with openpyxl_de_verdade():
        export = _export(tmp_path, ["4500063671.9043", "4500063671.9010"])
        list(autorizados.executar(export, pasta))
        ws = _aba(pasta / T1)

        assert (ws["S17"].value, ws["T17"].value) == ("AUTORIZADO", 30)
        assert (ws["S8"].value, ws["T8"].value) == ("AUTORIZADO", 2)


@precisa_do_kit
def test_layout_antigo_ganha_apto_sim(pasta, tmp_path):
    pytest.importorskip("lxml")
    with openpyxl_de_verdade():
        export = _export(tmp_path, ["4500063671.9010"])  # linha 7 do TESTE02, APTO vazio
        list(autorizados.executar(export, pasta))
        ws = _aba(pasta / T2)

        assert ws["R7"].value == "SIM"
        assert ws["R8"].value is None  # quem não está no export fica


@precisa_do_kit
def test_a_isca_em_testes_autospec_nao_e_tocada(pasta, tmp_path):
    pytest.importorskip("lxml")
    isca = pasta / "testes_autospec" / T1
    antes = isca.read_bytes()
    with openpyxl_de_verdade():
        export = _export(tmp_path, ["4500063671.9003"])
        linhas = list(autorizados.executar(export, pasta))

    assert isca.read_bytes() == antes
    assert any("Ignorado" in linha and "testes_autospec" in linha for linha in linhas)


@precisa_do_kit
def test_pmib_que_nao_esta_em_nenhum_status_pmib_e_listado(pasta, tmp_path):
    pytest.importorskip("lxml")
    with openpyxl_de_verdade():
        export = _export(tmp_path, ["4500063671.9003", "4500063671.7777"])
        linhas = list(autorizados.executar(export, pasta))

    assert any("4500063671.7777" in linha for linha in linhas)


@precisa_do_kit
def test_rodar_o_mesmo_export_de_novo_nao_regrava(pasta, tmp_path):
    pytest.importorskip("lxml")
    with openpyxl_de_verdade():
        export = _export(tmp_path, ["4500063671.9003"])
        list(autorizados.executar(export, pasta))
        primeira = (pasta / T1).read_bytes()
        list(autorizados.executar(export, pasta))

    assert (pasta / T1).read_bytes() == primeira


@precisa_do_kit
def test_sem_data_no_nome_autoriza_mas_nao_inventa_atraso(pasta, tmp_path):
    pytest.importorskip("lxml")
    with openpyxl_de_verdade():
        export = _export(tmp_path, ["4500063671.9003"], nome="autorizados.xlsx")
        linhas = list(autorizados.executar(export, pasta))
        ws = _aba(pasta / T1)

    assert (ws["S6"].value, ws["T6"].value) == ("AUTORIZADO", None)
    assert any(linha.startswith("[AVISO]") and "data" in linha.lower() for linha in linhas)


@precisa_do_kit
def test_o_gestao_pmib_depois_mantem_o_autorizado(pasta, tmp_path):
    # AUTORIZADO é fato: o recálculo da T3 nunca o desfaz, e os dias ficam.
    pytest.importorskip("lxml")
    from sigft.services.pmib_manager import PMIBManager

    with openpyxl_de_verdade():
        export = _export(tmp_path, ["4500063671.9003"])
        list(autorizados.executar(export, pasta))
        list(PMIBManager()._atualizar_autorizacao(str(pasta / T1), dt.date(2026, 10, 20)))
        ws = _aba(pasta / T1)

    assert (ws["S6"].value, ws["T6"].value) == ("AUTORIZADO", 3)


# ===========================================================================
# F. Arquivo travado: a lista de antes e a do fim  [2026-10-06]
# ===========================================================================
# Ver `docs/superpowers/specs/2026-10-06-gravacao-com-retry-design.md`. O
# Excel aberto é o `ExcelDeMentira`: no Linux da suíte nada impede a escrita.
def _aplicar(export, pasta, tela=None, ao_ver=None):
    linhas = []
    for linha in autorizados.executar(export, pasta, callback_travados=tela):
        linhas.append(linha)
        if ao_ver is not None:
            ao_ver(linha)
    return linhas


@precisa_do_kit
def test_travado_antes_repetir_depois_de_fechar_grava(pasta, tmp_path, monkeypatch):
    pytest.importorskip("lxml")
    t1 = pasta / T1
    excel = ExcelDeMentira(monkeypatch)
    excel.abrir(t1, usuario="Luan")
    tela = TelaDeMentira(True, ao_perguntar=lambda momento, falhas: excel.fechar(t1))
    with openpyxl_de_verdade():
        export = _export(tmp_path, ["4500063671.9003"])
        linhas = _aplicar(export, pasta, tela)
        ws = _aba(t1)

    assert tela.perguntas == [(travas.ANTES, [(T1, "está aberto no Excel por Luan")])]
    assert ws["S6"].value == "AUTORIZADO"
    assert not resumo_do_log(linhas)


@precisa_do_kit
def test_travado_antes_seguir_sem_ele_nao_grava_e_avisa_no_fim(pasta, tmp_path, monkeypatch):
    pytest.importorskip("lxml")
    t1 = pasta / T1
    antes = t1.read_bytes()
    excel = ExcelDeMentira(monkeypatch)
    excel.abrir(t1)
    with openpyxl_de_verdade():
        assert _aba(pasta / T2)["R7"].value is None
        export = _export(tmp_path, ["4500063671.9003", "4500063671.9010"])
        linhas = _aplicar(export, pasta, TelaDeMentira(False))
        ws2 = _aba(pasta / T2)

    assert t1.read_bytes() == antes
    assert ws2["R7"].value == "SIM"  # o outro arquivo seguiu sendo gravado
    resumo = resumo_do_log(linhas)
    assert len(resumo) == 2 and T1 in resumo[1]
    assert "autorizações não gravadas" in resumo[1] and "seguiu sem ele" in resumo[1]


@precisa_do_kit
def test_seguir_sem_um_arquivo_que_nao_tinha_nada_a_gravar_nao_vira_aviso(pasta, tmp_path, monkeypatch):
    # 9010 no TESTE01 já é AUTORIZADO com os dias congelados: nada a gravar
    # nele. Pulá-lo não perdeu nada; o TESTE02 ganha o APTO.
    pytest.importorskip("lxml")
    t1 = pasta / T1
    antes = t1.read_bytes()
    excel = ExcelDeMentira(monkeypatch)
    excel.abrir(t1)
    with openpyxl_de_verdade():
        export = _export(tmp_path, ["4500063671.9010"])
        linhas = _aplicar(export, pasta, TelaDeMentira(False))
        ws2 = _aba(pasta / T2)

    assert t1.read_bytes() == antes
    assert ws2["R7"].value == "SIM"
    assert not resumo_do_log(linhas)


@precisa_do_kit
def test_trava_durante_vai_para_a_lista_do_fim_e_repetir_rele_e_grava(pasta, tmp_path, monkeypatch):
    pytest.importorskip("lxml")
    t1 = pasta / T1
    excel = ExcelDeMentira(monkeypatch)
    tela = TelaDeMentira(True, ao_perguntar=lambda momento, falhas: excel.fechar(t1))
    with openpyxl_de_verdade():
        export = _export(tmp_path, ["4500063671.9003"])
        linhas = _aplicar(export, pasta, tela,
                          ao_ver=lambda linha: excel.abrir(t1) if depois_da_conferencia(linha) else None)
        ws = _aba(t1)

    assert tela.perguntas == [(travas.DEPOIS, [(T1, "está aberto no Excel por Luan")])]
    assert ws["S6"].value == "AUTORIZADO"
    assert any(T1 in linha and "gravado na nova tentativa" in linha for linha in linhas)
    assert not [linha for linha in linhas if "[AVISO]" in linha]
    assert not resumo_do_log(linhas)


@precisa_do_kit
def test_repetir_que_acha_o_arquivo_fora_do_padrao_nao_diz_que_gravou(pasta, tmp_path, monkeypatch):
    pytest.importorskip("lxml")
    from sigft.core.excel import status_sheet

    t1 = pasta / T1
    excel = ExcelDeMentira(monkeypatch)
    abrir_de_verdade = status_sheet.StatusPMIB.abrir
    aba_renomeada = []

    def _abrir(self, *args, **kwargs):
        if aba_renomeada and str(self.caminho_excel) == str(t1):
            raise KeyError("Lista de Materiais")
        return abrir_de_verdade(self, *args, **kwargs)

    monkeypatch.setattr(status_sheet.StatusPMIB, "abrir", _abrir)
    tela = TelaDeMentira(True, ao_perguntar=lambda momento, falhas: (excel.fechar(t1), aba_renomeada.append(1)))
    with openpyxl_de_verdade():
        export = _export(tmp_path, ["4500063671.9003"])
        linhas = _aplicar(export, pasta, tela,
                          ao_ver=lambda linha: excel.abrir(t1) if depois_da_conferencia(linha) else None)

    assert not [linha for linha in linhas if "gravado na nova tentativa" in linha]
    assert len(tela.perguntas) == 1
    resumo = resumo_do_log(linhas)
    assert len(resumo) == 2 and T1 in resumo[1]


@precisa_do_kit
def test_sem_callback_o_travado_nao_e_gravado_e_fica_no_resumo(pasta, tmp_path, monkeypatch):
    pytest.importorskip("lxml")
    t1 = pasta / T1
    antes = t1.read_bytes()
    excel = ExcelDeMentira(monkeypatch)
    with openpyxl_de_verdade():
        export = _export(tmp_path, ["4500063671.9003"])
        linhas = _aplicar(export, pasta,
                          ao_ver=lambda linha: excel.abrir(t1) if depois_da_conferencia(linha) else None)

    assert t1.read_bytes() == antes
    resumo = resumo_do_log(linhas)
    assert len(resumo) == 2 and T1 in resumo[1] and "aberto no Excel" in resumo[1]
    assert any("1 não gravado" in linha for linha in linhas)


def test_o_callback_antigo_saiu():
    import inspect

    assert "callback_retry_lock" not in inspect.signature(autorizados.executar).parameters
