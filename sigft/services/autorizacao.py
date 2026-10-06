r"""
sigft/services/autorizacao.py — a regra da autorização de entrega de Itaipu.

T2 do roteiro "Gestão PMIB no tratamento v2" (`gestao-sobressalentes/07 -
Diagnostico/Tarefa SIG-FT - Calculo e Gravacao sem Perda.md`, seção 2.1 --
decisões do Luan, 04-05/10/2026). Implementação de referência:
`situacao_autorizacao()` de `gestao-sobressalentes/_scripts/regras_sobressalentes.py`
mais a regra do DUPLICADO de `recalcular_situacao()` (`migrar_status_pmib_v2.py`).

O que ela decide, para cada linha do `_STATUS_PMIB`
---------------------------------------------------
As colunas SITUAÇÃO DA AUTORIZAÇÃO e DIAS DE ATRASO, que **o SIG-FT grava**
(o `_STATUS_PMIB` v2 não tem fórmula nenhuma). O Power BI v2 e o painel HTML
contam a partir do que fica gravado -- por isso esta é a ÚNICA implementação:
o Gestão PMIB a usa para gravar, o painel para mostrar.

Avaliada NESTA ORDEM (a primeira que casar vale):

  | # | Condição                                         | SITUAÇÃO          | DIAS           |
  |---|--------------------------------------------------|-------------------|----------------|
  | 1 | STATUS = DUPLICADO e o resultado não é AUTORIZADO| (branco)          | (branco)       |
  | 2 | atual = AUTORIZADO (ou SIM, do layout antigo)    | AUTORIZADO        | mantém         |
  | 3 | TIPO = DOCUMENTAL ou TÍTULO                      | N/A               | (branco)       |
  | 4 | EQUIPAMENTO ENTREGUE = SIM                       | AUTORIZADO        | mantém         |
  | 5 | TIPO vazio ou desconhecido                       | (branco)          | (branco)       |
  | 6 | (FÍSICA E DOCUMENTAL) sem DATA DO EMAIL          | (branco)          | (branco)       |
  | 7 | hoje > prazo                                     | ATRASADO ITAIPU   | hoje - prazo   |
  | 8 | senão                                            | AGUARDANDO ITAIPU | (branco)       |

  - **Só FÍSICA E DOCUMENTAL precisa de autorização.** DOCUMENTAL é o
    componente explodido (só tem ficha; a entrega física é a do pai); TÍTULO é
    agrupamento; tipo vazio não conta até alguém classificar.
  - **prazo** = DATA DO EMAIL + 15 dias ÚTEIS (`config.PRAZO_AUTORIZACAO_DIAS_UTEIS`),
    como o `WORKDAY` do Excel, pulando `config.FERIADOS`. **Dias de atraso são
    CORRIDOS** além do prazo.
  - AUTORIZADO é FATO (veio do export de autorizados, ou o material foi
    entregue) e nunca é desfeito pelo cálculo; os dias ficam congelados no
    valor que tinham. Os outros estados são recalculados a cada rodada.
  - DUPLICADO é o mesmo item repetido na mesma lista: a situação vale pela
    linha da ficha, não por esta. A regra 1 é conferida sobre o RESULTADO das
    outras (como na referência e no Power BI): DUPLICADO entregue fica
    AUTORIZADO.

Só stdlib, de propósito: a suíte de testes roda sem pandas/numpy de verdade.
"""
from __future__ import annotations

import datetime as dt
import math
import re
import unicodedata

from sigft import config

AGUARDANDO = "AGUARDANDO ITAIPU"
ATRASADO = "ATRASADO ITAIPU"
AUTORIZADO = "AUTORIZADO"
NAO_SE_APLICA = "N/A"
# A ordem da lista suspensa `lst_situacao` do `_STATUS_PMIB` v2.
SITUACOES = (AGUARDANDO, ATRASADO, AUTORIZADO, NAO_SE_APLICA)

