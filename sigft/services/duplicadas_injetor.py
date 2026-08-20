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
        # A linha EXISTE nesta ficha? (2026-08-19) Nem toda ficha tem as três
        # linhas da seção: no print do usuário, a de Fornecedor é FIXA -- não
        # tem combo a escolher, e o campo de Referência dela é o do ícone ⓘ.
        # Sem esta distinção, "a ficha não tem essa linha" era reportado como
        # falha e o passo seguinte ainda tentava escrever nela, batendo na
        # ambiguidade de campos. Ausência não é falha.
        self.tem_linha = True

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
    return _escolher_no_combo(
        portal, "fabricante", nome_fabricante,
        achar_combo_do_fabricante(portal, callback_log),
        sel.PLACEHOLDER_COMBO_FABRICANTE, callback_log,
    )


def escolher_fornecedor(portal, nome_fornecedor, callback_log=None):
    """Abre o combo de FORNECEDOR, filtra por texto e escolhe a opção.

    ⚠️ ESTA FUNÇÃO NÃO EXISTIA, e a falta dela é o defeito que o usuário
    relatou em 2026-08-18: *"ele não está conseguindo nem colocar a referência
    correta do fornecedor correto, ele está fazendo no campo de fornecimento
    da GE"*.

    O combo do fornecedor estava mapeado (`PLACEHOLDER_COMBO_FORNECEDOR`,
    levantado do DOM em 2026-08-17) e **nunca era usado por ninguém**: o robô
    ia direto escrever no campo da linha fixa.

    ⚠️ QUANTAS LINHAS A SEÇÃO TEM DEPENDE DA FICHA -- corrigido em 2026-08-19,
    com o print da tela na mão. Não é constante, e supor que fosse é o que
    produziu os dois `[Erro]` da sessão real:

        Fabricante   combo -> Referência = CÓDIGO DO MATERIAL   (sempre existe)
        Fornecedor   combo -> Referência = CÓDIGO DO MATERIAL   (nem sempre)
        Linha FIXA   campo com ícone ⓘ   = CÓDIGO CMI / CÓDIGO GE

    Na 4500063671.1418 a do meio NÃO EXISTE: o fornecedor é texto fixo e a
    linha dele é a do ícone ⓘ. Quem decide é a TELA -- zero combos devolve
    `tem_linha=False`, e o robô não escreve numa linha que não está lá.

    Qual fornecedor escolher vem da FICHA ORIGINAL -- *"vem da ficha original,
    lendo qual fornecedor foi preenchido"*. Não é fixo (a leitura anterior, de
    que o fornecedor era sempre a própria empresa, confundia esta linha com a
    da GE Vernova).
    """
    _log = _log_de(callback_log)

    # ⚠️ ANTES DE PROCURAR O COMBO: esta ficha TEM a linha de fornecedor com
    # combo? No print de 2026-08-19 (ficha 4500063671.1418) não tem -- o bloco
    # "Adicionar Fornecedor / Referência" traz o fornecedor como TEXTO FIXO
    # ("GE ENERGIAS RENOVAVEIS LTDA") e um campo de Referência marcado com o
    # ícone ⓘ, que é justamente o que este módulo cataloga como "a linha da GE
    # Vernova". Ou seja: nessa ficha as duas são a MESMA linha.
    #
    # Zero combos não é erro: é uma seção de DUAS linhas em vez de três.
    # Tratar como erro custava caro -- a ficha saía "0 de 1" por causa de uma
    # linha que ela não tem, e o passo seguinte ainda tentava escrever,
    # caindo na ambiguidade de "2 campos de Referência na tela".
    quantos = portal.engine.contar(sel.XPATH_COMBO_POR_PLACEHOLDER.format(
        texto=_literal(sel.PLACEHOLDER_COMBO_FORNECEDOR)))
    if quantos == 0:
        _log("      Sem combo de fornecedor nesta ficha: a linha de Fornecedor é "
             "FIXA (a do ícone ⓘ) e recebe o CÓDIGO CMI/GE da planilha. "
             "Nada a escolher aqui.")
        resultado = ResultadoDaSecao("fornecedor", True, "linha fixa (sem combo)")
        resultado.tem_linha = False
        return resultado

    return _escolher_no_combo(
        portal, "fornecedor", nome_fornecedor,
        achar_combo_do_fornecedor(portal, callback_log),
        sel.PLACEHOLDER_COMBO_FORNECEDOR, callback_log,
    )


