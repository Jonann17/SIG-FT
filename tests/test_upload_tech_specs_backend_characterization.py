"""
Teste de caracterização (CP 0.1) — upload_tech_specs_backend.py.

Cobre o par pedido pelo CP 0.1 (`normalizar_texto` + `limpar_pergunta`) na
classe que tem os dois: `TechSpecsProcessor` (linhas 32 e 38).

`TechSpecsAutomation` (linha 314) também tem seu próprio `normalizar_texto`
(linha 369) — caracterizado aqui também, comparando-o diretamente ao de
`TechSpecsProcessor` para registrar que HOJE as duas implementações são
idênticas (nenhuma divergência entre elas; a duplicação em si é o problema
listado no diagnóstico do plano, seção 1.2).

Todos os métodos abaixo são "puros" (não usam atributos de instância); as
instâncias são criadas via `__new__` para não rodar `__init__` — em
`TechSpecsProcessor.__init__`, isso evitaria uma chamada real a
`genai.configure(...)` caso `api_key` fosse truthy.
"""
from upload_tech_specs_backend import TechSpecsAutomation, TechSpecsProcessor


def _make_processor():
    return TechSpecsProcessor.__new__(TechSpecsProcessor)


def _make_automation():
    return TechSpecsAutomation.__new__(TechSpecsAutomation)


# --- normalizar_texto (TechSpecsProcessor, linha 32) -----------------------

def test_normalizar_texto_remove_acentos_e_colapsa_espacos():
    proc = _make_processor()
    resultado = proc.normalizar_texto("  Válvula   de   Retenção  ")
    assert resultado == "VALVULA DE RETENCAO"


def test_normalizar_texto_maiusculiza():
    proc = _make_processor()
    assert proc.normalizar_texto("já com MAIÚSCULAS") == "JA COM MAIUSCULAS"


def test_normalizar_texto_none_retorna_vazio():
    proc = _make_processor()
    assert proc.normalizar_texto(None) == ""


def test_normalizar_texto_string_vazia_retorna_vazio():
    proc = _make_processor()
    assert proc.normalizar_texto("") == ""


def test_normalizar_texto_zero_retorna_vazio_por_ser_falsy():
    # Peculiaridade / DIVERGÊNCIA vs PMIBSearcher._limpar_texto_parrudo:
    # `if not texto: return ""` trata QUALQUER valor falsy (não só None/"")
    # como vazio — inclusive o inteiro 0. `_limpar_texto_parrudo` usa
    # `pd.isna()`, que trataria 0 como válido (retornaria "0"). Duas funções
    # de "normalização" com contrato diferente para o mesmo tipo de entrada —
    # candidato a unificação no CP 1.2.
    proc = _make_processor()
    assert proc.normalizar_texto(0) == ""


def test_normalizar_texto_preserva_pontuacao_e_simbolos_nao_alfabeticos():
    # Diferente de PMIBSearcher._limpar_texto_parrudo (que remove TODA
    # pontuação via regex [^A-Z0-9]), normalizar_texto só remove acentos
    # (marcas de combinação Unicode categoria 'Mn'); hífen, barra e ponto são
    # preservados no resultado.
    proc = _make_processor()
    resultado = proc.normalizar_texto("texto_simples-com/pontuacao.teste")
    assert resultado == "TEXTO_SIMPLES-COM/PONTUACAO.TESTE"


def test_normalizar_texto_preserva_caracteres_sem_decomposicao_canonica():
    # Mesma raiz técnica do teste equivalente em _limpar_texto_parrudo, mas
    # com resultado OPOSTO: aqui 'Ø' e 'º' são PRESERVADOS (não são marca de
    # combinação 'Mn', então o filtro por categoria não os remove) — ao
    # contrário de _limpar_texto_parrudo, que os descarta via
    # encode('ascii', 'ignore'). Duas funções de "normalização" de nome
    # parecido com resultados opostos para o mesmo caractere: candidato forte
    # a unificação no CP 1.2 (ver core/excel/pmib_codes.py e afins).
    proc = _make_processor()
    resultado = proc.normalizar_texto("Peça (Ø 10mm) nº 5")
    assert resultado == "PECA (Ø 10MM) Nº 5"


def test_automation_normalizar_texto_e_identico_ao_do_processor():
    # TechSpecsAutomation.normalizar_texto (linha 369) é cópia textual do de
    # TechSpecsProcessor (linha 32); confirmamos aqui que o comportamento é
    # idêntico HOJE (a duplicação em si é o problema, não uma divergência).
    proc = _make_processor()
    auto = _make_automation()
    entrada = "  Válvula   de   Retenção nº 5 (Ø 10mm) "
    assert auto.normalizar_texto(entrada) == proc.normalizar_texto(entrada)
    assert auto.normalizar_texto(entrada) == "VALVULA DE RETENCAO Nº 5 (Ø 10MM)"


# --- limpar_pergunta (TechSpecsProcessor, linha 38) -------------------------

def test_limpar_pergunta_remove_prefixo_numero_hifen():
    proc = _make_processor()
    assert proc.limpar_pergunta("12 - Qual a cor?") == "Qual a cor?"


def test_limpar_pergunta_sem_espacos_ao_redor_do_hifen():
    proc = _make_processor()
    resultado = proc.limpar_pergunta("3-Sem espaco em volta")
    assert resultado == "Sem espaco em volta"


def test_limpar_pergunta_sem_prefixo_numerico_retorna_texto_original_stripado():
    proc = _make_processor()
    texto = "Pergunta sem numero prefixado"
    assert proc.limpar_pergunta(texto) == texto


def test_limpar_pergunta_remove_espacos_extras_ao_final():
    proc = _make_processor()
    resultado = proc.limpar_pergunta("007 - Múltiplos espaços de sobra   ")
    assert resultado == "Múltiplos espaços de sobra"


def test_limpar_pergunta_numero_sem_hifen_nao_e_removido():
    # Peculiaridade: o regex exige um hífen literal após os dígitos; sem
    # hífen, nenhum prefixo é removido (mesmo havendo dígitos no início).
    proc = _make_processor()
    texto = "42 Pergunta sem traco"
    assert proc.limpar_pergunta(texto) == texto


def test_limpar_pergunta_none_vira_a_string_none():
    # Peculiaridade: `str(None)` é a string "None"; como ela não começa com
    # dígito, cai no fallback `str(texto_pergunta).strip()`, retornando a
    # STRING "None" (não o objeto None, não "").
    proc = _make_processor()
    assert proc.limpar_pergunta(None) == "None"


def test_limpar_pergunta_aceita_entrada_nao_string():
    proc = _make_processor()
    assert proc.limpar_pergunta(42) == "42"
