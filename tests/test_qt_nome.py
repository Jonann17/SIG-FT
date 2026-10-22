"""O nome na saudação da Home, perguntado uma vez (`sigft/app_qt/nome.py`, 2026-10-20).

A regra (spec do sistema visual, "Nome no saudação da Home"): a primeira
abertura sem nome guardado pergunta; "Agora não" ou fechar só registra que já
perguntou; clicar na saudação troca o nome. O nome só aparece na tela.
"""
import pathlib
from datetime import datetime

import pytest

from sigft.app_qt import nome

RAIZ = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture
def prefs_temporarias(tmp_path, monkeypatch):
    arquivo = tmp_path / "p.json"
    monkeypatch.setattr(nome, "_arquivo_de_prefs", lambda: arquivo)
    monkeypatch.setattr(nome, "_sem_gravar", [])
    return arquivo


# --- a regra -------------------------------------------------------------------

def test_saudacao_pelo_relogio():
    assert nome.saudacao(datetime(2026, 10, 20, 9), "Ana") == "Bom dia, Ana"
    assert nome.saudacao(datetime(2026, 10, 20, 14), "") == "Boa tarde"
    assert nome.saudacao(datetime(2026, 10, 20, 19), "Ana") == "Boa noite, Ana"


def test_saudacao_nas_viradas():
    # Boa noite até 5h (às 2h "Bom dia" soa estranho), Bom dia até 12h, Boa
    # tarde até 18h, Boa noite depois.
    assert nome.saudacao(datetime(2026, 10, 20, 0, 30), "") == "Boa noite"
    assert nome.saudacao(datetime(2026, 10, 20, 4, 59), "") == "Boa noite"
    assert nome.saudacao(datetime(2026, 10, 20, 5), "") == "Bom dia"
    assert nome.saudacao(datetime(2026, 10, 20, 11, 59), "") == "Bom dia"
    assert nome.saudacao(datetime(2026, 10, 20, 12), "") == "Boa tarde"
    assert nome.saudacao(datetime(2026, 10, 20, 17, 59), "") == "Boa tarde"
    assert nome.saudacao(datetime(2026, 10, 20, 18), "") == "Boa noite"


def test_pergunta_uma_vez_so(prefs_temporarias):
    assert nome.precisa_perguntar()
    nome.recusar()
    assert not nome.precisa_perguntar()
    assert nome.guardado() == ""


def test_guardar_apara_e_limita(prefs_temporarias):
    nome.guardar("   Jonathan   ")
    assert nome.guardado() == "Jonathan"
    assert not nome.precisa_perguntar()
    nome.guardar("x" * 100)
    assert len(nome.guardado()) == 40


def test_guardar_vazio_tira_o_nome_e_nao_pergunta_de_novo(prefs_temporarias):
    nome.guardar("Ana")
    nome.guardar("   ")
    assert nome.guardado() == ""
    assert not nome.precisa_perguntar()


def test_quem_ja_tinha_o_app_e_recebe_a_versao_tambem_e_perguntado(prefs_temporarias):
    """Prefs de uma versão anterior (tema gravado, sem nome nem registro): pergunta."""
    from sigft.core import prefs

    prefs.gravar_preferencia("tema", "claro", config_path=prefs_temporarias)
    assert nome.precisa_perguntar()


def test_gravar_que_falha_nao_derruba(prefs_temporarias, monkeypatch):
    from sigft.core import prefs

    def quebra(*_a, **_k):
        raise OSError("pasta so de leitura")

    monkeypatch.setattr(prefs, "gravar_preferencia", quebra)
    nome.guardar("Ana")
    nome.recusar()
    # Prefs que se leem mas não se gravam: perguntar de novo a cada abertura
    # seria pior que não perguntar. Uma falha de gravar basta para parar.
    assert not nome.precisa_perguntar()


def test_ler_que_falha_vale_sem_nome_e_sem_perguntar(prefs_temporarias, monkeypatch):
    """Arquivo ilegível: nada de perguntar a cada abertura sem conseguir lembrar."""
    from sigft.core import prefs

    def quebra(*_a, **_k):
        raise OSError("ilegivel")

    monkeypatch.setattr(prefs, "ler_preferencia", quebra)
    assert nome.guardado() == ""
    assert not nome.precisa_perguntar()


