r"""
Ficha duplicada — DOCUMENTOS / datasheets (CP 6.4).

O documento **já existe** como objeto no portal: a ficha nova não sobe arquivo
nenhum, ela ASSOCIA o que a ficha original já usa. Por isso esta seção é a
mais barata das três do CP 6.4 -- não há download, nem upload, nem arquivo em
disco.

O caminho, com o HTML que o usuário levantou em 2026-08-18:

    "Associar documentos"  ->  abre o diálogo
    campo de busca         ->  a descrição do documento (a lista tem 809 itens
                               em 162 páginas: paginar não é alternativa)
    checkbox da linha      ->  marca
    botão ASSOCIAR         ->  confirma

⚠️ O MÓDULO ANTIGO PARA NO CHECKBOX. `ficha_duplicada._associar_documentos`
marca a caixa e volta, com um comentário admitindo a dúvida: *"(Aqui pode ser
necessário clicar em um botão para fechar o modal/confirmar, dependendo da
UI)"*. É necessário -- o usuário mandou o botão: `<button class="btn
btn-primary">ASSOCIAR</button>`. Sem esse clique, marcar a caixa não associa
nada, e o diálogo fecha igual.

A busca casa a descrição EXATA na coluna "Descrição"
(`XPATH_DOCUMENTO_LINHA_POR_DESCRICAO`), e não uma substring em qualquer
célula: uma descrição curta ("1188") apareceria também numa coluna de data ou
de código, e associar o documento errado é do tipo de erro que ninguém
percebe.
"""
from __future__ import annotations

import time

from sigft.core.rpa import seletores_duplicada as sel
from sigft.services.duplicadas_injetor import ResultadoDaSecao, _literal, _log_de

PAUSA_ABERTURA_DIALOGO = 2.0
PAUSA_RECARGA_DA_BUSCA = 2.0
PAUSA_APOS_ASSOCIAR = 2.0

# ⚠️ A CONFERÊNCIA PRECISA ESPERAR A TABELA RECARREGAR. Log de 2026-08-20, duas
# linhas seguidas no mesmo segundo:
#
#     Associado: 2904616
#     [Erro] 1 documento(s) NÃO ficaram associados: 2904616.
#
# O portal fecha o diálogo e recarrega a tabela da ficha; ler antes disso
# devolve o estado ANTERIOR, e o robô acusa de falha o que acabou de dar certo
# -- a pior espécie de falso alarme, porque some a confiança no log inteiro.
PAUSA_ANTES_DE_CONFERIR = 3.0

# ⚠️ DESISTIR CEDO. *"Eu fechei porque eu não aguentei esperar ele errar todas
# as características da ficha original tentando buscar na seção de
# documentos."* (usuário, 2026-08-20)
#
# Foram 38 buscas fracassadas, ~47 s cada: meia hora para chegar a uma
# conclusão que a TERCEIRA falha seguida já entregava -- a lista está errada.
# Nenhuma ficha real tem 38 documentos que o catálogo desconhece um a um.
#
# E insistir custava também na TELA: cada tentativa abre o diálogo de
# associação, e diálogos empilhados são o *"a página fica metade da tela,
# parecendo colapsar"* do mesmo relato.
#
# Três é o número: uma falha é um documento que sumiu do catálogo, duas ainda
# é azar, três seguidas é padrão.
MAX_FALHAS_SEGUIDAS = 3


def _marcar_checkbox_da_linha(portal, linha, callback_log=None):
    """Marca o checkbox DENTRO da linha já endereçada pela descrição.

    Duas âncoras, nesta ordem: a semântica (`@data-checkbox`) e, se ela não
    casar, qualquer checkbox da linha. A linha já foi escolhida pela descrição
    exata, então "qualquer checkbox desta linha" é uma reserva honesta -- o
    que não se pode é procurar checkbox na TELA.
    """
    for relativo in (sel.XPATH_DOCUMENTO_CHECKBOX_SEMANTICO,
                     sel.XPATH_DOCUMENTO_CHECKBOX_QUALQUER):
        seletor = linha + relativo[1:]
        try:
            if portal.engine.contar(seletor) != 1:
                continue
        except Exception:  # noqa: BLE001
            continue
        return portal.check_or_uncheck(seletor, True, callback_log)
    return False


