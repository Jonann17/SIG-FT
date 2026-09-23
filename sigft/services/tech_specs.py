import os
import re
import json
import time
import pandas as pd
import unicodedata

from sigft import config
from sigft.core.excel import headers, pmib_codes, status_sheet
# CP 2.1 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 2): fábrica única de
# driver Chrome, substitui `webdriver.Chrome()` cru em
# `TechSpecsAutomation.iniciar` abaixo.
# CP 5.3 (Fase 5): `tech_specs` migrado -- o `selenium` sumiu dos imports.
# Quem decide o motor é `config.RPA_ENGINE["tech_specs"]`; a exceção que o laço
# de linhas discrimina passou a ser a NEUTRA de `core/rpa/engine.py` (no motor
# Playwright ela simplesmente nunca ocorre, porque o seletor é reavaliado a
# cada ação em vez de guardar uma referência que envelhece).
from sigft.core.rpa.engine import ElementoObsoleto
from sigft.core.rpa.factory import criar_engine
# CP 2.2 (Fase 2): `safe_click`/`_pesquisar_e_abrir`/`_excluir_linha_segura`/
# o stop-flag de `TechSpecsProcessor`/`TechSpecsAutomation` passam a delegar
# para `PMIBPortal`. `safe_send_keys_elem`/`safe_send_keys_locator`/
# `_preencher_input_com_auditoria`/`_preencher_linha` continuam usando
# `self.driver`/`self.wait` crus, sem nenhuma alteração (não fazem parte do
# escopo deste checkpoint -- ver docs/refatoracao/PENDENCIAS.md).
#
# CP 2.3 (Fase 2): os 10 `time.sleep(<literal>)` do arquivo viram
# constantes nomeadas (nenhum eliminado) -- ver
# docs/refatoracao/PLANO_REFATORACAO.md Fase 2 -> CP 2.3.
# CP 3.1 (Fase 3): `PAUSA_RETRY_IA_CURTA` REMOVIDA deste import -- o retry de
# IA (e o sleep entre tentativas) agora vive dentro de `LLMClient` (ver
# `sigft.core.llm.client.get_llm`); a constante continua existindo em
# `portal.py` (intocada), só este import é que fica sem uso dela.
from sigft.core.rpa.portal import (
    PMIBPortal,
    PAUSA_ANIMACAO,
    PAUSA_AUDITORIA,
    PAUSA_CARGA_TABELA,
    PAUSA_DIGITACAO,
    PAUSA_INJECAO_JS,
    PAUSA_PAGINACAO,
    PAUSA_POS_INJECAO_JS,
    PAUSA_SCROLL,
)
# CP 3.1 (Fase 3): `google.generativeai` deixou de ser importado aqui --
# `TechSpecsProcessor._chamar_gemini_specs` abaixo delega para `LLMClient`/
# `GeminiProvider` (ÚNICO lugar do projeto que importa `genai`).
from sigft.core.llm.client import get_llm
# CP 4.4 (Fase 4): `processar_lista` (o lote de RPA) emite o padrão único de
# log. Forma DIRETA, somando ao que já existia -- este módulo é um dos que o
# diagnóstico do plano cita como "loga bem", então as mensagens por etapa
# foram todas PRESERVADAS; o ganho aqui é início, resumo e o aviso de
# pendências virando causa→consequência formal.
from sigft.core.callbacks import from_legacy
from sigft.core.relatorio_lote import RelatorioLote
# CP 3.5 (Fase 3): o TEXTO do `system_instruction`/`prompt_user` de
# `_chamar_gemini_specs` abaixo mora em `sigft.core.llm.prompts`
# (`SYSTEM_TECH_SPECS`/`montar_tech_specs_user`).
from sigft.core.llm import prompts


# =============================================================================
# CONTRATO DA RESPOSTA DA IA — validado, não confiado
# =============================================================================
# Acrescentado em 2026-08-11, depois do 1º lote rodado num modelo que não é o
# Gemini. O prompt pede uma LISTA de objetos no nível raiz; o MiniMax M3
# devolveu `{"items": [...]}` e trocou o nome de quase todo campo
# (`RESPOSTA_NORMALIZADA_PT` no lugar de `RESPOSTA_PT_FINAL`, `SIMBOLO_UNIDADE`
# no lugar de `SIMBOLO`, `TIPO_DADO` no lugar de `TIPO`).
#
# O estrago tinha DOIS níveis, e o segundo é o perigoso:
#
#   1. O envelope `{"items": ...}` fazia `for d in dados` iterar as CHAVES do
#      dicionário, então `d` virava a string "items" e o acesso
#      `d['CARACTERISTICA_CHAVE']` estourava
#      `TypeError: string indices must be integers` -- 13 segundos depois de o
#      robô já estar no portal, com uma mensagem que não diz nada sobre IA.
#
#   2. Se só o envelope fosse corrigido, a lista passaria e o RPA leria os
#      campos com `dado.get("RESPOSTA_PT_FINAL", "")` -- que, com o nome
#      trocado, devolve STRING VAZIA. O robô preencheria a ficha inteira com
#      valores em branco e reportaria SUCESSO. Falhar alto é melhor.
#
# Por isso aqui NÃO se traduz nome de campo: renomear
# `RESPOSTA_NORMALIZADA_PT` seria adivinhar o sinônimo de UM modelo, e o
# próximo inventa outro. O envelope, sim, é desembrulhado -- é ambiguidade de
# formatação, não de significado.
# O conjunto exigido é o que o RPA lê com defaults PERIGOSOS -- nada além
# disso. `TIPO` ausente vira `""`, que não casa com nenhum ramo de
# `_preencher_linha` e faz a linha ser pulada em silêncio; `RESPOSTA_PT_FINAL`
# ausente vira `""` e é ESCRITO no portal, apagando o que estava lá.
#
# `SIMBOLO`, `RESPOSTA_ES_FINAL` e `SUBTIPO_INTERVALO` ficam de FORA de
# propósito: o código já trata a ausência dos três como caso legítimo
# (`simb = dado.get("SIMBOLO"); if simb:` -- característica sem unidade é
# normal). Exigi-los na 1ª versão desta validação reprovou 4 testes de
# `processar_lista` que estavam certos.
CHAVES_ITEM_SEMPRE = ("CARACTERISTICA_CHAVE", "ACAO")
CHAVES_ITEM_PREENCHER = ("TIPO", "RESPOSTA_PT_FINAL")


def indexar_por_caracteristica(dados, normalizar):
    """Índice `chave normalizada -> item` para o RPA, com PREENCHER vencendo
    REMOVER.

    Era um dict comprehension (`{normalizar(d['CARACTERISTICA_CHAVE']): d for
    d in dados}`), onde o ÚLTIMO item de cada chave vencia. Parecia inofensivo
    porque o prompt manda a IA não repetir chave -- mas o Master (SAM) traz a
    mesma característica UMA VEZ POR REVISÃO do PDM, então o contexto enviado
    à IA tem a característica repetida, e a IA responde na mesma ordem: a
    linha da revisão atual PREENCHIDA e as das revisões antigas como REMOVER.
    Com "o último vence", a REMOVER da revisão velha apagava a resposta boa.

    Medido no 1º lote real (ficha 4500063671.1471, PDM.4320.002 com 3
    revisões no Master): a IA devolveu 37 PREENCHER -- exatamente os 37
    campos que o fornecedor preencheu na ficha --, e só 21 chegaram ao
    portal. Os outros 16 viraram exclusão de linha. Não era qualidade do
    modelo: era este dicionário.

    PREENCHER vence porque a assimetria de dano é enorme: apagar uma linha
    para a qual existe resposta é perda de informação que ninguém percebe;
    manter uma linha que poderia ser apagada é, no pior caso, uma linha a
    mais para revisar. Entre dois itens do mesmo tipo, vence o PRIMEIRO --
    no Master a revisão vigente vem antes das antigas.
    """
    indice = {}
    for item in dados:
        chave = normalizar(item['CARACTERISTICA_CHAVE'])
        atual = indice.get(chave)
        if atual is None:
            indice[chave] = item
            continue
        if str(atual.get("ACAO", "")).strip().upper() == "PREENCHER":
            continue  # já temos o bom; nada supera um PREENCHER
        if str(item.get("ACAO", "")).strip().upper() == "PREENCHER":
            indice[chave] = item
    return indice


# ---------------------------------------------------------------------------
# Transbordo de casas decimais -> CARACTERISTICAS ADICIONAIS (2026-08-18)
# ---------------------------------------------------------------------------
# Relato do usuário: *"um erro que costuma dar é quando eu tenho que colocar
# 0,002 e o campo aceita apenas 2 unidades após a vírgula"*.
#
# Medido no Master real: das 6.085 linhas `NUM`, **6.060 aceitam exatamente 2
# casas**. Ou seja, não é caso de canto -- é a regra do portal, e todo valor
# mais preciso que centésimo bate nela.
#
# A saída, proposta pelo usuário: mover para o campo de texto livre
# ("CARACTERISTICAS ADICIONAIS"), escrevendo nome e valor. Várias, uma por
# linha. Isso preserva a informação em vez de arredondá-la -- e arredondar
# 0,002 para 0,00 seria pior do que não preencher, porque vira um número
# plausível e errado.
#
# ⚠️ Feito em CÓDIGO e não só no prompt, de propósito. É uma regra aritmética
# com resposta única; depender do modelo lembrar dela a cada ficha é escolher
# a fonte menos confiável para algo que não tem ambiguidade nenhuma.
def juntar_para_char(dado):
    """Junta valor + unidade (+ subtipo, se intervalo) num texto único.

    É o recuo pedido pelo usuário em 2026-08-18: *"quando der erro de colocar
    em uma int, uma lista ou um intervalo, devemos tentar juntar as duas
    informações e colocar em CHAR e selecionar a unidade como adimensional"*.

    Por que isso é seguro: 32.578 das 32.655 linhas do Master aceitam `AD`
    entre os símbolos (99,8%) -- medido. Então "cair para CHAR + AD" quase
    sempre tem para onde ir.

    E por que é MELHOR do que falhar: o tipo do portal e o tipo do Master
    divergem quando a ficha foi gerada numa revisão e o portal já está noutra
    (8 características do PDM.4820.015 trocaram de tipo entre r0 e r1, todas
    CHAR->NUM). Nesses casos o dado existe e é correto; só não cabe na caixa
    que o JSON esperava. Perder a informação por causa da caixa seria o pior
    dos dois mundos.
    """
    valor = str(dado.get("RESPOSTA_PT_FINAL", "") or "").strip()
    simbolo = str(dado.get("SIMBOLO", "") or "").strip()
    if simbolo and simbolo.upper() != "AD":
        valor = f"{valor} {simbolo}".strip()
    subtipo = str(dado.get("SUBTIPO_INTERVALO", "") or "").strip()
    if subtipo and subtipo.upper() not in ("NONE", "NULL"):
        valor = f"{valor} ({subtipo})".strip()
    return valor


_RE_CHAVE_DA_CARACTERISTICA = re.compile(r"^\s*\d+\s*-\s*(.*)")


def chave_da_caracteristica(descricao, normalizar):
    """`"1650 - COMPONENTES"` -> `"COMPONENTES"`, normalizado.

    ⚠️ UMA DEFINICAO SO, e isso nao e zelo. Duas rotinas usam esta chave: o
    laco que PREENCHE (para achar o dado no JSON) e a limpeza que APAGA as
    linhas em branco fora do JSON. Se as duas calcularem a chave de jeitos
    diferentes, a limpeza apaga exatamente o que acabou de ser preenchido.

    O formato real do portal tem espacos em volta do hifen (`1650 -
    COMPONENTES`, medido no recorte de 2026-09-23); sem o codigo na frente,
    devolve o texto inteiro normalizado.
    """
    texto = str(descricao or "")
    achado = _RE_CHAVE_DA_CARACTERISTICA.search(texto)
    return normalizar(achado.group(1) if achado else texto)


