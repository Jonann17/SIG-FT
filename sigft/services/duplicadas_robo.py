r"""
Ficha duplicada — o robô (CP 6.3).

Amarra as três peças que já existem e estão testadas em isolamento:

    duplicadas.py           quais fichas duplicar (lê o `_STATUS_PMIB`)
    duplicadas_extrator.py  o que a ficha ORIGINAL tem (lê o portal)
    duplicadas_injetor.py   escrever na ficha ALVO

Roda **no motor novo**, a pedido do usuário em 2026-08-17: *"o ficha duplicada
podemos fazer direto em Playwright, pois o de antes não funcionava muito bem"*.
Não há uma linha de Selenium neste caminho -- `config.RPA_ENGINE["duplicadas"]`
decide o motor, e trocar de motor não toca em nenhum destes arquivos.

**O que este robô AINDA NÃO faz**, e está dito aqui porque a diferença importa
na hora de conferir a ficha: documentos, imagens e as abas de Condições são o
CP 6.4. Hoje ele cobre fabricante, referência (com a regra do `'D`) e a purga
das características técnicas. O módulo antigo (`ficha_duplicada.py`) continua
inteiro e disponível -- por isso a tela tem os dois botões.
"""
from __future__ import annotations

import time

from sigft import config
from sigft.core.excel import status_sheet
from sigft.core.rpa import seletores_duplicada as sel
from sigft.core.rpa.factory import criar_engine
from sigft.core.rpa.portal import PMIBPortal
from sigft.services import duplicadas_extrator as extrator
from sigft.services import duplicadas_injetor as injetor

NOME_DO_MODULO = "duplicadas"  # chave em `config.RPA_ENGINE`

PAUSA_APOS_ABRIR_FICHA = 3.0

# Rótulos de bloco, no modo de visualização, que trazem o fabricante. Lista e
# não constante porque não sabemos ainda como o portal nomeia esse bloco -- e
# chutar um nome só faria a leitura devolver vazio sem dizer por quê.
ROTULOS_DE_FABRICANTE = ("Fabricante", "Fabricantes", "Fabricante/Fornecedor")

# Rótulos que trazem o NOME DO FORNECEDOR na ficha original.
#
# ⚠️ Antes daqui saía uma REFERÊNCIA, e era o erro. *"Vem da ficha original,
# lendo qual fornecedor foi preenchido"* (usuário, 2026-08-18): o que se lê da
# original é QUEM é o fornecedor, para escolhê-lo no combo da ficha nova. A
# referência que vai na linha dele é o CÓDIGO DO MATERIAL, o mesmo do
# fabricante -- não um valor lido do portal.
#
# Lista e não constante pelo mesmo motivo de `ROTULOS_DE_FABRICANTE`: não
# sabemos como o portal nomeia esse bloco, e chutar um nome só faria a leitura
# devolver vazio sem dizer por quê. Vazio => não escolhe nada, e a ficha sai
# INCOMPLETO com o motivo no log.
ROTULOS_DE_FORNECEDOR = (
    "Fornecedor", "Fornecedores", "Nome do fornecedor", "Razão social do fornecedor",
)

# ---------------------------------------------------------------------------
# De onde vem cada dado — a ordem de precedência, decidida pelo usuário
# ---------------------------------------------------------------------------
# 2026-08-17, depois da 1ª sessão real:
#
#   FABRICANTE (nome) -> da FICHA ORIGINAL, com a planilha (MARCA/MODELO) de
#                  reserva. ⚠️ INVERTIDO EM 2026-08-19, a pedido do usuário:
#                  *"o código do material do fabricante deve vir da
#                  _STATUS_PMIB, mas o nome do fabricante vem da ficha
#                  original"*. Até então mandava a planilha (decisão dele em
#                  2026-08-17). Divergência entre as duas vai para o log.
#
#   REFERÊNCIAS -> SEMPRE da PLANILHA, nunca copiadas da ficha original:
#                  *"esse número muda quando estamos trabalhando para outro
#                  sistema"* (2026-08-19). CÓDIGO DO MATERIAL na linha do
#                  fabricante; CÓDIGO CMI/GE na linha fixa. O que se lê da
#                  original é NOME, jamais referência.
#
#   FORNECEDOR  -> da FICHA ORIGINAL. *"O fornecedor você pode tirar da ficha
#                  original, acho que seria mais correto, só caso lá estiver
#                  vazio"* -- aí sim a planilha (CÓDIGO CMI / CÓDIGO GE).
#
#   Não achou em nenhum dos dois -> deixa EM BRANCO e a ficha vira INCOMPLETO
#   no `_STATUS_PMIB`. Nunca chuta.

