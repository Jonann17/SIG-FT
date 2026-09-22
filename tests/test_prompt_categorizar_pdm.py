r"""Propriedades de CONTEÚDO do prompt de escolha de PDM (`categorizar_pdm`).

Por que este arquivo existe, separado do snapshot: `tests/test_llm_prompts_snapshot.py`
prova que o prompt não mudou por acidente, mas uma fixture regenerada não
consegue provar nada sobre si mesma. As propriedades que a reescrita de
2026-09-22 introduziu -- e que uma regressão silenciosa desfaria -- moram
aqui, checadas por conteúdo. É a mesma divisão de
`tests/test_prompt_condicoes_fidelidade.py` (CP de 2026-08-18).

O QUE A REESCRITA CONSERTOU, e que cada teste abaixo tranca
------------------------------------------------------------------------
Conferindo os 8 exemplos few-shot do prompt antigo, um a um, contra o
catálogo real (`PDMs_SAM-GM_1193.xlsx`, 1193 PDMs) na REVISÃO VIGENTE de cada
PDM, DOIS estavam errados:

  1. `PDM.4020.001 - BOMBA CENTRIFUGA` -- o código NÃO EXISTE, e não há
     nenhum "BOMBA CENTRIFUGA" no catálogo sob qualquer código. O certo para
     uma bomba KSB é `PDM.4320.007 - BOMBA` (classe 4320).
  2. `PDM.6145.011 - CABO, TRANSMISSAO DADOS` -- o código existe, o título
     real NÃO tem a vírgula. E é essa string que vai ser digitada no filtro
     de PDM do portal.
⚠️ Um TERCEIRO foi acusado por engano e ABSOLVIDO no mesmo dia:
`PDM.7010.018 - SERVIDOR` estava CERTO. A acusação nasceu de um defeito do
leitor do catálogo, que pegava o título da PRIMEIRA linha do código em vez do
da revisão VIGENTE -- e na revisão 0 esse PDM se chamava "SERVIDOR CONSOLE".
Na vigente (rev 2, 28/02/2025) ele é "SERVIDOR". O teste que trancava a
acusação virou o teste que tranca a absolvição.

E um outro, corrigido pelas NOTAS DO PRÓPRIO CATÁLOGO: o exemplo da câmera
apontava `PDM.6720.001 - CAMERA`, da classe 6720 = "CÁMARAS FOTOGRÁFICAS". A
AXIS P1375-E é câmera de rede; a classe 6710 exclui explicitamente "CÂMERAS
DE VÍDEO (COA 5836)" e a 5836 inclui "equipos electrónicos de video, como
[...] cámaras". O PDM certo é `PDM.5836.000 - CAMERA VIDEO`.

Exemplo few-shot é o sinal MAIS FORTE de um prompt. Ensinar um código
fabricado é ensinar o formato de fabricar código -- é por isso que estes
testes existem, e não são cosméticos.
"""
from __future__ import annotations

from sigft.core.llm import prompts


def _prompt():
    return prompts.montar_categorizar_pdm(
        "<<<INSTRUCOES>>>", "<<<LISTA_PDMS>>>", "<<<ITENS_TEXTO>>>"
    )


# =============================================================================
# 1. Os exemplos errados não voltam
# =============================================================================
def test_nao_ensina_codigo_de_pdm_que_nao_existe():
    assert "PDM.4020.001" not in _prompt()


def test_nao_ensina_bomba_centrifuga_que_nao_esta_no_catalogo():
    assert "BOMBA CENTRIFUGA" not in _prompt()


def test_nao_ensina_o_titulo_de_cabo_com_virgula():
    """A vírgula é exatamente o caractere que o filtro do portal não casaria."""
    assert "CABO, TRANSMISSAO DADOS" not in _prompt()


def _pdms_escolhidos_nos_exemplos():
    """Os PDMs que os exemplos apresentam como RESPOSTA (as linhas
    "- PDM: ...")."""
    return [
        linha.split(":", 1)[1].strip()
        for linha in _prompt().splitlines()
        if linha.strip().startswith("- PDM:")
    ]


