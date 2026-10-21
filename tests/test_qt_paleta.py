"""Ctrl+K: a caixa de busca dos módulos e das ações (2026-10-21, etapa 1b)."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QLineEdit

from sigft.app_qt import catalogo, estilo, icones, tema
from sigft.app_qt import main as qmain
from sigft.app_qt.widgets.paleta import PaletaDeComandos


def test_comandos_tem_os_modulos_e_as_acoes():
    # Fix round 1 (2026-10-21): o módulo bloqueado aparece, apagado, como no menu.
    chaves = [c.chave for c in catalogo.comandos()]
    modulos = [c for c in chaves if c.startswith("tela:")]
    assert len(modulos) == len(catalogo.MODULOS)
    bloqueados = [c for c in catalogo.comandos() if c.bloqueado]
    assert [c.chave for c in bloqueados] == ["tela:CorrecaoPDM"]
    assert bloqueados[0].texto.endswith(" (bloqueado)")
    assert bloqueados[0].dica == catalogo.dica_do_menu("CorrecaoPDM")
    assert {f"acao:{acao[0]}" for acao in catalogo.ACOES} <= set(chaves)
    assert len(chaves) == len(set(chaves))


def test_todo_icone_existe():
    assert {c.icone for c in catalogo.comandos()} <= icones.NOMES


def test_texto_dos_comandos_sem_travessao():
    for comando in catalogo.comandos():
        assert "—" not in comando.texto and "–" not in comando.texto


@pytest.mark.parametrize("consulta, primeiro", [
    ("tradutor", "tela:Translator"),
    ("TRADUTOR", "tela:Translator"),
    ("condicoes", "tela:UploadConditions"),
    ("CONDIÇÕES", "tela:UploadConditions"),
    ("4.2", "tela:Translator"),
    ("tema claro", "acao:tema_claro"),
    ("procurar", "acao:atualizacoes"),
    ("chaves", "acao:chaves"),
    ("search", "tela:SearchPMIB"),
    ("inicio", "acao:inicio"),
])
def test_filtra_sem_acento_e_sem_caixa(consulta, primeiro):
    assert catalogo.filtrar(catalogo.comandos(), consulta)[0].chave == primeiro


def test_vazio_mostra_tudo_e_nada_nao_mostra_nada():
    assert catalogo.filtrar(catalogo.comandos(), "") == catalogo.comandos()
    assert catalogo.filtrar(catalogo.comandos(), "   ") == catalogo.comandos()
    assert catalogo.filtrar(catalogo.comandos(), "xyzzy") == []


def _paleta(qtbot):
    escolhas = []
    p = PaletaDeComandos(None, catalogo.comandos())
    qtbot.addWidget(p)
    p.escolheu.connect(escolhas.append)
    p.show()
    return p, escolhas


def test_digitar_filtra_e_enter_escolhe(qt_interface, qtbot):
    p, escolhas = _paleta(qtbot)
    qtbot.keyClicks(p.campo, "tradu")
    assert p.lista.count() == 1 and p.lista.currentRow() == 0
    qtbot.keyClick(p.campo, Qt.Key.Key_Return)
    assert escolhas == ["tela:Translator"]
    assert not p.isVisible()


def test_setas_andam_na_lista_sem_sair_do_campo(qt_interface, qtbot):
    p, _ = _paleta(qtbot)
    qtbot.keyClicks(p.campo, "tema")
    assert p.lista.count() == 3
    qtbot.keyClick(p.campo, Qt.Key.Key_Down)
    qtbot.keyClick(p.campo, Qt.Key.Key_Down)
    qtbot.keyClick(p.campo, Qt.Key.Key_Down)      # no fim, fica no fim
    assert p.lista.currentItem().data(Qt.ItemDataRole.UserRole) == "acao:tema_sistema"
    qtbot.keyClick(p.campo, Qt.Key.Key_Up)
    assert p.lista.currentItem().data(Qt.ItemDataRole.UserRole) == "acao:tema_claro"
    assert p.campo.text() == "tema"


def test_nada_encontrado_e_enter_nao_faz_nada(qt_interface, qtbot):
    p, escolhas = _paleta(qtbot)
    qtbot.keyClicks(p.campo, "xyzzy")
    assert p.lista.count() == 0 and not p.vazio.isHidden()
    qtbot.keyClick(p.campo, Qt.Key.Key_Return)
    assert escolhas == []
    qtbot.keyClick(p.campo, Qt.Key.Key_Down)      # lista vazia: seta não derruba


def test_clicar_num_item_escolhe(qt_interface, qtbot):
    p, escolhas = _paleta(qtbot)
    qtbot.keyClicks(p.campo, "chaves")
    item = p.lista.item(0)
    qtbot.mouseClick(p.lista.viewport(), Qt.MouseButton.LeftButton,
                     pos=p.lista.visualItemRect(item).center())
    assert escolhas == ["acao:chaves"]


def test_modulo_bloqueado_aparece_apagado_e_nao_se_escolhe(qt_interface, qtbot):
    p, escolhas = _paleta(qtbot)
    qtbot.keyClicks(p.campo, "correcao")
    assert p.lista.count() == 1
    item = p.lista.item(0)
    assert not item.flags() & Qt.ItemFlag.ItemIsEnabled
    assert item.toolTip() == catalogo.dica_do_menu("CorrecaoPDM")
    assert p.lista.currentRow() == -1
    qtbot.keyClick(p.campo, Qt.Key.Key_Down)
    qtbot.keyClick(p.campo, Qt.Key.Key_Return)
    assert escolhas == [] and p.isVisible()


def test_setas_pulam_o_modulo_bloqueado(qt_interface, qtbot):
    p, escolhas = _paleta(qtbot)
    qtbot.keyClicks(p.campo, "pdm")             # Planilhas (PDM), Correção de PDM (bloqueado)
    chaves = [p.lista.item(i).data(Qt.ItemDataRole.UserRole) for i in range(p.lista.count())]
    assert chaves == ["tela:PDM", "tela:CorrecaoPDM"]
    qtbot.keyClick(p.campo, Qt.Key.Key_Down)    # não para no bloqueado
    assert p.lista.currentItem().data(Qt.ItemDataRole.UserRole) == "tela:PDM"
    p, escolhas = _paleta(qtbot)
    for _ in range(5):                          # 0 -> 1, 2, 3, 4, (5 bloqueado) 6
        qtbot.keyClick(p.campo, Qt.Key.Key_Down)
    assert p.lista.currentItem().data(Qt.ItemDataRole.UserRole) == "tela:Translator"
    qtbot.keyClick(p.campo, Qt.Key.Key_Up)
    assert p.lista.currentItem().data(Qt.ItemDataRole.UserRole) == "tela:UploadSpecs"


def test_acoes_da_home_num_lugar_so():
    """A barra da Home, o Ctrl+K e quem faz cada ação saem de `catalogo.ACOES_DA_HOME`."""
    from sigft.app_qt.views import home

    acoes = catalogo.ACOES_DA_HOME
    assert [(a.chave, a.texto, a.variante, a.metodo) for a in acoes if a.chave != "atualizacoes"] \
        == list(home.BARRA)
    assert home.ICONE_DA_BARRA == {a.chave: a.icone for a in acoes}
    assert home.TEXTO_BOTAO_ATUALIZACOES == next(a.texto for a in acoes if a.chave == "atualizacoes")
    assert home.SELETOR_TEMA is catalogo.SELETOR_TEMA
    assert qmain.ACAO_NA_HOME == {a.chave: a.metodo for a in acoes}
    na_paleta = {a[0]: (a[1], a[2]) for a in catalogo.ACOES}
    for a in acoes:
        assert na_paleta[a.chave] == (a.texto, a.icone)
        assert callable(getattr(home.HomeView, a.metodo))


def test_esc_fecha_sem_escolher(qt_interface, qtbot):
    p, escolhas = _paleta(qtbot)
    qtbot.keyClick(p.campo, Qt.Key.Key_Escape)
    assert not p.isVisible() and escolhas == []


def test_app_perde_o_foco_fecha_sem_escolher(qt_interface, qtbot):
    """Alt+Tab para outro programa: a caixa não fica esquecida aberta."""
    p, escolhas = _paleta(qtbot)
    QApplication.instance().applicationStateChanged.emit(Qt.ApplicationState.ApplicationInactive)
    assert not p.isVisible() and escolhas == []


def test_janela_flutuante_que_some_ao_clicar_fora(qt_interface, qtbot):
    """`Popup`: o Qt fecha a caixa no clique fora dela (perda de foco na janela)."""
    p, _ = _paleta(qtbot)
    assert p.windowFlags() & Qt.WindowType.Popup == Qt.WindowType.Popup


@pytest.fixture
def janela(qt_interface, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    j = qmain.SIG_FT_App()
    j.fechar_sem_perguntar = True
    qtbot.addWidget(j)
    return j


def _ativar(janela, qtbot):
    """O atalho de janela só dispara na janela ATIVA (a ativação chega depois)."""
    janela.show()
    qtbot.waitExposed(janela)
    janela.activateWindow()
    qtbot.waitUntil(lambda: QApplication.activeWindow() is janela, timeout=2000)


def test_ctrl_k_esta_ligado(janela):
    assert janela.atalho_paleta.key() == QKeySequence("Ctrl+K")


def test_ctrl_k_abre_a_paleta(janela, qtbot):
    _ativar(janela, qtbot)
    janela.pilha.setFocus()
    qtbot.keyClick(janela.pilha, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
    assert janela._paleta is not None and janela._paleta.isVisible()
    janela._paleta.close()


def test_ctrl_k_nao_rouba_o_atalho_do_campo_de_texto(janela, qtbot):
    """Onde o campo de texto usa o Ctrl+K (apagar até o fim da linha, no Linux e
    no Mac), o campo ganha; onde não usa (Windows), a caixa abre."""
    _ativar(janela, qtbot)
    campo = QLineEdit("abcdef", janela.pilha)
    campo.show()
    campo.setFocus()
    campo.setCursorPosition(2)
    qtbot.keyClick(campo, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
    campo_usa = QKeySequence("Ctrl+K") in QKeySequence.keyBindings(QKeySequence.StandardKey.DeleteEndOfLine)
    if campo_usa:
        assert campo.text() == "ab"
        assert janela._paleta is None
    else:
        assert campo.text() == "abcdef"
        assert janela._paleta is not None and janela._paleta.isVisible()
        janela._paleta.close()


def test_escolher_um_modulo_abre_a_tela(janela, qtbot):
    p = janela.abrir_paleta()
    assert janela.abrir_paleta() is p               # aberta: não abre outra
    qtbot.keyClicks(p.campo, "tradutor")
    qtbot.keyClick(p.campo, Qt.Key.Key_Return)
    assert janela.pilha.currentWidget() is janela.telas["Translator"]


def test_a_acao_roda_com_a_caixa_ja_fechada(janela, qtbot, monkeypatch):
    """Ação que abre janela (Chaves de API): a caixa já saiu, sem segurar o mouse."""
    home = janela.telas["Home"]
    visto = []
    monkeypatch.setattr(home, "abrir_janela_chaves_api",
                        lambda: visto.append((p.isVisible(), QApplication.activePopupWidget())))
    p = janela.abrir_paleta()
    qtbot.keyClicks(p.campo, "chaves de api")
    qtbot.keyClick(p.campo, Qt.Key.Key_Return)
    assert visto == [(False, None)]


def test_a_paleta_fechada_abre_de_novo(janela, qtbot):
    p = janela.abrir_paleta()
    qtbot.keyClick(p.campo, Qt.Key.Key_Escape)
    nova = janela.abrir_paleta()
    assert nova.isVisible()
    nova.close()


def test_toda_acao_tem_quem_faca(janela, monkeypatch):
    feitos = []
    home = janela.telas["Home"]
    for metodo in {*qmain.ACAO_NA_HOME.values(), "escolher_tema"}:
        monkeypatch.setattr(home, metodo, lambda *a, m=metodo: feitos.append((m, a)))
    monkeypatch.setattr(janela, "abrir_pasta_de_logs", lambda: feitos.append(("logs", ())))
    janela.show_frame("Translator")
    for chave, *_resto in catalogo.ACOES:
        janela.executar_comando(f"acao:{chave}")
    assert ("escolher_tema", ("claro",)) in feitos
    assert ("abrir_janela_chaves_api", ()) in feitos
    assert len(feitos) == len(catalogo.ACOES) - 1      # "inicio" só navega
    assert janela.pilha.currentWidget() is janela.telas["Home"]


@pytest.fixture
def volta_ao_escuro(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(tema, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    folha, atual = qapp.styleSheet(), estilo.TEMA_ATUAL
    yield qapp
    estilo.TEMA_ATUAL = atual
    qapp.setStyleSheet(folha)


def test_tema_pela_paleta_marca_o_seletor_da_home(volta_ao_escuro, janela):
    home = janela.telas["Home"]
    janela.executar_comando("acao:tema_claro")
    assert estilo.TEMA_ATUAL == "claro" and tema.escolhido() == "claro"
    assert home.botoes_tema["claro"].property("ativo") is True
    assert home.botoes_tema["escuro"].property("ativo") is False


def test_abrir_logs_usa_o_mesmo_ajudante_da_home(janela, monkeypatch):
    from sigft.app_qt import pasta_de_logs
    from sigft.app_qt.views import home as home_mod

    chamadas = []
    monkeypatch.setattr(pasta_de_logs, "abrir", lambda pai=None: chamadas.append(pai))
    janela.executar_comando("acao:logs")
    home_mod.HomeView._abrir_pasta_logs_gastos_ia(janela.telas["Home"])
    assert len(chamadas) == 2


def test_comando_desconhecido_nao_derruba(janela):
    janela.executar_comando("acao:nao_existe")
    janela.executar_comando("tela:")
    janela.executar_comando("qualquer")


def test_folha_tem_as_regras_da_paleta():
    folha = estilo.folha_de_estilo()
    assert "#paleta" in folha and "#lista_paleta::item:selected" in folha
