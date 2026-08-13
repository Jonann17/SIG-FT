r"""Glossário em 5 idiomas (2026-08-13).
Ver `sigft/services/autospec_rag.py`, bloco `GLOSSARIO_MULTILINGUE`.

O parque gerador de Itaipu não é abastecido por fornecedores de língua
inglesa. Quem assina os equipamentos: Voith Hydro, Siemens, HYDAC, Bosch
Rexroth, Andritz (ALEMÃO); Alstom/GE Hydro, Schneider (FRANCÊS); a própria
Itaipu é BINACIONAL e documenta também em ESPANHOL; e há fabricantes
italianos de válvulas e hidráulica.

A ficha pergunta em português. Antes disto, um datasheet alemão passava pelo
BM25 sem casar termo nenhum — `pressao` não casa com `Druck` — e o trecho
que continha a resposta era recortado fora do contexto, exatamente como
acontecia com o inglês antes de 2026-08-11.
"""
import pytest

from sigft.services import autospec_rag as rag


# Trechos escritos como um datasheet de verdade escreve, por idioma.
DATASHEETS = {
    "alemao": (
        "TECHNISCHE DATEN\n"
        "Maximaler Betriebsdruck 175 bar. Gewicht 41 kg.\n"
        "Betriebstemperatur 0 bis +70 C. Schutzart IP55.\n"
        "Werkstoff der Dichtung: NBR. Durchmesser der Welle 25.4 mm.\n"
        "Anschluss G1/2. Drehzahl 1450 min-1. Durchfluss 50 l/min.\n"
    ),
    "espanhol": (
        "DATOS TECNICOS\n"
        "Presion maxima de trabajo 175 bar. Peso 41 kg.\n"
        "Temperatura de funcionamiento 0 a +70 C. Proteccion IP55.\n"
        "Material de la junta: NBR. Diametro del eje 25.4 mm.\n"
        "Conexion G1/2. Caudal 50 l/min.\n"
    ),
    "frances": (
        "CARACTERISTIQUES TECHNIQUES\n"
        "Pression maximale de service 175 bar. Poids 41 kg.\n"
        "Temperature de fonctionnement 0 a +70 C. Protection IP55.\n"
        "Materiau du joint: NBR. Diametre de l'arbre 25.4 mm.\n"
        "Raccordement G1/2. Debit 50 l/min.\n"
    ),
    "italiano": (
        "DATI TECNICI\n"
        "Pressione massima di esercizio 175 bar. Peso 41 kg.\n"
        "Temperatura di funzionamento 0 a +70 C. Protezione IP55.\n"
        "Materiale della guarnizione: NBR. Diametro dell'albero 25.4 mm.\n"
        "Attacco G1/2. Portata 50 l/min.\n"
    ),
}

ENCHIMENTO = (
    "Allgemeine Hinweise, informacion general, informations generales, "
    "informazioni generali, warranty terms and ordering codes. " * 25
)

# As perguntas da ficha, em PORTUGUÊS — como sempre chegam.
CONSULTAS = [
    "6 - PRESSAO DE TRABALHO (Indicar a pressao de trabalho do item)",
    "Peso liquido (kg)",
    "4 - FAIXA DE TEMPERATURA DE USO",
    "13 - GRAU DE PROTECAO",
    "12 - MATERIAL DA VEDACAO",
    "18 - DIAMETRO DO EIXO",
]
AGULHAS = ["175 bar", "41 kg", "+70 C", "IP55", "NBR", "25.4 mm"]


def _documento(idioma, paginas=25):
    """O trecho útil diluído em enchimento, como num datasheet real."""
    partes = [f"--- WEB DOC: datasheet_{idioma}.pdf ---"]
    for i in range(paginas):
        partes.append(f"\nSeite {i + 1}\n{ENCHIMENTO}")
    partes.append("\n" + DATASHEETS[idioma])
    return "\n".join(partes)