def _escolher_no_combo(portal, papel, nome, seletor_toggle, placeholder, callback_log=None):
    """Mecânica comum aos combos de fabricante e de fornecedor.

    São o MESMO widget (`virtual-select`) com a mesma sequência: abrir,
    digitar para filtrar, escolher a opção, e descobrir qual campo de
    Referência nasceu. O que difere entre os dois é só qual combo e qual
    placeholder -- por isso os dois entram aqui em vez de virarem duas cópias
    que envelhecem separadas.
    """
    _log = _log_de(callback_log)
    if not nome:
        _log(f"      {papel.capitalize()} não informado -- pulando.")
        return ResultadoDaSecao(papel, False, "sem nome na origem")

    if seletor_toggle is None:
        return ResultadoDaSecao(papel, False, "combo ambíguo na tela")

    # FOTO DE ANTES. O campo de Referência da linha só nasce quando a opção é
    # escolhida, então o que aparecer entre esta linha e a de baixo é dele --
    # e é assim que a linha certa deixa de ser adivinhação.
    antes = set(ids_dos_campos_de_referencia(portal))

    portal.safe_click(seletor_toggle)
    busca = sel.XPATH_BUSCA_POR_PLACEHOLDER.format(texto=_literal(placeholder))
    if not portal.engine.element_exists(busca):
        # A caixa de busca do dropdown ABERTO é a única na tela; se o
        # placeholder não bater, cai no seletor genérico em vez de travar.
        busca = sel.XPATH_FABRICANTE_BUSCA
    portal.safe_fill(busca, nome)
    time.sleep(PAUSA_APOS_DIGITAR)

    alvo = sel.XPATH_FABRICANTE_OPCAO.format(texto=_literal(nome))
    if not portal.engine.element_exists(alvo):
        # Não clicar em "a primeira opção que sobrou" é deliberado: o filtro
        # textual pode deixar uma opção PARECIDA, e escolher errado aqui é
        # exatamente o erro que não dá sintoma nenhum na tela.
        _log(f"      [Erro] {papel.capitalize()} {nome!r} não apareceu no combo "
             f"depois de filtrar. Nada foi selecionado.")
        return ResultadoDaSecao(papel, False, "não encontrado no combo")

    portal.safe_click(alvo)
    time.sleep(PAUSA_APOS_DIGITAR)

    # FOTO DE DEPOIS.
    novos = [i for i in ids_dos_campos_de_referencia(portal) if i not in antes]
    resultado = ResultadoDaSecao(papel, True, nome)
    if len(novos) == 1:
        resultado.id_do_campo_de_referencia = novos[0]
        _log(f"      {papel.capitalize()}: {nome} (campo de referência: {novos[0]})")
    else:
        # Zero: o campo não apareceu (ou já existia, numa ficha reprocessada).
        # Mais de um: a tela renderizou coisa demais e não dá para saber qual.
        # Nos dois casos, escrever seria chute -- e `escrever_referencia`
        # sabe recusar quando não recebe o alvo.
        resultado.id_do_campo_de_referencia = ""
        _log(f"      {papel.capitalize()}: {nome} "
             f"([Aviso] {len(novos)} campos de referência novos após a escolha; "
             f"esperava 1)")
    return resultado


