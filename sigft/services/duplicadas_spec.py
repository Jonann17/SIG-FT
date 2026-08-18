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

import unicodedata

from sigft.core.excel import pmib_codes

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


# Como o módulo ANTIGO decide, e a resposta mudou depois de ler a TELA:
# `ficha_duplicada.montar_fila_processamento` tem `marcador_duplicada` como
# PARÂMETRO, com default `"DUPLICADA"` -- mas a tela (`ModuloCopiaFichas.
# _worker_leitura_excel`) sempre passou `"PDM.9900.000"`. Ou seja, o default
# nunca rodou em produção: o que roda é SUBSTRING do código, e a diferença
# para a regra nova é só uma:
#
#   - código presente mas NÃO no começo ("usado PDM.9900.000") -> o antigo
#     pega, o novo não;
#   - só a palavra "DUPLICADA", sem o código -> NENHUM dos dois pega (o
#     antigo tampouco, apesar do nome do parâmetro sugerir que sim).
#
# A regra que vale é a do usuário (prefixo, ver acima). Mas "pegar de menos" é
# o erro caro: a ficha some da lista sem nenhum sintoma, e ninguém procura o
# que não apareceu. Por isso o serviço passa as NÃO casadas por aqui e avisa --
# a decisão continua sendo do usuário, agora com a informação na tela.
MARCADOR_DUPLICADA_LEGADO = "DUPLICADA"


def parece_duplicada_sem_o_pdm(valor_pdm_usado):
    """A linha cheira a duplicada mas não casa a regra? (só para AVISAR)

    Dois casos, e o primeiro é o que de fato diverge do módulo antigo:

      1. o código `PDM.9900.000` está no texto mas NÃO no começo -- a regra
         antiga (substring) pega, a nova (prefixo) não;
      2. a palavra "DUPLICADA" sem o código -- nenhuma das duas pega, mas é
         justamente o caso em que a planilha pode estar mal preenchida, e vale
         o aviso.
    """
    if e_ficha_duplicada(valor_pdm_usado) or valor_pdm_usado is None:
        return False
    texto = str(valor_pdm_usado).strip()
    if not texto or texto.lower() == "nan":
        return False
    maiusculo = _sem_acento(texto).upper()
    return (PDM_DUPLICADA.upper() in maiusculo
            or MARCADOR_DUPLICADA_LEGADO in maiusculo)


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
    r"""Código PMIB da ficha ORIGINAL, lido da coluna OBSERVAÇÕES.

    Confirmado pelo usuário: *"haverá sempre só um código nessa estrutura; às
    vezes pode ter mais texto, mas haverá apenas um código se o PDM for o
    correto"*.

    DELEGA para `core.excel.pmib_codes.find_pmib_code_in_text`, e essa correção
    tem história: a primeira versão desta função tinha um `re.search` PRÓPRIO,
    com o padrão `\d{10}\.\d{4}`. Era reimplementação -- o projeto já tem o
    extrator canônico desde o CP 1.2, criado exatamente a partir desta mesma
    coluna do `_STATUS_PMIB` (a réplica do `montar_fila_processamento` do
    módulo antigo). E não era só redundância: o canônico aceita fração de
    QUALQUER número de dígitos (`\d{10}\.\d+`), enquanto o meu exigia
    exatamente 4 -- um código como `4500063671.11651` seria ignorado pelo meu e
    achado pelo dele.

    O princípio nº 1 da arquitetura-alvo é "uma implementação por conceito", e
    "achar código PMIB em texto livre" é um conceito só.
    """
    texto = str(observacoes or "").strip()
    if not texto or texto.lower() == "nan":
        return None
    achado = pmib_codes.find_pmib_code_in_text(texto)
    if achado:
        return achado
    # Sem o formato canônico: devolve o texto limpo, para o RPA ao menos
    # tentar -- e o log dirá o que foi digitado.
    return texto or None


# ---------------------------------------------------------------------------
# 6. Leitura do modo de visualização: parear rótulo com valor
# ---------------------------------------------------------------------------
# A tela de visualização repete a mesma estrutura para todo campo: um
# `<label>` e, logo depois, um bloco `PMIB_DataSheetView.Block_Expression` com
# o valor. Não há id útil ligando os dois -- o que liga é a ORDEM DE DOCUMENTO.
#
# Daí a estratégia: uma varredura só, pedindo rótulos e valores na mesma
# consulta (`XPATH_VIEW_ROTULOS_E_VALORES`, um `|` de XPath, que devolve em
# ordem de documento) e pareando aqui. Duas varreduras separadas obrigariam a
# casar por índice, e bastaria um campo sem valor para desalinhar tudo dali
# para baixo -- o tipo de erro que produz ficha plausível e errada.


def parear_rotulos_e_valores(tokens):
    """{rótulo: valor} a partir da sequência `("rotulo"|"valor", texto)` em
    ordem de documento.

    Regras, e cada uma existe por um caso da tela real:

      - **cada valor pertence ao rótulo imediatamente anterior.** É o que a
        estrutura garante;
      - **rótulo sem valor** (campo em branco na ficha) vira `""`, e NÃO some.
        Sumir seria pior: o injetor não saberia distinguir "não existe esse
        campo" de "existe e está vazio", e o segundo caso é informação;
      - **valor sem rótulo antes** é descartado. Acontece com texto solto no
        bloco (o título do fieldset, por exemplo); atribuí-lo ao rótulo
        seguinte inverteria o pareamento de toda a aba;
      - **rótulo repetido** fica com o PRIMEIRO valor. O portal repete rótulo
        entre abas (ex.: "Peso líquido"), e o extrator é chamado por aba --
        dentro de uma aba, repetição é sinal de estrutura inesperada, e
        sobrescrever esconderia isso.

    A regra vale para os DOIS padrões de campo da tela, que são estruturalmente
    opostos (ver `seletores_duplicada`, §7 e §7b):

      - campo de texto: rótulo em `<label><span>`, valor em
        `Block_Expression > span[@data-expression]`;
      - opção marcada (rádio): rótulo em `<span class="text-primary">`, valor
        DENTRO de um `<label data-label>`.

    Quem classifica cada token é o extrator, pelos seletores. Aqui só chega
    `("rotulo"|"valor", texto)` em ordem de documento -- e é justamente por
    isso que a mesma regra atende os dois: a ordem é a mesma, só a origem
    muda.
    """
    pares = {}
    rotulo_atual = None
    for tipo, texto in tokens:
        limpo = " ".join(str(texto or "").split())
        if tipo == "rotulo":
            if not limpo:
                continue
            rotulo_atual = limpo
            pares.setdefault(rotulo_atual, "")
        elif tipo == "valor":
            if rotulo_atual is None:
                continue
            if not pares.get(rotulo_atual):
                pares[rotulo_atual] = limpo
    return pares


# A coluna que guarda "MARCA / MODELO" juntos. O FABRICANTE da ficha duplicada
# sai daqui -- confirmado pelo usuário em 2026-08-17: *"você sabe que tem, já
# te pedi para mapear no conhecimento do _STATUS_PMIB todas as informações que
# temos hoje"*. Estava mapeado em `config.COL_MARCA_MODELO` desde 2026-08-13,
# e eu perguntei em vez de olhar.
COLUNAS_MARCA_MODELO = ("MARCA/MODELO", "MARCA / MODELO", "MARCA")
