r"""Salvar e retomar a conferência num `.txt` (2026-08-17).

**O problema que isto resolve**, relatado pelo Luan depois de usar a
ferramenta: o lote roda, a lista de duvidosos aparece, e conferir link por
link leva tempo. Se ele precisa fechar o aplicativo antes de terminar,
**perde o processamento inteiro** — os links, o agrupamento por ficha, e o que
já tinha conferido. Rodar de novo custa cota de busca e tempo de IA.

O combinado: um botão exporta a aba para um `.txt` na pasta do `_STATUS_PMIB`,
e outro importa esse `.txt` de volta — inclusive num dia seguinte, com o
aplicativo reaberto do zero.

**Por que `.txt` e não JSON/pickle:** o arquivo é para SER LIDO E EDITADO POR
UMA PESSOA. O engenheiro abre no Bloco de Notas, clica nos links, marca `[x]`
no que serve, salva. O formato precisa aguentar mão humana — marcação torta,
linha em branco a mais, comentário escrito no meio.
"""
import os

import pytest

from sigft.services import autospec_conferencia as conf
from sigft.services.autospec import AutoSpecCore


DOCS = [
    {"url": "https://www.target.com/p/minnie-t-shirt/-/A-1000325606",
     "title": "Women's Disney Minnie Mouse T-Shirt", "snippet": "oversized graphic tee"},
    {"url": "https://docs.rs-online.com/284f/A700000011330366.pdf",
     "title": "Fieldbus Coupler Modbus TCP; 4th generation Data Sheet",
     "snippet": "750-362 technical data"},
]


def _conferencia_de_exemplo():
    c = conf.Conferencia()
    c.registrar("C:/fichas/4500063671.0071.xlsx", material="WAGO / 750-362",
                documentos=DOCS, refs_locais=["C:/manuais/wago.pdf"])
    c.registrar("C:/fichas/4500063671.0154.xlsx", material="NIDEC / M2QA90L4A",
                documentos=[{"url": "https://nidec/motor.pdf", "title": "Motor M2QA",
                             "snippet": "3 kW"}])
    return c


# =============================================================================
# A. O que o arquivo precisa carregar
# =============================================================================
def test_o_txt_traz_a_ficha_o_material_e_os_links():
    texto = conf.exportar_txt(_conferencia_de_exemplo())
    assert "4500063671.0071.xlsx" in texto
    assert "WAGO / 750-362" in texto
    for doc in DOCS:
        assert doc["url"] in texto


def test_o_txt_traz_o_caminho_COMPLETO_da_ficha():
    """Sem o caminho, a 2ª passada não sabe qual planilha abrir — o arquivo
    seria bonito e inútil."""
    texto = conf.exportar_txt(_conferencia_de_exemplo())
    assert "C:/fichas/4500063671.0071.xlsx" in texto


def test_o_que_estava_marcado_na_tela_sai_marcado_no_txt():
    """Quem conferiu metade na tela e exportou não pode perder a metade."""
    texto = conf.exportar_txt(_conferencia_de_exemplo(), marcados={(0, 1): True})
    linhas = [l.strip() for l in texto.splitlines() if DOCS[1]["url"] in l]
    assert linhas and linhas[0].startswith("[x]")
    minnie = [l.strip() for l in texto.splitlines() if DOCS[0]["url"] in l]
    assert minnie and minnie[0].startswith("[ ]")


def _linhas_de_link(texto):
    """Só as linhas de documento — o cabeçalho também cita `[ ]` e `[x]` ao
    explicar como marcar, e contá-lo junto mediria a instrução, não o dado."""
    return [l.strip() for l in texto.splitlines()
            if "http" in l and not l.strip().startswith("#")]


def test_sem_marcacao_nenhuma_tudo_sai_desmarcado():
    linhas = _linhas_de_link(conf.exportar_txt(_conferencia_de_exemplo()))
    assert len(linhas) == 3
    assert all(l.startswith("[ ]") for l in linhas)


def test_o_arquivo_explica_como_usar():
    """Ele vai ser aberto horas depois, talvez por outra pessoa, fora do
    aplicativo. Sem instrução dentro, vira um monte de link solto."""
    texto = conf.exportar_txt(_conferencia_de_exemplo())
    assert "[x]" in texto
    assert "IMPORTAR" in texto.upper()


