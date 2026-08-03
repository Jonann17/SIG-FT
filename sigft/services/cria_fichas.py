import pandas as pd
import openpyxl
import json
import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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
            raise Exception(f"Erro na IA: {e}")


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


class AutomacaoPMIB:
    def __init__(self):
        self.engine = None
        self.driver = None
        self.wait = None
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

        `self.driver`/`self.wait` continuam sendo expostos QUANDO o motor é o
        Selenium, porque `processar_item_individual` ainda depende deles --
        esse fluxo é o CP 5.4. Com o motor Playwright eles ficam `None`, e
        `processar_item_individual` avisa disso de forma explícita em vez de
        estourar um `AttributeError` obscuro.
        """
        self.engine = criar_engine("cria_fichas", wait_timeout=10)
        self.driver = getattr(self.engine, "driver", None)
        self.wait = getattr(self.engine, "wait", None)
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

        CP 5.2: este fluxo NÃO foi migrado -- ele é o CP 5.4 ("o fluxo por
        TAB/active_element é o mais frágil do sistema; reimplementar com
        seletores diretos onde o usuário confirmar que o alvo é estável").
        Por isso ele ainda fala Selenium direto, e a guarda abaixo falha com
        uma mensagem que diz o que fazer, em vez de deixar um
        `AttributeError: 'NoneType' object has no attribute 'find_element'`
        aparecer no meio da criação de uma ficha real.
        """
        if self.driver is None:
            raise RuntimeError(
                "Criar Fichas (item individual) ainda roda só no motor Selenium "
                "-- a migração desse fluxo é o CP 5.4 do plano de refatoração. "
                "Rode este módulo com SIGFT_RPA_ENGINE=selenium (ou remova a "
                "variável de ambiente). A opção 'atualizar projeto em massa' já "
                "funciona nos dois motores."
            )
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

        try:
            # 1. Clicar em Nova Ficha
            time.sleep(PAUSA_INICIO_ITEM)
            locator_nova_ficha = (By.XPATH, '//*[@id="b1-Actions"]/button')
            self.wait.until(EC.element_to_be_clickable(locator_nova_ficha)).click()

            # 2. Preencher PDM (LÓGICA ATUALIZADA - CLIQUE NA DIV)
            time.sleep(PAUSA_ABERTURA_FICHA)
            # Clica na div container, não no input direto
            locator_div_pdm = (By.XPATH, '//div[@data-tooltip="Pesquisar PDM"]')
            div_pdm = self.wait.until(EC.element_to_be_clickable(locator_div_pdm))
            div_pdm.click()

            time.sleep(PAUSA_MUDANCA_FOCO)  # Espera foco mudar

            # Pega o input que ganhou o foco automaticamente
            campo_pdm_input = self.driver.switch_to.active_element
            campo_pdm_input.send_keys(pdm)
            time.sleep(PAUSA_FILTRO_PDM)
            campo_pdm_input.send_keys(Keys.ENTER)

            # 3. Preencher Contrato
            locator_contrato = (By.XPATH, '//*[@id="b10-ContractDropdownSearch"]')
            self.wait.until(EC.element_to_be_clickable(locator_contrato)).click()
            time.sleep(PAUSA_FOCO)

            elm_ativo = self.driver.switch_to.active_element
            elm_ativo.send_keys(Keys.TAB)
            time.sleep(PAUSA_ANIMACAO)

            elm_ativo_final = self.driver.switch_to.active_element
            elm_ativo_final.send_keys(Keys.ENTER)

            # 4. Clicar em Salvar (1º)
            locator_salvar_1 = (By.XPATH, '//*[@id="b10-b7-Button"]/button')
            self.wait.until(EC.element_to_be_clickable(locator_salvar_1)).click()

            # 5. Capturar Código PMIB
            time.sleep(PAUSA_GERACAO_PMIB)  # Aumentado de 3 para 6 segundos para cobrir a latência da 1ª ficha
            locator_cod = (By.XPATH, '//*[@id="b8-b1-Content"]/span')
            elemento_pmib = self.wait.until(EC.visibility_of_element_located(locator_cod))
            codigo_pmib = str(elemento_pmib.text).strip().split(" ")[0]

            # 6. Inserir Código do Projeto
            locator_proj = (By.XPATH, '//*[@id="b10-b9-TextArea_ProjectCode"]')
            # Mudado para esperar o campo ficar clicável, não apenas visível
            campo_proj = self.wait.until(EC.element_to_be_clickable(locator_proj))
            time.sleep(PAUSA_FOCO)  # Pausa extra estabilizadora
            campo_proj.click()  # Crava o foco no campo antes de digitar
            campo_proj.send_keys(cod_projeto)

            # 7. Descrição Breve (Via TAB)
            campo_proj.send_keys(Keys.TAB)
            time.sleep(PAUSA_ANIMACAO)
            self.driver.switch_to.active_element.send_keys(desc_curta)

            # 8. Origem (3 Tabs)
            self.driver.switch_to.active_element.send_keys(Keys.TAB, Keys.TAB, Keys.TAB)
            time.sleep(PAUSA_ANIMACAO)
            campo_origem = self.driver.switch_to.active_element
            campo_origem.send_keys(Keys.ENTER)
            time.sleep(PAUSA_ANIMACAO)
            char_origem = "i" if origem and origem.lower() == 'importado' else "n"
            campo_origem.send_keys(char_origem, Keys.ENTER)

            # 9. Tipo (1 Tab)
            self.driver.switch_to.active_element.send_keys(Keys.TAB)
            time.sleep(PAUSA_ANIMACAO)
            campo_tipo = self.driver.switch_to.active_element
            campo_tipo.send_keys(Keys.ENTER)
            time.sleep(PAUSA_ANIMACAO)
            char_tipo = "n" if tipo and tipo.lower() == 'não reparável' else "r"
            campo_tipo.send_keys(char_tipo, Keys.ENTER)

            # 10. Unidade (1 Tab)
            self.driver.switch_to.active_element.send_keys(Keys.TAB)
            time.sleep(PAUSA_MUDANCA_FOCO)

            div_unidade = self.driver.switch_to.active_element
            div_unidade.send_keys(Keys.ENTER)
            time.sleep(PAUSA_MUDANCA_FOCO)

            campo_unidade = self.driver.switch_to.active_element
            u_l = unidade.lower() if unidade else "unidade"
            u_keys = "un"
            if u_l in ('peça', 'pç', 'peca'): u_keys = "pç"
            elif u_l in ('metro', 'm'): u_keys = 'metro - (m)'
            elif u_l in ('litro', 'l'): u_keys = 'litro - (l)'
            elif u_l in ('conjunto', 'cj'): u_keys = 'cj'

            campo_unidade.send_keys(u_keys, Keys.ENTER)
            time.sleep(PAUSA_FOCO)

            # 11. Fabricação (5 Tabs)
            self.driver.switch_to.active_element.send_keys(Keys.TAB, Keys.TAB, Keys.TAB, Keys.TAB, Keys.TAB)
            time.sleep(PAUSA_ANIMACAO)
            campo_fab = self.driver.switch_to.active_element
            campo_fab.send_keys(Keys.ENTER)
            time.sleep(PAUSA_FOCO)

            campo_fab_in = self.driver.switch_to.active_element
            char_fab = "e" if tipo_fabricacao and tipo_fabricacao.lower() == 'especial' else "s"
            campo_fab_in.send_keys(char_fab, Keys.ENTER)
            time.sleep(PAUSA_ANIMACAO)

            # 12. Salvar Final
            locator_salvar_2 = (By.XPATH, '//*[@id="b10-b9-Form1"]/div[6]/button[1]')
            self.wait.until(EC.element_to_be_clickable(locator_salvar_2)).click()

            # --- ATUALIZAÇÃO 2: Captura Robusta do PDM Final ---
            print("Aguardando PDM Final...")
            # Procura div com tooltip começando com PDM
            locator_pdm_final = (By.CSS_SELECTOR, "div.vscomp-value[data-tooltip^='PDM']")
            elemento_pdm_final = self.wait.until(EC.visibility_of_element_located(locator_pdm_final))
            texto_tooltip = elemento_pdm_final.get_attribute("data-tooltip")

            # Pegando a string inteira, removendo apenas espaços em branco das pontas
            pdm_revisao = texto_tooltip.strip()

            # 13. Voltar para lista (URL Reset para garantir limpeza)
            self.driver.get('https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList')

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
