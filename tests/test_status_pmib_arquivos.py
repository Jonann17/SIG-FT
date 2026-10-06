r"""
Quais `_STATUS_PMIB` são controle VIVO, e a linha da revisão em uso
(`sigft/services/status_pmib_arquivos.py`) -- T3-a e T3-f do roteiro do Gestão
PMIB v2.

O defeito de 05/10/2026 que motivou a T3-a: o `os.walk` do Gestão PMIB entrava
em `testes_autospec/`; para `#ST00=B01BMU10&EPB020` o link "Abrir Box" da
mapeadora apontava para a CÓPIA de teste, e a contagem podia vir dela (a última
encontrada sobrescrevia). As exclusões são as mesmas de
`regras_sobressalentes.py` (cofre), que o painel e o Power BI também usam.

Só stdlib: arquivos vazios bastam -- ninguém abre planilha aqui.
"""
from __future__ import annotations

import os

import pytest

from sigft.services import status_pmib_arquivos as arquivos


# ===========================================================================
# A. Pastas e nomes que não são controle vivo
# ===========================================================================
@pytest.mark.parametrize("relativo", [
    "ELETRICA/testes_autospec/#ST00=B01BMU10&EPB020_STATUS_PMIB.xlsx",
    "00 - OBSOLETO/#ST00=X&MPB020_STATUS_PMIB.xlsx",
    "MECANICA/_obsoleto/#ST00=X&MPB020_STATUS_PMIB.xlsx",
    "10- TESTES/#ST00=X&MPB020_STATUS_PMIB.xlsx",
    "AREA/SISTEMA/DATASHEETS/#ST00=X&MPB020_STATUS_PMIB.xlsx",
    "DATASHEETS/#ST00=X&MPB020_STATUS_PMIB.xlsx",
    "AREA/Backup 2025/#ST00=X&MPB020_STATUS_PMIB.xlsx",
    "AREA/~$#ST00=X&MPB020_STATUS_PMIB.xlsx",
    "AREA/#ST00=X&MPB020_STATUS_PMIB - Copy.xlsx",
    "AREA/#ST00=X&MPB020_STATUS_PMIB - Cópia.xlsx",
    "AREA/copia #ST00=X&MPB020_STATUS_PMIB.xlsx",
    "AREA/#ST00=X&MPB020_STATUS_PMIB comentarios.xlsx",
    "AREA/RESPOSTA #ST00=X&MPB020_STATUS_PMIB.xlsx",
])
def test_o_que_nao_e_controle_vivo_e_ignorado_com_motivo(relativo):
    motivo = arquivos.motivo_para_ignorar(relativo)
    assert motivo, relativo


@pytest.mark.parametrize("relativo", [
    "#ST00=TESTE01&MPB020_STATUS_PMIB.xlsx",
    "ELETRICA/SISTEMA DE EXCITACAO/#ST00=B01BMU10&EPB020_STATUS_PMIB.xlsx",
    # "DATASHEETS" só como PASTA: um nome que contém a palavra não é pasta.
    "AREA/#ST00=DATASHEETSX&MPB020_STATUS_PMIB.xlsx",
])
def test_controle_vivo_nao_e_ignorado(relativo):
    assert arquivos.motivo_para_ignorar(relativo) is None


def test_o_motivo_diz_o_que_casou():
    assert "TESTES_AUTOSPEC" in arquivos.motivo_para_ignorar("A/testes_autospec/x_STATUS_PMIB.xlsx")
    assert "~$" in arquivos.motivo_para_ignorar("A/~$x_STATUS_PMIB.xlsx")


def test_separador_do_windows_tambem_vale():
    assert arquivos.motivo_para_ignorar("ELETRICA\\testes_autospec\\x_STATUS_PMIB.xlsx")


# ===========================================================================
# B. O código da lista no nome do arquivo
# ===========================================================================
@pytest.mark.parametrize("nome, codigo", [
    ("#ST00=TESTE01&MPB020_STATUS_PMIB.xlsx", "#ST00=TESTE01&MPB020"),
    ("#ST00=TESTE01&MPB020_status_pmib.xlsx", "#ST00=TESTE01&MPB020"),
    ("#ST00=B03BDV10UC012-UC001&EPB020_STATUS_PMIB.xls", "#ST00=B03BDV10UC012-UC001&EPB020"),
    ("#ST00=TESTE01&MPB020.xlsx", None),
    ("#ST00=TESTE01&MPB020_STATUS_PMIB.xlsm", None),
    ("_STATUS_PMIB.xlsx", None),
])
def test_codigo_do_arquivo(nome, codigo):
    assert arquivos.codigo_do_arquivo(nome) == codigo


