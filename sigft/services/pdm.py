"""Planilhas PMIB: as fichas montadas a partir da planilha de PDMs (SAM-GM).

O que sobrou do antigo "Gerenciador de PDMs" (2026-10-21, pedido do Luan): a
tela fica só com a planilha de PDMs e a criação das planilhas PMIB. Sairam o
fatiamento da lista geral (From Itaipu), os PDMs Modificados (formatar,
regenerar, traduzir a pasta) e a exclusao de duplicados de pasta; as perguntas
de cada ficha vem sempre da planilha (`aplicar_templates_fichas_da_planilha`).
"""
import os
from dataclasses import dataclass, field
# CP 4.3: o template e lido do disco uma vez; cada ficha reabre de `BytesIO`.
from io import BytesIO

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Border, Side, Alignment, Font

from sigft import config
from sigft.core.excel import headers, pmib_codes
# CP 4.4: padrao unico de log de lote; `from_legacy` adapta o `log_callback`
# de assinatura antiga para `UICallbacks` sem mudar a assinatura publica.
from sigft.core.callbacks import from_legacy
from sigft.core.relatorio_lote import RelatorioLote
from sigft.core.excel import locking
# 2026-09-24: as regras da ficha montada pela planilha de PDMs.
from sigft.services import pdm_planilha


# =============================================================================
# LÓGICA CRIAÇÃO DE FICHAS (PMIB)
# =============================================================================
# Até onde procurar o cabeçalho do `_STATUS_PMIB`: o mesmo alcance que
# `duplicadas` usa para o mesmo arquivo.
LINHAS_BUSCA_CABECALHO = 30


def ler_lista_materiais(arquivo_status_pmib):
    """A aba "Lista de Materiais" do `_STATUS_PMIB`, com o cabeçalho ACHADO.

    [2026-10-05, T0 do roteiro do Gestão PMIB v2] Lia com `skiprows=3`, o
    cabeçalho fixo na linha 4. No layout v2 (04/10/2026) a linha 4 é a da
    revisão em uso e o cabeçalho está na 5: a frase da revisão virava o nome
    da primeira coluna e nenhuma coluna era encontrada. A busca acha a linha
    nos dois layouts; `config.LINHA_STATUS_PMIB` só vale se ela não achar.
    """
    previa = pd.read_excel(arquivo_status_pmib, sheet_name=config.ABA_LISTA_MATERIAIS,
                           header=None, nrows=LINHAS_BUSCA_CABECALHO)
    linha_cabecalho = headers.find_header_row(previa.values.tolist(), [config.COL_CODIGO_PMIB])
    if linha_cabecalho is None:
        linha_cabecalho = config.LINHA_STATUS_PMIB - 1
    return pd.read_excel(arquivo_status_pmib, sheet_name=config.ABA_LISTA_MATERIAIS,
                         header=linha_cabecalho)


def codigos_pmib_da_lista(arquivo_status_pmib):
    """Os códigos PMIB do `_STATUS_PMIB`, normalizados, sem repetição e em
    ordem -- o que a tela do PDM mostra no modo "selecionar códigos".

    Levanta `ValueError` se a planilha não tiver a coluna, para a tela dizer
    isso em vez de abrir uma janela de seleção vazia.
    """
    df = ler_lista_materiais(arquivo_status_pmib)
    coluna = next((c for c in df.columns if config.COL_CODIGO_PMIB in str(c)), None)
    if coluna is None:
        raise ValueError(f"Coluna '{config.COL_CODIGO_PMIB}' não encontrada.")
    # CP 1.2: normalização única e canônica (core.excel.pmib_codes). O
    # `str(c).strip()` antes garante que ela sempre veja uma string, como o
    # código que morava na tela fazia.
    return sorted({pmib_codes.normalize_pmib(str(c).strip()) for c in df[coluna].dropna().unique()})


