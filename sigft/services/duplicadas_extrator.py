r"""
Ficha duplicada — leitura da ficha ORIGINAL no portal (CP 6.2, segunda metade).

Duas responsabilidades, e só estas:

  1. **achar e abrir** a ficha original, que pode estar em qualquer uma das 7
     abas de status da lista;
  2. **ler** o que está na tela, em MODO DE VISUALIZAÇÃO, como pares
     rótulo→valor.

O que este módulo deliberadamente NÃO faz: escrever na ficha alvo (é o CP 6.3)
e navegar entre as seções internas da ficha (ver "o que falta", no fim).

Por que visualização e não edição — a decisão está em `duplicadas_spec.
MODO_LEITURA_ORIGINAL`, e o resumo é: a original pode estar em status que nem
abre para edição, e em visualização o portal renderiza os valores como TEXTO.
Um extrator escrito para `input[value]` não acha nada e devolve ficha vazia,
**sem erro nenhum** -- que é o pior modo de falhar que existe aqui.
"""
from __future__ import annotations

import time

from sigft.core.rpa import seletores_duplicada as sel
from sigft.services import duplicadas_spec as spec


def _log_de(callback_log):
    """Adaptador de log, igual ao de `duplicadas_injetor`/`duplicadas_robo`.

    O idioma antigo deste arquivo era um `def _log` embutido em cada função.
    As funções do CP 6.4 (abaixo) usam este helper -- mesma semântica, sem a
    repetição. As antigas ficaram como estavam: reescrevê-las seria mexer em
    código que roda, de carona.
    """
    def _log(mensagem):
        if callback_log:
            callback_log(mensagem)
    return _log


def _literal_xpath(texto):
    """`texto` como literal XPath, com aspas escolhidas para não colidir.

    Os nomes das abas vêm de constantes hoje, mas o dia em que um deles ganhar
    um apóstrofo o XPath quebraria de um jeito difícil de ler -- e escapar
    literal em XPath 1.0 não tem `\\'`, tem `concat`.
    """
    texto = str(texto)
    if "'" not in texto:
        return f"'{texto}'"
    if '"' not in texto:
        return f'"{texto}"'
    partes = "', \"'\", '".join(texto.split("'"))
    return f"concat('{partes}')"


# ===========================================================================
# 1. Achar a ficha original entre as abas de status
# ===========================================================================
# "A ficha original é sempre encontrável, mas pode variar dentro do portal se
# ela está em Elaboração, ou se está em Análise, ou demais campos."
#
# Isto NÃO é uma reimplementação de `portal.pesquisar_e_abrir`: aquilo responde
# "abra a ficha X" assumindo que ela está na lista visível, com 3 tentativas e
# sleeps próprios. Aqui a pergunta é outra -- "em QUAL aba ela está?" -- e
# rodar o `pesquisar_e_abrir` sete vezes multiplicaria por sete os sleeps dele
# para responder uma pergunta que uma checagem de existência resolve.

PAUSA_APOS_BUSCA = 2.5  # segundos; o filtro da lista é assíncrono


# Espera pela LINHA depois do ENTER da busca. TENTATIVAS x INTERVALO, e não um
# teto de relógio: com `time.sleep` anulado (o que os testes fazem, e devem
# fazer) um teto de relógio vira laço em vazio girando os 10 s inteiros. Assim
# o teste termina na hora e a produção espera o mesmo tanto.
TENTATIVAS_DA_LINHA = 20
INTERVALO_DA_LINHA = 0.5


def _buscar_na_aba_atual(portal, pmib):
    """Digita `pmib` no filtro da lista e espera a LINHA aparecer.

    ⚠️ Aqui havia `time.sleep(PAUSA_APOS_BUSCA)` e nada mais -- 2,5 s fixos,
    contra um servidor que às vezes leva mais. Quando levava, a linha ainda
    não estava no DOM, `localizar_aba_da_ficha` concluía "não está nesta aba"
    e seguia para a próxima. Com sete abas, o resultado era
    `não achei a ficha original em nenhuma aba` -- uma ficha que está lá, e
    que a mesma função acha na tentativa seguinte. Medido em 2026-08-25: a
    rodada do robô falhou nas sete abas e uma busca manual, com espera maior,
    achou na primeira.

    A cura não é um sleep maior (que só desloca o limite e cobra o tempo de
    toda ficha que o portal responde rápido): é esperar a CONDIÇÃO. Quem não
    tem a ficha sai pelo teto, e aí "não está nesta aba" é verdade.
    """
    portal.safe_fill(sel.XPATH_BUSCA_DA_LISTA, pmib)
    portal.engine.press("ENTER")
    time.sleep(PAUSA_APOS_BUSCA)

    linha = sel.XPATH_LINHA_ACAO_VISUALIZAR.format(pmib=pmib)
    for _ in range(TENTATIVAS_DA_LINHA):
        try:
            if portal.engine.element_exists(linha):
                return True
        except Exception:  # noqa: BLE001 -- tabela remontando; tentar de novo
            pass
        time.sleep(INTERVALO_DA_LINHA)
    return False


