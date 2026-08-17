r"""
Regras de negócio da ficha DUPLICADA — a parte que não depende de navegador.

CP 6.1 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 6). O módulo antigo
(`services/ficha_duplicada.py`) é o único que nunca foi portado e o
diagnóstico do plano o classifica como "frágil por concepção"; a Fase 6 o
reconstrói. Este arquivo é o primeiro tijolo, e de propósito **não tem uma
linha de RPA**: são as decisões de negócio isoladas, onde dá para testá-las
sem portal, sem Selenium e sem Playwright.

Tudo aqui vem das respostas do usuário em 2026-08-11 e está registrado em
`docs/refatoracao/FICHA_DUPLICADA.md`, com as perguntas que ficaram abertas.
Quando a regra for uma leitura minha e não uma afirmação dele, a docstring
diz isso.
"""
from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# 1. Identificação: o que é uma ficha duplicada
# ---------------------------------------------------------------------------
# "Toda ficha que tiver o PDM como 'PDM.9900.000 - FICHA PMIB, DUPLICADA, R0'
# significa que ela é uma duplicação. No caso pra dar correspondência seria bom
# apenas a primeira parte PDM.9900.000."
#
# O casamento é por PREFIXO, e isso não é preguiça: o sufixo carrega revisão
# (`R0`, `R1`...) e descrição, que mudam sem aviso e por motivo alheio ao que
# se está decidindo aqui. Prender a identificação ao texto inteiro seria criar
# um jeito de o módulo parar de achar fichas depois de uma revisão do PDM.
PDM_DUPLICADA = "PDM.9900.000"

# "a coluna 'PDM usado' que às vezes pode ter alguma variação como PDMs usados"
COLUNAS_PDM_USADO = ("PDM usado", "PDMs usados", "PDM USADO", "PDM")

# Colunas do `_STATUS_PMIB` que a duplicação consome. Cada uma com as grafias
# que o usuário citou -- planilha preenchida por gente tem variação, e
# reprovar por causa disso seria implicância (mesmo tratamento dado à planilha
# de LMR).
COLUNAS_REFERENCIA_FABRICANTE = ("CÓDIGO DO MATERIAL", "CODIGO DO MATERIAL")
COLUNAS_REFERENCIA_FORNECEDOR = ("CÓDIGO CMI", "CODIGO CMI", "CÓDIGO GE", "CODIGO GE")
COLUNAS_FICHA_ORIGINAL = ("OBSERVAÇÕES", "OBSERVACOES", "OBSERVAÇÃO")


def _sem_acento(texto):
    return unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()


def _normalizar_cabecalho(texto):
    return _sem_acento(texto).strip().upper()


def achar_coluna(colunas, candidatas):
    """Primeiro nome de `candidatas` presente em `colunas`, ignorando caixa,
    acento e espaço. `None` se nenhum existir."""
    disponiveis = {_normalizar_cabecalho(c): c for c in colunas}
    for candidata in candidatas:
        real = disponiveis.get(_normalizar_cabecalho(candidata))
        if real is not None:
            return real
    return None


def e_ficha_duplicada(valor_pdm_usado):
    """A ficha é uma duplicação?

    Compara só o começo, tolerando espaço em volta e caixa. Um valor vazio,
    `None` ou `nan` (o que o pandas devolve para célula em branco) é `False`
    -- ficha sem PDM não é duplicada, é ficha sem PDM.
    """
    if valor_pdm_usado is None:
        return False
    texto = str(valor_pdm_usado).strip()
    if not texto or texto.lower() == "nan":
        return False
    return texto.upper().startswith(PDM_DUPLICADA.upper())


# ---------------------------------------------------------------------------
# 2. A referência do fabricante e o sufixo 'D
# ---------------------------------------------------------------------------
# "a referência, que geralmente deve vir do Status PMIB da coluna 'CÓDIGO DO
# MATERIAL', só que se aparecer 'a referência já existe', devemos colocar o
# partnumber dele 2904616 com o 'D1 no final, ficando "2904616'D1", e se ainda
# não existir, deve colocar o 'D2, e se não existir, colocar D3, assim por
# diante, até ele conseguir."
#
# Ou seja: é uma sequência de TENTATIVAS, e quem decide se parou é o PORTAL
# (a mensagem "A referência já existe!" embaixo do campo). O código não tem
# como saber de antemão qual vai passar -- por isso a função gera a sequência
# e o RPA a consome uma a uma, conferindo a tela entre elas.
SUFIXO_DUPLICADA = "'D"

# Teto de tentativas. Não veio do usuário: é decisão de engenharia. Sem um
# teto, um portal que rejeite TUDO (campo travado, sessão expirada, mensagem
# de erro diferente lida como "já existe") faz o robô tentar para sempre,
# escrevendo no campo a cada volta. 20 é folgado o bastante para qualquer
# caso real de material repetido e curto o bastante para o usuário perceber.
MAX_TENTATIVAS_REFERENCIA = 20


