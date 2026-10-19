# -*- coding: utf-8 -*-
"""As duas conferencias que o proprio `.exe` faz de si mesmo, no CI.

Vieram do dossie do Corella Suite, e resolvem um problema que o CLAUDE.md
deste projeto ja nomeava sem ter solucao:

    "Editou frontend.py? ABRA O APP antes de dizer que esta pronto."

Em 2026-08-25 o CP 5.5 removeu um frame e deixou um widget filho para tras.
`compileall` passou, os 2625 testes passaram, e o app morria na abertura com
`NameError: name 'f_novo' is not defined`. A unica coisa que teria pego era
abrir a janela -- e nenhuma maquina de CI em Linux pode fazer isso.

O workflow de Release roda no WINDOWS. La o `.exe` recem-compilado pode se
abrir e responder duas perguntas:

  --smoke            a janela monta? (pega o widget orfao, o import que sumiu
                     no bundle, o tema que nao carrega)
  --conferir-pacote  o bundle consegue IMPORTAR o que o app precisa?

ARMADILHA que o Corella documentou e que vale para o SIG-FT tambem: o
`SIG-FT.spec` usa `console=False`. Um `.exe` sem console NAO se prende ao
terminal -- nem a saida nem o codigo de saida chegam por uma chamada direta do
PowerShell. Por isso `--conferir-pacote` GRAVA UM ARQUIVO, e o workflow o le.

E a outra, medida no Corella: modulo Python puro NAO vira pasta em `_internal/`.
O PyInstaller so deixa la o que tem extensao binaria ou arquivo de dados; o
resto vai para dentro do PYZ. Uma conferencia que procurasse `_internal/requests`
reprovaria um build perfeitamente bom. A pergunta certa nunca foi "o arquivo
esta la?", e sim "o aplicativo consegue importar?".
"""
import ast
import pathlib
import subprocess
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
MAIN = RAIZ / "sigft" / "app_qt" / "main.py"
CONFERENCIA = RAIZ / "sigft" / "app" / "conferencia.py"


# =============================================================================
# A. As flags existem e sao tratadas ANTES de a janela abrir
# =============================================================================

# ATENCAO -- aqui havia dois testes, e os dois davam verde com o defeito dentro:
#
#     def test_o_main_trata_a_flag_smoke():
#         assert "--smoke" in MAIN.read_text(...)
#
#     def test_o_main_trata_a_flag_conferir_pacote():
#         assert "--conferir-pacote" in MAIN.read_text(...)
#
# Dois problemas, e cada um bastava para deixar passar o que passou em
# 2026-09-21:
#
# 1. mediam o `main.py` da interface (na epoca, `sigft/app/main.py`), e o
#    bundle NAO roda aquele arquivo -- o
#    `SIG-FT.spec` empacota o `frontend.py`. As flags estavam tratadas no
#    lugar certo do arquivo errado;
# 2. mediam TEXTO. Um `--smoke` citado num comentario satisfaz o `in fonte`
#    tao bem quanto um tratado de verdade. (E foi o que sobrou: depois do
#    conserto, `main.py` ainda menciona a flag em comentario, e os dois
#    continuariam verdes sem tratar nada.)
#
# Sairam daqui em favor de `tests/test_ponto_de_entrada.py`, que le o script do
# `Analysis(...)` do spec, RODA aquele script com a flag e exige resposta. Foi
# a quarta vez nesta frente que um guard mediu a coisa ao lado da coisa.


def test_a_conferencia_nao_importa_nada_pesado():
    """O defeito de desenho que o proprio teste achou.

    A primeira versao disto morava no `main.py` da interface, que importava a
    biblioteca grafica e as 12 telas no topo. Rodar `--conferir-pacote` por la
    significava pagar todos esses imports ANTES de conseguir relatar qualquer
    coisa -- ou seja, num bundle quebrado a conferencia quebrava junto, e o
    passo do CI morria com um traceback em vez de dizer o que faltava.

    Era o contrario do que ela existe para fazer.
    """
    arvore = ast.parse(CONFERENCIA.read_text(encoding="utf-8"))
    # (A Qt fica de fora da lista de proposito: `conferir_qt` a importa DENTRO
    # da funcao, e o que falhar vira linha de FALHA no relatorio.)
    pesados = {"PIL", "pandas", "openpyxl", "playwright", "requests"}

    for no in ast.walk(arvore):
        nomes = []
        if isinstance(no, ast.Import):
            nomes = [a.name.split(".")[0] for a in no.names]
        elif isinstance(no, ast.ImportFrom):
            nomes = [(no.module or "").split(".")[0]]
        for nome in nomes:
            assert nome not in pesados, (
                f"conferencia.py importa `{nome}` -- ela tem de funcionar num "
                f"bundle INCOMPLETO, que e quando ela e util"
            )


