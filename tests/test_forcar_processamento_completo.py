r"""
O interruptor "Forçar processamento de fichas com status 'COMPLETO'".

Contexto (2026-08-18). O usuário relatou que o botão não funcionava em
Condições. Ele estava certo, e o defeito não era sutil: o `CTkSwitch` (interface antiga) ligado
a `self.var_processar_completos` existia na tela desde sempre, mas
`.get()` NUNCA era chamado, `_worker_ia` não recebia o valor e
`processar_ia_lote` não tinha o parâmetro. O `frontend.py` até registrava a
dívida por escrito, num comentário: *"para manter simples, vamos rodar. Se o
usuário quiser forçar, ele deveria alterar o Excel, ou precisaremos adicionar
essa lógica no backend no futuro."*

Em Características Técnicas a fiação sempre existiu — o usuário suspeitava do
contrário, e a suspeita não se confirmou. O que havia lá era um buraco
vizinho: quando a coluna `CARACT. TÉCNICAS` não existe no `_STATUS_PMIB`, a
checagem inteira era pulada **em silêncio**, com a consequência invertida
(toda ficha ia para a IA, inclusive as completas — gastando API onde o
objetivo era economizar).

**Por que a tela é testada por AST.** Nasceu assim porque a tela não podia ser
importada nos testes. [2026-10-15] A tela agora é a Qt
(`sigft/app_qt/views/upload_*.py`; a antiga saiu do SIG-FT), e o teste continua
por AST porque o defeito daqui era
exatamente de FIAÇÃO — widget presente, valor nunca lido —, e é isso que a AST
enxerga bem. Um teste só de backend teria passado feliz durante todo o tempo
em que o botão não fazia nada.
"""
import ast
import pathlib

import pytest

from sigft.services import upload_conditions


# [CP 7.3] As duas telas saíram do `frontend.py` para arquivos próprios, e
# para arquivos DIFERENTES -- por isso o mapa em vez de um caminho só.
VIEWS = pathlib.Path(__file__).resolve().parents[1] / "sigft" / "app_qt" / "views"
ARQUIVO_DA_TELA = {
    "ModuloUploadConditions": VIEWS / "upload_conditions.py",
    "ModuloUploadTechSpecs": VIEWS / "upload_tech_specs.py",
}


# =============================================================================
# Duplos de teste
# =============================================================================
class _SerieFake:
    """`pandas.Series` é `MagicMock` no conftest, e `isinstance(x, MagicMock)`
    levanta `TypeError`. O código de produção faz esse `isinstance` para tratar
    PMIB duplicado na planilha, então os testes precisam de uma classe REAL no
    lugar — senão o erro do stub se disfarça de erro do código."""


class _DfStatusFake:
    """Mínimo que `processar_ia_lote` consome: `df_status.loc[pmib, coluna]`."""

    def __init__(self, valores):
        self.loc = _LocFake(valores)


class _LocFake:
    def __init__(self, valores):
        self._valores = valores

    def __getitem__(self, chave):
        if chave not in self._valores:
            raise KeyError(chave)
        return self._valores[chave]


class _LLMFake:
    def __init__(self):
        self.chamadas = []

    def generate(self, prompt, *, system=None, json_mode=False, tags=None):
        self.chamadas.append(prompt)
        return _RespostaFake()


class _RespostaFake:
    parsed_json = {"pmib_codigo": "sera-sobrescrito"}
    text = ""


PMIB = "4500063671.1234"
CAMINHO = f"{PMIB}.xlsx"
DADOS_BRUTOS = {"descricao_breve": "Disjuntor Tripolar 250A", "dimensoes": {}}


@pytest.fixture
def processor(monkeypatch):
    monkeypatch.setattr(upload_conditions.pd, "Series", _SerieFake, raising=False)
    p = upload_conditions.ConditionsProcessor("chave-fake")
    p._llm = _LLMFake()
    p.extrair_dados_brutos_excel = lambda caminho: DADOS_BRUTOS
    return p


def _rodar(processor, status_condicoes, **kwargs):
    linhas = []
    df = _DfStatusFake({
        (PMIB, "CONDIÇÕES"): status_condicoes,
        (PMIB, "DESCRIÇÃO"): "DISJUNTOR TRIPOLAR 250A",
    })
    processor.processar_ia_lote([CAMINHO], df, callback_log=linhas.append, **kwargs)
    return linhas


# =============================================================================
# 1. Condições — o comportamento que o interruptor promete
# =============================================================================
def test_por_padrao_a_ficha_completa_e_pulada(processor):
    linhas = _rodar(processor, "COMPLETO")

    assert processor._llm.chamadas == [], "gastou API numa ficha já COMPLETO"
    assert any("já COMPLETO" in l for l in linhas)


def test_com_o_interruptor_ligado_a_ficha_completa_e_reprocessada(processor):
    linhas = _rodar(processor, "COMPLETO", processar_completos=True)

    assert len(processor._llm.chamadas) == 1, (
        "o interruptor está ligado e a ficha COMPLETO continuou sendo pulada -- "
        "é exatamente o defeito relatado pelo usuário"
    )
    assert any("Forçar processamento" in l for l in linhas)


