r"""
Teste de snapshot do Checkpoint 3.5 -- prova que o TEXTO de cada um dos 5
prompts de IA do SIG-FT (`analyzer_backend`, `cria_fichas_no_pmib_v1_backend`,
`upload_conditions_backend`, `upload_tech_specs_backend`, `autospec_backend`)
continua BYTE A BYTE idêntico depois da extração para
`sigft/core/llm/prompts.py`.

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.5 (*Aceite*:
"teste de snapshot prova que o prompt gerado é idêntico ao antigo").

DISCIPLINA (mesma do CP 0.1 -- caracterizar ANTES de tocar produção): as
fixtures em `tests/fixtures/prompts/*.txt` foram capturadas com os 5
backends ainda no estado ANTERIOR a este checkpoint (prompt gigante embutido
inline no método, antes de qualquer linha de `sigft/core/llm/prompts.py`
existir) -- via `git stash` da única mudança de produção que já existia
nesta sessão no momento da captura, para garantir um estado 100% pré-
refactor nos 5 arquivos, e a MESMA técnica de `_FakeLLM` usada abaixo. As
fixtures NUNCA são regeneradas por este arquivo de teste -- se algum teste
aqui falhar depois de uma mudança de código, a correção é no CÓDIGO, nunca
editar a fixture (ver docs/refatoracao/PENDENCIAS.md, entrada do CP 3.5,
para o racional completo e para como regenerar caso um dia seja
legitimamente necessário).

Técnica de captura (idêntica a tests/test_llm_backend_migration.py e
tests/test_llm_autospec_migration.py, já usada nos CPs 3.1-3.4): cada
consumidor é construído normalmente e `instancia._llm` é substituído por um
`_FakeLLM` -- um duplo de `LLMClient` que grava a chamada recebida (com
`prompt`/`system` exatamente como o consumidor os monta) sem precisar de
rede nem reimplementar `LLMClient`/`GeminiProvider` (já cobertos em outros
arquivos de teste).

Entradas FIXAS e determinísticas (sem data/hora, `os.urandom`, ordem de
`set` etc.) -- dicts literais em Python preservam ordem de inserção, então
são seguros; nenhum trecho abaixo itera um `set`.
"""
import os

import pytest

import analyzer_backend
import autospec_backend
import cria_fichas_no_pmib_v1_backend
import upload_conditions_backend
import upload_tech_specs_backend
from sigft import config
from sigft.core.llm.client import LLMResponse

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "prompts")


@pytest.fixture(autouse=True)
def _isola_config_file_do_cwd_real(monkeypatch, tmp_path):
    """Mesma isolação de tests/test_llm_backend_migration.py/
    tests/test_llm_autospec_migration.py: `get_llm()` (chamado no
    `__init__` de cada consumidor abaixo) consulta `config.CONFIG_FILE`
    para resolver a seleção de modelo do usuário (CP 3.3) -- isola estes
    testes de um `api_config.json` REAL que porventura exista no cwd de
    quem roda a suíte."""
    monkeypatch.setattr(config, "CONFIG_FILE", str(tmp_path / "api_config_isolado_test.json"))


def _ler_fixture(nome):
    caminho = os.path.join(FIXTURES_DIR, nome + ".txt")
    with open(caminho, "r", encoding="utf-8") as f:
        return f.read()


# =============================================================================
# Helpers (idênticos aos de tests/test_llm_backend_migration.py)
# =============================================================================
class _FakeLLM:
    """Substitui `self._llm` (uma instância de `LLMClient`) nos 5
    consumidores -- grava toda chamada recebida (`prompt`/`system`/
    `json_mode`/`tags`) e devolve `retorno`, sem precisar de rede."""

    def __init__(self, retorno=None):
        self.retorno = retorno
        self.chamadas = []

    def generate(self, prompt, *, system=None, json_mode=False, tags=None):
        self.chamadas.append(
            {"prompt": prompt, "system": system, "json_mode": json_mode, "tags": tags}
        )
        return self.retorno


def _resposta_ok(parsed_json=None):
    """`LLMResponse` de sucesso mínima -- só o suficiente para os 5 métodos
    não levantarem ao processar o retorno depois de capturar a chamada."""
    return LLMResponse(
        text="texto cru da IA",
        parsed_json=parsed_json if parsed_json is not None else {},
        tokens_in=None,
        tokens_out=None,
        custo_usd=None,
        model="modelo-fake",
        provider="gemini",
        duracao_s=0.0,
    )


