"""A janela Configuração, a engrenagem da Home (2026-10-22).

Tudo o que se ajusta no SIG-FT saiu da Home para esta janela: aparência (tema e
letra), seu nome, avisos do Windows, inteligência artificial (chaves e modelos) e
atualizações. Cada controle faz o MESMO que o da Home fazia.
"""
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QPushButton

from sigft.app import tokens
from sigft.app_qt import aviso_windows, catalogo, estilo, letra, nome, tema
from sigft.app_qt.views import configuracao as config_mod
from sigft.app_qt.views import home as home_mod
from sigft.app_qt.widgets import controles
from sigft.services import updater


class Controller:
    api_keys: dict = {}

    def get_key(self, _chave):
        return ""

    def save_keys(self, _novas):
        pass

    def show_frame(self, _nome):
        pass


@pytest.fixture
def prefs(tmp_path, monkeypatch):
    arquivo = tmp_path / "p.json"
    for modulo in (tema, letra, aviso_windows):
        monkeypatch.setattr(modulo, "_arquivo_de_prefs", lambda: arquivo)
    monkeypatch.setattr(updater, "canal_testes_ligado", lambda **_k: False)
    return arquivo


@pytest.fixture
def home(qt_interface, qtbot, prefs):
    folha, atual = qt_interface.styleSheet(), estilo.TEMA_ATUAL
    tela = home_mod.HomeView(controller=Controller())
    qtbot.addWidget(tela)
    yield tela
    letra.aplicar(qt_interface, "normal", gravar=False)
    estilo.TEMA_ATUAL = atual
    qt_interface.setStyleSheet(folha)


def _visiveis(janela):
    return [j for j in janela.parent().findChildren(config_mod.JanelaConfiguracao) if j.isVisible()]


def test_a_engrenagem_abre_a_janela_e_o_segundo_clique_traz_a_mesma(home, qtbot):
    home.show()
    qtbot.mouseClick(home.btn_configuracao, Qt.MouseButton.LeftButton)
    janela = home._janelas["configuracao"]
    assert isinstance(janela, config_mod.JanelaConfiguracao)
    assert janela.isVisible() and janela.windowTitle() == "Configuração"
    assert janela.windowModality() == Qt.WindowModality.NonModal
    qtbot.mouseClick(home.btn_configuracao, Qt.MouseButton.LeftButton)
    assert _visiveis(janela) == [janela]
    janela.close()
    # Fechada, a próxima nasce de novo, com o que vale agora (como os painéis).
    assert home.abrir_configuracao() is not janela


@pytest.mark.parametrize("nome_tema", ["escuro", "claro"])
@pytest.mark.parametrize("escolha", ["normal", "grande"])
def test_a_engrenagem_fica_a_direita_do_titulo_sem_alargar_a_home(home, qtbot, escolha, nome_tema):
    estilo.TEMA_ATUAL = nome_tema          # a folha que a letra aplica sai neste tema
    letra.aplicar(QApplication.instance(), escolha, gravar=False)
    home.resize(1280 - estilo.LARGURA_BARRA_LATERAL, 850)
    home.show()
    qtbot.waitExposed(home)
    corpo = home.widget()
    qtbot.waitUntil(lambda: corpo.width() == home.viewport().width(), timeout=1000)
    qtbot.waitUntil(lambda: not home.horizontalScrollBar().isVisible(), timeout=1000)
    titulo = home.label_titulo.geometry()
    engrenagem = home.btn_configuracao
    topo = engrenagem.mapTo(corpo, QPoint(0, 0))
    assert topo.y() >= titulo.y() and topo.y() + engrenagem.height() <= titulo.y() + titulo.height()
    assert topo.x() + engrenagem.width() == corpo.width() - 57
    assert engrenagem.property("icone") == "settings" and not engrenagem.icon().isNull()
    assert engrenagem.property("variante") == "fantasma"
    assert engrenagem.toolTip() == "Configuração"
    if escolha == "normal":
        assert (titulo.x(), titulo.y(), titulo.height()) == (46, 46, 38)