# Espera pela LISTA montar. Ver `esperar_abas_da_lista`.
ESPERA_DAS_ABAS = 10.0      # segundos, teto
INTERVALO_DAS_ABAS = 0.25


def esperar_abas_da_lista(portal, espera=ESPERA_DAS_ABAS):
    """Espera ALGUMA aba de status aparecer. `True` se apareceu.

    ⚠️ ISTO CONSERTA O DEFEITO DE 2026-08-21, 16:16, e ele é sutil.

    `localizar_aba_da_ficha` pula em silêncio a aba que não está na tela --
    de propósito, porque o portal não mostra as sete para todo perfil. Só que
    `element_exists` é `count() > 0`, uma checagem IMEDIATA, e `ir_para_lista`
    só navega (e só espera) quando a URL é outra. Na PRIMEIRA ficha do lote a
    URL já era a da lista: ninguém esperou nada, e a tela ainda estava sendo
    montada pelo React.

    Resultado no log do usuário: `Abas tentadas:` com SEIS abas, faltando
    exatamente a primeira -- "Em Elaboração", onde a ficha seguinte do mesmo
    lote foi achada dois segundos depois. "A tela ainda não montou" tinha
    virado "esta aba não existe", e a ficha inteira se perdeu.

    A espera resolve na raiz: só depois que a lista existe é que "esta aba não
    está aqui" quer dizer alguma coisa.
    """
    tentativas = max(1, int(espera / INTERVALO_DAS_ABAS))
    for _ in range(tentativas):
        for nome in spec.ABAS_DE_STATUS_DA_LISTA:
            if portal.engine.element_exists(
                    sel.XPATH_ABA_STATUS.format(texto=_literal_xpath(nome))):
                return True
        time.sleep(INTERVALO_DAS_ABAS)
    return False


def localizar_aba_da_ficha(portal, pmib, callback_log=None):
    """Nome da aba de status onde `pmib` aparece, ou `None`.

    Varre as abas na ordem de `spec.ABAS_DE_STATUS_DA_LISTA`, que é a ordem da
    tela -- e não por acaso: "Em Elaboração" vem primeiro e é onde a maioria
    das originais está, então o caso comum custa uma aba, não sete.

    Aba que não existe na tela é PULADA em silêncio (o portal não mostra as 7
    para todo perfil); aba que existe e não tem a ficha é registrada no log,
    porque quando a busca falhar nas sete o usuário vai querer saber que todas
    foram mesmo tentadas.
    """
    def _log(mensagem):
        if callback_log:
            callback_log(mensagem)

    # A LISTA PRIMEIRO. Sem isto, "a tela ainda não montou" vira "esta aba não
    # existe" -- ver `esperar_abas_da_lista`.
    esperar_abas_da_lista(portal)

    alvo = sel.XPATH_LINHA_ACAO_VISUALIZAR.format(pmib=pmib)
    tentadas = []
    for nome in spec.ABAS_DE_STATUS_DA_LISTA:
        seletor_aba = sel.XPATH_ABA_STATUS.format(texto=_literal_xpath(nome))
        if not portal.engine.element_exists(seletor_aba):
            continue
        portal.engine.click_nativo(seletor_aba)
        _buscar_na_aba_atual(portal, pmib)
        tentadas.append(nome)
        if portal.engine.element_exists(alvo):
            _log(f"   Ficha {pmib} encontrada na aba '{nome}'.")
            return nome

    _log(f"   [Erro] Ficha {pmib} não encontrada. Abas tentadas: "
         f"{', '.join(tentadas) or '(nenhuma aba de status na tela)'}.")
    return None


def abrir_original_em_visualizacao(portal, pmib, callback_log=None):
    """Abre a ficha original em modo de LEITURA. `True` se conseguiu.

    Entra pelo ícone de folha (`-View`), nunca pelo lápis (`-Edit`): abrir para
    edição uma ficha que já foi enviada à ITAIPU é efeito colateral em ficha de
    terceiro, e a duplicação não precisa de nada além de ler.
    """
    def _log(mensagem):
        if callback_log:
            callback_log(mensagem)

    portal.ir_para_lista()
    if localizar_aba_da_ficha(portal, pmib, callback_log) is None:
        return False

    portal.engine.click_nativo(sel.XPATH_LINHA_ACAO_VISUALIZAR.format(pmib=pmib))
    if not esperar_a_ficha_abrir(portal):
        _log(f"   [Erro] Cliquei em visualizar a ficha {pmib} e a tela dela não "
             f"apareceu em {TENTATIVAS_DA_FICHA}s. Nada foi copiado desta ficha.")
        return False
    _log(f"   Ficha {pmib} aberta em modo de visualização.")
    return True


