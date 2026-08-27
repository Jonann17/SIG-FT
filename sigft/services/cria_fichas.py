import pandas as pd
import openpyxl
import time

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

    def _formatar_itens(self, df):
        texto = ""
        for index, row in df.iterrows():
            texto += f"\n### ITEM {index + 1}\n"
            texto += f"- Descrição: {row['DESCRIÇÃO']}\n"
            texto += f"- Marca/Modelo: {row['MARCA/MODELO']}\n"
            cod_mat = str(row['CÓDIGO DO MATERIAL']).strip() if pd.notna(row['CÓDIGO DO MATERIAL']) else ""
            texto += f"- Código do Material: {cod_mat}\n"

            # Checa se o campo é vazio (ou string vazia criada pelo fillna) e trata corretamente
            unidade_raw = row.get('UNID.', '')
            unidade_final = "NÃO ESPECIFICADA" if not unidade_raw or pd.isna(unidade_raw) else unidade_raw
            texto += f"- Unidade: {unidade_final}\n"
        return texto

    def processar_lote(self, df_itens, lista_pdms, instrucoes):
        # CP 3.1: `model = genai.GenerativeModel(...)` sai daqui -- a
        # resolução de modelo/provider agora é responsabilidade de
        # `self._llm` (`get_llm("categorizar_pdm", ...)`, ver `__init__`).
        if not self.api_key: raise ValueError("API Key não configurada.")
        itens_texto = self._formatar_itens(df_itens)

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
            return resp.parsed_json
        except Exception as e:
            # `from e` mantem o traceback ORIGINAL encadeado. Sem ele, o
            # erro de verdade (timeout, chave invalida, resposta malformada)
            # some, e sobra so a string -- que e o que chega no console do
            # usuario quando a IA falha.
            raise Exception(f"Erro na IA: {e}") from e


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

            # Digita no input que ganhou o foco automaticamente
            self.engine.digitar_no_foco(pdm)
            time.sleep(PAUSA_FILTRO_PDM)
            self.engine.press("ENTER")

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