def test_os_manuais_locais_vao_junto():
    """A 2ª passada usa os PDFs anexados na 1ª. Se eles não voltarem, o
    contexto fica menor do que era — a conferência pioraria a ficha."""
    texto = conf.exportar_txt(_conferencia_de_exemplo())
    assert "C:/manuais/wago.pdf" in texto


def test_titulo_com_quebra_de_linha_nao_quebra_o_formato():
    """Snippet do Google vem com `\\n` no meio. Uma linha virando duas
    desalinharia o arquivo inteiro."""
    c = conf.Conferencia()
    c.registrar("a.xlsx", documentos=[
        {"url": "https://x/1", "title": "linha um\nlinha dois", "snippet": "a\r\nb"}])
    texto = conf.exportar_txt(c)
    assert "linha um linha dois" in texto
    assert len([l for l in texto.splitlines() if l.strip().startswith("TITULO:")]) == 1


# =============================================================================
# B. Voltar do arquivo
# =============================================================================
def test_o_txt_volta_com_as_mesmas_fichas_e_links():
    original = _conferencia_de_exemplo()
    volta, _ = conf.importar_txt(conf.exportar_txt(original))
    assert len(volta.pendencias) == 2
    assert volta.total_documentos == 3
    assert volta.pendencias[0].ficha == "C:/fichas/4500063671.0071.xlsx"
    assert [d["url"] for d in volta.pendencias[0].documentos] == [d["url"] for d in DOCS]


def test_material_titulo_e_manual_sobrevivem_ao_roundtrip():
    """A tela remonta a lista a partir disto — sem título, o engenheiro vê
    só URL crua e perde o pouco de contexto que tinha."""
    volta, _ = conf.importar_txt(conf.exportar_txt(_conferencia_de_exemplo()))
    p = volta.pendencias[0]
    assert p.material == "WAGO / 750-362"
    assert p.refs_locais == ["C:/manuais/wago.pdf"]
    assert p.documentos[1]["title"].startswith("Fieldbus Coupler")


def test_o_que_estava_marcado_volta_marcado():
    texto = conf.exportar_txt(_conferencia_de_exemplo(), marcados={(0, 1): True})
    volta, marcados = conf.importar_txt(texto)
    assert marcados == {(0, 0): False, (0, 1): True, (1, 0): False}


def test_o_roundtrip_preserva_a_SELECAO_e_nao_so_o_texto():
    """O que importa no fim é `selecao_por_ficha` devolver as mesmas URLs —
    é ela que alimenta a 2ª passada."""
    original = _conferencia_de_exemplo()
    marcados = {(0, 1): True, (1, 0): True}
    volta, marcados_lidos = conf.importar_txt(conf.exportar_txt(original, marcados))
    assert volta.selecao_por_ficha(marcados_lidos) == original.selecao_por_ficha(marcados)


@pytest.mark.parametrize("marca", ["[x]", "[X]", "[ x ]", "[*]"])
def test_marcacao_feita_a_mao_no_bloco_de_notas_vale(marca):
    """Ninguém vai marcar com precisão de parser. `[X]` e `[ x ]` são o que
    sai de uma pessoa apressada, e valem tanto quanto `[x]`."""
    texto = f"FICHA: a.xlsx\n  {marca} https://x/1\n"
    _, marcados = conf.importar_txt(texto)
    assert marcados == {(0, 0): True}


@pytest.mark.parametrize("marca", ["[ ]", "[]", "[  ]"])
def test_o_que_nao_foi_marcado_continua_desmarcado(marca):
    texto = f"FICHA: a.xlsx\n  {marca} https://x/1\n"
    _, marcados = conf.importar_txt(texto)
    assert marcados == {(0, 0): False}


def test_comentario_e_linha_em_branco_sao_ignorados():
    texto = (
        "# isto e um comentario\n"
        "\n"
        "FICHA: a.xlsx\n"
        "# outro comentario no meio\n"
        "  [x] https://x/1\n"
        "\n"
    )
    volta, marcados = conf.importar_txt(texto)
    assert volta.total_documentos == 1
    assert marcados == {(0, 0): True}


def test_arquivo_vazio_nao_quebra():
    volta, marcados = conf.importar_txt("")
    assert not volta
    assert marcados == {}


def test_texto_que_nao_e_conferencia_devolve_nada():
    """Importar o arquivo errado tem de dar lista vazia, não meia
    conferência inventada."""
    volta, marcados = conf.importar_txt("Prezado senhor,\n\nsegue em anexo...")
    assert not volta
    assert marcados == {}


