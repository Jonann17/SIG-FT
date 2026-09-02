r"""Tradução dos PDMs Modificados para inglês (2026-08-28).

**Por que existe** (pedido do usuário): o SIG-FT tem dois templates de ficha —
PT-BR e inglês — mas as características técnicas coladas dentro deles vêm
sempre da mesma pasta de *PDMs Modificados*, que está em português. Hoje a
tradução dessas perguntas é feita **na mão**, ficha a ficha.

O desenho aprovado: traduzir a pasta inteira uma vez, guardar numa pasta
paralela, e o montador da ficha escolhe a pasta pelo idioma do template.

**O que este arquivo NÃO testa:** o motor de tradução de verdade (IA ou
`deep_translator`). Ele é injetado, sempre. Um teste que dependesse da
internet mediria a rede, não o código — e não rodaria na suíte.
"""
import json
import os

import pytest

from sigft.services import traducao_pdm as tp


def _falso(pares):
    """Motor de tradução falso: devolve 'EN:<original>' para cada texto."""
    def traduzir(textos):
        return [pares.get(t, f"EN:{t}") for t in textos]
    return traduzir


# =============================================================================
# A. Quebrar a pergunta em partes — o que traduz e o que NÃO traduz
# =============================================================================
def test_o_numero_da_pergunta_nao_e_traduzido():
    """`"1 - Pressão de trabalho (bar):"` — o `1 - ` é numeração da lista, e
    mandá-lo para um tradutor é pedir para ele inventar."""
    prefixo, miolo, sufixo = tp.partes_da_pergunta("1 - Pressão de trabalho (bar):")
    assert prefixo == "1 - "
    assert miolo == "Pressão de trabalho (bar)"
    assert sufixo == ":"


def test_pergunta_sem_numeracao_tambem_funciona():
    prefixo, miolo, sufixo = tp.partes_da_pergunta("Material de fabricação")
    assert prefixo == ""
    assert miolo == "Material de fabricação"
    assert sufixo == ""


def test_numero_de_dois_digitos():
    prefixo, miolo, _ = tp.partes_da_pergunta("12 - Vazão (l/min):")
    assert prefixo == "12 - "
    assert miolo == "Vazão (l/min)"


def test_a_montagem_de_volta_devolve_a_frase_inteira():
    original = "7 - Tensão de isolamento (kV):"
    prefixo, miolo, sufixo = tp.partes_da_pergunta(original)
    assert prefixo + miolo + sufixo == original


def test_texto_vazio_nao_quebra():
    assert tp.partes_da_pergunta(None) == ("", "", "")
    assert tp.partes_da_pergunta("   ") == ("", "", "")


# =============================================================================
# B. O glossário — corrigir uma vez e valer sempre
# =============================================================================
def test_glossario_vazio_quando_o_arquivo_nao_existe(tmp_path):
    assert tp.carregar_glossario(str(tmp_path / "nao_existe.txt")) == {}


def test_glossario_le_pares_pt_igual_en(tmp_path):
    arquivo = tmp_path / "g.txt"
    arquivo.write_text("vazão = flow rate\niçamento = lifting\n", encoding="utf-8")
    assert tp.carregar_glossario(str(arquivo)) == {
        "vazão": "flow rate", "içamento": "lifting"}


def test_glossario_ignora_comentario_e_linha_em_branco(tmp_path):
    arquivo = tmp_path / "g.txt"
    arquivo.write_text("# como usar\n\nvazão = flow rate\n\n# fim\n", encoding="utf-8")
    assert tp.carregar_glossario(str(arquivo)) == {"vazão": "flow rate"}


def test_glossario_aguenta_ANSI_do_bloco_de_notas(tmp_path):
    """Mesma lição do `.txt` da conferência do AutoSpec: o arquivo é para ser
    editado à mão, e o Bloco de Notas ainda oferece ANSI no 'Salvar como'."""
    arquivo = tmp_path / "g.txt"
    arquivo.write_bytes("vazão = flow rate\n".encode("cp1252"))
    assert tp.carregar_glossario(str(arquivo)) == {"vazão": "flow rate"}


