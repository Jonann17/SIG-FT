r"""A conferencia passa a ser pela PROVA que a IA devolve (2026-09-24).

O caso que abriu esta frente, ficha 0088 (fusivel Protistor 36x250 gR 2000 V
DC). A IA respondeu CERTO, e o lastro reprovou:

    4 - DIAMETRO EXTERNO VIROLA -> a IA respondeu '36 mm'
      motivo: o documento tem medidas em mm e nenhuma bate com 36
    7 - COMPRIMENTO TOTAL -> a IA respondeu '250 mm'
      motivo: o documento tem medidas em mm e nenhuma bate com 250

O datasheet cota o desenho sem escrever a unidade -- `ø 36`, `250`, e o
tamanho `36x250` --, e o unico "mm" do PDF inteiro e o `20 mm` da forca de
disparo. O lastro procurava "36 mm" no documento todo, e no desenho nao ha.

O desenho novo pede a PROVA junto com o valor -- documento, pagina e o
trecho copiado -- e confere a prova:

- o trecho existe no documento (sem ligar para quebra de linha, espaco,
  virgula decimal), e na linha do modelo CERTO;
- todo numero do valor sai do trecho: literal, com ou sem unidade ao lado,
  ou por conversao refeita pelo app;
- DEDUCAO so para texto (material, norma, uso, tipo). Numero so com
  documento -- o numero de uma norma (`IEC 60269-4`) nao conta como medida.

Resposta SEM prova (modelo que ignora o formato novo) cai na regra antiga,
inteira: nada fica mais frouxo para quem nao prova.
"""
import sys
import types

import pytest

from sigft.core.llm import prompts
from sigft.services import autospec, autospec_documentos as docs
from sigft.services import autospec_evidencia as ev
from sigft.services.autospec import AutoSpecCore

# Trecho do texto REAL do datasheet da ficha 0088, como o PyMuPDF o extrai.
DOC_0088 = (
    "--- LOCAL DOC: 4500063671.0088.pdf ---\n"
    "[página 1]\n"
    "Protistor DC fuses\nSCDC16\nDC Ferrule Fuses\n36x250\ngR 2000V DC\n12/04\n"
    "gRB from 0.8 to 40 A\n255\n43\n20\nø 36\nø12\n250\nCC 209P ...\n"
    "Weight 667 g\nWeight 610 g\nCC 2000 ...\n"
    "Main Characteristics\nDimensions\nPack: 1 piece\n36x250\n@ 2000 V DC\n30 kA\n"
    "L/R = 20 ms\nTrip force: 15 N at 20 mm\n"
    "Minimum trip indicator operating voltage: 90 V\n"
)

PERGUNTA_VIROLA = ("4 - DIAMETRO EXTERNO VIROLA (Indicar o diâmetro externos das virolas "
                   "do item (mm) ex. Diâmetro 36 mm)")
PERGUNTA_COMPRIMENTO = "7 - COMPRIMENTO TOTAL (Indicar o comprimento total do item (mm))"
PERGUNTA_TIPO = ("12 - TIPO CONSTRUTIVO (Indicar o tipo construtivo do item RD, RDE, UD, "
                 "R, DRVAL, OUTROS)")


def _prova(tipo="documento", trecho="", fonte="4500063671.0088.pdf", pagina=1, justificativa=""):
    return ev.Evidencia(tipo=tipo, fonte=fonte, pagina=pagina, trecho=trecho,
                        justificativa=justificativa)


def _core(evidencias, modelo=""):
    core = AutoSpecCore.__new__(AutoSpecCore)
    core.ultimas_evidencias_por_campo = evidencias
    core._modelo_do_item = modelo
    return core


def _logs():
    linhas = []

    class _Cb:
        def log(self, msg, nivel="info", contexto=None):
            linhas.append((nivel, str(msg)))

    return _Cb(), linhas


# =============================================================================
# 1. Achar o trecho citado
# =============================================================================
def test_o_trecho_e_achado_apesar_da_quebra_de_linha_e_do_espaco():
    texto = "Max. Temperature/Pressure Rating\nStorage Temperature\n-20 °C to 85 ° C\n"
    achado = ev.achar_trecho("Storage Temperature: -20 °C to 85 °C", texto)
    assert achado is not None and "-20" in achado


def test_virgula_decimal_nao_impede_de_achar():
    """A IA copia `0,5` quando o documento diz `0.5`: o trecho e o mesmo."""
    assert ev.achar_trecho("±0,5% of full scale", "Accuracy ±0.5% of full scale @ 25 °C")


def test_trecho_que_nao_existe_nao_e_achado():
    assert ev.achar_trecho("Operating pressure 0 to 5 bar",
                           "Operating pressure\n-XL\n0 to 3.4 bar\n") is None


