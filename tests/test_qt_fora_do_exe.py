"""O .exe do SIG-FT ainda e o app CustomTkinter: o Qt nao pode entrar nele.

`SIG-FT.spec` faz `collect_submodules("sigft")`, que sem filtro pegaria
`sigft.app_qt.*` e arrastaria PySide6 + DLLs/plugins do Qt (50 MB ou mais)
para um instalador que nem abre essa interface. Duas protecoes, as duas
conferidas aqui como texto (o PyInstaller nao roda na suite):

1. o `collect_submodules("sigft")` filtra `sigft.app_qt`;
2. `PySide6` e `shiboken6` estao nos `excludes` do Analysis.

REMOVER ESTE TESTE NO CORTE (Etapa 6 da migracao para Qt): ali o .exe passa a
ser o app Qt e as duas protecoes saem do spec.
"""
from pathlib import Path

SPEC = (Path(__file__).resolve().parent.parent / "SIG-FT.spec").read_text(
    encoding="utf-8")


def test_collect_submodules_de_sigft_filtra_app_qt():
    assert 'collect_submodules(\n    "sigft", filter=lambda nome: '\
           'not nome.startswith("sigft.app_qt"))' in SPEC


def test_excludes_do_analysis_tem_pyside6_e_shiboken6():
    inicio = SPEC.index("excludes=[")
    lista = SPEC[inicio:SPEC.index("]", inicio)]
    assert '"PySide6"' in lista
    assert '"shiboken6"' in lista
