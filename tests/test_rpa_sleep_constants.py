r"""
Testes do Checkpoint 2.3 — constantes `PAUSA_*` de `sigft/core/rpa/portal.py`
(Fase 2 -> CP 2.3, "Sincronização: sleeps -> waits").

Não há como testar o TEMPO real de espera (nenhum acesso ao portal real
neste ambiente) — o que é testável e importa aqui:
  1. cada constante `PAUSA_*` citada no plano/relatório do checkpoint existe
     com o valor NUMÉRICO exato que tinha como `time.sleep(N)` cru antes da
     migração (preservação de comportamento — nenhum tempo de espera
     mudou, só ganhou nome);
  2. todas são `int`/`float` positivos (nunca zero/negativo — um valor assim
     seria um bug de digitação, não uma pausa real);
  3. os 6 arquivos-alvo (`apagar_lmr_backend.py`, `lmr_backend.py`,
     `upload_tech_specs_backend.py`, `upload_conditions_backend.py`,
     `upload_ficha_duplicada.py`, `cria_fichas_no_pmib_v1_backend.py`) não
     têm mais NENHUM `time.sleep(<literal numérico>)` cru — só chamadas
     via constante nomeada (grep de verificação, mesmo padrão dos testes de
     smoke doutros checkpoints).
"""
import re
from pathlib import Path

import pytest

import sigft.core.rpa.portal as portal

REPO_ROOT = Path(__file__).resolve().parent.parent

ARQUIVOS_ALVO = [
    "apagar_lmr_backend.py",
    "lmr_backend.py",
    "upload_tech_specs_backend.py",
    "upload_conditions_backend.py",
    "upload_ficha_duplicada.py",
    "cria_fichas_no_pmib_v1_backend.py",
]

# Valor NUMÉRICO exato que cada constante tinha como `time.sleep(N)` cru
# antes da migração (CP 2.3) — levantado do diff real de cada um dos 6
# arquivos. Cobre as 32 constantes `PAUSA_*` definidas em `portal.py`.
VALORES_ESPERADOS = {
    "PAUSA_ANIMACAO": 0.5,
    "PAUSA_FOCO": 1,
    "PAUSA_MUDANCA_FOCO": 1.5,
    "PAUSA_SCROLL": 0.2,
    "PAUSA_DIGITACAO": 0.2,
    "PAUSA_ENTRE_CAMPOS": 0.3,
    "PAUSA_RECARGA_TABELA": 2,
    "PAUSA_CARGA_TABELA": 2,
    "PAUSA_PAGINACAO": 3,
    "PAUSA_CARGA_LISTA": 2,
    "PAUSA_ABERTURA_ABA": 2,
    "PAUSA_ABERTURA_SECAO": 1.5,
    "PAUSA_TROCA_SUBABA": 1,
    "PAUSA_ABERTURA_MODAL": 1,
    "PAUSA_ABERTURA_FICHA": 5,
    "PAUSA_INICIO_ITEM": 1.5,
    "PAUSA_SALVAMENTO": 1,
    "PAUSA_SALVAMENTO_LONGA": 1.5,
    "PAUSA_SALVAMENTO_FINAL": 3,
    "PAUSA_FALLBACK_SALVAMENTO": 5,
    "PAUSA_POS_EXCLUSAO": 1.5,
    "PAUSA_FILTRO_PDM": 1,
    "PAUSA_FILTRO_FORNECEDOR": 1.5,
    "PAUSA_AUDITORIA": 0.5,
    "PAUSA_INJECAO_JS": 1.5,
    "PAUSA_POS_INJECAO_JS": 1.0,
    "PAUSA_POLL_DOWNLOAD": 1,
    "PAUSA_UPLOAD_ARQUIVO": 3,
    "PAUSA_RETRY_IA_CURTA": 2,
    "PAUSA_RETRY_IA_LONGA": 30,
    "PAUSA_RETRY_ARQUIVO_BLOQUEADO": 5,
    "PAUSA_GERACAO_PMIB": 6,
    "PAUSA_RETORNO_LISTA": 1,
}


def test_todas_as_constantes_pausa_de_portal_estao_cobertas_pelo_teste():
    # Nenhuma constante `PAUSA_*` nova em portal.py pode ficar sem uma
    # asserção de valor aqui (e vice-versa) — mantém este arquivo honesto
    # sobre o que de fato verifica.
    nomes_no_modulo = {
        nome for nome in dir(portal)
        if nome.startswith("PAUSA_") and not nome.startswith("_")
    }
    assert nomes_no_modulo == set(VALORES_ESPERADOS)


@pytest.mark.parametrize("nome_constante,valor_esperado", sorted(VALORES_ESPERADOS.items()))
def test_constante_pausa_preserva_o_valor_numerico_original(nome_constante, valor_esperado):
    valor_real = getattr(portal, nome_constante)
    assert valor_real == valor_esperado
    assert isinstance(valor_real, (int, float))
    assert valor_real > 0


@pytest.mark.parametrize("nome_arquivo", ARQUIVOS_ALVO)
def test_arquivo_nao_tem_mais_time_sleep_com_literal_numerico_cru(nome_arquivo):
    """Aceite do CP 2.3: "nenhum time.sleep( com literal numérico em
    services/" -- verifica que os 6 arquivos-alvo só chamam `time.sleep(`
    com um NOME (constante importada de `portal.py`), nunca com um
    número/literal direto."""
    conteudo = (REPO_ROOT / nome_arquivo).read_text(encoding="utf-8")
    # `time.sleep(` seguido diretamente de um dígito (com ou sem sinal) é
    # exatamente o padrão "literal numérico cru" que o aceite proíbe.
    achados = re.findall(r"time\.sleep\(\s*-?\d", conteudo)
    assert achados == [], f"{nome_arquivo} ainda tem time.sleep com literal numérico: {achados}"


def test_arquivos_alvo_existem_e_foram_de_fato_verificados():
    # Proteção contra erro de digitação em ARQUIVOS_ALVO (um nome de
    # arquivo errado faria o teste anterior "passar" silenciosamente por
    # não achar nada, mas também não estaria testando NADA de verdade).
    for nome_arquivo in ARQUIVOS_ALVO:
        assert (REPO_ROOT / nome_arquivo).is_file(), f"{nome_arquivo} não encontrado"
