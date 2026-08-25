r"""
Testes do Checkpoint 4.1 (1ª metade) — shims de compatibilidade para os
backends movidos para `sigft/services/` (ver
docs/refatoracao/PLANO_REFATORACAO.md, Fase 4 -> CP 4.1, e
`sigft/services/__init__.py`).

Escopo desta 1ª metade (6 dos 12 módulos do checkpoint, nesta ordem — um
commit por módulo): `apagar_lmr` -> `lmr` -> `search` -> `pdm` ->
`translator` -> `analyzer`. A 2ª metade (`autospec` -> `cria_fichas` ->
`upload_conditions` -> `tech_specs` -> `ficha_duplicada` como está ->
`pmib_manager`) é uma tarefa separada; a tabela `MODULOS_SHIM` abaixo foi
desenhada para que acrescentá-la seja só adicionar linhas (ver comentário
junto da tabela).

Para cada módulo, cobre os 4 ângulos pedidos pelo checkpoint:
  1. o nome ANTIGO (raiz, ex. `apagar_lmr_backend`) continua importável;
  2. `<nome_antigo> is <sigft.services.novo>` — IDENTIDADE de objeto. É o
     que o shim GARANTE (aliasing de módulo, `sys.modules[__name__] =
     <módulo novo>` — ver docstring de cada `*_backend.py` na raiz) e o que
     `from ... import *` NÃO daria (criaria 2 namespaces distintos);
  3. pelo menos um símbolo público conhecido de cada módulo continua
     acessível pelo nome antigo (`analyzer_backend` tem 2: a classe
     principal e o `CONFIG_MAP` importado de `core.rpa.ficha_layout`);
  4. o módulo novo é importável DIRETAMENTE por `sigft.services.<nome>`,
     sem passar pelo nome antigo.

Além disso: uma demonstração concreta (não só estrutural) de por que
aliasing foi escolhido em vez de `import *` — um `monkeypatch.setattr` pelo
nome ANTIGO precisa ficar visível pelo nome NOVO, exatamente o cenário que
os ~15 arquivos de teste que importam os backends pelos nomes antigos
dependem implicitamente — e 2 canários comportamentais leves (instanciar
uma classe / chamar uma função pura através do nome antigo) provando que o
shim não só "parece" certo, funciona de ponta a ponta.

`tests/test_smoke_imports.py` cobre o import dos 12 módulos (incluindo
estes 6, pelos nomes antigos) e continua passando sem edição — este arquivo
é mais específico: prova a MECÂNICA do shim (identidade de objeto), que o
smoke de importação não verifica.
"""
import importlib
import pathlib

import pytest


# =============================================================================
# Tabela única (nome_antigo, nome_novo, atributo_publico) — fonte de verdade
# deste arquivo. `nome_novo` é o sufixo dentro de `sigft.services.<nome_novo>`
# (não um caminho de arquivo) — quem quiser o caminho físico usa
# `sigft/services/<nome_novo>.py`, mesma tabela do checkpoint no plano.
#
# Um `(nome_antigo, nome_novo)` pode aparecer mais de uma vez, uma linha por
# atributo público verificado — é o caso de `analyzer_backend`, que tem 2
# símbolos públicos citados explicitamente no checkpoint (`DatasheetAnalyzer`
# e `CONFIG_MAP`, este último só IMPORTADO por analyzer, não definido nele —
# ver sigft/core/rpa/ficha_layout.py, CP 2.4).
#
# Para a 2ª metade (tarefa separada), bastará acrescentar linhas como as
# abaixo -- `nome_novo`/nome de arquivo de destino ficam a critério de quem
# executar aquele checkpoint (o plano só fixa a ORDEM de módulos, não o
# nome de arquivo final); os nomes de classe já são reais, conferidos por
# grep em cada arquivo nesta sessão:
#   ("autospec_backend", "autospec", "AutoSpecCore"),
#   ("cria_fichas_no_pmib_v1_backend", "cria_fichas", "DataManager"),          # também tem GeminiCategorizer/AutomacaoPMIB
#   ("upload_conditions_backend", "upload_conditions", "ConditionsProcessor"),  # também tem UploadAutomation
#   ("upload_tech_specs_backend", "tech_specs", "TechSpecsProcessor"),          # também tem TechSpecsAutomation/TechSpecsController
#   ("upload_ficha_duplicada", "ficha_duplicada", "GerenciadorFilaPMIB"),       # "como está" -- ver Fase 4 -> CP 4.1 e Fase 6
#   ("pmib_manager_backend", "pmib_manager", "PMIBManager"),
# nenhuma outra mudança neste arquivo é necessária -- todos os testes abaixo
# são parametrizados a partir desta tabela.
# =============================================================================
MODULOS_SHIM = [
    ("apagar_lmr_backend", "apagar_lmr", "ApagarLMRAutomation"),
    ("lmr_backend", "lmr", "LMRAutomation"),
    ("search_pmib_backend", "search", "PMIBSearcher"),
    ("pdm_backend", "pdm", "extrair_pdm_id"),
    ("translator_backend", "translator", "TechnicalTranslator"),
    ("analyzer_backend", "analyzer", "DatasheetAnalyzer"),
    ("analyzer_backend", "analyzer", "CONFIG_MAP"),
    # --- 2ª metade do CP 4.1 ---
    ("autospec_backend", "autospec", "AutoSpecCore"),
    ("cria_fichas_no_pmib_v1_backend", "cria_fichas", "GeminiCategorizer"),
    ("cria_fichas_no_pmib_v1_backend", "cria_fichas", "AutomacaoPMIB"),
    ("cria_fichas_no_pmib_v1_backend", "cria_fichas", "DataManager"),
    ("upload_conditions_backend", "upload_conditions", "ConditionsProcessor"),
    ("upload_tech_specs_backend", "tech_specs", "TechSpecsProcessor"),
    ("pmib_manager_backend", "pmib_manager", "PMIBManager"),
]