# =============================================================================
# A. A expansão traz o termo estrangeiro
# =============================================================================
@pytest.mark.parametrize(
    "consulta,esperado,idioma",
    [
        ("PRESSAO", "druck", "alemao"),
        ("PRESSAO", "presion", "espanhol"),
        ("PRESSAO", "pression", "frances"),
        ("PRESSAO", "pressione", "italiano"),
        ("PESO", "gewicht", "alemao"),
        ("VEDACAO", "dichtung", "alemao"),
        ("PROTECAO", "schutzart", "alemao"),
        ("EIXO", "welle", "alemao"),
        ("VAZAO", "caudal", "espanhol"),
        ("TEMPERATURA DE OPERACAO", "funcionamiento", "espanhol"),
        ("CONEXAO", "raccordement", "frances"),
        ("MATERIAL", "materiau", "frances"),
        ("ROLAMENTO", "cuscinetto", "italiano"),
        ("POTENCIA", "potenza", "italiano"),
    ],
)
def test_expansao_traz_o_equivalente(consulta, esperado, idioma):
    assert esperado in rag.expandir_consulta(consulta), idioma


def test_o_termo_em_portugues_e_o_ingles_continuam_valendo():
    """Aditivo: acrescentar idiomas não pode custar o que já funcionava."""
    tokens = rag.expandir_consulta("PRESSAO DE TRABALHO")
    assert "pressao" in tokens
    assert "pressure" in tokens


def test_codigo_de_peca_continua_passando_intacto():
    assert rag.expandir_consulta("PVF100-4") == rag.tokenizar("PVF100-4")


# =============================================================================
# B. O recorte encontra a resposta em cada idioma
# =============================================================================
@pytest.mark.parametrize("idioma", sorted(DATASHEETS))
def test_o_recorte_preserva_os_dados_em_cada_idioma(idioma):
    recortado, _ = rag.montar_contexto_relevante(_documento(idioma), CONSULTAS)
    perdidos = [a for a in AGULHAS if a not in recortado]
    assert perdidos == [], f"datasheet em {idioma}: o recorte perdeu {perdidos}"


@pytest.mark.parametrize("idioma", sorted(DATASHEETS))
def test_o_recorte_economiza_em_cada_idioma(idioma):
    _, est = rag.montar_contexto_relevante(_documento(idioma), CONSULTAS)
    if est.get("recorte_dispensado"):
        return  # documento pequeno vai inteiro, por desenho
    assert est["chars_finais"] < est["chars_originais"]


def test_documento_MISTO_tambem_funciona():
    """Catálogo alemão com resumo em inglês é comum — e o glossário não pode
    escolher um idioma e ignorar o outro."""
    misto = _documento("alemao", paginas=10) + "\n" + (
        "SUMMARY\nMaximum operating pressure 175 bar. Net weight 41 kg.\n"
    )
    recortado, _ = rag.montar_contexto_relevante(misto, CONSULTAS)
    assert "175 bar" in recortado and "41 kg" in recortado


# =============================================================================
# C. Higiene do glossário
# =============================================================================
def test_nenhum_equivalente_tem_acento():
    """`tokenizar` normaliza por NFKD: `Länge` no documento vira `lange`. Um
    equivalente acentuado no glossário nunca casaria com nada."""
    import unicodedata

    for chave, equivalentes in rag.GLOSSARIO_MULTILINGUE.items():
        for termo in equivalentes:
            sem = "".join(
                c for c in unicodedata.normalize("NFKD", termo)
                if not unicodedata.combining(c)
            )
            assert termo == sem, f"{chave} -> {termo!r} tem acento"


def test_nenhum_equivalente_repetido_na_mesma_chave():
    for chave, equivalentes in rag.GLOSSARIO_MULTILINGUE.items():
        assert len(equivalentes) == len(set(equivalentes)), chave


def test_o_nome_antigo_continua_importavel():
    assert rag.GLOSSARIO_PT_EN is rag.GLOSSARIO_MULTILINGUE
