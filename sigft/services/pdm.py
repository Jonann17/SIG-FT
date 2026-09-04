import pandas as pd
import os
import glob
import re
import shutil
from copy import copy
# CP 4.3: `BytesIO` permite reabrir uma planilha já lida para memória sem
# tocar o disco de novo -- ver `pdms_fromItaipu_lista_geral` e
# `aplicar_templates_fichas`.
from io import BytesIO

from openpyxl import load_workbook
from openpyxl.styles import Border, Side, Alignment, Font

from sigft.core.excel import pmib_codes
# CP 4.4 (Fase 4, docs/refatoracao/PLANO_REFATORACAO.md): padrão único de log
# de lote. `pdm_backend` era um dos "módulos hoje pobres" do diagnóstico
# (sem resumo final, sem contexto do item) -- as 3 funções de LOTE deste
# módulo (`pdms_fromItaipu_lista_geral`, `aplicar_templates_fichas`,
# `logica_excluir_duplicados`) já recebiam `log_callback` (assinatura
# ANTIGA, um único callable posicional) -- `from_legacy` adapta isso para
# `UICallbacks` sem mudar a assinatura pública de nenhuma das 3 funções.
# `processar_pastas_fichas`/`mover_fichas_para_raiz` NÃO têm nenhum canal de
# log hoje -- fora de escopo deste checkpoint (ver PENDENCIAS.md).
from sigft.core.callbacks import from_legacy
from sigft.core.relatorio_lote import RelatorioLote
from sigft.core.excel import locking


# =============================================================================
# FUNÇÕES UTILITÁRIAS
# =============================================================================
def listar_arquivos_excel(caminho_pasta):
    return [arq for arq in glob.glob(os.path.join(caminho_pasta, '*.xls*')) if os.path.isfile(arq)]


def extrair_pdm_id(nome_arquivo):
    match = re.search(r'PDM_\d{4}_\d{3}', nome_arquivo)
    return match.group() if match else None


# =============================================================================
# LÓGICA DE PROCESSAMENTO DE PDM
# =============================================================================
def processar_arquivo_pdm(caminho_arquivo_pdm):
    try:
        # Tenta ler ignorando erros de cabeçalho inicial
        df = pd.read_excel(caminho_arquivo_pdm, sheet_name="TEMPLATE_PDM", skiprows=6, header=None)

        # Validação básica de colunas
        if df.shape[1] < 19: return None  # Verifica se tem colunas suficientes (S é a 19ª)

        col_q = df.iloc[:, 16]  # Coluna Q (índice 16)
        col_s = df.iloc[:, 18]  # Coluna S (índice 18)

        nova_tabela = pd.DataFrame({
            'Descrição': [f"{i+1} - {str(q)} ({str(s)}):" for i, (q, s) in enumerate(zip(col_q, col_s))],
            'Resposta': ['' for _ in range(len(col_q))]
        })
        return nova_tabela
    except Exception as e:
        print(f"Erro processar_arquivo_pdm: {e}")
        return None