# Colunas de seção do `_STATUS_PMIB` que este robô preenche, e quais
# resultados entram em cada uma. As de Condições e Documentos/Imagens ficam de
# fora até o CP 6.4 -- marcar como COMPLETO uma seção que o robô nem tentou
# seria mentir na planilha, que é onde a mentira dura mais.
#
# 2026-08-18: a seção de Fabricantes/Fornecedores passou de três resultados
# para cinco -- combo do fornecedor, referência dele, e a referência da linha
# fixa. Todas alimentam a mesma coluna.
#
# ⚠️ 2026-08-19: QUANTAS linhas a seção tem depende da FICHA, não é constante.
# No print da 4500063671.1418 são DUAS -- o fornecedor é texto fixo (GE
# ENERGIAS RENOVAVEIS LTDA) e o campo de Referência dele é o do ícone ⓘ, a
# mesma linha que aqui se chama "ge_vernova". As chaves abaixo continuam as
# cinco de propósito: `escolher_fornecedor` devolve `tem_linha=False` quando
# não há combo, e aí "fornecedor" sai ok sem que nada seja escrito. Reduzir a
# lista faria a ficha de TRÊS linhas (a com dois fornecedores, que o usuário
# mostrou em 2026-08-18) deixar de ser conferida.
SECOES_DA_PLANILHA = {
    config.COL_INFO_GERAIS: (
        "fabricante", "referencia",
        "fornecedor", "referencia_fornecedor",
        "ge_vernova", "salvar_fabricantes",
    ),
    config.COL_CARACT_TECNICAS: ("caracteristicas",),
}


class ResultadoDaFicha:
    """O que aconteceu com UMA ficha, sem interpretação.

    `secoes` guarda os `ResultadoDaSecao` na ordem em que rodaram, e o `ok` da
    ficha é a conjunção -- de propósito: uma ficha com a referência não gravada
    NÃO é sucesso, mesmo tendo salvado as características. Contar como sucesso
    o que ficou pela metade é o que faz um lote fechar "✅" e a ficha estar
    errada no portal.
    """

    def __init__(self, pmib_alvo, pmib_original):
        self.pmib_alvo = pmib_alvo
        self.pmib_original = pmib_original
        self.secoes = []
        self.erro_fatal = ""

    def registrar(self, resultado_da_secao):
        self.secoes.append(resultado_da_secao)
        return resultado_da_secao

    @property
    def ok(self):
        """Nada FALHOU. Seção pendente (que o checkpoint ainda não implementou)
        não conta como falha aqui -- ver `ResultadoDaSecao.pendente`. Para a
        PLANILHA a conta é outra: pendente também não é completo."""
        return (not self.erro_fatal and bool(self.secoes)
                and all(s.ok or s.pendente for s in self.secoes))

    @property
    def resumo(self):
        if self.erro_fatal:
            return f"{self.pmib_alvo}: {self.erro_fatal}"
        falhas = [s.nome for s in self.secoes if not s.ok and not s.pendente]
        pendentes = [s.nome for s in self.secoes if s.pendente]
        if falhas:
            texto = f"{self.pmib_alvo}: falhou em {', '.join(falhas)}"
        else:
            texto = f"{self.pmib_alvo}: ok ({len(self.secoes)} seção(ões))"
        if pendentes:
            texto += f"; pendente(s) do checkpoint: {', '.join(pendentes)}"
        return texto


