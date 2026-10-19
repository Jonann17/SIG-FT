r"""A IA passa a ler o documento INTEIRO -- e, quando pode, o proprio PDF (2026-09-24).

O que a comparacao do usuario com o AMP mostrou, medido no log da ficha 0094:

    4500063671.0094.pdf: 166 pagina(s), 166 lida(s) (100%), 177273 chars
    Contexto recortado: 19 de 61 trecho(s), 23259 de 60041 chars

O manual foi lido por inteiro -- e 87% dele nunca chegou a IA. Dois cortes em
serie: `t[:60000]` por documento, antes de qualquer busca, e um teto de
24.000 caracteres no recorte por relevancia. Vazao, pressao estatica,
dimensoes e peso do ventilador ficaram em branco; o AMP, que recebe o PDF
inteiro, achou todos.

O desenho novo, em tres pecas testadas aqui:

1. **Documento inteiro.** Nada de corte por documento; o recorte (RAG) so
   entra acima de 300 mil caracteres -- um manual de mil paginas, nao um
   datasheet de seis.
2. **O proprio PDF**, quando o modelo le PDF (`LLMClient.aceita_pdf`) e o
   arquivo cabe (15 MB, 500 paginas por chamada). O modelo ve o desenho
   cotado e a tabela; o texto extraido continua existindo, para conferir a
   prova que ele devolve.
3. **Rede automatica:** se o provedor recusar o anexo, a mesma ficha e
   refeita pelo texto. Timeout NAO cai para o texto -- dobraria a espera.
"""
import json

import pytest

from sigft import config
from sigft.services import autospec, autospec_documentos as docs
from sigft.services.autospec import AutoSpecCore


# =============================================================================
# Andaimes
# =============================================================================
class _Resposta:
    def __init__(self, parsed):
        self.parsed_json = parsed
        self.text = json.dumps(parsed)


class _LLMFake:
    """Grava cada chamada; `falhas` e uma lista de excecoes consumida em
    ordem, uma por chamada (None = responde)."""

    def __init__(self, aceita_pdf=True, falhas=None, parsed=None):
        self.aceita_pdf = aceita_pdf
        self.falhas = list(falhas or [])
        self.parsed = parsed if parsed is not None else {"empilhamento": "5"}
        self.chamadas = []

    def generate(self, prompt, *, system=None, json_mode=False, tags=None, anexos=None):
        self.chamadas.append({"prompt": prompt, "anexos": anexos})
        falha = self.falhas.pop(0) if self.falhas else None
        if falha is not None:
            raise falha
        return _Resposta(self.parsed)


CAMPO = {"empilhamento": {"type": "text", "desc": "Empilhamento maximo", "ref": "M42"}}


def _core(llm):
    core = AutoSpecCore(
        gemini_key="k", llama_key=None, google_search_key=None, google_cse_id=None,
        selecao_resolvida={"provider": config.PROVIDER_GEMINI, "model": "m"},
    )
    core._llm = llm
    core.usar_cache_resposta = False
    return core


def _logs():
    registro = []

    class _CB:
        def log(self, msg, nivel="info", contexto=None):
            registro.append((nivel, str(msg)))

    return _CB(), registro


def _pdf(nome="datasheet.pdf", paginas=("Operating temperature -10 to 85 C",), dados=b"%PDF-1.4"):
    return docs.Documento(nome=nome, origem="LOCAL", paginas=list(paginas),
                          mime="application/pdf", dados=dados)


# =============================================================================
# 1. O documento, por pagina
# =============================================================================
def test_o_texto_leva_o_marcador_do_documento_e_de_cada_pagina():
    """A pagina e o que a IA cita como prova -- e o que o engenheiro abre
    para conferir. Sem marcador, "pagina 3" nao teria de onde sair."""
    doc = _pdf(paginas=["Capa", "Storage temperature -20 to 85 C"])
    texto = doc.texto_marcado()
    assert texto.startswith("--- LOCAL DOC: datasheet.pdf ---")
    assert "[página 2]\nStorage temperature -20 to 85 C" in texto


