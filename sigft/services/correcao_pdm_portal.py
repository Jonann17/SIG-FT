r"""As duas operações de portal do módulo de correção de PDM (E4, parte 1).

TROCAR o PDM de uma ficha para um PDM qualquer, e ESCREVER uma característica
a partir do plano da E3. As duas já existem no app, e nenhuma das duas serve
como está:

- `duplicadas_pdm.garantir_pdm` troca para UM PDM fixo (`sel.PDM_DA_DUPLICADA`,
  a ficha-modelo da duplicação), amarrado no módulo. Aqui o PDM vem da tela,
  ficha a ficha;
- `tech_specs._preencher_linha` escreve a partir do dicionário do JSON da IA,
  e não a partir de uma `Reposicao`.

⚠️ "JA E O PDM CERTO" NAO SE DECIDE PELO CODIGO
------------------------------------------------------------------------
O caso principal do usuário são 25 fichas que **só mudam de revisão**: mesmo
código, `R1` virando `R2`. Um guard que comparasse código com código diria "já
está certo" e o módulo não faria nada, calado, nas 25.

Quem decide é o confronto entre o que está na ficha e **o que o combo oferece**:
o portal lista só a revisão vigente (dito pelo usuário em 2026-09-23), então a
opção que aparece É o destino. Igual ao que já está lá, não mexe; diferente,
troca.

O outro lado dessa regra importa igual: se a ficha já está na revisão vigente,
**não trocar** é obrigatório. A troca apaga todas as características, e
apagá-las para chegar ao mesmo lugar seria destruir a ficha à toa.

O QUE ESTE MODULO HERDA, E NAO REDESCOBRE
------------------------------------------------------------------------
1. **A caixa de busca do combo do PDM** é endereçada pelo número da instância
   do widget (`sel.XPATH_PDM_BUSCA`). A página tem CINCO `vscomp-search-input`,
   e a genérica pega a primeira, escondida (2026-08-25).
2. **O combo abriu mesmo?** `engine.fill` não levanta por contrato: escrever
   num dropdown que nunca abriu custa o timeout inteiro e a mensagem manda
   investigar o catálogo em vez da tela (2026-08-21).
3. **O modal de confirmação cobre a página inteira** enquanto estiver aberto.
   Ele é o que avisa que as características serão removidas.
4. **A prova é reler o combo depois de salvar.** Um SALVAR confirmado não
   garante que o valor ficou (ficha 4500063671.0922).
5. **A cascata de busca** (texto completo, só o código, só o título) é a de
   `cria_fichas.tentativas_de_busca`, pedida pelo usuário em 2026-09-22.
6. **Escrever uma linha** é `tech_specs._preencher_linha`, reusada inteira.

Plano completo em `docs/refatoracao/CORRECAO_PDM.md` (etapa E4).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass

from sigft.core.rpa import caracteristicas as leitor
from sigft.core.rpa import seletores_duplicada as sel
from sigft.services import cria_fichas, duplicadas_extrator as extrator
from sigft.services.duplicadas_injetor import _literal, _log_de
from sigft.services.tech_specs import TechSpecsAutomation


PAUSA_APOS_DIGITAR = 0.6
# A recarga muda a tela inteira: a lista de características é outra.
PAUSA_APOS_TROCAR = 3.0
TENTATIVAS_DO_FECHO = 12
INTERVALO_DO_FECHO = 0.5

_RE_INDICE = re.compile(r"\)\[(\d+)\]")
_RE_LITERAL = re.compile(r"starts-with\(@data-tooltip, '([^']*)'\)")


def seletor_da_linha(indice: int) -> str:
    """O endereço da linha `indice` (1-based) da tabela de características.

    ⚠️ A MESMA base do leitor (E1), de propósito e com teste. Ler a linha 3 e
    escrever na linha 4 seria o defeito perfeito: silencioso e destrutivo.
    """
    return f"({leitor.XPATH_LINHAS})[{indice}]"


def _indice_do_seletor(seletor):
    """O `N` de `(...)[N]`, ou `None`. O primeiro `[` não serve: o XPath das
    linhas tem colchetes dentro (`contains(@id, ...)`)."""
    achado = _RE_INDICE.search(str(seletor or ""))
    return int(achado.group(1)) if achado else None


def _texto_do_literal(seletor):
    """O texto que `XPATH_PDM_OPCAO_POR_PREFIXO` está filtrando."""
    achado = _RE_LITERAL.search(str(seletor or ""))
    return achado.group(1) if achado else ""


# =============================================================================
# Trocar o PDM
# =============================================================================
@dataclass(frozen=True)
class ResultadoDaTroca:
    """`trocou` e `ok` são perguntas DIFERENTES.

    `ok=True, trocou=False` é o caso bom de uma ficha que já estava na revisão
    certa: nada falhou e nada foi mexido. Quem chama não pode confundir os dois
    -- seguir para a reposição achando que houve troca faria o robô repor
    características sobre uma ficha que não perdeu nenhuma.
    """

    ok: bool
    trocou: bool
    pdm_antes: str = ""
    pdm_depois: str = ""
    motivo: str = ""


def pdm_atual(portal) -> str:
    """O texto do PDM da ficha aberta, COM a revisão. `""` se o combo sumiu."""
    return portal.texto_se_existir(sel.XPATH_PDM_VALOR).strip()


def _opcoes_que_casam(portal, texto):
    """As opções do combo cujo `data-tooltip` começa por `texto`, já lidas.

    Ler o texto (e não só contar) é o que permite decidir se a opção é
    diferente do que a ficha já tem -- a regra do topo deste módulo.
    """
    alvo = sel.XPATH_PDM_OPCAO_POR_PREFIXO.format(texto=_literal(texto))
    try:
        quantas = portal.engine.contar(alvo)
    except Exception:  # noqa: BLE001 -- tela remontando
        return alvo, []

    lidas = []
    for indice in range(1, quantas + 1):
        try:
            lidas.append(str(portal.engine.texto(f"({alvo})[{indice}]") or "").strip())
        except Exception:  # noqa: BLE001
            lidas.append("")
    return alvo, lidas


def _abrir_o_combo(portal, callback_log=None):
    """Clica no combo e confirma que ele abriu. `True` se a caixa está na tela."""
    _log = _log_de(callback_log)
    portal.safe_click(f"({sel.XPATH_PDM_COMBO})[1]")
    time.sleep(PAUSA_APOS_DIGITAR)

    if not portal.engine.element_exists(sel.XPATH_PDM_BUSCA):
        _log("      [Erro] O combo de PDM nao abriu (nenhuma caixa de busca na "
             "tela depois do clique). Nao cheguei a filtrar nada: o PDM da "
             "ficha continua o que era.")
        return False
    return True


def _procurar_no_combo(portal, pdm_pretendido, callback_log=None):
    """Filtra o combo pela cascata e devolve `(seletor_da_opcao, texto)`.

    `(None, "")` quando nenhuma das tentativas achou. A cascata é a de
    `cria_fichas.tentativas_de_busca`: texto completo, só o código, só o
    título.
    """
    _log = _log_de(callback_log)

    for tentativa in cria_fichas.tentativas_de_busca(pdm_pretendido):
        portal.safe_fill(sel.XPATH_PDM_BUSCA, tentativa)
        time.sleep(PAUSA_APOS_DIGITAR)

        # O filtro do combo é por texto livre; o casamento da OPÇÃO continua
        # sendo pelo que se pediu, para o caso de a busca por título trazer
        # vizinhos.
        codigo = cria_fichas.codigo_do_pdm(pdm_pretendido)
        alvo, lidas = _opcoes_que_casam(portal, codigo or tentativa)
        if not lidas:
            continue

        if len(lidas) > 1:
            # O portal deveria listar so a revisao vigente. Se listar duas, a
            # escolha vira palpite -- e um palpite aqui apaga caracteristicas.
            # Nao bloqueia (bloquear travaria as 25 fichas por uma hipotese),
            # mas nao passa calado. Pendencia aberta em PENDENCIAS.md.
            _log(f"      [Aviso] O combo trouxe {len(lidas)} opcoes para "
                 f"{codigo or tentativa!r}: {', '.join(repr(x) for x in lidas)}. "
                 f"Fico com a primeira; confira a revisao no fim.")
        return f"({alvo})[1]", lidas[0]

    _log(f"      [Erro] {pdm_pretendido!r} nao apareceu no combo do PDM depois "
         f"de filtrar (tentei o texto completo, o codigo e o titulo). Nada foi "
         f"selecionado.")
    return None, ""


def _confirmar_a_troca(portal, callback_log=None):
    """Clica no CONFIRMAR do diálogo "Trocar PDM". `True` se não sobrou modal.

    Diálogo que não aparece não é erro: quando a ficha não tem característica
    nenhuma a perder, o portal troca direto.
    """
    _log = _log_de(callback_log)
    for _ in range(TENTATIVAS_DO_FECHO):
        try:
            if not portal.engine.contar(sel.XPATH_DIALOGO_CONFIRMAR):
                return True
        except Exception:  # noqa: BLE001 -- tela remontando
            return True
        try:
            portal.engine.click_estrito(sel.XPATH_DIALOGO_CONFIRMAR)
            _log("      Confirmei a troca de PDM (o portal avisa que as "
                 "Caracteristicas Tecnicas serao removidas: e o que se quer, "
                 "porque elas ja estao no retrato).")
            time.sleep(PAUSA_APOS_DIGITAR)
        except Exception as erro:  # noqa: BLE001
            _log(f"      [Erro] O dialogo 'Trocar PDM' esta na tela e o "
                 f"CONFIRMAR nao aceitou o clique: {type(erro).__name__}. "
                 f"Enquanto ele estiver aberto, nada mais na pagina e clicavel.")
            return False
        time.sleep(INTERVALO_DO_FECHO)
    try:
        return not portal.engine.contar(sel.XPATH_DIALOGO_CONFIRMAR)
    except Exception:  # noqa: BLE001
        return True


def trocar_pdm(portal, pdm_pretendido, callback_log=None) -> ResultadoDaTroca:
    """Deixa a ficha aberta com `pdm_pretendido`. Ver `ResultadoDaTroca`.

    `pdm_pretendido` pode ser o texto completo (`PDM.5920.020 - PROTETOR,
    SURTO`) ou só o código (`PDM.5920.020`). Só o código é o modo **"atualizar
    a revisão"**: o combo oferece a vigente, e é ela que entra.

    ⚠️ Esta função NAO grava retrato e NAO confere se há características a
    perder. Quem chama é que tem essa obrigação, e ela é a regra de ordem do
    plano: *não trocar o PDM se o retrato não gravou*.
    """
    _log = _log_de(callback_log)

    if not extrator.abrir_secao(portal, sel.NOME_DA_ABA_INFO_GERAIS, callback_log):
        _log("      [Erro] Nao abri 'Informacoes gerais' para ver o PDM. Nao "
             "mexi em nada.")
        return ResultadoDaTroca(False, False, motivo="a aba nao abriu")

    antes = pdm_atual(portal)
    if not antes:
        # Sem saber o PDM atual, trocar e chute -- e o retrato ficaria sem o
        # "de onde" que o relatorio precisa.
        _log("      [Erro] Nao achei o combo de PDM nesta tela.")
        return ResultadoDaTroca(False, False, motivo="combo de PDM nao encontrado")

    if not _abrir_o_combo(portal, callback_log):
        return ResultadoDaTroca(False, False, pdm_antes=antes,
                                motivo="o combo de PDM nao abriu")

    seletor, texto_da_opcao = _procurar_no_combo(portal, pdm_pretendido, callback_log)
    if not seletor:
        _fechar_o_combo(portal)
        return ResultadoDaTroca(False, False, pdm_antes=antes,
                                motivo=f"{pdm_pretendido} nao esta no combo")

    # ⚠️ AQUI MORA A REGRA DO TOPO DO MODULO. A comparacao e entre o que a
    # ficha TEM e o que o combo OFERECE -- os dois textos completos, com a
    # revisao. Comparar codigos faria as 25 fichas de "so atualizar a revisao"
    # passarem batidas; trocar sem comparar apagaria as caracteristicas de uma
    # ficha que ja estava certa.
    if _mesmo_texto(antes, texto_da_opcao):
        _fechar_o_combo(portal)
        _log(f"      PDM ja e o vigente: {antes}. Nao troquei nada (trocar "
             f"apagaria as caracteristicas para chegar ao mesmo lugar).")
        return ResultadoDaTroca(True, False, pdm_antes=antes, pdm_depois=antes)

    _log(f"      PDM atual: {antes}. Trocando para: {texto_da_opcao}.")
    portal.safe_click(seletor)
    time.sleep(PAUSA_APOS_DIGITAR)

    if not _confirmar_a_troca(portal, callback_log):
        return ResultadoDaTroca(False, False, pdm_antes=antes,
                                motivo="o modal de confirmacao nao fechou")

    if not portal.salvar_e_confirmar(sel.NOME_DA_ABA_INFO_GERAIS, callback_log,
                                     ancora=sel.XPATH_INFO_GERAIS_SECAO):
        _log("      [Erro] Troquei o PDM e o portal nao confirmou o "
             "salvamento. NAO siga para as caracteristicas.")
        return ResultadoDaTroca(False, True, pdm_antes=antes,
                                motivo="troquei e o portal nao salvou")

    time.sleep(PAUSA_APOS_TROCAR)

    # A PROVA: rele. Um SALVAR confirmado nao garante que o combo ficou com o
    # valor escolhido, e e justamente a ficha 0922 que mostra o preco de supor.
    depois = pdm_atual(portal)
    if not _mesmo_texto(depois, texto_da_opcao):
        _log(f"      [Erro] Depois de salvar, o PDM da ficha e {depois!r} e nao "
             f"{texto_da_opcao!r}.")
        return ResultadoDaTroca(False, True, pdm_antes=antes, pdm_depois=depois,
                                motivo=f"depois de salvar ficou {depois}")

    _log(f"      PDM trocado e confirmado: {depois}")
    return ResultadoDaTroca(True, True, pdm_antes=antes, pdm_depois=depois)


def _mesmo_texto(a, b) -> str:
    return " ".join(str(a or "").upper().split()) == " ".join(str(b or "").upper().split())


def _fechar_o_combo(portal):
    """Tira o dropdown da frente. Ele cobre o resto da tela enquanto aberto."""
    try:
        portal.engine.press("ESCAPE")
    except Exception:  # noqa: BLE001 -- fechar e cortesia, nao requisito
        pass


# =============================================================================
# Escrever uma característica
# =============================================================================
def dado_de_escrita(reposicao) -> dict:
    """Uma `Reposicao` (E3) no dicionário que `_preencher_linha` espera.

    ⚠️ O INTERVALO VAI COM BARRA porque `_preencher_linha` lê a faixa com
    `val_pt.split("/")`. Qualquer outro separador manda o máximo para o limbo,
    sem erro nenhum.

    ⚠️ E o subtipo vazio é mantido VAZIO. `_preencher_linha` tem o default
    `"MINIMO / MAXIMO"`, que também é uma invenção; mandar vazio faz
    `selecionar_dropdown_lista` devolver `True` sem tocar no dropdown, que é o
    certo quando não se sabe qual era.
    """
    tipo = str(getattr(reposicao, "tipo", "") or "").upper()
    if tipo == "INT":
        pontas = [p for p in (reposicao.minimo, reposicao.maximo) if str(p).strip()]
        valor_pt = " / ".join(pontas)
        valor_es = valor_pt
    else:
        valor_pt = reposicao.valor_pt
        valor_es = reposicao.valor_es

    return {
        "CARACTERISTICA_CHAVE": reposicao.nome,
        "TIPO": tipo,
        "RESPOSTA_PT_FINAL": valor_pt,
        "RESPOSTA_ES_FINAL": valor_es,
        "SIMBOLO": reposicao.unidade,
        "SUBTIPO_INTERVALO": reposicao.subtipo,
    }


class EscritorDeLinha:
    r"""Escreve uma característica na linha, com as regras do `tech_specs`.

    ⚠️ REUSO DELIBERADO DE `_preencher_linha`, e o motivo é o tamanho do que se
    reusa:

    - o **blur do OutSystems**. Nem `fill` nem `send_keys` disparam `change`;
      sem o clique fora, o SALVAR grava o valor ANTIGO, sem erro nenhum;
    - a **auditoria com injeção forçada**, para quando o site zera o campo;
    - o **casamento de lista em PT e ES**, exato antes de substring;
    - a **unidade pelos parênteses** (`"Milímetro (MM)"`), com queda para a
      sigla solta.

    São duzentas linhas de regra que nasceram de falha real, e uma cópia
    divergiria na primeira correção. `TechSpecsAutomation()` não abre navegador
    nenhum no `__init__` (só `iniciar()` abre), então anexar o engine do portal
    que já está aberto é barato -- e há teste que reprova se isso mudar.
    """

    def __init__(self, portal):
        self._automacao = TechSpecsAutomation()
        self._automacao.engine = portal.engine
        self._automacao.portal = portal

    def escrever(self, seletor_linha, reposicao, callback_log=None) -> bool:
        """`True` se o portal aceitou. `False` vira pendência para quem chama."""
        return bool(self._automacao._preencher_linha(
            seletor_linha, dado_de_escrita(reposicao), callback_log))
