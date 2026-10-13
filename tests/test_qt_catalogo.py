import ast
import os

from sigft.app_qt import catalogo

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _valor(caminho, nome):
    arvore = ast.parse(open(caminho, encoding="utf-8").read())
    for no in arvore.body:
        if isinstance(no, ast.Assign) and getattr(no.targets[0], "id", None) == nome:
            return ast.literal_eval(no.value)
    raise AssertionError(f"{nome} não achado em {caminho}")


HOME = os.path.join(RAIZ, "sigft", "app", "views", "home.py")
MAIN = os.path.join(RAIZ, "sigft", "app", "main.py")


def test_modulos_iguais_aos_da_home_atual():
    assert catalogo.MODULOS == _valor(HOME, "MODULOS")


def test_bloqueadas_iguais():
    assert catalogo.TELAS_BLOQUEADAS == frozenset(_valor(MAIN, "TELAS_BLOQUEADAS"))


def test_mensagens_iguais():
    assert catalogo.MSG_TAREFA_EM_ANDAMENTO == _valor(MAIN, "MSG_TAREFA_EM_ANDAMENTO")
    assert catalogo.MSG_ABERTURA_FALHOU == _valor(MAIN, "MSG_ABERTURA_FALHOU")


def test_menu_tem_as_telas_dos_cards_e_na_ordem_da_barra():
    telas_menu = [item[2] for item in catalogo.MENU if item[0] == "botao"]
    assert telas_menu == ["CriaFichas", "PDM", "Analyzer", "UploadConditions", "Translator",
                          "UploadSpecs", "CorrecaoPDM", "CopiaFichas", "AutoSpec", "LMR",
                          "PMIBManager", "SearchPMIB"]
    assert {m[0] for m in catalogo.MODULOS} == set(telas_menu)
