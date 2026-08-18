r"""
Ficha duplicada — escrita na ficha ALVO (CP 6.3).

A metade que MEXE no portal. Três seções, e a ordem importa pouco entre elas,
mas muito dentro de cada uma:

  1. **fabricante + referência** — inclui a regra do sufixo `'D`, a mais
     delicada do módulo: quem decide quando parar é o PORTAL, não o código;
  2. **características técnicas** — apaga tudo menos `CODIGO PMIB`, que recebe
     o código da ficha original;
  3. **fornecedor** — referência fixa vinda do `_STATUS_PMIB`; vazio ⇒ pula.

Reconstruído direto no motor NOVO, a pedido do usuário em 2026-08-17: *"o
ficha duplicada podemos fazer direto em Playwright, pois o de antes não
funcionava muito bem"*. Não há uma linha de Selenium aqui -- tudo passa por
`RPAEngine`/`PMIBPortal`, e é o que permite trocar de motor sem tocar neste
arquivo.

As REGRAS (o que fazer) estão em `duplicadas_spec.py`, sem I/O e testadas em
isolamento. Aqui só a MECÂNICA (como fazer na tela).
"""
from __future__ import annotations

import time

from sigft.core.rpa import seletores_duplicada as sel
from sigft.services import duplicadas_spec as spec

# Pausas. Cada uma existe porque o portal é assíncrono e não avisa quando
# terminou; os valores vêm do módulo antigo, que roda contra o portal real.
PAUSA_CARGA_TABELA = 3.0
PAUSA_PAGINACAO = 2.0
PAUSA_APOS_DIGITAR = 0.6

# Teto de páginas da tabela de características. Não veio do usuário: é decisão
# de engenharia, do mesmo tipo do teto de tentativas da referência. O laço do
# módulo antigo é `while True` e depende de o botão "próxima página" ficar
# desabilitado no fim -- se ele NÃO ficar (mudança de portal, botão sempre
# habilitado), o robô pagina para sempre, apagando o que encontrar. Um teto
# transforma um travamento infinito em uma mensagem de erro.
MAX_PAGINAS_CARACTERISTICAS = 50


class ResultadoDaSecao:
    """O que aconteceu numa seção, para o log e para o resumo do lote.

    Classe e não tupla porque estes campos são lidos em três lugares e um
    `[0]`/`[1]` trocado aqui vira relatório errado -- que é pior do que
    relatório nenhum, porque parece certo.
    """

    def __init__(self, nome, ok, detalhe="", pendente=False):
        self.nome = nome
        self.ok = ok
        self.detalhe = detalhe
        # Preenchido só por `escolher_fabricante`: o id do campo de Referência
        # que NASCEU quando o fabricante foi escolhido. É o que `escrever_
        # referencia` usa para não ter de adivinhar a linha.
        self.id_do_campo_de_referencia = ""
        # `pendente` separa "TENTEI e não consegui" de "AINDA NÃO EXISTE".
        # Sem essa distinção, uma seção que o checkpoint ainda não implementou
        # faria TODA ficha aparecer como falha no resumo do lote -- e um resumo
        # que diz "0 de 15" toda vez para de ser lido, escondendo a falha de
        # verdade quando ela vier. Para a PLANILHA os dois casos são iguais: a
        # seção não está completa, então não recebe COMPLETO.
        self.pendente = pendente

    def __repr__(self):
        if self.pendente:
            estado = "pendente"
        else:
            estado = "ok" if self.ok else "FALHOU"
        return f"<{self.nome}: {estado} {self.detalhe}>".strip()


def _log_de(callback_log):
    def _log(mensagem):
        if callback_log:
            callback_log(mensagem)
    return _log


# O fornecedor é FIXO e é a própria empresa: "no campo do fornecedor, GE
# ENERGIAS RENOVÁVEIS, como o fornecedor é a gente, que é sempre fixo (tipo
# intermediador)". Serve para DISTINGUIR os dois combos da seção -- ver
# `escolher_fabricante`.
FORNECEDOR_FIXO = "GE ENERGIAS RENOVÁVEIS"