def iniciar(wait_timeout=20):
    """(engine, portal) no motor que `config.RPA_ENGINE` mandar."""
    engine = criar_engine(NOME_DO_MODULO, wait_timeout=wait_timeout)
    return engine, PMIBPortal(engine)


def _log_de(callback_log):
    def _log(mensagem):
        if callback_log:
            callback_log(mensagem)
    return _log


def _valor_por_rotulo(blocos, rotulos):
    """Primeiro valor não vazio, nos blocos lidos, cujo rótulo esteja em
    `rotulos`. `""` se nenhum bater.

    Devolver `""` em vez de adivinhar é o ponto: um chute aqui vira dado errado
    numa ficha real, e a tela não reclama de nada.
    """
    alvos = {r.strip().lower() for r in rotulos}
    for _titulo, campos in blocos:
        for rotulo, valor in campos.items():
            if rotulo.strip().lower() in alvos and valor:
                return valor
    return ""


def achar_fabricante(blocos, ficha=None):
    """Fabricante a usar: a PLANILHA primeiro, a ficha original como reserva.

    A coluna `MARCA/MODELO` guarda "MARCA / MODELO" juntos e já está mapeada
    desde 2026-08-13; `duplicadas.localizar_duplicadas` a separa e entrega o
    fabricante pronto. Raspar o portal para descobrir o que a planilha já diz
    seria trabalho a mais para um resultado igual ou pior -- e a seção de
    Fabricantes fica numa aba interna que o extrator ainda não navega.
    """
    if ficha is not None and getattr(ficha, "fabricante", ""):
        return ficha.fabricante
    return _valor_por_rotulo(blocos, ROTULOS_DE_FABRICANTE)


def achar_fornecedor(blocos, ficha=None):
    """Nome do fornecedor a escolher no combo -- lido da FICHA ORIGINAL.

    *"O fornecedor você pode tirar da ficha original, acho que seria mais
    correto"* + *"vem da ficha original, lendo qual fornecedor foi
    preenchido"*.

    Só a original: a planilha NÃO tem o nome do fornecedor (as colunas CÓDIGO
    CMI / CÓDIGO GE trazem a referência da GE Vernova, que é outra linha da
    tela). Vazio ⇒ `""`, o combo não é tocado, e a ficha sai INCOMPLETO com o
    motivo no log -- melhor do que escolher um fornecedor por parecer
    plausível.

    O parâmetro `ficha` não é usado hoje; fica na assinatura por simetria com
    `achar_fabricante` e para o caso de a planilha vir a trazer a coluna.

    ⚠️ **`blocos` NÃO CONTÉM ESTA SEÇÃO, e é por isso que existe
    `achar_fornecedor_na_tabela` abaixo.** O HTML de 2026-08-18 mostrou que
    Fabricantes/Fornecedores em modo de visualização são duas TABELAS, cujas
    células não têm o ancestral `PMIB_DataSheetView.Block_Expression` que a
    varredura de rótulo→valor exige. Ou seja: esta função devolve `""` para
    uma ficha real, sem erro nenhum. Ela fica como reserva -- se um dia o
    portal renderizar o fornecedor como par rótulo→valor, ela acha.
    """
    return _valor_por_rotulo(blocos, ROTULOS_DE_FORNECEDOR)


def _primeiro_nome(itens):
    for nome, _referencia in itens or ():
        if nome:
            return nome
    return ""


def achar_fornecedor_na_tabela(tabelas, blocos=(), ficha=None):
    """Nome do fornecedor a escolher no combo, lido da TABELA da original.

    `tabelas` vem de `extrator.ler_fabricantes_e_fornecedores`.

    Fica com o PRIMEIRO da tabela. A ficha levantada tem um só fornecedor
    (GE ENERGIAS RENOVAVEIS LTDA); se um dia tiver mais de um, o combo da
    ficha nova aceita um por vez e escolher "todos" não é uma opção -- então
    o log avisa em vez de o robô decidir sozinho.

    Cai para a varredura de rótulo→valor se a tabela vier vazia: custa nada e
    cobre um portal que mude de layout.
    """
    da_tabela = _primeiro_nome((tabelas or {}).get("fornecedores"))
    if da_tabela:
        return da_tabela
    return achar_fornecedor(blocos, ficha)