def sequencia_de_referencias(codigo_material, maximo=MAX_TENTATIVAS_REFERENCIA):
    """Referências a tentar, em ordem: o código cru, depois `'D1`, `'D2`...

    O código cru vem primeiro porque é o caso comum -- a maioria das fichas
    duplicadas não colide com nada. Os sufixos só entram quando o portal
    recusa, e é o portal quem diz.
    """
    base = str(codigo_material or "").strip()
    if not base:
        return []
    return [base] + [f"{base}{SUFIXO_DUPLICADA}{n}" for n in range(1, maximo + 1)]


_MENSAGENS_DE_COLISAO = (
    "a referencia ja existe",
    "referencia ja existe",
    "la referencia ya existe",
)


def e_erro_de_referencia_repetida(texto_da_tela):
    """A mensagem sob o campo é a de referência repetida?

    Existe para o RPA NÃO tratar qualquer erro como colisão: se o portal
    reclamar de outra coisa (campo obrigatório, sessão expirada), tentar
    `'D1`, `'D2`, `'D3`... não resolve nada e ainda gasta 20 voltas escondendo
    o erro de verdade. Aceita PT e ES porque a tela alterna de idioma -- o
    mesmo problema que já apareceu nos dropdowns de `tech_specs`.
    """
    limpo = _sem_acento(texto_da_tela or "").lower()
    return any(mensagem in limpo for mensagem in _MENSAGENS_DE_COLISAO)


# ---------------------------------------------------------------------------
# 3. O que se copia e o que NÃO se copia
# ---------------------------------------------------------------------------
# Da resposta do usuário, por seção. O valor deste bloco é ser a lista
# fechada: o módulo antigo copiava "o que desse", e não havia onde conferir
# se algo tinha ficado para trás ou vindo a mais.
SECOES_A_REPLICAR = (
    "fabricantes_fornecedores",
    "caracteristicas_tecnicas",
    "documentos_imagens",
    "condicoes",
)

# "Na seção de condições, copiar todos os dados em todas as seções, com
# exceção da parte financeira." + esclarecimento de 2026-08-11: "Condições
# financeira é uma seção interna dentro das condições."
#
# ISSO SIMPLIFICOU MUITO a regra, e vale registrar por quê: a primeira leitura
# era "existe uma lista de campos financeiros espalhados pelas Condições", o
# que exigiria enumerar campo a campo e deixaria a seção bloqueada até alguém
# fazer esse levantamento. Não é isso: "Financeira" é uma ABA. A exclusão é
# nomeável, verificável e não depende de nenhuma lista -- o robô simplesmente
# não entra naquela aba.
#
# As abas têm nomes DIFERENTES nos dois modos da ficha, e isso não é detalhe:
#   - modo EDIÇÃO (5 abas):     Condições de armazenamento | Condições
#     financeiras | Condições de transporte e movimentação | Condições de
#     manutenção | Condições de descarte
#   - modo VISUALIZAÇÃO (3 abas): Armazenamento e transporte | Financeira |
#     Manutenção e descarte
# O extrator lê do modo VISUALIZAÇÃO (ver `MODO_LEITURA_*` abaixo) e o injetor
# escreve no modo EDIÇÃO, então os dois conjuntos precisam existir.
ABA_CONDICOES_FINANCEIRA_EDICAO = "Condições financeiras"
ABA_CONDICOES_FINANCEIRA_VISUALIZACAO = "Financeira"

ABAS_CONDICOES_EDICAO = (
    "Condições de armazenamento",
    ABA_CONDICOES_FINANCEIRA_EDICAO,
    "Condições de transporte e movimentação",
    "Condições de manutenção",
    "Condições de descarte",
)
ABAS_CONDICOES_VISUALIZACAO = (
    "Armazenamento e transporte",
    ABA_CONDICOES_FINANCEIRA_VISUALIZACAO,
    "Manutenção e descarte",
)

# Nada mais bloqueado: com a exclusão virando "não entre nesta aba", a seção
# de Condições saiu do limbo. Mantido como tupla vazia (e não removido) porque
# o mecanismo continua útil -- se aparecer outra regra com especificação
# incompleta, é aqui que ela fica visível em vez de virar comportamento.
SECOES_BLOQUEADAS_ATE_CONFIRMACAO = ()


def e_aba_financeira(nome_da_aba):
    """A aba é a financeira -- em qualquer um dos dois modos da ficha?

    Comparação por SUBSTRING normalizada ("financeir" cobre "Condições
    financeiras" e "Financeira", singular e plural, com e sem acento). Errar
    para o lado de reconhecer é o lado seguro: um falso positivo deixa de
    copiar uma aba, um falso negativo COPIA dado financeiro de uma ficha para
    outra -- e esse erro fica plausível na tela e ninguém confere.
    """
    return "financeir" in _sem_acento(nome_da_aba or "").lower()


def abas_de_condicoes_a_copiar(modo="visualizacao"):
    """Abas de Condições que entram na duplicação, na ordem da tela."""
    todas = ABAS_CONDICOES_VISUALIZACAO if modo == "visualizacao" else ABAS_CONDICOES_EDICAO
    return tuple(aba for aba in todas if not e_aba_financeira(aba))


