r"""
sigft/services/autorizados.py — o export de autorizados de Itaipu gravado nos
`_STATUS_PMIB`.

T4 do roteiro "Gestão PMIB no tratamento v2" (`gestao-sobressalentes/07 -
Diagnostico/Tarefa SIG-FT - Calculo e Gravacao sem Perda.md`). Porte de
`apto_para_entrega_att.py` (versão de 28/07/2026), que vivia no Box em
`15 - PDM/_python_pdm/SIG-FT/` com os caminhos FIXOS no código -- cópia de
referência em `gestao-sobressalentes/_gestao_v2/referencia_sigft/`.

O que ele faz
-------------
Itaipu manda a lista dos sobressalentes cuja entrega autorizou
(`sobressalentes_autorizados_AAAAMMDDhhmm.xlsx`, coluna `PMIB`). Para cada PMIB
dela, em cada `_STATUS_PMIB` vivo:

  - layout v2: SITUAÇÃO DA AUTORIZAÇÃO := AUTORIZADO (é FATO: vale para qualquer
    tipo de entrega) e, **se DIAS DE ATRASO estiver vazio**, o atraso que houve
    até a autorização (`autorizacao.dias_de_atraso_na_autorizacao`, com a data
    tirada do NOME do arquivo; vazio se veio no prazo);
  - layout antigo (sem a SITUAÇÃO): APTO PARA ENTREGA := SIM, como o script
    fazia.

O que mudou em relação ao script
--------------------------------
  - caminhos vêm da tela (Gestão PMIB), não do código;
  - as mesmas exclusões de pasta e cópia do Gestão PMIB
    (`status_pmib_arquivos`): o script também entrava em `testes_autospec/`;
  - grava pelo editor cirúrgico (`StatusPMIB`): o `wb.save` do script apagava
    os comentários em thread;
  - PMIB normalizado dos dois lados (`pmib_codes.normalize_pmib`): um PMIB que
    perdeu o zero do fim na planilha (`4500063671.901`) casa com o do export;
  - os PMIBs autorizados que não estão em NENHUM `_STATUS_PMIB` aparecem no log.
"""
from __future__ import annotations

import datetime as dt
import os
import re

from sigft import config
from sigft.core.excel import headers, pmib_codes, status_sheet
from sigft.services import autorizacao, status_pmib_arquivos

COLUNA_PMIB_DO_EXPORT = "PMIB"
# sobressalentes_autorizados_202607210948.xlsx -> 2026-07-21
_RE_DATA_NO_NOME = re.compile(r"AUTORIZADOS_(\d{4})(\d{2})(\d{2})\d{0,6}", re.IGNORECASE)


def data_do_export(caminho) -> dt.date | None:
    """A data do export, tirada do nome `sobressalentes_autorizados_AAAAMMDDhhmm`,
    ou `None` se o nome não a tiver."""
    m = _RE_DATA_NO_NOME.search(os.path.basename(str(caminho)))
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def ler_autorizados(caminho) -> set[str]:
    """Os PMIBs da coluna `PMIB` do export, normalizados. A coluna é achada
    pelo nome nas 10 primeiras linhas; sem ela, `ValueError` com a mensagem
    para a tela."""
    import openpyxl  # preguiçoso: a suíte troca pelo real só quando precisa

    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    try:
        ws = wb.worksheets[0]
        linhas = [list(linha) for linha in ws.iter_rows(values_only=True)]
    finally:
        wb.close()
    colunas, cabecalho = headers.find_columns(linhas[:10], {COLUNA_PMIB_DO_EXPORT: COLUNA_PMIB_DO_EXPORT})
    if cabecalho is None:
        raise ValueError(f"o export não tem a coluna '{COLUNA_PMIB_DO_EXPORT}' nas 10 primeiras linhas.")
    coluna = colunas[COLUNA_PMIB_DO_EXPORT] - 1
    pmibs = set()
    for linha in linhas[cabecalho:]:
        valor = linha[coluna] if coluna < len(linha) else None
        if autorizacao.normalizar(valor) in ("", "NAN", "NAT"):
            continue
        pmibs.add(pmib_codes.normalize_pmib(valor if isinstance(valor, (int, float)) else str(valor).strip()))
    return pmibs