def achar_fabricante_na_tabela(tabelas, blocos=(), ficha=None, callback_log=None):
    """Fabricante a usar: a FICHA ORIGINAL primeiro, a planilha como reserva.

    ⚠️ A PRECEDÊNCIA INVERTEU EM 2026-08-19, e a inversão é do usuário:
    *"o código do material do fabricante deve vir da _STATUS_PMIB, mas o NOME
    do fabricante vem da ficha original"*. Antes mandava a coluna MARCA/MODELO
    (decisão dele em 2026-08-17).

    A divisão faz sentido: o nome do fabricante é um fato da peça, e a ficha
    original é onde ele foi conferido; o código do material é do CONTRATO, e
    esse só a planilha conhece.

    Quando as duas fontes DIVERGEM, as duas vão para o log. Divergência aqui é
    quase sempre grafia ("PHOENIX CONTACT" x "PHOENIX CONTACTS S.A."), mas
    pode ser a planilha desatualizada -- e a escolha silenciosa esconderia as
    duas.
    """
    _log = _log_de(callback_log)
    da_tabela = _primeiro_nome((tabelas or {}).get("fabricantes"))
    da_planilha = getattr(ficha, "fabricante", "") if ficha is not None else ""

    if da_tabela:
        if da_planilha and da_planilha.strip().upper() != da_tabela.strip().upper():
            _log(f"   [i] Fabricante diverge: ficha original {da_tabela!r} x "
                 f"planilha {da_planilha!r}. Uso o da ficha original, como combinado.")
        return da_tabela
    if da_planilha:
        return da_planilha
    return achar_fabricante(blocos, ficha)


def ler_ficha_original(portal, pmib_original, callback_log=None):
    """Abre a original em visualização e devolve os blocos lidos."""
    _log = _log_de(callback_log)
    if not extrator.abrir_original_em_visualizacao(portal, pmib_original, callback_log):
        return None
    time.sleep(PAUSA_APOS_ABRIR_FICHA)
    blocos = extrator.ler_secao_visivel(portal.engine, callback_log)
    _log(f"   Li {len(blocos)} bloco(s) da ficha original {pmib_original}.")
    return blocos


def abrir_alvo_para_edicao(portal, pmib_alvo, callback_log=None):
    """Abre a ficha ALVO em modo de EDIÇÃO. `True` se conseguiu.

    Aqui é o lápis, e não a folha: a alvo é a ficha que vamos escrever. Usa a
    mesma varredura de abas da original -- a duplicada recém-criada costuma
    estar "Em Elaboração", mas assumir isso seria trocar uma varredura barata
    por uma falha no meio do lote.
    """
    _log = _log_de(callback_log)
    portal.ir_para_lista()
    if extrator.localizar_aba_da_ficha(portal, pmib_alvo, callback_log) is None:
        return False
    portal.engine.click_nativo(sel.XPATH_LINHA_ACAO_EDITAR.format(pmib=pmib_alvo))
    time.sleep(PAUSA_APOS_ABRIR_FICHA)
    _log(f"   Ficha alvo {pmib_alvo} aberta para edição.")
    return True


