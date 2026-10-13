"""A leitura do mural no mapeamento -- `services/mural_atividades.py`.

Até a E5.1 morava nas duas Homes (CustomTkinter e Qt), linha a linha: o mesmo
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
    linha = [None] * 16
    linha[at.COL_NV - 1] = 2
    linha[at.COL_DESCRICAO - 1] = "Revisar"
    linha[at.COL_STATUS - 1] = "Em andamento"
    linha[at.COL_PREVISAO_TERMINO - 1] = "2026-10-01"
    linha[at.COL_DATA_INICIO - 1] = "2026-09-30"
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
    assert linhas[0]["descricao"] == "Revisar" and linhas[0]["status"] == "Em andamento"
    assert linhas[0]["previsao_termino"] == "2026-10-01"
    assert linhas[0]["data_inicio"] == "2026-09-30", "a data REAL de início não pode vir em branco"
    assert linhas[0]["data_termino"] == "" and linhas[0]["data_prevista_inicio"] == ""
    assert linhas[1]["nv"] == 1 and linhas[1]["descricao"] is None  # linha curta não quebra


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


@pytest.mark.parametrize("modulo", ["sigft.app.views.home", "sigft.app_qt.views.home"])
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


@pytest.mark.parametrize("modulo", ["sigft.app.views.home", "sigft.app_qt.views.home"])
def test_as_homes_nao_leem_a_planilha(modulo):
    """Regra de negócio fora da interface (CLAUDE.md, princípio 2): nenhuma das
    duas Homes abre planilha nem procura arquivo -- é tudo do serviço."""
    import importlib

    fonte = inspect.getsource(importlib.import_module(modulo))
    arvore = ast.parse(fonte)
    importados = {alias.name for no in ast.walk(arvore) if isinstance(no, (ast.Import, ast.ImportFrom))
                  for alias in no.names}
    chamados = {no.func.attr for no in ast.walk(arvore)
                if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)}
    assert "openpyxl" not in importados
    assert not {"iter_rows", "load_workbook", "listdir", "get_last_file"} & chamados