def test_documento_da_web_leva_a_url_logo_abaixo_do_marcador():
    """Mesmo formato de sempre: `origens_do_contexto` le a URL dessa linha."""
    doc = docs.Documento(nome="Datasheet X", origem="WEB", paginas=["texto"],
                         url="https://fab.com/x.pdf")
    assert doc.texto_marcado().startswith(
        "--- WEB DOC: Datasheet X ---\nURL: https://fab.com/x.pdf\n")


def test_pagina_sem_texto_e_identificada():
    """Pagina escaneada, lida pela IA no PDF nativo: a prova dela nao tem
    como ser conferida no texto, e a conferencia precisa saber disso."""
    doc = _pdf(paginas=["Texto de verdade, com mais de quarenta caracteres aqui.", "  "])
    assert doc.paginas_sem_texto == [2]


def test_o_pdf_e_lido_pagina_a_pagina(tmp_path):
    pymupdf = pytest.importorskip("pymupdf")
    arquivo = tmp_path / "ficha.pdf"
    pdf = pymupdf.open()
    pdf.new_page().insert_text((72, 72), "Rated voltage 2000 V DC, breaking capacity 30 kA")
    pdf.new_page()  # pagina em branco -- a "escaneada"
    pdf.save(str(arquivo))

    doc = docs.ler_documento(str(arquivo), autospec.PDFProcessor(None), origem="LOCAL")
    assert len(doc.paginas) == 2
    assert "2000 V DC" in doc.paginas[0]
    assert doc.paginas_sem_texto == [2]
    assert doc.mime == "application/pdf"
    assert doc.pode_ir_como_anexo


# =============================================================================
# 2. O que vai como PDF e o que vai como texto
# =============================================================================
def test_modelo_que_nao_le_pdf_recebe_tudo_em_texto():
    anexos, em_texto = docs.planejar_envio([_pdf()], aceita_pdf=False)
    assert anexos == [] and len(em_texto) == 1


def test_modelo_que_le_pdf_recebe_o_arquivo():
    anexos, em_texto = docs.planejar_envio([_pdf()], aceita_pdf=True)
    assert len(anexos) == 1 and em_texto == []


def test_o_que_passa_do_limite_de_tamanho_vai_como_texto():
    grande = _pdf(nome="manual.pdf", dados=b"x" * 2000)
    pequeno = _pdf(nome="datasheet.pdf", dados=b"x" * 500)
    anexos, em_texto = docs.planejar_envio(
        [pequeno, grande], aceita_pdf=True, limite_bytes=1000)
    assert [d.nome for d in anexos] == ["datasheet.pdf"]
    assert [d.nome for d in em_texto] == ["manual.pdf"]


def test_o_que_passa_do_limite_de_paginas_vai_como_texto():
    manual = _pdf(nome="manual.pdf", paginas=["p"] * 400)
    catalogo = _pdf(nome="catalogo.pdf", paginas=["p"] * 200)
    anexos, em_texto = docs.planejar_envio(
        [manual, catalogo], aceita_pdf=True, limite_paginas=500)
    assert [d.nome for d in anexos] == ["manual.pdf"]
    assert [d.nome for d in em_texto] == ["catalogo.pdf"]


def test_pagina_html_vai_sempre_como_texto():
    pagina = docs.Documento(nome="Loja", origem="WEB", paginas=["specs"],
                            url="https://x", mime="text/html", dados=b"<html>")
    anexos, em_texto = docs.planejar_envio([pagina], aceita_pdf=True)
    assert anexos == [] and len(em_texto) == 1


