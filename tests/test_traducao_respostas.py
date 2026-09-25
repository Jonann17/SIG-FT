r"""Regras da tradução das RESPOSTAS das fichas (Tradutor 4.2), sem Excel e sem
modelo: o motor é dublado aqui, e o modelo de verdade é exercitado em
`test_tradutor_local.py`.

As frases e os erros vêm do modelo REAL (OPUS-MT tc-big), medidos em
2026-09-25 no GitHub Actions (spec
`docs/superpowers/specs/2026-09-25-tradutor-local-design.md`):

* sem ajuda, ele erra o vocabulário da casa: "PORCA SEXTAVADA" ->
  "CERDA HEXAGONAL", "Mancal de deslizamento" -> "Falta de deslizamiento";
* com o termo já em espanhol na frase, às vezes ele o "retraduz":
  `tuerca` -> `cerda`, `cojinete` -> `rodamiento`;
* com o termo trocado por um MARCADOR, o termo sai sempre certo, mas às vezes
  a frase em volta estraga: "Válvula de compuerta **como** vástago" (era
  "con"), "Filtro de aceite de guía cojinete" (ordem trocada);
* o `Ø`, fora do vocabulário, virava `⁇` (ou o próprio prefixo `>>spa<<`).

Daí a regra: as três versões vão ao modelo NUMA ida, e vence a mais natural
que mantém o termo da casa -- direta, depois com o espanhol, depois com
marcador.
"""
import re

import pytest

from sigft.services import traducao_respostas as tr


# =============================================================================
# Dublês do motor
# =============================================================================
# Um "modelo" de brinquedo: troca palavra por palavra pelo dicionário abaixo e
# copia o resto -- inclusive os marcadores, como o modelo real copia códigos
# do tipo `6205-2RS`. Os ERROS de propósito são os que o modelo real cometeu.
_DICIONARIO = {
    "porca": "cerda",            # o erro real
    "sextavada": "hexagonal",
    "mancal": "falta",           # o erro real
    "de": "de",
    "deslizamento": "deslizamiento",
    "aço": "acero",
    "carbono": "al carbono",
    "inoxidável": "inoxidable",
    "filtro": "filtro",
    "óleo": "aceite",
    "do": "del",
    "guia": "guía",
    "sim": "sí.",                # o modelo real acrescenta o ponto final
    "desenho": "dibujo",
    "tipo": "tipo",
    "vida": "vida",
    "útil": "útil",
    "anos": "años",
    "gaveta": "cajón",           # o erro real ("válvula de cajón")
    "com": "con",
    "haste": "vástago",
    "diâmetro": "diámetro",
    "externo": "externo",
    "arruela": "lavadora",       # o erro real
    "pressão": "presión",
}


class MotorDeBrinquedo:
    """Traduz palavra a palavra e ANOTA o que recebeu.

    `quebrar_marcador`: some com o marcador.
    `retraduz`: o que ele faz com um termo que JÁ veio em espanhol.
    `marcador_estraga`: com marcador na frase, "com" vira "como" -- o erro
    real de gramática em volta do marcador.
    `marcador_troca_ordem`: o marcador troca de lugar com a palavra seguinte
    ("do cojinete guía" saiu "de guía cojinete").
    """

    def __init__(self, quebrar_marcador=False, mudar_numero=False, retraduz=None,
                 marcador_estraga=False, marcador_troca_ordem=False):
        self.lotes = []
        self.quebrar_marcador = quebrar_marcador
        self.mudar_numero = mudar_numero
        self.retraduz = retraduz or {}
        self.marcador_estraga = marcador_estraga
        self.marcador_troca_ordem = marcador_troca_ordem

    def __call__(self, textos):
        self.lotes.append(list(textos))
        return [self._um(t) for t in textos]

    def _um(self, texto):
        tem_marcador = bool(re.search(tr.PADRAO_MARCADOR, texto))
        palavras = []
        for palavra in texto.split(" "):
            nucleo, pontuacao = re.match(r"^(.*?)([.,;:!?]*)$", palavra).groups()
            chave = nucleo.lower()
            if self.quebrar_marcador and re.fullmatch(tr.PADRAO_MARCADOR, nucleo):
                palavras.append("perdido" + pontuacao)
                continue
            if self.mudar_numero and nucleo.isdigit():
                palavras.append(str(int(nucleo) + 1) + pontuacao)
                continue
            if self.marcador_estraga and tem_marcador and chave == "com":
                palavras.append("como" + pontuacao)
                continue
            traduzida = self.retraduz.get(chave) or _DICIONARIO.get(chave, nucleo)
            if nucleo[:1].isupper():
                traduzida = traduzida[:1].upper() + traduzida[1:]
            palavras.append(traduzida + pontuacao)
        if self.marcador_troca_ordem:
            for i in range(len(palavras) - 1):
                if re.fullmatch(tr.PADRAO_MARCADOR, palavras[i]):
                    palavras[i], palavras[i + 1] = palavras[i + 1], palavras[i]
                    break
        return " ".join(palavras)


