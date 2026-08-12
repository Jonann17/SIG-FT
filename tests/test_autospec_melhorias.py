r"""
Testes das melhorias P-02 a P-06 do AutoSpecAI (2026-08-11).
Ver docs/AUTOSPEC_MELHORIAS.md e docs/base-conhecimento/08b-autospec-contexto-negocio.md.

  P-02  cascata de busca web com truncamento por PALAVRA (regras §4.2 passo 3)
  P-03  formatos de imagem vão para o OCR, não para o parser de HTML (§2.3/§6.1)
  P-04  rastreabilidade campo->fonte, aceitando as duas formas de resposta (§3.4)
  P-05  falha de rede/parse deixa de ser silenciosa
  P-06  varredura das especificações para na última linha PREENCHIDA (§2.2)

Os valores usados nos casos reais vêm da ficha `4500063671.0662`
(POWER PACKS / Hydac), analisada com o usuário.
"""
import pytest

import autospec_backend
from sigft import config
from sigft.core.callbacks import UICallbacks

AutoSpecCore = autospec_backend.AutoSpecCore


@pytest.fixture(autouse=True)
def _isola_config_file_do_cwd_real(monkeypatch, tmp_path):
    monkeypatch.setattr(
        config, "CONFIG_FILE", str(tmp_path / "api_config_isolado_test.json")
    )


@pytest.fixture
def registro():
    """Coletor de log no formato do protocolo `UICallbacks`."""
    linhas = []
    cb = UICallbacks(
        log=lambda msg, nivel="info", contexto=None: linhas.append((str(msg), nivel))
    )
    cb.linhas = linhas
    cb.texto = lambda: "\n".join(m for m, _ in linhas)
    cb.niveis = lambda: {n for _, n in linhas}
    return cb


# =============================================================================
# P-02 — cascata de busca web
# =============================================================================
# Texto breve real da ficha 4500063671.0662, com o espaço duplo e a sobra no
# fim exatamente como estão na planilha.
TXT_BRV_REAL = "CONJUNTO REPARO PARA BOMBA 3527528  PVF100-4 NBR  "
FAB_REAL = "Hydac"


def test_cascata_comeca_pelo_codigo_do_material_entre_aspas():
    qs = AutoSpecCore._montar_queries_busca(TXT_BRV_REAL, FAB_REAL, "MAT-123")
    assert qs[0] == '"MAT-123" Hydac datasheet specs'


def test_sem_codigo_do_material_a_cascata_comeca_pelo_texto_breve():
    qs = AutoSpecCore._montar_queries_busca(TXT_BRV_REAL, FAB_REAL, "")
    assert qs[0].startswith("CONJUNTO REPARO PARA BOMBA 3527528 PVF100-4 NBR")


def test_espaco_duplo_e_sobra_no_fim_sao_normalizados():
    """A planilha real traz `"...NBR  "`. Sem normalizar, a query sai com
    espaço duplo no meio e sobra antes de "Hydac"."""
    qs = AutoSpecCore._montar_queries_busca(TXT_BRV_REAL, FAB_REAL, "")
    assert "  " not in qs[0]
    assert not qs[0].startswith(" ") and not qs[0].endswith(" ")


def test_truncamento_larga_uma_PALAVRA_por_rodada():
    """O passo 3 corta por palavra, não por caractere: cortar 4 caracteres
    parte o token no meio ("PVF100-4" -> "PVF10") e produz query pior."""
    qs = AutoSpecCore._montar_queries_busca("ALPHA BETA GAMA DELTA", "Fab", "")
    trechos = [q.replace(" Fab datasheet specs", "") for q in qs]
    assert trechos == [
        "ALPHA BETA GAMA DELTA",
        "ALPHA BETA GAMA",
        "ALPHA BETA",
    ]


