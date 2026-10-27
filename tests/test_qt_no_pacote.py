"""O pacote do Release leva a interface Qt (E6.2), e so o que ela usa.

Ate a E6.1 o `SIG-FT.spec` deixava a Qt de fora de proposito (filtro em
`collect_submodules("sigft")` e `PySide6`/`shiboken6` nos `excludes`); desde o
corte o `.exe` abre a Qt, e sem ela dentro abriria sem nada. Este arquivo
substitui o `test_qt_fora_do_exe.py`, que travava a exclusao.

Como o PyInstaller nao roda na suite, o spec e EXECUTADO com dubles das
funcoes do PyInstaller (`Analysis`, `COLLECT`, `collect_submodules`...): o que
se confere e o que ele pede ao PyInstaller e o que entrega ao `COLLECT` depois
dos filtros -- comportamento, e nao o texto do arquivo. Mesma ideia para o hook
que escolhe os plugins do Qt (`empacotamento/hooks/hook-PySide6.QtGui.py`).
"""
import hashlib
import os
import sys
import types
from importlib import metadata
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SPEC = RAIZ / "SIG-FT.spec"
PASTA_HOOKS = RAIZ / "empacotamento" / "hooks"
HOOK_QTGUI = PASTA_HOOKS / "hook-PySide6.QtGui.py"
PASTA_LICENCAS = RAIZ / "empacotamento" / "licencas"


# -- dubles do PyInstaller ------------------------------------------------------

def _submodulos_do_disco(pacote, filter=None):  # noqa: A002 -- nome do PyInstaller
    """O que o `collect_submodules` do PyInstaller devolve, lido do disco."""
    nomes = []
    for caminho in sorted((RAIZ / pacote.replace(".", "/")).rglob("*.py")):
        if "__pycache__" in caminho.parts:
            continue
        partes = list(caminho.relative_to(RAIZ).with_suffix("").parts)
        if partes[-1] == "__init__":
            partes = partes[:-1]
        nome = ".".join(partes)
        if filter is None or filter(nome):
            nomes.append(nome)
    return nomes


def _instalar_pyinstaller_falso(monkeypatch, **modulos):
    """Poe um `PyInstaller` de mentira em `sys.modules` (restaurado no fim)."""
    for nome in ("PyInstaller", "PyInstaller.utils"):
        monkeypatch.setitem(sys.modules, nome, types.ModuleType(nome))
    for nome, atributos in modulos.items():
        modulo = types.ModuleType(nome)
        for chave, valor in atributos.items():
            setattr(modulo, chave, valor)
        monkeypatch.setitem(sys.modules, nome, modulo)


# Um resultado de analise como o do PyInstaller 6 (destino, origem, tipo), com
# a Qt dos dois leiautes: Windows (PySide6/...) e Linux/macOS (PySide6/Qt/...).
_BINARIOS_DA_ANALISE = [
    ("PySide6/Qt6Core.dll", "/w/PySide6/Qt6Core.dll", "BINARY"),
    ("PySide6/opengl32sw.dll", "/w/PySide6/opengl32sw.dll", "BINARY"),
    ("PySide6/plugins/platforms/qwindows.dll", "/w/PySide6/plugins/platforms/qwindows.dll", "BINARY"),
    ("PySide6/Qt/lib/libQt6Core.so.6", "/l/PySide6/Qt/lib/libQt6Core.so.6", "BINARY"),
    ("libctranslate2.so.4", "/l/ctranslate2.libs/libctranslate2.so.4", "BINARY"),
]
_DADOS_DA_ANALISE = [
    ("PySide6/translations/qtbase_pt_BR.qm", "/w/PySide6/translations/qtbase_pt_BR.qm", "DATA"),
    ("PySide6/translations/qtbase_de.qm", "/w/PySide6/translations/qtbase_de.qm", "DATA"),
    ("PySide6/translations/qt_pt_BR.qm", "/w/PySide6/translations/qt_pt_BR.qm", "DATA"),
    ("PySide6/Qt/translations/qtbase_pt_BR.qm", "/l/PySide6/Qt/translations/qtbase_pt_BR.qm", "DATA"),
    ("PySide6/Qt/translations/qtbase_es.qm", "/l/PySide6/Qt/translations/qtbase_es.qm", "DATA"),
    ("outro_pacote/translations/app_de.qm", "/l/outro_pacote/translations/app_de.qm", "DATA"),
    ("assets/logo.png", str(RAIZ / "assets" / "logo.png"), "DATA"),
] + [
    # Com `noarchive=True` (2026-10-27) todo modulo puro chega aqui, em
    # `a.datas`, como `.pyc` solto -- inclusive os que moram nas pastas que os
    # filtros do spec olham (Qt, Google, Playwright).
    (destino, "/build/localpycs/0/" + destino, "DATA") for destino in (
        "PySide6/__init__.pyc",
        "PySide6/support/deprecated.pyc",
        "googleapiclient/discovery_cache/__init__.pyc",
        "googleapiclient/discovery_cache/base.pyc",
        "playwright/sync_api/__init__.pyc",
        "sigft/app_qt/estilo.pyc",
        "encodings/cp1252.pyc",
    )
]
_PYCS_DA_ANALISE = [d[0] for d in _DADOS_DA_ANALISE if d[0].endswith(".pyc")]


