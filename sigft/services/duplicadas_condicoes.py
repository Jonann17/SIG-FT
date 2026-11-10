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
from sigft.core.rpa.engine import NavegadorFechado
from sigft.services import duplicadas_extrator as extrator
from sigft.services.duplicadas_injetor import ResultadoDaSecao, _literal, _log_de

# Pausas. Mesmos valores do módulo antigo, que roda contra o portal real.
PAUSA_ABERTURA_SECAO = 2.0
PAUSA_TROCA_SUBABA = 1.5
PAUSA_APOS_ESCREVER = 0.4
TENTATIVAS_SUBABA = 20
INTERVALO_SUBABA = 0.25


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
    # Todo tipo de traço vira hífen simples. O portal escreve "Classe I -
    # Perigoso" com hífen e "Classe II – Não perigoso" com travessão, na MESMA
    # lista de opções -- e `NFKD` não unifica os dois. Sem isto, a chave do
    # mapa passaria a depender de qual traço o portal usou no dia, e o sintoma
    # seria "opção desconhecida" numa opção que está escrita certa.
    for traco in "‐‑‒–—―−":
        texto = texto.replace(traco, "-")
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

        # A SEGUNDA FORMA DA TABELA: grupo de opções. O destino é
        # `{valor lido: sufixo}` e o que se escreve é `True` no controle certo
        # -- ver `seletores_duplicada.CONDICOES_ROTULO_PARA_CAMPO`.
        if isinstance(sufixo, dict):
            opcoes = sufixo
            marcadas = [
                pedaco for pedaco in
                str(valor).split(sel.SEPARADOR_DE_OPCOES)
                if pedaco.strip()
            ]
            for pedaco in marcadas:
                escolhido = opcoes.get(chave_de_rotulo(pedaco))
                if escolhido is None:
                    # ⚠️ NÃO É "pular em silêncio". Opção que o mapa não conhece
                    # é exatamente o caso em que a ficha sai plausível e errada
                    # -- pior, o grupo «Proteção» é obrigatório, e deixá-lo
                    # vazio faz o portal recusar a SEÇÃO INTEIRA com uma
                    # mensagem que não nomeia campo nenhum.
                    _log(f"      [!] Condições: «{rotulo}» está como "
                         f"«{' '.join(str(pedaco).split())}» na original, e o "
                         f"mapa não conhece essa opção. Conhecidas: "
                         f"{', '.join(sorted(opcoes)) or '(nenhuma)'}.")
                    continue
                convertido.setdefault(subaba, {})[escolhido] = True
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