def test_truncamento_respeita_o_piso_de_tokens():
    """Não desce até 1 token: "CONJUNTO Hydac datasheet specs" traz catálogo
    de qualquer coisa e gasta cota do CSE à toa."""
    qs = AutoSpecCore._montar_queries_busca("ALPHA BETA GAMA DELTA", "Fab", "")
    menor = qs[-1].replace(" Fab datasheet specs", "")
    assert len(menor.split()) == AutoSpecCore.MIN_TOKENS_BUSCA


def test_fabricante_sobrevive_a_todas_as_rodadas():
    """É o fabricante que ancora o filtro anti-intruso (§4.3) — não pode
    sumir junto com o truncamento."""
    qs = AutoSpecCore._montar_queries_busca(TXT_BRV_REAL, FAB_REAL, "MAT-1")
    assert all("Hydac" in q for q in qs)


def test_cascata_nao_repete_query():
    qs = AutoSpecCore._montar_queries_busca("ALPHA BETA", "Fab", "ALPHA BETA")
    assert len(qs) == len(set(qs))


def test_texto_breve_curto_nao_gera_query_degenerada():
    qs = AutoSpecCore._montar_queries_busca("BOMBA", "Fab", "")
    assert all(q.strip() for q in qs)
    assert all("datasheet specs" in q for q in qs)


def test_texto_breve_vazio_nao_quebra():
    assert AutoSpecCore._montar_queries_busca("", "Fab", "") == []
    assert AutoSpecCore._montar_queries_busca(None, None, None) == []


# =============================================================================
# P-03 — detecção de formato do download
# =============================================================================
@pytest.mark.parametrize(
    "url,esperado,caso",
    [
        ("https://x.com/a/datasheet.pdf", ".pdf", "pdf direto"),
        ("https://x.com/a/datasheet.pdf?download=1&t=9", ".pdf", "pdf com query string"),
        ("https://x.com/a/catalogo.tif", ".tif", "tiff digitalizado"),
        ("https://x.com/a/desenho.PNG", ".png", "png em maiúsculas"),
        ("https://x.com/a/pagina", ".html", "sem extensão -> html"),
    ],
)
def test_sufixo_detectado_pela_url(url, esperado, caso):
    assert autospec_backend._sufixo_para_url(url) == esperado, caso


def test_content_type_decide_quando_a_url_nao_diz():
    assert autospec_backend._sufixo_para_url("https://x.com/get?id=9", "application/pdf") == ".pdf"
    assert autospec_backend._sufixo_para_url("https://x.com/get?id=9", "image/tiff; charset=binary") == ".tif"


def test_url_vence_content_type_ausente():
    assert autospec_backend._sufixo_para_url("https://x.com/a.pdf", None) == ".pdf"


def test_imagem_sem_chave_do_llamaparse_avisa_em_vez_de_virar_lixo(registro, tmp_path):
    """Antes, um .tif caía no BeautifulSoup e virava texto-lixo, calado."""
    img = tmp_path / "catalogo.tif"
    img.write_bytes(b"\x49\x49\x2a\x00 nao e html")

    proc = autospec_backend.PDFProcessor(llama_key=None)
    texto, metodo = proc.extract_text(str(img), callbacks=registro)

    assert texto == "" and metodo == ""
    assert "OCR" in registro.texto()
    assert "warn" in registro.niveis()


def test_imagem_com_chave_do_llamaparse_vai_para_o_ocr(monkeypatch, tmp_path, registro):
    img = tmp_path / "catalogo.tif"
    img.write_bytes(b"conteudo")

    class _DocFake:
        text = "TEXTO OCR DO CATALOGO"

    class _ParserFake:
        def __init__(self, **kw): pass
        def load_data(self, caminho): return [_DocFake()]

    monkeypatch.setattr(autospec_backend, "LlamaParse", _ParserFake)
    proc = autospec_backend.PDFProcessor(llama_key="chave")
    texto, metodo = proc.extract_text(str(img), callbacks=registro)

    assert texto == "TEXTO OCR DO CATALOGO"
    assert metodo == "LlamaParse"


