r"""Tradução das perguntas dos PDMs para inglês (2026-08-28; da planilha desde 2026-10-21).

**Por que existe** (pedido do usuário): o SIG-FT tem dois templates de ficha —
PT-BR e inglês — mas as características técnicas vêm da planilha de PDMs, em
português. Traduzir essas perguntas na mão, ficha a ficha, era o trabalho.

Desde 2026-10-21 a ficha em inglês sai direto da planilha: o montador traduz
as perguntas do lote (glossário e cache na pasta de dados do usuário). Antes
era preciso traduzir uma pasta de PDMs Modificados, que saiu do SIG-FT.

**O que este arquivo NÃO testa:** o motor de tradução de verdade (IA ou
`deep_translator`). Ele é injetado, sempre. Um teste que dependesse da
internet mediria a rede, não o código — e não rodaria na suíte.
"""
import os

import pytest

from sigft.services import traducao_pdm as tp


def _falso(pares):
    """Motor de tradução falso: devolve 'EN:<original>' para cada texto."""
    def traduzir(textos):
        return [pares.get(t, f"EN:{t}") for t in textos]
    return traduzir


# =============================================================================
# A. Quebrar a pergunta em partes — o que traduz e o que NÃO traduz
# =============================================================================
def test_o_numero_da_pergunta_nao_e_traduzido():
    """`"1 - Pressão de trabalho (bar):"` — o `1 - ` é numeração da lista, e
    mandá-lo para um tradutor é pedir para ele inventar."""
    prefixo, miolo, sufixo = tp.partes_da_pergunta("1 - Pressão de trabalho (bar):")
    assert prefixo == "1 - "
    assert miolo == "Pressão de trabalho (bar)"
    assert sufixo == ":"


def test_pergunta_sem_numeracao_tambem_funciona():
    prefixo, miolo, sufixo = tp.partes_da_pergunta("Material de fabricação")
    assert prefixo == ""
    assert miolo == "Material de fabricação"
    assert sufixo == ""


def test_numero_de_dois_digitos():
    prefixo, miolo, _ = tp.partes_da_pergunta("12 - Vazão (l/min):")
    assert prefixo == "12 - "
    assert miolo == "Vazão (l/min)"


def test_a_montagem_de_volta_devolve_a_frase_inteira():
    original = "7 - Tensão de isolamento (kV):"
    prefixo, miolo, sufixo = tp.partes_da_pergunta(original)
    assert prefixo + miolo + sufixo == original


def test_texto_vazio_nao_quebra():
    assert tp.partes_da_pergunta(None) == ("", "", "")
    assert tp.partes_da_pergunta("   ") == ("", "", "")


# =============================================================================
# B. O glossário — corrigir uma vez e valer sempre
# =============================================================================
def test_glossario_vazio_quando_o_arquivo_nao_existe(tmp_path):
    assert tp.carregar_glossario(str(tmp_path / "nao_existe.txt")) == {}


def test_glossario_le_pares_pt_igual_en(tmp_path):
    arquivo = tmp_path / "g.txt"
    arquivo.write_text("vazão = flow rate\niçamento = lifting\n", encoding="utf-8")
    assert tp.carregar_glossario(str(arquivo)) == {
        "vazão": "flow rate", "içamento": "lifting"}


def test_glossario_ignora_comentario_e_linha_em_branco(tmp_path):
    arquivo = tmp_path / "g.txt"
    arquivo.write_text("# como usar\n\nvazão = flow rate\n\n# fim\n", encoding="utf-8")
    assert tp.carregar_glossario(str(arquivo)) == {"vazão": "flow rate"}


def test_glossario_aguenta_ANSI_do_bloco_de_notas(tmp_path):
    """Mesma lição do `.txt` da conferência do AutoSpec: o arquivo é para ser
    editado à mão, e o Bloco de Notas ainda oferece ANSI no 'Salvar como'."""
    arquivo = tmp_path / "g.txt"
    arquivo.write_bytes("vazão = flow rate\n".encode("cp1252"))
    assert tp.carregar_glossario(str(arquivo)) == {"vazão": "flow rate"}