def _textos(resultado):
    return [t.texto for t in resultado]


# =============================================================================
# A. O que NÃO vai ao modelo
# =============================================================================
@pytest.mark.parametrize("texto", [
    "220 V", "1750 rpm", "4-20 mA", "0,5", "25 kg", "IP65", "6205-2RS",
    "NBR 5410", "AISI 316L", "N/A", "NA", "-", "--", ".", "M12 x 50",
    "Ø 36 mm", "60 Hz", "IP 65",
])
def test_numero_unidade_codigo_e_na_passam_direto(texto):
    assert tr.nao_precisa_traduzir(texto)


@pytest.mark.parametrize("texto", [
    "Aço carbono", "LATÃO", "Contator", "Sim", "Conforme desenho",
    "Aprox. 25 kg", "Bobina 125 Vcc",
])
def test_texto_de_verdade_vai_ao_modelo(texto):
    assert not tr.nao_precisa_traduzir(texto)


def test_o_que_passa_direto_nao_chega_ao_motor():
    motor = MotorDeBrinquedo()
    saida = tr.traduzir_respostas(["220 V", "IP65", "N/A"], motor)
    assert _textos(saida) == ["220 V", "IP65", "N/A"]
    assert motor.lotes == []
    assert {t.origem for t in saida} == {"igual"}


def test_vazio_e_none_voltam_vazios_sem_ir_ao_motor():
    motor = MotorDeBrinquedo()
    saida = tr.traduzir_respostas(["", None, "   "], motor)
    assert _textos(saida) == ["", "", ""]
    assert motor.lotes == []


# =============================================================================
# B. Caixa alta
# =============================================================================
def test_caixa_alta_vai_em_caixa_de_frase_e_volta_em_maiusculas():
    motor = MotorDeBrinquedo()
    saida = tr.traduzir_respostas(["AÇO CARBONO"], motor)
    assert motor.lotes == [["Aço carbono"]]
    assert _textos(saida) == ["ACERO AL CARBONO"]


def test_caixa_de_frase_preserva_sigla_e_codigo():
    assert tr.caixa_de_frase("AÇO INOXIDÁVEL AISI 316L") == ("Aço inoxidável AISI 316L", True)
    assert tr.caixa_de_frase("BORRACHA NITRÍLICA (NBR)") == ("Borracha nitrílica (NBR)", True)


def test_texto_misto_nao_muda_de_caixa():
    assert tr.caixa_de_frase("Aço carbono ASTM A36") == ("Aço carbono ASTM A36", False)
    assert tr.caixa_de_frase("SKF") == ("SKF", False)


# =============================================================================
# C. Glossário: frase inteira
# =============================================================================
def test_frase_inteira_do_glossario_nem_vai_ao_modelo():
    motor = MotorDeBrinquedo()
    glossario = {"conforme desenho": "según plano"}
    saida = tr.traduzir_respostas(["Conforme desenho", "CONFORME DESENHO"], motor, glossario)
    assert _textos(saida) == ["Según plano", "SEGÚN PLANO"]
    assert motor.lotes == []
    assert {t.origem for t in saida} == {"glossario"}