def test_o_nome_nao_vai_para_o_log(qt_interface, qtbot, tmp_path, monkeypatch):
    """Só aparece na tela: nada de log, planilha, IA ou portal."""
    # Quem lê o nome por qualquer caminho: a função, o import direto dela ou a
    # chave das preferências.
    sinais = ("nome.guardado(", "import guardado", "CHAVE_NOME",
              'ler_preferencia("nome"', "ler_preferencia('nome'")
    usos = [p for p in (RAIZ / "sigft").rglob("*.py")
            if any(s in p.read_text(encoding="utf-8") for s in sinais)]
    # 2026-10-22: o campo "Seu nome" da janela Configuração mostra o nome guardado (só tela).
    permitidos = {"sigft/app_qt/nome.py", "sigft/app_qt/views/home.py",
                  "sigft/app_qt/views/configuracao.py"}
    assert {p.relative_to(RAIZ).as_posix() for p in usos} <= permitidos


# --- a caixa ---------------------------------------------------------------------

def _textos(widget):
    from PySide6.QtWidgets import QLabel, QPushButton

    achados = widget.findChildren(QLabel) + widget.findChildren(QPushButton)
    return [w.text() for w in achados if w.text()]


def test_a_caixa_pergunta_e_tem_os_dois_botoes(qt_interface, qtbot, prefs_temporarias):
    caixa = nome.PerguntaDoNome(None)
    qtbot.addWidget(caixa)
    assert "Como podemos te chamar?" in _textos(caixa)
    assert caixa.botao_salvar.text() == "Salvar"
    assert caixa.botao_salvar.property("variante") == "primario"
    assert caixa.botao_agora_nao.text() == "Agora não"
    assert caixa.botao_agora_nao.property("variante") == "secundario"
    assert caixa.campo.maxLength() == nome.LIMITE


def test_salvar_guarda_o_nome(qt_interface, qtbot, prefs_temporarias):
    caixa = nome.PerguntaDoNome(None)
    qtbot.addWidget(caixa)
    caixa.campo.setText("  Ana  ")
    caixa.botao_salvar.click()
    assert nome.guardado() == "Ana"
    assert caixa.result() == caixa.DialogCode.Accepted


def test_agora_nao_so_registra(qt_interface, qtbot, prefs_temporarias):
    caixa = nome.PerguntaDoNome(None)
    qtbot.addWidget(caixa)
    caixa.campo.setText("Ana")
    caixa.botao_agora_nao.click()
    assert nome.guardado() == ""
    assert not nome.precisa_perguntar()


def test_fechar_pelo_x_tambem_registra(qt_interface, qtbot, prefs_temporarias):
    caixa = nome.PerguntaDoNome(None)
    qtbot.addWidget(caixa)
    caixa.show()
    caixa.close()
    assert not nome.precisa_perguntar()


def test_agora_nao_ao_trocar_mantem_o_nome_que_ja_havia(qt_interface, qtbot, prefs_temporarias):
    nome.guardar("Ana")
    caixa = nome.PerguntaDoNome(None)
    qtbot.addWidget(caixa)
    assert caixa.campo.text() == "Ana"
    caixa.campo.setText("Outro")
    caixa.botao_agora_nao.click()
    assert nome.guardado() == "Ana"


def test_o_texto_da_caixa_nao_tem_travessao(qt_interface, qtbot, prefs_temporarias):
    caixa = nome.PerguntaDoNome(None)
    qtbot.addWidget(caixa)
    textos = _textos(caixa) + [caixa.windowTitle(), caixa.campo.placeholderText()]
    assert not [t for t in textos if "—" in t or "–" in t]


# --- a abertura -------------------------------------------------------------------

@pytest.fixture
def principal(qt_interface, qtbot):
    from PySide6.QtWidgets import QMainWindow

    janela = QMainWindow()
    qtbot.addWidget(janela)
    janela.show()
    return janela


