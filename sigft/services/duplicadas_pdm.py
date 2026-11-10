r"""
Ficha duplicada — o PDM da ficha ALVO (CP 6.4).

Achado do usuário na rodada de 2026-08-20: *"a ficha 922 estava com um PDM
diferente, então as características técnicas não estavam corretas na ficha.
Devemos primeiro ver que tipo de PDM é a ficha alvo."*

🎯 **O PDM DETERMINA QUAIS CARACTERÍSTICAS A FICHA TEM.** É por isso que isto
é pré-requisito e não um detalhe de conferência. A 4500063671.0922 estava com
`PDM.4820.010 - REGULADOR, PRESSAO` e o robô apagou as 26 características
daquele PDM procurando uma linha `CODIGO PMIB` que ali não existe:

    Características: 26 apagada(s), 0 preservada(s).
    [Erro] Nenhuma linha de CODIGO PMIB encontrada.

Trocar o PDM depois não desfaz isso. A ordem certa é: trocar o PDM, SALVAR
(aí o portal renderiza as características do PDM novo) e só então purgar.

O combo é o mesmo widget `virtual-select` do fabricante, então a mecânica de
abrir/filtrar/escolher é a que `duplicadas_injetor` já tem. O que muda é o
casamento: por PREFIXO (`PDM.9900.000`), porque *"a revisão R0 pode mudar"*.
"""
from __future__ import annotations

import time

from sigft.core.rpa import seletores_duplicada as sel
from sigft.core.rpa.engine import NavegadorFechado
from sigft.services import duplicadas_extrator as extrator
from sigft.services.duplicadas_injetor import ResultadoDaSecao, _literal, _log_de

PAUSA_APOS_DIGITAR = 0.6
PAUSA_APOS_TROCAR = 3.0


def pdm_atual(portal):
    """Texto do PDM que está na ficha aberta. `""` se o combo não estiver lá."""
    return portal.texto_se_existir(sel.XPATH_PDM_VALOR).strip()


def e_o_pdm_da_duplicada(texto):
    """Compara pelo PREFIXO. Ver `sel.PDM_DA_DUPLICADA`: a revisão varia."""
    return str(texto or "").strip().upper().startswith(sel.PDM_DA_DUPLICADA)


def garantir_pdm(portal, callback_log=None):
    """Deixa a ficha ALVO com o PDM da duplicada. Devolve `ResultadoDaSecao`.

    Não é idempotente por acaso: quando o PDM já é o certo, NÃO salva. Salvar
    à toa custa uma recarga de página e um toast a mais na tela -- e o toast a
    mais é justamente o que confunde a confirmação da seção seguinte.
    """
    _log = _log_de(callback_log)

    if not extrator.abrir_secao(portal, sel.NOME_DA_ABA_INFO_GERAIS, callback_log):
        _log("      [Erro] Não abri 'Informações gerais' para conferir o PDM. "
             "As características podem ser as do PDM errado -- confira à mão.")
        return ResultadoDaSecao("pdm", False, "aba não abriu")

    atual = pdm_atual(portal)
    if not atual:
        _log("      [Erro] Não achei o combo de PDM nesta tela. NÃO mexi nas "
             "características -- sem saber o PDM, purgar é chute.")
        return ResultadoDaSecao("pdm", False, "combo não encontrado")

    if e_o_pdm_da_duplicada(atual):
        _log(f"      PDM já é o da duplicada: {atual}")
        return ResultadoDaSecao("pdm", True, atual)

    _log(f"      PDM atual: {atual}, trocando para {sel.PDM_DA_DUPLICADA}.")
    if not _escolher_pdm_da_duplicada(portal, callback_log):
        return ResultadoDaSecao("pdm", False, f"não troquei (estava {atual})")

    if not portal.salvar_e_confirmar(sel.NOME_DA_ABA_INFO_GERAIS, callback_log,
                                     ancora=sel.XPATH_INFO_GERAIS_SECAO):
        _log("      [Erro] Troquei o PDM mas o portal não confirmou o "
             "salvamento. NÃO siga para as características: elas ainda são as "
             "do PDM antigo.")
        return ResultadoDaSecao("pdm", False, "troquei e não salvou")

    # A recarga muda a tela inteira -- a lista de características é outra.
    time.sleep(PAUSA_APOS_TROCAR)

    # A PROVA: relê. Um SALVAR confirmado não garante que o combo ficou com o
    # valor escolhido, e é justamente esta ficha que mostra o preço de supor.
    depois = pdm_atual(portal)
    if not e_o_pdm_da_duplicada(depois):
        _log(f"      [Erro] Depois de salvar, o PDM continua {depois!r}. "
             f"Ajuste à mão antes de seguir.")
        return ResultadoDaSecao("pdm", False, f"ficou {depois}")

    _log(f"      PDM trocado e confirmado: {depois}")
    return ResultadoDaSecao("pdm", True, depois)


