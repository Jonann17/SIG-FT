"""O STATUS REAL de uma lista, pela batalha de versões do DocManager, e as regras em cima dele.

O status real é o que `calcular_status_real` devolve, **sem** o consolidado do DocManager:
distingue Aprovado, Aprovado com Comentários e Para Assinatura (decisão do Luan, 26/10/2026).
A mapeadora grava esse texto; os painéis e a Conferência de Revisões o classificam com
`eh_aprovacao` e `categoria`, que aceitam também os valores antigos digitados à mão
(APROVADO, EM PROCESSO, NÃO APROVADO). Ver
`docs/superpowers/specs/2026-10-26-aconex-ao-vivo-design.md`, §4.4 e §5.2.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from sigft.core.aconex._docmanager import constants, normalize, status_engine, truth_line

if TYPE_CHECKING:
    import pandas as pd

Categoria = Literal["aprovada", "em_processo", "nao_aprovada", "outros"]
ORDEM_DAS_CATEGORIAS: tuple[Categoria, ...] = ("aprovada", "em_processo", "nao_aprovada", "outros")


def _chave(status: object) -> str:
    """Maiúsculas, sem acento, espaços colapsados; `None` vira ''."""
    if status is None:
        return ""
    return " ".join(normalize.remover_acentos(str(status)).upper().split())


_APROVACAO = frozenset(_chave(s) for s in constants.STATUS_APROVACAO_UPPER)
_REPROVACAO = frozenset(_chave(s) for s in constants.STATUS_REPROVACAO_UPPER)
_EM_PROCESSO = "EM PROCESSO"  # o motor devolve o literal "Em Processo" (status_engine.py)
_NAO_EMITIDO = _chave(constants.NAO_EMITIDO)


# As colunas do histórico que a linha da verdade e a batalha leem.
COLUNAS_DO_HISTORICO = (constants.COL_TRACKING, constants.COL_DOC_ITAIPU, constants.COL_CURRENT,
                        constants.COL_REVISAO, constants.COL_VERSAO, constants.COL_STATUS,
                        constants.COL_STATUS_REVISAO, constants.COL_DATA, constants.COL_TITULO)


def colunas_que_faltam(historico: pd.DataFrame) -> list[str]:
    """As colunas de `COLUNAS_DO_HISTORICO` que o histórico não tem (vazio = dá para calcular)."""
    return [c for c in COLUNAS_DO_HISTORICO if c not in historico.columns]


def status_real_do_documento(historico: pd.DataFrame) -> str:
    """O status real de um documento. `historico` são todas as linhas de UM Tracking ID,
    com as colunas do extrato do DocManager."""
    tl = truth_line.resolver_linha_da_verdade(historico)
    if tl.nao_emitido:
        return constants.NAO_EMITIDO
    return status_engine.calcular_status_real(tl.df_para_calculo, tl.revisao_atual)


def eh_aprovacao(status: object) -> bool:
    """Família de aprovação: Aprovado, Aprovado com Comentários, Para Assinatura (e o antigo APROVADO)."""
    return _chave(status) in _APROVACAO


def eh_nao_emitido(status: object) -> bool:
    """NÃO EMITIDO: a batalha não achou emissão que valha (a lista só passou pela integração, ou a
    primeira emissão foi cancelada). Sem acento e sem caixa, como `eh_aprovacao`: o valor antigo,
    digitado à mão na mapeadora, também se encaixa."""
    return _chave(status) == _NAO_EMITIDO


def categoria(status: object) -> Categoria:
    chave = _chave(status)
    if chave in _APROVACAO:
        return "aprovada"
    if chave == _EM_PROCESSO:
        return "em_processo"
    if chave in _REPROVACAO:
        return "nao_aprovada"
    return "outros"


def revisoes_iguais(a: object, b: object) -> bool:
    """Mesma revisão, sem ligar para caixa nem espaço. Revisão vazia nunca é igual a nada."""
    ra = normalize.normalizar_revisao(a) if a is not None else ""
    rb = normalize.normalizar_revisao(b) if b is not None else ""
    return bool(ra) and ra == rb
