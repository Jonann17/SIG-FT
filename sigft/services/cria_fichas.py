import re
import time

import pandas as pd
import openpyxl

from sigft import config
from sigft.core.excel import headers, locking
# CP 3.1 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 3): `google.generativeai`
# deixou de ser importado aqui -- `GeminiCategorizer.processar_lote` abaixo
# delega para `LLMClient`/`GeminiProvider` (ÚNICO lugar do projeto que
# importa `genai`).
from sigft.core.llm.client import get_llm
# CP 3.5 (Fase 3): o TEXTO do prompt de `processar_lote` abaixo mora em
# `sigft.core.llm.prompts.montar_categorizar_pdm` -- só o pré-processamento
# (`_formatar_itens`) continua aqui.
from sigft.core.llm import prompts
# CP 2.1 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 2): fábrica única de
# driver Chrome, substitui `webdriver.Chrome()` cru em
# `AutomacaoPMIB.iniciar_driver` abaixo.
# CP 5.2 (Fase 5): `atualizar_projeto_em_massa` migrado para as primitivas de
# `RPAEngine`; quem escolhe o motor é `config.RPA_ENGINE["cria_fichas"]`.
# `processar_item_individual` (fluxo por TAB/`active_element`) segue em
# Selenium cru -- é o CP 5.4, que exige os seletores confirmados com o usuário
# na tela real. Enquanto isso, `self.driver`/`self.wait` continuam existindo
# quando o motor é o Selenium.
from sigft.core.rpa.factory import criar_engine
# CP 2.2 (Fase 2): `self.portal` passa a existir por consistência estrutural
# com os outros 5 backends (`AutomacaoPMIB` é uma das "6 classes de
# automação" do aceite do checkpoint), mas NENHUM call site desta classe foi
# migrado -- `AutomacaoPMIB` não tem `safe_click`/`safe_send_keys`/
# `check_or_uncheck` (não é um dos 4 arquivos do diagnóstico que os têm) e
# `atualizar_projeto_em_massa` tem uma 6ª variante de "pesquisar + clicar no
# lápis" com seletores NÃO cobertos pelo levantamento deste checkpoint
# (busca só por `contains(@id, 'InputDatasheetFilter')`, lápis por substring
# de linha inteira + classe de ícone `fa-pencil-square-o`) -- migrar isso
# exigiria autorizar um seletor não revisado, fora do escopo conservador
# deste checkpoint; ver docs/refatoracao/PENDENCIAS.md.
#
# CP 2.3 (Fase 2): os 25 `time.sleep(<literal>)` do arquivo (o "TAB dance"
# de `processar_item_individual` e os sleeps de
# `atualizar_projeto_em_massa`) viram constantes nomeadas (nenhum
# eliminado) -- ver docs/refatoracao/PLANO_REFATORACAO.md Fase 2 -> CP 2.3.
from sigft.core.rpa.portal import (
    PMIBPortal,
    PAUSA_ABERTURA_FICHA,
    PAUSA_ANIMACAO,
    PAUSA_CARGA_LISTA,
    PAUSA_FILTRO_PDM,
    PAUSA_FOCO,
    PAUSA_GERACAO_PMIB,
    PAUSA_INICIO_ITEM,
    PAUSA_MUDANCA_FOCO,
    PAUSA_SALVAMENTO_FINAL,
)


class DataManager:
    @staticmethod
    def carregar_planilha_inteligente(arquivo, nome_da_aba, colunas_desejadas):
        try:
            # Aumentado para 30 para maior segurança
            df_preview = pd.read_excel(arquivo, sheet_name=nome_da_aba, header=None, nrows=30)

            # CP 1.2: busca dinâmica da linha de cabeçalho via
            # core.excel.headers (mesmo alcance do original: até as 30
            # linhas de df_preview, exige TODAS as colunas_desejadas na
            # mesma linha).
            header_row_index = headers.find_header_row(df_preview.values.tolist(), list(colunas_desejadas))
            if header_row_index is None:
                return None, "", "Colunas não encontradas."

            codigo_projeto_sugerido = ""  # Variável para guardar o código

            # --- Lógica de Auto-Preenchimento do Código do Projeto ---
            if header_row_index > 0:  # Só podemos olhar pra cima se a linha do cabeçalho não for a primeiríssima (0)
                for col_idx in range(len(df_preview.columns)):
                    cell_value = str(df_preview.iloc[header_row_index, col_idx]).strip().upper()
                    if cell_value == "ITEM":
                        # Pega a célula da MESMA coluna, mas 1 linha acima
                        valor_acima = df_preview.iloc[header_row_index - 1, col_idx]
                        if pd.notna(valor_acima):
                            codigo_projeto_sugerido = str(valor_acima).strip()
                        break  # Achou a coluna ITEM, não precisa olhar o resto das colunas

            df_final = pd.read_excel(arquivo, sheet_name=nome_da_aba, header=header_row_index, dtype=str)
            # Garante que as colunas sejam strings (evita erro de .strip() em colunas sem nome)
            df_final.columns = df_final.columns.astype(str).str.strip()

            return df_final, codigo_projeto_sugerido, None  # Retorna os 3 valores
        except Exception as e:
            return None, "", str(e)

    @staticmethod
    def atualizar_excel_final(filepath, nome_aba, lista_resultados):
        try:
            wb = openpyxl.load_workbook(filepath)

            if nome_aba in wb.sheetnames:
                ws = wb[nome_aba]
            else:
                ws = wb.active

            # CP 1.2: busca dinâmica de cabeçalho via core.excel.headers
            # (mesmo alcance do original: até as 20 primeiras linhas).
            # "PDM USADO" e "PDM" são grafias alternativas para a MESMA
            # coluna de saída "PDM usado" (mantida com essa grafia mista,
            # igual ao original).
            keywords = {
                config.COL_DESCRICAO: config.COL_DESCRICAO,
                config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB,
                config.COL_PDM_USADO: ["PDM USADO", "PDM"],
            }
            rows = headers.rows_from_worksheet(ws, max_row=20)
            col_map, header_row = headers.find_columns(rows, keywords)

            if header_row is None:
                return False, "Erro: Colunas não encontradas no Excel."

            linhas_atualizadas = 0
            for desc_original, pmib_criado, pdm_revisao in lista_resultados:
                desc_search = str(desc_original).strip()

                for row_num in range(header_row + 1, ws.max_row + 1):
                    cell_desc = ws.cell(row=row_num, column=col_map[config.COL_DESCRICAO]).value

                    if cell_desc and str(cell_desc).strip() == desc_search:
                        ws.cell(row=row_num, column=col_map[config.COL_CODIGO_PMIB]).value = pmib_criado
                        ws.cell(row=row_num, column=col_map[config.COL_PDM_USADO]).value = pdm_revisao
                        linhas_atualizadas += 1
                        break

            # CP 1.3: delega o retry de PermissionError para
            # locking.save_with_retry (única implementação). `max_attempts=1`
            # preserva o comportamento ORIGINAL desta variante (log + sai):
            # nenhuma retentativa, aborta na 1ª PermissionError (relevantada
            # e capturada pelo `except` abaixo, exatamente como antes).
            locking.save_with_retry(wb, filepath, max_attempts=1)
            return True, f"{linhas_atualizadas} linhas atualizadas."

        except PermissionError:
            return False, "Erro: O arquivo Excel está ABERTO."
        except Exception as e:
            return False, f"Erro ao salvar: {e}"


