r"""
O Gestão PMIB quando a gravação falha: qual arquivo, por quê, e Repetir.
Ver `docs/superpowers/specs/2026-10-06-gravacao-com-retry-design.md`.

  A. as peças: `_atualizar_autorizacao` não pergunta mais (devolve a falha) e
     a renomeação de arquivo aberto não deixa cópia para trás;
  B. a lista de ANTES (Repetir depois de fechar / Seguir sem ele);
  C. a lista do FIM DA ETAPA 5 (trava que aparece durante o processo);
  D. a mapeadora NA HORA -- e o defeito que o desenho conserta: o Repetir
     gravava por cima do que a pessoa salvou antes de fechar;
  E. sem tela nenhuma (callback ausente): nada pergunta, o resumo diz.

O Excel aberto é o `ExcelDeMentira` (tests/_excel_de_mentira.py): no Linux da
suíte, nada impede gravar num arquivo aberto. O critério de pronto de cada
cenário que termina gravando é o do roteiro: o validador do kit diz KIT OK.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import shutil
import warnings
from pathlib import Path

import pytest

from _excel_de_mentira import ExcelDeMentira, TelaDeMentira as _Tela
from _excel_de_mentira import depois_da_conferencia as _antes_de_gravar, resumo_do_log as _resumo
from _openpyxl_de_verdade import openpyxl_de_verdade
from _pandas_de_verdade import pandas_de_verdade

from sigft.core.excel import travas
from sigft.services import pmib_manager
from sigft.services.pmib_manager import PMIBManager

RAIZ = Path(__file__).resolve().parent.parent
GESTAO_V2 = RAIZ / "gestao-sobressalentes" / "_gestao_v2"
KIT = GESTAO_V2 / "fixtures" / "kit_gestao_pmib"
T1 = "#ST00=TESTE01&MPB020_STATUS_PMIB.xlsx"
T2 = "#ST00=TESTE02&MPB020_STATUS_PMIB.xlsx"
MAPA = "mapeadora_sintetica.xlsx"
HOJE = dt.date(2026, 10, 10)

# O kit tem listas suspensas x14, que o openpyxl avisa (ao LER) que não entende.
pytestmark = pytest.mark.filterwarnings("ignore:Data Validation extension:UserWarning")

precisa_do_kit = pytest.mark.skipif(not (KIT / "esperado.json").is_file(),
                                    reason="kit de teste do cofre ausente (gestao-sobressalentes/)")


@pytest.fixture
def kit(tmp_path):
    pytest.importorskip("lxml")
    destino = tmp_path / "kit"
    shutil.copytree(KIT, destino)
    return destino


def _consumir(gerador):
    linhas = []
    while True:
        try:
            linhas.append(next(gerador))
        except StopIteration as fim:
            return linhas, fim.value


def _validador():
    spec = importlib.util.spec_from_file_location("validar_kit_gestao_pmib", GESTAO_V2 / "validar_kit_gestao_pmib.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def rodar(kit, monkeypatch):
    """Roda o fluxo inteiro sobre o kit, com as bibliotecas de verdade.
    `ao_ver(linha)`: a pessoa agindo no meio do processo."""

    def _rodar(tela=None, ao_ver=None, validar=True):
        log = []
        with openpyxl_de_verdade(pmib_manager) as openpyxl_real, pandas_de_verdade(pmib_manager):
            monkeypatch.setattr(pmib_manager, "openpyxl", openpyxl_real)
            for m in PMIBManager().executar_fluxo(
                    str(kit / "docmanager_sintetico.xlsx"), str(kit / "status"), str(kit / MAPA),
                    hoje=HOJE, callback_travados=tela):
                linha = m if isinstance(m, str) else m[0]
                log.append(linha)
                if ao_ver is not None:
                    ao_ver(linha)
            erros = _validador().validar(kit) if validar else None
        return log, erros

    return _rodar


# ===========================================================================
# A. As peças
# ===========================================================================
@precisa_do_kit
def test_atualizar_autorizacao_com_arquivo_aberto_devolve_a_falha_sem_perguntar(kit, monkeypatch):
    t1 = kit / "status" / T1
    antes = t1.read_bytes()
    excel = ExcelDeMentira(monkeypatch)
    excel.abrir(t1, usuario="Luan")

    with openpyxl_de_verdade():
        linhas, resultado = _consumir(PMIBManager()._atualizar_autorizacao(str(t1), HOJE))

    assert t1.read_bytes() == antes
    assert resultado["gravado"] is False
    assert resultado["falha"].diagnostico.tipo == travas.ABERTO_NO_EXCEL
    assert "por Luan" in resultado["falha"].diagnostico.motivo
    assert resultado["revisao_em_uso"] == "1"  # a leitura aconteceu
    # Durante a etapa, nada de [AVISO]: se o Repetir resolver, não sobra aviso.
    assert not [linha for linha in linhas if "[AVISO]" in linha]
    assert any(T1 in linha and "aberto no Excel" in linha for linha in linhas)


@precisa_do_kit
def test_atualizar_autorizacao_sem_gravar_le_calcula_e_diz_se_tinha_o_que_gravar(kit):
    t1 = kit / "status" / T1
    antes = t1.read_bytes()

    with openpyxl_de_verdade():
        _, resultado = _consumir(PMIBManager()._atualizar_autorizacao(str(t1), HOJE, gravar=False))

    assert t1.read_bytes() == antes
    assert resultado["pendente"] is True  # o kit tem células a recalcular
    assert resultado["revisao_em_uso"] == "1"
    assert resultado["falha"] is None


def test_renomear_arquivo_aberto_no_excel_nao_deixa_copia_com_o_nome_novo(tmp_path, monkeypatch):
    # No Windows, `shutil.move` de um arquivo aberto: o rename falha, ele COPIA
    # para o nome novo, e o apagar do original falha -- sobravam dois.
    antigo = tmp_path / "#ST00=VELHO&MPB020_STATUS_PMIB.xlsx"
    antigo.write_bytes(b"conteudo")
    excel = ExcelDeMentira(monkeypatch)
    excel.abrir(antigo)

    sucesso, _msg, caminho, falha = PMIBManager()._renomear_arquivo_status_pmib(str(antigo), "#ST00=NOVO&MPB020")

    assert sucesso is False and caminho == str(antigo)
    assert sorted(p.name for p in tmp_path.iterdir() if not p.name.startswith("~$")) == [antigo.name]
    assert falha.diagnostico.tipo == travas.ABERTO_NO_EXCEL
    assert "#ST00=NOVO&MPB020_STATUS_PMIB.xlsx" in falha.consequencia


def test_renomear_para_um_nome_que_ja_existe_nao_apaga_o_outro(tmp_path):
    antigo = tmp_path / "#ST00=VELHO&MPB020_STATUS_PMIB.xlsx"
    novo = tmp_path / "#ST00=NOVO&MPB020_STATUS_PMIB.xlsx"
    antigo.write_bytes(b"velho")
    novo.write_bytes(b"novo")

    sucesso, _msg, caminho, falha = PMIBManager()._renomear_arquivo_status_pmib(str(antigo), "#ST00=NOVO&MPB020")

    assert sucesso is False and caminho == str(antigo)
    assert (antigo.read_bytes(), novo.read_bytes()) == (b"velho", b"novo")
    assert falha.diagnostico.tipo == travas.JA_EXISTE


def test_renomear_livre_continua_renomeando(tmp_path):
    antigo = tmp_path / "#ST00=VELHO&MPB020_STATUS_PMIB.xlsx"
    antigo.write_bytes(b"x")

    sucesso, _msg, caminho, falha = PMIBManager()._renomear_arquivo_status_pmib(str(antigo), "#ST00=NOVO&MPB020")

    assert sucesso is True and falha is None
    assert Path(caminho).name == "#ST00=NOVO&MPB020_STATUS_PMIB.xlsx" and Path(caminho).read_bytes() == b"x"


# ===========================================================================
# B. A lista de antes
# ===========================================================================
@precisa_do_kit
def test_travado_antes_repetir_depois_de_fechar_grava_tudo(kit, monkeypatch, rodar):
    t1 = kit / "status" / T1
    excel = ExcelDeMentira(monkeypatch)
    excel.abrir(t1, usuario="Luan")
    tela = _Tela(True, ao_perguntar=lambda momento, falhas: excel.fechar(t1))

    log, erros = rodar(tela)

    assert tela.perguntas == [(travas.ANTES, [(T1, "está aberto no Excel por Luan")])]
    assert erros == [], "\n".join(erros)
    assert not _resumo(log)
    assert not [linha for linha in log if "[ERRO]" in linha or "[AVISO]" in linha]


@precisa_do_kit
def test_travado_antes_seguir_sem_ele_le_mas_nao_grava_e_avisa_no_fim(kit, monkeypatch, rodar):
    t1 = kit / "status" / T1
    antes = t1.read_bytes()
    excel = ExcelDeMentira(monkeypatch)
    excel.abrir(t1)
    tela = _Tela(False)

    log, erros = rodar(tela)

    assert t1.read_bytes() == antes
    # Só o que é do TESTE01 falha no validador: a mapeadora foi gravada, com a
    # revisão e a situação no PMIB lidas do arquivo pulado.
    assert erros and all(erro.startswith("TESTE01") for erro in erros), "\n".join(erros)
    resumo = _resumo(log)
    assert len(resumo) == 2 and "(1)" in resumo[0]
    assert T1 in resumo[1] and "seguiu sem ele" in resumo[1] and "aberto no Excel" in resumo[1]
    assert len(tela.perguntas) == 1  # nada de pergunta no fim da etapa por ele


@precisa_do_kit
def test_seguir_sem_um_arquivo_que_nao_tinha_nada_a_gravar_nao_vira_aviso(kit, monkeypatch, rodar):
    # O TESTE02 é do layout antigo: o Gestão PMIB nunca grava nele. Pulá-lo não
    # perdeu nada, e o resumo do fim não pode acusar o contrário.
    excel = ExcelDeMentira(monkeypatch)
    excel.abrir(kit / "status" / T2)

    log, erros = rodar(_Tela(False))

    assert erros == [], "\n".join(erros)
    assert not _resumo(log)


@precisa_do_kit
def test_pulado_que_nem_abre_aparece_no_resumo_como_nao_lido(kit, monkeypatch, rodar):
    from sigft.core.excel import status_sheet

    t1 = kit / "status" / T1
    excel = ExcelDeMentira(monkeypatch)
    excel.abrir(t1)
    abrir_de_verdade = status_sheet.StatusPMIB.abrir

    def _box_fora_do_ar(self, *args, **kwargs):
        if str(self.caminho_excel) == str(t1):
            raise OSError(5, "Input/output error")
        return abrir_de_verdade(self, *args, **kwargs)

    monkeypatch.setattr(status_sheet.StatusPMIB, "abrir", _box_fora_do_ar)

    log, _ = rodar(_Tela(False), validar=False)

    resumo = _resumo(log)
    assert len(resumo) == 2 and T1 in resumo[1] and "não lido nem gravado" in resumo[1]


@precisa_do_kit
def test_seguir_sem_um_status_que_precisava_de_nome_novo_adia_a_renomeacao(kit, monkeypatch, rodar):
    t1 = kit / "status" / T1
    excel = ExcelDeMentira(monkeypatch)
    excel.abrir(t1)
    monkeypatch.setattr(PMIBManager, "_buscar_rdspp_mais_recente",
                        lambda self, codigo, df: "#ST00=TESTE09&MPB020" if "TESTE01" in codigo else codigo.strip())

    log, _ = rodar(_Tela(False), validar=False)

    assert t1.exists() and not (kit / "status" / "#ST00=TESTE09&MPB020_STATUS_PMIB.xlsx").exists()
    assert any("Renomeação adiada" in linha and T1 in linha for linha in log)


# ===========================================================================
# C. A lista do fim da etapa
# ===========================================================================
@precisa_do_kit
def test_trava_durante_a_etapa_vai_para_a_lista_do_fim_e_repetir_rele_e_grava(kit, monkeypatch, rodar):
    t1 = kit / "status" / T1
    excel = ExcelDeMentira(monkeypatch)
    tela = _Tela(True, ao_perguntar=lambda momento, falhas: excel.fechar(t1))

    # A pessoa abre o arquivo DEPOIS da conferência de antes.
    log, erros = rodar(tela, ao_ver=lambda linha: excel.abrir(t1) if _antes_de_gravar(linha) else None)

    assert tela.perguntas == [(travas.DEPOIS, [(T1, "está aberto no Excel por Luan")])]
    assert erros == [], "\n".join(erros)
    assert any(T1 in linha and "gravado na nova tentativa" in linha for linha in log)
    assert not _resumo(log)
    assert not [linha for linha in log if "[AVISO]" in linha]


@precisa_do_kit
def test_repetir_que_acha_o_arquivo_fora_do_padrao_nao_diz_que_gravou(kit, monkeypatch, rodar):
    # A pessoa fechou o arquivo, mas renomeou a aba antes: a nova tentativa
    # não grava (o [AVISO] da aba sai), e o log não pode dizer "gravado".
    from sigft.core.excel import status_sheet

    t1 = kit / "status" / T1
    excel = ExcelDeMentira(monkeypatch)
    abrir_de_verdade = status_sheet.StatusPMIB.abrir
    aba_renomeada = []

    def _abrir(self, *args, **kwargs):
        if aba_renomeada and str(self.caminho_excel) == str(t1):
            raise KeyError("Lista de Materiais")
        return abrir_de_verdade(self, *args, **kwargs)

    monkeypatch.setattr(status_sheet.StatusPMIB, "abrir", _abrir)
    tela = _Tela(True, ao_perguntar=lambda momento, falhas: (excel.fechar(t1), aba_renomeada.append(1)))

    log, _ = rodar(tela, ao_ver=lambda linha: excel.abrir(t1) if _antes_de_gravar(linha) else None,
                   validar=False)

    assert not [linha for linha in log if "gravado na nova tentativa" in linha]
    assert len(tela.perguntas) == 1  # Repetir não resolve: não volta para a janela
    resumo = _resumo(log)
    assert len(resumo) == 2 and T1 in resumo[1]


@precisa_do_kit
def test_trava_durante_e_seguir_fica_no_resumo_com_o_motivo(kit, monkeypatch, rodar):
    t1 = kit / "status" / T1
    antes = t1.read_bytes()
    excel = ExcelDeMentira(monkeypatch)

    log, _ = rodar(_Tela(False), ao_ver=lambda linha: excel.abrir(t1) if _antes_de_gravar(linha) else None,
                   validar=False)

    assert t1.read_bytes() == antes
    resumo = _resumo(log)
    assert len(resumo) == 2 and T1 in resumo[1]
    assert "situação e dias de atraso não gravados" in resumo[1] and "aberto no Excel" in resumo[1]
    assert any("1 não gravado" in linha for linha in log)  # o resumo da etapa 5 conta


# ===========================================================================
# D. A mapeadora, na hora
# ===========================================================================
def _linha_da_lista(ws, lista):
    cab = {str(c.value).strip(): c.column for c in ws[2] if c.value}
    for r in range(3, ws.max_row + 1):
        if str(ws.cell(r, cab["N° DOCUMENTO ITAIPU"]).value or "").strip() == lista:
            return r, cab
    raise AssertionError(lista)


@precisa_do_kit
def test_mapeadora_travada_na_hora_repetir_rele_e_preserva_o_que_a_pessoa_salvou(kit, monkeypatch, rodar):
    mapa = kit / MAPA
    excel = ExcelDeMentira(monkeypatch)

    def _pessoa_salva_e_fecha(momento, falhas):
        excel.fechar(mapa)
        from openpyxl import load_workbook  # o de verdade: estamos dentro do `rodar`

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            wb = load_workbook(mapa)
        ws = wb["Acompanhamento Sobressalente"]
        r, cab = _linha_da_lista(ws, "#ST00=TESTE01&MPB020")
        ws.cell(r, cab["OBSERVAÇÃO"]).value = "anotação da pessoa"
        wb.save(mapa)

    tela = _Tela(True, ao_perguntar=_pessoa_salva_e_fecha)

    log, erros = rodar(tela, ao_ver=lambda linha: excel.abrir(mapa) if _antes_de_gravar(linha) else None)

    assert [momento for momento, _ in tela.perguntas] == [travas.NA_HORA]
    assert tela.perguntas[0][1][0][1] == "está aberto no Excel por Luan"
    assert erros == [], "\n".join(erros)
    with openpyxl_de_verdade():
        from openpyxl import load_workbook

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ws = load_workbook(mapa)["Acompanhamento Sobressalente"]
        r, cab = _linha_da_lista(ws, "#ST00=TESTE01&MPB020")
        assert ws.cell(r, cab["OBSERVAÇÃO"]).value == "anotação da pessoa"
    assert not _resumo(log)


@precisa_do_kit
def test_mapeadora_travada_na_hora_seguir_sem_ela_grava_os_status_e_pergunta_uma_vez(kit, monkeypatch, rodar):
    mapa = kit / MAPA
    excel = ExcelDeMentira(monkeypatch)
    tela = _Tela(False)
    antes = None

    def _abre_a_mapeadora(linha):
        nonlocal antes
        if _antes_de_gravar(linha):
            antes = mapa.read_bytes()
            excel.abrir(mapa)

    log, erros = rodar(tela, ao_ver=_abre_a_mapeadora)

    assert mapa.read_bytes() == antes
    assert len(tela.perguntas) == 1  # as 4 gravações da mapeadora não perguntam 4 vezes
    assert erros and all(erro.startswith("mapeadora") for erro in erros), "\n".join(erros)
    assert not [linha for linha in log if "[ERRO]" in linha]  # deixou de abortar
    resumo = _resumo(log)
    assert len(resumo) == 2 and "Planilha de mapeamento" in resumo[1]


@precisa_do_kit
def test_mapeadora_travada_antes_seguir_sem_ela_nao_renomeia_nem_pergunta_de_novo(kit, monkeypatch, rodar):
    mapa = kit / MAPA
    antes = mapa.read_bytes()
    excel = ExcelDeMentira(monkeypatch)
    excel.abrir(mapa)
    monkeypatch.setattr(PMIBManager, "_buscar_rdspp_mais_recente",
                        lambda self, codigo, df: "#ST00=TESTE09&MPB020" if "TESTE01" in codigo else codigo.strip())
    tela = _Tela(False)

    log, _ = rodar(tela, validar=False)

    assert mapa.read_bytes() == antes
    assert [momento for momento, _ in tela.perguntas] == [travas.ANTES]
    # Renomear sem gravar a mapeadora quebraria o link "Abrir Box".
    assert (kit / "status" / T1).exists()
    assert any("Renomeação adiada" in linha for linha in log)
    # Os `_STATUS_PMIB` continuam sendo gravados: é o trabalho de todo dia.
    assert any("célula(s) de situação/dias de atraso atualizada(s)" in linha for linha in log)


# ===========================================================================
# E. Sem tela
# ===========================================================================
@precisa_do_kit
def test_sem_callback_nada_pergunta_e_o_resumo_diz_o_que_ficou(kit, monkeypatch, rodar):
    t1 = kit / "status" / T1
    excel = ExcelDeMentira(monkeypatch)

    log, _ = rodar(None, ao_ver=lambda linha: excel.abrir(t1) if _antes_de_gravar(linha) else None,
                   validar=False)

    assert _resumo(log) and T1 in _resumo(log)[1]
    assert log[-1] == "--- PROCESSO CONCLUÍDO ---"


def test_o_callback_antigo_saiu_do_fluxo():
    # Ninguém mais o chama: a pergunta por arquivo, no meio da etapa, era o
    # que o desenho novo tirou.
    import inspect

    assert "callback_retry_lock" not in inspect.signature(PMIBManager.executar_fluxo).parameters