def test_tabela_com_colunas_intercaladas_ainda_e_achada():
    """No texto extraido, o rotulo, a variante e o valor da tabela vem em
    linhas separadas, com as outras variantes no meio."""
    texto = ("Operating pressure\n-XU\n0 to 0.7 bar\n0 to 10 psi\n-XL\n0 to 3.4 bar\n"
             "0 to 50 psi\n-XH\n0 to 17 bar\n")
    achado = ev.achar_trecho("Operating pressure -XL 0 to 3.4 bar", texto)
    assert achado is not None and "3.4" in achado


# =============================================================================
# 2. O numero do valor sai do trecho
# =============================================================================
@pytest.mark.parametrize("valor,trecho", [
    ("36 mm", "ø 36"),                      # cota de desenho, sem unidade
    ("250 mm", "36x250"),                   # designacao do tamanho
    ("2860 rpm", "Nenndrehzahl 2860 1/min"),
    ("-20 a 85 °C", "Storage Temperature -20 °C to 85 ° C"),
    ("12 a 24 Vcc", "12 to 24 VDC ±10%, regulated"),
    ("IP65", "NEMA 4X/IP65 rated when using the 3-8052-1"),
    ("±0,5% do fundo de escala", "±0.5% of full scale @ 25 °C"),
    ("PVDF", "Sensor housing PVDF"),
])
def test_valor_que_sai_do_trecho(valor, trecho):
    ok, _explicacoes = ev.valor_sai_do_trecho(valor, trecho)
    assert ok, (valor, trecho)


def test_conversao_certa_sai_do_trecho_e_diz_de_onde():
    ok, explicacoes = ev.valor_sai_do_trecho("35 MPa", "Maximum operating pressure: 350 bar")
    assert ok and any("350 bar" in e for e in explicacoes)


@pytest.mark.parametrize("valor,trecho", [
    ("3,5 MPa", "Maximum operating pressure: 350 bar"),  # conta errada
    ("41 g", "Shipping weight 41 kg"),                   # mesma grandeza, outra unidade
    ("IP67", "NEMA 4X/IP65 rated"),                      # o codigo tem de estar la
    ("900 x 800 x 700 mm", "Dimensions: 5.98 x 3.58 x 5.31 in."),
])
def test_valor_que_NAO_sai_do_trecho(valor, trecho):
    ok, _explicacoes = ev.valor_sai_do_trecho(valor, trecho)
    assert not ok, (valor, trecho)


# =============================================================================
# 3. Deducao: texto sim, numero nao
# =============================================================================
@pytest.mark.parametrize("valor", [
    "Cobre prateado", "Interno", "OUTROS", "Não aplicável",
    "IEC 60269-1; IEC 60269-4", "ABNT NBR IEC 60529", "Ventilação industrial",
])
def test_deducao_de_texto_e_permitida(valor):
    assert ev.deducao_permitida(valor)


@pytest.mark.parametrize("valor", [
    "IP65", "NEMA 4X", "1,3 x In", "0 a 95 %", "DN50", "4,30 kg", "250 mm",
])
def test_deducao_com_numero_nao_e_permitida(valor):
    """Foi um numero deduzido que o AMP alucinou (pressao maxima de
    trabalho, ficha 0084). Grau de protecao e dimensao sao do MODELO."""
    assert not ev.deducao_permitida(valor)


# =============================================================================
# 4. A prova sai da resposta da IA
# =============================================================================
def test_a_prova_e_lida_da_resposta():
    bruto = {"var_row_80": {"valor": "36 mm", "tipo": "Documento", "fonte": "a.pdf",
                            "pagina": "p. 1", "trecho": "ø 36", "justificativa": ""}}
    prova = ev.extrair_evidencias(bruto, ["var_row_80"])["var_row_80"]
    assert (prova.tipo, prova.fonte, prova.pagina, prova.trecho) == ("documento", "a.pdf", 1, "ø 36")


@pytest.mark.parametrize("escrito,esperado", [
    ("Dedução", "deducao"), ("cálculo", "calculo"), ("documento", "documento"),
    ("", "documento"), (None, "documento"), ("qualquer", "documento"),
])
def test_tipo_da_prova_e_normalizado(escrito, esperado):
    bruto = {"c": {"valor": "x", "tipo": escrito}}
    assert ev.extrair_evidencias(bruto, ["c"])["c"].tipo == esperado


def test_resposta_no_formato_antigo_nao_tem_prova():
    assert ev.extrair_evidencias({"c": "valor cru"}, ["c"]) == {}


def test_a_normalizacao_da_resposta_guarda_as_provas():
    core = AutoSpecCore.__new__(AutoSpecCore)
    core._normalizar_resposta_ia(
        {"var_row_80": {"valor": "36 mm", "fonte": "a.pdf", "trecho": "ø 36"}},
        campos_pedidos=["var_row_80"])
    assert core.ultimas_evidencias_por_campo["var_row_80"].trecho == "ø 36"


