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

⚠️ EXCEÇÃO REGISTRADA -- `upload_conditions_system` foi REGERADA em
2026-08-18. É o caso que a regra acima prevê como "legitimamente
necessário": o usuário pediu que o prompt de Condições parasse de inventar
conteúdo, então o TEXTO mudou de propósito. A fixture continua valendo como
trava contra mudança ACIDENTAL -- o que ela não prova mais, para esta
tarefa, é "idêntico ao pré-refatoração", porque não é mais esse o objetivo.
A propriedade que passou a importar (o prompt não manda inventar) é testada
em tests/test_prompt_condicoes_fidelidade.py, que checa CONTEÚDO e não
igualdade -- uma fixture regerada não pode se auto-aprovar. As outras 4
fixtures seguem intocadas desde a captura original.

⚠️ SEGUNDA REGERAÇÃO -- `upload_conditions_system` E `upload_conditions_user`,
em 2026-08-19, pelo mesmo motivo e com o mesmo aval. O usuário pediu que a IA
DEDUZA a unidade quando a ficha não a declara (*"eu preciso que a IA adivinhe
sim com base no tipo de equipamento"*), o que reescreveu as regras 3 e 7 do
prompt; e o payload passou a levar `Descrição breve da ficha` (a célula H6),
que é o segundo sinal sobre o material -- daí a fixture de USER ter mudado
também, coisa que não acontecia desde a captura.

O diff foi conferido linha a linha antes de gravar: as 18 linhas removidas
estão todas dentro das regras 3 e 7 e da linha da tabela da REGRA 0 que
proibia a dedução. Nenhuma outra parte do prompt foi tocada. As propriedades
de conteúdo -- que é o que uma fixture regerada não consegue provar sobre si
mesma -- estão em tests/test_prompt_condicoes_unidades.py.

⚠️ TERCEIRA REGERAÇÃO -- `cria_fichas_prompt`, em 2026-09-22, com o mesmo
aval do usuário ("melhorar o módulo de cria fichas, talvez o prompt que a IA
recebe"). O prompt de `categorizar_pdm` foi REESCRITO porque três dos seus
oito exemplos few-shot apontavam para PDMs errados, conferidos um a um contra
o catálogo real de 1193 PDMs:

  - `PDM.4020.001 - BOMBA CENTRIFUGA` -- código inexistente, e não há nenhum
    "BOMBA CENTRIFUGA" no catálogo sob qualquer código;
  - `PDM.6145.011 - CABO, TRANSMISSAO DADOS` -- o título real não tem a
    vírgula, e é essa string que é digitada no filtro de PDM do portal;
  - `PDM.7010.018 - SERVIDOR` -- o título real é `SERVIDOR CONSOLE`
    (console/KVM), e o exemplo era um Dell PowerEdge.

Mais um quarto, corrigido pelas notas do próprio catálogo: o exemplo da
câmera apontava a classe 6720 ("CÁMARAS FOTOGRÁFICAS") para uma câmera de
rede, contra a nota da classe 6710, que remete câmeras de vídeo à 5836.

Junto com isso: o manual de regras passou a ser podado às classes que têm
PDM (eram 165 descritas, 124 com PDM), a lista passou a vir agrupada por
classe FSC, e cada item leva seus candidatos pré-filtrados. Ver
`sigft/core/pdm_catalogo.py`.

O que a fixture regerada NÃO prova sobre si mesma está em
tests/test_prompt_categorizar_pdm.py, que checa CONTEÚDO: que os três
exemplos errados não voltaram, que a regra de lista fechada está no texto, e
que o contrato de JSON (as 7 chaves que o app lê campo a campo por nome)
continua intacto.

⚠️ QUARTA REGERAÇÃO -- `upload_tech_specs_system` E `upload_tech_specs_user`,
em 2026-09-28, com o aval do usuário ("devemos garantir que a resposta da IA
contemple apenas uma resposta" na LISTA). O prompt mandava separar "múltiplos
itens selecionados" de LISTA com ponto e vírgula e dizia que a vírgula era
"exclusiva para decimais" -- mas no PDM SAM é a VÍRGULA que separa uma opção
da outra, e a IA devolveu duas opções ("Protecao contra descargas
atmosfericas, etc.") num campo do portal que seleciona uma.

O diff foi conferido linha a linha: no SYSTEM mudaram só a regra 2 de
formatação e a regra 4 (LISTA); no USER, só a regra 4 do contrato de saída
ganhou quatro linhas. Nenhuma outra parte foi tocada. O CONTEÚDO da regra nova
-- o que a fixture regerada não prova sobre si mesma -- está em
tests/test_prompt_tech_specs_lista.py, e a garantia em código, que não depende
de o modelo obedecer, em tests/test_tech_specs_lista_uma_opcao.py.

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

# Entradas do prompt de `categorizar_pdm`. Em 2026-09-22 elas passaram a ser
# o que o CATÁLOGO produz (`manual_de_regras` e `lista_por_classe`), porque
# `processar_lote` deixou de receber duas strings prontas -- e foram trocadas
# por PDMs que EXISTEM no catálogo real: a fixture antiga usava
# `PDM.4020.001 - BOMBA CENTRIFUGA`, que não existe, e
# `CABO, TRANSMISSAO DADOS`, cujo título real não tem a vírgula. Dublê de
# entrada de teste com dado impossível convida a copiá-lo como se fosse real.
CRIA_FICHAS_INSTRUCOES = (
    "- CLASSE 4320: BOMBAS E COMPRESSORES\n"
    "  - Inclui: BOMBAS DE AGUA\n"
    "  - Nao inclui: BOMBAS DE PARAFUSO\n"
)
CRIA_FICHAS_LISTA_PDMS = (
    "## CLASSE 4320 - BOMBAS E COMPRESSORES\n"
    "- PDM.4320.007 - BOMBA\n"
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
class _CatalogoDeSnapshot:
    """Devolve as duas strings da fixture, para o snapshot medir só o TEXTO do
    prompt. `processar_lote` passou a receber o catálogo em 2026-09-22."""

    def lista_por_classe(self):
        return CRIA_FICHAS_LISTA_PDMS

    def manual_de_regras(self, numeros=None):
        return CRIA_FICHAS_INSTRUCOES

    def candidatos(self, texto, limite=None):
        return []

    def bloco_de_candidatos(self, pdms):
        return ""


class _UmItemSo:
    def iterrows(self):
        return iter([(0, {"DESCRIÇÃO": "Bomba", "MARCA/MODELO": "KSB",
                          "CÓDIGO DO MATERIAL": "123-ABC", "UNID.": "Unidade"})])

    def __len__(self):
        return 1


def test_snapshot_cria_fichas_categorizar_pdm_prompt():
    cat = cria_fichas_no_pmib_v1_backend.GeminiCategorizer("chave-fake")
    cat._formatar_itens = lambda df, catalogo=None: CRIA_FICHAS_ITENS_TEXTO
    fake = _FakeLLM(retorno=_resposta_ok([]))
    cat._llm = fake

    cat.processar_lote(df_itens=_UmItemSo(), catalogo=_CatalogoDeSnapshot())

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
