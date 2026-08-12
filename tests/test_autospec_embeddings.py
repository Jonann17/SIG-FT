r"""
Testes do reforço semântico opcional (2026-08-11).
Ver `sigft/services/autospec_embeddings.py`.

⚠️ **O que estes testes cobrem e o que NÃO cobrem.**

Eles exercitam a LÓGICA deste módulo — combinação híbrida, estabilidade da
ordenação, e principalmente a **degradação graciosa** — com um codificador
injetado. Não exercitam a biblioteca de embedding real: ao construir o módulo,
o download do modelo falhou com `ProxyError: 403 Forbidden` no ambiente de
desenvolvimento, e é exatamente por isso que o caminho de degradação é o mais
testado aqui. Se o proxy do usuário fizer o mesmo, é este caminho que roda.
"""
import pytest

from sigft.services import autospec_embeddings as emb
from sigft.services import autospec_rag as rag


def _trecho(texto, ordem=0):
    return rag.Trecho(texto, "doc.pdf", ordem)


def _codificador_fake(mapa):
    """Codificador determinístico: cada texto vira o vetor que o `mapa` disser,
    casando por substring. Torna o teste independente de modelo baixado."""
    def codificar(textos):
        vetores = []
        for texto in textos:
            escolhido = [0.0, 0.0, 1.0]
            for chave, vetor in mapa.items():
                if chave.lower() in texto.lower():
                    escolhido = vetor
                    break
            vetores.append(escolhido)
        return vetores
    return codificar


# =============================================================================
# A. Degradação graciosa — o caminho que MAIS importa
# =============================================================================
def test_sem_biblioteca_devolve_None_em_vez_de_quebrar(monkeypatch):
    """Se o reforço fosse requisito, o AutoSpec pararia de funcionar atrás do
    proxy. Ele não é."""
    monkeypatch.setattr(emb, "_cache_codificador", {})
    monkeypatch.setattr(emb, "_obter_codificador", lambda modelo=None: None)
    assert emb.obter_reordenador() is None


def test_diagnostico_explica_por_que_esta_inativo(monkeypatch):
    monkeypatch.setattr(emb, "_cache_codificador", {})
    monkeypatch.setattr(emb, "_obter_codificador", lambda modelo=None: None)
    texto = emb.diagnostico()
    assert "INATIVO" in texto
    assert "BM25" in texto, "precisa dizer que o retrieval continua funcionando"
    assert "fastembed" in texto, "precisa dizer como ligar"


def test_diagnostico_confirma_quando_esta_ativo(monkeypatch):
    monkeypatch.setattr(emb, "_cache_codificador", {})
    monkeypatch.setattr(emb, "_obter_codificador", lambda modelo=None: (lambda t: []))
    assert "ATIVO" in emb.diagnostico()


def test_codificador_que_devolve_lixo_nao_reordena_nada():
    """Vetores em quantidade errada: mantém a ordem do BM25 em vez de
    inventar uma."""
    ruim = emb.criar_reordenador(lambda textos: [[1.0, 0.0]])  # falta vetor
    trechos = [_trecho("a", 0), _trecho("b", 1), _trecho("c", 2)]
    assert ruim("consulta", trechos) == trechos


def test_um_candidato_so_passa_direto():
    chamou = []
    r = emb.criar_reordenador(lambda t: chamou.append(t) or [[1.0]])
    unico = [_trecho("a")]
    assert r("consulta", unico) == unico
    assert chamou == [], "nao gasta chamada de modelo para 1 candidato"


# =============================================================================
# B. A reordenação em si
# =============================================================================
def test_trecho_semanticamente_proximo_sobe():
    """O ganho real do semântico: 'vida util' casando com 'service life', que
    o glossário PT->EN não cobre."""
    codificador = _codificador_fake({
        "vida util": [1.0, 0.0, 0.0],
        "service life": [0.98, 0.1, 0.0],
        "packaging": [0.0, 1.0, 0.0],
    })
    reordenar = emb.criar_reordenador(codificador)

    # BM25 colocou o irrelevante na frente (nenhum termo casou)
    trechos = [_trecho("packaging and shipping", 0), _trecho("service life expectancy", 1)]
    resultado = reordenar("vida util do item", trechos)
    assert "service life" in resultado[0].texto