def processar_ficha(portal, ficha, callback_log=None, log_auditoria=None):
    """Duplica UMA ficha. Devolve `ResultadoDaFicha`.

    Nunca levanta por falha de seção: uma ficha que dá errado não pode derrubar
    o lote inteiro. O que ela produz é um resultado com `ok=False` e o motivo,
    que o chamador loga e segue.
    """
    _log = _log_de(callback_log)
    resultado = ResultadoDaFicha(ficha.pmib, ficha.ficha_original)
    _log(f"\n>> {ficha.pmib}  <-  {ficha.ficha_original}  ({ficha.descricao})")

    try:
        blocos = ler_ficha_original(portal, ficha.ficha_original, callback_log)
        if blocos is None:
            resultado.erro_fatal = (
                f"não achei a ficha original {ficha.ficha_original} em nenhuma aba")
            _log(f"   [Erro] {resultado.erro_fatal}")
            return resultado

        # A seção de Fabricantes/Fornecedores mora numa ABA própria e é
        # TABELA, não par rótulo→valor -- por isso tem leitura separada. Antes
        # de 2026-08-18 o robô procurava esses dois nomes na varredura de
        # rótulo→valor, que não enxerga a seção: o fornecedor vinha sempre
        # vazio, sem erro.
        tabelas = extrator.ler_fabricantes_e_fornecedores(
            portal, callback_log, log_auditoria)

        fabricante = achar_fabricante_na_tabela(tabelas, blocos, ficha,
                                                callback_log)
        if not fabricante:
            # Não é fatal: as outras seções continuam valendo, e o usuário
            # preenche o fabricante à mão. Fatal seria perder também a purga.
            # `getattr` e não `ficha.linha`: uma linha de LOG não pode ser o
            # que derruba a ficha. Escrita como acesso direto, um atributo
            # ausente virava `AttributeError`, era engolido pelo `except` lá
            # embaixo e aparecia como "erro fatal" -- a ficha morria por causa
            # da mensagem que existia só para avisar.
            _log(f"   [Aviso] Sem fabricante: a coluna MARCA/MODELO da linha "
                 f"{getattr(ficha, 'linha', '?')} está vazia e a ficha original "
                 f"também não trouxe.")
        else:
            _log(f"   Fabricante (planilha): {fabricante}")

        fornecedor = achar_fornecedor_na_tabela(tabelas, blocos, ficha)
        if not fornecedor:
            _log("   [Aviso] Não achei o fornecedor na ficha original -- a linha de "
                 "Fornecedor não será preenchida.")
        else:
            _log(f"   Fornecedor (ficha original): {fornecedor}")

        if not abrir_alvo_para_edicao(portal, ficha.pmib, callback_log):
            resultado.erro_fatal = f"não achei a ficha alvo {ficha.pmib} em nenhuma aba"
            _log(f"   [Erro] {resultado.erro_fatal}")
            return resultado

        secao_fabricante = resultado.registrar(
            injetor.escolher_fabricante(portal, fabricante, callback_log))
        # O id do campo de Referência que NASCEU ao escolher o fabricante vai
        # junto: é ele que diz em qual linha escrever, em vez de o injetor
        # pegar a primeira "Referência" da tela -- que é a da GE.
        resultado.registrar(injetor.escrever_referencia(
            portal, ficha.codigo_material, callback_log,
            id_do_campo=secao_fabricante.id_do_campo_de_referencia,
            log_auditoria=log_auditoria))

        # --- Linha do FORNECEDOR ---------------------------------------
        # Mesma mecânica do fabricante -- combo, e o campo certo é o que NASCE
        # quando a opção é escolhida. A referência que vai aqui é o CÓDIGO DO
        # MATERIAL, o MESMO do fabricante: *"o código do material deve ser
        # preenchido no campo de fornecedor que devemos selecionar"* (usuário,
        # 2026-08-18).
        #
        # Escrever o mesmo código em duas linhas parece estranho e não é: a
        # regra do sufixo `'D` é resolvida pelo PORTAL, uma linha de cada vez.
        # Se ele considerar as duas uma colisão, a segunda recebe `'D1` --
        # `escrever_referencia` lê a resposta da tela e se adapta, em vez de o
        # código supor qual das duas deve mudar.
        secao_fornecedor = resultado.registrar(
            injetor.escolher_fornecedor(portal, fornecedor, callback_log))
        # ⚠️ SÓ ESCREVE SE A LINHA EXISTIR (2026-08-19). Nem toda ficha tem a
        # linha de fornecedor com combo: no print da 4500063671.1418 o
        # fornecedor é TEXTO FIXO e o campo de Referência dela é o do ícone ⓘ
        # -- a mesma linha que este módulo chama de "GE Vernova". Escrever
        # assim mesmo era o que produzia `2 campos de Referência na tela e o
        # fabricante não indicou qual é o dele`, e sem a recusa poria o código
        # do material na linha da GE.
        if secao_fornecedor.tem_linha:
            resultado.registrar(injetor.escrever_referencia(
                portal, ficha.codigo_material, callback_log,
                id_do_campo=secao_fornecedor.id_do_campo_de_referencia,
                nome_da_secao="referencia_fornecedor",
                log_auditoria=log_auditoria))

        # --- Linha da GE VERNOVA ---------------------------------------
        # Campo FIXO (o do ícone ⓘ), e o único que recebe CÓDIGO CMI /
        # CÓDIGO GE: *"deve ser preenchido somente se tiver no _STATUS_PMIB, e
        # deve ser preenchido no campo do fornecimento da GE, que é fixo"*.
        # Vazio ⇒ pula sem erro e sem pendência.
        # `getattr` e não acesso direto: um atributo ausente na ficha viraria
        # AttributeError, seria engolido pelo `except` lá embaixo e apareceria
        # como "erro fatal" -- a ficha morreria por causa de um campo
        # OPCIONAL. Mesma lição do log do fabricante, em 2026-08-17.
        resultado.registrar(injetor.escrever_referencia_da_ge(
            portal, getattr(ficha, "codigo_fornecedor", ""), callback_log,
            log_auditoria=log_auditoria))

        # ⚠️ O RETORNO NÃO PODE SER DESCARTADO (2026-08-19). `limpar_
        # caracteristicas` já checava o seu; aqui o valor era jogado fora, e
        # essa é a OUTRA explicação possível para a tabela vazia do print da
        # 4500063671.1418: com o "+" funcionando, um salvar que não pega deixa
        # a ficha como estava e o log segue dizendo que deu certo.
        if not portal.clicar_salvar_visivel("Fabricantes e Fornecedores"):
            resultado.registrar(injetor.ResultadoDaSecao(
                "salvar_fabricantes", False, "o salvar da seção não pegou"))
            _log("   [Erro] Não consegui salvar a seção de Fabricantes e "
                 "Fornecedores. O que foi preenchido pode não ter ficado.")
        resultado.registrar(
            injetor.limpar_caracteristicas(portal, ficha.ficha_original, callback_log))

    except Exception as erro:  # noqa: BLE001 -- ver docstring
        resultado.erro_fatal = f"{type(erro).__name__}: {erro}"
        _log(f"   [Erro] {resultado.erro_fatal}")

    _log(f"   {resultado.resumo}")
    return resultado


