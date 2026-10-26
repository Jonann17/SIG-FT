"""Lista nova só com PB020 no código (pedido do Luan, 26/10/2026).

Começaram a aparecer como "lista nova" planilhas de comissionamento com
SOBRESSALENTES no título. A regra passa a ser: código com PB020, título com
SOBRESSALENTES e sem PREÇO/PREÇOS (sem acento também). O teste do `-01` sai: a
lista do SMF (`...PB020-01`) é de sobressalentes e era barrada por engano
(pendência de 2026-09-03). Desenho: `docs/superpowers/specs/2026-10-26-aconex-ao-vivo-design.md`, §4.3.
"""
from __future__ import annotations

import pytest

from sigft.services.pmib_manager import e_lista_de_sobressalentes


@pytest.mark.parametrize("codigo, titulo, esperado", [
    ("#ITA0=Y01TF001&BPB020", "LISTA DE SOBRESSALENTES - RTA", True),
    ("#ITA0=A01AAM10&EPB020-01", "LISTA DE SOBRESSALENTES - SMF", True),        # o -01 não barra mais
    ("#ST00=X01ABC10&EPB020-01", "LISTA DE PREÇOS DE SOBRESSALENTES", False),
    ("#ST00=X01ABC10&EPB020-02", "LISTA DE PRECOS DE SOBRESSALENTES", False),   # sem acento
    ("#ST00=X01ABC10&MCM001", "PLANILHA DE COMISSIONAMENTO - SOBRESSALENTES", False),
    ("#ST00=X01ABC10&MPB021", "LISTA DE PREÇOS DE SOBRESSALENTES", False),
    ("#ST00=X01ABC10&mpb020", "Lista de Sobressalentes", True),                 # caixa não importa
    ("#ST00=X01ABC10&MPB020", "LISTA DE MATERIAIS", False),                     # sem SOBRESSALENTES
    (None, None, False)])
def test_e_lista_de_sobressalentes(codigo, titulo, esperado):
    assert e_lista_de_sobressalentes(codigo, titulo) is esperado


def test_so_a_lista_com_pb020_e_oferecida_como_nova(tmp_path):
    """Pelo fluxo da etapa 4: a planilha de comissionamento e a lista de preços
    não chegam à janela de listas novas; a lista do SMF (`-01`) chega."""
    pytest.importorskip("pandas")
    pytest.importorskip("openpyxl")
    from _historico_aconex import HistoricoBuilder, base, motor_com_pandas_real
    from _openpyxl_de_verdade import openpyxl_de_verdade
    from sigft.services import pmib_manager

    existente = "#ITA0=Y01TF001&BPB020"
    historico = [
        HistoricoBuilder("T1", existente, "C1", titulo="LISTA DE SOBRESSALENTES - RTA"),
        HistoricoBuilder("T2", "#ITA0=A01AAM10&EPB020-01", "C2", titulo="LISTA DE SOBRESSALENTES - SMF"),
        HistoricoBuilder("T3", "#ST00=X01ABC10&MCM001", "C3", titulo="PLANILHA DE COMISSIONAMENTO - SOBRESSALENTES"),
        HistoricoBuilder("T4", "#ST00=X01ABC10&EPB020-02", "C4", titulo="LISTA DE PREÇOS DE SOBRESSALENTES"),
    ]
    for h in historico:
        h.evento("0", 1, "Aprovado", "01/09/2026", current=True)
    oferecidas = []

    def confirmar(df_novos):
        oferecidas.extend(df_novos["No. do Documento"])
        return df_novos.iloc[0:0]

    caminho = tmp_path / "mapeadora.xlsx"
    with openpyxl_de_verdade(pmib_manager) as openpyxl_real, motor_com_pandas_real(pmib_manager):
        livro = openpyxl_real.Workbook()
        aba = livro.active
        aba.title = pmib_manager.NOME_ABA_SOBRESSALENTES
        aba.append(["MAPEAMENTO DAS LISTAS"])
        aba.append(["N° DOCUMENTO ITAIPU", "DESCRIÇÃO", "STATUS REAL"])
        aba.append([existente, None, None])
        livro.save(caminho)
        df_api = base(*historico)
        df_api["Current"] = df_api["Current"].astype(str).str.lower() == "true"
        list(pmib_manager.PMIBManager()._atualizar_mapeamento(str(caminho), df_api, confirmar, {}))

    assert oferecidas == ["#ITA0=A01AAM10&EPB020-01"]