def achar_combo_do_fornecedor(portal, callback_log=None):
    """Seletor do combo do FORNECEDOR, ou `None` se não der para ter certeza.

    Só a estratégia do placeholder (`data-tooltip` diz "fornecedor" enquanto o
    combo está vazio). A eliminação que `achar_combo_do_fabricante` usa como
    2ª estratégia NÃO serve aqui, e o motivo vale registrar: ela se apoia em
    "o outro combo é o fornecedor fixo, a própria empresa" -- premissa que a
    resposta do usuário de 2026-08-18 derrubou. O fornecedor varia (vem da
    ficha original); quem é fixo é a linha da GE Vernova, que sequer tem
    combo.

    Sem uma 2ª estratégia com evidência, esta função recusa. Pendência manual
    é barata; referência na linha errada não é -- e foi justamente o que
    aconteceu.
    """
    _log = _log_de(callback_log)
    por_placeholder = sel.XPATH_COMBO_POR_PLACEHOLDER.format(
        texto=_literal(sel.PLACEHOLDER_COMBO_FORNECEDOR))
    quantos = portal.engine.contar(por_placeholder)
    if quantos == 1:
        return f"({por_placeholder})[1]"
    if quantos == 0:
        _log(f"      [Erro] Nenhum combo diz '{sel.PLACEHOLDER_COMBO_FORNECEDOR}' na "
             f"tela. Pode ser que o fornecedor já esteja escolhido nesta ficha -- "
             f"nesse caso o tooltip virou o nome dele e não dá para reconhecê-lo "
             f"assim. NÃO escrevi nada.")
    else:
        _log(f"      [Erro] {quantos} combos dizem "
             f"'{sel.PLACEHOLDER_COMBO_FORNECEDOR}' -- não dá para saber qual é a "
             f"linha do fornecedor. NÃO escrevi nada.")
    return None


def ids_dos_campos_de_referencia(portal):
    """Ids dos campos de Referência que existem na tela AGORA.

    Serve para o "antes e depois" de `escolher_fabricante`: o campo de
    Referência do fabricante **só é renderizado quando o fabricante é
    escolhido** (*"daí quando seleciona uma caixa do dropdown aparece o campo
    de referência à direita"*). Então a pergunta "qual dos campos é o certo?",
    que não tinha resposta boa pelo DOM, vira "qual apareceu agora?", que tem.
    """
    seletor = sel.XPATH_REFERENCIA_INPUT_SEM_GE
    total = portal.engine.contar(seletor)
    ids = []
    for posicao in range(1, total + 1):
        try:
            ids.append(portal.engine.atributo(f"({seletor})[{posicao}]", "id") or "")
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


def _clicar_no_mais(portal, seletor_mais, callback_log=None):
    """Clica no "+" DIZENDO por que falhou, em vez de engolir.

    `safe_click` delega para `engine.click`, que engole a exceção por
    contrato -- e foi exatamente isso que transformou um "+" que não funcionou
    em log de sucesso na sessão de 2026-08-19. O caminho estrito não conserta
    o clique; conserta o SILÊNCIO, que é o que impedia diagnosticar.
    """
    _log = _log_de(callback_log)
    try:
        portal.engine.click_estrito(seletor_mais)
        return True
    except Exception as erro:  # noqa: BLE001 -- ver docstring
        _log(f"      [!] O '+' não aceitou o clique: {type(erro).__name__}: {erro}")
        return False


def linha_entrou_na_tabela(portal, seletor_input, referencia):
    """O "+" levou mesmo a linha para a tabela?

    A pergunta parece precisar do DOM da tabela e não precisa: o que prova o
    commit é o **formulário de adicionar largar o valor**. São dois desfechos,
    e os dois valem:

      - linha do FABRICANTE: o campo de Referência é renderizado ao escolher
        o fabricante e some quando a linha entra -- é a mecânica do "campo que
        nasce", ao contrário;
      - linha FIXA (fornecedor/GE): o campo continua na tela, mas esvazia.

    Se o valor digitado AINDA está lá, nada foi comitado. Foi o caso real: no
    passo seguinte o robô contou DOIS campos de Referência em vez de um,
    porque o do fabricante seguia na tela com "2904616" dentro.
    """
    # ⚠️ `valor_se_existir` e não `engine.get_value`, e aqui o motivo é
    # especialmente traiçoeiro: o campo SUMIR é o desfecho BOM desta função.
    # Com `get_value`, toda referência gravada com sucesso pagava o timeout
    # inteiro (20 s) esperando um elemento que a gente mesmo esperava não
    # achar. Não travava -- só ficava lento no caminho certo, que é pior de
    # diagnosticar: ninguém investiga o que está funcionando.
    atual = portal.valor_se_existir(seletor_input)
    if atual is None:
        return True                # o campo saiu da tela: a linha entrou
    return str(atual).strip() != str(referencia or "").strip()