# Módulos únicos desta 1ª metade (sem repetição), na ordem do checkpoint —
# usado pelo teste de "honestidade" abaixo e para IDs de teste legíveis.
_MODULOS_UNICOS_1A_METADE = [
    "apagar_lmr_backend",
    "lmr_backend",
    "search_pmib_backend",
    "pdm_backend",
    "translator_backend",
    "analyzer_backend",
]

# 2ª metade do CP 4.1 — completa os 12 módulos do checkpoint.
_MODULOS_UNICOS_2A_METADE = [
    "autospec_backend",
    "cria_fichas_no_pmib_v1_backend",
    "upload_conditions_backend",
    "upload_tech_specs_backend",
    "pmib_manager_backend",
]

# Os 12 do checkpoint, na ordem em que o plano os lista.
_MODULOS_UNICOS = _MODULOS_UNICOS_1A_METADE + _MODULOS_UNICOS_2A_METADE


def _ids(tabela):
    return [f"{nome_antigo}::{atributo}" for nome_antigo, _nome_novo, atributo in tabela]


# =============================================================================
# 1. O nome ANTIGO continua importável.
# =============================================================================
@pytest.mark.parametrize("nome_antigo,nome_novo,atributo", MODULOS_SHIM, ids=_ids(MODULOS_SHIM))
def test_nome_antigo_continua_importavel(nome_antigo, nome_novo, atributo):
    modulo_antigo = importlib.import_module(nome_antigo)
    assert modulo_antigo is not None


# =============================================================================
# 2. Identidade de objeto: nome antigo e `sigft.services.<novo>` são o MESMO
#    módulo — é o que o aliasing garante e `from ... import *` não daria.
# =============================================================================
@pytest.mark.parametrize("nome_antigo,nome_novo,atributo", MODULOS_SHIM, ids=_ids(MODULOS_SHIM))
def test_shim_e_o_mesmo_objeto_de_modulo_que_sigft_services(nome_antigo, nome_novo, atributo):
    modulo_antigo = importlib.import_module(nome_antigo)
    modulo_novo = importlib.import_module(f"sigft.services.{nome_novo}")
    assert modulo_antigo is modulo_novo


# =============================================================================
# 3. Símbolo público conhecido continua acessível pelo nome antigo.
# =============================================================================
@pytest.mark.parametrize("nome_antigo,nome_novo,atributo", MODULOS_SHIM, ids=_ids(MODULOS_SHIM))
def test_simbolo_publico_acessivel_pelo_nome_antigo(nome_antigo, nome_novo, atributo):
    modulo_antigo = importlib.import_module(nome_antigo)
    assert hasattr(modulo_antigo, atributo), (
        f"{nome_antigo}.{atributo} não existe -- shim quebrado ou atributo "
        "renomeado durante a mudança de MODULOS_SHIM"
    )
    assert getattr(modulo_antigo, atributo) is not None


# =============================================================================
# 4. O módulo novo é importável DIRETAMENTE por `sigft.services.<nome>`.
# =============================================================================
@pytest.mark.parametrize("nome_antigo,nome_novo,atributo", MODULOS_SHIM, ids=_ids(MODULOS_SHIM))
def test_modulo_novo_importavel_diretamente_por_sigft_services(nome_antigo, nome_novo, atributo):
    modulo_novo = importlib.import_module(f"sigft.services.{nome_novo}")
    assert modulo_novo is not None
    assert hasattr(modulo_novo, atributo)


# =============================================================================
# Honestidade: garante que MODULOS_SHIM cobre exatamente os módulos que ainda
# existem (nem a mais, nem a menos) -- mesmo padrão de
# tests/test_rpa_sleep_constants.py::test_todas_as_constantes_pausa_de_portal_estao_cobertas_pelo_teste.
# =============================================================================
def test_todos_os_modulos_do_checkpoint_estao_cobertos_pela_tabela():
    """Eram 12 no CP 4.1; são 11 desde o CP 5.5.

    `upload_ficha_duplicada` saiu em 2026-08-25 com o Selenium: ele era o
    shim do módulo ANTIGO de ficha duplicada, que a Fase 6 substituiu por
    `services/duplicadas*.py`. O número aqui é derivado da tabela, e não
    escrito à mão, justamente para a próxima remoção não exigir editar dois
    lugares -- mas o `assert` do total fica, porque é ele que impede alguém
    apagar uma linha da tabela sem perceber."""
    nomes_na_tabela = {nome_antigo for nome_antigo, _nome_novo, _atributo in MODULOS_SHIM}
    assert nomes_na_tabela == set(_MODULOS_UNICOS)
    assert len(_MODULOS_UNICOS) == 11