def _confirmar_escrita(portal, seletor, esperado, nome_do_campo, callback_log=None):
    """Releu o campo e ele tem o que escrevemos? (read-back do CP 6.3)

    `engine.fill` ENGOLE a falha por contrato (`except Exception: pass`), então
    sem reler não há como distinguir "escreveu" de "não escreveu": as duas
    coisas são silenciosas e a tela parece igual. O plano pede read-back neste
    checkpoint justamente por isso, e a primeira versão deste módulo não fazia.
    """
    _log = _log_de(callback_log)
    try:
        lido = (portal.engine.get_value(seletor) or "").strip()
    except Exception as erro:  # noqa: BLE001 -- campo pode nem existir
        _log(f"      [Erro] Não consegui reler {nome_do_campo}: "
             f"{type(erro).__name__}: {erro}")
        return False

    if lido == str(esperado).strip():
        return True

    _log(f"      [Erro] {nome_do_campo}: escrevi {esperado!r} e o campo ficou "
         f"com {lido!r}.")
    return False


def texto_do_aviso_de_colisao(portal):
    """Texto do bloco de aviso de referência repetida — `""` se não há aviso.

    ⚠️ A pergunta é "este bloco tem CONTEÚDO?", **não** "este bloco existe?".
    O `div#…CoincidenceReference` fica no DOM o tempo todo, vazio, e só ganha
    texto quando há colisão -- dá para ver isso no próprio HTML que o usuário
    inspecionou, colhido numa ficha sem colisão nenhuma.

    A primeira versão perguntou "existe?" e o resultado foi exatamente o que se
    espera: **as 21 tentativas de referência foram recusadas**, incluindo a
    primeira, numa ficha que provavelmente aceitaria o código cru. A
    documentação deste projeto já dizia a frase certa ("a pergunta vira 'este
    bloco tem conteúdo?'") -- eu implementei a outra.
    """
    if not portal.engine.element_exists(sel.XPATH_REFERENCIA_AVISO_COLISAO):
        return ""
    try:
        return " ".join((portal.engine.texto(sel.XPATH_REFERENCIA_AVISO_COLISAO) or "").split())
    except Exception:  # noqa: BLE001
        return ""