# =============================================================================
# Guardas da escolha de PDM (2026-09-22)
# =============================================================================
# Quantos itens por chamada de IA. O lote inteiro ia numa chamada só, com
# `max_retries=0` (política de `categorizar_pdm`) -- uma falha de API derrubava
# os 40 itens juntos, e o prompt crescia sem teto junto com a seleção.
# Fatiar dá dois ganhos: a falha fica contida num bloco, e o bloco que falha
# pode ser repetido sem repetir o que já deu certo.
ITENS_POR_BLOCO = 15

# O que a IA responde quando nenhum PDM serve. `processar_item_individual`
# trata como PULAR -- é resposta legítima, não erro.
PDM_NENHUM = "NENHUM"


_RE_CODIGO_PDM = re.compile(r"PDM\.\d{4}\.\d{3}")


def tentativas_de_busca(pdm):
    """As buscas a tentar no combo de PDM do portal, da melhor para a última.

        1. `PDM.6120.003 - TRANSFORMADOR POTENCIA`  (o que funciona hoje)
        2. `PDM.6120.003`                           (só o código)
        3. `TRANSFORMADOR POTENCIA`                 (só o título)

    Pedido do usuário em 2026-09-22. A ordem não é arbitrária:

    - o **completo** é o que já funciona na esmagadora maioria dos itens, e
      continua sendo o primeiro -- a cascata é rede, não substituição;
    - o **código** é a parte estável da string: imune a acento (5 PDMs do
      Master têm), a espaço duplo (18 têm) e a mudança de título entre
      revisões (179 têm). Quando o completo falha, é quase sempre por causa
      do título;
    - o **título** cobre o caso oposto: o portal indexar pelo nome e não pelo
      código.

    Partir no PRIMEIRO " - " e não no primeiro hífen é o que preserva
    `MOTO-VENTILADOR`; partir no hífen daria o título "MOTO".

    Sem duplicata: repetir a mesma busca gasta uma rodada no portal e não
    descobre nada.
    """
    texto = str(pdm or "").strip()
    if not texto:
        return []

    tentativas = [texto]
    achado = _RE_CODIGO_PDM.search(texto.upper())
    if achado:
        codigo = achado.group(0)
        titulo = texto[achado.end():].lstrip(" -").strip()
        for candidata in (codigo, titulo):
            if candidata and candidata not in tentativas:
                tentativas.append(candidata)
    return tentativas


def codigo_do_pdm(texto):
    """Só o código (`PDM.4820.004`) de uma string de PDM, ou `""`.

    Serve para comparar o PDM PEDIDO com o que o portal GRAVOU: o valor que
    volta do portal é o `data-tooltip` do combo, que traz a revisão junto, e
    portanto nunca é igual caractere a caractere ao que foi digitado. O código
    é a parte estável dos dois lados."""
    achado = _RE_CODIGO_PDM.search(str(texto or "").upper())
    return achado.group(0) if achado else ""


def alinhar_resposta(res_json, total):
    """Casa a resposta da IA com os itens do lote PELO `item_processado`.

    Devolve uma lista de `total` posições, com `None` onde a IA não respondeu.

    Antes isto era `res_json[i]` -> `df.iloc[i]`, casamento por POSIÇÃO. Se a
    IA pulasse ou reordenasse um item, toda linha seguinte recebia o PDM de
    OUTRO material -- e nada no fluxo denunciava: a planilha saía preenchida,
    com PDMs plausíveis, nos materiais errados.

    O fallback para a ordem existe para um modelo que ignore a instrução: sem
    NENHUM `item_processado` utilizável, a ordem é o melhor palpite -- o mesmo
    comportamento de antes, agora como último recurso em vez de único caminho.
    """
    alinhado = [None] * total
    # "numerou" e "numerou DENTRO da faixa" são coisas diferentes, e confundi-las
    # era um bug: um `item_processado: 99` num lote de 2 é numeração errada, não
    # ausência de numeração -- cair na ordem ali seria adivinhar. O fallback só
    # vale quando NENHUM item trouxe número utilizável.
    algum_numero_presente = False

    for item in res_json or []:
        if not isinstance(item, dict):
            continue
        try:
            numero = int(item.get("item_processado"))
        except (TypeError, ValueError):
            continue
        algum_numero_presente = True
        if 1 <= numero <= total:
            alinhado[numero - 1] = item

    if not algum_numero_presente:
        for i, item in enumerate(res_json or []):
            if i < total and isinstance(item, dict):
                alinhado[i] = item

    return alinhado