def processar_lote(fichas, callback_log=None, callback_progresso=None,
                   portal=None, deve_parar=None, log_auditoria=None):
    """Duplica cada ficha de `fichas`. Devolve a lista de `ResultadoDaFicha`.

    `portal` injetável para teste; em produção vem de `iniciar()`.
    """
    _log = _log_de(callback_log)
    resultados = []
    total = len(fichas)

    for posicao, ficha in enumerate(fichas, start=1):
        if deve_parar and deve_parar():
            _log(f"\n[Parado pelo usuário] {posicao - 1} de {total} processada(s).")
            break
        resultados.append(
            processar_ficha(portal, ficha, callback_log,
                            log_auditoria=log_auditoria))
        if callback_progresso:
            callback_progresso(posicao / total if total else 1)

    ok = [r for r in resultados if r.ok]
    _log(f"\n=== Fim do lote: {len(ok)} de {len(resultados)} ficha(s) sem pendência.")
    for resultado in resultados:
        if not resultado.ok:
            _log(f"    - {resultado.resumo}")
    return resultados


# ===========================================================================
# Marcar o `_STATUS_PMIB`: COMPLETO por seção, INCOMPLETO no que faltou
# ===========================================================================
# "Se por fim você não conseguir, deixa em branco e daí na hora de completar o
# _STATUS_PMIB você coloca na coluna de Informações Gerais como INCOMPLETO para
# a ficha. Para as colunas que você conseguir preencher tudo, você coloca como
# COMPLETO."
#
# É a correção de um hábito do fluxo antigo: ele marcava as QUATRO colunas como
# COMPLETO para toda ficha que não tivesse estourado, sem olhar seção nenhuma
# (`frontend._worker_salvar`, dicionário com quatro `True` fixos). Uma planilha
# que diz COMPLETO no que ficou pela metade é pior do que uma planilha vazia:
# ninguém volta para conferir o que está marcado como pronto.