# ===========================================================================
# 1. Fabricante e referência
# ===========================================================================
def escolher_fabricante(portal, nome_fabricante, callback_log=None):
    """Abre o combo de fabricante, filtra por texto e escolhe a opção.

    Por que digitar em vez de percorrer a lista: o combo é um `virtual-select`
    (renderiza só o que está na viewport), então "achar a opção rolando" é caro
    e frágil. O usuário mesmo indicou o caminho: *"esse aqui é melhor por
    digitando texto, que daí filtra"*.
    """
    _log = _log_de(callback_log)
    if not nome_fabricante:
        _log("      Fabricante não informado na ficha original -- pulando.")
        return ResultadoDaSecao("fabricante", False, "sem nome na origem")

    seletor_toggle = achar_combo_do_fabricante(portal, callback_log)
    if seletor_toggle is None:
        return ResultadoDaSecao("fabricante", False, "combo ambíguo na tela")

    # FOTO DE ANTES. O campo de Referência do fabricante só nasce quando o
    # fabricante é escolhido, então o que aparecer entre esta linha e a de
    # baixo é dele -- e é assim que a linha certa deixa de ser adivinhação.
    antes = set(ids_dos_campos_de_referencia(portal))

    portal.safe_click(seletor_toggle)
    busca = sel.XPATH_BUSCA_POR_PLACEHOLDER.format(
        texto=_literal(sel.PLACEHOLDER_COMBO_FABRICANTE))
    if not portal.engine.element_exists(busca):
        # A caixa de busca do dropdown ABERTO é a única na tela; se o
        # placeholder não bater, cai no seletor genérico em vez de travar.
        busca = sel.XPATH_FABRICANTE_BUSCA
    portal.safe_fill(busca, nome_fabricante)
    time.sleep(PAUSA_APOS_DIGITAR)

    alvo = sel.XPATH_FABRICANTE_OPCAO.format(texto=_literal(nome_fabricante))
    if not portal.engine.element_exists(alvo):
        # Não clicar em "a primeira opção que sobrou" é deliberado: o filtro
        # textual pode deixar uma opção PARECIDA, e escolher fabricante errado
        # é exatamente o erro que não dá sintoma nenhum na tela.
        _log(f"      [Erro] Fabricante {nome_fabricante!r} não apareceu no combo "
             f"depois de filtrar. Nada foi selecionado.")
        return ResultadoDaSecao("fabricante", False, "não encontrado no combo")

    portal.safe_click(alvo)
    time.sleep(PAUSA_APOS_DIGITAR)

    # FOTO DE DEPOIS.
    novos = [i for i in ids_dos_campos_de_referencia(portal) if i not in antes]
    resultado = ResultadoDaSecao("fabricante", True, nome_fabricante)
    if len(novos) == 1:
        resultado.id_do_campo_de_referencia = novos[0]
        _log(f"      Fabricante: {nome_fabricante} (campo de referência: {novos[0]})")
    else:
        # Zero: o campo não apareceu (ou já existia, numa ficha reprocessada).
        # Mais de um: a tela renderizou coisa demais e não dá para saber qual.
        # Nos dois casos, escrever seria chute -- e `escrever_referencia`
        # sabe recusar quando não recebe o alvo.
        resultado.id_do_campo_de_referencia = ""
        _log(f"      Fabricante: {nome_fabricante} "
             f"([Aviso] {len(novos)} campos de referência novos após a escolha; "
             f"esperava 1)")
    return resultado


def ids_dos_campos_de_referencia(portal):
    """Ids dos campos de Referência que existem na tela AGORA.

    Serve para o "antes e depois" de `escolher_fabricante`: o campo de
    Referência do fabricante **só é renderizado quando o fabricante é
    escolhido** (*"daí quando seleciona uma caixa do dropdown aparece o campo
    de referência à direita"*). Então a pergunta "qual dos campos é o certo?",
    que não tinha resposta boa pelo DOM, vira "qual apareceu agora?", que tem.
    """
    total = portal.engine.contar(sel.XPATH_REFERENCIA_INPUT)
    ids = []
    for posicao in range(1, total + 1):
        try:
            ids.append(portal.engine.atributo(
                f"({sel.XPATH_REFERENCIA_INPUT})[{posicao}]", "id") or "")
        except Exception:  # noqa: BLE001
            ids.append("")
    return [i for i in ids if i]


def prefixo_do_bloco(id_do_campo):
    """`"b10-b11-b4-Input_TextVar"` -> `"b10-b11-b4-"`.

    O campo de Referência e o "+" da mesma linha compartilham esse prefixo (o
    caminho do bloco no OutSystems). O prefixo é GERADO e não pode ser escrito
    no código, mas pode ser lido em tempo de execução -- é o que amarra os dois
    sem depender da estrutura de `<div>` em volta, que não conhecemos.
    """
    texto = str(id_do_campo or "")
    if not texto.endswith(sel.SUFIXO_ID_REFERENCIA):
        return ""
    return texto[: -len(sel.SUFIXO_ID_REFERENCIA)]


