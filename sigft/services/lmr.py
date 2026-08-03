import pandas as pd
import time
import os

# CP 1.4 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 1): protocolo único
# UI<->serviço. `processar_lista` aceita o novo parâmetro `callbacks`
# preservando `callback_log`/`callback_ask` antigos como aliases
# retrocompatíveis (via `from_legacy`) — ver core/callbacks.py.
# `callback_input` (texto livre) NÃO faz parte de `UICallbacks` — ver
# docstring de core/callbacks.py e docs/refatoracao/PENDENCIAS.md.
from sigft.core.callbacks import UICallbacks, from_legacy
# CP 4.4 (Fase 4): `processar_lista` passa a emitir o padrão único de log
# (início com total/contexto, linha por ficha, resumo com falhas listadas).
# Forma DIRETA (`lote.sucesso/falha`), sem `with lote.item(...)`: o laço já
# tem um `try/except` próprio com semântica particular (`ask` ao usuário +
# tentativa de recarregar a home, com `break` se nem isso funcionar), que
# não vale a pena reescrever só para trocar o mecanismo de contagem.
from sigft.core.relatorio_lote import RelatorioLote

# CP 2.1 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 2): fábrica única de
# driver Chrome, substitui `webdriver.Chrome()` cru em `iniciar_driver`
# abaixo.
# CP 5.2 (Fase 5): `lmr` migrado para o motor escolhido por
# `config.RPA_ENGINE["lmr"]` -- o `selenium` sumiu dos imports deste arquivo.
# Ver `core/rpa/factory.py` e a nota do CP 5.1 em `apagar_lmr.py`.
from sigft.core.rpa.factory import criar_engine
# CP 2.2 (Fase 2): EXCEÇÃO AUTORIZADA pelo plano -- o fluxo de 24 TABs cegos
# de `processar_lista` (ver abaixo) é substituído por uma chamada a
# `PMIBPortal.pesquisar_e_abrir` (mesmo alvo final: abrir a ficha em modo de
# edição) -- única classe onde o plano autoriza essa mudança de MECANISMO
# (não só reorganização) nas Fases 1-4. `_processar_ficha_lmr_interna`
# continua usando `self.driver`/`self.wait` crus, sem nenhuma alteração
# (não tem safe_click/safe_send_keys pra delegar -- ver
# docs/refatoracao/PENDENCIAS.md).
#
# CP 2.3 (Fase 2): os 5 `time.sleep(<literal>)` do arquivo viram constantes
# nomeadas (`PAUSA_ANIMACAO`, `PAUSA_SALVAMENTO`, `PAUSA_ABERTURA_ABA`,
# `PAUSA_RETORNO_LISTA` x2) -- nenhum eliminado.
from sigft.core.rpa.portal import (
    PAUSA_ANIMACAO as PAUSA_TAB_ANTES_DO_ENTER,  # ver comentário no uso, em _processar_ficha_lmr_interna
    PMIBPortal,
    PAUSA_ABERTURA_ABA,
    PAUSA_ANIMACAO,
    PAUSA_RETORNO_LISTA,
    PAUSA_SALVAMENTO,
)


# =============================================================================
# CLASSE DE AUTOMAÇÃO LMR (BACKEND)
# =============================================================================
# CP 5.2 (Fase 5) — seletores XPath do formulário de LMR.
#
# Eram literais repetidos no meio do fluxo. Extraí-los é pré-requisito da
# migração: as primitivas de `RPAEngine` recebem SELETOR (string XPath), não um
# elemento já localizado, então cada XPath passa a aparecer 2x no código
# (esperar/agir). Com o literal solto, isso viraria duplicação convidando a
# divergência -- o problema nº 1 do diagnóstico. Valores idênticos aos de
# antes, verbatim.
# =============================================================================
XPATH_CAMPO_CODIGO = '//*[@id="b10-b19-Input_EquipmentCode"]'
XPATH_CAMPO_QUANTIDADE = '//*[@id="b10-b19-Input_QuantityInstalled"]'
XPATH_CAMPO_TAG = '//*[@id="b10-b19-Input_Tag"]'
XPATH_BOTAO_SALVAR = '//*[@id="b10-b19-Form"]/div[2]/button[1]'
XPATH_BOTAO_CONFIRMAR = '//*[@id="b10-b19-b22-b1-Footer"]/div/button[1]'
XPATH_ABA_LMR = '//*[@id="b10-ApplicationMRL"]/button'
XPATH_VOLTAR = '//*[@id="b9-Content"]'