def conferir_pdm(item, catalogo):
    """O PDM escolhido existe no catálogo? Devolve `(ok, motivo)`.

    Quando o código está certo e só o título divergiu (a vírgula de
    "CABO, TRANSMISSAO DADOS", que o prompt antigo ensinava), **canoniza** o
    valor dentro do próprio `item` em vez de reprovar: a string vai ser
    DIGITADA no filtro de PDM do portal, e é a vírgula que não casaria lá.

    Sem esta guarda, um código inventado pela IA atravessava a revisão humana
    (um `askstring` de texto livre) e chegava ao portal, que filtra e aperta
    ENTER -- levando o que estivesse destacado.

    `catalogo=None` não reprova nada: é o modo "Pular IA", em que o PDM vem da
    planilha e não há com o que comparar.
    """
    escolhido = (item or {}).get("pdm_escolhido")
    escolhido = str(escolhido).strip() if escolhido is not None else ""

    if not escolhido:
        return False, "a IA nao devolveu 'pdm_escolhido' para este item"
    if escolhido.upper() == PDM_NENHUM:
        return True, ""
    if catalogo is None:
        return True, ""

    if catalogo.contem(escolhido):
        return True, ""

    canonico = catalogo.resolver(escolhido)
    if canonico is not None:
        item["pdm_escolhido"] = canonico.completo
        return True, ""

    return False, f"PDM fora do catalogo: {escolhido!r}"