def test_nenhum_backend_pesado_sobrou_na_raiz_fora_dos_shims():
    """Aceite do CP 4.1: depois dos 12 módulos migrados, o único `.py` de
    peso que resta na raiz é `frontend.py` (a quebra dele em views é a Fase
    7). Todo o resto tem que ser shim de poucas linhas -- se um arquivo da
    raiz voltar a ter código de verdade, este teste denuncia."""
    raiz = pathlib.Path(__file__).resolve().parent.parent
    for nome_antigo in _MODULOS_UNICOS:
        caminho = raiz / f"{nome_antigo}.py"
        assert caminho.is_file(), f"{caminho} sumiu -- o shim precisa existir"
        linhas = caminho.read_text(encoding="utf-8").splitlines()
        codigo = [
            linha for linha in linhas
            if linha.strip() and not linha.lstrip().startswith("#")
        ]
        # docstring + 3 linhas de aliasing; folga generosa, mas longe das
        # centenas de linhas que cada backend tinha antes.
        assert len(codigo) < 40, f"{caminho} tem {len(codigo)} linhas de código -- virou shim mesmo?"


def test_modulos_desta_1a_metade_nao_reaparecem_como_backend_pesado_na_raiz_sem_shim():
    # Canário de digitação: cada `nome_novo` usado em MODULOS_SHIM deve ser
    # ÚNICO por `nome_antigo` (um backend não pode ter migrado para 2
    # destinos diferentes por engano).
    destino_por_origem = {}
    for nome_antigo, nome_novo, _atributo in MODULOS_SHIM:
        if nome_antigo in destino_por_origem:
            assert destino_por_origem[nome_antigo] == nome_novo, (
                f"{nome_antigo} aparece na tabela apontando para 2 destinos "
                f"diferentes: {destino_por_origem[nome_antigo]!r} e {nome_novo!r}"
            )
        destino_por_origem[nome_antigo] = nome_novo


# =============================================================================
# Demonstração concreta do PORQUÊ do aliasing (não só a identidade
# estrutural acima): um monkeypatch pelo nome ANTIGO -- o padrão usado por
# vários arquivos de teste deste repositório -- só tem efeito sobre o código
# real (que roda a partir de `sigft.services`) porque os dois nomes
# compartilham o MESMO `__dict__` de módulo. Com `from ... import *` o shim
# teria seu PRÓPRIO namespace, e este teste FALHARIA.
# =============================================================================
def test_monkeypatch_pelo_nome_antigo_e_visivel_pelo_nome_novo(monkeypatch):
    import apagar_lmr_backend
    from sigft.services import apagar_lmr as apagar_lmr_novo

    sentinela = object()
    monkeypatch.setattr(apagar_lmr_backend, "_CANARIO_DE_ALIASING_DO_TESTE", sentinela, raising=False)

    assert apagar_lmr_novo._CANARIO_DE_ALIASING_DO_TESTE is sentinela

    # E a via inversa: patch pelo nome NOVO também aparece pelo antigo.
    sentinela_2 = object()
    monkeypatch.setattr(apagar_lmr_novo, "_OUTRO_CANARIO_DE_ALIASING", sentinela_2, raising=False)
    assert apagar_lmr_backend._OUTRO_CANARIO_DE_ALIASING is sentinela_2


# =============================================================================
# Canários comportamentais leves: o shim não só "existe", funciona de ponta
# a ponta através do nome antigo (sem duplicar as suítes de caracterização
# já existentes -- test_pdm_backend_characterization.py,
# test_apagar_lmr_backend_migration.py -- que continuam rodando, agora
# contra o código em sigft/services/, sem nenhuma edição).
# =============================================================================
def test_canario_instancia_classe_trivial_pelo_nome_antigo():
    import apagar_lmr_backend

    auto = apagar_lmr_backend.ApagarLMRAutomation()

    # CP 5.1: `driver`/`wait` deram lugar a `engine` -- `apagar_lmr` é o
    # piloto da migração para Playwright e não fala mais Selenium. A URL
    # continua idêntica, agora vinda de `config.PORTAL_URL` em vez de um
    # literal local.
    assert auto.engine is None
    assert auto.portal is None
    assert auto.url_inicial == "https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList"


def test_canario_chama_funcao_pura_pelo_nome_antigo_e_bate_com_modulo_novo():
    import pdm_backend
    from sigft.services import pdm as pdm_novo

    resultado_antigo = pdm_backend.extrair_pdm_id("PDM_1234_005 - Motor Elétrico.xlsx")
    resultado_novo = pdm_novo.extrair_pdm_id("PDM_1234_005 - Motor Elétrico.xlsx")

    assert resultado_antigo == "PDM_1234_005"
    assert resultado_antigo == resultado_novo