def test_frase_inteira_no_glossario_NAO_chama_o_motor(tmp_path):
    """A correção do usuário vence o motor — é o ponto do glossário."""
    chamou = []

    def traduzir(textos):
        chamou.extend(textos)
        return [f"EN:{t}" for t in textos]

    glossario = {"Pressão de trabalho (bar)": "Working pressure (bar)"}
    saida = tp.traduzir_textos(["1 - Pressão de trabalho (bar):"], traduzir, glossario)
    assert saida == ["1 - Working pressure (bar):"]
    assert chamou == [], "o glossário deveria ter resolvido sem o motor"


def test_o_glossario_cria_um_arquivo_de_exemplo_explicando_o_uso(tmp_path):
    caminho = tp.criar_glossario_exemplo(str(tmp_path))
    texto = open(caminho, encoding="utf-8").read()
    assert "=" in texto
    assert "#" in texto  # tem instrução comentada
    assert os.path.dirname(caminho) == str(tmp_path)


def test_criar_glossario_NAO_sobrescreve_o_que_o_usuario_editou(tmp_path):
    caminho = tp.criar_glossario_exemplo(str(tmp_path))
    with open(caminho, "a", encoding="utf-8") as fh:
        fh.write("vazão = flow rate\n")
    tp.criar_glossario_exemplo(str(tmp_path))
    assert "flow rate" in open(caminho, encoding="utf-8").read()


# =============================================================================
# C. Cache — o mesmo texto não é traduzido duas vezes
# =============================================================================
def test_texto_repetido_vai_UMA_vez_ao_motor():
    """Perguntas se repetem entre PDMs ('Fabricante', 'Modelo', 'Peso'). Sem
    dedupe, uma pasta grande paga a mesma tradução dezenas de vezes — e, no
    caminho da `deep_translator`, cada item custa 1 segundo de espera."""
    chamou = []

    def traduzir(textos):
        chamou.extend(textos)
        return [f"EN:{t}" for t in textos]

    entrada = ["1 - Peso (kg):", "2 - Peso (kg):", "3 - Vazão (l/min):"]
    saida = tp.traduzir_textos(entrada, traduzir, {})
    assert chamou == ["Peso (kg)", "Vazão (l/min)"]
    assert saida == ["1 - EN:Peso (kg):", "2 - EN:Peso (kg):", "3 - EN:Vazão (l/min):"]


def test_o_cache_sobrevive_entre_execucoes(tmp_path):
    cache = tp.Cache(str(tmp_path))
    cache.guardar("Vazão (l/min)", "Flow rate (l/min)")
    cache.salvar()

    outro = tp.Cache(str(tmp_path))
    assert outro.buscar("Vazão (l/min)") == "Flow rate (l/min)"


def test_cache_corrompido_nao_derruba_a_traducao(tmp_path):
    (tmp_path / tp.NOME_CACHE).write_text("{isto não é json", encoding="utf-8")
    assert tp.Cache(str(tmp_path)).buscar("qualquer") is None


# =============================================================================
# D. Traduzir as perguntas da planilha (2026-10-21)
# =============================================================================
# A ficha em inglês sai da planilha de PDMs: as perguntas de todas as fichas
# do lote são traduzidas ANTES de montar (`preparar_traducao`, em lotes, sem
# repetir texto), e cada ficha só consulta o que ficou pronto
# (`traducao_conhecida`). O que não traduziu fica em português e é contado:
# uma falha do tradutor nunca derruba o lote.
def test_o_glossario_e_o_cache_moram_na_pasta_de_dados_do_usuario(monkeypatch, tmp_path):
    from sigft.core import dados_usuario

    monkeypatch.setattr(dados_usuario, "pasta_dados", lambda: tmp_path)
    assert tp.pasta_da_traducao() == str(tmp_path / "traducao_pdm")


