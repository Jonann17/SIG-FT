"""O diagnóstico do `SIG-FT.exe` (2026-10-20): comparar duas listas diz O QUE mudou.

A leitura do `.exe` precisa do PyInstaller (só o Release o tem); a comparação
é pura e roda em qualquer lugar.
"""
import importlib.util
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("conteudo_do_exe", RAIZ / "tools" / "conteudo_do_exe.py")
conteudo_do_exe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(conteudo_do_exe)


def _lista(cabecalho="c", pkg=None, pyz=None):
    return {"exe": "x", "cabecalho": cabecalho, "pkg": pkg or {}, "pyz": pyz or {}}


def test_iguais_nao_tem_linha():
    a = _lista(pkg={"PYZ.pyz": "1"}, pyz={"json": "2"})
    assert conteudo_do_exe.comparar(a, dict(a)) == []


def test_aponta_o_modulo_que_mudou_entrou_e_saiu():
    velho = _lista(pyz={"json": "1", "numpy": "2", "velho": "3"})
    novo = _lista(pyz={"json": "1", "numpy": "9", "novo": "4"})
    assert conteudo_do_exe.comparar(velho, novo) == [
        "pyz: + novo", "pyz: ~ numpy", "pyz: - velho"]


def test_cabecalho_do_bootloader_tem_linha_propria():
    assert conteudo_do_exe.comparar(_lista("a"), _lista("b")) == [
        "cabecalho (bootloader/recursos PE) mudou"]


def test_o_release_publica_e_compara_o_conteudo():
    yml = (RAIZ / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "tools/conteudo_do_exe.py dist/SIG-FT/SIG-FT.exe" in yml
    assert "conteudo-do-exe.json#" in yml