class GeminiCategorizer:
    def __init__(self, api_key):
        self.api_key = api_key
        # CP 3.1: genai.configure(...) sai daqui -- agora vive dentro de
        # GeminiProvider (chamado por get_llm), com o MESMO guard ("só
        # configura se api_key for truthy"). O aviso em stdout continua
        # (é só um print, não chama genai) -- mesmo comportamento
        # observável de hoje quando a chave está ausente.
        self._llm = get_llm("categorizar_pdm", api_key)
        if not self.api_key:
            print("AVISO: Nenhuma API Key fornecida.")

    @property
    def modelo_em_uso(self) -> str:
        """`provider/model` REALMENTE resolvido para esta execução, no
        formato de uma linha de log.

        Existe porque a UI escrevia "Processando com IA (Gemini)..." fixo no
        console -- e desde o CP 3.3 o modelo vem do painel "Modelos de IA"
        da Home, que pode apontar para OpenRouter ou para o endpoint interno
        da empresa. O usuário rodou um lote inteiro no MiniMax lendo
        "Gemini" na tela; a única forma de descobrir o que de fato rodou era
        abrir `logs/llm_usage.jsonl` depois. Quem sabe a resposta é o
        `LLMClient` já construído -- perguntar a ele é o que garante que o
        log não pode divergir da chamada."""
        return f"{self._llm.provider_name}/{self._llm.model}"

    def _formatar_itens(self, df, catalogo=None):
        """O bloco `### ITEM N` de cada item do lote.

        Duas mudanças de 2026-09-22:

        1. A numeração passou a ser **1..N dentro do lote**, com `enumerate`.
           Era `index + 1` com o índice ORIGINAL da planilha -- e a seleção não
           fazia `reset_index`, então selecionar as linhas 50-52 produzia
           "### ITEM 51/52/53" enquanto o contrato de JSON pedia 1, 2, 3. O
           número agora é a CHAVE de casamento da resposta (`alinhar_resposta`),
           então ele tem que ser o mesmo dos dois lados.
        2. Cada item leva seus **candidatos pré-filtrados**, com a classe FSC e
           as características de cada um -- o sinal que existia na planilha e
           nunca chegava à IA.
        """
        texto = ""
        for posicao, (_indice, row) in enumerate(df.iterrows(), start=1):
            descricao = row['DESCRIÇÃO']
            texto += f"\n### ITEM {posicao}\n"
            texto += f"- Descrição: {descricao}\n"
            texto += f"- Marca/Modelo: {row['MARCA/MODELO']}\n"
            cod_mat = str(row['CÓDIGO DO MATERIAL']).strip() if pd.notna(row['CÓDIGO DO MATERIAL']) else ""
            texto += f"- Código do Material: {cod_mat}\n"

            # Checa se o campo é vazio (ou string vazia criada pelo fillna) e trata corretamente
            unidade_raw = row.get('UNID.', '')
            unidade_final = "NÃO ESPECIFICADA" if not unidade_raw or pd.isna(unidade_raw) else unidade_raw
            texto += f"- Unidade: {unidade_final}\n"

            if catalogo is not None:
                texto += self._bloco_de_candidatos(descricao, row, catalogo)
        return texto

    @staticmethod
    def _bloco_de_candidatos(descricao, row, catalogo):
        """Os candidatos de UM item. A marca entra na consulta junto com a
        descrição: em muitas linhas o substantivo do equipamento está só na
        coluna MARCA/MODELO."""
        consulta = f"{descricao} {row.get('MARCA/MODELO', '') or ''}"
        candidatos = catalogo.candidatos(consulta)
        if not candidatos:
            # Dizer que não há candidato é informação, não ruído: sem esta
            # linha o modelo poderia ler a ausência da seção como "a lista de
            # candidatos é a lista completa". Medido contra o arquivo real,
            # descrições como "IE4010 w/ 12GE SFP uplink ports" não têm
            # nenhuma palavra que nomeie o equipamento.
            return ("- CANDIDATOS: nenhum candidato foi pré-selecionado para "
                    "este item. Procure na LISTA DE PDMS POR CLASSE.\n")
        return "- CANDIDATOS (pré-selecionados por semelhança):\n" + \
            catalogo.bloco_de_candidatos(candidatos) + "\n"

    def processar_lote(self, df_itens, catalogo, callback_log=None):
        """Classifica o lote inteiro, em blocos de `ITENS_POR_BLOCO`.

        Devolve uma lista com UM objeto por item do lote, na ordem do lote --
        `None` nas posições que a IA não respondeu (ver `alinhar_resposta`).

        MUDOU EM 2026-09-22 (era `processar_lote(df_itens, lista_pdms, instrucoes)`):

        - recebe o **catálogo** em vez de duas strings já montadas. Quem
          montava o manual de regras era a VIEW, num laço de ~20 linhas --
          regra de negócio dentro da UI, contra o princípio 2 do `CLAUDE.md`.
          Agora o manual sai de `CatalogoPDM.manual_de_regras`, podado às
          classes que realmente aparecem nos candidatos do bloco;
        - **fatia o lote**. Antes tudo ia numa chamada com `max_retries=0`:
          uma falha de API derrubava os 40 itens juntos.
        """
        # CP 3.1: `model = genai.GenerativeModel(...)` sai daqui -- a
        # resolução de modelo/provider agora é responsabilidade de
        # `self._llm` (`get_llm("categorizar_pdm", ...)`, ver `__init__`).
        if not self.api_key: raise ValueError("API Key não configurada.")

        blocos = _fatiar(list(df_itens.iterrows()), ITENS_POR_BLOCO)
        resultado = []
        for numero_do_bloco, bloco in enumerate(blocos, start=1):
            if callback_log and len(blocos) > 1:
                callback_log(
                    f"IA: bloco {numero_do_bloco}/{len(blocos)} "
                    f"({len(bloco)} itens)"
                )
            resultado.extend(
                self._processar_bloco(_DataFrameDeBloco(bloco), catalogo)
            )
        return resultado

    def _processar_bloco(self, df_bloco, catalogo):
        itens_texto = self._formatar_itens(df_bloco, catalogo=catalogo)

        if catalogo is not None:
            lista_pdms = catalogo.lista_por_classe()
            instrucoes = catalogo.manual_de_regras(
                self._classes_relevantes(df_bloco, catalogo)
            )
        else:
            lista_pdms = ""
            instrucoes = ""

        # CP 3.5 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 3): o TEXTO do
        # prompt (antes embutido aqui como f-string gigante) agora mora em
        # `sigft.core.llm.prompts.montar_categorizar_pdm` -- só o
        # pré-processamento acima (`_formatar_itens`) continua neste método.
        prompt_template = prompts.montar_categorizar_pdm(instrucoes, lista_pdms, itens_texto)
        # CP 3.1: SEM retry (política de `categorizar_pdm`: `max_retries=0`,
        # 1 tentativa só -- mesmo comportamento de hoje) e limpeza/parse do
        # JSON delegados a `LLMClient.generate()` (`_limpar_e_parsear_json`,
        # que substitui a busca de `[`...`]` + fallback frágil de slice
        # deste método). Preserva o `raise Exception(f"Erro na IA: {e}")`
        # (wrapping) em qualquer falha, exatamente como hoje.
        try:
            resp = self._llm.generate(
                prompt_template,
                tags={"modulo": "cria_fichas_no_pmib_v1_backend", "tarefa": "categorizar_pdm"},
            )
        except Exception as e:
            # `from e` mantem o traceback ORIGINAL encadeado. Sem ele, o
            # erro de verdade (timeout, chave invalida, resposta malformada)
            # some, e sobra so a string -- que e o que chega no console do
            # usuario quando a IA falha.
            raise Exception(f"Erro na IA: {e}") from e

        return alinhar_resposta(resp.parsed_json, total=len(df_bloco))

    @staticmethod
    def _classes_relevantes(df_bloco, catalogo):
        """As classes FSC que aparecem entre os candidatos deste bloco.

        É o que permite mandar o manual de regras PODADO: o manual inteiro
        custa ~11 mil tokens (124 classes), e um bloco toca uma fração disso.
        A lista de PDMs por classe continua completa -- ela é a rede."""
        classes = set()
        for _indice, row in df_bloco.iterrows():
            consulta = f"{row['DESCRIÇÃO']} {row.get('MARCA/MODELO', '') or ''}"
            for candidato in catalogo.candidatos(consulta):
                classes.add(candidato.classe)
        return classes


def _fatiar(itens, tamanho):
    return [itens[i:i + tamanho] for i in range(0, len(itens), tamanho)] or [[]]


class _DataFrameDeBloco:
    """O mínimo de `DataFrame` que `_formatar_itens` usa (`iterrows`/`len`).

    Existe para o fatiamento não depender de `df.iloc[a:b]`: o `df_itens` que
    chega aqui vem de `iloc[indices].copy()` na view, e fatiar por posição
    sobre um índice não reiniciado é exatamente o tipo de sutileza que causou
    o bug de numeração que este checkpoint conserta."""

    def __init__(self, pares):
        self._pares = pares

    def iterrows(self):
        return iter(self._pares)

    def __len__(self):
        return len(self._pares)


