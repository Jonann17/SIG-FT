"""Hook do PyInstaller para o `PySide6.QtGui`, no lugar do que vem com ele (E6.2).

Coleta o mesmo que o hook do PyInstaller (`add_qt6_dependencies`), menos os
PLUGINS que o SIG-FT não usa. O PyInstaller leva todas as famílias de plugin
do QtGui -- formatos de imagem, SVG, toque (tuio), teclado virtual, temas e
integrações do Linux (Wayland, EGL...) --, e a interface precisa de duas:

* `platforms`, a ponte com o sistema de janelas: sem ela a janela não abre.
  Ficam a do Windows (`qwindows`), a do Linux (`qxcb`) e a do Mac (`qcocoa`),
  mais as sem tela, `offscreen` (o `--smoke` e os testes) e `minimal`. Saem as
  alternativas que ninguém usa aqui (`qdirect2d`, `qwayland`, `qeglfs`, `qvnc`...).
* `styles`, o estilo nativo (no Windows, `qmodernwindowsstyle`: "windows11" e
  "windowsvista"). Sem ele o Qt cai no estilo "Windows" clássico SEM AVISO. A
  família inteira fica.

Imagem: o app só carrega PNG (o logo e o ícone da janela), que o QtGui lê sem
plugin. Medido no wheel 6.12 do Windows: saem 4,3 MB, entre plugins e o
`Qt6Svg.dll` que só os de SVG usavam.

Desde 2026-10-20 os ícones dos botões são SVG (`sigft/app_qt/icones.py`), mas
desenhados pelo `QSvgRenderer` do MÓDULO QtSvg, que o spec pede nos
`hiddenimports` e traz o `Qt6Svg.dll` de volta. Os plugins de SVG continuam
fora: o `icones.py` não passa pelo `QIcon("x.svg")` nem pelo `QImage`, que são
quem precisaria deles. O `--smoke` do Release desenha os ícones dentro do
`.exe` e reprova se algum vier vazio.

Por que um hook, e não um filtro no fim do spec, como o do navegador: a análise
de dependências do PyInstaller roda DEPOIS dos hooks. Plugin tirado aqui não
puxa as bibliotecas dele; tirado depois, elas ficariam órfãs no pacote -- no
Windows, o `Qt6Svg.dll` e o `Qt6Network.dll` (que o `qtuiotouchplugin` puxa;
o módulo QtNetwork sai pelos `excludes` do spec); no build de Linux, medido,
8 MB de GTK que só o tema `gtk3` trazia.

Hook do projeto ganha do embutido: o PyInstaller usa um hook por módulo, o de
prioridade mais alta, e os do `hookspath` do spec têm a mais alta de todas. Ao
atualizar o PyInstaller, confira se o hook dele
(`PyInstaller/hooks/hook-PySide6.QtGui.py`) ainda é só `add_qt6_dependencies`.

`tests/test_qt_no_pacote.py` roda este arquivo com plugins de mentira dos três
sistemas; a `--conferir-pacote` CARREGA a plataforma e confere o estilo dentro
do `.exe`, no Release.
"""
import os

from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)

PLATAFORMAS_USADAS = {"qwindows", "qxcb", "qcocoa", "qoffscreen", "qminimal"}


def _familia(destino):
    """`PySide6/plugins/platforms` (Windows) ou `PySide6/Qt/plugins/platforms`
    (Linux, Mac) -> `platforms`. `None` para o que não é plugin."""
    partes = destino.replace("\\", "/").split("/")
    if "plugins" not in partes:
        return None
    return "/".join(partes[len(partes) - partes[::-1].index("plugins"):])


def _nome(arquivo):
    """`qwindows.dll`, `libqxcb.so`, `libqcocoa.dylib` -> `qwindows`, `qxcb`, `qcocoa`."""
    base = os.path.splitext(os.path.basename(arquivo))[0]
    return base[3:] if base.startswith("lib") else base


def _fica(origem, destino):
    familia = _familia(destino)
    if familia is None or familia == "styles":
        return True
    return familia == "platforms" and _nome(origem) in PLATAFORMAS_USADAS


binaries = [(origem, destino) for (origem, destino) in binaries if _fica(origem, destino)]