# Espera pela TELA da ficha depois do clique -- TENTATIVAS x INTERVALO, pelo
# mesmo motivo de `TENTATIVAS_DA_LINHA`.
TENTATIVAS_DA_FICHA = 45
INTERVALO_DA_FICHA = 1.0


def esperar_a_ficha_abrir(portal, espera=None):
    """A ficha abriu? Espera pela TELA, nunca pela URL.

    ⚠️ 2026-08-24, e custou três tentativas silenciosas antes de eu ver. O
    portal é uma SPA: o clique no ícone de visualizar abre a ficha e o
    endereço CONTINUA `PMIB_DatasheetList` por tempo indeterminado -- às vezes
    nunca muda. Quem espera `"PMIB_DataSheetView" in url` conclui "não abriu"
    com a ficha aberta na frente.

    O sinal é a aba «Condições» da própria ficha: ela não existe na lista e
    existe em toda ficha, nos dois modos (visualização e edição).

    Antes desta espera a função devolvia `True` no instante do clique. O que
    vinha depois -- abrir seção, varrer pares -- rodava contra a LISTA ainda na
    tela, falhava com "a aba 'Condições' não existe nesta tela", e o log
    culpava o portal por uma corrida do próprio robô.
    """
    alvo = sel.XPATH_ABA_DA_FICHA.format(texto=_literal_xpath(sel.ABA_CONDICOES))
    for _ in range(espera or TENTATIVAS_DA_FICHA):
        try:
            if portal.engine.contar(alvo):
                # O clique pegou; dar tempo do painel montar antes de varrer.
                time.sleep(PAUSA_APOS_ABRIR_FICHA)
                return True
        except Exception:  # noqa: BLE001 -- tela trocando; tentar de novo
            pass
        time.sleep(INTERVALO_DA_FICHA)
    return False


# Depois que a aba aparece, o painel ainda está montando. Sem esta pausa a
# primeira varredura pega a seção meio renderizada e devolve campo a menos --
# e campo a menos aqui vira campo vazio na ficha copiada, sem erro nenhum.
PAUSA_APOS_ABRIR_FICHA = 3.0


# ===========================================================================
# 2. Ler a tela
# ===========================================================================
# A estrutura do modo de visualização é uniforme (ver `seletores_duplicada`,
# §7): cada campo é um par rótulo→valor dentro de um `<fieldset>`. Por isso a
# leitura é uma VARREDURA, e não cinquenta seletores nomeados -- que
# envelheceriam todos juntos na próxima atualização do portal.

def _ancorar_no_bloco(base):
    """A varredura (relativa, com ramos em `.//`) ancorada num bloco.

    Cada ramo precisa do prefixo, não só o primeiro: em XPath, `A/.//x | .//y`
    é lido como duas expressões independentes, e a segunda varreria a PÁGINA
    INTEIRA. O sintoma seria campo de outro bloco aparecendo no meio deste --
    ficha plausível e errada, de novo.
    """
    ramos = sel.XPATH_VIEW_VARREDURA.split(" | ")
    return " | ".join(base + ramo.lstrip(".") for ramo in ramos)


def _texto_do_indice(engine, seletor_uniao, indice):
    return engine.texto(f"({seletor_uniao})[{indice}]")


def _e_valor(engine, seletor_uniao, indice):
    """O nó `indice` da varredura é um VALOR (e não um rótulo)?

    Uma pergunta por nó, e não uma por padrão de campo: os dois padrões da tela
    são estruturalmente opostos, mas `parear_rotulos_e_valores` só precisa do
    par ordenado -- ver `PREDICADO_VIEW_E_VALOR`.
    """
    return engine.element_exists(
        f"({seletor_uniao})[{indice}][{sel.PREDICADO_VIEW_E_VALOR}]"
    )


