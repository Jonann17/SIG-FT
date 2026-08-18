r"""
sigft/core/rpa/playwright_engine.py — implementação Playwright de `RPAEngine`
(Checkpoint 5.1 do plano de refatoração).

Ver docs/refatoracao/PLANO_REFATORACAO.md, decisão de produto nº 5 e Fase 5:
"implementar `playwright_engine.py` com a MESMA interface do engine; migrar
módulo a módulo com validação assistida pelo usuário contra o portal real";
CP 5.1: "engine com contexto persistente e modo headed".

Este arquivo NÃO conhece o portal PMIB nem nenhum serviço: é só o motor. Quem
sabe qual motor usar é `factory.py` (mapa `config.RPA_ENGINE`), e quem sabe
falar com o portal é `portal.py`. Nenhum dos dois muda quando este arquivo
muda.

--------------------------------------------------------------------------
Por que Playwright (o problema que ele resolve)
--------------------------------------------------------------------------
Diagnóstico do plano, seção 1.5: "`time.sleep()` fixo como sincronização
primária do RPA (dezenas de ocorrências, 0.2s a 6s) — lento no caso bom,
frágil no caso ruim. Playwright resolve isso nativamente (auto-wait)."

Toda ação de Playwright já espera, sozinha, o elemento existir, ficar visível,
estável e habilitado antes de agir. Por isso os métodos abaixo NÃO repetem os
`wait.until(...)` que a versão Selenium precisa: eles seriam redundantes. Os
`time.sleep` que restam são os do CONSUMIDOR (portal/serviço), que este
checkpoint não mexe — tirá-los é ganho para os checkpoints seguintes, com o
portal real na frente para validar.

--------------------------------------------------------------------------
Contexto persistente (o ganho de UX que o CP 5.1 pede)
--------------------------------------------------------------------------
`launch_persistent_context` guarda cookies e sessão num diretório de perfil no
disco. Consequência prática no PMIB: o login manual feito numa execução
continua valendo na próxima, em vez de a cada rodada abrir um Chrome zerado e
exigir login de novo. `aguardar_login_manual` (em `PMIBPortal`) segue existindo
e com o MESMO fluxo de hoje — a janela da UI é que libera o robô; o que muda é
que, com sessão persistida, na maioria das vezes o usuário só clica OK.

O perfil fica FORA do repositório, em `%LOCALAPPDATA%\SIG-FT\perfil-navegador`
(ou `~/.local/share/SIG-FT/...` fora do Windows): é estado por máquina/usuário,
com cookies de sessão do portal dentro — a mesma razão pela qual
`api_config.json` e `user_prefs.json` não são versionados.

--------------------------------------------------------------------------
Import preguiçoso
--------------------------------------------------------------------------
`playwright.sync_api` só é importado DENTRO de `criar()` (mesma convenção de
`core/llm/providers/gemini.py` para `google.generativeai`). Assim este módulo
é importável — e testável — sem Playwright instalado e sem browser nenhum, o
que importa porque durante toda a Fase 5 o motor padrão continua sendo o
Selenium: quem só roda o app não deve ser obrigado a baixar um Chromium de
~150 MB por causa de um import de topo.

O `driver`/`wait` do Selenium NÃO têm equivalente aqui, e é de propósito: um
consumidor que ainda alcance `engine.driver` não roda neste motor. Isso é o
detector de migração incompleta — `AttributeError` alto e claro, em vez de
comportamento sutilmente errado.
"""

from __future__ import annotations

import os
import sys

from sigft.core.rpa.engine import (
    ElementoObsoleto,  # noqa: F401 -- reexportado por simetria com selenium_engine
    RPAEngine,
    TempoEsgotado,
)

# Playwright aceita XPath, mas só reconhece a string como XPath quando ela vem
# prefixada por `xpath=` ou começa com `/`/`(`. Todos os seletores do projeto
# são XPath puro (levantamento do CP 2.1: 139 de 140), e vários começam com
# `//*[@id=...]`, que o Playwright já entende. O prefixo explícito elimina a
# dúvida para os que não começam com `/` -- ex.: `(//button)[1]`.
_PREFIXO_XPATH = "xpath="

# Escape hatch para rede que bloqueia o download do Chromium -- ver `criar()`.
_ENV_EXECUTAVEL = "SIGFT_PLAYWRIGHT_EXECUTABLE"