@pytest.fixture
def spec_executado(monkeypatch):
    """Executa o `SIG-FT.spec` com dubles e devolve o que ele pediu e entregou."""
    _instalar_pyinstaller_falso(monkeypatch, **{"PyInstaller.utils.hooks": {
        "collect_data_files": lambda pacote, include_py_files=False, **_: [],
        "collect_dynamic_libs": lambda pacote, **_: [],
        "collect_submodules": _submodulos_do_disco,
    }})
    capturado = {}

    class _Analise:
        def __init__(self, scripts, **opcoes):
            capturado["analysis"] = opcoes
            self.pure, self.scripts = [], []
            self.datas = list(_DADOS_DA_ANALISE)
            self.binaries = list(_BINARIOS_DA_ANALISE)

    def _collect(exe, binaries, datas, **_):
        capturado["binaries"] = list(binaries)
        capturado["datas"] = list(datas)

    monkeypatch.delenv("SIGFT_EMBUTIR_NAVEGADOR", raising=False)
    monkeypatch.chdir(RAIZ)  # o spec usa caminhos relativos a raiz, como o workflow
    espaco = {"Analysis": _Analise, "PYZ": lambda *a, **k: "pyz", "EXE": lambda *a, **k: "exe",
              "COLLECT": _collect, "SPECPATH": str(RAIZ), "__name__": "__main__"}
    exec(compile(SPEC.read_text(encoding="utf-8"), str(SPEC), "exec"), espaco)  # noqa: S102
    return capturado


# -- A. a interface Qt entra -----------------------------------------------------

def test_o_spec_coleta_a_interface_qt_inteira(spec_executado):
    """As telas Qt nascem na primeira visita (import dentro das fabricas de
    `TELAS`): o `collect_submodules("sigft")` e o que as garante no pacote."""
    pedidos = set(spec_executado["analysis"]["hiddenimports"])
    telas = {f"sigft.app_qt.views.{p.stem}" for p in (RAIZ / "sigft" / "app_qt" / "views").glob("*.py")
             if p.stem != "__init__"}

    assert "sigft.app_qt.main" in pedidos
    assert telas and telas <= pedidos, sorted(telas - pedidos)


def test_o_spec_nao_exclui_mais_o_pyside6(spec_executado):
    excluidos = set(spec_executado["analysis"]["excludes"])

    assert not excluidos & {"PySide6", "shiboken6"}, excluidos


def _importa_qtnetwork(arquivo: Path) -> bool:
    import ast

    for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
        if isinstance(no, ast.Import) and any(a.name.startswith("PySide6.QtNetwork") for a in no.names):
            return True
        if isinstance(no, ast.ImportFrom):
            if (no.module or "").startswith("PySide6.QtNetwork"):
                return True
            if no.module == "PySide6" and any(a.name == "QtNetwork" for a in no.names):
                return True
    return False


def test_o_python_vai_solto_e_nenhum_filtro_do_spec_tira_um_pyc(spec_executado):
    """`noarchive=True` (2026-10-27): as bibliotecas saem do `.exe` como `.pyc`
    em `a.datas`. Os filtros que o spec aplica DEPOIS da analise (navegador,
    descritores do Google, Qt que a interface nao usa) passam por eles -- e
    nenhum pode levar um modulo junto, ou o app abriria sem ele."""
    assert spec_executado["analysis"]["noarchive"] is True
    entregues = {d[0] for d in spec_executado["datas"]}

    assert set(_PYCS_DA_ANALISE) <= entregues, sorted(set(_PYCS_DA_ANALISE) - entregues)