class _FakeLocSempreKeyError:
    """`.loc[...]` de um DataFrame fake que SEMPRE levanta `KeyError` --
    mesmo duplo usado em tests/test_llm_backend_migration.py para simular
    "PMIB ainda não tem linha/coluna correspondente no status", sem
    depender de `pandas.DataFrame`/`pandas.Series` reais (mockados neste
    ambiente de teste)."""

    def __getitem__(self, chave):
        raise KeyError(chave)


class _FakeDfStatusSempreKeyError:
    def __init__(self):
        self.loc = _FakeLocSempreKeyError()


# =============================================================================
# Entradas FIXAS -- reaproveitadas pelo script (fora da suíte, rodado 1x,
# ANTES desta migração) que gerou tests/fixtures/prompts/*.txt e por estes
# testes (que só LEEM as fixtures já geradas). Ver docstring do módulo.
# =============================================================================
ANALYZER_CONTEXT = {
    "texto_breve_material": "Bomba Centrífuga Multiestágio",
    "fabricante": "KSB",
}
ANALYZER_FIXED = {
    "embalagem_transporte": "Caixa de madeira reforçada",
    "transporte": "Rodoviário, sobre paletes",
}
ANALYZER_VARIABLE = [
    {"pergunta": "Peso líquido", "resposta": "125 kg"},
    {"pergunta": "Vazão nominal", "resposta": "50 m³/h"},
]

CRIA_FICHAS_INSTRUCOES = (
    "### GRUPO 40: HIDRÁULICA E BOMBAS\n"
    "  - CLASSE 4020: Bombas Centrifugas\n"
    "    - Inclui: Bombas de até 100kW\n"
    "    - Não inclui: Bombas de parafuso\n"
)
CRIA_FICHAS_LISTA_PDMS = (
    "- PDM.4020.001 - BOMBA CENTRIFUGA\n"
    "- PDM.5895.011 - CABO, TRANSMISSAO DADOS\n"
)
CRIA_FICHAS_ITENS_TEXTO = (
    "### ITEM 1\n"
    "- Descrição: Bomba Centrifuga\n"
    "- Marca/Modelo: KSB\n"
    "- Código do Material: 123-ABC\n"
    "- Unidade: Unidade\n"
)

UPLOAD_CONDITIONS_CAMINHO = "4500063671.1234.xlsx"
UPLOAD_CONDITIONS_DADOS_BRUTOS = {
    "descricao_breve": "Disjuntor Tripolar 250A",
    "dimensoes": {"comprimento": "30", "largura": "20", "altura": "15"},
    "controle_temperatura": "SIM, manter de 15 a 30 graus",
    "posicao_armazenamento": "Vertical",
    "nocivo": "Não contém",
    "peso": "12,5 kg",
    "sujeito_intemperie": "NÃO",
    "protecao": "SN, UV",
    "empilhamento": "5 unidades",
    "outros_cuidados": "Manter em local seco",
    "embalagem_transp": "Caixa de papelão reforçada",
    "posicao_icagem": "Içar pelas alças laterais",
    "cuidad_preserv": "Aplicar óleo protetivo mensalmente",
    "limpeza_secagem": "Pano seco, sem produtos abrasivos",
    "ferramentas": "Nenhuma ferramenta especial",
    "legislacao": "N/A",
    "perigoso_10004": "CLASSE 1: PERIGOSO",
    "descarte": "Conforme legislação",
    "logistica_reversa": {"status": "SIM", "logistica_reversa": "Verificar com fabricante."},
}

UPLOAD_TECH_SPECS_CONTEXTO = {
    "CODIGO_PMIB": "4500063671.1234",
    "PDM": "PDM.4020.001",
    "CARACTERISTICAS": [
        {
            "CARACTERISTICA_CHAVE": "Vazão máxima",
            "TIPO_DADO": "NUM",
            "RESPOSTA_CRUA_PT": "80 l/min",
            "TEXTO_AJUDA": "Vazão nominal em regime contínuo",
            "SIMBOLO_UNIDADE": "AD, m³/h, m³/s",
        },
        {
            "CARACTERISTICA_CHAVE": "Material da carcaça",
            "TIPO_DADO": "CHAR",
            "RESPOSTA_CRUA_PT": "Ferro fundido",
            "TEXTO_AJUDA": "Material predominante da carcaça",
            "SIMBOLO_UNIDADE": "AD",
        },
    ],
}

AUTOSPEC_TXT_BRV = "Bomba Centrífuga Multiestágio"
AUTOSPEC_FAB = "KSB"
AUTOSPEC_DESC_COMP = "Bomba centrífuga multiestágio, corpo em ferro fundido"
AUTOSPEC_CONTEXT = "--- LOCAL DOC: manual.pdf ---\nEspecificações técnicas do fabricante..."
AUTOSPEC_MISSING = {
    "empilhamento": {"type": "text", "desc": "Empilhamento máximo (unidades)", "ref": "M42"},
    "texto_breve_material": {"type": "text", "desc": "Texto breve do material", "ref": "H6"},
    "posicao_armazenamento": {
        "type": "checkbox",
        "options": ["G25", "G27", "G29"],
        "desc": "Posição de armazenamento",
        "ref": ["G25", "G27", "G29"],
    },
}


