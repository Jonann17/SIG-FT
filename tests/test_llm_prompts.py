r"""
Testes unitários de `sigft.core.llm.prompts` (Checkpoint 3.5).

Complementa tests/test_llm_prompts_snapshot.py (que prova "idêntico ao
antigo", exercitando os 5 backends via `_FakeLLM`): este arquivo testa o
módulo `prompts.py` DIRETAMENTE, sem depender de nenhum backend, e cobre 3
frentes pedidas pelo checkpoint:

  (a) as constantes estáticas (`SYSTEM_CONDICOES`/`SYSTEM_TECH_SPECS`) batem
      exatamente com a fixture -- mesmo texto que os testes de snapshot já
      comparam indiretamente (via os backends), mas aqui testado como
      propriedade do PRÓPRIO módulo;
  (b) cada função de montagem (`montar_*`) interpola corretamente em cada
      parâmetro -- usando um marcador improvável (`"<<<...>>>"`) e
      confirmando que ele aparece no resultado, e que trechos FIXOS do
      texto continuam presentes;
  (c) o invariante do *Aceite* do checkpoint ("nenhum prompt >15 linhas
      dentro de `services/`", lido aqui como "nenhum literal de string com
      mais de 15 quebras de linha dentro dos 5 arquivos `*_backend.py`
      migrados" -- na época do CP 3.5 os backends ainda estavam na raiz, a
      mudança para `sigft/services/` é o CP 4.1): percorre a AST de cada um
      dos 5 arquivos, acha todo `ast.Constant` de `str` (inclusive os
      pedaços de texto literal DENTRO de f-strings -- `ast.walk` visita os
      nós `Constant` aninhados em `JoinedStr.values`) e falha se algum tiver
      mais de 15 quebras de linha. `sigft/core/llm/prompts.py` em si NÃO
      entra nesse invariante -- é justamente para onde o texto grande foi
      migrado, por design.

CP 4.1 (Fase 4, 1ª metade -- docs/refatoracao/PLANO_REFATORACAO.md):
`analyzer_backend.py` já foi movido -- o código real mora agora em
`sigft/services/analyzer.py`; o que sobrou na raiz é um shim de
compatibilidade cuja PRÓPRIA docstring (explicando o aliasing) passou a ter
mais de 15 quebras de linha. Sem apontar `ARQUIVOS_MIGRADOS` para o caminho
físico novo, o teste (c) abaixo FALHARIA contra o texto do shim -- um
literal que nada tem a ver com o invariante de prompts que este teste
audita; `sigft/services/analyzer.py` é o arquivo correto a auditar (maior
literal real: 2 quebras de linha). Os outros 4 (`cria_fichas`,
`upload_conditions`, `upload_tech_specs`, `autospec`) ainda não foram
movidos (2ª metade do CP 4.1, tarefa separada) -- continuam na raiz.
"""
import ast
import os

from sigft.core.llm import prompts

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "prompts")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ler_fixture(nome):
    caminho = os.path.join(FIXTURES_DIR, nome + ".txt")
    with open(caminho, "r", encoding="utf-8") as f:
        return f.read()


# =============================================================================
# (a) Constantes estáticas batem exatamente com a fixture.
# =============================================================================
def test_system_condicoes_bate_byte_a_byte_com_a_fixture():
    assert prompts.SYSTEM_CONDICOES == _ler_fixture("upload_conditions_system")


def test_system_tech_specs_bate_byte_a_byte_com_a_fixture():
    assert prompts.SYSTEM_TECH_SPECS == _ler_fixture("upload_tech_specs_system")


# =============================================================================
# (b) Cada função de montagem interpola nos lugares certos.
# =============================================================================
def test_montar_validar_ficha_interpola_mat_fab_str_fixed_str_vars():
    texto = prompts.montar_validar_ficha(
        "<<<MAT>>>", "<<<FAB>>>", "<<<STR_FIXED>>>", "<<<STR_VARS>>>"
    )

    assert "<<<MAT>>>" in texto
    assert "<<<FAB>>>" in texto
    assert "<<<STR_FIXED>>>" in texto
    assert "<<<STR_VARS>>>" in texto
    # trechos fixos do texto original continuam presentes
    assert "REGRAS DE VALIDAÇÃO:" in texto
    assert "4. REGRA DE OURO:" in texto
    assert "#Notes: Retorne sua resposta APENAS no formato JSON." in texto
    assert '"campos_fixos"' in texto
    assert '"campos_variaveis"' in texto


