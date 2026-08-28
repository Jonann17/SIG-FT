import pandas as pd
import unicodedata

from sigft import config
import time

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
def _mapear_colunas_lmr(colunas_da_aba):
    """{papel: nome real da coluna} ou `None` se faltar algum papel.

    A comparação ignora caixa, acento e espaço em volta: uma planilha
    preenchida à mão traz "Tag LMR", "TAG LMR " e "tag lmr" com igual
    frequência, e reprovar por isso seria implicância.
    """
    normalizados = {}
    for coluna in colunas_da_aba:
        chave = unicodedata.normalize("NFKD", str(coluna)).encode("ascii", "ignore")
        normalizados[chave.decode().strip().upper()] = coluna

    mapa = {}
    for papel, candidatos in config.LMR_COLUNAS.items():
        for nome in candidatos:
            alvo = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().upper()
            if alvo in normalizados:
                mapa[papel] = normalizados[alvo]
                break
        else:
            return None
    return mapa


def agrupar_por_codigo(linhas):
    """[(código, [tags…])] — uma entrada por CÓDIGO LMR, na ordem em que ele
    aparece pela primeira vez.

    ⚠️ CONSERTO DE 2026-08-21, pedido do usuário: *"se o código LMR for X na
    linha 1 e na linha 2 Y e na linha 3 X, ele tem que identificar que são 1
    código e 2 tags distintas, contando 2 quantidades instaladas no código X"*.

    A versão anterior agrupava só TAGs **consecutivas** (`while … == código`),
    o que quer dizer que a planilha precisava estar ORDENADA por código para
    dar o resultado certo. Espalhado, o mesmo código virava duas aplicações de
    1 TAG cada -- duas visitas ao portal, cada uma gravando quantidade 1, e a
    última sobrescrevendo a primeira. A planilha não tem obrigação de estar
    ordenada, e o robô não avisava nada.

    **Tag repetida CONTA.** *"Se aparece com a mesma tag não tem problema, são
    2 distintos. Quem manda é o código: o código LMR repetido significa que
    está em determinado lugar, e daí a quantidade de TAG (independentemente
    distinta ou não) determina a quantidade instalada naquele código LMR."*
    Por isso a lista de tags é uma LISTA e não um conjunto -- trocar por `set`
    aqui perderia unidade instalada em silêncio.

    Linha sem código é descartada: não há aplicação de LMR sem lugar onde ela
    está instalada, e mandá-la ao portal escreveria num campo em branco.
    """
    grupos = {}
    ordem = []
    for codigo, tag in linhas:
        chave = str(codigo or "").strip()
        if not chave:
            continue
        if chave not in grupos:
            grupos[chave] = []
            ordem.append(chave)
        grupos[chave].append(str(tag or "").strip())
    return [(chave, grupos[chave]) for chave in ordem]


def listar_abas(caminho_excel):
    """Nomes das abas do arquivo, na ordem em que aparecem nele.

    É o que popula o seletor de aba da tela. QUEM ESCOLHE É O USUÁRIO: a
    primeira versão disto adivinhava a aba (tentava `LMR`, `GERAL` e depois
    qualquer uma que tivesse as colunas), e o usuário recusou -- com razão.
    Adivinhar aba é o tipo de "ajuda" que funciona nove vezes e, na décima,
    cadastra o lote inteiro a partir da planilha errada sem ninguém notar.
    """
    return list(pd.ExcelFile(caminho_excel).sheet_names)


