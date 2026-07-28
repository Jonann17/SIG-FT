import pandas as pd
import openpyxl
import google.generativeai as genai
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
# CP 2.1 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 2): fábrica única de
# driver Chrome, substitui `webdriver.Chrome()` cru em
# `AutomacaoPMIB.iniciar_driver` abaixo.
from sigft.core.rpa.selenium_engine import create_chrome_driver, SeleniumEngine
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
from sigft.core.rpa.portal import PMIBPortal


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
        if self.api_key:
            genai.configure(api_key=self.api_key, transport='rest')
        else:
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
        if not self.api_key: raise ValueError("API Key não configurada.")
        model = genai.GenerativeModel('gemini-3.1-pro-preview')
        itens_texto = self._formatar_itens(df_itens)

        prompt_template = f"""
        Você é um especialista em catalogação de materiais (PDM) altamente preciso.
        Sua tarefa é classificar uma *lista de itens* usando um manual de regras,
        uma lista de PDMs e um conjunto de exemplos.

        ### PROCESSO (Para cada item):
        1. Analise o "ITEM" (Descrição, Marca, etc.).
        2. Use o "MANUAL DE REGRAS" e os "EXEMPLOS" para achar a CLASSE correta.
        3. Use a "LISTA DE PDMS FINAIS" para escolher o PDM exato daquela classe.

        ---
        ### MANUAL DE REGRAS (GRUPOS E CLASSES)
        {instrucoes}
        ---
        ### LISTA DE PDMS FINAIS (ESCOLHA UM DESTES)
        {lista_pdms}
        ---
        ### EXEMPLOS DE CLASSIFICAÇÃO CORRETA
        (Estes exemplos são apenas guias de lógica. A sua escolha de PDM
        DEVE vir da "LISTA DE PDMS FINAIS" acima.)

        Exemplo 1 (Mecânico):
        - Descrição: Bomba KSB 123-ABC
        - PDM: PDM.4020.001 - BOMBA CENTRIFUGA
        - Descrição breve: BOMBA - KSB 123-ABC

        Exemplo 2 (Câmera):
        - Descrição original: CAMERAS DOME FIZ AXIS P1375-E
        - PDM: PDM.6720.001 - CAMERA
        - Descrição breve: CAMERA - P1375-E

        Exemplo 3 (Rede):
        - Descrição original: Cisco Analog Voice Gateway VG420 - 144FXS
        - PDM: PDM.5895.016 - VOIP GATEWAY
        - Descrição breve: VOICE GATEWAY - VG420-144FXS

        Exemplo 4 (Rede):
        - Descrição original: IE4010 w/ 12GE SFP, 12GE Copper PoE+ & 4GE SFP uplink ports
        - PDM: PDM.5895.003 - SWITCH
        - Descrição breve: SWITCH - IE-4010-16S12P

        Exemplo 5 (Cabo):
        - Descrição original: 5 ft LOW LOSS CABLE ASSEMBLY W/N CONNECTORS
        - PDM: PDM.6145.011 - CABO, TRANSMISSAO DADOS
        - Descrição breve: CABO ACCESS POINT - AIR-CAB005LL-N

        Exemplo 6 (Rede):
        - Descrição original: PATCH PANEL DESCARREGADO 24P BLINDADO - DATAWAVE READY
        - PDM: PDM.5895.006 - PATCH PANEL
        - Descrição breve: PATCH PANEL 24P - DATAWAVE READY

        Exemplo 7 (TI):
        - Descrição original: Servidor Dell PowerEdge C6600 ...
        - PDM: PDM.7010.018 - SERVIDOR
        - Descrição Breve: SERVIDOR - POWEREDGE C6600

        Exemplo 8 (Rede):
        - Descrição original: Wi-Fi 6 Outdoor AP, External Ant, -ROW Regulatory Domain
        - PDM: PDM.5895.015 - ACCESS POINT
        - Descrição Breve: ACCESS POINT - C9124AXE-ROW

        ---
        ### ITENS PARA ANALISAR (EM LOTE):
        {itens_texto}
        ---
        ### SUA TAREFA:
        Analise CADA UM dos itens da lista "ITENS PARA ANALISAR".
        Retorne um JSON contendo UMA LISTA de objetos. Cada objeto deve
        corresponder a UM item, na MESMA ORDEM.

        Formato da Resposta (Lista de JSON):
        [
        {{
            "item_processado": 1,
            "pdm_escolhido": "...",
            "descricao_curta": "...",
            "origem": "Importado" | "Nacional",
            "tipo de fabricação": "Catálogo" | "Especial",
            "tipo": "Reparável" | "Não Reparável",
            "unidade": "Unidade" | "Peça" | "Conjunto" | "metro - (m)" | "litro - (l)"
        }},
        {{
            "item_processado": 2,
            "pdm_escolhido": "...",
            "descricao_curta": "...",
            "origem": "...",
            "tipo de fabricação": "...",
            "tipo": "...",
            "unidade": "..."
        }}
        ]

        Regras para o JSON (para cada item):
        1. 'pdm_escolhido': O PDM COMPLETO (ex: "PDM.1650.001 - ACUMULADOR"). Se NENHUM for adequado, retorne "NENHUM".
        2. 'descricao_curta': Uma descrição de até 40 caracteres, sem acentuação.
        3. 'origem': 'Importado' ou 'Nacional'.
        4. 'tipo de fabricação': 'Catálogo' ou 'Especial'.
        5. 'tipo': 'Reparável' ou 'Não Reparável'.
        6. 'unidade': 'Unidade', 'Peça', 'Conjunto', 'metro - (m)' ou 'litro - (l)'. Se inconclusivo ou "NÃO ESPECIFICADA", use "Unidade".

        Responda APENAS com a lista JSON. Não inclua texto antes ou depois.
        """
        try:
            response = model.generate_content(prompt_template)
            texto_bruto = response.text
            inicio = texto_bruto.find('[')
            fim = texto_bruto.rfind(']')
            if inicio != -1 and fim != -1:
                return json.loads(texto_bruto[inicio: fim + 1])
            else:
                clean = texto_bruto.strip()
                if clean.startswith("```json"): clean = clean[7:-3].strip()
                return json.loads(clean)
        except Exception as e:
            raise Exception(f"Erro na IA: {e}")