def test_o_qtnetwork_fica_de_fora_porque_ninguem_o_usa(spec_executado):
    """O `PySide6/__init__.py` tem um `from . import QtNetwork` CONDICIONAL (so
    no Windows, se existir a pasta `PySide6\\openssl`, que o wheel do PyPI nao
    tem; e dentro de try/except ImportError). A analise do PyInstaller o segue
    e levaria o QtNetwork, o Qt6Network e os plugins de TLS e de rede (3,6 MB no
    Windows, 4 MB no Linux) para uma interface que nao usa rede pelo Qt.

    A outra metade e a que protege: se um dia alguem importar o QtNetwork, o
    `.exe` quebraria -- e este teste manda tirar o exclude antes disso."""
    assert "PySide6.QtNetwork" in spec_executado["analysis"]["excludes"]
    usam = [str(p.relative_to(RAIZ)) for p in [RAIZ / "frontend.py", *(RAIZ / "sigft").rglob("*.py")]
            if _importa_qtnetwork(p)]
    assert not usam, f"{usam} importam o QtNetwork: tire 'PySide6.QtNetwork' dos excludes do SIG-FT.spec"


# -- B. so o que a interface usa -------------------------------------------------

def test_o_pacote_leva_so_as_traducoes_do_qt_que_a_interface_usa(spec_executado):
    """`_instalar_traducao` (sigft/app_qt/main.py) carrega `qtbase_pt_BR` ou
    `qtbase_es`; o PyInstaller traria as ~100 traducoes do Qt (7 MB no Windows)."""
    dados = {destino for destino, _origem, _tipo in spec_executado["datas"]}

    assert "PySide6/translations/qtbase_pt_BR.qm" in dados
    assert "PySide6/Qt/translations/qtbase_pt_BR.qm" in dados
    assert "PySide6/Qt/translations/qtbase_es.qm" in dados
    assert not dados & {"PySide6/translations/qtbase_de.qm", "PySide6/translations/qt_pt_BR.qm"}
    # O filtro e da Qt: traducao de outro pacote e dado comum fica.
    assert {"outro_pacote/translations/app_de.qm", "assets/logo.png"} <= dados


def test_o_pacote_nao_leva_o_opengl_de_software(spec_executado):
    """`opengl32sw.dll` (20 MB) e o OpenGL por software do Qt Quick e do
    QOpenGLWidget; uma interface so de QtWidgets desenha sem OpenGL."""
    binarios = {destino for destino, _origem, _tipo in spec_executado["binaries"]}

    assert "PySide6/opengl32sw.dll" not in binarios
    assert {"PySide6/Qt6Core.dll", "PySide6/plugins/platforms/qwindows.dll",
            "PySide6/Qt/lib/libQt6Core.so.6", "libctranslate2.so.4"} <= binarios


def test_o_spec_usa_o_hook_que_escolhe_os_plugins_do_qt(spec_executado):
    pastas = [Path(p).resolve() for p in spec_executado["analysis"]["hookspath"]]

    assert PASTA_HOOKS.resolve() in pastas
    assert HOOK_QTGUI.is_file()


def _rodar_hook_qtgui(monkeypatch, plugins):
    chamadas = []

    def add_qt6_dependencies(arquivo_do_hook):
        chamadas.append(arquivo_do_hook)
        return ["PySide6.QtCore"], list(plugins), [("/x/qtbase_pt_BR.qm", "PySide6/translations")]

    _instalar_pyinstaller_falso(monkeypatch, **{
        "PyInstaller.utils.hooks": {},
        "PyInstaller.utils.hooks.qt": {"add_qt6_dependencies": add_qt6_dependencies},
    })
    espaco = {"__file__": str(HOOK_QTGUI), "__name__": "hook-PySide6.QtGui"}
    exec(compile(HOOK_QTGUI.read_text(encoding="utf-8"), str(HOOK_QTGUI), "exec"), espaco)  # noqa: S102
    return espaco, chamadas


