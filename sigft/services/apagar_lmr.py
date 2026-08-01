import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

# CP 1.4 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 1): protocolo único
# UI<->serviço. `executar_limpeza` aceita o novo parâmetro `callbacks`
# preservando o `callback_log` antigo como alias retrocompatível (via
# `from_legacy`) — ver core/callbacks.py.
from sigft.core.callbacks import UICallbacks, from_legacy

# CP 2.1 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 2): fábrica única de
# driver Chrome, substitui `webdriver.Chrome()` cru em `iniciar_driver`
# abaixo.
from sigft.core.rpa.selenium_engine import create_chrome_driver, SeleniumEngine
# CP 2.2 (Fase 2): `safe_click`/`_pesquisar_e_abrir` passam a delegar para
# `PMIBPortal` (construído logo após o driver, em `iniciar_driver`). O loop
# de exclusão de `executar_limpeza` CONTINUA usando `self.driver`/
# `self.wait` crus -- é estruturalmente diferente das 2 outras variantes de
# "excluir linha" do diagnóstico (busca a 1ª lixeira visível da TABELA
# INTEIRA via um XPath específico deste módulo, sem uma "linha" localizada
# pra passar para `PMIBPortal.excluir_linha_com_confirmacao(row)`) — ver
# docs/refatoracao/PENDENCIAS.md.
#
# CP 2.3 (Fase 2): os 3 `time.sleep(<literal>)` do loop de exclusão viram 2
# constantes nomeadas (`PAUSA_ABERTURA_ABA`, `PAUSA_POS_EXCLUSAO`) + 1
# ELIMINADO (ver comentário no local, dentro de `executar_limpeza`).
from sigft.core.rpa.portal import PMIBPortal, PAUSA_ABERTURA_ABA, PAUSA_POS_EXCLUSAO


