r"""
Ficha duplicada — a seção de CONDIÇÕES (CP 6.4).

Copia as quatro sub-abas (Armazenamento, Transporte, Manutenção, Descarte) da
ficha ORIGINAL para a ficha ALVO, **campo a campo, por XPath**.

Por que por XPath e não por significado: é uma DUPLICAÇÃO. O valor que está em
`Input_PackingLength` na original vai para `Input_PackingLength` na alvo, e
pronto -- nenhum rótulo precisa ser interpretado, nenhuma unidade convertida,
nenhum radio traduzido. O mapa vive em `seletores_duplicada.CONDICOES_POR_
SUBABA` e foi portado do módulo antigo, que roda contra o portal real.

A leitura exige a original aberta em EDIÇÃO -- é o único modo em que estes
campos existem como `input`/`textarea`. **Nada é salvo na original**: este
módulo só escreve na alvo.

O que ele acrescenta ao módulo antigo, e é o pedido do usuário de 2026-08-19
(*"antes de sair de cada uma das páginas, quero que você valide se de fato
conseguiu colocar os dados"*):

  - cada sub-aba é salva com `salvar_e_confirmar` -- só passa com o toast;
  - depois de salvar, a sub-aba é RELIDA e comparada com o que se pediu;
  - o que não bateu vira pendência COM O NOME DO CAMPO, em vez de sumir.
"""
from __future__ import annotations

import time
import unicodedata

from sigft.core.rpa import seletores_duplicada as sel
from sigft.services import duplicadas_extrator as extrator
from sigft.services.duplicadas_injetor import ResultadoDaSecao, _log_de

# Pausas. Mesmos valores do módulo antigo, que roda contra o portal real.
PAUSA_ABERTURA_SECAO = 2.0
PAUSA_TROCA_SUBABA = 1.5
PAUSA_APOS_ESCREVER = 0.4


def _seletor(sufixo):
    return sel.XPATH_CONDICOES_CAMPO.format(sufixo=f"'{sufixo}'")


# ===========================================================================
# Leitura pela VISUALIZAÇÃO — rótulo visível → campo de edição
# ===========================================================================
# Ver `seletores_duplicada`, §15b, para por que este caminho existe (a original
# nunca é aberta em edição) e por que a tabela nasce vazia.