def test_frase_inteira_no_glossario_NAO_chama_o_motor(tmp_path):
    """A correção do usuário vence o motor — é o ponto do glossário."""
    chamou = []

    def traduzir(textos):
        chamou.extend(textos)
        return [f"EN:{t}" for t in textos]

    glossario = {"Pressão de trabalho (bar)": "Working pressure (bar)"}
    saida = tp.traduzir_textos(["1 - Pressão de trabalho (bar):"], traduzir, glossario)
    assert saida == ["1 - Working pressure (bar):"]
    assert chamou == [], "o glossário deveria ter resolvido sem o motor"


def test_o_glossario_cria_um_arquivo_de_exemplo_explicando_o_uso(tmp_path):
    caminho = tp.criar_glossario_exemplo(str(tmp_path))
    texto = open(caminho, encoding="utf-8").read()
    assert "=" in texto
    assert "#" in texto  # tem instrução comentada
    assert os.path.dirname(caminho) == str(tmp_path)


def test_criar_glossario_NAO_sobrescreve_o_que_o_usuario_editou(tmp_path):
    caminho = tp.criar_glossario_exemplo(str(tmp_path))
    with open(caminho, "a", encoding="utf-8") as fh:
        fh.write("vazão = flow rate\n")
    tp.criar_glossario_exemplo(str(tmp_path))
    assert "flow rate" in open(caminho, encoding="utf-8").read()


# =============================================================================
# C. Cache — o mesmo texto não é traduzido duas vezes
# =============================================================================
def test_texto_repetido_vai_UMA_vez_ao_motor():
    """Perguntas se repetem entre PDMs ('Fabricante', 'Modelo', 'Peso'). Sem
    dedupe, uma pasta grande paga a mesma tradução dezenas de vezes — e, no
    caminho da `deep_translator`, cada item custa 1 segundo de espera."""
    chamou = []

    def traduzir(textos):
        chamou.extend(textos)
        return [f"EN:{t}" for t in textos]

    entrada = ["1 - Peso (kg):", "2 - Peso (kg):", "3 - Vazão (l/min):"]
    saida = tp.traduzir_textos(entrada, traduzir, {})
    assert chamou == ["Peso (kg)", "Vazão (l/min)"]
    assert saida == ["1 - EN:Peso (kg):", "2 - EN:Peso (kg):", "3 - EN:Vazão (l/min):"]


def test_o_cache_sobrevive_entre_execucoes(tmp_path):
    cache = tp.Cache(str(tmp_path))
    cache.guardar("Vazão (l/min)", "Flow rate (l/min)")
    cache.salvar()

    outro = tp.Cache(str(tmp_path))
    assert outro.buscar("Vazão (l/min)") == "Flow rate (l/min)"


def test_cache_corrompido_nao_derruba_a_traducao(tmp_path):
    (tmp_path / tp.NOME_CACHE).write_text("{isto não é json", encoding="utf-8")
    assert tp.Cache(str(tmp_path)).buscar("qualquer") is None