# ---------------------------------------------------------------------------
# 4. De onde se LÊ a ficha original
# ---------------------------------------------------------------------------
# "A ficha original é sempre encontrável, mas pode variar dentro do portal se
# ela está em Elaboração, ou se está em Análise, ou demais campos." +
# "acho que é melhor sempre fazermos o webscraping de como abrimos a ficha no
# modo de visualização (pq nem sempre estará em Em Elaboração)".
#
# É uma decisão de ARQUITETURA, não de conveniência, e é o que separa este
# módulo do `upload_conditions`: aquele lê e escreve na ficha em EDIÇÃO, com
# `<input>`/`<textarea>`/`<select>`. A ficha ORIGINAL de uma duplicação
# raramente está em elaboração -- na tela levantada ela estava "Em Análise
# ITAIPU" --, e nesse estado o portal mostra os valores como TEXTO, não como
# campo. Um extrator que procure `input[value]` não acha nada e devolve ficha
# vazia, sem erro.
MODO_LEITURA_ORIGINAL = "visualizacao"

# A busca da ficha original NÃO pode assumir aba de status: o portal separa
# por "Em Elaboração", "Para enviar à ITAIPU", "Em Análise ITAIPU",
# "Rejeitado pela ITAIPU", "Aprovado parcialmente IB", "Aprovado pela
# ITAIPU" e "Cancelado", e a original pode estar em qualquer uma.
ABAS_DE_STATUS_DA_LISTA = (
    "Em Elaboração",
    "Para enviar à ITAIPU",
    "Em Análise ITAIPU",
    "Rejeitado pela ITAIPU",
    "Aprovado parcialmente IB",
    "Aprovado pela ITAIPU",
    "Cancelado",
)

# ---------------------------------------------------------------------------
# 5. Imagens: como se copia
# ---------------------------------------------------------------------------
# "Basta entrar na imagem do portal, clicar na figura, dar copiar na figura,
# ir na ficha que você quer, clicar em adicionar imagem e colar no campo que
# abre. Daí de descrição em espanhol e português podemos colocar a descrição
# do item que está no próprio STATUS PMIB."
#
# É o fluxo MANUAL, e ele passa pela área de transferência. Para o robô, a
# recomendação é OUTRA e o motivo é técnico: colar imagem da área de
# transferência dentro de um campo de upload é a operação menos confiável que
# existe em automação de navegador -- depende do sistema operacional, do foco
# da janela e de o navegador aceitar `paste` sintético. O diálogo "Adicionar
# Imagens" aceita ARQUIVO ("Arraste e solte arquivos aqui ou Adicione"), e
# toda imagem no portal tem URL. Então: BAIXAR da original e SUBIR na
# duplicada -- mesmo resultado, sem clipboard no caminho.
#
# ⚠️ A confirmar na tela: se o `<input type=file>` do diálogo é alcançável
# (Playwright preenche isso direto com `set_input_files`, sem simular arraste).
IMAGENS_VIA_ARQUIVO = True
MAX_IMAGENS_POR_ENVIO = 10  # "Máximo 10 arquivos", dito pelo próprio diálogo


def descricao_das_imagens(descricao_do_material):
    """Descrição (ES e PT) a usar nas imagens: a descrição do material, do
    `_STATUS_PMIB`.

    Devolve o MESMO texto para os dois idiomas -- foi o que o usuário
    especificou ("podemos colocar a descrição do item que está no próprio
    STATUS PMIB", que é uma coluna só). Traduzir por conta própria seria
    inventar dado.
    """
    texto = str(descricao_do_material or "").strip()
    if not texto or texto.lower() == "nan":
        return None
    return {"es": texto, "pt": texto}

# "No campo de Características técnicas vai haver 4 seções, devemos apagar 3 e
# deixar somente a da imagem anexa" -- a característica `3626 - CODIGO PMIB`,
# preenchida com o código da ficha ORIGINAL (coluna OBSERVAÇÕES do STATUS).
CARACTERISTICA_UNICA_DUPLICADA = "CODIGO PMIB"
CODIGO_CARACTERISTICA_DUPLICADA = "3626"


def extrair_ficha_original(observacoes):
    """Código PMIB da ficha ORIGINAL, lido da coluna OBSERVAÇÕES.

    ⚠️ LEITURA MINHA, NÃO AFIRMAÇÃO DO USUÁRIO: ele disse que o código "vem da
    coluna de OBSERVAÇÕES", mas não disse se a célula contém SÓ o código ou um
    texto com o código no meio. Esta função aceita os dois -- procura o padrão
    de código PMIB em qualquer posição -- porque o caso "só o código" é
    subconjunto do outro. Se a coluna tiver DOIS códigos, devolve o primeiro,
    e isso precisa ser confirmado antes de rodar em lote.
    """
    texto = str(observacoes or "").strip()
    if not texto or texto.lower() == "nan":
        return None
    achado = re.search(r"\d{10}\.\d{4}", texto)
    if achado:
        return achado.group(0)
    # Sem o formato canônico: devolve o texto limpo, para o RPA ao menos
    # tentar -- e o log dirá o que foi digitado.
    return texto or None