def test_preparar_manda_ao_motor_so_o_que_falta_uma_vez_cada(tmp_path):
    chamou = []

    def motor(textos):
        chamou.append(list(textos))
        return [f"EN:{t}" for t in textos]

    cache = tp.Cache(str(tmp_path))
    cache.guardar("Peso (kg)", "Weight (kg)")
    falhas = tp.preparar_traducao(
        ["1 - Peso (kg):", "2 - Vazão (l/min):", "1 - Vazão (l/min):", "3 - Modelo:"],
        motor, {"Modelo": "Model"}, cache)
    assert falhas == 0
    assert chamou == [["Vazão (l/min)"]]
    assert cache.buscar("Vazão (l/min)") == "EN:Vazão (l/min)"


def test_preparar_vai_em_lotes(tmp_path, monkeypatch):
    monkeypatch.setattr(tp, "TEXTOS_POR_LOTE", 2)
    chamou = []

    def motor(textos):
        chamou.append(len(textos))
        return [f"EN:{t}" for t in textos]

    tp.preparar_traducao([f"{i} - P{i}:" for i in range(1, 6)], motor, {}, tp.Cache(str(tmp_path)))
    assert chamou == [2, 2, 1]


def test_lote_que_falha_nao_derruba_e_os_outros_seguem(tmp_path, monkeypatch):
    monkeypatch.setattr(tp, "TEXTOS_POR_LOTE", 2)
    avisos = []

    def motor(textos):
        if "P1" in textos:
            raise OSError("rede bloqueada")
        return [f"EN:{t}" for t in textos]

    cache = tp.Cache(str(tmp_path))
    falhas = tp.preparar_traducao(["1 - P1:", "2 - P2:", "3 - P3:"], motor, {}, cache,
                                  avisar=avisos.append)
    assert falhas == 1
    assert cache.buscar("P1") is None and cache.buscar("P3") == "EN:P3"
    assert len(avisos) == 1 and "rede bloqueada" in avisos[0]


def test_o_cache_vai_para_o_disco_ao_fim_do_preparo(tmp_path):
    tp.preparar_traducao(["1 - Vazão:"], lambda t: [f"EN:{x}" for x in t], {}, tp.Cache(str(tmp_path)))
    assert tp.Cache(str(tmp_path)).buscar("Vazão") == "EN:Vazão"


def test_pergunta_cujo_nome_comeca_por_numero_e_traduzida_e_fica_no_cache(tmp_path):
    """Revisão de 2026-10-21: o miolo "4-20 mA SAIDA" era quebrado DE NOVO
    ("4-" + "20 mA SAIDA"), a chave do cache nunca casava e a pergunta ficava
    em português, reenviada a cada rodada."""
    chamou = []

    def motor(textos):
        chamou.append(list(textos))
        return [f"EN {t}" for t in textos]

    cache = tp.Cache(str(tmp_path))
    tp.preparar_traducao(["3 - 4-20 mA SAIDA:"], motor, {}, cache)
    assert chamou == [["4-20 mA SAIDA"]]
    assert tp.traducao_conhecida(["3 - 4-20 mA SAIDA:"], {}, cache) == (["3 - EN 4-20 mA SAIDA:"], 0)

    segundo = tp.Cache(str(tmp_path))      # a próxima rodada, do disco
    tp.preparar_traducao(["3 - 4-20 mA SAIDA:"], motor, {}, segundo)
    assert len(chamou) == 1, "a segunda rodada deveria sair do cache"


def test_traducao_igual_a_entrada_e_valida_e_vai_para_o_cache(tmp_path):
    """"NCM", "PT-100": traduzem para eles mesmos. Não podem contar como
    "sem tradução" a cada rodada."""
    cache = tp.Cache(str(tmp_path))
    avisos = []
    tp.preparar_traducao(["1 - NCM:", "2 - Vazão:"], lambda t: [t[0], "Flow rate"], {}, cache,
                         avisar=avisos.append)
    assert cache.buscar("NCM") == "NCM" and cache.buscar("Vazão") == "Flow rate"
    assert avisos == []


