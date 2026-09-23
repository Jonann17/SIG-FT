r"""Casar as características ANTIGAS com as linhas do PDM NOVO, e converter tipo.

É o coração do módulo de correção de PDM, e **onde mora o risco de perder dado
em silêncio**. Depois que o portal troca o PDM a tabela está vazia; o que volta
para a ficha é exatamente o que este módulo disser que volta.

Camada de REGRA PURA: nada aqui fala com o portal. Entra o retrato (E2) e a
tabela nova já lida (E1), sai um `Plano`. Isso é o que torna a matriz de tipos
testável linha por linha, sem navegador.

A REGRA DE OURO
------------------------------------------------------------------------
> Converter só quando a conversão é **sem perda e sem ambiguidade**; no resto,
> não repor e **listar**.

Repor um valor plausível e errado é pior que deixar vazio: o vazio a pessoa vê
e preenche, o errado ela assina. É a mesma lição do prompt de Condições
(2026-08-18).

POR QUE A MATRIZ EXISTE
------------------------------------------------------------------------
Medido no Master: **3160 de 8841 características mudam de tipo entre revisões
do mesmo PDM - 35,7%, em 748 PDMs.** E as seis direções acontecem: em R0->R1
domina CHAR->NUM, mas na amostra de R1->R2 (a transição que o usuário está
vivendo) aparecem também NUM->CHAR e INT->CHAR. Nenhuma aposta.

⚠️ O TIPO VEM SEMPRE DA TELA NOVA, nunca do retrato. Quem chama passa a tabela
lida DEPOIS da troca; o tipo do retrato só serve para saber o que se está
segurando, não para onde vai.

Plano e matriz completa em `docs/refatoracao/CORRECAO_PDM.md` §11.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace

from sigft.core.rpa.caracteristicas import Caracteristica
from sigft.services.tech_specs import juntar_para_char


# Unidade "adimensional". Tratada como AUSÊNCIA de unidade nas conversões: é o
# que `juntar_para_char` escolhe quando junta tudo num texto, e o que 99,8% das
# linhas do Master aceitam.
ADIMENSIONAL = "AD"

_TIPOS_CONHECIDOS = ("CHAR", "NUM", "INT", "LISTA")

# Número como o portal o escreve: pt/es, logo a vírgula decimal é a regra e não
# a exceção. Sem sinal de milhar de propósito -- "1.500" é ambíguo entre mil e
# quinhentos e um vírgula cinco, e ambiguidade aqui é motivo para listar.
_RE_NUMERO = re.compile(r"^[+-]?\d+(?:[.,]\d+)?$")
_RE_NUMERO_COM_SIMBOLO = re.compile(r"^([+-]?\d+(?:[.,]\d+)?)\s+(\S+)$")


def _sem_acento(texto) -> str:
    bruto = str(texto if texto is not None else "")
    return "".join(c for c in unicodedata.normalize("NFKD", bruto)
                   if not unicodedata.combining(c))


def _normalizar(texto) -> str:
    """Caixa alta, sem acento, espaço colapsado."""
    return " ".join(_sem_acento(texto).upper().split())


def chave(caracteristica: Caracteristica) -> str:
    """A chave do casamento: o CÓDIGO, e o nome normalizado quando não há código.

    O código vence porque é imune a tradução (a tela alterna PT/ES) e a
    renomeação - e a Itaipu está mexendo em nome de característica agora.
    Medido no Master: 2278 códigos e 2278 nomes, bijeção perfeita, então cair
    para o nome quando o código não veio é seguro.

    ⚠️ Esta função é EXPORTADA de propósito. É por ela que o serviço (E4)
    reencontra a linha na tela enquanto caminha a tabela nova. Se ele
    calculasse a chave dele, uma diferença de normalização faria a reposição
    pular linhas **em silêncio** - o defeito mais caro que este módulo pode
    ter.
    """
    codigo = str(caracteristica.codigo or "").strip()
    if codigo:
        return f"#{codigo}"
    return f"@{_normalizar(caracteristica.nome)}"


@dataclass(frozen=True)
class Reposicao:
    """Uma característica que VAI ser escrita na ficha nova.

    Os campos são os da linha NOVA, já no formato que ela aceita: quem escreve
    não precisa saber de que tipo o valor veio.
    """

    codigo: str
    nome: str
    tipo: str            # o tipo da TELA NOVA, e é ele que manda
    valor_pt: str = ""
    valor_es: str = ""
    unidade: str = ""
    minimo: str = ""
    maximo: str = ""
    subtipo: str = ""
    tipo_antigo: str = ""
    aviso: str = ""
    # Pode não dar certo, e quem descobre é a TELA: a opção pode não existir
    # na lista. Falhar aqui é normal e vira pendência no serviço, não erro.
    tentativa: bool = False

    @property
    def convertida(self) -> bool:
        return bool(self.tipo_antigo) and self.tipo_antigo != self.tipo


@dataclass(frozen=True)
class Pendencia:
    """Uma característica do retrato que NÃO volta para a ficha.

    Guarda o VALOR de propósito: é com esta lista que a pessoa preenche à mão
    o que o robô não conseguiu devolver. Uma pendência sem o valor só diz que
    algo se perdeu.
    """

    codigo: str
    nome: str
    tipo_antigo: str
    tipo_novo: str   # "" quando a linha nem existe no PDM novo
    valor: str
    motivo: str
    # No campo dela, e nao colada no valor: ver `_como_texto`.
    unidade: str = ""


@dataclass(frozen=True)
class Plano:
    """O que fazer com a ficha, decidido antes de tocar em qualquer campo."""

    repor: tuple[Reposicao, ...] = ()
    converter: tuple[Reposicao, ...] = ()
    nao_casou: tuple[Pendencia, ...] = ()
    sem_valor: tuple[Caracteristica, ...] = ()
    avisos: tuple[str, ...] = ()

    @property
    def escritas(self) -> tuple[Reposicao, ...]:
        """Tudo que vai ser escrito, reposição direta e conversão."""
        return tuple(self.repor) + tuple(self.converter)

    def por_chave(self) -> dict[str, Reposicao]:
        """As escritas indexadas pela mesma `chave()` da tela.

        É como o serviço pergunta *"o que eu escrevo nesta linha?"* enquanto
        caminha a tabela nova, sem depender da ordem das duas listas.
        """
        return {chave(Caracteristica(codigo=r.codigo, nome=r.nome, tipo=r.tipo)): r
                for r in self.escritas}

    def relatorio(self) -> list[str]:
        """As linhas do relatório, para o log e para o arquivo.

        Sai sempre com pelo menos uma linha: um relatório vazio num arquivo de
        saída se confunde com relatório que não rodou.
        """
        linhas = [
            f"Reposicao: {len(self.repor)} direta(s), "
            f"{len(self.converter)} com conversao de tipo."
        ]
        for aviso in self.avisos:
            linhas.append(f"   [Aviso] {aviso}")

        if self.nao_casou:
            linhas.append(f"Nao voltaram para a ficha ({len(self.nao_casou)}):")
            for p in self.nao_casou:
                rotulo = f"{p.codigo}-{p.nome}" if p.codigo else p.nome
                unidade = ""
                if p.unidade and p.unidade.upper() != ADIMENSIONAL:
                    unidade = f" [{p.unidade}]"
                linhas.append(
                    f"   {rotulo}: \"{p.valor}\"{unidade} ({p.motivo})")
        else:
            linhas.append("Nao voltaram para a ficha: nenhuma.")

        if self.sem_valor:
            linhas.append(f"Ficaram em branco, para apagar ({len(self.sem_valor)}):")
            for c in self.sem_valor:
                rotulo = f"{c.codigo}-{c.nome}" if c.codigo else c.nome
                linhas.append(f"   {rotulo}")
        else:
            linhas.append("Ficaram em branco: nenhuma.")
        return linhas


# =============================================================================
# A conversão -- a matriz da §11, uma direção por vez
# =============================================================================
def _partes(antiga: Caracteristica, espanhol=False) -> tuple[str, str]:
    """`(valor, subtipo)` -- o valor SEM a unidade, e o subtipo se for intervalo.

    Um intervalo vira `"min / max"`, que é o formato que o próprio app já usa:
    `tech_specs._preencher_linha` lê a faixa com `val_pt.split("/")`. Só as
    pontas preenchidas entram, porque `MAIOR QUE 10` não tem máximo e
    `"10 / "` seria um texto quebrado escrito na ficha do usuário.

    No espanhol, quando a origem não tem versão ES (as linhas `NUM`, `INT` e
    `LISTA` têm um valor só), espelha o português: deixar o espanhol vazio
    perderia metade da ficha, e número não tem idioma.
    """
    if antiga.tipo == "INT":
        pontas = [p for p in (antiga.minimo, antiga.maximo) if str(p).strip()]
        return " / ".join(pontas), antiga.subtipo
    if espanhol:
        return (antiga.valor_es or antiga.valor_pt), ""
    return (antiga.valor_pt or antiga.valor_es), ""


def _como_texto(antiga: Caracteristica, com_unidade: bool, espanhol=False) -> str:
    """O valor escrito como texto.

    Reusa `juntar_para_char` (de `tech_specs`) em vez de reescrevê-la: é a
    MESMA regra de "valor + unidade + subtipo num texto só" que o robô já
    aplica quando recua de NUM para CHAR. Duas implementações do mesmo
    conceito divergiriam no primeiro ajuste.

    ⚠️ `com_unidade` não é conveniência. Numa conversão que termina em CHAR o
    símbolo TEM de entrar no texto (é o único lugar que sobra para ele); num
    relatório, NÃO: uma linha CHAR com texto `"220 V"` e unidade `A` viraria
    `"220 V A"`, um valor que nunca esteve na ficha. O teste pegou exatamente
    esse caso. No relatório a unidade viaja no seu próprio campo.
    """
    bruto, subtipo = _partes(antiga, espanhol=espanhol)
    return juntar_para_char({
        "RESPOSTA_PT_FINAL": bruto,
        "SIMBOLO": antiga.unidade if com_unidade else "",
        "SUBTIPO_INTERVALO": subtipo,
    })


def _como_numero(antiga: Caracteristica) -> tuple[str, str] | None:
    """`(numero, unidade)` se o texto for um número sem ambiguidade; senão `None`.

    Três casos aceitos, e nenhum deles interpreta nada:

    1. **número puro** (`"220"`, `"1,5"`) - a unidade gravada continua valendo;
    2. **número + o símbolo que JÁ está na unidade** (`"220 V"` com unidade
       `V`) - o texto só repete o que a linha já dizia;
    3. **número + símbolo, com a unidade em `AD` ou vazia** - este é o caminho
       de volta do recuo de 2026-08-18: `"220 V"` com unidade `AD` é
       exatamente o que `juntar_para_char` escreve quando o robô cai de NUM
       para CHAR. `AD` não carrega informação, então trocá-lo por `V` não
       perde nada.

    Fora disso, `None`. *"Aço inox" não vira número* - e `"220 V"` numa linha
    cuja unidade gravada é `A` é uma contradição: os dois não podem estar
    certos, e escolher um seria escolher no escuro.
    """
    texto = " ".join(str(antiga.valor_pt or antiga.valor_es or "").split())
    if not texto:
        return None

    if _RE_NUMERO.match(texto):
        return texto, antiga.unidade

    achado = _RE_NUMERO_COM_SIMBOLO.match(texto)
    if not achado:
        return None

    numero, simbolo = achado.group(1), achado.group(2)
    gravada = _normalizar(antiga.unidade)
    if gravada == _normalizar(simbolo):
        return numero, antiga.unidade
    if gravada in ("", ADIMENSIONAL):
        return numero, simbolo
    return None


def _converter(antiga: Caracteristica, nova: Caracteristica):
    """`(Reposicao, "")` quando dá para levar o valor; `(None, motivo)` quando
    não dá. O `motivo` é o que a pessoa lê no relatório."""
    de, para = antiga.tipo, nova.tipo

    def posta(**campos):
        return Reposicao(codigo=nova.codigo or antiga.codigo,
                         nome=nova.nome or antiga.nome,
                         tipo=para, tipo_antigo=de, **campos), ""

    if not de or de not in _TIPOS_CONHECIDOS:
        return None, ("nao foi possivel identificar o tipo da linha antiga, "
                      "entao nao da para saber o que ela guardava")
    if not para or para not in _TIPOS_CONHECIDOS:
        return None, ("a linha nova nao se parece com nenhum tipo conhecido; "
                      "preencher seria palpite")

    if de == para:
        return posta(valor_pt=antiga.valor_pt, valor_es=antiga.valor_es,
                     unidade=antiga.unidade, minimo=antiga.minimo,
                     maximo=antiga.maximo, subtipo=antiga.subtipo)

    if para == "CHAR":
        # Sem perda: valor, unidade e subtipo cabem inteiros num texto. A
        # unidade vai para AD porque o simbolo JA esta dentro do texto.
        return posta(valor_pt=_como_texto(antiga, com_unidade=True),
                     valor_es=_como_texto(antiga, com_unidade=True, espanhol=True),
                     unidade=ADIMENSIONAL)

    if para == "NUM":
        numero = _como_numero(antiga) if de in ("CHAR", "LISTA") else None
        if numero:
            return posta(valor_pt=numero[0], unidade=numero[1])
        if de == "INT":
            return None, ("de INT para NUM: dois valores nao cabem num campo "
                          "so, e escolher um perderia o outro")
        return None, (f"de {de} para NUM: o valor nao e um numero")

    if para == "LISTA":
        # A tela e que sabe quais opcoes existem, e esta camada nao fala com o
        # portal. Entrega os dois idiomas como candidatos, como
        # `_preencher_linha` ja faz, e quem escreve decide.
        return posta(valor_pt=_como_texto(antiga, com_unidade=False),
                     valor_es=_como_texto(antiga, com_unidade=False, espanhol=True),
                     unidade=antiga.unidade, tentativa=True)

    # para == "INT"
    return None, (f"de {de} para INT: definir minimo e maximo a partir deste "
                  "valor exigiria interpretar o texto")


# =============================================================================
# O casamento
# =============================================================================
def casar(retrato, caracteristicas_novas) -> Plano:
    """Decide, antes de tocar em qualquer campo, o que vai para onde.

    `retrato` é o de `correcao_pdm_retrato` (ou qualquer objeto com
    `.caracteristicas`); `caracteristicas_novas` é a tabela lida DEPOIS da
    troca de PDM.

    Quatro listas saem daqui, e toda característica com valor cai em
    exatamente uma delas. O silêncio é o único resultado inaceitável: uma
    direção esquecida na matriz sumiria sem erro nenhum.
    """
    novas = list(caracteristicas_novas or ())

    # Índice das linhas novas por chave. Lista por chave, e não um valor só:
    # se a tabela repetir um código, a segunda linha ainda tem que ter dono.
    disponiveis: dict[str, list[int]] = {}
    for posicao, nova in enumerate(novas):
        disponiveis.setdefault(chave(nova), []).append(posicao)

    repor: list[Reposicao] = []
    converter: list[Reposicao] = []
    nao_casou: list[Pendencia] = []
    avisos: list[str] = []
    atendidas: set[int] = set()   # posicoes na tabela nova, nao objetos

    for antiga in getattr(retrato, "caracteristicas", ()) or ():
        # Vazia no retrato não é perda: não havia nada. Listá-la encheria o
        # relatório de linhas que a pessoa não precisa conferir -- e ruído num
        # relatório é como uma perda de verdade passa batida.
        if antiga.esta_vazia:
            continue

        fila = disponiveis.get(chave(antiga)) or []
        posicao = fila.pop(0) if fila else None
        nova = novas[posicao] if posicao is not None else None

        if nova is None:
            nao_casou.append(Pendencia(
                codigo=antiga.codigo, nome=antiga.nome, tipo_antigo=antiga.tipo,
                tipo_novo="", valor=_como_texto(antiga, com_unidade=False),
                unidade=antiga.unidade,
                motivo="o PDM novo nao tem esta caracteristica"))
            continue

        posta, motivo = _converter(antiga, nova)
        if posta is None:
            nao_casou.append(Pendencia(
                codigo=antiga.codigo, nome=antiga.nome, tipo_antigo=antiga.tipo,
                tipo_novo=nova.tipo, valor=_como_texto(antiga, com_unidade=False),
                unidade=antiga.unidade, motivo=motivo))
            continue

        # Nome diferente é AVISO, não bloqueio: o nome é conferência, o código
        # é a chave. Mas quem revisa a ficha depois precisa ver que os dois
        # não batem.
        if (antiga.codigo and nova.nome
                and _normalizar(antiga.nome) != _normalizar(nova.nome)):
            aviso = (f"{antiga.codigo}: o retrato chama de \"{antiga.nome}\" e "
                     f"o PDM novo chama de \"{nova.nome}\"")
            posta = replace(posta, aviso=aviso)
            avisos.append(aviso)

        atendidas.add(posicao)
        (converter if posta.convertida else repor).append(posta)

    # As linhas novas que não recebem nada e já estão em branco: requisito 6 do
    # usuário, *"apagar todas as características que ficaram em branco e se
    # possível colocar num relatório"*.
    #
    # ⚠️ "já está em branco" importa. Logo depois da troca a tabela inteira
    # está vazia, mas o módulo também roda no modo "só repor", sobre uma ficha
    # em que alguém pode ter digitado algo. Apagar isso seria apagar trabalho
    # humano.
    sem_valor = [n for i, n in enumerate(novas)
                 if i not in atendidas and n.esta_vazia]

    return Plano(repor=tuple(repor), converter=tuple(converter),
                 nao_casou=tuple(nao_casou), sem_valor=tuple(sem_valor),
                 avisos=tuple(avisos))
