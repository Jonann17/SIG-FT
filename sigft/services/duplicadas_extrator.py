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


def _buscar_na_aba_atual(portal, pmib):
    """Digita `pmib` no filtro da lista e espera o resultado assentar."""
    portal.safe_fill(sel.XPATH_BUSCA_DA_LISTA, pmib)
    portal.engine.press("ENTER")
    time.sleep(PAUSA_APOS_BUSCA)


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
    _log(f"   Ficha {pmib} aberta em modo de visualização.")
    return True


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
    for indice in range(1, total + 1):
        tipo = "valor" if _e_valor(engine, uniao, indice) else "rotulo"
        tokens.append((tipo, _texto_do_indice(engine, uniao, indice)))

    return " ".join(str(titulo or "").split()), spec.parear_rotulos_e_valores(tokens)


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


def abrir_secao(portal, nome, callback_log=None):
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
        return True

    _log(f"   [Erro] Cliquei em {nome!r} e o portal não marcou a aba como ativa. "
         f"NÃO vou ler -- leria a seção anterior achando que era esta.")
    return False


def abrir_subaba_de_condicoes(portal, nome, callback_log=None):
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
        return True

    _log(f"      [Erro] Cliquei em {nome!r} e ela não ficou com '{sel.CLASSE_SUBABA_ATIVA}'. "
         f"NÃO vou ler.")
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

def ler_tabela_de(portal, coluna_nome, callback_log=None):
    """Linhas de uma das tabelas, como lista de `(nome, referência)`.

    `coluna_nome` é `COLUNA_NOME_FABRICANTE` ou `COLUNA_NOME_FORNECEDOR`.

    Devolve TODAS as linhas de propósito: nesta ficha o fabricante tem duas
    ("a gente comprou de um que comprou do fabricante" -- ENERSYS fabrica,
    SASSI revende). Ler só a primeira perderia a segunda em silêncio.
    """
    _log = _log_de(callback_log)
    linhas_xpath = sel.XPATH_LINHAS_DA_TABELA_DE.format(
        coluna=_literal_xpath(coluna_nome))
    total = portal.engine.contar(linhas_xpath)

    itens = []
    for posicao in range(1, (total or 0) + 1):
        base = f"({linhas_xpath})[{posicao}]"
        nome = _celula(portal, base, coluna_nome)
        referencia = _celula(portal, base, sel.COLUNA_REFERENCIA)
        if nome or referencia:
            itens.append((nome, referencia))

    if not itens:
        _log(f"   [Aviso] A tabela de '{coluna_nome}' está vazia nesta ficha.")
    return itens


def _celula(portal, base_da_linha, coluna):
    try:
        bruto = portal.engine.texto(
            base_da_linha + sel.XPATH_REL_CELULA.format(coluna=_literal_xpath(coluna)))
    except Exception:  # noqa: BLE001
        return ""
    # `str.split()` normaliza `&nbsp;` (\xa0) junto com o resto -- mesma
    # decisão de `ler_bloco`.
    return " ".join(str(bruto or "").split())


def ler_fabricantes_e_fornecedores(portal, callback_log=None):
    """Abre a aba e devolve `{"fabricantes": [...], "fornecedores": [...]}`.

    Cada item é `(nome, referência)`. Aba que não abre devolve as duas listas
    vazias -- e quem chama trata isso como "não sei", nunca como "não tem".
    """
    _log = _log_de(callback_log)
    if not abrir_secao(portal, sel.ABA_FABRICANTES_E_FORNECEDORES, callback_log):
        return {"fabricantes": [], "fornecedores": []}

    fabricantes = ler_tabela_de(portal, sel.COLUNA_NOME_FABRICANTE, callback_log)
    fornecedores = ler_tabela_de(portal, sel.COLUNA_NOME_FORNECEDOR, callback_log)

    for nome, referencia in fabricantes:
        _log(f"      Fabricante lido: {nome}  (ref. {referencia})")
    for nome, referencia in fornecedores:
        _log(f"      Fornecedor lido: {nome}  (ref. {referencia})")

    return {"fabricantes": fabricantes, "fornecedores": fornecedores}