def test_montar_categorizar_pdm_interpola_instrucoes_lista_pdms_itens_texto():
    texto = prompts.montar_categorizar_pdm(
        "<<<INSTRUCOES>>>", "<<<LISTA_PDMS>>>", "<<<ITENS_TEXTO>>>"
    )

    assert "<<<INSTRUCOES>>>" in texto
    assert "<<<LISTA_PDMS>>>" in texto
    assert "<<<ITENS_TEXTO>>>" in texto
    assert "### MANUAL DE REGRAS (GRUPOS E CLASSES)" in texto
    assert "### LISTA DE PDMS FINAIS (ESCOLHA UM DESTES)" in texto
    assert "### ITENS PARA ANALISAR (EM LOTE):" in texto
    assert "Responda APENAS com a lista JSON. Não inclua texto antes ou depois." in texto


def test_montar_condicoes_user_interpola_dados_api_input_json():
    texto = prompts.montar_condicoes_user("<<<DADOS_API_INPUT_JSON>>>")

    assert texto == "Processar: <<<DADOS_API_INPUT_JSON>>>"


def test_montar_tech_specs_user_interpola_contexto_json_serializado():
    texto = prompts.montar_tech_specs_user("<<<CONTEXTO_JSON_SERIALIZADO>>>")

    assert "<<<CONTEXTO_JSON_SERIALIZADO>>>" in texto
    assert "DADOS DE ENTRADA:" in texto
    assert "Analise os dados abaixo referentes a um material técnico." in texto


def test_montar_autospec_interpola_todos_os_parametros():
    texto = prompts.montar_autospec(
        "<<<TXT_BRV>>>", "<<<FAB>>>", "<<<DESC_COMP>>>", "<<<CONTEXT>>>", "<<<DESC_LIST_TEXTO>>>"
    )

    assert "<<<TXT_BRV>>>" in texto
    assert "<<<FAB>>>" in texto
    assert "<<<DESC_COMP>>>" in texto
    assert "<<<CONTEXT>>>" in texto
    assert texto.endswith("<<<DESC_LIST_TEXTO>>>")  # concatenado no final, fora do f-string
    assert "Você é um Assistente Técnico Industrial." in texto
    assert "CAMPOS A PREENCHER (Retorne JSON {ID: Resposta}):" in texto


def test_montar_autospec_context_falsy_cai_no_texto_padrao():
    # `{context if context else "Nenhuma informação disponível."}` no
    # original -- testa os 2 valores falsy possíveis (string vazia / None).
    texto_vazio = prompts.montar_autospec("Motor X", "Fab Y", "Desc", "", "")
    assert "Nenhuma informação disponível." in texto_vazio

    texto_none = prompts.montar_autospec("Motor X", "Fab Y", "Desc", None, "")
    assert "Nenhuma informação disponível." in texto_none


# =============================================================================
# (c) Invariante de Aceite: nenhum literal de string >15 linhas dentro dos 5
#     arquivos *_backend.py migrados.
# =============================================================================
ARQUIVOS_MIGRADOS = [
    "sigft/services/analyzer.py",  # CP 4.1: movido de analyzer_backend.py
    "cria_fichas_no_pmib_v1_backend.py",
    "upload_conditions_backend.py",
    "upload_tech_specs_backend.py",
    "autospec_backend.py",
]

LIMITE_LINHAS = 15


def _maior_literal_de_string_em_linhas(caminho):
    """Percorre a AST do arquivo e devolve o maior número de quebras de
    linha (`\n`) dentro de um único literal `str` (`ast.Constant`) --
    inclusive os pedaços de texto literal dentro de f-strings, que `ast`
    representa como `Constant`s aninhados em `JoinedStr.values` (visitados
    normalmente por `ast.walk`)."""
    with open(caminho, "r", encoding="utf-8") as f:
        arvore = ast.parse(f.read(), filename=caminho)

    maior = 0
    for node in ast.walk(arvore):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            n_linhas = node.value.count("\n")
            if n_linhas > maior:
                maior = n_linhas
    return maior


def test_nenhum_literal_de_string_maior_que_15_linhas_nos_5_arquivos_migrados():
    for nome_arquivo in ARQUIVOS_MIGRADOS:
        caminho = os.path.join(REPO_ROOT, nome_arquivo)
        maior = _maior_literal_de_string_em_linhas(caminho)
        assert maior <= LIMITE_LINHAS, (
            f"{nome_arquivo} tem um literal de string com {maior} quebras de "
            f"linha (> {LIMITE_LINHAS}) -- o Aceite do CP 3.5 exige que o "
            "texto grande more só em sigft/core/llm/prompts.py"
        )


def test_prompts_py_e_o_unico_lugar_com_literais_grandes_por_contraste():
    """Contraste explícito com o teste acima: `prompts.py` (fora do escopo
    do invariante -- é justamente para onde o texto migrou) TEM, sim,
    literais grandes -- prova que o invariante acima é significativo (não
    passa "por acidente" por o parser não achar nada em lugar nenhum)."""
    caminho = os.path.join(REPO_ROOT, "sigft", "core", "llm", "prompts.py")
    maior = _maior_literal_de_string_em_linhas(caminho)
    assert maior > LIMITE_LINHAS