def espanhol_dos_baloes(portal, rotulos_e_valores, callback_log=None,
                        sleep_fn=None):
    """Os textos em ESPANHOL, lidos dos balões da visualização.

    Devolve `{sub-aba: {sufixo_ES: texto}}`, no mesmo formato de
    `converter_da_visualizacao`, para o chamador fundir os dois.

    🎯 É O QUE FECHA A SEÇÃO SEM ABRIR A ORIGINAL EM EDIÇÃO. Cada texto longo
    tem par (`TextArea_XxxPT` e `TextArea_XxxES`) e a visualização mostra um
    só -- o outro está no balão do tooltip, que o portal só monta quando
    alguém aponta para o texto. Ver `sel.XPATH_TOOLTIP_DO_ROTULO` e
    `PMIBPortal.texto_do_balao`.

    ⚠️ **A CONFERÊNCIA DO GATILHO NÃO É PARANOIA.** O gatilho é achado pelo
    `following::[1]` a partir do rótulo, e um campo sem tooltip faria esse
    `[1]` cair no balão do campo SEGUINTE -- a ficha alvo receberia o espanhol
    de outro texto, e nada no log diria. Por isso o português do gatilho é
    comparado com o valor que já foi lido para aquele rótulo: se não bate, o
    campo é PULADO e o log diz por quê. Espanhol faltando é uma pendência;
    espanhol trocado é um erro que ninguém vê.
    """
    _log = _log_de(callback_log)
    mapa = sel.CONDICOES_ROTULO_PARA_CAMPO
    achado = {}
    trocados = []

    for rotulo, valor in _pares(rotulos_e_valores):
        destino = mapa.get(chave_de_rotulo(rotulo))
        if destino is None:
            continue
        subaba, sufixo = destino
        # GRUPO DE OPÇÕES (`{valor: sufixo}`) não tem par de idioma nenhum: o
        # portal guarda a escolha, não um texto por idioma. Sai antes do
        # `endswith`, que só existe para string -- sem esta linha a leitura
        # inteira morria com `AttributeError` assim que a tabela ganhou a
        # segunda forma.
        if isinstance(sufixo, dict):
            continue
        # Só texto longo tem par de idioma. Número e radio não têm balão.
        if not sufixo.endswith("PT"):
            continue
        if not str(valor or "").strip():
            continue

        gatilho = sel.XPATH_TOOLTIP_DO_ROTULO.format(texto=_literal(rotulo))
        visivel = portal.texto_se_existir(gatilho).strip()

        # SEM GATILHO NENHUM é o caso comum, e sai calado: nem todo texto tem
        # par de idioma, e a ficha só com números não tem um balão sequer.
        # Avisar aqui encheria o log de alarme falso em toda ficha do lote --
        # e log que grita sempre é log que ninguém lê quando importa.
        if not visivel:
            continue

        # GATILHO COM OUTRO TEXTO, sim, é aviso: significa que o
        # `following::[1]` pulou para o campo seguinte, e copiar dali poria o
        # espanhol de outro texto na ficha alvo.
        if chave_de_rotulo(visivel) != chave_de_rotulo(valor):
            trocados.append(rotulo)
            continue

        espanhol = portal.texto_do_balao(gatilho, sleep_fn=sleep_fn)
        if espanhol:
            achado.setdefault(subaba, {})[sufixo[:-2] + "ES"] = espanhol

    if trocados:
        _log(f"      [!] Condições: em {len(trocados)} campo(s) o balão do "
             f"tooltip não é o do próprio rótulo -- NÃO copiei o espanhol "
             f"deles para não escrever o texto de outro campo: "
             f"{', '.join(trocados[:3])}"
             f"{' …' if len(trocados) > 3 else ''}.")

    return achado