def _aplicar_no_arquivo(caminho, pmibs, data_export, callback_retry_lock):
    """Generator: aplica as autorizações num `_STATUS_PMIB`. Devolve (`return`)
    `(estado, pmibs_achados)`; `estado` é 'atualizado', 'intacto' ou 'pulado'."""
    nome = os.path.basename(caminho)
    achados: set[str] = set()
    if not caminho.lower().endswith(".xlsx"):
        yield f"[AVISO] {nome}: formato antigo ({os.path.splitext(nome)[1]}), não é lido nem gravado."
        return "pulado", achados

    painel = status_sheet.StatusPMIB(caminho, config.ABA_LISTA_MATERIAIS)
    chaves = {c: c for c in (config.COL_CODIGO_PMIB, config.COL_SITUACAO_AUTORIZACAO, config.COL_DIAS_ATRASO,
                             config.COL_DATA_EMAIL_ENTREGA, config.COL_APTO_PARA_ENTREGA)}
    try:
        col_map, header_row = painel.abrir(keywords=chaves, required=[config.COL_CODIGO_PMIB], max_row=10,
                                           normalize=autorizacao.normalizar)
    except KeyError:
        yield f"[AVISO] {nome}: não tem a aba '{config.ABA_LISTA_MATERIAIS}'."
        return "pulado", achados
    except Exception as e:
        yield f"[AVISO] {nome}: não consegui abrir ({type(e).__name__}: {e})."
        return "pulado", achados

    try:
        if header_row is None:
            yield f"[AVISO] {nome}: cabeçalho com '{config.COL_CODIGO_PMIB}' não encontrado."
            return "pulado", achados
        v2 = config.COL_SITUACAO_AUTORIZACAO in col_map
        if not v2 and config.COL_APTO_PARA_ENTREGA not in col_map:
            yield (f"[AVISO] {nome}: sem '{config.COL_SITUACAO_AUTORIZACAO}' nem "
                   f"'{config.COL_APTO_PARA_ENTREGA}': fora do template, nada gravado.")
            return "pulado", achados
        if v2 and config.COL_DIAS_ATRASO not in col_map:
            yield f"[AVISO] {nome}: layout v2 sem '{config.COL_DIAS_ATRASO}': nada gravado."
            return "pulado", achados

        ws = painel.ws
        for r in range(header_row + 1, ws.max_row + 1):
            valor = ws.cell(row=r, column=col_map[config.COL_CODIGO_PMIB]).value
            if valor in (None, ""):
                continue
            pmib = pmib_codes.normalize_pmib(valor)
            if pmib not in pmibs:
                continue
            achados.add(pmib)
            if not v2:
                coluna_apto = col_map[config.COL_APTO_PARA_ENTREGA]
                if autorizacao.normalizar(ws.cell(row=r, column=coluna_apto).value) != "SIM":
                    painel.escrever(r, coluna_apto, "SIM")
                continue
            coluna_sit = col_map[config.COL_SITUACAO_AUTORIZACAO]
            if autorizacao.normalizar(ws.cell(row=r, column=coluna_sit).value) != autorizacao.AUTORIZADO:
                painel.escrever(r, coluna_sit, autorizacao.AUTORIZADO)
            coluna_dias = col_map[config.COL_DIAS_ATRASO]
            if data_export is not None and autorizacao.dias_da_celula(ws.cell(row=r, column=coluna_dias).value) is None:
                email = (ws.cell(row=r, column=col_map[config.COL_DATA_EMAIL_ENTREGA]).value
                         if config.COL_DATA_EMAIL_ENTREGA in col_map else None)
                dias = autorizacao.dias_de_atraso_na_autorizacao(email, data_export)
                if dias is not None:
                    painel.escrever(r, coluna_dias, dias, formato_geral=True)

        escritas = len(painel.escritas_pendentes)
        if not escritas:
            return "intacto", achados

        def _perguntar(_tentativa, _erro):
            return bool(callback_retry_lock(caminho)) if callback_retry_lock else False

        try:
            painel.salvar(on_locked=_perguntar)
        except PermissionError:
            yield f"[AVISO] {nome} está aberto no Excel: as autorizações dele NÃO foram gravadas. Feche e rode de novo."
            return "pulado", achados
        except Exception as e:
            yield f"[AVISO] {nome}: falha ao gravar ({type(e).__name__}: {e}). Nada gravado."
            return "pulado", achados
        campo = config.COL_SITUACAO_AUTORIZACAO if v2 else config.COL_APTO_PARA_ENTREGA
        yield f" -> [ATUALIZADO] {nome}: {escritas} célula(s) ({campo}{' e dias de atraso' if v2 else ''})."
        return "atualizado", achados
    finally:
        painel.fechar()