# =============================================================================
# 3. Na chamada da IA
# =============================================================================
def test_modelo_que_le_pdf_recebe_o_arquivo_e_o_prompt_diz_qual_e():
    llm = _LLMFake(aceita_pdf=True)
    core = _core(llm)
    core._documentos = [_pdf(nome="4500063671.0088.pdf", dados=b"%PDF fusivel")]
    core.generate_ai_response("Fusivel", "", "Desc", CAMPO, core._documentos[0].texto_marcado())

    chamada = llm.chamadas[0]
    assert [a.nome for a in chamada["anexos"]] == ["4500063671.0088.pdf"]
    assert chamada["anexos"][0].dados == b"%PDF fusivel"
    assert "4500063671.0088.pdf" in chamada["prompt"]
    # O texto do documento NAO vai junto: seria pagar duas vezes pelo mesmo.
    assert "Operating temperature" not in chamada["prompt"]


def test_desligar_a_leitura_nativa_manda_o_texto():
    llm = _LLMFake(aceita_pdf=True)
    core = _core(llm)
    core.ler_pdf_nativo = False
    core._documentos = [_pdf()]
    core.generate_ai_response("X", "", "D", CAMPO, core._documentos[0].texto_marcado())
    assert not llm.chamadas[0]["anexos"]
    assert "Operating temperature" in llm.chamadas[0]["prompt"]


def test_provedor_que_recusa_o_pdf_faz_a_ficha_cair_para_o_texto():
    llm = _LLMFake(aceita_pdf=True, falhas=[ValueError("400 Bad Request: file not supported")])
    core = _core(llm)
    core._documentos = [_pdf()]
    cb, registro = _logs()
    resultado = core.generate_ai_response(
        "X", "", "D", CAMPO, core._documentos[0].texto_marcado(), callbacks=cb)

    assert resultado == {"empilhamento": "5"}
    assert len(llm.chamadas) == 2
    assert not llm.chamadas[1]["anexos"]
    assert "Operating temperature" in llm.chamadas[1]["prompt"]
    assert core.ultima_falha_ia is None
    assert any(nivel == "warn" and "texto" in msg for nivel, msg in registro), registro


def test_timeout_com_pdf_NAO_tenta_de_novo_pelo_texto():
    """Timeout nao e recusa: o provedor aceitou e demorou. Refazer pelo texto
    somaria mais 5 minutos de espera a uma ficha que ja esperou 10."""
    llm = _LLMFake(aceita_pdf=True, falhas=[TimeoutError("Read timed out")])
    core = _core(llm)
    core._documentos = [_pdf()]
    assert core.generate_ai_response("X", "", "D", CAMPO, "ctx") == {}
    assert len(llm.chamadas) == 1
    assert "Read timed out" in core.ultima_falha_ia


def test_o_cache_distingue_o_mesmo_prompt_com_pdf_diferente():
    """O prompt do caminho nativo NAO carrega o texto do documento -- so o
    nome. Sem os bytes na chave, trocar o PDF por uma revisao nova com o
    mesmo nome serviria a resposta da revisao velha."""
    a = autospec._chave_cache_resposta("p", "g", "m", anexos=[b"%PDF rev A"])
    b = autospec._chave_cache_resposta("p", "g", "m", anexos=[b"%PDF rev B"])
    assert a != b
    assert autospec._chave_cache_resposta("p", "g", "m") == autospec._chave_cache_resposta("p", "g", "m")


# =============================================================================
# 4. Sem corte: o documento chega inteiro
# =============================================================================
def test_documento_de_200_mil_caracteres_chega_inteiro_a_IA():
    """A 0094 tinha 177 mil caracteres, e chegavam 23 mil."""
    llm = _LLMFake(aceita_pdf=False)
    core = _core(llm)
    corpo = "linha de manual com dado tecnico\n" * 6000  # ~200 mil chars
    contexto = f"--- LOCAL DOC: manual.pdf ---\n{corpo}FIM DO MANUAL: vazao 164 m3/h"
    core.generate_ai_response("Ventilador", "", "D", CAMPO, contexto)
    assert "FIM DO MANUAL: vazao 164 m3/h" in llm.chamadas[0]["prompt"]