def test_frase_inteira_ignora_acento_ponto_final_e_espacos():
    """O ponto final segue o original, como na tradução pelo modelo."""
    glossario = {"não aplicável": "no aplicable"}
    saida = tr.traduzir_respostas(["Nao  aplicavel.", "Não aplicável"], MotorDeBrinquedo(), glossario)
    assert _textos(saida) == ["No aplicable.", "No aplicable"]


# =============================================================================
# D. Glossário: termo dentro da frase (as três versões)
# =============================================================================
def test_sem_termo_do_glossario_vai_uma_versao_so():
    motor = MotorDeBrinquedo()
    tr.traduzir_respostas(["Aço carbono", "Sim"], motor, {"porca": "tuerca"})
    assert motor.lotes == [["Aço carbono", "Sim"]]


def test_com_termo_as_tres_versoes_vao_numa_ida_so():
    motor = MotorDeBrinquedo()
    tr.traduzir_respostas(["Porca sextavada"], motor, {"porca": "tuerca"})
    [lote] = motor.lotes
    direta, com_espanhol, com_marcador = lote
    assert direta == "Porca sextavada"
    assert com_espanhol == "Tuerca sextavada"
    assert "porca" not in com_marcador.lower() and re.search(tr.PADRAO_MARCADOR, com_marcador)


def test_so_o_marcador_garante_o_termo_e_ele_vence():
    """O caso real: direta dá "cerda", e o modelo retraduz "tuerca" em "cerda"."""
    motor = MotorDeBrinquedo(retraduz={"tuerca": "cerda"})
    saida = tr.traduzir_respostas(["PORCA SEXTAVADA"], motor, {"porca": "tuerca"})
    assert _textos(saida) == ["TUERCA HEXAGONAL"]
    assert saida[0].origem == "tradutor"


def test_vence_a_versao_mais_natural_que_mantem_o_termo():
    """O caso real da válvula: com marcador, "com" virou "como"; com o termo
    já em espanhol a frase sai certa -- e é ela que vence."""
    motor = MotorDeBrinquedo(marcador_estraga=True)
    glossario = {"válvula gaveta": "válvula de compuerta"}
    saida = tr.traduzir_respostas(["Válvula gaveta com haste"], motor, glossario)
    assert _textos(saida) == ["Válvula de compuerta con vástago"]


def test_a_direta_vence_quando_ja_acerta_o_termo():
    """O caso real do filtro: sem ajuda o modelo já dizia "cojinete guía", e
    o marcador bagunçava a ordem."""
    motor = MotorDeBrinquedo(retraduz={"mancal": "cojinete"}, marcador_troca_ordem=True)
    saida = tr.traduzir_respostas(["Filtro de óleo do mancal guia"], motor, {"mancal": "cojinete"})
    assert _textos(saida) == ["Filtro de aceite del cojinete guía"]


def test_termo_mais_longo_vence_o_mais_curto():
    glossario = {"mancal": "cojinete", "mancal de deslizamento": "cojinete de deslizamiento"}
    motor = MotorDeBrinquedo()
    saida = tr.traduzir_respostas(["Mancal de deslizamento", "Filtro do mancal de deslizamento"],
                                  motor, glossario)
    assert _textos(saida) == ["Cojinete de deslizamiento", "Filtro del cojinete de deslizamiento"]
    # A 1ª é frase inteira (nem vai ao motor). Na 2ª, UM marcador cobre o
    # termo longo inteiro -- o curto não fatia o longo.
    [lote] = motor.lotes
    com_marcador = lote[-1]
    assert "mancal" not in com_marcador.lower()
    assert len(re.findall(tr.PADRAO_MARCADOR, com_marcador)) == 1