class AutomacaoPMIB:
    def __init__(self):
        self.driver = None
        self.wait = None
        self.portal = None

    def iniciar_driver(self):
        """CP 2.1: a criação em si (Chrome + maximize + WebDriverWait(10s))
        agora vem de `create_chrome_driver` (única fábrica, ver
        core/rpa/selenium_engine.py) — timeout preservado EXATAMENTE como
        antes (10s, o único dos 6 pontos originais com esse valor).

        CP 2.2: logo em seguida, `self.portal` passa a existir (`PMIBPortal`
        sobre um `SeleniumEngine` construído com o MESMO `driver`/`wait`) --
        por consistência estrutural com os outros 5 backends, SEM nenhum
        call site desta classe migrado ainda (ver comentário de import no
        topo do arquivo e docs/refatoracao/PENDENCIAS.md).
        """
        self.driver, self.wait = create_chrome_driver(wait_timeout=10)
        self.portal = PMIBPortal(SeleniumEngine(self.driver, self.wait))
        return self.driver

    def abrir_portal(self, url):
        url_limpa = str(url).strip()
        if not url_limpa.lower().startswith("http"):
            url_limpa = "https://" + url_limpa
        self.driver.get(url_limpa)

    def processar_item_individual(self, dados_item):
        """
        Lógica atualizada com correções de foco e espera.
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

        try:
            # 1. Clicar em Nova Ficha
            time.sleep(1.5)
            locator_nova_ficha = (By.XPATH, '//*[@id="b1-Actions"]/button')
            self.wait.until(EC.element_to_be_clickable(locator_nova_ficha)).click()

            # 2. Preencher PDM (LÓGICA ATUALIZADA - CLIQUE NA DIV)
            time.sleep(5)
            # Clica na div container, não no input direto
            locator_div_pdm = (By.XPATH, '//div[@data-tooltip="Pesquisar PDM"]')
            div_pdm = self.wait.until(EC.element_to_be_clickable(locator_div_pdm))
            div_pdm.click()

            time.sleep(1.5)  # Espera foco mudar

            # Pega o input que ganhou o foco automaticamente
            campo_pdm_input = self.driver.switch_to.active_element
            campo_pdm_input.send_keys(pdm)
            time.sleep(1)
            campo_pdm_input.send_keys(Keys.ENTER)

            # 3. Preencher Contrato
            locator_contrato = (By.XPATH, '//*[@id="b10-ContractDropdownSearch"]')
            self.wait.until(EC.element_to_be_clickable(locator_contrato)).click()
            time.sleep(1)

            elm_ativo = self.driver.switch_to.active_element
            elm_ativo.send_keys(Keys.TAB)
            time.sleep(0.5)

            elm_ativo_final = self.driver.switch_to.active_element
            elm_ativo_final.send_keys(Keys.ENTER)

            # 4. Clicar em Salvar (1º)
            locator_salvar_1 = (By.XPATH, '//*[@id="b10-b7-Button"]/button')
            self.wait.until(EC.element_to_be_clickable(locator_salvar_1)).click()

            # 5. Capturar Código PMIB
            time.sleep(6)  # Aumentado de 3 para 6 segundos para cobrir a latência da 1ª ficha
            locator_cod = (By.XPATH, '//*[@id="b8-b1-Content"]/span')
            elemento_pmib = self.wait.until(EC.visibility_of_element_located(locator_cod))
            codigo_pmib = str(elemento_pmib.text).strip().split(" ")[0]

            # 6. Inserir Código do Projeto
            locator_proj = (By.XPATH, '//*[@id="b10-b9-TextArea_ProjectCode"]')
            # Mudado para esperar o campo ficar clicável, não apenas visível
            campo_proj = self.wait.until(EC.element_to_be_clickable(locator_proj))
            time.sleep(1)  # Pausa extra estabilizadora
            campo_proj.click()  # Crava o foco no campo antes de digitar
            campo_proj.send_keys(cod_projeto)

            # 7. Descrição Breve (Via TAB)
            campo_proj.send_keys(Keys.TAB)
            time.sleep(0.5)
            self.driver.switch_to.active_element.send_keys(desc_curta)

            # 8. Origem (3 Tabs)
            self.driver.switch_to.active_element.send_keys(Keys.TAB, Keys.TAB, Keys.TAB)
            time.sleep(0.5)
            campo_origem = self.driver.switch_to.active_element
            campo_origem.send_keys(Keys.ENTER)
            time.sleep(0.5)
            char_origem = "i" if origem and origem.lower() == 'importado' else "n"
            campo_origem.send_keys(char_origem, Keys.ENTER)

            # 9. Tipo (1 Tab)
            self.driver.switch_to.active_element.send_keys(Keys.TAB)
            time.sleep(0.5)
            campo_tipo = self.driver.switch_to.active_element
            campo_tipo.send_keys(Keys.ENTER)
            time.sleep(0.5)
            char_tipo = "n" if tipo and tipo.lower() == 'não reparável' else "r"
            campo_tipo.send_keys(char_tipo, Keys.ENTER)

            # 10. Unidade (1 Tab)
            self.driver.switch_to.active_element.send_keys(Keys.TAB)
            time.sleep(1.5)

            div_unidade = self.driver.switch_to.active_element
            div_unidade.send_keys(Keys.ENTER)
            time.sleep(1.5)

            campo_unidade = self.driver.switch_to.active_element
            u_l = unidade.lower() if unidade else "unidade"
            u_keys = "un"
            if u_l in ('peça', 'pç', 'peca'): u_keys = "pç"
            elif u_l in ('metro', 'm'): u_keys = 'metro - (m)'
            elif u_l in ('litro', 'l'): u_keys = 'litro - (l)'
            elif u_l in ('conjunto', 'cj'): u_keys = 'cj'

            campo_unidade.send_keys(u_keys, Keys.ENTER)
            time.sleep(1)

            # 11. Fabricação (5 Tabs)
            self.driver.switch_to.active_element.send_keys(Keys.TAB, Keys.TAB, Keys.TAB, Keys.TAB, Keys.TAB)
            time.sleep(0.5)
            campo_fab = self.driver.switch_to.active_element
            campo_fab.send_keys(Keys.ENTER)
            time.sleep(1.0)

            campo_fab_in = self.driver.switch_to.active_element
            char_fab = "e" if tipo_fabricacao and tipo_fabricacao.lower() == 'especial' else "s"
            campo_fab_in.send_keys(char_fab, Keys.ENTER)
            time.sleep(0.5)

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
        try:
            # 1. Garante que está na tela inicial da lista
            self.driver.get('https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList')
            time.sleep(2)

            # 2. Localiza a barra de pesquisa principal (usando contains para ignorar prefixos dinâmicos do OutSystems)
            locator_pesquisa = (By.XPATH, "//input[contains(@id, 'InputDatasheetFilter')]")
            campo_pesquisa = self.wait.until(EC.element_to_be_clickable(locator_pesquisa))

            # Limpa o campo de forma mais agressiva (OutSystems às vezes ignora o .clear() simples)
            campo_pesquisa.send_keys(Keys.CONTROL + "a")
            campo_pesquisa.send_keys(Keys.DELETE)
            time.sleep(0.5)

            campo_pesquisa.send_keys(pmib)
            campo_pesquisa.send_keys(Keys.ENTER)

            # 3. Espera INTELIGENTE: Aguarda até que uma linha da tabela contenha o texto do PMIB pesquisado
            # Isso garante que a tabela já filtrou os resultados antes de tentar clicar
            locator_linha_resultado = (By.XPATH, f"//tr[contains(., '{pmib}')]")
            self.wait.until(EC.presence_of_element_located(locator_linha_resultado))

            # Agora sim, procura o ícone de lápis DENTRO dessa linha específica e clica
            locator_ficha = (By.XPATH, f"//tr[contains(., '{pmib}')]//a[.//i[contains(@class, 'fa-pencil-square-o')]]")
            self.wait.until(EC.element_to_be_clickable(locator_ficha)).click()

            # 4. Inserir o NOVO Código do Projeto
            # O próprio WebDriverWait já vai esperar a nova página carregar e o campo ficar disponível. Não precisamos de sleep(4).
            locator_proj = (By.XPATH, '//*[@id="b10-b9-TextArea_ProjectCode"]')
            campo_proj = self.wait.until(EC.element_to_be_clickable(locator_proj))

            # Mantemos apenas essa micro-pausa de 0.5s porque o OutSystems tem
            # uma animação de "deslizar" a tela que às vezes rouba o foco do clique
            time.sleep(0.5)
            campo_proj.click()

            # Como o campo já tem texto, precisamos limpá-lo antes de digitar
            # (O send_keys(Keys.CONTROL + "a") seguido de DELETE é mais robusto que o .clear() no Selenium em campos Textarea)
            campo_proj.send_keys(Keys.CONTROL + "a")
            campo_proj.send_keys(Keys.DELETE)
            time.sleep(0.5)

            campo_proj.send_keys(novo_codigo_projeto)

            # 5. Clicar em Salvar (Mesmo XPath do salvar final da criação)
            time.sleep(1)
            locator_salvar_2 = (By.XPATH, '//*[@id="b10-b9-Form1"]/div[6]/button[1]')
            self.wait.until(EC.element_to_be_clickable(locator_salvar_2)).click()

            # Aguarda a mensagem de sucesso ou salvamento processar (adapte se tiver um popup)
            time.sleep(3)
            return "SUCESSO", "Salvo."

        except Exception as e:
            return "ERRO", str(e)