def test_a_conferencia_GRAVA_arquivo_e_nao_so_imprime():
    """A armadilha do `console=False`.

    Um `.exe` sem console nao devolve saida nem codigo de saida por uma chamada
    direta do PowerShell. Se a conferencia so imprimisse, o workflow nao teria
    como ler o resultado -- e o passo passaria sempre.
    """
    assert "conferencia-do-pacote.txt" in CONFERENCIA.read_text(encoding="utf-8")


def test_o_spec_continua_sem_console():
    """Se um dia o `.exe` ganhar console, a gravacao em arquivo deixa de ser
    necessaria -- mas ate la ela e a unica via."""
    spec = (RAIZ / "SIG-FT.spec").read_text(encoding="utf-8")

    assert "console=False" in spec.replace(" ", "")


# =============================================================================
# B. A conferencia usa `find_spec`, nao `importlib.metadata`
# =============================================================================

def test_a_conferencia_nao_usa_importlib_metadata():
    """O caso REAL do Corella: o usuario instalou a v1.0.0 e o diagnostico
    dizia "pandas: nao instalado".

    `importlib.metadata` nao viaja para dentro do `.exe`: o `.dist-info` so
    entra se alguem pedir (`copy_metadata` no .spec), entao `version("pandas")`
    levanta `PackageNotFoundError` mesmo com o pandas funcionando. Para
    perguntar "esta instalado?", `importlib.util.find_spec` -- que tambem nao
    IMPORTA o modulo, o que importa num app que nao pode carregar o pandas so
    para conferir.
    """
    fonte = CONFERENCIA.read_text(encoding="utf-8")
    arvore = ast.parse(fonte)

    # Via AST, e nao por busca de texto: o modulo EXPLICA no docstring por que
    # nao usa `importlib.metadata` -- e deve mesmo, e o que impede alguem de
    # reintroduzir. Uma busca por substring reprovaria a explicacao.
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            for alias in no.names:
                assert not alias.name.startswith("importlib.metadata"), (
                    "ver o docstring: metadata nao viaja para dentro do .exe"
                )
        if isinstance(no, ast.ImportFrom):
            assert not (no.module or "").startswith("importlib.metadata"), (
                "ver o docstring: metadata nao viaja para dentro do .exe"
            )

    assert "find_spec" in fonte


# =============================================================================
# C. As flags funcionam DE VERDADE, rodando o processo
# =============================================================================
#
# Aqui nao ha .exe: estes testes rodam `python -m sigft.app_qt.main --flag` num
# subprocesso. Isso prova o CAMINHO DE CODIGO das flags -- o parsing, o codigo
# de saida, o arquivo gravado. O que so o Windows prova e que a janela monta de
# verdade dentro do bundle.

def _rodar(*flags, cwd=None):
    """Roda `python -m sigft.app_qt.main <flags>` e devolve o resultado.

    `cwd` e o diretorio de TRABALHO, e ele importa: a conferencia grava o
    relatorio nele, e o teste precisa que isso caia num `tmp_path` e nao na
    raiz do repositorio.
    """
    import os

    ambiente = dict(os.environ, PYTHONPATH=str(RAIZ))
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "sigft.app_qt.main", *flags],
        cwd=str(cwd or RAIZ), env=ambiente,
        capture_output=True, text=True, timeout=120)


def test_conferir_pacote_grava_o_arquivo_e_sai_com_codigo(tmp_path):
    """O contrato que o workflow consome: arquivo + codigo de saida."""
    resultado = _rodar("--conferir-pacote", cwd=tmp_path)

    assert (tmp_path / "conferencia-do-pacote.txt").is_file(), (
        f"o arquivo nao foi gravado.\nstdout: {resultado.stdout}\n"
        f"stderr: {resultado.stderr}"
    )
    relatorio = (tmp_path / "conferencia-do-pacote.txt").read_text(encoding="utf-8")
    assert "sigft" in relatorio.lower()