# =============================================================================
# 5. A conferencia inteira, no caso do usuario
# =============================================================================
def test_o_caso_do_usuario_36_e_250_mm_passam_com_a_prova():
    """O teste que fecha o pedido."""
    core = _core({
        "var_row_80": _prova(trecho="ø 36"),
        "var_row_83": _prova(trecho="DC Ferrule Fuses 36x250"),
    })
    aprovados = core._filtrar_por_lastro(
        {"var_row_80": "36 mm", "var_row_83": "250 mm"},
        {"var_row_80": {"desc": PERGUNTA_VIROLA}, "var_row_83": {"desc": PERGUNTA_COMPRIMENTO}},
        DOC_0088)
    assert aprovados == {"var_row_80": "36 mm", "var_row_83": "250 mm"}


def test_sem_prova_a_regra_antiga_continua_valendo_inteira():
    """Modelo que ignora o formato novo nao ganha folga nenhuma."""
    aprovados = _core({})._filtrar_por_lastro(
        {"var_row_80": "36 mm"}, {"var_row_80": {"desc": PERGUNTA_VIROLA}}, DOC_0088)
    assert "var_row_80" not in aprovados


def test_deducao_de_texto_entra_marcada_e_com_a_justificativa():
    core = _core({"var_row_91": _prova(
        tipo="deducao", trecho="", fonte="conhecimento tecnico",
        justificativa="Fusivel cilindrico (ferrule) 36x250: nao e RD/RDE/UD/R/DRVAL.")})
    cb, linhas = _logs()
    aprovados = core._filtrar_por_lastro(
        {"var_row_91": "OUTROS"}, {"var_row_91": {"desc": PERGUNTA_TIPO}}, DOC_0088, cb)
    assert aprovados == {"var_row_91": "OUTROS"}
    texto = "\n".join(m for _n, m in linhas)
    assert "DEDU" in texto.upper() and "ferrule" in texto
    assert "ferrule" in core.notas_por_campo["var_row_91"]


def test_numero_deduzido_nao_entra():
    core = _core({"var_row_79": _prova(tipo="deducao", trecho="",
                                       justificativa="gR interrompe a partir de 1,3 In")})
    cb, linhas = _logs()
    aprovados = core._filtrar_por_lastro(
        {"var_row_79": "1,3 x In"},
        {"var_row_79": {"desc": "3 - CORRENTE MINIMA DE ATUACAO"}}, DOC_0088, cb)
    assert "var_row_79" not in aprovados
    assert any("dedu" in m.lower() for _n, m in linhas)


def test_trecho_inventado_com_numero_que_nao_esta_no_documento_e_reprovado():
    core = _core({"var_row_83": _prova(trecho="Overall length 258 mm")})
    cb, linhas = _logs()
    aprovados = core._filtrar_por_lastro(
        {"var_row_83": "258 mm"}, {"var_row_83": {"desc": PERGUNTA_COMPRIMENTO}}, DOC_0088, cb)
    assert "var_row_83" not in aprovados
    assert any("trecho" in m.lower() for _n, m in linhas)


def test_trecho_da_linha_de_OUTRO_modelo_e_reprovado():
    doc = "--- LOCAL DOC: d.pdf ---\nUCSCH1: 168 x 150 x 55 mm\nUCECH1: 168 x 150 x 85 mm\n"
    core = _core({"var_row_90": _prova(trecho="UCECH1: 168 x 150 x 85 mm", fonte="d.pdf")},
                 modelo="UCSCH1")
    aprovados = core._filtrar_por_lastro(
        {"var_row_90": "168 x 150 x 85 mm"}, {"var_row_90": {"desc": "DIMENSOES (mm)"}}, doc)
    assert "var_row_90" not in aprovados


def test_a_rotacao_certa_da_0094_passa_intacta():
    doc = "--- LOCAL DOC: m.pdf ---\nMotor 3~ 400 V 60 Hz\nDrehzahl 2860\n"
    core = _core({"var_row_85": _prova(trecho="Drehzahl 2860", fonte="m.pdf")})
    aprovados = core._filtrar_por_lastro(
        {"var_row_85": "2860 rpm"}, {"var_row_85": {"desc": "7 - ROTACAO"}}, doc)
    assert aprovados == {"var_row_85": "2860 rpm"}


