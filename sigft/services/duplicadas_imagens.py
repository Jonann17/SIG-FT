r"""
Ficha duplicada — IMAGENS (CP 6.4).

A única das três seções que não se resolve associando. Documento já existe
como objeto no portal, então basta apontar para ele; **imagem é arquivo**, e
tem de sair da ficha original e entrar na nova.

⚠️ E O `src` DELA É UM `blob:`:

    <img class="custom-img" src="blob:https://apps.itaipu.gov.br/29077935-…">

`blob:` não é endereço HTTP -- é um identificador de objeto que só vale dentro
daquela página, naquela sessão. Não há servidor do outro lado para baixar
dele. A imagem só pode ser lida de dentro do navegador, e é o que
`RPAEngine.bytes_da_imagem` faz.

Isso desfaz a pendência que eu tinha registrado em 2026-08-19 ("o Playwright
não reproduz a pasta de downloads do Chrome"): o caminho certo nunca foi a
pasta de downloads. Ler o blob de dentro da página é mais direto, funciona
igual nos dois motores e não depende de configurar o navegador.

O ciclo, por imagem: ler os bytes -> gravar num arquivo temporário -> subir ->
conferir que o FilePond aceitou -> salvar. **Os temporários são apagados no
fim**, como o usuário pediu: *"precisamos baixar temporariamente a imagem no
disco e depois apagá-la para fazer o upload"*.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import time

from sigft.core.rpa import seletores_duplicada as sel
from sigft.services.duplicadas_injetor import ResultadoDaSecao, _log_de

PAUSA_ABERTURA_FORM = 2.0
PAUSA_APOS_UPLOAD = 2.0

# Teto da espera pelo processamento do FilePond, e o intervalo entre olhadas.
# 60 s é folgado para uma imagem de ficha (as do portal têm dezenas de KB) e
# curto o bastante para o usuário não achar que travou. Ver
# `esperar_processamento` para por que a espera é por ESTADO e não por relógio.
TIMEOUT_PROCESSAMENTO = 60.0
INTERVALO_DE_POLL = 0.5


def esperar_processamento(portal, callback_log=None, timeout=TIMEOUT_PROCESSAMENTO):
    """Espera o FilePond TERMINAR de subir o arquivo. `True` se terminou.

    ⚠️ CONSERTO DE 2026-08-21, a partir do log e do diagnóstico do usuário:
    *"quando carregamos uma imagem, pode ser que demore a fazer o upload, e
    talvez seja esse o erro, tentar clicar antes de esperar dar o upload"*.

    A versão anterior dormia 2 s fixos e clicava em "Confirmar". Dois segundos
    é uma aposta: acerta na imagem pequena e na rede boa, erra em qualquer
    outro dia -- e o sintoma não é um erro claro, é o portal não devolver toast
    nenhum, que foi exatamente o que apareceu no log.

    Se a tela não expõe `data-filepond-item-state` (versão de FilePond
    diferente, ou item ainda não renderizado), não há o que observar: devolve
    `True` e deixa a checagem do `<li>` decidir. Fingir que esperou seria pior
    do que dizer que não deu para ver.
    """
    _log = _log_de(callback_log)
    if not portal.engine.contar(sel.XPATH_IMAGENS_ITEM_COM_ESTADO):
        return True

    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        if not portal.engine.contar(sel.XPATH_IMAGENS_ITEM_PROCESSANDO):
            return True
        time.sleep(INTERVALO_DE_POLL)

    _log(f"      [Erro] O FilePond ainda estava processando depois de "
         f"{timeout:.0f}s. NÃO cliquei em Confirmar -- confirmar no meio do "
         f"upload é o que fazia o portal não responder nada.")
    return False


def extensao_de(dados):
    """`.png` / `.jpg` pela ASSINATURA do arquivo, não pelo nome.

    Um `blob:` não tem nome nem extensão, e o `<input>` do portal declara
    `accept="image/jpeg,image/png"` -- se o arquivo temporário sair com a
    extensão errada, o navegador anuncia o MIME errado e o portal recusa sem
    dizer por quê. Os primeiros bytes são a única fonte confiável aqui.
    """
    for assinatura, extensao in sel.ASSINATURAS_DE_IMAGEM:
        if dados[:len(assinatura)] == assinatura:
            return extensao
    return ""


def ler_da_original(portal, callback_log=None):
    """Imagens da ficha original, como `[(legenda, bytes), …]`.

    A ficha tem de estar aberta em VISUALIZAÇÃO -- é onde o carrossel mostra
    as imagens. Slide sem bytes legíveis é pulado COM aviso: melhor uma imagem
    a menos e uma linha no log do que um arquivo vazio subindo para o portal.
    """
    _log = _log_de(callback_log)
    try:
        total = portal.engine.contar(sel.XPATH_IMAGENS_SLIDES)
    except Exception:  # noqa: BLE001
        total = 0
    if not total:
        return []

    imagens = []
    for indice in range(1, total + 1):
        slide = f"({sel.XPATH_IMAGENS_SLIDES})[{indice}]"
        legenda = portal.texto_se_existir(
            slide + sel.XPATH_REL_LEGENDA_DO_SLIDE[1:]).strip()
        dados = portal.engine.bytes_da_imagem(
            slide + sel.XPATH_REL_IMAGEM_DO_SLIDE[1:])
        if not dados:
            _log(f"      [Aviso] Imagem {indice}/{total} "
                 f"({legenda or 'sem legenda'}) não pôde ser lida. Copie à mão.")
            continue
        imagens.append((legenda, dados))

    _log(f"      {len(imagens)} imagem(ns) lida(s) da ficha original.")
    return imagens


def gravar_temporarias(imagens, pasta):
    """Grava cada imagem num arquivo de `pasta`. `[(legenda, caminho), …]`.

    Imagem cujo formato não é JPEG nem PNG NÃO é gravada: o portal a recusaria,
    e um upload que falha no meio deixa o formulário num estado que a próxima
    imagem herda.
    """
    arquivos = []
    for indice, (legenda, dados) in enumerate(imagens, start=1):
        extensao = extensao_de(dados)
        if not extensao:
            continue
        caminho = os.path.join(pasta, f"imagem_{indice}{extensao}")
        with open(caminho, "wb") as arquivo:
            arquivo.write(dados)
        arquivos.append((legenda, caminho))
    return arquivos


def subir_uma(portal, legenda, caminho, callback_log=None):
    """Sobe UMA imagem na ficha alvo (já aberta em edição). `True` se entrou."""
    _log = _log_de(callback_log)

    if not _abrir_formulario(portal):
        _log("      [Erro] Não achei 'Adicionar imagens' nesta tela.")
        return False
    time.sleep(PAUSA_ABERTURA_FORM)

    # A ficha é bilíngue e a legenda que veio da original serve para os dois
    # idiomas -- não temos a versão em espanhol dela, e traduzir seria inventar.
    for seletor in (sel.XPATH_IMAGENS_DESCRICAO_ES, sel.XPATH_IMAGENS_DESCRICAO_PT):
        if portal.engine.contar(seletor):
            portal.safe_fill(seletor, legenda)

    try:
        portal.engine.enviar_arquivo(sel.XPATH_IMAGENS_INPUT_ARQUIVO, caminho)
    except Exception as erro:  # noqa: BLE001
        _log(f"      [Erro] O upload de {os.path.basename(caminho)} falhou: "
             f"{type(erro).__name__}: {erro}")
        return False
    time.sleep(PAUSA_APOS_UPLOAD)

    # ESPERA PELO FIM DO UPLOAD, e não por um relógio. Ver
    # `esperar_processamento`: clicar em "Confirmar" no meio do processamento é
    # o que fazia o portal não devolver toast nenhum.
    if not esperar_processamento(portal, callback_log):
        return False

    # A PROVA de que o arquivo foi ACEITO: o FilePond cria um `<li>` na lista.
    # Sem ela, "enviei o arquivo" é só "chamei a função" -- o mesmo buraco que
    # o "+" da referência e o SALVAR sem toast já custaram neste módulo.
    try:
        na_lista = portal.engine.contar(sel.XPATH_IMAGENS_ITEM_NA_LISTA)
    except Exception:  # noqa: BLE001
        na_lista = 0
    if not na_lista:
        _log(f"      [Erro] O FilePond não listou {os.path.basename(caminho)} "
             f"depois do envio. A imagem não entrou.")
        return False

    # ⚠️ "Confirmar", DENTRO do diálogo -- não o SALVAR da seção, que fica
    # inacessível enquanto ele está aberto (20 s de timeout no log de
    # 2026-08-20). O portal responde com toast próprio: "A imagem foi
    # adicionada com sucesso!".
    return portal.clicar_e_confirmar(sel.XPATH_IMAGENS_CONFIRMAR,
                                     sel.ABA_DOCUMENTOS_EDICAO, callback_log)


TENTATIVAS_DE_FECHAR = 3


def fechar_formulario(portal, callback_log=None):
    """Fecha o formulário de "Adicionar imagens" se ele ficou aberto.

    `True` quando a tela ficou livre. ESC é o mesmo recurso que já fecha a
    lista do PDM (`duplicadas_pdm`); e com o formulário fechado ele não faz
    nada -- por isso dá para chamar sempre, sem perguntar antes.
    """
    _log = _log_de(callback_log)
    for _ in range(TENTATIVAS_DE_FECHAR):
        try:
            if not portal.engine.contar(sel.XPATH_IMAGENS_CONTAINER):
                return True
        except Exception:  # noqa: BLE001 -- tela remontando
            pass
        try:
            portal.engine.press("ESCAPE")
        except Exception:  # noqa: BLE001 -- sem foco; a próxima volta tenta
            pass
        time.sleep(PAUSA_APOS_UPLOAD / 2)
    try:
        livre = not portal.engine.contar(sel.XPATH_IMAGENS_CONTAINER)
    except Exception:  # noqa: BLE001
        livre = False
    if not livre:
        _log("      [Erro] O formulário de imagens ficou aberto e não fechou "
             "com ESC. Feche à mão: ele cobre a tela e trava o que vem "
             "depois.")
    return livre


def _abrir_formulario(portal):
    """Clica em "Adicionar imagens". Duas âncoras: o link e, se ele não casar,
    o próprio rótulo -- a captura do usuário mostra só o `<span>`, sem revelar
    o que há em volta."""
    for seletor in (sel.XPATH_IMAGENS_ABRIR, sel.XPATH_IMAGENS_ABRIR_SPAN):
        try:
            if portal.engine.contar(seletor):
                portal.safe_click(f"({seletor})[1]")
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def subir_arquivos(portal, arquivos, callback_log=None):
    """Sobe `[(descricao, caminho), …]` na ficha aberta em edição, um por vez.
    Devolve quantos entraram. Também usado pelo Upload de Fotos."""
    _log = _log_de(callback_log)
    subidas = 0
    for descricao, caminho in arquivos:
        entrou = subir_uma(portal, descricao, caminho, callback_log)
        if not entrou:
            # AUTOCONFERÊNCIA COM REPARO: o upload que falha deixa o
            # formulário ABERTO, e ele cobre a tela. No log de 2026-10-19
            # foi uma cadeia: o FilePond não apareceu, a imagem seguinte
            # "não achou 'Adicionar imagens'" e as DUAS fichas seguintes
            # não acharam nem a lista. Fechar e tentar de novo, uma vez.
            fechar_formulario(portal, callback_log)
            _log(f"      [Autoconferência] Imagens: "
                 f"{os.path.basename(caminho)} não entrou -- fechei o "
                 f"formulário e vou tentar de novo.")
            entrou = subir_uma(portal, descricao, caminho, callback_log)
            if not entrou:
                fechar_formulario(portal, callback_log)
        if entrou:
            subidas += 1
            _log(f"      Imagem enviada: {descricao[:50] or '(sem legenda)'}")

    # Saída LIMPA, aconteça o que acontecer: a próxima seção (e a próxima
    # ficha) não pode herdar um formulário aberto por cima da tela.
    fechar_formulario(portal, callback_log)
    return subidas


def copiar(portal, imagens, pmib_alvo="", callback_log=None):
    """Sobe na ficha ALVO as imagens lidas da original.

    `imagens` vem de `ler_da_original`, com a ficha original ainda aberta.

    A LEGENDA de cada uma é a da ficha original quando existe -- é mais fiel do
    que qualquer texto inventado. Só quando ela vem vazia é que entra o código
    PMIB da ficha, que foi a sugestão do usuário: *"a descrição da imagem pode
    ser o código PMIB da ficha"*.

    Os arquivos temporários vão para uma pasta própria e são apagados no
    `finally` -- inclusive quando alguma imagem falha.
    """
    _log = _log_de(callback_log)
    if not imagens:
        _log("      Imagens: a ficha original não tem nenhuma -- pulando.")
        return ResultadoDaSecao("imagens", True, "nenhuma na origem")

    pasta = tempfile.mkdtemp(prefix="sigft_imagens_")
    try:
        arquivos = gravar_temporarias(imagens, pasta)
        recusadas = len(imagens) - len(arquivos)
        if recusadas:
            _log(f"      [Aviso] {recusadas} imagem(ns) não são JPEG nem PNG e "
                 f"o portal as recusaria. Copie à mão.")

        subidas = subir_arquivos(
            portal, [(legenda or pmib_alvo, caminho) for legenda, caminho in arquivos],
            callback_log)

        faltaram = len(imagens) - subidas
        if faltaram:
            return ResultadoDaSecao("imagens", False,
                                    f"{faltaram} de {len(imagens)} não subiram")
        return ResultadoDaSecao("imagens", True, f"{subidas} imagem(ns)")
    finally:
        # *"…e depois apagá-la"*. `ignore_errors` porque um temporário que
        # sobrou é lixo em disco; falhar por causa dele derrubaria uma ficha
        # que já está pronta no portal.
        shutil.rmtree(pasta, ignore_errors=True)