CARACTERISTICA_TEXTO_LIVRE = "CARACTERISTICAS ADICIONAIS"
TIPOS_NUMERICOS = ("NUM", "INT")


def casas_decimais_de(valor):
    """Quantas casas decimais o texto tem. Aceita vírgula ou ponto."""
    texto = str(valor if valor is not None else "").strip()
    for separador in (",", "."):
        if separador in texto:
            depois = texto.rsplit(separador, 1)[1]
            if depois.isdigit():
                return len(depois)
    return 0


def cabe_nas_casas(valor, casas_permitidas):
    """O valor cabe no campo? Limite ausente/ilegível ⇒ assume que cabe.

    Assumir que cabe é o lado seguro: um limite que não conseguimos ler não
    pode virar motivo para mover uma característica de lugar.
    """
    texto = str(casas_permitidas if casas_permitidas is not None else "").strip()
    if not texto.isdigit():
        return True
    return casas_decimais_de(valor) <= int(texto)


def _linha_de_transbordo(dado):
    nome = str(dado.get("CARACTERISTICA_CHAVE", "")).strip()
    valor = str(dado.get("RESPOSTA_PT_FINAL", "")).strip()
    simbolo = str(dado.get("SIMBOLO", "") or "").strip()
    if simbolo and simbolo.upper() != "AD":
        valor = f"{valor} {simbolo}"
    return f"{nome}: {valor}"


def realocar_por_casas_decimais(dados, casas_por_caracteristica):
    """Move para o texto livre os valores que não cabem no campo numérico.

    Devolve `(dados_ajustados, movidas)`. `movidas` é a lista de nomes -- o
    chamador loga, porque mover característica de lugar em silêncio esconderia
    do usuário exatamente a informação que ele precisa conferir.

    A característica de origem vira `REMOVER`: deixá-la como `PREENCHER` faria
    o robô tentar de novo e falhar de novo, e deixá-la em branco no portal
    confundiria "não coube" com "não se aplica".
    """
    linhas_extras = []
    movidas = []
    ajustados = []

    for dado in dados:
        nome = str(dado.get("CARACTERISTICA_CHAVE", "")).strip()
        tipo = str(dado.get("TIPO", "")).strip().upper()
        acao = str(dado.get("ACAO", "")).strip().upper()
        if (acao == "PREENCHER" and tipo in TIPOS_NUMERICOS
                and not cabe_nas_casas(dado.get("RESPOSTA_PT_FINAL"),
                                       casas_por_caracteristica.get(nome))):
            linhas_extras.append(_linha_de_transbordo(dado))
            movidas.append(nome)
            ajustados.append({"CARACTERISTICA_CHAVE": nome, "ACAO": "REMOVER"})
            continue
        ajustados.append(dado)

    if not linhas_extras:
        return ajustados, []

    for dado in ajustados:
        if str(dado.get("CARACTERISTICA_CHAVE", "")).strip().upper() != CARACTERISTICA_TEXTO_LIVRE:
            continue
        for chave in ("RESPOSTA_PT_FINAL", "RESPOSTA_ES_FINAL"):
            atual = str(dado.get(chave, "") or "").strip()
            # "N/A" é resposta de "não há", e o que estamos acrescentando É
            # conteúdo -- mantê-lo faria a ficha dizer as duas coisas.
            if atual.upper() in ("N/A", "NA", "-"):
                atual = ""
            dado[chave] = "\n".join([p for p in (atual, *linhas_extras) if p])
        dado["ACAO"] = "PREENCHER"
        return ajustados, movidas

    # O PDM não tem o campo de texto livre: não dá para mover. Melhor devolver
    # tudo como estava e avisar do que apagar a característica sem destino.
    return dados, []


COLUNA_REVISAO_DO_MASTER = "REVISIÓN"


def revisao_como_numero(valor):
    """`"1"` -> 1.0; lixo -> -1.0 (perde para qualquer revisão de verdade)."""
    texto = str(valor if valor is not None else "").strip().replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return -1.0


def filtrar_revisao_vigente(df_do_pdm, coluna=COLUNA_REVISAO_DO_MASTER):
    """Fica só com as linhas da MAIOR revisão do PDM.

    ⚠️ Este filtro é o conserto do "lixo" que o usuário relatou em 2026-08-18,
    e ele só existe porque o Master REAL foi finalmente lido. A entrada
    anterior de PENDENCIAS dizia que a revisão era irrecuperável -- estava
    errada: `TEMPLATE_PDM` tem a coluna `REVISIÓN` (coluna 10), e o cabeçalho
    de verdade está na LINHA 6, não na 3.

    Medido no arquivo do usuário (`PDMs SAM-GM`, 32.655 linhas, 1.194 PDMs):

        PDM.4820.015   revisão 0: 42 características
                       revisão 1: 20  <- vigente
                       união:     44  <- o que entrava no JSON
                       lixo:      24  (CONTINUACAO 1..4, COR, COMPRIMENTO…)

    Os 24 batem, nome por nome, com os `REMOVER` que o usuário não reconheceu.
    E 1.023 dos 1.194 PDMs têm mais de uma revisão, então isto não é um caso
    isolado deste PDM.

    Por que não bastava a deduplicação: ela colapsa nomes REPETIDOS entre
    revisões, mas característica que existiu SÓ na revisão antiga tem nome
    único, passa pelo filtro e chega ao JSON. As duas coisas são
    complementares -- este filtro continua antes dela.

    Coluna ausente ⇒ devolve tudo. Um Master exportado sem `REVISIÓN` é raro,
    mas descartar o PDM inteiro por causa disso trocaria um problema visível
    por um mudo.
    """
    if coluna not in getattr(df_do_pdm, "columns", []):
        return df_do_pdm
    revisoes = [revisao_como_numero(v) for v in df_do_pdm[coluna]]
    if not revisoes:
        return df_do_pdm
    vigente = max(revisoes)
    manter = [r == vigente for r in revisoes]
    return df_do_pdm[manter]


def deduplicar_contexto(lista_contexto):
    """Uma característica por nome no contexto enviado à IA.

    O Master (SAM) é filtrado só por CÓDIGO PDM, e guarda uma linha por
    característica POR REVISÃO -- PDM.4320.002 tem 106 linhas em 3 revisões
    para 51 características reais. Mandar as 106 tem três custos, e nenhum é
    teórico:

      1. a IA recebe a mesma característica 2-3 vezes e responde 2-3 vezes,
         com instruções que se contradizem (PREENCHER e REMOVER para a mesma
         chave) -- a origem do bug dos 16 campos perdidos;
      2. o prompt dobra de tamanho, e o custo com ele;
      3. as revisões antigas trazem TIPO_DADO e texto de ajuda DEGRADADOS
         (na revisão 0 deste PDM, tudo é "CHAR" e a ajuda é vazia), o que
         empurra a IA para o tipo errado.

    Fica a PRIMEIRA ocorrência: o Master vem ordenado com a revisão vigente
    à frente das antigas. E a tela do portal mostra cada característica uma
    vez só, então nada se perde -- o que sobrava não tinha para onde ir.
    """
    vistos = set()
    unicos = []
    for entrada in lista_contexto:
        chave = str(entrada.get("CARACTERISTICA_DESC_PT", "")).strip().upper()
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(entrada)
    return unicos


def normalizar_resposta_specs(bruto):
    """Devolve a lista de características da resposta da IA, ou levanta
    `ValueError` dizendo o que veio no lugar.

    Aceita o envelope de um único par (`{"items": [...]}`, `{"dados": [...]}`,
    o nome não importa) e devolve a lista de dentro. Qualquer outra coisa é
    erro -- inclusive uma lista cujos itens não tenham as chaves que o RPA lê.
    """
    if bruto is None:
        raise ValueError("A IA não devolveu resposta nenhuma.")

    # Desembrulha envelopes de 1 chave, aninhados ou não (`{"resultado":
    # {"items": [...]}}` já foi visto na natureza). O teto de 3 evita laço
    # infinito num JSON malformado auto-referente.
    for _ in range(3):
        if isinstance(bruto, dict) and len(bruto) == 1:
            unico = next(iter(bruto.values()))
            if isinstance(unico, (list, dict)):
                bruto = unico
                continue
        break

    if not isinstance(bruto, list):
        raise ValueError(
            f"A IA devolveu {type(bruto).__name__}, e o formato exigido é uma LISTA de "
            f"características no nível raiz. Conteúdo recebido: {str(bruto)[:200]}"
        )

    for posicao, item in enumerate(bruto, start=1):
        if not isinstance(item, dict):
            raise ValueError(
                f"O item {posicao} da resposta da IA é {type(item).__name__}, não um objeto JSON."
            )

        faltando = [c for c in CHAVES_ITEM_SEMPRE if c not in item]
        if str(item.get("ACAO", "")).strip().upper() == "PREENCHER":
            faltando += [c for c in CHAVES_ITEM_PREENCHER if c not in item]

        if faltando:
            raise ValueError(
                f"O item {posicao} da resposta da IA não tem {', '.join(faltando)}. "
                f"Chaves que vieram: {', '.join(sorted(item)) or '(nenhuma)'}. "
                "O modelo escolhido não está seguindo o formato pedido no prompt -- "
                "troque o modelo da tarefa 'Caract. Técnicas' no painel 'Modelos de IA' "
                "da Home."
            )

    return bruto


