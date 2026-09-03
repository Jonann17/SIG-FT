r"""Traduz os *PDMs Modificados* para inglês, para a ficha em inglês.

O PROBLEMA
------------------------------------------------------------------------
O SIG-FT tem dois templates de ficha técnica — PT-BR e inglês —, mas as
características técnicas coladas dentro deles vêm sempre da **mesma** pasta de
PDMs Modificados, que está em português. Traduzir isso ficha a ficha, à mão,
era o trabalho que este módulo elimina.

O DESENHO (aprovado pelo usuário em 2026-08-28)
------------------------------------------------------------------------
Traduzir a pasta inteira **uma vez**, gravar numa pasta paralela, e deixar o
montador (`pdm.aplicar_templates_fichas`) escolher a pasta pelo idioma do
template. Os arquivos traduzidos mantêm **nome e geometria** dos originais:

- o nome, porque o montador acha o PDM por SUBSTRING do id (`PDM_1234_001`)
  no nome do arquivo — renomear quebraria o casamento em silêncio;
- a célula, porque o montador lê `cell(linha, 1)` — escrever noutra coluna
  geraria fichas em branco, e ninguém perceberia até abrir uma.

O QUE É TRADUZIDO, E O QUE NÃO É
------------------------------------------------------------------------
Cada pergunta tem a forma `"1 - NOME (Instrução de preenchimento):"`. O
`"1 - "` é numeração da lista e o `":"` é pontuação — mandar os dois para um
tradutor é pedir para ele inventar. Só o miolo viaja.

A FORMA REAL, conferida em 2026-09-03 contra as fichas que o usuário entregou
(e diferente do que este arquivo dizia antes):

    9 - TIPO CONSTRUTIVO (Indicar o tipo construtivo do item. Nota: Material
    especifico de compra com (Número de desenho, referência, nome usual,
    outros)):

Não é um rótulo curto com a unidade entre parênteses — são 100 a 200
caracteres, com uma instrução inteira dentro dos parênteses e outros
parênteses aninhados nela. A instrução VIAJA JUNTO e é traduzida também: é o
que o fornecedor lê para saber o que responder. Deixá-la em português produz
ficha metade em cada idioma, e isso não se denuncia sozinho.

`partes_da_pergunta` foi medida contra as 17 perguntas reais da ficha
4500063671.0071: as 17 remontam byte a byte (`tests/test_traducao_pdm.py`,
seção E).

TRÊS CAMADAS ANTES DO MOTOR
------------------------------------------------------------------------
1. **Glossário** (`_GLOSSARIO_PT_EN.txt`, editável à mão). Frase inteira que
   estiver ali é usada **verbatim, sem chamar o motor** — é o "corrigiu uma
   vez, vale sempre". Os termos soltos também são passados ao motor como
   vocabulário obrigatório.
2. **Cache** (`_CACHE_TRADUCAO.json`, crescido pela máquina). Rerodar a pasta
   não paga tradução de novo.
3. **Dedupe** dentro da rodada: `Fabricante`, `Modelo` e `Peso` aparecem em
   dezenas de PDMs e vão ao motor **uma vez só** — no caminho da
   `deep_translator`, cada item custa 1 segundo de espera.

O motor é **injetado** (`traduzir: list[str] -> list[str]`). Quem monta o de
produção é `motor_padrao()`, no fim do arquivo: IA primeiro, `deep_translator`
como reserva. Injetá-lo é o que permite testar tudo isto sem rede.
"""
import json
import os
import re
import shutil

from sigft.core.excel import locking

NOME_GLOSSARIO = "_GLOSSARIO_PT_EN.txt"
NOME_CACHE = "_CACHE_TRADUCAO.json"

# "1 - ", "12 - ", "007 - " no começo; ":" ou ":." no fim.
_PREFIXO = re.compile(r"^\s*(\d+\s*-\s*)")
_SUFIXO = re.compile(r"([:.\s]+)$")