def executar(caminho_export, pasta_raiz, *, data_export=None, callback_retry_lock=None):
    """Aplica o export de autorizados em todos os `_STATUS_PMIB` vivos da pasta.

    Generator de linhas de log (mesmo contrato das outras telas). `data_export`
    sobrepõe a data tirada do nome do arquivo; sem nenhuma das duas, autoriza
    mas não calcula o atraso (e diz isso). `callback_retry_lock(caminho)`:
    arquivo aberto no Excel -- `True` tenta de novo, `False` pula o arquivo.
    """
    yield f"Lendo o export de autorizados: {os.path.basename(str(caminho_export))}"
    try:
        pmibs = ler_autorizados(caminho_export)
    except Exception as e:
        yield f"[ERRO] Não consegui ler o export de autorizados: {e}"
        return
    yield f" -> {len(pmibs)} PMIB(s) autorizado(s) no export."
    if not pmibs:
        return

    data_export = data_export or data_do_export(caminho_export)
    if data_export is None:
        yield ("[AVISO] Não achei a data no nome do export (sobressalentes_autorizados_AAAAMMDDhhmm.xlsx): "
               "as linhas viram AUTORIZADO, mas os dias de atraso não são calculados.")
    else:
        yield f" -> Data do export: {data_export.strftime('%d/%m/%Y')}."

    levantamento = status_pmib_arquivos.listar(pasta_raiz)
    for caminho, motivo in levantamento.ignorados:
        yield f" -> Ignorado ({motivo}): {os.path.relpath(caminho, pasta_raiz)}"
    for codigo, escolhido, descartados in levantamento.repetidos:
        yield (f"[AVISO] Mais de um _STATUS_PMIB vivo para {codigo}: usando "
               f"{os.path.relpath(escolhido, pasta_raiz)}; ignorado(s): "
               + ", ".join(os.path.relpath(d, pasta_raiz) for d in descartados))

    contagem = {"atualizado": 0, "intacto": 0, "pulado": 0}
    encontrados: set[str] = set()
    for _codigo, caminho in levantamento.vivos:
        estado, achados = yield from _aplicar_no_arquivo(caminho, pmibs, data_export, callback_retry_lock)
        contagem[estado] += 1
        encontrados |= achados

    faltam = sorted(pmibs - encontrados)
    yield (f" -> Resumo: {contagem['atualizado']} _STATUS_PMIB atualizado(s), {contagem['intacto']} já em dia, "
           f"{contagem['pulado']} não gravado(s).")
    if faltam:
        yield (f"[AVISO] {len(faltam)} PMIB(s) do export não estão em nenhum _STATUS_PMIB vivo: "
               + ", ".join(faltam[:20]) + ("..." if len(faltam) > 20 else ""))