def achar_combo_do_fabricante(portal, callback_log=None):
    """Seletor do combo do FABRICANTE, ou `None` se não der para ter certeza.

    ⚠️ CONSERTO DE 2026-08-17, relatado pelo usuário na primeira sessão real:
    *"ele entrou no campo de fabricantes, mas tentou preencher o errado, o campo
    que é da GE"*. `XPATH_FABRICANTE_TOGGLE` casa **qualquer**
    `.vscomp-toggle-button` da página, e a seção tem mais de um -- XPath devolve
    o primeiro em ordem de documento, que não é necessariamente o do fabricante.

    O que distingue os dois é informação que o usuário já deu: o fornecedor é
    **fixo** e é a própria empresa (`FORNECEDOR_FIXO`). Então o combo do
    fabricante é o que NÃO está preenchido com ela.

    Devolver `None` em vez de "chutar o primeiro" é a decisão central aqui:
    escrever no combo errado põe dado errado numa ficha real e **não dá sintoma
    nenhum na tela** -- o robô seguiria dizendo que deu certo. Não escrever
    custa uma pendência manual, que aparece no log.
    """
    _log = _log_de(callback_log)

    # ESTRATÉGIA 1 -- o combo se identifica sozinho enquanto está vazio:
    # `data-tooltip="Selecione um fabricante"`. É direto, e vale exatamente no
    # momento em que precisamos: antes de escolher.
    por_placeholder = sel.XPATH_COMBO_POR_PLACEHOLDER.format(
        texto=_literal(sel.PLACEHOLDER_COMBO_FABRICANTE))
    quantos = portal.engine.contar(por_placeholder)
    if quantos == 1:
        return f"({por_placeholder})[1]"
    if quantos > 1:
        _log(f"      [Aviso] {quantos} combos dizem "
             f"'{sel.PLACEHOLDER_COMBO_FABRICANTE}' -- caindo para a eliminação.")

    # ESTRATÉGIA 2 -- eliminação. Serve quando a ficha já tem um fabricante
    # escolhido (aí o tooltip virou o NOME dele e a estratégia 1 não casa).
    total = portal.engine.contar(sel.XPATH_FABRICANTE_TOGGLE)

    if total == 0:
        _log("      [Erro] Nenhum combo de fabricante/fornecedor na tela.")
        return None
    if total == 1:
        return f"({sel.XPATH_FABRICANTE_TOGGLE})[1]"

    candidatos = []
    for posicao in range(1, total + 1):
        seletor = f"({sel.XPATH_FABRICANTE_TOGGLE})[{posicao}]"
        try:
            conteudo = " ".join((portal.engine.texto(seletor) or "").split())
        except Exception:  # noqa: BLE001
            conteudo = ""
        e_o_fornecedor = _sem_acento(FORNECEDOR_FIXO) in _sem_acento(conteudo)
        _log(f"      [Combo {posicao}/{total}] {conteudo or '(vazio)'}"
             f"{'  <- fornecedor fixo' if e_o_fornecedor else ''}")
        if not e_o_fornecedor:
            candidatos.append(seletor)

    if len(candidatos) == 1:
        return candidatos[0]

    _log(f"      [Erro] Não consigo distinguir o combo do FABRICANTE: {total} combos "
         f"na tela e {len(candidatos)} não são o fornecedor fixo "
         f"({FORNECEDOR_FIXO}). NÃO escrevi nada -- escolher errado poria dado "
         f"errado na ficha sem nenhum sintoma. Preencha à mão.")
    return None


def _sem_acento(texto):
    from unicodedata import normalize
    return normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().upper()


def _literal(texto):
    """Literal XPath com aspas que não colidem (XPath 1.0 não tem escape)."""
    texto = str(texto)
    if "'" not in texto:
        return f"'{texto}'"
    if '"' not in texto:
        return f'"{texto}"'
    return "concat('" + "', \"'\", '".join(texto.split("'")) + "')"