# ===========================================================================
# C. O levantamento da pasta
# ===========================================================================
def _arquivo(raiz, relativo, idade=0):
    caminho = raiz / relativo
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(b"")
    if idade:
        instante = 1_700_000_000 - idade
        os.utime(caminho, (instante, instante))
    return caminho


def test_levantamento_do_kit_ignora_a_isca(tmp_path):
    t1 = _arquivo(tmp_path, "#ST00=TESTE01&MPB020_STATUS_PMIB.xlsx")
    t2 = _arquivo(tmp_path, "#ST00=TESTE02&MPB020_STATUS_PMIB.xlsx")
    isca = _arquivo(tmp_path, "testes_autospec/#ST00=TESTE01&MPB020_STATUS_PMIB.xlsx")
    _arquivo(tmp_path, "outra planilha.xlsx")

    levantado = arquivos.listar(tmp_path)

    assert levantado.vivos == [("#ST00=TESTE01&MPB020", str(t1)), ("#ST00=TESTE02&MPB020", str(t2))]
    assert [c for c, _ in levantado.ignorados] == [str(isca)]
    assert levantado.repetidos == []


def test_dois_vivos_com_o_mesmo_codigo_fica_o_mais_recente_e_avisa(tmp_path):
    antigo = _arquivo(tmp_path, "ELETRICA/#ST00=X&MPB020_STATUS_PMIB.xlsx", idade=3600)
    novo = _arquivo(tmp_path, "ELETRICA/SUB/#ST00=X&MPB020_STATUS_PMIB.xlsx", idade=60)

    levantado = arquivos.listar(tmp_path)

    assert levantado.vivos == [("#ST00=X&MPB020", str(novo))]
    assert levantado.repetidos == [("#ST00=X&MPB020", str(novo), [str(antigo)])]


def test_pasta_inexistente_devolve_vazio(tmp_path):
    levantado = arquivos.listar(tmp_path / "nao_existe")
    assert levantado.vivos == [] and levantado.ignorados == [] and levantado.repetidos == []


# ===========================================================================
# D. A revisão em uso, lida da linha acima do cabeçalho
# ===========================================================================
@pytest.mark.parametrize("texto, revisao", [
    ("REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: 0A - DATA DE ALTERAÇÃO: 03/09/2026", "0A"),
    ("REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: 1 - DATA DE ALTERAÇÃO: —", "1"),
    ("REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: SEM LISTA - DATA DE ALTERAÇÃO: —", "SEM LISTA"),
    ("Revisão da lista de sobressalentes atual em uso:  0B  -  Data de alteração: 01/10/2026", "0B"),
    ("REVISAO DA LISTA DE SOBRESSALENTES ATUAL EM USO: 2 - DATA DE ALTERACAO: 01/10/2026", "2"),
    # sem revisão: não mexer na mapeadora
    ("REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: — - DATA DE ALTERAÇÃO: —", None),
    ("REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO:  - DATA DE ALTERAÇÃO: —", None),
    ("CONTROLE DE FICHAS TÉCNICAS", None),
    ("", None),
    (None, None),
])
def test_revisao_do_texto(texto, revisao):
    assert arquivos.revisao_do_texto(texto) == revisao


def test_revisao_acima_do_cabecalho_procura_pelo_texto_e_nao_pela_coordenada():
    linhas = [
        [None, None],
        ["TEXTO DE TESTE 67", None],
        [None, "REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: 0A - DATA DE ALTERAÇÃO: 03/09/2026"],
        ["ITEM", "DESCRIÇÃO"],  # o cabeçalho (linha 4 deste exemplo)
        [1, "REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: 9 - DATA DE ALTERAÇÃO: x"],  # abaixo: não conta
    ]
    assert arquivos.revisao_acima_do_cabecalho(linhas, linha_cabecalho=4) == "0A"
    assert arquivos.revisao_acima_do_cabecalho(linhas, linha_cabecalho=3) is None