def processar_pastas_fichas(arquivo_STATUS_PMIB, destino_fichas, lista_selecionados=None, criar_subpastas=True):
    """Cria a estrutura de pastas (ou apenas lista os caminhos) baseada no Excel STATUS_PMIB"""
    try:
        df = ler_lista_materiais(arquivo_STATUS_PMIB)

        # Busca dinâmica de colunas
        c_pmib = next((c for c in df.columns if "CÓDIGO PMIB" in str(c)), None)
        c_pdm = next((c for c in df.columns if "PDM usado" in str(c)), None)

        if not c_pmib or not c_pdm:
            return [], (
                "Colunas 'CÓDIGO PMIB' ou 'PDM usado' não encontradas na aba "
                f"'{config.ABA_LISTA_MATERIAIS}' (cabeçalho procurado nas "
                f"{LINHAS_BUSCA_CABECALHO} primeiras linhas).")

        df = df[[c_pmib, c_pdm]].dropna()

        # PARA: Formata a coluna inteira do DataFrame ANTES de filtrar (Idêntico ao Script 1)
        df[c_pmib] = df[c_pmib].astype(str).str.strip()
        # CP 1.2: delega a normalização (zeros à direita) para a
        # implementação única e canônica (core.excel.pmib_codes.normalize_pmib)
        # — este código TRUNCAVA a fração para 4 dígitos quando havia mais;
        # o canônico NÃO trunca (diferença só visível com mais de 4 casas
        # decimais, que não ocorre em PMIB real) — ver
        # docs/refatoracao/PENDENCIAS.md.
        df[c_pmib] = df[c_pmib].apply(pmib_codes.normalize_pmib)

        # Filtro de seleção manual (se houver)
        if lista_selecionados:
            df = df[df[c_pmib].isin(lista_selecionados)]

        criados = []
        for _, row in df.iterrows():
            cod_fmt = row[c_pmib]  # Já está com os zeros garantidos!
            pdm_val = str(row[c_pdm]).strip()

            # PARA: Nova lógica de decisão
            if criar_subpastas:
                path_dir = os.path.join(destino_fichas, cod_fmt)
                if not os.path.exists(path_dir):
                    os.makedirs(path_dir, exist_ok=True)
            else:
                # Se for "Apenas Planilhas", o diretório alvo é a própria raiz!
                path_dir = destino_fichas

            criados.append((cod_fmt, pdm_val, path_dir))

        tipo_str = "pastas" if criar_subpastas else "itens"
        return criados, f"{len(criados)} {tipo_str} processados."
    except Exception as e:
        return [], f"Erro ao ler Excel: {e}"



# =============================================================================
# A ABA DA FICHA DENTRO DO TEMPLATE
# =============================================================================
# A implementacao MUDOU DE CASA em 2026-09-03, para `core/rpa/ficha_layout.py`.
#
# Ela nasceu aqui porque o montador foi o primeiro a precisar dela. Mas a
# auditoria da ficha em ingles achou mais DOIS modulos resolvendo "qual aba e a
# ficha" por conta propria -- `upload_conditions.extrair_dados_brutos_excel` e
# `AutoSpecCore.fill_save` --, os dois exigindo o nome literal em portugues, e
# os dois quebrando na ficha em ingles que o proprio SIG-FT gera. Tres copias
# do mesmo conceito e exatamente como o `CONFIG_MAP` acabou duplicado com
# ranges divergentes antes do CP 2.4.
#
# `ficha_layout.py` e, por docstring propria, "fonte unica do layout da Ficha
# Tecnica Padrao" -- e o nome da aba e layout. Os nomes seguem importaveis
# daqui: quem ja fazia `pdm.nome_da_aba_da_ficha` nao precisa saber que mudou.
from sigft.core.rpa import ficha_layout

# Reexportacao por ATRIBUICAO, e nao por `from ... import`: um import so usado
# para reexportar e "importado e nao usado" para os linters, e o comentario `noqa` nao
# vale para o pyflakes nem, dentro de parenteses, para o ruff. Atribuir e
# explicito -- diz "isto continua morando aqui de proposito".
NOME_CANONICO_DA_ABA = ficha_layout.NOME_CANONICO_DA_ABA
NOME_DA_ABA_EM_INGLES = ficha_layout.NOME_DA_ABA_EM_INGLES
NOMES_DA_ABA_DA_FICHA = ficha_layout.NOMES_DA_ABA_DA_FICHA
nome_da_aba_da_ficha = ficha_layout.nome_da_aba_da_ficha
_normalizar_nome_de_aba = ficha_layout._normalizar_nome_de_aba

_ALVO_EN = _normalizar_nome_de_aba(NOME_DA_ABA_EM_INGLES)


# =============================================================================
# MONTAGEM DA FICHA
# =============================================================================
# A montagem (template da memória, aba resolvida uma vez, linha 79, mesclas,
# fonte 8, altura 32, bordas, salvar perguntando) é UMA só. As perguntas de
# cada material vêm da planilha de PDMs (`aplicar_templates_fichas_da_planilha`);
# a fonte antiga, a pasta de PDMs Modificados, saiu em 2026-10-21. Ver
# docs/superpowers/specs/2026-09-23-planilhas-pmib-da-planilha-design.md.

class _Recusado(Exception):
    """A fonte não tem as perguntas deste material.

    `motivo` vai para o resumo do lote; `linha_de_log`, para a lista `log` que
    a função pública devolve."""

    def __init__(self, motivo, linha_de_log):
        super().__init__(motivo)
        self.motivo = motivo
        self.linha_de_log = linha_de_log


