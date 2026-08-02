import pandas as pd
import time
import os
import glob
import shutil
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import StaleElementReferenceException
# CP 1.3: `openpyxl` deixou de ser importado diretamente aqui -- o único
# consumidor (AtualizadorStatusPMIB.atualizar_ficha_concluida) agora delega
# para core.excel.status_sheet.StatusPMIB, que importa openpyxl de forma
# preguiçosa só quando precisa (ver docstring de status_sheet.py).

from sigft import config
from sigft.core.excel import headers, pmib_codes, status_sheet
# CP 2.1 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 2): fábrica única de
# driver Chrome, substitui `webdriver.Chrome(options=...)` cru em
# `ExtratorFichaBase.iniciar_driver_silencioso` abaixo (a ÚNICA das 6
# inicializações que já configurava `download_dir` via ChromeOptions/prefs
# — mecânica preservada intacta dentro da fábrica).
from sigft.core.rpa.selenium_engine import create_chrome_driver, SeleniumEngine
# CP 2.2 (Fase 2): `ExtratorFichaBase._pesquisar_e_abrir` e
# `InjetorFichaAlvo.safe_click`/`_clicar_salvar_visivel`/
# `_pesquisar_e_abrir`/o ramo de exclusão de
# `_limpar_caracteristicas_tecnicas` passam a delegar para `PMIBPortal`.
# `_ler_condicoes`/`_preencher_condicoes`/`_adicionar_fornecedores`/
# `_associar_documentos`/`_upload_imagens` continuam usando `self.driver`/
# `self.wait` crus, sem nenhuma alteração (fora do escopo deste checkpoint).
#
# CP 2.3 (Fase 2): os 17 `time.sleep(<literal>)` ATIVOS do arquivo viram
# constantes nomeadas (nenhum eliminado); o comentário desabilitado dentro
# de `_upload_imagens` (já morto antes deste checkpoint) também teve seu
# sleep fixo de exemplo (1 segundo) trocado por `PAUSA_ABERTURA_MODAL` só
# por consistência (não é código ativo) -- ver
# docs/refatoracao/PLANO_REFATORACAO.md Fase 2 -> CP 2.3.
from sigft.core.rpa.portal import (
    PMIBPortal,
    PAUSA_ABERTURA_MODAL,
    PAUSA_ABERTURA_SECAO,
    PAUSA_ANIMACAO,
    PAUSA_CARGA_TABELA,
    PAUSA_FILTRO_FORNECEDOR,
    PAUSA_PAGINACAO,
    PAUSA_POLL_DOWNLOAD,
    PAUSA_RECARGA_TABELA,
    PAUSA_RETRY_ARQUIVO_BLOQUEADO,
    PAUSA_SALVAMENTO,
    PAUSA_SALVAMENTO_LONGA,
    PAUSA_TROCA_SUBABA,
    PAUSA_UPLOAD_ARQUIVO,
)


class GerenciadorFilaPMIB:
    def __init__(self, caminho_excel, nome_aba="Lista de Materiais"):
        self.caminho_excel = caminho_excel
        self.nome_aba = nome_aba

    def _encontrar_cabecalho(self, df, limite_linhas=15):
        """Busca dinamicamente a linha de cabeçalho para evitar quebra por linhas vazias no topo."""
        # CP 1.2: delega para a implementação única (core.excel.headers). O
        # original declarava colunas_chave = ["CÓDIGO PMIB", "PDM usado",
        # "OBSERVAÇÕES"] mas só verificava "CÓDIGO PMIB" na prática (as
        # outras duas nunca entravam na condição) — comportamento
        # preservado, só essa palavra-chave é usada de fato.
        idx = headers.find_header_row(df.head(limite_linhas).values.tolist(), config.COL_CODIGO_PMIB)
        return idx if idx is not None else -1

    def montar_fila_processamento(self, marcador_duplicada="DUPLICADA"):
        """
        Lê o Excel, garante a formatação dos números PMIB e retorna uma fila de tarefas.
        marcador_duplicada: O texto que você usa na coluna 'PDM usado' para indicar que é cópia.
        """
        fila_processamento = []

        try:
            # Lemos primeiro sem cabeçalho para achar a linha correta
            df_raw = pd.read_excel(self.caminho_excel, sheet_name=self.nome_aba, header=None, dtype=str)
            header_idx = self._encontrar_cabecalho(df_raw)

            if header_idx == -1:
                return False, "Erro: Coluna 'CÓDIGO PMIB' não encontrada nas primeiras linhas."

            # Promovemos a linha correta a cabeçalho
            df = df_raw.iloc[header_idx + 1:].copy()
            df.columns = df_raw.iloc[header_idx].astype(str).str.strip().str.upper()

            # Limpeza de colunas vitais
            if "CÓDIGO PMIB" not in df.columns or "OBSERVAÇÕES" not in df.columns:
                return False, "Erro: Colunas obrigatórias ausentes (CÓDIGO PMIB ou OBSERVAÇÕES)."

            # Tratamento da coluna PDM usado (tem que ser estritamente maiúsculo pois convertemos acima)
            col_pdm = "PDM USADO" if "PDM USADO" in df.columns else "PDM"

            for index, row in df.iterrows():
                pmib_alvo_raw = row.get("CÓDIGO PMIB")
                pdm_status = str(row.get(col_pdm, "")).strip().upper()
                observacao = str(row.get("OBSERVAÇÕES", "")).strip()

                # Regra de negócio: Se o PDM indica ser cópia
                if marcador_duplicada in pdm_status:
                    # Extrai o PMIB base da observação (texto livre, NÃO é
                    # caminho de arquivo) -- CP 1.2: delega para
                    # core.excel.pmib_codes.find_pmib_code_in_text.
                    pmib_base = pmib_codes.find_pmib_code_in_text(observacao)

                    if pmib_base and pmib_alvo_raw:
                        # --- BLINDAGEM DO CÓDIGO ALVO (Mantendo Zeros à
                        # direita) --- CP 1.2: delega para a normalização
                        # única e canônica
                        # (core.excel.pmib_codes.normalize_pmib).
                        pmib_alvo = pmib_codes.normalize_pmib(pmib_alvo_raw)

                        descricao = str(row.get("DESCRIÇÃO", "Sem Descrição")).strip()

                        fila_processamento.append({
                            "descricao": descricao,
                            "pmib_original": pmib_base,
                            "pmib_alvo": pmib_alvo
                        })

            return True, fila_processamento

        # CP 1.3: este `except PermissionError` NÃO foi migrado para
        # `core.excel.locking.save_with_retry` -- ele protege uma LEITURA
        # (`pd.read_excel` acima), não um `wb.save(path)`. `save_with_retry`
        # envolve só a chamada de salvamento (onde o lock do Excel de fato
        # morde); abrir/ler um arquivo já aberto no Excel normalmente
        # FUNCIONA (ver docstring de `locking.py`), então não há um "laço de
        # retry" aqui para unificar -- é só uma mensagem amigável para o
        # caso raro de leitura falhar por permissão. Documentado em
        # docs/refatoracao/PENDENCIAS.md.
        except PermissionError:
            return False, "Erro de Permissão: O arquivo Excel de STATUS está aberto. Feche-o e tente novamente."
        except Exception as e:
            return False, f"Erro ao montar fila: {e}"