def test_as_secoes_na_ordem_da_spec(home):
    janela = home.abrir_configuracao()
    assert list(janela.secoes) == [chave for chave, _titulo in catalogo.SECOES_DA_CONFIGURACAO]
    assert [r.text() for r in janela.secoes.values()] == \
        [titulo for _chave, titulo in catalogo.SECOES_DA_CONFIGURACAO]


def test_tema_muda_na_hora_e_fica_lembrado(home):
    janela = home.abrir_configuracao()
    assert set(janela.botoes_tema) == set(tema.TEMAS)
    assert janela.botoes_tema["escuro"].property("ativo") is True
    janela.botoes_tema["claro"].click()
    assert estilo.TEMA_ATUAL == "claro" and tema.escolhido() == "claro"
    assert janela.botoes_tema["claro"].property("ativo") is True
    assert janela.botoes_tema["escuro"].property("ativo") is False


def test_tema_de_fora_marca_a_janela_aberta(home):
    # O Ctrl+K chama `HomeView.escolher_tema`: a janela aberta acompanha.
    janela = home.abrir_configuracao()
    home.escolher_tema("sistema")
    assert janela.botoes_tema["sistema"].property("ativo") is True
    assert janela.botoes_tema["escuro"].property("ativo") is False


def test_letra_muda_na_hora_e_fica_lembrada(home):
    janela = home.abrir_configuracao()
    assert janela.botoes_letra["normal"].property("ativo") is True
    janela.botoes_letra["grande"].click()
    assert estilo.AUMENTO_LETRA == tokens.AUMENTO_DA_LETRA["grande"]
    assert letra.escolhido() == "grande"
    assert janela.botoes_letra["grande"].property("ativo") is True
    letra.aplicar(QApplication.instance(), "normal", gravar=False)   # de fora (Ctrl+K)
    assert janela.botoes_letra["normal"].property("ativo") is True


def test_seu_nome_guarda_e_a_saudacao_muda_na_hora(home):
    janela = home.abrir_configuracao()
    janela.campo_nome.setText("  Ana  ")
    janela.campo_nome.editingFinished.emit()
    assert nome.guardado() == "Ana"
    assert home.label_titulo.text().endswith(", Ana")
    janela.campo_nome.setText("")
    janela.campo_nome.editingFinished.emit()
    assert nome.guardado() == ""
    assert "," not in home.label_titulo.text()


def test_seu_nome_mostra_o_que_foi_guardado(home):
    # [2026-10-22] O campo mostra o nome como ficou guardado (aparado), e não
    # o que foi digitado: senão o campo e a saudação contam coisas diferentes.
    janela = home.abrir_configuracao()
    janela.campo_nome.setText("  Ana  ")
    janela.campo_nome.editingFinished.emit()
    assert janela.campo_nome.text() == "Ana"


def test_seu_nome_acompanha_a_troca_pela_saudacao_da_home(home):
    # Clicar na saudação da Home troca o nome (`PerguntaDoNome`); ao fechar a
    # pergunta, a Home refaz a saudação, e o campo da janela aberta acompanha.
    janela = home.abrir_configuracao()
    nome.guardar("Bia")
    home.atualizar_saudacao()
    assert janela.campo_nome.text() == "Bia"


def test_seu_nome_nao_atropela_o_que_esta_sendo_digitado(home):
    janela = home.abrir_configuracao()
    janela.campo_nome.setText("Car")
    janela.campo_nome.setModified(True)      # a pessoa digitando, sem sair do campo
    home.atualizar_saudacao()
    assert janela.campo_nome.text() == "Car"