# =============================================================================
# 1. analyzer_backend.DatasheetAnalyzer -- tarefa "validar_ficha"
# =============================================================================
def test_snapshot_analyzer_validar_ficha_prompt():
    analyzer = analyzer_backend.DatasheetAnalyzer("chave-fake")
    fake = _FakeLLM(retorno=_resposta_ok())
    analyzer._llm = fake

    prompt_texto = analyzer._build_gemini_prompt(ANALYZER_CONTEXT, ANALYZER_FIXED, ANALYZER_VARIABLE)
    analyzer._call_gemini_api(prompt_texto)

    assert len(fake.chamadas) == 1
    assert fake.chamadas[0]["prompt"] == _ler_fixture("analyzer_prompt")
    assert fake.chamadas[0]["system"] is None  # esta tarefa nunca teve system prompt


# =============================================================================
# 2. cria_fichas_no_pmib_v1_backend.GeminiCategorizer -- tarefa "categorizar_pdm"
# =============================================================================
def test_snapshot_cria_fichas_categorizar_pdm_prompt():
    cat = cria_fichas_no_pmib_v1_backend.GeminiCategorizer("chave-fake")
    cat._formatar_itens = lambda df: CRIA_FICHAS_ITENS_TEXTO
    fake = _FakeLLM(retorno=_resposta_ok([]))
    cat._llm = fake

    cat.processar_lote(df_itens=object(), lista_pdms=CRIA_FICHAS_LISTA_PDMS, instrucoes=CRIA_FICHAS_INSTRUCOES)

    assert len(fake.chamadas) == 1
    assert fake.chamadas[0]["prompt"] == _ler_fixture("cria_fichas_prompt")
    assert fake.chamadas[0]["system"] is None


# =============================================================================
# 3. upload_conditions_backend.ConditionsProcessor -- tarefa "condicoes"
# =============================================================================
def test_snapshot_upload_conditions_system_e_user_prompt():
    processor = upload_conditions_backend.ConditionsProcessor("chave-fake")
    fake = _FakeLLM(retorno=_resposta_ok({}))
    processor._llm = fake
    processor.extrair_dados_brutos_excel = lambda caminho: UPLOAD_CONDITIONS_DADOS_BRUTOS

    processor.processar_ia_lote([UPLOAD_CONDITIONS_CAMINHO], _FakeDfStatusSempreKeyError())

    assert len(fake.chamadas) == 1
    assert fake.chamadas[0]["system"] == _ler_fixture("upload_conditions_system")
    assert fake.chamadas[0]["prompt"] == _ler_fixture("upload_conditions_user")


# =============================================================================
# 4. upload_tech_specs_backend.TechSpecsProcessor -- tarefa "tech_specs"
# =============================================================================
def test_snapshot_upload_tech_specs_system_e_user_prompt():
    processor = upload_tech_specs_backend.TechSpecsProcessor("chave-fake")
    fake = _FakeLLM(retorno=_resposta_ok([]))
    processor._llm = fake

    processor._chamar_gemini_specs(UPLOAD_TECH_SPECS_CONTEXTO)

    assert len(fake.chamadas) == 1
    assert fake.chamadas[0]["system"] == _ler_fixture("upload_tech_specs_system")
    assert fake.chamadas[0]["prompt"] == _ler_fixture("upload_tech_specs_user")
    assert fake.chamadas[0]["json_mode"] is True  # preservado -- não é objeto deste checkpoint


# =============================================================================
# 5. autospec_backend.AutoSpecCore -- tarefa "autospec"
# =============================================================================
def test_snapshot_autospec_prompt():
    core = autospec_backend.AutoSpecCore(
        gemini_key="chave-fake", llama_key=None, google_search_key=None, google_cse_id=None
    )
    fake = _FakeLLM(retorno=_resposta_ok({}))
    core._llm = fake

    core.generate_ai_response(
        AUTOSPEC_TXT_BRV, AUTOSPEC_FAB, AUTOSPEC_DESC_COMP, AUTOSPEC_MISSING, AUTOSPEC_CONTEXT
    )

    assert len(fake.chamadas) == 1
    assert fake.chamadas[0]["prompt"] == _ler_fixture("autospec_prompt")
    assert fake.chamadas[0]["system"] is None