def status_por_secao(resultado_da_ficha):
    """{coluna do `_STATUS_PMIB`: "COMPLETO" | "INCOMPLETO"} para UMA ficha.

    Uma coluna só recebe COMPLETO se TODAS as seções que a alimentam deram
    certo. Seção que o robô nem tentou (Condições, Documentos) não aparece:
    escrever INCOMPLETO nelas seria correto mas ruidoso -- a ficha ainda vai
    passar pelo robô antigo ou pela mão -- e escrever COMPLETO seria mentira.
    """
    # Pendente conta como NÃO completo: a seção não foi preenchida, e é
    # exatamente isso que a coluna do `_STATUS_PMIB` precisa dizer.
    por_nome = {secao.nome: (secao.ok and not secao.pendente)
                for secao in resultado_da_ficha.secoes}
    marcas = {}
    for coluna, nomes in SECOES_DA_PLANILHA.items():
        relevantes = [por_nome[nome] for nome in nomes if nome in por_nome]
        if not relevantes:
            continue
        marcas[coluna] = (status_sheet.VALOR_COMPLETO if all(relevantes)
                          else status_sheet.VALOR_INCOMPLETO)
    return marcas


def marcar_status_na_planilha(caminho_excel, resultados, callback_log=None):
    """Escreve COMPLETO/INCOMPLETO nas colunas de seção, ficha a ficha.

    Devolve (marcadas, falhas). Erro numa ficha não impede as outras: o robô
    já rodou, e perder o registro de 14 fichas porque a 15ª não foi encontrada
    na planilha seria trocar um problema pequeno por um grande.
    """
    _log = _log_de(callback_log)
    marcadas = 0
    falhas = []

    for resultado in resultados:
        marcas = status_por_secao(resultado)
        if not marcas:
            continue
        painel = status_sheet.StatusPMIB(caminho_excel)
        try:
            chaves = {config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB}
            for coluna in marcas:
                chaves[coluna.upper()] = coluna.upper()
            painel.abrir(keywords=chaves, required=[config.COL_CODIGO_PMIB], max_row=15)

            linha = painel.buscar_linha(resultado.pmib_alvo)
            if linha is None:
                falhas.append(f"{resultado.pmib_alvo}: não achei a linha na planilha")
                continue

            # Uma chamada por VALOR: `marcar_linha` escreve o mesmo valor em
            # todas as colunas que recebe, e aqui os valores podem diferir --
            # INFO. GERAIS incompleta e CARACT. TÉCNICAS completa é o caso
            # normal enquanto o CP 6.4 não fecha.
            for valor in (status_sheet.VALOR_COMPLETO, status_sheet.VALOR_INCOMPLETO):
                colunas = [c for c, v in marcas.items() if v == valor]
                if colunas:
                    painel.marcar_linha(linha, colunas, valor=valor)

            painel.salvar()
            marcadas += 1
            _log(f"   Planilha: {resultado.pmib_alvo} -> "
                 + ", ".join(f"{c} = {v}" for c, v in marcas.items()))
        except Exception as erro:  # noqa: BLE001 -- ver docstring
            falhas.append(f"{resultado.pmib_alvo}: {type(erro).__name__}: {erro}")
        finally:
            try:
                painel.fechar()
            except Exception:  # noqa: BLE001
                pass

    if falhas:
        _log(f"   [Aviso] {len(falhas)} ficha(s) não foram marcadas na planilha:")
        for falha in falhas:
            _log(f"      - {falha}")
    return marcadas, falhas