def test_ordem_do_BM25_e_preservada_no_empate():
    """Reordenação estável: pontuação igual não pode virar sorteio."""
    codificador = _codificador_fake({})  # tudo com o mesmo vetor
    reordenar = emb.criar_reordenador(codificador)
    trechos = [_trecho("a", 0), _trecho("b", 1), _trecho("c", 2)]
    assert [t.texto for t in reordenar("q", trechos)] == ["a", "b", "c"]


def test_combinacao_e_HIBRIDA_nao_puramente_semantica():
    """Peso 0.5: a posição do BM25 continua contando. Descartá-la entregaria o
    casamento de código de peça ao modelo, que é onde ele erra."""
    assert 0 < emb.PESO_SEMANTICO < 1


def test_peso_semantico_zero_devolve_a_ordem_do_BM25():
    codificador = _codificador_fake({"b": [1.0, 0.0, 0.0]})
    reordenar = emb.criar_reordenador(codificador, peso_semantico=0.0)
    trechos = [_trecho("a", 0), _trecho("b", 1)]
    assert [t.texto for t in reordenar("b", trechos)] == ["a", "b"]


# =============================================================================
# C. Similaridade de cosseno
# =============================================================================
@pytest.mark.parametrize(
    "a,b,esperado,caso",
    [
        ([1.0, 0.0], [1.0, 0.0], 1.0, "vetores iguais"),
        ([1.0, 0.0], [0.0, 1.0], 0.0, "ortogonais"),
        ([1.0, 0.0], [-1.0, 0.0], -1.0, "opostos"),
    ],
)
def test_cosseno(a, b, esperado, caso):
    assert emb.similaridade_cosseno(a, b) == pytest.approx(esperado), caso


@pytest.mark.parametrize("a,b", [([], [1.0]), ([0.0, 0.0], [1.0, 1.0]), ([1.0], [1.0, 2.0])])
def test_cosseno_em_caso_degenerado_devolve_zero(a, b):
    """Vetor vazio, nulo ou de tamanho diferente não pode levantar exceção —
    isto roda dentro do laço de retrieval."""
    assert emb.similaridade_cosseno(a, b) == 0.0


# =============================================================================
# D. Integração com o retrieval
# =============================================================================
def test_retrieval_com_reordenador_continua_preservando_os_dados():
    """A garantia que não pode regredir: ligar o semântico não pode fazer o
    recorte perder dado que o BM25 sozinho encontrava."""
    contexto = (
        "--- LOCAL DOC: m.pdf ---\n"
        + "\n".join(
            f"Secao {i}\n" + ("texto irrelevante de enchimento. " * 40)
            for i in range(30)
        )
        + "\nPRESSURE\nMaximum operating pressure 175 bar.\n"
        + "\nWEIGHT\nNet weight 41 kg.\n"
    )
    consultas = ["6 - PRESSAO DE TRABALHO", "Peso liquido (kg)"]

    reordenar = emb.criar_reordenador(_codificador_fake({}))
    recortado, _ = rag.montar_contexto_relevante(
        contexto, consultas, reordenador=reordenar
    )
    assert "175 bar" in recortado and "41 kg" in recortado


def test_reordenador_recebe_pool_MAIOR_que_o_limite_final():
    """"Recupera largo, reordena estreito": entregar exatamente os 3 finais
    não daria ao reordenador o que escolher."""
    tamanhos = []

    def _espiao(consulta, trechos):
        tamanhos.append(len(trechos))
        return trechos

    contexto = "--- LOCAL DOC: m.pdf ---\n" + "\n".join(
        f"Secao {i} sobre pressao e temperatura do equipamento.\n"
        + ("conteudo tecnico variado. " * 40)
        for i in range(40)
    )
    rag.montar_contexto_relevante(contexto, ["pressao"], reordenador=_espiao)

    assert tamanhos, "o reordenador precisa ter sido chamado"
    assert tamanhos[0] > rag.TRECHOS_POR_CAMPO