@dataclass
class _Perguntas:
    # `[(descricao, resposta), ...]` na ordem da ficha, a partir da linha 79.
    # Entrada vazia PULA uma linha (a ficha guarda o lugar da pergunta).
    linhas: list
    # Completa a linha de sucesso do lote: "(PDM.5925.001 R5, 51 perguntas)".
    detalhe: str = ""
    # `[(causa, consequencia), ...]` para `RelatorioLote.aviso`.
    avisos: list = field(default_factory=list)
    divergencia: str = ""
    causa_da_divergencia: str = ""


def _ler_template(path_template):
    # CP 4.3 (otimização de I/O): o template é lido do disco UMA única vez,
    # para memória; cada ficha reabre uma cópia limpa de `BytesIO`.
    with open(path_template, "rb") as arquivo_template:
        return arquivo_template.read()



def _escrever_perguntas(ws_target, linhas):
    # Lógica de cópia (Linha 79 fixo)
    start_row = 79
    borda = Border(left=Side('thin'), right=Side('thin'), top=Side('thin'), bottom=Side('thin'))
    align = Alignment(wrap_text=True, vertical='top')
    font8 = Font(size=8)

    for i, (v_desc, v_resp) in enumerate(linhas, start=1):
        if not v_desc and not v_resp: continue

        row_idx = start_row + i - 1

        # Merge e escrita
        ws_target.merge_cells(start_row=row_idx, start_column=3, end_row=row_idx, end_column=12)
        ws_target.merge_cells(start_row=row_idx, start_column=13, end_row=row_idx, end_column=22)

        c_d = ws_target.cell(row=row_idx, column=3, value=v_desc)
        c_r = ws_target.cell(row=row_idx, column=13, value=v_resp)

        c_d.font = font8; c_d.alignment = align
        c_r.font = font8; c_r.alignment = align

        # Bordas
        for c in range(3, 13): ws_target.cell(row=row_idx, column=c).border = borda
        for c in range(13, 23): ws_target.cell(row=row_idx, column=c).border = borda

        ws_target.row_dimensions[row_idx].height = 32


def _montar_fichas(lista_dados, obter_perguntas, bytes_template, *, callbacks,
                   retry_lock, idioma, titulo, contexto, log):
    """O laço de montagem. Devolve `(count, erro_de_template, divergencias)`,
    com `divergencias = [(pmib, divergencia, causa), ...]` das fichas GERADAS."""
    count = 0
    nome_da_aba = None
    erro_de_template = None
    divergencias = []
    em_ingles = str(idioma or "pt").strip().lower().startswith("en")
    # CP 4.4: `RelatorioLote` (início com total/contexto, linha por item,
    # resumo final com as falhas listadas).
    with RelatorioLote(callbacks, titulo=titulo, total=len(lista_dados),
                       contexto=contexto) as lote:
        for pmib, pdm_nome, pasta_destino in lista_dados:
            try:
                perguntas = obter_perguntas(pmib, pdm_nome)
                for causa, consequencia in perguntas.avisos:
                    lote.aviso(pmib, causa, consequencia)

                # CP 4.3: cópia limpa do template vinda da MEMÓRIA.
                wb_target = load_workbook(BytesIO(bytes_template))

                # A aba e resolvida UMA vez, na primeira ficha, reaproveitando
                # o workbook que seria lido de qualquer jeito. Template errado
                # e problema do TEMPLATE, nao de cada ficha: falhar 200 vezes
                # com a mesma mensagem generica esconde a causa em vez de
                # mostra-la, entao o lote PARA com o motivo.
                if nome_da_aba is None:
                    try:
                        nome_da_aba = nome_da_aba_da_ficha(wb_target)
                    except ValueError as e:
                        erro_de_template = f"Erro no template: {e}"
                        log.append(erro_de_template)
                        lote.falha(pmib, erro_de_template)
                        break
                ws_target = wb_target[nome_da_aba]

                # A aba da ficha ENTREGUE ao fornecedor estrangeiro tem de ter
                # nome em ingles. O template ainda traz o nome em portugues, e
                # o usuario vinha renomeando a mao, ficha a ficha (decisao de
                # 2026-09-03). Renomear e seguro do lado de quem LE de volta:
                # `analyzer._aba_da_ficha` escolhe a aba por EVIDENCIA --
                # quantas ancoras do CONFIG_MAP estao preenchidas --, nao por
                # nome.
                #
                # A comparacao normalizada evita o caso "alguem ja consertou o
                # template": renomear uma aba para o nome que ela ja tem e
                # inofensivo, mas renomear para o nome de OUTRA aba do mesmo
                # workbook nao e.
                if em_ingles and _normalizar_nome_de_aba(ws_target.title) != _ALVO_EN:
                    if not any(_normalizar_nome_de_aba(outra.title) == _ALVO_EN
                               for outra in wb_target.worksheets):
                        ws_target.title = NOME_DA_ABA_EM_INGLES

                _escrever_perguntas(ws_target, perguntas.linhas)

                out_file = os.path.join(pasta_destino, f"{pmib}.xlsx")
                locking.salvar_perguntando(wb_target, out_file, retry_lock=retry_lock)
                wb_target.close()
                count += 1
                linha_de_sucesso = f"ficha gerada: {os.path.basename(out_file)}"
                if perguntas.detalhe:
                    linha_de_sucesso += f" {perguntas.detalhe}"
                lote.sucesso(pmib, linha_de_sucesso)
                if perguntas.divergencia:
                    divergencias.append((pmib, perguntas.divergencia,
                                         perguntas.causa_da_divergencia))

            except _Recusado as e:
                log.append(e.linha_de_log)
                lote.falha(pmib, e.motivo)
            except Exception as e:
                msg_erro = f"ERRO ao gerar ficha {pmib}: {e}"
                log.append(msg_erro)
                lote.falha(pmib, f"{type(e).__name__}: {e}")

    return count, erro_de_template, divergencias



