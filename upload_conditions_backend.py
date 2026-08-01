import time
import openpyxl
import pandas as pd
import os
import json
import ast
from types import SimpleNamespace
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from sigft import config
from sigft.core.excel import headers, locking, pmib_codes, status_sheet
# CP 2.1 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 2): fábrica única de
# driver Chrome, substitui `webdriver.Chrome()` cru em
# `UploadAutomation.iniciar` abaixo.
from sigft.core.rpa.selenium_engine import create_chrome_driver, SeleniumEngine
# CP 2.2 (Fase 2): `safe_click`/`safe_send_keys`/`check_or_uncheck`/a busca-e-
# abertura inline de `processar_lista`/o stop-flag de `ConditionsProcessor` e
# `UploadAutomation` passam a delegar para `PMIBPortal`.
#
# CP 2.3 (Fase 2): os 11 `time.sleep(<literal>)` do arquivo viram
# constantes nomeadas (nenhum eliminado) -- ver
# docs/refatoracao/PLANO_REFATORACAO.md Fase 2 -> CP 2.3.
#
# CP 3.1 (Fase 3): `PAUSA_RETRY_IA_LONGA` REMOVIDA deste import -- o retry de
# IA (e o sleep entre tentativas) agora vive dentro de `LLMClient` (ver
# `sigft.core.llm.client.get_llm`); a constante continua existindo em
# `portal.py` (intocada), só este import é que fica sem uso dela.
from sigft.core.rpa.portal import (
    PMIBPortal,
    PAUSA_DIGITACAO,
    PAUSA_ENTRE_CAMPOS,
    PAUSA_FALLBACK_SALVAMENTO,
    PAUSA_SALVAMENTO,
)
# CP 3.1 (Fase 3): `google.generativeai` deixou de ser importado aqui --
# `ConditionsProcessor.processar_ia_lote` abaixo delega para `LLMClient`/
# `GeminiProvider` (ÚNICO lugar do projeto que importa `genai`).
from sigft.core.llm.client import get_llm
# CP 3.5 (Fase 3): o TEXTO do `system_prompt`/`user_prompt` de
# `processar_ia_lote` abaixo mora em `sigft.core.llm.prompts`
# (`SYSTEM_CONDICOES`/`montar_condicoes_user`).
from sigft.core.llm import prompts