def _colunas_da_aba(caminho_excel, aba):
    return list(pd.read_excel(caminho_excel, sheet_name=aba, nrows=0).columns)


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
    def carregar_dados_excel(self, caminho_excel, aba=None):
        """
        Lê o Excel, filtra e retorna:
        1. O DataFrame completo limpo.
        2. A lista de PMIBs únicos para seleção.
        """
        try:
            if not aba:
                return False, None, None, (
                    "Nenhuma aba escolhida. Selecione a aba da planilha que contém "
                    "as aplicações de LMR. Abas do arquivo: "
                    + (", ".join(listar_abas(caminho_excel)) or "(nenhuma)")
                )

            aba_usada = aba
            mapa = _mapear_colunas_lmr(_colunas_da_aba(caminho_excel, aba_usada))
            if mapa is None:
                return False, None, None, (
                    f"A aba '{aba_usada}' não tem as colunas da planilha de LMR. "
                    "Esperado (qualquer uma das grafias): "
                    + " | ".join(
                        f"{papel}: {' / '.join(nomes)}"
                        for papel, nomes in config.LMR_COLUNAS.items()
                    )
                    + ". Escolha outra aba no seletor."
                )

            df_bruto = pd.read_excel(caminho_excel, sheet_name=aba_usada, dtype=str)
            # Renomeia para os nomes INTERNOS ('PMIB'/'Código_PMIB'/'TAG_PMIB'),
            # que é o que o resto do módulo já usa. Assim a planilha pode ter
            # o cabeçalho novo ou o antigo sem que nada mais mude.
            df_completo = df_bruto[[mapa["pmib"], mapa["codigo"], mapa["tag"]]].copy()
            df_completo.columns = ['PMIB', 'Código_PMIB', 'TAG_PMIB']

            # Limpeza
            df_completo['PMIB'] = df_completo['PMIB'].str.strip()
            df_completo.dropna(subset=['PMIB'], inplace=True)

            pmibs_unicos = df_completo['PMIB'].unique().tolist()
            return True, df_completo, pmibs_unicos, (
                f"Aba '{aba_usada}': {len(df_completo)} registros e "
                f"{len(pmibs_unicos)} PMIBs únicos."
            )
        except Exception as e:
            return False, None, None, str(e)

    # --- CP 1.4: decisão de linha inicial, extraída para ser testável em
    # isolamento (não toca self.driver/self.wait — roda inteiramente ANTES
    # de qualquer chamada Selenium dentro de `_processar_ficha_lmr_interna`,
    # que só começa em `self.wait.until(...)` depois de resolvida a linha
    # inicial). Mesma lógica do original, só reorganizada num método próprio
    # — ver tests/test_lmr_backend_migration.py.
    def _resolver_linha_inicial(self, df_filtrado, callbacks: UICallbacks,
                                callback_input=None, linha_inicio=None) -> int:
        """Índice do primeiro grupo a processar. Padrão: **0**, sem perguntar.

        ⚠️ MUDOU EM 2026-08-21, a pedido do usuário: *"o default das fichas
        deve ser começar do 0, e somente quando eu peço para começar de uma
        linha específica que deve aparecer a mensagem da ficha específica (tipo
        um toggle pra habilitar/desabilitar)"*.

        Antes, TODA execução abria um Sim/Não ("deseja começar de uma linha
        específica?") e, se sim, um segundo diálogo pedindo o número -- duas
        caixas por ficha, para uma resposta que é "não" quase sempre. Agora
        quem decide é a TELA, pelo toggle, e ela manda o número pronto.

        `callback_input` continua na assinatura porque `_processar_ficha_lmr_
        interna` o repassa, mas NÃO é mais consultado: manter o parâmetro evita
        mexer na cadeia de chamadas por causa de um argumento morto, e o
        docstring diz que ele não faz nada.

        Fora da faixa vira 0 **com aviso no log** -- silenciar aqui faria o
        usuário pedir a linha 50 numa ficha de 3 códigos e achar que ela foi
        processada a partir dali.
        """
        if linha_inicio is None:
            return 0

        try:
            linha_inicio = int(linha_inicio)
        except (TypeError, ValueError):
            callbacks.log(f"Linha inicial inválida ({linha_inicio!r}). Começando do 0.")
            return 0

        if linha_inicio < 0 or linha_inicio >= len(df_filtrado):
            callbacks.log(
                f"Linha inicial {linha_inicio} fora da faixa (0 a "
                f"{max(len(df_filtrado) - 1, 0)}). Começando do 0.")
            return 0

        return linha_inicio

    # --- LÓGICA CORE (MANTIDA DO ORIGINAL) ---
    def _processar_ficha_lmr_interna(self, df_filtrado, callbacks: UICallbacks,
                                     callback_input=None, linha_inicio=None):
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

        # AGRUPAMENTO POR CÓDIGO, INDEPENDENTE DA ORDEM (2026-08-21).
        #
        # Antes o laço andava linha a linha e juntava TAGs CONSECUTIVAS, o que
        # exigia a planilha ordenada por código. Espalhado (X, Y, X), o mesmo
        # código virava duas aplicações de 1 TAG cada -- duas visitas ao
        # portal, a segunda sobrescrevendo a quantidade da primeira, sem aviso
        # nenhum. Ver `agrupar_por_codigo`.
        #
        # A unidade de iteração passou a ser o CÓDIGO, não a linha da planilha:
        # `linha_inicio` conta grupos, e o log diz quantos são.
        grupos = agrupar_por_codigo(
            (df_filtrado.loc[i, 'Código_PMIB'], df_filtrado.loc[i, 'TAG_PMIB'])
            for i in range(len(df_filtrado))
        )
        callbacks.log(
            f"{len(df_filtrado)} linha(s) -> {len(grupos)} código(s) LMR distinto(s)."
        )

        # Depois do agrupamento, e não antes: `linha_inicio` conta GRUPOS,
        # então a faixa válida só existe quando os grupos existem.
        linha_inicio = self._resolver_linha_inicial(
            grupos, callbacks, callback_input, linha_inicio)

        processados_ok = []
        processados_erro_ficha = []

        index = linha_inicio
        while index < len(grupos):
            codigo_pmib_item = ""
            # CP 4.2: guarda o índice de ENTRADA desta iteração, para o
            # `except` distinguir "o laço segue sozinho" de "o laço repete este
            # mesmo item para sempre".
            index_no_inicio = index
            try:
                codigo_pmib_item, grupo_tags = grupos[index]
                index += 1

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
        linha_inicio=None,
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
        # 2026-08-28: as fichas que CHEGARAM AO FIM do fluxo, com ou sem erro.
        # Não é o mesmo que `lista_pmibs`: o laço pode terminar cedo (o `break`
        # quando nem a home recarrega), e marcar no `_STATUS_PMIB` uma ficha que
        # nunca foi aberta seria pior que não marcar nada.
        fichas_processadas = []

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
                erros = self._processar_ficha_lmr_interna(
                    df_filtrado, callbacks, callback_input, linha_inicio)

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
                # Chegou ao fim do fluxo -- entra na marcação do `_STATUS_PMIB`
                # como COMPLETO (se `erros` estava vazio) ou INCOMPLETO.
                fichas_processadas.append(pmib_atual)

            except Exception as e:
                msg = f"ERRO FATAL em {pmib_atual}: {e}"
                callbacks.log(msg)

                fichas_com_erro.append(pmib_atual)
                erros_totais.append({'ficha': pmib_atual, 'erro_fatal': str(e)})
                # Falhou, mas foi TENTADA: vai para o `_STATUS_PMIB` como
                # INCOMPLETO. Marcar o fracasso é informação — o que não pode
                # acontecer é a planilha ficar em branco sobre uma ficha que o
                # robô mexeu.
                fichas_processadas.append(pmib_atual)

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

        # 2026-08-28: retorno NOVO e aditivo -- quem chamava sem usar o retorno
        # (a tela, até agora) continua funcionando igual.
        #
        # Serve para a tela marcar a coluna "APLICAÇÃO - LMR" do `_STATUS_PMIB`,
        # como as outras 4 seções já eram marcadas. Mesmo contrato que
        # `upload_conditions.processar_lista` devolve: `(completas, incompletas)`.
        #
        # Só entram fichas que o robô REALMENTE tentou (`fichas_processadas`).
        # Se o laço parou no meio, as que não foram abertas ficam de fora dos
        # dois lados — não marcar é honesto; marcar seria mentira.
        completas = [p for p in fichas_processadas if p not in fichas_com_erro]
        incompletas = [p for p in fichas_processadas if p in fichas_com_erro]
        return completas, incompletas