# =============================================================================
# CLASSE 1: PROCESSADOR DE DADOS E IA
# =============================================================================
class TechSpecsProcessor:
    def __init__(self, api_key):
        self.api_key = api_key
        # CP 2.2: stop-flag delega para `PMIBPortal` -- construído SEM
        # engine, porque esta classe só chama a API do Gemini (não tem
        # driver/browser nenhum) -- mesmo padrão de `ConditionsProcessor`
        # (upload_conditions_backend.py); ver docstring de
        # `PMIBPortal.__init__` e docs/refatoracao/PENDENCIAS.md.
        self.portal = PMIBPortal()
        # CP 3.1: `genai.configure(...)` sai daqui -- agora vive dentro de
        # `GeminiProvider` (chamado por `get_llm`), com o MESMO guard ("só
        # configura se api_key for truthy").
        self._llm = get_llm("tech_specs", api_key)

    def solicitar_parada(self):
        self.portal.solicitar_parada()

    # --- HELPERS DE TEXTO E EXCEL ---

    def normalizar_texto(self, texto):
        if not texto: return ""
        texto_norm = unicodedata.normalize('NFD', str(texto))
        texto_sem_acento = "".join(c for c in texto_norm if unicodedata.category(c) != 'Mn')
        return " ".join(texto_sem_acento.upper().split())

    def limpar_pergunta(self, texto_pergunta):
        match = re.search(r"^\d+\s*-\s*(.*)", str(texto_pergunta))
        if match: return match.group(1).strip()
        return str(texto_pergunta).strip()

    def extrair_codigo_pmib_arquivo(self, nome_arquivo):
        # CP 1.2: delega para a implementação única (core.excel.pmib_codes).
        # O chamador já passa o basename (preparar_dados_ia faz
        # os.path.basename() antes de invocar este método); basename aqui
        # dentro é idempotente, então o comportamento é preservado.
        return pmib_codes.extract_pmib_code_full(nome_arquivo)

    def formatar_pdm(self, pdm_raw):
        partes = str(pdm_raw).split(' ')
        return partes[0].strip()

    def encontrar_header(self, df, coluna_chave, limite_linhas=15):
        # CP 1.2: delega para a implementação única (core.excel.headers).
        header_idx = headers.find_header_row(df.head(limite_linhas).values.tolist(), coluna_chave)

        if header_idx is not None:
            df.columns = df.iloc[header_idx]
            return df.iloc[header_idx + 1:].reset_index(drop=True)
        return pd.DataFrame()

    # CP 3.1: `_limpar_json_ia` REMOVIDO -- a limpeza/parse do JSON da
    # resposta agora é responsabilidade única de
    # `sigft.core.llm.client._limpar_e_parsear_json` (chamada internamente
    # por `LLMClient.generate()`, usado em `_chamar_gemini_specs` abaixo).

    # --- LÓGICA PRINCIPAL DE PREPARAÇÃO ---
    def preparar_dados_ia(self, lista_arquivos, path_status, path_master, processar_completos=False, callback_log=None):
        """
        Lê Excel -> Cruza dados -> Chama IA -> Retorna JSON processado.
        """
        if callback_log: callback_log("Lendo arquivos de referência...")

        try:
            df_status_raw = pd.read_excel(path_status, sheet_name="Lista de Materiais", header=None)
            status_df = self.encontrar_header(df_status_raw, config.COL_CODIGO_PMIB)

            df_master_raw = pd.read_excel(path_master, sheet_name="TEMPLATE_PDM", header=None)
            master_pdm_df = self.encontrar_header(df_master_raw, "CÓDIGO PDM", limite_linhas=10)
        except Exception as e:
            if callback_log: callback_log(f"Erro ao ler arquivos base: {e}")
            return []

        resultados_processados = []

        # 2. Loop Arquivos
        for arquivo in lista_arquivos:
            # --- VERIFICAÇÃO DE PARADA ---
            if self.portal.deve_parar():
                if callback_log: callback_log("Processamento IA interrompido pelo usuário! Salvando o que já foi processado...")
                break

            nome_arquivo = os.path.basename(arquivo)
            codigo_pmib = self.extrair_codigo_pmib_arquivo(nome_arquivo)

            if not codigo_pmib:
                if callback_log: callback_log(f"Ignorado (Sem PMIB): {nome_arquivo}")
                continue

            # Match Status
            row_status = status_df[status_df['CÓDIGO PMIB'].astype(str).str.contains(codigo_pmib, na=False)]
            if row_status.empty:
                if callback_log: callback_log(f"PMIB {codigo_pmib} não encontrado no Status.")
                continue

            # --- VERIFICAÇÃO DE STATUS COMPLETO ---
            # `processar_completos` vem do interruptor "Forçar processamento
            # de fichas 'COMPLETO'" da tela, e AQUI ele sempre funcionou (o
            # gêmeo em `upload_conditions` é que estava solto -- corrigido em
            # 2026-08-18).
            coluna_status = config.COL_CARACT_TECNICAS
            if coluna_status in row_status.columns:
                status_atual = str(row_status.iloc[0][coluna_status]).strip().upper()
                if status_atual == "COMPLETO":
                    if processar_completos:
                        # Sinal VISÍVEL de que o interruptor pegou. Sem ele, a
                        # única evidência seria a ausência da linha "PULADO",
                        # e ausência de mensagem não é algo que o usuário veja.
                        if callback_log:
                            callback_log(f"PMIB {codigo_pmib} está COMPLETO, mas o "
                                         f"'Forçar processamento' está ligado -- reprocessando.")
                    else:
                        if callback_log: callback_log(f"PULADO: PMIB {codigo_pmib} já está COMPLETO. (Economizando API)")
                        continue
            else:
                # A coluna não existe com esse nome. O código antigo apenas
                # não fazia a checagem -- em silêncio, e com a consequência
                # invertida: TODA ficha era mandada para a IA, inclusive as
                # completas, gastando API justamente onde o objetivo era
                # economizar. Quem visse o gasto não teria como ligar uma
                # coisa à outra.
                if callback_log:
                    callback_log(f"   [!] Coluna {coluna_status!r} não existe no _STATUS_PMIB -- "
                                 f"não dá para saber se {codigo_pmib} já está COMPLETO. "
                                 f"Processando (pode gastar API à toa).")
            # -------------------------------------------

            try:
                pdm_usado = row_status.iloc[0]['PDM usado']
                pdm_fmt = self.formatar_pdm(pdm_usado)
            except Exception:
                if callback_log: callback_log(f"Erro ao ler PDM usado para {codigo_pmib}.")
                continue

            # Match Master PDM
            df_master_filt = master_pdm_df[master_pdm_df['CÓDIGO PDM'].astype(str) == pdm_fmt]
            if df_master_filt.empty:
                if callback_log: callback_log(f"PDM {pdm_fmt} não encontrado no Master.")
                continue

            # Só a revisão VIGENTE. Ver `filtrar_revisao_vigente`: o Master
            # guarda todas as revisões, e as antigas traziam características
            # que não existem mais na ficha -- o "lixo" de REMOVER.
            antes_da_revisao = len(df_master_filt)
            df_master_filt = filtrar_revisao_vigente(df_master_filt)
            if callback_log and len(df_master_filt) != antes_da_revisao:
                callback_log(
                    f"   [Revisão] {pdm_fmt}: {antes_da_revisao} linha(s) no Master "
                    f"(todas as revisões) -> {len(df_master_filt)} da revisão vigente.")

            # Ler Ficha Individual
            try:
                df_ficha = pd.read_excel(arquivo, sheet_name="Especificações técnicas copiar", header=0)
                cols_map = {
                    "Pergunta": "PERGUNTA",
                    "Resposta (Espanhol s/ caracteres especiais)": "RESP_ES",
                    "Resposta (Português s/ caracteres especiais)": "RESP_PT"
                }
                # noqa B023: o pandas chama este lambda DENTRO do `rename`,
                # antes de `cols_map` poder mudar na proxima volta do laco.
                df_ficha = df_ficha.rename(columns=lambda x: cols_map.get(x, x))  # noqa: B023

                respostas_pmib = {}
                for _, row in df_ficha.iterrows():
                    p_limpa = self.limpar_pergunta(row['PERGUNTA'])
                    respostas_pmib[p_limpa] = {"pt": row['RESP_PT'], "es": row['RESP_ES']}
            except Exception as e:
                if callback_log: callback_log(f"Erro leitura ficha {nome_arquivo}: {e}")
                continue

            # Montar Contexto
            lista_contexto = []
            for _, row_m in df_master_filt.iterrows():
                desc_pt = str(row_m['CARACTERÍSTICA - DESCRIPCIÓN PT']).strip()
                dados_resp = respostas_pmib.get(desc_pt, {"pt": None, "es": None})

                # Três colunas do Master que SEMPRE existiram e nunca eram
                # enviadas à IA -- e cada uma corresponde a um erro medido no
                # 1º lote real:
                #   VALORES ES  -> o `<select>` do portal pode estar em ES; sem
                #                  a opção ES, o casamento falha e o campo fica
                #                  em branco;
                #   CANTIDAD DE DECIMALES -> "56%" virou "0,56" porque nada
                #                  dizia à IA quantas casas o campo aceita;
                #   SÍMBOLO (já ia) -> agora o prompt diz que é lista FECHADA,
                #                  depois de a IA devolver "kW" num campo que
                #                  só admite "CV, HP".
                lista_contexto.append({
                    "CARACTERISTICA_DESC_PT": desc_pt,
                    "TEXTO_AJUDA": str(row_m.get('TEXTO DE AYUDA PT', '')),
                    "TIPO_DADO": str(row_m.get('TIPO DE CARACTERÍSTICA', '')),
                    "VALORES_POSSIVEIS_MASTER": str(row_m.get('VALORES PT', '')),
                    "VALORES_POSSIVEIS_ES": str(row_m.get('VALORES ES', '')),
                    "CASAS_DECIMAIS": str(row_m.get('CANTIDAD DE DECIMALES', '')),
                    "SIMBOLO_UNIDADE": str(row_m.get('SÍMBOLO', '')),
                    "RESPOSTA_CRUA_PT": str(dados_resp['pt']),
                    "RESPOSTA_CRUA_ES": str(dados_resp['es'])
                })

            # O Master traz uma linha por característica POR REVISÃO do PDM;
            # a tela do portal mostra cada uma UMA vez. Mandar as repetidas
            # fazia a IA responder instruções contraditórias para a mesma
            # chave -- ver `deduplicar_contexto`.
            total_bruto = len(lista_contexto)
            lista_contexto = deduplicar_contexto(lista_contexto)
            if callback_log and total_bruto != len(lista_contexto):
                callback_log(
                    f"   [Contexto] {total_bruto} linhas no Master para este PDM "
                    f"(revisões antigas incluídas) -> {len(lista_contexto)} características "
                    "únicas enviadas à IA."
                )

            pacote_envio = {
                "CODIGO_PMIB": codigo_pmib,
                "PDM": pdm_fmt,
                "CARACTERISTICAS": lista_contexto
            }

            # Chamada IA
            if callback_log: callback_log(f"Enviando {codigo_pmib} para IA...")
            # Passa o callback para logar erros internos da API
            dados_tratados = self._chamar_gemini_specs(pacote_envio, callback_log)

            if dados_tratados:
                # Transbordo de casas decimais -> texto livre. Em CÓDIGO e não
                # só no prompt: é aritmética com resposta única, e das 6.085
                # linhas NUM do Master 6.060 aceitam 2 casas -- depender do
                # modelo lembrar disso a cada ficha seria escolher a fonte
                # menos confiável para algo sem ambiguidade.
                casas = {c["CARACTERISTICA_DESC_PT"]: c.get("CASAS_DECIMAIS")
                         for c in lista_contexto}
                dados_tratados, movidas = realocar_por_casas_decimais(dados_tratados, casas)
                if movidas and callback_log:
                    callback_log(
                        f"   [Decimais] {len(movidas)} característica(s) não cabem no campo "
                        f"numérico e foram para '{CARACTERISTICA_TEXTO_LIVRE}': "
                        + ", ".join(movidas))

                resultados_processados.append({
                    "METADATA": {
                        "PMIB": codigo_pmib,
                        "PDM": pdm_fmt,
                        "ARQUIVO_ORIGEM": nome_arquivo
                    },
                    "DADOS_TRATADOS": dados_tratados
                })
                if callback_log: callback_log(f"Sucesso IA: {codigo_pmib}")
            else:
                if callback_log: callback_log(f"Falha IA: {codigo_pmib} (Verifique console para detalhes)")

        return resultados_processados

    def _chamar_gemini_specs(self, contexto_json, callback_log=None):
        # CP 3.5 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 3): o TEXTO
        # deste system prompt (estático -- antes embutido aqui) agora mora em
        # `sigft.core.llm.prompts.SYSTEM_TECH_SPECS`.
        system_instruction = prompts.SYSTEM_TECH_SPECS

        # CP 3.5: o TEXTO deste prompt de usuário agora mora em
        # `sigft.core.llm.prompts.montar_tech_specs_user` -- a
        # serialização do JSON continua aqui (só o texto muda de arquivo,
        # resultado em runtime é byte-idêntico).
        contexto_json_serializado = json.dumps(contexto_json, indent=2, ensure_ascii=False)
        prompt_user = prompts.montar_tech_specs_user(contexto_json_serializado)

        # CP 3.1: `safety_settings` (BLOCK_NONE) e o laço de retry (3
        # tentativas, 2s entre elas) saem daqui -- `safety_settings` agora
        # vive dentro de `GeminiProvider` (aplicado a TODA chamada, ver
        # docs/refatoracao/PENDENCIAS.md); retry + limpeza/parse do JSON
        # (`generation_config={"response_mime_type": "application/json"}`
        # via `json_mode=True`) agora vivem dentro de `LLMClient.generate()`
        # (`self._llm`, resolvido em `__init__` via
        # `get_llm("tech_specs", ...)`). Preserva o `return None` em falha
        # total -- só os logs GRANULARES por tentativa ("Retry N: IA
        # retornou texto vazio.", "Retry N Error: ...") deixam de existir
        # (perda de granularidade aceita, ver PENDENCIAS.md).
        def _pedir(prompt):
            resp = self._llm.generate(
                prompt,
                system=system_instruction,
                json_mode=True,
                tags={"modulo": "upload_tech_specs_backend", "tarefa": "tech_specs"},
            )
            # Valida ANTES de virar arquivo: um JSON fora do contrato só
            # explodiria lá na frente, com o robô já dentro do portal (ou,
            # pior, preencheria a ficha com campos vazios em silêncio).
            return normalizar_resposta_specs(resp.parsed_json)

        try:
            return _pedir(prompt_user)
        except ValueError as erro_formato:
            # SEGUNDA CHANCE com o erro na mão. Repetir o mesmo prompt não
            # adiantaria (o modelo repete a interpretação); mostrar o motivo
            # exato da recusa, sim -- modelos corrigem formato com facilidade
            # quando sabem o que saiu errado. É model-agnóstico de propósito:
            # o app não pode depender de um provedor acertar de primeira.
            #
            # Só `ValueError` (formato). Erro de rede/cota vem como outra
            # exceção e cai no `except` de baixo, sem gastar uma 2ª chamada
            # que falharia igual.
            if callback_log:
                callback_log(f"   [Formato] A IA respondeu fora do contrato: {erro_formato}")
                callback_log("   [Formato] Pedindo correção (2ª e última tentativa)...")
            try:
                dados = _pedir(prompts.montar_tech_specs_correcao(
                    str(erro_formato), contexto_json_serializado,
                ))
            except Exception as erro_segunda:
                if callback_log:
                    callback_log(f"   [Formato] A correção também falhou: {erro_segunda}")
                return None
            if callback_log:
                callback_log("   [Formato] Corrigido na 2ª tentativa.")
            return dados
        except Exception as e:
            if callback_log: callback_log(f"Erro ao chamar IA: {e}")
            return None


