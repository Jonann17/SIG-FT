"""`sigft.core.saida_log`: sem console, o `print` do .exe vai para o sigft.log."""
import sys

from sigft.core import dados_usuario, saida_log


def test_fora_do_exe_nao_mexe_em_nada(monkeypatch, tmp_path):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(dados_usuario, "pasta_logs", lambda: tmp_path)
    saida_log.desviar_saida_para_arquivo()
    assert sys.stdout is None
    assert not (tmp_path / "sigft.log").exists()


def test_exe_com_console_nao_mexe_em_nada(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(dados_usuario, "pasta_logs", lambda: tmp_path)
    antes = (sys.stdout, sys.stderr)
    saida_log.desviar_saida_para_arquivo()
    assert (sys.stdout, sys.stderr) == antes
    assert not (tmp_path / "sigft.log").exists()


def test_exe_sem_console_grava_no_log(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.setattr(dados_usuario, "pasta_logs", lambda: tmp_path)
    saida_log.desviar_saida_para_arquivo()
    try:
        assert sys.stdout is not None and sys.stderr is sys.stdout
        print("linha de teste")
        sys.stdout.flush()
    finally:
        arquivo = sys.stdout
        sys.stdout = sys.stderr = None  # o monkeypatch restaura depois
        if arquivo is not None:
            arquivo.close()
    texto = (tmp_path / "sigft.log").read_text(encoding="utf-8")
    assert "===== SIG-FT iniciado em" in texto
    assert "linha de teste" in texto


def test_nunca_levanta_se_nao_da_para_abrir_o_log(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    def quebra():
        raise OSError("disco cheio")

    monkeypatch.setattr(dados_usuario, "pasta_logs", quebra)
    saida_log.desviar_saida_para_arquivo()  # nao levanta
    assert sys.stdout is None


def test_modulo_nao_importa_interface():
    import ast
    from pathlib import Path

    arvore = ast.parse(Path(saida_log.__file__).read_text(encoding="utf-8"))
    nomes = {n.module if isinstance(n, ast.ImportFrom) else a.name
             for n in ast.walk(arvore) if isinstance(n, (ast.Import, ast.ImportFrom))
             for a in (n.names if isinstance(n, ast.Import) else [n])}
    assert not any(n and n.split(".")[0] in {"tkinter", "customtkinter", "PySide6"}
                   for n in nomes)
