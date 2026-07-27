r"""
sigft/core/excel/pmib_codes.py — normalização e extração do código PMIB
(Checkpoint 1.2 do plano de refatoração).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 1 -> CP 1.2, e a pendência
"Divergência com risco real de bug latente" registrada no CP 0.1 em
docs/refatoracao/PENDENCIAS.md. Só stdlib (`os`, `re`) — importável no
ambiente de teste (ver tests/conftest.py).

Este módulo unifica DUAS famílias de duplicação diagnosticadas na seção 1.2
do plano:

  1. Normalização do código PMIB (apóstrofo/vírgula, zeros à direita,
     float -> ":.4f") — 6 sites hoje: `upload_conditions_backend.py`
     (`carregar_lookup_status` e `atualizar_status_excel`),
     `upload_ficha_duplicada.py` (`GerenciadorFilaPMIB.montar_fila_processamento`
     e `AtualizadorStatusPMIB._blindar_numero_pmib`), `pdm_backend.py`
     (`processar_pastas_fichas`) e `frontend.py` (`ModuloPDM._op2_executar` e
     `ModuloUploadConditions._start_web_from_file`).
  2. Extração do código PMIB (4 últimos dígitos) a partir de um caminho de
     arquivo — 2 sites hoje: `analyzer_backend.DatasheetAnalyzer.extract_pmib_code`
     e `autospec_backend.AutoSpecCore.extract_pmib_code`, com uma DIVERGÊNCIA
     real entre eles (ver `extract_pmib_code` abaixo).

DECISÃO CANÔNICA — `normalize_pmib()` (obrigatória para o aceite do CP 1.2):
o comportamento de referência é o de
`AtualizadorStatusPMIB._blindar_numero_pmib` (upload_ficha_duplicada.py:677-690),
porque é a implementação caracterizada pelos testes do CP 0.1
(`tests/test_pmib_normalization_characterization.py`), incluindo o caso
`test_mais_de_4_casas_decimais_nao_e_truncado`. As outras variantes divergem
desse canônico só para ENTRADA MALFORMADA (código PMIB real sempre tem
EXATAMENTE 4 casas decimais, formato `\d{10}\.\d{4}`):

  - `pdm_backend.py:182` e `frontend.py:1322-1323` faziam
    `.ljust(4, '0')[:4]` — TRUNCAVAM para 4 dígitos quando a fração tinha
    mais de 4 (ex.: ".12345" virava ".1234"). O canônico NÃO trunca (ver
    `test_mais_de_4_casas_decimais_nao_e_truncado`): ".12345" permanece
    ".12345". Diferença só visível com >4 casas decimais (nunca ocorre em
    PMIB real).
  - `upload_conditions_backend.py:67-70` e `frontend.py:2082-2085` só
    acrescentavam UM '0' e só quando a fração já tinha EXATAMENTE 3 dígitos
    (regex `^\d{10}\.\d{3}$`) — não cobriam 1 ou 2 dígitos faltando, e
    (adicionalmente) não tratavam vírgula decimal nem apóstrofo. O canônico
    cobre os 3 casos (`.ljust(4, '0')` genérico) e limpa apóstrofo/vírgula
    sempre. Diferença só visível com <3 casas decimais faltando, ou
    apóstrofo/vírgula em módulos que antes não os removiam.
  - `pdm_backend.py:182`, `frontend.py:1322-1323` e
    `upload_ficha_duplicada.py:76` (`GerenciadorFilaPMIB`) também não
    removiam apóstrofo/vírgula (só `.strip()` simples ou nada) — o canônico
    remove ambos sempre. Ver PENDENCIAS.md para o registro completo desta
    unificação (é uma correção, não uma regressão: o valor final fica MAIS
    correto, nunca menos, para entrada real).

DECISÃO CANÔNICA — `extract_pmib_code()`: aplica `os.path.basename()` ANTES
do regex `\d{10}\.(\d{4})`. Esse é o comportamento que já era o CORRETO em
`autospec_backend.AutoSpecCore.extract_pmib_code` (autospec_backend.py:178-181);
`analyzer_backend.DatasheetAnalyzer.extract_pmib_code` (analyzer_backend.py:105-107)
rodava o regex sobre o CAMINHO INTEIRO recebido (sem basename), o que podia
"vazar" um match do nome de um DIRETÓRIO (ex.: uma subpasta
`9999999999.8888/` criada por `pdm_backend.processar_pastas_fichas`) em vez
do arquivo de fato — um bug latente que degradava silenciosamente o
enriquecimento de contexto por IA do analyzer. Decisão do arquiteto
(registrada no CP 0.1 e no plano, Fase 1 -> CP 1.2): corrigir o analyzer para
o comportamento do autospec. O teste de caracterização do analyzer é
atualizado INTENCIONALMENTE no CP 1.2 para refletir a correção (ver
tests/test_analyzer_backend_characterization.py).

Funções auxiliares adicionais (fora do par citado explicitamente no plano,
adicionadas para satisfazer o critério de aceite "grep não encontra regex...
de PMIB fora de pmib_codes.py", que também alcança outras duas variantes de
regex de código PMIB encontradas por grep):

  - `extract_pmib_code_full()`: código PMIB COMPLETO (prefixo + fração de
    QUALQUER número de dígitos), a partir do basename de um caminho — réplica
    de `upload_tech_specs_backend.TechSpecsProcessor.extrair_codigo_pmib_arquivo`
    (regex `\d{10}\.\d+`), que já fazia basename ANTES de chamar o método
    (sem o bug do analyzer), então não há correção de comportamento aqui —
    só unificação.
  - `find_pmib_code_in_text()`: mesma extração de código completo, mas SEM
    `os.path.basename()` — para texto livre (não é um caminho de arquivo!).
    Réplica de `GerenciadorFilaPMIB.montar_fila_processamento`
    (upload_ficha_duplicada.py:66), que extrai o PMIB "base" de uma célula de
    texto livre (coluna OBSERVAÇÕES). Aplicar `basename()` a texto livre
    seria incorreto (uma OBSERVAÇÃO pode conter "/" sem ser um caminho) —
    por isso esta função não usa `extract_pmib_code_full()` internamente
    apesar do regex idêntico.
  - `extract_contract_pmib_code()`: código PMIB completo, mas exigindo o
    PREFIXO DE CONTRATO configurado (`sigft.config.PREFIXO_CONTRATO`) — só
    aceita nomes de arquivo cujo código começa por esse prefixo. Réplica de
    `upload_conditions_backend.ConditionsProcessor.processar_ia_lote`
    (regex hardcoded `4500063671\.\d{4}`, upload_conditions_backend.py:147),
    já com o mesmo `os.path.basename()` que o original fazia. Deriva o
    prefixo de `config.PREFIXO_CONTRATO` em vez de repetir o literal (pedido
    explícito do checkpoint).
"""