def escrever_referencia(portal, codigo_material, callback_log=None, id_do_campo=""):
    """A regra do `'D`: tenta o código cru, depois `'D1`, `'D2`… até o portal
    aceitar.

    > *"Se aparecer 'a referência já existe', devemos colocar o partnumber dele
    > 2904616 com o 'D1 no final (…) até ele conseguir."*

    Quem decide se parou é o PORTAL. O código não tem como saber de antemão
    qual sufixo passa, então a sequência é consumida uma a uma, **conferindo a
    tela entre elas**.

    O aviso de colisão é conferido DUAS vezes -- depois de digitar e depois de
    clicar no "+" -- e isso é deliberado: não observamos em qual dos dois
    momentos o portal valida. Conferir nos dois é correto se for em qualquer um
    deles; conferir só no que eu chutasse seria correto só se eu chutasse
    certo, e o erro seria gravar a MESMA referência de outra ficha.
    """
    _log = _log_de(callback_log)
    candidatos = spec.sequencia_de_referencias(codigo_material)
    if not candidatos:
        _log("      [Erro] Sem CÓDIGO DO MATERIAL -- nenhuma referência a escrever.")
        return ResultadoDaSecao("referencia", False, "sem código do material")

    # QUAL campo, e QUAL "+". O id vem de `escolher_fabricante`, que sabe qual
    # campo NASCEU quando o fabricante foi escolhido -- a linha certa deixou de
    # ser adivinhação. O "+" da mesma linha sai do mesmo prefixo de bloco.
    if id_do_campo:
        seletor_input = sel.XPATH_POR_ID.format(id=_literal(id_do_campo))
        prefixo = prefixo_do_bloco(id_do_campo)
        seletor_mais = (sel.XPATH_ADICIONAR_DO_BLOCO.format(prefixo=_literal(prefixo))
                        if prefixo else sel.XPATH_REFERENCIA_ADICIONAR)
    else:
        seletor_input = sel.XPATH_REFERENCIA_INPUT
        seletor_mais = sel.XPATH_REFERENCIA_ADICIONAR
        total_de_campos = portal.engine.contar(sel.XPATH_REFERENCIA_INPUT)
        if total_de_campos == 0:
            _log("      [Erro] Nenhum campo de Referência na tela.")
            return ResultadoDaSecao("referencia", False, "campo não encontrado")
        if total_de_campos > 1:
            # Sem o id, o XPath sem índice pega o primeiro em ordem de
            # documento -- foi assim que a referência do fabricante foi parar
            # na linha da GE. Recusar custa uma pendência; escrever custa uma
            # ficha errada que ninguém vê.
            _log(f"      [Erro] {total_de_campos} campos de Referência na tela e o "
                 f"fabricante não indicou qual é o dele. NÃO escrevi nada -- "
                 f"preencha à mão.")
            return ResultadoDaSecao("referencia", False,
                                    f"{total_de_campos} campos ambíguos")

    avisos_vistos = []
    for tentativa, referencia in enumerate(candidatos, start=1):
        portal.safe_fill(seletor_input, referencia)
        time.sleep(PAUSA_APOS_DIGITAR)

        if not _confirmar_escrita(portal, seletor_input, referencia,
                                  "campo de Referência", callback_log):
            # Não adianta tentar mais 20 sufixos num campo que não recebe o que
            # se digita -- é outro problema, e insistir esconderia ele.
            return ResultadoDaSecao("referencia", False, "campo não aceitou o texto")

        aviso = texto_do_aviso_de_colisao(portal)
        if aviso:
            avisos_vistos.append(aviso)
            continue

        portal.safe_click(seletor_mais)
        time.sleep(PAUSA_APOS_DIGITAR)
        aviso = texto_do_aviso_de_colisao(portal)
        if aviso:
            avisos_vistos.append(aviso)
            continue

        if tentativa > 1:
            _log(f"      Referência: {referencia} (as {tentativa - 1} anteriores "
                 f"já existiam no portal)")
        else:
            _log(f"      Referência: {referencia}")
        return ResultadoDaSecao("referencia", True, referencia)

    # "Apenas notificar que não foi possível colocar a referência" -- palavra
    # do usuário. NÃO aborta a ficha nem desfaz o que já foi preenchido: vira
    # pendência manual, como os campos rejeitados de `tech_specs`.
    _log(f"      [Erro] Não consegui gravar a referência: as "
         f"{len(candidatos)} tentativas ({candidatos[0]} … {candidatos[-1]}) "
         f"foram recusadas. Preencha à mão antes de salvar.")
    if avisos_vistos:
        # TODAS recusadas é resultado suspeito -- inclusive a primeira, que na
        # maioria das fichas passa. Mostrar o texto que o portal exibiu é o que
        # permite decidir, em uma olhada, se era mesmo colisão ou se estamos
        # lendo como colisão um aviso que é outra coisa.
        _log(f"      [Diagnóstico] O portal exibiu: {avisos_vistos[0]!r}. Se isso "
             f"não é 'a referência já existe', o robô está lendo o aviso errado.")
    return ResultadoDaSecao("referencia", False, "todas as tentativas recusadas")