def test_resposta_vazia_nao_vai_para_o_cache(tmp_path):
    cache = tp.Cache(str(tmp_path))
    tp.preparar_traducao(["1 - Vazão:", "2 - Peso:"], lambda t: [None, ""], {}, cache)
    assert cache.buscar("Vazão") is None and cache.buscar("Peso") is None


def test_tradutor_mudo_avisa_UMA_vez_e_nao_congela_o_portugues(tmp_path, monkeypatch):
    """Tudo voltou igual à entrada: é o tradutor sem rede ou sem chave. Um
    aviso só no lote, e nada no cache (a próxima rodada pergunta de novo)."""
    monkeypatch.setattr(tp, "TEXTOS_POR_LOTE", 2)
    cache = tp.Cache(str(tmp_path))
    avisos = []
    textos = [f"{i} - CARACTERISTICA {i}:" for i in range(1, 7)]
    tp.preparar_traducao(textos, lambda t: list(t), {}, cache, avisar=avisos.append)
    assert len(avisos) == 1 and "identic" in avisos[0]
    assert cache.buscar("CARACTERISTICA 1") is None


def test_traducao_conhecida_usa_glossario_e_cache_e_conta_o_que_faltou(tmp_path):
    cache = tp.Cache(str(tmp_path))
    cache.guardar("Vazão (l/min)", "Flow rate (l/min)")
    saida, faltaram = tp.traducao_conhecida(
        ["1 - Vazão (l/min):", "2 - Modelo:", "3 - Peso (kg):", None, ""],
        {"Modelo": "Model"}, cache)
    assert saida == ["1 - Flow rate (l/min):", "2 - Model:", "3 - Peso (kg):", None, ""]
    assert faltaram == 1


# =============================================================================
# E. As frases REAIS (2026-09-03)
# =============================================================================
# Ate aqui os testes usavam frases curtas inventadas por mim -- "1 - Pressao de
# trabalho (bar):". O usuario mandou o template em ingles e uma ficha ja
# preenchida, e a forma real e OUTRA: nome da caracteristica em MAIUSCULAS,
# seguido de uma INSTRUCAO DE PREENCHIMENTO inteira entre parenteses, com
# parenteses aninhados dentro. Sao 100-200 caracteres, nao um rotulo.
#
# Isto nao e detalhe de estilo: o prompt dizia "PRESERVE a unidade entre
# parenteses exatamente como esta", escrito quando eu achava que o parenteses
# continha "(bar)". Aplicada a "(Indicar a tensao de alimentacao do item em
# (V))", essa regra manda o modelo devolver a instrucao inteira em portugues --
# ficha meio traduzida, e nenhum teste da suite reclamaria, porque todos os
# meus exemplos casavam com a minha suposicao errada.
#
# As frases abaixo sao copia literal de:
#   PT: 4500063671.0071_completed.xlsx, aba "Ficha Tecnica Padrao", C79:C95
#   EN: 4500063671.0052_enUS.xlsx, aba "Standard Technical Sheet", C79:C92
PERGUNTAS_REAIS_PT = [
    "1 - FAIXA DE TEMPERATURA DE USO (Indicar a faixa de temperatura de uso do item em grau Celsius (°C).):",
    "2 - SINAL DE ENTRADA (Indicar o sinal de entrada do item em (mV, V, A, mA) ex.: 4-20mA, 0-5 V, outros):",
    "4 - TENSAO DE ALIMENTACAO (Indicar a tensão de alimentação do item em (V)):",
    "6 - NORMAS TECNICAS APLICAVEIS (Indicar quais as normas técnicas aplicáveis ao item.):",
    "9 - TIPO CONSTRUTIVO (Indicar o tipo construtivo do item. Nota: Material especifico de compra com (Número de desenho, referência, nome usual, outros)):",
    "12 - APLICACAO (Indicar a aplicação do item. Nota: mencionar o equipamento (tipo, modelo) (ex.: Red EIA, 2 fios, diferencial RS485, red EIA 4 fios direferencial RS 485, fibra optica, outros).):",
    "17 - DIMENSOES (Indicar as dimensões do item (in, mm) ex.: comp. x larg. x alt.):",
]

