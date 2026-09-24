r"""Regenerar as pastas de PDMs a partir da planilha, com a revisão no nome.

Pedido do usuário em 2026-09-23 (D5 do spec): as pastas *PDMs From Itaipu* e
*PDMs Modificados* nasciam dos passos antigos "Fatiar" e "Formatar", que PULAM
o que já existe: revisado um PDM, o arquivo velho ficava. Este módulo refaz as
duas a partir da planilha, com a revisão do PDM no nome
(`PDM_1650_001 - ACUMULADOR - R2_formatado.xlsx`), e manda a versão antiga de
cada PDM para a subpasta `_versoes_antigas`: nada é apagado.

A pasta From Itaipu é fatiada lendo a planilha UMA vez. O "Fatiar" antigo relê
a planilha inteira a cada código (7,1 s cada na planilha de 23/09/2026, umas
2,4 horas para os 1.199), porque cada volta mutila o workbook que abriu: é a
otimização que o CP 4.3 deixou registrada em PENDENCIAS.md.

Desenho: seção 6 de
docs/superpowers/specs/2026-09-23-planilhas-pmib-da-planilha-design.md.
"""
from __future__ import annotations

import os
import re
import shutil
from copy import copy
from types import SimpleNamespace

from sigft.core import pdm_catalogo
from sigft.core.callbacks import from_legacy
from sigft.core.excel import locking
from sigft.core.relatorio_lote import RelatorioLote
from sigft.services import pdm, pdm_planilha

PASTA_VERSOES_ANTIGAS = "_versoes_antigas"
SUFIXO_FORMATADO = "_formatado"

# As linhas 1 a 6 da aba TEMPLATE_PDM: título, "Exportado el:", o cabeçalho de
# layout e o cabeçalho de verdade (linha 6). Os dados começam na 7.
_LINHAS_DO_CABECALHO = 6

_EXTENSOES = (".xlsx", ".xlsm", ".xls")

# "A6:X21323" -> "A6:X" + a última linha da fatia.
_RE_FIM_DO_INTERVALO = re.compile(r"^([A-Z]+\d+:[A-Z]+)\d+$")


def regenerar_pastas(caminho_planilha, pasta_modificados, pasta_from_itaipu=None,
                     log_callback=None, retry_lock=None):
    """Regenera a pasta Modificados e, se informada, a From Itaipu.

    Levanta `ValueError` ANTES de tocar em qualquer arquivo quando a entrada
    não serve: pasta faltando, as duas pastas iguais, planilha ilegível ou no
    formato antigo. Devolve o resumo, uma linha por pasta."""
    if not pasta_modificados:
        raise ValueError("Selecione a 'Pasta dos PDMs Modificados'.")
    if pasta_from_itaipu and _mesma_pasta(pasta_modificados, pasta_from_itaipu):
        raise ValueError(
            "A 'Pasta (PDMs From Itaipu)' e a 'Pasta dos PDMs Modificados' nao "
            "podem ser a mesma: a busca de versoes antigas moveria os arquivos de "
            "uma para a outra."
        )
    try:
        catalogo = pdm_catalogo.carregar(caminho_planilha)
        pdm_planilha.conferir_catalogo(catalogo)
    except Exception as e:
        raise ValueError(f"Nao consegui usar a planilha de PDMs: {e}") from e

    callbacks = from_legacy(callback_log=log_callback)
    callbacks.log(pdm_planilha.descrever_catalogo(catalogo), nivel="info")
    pdms = sorted(catalogo.pdms, key=lambda p: p.codigo)

    resumo = [_regenerar_pasta(
        pasta_modificados, pdms, SUFIXO_FORMATADO, "PDMs Modificados",
        lambda p, caminho: _gravar_formatado(p, caminho, retry_lock),
        callbacks, retry_lock, avisar_identidades=True,
    )]
    if not pasta_from_itaipu:
        resumo.append("PDMs From Itaipu: pasta nao informada, nao foi regenerada.")
        return "\n".join(resumo)

    from openpyxl import load_workbook

    callbacks.log("Lendo a planilha com a formatacao, para a pasta From Itaipu...", nivel="info")
    wb_mestra = load_workbook(caminho_planilha)
    try:
        ws_mestra = wb_mestra["TEMPLATE_PDM"]
        # Uma varredura só, aqui. Ver `_copiar_linha`.
        ultima_coluna = ws_mestra.max_column
        copiador = _CopiadorDeEstilo()
        resumo.append(_regenerar_pasta(
            pasta_from_itaipu, pdms, "", "PDMs From Itaipu",
            lambda p, caminho: _gravar_fatia(p, caminho, ws_mestra, retry_lock,
                                             ultima_coluna=ultima_coluna,
                                             copiador=copiador),
            callbacks, retry_lock, avisar_identidades=False,
        ))
    finally:
        wb_mestra.close()
    return "\n".join(resumo)