def espanhol_por_texto(pares_pt_es, convertido, callback_log=None):
    """`[(pt, es)]` + `{sub-aba: {sufixo: valor}}` -> `{sub-aba: {..._ES: texto}}`.

    Casa cada espanhol com o campo `..._PT` cujo valor é o mesmo português.
    Substitui `espanhol_dos_baloes`, que passava o mouse campo a campo e lia o
    tooltip errado (ver `seletores_duplicada`, §15c).

    ⚠️ **O DESEMPATE É A ORDEM, e ele é necessário.** "não aplicável" é o valor
    de vários campos da mesma ficha, e o espanhol de cada um pode diferir. As
    duas listas vêm em ordem de documento, então consumir o primeiro par ainda
    não usado casa o certo com o certo. Casar só por texto atribuiria o mesmo
    espanhol a todos e ninguém veria diferença até um deles ter tradução
    própria -- ficha plausível e errada.

    Campo `..._PT` sem espanhol correspondente é NOMEADO no log. É a única
    coisa que separa "a original não tinha" de "eu não achei", e a segunda foi
    exatamente o que travou esta seção por uma semana.
    """
    _log = _log_de(callback_log)
    disponiveis = [[pt, es, False] for pt, es in (pares_pt_es or ())
                   if str(es or "").strip()]
    saida = {}
    sem_par = []

    for subaba in sel.CONDICOES_POR_SUBABA:
        for sufixo, valor in ((convertido or {}).get(subaba) or {}).items():
            if not isinstance(sufixo, str) or not sufixo.endswith("PT"):
                continue
            alvo = " ".join(str(valor or "").split())
            if not alvo:
                continue
            for item in disponiveis:
                if item[2] or item[0] != alvo:
                    continue
                item[2] = True
                saida.setdefault(subaba, {})[sufixo[:-2] + "ES"] = item[1]
                break
            else:
                sem_par.append(f"{subaba}/{sufixo}")

    # ⚠️ O CASO INEQUÍVOCO. Sobrou UM campo `..._PT` sem par e UM espanhol sem
    # dono: não há escolha a fazer, e deixar assim tem preço alto -- em
    # Descarte o `..._ES` é obrigatório, então um pareamento perdido faz o
    # portal recusar a sub-aba INTEIRA com "Por favor, verifique os campos", e
    # junto dela ficam sem gravar campos que nada tinham a ver (a Logística de
    # reversa, por exemplo).
    #
    # Por que o casamento por texto falha às vezes: os balões do tooltip
    # entram no DOM depois dos campos, e a varredura pega a foto pela metade.
    # A ordem de documento é a mesma nas duas listas, então com um de cada
    # lado o par é o que sobrou.
    #
    # DOIS OU MAIS sobrando é ambíguo e continua saindo no log sem chute:
    # espanhol trocado entre campos é ficha plausível e errada.
    orfaos = [item for item in disponiveis if not item[2]]
    if len(sem_par) == 1 and len(orfaos) == 1:
        subaba, sufixo = sem_par[0].split("/", 1)
        saida.setdefault(subaba, {})[sufixo[:-2] + "ES"] = orfaos[0][1]
        _log(f"      [i] Condições: {sem_par[0]} ficou sem par por texto e "
             f"sobrou exatamente um espanhol órfão -- casei os dois pela "
             f"ordem.")
        sem_par = []

    if sem_par:
        _log(f"      [i] Condições: {len(sem_par)} texto(s) sem espanhol na "
             f"ficha original: {', '.join(sem_par[:6])}"
             f"{' …' if len(sem_par) > 6 else ''}.")
    return saida


def fundir(convertido, espanhol):
    """Junta `{sub-aba: {sufixo: valor}}` de duas leituras, sem sobrescrever.

    O português vem da varredura de pares e o espanhol dos balões; são
    conjuntos de sufixos disjuntos (`...PT` × `...ES`), então "sem
    sobrescrever" é conservador de propósito -- se um dia deixarem de ser, o
    que já estava lido ganha, e o duplicado aparece como campo faltando em vez
    de virar sobrescrita silenciosa.
    """
    saida = {aba: dict(campos) for aba, campos in (convertido or {}).items()}
    for aba, campos in (espanhol or {}).items():
        destino = saida.setdefault(aba, {})
        for sufixo, valor in campos.items():
            destino.setdefault(sufixo, valor)
    return saida