def marcar_status_pmib(
    caminho_status,
    completas,
    incompletas,
    *,
    retry_lock=None,
    callback_log=None,
):
    """Marca a coluna "APLICAÇÃO - LMR" do `_STATUS_PMIB` para as fichas do lote.

    Acrescentado em 2026-08-28, a pedido do usuário: a tela de Aplicação LMR
    passa a registrar na planilha o que registrava só no console. É o mesmo
    papel que `upload_conditions` cumpre para a coluna "CONDIÇÕES".

    `completas` recebem COMPLETO; `incompletas` recebem INCOMPLETO. Marcar o
    fracasso é decisão do usuário e é informação: uma ficha que o robô mexeu e
    deixou pela metade precisa aparecer na planilha, senão ela se confunde com
    uma que ninguém tocou.

    Devolve `(quantidade_marcada, mensagem)`. Nunca levanta por causa da
    planilha — uma falha aqui não pode apagar o trabalho que o robô já fez no
    portal, que é a parte cara e não repetível.
    """
    from sigft.core.excel import status_sheet

    alvos = [(p, "COMPLETO") for p in completas]
    alvos += [(p, "INCOMPLETO") for p in incompletas]
    if not alvos:
        return 0, "Nenhuma ficha para marcar no _STATUS_PMIB."

    def _log(msg):
        if callback_log:
            callback_log(msg)

    try:
        painel = status_sheet.StatusPMIB(caminho_status, config.ABA_LISTA_MATERIAIS)
        # A coluna de LMR entra com TODOS os aliases apontando para a MESMA
        # chave de saída -- é o recurso que `find_columns` oferece para
        # cabeçalho com grafia variável (ver config.ALIASES_COL_APLICACAO_LMR).
        painel.abrir(
            keywords={
                config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB,
                config.COL_APLICACAO_LMR: config.ALIASES_COL_APLICACAO_LMR,
            },
            # `required` só o código: a varredura não pode parar por não achar
            # a coluna de LMR -- precisamos chegar ao fim para poder LISTAR os
            # cabeçalhos que existem, que é o que ajuda quem for corrigir.
            required=[config.COL_CODIGO_PMIB],
            max_row=15,
            max_col=49,
        )
    except Exception as erro:  # noqa: BLE001 -- planilha não pode derrubar o lote
        return 0, f"Não consegui abrir o _STATUS_PMIB: {type(erro).__name__}: {erro}"

    if config.COL_APLICACAO_LMR not in painel.col_map:
        encontrados = _cabecalhos_da_linha(painel)
        return 0, (
            f"A coluna '{config.COL_APLICACAO_LMR}' não foi encontrada no _STATUS_PMIB "
            f"-- nada foi marcado.\n"
            f"      Cabeçalhos que existem na planilha: {encontrados}\n"
            f"      Se o nome certo for um destes, me diga qual e eu ajusto "
            f"(config.ALIASES_COL_APLICACAO_LMR)."
        )

    header_row = painel.header_row if painel.header_row is not None else 1
    marcadas, nao_achadas = 0, []

    for pmib, status in alvos:
        linha = painel.buscar_linha(str(pmib).strip(), header_row=header_row)
        if linha is None:
            nao_achadas.append(str(pmib))
            continue
        painel.marcar_linha(linha, {config.COL_APLICACAO_LMR: True}, valor=status)
        marcadas += 1
        _log(f"   Planilha: {pmib} -> {config.COL_APLICACAO_LMR} = {status}")

    if not marcadas:
        painel.fechar()
        return 0, (
            "Nenhuma das fichas do lote foi encontrada no _STATUS_PMIB "
            f"(procurei {len(alvos)}). Nada foi salvo."
        )

    # O salvamento passa pelo canal do CP D: com a planilha aberta no Excel, o
    # usuário vê a janela "feche o arquivo e tente de novo" em vez de perder a
    # marcação em silêncio.
    try:
        painel.salvar(on_locked=lambda _tent, _exc: bool(retry_lock(caminho_status))
                      if retry_lock else False)
    except PermissionError:
        painel.fechar()
        return 0, (
            "O _STATUS_PMIB está aberto no Excel e a marcação NÃO foi salva. "
            "O trabalho no portal está feito -- feche a planilha e rode de novo "
            "só para marcar, ou marque à mão."
        )
    except Exception as erro:  # noqa: BLE001
        painel.fechar()
        return 0, f"Não consegui salvar o _STATUS_PMIB: {type(erro).__name__}: {erro}"

    painel.fechar()

    recado = f"{marcadas} linha(s) marcada(s) no _STATUS_PMIB."
    if nao_achadas:
        recado += (
            f" {len(nao_achadas)} ficha(s) não foram encontradas na planilha: "
            f"{', '.join(nao_achadas[:5])}"
            + ("…" if len(nao_achadas) > 5 else "")
        )
    return marcadas, recado


def _cabecalhos_da_linha(painel):
    """Os textos da linha de cabeçalho, para a mensagem de erro poder DIZER o
    que a planilha tem — em vez de só reclamar do que ela não tem."""
    try:
        linha = painel.header_row or 1
        valores = [
            str(painel.ws.cell(row=linha, column=c).value or "").strip()
            for c in range(1, 50)
        ]
        return ", ".join(f"'{v}'" for v in valores if v) or "(nenhum)"
    except Exception:  # noqa: BLE001
        return "(não consegui ler)"