def test_aviso_do_windows_liga_e_desliga(home):
    janela = home.abrir_configuracao()
    caixa = janela.caixa_avisos_windows
    assert caixa.text() == config_mod.TEXTO_AVISOS_WINDOWS
    assert caixa.isChecked()
    caixa.click()
    assert aviso_windows.ligado() is False


def test_chaves_e_modelos_abrem_as_mesmas_janelas_da_home(home, monkeypatch):
    janela = home.abrir_configuracao()
    chamados = []
    monkeypatch.setattr(home, "abrir_janela_chaves_api", lambda: chamados.append("chaves"))
    monkeypatch.setattr(home, "abrir_janela_modelos_ia", lambda: chamados.append("modelos"))
    janela.btn_chaves.click()
    janela.btn_modelos.click()
    assert chamados == ["chaves", "modelos"]
    assert janela.btn_chaves.text() == "Chaves de API"
    assert janela.btn_modelos.text() == "Modelos de IA"


def test_versoes_de_teste_lembra(home, monkeypatch):
    escolhas = []
    monkeypatch.setattr(updater, "ligar_canal_testes", lambda ligado, **_k: escolhas.append(ligado))
    janela = home.abrir_configuracao()
    caixa = janela.caixa_canal_testes
    assert isinstance(caixa, controles.CaixaDeMarcar)   # o "v" pintado, como era na Home
    assert caixa.text() == config_mod.TEXTO_CANAL_TESTES
    assert not caixa.isChecked()
    caixa.click()
    assert escolhas == [True]


def test_versoes_de_teste_que_nao_se_le_fica_desmarcada(home, monkeypatch):
    def quebra(*_a, **_k):
        raise OSError("sem permissão")

    monkeypatch.setattr(updater, "canal_testes_ligado", quebra)
    monkeypatch.setattr(updater, "ligar_canal_testes", quebra)
    janela = home.abrir_configuracao()
    assert not janela.caixa_canal_testes.isChecked()
    janela.caixa_canal_testes.click()   # lembrar não pode atrapalhar o clique
    assert janela.caixa_canal_testes.isChecked()


def test_procurar_atualizacoes_pergunta_agora_e_o_botao_volta(home, monkeypatch):
    from sigft.app_qt import atualizacao

    pedidos = []
    monkeypatch.setattr(atualizacao, "procurar_agora", lambda janela, **kw: pedidos.append((janela, kw)))
    janela = home.abrir_configuracao()
    botao = janela.btn_atualizacoes
    assert botao.text() == "Procurar atualizações"
    botao.click()
    assert not botao.isEnabled(), "dois cliques seriam duas consultas"
    assert botao.text() == home_mod.TEXTO_PROCURANDO
    [(quem, kw)] = pedidos
    assert quem is home.controller, "o aviso nasce da janela principal"
    kw["ao_terminar"]()
    assert botao.isEnabled() and botao.text() == "Procurar atualizações"


def test_procurar_atualizacoes_sem_botao_e_o_do_ctrl_k(home, monkeypatch):
    from sigft.app_qt import atualizacao

    pedidos = []
    monkeypatch.setattr(atualizacao, "procurar_agora", lambda janela, **kw: pedidos.append(kw))
    home.procurar_atualizacoes()
    [kw] = pedidos
    kw["ao_terminar"]()   # sem botão: nada a devolver, e não quebra


def _cortados(janela):
    achados = []
    for w in janela.findChildren(QPushButton) + janela.findChildren(QCheckBox) + janela.findChildren(QLabel):
        if not w.isVisible() or not w.text().strip():
            continue
        if isinstance(w, QLabel) and w.wordWrap():
            continue
        if w.width() < w.sizeHint().width():
            achados.append(w.text())
    return achados


def test_a_barra_de_rolagem_so_aparece_quando_ha_o_que_rolar(home, qtbot):
    # [2026-10-22] O `JanelaPainel` deixa a barra sempre à vista (a faixa do
    # CTkScrollableFrame); aqui ela aparecia cheia, sem nada para rolar.
    janela = home.abrir_configuracao()
    qtbot.waitExposed(janela)
    assert janela.area.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    barra = janela.area.verticalScrollBar()
    qtbot.waitUntil(lambda: barra.maximum() == 0, timeout=1000)
    assert not barra.isVisible()


