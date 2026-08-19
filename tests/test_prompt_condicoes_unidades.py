r"""
O prompt de Condições precisa DEDUZIR a unidade quando a ficha não declara.

⚠️ Isto INVERTE uma decisão de 2026-08-19 tomada horas antes, e a inversão é
do usuário. Vale registrar as duas, porque o par explica o limite:

  1º pedido: *"devemos ser estritamente fiel à informação que veio da ficha,
     fazendo a conversão para cm"* -- eu li como "nunca suponha unidade" e
     escrevi `SEM UNIDADE DECLARADA, NÃO ADIVINHE`.

  correção: *"eu preciso que a IA adivinhe sim com base no tipo de
     equipamento que estamos lidando, se a embalagem está 400 e estamos
     falando de um equipamento que não é muito grande, então a sugestão é
     que seja 40 cm. O peso auxilia também a ter noção. A maioria das
     fichas não virá unidade."*

Não é contradição: **fidelidade é ao TAMANHO REAL do material, não ao
dígito.** Uma caixa de relé anotada "400" e gravada como 400 cm não é fiel a
nada -- é uma caixa de 4 metros que não existe. O que continua proibido é
inventar CONTEÚDO (norma, lei, cuidado, texto que o fornecedor não
escreveu); o que passa a ser exigido é ler a MEDIDA na escala certa.

A fronteira entre as duas coisas é o que este arquivo tranca. Os testes de
`test_prompt_condicoes_fidelidade.py` continuam valendo inteiros -- nenhum
deles é afrouxado aqui.
"""
import re

import pytest

from sigft.core.llm import prompts

TEXTO = prompts.SYSTEM_CONDICOES


# =============================================================================
# 1. A dedução tem de estar ENSINADA, não só permitida
# =============================================================================
def test_o_prompt_manda_deduzir_a_unidade_quando_ela_nao_vem():
    """A regra antiga (`SEM UNIDADE DECLARADA, NÃO ADIVINHE`) não pode
    sobreviver em lugar nenhum do texto: era a instrução exatamente oposta."""
    proibidas = ("NÃO ADIVINHE", "NAO ADIVINHE", "não adivinhe")
    presentes = [p for p in proibidas if p in TEXTO]
    assert presentes == [], (
        "O prompt voltou a proibir a dedução de unidade, que o usuário pediu "
        f"explicitamente. Trechos: {presentes}"
    )


def test_a_deducao_usa_o_tipo_de_material_como_instrumento():
    """Instrumento (a) do pedido: *"com base no tipo de equipamento que
    estamos lidando"*. A chave tem de ser citada pelo nome que o serviço
    manda, senão a IA não sabe onde olhar."""
    assert "Descrição do material" in TEXTO


def test_a_deducao_usa_o_peso_como_aferidor():
    """Instrumento (b) do pedido: *"O peso auxilia também a ter noção"*. Sem
    a fórmula, "usar o peso" é conselho vago; com ela, é conta."""
    assert "densidade" in TEXTO.lower()
    assert "g/cm³" in TEXTO
    # A conta em si, não só a palavra.
    assert re.search(r"peso.{0,40}÷.{0,40}C\s*×\s*L\s*×\s*A", TEXTO), (
        "A fórmula da densidade aparente sumiu do prompt -- sem ela a IA "
        "não tem como aferir a hipótese contra o peso."
    )


def test_o_veredito_de_cada_faixa_esta_escrito():
    """Densidade baixa demais ⇒ era mm; alta demais ⇒ era m. Sem os dois
    vereditos a IA calcula a densidade e não sabe o que concluir."""
    assert "dividir por 10" in TEXTO or "divida por 10" in TEXTO
    assert "multiplicar por 100" in TEXTO or "multiplique por 100" in TEXTO


def test_ha_exemplos_trabalhados_com_a_conta_feita():
    """O pedido foi literal: *"traga exemplos para ela entender o que é pra
    fazer"*. Um exemplo com a aritmética visível ensina; uma regra abstrata
    não. Exigimos os três desfechos possíveis -- converter para baixo,
    converter para cima, e NÃO mexer."""
    assert "EXEMPLO" in TEXTO
    # o caso mais comum (mm), o caso raro (m) e o caso em que já estava certo
    assert "hipótese mm" in TEXTO
    assert "hipótese m:" in TEXTO
    assert "INALTERADO" in TEXTO, (
        "Falta o exemplo em que o número JÁ estava em cm. Sem ele a IA "
        "aprende que sempre há uma conversão a fazer, e passa a dividir por "
        "10 o que estava certo."
    )


# =============================================================================
# 2. A fronteira: deduzir UNIDADE não é inventar CONTEÚDO
# =============================================================================
def test_a_deducao_e_declarada_restrita_aos_campos_numericos():
    """O risco real desta mudança é vazar: a IA lê "deduza" e volta a
    completar texto livre com o que "costuma ser". O prompt tem de dizer,
    dentro da própria regra, que a licença acaba nos números."""
    assert "só da UNIDADE" in TEXTO or "só da unidade" in TEXTO
    assert "REGRA 0 continua soberana" in TEXTO


def test_deduzir_unidade_nao_autoriza_inventar_numero_que_nao_veio():
    """Campo de dimensão vazio continua vazio. Deduzir a escala de um número
    existente é uma coisa; estimar o tamanho da caixa a partir do material é
    outra, e essa continua proibida."""
    assert "Nunca invente um número que não veio" in TEXTO


def test_a_regra_0_deixou_de_proibir_a_deducao_de_unidade():
    """A tabela de "erro evidente" da REGRA 0 trazia a linha que proibia
    exatamente o que o usuário agora pede. Se ela voltar, a IA recebe duas
    ordens opostas no mesmo texto -- e a REGRA 0 é a soberana, então a
    proibição venceria em silêncio."""
    assert "devolver o número como veio" not in TEXTO, (
        "A linha da tabela da REGRA 0 que mandava devolver o número sem "
        "deduzir a unidade voltou, e ela contradiz a regra 3."
    )


# =============================================================================
# 3. Coerência interna -- os erros que a dedução pode introduzir
# =============================================================================
def test_o_mesmo_fator_vale_para_as_tres_medidas():
    """Comprimento em mm e largura em cm na mesma caixa é erro de leitura,
    não fornecedor misturando unidade."""
    assert "MESMO fator" in TEXTO


def test_uma_unidade_declarada_contamina_as_outras_duas():
    """Se o fornecedor escreveu "500 mm" no comprimento e só números nas
    outras, ele preencheu a mesma linha do formulário na mesma unidade."""
    assert "vale para as três" in TEXTO


def test_o_peso_liquido_nunca_passa_do_bruto():
    """Checagem de graça que pega justamente o erro que a dedução pode
    criar: um dos dois pesos convertido e o outro não."""
    assert "nunca" in TEXTO and "maior que o bruto" in TEXTO


def test_na_duvida_genuina_o_numero_fica_como_veio():
    """A dedução vale contra o absurdo, não contra o meramente incerto -- é
    o que sobra do pedido original de fidelidade."""
    assert "fique com o número como veio" in TEXTO


def test_o_prompt_continua_proibindo_arredondar():
    """Regressão: o campo do portal não tem limite de casas decimais
    (confirmado pelo HTML em 2026-08-19). Arredondar perde informação que a
    ficha trouxe, e a dedução não muda isso."""
    assert TEXTO.count("NÃO ARREDONDE") >= 2, (
        "A proibição de arredondar tem de valer para dimensões E para peso."
    )
