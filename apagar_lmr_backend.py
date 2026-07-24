import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException


# =============================================================================
# CLASSE DE AUTOMAÇÃO - APAGAR LMR
# =============================================================================
class ApagarLMRAutomation:
    def __init__(self):
        self.driver = None
        self.wait = None
        self.url_inicial = 'https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList'

    def iniciar_driver(self):
        """Inicia o navegador Chrome."""
        self.driver = webdriver.Chrome()
        self.driver.maximize_window()
        self.wait = WebDriverWait(self.driver, 20)
        return self.driver

    def fechar_driver(self):
        if self.driver:
            self.driver.quit()

    def abrir_portal(self):
        if self.driver:
            self.driver.get(self.url_inicial)

    # --- HELPERS DE NAVEGAÇÃO ---
    def safe_click(self, locator):
        try:
            el = self.wait.until(EC.presence_of_element_located(locator))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
            time.sleep(0.5)
            self.wait.until(EC.element_to_be_clickable(locator))
            self.driver.execute_script("arguments[0].click();", el)
        except Exception:
            pass

    def _pesquisar_e_abrir(self, pmib):
        """
        Navega, Pesquisa e Clica no Lápis (Edição) para abrir a ficha.
        """
        # 1. Garantir URL
        if self.driver.current_url != self.url_inicial:
            self.driver.get(self.url_inicial)
            time.sleep(2)

        # 2. Pesquisar
        locator_pesquisa = (By.XPATH, "//input[contains(@placeholder, 'Código')]")
        try:
            campo = self.wait.until(EC.element_to_be_clickable(locator_pesquisa))
            campo.clear()
            time.sleep(0.2)
            campo.send_keys(pmib)
            time.sleep(0.5)
            campo.send_keys(Keys.ENTER)
            time.sleep(3)  # Espera tabela recarregar
        except Exception as e:
            return False, f"Erro na pesquisa: {e}"

        # 3. Clicar no Editar (Lápis)
        # Usa a sequência de TABs ou busca direta. Vamos usar busca direta por ser mais robusta.
        xpath_lapis = f"//span[text()='{pmib}']/ancestor::tr//i[contains(@class, 'fa-pencil')]/parent::a"

        try:
            # Tenta clicar
            botao = self.wait.until(EC.presence_of_element_located((By.XPATH, xpath_lapis)))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", botao)
            time.sleep(1)
            self.driver.execute_script("arguments[0].click();", botao)
            time.sleep(4)  # Espera abrir a edição
            return True, "Ficha aberta."
        except Exception as e:
            return False, f"Ficha {pmib} não encontrada ou não editável."

    # --- LÓGICA PRINCIPAL DE EXCLUSÃO (DO SCRIPT ORIGINAL) ---
    def executar_limpeza(self, pmib_codigo, callback_log=None):
        """
        Abre a ficha e apaga todas as LMRs em loop.
        """
        if callback_log: callback_log(f"Iniciando processo para PMIB: {pmib_codigo}")

        # 1. Abre a Ficha
        sucesso, msg = self._pesquisar_e_abrir(pmib_codigo)
        if not sucesso:
            if callback_log: callback_log(msg)
            return

        # 2. Acessa Aba LMR
        try:
            if callback_log: callback_log("Acessando aba 'Aplicação - LMR'...")
            # XPath do script original
            botao_lmr = self.wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="b10-ApplicationMRL"]/button')))
            botao_lmr.click()
            time.sleep(2)
        except Exception as e:
            if callback_log: callback_log(f"Erro ao abrir aba LMR (pode já estar aberta): {e}")

        # 3. Loop de Exclusão (Original)
        count = 0
        if callback_log: callback_log("Iniciando varredura de exclusão...")

        while True:
            try:
                # Espera a tabela estabilizar
                time.sleep(1)

                # Tenta localizar a primeira lixeira (ícone de exclusão)
                # XPath original: //*[@id="b10-b19-$b17"]/table/tbody/tr[2]/td[8]/a[2]/i
                # Nota: tr[2] geralmente é a primeira linha de dados (tr[1] é header)
                xpath_lixeira = '//*[@id="b10-b19-$b17"]/table/tbody/tr[2]//i[contains(@class, "fa-trash")]/parent::a'

                lixeira = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath_lixeira)))

                # Scroll para garantir que está visível e clicável
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", lixeira)
                lixeira.click()

                # Espera o botão de confirmação da exclusão e clica
                # XPath original: //*[@id="b10-b19-b17-b10-b1-Footer"]/div/button[1]
                xpath_confirmar = '//button[@type="button" and text()="CONFIRMAR"]'  # Mais genérico/seguro ou usar o ID original

                confirmar = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath_confirmar)))
                confirmar.click()

                # Espera a exclusão processar
                count += 1
                if callback_log: callback_log(f" -> Item {count} apagado.")
                time.sleep(1.5)  # Pausa para refresh da tabela

            except TimeoutException:
                # Não achou mais lixeiras -> Fim
                if callback_log: callback_log("✅ Todas as aplicações visíveis foram apagadas.")
                break
            except StaleElementReferenceException:
                # Tabela atualizou enquanto tentava clicar -> Tenta loop de novo
                continue
            except Exception as e:
                # Outro erro -> Para
                if callback_log: callback_log(f"Parada ou Erro: {e}")
                break

        # Voltar para lista (opcional, bom para fluxo continuo)
        try:
            self.driver.get(self.url_inicial)
        except:
            pass