@pytest.mark.parametrize("escolha", ["normal", "grande"])
def test_nada_corta_nem_rola_de_lado(home, qtbot, escolha):
    letra.aplicar(QApplication.instance(), escolha, gravar=False)
    janela = home.abrir_configuracao()
    qtbot.waitExposed(janela)
    qtbot.waitUntil(lambda: not janela.area.horizontalScrollBar().isVisible(), timeout=1000)
    assert _cortados(janela) == []


def test_nenhum_botao_nem_caixa_pega_o_foco(home):
    # Como os da Home: um Espaço perdido não troca o tema nem fecha a janela.
    janela = home.abrir_configuracao()
    controles_ = janela.findChildren(QPushButton) + janela.findChildren(QCheckBox)
    # [2026-10-22] 13: os 3 de idioma e o "Reiniciar agora" da seção Idioma a mais.
    assert len(controles_) >= 13
    for controle in controles_:
        assert controle.focusPolicy() == Qt.FocusPolicy.NoFocus, controle.text()


def test_a_home_ficou_so_com_o_que_e_dela(home):
    assert list(home.botoes_barra) == ["atividades", "gastos"]
    for saiu in ("caixa_canal_testes", "caixa_avisos_windows", "botoes_tema", "botoes_letra",
                 "btn_atualizacoes"):
        assert not hasattr(home, saiu), saiu


def test_ctrl_k_abre_a_configuracao(qt_interface, qtbot, tmp_path, monkeypatch, prefs):
    from sigft.app_qt import main as qmain

    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    principal = qmain.SIG_FT_App()
    principal.fechar_sem_perguntar = True
    qtbot.addWidget(principal)
    assert "acao:configuracao" in {c.chave for c in catalogo.comandos()}
    principal.show_frame("Translator")
    principal.executar_comando("acao:configuracao")
    janela = principal.telas["Home"]._janelas["configuracao"]
    assert janela.isVisible()


# --- a seção Idioma (Task 3) ----------------------------------------------------------

@pytest.fixture
def prefs_do_idioma(tmp_path, monkeypatch):
    from sigft.app import idioma

    monkeypatch.setattr(idioma, "_arquivo_de_prefs", lambda: tmp_path / "idioma.json")
    return idioma


def test_idioma_guarda_no_clique_e_so_entao_libera_o_reiniciar(home, prefs_do_idioma):
    idioma = prefs_do_idioma
    janela = home.abrir_configuracao()
    assert [b.text() for b in janela.botoes_idioma.values()] == ["Español", "Português", "English"]
    assert janela.botoes_idioma["pt"].property("ativo") is True
    assert not janela.btn_reiniciar.isEnabled(), "o idioma escolhido é o que está valendo"
    assert janela.aviso_idioma.text() == config_mod.TEXTO_IDIOMA_AO_REINICIAR
    janela.botoes_idioma["es"].click()
    assert idioma.escolhido() == "es"
    assert janela.botoes_idioma["es"].property("ativo") is True
    assert janela.btn_reiniciar.isEnabled()
    janela.botoes_idioma["pt"].click()
    assert not janela.btn_reiniciar.isEnabled()


def test_reiniciar_agora_chama_o_reinicio_com_a_janela_principal(home, prefs_do_idioma, monkeypatch):
    from sigft.app_qt import reinicio

    pedidos = []
    monkeypatch.setattr(reinicio, "reiniciar", lambda janela, pai=None: pedidos.append((janela, pai)))
    janela = home.abrir_configuracao()
    janela.botoes_idioma["en"].click()
    janela.btn_reiniciar.click()
    assert pedidos == [(home.controller, janela)]