def _mesma_pasta(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _regenerar_pasta(pasta, pdms, sufixo, rotulo, gravar, callbacks, retry_lock, *,
                     avisar_identidades):
    os.makedirs(pasta, exist_ok=True)
    indice = _indexar(pasta, formatado=bool(sufixo))
    novos = atualizados = em_dia = 0
    with RelatorioLote(callbacks, titulo=f"Regenerando {rotulo} a partir da planilha",
                       total=len(pdms), contexto={"pasta": pasta}) as lote:
        for p in pdms:
            if not p.caracteristicas_em_ordem:
                lote.pulado(p.codigo, "sem caracteristica na planilha")
                continue
            if avisar_identidades:
                outras = pdm_planilha.outras_identidades(p)
                if outras:
                    lote.aviso(p.codigo,
                               f"a planilha traz tambem {pdm_planilha.descrever_identidades(outras)}",
                               f"ficou de fora, valeu {p.titulo} (R{p.revisao}); confira com a Itaipu")
            nome_novo = pdm_planilha.nome_de_arquivo(p, sufixo=sufixo)
            id_pdm = p.codigo.replace(".", "_")
            existentes = indice.get(id_pdm, [])
            antigos = [n for n in existentes if n != nome_novo]
            try:
                for nome in antigos:
                    _mover_para_versoes_antigas(pasta, nome, retry_lock)
                if nome_novo in existentes:
                    indice[id_pdm] = [nome_novo]
                    if antigos:
                        atualizados += 1
                        lote.sucesso(p.codigo, f"ja estava na R{p.revisao}; "
                                               f"{len(antigos)} versao(oes) antiga(s) movida(s)")
                    else:
                        em_dia += 1
                        lote.sucesso(p.codigo, f"ja em dia (R{p.revisao})")
                    continue
                gravar(p, os.path.join(pasta, nome_novo))
                indice[id_pdm] = [nome_novo]
                if antigos:
                    atualizados += 1
                    lote.sucesso(p.codigo, f"atualizado: {_de_onde(antigos)} -> R{p.revisao}")
                else:
                    novos += 1
                    lote.sucesso(p.codigo, f"novo: {nome_novo}")
            except Exception as e:
                lote.falha(p.codigo, f"{type(e).__name__}: {e}")
    return (f"{rotulo}: {novos} novo(s), {atualizados} atualizado(s), {em_dia} ja em dia, "
            f"{len(lote.falhas)} falha(s). Versoes antigas em "
            f"{os.path.join(pasta, PASTA_VERSOES_ANTIGAS)}")


def _indexar(pasta, *, formatado):
    """`{"PDM_1650_001": [nomes...]}` dos arquivos DESTE tipo na pasta: com
    `_formatado` na Modificados, sem ele na From Itaipu. Uma listagem por
    pasta, e não uma por PDM: a pasta mora no Box, e 1.199 listagens
    custariam caro."""
    indice = {}
    for nome in sorted(os.listdir(pasta)):
        if nome.startswith("~$") or not nome.lower().endswith(_EXTENSOES):
            continue
        if not os.path.isfile(os.path.join(pasta, nome)):
            continue
        if (SUFIXO_FORMATADO in nome) != formatado:
            continue
        id_pdm = pdm.extrair_pdm_id(nome)
        if id_pdm:
            indice.setdefault(id_pdm, []).append(nome)
    return indice


def _de_onde(nomes):
    """`"R1"`, `"sem revisao no nome"`, ou os dois: o que foi substituído."""
    revisoes = sorted({pdm_planilha.revisao_no_nome(n) for n in nomes},
                      key=lambda r: -1 if r is None else r)
    return ", ".join("sem revisao no nome" if r is None else f"R{r}" for r in revisoes)


def _mover_para_versoes_antigas(pasta, nome, retry_lock):
    """Move `nome` para `<pasta>/_versoes_antigas`, sem sobrescrever nada lá.

    Usa o canal `retry_lock` do `locking` (o `save_with_retry` só precisa de
    um objeto com `.save(caminho)`): arquivo aberto no Excel faz a janela
    "feche e tente de novo" aparecer, como em qualquer gravação do app. Se o
    usuário desistir, o `PermissionError` sobe e o PDM vira falha SEM o
    arquivo novo: a pasta não fica com duas versões."""
    origem = os.path.join(pasta, nome)
    destino_dir = os.path.join(pasta, PASTA_VERSOES_ANTIGAS)
    os.makedirs(destino_dir, exist_ok=True)
    destino = _nome_livre(os.path.join(destino_dir, nome))
    movedor = SimpleNamespace(save=lambda _caminho: shutil.move(origem, destino))
    locking.salvar_perguntando(movedor, origem, retry_lock=retry_lock)


def _nome_livre(caminho):
    """`caminho`, ou `caminho` com " (2)", " (3)"... antes da extensão."""
    if not os.path.exists(caminho):
        return caminho
    raiz, extensao = os.path.splitext(caminho)
    numero = 2
    while os.path.exists(f"{raiz} ({numero}){extensao}"):
        numero += 1
    return f"{raiz} ({numero}){extensao}"


def _gravar_formatado(p, caminho, retry_lock):
    """O PDM formatado: a mesma tabela do passo "Formatar"
    (`pdm.formatar_tabela_de_perguntas`), com as perguntas da planilha."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    # O nome que o `to_excel` do pandas dava à aba no passo antigo. Ninguém lê
    # a aba pelo nome (é sempre `wb.active`); o arquivo só fica igual ao de
    # sempre.
    ws.title = "Sheet1"
    linhas = [(pdm_planilha.montar_pergunta(numero, c.nome, c.ajuda), "")
              for numero, c in enumerate(p.caracteristicas_em_ordem, start=1)]
    pdm.formatar_tabela_de_perguntas(ws, linhas)
    locking.salvar_perguntando(wb, caminho, retry_lock=retry_lock)
    wb.close()


def _gravar_fatia(p, caminho, ws_mestra, retry_lock, *, ultima_coluna, copiador):
    """O PDM no formato da planilha (aba TEMPLATE_PDM): as 6 linhas do
    cabeçalho e as da revisão vigente, na ordem da SECUENCIA. É a mesma ordem
    das perguntas, para o passo antigo "Formatar" sobre este arquivo dar o
    mesmo PDM formatado que a regeneração grava."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "TEMPLATE_PDM"
    copiador.novo_destino()
    origens = (list(range(1, _LINHAS_DO_CABECALHO + 1))
               + [c.linha for c in p.caracteristicas_em_ordem])
    for destino, origem in enumerate(origens, start=1):
        _copiar_linha(ws_mestra, origem, ws, destino, ultima_coluna, copiador)
    _copiar_formato_da_aba(ws_mestra, ws, ultima_linha=len(origens))
    locking.salvar_perguntando(wb, caminho, retry_lock=retry_lock)
    wb.close()


class _CopiadorDeEstilo:
    """Copia o estilo das células da planilha para os workbooks novos da
    regeneração, sem refazer o trabalho a cada célula.

    Medido na planilha real (2026-09-24): o `copy()` de estilo do openpyxl faz
    ida e volta em XML (`to_tree` + `from_tree`), e atribuir o estilo à célula
    compara por hash com os que o workbook já tem. Célula a célula, como o
    "Fatiar" antigo fazia, eram 830 ms por PDM, uns 16 minutos para os 1.199.
    A planilha tem 18 estilos distintos: copiando cada um UMA vez por
    regeneração, e reaproveitando dentro de cada arquivo o estilo já montado,
    são 18 ms por PDM, com o mesmo resultado célula a célula."""

    def __init__(self):
        # estilo de origem -> (fonte, borda, preenchimento, formato, alinhamento)
        self._copiados = {}
        # estilo de origem -> o `_style` já montado no workbook de DESTINO atual
        self._no_destino = {}

    def novo_destino(self):
        """Um workbook novo tem as próprias tabelas de estilo: o que foi
        montado no anterior não vale nele."""
        self._no_destino = {}

    def aplicar(self, origem, destino):
        chave = tuple(origem._style)
        montado = self._no_destino.get(chave)
        if montado is not None:
            # O jeito do próprio openpyxl de copiar estilo DENTRO de um
            # workbook (é o que o `WorksheetCopy` dele faz): os índices do
            # `_style` apontam para as tabelas deste workbook.
            destino._style = type(montado)(montado)
            return
        objetos = self._copiados.get(chave)
        if objetos is None:
            objetos = (copy(origem.font), copy(origem.border), copy(origem.fill),
                       origem.number_format, copy(origem.alignment))
            self._copiados[chave] = objetos
        (destino.font, destino.border, destino.fill,
         destino.number_format, destino.alignment) = objetos
        self._no_destino[chave] = type(destino._style)(destino._style)


def _copiar_linha(ws_origem, linha_origem, ws_destino, linha_destino, ultima_coluna, copiador):
    # A mesma cópia de estilo do "Fatiar" antigo (`pdm.pdms_fromItaipu_lista_geral`).
    #
    # `iter_rows` com os DOIS limites, e não `ws[linha]`: para responder
    # `ws[linha]` o openpyxl calcula `max_column` varrendo TODAS as células da
    # aba -- ~530 mil na planilha real, a cada linha copiada. Medido em
    # 2026-09-24: 3,5 s por PDM, uns 70 minutos para os 1.199.
    linha, = ws_origem.iter_rows(min_row=linha_origem, max_row=linha_origem,
                                 max_col=ultima_coluna)
    for celula in linha:
        if celula.value is None and not celula.has_style:
            continue
        nova = ws_destino.cell(row=linha_destino, column=celula.column, value=celula.value)
        if celula.has_style:
            copiador.aplicar(celula, nova)
    altura = ws_origem.row_dimensions[linha_origem].height
    if altura is not None:
        ws_destino.row_dimensions[linha_destino].height = altura


def _copiar_formato_da_aba(ws_origem, ws_destino, *, ultima_linha):
    for letra, dimensao in ws_origem.column_dimensions.items():
        if dimensao.width:
            ws_destino.column_dimensions[letra].width = dimensao.width
    # `merge_cells` depois das células escritas: comparado com o "Fatiar"
    # antigo no cabeçalho real (2026-09-24), 0 célula diferente.
    for intervalo in ws_origem.merged_cells.ranges:
        if intervalo.max_row <= _LINHAS_DO_CABECALHO:
            ws_destino.merge_cells(intervalo.coord)
    if ws_origem.freeze_panes:
        ws_destino.freeze_panes = ws_origem.freeze_panes
    filtro = _RE_FIM_DO_INTERVALO.match(ws_origem.auto_filter.ref or "")
    if filtro:
        ws_destino.auto_filter.ref = f"{filtro.group(1)}{ultima_linha}"