# =============================================================================
# D. Traduzir a pasta inteira
# =============================================================================
def _pdm_falso(pasta, nome, perguntas):
    """Um PDM Modificado como `salvar_tabela_formatada` o grava: descrição na
    coluna 1 (mesclada 1–10), resposta na 11 (mesclada 11–20), vazia."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    for i, pergunta in enumerate(perguntas, start=1):
        ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=10)
        ws.cell(row=i, column=1, value=pergunta)
        ws.merge_cells(start_row=i, start_column=11, end_row=i, end_column=20)
    caminho = os.path.join(pasta, nome)
    wb.save(caminho)
    return caminho


@pytest.fixture
def openpyxl_real():
    """A suíte stuba o openpyxl; estes testes precisam do de verdade."""
    import importlib
    import sys
    guardado = sys.modules.get("openpyxl")
    for nome in [n for n in list(sys.modules) if n.startswith("openpyxl")]:
        del sys.modules[nome]
    try:
        modulo = importlib.import_module("openpyxl")
        if not hasattr(modulo, "Workbook") or "Mock" in type(modulo).__name__:
            pytest.skip("openpyxl real nao disponivel")
        yield modulo
    finally:
        for nome in [n for n in list(sys.modules) if n.startswith("openpyxl")]:
            del sys.modules[nome]
        if guardado is not None:
            sys.modules["openpyxl"] = guardado


def test_a_pasta_traduzida_ganha_um_arquivo_por_PDM(tmp_path, openpyxl_real):
    origem, destino = tmp_path / "pt", tmp_path / "en"
    origem.mkdir()
    _pdm_falso(str(origem), "PDM_1234_001_formatado.xlsx", ["1 - Vazão (l/min):"])
    _pdm_falso(str(origem), "PDM_5678_002_formatado.xlsx", ["1 - Peso (kg):"])

    linhas = list(tp.traduzir_pasta(str(origem), str(destino), traduzir=_falso({})))
    gerados = sorted(os.listdir(destino))
    assert "PDM_1234_001_formatado.xlsx" in gerados
    assert "PDM_5678_002_formatado.xlsx" in gerados
    assert any("2" in l and "PDM" in l for l in linhas)


def test_o_NOME_do_arquivo_e_preservado(tmp_path, openpyxl_real):
    """O montador acha o PDM por SUBSTRING do id (`PDM_1234_001`) no nome do
    arquivo. Renomear na tradução quebraria o casamento em silêncio."""
    origem, destino = tmp_path / "pt", tmp_path / "en"
    origem.mkdir()
    _pdm_falso(str(origem), "PDM_1234_001_formatado.xlsx", ["1 - Vazão:"])
    list(tp.traduzir_pasta(str(origem), str(destino), traduzir=_falso({})))
    assert os.path.exists(destino / "PDM_1234_001_formatado.xlsx")


def test_o_conteudo_traduzido_fica_na_MESMA_celula(tmp_path, openpyxl_real):
    """O montador lê `cell(i, 1)`. Traduzir para outra célula geraria fichas
    em branco, e ninguém perceberia até abrir uma."""
    origem, destino = tmp_path / "pt", tmp_path / "en"
    origem.mkdir()
    _pdm_falso(str(origem), "PDM_1234_001_formatado.xlsx",
               ["1 - Vazão (l/min):", "2 - Peso (kg):"])
    list(tp.traduzir_pasta(str(origem), str(destino),
                           traduzir=_falso({"Vazão (l/min)": "Flow rate (l/min)",
                                            "Peso (kg)": "Weight (kg)"})))
    ws = openpyxl_real.load_workbook(destino / "PDM_1234_001_formatado.xlsx").active
    assert ws.cell(row=1, column=1).value == "1 - Flow rate (l/min):"
    assert ws.cell(row=2, column=1).value == "2 - Weight (kg):"


def test_linha_vazia_no_meio_nao_vira_traducao(tmp_path, openpyxl_real):
    origem, destino = tmp_path / "pt", tmp_path / "en"
    origem.mkdir()
    _pdm_falso(str(origem), "PDM_1234_001_formatado.xlsx",
               ["1 - Vazão:", None, "3 - Peso:"])
    list(tp.traduzir_pasta(str(origem), str(destino), traduzir=_falso({})))
    ws = openpyxl_real.load_workbook(destino / "PDM_1234_001_formatado.xlsx").active
    assert ws.cell(row=2, column=1).value in (None, "")


def test_pasta_de_origem_vazia_avisa_em_vez_de_fingir_sucesso(tmp_path, openpyxl_real):
    origem, destino = tmp_path / "pt", tmp_path / "en"
    origem.mkdir()
    linhas = list(tp.traduzir_pasta(str(origem), str(destino), traduzir=_falso({})))
    assert any("nenhum" in l.lower() for l in linhas)


def test_um_arquivo_ilegivel_nao_derruba_a_pasta(tmp_path, openpyxl_real):
    origem, destino = tmp_path / "pt", tmp_path / "en"
    origem.mkdir()
    (origem / "quebrado.xlsx").write_text("isto nao e um xlsx")
    _pdm_falso(str(origem), "PDM_1234_001_formatado.xlsx", ["1 - Vazão:"])
    linhas = list(tp.traduzir_pasta(str(origem), str(destino), traduzir=_falso({})))
    assert os.path.exists(destino / "PDM_1234_001_formatado.xlsx")
    assert any("quebrado.xlsx" in l for l in linhas)


# =============================================================================
# E. A fronteira
# =============================================================================
def test_o_servico_NAO_importa_tkinter():
    import ast
    import inspect
    arvore = ast.parse(inspect.getsource(tp))
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.update(a.name.split(".")[0] for a in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module.split(".")[0])
    assert "tkinter" not in importados and "customtkinter" not in importados