# =============================================================================
# CP 5.3 (Fase 5) — seletores XPath da aba "Características técnicas".
#
# Os `XPATH_REL_*` são RELATIVOS a uma linha da tabela: antes eram usados como
# `linha.find_element(By.XPATH, ".//textarea[...]")`; agora são concatenados ao
# seletor da linha (`(//linhas)[3]` + `.//textarea[...]`). Mesmos XPaths,
# mesmo alvo — o que muda é o endereçamento, não a estratégia de seletor.
# =============================================================================
XPATH_ABA_CARACTERISTICAS = "//button[@role='tab' and contains(., 'Características técnicas')]"
XPATH_TABELA_CARACTERISTICAS = "//div[contains(@id, 'TechnicalCharacteristics')]//table"
XPATH_LINHAS_TABELA = "//div[contains(@id, 'TechnicalCharacteristics')]//table/tbody/tr"
XPATH_BOTAO_PROXIMA_PAGINA = "//button[@aria-label='Ir para a página seguinte']"

# A seção de Características, para ANCORAR o SALVAR. A ficha tem um botão
# "SALVAR" por seção, e sem âncora a busca varre a tela -- 2026-08-20.
XPATH_SECAO_DE_CARACTERISTICAS = "//div[contains(@id, 'TechnicalCharacteristics_Content')]"

# Teto de paginas da tabela. Um botao "proxima" que nunca desabilita giraria
# para sempre; `limpar_caracteristicas` e o leitor da E1 tem o mesmo teto.
MAX_PAGINAS_CARACTERISTICAS = 50

# ---------------------------------------------------------------------------
# O CAMPO QUE O PORTAL RECUSOU (2026-09-23, HTML mandado pelo usuario)
# ---------------------------------------------------------------------------
# Quando o SALVAR nao passa, o portal nao se limita ao toast generico: ele
# MARCA os campos culpados. O `<textarea>` ganha a classe `not-valid` e nasce
# embaixo dele um aviso:
#
#   <textarea class="form-control text-uppercase not-valid"
#             id="...-TextArea_ValuePT">FECHADOaa</textarea>
#   <div ...><div><div><span class="text-error">Caracter invalido!</span></div></div></div>
#
# ⚠️ O MARCADOR E A CLASSE, NAO O TEXTO. A mensagem muda conforme o motivo
# (caractere invalido, limite do SAP, campo obrigatorio); `not-valid` e
# `text-error` sao o que nao muda. Mesma licao do toast de sucesso, que e
# reconhecido por `feedback-message-success` e nao pela redacao.
#
# ⚠️ E ELE APARECE POR IDIOMA. Numa linha CHAR o aviso nasce embaixo do ES e do
# PT separadamente -- entao da para dizer em qual dos dois esta o problema, o
# que poupa procurar nos dois.
XPATH_REL_ERRO_DO_CAMPO = (
    "//span[contains(concat(' ', normalize-space(@class), ' '), ' text-error ')]"
)
XPATH_REL_CAMPO_INVALIDO = (
    "//*[contains(concat(' ', normalize-space(@class), ' '), ' not-valid ')]"
)
# Por idioma, para dizer QUAL dos dois.
XPATH_REL_INVALIDO_PT = (
    "//textarea[contains(concat(' ', normalize-space(@class), ' '), ' not-valid ')]"
    "[contains(@id, 'TextArea_ValuePT')]"
)
XPATH_REL_INVALIDO_ES = (
    "//textarea[contains(concat(' ', normalize-space(@class), ' '), ' not-valid ')]"
    "[contains(@id, 'TextArea_ValueES')]"
)
NOME_DA_SECAO_DE_CARACTERISTICAS = "Características técnicas"

XPATH_REL_COL_DESCRICAO = "//td[contains(@data-header, 'Descrição')]"
XPATH_REL_TEXTAREA_PT = '//textarea[contains(@id, "TextArea_ValuePT")]'
XPATH_REL_TEXTAREA_ES = '//textarea[contains(@id, "TextArea_ValueES")]'
XPATH_REL_INPUT_NUM = '//input[contains(@id, "NumberValue_Input")]'
XPATH_REL_INPUT_MIN = '//input[contains(@id, "MinValue_Input")]'
XPATH_REL_INPUT_MAX = '//input[contains(@id, "MaxValue_Input")]'
XPATH_REL_SELECT_LISTA = '//select[contains(@id, "Dropdown1")]'
XPATH_REL_SELECT_INTERVALO = '//select[contains(@id, "Dropdown_IntervalOptions")]'
XPATH_REL_SELECT_UNIDADE = '//select[contains(@id, "DropdownTCUnitsOfMeasurement")]'