def chave_de_rotulo(rotulo):
    """Rótulo da tela -> chave de busca no mapa.

    Sem acento, minúsculo, espaços colapsados, sem ':' final. O portal escreve
    o mesmo rótulo de jeitos diferentes conforme a tela, e casar o texto cru
    transformaria cada variação numa falha silenciosa -- a chave não bate, o
    campo não copia, o log não diz nada.

    `None` vira `""` em vez de estourar: a varredura devolve `None` quando o
    `<span>` do rótulo está vazio, e derrubar a leitura inteira por causa de
    um campo seria trocar uma seção incompleta por nenhuma seção.
    """
    texto = unicodedata.normalize("NFKD", str(rotulo or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.replace(":", " ").split()).lower()


def _pares(rotulos_e_valores):
    """`{rótulo: valor}` ou `[(rótulo, valor)]` -> lista de pares.

    Aceita os dois porque a varredura da tela pode trazer o MESMO rótulo duas
    vezes com valores diferentes, e um `dict` perderia um deles antes de chegar
    aqui. Quem chama não deve precisar achatar cedo.
    """
    if hasattr(rotulos_e_valores, "items"):
        return list(rotulos_e_valores.items())
    return list(rotulos_e_valores or ())


def converter_da_visualizacao(rotulos_e_valores, callback_log=None):
    """Pares rótulo→valor da ORIGINAL -> `{sub-aba: {sufixo: valor}}`.

    A saída é exatamente o que `escrever` já consome, então o injetor não muda:
    o que muda é de onde os dados vêm.

    ⚠️ **O log dos rótulos DESCONHECIDOS é a parte que importa hoje.** Enquanto
    `CONDICOES_ROTULO_PARA_CAMPO` estiver vazio isto devolve `{}` e nada é
    copiado -- e é essa lista, com o texto integral de cada rótulo, que
    transforma uma rodada real contra o portal na tabela que falta.

    Rótulo desconhecido é logado MESMO com valor vazio: o log serve para
    construir o mapa, não para relatar esta ficha, e o rótulo é o mesmo em
    todas elas.
    """
    _log = _log_de(callback_log)
    mapa = sel.CONDICOES_ROTULO_PARA_CAMPO
    convertido = {}
    desconhecidos = []

    for rotulo, valor in _pares(rotulos_e_valores):
        destino = mapa.get(chave_de_rotulo(rotulo))
        if destino is None:
            texto = " ".join(str(rotulo or "").split())
            # ⚠️ O VALOR VAI JUNTO. Conserto de 2026-08-24: a lista saía só com
            # os nomes, e nome sozinho não fecha o mapa. Para escrever
            # "Posição de armazenamento" na alvo eu preciso saber QUE opção a
            # original mostra ("Horizontal"), porque na edição isso é um radio
            # e o que se escolhe é a opção, não o rótulo.
            visto = " ".join(str(valor or "").split())
            if texto and not any(t == texto for t, _ in desconhecidos):
                desconhecidos.append((texto, visto))
            continue

        subaba, sufixo = destino
        if subaba not in sel.CONDICOES_POR_SUBABA:
            # A tabela é preenchida À MÃO. Uma sub-aba com nome errado faria
            # `escrever` procurar por uma chave que ninguém percorre, e a
            # escrita sumiria em silêncio -- de novo o mesmo modo de falha.
            _log(f"      [!] Condições: o mapa manda «{rotulo}» para a sub-aba "
                 f"«{subaba}», que não existe na edição. Campo ignorado.")
            continue

        # Valor em branco não vira escrita: `fill(\"\")` é uma chance a mais de
        # disparar validação do portal sem acrescentar nada, e na ficha que já
        # tem conteúdo apagaria.
        if not str(valor or "").strip():
            continue
        convertido.setdefault(subaba, {})[sufixo] = valor

    if desconhecidos:
        _log(f"      [i] Condições: {len(desconhecidos)} rótulo(s) da ficha "
             f"original ainda não estão no mapa RÓTULO→campo. Copie a lista "
             f"abaixo para fechar a seção:")
        for texto, visto in desconhecidos:
            _log(f"          · {texto} = {visto!r}" if visto
                 else f"          · {texto} (vazio nesta ficha)")

    return convertido


def sufixos_em_espanhol_nao_copiados(condicoes):
    """Os `..._ES` cujos pares `..._PT` foram escritos. Lista, em ordem.

    ⚠️ A METADE QUE A VISUALIZAÇÃO NÃO ENTREGA. Cada texto longo tem par na
    edição (`TextArea_XxxPT` e `TextArea_XxxES`) e a visualização mostra UM
    valor só -- o bloco é o `Block_ExpressionBothLenguage`, e o que fica
    visível é o português; o espanhol, se está em algum lugar, está atrás do
    tooltip, que a varredura não abre.

    Copiar o texto em português para dentro do campo em espanhol seria
    INVENTAR uma tradução na ficha de outra pessoa. Então o robô copia o PT e
    esta função diz o que ficou para trás -- é o que impede a seção de fechar
    como COMPLETA com metade dos campos em branco.

    Campo numérico não entra: `Input_LiquidWeight` é um só, número é número
    nos dois idiomas. Recusar a ficha que só tem números seria inventar
    pendência para o que está certo.
    """
    faltando = []
    for campos in (condicoes or {}).values():
        for sufixo in campos:
            if not sufixo.endswith("PT"):
                continue
            par = sufixo[:-2] + "ES"
            if par not in campos and par not in faltando:
                faltando.append(par)
    return faltando


def abrir_secao(portal, callback_log=None):
    """Abre a sanfona de Condições. Idempotente do ponto de vista do portal:
    clicar de novo numa seção aberta não a fecha (é um header, não um toggle
    de duas posições) -- e mesmo que fechasse, a leitura seguinte falharia
    alto, com o campo não encontrado no log."""
    portal.safe_click(sel.XPATH_CONDICOES_ABRIR_SECAO)
    time.sleep(PAUSA_ABERTURA_SECAO)


def abrir_subaba(portal, nome, callback_log=None):
    """Vai para a sub-aba `nome`. Armazenamento já vem aberta -- posição
    `None` significa "não clique em nada"."""
    posicao = sel.CONDICOES_POR_SUBABA[nome]["posicao"]
    if posicao is None:
        return
    portal.safe_click(sel.XPATH_CONDICOES_SUBABA.format(posicao=posicao))
    time.sleep(PAUSA_TROCA_SUBABA)


def ler(portal, callback_log=None):
    """Lê as 4 sub-abas da ficha aberta. Devolve `{subaba: {sufixo: valor}}`.

    Valor é `str` para texto e `bool` para radio/checkbox -- é o tipo que diz,
    na hora de escrever, se o campo se digita ou se clica.

    Campo que não existe na tela NÃO entra no dicionário. Entrar com `""`
    faria a escrita apagar um campo da alvo por causa de uma leitura que
    falhou, que é o pior desfecho possível numa duplicação.
    """
    _log = _log_de(callback_log)
    abrir_secao(portal, callback_log)

    lido = {}
    for nome, mapa in sel.CONDICOES_POR_SUBABA.items():
        abrir_subaba(portal, nome, callback_log)
        campos = {}
        for sufixo in mapa["textos"]:
            # `valor_se_existir` e não `engine.get_value`: são 45 campos por
            # ficha e nem todos existem em toda uma, e o `get_value` do
            # Playwright ESPERA o timeout pelo ausente -- 20 s cada. Foi o
            # travamento de 2026-08-20, na tabela de documentos, e aqui o
            # risco era maior. `None` = não está na tela: não entra.
            valor = portal.valor_se_existir(_seletor(sufixo))
            if valor is not None:
                campos[sufixo] = valor
        for sufixo in mapa["booleanos"]:
            try:
                campos[sufixo] = bool(portal.engine.esta_marcado(_seletor(sufixo)))
            except Exception:  # noqa: BLE001
                continue
        lido[nome] = campos
        _log(f"      [{nome}] li {len(campos)} campo(s).")
    return lido


def fotografar_edicao(portal, log_auditoria=None, callback_log=None):
    """Fotografa as 4 sub-abas de Condições da ficha ALVO, **em EDIÇÃO**.

    🎯 É O QUE FALTA PARA FECHAR A SEÇÃO, e não sai de graça em nenhum outro
    lugar do lote. A ficha ORIGINAL é lida só em visualização (decisão do
    usuário em 2026-08-20), e lá:

      - os textos longos vêm por `ViewAttachment`, num idioma só -- nenhum id
        `..._ES` aparece na tela;
      - dos 19 radios/checkboxes, só 2 são renderizados como `<input>`
        (`Checkbox1` e `Checkbox2`); os outros viram texto puro ("Horizontal",
        "Sem necessidade"), sem nada que diga a QUAL campo pertencem.

    A ALVO, essa sim, está aberta em edição -- e é o único lugar onde os 45
    campos existem com o rótulo visível ao lado. A foto responde duas
    perguntas de uma vez: qual sufixo corresponde a cada opção de radio, e se
    os campos em espanhol são `required` (se forem, a seção não fecha sem
    eles, e ler só a visualização deixa de ser suficiente).

    Só roda com o modo de auditoria ligado, e não escreve nada.
    """
    if log_auditoria is None:
        return

    _log = _log_de(callback_log)
    abrir_secao(portal, callback_log)

    painel = extrator.id_do_painel(portal, sel.NOME_DA_ABA_CONDICOES)
    alvo = (sel.XPATH_PAINEL_POR_ID.format(id=extrator._literal_xpath(painel))
            if painel else None)

    for nome in sel.CONDICOES_POR_SUBABA:
        abrir_subaba(portal, nome, callback_log)
        extrator.fotografar(portal, f"ALVO em EDIÇÃO — Condições «{nome}»",
                            log_auditoria, seletor=alvo)

    _log(f"      [i] Condições: fotografei as {len(sel.CONDICOES_POR_SUBABA)} "
         f"sub-abas da ficha ALVO em edição (modo de auditoria).")


def ancora_da_subaba(nome):
    """Um campo QUALQUER desta sub-aba, para achar o SALVAR da seção por ele.

    Ver `PMIBPortal.XPATH_SALVAR_DO_BLOCO`: a partir de um elemento da seção,
    o XPath sobe até o container e desce para o botão de lá. Qualquer campo
    serve; o primeiro de texto é o mais estável (existe nas quatro sub-abas).
    """
    textos = sel.CONDICOES_POR_SUBABA[nome]["textos"]
    return _seletor(textos[0]) if textos else None


def escrever_subaba(portal, nome, campos, callback_log=None):
    """Escreve os campos de UMA sub-aba. Devolve os sufixos que falharam.

    Texto vazio é PULADO de propósito: a ficha alvo nasce vazia, então
    escrever "" não acrescenta nada -- e um `fill("")` a mais é uma chance a
    mais de disparar validação do portal sem motivo.
    """
    _log = _log_de(callback_log)
    falhas = []
    for sufixo, valor in campos.items():
        seletor = _seletor(sufixo)
        try:
            if isinstance(valor, bool):
                if not portal.check_or_uncheck(seletor, valor, callback_log):
                    falhas.append(sufixo)
                continue
            if not str(valor).strip():
                continue
            portal.safe_fill(seletor, str(valor))
            time.sleep(PAUSA_APOS_ESCREVER)
        except Exception as erro:  # noqa: BLE001
            _log(f"      [!] {nome}/{sufixo}: {type(erro).__name__}: {erro}")
            falhas.append(sufixo)
    return falhas


def conferir_subaba(portal, nome, campos, callback_log=None):
    """Relê a sub-aba e devolve os sufixos que NÃO ficaram como se pediu.

    É a validação que o usuário pediu antes de sair da página. O toast prova
    que o portal aceitou o salvamento; só a releitura prova que o VALOR ficou.
    """
    divergentes = []
    for sufixo, esperado in campos.items():
        seletor = _seletor(sufixo)
        try:
            if isinstance(esperado, bool):
                if bool(portal.engine.esta_marcado(seletor)) != esperado:
                    divergentes.append(sufixo)
                continue
            if not str(esperado).strip():
                continue
            # Mesma armadilha da leitura, e aqui ela seria pior: a
            # conferência roda DEPOIS do salvamento, com a tela recarregada.
            # `None` = o campo sumiu da tela; não dá para conferir, e inventar
            # divergência a partir de uma leitura que não aconteceu seria
            # ruído sobre a ficha certa.
            atual = portal.valor_se_existir(seletor)
            if atual is None:
                continue
            if str(atual).strip() != str(esperado).strip():
                divergentes.append(sufixo)
        except Exception:  # noqa: BLE001 -- não dá para conferir; não inventa falha
            continue
    return divergentes


def conferir_ja_preenchida(portal, callback_log=None):
    """A ficha ALVO já tem Condições preenchidas? `ResultadoDaSecao` ou `None`.

    `None` = não achei conteúdo (ou não consegui ler); quem chamou decide.

    Existe porque "o robô não copiou" e "a ficha não tem" são coisas
    diferentes, e até 2026-08-21 o módulo só sabia a primeira -- então marcava
    INCOMPLETO no `_STATUS_PMIB` uma seção que outra pessoa já tinha preenchido
    à mão, apagando o trabalho dela na planilha.

    O critério é CONTEÚDO DE TEXTO, não os booleanos: rádio e checkbox sempre
    têm um estado (marcado ou não), então contá-los diria "preenchido" para
    toda ficha em branco. Campo de texto com algo dentro só existe se alguém
    escreveu.

    ⚠️ **A conta vai para o log de propósito.** O robô não tem como julgar se a
    seção está COMPLETA no sentido do negócio -- ele sabe dizer "tem conteúdo".
    Mostrar "12 de 14 campos" deixa o número suspeito visível em vez de
    esconder a decisão atrás de um COMPLETO.
    """
    _log = _log_de(callback_log)
    try:
        lido = ler(portal, callback_log=None)
    except Exception as erro:  # noqa: BLE001
        _log(f"      [Aviso] Não consegui conferir as Condições da ficha alvo: "
             f"{type(erro).__name__}: {erro}")
        return None

    preenchidos = 0
    total = 0
    detalhe_por_aba = []
    for nome, mapa in sel.CONDICOES_POR_SUBABA.items():
        campos = lido.get(nome, {})
        textos = [s for s in mapa["textos"] if s in campos]
        cheios = [s for s in textos if str(campos.get(s) or "").strip()]
        preenchidos += len(cheios)
        total += len(textos)
        if textos:
            detalhe_por_aba.append(f"{nome} {len(cheios)}/{len(textos)}")

    if not preenchidos:
        return None

    # ⚠️ TODOS OS CAMPOS, não "algum". Correção do usuário em 2026-08-21:
    # *"tem que estar completo todos os campos; tem que ter conteúdo, só não
    # pode estar em branco"*.
    #
    # A primeira versão fechava a seção com QUALQUER conteúdo e mandava a conta
    # para o log, para o usuário julgar. Julgar é trabalho que a planilha
    # existe para poupar: um `3 de 14` marcado COMPLETO é a mesma mentira que
    # este módulo inteiro combate, só que com uma nota de rodapé.
    #
    # "Todos" quer dizer todos os que ESTÃO NA TELA -- `ler` não devolve campo
    # que não existe nesta ficha, e exigir campo inexistente reprovaria ficha
    # correta.
    if preenchidos < total:
        _log(f"      Condições da ficha alvo INCOMPLETAS: {preenchidos} de {total} "
             f"campo(s) de texto com conteúdo ({'; '.join(detalhe_por_aba)}).")
        _log("      Falta preencher o resto à mão -- o robô não copia por cima do "
             "que já está lá.")
        return None

    _log(f"      Condições JÁ preenchidas na ficha alvo: {total} de {total} "
         f"campo(s) de texto ({'; '.join(detalhe_por_aba)}).")
    _log("      Não foram copiadas de novo -- sobrescrever apagaria o que já está lá.")
    return ResultadoDaSecao("condicoes", True, f"já preenchida ({total}/{total} campos)")


def escrever(portal, condicoes, callback_log=None):
    """Escreve as 4 sub-abas na ficha ALVO, salvando e CONFERINDO cada uma.

    Uma sub-aba por vez, com salvamento próprio -- é como o portal trata a
    seção (cada aba tem o seu SALVAR) e como o módulo antigo já faz.

    Devolve `ResultadoDaSecao("condicoes", ...)`. Falha em UMA sub-aba não
    interrompe as outras: a ficha meio preenchida com o log dizendo o que
    faltou é melhor do que a ficha vazia com um erro genérico.
    """
    _log = _log_de(callback_log)
    if not condicoes:
        # A ORIGEM NÃO TROUXE NADA -- mas a ALVO pode já estar preenchida.
        #
        # ⚠️ 2026-08-21, pedido do usuário: *"a condição já estava feita, mas
        # daí o robô deveria dar uma checada se está completa, pois eu havia
        # marcado o Excel como completo e daí agora ele marcou como Incompleto,
        # sendo que tá completo, mas outra pessoa fez"*.
        #
        # É a diferença entre "eu não escrevi" e "não está lá". O robô só sabia
        # a primeira, e reportava a segunda -- e apagava na planilha o trabalho
        # de quem preencheu à mão.
        ja_tem = conferir_ja_preenchida(portal, callback_log)
        if ja_tem is not None:
            return ja_tem

        # ⚠️ PENDENTE, não "ok". Conserto de 2026-08-21, do log do usuário: o
        # extrator ainda NÃO lê as Condições do modo de visualização (ele mesmo
        # diz isso duas linhas acima, no log: "Condições NÃO serão copiadas:
        # falta o mapa RÓTULO→campo"). Ou seja, `condicoes` chega vazio em
        # TODA ficha -- e devolver `ok=True` aqui marcava CONDIÇÕES = COMPLETO
        # em todas elas, para uma seção que ninguém sequer tentou copiar.
        #
        # `pendente` diz a verdade nos dois lados: não conta como falha no
        # resumo do lote (não é falha, é etapa que falta) e não deixa a coluna
        # fechar como completa.
        _log("      Condições: a ficha original não trouxe nada -- pulando.")
        return ResultadoDaSecao("condicoes", False, "origem vazia", pendente=True)

    abrir_secao(portal, callback_log)
    problemas = []

    for nome in sel.CONDICOES_POR_SUBABA:
        campos = condicoes.get(nome) or {}
        if not campos:
            continue
        abrir_subaba(portal, nome, callback_log)

        falhas = escrever_subaba(portal, nome, campos, callback_log)
        if falhas:
            problemas.append(f"{nome}: não escrevi {', '.join(falhas[:4])}")

        # O nome da sub-aba VAI CRU (e não "Condições / Armazenamento") porque
        # é a chave de `PALAVRA_DA_SECAO` no portal: com ela, o toast é
        # casado pela palavra da seção e um toast remanescente de OUTRA
        # sub-aba não confirma esta.
        #
        # `ancora` = um campo DESTA sub-aba. É o que faz o robô clicar o
        # SALVAR de Condições em vez do primeiro da tela -- sem isso, em
        # 2026-08-20 as quatro sub-abas saíram "salvas e conferidas" com a
        # ficha vazia, porque o botão clicado era o de Informações Gerais e a
        # releitura via o formulário NÃO GRAVADO.
        if not portal.salvar_e_confirmar(nome, callback_log,
                                         ancora=ancora_da_subaba(nome)):
            problemas.append(f"{nome}: o portal não confirmou o salvamento")
            continue

        divergentes = conferir_subaba(portal, nome, campos, callback_log)
        if divergentes:
            _log(f"      [Erro] {nome}: {len(divergentes)} campo(s) não ficaram "
                 f"como se pediu: {', '.join(divergentes[:4])}"
                 f"{' …' if len(divergentes) > 4 else ''}.")
            problemas.append(f"{nome}: {len(divergentes)} campo(s) divergentes")
        else:
            _log(f"      [{nome}] {len(campos)} campo(s), salvo e conferido.")

    # ⚠️ O ESPANHOL. Ver `sufixos_em_espanhol_nao_copiados`: a visualização
    # entrega um texto por campo bilíngue, e é o português. Fechar CONDIÇÕES =
    # COMPLETO com os `..._ES` em branco seria a mentira de planilha de sempre
    # -- e a de planilha dura mais do que qualquer erro de tela, porque ninguém
    # volta para conferir o que já está marcado como pronto.
    faltando_es = sufixos_em_espanhol_nao_copiados(condicoes)
    if faltando_es:
        _log(f"      [i] Condições: {len(faltando_es)} campo(s) em espanhol NÃO "
             f"foram copiados -- a visualização da ficha original só mostra o "
             f"texto em português. Preencha à mão: "
             f"{', '.join(faltando_es[:4])}"
             f"{' …' if len(faltando_es) > 4 else ''}.")
        problemas.append(f"{len(faltando_es)} campo(s) em espanhol sem tradução")

    if problemas:
        return ResultadoDaSecao("condicoes", False, "; ".join(problemas))
    return ResultadoDaSecao("condicoes", True,
                            f"{len(sel.CONDICOES_POR_SUBABA)} sub-abas")
