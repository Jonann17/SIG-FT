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

    def __init__(self, nome, ok, detalhe=""):
        self.nome = nome
        self.ok = ok
        self.detalhe = detalhe

    def __repr__(self):
        return f"<{self.nome}: {'ok' if self.ok else 'FALHOU'} {self.detalhe}>".strip()


def _log_de(callback_log):
    def _log(mensagem):
        if callback_log:
            callback_log(mensagem)
    return _log


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

    portal.safe_click(sel.XPATH_FABRICANTE_TOGGLE)
    portal.safe_fill(sel.XPATH_FABRICANTE_BUSCA, nome_fabricante)
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
    _log(f"      Fabricante: {nome_fabricante}")
    return ResultadoDaSecao("fabricante", True, nome_fabricante)


def _literal(texto):
    """Literal XPath com aspas que não colidem (XPath 1.0 não tem escape)."""
    texto = str(texto)
    if "'" not in texto:
        return f"'{texto}'"
    if '"' not in texto:
        return f'"{texto}"'
    return "concat('" + "', \"'\", '".join(texto.split("'")) + "')"


def escrever_referencia(portal, codigo_material, callback_log=None):
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

    for tentativa, referencia in enumerate(candidatos, start=1):
        portal.safe_fill(sel.XPATH_REFERENCIA_INPUT, referencia)
        time.sleep(PAUSA_APOS_DIGITAR)
        if portal.engine.element_exists(sel.XPATH_REFERENCIA_AVISO_COLISAO):
            continue

        portal.safe_click(sel.XPATH_REFERENCIA_ADICIONAR)
        time.sleep(PAUSA_APOS_DIGITAR)
        if portal.engine.element_exists(sel.XPATH_REFERENCIA_AVISO_COLISAO):
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
    for pagina in range(1, MAX_PAGINAS_CARACTERISTICAS + 1):
        indice = 1
        while indice <= portal.engine.contar(sel.XPATH_CARACTERISTICAS_LINHAS):
            linha = f"({sel.XPATH_CARACTERISTICAS_LINHAS})[{indice}]"
            descricao = portal.engine.texto(linha + sel.XPATH_REL_CARACTERISTICA_DESCRICAO[1:])

            if _e_a_linha_do_codigo_pmib(descricao):
                seletor_valor = linha + sel.XPATH_REL_CARACTERISTICA_VALOR_PT[1:]
                portal.safe_fill(seletor_valor, pmib_original)
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

    portal.clicar_salvar_visivel("Características Técnicas")
    _log(f"      Características: {apagadas} apagada(s), {preenchidas} preservada(s).")

    if preenchidas == 0:
        # Sem a linha do CÓDIGO PMIB a ficha duplicada perde a ÚNICA
        # característica que ela precisa ter -- e a tela não reclama.
        _log("      [Erro] Nenhuma linha de CODIGO PMIB encontrada. A ficha "
             "ficou sem a característica da duplicação.")
        return ResultadoDaSecao("caracteristicas", False, "CODIGO PMIB ausente")

    return ResultadoDaSecao(
        "caracteristicas", True, f"{apagadas} apagadas, {preenchidas} preservada")