# =============================================================================
# CLASSE 2: AUTOMAÇÃO WEB (SELENIUM) - VERSÃO FINAL BLINDADA
# =============================================================================
class TechSpecsAutomation:
    def __init__(self):
        self.engine = None
        # CP 2.2: `self.portal` (SEM engine ainda) já nasce aqui -- não só em
        # `iniciar()` -- para que `solicitar_parada()` continue seguro de
        # chamar a QUALQUER momento, inclusive ANTES de `iniciar()` rodar
        # (mesmo racional de `UploadAutomation` em
        # upload_conditions_backend.py: o botão "Parar" do frontend pode
        # disparar entre a atribuição a `self.automacao_ativa` e a thread de
        # trabalho chegar a `iniciar()`). `iniciar()` abaixo só ANEXA o
        # engine à MESMA instância de `PMIBPortal` -- ver
        # docs/refatoracao/PENDENCIAS.md.
        self.portal = PMIBPortal()

    def solicitar_parada(self):
        self.portal.solicitar_parada()

    def iniciar(self):
        """CP 2.1: a criação em si (Chrome + maximize + WebDriverWait(20s))
        agora vem de `create_chrome_driver` (única fábrica, ver
        core/rpa/selenium_engine.py) — timeout preservado EXATAMENTE como
        antes (20s) (inclusive: este método nunca teve `return self.driver`
        — preservado sem retorno).

        CP 2.2: `self.portal` (já existente desde `__init__`, ver acima)
        ganha o `engine` de verdade.

        CP 5.3: quem escolhe o motor é `criar_engine`, por
        `config.RPA_ENGINE["tech_specs"]`. Timeout de 20s preservado nos dois
        motores; `self.engine` é agora a única referência ao browser nesta
        classe (`self.driver`/`self.wait` deixaram de existir).
        """
        self.engine = criar_engine("tech_specs", wait_timeout=20)
        self.portal.engine = self.engine

    def fechar(self):
        if self.engine:
            self.engine.fechar()

    def abrir_portal(self, url):
        if self.engine:
            self.engine.goto(url)

    # --- HELPERS DE INTERAÇÃO SEGURA ---
    def safe_click(self, locator):
        """Clica com Scroll + JS para evitar interceptação.

        CP 2.2: DELEGADOR FINO -- a mecânica real agora vive em
        `PMIBPortal.safe_click`/`SeleniumEngine.click` (um único lugar).
        `locator` continua aceito como tupla `(By.XPATH, xpath)` -- é assim
        que os MUITOS call sites internos desta classe já chamam hoje; a
        string XPath é extraída aqui antes de repassar."""
        seletor = locator[1] if isinstance(locator, tuple) else locator
        self.portal.safe_click(seletor)

    def safe_send_keys_elem(self, seletor, text):
        """Preenche inputs limpando antes e enviando TAB no final.

        CP 5.3: passou a receber o SELETOR em vez do elemento Selenium -- era
        justamente esse elemento circulando entre métodos que impedia o
        módulo de rodar em Playwright. A mecânica é a mesma:
        `engine.fill` já faz scroll + clique de foco + Ctrl+A + Backspace +
        digitar (a versão TOLERANTE, que engole falha, igual ao
        `except Exception: pass` do original); o TAB do fim continua aqui,
        depois da pausa de digitação.
        """
        try:
            self.engine.scroll_to(seletor)
            time.sleep(PAUSA_SCROLL)
            self.engine.fill(seletor, str(text))
            time.sleep(PAUSA_DIGITACAO)
            self.engine.press("TAB")
        except Exception:
            pass

    def safe_send_keys_locator(self, locator, text):
        """Alias retrocompatível: aceita a tupla `(By.XPATH, xpath)` que os
        call sites antigos usavam e repassa só o XPath."""
        seletor = locator[1] if isinstance(locator, tuple) else locator
        self.safe_send_keys_elem(seletor, text)

    # --- HELPERS DE DADOS ---
    def normalizar_texto(self, texto):
        if not texto: return ""
        norm = unicodedata.normalize('NFD', str(texto))
        sem_acento = "".join(c for c in norm if unicodedata.category(c) != 'Mn')
        return " ".join(sem_acento.upper().split())

    def selecionar_dropdown_lista(self, seletor, texto, alternativas=(), nome_campo="", callback_log=None):
        """Seleciona no `<select>`, tentando PT e ES, e DEVOLVE se conseguiu.

        CP 5.3: recebe SELETOR em vez de elemento; o `Select` do Selenium
        virou as primitivas `opcoes`/`selecionar_por_texto`/
        `selecionar_por_indice`. A REGRA de casamento fica aqui, que é onde
        ela é regra de negócio -- o motor só sabe mexer no `<select>`.

        Reescrito em 2026-08-11 por dois motivos relatados no uso real:

        1. **A lista falhava calada.** Toda a função vivia dentro de um
           `except Exception: pass`, e quando nenhum casamento dava certo ela
           voltava como se tivesse selecionado. A característica ficava em
           branco no portal e ninguém sabia -- justamente o campo em que
           "vazio" é indistinguível de "não se aplica". Agora devolve
           `True`/`False`, e o chamador transforma `False` em pendência
           manual, do mesmo jeito que o campo numérico já fazia.

        2. **O portal fala UMA língua por vez.** O `<select>` da linha é um
           só (`Dropdown1`), e as opções vêm ora em português ora em
           espanhol; mandar só o texto PT fazia o casamento falhar sempre que
           a tela estava em ES -- o problema que o usuário descreve como "ele
           tenta a opção espanhol na caixa de português". Passar a resposta ES
           como ALTERNATIVA resolve sem adivinhar em que língua a tela está:
           tenta-se uma, tenta-se a outra.

        A ordem é deliberada: TODOS os candidatos por casamento exato antes de
        qualquer casamento por substring. Substring é mais frouxo -- "60" casa
        "50/60" --, então deixá-la competir cedo trocaria um acerto exato de
        outro candidato por um acerto aproximado deste.
        """
        candidatos = [c for c in [texto, *alternativas] if str(c or "").strip()]
        if not candidatos:
            return True  # nada a selecionar não é falha

        opcoes = []
        try:
            opcoes = list(self.engine.opcoes(seletor))
        except Exception:
            pass

        # 1. Exato, para todos os candidatos.
        for candidato in candidatos:
            try:
                self.engine.selecionar_por_texto(seletor, candidato)
                return True
            except Exception:
                pass

        # 2. Substring normalizada, para todos os candidatos.
        for candidato in candidatos:
            alvo = self.normalizar_texto(candidato)
            for indice, opcao in enumerate(opcoes):
                if alvo and alvo in self.normalizar_texto(opcao):
                    try:
                        self.engine.selecionar_por_indice(seletor, indice)
                        return True
                    except Exception:
                        pass

        # 3. Desistiu -- e diz o que tentou E o que havia. As duas metades
        # importam: sem as opções reais, quem lê o log não sabe se o problema
        # foi a resposta da IA ou a tela.
        if callback_log:
            callback_log(
                f"   [!] Lista '{nome_campo}': nenhuma opção casou. "
                f"Tentado: {', '.join(repr(c) for c in candidatos)}. "
                f"Disponível na tela: {', '.join(repr(o) for o in opcoes) or '(nenhuma opção lida)'}"
            )
        return False

    def selecionar_dropdown_unidade(self, seletor, texto, nome_campo="", callback_log=None):
        """Idem, com a regra própria das unidades: casa o símbolo entre
        parênteses no texto da opção (ex.: "Milímetro (MM)").

        Também devolve `True`/`False` desde 2026-08-11. A unidade errada (ou
        ausente) é o tipo de defeito que passa despercebido na revisão: o
        número aparece certo na tela, e só quem confere a coluna de unidade
        nota que "3000" está em bar em vez de kPa. E ela falha com
        regularidade, porque a IA pode devolver um símbolo que o PDM não
        admite (medido: `POTENCIA BOMBA` recebeu "kW", mas o Master só aceita
        "CV, HP" para essa característica).
        """
        if not str(texto or "").strip():
            return True

        opcoes = []
        try:
            opcoes = list(self.engine.opcoes(seletor))
        except Exception:
            pass

        if not opcoes:
            # NADA lido: ou a característica não tem dropdown de unidade
            # (comum em LISTA e CHAR), ou ele ainda não carregou. Nos dois
            # casos NÃO é "a IA errou o símbolo", e tratar como falha
            # transformava um caso normal em pendência manual -- foi o que
            # aconteceu com FREQUENCIA NOMINAL no 2º lote real, onde o valor
            # tinha sido selecionado corretamente e mesmo assim a ficha saiu
            # marcada com campo rejeitado.
            if callback_log:
                callback_log(
                    f"   ·  '{nome_campo}': sem dropdown de unidade nesta linha "
                    f"(símbolo {texto!r} não aplicado)"
                )
            return True

        alvo_parenteses = f"({str(texto).strip().upper()})"
        for indice, opcao in enumerate(opcoes):
            if alvo_parenteses in opcao.upper():
                try:
                    self.engine.selecionar_por_indice(seletor, indice)
                    return True
                except Exception:
                    pass

        # Fallback: símbolo solto, sem os parênteses (algumas opções do portal
        # vêm só com a sigla). Depois dos parênteses, nunca antes -- "(V)" é
        # inequívoco, "V" casaria "kV" e "mV".
        alvo = self.normalizar_texto(texto)
        for indice, opcao in enumerate(opcoes):
            if alvo and self.normalizar_texto(opcao) == alvo:
                try:
                    self.engine.selecionar_por_indice(seletor, indice)
                    return True
                except Exception:
                    pass

        if callback_log:
            callback_log(
                f"   [!] Unidade '{nome_campo}': símbolo {texto!r} não existe no dropdown. "
                f"Disponível: {', '.join(repr(o) for o in opcoes) or '(nenhuma opção lida)'}"
            )
        return False

    def _preencher_input_com_auditoria(self, seletor, valor_alvo, seletor_neutro, nome_campo="", callback_log=None):
        """Tenta preencher, audita se o site zerou o valor e força o valor
        como 2ª tentativa.

        CP 5.3: recebe SELETORES (o campo e o "elemento neutro" para clicar
        fora) em vez de elementos Selenium. A 2ª tentativa -- que era injeção
        de JavaScript escrita à mão aqui -- virou `engine.forcar_valor`, que
        cada motor cumpre do seu jeito: no Selenium, a MESMA injeção com os 3
        `dispatchEvent`; no Playwright, um `fill` (que já emite os eventos).
        É exatamente o que o checkpoint pede, e o "fallback de aviso de
        pendência manual" continua sendo o `return False` daqui, que o
        chamador transforma em pendência.
        """
        if not valor_alvo:
            return True

        def _clicar_fora():
            if seletor_neutro and self.engine.element_exists(seletor_neutro):
                self.engine.click_raw(seletor_neutro)

        # 1ª Tentativa: Digitação normal
        self.engine.clear(seletor)
        self.safe_send_keys_elem(seletor, valor_alvo)
        _clicar_fora()
        time.sleep(PAUSA_AUDITORIA)

        # Auditoria
        valor_atual = str(self.engine.get_value(seletor)).strip()

        # Se o site rejeitou a primeira tentativa
        if (valor_atual == "0" or valor_atual == "") and str(valor_alvo).strip() != "0":

            # --- MENSAGEM VISUAL E PAUSA ESTRATÉGICA ---
            if callback_log:
                callback_log(f"   [!] O site rejeitou '{nome_campo}'. Tentando injeção forçada...")
            time.sleep(PAUSA_INJECAO_JS)  # Dá tempo para o usuário ver na tela e o JS do site assentar

            # 2ª Tentativa: força o valor por baixo da digitação
            self.engine.forcar_valor(seletor, valor_alvo)
            _clicar_fora()

            time.sleep(PAUSA_POS_INJECAO_JS)  # Pausa maior após a injeção para validar o resultado

            # Auditoria Final
            valor_atual_2 = str(self.engine.get_value(seletor)).strip()
            if (valor_atual_2 == "0" or valor_atual_2 == "") and str(valor_alvo).strip() != "0":
                return False  # Desiste de vez

        return True

    def _pesquisar_e_abrir(self, pmib):
        """Navega, Pesquisa e Clica no Lápis com tratamento de StaleElement.

        CP 2.2: o corpo passa a delegar para `PMIBPortal.pesquisar_e_abrir`
        com os seletores DEFAULT -- esta classe é justamente a FONTE da
        estrutura de robustez (retry 3x, tratamento de
        `StaleElementReferenceException`/`TimeoutException`, retorno bool)
        que `PMIBPortal.pesquisar_e_abrir` adota para TODOS os módulos; ver
        sua docstring para o levantamento completo dos seletores por
        módulo."""
        return self.portal.pesquisar_e_abrir(pmib)

    # --- FLUXO PRINCIPAL ---
    def processar_lista(self, lista_fichas, callback_log=None, callback_pause=None):
        pmibs_finalizados = []  # <--- NOVO: Lista para tracking

        # CP 4.4: `from_legacy` adapta o `callback_log` antigo sem mudar a
        # assinatura pública (o controller segue chamando igual).
        lote = RelatorioLote(
            from_legacy(callback_log=callback_log),
            titulo="Características Técnicas: preenchendo no portal",
            total=len(lista_fichas),
            contexto={"fichas": len(lista_fichas)},
        )
        lote.iniciar()

        for item in lista_fichas:
            # --- VERIFICAÇÃO DE PARADA ---
            if self.portal.deve_parar():
                if callback_log: callback_log("Robô Web interrompido pelo usuário!")
                break

            meta = item.get("METADATA", {})
            pmib = meta.get("PMIB")
            # 2ª camada de defesa: o JSON pode ter sido gerado ANTES da
            # validação existir (o do 1º teste real está assim no disco do
            # usuário) ou editado à mão. Sem isto, um `DADOS_TRATADOS` fora do
            # formato vira `TypeError: string indices must be integers` lá
            # embaixo, no meio do RPA -- mensagem que não aponta para o JSON.
            try:
                dados = normalizar_resposta_specs(item.get("DADOS_TRATADOS"))
            except ValueError as erro_formato:
                # Mesma dupla do `except` geral lá embaixo: a linha crua no
                # log e a contabilizada no resumo (o ❌ quem põe é o lote).
                if callback_log:
                    callback_log(f"JSON fora do formato em {pmib}: {erro_formato}")
                lote.falha(str(pmib), f"JSON fora do formato: {erro_formato}")
                continue

            # ---> NOVA VARIÁVEL: Guarda o que falhou na auditoria
            pendencias_manuais = []

            if callback_log: callback_log(f"Iniciando {pmib}...")

            try:
                # 1. Busca Robusta
                if not self._pesquisar_e_abrir(pmib):
                    if callback_log: callback_log(f"Erro: Ficha {pmib} não encontrada na busca.")
                    continue

                # 2. Entrar na Aba Specs
                self.safe_click(XPATH_ABA_CARACTERISTICAS)

                try:
                    self.engine.wait_visible(XPATH_TABELA_CARACTERISTICAS)
                except Exception:
                    if callback_log: callback_log("Erro: Tabela de características não carregou.")
                    continue

                time.sleep(PAUSA_CARGA_TABELA)

                # Dicionário de dados para acesso rápido O(1)
                # PREENCHER vence REMOVER na mesma chave -- ver
                # `indexar_por_caracteristica`. Um dict comprehension aqui
                # (o último vence) custou 16 dos 37 campos do 1º lote real.
                dict_dados = indexar_por_caracteristica(dados, self.normalizar_texto)

                # --- LOOP DE PAGINAÇÃO E LINHAS (Restaurado do Original) ---
                # Conjuntos da auditoria: o que a tela mostrou, o que foi
                # efetivamente preenchido e removido. Servem para a
                # RECONCILIAÇÃO no fim -- comparar o que o JSON pedia com o
                # que o portal recebeu é a única forma de "37 viraram 21"
                # aparecer numa execução em vez de numa conferência manual.
                vistas_na_tela = set()
                preenchidas = set()
                removidas = set()

                pagina_atual = 1
                while True:
                    if callback_log: callback_log(f"Processando Página {pagina_atual}...")

                    row_index = 0
                    while True:
                        # Reconta a cada iteração (CRÍTICO para evitar StaleElement)
                        #
                        # CP 5.3: era `find_elements` + `rows[row_index]`, ou
                        # seja, um ELEMENTO Selenium guardado e usado depois.
                        # Virou `contar` + XPath indexado -- o MESMO XPath de
                        # linha, endereçado por posição. E o efeito colateral é
                        # bom: como o seletor é reavaliado a cada uso, o
                        # elemento nunca "envelhece", que era a razão de o laço
                        # recarregar a lista inteira toda vez.
                        total_linhas = self.engine.contar(XPATH_LINHAS_TABELA)

                        if row_index >= total_linhas:
                            break  # Fim da página atual

                        # XPath é base 1; `row_index` é base 0.
                        seletor_linha = f"({XPATH_LINHAS_TABELA})[{row_index + 1}]"
                        item_foi_excluido = False

                        try:
                            # Traz a linha para a vista ANTES de tocá-la. Sem
                            # isto, uma linha abaixo da dobra não é
                            # "interactable" para o WebDriver e o preenchimento
                            # engasga -- o usuário relatou ter de rolar a tela
                            # à mão para o robô destravar. `scroll_to` não
                            # clica nem espera nada; é barato e vale para as
                            # 51 linhas.
                            try:
                                self.engine.scroll_to(seletor_linha)
                            except Exception:
                                pass  # rolar é conveniência, não pode matar a linha

                            # Extrair nome da característica na tela
                            txt_tela = self.engine.texto(seletor_linha + XPATH_REL_COL_DESCRICAO)
                            # A MESMA funcao que a limpeza usa. Ver
                            # `chave_da_caracteristica`: chaves diferentes
                            # fariam a limpeza apagar o que foi preenchido.
                            chave_limpa = chave_da_caracteristica(
                                txt_tela, self.normalizar_texto)

                            dado = dict_dados.get(chave_limpa)

                            # AUDITORIA POR LINHA. Toda característica que
                            # aparece na tela é registrada com o que foi feito
                            # nela -- pedido do usuário depois de o portal
                            # receber 21 dos 37 campos sem nenhuma mensagem de
                            # erro no terminal. Sem esta linha, "o que o robô
                            # fez" só era observável abrindo a ficha no portal
                            # e conferindo campo a campo.
                            vistas_na_tela.add(chave_limpa)
                            dado = dict_dados.get(chave_limpa)

                            if dado:
                                acao = dado.get("ACAO")

                                # --- CASO: REMOVER ---
                                if acao == "REMOVER":
                                    sucesso_exclusao = self._excluir_linha_segura(seletor_linha, chave_limpa, callback_log)
                                    if sucesso_exclusao:
                                        item_foi_excluido = True
                                        removidas.add(chave_limpa)
                                        if callback_log:
                                            callback_log(f"   🗑️  removido: {chave_limpa}")
                                    elif callback_log:
                                        callback_log(f"   ⚠️  NÃO removido (exclusão falhou): {chave_limpa}")
                                    # Se falhar, item_foi_excluido continua False e o iterador (row_index) será incrementado.
                                    # Isso impede que o robô trave eternamente tentando excluir a mesma linha com erro.

                                # --- CASO: PREENCHER ---
                                else:
                                    # Agora passamos o callback_log para a função poder avisar da 2ª tentativa
                                    sucesso_preenchimento = self._preencher_linha(seletor_linha, dado, callback_log)
                                    preenchidas.add(chave_limpa)
                                    valor_log = str(dado.get("RESPOSTA_PT_FINAL", ""))[:60]
                                    if sucesso_preenchimento:
                                        if callback_log:
                                            callback_log(f"   ✏️  preenchido: {chave_limpa} = {valor_log!r}")
                                    else:
                                        if callback_log:
                                            callback_log(f"   ⚠️  preenchimento REJEITADO pelo portal: {chave_limpa}")
                                        # Se a auditoria falhou, guarda os dados para avisar o usuário
                                        pendencias_manuais.append({
                                            "CHAVE": chave_limpa,
                                            "VALOR": dado.get("RESPOSTA_PT_FINAL", "N/A"),
                                            "UNIDADE": dado.get("SIMBOLO", "AD")
                                        })
                            elif callback_log:
                                # Linha na tela que a IA não mencionou. Não é
                                # erro, mas é informação: se aparecerem muitas,
                                # o casamento por NOME está falhando.
                                callback_log(f"   ·  ignorada (não veio no JSON): {chave_limpa}")

                        except ElementoObsoleto:
                            continue  # Tenta pegar a linha de novo
                        except Exception as erro_linha:
                            # Era `pass`. Uma linha que estoura aqui é uma
                            # característica que NÃO foi preenchida nem
                            # removida, e o silêncio fazia isso desaparecer:
                            # o lote terminava com "✅ sucesso" e a ficha
                            # incompleta no portal.
                            if callback_log:
                                callback_log(
                                    f"   ⚠️  linha {row_index + 1} da página {pagina_atual} falhou: "
                                    f"{type(erro_linha).__name__}: {erro_linha}"
                                )

                        # Se excluiu, NÃO incrementa (o item de baixo subiu). Se preencheu, incrementa.
                        if not item_foi_excluido:
                            row_index += 1

                    # --- PAGINAÇÃO ---
                    try:
                        # CP 5.3: `find_element` + `is_enabled` + `execute_script`
                        # viraram `element_exists` + `esta_habilitado` +
                        # `click_raw`. O `except` de fora continua sendo o
                        # "botão não existe -> última página".
                        if not self.engine.element_exists(XPATH_BOTAO_PROXIMA_PAGINA):
                            break  # Botão não existe
                        # Verifica se está habilitado (em alguns frameworks é class disabled)
                        if self.engine.esta_habilitado(XPATH_BOTAO_PROXIMA_PAGINA):
                            self.engine.click_raw(XPATH_BOTAO_PROXIMA_PAGINA)
                            time.sleep(PAUSA_PAGINACAO)
                            self.engine.wait_visible(XPATH_TABELA_CARACTERISTICAS)
                            pagina_atual += 1
                        else:
                            break  # Última página
                    except Exception:
                        break  # Botão não existe

                # 4. Relatório de Pendências da Auditoria
                if pendencias_manuais and callback_log:
                    callback_log("=========================================")
                    callback_log("⚠️ ATENÇÃO: O site bloqueou a digitação dos seguintes campos.")
                    callback_log("Por favor, preencha MANUALMENTE antes de salvar:")
                    for pendencia in pendencias_manuais:
                        callback_log(f" -> {pendencia['CHAVE']}: {pendencia['VALOR']} ({pendencia['UNIDADE']})")
                    callback_log("=========================================")

                # --- RECONCILIAÇÃO: o que o JSON pedia x o que o portal
                # recebeu. É a peça que faltava para "37 viraram 21" aparecer
                # numa EXECUÇÃO, em vez de só numa conferência campo a campo
                # dentro do portal. Sem ela, o lote fechava com "✅ sucesso"
                # e a ficha incompleta.
                if callback_log:
                    pedidos_preencher = {
                        c for c, d in dict_dados.items()
                        if str(d.get("ACAO", "")).strip().upper() != "REMOVER"
                    }
                    pedidos_remover = set(dict_dados) - pedidos_preencher
                    # Só conta o que EXISTE na tela: o JSON traz também
                    # características de revisões antigas do PDM, que não têm
                    # linha nenhuma na ficha e nunca poderiam ser tocadas.
                    alcancaveis_preencher = pedidos_preencher & vistas_na_tela
                    alcancaveis_remover = pedidos_remover & vistas_na_tela

                    callback_log(
                        f"   ── Auditoria {pmib}: {len(vistas_na_tela)} linha(s) vistas na tela | "
                        f"preenchidas {len(preenchidas)}/{len(alcancaveis_preencher)} | "
                        f"removidas {len(removidas)}/{len(alcancaveis_remover)}"
                    )
                    nao_alcancadas = sorted(pedidos_preencher - vistas_na_tela)
                    if nao_alcancadas:
                        callback_log(
                            f"   ⚠️  {len(nao_alcancadas)} característica(s) com resposta no JSON NUNCA "
                            "apareceram na tela (o robô não passou por elas): "
                            + ", ".join(nao_alcancadas)
                        )
                        lote.aviso(
                            pmib,
                            f"{len(nao_alcancadas)} característica(s) preenchida(s) pela IA não foram "
                            "alcançadas no portal",
                            "conferir a ficha antes de salvar",
                        )

                # 5. LIMPEZA: as linhas EM BRANCO que o JSON não menciona.
                #
                # Elas são características de uma revisão MAIS NOVA do PDM do
                # que a revisão em que a ficha foi feita. Pedido do usuário em
                # 2026-09-23. Ver `apagar_em_branco_fora_do_json`: as três
                # condições (em branco, fora do JSON, mesma chave) são todas
                # necessárias.
                apagadas_em_branco = self.apagar_em_branco_fora_do_json(
                    dict_dados, callback_log)
                if apagadas_em_branco and callback_log:
                    callback_log(
                        f"   ── {len(apagadas_em_branco)} caracteristica(s) em "
                        f"branco apagada(s) por nao virem no JSON de origem.")

                # 6. SALVAR, e só seguir com a confirmação do portal.
                #
                # ⚠️ ISTO MUDOU O FLUXO (2026-09-23). Antes o robô preenchia e
                # PAUSAVA em toda ficha, para a pessoa conferir e salvar. Agora
                # ele salva e lê o toast: confirmou, segue para a próxima; não
                # confirmou, aí sim chama a pausa -- que é onde a pessoa
                # realmente faz falta.
                salvou, mensagem_do_portal = self.salvar_caracteristicas(callback_log)

                if salvou:
                    if callback_log:
                        callback_log(f"   ✅ {pmib}: o portal confirmou o salvamento.")
                else:
                    if callback_log:
                        callback_log(
                            f"   ⛔ {pmib}: o portal NAO confirmou o salvamento"
                            + (f" ({mensagem_do_portal})" if mensagem_do_portal else "")
                            + ". Esta ficha precisa ser conferida e salva A MAO.")
                    # QUAIS campos o portal recusou. É o que transforma o
                    # "verifique os campos" na lista do que corrigir.
                    for erro in self.caracteristicas_com_erro():
                        idiomas = "/".join(erro["campos"]) or "campo"
                        if callback_log:
                            callback_log(
                                f"      ✋ {erro['chave']} [{idiomas}]: {erro['mensagem']}")

                    # A PAUSA SÓ AQUI. Era em toda ficha; agora é na que pede
                    # gente de verdade.
                    if callback_pause:
                        callback_pause(pmib)

                        # ⬇️ A RECONFERÊNCIA (2026-09-23). Sem ela, a ficha que
                        # a pessoa acabou de consertar e salvar durante a pausa
                        # continuaria pendente: o robô decidia pela 1ª tentativa
                        # e nunca mais olhava. Clicar em SALVAR de novo é barato
                        # e é a única forma de ele saber que o problema sumiu --
                        # o portal só devolve o toast verde se gravou AGORA.
                        salvou, mensagem_do_portal = self.salvar_caracteristicas(
                            callback_log)
                        if salvou:
                            if callback_log:
                                callback_log(
                                    f"   ✅ {pmib}: o portal confirmou o salvamento"
                                    " depois da conferencia. Ficha COMPLETA.")
                        elif callback_log:
                            callback_log(
                                f"   ⛔ {pmib}: o portal continua sem confirmar"
                                + (f" ({mensagem_do_portal})" if mensagem_do_portal else "")
                                + ". A ficha fica PENDENTE.")

                if not salvou:
                    lote.aviso(
                        pmib,
                        "o portal nao confirmou o salvamento"
                        + (f": {mensagem_do_portal}" if mensagem_do_portal else ""),
                        "conferir e salvar a mao (os campos recusados estao no log)",
                    )

                if pendencias_manuais:
                    lote.aviso(
                        pmib,
                        f"{len(pendencias_manuais)} campo(s) rejeitado(s) pela digitação do site",
                        "preencher MANUALMENTE antes de salvar (listados acima)",
                    )

                if callback_log: callback_log(f"Fim {pmib}.")

                # ⚠️ SÓ A FICHA CONFIRMADA CONTA COMO FINALIZADA. É esta lista
                # que marca "COMPLETO" no `_STATUS_PMIB`; marcar uma ficha que
                # o portal não gravou seria declarar pronto o que não está.
                # A ficha consertada durante a pausa chega aqui com `salvou`
                # já atualizado pela reconferência logo acima.
                if salvou:
                    pmibs_finalizados.append(pmib)
                    lote.sucesso(pmib)

            except Exception as e:
                if callback_log: callback_log(f"Erro geral {pmib}: {e}")
                lote.falha(pmib, f"{type(e).__name__}: {e}")

        lote.finalizar()
        return pmibs_finalizados  # <--- NOVO: Devolve a lista de sucesso para o Controller

    def _excluir_linha_segura(self, seletor_linha, chave_limpa, callback_log=None):
        """Tenta clicar na lixeira e confirmar a exclusão. Retorna True se der certo, False se falhar.

        CP 2.2: o corpo passa a delegar para
        `PMIBPortal.excluir_linha_com_confirmacao(row)` -- esta classe é a
        fonte da mecânica adotada pelo portal (sleep de 0,5s antes do
        clique na lixeira, 2,5s após confirmar; mesma mecânica também usada
        pelo ramo de exclusão de
        `upload_ficha_duplicada.InjetorFichaAlvo._limpar_caracteristicas_tecnicas`).
        `chave_limpa`/`callback_log` são só para o LOG desta classe (o
        portal não conhece esse vocabulário); a mensagem de falha perde o
        texto da exceção original (`{e}`) porque o portal engole a exceção
        internamente antes de devolver `False` -- ver
        docs/refatoracao/PENDENCIAS.md.
        """
        sucesso = self.portal.excluir_linha_com_confirmacao(seletor_linha)
        if callback_log:
            if sucesso:
                callback_log(f"Sucesso ao excluir item: {chave_limpa}")
            else:
                callback_log(f"Falha ao excluir item {chave_limpa}.")
        return sucesso

    # Campo que identifica cada tipo dentro de uma linha da tabela.
    CAMPO_CARACTERISTICO_DO_TIPO = {
        "CHAR": ("//textarea[contains(@id, \"TextArea_ValuePT\")]",),
        "NUM": ('//input[contains(@id, "NumberValue_Input")]',),
        "LISTA": ('//select[contains(@id, "Dropdown1")]',),
        "INT": ('//select[contains(@id, "Dropdown_IntervalOptions")]',),
    }

    def _linha_oferece(self, seletor_linha, tipo):
        """A linha tem o campo do tipo declarado? Tipo desconhecido ⇒ `True`.

        Devolver `True` para o que não se conhece é deliberado: o recuo existe
        para consertar divergência OBSERVADA, e um tipo novo do portal não
        pode virar motivo para o robô mudar de comportamento sozinho.
        """
        relativos = self.CAMPO_CARACTERISTICO_DO_TIPO.get(str(tipo).strip().upper())
        if not relativos:
            return True
        for relativo in relativos:
            try:
                if self.engine.element_exists(seletor_linha + relativo):
                    return True
            except Exception:  # noqa: BLE001 -- observar não derruba nada
                return True
        return False

    def _tipo_da_linha(self, seletor_linha):
        """Que tipo de campo ESTA LINHA do portal oferece? `""` se não der para saber.

        O portal renderiza a linha conforme o tipo QUE ELE conhece. Perguntar à
        tela, em vez de confiar no JSON, é o que transforma "o campo na tela é
        diferente" (exceção, campo em branco) em "então preencho do jeito que a
        tela aceita".

        A ordem importa: `INT` é testado antes de `NUM` porque a linha de
        intervalo tem DOIS inputs numéricos e casaria como NUM por engano.
        `""` (não sei) faz o chamador seguir o JSON, como antes -- não saber
        não pode virar motivo para mudar de comportamento.
        """
        def existe(relativo):
            try:
                return self.engine.element_exists(seletor_linha + relativo)
            except Exception:  # noqa: BLE001 -- observar não derruba nada
                return False

        if existe(XPATH_REL_TEXTAREA_PT):
            return "CHAR"
        if existe(XPATH_REL_SELECT_INTERVALO) and existe(XPATH_REL_INPUT_MIN):
            return "INT"
        if existe(XPATH_REL_SELECT_LISTA):
            return "LISTA"
        if existe(XPATH_REL_INPUT_NUM):
            return "NUM"
        return ""

    def apagar_em_branco_fora_do_json(self, dict_dados, callback_log=None):
        """Apaga as linhas EM BRANCO que o JSON de origem nao menciona.

        Pedido do usuario em 2026-09-23: quando a ficha foi feita numa revisao
        ANTIGA do PDM e o portal ja esta numa mais nova, a tabela tem linhas
        que nao existiam na origem. Elas ficam em branco, e ate aqui o robo as
        deixava com um `·  ignorada (nao veio no JSON)`.

        ⚠️ AS TRES CONDICOES SAO TODAS NECESSARIAS:

        - **em branco**: uma linha COM valor fora do JSON pode ter sido
          preenchida a mao. Apaga-la seria destruir trabalho humano;
        - **fora do JSON**: uma linha em branco que o JSON MENCIONA e um
          preenchimento que falhou. Apaga-la esconderia o que falta corrigir;
        - **a mesma chave do laco de preenchimento** (`chave_da_caracteristica`).

        ⚠️ O INDICE NAO AVANCA quando a linha e apagada: a de baixo sobe para o
        lugar dela. E a licao de `limpar_caracteristicas`. Quando a exclusao
        FALHA o indice avanca, senao o robo gira para sempre na mesma linha.

        Quem le a linha e `core/rpa/caracteristicas.ler_linha` -- o leitor que
        nasceu para a correcao de PDM e ja esta provado contra o HTML real do
        portal. Devolve a lista de chaves apagadas.
        """
        from sigft.core.rpa.caracteristicas import dentro_da_linha, ler_linha

        apagadas = []
        for _pagina in range(1, MAX_PAGINAS_CARACTERISTICAS + 1):
            indice = 1
            while True:
                if indice > self._quantas_linhas():
                    break

                seletor = f"({XPATH_LINHAS_TABELA})[{indice}]"
                try:
                    linha = ler_linha(self.engine, seletor)
                except Exception:  # noqa: BLE001 -- ler nao derruba a ficha
                    indice += 1
                    continue

                descricao = self.engine.texto(
                    dentro_da_linha(seletor, ".//td[contains(@data-header, 'Descrição')]"))
                chave = chave_da_caracteristica(descricao, self.normalizar_texto)

                if chave in dict_dados or not linha.esta_vazia:
                    indice += 1
                    continue

                antes = self._quantas_linhas()
                if self._excluir_linha_segura(seletor, chave, None):
                    # ⚠️ "APAGUEI" NAO E PROVA DE QUE SUMIU, e aqui isso nao e
                    # zelo: o indice so NAO avanca porque a linha de baixo sobe
                    # para o lugar desta. Se a exclusao mentir -- devolver
                    # `True` com a tabela intacta --, o laco tenta a mesma
                    # linha para sempre e o robo trava sem mensagem nenhuma.
                    # Conferir a contagem custa uma chamada.
                    if self._quantas_linhas() < antes:
                        apagadas.append(chave)
                        if callback_log:
                            callback_log(
                                f"   🗑️  apagada: {chave} (estava em branco e nao "
                                f"veio no JSON de origem; e caracteristica de uma "
                                f"revisao mais nova do PDM)")
                        continue   # a linha de baixo subiu para ca
                    if callback_log:
                        callback_log(
                            f"   ⚠️  o portal disse que apagou {chave}, mas a "
                            f"tabela continua com {antes} linha(s). Sigo.")
                    indice += 1
                    continue
                if callback_log:
                    callback_log(f"   ⚠️  nao consegui apagar a linha em branco: {chave}")
                indice += 1

            if not self._avancar_pagina():
                break
        return apagadas

    def _quantas_linhas(self):
        try:
            return self.engine.contar(XPATH_LINHAS_TABELA)
        except Exception:  # noqa: BLE001
            return 0

    def _avancar_pagina(self):
        """`True` se foi para a proxima pagina da tabela."""
        try:
            if not self.engine.element_exists(XPATH_BOTAO_PROXIMA_PAGINA):
                return False
            if not self.engine.esta_habilitado(XPATH_BOTAO_PROXIMA_PAGINA):
                return False
            self.engine.click_raw(XPATH_BOTAO_PROXIMA_PAGINA)
            time.sleep(PAUSA_PAGINACAO)
            return True
        except Exception:  # noqa: BLE001 -- botao ausente = ultima pagina
            return False

    def caracteristicas_com_erro(self):
        """As linhas que o portal MARCOU como invalidas, com o porque.

        Devolve `[{"chave", "campos", "mensagem"}, ...]`. `campos` diz em qual
        idioma esta o problema (`["PT"]`, `["ES"]` ou os dois) -- numa ficha
        bilingue isso poupa procurar nos dois.

        E o que transforma o "Por favor, verifique os campos" (que nao diz
        nada) na lista exata do que corrigir a mao. Ver o comentario em
        `XPATH_REL_ERRO_DO_CAMPO`: o marcador e a CLASSE, nao o texto.
        """
        from sigft.core.rpa.caracteristicas import dentro_da_linha

        achados = []
        for _pagina in range(1, MAX_PAGINAS_CARACTERISTICAS + 1):
            try:
                total = self.engine.contar(XPATH_LINHAS_TABELA)
            except Exception:  # noqa: BLE001 -- ler nao derruba a ficha
                break

            for indice in range(1, (total or 0) + 1):
                seletor = f"({XPATH_LINHAS_TABELA})[{indice}]"
                erros = self._textos(dentro_da_linha(seletor, XPATH_REL_ERRO_DO_CAMPO))
                if not erros:
                    continue

                descricao = self._texto_ou_vazio(
                    dentro_da_linha(seletor, XPATH_REL_COL_DESCRICAO))
                campos = [
                    idioma for idioma, relativo in (("PT", XPATH_REL_INVALIDO_PT),
                                                    ("ES", XPATH_REL_INVALIDO_ES))
                    if self._existe(dentro_da_linha(seletor, relativo))
                ]
                achados.append({
                    "chave": chave_da_caracteristica(descricao, self.normalizar_texto),
                    "campos": campos,
                    "mensagem": erros[0],
                })

            if not self._avancar_pagina():
                break
        return achados

    def _textos(self, seletor):
        """Os textos de TODOS os casamentos, normalizados. Nunca levanta."""
        try:
            total = self.engine.contar(seletor)
        except Exception:  # noqa: BLE001
            return []
        achados = []
        for posicao in range(1, (total or 0) + 1):
            texto = self._texto_ou_vazio(f"({seletor})[{posicao}]")
            if texto:
                achados.append(texto)
        return achados

    def _texto_ou_vazio(self, seletor):
        try:
            return " ".join(str(self.engine.texto(seletor) or "").split())
        except Exception:  # noqa: BLE001
            return ""

    def _existe(self, seletor):
        try:
            return bool(self.engine.element_exists(seletor))
        except Exception:  # noqa: BLE001
            return False

    def salvar_caracteristicas(self, callback_log=None):
        """Clica SALVAR na secao de caracteristicas e classifica o resultado.

        Devolve `(ok, mensagem)`. `ok` so e `True` com o toast de sucesso NOVO
        na tela -- quem garante isso e `PMIBPortal.salvar_e_confirmar`, que ja
        fotografa as mensagens de ANTES para nao reler um toast velho.

        ⚠️ A ANCORA decide QUAL botao. A ficha tem um SALVAR por secao, e sem
        ela a busca varre a tela inteira -- o defeito de 2026-08-20.

        Quando nao confirma, procura o AVISO do portal ("Por favor, verifique
        os campos"). Ele nao tem `feedback-message-autoclose`, entao fica na
        tela e da para ler com calma. Mensagem vazia quer dizer que o portal
        nao disse nada: tambem e falha, so que sem nada a mostrar para quem
        vai corrigir.
        """
        ok = self.portal.salvar_e_confirmar(
            NOME_DA_SECAO_DE_CARACTERISTICAS, callback_log,
            ancora=XPATH_SECAO_DE_CARACTERISTICAS)
        if ok:
            sucessos = [m for m in self.portal._mensagens_de_feedback(so_sucesso=True) if m]
            return True, " ".join(sucessos[-1].split()) if sucessos else ""

        # A leitura do aviso e do PORTAL, nao daqui: e a mesma mecanica de
        # percorrer toast por indice que ele ja tem. Uma copia aqui seria a
        # segunda implementacao do mesmo conceito.
        avisos = [m for m in self.portal.mensagens_de_aviso() if m]
        return False, " ".join(avisos[-1].split()) if avisos else ""

    def _preencher_linha(self, seletor_linha, dado, callback_log=None):
        """
        Preenche os campos e audita o resultado.
        Retorna True se sucesso, ou False se a inserção foi rejeitada pelo site.

        CP 5.3: recebe o SELETOR da linha em vez do elemento. Cada campo
        "dentro da linha" vira concatenação de XPath (`<linha>` + `.//input`)
        -- os MESMOS XPaths relativos de antes, só endereçados de outro jeito.
        """
        tipo = dado.get("TIPO", "")
        val_pt = dado.get("RESPOSTA_PT_FINAL", "")
        nome_campo = dado.get("CARACTERISTICA_CHAVE", "Valor")  # Pega o nome para o Log
        sucesso_auditoria = True

        def _campo(xpath_relativo):
            return seletor_linha + xpath_relativo

        # Elemento Neutro para clicar fora
        seletor_neutro = _campo(XPATH_REL_COL_DESCRICAO)
        if not self.engine.element_exists(seletor_neutro):
            seletor_neutro = None

        def _clicar_fora():
            if seletor_neutro:
                self.engine.click_raw(seletor_neutro)

        # RECUO DE TIPO (2026-08-18). O `TIPO` do JSON vem do Master; o portal
        # renderiza a linha conforme o tipo QUE ELE conhece. Os dois divergem
        # quando a ficha foi gerada numa revisão do PDM e o portal já está
        # noutra -- medido no Master do usuário: 8 características do
        # PDM.4820.015 trocaram de tipo entre r0 e r1.
        #
        # ⚠️ O JSON CONTINUA MANDANDO enquanto o campo dele existir na linha.
        # A primeira versão disto deixava a tela SOBREPOR o JSON, e derrubou 5
        # testes: numa linha que oferece mais de um tipo de campo, "o que a
        # tela tem" não identifica o campo certo -- só "o que a tela NÃO tem"
        # identifica. Por isso o recuo só acontece quando o campo do tipo
        # declarado está ausente, que é exatamente o caso que antes virava
        # exceção, "[Erro Estrutural]" e campo em branco no portal.
        if tipo and not self._linha_oferece(seletor_linha, tipo):
            alternativo = self._tipo_da_linha(seletor_linha)
            if alternativo and alternativo != tipo:
                if callback_log:
                    callback_log(f"   [Tipo] '{nome_campo}': o JSON diz {tipo} e a linha não "
                                 f"tem esse campo; a tela oferece {alternativo}. Recuando.")
                if alternativo == "CHAR":
                    # "Juntar as duas informações e colocar em CHAR e
                    # selecionar a unidade como adimensional" -- pedido do
                    # usuário. `AD` é aceito em 99,8% das linhas do Master.
                    dado = dict(dado)
                    dado["RESPOSTA_ES_FINAL"] = juntar_para_char(
                        {**dado, "RESPOSTA_PT_FINAL": dado.get("RESPOSTA_ES_FINAL", "")})
                    dado["RESPOSTA_PT_FINAL"] = juntar_para_char(dado)
                    dado["SIMBOLO"] = "AD"
                    val_pt = dado["RESPOSTA_PT_FINAL"]
                tipo = alternativo

        try:
            if tipo == "CHAR":
                # PT (Sem auditoria pesada, campos textuais raramente dão problema)
                sel_pt = _campo(XPATH_REL_TEXTAREA_PT)
                self.engine.clear(sel_pt)
                self.safe_send_keys_elem(sel_pt, val_pt)
                _clicar_fora()

                # ES
                val_es = dado.get("RESPOSTA_ES_FINAL", "")
                sel_es = _campo(XPATH_REL_TEXTAREA_ES)
                self.engine.clear(sel_es)
                self.safe_send_keys_elem(sel_es, val_es)
                _clicar_fora()

            elif tipo == "NUM":
                sucesso_auditoria = self._preencher_input_com_auditoria(
                    _campo(XPATH_REL_INPUT_NUM), val_pt, seletor_neutro, nome_campo, callback_log
                )

            elif tipo == "LISTA":
                # A resposta ES entra como ALTERNATIVA: o `<select>` da linha é
                # um só e as opções vêm ora em PT ora em ES -- tentar as duas
                # línguas é o que resolve o "ele tenta a opção espanhol na
                # caixa de português" sem adivinhar em que idioma a tela está.
                if not self.selecionar_dropdown_lista(
                    _campo(XPATH_REL_SELECT_LISTA), val_pt,
                    alternativas=(dado.get("RESPOSTA_ES_FINAL", ""),),
                    nome_campo=nome_campo, callback_log=callback_log,
                ):
                    # Antes isto era "vamos assumir que lista não falha". Falha,
                    # e falhava calado -- a característica ficava em branco no
                    # portal, que é onde "vazio" se confunde com "não se aplica".
                    sucesso_auditoria = False
                time.sleep(PAUSA_ANIMACAO)
                _clicar_fora()

            elif tipo == "INT":
                subtipo = dado.get("SUBTIPO_INTERVALO", "MINIMO / MAXIMO")
                if not self.selecionar_dropdown_lista(
                    _campo(XPATH_REL_SELECT_INTERVALO), subtipo,
                    nome_campo=f"{nome_campo} (intervalo)", callback_log=callback_log,
                ):
                    sucesso_auditoria = False
                time.sleep(PAUSA_ANIMACAO)

                vals = val_pt.split('/')
                v1 = vals[0].strip()
                v2 = vals[1].strip() if len(vals) > 1 else ""

                s1 = self._preencher_input_com_auditoria(
                    _campo(XPATH_REL_INPUT_MIN), v1, seletor_neutro, f"{nome_campo} (Mín)", callback_log
                )
                s2 = self._preencher_input_com_auditoria(
                    _campo(XPATH_REL_INPUT_MAX), v2, seletor_neutro, f"{nome_campo} (Máx)", callback_log
                )

                # Se qualquer um dos dois (min/max) falhou, marca o item como falha
                if not s1 or not s2:
                    sucesso_auditoria = False

            # Unidade
            simb = dado.get("SIMBOLO")
            if simb:
                # Unidade errada é o defeito mais fácil de passar batido numa
                # revisão visual: o número aparece certo e só a coluna de
                # unidade denuncia. Vira pendência como qualquer outra falha.
                if not self.selecionar_dropdown_unidade(
                    _campo(XPATH_REL_SELECT_UNIDADE), simb,
                    nome_campo=nome_campo, callback_log=callback_log,
                ):
                    sucesso_auditoria = False

        except Exception:
            # Avisa no log que o tipo esperado pelo JSON não bateu com a tela real
            if callback_log:
                callback_log(f"   [Erro Estrutural] Não foi possível preencher '{nome_campo}' como {tipo}. O campo na tela é diferente.")
            return False

        return sucesso_auditoria