def salvar_tabela_formatada(nova_tabela, caminho_arquivo_original, pasta_destino, force=False, retry_lock=None):
    nome_original = os.path.basename(caminho_arquivo_original)
    nome_sem_extensao = os.path.splitext(nome_original)[0]
    novo_nome = nome_sem_extensao + "_formatado.xlsx"
    caminho_saida = os.path.join(pasta_destino, novo_nome)

    if not force:
        if any(nome_sem_extensao.upper() in f.upper() for f in os.listdir(pasta_destino)):
            return False, f"Ignorado (já existe): {nome_original}"

    try:
        nova_tabela.to_excel(caminho_saida, index=False, header=False)
        wb = load_workbook(caminho_saida)
        ws = wb.active

        borda = Border(left=Side('thin'), right=Side('thin'), top=Side('thin'), bottom=Side('thin'))
        estilo = Alignment(wrap_text=True, vertical='top')
        fonte = Font(size=8)

        for i, row in enumerate(nova_tabela.itertuples(index=False), start=1):
            ws.row_dimensions[i].height = 32

            # Formatação Coluna 1 (Desc)
            ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=10)
            c1 = ws.cell(row=i, column=1, value=row[0])
            c1.alignment = estilo; c1.font = fonte
            for c in range(1, 11): ws.cell(row=i, column=c).border = borda

            # Formatação Coluna 2 (Resp)
            ws.merge_cells(start_row=i, start_column=11, end_row=i, end_column=20)
            c2 = ws.cell(row=i, column=11, value=row[1])
            c2.alignment = estilo; c2.font = fonte
            for c in range(11, 21): ws.cell(row=i, column=c).border = borda

        locking.salvar_perguntando(wb, caminho_saida, retry_lock=retry_lock)
        return True, f"Salvo: {novo_nome}"
    except Exception as e:
        return False, f"Erro ao salvar: {e}"


# =============================================================================
# LÓGICA FROM ITAIPU
# =============================================================================
def pdms_fromItaipu_lista_geral(path_lista_geral_pdms, pasta_destino, log_callback=None, retry_lock=None):
    # CP 4.4: `from_legacy` adapta o `log_callback` de assinatura ANTIGA
    # (1 callable posicional) para `UICallbacks` -- a assinatura pública da
    # função NÃO muda (continua `log_callback=None`, aceitando o mesmo
    # callable de sempre); `callbacks` é só uma variável LOCAL usada daqui
    # pra baixo. Sem `log_callback`, `callbacks.log` vira no-op (mesmo
    # comportamento de hoje: `if log_callback: ...` nunca disparava).
    callbacks = from_legacy(callback_log=log_callback)

    if not path_lista_geral_pdms or not pasta_destino:
        return "Caminhos inválidos."

    arquivos_existentes = {os.path.splitext(f)[0].split(' - ')[0].strip().upper() for f in os.listdir(pasta_destino) if f.endswith(('.xlsx', '.xls'))}

    # CP 4.3 (otimização de I/O): a planilha de origem é lida do disco UMA
    # única vez, para memória. Antes, o laço abaixo fazia
    # `load_workbook(path_lista_geral_pdms)` a cada código novo — a origem
    # inteira relida do disco N vezes (o O(n·m) de I/O apontado no
    # diagnóstico do plano, seção 1.5). Não dá para reaproveitar UM objeto
    # workbook entre iterações porque cada volta o MUTILA (`wb.remove`,
    # `ws.delete_rows`); então o que se guarda são os BYTES, e cada iteração
    # abre um `BytesIO` novo — mesmo resultado, sem tocar o disco de novo.
    try:
        with open(path_lista_geral_pdms, "rb") as arquivo_origem:
            bytes_origem = arquivo_origem.read()
        wb_check = load_workbook(BytesIO(bytes_origem))
        ws_check = wb_check["TEMPLATE_PDM"]
    except Exception as e:
        return f"Erro ao abrir planilha: {e}"

    # Mapeamento de códigos
    linhas_por_codigo = {}
    for i, row in enumerate(ws_check.iter_rows(min_row=7, values_only=False), start=7):
        cell = row[0]
        if cell and cell.value:
            cod = str(cell.value).strip().replace('.', '_').upper()
            if cod:
                linhas_por_codigo.setdefault(cod, []).append(i)

    codigos_todos = set(linhas_por_codigo.keys())
    codigos_novos = codigos_todos - arquivos_existentes
    criados = []

    if not codigos_novos:
        return "Nenhum código novo encontrado."

    # CP 4.4: `RelatorioLote` substitui os `if log_callback: log_callback(...)`
    # soltos do laço pelo padrão único (início com total/contexto, por item,
    # resumo final com falhas listadas) -- nenhuma condição/ordem do laço
    # muda, só o que é logado.
    with RelatorioLote(
        callbacks,
        titulo="Fatiando lista geral de PDMs (From Itaipu)",
        total=len(codigos_novos),
        contexto={"origem": path_lista_geral_pdms, "destino": pasta_destino},
    ) as lote:
        for codigo in codigos_novos:
            # Check duplo de segurança
            if any(codigo in f.upper() for f in os.listdir(pasta_destino)):
                lote.pulado(codigo, "já existe em pasta_destino (checagem dupla)")
                continue

            linhas = linhas_por_codigo[codigo]
            # Pega descrição da coluna D (índice 4 no Excel, 3 no python 0-based, mas openpyxl é 1-based)
            desc_val = (ws_check.cell(row=linhas[0], column=4).value or "sem_descricao").strip()
            nome_arq = f"{codigo} - {desc_val}.xlsx"
            caminho_final = os.path.join(pasta_destino, nome_arq)

            # Processo de criação (reabre uma cópia LIMPA da origem)
            try:
                # CP 4.3: `BytesIO(bytes_origem)` em vez de reler o arquivo do
                # disco. Cada iteração ainda precisa de um workbook novo (o corpo
                # abaixo remove abas e apaga linhas), mas agora a cópia sai da
                # memória.
                wb = load_workbook(BytesIO(bytes_origem))
                for n in wb.sheetnames:
                    if n != "TEMPLATE_PDM":
                        wb.remove(wb[n])

                ws = wb["TEMPLATE_PDM"]
                todas = list(ws.iter_rows(values_only=False))
                cabecalho = todas[:6]
                linhas_conteudo = [todas[i-1] for i in linhas]

                ws.delete_rows(1, ws.max_row)

                for idx_l, linha in enumerate(cabecalho + linhas_conteudo, start=1):
                    for idx_c, celula in enumerate(linha, start=1):
                        new_c = ws.cell(row=idx_l, column=idx_c, value=celula.value)
                        if celula.has_style:
                            new_c.font = copy(celula.font)
                            new_c.border = copy(celula.border)
                            new_c.fill = copy(celula.fill)
                            new_c.number_format = copy(celula.number_format)
                            new_c.alignment = copy(celula.alignment)

                locking.salvar_perguntando(wb, caminho_final, retry_lock=retry_lock)
                criados.append(nome_arq)
                wb.close()
                lote.sucesso(codigo, f"criado {nome_arq}")
            except Exception as e:
                lote.falha(codigo, f"{type(e).__name__}: {e}")

    return f"Concluído.\nCriados: {len(criados)}\nTotal Analisado: {len(codigos_todos)}"