def ler_bloco(engine, indice_bloco):
    """(título, {rótulo: valor}) de um `<fieldset>` da tela, 1-indexado.

    O título vem da `<legend>`; os campos, da varredura em ordem de documento.
    Bloco sem `<legend>` devolve título vazio em vez de estourar: o portal tem
    blocos sem título, e derrubar a extração inteira por causa de um seria
    trocar uma ficha incompleta por nenhuma ficha.
    """
    base = f"({sel.XPATH_VIEW_BLOCO})[{indice_bloco}]"
    seletor_titulo = base + sel.XPATH_VIEW_TITULO_DO_BLOCO.lstrip(".")
    titulo = engine.texto(seletor_titulo) if engine.element_exists(seletor_titulo) else ""

    uniao = _ancorar_no_bloco(base)
    total = engine.contar(uniao)
    tokens = []
    onde_esta_o_rotulo = {}
    for indice in range(1, total + 1):
        texto = _texto_do_indice(engine, uniao, indice)
        tipo = "valor" if _e_valor(engine, uniao, indice) else "rotulo"
        tokens.append((tipo, texto))
        if tipo == "rotulo":
            limpo = " ".join(str(texto or "").split())
            if limpo:
                onde_esta_o_rotulo.setdefault(limpo, indice)

    titulo_limpo = " ".join(str(titulo or "").split())
    campos = spec.parear_rotulos_e_valores(tokens)
    campos = _resgatar_texto_ao_lado(engine, uniao, onde_esta_o_rotulo, campos)
    campos = _rotular_pela_legenda(titulo_limpo, tokens, campos)
    return titulo_limpo, campos


# A CAIXA de um rótulo do padrão B, quando ela é um invólucro SIMPLES.
#
# Os dois predicados negativos são o que impede o resgate de virar invenção:
# uma caixa que contenha `label[@data-label]` ou `Block_Expression` é um
# agrupamento de VÁRIOS campos, e o texto dela seria a colagem de todos --
# atribuir isso a um campo daria valor plausível e errado, que é o erro que
# este módulo mais teme.
_CAIXA_SIMPLES_DO_ROTULO = (
    "/ancestor::div[@data-container][2]"
    "[not(.//label[@data-label])]"
    "[not(.//div[@data-block='PMIB_DataSheetView.Block_Expression'])]"
)


def _resgatar_texto_ao_lado(engine, uniao, onde_esta_o_rotulo, campos):
    """Preenche rótulo que ficou vazio quando o valor é texto solto IRMÃO.

    A terceira variante do padrão C (ver `seletores_duplicada`, §7b-bis). Em
    «Temperatura, Umidade e Clima» o valor não tem `div` próprio -- é nó de
    texto direto da mesma caixa que embrulha o rótulo:

        <div data-container="" class="margin-top-s">
          <div data-container=""><span class="text-primary">Necessidade…</span></div>
          Sem necessidade                      <-- nem elemento é
        </div>

    Não dá para alcançá-lo por seletor de ELEMENTO (não há elemento), e pôr a
    caixa inteira na união inverteria o pareamento: em ordem de documento ela
    abre ANTES do próprio rótulo. Por isso é um segundo passo, e só sobre
    rótulo que ficou vazio -- onde hoje não há nada a perder.

    Só substitui quando o texto da caixa COMEÇA pelo rótulo e sobra algo
    depois. Campo genuinamente vazio tem caixa igual ao rótulo, não sobra
    resto, e continua `""`.
    """
    for rotulo, valor in list(campos.items()):
        if valor:
            continue
        indice = onde_esta_o_rotulo.get(rotulo)
        if not indice:
            continue
        caixa = f"({uniao})[{indice}]" + _CAIXA_SIMPLES_DO_ROTULO
        try:
            if not engine.element_exists(caixa):
                continue
            inteiro = " ".join(str(engine.texto(caixa) or "").split())
        except Exception:  # noqa: BLE001 -- não dá para ler; não inventa valor
            continue
        cabeca = " ".join(str(rotulo).split())
        if inteiro.startswith(cabeca) and len(inteiro) > len(cabeca):
            campos[rotulo] = inteiro[len(cabeca):].strip()
    return campos


def _rotular_pela_legenda(titulo, tokens, campos):
    """Bloco cujo ÚNICO rótulo é a própria `<legend>`.

    «Proteção» é assim: o valor ("Sem necessidade") não tem rótulo de campo
    nenhum ao lado -- quem nomeia o campo é a legenda do `<fieldset>`. O
    pareamento descarta valor sem rótulo anterior (e faz bem: é o que impede
    texto solto de layout de virar campo), então o bloco saía VAZIO. Foi esse
    vazio que deixou `Checkbox6/7/8` sem marcar e fez o portal recusar a
    seção inteira com "Por favor, verifique os campos".

    Só age quando o pareamento não produziu campo NENHUM -- ou seja, onde hoje
    a saída é vazia. Não pode, por construção, mudar bloco que já funciona.

    O que entra aqui ainda passa pela allowlist `CONDICOES_ROTULO_PARA_CAMPO`:
    legenda desconhecida (o "Nenhuma aplicação LMR para mostrar…" do bloco de
    LMR, por exemplo) é registrada no log e ignorada, nunca escrita na ficha.
    """
    if campos or not titulo:
        return campos
    valores = [" ".join(str(texto or "").split())
               for tipo, texto in tokens if tipo == "valor"]
    valores = [v for v in valores if v]
    if not valores:
        return campos
    # VÁRIOS valores viram uma string só, separada por `SEPARADOR_DE_OPCOES`.
    # «Proteção» aceita mais de uma marca (`Checkbox6/7/8` são checkboxes, não
    # rádios), e ficar com a primeira perderia as outras em silêncio -- a
    # mesma classe de erro que este conserto veio corrigir. Quem sabe separar
    # é `converter_da_visualizacao`, que tem o mapa das opções.
    return {titulo: sel.SEPARADOR_DE_OPCOES.join(valores)}