# Traducoes da CASA, extraidas da ficha em ingles que o usuario entregou. Sao
# a referencia de estilo -- nao invencao minha.
PARES_REAIS_DA_CASA = [
    ("NORMAS TECNICAS APLICAVEIS", "APPLICABLE TECHNICAL STANDARDS"),
    ("CARACTERISTICAS ADICIONAIS", "ADDITIONAL CHARACTERISTICS"),
    ("TIPO CONSTRUTIVO", "TYPE OF CONSTRUCTION"),
    ("CERTIFICADO", "CERTIFICATE"),
]


@pytest.mark.parametrize("pergunta", PERGUNTAS_REAIS_PT)
def test_a_frase_real_remonta_EXATAMENTE(pergunta):
    """Nada pode se perder na ida e volta: o que sai da divisao, concatenado,
    tem de ser byte a byte o original. Parenteses aninhados e o ".)" antes dos
    dois pontos sao os pontos onde uma regex desatenta come um caractere."""
    prefixo, miolo, sufixo = tp.partes_da_pergunta(pergunta)
    assert f"{prefixo}{miolo}{sufixo}" == pergunta


@pytest.mark.parametrize("pergunta", PERGUNTAS_REAIS_PT)
def test_a_INSTRUCAO_entre_parenteses_vai_junto_para_o_motor(pergunta):
    """O miolo tem de levar a instrucao inteira. Se a divisao deixasse o
    parenteses para tras, o motor traduziria so o nome e a ficha em ingles
    sairia com metade de cada linha em portugues."""
    _, miolo, _ = tp.partes_da_pergunta(pergunta)
    assert "(Indicar" in miolo or "(indicar" in miolo
    assert miolo.rstrip().endswith(")")


def test_o_numero_da_pergunta_real_NAO_vai_ao_motor():
    """Vale para numero de dois digitos tambem -- `12 - `, nao so `1 - `."""
    enviados = []

    def espiao(textos):
        enviados.extend(textos)
        return [f"EN:{t}" for t in textos]

    tp.traduzir_textos(PERGUNTAS_REAIS_PT, espiao)
    assert enviados, "o motor deveria ter sido chamado"
    for texto in enviados:
        assert not texto[0].isdigit(), f"a numeracao vazou para o motor: {texto!r}"


# -----------------------------------------------------------------------------
# O prompt precisa DESCREVER a forma real, e mostrar um exemplo dela
# -----------------------------------------------------------------------------
def test_o_prompt_traz_a_frase_real_INTEIRA():
    from sigft.core.llm import prompts
    texto = prompts.montar_traduzir_pdm([PERGUNTAS_REAIS_PT[4]])
    assert "Número de desenho" in texto, "a frase chegou truncada ao prompt"


def test_o_prompt_manda_TRADUZIR_a_instrucao_entre_parenteses():
    """A regra antiga ("preserve o que esta entre parenteses") produziria ficha
    meio em portugues. O prompt tem de dizer que o parenteses e INSTRUCAO."""
    from sigft.core.llm import prompts
    texto = prompts.montar_traduzir_pdm(["1 - X (Indicar o X do item.):"]).lower()
    assert "instru" in texto
    assert "traduza a instru" in texto or "traduza tambem a instru" in texto \
        or "traduza também a instru" in texto


def test_o_prompt_mostra_um_exemplo_REAL_da_casa():
    """Um exemplo trabalhado vale mais que tres regras -- e este exemplo veio
    da ficha em ingles que a propria Itaipu entregou, nao da minha cabeca."""
    from sigft.core.llm import prompts
    texto = prompts.montar_traduzir_pdm(["1 - X:"])
    assert "APPLICABLE TECHNICAL STANDARDS" in texto
    assert "NORMAS TECNICAS APLICAVEIS" in texto