def test_link_solto_antes_de_qualquer_ficha_e_ignorado():
    """Sem `FICHA:` acima, não há planilha para reprocessar — o link não tem
    dono e não pode virar um."""
    volta, _ = conf.importar_txt("  [x] https://orfa/1\nFICHA: a.xlsx\n  [ ] https://x/1\n")
    assert volta.total_documentos == 1
    assert volta.pendencias[0].documentos[0]["url"] == "https://x/1"


def test_ficha_sem_nenhum_link_nao_entra():
    """Mesma regra da conferência em memória: só entra o que precisa de
    decisão."""
    volta, _ = conf.importar_txt("FICHA: vazia.xlsx\nMATERIAL: nada\n")
    assert not volta


def test_espaco_sobrando_na_url_e_limpo():
    volta, _ = conf.importar_txt("FICHA: a.xlsx\n[x]    https://x/1   \n")
    assert volta.pendencias[0].documentos[0]["url"] == "https://x/1"


def test_a_2a_passada_aceita_a_conferencia_IMPORTADA():
    """O teste que fecha o ciclo: reabrir o app, importar o .txt e
    reprocessar tem de funcionar sem a 1ª passada ter acontecido nesta
    sessão."""
    texto = conf.exportar_txt(_conferencia_de_exemplo(), marcados={(0, 1): True})
    volta, marcados = conf.importar_txt(texto)

    core = AutoSpecCore.__new__(AutoSpecCore)
    core.conferencia = volta
    core.usar_navegador_ultimo_recurso = False
    core.analyze_sheet = lambda f, s: (
        object(), {"var_row_79": {"type": "text", "desc": "P", "ref": "M79"}},
        "MAT", "WAGO", "desc", "cod", "750-362")
    refs_vistos = []
    core.contexto_das_urls = lambda urls, refs=(), callbacks=None: (
        refs_vistos.append(list(refs)) or "Modbus TCP coupler datasheet." * 20)
    core.generate_ai_response = lambda *a, **k: {"var_row_79": "24 V"}
    core.fill_save = lambda wb, f, r, m, callbacks=None: f"{f}_completed.xlsx"

    linhas = list(core.processar_conferidos(volta.selecao_por_ficha(marcados), None))
    assert any("Salvo:" in l for l in linhas)
    # os manuais da 1a passada foram junto, vindos do proprio .txt
    assert refs_vistos == [["C:/manuais/wago.pdf"]]


# =============================================================================
# C. Onde o arquivo fica
# =============================================================================
def test_salva_na_pasta_do_STATUS_PMIB(tmp_path):
    """Pedido explícito do usuário: é a pasta que ele já tem aberta."""
    status = tmp_path / "planilhas" / "_STATUS_PMIB.xlsx"
    status.parent.mkdir()
    status.write_text("x")
    caminho = conf.salvar_txt(_conferencia_de_exemplo(), str(status))
    assert os.path.dirname(caminho) == str(status.parent)
    assert caminho.endswith(".txt")


def test_sem_STATUS_PMIB_cai_na_pasta_da_ficha(tmp_path):
    """O status é obrigatório para processar, mas não posso perder o arquivo
    do usuário se ele vier vazio."""
    ficha = tmp_path / "0071.xlsx"
    ficha.write_text("x")
    c = conf.Conferencia()
    c.registrar(str(ficha), documentos=[{"url": "https://x/1"}])
    caminho = conf.salvar_txt(c, "")
    assert os.path.dirname(caminho) == str(tmp_path)


def test_salvar_duas_vezes_nao_sobrescreve_a_conferencia_anterior(tmp_path):
    """Perder a conferência de ontem ao exportar a de hoje seria o mesmo bug
    que este recurso veio consertar."""
    status = tmp_path / "_STATUS_PMIB.xlsx"
    status.write_text("x")
    a = conf.salvar_txt(_conferencia_de_exemplo(), str(status))
    b = conf.salvar_txt(_conferencia_de_exemplo(), str(status))
    assert a != b
    assert os.path.exists(a) and os.path.exists(b)


