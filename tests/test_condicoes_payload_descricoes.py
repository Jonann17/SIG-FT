r"""
Contrato entre o payload de Condições e o prompt.

Fica separado de `test_prompt_condicoes_unidades.py` de propósito: aquele
arquivo lê SÓ o texto do prompt (`sigft/core/llm/prompts.py`, zona
compartilhada com a frente do AutoSpecAI, que vai em commit isolado); este
aqui lê o SERVIÇO. Separar mantém cada commit verde por si.

O que ele tranca: a IA só consegue deduzir a unidade de uma medida se
souber o que é o material, e ela só sabe disso pelas chaves que o serviço
manda. Prompt citando chave que o payload não envia é instrução para olhar
um campo que não existe -- e falha em silêncio, porque o JSON continua
válido e a resposta continua vindo.
"""
import inspect

from sigft.core.llm import prompts

TEXTO = prompts.SYSTEM_CONDICOES


def test_as_chaves_de_descricao_citadas_no_prompt_sao_as_que_o_servico_envia():
    """Prompt e payload não podem divergir: uma chave citada aqui e não
    enviada lá vira instrução para olhar um campo que não existe.

    As duas fontes são do usuário: *"vem da descrição do STATUS_PMIB e da
    célula H6 da própria ficha (...) mas o do _STATUS_PMIB é melhor"*.
    """
    from sigft.services import upload_conditions

    fonte = inspect.getsource(upload_conditions.ConditionsProcessor.processar_ia_lote)
    for chave in ("Descrição do material", "Descrição breve da ficha"):
        assert f"'{chave}'" in fonte or f'"{chave}"' in fonte, (
            f"O prompt cita a chave {chave!r}, mas `processar_ia_lote` não a "
            f"envia no payload."
        )
        assert chave in TEXTO, (
            f"O serviço envia {chave!r} e o prompt não diz para usá-la."
        )
