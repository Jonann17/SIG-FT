r"""A ficha em INGLÊS no resto do aplicativo (auditoria de 2026-09-03).

**Por que esta auditoria existe.** Ao corrigir o `analyzer`, que procurava o
título da seção de especificações só em português, o usuário levantou a
pergunta certa: *"e o que mais pode quebrar com ficha em inglês?"*

A varredura foi por AST — todo literal em português usado numa COMPARAÇÃO
(`==`, `in`, `startswith`) dentro de `sigft/`, ignorando a UI (que fala
português com o usuário brasileiro, e deve mesmo). Deu 60 ocorrências, e a
maioria era **alarme falso**, o que só se descobre olhando:

| Achado | Veredito |
|---|---|
| `upload_conditions`: `== "SIM"` / `== "NÃO"` / `== "Nocivo"` | **falso.** Não vêm do texto da ficha: são derivados de QUAL CÉLULA de caixa de seleção está marcada (`if get_val('P69'): "NÃO"`). Vocabulário interno do app |
| `cria_fichas`: `== 'não reparável'` / `== 'especial'` | **falso.** Vêm da planilha de status e do prompt de IA, que respondem em português por contrato |
| `pmib_manager`: `'CÓDIGO PMIB'`, `'VALORIZAÇÃO'`, `'ÍNDICE DE EMISSÃO'` | **falso.** São cabeçalhos da planilha da Itaipu, sempre em português |
| `upload_conditions`: `'DESCRIÇÃO'`, `'CONDIÇÕES'` | **falso.** Colunas de DataFrame, não células de ficha |

Sobraram DOIS defeitos reais, e são estes que este arquivo tranca.
"""
import ast
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]


# =============================================================================
# 1. O NOME DA ABA, hardcoded em dois módulos
# =============================================================================
# `upload_conditions.extrair_dados_brutos_excel` e `AutoSpecCore.fill_save`
# exigiam a aba `"Ficha Técnica Padrão"` pelo nome literal. Uma ficha em
# inglês tem a aba `"Standard Technical Sheet"` — e desde 2026-09-03 é o
# PRÓPRIO SIG-FT que a nomeia assim, a pedido do usuário.
#
# Ou seja: o rename que eu implementei de manhã quebraria, à tarde, o upload
# de condições e o preenchimento pelo AutoSpec. É o tipo de defeito que só
# aparece quando alguém percorre o fluxo inteiro com uma ficha em inglês — e
# um deles falhava EM SILÊNCIO (`return None`, sem dizer por quê).

MODULOS_QUE_ABREM_A_FICHA = [
    "sigft/services/upload_conditions.py",
    "sigft/services/autospec.py",
]


@pytest.mark.parametrize("caminho", MODULOS_QUE_ABREM_A_FICHA)
def test_nenhum_modulo_exige_o_nome_da_aba_EM_PORTUGUES(caminho):
    """O nome literal não pode aparecer em comparação nem em indexação.

    Comentário e docstring podem citá-lo à vontade — o que não pode é o
    código DEPENDER dele."""
    fonte = (RAIZ / caminho).read_text(encoding="utf-8")
    arvore = ast.parse(fonte)

    usos = []
    for no in ast.walk(arvore):
        # `wb["Ficha Técnica Padrão"]`
        if isinstance(no, ast.Subscript) and isinstance(no.slice, ast.Constant) \
                and no.slice.value == "Ficha Técnica Padrão":
            usos.append(("indexacao", no.lineno))
        # `"Ficha Técnica Padrão" not in wb.sheetnames`
        if isinstance(no, ast.Compare):
            for lado in [no.left, *no.comparators]:
                if isinstance(lado, ast.Constant) and lado.value == "Ficha Técnica Padrão":
                    usos.append(("comparacao", no.lineno))

    assert not usos, (
        f"{caminho} ainda depende do nome da aba em portugues: {usos}. "
        "Uma ficha em ingles tem a aba 'Standard Technical Sheet'.")