CABECALHO_GLOSSARIO = """\
# GLOSSARIO PT -> EN  (SIG-FT, traducao dos PDMs Modificados)
#
# COMO USAR
#   Uma correcao por linha, no formato:   portugues = ingles
#
#   Vale de duas formas:
#     · a PERGUNTA INTEIRA (sem o numero e sem os dois pontos) e usada
#       exatamente como voce escreveu, SEM passar pelo tradutor. E o jeito
#       mais forte: serve inclusive para consertar uma traducao ruim;
#     · um TERMO solto vira vocabulario obrigatorio para o tradutor de IA.
#       Atencao: no caminho reserva (deep_translator/Google) o termo solto so
#       conserta o que o tradutor tiver DEIXADO em portugues -- se ele ja
#       traduziu mal, o portugues nao esta mais la para ser trocado. Para
#       consertar uma traducao ruim com certeza, use a PERGUNTA INTEIRA.
#
#   Linhas comecadas por # sao ignoradas. Acrescente sempre que vir uma
#   traducao ruim: o que esta aqui vence o tradutor, hoje e sempre.
#
# ===========================================================================
# TERMOS DA CASA
# Extraidos das fichas reais da Itaipu (4500063671.0071 em PT e
# 4500063671.0052 em EN). NAO sao chute: e assim que a casa ja traduz.
# ===========================================================================
NORMAS TECNICAS APLICAVEIS = APPLICABLE TECHNICAL STANDARDS
CARACTERISTICAS ADICIONAIS = ADDITIONAL CHARACTERISTICS
TIPO CONSTRUTIVO = TYPE OF CONSTRUCTION
CERTIFICADO = CERTIFICATE
Indicar = Indicate
do item = of the item
outros = others
#
# ===========================================================================
# EXEMPLOS (apague ou edite a vontade)
# ===========================================================================
vazão = flow rate
içamento = lifting
estanqueidade = tightness
grau de proteção = protection degree
tensão de isolamento = insulation voltage
"""


# =============================================================================
# Partes da pergunta
# =============================================================================
def partes_da_pergunta(texto):
    """`"1 - Pressão (bar):"` -> `("1 - ", "Pressão (bar)", ":")`.

    Devolve sempre uma tripla que remonta o original ao ser concatenada.
    """
    if texto is None:
        return "", "", ""
    bruto = str(texto)
    if not bruto.strip():
        return "", "", ""

    prefixo = ""
    casamento = _PREFIXO.match(bruto)
    if casamento:
        prefixo = casamento.group(1)
        bruto = bruto[len(prefixo):]

    sufixo = ""
    casamento = _SUFIXO.search(bruto)
    if casamento and casamento.group(1).strip():
        sufixo = casamento.group(1)
        bruto = bruto[: -len(sufixo)]

    return prefixo, bruto, sufixo


# =============================================================================
# Glossário
# =============================================================================
def _ler_texto(caminho):
    """UTF-8 primeiro; cp1252 depois. O arquivo é para ser editado à mão, e o
    Bloco de Notas ainda oferece ANSI no 'Salvar como' — mesma lição do `.txt`
    da conferência do AutoSpec."""
    try:
        with open(caminho, "rb") as arquivo:
            bruto = arquivo.read()
    except Exception:
        return ""
    for codificacao in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return bruto.decode(codificacao)
        except UnicodeDecodeError:
            continue
    return bruto.decode("utf-8", errors="replace")


def carregar_glossario(caminho):
    """`{pt: en}`. Arquivo ausente ou ilegível devolve `{}` — glossário é
    conforto, e conforto não pode impedir a tradução de rodar."""
    termos = {}
    for linha in _ler_texto(caminho).splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        pt, _, en = linha.partition("=")
        pt, en = pt.strip(), en.strip()
        if pt and en:
            termos[pt] = en
    return termos