def ler_espanhol_visivel(engine):
    """`[(português, espanhol)]` dos textos longos da seção aberta.

    Em ORDEM DE DOCUMENTO, que é o que permite casar com os pares
    rótulo→valor sem depender de id: dois campos podem ter o mesmo português
    ("não aplicável" aparece várias vezes numa ficha), e nesse caso a ordem é
    a única coisa que os distingue.

    Uma consulta por bloco, sem `hover` e sem JS -- ver `seletores_duplicada`,
    §15c. Par sem espanhol sai com `""` em vez de sumir: some seria perder a
    informação de que o campo existe e está vazio no outro idioma.
    """
    pares = []
    total = engine.contar(sel.XPATH_VIEW_BLOCO_DOIS_IDIOMAS)
    for indice in range(1, total + 1):
        base = f"({sel.XPATH_VIEW_BLOCO_DOIS_IDIOMAS})[{indice}]"
        portugues = engine.texto(base + sel.XPATH_VIEW_TEXTO_DO_BLOCO)
        alvo = sel.XPATH_VIEW_BALAO_DO_BLOCO.format(base=base)
        espanhol = engine.texto(alvo) if engine.element_exists(alvo) else ""
        pares.append((" ".join(str(portugues or "").split()),
                      " ".join(str(espanhol or "").split())))
    return pares


def ler_secao_visivel(engine, callback_log=None):
    """[(título, {rótulo: valor})] de TODOS os blocos da seção aberta.

    Bloco sem nenhum campo é descartado: o portal usa `<fieldset>` também como
    caixa de layout, e um bloco vazio na saída viraria seção fantasma para o
    injetor do CP 6.3 tentar preencher.
    """
    def _log(mensagem):
        if callback_log:
            callback_log(mensagem)

    total = engine.contar(sel.XPATH_VIEW_BLOCO)
    blocos = []
    for indice in range(1, total + 1):
        titulo, campos = ler_bloco(engine, indice)
        if not campos:
            continue
        blocos.append((titulo, campos))
        _log(f"      [{titulo or 'sem título'}] {len(campos)} campo(s).")

    if not blocos:
        _log("      [Aviso] Nenhum bloco com campos nesta seção. Se a ficha tem "
             "dados na tela, o modo de leitura pode não ser o de visualização.")
    return blocos


# ===========================================================================
# 3. O que ainda falta — e por que não foi adivinhado
# ===========================================================================
# A navegação entre as SEÇÕES INTERNAS da ficha (Condições e suas abas, §3.4
# da especificação) NÃO está aqui. O HTML levantado com o usuário até agora é
# o das abas de status da LISTA (`role="tab"`, com badge de contagem); que as
# abas internas da ficha usem o mesmo componente é plausível e não está
# verificado -- e "plausível e não verificado" é exatamente o que produziu a
# armadilha do contador de anexos (§7d dos seletores).
#
# Enquanto isso, `ler_secao_visivel` lê a seção que estiver aberta, que é o
# suficiente para o usuário conferir a extração contra a ficha real.


# ===========================================================================
# 4. Navegar entre as seções da ficha (CP 6.4)
# ===========================================================================
# HTML levantado com o usuário em 2026-08-18. Era o que faltava: até aqui
# `ler_secao_visivel` lia a seção que estivesse aberta, e não havia como abrir
# outra.
#
# As duas funções abaixo CONFEREM o resultado do clique, e isso não é zelo
# excessivo. As seções todas ficam no DOM; um clique que não pegou deixa o
# extrator lendo a seção ANTERIOR e devolvendo dados plausíveis da seção
# errada -- o tipo de falha que não parece falha e chega até a ficha alvo.

def _sem_acento(texto):
    from unicodedata import normalize
    return normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().lower()


# XPath da raiz de uma seção aberta. Amplo de propósito: a foto de auditoria
# quer o CONTEXTO em volta, não o campo exato -- é justamente o que não se sabe
# ainda quando uma seção é nova.
XPATH_CONTEUDO_DA_SECAO = "//div[contains(@class, 'osui-tabs__content')]"

