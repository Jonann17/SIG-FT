r"""
O prompt de Condições não pode MANDAR a IA inventar.

Contexto (2026-08-18). O usuário relatou que o módulo de Condições estava
"inventando coisas que o fornecedor não escreveu". A investigação mostrou que
não era alucinação do modelo: `SYSTEM_CONDICOES` **instruía** isso, em quatro
lugares distintos, e os exemplos few-shot ensinavam o padrão citando normas
técnicas como se fossem fato apurado.

A regra que o usuário definiu para a reescrita:

    "corrigido para não inventar, salvo o caso de que realmente esteja errado,
    evidentemente errado; se a IA não tiver certeza, a regra é para seguir o
    texto que o fornecedor colocou."

Por que este arquivo existe, e por que ele NÃO é uma comparação com fixture:
`tests/test_llm_prompts.py` já compara `SYSTEM_CONDICOES` byte a byte com
`tests/fixtures/prompts/upload_conditions_system.txt`. Essa trava pega
mudança acidental, mas é circular para o que importa aqui -- quem regenera a
fixture regenera junto qualquer instrução ruim que tenha reintroduzido, e o
teste passa. Um teste de CONTEÚDO não tem esse buraco: ele falha mesmo se a
fixture for atualizada.

O alvo é sempre o TEXTO DO PROMPT -- nunca a saída de um modelo. Não há
chamada de rede aqui, nem julgamento de resposta de IA: instrução escrita é
determinística e é a única coisa que este projeto controla.
"""
from sigft.core.llm import prompts


# =============================================================================
# 1. As instruções que MANDAVAM inventar não podem voltar
# =============================================================================
# Cada trecho abaixo é literal do prompt anterior (ver o commit da reescrita).
# Estão aqui como frases inteiras, e não como palavras soltas, porque o que se
# proíbe é a INSTRUÇÃO -- "substituir" ou "corrigir" isolados são palavras
# legítimas em outros contextos do mesmo texto.
INSTRUCOES_DE_INVENCAO_REMOVIDAS = (
    # Regra 1: mandava preencher campo em branco com o que "costuma ser".
    "complete-o baseado no tipo de equipamento",
    # Regra 12: mandava trocar texto genérico por norma inventada.
    "Você deve **SUBSTITUIR** por um texto técnico completo citando as leis aplicáveis",
    # Regra 13: mandava reclassificar o material contra o que o fornecedor disse.
    "você deve **CORRIGIR para \"SIM\"**",
    # Regra 15: o pior deles -- mandava descartar a entrada do fornecedor.
    "você **DEVE IGNORAR** a entrada",
    # Regra 15, continuação: mandava usar conhecimento próprio no lugar dela.
    "use seu conhecimento de engenharia sobre o",
)


def test_nenhuma_instrucao_de_invencao_sobrevive_no_prompt():
    presentes = [t for t in INSTRUCOES_DE_INVENCAO_REMOVIDAS
                 if t in prompts.SYSTEM_CONDICOES]
    assert presentes == [], (
        "O prompt de Condições voltou a mandar a IA inventar. Trechos "
        f"reintroduzidos: {presentes}"
    )


# =============================================================================
# 2. Nenhuma norma técnica pode ser citada pelo próprio prompt
# =============================================================================
# Os exemplos few-shot antigos traziam estes números como resposta "esperada".
# Um exemplo não é uma sugestão: é o padrão que o modelo copia. Enquanto
# estiverem no texto, a IA os reproduz em fichas onde ninguém os mencionou.
#
# A checagem é sobre o PROMPT, não sobre a saída: se nenhuma norma está escrita
# aqui, nenhuma pode ser copiada daqui.
NORMAS_QUE_O_PROMPT_NAO_PODE_CITAR = (
    "NBR IEC 60947-2",
    "NBR 5410",
    "ISO 5208",
    "ISO 5599",
    "ASME B16.34",
    "NBR 15827",
    "NBR 12288",
    "Lei 12.305/2010",
    "Ley 12.305/2010",
    "Lei 3956/09",
    "Ley 3956/09",
)


def test_prompt_nao_cita_norma_nem_lei_como_resposta_modelo():
    citadas = [n for n in NORMAS_QUE_O_PROMPT_NAO_PODE_CITAR
               if n in prompts.SYSTEM_CONDICOES]
    # A Lei 12.305/2010 aparece UMA vez no texto novo, mas dentro do
    # "EXEMPLO 2 -- o que NÃO fazer", que ensina o oposto. Se ela voltar a
    # aparecer, este teste exige que seja só ali.
    fora_do_contraexemplo = [n for n in citadas if n not in ("Lei 12.305/2010", "Lei 3956/09")]
    assert fora_do_contraexemplo == [], (
        "O prompt voltou a citar norma/lei como resposta a ser produzida: "
        f"{fora_do_contraexemplo}"
    )


