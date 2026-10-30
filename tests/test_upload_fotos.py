r"""
Upload de Fotos (2026-10-30) -- `sigft/services/upload_fotos.py`.

O portal aqui é um dublê com estado: a tabela de imagens é uma lista de nomes,
a lixeira abre o diálogo e o CONFIRMAR tira a primeira linha. Ele prova a
ORDEM e as CONFERÊNCIAS do robô (excluir antes de subir, só dar ok com o nome
na tabela), não os seletores -- esses só a primeira execução real prova.
"""
import pytest

from sigft.services import upload_fotos as uf

from _openpyxl_de_verdade import openpyxl_de_verdade


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(uf.time, "sleep", lambda _s: None)


# ===========================================================================
# 1. O lote
# ===========================================================================
def test_agrupar_fotos_na_ordem_de_subida_e_lista_o_que_nao_segue_o_padrao(tmp_path):
    for nome in ("0071b.JPG", "0071.jpg", "0071a.png", "0072.jpeg", "leia-me.txt", "0071c.gif", "71.jpg"):
        (tmp_path / nome).write_bytes(b"x")

    grupos, ignorados = uf.agrupar_fotos(str(tmp_path))

    assert {q: [p.rsplit("/", 1)[-1] for p in c] for q, c in grupos.items()} == {
        "0071": ["0071.jpg", "0071a.png", "0071b.JPG"],
        "0072": ["0072.jpeg"],
    }
    assert sorted(ignorados) == ["0071c.gif", "71.jpg", "leia-me.txt"]


def test_ligar_as_fichas_pelo_final_e_nunca_adivinhar_ambiguo():
    grupos = {"0071": ["a"], "0072": ["b"], "0099": ["c"]}
    codigos = ["4500063671.0071", "'4500063671.72", "4500063671.0072", "4500099999.0072"]

    fichas, sem_ficha, ambiguas = uf.ligar_as_fichas(grupos, codigos)

    assert fichas == [("4500063671.0071", "0071", ["a"])]
    assert sem_ficha == ["0099"]
    assert ambiguas == {"0072": ["4500063671.0072", "4500099999.0072"]}


# ===========================================================================
# 2. O robô, contra o dublê
# ===========================================================================
class _Engine:
    def __init__(self, fotos=(), documentos=0):
        self.fotos = list(fotos)
        self.documentos = documentos
        self.dialogo = False
        self.ordem = []

    def contar(self, seletor):
        if seletor.startswith(uf.XPATH_TABELA_DE_IMAGENS + "//tr[.//td[normalize-space()="):
            return sum(1 for nome in self.fotos if f"'{nome}'" in seletor)
        if seletor == uf.XPATH_LINHAS_DE_IMAGEM:
            return len(self.fotos)
        if seletor == uf.XPATH_TABELA_DE_IMAGENS:
            return 1
        if seletor == uf.XPATH_LINHAS_DE_DOCUMENTO:
            return self.documentos
        if "CONFIRMAR" in seletor:
            return 1 if self.dialogo else 0
        return 0

    def scroll_to(self, _seletor):
        pass

    def click_raw(self, seletor):
        if "fa-trash" in seletor:
            self.dialogo = True
        elif "CONFIRMAR" in seletor and self.dialogo:
            self.ordem.append(("excluiu", self.fotos.pop(0)))
            self.dialogo = False


class _Portal:
    def __init__(self, engine):
        self.engine = engine

    def pesquisar_e_abrir(self, _pmib):
        return True


@pytest.fixture
def portal(monkeypatch):
    def _criar(fotos=(), documentos=0, sobe=True):
        engine = _Engine(fotos, documentos)

        def _subir(_portal, arquivos, _log=None):
            for descricao, caminho in arquivos:
                engine.ordem.append(("subiu", caminho, descricao))
                if sobe:
                    engine.fotos.append(caminho.rsplit("/", 1)[-1])
            return len(arquivos) if sobe else 0

        monkeypatch.setattr(uf.extrator, "esperar_a_ficha_abrir", lambda _p: True)
        monkeypatch.setattr(uf.extrator, "abrir_secao", lambda *_a, **_k: True)
        monkeypatch.setattr(uf.imagens, "subir_arquivos", _subir)
        return _Portal(engine)
    return _criar


NOVAS = ["/fotos/0071.JPG", "/fotos/0071a.JPG"]