# =============================================================================
# LÓGICA CRIAÇÃO DE FICHAS (PMIB)
# =============================================================================
def processar_pastas_fichas(arquivo_STATUS_PMIB, destino_fichas, lista_selecionados=None, criar_subpastas=True):
    """Cria a estrutura de pastas (ou apenas lista os caminhos) baseada no Excel STATUS_PMIB"""
    try:
        df = pd.read_excel(arquivo_STATUS_PMIB, sheet_name="Lista de Materiais", skiprows=3)

        # Busca dinâmica de colunas
        c_pmib = next((c for c in df.columns if "CÓDIGO PMIB" in str(c)), None)
        c_pdm = next((c for c in df.columns if "PDM usado" in str(c)), None)

        if not c_pmib or not c_pdm:
            return [], "Colunas 'CÓDIGO PMIB' ou 'PDM usado' não encontradas no Excel (linha 4)."

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
# para reexportar e "importado e nao usado" para os linters, e o `# noqa` nao
# vale para o pyflakes nem, dentro de parenteses, para o ruff. Atribuir e
# explicito -- diz "isto continua morando aqui de proposito".
NOME_CANONICO_DA_ABA = ficha_layout.NOME_CANONICO_DA_ABA
NOME_DA_ABA_EM_INGLES = ficha_layout.NOME_DA_ABA_EM_INGLES
NOMES_DA_ABA_DA_FICHA = ficha_layout.NOMES_DA_ABA_DA_FICHA
nome_da_aba_da_ficha = ficha_layout.nome_da_aba_da_ficha
_normalizar_nome_de_aba = ficha_layout._normalizar_nome_de_aba

