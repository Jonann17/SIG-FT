import os
import re
import json
import time
import pandas as pd
import unicodedata
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from selenium.webdriver.common.keys import Keys

from sigft import config
from sigft.core.excel import headers, pmib_codes, status_sheet
# CP 2.1 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 2): fábrica única de
# driver Chrome, substitui `webdriver.Chrome()` cru em
# `TechSpecsAutomation.iniciar` abaixo.
from sigft.core.rpa.selenium_engine import create_chrome_driver, SeleniumEngine
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
# CP 3.5 (Fase 3): o TEXTO do `system_instruction`/`prompt_user` de
# `_chamar_gemini_specs` abaixo mora em `sigft.core.llm.prompts`
# (`SYSTEM_TECH_SPECS`/`montar_tech_specs_user`).
from sigft.core.llm import prompts


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
            except Exception:
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
        try:
            resp = self._llm.generate(
                prompt_user,
                system=system_instruction,
                json_mode=True,
                tags={"modulo": "upload_tech_specs_backend", "tarefa": "tech_specs"},
            )
            return resp.parsed_json
        except Exception as e:
            if callback_log: callback_log(f"Erro ao chamar IA: {e}")
            return None


# =============================================================================
# CLASSE 2: AUTOMAÇÃO WEB (SELENIUM) - VERSÃO FINAL BLINDADA
# =============================================================================
class TechSpecsAutomation:
    def __init__(self):
        self.driver = None
        self.wait = None
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
        ganha o `engine` de verdade (`SeleniumEngine` sobre o MESMO
        `driver`/`wait`) -- `safe_click`/`_pesquisar_e_abrir`/
        `_excluir_linha_segura` abaixo passam a delegar para ele.
        """
        self.driver, self.wait = create_chrome_driver(wait_timeout=20)
        self.portal.engine = SeleniumEngine(self.driver, self.wait)

    def fechar(self):
        if self.driver: self.driver.quit()

    def abrir_portal(self, url):
        if self.driver: self.driver.get(url)

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

    def safe_send_keys_elem(self, element, text):
        """Preenche inputs limpando antes e enviando TAB no final."""
        try:
            # Garante visibilidade
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(PAUSA_SCROLL)
            element.click()  # Foco
            element.send_keys(Keys.CONTROL, "a")
            element.send_keys(Keys.BACKSPACE)
            element.send_keys(str(text))
            time.sleep(PAUSA_DIGITACAO)
            element.send_keys(Keys.TAB)
        except Exception: pass

    def safe_send_keys_locator(self, locator, text):
        """Versão que recebe locator em vez de elemento."""
        try:
            el = self.wait.until(EC.presence_of_element_located(locator))
            self.safe_send_keys_elem(el, text)
        except Exception: pass

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
            except Exception: pass

            # 2. Tentativa Normalizada
            for opt in sel.options:
                if alvo in self.normalizar_texto(opt.text):
                    opt.click()
                    return
        except Exception: pass

    def selecionar_dropdown_unidade(self, element, texto):
        if not texto: return
        try:
            sel = Select(element)
            target = f"({texto.strip().upper()})"
            for opt in sel.options:
                if target in opt.text.upper():
                    opt.click()
                    return
        except Exception: pass

    def _preencher_input_com_auditoria(self, element, valor_alvo, elem_neutro, nome_campo="", callback_log=None):
        """Tenta preencher, audita se o site zerou o valor e usa JS Forçado como 2ª tentativa."""
        if not valor_alvo: return True

        # 1ª Tentativa: Digitação normal
        element.clear()
        self.safe_send_keys_elem(element, valor_alvo)
        if elem_neutro: elem_neutro.click()
        time.sleep(PAUSA_AUDITORIA)

        # Auditoria
        valor_atual = str(element.get_attribute("value")).strip()

        # Se o site rejeitou a primeira tentativa
        if (valor_atual == "0" or valor_atual == "") and str(valor_alvo).strip() != "0":

            # --- MENSAGEM VISUAL E PAUSA ESTRATÉGICA ---
            if callback_log:
                callback_log(f"   [!] O site rejeitou '{nome_campo}'. Tentando injeção forçada (JavaScript)...")
            time.sleep(PAUSA_INJECAO_JS)  # Dá tempo para o usuário ver na tela e o JS do site assentar

            # 2ª Tentativa: Injeção Direta no DOM (Força Bruta)
            self.driver.execute_script(f"arguments[0].value = '{valor_alvo}';", element)
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", element)
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", element)
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));", element)
            if elem_neutro: elem_neutro.click()

            time.sleep(PAUSA_POS_INJECAO_JS)  # Pausa maior após a injeção para validar o resultado

            # Auditoria Final
            valor_atual_2 = str(element.get_attribute("value")).strip()
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

        for item in lista_fichas:
            # --- VERIFICAÇÃO DE PARADA ---
            if self.portal.deve_parar():
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
                except Exception:
                    if callback_log: callback_log("Erro: Tabela de características não carregou.")
                    continue

                time.sleep(PAUSA_CARGA_TABELA)

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
                            time.sleep(PAUSA_PAGINACAO)
                            self.wait.until(EC.visibility_of_element_located(locator_tabela))
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

                # 5. Pausa Manual (Obrigatória)
                if callback_pause:
                    callback_pause(pmib)

                if callback_log: callback_log(f"Fim {pmib}.")
                pmibs_finalizados.append(pmib)  # <--- NOVO: Adiciona a ficha na lista de sucesso

            except Exception as e:
                if callback_log: callback_log(f"Erro geral {pmib}: {e}")

        return pmibs_finalizados  # <--- NOVO: Devolve a lista de sucesso para o Controller

    def _excluir_linha_segura(self, row, chave_limpa, callback_log=None):
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
        sucesso = self.portal.excluir_linha_com_confirmacao(row)
        if callback_log:
            if sucesso:
                callback_log(f"Sucesso ao excluir item: {chave_limpa}")
            else:
                callback_log(f"Falha ao excluir item {chave_limpa}.")
        return sucesso

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
        except Exception:
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
                time.sleep(PAUSA_ANIMACAO)
                if elem_neutro: elem_neutro.click()
                # Em Listas vamos assumir que não zera por bug numérico, então sucesso.

            elif tipo == "INT":
                subtipo = dado.get("SUBTIPO_INTERVALO", "MINIMO / MAXIMO")
                sel_int = row.find_element(By.XPATH, './/select[contains(@id, "Dropdown_IntervalOptions")]')
                self.selecionar_dropdown_lista(sel_int, subtipo)
                time.sleep(PAUSA_ANIMACAO)

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