# ===========================================================================
# 2. Características técnicas — apagar tudo menos o CÓDIGO PMIB
# ===========================================================================
def _e_a_linha_do_codigo_pmib(texto_da_descricao):
    """A descrição da linha é a característica que se PRESERVA?

    Comparação sem acento e em caixa alta porque o portal escreve "CODIGO PMIB"
    e "CÓDIGO PMIB" em telas diferentes -- o módulo antigo testava as duas
    grafias na mão, o que é o mesmo que normalizar, só que sujeito a esquecer a
    terceira.
    """
    from unicodedata import normalize
    limpo = normalize("NFKD", str(texto_da_descricao or "")).encode("ascii", "ignore").decode()
    return spec.CARACTERISTICA_UNICA_DUPLICADA in limpo.upper()


def limpar_caracteristicas(portal, pmib_original, callback_log=None):
    """Apaga todas as características menos `CODIGO PMIB`, que recebe o código
    da ficha ORIGINAL.

    A tabela é paginada e ENCOLHE a cada exclusão: apagada a linha `i`, a de
    baixo sobe para o índice `i`. Por isso o índice só avança quando a linha é
    PRESERVADA -- avançar sempre pularia uma linha a cada exclusão, e metade
    das características sobreviveria à purga.
    """
    _log = _log_de(callback_log)
    portal.safe_click(sel.XPATH_CARACTERISTICAS_ABA)
    time.sleep(PAUSA_CARGA_TABELA)

    apagadas = 0
    preenchidas = 0
    falhas_de_escrita = []
    for pagina in range(1, MAX_PAGINAS_CARACTERISTICAS + 1):
        indice = 1
        while indice <= portal.engine.contar(sel.XPATH_CARACTERISTICAS_LINHAS):
            linha = f"({sel.XPATH_CARACTERISTICAS_LINHAS})[{indice}]"
            descricao = portal.engine.texto(linha + sel.XPATH_REL_CARACTERISTICA_DESCRICAO[1:])

            if _e_a_linha_do_codigo_pmib(descricao):
                seletor_valor = linha + sel.XPATH_REL_CARACTERISTICA_VALOR_PT[1:]
                seletor_descricao = linha + sel.XPATH_REL_CARACTERISTICA_DESCRICAO[1:]
                portal.safe_fill(seletor_valor, pmib_original)

                # CLIQUE FORA PARA DISPARAR O onBlur -- e é o conserto do
                # relato "eu até vi ele colocando mas não conseguiu salvar".
                #
                # Nem o `fill` do Playwright nem o `send_keys` do Selenium
                # disparam `change`: esse evento nasce do BLUR, no navegador
                # real. O OutSystems liga a variável do servidor ao `change`,
                # então sem o blur o texto fica na caixa e o servidor nunca
                # soube dele -- o SALVAR salva o valor ANTIGO, sem erro nenhum.
                # O módulo antigo já fazia isso, com o comentário "Clica fora
                # para disparar o evento onBlur"; eu não portei a linha.
                #
                # `click_nativo` e não `click_raw`: o clique por JavaScript
                # dispara o evento de clique mas NÃO executa os passos de foco
                # do navegador -- ou seja, não tira o foco do textarea, que é
                # justamente a única coisa que precisamos aqui. É a mesma
                # distinção que quebrou o campo de Contrato no CP 5.4.
                portal.engine.click_nativo(seletor_descricao)
                time.sleep(PAUSA_APOS_DIGITAR)

                if not _confirmar_escrita(portal, seletor_valor, pmib_original,
                                          "valor do CÓDIGO PMIB", callback_log):
                    falhas_de_escrita.append(indice)
                else:
                    preenchidas += 1
                    _log(f"      Mantida: {' '.join(descricao.split())} = {pmib_original}")
                indice += 1  # preservada: a linha continua onde estava
                continue

            if portal.excluir_linha_com_confirmacao(linha):
                apagadas += 1
                # NÃO incrementa o índice: a linha de baixo subiu para cá.
                continue

            # Falha ao excluir precisa AVANÇAR, senão o laço tenta a mesma
            # linha para sempre. O módulo antigo marcava sucesso sem conferir
            # e nunca caía aqui -- e era assim que uma exclusão que falhou
            # passava por bem-sucedida.
            _log(f"      [Aviso] Não consegui excluir a linha {indice} "
                 f"({' '.join(descricao.split())[:60]}). Confira à mão.")
            indice += 1

        if not portal.engine.element_exists(sel.XPATH_CARACTERISTICAS_PROXIMA_PAGINA):
            break
        if not portal.engine.esta_habilitado(sel.XPATH_CARACTERISTICAS_PROXIMA_PAGINA):
            break
        portal.engine.click_raw(sel.XPATH_CARACTERISTICAS_PROXIMA_PAGINA)
        time.sleep(PAUSA_PAGINACAO)
    else:
        _log(f"      [Erro] A tabela passou de {MAX_PAGINAS_CARACTERISTICAS} "
             f"páginas. Parei por segurança -- confira a ficha à mão.")
        return ResultadoDaSecao("caracteristicas", False, "paginação sem fim")

    # O retorno do SALVAR não pode ser ignorado: `clicar_salvar_visivel`
    # devolve `False` quando nenhum botão SALVAR estava visível e habilitado --
    # que é exatamente o sintoma de "o portal não registrou a mudança". Sem
    # olhar, a seção fechava como sucesso com a ficha inalterada.
    salvou = portal.clicar_salvar_visivel("Características Técnicas")
    _log(f"      Características: {apagadas} apagada(s), {preenchidas} preservada(s).")

    if falhas_de_escrita:
        _log(f"      [Erro] O valor do CÓDIGO PMIB não ficou gravado em "
             f"{len(falhas_de_escrita)} linha(s). Preencha à mão antes de salvar.")
        return ResultadoDaSecao("caracteristicas", False, "valor não gravado")

    if not salvou:
        _log("      [Erro] Não achei botão SALVAR visível e habilitado nesta aba. "
             "Se o portal não habilitou o botão, é sinal de que ele não registrou "
             "nenhuma mudança -- confira a ficha antes de seguir.")
        return ResultadoDaSecao("caracteristicas", False, "não salvou")

    if preenchidas == 0:
        # Sem a linha do CÓDIGO PMIB a ficha duplicada perde a ÚNICA
        # característica que ela precisa ter -- e a tela não reclama.
        _log("      [Erro] Nenhuma linha de CODIGO PMIB encontrada. A ficha "
             "ficou sem a característica da duplicação.")
        return ResultadoDaSecao("caracteristicas", False, "CODIGO PMIB ausente")

    return ResultadoDaSecao(
        "caracteristicas", True, f"{apagadas} apagadas, {preenchidas} preservada")


