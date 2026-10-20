"""Ícones Lucide no lugar dos emoji (sistema visual, Task 6, 2026-10-20).

O emoji dependia da fonte do sistema (colorido ou preto e branco, conforme a
máquina) e não seguia o tema. O ícone é um SVG de traço (`assets/icons/`,
copiado do `lucide-static@0.460.0`, licença ISC), pintado na cor da paleta do
tema atual; `icones.reaplicar` repinta tudo quando o tema muda (Task 7).
"""
import ast
from pathlib import Path

import pytest
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from sigft.app_qt import estilo, icones

RAIZ = Path(__file__).resolve().parent.parent


def test_todo_icone_listado_existe():
    for nome in icones.NOMES:
        assert (icones.PASTA / f"{nome}.svg").is_file(), nome


def test_a_pasta_tem_so_os_icones_listados():
    """Copiar o pacote inteiro (1500 SVG) por engano incharia o instalador."""
    na_pasta = {p.stem for p in icones.PASTA.glob("*.svg")}
    assert na_pasta == set(icones.NOMES)


def test_icone_carrega_colorido(qapp):
    i = icones.icone("house", "#00C975")
    assert not i.isNull()
    assert not i.pixmap(18, 18).isNull()


def test_a_cor_pedida_e_a_que_sai_no_desenho(qapp):
    imagem = icones.icone("square", "#FF0000", 24).pixmap(24, 24).toImage()
    cores = {imagem.pixelColor(x, y).name() for x in range(24) for y in range(24)
             if imagem.pixelColor(x, y).alpha() == 255}
    assert "#ff0000" in cores


def test_cache_por_nome_cor_e_tamanho(qapp):
    assert icones.icone("house", "#00C975").cacheKey() == icones.icone("house", "#00C975").cacheKey()
    assert icones.icone("house", "#00C975").cacheKey() != icones.icone("house", "#FFFFFF").cacheKey()


def test_nome_desconhecido_nao_derruba(qapp):
    assert icones.icone("nao-existe", "#FFFFFF").isNull()


def test_licenca_vai_junto():
    assert "ISC" in (icones.PASTA / "LICENSE").read_text(encoding="utf-8")


def test_pacote_leva_os_icones():
    spec = open(RAIZ / "SIG-FT.spec", encoding="utf-8").read()
    assert "assets/icons" in spec or "assets\\\\icons" in spec


def test_o_pacote_leva_o_qtsvg_que_desenha_os_icones():
    """`icones.py` desenha com o `QSvgRenderer` (módulo QtSvg, `Qt6Svg.dll`),
    sem plugin de imagem: o hook do QtGui pode continuar tirando os plugins de
    SVG, mas o módulo não pode sair do pacote."""
    spec = (RAIZ / "SIG-FT.spec").read_text(encoding="utf-8")
    arvore = ast.parse(spec)
    excludes = next(
        ast.literal_eval(k.value) for no in ast.walk(arvore) if isinstance(no, ast.Call)
        for k in no.keywords if k.arg == "excludes")
    assert not any(e.startswith("PySide6.QtSvg") for e in excludes)
    assert '"PySide6.QtSvg"' in spec  # pedido por extenso nos hiddenimports


def test_conferir_acha_todos_os_icones(qapp):
    assert icones.conferir() == []


def test_conferir_acusa_o_icone_que_nao_desenha(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(icones, "PASTA", tmp_path)
    icones._CACHE.clear()
    try:
        assert "house" in icones.conferir()
    finally:
        icones._CACHE.clear()


# --- aplicar e reaplicar --------------------------------------------------------

def test_aplicar_guarda_o_nome_e_poe_o_icone(qapp):
    botao = QPushButton("Abrir Pasta")
    icones.aplicar(botao, "folder-open")
    assert botao.property("icone") == "folder-open"
    assert not botao.icon().isNull()
    assert botao.text() == "Abrir Pasta"   # o texto fica: teste e leitor de tela


def test_a_cor_do_icone_e_a_do_texto_da_variante():
    p = estilo.paleta_atual()
    assert estilo.cor_do_texto_da_variante(None) == p["texto"]
    assert estilo.cor_do_texto_da_variante("primario") == p["texto_sobre_primaria"]
    assert estilo.cor_do_texto_da_variante("perigo") == estilo.TEXTO_SOBRE_PERIGO


def test_rotulo_recebe_o_icone_como_desenho(qapp):
    rotulo = QLabel()
    icones.aplicar(rotulo, "sparkles", papel_cor="primaria", tamanho=20)
    assert rotulo.pixmap() is not None and not rotulo.pixmap().isNull()


def test_reaplicar_repinta_na_cor_do_tema_novo(qapp, monkeypatch):
    raiz = QWidget()
    botao = QPushButton("Home", raiz)
    rotulo = QLabel(raiz)
    icones.aplicar(botao, "house")
    icones.aplicar(rotulo, "tag", papel_cor="primaria")
    antes_botao, antes_rotulo = botao.icon().cacheKey(), rotulo.pixmap().cacheKey()

    monkeypatch.setattr(estilo, "TEMA_ATUAL", "claro")
    icones.reaplicar(raiz)

    assert botao.icon().cacheKey() != antes_botao
    assert rotulo.pixmap().cacheKey() != antes_rotulo
    assert botao.icon().cacheKey() == icones.icone("house", estilo.paleta_atual()["texto"]).cacheKey()


def test_reaplicar_segue_a_variante_trocada(qapp):
    botao = QPushButton("Limpar")
    icones.aplicar(botao, "trash-2")
    estilo.definir_variante(botao, "perigo")
    icones.reaplicar(botao)
    assert botao.icon().cacheKey() == icones.icone("trash-2", estilo.TEXTO_SOBRE_PERIGO).cacheKey()