# =============================================================================
# CLASSE 3: CONTROLADOR / ORQUESTRADOR (A Ponte com o Frontend customtkinter)
# =============================================================================
class TechSpecsController:
    def __init__(self):
        # Armazena o estado atual dos dados processados para fácil acesso
        self.dados_em_memoria = []
        self.processor_ativo = None   # Referência ao processo de IA atual
        self.automacao_ativa = None   # Referência ao processo Web atual

    def cancelar_processo_ia(self):
        """Sinaliza parada para a IA"""
        if self.processor_ativo:
            self.processor_ativo.solicitar_parada()

    def cancelar_processo_web(self):
        """Sinaliza parada para o Selenium"""
        if self.automacao_ativa:
            self.automacao_ativa.solicitar_parada()

    def executar_pipeline_ia(self, api_key, lista_arquivos, path_status, path_master, processar_completos=False, callback_log=None):
        """Aciona o motor de IA e retorna os dados tratados."""
        if callback_log: callback_log("Iniciando motor de IA...")

        self.processor_ativo = TechSpecsProcessor(api_key)
        resultados = self.processor_ativo.preparar_dados_ia(
            lista_arquivos,
            path_status,
            path_master,
            processar_completos,
            callback_log
        )

        self.dados_em_memoria = resultados
        self.processor_ativo = None  # Limpa a referência ao terminar
        return resultados

    def salvar_json(self, dados, caminho_arquivo, modo_anexar=False, callback_log=None):
        """Grava os resultados no disco, imitando a funcionalidade de criar/anexar do Script 1."""
        if not dados:
            if callback_log: callback_log("Nenhum dado novo para salvar.")
            return False

        dados_finais = dados
        if modo_anexar and os.path.exists(caminho_arquivo):
            try:
                with open(caminho_arquivo, 'r', encoding='utf-8') as f:
                    dados_antigos = json.load(f)
                    if isinstance(dados_antigos, list):
                        dados_finais = dados_antigos + dados
            except Exception as e:
                if callback_log: callback_log(f"Erro ao ler JSON existente para anexar: {e}")
                return False

        try:
            with open(caminho_arquivo, 'w', encoding='utf-8') as f:
                json.dump(dados_finais, f, ensure_ascii=False, indent=4)
            if callback_log: callback_log(f"Arquivo salvo com sucesso em: {caminho_arquivo}")
            return True
        except Exception as e:
            if callback_log: callback_log(f"Erro ao salvar JSON: {e}")
            return False

    def executar_pipeline_rpa(self, dados_json, caminho_status="", callback_log=None, callback_pause=None):
        """Aciona o Selenium para preencher o site e atualiza o Excel de Status."""
        if not dados_json:
            if callback_log: callback_log("Erro: Lista de dados vazia. Nada para processar no RPA.")
            return False

        self.automacao_ativa = TechSpecsAutomation()
        try:
            if callback_log: callback_log("Iniciando navegador...")
            self.automacao_ativa.iniciar()

            # Abre a tela inicial exigida
            self.automacao_ativa.abrir_portal("https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList")

            # Pausa para o usuário fazer o login manual
            if callback_pause:
                callback_pause("LOGIN_NECESSARIO")

            # Inicia o loop de preenchimento e recebe os PMIBs que foram finalizados
            pmibs_finalizados = self.automacao_ativa.processar_lista(dados_json, callback_log, callback_pause)

            # --- ATUALIZAÇÃO DO FICHEIRO DE STATUS ---
            # CP 1.3: cabeçalho/linha/marcação delegam para
            # `core.excel.status_sheet.StatusPMIB` (única implementação,
            # compartilhada com `upload_conditions`/`upload_ficha_duplicada`
            # -- ver docs/refatoracao/PLANO_REFATORACAO.md Fase 1 -> CP 1.3).
            # `save_with_retry` dá a este bloco a PRIMEIRA retentativa de
            # `PermissionError` que ele já teve: o original não tratava
            # arquivo aberto (caía direto no `except Exception` genérico
            # abaixo, sem tentar de novo). `max_attempts`/`sleep_seconds`
            # finitos evitam travar o robô para sempre se o usuário nunca
            # fechar o Excel (não há callback interativo disponível aqui).
            if caminho_status and pmibs_finalizados:
                try:
                    if callback_log: callback_log("A atualizar ficheiro _STATUS_PMIB...")
                    # Abre mantendo formatações e fórmulas (importante para
                    # não corromper o Master) -- mesmo `openpyxl.load_workbook`
                    # sem `data_only`, agora dentro de `StatusPMIB.abrir()`.
                    painel = status_sheet.StatusPMIB(caminho_status, config.ABA_LISTA_MATERIAIS)
                    painel.abrir(
                        keywords={
                            config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB,
                            config.COL_CARACT_TECNICAS: config.COL_CARACT_TECNICAS,
                        },
                        max_row=15,
                    )

                    if painel.header_row is not None:
                        # 2. Marcar cada PMIB concluído (só a 1ª ocorrência
                        #    de cada um, igual ao original).
                        for pmib in pmibs_finalizados:
                            linha = painel.buscar_linha(pmib)
                            if linha is not None:
                                painel.marcar_linha(linha, [config.COL_CARACT_TECNICAS])
                                if callback_log: callback_log(f"   -> {pmib} marcado como COMPLETO.")

                        painel.salvar(max_attempts=3, sleep_seconds=5, logger=callback_log)
                        if callback_log: callback_log("✅ Ficheiro _STATUS_PMIB salvo com sucesso!")
                    else:
                        if callback_log: callback_log("Aviso: Não encontrei as colunas 'CÓDIGO PMIB' ou 'CARACT. TÉCNICAS' para atualizar.")

                    painel.fechar()
                except Exception as ex:
                    if callback_log: callback_log(f"Erro ao tentar escrever no Excel de status: {ex}")

        except Exception as e:
            if callback_log: callback_log(f"Erro fatal na automação: {e}")
        finally:
            if callback_log: callback_log("Fim do processo de RPA.")
            self.automacao_ativa = None  # Limpa a referência ao terminar