def _sel(seletor: str) -> str:
    """Normaliza um seletor XPath do projeto para a sintaxe do Playwright."""
    if seletor.startswith(_PREFIXO_XPATH):
        return seletor
    return _PREFIXO_XPATH + seletor


def perfil_padrao() -> str:
    """Diretório do perfil persistente do navegador -- ver docstring do
    módulo (por que fora do repositório)."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share"
        )
    return os.path.join(base, "SIG-FT", "perfil-navegador")


# Quanto se espera pelo clique de MOUSE REAL antes de cair no clique por DOM
# (`click_dom`). Não é o timeout do elemento EXISTIR -- esse continua sendo o
# `timeout_ms` cheio; é só quanto se insiste no clique real depois que o alvo
# já está no DOM.
#
# O número importa porque a falha aqui é cara e silenciosa: `click` engole a
# exceção por contrato, então cada radio inalcançável de `upload_conditions`
# custava os 20 s inteiros e não deixava rastro -- uma ficha com 19 controles
# gastava minutos para terminar vazia. 3 s é folgado para um clique que vai
# dar certo (o Playwright reavalia a acionabilidade em laço) e barato para um
# que não vai.
TIMEOUT_CLIQUE_REAL_MS = 3_000

# O clique nativo do elemento. Contrapartida exata do
# `arguments[0].click()` do motor Selenium.
_JS_CLICK = "el => el.click()"


class PlaywrightEngine(RPAEngine):
    """Implementação de `RPAEngine` sobre Playwright (motor-alvo da Fase 5).

    Construída por `criar()`, não diretamente: é `criar()` que sobe o
    Playwright, o contexto persistente e a página. O `__init__` só recebe
    objetos já prontos, o que mantém a classe testável com fakes -- mesmo
    padrão de `SeleniumEngine(driver, wait)`.
    """

    def __init__(self, page, *, context=None, playwright=None, timeout_ms: int = 20_000) -> None:
        self.page = page
        self.context = context
        self._playwright = playwright
        self.timeout_ms = timeout_ms
        self._download_dir: str | None = None

    # =====================================================================
    # Construção
    # =====================================================================
    @classmethod
    def criar(
        cls,
        *,
        wait_timeout: int = 20,
        download_dir: str | None = None,
        perfil: str | None = None,
        headless: bool = False,
        executable_path: str | None = None,
    ) -> "PlaywrightEngine":
        """Sobe um Chromium com contexto persistente e devolve o engine.

        `wait_timeout` chega em SEGUNDOS (mesma unidade de
        `create_chrome_driver`, para os call sites poderem trocar de motor
        sem converter nada) e vira o timeout padrão de toda ação/espera do
        Playwright, em milissegundos.

        `headless=False` é o default por decisão do CP 5.1 ("modo headed"):
        o fluxo do PMIB tem login manual e validação visual pelo usuário --
        um robô invisível aqui atrapalharia em vez de ajudar.

        `executable_path` (ou a variável de ambiente
        `SIGFT_PLAYWRIGHT_EXECUTABLE`) aponta um navegador JÁ INSTALADO em vez
        do que o `playwright install` baixaria. Existe para o caso corporativo
        real: rede que bloqueia o download do Chromium (o processo Node do
        Playwright não respeita as variáveis de certificado do Python -- ver
        README, "Rede corporativa"), mas onde a TI já mantém um Chrome/Edge na
        máquina. Sem essa saída, um Zscaler mais rígido simplesmente impede
        usar o motor novo.
        """
        from playwright.sync_api import sync_playwright  # import preguiçoso -- ver docstring

        binario = executable_path or os.environ.get(_ENV_EXECUTAVEL) or None

        playwright = sync_playwright().start()
        try:
            context = playwright.chromium.launch_persistent_context(
                perfil or perfil_padrao(),
                headless=headless,
                accept_downloads=True,
                no_viewport=True,  # equivalente ao `.maximize_window()` do Selenium
                **({"executable_path": binario} if binario else {}),
            )
        except BaseException:
            # Sem isto, uma falha ao subir o browser (Chromium não instalado,
            # perfil travado por outra instância) deixaria o processo-nó do
            # Playwright rodando órfão até o app fechar.
            playwright.stop()
            raise

        context.set_default_timeout(wait_timeout * 1000)
        page = context.pages[0] if context.pages else context.new_page()

        engine = cls(page, context=context, playwright=playwright, timeout_ms=wait_timeout * 1000)
        if download_dir:
            engine.set_download_dir(download_dir)
        return engine

    # =====================================================================
    # Tradução de exceção
    # =====================================================================
    # Mesmo papel do `_traduzir`/`_traduzindo` de `selenium_engine.py`, e pelo
    # mesmo motivo: o consumidor decide o fluxo pelo TIPO da falha. Aqui a
    # tabela tem uma linha só -- `ElementoObsoleto` não existe em Playwright,
    # que reavalia o seletor a cada ação em vez de guardar uma referência que
    # envelhece (ver `engine.py`).
    def _traduzir(self, excecao: BaseException) -> BaseException:
        for classe in type(excecao).__mro__:
            # `playwright.sync_api.TimeoutError` -- casado por NOME para não
            # obrigar um import de topo do SDK (ver docstring do módulo).
            if classe.__name__ in ("TimeoutError", "PlaywrightTimeoutError"):
                return TempoEsgotado(str(excecao) or "tempo esgotado")
        return excecao

    def _executar(self, funcao):
        try:
            return funcao()
        except BaseException as excecao:
            traduzida = self._traduzir(excecao)
            if traduzida is excecao:
                raise
            raise traduzida from excecao

    def _loc(self, seletor: str):
        """Primeiro elemento que casa com `seletor`.

        O `.first` é deliberado: `wait.until(EC.presence_of_element_located)`
        do Selenium devolve o PRIMEIRO casamento, enquanto um `Locator` do
        Playwright que case com vários elementos levanta "strict mode
        violation" na hora de agir. Sem `.first`, seletores hoje ambíguos --
        e o diagnóstico do plano registra que existem, ex.:
        "`RadioButton1-input` aparece em mais de uma aba" -- passariam a
        estourar onde antes funcionavam. Manter a semântica de "o primeiro"
        é o que torna a troca de motor uma troca, e não uma reescrita de
        seletores.
        """
        return self.page.locator(_sel(seletor)).first

    # =====================================================================
    # Navegação
    # =====================================================================
    def goto(self, url: str) -> None:
        self._executar(lambda: self.page.goto(url))

    def current_url(self) -> str:
        return self.page.url

    # =====================================================================
    # Interação
    # =====================================================================
    def click(self, seletor: str) -> None:
        """Contrapartida do `safe_click`: ENGOLE a falha, como a versão
        Selenium (ver `engine.py`)."""
        try:
            self.click_estrito(seletor)
        except Exception:
            pass

    def click_estrito(self, seletor: str) -> None:
        """Clica propagando a falha -- tentando primeiro como um usuário
        clicaria e recuando para o clique por DOM quando o alvo não é
        acionável.

        **A ordem é deliberada e não é "tentar de novo até dar certo".** O
        clique real é melhor quando funciona: ele roda a checagem de hit
        target, que denuncia seletor errado e elemento coberto por modal --
        coisas que o clique por DOM esconde ao "funcionar" no lugar errado.
        Por isso ele vem primeiro, e o recuo só acontece quando ele falha.

        O recuo restaura a equivalência com o motor Selenium, onde
        `click_estrito` SEMPRE foi um `execute_script("arguments[0].click()")`
        -- ou seja, sempre teve o comportamento do recuo, e nunca o da
        checagem. Sem ele, os controles customizados do OutSystems (o
        `<input>` coberto pelo `<label>` estilizado) ficavam inalcançáveis no
        motor novo. Ver `engine.click_dom` para o diagnóstico completo.

        A espera pelo elemento EXISTIR continua com o timeout cheio; o que
        encurta é só a insistência no clique real (`TIMEOUT_CLIQUE_REAL_MS`).
        """
        def _acao():
            alvo = self._loc(seletor)
            # Presença com o timeout cheio -- equivale ao
            # `presence_of_element_located` que a versão Selenium espera antes
            # de qualquer coisa. Um elemento que nunca aparece tem de estourar
            # aqui, como TempoEsgotado, e NÃO virar um clique por DOM em nada.
            alvo.wait_for(state="attached", timeout=self.timeout_ms)
            try:
                alvo.scroll_into_view_if_needed(timeout=TIMEOUT_CLIQUE_REAL_MS)
            except Exception:  # noqa: BLE001
                # Rolar é conveniência; um alvo que não rola (escondido, dentro
                # de container com overflow travado) ainda pode ser clicado
                # pelo DOM. Falhar aqui seria desistir antes da tentativa.
                pass
            try:
                alvo.click(timeout=TIMEOUT_CLIQUE_REAL_MS)
            except Exception:  # noqa: BLE001 -- qualquer não-acionabilidade
                alvo.evaluate(_JS_CLICK)

        self._executar(_acao)

    def click_dom(self, seletor: str) -> None:
        """Clique por DOM, sem checagem de acionabilidade -- ver `engine.py`.

        `evaluate("el => el.click()")` chama o `HTMLElement.click()` nativo,
        que é exatamente o que `execute_script("arguments[0].click()")` faz no
        Selenium: dispara o evento E executa o comportamento padrão do
        elemento (marcar o checkbox, alternar o radio, emitir `change`).

        Não é `dispatch_event("click")`: aquele monta um `MouseEvent`
        sintético e NÃO executa o comportamento padrão -- um checkbox
        receberia o evento sem mudar de estado, que é a pior falha possível
        aqui (parece que funcionou).
        """
        def _acao():
            alvo = self._loc(seletor)
            alvo.wait_for(state="attached", timeout=self.timeout_ms)
            alvo.evaluate(_JS_CLICK)

        self._executar(_acao)

    def scroll_to(self, seletor: str) -> None:
        self._executar(lambda: self._loc(seletor).scroll_into_view_if_needed())

    def click_raw(self, seletor: str) -> None:
        """Em Playwright não existe "clicar sem esperar": `Locator.click`
        sempre confere a acionabilidade do alvo antes. O que este método
        entrega é a outra metade do contrato -- não rolar a tela por conta
        própria (`scroll_to` é chamado à parte pelo consumidor) -- e essa
        espera embutida a mais é justamente o auto-wait que motiva a Fase 5;
        ela substitui os `time.sleep` fixos, não os acumula."""
        self._executar(lambda: self._loc(seletor).click())

    def click_nativo(self, seletor: str) -> None:
        """Em Playwright, `Locator.click()` JÁ é um clique de mouse real
        (o Playwright injeta o evento pelo CDP, não por `element.click()`),
        e portanto já leva o foco para o alvo -- que é exatamente o que o
        contrato pede aqui. A espera de acionabilidade também é embutida,
        cobrindo o `element_to_be_clickable` do lado Selenium.

        Ou seja: neste motor `click_nativo` e `click_raw` fazem a mesma
        coisa. A duplicação é deliberada -- é no Selenium que os dois
        divergem, e o consumidor precisa poder declarar qual dos dois
        comportamentos ele depende, sem saber qual motor está montado."""
        self._executar(lambda: self._loc(seletor).click())

    def fill(self, seletor: str, texto: str) -> None:
        """Limpa e preenche -- equivalente ao Ctrl+A/Backspace/digitar da
        versão Selenium, que aqui é o próprio `Locator.fill`. Engole a falha,
        igual à versão Selenium."""
        try:
            self.fill_estrito(seletor, texto)
        except Exception:
            pass

    def fill_estrito(self, seletor: str, texto: str) -> None:
        """`fill` sem engolir a falha -- ver `engine.py` para por que as duas
        variantes precisam coexistir."""
        self._executar(lambda: self._loc(seletor).fill(str(texto)))

    def clear(self, seletor: str) -> None:
        self._executar(lambda: self._loc(seletor).fill(""))

    def type_text(self, seletor: str, texto: str) -> None:
        """Digita no fim do conteúdo atual, sem limpar (ver `engine.py`).

        `press_sequentially` emite os eventos de teclado tecla a tecla, que é
        o que o `send_keys` do Selenium faz -- e o que os campos do
        OutSystems no PMIB precisam para disparar a busca/autocomplete. Um
        `fill` aqui seria um atalho que troca o comportamento.

        Não há `click()` antes: `press_sequentially` já foca o elemento por
        conta própria, então clicar seria uma interação A MAIS que o motor
        Selenium não faz -- e num portal cheio de dropdown, um clique extra
        não é neutro. É também o que deixa o `press("ENTER")` seguinte
        chegar no campo certo nos dois motores, pelo mesmo caminho: quem
        digitou por último está com o foco.
        """
        self._executar(lambda: self._loc(seletor).press_sequentially(str(texto)))

    def press(self, teclas: str | list[str]) -> None:
        """Envia tecla(s) ao elemento com foco -- sem seletor, igual ao
        contrato de `engine.py`.

        Os nomes vêm no formato do Selenium (`"ENTER"`, `"TAB"`), que é o que
        os serviços já escrevem hoje; `_TECLAS` traduz para o formato do
        Playwright (`"Enter"`, `"Tab"`).
        """
        sequencia = [teclas] if isinstance(teclas, str) else list(teclas)
        for tecla in sequencia:
            self._executar(lambda t=tecla: self.page.keyboard.press(_TECLAS.get(t, t)))

    # =====================================================================
    # Espera
    # =====================================================================
    # Playwright já espera sozinho antes de cada ação (ver docstring do
    # módulo), então estes métodos existem para os consumidores que esperam
    # DE PROPÓSITO -- tipicamente para decidir fluxo pelo estouro do tempo
    # (`except TempoEsgotado` = "acabou o lote"), não para sincronizar.
    def wait_visible(self, seletor: str) -> None:
        self._executar(lambda: self._loc(seletor).wait_for(state="visible"))

    def wait_present(self, seletor: str) -> None:
        self._executar(lambda: self._loc(seletor).wait_for(state="attached"))

    def wait_clickable(self, seletor: str) -> None:
        """"Clicável" = visível E habilitado.

        Playwright não tem um `state="clickable"`: o `wait_for` cobre a
        visibilidade, e a parte "habilitado" (o que o
        `EC.element_to_be_clickable` do Selenium acrescenta) é checada por
        `is_enabled` em laço até o timeout. Sem essa segunda metade, um botão
        visível porém desabilitado passaria por clicável -- e o laço de
        exclusão de `apagar_lmr`, que usa o estouro do tempo como sinal de
        "acabou", pararia cedo demais.
        """
        import time as _time

        def _acao():
            alvo = self._loc(seletor)
            alvo.wait_for(state="visible")
            limite = _time.monotonic() + self.timeout_ms / 1000
            while not alvo.is_enabled():
                if _time.monotonic() >= limite:
                    raise TempoEsgotado(f"elemento visível mas nunca habilitado: {seletor}")
                _time.sleep(0.1)

        self._executar(_acao)

    # =====================================================================
    # Leitura
    # =====================================================================
    def element_exists(self, seletor: str) -> bool:
        """Checagem IMEDIATA, sem esperar -- `count()` não bloqueia, ao
        contrário de quase todo o resto da API do Playwright."""
        return self.page.locator(_sel(seletor)).count() > 0

    def get_value(self, seletor: str) -> str:
        return self._executar(lambda: self._loc(seletor).input_value())

    # =====================================================================
    # Primitivas do CP 5.3 -- ver `engine.py` para o racional de cada uma
    # =====================================================================
    def contar(self, seletor: str) -> int:
        return self.page.locator(_sel(seletor)).count()

    def esta_visivel(self, seletor: str) -> bool:
        # `is_visible()` não espera -- é a checagem imediata que o contrato
        # pede, ao contrário de `wait_for(state="visible")`.
        return self.contar(seletor) > 0 and self._loc(seletor).is_visible()

    def esta_habilitado(self, seletor: str) -> bool:
        return self.contar(seletor) > 0 and self._loc(seletor).is_enabled()

    def esta_marcado(self, seletor: str) -> bool:
        return self.contar(seletor) > 0 and self._loc(seletor).is_checked()

    def forcar_valor(self, seletor: str, texto: str) -> None:
        """Aqui é só `fill` -- exatamente o que o CP 5.3 pede ("em Playwright
        usar `fill` + verificação de valor").

        `Locator.fill` já dispara os eventos de `input`/`change` que a versão
        Selenium precisa emitir à mão, então não há injeção de JavaScript
        nenhuma neste motor. A "verificação de valor" continua no serviço,
        que relê com `get_value` -- é ele quem sabe o que fazer quando o site
        recusa duas vezes.
        """
        self._executar(lambda: self._loc(seletor).fill(str(texto)))

    def focar(self, seletor: str) -> None:
        self._executar(lambda: self._loc(seletor).focus())

    def digitar_no_foco(self, texto: str) -> None:
        """`keyboard.type` digita no que estiver com foco, tecla a tecla --
        o par de `press`, e o equivalente do `active_element.send_keys` da
        versão Selenium."""
        self._executar(lambda: self.page.keyboard.type(str(texto)))

    def atributo(self, seletor: str, nome: str) -> str:
        return self._executar(lambda: self._loc(seletor).get_attribute(nome) or "")

    def texto(self, seletor: str) -> str:
        """`text_content()` é o `textContent` do DOM -- inclui o que está
        oculto por CSS, ao contrário de `inner_text()`. É o que a versão
        Selenium lê, e o contrato exige a mesma coisa."""
        return self._executar(lambda: self._loc(seletor).text_content() or "")

    def opcoes(self, seletor: str) -> list[str]:
        return self._executar(
            lambda: [
                (texto or "").strip()
                for texto in self._loc(seletor).locator("option").all_text_contents()
            ]
        )

    def selecionar_por_texto(self, seletor: str, texto: str) -> None:
        self._executar(lambda: self._loc(seletor).select_option(label=texto))

    def selecionar_por_indice(self, seletor: str, indice: int) -> None:
        self._executar(lambda: self._loc(seletor).select_option(index=indice))

    # =====================================================================
    # Diagnóstico / configuração
    # =====================================================================
    def screenshot(self, caminho: str) -> None:
        self._executar(lambda: self.page.screenshot(path=caminho))

    def set_download_dir(self, caminho: str) -> None:
        """Redireciona downloads da sessão já aberta para `caminho`.

        Playwright não expõe o `Page.setDownloadBehavior` do CDP que a versão
        Selenium usa: aqui todo download vira um evento `download`, e é o
        código que decide onde salvar. O handler abaixo faz esse papel, com o
        mesmo efeito observável (o arquivo aparece na pasta pedida, sem
        diálogo). Chamar de novo troca a pasta -- o handler lê
        `self._download_dir` na hora do evento, e não uma cópia do valor.
        """
        primeira_vez = self._download_dir is None
        self._download_dir = caminho
        os.makedirs(caminho, exist_ok=True)
        if primeira_vez:
            self.page.on("download", self._salvar_download)

    def _salvar_download(self, download) -> None:
        destino = self._download_dir
        if not destino:
            return
        try:
            download.save_as(os.path.join(destino, download.suggested_filename))
        except Exception:
            # Diagnóstico nunca derruba produção: uma falha ao salvar não pode
            # abortar a automação que estava em curso.
            pass

    # =====================================================================
    # Encerramento
    # =====================================================================
    def fechar(self) -> None:
        """Fecha contexto e para o Playwright. Idempotente (contrato de
        `engine.py`) e tolerante a falha em cada etapa: o browser pode já ter
        sido fechado pelo usuário, e isso não é motivo para estourar no
        `finally` de quem chamou."""
        for encerrar in (
            getattr(self.context, "close", None),
            getattr(self._playwright, "stop", None),
        ):
            if encerrar is None:
                continue
            try:
                encerrar()
            except Exception:
                pass
        self.context = None
        self._playwright = None
        self.page = None


# Nome de tecla no formato Selenium -> formato Playwright. Só as teclas que os
# serviços realmente usam hoje (levantamento por grep de `Keys.` no
# repositório); um nome fora da tabela é repassado como veio, que é o que faz
# `press("Enter")` (grafia do Playwright) também funcionar.
_TECLAS = {
    "ENTER": "Enter",
    "RETURN": "Enter",
    "TAB": "Tab",
    "ESCAPE": "Escape",
    "BACKSPACE": "Backspace",
    "DELETE": "Delete",
    "SPACE": " ",
    "ARROW_DOWN": "ArrowDown",
    "ARROW_UP": "ArrowUp",
    "ARROW_LEFT": "ArrowLeft",
    "ARROW_RIGHT": "ArrowRight",
    "HOME": "Home",
    "END": "End",
    "PAGE_DOWN": "PageDown",
    "PAGE_UP": "PageUp",
}