# As duas listas do fim do lote pela planilha (regras 4 e 5 do spec).
_TITULOS_DAS_DIVERGENCIAS = (
    (pdm_planilha.PORTAL_ATRAS, "PDM precisa subir de revisao no portal"),
    (pdm_planilha.PLANILHA_ATRAS, "Planilha atras do portal, exporte uma nova da Itaipu"),
)


def _listar_divergencias(callbacks, divergencias):
    """O `RelatorioLote` conta os avisos mas não os lista, e estas duas listas
    SÃO o que o usuário faz depois: subir revisão no portal, ou pedir planilha
    nova."""
    for tipo, titulo in _TITULOS_DAS_DIVERGENCIAS:
        do_tipo = [(pmib, causa) for pmib, qual, causa in divergencias if qual == tipo]
        if do_tipo:
            callbacks.log(f"{titulo} ({len(do_tipo)}):", nivel="warn")
            for pmib, causa in do_tipo:
                callbacks.log(f"   {pmib}: {causa}", nivel="warn")


def aplicar_templates_fichas_da_planilha(lista_dados, catalogo, path_template,
                                         log_callback=None, retry_lock=None):
    """As perguntas vêm da PLANILHA de PDMs (`catalogo`, de
    `pdm_catalogo.carregar`): revisão vigente, ordem da SECUENCIA, sem
    "(nan)". Sempre em português: a ficha em inglês usa a pasta traduzida
    (decisão do usuário, 2026-09-23). Regras em `services/pdm_planilha.py`."""
    callbacks = from_legacy(callback_log=log_callback)
    log = []
    try:
        pdm_planilha.conferir_catalogo(catalogo)
    except pdm_planilha.PDMRecusado as e:
        callbacks.log(str(e), nivel="error")
        return str(e), [str(e)]
    callbacks.log(pdm_planilha.descrever_catalogo(catalogo), nivel="info")
    try:
        bytes_template = _ler_template(path_template)
    except Exception as e:
        return f"Erro ao abrir template: {e}", [f"Erro ao abrir template: {e}"]

    def obter(pmib, pdm_nome):
        try:
            resultado = pdm_planilha.perguntas_do_pdm(catalogo, pdm_nome)
        except pdm_planilha.PDMRecusado as e:
            raise _Recusado(str(e), f"FALHA: {pmib}: {e}") from e
        pdm_do_item = resultado.pdm
        return _Perguntas(
            linhas=[(texto, None) for texto in resultado.linhas],
            detalhe=(f"({pdm_do_item.codigo} R{pdm_do_item.revisao}, "
                     f"{len(resultado.linhas)} perguntas)"),
            avisos=([(resultado.causa, resultado.consequencia)]
                    if resultado.divergencia else []),
            divergencia=resultado.divergencia,
            causa_da_divergencia=resultado.causa,
        )

    count, erro_de_template, divergencias = _montar_fichas(
        lista_dados, obter, bytes_template, callbacks=callbacks,
        retry_lock=retry_lock, idioma="pt",
        titulo="Montando fichas a partir da planilha de PDMs",
        contexto={"planilha": catalogo.origem, "template": path_template},
        log=log,
    )
    _listar_divergencias(callbacks, divergencias)
    if erro_de_template:
        return erro_de_template, log
    mensagem = f"Fichas geradas: {count}"
    if divergencias:
        mensagem += f" ({len(divergencias)} com revisao diferente do portal)"
    return mensagem, log

