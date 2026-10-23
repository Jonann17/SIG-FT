"""Cada parte convertida da interface, montada em espanhol e em inglês (2026-10-22).

`ainda_em_portugues` (tests/_idioma.py) acusa o texto à vista que tem, no
catálogo, uma tradução diferente dele mesmo: a constante marcada (`marcar`) que
chegou à tela sem `t()`, que a guarda estática não vê. Cada tarefa do plano
`docs/superpowers/plans/2026-10-22-configuracao-e-idioma.md` acrescenta as suas.
"""
import threading

import pytest

from _idioma import ainda_em_portugues, em_idioma

IDIOMAS = ["es", "en"]


def _sem_conteudo(_pai):
    pass


@pytest.mark.parametrize("codigo", IDIOMAS)
def test_pecas_compartilhadas(qt_interface, qtbot, codigo):
    from sigft.app_qt.widgets import atividade, console, dialogos_selecao, dialogs, painel_janela, pickers
    from sigft.app_qt.widgets import resumo_lote as janela_resumo

    with em_idioma(codigo):
        pecas = [
            console.ConsoleFrame(),
            janela_resumo.JanelaResumoDoLote(None, "Upload duplicadas", [
                ("4500063671.0001: [Erro] ficha não encontrada", "erro"),
                ("[Aviso] tabela vazia", "aviso")]),
            dialogs.PausaLoginDialog(None, mensagem="x", evento_espera=threading.Event()),
            dialogs.RetryLockDialog(None, evento_espera=threading.Event(), resultado={}),
            dialogos_selecao.SelecaoMultiplaDialog(None, itens=["A", "B"], com_selecionar_todos=True),
            pickers.FileQueueList(chave="t.fila"),
            atividade.FaixaDeAtividade(),
            painel_janela.JanelaPainel(None, titulo="x", montar=_sem_conteudo),
        ]
        for peca in pecas:
            qtbot.addWidget(peca)
            assert ainda_em_portugues(peca, codigo) == set(), type(peca).__name__


@pytest.mark.parametrize("codigo", IDIOMAS)
def test_frases_do_resumo_e_dicas_no_idioma(codigo):
    from sigft.app import idioma, resumo_lote, textos_dicas

    with em_idioma(codigo):
        traducoes = idioma.catalogo(codigo)
        erros, juncao, aviso = idioma.t("{n} erros", n=2), idioma.t(" e "), idioma.t("{n} aviso", n=1)
        assert resumo_lote.frase_da_contagem(2, 1) == erros + juncao + aviso
        assert resumo_lote.frase_da_contagem(2, 1) != "2 erros e 1 aviso"
        dicas = textos_dicas.dicas_da_classe(type("ModuloCopiaFichas", (), {}))
        assert "{portal}" not in dicas["btn_robo_novo"]
        assert traducoes[textos_dicas.PORTAL] in dicas["btn_robo_novo"]


@pytest.mark.parametrize("codigo, linha_do_cartao, cabecalho", [
    ("es", "con Luan   ·   Em andamento   ·   criticidad 5", "1 actividad(es) que requieren atención"),
    ("en", "with Luan   ·   Em andamento   ·   criticality 5", "Activities needing attention: 1"),
])
def test_mural_com_um_cartao(qt_interface, qtbot, codigo, linha_do_cartao, cabecalho):
    """O cartão do mural no idioma da sessão: "com"/"criticidade" traduzidos, o
    que vem da planilha (pessoa, status, nível) como veio (revisão da Task 4)."""
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

    from sigft.app_qt.widgets import mural
    from sigft.services import atividades as at

    with em_idioma(codigo):
        pai = QWidget()
        QVBoxLayout(pai)
        qtbot.addWidget(pai)
        gavetas = {f: [] for f in at.FAIXAS}
        gavetas[at.ATRASADA] = [{"descricao": "Revisar fichas", "_dias": -4, "_termino": None,
                                 "com_quem": "Luan", "status": "Em andamento", "criticidade": 5}]
        mural.montar(pai, gavetas, "09/10/2026")
        textos = [r.text() for r in pai.findChildren(QLabel)]
        assert linha_do_cartao in textos
        assert cabecalho in textos
        assert ainda_em_portugues(pai, codigo) == set()


