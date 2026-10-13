import os

from PySide6.QtWidgets import QFileDialog

from sigft.app_qt import file_dialogs as fd


def test_filtro_tk_vira_filtro_qt():
    assert fd.filtro_qt([("Excel", "*.xlsx;*.xlsm")]) == "Excel (*.xlsx *.xlsm)"
    assert fd.filtro_qt([("Excel", "*.xlsx *.xlsm"), ("PDF", "*.pdf")]) == \
        "Excel (*.xlsx *.xlsm);;PDF (*.pdf)"
    assert fd.filtro_qt(None) == ""


def test_abrir_um_lembra_a_pasta(qt_interface, tmp_path, monkeypatch):
    escolhido = tmp_path / "a" / "ficha.xlsx"
    escolhido.parent.mkdir()
    escolhido.write_text("x")
    chamadas = []

    def falso(parent, titulo, pasta, filtro):
        chamadas.append((titulo, filtro))
        return str(escolhido), filtro

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(falso))
    config = tmp_path / "prefs.json"
    caminho = fd.ask_open_file("lmr.excel", "excel", titulo="Selecione", filetypes=[("Excel", "*.xlsx")],
                               config_path=config)
    assert caminho == str(escolhido)
    assert chamadas == [("Selecione", "Excel (*.xlsx)")]
    # a memória de pastas é a de sempre (sigft.core.prefs)
    from sigft.core import prefs
    assert prefs.get_initial_dir("lmr.excel", "excel", config_path=config) == str(escolhido.parent)


def test_cancelar_devolve_vazio(qt_interface, monkeypatch, tmp_path):
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", staticmethod(lambda *a: ([], "")))
    assert fd.ask_open_files("x", "excel", config_path=tmp_path / "p.json") == ()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a: ""))
    assert fd.ask_directory("x", "pasta", config_path=tmp_path / "p.json") == ""


def test_salvar_acrescenta_extensao(qt_interface, monkeypatch, tmp_path):
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a: (os.path.join(str(tmp_path), "relatorio"), "")))
    assert fd.ask_save_file("x", "excel", defaultextension=".xlsx",
                            config_path=tmp_path / "p.json").endswith("relatorio.xlsx")