# =============================================================================
# CLASSES DE SERVIÇO (BACKEND PURO)
# =============================================================================
class ConditionsProcessor:
    def __init__(self, api_key):
        self.api_key = api_key
        # CP 2.2: stop-flag delega para `PMIBPortal` -- construído SEM
        # engine, porque esta classe só chama a API do Gemini (não tem
        # driver/browser nenhum). `solicitar_parada`/`deve_parar` são os
        # únicos métodos de `PMIBPortal` que nunca tocam `self.engine`, então
        # isso é seguro -- ver docstring de `PMIBPortal.__init__` e
        # docs/refatoracao/PENDENCIAS.md.
        self.portal = PMIBPortal()
        # CP 3.1: `genai.configure(...)` sai daqui -- agora vive dentro de
        # `GeminiProvider` (chamado por `get_llm`), com o MESMO guard ("só
        # configura se api_key for truthy").
        self._llm = get_llm("condicoes", api_key)

    def solicitar_parada(self):
        self.portal.solicitar_parada()

    def carregar_lookup_status(self, caminho_status_pmib):
        sheet_name = 'Lista de Materiais'
        column_to_find = config.COL_CODIGO_PMIB
        try:
            # NOVO: dtype=str força a ler como texto puro, mantendo a precisão exata do Excel
            df = pd.read_excel(caminho_status_pmib, sheet_name=sheet_name, header=None, dtype=str)

            # CP 1.2: busca dinâmica de cabeçalho via core.excel.headers
            # (mesmo alcance do original: até as 10 primeiras linhas; usa
            # `.head(10)` antes de materializar em lista, como o original,
            # para não converter o arquivo inteiro à toa).
            header_row_index = headers.find_header_row(df.head(10).values.tolist(), column_to_find)
            if header_row_index is None:
                return None, "Coluna 'CÓDIGO PMIB' não encontrada."

            new_header = df.iloc[header_row_index]
            df = df[header_row_index+1:]
            df.columns = new_header

            if 'DESCRIÇÃO' not in df.columns:
                return None, "Coluna 'DESCRIÇÃO' não encontrada."
            if 'CONDIÇÕES' not in df.columns:
                df['CONDIÇÕES'] = ""
            else:
                df['CONDIÇÕES'] = df['CONDIÇÕES'].fillna("")

            # --- CORREÇÃO DO CÓDIGO PMIB (Apóstrofos, vírgula decimal e
            # zeros perdidos) --- CP 1.2: delega para a normalização única e
            # canônica (core.excel.pmib_codes.normalize_pmib), que cobre
            # TODOS os casos que este código só tratava parcialmente (só
            # completava zero quando faltava EXATAMENTE 1 dígito, e não
            # tratava vírgula decimal) — ver docs/refatoracao/PENDENCIAS.md.
            df[column_to_find] = df[column_to_find].apply(pmib_codes.normalize_pmib)

            df.set_index(column_to_find, inplace=True)
            return df, f"Carregado: {len(df)} registros."
        except Exception as e:
            return None, str(e)

    def extrair_dados_brutos_excel(self, caminho_planilha):
        try:
            wb = openpyxl.load_workbook(caminho_planilha, data_only=True)
            if "Ficha Técnica Padrão" not in wb.sheetnames:
                wb.close()
                return None
            ws = wb["Ficha Técnica Padrão"]
        except Exception:
            return None

        def get_val(ref):
            v = ws[ref].value
            return str(v).strip() if v is not None else ""

        dados = {}
        try:
            dados['descricao_breve'] = get_val('H6')
            dados["dimensoes"] = {"comprimento": get_val('H17'), "largura": get_val('H19'), "altura": get_val('H21')}
            dados["peso"] = {"liquido": get_val('P17'), "bruto": get_val('P19')}
            dados['controle_temperatura'] = get_val('M23')

            if get_val('Q21'): dados['sujeito_intemperie'] = "SIM"
            elif get_val('S21'): dados['sujeito_intemperie'] = "NÃO"
            else: dados['sujeito_intemperie'] = ""

            if get_val('G25'): dados['posicao_armazenamento'] = "Vertical"
            elif get_val('G27'): dados['posicao_armazenamento'] = "Horizontal"
            elif get_val('G29'): dados['posicao_armazenamento'] = "Indiferente"
            else: dados['posicao_armazenamento'] = ""

            prot = []
            if get_val('S27'): prot.append("UV")
            if get_val('S29'): prot.append("EL")
            if get_val('S25'): prot.append("SN")
            dados['protecao'] = prot

            if get_val('E33'): dados['nocivo'] = {"status": "Nocivo", "cuidado": get_val('M33')}
            elif get_val('E31'): dados['nocivo'] = {"status": "Não contém", "cuidado": ""}
            else: dados['nocivo'] = {"status": "", "cuidado": ""}

            dados['empilhamento'] = get_val('J35')
            cuid_txt = get_val('J36')
            dados['outros_cuidados'] = {"status": "SIM" if cuid_txt else "NÃO", "cuidados": cuid_txt}

            dados['embalagem_transp'] = get_val('M42')
            dados['posicao_icagem'] = get_val('M45')
            dados['cuidad_preserv'] = get_val('M52')
            dados['limpeza_secagem'] = get_val('M54')
            dados['ferramentas'] = get_val('M56')
            dados['legislacao'] = get_val('M63')
            dados['descarte'] = get_val('M65')

            if get_val('E69'): dados['perigoso_10004'] = "SIM"
            elif get_val('J69'): dados['perigoso_10004'] = "NÃO"
            else: dados['perigoso_10004'] = ""

            log_st = ""
            if get_val('P69'): log_st = "NÃO"
            elif get_val('T69'): log_st = "SIM"
            dados['logistica_reversa'] = {"status": log_st, "logistica_reversa": get_val('N71') if log_st == "SIM" else ""}

            wb.close()
            return dados
        except Exception:
            wb.close()
            return None

    def processar_ia_lote(self, lista_caminhos, df_status, callback_log=None):
        fichas_processadas = []
        # CP 1.2: prefixo de contrato deriva de config.PREFIXO_CONTRATO (era
        # hardcoded "4500063671" aqui); ver
        # core.excel.pmib_codes.extract_contract_pmib_code, usada abaixo.

        # CP 3.5 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 3): o TEXTO
        # deste system prompt (estático -- antes embutido aqui) agora mora em
        # `sigft.core.llm.prompts.SYSTEM_CONDICOES`.
        system_prompt = prompts.SYSTEM_CONDICOES

        # CP 3.1: `safety_settings` (BLOCK_NONE) sai daqui -- agora vive
        # dentro de `GeminiProvider` (aplicado a TODA chamada, não só a
        # `condicoes`/`tech_specs` -- ver docs/refatoracao/PENDENCIAS.md).

        for caminho in lista_caminhos:
            if self.portal.deve_parar():
                if callback_log: callback_log("Processamento de IA interrompido pelo usuário.")
                break  # Sai do loop principal

            nome_arquivo = os.path.basename(caminho)
            pmib_codigo = pmib_codes.extract_contract_pmib_code(caminho)
            if not pmib_codigo:
                if callback_log: callback_log(f"Ignorado (Sem PMIB): {nome_arquivo}")
                continue

            try:
                status_atual = df_status.loc[pmib_codigo, 'CONDIÇÕES']

                # Se houver PMIBs duplicados na planilha, o Pandas retorna uma Series.
                # Seguindo sua regra, pegamos apenas a primeira célula.
                if isinstance(status_atual, pd.Series):
                    status_atual = status_atual.iloc[0]

                if str(status_atual).strip().upper() == "COMPLETO":
                    if callback_log: callback_log(f"PMIB {pmib_codigo} já COMPLETO.")
                    continue
            except KeyError:
                pass

            dados_brutos = self.extrair_dados_brutos_excel(caminho)
            if not dados_brutos: continue

            try:
                descricao = df_status.loc[pmib_codigo, 'DESCRIÇÃO']

                # Mesma proteção contra duplicatas para a descrição não ir "suja" para a IA
                if isinstance(descricao, pd.Series):
                    descricao = descricao.iloc[0]
            except:
                descricao = dados_brutos.get('descricao_breve', 'N/A')

            dados_api_input = {
                "pmib_codigo": pmib_codigo,
                'Descrição do material': descricao,
                "dimensoes": dados_brutos.get("dimensoes"),
                'controle_temperatura': dados_brutos.get("controle_temperatura"),
                "posicao_armazenamento": dados_brutos.get("posicao_armazenamento"),
                "nocivo": dados_brutos.get("nocivo"),
                "peso": dados_brutos.get("peso"),
                "sujeito_intemperie": dados_brutos.get("sujeito_intemperie"),
                "protecao": dados_brutos.get("protecao"),
                "empilhamento": dados_brutos.get("empilhamento"),
                "outros_cuidados": dados_brutos.get("outros_cuidados"),
                "embalagem_transp": dados_brutos.get("embalagem_transp"),
                "posicao_icagem": dados_brutos.get("posicao_icagem"),
                "cuidad_preserv": dados_brutos.get("cuidad_preserv"),
                "limpeza_secagem": dados_brutos.get("limpeza_secagem"),
                "ferramentas": dados_brutos.get("ferramentas"),
                "legislacao": dados_brutos.get("legislacao"),
                "perigoso_10004": dados_brutos.get("perigoso_10004"),
                "descarte": dados_brutos.get("descarte"),
                "logistica_reversa": dados_brutos.get("logistica_reversa")
            }

            # CP 3.5: o TEXTO deste prompt de usuário agora mora em
            # `sigft.core.llm.prompts.montar_condicoes_user` -- a
            # serialização do JSON continua aqui (só o texto muda de
            # arquivo, resultado em runtime é byte-idêntico).
            dados_api_input_json = json.dumps(dados_api_input, indent=2, ensure_ascii=False)
            user_prompt = prompts.montar_condicoes_user(dados_api_input_json)

            # CP 3.1: retry (3 tentativas, 30s entre elas) + limpeza/parse do
            # JSON da resposta agora vivem dentro de `LLMClient.generate()`
            # (`self._llm`, resolvido em `__init__` via
            # `get_llm("condicoes", ...)`) -- este bloco vira uma única
            # chamada com um try/except fino. Preserva os logs POR FICHA
            # ("Enviando ... para API", "Sucesso API", "Falha definitiva no
            # PMIB ...") -- só os logs GRANULARES por TENTATIVA ("Tentativa
            # N/3...", "Aguardando 30 segundos...", "Erro na tentativa
            # N...") deixam de existir, já que o retry passa a acontecer
            # dentro do `LLMClient`, sem hook de log por tentativa -- ver
            # docs/refatoracao/PENDENCIAS.md.
            try:
                if callback_log: callback_log(f"Enviando {pmib_codigo} para API...")
                resp = self._llm.generate(
                    user_prompt,
                    system=system_prompt,
                    tags={"modulo": "upload_conditions_backend", "tarefa": "condicoes"},
                )
                res_json = resp.parsed_json
                res_json["pmib_codigo"] = pmib_codigo
                fichas_processadas.append(res_json)
                if callback_log: callback_log(f"Sucesso API: {pmib_codigo}")
            except Exception as e:
                if callback_log: callback_log(f"Falha definitiva no PMIB {pmib_codigo}: {e}")

        return fichas_processadas

    def salvar_excel_intermediario(self, fichas, caminho_salvar):
        try:
            df = pd.DataFrame(fichas)
            df.to_excel(caminho_salvar, index=False)
            return True, f"Salvo em: {caminho_salvar}"
        except Exception as e:
            return False, str(e)

    # -----------------------------------------------------------------
    # NOVOS MÉTODOS DE SALVAMENTO (INTEGRAÇÃO COMPLETA)
    # -----------------------------------------------------------------
    def salvar_novo_arquivo(self, fichas_novas, caminho_destino):
        """Salva uma lista de dicionários em um novo arquivo Excel."""
        try:
            df = pd.DataFrame(fichas_novas)
            df.to_excel(caminho_destino, index=False)
            return True, f"Arquivo criado com sucesso:\n{caminho_destino}"
        except Exception as e:
            return False, f"Erro ao criar arquivo: {e}"

    def anexar_a_arquivo_existente(self, fichas_novas, caminho_existente):
        """
        Lê um Excel existente, anexa os novos dados, remove duplicatas (mantendo a mais recente)
        e salva no mesmo local.
        """
        try:
            # 1. Carregar dados antigos
            try:
                df_antigo = pd.read_excel(caminho_existente)
            except Exception as e:
                return False, f"Erro ao ler arquivo existente: {e}"

            # 2. Preparar dados novos
            df_novo = pd.DataFrame(fichas_novas)

            # 3. Concatenar
            df_final = pd.concat([df_antigo, df_novo], ignore_index=True)

            # 4. Remover duplicatas (baseado no código PMIB)
            # keep='last' garante que a versão recém processada pela IA substitua a antiga
            if 'pmib_codigo' in df_final.columns:
                df_final.drop_duplicates(subset=['pmib_codigo'], keep='last', inplace=True)

            # 5. Salvar -- CP 1.3: delega para locking.save_with_retry (única
            # implementação de retry de PermissionError). `pandas.DataFrame`
            # não tem `.save(path)`; adapta com um objeto duck-typed mínimo.
            # `max_attempts=1` preserva o comportamento ORIGINAL desta
            # variante (log + sai): nenhuma retentativa, aborta na 1ª
            # PermissionError (relevantada e capturada pelo `except`
            # abaixo, exatamente como antes).
            _adaptador_save = SimpleNamespace(save=lambda caminho: df_final.to_excel(caminho, index=False))
            locking.save_with_retry(_adaptador_save, caminho_existente, max_attempts=1)

            return True, f"Dados anexados com sucesso!\nTotal de registros agora: {len(df_final)}"

        except PermissionError:
            return False, "Erro de Permissão: O arquivo Excel está aberto. Feche-o e tente novamente."
        except Exception as e:
            return False, f"Erro ao anexar dados: {e}"