# Seletores EXATOS de busca/lápis usados por `ExtratorFichaBase.
# _pesquisar_e_abrir` e `InjetorFichaAlvo._pesquisar_e_abrir` -- IDÊNTICOS
# entre as duas classes (já eram cópias literais uma da outra antes deste
# checkpoint) -- overrides passados a `PMIBPortal.pesquisar_e_abrir` (ver
# docstring do método). Constantes de MÓDULO (não de classe) para não
# duplicar as strings entre as 2 classes que as usam.
_BUSCA_XPATH_FICHA_DUPLICADA = "//input[contains(@id, 'InputDatasheetFilter') or contains(@placeholder, 'Código')]"
_LAPIS_XPATH_TEMPLATE_FICHA_DUPLICADA = "//tr[contains(., '{pmib}')]//a[.//i[contains(@class, 'fa-pencil')]]"


class ExtratorFichaBase:
    def __init__(self, dir_download_temp="./temp_downloads"):
        self.driver = None
        self.wait = None
        self.portal = None
        self.dir_download = os.path.abspath(dir_download_temp)
        self._preparar_pasta_temp()

    def _preparar_pasta_temp(self):
        """Cria ou limpa a pasta temporária de downloads antes de iniciar."""
        if not os.path.exists(self.dir_download):
            os.makedirs(self.dir_download)
        else:
            for f in glob.glob(os.path.join(self.dir_download, "*")):
                try: os.remove(f)
                except Exception: pass

    def iniciar_driver_silencioso(self):
        """Inicia o Chrome com preferências para download automático.

        CP 2.1: a criação em si (ChromeOptions/prefs de download + Chrome +
        maximize + WebDriverWait(15s)) agora vem de `create_chrome_driver`
        (única fábrica, ver core/rpa/selenium_engine.py) — mesma mecânica
        de `options`/prefs, mesmo timeout (15s, preservado EXATAMENTE como
        antes) e `download_dir=self.dir_download` repassado tal qual.

        CP 2.2: logo em seguida, `self.portal` passa a existir (`PMIBPortal`
        sobre um `SeleniumEngine` construído com o MESMO `driver`/`wait`) --
        `_pesquisar_e_abrir` abaixo passa a delegar para ele.
        """
        self.driver, self.wait = create_chrome_driver(wait_timeout=15, download_dir=self.dir_download)
        self.portal = PMIBPortal(SeleniumEngine(self.driver, self.wait))
        return self.driver

    # --- HELPERS DE LEITURA (SCRAPING) ---
    def _ler_input(self, xpath):
        """Lê o valor de um input type text ou textarea."""
        try:
            el = self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
            return el.get_attribute("value").strip()
        except Exception:
            return ""

    def _ler_tabela_outsystems(self, data_header):
        """Lê os textos dentro das tags span de colunas específicas (Fabricante, Ref, Documentos)."""
        textos = []
        try:
            # Pega todas as células da tabela que tenham o data-header específico
            celulas = self.driver.find_elements(By.XPATH, f"//td[@data-header='{data_header}']//span[@data-expression]")
            for cel in celulas:  # Correção: alterado 'em' para 'in'
                texto = cel.get_attribute("textContent").strip()
                if texto: textos.append(texto)
            return textos
        except Exception:
            return []

    def _esperar_download_e_renomear(self, nome_descritivo):
        """Aguarda o arquivo cair na pasta temp e o renomeia com a descrição lida da tela."""
        tempo_maximo = 10
        tempo_decorrido = 0

        while tempo_decorrido < tempo_maximo:
            # Procura qualquer arquivo na pasta que não seja ".crdownload" (arquivo temporário do Chrome)
            arquivos = [f for f in glob.glob(os.path.join(self.dir_download, "*")) if not f.endswith(".crdownload")]

            if arquivos:
                arquivo_baixado = max(arquivos, key=os.path.getctime)  # Pega o arquivo mais recente
                extensao = os.path.splitext(arquivo_baixado)[1]

                # Sanitiza o nome descritivo para não quebrar caminhos no Windows
                nome_seguro = "".join([c for c in nome_descritivo if c.isalpha() or c.isdigit() or c == ' ']).rstrip()
                novo_caminho = os.path.join(self.dir_download, f"{nome_seguro}{extensao}")

                try:
                    shutil.move(arquivo_baixado, novo_caminho)
                    return novo_caminho
                except Exception:
                    pass

            time.sleep(PAUSA_POLL_DOWNLOAD)
            tempo_decorrido += 1

        return None

    def _pesquisar_e_abrir(self, pmib):
        """Navega, pesquisa o PMIB e clica no lápis de edição.

        CP 2.2: o corpo passa a delegar para
        `PMIBPortal.pesquisar_e_abrir` com os seletores EXATOS que esta
        classe já usava (`_BUSCA_XPATH_FICHA_DUPLICADA`/
        `_LAPIS_XPATH_TEMPLATE_FICHA_DUPLICADA`, no topo do módulo) --
        ver docstring do método para o levantamento completo.

        O ORIGINAL não tinha NENHUM try/except aqui: qualquer falha
        Selenium propagava (barulhenta) para quem chamasse
        `extrair_dados_ficha`. O portal agora ENGOLE exceções internamente
        durante o retry (3x) e devolve `False` em vez de deixar propagar --
        para preservar a característica "falha alta" do original em vez de
        prosseguir silenciosamente com a ficha errada aberta (ou nenhuma
        ficha aberta), este delegador levanta `RuntimeError` explicitamente
        quando o portal devolve `False` (o único chamador,
        `frontend.py._bot_worker`, já usa `except Exception as e:` genérico
        -- confirmado por leitura -- então a troca de tipo de exceção não
        tem efeito observável) -- ver docs/refatoracao/PENDENCIAS.md.
        """
        sucesso = self.portal.pesquisar_e_abrir(
            pmib,
            busca_xpath=_BUSCA_XPATH_FICHA_DUPLICADA,
            lapis_xpath_template=_LAPIS_XPATH_TEMPLATE_FICHA_DUPLICADA,
        )
        if not sucesso:
            raise RuntimeError(f"Não foi possível pesquisar/abrir a ficha {pmib}.")

    # --- MÉTODO PRINCIPAL DE EXTRAÇÃO ---
    def extrair_dados_ficha(self, pmib_original):
        """Abre a ficha base e raspa todos os dados necessários para um dicionário."""
        dados_colhidos = {
            "pmib": pmib_original,
            "info_gerais": {},
            "fornecedores": [],
            "condicoes": {},
            "documentos_associados": [],
            "imagens_baixadas": []
        }

        # 1. Navegar e abrir ficha
        self._pesquisar_e_abrir(pmib_original)

        # 2. Ler Informações Gerais
        print("    [Extrator] Lendo Informações Gerais...")
        dados_colhidos["info_gerais"] = self._ler_info_gerais()

        # 3. Ler Fornecedores
        print("    [Extrator] Extraindo Fornecedores...")
        fabricantes = self._ler_tabela_outsystems("Fabricante")
        referencias = self._ler_tabela_outsystems("Referência")
        for f, r in zip(fabricantes, referencias):
            dados_colhidos["fornecedores"].append({"fabricante": f, "referencia": r})
        print(f"        -> Encontrados {len(dados_colhidos['fornecedores'])} fornecedores.")

        # 4. Ler Condições
        print("    [Extrator] Mapeando Condições Especiais...")
        dados_colhidos["condicoes"] = self._ler_condicoes()

        # 5. Documentos e Imagens
        print("    [Extrator] Mapeando Documentos e Imagens...")
        nomes_documentos = self._ler_tabela_outsystems("Descrição")
        dados_colhidos["documentos_associados"] = nomes_documentos
        print(f"        -> Encontrados {len(nomes_documentos)} documentos para associar.")

        linhas_imagens = self.driver.find_elements(By.XPATH, "//table[contains(@class, 'TabelaImagens')]//tr")
        for linha in linhas_imagens:
            try:
                # Lê a descrição daquela imagem
                col_desc = linha.find_element(By.XPATH, ".//td[@data-header='Descrição']//span")
                descricao_img = col_desc.get_attribute("textContent").strip()

                # Clica no botão de download daquela imagem específica
                btn_download = linha.find_element(By.XPATH, ".//a[.//i[contains(@class, 'fa-cloud-download')]]")
                self.driver.execute_script("arguments[0].click();", btn_download)

                # Aguarda o Chrome baixar, pega o arquivo na pasta e renomeia
                caminho_local = self._esperar_download_e_renomear(descricao_img)

                if caminho_local:
                    dados_colhidos["imagens_baixadas"].append({
                        "caminho": caminho_local,
                        "descricao_pt": descricao_img,
                        "descricao_es": descricao_img  # Se não houver campo separado, replicamos
                    })
            except Exception as e:
                print(f"Erro ao processar linha de imagem: {e}")

        return dados_colhidos

    def _ler_select_por_label(self, texto_label):
        """Helper inteligente: encontra o dropdown baseado no nome do label ao lado dele."""
        try:
            from selenium.webdriver.support.ui import Select
            # Procura o label e pega o primeiro <select> que vier logo após ele no HTML
            xpath = f"//label[contains(text(), '{texto_label}')]/following::select[1]"
            elemento = self.driver.find_element(By.XPATH, xpath)
            return Select(elemento).first_selected_option.text.strip()
        except Exception:
            return ""

    def _ler_info_gerais(self):
        """Lê os 4 campos dropdown da aba principal."""
        return {
            "Origem": self._ler_select_por_label("Origem"),
            "Tipo": self._ler_select_por_label("Tipo"),
            "Unidade": self._ler_select_por_label("Unidade de medida"),
            "Fabricacao": self._ler_select_por_label("Tipo de fabricação")
        }

    def _ler_condicoes(self):
        """Varre os inputs, radios e checkboxes capturando o estado exato de cada XPath de forma blindada."""
        # Abre a seção de Condições ignorando o prefixo dinâmico
        btn_cond = self.wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(@id, 'Conditions_Header')]//button")))
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_cond)
        time.sleep(PAUSA_ANIMACAO)
        self.driver.execute_script("arguments[0].click();", btn_cond)
        time.sleep(PAUSA_ABERTURA_SECAO)  # Tempo para a sanfona abrir completamente

        condicoes_por_aba = {}

        # TODOS os IDs agora usam 'contains' para ignorar o prefixo que muda a cada sessão
        mapa_condicoes = {
            "ARMAZENAMENTO": {
                "tab_xpath": None,
                "textos": [
                    "//*[contains(@id, 'Input_PackingLength')]", "//*[contains(@id, 'Input_PackagingWidth')]",
                    "//*[contains(@id, 'Input_PackagingHeight')]", "//*[contains(@id, 'Input_LiquidWeight')]",
                    "//*[contains(@id, 'Input_GrossWeight')]", "//*[contains(@id, 'Input_Stacking')]",
                    "//*[contains(@id, 'TextArea_StorageCareES')]", "//*[contains(@id, 'TextArea_StorageCarePT')]",
                    "//*[contains(@id, 'TextArea_OtherCareES')]", "//*[contains(@id, 'TextArea_OtherCarePT')]"
                ],
                "booleanos": [
                    "//*[contains(@id, 'RadioButton5-input')]", "//*[contains(@id, 'RadioButton4-input')]",
                    "//*[contains(@id, 'Checkbox4')]", "//*[contains(@id, 'Checkbox5')]",
                    "//*[contains(@id, 'RadioButton-input')]", "//*[contains(@id, 'RadioButton7-input')]", "//*[contains(@id, 'RadioButton8-input')]",
                    "//*[contains(@id, 'RadioButton2-input')]", "//*[contains(@id, 'RadioButton1-input')]",
                    "//*[contains(@id, 'Checkbox3')]",
                    "//*[contains(@id, 'Checkbox6')]", "//*[contains(@id, 'Checkbox7')]", "//*[contains(@id, 'Checkbox8')]",
                    "//*[contains(@id, 'RadioButton6-input')]", "//*[contains(@id, 'RadioButton3-input')]"
                ]
            },
            "TRANSPORTE": {
                "tab_xpath": "//*[contains(@id, 'Title')]/div[3]",
                "textos": ["//*[contains(@id, 'TextArea_TransportPackagingES')]", "//*[contains(@id, 'TextArea_TransportPackagingPT')]",
                           "//*[contains(@id, 'TextArea_PositionCareES')]", "//*[contains(@id, 'TextArea_PositionCarePT')]"],
                "booleanos": []
            },
            "MANUTENCAO": {
                "tab_xpath": "//*[contains(@id, 'Title')]/div[4]",
                "textos": ["//*[contains(@id, 'TextArea_PreservationCareES')]", "//*[contains(@id, 'TextArea_PreservationCarePT')]",
                           "//*[contains(@id, 'TextArea_CleaningMethodES')]", "//*[contains(@id, 'TextArea_CleaningMethodPT')]",
                           "//*[contains(@id, 'TextArea_ToolPreservationES')]", "//*[contains(@id, 'TextArea_ToolPreservationPT')]"],
                "booleanos": []
            },
            "DESCARTE": {
                "tab_xpath": "//*[contains(@id, 'Title')]/div[5]",
                "textos": ["//*[contains(@id, 'TextArea_TypeLegislationES')]", "//*[contains(@id, 'TextArea_TypeLegislationPT')]",
                           "//*[contains(@id, 'TextArea_DiscardTypeES')]", "//*[contains(@id, 'TextArea_DiscardTypePT')]",
                           "//*[contains(@id, 'TextArea_ReserveLogisticES')]", "//*[contains(@id, 'TextArea_ReserveLogisticPT')]"],
                "booleanos": [
                    "//*[contains(@id, 'RadioButton1-input')]", "//*[contains(@id, 'RadioButton2-input')]",
                    "//*[contains(@id, 'Applies-input')]", "//*[contains(@id, 'DoesNotApply-input')]"
                ]
            }
        }

        for aba, dados in mapa_condicoes.items():
            if dados["tab_xpath"]:
                aba_btn = self.wait.until(EC.presence_of_element_located((By.XPATH, dados["tab_xpath"])))
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", aba_btn)
                time.sleep(PAUSA_ANIMACAO)
                self.driver.execute_script("arguments[0].click();", aba_btn)
                time.sleep(PAUSA_TROCA_SUBABA)

            campos_aba = {}
            for xpath in dados["textos"]:
                campos_aba[xpath] = self._ler_input(xpath)

            for xpath in dados["booleanos"]:
                try:
                    el = self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                    campos_aba[xpath] = el.is_selected()
                except Exception:
                    campos_aba[xpath] = False

            condicoes_por_aba[aba] = campos_aba

        return condicoes_por_aba