def test_acima_de_300_mil_caracteres_o_recorte_volta_a_agir():
    llm = _LLMFake(aceita_pdf=False)
    core = _core(llm)
    contexto = ("--- LOCAL DOC: gigante.pdf ---\n" + ("texto sem relacao nenhuma\n" * 16000)
                + "Empilhamento maximo: 5 caixas\n")
    core.generate_ai_response("X", "", "D", CAMPO, contexto)
    prompt = llm.chamadas[0]["prompt"]
    assert len(prompt) < len(contexto) / 2
    assert "Empilhamento maximo: 5 caixas" in prompt


def test_os_documentos_locais_nao_sao_mais_cortados_em_60_mil():
    class _Leitor:
        def ler_paginas(self, caminho, callbacks=None, nome_exibicao=None):
            return ["x" * 100_000, "y" * 100_000], "PyMuPDF"

    core = AutoSpecCore.__new__(AutoSpecCore)
    core.pdf_parser = _Leitor()
    texto = core.process_local_documents(["/tmp/manual.pdf"])
    assert texto.count("x") == 100_000 and texto.count("y") == 100_000
    assert [d.nome for d in core._documentos] == ["manual.pdf"]


# =============================================================================
# 5. Pagina sem texto vai como IMAGEM quando o PDF vai como texto  [2026-10-19]
# =============================================================================
# No caminho de texto (modelo que nao le PDF, ou documento grande demais para
# ir inteiro) a pagina escaneada ou o desenho cotado chegava VAZIO a IA, e a
# unica saida era o LlamaParse, que sobe o arquivo inteiro. Agora a pagina sem
# texto vai como imagem (JPEG), ate `MAX_PAGINAS_IMAGEM` por ficha. Ideia do
# RAG-Anything (HKUDS, MIT): mandar a pagina a um modelo com visao. Modelo sem
# visao recusa o anexo, e a ficha cai para o texto, pela rede de sempre.

TEXTO_LONGO = "Rated voltage 2000 V DC, breaking capacity 30 kA, IP65 enclosure."


def _pdf_real(paginas_texto, total, nome="manual.pdf"):
    pymupdf = pytest.importorskip("pymupdf")
    pdf = pymupdf.open()
    for i in range(total):
        pagina = pdf.new_page()
        if i in paginas_texto:
            pagina.insert_text((72, 72), TEXTO_LONGO)
        else:
            pagina.draw_rect(pymupdf.Rect(100, 100, 400, 300), color=(0, 0, 0))  # o "desenho"
    dados = pdf.tobytes()
    pdf.close()
    return docs.Documento(nome=nome, origem="LOCAL", mime="application/pdf", dados=dados,
                          paginas=[TEXTO_LONGO if i in paginas_texto else "" for i in range(total)])


def test_paginas_sem_texto_viram_imagem_jpeg_com_o_nome_e_a_pagina():
    doc = _pdf_real({0, 2}, total=4)

    anexos, vistas, deixadas = docs.paginas_em_imagem([doc])

    assert [a.nome for a in anexos] == ["manual.pdf - pagina 2.jpg", "manual.pdf - pagina 4.jpg"]
    assert all(a.mime == "image/jpeg" and a.dados[:3] == b"\xff\xd8\xff" for a in anexos)
    assert [v.paginas_como_imagem for v in vistas] == [(2, 4)] and deixadas == 0


def test_o_limite_de_paginas_imagem_e_por_ficha_e_o_resto_e_contado():
    a, b = _pdf_real(set(), total=3, nome="a.pdf"), _pdf_real(set(), total=3, nome="b.pdf")

    anexos, vistas, deixadas = docs.paginas_em_imagem([a, b], limite=4)

    assert [x.nome for x in anexos] == ["a.pdf - pagina 1.jpg", "a.pdf - pagina 2.jpg",
                                        "a.pdf - pagina 3.jpg", "b.pdf - pagina 1.jpg"]
    assert [v.paginas_como_imagem for v in vistas] == [(1, 2, 3), (1,)] and deixadas == 2