from __future__ import annotations

import os
import re

from sigft import config

# --------------------------------------------------------------------------
# 1. normalize_pmib — ver decisão canônica no docstring do módulo acima.
# --------------------------------------------------------------------------

# Réplica exata de AtualizadorStatusPMIB._blindar_numero_pmib
# (upload_ficha_duplicada.py:677-690).
_PMIB_SUFFIX_REGEX = re.compile(r"\d{10}\.(\d{4})")
_PMIB_FULL_REGEX = re.compile(r"\d{10}\.\d+")
_CONTRACT_PMIB_REGEX = re.compile(rf"({re.escape(config.PREFIXO_CONTRATO)}\.\d{{4}})")


def normalize_pmib(valor: object) -> str:
    r"""Normaliza um valor de célula "CÓDIGO PMIB" para o formato canônico
    `\d{10}\.\d{4}` (ou mais dígitos na fração, se a entrada já tinha mais —
    ver `test_mais_de_4_casas_decimais_nao_e_truncado`).

    Comportamento (idêntico a `AtualizadorStatusPMIB._blindar_numero_pmib`):
      1. `None` -> `""`.
      2. `float`/`int` -> formatado com `:.4f` (ex.: `4500063671.1165` ->
         `"4500063671.1165"`; `4500063671` (int) -> `"4500063671.0000"`).
      3. Qualquer outro valor -> `str(valor)`, remove apóstrofos (Excel força
         texto com apóstrofo à frente) e troca vírgula por ponto (separador
         decimal PT-BR), depois `.strip()`. Se o resultado tiver EXATAMENTE
         um ponto e a parte antes dele tiver EXATAMENTE 10 dígitos (formato
         de prefixo de contrato), a fração é completada com zeros à direita
         via `.ljust(4, '0')` — SEM truncar se já tiver mais de 4 dígitos.
         Caso contrário (sem ponto, mais de um ponto, ou prefixo != 10
         dígitos), devolve o texto só limpo, sem tentar completar zeros.

    Usado via `.apply(normalize_pmib)` numa coluna/Series pandas, ou
    diretamente célula a célula (ex.: dentro de um loop openpyxl).
    """
    if valor is None:
        return ""
    if isinstance(valor, (float, int)):
        return f"{float(valor):.4f}"

    texto_limpo = str(valor).replace("'", "").replace(",", ".").strip()
    partes = texto_limpo.split(".")
    if len(partes) == 2 and len(partes[0]) == 10:
        return f"{partes[0]}.{partes[1].ljust(4, '0')}"
    return texto_limpo


