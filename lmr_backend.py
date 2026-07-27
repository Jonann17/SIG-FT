import pandas as pd
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# CP 1.4 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 1): protocolo único
# UI<->serviço. `processar_lista` aceita o novo parâmetro `callbacks`
# preservando `callback_log`/`callback_ask` antigos como aliases
# retrocompatíveis (via `from_legacy`) — ver core/callbacks.py.
# `callback_input` (texto livre) NÃO faz parte de `UICallbacks` — ver
# docstring de core/callbacks.py e docs/refatoracao/PENDENCIAS.md.
from sigft.core.callbacks import UICallbacks, from_legacy

# CP 2.1 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 2): fábrica única de
# driver Chrome, substitui `webdriver.Chrome()` cru em `iniciar_driver`
# abaixo. Escopo estrito deste checkpoint: SÓ a criação do driver muda — o
# resto da classe (24 TABs, `_processar_ficha_lmr_interna` etc.) continua
# usando `self.driver`/`self.wait` crus, sem nenhuma alteração.
from sigft.core.rpa.selenium_engine import create_chrome_driver


# =============================================================================
# CLASSE DE AUTOMAÇÃO LMR (BACKEND)
# =============================================================================
class LMRAutomation:
    def __init__(self):
        self.driver = None
        self.wait = None
        self.url_inicial = 'https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList'

    def iniciar_driver(self):
        """Inicia o navegador Chrome.

        CP 2.1: a criação em si (Chrome + maximize + WebDriverWait(20s))
        agora vem de `create_chrome_driver` (única fábrica, ver
        core/rpa/selenium_engine.py) — timeout preservado EXATAMENTE como
        antes (20s). Nada mais deste método/classe muda.
        """
        self.driver, self.wait = create_chrome_driver(wait_timeout=20)
        return self.driver

    def fechar_driver(self):
        if self.driver:
            self.driver.quit()

    def abrir_portal(self, url=None):
        target = url if url else self.url_inicial
        if self.driver:
            self.driver.get(target)

    # --- MÉTODOS DE DADOS ---
    def carregar_dados_excel(self, caminho_excel):
        """
        Lê o Excel, filtra e retorna:
        1. O DataFrame completo limpo.
        2. A lista de PMIBs únicos para seleção.
        """
        try:
            df_completo = pd.read_excel(
                caminho_excel,
                sheet_name='GERAL',
                usecols=['PMIB', 'Código_PMIB', 'TAG_PMIB'],
                dtype={'PMIB': str, 'Código_PMIB': str, 'TAG_PMIB': str}
            )
            # Limpeza
            df_completo['PMIB'] = df_completo['PMIB'].str.strip()
            df_completo.dropna(subset=['PMIB'], inplace=True)

            pmibs_unicos = df_completo['PMIB'].unique().tolist()
            return True, df_completo, pmibs_unicos, f"Carregados {len(df_completo)} registros e {len(pmibs_unicos)} PMIBs únicos."
        except Exception as e:
            return False, None, None, str(e)

    # --- CP 1.4: decisão de linha inicial, extraída para ser testável em
    # isolamento (não toca self.driver/self.wait — roda inteiramente ANTES
    # de qualquer chamada Selenium dentro de `_processar_ficha_lmr_interna`,
    # que só começa em `self.wait.until(...)` depois de resolvida a linha
    # inicial). Mesma lógica do original, só reorganizada num método próprio
    # — ver tests/test_lmr_backend_migration.py.
    def _resolver_linha_inicial(self, df_filtrado, callbacks: UICallbacks, callback_input=None) -> int:
        """
        Pergunta opcional ao usuário se deseja começar de uma linha
        específica (em vez do zero). `callback_input` continua CRU (texto
        livre, fora de `UICallbacks` — ver core/callbacks.py); só é
        consultado se foi de fato passado (mesmo gate do original:
        `if callback_ask and callback_input`). Como `callbacks.ask` agora é
        SEMPRE chamável (no-op devolve `False` quando não há provedor real —
        ver `UICallbacks`), o gate `and callback_ask` fica redundante e é
        substituído por só `if callback_input`: se não houver provedor real
        de `ask`, `callbacks.ask(...)` devolve `False` e o resultado final
        (`linha_inicio == 0`, sem chamar `callback_input`) é idêntico ao
        comportamento original quando `callback_ask` estava ausente.
        """
        linha_inicio = 0
        if callback_input:
            # Pergunta se quer começar de linha específica (Sim/Não)
            usar_personalizado = callbacks.ask(
                "Deseja começar de uma linha específica (não do zero)?",
                titulo="Configuração LMR",
            )
            if usar_personalizado:
                try:
                    val = callback_input("Linha Inicial", f"Digite o número da linha (0 a {len(df_filtrado)-1}):")
                    linha_inicio = int(val)
                except:
                    callbacks.log("Entrada inválida. Começando do 0.")
                    linha_inicio = 0

        if linha_inicio < 0 or linha_inicio >= len(df_filtrado):
            linha_inicio = 0

        return linha_inicio

    # --- LÓGICA CORE (MANTIDA DO ORIGINAL) ---
    def _processar_ficha_lmr_interna(self, df_filtrado, callbacks: UICallbacks, callback_input=None):
        """
        Executa a lógica interna de preenchimento da LMR para uma ficha.
        Mantém a lógica de agrupamento de TAGs e input de linha inicial.

        CP 1.4: recebe `callbacks` (já resolvido por `processar_lista`) em
        vez dos 3 callbacks avulsos antigos (`callback_log`, `callback_ask`
        vivem agora dentro de `callbacks`). `callback_input` (texto livre)
        continua sendo repassado cru, à parte — não faz parte de
        `UICallbacks` (ver core/callbacks.py). Método privado, só chamado
        internamente por `processar_lista` — pode mudar de assinatura
        livremente.
        """
        callbacks.log(f'Qtd aplicações nesta ficha: {df_filtrado.shape[0]}')

        if df_filtrado.empty:
            callbacks.log("Nenhuma aplicação encontrada. Pulando.")
            return []

        linha_inicio = self._resolver_linha_inicial(df_filtrado, callbacks, callback_input)

        processados_ok = []
        processados_erro_ficha = []

        # Loop a partir da linha escolhida
        index = linha_inicio
        while index < len(df_filtrado):
            codigo_pmib_item = ""
            try:
                row = df_filtrado.loc[index]
                codigo_pmib_item = str(row['Código_PMIB'])

                # --- LÓGICA DE AGRUPAMENTO (ORIGINAL) ---
                grupo_tags = []
                # Agrupa todas as TAGs consecutivas com o mesmo Código_PMIB
                while index < len(df_filtrado) and str(df_filtrado.loc[index, 'Código_PMIB']) == codigo_pmib_item:
                    grupo_tags.append(str(df_filtrado.loc[index, 'TAG_PMIB']))
                    index += 1  # avança index
                # ----------------------------------------

                quantidade = len(grupo_tags)
                callbacks.log(f"Processando Cód {codigo_pmib_item} com {quantidade} TAG(s)")

                # Preenche campos
                campo_codigo = self.wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="b10-b19-Input_EquipmentCode"]')))
                campo_codigo.clear()
                campo_codigo.send_keys(codigo_pmib_item)

                campo_quantidade = self.driver.find_element(By.XPATH, '//*[@id="b10-b19-Input_QuantityInstalled"]')
                campo_quantidade.clear()
                campo_quantidade.send_keys(str(quantidade))

                # Insere todas as TAGs com TAB + ENTER após cada uma
                for tag_pmib in grupo_tags:
                    campo_tag = self.driver.find_element(By.XPATH, '//*[@id="b10-b19-Input_Tag"]')
                    campo_tag.clear()
                    campo_tag.send_keys(tag_pmib)
                    actions = ActionChains(self.driver)
                    actions.send_keys(Keys.TAB).pause(0.5).send_keys(Keys.ENTER).perform()
                    time.sleep(0.5)

                # Salvar e confirmar
                self.driver.find_element(By.XPATH, '//*[@id="b10-b19-Form"]/div[2]/button[1]').click()
                self.wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="b10-b19-b22-b1-Footer"]/div/button[1]'))).click()
                time.sleep(1)

                processados_ok.append(codigo_pmib_item)
                callbacks.log(f' -> Código {codigo_pmib_item} inserido ✔️')

            except Exception as e:
                callbacks.log(f"Erro no Cód {codigo_pmib_item}: {e}")

                # Registra erro
                ficha_pmib_atual = df_filtrado.iloc[0]['PMIB']
                processados_erro_ficha.append({
                    'ficha_pmib': ficha_pmib_atual,
                    'index': index,
                    'codigo_pmib': codigo_pmib_item,
                    'erro': str(e)
                })

                # Pausa manual para correção (Substitui o input())
                callbacks.ask(
                    f"Erro no item {codigo_pmib_item}.\nCorrija manualmente no navegador e clique OK para continuar.",
                    titulo="Erro LMR",
                )

                # O loop 'while' tentará o mesmo item novamente ou o próximo dependendo de onde quebrou.
                # No script original, ele NÃO incrementava o index no except, então repetia.
                # Mantendo comportamento original.

        return processados_erro_ficha

    # --- FLUXO PRINCIPAL (Substitui main) ---
    def processar_lista(
        self,
        lista_pmibs,
        df_completo,
        callbacks: UICallbacks | None = None,
        callback_log=None,
        callback_ask=None,
        callback_input=None,
    ):
        """
        Executa a automação para a lista de PMIBs selecionados.

        CP 1.4: `callbacks` (novo, `core.callbacks.UICallbacks`) substitui
        os 3 parâmetros `callback_log`/`callback_ask`/`callback_input`
        antigos — que continuam aceitos como aliases retrocompatíveis:
        `frontend.py` chama `auto.processar_lista(selecionados, df_completo,
        callback_log=cb_log, callback_ask=cb_ask, callback_input=cb_input)`
        hoje e continua funcionando sem nenhuma mudança. Se `callbacks` for
        passado diretamente por um chamador novo, ele tem prioridade; senão
        é construído a partir de `callback_log`/`callback_ask` via
        `from_legacy`. `callback_input` (texto livre) NÃO faz parte de
        `UICallbacks` — continua sendo repassado cru, à parte, direto para
        `_processar_ficha_lmr_interna` (ver core/callbacks.py e
        docs/refatoracao/PENDENCIAS.md).
        """
        callbacks = callbacks or from_legacy(callback_log=callback_log, callback_ask=callback_ask)

        fichas_com_erro = []
        erros_totais = []

        total = len(lista_pmibs)

        for i, pmib_atual in enumerate(lista_pmibs):
            callbacks.log(f"\n--- Ficha {i+1}/{total}: {pmib_atual} ---")

            try:
                # 4.1. Pesquisar
                callbacks.log(f"Pesquisando: {pmib_atual}")
                time.sleep(0.2)

                # Volta para home se necessário (garantia)
                if self.driver.current_url != self.url_inicial:
                    self.driver.get(self.url_inicial)
                    time.sleep(2)

                locator_pesquisa = (By.XPATH, '//*[@id="b7-InputDatasheetFilter"]')
                campo_pesquisa = self.wait.until(EC.visibility_of_element_located(locator_pesquisa))
                campo_pesquisa.click()
                time.sleep(0.2)
                campo_pesquisa.send_keys(Keys.CONTROL, "a")
                time.sleep(0.2)
                campo_pesquisa.send_keys(Keys.BACKSPACE)
                time.sleep(0.2)
                campo_pesquisa.send_keys(pmib_atual)
                campo_pesquisa.send_keys(Keys.ENTER)
                time.sleep(3)

                # 4.2. Clicar em "Editar" (Sequência de TABs original mantida)
                callbacks.log("Navegando até editar (TABs)...")

                # Sequência exata do script original
                campo_pesquisa.send_keys(Keys.TAB, Keys.TAB, Keys.TAB, Keys.TAB, Keys.TAB, Keys.TAB, Keys.TAB, Keys.TAB, Keys.TAB, Keys.TAB, Keys.TAB, Keys.TAB, Keys.TAB,
                                         Keys.TAB, Keys.TAB, Keys.TAB, Keys.TAB, Keys.TAB, Keys.TAB, Keys.TAB, Keys.TAB, Keys.TAB, Keys.TAB, Keys.TAB)

                locator_editar = self.driver.switch_to.active_element
                locator_editar.send_keys(Keys.ENTER)
                time.sleep(3)

                # 4.3. Clicar na aba "Aplicação - LMR"
                callbacks.log("Abrindo aba LMR...")
                locator_aba_lmr = (By.XPATH, '//*[@id="b10-ApplicationMRL"]/button')
                self.wait.until(EC.element_to_be_clickable(locator_aba_lmr)).click()
                time.sleep(2)

                # 4.4. Filtrar DataFrame
                df_filtrado = df_completo[df_completo['PMIB'] == pmib_atual].reset_index(drop=True)

                # 4.5. Processamento Interno
                erros = self._processar_ficha_lmr_interna(df_filtrado, callbacks, callback_input)

                if erros:
                    fichas_com_erro.append(pmib_atual)
                    erros_totais.extend(erros)

                # 4.6. Voltar
                callbacks.log("Voltando para lista...")
                time.sleep(1)
                locator_voltar = (By.XPATH, '//*[@id="b9-Content"]')  # Botão de voltar do breadcrumb ou similar
                self.wait.until(EC.element_to_be_clickable(locator_voltar)).click()
                time.sleep(1)

            except Exception as e:
                msg = f"ERRO FATAL em {pmib_atual}: {e}"
                callbacks.log(msg)

                fichas_com_erro.append(pmib_atual)
                erros_totais.append({'ficha': pmib_atual, 'erro_fatal': str(e)})

                callbacks.ask(
                    f"{msg}\nPressione OK para tentar recarregar a home e seguir.",
                    titulo="Erro Fatal",
                )

                try:
                    self.driver.get(self.url_inicial)
                except:
                    break

        # Relatório Final
        if erros_totais:
            callbacks.log("Salvando relatório de erros (erros_lmr.csv)...")
            try:
                pd.DataFrame(erros_totais).to_csv("erros_lmr.csv", index=False)
            except: pass

        callbacks.log("Processo Finalizado.")