@pytest.fixture
def janela(qt_interface, qtbot, tmp_path, monkeypatch):
    """A janela principal, montada DENTRO do idioma do teste (cada tela lê os textos ao nascer)."""
    from sigft.app_qt import main as qmain

    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))

    def montar():
        principal = qmain.SIG_FT_App()
        principal.fechar_sem_perguntar = True
        qtbot.addWidget(principal)
        return principal
    return montar


@pytest.mark.parametrize("codigo", IDIOMAS)
def test_menu_home_configuracao_e_ctrl_k(janela, codigo, monkeypatch):
    with em_idioma(codigo):
        principal = janela()
        home = principal.telas["Home"]
        monkeypatch.setattr(principal, "get_key", lambda _chave: "chave-de-teste")
        abertas = [home.abrir_configuracao(), home.abrir_janela_chaves_api(),
                   home.abrir_janela_modelos_ia(), home.abrir_janela_gastos_ia()]
        assert ainda_em_portugues(principal, codigo) == set()
        for aberta in abertas:
            assert ainda_em_portugues(aberta, codigo) == set(), aberta.windowTitle()
        paleta = principal.abrir_paleta()
        assert ainda_em_portugues(paleta, codigo) == set()
        paleta.close()


@pytest.mark.parametrize("codigo", IDIOMAS)
def test_splash_pergunta_do_nome_e_do_idioma(qt_interface, qtbot, codigo):
    from sigft.app_qt import escolha_de_idioma, nome
    from sigft.app_qt.main import SplashScreen

    with em_idioma(codigo):
        for peca in (SplashScreen(), nome.PerguntaDoNome(), escolha_de_idioma.PerguntaDoIdioma()):
            qtbot.addWidget(peca)
            assert ainda_em_portugues(peca, codigo) == set(), type(peca).__name__


@pytest.mark.parametrize("codigo", IDIOMAS)
def test_saudacao_no_idioma(codigo):
    from datetime import datetime

    from sigft.app import idioma
    from sigft.app_qt import nome

    with em_idioma(codigo):
        manha = nome.saudacao(datetime(2026, 10, 22, 9), "Ana")
        assert manha == f"{idioma.t('Bom dia')}, Ana" and not manha.startswith("Bom dia")


@pytest.mark.parametrize("codigo, texto_do_tema, palavra_traduzida", [
    ("es", "Tema: Oscuro", "apariencia"),
    ("en", "Theme: Dark", "appearance"),
])
def test_ctrl_k_traduzido_acha_tambem_em_portugues(codigo, texto_do_tema, palavra_traduzida):
    """O Ctrl+K busca pelo texto traduzido e pelas palavras no idioma E em
    português: quem trocou de idioma e ainda digita em português acha."""
    from sigft.app_qt import catalogo

    with em_idioma(codigo):
        lista = catalogo.comandos()
        textos = {c.chave: c.texto for c in lista}
        assert textos["acao:tema_escuro"] == texto_do_tema
        assert textos["tela:CriaFichas"] != "Cria Fichas PMIB"
        nome_do_tema = texto_do_tema.split()[-1]
        for consulta in (f"aparencia {nome_do_tema}", f"{palavra_traduzida} {nome_do_tema}"):
            assert "acao:tema_escuro" in [c.chave for c in catalogo.filtrar(lista, consulta)], consulta
        assert "acao:configuracao" in [c.chave for c in catalogo.filtrar(lista, "engrenagem")]
        # Os nomes em português (menu, módulo, texto da ação) também acham.
        em_portugues = {"tradutor": "tela:Translator", "configuracao": "acao:configuracao",
                        "escuro": "acao:tema_escuro", "planilhas": "tela:PDM",
                        "chaves": "acao:chaves", "busca": "tela:SearchPMIB",
                        "duplicadas": "tela:CopiaFichas", "inicio": "acao:inicio",
                        "letra grande": "acao:letra_grande"}
        for consulta, chave in em_portugues.items():
            assert chave in [c.chave for c in catalogo.filtrar(lista, consulta)], consulta


