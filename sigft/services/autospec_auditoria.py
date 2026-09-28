r"""A conferencia das respostas que o FORNECEDOR escreveu, contra o datasheet.

POR QUE ESTE MODULO EXISTE (2026-09-28, pedido do Luan)
------------------------------------------------------------------------
O AutoSpec so olhava celula VAZIA. O que o fornecedor escreveu passava sem
conferencia nenhuma -- inclusive o "nao se aplica" que ele escreve por
desleixo, com a caracteristica bem ali no datasheet. Duas regras do usuario:

1. "nao se aplica" (e afins, ver `ficha_layout.e_nao_se_aplica`) com o valor
   no documento e a PROVA conferida: grava o valor do documento, e a resposta
   original fica no comentario da celula;
2. valor preenchido que DIVERGE do documento: so no log. Nada e gravado.

Spec: docs/superpowers/specs/2026-09-28-autospec-conferencia-fornecedor-design.md

Aqui ficam as pecas puras, sem Excel e sem IA: ler a resposta, comparar dois
valores, montar a lista do prompt e o log. A decisao de cada campo usa a
conferencia pela prova (`autospec.AutoSpecCore._conferir_pela_prova`) e mora
no `AutoSpecCore`, que conhece o documento -- mesma divisao de
`autospec_evidencia`.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

from sigft.services import autospec_evidencia as ev

SITUACOES = ("confere", "diverge", "nao_consta")

# Resposta do fornecedor maior que isto vai cortada para o prompt: a
# conferencia e do DADO, e um paragrafo inteiro so gasta token.
TETO_RESPOSTA_NO_PROMPT = 300


@dataclass
class ItemAuditado:
    """O que a IA disse sobre UMA resposta do fornecedor."""

    situacao: str = "nao_consta"
    valor_documento: str = ""
    prova: ev.Evidencia = field(default_factory=ev.Evidencia)


def _sem_acento(texto):
    s = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _situacao(escrita):
    """`confere`, `diverge` ou `nao_consta`. Na duvida, `nao_consta`: e o
    unico dos tres que nao leva a nada gravado nem apontado."""
    t = " ".join(_sem_acento(escrita).replace("_", " ").split())
    if t.startswith(("diverg", "nao confere", "diferente", "incorret", "errad")):
        return "diverge"
    if t.startswith(("confer", "ok", "igual", "corret")):
        return "confere"
    return "nao_consta"


def ler_resposta(bruto, ids):
    """`{campo: ItemAuditado}` da resposta crua da IA.

    Envelope (`{"respostas": {...}}`) e desembrulhado com o criterio de
    `autospec_evidencia.extrair_evidencias`, que tambem le a prova. Campo nao
    pedido e ignorado. Resposta que nao e um objeto levanta `ValueError`: e
    formato errado, nao "nada a apontar".
    """
    pedidos = set(ids or ())
    for _ in range(3):
        if (pedidos and isinstance(bruto, dict) and len(bruto) == 1
                and next(iter(bruto)) not in pedidos
                and isinstance(next(iter(bruto.values())), dict)):
            bruto = next(iter(bruto.values()))
            continue
        break
    if not isinstance(bruto, dict):
        raise ValueError(
            f"A IA devolveu {type(bruto).__name__} na conferencia do fornecedor; o "
            f"formato pedido e um objeto JSON {{ID: {{situacao: ...}}}}.")

    provas = ev.extrair_evidencias(bruto, campos_pedidos=pedidos)
    itens = {}
    for campo, conteudo in bruto.items():
        if campo not in pedidos:
            continue
        if isinstance(conteudo, dict):
            itens[campo] = ItemAuditado(
                situacao=_situacao(conteudo.get("situacao")),
                valor_documento=str(conteudo.get("valor_documento") or "").strip(),
                prova=provas.get(campo) or ev.Evidencia(),
            )
        elif isinstance(conteudo, str):
            itens[campo] = ItemAuditado(situacao=_situacao(conteudo))
    return itens


def _chave_texto(texto):
    return " ".join(_sem_acento(texto).strip(" .;:,!").split())


def _com_unidade(valor, pergunta):
    try:
        from sigft.services import autospec_unidades

        return autospec_unidades.aplicar_unidade_da_pergunta(valor, pergunta)
    except Exception:
        return valor


def equivalentes(fornecedor, documento, pergunta=""):
    """O fornecedor e o documento dizem a MESMA coisa?

    Existe para o log nao se encher de alarme falso: a IA as vezes aponta
    `24 Vcc` x `24 VDC`. Duas regras:

    - o mesmo texto, sem acento, caixa e pontuacao de borda;
    - com numero: todo numero de um lado sai do outro, nos DOIS sentidos,
      literal ou por conversao refeita pelo `autospec_unidades`
      (`0,5 kW` = `500 W`). `220 V` x `220/380 V` nao e equivalente: o
      documento diz mais do que o fornecedor.

    Texto sem numero e diferente (`Aco inox` x `Stainless steel`) fica com o
    julgamento da IA -- traducao nao e algo que o app saiba conferir.
    """
    a, b = str(fornecedor or "").strip(), str(documento or "").strip()
    if not a or not b:
        return False
    if _chave_texto(a) == _chave_texto(b):
        return True
    if not (ev.tem_numero(a) and ev.tem_numero(b)):
        return False
    a, b = _com_unidade(a, pergunta), _com_unidade(b, pergunta)
    return ev.valor_sai_do_trecho(a, b)[0] and ev.valor_sai_do_trecho(b, a)[0]


def montar_lista(respostas):
    """As respostas do fornecedor, uma por linha, para o fim do prompt."""
    linhas = []
    for campo, info in respostas.items():
        resposta = " ".join(str(info.get("resposta") or "").split())
        resposta = resposta[:TETO_RESPOSTA_NO_PROMPT]
        pergunta = info.get("desc") or campo
        linhas.append(f"- ID '{campo}': {pergunta} -> o fornecedor respondeu: \"{resposta}\"")
    return "\n".join(linhas)


@dataclass
class ResultadoAuditoria:
    """O que a conferencia de UMA ficha decidiu.

    `gravar`/`campos`/`notas` tem o formato do preenchimento (`ai_data`,
    `missing`, `notas_por_campo`), para entrarem no MESMO `fill_save`.
    """

    gravar: dict = field(default_factory=dict)
    campos: dict = field(default_factory=dict)
    notas: dict = field(default_factory=dict)
    na_preenchidos: list = field(default_factory=list)  # (desc, fornecedor, valor, onde)
    divergencias: list = field(default_factory=list)    # (desc, forn., doc., onde, trecho, just.)
    na_mantidos: int = 0
    conferem: int = 0
    sem_dado: int = 0
    descartados: list = field(default_factory=list)     # (desc, motivo)
    falha: str | None = None
    sem_documento: bool = False

    def linhas_de_log(self):
        """`[(nivel, texto)]` para o console. Vazio quando nada foi conferido."""
        linhas = []
        if self.na_preenchidos:
            linhas.append(("warn", (
                f"{len(self.na_preenchidos)} resposta(s) \"nao se aplica\" do fornecedor ESTAO no "
                f"documento: gravei o valor do documento (em azul), e a resposta original "
                f"ficou no comentario da celula:")))
            for desc, fornecedor, valor, onde in self.na_preenchidos:
                linhas.append(("warn", (
                    f"      · {desc[:60]}: fornecedor {fornecedor[:30]!r} -> documento "
                    f"{valor[:40]!r} ({onde})")))
        if self.divergencias:
            linhas.append(("warn", (
                f"{len(self.divergencias)} divergencia(s) entre a resposta do fornecedor e o "
                f"documento. NADA foi alterado na ficha; confira:")))
            for desc, fornecedor, valor, onde, trecho, justificativa in self.divergencias:
                linhas.append(("warn", (
                    f"      · {desc[:60]}: fornecedor {fornecedor[:40]!r} x documento "
                    f"{valor[:40]!r} ({onde})")))
                if trecho:
                    linhas.append(("warn", f"        trecho: \"{trecho[:120]}\""))
                if justificativa:
                    linhas.append(("warn", f"        por que: {justificativa[:120]}"))
        if self.na_mantidos:
            linhas.append(("info", (
                f"{self.na_mantidos} resposta(s) \"nao se aplica\" conferida(s): o documento "
                f"nao traz o dado, ficou o que o fornecedor escreveu.")))
        if self.conferem or self.sem_dado:
            linhas.append(("info", (
                f"{self.conferem} resposta(s) conferem com o documento; {self.sem_dado} o "
                f"documento nao traz.")))
        if self.descartados:
            linhas.append(("warn", (
                f"{len(self.descartados)} apontamento(s) da IA NAO entraram, porque a prova "
                f"nao pode ser conferida no documento (confira a mao se quiser):")))
            for desc, motivo in self.descartados[:10]:
                linhas.append(("warn", f"      · {desc[:60]}: {motivo[:140]}"))
        return linhas

    def resumo(self):
        """Uma linha para o resumo do lote."""
        partes = []
        if self.na_preenchidos:
            partes.append(f"{len(self.na_preenchidos)} 'nao se aplica' preenchido(s) com o documento")
        if self.divergencias:
            partes.append(f"{len(self.divergencias)} divergencia(s) no log")
        return "conferida: " + (", ".join(partes) if partes else "nenhuma divergencia")