def associar_um(portal, descricao, callback_log=None):
    """Associa UM documento pela descrição. `True` se chegou até o ASSOCIAR."""
    _log = _log_de(callback_log)

    portal.safe_click(sel.XPATH_DOCUMENTOS_ABRIR)
    time.sleep(PAUSA_ABERTURA_DIALOGO)

    portal.safe_fill(sel.XPATH_DOCUMENTOS_BUSCA, descricao)
    portal.safe_click(sel.XPATH_DOCUMENTOS_LUPA)
    time.sleep(PAUSA_RECARGA_DA_BUSCA)

    linha = sel.XPATH_DOCUMENTO_LINHA_POR_DESCRICAO.format(texto=_literal(descricao))
    try:
        quantas = portal.engine.contar(linha)
    except Exception:  # noqa: BLE001
        quantas = 0

    if quantas == 0:
        _log(f"      [Erro] Documento {descricao!r} não apareceu na busca. "
             f"Associe à mão.")
        return False
    if quantas > 1:
        # Duas linhas com a MESMA descrição exata: escolher uma é chute, e o
        # diálogo fecha igual nos dois casos.
        _log(f"      [Erro] {quantas} documentos com a descrição {descricao!r}. "
             f"NÃO associei -- escolha à mão qual é o certo.")
        return False

    if not _marcar_checkbox_da_linha(portal, f"({linha})[1]", callback_log):
        _log(f"      [Erro] Achei a linha de {descricao!r} mas não consegui "
             f"marcar a caixa. Associe à mão.")
        return False

    portal.safe_click(sel.XPATH_DOCUMENTOS_ASSOCIAR)
    time.sleep(PAUSA_APOS_ASSOCIAR)
    return True


def ja_associados(portal, escopo=None):
    """Descrições dos documentos que a ficha ABERTA já tem.

    É a releitura que fecha a seção -- *"antes de sair de cada uma das
    páginas, quero que você valide se de fato conseguiu colocar os dados"*.
    Marcar a caixa e clicar em ASSOCIAR não prova que o portal associou.
    """
    seletor = sel.XPATH_LINHAS_DA_TABELA_DE.format(
        coluna=_literal(sel.COLUNA_DESCRICAO))
    # Mesmo motivo de `extrator.ler_tabela_de`: "Descrição" é coluna de
    # características TAMBÉM, e sem escopo a leitura pega a tabela errada.
    if escopo:
        seletor = sel.XPATH_PAINEL_POR_ID.format(id=_literal(escopo)) + seletor
    try:
        total = portal.engine.contar(seletor)
    except Exception:  # noqa: BLE001
        return []
    descricoes = []
    for indice in range(1, (total or 0) + 1):
        celula = (f"({seletor})[{indice}]"
                  + sel.XPATH_REL_CELULA.format(
                      coluna=_literal(sel.COLUNA_DESCRICAO)))
        # `texto_se_existir`: linha sem a célula de Descrição é possível, e
        # esperar o timeout por ela é o travamento de 2026-08-20.
        texto = portal.texto_se_existir(celula)
        if texto and texto.strip():
            descricoes.append(" ".join(texto.split()))
    return descricoes


def associar(portal, descricoes, callback_log=None, escopo=None):
    """Associa todos os documentos da original e CONFERE o resultado."""
    _log = _log_de(callback_log)
    desejados = [" ".join(str(d).split()) for d in (descricoes or []) if str(d).strip()]
    if not desejados:
        _log("      Documentos: a ficha original não tem nenhum -- pulando.")
        return ResultadoDaSecao("documentos", True, "nenhum na origem")

    ja_tem = set(ja_associados(portal, escopo))
    faltando = [d for d in desejados if d not in ja_tem]
    if ja_tem:
        _log(f"      Documentos: {len(ja_tem)} já estavam na ficha.")

    falhas_seguidas = 0
    desistiu = False
    for descricao in faltando:
        if associar_um(portal, descricao, callback_log):
            _log(f"      Associado: {descricao[:60]}")
            falhas_seguidas = 0
            continue
        falhas_seguidas += 1
        if falhas_seguidas >= MAX_FALHAS_SEGUIDAS:
            _log(f"      [Erro] {falhas_seguidas} documentos seguidos não "
                 f"apareceram na busca -- desisti da seção. O provável é que a "
                 f"LISTA esteja errada (lida da seção errada da ficha original), "
                 f"não que o catálogo tenha perdido {len(faltando)} documentos. "
                 f"Confira e associe à mão.")
            desistiu = True
            break

    if desistiu:
        return ResultadoDaSecao("documentos", False,
                                f"desisti após {falhas_seguidas} falhas seguidas")

    # A CONFERÊNCIA: relê a tabela da ficha, não o que o diálogo mostrou.
    time.sleep(PAUSA_ANTES_DE_CONFERIR)
    agora = set(ja_associados(portal, escopo))
    nao_entraram = [d for d in desejados if d not in agora]
    if nao_entraram:
        _log(f"      [Erro] {len(nao_entraram)} documento(s) NÃO ficaram "
             f"associados: {', '.join(d[:40] for d in nao_entraram[:3])}"
             f"{' …' if len(nao_entraram) > 3 else ''}. Associe à mão.")
        return ResultadoDaSecao("documentos", False,
                                f"{len(nao_entraram)} não associados")

    return ResultadoDaSecao("documentos", True, f"{len(desejados)} associado(s)")
