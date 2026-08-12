r"""
Testes do retrieval do AutoSpecAI (2026-08-11).
Ver `sigft/services/autospec_rag.py` e docs/AUTOSPEC_MELHORIAS.md.

O módulo troca *context stuffing* (mandar o documento inteiro) por RAG de
verdade (mandar só os trechos que respondem os campos pedidos). Os dois riscos
que estes testes guardam:

  1. **Perder dado no recorte.** É o que o usuário temia, e a primeira versão
     do módulo perdia mesmo — ver a seção C.
  2. **Perder proveniência.** A instrução 1 do prompt manda `Priorize
     "LOCAL DOC"`, e ela só funciona se o marcador sobreviver ao recorte.
"""
import pytest

from sigft.services import autospec_rag as rag


# Datasheet realista: seções úteis diluídas em conteúdo irrelevante, escrito em
# INGLÊS — como são os datasheets de fabricante de verdade.
SECOES = {
    "DIMENSIONS": "Overall length 340 mm. Width 210 mm. Height 265 mm.",
    "WEIGHT": "Net weight 41 kg. Gross weight with packaging 46 kg.",
    "PRESSURE": "Maximum operating pressure 175 bar. Peak pressure 210 bar.",
    "TEMPERATURE": "Operating temperature range 0 to +70 C.",
    "SEALS": "Standard seal material NBR (Nitrile).",
    "SHAFT": "Shaft diameter 25.4 mm. Key width 9.53 mm.",
    "PROTECTION": "Enclosure rating IP55.",
}
ENCHIMENTO = (
    "General company information, warranty terms, ordering codes, installation "
    "guidelines and safety warnings. " * 22
)


def _datasheet(origem="manual_hydac.pdf", tipo="LOCAL", paginas=40):
    partes = [f"--- {tipo} DOC: {origem} ---"]
    for i in range(paginas):
        partes.append(f"\nPage {i+1}\n{ENCHIMENTO}")
        if i < len(SECOES):
            titulo, corpo = list(SECOES.items())[i]
            partes.append(f"\n{titulo}\n{corpo}\n")
    return "\n".join(partes)


# As perguntas da ficha real 4500063671.0662, em PORTUGUÊS.
CONSULTAS = [
    "16 - DIMENSOES (Indicar as dimensoes do item (in, mm))",
    "Peso liquido (kg)",
    "6 - PRESSAO DE TRABALHO (Indicar a pressao de trabalho do item)",
    "4 - FAIXA DE TEMPERATURA DE USO",
    "2 - MATERIAL (Indicar o material do item)",
    "18 - DIAMETRO EXTERNO",
    "Protecao",
]

AGULHAS = ["340 mm", "41 kg", "175 bar", "+70 C", "NBR", "25.4 mm", "IP55"]


# =============================================================================
# A. Tokenização — código de peça não pode ser despedaçado
# =============================================================================
def test_codigo_de_peca_nao_e_quebrado_em_pedacos():
    """Quebrar no hífen transformaria `PVF100-4` em `pvf100` e `4`, e o `4`
    casaria com qualquer coisa. O token tem de sobreviver inteiro."""
    assert "pvf100-4" in rag.tokenizar("Modelo PVF100-4")
    assert "25.4" in rag.tokenizar("Shaft diameter 25.4 mm")
    assert "ip55" in rag.tokenizar("Enclosure rating IP55")


def test_acento_e_caixa_sao_normalizados():
    assert rag.tokenizar("PRESSÃO Máxima") == rag.tokenizar("pressao maxima")


# =============================================================================
# B. Glossário PT->EN — a ficha pergunta em português, o datasheet responde inglês
# =============================================================================
def test_expansao_traz_o_equivalente_em_ingles():
    tokens = rag.expandir_consulta("PRESSAO DE TRABALHO")
    assert "pressao" in tokens, "o termo original nao pode ser substituido"
    assert "pressure" in tokens


def test_expansao_e_ADITIVA_nao_substitui():
    """Código de peça e unidade continuam casando direto — é onde o lexical é
    imbatível e o glossário não pode atrapalhar."""
    tokens = rag.expandir_consulta("Modelo PVF100-4 pressao 175 bar")
    assert "pvf100-4" in tokens and "bar" in tokens and "175" in tokens


def test_consulta_sem_termo_do_glossario_passa_intacta():
    assert rag.expandir_consulta("PVF100-4") == rag.tokenizar("PVF100-4")


# =============================================================================
# C. O recorte NÃO pode perder dado — o risco levantado pelo usuário
# =============================================================================
def test_todos_os_dados_procurados_sobrevivem_ao_recorte():
    """Regressão da falha real: a 1ª versão, com BM25 puro, perdia `175 bar` e
    `+70 C` porque `pressao` não casa com `pressure`."""
    recortado, _ = rag.montar_contexto_relevante(_datasheet(), CONSULTAS)
    perdidos = [a for a in AGULHAS if a not in recortado]
    assert perdidos == [], f"o recorte perdeu: {perdidos}"


@pytest.mark.parametrize(
    "consulta,agulha",
    [
        ("6 - PRESSAO DE TRABALHO", "175 bar"),
        ("4 - FAIXA DE TEMPERATURA DE USO", "+70 C"),
        ("Peso liquido", "41 kg"),
        ("Protecao", "IP55"),
    ],
)
def test_cada_campo_isolado_encontra_sua_resposta(consulta, agulha):
    """Uma consulta por vez: se falhar aqui, o glossário perdeu um par."""
    recortado, _ = rag.montar_contexto_relevante(_datasheet(), [consulta])
    assert agulha in recortado


