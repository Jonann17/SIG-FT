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


# --- Paridade com o CTkTabview (captura interface antiga, 1280x850, winfo_*) ------

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
    # 2026-10-20: o fundo da tela e o quadro do Tabview vêm do mesmo token, `fundo`
    # (a regra `#quadro_abas` da folha): o quadro volta a ser invisível, como na CTk. A barra
    # (`superficie_alta`) fica ~17 acima dele por canal: tolerância de 6.
    fundos = [QColor(theme.COLORS["background"])]

    def e_fundo(pixel):
        c = QColor(pixel)
        return any(max(abs(c.red() - f.red()), abs(c.green() - f.green()),
                       abs(c.blue() - f.blue())) <= 6 for f in fundos)

    xs, ys = [], []
    for y in range(topo, base):
        for x in range(x0, x1):
            if not e_fundo(imagem.pixel(x, y)):
                xs.append(x)
                ys.append(y)
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def test_medidas_iguais_as_do_interface_antiga(folha, qtbot):
    # 2026-10-20: medida do sistema visual (botão/campo 32, título 22, borda 1); a CTk saiu em 2026-10-15.
    # Na captura da interface antiga (coordenadas da tela, que aqui inclui a margem de 20 do
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
    assert (conteudo.x(), conteudo.y(), t.content.width()) == (40, 77, 923)
    assert t.console.y() == 670 and t.console.height() == 150

    imagem = t.grab().toImage()
    esq, topo, dir_, base = _caixa_do_botao_segmentado(imagem, 79, 121, 40, 963)
    assert topo == 87 and base == 114                      # 27 de altura
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
        assert p.x() == 52 and p.y() == 126
        assert vista.width() == 888 and vista.height() == 512
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
        # 2026-10-20: o quadro do Tabview é o token `fundo`, o mesmo da tela.
        fundo = theme.COLORS["background"].upper()
        assert QColor(foto.pixel(c.x() + 100, c.y() - 10)).name().upper() == fundo
        assert QColor(foto.pixel(p.x() + 2, p.y() + vista.height() - 3)).name().upper() == fundo

    # O quadro do Tabview é liso (o token `fundo` desde 2026-10-20): nada pintado
    # ao lado da área.
    from PySide6.QtGui import QColor
    from sigft.app import theme
    imagem = t.grab().toImage()
    fundo = QColor(theme.COLORS["background"]).rgb()
    assert imagem.pixel(44, 400) == fundo and imagem.pixel(958, 400) == fundo


# --- um robô por vez NA SEÇÃO (decisão de 2026-10-19) ---------------------------
# Pendência de 2026-10-11: cada aba tinha o seu "um robô por vez", mas nada
# impedia o Upload e a Exclusão de rodarem juntos, na MESMA página do portal e
# no mesmo console. Agora as duas abas dividem uma trava.

def test_trava_de_robo():
    from sigft.app_qt.widgets.trava_robo import TravaDeRobo

    trava = TravaDeRobo()
    assert trava.ocupar("Upload") and trava.dono == "Upload"
    assert not trava.ocupar("Exclusão") and trava.dono == "Upload"
    trava.liberar()
    assert trava.dono is None and trava.ocupar("Exclusão")


def test_as_duas_abas_dividem_a_mesma_trava(qt_interface, qtbot):
    secao = ModuloAplicacaoLMR()
    qtbot.addWidget(secao)

    assert secao.tela_upload.trava_robo is secao.tela_exclusao.trava_robo is not None


def test_com_o_upload_rodando_a_exclusao_nao_comeca(qt_interface, qtbot, monkeypatch):
    secao = ModuloAplicacaoLMR()
    qtbot.addWidget(secao)
    secao.trava_robo.ocupar("Upload de aplicações")
    monkeypatch.setattr(secao.tela_exclusao, "backend",
                        lambda nome: pytest.fail("nao devia nem carregar o modulo"))
    secao.tela_exclusao.entry_pmib.setText("4500001.0001")

    secao.tela_exclusao.iniciar_limpeza()

    qtbot.waitUntil(lambda: "Upload de aplicações" in secao.console.toPlainText(), timeout=2000)
    assert "está rodando" in secao.console.toPlainText()


def test_com_a_exclusao_rodando_o_upload_nao_comeca(qt_interface, qtbot, monkeypatch):
    secao = ModuloAplicacaoLMR()
    qtbot.addWidget(secao)
    secao.trava_robo.ocupar("Exclusão de aplicações")
    monkeypatch.setattr(secao.tela_upload, "backend",
                        lambda nome: pytest.fail("nao devia nem carregar o modulo"))

    secao.tela_upload.iniciar_lmr()

    qtbot.waitUntil(lambda: "Exclusão de aplicações" in secao.console.toPlainText(), timeout=2000)


def test_a_trava_e_liberada_no_fim_da_tarefa_mesmo_com_erro(qt_interface, qtbot):
    secao = ModuloAplicacaoLMR()
    qtbot.addWidget(secao)
    tela = secao.tela_exclusao

    def falha():
        raise RuntimeError("portal fora")

    thread = tela.iniciar_com_trava(falha, botao=None)
    thread.join(timeout=5)

    assert secao.trava_robo.dono is None

