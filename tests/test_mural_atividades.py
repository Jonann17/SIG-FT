"""A leitura do mural no mapeamento -- `services/mural_atividades.py`.

Até a E5.1 morava nas duas Homes (interface antiga e Qt), linha a linha: o mesmo
bloco que já teve três defeitos reais (`ws.cell` levando 3,9 s, `data_inicio`
lida em branco, as faixas listadas a mão). Agora as duas Homes DELEGAM para o
serviço (`HomeView._ler_mural` / `_caminho_do_mapeamento`), e a regra se prova
aqui, sem janela nenhuma. (Não em `services/atividades.py`: aquele módulo é a
regra pura, e `test_o_modulo_nao_depende_de_excel` o proíbe de ler planilha.)
"""
import ast
import inspect
import sys
import types
from datetime import date

import pytest

from sigft.services import atividades as at
from sigft.services import mural_atividades as ma

HOJE = date(2026, 10, 9)


class _AbaFalsa:
    def __init__(self, linhas):
        self.linhas = linhas
        self.pedidos = []

    def iter_rows(self, min_row=1, values_only=False):
        self.pedidos.append((min_row, values_only))
        return iter(self.linhas)


class _PastaFalsa:
    def __init__(self, abas):
        self.abas = abas
        self.sheetnames = list(abas)
        self.fechada = False

    def __getitem__(self, nome):
        return self.abas[nome]

    def close(self):
        self.fechada = True


def _openpyxl_falso(monkeypatch, pasta):
    modulo = types.ModuleType("openpyxl")
    modulo.abertos = []

    def load_workbook(caminho, **kw):
        modulo.abertos.append((caminho, kw))
        if isinstance(pasta, Exception):
            raise pasta
        return pasta

    modulo.load_workbook = load_workbook
    monkeypatch.setitem(sys.modules, "openpyxl", modulo)
    return modulo


def test_sem_mapeamento_explica_o_que_fazer():
    gavetas, erro = ma.ler_mural_do_mapeamento(None, HOJE)
    assert gavetas == {f: [] for f in at.FAIXAS}
    assert erro == ("Nao encontrei o arquivo de mapeamento.\n\n"
                    "Rode o PMIB Manager uma vez apontando a planilha gerenciadora -- "
                    "o mural passa a ler dela.")


def test_planilha_sem_a_aba(monkeypatch):
    pasta = _PastaFalsa({"Outra": _AbaFalsa([])})
    _openpyxl_falso(monkeypatch, pasta)
    gavetas, erro = ma.ler_mural_do_mapeamento("/x/mapeamento.xlsx", HOJE)
    assert gavetas == {f: [] for f in at.FAIXAS}
    assert erro == "A planilha nao tem a aba 'Atividades'.\n\n/x/mapeamento.xlsx"
    assert pasta.fechada


def test_le_as_colunas_e_classifica(monkeypatch):
    # As 10 colunas mapeadas, cada uma com um valor diferente: trocar uma coluna
    # por outra no serviço deixa este teste vermelho.
    colunas = {
        "nv": at.COL_NV, "descricao": at.COL_DESCRICAO, "concluida": at.COL_CONCLUIDA,
        "status": at.COL_STATUS, "com_quem": at.COL_COM_QUEM, "criticidade": at.COL_CRITICIDADE,
        "data_prevista_inicio": at.COL_DATA_PREVISTA_INICIO, "previsao_termino": at.COL_PREVISAO_TERMINO,
        "data_inicio": at.COL_DATA_INICIO, "data_termino": at.COL_DATA_TERMINO,
    }
    assert len(set(colunas.values())) == 10
    valores = {"nv": 2, "descricao": "Revisar", "concluida": False, "status": "Em andamento",
               "com_quem": "Luan", "criticidade": 3, "data_prevista_inicio": "2026-09-01",
               "previsao_termino": "2026-10-01", "data_inicio": "2026-09-30", "data_termino": "2026-10-05"}
    linha = [None] * (max(colunas.values()) + 3)
    for campo, coluna in colunas.items():
        linha[coluna - 1] = valores[campo]
    aba = _AbaFalsa([tuple(linha), (1,)])
    pasta = _PastaFalsa({"Atividades": aba})
    modulo = _openpyxl_falso(monkeypatch, pasta)
    recebidas = []
    monkeypatch.setattr(at, "mural", lambda linhas, hoje: recebidas.append((linhas, hoje)) or "GAVETAS")

    gavetas, erro = ma.ler_mural_do_mapeamento("/x/mapeamento.xlsx", HOJE)

    assert (gavetas, erro) == ("GAVETAS", None)
    # `data_only`: as células de agregação são fórmulas; sem ele viria "=FALSE()".
    assert modulo.abertos == [("/x/mapeamento.xlsx", {"data_only": True, "read_only": True})]
    assert aba.pedidos == [(at.LINHA_CABECALHO + 1, True)]
    assert pasta.fechada
    [(linhas, hoje)] = recebidas
    assert hoje == HOJE
    assert linhas[0] == valores, "cada campo vem da sua coluna (a data REAL de início também)"
    # Linha curta não quebra; as datas vazias viram "".
    assert linhas[1]["nv"] == 1 and linhas[1]["descricao"] is None
    assert linhas[1]["data_inicio"] == "" and linhas[1]["data_termino"] == ""


def test_falha_na_leitura_vira_texto(monkeypatch):
    _openpyxl_falso(monkeypatch, PermissionError("travado"))
    gavetas, erro = ma.ler_mural_do_mapeamento("/x/m.xlsx", HOJE)
    assert gavetas == {f: [] for f in at.FAIXAS}
    assert erro == "Nao consegui ler as atividades:\nPermissionError: travado\n\n/x/m.xlsx"