@pytest.mark.parametrize("doc", [
    docs.Documento(nome="loja", origem="WEB", paginas=[""], mime="text/html", dados=b"<html>"),
    docs.Documento(nome="ruim.pdf", origem="LOCAL", paginas=[""], mime="application/pdf",
                   dados=b"nao e pdf"),
    docs.Documento(nome="sumiu.pdf", origem="LOCAL", paginas=[""], mime="application/pdf",
                   caminho="/nao/existe.pdf"),
], ids=["html", "pdf-invalido", "arquivo-sumiu"])
def test_o_que_nao_e_pdf_legivel_nao_vira_imagem_e_nao_quebra(doc):
    assert docs.paginas_em_imagem([doc]) == ([], [], 0)


def test_modelo_que_nao_le_pdf_recebe_o_texto_E_as_paginas_sem_texto_como_imagem():
    llm = _LLMFake(aceita_pdf=False)
    core = _core(llm)
    core._documentos = [_pdf_real({0}, total=2)]
    cb, registro = _logs()

    core.generate_ai_response("X", "", "D", CAMPO, core._documentos[0].texto_marcado(), callbacks=cb)

    chamada = llm.chamadas[0]
    assert [a.nome for a in chamada["anexos"]] == ["manual.pdf - pagina 2.jpg"]
    assert TEXTO_LONGO in chamada["prompt"]
    assert "manual.pdf" in chamada["prompt"] and "IMAGEM" in chamada["prompt"]
    assert any("imagem" in msg.lower() for _, msg in registro)


def test_desligar_as_paginas_imagem_manda_so_o_texto():
    llm = _LLMFake(aceita_pdf=False)
    core = _core(llm)
    core.enviar_paginas_imagem = False
    core._documentos = [_pdf_real({0}, total=2)]

    core.generate_ai_response("X", "", "D", CAMPO, core._documentos[0].texto_marcado())

    assert not llm.chamadas[0]["anexos"]


def test_modelo_sem_visao_que_recusa_a_imagem_cai_para_o_texto():
    llm = _LLMFake(aceita_pdf=False, falhas=[ValueError("400: image input not supported")])
    core = _core(llm)
    core._documentos = [_pdf_real({0}, total=2)]

    resultado = core.generate_ai_response("X", "", "D", CAMPO, core._documentos[0].texto_marcado())

    assert resultado == {"empilhamento": "5"}
    assert len(llm.chamadas) == 2 and not llm.chamadas[1]["anexos"]


def test_quando_o_pdf_vai_inteiro_nenhuma_pagina_vai_de_novo_como_imagem():
    llm = _LLMFake(aceita_pdf=True)
    core = _core(llm)
    core._documentos = [_pdf_real({0}, total=2)]

    core.generate_ai_response("X", "", "D", CAMPO, core._documentos[0].texto_marcado())

    assert [a.nome for a in llm.chamadas[0]["anexos"]] == ["manual.pdf"]


class _Prova:
    def __init__(self, fonte, pagina):
        self.fonte, self.pagina = fonte, pagina


def test_a_conferencia_aceita_a_pagina_que_foi_como_imagem_e_so_ela():
    # A pagina 4 tambem nao tem texto, mas nao foi como imagem (passou do
    # limite): um trecho "dela" seria invencao, e nao pode passar por leitura.
    vista = docs.Documento(nome="manual.pdf", origem="LOCAL", mime="application/pdf",
                           paginas=[TEXTO_LONGO, "", TEXTO_LONGO, ""], paginas_como_imagem=(2,))

    assert autospec._documento_de_pagina_sem_texto(_Prova("manual.pdf", 2), [vista]) is vista
    assert autospec._documento_de_pagina_sem_texto(_Prova("manual.pdf", 4), [vista]) is None