# =============================================================================
class LMRAutomation:
    def __init__(self):
        self.engine = None
        self.portal = None
        self.url_inicial = 'https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList'

    def iniciar_driver(self):
        """Inicia o navegador Chrome.

        CP 2.1: a criação em si (Chrome + maximize + WebDriverWait(20s))
        agora vem de `create_chrome_driver` (única fábrica, ver
        core/rpa/selenium_engine.py) — timeout preservado EXATAMENTE como
        antes (20s).

        CP 2.2: logo em seguida, `self.portal` passa a existir (`PMIBPortal`
        sobre o engine) -- `processar_lista` abaixo passa a chamar
        `self.portal.pesquisar_e_abrir` no lugar do fluxo de 24 TABs cegos.

        CP 5.2: quem escolhe o motor agora é `criar_engine`, por
        `config.RPA_ENGINE["lmr"]`. Timeout de 20s preservado nos dois
        motores. Devolve o ENGINE (não um driver Selenium) -- `frontend.py`
        não usa o valor de retorno.
        """
        self.engine = criar_engine("lmr", wait_timeout=20)
        self.portal = PMIBPortal(self.engine)
        return self.engine

    def fechar_driver(self):
        if self.engine:
            self.engine.fechar()

    def abrir_portal(self, url=None):
        target = url if url else self.url_inicial
        if self.engine:
            self.engine.goto(target)

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
                except Exception:
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
            # CP 4.2: guarda o índice de ENTRADA desta iteração. É o que
            # permite distinguir, no `except` abaixo, se o agrupamento chegou
            # a avançar `index` (linha `index += 1` dentro do try) ou não --
            # a diferença entre "o laço segue sozinho" e "o laço repete este
            # mesmo item para sempre". Ver o `except` para o racional.
            index_no_inicio = index
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
                #
                # CP 5.2: `clear()` + `send_keys()` de cada campo viraram
                # `engine.clear` + `engine.type_text` -- mesmos seletores,
                # mesma ordem, mesmo par limpar-depois-digitar. Dois desvios
                # deliberados, ambos no sentido de MAIS tolerância (registrados
                # em docs/refatoracao/PENDENCIAS.md):
                #   - quantidade e TAG usavam `driver.find_element`, que não
                #     espera nada e estoura na hora se o campo ainda não
                #     renderizou; as primitivas esperam até o timeout do motor.
                #     Como o `except Exception` deste laço trata qualquer falha
                #     igual, o efeito é só deixar de perder uma ficha por causa
                #     de meio segundo de renderização.
                #   - os cliques de salvar/confirmar eram nativos e passam a ser
                #     via JS (mecânica canônica do projeto).
                self.engine.clear(XPATH_CAMPO_CODIGO)
                self.engine.type_text(XPATH_CAMPO_CODIGO, codigo_pmib_item)

                self.engine.clear(XPATH_CAMPO_QUANTIDADE)
                self.engine.type_text(XPATH_CAMPO_QUANTIDADE, str(quantidade))

                # Insere todas as TAGs com TAB + ENTER após cada uma
                for tag_pmib in grupo_tags:
                    self.engine.clear(XPATH_CAMPO_TAG)
                    self.engine.type_text(XPATH_CAMPO_TAG, tag_pmib)
                    # Era `ActionChains(...).send_keys(TAB).pause(0.5).
                    # send_keys(ENTER).perform()`: o `.pause(0.5)` dava tempo do
                    # autocomplete do OutSystems reagir ao TAB antes do ENTER.
                    # Vira TAB + sleep + ENTER, com a pausa VISÍVEL aqui, no
                    # consumidor, em vez de escondida dentro da cadeia.
                    self.engine.press("TAB")
                    time.sleep(PAUSA_TAB_ANTES_DO_ENTER)
                    self.engine.press("ENTER")
                    time.sleep(PAUSA_ANIMACAO)

                # Salvar e confirmar
                self.engine.click_raw(XPATH_BOTAO_SALVAR)
                self.engine.wait_clickable(XPATH_BOTAO_CONFIRMAR)
                self.engine.click_raw(XPATH_BOTAO_CONFIRMAR)
                time.sleep(PAUSA_SALVAMENTO)

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

                # CP 4.2 -- correção do não-incremento de índice (apontada no
                # diagnóstico do plano, seção 1.5: "no `except` do loop interno
                # o índice não avança -> risco de loop infinito").
                #
                # `index` só avança DENTRO do try, no laço de agrupamento de
                # TAGs. Então há 2 situações bem diferentes aqui:
                if index > index_no_inicio:
                    # (a) O agrupamento concluiu e a falha veio depois, na
                    # interação com o portal. `index` JÁ passou deste código,
                    # então o laço segue sozinho para o próximo -- só avisa.
                    # NÃO oferecemos "tentar de novo": o item pode ter sido
                    # salvo parcialmente no portal, e repetir cegamente
                    # duplicaria TAGs. Rebobinar o índice seria pior que o
                    # problema que este checkpoint conserta.
                    callbacks.ask(
                        f"Erro no item {codigo_pmib_item} durante o preenchimento.\n"
                        "Confira/corrija manualmente no navegador e clique OK — "
                        "o processamento segue para o próximo código.",
                        titulo="Erro LMR",
                    )
                else:
                    # (b) A falha veio ANTES de o índice avançar (ex.: erro ao
                    # ler a linha do DataFrame). Sem intervenção, o `while`
                    # externo repetiria EXATAMENTE este item para sempre --
                    # um modal atrás do outro, sem saída a não ser matar o app.
                    # Como nada chegou a ser enviado ao portal, aqui "tentar de
                    # novo" É seguro, e a escolha fica com o usuário.
                    tentar_de_novo = callbacks.ask(
                        f"Erro no item {codigo_pmib_item} ANTES do envio ao portal:\n{e}\n\n"
                        "SIM = corrigi o problema, tentar este item de novo.\n"
                        "NÃO = pular este item e seguir para o próximo.",
                        titulo="Erro LMR",
                    )
                    if not tentar_de_novo:
                        index = index_no_inicio + 1
                    # Sem provedor de `ask` (execução sem UI), `UICallbacks.ask`
                    # devolve False por contrato (CP 1.4) -> pula. É o default
                    # SEGURO: garante progresso e nunca trava num laço infinito.

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

        lote = RelatorioLote(
            callbacks,
            titulo="LMR — aplicando TAGs nas fichas",
            total=total,
            contexto={"fichas selecionadas": total},
        )
        lote.iniciar()

        for i, pmib_atual in enumerate(lista_pmibs):
            callbacks.log(f"\n--- Ficha {i+1}/{total}: {pmib_atual} ---")

            try:
                # 4.1/4.2. Pesquisar e abrir a ficha em modo de edição.
                #
                # CP 2.2: EXCEÇÃO AUTORIZADA pelo plano -- o fluxo original
                # (campo de busca por ID fixo `b7-InputDatasheetFilter` +
                # Ctrl+A/Backspace/digitar/ENTER + 24 TABs cegos + ENTER no
                # `active_element`) é substituído por uma chamada a
                # `PMIBPortal.pesquisar_e_abrir`, com os seletores DEFAULT
                # (mesmos de `apagar_lmr`/`upload_tech_specs`) -- `lmr` nunca
                # teve um seletor de busca/lápis próprio para "preservar"
                # aqui (a abertura da ficha sempre foi via TABs cegos, não um
                # lápis clicado diretamente); mesmo alvo final: abrir a ficha
                # em modo de edição. Se falhar, levanta para cair no MESMO
                # tratamento de "ERRO FATAL" do `except` abaixo (log + ask +
                # tentativa de recarregar a home), preservando o
                # comportamento observável de uma falha na etapa de
                # pesquisa/abertura.
                callbacks.log(f"Pesquisando: {pmib_atual}")
                if not self.portal.pesquisar_e_abrir(pmib_atual):
                    raise RuntimeError(f"Não foi possível pesquisar/abrir a ficha {pmib_atual}.")

                # 4.3. Clicar na aba "Aplicação - LMR"
                callbacks.log("Abrindo aba LMR...")
                self.engine.wait_clickable(XPATH_ABA_LMR)
                self.engine.click_raw(XPATH_ABA_LMR)
                time.sleep(PAUSA_ABERTURA_ABA)

                # 4.4. Filtrar DataFrame
                df_filtrado = df_completo[df_completo['PMIB'] == pmib_atual].reset_index(drop=True)

                # 4.5. Processamento Interno
                erros = self._processar_ficha_lmr_interna(df_filtrado, callbacks, callback_input)

                if erros:
                    fichas_com_erro.append(pmib_atual)
                    erros_totais.extend(erros)

                # 4.6. Voltar
                callbacks.log("Voltando para lista...")
                time.sleep(PAUSA_RETORNO_LISTA)
                # Botão de voltar do breadcrumb ou similar
                self.engine.wait_clickable(XPATH_VOLTAR)
                self.engine.click_raw(XPATH_VOLTAR)
                time.sleep(PAUSA_RETORNO_LISTA)

                # CP 4.4: a ficha CONCLUIU o fluxo. Se algum item interno
                # falhou, isso é um aviso (causa → consequência), não uma
                # falha da ficha inteira -- o comportamento de hoje já
                # segue para a próxima ficha nesse caso.
                if erros:
                    lote.aviso(
                        pmib_atual,
                        f"{len(erros)} item(ns) da LMR não foram inseridos",
                        "conferir/lançar manualmente no portal (detalhes em erros_lmr.csv)",
                    )
                lote.sucesso(pmib_atual)

            except Exception as e:
                msg = f"ERRO FATAL em {pmib_atual}: {e}"
                callbacks.log(msg)

                fichas_com_erro.append(pmib_atual)
                erros_totais.append({'ficha': pmib_atual, 'erro_fatal': str(e)})

                lote.falha(pmib_atual, f"{type(e).__name__}: {e}")

                callbacks.ask(
                    f"{msg}\nPressione OK para tentar recarregar a home e seguir.",
                    titulo="Erro Fatal",
                )

                try:
                    self.engine.goto(self.url_inicial)
                except Exception:
                    break

        # Relatório Final
        if erros_totais:
            callbacks.log("Salvando relatório de erros (erros_lmr.csv)...")
            try:
                pd.DataFrame(erros_totais).to_csv("erros_lmr.csv", index=False)
            except Exception: pass

        lote.finalizar()
        callbacks.log("Processo Finalizado.")