_ALVO_EN = _normalizar_nome_de_aba(NOME_DA_ABA_EM_INGLES)


def aplicar_templates_fichas(lista_dados, pasta_pdms_modificados, path_template,
                             log_callback=None, retry_lock=None, idioma="pt"):
    # CP 4.4: mesma adaptação de `pdms_fromItaipu_lista_geral` acima --
    # `callbacks` é local, a assinatura pública não muda.
    callbacks = from_legacy(callback_log=log_callback)
    log = []

    # Cache dos arquivos de PDM para não listar disco toda hora
    pdms_disponiveis = listar_arquivos_excel(pasta_pdms_modificados)

    # CP 4.3 (otimização de I/O): o template é lido do disco UMA única vez,
    # para memória. Antes, `load_workbook(path_template)` acontecia DENTRO do
    # laço, uma vez por ficha gerada (o próprio comentário original admitia:
    # "Para performance ideal, deveríamos copiar o objeto workbook, mas I/O é
    # aceitável aqui"). Cada ficha continua precisando de um template LIMPO
    # (o laço escreve nele antes de salvar), então a cópia agora vem de um
    # `BytesIO` — mesmo isolamento, sem I/O repetido.
    #
    # Some junto um desperdício puro que existia aqui: o `wb_templ =
    # load_workbook(path_template)` original era carregado e NUNCA usado —
    # só fechado no fim da função. Ler os bytes substitui os dois papéis.
    try:
        with open(path_template, "rb") as arquivo_template:
            bytes_template = arquivo_template.read()
    except Exception as e:
        return f"Erro ao abrir template: {e}", [f"Erro ao abrir template: {e}"]


    count = 0
    nome_da_aba = None
    erro_de_template = None
    em_ingles = str(idioma or "pt").strip().lower().startswith("en")
    # CP 4.4: mesma troca de `pdms_fromItaipu_lista_geral` -- o
    # `if log_callback: log_callback(...)` de cada branch vira uma chamada de
    # `RelatorioLote`; a lista `log` (parte do retorno público da função,
    # consumida hoje só por `frontend.py` e por
    # `tests/test_pdm_io.py::test_templates_fichas_reporta_erro_se_o_template_nao_abrir`)
    # continua recebendo EXATAMENTE as mesmas strings de antes.
    with RelatorioLote(
        callbacks,
        titulo="Aplicando templates de PDM nas fichas técnicas",
        total=len(lista_dados),
        contexto={"pasta_pdms_modificados": pasta_pdms_modificados, "template": path_template},
    ) as lote:
        for pmib, pdm_nome, pasta_destino in lista_dados:
            id_pdm = pdm_nome.split(" - ")[0].replace(".", "_")

            # Achar arquivo fonte
            src = next((f for f in pdms_disponiveis if id_pdm in os.path.basename(f)), None)
            if not src:
                msg_falha = f"PDM fonte não encontrado para {pmib} ({id_pdm})"
                log.append(f"FALHA: {msg_falha}")
                lote.falha(pmib, msg_falha)
                continue

            try:
                wb_pdm = load_workbook(src)
                ws_pdm = wb_pdm.active

                # CP 4.3: cópia limpa do template vinda da MEMÓRIA (antes era
                # um `load_workbook(path_template)` por ficha).
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

                # Lógica de cópia (Linha 79 fixo)
                start_row = 79
                borda = Border(left=Side('thin'), right=Side('thin'), top=Side('thin'), bottom=Side('thin'))
                align = Alignment(wrap_text=True, vertical='top')
                font8 = Font(size=8)

                for i in range(1, ws_pdm.max_row + 1):
                    v_desc = ws_pdm.cell(row=i, column=1).value
                    v_resp = ws_pdm.cell(row=i, column=2).value

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

                out_file = os.path.join(pasta_destino, f"{pmib}.xlsx")
                locking.salvar_perguntando(wb_target, out_file, retry_lock=retry_lock)
                wb_target.close()
                wb_pdm.close()
                count += 1
                lote.sucesso(pmib, f"ficha gerada: {os.path.basename(out_file)}")

            except Exception as e:
                msg_erro = f"ERRO ao gerar ficha {pmib}: {e}"
                log.append(msg_erro)
                lote.falha(pmib, f"{type(e).__name__}: {e}")

    # CP 4.3: não há mais `wb_templ` para fechar — o template vive como
    # bytes em memória (ver o início da função).
    if erro_de_template:
        return erro_de_template, log
    return f"Fichas geradas: {count}", log