def test_o_prompt_manda_manter_o_NOME_em_maiusculas():
    """Estilo da casa: `NOME EM CAIXA ALTA (Instrucao em caixa normal)`."""
    from sigft.core.llm import prompts
    texto = prompts.montar_traduzir_pdm(["1 - X:"]).lower()
    assert "maiúscul" in texto or "maiuscul" in texto or "caixa alta" in texto


def test_o_glossario_de_exemplo_ja_vem_com_os_termos_da_CASA():
    """O usuario nao devia ter que descobrir sozinho como a Itaipu traduz
    'NORMAS TECNICAS APLICAVEIS' -- a ficha em ingles dele ja diz."""
    for pt, en in PARES_REAIS_DA_CASA:
        assert pt in tp.CABECALHO_GLOSSARIO, f"falta o termo {pt!r}"
        assert en in tp.CABECALHO_GLOSSARIO, f"falta a traducao {en!r}"


def test_os_termos_da_casa_sao_carregaveis_como_glossario(tmp_path):
    """Nao basta estarem no texto: tem de sobreviver ao parser, sem virar
    comentario nem perder o lado de la do `=`."""
    caminho = tp.criar_glossario_exemplo(str(tmp_path))
    glossario = tp.carregar_glossario(caminho)
    for pt, en in PARES_REAIS_DA_CASA:
        assert glossario.get(pt) == en, f"{pt!r} nao chegou ao glossario carregado"


# =============================================================================
# F. Tradutor mudo — a falha que se disfarça de sucesso (2026-09-03)
# =============================================================================
# O QUE ACONTECEU. O usuário rodou a tradução numa pasta de 1192 PDMs. O log
# dizia, arquivo após arquivo:
#
#     OK  PDM_1650_001 - ACUMULADOR_formatado.xlsx (0 pergunta(s))
#
# e os arquivos gerados estavam **em português**. Duas causas somadas:
#
#   1. `traduzir_pdm` não estava nos mapas que `get_llm` consulta, então a IA
#      nunca rodava (ver tests/test_llm_get_llm_factory.py);
#   2. o caminho de reserva (`deep_translator`) tem um `except` que, quando
#      Google e MyMemory falham — rede corporativa bloqueando —, devolve o
#      **texto original**. Nada muda no arquivo, e `traduzir_pasta` reporta OK.
#
# A causa nº 1 se conserta. A nº 2 é de FEITIO: um tradutor que devolve a
# entrada é indistinguível de um que traduziu bem um texto já em inglês. Por
# isso a reserva LEVANTA quando nada passou, em vez de devolver o original.

def test_deep_translator_sem_rede_LEVANTA_em_vez_de_devolver_o_original(monkeypatch):
    """Na origem do problema: quando Google E MyMemory falham para TODOS os
    textos, isso é o tradutor fora do ar — e tem de ser dito, não disfarçado
    de tradução."""
    import types

    falso = types.ModuleType("deep_translator")

    class _Quebrado:
        def __init__(self, **kwargs):
            pass

        def translate(self, texto):
            raise OSError("rede bloqueada pelo proxy corporativo")

    falso.GoogleTranslator = _Quebrado
    falso.MyMemoryTranslator = _Quebrado
    monkeypatch.setitem(__import__("sys").modules, "deep_translator", falso)
    monkeypatch.setattr(tp.time, "sleep", lambda _s: None)   # sem 1s por item

    with pytest.raises(tp.TraducaoIndisponivel) as erro:
        tp._traduzir_com_deep_translator(["Pressão de trabalho", "Vazão nominal"])

    assert "rede" in str(erro.value).lower() or "tradutor" in str(erro.value).lower()


# =============================================================================
# G. A fronteira
# =============================================================================
def test_o_servico_NAO_importa_interface():
    from test_sem_interface_antiga import MODULOS_PROIBIDOS

    import ast
    import inspect
    arvore = ast.parse(inspect.getsource(tp))
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.update(a.name.split(".")[0] for a in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module.split(".")[0])
    assert not importados & (MODULOS_PROIBIDOS | {"PySide6", "shiboken6"})