_W, _L = "PySide6/plugins/", "PySide6/Qt/plugins/"
_PLUGINS_QUE_FICAM = [
    ("/w/qwindows.dll", _W + "platforms"),
    ("/w/qoffscreen.dll", _W + "platforms"),
    ("/w/qminimal.dll", _W + "platforms"),
    ("/w/qmodernwindowsstyle.dll", _W + "styles"),
    ("/l/libqxcb.so", _L + "platforms"),
    ("/l/libqoffscreen.so", _L + "platforms"),
    ("/l/libqminimal.so", _L + "platforms"),
    ("/m/libqcocoa.dylib", _L + "platforms"),
    ("/m/libqmacstyle.dylib", _L + "styles"),
    # O filtro e de PLUGIN: se um dia o hook do PyInstaller trouxer outro
    # binario (fora de `plugins/`), ele passa, em vez de sumir calado.
    ("/w/PySide6/algum_extra.dll", "PySide6"),
]
_PLUGINS_QUE_SAEM = [
    ("/w/qdirect2d.dll", _W + "platforms"),
    ("/w/qjpeg.dll", _W + "imageformats"),
    ("/w/qsvg.dll", _W + "imageformats"),
    ("/w/qsvgicon.dll", _W + "iconengines"),
    ("/w/qtuiotouchplugin.dll", _W + "generic"),
    ("/w/qtvirtualkeyboardplugin.dll", _W + "platforminputcontexts"),
    ("/l/libqwayland.so", _L + "platforms"),
    ("/l/libqeglfs.so", _L + "platforms"),
    ("/l/libqvnc.so", _L + "platforms"),
    ("/l/libqminimalegl.so", _L + "platforms"),
    ("/l/libqgtk3.so", _L + "platformthemes"),
    ("/l/libcomposeplatforminputcontextplugin.so", _L + "platforminputcontexts"),
    ("/l/libqxcb-glx-integration.so", _L + "xcbglintegrations"),
    ("/l/libqeglfs-kms-integration.so", _L + "egldeviceintegrations"),
    ("/l/libxdg-shell.so", _L + "wayland-shell-integration"),
]


def test_o_hook_do_qtgui_leva_so_plataforma_e_estilo(monkeypatch):
    """O PyInstaller leva TODAS as familias de plugin do QtGui (imagens, SVG,
    toque, temas do Linux...). O SIG-FT so precisa da plataforma (sem ela a
    janela nao abre) e do estilo nativo. Tirar ANTES da analise, no hook, e o
    que evita levar as bibliotecas que so esses plugins puxam (no Windows:
    Qt6Network.dll pelo tuio, Qt6Svg.dll pelos de SVG)."""
    espaco, chamadas = _rodar_hook_qtgui(monkeypatch, _PLUGINS_QUE_FICAM + _PLUGINS_QUE_SAEM)

    assert espaco["binaries"] == _PLUGINS_QUE_FICAM
    # O resto do que o hook do PyInstaller devolve passa intacto.
    assert espaco["hiddenimports"] == ["PySide6.QtCore"]
    assert espaco["datas"] == [("/x/qtbase_pt_BR.qm", "PySide6/translations")]
    # `add_qt6_dependencies` tira o modulo do NOME do arquivo do hook.
    assert [Path(c).name for c in chamadas] == ["hook-PySide6.QtGui.py"]


def test_o_hook_leva_a_plataforma_que_a_conferencia_exige(monkeypatch):
    """As duas pontas andam juntas: a plataforma que a `--conferir-pacote`
    procura em cada sistema (e a `offscreen` do --smoke no CI) sobrevive ao
    filtro do hook."""
    from sigft.app import conferencia

    exigidas = set(conferencia.PLATAFORMA_PADRAO.values()) | {"offscreen"}
    plugins = []
    for chave in sorted(exigidas):
        plugins += [(f"/w/q{chave}.dll", _W + "platforms"), (f"/l/libq{chave}.so", _L + "platforms"),
                    (f"/m/libq{chave}.dylib", _L + "platforms")]

    espaco, _ = _rodar_hook_qtgui(monkeypatch, plugins)

    assert espaco["binaries"] == plugins


# -- C. o que a interface le do disco vai junto -----------------------------------

def _destino_no_pacote(datas, arquivo: Path):
    """Onde o PyInstaller poe `arquivo` (relativo a raiz), pelas `datas` do spec."""
    relativo = arquivo.relative_to(RAIZ).as_posix()
    for origem, destino in datas:
        origem = Path(origem).as_posix()
        if relativo == origem or relativo.startswith(origem + "/"):
            resto = relativo[len(origem):].lstrip("/")
            nome = resto or Path(relativo).name
            return (Path(destino) / nome).as_posix() if destino != "." else nome
    return None


