"""O pedido de cada lista para o AMP: os arquivos como estão na pasta e a mensagem que o SIG-FT
monta sozinho, e quais listas têm o que precisa. O SIG-FT não lê mais o conteúdo dos arquivos.
Desenho: `docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`, §5.2.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from sigft.services import conferencia_revisoes as cr
from sigft.services import revisao_amp as ra

CODIGO = "#ITA0=Y01TF001&BPB020"
HOJE = date(2026, 11, 3)


def _lista(codigo=CODIGO, ultima="0B", em_uso="0A", status_real="Aprovado"):
    return cr.ListaNaMapeadora(codigo, ultima, "Em Processo", status_real, em_uso,
                               f"Lista {codigo[-3:]}/{codigo}_STATUS_PMIB.xlsx")


def _pasta(raiz: Path, codigo=CODIGO, pdfs=(), com_status=True) -> Path:
    pasta = raiz / f"Lista {codigo[-3:]}"
    pasta.mkdir(parents=True, exist_ok=True)
    if com_status:
        (pasta / f"{codigo}_STATUS_PMIB.xlsx").write_bytes(b"planilha")
    for revisao in pdfs:
        (pasta / cr.nome_do_pdf(codigo, revisao)).write_bytes(b"%PDF")
    return pasta


def _conferencia(*itens):
    return cr.Conferencia(list(itens), em_dia=0, sem_status_pmib=0)


def _uma_lista(tmp_path, *, em_uso="0A", ultima="0B"):
    pasta = _pasta(tmp_path, pdfs=(em_uso, ultima) if em_uso else (ultima,))
    item = cr.ItemConferencia(_lista(ultima=ultima, em_uso=em_uso), "aprovada", pasta)
    [lista] = ra.listas_para_amp(_conferencia(item), [], tmp_path, None)
    return lista


# ------------------------------------------------------------------ quais listas vão

def test_listas_usam_os_pdfs_baixados_na_sessao(tmp_path):
    pasta = _pasta(tmp_path, pdfs=("0A",))
    baixado = pasta / cr.nome_do_pdf(CODIGO, "0C")
    baixado.write_bytes(b"%PDF")
    downloads = [cr.Download(CODIGO, "0C", baixado, "baixado", "mapeadora desatualizada: o Aconex está na 0C"),
                 cr.Download(CODIGO, "0A", pasta / cr.nome_do_pdf(CODIGO, "0A"), "ja_existia")]
    [lista] = ra.listas_para_amp(_conferencia(cr.ItemConferencia(_lista(), "aprovada", pasta)),
                                 downloads, tmp_path, None)
    assert (lista.revisao_atual, lista.pdf_atual, lista.falta) == ("0C", baixado, "")
    assert lista.pdf_em_uso == pasta / cr.nome_do_pdf(CODIGO, "0A")
    assert lista.status_pmib == pasta / f"{CODIGO}_STATUS_PMIB.xlsx"


def test_listas_sem_download_procuram_pelo_nome(tmp_path):
    pasta = _pasta(tmp_path, pdfs=("0A", "0B"))
    [lista] = ra.listas_para_amp(_conferencia(cr.ItemConferencia(_lista(), "aprovada", pasta)), [], tmp_path, None)
    assert (lista.revisao_atual, lista.pdf_atual.name, lista.pdf_em_uso.name, lista.falta) == (
        "0B", cr.nome_do_pdf(CODIGO, "0B"), cr.nome_do_pdf(CODIGO, "0A"), "")


def test_lista_sem_revisao_em_uso_nao_exige_esse_pdf(tmp_path):
    lista = _uma_lista(tmp_path, em_uso="", ultima="0")
    assert (lista.pdf_em_uso, lista.falta) == (None, "")


def test_o_que_falta_aparece_e_a_ordem_e_a_das_categorias(tmp_path):
    outro = "#ST00=X01MPB020&MPB020"
    pasta_ok = _pasta(tmp_path, outro, pdfs=("0A", "0B"))
    pasta_sem = _pasta(tmp_path, pdfs=("0A",))
    pasta_sem_status = _pasta(tmp_path / "s", "#ZZ00=1&MPB020", pdfs=("0A", "0B"), com_status=False)
    listas = ra.listas_para_amp(_conferencia(
        cr.ItemConferencia(_lista(outro, status_real="Em Processo"), "em_processo", pasta_ok),
        cr.ItemConferencia(_lista(), "aprovada", pasta_sem),
        cr.ItemConferencia(_lista("#ZZ00=1&MPB020"), "outros", pasta_sem_status)), [], tmp_path, None)
    assert [(lst.item.lista.codigo, lst.falta) for lst in listas] == [
        (CODIGO, "falta: PDF da revisão atual"),
        (outro, ""),
        ("#ZZ00=1&MPB020", "falta: _STATUS_PMIB"),
    ]


def test_lista_sem_pasta_fica_de_fora(tmp_path):
    item = cr.ItemConferencia(_lista(), "outros", None, cr.MOTIVO_SEM_PASTA)
    assert ra.listas_para_amp(_conferencia(item), [], tmp_path, None) == []


# ------------------------------------------------------------------ a mensagem e o pedido

def test_mensagem_tem_a_lista_as_revisoes_os_arquivos_e_a_data(tmp_path):
    lista = _uma_lista(tmp_path)
    assert ra.mensagem_da_lista(lista, hoje=HOJE) == (
        f"Lista: {CODIGO}. Revisão em uso: 0A (arquivo {cr.nome_do_pdf(CODIGO, '0A')}). "
        f"Revisão atual: 0B (arquivo {cr.nome_do_pdf(CODIGO, '0B')}). "
        f"Controle: {CODIGO}_STATUS_PMIB.xlsx. Data de hoje: 03/11/2026. Faça a revisão.")


def test_mensagem_sem_revisao_em_uso(tmp_path):
    mensagem = ra.mensagem_da_lista(_uma_lista(tmp_path, em_uso="", ultima="0"), hoje=HOJE)
    assert ("Revisão em uso: nenhuma (a lista ainda não tem revisão em uso: compare só a revisão atual "
            "com o controle).") in mensagem
    assert f"Revisão atual: 0 (arquivo {cr.nome_do_pdf(CODIGO, '0')})." in mensagem


def test_pedido_leva_os_arquivos_como_estao_e_a_mensagem(tmp_path):
    lista = _uma_lista(tmp_path)
    pedido = ra.montar_pedido(lista, hoje=HOJE)
    assert pedido.campos == {"modo": "revisar", "mensagem": ra.mensagem_da_lista(lista, hoje=HOJE)}
    assert pedido.arquivos == {"revisao_em_uso": lista.pdf_em_uso, "revisao_atual": lista.pdf_atual,
                               "status_pmib": lista.status_pmib}
    assert list(pedido.arquivos) == ["revisao_em_uso", "revisao_atual", "status_pmib"]


def test_pedido_sem_revisao_em_uso_vai_com_dois_arquivos(tmp_path):
    pedido = ra.montar_pedido(_uma_lista(tmp_path, em_uso="", ultima="0"), hoje=HOJE)
    assert list(pedido.arquivos) == ["revisao_atual", "status_pmib"]


def test_o_sigft_nao_le_mais_o_conteudo():
    for nome in ("texto_do_pdf", "status_pmib_em_tsv", "TextoPdf", "TabelaStatus", "codigos_para_eco"):
        assert not hasattr(ra, nome), nome