def test_conferir_pacote_REPROVA_quando_falta_modulo(tmp_path, monkeypatch):
    """O teste que prova que a conferencia nao passa sempre.

    Uma conferencia que nunca reprova e pior que nenhuma: ela da a impressao
    de estar protegendo.
    """
    from sigft.app import conferencia

    relatorio, ok = conferencia.conferir_pacote(
        modulos=["sigft.config", "um_modulo_que_nao_existe_de_jeito_nenhum"])

    assert ok is False
    assert "um_modulo_que_nao_existe_de_jeito_nenhum" in relatorio


def test_conferir_pacote_APROVA_quando_esta_tudo_la():
    from sigft.app import conferencia

    relatorio, ok = conferencia.conferir_pacote(modulos=["sigft.config", "json", "os"])

    assert ok is True
    assert "json" in relatorio


def test_a_lista_padrao_cobre_o_que_o_app_precisa():
    """Os modulos que, faltando no bundle, derrubam o app no uso -- nao na
    abertura. E o caso mais caro: a pessoa descobre no meio do trabalho."""
    from sigft.app import conferencia

    padrao = " ".join(conferencia.MODULOS_ESSENCIAIS)

    for essencial in ("pandas", "openpyxl", "playwright", "requests", "sigft.config"):
        assert essencial in padrao, f"{essencial} nao esta na conferencia do pacote"


# =============================================================================
# O tradutor local DENTRO do pacote (2026-09-25)
# =============================================================================
# `find_spec` diz que o `ctranslate2` está lá; não diz se a DLL dele carrega
# nem se o modelo (218 MB, `modelos/tradutor_pt_es`) entrou no pacote. A
# conferência traduz uma frase de verdade dentro do .exe: se falhar, o
# release para ANTES de publicar um tradutor que não traduz.
class _TradutorQueResponde:
    def __init__(self, saida):
        self.saida = saida

    def __call__(self, pasta):
        self.pasta = pasta
        return self

    def traduzir(self, textos):
        return [self.saida for _ in textos]


def test_a_conferencia_traduz_uma_frase_com_o_modelo_do_pacote(monkeypatch, tmp_path):
    from sigft.app import conferencia
    from sigft.core import tradutor_local

    monkeypatch.setattr(tradutor_local, "localizar_modelo", lambda: tmp_path)
    monkeypatch.setattr(tradutor_local, "TradutorLocal", _TradutorQueResponde("Acero inoxidable"))

    relatorio, ok = conferencia.conferir_tradutor()

    assert ok is True
    assert "Acero inoxidable" in relatorio and str(tmp_path) in relatorio


def test_a_conferencia_reprova_sem_o_modelo(monkeypatch):
    from sigft.app import conferencia
    from sigft.core import tradutor_local

    def sem_modelo():
        raise tradutor_local.ModeloAusente("Nao achei o modelo do tradutor local.")

    monkeypatch.setattr(tradutor_local, "localizar_modelo", sem_modelo)

    relatorio, ok = conferencia.conferir_tradutor()

    assert ok is False
    assert "Nao achei o modelo" in relatorio


def test_a_conferencia_reprova_um_tradutor_que_nao_traduz(monkeypatch, tmp_path):
    from sigft.app import conferencia
    from sigft.core import tradutor_local

    monkeypatch.setattr(tradutor_local, "localizar_modelo", lambda: tmp_path)
    monkeypatch.setattr(tradutor_local, "TradutorLocal", _TradutorQueResponde("Aço inoxidável"))

    assert conferencia.conferir_tradutor()[1] is False


def test_o_codigo_de_saida_junta_pacote_e_tradutor(monkeypatch, tmp_path):
    from sigft.app import conferencia

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(conferencia, "conferir_pacote", lambda: ("PACOTE OK", True))
    monkeypatch.setattr(conferencia, "conferir_tradutor", lambda: ("TRADUTOR QUEBRADO", False))

    assert conferencia.cli() == 1
    texto = (tmp_path / conferencia.ARQUIVO_CONFERENCIA).read_text(encoding="utf-8")
    assert "PACOTE OK" in texto and "TRADUTOR QUEBRADO" in texto


def test_a_lista_padrao_cobre_o_tradutor_local():
    from sigft.app import conferencia

    for modulo in ("ctranslate2", "sentencepiece", "sigft.core.tradutor_local",
                   "sigft.services.translator"):
        assert modulo in conferencia.MODULOS_ESSENCIAIS, modulo


# =============================================================================
# A interface Qt dentro do pacote (E6.1, o corte)
# =============================================================================
# Desde o corte o `.exe` abre a Qt. As telas Qt sao importadas na PRIMEIRA
# visita (as fabricas de `sigft.app_qt.main.TELAS`): uma que o PyInstaller
# deixasse de fora passaria pela abertura e pelo `--smoke` de um build sem a
# conferencia, e a pessoa descobriria ao clicar no menu. A conferencia procura
# cada uma dentro do `.exe` antes de publicar.