def mover_fichas_para_raiz(lista_dados):
    count = 0
    if not lista_dados:
        return "Nada para mover."

    # Pasta raiz é a pasta mãe de onde estão as pastas de PMIB
    pasta_raiz = os.path.dirname(lista_dados[0][2])

    for pmib, _, pasta_origem in lista_dados:
        f_origem = os.path.join(pasta_origem, f"{pmib}.xlsx")
        f_dest = os.path.join(pasta_raiz, f"{pmib}.xlsx")

        if os.path.exists(f_origem):
            try:
                shutil.move(f_origem, f_dest)
                count += 1
            except Exception: pass

    return f"{count} arquivos movidos para {pasta_raiz}"


# =============================================================================
# EXCLUSÃO DUPLICADOS
# =============================================================================
def logica_excluir_duplicados(pasta_alvo, log_callback=None):
    if not pasta_alvo:
        return "Pasta inválida."

    # CP 4.4: mesma adaptação das 2 funções acima -- `callbacks` local, sem
    # tocar na assinatura pública.
    callbacks = from_legacy(callback_log=log_callback)

    files = {}
    # Agrupa
    for f in os.listdir(pasta_alvo):
        if f.endswith(('.xlsx', '.xls', '.xlsm')):
            pid = extrair_pdm_id(f)
            if pid: files.setdefault(pid, []).append(os.path.join(pasta_alvo, f))

    deleted = 0
    log = []
    # `total` do lote = só os grupos que TÊM duplicata (os únicos que o laço
    # abaixo de fato processa) -- grupos com 1 arquivo só continuam
    # silenciosos, como sempre foram (nunca houve log pra eles).
    total_com_duplicata = sum(1 for paths in files.values() if len(paths) > 1)

    with RelatorioLote(
        callbacks,
        titulo="Excluindo PDMs duplicados",
        total=total_com_duplicata,
        contexto={"pasta": pasta_alvo},
    ) as lote:
        for pid, paths in files.items():
            if len(paths) > 1:
                # Ordena: Maior tamanho primeiro, depois mais recente
                paths.sort(key=lambda x: (-os.path.getsize(x), os.path.getmtime(x)))
                # Exclui o primeiro (o "melhor" candidato a duplicata inútil segundo a lógica original?)
                # NOTA: O script original excluía o PRIMEIRO da lista sorted.
                # Se sort é (Tamanho DESC), o primeiro é o MAIOR arquivo.
                # Isso parece contra-intuitivo (excluir o maior?), mas mantive a lógica original.
                try:
                    os.remove(paths[0])
                    deleted += 1
                    msg = f"Lixeira - Excluído: {os.path.basename(paths[0])}"
                    log.append(msg)
                    lote.sucesso(pid, os.path.basename(paths[0]))
                except Exception as e:
                    msg_erro = f"Erro ao excluir {paths[0]}: {e}"
                    log.append(msg_erro)
                    lote.falha(pid, f"{type(e).__name__}: {e}")

    return f"Total excluídos: {deleted}\n" + "\n".join(log)
