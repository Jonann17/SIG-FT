r"""
Reforço semântico OPCIONAL do retrieval do AutoSpecAI.

Reordena os candidatos que o BM25 trouxe, usando similaridade de embedding.
É **complemento**, nunca requisito: sem biblioteca, sem modelo baixado ou sem
rede, `obter_reordenador()` devolve `None` e o `autospec_rag` segue com o BM25
sozinho — que é o caminho principal e o que responde hoje.

POR QUE OPCIONAL, E NÃO O PADRÃO
------------------------------------------------------------------------
Três razões, na ordem em que pesam:

1. **O proxy corporativo bloqueia o download do modelo.** Isto não é hipótese:
   ao construir este módulo em 2026-08-11, a tentativa de baixar
   `paraphrase-multilingual-MiniLM-L12-v2` falhou com `ProxyError: 403
   Forbidden` no próprio ambiente de desenvolvimento. Se o caminho semântico
   fosse requisito, o AutoSpec teria parado de funcionar ali.

2. **Peso.** `fastembed` (ONNX) é o mais leve dos caminhos viáveis e ainda
   assim baixa ~100 MB de modelo no primeiro uso; `sentence-transformers`
   puxa `torch` (~2 GB). O SIG-FT instala por `pip` no `.bat` de cada máquina.

3. **O domínio favorece o lexical.** Código de peça é onde embedding erra:
   `PVF100-4` e `PVF100-8` caem quase no mesmo ponto do espaço vetorial e são
   peças diferentes. Ver o docstring de `autospec_rag`.

O QUE ELE ACRESCENTA, QUANDO ESTÁ DISPONÍVEL
------------------------------------------------------------------------
O glossário PT->EN de `autospec_rag` cobre o vocabulário técnico previsto —
`pressao`->`pressure`, `peso`->`weight`. O que ele NÃO cobre é o termo que
ninguém pensou em cadastrar: uma pergunta sobre "resistência à corrosão"
casando com uma seção "Corrosion resistance / salt spray test", ou "vida útil"
com "service life expectancy". É aí que o semântico ganha, e é por isso que
vale existir mesmo sendo opcional.

COMO LIGAR (na máquina de quem quiser)
------------------------------------------------------------------------
    pip install fastembed

Nada é acrescentado ao `requirements.txt` de propósito: o `SIG-FT.bat` roda em
máquina de usuário atrás do proxy, e uma dependência que pode falhar no
download não pode estar no caminho crítico da instalação.
"""
import math

# Multilíngue de propósito: a ficha pergunta em português e o datasheet
# responde em inglês. Um modelo só-inglês reintroduziria exatamente o furo que
# o glossário de `autospec_rag` existe para tapar.
MODELO_PADRAO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Peso do sinal semântico na combinação com o lexical. 0.5 = metade a metade.
# Não é 1.0 de propósito: descartar a ordem do BM25 jogaria fora o casamento
# exato de código de peça, que é a força do lexical.
PESO_SEMANTICO = 0.5

_cache_codificador = {}


def _obter_codificador(modelo=MODELO_PADRAO):
    """Codificador de texto, ou `None` se não der para ter um.

    Tenta `fastembed` (ONNX, leve) e depois `sentence-transformers`. Qualquer
    falha — biblioteca ausente, modelo não baixado, proxy bloqueando — devolve
    `None`, e o chamador segue sem reforço semântico.
    """
    if modelo in _cache_codificador:
        return _cache_codificador[modelo]

    codificador = None
    try:
        import warnings

        from fastembed import TextEmbedding

        with warnings.catch_warnings():
            # O fastembed avisa sobre mudanca de pooling entre versoes dele.
            # E ruido para o usuario do SIG-FT, que nao escolheu esse modelo
            # nem pode fazer nada a respeito -- e o console dele e onde estao
            # os avisos que IMPORTAM (leitura incompleta, campo descartado).
            warnings.simplefilter("ignore")
            motor = TextEmbedding(model_name=modelo)
        codificador = lambda textos: [list(v) for v in motor.embed(list(textos))]
    except Exception:
        try:
            from sentence_transformers import SentenceTransformer

            motor = SentenceTransformer(modelo)
            codificador = lambda textos: [
                list(v) for v in motor.encode(list(textos), show_progress_bar=False)
            ]
        except Exception:
            codificador = None

    _cache_codificador[modelo] = codificador
    return codificador


def similaridade_cosseno(a, b):
    """Cosseno entre dois vetores, em Python puro (evita exigir numpy só para
    isto). `0.0` quando qualquer um dos vetores é nulo."""
    if not a or not b or len(a) != len(b):
        return 0.0
    produto = sum(x * y for x, y in zip(a, b))
    norma_a = math.sqrt(sum(x * x for x in a))
    norma_b = math.sqrt(sum(y * y for y in b))
    if not norma_a or not norma_b:
        return 0.0
    return produto / (norma_a * norma_b)


def criar_reordenador(codificador, peso_semantico=PESO_SEMANTICO):
    """Monta a função `(consulta, trechos) -> trechos reordenados`.

    A combinação é HÍBRIDA: a posição que o BM25 deu ao trecho continua
    valendo, misturada à similaridade semântica. Descartar o lexical
    entregaria o casamento de código de peça ao modelo, que é justamente onde
    ele erra.

    `codificador` recebe uma lista de textos e devolve uma lista de vetores —
    injetável, o que torna esta função testável sem baixar modelo nenhum.
    """

    def reordenar(consulta, trechos):
        candidatos = list(trechos or [])
        if len(candidatos) < 2:
            return candidatos

        vetores = codificador([consulta] + [t.texto for t in candidatos])
        if not vetores or len(vetores) != len(candidatos) + 1:
            return candidatos

        vetor_consulta = vetores[0]
        total = len(candidatos)
        pontuados = []
        for posicao, (trecho, vetor) in enumerate(zip(candidatos, vetores[1:])):
            # Posição do BM25 normalizada para [0, 1]: o 1º da lista vale 1.
            lexical = 1.0 - (posicao / total)
            semantico = similaridade_cosseno(vetor_consulta, vetor)
            combinado = (1 - peso_semantico) * lexical + peso_semantico * semantico
            pontuados.append((combinado, posicao, trecho))

        # `posicao` no desempate mantém a ordem do BM25 quando as pontuações
        # empatam — reordenação estável, sem sorteio.
        pontuados.sort(key=lambda item: (-item[0], item[1]))
        return [trecho for _, _, trecho in pontuados]

    return reordenar


def obter_reordenador(modelo=MODELO_PADRAO):
    """Reordenador pronto, ou `None` quando o reforço semântico não está
    disponível. É o que `AutoSpecCore._reordenador_semantico` chama."""
    codificador = _obter_codificador(modelo)
    if codificador is None:
        return None
    return criar_reordenador(codificador)


def diagnostico(modelo=MODELO_PADRAO):
    """Frase dizendo se o reforço semântico está de pé, e por que não está.

    Existe para o console: sem isto, "o embedding está ligado?" viraria
    adivinhação, e o usuário não saberia que está rodando só com o BM25.
    """
    if _obter_codificador(modelo) is not None:
        return f"Reforco semantico ATIVO (modelo {modelo})."
    return (
        "Reforco semantico INATIVO — retrieval rodando so com BM25 + glossario "
        "PT/EN, que e o caminho padrao. Para ligar: `pip install fastembed` "
        "(baixa ~100 MB no 1o uso; pode ser bloqueado por proxy corporativo)."
    )