def test_termo_nao_casa_dentro_de_outra_palavra():
    glossario = {"porca": "tuerca"}
    motor = MotorDeBrinquedo()
    tr.traduzir_respostas(["Porcas e porcarias"], motor, glossario)
    assert motor.lotes == [["Porcas e porcarias"]]


def test_termo_casa_sem_acento():
    """Fornecedor que já digitou sem acento (o portal não aceita acento)."""
    motor = MotorDeBrinquedo()
    saida = tr.traduzir_respostas(["Icamento com cinta"], motor, {"içamento": "izaje"})
    assert _textos(saida)[0].startswith("Izaje")


def test_marcador_perdido_fica_com_a_versao_em_espanhol():
    motor = MotorDeBrinquedo(quebrar_marcador=True)
    saida = tr.traduzir_respostas(["Porca sextavada"], motor, {"porca": "tuerca"})
    assert saida[0].texto == "Tuerca hexagonal"
    assert saida[0].origem == "tradutor" and saida[0].aviso == ""


def test_nenhuma_versao_mantem_o_termo_vira_conferir():
    """Sem marcador e com o modelo trocando o espanhol: não dá para garantir
    o termo da casa, e o log tem de dizer qual."""
    motor = MotorDeBrinquedo(quebrar_marcador=True, retraduz={"tuerca": "cerda"})
    saida = tr.traduzir_respostas(["Porca sextavada"], motor, {"porca": "tuerca"})
    assert saida[0].texto == "Cerda hexagonal"
    assert saida[0].origem == "conferir"
    assert "porca = tuerca" in saida[0].aviso


def test_resposta_que_ja_tem_algo_parecido_com_marcador_nao_usa_marcador():
    """Um código `XQ1` de verdade na resposta seria trocado pelo termo na volta."""
    motor = MotorDeBrinquedo()
    saida = tr.traduzir_respostas(["Porca modelo XQ1"], motor, {"porca": "tuerca"})
    assert all(not re.search(r"XQ[2-9]", t) for t in motor.lotes[0])
    assert _textos(saida) == ["Tuerca modelo XQ1"]


# =============================================================================
# E. Símbolo fora do vocabulário
# =============================================================================
def test_simbolo_que_o_modelo_nao_conhece_vai_protegido():
    motor = MotorDeBrinquedo()
    saida = tr.traduzir_respostas(["Diâmetro externo Ø 150 mm"], motor)
    assert "Ø" not in motor.lotes[0][0]
    assert _textos(saida) == ["Diámetro externo Ø 150 mm"]


def test_token_inteiro_com_simbolo_vai_protegido():
    motor = MotorDeBrinquedo()
    saida = tr.traduzir_respostas(["Diâmetro Ø150mm"], motor)
    assert _textos(saida) == ["Diámetro Ø150mm"]


@pytest.mark.parametrize("vazou", ["Diámetro ⁇ 150", "Diámetro >>spa<< 150"])
def test_saida_com_desconhecido_ou_prefixo_vazado_vira_conferir(vazou):
    saida = tr.traduzir_respostas(["Diâmetro 150"], lambda textos: [vazou] * len(textos))
    assert saida[0].texto == "Diâmetro 150"
    assert saida[0].origem == "conferir"


# =============================================================================
# F. Conferências
# =============================================================================
def test_numero_que_muda_na_traducao_devolve_o_original_e_avisa():
    motor = MotorDeBrinquedo(mudar_numero=True)
    saida = tr.traduzir_respostas(["Vida útil 10 anos"], motor)
    assert saida[0].texto == "Vida útil 10 anos"
    assert saida[0].origem == "conferir"
    assert "10" in saida[0].aviso


def test_ponto_final_que_o_original_nao_tinha_sai():
    saida = tr.traduzir_respostas(["Sim"], MotorDeBrinquedo())
    assert _textos(saida) == ["Sí"]


def test_ponto_final_do_original_fica():
    saida = tr.traduzir_respostas(["Tipo aço."], MotorDeBrinquedo())
    assert _textos(saida) == ["Tipo acero."]


