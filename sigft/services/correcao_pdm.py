r"""Corrigir o PDM de uma ficha sem perder as características técnicas.

O problema, na mecânica do portal: **trocar ou atualizar o PDM de uma ficha faz
o portal apagar TODAS as características técnicas** -- inclusive as que o PDM
novo também tem e que continuariam válidas. O próprio modal avisa ("Todos os
dados de Características Técnicas serão removidos"). Hoje isso é redigitação à
mão, ficha a ficha, e o usuário tem ~25 só de atualização de revisão.

Este módulo ORQUESTRA. Quem faz o trabalho já existe:

    abrir -> ler a tabela (E1) -> gravar o retrato (E2) ->
    trocar o PDM (E4a) -> reler a tabela (E1) -> casar (E3) ->
    repor (E4a) -> apagar as que ficaram em branco -> salvar -> relatar

AS QUATRO RECUSAS, QUE SAO O MOTIVO DE ESTE MODULO EXISTIR
------------------------------------------------------------------------
Cada uma impede que uma ficha fique **pior do que estava**:

1. **Nao trocar o PDM se o retrato nao gravou.** Sem rede, nao salta: depois do
   CONFIRMAR o dado nao existe mais em lugar nenhum.
2. **Apagar so DEPOIS de repor.** Apagar antes eliminaria as linhas que iam
   receber valor.
3. **Nao apagar nada se a reposicao falhou.** Melhor uma ficha com linhas
   vazias do que uma ficha sem as linhas: o que esta vazio a pessoa preenche, o
   que sumiu ela tem que redescobrir.
4. **Nao apagar nada quando o retrato tinha valores e NENHUM voltou.** Isso nao
   e "nao havia o que reaproveitar": e o sintoma de uma leitura quebrada, e
   nesse estado apagar as "vazias" apagaria a ficha inteira.

QUANTO SE RECUPERA -- medido, nao estimado
------------------------------------------------------------------------
- atualizacao de revisao (o caso das 25 fichas): mediana 100%, media 89%;
- os tres PDMs que a Itaipu cobrou: 76% e 57%;
- troca de PDM entre codigos diferentes: 30 a 50%.

Ou seja: numa TROCA o modulo nao devolve tudo. O que ele garante e que nada do
reaproveitavel se perde e que o resto sai em **lista explicita** em vez de
sumir calado.

Plano completo em `docs/refatoracao/CORRECAO_PDM.md`.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from sigft.core.rpa import seletores_duplicada as sel
from sigft.core.rpa.caracteristicas import XPATH_LINHAS, ler_linha, ler_tabela
from sigft.services import correcao_pdm_portal as operacoes
from sigft.services import correcao_pdm_retrato as retrato
from sigft.services.correcao_pdm_casamento import Pendencia, casar, chave
from sigft.services.correcao_pdm_portal import EscritorDeLinha, seletor_da_linha
from sigft.services.duplicadas_injetor import _log_de


# O nome da aba, para a mensagem do SALVAR. `seletores_duplicada` tem os das
# outras duas abas (Informacoes gerais, Condicoes) e nao esta; o texto vem do
# XPath da aba em `caracteristicas.XPATH_ABA`.
NOME_DA_ABA_CARACTERISTICAS = "Características técnicas"

PAUSA_CARGA_TABELA = 2.0
# O mesmo teto de `limpar_caracteristicas` e do leitor: um botao "proxima" que
# nunca desabilita giraria para sempre.
MAX_PAGINAS = 50


@dataclass(frozen=True)
class ResultadoDaFicha:
    """O que aconteceu com UMA ficha. `etapa` diz onde parou quando `ok` e falso."""

    pmib: str
    ok: bool
    etapa: str = ""
    motivo: str = ""
    pdm_antes: str = ""
    pdm_depois: str = ""
    trocou: bool = False
    repostas: int = 0
    convertidas: int = 0
    apagadas: int = 0
    retrato: str = ""
    falhas: tuple[str, ...] = ()
    nao_voltaram: tuple[Pendencia, ...] = ()
    em_branco: tuple[str, ...] = ()
    linhas: tuple[str, ...] = field(default=())

    def relatorio(self) -> list[str]:
        cabeca = f"{self.pmib}: " + ("ok" if self.ok else f"PAROU em {self.etapa}")
        if self.motivo:
            cabeca += f" ({self.motivo})"
        return [cabeca, *[f"   {x}" for x in self.linhas]]


# =============================================================================
# Uma ficha
# =============================================================================
def corrigir_ficha(portal, pmib, pdm_novo, callback_log=None,
                   callback_pause=None, apagar_vazias=True) -> ResultadoDaFicha:
    """Corrige o PDM de UMA ficha, reaproveitando o que der.

    `pdm_novo` pode ser o texto completo ou só o código. Só o código é o modo
    **"atualizar a revisão"**: o combo do portal oferece a vigente.

    `callback_pause`, quando dado, é chamado antes do SALVAR final -- é o
    costume do `tech_specs`, que preenche e deixa a pessoa conferir. A
    política é da tela; o serviço só oferece o gancho.
    """
    _log = _log_de(callback_log)
    _log(f"   {pmib}: abrindo.")

    if not portal.pesquisar_e_abrir(pmib):
        _log(f"   [Erro] {pmib}: nao abri a ficha. Nao mexi em nada.")
        return ResultadoDaFicha(pmib, False, "abrir", "a ficha nao abriu")

    # 1. FOTOGRAFAR. Antes de qualquer coisa, e com a ficha ainda intacta.
    antigas = _ler_a_tabela(portal, callback_log)
    com_valor = [c for c in antigas if not c.esta_vazia]
    _log(f"   {pmib}: {len(antigas)} caracteristica(s) na tela, "
         f"{len(com_valor)} com valor.")

    # 2. GRAVAR o retrato. A regra 1: sem rede, nao salta.
    foto = retrato.Retrato(pmib=str(pmib), pdm_antigo=operacoes.pdm_atual(portal),
                           pdm_novo=str(pdm_novo), caracteristicas=tuple(antigas))
    try:
        caminho = str(retrato.gravar(foto))
    except Exception as erro:  # noqa: BLE001 -- e a rede; sem ela nao se salta
        _log(f"   [Erro] {pmib}: nao consegui gravar o retrato "
             f"({type(erro).__name__}: {erro}). NAO troquei o PDM: trocar sem "
             f"o retrato gravado destruiria as caracteristicas sem volta.")
        return ResultadoDaFicha(pmib, False, "retrato", str(erro))
    _log(f"   {pmib}: retrato em {caminho}")

    # 3. TROCAR.
    troca = operacoes.trocar_pdm(portal, pdm_novo, callback_log)
    if not troca.ok:
        return ResultadoDaFicha(pmib, False, "troca", troca.motivo,
                                pdm_antes=troca.pdm_antes,
                                pdm_depois=troca.pdm_depois,
                                trocou=troca.trocou, retrato=caminho)

    if not troca.trocou:
        # A ficha ja estava na revisao vigente. As caracteristicas nunca foram
        # apagadas: nao ha o que repor, e apagar as vazias de uma ficha que nao
        # se mexeu seria mexer nela sem motivo.
        _log(f"   {pmib}: nada a fazer, o PDM ja e o vigente.")
        return ResultadoDaFicha(pmib, True, retrato=caminho, trocou=False,
                                pdm_antes=troca.pdm_antes,
                                pdm_depois=troca.pdm_depois,
                                linhas=("PDM ja era o vigente; ficha intacta.",))

    # 4 a 6: RELER, CASAR, REPOR e APAGAR -- o mesmo trecho que o modo
    # "so repor" roda sozinho.
    return _repor_e_apagar(portal, foto, caminho, callback_log=callback_log,
                           callback_pause=callback_pause,
                           apagar_vazias=apagar_vazias, troca=troca)


def _repor_e_apagar(portal, foto, caminho, callback_log=None,
                    callback_pause=None, apagar_vazias=True,
                    troca=None) -> ResultadoDaFicha:
    """Lê a tabela ATUAL, casa com o retrato, repõe e apaga as que sobraram.

    É a segunda metade de `corrigir_ficha` e o corpo inteiro de
    `repor_do_retrato`: depois da troca, e na retomada, o trabalho é o mesmo.
    A única diferença é que aqui o PDM já está onde tem de estar.
    """
    _log = _log_de(callback_log)
    pmib = foto.pmib
    com_valor = [c for c in foto.caracteristicas if not c.esta_vazia]
    antes = getattr(troca, "pdm_antes", "") if troca else foto.pdm_antigo
    depois = getattr(troca, "pdm_depois", "") if troca else ""

    novas = _ler_a_tabela(portal, callback_log)
    plano = casar(foto, novas)
    for linha in plano.relatorio():
        _log(f"   {linha}")

    # Recusa 4: o retrato tinha valor e nenhum voltou.
    if com_valor and not plano.escritas:
        _log(f"   [Erro] {pmib}: o retrato tinha {len(com_valor)} "
             f"caracteristica(s) com valor e NENHUMA casou com a tabela nova. "
             f"Isso nao parece ficha sem nada a reaproveitar, parece leitura "
             f"quebrada. NAO escrevi e NAO apaguei nada; o retrato esta em "
             f"{caminho}.")
        return ResultadoDaFicha(
            pmib, False, "casamento",
            "nenhuma das caracteristicas do retrato casou (leitura suspeita)",
            pdm_antes=antes, pdm_depois=depois, trocou=bool(troca),
            retrato=caminho, nao_voltaram=plano.nao_casou,
            linhas=tuple(plano.relatorio()))

    repostas, convertidas, falhas = _repor(portal, plano, callback_log)

    if callback_pause:
        callback_pause(pmib)

    # ⚠️ O RETORNO DO SALVAR IMPORTA, e ignorar era um defeito de verdade: sem
    # confirmacao, os valores estao na TELA e nao no servidor -- e a exclusao
    # das linhas em branco, que vem logo depois, chega ao servidor na hora.
    # A ficha terminaria com as linhas apagadas e a reposicao perdida, que e
    # exatamente o "pior do que estava" que este modulo existe para impedir.
    salvou = portal.salvar_e_confirmar(NOME_DA_ABA_CARACTERISTICAS, callback_log)
    if salvou is False:
        falhas = list(falhas) + ["(o portal nao confirmou o salvamento)"]
        _log(f"   [Erro] {pmib}: preenchi as caracteristicas e o portal nao "
             f"confirmou o salvamento. NAO apaguei nada. O retrato continua em "
             f"{caminho}: da para retomar com 'so repor'.")

    em_branco = tuple(f"{c.codigo}-{c.nome}" if c.codigo else c.nome
                      for c in plano.sem_valor)

    # Recusa 3: apagar so se nada falhou.
    apagadas = 0
    if falhas:
        _log(f"   [Aviso] {pmib}: {len(falhas)} caracteristica(s) nao entraram. "
             f"NAO apaguei as linhas em branco: com a reposicao incompleta, "
             f"apagar tiraria da tela justamente o que falta preencher.")
    elif apagar_vazias and plano.sem_valor:
        apagadas = _apagar_as_vazias(portal, plano, callback_log)
        if portal.salvar_e_confirmar(NOME_DA_ABA_CARACTERISTICAS,
                                     callback_log) is False:
            _log(f"   [Aviso] {pmib}: apaguei {apagadas} linha(s) em branco e o "
                 f"portal nao confirmou o salvamento. Confira a ficha.")

    ok = not falhas
    return ResultadoDaFicha(
        pmib, ok, "" if ok else "reposicao",
        "" if ok else f"{len(falhas)} problema(s) na reposicao",
        pdm_antes=antes, pdm_depois=depois, trocou=bool(troca),
        repostas=repostas, convertidas=convertidas, apagadas=apagadas,
        retrato=caminho, falhas=tuple(falhas), nao_voltaram=plano.nao_casou,
        em_branco=em_branco, linhas=tuple(plano.relatorio()))


def repor_do_retrato(portal, pmib, caminho=None, callback_log=None,
                     callback_pause=None, apagar_vazias=True) -> ResultadoDaFicha:
    r"""Retoma a reposição a partir de um retrato em disco, SEM tocar no PDM.

    É a razão de o retrato ir para o disco. Se o robô cair entre a troca e a
    reposição -- queda de rede, sessão expirada, a janela fechada --, a ficha
    fica vazia e o portal já não tem mais o original. Daqui ela volta.

    Sem `caminho`, pega o retrato MAIS NOVO da ficha: é o da tentativa que
    falhou (`retrato.listar` já devolve nessa ordem).

    ⚠️ NAO troca o PDM, de proposito. Nesse ponto ele ja esta onde tem de
    estar; trocar de novo apagaria as caracteristicas outra vez -- e o segundo
    retrato seria o da ficha VAZIA, sobrescrevendo o unico bom que restava.
    """
    _log = _log_de(callback_log)

    if caminho is None:
        achados = retrato.listar(pmib)
        if not achados:
            _log(f"   [Erro] {pmib}: nao ha retrato gravado para esta ficha.")
            return ResultadoDaFicha(str(pmib), False, "retrato",
                                    "nenhum retrato gravado para esta ficha")
        caminho = achados[0]

    try:
        foto = retrato.ler(caminho)
    except Exception as erro:  # noqa: BLE001
        _log(f"   [Erro] {pmib}: nao consegui ler o retrato {caminho} "
             f"({type(erro).__name__}: {erro}).")
        return ResultadoDaFicha(str(pmib), False, "retrato", str(erro),
                                retrato=str(caminho))

    _log(f"   {pmib}: repondo a partir de {caminho} "
         f"({len(foto.caracteristicas)} caracteristica(s) no retrato).")

    if not portal.pesquisar_e_abrir(pmib):
        _log(f"   [Erro] {pmib}: nao abri a ficha. Nao mexi em nada.")
        return ResultadoDaFicha(str(pmib), False, "abrir", "a ficha nao abriu",
                                retrato=str(caminho))

    return _repor_e_apagar(portal, foto, str(caminho), callback_log=callback_log,
                           callback_pause=callback_pause,
                           apagar_vazias=apagar_vazias, troca=None)


def _ler_a_tabela(portal, callback_log=None):
    """Abre a aba de características e lê a tabela inteira."""
    portal.safe_click(sel.XPATH_CARACTERISTICAS_ABA)
    time.sleep(PAUSA_CARGA_TABELA)
    return ler_tabela(portal.engine)


def _percorrer(portal):
    """Gera `(indice, seletor)` de cada linha, página por página.

    Índice SEMPRE avança: quem repõe não apaga nada, então a tabela não encolhe
    embaixo do laço. (Quem apaga tem o laço próprio, que não avança -- ver
    `_apagar_as_vazias`.)
    """
    for _pagina in range(MAX_PAGINAS):
        try:
            total = portal.engine.contar(XPATH_LINHAS)
        except Exception:  # noqa: BLE001
            return
        for indice in range(1, total + 1):
            yield indice, seletor_da_linha(indice)
        if not _avancar_pagina(portal):
            return


def _avancar_pagina(portal):
    from sigft.core.rpa.caracteristicas import XPATH_PROXIMA_PAGINA
    try:
        if not portal.engine.element_exists(XPATH_PROXIMA_PAGINA):
            return False
        if not portal.engine.esta_habilitado(XPATH_PROXIMA_PAGINA):
            return False
        portal.engine.click_raw(XPATH_PROXIMA_PAGINA)
        time.sleep(PAUSA_CARGA_TABELA)
        return True
    except Exception:  # noqa: BLE001
        return False


def _repor(portal, plano, callback_log=None):
    """Escreve o plano na tabela nova. Devolve `(repostas, convertidas, falhas)`.

    Caminha a tabela e pergunta, linha a linha, *"o que eu escrevo aqui?"* --
    pela MESMA `chave()` que o casamento usou. Endereçar pela ordem das duas
    listas daria certo até a primeira página que carregasse diferente.
    """
    _log = _log_de(callback_log)
    escritor = EscritorDeLinha(portal)
    por_chave = plano.por_chave()
    convertidas_por_chave = {chave_de(r) for r in plano.converter}

    repostas = convertidas = 0
    falhas = []
    vistas = set()

    for _indice, seletor in _percorrer(portal):
        try:
            linha = ler_linha(portal.engine, seletor)
        except Exception:  # noqa: BLE001
            continue
        alvo = por_chave.get(chave(linha))
        if alvo is None:
            continue

        vistas.add(chave(linha))
        if escritor.escrever(seletor, alvo, callback_log):
            repostas += 1
            if chave(linha) in convertidas_por_chave:
                convertidas += 1
        else:
            falhas.append(alvo.nome)

    # Uma linha planejada que o laço NUNCA viu é tão grave quanto uma recusa:
    # nos dois casos o valor não entrou, e só a contagem denuncia.
    nao_vistas = [r.nome for k, r in por_chave.items() if k not in vistas]
    if nao_vistas:
        _log(f"      [Aviso] {len(nao_vistas)} caracteristica(s) do plano nunca "
             f"apareceram na tela: {', '.join(nao_vistas)}")
        falhas.extend(nao_vistas)

    return repostas, convertidas, falhas


def chave_de(reposicao):
    """A chave de uma `Reposicao`, pela mesma regra das características."""
    from sigft.core.rpa.caracteristicas import Caracteristica
    return chave(Caracteristica(codigo=reposicao.codigo, nome=reposicao.nome,
                                tipo=reposicao.tipo))


def _quantas_linhas(portal):
    try:
        return portal.engine.contar(XPATH_LINHAS)
    except Exception:  # noqa: BLE001
        return 0


def _apagar_as_vazias(portal, plano, callback_log=None):
    """Apaga as linhas que ficaram em branco. Devolve quantas.

    ⚠️ O INDICE NAO AVANCA quando a linha e apagada: a de baixo sobe para o
    lugar dela. Avancar sempre pularia uma linha a cada exclusao, e metade das
    vazias sobreviveria. E a licao de `limpar_caracteristicas`.

    ⚠️ E CADA LINHA E RELIDA antes de apagar. A lista veio do plano, feita
    ANTES da reposicao; apagar por ela sem conferir apagaria uma linha que
    acabou de receber valor.
    """
    _log = _log_de(callback_log)
    alvos = {chave(c) for c in plano.sem_valor}
    apagadas = 0

    for _pagina in range(MAX_PAGINAS):
        indice = 1
        while True:
            if indice > _quantas_linhas(portal):
                break
            seletor = seletor_da_linha(indice)
            try:
                linha = ler_linha(portal.engine, seletor)
            except Exception:  # noqa: BLE001
                indice += 1
                continue

            if chave(linha) not in alvos or not linha.esta_vazia:
                indice += 1
                continue

            antes = _quantas_linhas(portal)
            if portal.excluir_linha_com_confirmacao(seletor):
                # ⚠️ "APAGUEI" NAO E PROVA DE QUE SUMIU, e aqui isso nao e
                # zelo: o indice so NAO avanca porque a linha de baixo subiu
                # para o lugar desta. Se a exclusao mentir -- devolver `True`
                # com a tabela intacta --, o laco tenta a mesma linha para
                # sempre, e o app trava sem mensagem nenhuma. Conferir a
                # contagem custa uma chamada e transforma trava em aviso.
                if _quantas_linhas(portal) < antes:
                    apagadas += 1
                    continue  # a linha de baixo subiu para ca.
                _log(f"      [Aviso] o portal disse que apagou "
                     f"{linha.nome!r}, mas a tabela continua com {antes} "
                     f"linha(s). Sigo para a proxima.")
                indice += 1
                continue
            _log(f"      [Aviso] nao consegui apagar a linha em branco "
                 f"{linha.nome!r}.")
            indice += 1

        if not _avancar_pagina(portal):
            break

    _log(f"      {apagadas} linha(s) em branco apagada(s).")
    return apagadas


# =============================================================================
# O lote
# =============================================================================
def corrigir_lote(portal, fichas, callback_log=None, callback_pause=None,
                  callback_progress=None, apagar_vazias=True):
    """Corrige uma lista de `(pmib, pdm_novo)`. Devolve um resultado por ficha.

    Uma ficha que falha NAO derruba as outras: com 25 numa rodada, parar tudo
    na primeira obrigaria a refazer as que ja tinham dado certo.
    """
    _log = _log_de(callback_log)
    fichas = list(fichas or ())
    resultados = []

    for posicao, (pmib, pdm_novo) in enumerate(fichas, start=1):
        if getattr(portal, "deve_parar", None) and portal.deve_parar():
            _log("Parada pedida pelo usuario. O que ja foi corrigido esta "
                 "salvo; o resto nao foi tocado.")
            break
        if callback_progress:
            callback_progress(posicao, len(fichas), item=pmib)
        try:
            resultados.append(corrigir_ficha(
                portal, pmib, pdm_novo, callback_log=callback_log,
                callback_pause=callback_pause, apagar_vazias=apagar_vazias))
        except Exception as erro:  # noqa: BLE001 -- uma ficha nao leva o lote
            _log(f"   [Erro] {pmib}: {type(erro).__name__}: {erro}")
            resultados.append(ResultadoDaFicha(str(pmib), False, "excecao",
                                               f"{type(erro).__name__}: {erro}"))
    return resultados


def relatorio_do_lote(resultados) -> list[str]:
    """O relatório da rodada: uma linha por ficha, e o detalhe embaixo.

    Sai sempre com cabeçalho, mesmo com zero fichas: um relatório vazio num
    arquivo de saída se confunde com relatório que não rodou.
    """
    resultados = list(resultados or ())
    certas = [r for r in resultados if r.ok]
    linhas = [
        f"Correcao de PDM: {len(certas)} de {len(resultados)} ficha(s) ok.",
        f"Repostas: {sum(r.repostas for r in resultados)} | "
        f"convertidas: {sum(r.convertidas for r in resultados)} | "
        f"apagadas em branco: {sum(r.apagadas for r in resultados)}",
        "",
    ]
    for r in resultados:
        linhas.extend(r.relatorio())
        if r.em_branco:
            linhas.append(f"   Ficaram em branco: {', '.join(r.em_branco)}")
        if r.retrato:
            linhas.append(f"   Retrato: {r.retrato}")
        linhas.append("")
    return linhas
