"""O "Como funciona" na tela (2026-10-28): logo abaixo do título de cada tela,
sempre no mesmo lugar; fechado na primeira vez; aberto ou fechado lembrado por
tela; nas seções de abas, o texto da aba aberta.

Desenho: `docs/superpowers/specs/2026-10-28-ajuda-para-quem-comeca-design.md`, parte 1.
A varredura de corte com o bloco ABERTO (pt, es, en e letra Grande) está em
`tests/_varredura.py`, que `test_qt_letra` e `test_qt_idioma_varredura` usam.
"""
from __future__ import annotations

import pytest

from _idioma import em_idioma
from sigft.app import como_funciona as textos
from sigft.app_qt import catalogo, icones
from sigft.app_qt.widgets import como_funciona as cf
from sigft.app_qt.widgets.module_frame import ModuleFrame


class Tela(ModuleFrame):
    def _build_ui(self):
        self.content_layout.addStretch()
        cf.instalar_como_funciona(self, "Translator")


@pytest.fixture(autouse=True)
def _com_o_bloco(monkeypatch):
    # O conftest desliga o bloco para os testes de medida das telas.
    monkeypatch.delenv(cf.ENV_DESLIGAR, raising=False)


@pytest.fixture
def prefs_do_teste(monkeypatch, tmp_path):
    arquivo = tmp_path / "user_prefs.json"
    monkeypatch.setattr(cf, "_arquivo_de_prefs", lambda: str(arquivo))
    return arquivo


def _bloco(tela) -> cf.ComoFunciona:
    blocos = tela.findChildren(cf.ComoFunciona)
    assert len(blocos) == 1
    return blocos[0]


# --- o widget ----------------------------------------------------------------------

def test_nasce_fechado_com_a_frase_a_vista(qt_interface, qtbot, prefs_do_teste):
    tela = Tela(titulo="x")
    qtbot.addWidget(tela)
    bloco = _bloco(tela)
    texto = textos.TEXTOS["Translator"]
    assert bloco.frase.text() == texto.frase
    assert bloco.frase.isVisibleTo(tela)
    assert not bloco.aberto()
    assert not bloco.detalhe.isVisibleTo(tela)
    assert bloco.botao.text() == cf.ROTULO_FECHADO
    assert [r.text() for r in bloco.rotulos_dos_itens()] == list(texto.itens)


def test_botao_de_ajuda_discreto_com_icone(qt_interface, qtbot, prefs_do_teste):
    tela = Tela(titulo="x")
    qtbot.addWidget(tela)
    botao = _bloco(tela).botao
    assert botao.property("variante") == "secundario"
    assert botao.property("icone") == cf.ICONE
    assert cf.ICONE in icones.NOMES
    assert not botao.icon().isNull()
    assert botao.accessibleName() == cf.ROTULO_FECHADO


def test_abre_e_fecha_no_clique(qt_interface, qtbot, prefs_do_teste):
    tela = Tela(titulo="x")
    qtbot.addWidget(tela)
    bloco = _bloco(tela)
    bloco.botao.click()
    assert bloco.aberto() and bloco.detalhe.isVisibleTo(tela)
    assert bloco.botao.text() == cf.ROTULO_ABERTO
    bloco.botao.click()
    assert not bloco.aberto() and not bloco.detalhe.isVisibleTo(tela)
    assert bloco.botao.text() == cf.ROTULO_FECHADO


def test_lembra_aberto_por_tela(qt_interface, qtbot, prefs_do_teste):
    primeira = Tela(titulo="x")
    qtbot.addWidget(primeira)
    _bloco(primeira).botao.click()
    assert "como_funciona_aberto.Translator" in prefs_do_teste.read_text(encoding="utf-8")

    de_novo = Tela(titulo="x")
    qtbot.addWidget(de_novo)
    assert _bloco(de_novo).aberto()
    assert _bloco(de_novo).detalhe.isVisibleTo(de_novo)

    _bloco(de_novo).botao.click()
    terceira = Tela(titulo="x")
    qtbot.addWidget(terceira)
    assert not _bloco(terceira).aberto()


def test_alternar_sem_gravar_nao_mexe_na_preferencia(qt_interface, qtbot, prefs_do_teste):
    tela = Tela(titulo="x")
    qtbot.addWidget(tela)
    _bloco(tela).alternar(True, gravar=False)
    assert _bloco(tela).aberto()
    assert not prefs_do_teste.exists()


def test_preferencia_que_nao_se_le_e_fechado(qt_interface, qtbot, monkeypatch):
    def quebrado():
        raise OSError("sem disco")
    monkeypatch.setattr(cf, "_arquivo_de_prefs", quebrado)
    tela = Tela(titulo="x")
    qtbot.addWidget(tela)
    bloco = _bloco(tela)
    assert not bloco.aberto()
    bloco.botao.click()                 # gravar que falha não derruba nada
    assert bloco.aberto()


def test_fica_logo_abaixo_do_titulo(qt_interface, qtbot, prefs_do_teste):
    tela = Tela(titulo="x")
    qtbot.addWidget(tela)
    linha = tela.header.layout()
    assert linha.itemAt(0).widget() is tela.label_titulo
    assert linha.itemAt(1).widget() is _bloco(tela)