# ⚠️ A FOTO SAIU VAZIA NAS QUATRO SEÇÕES do log de 2026-08-20:
#
#     (nada casou para: //div[contains(@class, 'osui-tabs__content')],
#                       //form | //div[@id='b12'])
#
# Ou seja, o modo de auditoria estava ligado e não fotografava nada -- a
# ferramenta que existe para mapear o portal sem acesso a ele não mapeava.
#
# O que os HTMLs que o usuário mandou revelam é o padrão do container: as abas
# apontam para ele por `aria-controls`, e o id sempre termina em `_Content`:
#
#     aria-controls="b10-GeneralInformations_Content"
#     aria-controls="b10-DocumentsandImages_Content"
#
# `_Content` é semântico (nomeado por quem desenhou a tela) e o prefixo `b10-`
# é gerado -- daí o `contains`, não a igualdade.
XPATH_CONTEUDO_POR_ID = "//div[contains(@id, '_Content')]"

# `//div[@id='b12']` era um id GERADO, o que este projeto proíbe: ele mudou e a
# foto passou a devolver vazio. Fica só `//form`, mais o `<body>` como último
# recurso -- uma foto grande demais ainda é infinitamente melhor do que
# "(nada casou)", porque pelo menos contém a resposta.
XPATH_FICHA_INTEIRA = "//form | //body"

# ⚠️ O ÚLTIMO RECURSO PRECISA DE COLEIRA. Com `//body` valendo, o log de
# 2026-08-20 saiu com 121 KB para 56 linhas de texto: o arquivo que o usuário
# manda para eu ler virou ilegível para ele.
#
# 20 000 caracteres foram o suficiente, naquele mesmo log, para achar as duas
# tabelas com coluna "Descrição" e o `aria-controls` das abas -- que era tudo o
# que faltava. `recortar` avisa quanto ficou de fora, então nada some em
# silêncio.
LIMITE_DA_FOTO_DA_PAGINA = 20_000


def fotografar(portal, titulo, log_auditoria=None, seletor=None):
    """Guarda no log de execução o HTML do que está na tela.

    É o coração do MODO DE AUDITORIA, e existe por um motivo concreto: mapear
    uma seção do portal custava, até aqui, o usuário abrir o "inspecionar
    elemento" e copiar caixa por caixa. Com isto, uma execução normal deixa a
    estrutura registrada no arquivo -- e quem for consertar o seletor lê o
    markup real em vez de adivinhar.

    Vai só para o ARQUIVO (`LogDeExecucao.bloco`), nunca para o console: HTML
    de OutSystems tornaria ilegível a tela que o usuário está acompanhando.

    `log_auditoria=None` desliga tudo -- é o caminho normal, sem custo.
    """
    if log_auditoria is None:
        return ""
    alvos = [seletor] if seletor else [
        XPATH_CONTEUDO_DA_SECAO, XPATH_CONTEUDO_POR_ID, XPATH_FICHA_INTEIRA]
    for alvo in alvos:
        try:
            html = portal.engine.html_do_elemento(alvo)
        except Exception:  # noqa: BLE001 -- observar não pode derrubar o lote
            html = ""
        if html:
            # A foto da PÁGINA INTEIRA é o último recurso e a maior: leva
            # limite próprio, senão inunda o arquivo (ver
            # `LIMITE_DA_FOTO_DA_PAGINA`).
            if alvo == XPATH_FICHA_INTEIRA:
                log_auditoria.bloco(f"{titulo}  [{alvo}]", html,
                                    limite=LIMITE_DA_FOTO_DA_PAGINA)
            else:
                log_auditoria.bloco(f"{titulo}  [{alvo}]", html)
            return html
    log_auditoria.bloco(titulo, f"(nada casou para: {', '.join(alvos)})")
    return ""


def id_do_painel(portal, nome):
    """Id do PAINEL da seção `nome`, lido do `aria-controls` da aba.

    É o escopo que impede a leitura de uma seção pegar a tabela de outra. O id
    é gerado (`b12-$b17`) e por isso NÃO pode ser escrito no código -- mas
    pode ser lido em tempo de execução, que é a mesma técnica usada para achar
    o "+" da linha do fabricante pelo prefixo do campo.

    `""` quando a aba não existe: quem chama trata como "sem escopo" e o
    comportamento volta a ser o antigo, com o risco declarado.
    """
    alvo = sel.XPATH_ABA_DA_FICHA.format(texto=_literal_xpath(nome))
    try:
        return portal.engine.atributo(f"({alvo})[1]", "aria-controls") or ""
    except Exception:  # noqa: BLE001 -- ler a tela não derruba a ficha
        return ""