def sufixos_em_espanhol_nao_copiados(condicoes):
    """Os `..._ES` cujos pares `..._PT` foram escritos. Lista, em ordem.

    ⚠️ O QUE ESTA FUNÇÃO SIGNIFICA MUDOU EM 2026-08-24. Ela nascia dizendo "a
    metade que a visualização não entrega", porque eu tinha concluído que o
    espanhol não estava na tela. **Está**: fica no balão do tooltip, e
    `espanhol_dos_baloes` o traz. Então a lista deixou de ser "todos os `..._ES`
    da ficha" e passou a ser o RESÍDUO -- os pares que nem o balão deu.

    Um resíduo é esperado e legítimo (campo que a original tem só em
    português), e continua impedindo a seção de fechar como COMPLETA: copiar o
    texto em português para dentro do campo em espanhol seria inventar uma
    tradução na ficha de outra pessoa. Uma lista GRANDE, essa sim, é sintoma --
    de gatilho recusado (ver o aviso de `espanhol_dos_baloes`) ou de balão que
    não nasceu.

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
    """Seleciona também Armazenamento: a auditoria pode ter deixado Descarte
    aberta. Abrir o cabeçalho de Condições não reinicia a sub-aba ativa."""
    reabrir_subaba(portal, nome, callback_log)


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
            except NavegadorFechado:
                raise
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
        extrator.fotografar(portal, f"ALVO em EDIÇÃO. Condições «{nome}»",
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


def esperar_subaba_montar(portal, nome, callback_log=None):
    """Espera uma âncora exclusiva da sub-aba antes de tocar em seus radios.

    RadioButton1 existe em Armazenamento e Descarte. Uma contagem dele não
    distingue a aba certa; o primeiro campo de texto distingue. Uma espera
    limitada por sub-aba evita pagar o timeout do motor por campo ausente.
    """
    for _ in range(TENTATIVAS_SUBABA):
        if portal.engine.contar(ancora_da_subaba(nome)) == 1:
            return True
        time.sleep(INTERVALO_SUBABA)
    _log_de(callback_log)(f"      [!] {nome}: a sub-aba não mostrou seus campos; "
                          "não escrevi nem salvei.")
    return False


def escrever_subaba(portal, nome, campos, callback_log=None):
    """Escreve os campos de UMA sub-aba. Devolve os sufixos que falharam.

    Texto vazio é PULADO de propósito: a ficha alvo nasce vazia, então
    escrever "" não acrescenta nada -- e um `fill("")` a mais é uma chance a
    mais de disparar validação do portal sem motivo.

    ⚠️ `safe_fill` ENGOLE a falha (contrato do motor): um campo que não
    aceitou o `fill` paga 20 s e some em silêncio. Foi o que o log de
    2026-10-19 mostrou -- Armazenamento levando 106 s numa sub-aba que
    escreve em 6 -- e é por isso que `escrever` confere a sub-aba ANTES de
    salvar (`autoconferir`): é lá que um campo que não pegou ganha nome.
    """
    _log = _log_de(callback_log)
    falhas = []
    for sufixo, valor in campos.items():
        seletor = _seletor(sufixo)
        try:
            if not isinstance(valor, bool) and not str(valor).strip():
                continue
            if not portal.engine.contar(seletor):
                _log(f"      [!] {nome}/{sufixo}: campo ausente na sub-aba; não escrevi.")
                falhas.append(sufixo)
                continue
            if isinstance(valor, bool):
                if not portal.check_or_uncheck(seletor, valor, callback_log):
                    falhas.append(sufixo)
                continue
            portal.safe_fill(seletor, str(valor))
            time.sleep(PAUSA_APOS_ESCREVER)
        except NavegadorFechado:
            raise
        except Exception as erro:  # noqa: BLE001
            _log(f"      [!] {nome}/{sufixo}: {type(erro).__name__}: {erro}")
            falhas.append(sufixo)
    return falhas


def _numero(texto):
    """"2,5" -> 2.5; `None` se não for número. Vírgula é o decimal do portal."""
    bruto = "".join(str(texto or "").split())
    if not bruto:
        return None
    if "," in bruto:
        bruto = bruto.replace(".", "").replace(",", ".")
    try:
        return float(bruto)
    except ValueError:
        return None


def mesmo_valor(esperado, atual):
    """O campo ficou com o que se pediu?

    Igualdade de texto, e um afrouxamento só para NÚMERO: os campos de volume
    e peso têm máscara numérica (`InputMaskReact.MaskNumber`), e uma máscara
    que mostra "40,00" para o "40" que se digitou guardou o valor certo.
    Acusar isso de divergência mandaria o usuário conferir o que está certo.
    """
    if str(atual).strip() == str(esperado).strip():
        return True
    a, b = _numero(esperado), _numero(atual)
    return a is not None and b is not None and a == b


def divergencias_da_subaba(portal, nome, campos, callback_log=None):
    """Relê a sub-aba e devolve `[(sufixo, esperado, lido)]` do que NÃO ficou.

    `lido` vai junto para o log: "pedi 40, ficou ''" (a máscara apagou) e
    "pedi 40, ficou 4" (perdeu tecla) são defeitos diferentes, e só o valor
    lido diz qual dos dois aconteceu.
    """
    divergentes = []
    for sufixo, esperado in campos.items():
        seletor = _seletor(sufixo)
        try:
            if not isinstance(esperado, bool) and not str(esperado).strip():
                continue
            if not portal.engine.contar(seletor):
                divergentes.append((sufixo, esperado, None))
                continue
            if isinstance(esperado, bool):
                marcado = bool(portal.engine.esta_marcado(seletor))
                if marcado != esperado:
                    divergentes.append((sufixo, esperado, marcado))
                continue
            atual = portal.valor_se_existir(seletor)
            # Ausente/ilegível não é conferido: nunca transformar uma falha
            # de leitura (inclusive depois do SALVAR) em sucesso.
            if atual is None or not mesmo_valor(esperado, atual):
                divergentes.append((sufixo, esperado, atual))
        except NavegadorFechado:
            raise
        except Exception:  # noqa: BLE001 -- sem leitura, permanece pendente
            divergentes.append((sufixo, esperado, None))
    return divergentes


def conferir_subaba(portal, nome, campos, callback_log=None):
    """Relê a sub-aba e devolve os sufixos que NÃO ficaram como se pediu.

    É a validação que o usuário pediu antes de sair da página. O toast prova
    que o portal aceitou o salvamento; só a releitura prova que o VALOR ficou.
    """
    return [s for s, _e, _a in divergencias_da_subaba(portal, nome, campos,
                                                       callback_log)]


def descrever_divergencias(divergencias, limite=4):
    """`Input_PackingLength (pedi '40', ficou '')`, para o log."""
    partes = []
    for sufixo, esperado, atual in divergencias[:limite]:
        if atual is None:
            partes.append(f"{sufixo} (ausente ou ilegível; não conferido)")
        elif isinstance(esperado, bool):
            partes.append(f"{sufixo} (pedi {'marcado' if esperado else 'desmarcado'}, "
                          f"ficou {'marcado' if atual else 'desmarcado'})")
        else:
            partes.append(f"{sufixo} (pedi {str(esperado)!r}, ficou {str(atual)!r})")
    resto = len(divergencias) - limite
    return ", ".join(partes) + (f" e mais {resto}" if resto > 0 else "")


def redigitar(portal, sufixo, valor, callback_log=None):
    """Segunda forma de escrever um campo que NÃO pegou: tecla a tecla.

    O `fill` põe o valor de uma vez. Num campo com máscara (`MaskNumber`) a
    máscara escuta o TECLADO, e o valor posto de uma vez pode ser desfeito por
    ela -- é a hipótese mais forte para os campos de volume que sumiram no log
    de 2026-10-19 (ver `docs/refatoracao/PENDENCIAS.md`). Por isso esta forma
    só entra no REPARO: o campo que já ficou com o `fill` não passa por aqui,
    e o que funciona hoje não muda.

    O TAB no fim é o `blur`: é dele que nasce o `change` que o OutSystems
    escuta (ver `duplicadas_injetor.limpar_caracteristicas`).
    """
    _log = _log_de(callback_log)
    seletor = _seletor(sufixo)
    try:
        if not portal.engine.contar(seletor):
            return False
        if isinstance(valor, bool):
            return bool(portal.check_or_uncheck(seletor, valor, callback_log))
        portal.engine.clear(seletor)
        portal.engine.type_text(seletor, str(valor))
        portal.engine.press("TAB")
        time.sleep(PAUSA_APOS_ESCREVER)
        return True
    except NavegadorFechado:
        raise
    except Exception as erro:  # noqa: BLE001
        _log(f"      [!] Não consegui redigitar {sufixo}: {type(erro).__name__}: {erro}")
        return False


def autoconferir(portal, nome, campos, callback_log=None):
    """Confere a sub-aba e REESCREVE o que não ficou. Devolve o que sobrou.

    É a autoconferência que o usuário pediu em 2026-10-20: *"quando completa
    uma aba, repasse de volta verificando seu campo"*. Uma rodada de reparo
    só -- se a segunda forma de escrever também não pega, insistir não muda o
    resultado e atrasa as outras fichas do lote.
    """
    _log = _log_de(callback_log)
    divergencias = divergencias_da_subaba(portal, nome, campos, callback_log)
    if not divergencias:
        return []
    _log(f"      [Autoconferência] {nome}: {len(divergencias)} campo(s) não "
         f"ficaram -- {descrever_divergencias(divergencias)}. Reescrevendo "
         f"tecla a tecla.")
    for sufixo, esperado, atual in divergencias:
        if atual is not None:
            redigitar(portal, sufixo, esperado, callback_log)
    sobra = divergencias_da_subaba(
        portal, nome, {s: campos[s] for s, _e, _a in divergencias}, callback_log)
    if not sobra:
        _log(f"      [Autoconferência] {nome}: corrigido na segunda tentativa.")
    return sobra


def _salvar_e_conferir(portal, nome, campos, callback_log=None):
    """Salva a sub-aba e confere. `(salvou, divergencias)`.

    Se a releitura depois do salvamento acusar campo, faz UMA rodada de
    reparo (reescreve tecla a tecla, salva de novo, confere de novo). O toast
    prova que o portal aceitou o SALVAR; não prova que o valor ficou -- no
    log de 2026-10-19 o portal confirmou Armazenamento três vezes com o
    volume em branco.
    """
    _log = _log_de(callback_log)
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
        return False, []
    divergencias = divergencias_da_subaba(portal, nome, campos, callback_log)
    if not divergencias:
        return True, []

    _log(f"      [Autoconferência] {nome}: depois de salvar, "
         f"{len(divergencias)} campo(s) não ficaram -- "
         f"{descrever_divergencias(divergencias)}. Reescrevendo e salvando "
         f"de novo.")
    for sufixo, esperado, _atual in divergencias:
        redigitar(portal, sufixo, esperado, callback_log)
    if not portal.salvar_e_confirmar(nome, callback_log,
                                     ancora=ancora_da_subaba(nome)):
        return False, divergencias
    return True, divergencias_da_subaba(portal, nome, campos, callback_log)


def reabrir_subaba(portal, nome, callback_log=None):
    """Seleciona explicitamente a sub-aba, na ida e no repasse final."""
    posicao = sel.CONDICOES_POR_SUBABA[nome]["posicao"]
    if posicao is None:
        posicao = sel.POSICAO_ARMAZENAMENTO
    portal.safe_click(sel.XPATH_CONDICOES_SUBABA.format(posicao=posicao))
    time.sleep(PAUSA_TROCA_SUBABA)


def repassar(portal, escritas, callback_log=None):
    """O REPASSE FINAL: volta em cada sub-aba já salva e relê tudo.

    `escritas` = `{sub-aba: campos}` das que saíram salvas e conferidas.
    Devolve `{sub-aba: [divergências]}` só das que mudaram depois.

    Por que de novo, se cada uma já foi conferida ao salvar: a conferência
    de cada sub-aba é feita com ELA aberta, logo depois do SALVAR. O que este
    repasse pega é o que se perde DEPOIS -- ao trocar de sub-aba o portal
    remonta o formulário com o que o SERVIDOR tem, e um valor que só existia
    na tela some ali. É o que o usuário pediu: *"repasse de volta verificando
    seu campo"*.
    """
    _log = _log_de(callback_log)
    perdidas = {}
    lidas = 0
    for nome, campos in escritas.items():
        reabrir_subaba(portal, nome, callback_log)
        if not esperar_subaba_montar(portal, nome, callback_log):
            perdidas[nome] = [(s, v, None) for s, v in campos.items()]
            continue
        divergencias = divergencias_da_subaba(portal, nome, campos, callback_log)
        textos = [s for s, v in campos.items()
                  if not isinstance(v, bool) and str(v).strip()]
        if textos and all(portal.valor_se_existir(_seletor(s)) is None
                          for s in textos):
            _log(f"      [!] Repasse: não consegui reabrir {nome} -- nenhum "
                 f"campo dela está na tela. Confira à mão.")
            perdidas[nome] = [(s, campos[s], None) for s in textos]
            continue
        lidas += 1
        if divergencias:
            perdidas[nome] = divergencias
            _log(f"      [Erro] Repasse: em {nome}, {len(divergencias)} campo(s) "
                 f"mudaram DEPOIS de salvos -- "
                 f"{descrever_divergencias(divergencias)}.")
    if escritas and not perdidas:
        _log(f"      [Autoconferência] Repasse final: {lidas} sub-aba(s) "
             f"relidas, tudo como se pediu.")
    return perdidas


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
    except NavegadorFechado:
        raise
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
    salvas = {}

    for nome in sel.CONDICOES_POR_SUBABA:
        campos = condicoes.get(nome) or {}
        if not campos:
            continue
        abrir_subaba(portal, nome, callback_log)

        if not esperar_subaba_montar(portal, nome, callback_log):
            problemas.append(f"{nome}: sub-aba não carregada")
            continue

        falhas = escrever_subaba(portal, nome, campos, callback_log)
        if falhas:
            problemas.append(f"{nome}: não escrevi {', '.join(falhas[:4])}")

        # AUTOCONFERÊNCIA ANTES DE SALVAR: o campo que o `fill` não pegou é
        # reescrito AQUI, enquanto ainda dá -- salvar primeiro gravaria o
        # buraco e só depois o descobriria.
        autoconferir(portal, nome, campos, callback_log)

        salvou, divergencias = _salvar_e_conferir(portal, nome, campos,
                                                  callback_log)
        if not salvou:
            problemas.append(f"{nome}: o portal não confirmou o salvamento")
            continue

        if divergencias:
            _log(f"      [Erro] {nome}: {len(divergencias)} campo(s) não ficaram "
                 f"como se pediu: {descrever_divergencias(divergencias)}.")
            problemas.append(f"{nome}: {len(divergencias)} campo(s) divergentes")
        else:
            _log(f"      [{nome}] {len(campos)} campo(s), salvo e conferido.")
            salvas[nome] = campos

    # O REPASSE: de volta em cada sub-aba que fechou, depois de passar pelas
    # outras. Só as que fecharam -- a que já saiu com erro está no log.
    for nome, divergencias in repassar(portal, salvas, callback_log).items():
        problemas.append(f"{nome}: {len(divergencias)} campo(s) mudaram "
                         f"depois de salvos")

    # ⚠️ O ESPANHOL QUE SOBROU. Desde 2026-08-24 o espanhol vem do balão do
    # tooltip (`espanhol_dos_baloes`), então esta lista é RESÍDUO, não regra:
    # os pares que nem o balão deu. Fechar CONDIÇÕES = COMPLETO com os
    # `..._ES` em branco continua sendo a mentira de planilha de sempre -- e a
    # de planilha dura mais do que qualquer erro de tela, porque ninguém volta
    # para conferir o que já está marcado como pronto.
    faltando_es = sufixos_em_espanhol_nao_copiados(condicoes)
    if faltando_es:
        _log(f"      [i] Condições: {len(faltando_es)} campo(s) em espanhol "
             f"ficaram sem texto -- nem a visualização nem o balão do tooltip "
             f"da ficha original tinham o que copiar. Preencha à mão: "
             f"{', '.join(faltando_es[:4])}"
             f"{' …' if len(faltando_es) > 4 else ''}.")
        problemas.append(f"{len(faltando_es)} campo(s) em espanhol sem texto")

    if problemas:
        return ResultadoDaSecao("condicoes", False, "; ".join(problemas))
    return ResultadoDaSecao("condicoes", True,
                            f"{len(sel.CONDICOES_POR_SUBABA)} sub-abas")