# =============================================================================
# CP 5.2 (Fase 5) — seletores XPath de `atualizar_projeto_em_massa`.
# Ver a nota equivalente em `services/lmr.py`: as primitivas de `RPAEngine`
# recebem seletor, não elemento, então cada XPath aparece 2x (esperar/agir) --
# com o literal solto isso viraria duplicação convidando a divergência.
# Valores idênticos aos de antes, verbatim.
# =============================================================================
XPATH_BUSCA_MASSA = "//input[contains(@id, 'InputDatasheetFilter')]"
XPATH_LINHA_RESULTADO = "//tr[contains(., '{pmib}')]"
XPATH_LAPIS_MASSA = "//tr[contains(., '{pmib}')]//a[.//i[contains(@class, 'fa-pencil-square-o')]]"
XPATH_CAMPO_PROJETO = '//*[@id="b10-b9-TextArea_ProjectCode"]'
XPATH_SALVAR_PROJETO = '//*[@id="b10-b9-Form1"]/div[6]/button[1]'

# CP 5.4 — seletores do fluxo de criação de ficha individual.
XPATH_BOTAO_NOVA_FICHA = '//*[@id="b1-Actions"]/button'
XPATH_DIV_PESQUISAR_PDM = '//div[@data-tooltip="Pesquisar PDM"]'
XPATH_DROPDOWN_CONTRATO = '//*[@id="b10-ContractDropdownSearch"]'
XPATH_SALVAR_1 = '//*[@id="b10-b7-Button"]/button'
XPATH_CODIGO_PMIB = '//*[@id="b8-b1-Content"]/span'

# Marcador de validação do OutSystems ("Campo obrigatório!" em vermelho embaixo
# do campo em branco). NÃO é um seletor de fluxo -- nada é clicado nem lido a
# partir dele; serve só para transformar uma falha MUDA em uma frase.
#
# Quando o Salvar é recusado, o portal não navega: o Código PMIB nunca aparece,
# o `wait_visible` estoura e o usuário recebe `ERRO no Selenium: Message:` --
# um `TimeoutException` do Selenium tem a mensagem VAZIA, então a tela do app
# não diz absolutamente nada sobre o que houve. Foi exatamente o que aconteceu
# no 1º teste real (2026-08-11), e custou uma sessão inteira de diagnóstico
# para descobrir que o campo em branco era o Contrato.
#
# `text()` casa só o nó de texto direto; `contains(., ...)` casaria também
# qualquer ancestral (inclusive o `<body>`), o que daria "campo obrigatório"
# como resposta para toda ficha. Sem acento no fim ("obrigatóri") para não
# depender de "obrigatório!"/"obrigatória"/"obrigatorio".
XPATH_CAMPO_OBRIGATORIO = "//*[contains(text(), 'obrigat')]"

# ÚNICO seletor CSS que restava no projeto (levantado já no CP 2.1: "139 dos
# 140 usos de `By.*` são XPATH"). Traduzido para XPath aqui, porque o contrato
# de `RPAEngine` é só XPath. Equivalência: `div.vscomp-value[data-tooltip^=
# 'PDM']` -> div com a classe na lista de classes E tooltip começando por PDM.
# O `concat(' ', @class, ' ')` é o jeito canônico de casar UMA classe em XPath
# sem pegar `vscomp-value-outra` por engano.
XPATH_PDM_FINAL = (
    "//div[contains(concat(' ', normalize-space(@class), ' '), ' vscomp-value ')"
    " and starts-with(@data-tooltip, 'PDM')]"
)

# "PDM não encontrado" -- o ÚNICO sinal de que o filtro do combo não achou nada.
#
# HTML, colado da tela pelo usuário em 2026-09-22:
#
#     <div class="vscomp-no-search-results" tabindex="0"
#          aria-hidden="false">PDM não encontrado</div>
#
# É a regra 6 de docs/PORTAL_COMO_ELE_SE_COMPORTA.md em estado puro ("recusa
# muitas vezes é silenciosa; às vezes o único sinal é um elemento aparecer ou
# sumir"). Sem ele, o fluxo digitava, esperava um segundo e apertava ENTER no
# vazio -- e a automação quebrava três passos adiante, com o PDM CERTO já
# escolhido.
#
# Duas decisões de seletor, e o porquê de cada uma:
#
# 1. `@aria-hidden='false'`, e NÃO a mera existência do nó. O widget `vscomp`
#    esconde em vez de remover -- é a mesma armadilha já documentada na §2 do
#    doc do portal e em `seletores_duplicada.py` (contar opção devolve 10 com o
#    dropdown fechado). Testar só a presença daria "não encontrado" sempre, e a
#    cascata gastaria as três tentativas em todo item.
#
# 2. NÃO casa o texto "PDM não encontrado". A tela do PMIB alterna PT/ES e a
#    redação em espanhol é desconhecida -- o mesmo motivo que deixou
#    `PALAVRA_DA_SECAO` em PENDENCIAS. Seletor que depende de texto não
#    traduzido falha em SILÊNCIO, que é justamente o defeito que este veio
#    consertar. A classe basta: neste ponto do fluxo o único combo aberto é o
#    do PDM, porque o passo anterior acabou de clicar nele.
XPATH_PDM_NAO_ENCONTRADO = (
    "//div[contains(concat(' ', normalize-space(@class), ' '),"
    " ' vscomp-no-search-results ') and @aria-hidden='false']"
)


def _teclas_da_unidade(unidade):
    """Texto a digitar no combo de unidade -- extraído do meio do fluxo para
    ficar testável sem browser nenhum. Mesmas equivalências de antes."""
    u_l = unidade.lower() if unidade else "unidade"
    if u_l in ('peça', 'pç', 'peca'):
        return "pç"
    if u_l in ('metro', 'm'):
        return 'metro - (m)'
    if u_l in ('litro', 'l'):
        return 'litro - (l)'
    if u_l in ('conjunto', 'cj'):
        return 'cj'
    return "un"