def test_conversao_com_prova_e_aprovada_e_anunciada():
    doc = "--- WEB DOC: Cisco ---\nDimensions (H x W x D): 5.98 x 3.58 x 5.31 in.\n"
    core = _core({"var_row_90": _prova(
        tipo="calculo", trecho="Dimensions (H x W x D): 5.98 x 3.58 x 5.31 in.", fonte="Cisco")})
    cb, linhas = _logs()
    aprovados = core._filtrar_por_lastro(
        {"var_row_90": "152 x 91 x 135"},
        {"var_row_90": {"desc": "14 - DIMENSIONS (Indicate the dimensions in (mm))"}}, doc, cb)
    assert aprovados == {"var_row_90": "152 x 91 x 135"}
    assert any("CONVERS" in m.upper() for _n, m in linhas)


def test_conta_errada_com_prova_e_refeita_dentro_do_trecho():
    doc = "--- LOCAL DOC: v.pdf ---\nMaximum operating pressure: 350 bar\nTest pressure 525 bar\n"
    core = _core({"var_row_84": _prova(
        tipo="calculo", trecho="Maximum operating pressure: 350 bar", fonte="v.pdf")})
    aprovados = core._filtrar_por_lastro(
        {"var_row_84": "3,5 MPa"}, {"var_row_84": {"desc": "6 - PRESSAO DE TRABALHO (MPa)"}}, doc)
    assert aprovados == {"var_row_84": "35 MPa"}


def test_valor_lido_de_pagina_sem_texto_entra_com_aviso():
    """PDF escaneado que a IA leu no proprio arquivo: a prova nao tem como
    ser conferida no texto. Entra -- e a mesma confianca do OCR de antes --,
    mas marcado para o engenheiro conferir na pagina."""
    escaneado = docs.Documento(nome="placa.pdf", paginas=["", ""],
                               mime="application/pdf", dados=b"%PDF")
    core = _core({"var_row_92": _prova(trecho="Weight 4,3 kg", fonte="placa.pdf", pagina=2)})
    core._documentos_anexados = [escaneado]
    cb, linhas = _logs()
    aprovados = core._filtrar_por_lastro(
        {"var_row_92": "4,3 kg"}, {"var_row_92": {"desc": "25 - PESO"}}, "", cb)
    assert aprovados == {"var_row_92": "4,3 kg"}
    assert "placa.pdf" in core.notas_por_campo["var_row_92"]
    assert any("sem texto" in m.lower() for _n, m in linhas)


# =============================================================================
# 6. O prompt pede a prova, e as regras que faltavam
# =============================================================================
def test_o_prompt_pede_a_prova_de_cada_valor():
    texto = prompts.montar_autospec("Fusivel", "", "Desc", "ctx", "- ID 'x': Campo X")
    for chave in ('"trecho"', '"pagina"', '"tipo"', '"justificativa"', "deducao", "calculo"):
        assert chave in texto, chave


def test_o_prompt_separa_temperatura_de_operacao_processo_e_armazenamento():
    """O erro da ficha 0084: temperatura de PROCESSO gravada como ambiente."""
    texto = prompts.montar_autospec("Sensor", "", "Desc", "ctx", "").lower()
    assert "armazenamento" in texto and "processo" in texto and "opera" in texto


def test_o_prompt_avisa_que_o_documento_pode_trazer_outro_produto():
    """A ficha 0088 veio com dois fusiveis diferentes anexados."""
    texto = prompts.montar_autospec("Fusivel", "", "Desc", "ctx", "").lower()
    assert "outro produto" in texto or "outros modelos" in texto


# =============================================================================
# 7. A nota vai para a celula
# =============================================================================
class _Celula:
    def __init__(self):
        self.value = None
        self.font = None
        self.comment = None


class _Aba(dict):
    def __missing__(self, chave):
        self[chave] = _Celula()
        return self[chave]


class _Livro:
    def __init__(self):
        self.aba = _Aba()
        self.sheetnames = ["Ficha Técnica Padrão"]

    def __getitem__(self, nome):
        return self.aba


def test_a_nota_da_deducao_vira_comentario_na_celula(monkeypatch, tmp_path):
    comentarios = types.ModuleType("openpyxl.comments")

    class _Comment:
        def __init__(self, texto, autor):
            self.text, self.author = texto, autor

    comentarios.Comment = _Comment
    monkeypatch.setitem(sys.modules, "openpyxl.comments", comentarios)
    monkeypatch.setattr(autospec.locking, "salvar_perguntando", lambda *a, **k: None)

    core = AutoSpecCore.__new__(AutoSpecCore)
    core.notas_por_campo = {"var_row_91": "AutoSpec: deducao tecnica. Fusivel ferrule."}
    livro = _Livro()
    core.fill_save(livro, str(tmp_path / "f.xlsx"), {"var_row_91": "OUTROS"},
                   {"var_row_91": {"type": "text", "ref": "M91:V91"}})
    celula = livro.aba["M91"]
    assert celula.value == "OUTROS"
    assert celula.comment.text.startswith("AutoSpec: deducao tecnica")
