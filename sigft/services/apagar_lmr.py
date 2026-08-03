import time

from sigft import config

# CP 1.4 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 1): protocolo único
# UI<->serviço. `executar_limpeza` aceita o novo parâmetro `callbacks`
# preservando o `callback_log` antigo como alias retrocompatível (via
# `from_legacy`) — ver core/callbacks.py.
from sigft.core.callbacks import UICallbacks, from_legacy

# CP 5.1 (Fase 5): este é o módulo PILOTO da migração para Playwright. O
# `selenium` sumiu dos imports daqui: quem decide o motor é
# `factory.criar_engine("apagar_lmr")`, lendo `config.RPA_ENGINE`. Trocar de
# motor (ou voltar atrás) é editar uma linha de config ou exportar
# `SIGFT_RPA_ENGINE` -- nenhuma linha deste arquivo muda.
#
# As exceções que o laço de exclusão discrimina por tipo (fim normal x tabela
# reconstruída) passam a ser as NEUTRAS de `engine.py`, traduzidas por cada
# motor. Sem isso, o laço rodaria para sempre no Playwright: um
# `except TimeoutException` do Selenium não enxerga o `TimeoutError` do
# Playwright.
from sigft.core.rpa.engine import ElementoObsoleto, TempoEsgotado
from sigft.core.rpa.factory import criar_engine
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

# CP 4.4 (Fase 4, docs/refatoracao/PLANO_REFATORACAO.md): padrão único de log
# de lote. O loop de exclusão é o único "lote" deste módulo -- cada aplicação
# LMR apagada é um item (não há um loop externo de várias fichas aqui: uma
# chamada de `executar_limpeza` já é sobre UM PMIB só).
from sigft.core.relatorio_lote import RelatorioLote


# =============================================================================
# CLASSE DE AUTOMAÇÃO - APAGAR LMR
# =============================================================================
class ApagarLMRAutomation:
    def __init__(self):
        self.engine = None
        self.portal = None
        self.url_inicial = config.PORTAL_URL

    def iniciar_driver(self):
        """Inicia o navegador.

        CP 2.1: a criação em si (Chrome + maximize + WebDriverWait(20s))
        veio de `create_chrome_driver` (única fábrica) — timeout preservado
        EXATAMENTE como antes (20s).

        CP 2.2: logo em seguida, `self.portal` passa a existir
        (`PMIBPortal` sobre o engine) — `safe_click`/`_pesquisar_e_abrir`
        abaixo delegam para ele.

        CP 5.1: quem escolhe o motor agora é `criar_engine`, pelo
        `config.RPA_ENGINE["apagar_lmr"]`. O timeout de 20s continua o
        mesmo nos dois motores.

        Continua devolvendo algo verdadeiro para não quebrar chamadores que
        testem o retorno — mas o que volta é o ENGINE, não um driver
        Selenium. `frontend.py` não usa o valor (só chama
        `iniciar_driver()`), e é de propósito que um consumidor que tentasse
        usá-lo como driver falhe alto: seria justamente um ponto ainda não
        migrado.
        """
        self.engine = criar_engine("apagar_lmr", wait_timeout=20)
        self.portal = PMIBPortal(self.engine)
        return self.engine

    def fechar_driver(self):
        if self.engine:
            self.engine.fechar()

    def abrir_portal(self):
        if self.engine:
            self.engine.goto(self.url_inicial)

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
            # CP 5.1: `wait.until(element_to_be_clickable(...)).click()` virou
            # `wait_clickable` + `click_raw` -- mesma sequência (esperar
            # clicável, depois clicar), agora sem tocar em Selenium. O
            # `except` de baixo continua tratando qualquer falha como "a aba
            # pode já estar aberta", igual a antes.
            xpath_aba_lmr = '//*[@id="b10-ApplicationMRL"]/button'
            self.engine.wait_clickable(xpath_aba_lmr)
            self.engine.click_raw(xpath_aba_lmr)
            time.sleep(PAUSA_ABERTURA_ABA)
        except Exception as e:
            callbacks.log(f"Erro ao abrir aba LMR (pode já estar aberta): {e}")

        # 3. Loop de Exclusão (Original)
        #
        # CP 4.4: envolvido por `RelatorioLote` -- cada aplicação LMR apagada
        # vira um "item" do lote (identificador "Aplicação N"), com o resumo
        # final (contagem + tempo total) saindo automaticamente ao fim do
        # `with`. NADA da lógica original muda: mesmos seletores, mesma
        # ordem, mesmos `time.sleep` (`PAUSA_ABERTURA_ABA`/
        # `PAUSA_POS_EXCLUSAO`, intocados), mesmo tratamento por tipo de
        # exceção (`TimeoutException` = fim normal; `StaleElementReference`
        # = tenta de novo; outra exceção = para). Usa a forma DIRETA
        # (`lote.sucesso`/`falha`, não `lote.item()`) porque o try/except já
        # existente tem 3 ramos com semânticas DIFERENTES (fim normal / retry
        # / erro real) que `lote.item()` (que trata QUALQUER exceção como
        # falha) confundiria.
        with RelatorioLote(
            callbacks,
            titulo=f"Apagando aplicações LMR do PMIB {pmib_codigo}",
            contexto={"pmib": pmib_codigo},
        ) as lote:
            count = 0

            while True:
                inicio_item = time.time()
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

                    # CP 5.1: a mesma sequência de antes -- esperar a lixeira
                    # ficar clicável, rolar até ela, clicar -- agora pelas
                    # primitivas do engine. É esta espera que serve de SINAL
                    # DE FIM do lote: quando não há mais lixeira, ela estoura
                    # o tempo e cai no `except TempoEsgotado` lá embaixo.
                    #
                    # Único desvio do original, deliberado: o clique era
                    # `lixeira.click()` NATIVO e passa a ser via JS
                    # (`click_raw`, a mecânica canônica do projeto -- ver
                    # `selenium_engine.click_raw` e PENDENCIAS.md). Efeito
                    # prático: um overlay que interceptasse o clique deixa de
                    # derrubar o laço.
                    self.engine.wait_clickable(xpath_lixeira)
                    self.engine.scroll_to(xpath_lixeira)
                    self.engine.click_raw(xpath_lixeira)

                    # Espera o botão de confirmação da exclusão e clica
                    # XPath original: //*[@id="b10-b19-b17-b10-b1-Footer"]/div/button[1]
                    xpath_confirmar = '//button[@type="button" and text()="CONFIRMAR"]'  # Mais genérico/seguro ou usar o ID original

                    self.engine.wait_clickable(xpath_confirmar)
                    self.engine.click_raw(xpath_confirmar)

                    # Espera a exclusão processar
                    count += 1
                    lote.sucesso(f"Aplicação {count}", duracao_s=time.time() - inicio_item)
                    time.sleep(PAUSA_POS_EXCLUSAO)  # Pausa para refresh da tabela

                except TempoEsgotado:
                    # Não achou mais lixeiras -> Fim
                    callbacks.log("✅ Todas as aplicações visíveis foram apagadas.")
                    break
                except ElementoObsoleto:
                    # Tabela atualizou enquanto tentava clicar -> Tenta loop de novo
                    continue
                except Exception as e:
                    # Outro erro -> Para
                    lote.falha(f"Aplicação {count + 1}", f"{type(e).__name__}: {e}")
                    break

        # Voltar para lista (opcional, bom para fluxo continuo)
        try:
            self.engine.goto(self.url_inicial)
        except Exception:
            pass