# =============================================================================
# CLASSE DE AUTOMAÇÃO (SELENIUM)
# =============================================================================
class UploadAutomation:
    def __init__(self):
        self.driver = None
        self.wait = None
        # CP 2.2: `self.portal` (SEM engine ainda) já nasce aqui -- não só em
        # `iniciar()` -- para que `solicitar_parada()` continue seguro de
        # chamar a QUALQUER momento, inclusive ANTES de `iniciar()` rodar
        # (cenário real: `frontend.py` atribui a instância a
        # `self.automacao_ativa` e só DEPOIS a thread de trabalho chega a
        # `iniciar()`; o botão "Parar" pode disparar nesse meio-tempo).
        # `iniciar()` abaixo só ANEXA o engine à MESMA instância de
        # `PMIBPortal` (preserva um stop-flag já setado, se houver) -- ver
        # docs/refatoracao/PENDENCIAS.md.
        self.portal = PMIBPortal()

    def solicitar_parada(self):
        self.portal.solicitar_parada()

    def iniciar(self):
        """CP 2.1: a criação em si (Chrome + maximize + WebDriverWait(20s))
        agora vem de `create_chrome_driver` (única fábrica, ver
        core/rpa/selenium_engine.py) — timeout preservado EXATAMENTE como
        antes (20s).

        CP 2.2: `self.portal` (já existente desde `__init__`, ver acima)
        ganha o `engine` de verdade (`SeleniumEngine` sobre o MESMO
        `driver`/`wait`) -- `safe_click`/`safe_send_keys`/`check_or_uncheck`/
        `processar_lista` abaixo passam a delegar para ele.
        """
        self.driver, self.wait = create_chrome_driver(wait_timeout=20)
        self.portal.engine = SeleniumEngine(self.driver, self.wait)
        return self.driver

    # --- NOVO MÉTODO PARA CORRIGIR O ERRO DA URL DATA:, ---
    def abrir_portal(self, url):
        """Carrega a URL fornecida no navegador já aberto."""
        if self.driver:
            self.driver.get(url)
    # ------------------------------------------------------

    def fechar(self):
        if self.driver:
            self.driver.quit()

    def safe_click(self, locator):
        """CP 2.2: DELEGADOR FINO -- a mecânica real agora vive em
        `PMIBPortal.safe_click`/`SeleniumEngine.click` (um único lugar).
        `locator` continua aceito como tupla `(By.XPATH, xpath)` -- é assim
        que os MUITOS call sites internos desta classe já chamam hoje; a
        string XPath é extraída aqui antes de repassar."""
        seletor = locator[1] if isinstance(locator, tuple) else locator
        self.portal.safe_click(seletor)

    def safe_send_keys(self, locator, text):
        """CP 2.2: DELEGADOR FINO para `PMIBPortal.safe_fill`/
        `SeleniumEngine.fill` -- mesma extração de XPath de `safe_click`
        acima."""
        seletor = locator[1] if isinstance(locator, tuple) else locator
        self.portal.safe_fill(seletor, text)

    def check_or_uncheck(self, locator, should_check):
        """CP 2.2: DELEGADOR FINO para `PMIBPortal.check_or_uncheck` --
        mesma extração de XPath de `safe_click`/`safe_send_keys` acima."""
        seletor = locator[1] if isinstance(locator, tuple) else locator
        self.portal.check_or_uncheck(seletor, should_check)

    def processar_lista(self, lista_fichas, caminho_status, callback_ask=None, callback_log=None, callback_pause=None):
        url = "https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList"
        # O 'driver.get(url)' foi removido do início daqui porque agora
        # o App chama 'abrir_portal' ANTES de pedir o login.

        for ficha in lista_fichas:
            if self.portal.deve_parar():
                if callback_log: callback_log("Automação Web interrompida pelo usuário.")
                break  # Quebra o loop principal e vai para o finally de fechamento

            pmib = ficha['pmib_codigo']
            if callback_log: callback_log(f"Processando {pmib}...")

            try:
                # 1. Busca e abre a ficha em modo de edição.
                #
                # CP 2.2: delega para `PMIBPortal.pesquisar_e_abrir` com os
                # seletores EXATOS que este módulo já usava (placeholder
                # completo do campo de busca; ícone `fa-pencil-square-o`,
                # DIFERENTE de `fa-pencil` usado por `apagar_lmr`/
                # `upload_tech_specs`) -- ver docstring de `PMIBPortal.
                # pesquisar_e_abrir`. O retorno `bool` é intencionalmente
                # DESCARTADO aqui: o ORIGINAL não tinha NENHUM sinal de
                # sucesso/falha nesta etapa (`safe_click`/`safe_send_keys`
                # sempre engoliam exceção silenciosamente; `driver.get(url)`
                # não falha por si só) -- preservado tal qual (mesmo silêncio
                # de antes, não uma correção deste checkpoint); ver
                # docs/refatoracao/PENDENCIAS.md.
                self.portal.pesquisar_e_abrir(
                    pmib,
                    busca_xpath="//input[@placeholder='Código, Nome ES/PT pela Ficha Técnica, Código do projeto e/ou contrato']",
                    lapis_xpath_template="//span[text()='{pmib}']/ancestor::tr//a[.//i[contains(@class, 'fa-pencil-square-o')]]",
                )

                # --- ABA 1: CONDIÇÕES (ARMAZENAMENTO) ---
                try:
                    self.safe_click((By.XPATH, '//*[@id="b10-Conditions_Header"]/button'))
                except Exception as e:
                    if callback_log: callback_log(f"ERRO: Não abriu aba Condições. {e}")
                    continue  # Pula ficha se falhar a aba principal

                try:
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b1-Input_PackingLength"]'), ficha["dimensoes"]["comprimento"])
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b1-Input_PackagingWidth"]'), ficha["dimensoes"]["largura"])
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b1-Input_PackagingHeight"]'), ficha["dimensoes"]["altura"])
                except Exception as e:
                    if callback_log: callback_log(f"Aviso: Falha nas Dimensões. {e}")

                try:
                    controle_temp_data = ficha["controle_temperatura"]
                    if controle_temp_data["necessidade"] == "SIM":
                        self.safe_click((By.XPATH, '//*[@id="b10-b17-b1-RadioButton5-input"]'))
                        if controle_temp_data["climatizacao"]["ativo"]:
                            loc_check_clima = (By.XPATH, '//*[@id="b10-b17-b1-Checkbox4"]')
                            self.check_or_uncheck(loc_check_clima, True)
                            check_clima = self.wait.until(EC.element_to_be_clickable(loc_check_clima))
                            check_clima.send_keys(Keys.TAB)
                            time.sleep(PAUSA_DIGITACAO)
                            campo_temp_max = self.driver.switch_to.active_element
                            campo_temp_max.send_keys(controle_temp_data["climatizacao"]["temp_max"])
                            time.sleep(PAUSA_ENTRE_CAMPOS)
                            campo_temp_max.send_keys(Keys.TAB)
                            time.sleep(PAUSA_DIGITACAO)
                            campo_temp_min = self.driver.switch_to.active_element
                            campo_temp_min.send_keys(controle_temp_data["climatizacao"]["temp_min"])
                            time.sleep(PAUSA_ENTRE_CAMPOS)
                        if controle_temp_data["umidade"]["ativo"]:
                            loc_check_umid = (By.XPATH, '//*[@id="b10-b17-b1-Checkbox5"]')
                            self.check_or_uncheck(loc_check_umid, True)
                            check_umid = self.wait.until(EC.element_to_be_clickable(loc_check_umid))
                            check_umid.send_keys(Keys.TAB)
                            time.sleep(PAUSA_DIGITACAO)
                            campo_hr_max = self.driver.switch_to.active_element
                            campo_hr_max.send_keys(controle_temp_data["umidade"]["hr_max"])
                            time.sleep(PAUSA_ENTRE_CAMPOS)
                            campo_hr_max.send_keys(Keys.TAB)
                            time.sleep(PAUSA_DIGITACAO)
                            campo_hr_min = self.driver.switch_to.active_element
                            campo_hr_min.send_keys(controle_temp_data["umidade"]["hr_min"])
                            time.sleep(PAUSA_ENTRE_CAMPOS)
                    else:
                        self.safe_click((By.XPATH, '//*[@id="b10-b17-b1-RadioButton4-input"]'))
                except Exception as e:
                    if callback_log: callback_log(f"Aviso: Falha em Temperatura. {e}")

                try:
                    posicoes = {
                        "Vertical": (By.XPATH, '//*[@id="b10-b17-b1-RadioButton-input"]'),
                        "Horizontal": (By.XPATH, '//*[@id="b10-b17-b1-RadioButton7-input"]'),
                        "Indiferente": (By.XPATH, '//*[@id="b10-b17-b1-RadioButton8-input"]')
                    }
                    if ficha.get("posicao_armazenamento") in posicoes:
                        self.safe_click(posicoes[ficha["posicao_armazenamento"]])
                except Exception as e:
                    if callback_log: callback_log(f"Aviso: Falha na Posição. {e}")

                try:
                    nocivo_data = ficha["nocivo"]
                    if nocivo_data["status"] == "Nocivo":
                        self.safe_click((By.XPATH, '//*[@id="b10-b17-b1-RadioButton2-input"]'))
                        self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b1-TextArea_StorageCareES"]'), nocivo_data["cuidado_es"])
                        self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b1-TextArea_StorageCarePT"]'), nocivo_data["cuidado_pt"])
                    else:
                        self.safe_click((By.XPATH, '//*[@id="b10-b17-b1-RadioButton1-input"]'))
                except Exception as e:
                    if callback_log: callback_log(f"Aviso: Falha em Nocivo. {e}")

                try:
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b1-Input_LiquidWeight"]'), ficha["peso"]["liquido"])
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b1-Input_GrossWeight"]'), ficha["peso"]["bruto"])
                except Exception as e:
                    if callback_log: callback_log(f"Aviso: Falha nos Pesos. {e}")

                if ficha["controle_temperatura"]["necessidade"] == "NÃO":
                    try:
                        self.check_or_uncheck((By.XPATH, '//*[@id="b10-b17-b1-Checkbox3"]'), ficha.get("sujeito_intemperie") == "SIM")
                    except Exception as e:
                        if callback_log: callback_log(f"Aviso: Falha em Intempérie. {e}")

                try:
                    mapa_protecao = {
                        "SN": (By.XPATH, '//*[@id="b10-b17-b1-Checkbox6"]'),
                        "UV": (By.XPATH, '//*[@id="b10-b17-b1-Checkbox7"]'),
                        "EL": (By.XPATH, '//*[@id="b10-b17-b1-Checkbox8"]')
                    }
                    for loc in mapa_protecao.values():
                        self.check_or_uncheck(loc, False)
                    for prot in ficha.get("protecao", []):
                        if prot in mapa_protecao:
                            self.check_or_uncheck(mapa_protecao[prot], True)
                except Exception as e:
                    if callback_log: callback_log(f"Aviso: Falha na Proteção. {e}")

                try:
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b1-Input_Stacking"]'), ficha.get("empilhamento", ""))
                except Exception as e:
                    if callback_log: callback_log(f"Aviso: Falha no Empilhamento. {e}")

                try:
                    cuidados_data = ficha["outros_cuidados"]
                    if cuidados_data["status"] == "SIM":
                        self.safe_click((By.XPATH, '//*[@id="b10-b17-b1-RadioButton6-input"]'))
                        self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b1-TextArea_OtherCareES"]'), cuidados_data["cuidado_es"])
                        self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b1-TextArea_OtherCarePT"]'), cuidados_data["cuidado_pt"])
                    else:
                        self.safe_click((By.XPATH, '//*[@id="b10-b17-b1-RadioButton3-input"]'))
                except Exception as e:
                    if callback_log: callback_log(f"Aviso: Falha em Outros Cuidados. {e}")

                self.safe_save_with_pause((By.XPATH, '//*[@id="b10-b17-b1-b35-Button"]/button'), "Armazenamento", callback_log, callback_pause)

                # --- ABA 2: TRANSPORTE ---
                try:
                    self.safe_click((By.XPATH, '//*[@id="b10-b17-Title"]/div[3]'))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b3-TextArea_TransportPackagingES"]'), ficha.get("embalagem_transp_es", ""))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b3-TextArea_TransportPackagingPT"]'), ficha.get("embalagem_transp_pt", ""))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b3-TextArea_PositionCareES"]'), ficha.get("posicao_icagem_es", ""))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b3-TextArea_PositionCarePT"]'), ficha.get("posicao_icagem_pt", ""))
                except Exception as e:
                    if callback_log: callback_log(f"Aviso: Falha na aba Transporte. {e}")

                self.safe_save_with_pause((By.XPATH, '//*[@id="b10-b17-$b3"]/div[3]/button'), "Transporte", callback_log, callback_pause)

                # --- ABA 3: MANUTENÇÃO ---
                try:
                    self.safe_click((By.XPATH, '//*[@id="b10-b17-Title"]/div[4]'))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b4-TextArea_PreservationCareES"]'), ficha.get("cuidad_preserv_es", ""))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b4-TextArea_PreservationCarePT"]'), ficha.get("cuidad_preserv_pt", ""))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b4-TextArea_CleaningMethodES"]'), ficha.get("limpeza_secagem_es", ""))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b4-TextArea_CleaningMethodPT"]'), ficha.get("limpeza_secagem_pt", ""))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b4-TextArea_ToolPreservationES"]'), ficha.get("ferramentas_es", ""))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b4-TextArea_ToolPreservationPT"]'), ficha.get("ferramentas_pt", ""))
                except Exception as e:
                    if callback_log: callback_log(f"Aviso: Falha na aba Manutenção. {e}")

                self.safe_save_with_pause((By.XPATH, '//*[@id="b10-b17-$b4"]/div[4]/button'), "Manutenção", callback_log, callback_pause)

                # --- ABA 4: DESCARTE ---
                try:
                    self.safe_click((By.XPATH, '//*[@id="b10-b17-Title"]/div[5]'))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b5-TextArea_TypeLegislationES"]'), ficha.get("legislacao_es", ""))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b5-TextArea_TypeLegislationPT"]'), ficha.get("legislacao_pt", ""))

                    if ficha.get("perigoso_10004") == "SIM":
                        self.safe_click((By.XPATH, '//*[@id="b10-b17-b5-RadioButton1-input"]'))
                    else:
                        self.safe_click((By.XPATH, '//*[@id="b10-b17-b5-RadioButton2-input"]'))

                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b5-TextArea_DiscardTypeES"]'), ficha.get("descarte_es", ""))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b5-TextArea_DiscardTypePT"]'), ficha.get("descarte_pt", ""))

                    logistica_rev = ficha.get("logistica_reversa", {})
                    if logistica_rev.get("status") == "SIM":
                        self.safe_click((By.XPATH, '//*[@id="b10-b17-b5-Applies-input"]'))
                        self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b5-TextArea_ReserveLogisticES"]'), logistica_rev.get("logistica_reversa_es", ""))
                        self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b5-TextArea_ReserveLogisticPT"]'), logistica_rev.get("logistica_reversa_pt", ""))
                    else:
                        self.safe_click((By.XPATH, '//*[@id="b10-b17-b5-DoesNotApply-input"]'))
                except Exception as e:
                    if callback_log: callback_log(f"Aviso: Falha na aba Descarte. {e}")

                self.safe_save_with_pause((By.XPATH, '//*[@id="b10-b17-$b5"]/div[5]/button'), "Descarte", callback_log, callback_pause)

                if callback_log: callback_log(f"{pmib} concluído no portal.")
                self.atualizar_status_excel(caminho_status, pmib, "COMPLETO", callback_log, callback_ask)

            except Exception as e:
                if callback_log: callback_log(f"!!! ERRO CRÍTICO processando {pmib}: {e} !!!")
                try:
                    self.driver.save_screenshot(f"erro_web_{pmib}.png")
                    if callback_log: callback_log(f"Evidência salva: erro_web_{pmib}.png")
                except:
                    pass

    def safe_save_with_pause(self, locator, section_name, callback_log=None, callback_pause=None):
        """Tenta salvar. Se der erro, usa o callback_pause para travar a execução até o usuário intervir na UI."""
        try:
            if callback_log: callback_log(f"Salvando {section_name}...")
            self.safe_click(locator)
            time.sleep(PAUSA_SALVAMENTO)
        except Exception as e:
            if callback_log: callback_log(f"Falha ao salvar {section_name}. Aguardando intervenção manual.")
            if callback_pause:
                callback_pause(section_name)  # Chama o Frontend para mostrar a janela e pausar
            else:
                time.sleep(PAUSA_FALLBACK_SALVAMENTO)  # Fallback caso falte o callback

    def atualizar_status_excel(self, caminho, pmib, status, callback_log=None, callback_ask=None):
        """Atualiza o Excel com loop de retentativa caso esteja aberto.

        CP 1.3: cabeçalho/linha/marcação delegam para
        `core.excel.status_sheet.StatusPMIB`; o retry de `PermissionError`
        (variante INTERATIVA do diagnóstico -- ver `core.excel.locking`)
        delega para `locking.save_with_retry` via `StatusPMIB.salvar`.

        NOTA DE COMPORTAMENTO (ver docs/refatoracao/PENDENCIAS.md): o laço
        original recarregava o workbook INTEIRO (e reaplicava a busca de
        cabeçalho/edição de célula) a cada retentativa, dentro do próprio
        `while True`. Aqui o workbook é carregado e a célula marcada UMA
        única vez; só o `wb.save(caminho)` retenta. Equivalente no cenário
        real (usuário fecha o Excel e clica "tentar novamente"); a
        diferença é só teórica.
        """
        pmib_alvo = str(pmib).strip()

        try:
            painel = status_sheet.StatusPMIB(caminho, config.ABA_LISTA_MATERIAIS)
            # 1. Busca dinâmica de Cabeçalho (Varre as 15 primeiras linhas,
            #    49 colunas) -- mesmo alcance do original.
            painel.abrir(
                keywords={config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB, config.COL_CONDICOES: config.COL_CONDICOES},
                max_row=15,
                max_col=49,
            )

            # Fallback caso não encontre os nomes exatos (mesmas colunas
            # fixas 8/10 do original).
            painel.col_map.setdefault(config.COL_CODIGO_PMIB, 8)
            painel.col_map.setdefault(config.COL_CONDICOES, 10)
            header_row = painel.header_row if painel.header_row is not None else 1

            # 2. Busca varrendo da linha do cabeçalho pra baixo -- 3.
            #    Blindagem contra Perda de Precisão (o segredo do .1165)
            #    via `pmib_codes.normalize_pmib` (dentro de `buscar_linha`).
            linha = painel.buscar_linha(pmib_alvo, header_row=header_row)

            if linha is not None:
                # 4. Grava o status.
                painel.marcar_linha(linha, {config.COL_CONDICOES: True}, valor=status)

                def _on_locked(attempt, exc):
                    if callback_log:
                        callback_log("Erro: Arquivo Excel aberto.")
                    if callback_ask:
                        # Envia a requisição para a UI perguntando o que
                        # fazer e aguarda resposta.
                        resposta_retry = callback_ask("ARQUIVO_BLOQUEADO")
                        if not resposta_retry:
                            if callback_log:
                                callback_log("Salvamento ignorado pelo usuário.")
                        return bool(resposta_retry)
                    return False  # Fallback: sem callback_ask, não retenta.

                try:
                    painel.salvar(on_locked=_on_locked)
                except PermissionError:
                    # Usuário optou por não retentar (ou não havia
                    # callback_ask) -- já logado em `_on_locked` acima.
                    painel.fechar()
                    return

                if callback_log:
                    callback_log(f"Excel atualizado para COMPLETO: {pmib_alvo}")
            else:
                if callback_log:
                    callback_log(f"Aviso Crítico: PMIB {pmib_alvo} NÃO encontrado na planilha _STATUS. (Não pôde salvar).")

            painel.fechar()

        except Exception as e:
            if callback_log:
                callback_log(f"Erro ao atualizar Excel: {e}")