def test_o_reprocessamento_forcado_aparece_no_log(processor):
    """Sem esta linha, a única evidência de que o interruptor pegou seria a
    AUSÊNCIA da mensagem "já COMPLETO" -- e ausência de mensagem não é algo
    que o usuário consiga ver na tela."""
    linhas = _rodar(processor, "COMPLETO", processar_completos=True)

    assert any(PMIB in l and "Forçar processamento" in l for l in linhas)


@pytest.mark.parametrize("forcar", [False, True])
def test_ficha_nao_completa_e_processada_nos_dois_modos(processor, forcar):
    processor.processar_ia_lote(
        [CAMINHO],
        _DfStatusFake({(PMIB, "CONDIÇÕES"): "PENDENTE",
                       (PMIB, "DESCRIÇÃO"): "DISJUNTOR"}),
        callback_log=lambda _m: None,
        processar_completos=forcar,
    )

    assert len(processor._llm.chamadas) == 1


def test_o_default_continua_economizando_api(processor):
    """Quem chama sem o argumento (código antigo, testes antigos) não pode
    passar a gastar API de repente."""
    processor.processar_ia_lote(
        [CAMINHO],
        _DfStatusFake({(PMIB, "CONDIÇÕES"): "COMPLETO"}),
        callback_log=lambda _m: None,
    )

    assert processor._llm.chamadas == []


# =============================================================================
# 2. A fiação da tela — o defeito real estava AQUI
# =============================================================================
@pytest.fixture(scope="module")
def arvore():
    """[CP 7.3] Cada tela vive no seu arquivo: a "árvore" virou um mapa de
    nome da classe -> AST do arquivo dela."""
    return {
        nome: ast.parse(caminho.read_text(encoding="utf-8"))
        for nome, caminho in ARQUIVO_DA_TELA.items()
    }


def _classe(arvore, nome):
    no_modulo = arvore[nome] if isinstance(arvore, dict) else arvore
    for no in ast.walk(no_modulo):
        if isinstance(no, ast.ClassDef) and no.name == nome:
            return no
    pytest.fail(f"class {nome} sumiu de {ARQUIVO_DA_TELA.get(nome, '?')}")


def _metodo(classe, nome):
    for no in classe.body:
        if isinstance(no, ast.FunctionDef) and no.name == nome:
            return no
    pytest.fail(f"método {nome} não existe em {classe.name}")


def _le_o_interruptor(no):
    """Existe um `self.switch_completos.isChecked()` dentro do nó? (Na tela
    antiga era `self.var_processar_completos.get()`.)"""
    for chamada in ast.walk(no):
        if not (isinstance(chamada, ast.Call)
                and isinstance(chamada.func, ast.Attribute)
                and chamada.func.attr == "isChecked"):
            continue
        alvo = chamada.func.value
        if (isinstance(alvo, ast.Attribute)
                and alvo.attr == "switch_completos"):
            return True
    return False


def _passa_processar_completos(no):
    """Alguma chamada dentro do nó recebe `processar_completos=`?"""
    for chamada in ast.walk(no):
        if isinstance(chamada, ast.Call):
            for kw in chamada.keywords:
                if kw.arg == "processar_completos":
                    return True
    return False


@pytest.mark.parametrize("tela", ["ModuloUploadConditions", "ModuloUploadTechSpecs"])
def test_a_tela_LE_o_interruptor_antes_de_disparar_a_ia(arvore, tela):
    """O defeito de Condições em uma linha: o widget existia, o valor não era
    lido. Vale para as duas telas -- são gêmeas e erram juntas."""
    inicio = _metodo(_classe(arvore, tela), "_start_ia_process")

    assert _le_o_interruptor(inicio), (
        f"{tela}._start_ia_process não chama switch_completos.isChecked() -- "
        "o interruptor da tela voltou a ser decorativo"
    )


def test_condicoes_repassa_o_valor_para_o_backend(arvore):
    worker = _metodo(_classe(arvore, "ModuloUploadConditions"), "_worker_ia")

    assert "processar_completos" in {a.arg for a in worker.args.args}, (
        "_worker_ia não recebe mais o valor do interruptor"
    )
    assert _passa_processar_completos(worker), (
        "_worker_ia recebe o valor e não o repassa para processar_ia_lote"
    )


def test_tech_specs_repassa_o_valor_para_o_backend(arvore):
    worker = _metodo(_classe(arvore, "ModuloUploadTechSpecs"), "_worker_ia")

    assert "processar_completos" in {a.arg for a in worker.args.args}
    # Aqui o valor vai POSICIONALMENTE para `executar_pipeline_ia` -- é como
    # sempre esteve e funciona; o teste confere que ele continua chegando.
    nomes = {n.id for n in ast.walk(worker) if isinstance(n, ast.Name)}
    assert "processar_completos" in nomes


def test_o_comentario_que_confessava_a_divida_nao_voltou():
    """O código antigo dizia, por escrito, que a lógica ficaria "para o
    futuro". Se essa frase reaparecer, alguém desfez a correção.

    [CP 7.3] Passa a varrer os DOIS arquivos de tela — antes bastava ler o
    `frontend.py`, onde as duas moravam.
    """
    for caminho in ARQUIVO_DA_TELA.values():
        fonte = caminho.read_text(encoding="utf-8")
        assert "precisaremos adicionar essa lógica no backend no futuro" not in fonte, caminho