def abrir_secao(portal, nome, callback_log=None, log_auditoria=None):
    """Abre uma das abas da ficha ("Fabricantes e fornecedores", "Documentos",
    "Condições"). Devolve `True` se o portal confirmou que ela ficou ativa.

    A confirmação é `aria-selected="true"` no próprio botão -- ver
    `seletores_duplicada` §11.
    """
    _log = _log_de(callback_log)
    alvo = sel.XPATH_ABA_DA_FICHA.format(texto=_literal_xpath(nome))

    if not portal.engine.contar(alvo):
        _log(f"   [Erro] A aba {nome!r} não existe nesta tela.")
        return False

    portal.safe_click(f"({alvo})[1]")

    ativa = sel.XPATH_ABA_DA_FICHA_ATIVA.format(texto=_literal_xpath(nome))
    if portal.engine.contar(ativa):
        _log(f"   Seção aberta: {nome}")
        # ⚠️ FOTOGRAFA O PAINEL, não a página. `//body` começa no topo, e a
        # seção de Condições fica lá embaixo: com o teto de 20 000 caracteres
        # (que existe para o log não virar 121 KB), o markup que eu precisava
        # ler foi cortado antes de aparecer -- a rodada de 2026-08-20 15h
        # fotografou a aba certa e não trouxe um único "Comprimento".
        #
        # O `aria-controls` dá o painel exato e resolve as duas pontas: cabe
        # no limite e não traz nada de outra seção junto.
        painel = id_do_painel(portal, nome)
        alvo = (sel.XPATH_PAINEL_POR_ID.format(id=_literal_xpath(painel))
                if painel else None)
        fotografar(portal, f"Seção «{nome}» (aberta)", log_auditoria, seletor=alvo)
        return True

    _log(f"   [Erro] Cliquei em {nome!r} e o portal não marcou a aba como ativa. "
         f"NÃO vou ler -- leria a seção anterior achando que era esta.")
    # Foto do FRACASSO: é o caso em que o markup real vale mais, porque quem
    # for consertar precisa ver por que o clique não pegou.
    fotografar(portal, f"Seção «{nome}» (o clique NÃO pegou)", log_auditoria)
    return False


def abrir_subaba_de_condicoes(portal, nome, callback_log=None, log_auditoria=None):
    """Abre uma sub-aba DENTRO de Condições. Devolve `True` se ficou ativa.

    As sub-abas NÃO são o mesmo componente das abas de cima: são `<div
    class="OSInline">` com `cursor: pointer`, e a aberta ganha a classe
    `dummy-active`. Supor que fossem `role="tab"` era plausível -- e errado;
    tem teste contra o HTML real para a suposição não voltar.
    """
    _log = _log_de(callback_log)
    alvo = sel.XPATH_SUBABA_CONDICOES.format(texto=_literal_xpath(nome))

    if not portal.engine.contar(alvo):
        _log(f"   [Erro] A sub-aba {nome!r} não existe nesta tela.")
        return False

    portal.safe_click(f"({alvo})[1]")

    ativa = sel.XPATH_SUBABA_CONDICOES_ATIVA.format(texto=_literal_xpath(nome))
    if portal.engine.contar(ativa):
        _log(f"      Sub-aba aberta: {nome}")
        # ⚠️ MESMA COLEIRA DE `abrir_secao`, e pelo mesmo motivo -- eu tinha
        # consertado lá e deixado AQUI o defeito. Sem âncora, `fotografar` cai
        # no último recurso (`//form | //body`), que começa no topo da página;
        # o teto de 20 000 caracteres então gasta a foto inteira no cabeçalho.
        # No log de 2026-08-24 as duas fotos de sub-aba saíram com 20 KB de
        # menu e calendário, e nenhuma linha de Condições -- eu fiquei cego
        # justamente na seção que estou tentando fechar.
        painel = id_do_painel(portal, sel.NOME_DA_ABA_CONDICOES)
        alvo = (sel.XPATH_PAINEL_POR_ID.format(id=_literal_xpath(painel))
                if painel else None)
        fotografar(portal, f"Sub-aba de Condições «{nome}» (aberta)",
                   log_auditoria, seletor=alvo)
        return True

    _log(f"      [Erro] Cliquei em {nome!r} e ela não ficou com '{sel.CLASSE_SUBABA_ATIVA}'. "
         f"NÃO vou ler.")
    fotografar(portal, f"Sub-aba «{nome}» (o clique NÃO pegou)", log_auditoria)
    return False