FISICA_E_DOCUMENTAL = "FÍSICA E DOCUMENTAL"
DOCUMENTAL = "DOCUMENTAL"
TITULO = "TÍTULO"

# Grafias que aparecem nas planilhas -> o texto canônico da lista suspensa
# `lst_tipo_entrega`. Chaves já normalizadas (ver `normalizar`).
TIPO_CANONICO = {
    "FISICA E DOCUMENTAL": FISICA_E_DOCUMENTAL,
    "FISICO E DOCUMENTAL": FISICA_E_DOCUMENTAL,
    "DOCUMENTAL": DOCUMENTAL,
    "APENAS DOCUMENTAL": DOCUMENTAL,
    "TITULO": TITULO,
    "CONJUNTO": TITULO,
    "CONJUNTO (TITULO)": TITULO,
}


# --------------------------------------------------------------------------
# Normalização
# --------------------------------------------------------------------------
def _vazio(valor) -> bool:
    """`None`, e todo "vazio" do pandas (NaN, NaT): é diferente de si mesmo."""
    if valor is None:
        return True
    try:
        return bool(valor != valor)
    except (TypeError, ValueError):
        return False


def normalizar(valor) -> str:
    """Maiúsculas, sem acento, espaços colapsados. Vazio -> ''."""
    if _vazio(valor):
        return ""
    sem_acento = unicodedata.normalize("NFD", str(valor)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento.upper()).strip()


def tipo_canonico(valor) -> str | None:
    """O TIPO DE ENTREGA no texto da lista suspensa, ou `None` (vazio ou
    desconhecido -- que, para a regra, é a mesma coisa: não conta)."""
    return TIPO_CANONICO.get(normalizar(valor))


# --------------------------------------------------------------------------
# Datas
# --------------------------------------------------------------------------
def dia_util(d: dt.date, feriados=None) -> bool:
    feriados = config.FERIADOS if feriados is None else feriados
    return d.weekday() < 5 and d not in feriados


def somar_dias_uteis(inicio: dt.date, n: int, feriados=None) -> dt.date:
    """O `WORKDAY(inicio; n; feriados)` do Excel: avança dia a dia e conta os
    que não são sábado, domingo nem feriado. E-mail num sábado não ganha dia a
    mais -- a contagem começa no dia seguinte, seja qual for."""
    d = inicio
    while n > 0:
        d += dt.timedelta(days=1)
        if dia_util(d, feriados):
            n -= 1
    return d


def prazo_autorizacao(data_email: dt.date | None, feriados=None) -> dt.date | None:
    """Até quando Itaipu pode autorizar: o e-mail + 15 dias úteis."""
    if data_email is None:
        return None
    return somar_dias_uteis(data_email, config.PRAZO_AUTORIZACAO_DIAS_UTEIS, feriados)


def para_data(valor) -> dt.date | None:
    """A DATA DO EMAIL como a planilha a entrega: data do openpyxl, Timestamp do
    pandas, ou texto `dd/mm/aaaa` / `aaaa-mm-dd`. Qualquer outra coisa (vazio,
    NaT, número solto, "A CONFIRMAR") -> `None`."""
    if _vazio(valor):
        return None
    if isinstance(valor, dt.datetime):
        return valor.date()
    if isinstance(valor, dt.date):
        return valor
    if isinstance(valor, str):
        texto = valor.strip()
        for formato in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return dt.datetime.strptime(texto, formato).date()
            except ValueError:
                continue
    return None


def _serial_excel(d: dt.date) -> int:
    """O número de série do Excel de uma data -- o inverso do `from_excel` do
    openpyxl, inclusive antes de 01/03/1900, onde o Excel conta o 29/02/1900
    que não existiu."""
    momento = d if isinstance(d, dt.datetime) else dt.datetime.combine(d, dt.time())
    dias = (momento - dt.datetime(1899, 12, 30)).days
    return dias - 1 if momento < dt.datetime(1900, 3, 1) else dias