def test_na_abertura_agenda_a_pergunta_quando_precisa(principal, prefs_temporarias, monkeypatch):
    monkeypatch.setattr(nome.sys, "argv", ["frontend.py"])
    agendadas = []
    assert nome.perguntar_na_abertura(principal, agendar=lambda ms, f: agendadas.append(f))
    assert len(agendadas) == 1
    agendadas[0]()
    caixa = principal._pergunta_do_nome
    assert caixa.isVisible()
    caixa.botao_agora_nao.click()


def test_na_abertura_nao_pergunta_quem_ja_respondeu(principal, prefs_temporarias, monkeypatch):
    monkeypatch.setattr(nome.sys, "argv", ["frontend.py"])
    nome.recusar()
    agendadas = []
    assert not nome.perguntar_na_abertura(principal, agendar=lambda ms, f: agendadas.append(f))
    assert agendadas == []


def test_smoke_nao_pergunta(principal, prefs_temporarias, monkeypatch):
    """O `--smoke` (Release e CI) fecha sozinho: a pergunta o travaria."""
    monkeypatch.setattr(nome.sys, "argv", ["frontend.py", "--smoke"])
    agendadas = []
    assert not nome.perguntar_na_abertura(principal, agendar=lambda ms, f: agendadas.append(f))
    assert agendadas == []


def test_depois_de_responder_avisa_quem_pediu(principal, prefs_temporarias, monkeypatch):
    monkeypatch.setattr(nome.sys, "argv", ["frontend.py"])
    avisos = []
    agendadas = []
    nome.perguntar_na_abertura(principal, depois=lambda: avisos.append(nome.guardado()),
                               agendar=lambda ms, f: agendadas.append(f))
    agendadas[0]()
    caixa = principal._pergunta_do_nome
    caixa.campo.setText("Ana")
    caixa.botao_salvar.click()
    assert avisos == ["Ana"]


def test_montar_a_janela_principal_nao_abre_a_pergunta(qt_interface, qtbot, tmp_path,
                                                       monkeypatch):
    """A pergunta sai do lançador (`main.main`), não do `SIG_FT_App`: nenhum
    teste que monta a janela espera uma resposta."""
    from sigft.app_qt import main as qmain

    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    assert nome.precisa_perguntar()  # prefs isoladas do conftest: sem nome
    janela = qmain.SIG_FT_App()
    qtbot.addWidget(janela)
    janela.fechar_sem_perguntar = True
    janela.show()
    qtbot.wait(50)
    assert getattr(janela, "_pergunta_do_nome", None) is None


def test_novidades_esperam_a_pergunta_fechar(principal, prefs_temporarias, monkeypatch, qtbot):
    """As novidades vêm DEPOIS da pergunta: com ela aberta, esperam o fim."""
    from sigft.app_qt import novidades as tela_novidades
    from sigft.core import novidades

    monkeypatch.setattr(nome.sys, "argv", ["frontend.py"])
    bloco = novidades.Bloco(versao="1.2.0", data="2026-10-19", itens=["item"])
    chamadas = []
    monkeypatch.setattr(novidades, "para_mostrar_na_abertura",
                        lambda versao, **kw: chamadas.append(versao) or bloco)
    agendadas = []
    nome.perguntar_na_abertura(principal, agendar=lambda ms, f: agendadas.append(f))
    agendadas[0]()

    assert tela_novidades.mostrar_se_houver(principal, versao_atual="1.2.0",
                                            empacotado=True) is None
    assert chamadas == [], "decidiu (e gravou a versao como vista) sem mostrar"

    principal._pergunta_do_nome.botao_agora_nao.click()
    assert chamadas == ["1.2.0"]
    janela = principal._janela_de_novidades
    qtbot.addWidget(janela)
    assert janela.isVisible()


# --- a Home -------------------------------------------------------------------------

class _Controller:
    api_keys: dict = {}


def _home(qtbot):
    from sigft.app_qt.views import home as home_mod

    tela = home_mod.HomeView(controller=_Controller())
    qtbot.addWidget(tela)
    return tela