def _escolher_pdm_da_duplicada(portal, callback_log=None):
    """Abre o combo, filtra pelo prefixo e escolhe. `True` se clicou a opção."""
    _log = _log_de(callback_log)

    portal.safe_click(f"({sel.XPATH_PDM_COMBO})[1]")
    time.sleep(PAUSA_APOS_DIGITAR)

    # ⚠️ A CAIXA DO COMBO DO PDM, amarrada ao widget pelo número da instância
    # (ver `seletores_duplicada`, "O DROPDOWN CERTO"). Aqui havia uma busca
    # por placeholder "PDM" -- que não existe, a caixa do PDM diz só
    # "Pesquisar" -- com queda para um seletor genérico que casa as CINCO
    # caixas da tela. `safe_fill` pegava a primeira, escondida, e o filtro ia
    # para o dropdown de característica técnica. O log então listava as opções
    # DAQUELE dropdown e concluía que `PDM.9900.000` não estava no catálogo.
    # Está: com a caixa certa, o filtro deixa exatamente uma opção.
    busca = sel.XPATH_PDM_BUSCA

    # ⚠️ O COMBO ABRIU MESMO? Conserto de 2026-08-21, do log das 16:17: entre
    # "trocando para PDM.9900.000" e o erro passaram 22 s, numa função cujas
    # pausas somam 1,2 s. Os 20 s que faltavam eram o timeout do motor sendo
    # ENGOLIDO -- `engine.fill` não levanta por contrato, então escrever o
    # filtro num dropdown que nunca abriu custava o timeout inteiro e não
    # deixava rastro.
    #
    # Pior que o tempo era a MENSAGEM: a função seguia e terminava com
    # "PDM.9900.000 não apareceu no combo depois de filtrar", que manda
    # conferir o catálogo. O problema era a tela. Duas investigações
    # diferentes, e a errada custa a tarde.
    if not portal.engine.element_exists(busca):
        _log("      [Erro] O combo de PDM não abriu (nenhuma caixa de busca na "
             "tela depois do clique). Não cheguei a filtrar nada -- o PDM da "
             "ficha continua o que era.")
        return False

    portal.safe_fill(busca, sel.PDM_DA_DUPLICADA)
    time.sleep(PAUSA_APOS_DIGITAR)

    alvo = sel.XPATH_PDM_OPCAO_POR_PREFIXO.format(
        texto=_literal(sel.PDM_DA_DUPLICADA))
    try:
        quantas = portal.engine.contar(alvo)
    except NavegadorFechado:
        raise
    except Exception:  # noqa: BLE001
        quantas = 0

    if quantas == 0:
        _log(f"      [Erro] {sel.PDM_DA_DUPLICADA} não apareceu no combo do PDM "
             f"depois de filtrar. Nada foi selecionado.")
        # ⚠️ A LISTA REAL, e não mais o meu palpite. Este erro já apareceu em
        # três rodadas seguidas (0928, 0929, 1277) e a mensagem sozinha não
        # distingue as duas causas possíveis: ou o PDM.9900.000 não está no
        # catálogo deste usuário, ou o filtro foi digitado num lugar que não é
        # a caixa de busca deste dropdown. As duas pedem conserto oposto.
        _listar_opcoes(portal, callback_log)
        return False

    # Mais de uma opção com o mesmo prefixo é possível (revisões diferentes do
    # mesmo PDM). Ficar com a primeira é aceitável AQUI, e só aqui: as opções
    # diferem pela revisão, e o portal lista a vigente primeiro. Escolher entre
    # fabricantes parecidos seria outra história -- lá o robô recusa.
    portal.safe_click(f"({alvo})[1]")
    time.sleep(PAUSA_APOS_DIGITAR)
    if not _confirmar_a_troca(portal, callback_log):
        return False
    return _fechar_o_dropdown(portal, callback_log)


def _confirmar_a_troca(portal, callback_log=None):
    """Clica no CONFIRMAR do diálogo "Trocar PDM". `True` se não sobrou modal.

    O portal pergunta antes de trocar, porque a troca APAGA as Características
    Técnicas -- e essa é justamente a intenção aqui. Enquanto o diálogo estiver
    aberto ele cobre a página inteira: o SALVAR de Informações gerais e os
    quatro de Condições falharam todos por `TempoEsgotado` até este clique
    existir (2026-08-25).

    Diálogo que não aparece não é erro: quando o PDM já era o certo, ou quando
    a ficha não tem característica nenhuma a perder, o portal troca direto.
    """
    _log = _log_de(callback_log)
    for _ in range(TENTATIVAS_DO_FECHO):
        try:
            if not portal.engine.contar(sel.XPATH_DIALOGO_CONFIRMAR):
                return True
        except NavegadorFechado:
            raise
        except Exception:  # noqa: BLE001 -- tela remontando
            return True
        try:
            portal.engine.click_estrito(sel.XPATH_DIALOGO_CONFIRMAR)
            _log("      Confirmei a troca de PDM (o portal avisa que as "
                 "Características Técnicas serão removidas -- é o que se quer).")
            time.sleep(PAUSA_APOS_DIGITAR)
        except NavegadorFechado:
            raise
        except Exception as erro:  # noqa: BLE001
            _log(f"      [Erro] O diálogo 'Trocar PDM' está na tela e o "
                 f"CONFIRMAR não aceitou o clique: {type(erro).__name__}. "
                 f"Enquanto ele estiver aberto, nada mais na página é "
                 f"clicável.")
            return False
        time.sleep(INTERVALO_DO_FECHO)
    return not portal.engine.contar(sel.XPATH_DIALOGO_CONFIRMAR)