@pytest.mark.parametrize("caminho", MODULOS_QUE_ABREM_A_FICHA)
def test_os_modulos_usam_a_UNICA_implementacao_de_resolver_a_aba(caminho):
    """Princípio nº 1 do projeto: uma implementação por conceito. Três
    módulos resolvendo 'qual aba é a ficha' por conta própria é a receita
    para os três divergirem — foi assim que o `CONFIG_MAP` acabou duplicado
    e com ranges diferentes antes do CP 2.4."""
    fonte = (RAIZ / caminho).read_text(encoding="utf-8")
    assert "nome_da_aba_da_ficha" in fonte


def test_a_implementacao_mora_no_layout_da_ficha():
    """`ficha_layout.py` é, por docstring própria, a 'fonte única do layout da
    Ficha Técnica Padrão'. O nome da aba é layout."""
    from sigft.core.rpa import ficha_layout

    assert hasattr(ficha_layout, "nome_da_aba_da_ficha")
    assert hasattr(ficha_layout, "NOMES_DA_ABA_DA_FICHA")


def test_pdm_continua_exportando_o_nome_de_sempre():
    """`pdm.nome_da_aba_da_ficha` existe desde 28/08 e é usado pelo montador
    e pelos testes. Mudar de casa não pode quebrar quem já importava."""
    from sigft.core.rpa import ficha_layout
    from sigft.services import pdm

    assert pdm.nome_da_aba_da_ficha is ficha_layout.nome_da_aba_da_ficha
    assert pdm.NOMES_DA_ABA_DA_FICHA == ficha_layout.NOMES_DA_ABA_DA_FICHA


# =============================================================================
# 2. "Not applicable" — a resposta que o app não reconhece
# =============================================================================
# Três listas independentes catalogam as formas de "isto não se aplica":
#
#   analyzer.FORBIDDEN_NA_STRINGS ......... PT
#   autospec (RESPOSTAS_VAZIAS) ........... PT
#   upload_conditions (_campos_vazios) .... PT + ES
#
# Nenhuma tem INGLÊS. O fornecedor estrangeiro — que é a razão de a ficha em
# inglês existir — escreve "Not applicable", e o efeito é o pior possível: o
# `analyzer` conta isso como RESPOSTA VÁLIDA, a ficha pontua como se tivesse
# sido preenchida, e o campo vazio chega ao portal.
#
# Acrescentar sinônimos é ganho puro: não muda nada em português.

FORMAS_EM_INGLES = ["not applicable", "does not apply", "not required"]


@pytest.mark.parametrize("forma", FORMAS_EM_INGLES)
def test_o_analyzer_reconhece_nao_aplicavel_em_INGLES(forma):
    from sigft.services import analyzer

    assert forma in analyzer.FORBIDDEN_NA_STRINGS


@pytest.mark.parametrize("forma", FORMAS_EM_INGLES)
def test_o_upload_de_condicoes_reconhece_nao_aplicavel_em_INGLES(forma):
    """`campos_em_branco_na_origem` é quem avisa o usuário 'este campo foi
    para o portal vazio'. Sem o inglês, ele não avisa."""
    from sigft.services import upload_conditions

    vazios = upload_conditions.campos_em_branco_na_origem(
        {campo: forma for campo in upload_conditions.CAMPOS_QUE_O_PORTAL_EXIGE})
    assert set(vazios) == set(upload_conditions.CAMPOS_QUE_O_PORTAL_EXIGE), (
        f"{forma!r} passou como resposta de verdade")


def test_o_portugues_continua_reconhecido():
    """A guarda contra 'consertei o inglês e quebrei o português'."""
    from sigft.services import analyzer

    for forma in ("n/a", "não aplicável", "nao aplicavel", "não se aplica"):
        assert forma in analyzer.FORBIDDEN_NA_STRINGS


def test_uma_resposta_de_VERDADE_nao_vira_nao_aplicavel():
    """O risco de encher a lista: engolir resposta legítima. 'Aplicável' e
    'Applicable' são respostas, e o oposto do que a lista cataloga."""
    from sigft.services import analyzer

    for forma in ("aplicável", "applicable", "aço inox 316", "stainless steel"):
        assert forma not in analyzer.FORBIDDEN_NA_STRINGS