# ===========================================================================
# 5. Fabricantes e fornecedores — duas TABELAS, não pares rótulo→valor
# ===========================================================================
# ⚠️ CORRIGE UMA SUPOSIÇÃO DO EXTRATOR. `ler_secao_visivel` varre pares
# rótulo→valor exigindo o ancestral `PMIB_DataSheetView.Block_Expression`; as
# células desta seção NÃO o têm. Ou seja, `achar_fabricante`/`achar_fornecedor`
# lendo daquela varredura devolvem VAZIO para esta ficha, sem erro nenhum --
# provado em `tests/test_duplicadas_xpath_real.py` contra o HTML real.
#
# Os dois contêineres têm o MESMO sufixo de id (`-ManufacturerAndProvider`),
# então o id não separa fabricante de fornecedor. Quem separa é o
# `@data-header` da célula -- o mesmo atributo que `tech_specs` já usa.

def ler_tabela_de(portal, coluna_nome, callback_log=None,
                  coluna_referencia=sel.COLUNA_REFERENCIA, escopo=None):
    """Linhas de uma das tabelas, como lista de `(nome, referência)`.

    `coluna_nome` é `COLUNA_NOME_FABRICANTE`, `COLUNA_NOME_FORNECEDOR` ou
    `COLUNA_DESCRICAO`.

    ⚠️ `coluna_referencia=None` para as tabelas que NÃO TÊM segunda coluna --
    a de Documentos é uma. Passar o default nela foi o travamento de
    2026-08-20: cada linha esperava o timeout inteiro por uma célula que não
    existe. O conserto geral (não esperar pelo ausente) está em
    `PMIBPortal.texto_se_existir`; este parâmetro é o conserto local, e vale
    por si -- não se pede o que se sabe que não está lá.

    Devolve TODAS as linhas de propósito: nesta ficha o fabricante tem duas
    ("a gente comprou de um que comprou do fabricante" -- ENERSYS fabrica,
    SASSI revende). Ler só a primeira perderia a segunda em silêncio.
    """
    _log = _log_de(callback_log)
    linhas_xpath = sel.XPATH_LINHAS_DA_TABELA_DE.format(
        coluna=_literal_xpath(coluna_nome))
    # ⚠️ SEM ESCOPO A LEITURA VAZA PARA OUTRA SEÇÃO. "Descrição" é coluna de
    # características E de documentos; sem prender a busca ao painel, o XPath
    # fica com a primeira tabela da página. Ver `XPATH_PAINEL_POR_ID`.
    if escopo:
        linhas_xpath = (sel.XPATH_PAINEL_POR_ID.format(id=_literal_xpath(escopo))
                        + linhas_xpath)
    total = portal.engine.contar(linhas_xpath)

    itens = []
    for posicao in range(1, (total or 0) + 1):
        base = f"({linhas_xpath})[{posicao}]"
        nome = _celula(portal, base, coluna_nome)
        referencia = (_celula(portal, base, coluna_referencia)
                      if coluna_referencia else "")
        if nome or referencia:
            itens.append((nome, referencia))

    if not itens:
        _log(f"   [Aviso] A tabela de '{coluna_nome}' está vazia nesta ficha.")
    return itens


def _celula(portal, base_da_linha, coluna):
    # `texto_se_existir` e não `engine.texto`: célula ausente é NORMAL aqui
    # (coluna que aquela tabela não tem), e esperar o timeout por ela foi o
    # travamento de 2026-08-20. Ver `PMIBPortal.texto_se_existir`.
    bruto = portal.texto_se_existir(
        base_da_linha + sel.XPATH_REL_CELULA.format(coluna=_literal_xpath(coluna)))
    # `str.split()` normaliza `&nbsp;` (\xa0) junto com o resto -- mesma
    # decisão de `ler_bloco`.
    return " ".join(str(bruto or "").split())


def ler_fabricantes_e_fornecedores(portal, callback_log=None, log_auditoria=None):
    """Abre a aba e devolve `{"fabricantes": [...], "fornecedores": [...]}`.

    Cada item é `(nome, referência)`. Aba que não abre devolve as duas listas
    vazias -- e quem chama trata isso como "não sei", nunca como "não tem".
    """
    _log = _log_de(callback_log)
    if not abrir_secao(portal, sel.ABA_FABRICANTES_E_FORNECEDORES,
                       callback_log, log_auditoria):
        return {"fabricantes": [], "fornecedores": []}

    fabricantes = ler_tabela_de(portal, sel.COLUNA_NOME_FABRICANTE, callback_log)
    fornecedores = ler_tabela_de(portal, sel.COLUNA_NOME_FORNECEDOR, callback_log)

    for nome, referencia in fabricantes:
        _log(f"      Fabricante lido: {nome}  (ref. {referencia})")
    for nome, referencia in fornecedores:
        _log(f"      Fornecedor lido: {nome}  (ref. {referencia})")

    return {"fabricantes": fabricantes, "fornecedores": fornecedores}