def test_a_lista_padrao_cobre_o_qt():
    from sigft.app import conferencia

    for modulo in ("PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
                   "shiboken6", "sigft.app_qt.main"):
        assert modulo in conferencia.MODULOS_ESSENCIAIS, modulo


def _modulos_da_fabrica(fabrica) -> set:
    """Os modulos que uma fabrica de `TELAS` precisa, lidos do bytecode dela.

    Dois formatos convivem no registro: a fabrica com o import DENTRO
    (`from sigft.app_qt.views.x import Tela`, o `IMPORT_NAME`) e o lambda que
    usa uma classe importada no topo do `main.py` (o `LOAD_GLOBAL`, cujo
    modulo e o `__module__` da classe). Lido do objeto vivo, e nao de uma
    lista escrita aqui: uma tela nova entra no teste sozinha.

    Um `functools.partial` e lido pela fabrica de dentro, e a propria classe da
    tela registrada da o modulo dela. Outro chamavel devolve vazio -- e o teste
    diz qual tela nao conseguiu ler, em vez de estourar aqui.
    """
    import dis
    import functools
    import inspect

    while isinstance(fabrica, functools.partial):
        fabrica = fabrica.func
    if inspect.isclass(fabrica):
        return {fabrica.__module__}
    if not inspect.isfunction(fabrica):
        return set()
    modulos = set()
    for instrucao in dis.get_instructions(fabrica):
        if instrucao.opname == "IMPORT_NAME":
            modulos.add(instrucao.argval)
        elif instrucao.opname == "LOAD_GLOBAL":
            objeto = fabrica.__globals__.get(instrucao.argval)
            if isinstance(objeto, type) and objeto.__module__.startswith("sigft.app_qt."):
                modulos.add(objeto.__module__)
    return modulos


def test_toda_tela_registrada_esta_na_conferencia_do_pacote():
    """As duas listas andam juntas: tela registrada em `TELAS` sem entrar na
    conferencia reprova aqui, e tela de `MODULOS_ESSENCIAIS` que saiu do
    registro tambem (a conferencia acusaria FALTA de um modulo que nem existe
    mais, e o Release pararia por nada)."""
    from sigft.app import conferencia
    from sigft.app_qt import main as qmain

    essenciais = set(conferencia.MODULOS_ESSENCIAIS)
    das_telas = {}
    for chave, fabrica in qmain.TELAS.items():
        modulos = _modulos_da_fabrica(fabrica)
        assert modulos, f"nao achei o modulo da tela {chave!r} na fabrica dela"
        for modulo in modulos:
            das_telas[modulo] = chave

    faltando = {m: chave for m, chave in das_telas.items() if m not in essenciais}
    assert not faltando, (
        "telas registradas em `sigft.app_qt.main.TELAS` que a conferencia do "
        "pacote nao procura -- acrescente em `conferencia.MODULOS_ESSENCIAIS`: "
        + ", ".join(f"{m} (tela {c!r})" for m, c in sorted(faltando.items())))

    sobrando = sorted(m for m in essenciais
                      if m.startswith("sigft.app_qt.views.") and m not in das_telas)
    assert not sobrando, (
        "modulos de tela na conferencia que nenhuma fabrica de `TELAS` importa "
        "mais -- tire de `conferencia.MODULOS_ESSENCIAIS`: " + ", ".join(sobrando))


def test_a_trava_entende_partial_e_classe_registrados_em_telas(monkeypatch):
    """`TELAS` aceita qualquer chamavel(parent, controller): um `partial` de uma
    fabrica, ou a propria classe da tela, tem de ser lido -- e nao estourar com
    AttributeError/TypeError no lugar da mensagem que diz o que fazer."""
    import functools

    from sigft.app_qt import main as qmain
    from sigft.app_qt.views.busca_pmib import ModuloBuscaPMIB

    monkeypatch.setitem(qmain.TELAS, "SearchPMIB", ModuloBuscaPMIB)
    monkeypatch.setitem(qmain.TELAS, "PDM", functools.partial(qmain.TELAS["PDM"]))

    test_toda_tela_registrada_esta_na_conferencia_do_pacote()