class InjetorFichaAlvo:
    def __init__(self, driver, wait):
        # Recebe o driver e o wait já instanciados e logados da Fase 2
        self.driver = driver
        self.wait = wait
        # CP 2.2: `self.portal` (`PMIBPortal` sobre um `SeleniumEngine` do
        # MESMO `driver`/`wait` recebidos acima -- nada de novo é criado) --
        # `safe_click`/`_clicar_salvar_visivel`/`_pesquisar_e_abrir`/o ramo
        # de exclusão de `_limpar_caracteristicas_tecnicas` passam a
        # delegar para ele.
        self.portal = PMIBPortal(SeleniumEngine(driver, wait))

    def safe_click(self, locator):
        """Helper para clicar com segurança via JavaScript (evita interceptações).

        CP 2.2: DELEGADOR FINO -- a mecânica real agora vive em
        `PMIBPortal.safe_click`/`SeleniumEngine.click` (um único lugar).
        `locator` continua aceito como tupla `(By.XPATH, xpath)` -- é assim
        que os call sites internos desta classe já chamam hoje; a string
        XPath é extraída aqui antes de repassar. NOTA DE COMPORTAMENTO: o
        ORIGINAL logava `print(f"Erro no safe_click: {e}")` quando a
        mecânica falhava; `SeleniumEngine.click` (CP 2.1) engole a exceção
        SEM logar nada (mesmo `except Exception: pass` das outras 3 cópias
        históricas de `safe_click` no diagnóstico) -- este `print` específico
        de `upload_ficha_duplicada` deixa de acontecer; ver
        docs/refatoracao/PENDENCIAS.md.
        """
        seletor = locator[1] if isinstance(locator, tuple) else locator
        self.portal.safe_click(seletor)

    def _clicar_salvar_visivel(self, nome_secao=""):
        """Procura na tela o botão SALVAR que está ativo/visível no momento e clica nele.

        CP 2.2: DELEGADOR FINO para `PMIBPortal.clicar_salvar_visivel`
        (mecânica idêntica, incluindo os `print()` de progresso/aviso, que
        vivem agora no portal)."""
        return self.portal.clicar_salvar_visivel(nome_secao)

    # --- 1. FORNECEDORES ---
    def _adicionar_fornecedores(self, fornecedores):
        """Abre o dropdown customizado, pesquisa fabricante e insere referência."""
        if fornecedores:
            print(f"      [Injetor] Inserindo {len(fornecedores)} Fornecedor(es)...")

        for f in fornecedores:
            fabricante = f.get("fabricante")
            referencia = f.get("referencia")
            if not fabricante: continue

            try:
                print(f"        -> Tentando inserir Fornecedor: {fabricante} | Ref: {referencia}")

                # 1. Abre o Dropdown do Fabricante focando no container pai
                locator_fab = (By.XPATH, "//div[contains(@class, 'vscomp-toggle-button') and contains(., 'fabricante')]")
                self.safe_click(locator_fab)

                # 2. Pesquisa o Fabricante
                input_fab = self.wait.until(EC.visibility_of_element_located((By.XPATH, "//input[contains(@class, 'vscomp-search-input')]")))
                input_fab.send_keys(Keys.CONTROL + "a", Keys.DELETE)
                input_fab.send_keys(fabricante)
                time.sleep(PAUSA_FILTRO_FORNECEDOR)  # Pausa levemente maior para dar tempo de o OutSystems filtrar os resultados AJAX
                input_fab.send_keys(Keys.ENTER)

                # 3. Insere Referência e clica no (+)
                if referencia:
                    input_ref = self.wait.until(EC.visibility_of_element_located((By.XPATH, "//input[contains(@id, 'Input_TextVar')]")))
                    input_ref.send_keys(Keys.CONTROL + "a", Keys.DELETE)
                    input_ref.send_keys(referencia)

                    # Clica no ícone de mais (fa-plus-circle)
                    self.safe_click((By.XPATH, "//a[.//i[contains(@class, 'fa-plus-circle')]]"))
                    time.sleep(PAUSA_SALVAMENTO)

            except Exception as e:
                print(f"        -> ❌ Falha ao inserir o fornecedor {fabricante}: {e}")

    # --- 2. CARACTERÍSTICAS TÉCNICAS (PURGA E RASTREABILIDADE) ---
    def _limpar_caracteristicas_tecnicas(self, pmib_original):
        """Varre as páginas apagando tudo, exceto o CODIGO PMIB (que recebe o valor original)."""
        # Clica na aba (assumindo que o ID ou role tab seja mapeado aqui)
        self.safe_click((By.XPATH, "//button[@role='tab' and contains(., 'Características técnicas')]"))
        time.sleep(PAUSA_CARGA_TABELA)

        while True:
            row_index = 0
            while True:
                # Recarrega as linhas para evitar StaleElement
                rows = self.driver.find_elements(By.XPATH, "//div[contains(@id, 'TechnicalCharacteristics')]//table/tbody/tr")
                if row_index >= len(rows): break

                row = rows[row_index]
                item_foi_excluido = False

                try:
                    col_desc = row.find_element(By.XPATH, ".//td[contains(@data-header, 'Descrição')]")
                    txt_tela = col_desc.get_attribute("textContent").strip().upper()

                    if "CODIGO PMIB" in txt_tela or "CÓDIGO PMIB" in txt_tela:
                        # Achou a chave mestre! Injeta o código da ficha original
                        txt_pt = row.find_element(By.XPATH, './/textarea[contains(@id, "TextArea_ValuePT")]')
                        txt_pt.clear()
                        txt_pt.send_keys(pmib_original)
                        # Clica fora para disparar o evento onBlur
                        col_desc.click()
                    else:
                        # Exclui a característica.
                        #
                        # CP 2.2: delega para
                        # `PMIBPortal.excluir_linha_com_confirmacao(row)` --
                        # mesma mecânica CENTRAL agora compartilhada com
                        # `upload_tech_specs_backend.TechSpecsAutomation.
                        # _excluir_linha_segura` (sleep de 0,5s antes do
                        # clique na lixeira -- NOVO aqui -- e 2,5s após
                        # confirmar -- era 2s -- ver
                        # docs/refatoracao/PENDENCIAS.md). `item_foi_excluido`
                        # continua `True` INCONDICIONALMENTE após a
                        # tentativa -- o ORIGINAL também não checava sucesso
                        # aqui (só setava a flag direto após o clique) --
                        # comportamento preservado tal qual, mesmo agora que
                        # o portal devolve um `bool` real.
                        self.portal.excluir_linha_com_confirmacao(row)
                        item_foi_excluido = True

                except StaleElementReferenceException:
                    continue  # Tenta pegar a linha novamente
                except Exception:
                    pass

                # Se excluiu, a linha de baixo subiu para o mesmo index. Se preencheu, pula para a próxima.
                if not item_foi_excluido: row_index += 1

            # Tenta ir para a próxima página
            try:
                btn_proximo = self.driver.find_element(By.XPATH, "//button[@aria-label='Ir para a página seguinte']")
                if btn_proximo.is_enabled():
                    self.driver.execute_script("arguments[0].click();", btn_proximo)
                    time.sleep(PAUSA_PAGINACAO)
                else:
                    break
            except Exception:
                break

        # CLIQUE SEGURO DO BOTÃO SALVAR DA ABA
        self._clicar_salvar_visivel("Características Técnicas (Purga/Código Base)")

    # --- 3. DOCUMENTOS E IMAGENS ---
    def _associar_documentos(self, documentos):
        """Abre o modal de associação, pesquisa o nome e marca o checkbox."""
        for doc in documentos:
            # 1. Clicar em "Associar documentos"
            self.safe_click((By.XPATH, "//a[.//i[contains(@class, 'fa-plus-square')]]"))
            time.sleep(PAUSA_ABERTURA_MODAL)

            # 2. Pesquisar documento
            input_search = self.wait.until(EC.visibility_of_element_located((By.XPATH, "//input[contains(@id, 'Input_SearchFilter')]")))
            input_search.clear()
            input_search.send_keys(doc)
            input_search.send_keys(Keys.ENTER)

            # Aguarda a tabela recarregar com o resultado (espera explícita de 2s costuma ser útil em AJAX)
            time.sleep(PAUSA_RECARGA_TABELA)

            # 3. Marcar Checkbox (procura o input do tipo checkbox dentro da tabela visível)
            try:
                checkbox = self.wait.until(EC.presence_of_element_located((By.XPATH, "//td[@data-header='Selecionar']//input[@data-checkbox]")))
                if not checkbox.is_selected():
                    self.driver.execute_script("arguments[0].click();", checkbox)
            except Exception as e:
                print(f"Não encontrou o documento '{doc}' para associar: {e}")

            # (Aqui pode ser necessário clicar em um botão para fechar o modal/confirmar, dependendo da UI)

    def _upload_imagens(self, imagens):
        """Aciona o FilePond nativo injetando o caminho absoluto do arquivo."""
        for img in imagens:
            # 1. Clicar em "Adicionar imagens" (Assumindo que seja um botão similar aos outros)
            # self.safe_click((By.XPATH, "//span[text()='Adicionar imagens']/parent::a"))
            # time.sleep(PAUSA_ABERTURA_MODAL)  -- código já desabilitado antes do CP 2.3; comentário
            # só atualizado por consistência (ver docs/refatoracao/PLANO_REFATORACAO.md Fase 2 -> CP 2.3)

            # 2. Preencher Descrições PT/ES
            desc_es = self.wait.until(EC.presence_of_element_located((By.XPATH, "//input[contains(@id, 'Input_DescriptionES')]")))
            desc_pt = self.wait.until(EC.presence_of_element_located((By.XPATH, "//input[contains(@id, 'Input_DescriptionPT')]")))

            desc_es.clear(); desc_es.send_keys(img["descricao_es"])
            desc_pt.clear(); desc_pt.send_keys(img["descricao_pt"])

            # 3. O Pulo do Gato: Upload Invisível no FilePond
            input_file = self.driver.find_element(By.XPATH, "//input[contains(@class, 'filepond--browser') and @type='file']")

            # O Selenium aceita enviar o caminho local da máquina direto para o input type="file"
            # Importante: O elemento não precisa estar visível/clicável para receber o send_keys()
            input_file.send_keys(img["caminho"])

            # Aguarda a barra de progresso do FilePond processar o arquivo
            time.sleep(PAUSA_UPLOAD_ARQUIVO)

    def _preencher_info_gerais(self, info_gerais):
        """Despeja os dados de Origem, Tipo, Unidade e Fabricação."""
        print("      [Injetor] Preenchendo Informações Gerais...")
        self._escrever_select_por_label("Origem", info_gerais.get("Origem", ""))
        self._escrever_select_por_label("Tipo", info_gerais.get("Tipo", ""))
        self._escrever_select_por_label("Unidade de medida", info_gerais.get("Unidade", ""))
        self._escrever_select_por_label("Tipo de fabricação", info_gerais.get("Fabricacao", ""))

        # Usa o salvamento robusto
        self._clicar_salvar_visivel("Informações Gerais")

    def _escrever_select_por_label(self, texto_label, valor_desejado):
        """Helper para selecionar o dropdown com base no label."""
        if not valor_desejado or valor_desejado == "Selecione": return
        try:
            from selenium.webdriver.support.ui import Select
            xpath = f"//label[contains(text(), '{texto_label}')]/following::select[1]"
            elemento = self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elemento)
            Select(elemento).select_by_visible_text(valor_desejado)
        except Exception as e:
            print(f"Aviso: Não preencheu {texto_label}. {e}")

    def _preencher_condicoes(self, condicoes_por_aba):
        """Varre o dicionário estruturado por aba e aplica o estado, clicando no botão SALVAR visível a cada etapa."""
        # Abre a seção de Condições
        self.safe_click((By.XPATH, "//*[contains(@id, 'Conditions_Header')]//button"))
        time.sleep(PAUSA_ABERTURA_SECAO)

        for aba, campos in condicoes_por_aba.items():
            # Navega para a aba correta
            if aba == "TRANSPORTE": self.safe_click((By.XPATH, "//*[contains(@id, 'Title')]/div[3]"))
            elif aba == "MANUTENCAO": self.safe_click((By.XPATH, "//*[contains(@id, 'Title')]/div[4]"))
            elif aba == "DESCARTE": self.safe_click((By.XPATH, "//*[contains(@id, 'Title')]/div[5]"))
            time.sleep(PAUSA_TROCA_SUBABA)

            # Preenche os campos
            for xpath, valor in campos.items():
                try:
                    elemento = self.driver.find_element(By.XPATH, xpath)
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elemento)

                    if isinstance(valor, bool):
                        if elemento.is_selected() != valor:
                            self.driver.execute_script("arguments[0].click();", elemento)
                    else:
                        if valor:
                            elemento.clear()
                            elemento.send_keys(Keys.CONTROL + "a", Keys.DELETE)
                            elemento.send_keys(str(valor))
                except Exception:
                    pass

            # Procura o botão de SALVAR visível da aba atual e clica
            botoes_salvar = self.driver.find_elements(By.XPATH, "//button[contains(@class, 'btn-primary') and normalize-space(text())='SALVAR']")
            for btn in botoes_salvar:
                if btn.is_displayed() and btn.is_enabled():
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    time.sleep(PAUSA_ANIMACAO)
                    self.driver.execute_script("arguments[0].click();", btn)
                    time.sleep(PAUSA_SALVAMENTO_LONGA)  # Aguarda o salvamento processar
                    break

    def _pesquisar_e_abrir(self, pmib):
        """Navega, pesquisa o PMIB e clica no lápis de edição.

        CP 2.2: mesma migração de `ExtratorFichaBase._pesquisar_e_abrir`
        (cópia idêntica antes deste checkpoint) -- delega para
        `PMIBPortal.pesquisar_e_abrir` com os mesmos seletores
        (`_BUSCA_XPATH_FICHA_DUPLICADA`/`_LAPIS_XPATH_TEMPLATE_FICHA_DUPLICADA`,
        no topo do módulo) e levanta `RuntimeError` em caso de falha, pela
        MESMA razão (preservar a característica "falha alta" do original,
        que não tinha try/except nenhum aqui) -- ver docstring do método
        irmão e docs/refatoracao/PENDENCIAS.md.
        """
        sucesso = self.portal.pesquisar_e_abrir(
            pmib,
            busca_xpath=_BUSCA_XPATH_FICHA_DUPLICADA,
            lapis_xpath_template=_LAPIS_XPATH_TEMPLATE_FICHA_DUPLICADA,
        )
        if not sucesso:
            raise RuntimeError(f"Não foi possível pesquisar/abrir a ficha {pmib}.")

    # --- ORQUESTRADOR PRINCIPAL DA FASE 3 ---
    def clonar_ficha(self, dados_colhidos):
        """Recebe o dicionário da Fase 2 e preenche a ficha alvo."""
        pmib_original = dados_colhidos["pmib"]
        pmib_alvo = dados_colhidos["pmib_alvo"]

        print(f"\n    [Injetor] Iniciando Clonagem na Ficha Alvo: {pmib_alvo}")
        self._pesquisar_e_abrir(pmib_alvo)

        # 1. Info Gerais e Fornecedores (Eles já possuem seus próprios salvamentos/inclusões nas funções)
        self._preencher_info_gerais(dados_colhidos["info_gerais"])
        self._adicionar_fornecedores(dados_colhidos["fornecedores"])

        # 2. Condições (A função já salva cada sub-aba individualmente)
        self._preencher_condicoes(dados_colhidos["condicoes"])

        # 3. Características (Com o novo botão Salvar inserido acima)
        self._limpar_caracteristicas_tecnicas(pmib_original)

        # 4. Imagens e Documentos (Auto-save via FilePond/Checkbox)
        self._associar_documentos(dados_colhidos["documentos_associados"])
        self._upload_imagens(dados_colhidos["imagens_baixadas"])

        return True