class AutomacaoPMIB:
    def __init__(self):
        self.engine = None
        self.portal = None

    def iniciar_driver(self):
        """CP 2.1: a criação em si (Chrome + maximize + WebDriverWait(10s))
        agora vem de `create_chrome_driver` (única fábrica, ver
        core/rpa/selenium_engine.py) — timeout preservado EXATAMENTE como
        antes (10s, o único dos 6 pontos originais com esse valor).

        CP 2.2: logo em seguida, `self.portal` passa a existir (`PMIBPortal`
        sobre o engine).

        CP 5.2: quem escolhe o motor agora é `criar_engine`, por
        `config.RPA_ENGINE["cria_fichas"]`. Timeout de 10s preservado.

        CP 5.4: `processar_item_individual` foi portado, então `self.driver`/
        `self.wait` deixaram de existir -- o módulo inteiro roda nos dois
        motores e a guarda que avisava sobre isso saiu junto.
        """
        self.engine = criar_engine("cria_fichas", wait_timeout=10)
        self.portal = PMIBPortal(self.engine)
        return self.engine

    def abrir_portal(self, url):
        url_limpa = str(url).strip()
        if not url_limpa.lower().startswith("http"):
            url_limpa = "https://" + url_limpa
        self.engine.goto(url_limpa)

    def _buscar_pdm(self, pdm):
        """Digita as variações do PDM no combo até o portal achar alguma.

        Devolve o texto que funcionou, ou `None` se as três falharem.

        Pressupõe o combo JÁ ABERTO e com o foco na caixa de busca -- é o
        estado que o clique em `XPATH_DIV_PESQUISAR_PDM` deixa, logo acima.

        O QUE MUDOU, E POR QUÊ (2026-09-22, pedido do usuário)
        --------------------------------------------------------------
        Antes: `digitar_no_foco(pdm)` -> `sleep` -> `ENTER`, sem nunca
        perguntar se o filtro achou algo. Quando o texto não casava, o ENTER
        caía no vazio e a automação quebrava três passos adiante -- com o PDM
        CERTO já escolhido, que é o que torna esse erro tão caro de
        diagnosticar.

        Agora cada tentativa é CONFERIDA contra `XPATH_PDM_NAO_ENCONTRADO`
        antes do ENTER. `esta_visivel` e não `element_exists`: o widget
        `vscomp` esconde em vez de remover.

        Por que BACKSPACE e não Ctrl+A: `RPAEngine.press` só aceita teclas
        NOMEADAS (o mapa de teclas de cada motor tem ENTER, TAB, BACKSPACE...
        e nenhum combinador). E `fill`/`clear` pedem um seletor,
        que aqui não existe -- a caixa de busca do `vscomp` tem id gerado, e
        identificá-la pelo placeholder é a armadilha documentada na §4 do doc
        do portal (a do PDM diz só "Pesquisar", igual à do contrato; um
        seletor genérico escreve na caixa de OUTRO widget, escondida). O foco
        já está no lugar certo: BACKSPACE age nele, sem seletor nenhum.

        ⚠️ Esta função NÃO foi validada contra o portal real. O seletor veio
        de um HTML colado no chat, e `scripts/check.sh` verde não é prova de
        portal (CLAUDE.md). Precisa de uma execução em sessão local.
        """
        for tentativa in tentativas_de_busca(pdm):
            self.engine.digitar_no_foco(tentativa)
            time.sleep(PAUSA_FILTRO_PDM)

            if not self.engine.esta_visivel(XPATH_PDM_NAO_ENCONTRADO):
                self.engine.press("ENTER")
                return tentativa

            # Limpa para a próxima. Com folga: se o portal tiver completado
            # algo sozinho, sobrar caractere faria a busca seguinte procurar
            # por "TENTATIVA_ANTERIORtentativa_nova" -- que não acha nada, e a
            # cascata inteira falharia por um motivo que não é o do portal.
            self.engine.press(["BACKSPACE"] * (len(tentativa) + 5))
            time.sleep(PAUSA_ANIMACAO)
        return None

    def processar_item_individual(self, dados_item):
        """
        Lógica atualizada com correções de foco e espera.

        CP 5.4 (Fase 5): PORTE FIEL para as primitivas de `RPAEngine`. O
        mecanismo NÃO mudou -- continua sendo o fluxo por TAB/foco, com os
        mesmos seletores, a mesma contagem de TABs e os mesmos `time.sleep`.

        O que o checkpoint pede além disso ("reimplementar com seletores
        diretos ONDE O USUÁRIO CONFIRMAR que o alvo é estável") NÃO foi feito,
        e de propósito: escolher seletor direto para um campo que hoje só é
        alcançado por "3 TABs depois da descrição" exige olhar a tela real. O
        porte tira o módulo do Selenium sem inventar nada; a troca de
        mecanismo fica para a sessão com o usuário.

        CLIQUE NATIVO, NÃO POR JAVASCRIPT (corrigido após o 1º teste real).
        Todo clique deste fluxo é `click_nativo`, porque todo clique deste
        fluxo existe para LEVAR O FOCO a um campo -- o que vem depois dele é
        sempre `digitar_no_foco(...)` ou `press("TAB")`. O clique por JS
        (`click`/`click_estrito`/`click_raw`, a mecânica canônica do resto do
        projeto) dispara o evento mas não move o foco, e o sintoma é mudo: o
        campo fica vazio, as teclas caem no vizinho e o erro só aparece
        páginas depois, como timeout. Foi assim que o Contrato ficou em
        branco no primeiro teste da Fase 5. O original usava clique nativo em
        todos os 5 pontos; este porte voltou a usar.

        UM PONTO A CONFERIR NA VALIDAÇÃO (registrado em PENDENCIAS.md): o
        original capturava o elemento ativo numa variável e mandava as teclas
        seguintes para AQUELA referência, mesmo que o foco tivesse mudado. Um
        `active_element` não tem seletor, então aqui as teclas vão para quem
        estiver com o foco NA HORA. Nos combos do OutSystems isso costuma dar
        no mesmo (o elemento externo repassa as teclas ao input interno), mas
        é a diferença mais sutil desta migração e só o portal responde.
        """
        pdm = dados_item.get('pdm_escolhido')
        desc_curta = dados_item.get('descricao_curta')
        origem = dados_item.get('origem')
        tipo = dados_item.get('tipo')
        tipo_fabricacao = dados_item.get('tipo de fabricação')
        cod_projeto = dados_item.get('codigo_projeto')
        unidade = dados_item.get('unidade')

        # --- ATUALIZAÇÃO 1: Tratamento de "NENHUM" ---
        if pdm == "NENHUM":
            return "PULAR", ("VERIFICAR (PULADO)", "VERIFICAR (PULADO)")

        def _clicar(seletor):
            """`wait.until(element_to_be_clickable(...)).click()` -- o par que
            se repete 4x neste fluxo.

            `click_nativo` e não `click_raw`: aqui o clique tem que levar o
            foco junto (ver a docstring da função). `click_nativo` já embute a
            espera de "clicável", mas o `wait_clickable` explícito fica: ele
            é o que faz a espera valer também no motor Playwright do jeito
            que o original esperava, e custa nada quando o alvo já está
            pronto."""
            self.engine.wait_clickable(seletor)
            self.engine.click_nativo(seletor)

        try:
            # 1. Clicar em Nova Ficha
            time.sleep(PAUSA_INICIO_ITEM)
            _clicar(XPATH_BOTAO_NOVA_FICHA)

            # 2. Preencher PDM (LÓGICA ATUALIZADA - CLIQUE NA DIV)
            time.sleep(PAUSA_ABERTURA_FICHA)
            # Clica na div container, não no input direto
            _clicar(XPATH_DIV_PESQUISAR_PDM)

            time.sleep(PAUSA_MUDANCA_FOCO)  # Espera foco mudar

            # Digita no input que ganhou o foco automaticamente, tentando as
            # variações até o portal achar (ver `_buscar_pdm`). Antes daqui
            # era `digitar_no_foco(pdm)` + sleep + ENTER, SEM nunca perguntar
            # se o filtro tinha achado alguma coisa.
            usado = self._buscar_pdm(pdm)
            if usado is None:
                tentadas = ", ".join(repr(t) for t in tentativas_de_busca(pdm))
                return "ERRO", (
                    f"O portal respondeu 'PDM nao encontrado' para todas as "
                    f"buscas: {tentadas}. O PDM pode nao existir no portal, ou "
                    f"o titulo pode estar diferente do que o portal indexa. "
                    f"Escolha outro PDM ou confira a ficha a mao."
                )

            # 3. Preencher Contrato
            _clicar(XPATH_DROPDOWN_CONTRATO)
            time.sleep(PAUSA_FOCO)

            self.engine.press("TAB")
            time.sleep(PAUSA_ANIMACAO)

            self.engine.press("ENTER")

            # 4. Clicar em Salvar (1º)
            _clicar(XPATH_SALVAR_1)

            # 5. Capturar Código PMIB
            time.sleep(PAUSA_GERACAO_PMIB)  # Cobre a latência da 1ª ficha
            try:
                self.engine.wait_visible(XPATH_CODIGO_PMIB)
            except Exception:
                # O Código PMIB não apareceu. A causa MAIS COMUM não é o
                # portal estar lento -- é o Salvar ter sido RECUSADO, com
                # algum campo em branco marcado em vermelho. Sem isto aqui, o
                # usuário vê `ERRO no Selenium: Message:` (mensagem vazia) e
                # não tem como saber disso.
                try:
                    recusado = self.engine.element_exists(XPATH_CAMPO_OBRIGATORIO)
                except Exception:
                    # A sonda é um EXTRA. Se ela própria falhar (página caiu,
                    # sessão morreu), o erro que vale é o de cima, não o dela.
                    recusado = False
                if recusado:
                    raise RuntimeError(
                        "A ficha nao foi salva: o portal marcou campo obrigatorio em "
                        "branco. O suspeito n. 1 e o CONTRATO, que este fluxo escolhe "
                        "por TAB+ENTER no dropdown -- confira a tela, que ficou parada "
                        "no erro de proposito."
                    ) from None
                raise
            codigo_pmib = str(self.engine.texto(XPATH_CODIGO_PMIB)).strip().split(" ")[0]

            # 6. Inserir Código do Projeto
            # Espera o campo ficar CLICÁVEL, não apenas visível
            self.engine.wait_clickable(XPATH_CAMPO_PROJETO)
            time.sleep(PAUSA_FOCO)  # Pausa extra estabilizadora
            # Clique NATIVO: "cravar o foco" é o propósito inteiro desta
            # linha, e um clique por JS não crava foco nenhum.
            self.engine.click_nativo(XPATH_CAMPO_PROJETO)
            self.engine.digitar_no_foco(cod_projeto)

            # 7. Descrição Breve (Via TAB)
            self.engine.press("TAB")
            time.sleep(PAUSA_ANIMACAO)
            self.engine.digitar_no_foco(desc_curta)

            # 8. Origem (3 Tabs)
            self.engine.press(["TAB", "TAB", "TAB"])
            time.sleep(PAUSA_ANIMACAO)
            self.engine.press("ENTER")
            time.sleep(PAUSA_ANIMACAO)
            char_origem = "i" if origem and origem.lower() == 'importado' else "n"
            self.engine.digitar_no_foco(char_origem)
            self.engine.press("ENTER")

            # 9. Tipo (1 Tab)
            self.engine.press("TAB")
            time.sleep(PAUSA_ANIMACAO)
            self.engine.press("ENTER")
            time.sleep(PAUSA_ANIMACAO)
            char_tipo = "n" if tipo and tipo.lower() == 'não reparável' else "r"
            self.engine.digitar_no_foco(char_tipo)
            self.engine.press("ENTER")

            # 10. Unidade (1 Tab)
            self.engine.press("TAB")
            time.sleep(PAUSA_MUDANCA_FOCO)

            self.engine.press("ENTER")
            time.sleep(PAUSA_MUDANCA_FOCO)

            self.engine.digitar_no_foco(_teclas_da_unidade(unidade))
            self.engine.press("ENTER")
            time.sleep(PAUSA_FOCO)

            # 11. Fabricação (5 Tabs)
            self.engine.press(["TAB", "TAB", "TAB", "TAB", "TAB"])
            time.sleep(PAUSA_ANIMACAO)
            self.engine.press("ENTER")
            time.sleep(PAUSA_FOCO)

            char_fab = "e" if tipo_fabricacao and tipo_fabricacao.lower() == 'especial' else "s"
            self.engine.digitar_no_foco(char_fab)
            self.engine.press("ENTER")
            time.sleep(PAUSA_ANIMACAO)

            # 12. Salvar Final
            _clicar(XPATH_SALVAR_PROJETO)

            # --- ATUALIZAÇÃO 2: Captura Robusta do PDM Final ---
            print("Aguardando PDM Final...")
            # Procura div com tooltip começando com PDM
            self.engine.wait_visible(XPATH_PDM_FINAL)
            texto_tooltip = self.engine.atributo(XPATH_PDM_FINAL, "data-tooltip")

            # Pegando a string inteira, removendo apenas espaços das pontas
            pdm_revisao = texto_tooltip.strip()

            # 13. Voltar para lista (URL Reset para garantir limpeza)
            self.engine.goto(config.PORTAL_URL)

            return "SUCESSO", (codigo_pmib, pdm_revisao)

        except Exception as e:
            # Deixa a tela parada no erro para o usuário inspecionar visualmente
            return "ERRO", str(e)

    def atualizar_projeto_em_massa(self, pmib, novo_codigo_projeto):
        """Abre a ficha `pmib` e troca o Código do Projeto.

        CP 5.2 (Fase 5): migrado para as primitivas de `RPAEngine` -- roda em
        Selenium ou Playwright conforme `config.RPA_ENGINE["cria_fichas"]`.
        Mesmos seletores, mesma ordem, mesmos `time.sleep`.

        Duas notas sobre fidelidade:

        - O preenchimento usa `fill_estrito`, não `fill`: esta função REPORTA
          o resultado (`("SUCESSO", ...)` / `("ERRO", ...)`). Com o `fill`
          tolerante, uma falha ao escrever o código passaria batida, a ficha
          seria salva sem o valor novo e a função devolveria SUCESSO -- pior
          que um erro, porque ninguém confere.
        - `fill_estrito` faz Ctrl+A + BACKSPACE + digitar; o original fazia
          Ctrl+A + DELETE. Depois do Ctrl+A o conteúdo inteiro está
          selecionado e as duas teclas apagam a seleção igualmente. O que o
          comentário original defendia -- Ctrl+A no lugar do `.clear()`, não
          confiável em textarea do OutSystems -- está preservado.

        `processar_item_individual` NÃO foi migrado aqui: o fluxo por
        TAB/`active_element` é o mais frágil do sistema e o plano reserva o
        CP 5.4 para ele, com os seletores confirmados pelo usuário na tela
        real.
        """
        try:
            # 1. Garante que está na tela inicial da lista
            self.engine.goto(config.PORTAL_URL)
            time.sleep(PAUSA_CARGA_LISTA)

            # 2. Localiza a barra de pesquisa principal (usando contains para
            #    ignorar prefixos dinâmicos do OutSystems).
            #
            #    A limpeza agressiva (Ctrl+A + apagar) que o original fazia à
            #    mão é exatamente a mecânica de `fill_estrito` -- por isso
            #    limpar e digitar viraram uma chamada só.
            self.engine.wait_clickable(XPATH_BUSCA_MASSA)
            self.engine.fill_estrito(XPATH_BUSCA_MASSA, pmib)
            self.engine.press("ENTER")

            # 3. Espera INTELIGENTE: aguarda até que uma linha da tabela
            #    contenha o texto do PMIB pesquisado -- garante que a tabela
            #    já filtrou antes de tentar clicar.
            self.engine.wait_present(XPATH_LINHA_RESULTADO.format(pmib=pmib))

            # Agora sim, procura o ícone de lápis DENTRO dessa linha
            # específica e clica.
            xpath_ficha = XPATH_LAPIS_MASSA.format(pmib=pmib)
            self.engine.wait_clickable(xpath_ficha)
            self.engine.click_raw(xpath_ficha)

            # 4. Inserir o NOVO Código do Projeto.
            # A espera do motor já cobre o carregamento da nova página e o
            # campo ficar disponível -- não precisamos de sleep(4).
            self.engine.wait_clickable(XPATH_CAMPO_PROJETO)

            # Micro-pausa mantida porque o OutSystems tem uma animação de
            # "deslizar" a tela que às vezes rouba o foco do clique.
            time.sleep(PAUSA_ANIMACAO)
            self.engine.fill_estrito(XPATH_CAMPO_PROJETO, novo_codigo_projeto)

            # 5. Clicar em Salvar (mesmo XPath do salvar final da criação)
            time.sleep(PAUSA_FOCO)
            self.engine.wait_clickable(XPATH_SALVAR_PROJETO)
            self.engine.click_raw(XPATH_SALVAR_PROJETO)

            # Aguarda a mensagem de sucesso ou salvamento processar
            time.sleep(PAUSA_SALVAMENTO_FINAL)
            return "SUCESSO", "Salvo."

        except Exception as e:
            return "ERRO", str(e)