def test_ctrl_k_em_portugues_nao_duplica_as_palavras():
    """Em português as palavras da busca são só as originais: nada repetido."""
    from sigft.app_qt import catalogo

    no_menu = {item[2]: item[1] for item in catalogo.MENU if item[0] == "botao"}
    palavras = {c.chave: c.palavras for c in catalogo.comandos()}
    for alvo, _titulo, _descricao in catalogo.MODULOS:
        assert palavras[f"tela:{alvo}"] == f"{no_menu.get(alvo, '')} {alvo}"
    for acao in catalogo.ACOES:
        assert palavras[f"acao:{acao.chave}"] == acao.palavras


@pytest.mark.parametrize("codigo", IDIOMAS)
def test_cria_fichas_planilhas_e_analyzer(janela, codigo):
    with em_idioma(codigo):
        principal = janela()
        for alvo in ("CriaFichas", "PDM", "Analyzer"):
            principal.show_frame(alvo)
            assert ainda_em_portugues(principal.telas[alvo], codigo) == set(), alvo


@pytest.mark.parametrize("codigo", IDIOMAS)
def test_janelas_auxiliares(qt_interface, qtbot, codigo):
    from sigft.app_qt.views import janelas
    from sigft.core.pdm_catalogo import PDM, CatalogoPDM

    catalogo = CatalogoPDM([PDM(codigo="PDM.4820.004", classe="4820", titulo="VALVULA ESFERA",
                                caracteristicas=("DIAMETRO",))])
    fila = [{"descricao": "Válvula", "pmib_original": "4500063671.0001", "pmib_alvo": "4500063671.0002"}]
    with em_idioma(codigo):
        for peca in (janelas.JanelaEscolherPDM(None, catalogo),
                     janelas.DialogoAcaoRobo(None, "erro", "PDM.4820.004"),
                     janelas.JanelaRevisaoEdicao(None, fila)):
            qtbot.addWidget(peca)
            assert ainda_em_portugues(peca, codigo) == set(), type(peca).__name__


@pytest.mark.parametrize("codigo", IDIOMAS)
def test_uploads_e_tradutor(janela, codigo):
    with em_idioma(codigo):
        principal = janela()
        for alvo in ("UploadConditions", "Translator", "UploadSpecs"):
            principal.show_frame(alvo)
            assert ainda_em_portugues(principal.telas[alvo], codigo) == set(), alvo


@pytest.mark.parametrize("codigo", IDIOMAS)
def test_pausa_de_login_dos_uploads_no_idioma(qt_interface, codigo):
    """A janela de pausa não está na tela montada: a guarda em tela não a vê."""
    from sigft.app import idioma
    from sigft.app.textos_dialogos import LOGIN_NECESSARIO, MSG_LOGIN_SOLTAR_ROBO
    from sigft.app_qt.views.upload_conditions import ModuloUploadConditions
    from sigft.app_qt.views.upload_tech_specs import ModuloUploadTechSpecs

    with em_idioma(codigo):
        esperado = idioma.catalogo(codigo)[MSG_LOGIN_SOLTAR_ROBO]
        for tela in (ModuloUploadConditions, ModuloUploadTechSpecs):
            assert tela._mensagem_da_pausa(LOGIN_NECESSARIO) == esperado, tela.__name__