def test_as_fontes_da_interface_vao_para_onde_o_estilo_as_procura(spec_executado):
    """`estilo.PASTA_FONTES` sai de `__file__`: no pacote, `_MEIPASS/sigft/
    app_qt/estilo.pyc` -> `_MEIPASS/assets/fonts`. As fontes tem de cair ai."""
    from sigft.app_qt import estilo

    esperado = Path(os.path.relpath(estilo.PASTA_FONTES, estilo._RAIZ)).as_posix()
    for nome in estilo.ARQUIVOS_DE_FONTE:
        destino = _destino_no_pacote(spec_executado["analysis"]["datas"], RAIZ / esperado / nome)
        assert destino == f"{esperado}/{nome}", (nome, destino)



def test_os_catalogos_de_idioma_vao_para_onde_o_idioma_os_procura(spec_executado):
    """`idioma.PASTA_CATALOGOS` sai de `__file__`: no pacote, `_MEIPASS/sigft/app/
    idioma.pyc` -> `_MEIPASS/sigft/app/idiomas`. Os catálogos têm de cair aí."""
    from sigft.app import idioma

    esperado = Path(os.path.relpath(idioma.PASTA_CATALOGOS, RAIZ)).as_posix()
    for codigo in ("es", "en"):
        arquivo = RAIZ / esperado / f"{codigo}.json"
        assert arquivo.exists(), arquivo
        destino = _destino_no_pacote(spec_executado["analysis"]["datas"], arquivo)
        assert destino == f"{esperado}/{codigo}.json", (codigo, destino)

# -- D. as licencas do Qt (LGPLv3) vao no pacote -----------------------------------

# SHA-256 dos textos oficiais da FSF (gnu.org/licenses/lgpl-3.0.txt e
# gpl-3.0.txt), com fim de linha LF. Conferidos contra duas copias
# independentes cada um: /usr/share/common-licenses (Ubuntu, base-files) e o
# LICENSE.txt do psycopg 3.3.6 no PyPI (LGPL); o COPYING do GNU automake (GPL).
_SHA256_OFICIAL = {
    "LGPL-3.0.txt": "e3a994d82e644b03a792a930f574002658412f62407f5fee083f2555c5f23118",
    "GPL-3.0.txt": "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986",
}


@pytest.mark.parametrize("nome", sorted(_SHA256_OFICIAL))
def test_os_textos_da_licenca_sao_os_oficiais(nome):
    """O wheel do PySide6 nao traz o texto da LGPL (so um
    `LicenseRef-Qt-Commercial.txt`), e a LGPLv3 exige mandar a LGPL e a GPL
    junto. Texto de licenca nao se edita: o hash e o do original. (CRLF vira
    LF antes: o checkout do Windows converte os .txt.)"""
    texto = (PASTA_LICENCAS / nome).read_bytes().replace(b"\r\n", b"\n")

    assert hashlib.sha256(texto).hexdigest() == _SHA256_OFICIAL[nome]


def _pedidos_em(datas, pasta):
    return {Path(origem).resolve() for origem, destino in datas
            if Path(destino).as_posix() == pasta}


def test_o_pacote_leva_os_textos_e_o_aviso_da_licenca(spec_executado):
    datas = spec_executado["analysis"]["datas"]
    pedidos = _pedidos_em(datas, "licencas")

    for nome in ("LEIA-ME-Qt.txt", "LGPL-3.0.txt", "GPL-3.0.txt"):
        assert (PASTA_LICENCAS / nome).resolve() in pedidos, nome


@pytest.mark.parametrize("distribuicao", ["PySide6_Essentials", "shiboken6"])
def test_o_pacote_leva_os_arquivos_de_licenca_que_o_wheel_traz(spec_executado, distribuicao):
    """Os do wheel instalado no build (METADATA, que declara a licenca, e o
    que houver em `.dist-info/licenses/`), na versao que vai no pacote."""
    dist = metadata.distribution(distribuicao)
    do_wheel = {Path(dist.locate_file(f)).resolve() for f in dist.files
                if f.parts[0].endswith(".dist-info") and (f.name == "METADATA" or "licenses" in f.parts)}
    pedidos = _pedidos_em(spec_executado["analysis"]["datas"], f"licencas/{distribuicao}")

    assert any(p.name == "METADATA" for p in do_wheel)
    assert do_wheel and do_wheel <= pedidos, sorted(map(str, do_wheel - pedidos))