def criar_glossario_exemplo(pasta):
    """Cria o arquivo com as instruções, se ainda não existir. Devolve o
    caminho. **Nunca sobrescreve** — o que o usuário editou é o que vale."""
    caminho = os.path.join(pasta, NOME_GLOSSARIO)
    if not os.path.exists(caminho):
        os.makedirs(pasta, exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as arquivo:
            arquivo.write(CABECALHO_GLOSSARIO)
    return caminho


# =============================================================================
# Cache
# =============================================================================
class Cache:
    """Traduções já feitas, guardadas ao lado dos arquivos traduzidos.

    Separado do glossário de propósito: o glossário é **curado por gente** e
    vence tudo; o cache é **crescido pela máquina** e só evita repetir
    trabalho. Misturar os dois faria a correção do usuário se perder na
    próxima limpeza de cache.
    """

    def __init__(self, pasta):
        self.pasta = pasta
        self._dados = {}
        caminho = os.path.join(pasta, NOME_CACHE)
        if os.path.exists(caminho):
            try:
                with open(caminho, encoding="utf-8") as arquivo:
                    carregado = json.load(arquivo)
                if isinstance(carregado, dict):
                    self._dados = {str(k): str(v) for k, v in carregado.items()}
            except Exception:
                self._dados = {}  # cache corrompido nao pode derrubar a traducao

    def buscar(self, texto):
        return self._dados.get(texto)

    def guardar(self, texto, traducao):
        self._dados[texto] = traducao

    def salvar(self):
        try:
            os.makedirs(self.pasta, exist_ok=True)
            with open(os.path.join(self.pasta, NOME_CACHE), "w", encoding="utf-8") as arquivo:
                json.dump(self._dados, arquivo, ensure_ascii=False, indent=1, sort_keys=True)
        except Exception:
            pass


# =============================================================================
# Tradução
# =============================================================================
def traduzir_textos(textos, traduzir, glossario=None, cache=None):
    """Traduz uma lista de perguntas inteiras, devolvendo na mesma ordem.

    O motor recebe **só os miolos ainda desconhecidos**, uma vez cada.
    """
    glossario = glossario or {}
    partes = [partes_da_pergunta(t) for t in textos]

    pendentes = []
    resolvidos = {}
    for _, miolo, _ in partes:
        if not miolo or miolo in resolvidos:
            continue
        if miolo in glossario:
            resolvidos[miolo] = glossario[miolo]
        elif cache is not None and cache.buscar(miolo):
            resolvidos[miolo] = cache.buscar(miolo)
        elif miolo not in pendentes:
            pendentes.append(miolo)

    if pendentes:
        traduzidos = traduzir(pendentes)
        for miolo, traducao in zip(pendentes, traduzidos):
            texto = str(traducao or miolo)
            resolvidos[miolo] = texto
            if cache is not None:
                cache.guardar(miolo, texto)

    saida = []
    for (prefixo, miolo, sufixo), original in zip(partes, textos):
        if not miolo:
            saida.append(original)
            continue
        saida.append(f"{prefixo}{resolvidos.get(miolo, miolo)}{sufixo}")
    return saida


def traduzir_pasta(pasta_origem, pasta_destino, traduzir=None, callbacks=None,
                   retry_lock=None):
    """Traduz todos os PDMs Modificados de uma pasta. Generator de linhas de
    log, mesmo contrato dos outros serviços do projeto.

    Cada arquivo é **copiado** e só as células de descrição são reescritas —
    assim toda a formatação (mescla, bordas, altura, fonte 8) sobrevive sem
    precisar ser refeita.
    """
    import openpyxl

    if traduzir is None:
        traduzir = motor_padrao(callbacks=callbacks)

    os.makedirs(pasta_destino, exist_ok=True)
    caminho_glossario = criar_glossario_exemplo(pasta_destino)
    glossario = carregar_glossario(caminho_glossario)
    cache = Cache(pasta_destino)

    arquivos = sorted(
        os.path.join(pasta_origem, nome)
        for nome in os.listdir(pasta_origem)
        if nome.lower().endswith((".xlsx", ".xlsm", ".xls"))
        and not nome.startswith("~$") and not nome.startswith("_")
    ) if os.path.isdir(pasta_origem) else []

    if not arquivos:
        yield f"Nenhum PDM encontrado em: {pasta_origem}"
        return 0

    yield f"Traduzindo {len(arquivos)} PDM(s) para ingles..."
    if glossario:
        yield f"   glossario com {len(glossario)} termo(s): {os.path.basename(caminho_glossario)}"

    traduzidos = 0
    for caminho in arquivos:
        nome = os.path.basename(caminho)
        destino = os.path.join(pasta_destino, nome)
        try:
            shutil.copy2(caminho, destino)
            wb = openpyxl.load_workbook(destino)
            ws = wb.active

            linhas = list(range(1, ws.max_row + 1))
            originais = [ws.cell(row=i, column=1).value for i in linhas]
            novos = traduzir_textos(originais, traduzir, glossario, cache)

            mudou = 0
            for i, antigo, novo in zip(linhas, originais, novos):
                if antigo and novo != antigo:
                    ws.cell(row=i, column=1, value=novo)
                    mudou += 1

            # `salvar_perguntando` e nao `wb.save` direto: e a regra do
            # projeto (tests/test_excel_travado_pergunta.py) -- com a planilha
            # aberta no Excel, o usuario ganha a janela "feche o arquivo" em
            # vez de um erro no meio do lote.
            locking.salvar_perguntando(wb, destino, retry_lock=retry_lock)
            wb.close()
            traduzidos += 1
            yield f"   OK  {nome} ({mudou} pergunta(s))"
        except Exception as e:
            # Um arquivo ruim nao pode derrubar a pasta -- e a pasta e o
            # trabalho de um dia inteiro de traducao.
            if os.path.exists(destino):
                try:
                    os.remove(destino)
                except Exception:
                    pass
            yield f"   FALHA  {nome}: {type(e).__name__}: {e}"

    cache.salvar()
    yield f"Traducao concluida: {traduzidos} de {len(arquivos)} arquivo(s)."
    return traduzidos


# =============================================================================
# O motor de produção
# =============================================================================
def motor_padrao(api_key=None, callbacks=None, glossario=None):
    """IA primeiro, `deep_translator` como reserva.

    Decisão do usuário (2026-08-28): a IA entende termo técnico de
    hidrelétrica muito melhor que o Google Tradutor ("vazão" vira *flow rate*,
    não *outflow*), e traduz em lote — enquanto a `deep_translator` cobra 1
    segundo de espera por item. A reserva existe porque a chave de IA pode
    faltar, e uma pasta inteira não pode ficar sem tradução por causa disso.
    """
    def traduzir(textos):
        if not textos:
            return []
        try:
            return _traduzir_com_ia(textos, api_key=api_key, glossario=glossario)
        except Exception as e:
            if callbacks is not None:
                try:
                    callbacks.log(f"IA indisponivel para traduzir ({e}); "
                                  "usando deep_translator.", nivel="warn")
                except Exception:
                    pass
        return _traduzir_com_deep_translator(textos, glossario=glossario)

    return traduzir


def _traduzir_com_ia(textos, api_key=None, glossario=None):
    from sigft.core.llm.client import get_llm
    from sigft.core.llm import prompts

    llm = get_llm("traduzir_pdm", api_key)
    prompt = prompts.montar_traduzir_pdm(textos, glossario or {})
    resposta = llm.generate(prompt, json_mode=True,
                            tags={"modulo": "traducao_pdm", "tarefa": "traduzir_pdm"})
    dados = resposta.parsed_json or {}
    traducoes = dados.get("traducoes") if isinstance(dados, dict) else None
    if not isinstance(traducoes, list) or len(traducoes) != len(textos):
        raise ValueError(
            f"a IA devolveu {len(traducoes) if isinstance(traducoes, list) else 'nada'} "
            f"traducao(oes) para {len(textos)} texto(s)")
    return [str(t) for t in traducoes]


def _traduzir_com_deep_translator(textos, glossario=None):
    """Mesma cadeia do fluxo do espanhol (`services/translator.py`): Google
    primeiro, MyMemory como reserva, e o texto original se as duas falharem.

    A diferença é o alvo (`en` em vez de `es`) e a ausência do `unidecode`: o
    acento é retirado no fluxo do espanhol por exigência do portal, e aqui só
    empobreceria o texto.
    """
    import time

    from deep_translator import GoogleTranslator, MyMemoryTranslator

    saida = []
    for texto in textos:
        traduzido = texto
        try:
            traduzido = GoogleTranslator(source="pt", target="en").translate(texto)
        except Exception:
            try:
                time.sleep(1)
                traduzido = MyMemoryTranslator(source="pt", target="en").translate(texto)
            except Exception:
                traduzido = texto
        saida.append(_aplicar_termos(str(traduzido or texto), glossario))
    return saida


def _aplicar_termos(texto, glossario):
    """Correção pós-tradução para o caminho da `deep_translator`.

    A IA recebe o glossário no prompt e o aplica com contexto; o Google
    Tradutor não tem onde receber vocabulário, então os termos são corrigidos
    depois, por palavra inteira e sem diferenciar maiúscula de minúscula.
    """
    if not glossario:
        return texto
    for pt, en in glossario.items():
        if len(pt) < 3:
            continue
        texto = re.sub(rf"\b{re.escape(pt)}\b", en, texto, flags=re.IGNORECASE)
    return texto