# =============================================================================
# CLASSE DE AUTOMAÇÃO - APAGAR LMR
# =============================================================================
class ApagarLMRAutomation:
    def __init__(self):
        self.driver = None
        self.wait = None
        self.portal = None
        self.url_inicial = 'https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList'

    def iniciar_driver(self):
        """Inicia o navegador Chrome.

        CP 2.1: a criação em si (Chrome + maximize + WebDriverWait(20s))
        agora vem de `create_chrome_driver` (única fábrica, ver
        core/rpa/selenium_engine.py) — timeout preservado EXATAMENTE como
        antes (20s).

        CP 2.2: logo em seguida, `self.portal` passa a existir
        (`PMIBPortal` sobre um `SeleniumEngine` construído com o MESMO
        `driver`/`wait` — nada de novo é criado) — `safe_click`/
        `_pesquisar_e_abrir` abaixo passam a delegar para ele.
        """
        self.driver, self.wait = create_chrome_driver(wait_timeout=20)
        self.portal = PMIBPortal(SeleniumEngine(self.driver, self.wait))
        return self.driver

    def fechar_driver(self):
        if self.driver:
            self.driver.quit()

    def abrir_portal(self):
        if self.driver:
            self.driver.get(self.url_inicial)

    # --- HELPERS DE NAVEGAÇÃO ---
    def safe_click(self, locator):
        """CP 2.2: DELEGADOR FINO -- a mecânica real (scroll + espera +
        clique via JS) agora vive em `PMIBPortal.safe_click`/
        `SeleniumEngine.click` (um único lugar). `locator` continua sendo
        aceito como tupla `(By.XPATH, xpath)` -- é assim que os MUITOS call
        sites internos desta classe já chamam hoje; a string XPath é
        extraída aqui antes de repassar (o portal só entende XPath puro).
        """
        seletor = locator[1] if isinstance(locator, tuple) else locator
        self.portal.safe_click(seletor)

    def _pesquisar_e_abrir(self, pmib):
        """
        Navega, Pesquisa e Clica no Lápis (Edição) para abrir a ficha.

        CP 2.2: o corpo passa a delegar para `PMIBPortal.pesquisar_e_abrir`
        com os seletores DEFAULT (apagar_lmr é um dos 2 módulos -- junto
        com `upload_tech_specs` -- que já usava exatamente esses seletores;
        ver docstring de `PMIBPortal.pesquisar_e_abrir`). O retorno `bool`
        do portal é adaptado para a tupla `(bool, mensagem)` que o único
        chamador desta classe (`executar_limpeza`) espera -- mesmo
        contrato externo de antes.
        """
        sucesso = self.portal.pesquisar_e_abrir(pmib)
        if sucesso:
            return True, "Ficha aberta."
        return False, f"Ficha {pmib} não encontrada ou não editável."

    # --- LÓGICA PRINCIPAL DE EXCLUSÃO (DO SCRIPT ORIGINAL) ---
    def executar_limpeza(self, pmib_codigo, callbacks: UICallbacks | None = None, callback_log=None):
        """
        Abre a ficha e apaga todas as LMRs em loop.

        CP 1.4: `callbacks` (novo, `core.callbacks.UICallbacks`) substitui o
        parâmetro único `callback_log` antigo, que continua aceito como
        alias retrocompatível — `frontend.py` chama
        `auto.executar_limpeza(pmib, callback_log=cb_log)` hoje e continua
        funcionando sem nenhuma mudança. Se `callbacks` for passado
        diretamente por um chamador novo, ele tem prioridade; senão é
        construído a partir de `callback_log` via `from_legacy`.
        """
        callbacks = callbacks or from_legacy(callback_log=callback_log)

        callbacks.log(f"Iniciando processo para PMIB: {pmib_codigo}")

        # 1. Abre a Ficha
        sucesso, msg = self._pesquisar_e_abrir(pmib_codigo)
        if not sucesso:
            callbacks.log(msg)
            return

        # 2. Acessa Aba LMR
        try:
            callbacks.log("Acessando aba 'Aplicação - LMR'...")
            # XPath do script original
            botao_lmr = self.wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="b10-ApplicationMRL"]/button')))
            botao_lmr.click()
            time.sleep(PAUSA_ABERTURA_ABA)
        except Exception as e:
            callbacks.log(f"Erro ao abrir aba LMR (pode já estar aberta): {e}")

        # 3. Loop de Exclusão (Original)
        count = 0
        callbacks.log("Iniciando varredura de exclusão...")

        while True:
            try:
                # CP 2.3: o sleep fixo de 1 segundo ("Espera a tabela
                # estabilizar") que existia aqui foi ELIMINADO (não virou
                # constante) --
                # critério (B) do checkpoint: a busca imediatamente abaixo
                # já é um `wait.until(EC.element_to_be_clickable(...))` para
                # a PRÓPRIA lixeira que o sleep tentava dar tempo de
                # (re)aparecer, com retry/timeout PRÓPRIOS (até o timeout
                # global do `WebDriverWait`) -- o loop inteiro já depende de
                # `TimeoutException` (abaixo) para decidir "acabou", ou seja,
                # a sincronização REAL já é feita por este `wait.until`; o
                # sleep fixo era redundante ("cinto e suspensório"). Ver
                # docs/refatoracao/PLANO_REFATORACAO.md Fase 2 -> CP 2.3 e
                # docs/refatoracao/PENDENCIAS.md.

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
                callbacks.log(f" -> Item {count} apagado.")
                time.sleep(PAUSA_POS_EXCLUSAO)  # Pausa para refresh da tabela

            except TimeoutException:
                # Não achou mais lixeiras -> Fim
                callbacks.log("✅ Todas as aplicações visíveis foram apagadas.")
                break
            except StaleElementReferenceException:
                # Tabela atualizou enquanto tentava clicar -> Tenta loop de novo
                continue
            except Exception as e:
                # Outro erro -> Para
                callbacks.log(f"Parada ou Erro: {e}")
                break

        # Voltar para lista (opcional, bom para fluxo continuo)
        try:
            self.driver.get(self.url_inicial)
        except:
            pass