def test_o_titulo_da_home_e_a_saudacao(qt_interface, qtbot, prefs_temporarias, monkeypatch):
    from sigft.app_qt.views import home as home_mod

    nome.guardar("Ana")
    monkeypatch.setattr(home_mod, "_agora", lambda: datetime(2026, 10, 20, 9))
    tela = _home(qtbot)
    assert tela.label_titulo.text() == "Bom dia, Ana"
    assert tela.label_titulo.toolTip() == "Mudar como te chamamos"

    monkeypatch.setattr(home_mod, "_agora", lambda: datetime(2026, 10, 20, 15))
    tela.atualizar_saudacao()
    assert tela.label_titulo.text() == "Boa tarde, Ana"


def test_clicar_na_saudacao_troca_o_nome(qt_interface, qtbot, prefs_temporarias, monkeypatch):
    from PySide6.QtCore import Qt

    from sigft.app_qt.views import home as home_mod

    monkeypatch.setattr(home_mod, "_agora", lambda: datetime(2026, 10, 20, 19))
    tela = _home(qtbot)
    tela.show()
    assert tela.label_titulo.text() == "Boa noite"
    qtbot.mouseClick(tela.label_titulo, Qt.MouseButton.LeftButton)
    caixa = tela._pergunta_do_nome
    assert caixa.isVisible()
    caixa.campo.setText("Bia")
    caixa.botao_salvar.click()
    assert tela.label_titulo.text() == "Boa noite, Bia"


def test_apertar_e_arrastar_para_fora_nao_abre_a_pergunta(qt_interface, qtbot, prefs_temporarias):
    # Como um botão: a troca é no soltar, e soltar fora da saudação desiste.
    from PySide6.QtCore import QPoint, Qt

    tela = _home(qtbot)
    tela.show()
    rotulo = tela.label_titulo
    qtbot.mousePress(rotulo, Qt.MouseButton.LeftButton)
    assert getattr(tela, "_pergunta_do_nome", None) is None
    qtbot.mouseRelease(rotulo, Qt.MouseButton.LeftButton, pos=QPoint(-5, -5))
    assert getattr(tela, "_pergunta_do_nome", None) is None


def test_nome_comprido_nao_alarga_a_home(qt_interface, qtbot, prefs_temporarias):
    """40 letras na fonte do título não podem empurrar o seletor de tema para
    fora nem abrir rolagem horizontal: o fim do texto vira reticências."""
    from sigft.app_qt import estilo

    qt_interface.setStyleSheet(estilo.folha_de_estilo("escuro"))
    nome.guardar("W" * 40)
    tela = _home(qtbot)
    tela.resize(1280 - estilo.LARGURA_BARRA_LATERAL, 850)
    tela.show()
    qtbot.waitExposed(tela)
    corpo = tela.widget()
    assert corpo.minimumSizeHint().width() <= tela.viewport().width()
    assert tela.label_titulo.texto_visivel().endswith("…")
    assert tela.label_titulo.text().endswith("W" * 40)


def test_voltar_a_home_recalcula_a_saudacao(qt_interface, qtbot, tmp_path, monkeypatch):
    """"Bom dia" vira "Boa tarde" sem reabrir: a janela recalcula ao mostrar a Home."""
    from sigft.app_qt import main as qmain
    from sigft.app_qt.views import home as home_mod

    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    monkeypatch.setattr(home_mod, "_agora", lambda: datetime(2026, 10, 20, 9))
    janela = qmain.SIG_FT_App()
    qtbot.addWidget(janela)
    janela.fechar_sem_perguntar = True
    home = janela.telas["Home"]
    assert home.label_titulo.text() == "Bom dia"

    monkeypatch.setattr(home_mod, "_agora", lambda: datetime(2026, 10, 20, 13))
    janela.show_frame("Translator")
    janela.show_home()
    assert home.label_titulo.text() == "Boa tarde"

    # A resposta da pergunta da abertura também redesenha (o `depois` do lançador).
    nome.guardar("Ana")
    qmain._redesenhar_saudacao(janela)()
    assert home.label_titulo.text() == "Boa tarde, Ana"
