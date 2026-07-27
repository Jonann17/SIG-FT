import os
import re
import json
import time
import pandas as pd
import google.generativeai as genai
import unicodedata
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from selenium.webdriver.common.keys import Keys

from sigft import config
from sigft.core.excel import headers, pmib_codes


# =============================================================================
# CLASSE 1: PROCESSADOR DE DADOS E IA
# =============================================================================
class TechSpecsProcessor:
    def __init__(self, api_key):
        self.api_key = api_key
        self.cancel_requested = False  # <--- NOVA FLAG DE PARADA
        if self.api_key:
            genai.configure(api_key=self.api_key, transport='rest')

    def solicitar_parada(self):
        self.cancel_requested = True

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

    def _limpar_json_ia(self, texto):
        if not texto: return None
        # Remove marcadores de código e espaços
        texto = texto.replace("```json", "").replace("```", "").strip()
        # Garante que começa e termina com colchetes (lista JSON)
        inicio = texto.find('[')
        fim = texto.rfind(']')
        if inicio != -1 and fim != -1:
            return texto[inicio: fim + 1]
        return texto

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
            if self.cancel_requested:
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

            # --- NOVA VERIFICAÇÃO DE STATUS COMPLETO ---
            coluna_status = "CARACT. TÉCNICAS"
            if coluna_status in row_status.columns:
                status_atual = str(row_status.iloc[0][coluna_status]).strip().upper()
                if status_atual == "COMPLETO" and not processar_completos:
                    if callback_log: callback_log(f"PULADO: PMIB {codigo_pmib} já está COMPLETO. (Economizando API)")
                    continue
            # -------------------------------------------

            try:
                pdm_usado = row_status.iloc[0]['PDM usado']
                pdm_fmt = self.formatar_pdm(pdm_usado)
            except:
                if callback_log: callback_log(f"Erro ao ler PDM usado para {codigo_pmib}.")
                continue

            # Match Master PDM
            df_master_filt = master_pdm_df[master_pdm_df['CÓDIGO PDM'].astype(str) == pdm_fmt]
            if df_master_filt.empty:
                if callback_log: callback_log(f"PDM {pdm_fmt} não encontrado no Master.")
                continue

            # Ler Ficha Individual
            try:
                df_ficha = pd.read_excel(arquivo, sheet_name="Especificações técnicas copiar", header=0)
                cols_map = {
                    "Pergunta": "PERGUNTA",
                    "Resposta (Espanhol s/ caracteres especiais)": "RESP_ES",
                    "Resposta (Português s/ caracteres especiais)": "RESP_PT"
                }
                df_ficha = df_ficha.rename(columns=lambda x: cols_map.get(x, x))

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

                lista_contexto.append({
                    "CARACTERISTICA_DESC_PT": desc_pt,
                    "TEXTO_AJUDA": str(row_m.get('TEXTO DE AYUDA PT', '')),
                    "TIPO_DADO": str(row_m.get('TIPO DE CARACTERÍSTICA', '')),
                    "VALORES_POSSIVEIS_MASTER": str(row_m.get('VALORES PT', '')),
                    "SIMBOLO_UNIDADE": str(row_m.get('SÍMBOLO', '')),
                    "RESPOSTA_CRUA_PT": str(dados_resp['pt']),
                    "RESPOSTA_CRUA_ES": str(dados_resp['es'])
                })

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
        system_instruction = """
        Você é um assistente especialista em normalização de dados técnicos de engenharia.
        Sua tarefa é analisar características técnicas de materiais, comparar com definições de um padrão (PDM) e validar/corrigir as respostas, sem jamais utilizar acentuação nas respostas.

        === REGRAS DE INTEGRIDADE (PROIBIDO DUPLICAR E ALTERAR TIPOS) ===
        1. CHAVES ÚNICAS: O JSON final NÃO PODE, sob nenhuma hipótese, conter características duplicadas. Cada 'CARACTERISTICA_CHAVE' deve aparecer EXATAMENTE UMA VEZ na lista final. Se houver redundância, consolide os dados e mantenha apenas um item.
        2. OBEDIÊNCIA ESTRITA AO TIPO DE DADO: Respeite rigorosamente o 'TIPO_DADO' fornecido na entrada. Se o sistema informou que "VAZAO MAXIMA" é 'NUM', você NUNCA deve alterar para 'CHAR' no JSON. Se a entrada bruta for "max. 80 l/min", como o tipo é 'NUM', você deve extrair APENAS O NÚMERO ("80") e retornar o TIPO intacto como 'NUM'.

        === REGRAS DE FORMATAÇÃO (DECIMAIS E LISTAS) - MUITO IMPORTANTE ===
        1. SEPARADOR DECIMAL: Para valores numéricos (NUM ou INT) com casas decimais, você DEVE utilizar OBRIGATORIAMENTE a VÍRGULA (,) como separador decimal, e NUNCA o ponto (.).
           - Exemplo Correto: "0,86" | "10,26".
           - Exemplo Incorreto: "0.86" | "10.26".
        2. SEPARADOR DE LISTA: Se a resposta pertencer ao tipo LISTA e contiver múltiplos itens selecionados, você DEVE usar PONTO E VÍRGULA (;) para separá-los. NUNCA use vírgula para separar itens, pois a vírgula é exclusiva para decimais.
           - Exemplo Correto: "A; B; E; F".

        === REGRA DE CONVERSÃO DE UNIDADES (SÍMBOLOS) ===
        Para campos do tipo 'NUM' ou 'INT', o sistema fornece as unidades aceitas no campo 'SIMBOLO_UNIDADE' (ex: "AD, m³/h, m³/s").
        - Compare a unidade de medida informada na 'RESPOSTA_CRUA_PT' com as opções válidas.
        - Se a unidade for diferente, você DEVE realizar a conversão matemática correta para uma das unidades válidas (Ex: se a entrada for "171 l/min" e o sistema aceitar "m³/h", você fará o cálculo e retornará "10,26").
        - Coloque APENAS O NÚMERO convertido em 'RESPOSTA_PT_FINAL'.
        - Coloque a UNIDADE VÁLIDA correspondente no campo 'SIMBOLO'.

        === REGRA GLOBAL DE RETENÇÃO E EXCLUSÃO ===
        Sua prioridade MÁXIMA é NÃO perder dados técnicos. Leia o 'TEXTO_AJUDA' fornecido para entender o contexto da característica. Se a 'RESPOSTA_CRUA_PT' contiver qualquer informação que responda ao que é pedido (ex: "classe H", "aço", "NBR"), você DEVE adequar o dado e definir ACAO = "PREENCHER".

        POR OUTRO LADO, se a resposta indicar CLARAMENTE que a característica NÃO SE APLICA, é inexistente ou totalmente vazia, você DEVE definir ACAO = "REMOVER".
        Termos considerados como "Não Aplicável":
        - "NA", "N/A", "N.A", "N.A.", "N/D"
        - "Não aplicável", "Não se aplica", "Sem aplicação"
        - "Inexistente", "Não possui"
        - Traços simples ou duplos: "-", "--", "---"
        - "Idem", "Vide X" (Se não for possível resolver)

        Se a resposta cair na regra de exclusão acima, ignore as regras de tipo abaixo e force a remoção.

        REGRAS DE PROCESSAMENTO POR TIPO:
        1. CHAR (Texto):
           - Verifique se não está em branco. Se estiver vazio, ACAO = "REMOVER".
           - O campo RESPOSTA_ES é obrigatório apenas aqui.
           - SÍMBOLO deve ser sempre "AD".

        2. INT (Intervalo):
           - O campo 'SUBTIPO_INTERVALO' é OBRIGATÓRIO.
           - Analise o contexto (Pergunta e Texto de Ajuda) para escolher EXATAMENTE uma das opções: ["MINIMO / MAXIMO", "DE / PARA", "INICIO / FIM", "LIMITE INFERIOR / LIMITE SUPERIOR", "LIMITE BAIXO / LIMITE ALTO", "MARGEM INFERIOR / MARGEM SUPERIOR", "MAIOR A / MENOR A", "DESDE / ATE"]. Use "MINIMO / MAXIMO" como padrão.
           - RESPOSTA_PT_FINAL deve conter os dois valores separados por barra "/" (ex: "10,5 / 20,8"). E o valor menor deve ser indicado como MINIMO, DE, LIMITE INFERIOR, LIMITE BAIXO, MARGEM INFERIOR, MAIOR A, DESDE e o valor maior como MAXIMO, LIMITE ALTO, LIMITE SUPERIOR, MENOR A, MARGEM SUPERIOR, ATE e outras palavras que indiquem que é quantitativamente maior.

        3. NUM (Numérico Único):
           - Aceita apenas um valor (Lembre-se da regra da vírgula para decimais).
           - Se a resposta tiver múltiplos valores, escolha o mais representativo (pior caso ou nominal). Não adicione textos descritivos (como "max", "min", "ate") na resposta, apenas o valor numérico.

        4. LISTA (Seleção):
           - A resposta DEVE ser baseada nos valores presentes no campo 'VALORES_POSSIVEIS_MASTER'.
           - Lembre-se: múltiplos valores devem ser separados por ponto e vírgula (;).

        SAÍDA ESPERADA (JSON):
        Retorne um JSON puro contendo uma lista de objetos:
        [
            {
                "CARACTERISTICA_CHAVE": "Nome da característica (limpo)",
                "TIPO": "CHAR" | "INT" | "NUM" | "LISTA",
                "VALORES_PT": "...", (Preenchido se tipo LISTA)
                "SUBTIPO_INTERVALO": "MINIMO / MAXIMO" (ou null),
                "RESPOSTA_PT_FINAL": "...",
                "RESPOSTA_ES_FINAL": "...",
                "SIMBOLO": "Unidade (Ex: V, A, mm, m³/h)",
                "ACAO": "PREENCHER" ou "REMOVER"
            }
        ]
        """

        prompt_user = f"""
        Analise os dados abaixo referentes a um material técnico.
        Execute as regras de normalização e retorne o JSON solicitado.

        DADOS DE ENTRADA:
        {json.dumps(contexto_json, indent=2, ensure_ascii=False)}
        """

        safety_settings = {
            'HATE_SPEECH': 'BLOCK_NONE',
            'HARASSMENT': 'BLOCK_NONE',
            'SEXUALLY_EXPLICIT': 'BLOCK_NONE',
            'DANGEROUS': 'BLOCK_NONE'
        }

        # Lógica de Retry
        for i in range(3):
            try:
                # --- CORREÇÃO IMPORTANTE: generation_config PARA JSON ---
                model = genai.GenerativeModel(
                    'gemini-3.5-flash',
                    system_instruction=system_instruction,
                    safety_settings=safety_settings,
                    generation_config={"response_mime_type": "application/json"},
                )

                resp = model.generate_content(prompt_user)

                # Debug do texto bruto se falhar
                clean_json = self._limpar_json_ia(resp.text)

                if not clean_json:
                    if callback_log: callback_log(f"Retry {i+1}: IA retornou texto vazio.")
                    continue

                return json.loads(clean_json)

            except Exception as e:
                # Loga o erro real (400, 403, 429, 500)
                if callback_log: callback_log(f"Retry {i+1} Error: {e}")
                time.sleep(2)

        return None


