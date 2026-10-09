r"""A busca em duas frentes do pré-filtro de PDM (2026-10-08).

Spec: docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md §4.2.

Frente A: a interpretação da IA ("é" + sinônimos), até 8 vagas.
Frente B: a busca de hoje, pela descrição crua, completando até 12. É a rede
contra uma interpretação errada, e por isso não é filtrada por ela.
"""
from __future__ import annotations

from sigft.core.pdm_catalogo import CatalogoPDM, PDM


def _pdm(codigo, base, mod="", caracts=()):
    titulo = f"{base} {mod}".strip()
    return PDM(codigo=codigo, classe=codigo.split(".")[1], titulo=titulo,
               nome_base=base, modificador=mod, caracteristicas=tuple(caracts))


def _codigos(pdms):
    return [p.codigo for p in pdms]


# --- O caso DISPLAY, com o ranqueamento real ---------------------------------
DISPLAY_CERTO = _pdm("PDM.6685.017", "INDICADOR", "DIGITAL",
                     ["CARACTERISTICAS DO DISPLAY", "FAIXA DE MEDICAO"])
CRUA_DISPLAY = "DISPLAY CRISTAL LIQUIDO 20X2 BACKLIGHT VERDE"
INTERPRETADA_DISPLAY = "INDICADOR DIGITAL MOSTRADOR DISPLAY LCD"


def _catalogo_do_display():
    """15 distratores com palavra da descrição no NOME BASE (peso 5,0), em 5
    classes (o teto é 3 por classe), contra o PDM certo, que só casa pela
    característica (peso 1,0)."""
    distratores = []
    for palavra, classe in (("CRISTAL", "5340"), ("LIQUIDO", "6850"),
                            ("VERDE", "6210"), ("BACKLIGHT", "6625"),
                            ("CRISTAL", "4820")):
        for j in range(3):
            distratores.append(_pdm(f"PDM.{classe}.{j:03d}", palavra, f"TIPO{j}"))
    outros = [_pdm(f"PDM.7010.{j:03d}", "SERVIDOR", f"M{j}") for j in range(5)]
    return CatalogoPDM(pdms=[DISPLAY_CERTO] + distratores + outros)


def test_PRECONDICAO_a_busca_de_hoje_deixa_o_display_fora_das_12_vagas():
    """O defeito que motivou a mudança, provado com o ranqueamento real."""
    assert "PDM.6685.017" not in _codigos(_catalogo_do_display().candidatos(CRUA_DISPLAY))


def test_a_interpretacao_poe_o_display_em_primeiro():
    achados = _catalogo_do_display().candidatos_em_duas_frentes(
        INTERPRETADA_DISPLAY, CRUA_DISPLAY)
    assert _codigos(achados)[0] == "PDM.6685.017"


def test_sem_interpretacao_e_identico_a_busca_de_hoje():
    cat = _catalogo_do_display()
    for vazia in ("", "   ", None):
        assert (_codigos(cat.candidatos_em_duas_frentes(vazia, CRUA_DISPLAY))
                == _codigos(cat.candidatos(CRUA_DISPLAY)))


# --- As cotas ------------------------------------------------------------------
def _catalogo_largo():
    """Classes todas distintas, para o teto por classe não interferir."""
    alfas = [_pdm(f"PDM.{1000 + j}.001", "ALFA", f"A{j}") for j in range(20)]
    betas = [_pdm(f"PDM.{3000 + j}.001", "BETA", f"B{j}") for j in range(20)]
    gamas = [_pdm(f"PDM.{5000 + j}.001", "GAMA", f"G{j}") for j in range(2)]
    return CatalogoPDM(pdms=alfas + betas + gamas)


def test_frente_a_fica_com_8_vagas_e_vem_primeiro():
    codigos = _codigos(_catalogo_largo().candidatos_em_duas_frentes("ALFA", "BETA"))
    assert len(codigos) == 12
    assert all(c.startswith("PDM.1") for c in codigos[:8])
    assert all(c.startswith("PDM.3") for c in codigos[8:])


def test_frente_b_completa_quando_a_interpretacao_rende_pouco():
    codigos = _codigos(_catalogo_largo().candidatos_em_duas_frentes("GAMA", "BETA"))
    assert len(codigos) == 12
    assert sum(c.startswith("PDM.5") for c in codigos) == 2
    assert sum(c.startswith("PDM.3") for c in codigos) == 10


def test_frente_a_completa_quando_a_descricao_crua_rende_pouco():
    codigos = _codigos(_catalogo_largo().candidatos_em_duas_frentes("ALFA", "GAMA"))
    assert len(codigos) == 12
    assert sum(c.startswith("PDM.5") for c in codigos) == 2
    assert sum(c.startswith("PDM.1") for c in codigos) == 10


def test_o_mesmo_pdm_nas_duas_frentes_entra_uma_vez_so():
    codigos = _codigos(_catalogo_largo().candidatos_em_duas_frentes("ALFA", "ALFA"))
    assert len(codigos) == len(set(codigos))


# --- O caso PLAQUETA -----------------------------------------------------------
def test_a_aplicacao_nao_passa_na_frente_dos_candidatos_da_interpretacao():
    """As válvulas que a palavra VALVULA puxa só entram depois do que a
    interpretação achou."""
    plaqueta = _pdm("PDM.5930.012", "PLAQUETA", "INDICADORA", ["MATERIAL", "TEXTO GRAVADO"])
    valvulas = [_pdm(f"PDM.{4810 + j}.001", "VALVULA", f"V{j}") for j in range(12)]
    placas = [_pdm(f"PDM.{9500 + j}.001", "PLACA", f"IDENT{j}") for j in range(4)]
    cat = CatalogoPDM(pdms=[plaqueta] + valvulas + placas)

    codigos = _codigos(cat.candidatos_em_duas_frentes(
        "PLAQUETA INDICADORA PLACA IDENTIFICACAO",
        "PLAQUETA EM ALUMINIO PARA VALVULA DUPLOMATIC DUPLOMATIC"))

    assert codigos[0] == "PDM.5930.012"
    primeira_valvula = next(i for i, c in enumerate(codigos) if c.startswith("PDM.48"))
    assert primeira_valvula >= 5  # a plaqueta e as 4 placas vêm antes