def test_a_trava_diz_qual_tela_nao_conseguiu_ler(monkeypatch):
    from sigft.app_qt import main as qmain

    class _ChamavelOpaco:
        def __call__(self, parent, controller):
            return None

    monkeypatch.setitem(qmain.TELAS, "Opaca", _ChamavelOpaco())

    with pytest.raises(AssertionError, match="nao achei o modulo da tela 'Opaca'"):
        test_toda_tela_registrada_esta_na_conferencia_do_pacote()


# =============================================================================
# A Qt CARREGA dentro do pacote (E6.2)
# =============================================================================
# `find_spec` acha `PySide6.QtCore` sem carregar o `QtCore.pyd` nem as DLLs do
# Qt: um pacote sem `Qt6Core.dll` passaria na lista acima e so morreria na
# abertura. `conferir_qt` importa de verdade e confere o que a janela le do
# disco -- o plugin da plataforma, o estilo nativo, a traducao pt_BR e as
# fontes --, para que um pacote incompleto pare o Release com o nome do que
# falta, e nao numa janela que nao abre.

def _linha(relatorio: str, trecho: str) -> str:
    linhas = [linha for linha in relatorio.splitlines() if trecho in linha]
    assert linhas, f"nenhuma linha com {trecho!r}:\n{relatorio}"
    return linhas[0]


def test_a_conferencia_carrega_a_qt_de_verdade():
    import PySide6

    from sigft.app import conferencia

    relatorio, ok = conferencia.conferir_qt()

    assert ok is True, relatorio
    assert f"PySide6 {PySide6.__version__}" in relatorio
    assert "FALHA" not in relatorio


def test_a_conferencia_reprova_um_modulo_qt_que_nao_carrega(monkeypatch):
    """`None` em `sys.modules` faz o import falhar como faria o `QtWidgets.pyd`
    com uma DLL do Qt faltando: ImportError."""
    from sigft.app import conferencia

    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", None)

    relatorio, ok = conferencia.conferir_qt()

    assert ok is False
    assert _linha(relatorio, "PySide6.QtWidgets").lstrip().startswith("FALHA")


def _qt_com_pasta_trocada(monkeypatch, nome, pasta):
    from sigft.app import conferencia

    real = conferencia._pasta_do_qt
    monkeypatch.setattr(conferencia, "_pasta_do_qt",
                        lambda pedido: str(pasta) if pedido == nome else real(pedido))
    return conferencia


def test_a_conferencia_reprova_sem_o_plugin_da_plataforma(monkeypatch, tmp_path):
    """Sem o plugin, o Qt nem abre a janela -- e no Windows ainda mostra uma
    caixa modal ("no Qt platform plugin"), que penduraria o passo --smoke."""
    (tmp_path / "platforms").mkdir()
    conferencia = _qt_com_pasta_trocada(monkeypatch, "PluginsPath", tmp_path)

    relatorio, ok = conferencia.conferir_qt()

    plataforma = conferencia.plataformas_do_qt()[0]
    assert ok is False
    assert _linha(relatorio, f"'{plataforma}'").lstrip().startswith("FALHA")


def test_a_conferencia_diz_por_que_o_plugin_da_plataforma_nao_carregou(monkeypatch, tmp_path):
    """Plugin presente que nao carrega (dependencia faltando) e o caso mais
    traicoeiro: o arquivo esta la. A linha traz o arquivo e o erro do Qt."""
    plataformas = tmp_path / "platforms"
    plataformas.mkdir()
    (plataformas / "libqquebrado.so").write_bytes(b"isto nao e uma biblioteca")
    conferencia = _qt_com_pasta_trocada(monkeypatch, "PluginsPath", tmp_path)

    relatorio, ok = conferencia.conferir_qt()

    assert ok is False
    assert "libqquebrado.so" in relatorio


def test_a_conferencia_reprova_sem_a_traducao_pt_br(monkeypatch, tmp_path):
    """Sem ela os dialogos saem com "Yes"/"No"/"Cancel"."""
    conferencia = _qt_com_pasta_trocada(monkeypatch, "TranslationsPath", tmp_path)

    relatorio, ok = conferencia.conferir_qt()

    assert ok is False
    assert _linha(relatorio, "pt_BR").lstrip().startswith("FALHA")


def test_a_conferencia_reprova_sem_as_fontes(monkeypatch, tmp_path):
    """A pasta das fontes sai de `__file__` no `estilo`: e no pacote que se
    descobre se ela aponta para onde o spec as pos."""
    from sigft.app import conferencia
    from sigft.app_qt import estilo

    monkeypatch.setattr(estilo, "PASTA_FONTES", str(tmp_path))

    relatorio, ok = conferencia.conferir_qt()

    assert ok is False
    assert _linha(relatorio, "Roboto-Regular.ttf").lstrip().startswith("FALHA")