def test_usa_o_titulo_vigente_do_pdm_de_servidor():
    """`PDM.7010.018` é "SERVIDOR" na revisão vigente e "SERVIDOR CONSOLE" na
    revisão 0. O título digitado no filtro do portal tem que ser o vigente --
    o antigo não filtra nada, e a automação quebra com o PDM certo escolhido."""
    escolhidos = _pdms_escolhidos_nos_exemplos()
    assert escolhidos, "nenhum exemplo com linha '- PDM:' foi encontrado"
    assert "PDM.7010.018 - SERVIDOR" in escolhidos
    assert not any("SERVIDOR CONSOLE" in p for p in escolhidos)


def test_nao_usa_camera_fotografica_para_camera_de_rede():
    """A classe 6720 é "CÁMARAS FOTOGRÁFICAS" e a 6710 exclui câmeras de
    vídeo remetendo à 5836 -- o catálogo já responde qual é a certa."""
    assert "PDM.6720.001" not in _prompt()


# =============================================================================
# 2. O elo que faltava entre o manual e a lista
# =============================================================================
def test_diz_que_o_codigo_do_pdm_embute_a_classe_fsc():
    """O prompt antigo mandava "ache a classe no manual, depois escolha o PDM
    daquela classe" -- sem nunca dizer que os 4 dígitos do meio do código SÃO
    a classe. A regra é determinística em todos os PDMs válidos do arquivo."""
    texto = _prompt()
    assert "PDM.XXXX.YYY" in texto
    assert "classe" in texto.lower()


# =============================================================================
# 3. Lista fechada -- a IA não pode inventar PDM
# =============================================================================
def test_manda_escolher_uma_string_que_aparece_literalmente_na_lista():
    assert "literalmente" in _prompt().lower()


def test_manda_responder_nenhum_quando_nada_serve():
    texto = _prompt()
    assert "NENHUM" in texto


def test_proibe_inventar_codigo_de_pdm():
    assert "invent" in _prompt().lower()


# =============================================================================
# 4. O contrato de JSON não pode mudar -- o parser lê campo a campo por nome
# =============================================================================
def test_preserva_todas_as_chaves_do_json_que_o_app_le():
    """`services/cria_fichas.processar_item_individual` e
    `app/views/cria_fichas.py` leem estes nomes. Mudar qualquer um quebra o
    preenchimento da ficha no portal, em silêncio."""
    texto = _prompt()
    for chave in ("item_processado", "pdm_escolhido", "descricao_curta",
                  "origem", "tipo de fabricação", "tipo", "unidade"):
        assert f'"{chave}"' in texto, chave


def test_preserva_os_valores_permitidos_de_unidade():
    texto = _prompt()
    for valor in ("Unidade", "Peça", "Conjunto", "metro - (m)", "litro - (l)"):
        assert valor in texto, valor


def test_preserva_os_valores_permitidos_de_origem_tipo_e_fabricacao():
    texto = _prompt()
    for valor in ("Importado", "Nacional", "Catálogo", "Especial",
                  "Reparável", "Não Reparável"):
        assert valor in texto, valor


def test_manda_responder_so_o_json():
    assert "Responda APENAS com a lista JSON" in _prompt()


# =============================================================================
# 5. item_processado deixou de ser decorativo
# =============================================================================
def test_exige_que_item_processado_repita_o_numero_do_item():
    """A view passou a casar a resposta com o item PELO `item_processado`, em
    vez de pela posição na lista. Antes, um item pulado pela IA deslocava
    todas as linhas seguintes -- cada material recebia o PDM de outro, sem
    nenhum aviso. Para isso funcionar, o prompt tem que exigir o número."""
    texto = _prompt()
    assert "item_processado" in texto
    assert "### ITEM" in texto


# =============================================================================
# 6. Interpolação dos três blocos
# =============================================================================
def test_interpola_instrucoes_lista_e_itens():
    texto = _prompt()
    assert "<<<INSTRUCOES>>>" in texto
    assert "<<<LISTA_PDMS>>>" in texto
    assert "<<<ITENS_TEXTO>>>" in texto
