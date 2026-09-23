r"""LER a tabela de Características Técnicas do portal PMIB.

O pedaço que faltava. Até 2026-09-23 o app sabia **escrever** uma
característica (`tech_specs._preencher_linha`) e **apagar** (`duplicadas_injetor.
limpar_caracteristicas`), mas nunca precisou LER o valor de uma.

O módulo de correção de PDM precisa: trocar o PDM faz o portal apagar TODAS as
características — inclusive as que o PDM novo também tem e que continuariam
válidas. A saída é fotografar antes e repor depois, e a foto é isto aqui.

Plano completo em `docs/refatoracao/CORRECAO_PDM.md`.

O QUE ESTE MÓDULO HERDA, E NÃO REDESCOBRE
------------------------------------------------------------------------
1. **O tipo vem da TELA, não de quem chama.** É a regra de
   `tech_specs._tipo_da_linha`, e o número que a justifica foi medido no
   Master: **3160 de 8841 características mudam de tipo entre revisões do
   mesmo PDM — 35,7%, em 748 PDMs.** Um tipo declarado é palpite.
2. **`INT` é testado antes de `NUM`**: a linha de intervalo tem dois inputs
   numéricos e casaria como `NUM` por engano.
3. **A descrição é lida por `textContent`** (o contrato de `RPAEngine.texto()`
   garante isso). Numa tabela rolável, a célula fora da viewport devolve
   string VAZIA em texto visível — e descrição vazia faria o casamento
   inteiro falhar em silêncio.
4. **A paginação**, com teto — o mesmo laço de `limpar_caracteristicas`, sem
   o apagar.

⚠️ SELETORES DUPLICADOS, DE PROPÓSITO. Os mesmos XPaths vivem em
`seletores_duplicada.py` e em `services/tech_specs.py`. Unificar os três é o
certo e **não foi feito agora**, por decisão do usuário em 2026-09-23: aqueles
dois módulos rodam contra o portal real hoje, e mexer neles junto com código
novo misturaria "o que pode falhar" com "o que funciona". A dívida está
registrada em `docs/refatoracao/PENDENCIAS.md`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


# =============================================================================
# Seletores -- copiados de `seletores_duplicada.py` / `tech_specs.py`
# =============================================================================
XPATH_ABA = "//button[@role='tab' and contains(., 'Características técnicas')]"

# ⚠️ `_Content`, E NÃO SÓ `TechnicalCharacteristics`. Medido no recorte real do
# portal (2026-09-23): o id aparece DUAS vezes na página, no painel
# (`b10-TechnicalCharacteristics_Content`) e no cabeçalho da aba
# (`..._Header`). Hoje o cabeçalho não tem tabela dentro, então a versão larga
# funcionava -- por sorte, não por desenho.
XPATH_SECAO = "//div[contains(@id, 'TechnicalCharacteristics_Content')]"
XPATH_LINHAS = XPATH_SECAO + "//table/tbody/tr"

# ⚠️ ESCOPADO À SEÇÃO. Medido no recorte real de 2026-09-23: o `aria-label`
# NÃO é exclusivo -- a aba "Aplicação - LMR" tem a própria paginação, com o
# mesmo rótulo, e o seletor de página inteira casa os DOIS.
#
# Hoje isso não quebra, e é importante não exagerar: `PlaywrightEngine._loc`
# usa `.first` de propósito (ver a docstring dele), então um seletor ambíguo
# não levanta -- ele age sobre o primeiro em ordem de documento, que nesta
# página é justamente o da tabela de características.
#
# O que se conserta aqui é a DEPENDÊNCIA DE ORDEM. "Está habilitado?" e "clica
# na próxima" passariam a falar de outra tabela no dia em que um painel
# renderizado antes mostrasse a paginação dele -- e o sintoma seria a leitura
# parar cedo, com o retrato saindo incompleto e a troca de PDM apagando o
# resto. Escopar custa uma concatenação e tira a sorte do caminho.
XPATH_PROXIMA_PAGINA = (
    XPATH_SECAO + "//button[@aria-label='Ir para a página seguinte']")

# Relativos à linha. Sozinhos casariam a célula de QUALQUER linha.
#
# ⚠️ SEM O PONTO INICIAL, e isso não é estilo. Eles são SOMADOS ao seletor da
# linha, e `(//...//tr)[3]` + `.//td` **não é XPath válido** -- não existe `.`
# depois de `]` sem uma barra. O `lxml` responde `XPathEvalError: Invalid
# expression`, e o Playwright levanta igual.
#
# Foi assim que a primeira execução real, em 2026-09-23, gravou um retrato com
# uma entrada por linha e TODOS os campos vazios: a expressão levantava, os
# `try/except` de `_texto`/`_valor`/`_existe` engoliam (eles existem para que
# ler a tela não derrube a ficha) e devolviam `""` para tudo.
#
# `tech_specs` guarda os dele já com `//`; `duplicadas_injetor` guarda com `.`
# e corta na hora (`[1:]`). Aqui a soma passa por `dentro_da_linha`, que corta
# de qualquer jeito -- mas os relativos nascem certos, para que o call site não
# dependa disso. Ver `tests/test_correcao_pdm_xpath_real.py`.
REL_DESCRICAO = "//td[contains(@data-header, 'Descrição')]"
REL_VALOR_PT = '//textarea[contains(@id, "TextArea_ValuePT")]'
REL_VALOR_ES = '//textarea[contains(@id, "TextArea_ValueES")]'
REL_INPUT_NUM = '//input[contains(@id, "NumberValue_Input")]'
REL_INPUT_MIN = '//input[contains(@id, "MinValue_Input")]'
REL_INPUT_MAX = '//input[contains(@id, "MaxValue_Input")]'
REL_SELECT_LISTA = '//select[contains(@id, "Dropdown1")]'
REL_SELECT_INTERVALO = '//select[contains(@id, "Dropdown_IntervalOptions")]'
REL_SELECT_UNIDADE = '//select[contains(@id, "DropdownTCUnitsOfMeasurement")]'

# Teto de páginas. Um botão "próxima" que nunca desabilita giraria para
# sempre; `limpar_caracteristicas` tem o mesmo teto, pelo mesmo motivo.
MAX_PAGINAS = 50

_RE_CODIGO_E_NOME = re.compile(r"^\s*(\d+)\s*-\s*(.*)$", re.DOTALL)


def seletor_da_linha(indice: int) -> str:
    """O endereço da linha `indice` (1-based) da tabela.

    Mora aqui, ao lado de `XPATH_LINHAS`, para que quem LÊ e quem ESCREVE
    usem a mesma base: ler a linha 3 e escrever na 4 seria o defeito perfeito,
    silencioso e destrutivo.
    """
    return f"({XPATH_LINHAS})[{indice}]"


# O símbolo da unidade, dentro do rótulo da opção.
#
# ⚠️ NO PORTAL O SÍMBOLO VEM NA FRENTE: `(AD) ADIMENSIONAL`. Medido no recorte
# real de 2026-09-23. A docstring de `tech_specs.selecionar_dropdown_unidade`
# dá o exemplo `"Milímetro (MM)"`, que está desatualizado -- ela só continua
# funcionando porque procura `"(AD)"` como SUBSTRING, em qualquer posição.
#
# O combo de unidade de ESTOQUE, na mesma tela, escreve ao contrário
# (`UNIDADE - (UN)`). Aguentar as duas formas custa uma linha, então as duas
# entram: primeiro o grupo no INÍCIO, senão o do FIM.
_RE_SIMBOLO_NA_FRENTE = re.compile(r"^\(([^()]+)\)")
_RE_SIMBOLO_NO_FIM = re.compile(r"\(([^()]+)\)\s*$")

# O texto da primeira `<option>` quando nada foi escolhido. Ele NÃO é uma
# unidade: mandá-lo para o retrato faria "Selecionar" ser escrito na ficha.
_PLACEHOLDERS = ("SELECIONAR", "SELECIONE")


def simbolo_da_unidade(rotulo) -> str:
    """`"(AD) ADIMENSIONAL"` -> `"AD"`. Sem parênteses, devolve o texto inteiro.

    ⚠️ O SIMBOLO, E NAO O ROTULO, e isso tem consequencia em tres lugares:

    1. `juntar_para_char` escreve o simbolo DENTRO do texto quando a linha cai
       de NUM para CHAR -- com o rotulo, a ficha receberia `"220 Volt (V)"`;
    2. `correcao_pdm_casamento._como_numero` so desfaz o recuo de 2026-08-18
       quando a unidade gravada e `AD`; com o rotulo, o caminho de volta
       NUM->CHAR->NUM deixa de funcionar;
    3. o relatorio omite a unidade quando ela e `AD` (ela nao carrega
       informacao); com o rotulo, imprimiria `[Adimensional (AD)]` em toda
       linha CHAR.

    E quem escreve de volta (`tech_specs.selecionar_dropdown_unidade`) casa
    `"(AD)"` dentro do texto da opcao: o simbolo e a forma que fecha o ciclo.

    Sem parenteses devolve o texto inteiro -- devolver vazio perderia a
    unidade, e o casamento por sigla solta daquele modulo ainda tem chance.
    """
    texto = " ".join(str(rotulo or "").split())
    if texto.upper().startswith(_PLACEHOLDERS):
        return ""
    achado = _RE_SIMBOLO_NA_FRENTE.match(texto) or _RE_SIMBOLO_NO_FIM.search(texto)
    return achado.group(1).strip() if achado else texto


def dentro_da_linha(seletor_linha: str, relativo: str) -> str:
    """Endereça um campo DENTRO da linha. **É a única soma permitida.**

    Corta o ponto inicial do relativo, se houver: `(...)[3]` + `.//td` não é
    XPath válido, e a expressão inválida levanta dentro de um `try/except` que
    devolve string vazia -- o defeito some. Ver o aviso nos relativos acima.
    """
    return seletor_linha + str(relativo or "").lstrip(".")


def codigo_e_nome(descricao):
    """`"1064-CORRENTE NOMINAL"` -> `("1064", "CORRENTE NOMINAL")`.

    O CÓDIGO é a chave do casamento antigo↔novo, e não o nome. Medido no
    Master: 2278 códigos distintos e 2278 nomes distintos, **sem uma única
    ambiguidade nos dois sentidos** — é uma bijeção. Mesmo assim o código
    vence, porque é imune a tradução (a tela alterna PT/ES) e a renomeação,
    e a Itaipu está mexendo em nomes de características agora.

    Sem código reconhecível, devolve `("", nome)` — quem casa decide o que
    fazer com isso. Inventar um código aqui seria pior que não ter.
    """
    texto = " ".join(str(descricao or "").split())
    achado = _RE_CODIGO_E_NOME.match(texto)
    if achado:
        return achado.group(1), " ".join(achado.group(2).split())
    return "", texto


@dataclass(frozen=True)
class Caracteristica:
    """Uma linha da tabela, como ela está no portal AGORA."""

    codigo: str
    nome: str
    tipo: str          # CHAR | NUM | INT | LISTA | "" (não deu para saber)
    valor_pt: str = ""
    valor_es: str = ""
    unidade: str = ""
    minimo: str = ""
    maximo: str = ""
    subtipo: str = ""  # o "ENTRE"/"MAIOR QUE"... do tipo INT

    @property
    def esta_vazia(self) -> bool:
        """A linha não tem VALOR nenhum.

        A unidade NÃO conta: ela vem escolhida por padrão em muitas linhas, e
        tratá-la como valor faria o módulo concluir que a ficha inteira está
        preenchida. Valor só em espanhol TAMBÉM conta como preenchido — meia
        ficha ainda é informação, e apagá-la perderia o que o fornecedor
        escreveu.
        """
        return not any((self.valor_pt, self.valor_es, self.minimo, self.maximo))


def _texto(engine, seletor):
    try:
        return " ".join(str(engine.texto(seletor) or "").split())
    except Exception:  # noqa: BLE001 -- ler a tela não derruba a ficha
        return ""


def _valor(engine, seletor):
    """Valor de um campo, ou `""` se o campo não existe naquela linha.

    O `contar` antes é o que evita pagar o timeout do motor por cada campo
    ausente — e numa linha `CHAR` seis dos nove campos estão ausentes.
    """
    try:
        if not engine.contar(seletor):
            return ""
        return str(engine.get_value(seletor) or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def _selecionado(engine, seletor):
    try:
        if not engine.contar(seletor):
            return ""
        return str(engine.texto_selecionado(seletor) or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def _existe(engine, seletor):
    try:
        return bool(engine.element_exists(seletor))
    except Exception:  # noqa: BLE001
        return False


def tipo_da_linha(engine, seletor_linha):
    """Que tipo de campo ESTA linha oferece? `""` quando não dá para saber.

    Mesma lógica e MESMA ORDEM de `tech_specs._tipo_da_linha` -- `INT` antes
    de `NUM` porque a linha de intervalo tem dois inputs numéricos e casaria
    como `NUM`.
    """
    if _existe(engine, dentro_da_linha(seletor_linha, REL_VALOR_PT)):
        return "CHAR"
    if (_existe(engine, dentro_da_linha(seletor_linha, REL_SELECT_INTERVALO))
            and _existe(engine, dentro_da_linha(seletor_linha, REL_INPUT_MIN))):
        return "INT"
    if _existe(engine, dentro_da_linha(seletor_linha, REL_SELECT_LISTA)):
        return "LISTA"
    if _existe(engine, dentro_da_linha(seletor_linha, REL_INPUT_NUM)):
        return "NUM"
    return ""


def ler_linha(engine, seletor_linha) -> Caracteristica:
    """Uma linha da tabela, inteira.

    Lê só os campos do tipo que a TELA oferece: perguntar por todos em toda
    linha custaria seis buscas inúteis por linha, e a tabela tem dezenas.
    """
    codigo, nome = codigo_e_nome(_texto(engine, dentro_da_linha(seletor_linha, REL_DESCRICAO)))
    tipo = tipo_da_linha(engine, seletor_linha)
    unidade = simbolo_da_unidade(
        _selecionado(engine, dentro_da_linha(seletor_linha, REL_SELECT_UNIDADE)))

    valor_pt = valor_es = minimo = maximo = subtipo = ""
    if tipo == "CHAR":
        valor_pt = _valor(engine, dentro_da_linha(seletor_linha, REL_VALOR_PT))
        valor_es = _valor(engine, dentro_da_linha(seletor_linha, REL_VALOR_ES))
    elif tipo == "NUM":
        valor_pt = _valor(engine, dentro_da_linha(seletor_linha, REL_INPUT_NUM))
    elif tipo == "INT":
        minimo = _valor(engine, dentro_da_linha(seletor_linha, REL_INPUT_MIN))
        maximo = _valor(engine, dentro_da_linha(seletor_linha, REL_INPUT_MAX))
        subtipo = _selecionado(engine, dentro_da_linha(seletor_linha, REL_SELECT_INTERVALO))
    elif tipo == "LISTA":
        # Pelo TEXTO da opção, não pelo `value`: quem repõe é
        # `selecionar_por_texto`, que casa por label.
        valor_pt = _selecionado(engine, dentro_da_linha(seletor_linha, REL_SELECT_LISTA))

    return Caracteristica(
        codigo=codigo, nome=nome, tipo=tipo, valor_pt=valor_pt,
        valor_es=valor_es, unidade=unidade, minimo=minimo, maximo=maximo,
        subtipo=subtipo,
    )


def ler_tabela(engine) -> list[Caracteristica]:
    """A tabela inteira, atravessando as páginas.

    Ler só a primeira página perderia o resto da ficha em silêncio -- é o
    mesmo motivo pelo qual `limpar_caracteristicas` pagina.

    Ao contrário dela, aqui o índice **sempre avança**: nada é apagado, então
    a tabela não encolhe embaixo do laço.
    """
    lidas = []
    for _pagina in range(MAX_PAGINAS):
        total = engine.contar(XPATH_LINHAS)
        for indice in range(1, total + 1):
            lidas.append(ler_linha(engine, seletor_da_linha(indice)))

        if not _existe(engine, XPATH_PROXIMA_PAGINA):
            break
        try:
            if not engine.esta_habilitado(XPATH_PROXIMA_PAGINA):
                break
        except Exception:  # noqa: BLE001
            break
        engine.click_raw(XPATH_PROXIMA_PAGINA)
    return lidas
