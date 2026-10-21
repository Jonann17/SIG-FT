"""Arquivo entregue sem diálogo: o caminho do arrastar e dos recentes (2026-10-21)."""
import pytest

from sigft.app import file_dialogs
from sigft.core import prefs


def _nao_abre(**_):
    raise AssertionError("o diálogo não devia abrir")


@pytest.fixture
def config_path(tmp_path):
    return tmp_path / "user_prefs.json"


def test_entregue_volta_sem_dialogo_e_vira_recente(tmp_path, config_path):
    arquivo = tmp_path / "STATUS.xlsx"
    arquivo.write_text("x", encoding="utf-8")
    file_dialogs.entregar("k", [str(arquivo)])
    assert file_dialogs.ask_open_file("k", "excel", dialog_fn=_nao_abre, config_path=config_path) == str(arquivo)
    assert prefs.recentes("k", config_path=config_path) == [str(arquivo)]
    assert prefs.get_initial_dir("k", "excel", config_path=config_path) == str(tmp_path)
    # a entrega vale UMA vez
    assert file_dialogs.pendente("k") is None
    assert file_dialogs.ask_open_file("k", "excel", dialog_fn=lambda **_: "", config_path=config_path) == ""


def test_entrega_de_uma_chave_nao_vale_para_outra(config_path):
    file_dialogs.entregar("a", ["/x.xlsx"])
    try:
        assert file_dialogs.ask_open_file("b", "excel", dialog_fn=lambda **_: "", config_path=config_path) == ""
        assert file_dialogs.pendente("a") == ("/x.xlsx",)
    finally:
        file_dialogs.descartar("a")
    assert file_dialogs.pendente("a") is None


def test_varios_entregues_e_recentes_na_ordem(tmp_path, config_path):
    a, b = tmp_path / "a.xlsx", tmp_path / "b.xlsx"
    for p in (a, b):
        p.write_text("x", encoding="utf-8")
    file_dialogs.entregar("k", [str(a), str(b)])
    assert file_dialogs.ask_open_files("k", "excel", dialog_fn=_nao_abre, config_path=config_path) == (str(a), str(b))
    assert prefs.recentes("k", config_path=config_path) == [str(a), str(b)]


def test_escolha_pelo_dialogo_tambem_vira_recente(tmp_path, config_path):
    arquivo = tmp_path / "a.xlsx"
    arquivo.write_text("x", encoding="utf-8")
    file_dialogs.ask_open_file("k", "excel", dialog_fn=lambda **_: str(arquivo), config_path=config_path)
    assert prefs.recentes("k", config_path=config_path) == [str(arquivo)]


@pytest.mark.parametrize("filetypes, esperado", [
    ([("Excel", "*.xlsx;*.xlsm")], (".xlsx", ".xlsm")),
    ([("Excel", "*.xlsx *.xls")], (".xlsx", ".xls")),
    ([("Docs", "*.pdf *.txt")], (".pdf", ".txt")),
    ([("Texto", "*.txt"), ("Todos", "*.*")], None),
    (None, None),
])
def test_extensoes_de(filetypes, esperado):
    assert file_dialogs.extensoes_de(filetypes) == esperado


def test_extensao_aceita():
    assert file_dialogs.extensao_aceita("C:/pasta/STATUS.XLSX", (".xlsx",))
    assert not file_dialogs.extensao_aceita("manual.pdf", (".xlsx", ".xlsm"))
    assert file_dialogs.extensao_aceita("qualquer.bin", None)