def test_a_unica_lei_citada_esta_no_contraexemplo():
    """A Lei 12.305/2010 sobrevive só como exemplo do que NÃO fazer."""
    texto = prompts.SYSTEM_CONDICOES
    if "Lei 12.305/2010" not in texto:
        return  # sumiu de vez: melhor ainda
    marcador = "EXEMPLO 2"
    assert marcador in texto, "A lei aparece sem o contraexemplo que a explica"
    # Tudo que vem depois do marcador é o bloco do contraexemplo; a lei não
    # pode aparecer ANTES dele (onde seria instrução, não advertência).
    antes = texto.split(marcador, 1)[0]
    assert "Lei 12.305/2010" not in antes, (
        "A Lei 12.305/2010 voltou a aparecer como instrução, fora do "
        "contraexemplo"
    )


# =============================================================================
# 3. A regra de fidelidade precisa estar escrita, e precisa ser soberana
# =============================================================================
# Remover as instruções ruins não basta: sem uma regra explícita, o modelo
# preenche o vazio com "ser prestativo" -- que é exatamente o comportamento
# que produziu o problema.
def test_a_regra_de_fidelidade_existe_e_e_declarada_soberana():
    texto = prompts.SYSTEM_CONDICOES
    assert "REGRA 0" in texto
    assert "FIDELIDADE AO FORNECEDOR" in texto
    assert "soberana" in texto.lower()


def test_o_prompt_proibe_acrescentar_informacao_que_nao_esta_na_entrada():
    texto = prompts.SYSTEM_CONDICOES.lower()
    assert "nunca acrescente informação que não esteja na entrada" in texto


def test_campo_vazio_permanece_vazio():
    texto = prompts.SYSTEM_CONDICOES.lower()
    assert "campo vazio permanece vazio" in texto


def test_o_prompt_proibe_citar_norma_que_nao_veio_na_entrada():
    texto = prompts.SYSTEM_CONDICOES.lower()
    assert "nunca cite lei, norma" in texto
    assert "que não esteja escrito na entrada" in texto


def test_na_duvida_vence_o_texto_do_fornecedor():
    """O pedido literal do usuário: incerteza ⇒ fica o que o fornecedor pôs."""
    texto = prompts.SYSTEM_CONDICOES.lower()
    assert "na dúvida, o texto do fornecedor vence" in texto


# =============================================================================
# 4. A exceção ("evidentemente errado") precisa de um TESTE, não de bom senso
# =============================================================================
# O usuário autorizou correção só quando o erro é evidente. "Evidente" sem
# critério é convite a voltar ao comportamento antigo por outro caminho -- o
# modelo sempre acha que sabe. O prompt define isso operacionalmente: se
# precisar de conhecimento externo sobre o material, não é evidente.
def test_a_excecao_de_erro_evidente_traz_o_criterio_operacional():
    texto = prompts.SYSTEM_CONDICOES
    assert "erro EVIDENTE" in texto
    baixo = texto.lower()
    assert "sem apelar ao seu conhecimento" in baixo
    assert "não é evidente" in baixo


def test_reclassificar_perigoso_por_conta_propria_e_proibido():
    """O caso concreto que o prompt antigo mandava fazer (regra 13)."""
    texto = prompts.SYSTEM_CONDICOES
    assert "NÃO reclassifique por conta própria" in texto


# =============================================================================
# 5. O contrato de JSON não pode ter mudado junto
# =============================================================================
# `upload_conditions.processar_lista` lê o resultado campo a campo por NOME
# (`ficha["dimensoes"]["comprimento"]`, `ficha.get("legislacao_es")`, ...).
# Reescrever a política de conteúdo não pode renomear chave nenhuma, ou o RPA
# passa a preencher o portal com vazio sem reclamar de nada.
CHAVES_QUE_O_RPA_CONSOME = (
    "pmib_codigo",
    "dimensoes",
    "controle_temperatura",
    "posicao_armazenamento",
    "nocivo",
    "peso",
    "sujeito_intemperie",
    "protecao",
    "empilhamento",
    "outros_cuidados",
    "embalagem_transp_es",
    "embalagem_transp_pt",
    "posicao_icagem_es",
    "posicao_icagem_pt",
    "cuidad_preserv_es",
    "cuidad_preserv_pt",
    "limpeza_secagem_es",
    "limpeza_secagem_pt",
    "ferramentas_es",
    "ferramentas_pt",
    "legislacao_es",
    "legislacao_pt",
    "descarte_es",
    "descarte_pt",
    "perigoso_10004",
    "logistica_reversa",
)


def test_todas_as_chaves_consumidas_pelo_rpa_seguem_descritas_no_prompt():
    ausentes = [c for c in CHAVES_QUE_O_RPA_CONSOME
                if c not in prompts.SYSTEM_CONDICOES]
    assert ausentes == [], (
        "A reescrita do prompt deixou de descrever chaves que o RPA lê -- o "
        f"portal seria preenchido com vazio: {ausentes}"
    )