@pytest.mark.parametrize("escolha", ["normal", "grande"])
def test_fechado_custa_uma_linha_de_texto(qt_interface, qtbot, prefs_do_teste, tmp_path,
                                          monkeypatch, escolha):
    """Fix round 2026-10-28: fechado, o bloco somava 38 px a cada cabeçalho (27 -> 65),
    e as telas mais altas passavam da tela de um notebook 1366x768. A frase e o
    botão dividem UMA linha, e o botão é compacto: o bloco fechado custa uma
    linha de texto, mais o respiro do título."""
    from sigft.app_qt import letra

    monkeypatch.setattr(letra, "_arquivo_de_prefs", lambda: tmp_path / "letra.json")
    letra.aplicar(qt_interface, escolha, gravar=False)
    try:
        tela = Tela(titulo="x")
        qtbot.addWidget(tela)
        tela.resize(1100, 700)
        tela.show()
        qtbot.waitExposed(tela)
        bloco = _bloco(tela)
        linha_de_texto = bloco.frase.fontMetrics().lineSpacing()
        assert bloco.botao.geometry().top() == bloco.frase.geometry().top() or \
            abs(bloco.botao.geometry().center().y() - bloco.frase.geometry().center().y()) <= 2
        assert bloco.height() <= linha_de_texto + 6, (bloco.height(), linha_de_texto)
        assert tela.header.height() - tela.label_titulo.height() <= linha_de_texto + 6 + cf.ESPACO_DO_TITULO
        assert bloco.botao.width() >= bloco.botao.sizeHint().width()   # o texto do botão cabe
    finally:
        letra.aplicar(qt_interface, "normal", gravar=False)


def test_tela_sem_bloco_nao_muda(qt_interface, qtbot):
    class SemBloco(ModuleFrame):
        def _build_ui(self):
            self.content_layout.addStretch()

    tela = SemBloco(titulo="x")
    qtbot.addWidget(tela)
    assert tela.findChildren(cf.ComoFunciona) == []
    assert tela.header.layout().count() == 1


def test_desligado_pela_variavel_dos_testes(qt_interface, qtbot, monkeypatch):
    monkeypatch.setenv(cf.ENV_DESLIGAR, "1")
    tela = Tela(titulo="x")
    qtbot.addWidget(tela)
    assert tela.findChildren(cf.ComoFunciona) == []
    assert tela.header.layout().count() == 1


def test_tela_embutida_nao_ganha_bloco(qt_interface, qtbot):
    tela = Tela(titulo="x", embutida=True)
    qtbot.addWidget(tela)
    assert tela.findChildren(cf.ComoFunciona) == []


def test_texto_no_idioma_da_sessao(qt_interface, qtbot, prefs_do_teste):
    from sigft.app import idioma

    with em_idioma("en"):
        tela = Tela(titulo="x")
        qtbot.addWidget(tela)
        bloco = _bloco(tela)
        assert bloco.frase.text() == idioma.t(textos.TEXTOS["Translator"].frase)
        assert bloco.botao.text() == idioma.t(cf.ROTULO_FECHADO)
    assert bloco.frase.text() != textos.TEXTOS["Translator"].frase


# --- as telas do menu -------------------------------------------------------------

@pytest.fixture
def janela(qt_interface, qtbot, tmp_path, monkeypatch, prefs_do_teste):
    from sigft.app_qt import main as qmain

    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    j = qmain.SIG_FT_App()
    j.fechar_sem_perguntar = True
    qtbot.addWidget(j)
    return j


def _tela(janela, alvo):
    from sigft.app_qt import main as qmain

    if alvo in catalogo.TELAS_BLOQUEADAS:   # fora do menu, mas o bloco já vem montado
        tela = qmain.TELAS[alvo](janela.pilha, janela)
        janela.pilha.addWidget(tela)
        return tela
    janela.show_frame(alvo)
    return janela.telas[alvo]


@pytest.mark.parametrize("alvo", [m[0] for m in catalogo.MODULOS])
def test_toda_tela_do_menu_tem_o_bloco_abaixo_do_titulo(janela, alvo):
    tela = _tela(janela, alvo)
    bloco = _bloco(tela)
    assert tela.header.layout().itemAt(1).widget() is bloco
    primeira = textos.chaves_da_tela(alvo)[0]
    assert bloco.chave == primeira
    assert bloco.frase.text() == textos.TEXTOS[primeira].frase
    # Só o da tela de fora: as telas embutidas nas abas não têm o seu.
    assert len(tela.findChildren(cf.ComoFunciona)) == 1


@pytest.mark.parametrize("alvo", sorted(textos.ABAS_DAS_SECOES))
def test_secao_de_abas_mostra_o_texto_da_aba_aberta(janela, alvo):
    tela = _tela(janela, alvo)
    bloco = _bloco(tela)
    nomes = list(tela.abas.abas)
    chaves = textos.chaves_da_tela(alvo)
    assert len(nomes) == len(chaves)
    for nome, chave in zip(nomes, chaves):
        tela.abas.botoes[nome].click()
        assert bloco.chave == chave
        assert bloco.frase.text() == textos.TEXTOS[chave].frase
        assert [r.text() for r in bloco.rotulos_dos_itens()] == list(textos.TEXTOS[chave].itens)
    tela.abas.set(nomes[0])
    assert bloco.chave == chaves[0]


def test_aba_lembra_o_proprio_estado(janela):
    tela = _tela(janela, "ConferenciaListas")
    bloco = _bloco(tela)
    assert not bloco.aberto()
    bloco.botao.click()                                       # aberto na Conferência
    nomes = list(tela.abas.abas)
    tela.abas.botoes[nomes[1]].click()                        # Revisão no AMP: nunca aberto
    assert bloco.chave == "ConferenciaListas.amp" and not bloco.aberto()
    tela.abas.botoes[nomes[0]].click()
    assert bloco.chave == "ConferenciaListas.conferencia" and bloco.aberto()


def test_autospec_tem_o_bloco_com_o_texto_do_08b(janela):
    tela = _tela(janela, "AutoSpec")
    assert _bloco(tela).frase.text() == textos.TEXTOS["AutoSpec"].frase