@pytest.mark.parametrize("codigo", IDIOMAS)
def test_aba_do_robo_das_specs_no_idioma(janela, codigo):
    """O "Continuar" seleciona a aba do robô pelo nome; fora do português o nome
    é o traduzido, e `add` e `set` usam o mesmo `t(ABA_WEB)` (revisão da Task 7)."""
    from sigft.app import idioma
    from sigft.app_qt.views._upload_comum import ABA_WEB

    with em_idioma(codigo):
        principal = janela()
        principal.show_frame("UploadSpecs")
        tela = principal.telas["UploadSpecs"]
        tela.tabview.set(idioma.t(ABA_WEB))
        assert tela.tabview.get() == idioma.catalogo(codigo)[ABA_WEB]


@pytest.mark.parametrize("codigo", IDIOMAS)
def test_correcao_duplicadas_e_autospec(janela, codigo):
    from sigft.app_qt import main as qmain

    with em_idioma(codigo):
        principal = janela()
        for alvo in ("CopiaFichas", "AutoSpec"):
            principal.show_frame(alvo)
            assert ainda_em_portugues(principal.telas[alvo], codigo) == set(), alvo
        correcao = qmain.TELAS["CorrecaoPDM"](principal.pilha, principal)
        assert ainda_em_portugues(correcao, codigo) == set()


@pytest.mark.parametrize("codigo", IDIOMAS)
def test_lmr_pmib_manager_e_busca(janela, codigo):
    with em_idioma(codigo):
        principal = janela()
        for alvo in ("LMR", "PMIBManager", "SearchPMIB"):
            principal.show_frame(alvo)
            assert ainda_em_portugues(principal.telas[alvo], codigo) == set(), alvo


@pytest.mark.parametrize("codigo", IDIOMAS)
def test_dialogos_auxiliares_de_lmr_pmib_manager_e_busca(qt_interface, qtbot, codigo):
    """As janelas que as telas da Task 9 abrem (pendência da revisão dela,
    2026-10-22): "Escolha a aba", "Novas Listas Encontradas" e os resultados da
    busca, montadas no idioma."""
    from sigft.app_qt.views import busca_pmib, lmr, pmib_manager

    with em_idioma(codigo):
        busca = busca_pmib.ModuloBuscaPMIB(None, None)
        qtbot.addWidget(busca)
        resultado = {"codigo_itaipu": "4500063671.0012", "coluna_match": "DESCRIÇÃO", "amostra": "ROLAMENTO",
                     "caminho_arquivo": "/fichas/UG01/a.xlsx", "caminho_pasta": "/fichas/UG01"}
        janelas = [
            lmr.DialogoDaAba(None, nome_arquivo="LMR_Aplicacoes_2026.xlsx", abas=["Plan1", "LMR"]),
            pmib_manager.NovasListasDialog(None, itens=[(0, "[L-1]  -  Lista 1")],
                                           evento_espera=threading.Event(), resultado={}),
            busca_pmib.JanelaResultados(busca, [resultado]),
        ]
        for janela in janelas:
            qtbot.addWidget(janela)
            assert ainda_em_portugues(janela, codigo) == set(), type(janela).__name__


@pytest.mark.parametrize("codigo, esperado", [("es", "Ficha 3 de 8"), ("en", "Sheet 3 of 8")])
def test_avanco_da_faixa_de_atividade_no_idioma(qt_interface, qtbot, codigo, esperado):
    """O "Ficha 3 de 8" da faixa: o rótulo (marcado em `atividade`) e a frase
    passam por `t()` (pendência das Tasks 4/8; em espanhol a frase é a mesma)."""
    from sigft.app_qt.widgets import atividade

    with em_idioma(codigo):
        faixa = atividade.FaixaDeAtividade()
        qtbot.addWidget(faixa)
        faixa.comecar()
        faixa.progresso(3, 8, atividade.ROTULO_FICHA)
        assert esperado in faixa.rotulo.text()
        faixa.progresso(1, 2)
        assert {"es": "Ítem 1 de 2", "en": "Item 1 of 2"}[codigo] in faixa.rotulo.text()
        faixa.terminar()