def test_caminho_do_mapeamento(monkeypatch, tmp_path):
    from sigft.core import prefs

    monkeypatch.setattr(prefs, "get_last_file", lambda chave: "/salvo/Mapeamento.xlsx"
                        if chave == prefs.CHAVE_MAPEAMENTO else None)
    assert ma.caminho_do_mapeamento() == "/salvo/Mapeamento.xlsx"

    # Reserva: a pasta lembrada do seletor do PMIB Manager, procurando o arquivo nela.
    monkeypatch.setattr(prefs, "get_last_file", lambda chave: None)
    (tmp_path / "leia-me.txt").write_text("x")
    (tmp_path / "PMIB - Mapeamento geral.xlsm").write_text("x")
    monkeypatch.setattr(prefs, "get_initial_dir", lambda chave, categoria: str(tmp_path)
                        if (chave, categoria) == ("pmib_manager.master", "excel") else None)
    assert ma.caminho_do_mapeamento() == str(tmp_path / "PMIB - Mapeamento geral.xlsm")

    monkeypatch.setattr(prefs, "get_initial_dir", lambda *a: str(tmp_path / "nao-existe"))
    assert ma.caminho_do_mapeamento() is None


def test_preferencia_ilegivel_nao_derruba_o_caminho(monkeypatch):
    from sigft.core import prefs

    def quebra(*_a, **_k):
        raise OSError("user_prefs.json ilegível")

    monkeypatch.setattr(prefs, "get_last_file", quebra)
    monkeypatch.setattr(prefs, "get_initial_dir", quebra)
    assert ma.caminho_do_mapeamento() is None


# =============================================================================
# As duas Homes só DELEGAM (nenhuma lê a planilha)
# =============================================================================

def _home_falsa(caminho):
    return types.SimpleNamespace(_caminho_do_mapeamento=lambda: caminho)


@pytest.mark.parametrize("modulo", ["sigft.app_qt.views.home"])
def test_as_homes_delegam_a_leitura_ao_servico(modulo, monkeypatch):
    import importlib

    home = importlib.import_module(modulo)
    pedidos = []
    monkeypatch.setattr(ma, "ler_mural_do_mapeamento",
                        lambda caminho, hoje: pedidos.append((caminho, hoje)) or ("G", "E"))
    monkeypatch.setattr(ma, "caminho_do_mapeamento", lambda: "/do/servico.xlsx")

    assert home.HomeView._ler_mural(_home_falsa("/da/tela.xlsx")) == ("G", "E")
    assert pedidos == [("/da/tela.xlsx", date.today())]
    assert home.HomeView._caminho_do_mapeamento(object()) == "/do/servico.xlsx"


_PROIBIDAS = {"iter_rows", "load_workbook", "listdir", "get_last_file"}


def _le_planilha(fonte):
    """O que, na fonte, abre planilha ou procura arquivo: o import do openpyxl
    (`import openpyxl`, `import openpyxl.x`, `from openpyxl import ...`) e as
    chamadas proibidas, como atributo (`openpyxl.load_workbook(...)`) ou como
    nome solto (`load_workbook(...)` depois de um `from ... import`)."""
    importados, chamados = set(), set()
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.Import):
            importados.update(a.name.split(".")[0] for a in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module.split(".")[0])
        elif isinstance(no, ast.Call):
            if isinstance(no.func, ast.Attribute):
                chamados.add(no.func.attr)
            elif isinstance(no.func, ast.Name):
                chamados.add(no.func.id)
    return ("openpyxl" in importados), _PROIBIDAS & chamados


@pytest.mark.parametrize("fonte", [
    "import openpyxl\nopenpyxl.load_workbook('m.xlsx')",
    "from openpyxl import load_workbook\nload_workbook('m.xlsx')",
    "import openpyxl.reader.excel as r",
    "from os import listdir\nlistdir('.')",
])
def test_a_guarda_pega_os_jeitos_de_ler_a_planilha(fonte):
    importa, chamadas = _le_planilha(fonte)
    assert importa or chamadas


@pytest.mark.parametrize("modulo", ["sigft.app_qt.views.home"])
def test_as_homes_nao_leem_a_planilha(modulo):
    """Regra de negócio fora da interface (CLAUDE.md, princípio 2): nenhuma das
    duas Homes abre planilha nem procura arquivo -- é tudo do serviço."""
    import importlib

    assert _le_planilha(inspect.getsource(importlib.import_module(modulo))) == (False, set())


def test_pasta_lembrada_sem_permissao_vira_o_texto_amigavel(monkeypatch, tmp_path):
    # `os.listdir` na pasta lembrada levantava PermissionError, que escapava do
    # botão do mural (nas duas Homes) em vez de virar o texto de erro de sempre.
    import os

    from sigft.core import prefs

    monkeypatch.setattr(prefs, "get_last_file", lambda chave: None)
    monkeypatch.setattr(prefs, "get_initial_dir", lambda *a: str(tmp_path))

    def sem_permissao(pasta):
        raise PermissionError(13, "Acesso negado", pasta)

    monkeypatch.setattr(os, "listdir", sem_permissao)
    assert ma.caminho_do_mapeamento() is None
    gavetas, erro = ma.ler_mural_do_mapeamento(ma.caminho_do_mapeamento(), HOJE)
    assert gavetas == {f: [] for f in at.FAIXAS}
    assert erro.startswith("Nao encontrei o arquivo de mapeamento.")
