"""Seção "Aplicação LMR" na interface Qt: Upload e Exclusão em abas, um console."""
import pytest

from sigft.app_qt.views.aplicacao_lmr import ModuloAplicacaoLMR


def test_duas_abas_com_um_console(qt_interface, qtbot):
    secao = ModuloAplicacaoLMR()
    qtbot.addWidget(secao)
    assert secao.label_titulo.text() == "Aplicação LMR"
    assert list(secao.abas.abas) == ["Upload de Aplicações", "Exclusão de Aplicações"]
    assert secao.abas.get() == "Upload de Aplicações"  # nunca abre direto na aba que APAGA
    assert secao.abas.tab("Upload de Aplicações").isAncestorOf(secao.tela_upload)
    assert secao.abas.tab("Exclusão de Aplicações").isAncestorOf(secao.tela_exclusao)
    assert secao.tela_upload.console is secao.console
    assert secao.tela_exclusao.console is secao.console
    assert secao.tela_upload.header is None and secao.tela_exclusao.header is None


def test_as_duas_abas_escrevem_no_mesmo_console(qt_interface, qtbot):
    secao = ModuloAplicacaoLMR()
    qtbot.addWidget(secao)
    secao.tela_upload.log("vindo do upload")
    secao.abas.botoes["Exclusão de Aplicações"].click()
    assert secao.abas.pilha.currentWidget() is secao.abas.tab("Exclusão de Aplicações")
    secao.tela_exclusao.log("vindo da exclusao")
    qtbot.waitUntil(lambda: "vindo da exclusao" in secao.console.toPlainText(), timeout=2000)
    texto = secao.console.toPlainText()
    assert texto.index("vindo do upload") < texto.index("vindo da exclusao")


def test_telas_registradas_no_menu(qt_interface, qtbot, tmp_path, monkeypatch):
    from sigft.app_qt import main as qmain
    from sigft.app_qt.views.translator import ModuloTranslator
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    janela = qmain.SIG_FT_App()
    qtbot.addWidget(janela)
    janela.show_frame("LMR")
    assert isinstance(janela.pilha.currentWidget(), ModuloAplicacaoLMR)
    janela.show_frame("Translator")
    assert isinstance(janela.pilha.currentWidget(), ModuloTranslator)


# --- Paridade com o CTkTabview (captura CustomTkinter, 1280x850, winfo_*) ------

@pytest.fixture
def folha(qt_interface):
    from sigft.app_qt import estilo
    anterior = qt_interface.styleSheet()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    yield
    qt_interface.setStyleSheet(anterior)


def _pos(w, base):
    return w.mapTo(base, w.rect().topLeft())


def _caixa_do_botao_segmentado(imagem, topo, base, x0, x1):
    """Retângulo dos pixels que NÃO são o fundo da tela, na faixa das abas."""
    from PySide6.QtGui import QColor
    from sigft.app import theme
    fundo = QColor(theme.COLORS["background"]).rgb()
    xs, ys = [], []
    for y in range(topo, base):
        for x in range(x0, x1):
            if imagem.pixel(x, y) != fundo:
                xs.append(x)
                ys.append(y)
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def test_medidas_iguais_as_do_customtkinter(folha, qtbot):
    # Na captura do CTk (coordenadas da tela, que aqui inclui a margem de 20 do
    # show_frame): conteúdo em (40, 79), 923 de largura; o botão segmentado
    # (137 + 150) x 27 centrado no conteúdo, 10 px abaixo do topo dele
    # (`_top_spacing`), o quadro do Tabview da cor do fundo (invisível); a área
    # rolável da tela embutida 12 px para dentro (6 do Tabview + 6 do
    # CTkScrollableFrame), 888 x 510, com a faixa da barra (16 + 1) à direita.
    t = ModuloAplicacaoLMR()
    qtbot.addWidget(t)
    t.resize(1003, 850)
    t.show()
    qtbot.waitExposed(t)

    conteudo = _pos(t.content, t)
    assert (conteudo.x(), conteudo.y(), t.content.width()) == (40, 79, 923)
    assert t.console.y() == 670 and t.console.height() == 150

    imagem = t.grab().toImage()
    esq, topo, dir_, base = _caixa_do_botao_segmentado(imagem, 79, 121, 40, 963)
    assert topo == 89 and base == 116                      # 27 de altura
    assert abs((esq + dir_) / 2 - (40 + 923 / 2)) <= 1      # centrado
    assert abs((dir_ - esq) - 287) <= 4                     # 137 + 150 (fonte)
    larguras = [b.width() for b in t.abas.botoes.values()]
    assert abs(larguras[0] - 137) <= 4 and abs(larguras[1] - 150) <= 4

    for nome, tela in (("Upload de Aplicações", t.tela_upload),
                       ("Exclusão de Aplicações", t.tela_exclusao)):
        t.abas.set(nome)
        qtbot.wait(10)
        rolagem = tela.content.parentWidget().parentWidget()  # viewport -> QScrollArea
        vista = rolagem.viewport()
        p = _pos(vista, t)
        assert p.x() == 52 and p.y() == 128
        assert vista.width() == 888 and vista.height() == 510
        cartao = tela.btn_run.parentWidget()
        assert _pos(cartao, t).y() - p.y() == 20
        # O cartão e o botão grande mantêm o fundo dentro da aba.
        from PySide6.QtGui import QColor
        from sigft.app import theme
        foto = t.grab().toImage()
        c, b = _pos(cartao, t), _pos(tela.btn_run, t)
        assert QColor(foto.pixel(c.x() + 3, c.y() + 100)).name().upper() == theme.COR_CARTAO.upper()
        assert QColor(foto.pixel(b.x() + 5, b.y() + 25)).name().upper() != theme.COR_CARTAO.upper()
        # ...e a área rolável é transparente: acima do cartão, o fundo da tela
        # (não a paleta clara do Qt, que o QScrollArea liga no widget de dentro).
        fundo = theme.COLORS["background"].upper()
        assert QColor(foto.pixel(c.x() + 100, c.y() - 10)).name().upper() == fundo
        assert QColor(foto.pixel(p.x() + 2, p.y() + vista.height() - 3)).name().upper() == fundo

    # O quadro do Tabview é da cor do fundo: nada pintado ao lado da área.
    from PySide6.QtGui import QColor
    from sigft.app import theme
    imagem = t.grab().toImage()
    fundo = QColor(theme.COLORS["background"]).rgb()
    assert imagem.pixel(44, 400) == fundo and imagem.pixel(958, 400) == fundo
