"""A leitura do mural de atividades: a aba "Atividades" do mapeamento.

[2026-10-10] Morava nas duas Homes (`sigft/app/views/home.py`, CustomTkinter,
e `sigft/app_qt/views/home.py`, Qt), copiada linha a linha. É regra de dados --
achar o arquivo, abrir a planilha, mapear as colunas -- e não desenho: as duas
interfaces DELEGAM para cá (`HomeView._ler_mural` e
`HomeView._caminho_do_mapeamento`), e a regra se prova sem janela
(`tests/test_mural_atividades.py`).

Fica fora de `services/atividades.py` de propósito: aquele módulo é a regra
pura (faixas, prazos, totais) e não lê planilha nenhuma
(`test_o_modulo_nao_depende_de_excel`). Este o usa para classificar.
`openpyxl` e `prefs` entram dentro das funções: importar este módulo não custa
nada a quem só abre o app.
"""
from __future__ import annotations

from sigft.services import atividades as at


def caminho_do_mapeamento():
    """O último arquivo gerenciadora que o usuário escolheu, se existir."""
    import os

    from sigft.core import prefs

    # 1. O arquivo que o PMIB Manager registrou ao ser usado.
    try:
        salvo = prefs.get_last_file(prefs.CHAVE_MAPEAMENTO)
    except Exception:
        salvo = None
    if salvo:
        return salvo

    # 2. Reserva: a PASTA lembrada do seletor, procurando o arquivo nela.
    #    Cobre quem já usou o PMIB Manager ANTES de o arquivo ser guardado,
    #    quando só a pasta era.
    try:
        pasta = prefs.get_initial_dir("pmib_manager.master", "excel")
    except Exception:
        pasta = None
    if pasta and os.path.isdir(pasta):
        for nome in sorted(os.listdir(pasta)):
            if "mapeamento" in nome.lower() and nome.lower().endswith((".xlsx", ".xlsm")):
                return os.path.join(pasta, nome)
    return None


def ler_mural_do_mapeamento(caminho, hoje):
    """`(gavetas, erro)` -- lê a aba Atividades do mapeamento em `caminho` e
    classifica as atividades para o dia `hoje` (`atividades.mural`).

    Devolve o erro como TEXTO em vez de levantar: o mural é informativo, e
    uma planilha ausente não pode virar traceback na cara do usuário.
    """
    # As gavetas saem de `at.FAIXAS`, NUNCA de uma lista escrita aqui. A
    # primeira versão listava as faixas à mão; quando o mural passou a ser por
    # PRAZO os nomes mudaram no serviço e a lista ficou para trás, com
    # `at.PARA_COMECAR` e `at.TRAVADA` inexistentes. O AttributeError subia
    # antes do try e o botão simplesmente não abria janela nenhuma. Derivando
    # de `FAIXAS` os dois lados não têm como divergir de novo.
    vazio = {faixa: [] for faixa in at.FAIXAS}

    if not caminho:
        return vazio, (
            "Nao encontrei o arquivo de mapeamento.\n\n"
            "Rode o PMIB Manager uma vez apontando a planilha gerenciadora -- "
            "o mural passa a ler dela."
        )

    try:
        import openpyxl

        # `data_only=True` é obrigatório: as células de agregação da aba são
        # fórmulas, e sem isto `.value` devolveria a string "=FALSE()" em vez
        # do valor. Foi um defeito real nesta mesma frente.
        wb = openpyxl.load_workbook(caminho, data_only=True, read_only=True)
        if "Atividades" not in wb.sheetnames:
            wb.close()
            return vazio, "A planilha nao tem a aba 'Atividades'.\n\n" + str(caminho)

        ws = wb["Atividades"]

        # ⚠️ `iter_rows`, NUNCA `ws.cell(...)` numa planilha `read_only`.
        #
        # Em modo read-only a aba é um FLUXO só-para-frente: cada
        # `ws.cell(linha, coluna)` re-percorre o XML desde o começo. Eram 84
        # linhas x 10 colunas = 840 varreduras, e o mural levava 3,9 s para
        # abrir num arquivo de 40 KB. `iter_rows` passa uma vez só: caiu para
        # centésimos de segundo.
        def _celula(valores, coluna):
            indice = coluna - 1
            return valores[indice] if indice < len(valores) else None

        linhas = []
        for valores in ws.iter_rows(min_row=at.LINHA_CABECALHO + 1, values_only=True):
            linhas.append({
                "nv": _celula(valores, at.COL_NV),
                "descricao": _celula(valores, at.COL_DESCRICAO),
                "concluida": _celula(valores, at.COL_CONCLUIDA),
                "status": _celula(valores, at.COL_STATUS),
                "com_quem": _celula(valores, at.COL_COM_QUEM),
                "criticidade": _celula(valores, at.COL_CRITICIDADE),
                "data_prevista_inicio": _celula(valores, at.COL_DATA_PREVISTA_INICIO) or "",
                "previsao_termino": _celula(valores, at.COL_PREVISAO_TERMINO) or "",
                # As datas REAIS. Antes iam como "" fixo, e a regra que decide
                # "já começou" ficava cega: atividade com DATA DE INÍCIO
                # preenchida aparecia como "era para começar há N dias".
                "data_inicio": _celula(valores, at.COL_DATA_INICIO) or "",
                "data_termino": _celula(valores, at.COL_DATA_TERMINO) or "",
            })
        wb.close()
        return at.mural(linhas, hoje), None
    except Exception as e:
        return vazio, "Nao consegui ler as atividades:\n{}: {}\n\n{}".format(
            type(e).__name__, e, caminho)