def test_a_conferencia_reprova_sem_o_estilo_nativo(monkeypatch):
    """Sem o plugin de estilo o Qt cai no estilo "Windows" classico, sem aviso
    nenhum: so uma conferencia o ve."""
    from sigft.app import conferencia

    monkeypatch.setattr(conferencia, "ESTILO_NATIVO", {sys.platform: "estilo-que-nao-existe"})

    relatorio, ok = conferencia.conferir_qt()

    assert ok is False
    assert _linha(relatorio, "estilo-que-nao-existe").lstrip().startswith("FALHA")


@pytest.mark.parametrize("ambiente, sistema, esperado", [
    ({}, "win32", ["windows"]),
    ({}, "darwin", ["cocoa"]),
    ({}, "linux", ["xcb"]),
    ({}, "freebsd14", ["xcb"]),
    ({"QT_QPA_PLATFORM": ""}, "win32", ["windows"]),
    ({"QT_QPA_PLATFORM": "offscreen"}, "win32", ["offscreen"]),
    ({"QT_QPA_PLATFORM": "windows:darkmode=2"}, "win32", ["windows"]),
    ({"QT_QPA_PLATFORM": "wayland;xcb"}, "linux", ["wayland", "xcb"]),
])
def test_a_plataforma_conferida_e_a_que_o_qt_usaria(ambiente, sistema, esperado):
    """No Release, sem `QT_QPA_PLATFORM`, e a do sistema (`windows`); com a
    variavel (o --smoke offscreen, os testes), e a dela -- a mesma regra do Qt."""
    from sigft.app import conferencia

    assert conferencia.plataformas_do_qt(ambiente, sistema) == esperado


def test_o_codigo_de_saida_tambem_depende_da_qt(monkeypatch, tmp_path):
    from sigft.app import conferencia

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(conferencia, "conferir_pacote", lambda: ("PACOTE OK", True))
    monkeypatch.setattr(conferencia, "conferir_tradutor", lambda: ("TRADUTOR OK", True))
    monkeypatch.setattr(conferencia, "conferir_qt", lambda: ("QT QUEBRADA", False))

    assert conferencia.cli() == 1
    texto = (tmp_path / conferencia.ARQUIVO_CONFERENCIA).read_text(encoding="utf-8")
    assert "QT QUEBRADA" in texto

    monkeypatch.setattr(conferencia, "conferir_qt", lambda: ("QT OK", True))
    assert conferencia.cli() == 0


def test_a_conferencia_so_importa_stdlib_no_topo():
    """O pedido de desenho: a Qt so e importada DENTRO de `conferir_qt`. No
    topo, so stdlib -- a conferencia tem de rodar num pacote quebrado."""
    arvore = ast.parse(CONFERENCIA.read_text(encoding="utf-8"))
    no_topo = set()
    for no in arvore.body:
        if isinstance(no, ast.Import):
            no_topo |= {a.name.split(".")[0] for a in no.names}
        elif isinstance(no, ast.ImportFrom):
            no_topo.add((no.module or "").split(".")[0])

    assert no_topo <= set(sys.stdlib_module_names) | {"__future__"}, no_topo


def test_o_codigo_do_sigft_vai_fora_do_exe():
    """2026-10-19: medido entre a 1.2.1-rc.4 e a rc.5, 37,1 dos 38,6 MB da
    atualização pequena eram o `SIG-FT.exe` -- o código do SIG-FT morava no
    PYZ, dentro dele. Com `module_collection_mode={"sigft": "pyc"}`, mudar um
    módulo muda só o `.pyc` dele, e a atualização pequena encolhe."""
    from pathlib import Path

    spec = (Path(__file__).resolve().parent.parent / "SIG-FT.spec").read_text(encoding="utf-8")
    assert 'module_collection_mode={"sigft": "pyc"}' in spec


def test_o_leitor_de_avif_do_pillow_fica_fora_do_pacote():
    """2026-10-19: 7,9 MB que nenhum arquivo do SIG-FT usa; o Pillow aguenta a
    falta dele (`AvifImagePlugin` importa `_avif` dentro de try/except)."""
    from pathlib import Path

    spec = (Path(__file__).resolve().parent.parent / "SIG-FT.spec").read_text(encoding="utf-8")
    assert '"PIL._avif"' in spec
