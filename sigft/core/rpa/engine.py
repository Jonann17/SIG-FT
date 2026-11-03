r"""
sigft/core/rpa/engine.py — interface mínima do motor de automação de browser
(Checkpoint 2.1 do plano de refatoração).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 2 (nota introdutória) e
CP 2.1: "a Fase 2 ainda roda sobre Selenium, mas a API pública do
`PMIBPortal` é definida em termos de intenção (`clicar`, `preencher`,
`esperar_linha`, `pesquisar_e_abrir`), não de Selenium. É o contrato que a
Fase 5 reimplementa em Playwright."

`RPAEngine` é essa camada mais BAIXA (abaixo de `PMIBPortal`, que chega no
CP 2.2): um punhado de operações de INTENÇÃO sobre um browser -- navegar,
clicar, preencher, esperar, ler, tirar print, configurar pasta de download
-- sem NENHUMA palavra "Selenium"/"Playwright" neste arquivo. Isso é
DELIBERADO: é o que permite a Fase 5 (`playwright_engine.py`) implementar
esta MESMA interface sem tocar em nenhum consumidor (serviço/`PMIBPortal`).

Interface exigida pelo CP 2.1: `goto(url)`, `click(seletor)`,
`fill(seletor, texto)`, `press(teclas)`, `wait_visible(seletor)`,
`wait_clickable(seletor)`, `element_exists(seletor)`, `get_value(seletor)`,
`screenshot(caminho)`, `set_download_dir(caminho)`.

Decisões de contrato (ver especificação do CP 2.1):
  - Todo `seletor` é uma STRING XPATH pura (não uma tupla `(By, valor)`).
    Levantamento do CP 2.1 por grep: 139 dos 140 usos de `By.*` no
    repositório hoje já são `By.XPATH` (a única exceção -- um
    `By.CSS_SELECTOR` de leitura de tooltip "PDM Final" em
    `cria_fichas_no_pmib_v1_backend.py:396` -- fica fora do escopo deste
    checkpoint: não é criação de driver, e migrar esse uso de leitura é
    trabalho do CP 2.2; ver docs/refatoracao/PENDENCIAS.md). XPath também é
    o que a nota da Fase 5 cita como reaproveitável em Playwright
    ("Seletores XPath atuais são reaproveitados... Playwright aceita
    XPath").
  - `press(teclas)` NÃO recebe seletor: envia a(s) tecla(s) nomeada(s)
    (ex.: `"ENTER"`, `["TAB", "TAB", "ENTER"]`) ao elemento que estiver COM
    FOCO no momento -- é o mesmo padrão de hoje via
    `driver.switch_to.active_element` (ex.:
    `cria_fichas_no_pmib_v1_backend.AutomacaoPMIB.processar_item_individual`,
    `lmr_backend.LMRAutomation.processar_lista`).
  - `element_exists(seletor)` é uma checagem IMEDIATA ("existe agora, sem
    esperar?"), DIFERENTE de `wait_visible`/`wait_clickable` (que BLOQUEIAM
    até a condição ser satisfeita ou o timeout do motor estourar). Ver
    `playwright_engine.py` para a implementação concreta de cada um. (Houve um
    `selenium_engine.py` até o CP 5.5; a abstração nasceu para permitir os dois
    lado a lado, e é o que tornaria barato um terceiro.)
  - `get_value(seletor)` lê o valor atual de um campo de formulário (mesmo
    papel do `_ler_input`/`get_attribute("value")` de hoje em
    `upload_ficha_duplicada.ExtratorFichaBase`).

Só biblioteca padrão (`abc`) -- importável em `tests/` sem NENHUM stub (ver
tests/conftest.py): nenhuma implementação concreta (Selenium, Playwright)
vive aqui, só o contrato abstrato. É isso que torna este arquivo estável
através da troca de motor da Fase 5: `playwright_engine.PlaywrightEngine`
herdará de `RPAEngine` sem que uma linha aqui precise mudar.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


# =============================================================================
# Exceções NEUTRAS de motor (Checkpoint 5.1)
# =============================================================================
# Sem elas a Fase 5 não sai do papel. Hoje vários laços de produção decidem o
# que fazer OLHANDO O TIPO da exceção do Selenium:
#
#   `apagar_lmr.executar_limpeza`: `except TimeoutException` = "não há mais
#   lixeiras, o lote acabou" (fim NORMAL, não erro); `except
#   StaleElementReferenceException` = "a tabela se reconstruiu, tenta de novo".
#
# `selenium.common.exceptions.TimeoutException` e o
# `playwright.sync_api.TimeoutError` não têm parentesco nenhum: um serviço que
# capture o primeiro simplesmente NÃO enxerga o segundo, e o laço acima viraria
# um loop infinito silencioso ao trocar de motor. Por isso cada engine traduz a
# exceção do seu SDK para uma destas, e os consumidores capturam só estas.
#
# `ElementoObsoleto` não tem equivalente em Playwright (que reavalia o seletor a
# cada ação, em vez de guardar uma referência que "envelhece"). Isso é esperado
# e não é um buraco: os `except ElementoObsoleto: continue` viram ramos que
# nunca disparam no motor novo — que é exatamente o ganho de estabilidade que a
# decisão de produto nº 5 busca.
class ErroRPA(Exception):
    """Base de todas as falhas traduzidas de um motor de browser."""


class TempoEsgotado(ErroRPA):
    """Uma espera estourou o tempo limite. Traduz
    `selenium.common.exceptions.TimeoutException` e
    `playwright.sync_api.TimeoutError`."""


class ElementoObsoleto(ErroRPA):
    """A referência ao elemento envelheceu porque a página se reconstruiu
    embaixo dela. Traduz `selenium.common.exceptions.
    StaleElementReferenceException`; em Playwright não ocorre."""


class RPAEngine(ABC):
    """Contrato único que um serviço de automação (hoje `*_backend.py`
    diretamente; `PMIBPortal` a partir do CP 2.2) usa para falar com um
    browser, sem conhecer se por trás roda Selenium
    (`selenium_engine.SeleniumEngine`, Fases 1-4, removido no CP 5.5) ou Playwright
    (`playwright_engine.PlaywrightEngine`, Fase 5)."""

    @abstractmethod
    def goto(self, url: str) -> None:
        """Navega para `url`."""

    @abstractmethod
    def click(self, seletor: str) -> None:
        """Clica no elemento localizado por `seletor` (XPath)."""

    @abstractmethod
    def fill(self, seletor: str, texto: str) -> None:
        """Limpa e preenche o campo localizado por `seletor` (XPath) com
        `texto`."""

    @abstractmethod
    def press(self, teclas: str | list[str]) -> None:
        """Envia a(s) tecla(s) nomeada(s) (ex.: `"ENTER"`,
        `["TAB", "TAB", "ENTER"]`) ao elemento que estiver com foco no
        momento -- não recebe seletor."""

    @abstractmethod
    def wait_visible(self, seletor: str) -> None:
        """Bloqueia até o elemento localizado por `seletor` ficar
        visível."""

    @abstractmethod
    def wait_clickable(self, seletor: str) -> None:
        """Bloqueia até o elemento localizado por `seletor` ficar
        clicável."""

    @abstractmethod
    def element_exists(self, seletor: str) -> bool:
        """Checagem IMEDIATA (sem esperar): `seletor` existe na página
        agora?"""

    @abstractmethod
    def get_value(self, seletor: str) -> str:
        """Lê o valor atual (`value`) do campo de formulário localizado por
        `seletor`."""

    @abstractmethod
    def screenshot(self, caminho: str) -> None:
        """Salva uma captura de tela em `caminho`."""

    @abstractmethod
    def set_download_dir(self, caminho: str) -> None:
        """Redireciona downloads subsequentes (da sessão já aberta) para a
        pasta `caminho`."""

    # =====================================================================
    # Primitivas acrescentadas pelo Checkpoint 5.1
    # =====================================================================
    # Os 10 métodos acima (CP 2.1) cobriam a INTENÇÃO dos serviços, mas não
    # o suficiente para o `PMIBPortal` largar o `self.engine.driver`/`.wait`
    # cru -- e enquanto ele não larga, trocar de motor é impossível, porque
    # um `PlaywrightEngine` não tem `.driver` nem `.wait` nenhum.
    #
    # Cada primitiva abaixo corresponde a UMA operação Selenium que hoje
    # está escrita à mão dentro de `portal.py`/`services/apagar_lmr.py`; a
    # implementação em `SeleniumEngine` é a MESMA LINHA, movida, não
    # reescrita. Isso é o que garante que o motor Selenium continue se
    # comportando exatamente como antes deste checkpoint (o caminho de
    # rollback do CP 5.1) enquanto o Playwright ganha um caminho próprio.
    #
    # A separação `click` vs `click_estrito` merece nota: `click` ENGOLE
    # exceção desde o CP 2.1 (é a mecânica do antigo `safe_click`, e é o que
    # `PMIBPortal.safe_click` promete). Num LAÇO que decide continuar ou
    # parar pelo resultado do clique -- o laço de exclusão de `apagar_lmr` é
    # exatamente isso -- engolir a falha faria o clique virar um no-op
    # silencioso e o laço girar sem fim. Daí a variante estrita.

    @abstractmethod
    def click_estrito(self, seletor: str) -> None:
        """Igual a `click`, mas PROPAGA a falha (`TempoEsgotado`,
        `ElementoObsoleto`) em vez de engoli-la. Para laços que decidem o
        que fazer a partir do resultado do clique."""

    @abstractmethod
    def fill_estrito(self, seletor: str, texto: str) -> None:
        """Igual a `fill` (limpa e preenche), mas PROPAGA a falha em vez de
        engoli-la -- o mesmo par que `click`/`click_estrito` forma.

        Necessário onde o chamador REPORTA o resultado:
        `cria_fichas.atualizar_projeto_em_massa` devolve `("SUCESSO", ...)` /
        `("ERRO", ...)`. Se o preenchimento falhasse em silêncio, a função
        seguiria para o botão salvar, salvaria a ficha sem o novo código de
        projeto e devolveria SUCESSO -- um resultado errado, e pior que um
        erro, porque ninguém vai conferir."""

    @abstractmethod
    def scroll_to(self, seletor: str) -> None:
        """Rola a página até o elemento ficar centralizado na viewport, sem
        clicar nem esperar por condição nenhuma."""

    @abstractmethod
    def click_raw(self, seletor: str) -> None:
        """Clica SEM a espera de "clicável" e sem rolar a tela antes.

        Existe porque `scroll_to` + `click_raw` é a sequência EXATA de dois
        pontos de produção que o CP 5.1 porta (o clique no lápis de
        `pesquisar_e_abrir` e o da lixeira em `apagar_lmr`), e ambos têm
        entre o scroll e o clique um `time.sleep` PRÓPRIO, de valor
        diferente. Espremer os dois dentro de `click_estrito` obrigaria a
        escolher um dos sleeps e a acrescentar ao lápis uma espera de
        "clicável" que ele nunca teve -- ou seja, mudaria o comportamento de
        4 módulos que continuam no Selenium. A decomposição mantém a
        orquestração (e os sleeps) no consumidor, onde ela sempre esteve."""

    @abstractmethod
    def click_nativo(self, seletor: str) -> None:
        """Clique de MOUSE DE VERDADE: espera "clicável" e clica como um
        usuário clicaria -- **movendo o foco do navegador para o alvo**.

        É a única primitiva de clique com essa garantia, e ela não é um
        detalhe: `click`, `click_estrito` e `click_raw` clicam por JavaScript
        (`arguments[0].click()`) no motor Selenium, e um clique sintético
        dispara o evento de clique mas NÃO executa os "focusing steps" que o
        navegador roda num clique real. O foco fica onde estava.

        Isso é invisível em quase todo o sistema -- clicar num botão de
        Salvar não depende de foco nenhum. Mas em `cria_fichas` o fluxo
        inteiro de preenchimento da ficha é *relativo ao foco*: clica num
        campo e a partir dali só há `press("TAB")` e `digitar_no_foco(...)`.
        Se o clique não leva o foco junto, as teclas seguintes vão para o
        elemento errado -- sem erro, sem log, com o campo simplesmente
        vazio. Foi o que aconteceu no primeiro teste real da Fase 5
        (Contrato em branco, "Campo obrigatório!"); ver
        docs/refatoracao/PENDENCIAS.md.

        Em Playwright todo `Locator.click()` já é um clique real via CDP, o
        que torna esta primitiva idêntica a `click_raw` naquele motor. Ela
        existe para o contrato poder DIZER "aqui o foco importa", em vez de
        depender de qual motor está montado.
        """

    @abstractmethod
    def click_dom(self, seletor: str) -> None:
        """Clique disparado pelo DOM (`elemento.click()`), SEM checagem de
        acionabilidade -- sem exigir que o alvo esteja visível, estável ou
        desobstruído. Exige apenas que ele exista.

        **Por que esta primitiva precisou existir (2026-08-18).** Ela é o que
        `click`/`click_estrito` sempre fizeram no motor Selenium
        (`execute_script("arguments[0].click()")`) e o que o motor Playwright
        NÃO tinha: lá `Locator.click()` é um clique de mouse real e roda a
        checagem de "hit target" -- se qualquer outro elemento receber o
        evento no ponto do clique, ele espera até o timeout e falha.

        Isso quebrou `upload_conditions` na migração, e a assimetria explica
        exatamente qual módulo quebrou. O controle customizado do OutSystems é

            <div class="custom"><span><input class="radio-button" ...></span>
                                <label>Não contém agentes nocivos</label></div>

        -- o `<input>` real fica coberto pelo rótulo estilizado, que é o que o
        usuário enxerga e clica. O clique por JavaScript passa por cima disso;
        o clique de mouse real, não. `upload_conditions` tem 19 seletores de
        radio/checkbox; `tech_specs` tem ZERO. Foi por isso que um quebrou e o
        outro não, e não por instabilidade do motor novo.

        Pior: `click` ENGOLE a falha por contrato, então cada campo perdido
        custava o timeout inteiro (20 s) e não deixava uma linha de log.

        Use quando o alvo é um controle que o navegador considera não
        acionável mas que a página trata como clicável. Para tudo o mais,
        `click`/`click_estrito` continuam melhores: a checagem de
        acionabilidade pega erro de seletor que o clique por DOM esconde.
        """

    @abstractmethod
    def html_do_elemento(self, seletor: str) -> str:
        """`outerHTML` do primeiro elemento que casar -- `""` se não casar nada.

        Existe para o MODO DE AUDITORIA (2026-08-18): quando o robô visita uma
        seção, o log de execução guarda a estrutura real da tela. Isso troca
        "abra o inspecionar elemento e copie caixa por caixa" por "rode uma
        vez e me mande o arquivo de log" -- e é a única forma de mapear uma
        seção do portal sem acesso a ele.

        NÃO levanta quando o seletor não casa: auditar é observar, e um modo
        de observação que derruba o lote observado não serve para nada.
        """

    @abstractmethod
    def bytes_da_imagem(self, seletor: str) -> bytes:
        """Bytes da imagem apontada por `seletor` (um `<img>`). `b""` se não
        der para ler.

        ⚠️ EXISTE POR CAUSA DO `blob:`. As imagens da ficha no PMIB são
        servidas assim:

            <img class="custom-img" src="blob:https://apps.itaipu.gov.br/29077935-…">

        Um `blob:` **não é um endereço HTTP**: é um identificador de objeto que
        só vale DENTRO daquela página, naquela sessão. Baixá-lo com `requests`
        não funciona -- não existe servidor do outro lado. Ele só pode ser lido
        de dentro do navegador.

        Por que uma primitiva de CONCEITO e não um `executar_js` genérico: a
        mecânica difere de verdade entre os motores (o Playwright espera uma
        promessa naturalmente; o Selenium precisa de `execute_async_script` com
        callback). Expor "rode este JS" obrigaria o serviço a escrever os dois
        scripts e a saber qual motor está rodando -- exatamente o que o
        `RPAEngine` existe para evitar. Expor "me dê os bytes" mantém o serviço
        ignorante e deixa cada motor resolver do seu jeito.

        NÃO levanta: imagem que não se consegue ler vira pendência no log, não
        derruba a ficha.
        """

    @abstractmethod
    def enviar_arquivo(self, seletor: str, caminho: str | list[str]) -> None:
        """Entrega `caminho` ao `<input type="file">` de `seletor`. Uma LISTA
        entrega vários de uma vez (input com `multiple`, como o do FilePond).

        É o par de `bytes_da_imagem`: um lê a imagem da ficha original, o outro
        a sobe na ficha nova. Propaga falhas -- upload que não acontece tem de
        aparecer.
        """

    @abstractmethod
    def wait_present(self, seletor: str) -> None:
        """Bloqueia até o elemento existir no DOM -- sem exigir que esteja
        visível ou clicável. Levanta `TempoEsgotado` no timeout."""

    @abstractmethod
    def clear(self, seletor: str) -> None:
        """Esvazia o campo localizado por `seletor`, sem digitar nada."""

    @abstractmethod
    def type_text(self, seletor: str, texto: str) -> None:
        """Digita `texto` NO FIM do conteúdo atual do campo (não limpa
        antes) -- diferente de `fill`, que limpa. Propaga falhas."""

    # =====================================================================
    # Primitivas acrescentadas pelo Checkpoint 5.3 (uploads)
    # =====================================================================
    # `upload_conditions` e `tech_specs` trouxeram três necessidades que as
    # primitivas anteriores não cobriam:
    #
    #   1. TABELA COM VÁRIAS LINHAS. `tech_specs` coletava `find_elements(...)`
    #      e depois fazia `linha.find_element(".//input")` -- busca RELATIVA a
    #      um elemento. O contrato aqui é todo por seletor, e continua sendo:
    #      a mesma intenção vira `contar(xpath_das_linhas)` + um XPath composto
    #      com índice, `(//linhas)[3]//input`. Mesmo XPath do pai, mesmo XPath
    #      relativo, só concatenados -- não é troca de estratégia de seletor
    #      (que o plano só autoriza depois do módulo estável no motor novo).
    #      É também o que evita introduzir um objeto de elemento no contrato,
    #      que vazaria o motor de volta para os serviços.
    #
    #   2. CAMPO QUE REJEITA A DIGITAÇÃO. `_preencher_input_com_auditoria`
    #      escrevia, relia, e quando o site zerava o valor, forçava via JS
    #      (`arguments[0].value = ...` + 3 `dispatchEvent`). `forcar_valor` é
    #      essa intenção; cada motor a cumpre do seu jeito -- é literalmente o
    #      que o CP 5.3 pede ("em Playwright usar `fill` + verificação de
    #      valor").
    #
    #   3. `<select>`. Vinha do `Select` do Selenium. As três primitivas de
    #      opção expõem só a MECÂNICA; a regra de casamento (texto exato,
    #      depois substring normalizada, e o `(SÍMBOLO)` das unidades) fica no
    #      serviço, que é onde ela é regra de negócio.

    @abstractmethod
    def contar(self, seletor: str) -> int:
        """Quantos elementos casam com `seletor` AGORA (sem esperar)."""

    @abstractmethod
    def esta_visivel(self, seletor: str) -> bool:
        """O elemento está visível na tela agora? Checagem imediata."""

    @abstractmethod
    def esta_habilitado(self, seletor: str) -> bool:
        """O elemento está habilitado agora? Checagem imediata."""

    @abstractmethod
    def esta_marcado(self, seletor: str) -> bool:
        """O checkbox/radio está marcado agora? Checagem imediata."""

    @abstractmethod
    def forcar_valor(self, seletor: str, texto: str) -> None:
        """Escreve `texto` no campo CONTORNANDO a digitação normal, para o
        caso em que o site rejeita/zera o valor digitado.

        Disparar os eventos de `input`/`change`/`blur` faz parte do
        contrato: sem eles o framework da página não percebe a mudança e o
        valor some no próximo redesenho."""

    @abstractmethod
    def passar_o_mouse(self, seletor: str) -> None:
        """Leva o ponteiro para cima do elemento, sem clicar.

        Existe por causa do TOOLTIP do portal (`osui-tooltip--is-hover`): o
        balão que guarda o texto em espanhol das Condições não está no DOM
        até alguém apontar para o gatilho. Ler o `aria-describedby` e
        procurar o id devolve vazio enquanto ninguém passou o mouse.

        É a única forma de LER um dado que a tela só entrega na interação --
        não é conveniência de navegação.
        """

    @abstractmethod
    def focar(self, seletor: str) -> None:
        """Põe o foco no elemento SEM clicar nele.

        Sem clique de propósito: em `upload_conditions`, o alvo é um checkbox
        que já está no estado certo -- clicar o desmarcaria. O original
        conseguia o mesmo mandando a tecla direto ao elemento; aqui o foco é
        explícito, e o `press` seguinte continua indo para quem tem o foco.
        """

    @abstractmethod
    def digitar_no_foco(self, texto: str) -> None:
        """Digita `texto` no elemento que estiver com foco -- sem seletor,
        mesmo espírito de `press`.

        `upload_conditions` navega por TAB entre campos que não têm seletor
        estável ("o campo DEPOIS do checkbox de climatização"), então digitar
        no foco é a única forma de reproduzir o fluxo sem inventar seletores
        que ninguém validou.
        """

    @abstractmethod
    def atributo(self, seletor: str, nome: str) -> str:
        """Lê um atributo HTML qualquer do elemento (ex.: `data-tooltip`).

        `get_value` cobre só o `value` de campo e `texto` só o conteúdo;
        `cria_fichas` precisa do `data-tooltip` de uma div para capturar o
        "PDM Final" depois de salvar a ficha. Devolve `""` quando o atributo
        não existe, para o chamador não ter de tratar `None`.
        """

    @abstractmethod
    def texto(self, seletor: str) -> str:
        """Texto do elemento (o `textContent` do DOM), não o `value` de um
        campo -- é `get_value` quem lê campo de formulário.

        `textContent` e não o "texto visível": é o que
        `tech_specs.processar_lista` já lia para descobrir o nome da
        característica na linha da tabela, e ele traz também o que está
        oculto por CSS. Trocar por texto visível mudaria silenciosamente
        quais linhas casam com o JSON da IA.
        """

    @abstractmethod
    def opcoes(self, seletor: str) -> list[str]:
        """Textos visíveis das opções do `<select>` em `seletor`, na ordem."""

    @abstractmethod
    def texto_selecionado(self, seletor: str) -> str:
        """Texto visível da opção ESCOLHIDA no `<select>` em `seletor`.
        `""` quando não há seleção ou o elemento não é um select.

        O par que faltava de `opcoes()` / `selecionar_por_texto()`:
        `opcoes()` diz quais existem, este diz qual está escolhida. E o
        TEXTO, não o `value` -- `get_value()` devolve o atributo `value` do
        `<option>`, enquanto `selecionar_por_texto()` casa por LABEL. Sem
        esta primitiva não dava para LER uma seleção e repô-la depois.

        Nasceu do módulo de correção de PDM (2026-09-23): a unidade de medida
        existe em TODA linha de característica, e as do tipo `LISTA` são um
        `<select>` inteiro. As duas seriam impossíveis de restaurar lendo só
        o `value`.
        """

    @abstractmethod
    def selecionar_por_texto(self, seletor: str, texto: str) -> None:
        """Seleciona a opção cujo texto visível é EXATAMENTE `texto`.
        Levanta se não houver."""

    @abstractmethod
    def selecionar_por_indice(self, seletor: str, indice: int) -> None:
        """Seleciona a opção na posição `indice` (base 0) -- o par de
        `opcoes()`, para quando o casamento é por regra do serviço."""

    @abstractmethod
    def current_url(self) -> str:
        """URL da página aberta agora."""

    @abstractmethod
    def fechar(self) -> None:
        """Encerra o browser e libera os recursos do motor. Idempotente:
        chamar duas vezes não levanta."""

    # =====================================================================
    # Leitura das respostas que a página recebe (2026-10-14)
    # =====================================================================
    # NÃO é abstrato, de propósito: os dublês dos testes e um motor futuro
    # continuam válidos sem implementá-lo, e quem usa decide pelo
    # `captura_respostas_disponivel` -- sem ele, o fluxo de antes (ler a tela).
    #
    # Continua sendo RPA. O motor não faz requisição nenhuma: o robô clica ou
    # navega como uma pessoa, e isto só lê o que o navegador recebeu por causa
    # disso. Regra do Luan (2026-10-14): a Itaipu proíbe contato com o banco de
    # dados dela, e o SIG-FT não chama o servidor por fora da tela. Ver
    # docs/PMIB_ENGENHARIA_REVERSA.md, R1.
    captura_respostas_disponivel = False

    def capturar_respostas(self, trecho_url: str, acao, *, quantas: int = 1,
                           ate=None, timeout_s: float = 20.0) -> list:
        """Executa `acao()` e devolve o JSON das respostas que a página recebeu
        de endereços que contêm `trecho_url`, na ordem de chegada.

        Para ao juntar `quantas` respostas, assim que `ate(json)` aceitar uma
        delas, ou ao fim de `timeout_s` -- e então devolve o que chegou, que
        pode ser lista vazia. Resposta sem JSON conta para `quantas`, mas não
        volta. Não levanta por falta de resposta: quem chama decide o que isso
        significa."""
        raise NotImplementedError("este motor não lê as respostas que a página recebe")
