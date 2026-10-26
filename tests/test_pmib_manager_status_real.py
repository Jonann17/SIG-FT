"""O Gestão PMIB grava o STATUS REAL da mapeadora pela batalha de versões do DocManager.

Desenho: `docs/superpowers/specs/2026-10-26-aconex-ao-vivo-design.md`, §4.4. O valor
é o status real, sem o consolidado: Aprovado, Aprovado com Comentários, Para
Assinatura, Em Processo... Até 26/10/2026 a coluna era digitada à mão e o Gestão
PMIB nunca a tocava; agora toda mudança aparece no log, com o antes e o depois.
"""
from __future__ import annotations

import pytest

from _historico_aconex import HistoricoBuilder, base, motor_com_pandas_real
from _openpyxl_de_verdade import openpyxl_de_verdade
from sigft.services import pmib_manager
from sigft.services.pmib_manager import PMIBManager

pytest.importorskip("pandas")
pytest.importorskip("openpyxl")

CABECALHO = ["N° DOCUMENTO ITAIPU", "DESCRIÇÃO", "ÚLTIMA REVISÃO EMITIDA", "STATUS DA REVISÃO", "STATUS REAL"]
CODIGO = "#ITA0=Y01TF001&BPB020"


def _rodar(tmp_path, linhas, *historicos, cabecalho=CABECALHO):
    """Monta a mapeadora (`linhas` = [(código, STATUS REAL digitado)]), roda a etapa 4
    sobre o histórico dos `historicos` e devolve (STATUS REAL por linha, log)."""
    caminho = tmp_path / "mapeadora.xlsx"
    with openpyxl_de_verdade(pmib_manager) as openpyxl_real, motor_com_pandas_real(pmib_manager):
        livro = openpyxl_real.Workbook()
        aba = livro.active
        aba.title = pmib_manager.NOME_ABA_SOBRESSALENTES
        aba.append(["MAPEAMENTO DAS LISTAS"])
        aba.append(cabecalho)
        for codigo, digitado in linhas:
            aba.append([{"N° DOCUMENTO ITAIPU": codigo, "STATUS REAL": digitado}.get(c) for c in cabecalho])
        livro.save(caminho)

        df_api = base(*historicos)
        df_api["Current"] = df_api["Current"].astype(str).str.lower() == "true"
        log = [m if isinstance(m, str) else m[0]
               for m in PMIBManager()._atualizar_mapeamento(str(caminho), df_api, None, {})]

        aba = openpyxl_real.load_workbook(caminho)[pmib_manager.NOME_ABA_SOBRESSALENTES]
        cab = [c.value for c in aba[2]]
        sr = cab.index("STATUS REAL") + 1 if "STATUS REAL" in cab else None
        codigos = [aba.cell(r, 1).value for r in range(3, aba.max_row + 1)]
        valores = {c: (aba.cell(r, sr).value if sr else None) for r, c in zip(range(3, aba.max_row + 1), codigos)}
    return valores, log


def _h(tracking="T1", doc=CODIGO):
    return HistoricoBuilder(tracking, doc, "CMI-1", titulo="LISTA GENERICA")


def test_status_real_gravado_pela_batalha(tmp_path):
    h = (_h().evento("0", 1, "Aprovado", "01/03/2026").evento("0A", 1, "Aprovado", "01/05/2026")
         .evento("0B", 1, "Em Processo", "01/09/2026", current=True))
    valores, _log = _rodar(tmp_path, [(CODIGO, None)], h)
    assert valores == {CODIGO: "Aprovado"}


def test_status_real_loga_antes_e_depois(tmp_path):
    h = _h().evento("0A", 1, "Aprovado", "01/05/2026", current=True)
    valores, log = _rodar(tmp_path, [(CODIGO, "APROVADO")], h)
    assert valores == {CODIGO: "Aprovado"}
    assert any(f"STATUS REAL de {CODIGO}: APROVADO → Aprovado" in linha for linha in log)


def test_status_real_igual_nao_loga(tmp_path):
    h = _h().evento("0", 1, "Para Assinatura", "01/05/2026", current=True)
    valores, log = _rodar(tmp_path, [(CODIGO, "Para Assinatura")], h)
    assert valores == {CODIGO: "Para Assinatura"}
    assert not any("STATUS REAL de" in linha for linha in log)


def test_status_real_sem_coluna_avisa_uma_vez(tmp_path):
    outro = "#ITA0=Y01TF002&BPB020"
    h1 = _h().evento("0", 1, "Aprovado", "01/05/2026", current=True)
    h2 = _h("T2", outro).evento("0", 1, "Aprovado", "01/05/2026", current=True)
    sem_coluna = [c for c in CABECALHO if c != "STATUS REAL"]
    _valores, log = _rodar(tmp_path, [(CODIGO, None), (outro, None)], h1, h2, cabecalho=sem_coluna)
    avisos = [linha for linha in log if "Coluna 'STATUS REAL' não encontrada" in linha]
    assert len(avisos) == 1


def test_status_real_codigo_fora_do_historico_nao_muda(tmp_path):
    h = _h().evento("0", 1, "Aprovado", "01/05/2026", current=True)
    valores, log = _rodar(tmp_path, [(CODIGO, None), ("SEM LISTA", "SEM LISTA")], h)
    assert valores == {CODIGO: "Aprovado", "SEM LISTA": "SEM LISTA"}
    assert any("STATUS REAL de SEM LISTA: fora do histórico do Aconex, não mudou." in linha for linha in log)


def test_status_real_segue_o_tracking_id_quando_o_codigo_muda(tmp_path):
    novo = "#ITA0=Y01TF009&BPB020"
    h = (_h().evento("0", 1, "Aprovado", "01/03/2026")
         .evento("0A", 1, "Em Processo", "01/09/2026", current=True, doc=novo))
    valores, _log = _rodar(tmp_path, [(CODIGO, None)], h)
    # o código vira o novo (como já era) e o status olha o histórico inteiro do Tracking ID
    assert valores == {novo: "Aprovado"}


def test_status_real_historico_sem_as_colunas_da_batalha_avisa_e_segue(tmp_path, monkeypatch):
    """Um histórico sem 'Versão' (o extrato sintético do kit, por exemplo) não
    derruba a etapa: os metadados são gravados, o STATUS REAL fica como estava e
    um aviso diz o que faltou."""
    h = _h().evento("0A", 1, "Aprovado", "01/05/2026", current=True)
    original = pmib_manager.PMIBManager._atualizar_mapeamento

    def sem_versao(self, caminho, df_api, *args):
        return original(self, caminho, df_api.drop(columns=["Versão"]), *args)

    monkeypatch.setattr(pmib_manager.PMIBManager, "_atualizar_mapeamento", sem_versao)
    valores, log = _rodar(tmp_path, [(CODIGO, "APROVADO")], h)
    assert valores == {CODIGO: "APROVADO"}
    avisos = [linha for linha in log if linha.startswith("[AVISO]") and "Versão" in linha]
    assert len(avisos) == 1
    assert any("Metadados atualizados (1 linhas)" in linha for linha in log)