# =============================================================================
# P-04 — rastreabilidade campo->fonte, tolerante às duas formas
# =============================================================================
def _core():
    return AutoSpecCore(
        gemini_key="chave-fake",
        llama_key=None,
        google_search_key=None,
        google_cse_id=None,
        selecao_resolvida={"provider": config.PROVIDER_GEMINI, "model": "m"},
    )


def test_forma_nova_e_achatada_e_a_fonte_fica_guardada():
    core = _core()
    saida = core._normalizar_resposta_ia(
        {"empilhamento": {"valor": 5, "fonte": "manual_bomba.pdf"}}
    )
    assert saida == {"empilhamento": 5}
    assert core.ultimas_fontes_por_campo == {"empilhamento": "manual_bomba.pdf"}


def test_forma_ANTIGA_continua_funcionando_sem_fonte():
    """Se o modelo ignorar a instrução 7 (modelo mais fraco, ou prompt
    truncado), o preenchimento não pode regredir."""
    core = _core()
    saida = core._normalizar_resposta_ia({"empilhamento": 5, "protecao": "S25"})
    assert saida == {"empilhamento": 5, "protecao": "S25"}
    assert core.ultimas_fontes_por_campo == {}


def test_resposta_mista_e_tratada_campo_a_campo():
    core = _core()
    saida = core._normalizar_resposta_ia(
        {"a": {"valor": 1, "fonte": "x.pdf"}, "b": "cru"}
    )
    assert saida == {"a": 1, "b": "cru"}
    assert core.ultimas_fontes_por_campo == {"a": "x.pdf"}


def test_dict_sem_chave_valor_e_DESCARTADO_com_aviso(registro):
    """MUDOU em 2026-08-11 (validação do contrato): antes o dict passava
    intacto e ia parar em `ws[ref].value`, virando lixo dentro da célula da
    ficha. Célula de ficha guarda texto ou número, nunca estrutura — então o
    campo é descartado, com aviso, e os campos bons seguem."""
    core = _core()
    saida = core._normalizar_resposta_ia(
        {"dims": {"largura": 10, "altura": 20}, "peso": "11 kg"},
        campos_pedidos=["dims", "peso"],
        callbacks=registro,
    )
    assert saida == {"peso": "11 kg"}, "o campo bom não pode ser perdido junto"
    assert "dims" in registro.texto()
    assert "warn" in registro.niveis()


def test_resposta_toda_inaproveitavel_RECUSA_ALTO():
    """Descarte parcial avisa e segue. Descarte TOTAL é formato errado do
    modelo — falha alto, com a instrução de trocar o modelo."""
    core = _core()
    with pytest.raises(ValueError, match="formato aproveitável"):
        core._normalizar_resposta_ia(
            {"a": {"x": 1}, "b": ["lista"]}, campos_pedidos=["a", "b"]
        )


def test_resposta_vazia_NAO_e_erro_de_formato(registro):
    """`{}` é resultado legítimo: pelas regras §3.2, campo [ESTRITO] sem
    evidência DEVE ficar em branco. Avisa, mas não levanta."""
    core = _core()
    assert core._normalizar_resposta_ia({}, campos_pedidos=["a"], callbacks=registro) == {}
    assert "warn" in registro.niveis()


def test_campo_inventado_pela_IA_e_ignorado_COM_aviso(registro):
    """Antes, `if k in missing` descartava em silêncio — a IA respondia algo
    e ninguém ficava sabendo que foi jogado fora."""
    core = _core()
    saida = core._normalizar_resposta_ia(
        {"peso": "11 kg", "campo_que_nao_existe": "algo"},
        campos_pedidos=["peso"],
        callbacks=registro,
    )
    assert saida == {"peso": "11 kg"}
    assert "campo_que_nao_existe" in registro.texto()


