import os
import re
import json
import hashlib
import unicodedata
import tempfile
import openpyxl
from openpyxl.styles import Font
import PyPDF2
from bs4 import BeautifulSoup

# Integração LlamaParse
from llama_parse import LlamaParse

from sigft import config
from sigft.core.excel import headers, pmib_codes
from sigft.core.rpa import ficha_layout
from sigft.core.rpa.ficha_layout import CONFIG_MAP, VARIAVEIS_SPECS, nome_da_aba_da_ficha
from sigft.core.llm.client import get_llm
# CP 3.5 (Fase 3): o TEXTO do preâmbulo do prompt de
# `generate_ai_response` abaixo mora em
# `sigft.core.llm.prompts.montar_autospec` -- o laço que monta `desc_list`
# (consulta GENERATIVE_FIELDS, logo abaixo) continua neste módulo.
from sigft.core.llm import prompts
# CP 4.4 (Fase 4, docs/refatoracao/PLANO_REFATORACAO.md): `process_queue` é a
# única função de LOTE deste módulo (os demais métodos de `AutoSpecCore` são
# helpers de UM item) -- passa a emitir o padrão único de log via
# `RelatorioLote`. Ver docstring de `process_queue` para como isso convive
# com o contrato de generator que `frontend.py` já consome.
from sigft.core.callbacks import UICallbacks
from sigft.core.relatorio_lote import RelatorioLote
from sigft.core import rede
# Retrieval (2026-08-11): recorta o contexto antes de mandar para a IA. Modulo
# separado porque este arquivo ja passou de 1.500 linhas -- e porque o
# algoritmo (BM25) nao sabe nada sobre ficha tecnica nem sobre Excel.
from sigft.services import autospec_rag
# Leitura INTEGRAL (2026-09-24): o documento por pagina, e o que vai para a IA
# como o proprio PDF. Ver o docstring do modulo para os numeros que motivaram.
from sigft.services import autospec_documentos
# A conferencia pela PROVA que a IA devolve com cada valor (2026-09-24).
from sigft.services import autospec_evidencia
from sigft.core.excel import locking

# -----------------------------------------------------------------
# 1. CONFIGURAÇÕES E MAPAS
# -----------------------------------------------------------------
# [REMOVIDO] Constantes de chaves API hardcoded foram removidas daqui.
# As chaves agora devem ser passadas exclusivamente via __init__ da classe AutoSpecCore.

GENERATIVE_FIELDS = [
    "empilhamento", "embalagem_transporte", "transporte", "preservacao",
    "metodo_limpeza", "ferramentas_para_preservacao", "tipo_legislacao",
    "tipo_descarte", "protecao", "posicao_armazenamento", "unidade", "tipo"
]

# CP 2.4: CONFIG_MAP/VARIAVEIS_SPECS deixaram de ser definidos aqui — agora
# importados de sigft.core.rpa.ficha_layout (fonte única, compartilhada com
# analyzer_backend.py). Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 2 ->
# CP 2.4, e o docstring de ficha_layout.py para o histórico da unificação.
#
# ATENÇÃO: o "range" canônico agora é o range COMPLETO da célula mesclada
# (ex.: "H6:P6", herdado do analyzer_backend) em vez de só a primeira célula
# (ex.: "H6", como este arquivo guardava antes). Os acessos que já faziam
# `.split(":")[0]` (ex.: dentro de `analyze_sheet`, mapeamento estático, e
# `fill_save`) continuam corretos sem alteração; os 2 acessos DIRETOS de
# `analyze_sheet` (txt_brv/fab, logo abaixo) precisaram do mesmo split — ver
# docs/refatoracao/PENDENCIAS.md, entrada do CP 2.4.


# Extensões que o LlamaParse consegue OCRar. Regras de negócio §2.3/§6.1:
# catálogos antigos digitalizados chegam como TIFF/PNG/JPG. Até 2026-08-11 o
# `PDFProcessor` só distinguia ".pdf" de "resto", e o resto ia para o
# BeautifulSoup como se fosse HTML -- uma imagem virava texto-lixo, em
# silêncio.
EXTENSOES_IMAGEM = (".tif", ".tiff", ".png", ".jpg", ".jpeg", ".bmp", ".webp")
EXTENSOES_OCR = (".pdf",) + EXTENSOES_IMAGEM

_CONTENT_TYPE_PARA_SUFIXO = {
    "application/pdf": ".pdf",
    "image/tiff": ".tif",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "text/plain": ".txt",
}


# P-01: todas as células que são MARCAÇÃO de algum grupo de checkbox.
# Usado para não confundir a marca de um grupo com o rótulo do vizinho ao
# varrer a planilha (`J69` fica a 6 colunas de `P69`).
_CELULAS_DE_MARCACAO = {
    celula
    for cfg in CONFIG_MAP.values()
    if cfg.get("type") == "checkbox"
    for celula in cfg.get("cells", [])
}


def _indice_da_coluna(letras):
    """`"A"` -> 1, `"H"` -> 8, `"AA"` -> 27. Equivale a
    `openpyxl.utils.column_index_from_string`, reimplementado em stdlib de
    propósito: `tests/conftest.py` stuba `openpyxl` como um `MagicMock`, que
    não é pacote, então `from openpyxl.utils import ...` quebraria a coleta
    da suíte inteira. Mesmo espírito de `core/excel/headers.py`, que também
    é stdlib-only para poder ser testado sem as dependências pesadas."""
    indice = 0
    for caractere in str(letras).upper():
        if not ("A" <= caractere <= "Z"):
            raise ValueError(f"Letra de coluna invalida: {letras!r}")
        indice = indice * 26 + (ord(caractere) - ord("A") + 1)
    if indice <= 0:
        raise ValueError(f"Letra de coluna invalida: {letras!r}")
    return indice