def test_recorte_economiza_de_verdade_em_documento_grande():
    _, est = rag.montar_contexto_relevante(_datasheet(), CONSULTAS)
    reducao = 1 - est["chars_finais"] / est["chars_originais"]
    assert reducao > 0.7, f"economia de apenas {reducao:.0%}"


# =============================================================================
# D. Proveniência — a instrução 1 do prompt depende dela
# =============================================================================
def test_marcador_LOCAL_sobrevive_ao_recorte():
    """`Priorize "LOCAL DOC"` vira letra morta se o marcador sumir."""
    recortado, _ = rag.montar_contexto_relevante(_datasheet(tipo="LOCAL"), CONSULTAS)
    assert "--- LOCAL DOC: manual_hydac.pdf ---" in recortado


def test_marcador_WEB_sobrevive_e_nao_vira_LOCAL():
    recortado, _ = rag.montar_contexto_relevante(
        _datasheet(origem="https://x.com/ds.pdf", tipo="WEB"), CONSULTAS
    )
    assert "--- WEB DOC: https://x.com/ds.pdf ---" in recortado
    assert "LOCAL DOC" not in recortado


def test_trecho_LOCAL_vem_antes_do_WEB():
    """A instrução manda priorizar o manual do usuário sobre o que veio da
    internet; a ordem do contexto tem de refletir isso."""
    misto = _datasheet(origem="manual.pdf", tipo="LOCAL", paginas=10) + "\n" + _datasheet(
        origem="https://x.com/ds.pdf", tipo="WEB", paginas=10
    )
    recortado, _ = rag.montar_contexto_relevante(misto, CONSULTAS)
    assert recortado.index("LOCAL DOC") < recortado.index("WEB DOC")


def test_origens_ficam_registradas_nas_estatisticas():
    _, est = rag.montar_contexto_relevante(_datasheet(), CONSULTAS)
    assert "manual_hydac.pdf" in est["origens"]


# =============================================================================
# E. Casos de borda — recorte não pode piorar a situação
# =============================================================================
def test_documento_pequeno_e_enviado_INTEIRO():
    """Medido: um contexto de 11.302 chars virava 12.171 depois do recorte,
    porque quase todo trecho era selecionado e cada um repetia o marcador.
    Nesse caso o original é melhor — mesmo conteúdo, ordem intacta."""
    pequeno = "--- LOCAL DOC: nota.pdf ---\nPressao maxima 10 bar. Peso 2 kg."
    recortado, est = rag.montar_contexto_relevante(pequeno, CONSULTAS)
    assert est.get("recorte_dispensado") is True
    assert recortado == pequeno
    assert "recortar nao economizaria" in rag.resumo_estatisticas(est)


def test_contexto_vazio_nao_quebra():
    for vazio in ["", None, "   "]:
        texto, est = rag.montar_contexto_relevante(vazio, CONSULTAS)
        assert texto == "" and est["trechos_total"] == 0


def test_sem_consulta_nao_devolve_o_documento_inteiro():
    """Sem campo faltante não há o que perguntar. Devolver tudo aqui seria
    voltar ao context stuffing que o módulo existe para eliminar."""
    texto, _ = rag.montar_contexto_relevante(_datasheet(), [])
    assert texto == ""


def test_texto_sem_marcador_nao_e_descartado():
    """Perder conteúdo em silêncio é o oposto do objetivo do módulo."""
    trechos = rag.dividir_em_trechos("Conteudo solto, sem marcador de origem nenhum.")
    assert trechos and trechos[0].origem == "(desconhecida)"


def test_teto_de_contexto_e_respeitado():
    _, est = rag.montar_contexto_relevante(
        _datasheet(paginas=200), CONSULTAS, teto_chars=5000
    )
    assert est["chars_finais"] <= 5000


# =============================================================================
# F. Chunking — tabela não pode ser partida ao meio
# =============================================================================
def test_trechos_tem_sobreposicao():
    """Valor que caia na fronteira aparece inteiro em pelo menos um trecho."""
    texto = "--- LOCAL DOC: x.pdf ---\n" + ("linha de tabela com valores 123 456\n" * 200)
    trechos = rag.dividir_em_trechos(texto)
    assert len(trechos) > 1
    assert rag.SOBREPOSICAO_TRECHO > 0


def test_ordem_de_leitura_e_preservada_no_contexto_final():
    """Remontar fora de ordem confunde o modelo mais do que ajuda."""
    recortado, _ = rag.montar_contexto_relevante(_datasheet(), CONSULTAS)
    # DIMENSIONS está na página 1 e PROTECTION na 7 — a ordem tem de refletir
    if "340 mm" in recortado and "IP55" in recortado:
        assert recortado.index("340 mm") < recortado.index("IP55")


# =============================================================================
# G. O gancho do reforço semântico opcional
# =============================================================================
def test_reordenador_opcional_e_chamado_quando_existe():
    chamadas = []

    def _reordenador(consulta, trechos):
        chamadas.append(consulta)
        return trechos

    rag.montar_contexto_relevante(_datasheet(), CONSULTAS[:2], reordenador=_reordenador)
    assert len(chamadas) == 2


def test_falha_no_reordenador_NAO_derruba_o_retrieval():
    """O reforço semântico é opcional: quebrar nele não pode custar o recorte,
    que é o caminho principal."""
    def _explode(consulta, trechos):
        raise RuntimeError("modelo de embedding indisponivel")

    recortado, _ = rag.montar_contexto_relevante(
        _datasheet(), CONSULTAS, reordenador=_explode
    )
    assert all(a in recortado for a in AGULHAS)
