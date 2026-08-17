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