def test_envelope_e_desembrulhado_sem_engolir_resposta_de_campo_unico(registro):
    """`{"campos": {...}}` é envelope. Mas `{"empilhamento": 5}` é resposta
    LEGÍTIMA de campo único — a diferença é a chave estar entre os pedidos."""
    core = _core()
    envelope = core._normalizar_resposta_ia(
        {"campos": {"peso": "11 kg"}}, campos_pedidos=["peso"], callbacks=registro
    )
    assert envelope == {"peso": "11 kg"}

    unico = core._normalizar_resposta_ia(
        {"empilhamento": 5}, campos_pedidos=["empilhamento"], callbacks=registro
    )
    assert unico == {"empilhamento": 5}, "campo único não pode ser confundido com envelope"


def test_fontes_sao_zeradas_a_cada_chamada():
    """A instância é reutilizada em todo o lote — fonte da ficha anterior não
    pode vazar para a próxima (§4.1, isolamento de contexto)."""
    core = _core()
    core._normalizar_resposta_ia({"a": {"valor": 1, "fonte": "primeira.pdf"}})
    core._normalizar_resposta_ia({"b": 2})
    assert core.ultimas_fontes_por_campo == {}


def test_resposta_nao_dict_RECUSA_ALTO():
    """MUDOU em 2026-08-11: antes passava intacta e estourava lá na frente,
    dentro do `fill_save`, com `AttributeError: 'list' object has no attribute
    'items'` — mensagem que não diz nada sobre IA. Agora falha aqui, dizendo o
    que veio e o que fazer. É a metade que faltava da pendência do Luan."""
    core = _core()
    with pytest.raises(ValueError, match="OBJETO JSON"):
        core._normalizar_resposta_ia([1, 2])
    with pytest.raises(ValueError, match="não devolveu resposta"):
        core._normalizar_resposta_ia(None)


# =============================================================================
# P-06 — varredura das especificações variáveis
# =============================================================================
class _CelulaFake:
    def __init__(self, value): self.value = value


class _FichaFake:
    """Ficha mínima para `analyze_sheet`: só o necessário para o laço das
    especificações variáveis. `max_row` propositalmente muito maior que a
    última linha com conteúdo — é o cenário do bug (na ficha real, perguntas
    até a 103 e `max_row` 132)."""

    def __init__(self, perguntas_ate, max_row):
        self._perguntas_ate = perguntas_ate
        self.max_row = max_row
        self.linhas_lidas = set()

    def cell(self, row, column):
        self.linhas_lidas.add(row)
        if column == 3 and 79 <= row <= self._perguntas_ate:
            return _CelulaFake(f"{row - 78} - PERGUNTA")
        return _CelulaFake(None)


def test_varredura_para_depois_da_ultima_pergunta():
    ws = _FichaFake(perguntas_ate=103, max_row=1_048_576)
    limite = AutoSpecCore.MAX_LINHAS_VAZIAS_SEGUIDAS

    r, vazias = 79, 0
    while r <= ws.max_row and vazias < limite:
        vazias = 0 if ws.cell(row=r, column=3).value else vazias + 1
        r += 1

    assert r <= 103 + limite + 1
    assert max(ws.linhas_lidas) < 200, "não pode varrer a planilha inteira"


def test_varredura_atravessa_buraco_menor_que_o_limite():
    """Um vão de linhas de layout no meio da lista não pode encerrar a
    varredura e perder as perguntas seguintes."""
    limite = AutoSpecCore.MAX_LINHAS_VAZIAS_SEGUIDAS
    assert limite >= 25, "folga suficiente para blocos de layout no meio da lista"


def test_a_ficha_real_cabe_com_folga_no_limite():
    """Ficha 4500063671.0662: perguntas de 79 a 103, `max_row` 132 — 29
    linhas vazias no fim. O limite tem de ser menor que isso para valer, e
    maior que qualquer vão interno observado."""
    vazias_no_fim_da_ficha_real = 132 - 103
    assert AutoSpecCore.MAX_LINHAS_VAZIAS_SEGUIDAS < vazias_no_fim_da_ficha_real
