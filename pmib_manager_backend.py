import os
import shutil
import pandas as pd
import openpyxl
from datetime import datetime
from openpyxl import load_workbook
from copy import copy
import warnings

from sigft.core.excel import headers, locking

# Configurações iniciais
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


# --- FUNÇÃO AUXILIAR DE FORMATAÇÃO (MANTIDA) ---
def copiar_estilo_seguro(celula_origem, celula_destino):
    """
    Copia propriedades visuais forçadamente.
    """
    if celula_origem.font:
        celula_destino.font = copy(celula_origem.font)

    if celula_origem.border:
        celula_destino.border = copy(celula_origem.border)

    if celula_origem.fill:
        celula_destino.fill = copy(celula_origem.fill)

    if celula_origem.alignment:
        celula_destino.alignment = copy(celula_origem.alignment)

    if celula_origem.number_format:
        celula_destino.number_format = copy(celula_origem.number_format)

    if celula_origem.protection:
        celula_destino.protection = copy(celula_origem.protection)


# =============================================================================
# CLASSE DE GERENCIAMENTO (BACKEND)
# =============================================================================
class PMIBManager:
    def __init__(self):
        pass

    # --- SALVAMENTO COM RETRY (CP 1.3) ---
    @staticmethod
    def _salvar_com_retry_interativo(wb, caminho, callback_retry_lock):
        """Salva `wb` em `caminho`, usando `callback_retry_lock()` (SEM
        argumentos, retorna bool) para decidir se retenta a cada
        `PermissionError` -- mesmo contrato dos 2 laços `while not salvo`
        originais de `executar_fluxo` (planilha mestra/gerenciadora),
        agora unificados aqui e delegando para
        `core.excel.locking.save_with_retry` (única implementação de
        retry de `PermissionError` -- ver
        docs/refatoracao/PLANO_REFATORACAO.md, Fase 1 -> CP 1.3).

        Retorna `True` se salvou; `False` se o usuário optou por não
        retentar (ou não havia `callback_retry_lock`) -- o arquivo
        permaneceu bloqueado. Nunca levanta `PermissionError` (é
        capturada aqui, ao contrário do contrato "cru" de
        `save_with_retry`), para que os 2 call sites continuem só
        checando um booleano, como antes.
        """
        def _on_locked(attempt, exc):
            return bool(callback_retry_lock()) if callback_retry_lock else False

        try:
            locking.save_with_retry(wb, caminho, on_locked=_on_locked)
            return True
        except PermissionError:
            return False

    # --- MÉTODOS DE LÓGICA PURA (Helpers) ---
    def _buscar_rdspp_mais_recente(self, codigo_arquivo_fisico, df_api):
        codigo_limpo = codigo_arquivo_fisico.strip()

        if 'No. do Documento' not in df_api.columns or 'Tracking ID' not in df_api.columns:
            return codigo_limpo

        filtro_codigo = df_api['No. do Documento'].str.strip() == codigo_limpo
        df_encontrado = df_api[filtro_codigo]

        if df_encontrado.empty:
            return codigo_limpo

        tracking_id = df_encontrado['Tracking ID'].iloc[0]

        filtro_current = (df_api['Tracking ID'] == tracking_id) & (df_api['Current'] == True)
        df_atual = df_api[filtro_current]

        if not df_atual.empty:
            return df_atual['No. do Documento'].iloc[0].strip()

        return codigo_limpo

    def _renomear_arquivo_status_pmib(self, caminho_original, new_codigo_rdspp):
        try:
            diretorio = os.path.dirname(caminho_original)
            nome_arquivo_antigo = os.path.basename(caminho_original)
            _, extensao = os.path.splitext(nome_arquivo_antigo)

            novo_nome_arquivo = f"{new_codigo_rdspp}_STATUS_PMIB{extensao}"
            caminho_novo = os.path.join(diretorio, novo_nome_arquivo)

            if caminho_original.lower() == caminho_novo.lower():
                return True, "Nome já está atualizado.", caminho_original

            shutil.move(caminho_original, caminho_novo)
            return True, f"Renomeado: '{nome_arquivo_antigo}' -> '{novo_nome_arquivo}'.", caminho_novo

        except Exception as e:
            return False, f"Erro ao renomear: {e}", caminho_original

    def _ler_status_pmib(self, codigo_rdspp, link):
        try:
            colunas_desejadas = {
                'CÓDIGO DO MATERIAL': 'CÓDIGO DO MATERIAL',
                'CÓDIGO CMI': 'CÓDIGO CMI',
                'CÓDIGO PMIB': 'CÓDIGO PMIB',
                'STATUS': 'STATUS',
                'INFO. GERAIS': 'INFO. GERAIS',
                'CARACT. TÉCNICAS': 'CARACT. TÉCNICAS',
                'DOCUMENTOS E IMAGENS': 'DOCUMENTOS E IMAGENS',
                'CONDIÇÕES': 'CONDIÇÕES',
                'VALORIZAÇÃO': 'VALORIZAÇÃO',
                'APLICAÇÃO - LMR': 'APLICAÇÃO - LMR',
                'DATA DO EMAIL COMUNICANDO ENTREGA': 'DATA INFORME',
                'EQUIPAMENTO ENTREGUE': 'ENTREGUE',
                'APTO PARA ENTREGA': 'APTO PARA ENTREGA'  # <- NOVA COLUNA MAPEADA
            }
            colunas_desejadas_norm = {str(k).strip().upper(): v for k, v in colunas_desejadas.items()}

            # CP 1.2: busca dinâmica de cabeçalho via core.excel.headers. O
            # original lia o arquivo em ATÉ 10 chamadas separadas de
            # pd.read_excel (uma por linha candidata, variando skiprows) só
            # para inspecionar o nome das colunas; aqui lemos as 10
            # primeiras linhas de UMA vez (header=None, valores brutos) e
            # delegamos a busca em memória — mesmo resultado (mesma linha
            # encontrada), muito menos I/O. O try/except externo do método
            # inteiro continua sendo a rede de segurança para arquivo
            # ilegível (cai no `except` no fim e retorna (None, None)).
            df_preview = pd.read_excel(link, sheet_name='Lista de Materiais', header=None, nrows=10, na_filter=False)
            header_row = headers.find_header_row(df_preview.values.tolist(), 'CÓDIGO DO MATERIAL')

            if header_row is None:
                return None, None

            df_raw = pd.read_excel(link, sheet_name='Lista de Materiais', skiprows=header_row, na_filter=False, engine='openpyxl')

            col_map = {}
            found_cols = set()
            for col_encontrada in df_raw.columns:
                col_limpa = str(col_encontrada).strip().upper()
                if col_limpa in colunas_desejadas_norm and colunas_desejadas_norm[col_limpa] not in found_cols:
                    col_map[col_encontrada] = colunas_desejadas_norm[col_limpa]
                    found_cols.add(colunas_desejadas_norm[col_limpa])

            df = df_raw.rename(columns=col_map)
            # Filtra apenas colunas existentes no df
            cols_to_keep = [c for c in col_map.values() if c in df.columns]
            df = df[cols_to_keep]
            df['RDS_PP'] = codigo_rdspp
            return df, codigo_rdspp

        except Exception:
            return None, None

    def _calcula_fichas(self, df, rdspp):
        if 'CÓDIGO PMIB' not in df.columns: return {}
        df['CÓDIGO PMIB'] = df['CÓDIGO PMIB'].astype(str).str.strip().replace('', pd.NA)
        df = df[df['CÓDIGO PMIB'].notna()]

        # --- NOVA REGRA: Expulsar as linhas marcadas como "DUPLICADO" ---
        if 'STATUS' in df.columns:
            # Filtra e mantém apenas as linhas onde o STATUS NÃO É 'DUPLICADO'
            df = df[df['STATUS'].astype(str).str.strip().str.upper() != 'DUPLICADO']

        # Adicionamos o .copy() no final para tornar o dataframe independente e acabar com o aviso
        df_unicos = df.drop_duplicates(subset=['CÓDIGO PMIB'], keep='first').copy()

        total_fichas = df_unicos['CÓDIGO PMIB'].dropna().nunique()

        status_map = {
            'COM O FORNECEDOR': 'fichas_com_fornecedor',
            'EM ELABORAÇÃO': 'fichas_em_elaboracao',
            'EM ANÁLISE IB': 'fichas_em_analise_ib',
            'INICIAR': 'fichas_para_iniciar',
            'FICHA CRIADA': 'fichas_criadas',
            'APROVADO': 'fichas_aprovadas',
            'EM CORREÇÃO': 'fichas_em_correcao',
            'N/A': 'fichas_na'
        }

        resultados = {'RDS_PP': rdspp, 'total_fichas': total_fichas}

        if 'STATUS' in df_unicos.columns:
            for status_excel, chave_dict in status_map.items():
                resultados[chave_dict] = (df_unicos['STATUS'] == status_excel).sum()

        # Check completeness (Mantido o indicador original caso precise, e adicionado o novo)
        cols_compl = ['INFO. GERAIS', 'CARACT. TÉCNICAS', 'DOCUMENTOS E IMAGENS', 'CONDIÇÕES']

        # 1. Nova Regra: Fichas Recebidas (Pelo menos um 'COMPLETO')
        if any(c in df_unicos.columns for c in cols_compl):
            mask_recebidas = pd.DataFrame()
            for c in cols_compl:
                if c in df_unicos.columns:
                    mask_recebidas[c] = df_unicos[c] == 'COMPLETO'
            # any(axis=1) verifica se tem pelo menos um True na linha
            resultados['fichas_recebidas'] = mask_recebidas.any(axis=1).sum()
        else:
            resultados['fichas_recebidas'] = 0

        # 2. Regra Original mantida: Info completa do fornecedor (Todos 'COMPLETO')
        if all(c in df_unicos.columns for c in cols_compl):
            condicoes_completas = (
                (df_unicos['INFO. GERAIS'] == 'COMPLETO') &
                (df_unicos['CARACT. TÉCNICAS'] == 'COMPLETO') &
                (df_unicos['DOCUMENTOS E IMAGENS'] == 'COMPLETO') &
                (df_unicos['CONDIÇÕES'] == 'COMPLETO')
            )
            resultados['fichas_completas_info_fornecedor'] = condicoes_completas.sum()
        else:
            resultados['fichas_completas_info_fornecedor'] = 0

        if 'VALORIZAÇÃO' in df_unicos.columns:
            resultados['fichas_com_valorizacao'] = (df_unicos['VALORIZAÇÃO'] == 'COMPLETO').sum()
        else: resultados['fichas_com_valorizacao'] = 0

        if 'APLICAÇÃO - LMR' in df_unicos.columns:
            resultados['fichas_com_aplicacao_lmr'] = (df_unicos['APLICAÇÃO - LMR'] == 'COMPLETO').sum()
        else: resultados['fichas_com_aplicacao_lmr'] = 0

        if 'ENTREGUE' in df_unicos.columns:
            # Padroniza a coluna para evitar erros de espaços ou minúsculas
            df_unicos['ENTREGUE'] = df_unicos['ENTREGUE'].astype(str).str.strip().str.upper()
            resultados['equipamentos_entregue'] = (df_unicos['ENTREGUE'] == 'SIM').sum()
        else:
            resultados['equipamentos_entregue'] = 0

        # 3. Novas Regras: Apto para Entrega e Atraso Itaipu
        if 'APTO PARA ENTREGA' in df_unicos.columns:
            # Padroniza para caixa alta e tira espaços
            df_unicos['APTO PARA ENTREGA'] = df_unicos['APTO PARA ENTREGA'].astype(str).str.strip().str.upper()

            # Conta os SIM (excluindo aqueles que já foram efetivamente entregues)
            if 'ENTREGUE' in df_unicos.columns:
                cond_apto = (df_unicos['APTO PARA ENTREGA'] == 'SIM') & (df_unicos['ENTREGUE'] != 'SIM')
            else:
                cond_apto = (df_unicos['APTO PARA ENTREGA'] == 'SIM')

            resultados['fichas_aptas_para_entrega'] = cond_apto.sum()

            # Verifica Atraso Itaipu
            if 'DATA INFORME' in df_unicos.columns:
                df_unicos.loc[:, 'DATA INFORME'] = pd.to_datetime(df_unicos['DATA INFORME'], errors='coerce')

                # Vamos trabalhar apenas com as linhas que possuem data válida
                df_com_data = df_unicos.dropna(subset=['DATA INFORME']).copy()

                if not df_com_data.empty:
                    data_hoje = pd.Timestamp(datetime.now().date())
                    data_limite = df_com_data['DATA INFORME'] + pd.to_timedelta(14, unit='D')

                    # Condição: Data Limite Venceu E Apto NÃO é 'SIM' E o equipamento NÃO foi entregue ainda
                    if 'ENTREGUE' in df_com_data.columns:
                        cond_atraso = (data_limite < data_hoje) & (df_com_data['APTO PARA ENTREGA'] != 'SIM') & (df_com_data['ENTREGUE'] != 'SIM')
                    else:
                        cond_atraso = (data_limite < data_hoje) & (df_com_data['APTO PARA ENTREGA'] != 'SIM')

                    resultados['atraso_autorizacao_itaipu'] = cond_atraso.sum()
                else:
                    resultados['atraso_autorizacao_itaipu'] = 0
            else:
                resultados['atraso_autorizacao_itaipu'] = 0

        else:
            # Planilha desatualizada: emite o alerta no lugar dos números
            resultados['fichas_aptas_para_entrega'] = "Atualizar template"
            resultados['atraso_autorizacao_itaipu'] = "Atualizar template"

        return resultados

    # --- FLUXO PRINCIPAL EXECUTADO PELO APP ---
    def executar_fluxo(self, caminho_api, pasta_raiz_status, caminho_gerenciadora, callback_confirm=None, callback_retry_lock=None):
        """
        Orquestra todo o processo de gerenciamento.
        Yields: Logs de progresso.
        """

        # 1. Carregar API
        yield ("Carregando Base de Dados do DocManager...", 0.05)
        try:
            df_api = pd.read_excel(caminho_api, na_filter=False)
            if 'Current' in df_api.columns:
                df_api['Current'] = df_api['Current'].astype(str).str.lower() == 'true'
            else:
                yield "[ERRO] Coluna 'Current' não encontrada no Histórico do DocManager."
                return
        except Exception as e:
            yield f"[ERRO] Falha ao ler o Histórico do DocManager: {e}"
            return

        # 2. Buscar Arquivos STATUS
        yield ("Buscando arquivos _STATUS_PMIB na pasta raiz...", 0.15)
        lista_documentos = []
        for root, dirs, files in os.walk(pasta_raiz_status):
            for file in files:
                nome_lower = file.lower()
                if nome_lower.endswith("_status_pmib.xlsx") or nome_lower.endswith("_status_pmib.xls"):
                    codigo_documento = file.rsplit("_STATUS_PMIB", 1)[0]  # Pega o prefixo
                    caminho_completo = os.path.join(root, file)
                    lista_documentos.append((codigo_documento, caminho_completo))

        if not lista_documentos:
            yield "[AVISO] Nenhum arquivo _STATUS_PMIB encontrado."
            return

        # 3. Renomeação
        yield ("Verificando atualização de nomes (Renomeação)...", 0.25)
        codigos_renomeados = {}  # {codigo_antigo: (novo_codigo, caminho_atualizado)}

        for codigo_antigo, caminho_original in lista_documentos:
            novo_codigo = self._buscar_rdspp_mais_recente(codigo_antigo, df_api)

            if codigo_antigo != novo_codigo:
                sucesso, msg, caminho_novo = self._renomear_arquivo_status_pmib(caminho_original, novo_codigo)
                yield f" -> {msg}"
                if sucesso:
                    codigos_renomeados[codigo_antigo] = (novo_codigo, caminho_novo)
                else:
                    codigos_renomeados[codigo_antigo] = (novo_codigo, caminho_original)
            else:
                codigos_renomeados[codigo_antigo] = (novo_codigo, caminho_original)

        # 4. Atualizar Mapeamento (Planilha Mestra)
        yield ("Atualizando Mapeamento e Inserindo Novos...", 0.45)
        try:
            wb = load_workbook(caminho_gerenciadora)
            ws = wb.active

            mapeamento_colunas = {
                'N° DOCUMENTO ITAIPU': 'No. do Documento',
                'N° DOCUMENTO CMI': 'Controle do Emissor',
                'DESCRIÇÃO': 'Título',
                'ÚLTIMA REVISÃO EMITIDA': 'Revisão',
                'STATUS DA REVISÃO': 'Status',
                'DATA DE ATUALIZAÇÃO': 'Data de Alteração',
                'ESPECIFICAÇÃO TÉCNICA': 'Especialidade',
                'CAPÍTULO': 'Subespecialidade'
            }

            col_indices = {}
            for col_idx, cell in enumerate(ws[2]):
                if cell.value: col_indices[cell.value] = col_idx

            if 'N° DOCUMENTO ITAIPU' not in col_indices:
                yield "[ERRO] Coluna 'N° DOCUMENTO ITAIPU' não encontrada na Mestra."
                wb.close()
                return

            # A. Mapear Existentes
            doc_col = col_indices['N° DOCUMENTO ITAIPU']
            tracking_ids_existentes = set()
            for i in range(3, ws.max_row + 1):
                cod = ws.cell(row=i, column=doc_col + 1).value
                if cod:
                    cod = str(cod).strip()
                    filtro = df_api['No. do Documento'].str.strip() == cod
                    if filtro.any():
                        tracking_ids_existentes.add(df_api.loc[filtro, 'Tracking ID'].iloc[0])

            # B. Identificar Novos
            df_vigentes = df_api[df_api['Current'] == True]
            df_novos_cand = df_vigentes[
                (df_vigentes['Título'].str.contains('SOBRESSALENTES', case=False, na=False)) &
                (~df_vigentes['Título'].str.contains('PREÇOS', case=False, na=False)) &
                (~df_vigentes['Título'].str.contains('PREÇO', case=False, na=False)) &
                (~df_vigentes['No. do Documento'].str.endswith('-01', na=False))
            ].copy()

            df_reais_novos = df_novos_cand[~df_novos_cand['Tracking ID'].isin(tracking_ids_existentes)]

            # C. Inserir Novos (Com Pop-up Interativo)
            if not df_reais_novos.empty:
                df_para_inserir = pd.DataFrame()  # Começa vazio

                if callback_confirm:
                    # Agora o callback envia a tabela inteira e recebe de volta só o que você marcou!
                    df_para_inserir = callback_confirm(df_reais_novos)

                if df_para_inserir is not None and not df_para_inserir.empty:
                    linha_molde_idx = ws.max_row
                    max_coluna_real = ws.max_column

                    for _, row in df_para_inserir.iterrows():
                        last_row = ws.max_row + 1
                        ws.cell(row=last_row, column=col_indices['N° DOCUMENTO ITAIPU'] + 1).value = row['No. do Documento']
                        if 'DESCRIÇÃO' in col_indices:
                            ws.cell(row=last_row, column=col_indices['DESCRIÇÃO'] + 1).value = row['Título']

                        # Copia estilo da linha anterior
                        if linha_molde_idx > 2:
                            for col_num in range(1, max_coluna_real + 1):
                                copiar_estilo_seguro(
                                    ws.cell(row=linha_molde_idx, column=col_num),
                                    ws.cell(row=last_row, column=col_num)
                                )
                    yield (f" -> {len(df_para_inserir)} novas listas inseridas na Mestra.", 0.60)
                else:
                    yield (" -> Inserção ignorada ou nenhuma lista selecionada.", 0.60)

            # D. Atualizar Metadados
            count_update = 0
            for row_idx in range(3, ws.max_row + 1):
                codigo_planilha = ws.cell(row=row_idx, column=doc_col + 1).value
                if codigo_planilha:
                    codigo_planilha = str(codigo_planilha).strip()
                    novo_codigo = self._buscar_rdspp_mais_recente(codigo_planilha, df_api)

                    if codigo_planilha != novo_codigo:
                        yield f" -> Atualizando Mestra: {codigo_planilha} -> {novo_codigo}"
                        ws.cell(row=row_idx, column=doc_col + 1).value = novo_codigo

                    dados_reais = df_api[(df_api['No. do Documento'].str.strip() == novo_codigo) & (df_api['Current'] == True)]

                    if not dados_reais.empty:
                        for col_mestra, col_api in mapeamento_colunas.items():
                            if col_mestra in col_indices and col_api in dados_reais.columns:
                                val = dados_reais[col_api].iloc[0]
                                ws.cell(row=row_idx, column=col_indices[col_mestra] + 1).value = val
                        count_update += 1

            # CP 1.3: retry de PermissionError unificado via
            # `_salvar_com_retry_interativo` (delega para
            # core.excel.locking.save_with_retry).
            if not self._salvar_com_retry_interativo(wb, caminho_gerenciadora, callback_retry_lock):
                yield "[ERRO] Processo cancelado. A Planilha Mestra está aberta no Excel."
                return  # Aborta o fluxo

            yield f" -> Metadados atualizados ({count_update} linhas)."

        except Exception as e:
            yield f"[ERRO] Atualização Mapeamento: {e}"
            return

        # 5. Calcular Indicadores (Ler cada Status PMIB)
        yield ("Lendo fichas individuais e calculando estatísticas...", 0.75)
        resultados_por_rdspp = {}

        for _, (codigo_atual, caminho_arquivo) in codigos_renomeados.items():
            if os.path.basename(caminho_arquivo).startswith('~$'): continue

            if os.path.exists(caminho_arquivo):
                df_fichas, rdspp_lido = self._ler_status_pmib(codigo_atual, caminho_arquivo)
                if df_fichas is not None:
                    res = self._calcula_fichas(df_fichas, rdspp_lido)
                    res['caminho_absoluto_arquivo'] = caminho_arquivo  # Salvamos o caminho para gerar o link depois
                    resultados_por_rdspp[rdspp_lido] = res

        # 6. Gravar Indicadores na Mestra
        if resultados_por_rdspp:
            yield ("Gravando estatísticas na Planilha Mestra...", 0.90)
            try:
                wb = load_workbook(caminho_gerenciadora)
                ws = wb.active

                gerenciadora_map = {
                    'FICHAS EXISTENTES': 'total_fichas',
                    'FICHAS RECEBIDAS': 'fichas_recebidas',
                    'FICHAS COM O FORNECEDOR': 'fichas_com_fornecedor',
                    'FICHAS EM ELABORAÇÃO': 'fichas_em_elaboracao',
                    'INFO. DO FORNECEDOR COMPLETO': 'fichas_completas_info_fornecedor',
                    'VALORIZAÇÃO': 'fichas_com_valorizacao',
                    'FICHAS COM APLICAÇÃO - LMR FINALIZADA': 'fichas_com_aplicacao_lmr',
                    'FICHAS EM ANÁLISE DE ITAIPU': 'fichas_em_analise_ib',
                    'FICHAS EM CORREÇÃO': 'fichas_em_correcao',
                    'FICHAS APROVADAS': 'fichas_aprovadas',
                    'APTO PARA ENTREGA': 'fichas_aptas_para_entrega',
                    'ATRASO DE AUTORIZAÇÃO DE ENTREGA ITAIPU': 'atraso_autorizacao_itaipu',
                    'EQUIPAMENTOS ENTREGUES': 'equipamentos_entregue',
                    'LINK DA PLANILHA': 'caminho_absoluto_arquivo'  # <- NOVA COLUNA MAPEADA
                }

                # Recalcula índices (pois o arquivo pode ter mudado ou sido recarregado)
                col_indices = {}
                for col_idx, cell in enumerate(ws[2]):
                    if cell.value: col_indices[cell.value] = col_idx

                doc_col = col_indices.get('N° DOCUMENTO ITAIPU')
                status_rev_col = col_indices.get('STATUS DA REVISÃO')
                situacao_col = col_indices.get('SITUAÇÃO NO PMIB')

                if doc_col is not None:
                    for row_idx in range(3, ws.max_row + 1):
                        rdspp_doc = ws.cell(row=row_idx, column=doc_col + 1).value
                        if rdspp_doc:
                            rdspp_doc = str(rdspp_doc).strip()

                            # Pega os dados se o arquivo existir, senão retorna um dicionário vazio (garantindo que tudo zere)
                            dados = resultados_por_rdspp.get(rdspp_doc, {})

                            for col_name, key in gerenciadora_map.items():
                                if col_name in col_indices:
                                    celula = ws.cell(row=row_idx, column=col_indices[col_name] + 1)

                                    # Lógica especial apenas para a coluna de Link
                                    if key == 'caminho_absoluto_arquivo':
                                        caminho_arq = dados.get(key)
                                        if caminho_arq:
                                            try:
                                                caminho_relativo = os.path.relpath(caminho_arq, start=os.path.dirname(caminho_gerenciadora))
                                                celula.value = "Abrir Box"
                                                celula.hyperlink = caminho_relativo
                                                celula.font = openpyxl.styles.Font(color="0563C1", underline="single")
                                            except ValueError:
                                                celula.value = "Erro no Link"
                                        else:
                                            # Remove formatações antigas caso a planilha não exista mais
                                            celula.value = ""
                                            celula.hyperlink = None
                                            celula.font = openpyxl.styles.Font(color="000000", underline="none")
                                    else:
                                        celula.value = dados.get(key, 0)

                            # --- CÁLCULO DOS ÍNDICES % ---
                            total = dados.get('total_fichas', 0)
                            if total > 0:
                                analise = dados.get('fichas_em_analise_ib', 0)
                                correcao = dados.get('fichas_em_correcao', 0)
                                aprovadas = dados.get('fichas_aprovadas', 0)

                                idx_emi = ((analise + correcao) / total) * 100
                                idx_conc = (aprovadas / total) * 100

                                if 'ÍNDICE DE EMISSAO' in col_indices:
                                    ws.cell(row=row_idx, column=col_indices['ÍNDICE DE EMISSAO'] + 1).value = f"{idx_emi:.2f}%"
                                if 'ÍNDICE DE CONCLUSÃO' in col_indices:
                                    ws.cell(row=row_idx, column=col_indices['ÍNDICE DE CONCLUSÃO'] + 1).value = f"{idx_conc:.2f}%"
                            else:
                                # Zera os índices caso não existam fichas
                                if 'ÍNDICE DE EMISSAO' in col_indices:
                                    ws.cell(row=row_idx, column=col_indices['ÍNDICE DE EMISSAO'] + 1).value = "0.00%"
                                if 'ÍNDICE DE CONCLUSÃO' in col_indices:
                                    ws.cell(row=row_idx, column=col_indices['ÍNDICE DE CONCLUSÃO'] + 1).value = "0.00%"

                            # --- CASCATA DE PRIORIDADE: SITUAÇÃO NO PMIB ---
                            if situacao_col is not None:
                                status_revisao = ""
                                if status_rev_col is not None:
                                    status_revisao = str(ws.cell(row=row_idx, column=status_rev_col + 1).value or "").strip().upper()

                                ini = dados.get('fichas_para_iniciar', 0)
                                cria = dados.get('fichas_criadas', 0)
                                forn = dados.get('fichas_com_fornecedor', 0)
                                elab = dados.get('fichas_em_elaboracao', 0)
                                analise = dados.get('fichas_em_analise_ib', 0)
                                corr = dados.get('fichas_em_correcao', 0)
                                aprov = dados.get('fichas_aprovadas', 0)
                                na = dados.get('fichas_na', 0)

                                situacao = "EM ANDAMENTO"  # Fallback para misturas não mapeadas

                                if status_revisao == "LISTA NÃO EMITIDA":
                                    situacao = "LISTA NÃO EMITIDA"
                                elif status_revisao == "SEM LISTA":
                                    situacao = "SEM LISTA"
                                elif total == 0:
                                    situacao = "INICIAR"
                                elif ini > 0:
                                    situacao = "CRIAÇÃO DAS FICHAS EM PROCESSO"
                                elif corr > 0 and elab > 0:
                                    situacao = "CORREÇÃO / ELABORAÇÃO"
                                elif corr > 0 and aprov > 0:
                                    situacao = "EM CORREÇÃO / FINALIZADO"
                                elif corr == total:
                                    situacao = "EM CORREÇÃO"
                                elif analise > 0 and elab > 0:
                                    situacao = "EM PROCESSO / ANÁLISE ITAIPU"
                                elif analise == total:
                                    situacao = "EM ANÁLISE ITAIPU"
                                elif forn > 0 and elab > 0:
                                    situacao = "FORNECEDOR / ELABORAÇÃO"
                                elif elab > 0:
                                    situacao = "EM PROCESSO DE PREENCHIMENTO"
                                elif forn == total:
                                    situacao = "FICHAS COM O FORNECEDOR"
                                elif (aprov + na) == total and total > 0:
                                    situacao = "FINALIZADO"
                                elif cria > 0 and forn == 0 and elab == 0 and analise == 0 and corr == 0 and aprov == 0:
                                    # Se tem ficha criada e nenhuma ficha avançou para o fornecedor ou além
                                    situacao = "FICHAS CRIADAS"

                                ws.cell(row=row_idx, column=situacao_col + 1).value = situacao

                    # CP 1.3: retry de PermissionError unificado via
                    # `_salvar_com_retry_interativo` (delega para
                    # core.excel.locking.save_with_retry).
                    if not self._salvar_com_retry_interativo(wb, caminho_gerenciadora, callback_retry_lock):
                        yield "[ERRO] Processo cancelado. A Planilha Mestra está aberta no Excel."
                        return  # Aborta o fluxo

                    yield " -> Estatísticas gravadas com sucesso."

            except Exception as e:
                yield f"[ERRO] Gravação Estatísticas: {e}"
        else:
            yield " -> Nenhuma ficha processada para estatísticas."

        yield ("--- PROCESSO CONCLUÍDO ---", 1.0)