def test_substituir_exclui_as_antigas_antes_de_subir_as_novas(portal):
    p = portal(fotos=["0071e.JPG", "0071c.JPG"], documentos=2)

    resultado = uf.processar_ficha(p, "4500063671.0071", "0071", NOVAS, uf.MODO_SUBSTITUIR)

    assert resultado.ok and resultado.tem_documentos
    assert p.engine.fotos == ["0071.JPG", "0071a.JPG"]
    assert [passo[0] for passo in p.engine.ordem] == ["excluiu", "excluiu", "subiu", "subiu"]
    assert p.engine.ordem[2][2] == "imagens - 0071"


def test_ficha_sem_foto_so_sobe_e_sem_documento_diz_isso(portal):
    p = portal(fotos=[], documentos=0)

    resultado = uf.processar_ficha(p, "4500063671.0071", "0071", NOVAS, uf.MODO_SUBSTITUIR)

    assert resultado.ok and not resultado.tem_documentos
    assert [passo[0] for passo in p.engine.ordem] == ["subiu", "subiu"]


def test_perguntar_e_pular_nao_toca_na_ficha(portal):
    p = portal(fotos=["0071.JPG"])
    perguntas = []

    def perguntar(pmib, quantas):
        perguntas.append((pmib, quantas))
        return uf.PULAR

    resultado = uf.processar_ficha(p, "4500063671.0071", "0071", NOVAS, uf.MODO_PERGUNTAR, perguntar)

    assert resultado.pulada and not resultado.ok
    assert perguntas == [("4500063671.0071", 1)]
    assert p.engine.ordem == []


def test_perguntar_e_adicionar_sobe_sem_excluir(portal):
    p = portal(fotos=["0071z.JPG"])

    resultado = uf.processar_ficha(p, "4500063671.0071", "0071", NOVAS, uf.MODO_PERGUNTAR,
                                   lambda *_a: uf.ADICIONAR)

    assert resultado.ok
    assert p.engine.fotos == ["0071z.JPG", "0071.JPG", "0071a.JPG"]


def test_foto_que_nao_aparece_na_tabela_nao_e_ok(portal):
    p = portal(fotos=[], sobe=False)

    resultado = uf.processar_ficha(p, "4500063671.0071", "0071", NOVAS)

    assert not resultado.ok
    assert "0071.JPG" in resultado.motivo and "0071a.JPG" in resultado.motivo


def test_lixeira_que_nao_exclui_para_a_ficha_sem_subir(portal):
    p = portal(fotos=["0071.JPG"])
    p.engine.click_raw = lambda _s: None  # o clique "pega", mas nada sai da tabela

    resultado = uf.processar_ficha(p, "4500063671.0071", "0071", NOVAS)

    assert not resultado.ok
    assert "excluir" in resultado.motivo
    assert p.engine.ordem == []


# ===========================================================================
# 3. A planilha, com arquivo de verdade
# ===========================================================================
def _status(tmp_path):
    caminho = tmp_path / "_STATUS_PMIB.xlsx"
    with openpyxl_de_verdade():
        from openpyxl import Workbook

        wb = Workbook()
        aba = wb.active
        aba.title = "Lista de Materiais"
        aba.append(["ITEM", "CÓDIGO PMIB", "DOCUMENTOS E IMAGENS"])
        aba.append([1, "4500063671.0071", ""])
        aba.append([2, "4500063671.0072", ""])
        wb.save(caminho)
    return caminho


def test_marcar_status_completo_e_incompleto_com_nota(tmp_path):
    pytest.importorskip("lxml")
    caminho = _status(tmp_path)
    resultados = [
        uf.ResultadoDaFicha("4500063671.0071", "0071", ok=True, tem_documentos=True),
        uf.ResultadoDaFicha("4500063671.0072", "0072", ok=True, tem_documentos=False),
        uf.ResultadoDaFicha("4500063671.0099", "0099", ok=False, motivo="falhou"),
    ]

    with openpyxl_de_verdade():
        quantas, recado = uf.marcar_status(str(caminho), resultados)
        from openpyxl import load_workbook

        aba = load_workbook(caminho)["Lista de Materiais"]

    assert quantas == 2, recado
    assert aba["C2"].value == "COMPLETO" and aba["C2"].comment is None
    assert aba["C3"].value == "INCOMPLETO"
    assert aba["C3"].comment.text == "Faltam documentos"


def test_ler_codigos_da_coluna_codigo_pmib(tmp_path):
    caminho = _status(tmp_path)

    with openpyxl_de_verdade():
        codigos = uf.ler_codigos(str(caminho))

    assert codigos == ["4500063671.0071", "4500063671.0072"]