def test_o_ciclo_completo_passando_pelo_disco(tmp_path):
    status = tmp_path / "_STATUS_PMIB.xlsx"
    status.write_text("x")
    original = _conferencia_de_exemplo()
    caminho = conf.salvar_txt(original, str(status), marcados={(0, 1): True})
    volta, marcados = conf.carregar_txt(caminho)
    assert volta.selecao_por_ficha(marcados) == original.selecao_por_ficha({(0, 1): True})


def test_arquivo_salvo_como_ANSI_pelo_bloco_de_notas_ainda_abre(tmp_path):
    """O "Salvar como" do Bloco de Notas ainda oferece ANSI, e um acento
    salvo assim não é UTF-8. O arquivo existe para ser editado à mão — se
    editar à mão puder torná-lo ilegível, o recurso não serve."""
    caminho = tmp_path / "conf.txt"
    caminho.write_bytes(
        "FICHA: a.xlsx\nMATERIAL: Válvula de retenção\n  [x] https://x/1\n".encode("cp1252")
    )
    volta, marcados = conf.carregar_txt(str(caminho))
    assert volta.pendencias[0].material == "Válvula de retenção"
    assert marcados == {(0, 0): True}


def test_acento_no_material_sobrevive_ao_disco(tmp_path):
    """`Válvula`, `Redução`, `Óleo` — a planilha é em português."""
    status = tmp_path / "_STATUS_PMIB.xlsx"
    status.write_text("x")
    c = conf.Conferencia()
    c.registrar("a.xlsx", material="Válvula de retenção — Ø 50",
                documentos=[{"url": "https://x/1", "title": "Injeção"}])
    volta, _ = conf.carregar_txt(conf.salvar_txt(c, str(status)))
    assert volta.pendencias[0].material == "Válvula de retenção — Ø 50"
    assert volta.pendencias[0].documentos[0]["title"] == "Injeção"


def test_nao_salva_conferencia_vazia(tmp_path):
    """Arquivo sem link nenhum só serviria para confundir na hora de
    importar."""
    status = tmp_path / "_STATUS_PMIB.xlsx"
    status.write_text("x")
    assert conf.salvar_txt(conf.Conferencia(), str(status)) is None


# =============================================================================
# D. O .txt de ontem, a máquina de hoje
# =============================================================================
def test_ficha_que_nao_existe_mais_e_avisada(tmp_path):
    """O `.txt` pode ter sido gerado noutra máquina, ou a planilha pode ter
    sido movida. Descobrir isso ao importar é melhor do que descobrir com a
    2ª passada falhando ficha por ficha."""
    existe = tmp_path / "0071.xlsx"
    existe.write_text("x")
    c = conf.Conferencia()
    c.registrar(str(existe), documentos=[{"url": "https://x/1"}])
    c.registrar(str(tmp_path / "sumiu.xlsx"), documentos=[{"url": "https://x/2"}])
    ausentes = conf.fichas_ausentes(c)
    assert ausentes == [str(tmp_path / "sumiu.xlsx")]


def test_todas_as_fichas_no_lugar_nao_gera_aviso(tmp_path):
    ficha = tmp_path / "0071.xlsx"
    ficha.write_text("x")
    c = conf.Conferencia()
    c.registrar(str(ficha), documentos=[{"url": "https://x/1"}])
    assert conf.fichas_ausentes(c) == []


# =============================================================================
# E. Blindagem descoberta na verificação de ponta a ponta (2026-08-17)
# =============================================================================
def test_fabricante_em_STRING_nao_vira_lista_de_letras():
    """`_resultado_e_relevante` itera os termos. Recebendo `"WAGO"` em vez de
    `["WAGO"]`, iterava **as letras** — e como termo de 1 caractere não casa,
    o fabricante nunca era encontrado e TODO resultado virava `duvidoso`.

    Nenhum chamador de hoje passa string (`_tokens_ancora_fabricante` devolve
    lista), então isto é blindagem, não correção de bug vivo. Ele apareceu ao
    escrever o roteiro de ponta a ponta, onde eu mesmo passei a string —
    exatamente o erro que o próximo a escrever um roteiro vai repetir.
    """
    from sigft.services.autospec import classificar_resultado

    titulo = "WAGO 750-362 Fieldbus Coupler Modbus TCP"
    link = "https://www.wago.com/global/p/750-362"
    assert classificar_resultado(["WAGO"], ["750-362"], titulo, "", link) == "certo"
    assert classificar_resultado("WAGO", "750-362", titulo, "", link) == "certo"
