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


def test_mensagem_da_abertura_que_falhou_da_o_caminho_do_log_e_nao_manda_para_a_antiga():
    """A interface antiga saiu (2026-10-15): a caixa diz o motivo e onde está o
    log, e não oferece mais um comando para abrir outra interface."""
    assert catalogo.MSG_ABERTURA_FALHOU == (
        "O SIG-FT não conseguiu abrir a janela principal.\n\n{erro}\n\n"
        "O detalhe completo está em Documentos\\SIG-FT\\logs\\sigft.log. "
        "Mande esse arquivo para quem cuida do SIG-FT.")


def test_abertura_que_falha_mostra_o_motivo_e_sai_com_1(qt_interface, monkeypatch):
    from sigft.app_qt import main as qmain
    from sigft.core import dados_usuario, instancia
    from sigft.core.rpa import navegador

    codigos, caixas, ligados = [], [], []

    class SplashFalsa:
        pronta = type("S", (), {"connect": lambda self, f: ligados.append(f)})()

        def show(self):
            pass

        def carregar(self):
            ligados[0]()

        def close(self):
            pass

    def quebra():
        raise ValueError("api_config.json corrompido")

    monkeypatch.setattr(instancia, "preparar", lambda: None)
    monkeypatch.setattr(instancia, "encerrar", lambda codigo=0: codigos.append(codigo))
    monkeypatch.setattr(dados_usuario, "migrar_se_preciso", lambda: [])
    monkeypatch.setattr(navegador, "preparar_ambiente_do_rpa", lambda: None)
    monkeypatch.setattr(qmain, "_preparar_qt",
                        lambda: type("A", (), {"exec": lambda self: None})())
    monkeypatch.setattr(qmain, "SplashScreen", SplashFalsa)
    monkeypatch.setattr(qmain, "SIG_FT_App", quebra)
    monkeypatch.setattr(qmain.QMessageBox, "critical",
                        lambda pai, titulo, texto: caixas.append(texto))
    qmain.main()
    assert codigos[0] == 1
    assert "api_config.json corrompido" in caixas[0]
    assert "sigft.log" in caixas[0] and "interface antiga" not in caixas[0]


def test_menu_tem_as_telas_dos_cards_e_na_ordem_da_barra():
    telas_menu = [item[2] for item in catalogo.MENU if item[0] == "botao"]
    assert telas_menu == ["CriaFichas", "PDM", "Analyzer", "UploadConditions", "Translator",
                          "UploadSpecs", "CorrecaoPDM", "CopiaFichas", "AutoSpec", "LMR",
                          "PMIBManager", "SearchPMIB"]
    assert {m[0] for m in catalogo.MODULOS} == set(telas_menu)