def fotografar_bloco_da_linha(portal, seletor_mais, seletor_input,
                              nome_da_secao, log_auditoria=None):
    """Despeja no log de AUDITORIA o HTML do campo e do "+" desta linha.

    Só é chamada quando a linha não entrou -- ou seja, no único momento em que
    o HTML tem informação nova. Falha em silêncio de propósito: uma foto que
    não sai não pode derrubar a ficha, e o que ela documenta já está dito em
    texto no console.
    """
    if log_auditoria is None:
        return
    for titulo, seletor in ((f"{nome_da_secao}: campo de Referência", seletor_input),
                            (f"{nome_da_secao}: o '+'", seletor_mais)):
        try:
            html = portal.engine.html_do_elemento(seletor)
        except Exception:  # noqa: BLE001 -- ver docstring
            html = ""
        log_auditoria.bloco(titulo, html or f"(nada casou {seletor})")


def escrever_referencia(portal, codigo_material, callback_log=None, id_do_campo="",
                        nome_da_secao="referencia", log_auditoria=None):
    """A regra do `'D`: tenta o código cru, depois `'D1`, `'D2`… até o portal
    aceitar.

    > *"Se aparecer 'a referência já existe', devemos colocar o partnumber dele
    > 2904616 com o 'D1 no final (…) até ele conseguir."*

    `nome_da_secao` existe porque DUAS linhas da tela passam por aqui -- a do
    fabricante e a do fornecedor (2026-08-18) --, e ambas recebem o mesmo
    CÓDIGO DO MATERIAL. Com um nome fixo, o segundo resultado sobrescreveria o
    primeiro no placar da ficha e uma falha ficaria invisível.

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
        return ResultadoDaSecao(nome_da_secao, False, "sem código do material")

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
            return ResultadoDaSecao(nome_da_secao, False, "campo não encontrado")
        if total_de_campos > 1:
            # Sem o id, o XPath sem índice pega o primeiro em ordem de
            # documento -- foi assim que a referência do fabricante foi parar
            # na linha da GE. Recusar custa uma pendência; escrever custa uma
            # ficha errada que ninguém vê.
            _log(f"      [Erro] {total_de_campos} campos de Referência na tela e o "
                 f"fabricante não indicou qual é o dele. NÃO escrevi nada -- "
                 f"preencha à mão.")
            return ResultadoDaSecao(nome_da_secao, False,
                                    f"{total_de_campos} campos ambíguos")

    avisos_vistos = []
    for tentativa, referencia in enumerate(candidatos, start=1):
        portal.safe_fill(seletor_input, referencia)
        time.sleep(PAUSA_APOS_DIGITAR)

        if not _confirmar_escrita(portal, seletor_input, referencia,
                                  "campo de Referência", callback_log):
            # Não adianta tentar mais 20 sufixos num campo que não recebe o que
            # se digita -- é outro problema, e insistir esconderia ele.
            return ResultadoDaSecao(nome_da_secao, False, "campo não aceitou o texto")

        aviso = texto_do_aviso_de_colisao(portal)
        if aviso:
            avisos_vistos.append(aviso)
            continue

        clicou = _clicar_no_mais(portal, seletor_mais, callback_log)
        time.sleep(PAUSA_APOS_DIGITAR)
        aviso = texto_do_aviso_de_colisao(portal)
        if aviso:
            avisos_vistos.append(aviso)
            continue

        # ⚠️ A PROVA. Até 2026-08-19 bastava "cliquei e o portal não reclamou"
        # para reportar sucesso -- e o usuário só descobriu que a tabela estava
        # vazia ao abrir a ficha. Escrever no campo não é adicionar a linha.
        if not linha_entrou_na_tabela(portal, seletor_input, referencia):
            _log(f"      [Erro] A linha NÃO ENTROU na tabela: escrevi "
                 f"{referencia!r}, cliquei no '+' e o campo continua com o "
                 f"valor. Adicione à mão antes de salvar."
                 + ("" if clicou else " (o clique já havia falhado, acima)"))
            # O HTML do bloco vai para o ARQUIVO de auditoria (nunca para o
            # console). Sem ele, a próxima rodada devolve a mesma mensagem e a
            # pergunta "por que o '+' não comitou?" continua aberta -- e a
            # resposta só existe no DOM daquele instante.
            fotografar_bloco_da_linha(portal, seletor_mais, seletor_input,
                                      nome_da_secao, log_auditoria)
            return ResultadoDaSecao(nome_da_secao, False, "a linha não entrou")

        if tentativa > 1:
            _log(f"      Referência: {referencia} (as {tentativa - 1} anteriores "
                 f"já existiam no portal)")
        else:
            _log(f"      Referência: {referencia}")
        return ResultadoDaSecao(nome_da_secao, True, referencia)

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
    return ResultadoDaSecao(nome_da_secao, False, "todas as tentativas recusadas")


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


def selecionar_unidade_adimensional(portal, linha, callback_log=None):
    """Põe a unidade da linha em ADIMENSIONAL. `True` se conseguiu.

    *"…e colocar a unidade adimensional."* (usuário, 2026-08-20)

    ⚠️ NÃO SABEMOS O TEXTO EXATO DA OPÇÃO. `tech_specs` trabalha com o SÍMBOLO
    ("AD"), que é o que vem do Master de PDMs; o que o `<select>` do portal
    mostra pode ser "AD", "Adimensional", "(AD) Adimensional"… Em vez de
    chutar um e falhar em silêncio, tentamos os casamentos plausíveis e, se
    nenhum servir, **listamos as opções no log** -- que é o que permite acertar
    o texto na próxima rodada sem ninguém inspecionar a tela.
    """
    _log = _log_de(callback_log)
    seletor = linha + sel.XPATH_REL_CARACTERISTICA_UNIDADE[1:]
    try:
        if not portal.engine.contar(seletor):
            return False           # linha sem dropdown de unidade: normal
        opcoes = list(portal.engine.opcoes(seletor) or [])
    except Exception:  # noqa: BLE001
        return False

    escolhida = _opcao_adimensional(opcoes)
    if not escolhida:
        _log(f"      [Aviso] Não achei a unidade adimensional no dropdown. "
             f"Opções: {', '.join(o[:20] for o in opcoes[:8])}"
             f"{' …' if len(opcoes) > 8 else ''}. Ajuste à mão.")
        return False

    try:
        portal.engine.selecionar_por_texto(seletor, escolhida)
    except Exception as erro:  # noqa: BLE001
        _log(f"      [Aviso] Não consegui selecionar {escolhida!r} como unidade: "
             f"{type(erro).__name__}.")
        return False
    return True


def _opcao_adimensional(opcoes):
    """A opção que representa "sem unidade", entre as do dropdown."""
    simbolo = sel.SIMBOLO_ADIMENSIONAL.upper()
    limpas = [(o, _sem_acento(o)) for o in opcoes]
    for original, limpa in limpas:
        if limpa.strip() == simbolo:
            return original
    for original, limpa in limpas:
        if "ADIMENSIONAL" in limpa:
            return original
    for original, limpa in limpas:
        if f"({simbolo})" in limpa:
            return original
    return ""


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
                seletor_es = linha + sel.XPATH_REL_CARACTERISTICA_VALOR_ES[1:]
                seletor_descricao = linha + sel.XPATH_REL_CARACTERISTICA_DESCRICAO[1:]
                portal.safe_fill(seletor_valor, pmib_original)
                # ⚠️ O ESPANHOL TAMBÉM (2026-08-20). *"A 3626 - CODIGO PMIB
                # deve ser preenchida com a ficha original, tanto no campo de
                # espanhol quanto no de português."* Até aqui só o português
                # era preenchido -- e a ficha é bilíngue, então metade dela
                # saía vazia sem que nada reclamasse.
                if portal.engine.contar(seletor_es):
                    portal.safe_fill(seletor_es, pmib_original)
                selecionar_unidade_adimensional(portal, linha, callback_log)

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

    # ⚠️ `salvar_e_confirmar` e não `clicar_salvar_visivel`: o segundo devolve
    # `True` por ter ACHADO um botão e clicado nele, sem ler nada da tela
    # depois -- e a ficha tem um SALVAR por seção, então "cliquei" nem sequer
    # garante que foi o desta. O usuário viu o efeito disso em 2026-08-19:
    # *"ele não conseguiu salvar a seção de características técnicas"*, com o
    # log dizendo que tinha salvado. Agora só passa com o toast de sucesso NOVO
    # na tela.
    # `ancora`: o SALVAR DESTA seção, não o primeiro da tela. Sem ela, em
    # 2026-08-20 o robô gravou Informações Gerais cinco vezes seguidas
    # enquanto o log dizia "salvo" para as outras seções.
    salvou = portal.salvar_e_confirmar(
        "Características Técnicas", callback_log,
        ancora=sel.XPATH_CARACTERISTICAS_SECAO)
    _log(f"      Características: {apagadas} apagada(s), {preenchidas} preservada(s).")

    if falhas_de_escrita:
        _log(f"      [Erro] O valor do CÓDIGO PMIB não ficou gravado em "
             f"{len(falhas_de_escrita)} linha(s). Preencha à mão antes de salvar.")
        return ResultadoDaSecao("caracteristicas", False, "valor não gravado")

    if not salvou:
        _log("      [Erro] A seção de Características Técnicas NÃO foi confirmada "
             "pelo portal. O motivo está na linha acima (botão ausente ou toast "
             "que não veio) -- confira a ficha antes de seguir.")
        return ResultadoDaSecao("caracteristicas", False, "não salvou")

    if preenchidas == 0:
        # Sem a linha do CÓDIGO PMIB a ficha duplicada perde a ÚNICA
        # característica que ela precisa ter -- e a tela não reclama.
        _log("      [Erro] Nenhuma linha de CODIGO PMIB encontrada. A ficha "
             "ficou sem a característica da duplicação.")
        return ResultadoDaSecao("caracteristicas", False, "CODIGO PMIB ausente")

    # ⚠️ A CONFERÊNCIA DEPOIS DO SAVE (2026-08-19). *"Antes de sair de cada uma
    # das páginas, quero que você valide se de fato conseguiu colocar os
    # dados."*
    #
    # O toast prova que o portal ACEITOU o salvamento; não prova que a tabela
    # ficou como se queria. Uma exclusão que falhou, uma linha que volta na
    # recarga, uma página que o laço não visitou -- tudo isso convive com um
    # toast de sucesso. E a consequência é concreta: *"se tiver mais
    # características, estas devem ser excluídas, pois se não, não vai
    # conseguir salvar"*.
    sobraram = sobrou_caracteristica_alem_do_codigo(portal)
    if sobraram:
        _log(f"      [Erro] Depois de salvar, ainda sobraram {len(sobraram)} "
             f"característica(s) além do CÓDIGO PMIB: "
             f"{', '.join(sobraram[:5])}"
             f"{' …' if len(sobraram) > 5 else ''}. Apague à mão -- com elas "
             f"a ficha não fecha.")
        return ResultadoDaSecao("caracteristicas", False,
                                f"{len(sobraram)} sobraram após salvar")

    return ResultadoDaSecao(
        "caracteristicas", True, f"{apagadas} apagadas, {preenchidas} preservada")


def sobrou_caracteristica_alem_do_codigo(portal):
    """Descrições que ainda estão na tabela e NÃO são a do CÓDIGO PMIB.

    Relê a tela depois do salvamento -- é a única leitura que enxerga o que o
    portal realmente gravou, porque a seção recarrega ao gravar. Lista vazia é
    o resultado bom.

    Não pagina: depois da purga a tabela tem uma linha. Se tiver mais de uma
    página, a primeira já basta para reprovar -- e reprovar é o objetivo.
    """
    sobraram = []
    try:
        total = portal.engine.contar(sel.XPATH_CARACTERISTICAS_LINHAS)
    except Exception:  # noqa: BLE001 -- ler a tela não derruba a ficha
        return []
    for indice in range(1, (total or 0) + 1):
        linha = f"({sel.XPATH_CARACTERISTICAS_LINHAS})[{indice}]"
        # `texto_se_existir`: não esperar o timeout por uma célula ausente
        # (ver `PMIBPortal.texto_se_existir` e o travamento de 2026-08-20).
        descricao = portal.texto_se_existir(
            linha + sel.XPATH_REL_CARACTERISTICA_DESCRICAO[1:])
        if descricao and not _e_a_linha_do_codigo_pmib(descricao):
            sobraram.append(" ".join(descricao.split())[:40])
    return sobraram


# ===========================================================================
# 3. A referência da GE Vernova — a TERCEIRA linha da seção
# ===========================================================================
# "O CÓDIGO CMI / CÓDIGO GE deve ser preenchido somente se tiver no
# _STATUS_PMIB, e deve ser preenchido no campo do fornecimento da GE, que é
# fixo." (usuário, 2026-08-18)
#
# ⚠️ ESTA FUNÇÃO SE CHAMAVA `escrever_referencia_do_fornecedor` E RECEBIA O
# VALOR ERRADO -- daí o defeito relatado: *"ele está fazendo no campo de
# fornecimento da GE"*. O nome antigo era a causa, não um detalhe dela: chamar
# de "fornecedor" esta linha fazia o valor do fornecedor parecer que ia para o
# lugar certo.
#
# ⚠️ E O QUE ESTA LINHA É, afinal, depende da ficha (2026-08-19). No print da
# 4500063671.1418 ela É a linha de Fornecedor -- o bloco "Adicionar Fornecedor
# / Referência" traz o fornecedor como texto fixo e o campo de Referência com
# o ícone ⓘ. Noutra ficha pode haver um combo de fornecedor ANTES dela.
#
# O que NÃO depende da ficha: **o valor aqui vem sempre da planilha**. *"Não
# devemos copiar e colar [a referência da ficha original], pois esse número
# muda quando estamos trabalhando para outro sistema; essa informação deve vir
# exclusivamente da planilha _STATUS_PMIB"* (usuário, 2026-08-19).

def escrever_referencia_da_ge(portal, referencia, callback_log=None,
                              log_auditoria=None):
    """Escreve a referência da GE Vernova (`CÓDIGO CMI` / `CÓDIGO GE`).

    *"Quando a coluna CÓDIGO CMI ou CÓDIGO GE estiver preenchida no
    _STATUS_PMIB vale a pena preencher esse campo, com o valor da coluna."*

    Vazio ⇒ pula sem erro e sem pendência ("se estiver vazio, só ignorar").

    ⚠️ A PRIMEIRA VERSÃO DESTA FUNÇÃO ESTAVA ERRADA, e o erro foi meu: eu a
    escrevi por SIMETRIA com o fabricante -- selecionar a GE num combo e
    escrever no campo que nascesse. O HTML da tela mostra que **não há combo**
    nessa linha: o campo é fixo e já está lá. Simetria é hipótese, não
    evidência, e neste módulo hipótese não checada já custou uma sessão.
    """
    _log = _log_de(callback_log)
    if not str(referencia or "").strip():
        _log("      Referência da GE Vernova vazia -- pulando, como combinado.")
        return ResultadoDaSecao("ge_vernova", True, "vazia (ignorada)")

    quantos = portal.engine.contar(sel.XPATH_REFERENCIA_GE_INPUT)
    if quantos != 1:
        # O discriminador é o ícone de informação no container. Zero ou mais de
        # um significa que a tela não é a que conhecemos -- e escrever no palpite
        # poria a referência da GE numa linha de fabricante.
        _log(f"      [Erro] Achei {quantos} campos de Referência com ícone de "
             f"informação (esperava 1, o da GE Vernova). NÃO escrevi -- "
             f"preencha {referencia!r} à mão.")
        return ResultadoDaSecao("ge_vernova", False,
                                f"{quantos} campos com o ícone (esperava 1)")

    id_do_campo = ""
    try:
        id_do_campo = portal.engine.atributo(
            f"({sel.XPATH_REFERENCIA_GE_INPUT})[1]", "id") or ""
    except Exception:  # noqa: BLE001
        pass

    resultado = escrever_referencia(portal, referencia, callback_log,
                                    id_do_campo=id_do_campo,
                                    log_auditoria=log_auditoria)
    # `escrever_referencia` nomeia a seção como "referencia"; aqui ela é a da
    # GE Vernova, e o nome é o que a planilha usa para decidir a coluna.
    resultado.nome = "ge_vernova"
    return resultado