def _chave_comparacao(texto):
    """Forma canônica para casar resposta da IA com rótulo da planilha:
    sem acento, sem caixa, sem espaço sobrando e sem pontuação de borda.
    "Não reparável", "NAO REPARAVEL" e "nao reparavel." casam entre si."""
    import unicodedata

    s = unicodedata.normalize("NFKD", str(texto or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().strip(" .:;\t\n").split())


# =============================================================================
# CONTRATO DA RESPOSTA DA IA — validado, não confiado
# =============================================================================
# Acrescentado em 2026-08-11, fechando a metade que faltava da pendência que o
# Luan abriu depois do 1º lote rodado num modelo que não é o Gemini (ver
# PENDENCIAS.md): "todos consomem `resp.parsed_json` e indexam o resultado
# assumindo o formato do prompt; nenhum valida". O desenho é o MESMO de
# `services/tech_specs.py:normalizar_resposta_specs` -- de propósito, para que
# o checkpoint que unificar os 4 consumidores tenha duas peças já iguais.
#
# Os defaults PERIGOSOS deste módulo, que é o que esta validação protege:
#
#   1. `fill_save` faz `for k, val in ai_data.items()`. Se a IA devolver uma
#      LISTA (ou o envelope `{"campos": {...}}`), `.items()` estoura
#      `AttributeError` com uma mensagem que não diz nada sobre IA -- ou, pior,
#      itera as chaves erradas.
#   2. `if k in missing` DESCARTA em silêncio todo campo que a IA inventou. O
#      engenheiro não fica sabendo que a IA respondeu algo que foi jogado fora.
#   3. Um valor que seja `dict`/`list` iria para `ws[ref].value` e viraria
#      lixo dentro da célula da ficha.
#
# O que NÃO se faz aqui, seguindo a lição do tech_specs: traduzir nome de
# campo. Renomear a chave que um modelo inventou é adivinhar o sinônimo DAQUELE
# modelo, e o próximo inventa outro. Envelope, sim, é desembrulhado -- é
# ambiguidade de formatação, não de significado.

CHAVE_VALOR = "valor"
CHAVE_FONTE = "fonte"


def normalizar_resposta_autospec(bruto, campos_pedidos=None, callbacks=None):
    """Devolve `(valores, fontes)` da resposta da IA, ou levanta `ValueError`
    dizendo o que veio no lugar.

    `valores` é o `{campo: valor}` achatado que `fill_save` consome —
    contrato inalterado. `fontes` é `{campo: origem}` (P-04), vazio quando o
    modelo não informou.

    Aceita as DUAS formas de valor, de propósito:
      - `{"campo": "resposta"}` — a forma anterior ao P-04, que um modelo
        mais fraco devolve mesmo com a instrução nova no prompt;
      - `{"campo": {"valor": ..., "fonte": ...}}` — a forma que o prompt pede.

    **Desembrulhar envelope aqui é mais delicado que no `tech_specs`.** Lá o
    formato exigido é uma LISTA na raiz, então um dict de 1 chave é
    inequivocamente envelope. Aqui a raiz JÁ É um dict de campos, e
    `{"empilhamento": 5}` é resposta LEGÍTIMA quando só um campo faltava.
    A desambiguação usa `campos_pedidos`: só é envelope quando a chave única
    NÃO é um campo pedido e o valor de dentro é um dict. Sem
    `campos_pedidos`, não desembrulha nada — melhor deixar passar um envelope
    do que engolir uma resposta de campo único.
    """
    cb = callbacks or _callbacks_silenciosos()
    pedidos = set(campos_pedidos or ())

    if bruto is None:
        raise ValueError(
            "A IA não devolveu resposta nenhuma (parse do JSON falhou ou veio vazio)."
        )

    if pedidos:
        for _ in range(3):  # teto contra JSON auto-referente, igual ao tech_specs
            if (
                isinstance(bruto, dict)
                and len(bruto) == 1
                and next(iter(bruto)) not in pedidos
            ):
                unico = next(iter(bruto.values()))
                if isinstance(unico, dict):
                    cb.log(
                        f"Resposta da IA veio embrulhada em {next(iter(bruto))!r} — "
                        f"desembrulhando.",
                        nivel="warn",
                    )
                    bruto = unico
                    continue
            break

    if not isinstance(bruto, dict):
        raise ValueError(
            f"A IA devolveu {type(bruto).__name__}, e o formato exigido é um OBJETO JSON "
            f"{{campo: resposta}} no nível raiz. Conteúdo recebido: {str(bruto)[:200]}. "
            "O modelo escolhido não está seguindo o formato pedido no prompt — troque o "
            "modelo da tarefa 'AutoSpec (RAG)' no painel 'Modelos de IA' da Home."
        )

    valores = {}
    fontes = {}
    inventados = []
    descartados = []

    for campo, conteudo in bruto.items():
        if pedidos and campo not in pedidos:
            # Não é fatal: campo inventado só polui. Mas o silêncio de antes
            # escondia que a IA respondeu algo que foi jogado fora.
            inventados.append(str(campo))
            continue

        if isinstance(conteudo, dict) and CHAVE_VALOR in conteudo:
            valor = conteudo.get(CHAVE_VALOR)
            fonte = conteudo.get(CHAVE_FONTE)
            if fonte:
                fontes[campo] = str(fonte)
        else:
            valor = conteudo

        if isinstance(valor, (dict, list)):
            # Iria para `ws[ref].value` e viraria lixo na célula. Campo vazio
            # é melhor que campo errado (regras de negócio §1.3).
            descartados.append(str(campo))
            continue

        valores[campo] = valor

    if inventados:
        cb.log(
            f"A IA respondeu {len(inventados)} campo(s) que não foram pedidos e serão "
            f"ignorados: {', '.join(sorted(inventados)[:10])}.",
            nivel="warn",
        )
    if descartados:
        cb.log(
            f"{len(descartados)} campo(s) vieram com estrutura aninhada em vez de um "
            f"valor simples e ficarão em branco: {', '.join(sorted(descartados))}.",
            nivel="warn",
        )
    if not bruto:
        # `{}` não é erro de formato: pelas regras de negócio §3.2, campo
        # [ESTRITO] sem evidência DEVE ficar vazio. A IA não ter o que
        # responder é resultado legítimo — só não pode passar despercebido.
        cb.log(
            "A IA não preencheu nenhum campo (resposta vazia). Pelas regras, campo sem "
            "evidência fica em branco — confira se o contexto chegou até ela.",
            nivel="warn",
        )
    elif pedidos and not valores:
        # Veio conteúdo, e NADA dele era aproveitável: aí é formato errado,
        # não ausência de evidência. Falhar alto.
        raise ValueError(
            f"A IA respondeu, mas nenhum dos {len(pedidos)} campos pedidos veio num "
            f"formato aproveitável. Chaves recebidas: "
            f"{', '.join(sorted(str(c) for c in bruto)[:10]) or '(nenhuma)'}. "
            "O modelo escolhido não está seguindo o formato pedido no prompt — troque o "
            "modelo da tarefa 'AutoSpec (RAG)' no painel 'Modelos de IA' da Home."
        )

    return valores, fontes


# Quantos resultados pedir por busca. O CSE aceita ate 10 e cobra a MESMA
# cota (1 query) para 3 ou para 10 -- pedir 3, como era ate 2026-08-11, jogava
# fora 70% do que ja estava pago.
RESULTADOS_POR_BUSCA = 10

# Cache de busca web: query -> resposta crua da CSE. Mesmo padrao dos caches de
# catalogo de modelo (`core/llm/catalogo.py`): JSON na raiz, com carimbo de
# tempo e TTL, gitignored.
#
# Existe por causa da cota: o free tier da Google CSE da 100 queries/DIA, e a
# cascata gasta varias por ficha. Sem cache, reprocessar o mesmo lote (que e o
# normal quando se ajusta um manual e roda de novo) queimava a cota inteira de
# novo. O que se guarda e a lista de URLs, nao os arquivos -- caminho de
# temporario nao sobrevive a execucao, mas a URL sim, e e ela que custou cota.
BUSCA_WEB_CACHE = "busca_web_cache.json"
BUSCA_WEB_CACHE_TTL_S = 7 * 24 * 3600  # datasheet de fabricante muda devagar


def _caminho_cache_busca():
    """Ao lado do `api_config.json`, seguindo `core/llm/catalogo.py`.

    A intenção sempre foi essa; o caminho é que não a cumpria. Ele saía de
    `os.path.dirname(os.path.abspath(config.CONFIG_FILE))`, e `CONFIG_FILE` é
    só o NOME do arquivo — na prática isso dava o diretório de TRABALHO, não a
    pasta do `api_config.json`. Sob `Program Files` (o padrão do instalador)
    essa pasta é somente-leitura e o cache nunca conseguiria ser escrito.
    """
    from sigft.core.dados_usuario import caminho

    return str(caminho(BUSCA_WEB_CACHE))


def _cache_busca_ler(query, agora=None):
    """Resposta guardada para `query`, ou `None` se ausente/expirada."""
    import time

    agora = time.time() if agora is None else agora
    try:
        with open(_caminho_cache_busca(), encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except Exception:
        return None
    if not isinstance(dados, dict):
        return None
    entrada = dados.get(query)
    if not isinstance(entrada, dict):
        return None
    gravado_em = entrada.get("gravado_em")
    items = entrada.get("items")
    if not isinstance(items, list) or not isinstance(gravado_em, (int, float)):
        return None
    if agora - gravado_em > BUSCA_WEB_CACHE_TTL_S:
        return None
    return items


def _cache_busca_gravar(query, items, agora=None):
    """Guarda a resposta de `query`. Falhar aqui nao e erro do usuario."""
    import time

    agora = time.time() if agora is None else agora
    caminho = _caminho_cache_busca()
    try:
        try:
            with open(caminho, encoding="utf-8") as arquivo:
                dados = json.load(arquivo)
            if not isinstance(dados, dict):
                dados = {}
        except Exception:
            dados = {}
        dados[query] = {"gravado_em": agora, "items": items}
        with open(caminho, "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo, indent=2, ensure_ascii=False)
    except Exception:
        pass  # cache e conveniencia; nao poder gravar nao quebra a execucao


# =============================================================================
# LASTRO DOCUMENTAL — o valor respondido está mesmo no documento?
# =============================================================================
# Pedido do usuário em 2026-08-13: "não gostei do ato de aceitar uma
# informação errada. Isto não deve acontecer."
#
# O QUE ISTO GARANTE, E O QUE NÃO GARANTE — a distinção importa.
#
# Garante: todo valor escrito num campo TÉCNICO aparece literalmente no
# documento que foi lido. Número que a IA respondeu e que não existe em lugar
# nenhum do contexto não chega à célula; o campo fica vazio e o console diz
# qual foi. Isso é verificável por código, sem probabilidade envolvida.
#
# NÃO garante "correto" no sentido de engenharia. Se o próprio datasheet
# estiver errado, ou for de outra peça, o valor tem lastro e mesmo assim está
# errado. Por isso o lastro é a SEGUNDA camada de três:
#
#   1. filtro anti-intruso (§4.3) — o documento é deste material?
#   2. lastro documental (aqui)   — o valor saiu mesmo do documento?
#   3. conferência humana         — a lista de origens por campo, no console
#
# Nenhuma das três sozinha basta. Juntas, o caminho para um dado errado
# entrar na ficha exige que o documento seja do material certo E que o valor
# esteja escrito nele.
_RE_NUMERO = re.compile(r"\d+(?:[.,]\d+)?")


def _numeros_normalizados(texto):
    """Números de um texto, comparáveis: `25,4` e `25.40` viram ambos `25.4`.

    Fabricante escreve decimal com ponto, planilha brasileira com vírgula, e
    a IA copia ora um ora outro. Sem normalizar, o valor certo seria
    descartado por diferença de pontuação.
    """
    achados = set()
    for bruto in _RE_NUMERO.findall(str(texto or "")):
        n = bruto.replace(",", ".")
        if "." in n:
            n = n.rstrip("0").rstrip(".")
        achados.add(n or "0")
    return achados


def _exige_lastro(campo):
    """Este campo precisa de prova documental?

    **Só a TABELA DE ESPECIFICAÇÕES (`var_row_*`).** Regressão corrigida em
    2026-08-13, olhando o console de 10 fichas reais que o Luan processou: o
    lastro estava bloqueando `fabricante`, `texto_breve_material` e os
    checkbox de origem, periculosidade e logística reversa — 7 dos 9 campos
    barrados numa ficha, e todos eles campos que **funcionavam antes**.

    O erro de raciocínio foi meu: apliquei a tudo uma regra que só faz
    sentido para dado técnico. `fabricante = WAGO` não sai de datasheet, sai
    da planilha; `logística reversa = Aplica-se` não sai de documento
    nenhum, sai de julgamento sobre a legislação. Exigir prova documental
    deles é exigir prova de algo que nunca foi para ser provado assim.

    O risco que o lastro existe para cobrir é outro: um valor técnico
    plausível e errado (`IP65` onde o documento diz `IP67`) escrito numa
    ficha que vai para a Itaipu. Esse risco mora inteiro na tabela de
    especificações.
    """
    return str(campo or "").startswith("var_row_")


def valor_tem_lastro(valor, contexto):
    """O valor respondido é rastreável ao contexto que foi enviado?

    Duas regras, nesta ordem:

    1. **Se o valor tem número, TODOS os números precisam estar no contexto.**
       Basta um inventado para reprovar — `"entre 175 e 999 bar"` cai mesmo
       com o 175 correto. Meia verdade num campo técnico é pior que campo
       vazio, porque passa na conferência por parecer certa.

    2. **Se não tem número**, exige que alguma palavra de 4+ letras apareça
       no contexto (`NBR`, `Nitrile`). Valor curto sem palavra longa
       (`"N/A"`, `"X"`) passa: não há o que verificar, e não é dado técnico.

    **Conversão de unidade é CONFERIDA, não reprovada** (2026-08-13, ajuste
    pedido pelo usuário). `35 MPa` a partir de `350 bar` não tem o `35`
    escrito em lugar nenhum, mas é conversão correta e não pode ser
    descartada. Quem confere é `autospec_unidades.conferir_texto`, que
    **refaz a conta** a partir do número do documento — não confia no cálculo
    da IA. `3,5 MPa` a partir de `350 bar` continua reprovando, e é justamente
    o erro de ordem de grandeza que ninguém percebe olhando.
    """
    texto = str(valor if valor is not None else "").strip()
    if not texto:
        return True  # vazio não precisa de lastro; não vai escrever nada

    ctx = _normalizar_texto_busca(contexto)

    # CÓDIGO ALFANUMÉRICO tem de aparecer INTEIRO, não só os dígitos dele.
    #
    # Bug real, encontrado auditando este próprio módulo em 2026-08-13:
    # `IP65` era APROVADO contra um documento que dizia `IP67`, porque o
    # `65` aparecia noutro lugar (`65 mm`). O grau de proteção errado entrava
    # na ficha exatamente pelo caminho que existe para impedir isso. Vale
    # para `IP67`, `DN50`, `G1/2`, `M8` — tudo que mistura letra e dígito.
    ctx_compacto = _compactar_codigo(ctx)
    for codigo in re.findall(r"[a-z]+\d[a-z0-9]*|\d+[a-z]+[a-z0-9]*",
                             _normalizar_texto_busca(texto)):
        if _compactar_codigo(codigo) not in ctx_compacto:
            return False

    # NÚMERO COM UNIDADE é conferido como MEDIDA, nunca só pelo número.
    #
    # Bug real, achado na varredura de 2026-08-13: `41 g` era APROVADO contra
    # um documento que diz `41 kg`, porque o `41` estava lá. Mil vezes de
    # diferença, e o caminho literal nunca olhava a unidade. Vale para todo
    # par grandeza/prefixo: `350 kPa` contra `350 bar`, `25,4 cm` contra
    # `25,4 mm`.
    medida_ok, numeros_soltos = _conferir_medidas(texto, contexto)
    if medida_ok is False:
        return False

    numeros_valor = numeros_soltos if medida_ok else _numeros_normalizados(texto)
    if numeros_valor:
        if numeros_valor <= _numeros_normalizados(ctx):
            return True
        return bool(explicar_conversao(texto, contexto))
    if medida_ok:
        return True  # tudo que havia eram medidas, e todas conferiram

    palavras = re.findall(r"[a-z]{4,}", _normalizar_texto_busca(texto))
    if not palavras:
        return True
    return any(p in ctx for p in palavras)


def _conferir_medidas(texto, contexto):
    """`(resultado, numeros_sem_unidade)` para o lastro.

    `resultado` é `True` quando havia medidas e TODAS conferiram (literal ou
    por conversão), `False` quando alguma não conferiu, e `None` quando não
    havia medida nenhuma — aí o caminho literal decide sozinho.
    """
    try:
        from sigft.services import autospec_unidades
    except ImportError:
        return None, set()
    try:
        if not autospec_unidades.extrair_medidas(texto):
            return None, set()
        ok, _explicacoes = autospec_unidades.conferir_texto(texto, contexto)
        if not ok:
            return False, set()
        soltos = {
            f"{v:g}".rstrip("0").rstrip(".") if "." in f"{v:g}" else f"{v:g}"
            for v in autospec_unidades.numeros_sem_unidade(texto)
        }
        return True, soltos
    except Exception:
        return None, set()


def explicar_conversao(valor, contexto):
    """Explicações da conversão, ou lista vazia se não for conversão válida.

    Fica aqui, e não dentro de `valor_tem_lastro`, porque quem filtra precisa
    do MESMO resultado duas vezes: para decidir se aprova e para dizer no
    console de onde veio o número. Calcular uma vez e passar adiante evitaria
    a segunda chamada, mas custaria clareza no ponto de uso — e são dezenas
    de campos, não milhões.
    """
    try:
        from sigft.services import autospec_unidades
    except ImportError:
        return []
    ok, explicacoes = autospec_unidades.conferir_texto(valor, contexto)
    if not ok:
        return []

    # Só é CONVERSÃO quando o valor mudou de forma. `30,3 kg = 30.3 kg` foi
    # copiado do documento, não calculado — anunciá-lo como conversão é
    # factualmente falso e faz o engenheiro desconfiar de um valor correto.
    # Achado na varredura de 2026-08-13, olhando o console de uma ficha real
    # de motor: 2 dos 4 "convertidos" eram literais.
    reais = []
    for explicacao in explicacoes:
        esquerda, _, direita = explicacao.partition(" = ")
        if _compactar_codigo(esquerda) != _compactar_codigo(direita):
            reais.append(explicacao)
    return reais


def _e_timeout(erro):
    """A chamada estourou o TEMPO (e não foi recusada)?

    `ReadTimeout`/`ConnectTimeout` do requests, `TimeoutError` da biblioteca
    padrão, `DeadlineExceeded` do SDK do Gemini -- os nomes variam, a palavra
    não.
    """
    nome = type(erro).__name__.lower()
    texto = str(erro).lower()
    return "timeout" in nome or "deadline" in nome or "timed out" in texto


def _corrigir_conversao(valor, contexto, pergunta=None):
    """Ponte para `autospec_unidades.corrigir_conversao`, tolerante à ausência
    do módulo — mesmo padrão de `explicar_conversao`.

    `pergunta` é o ENUNCIADO do campo, e é o que desempata quando o documento
    tem duas medidas da mesma grandeza: "6 - PRESSAO DE TRABALHO" aponta para
    "Maximum operating pressure" e não para "Peak pressure".
    """
    try:
        from sigft.services import autospec_unidades
    except ImportError:
        return None, ""
    try:
        return autospec_unidades.corrigir_conversao(valor, contexto, pergunta=pergunta)
    except Exception:
        return None, ""


def origens_do_contexto(contexto):
    """Nomes/URLs que aparecem nos marcadores `--- LOCAL DOC: x ---`.

    São os documentos que REALMENTE foram lidos. Uma fonte citada pela IA que
    não esteja aqui é sinal de invenção — e o engenheiro precisa saber disso
    antes de homologar.
    """
    texto = str(contexto or "")
    origens = set(re.findall(r"---\s*(?:LOCAL|WEB) DOC:\s*(.+?)\s*---", texto))
    # A URL TAMBEM (2026-09-15). O marcador leva o TITULO do documento
    # (`--- WEB DOC: Cisco Catalyst IE3200 ... - Amplicon ---`), e a URL vem na
    # linha seguinte. A IA cita a URL -- e a comparacao, por substring, nao
    # casava uma coisa com a outra: no log da ficha `4500063671.0070`, 26
    # campos foram acusados de citar "fonte que NAO esta entre os documentos
    # lidos" sendo que citavam exatamente o documento lido.
    #
    # Aviso falso em 26 campos ensina o usuario a ignorar o aviso, e ai o
    # verdadeiro passa junto. E o aviso verdadeiro aqui e serio: fonte que
    # ninguem leu e sinal de invencao.
    origens.update(re.findall(r"^URL:\s*(\S+)\s*$", texto, flags=re.MULTILINE))
    return origens


# Fontes que NÃO são documento e são legítimas: os campos gerativos
# (embalagem, transporte, descarte) saem de conhecimento técnico por desenho.
_FONTES_SEM_DOCUMENTO = ("conhecimento", "tecnico", "técnico", "padrao", "padrão", "boa pratica")


# =============================================================================
# CACHE DE RESPOSTA DA IA — 100% de economia ao reprocessar a mesma ficha
# =============================================================================
# O cache de busca (acima) poupa COTA da CSE; este poupa TOKEN, que e o custo
# dominante. Reprocessar um lote e o normal, nao a excecao: se um campo saiu
# errado, o usuario ajusta a planilha e roda tudo de novo -- e ate 2026-08-12
# cada rerun pagava a conta inteira da IA outra vez, incluindo as fichas que
# ja tinham vindo certas.
#
# A CHAVE E O PROMPT INTEIRO, nao o nome do arquivo. E o unico jeito de o
# acerto ser seguro: o prompt ja contem material, fabricante, contexto
# recortado e a lista de campos faltantes, entao qualquer coisa que mudaria a
# resposta ja muda a chave. Consequencias, todas desejadas:
#   - editou a ficha (mudou o que falta preencher) -> chave nova, IA roda;
#   - trocou/adicionou manual -> contexto muda -> chave nova, IA roda;
#   - renomeou o arquivo sem mudar nada -> MESMA chave, acerto;
#   - trocou de modelo -> chave nova (provider+modelo entram no hash), porque
#     a resposta de outro modelo nao pode ser servida como se fosse deste.
#
# PRIVACIDADE: o que vai para o disco e o HASH do prompt, nunca o prompt. O
# arquivo guarda o valor tecnico respondido (que e o que precisa ser servido
# de volta) mas nao o trecho do datasheet que o originou. Fica gitignored, ao
# lado do `api_config.json`, como os demais caches do projeto.
RESPOSTA_IA_CACHE = "autospec_resposta_cache.json"
# 30 dias: as entradas do prompt ja estao na chave, entao o TTL nao existe
# para corrigir resposta velha -- existe para o arquivo nao crescer para
# sempre com ficha que ninguem vai reprocessar.
RESPOSTA_IA_CACHE_TTL_S = 30 * 24 * 3600
RESPOSTA_IA_CACHE_MAX_ENTRADAS = 500


def _caminho_cache_resposta():
    """Ao lado do `api_config.json`, igual ao cache de busca (ver acima)."""
    from sigft.core.dados_usuario import caminho

    return str(caminho(RESPOSTA_IA_CACHE))


def _chave_cache_resposta(prompt, provider=None, model=None, anexos=None):
    """Hash de (provider, modelo, prompt, arquivos). Ver o bloco acima para
    por que o prompt inteiro entra, e por que o modelo tambem.

    `anexos` (2026-09-24): os BYTES de cada PDF que foi junto. No caminho
    nativo o prompt leva so o NOME do arquivo -- sem os bytes na chave, a
    revisao nova de um datasheet com o mesmo nome receberia a resposta dada
    a revisao velha.
    """
    bruto = f"{provider or ''}|{model or ''}|{prompt or ''}"
    digestor = hashlib.sha256(bruto.encode("utf-8"))
    for dados in anexos or ():
        digestor.update(hashlib.sha256(dados).digest())
    return digestor.hexdigest()


def _cache_resposta_ler(chave, agora=None):
    """Resposta guardada para `chave`, ou `None` se ausente/expirada."""
    import time

    agora = time.time() if agora is None else agora
    try:
        with open(_caminho_cache_resposta(), encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except Exception:
        return None
    if not isinstance(dados, dict):
        return None
    entrada = dados.get(chave)
    if not isinstance(entrada, dict):
        return None
    gravado_em = entrada.get("gravado_em")
    if not isinstance(gravado_em, (int, float)):
        return None
    if agora - gravado_em > RESPOSTA_IA_CACHE_TTL_S:
        return None
    resposta = entrada.get("resposta")
    # Só dict/list são respostas legítimas da IA aqui; qualquer outra coisa é
    # arquivo corrompido ou de uma versão anterior do formato.
    if not isinstance(resposta, (dict, list)):
        return None
    return resposta


def _cache_resposta_gravar(chave, resposta, agora=None):
    """Guarda `resposta` sob `chave`, podando o que expirou. Falhar aqui nao e
    erro do usuario -- ele so paga a IA de novo no proximo rerun."""
    import time

    agora = time.time() if agora is None else agora
    if not isinstance(resposta, (dict, list)) or not resposta:
        return  # resposta vazia nao vale a pena servir de volta
    try:
        try:
            with open(_caminho_cache_resposta(), encoding="utf-8") as arquivo:
                dados = json.load(arquivo)
            if not isinstance(dados, dict):
                dados = {}
        except Exception:
            dados = {}

        dados[chave] = {"gravado_em": agora, "resposta": resposta}

        # Poda: primeiro o que expirou, depois o excedente mais antigo. Sem
        # isto o arquivo cresceria sem limite e o cache viraria um problema
        # em vez de uma economia.
        vivas = {
            k: v
            for k, v in dados.items()
            if isinstance(v, dict)
            and isinstance(v.get("gravado_em"), (int, float))
            and agora - v["gravado_em"] <= RESPOSTA_IA_CACHE_TTL_S
        }
        if len(vivas) > RESPOSTA_IA_CACHE_MAX_ENTRADAS:
            recentes = sorted(vivas.items(), key=lambda kv: kv[1]["gravado_em"], reverse=True)
            vivas = dict(recentes[:RESPOSTA_IA_CACHE_MAX_ENTRADAS])

        with open(_caminho_cache_resposta(), "w", encoding="utf-8") as arquivo:
            json.dump(vivas, arquivo, indent=2, ensure_ascii=False)
    except Exception:
        pass  # cache e conveniencia; nao poder gravar nao quebra a execucao


# =============================================================================
# LEITURA DE PDF — local primeiro, e com prova de que foi lido INTEIRO
# =============================================================================
# Acrescentado em 2026-08-11. Até aqui a única aferição de "consegui ler" era:
#
#     if t and len(t) > 100:
#
# Cem caracteres. Um datasheet de 40 páginas do qual se leu UMA LINHA da capa
# passava nesse teste e entrava no contexto como se fosse o documento inteiro.
# A IA respondia "não encontrei" para tudo, e ninguém ficava sabendo que o
# problema tinha sido a LEITURA, não o documento.
#
# O PyMuPDF entrega o texto página a página, então dá para medir cobertura de
# verdade e dizer QUAIS páginas ficaram de fora. Decisão do usuário
# (2026-08-11): leitura incompleta AVISA e SEGUE com o que leu -- coerente com
# a regra de negócio §3.2 (campo sem evidência fica vazio) e com o fato de que
# 37 páginas boas valem mais que o descarte por causa de 3 ruins.

# Abaixo disto a página é tratada como "sem texto útil". Página técnica de
# datasheet tem tipicamente 1.000-3.000 caracteres; 40 é capa, número de
# página ou cabeçalho solto.
MIN_CHARS_PAGINA_UTIL = 40

# Cobertura abaixo disto marca o documento como leitura INCOMPLETA no log.
COBERTURA_MINIMA_ACEITAVEL = 0.80


class RelatorioLeitura:
    """Quanto de um PDF foi realmente lido, e o que ficou de fora."""

    def __init__(self, metodo, paginas_total, paginas_lidas, chars, paginas_sem_texto,
                 paginas=None):
        self.metodo = metodo
        self.paginas_total = paginas_total
        self.paginas_lidas = paginas_lidas
        self.chars = chars
        self.paginas_sem_texto = paginas_sem_texto
        # O texto de CADA pagina, na ordem, inclusive as vazias (2026-09-24):
        # e o que `autospec_documentos` usa para marcar `[página N]` e para
        # saber que pagina e imagem. Ver `PDFProcessor.ler_paginas`.
        self.paginas = list(paginas or [])

    @property
    def cobertura(self):
        if not self.paginas_total:
            return 0.0
        return self.paginas_lidas / self.paginas_total

    @property
    def completa(self):
        return self.paginas_total > 0 and self.cobertura >= COBERTURA_MINIMA_ACEITAVEL

    def nivel_log(self):
        return "info" if self.completa else "warn"

    def resumo(self, nome):
        base = (
            f"{nome}: {self.paginas_total} pagina(s), {self.paginas_lidas} lida(s) "
            f"({self.cobertura:.0%}), {self.chars} chars [{self.metodo}]"
        )
        if self.completa:
            return base
        faltantes = ", ".join(str(p) for p in self.paginas_sem_texto[:12])
        reticencias = "..." if len(self.paginas_sem_texto) > 12 else ""
        return (
            f"{base} — LEITURA INCOMPLETA. Sem texto nas paginas: "
            f"{faltantes}{reticencias}. Provavelmente escaneadas; precisariam de OCR. "
            f"Seguindo com o que foi lido — confira os campos que dependiam dessas paginas."
        )


def _ler_pdf_local(filepath):
    """Lê o PDF na PRÓPRIA MÁQUINA, página a página, via PyMuPDF.

    Devolve `(texto, RelatorioLeitura)` ou `("", None)` quando o PyMuPDF não
    está instalado ou não conseguiu abrir o arquivo — nesse caso quem chama
    cai para o PyPDF2.

    Por que PyMuPDF e não PyPDF2 como primeira opção: o PyPDF2 entrega texto
    corrido e **desmancha tabelas**, e datasheet é quase só tabela. O PyMuPDF
    preserva a ordem de leitura do layout e ainda informa, por página, se há
    imagem — que é o sinal de "esta página aqui é digitalizada".
    """
    try:
        import pymupdf  # import preguiçoso: o módulo importa sem a dependência
    except ImportError:
        try:
            import fitz as pymupdf  # nome antigo do mesmo pacote
        except ImportError:
            return "", None

    try:
        documento = pymupdf.open(filepath)
    except Exception:
        return "", None

    partes = []
    todas = []
    paginas_sem_texto = []
    lidas = 0
    try:
        total = documento.page_count
        for indice in range(total):
            try:
                texto = documento[indice].get_text() or ""
            except Exception:
                texto = ""
            if len(texto.strip()) >= MIN_CHARS_PAGINA_UTIL:
                partes.append(texto)
                todas.append(texto)
                lidas += 1
            else:
                paginas_sem_texto.append(indice + 1)  # 1-based, como o usuário conta
                todas.append("")
    finally:
        try:
            documento.close()
        except Exception:
            pass

    conteudo = "\n".join(partes)
    return conteudo, RelatorioLeitura(
        metodo="PyMuPDF",
        paginas_total=total,
        paginas_lidas=lidas,
        chars=len(conteudo),
        paginas_sem_texto=paginas_sem_texto,
        paginas=todas,
    )


def _callbacks_silenciosos():
    """`UICallbacks` que engole tudo — default de quem chama sem passar
    callbacks (testes antigos, uso programático). Mantém a assinatura
    retrocompatível sem espalhar `if callbacks:` pelo módulo."""
    return UICallbacks(log=lambda *a, **k: None)


def _sufixo_para_url(url, content_type=None):
    """Sufixo de arquivo temporário para um download.

    Antes de 2026-08-11 era `".pdf" if url.lower().endswith(".pdf") else
    ".html"` — o que erra em dois casos comuns em site de fabricante:
    URL de PDF com query string (`.../datasheet.pdf?download=1`, que não
    termina em ".pdf") e imagem digitalizada (vira ".html" e é lida como
    HTML). Agora olha o caminho da URL sem a query e, quando disponível, o
    `Content-Type` da resposta, que é a fonte mais confiável.
    """
    caminho = str(url or "").split("?")[0].split("#")[0].lower()
    for ext in EXTENSOES_OCR + (".txt",):
        if caminho.endswith(ext):
            return ext
    if content_type:
        base = str(content_type).split(";")[0].strip().lower()
        if base in _CONTENT_TYPE_PARA_SUFIXO:
            return _CONTENT_TYPE_PARA_SUFIXO[base]
    return ".html"


# =============================================================================
# CASAMENTO DE TERMO — o que o fabricante ESCREVE vs. o que a planilha GUARDA
# =============================================================================
# A planilha do PMIB guarda a RAZÃO SOCIAL brasileira (`HYDAC TECNOLOGIA
# LTDA`); o datasheet e o site do fabricante dizem `HYDAC`, `HYDAC Technology
# Corporation`, `HYDAC International`. Esta distância entre os dois mundos foi
# a causa raiz da falha de 2026-08-12 (ficha 4500063671.1188, 0 de 22 campos
# preenchidos) — ver `tests/test_autospec_busca_web_falha_real.py`.
#
# Palavras que compõem razão social e NÃO aparecem em documento técnico.
# `TECNOLOGIA` está aqui de propósito: é parte do nome jurídico da Hydac no
# Brasil, não do nome pelo qual o produto é publicado.
_RUIDO_RAZAO_SOCIAL = frozenset({
    "ltda", "ltda.", "sa", "s.a", "s.a.", "s/a", "eireli", "me", "epp",
    "cia", "cia.", "companhia", "industria", "industrias", "ind", "ind.",
    "comercio", "com", "com.", "comercial", "tecnologia", "tecnologias",
    "do", "da", "de", "dos", "das", "e", "brasil", "brazil",
    "gmbh", "inc", "inc.", "corp", "corp.", "corporation", "co", "co.",
    "llc", "ag", "kg", "bv", "nv", "spa", "srl", "plc", "sas",
    "group", "grupo", "sistemas", "equipamentos", "servicos",
    "importacao", "exportacao", "distribuidora", "representacoes",
    # 2026-08-13, varredura: `WEG EQUIPAMENTOS ELETRICOS SA` virava
    # `WEG ELETRICOS`. Ancorar em `eletricos` aprova qualquer catálogo
    # elétrico brasileiro, e polui a query com uma palavra que o fabricante
    # não usa no nome do produto.
    "eletricos", "eletricas", "eletrico", "eletrica", "eletronica",
    "mecanica", "hidraulica", "pneumatica", "automacao", "industrial",
    "industriais", "motores", "maquinas", "produtos", "solucoes",
    "engenharia", "componentes", "pecas", "materiais", "instrumentacao",
})


def _sem_acento(texto):
    """`válvula` -> `valvula`. A planilha tem acento; URL e título, não."""
    normalizado = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in normalizado if unicodedata.category(c) != "Mn")


def _normalizar_texto_busca(texto):
    """Minúsculas, sem acento — a forma em que dois textos são comparáveis."""
    return _sem_acento(texto).lower()


def _compactar_codigo(texto):
    """Só letras e dígitos: `CS 1000 Series` e `CS-1000` viram `cs1000series`
    e `cs1000`.

    Existe porque fabricante escreve o mesmo código de três jeitos —
    `CS1320`, `CS 1320`, `CS-1320` — e o casamento por substring falharia em
    dois deles. Aplicado só a código de peça, nunca a texto corrido.
    """
    return re.sub(r"[^a-z0-9]", "", _normalizar_texto_busca(texto))


# Valores que a planilha põe no lugar do fabricante quando NÃO HÁ fabricante.
# Ancorar o filtro anti-intruso em `DIVERSOS` aprovaria qualquer página que
# diga "diversos" — pior que não ter âncora, porque parece que tem.
_FABRICANTE_GENERICO = frozenset({
    "diversos", "diverso", "varios", "varias", "generico", "generica",
    "n/a", "na", "n.a.", "nd", "n/d", "nao aplicavel", "nao informado",
    "sem marca", "sem fabricante", "nacional", "importado", "similar",
    # Ficha em INGLES (2026-09-03): o campo Manufacturer preenchido com um
    # marcador de ausencia passava pelo filtro e disparava uma busca web
    # inutil, com o marcador dentro da query.
    "not applicable", "not aplicable", "not informed", "unknown", "none",
    "-", "--", "?", "xxx", "0",
})

# Preposições e artigos que não podem SOBRAR no fim de uma query truncada.
_LIGACAO_SOLTA = frozenset({
    "de", "da", "do", "das", "dos", "para", "por", "com", "sem", "em",
    "no", "na", "nos", "nas", "a", "o", "as", "os", "e", "ou", "ao", "aos",
})

# Teto de download. Catálogo de fabricante de centenas de MB existe, e
# `response.content` carregava o corpo INTEIRO na memória: numa máquina de
# usuário isso é o app travando sem mensagem nenhuma.
TETO_DOWNLOAD_BYTES = 40 * 1024 * 1024


def _e_termo_puramente_numerico(termo):
    """`3332066` sim; `750-362` e `CS1320` NÃO.

    Muda a REGRA de casamento: número solto casando por substring vira
    coringa (`123` dentro de `123456`), e por isso exige fronteira de
    palavra.

    **O hífen tira o termo desta categoria**, e a distinção não é cosmética.
    Bug real de 2026-08-13: `750-362` (o código WAGO) compactava para
    `750362`, era classificado como numérico puro, e então a busca por
    fronteira procurava `750362` no alvo **não compactado** — onde está
    escrito `750-362`. Nunca casava. Todos os códigos WAGO, CISCO e NIDEC da
    planilha do SFC têm hífen: nenhum deles seria reconhecido.

    Um termo com separador é código de peça, não número solto — e código de
    peça casa pelo caminho compactado, que é onde `750-362` e `750362` se
    encontram.
    """
    texto = str(termo or "").strip()
    if not texto.isdigit():
        return False
    return True


# =============================================================================
# DOCUMENTO QUE COBRE VARIOS MODELOS (2026-09-14)
# =============================================================================
# Pedido do usuario depois do defeito das dimensoes. O lastro conferia
# PRESENCA -- "este numero esta no documento?" -- e nao PERTINENCIA -- "este
# numero e DESTE modelo?". Num datasheet de familia isso deixa passar mistura:
#
#     UCSCH1, UCSCH2, UCSCS2: 168 x 150 x 55 mm
#     UCECH1:                 168 x 150 x 85 mm
#
# A resposta `168 x 150 x 85 mm` pega altura e profundidade de um modelo e a
# largura de outro. Os tres numeros estao no documento, entao o lastro
# aprovava -- e o engenheiro nao tem como perceber olhando.

# Um lado esquerdo de `X: valor` so e tratado como ROTULO DE MODELO quando
# parece codigo: letra e digito juntos. `Certificate:` e
# `Operating temperature:` continuam sendo rotulo comum, e a linha inteira
# vale para todas as variantes.
_RE_LINHA_COM_ROTULO = re.compile(r"^\s*([^:]{2,80}?)\s*:\s*(.*\S.*)$")
_RE_PARECE_CODIGO = re.compile(r"^(?=[a-z0-9\-/.]*[a-z])(?=[a-z0-9\-/.]*\d)[a-z0-9\-/.]{3,}$")


def _codigos_do_rotulo(rotulo):
    """Os tokens do lado esquerdo que parecem codigo de modelo."""
    return [t for t in re.split(r"[,;/]|\s+", _normalizar_texto_busca(rotulo))
            if t and _RE_PARECE_CODIGO.match(t)]


def contexto_do_modelo(contexto, modelo):
    """So as linhas do documento que servem para ESTE modelo.

    Tres casos, por linha:

    - a linha se declara de um ou mais modelos (`UCECH1: ...`) e o MEU esta
      entre eles -> fica;
    - a linha se declara de outros modelos -> **sai**. E a linha que produzia
      a mistura;
    - a linha nao se declara de modelo nenhum (cabecalho de secao, temperatura
      de operacao, norma aplicavel) -> fica. Spec compartilhada vale para
      todas as variantes, e cortar isso esvaziaria a ficha.

    Sem modelo informado, ou documento em que nenhuma linha se declara de um
    modelo, devolve o contexto INTEIRO: nao ha o que decidir, e recortar por
    um modelo que nao existe cegaria o lastro.

    A comparacao e por codigo COMPACTADO (`_compactar_codigo`), entao
    `IE-3200-8T2S-E` da planilha casa com `IE3200-8T2S-E` do documento. Hifen
    nao pode decidir se o dado entra na ficha.
    """
    texto = str(contexto or "")
    alvo = _compactar_codigo(_normalizar_texto_busca(modelo or ""))
    if not alvo or not texto:
        return texto

    linhas = texto.splitlines()
    guardadas = []
    cortou = False
    achou_o_meu = False
    for linha in linhas:
        casamento = _RE_LINHA_COM_ROTULO.match(linha)
        codigos = _codigos_do_rotulo(casamento.group(1)) if casamento else []
        if not codigos:
            guardadas.append(linha)          # spec compartilhada
            continue
        compactos = [_compactar_codigo(c) for c in codigos]
        # `in` nos dois sentidos: o documento pode trazer a familia
        # (`IE-3200`) onde a planilha traz o SKU (`IE-3200-8T2S-E`), e
        # vice-versa.
        if any(c == alvo or c in alvo or alvo in c for c in compactos):
            achou_o_meu = True
            guardadas.append(linha)
        else:
            cortou = True

    if not cortou:
        return texto
    # NAO CORTAR TUDO (2026-09-15). Se nenhuma linha casou com o meu modelo,
    # e mais provavel que ele esteja grafado diferente do que o documento
    # inteiro ser de outro produto -- e um recorte que remove todas as linhas
    # de especificacao deixaria a ficha vazia com o dado bem ali.
    if not achou_o_meu:
        return texto
    return "\n".join(guardadas)


def _com_unidade_do_enunciado(valor, pergunta):
    """A resposta com a unidade que a PERGUNTA ja declara, quando ela falta.

    So para CONFERIR. O que vai para a ficha continua sendo o valor original:
    a pergunta ja diz a unidade, e reescrever a resposta do fornecedor seria
    mudar um entregavel por conta propria.
    """
    try:
        from sigft.services import autospec_unidades
    except ImportError:
        return valor
    try:
        return autospec_unidades.aplicar_unidade_da_pergunta(valor, pergunta)
    except Exception:
        return valor


def _motivo_com_os_numeros(valor, contexto, motivo):
    """O motivo da reprovacao, dizendo QUAIS numeros nao estao no documento.

    `motivo: nao ha medida para recalcular` nao diz nada a quem le -- foi a
    mensagem que o usuario recebeu no lugar da dimensao, e nao dava para saber
    se o problema era o numero, a unidade ou o documento. Nomear o numero que
    faltou e o que transforma o aviso em acao.
    """
    try:
        faltam = sorted(_numeros_normalizados(valor) - _numeros_normalizados(contexto))
    except Exception:
        faltam = []
    if not faltam:
        return motivo
    lista = ", ".join(faltam[:5])
    return f"{motivo}; nao achei no documento: {lista}"


def _anotar_celula(celula, nota):
    """Comentário do Excel na célula, assinado "AutoSpec".

    Import preguiçoso e tolerante: sem `openpyxl.comments` (a suíte dubla o
    openpyxl inteiro), a célula só fica sem o comentário -- o valor e o log
    continuam. Nota nunca pode custar a ficha.
    """
    try:
        from openpyxl.comments import Comment
    except ImportError:
        return False
    try:
        celula.comment = Comment(str(nota)[:1500], "AutoSpec")
        return True
    except Exception:
        return False


class _ConferenciaDoLastro:
    """O que a conferência de UMA resposta decidiu, campo a campo.

    Existe para os dois caminhos (`_lastro_legado` e `_conferir_pela_prova`)
    escreverem nas mesmas listas -- e o log do fim contar uma história só.
    """

    def __init__(self):
        self.aprovados = {}
        self.reprovados = []   # (descricao, valor, motivo)
        self.convertidos = []  # (descricao, valor, [explicacoes])
        self.corrigidos = []   # (descricao, valor_da_ia, valor_gravado, motivo)
        self.deducoes = []     # (descricao, valor, justificativa)
        self.de_imagem = []    # (descricao, valor, onde)
        self.notas = {}        # campo -> comentario da celula


def _documento_de_pagina_sem_texto(prova, anexados):
    """O documento ANEXADO que a prova cita, quando a página citada (ou o
    documento inteiro) não tem texto -- a IA leu a imagem, e não há texto
    onde conferir o trecho. `None` em qualquer outro caso.

    Só vale para documento que foi como PDF: no caminho de texto a IA não viu
    a página-imagem, e um trecho dela seria invenção.
    """
    fonte = _normalizar_texto_busca(getattr(prova, "fonte", ""))
    if not fonte:
        return None
    for documento in anexados or ():
        nomes = [_normalizar_texto_busca(documento.nome), _normalizar_texto_busca(documento.url)]
        if not any(n and (n in fonte or fonte in n) for n in nomes):
            continue
        if not documento.texto.strip():
            return documento
        if prova.pagina and prova.pagina in documento.paginas_sem_texto:
            return documento
    return None


def classificar_resultado(fabricante, identificadores, title, snippet, link):
    """`"certo"`, `"duvidoso"` ou `"descartado"` para um resultado de busca.

    **Por que três destinos e não dois** (decisão do usuário, 2026-08-13). O
    filtro binário deixou entrar, numa ficha real do Luan, uma **camiseta da
    Minnie no site do Target** — a URL continha o código do material
    (`.../A-1000326972`) e isso bastava. Também entraram uma resenha de fone
    de ouvido e 220 mil caracteres de um site chinês de componentes.

    A regra agora é a que o usuário definiu:

      certo      cita o FABRICANTE **e** um identificador (modelo/código).
                 Duas evidências independentes; vira contexto direto.
      duvidoso   cita só uma das duas. Pode ser o datasheet certo num
                 distribuidor que não nomeia a marca, ou pode ser a camiseta.
                 Não dá para o código decidir — vai para conferência humana.
      descartado não cita nenhuma. Continua sendo jogado fora sem cerimônia.

    Sem fabricante conhecido (ficha sem marca na planilha), o identificador
    sozinho é o melhor que existe: aí ele vale como `duvidoso`, nunca como
    `certo` — não há segunda evidência para cruzar.
    """
    tem_fab = bool(fabricante) and _resultado_e_relevante(fabricante, title, snippet, link)
    tem_id = bool(identificadores) and _resultado_e_relevante(
        identificadores, title, snippet, link
    )
    if tem_fab and tem_id:
        return "certo"

    # O DOMINIO DO FABRICANTE VALE COMO SEGUNDA EVIDENCIA (2026-09-14).
    #
    # Caso do usuario: `CISCO / IE-3200-8T2S-E`. A pagina certa e
    # `cisco.com/.../cat-ie3200-rugged-series-ds.html` -- um datasheet de
    # FAMILIA, que e como fabricante publica. O titulo fala da serie, nao do
    # SKU; se o trecho do Google tambem nao trouxer o codigo exato, o
    # resultado virava `duvidoso` e NAO virava contexto: ia para a aba de
    # conferencia, e a ficha ficava vazia com a resposta na mao.
    #
    # `cisco.com` falando de produto Cisco nao e a camiseta da Minnie no
    # Target: o dominio do proprio fabricante E a evidencia que faltava.
    # A guarda continua de pe para todo o resto -- loja com o codigo na URL e
    # site de concorrente nao ganham nada com isto.
    if _dominio_do_fabricante(fabricante, link, identificadores,
                              f"{title} {snippet} {link}"):
        return "certo"

    if tem_fab or tem_id:
        return "duvidoso"
    return "descartado"


def _conflita_com_irmao(identificadores, texto):
    """O texto cita um produto da MESMA familia que NAO e o meu?"""
    alvos = [i for i in (identificadores or []) if i]
    if not alvos or not texto:
        return False
    tokens = [t for t in re.split(r"[\s,;()/]+", _normalizar_texto_busca(texto)) if t]
    for ident in alvos:
        meu = _compactar_codigo(_normalizar_texto_busca(ident))
        familia = _compactar_codigo(
            _normalizar_texto_busca(AutoSpecCore._familia_do_identificador(ident)))
        if not meu or len(familia) < 3:
            continue
        for token in tokens:
            candidato = _compactar_codigo(token)
            if len(candidato) <= len(familia) or not candidato.startswith(familia):
                continue
            if candidato in meu or meu in candidato:
                continue      # o proprio codigo, ou a familia dele
            return True
    return False


def _dominio_do_fabricante(fabricante, link, identificadores=(), texto=""):
    """O link mora no site do proprio fabricante, falando do MEU produto?

    Compara o nome do fabricante com o DOMINIO REGISTRAVEL, e nao com a URL
    inteira: `target.com/p/CISCO-switch` tem "cisco" na URL e nao e a Cisco.
    Sufixo de pais entra junto (`cisco.com.br`, `siemens.de`).

    **E recusa quando o resultado aponta para um IRMAO do meu produto.** Isto
    nao e detalhe: a primeira versao desta funcao aceitava
    `wago.com/br/p/750-513` para um item `750-362` -- produto errado, do
    fabricante certo --, e quem pegou foi a suite (`test_autospec_console_luan`,
    caso "OUTRO produto da mesma marca"). Seria criar, no filtro, exatamente o
    defeito de modelo-errado que esta rodada existe para fechar.

    Irmao e um codigo que comeca pela mesma FAMILIA que o meu (`750-*`,
    `IE-3200-*`) e nao e compativel com ele. `IP67` nao comeca pela familia de
    `IE-3200-8T2S-E`, entao nao conflita -- e o que impede a guarda de recusar
    por causa de um grau de protecao citado no titulo.
    """
    if not fabricante or not link:
        return False
    if _conflita_com_irmao(identificadores, texto):
        return False
    try:
        from urllib.parse import urlparse
        host = (urlparse(str(link)).hostname or "").lower()
    except Exception:
        return False
    if not host:
        return False
    partes = [p for p in host.split(".") if p and p != "www"]
    # Fora o TLD (e o sufixo de pais, quando houver): `www.cisco.com.br` ->
    # {"cisco"}; `www.moxa.com` -> {"moxa"}.
    _SUFIXOS = {"com", "net", "org", "co", "br", "de", "us", "uk", "cn", "jp",
                "it", "fr", "es", "eu", "io", "biz", "ind", "gov", "edu"}
    nucleo = {p for p in partes if p not in _SUFIXOS}
    if not nucleo:
        return False
    for nome in (fabricante if isinstance(fabricante, (list, tuple, set)) else [fabricante]):
        chave = _compactar_codigo(_normalizar_texto_busca(nome))
        if len(chave) < 3:
            continue
        if any(chave == _compactar_codigo(n) or chave in _compactar_codigo(n)
               for n in nucleo):
            return True
    return False


def _resultado_e_relevante(termos, title, snippet, link):
    """Filtro anti-intruso (regras de negócio §4.3): o resultado cita o
    fabricante ou o código do material?

    Sem termo nenhum, tudo passa — filtrar por nada barraria tudo, e material
    sem fabricante nem código existe.

    **Por que não é mais `termo in titulo`.** Era, até 2026-08-12, e por isso
    descartava 4 de 4 resultados corretos: o termo era a razão social inteira
    (`hydac tecnologia ltda`), que não aparece em página nenhuma. Agora cada
    termo casa de duas formas, e basta UMA:

      1. como texto normalizado (sem acento, sem caixa);
      2. como código compactado (sem separador), o que faz `CS1320` casar com
         `CS 1320` e com `CS-1320`.

    O casamento compactado exige 3+ caracteres para não transformar um termo
    curto (`SA`, `GE`) em coringa que aprova qualquer página.
    """
    if not termos:
        return True
    # Uma string e iteravel, e iterar "WAGO" da 'W','A','G','O' — termos de 1
    # caractere nunca casam, entao o fabricante "sumia" e TODO resultado caia
    # em `duvidoso`, em silencio. Nenhum chamador de hoje passa string (ver
    # `_tokens_ancora_fabricante`); isto e blindagem, e apareceu justamente
    # quando eu mesmo escrevi a chamada errada num roteiro de verificacao.
    if isinstance(termos, str):
        termos = [termos]

    alvo = _normalizar_texto_busca(f"{title} {snippet} {link}")
    alvo_compacto = _compactar_codigo(alvo)

    for termo in termos:
        limpo = _normalizar_texto_busca(termo).strip()
        compacto = _compactar_codigo(termo)
        if not limpo:
            continue

        # Termo CURTO ou puramente NUMÉRICO exige fronteira de palavra.
        # Casar por substring transformava `123` em coringa (casava dentro
        # de `123456`) e `GE` em coringa maior ainda (casaria em
        # "generico"). Marcas curtas legítimas — `3M`, `GE`, `NSK` — não
        # podem ser descartadas por serem curtas: são o nome da empresa.
        # Fronteira resolve os dois lados.
        if _e_termo_puramente_numerico(termo) or len(compacto) < 4:
            if re.search(rf"(?<![a-z0-9]){re.escape(compacto)}(?![a-z0-9])", alvo):
                return True
            continue

        if limpo in alvo:
            return True
        if compacto in alvo_compacto:
            return True
    return False


def tentar_navegador(url, callbacks=None, ligado=True, _robots=None, _navegador=None):
    """Último recurso: renderiza a página num navegador de verdade.

    **A ordem é a política.** Só chega aqui depois de o download simples
    falhar, e só prossegue se o `robots.txt` do domínio permitir. Um site
    que diz "não" continua recebendo "está bem" — isto não é um
    contornador de bloqueio, é uma forma de ler página que só existe
    depois do JavaScript (ver `core/web/navegador.py`).

    Devolve o caminho de um `.txt` temporário com o texto renderizado, ou
    `None`. `.txt` e não `.html` de propósito: o conteúdo já é texto
    extraído, e passá-lo pelo BeautifulSoup de novo não acrescenta nada.
    """
    cb = callbacks or _callbacks_silenciosos()
    if not ligado:
        return None

    try:
        if _robots is None:
            from sigft.core.web import robots as _robots
        if _navegador is None:
            from sigft.core.web import navegador as _navegador
    except ImportError:
        return None

    if not _robots.pode_acessar(url):
        cb.log(
            f"Nao vou insistir com navegador: o robots.txt do site nao permite (ou nao "
            f"pode ser lido). Respeitar isso e decisao de projeto: {url}",
            nivel="info",
        )
        return None

    if not _navegador.disponivel():
        cb.log(
            "Playwright nao instalado — sem ele nao da para ler pagina que so existe "
            "depois do JavaScript. Rode o Instalar-Playwright.bat se quiser esse "
            "recurso.",
            nivel="info",
        )
        return None

    cb.log(f"Tentando com navegador (ultimo recurso, pode demorar): {url}")
    texto = _navegador.texto_da_pagina(url)
    if not texto:
        cb.log(f"O navegador tambem nao trouxe conteudo util: {url}", nivel="warn")
        return None

    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt", mode="w", encoding="utf-8"
        ) as arquivo:
            arquivo.write(texto)
            cb.log(f"Navegador leu {len(texto)} chars que o download simples nao via.")
            return arquivo.name
    except Exception as e:
        cb.log(f"Nao consegui salvar o texto do navegador ({type(e).__name__}).", nivel="warn")
        return None


# -----------------------------------------------------------------
# 2. CLASSES UTILITÁRIAS (Busca e PDF)
# -----------------------------------------------------------------
class WebSearcher:
    def __init__(self, api_key, cse_id):
        self.api_key = api_key
        self.cse_id = cse_id
        self.search_url = "https://www.googleapis.com/customsearch/v1"
        # Espelha `AutoSpecCore.usar_navegador_ultimo_recurso`; o core
        # sincroniza no `__init__` dele.
        self.usar_navegador_ultimo_recurso = True
        # Resultados que citam UMA das duas evidencias (fabricante OU codigo).
        # Nao viram contexto: vao para a conferencia humana. O `AutoSpecCore`
        # substitui esta lista pela dele a cada ficha.
        self.duvidosos = []
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

    # `required_terms=None` em vez de `[]`: uma lista no default e criada UMA
    # vez, na definicao, e compartilhada por todas as chamadas -- se alguem
    # der um `.append` nela, o item vaza para a chamada seguinte.
    def search_and_download(self, query, required_terms=None, max_results=RESULTADOS_POR_BUSCA,
                            callbacks=None, fabricante=(), identificadores=()):
        # Normaliza o `None` do default para a lista vazia que o corpo espera:
        # `required_terms` e REPASSADO a `_baixar_resultados`, que o itera --
        # deixar o `None` passar trocaria um default inofensivo por TypeError.
        # Com isto, o comportamento e identico ao do default `[]` anterior.
        required_terms = required_terms or []
        cb = callbacks or _callbacks_silenciosos()
        if not self.api_key or not self.cse_id:
            return []
        # `gl`/`hl` removidos em 2026-08-11 (decisão do usuário): eles pediam
        # ao Google resultados BRASILEIROS em PORTUGUÊS. Datasheet de Hydac,
        # KSB, Parker e afins é documento em INGLÊS, em site estrangeiro — o
        # viés derrubava exatamente o que se procura. O navegador do usuário,
        # onde ele acha em 5 segundos, não tem esse viés.
        params = {'key': self.api_key, 'cx': self.cse_id, 'q': query, 'num': max_results}

        em_cache = _cache_busca_ler(query)
        if em_cache is not None:
            cb.log(f"Busca em cache (nao gastou cota da CSE): {query}")
            return self._baixar_resultados(
                em_cache, required_terms=required_terms, callbacks=cb,
                fabricante=fabricante, identificadores=identificadores,
            )

        try:
            # timeout adicionado em 2026-08-11: sem ele, uma chamada pendurada
            # à Google CSE travava o módulo INTEIRO por tempo indefinido --
            # `_download_file` logo abaixo já usava timeout=15, esta não usava
            # nenhum. Mesmo valor, pelo mesmo motivo.
            # Pela cascata de rotas (`core/rede.py`), e nao por
            # `requests.get`: com a VPN da empresa ligada a chamada direta
            # morre por timeout -- a rede so publica um arquivo PAC, que o
            # `requests` nao enxerga, e a busca web simplesmente nao achava
            # nada, sem dizer por que. `status_ok=None` mantem o
            # `raise_for_status()` abaixo no comando, para a cota estourada
            # do CSE continuar aparecendo com a mensagem propria.
            response = rede.get(self.search_url, params=params, timeout=15,
                                status_ok=None)
            response.raise_for_status()
            data = response.json()
            items = data.get('items', [])
        except Exception as e:
            # Até 2026-08-11 era `except Exception: return []` mudo: falha de
            # rede, cota estourada e "não achei nada" ficavam indistinguíveis
            # para quem olhava o console. A cota diária do CSE free tier (100
            # queries) é justamente o caso que mais confunde na prática.
            cb.log(
                f"Busca web falhou ({type(e).__name__}: {e}). Query: {query}",
                nivel="error",
            )
            return []

        # Guarda a resposta CRUA da CSE, nao os arquivos baixados: caminho de
        # temporario nao sobrevive a execucao, mas a lista de URLs sim -- e e
        # ela que custa cota.
        _cache_busca_gravar(query, items)
        return self._baixar_resultados(
            items, required_terms=required_terms, callbacks=cb,
            fabricante=fabricante, identificadores=identificadores,
        )

    def _baixar_resultados(self, items, required_terms=(), callbacks=None,
                           fabricante=(), identificadores=()):
        """Aplica o filtro anti-intruso (regras de negocio 4.3) e baixa o que
        passar. Separado de `search_and_download` para que o caminho de CACHE
        use exatamente a mesma logica do caminho de rede."""
        cb = callbacks or _callbacks_silenciosos()
        results = []
        descartados = 0
        for item in items:
            # A URL vai para o download SEM `.lower()` (2026-08-12): caminho
            # de URL é sensível a caixa em boa parte dos servidores, e
            # baixar a versão minúscula devolvia 404 em arquivo cujo nome
            # tinha maiúscula. A comparação é que normaliza, não o dado.
            link = item.get('link', '') or ''
            title = item.get('title', '') or ''
            snippet = item.get('snippet', '') or ''

            # TRÊS DESTINOS (2026-08-13). Ver `classificar_resultado`: o
            # binário deixou entrar uma camiseta da Minnie no Target porque a
            # URL continha o código do material.
            if fabricante or identificadores:
                destino = classificar_resultado(
                    fabricante, identificadores, title, snippet, link
                )
            else:
                destino = "certo" if _resultado_e_relevante(
                    required_terms, title, snippet, link
                ) else "descartado"

            if destino == "descartado":
                descartados += 1
                continue
            if destino == "duvidoso":
                # NÃO vira contexto agora. Fica guardado para a conferência
                # humana -- é melhor um campo vazio que o engenheiro preenche
                # do que um campo preenchido com a camiseta.
                self.duvidosos.append({"url": link, "title": title, "snippet": snippet})
                continue
            filepath = self._download_file(link, callbacks=cb)
            if filepath:
                results.append({"path": filepath, "url": link, "title": title})

        if self.duvidosos:
            cb.log(
                f"{len(self.duvidosos)} resultado(s) DUVIDOSOS: citam o fabricante ou o "
                f"codigo, mas nao os dois. Nao foram usados -- vao para conferencia:",
                nivel="warn",
            )
            for d in self.duvidosos[-6:]:
                cb.log(f"      · {d['url'][:100]}", nivel="warn")

        if descartados and descartados == len(items):
            # Descartar TUDO nunca é rotina — é sintoma de termo de filtro
            # errado, e foi exatamente o que escondeu a falha de 2026-08-12
            # (a linha antiga dizia "descartou 10 de 10" em nível `info`, no
            # meio de outras, como se fosse normal). Agora grita, e diz por
            # quais termos, que é o que permite diagnosticar em 5 segundos.
            cb.log(
                f"Filtro anti-intruso descartou TODOS os {len(items)} resultado(s) desta "
                f"busca. Nenhum cita: {', '.join(str(t) for t in required_terms)}. "
                f"Se o documento certo estava entre eles, o termo do filtro e que esta "
                f"errado — confira o nome do fabricante e o codigo na planilha.",
                nivel="warn",
            )
        elif descartados:
            cb.log(
                f"Filtro anti-intruso descartou {descartados} de {len(items)} resultado(s) "
                f"(nao citam fabricante nem codigo do material).",
                nivel="info",
            )
        return results

    def _download_file(self, url, callbacks=None, _get=None):
        """Baixa em pedaços, com TETO de tamanho.

        Até 2026-08-12 era `response.content`, que carrega o corpo inteiro na
        memória. Catálogo de fabricante de centenas de MB existe, e numa
        máquina de usuário isso é o app travando sem mensagem nenhuma — o
        `timeout=15` não protege, porque o download avança, só não acaba.

        `_get` é ponto de injeção para teste; em produção fica `None` e usa
        a cascata de rotas de `core/rede.py` (e não o `requests` direto: com
        a VPN ligada a chamada direta morre por timeout).
        """
        cb = callbacks or _callbacks_silenciosos()
        get = _get or (lambda u, **kw: rede.get(u, status_ok=None, **kw))
        response = None
        try:
            response = get(url, headers=self.headers, timeout=15, stream=True)
            if response.status_code == 403:
                # Aconteceu com `hydac.com/shop` no 1o teste real. Vai se
                # repetir: site de fabricante bloqueia robô. Dizer "recusado"
                # sem mais nada parece defeito do app, e não é.
                cb.log(
                    f"Site bloqueou o download automatico (HTTP 403): {url}",
                    nivel="warn",
                )
                return tentar_navegador(
                    url, callbacks=cb, ligado=self.usar_navegador_ultimo_recurso
                )
            if response.status_code != 200:
                cb.log(f"Download recusado (HTTP {response.status_code}): {url}", nivel="warn")
                return None

            suffix = _sufixo_para_url(url, (response.headers or {}).get("Content-Type"))
            total = 0
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                for pedaco in response.iter_content(chunk_size=64 * 1024):
                    if not pedaco:
                        continue
                    total += len(pedaco)
                    if total > TETO_DOWNLOAD_BYTES:
                        cb.log(
                            f"Documento grande demais (passou do teto de "
                            f"{TETO_DOWNLOAD_BYTES // (1024 * 1024)} MB) — download "
                            f"abortado: {url}",
                            nivel="warn",
                        )
                        try:
                            os.remove(tmp_file.name)
                        except Exception:
                            pass
                        return None
                    tmp_file.write(pedaco)
                return tmp_file.name
        except Exception as e:
            cb.log(f"Download falhou ({type(e).__name__}): {url}", nivel="warn")
            return None
        finally:
            try:
                if response is not None:
                    response.close()
            except Exception:
                pass


class PDFProcessor:
    def __init__(self, llama_key):
        self.llama_key = llama_key
        if self.llama_key:
            os.environ["LLAMA_CLOUD_API_KEY"] = self.llama_key

    def extract_text(self, filepath, callbacks=None, nome_exibicao=None):
        """`nome_exibicao` (2026-08-12): o que aparece NO CONSOLE.

        Documento vindo da web mora num `NamedTemporaryFile`, e o log saía
        como `tmp1wgju9r5.pdf: 6 pagina(s), 6 lida(s)` — visto no 1o teste
        real. O usuário não tem como saber a que documento aquilo se refere,
        e é justamente a linha que ele precisa ler para decidir se confia no
        resultado. Quem chama passa a URL; sem isso, cai no nome do arquivo.
        """
        cb = callbacks or _callbacks_silenciosos()
        text_content = ""
        method_used = ""
        nome = nome_exibicao or os.path.basename(str(filepath))
        alvo = str(filepath).lower()
        is_pdf = alvo.endswith('.pdf')
        # P-03: imagem também vai para o LlamaParse, que faz OCR. Antes só o
        # PDF entrava nesse caminho e o TIFF/PNG/JPG caía no BeautifulSoup.
        is_imagem = alvo.endswith(EXTENSOES_IMAGEM)
        ocr_possivel = is_pdf or is_imagem

        # ORDEM: local primeiro, nuvem por último.
        #
        # Até 2026-08-11 o LlamaParse (nuvem) era tentado PRIMEIRO sempre que
        # houvesse chave — o arquivo inteiro subia para a LlamaCloud mesmo
        # quando o PDF tinha camada de texto e podia ser lido aqui, de graça e
        # sem sair da máquina. Invertido pela decisão de privacidade
        # (docs/AUTOSPEC_MELHORIAS.md): a nuvem é último recurso.
        if is_pdf:
            text_content, relatorio = _ler_pdf_local(filepath)
            if relatorio is not None:
                method_used = relatorio.metodo
                cb.log(relatorio.resumo(nome), nivel=relatorio.nivel_log())

        if not text_content and is_pdf:
            # PyMuPDF ausente/falhou: PyPDF2 continua como rede de segurança.
            try:
                with open(filepath, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        t = page.extract_text()
                        if t: text_content += t + "\n"
                if text_content:
                    method_used = "PyPDF2"
            except Exception as e:
                cb.log(f"PyPDF2 falhou em {nome} ({type(e).__name__}: {e}).", nivel="warn")

        if not text_content and ocr_possivel and self.llama_key:
            # Última camada: nuvem. Só quando NADA local funcionou — PDF
            # escaneado ou imagem, que exigem OCR de verdade.
            cb.log(
                f"{nome}: nenhuma camada local leu o documento; recorrendo ao "
                f"LlamaParse (o arquivo SAI da rede).",
                nivel="warn",
            )
            try:
                parser = LlamaParse(result_type="text")
                documents = parser.load_data(filepath)
                text_content = "\n".join([doc.text for doc in documents])
                method_used = "LlamaParse"
            except Exception as e:
                cb.log(
                    f"LlamaParse falhou em {nome} ({type(e).__name__}: {e}).",
                    nivel="warn",
                )

        if not text_content and ocr_possivel and not self.llama_key:
            cb.log(
                f"{nome} precisa de OCR (PDF escaneado ou imagem) e não há OCR local "
                f"instalado nem chave do LlamaParse — documento ignorado.",
                nivel="warn",
            )
            return "", ""

        if not text_content and not ocr_possivel:
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    soup = BeautifulSoup(f, 'html.parser')
                    for script in soup(["script", "style", "nav", "footer", "header"]): script.extract()
                    text_content = soup.get_text(separator=' ', strip=True)
                method_used = "WebScrape(BS4)"
            except Exception as e:
                cb.log(f"Leitura HTML falhou em {nome} ({type(e).__name__}: {e}).", nivel="warn")

        return text_content, method_used

    def ler_paginas(self, filepath, callbacks=None, nome_exibicao=None):
        """`(paginas, metodo)`: como `extract_text`, mas POR PÁGINA (2026-09-24).

        PDF com camada de texto sai com uma entrada por página, inclusive as
        vazias -- é o que marca `[página N]` no contexto e o que diz à
        conferência que aquela página é imagem. O resto (PDF escaneado que o
        OCR leu, HTML) sai como uma entrada só, sem paginação.

        PDF sem texto nenhum e sem OCR volta com as páginas VAZIAS, e não com
        lista vazia: ele ainda pode ir inteiro para um modelo que lê PDF, e
        quem planeja o envio precisa saber quantas páginas ele tem.
        """
        cb = callbacks or _callbacks_silenciosos()
        nome = nome_exibicao or os.path.basename(str(filepath))
        relatorio = None
        if str(filepath).lower().endswith(".pdf"):
            _texto, relatorio = _ler_pdf_local(filepath)
            if relatorio is not None and relatorio.paginas_lidas:
                cb.log(relatorio.resumo(nome), nivel=relatorio.nivel_log())
                return list(relatorio.paginas), relatorio.metodo
        texto, metodo = self.extract_text(filepath, callbacks=cb, nome_exibicao=nome_exibicao)
        if texto:
            return [texto], metodo
        if relatorio is not None:
            return list(relatorio.paginas), relatorio.metodo
        return [], metodo


# -----------------------------------------------------------------
# 3. BACKEND PRINCIPAL
# -----------------------------------------------------------------
class AutoSpecCore:
    def __init__(
        self,
        gemini_key,
        llama_key,
        google_search_key,
        google_cse_id,
        *,
        chaves=None,
        selecao_resolvida=None,
    ):
        """
        `gemini_key` continua sendo a chave do GEMINI (o `frontend.py` passa
        `self.controller.get_key("GEMINI")`), e segue valendo tal qual quando
        o provedor resolvido é o Gemini -- é o mesmo caminho que `get_llm`
        usa para os 5 consumidores desde o CP 3.1.

        `chaves`/`selecao_resolvida` (keyword-only) são pontos de injeção
        para teste, com o MESMO contrato de `core/llm/client.py:get_llm()`:
        `chaves` substitui `config.carregar_chaves()`; `selecao_resolvida`
        substitui a leitura de `sigft.core.llm.selecao.resolver()`. Em uso
        real ficam `None` e tudo é lido do disco.
        """
        self.gemini_key = gemini_key
        self.llama_key = llama_key
        self.google_key = google_search_key
        self.cse_id = google_cse_id

        # Resolve o provedor UMA vez e reaproveita: o guard abaixo e o
        # `get_llm` no fim precisam concordar sobre qual provedor vai rodar.
        # Se cada um resolvesse por conta, uma seleção mudando no disco entre
        # as duas leituras produziria o pior dos mundos -- guard checando a
        # chave de um provedor e cliente construído com outro.
        self._selecao_autospec = self._resolver_selecao(selecao_resolvida)
        self._validar_chave_do_provedor(
            self._selecao_autospec["provider"], gemini_key, chaves
        )

        # [CP 3.2] LangChain removido -- `self._llm` é um `LLMClient` (via
        # `get_llm`), que já resolve o modelo e a `temperature=0.1` (via
        # `_POLITICA_RETRY_POR_TAREFA["autospec"]` em `core/llm/client.py`).
        self._llm = get_llm(
            "autospec",
            self.gemini_key,
            chaves=chaves,
            selecao_resolvida=self._selecao_autospec,
        )
        self.searcher = WebSearcher(self.google_key, self.cse_id)
        self.pdf_parser = PDFProcessor(self.llama_key)
        # P-04: preenchido por `generate_ai_response` a cada chamada (sempre
        # zerado antes). Vale só para a ÚLTIMA ficha processada -- leia logo
        # depois da chamada, como `process_queue` faz.
        self.ultimas_fontes_por_campo = {}
        # Retrieval ligado por padrão. Desligar devolve o comportamento de
        # context stuffing anterior a 2026-08-11 -- existe como escape se
        # alguma ficha mostrar que o recorte perdeu informação.
        self.usar_retrieval = True
        # Cache de resposta ligado por padrão (2026-08-12). Desligar força a
        # IA a responder de novo — existe como escape para o caso de se
        # querer comparar dois modelos na MESMA ficha, em que servir a
        # resposta guardada mascararia justamente o que se quer medir.
        self.usar_cache_resposta = True
        # Lastro documental LIGADO por padrão (2026-08-13, pedido do
        # usuário): campo técnico só é preenchido quando o valor aparece no
        # documento lido. Desligar existe para diagnóstico — ver
        # `valor_tem_lastro` para o que isto garante e o que não garante.
        self.exigir_lastro = True
        # Navegador como ÚLTIMO recurso (2026-08-13): só depois de o download
        # simples falhar, e só se o robots.txt do domínio permitir. Ver
        # `_tentar_navegador` — a ordem é a política.
        self.usar_navegador_ultimo_recurso = True
        # Leitura NATIVA do PDF ligada por padrão (2026-09-24): quando o modelo
        # lê PDF, o próprio arquivo vai para ele. Desligar devolve o caminho de
        # texto (documento inteiro, sem corte) -- existe como escape se algum
        # provedor ou proxy se comportar mal com anexo.
        self.ler_pdf_nativo = True
        # Os documentos da ficha em processamento. Preenchido por
        # `process_local_documents` (primeiro passo da coleta de cada ficha).
        self._documentos = []
        # O buscador tem a mesma chave; sincronizadas aqui para que desligar
        # num lugar desligue nos dois caminhos (403 e pagina vazia).
        self.searcher.usar_navegador_ultimo_recurso = self.usar_navegador_ultimo_recurso
        # O diagnostico do reforco semantico e emitido uma vez so por
        # instancia -- repeti-lo a cada ficha do lote seria ruido.
        self._diagnostico_rag_emitido = False

    @staticmethod
    def _resolver_selecao(selecao_resolvida):
        """Mesma cadeia de `get_llm`: seleção injetada > seleção salva pelo
        usuário no painel "Modelos de IA" > `config.LLM_MODELOS_HOJE`.

        Devolve SEMPRE um dict concreto `{"provider", "model"}` -- nunca
        `None` -- porque o resultado é repassado a `get_llm` como
        `selecao_resolvida`, onde `None` significaria "vá ler o disco de
        novo" e reabriria a janela de divergência que este método fecha.
        """
        if selecao_resolvida is not None:
            return selecao_resolvida

        from sigft.core.llm import selecao  # import local -- mesmo padrão de get_llm

        resolvido = selecao.resolver("autospec", config_path=config.CONFIG_FILE)
        return resolvido if resolvido is not None else config.LLM_MODELOS_HOJE["autospec"]

    @staticmethod
    def _validar_chave_do_provedor(provider_id, gemini_key, chaves):
        """Falha cedo, e com o nome do provedor REALMENTE em uso.

        Antes desta correção o guard era `if not gemini_key: raise
        ValueError("Chave Gemini é obrigatória.")`, escrito quando o módulo
        só sabia falar com o Gemini. Depois do CP 3.2 o AutoSpec roda por
        `LLMClient` e o provedor sai da seleção do usuário -- então quem
        configurava apenas `OPENROUTER_API_KEY` levava um erro pedindo uma
        chave do Gemini que o fluxo nem usaria. Ver
        docs/refatoracao/PENDENCIAS.md (2026-08-11).

        A mensagem é a MESMA para todo provedor, com o provedor e a chave
        esperada interpolados. Nenhum provedor é caso especial no texto --
        decisão de 2026-08-11, olhando para a migração para OpenRouter que
        já está no horizonte: uma mensagem que diz "Gemini" envelhece no dia
        em que o provedor padrão mudar, e ninguém lembra de trocá-la.

        O que continua diferente entre os provedores é só DE ONDE a chave
        vem, não o texto do erro:
          - Gemini: do argumento `gemini_key` (o `frontend.py` passa
            `get_key("GEMINI")`), que `get_llm` usa tal qual;
          - demais: de `config.carregar_chaves()`, pelo nome lógico em
            `config.CHAVE_POR_PROVIDER`.
        """
        nome_chave = config.CHAVE_POR_PROVIDER.get(provider_id)
        if nome_chave is None:
            # Provedor sem chave mapeada: não há o que validar aqui. Deixa
            # seguir para `get_llm`, que levanta o `NotImplementedError` com
            # a lista de provedores suportados -- erro melhor que qualquer
            # um que este guard saberia inventar.
            return

        if provider_id == config.PROVIDER_GEMINI:
            tem_chave = bool(gemini_key)
        else:
            chaves_resolvidas = chaves if chaves is not None else config.carregar_chaves()
            tem_chave = bool(chaves_resolvidas.get(nome_chave))

        if not tem_chave:
            raise ValueError(
                f"O AutoSpec não tem chave de IA configurada para o provedor "
                f"'{provider_id}' (chave esperada: '{nome_chave}'). Configure-a "
                f"na Home, ou escolha no painel 'Modelos de IA' um provedor "
                f"cuja chave você já tenha."
            )

    # P-06: quantas linhas seguidas SEM pergunta encerram a varredura das
    # especificações variáveis. 25 é folgado o suficiente para atravessar um
    # bloco de linhas de layout no meio da lista e curto o suficiente para
    # não varrer planilha formatada até o fim.
    MAX_LINHAS_VAZIAS_SEGUIDAS = 25

    # --- Helpers de Excel e Dados ---
    def extract_pmib_code(self, input_filepath):
        # CP 1.2: delega para a implementação única (core.excel.pmib_codes).
        # Já fazia os.path.basename() antes do regex — comportamento
        # inalterado (era o lado "correto" da divergência com o analyzer,
        # escolhido como canônico). Ver
        # tests/test_autospec_backend_characterization.py.
        return pmib_codes.extract_pmib_code(input_filepath)

    def find_header_columns(self, pmib_sheet):
        # CP 1.2: delega para a implementação única (core.excel.headers).
        # "CÓDIGO PMIB"/"DESCRIÇÃO" são obrigatórias; "CÓDIGO MATERIAL" (ou
        # "MATERIAL") é oportunista, com default de coluna 5 se ausente —
        # mesmo comportamento do original, incluindo o resultado PARCIAL
        # (pmib_col/desc_col podem vir None) quando as 10 primeiras linhas
        # não têm as colunas obrigatórias.
        rows = headers.rows_from_worksheet(pmib_sheet, max_row=10)
        keywords = {
            config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB,
            config.COL_DESCRICAO: config.COL_DESCRICAO,
            "CÓDIGO MATERIAL": ["CÓDIGO MATERIAL", "MATERIAL"],
            # 2026-08-13: oportunista como o "CÓDIGO MATERIAL" — planilha
            # antiga sem esta coluna continua funcionando, só sem o ganho.
            config.COL_MARCA_MODELO: ["MARCA/MODELO", "MARCA / MODELO", "MARCA"],
        }
        col_map, header_row = headers.find_columns(
            rows, keywords, required=[config.COL_CODIGO_PMIB, config.COL_DESCRICAO]
        )
        pmib_col = col_map.get(config.COL_CODIGO_PMIB)
        desc_col = col_map.get(config.COL_DESCRICAO)
        mat_col = col_map.get("CÓDIGO MATERIAL") or 5
        marca_col = col_map.get(config.COL_MARCA_MODELO)
        start_row = header_row + 1 if header_row is not None else None
        return pmib_col, desc_col, mat_col, start_row, marca_col

    @staticmethod
    def _sufixo_pmib_da_celula(valor):
        """Sufixo PMIB canônico da célula (`"0105"`), ou `""` se não houver.

        Existe para que `get_pmib_data` compare sufixo COM sufixo. Até
        2026-08-11 a comparação era `if code_suffix in val_pmib` -- substring
        contra o código inteiro, prefixo de contrato incluído. Como o prefixo
        (`config.PREFIXO_CONTRATO`, hoje `"4500063671"`) contém ele mesmo
        sequências de 4 dígitos, 7 sufixos (`0006`, `0063`, `0636`, `3671`,
        `4500`, `5000`, `6367`) casavam com QUALQUER linha da planilha, e a
        função devolvia a descrição e o código de material da PRIMEIRA linha
        -- de um material completamente diferente. O erro é silencioso e
        contamina o contexto RAG e as queries de busca web, ou seja, a IA
        pesquisa e preenche a ficha com base no material errado. Ver
        docs/refatoracao/PENDENCIAS.md (2026-08-11).

        A normalização passa por `core.excel.pmib_codes` (implementação
        única, CP 1.2), o que de quebra conserta um FALSO NEGATIVO: quando o
        Excel guarda o código como número, `4500063671.1050` vira o float
        `4500063671.105` e a comparação de hoje falha -- `normalize_pmib`
        restaura o zero à direita.
        """
        if valor is None:
            return ""
        texto = str(valor).strip()
        if not texto:
            return ""
        # A célula pode trazer o código no meio de texto livre
        # ("4500063671.0105 - BOMBA"), caso que a substring de antes cobria
        # e que precisa continuar casando.
        completo = pmib_codes.find_pmib_code_in_text(texto)
        norm = pmib_codes.normalize_pmib(completo if completo else valor)
        if not norm:
            return ""
        return norm.split(".")[-1] if "." in norm else norm

    def get_pmib_data(self, pmib_path, code_suffix):
        """`(descricao, codigo_material, marca_modelo)` da linha do material.

        `marca_modelo` (2026-08-13) é a coluna G — `WAGO / 750-362`. Terceiro
        elemento acrescentado à tupla; quem chamava com dois desempacota
        errado, e por isso o único chamador foi ajustado junto.
        """
        try:
            wb = openpyxl.load_workbook(pmib_path, data_only=True)
            ws, pmib_col, desc_col, mat_col, start_row, marca_col = self._aba_com_os_materiais(wb)
            if not pmib_col or not desc_col: return "", "", ""

            for row in ws.iter_rows(min_row=start_row):
                if len(row) < max(pmib_col, desc_col, mat_col): continue
                c_pmib = row[pmib_col-1]

                if self._sufixo_pmib_da_celula(c_pmib.value) == code_suffix:
                    desc_val = str(row[desc_col-1].value).strip() if row[desc_col-1].value else ""
                    mat_val = str(row[mat_col-1].value).strip() if row[mat_col-1].value else ""
                    marca_val = ""
                    if marca_col and len(row) >= marca_col and row[marca_col-1].value:
                        marca_val = str(row[marca_col-1].value).strip()
                    return desc_val, mat_val, marca_val
            return "", "", ""
        except Exception: return "", "", ""

    def _aba_com_os_materiais(self, wb):
        """A aba que TEM o cabeçalho, e não a que estava aberta.

        Achado no `_STATUS_PMIB` real de 2026-08-13: a planilha tem duas abas
        (`Lista de Materiais` e `Checklist`), e o código usava `wb.active` —
        a que estava selecionada quando alguém salvou. Se o colega fechar o
        arquivo com o `Checklist` à frente, `get_pmib_data` devolve vazio para
        TODA ficha, em silêncio, e a busca web perde a marca.

        Mesmo padrão dos outros achados desta camada: **assumir em vez de
        verificar**. Procurar o cabeçalho custa uma varredura de 10 linhas por
        aba e elimina a suposição.
        """
        # `worksheets` pode não existir (workbook falso de teste, versão
        # diferente do openpyxl): a aba ativa sozinha é o comportamento
        # anterior, e continua sendo o mínimo garantido.
        try:
            outras = [aba for aba in wb.worksheets if aba is not wb.active]
        except Exception:
            outras = []
        candidatas = [wb.active] + outras
        for aba in candidatas:
            try:
                pmib_col, desc_col, mat_col, start_row, marca_col = self.find_header_columns(aba)
            except Exception:
                continue
            if pmib_col and desc_col:
                return aba, pmib_col, desc_col, mat_col, start_row, marca_col
        return wb.active, None, None, 5, None, None

    @staticmethod
    def separar_marca_modelo(bruto):
        """`"WAGO / 750-362"` -> `("WAGO", "750-362")`.

        A coluna G junta os dois com barra, e é assim em toda a planilha:
        `NIDEC / MOD SVTN 3K6 W`, `CISCO / IE-3200-8T2S-E`. Sem barra, o texto
        inteiro é tratado como marca — é o caso de quem só anotou o
        fabricante.

        Quebra na PRIMEIRA barra: `WAGO / 750-362/000-001` tem barra dentro do
        modelo, e quebrar em todas partiria o código de peça ao meio.
        """
        texto = str(bruto or "").strip()
        if not texto:
            return "", ""
        if "/" not in texto:
            return texto, ""
        marca, _, modelo = texto.partition("/")
        return marca.strip(), modelo.strip()

    def is_empty(self, val):
        """Campo que o AutoSpec ainda precisa preencher.

        2026-09-08: era `s_val.startswith(...)` com o marcador literal em
        portugues. Numa ficha em INGLES o analyzer escreve `PROVIDE`, e o
        AutoSpec trataria isso como resposta do fornecedor -- pulando
        justamente os campos marcados como faltantes.

        `e_marcador_de_faltante` sai de `ficha_layout`, a MESMA fonte de quem
        escreve. Duas listas de marcadores divergiriam em silencio nos dois
        sentidos. Ela tambem e mais estrita que o `startswith` antigo: exige o
        marcador inteiro ou `MARCADOR (`, para nao engolir uma resposta de
        verdade que comece com as mesmas letras ("Provided by supplier").
        """
        if not val:
            return True
        if not str(val).strip():
            return True
        return ficha_layout.e_marcador_de_faltante(val)

    # P-01: alcance da varredura em busca do rótulo de um checkbox.
    ALCANCE_ROTULO_CHECKBOX = 4

    @staticmethod
    def _texto_util_para_rotulo(ws, linha, coluna):
        """Valor de célula que serve como rótulo, ou `None`.

        Descarta o que não é rótulo: célula vazia, a marca `"x"` solta, e
        qualquer célula que seja a MARCAÇÃO de um grupo de checkbox (sem
        isso, varrer à direita de `J69` alcança o `P69` do grupo vizinho e
        devolve `"x"` como se fosse rótulo — erro observado na ficha real).
        """
        if coluna < 1 or linha < 1:
            return None
        cel = ws.cell(row=linha, column=coluna)
        if cel.coordinate in _CELULAS_DE_MARCACAO:
            return None
        valor = cel.value
        if valor in (None, ""):
            return None
        texto = str(valor).strip()
        if not texto or texto.lower() in ("x", "×"):
            return None
        return texto

    @classmethod
    def _rotulos_checkbox_seguro(cls, ws, celulas):
        """`_rotulos_do_checkbox` que nunca levanta. Rótulo é enriquecimento
        opcional -- uma planilha atípica não pode impedir a ficha de ser
        analisada."""
        try:
            return cls._rotulos_do_checkbox(ws, celulas)
        except Exception:
            return {}

    @classmethod
    def _rotulos_do_checkbox(cls, ws, celulas):
        """Mapa `{célula: rótulo legível}` lido da PRÓPRIA planilha.

        O `CONFIG_MAP` guarda só endereços (`['G25','G27','G29']`), e era
        isso que o prompt oferecia à IA — endereços não dizem nada a um
        modelo de linguagem, então mesmo um acerto era chute entre 3
        opções. O rótulo, porém, está na planilha, ao lado da marcação.

        Duas disposições, ambas confirmadas na ficha real 4500063671.0662
        (ver Anexo B de docs/base-conhecimento/08b-autospec-contexto-negocio.md):

          - **à direita, mesma linha** — 7 dos 9 grupos
            (`G27` → `H27` = "Horizontal");
          - **na linha de cabeçalho acima**, varrendo para a esquerda a
            partir da coluna da marca — os 2 grupos da linha 69
            (`E69` → `D68` = "Classe I - Perigoso").

        Célula sem rótulo encontrável simplesmente não entra no mapa; quem
        chama continua tendo o endereço como alternativa.
        """
        rotulos = {}
        for celula in celulas:
            try:
                col = _indice_da_coluna(
                    "".join(c for c in celula if c.isalpha())
                )
                lin = int("".join(c for c in celula if c.isdigit()))
            except (ValueError, TypeError):
                continue

            achado = None
            # A leitura de rótulo é um BÔNUS: se a worksheet não suportar o
            # acesso por `.cell(row=, column=)` (fakes de teste antigos, um
            # objeto duck-typed mais magro), o campo simplesmente segue sem
            # rótulo e `fill_save` continua aceitando o endereço da célula —
            # exatamente o comportamento anterior a esta melhoria. Um extra
            # não pode derrubar a análise da ficha.
            if not hasattr(ws, "cell"):
                return rotulos
            for d in range(1, cls.ALCANCE_ROTULO_CHECKBOX + 1):
                achado = cls._texto_util_para_rotulo(ws, lin, col + d)
                if achado:
                    break
            if not achado:
                for d in range(0, cls.ALCANCE_ROTULO_CHECKBOX + 1):
                    achado = cls._texto_util_para_rotulo(ws, lin - 1, col - d)
                    if achado:
                        break
            if achado:
                rotulos[celula] = achado
        return rotulos

    # --- Análise da Ficha ---
    def analyze_sheet(self, filepath, status_pmib_path):
        # P-07: DUAS aberturas do mesmo arquivo, de propósito.
        #
        # `wb` (sem `data_only`) é o que sai daqui e é salvo por `fill_save`
        # — precisa manter as FÓRMULAS, que `data_only=True` descartaria na
        # gravação. `ws_valores` (com `data_only=True`) é só para LEITURA:
        # sem ele, `is_empty` enxergaria o texto da fórmula (`"=A1"`) e
        # trataria a célula como preenchida quando o valor calculado é
        # vazio. Ler de um e escrever no outro é o que concilia as duas
        # necessidades.
        wb = openpyxl.load_workbook(filepath)
        # `nome_da_aba_da_ficha` e nao o nome literal: a ficha em INGLES tem a
        # aba "Standard Technical Sheet", e desde 2026-09-03 e o proprio SIG-FT
        # que a nomeia assim. Com o nome fixo, o AutoSpec recusava a propria
        # ficha que o aplicativo gerou, pedindo uma aba em portugues.
        nome_da_aba = nome_da_aba_da_ficha(wb)
        ws_escrita = wb[nome_da_aba]

        try:
            wb_valores = openpyxl.load_workbook(filepath, data_only=True)
            ws = wb_valores[nome_da_aba]
        except Exception:
            # Planilha nunca aberta no Excel não tem valor calculado em
            # cache; nesse caso `data_only=True` devolve `None` em toda
            # célula com fórmula. Cair para a leitura direta é melhor que
            # tratar a ficha inteira como vazia.
            ws = ws_escrita

        pmib_suffix = self.extract_pmib_code(filepath)
        desc_comp, cod_mat, marca_modelo = "", "", ""
        if pmib_suffix and status_pmib_path:
            desc_comp, cod_mat, marca_modelo = self.get_pmib_data(status_pmib_path, pmib_suffix)

        # Contexto Base
        # CP 2.4: CONFIG_MAP["...]["range"] agora guarda o range COMPLETO da
        # célula mesclada (ex. "H6:P6", não mais só "H6") — acesso direto
        # `ws[range]` devolveria uma tupla de tuplas de células (não um
        # `Cell`), quebrando `.value`. `.split(":")[0]` resolve para a
        # primeira célula, igual ao comportamento anterior à unificação.
        txt_brv = ws[CONFIG_MAP["texto_breve_material"]["range"].split(":")[0]].value
        txt_brv = str(txt_brv).strip() if txt_brv else ""
        fab = ws[CONFIG_MAP["fabricante"]["range"].split(":")[0]].value
        fab = str(fab).strip() if fab else ""

        # A COLUNA G DO _STATUS_PMIB COMO REDE (2026-08-13).
        #
        # Causa raiz das fichas WAGO que o Luan processou e voltaram com ZERO
        # características técnicas: a ficha ainda NÃO TINHA fabricante nem
        # texto breve preenchidos -- é o AutoSpec que vai preenchê-los -- e a
        # busca web ia com o código interno da Itaipu (`1000325606`), que não
        # existe na internet. Ia buscar com a única coisa que ninguém publica.
        #
        # A planilha sabia a resposta o tempo todo, na coluna `MARCA/MODELO`:
        # `WAGO / 750-362`. Medido: `WAGO 750-362 datasheet` devolve 10
        # datasheets reais, incluindo o oficial do fabricante.
        #
        # A ficha continua tendo PRECEDÊNCIA: se o engenheiro já escreveu o
        # fabricante nela, é ele que vale. A planilha só entra no vazio.
        marca_status, modelo_status = self.separar_marca_modelo(marca_modelo)
        if not fab and marca_status:
            fab = marca_status
        if not txt_brv:
            # Modelo primeiro: é o que identifica a peça. A descrição entra
            # atrás porque é prosa em português, e a cascata de busca já sabe
            # separar identificador de prosa.
            txt_brv = " ".join(p for p in (modelo_status, desc_comp) if p).strip()

        missing = {}

        # Mapeamento Estático
        for key, cfg in CONFIG_MAP.items():
            if cfg["type"] == "cell":
                ref = cfg["range"].split(":")[0]
                if self.is_empty(ws[ref].value):
                    missing[key] = {"type": "text", "desc": cfg.get("desc", key), "ref": cfg["range"]}
            elif cfg["type"] == "checkbox":
                is_filled = any(self.is_empty(ws[c].value) is False for c in cfg["cells"])
                if not is_filled:
                    missing[key] = {
                        "type": "checkbox",
                        "options": cfg["cells"],
                        "desc": cfg.get("desc", ""),
                        "ref": cfg["cells"],
                        # P-01: rótulos lidos da própria planilha, para o
                        # prompt poder oferecer "Vertical" em vez de "G25".
                        # Best-effort: sem rótulo, cai no endereço de célula.
                        "rotulos": self._rotulos_checkbox_seguro(ws, cfg["cells"]),
                    }

        # Mapeamento Dinâmico (Variáveis)
        #
        # P-06: as regras de negócio dizem "linha 79 até a última linha
        # PREENCHIDA", mas o laço ia até `ws.max_row` -- que no openpyxl conta
        # linha com FORMATAÇÃO, não com conteúdo. Na ficha real
        # 4500063671.0662 as perguntas acabam na linha 103 e `max_row` é 132;
        # num template com estilo aplicado até o fim da planilha isso vira
        # dezenas de milhares de iterações inúteis por ficha.
        #
        # Para parar sem arriscar perder pergunta depois de um buraco, exige
        # uma SEQUÊNCIA de linhas sem pergunta (as fichas numeram as
        # perguntas em ordem — "1 - APLICACAO", "2 - MATERIAL" ... —, então
        # um vão maior que isso significa fim da lista, não lacuna).
        r = VARIAVEIS_SPECS["start_row"]
        vazias_seguidas = 0
        while r <= ws.max_row and vazias_seguidas < self.MAX_LINHAS_VAZIAS_SEGUIDAS:
            p_val = ws.cell(row=r, column=VARIAVEIS_SPECS["pergunta_col_idx"]).value
            r_val = ws.cell(row=r, column=VARIAVEIS_SPECS["resposta_col_idx"]).value
            if p_val:
                vazias_seguidas = 0
                if self.is_empty(r_val):
                    clean_p = str(p_val).strip().replace(":", "")
                    missing[f"var_row_{r}"] = {"type": "text", "desc": clean_p, "ref": ws.cell(row=r, column=VARIAVEIS_SPECS["resposta_col_idx"]).coordinate}
            else:
                vazias_seguidas += 1
            r += 1

        # 7o elemento (2026-08-13): o MODELO da coluna G. Devolvido à parte
        # mesmo já estando no início de `txt_brv`, porque a busca precisa
        # saber que aquilo É um identificador -- `GAAPA` não tem dígito e a
        # heurística de `_identificadores` nunca o reconheceria.
        return wb, missing, txt_brv, fab, desc_comp, cod_mat, modelo_status

    # --- RAG: Busca e Contexto ---
    # Piso do truncamento progressivo (passo 3 da cascata): abaixo disso a
    # query vira genérica demais para valer a chamada -- "CONJUNTO Hydac
    # datasheet specs" traz catálogo de qualquer coisa.
    MIN_TOKENS_BUSCA = 2

    @staticmethod
    def _identificadores(texto):
        """Tokens da descrição que parecem CÓDIGO DE PEÇA ou MODELO.

        Critério: contém pelo menos um dígito e tem 3+ caracteres. Em
        `"CONJUNTO REPARO PARA BOMBA 3527528  PVF100-4 NBR"` isso isola
        `["3527528", "PVF100-4"]` e descarta a prosa.

        É a peça central da correção de 2026-08-11 — ver
        `_montar_queries_busca` para o porquê.
        """
        achados = []
        for bruto in str(texto or "").split():
            token = bruto.strip(".,;:()[]{}\"'").strip()
            if len(token) < 3 or not any(c.isdigit() for c in token):
                continue
            # 2026-08-12: só "tem dígito" não bastava — `1/2` (polegada) e
            # `110` (tensão) entravam como se fossem código de peça, e o
            # `1/2` chegou a virar a PRIMEIRA query da cascata, gastando
            # cota da CSE numa busca que não significa nada.
            #
            # Código de peça é uma de duas coisas:
            #   - mistura letra e dígito (`PVF100-4`, `DN50`, `IP55`); ou
            #   - é numérico e LONGO (`3527528`, `6205`) -- medida solta
            #     raramente passa de 3 dígitos.
            if any(c.isalpha() for c in token):
                achados.append(token)
                continue
            if len(re.sub(r"\D", "", token)) >= 4:
                achados.append(token)
        return achados

    @classmethod
    def _nome_curto_fabricante(cls, fab):
        """`HYDAC TECNOLOGIA LTDA` -> `HYDAC`. O nome pelo qual o produto é
        PUBLICADO, não o nome jurídico pelo qual ele é comprado.

        Medido em 2026-08-12, na mesma busca com e sem a razão social:
        `HYDAC TECNOLOGIA LTDA CS1320 datasheet filetype:pdf` devolveu **1
        resultado relevante de 7** (o primeiro era um datasheet de bateria de
        lítio); trocando por `HYDAC`, **10 de 10** eram datasheets do CS1000.
        A razão social não quebra a busca — degrada o ranking, e o bastante
        para o documento certo cair fora das primeiras posições.

        Devolve o nome ORIGINAL quando a limpeza não sobra nada (empresa cujo
        nome é só termo genérico). Ficar sem fabricante seria pior: é ele que
        ancora o filtro anti-intruso.
        """
        bruto = str(fab or "").strip()
        if not bruto:
            return ""
        # 2026-08-12: o `_STATUS_PMIB` real usa `DIVERSOS`, `N/A`, `SEM
        # MARCA` no lugar do fabricante. Isso não é um fabricante ruim, é a
        # AUSÊNCIA de fabricante — e tratá-lo como nome produz query inútil
        # e, pior, uma âncora de filtro que aprova qualquer coisa.
        if _normalizar_texto_busca(bruto) in _FABRICANTE_GENERICO:
            return ""
        return " ".join(cls._tokens_ancora_fabricante(bruto)) or bruto

    @staticmethod
    def _tokens_ancora_fabricante(fab):
        """Só as palavras que servem de ÂNCORA — lista vazia é resposta
        legítima.

        Separado de `_nome_curto_fabricante` porque as duas decisões são
        diferentes, e confundi-las causou o defeito de `INDUSTRIA E COMERCIO
        LTDA`: para BUSCAR, um nome ruim é melhor que nome nenhum (por isso
        aquele método cai de volta no original); para FILTRAR, ancorar em
        `INDUSTRIA` aprova qualquer página industrial brasileira.
        """
        bruto = str(fab or "").strip()
        if not bruto or _normalizar_texto_busca(bruto) in _FABRICANTE_GENERICO:
            return []
        # Sem corte por tamanho: `3M`, `GE`, `NSK` e `FAG` são nomes de
        # empresa, não ruído. Cortar por 2 caracteres apagava a marca inteira
        # e fazia o método cair de volta na razão social completa. O risco de
        # termo curto virar coringa é tratado onde é o lugar dele — em
        # `_resultado_e_relevante`, exigindo fronteira de palavra.
        return [
            palavra for palavra in bruto.split()
            if _normalizar_texto_busca(palavra).strip(".,") not in _RUIDO_RAZAO_SOCIAL
        ]

    @staticmethod
    def _familia_do_identificador(identificador):
        """`CS1320-A-0-0-0-1/-000` -> `CS1320`. String vazia quando não há
        família distinta a procurar.

        **Por que isto existe.** `CS1320-A-0-0-0-1/-000` é o código de
        CONFIGURAÇÃO: identifica um SKU de loja. O datasheet não é publicado
        por SKU, é publicado pela FAMÍLIA (`ContaminationSensor CS 1000
        Series`). Medido em 2026-08-12: procurar o código completo devolve
        página de e-commerce em HTML; procurar a família com `filetype:pdf`
        devolve 10 datasheets de verdade.

        Corta no primeiro separador (`-` ou `/`). Exige dígito e 3+ caracteres
        na sobra — `ABC-1` não é código de peça, e devolver `ABC` como família
        traria qualquer coisa.
        """
        bruto = str(identificador or "").strip()
        partes = re.split(r"([-/])", bruto)
        if len(partes) < 3:
            return ""  # não havia separador: a família seria o próprio termo

        # PREFIXOS PROGRESSIVOS (2026-09-14). Cortar no PRIMEIRO separador
        # funciona para `CS1320-A-0-0-0-1` (família `CS1320`) e falha para
        # `IE-3200-8T2S-E`: dá `IE`, duas letras, e a função devolvia vazio --
        # então a série IE-3200 nunca era procurada, e é por série que a Cisco
        # publica datasheet. Mesmo caso de `S7-1200` e `NSD-100-A`.
        #
        # Fica o MENOR prefixo válido: `IE-3200` é a família, `IE-3200-8T2S`
        # já é quase o SKU e traria de volta a página de configuração.
        for fim in range(1, len(partes), 2):
            base = "".join(partes[:fim])
            if base == bruto:
                break
            if len(base) >= 3 and any(ch.isdigit() for ch in base):
                return base
        return ""

    @staticmethod
    def _identificador_distintivo(identificador):
        """O identificador aponta para ESTE fabricante, ou é da indústria toda?

        **Achado na varredura de 2026-08-13, com resultado real do Google.**
        `6205` é designação ISO de rolamento: SKF, NSK, FAG e todo mundo
        fabrica "o 6205". Uma página da NSK sobre o 6205 passava pelo filtro
        anti-intruso — o catálogo do concorrente virava contexto, que é
        exatamente o que a regra §4.3 existe para impedir. Mesmo caso de
        `380V` e `5CV` num motor: são ESPECIFICAÇÃO, não identidade.

        Distintivo = mistura letra e dígito **e** tem 5+ caracteres:

            CS1320-A-0-0-0-1/-000  sim    6205      nao (so digito)
            6205-2RS               sim    380V      nao (4 chars)
            4WRPEH                 sim    W22       nao (3 chars)
            PVF100-4               sim    2-214     nao (sem letra)

        O corte em 5 não é arbitrário: abaixo disso o token é curto demais
        para ser um código de catálogo e longo demais para ser só ruído —
        na prática é sempre uma medida (`380V`, `100L`, `5CV`).
        """
        texto = str(identificador or "")
        if len(texto) < 5:
            return False
        return any(c.isalpha() for c in texto) and any(c.isdigit() for c in texto)

    @classmethod
    def _termos_do_filtro(cls, fab, cod_mat, txt_brv, modelo=""):
        """Termos que um resultado precisa citar para não ser descartado.

        Antes de 2026-08-12 era `[fab, cod_mat]` — a razão social inteira e o
        código INTERNO do PMIB. Nenhum dos dois aparece em página de
        fabricante, e o filtro descartava 100% dos resultados corretos.
        Agora entram também os identificadores da descrição e suas famílias,
        que são o que a página realmente cita.
        """
        # ORDEM IMPORTA: o fabricante é a âncora FORTE. Os identificadores
        # entram como reforço, e só os DISTINTIVOS — ver
        # `_identificador_distintivo`.
        termos = []
        termos.extend(cls._tokens_ancora_fabricante(fab))
        # O MODELO DA COLUNA G é identificador POR DEFINIÇÃO -- a planilha o
        # declara como tal. Não passa pela regra do dígito, senão `NIDEC /
        # GAAPA` ficaria sem âncora nenhuma: `GAAPA` é o nome do cartão, e
        # não tem número. Achado com o _STATUS_PMIB real de 2026-08-13.
        modelo_txt = str(modelo or "").strip()
        if len(modelo_txt) > 2:
            termos.append(modelo_txt)
        if cod_mat and len(str(cod_mat)) > 2:
            termos.append(str(cod_mat))
        for ident in cls._identificadores(txt_brv):
            # O identificador E a família entram, cada um se for distintivo.
            # A 1ª versão parava no identificador (`continue`) e perdia a
            # família — e `CS1320` é justamente o que o datasheet de
            # distribuidor cita, não o código de configuração completo.
            if cls._identificador_distintivo(ident):
                termos.append(ident)
            familia = cls._familia_do_identificador(ident)
            if familia and cls._identificador_distintivo(familia):
                termos.append(familia)

        vistos = set()
        unicos = []
        for t in termos:
            chave = _normalizar_texto_busca(t)
            if chave not in vistos:
                vistos.add(chave)
                unicos.append(t)
        return unicos

    @classmethod
    def _tem_ancora_confiavel(cls, fab, cod_mat, txt_brv):
        """Dá para VERIFICAR se um documento é deste material?

        Sem fabricante e sem código, não dá — e `_termos_do_filtro` devolvia
        `[]`, que o filtro lê como "aceita tudo". A proteção §4.3 falhava
        ABERTA justamente na ficha em que menos se pode confiar no
        resultado: qualquer catálogo de qualquer concorrente entraria como
        contexto, e o engenheiro homologaria dado de outra peça.

        Quando isto é `False`, a busca web não acontece. Campo vazio é ruim;
        campo preenchido com dado de outro material é pior — é o princípio
        que a regra §4.3 já dizia, agora aplicado também ao caso degenerado.
        """
        return bool(cls._termos_do_filtro(fab, cod_mat, txt_brv))

    @classmethod
    def _montar_queries_busca(cls, txt_brv, fab, cod_mat, modelo=""):
        """Cascata de busca web, do mais específico ao mais genérico.

        **Reescrita em 2026-08-11, depois de achar a causa raiz de "o script
        não acha o que eu acho no Google em 5 segundos".**

        A cascata anterior mandava a DESCRIÇÃO INTEIRA como query:

            "CONJUNTO REPARO PARA BOMBA 3527528 PVF100-4 NBR Hydac datasheet specs"

        O Google trata cada palavra como termo. `CONJUNTO`, `REPARO`, `PARA`,
        `BOMBA` e `NBR` são prosa em português e **não existem num datasheet
        da Hydac, escrito em inglês** — cada uma empurra o documento certo
        para baixo. A query se auto-sabotava. Pior: o truncamento
        progressivo cortava do FIM, ou seja, descartava primeiro `PVF100-4` e
        `3527528` — justamente os tokens que valem — e preservava a prosa.

        O que uma pessoa digita à mão é `"Hydac PVF100-4 datasheet"`:
        fabricante + identificador, curto. A cascata agora faz isso:

        1. `"{cod_mat}" {fab} datasheet` — código exato entre aspas;
        2. `{fab} {todos os identificadores} datasheet` — a query "humana";
        3. `{fab} {identificador mais longo} datasheet` — o mais distintivo
           sozinho, para o caso de a combinação ser específica demais;
        4+. **fallback**: a prosa truncada por palavra, comportamento
           anterior — cobre material cuja descrição não tem identificador
           nenhum, que é quando a prosa é tudo que existe.

        O fabricante fica SEMPRE na query: é ele que ancora o filtro
        anti-intruso (§4.3).

        Devolve lista sem repetição, preservando a ordem.
        """
        # O texto vem da planilha e costuma trazer espaço duplo e sobra no
        # fim (visto na ficha real 4500063671.0662): `.split()` normaliza.
        tokens = str(txt_brv or "").split()
        # 2026-08-12: nome CURTO, não a razão social — ver
        # `_nome_curto_fabricante` para os números que motivaram a troca.
        fab_txt = cls._nome_curto_fabricante(fab)
        ids = cls._identificadores(txt_brv)
        familias = [f for f in (cls._familia_do_identificador(i) for i in ids) if f]

        queries = []
        # O MODELO DO FABRICANTE VEM PRIMEIRO (2026-08-13). O `cod_mat` da
        # coluna E costuma ser o código INTERNO da Itaipu (`1000325606`, 10
        # dígitos) -- não existe na internet, e gastava a primeira consulta
        # da cascata garantidamente à toa. O modelo da coluna G é o que o
        # fabricante publica: `WAGO 750-362` devolve 10 datasheets.
        modelo_txt = str(modelo or "").strip()
        if modelo_txt:
            queries.append(f"{fab_txt} {modelo_txt} datasheet filetype:pdf".strip())
            queries.append(f"{fab_txt} {modelo_txt} datasheet".strip())
        if cod_mat:
            queries.append(f'"{cod_mat}" {fab_txt} datasheet'.strip())

        if ids:
            todos = " ".join(ids)
            # PDF antes de HTML, com o código EXATO: o datasheet é o que se
            # quer; página de loja é o consolo.
            queries.append(f"{fab_txt} {todos} datasheet filetype:pdf".strip())
            queries.append(f"{fab_txt} {todos} datasheet".strip())

        # A FAMÍLIA vem depois do código exato, nunca antes: a cascata para na
        # primeira query que rende documento, e o datasheet da família certa
        # com a configuração errada é melhor que nada — mas pior que o exato.
        for familia in familias:
            queries.append(f"{fab_txt} {familia} datasheet filetype:pdf".strip())
            queries.append(f"{fab_txt} {familia} datasheet".strip())

        if len(ids) > 1:
            # O identificador mais longo costuma ser o modelo
            # ("PVF100-4"), mais reconhecível que o código interno.
            principal = max(ids, key=len)
            queries.append(f"{fab_txt} {principal} datasheet".strip())

        # Fallback: a cascata de prosa de antes. Só é alcançada se as queries
        # por identificador não renderem — e é a ÚNICA opção quando a
        # descrição não tem identificador nenhum.
        for corte in range(len(tokens), cls.MIN_TOKENS_BUSCA - 1, -1):
            if corte <= 0:
                break
            # 2026-08-13, varredura: cortar palavra a palavra deixava
            # preposição pendurada — `CONJUNTO DE REPARO PARA BOMBA DE KSB
            # datasheet specs`. O `DE` solto não filtra nada, e ainda cola no
            # nome do fabricante como se fosse parte dele. Corta junto.
            restantes = list(tokens[:corte])
            while restantes and _normalizar_texto_busca(restantes[-1]) in _LIGACAO_SOLTA:
                restantes.pop()
            if not restantes:
                continue
            trecho = " ".join(restantes)
            queries.append(f"{trecho} {fab_txt} datasheet specs".strip())

        vistas = set()
        unicas = []
        for q in queries:
            if q not in vistas:
                vistas.add(q)
                unicas.append(q)
        return unicas

    def retrieve_context(self, txt_brv, fab, cod_mat, refs_locais, callbacks=None, modelo=""):
        # Guardado para o lastro recortar o documento por modelo mais adiante
        # (`_filtrar_por_lastro` -> `contexto_do_modelo`). Mesmo idioma de
        # `ultimas_fontes_por_campo`: o valor viaja pela instancia em vez de
        # atravessar tres assinaturas.
        self._modelo_do_item = str(modelo or "").strip()
        cb = callbacks or _callbacks_silenciosos()

        # 1. Processar Locais
        local_txt = self.process_local_documents(refs_locais, callbacks=cb)

        # 2. Busca Web
        web_txt = ""
        sources = []

        if not (self.google_key and self.cse_id):
            cb.log(
                "Busca web desativada (chave do Google Search ou CSE ID ausente) "
                "— o contexto virá só dos documentos locais.",
                nivel="warn",
            )
            return (local_txt + "\n\n" + web_txt), sources

        # 2026-08-12: era `[fab, cod_mat]` — a razão social inteira e o código
        # interno do PMIB, nenhum dos dois presente em página de fabricante.
        # O filtro descartava 100% dos resultados certos. Ver
        # `_termos_do_filtro` e a regressão em
        # `tests/test_autospec_busca_web_falha_real.py`.
        required = self._termos_do_filtro(fab, cod_mat, txt_brv, modelo=modelo)
        # As duas evidencias, separadas: o filtro de tres destinos precisa
        # saber QUAL delas casou (ver `classificar_resultado`).
        ancora_fab = self._tokens_ancora_fabricante(fab)
        ancora_ids = [t for t in required if t not in ancora_fab]
        self.duvidosos = []
        if getattr(self, "searcher", None) is not None:
            self.searcher.duvidosos = self.duvidosos

        if not required:
            # Sem âncora não há como conferir se o documento é deste
            # material — e lista de termos vazia fazia o filtro aceitar
            # TUDO. Ver `_tem_ancora_confiavel`.
            cb.log(
                "Busca web pulada: a ficha não tem fabricante reconhecível nem código "
                "de peça, e sem uma dessas duas âncoras não há como verificar se o "
                "documento encontrado é deste material. Preencha o fabricante na "
                "planilha, ou anexe o manual — o contexto virá só dos documentos locais.",
                nivel="warn",
            )
            return (local_txt + "\n\n" + web_txt), sources

        queries = self._montar_queries_busca(txt_brv, fab, cod_mat, modelo=modelo)

        for i, q in enumerate(queries, start=1):
            files = self.searcher.search_and_download(
                q, required_terms=required, max_results=3, callbacks=cb,
                fabricante=ancora_fab, identificadores=ancora_ids,
            )
            if not files:
                cb.log(f"Busca {i}/{len(queries)} sem resultado util: {q}", nivel="info")
                continue

            aproveitados = 0
            for item in files:
                # `nome_exibicao=URL`: o arquivo é um temporário, e o nome
                # dele no log não diz nada a quem lê. Ver `extract_text`.
                #
                # INTEIRO, e com os bytes guardados (2026-09-24): o temporário
                # é apagado logo abaixo, e o PDF ainda pode ir como arquivo
                # para a IA. Era `t[:50000]`.
                documento = autospec_documentos.ler_documento(
                    item['path'], self.pdf_parser, origem="WEB",
                    nome=item['title'], url=item['url'], callbacks=cb,
                    guardar_bytes=True,
                )
                t, m = documento.texto, documento.metodo
                if t and len(t) > 100:
                    web_txt += documento.texto_marcado() + "\n\n"
                    self._documentos.append(documento)
                    sources.append(item['url'])
                    aproveitados += 1
                    cb.log(f"Documento web aproveitado ({m}, {len(t)} chars): {item['url']}")
                else:
                    # Baixou, mas veio quase vazio — é a assinatura de página
                    # que só existe depois do JavaScript (`hydac.com/shop` é
                    # assim). Pior que o 403, porque o documento "chegou" e
                    # não parece falha. Aqui também vale o último recurso.
                    cb.log(
                        f"Documento web veio quase vazio ({len(t or '')} chars) — pode ser "
                        f"pagina que so monta com JavaScript: {item['url']}",
                        nivel="warn",
                    )
                    renderizado = self._tentar_navegador(item['url'], callbacks=cb)
                    if renderizado:
                        t2, m2 = self.pdf_parser.extract_text(
                            renderizado, callbacks=cb, nome_exibicao=item.get('url')
                        )
                        try:
                            os.remove(renderizado)
                        except Exception:
                            pass
                        if t2 and len(t2) > 100:
                            renderizada = autospec_documentos.Documento(
                                nome=item['title'], origem="WEB", paginas=[t2],
                                url=item['url'], mime="text/html", metodo=m2,
                                paginado=False,
                            )
                            web_txt += renderizada.texto_marcado() + "\n\n"
                            self._documentos.append(renderizada)
                            sources.append(item['url'])
                            aproveitados += 1
                            cb.log(
                                f"Documento web aproveitado via navegador ({len(t2)} chars): "
                                f"{item['url']}"
                            )
                try: os.remove(item['path'])
                except Exception: pass

            # Só encerra a cascata se algum documento REALMENTE virou
            # contexto. Antes bastava a busca devolver arquivos: 3 PDFs
            # ilegíveis paravam a cascata e a ficha seguia sem contexto web,
            # com as queries mais genéricas nunca tentadas.
            if aproveitados:
                cb.log(f"Busca {i}/{len(queries)} rendeu {aproveitados} documento(s): {q}")
                break
            cb.log(
                f"Busca {i}/{len(queries)} achou {len(files)} arquivo(s), nenhum legivel "
                f"— seguindo para a proxima query.",
                nivel="warn",
            )

        if not sources:
            cb.log(
                f"Nenhum documento web aproveitavel apos {len(queries)} tentativa(s). "
                f"O contexto virá só dos documentos locais.",
                nivel="warn",
            )

        return (local_txt + "\n\n" + web_txt), sources

    def process_local_documents(self, paths, callbacks=None):
        """Le os manuais anexados, INTEIROS, e devolve o contexto de texto.

        Deixa em `self._documentos` a lista de `Documento` desta ficha -- e
        dela que `generate_ai_response` decide o que vai como o proprio PDF.
        Zerada aqui porque este e o primeiro passo da coleta de cada ficha
        (`retrieve_context` e `contexto_das_urls` comecam por ele): o PDF de
        uma ficha nao pode ir junto com a seguinte.

        Ate 2026-09-24 cada documento entrava cortado em `t[:60000]` -- o
        manual de 177 mil caracteres da ficha 0094 perdia dois tercos antes de
        qualquer busca.
        """
        cb = callbacks or _callbacks_silenciosos()
        self._documentos = []
        ctx = []
        for p in paths:
            nome = os.path.basename(str(p))
            try:
                documento = autospec_documentos.ler_documento(
                    p, self.pdf_parser, origem="LOCAL", callbacks=cb)
            except Exception as e:
                cb.log(
                    f"Falha ao processar manual local {nome} ({type(e).__name__}: {e}).",
                    nivel="error",
                )
                continue
            self._documentos.append(documento)
            if documento.texto.strip():
                ctx.append(documento.texto_marcado())
                cb.log(f"Manual local lido ({documento.metodo}, "
                       f"{len(documento.texto)} chars): {nome}")
            else:
                # Continua na lista: um modelo que le PDF ainda enxerga as
                # paginas-imagem. So nao ha texto para conferir a prova.
                cb.log(
                    f"Manual local nao rendeu texto: {nome}. So chega a IA se ela "
                    f"ler o PDF diretamente, e o que vier dele nao tem como ser "
                    f"conferido no texto.",
                    nivel="warn",
                )
        return "\n\n".join(ctx)

    # --- Geração IA ---
    def generate_ai_response(self, txt_brv, fab, desc_comp, missing, context, callbacks=None):
        cb = callbacks or _callbacks_silenciosos()
        # FALHA DA IA E FALHA DA FICHA (2026-09-24). O retorno continua `{}`
        # quando a chamada falha -- contrato antigo, com chamadores e testes
        # que dependem dele --, mas o motivo fica registrado aqui para quem
        # conta o lote. Antes, a ficha 0088 levou 6 minutos de `ReadTimeout`,
        # foi salva sem nada e o resumo disse "1 sucesso". Zerado a cada
        # chamada: a falha de uma ficha nao pode contaminar a seguinte.
        self.ultima_falha_ia = None
        if not missing: return {}

        # CP 3.5 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 3): o laço que
        # monta `desc_list` continua aqui (consulta GENERATIVE_FIELDS, constante
        # deste módulo) -- só o TEXTO do preâmbulo do prompt saiu daqui, para
        # `sigft.core.llm.prompts.montar_autospec`, que recebe o resultado já
        # concatenado.
        desc_list = []
        for k, v in missing.items():
            info = f"- ID '{k}': {v['desc']}"
            if k in GENERATIVE_FIELDS: info += " [INFO TÉCNICA PADRÃO]"
            else: info += " [ESTRITO]"
            if v['type'] == 'checkbox':
                # P-01: oferece os RÓTULOS legíveis quando a planilha os
                # tiver. Antes ia `(Opções: ['G25','G27','G29'])` — endereços
                # de célula, que não significam nada para um modelo de
                # linguagem: mesmo um acerto era chute entre 3. Com rótulo, a
                # pergunta vira respondível ("Vertical/Horizontal/
                # Indiferente"), e `fill_save` traduz de volta para a célula.
                rotulos = v.get('rotulos') or {}
                legiveis = [rotulos.get(c) for c in v['options'] if rotulos.get(c)]
                if len(legiveis) == len(v['options']):
                    info += f" (Escolha UMA: {legiveis})"
                else:
                    info += f" (Opções: {v['options']})"
            desc_list.append(info)

        # O QUE VAI PARA A IA (2026-09-24). Três caminhos, decididos aqui:
        #
        #   1. o PRÓPRIO PDF, quando o modelo lê PDF e o arquivo cabe na
        #      chamada (`autospec_documentos.planejar_envio`) -- o modelo vê o
        #      desenho cotado, a tabela, o gráfico;
        #   2. o texto INTEIRO, até `TETO_TEXTO_INTEIRO` (300 mil caracteres);
        #   3. o recorte por relevância (RAG), só acima disso.
        #
        # Até esta data o caminho único era o 3, com teto de 24 mil caracteres,
        # sobre documentos já cortados em 60 mil. Na comparação do usuário com
        # o AMP (que lê o PDF inteiro), isso valeu 43 achados contra 78 -- e a
        # ficha 0094 mandava à IA 13% do manual.
        documentos = list(getattr(self, "_documentos", None) or [])
        nativo = (
            bool(documentos)
            and getattr(self, "ler_pdf_nativo", True)
            and bool(getattr(self._llm, "aceita_pdf", False))
        )
        como_arquivo, como_texto = autospec_documentos.planejar_envio(
            documentos, aceita_pdf=nativo)
        lista_de_campos = "\n".join(desc_list)
        tags = {"modulo": "autospec_backend", "tarefa": "autospec"}
        # A conferência precisa saber o que a IA viu como ARQUIVO: prova de
        # página-imagem só existe lá. Ver `_documento_de_pagina_sem_texto`.
        self._documentos_anexados = list(como_arquivo)

        if como_arquivo:
            anexos = [documento.anexo() for documento in como_arquivo]
            contexto_final = autospec_documentos.descrever_anexos(como_arquivo)
            restante = self._contexto_de_texto(
                "\n\n".join(d.texto_marcado() for d in como_texto if d.texto.strip()),
                missing, cb)
            if restante:
                contexto_final += "\n\nDOCUMENTOS EM TEXTO:\n" + restante
            # A IA viu os documentos INTEIROS: a prova que ela devolver é
            # conferida contra o texto de todos eles.
            contexto_conferencia = context
            cb.log(
                f"A IA vai ler {len(anexos)} documento(s) no proprio PDF "
                f"({', '.join(d.nome for d in como_arquivo)}); o texto extraido "
                f"fica para conferir o que ela responder."
            )
        else:
            anexos = []
            contexto_final = self._contexto_de_texto(context, missing, cb)
            contexto_conferencia = contexto_final

        prompt = prompts.montar_autospec(txt_brv, fab, desc_comp, contexto_final, lista_de_campos)

        # CACHE (2026-08-12): reprocessar o mesmo lote é o normal, não a
        # exceção — e até aqui cada rerun repagava a IA por ficha que já tinha
        # vindo certa. Ver o bloco `RESPOSTA_IA_CACHE` para por que a chave é o
        # prompt inteiro, e não o nome do arquivo.
        selecao = getattr(self, "_selecao_autospec", None) or {}
        chave_cache = _chave_cache_resposta(
            prompt, selecao.get("provider"), selecao.get("model"),
            anexos=[anexo.dados for anexo in anexos],
        )
        if self.usar_cache_resposta:
            guardada = _cache_resposta_ler(chave_cache)
            if guardada is not None:
                # A resposta CRUA volta pela MESMA normalização do caminho
                # vivo. Guardar o resultado já normalizado pareceria mais
                # simples e seria pior: a normalização descarta campo não
                # pedido e preenche `ultimas_fontes_por_campo`, e um acerto de
                # cache tem de produzir os dois efeitos igual à chamada real.
                cb.log(
                    f"Resposta da IA reaproveitada do cache — nenhum token gasto "
                    f"nesta ficha ({txt_brv})."
                )
                valores = self._normalizar_resposta_ia(
                    guardada, campos_pedidos=missing.keys(), callbacks=cb
                )
                return self._conferir_e_filtrar(valores, missing, contexto_conferencia, cb)

        try:
            # [CP 3.2] LangChain removido -- `_limpar_e_parsear_json` do
            # `LLMClient` substitui `JsonOutputParser()` (implementação
            # única, mais robusta: cobre objeto E lista, tolera prosa/fences
            # ao redor do JSON -- ver docs/refatoracao/PENDENCIAS.md).
            # `autospec` GANHA retry (2 retentativas) que antes não tinha.
            #
            # `json_mode=True` (2026-08-12): o prompt PEDE JSON em texto
            # ("Retorne JSON {ID: ...}"), e até aqui era só isso -- o formato
            # dependia da boa vontade do modelo, e o `_limpar_e_parsear_json`
            # existia para raspar as cercas ```json quando ele resolvia
            # embrulhar. Com o flag, os 3 providers pedem JSON NATIVO ao
            # servidor (`response_mime_type` no Gemini, `response_format` no
            # OpenRouter/compat), e a limpeza vira rede de segurança em vez de
            # caminho principal. Importa mais agora que o provedor é
            # trocável: confiabilidade de formato varia muito entre modelos, e
            # falha de parse aqui devolve a ficha VAZIA.
            try:
                resp = self._chamar_ia(prompt, anexos, tags)
            except Exception as e:
                # RECUSA DO PDF CAI PARA O TEXTO (2026-09-24). O provedor pode
                # não aceitar o arquivo (modelo sem leitura de PDF, corpo grande
                # demais para o proxy): a ficha é refeita com o texto extraído,
                # que é o caminho de sempre. TIMEOUT não cai -- o provedor
                # aceitou e demorou, e refazer somaria mais uma espera inteira.
                if not anexos or _e_timeout(e):
                    raise
                cb.log(
                    f"O provedor recusou o(s) PDF(s) anexado(s) ({type(e).__name__}: "
                    f"{e}). Refazendo esta ficha com o texto extraido dos documentos.",
                    nivel="warn",
                )
                anexos = []
                self._documentos_anexados = []
                contexto_final = self._contexto_de_texto(context, missing, cb)
                contexto_conferencia = contexto_final
                prompt = prompts.montar_autospec(
                    txt_brv, fab, desc_comp, contexto_final, lista_de_campos)
                chave_cache = _chave_cache_resposta(
                    prompt, selecao.get("provider"), selecao.get("model"))
                resp = self._chamar_ia(prompt, anexos, tags)
            if self.usar_cache_resposta:
                _cache_resposta_gravar(chave_cache, resp.parsed_json)
            valores = self._normalizar_resposta_ia(
                resp.parsed_json, campos_pedidos=missing.keys(), callbacks=cb
            )
            return self._conferir_e_filtrar(valores, missing, contexto_conferencia, cb)
        except Exception as e:
            # Até 2026-08-11 isto era `print(f"Erro IA: {e}")` -- ia para o
            # stdout, ou seja, a janela preta que ninguém olha. O CP 4.4
            # padronizou os logs pelo console da UI e este ponto ficou de
            # fora: a ficha voltava vazia sem nenhuma explicação visível.
            cb.log(f"Chamada de IA falhou ({type(e).__name__}: {e}).", nivel="error")
            self.ultima_falha_ia = f"{type(e).__name__}: {e}"
            return {}

    def _chamar_ia(self, prompt, anexos, tags):
        """Uma chamada à IA. `anexos` só vai quando há anexo: os dublês de
        teste (e qualquer cliente antigo) não conhecem o parâmetro."""
        extras = {"anexos": anexos} if anexos else {}
        return self._llm.generate(prompt, json_mode=True, tags=tags, **extras)

    def _contexto_de_texto(self, texto, missing, callbacks=None):
        """O texto que vai no prompt: INTEIRO até `TETO_TEXTO_INTEIRO`, e só
        acima disso o recorte por relevância (2026-09-24).

        O recorte (2026-08-11) nasceu para economizar -- o prompt chegava a
        220 mil caracteres para "campos que precisam de umas 20 linhas". A
        conta mudou de lado: num modelo de US$ 0,50 por milhão de tokens, o
        documento inteiro de um datasheet custa frações de centavo, e o
        recorte a 24 mil caracteres custava a ficha. Continua existindo para o
        manual de centenas de páginas, que não cabe.
        """
        cb = callbacks or _callbacks_silenciosos()
        if not texto:
            return texto
        teto = autospec_documentos.TETO_TEXTO_INTEIRO
        if not getattr(self, "usar_retrieval", True) or len(texto) <= teto:
            cb.log(f"Documento(s) enviado(s) INTEIROS a IA como texto ({len(texto)} chars).")
            return texto

        consultas = [v.get("desc") or k for k, v in missing.items()]
        recortado, estatisticas = autospec_rag.montar_contexto_relevante(
            texto, consultas, teto_chars=teto, trechos_por_consulta=5,
            reordenador=self._reordenador_semantico(),
        )
        if not recortado:
            # Nenhum trecho casou com nenhum campo. Melhor mandar o contexto
            # inteiro do que mandar nada: recortar não pode transformar
            # "achei pouco" em "não achei".
            cb.log(
                "Nenhum trecho do contexto casou com os campos pedidos — "
                "enviando o contexto completo.",
                nivel="warn",
            )
            return texto
        cb.log(autospec_rag.resumo_estatisticas(estatisticas))
        # Uma vez por instancia: diz se o recorte teve reforco semantico ou foi
        # so BM25 + glossario. Fica AQUI, e nao na abertura do lote, para nao
        # tentar carregar modelo antes de haver o que recortar.
        if not getattr(self, "_diagnostico_rag_emitido", False):
            self._diagnostico_rag_emitido = True
            try:
                from sigft.services import autospec_embeddings
                cb.log(autospec_embeddings.diagnostico())
            except ImportError:
                pass
        return recortado

    def _tentar_navegador(self, url, callbacks=None, _robots=None, _navegador=None):
        """Delega para `tentar_navegador`, aplicando o interruptor desta
        instancia. Existe como metodo para o ponto de uso ficar legivel e
        para o interruptor morar num lugar so."""
        return tentar_navegador(
            url,
            callbacks=callbacks,
            ligado=getattr(self, "usar_navegador_ultimo_recurso", True),
            _robots=_robots,
            _navegador=_navegador,
        )

    def _conferir_e_filtrar(self, valores, missing, contexto, callbacks=None):
        """As duas conferências pós-resposta, num ponto só.

        Existe para que o caminho VIVO e o caminho do CACHE não possam
        divergir: um acerto de cache não pode virar porta de entrada para
        valor sem lastro.
        """
        self._conferir_fontes_citadas(contexto, callbacks)
        if not getattr(self, "exigir_lastro", True):
            return valores
        aprovados = self._filtrar_por_lastro(valores, missing, contexto, callbacks)

        # As listas do console têm de contar a MESMA história. Sem esta poda,
        # um campo bloqueado pelo lastro aparecia ao mesmo tempo em "Origem
        # dos dados" (porque a normalização já tinha registrado a fonte) e em
        # "a IA não respondeu" — visto no console das 10 fichas do Luan, e é
        # o tipo de contradição que faz o usuário parar de ler o log.
        fontes = getattr(self, "ultimas_fontes_por_campo", None)
        if isinstance(fontes, dict):
            self.ultimas_fontes_por_campo = {
                campo: fonte for campo, fonte in fontes.items() if campo in aprovados
            }
        return aprovados

    def _filtrar_por_lastro(self, valores, missing, contexto, callbacks=None):
        """Deixa passar só o que está no documento. Ver `valor_tem_lastro`.

        Os 12 `GENERATIVE_FIELDS` são isentos: as regras de negócio §3.2
        pedem que eles sejam GERADOS de conhecimento técnico (embalagem,
        transporte, descarte), e não há datasheet de onde saírem. Exigir
        lastro deles esvaziaria metade da ficha por desenho.
        """
        cb = callbacks or _callbacks_silenciosos()
        r = _ConferenciaDoLastro()
        # A PROVA de cada valor (2026-09-24), quando a IA devolveu no formato
        # novo -- ver `autospec_evidencia`. Resposta sem prova segue a regra
        # antiga, inteira. `getattr`: os testes constroem o core com
        # `__new__`, e quem chama `_filtrar_por_lastro` direto nao passou pela
        # normalizacao.
        provas = getattr(self, "ultimas_evidencias_por_campo", None) or {}
        anexados = getattr(self, "_documentos_anexados", None) or []
        contexto_completo = contexto

        # RECORTE POR MODELO (2026-09-14). O lastro passa a conferir contra as
        # linhas que servem a ESTE item, e nao contra o documento inteiro --
        # ver `contexto_do_modelo`. Sem isto, num datasheet de familia a
        # resposta podia pegar a altura de um modelo e a largura de outro, e
        # passar, porque os dois numeros estao no documento.
        #
        # `getattr` porque `_modelo_do_item` e definido em `retrieve_context`,
        # e o repositorio constroi o core com `__new__` nos testes. Sem
        # modelo, `contexto_do_modelo` devolve o contexto inteiro: o
        # comportamento de sempre.
        contexto_do_item = contexto_do_modelo(
            contexto, getattr(self, "_modelo_do_item", ""))
        if contexto_do_item != contexto:
            cb.log(
                "O documento cobre mais de um modelo; conferindo o lastro so "
                "contra as linhas do modelo do item.", nivel="info")
        contexto = contexto_do_item

        for campo, valor in (valores or {}).items():
            descricao = str((missing.get(campo) or {}).get("desc") or campo)
            if not _exige_lastro(campo):
                r.aprovados[campo] = valor
                continue
            prova = provas.get(campo)
            if prova is None:
                status, motivo = self._lastro_legado(campo, valor, descricao, contexto, r)
                if status == "reprovado":
                    r.reprovados.append((descricao, str(valor), motivo))
                continue
            self._conferir_pela_prova(
                campo, valor, descricao, prova, contexto, contexto_completo, anexados, r)

        # Lidos por `fill_save`, que vira cada nota em comentario na celula:
        # o log some, o arquivo fica.
        self.notas_por_campo = r.notas
        aprovados, reprovados = r.aprovados, r.reprovados
        convertidos, corrigidos = r.convertidos, r.corrigidos

        if r.deducoes:
            cb.log(
                f"{len(r.deducoes)} campo(s) preenchidos por DEDUCAO TECNICA: nao estao "
                f"escritos no documento. Cada celula leva um comentario com a "
                f"justificativa. Confira antes de homologar:",
                nivel="warn",
            )
            for descricao, valor, justificativa in r.deducoes:
                cb.log(f"      · {descricao[:60]} = {valor[:40]!r}", nivel="warn")
                cb.log(f"        porque: {justificativa[:160]}", nivel="warn")

        if r.de_imagem:
            cb.log(
                f"{len(r.de_imagem)} campo(s) lidos pela IA em pagina SEM TEXTO (imagem do "
                f"PDF): a prova nao tem como ser conferida no texto. Confira na pagina:",
                nivel="warn",
            )
            for descricao, valor, onde in r.de_imagem:
                cb.log(f"      · {descricao[:60]} = {valor[:40]!r} ({onde})", nivel="warn")

        if convertidos:
            cb.log(
                f"{len(convertidos)} campo(s) vieram de CONVERSAO de unidade, nao copiados "
                f"do documento. A conta foi refeita e confere — confira mesmo assim:",
                nivel="warn",
            )
            for descricao, valor, explicacoes in convertidos:
                cb.log(
                    f"      · {descricao[:60]} = {valor[:30]}  ({'; '.join(explicacoes)[:60]})",
                    nivel="warn",
                )

        if corrigidos:
            cb.log(
                f"{len(corrigidos)} campo(s) tiveram a CONTA REFEITA: a IA leu o numero certo "
                f"do documento e converteu errado. O valor gravado e o recalculado:",
                nivel="warn",
            )
            for descricao, antes, depois, motivo in corrigidos:
                cb.log(
                    f"      · {descricao[:56]}: a IA disse {antes[:22]!r}, gravei "
                    f"{depois[:22]!r} — {motivo[:70]}",
                    nivel="warn",
                )

        if reprovados:
            cb.log(
                f"{len(reprovados)} campo(s) ficaram VAZIOS porque o valor respondido nao "
                f"aparece no documento lido. Preencha a mao, conferindo na fonte:",
                nivel="warn",
            )
            for descricao, valor, motivo in reprovados:
                # O MOTIVO é a parte que o engenheiro usa: dizer "não achei"
                # não ajuda; dizer "o documento tem duas pressões e não dá
                # para saber qual" diz exatamente o que ele precisa decidir.
                # Por isso ele não é truncado junto com o resto.
                cb.log(
                    f"      · {descricao[:60]} -> a IA respondeu {valor[:30]!r}",
                    nivel="warn",
                )
                if motivo:
                    cb.log(f"        motivo: {motivo}", nivel="warn")
        return aprovados

    def _lastro_legado(self, campo, valor, descricao, contexto, r):
        """A regra de 2026-08-13, inteira: o valor tem de estar no documento.

        `(status, motivo)`: `"aprovado"` e `"corrigido"` já ficam registrados
        em `r`; `"reprovado"` volta com o motivo e quem chama decide -- a
        conferência pela prova ainda pode aceitar um TEXTO como dedução.
        """
        # A UNIDADE QUE O ENUNCIADO JA DECLARA (2026-09-15). Ver
        # `autospec_unidades.aplicar_unidade_da_pergunta`: a pergunta diz
        # `in (mm)`, a IA responde `152 x 91 x 135` sem repetir o `mm`, e
        # sem unidade nao ha medida para conferir -- uma conversao CERTA
        # de polegada para milimetro era jogada fora. O valor conferido
        # ganha a unidade; o que vai para a FICHA continua o original.
        valor_conferivel = _com_unidade_do_enunciado(valor, descricao)
        if not valor_tem_lastro(valor_conferivel, contexto):
            # Antes de descartar: a IA pode ter lido o número CERTO e
            # errado só a conta. Aí o dado é bom e a aritmética é do
            # computador — ver `autospec_unidades.corrigir_conversao`.
            certo, motivo = _corrigir_conversao(
                valor_conferivel, contexto, pergunta=descricao)
            if certo is not None:
                r.aprovados[campo] = certo
                r.corrigidos.append((descricao, str(valor), certo, motivo))
                return "corrigido", motivo
            return "reprovado", _motivo_com_os_numeros(valor, contexto, motivo)

        r.aprovados[campo] = valor
        # Número que passou por CONVERSÃO não foi copiado do documento —
        # foi calculado. Aprovar em silêncio seria pior que reprovar: quem
        # homologa precisa saber que aquele valor não está escrito lá, e
        # poder refazer a conta.
        explicacoes = explicar_conversao(valor, contexto)
        if explicacoes:
            r.convertidos.append((descricao, str(valor), explicacoes))
        return "aprovado", ""

    def _conferir_pela_prova(self, campo, valor, descricao, prova, contexto,
                             contexto_completo, anexados, r):
        """Confere um valor pela PROVA que a IA devolveu com ele (2026-09-24).

        A tabela de decisão está no docstring de `autospec_evidencia` e na
        spec `docs/superpowers/specs/2026-09-24-autospec-leitura-integral-design.md`
        §3.4. Em uma frase: número só entra se sair do trecho citado, e o
        trecho tem de existir no documento, na linha do modelo certo; texto
        sem prova entra como DEDUÇÃO marcada.
        """
        texto = str(valor)

        def _deduzir(justificativa):
            r.aprovados[campo] = valor
            r.deducoes.append((descricao, texto, justificativa))
            r.notas[campo] = (
                f"AutoSpec: deducao tecnica, nao esta escrito no documento. {justificativa}"
            ).strip()

        if prova.tipo == "deducao":
            if autospec_evidencia.deducao_permitida(texto):
                _deduzir(prova.justificativa or "(a IA nao justificou)")
            else:
                r.reprovados.append((descricao, texto, (
                    "a IA DEDUZIU um valor com numero. Medida so entra na ficha quando "
                    "esta escrita no documento. Preencha a mao.")))
            return

        if not prova.trecho:
            status, motivo = self._lastro_legado(campo, valor, descricao, contexto, r)
            if status != "reprovado":
                return
            if autospec_evidencia.deducao_permitida(texto):
                _deduzir(prova.justificativa or
                         "a IA citou o documento sem copiar o trecho, e o texto nao aparece nele")
            else:
                r.reprovados.append((descricao, texto, motivo))
            return

        achado = autospec_evidencia.achar_trecho(prova.trecho, contexto)
        if achado is None:
            if contexto != contexto_completo and autospec_evidencia.achar_trecho(
                    prova.trecho, contexto_completo):
                r.reprovados.append((descricao, texto, (
                    f"o trecho citado ({prova.trecho[:60]!r}) e da linha de OUTRO modelo "
                    f"do documento, nao do modelo deste item. Preencha a mao.")))
                return
            imagem = _documento_de_pagina_sem_texto(prova, anexados)
            if imagem is not None:
                onde = imagem.nome + (f", pag. {prova.pagina}" if prova.pagina else "")
                r.aprovados[campo] = valor
                r.de_imagem.append((descricao, texto, onde))
                r.notas[campo] = (
                    f"AutoSpec: lido de pagina sem texto ({onde}); a prova nao pode ser "
                    f"conferida automaticamente. Confira no documento.")
                return
            status, motivo = self._lastro_legado(campo, valor, descricao, contexto, r)
            if status != "reprovado":
                return
            if autospec_evidencia.deducao_permitida(texto):
                _deduzir(f"o trecho citado pela IA nao foi achado no documento "
                         f"({prova.trecho[:60]!r}). {prova.justificativa}".strip())
            else:
                r.reprovados.append((descricao, texto, (
                    f"o trecho citado pela IA ({prova.trecho[:60]!r}) nao esta no "
                    f"documento lido. {motivo[:1].upper()}{motivo[1:]}")))
            return

        valor_conferivel = _com_unidade_do_enunciado(valor, descricao)
        confere, explicacoes = autospec_evidencia.valor_sai_do_trecho(valor_conferivel, achado)
        if confere:
            r.aprovados[campo] = valor
            if explicacoes:
                r.convertidos.append((descricao, texto, explicacoes))
            return
        # A conta refeita DENTRO do trecho citado, e so nele: foi procurar
        # "a unica medida de rotacao" no documento inteiro que transformou o
        # 2860 rpm certo em 3600 (ficha 0094).
        certo, motivo = _corrigir_conversao(valor_conferivel, achado, pergunta=descricao)
        if certo is not None:
            r.aprovados[campo] = certo
            r.corrigidos.append((descricao, texto, certo, motivo))
            return
        r.reprovados.append((descricao, texto, (
            f"o valor nao sai do trecho que a IA citou ({achado[:70]!r}): {motivo}")))

    def _conferir_fontes_citadas(self, contexto, callbacks=None):
        """Denuncia fonte citada que não corresponde a documento lido.

        Não descarta o valor: se ele tem lastro, o dado está no documento e a
        etiqueta é que veio errada. Mas citar um documento que nunca existiu
        é sinal de invenção, e quem vai homologar precisa saber.
        """
        cb = callbacks or _callbacks_silenciosos()
        reais = origens_do_contexto(contexto)
        suspeitas = []
        for campo, fonte in (getattr(self, "ultimas_fontes_por_campo", {}) or {}).items():
            texto = str(fonte or "").strip()
            if not texto:
                continue
            normal = _normalizar_texto_busca(texto)
            if any(marca in normal for marca in _FONTES_SEM_DOCUMENTO):
                continue
            if any(real and (real in texto or texto in real) for real in reais):
                continue
            suspeitas.append((campo, texto))

        if suspeitas:
            cb.log(
                f"{len(suspeitas)} campo(s) citam uma fonte que NAO esta entre os "
                f"documentos lidos — confira estes com atencao redobrada:",
                nivel="warn",
            )
            for campo, fonte in suspeitas[:10]:
                cb.log(f"      · {campo}: {fonte[:80]}", nivel="warn")

    def _reordenador_semantico(self):
        """Gancho do reforço semântico OPCIONAL (`autospec_embeddings.py`).

        Devolve `None` quando a biblioteca de embeddings não está disponível —
        e nesse caso o BM25 decide sozinho, que é o caminho padrão. Ver o
        docstring de `autospec_rag` para por que lexical vem primeiro neste
        domínio.
        """
        try:
            from sigft.services import autospec_embeddings
        except ImportError:
            return None
        return autospec_embeddings.obter_reordenador()

    def _normalizar_resposta_ia(self, parsed, campos_pedidos=None, callbacks=None):
        """Adapta `normalizar_resposta_autospec` ao formato que o resto da
        classe usa: devolve só o `{campo: valor}` e guarda as fontes em
        `self.ultimas_fontes_por_campo`.

        A validação de verdade mora na função de módulo — ver o bloco
        "CONTRATO DA RESPOSTA DA IA" no topo do arquivo. Aqui só fica a
        adaptação de forma, para que `fill_save` continue recebendo o mesmo
        dicionário de sempre.
        """
        self.ultimas_fontes_por_campo = {}
        self.ultimas_evidencias_por_campo = {}
        valores, fontes = normalizar_resposta_autospec(
            parsed, campos_pedidos=campos_pedidos, callbacks=callbacks
        )
        self.ultimas_fontes_por_campo = fontes
        # A PROVA de cada valor (2026-09-24): tipo, pagina, trecho,
        # justificativa. Lida da MESMA resposta crua, a parte, para o contrato
        # de `normalizar_resposta_autospec` (valores, fontes) nao mudar.
        self.ultimas_evidencias_por_campo = autospec_evidencia.extrair_evidencias(
            parsed, campos_pedidos=campos_pedidos)
        return valores

    @staticmethod
    def _resolver_celula_checkbox(resposta, info):
        """Traduz a resposta da IA para a CÉLULA que deve receber o "X".

        Aceita, nesta ordem:
          1. o **endereço** da célula (`"G25"`, `"g25"`) — a única forma que
             funcionava antes de 2026-08-11, preservada;
          2. o **rótulo** lido da planilha (`"Horizontal"`, `"NAO REPARAVEL"`)
             — comparação sem acento e sem caixa;
          3. rótulo **contido** na resposta, ou vice-versa, para o caso de o
             modelo responder por extenso ("Armazenar na posição horizontal")
             — só quando um ÚNICO rótulo casa, para não escolher no chute.

        Devolve `None` quando nada casa; quem chama registra o descarte.
        """
        opcoes = info.get('options') or []
        rotulos = info.get('rotulos') or {}
        if resposta is None:
            return None

        bruto = str(resposta).strip()
        if not bruto:
            return None

        # 1. endereço de célula
        if bruto.upper() in opcoes:
            return bruto.upper()

        chave = _chave_comparacao(bruto)
        if not chave:
            return None

        # 2. rótulo exato (normalizado)
        for celula in opcoes:
            if celula in rotulos and _chave_comparacao(rotulos[celula]) == chave:
                return celula

        # 3. contenção, só se for inequívoca
        candidatos = []
        for celula in opcoes:
            rotulo = rotulos.get(celula)
            if not rotulo:
                continue
            chave_rotulo = _chave_comparacao(rotulo)
            if not chave_rotulo:
                continue
            if chave_rotulo in chave or chave in chave_rotulo:
                candidatos.append(celula)
        return candidatos[0] if len(candidatos) == 1 else None

    def fill_save(self, wb, filepath, ai_data, missing, callbacks=None):
        cb = callbacks or _callbacks_silenciosos()
        # Nome resolvido, e nao literal: a ficha em INGLES tem a aba "Standard
        # Technical Sheet" (2026-09-03).
        ws = wb[nome_da_aba_da_ficha(wb)]
        font = Font(color="0000FF")
        nao_casados = []
        # Deducao e leitura de pagina-imagem (2026-09-24): o que o log disse
        # vira COMENTARIO na celula. Ver `_filtrar_por_lastro`.
        notas = getattr(self, "notas_por_campo", None) or {}

        for k, val in ai_data.items():
            if k in missing and val:
                info = missing[k]
                if info['type'] == 'text':
                    ref = info['ref'].split(':')[0]
                    if k == 'empilhamento':
                        match = re.search(r'\d+', str(val))
                        ws[ref].value = int(match.group()) if match else None
                    else:
                        ws[ref].value = val
                    ws[ref].font = font
                    if notas.get(k):
                        _anotar_celula(ws[ref], notas[k])
                elif info['type'] == 'checkbox':
                    alvo = self._resolver_celula_checkbox(val, info)
                    if alvo:
                        for o in info['options']: ws[o].value = None
                        ws[alvo].value = "X"
                        ws[alvo].font = font
                    else:
                        # P-01: antes o `else` não existia — resposta fora das
                        # opções era descartada em SILÊNCIO e a ficha voltava
                        # com o campo vazio, sem nada indicando que a IA havia
                        # respondido. Falhar calado é pior que falhar.
                        cb.log(
                            f"Checkbox '{k}': resposta {str(val)!r} não casou com "
                            f"nenhuma opção {info['options']} — campo deixado em "
                            f"branco para preenchimento manual.",
                            nivel="warn",
                        )
                        nao_casados.append(k)

        if nao_casados:
            cb.log(
                f"{len(nao_casados)} checkbox(es) ficaram em branco por resposta "
                f"nao reconhecida: {', '.join(nao_casados)}.",
                nivel="warn",
            )

        base, ext = os.path.splitext(filepath)
        new_path = f"{base}_completed{ext}"
        # [CP D] Era `wb.save(new_path)` cru: com a ficha aberta no Excel, o
        # PermissionError subia e o preenchimento inteiro da IA se perdia.
        locking.salvar_perguntando(
            wb, new_path, retry_lock=getattr(callbacks, "retry_lock", None)
        )
        return new_path

    def _registrar_falha_da_ia(self, fname, lote):
        """Conta a ficha como FALHA se a IA nao respondeu -- e diz ao lote por
        que. Devolve `True` quando registrou (quem chama pula o salvamento).

        `getattr`: os testes de lote trocam `generate_ai_response` por fake, e
        o atributo pode nunca ter sido criado -- ausente e "nao falhou".
        """
        falha = getattr(self, "ultima_falha_ia", None)
        if not falha:
            return False
        lote.falha(
            fname,
            f"a IA nao respondeu ({falha}). Nada foi gravado nesta ficha; rode de novo.",
        )
        return True

    # --- MÉTODOS PÚBLICOS DE FLUXO ---
    def processar_conferidos(self, selecao, status_pmib_path):
        """SEGUNDA PASSADA: reprocessa só com os documentos que o engenheiro
        aprovou na conferência.

        `selecao` é `{caminho_da_ficha: [urls aprovadas]}` — o que
        `Conferencia.selecao_por_ficha` devolve.

        **Por que não é um `process_queue` com outra entrada.** A diferença
        está no contexto: aqui os documentos vêm de uma lista fechada de URLs
        já julgadas por uma pessoa, e por isso **não passam pelo filtro
        anti-intruso** — o filtro existe para decidir o que a pessoa acabou
        de decidir. Passar de novo seria desfazer a conferência.

        Mesmo contrato de generator do `process_queue`, para a tela consumir
        do mesmo jeito.
        """
        buffer: list[str] = []
        callbacks = UICallbacks(
            log=lambda msg, nivel="info", contexto=None: buffer.append(str(msg))
        )

        def _flush():
            while buffer:
                yield buffer.pop(0)

        itens = [(f, urls) for f, urls in (selecao or {}).items() if urls]
        if not itens:
            yield "Nenhum documento aprovado — nada a reprocessar."
            return

        with RelatorioLote(
            callbacks,
            titulo="AutoSpec — 2a passada com os documentos conferidos",
            total=len(itens),
            contexto={"status_pmib": status_pmib_path},
        ) as lote:
            yield from _flush()

            for indice, (ficha, urls) in enumerate(itens, start=1):
                fname = os.path.basename(ficha)
                yield f"[{indice}/{len(itens)}] {fname} — {len(urls)} documento(s) aprovado(s)..."
                try:
                    analise = self.analyze_sheet(ficha, status_pmib_path)
                    wb, missing, txt, fab, desc, cod = analise[:6]
                    if not missing:
                        yield " -> Ficha já está completa."
                        lote.pulado(fname, "sem campos faltantes")
                        yield from _flush()
                        continue

                    pendencia = None
                    if getattr(self, "conferencia", None) is not None:
                        pendencia = self.conferencia.pendencia_da_ficha(ficha)
                    refs = pendencia.refs_locais if pendencia else []

                    contexto = self.contexto_das_urls(urls, refs, callbacks=callbacks)
                    yield from _flush()
                    if not contexto.strip():
                        yield " -> Nenhum dos documentos aprovados rendeu texto."
                        lote.pulado(fname, "documentos aprovados sem texto legível")
                        yield from _flush()
                        continue

                    yield f" -> {len(missing)} campos faltantes. Consultando a IA..."
                    ai_resp = self.generate_ai_response(
                        txt, fab, desc, missing, contexto, callbacks=callbacks
                    )
                    yield from _flush()
                    if self._registrar_falha_da_ia(fname, lote):
                        yield from _flush()
                        continue

                    out_path = self.fill_save(wb, ficha, ai_resp, missing, callbacks=callbacks)
                    yield f" -> Salvo: {os.path.basename(out_path)}"
                    lote.sucesso(fname, f"salvo como {os.path.basename(out_path)}")
                    yield from _flush()
                except Exception as e:
                    yield f" -> ERRO: {e}"
                    lote.falha(fname, f"{type(e).__name__}: {e}")
                    yield from _flush()

        yield from _flush()

    def contexto_das_urls(self, urls, refs_locais=(), callbacks=None):
        """Baixa e extrai texto de uma lista FECHADA de URLs.

        Sem filtro anti-intruso e sem busca: a lista já é o resultado de uma
        decisão humana. É a única porta do módulo em que um documento entra
        sem passar pela §4.3, e ela existe justamente porque alguém olhou.
        """
        cb = callbacks or _callbacks_silenciosos()
        partes = []
        local = self.process_local_documents(refs_locais, callbacks=cb)
        if local:
            partes.append(local)

        for url in urls or []:
            caminho = self.searcher._download_file(url, callbacks=cb)
            if not caminho:
                caminho = tentar_navegador(
                    url, callbacks=cb,
                    ligado=getattr(self, "usar_navegador_ultimo_recurso", True),
                )
            if not caminho:
                cb.log(f"Nao consegui ler o documento aprovado: {url}", nivel="warn")
                continue
            # Inteiro e com os bytes guardados, como na 1a passada -- ver
            # `retrieve_context`. Era `texto[:50000]`.
            documento = autospec_documentos.ler_documento(
                caminho, self.pdf_parser, origem="WEB", nome=url, url=url,
                callbacks=cb, guardar_bytes=True,
            )
            texto, metodo = documento.texto, documento.metodo
            try:
                os.remove(caminho)
            except Exception:
                pass
            if texto and len(texto) > 100:
                partes.append(documento.texto_marcado() + "\n")
                self._documentos.append(documento)
                cb.log(f"Documento aprovado lido ({metodo}, {len(texto)} chars): {url}")
            else:
                cb.log(f"Documento aprovado veio quase vazio: {url}", nivel="warn")
        return "\n\n".join(partes)

    def process_queue(self, queue, status_pmib_path):
        """
        Processa a lista de tarefas. Queue Item: {'sheet': path, 'refs':
        [paths]}. Yields: Logs para UI -- continua generator, mesmo
        contrato que `frontend.py` já consome, sem pattern-match em valor
        sentinela.

        CP 4.4 (Fase 4): por dentro usa `RelatorioLote` (início com
        total/contexto, por item, resumo com falhas listadas). Um generator
        não loga direto por `callbacks`, então um `UICallbacks` interno
        acumula cada linha num buffer drenado via `yield from _flush()` logo
        em seguida -- ordem das mensagens antigas preservada, só ganham
        vizinhas novas (as linhas de abertura/fechamento viram as
        equivalentes, mais ricas, de `RelatorioLote`).
        """
        buffer: list[str] = []
        callbacks = UICallbacks(log=lambda msg, nivel="info", contexto=None: buffer.append(str(msg)))

        # CONFERÊNCIA HUMANA (2026-08-13): os documentos DUVIDOSOS de cada
        # ficha ficam guardados aqui e são apresentados no fim do lote. Ver
        # `autospec_conferencia.py` para por que a dúvida é entregue em vez
        # de descartada.
        from sigft.services import autospec_conferencia

        self.conferencia = autospec_conferencia.Conferencia()

        def _flush():
            while buffer:
                yield buffer.pop(0)

        with RelatorioLote(
            callbacks,
            titulo="AutoSpec — preenchendo fichas técnicas",
            total=len(queue),
            contexto={"status_pmib": status_pmib_path},
        ) as lote:
            yield from _flush()


            for i, task in enumerate(queue):
                ficha = task['sheet']
                refs = task['refs']
                fname = os.path.basename(ficha)

                yield f"\n[{i+1}/{len(queue)}] {fname}..."

                try:
                    # 1. Analisa Ficha
                    analise = self.analyze_sheet(ficha, status_pmib_path)
                    # Tolera o contrato de 6 elementos: `process_queue` é
                    # substituído por fake em teste, e um fake antigo devolve
                    # a tupla curta.
                    wb, missing, txt, fab, desc, cod = analise[:6]
                    modelo = analise[6] if len(analise) > 6 else ""

                    if not missing:
                        yield " -> Ficha já está completa."
                        lote.pulado(fname, "ficha já completa (sem campos faltantes)")
                        yield from _flush()
                        continue

                    yield f" -> {len(missing)} campos faltantes. Coletando contexto..."

                    # 2. Contexto
                    full_ctx, sources = self.retrieve_context(
                        txt, fab, cod, refs, callbacks=callbacks, modelo=modelo
                    )
                    yield from _flush()
                    if sources: yield f" -> Fontes Web: {len(sources)}"

                    # 3. IA
                    # Nada de citar provedor aqui: o modelo vem de
                    # `config.LLM_TASKS`/seleção da UI e pode ser OpenRouter
                    # ou o endpoint da empresa. Mensagem que nomeia "Gemini"
                    # envelhece igual à do guard de chave.
                    yield " -> Consultando a IA..."
                    ai_resp = self.generate_ai_response(
                        txt, fab, desc, missing, full_ctx, callbacks=callbacks
                    )
                    yield from _flush()
                    if self._registrar_falha_da_ia(fname, lote):
                        yield from _flush()
                        continue

                    # P-04: rastreabilidade campo->fonte. As regras de negócio
                    # (§3.4) pedem que o engenheiro veja de onde saiu cada
                    # dado antes de homologar; até aqui ele via só a lista de
                    # fontes do lote.
                    fontes = getattr(self, "ultimas_fontes_por_campo", {}) or {}
                    if fontes:
                        yield f" -> Origem dos dados ({len(fontes)} campo(s)):"
                        for campo, fonte in fontes.items():
                            yield f"      · {campo}: {fonte}"

                        # 2026-08-12: no 1o teste real, 29 campos faltavam e
                        # 28 vieram com origem. O 29o (`var_row_88`, "10 -
                        # PRECISAO") simplesmente não aparecia em lugar
                        # nenhum do console -- a IA não respondeu e ninguém
                        # ficou sabendo. Campo que continua vazio é
                        # informação, não silêncio: é o que o engenheiro
                        # precisa ir buscar à mão.
                        sem_resposta = [
                            (k, (v or {}).get("desc") or k)
                            for k, v in missing.items()
                            if not str(ai_resp.get(k) or "").strip()
                        ]
                        if sem_resposta:
                            yield (
                                f" -> {len(sem_resposta)} campo(s) a IA nao respondeu "
                                f"(continuam vazios, preencha a mao):"
                            )
                            for _chave, descricao in sem_resposta:
                                # `cm`, `cm`, `cm`, `kg` foi o que o usuario
                                # leu no log da ficha 4500063671.0070 -- e e
                                # fiel: o `desc` desses campos, no CONFIG_MAP,
                                # e literalmente a unidade. Descricao curta
                                # nao identifica campo nenhum, entao o nome do
                                # campo vai junto.
                                rotulo = str(descricao or "")
                                if len(rotulo.strip()) <= 6:
                                    rotulo = f"{_chave} ({rotulo})" if rotulo.strip() else str(_chave)
                                yield f"      · {rotulo[:90]}"
                    elif ai_resp:
                        yield (
                            "      (a IA não informou a origem dos dados — "
                            "confira manualmente antes de homologar)"
                        )

                    # 4. Salvar
                    out_path = self.fill_save(wb, ficha, ai_resp, missing, callbacks=callbacks)
                    yield f" -> Salvo: {os.path.basename(out_path)}"
                    lote.sucesso(fname, f"salvo como {os.path.basename(out_path)}")
                    # `getattr`: teste substitui `analyze_sheet`/`retrieve_context`
                    # por fake e o atributo pode nunca ter sido criado. A
                    # conferência é um EXTRA -- não pode transformar uma ficha
                    # que deu certo em falha.
                    if getattr(self, "duvidosos", None):
                        self.conferencia.registrar(
                            ficha, material=txt or fname,
                            documentos=self.duvidosos, refs_locais=refs,
                        )
                    yield from _flush()

                except Exception as e:
                    yield f" -> ERRO: {e}"
                    lote.falha(fname, f"{type(e).__name__}: {e}")
                    yield from _flush()

        yield from _flush()
        for linha in autospec_conferencia.resumo_para_console(self.conferencia):
            yield linha
