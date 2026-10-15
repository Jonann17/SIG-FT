"""O aviso de "a interface nao abriu", sem biblioteca grafica nenhuma.

`sigft/core/erro_de_abertura.py` roda quando a Qt nao importou ou nao subiu:
nao ha janela para mostrar o erro, e a interface antiga, que era a saida,
saiu do SIG-FT em 2026-10-15. O aviso usa o que o sistema operacional da:
`MessageBoxW` no Windows, `osascript` no Mac, a saida de erro nos outros. E o
motivo vai para o `sigft.log`.
"""
import sys
import types

import pytest

from sigft.core import erro_de_abertura as ea


def test_registra_motivo_e_pilha_no_sigft_log_da_pasta_de_dados(_isola_os_dados_do_usuario):
    caminho = ea.registrar_no_log("ImportError: sem DLL", "Traceback (pilha)\n")

    assert caminho == str(_isola_os_dados_do_usuario / "logs" / "sigft.log")
    texto = open(caminho, encoding="utf-8").read()
    assert "a interface do SIG-FT nao abriu" in texto
    assert "ImportError: sem DLL" in texto and "Traceback (pilha)" in texto


def test_log_que_nao_grava_nao_impede_o_aviso(monkeypatch):
    monkeypatch.setattr(ea, "caminho_do_log", lambda: (_ for _ in ()).throw(OSError("somente leitura")))

    assert ea.registrar_no_log("motivo") is None
    texto = ea.mensagem("motivo", None)
    assert "motivo" in texto and "Copie esta mensagem" in texto


def test_mensagem_tem_o_motivo_e_o_caminho_do_log():
    texto = ea.mensagem("ImportError: sem DLL", r"C:\Users\x\Documents\SIG-FT\logs\sigft.log")

    assert texto.startswith("O SIG-FT não conseguiu abrir a janela.")
    assert "ImportError: sem DLL" in texto
    assert r"C:\Users\x\Documents\SIG-FT\logs\sigft.log" in texto
    assert "interface antiga" not in texto and "--ctk" not in texto


def test_no_windows_usa_a_messagebox_do_user32(monkeypatch):
    chamadas = []
    user32 = types.SimpleNamespace(MessageBoxW=lambda *a: chamadas.append(a) or 1)
    monkeypatch.setitem(sys.modules, "ctypes",
                        types.SimpleNamespace(windll=types.SimpleNamespace(user32=user32)))

    assert ea.mostrar_caixa("texto", plataforma="win32") == "windows"
    pai, texto, titulo, estilo = chamadas[0]
    assert pai is None and texto == "texto" and titulo == "SIG-FT"
    assert estilo & 0x10, "sem o icone de erro"
    assert estilo & 0x40000, "sem MB_TOPMOST a caixa fica atras da janela preta"


def test_no_mac_usa_o_osascript_com_o_texto_como_argumento():
    rodados = []

    canal = ea.mostrar_caixa('motivo com "aspas" e \\ barra', plataforma="darwin",
                             rodar=lambda cmd, **kw: rodados.append(cmd))

    assert canal == "mac"
    cmd = rodados[0]
    assert cmd[0] == "osascript"
    # O texto vai no argv, inteiro, sem escape: nada dele entra no script.
    assert cmd[-2:] == ["SIG-FT", 'motivo com "aspas" e \\ barra']
    assert "display alert (item 1 of argv) message (item 2 of argv) as critical" in cmd


def test_fora_do_windows_e_do_mac_nao_abre_caixa():
    assert ea.mostrar_caixa("x", plataforma="linux", rodar=lambda *a, **k: pytest.fail("rodou")) == "nenhum"


def test_caixa_que_falha_nao_derruba_o_aviso():
    def quebra(*a, **k):
        raise FileNotFoundError("osascript")

    assert ea.mostrar_caixa("x", plataforma="darwin", rodar=quebra) == "nenhum"


def test_avisar_grava_escreve_na_saida_de_erro_e_mostra(monkeypatch, capsys):
    caixas = []
    monkeypatch.setattr(ea, "mostrar_caixa", lambda texto, **k: caixas.append(texto))

    texto = ea.avisar("RuntimeError: a Qt nao subiu", "Traceback: linha 1")

    assert caixas == [texto]
    erro = capsys.readouterr().err
    assert "Traceback: linha 1" in erro and "RuntimeError: a Qt nao subiu" in erro
    assert ea.caminho_do_log() in texto


def test_sem_saida_de_erro_o_exe_sem_console_nao_quebra(monkeypatch):
    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.setattr(ea, "mostrar_caixa", lambda texto, **k: "nenhum")

    assert "motivo" in ea.avisar("motivo", "pilha")


def test_so_biblioteca_padrao():
    """Roda justamente quando o resto falhou: nada de Qt, nada do resto do
    app (a pasta de dados e stdlib pura)."""
    import ast
    import inspect

    importados = set()
    for no in ast.walk(ast.parse(inspect.getsource(ea))):
        if isinstance(no, ast.Import):
            importados |= {a.name.split(".")[0] for a in no.names}
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module)
    assert importados <= {"__future__", "os", "subprocess", "sys", "time", "ctypes",
                          "sigft.core.dados_usuario"}, importados