# Quantas vezes se confere se o dropdown sumiu (x `INTERVALO_DO_FECHO`).
TENTATIVAS_DO_FECHO = 12
INTERVALO_DO_FECHO = 0.5


def _fechar_o_dropdown(portal, callback_log=None):
    """Garante que a lista do combo saiu da frente. `True` se saiu.

    ⚠️ ISTO NÃO É ZELO. Medido em 2026-08-25, na ficha 4500063671.0928: com a
    caixa de busca certa o combo passou a filtrar e a opção foi clicada -- e
    daí em diante TODO clique da ficha falhou com `TempoEsgotado`, "algo pode
    estar cobrindo o botão". Foram cinco: o SALVAR de Informações gerais e os
    quatro SALVAR de Condições, que na rodada anterior salvavam.

    O dropdown do `vscomp` é filho de `<body>` e se sobrepõe à página inteira.
    Enquanto ele estiver aberto, o Playwright recusa clicar em qualquer coisa
    embaixo -- e com razão: um humano também não conseguiria.

    O sintoma engana de propósito: a mensagem fala do botão que falhou, nunca
    do combo que ficou aberto três seções atrás. Consertar o combo sem fechá-lo
    trocaria "o PDM não troca" por "nada mais salva depois do PDM", que é pior.
    """
    _log = _log_de(callback_log)
    for _ in range(TENTATIVAS_DO_FECHO):
        try:
            # ⚠️ PERGUNTA PELO CONTAINER, NÃO PELA CONTAGEM DE OPÇÕES. O
            # widget esconde a lista sem tirá-la do DOM: contar opção devolve
            # 10 com o dropdown fechado, e o guard abortava uma troca que
            # tinha dado certo (medido em 2026-08-25).
            if not portal.engine.contar(sel.XPATH_PDM_DROPBOX_ABERTO):
                return True
        except NavegadorFechado:
            raise
        except Exception:  # noqa: BLE001 -- tela remontando
            pass
        try:
            portal.engine.press("ESCAPE")
        except NavegadorFechado:
            raise
        except Exception:  # noqa: BLE001 -- sem foco; a próxima volta tenta
            pass
        time.sleep(INTERVALO_DO_FECHO)

    _log("      [Erro] Escolhi o PDM mas a lista do combo não fechou. Ela cobre "
         "a página inteira: qualquer SALVAR depois disto falharia por "
         "'TempoEsgotado'. Feche a lista à mão e rode de novo.")
    return False


LIMITE_DE_OPCOES_NO_LOG = 15


def _listar_opcoes(portal, callback_log=None, limite=LIMITE_DE_OPCOES_NO_LOG):
    """Loga as opções que o dropdown DO PDM está mostrando de fato.

    ⚠️ ESCOPADO NO DROPBOX DO PDM desde 2026-08-25. Antes lia o seletor
    genérico de opção, que na tela de edição casa o dropdown de QUALQUER um
    dos cinco `vscomp`. Foi assim que o log de três rodadas seguidas (0928,
    0929, 1277) mandou investigar o catálogo de PDM mostrando "PEÇA - (PC)" e
    "3M DO BRASIL LTDA." -- as opções de outro widget. Diagnóstico que aponta
    para o lugar errado custa mais caro que diagnóstico nenhum.

    Só é chamado no fracasso -- é diagnóstico, não caminho normal. Lê pelo
    índice (`(...)[n]`) com `texto_se_existir`, que devolve `""` para o
    ausente em vez de pagar o timeout do motor: o dropdown pode ter fechado
    sozinho entre o filtro e esta leitura, e nesse caso a resposta certa é
    "nenhuma", na hora, e não vinte segundos de espera por opção.
    """
    _log = _log_de(callback_log)
    try:
        total = portal.engine.contar(sel.XPATH_PDM_OPCAO_QUALQUER)
    except NavegadorFechado:
        raise
    except Exception:  # noqa: BLE001 -- observar não pode derrubar o lote
        total = 0

    if not total:
        _log("         [i] O dropdown não está mostrando opção nenhuma agora. "
             "Ou ele fechou antes desta leitura, ou o texto do filtro nunca "
             "chegou na caixa de busca dele.")
        return []

    vistas = []
    for indice in range(1, min(total, limite) + 1):
        texto = portal.texto_se_existir(
            f"({sel.XPATH_PDM_OPCAO_QUALQUER})[{indice}]").strip()
        if texto:
            vistas.append(texto)

    _log(f"         [i] O combo está listando {total} opção(ões). "
         f"As {len(vistas)} primeiras:")
    for texto in vistas:
        _log(f"             · {texto}")
    if total > limite:
        _log(f"             … e mais {total - limite}.")
    return vistas