class AtualizadorStatusPMIB:
    def __init__(self, caminho_excel, nome_aba="Lista de Materiais"):
        self.caminho_excel = caminho_excel
        self.nome_aba = nome_aba

    def _blindar_numero_pmib(self, valor_celula):
        """Garante a precisão das 4 casas decimais para comparação."""
        # CP 1.2: delega para a implementação única e canônica
        # (core.excel.pmib_codes.normalize_pmib) — este método É a
        # implementação de referência que originou o canônico (ver
        # docs/refatoracao/PLANO_REFATORACAO.md, Fase 1 -> CP 1.2, e
        # tests/test_pmib_normalization_characterization.py).
        return pmib_codes.normalize_pmib(valor_celula)

    def atualizar_ficha_concluida(self, pmib_alvo, secoes_concluidas, callback_log=None):
        """
        Atualiza as colunas especificadas com 'COMPLETO'.
        secoes_concluidas: dicionário bool -> {"INFO. GERAIS": True, "CONDIÇÕES": True, ...}

        CP 1.3: cabeçalho/linha/marcação delegam para
        `core.excel.status_sheet.StatusPMIB`; o retry de `PermissionError`
        (variante AUTO-RETRY do diagnóstico: sleep fixo de 5s, sem limite
        de tentativas -- ver `core.excel.locking`) delega para
        `locking.save_with_retry` via `StatusPMIB.salvar`.

        NOTA DE COMPORTAMENTO (ver docs/refatoracao/PENDENCIAS.md): o laço
        original recarregava o workbook INTEIRO (e reaplicava a busca de
        cabeçalho/edição de célula, incluindo o log "Planilha atualizada
        para PMIB...") a cada retentativa, dentro do próprio `while True`.
        Aqui o workbook é carregado e a célula marcada UMA única vez; só o
        `wb.save(...)` retenta (e o log "Planilha atualizada..." também
        acontece só 1x, não 1x por retentativa). Equivalente no cenário
        real (usuário fecha o Excel e a próxima tentativa de save
        sucede); a diferença é só teórica.
        """
        pmib_formatado = self._blindar_numero_pmib(pmib_alvo)

        painel = status_sheet.StatusPMIB(self.caminho_excel, self.nome_aba)
        try:
            # 1. Busca Dinâmica de Cabeçalho. "CÓDIGO PMIB" é a única
            #    coluna obrigatória (âncora, mesmo alcance de 15 linhas do
            #    original); as colunas de `secoes_concluidas` são
            #    coletadas de forma oportunista, exatamente como antes.
            keywords = {config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB}
            for nome_secao in secoes_concluidas:
                secao_upper = nome_secao.upper()
                keywords[secao_upper] = secao_upper
            painel.abrir(keywords=keywords, required=[config.COL_CODIGO_PMIB], max_row=15)

            if painel.header_row is None:
                if callback_log: callback_log("Erro: Coluna 'CÓDIGO PMIB' não encontrada para atualização.")
                painel.fechar()
                return False

            # 2. Varredura e Atualização.
            linha = painel.buscar_linha(pmib_formatado)

            if linha is not None:
                # Preenche apenas as seções que vieram como True no dicionário.
                painel.marcar_linha(linha, secoes_concluidas)
                if callback_log: callback_log(f"Planilha atualizada para PMIB {pmib_formatado}.")

                def _on_locked(attempt, exc):
                    if callback_log:
                        callback_log("Arquivo aberto. Aguardando 5 segundos para tentar novamente...")
                    time.sleep(PAUSA_RETRY_ARQUIVO_BLOQUEADO)
                    return True  # retenta indefinidamente (sem limite, igual ao `while True` original)

                painel.salvar(on_locked=_on_locked)
            else:
                if callback_log: callback_log(f"Aviso: PMIB {pmib_formatado} não localizado no arquivo para atualização.")

            painel.fechar()
            return True

        except Exception as e:
            if callback_log: callback_log(f"Erro ao salvar Excel: {e}")
            return False