# =============================================================================
# CLASSE 2: AUTOMAÇÃO WEB (SELENIUM) - VERSÃO FINAL BLINDADA
# =============================================================================
class TechSpecsAutomation:
    def __init__(self):
        self.driver = None
        self.wait = None
        self.cancel_requested = False

    def solicitar_parada(self):
        self.cancel_requested = True

    def iniciar(self):
        self.driver = webdriver.Chrome()
        self.driver.maximize_window()
        self.wait = WebDriverWait(self.driver, 20)

    def fechar(self):
        if self.driver: self.driver.quit()

    def abrir_portal(self, url):
        if self.driver: self.driver.get(url)

    # --- HELPERS DE INTERAÇÃO SEGURA ---
    def safe_click(self, locator):
        """Clica com Scroll + JS para evitar interceptação."""
        try:
            el = self.wait.until(EC.presence_of_element_located(locator))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
            time.sleep(0.5)
            self.wait.until(EC.element_to_be_clickable(locator))
            self.driver.execute_script("arguments[0].click();", el)
        except Exception as e:
            # Em produção, pode-se logar o erro, aqui passamos para manter fluxo
            pass

    def safe_send_keys_elem(self, element, text):
        """Preenche inputs limpando antes e enviando TAB no final."""
        try:
            # Garante visibilidade
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.2)
            element.click()  # Foco
            element.send_keys(Keys.CONTROL, "a")
            element.send_keys(Keys.BACKSPACE)
            element.send_keys(str(text))
            time.sleep(0.2)
            element.send_keys(Keys.TAB)
        except: pass

    def safe_send_keys_locator(self, locator, text):
        """Versão que recebe locator em vez de elemento."""
        try:
            el = self.wait.until(EC.presence_of_element_located(locator))
            self.safe_send_keys_elem(el, text)
        except: pass

    # --- HELPERS DE DADOS ---
    def normalizar_texto(self, texto):
        if not texto: return ""
        norm = unicodedata.normalize('NFD', str(texto))
        sem_acento = "".join(c for c in norm if unicodedata.category(c) != 'Mn')
        return " ".join(sem_acento.upper().split())

    def selecionar_dropdown_lista(self, element, texto):
        if not texto: return
        try:
            sel = Select(element)
            alvo = self.normalizar_texto(texto)

            # 1. Tentativa Exata Visível
            try:
                sel.select_by_visible_text(texto)
                return
            except: pass

            # 2. Tentativa Normalizada
            for opt in sel.options:
                if alvo in self.normalizar_texto(opt.text):
                    opt.click()
                    return
        except: pass

    def selecionar_dropdown_unidade(self, element, texto):
        if not texto: return
        try:
            sel = Select(element)
            target = f"({texto.strip().upper()})"
            for opt in sel.options:
                if target in opt.text.upper():
                    opt.click()
                    return
        except: pass

    def _preencher_input_com_auditoria(self, element, valor_alvo, elem_neutro, nome_campo="", callback_log=None):
        """Tenta preencher, audita se o site zerou o valor e usa JS Forçado como 2ª tentativa."""
        if not valor_alvo: return True

        # 1ª Tentativa: Digitação normal
        element.clear()
        self.safe_send_keys_elem(element, valor_alvo)
        if elem_neutro: elem_neutro.click()
        time.sleep(0.5)

        # Auditoria
        valor_atual = str(element.get_attribute("value")).strip()

        # Se o site rejeitou a primeira tentativa
        if (valor_atual == "0" or valor_atual == "") and str(valor_alvo).strip() != "0":

            # --- MENSAGEM VISUAL E PAUSA ESTRATÉGICA ---
            if callback_log:
                callback_log(f"   [!] O site rejeitou '{nome_campo}'. Tentando injeção forçada (JavaScript)...")
            time.sleep(1.5)  # Dá tempo para o usuário ver na tela e o JS do site assentar

            # 2ª Tentativa: Injeção Direta no DOM (Força Bruta)
            self.driver.execute_script(f"arguments[0].value = '{valor_alvo}';", element)
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", element)
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", element)
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));", element)
            if elem_neutro: elem_neutro.click()

            time.sleep(1.0)  # Pausa maior após a injeção para validar o resultado

            # Auditoria Final
            valor_atual_2 = str(element.get_attribute("value")).strip()
            if (valor_atual_2 == "0" or valor_atual_2 == "") and str(valor_alvo).strip() != "0":
                return False  # Desiste de vez

        return True

    def _pesquisar_e_abrir(self, pmib):
        """Navega, Pesquisa e Clica no Lápis com tratamento de StaleElement."""
        url_lista = "https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList"

        # 1. Garantir URL
        if self.driver.current_url != url_lista:
            self.driver.get(url_lista)
            time.sleep(3)

        # 2. Pesquisar (com Retry)
        locator_pesquisa = (By.XPATH, "//input[contains(@placeholder, 'Código')]")

        for i in range(3):
            try:
                campo = self.wait.until(EC.element_to_be_clickable(locator_pesquisa))
                campo.clear()
                time.sleep(0.5)
                campo.send_keys(pmib)
                time.sleep(0.5)
                campo.send_keys(Keys.ENTER)
                time.sleep(4)  # Espera tabela recarregar
                break
            except StaleElementReferenceException:
                time.sleep(1)
            except Exception:
                return False

        # 3. Clicar no Editar (com Retry)
        xpath_lapis = f"//span[text()='{pmib}']/ancestor::tr//i[contains(@class, 'fa-pencil')]/parent::a"

        for i in range(3):
            try:
                botao = self.wait.until(EC.presence_of_element_located((By.XPATH, xpath_lapis)))
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", botao)
                time.sleep(1)
                self.driver.execute_script("arguments[0].click();", botao)
                time.sleep(4)  # Espera abrir
                return True
            except StaleElementReferenceException:
                time.sleep(2)
            except TimeoutException:
                time.sleep(2)

        return False

    # --- FLUXO PRINCIPAL ---
    def processar_lista(self, lista_fichas, callback_log=None, callback_pause=None):
        pmibs_finalizados = []  # <--- NOVO: Lista para tracking

        for item in lista_fichas:
            # --- VERIFICAÇÃO DE PARADA ---
            if self.cancel_requested:
                if callback_log: callback_log("Robô Web interrompido pelo usuário!")
                break

            meta = item.get("METADATA", {})
            pmib = meta.get("PMIB")
            dados = item.get("DADOS_TRATADOS", [])

            # ---> NOVA VARIÁVEL: Guarda o que falhou na auditoria
            pendencias_manuais = []

            if callback_log: callback_log(f"Iniciando {pmib}...")

            try:
                # 1. Busca Robusta
                if not self._pesquisar_e_abrir(pmib):
                    if callback_log: callback_log(f"Erro: Ficha {pmib} não encontrada na busca.")
                    continue

                # 2. Entrar na Aba Specs
                loc_aba = (By.XPATH, "//button[@role='tab' and contains(., 'Características técnicas')]")
                self.safe_click(loc_aba)

                locator_tabela = (By.XPATH, "//div[contains(@id, 'TechnicalCharacteristics')]//table")
                try:
                    self.wait.until(EC.visibility_of_element_located(locator_tabela))
                except:
                    if callback_log: callback_log("Erro: Tabela de características não carregou.")
                    continue

                time.sleep(2)

                # Dicionário de dados para acesso rápido O(1)
                dict_dados = {self.normalizar_texto(d['CARACTERISTICA_CHAVE']): d for d in dados}

                # --- LOOP DE PAGINAÇÃO E LINHAS (Restaurado do Original) ---
                pagina_atual = 1
                while True:
                    if callback_log: callback_log(f"Processando Página {pagina_atual}...")

                    row_index = 0
                    while True:
                        # Recarrega a lista a cada iteração (CRÍTICO para evitar StaleElement)
                        rows = self.driver.find_elements(By.XPATH, "//div[contains(@id, 'TechnicalCharacteristics')]//table/tbody/tr")

                        if row_index >= len(rows):
                            break  # Fim da página atual

                        row = rows[row_index]
                        item_foi_excluido = False

                        try:
                            # Extrair nome da característica na tela
                            col_desc = row.find_element(By.XPATH, ".//td[contains(@data-header, 'Descrição')]")
                            txt_tela = col_desc.get_attribute("textContent")
                            match = re.search(r"^\s*\d+\s*-\s*(.*)", txt_tela)
                            chave_limpa = self.normalizar_texto(match.group(1) if match else txt_tela)

                            dado = dict_dados.get(chave_limpa)

                            if dado:
                                acao = dado.get("ACAO")

                                # --- CASO: REMOVER ---
                                if acao == "REMOVER":
                                    sucesso_exclusao = self._excluir_linha_segura(row, chave_limpa, callback_log)
                                    if sucesso_exclusao:
                                        item_foi_excluido = True
                                    # Se falhar, item_foi_excluido continua False e o iterador (row_index) será incrementado.
                                    # Isso impede que o robô trave eternamente tentando excluir a mesma linha com erro.

                                # --- CASO: PREENCHER ---
                                else:
                                    # Agora passamos o callback_log para a função poder avisar da 2ª tentativa
                                    sucesso_preenchimento = self._preencher_linha(row, dado, callback_log)
                                    if not sucesso_preenchimento:
                                        # Se a auditoria falhou, guarda os dados para avisar o usuário
                                        pendencias_manuais.append({
                                            "CHAVE": chave_limpa,
                                            "VALOR": dado.get("RESPOSTA_PT_FINAL", "N/A"),
                                            "UNIDADE": dado.get("SIMBOLO", "AD")
                                        })

                        except StaleElementReferenceException:
                            continue  # Tenta pegar a linha de novo
                        except Exception:
                            pass

                        # Se excluiu, NÃO incrementa (o item de baixo subiu). Se preencheu, incrementa.
                        if not item_foi_excluido:
                            row_index += 1

                    # --- PAGINAÇÃO ---
                    try:
                        btn_proximo = self.driver.find_element(By.XPATH, "//button[@aria-label='Ir para a página seguinte']")
                        # Verifica se está habilitado (em alguns frameworks é class disabled, aqui assumimos is_enabled)
                        if btn_proximo.is_enabled():
                            self.driver.execute_script("arguments[0].click();", btn_proximo)
                            time.sleep(3)
                            self.wait.until(EC.visibility_of_element_located(locator_tabela))
                            pagina_atual += 1
                        else:
                            break  # Última página
                    except:
                        break  # Botão não existe

                # 4. Relatório de Pendências da Auditoria
                if pendencias_manuais and callback_log:
                    callback_log("=========================================")
                    callback_log("⚠️ ATENÇÃO: O site bloqueou a digitação dos seguintes campos.")
                    callback_log("Por favor, preencha MANUALMENTE antes de salvar:")
                    for pendencia in pendencias_manuais:
                        callback_log(f" -> {pendencia['CHAVE']}: {pendencia['VALOR']} ({pendencia['UNIDADE']})")
                    callback_log("=========================================")

                # 5. Pausa Manual (Obrigatória)
                if callback_pause:
                    callback_pause(pmib)

                if callback_log: callback_log(f"Fim {pmib}.")
                pmibs_finalizados.append(pmib)  # <--- NOVO: Adiciona a ficha na lista de sucesso

            except Exception as e:
                if callback_log: callback_log(f"Erro geral {pmib}: {e}")

        return pmibs_finalizados  # <--- NOVO: Devolve a lista de sucesso para o Controller

    def _excluir_linha_segura(self, row, chave_limpa, callback_log=None):
        """Tenta clicar na lixeira e confirmar a exclusão. Retorna True se der certo, False se falhar."""
        try:
            # Encontra e clica na lixeira da linha atual
            btn_lixo = row.find_element(By.XPATH, './/i[contains(@class, "fa-trash")]/parent::a')
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_lixo)
            time.sleep(0.5)
            self.driver.execute_script("arguments[0].click();", btn_lixo)

            # Clica no botão CONFIRMAR do Popup
            loc_conf = (By.XPATH, '//button[@type="button" and text()="CONFIRMAR"]')
            self.safe_click(loc_conf)

            time.sleep(2.5)  # Pausa crucial para o site reconstruir a tabela HTML
            if callback_log: callback_log(f"Sucesso ao excluir item: {chave_limpa}")
            return True

        except Exception as e:
            if callback_log: callback_log(f"Falha ao excluir item {chave_limpa}: {e}")
            return False

    def _preencher_linha(self, row, dado, callback_log=None):
        """
        Preenche os campos e audita o resultado.
        Retorna True se sucesso, ou False se a inserção foi rejeitada pelo site.
        """
        tipo = dado.get("TIPO", "")
        val_pt = dado.get("RESPOSTA_PT_FINAL", "")
        nome_campo = dado.get("CARACTERISTICA_CHAVE", "Valor")  # Pega o nome para o Log
        sucesso_auditoria = True

        # Elemento Neutro para clicar fora
        try:
            elem_neutro = row.find_element(By.XPATH, ".//td[contains(@data-header, 'Descrição')]")
        except:
            elem_neutro = None

        try:
            if tipo == "CHAR":
                # PT (Sem auditoria pesada, campos textuais raramente dão problema)
                txt_pt = row.find_element(By.XPATH, './/textarea[contains(@id, "TextArea_ValuePT")]')
                txt_pt.clear(); self.safe_send_keys_elem(txt_pt, val_pt)
                if elem_neutro: elem_neutro.click()

                # ES
                val_es = dado.get("RESPOSTA_ES_FINAL", "")
                txt_es = row.find_element(By.XPATH, './/textarea[contains(@id, "TextArea_ValueES")]')
                txt_es.clear(); self.safe_send_keys_elem(txt_es, val_es)
                if elem_neutro: elem_neutro.click()

            elif tipo == "NUM":
                inp = row.find_element(By.XPATH, './/input[contains(@id, "NumberValue_Input")]')
                sucesso_auditoria = self._preencher_input_com_auditoria(inp, val_pt, elem_neutro, nome_campo, callback_log)

            elif tipo == "LISTA":
                sel = row.find_element(By.XPATH, './/select[contains(@id, "Dropdown1")]')
                self.selecionar_dropdown_lista(sel, val_pt)
                time.sleep(0.5)
                if elem_neutro: elem_neutro.click()
                # Em Listas vamos assumir que não zera por bug numérico, então sucesso.

            elif tipo == "INT":
                subtipo = dado.get("SUBTIPO_INTERVALO", "MINIMO / MAXIMO")
                sel_int = row.find_element(By.XPATH, './/select[contains(@id, "Dropdown_IntervalOptions")]')
                self.selecionar_dropdown_lista(sel_int, subtipo)
                time.sleep(0.5)

                vals = val_pt.split('/')
                v1 = vals[0].strip()
                v2 = vals[1].strip() if len(vals) > 1 else ""

                i_min = row.find_element(By.XPATH, './/input[contains(@id, "MinValue_Input")]')
                s1 = self._preencher_input_com_auditoria(i_min, v1, elem_neutro, f"{nome_campo} (Mín)", callback_log)

                i_max = row.find_element(By.XPATH, './/input[contains(@id, "MaxValue_Input")]')
                s2 = self._preencher_input_com_auditoria(i_max, v2, elem_neutro, f"{nome_campo} (Máx)", callback_log)

                # Se qualquer um dos dois (min/max) falhou, marca o item como falha
                if not s1 or not s2:
                    sucesso_auditoria = False

            # Unidade
            simb = dado.get("SIMBOLO")
            if simb:
                sel_unit = row.find_element(By.XPATH, './/select[contains(@id, "DropdownTCUnitsOfMeasurement")]')
                self.selecionar_dropdown_unidade(sel_unit, simb)

        except Exception as e:
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
            if caminho_status and pmibs_finalizados:
                import openpyxl
                try:
                    if callback_log: callback_log("A atualizar ficheiro _STATUS_PMIB...")
                    # Abre mantendo formatações e fórmulas (importante para não corromper o Master)
                    wb = openpyxl.load_workbook(caminho_status)
                    ws = wb["Lista de Materiais"]

                    # 1. Encontrar as colunas chaves
                    col_codigo = None
                    col_status = None
                    header_row = 1

                    # Procura o cabeçalho nas primeiras 15 linhas
                    for row_idx in range(1, 16):
                        for col_idx in range(1, ws.max_column + 1):
                            cell_val = str(ws.cell(row=row_idx, column=col_idx).value).strip()
                            if cell_val == "CÓDIGO PMIB":
                                col_codigo = col_idx
                                header_row = row_idx
                            elif cell_val == "CARACT. TÉCNICAS":
                                col_status = col_idx
                        if col_codigo and col_status:
                            break

                    if col_codigo and col_status:
                        # 2. Marcar cada PMIB concluído
                        for pmib in pmibs_finalizados:
                            # Trata a possibilidade de o Excel ter ' na frente do número
                            alvo_busca = [str(pmib), f"'{pmib}"]

                            for row_idx in range(header_row + 1, ws.max_row + 1):
                                cell_codigo = str(ws.cell(row=row_idx, column=col_codigo).value).strip()

                                if cell_codigo in alvo_busca:
                                    # Encontrou o primeiro match! Atualiza e sai do loop interno (só a 1ª ocorrência).
                                    ws.cell(row=row_idx, column=col_status).value = "COMPLETO"
                                    if callback_log: callback_log(f"   -> {pmib} marcado como COMPLETO.")
                                    break

                        wb.save(caminho_status)
                        if callback_log: callback_log("✅ Ficheiro _STATUS_PMIB salvo com sucesso!")
                    else:
                        if callback_log: callback_log("Aviso: Não encontrei as colunas 'CÓDIGO PMIB' ou 'CARACT. TÉCNICAS' para atualizar.")
                except Exception as ex:
                    if callback_log: callback_log(f"Erro ao tentar escrever no Excel de status: {ex}")

        except Exception as e:
            if callback_log: callback_log(f"Erro fatal na automação: {e}")
        finally:
            if callback_log: callback_log("Fim do processo de RPA.")
            self.automacao_ativa = None  # Limpa a referência ao terminar
