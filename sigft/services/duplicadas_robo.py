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

# Rótulos que trazem a REFERÊNCIA DO FORNECEDOR na ficha original.
ROTULOS_DE_REFERENCIA_FORNECEDOR = (
    "Referência do fornecedor", "Referencia do fornecedor", "Referência", "Referencia",
)

# ---------------------------------------------------------------------------
# De onde vem cada dado — a ordem de precedência, decidida pelo usuário
# ---------------------------------------------------------------------------
# 2026-08-17, depois da 1ª sessão real:
#
#   FABRICANTE  -> da PLANILHA (coluna MARCA/MODELO). *"Você sabe que tem, já
#                  te pedi para mapear no conhecimento do _STATUS_PMIB todas as
#                  informações que temos hoje."* Estava mapeado em
#                  `config.COL_MARCA_MODELO` desde 2026-08-13 e eu perguntei em
#                  vez de olhar. A ficha original entra só como reserva.
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
SECOES_DA_PLANILHA = {
    config.COL_INFO_GERAIS: ("fabricante", "referencia", "fornecedor"),
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


def achar_referencia_do_fornecedor(blocos, ficha=None):
    """Referência do fornecedor: a FICHA ORIGINAL primeiro, planilha depois.

    Ordem invertida em relação ao fabricante, e é decisão do usuário: *"o
    fornecedor você pode tirar da ficha original, acho que seria mais correto,
    só caso lá estiver vazio"* -- aí a coluna CÓDIGO CMI / CÓDIGO GE.

    Vazio nos dois ⇒ `""`, e a ficha vira INCOMPLETO na planilha. É melhor do
    que escrever o código de outra ficha por parecer plausível.
    """
    da_original = _valor_por_rotulo(blocos, ROTULOS_DE_REFERENCIA_FORNECEDOR)
    if da_original:
        return da_original
    return getattr(ficha, "codigo_fornecedor", "") or ""


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


def processar_ficha(portal, ficha, callback_log=None):
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

        fabricante = achar_fabricante(blocos, ficha)
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

        referencia_fornecedor = achar_referencia_do_fornecedor(blocos, ficha)

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
            id_do_campo=secao_fabricante.id_do_campo_de_referencia))

        # A referência do FORNECEDOR usa a MESMA mecânica do fabricante: o
        # combo se identifica pelo placeholder e o campo certo é o que NASCE
        # quando ele é escolhido. Se qualquer um dos dois falhar, não escreve.
        resultado.registrar(injetor.escrever_referencia_do_fornecedor(
            portal, referencia_fornecedor, callback_log))

        portal.clicar_salvar_visivel("Fabricantes e Fornecedores")
        resultado.registrar(
            injetor.limpar_caracteristicas(portal, ficha.ficha_original, callback_log))

    except Exception as erro:  # noqa: BLE001 -- ver docstring
        resultado.erro_fatal = f"{type(erro).__name__}: {erro}"
        _log(f"   [Erro] {resultado.erro_fatal}")

    _log(f"   {resultado.resumo}")
    return resultado


def processar_lote(fichas, callback_log=None, callback_progresso=None,
                   portal=None, deve_parar=None):
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
        resultados.append(processar_ficha(portal, ficha, callback_log))
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
