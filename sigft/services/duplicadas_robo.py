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
        return not self.erro_fatal and bool(self.secoes) and all(s.ok for s in self.secoes)

    @property
    def resumo(self):
        if self.erro_fatal:
            return f"{self.pmib_alvo}: {self.erro_fatal}"
        falhas = [s.nome for s in self.secoes if not s.ok]
        if falhas:
            return f"{self.pmib_alvo}: falhou em {', '.join(falhas)}"
        return f"{self.pmib_alvo}: ok ({len(self.secoes)} seção(ões))"


def iniciar(wait_timeout=20):
    """(engine, portal) no motor que `config.RPA_ENGINE` mandar."""
    engine = criar_engine(NOME_DO_MODULO, wait_timeout=wait_timeout)
    return engine, PMIBPortal(engine)


def _log_de(callback_log):
    def _log(mensagem):
        if callback_log:
            callback_log(mensagem)
    return _log


def achar_fabricante(blocos):
    """Nome do fabricante nos blocos lidos da ficha original, ou `""`.

    Procura entre os RÓTULOS conhecidos, em qualquer bloco. Devolver `""` em
    vez de adivinhar é o ponto: `escolher_fabricante` já trata vazio como
    "pular com aviso", e um chute aqui viraria fabricante errado na ficha --
    que não dá sintoma nenhum na tela.
    """
    for _titulo, campos in blocos:
        for rotulo, valor in campos.items():
            if any(alvo.lower() == rotulo.strip().lower() for alvo in ROTULOS_DE_FABRICANTE):
                if valor:
                    return valor
    return ""


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

        fabricante = achar_fabricante(blocos)
        if not fabricante:
            # Não é fatal: as outras seções continuam valendo, e o usuário
            # preenche o fabricante à mão. Fatal seria perder também a purga.
            _log("   [Aviso] Não achei o fabricante na ficha original "
                 f"(rótulos procurados: {', '.join(ROTULOS_DE_FABRICANTE)}).")

        if not abrir_alvo_para_edicao(portal, ficha.pmib, callback_log):
            resultado.erro_fatal = f"não achei a ficha alvo {ficha.pmib} em nenhuma aba"
            _log(f"   [Erro] {resultado.erro_fatal}")
            return resultado

        resultado.registrar(injetor.escolher_fabricante(portal, fabricante, callback_log))
        resultado.registrar(
            injetor.escrever_referencia(portal, ficha.codigo_material, callback_log))
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