# ===========================================================================
# 3. Fornecedor — a mesma mecânica, do outro lado da seção
# ===========================================================================
# "No campo do fornecedor, GE ENERGIAS RENOVÁVEIS, como o fornecedor é a gente,
# que é sempre fixo (tipo intermediador), nós colocamos a informação que está
# no STATUS PMIB na coluna CÓDIGO CMI ou por vezes CÓDIGO GE. Se estiver vazio,
# só ignorar."
#
# O fornecedor em si não se ESCOLHE no sentido de decidir -- é sempre o mesmo.
# Mas a tela pede que ele seja selecionado no combo, e é a seleção que faz
# nascer o campo de Referência dele. Mesma mecânica do fabricante, mesmo
# discriminador (o placeholder), mesma garantia: se não der para saber em qual
# campo escrever, NÃO escreve.

def escrever_referencia_do_fornecedor(portal, referencia, callback_log=None):
    """Seleciona o fornecedor fixo e escreve a referência dele.

    Vazio ⇒ pula sem erro e sem pendência ("se estiver vazio, só ignorar").
    """
    _log = _log_de(callback_log)
    if not str(referencia or "").strip():
        _log("      Referência do fornecedor vazia -- pulando, como combinado.")
        return ResultadoDaSecao("fornecedor", True, "vazia (ignorada)")

    combo = sel.XPATH_COMBO_POR_PLACEHOLDER.format(
        texto=_literal(sel.PLACEHOLDER_COMBO_FORNECEDOR))
    if portal.engine.contar(combo) != 1:
        # Combo já preenchido (o placeholder some quando há valor) ou mais de
        # um na tela. Nos dois casos, o campo de Referência não vai nascer e
        # não há como saber qual é o dele.
        _log(f"      [Erro] Não achei o combo do fornecedor vazio na tela "
             f"({portal.engine.contar(combo)} encontrados). NÃO escrevi nada -- "
             f"preencha a referência {referencia!r} à mão.")
        return ResultadoDaSecao("fornecedor", False, "combo do fornecedor não localizado")

    antes = set(ids_dos_campos_de_referencia(portal))
    portal.safe_click(f"({combo})[1]")

    busca = sel.XPATH_BUSCA_POR_PLACEHOLDER.format(
        texto=_literal(sel.PLACEHOLDER_COMBO_FORNECEDOR))
    if not portal.engine.element_exists(busca):
        busca = sel.XPATH_FABRICANTE_BUSCA
    portal.safe_fill(busca, FORNECEDOR_FIXO)
    time.sleep(PAUSA_APOS_DIGITAR)

    opcao = sel.XPATH_FABRICANTE_OPCAO.format(texto=_literal(FORNECEDOR_FIXO))
    if not portal.engine.element_exists(opcao):
        _log(f"      [Erro] {FORNECEDOR_FIXO!r} não apareceu no combo do fornecedor. "
             f"Nada foi selecionado.")
        return ResultadoDaSecao("fornecedor", False, "fornecedor fixo não encontrado")

    portal.safe_click(opcao)
    time.sleep(PAUSA_APOS_DIGITAR)

    novos = [i for i in ids_dos_campos_de_referencia(portal) if i not in antes]
    if len(novos) != 1:
        _log(f"      [Erro] {len(novos)} campos de referência novos após escolher o "
             f"fornecedor (esperava 1). NÃO escrevi -- preencha {referencia!r} à mão.")
        return ResultadoDaSecao("fornecedor", False, "campo do fornecedor não identificado")

    resultado = escrever_referencia(portal, referencia, callback_log, id_do_campo=novos[0])
    # `escrever_referencia` devolve a seção com o nome "referencia"; aqui ela é
    # a do FORNECEDOR, e o nome é o que a planilha usa para decidir a coluna.
    resultado.nome = "fornecedor"
    return resultado
