"""O passo 7 da Gestão PMIB (aba "Atividades") só grava quando reconhece a aba.

2026-10-19, decisão tomada com a liberdade que o Luan deu ao Jonathan: o passo
7 vira OPCIONAL por si mesmo. Ele escreve por NÚMERO de coluna (`atividades.COL_*`);
numa aba "Atividades" com outro layout, gravaria os totais por cima das
colunas da pessoa. Sem a aba, ou com outro cabeçalho, a gestão segue e o
passo diz por que pulou -- nada é gravado.
"""
from __future__ import annotations

import pytest

from sigft.services import atividades as at
from sigft.services.pmib_manager import PMIBManager
from tests._openpyxl_de_verdade import openpyxl_de_verdade


@pytest.mark.parametrize("cabecalho, reconhece", [
    (("NV", "CÓDIGO ITAIPU", "DESCRIÇÃO"), True),
    (("nv", "  Codigo Itaipu ", "Descricao"), True),          # sem acento, caixa e espaço
    (("Tarefa", "Responsável", "Prazo"), False),
    (("NV", "DESCRIÇÃO", "CÓDIGO ITAIPU"), False),             # colunas trocadas
    ((), False),
])
def test_cabecalho_reconhecido(cabecalho, reconhece):
    assert at.cabecalho_reconhecido(cabecalho) is reconhece


class _Gestao:
    """O pedaço do `PMIBManager` que o passo 7 usa."""

    def __init__(self):
        self.gravou = False

    def _buscar_rdspp_mais_recente(self, codigo, df_api):
        return codigo

    def _gravar_mapeadora(self, wb, caminho):
        self.gravou = True
        wb.save(caminho)


def _mapeadora(caminho, cabecalho, linhas):
    with openpyxl_de_verdade() as openpyxl:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Atividades"
        ws.append(list(cabecalho))
        for linha in linhas:
            ws.append(list(linha))
        wb.save(caminho)
    return caminho


def _rodar(caminho):
    gestao = _Gestao()
    with openpyxl_de_verdade():
        mensagens = list(PMIBManager._atualizar_atividades(gestao, str(caminho), None))
    return gestao, mensagens


def test_aba_com_outro_formato_e_pulada_sem_gravar_nada(tmp_path):
    caminho = _mapeadora(tmp_path / "m.xlsx", ("Tarefa", "Responsável", "Prazo", "Notas"),
                         [("Revisar lista", "Ana", "2026-11-01", "urgente")])
    antes = caminho.read_bytes()

    gestao, mensagens = _rodar(caminho)

    assert not gestao.gravou and caminho.read_bytes() == antes
    assert any("outro formato" in m and "nada foi gravado" in m for m in mensagens), mensagens


def test_aba_reconhecida_continua_recalculando(tmp_path):
    cabecalho = ["NV", "CÓDIGO ITAIPU", "DESCRIÇÃO"] + [""] * (at.COL_CONCLUIDA - 3)
    grupo = [1, "LST-001", "Grupo"] + [None] * (at.COL_CONCLUIDA - 3)
    atividade = [2, None, "Atividade"] + [None] * (at.COL_CONCLUIDA - 3)
    caminho = _mapeadora(tmp_path / "m.xlsx", cabecalho, [grupo, atividade])

    gestao, mensagens = _rodar(caminho)

    assert gestao.gravou
    assert any("grupo(s) recalculado(s)" in m for m in mensagens), mensagens