def dias_da_celula(valor) -> int | None:
    """DIAS DE ATRASO como número inteiro, ou `None` se vazio/ilegível.

    A célula pode ter herdado o formato de data da coluna vizinha (aconteceu
    em 33 arquivos): o número 4 chega do openpyxl como 04/01/1900. Volta ao
    número que está gravado."""
    if _vazio(valor) or valor == "":
        return None
    if isinstance(valor, dt.date):
        return _serial_excel(valor)
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return int(numero) if math.isfinite(numero) else None


# --------------------------------------------------------------------------
# A regra
# --------------------------------------------------------------------------
def situacao_autorizacao(data_email, situacao_atual, entregue, hoje: dt.date,
                         dias_atual=None, tipo=None, status=None,
                         feriados=None) -> tuple[str, int | None]:
    """`(SITUAÇÃO DA AUTORIZAÇÃO, DIAS DE ATRASO)` de uma linha -- a tabela do
    docstring do módulo. `""` e `None` são a célula em branco.

    Aceita as células como vieram da planilha: data em qualquer formato que
    `para_data` entenda, dias com formato de data (`dias_da_celula`), textos em
    qualquer caixa e com ou sem acento.
    """
    situacao, dias = _regras_2_a_8(data_email, situacao_atual, entregue, hoje, dias_atual, tipo, feriados)
    # 1. DUPLICADO: a situação vale pela linha da ficha, não por esta -- a não
    #    ser que ESTA linha tenha um fato de autorização (marcada AUTORIZADO, ou
    #    o material entregue).
    #
    #    ⚠️ Aplicada DEPOIS das outras, como em `recalcular_situacao()` (a
    #    referência que gerou o `esperado.json` do kit) e no Power BI v2. A
    #    tabela do roteiro a lista primeiro, com "a SITUAÇÃO atual não é
    #    AUTORIZADO"; as duas leituras só divergem numa linha DUPLICADO com
    #    EQUIPAMENTO ENTREGUE = SIM, que aqui fica AUTORIZADO. Registrado em
    #    PENDENCIAS.md para o Luan confirmar.
    if normalizar(status) == "DUPLICADO" and situacao != AUTORIZADO:
        return "", None
    return situacao, dias


def _regras_2_a_8(data_email, situacao_atual, entregue, hoje, dias_atual, tipo,
                  feriados) -> tuple[str, int | None]:
    # 2. Marcação de fato: vale sempre, e os dias ficam como estavam.
    if normalizar(situacao_atual) in (AUTORIZADO, "SIM"):
        return AUTORIZADO, dias_da_celula(dias_atual)
    tipo_c = tipo_canonico(tipo)
    # 3. Sem entrega física deste item.
    if tipo_c in (DOCUMENTAL, TITULO):
        return NAO_SE_APLICA, None
    # 4. Entregue implica autorizado.
    if normalizar(entregue) == "SIM":
        return AUTORIZADO, dias_da_celula(dias_atual)
    # 5. Tipo vazio ou desconhecido não conta até alguém classificar.
    if tipo_c != FISICA_E_DOCUMENTAL:
        return "", None
    # 6. Sem e-mail de intenção, não há prazo correndo.
    prazo = prazo_autorizacao(para_data(data_email), feriados)
    if prazo is None:
        return "", None
    # 7-8. Dias CORRIDOS além do prazo.
    if hoje > prazo:
        return ATRASADO, (hoje - prazo).days
    return AGUARDANDO, None


def dias_de_atraso_na_autorizacao(data_email, data_autorizacao: dt.date,
                                  feriados=None) -> int | None:
    """Quando a autorização chega (data do export de autorizados): dias
    corridos além do prazo, ou `None` se chegou no prazo. É o valor que fica
    congelado em DIAS DE ATRASO."""
    prazo = prazo_autorizacao(para_data(data_email), feriados)
    if prazo is None:
        return None
    return (data_autorizacao - prazo).days if data_autorizacao > prazo else None