def test_resposta_vazia_do_modelo_vira_conferir():
    saida = tr.traduzir_respostas(["Aço carbono"], lambda textos: [""] * len(textos))
    assert saida[0].texto == "Aço carbono"
    assert saida[0].origem == "conferir"


# =============================================================================
# G. Lote
# =============================================================================
def test_repetidas_vao_ao_motor_uma_vez_e_voltam_na_ordem():
    motor = MotorDeBrinquedo()
    entrada = ["Aço carbono", "220 V", "Aço carbono", "Aço inoxidável"]
    saida = tr.traduzir_respostas(entrada, motor)
    assert motor.lotes == [["Aço carbono", "Aço inoxidável"]]
    assert _textos(saida) == ["Acero al carbono", "220 V", "Acero al carbono", "Acero inoxidable"]
    assert [t.original for t in saida] == entrada


def test_uma_ida_ao_motor_para_o_lote_inteiro():
    motor = MotorDeBrinquedo(quebrar_marcador=True)
    tr.traduzir_respostas(["Aço carbono", "Porca", "Sim", "Mancal guia"], motor,
                          {"porca": "tuerca", "mancal": "cojinete"})
    assert len(motor.lotes) == 1


def test_motor_que_devolve_quantidade_errada_levanta():
    with pytest.raises(tr.TraducaoFalhou):
        tr.traduzir_respostas(["Aço carbono", "Sim"], lambda textos: ["x"])


def test_resumo_conta_por_origem():
    saida = tr.traduzir_respostas(
        ["Aço carbono", "220 V", "Conforme desenho", ""], MotorDeBrinquedo(),
        {"conforme desenho": "según plano"})
    assert tr.resumo(saida) == {"tradutor": 1, "igual": 1, "glossario": 1, "vazio": 1}


# =============================================================================
# H. Arquivo do glossário
# =============================================================================
def test_glossario_le_linhas_ignora_comentario_e_aceita_cp1252(tmp_path):
    caminho = tmp_path / "g.txt"
    caminho.write_bytes("# comentario\n\nMancal = cojinete\ncoisa sem igual\ncapa=funda\n".encode("cp1252"))
    assert tr.carregar_glossario(caminho) == {"mancal": "cojinete", "capa": "funda"}


def test_glossario_ausente_e_vazio(tmp_path):
    assert tr.carregar_glossario(tmp_path / "nao_existe.txt") == {}


def test_glossario_do_usuario_vence_o_da_casa(tmp_path):
    caminho = tmp_path / "g.txt"
    caminho.write_text("mancal = rodamiento\n", encoding="utf-8")
    glossario = tr.glossario_em_uso(caminho)
    assert glossario["mancal"] == "rodamiento"
    assert glossario["porca"] == tr.GLOSSARIO_DA_CASA["porca"]


def test_arquivo_do_usuario_e_criado_com_instrucoes_e_nunca_sobrescrito(tmp_path):
    caminho = tmp_path / "sub" / "GLOSSARIO_PT_ES.txt"
    tr.criar_glossario_do_usuario(caminho)
    texto = caminho.read_text(encoding="utf-8")
    assert "portugues = espanhol" in texto
    assert tr.carregar_glossario(caminho) == {}      # so instrucoes, nenhum termo ativo
    caminho.write_text("porca = tuerca\n", encoding="utf-8")
    tr.criar_glossario_do_usuario(caminho)
    assert caminho.read_text(encoding="utf-8") == "porca = tuerca\n"


def test_glossario_da_casa_cobre_os_erros_medidos():
    """Os termos que o modelo errou no experimento de 2026-09-25."""
    casa = tr.GLOSSARIO_DA_CASA
    for pt in ("mancal", "porca", "arruela", "chave fim de curso", "conforme desenho",
               "revenido", "gaxeta", "escova de carvão", "ao tempo", "içamento"):
        assert pt in casa, pt
    assert all(pt == pt.lower() and pt.strip() == pt for pt in casa)