# --------------------------------------------------------------------------
# 2. extract_pmib_code — ver decisão canônica no docstring do módulo acima.
# --------------------------------------------------------------------------

def extract_pmib_code(caminho: str) -> str | None:
    r"""Extrai os 4 últimos dígitos do código PMIB (ex.: `"1234"`) a partir
    do NOME DO ARQUIVO de `caminho` (aplica `os.path.basename()` ANTES do
    regex `\d{10}\.(\d{4})`).

    Réplica de `autospec_backend.AutoSpecCore.extract_pmib_code`
    (autospec_backend.py:178-181) — o comportamento CORRETO das duas
    variantes que existiam antes do CP 1.2 (ver decisão canônica acima).
    `analyzer_backend.DatasheetAnalyzer.extract_pmib_code` passa a delegar
    para esta função, o que CORRIGE o bug latente (regex vazando do
    diretório) caracterizado no CP 0.1.

    Retorna `None` se `caminho` (ou seu basename) não contiver o padrão.
    """
    nome_arquivo = os.path.basename(caminho)
    match = _PMIB_SUFFIX_REGEX.search(nome_arquivo)
    return match.group(1) if match else None


def extract_pmib_code_full(caminho: str) -> str | None:
    r"""Extrai o código PMIB COMPLETO (prefixo + fração de QUALQUER número de
    dígitos, ex.: `"4500063671.1234"`) a partir do NOME DO ARQUIVO de
    `caminho` (aplica `os.path.basename()` antes do regex `\d{10}\.\d+`).

    Réplica de
    `upload_tech_specs_backend.TechSpecsProcessor.extrair_codigo_pmib_arquivo`
    (upload_tech_specs_backend.py:43-45). O chamador original já fazia
    `os.path.basename()` ANTES de invocar o método (upload_tech_specs_backend.py:100-101),
    então aplicar basename aqui dentro é equivalente (idempotente) e deixa a
    função robusta também para quem passar o caminho completo diretamente.
    """
    nome_arquivo = os.path.basename(caminho)
    match = _PMIB_FULL_REGEX.search(nome_arquivo)
    return match.group(0) if match else None


def find_pmib_code_in_text(texto: str) -> str | None:
    r"""Procura um código PMIB COMPLETO (prefixo + fração de QUALQUER número
    de dígitos, ex.: `"4500063671.1234"`) dentro de `texto` LIVRE — SEM
    aplicar `os.path.basename()` (não é um caminho de arquivo).

    Réplica de `GerenciadorFilaPMIB.montar_fila_processamento`
    (upload_ficha_duplicada.py:66: `re.search(r'(\d{10}\.\d+)', observacao)`),
    que extrai o PMIB "base" da coluna livre OBSERVAÇÕES do `_STATUS_PMIB`.

    Retorna `None` se `texto` não contiver o padrão.
    """
    match = _PMIB_FULL_REGEX.search(texto)
    return match.group(0) if match else None


def extract_contract_pmib_code(caminho: str) -> str | None:
    r"""Extrai o código PMIB COMPLETO (ex.: `"4500063671.1234"`) do NOME DO
    ARQUIVO de `caminho`, exigindo que ele comece pelo prefixo de contrato
    configurado (`sigft.config.PREFIXO_CONTRATO`) seguido de "." e EXATAMENTE
    4 dígitos. Aplica `os.path.basename()` antes do regex.

    Réplica de `upload_conditions_backend.ConditionsProcessor.processar_ia_lote`
    (regex hardcoded `4500063671\.\d{4}`, upload_conditions_backend.py:147),
    agora derivando o prefixo de `config.PREFIXO_CONTRATO` em vez de repetir
    o literal (o chamador original já fazia `os.path.basename()` antes de
    buscar o match — comportamento preservado).

    Retorna `None` se o padrão não for encontrado.
    """
    nome_arquivo = os.path.basename(caminho)
    match = _CONTRACT_PMIB_REGEX.search(nome_arquivo)
    return match.group(1) if match else None
