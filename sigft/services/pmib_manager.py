import os
import shutil
import zipfile
import pandas as pd
import openpyxl
from datetime import date
from openpyxl import load_workbook
from copy import copy
import warnings

from sigft import config
from sigft.core.excel import headers, locking, status_sheet
from sigft.services import autorizacao, status_pmib_arquivos

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

# =============================================================================
# Achar a aba certa  [2026-09-03]
# =============================================================================
# ⚠️ O código usava `wb.active` -- a aba que estava SELECIONADA quando a
# planilha foi salva pela última vez. Isso quebrou na cara do usuário:
#
#     [ERRO] Coluna 'N° DOCUMENTO ITAIPU' não encontrada na Mestra.
#
# Ele tinha salvado o arquivo com outra aba aberta, e o código foi procurar a
# coluna na aba errada. A planilha tem 3 abas (e ganhou uma quarta com a Lista
# de preços), então a chance de `wb.active` ser a certa só diminui.
#
# `wb.active` nunca foi uma forma de ACHAR uma aba: é só a que o Excel mostrará
# ao abrir. Achar exige procurar.
NOME_ABA_SOBRESSALENTES = "Acompanhamento Sobressalente"
COLUNA_CHAVE_SOBRESSALENTES = "N° DOCUMENTO ITAIPU"


def achar_aba(wb, nome_esperado, coluna_chave, linha_cabecalho=2):
    """A aba pelo NOME; não achando, a que TEM a coluna-chave.

    O fallback por conteúdo importa porque o nome da aba é editável pelo
    usuário — renomeá-la não deveria quebrar o app quando a estrutura continua
    lá. Devolve `(worksheet, motivo)`; `worksheet` é `None` se nenhuma servir,
    e `motivo` diz o que foi procurado, para o log poder ser específico.
    """
    if nome_esperado in wb.sheetnames:
        return wb[nome_esperado], f"aba '{nome_esperado}'"

    alvo = str(coluna_chave).strip().upper()
    for nome in wb.sheetnames:
        ws = wb[nome]
        for celula in ws[linha_cabecalho]:
            if celula.value and str(celula.value).strip().upper() == alvo:
                return ws, f"aba '{nome}' (achada pela coluna '{coluna_chave}')"

    return None, (
        f"nenhuma aba tem a coluna '{coluna_chave}' na linha {linha_cabecalho}. "
        f"Abas no arquivo: {', '.join(wb.sheetnames)}"
    )


# =============================================================================
# SITUAÇÃO NO PMIB (a "cascata")  [função pura desde 2026-10-05]
# =============================================================================
# A mesma cascata de prioridade que morava inline no passo 6; virou função para
# poder ser testada sem planilha. `dados` é o que `_calcula_fichas` devolve
# (total e contagem por STATUS, PMIB distinto, sem DUPLICADO); `status_revisao`
# é o STATUS DA REVISÃO da linha da mapeadora, já em maiúsculas.
def situacao_no_pmib(dados, status_revisao=""):
    total = dados.get('total_fichas', 0)
    ini = dados.get('fichas_para_iniciar', 0)
    cria = dados.get('fichas_criadas', 0)
    forn = dados.get('fichas_com_fornecedor', 0)
    elab = dados.get('fichas_em_elaboracao', 0)
    analise = dados.get('fichas_em_analise_ib', 0)
    corr = dados.get('fichas_em_correcao', 0)
    aprov = dados.get('fichas_aprovadas', 0)
    na = dados.get('fichas_na', 0)

    if status_revisao == "LISTA NÃO EMITIDA":
        return "LISTA NÃO EMITIDA"
    if status_revisao == "SEM LISTA":
        return "SEM LISTA"
    if total == 0:
        return "INICIAR"
    if ini > 0:
        return "CRIAÇÃO DAS FICHAS EM PROCESSO"
    if corr > 0 and elab > 0:
        return "CORREÇÃO / ELABORAÇÃO"
    if corr > 0 and aprov > 0:
        return "EM CORREÇÃO / FINALIZADO"
    if corr == total:
        return "EM CORREÇÃO"
    if analise > 0 and elab > 0:
        return "EM PROCESSO / ANÁLISE ITAIPU"
    if analise == total:
        return "EM ANÁLISE ITAIPU"
    if forn > 0 and elab > 0:
        return "FORNECEDOR / ELABORAÇÃO"
    if elab > 0:
        return "EM PROCESSO DE PREENCHIMENTO"
    if forn == total:
        return "FICHAS COM O FORNECEDOR"
    if (aprov + na) == total and total > 0:
        return "FINALIZADO"
    if cria > 0 and forn == 0 and elab == 0 and analise == 0 and corr == 0 and aprov == 0:
        # Tem ficha criada e nenhuma avançou para o fornecedor ou além
        return "FICHAS CRIADAS"
    return "EM ANDAMENTO"  # misturas não mapeadas


# =============================================================================
# Colunas do `_STATUS_PMIB` v2 que o recálculo da autorização lê  [T3-c]
# =============================================================================
# Casadas SEM acento e sem caixa (`autorizacao.normalizar`): um arquivo que
# passou por exportação pode ter "SITUACAO DA AUTORIZACAO".
COLUNAS_AUTORIZACAO = (
    config.COL_STATUS,
    config.COL_TIPO_ENTREGA,
    config.COL_DATA_EMAIL_ENTREGA,
    config.COL_SITUACAO_AUTORIZACAO,
    config.COL_DIAS_ATRASO,
    config.COL_EQUIPAMENTO_ENTREGUE,
)
# Até onde procurar o cabeçalho (está na linha 5 no v2, na 4 no layout antigo).
LINHAS_BUSCA_CABECALHO_STATUS = 10


def _o_que_o_openpyxl_apagaria(caminho):
    """O que um `save` do openpyxl apagaria deste arquivo: comentários em
    thread e listas suspensas gravadas como extensão. Lista vazia = nada.

    A mapeadora continua sendo gravada pelo openpyxl (ver o passo 4): hoje ela
    não tem nenhum dos dois. Se alguém comentar nela, o log avisa ANTES de o
    comentário sumir, em vez de ele simplesmente desaparecer."""
    try:
        with zipfile.ZipFile(caminho) as z:
            nomes = z.namelist()
            perdas = []
            if any(n.startswith("xl/threadedComments/") for n in nomes):
                perdas.append("comentários em thread")
            if any(n.startswith("xl/worksheets/") and n.endswith(".xml")
                   and b"x14:dataValidation" in z.read(n) for n in nomes):
                perdas.append("listas suspensas de extensão (x14)")
            return perdas
    except (OSError, zipfile.BadZipFile):
        return []


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
                # Layout v2 (04/10/2026). A SITUAÇÃO substituiu o APTO, que
                # continua aqui para os arquivos que ainda não migraram.
                'TIPO DE ENTREGA': 'TIPO DE ENTREGA',
                'SITUAÇÃO DA AUTORIZAÇÃO': 'SITUAÇÃO DA AUTORIZAÇÃO',
                'DIAS DE ATRASO': 'DIAS DE ATRASO',
                'APTO PARA ENTREGA': 'APTO PARA ENTREGA',
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
        """Total de fichas e contagem por STATUS -- só o que a cascata da
        SITUAÇÃO NO PMIB usa.

        [2026-10-05, T3-e] As outras contagens (recebidas, completas,
        valorização, LMR, entregues, aptas e o atraso de Itaipu) iam para
        colunas da mapeadora que saíram em 05/10/2026: a mapeadora virou
        CADASTRO, e quem conta, item a item dos `_STATUS_PMIB`, é o Power BI
        v2. O atraso era calculado com 14 dias CORRIDOS; a regra vigente (15
        dias úteis) mora em `services/autorizacao.py` e é gravada linha a
        linha no próprio `_STATUS_PMIB` (`_atualizar_autorizacao`).
        """
        if 'CÓDIGO PMIB' not in df.columns: return {}
        df['CÓDIGO PMIB'] = df['CÓDIGO PMIB'].astype(str).str.strip().replace('', pd.NA)
        df = df[df['CÓDIGO PMIB'].notna()]

        # Linha "DUPLICADO" = o mesmo item repetido na mesma lista: não é
        # ficha nova, a ficha conta pela outra linha.
        if 'STATUS' in df.columns:
            df = df[df['STATUS'].astype(str).str.strip().str.upper() != 'DUPLICADO']

        # `.copy()`: DataFrame independente (sem o aviso de cópia do pandas)
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

        resultados = {'RDS_PP': rdspp, 'total_fichas': int(total_fichas)}

        if 'STATUS' in df_unicos.columns:
            # strip + upper: "Aprovado " conta como APROVADO, como na
            # referência do kit e no Power BI.
            status = df_unicos['STATUS'].astype(str).str.strip().str.upper()
            for status_excel, chave_dict in status_map.items():
                resultados[chave_dict] = int((status == status_excel).sum())

        return resultados

    # --- SITUAÇÃO DA AUTORIZAÇÃO E DIAS DE ATRASO NO `_STATUS_PMIB` [T3-c] ---
    def _atualizar_autorizacao(self, caminho, hoje, callback_retry_lock=None):
        """Recalcula e grava SITUAÇÃO DA AUTORIZAÇÃO e DIAS DE ATRASO de cada
        linha do `_STATUS_PMIB` -- e lê a revisão em uso (T3-f).

        Generator: entrega as linhas de log e DEVOLVE (`return`) um dicionário
        para o passo 6: `revisao_em_uso` (str | None), `calculado` (o arquivo é
        v2 e a regra rodou nele) e `gravado` (alguma coisa mudou e foi gravada).

        - A regra é a de `services/autorizacao.py` (15 dias úteis); aqui só se
          lê, compara e grava.
        - Sem a coluna SITUAÇÃO DA AUTORIZAÇÃO (layout antigo) nada é gravado:
          o arquivo sai intocado, e o log diz por quê.
        - Grava SÓ as células que mudaram, pelo editor cirúrgico (`StatusPMIB`):
          os comentários em thread e as listas suspensas ficam.
        - DIAS DE ATRASO é número: célula que herdou formato de data ganha
          formato Geral ao ser gravada (senão 4 aparece como 04/01/1900).
        - Grava o nome definido `sigft_calculado_em` com a data do cálculo.
        - Arquivo aberto no Excel: pergunta (`callback_retry_lock(caminho)`); se
          a pessoa desistir, o log diz e o fluxo segue com o próximo arquivo.
        """
        nome = os.path.basename(caminho)
        resultado = {'revisao_em_uso': None, 'calculado': False, 'gravado': False}

        if not caminho.lower().endswith(".xlsx"):
            yield f"[AVISO] {nome}: formato antigo ({os.path.splitext(nome)[1]}), não é lido nem gravado. Salve como .xlsx."
            return resultado

        painel = status_sheet.StatusPMIB(caminho, config.ABA_LISTA_MATERIAIS)
        chaves = {config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB, config.COL_DESCRICAO: config.COL_DESCRICAO}
        chaves.update({coluna: coluna for coluna in COLUNAS_AUTORIZACAO})
        try:
            col_map, header_row = painel.abrir(
                keywords=chaves, required=[config.COL_CODIGO_PMIB],
                max_row=LINHAS_BUSCA_CABECALHO_STATUS, normalize=autorizacao.normalizar)
        except KeyError:
            yield f"[AVISO] {nome}: não tem a aba '{config.ABA_LISTA_MATERIAIS}'. Não lido."
            return resultado
        except Exception as e:
            yield f"[AVISO] {nome}: não consegui abrir ({type(e).__name__}: {e}). Não lido."
            return resultado

        try:
            if header_row is None:
                yield (f"[AVISO] {nome}: cabeçalho com '{config.COL_CODIGO_PMIB}' não encontrado nas "
                       f"{LINHAS_BUSCA_CABECALHO_STATUS} primeiras linhas. Não lido.")
                return resultado

            # T3-f: a revisão em uso, na linha de texto ACIMA do cabeçalho.
            linhas_acima = []
            if header_row > 1:
                linhas_acima = list(headers.rows_from_worksheet(
                    painel.ws, max_row=header_row - 1, max_col=min(painel.ws.max_column or 1, 30)))
            resultado['revisao_em_uso'] = status_pmib_arquivos.revisao_acima_do_cabecalho(
                linhas_acima, header_row)
            if resultado['revisao_em_uso'] is None:
                yield (f" -> {nome}: sem a linha '{config.TEXTO_LINHA_REVISAO}...' (ou sem revisão nela): "
                       "a REVISÃO EM USO da mapeadora não muda.")

            if config.COL_SITUACAO_AUTORIZACAO not in col_map:
                yield (f" -> {nome}: arquivo sem layout v2 (sem '{config.COL_SITUACAO_AUTORIZACAO}'): "
                       "situação e dias de atraso não são gravados.")
                return resultado
            faltam = [c for c in COLUNAS_AUTORIZACAO if c not in col_map]
            if faltam:
                yield f"[AVISO] {nome}: layout v2 incompleto (falta {', '.join(faltam)}). Nada gravado."
                return resultado

            ws = painel.ws
            col = col_map.__getitem__
            # Até a última linha com DESCRIÇÃO (as de baixo são formatação vazia).
            fim = header_row
            col_desc = col_map.get(config.COL_DESCRICAO)
            for r in range(header_row + 1, ws.max_row + 1):
                if col_desc is None or ws.cell(row=r, column=col_desc).value not in (None, ""):
                    fim = r

            alteradas = 0
            for r in range(header_row + 1, fim + 1):
                atual = ws.cell(row=r, column=col(config.COL_SITUACAO_AUTORIZACAO)).value
                celula_dias = ws.cell(row=r, column=col(config.COL_DIAS_ATRASO))
                situacao, dias = autorizacao.situacao_autorizacao(
                    ws.cell(row=r, column=col(config.COL_DATA_EMAIL_ENTREGA)).value,
                    atual,
                    ws.cell(row=r, column=col(config.COL_EQUIPAMENTO_ENTREGUE)).value,
                    hoje,
                    celula_dias.value,
                    ws.cell(row=r, column=col(config.COL_TIPO_ENTREGA)).value,
                    ws.cell(row=r, column=col(config.COL_STATUS)).value,
                )
                if autorizacao.normalizar(situacao) != autorizacao.normalizar(atual):
                    painel.escrever(r, col(config.COL_SITUACAO_AUTORIZACAO), situacao or None)
                    alteradas += 1
                # Número com formato de data herdado da vizinha também é
                # regravado: o valor não muda, o formato vira Geral.
                if dias != autorizacao.dias_da_celula(celula_dias.value) or (
                        dias is not None and getattr(celula_dias, "is_date", False) is True):
                    painel.escrever(r, col(config.COL_DIAS_ATRASO), dias, formato_geral=True)
                    alteradas += 1

            calculado_em = f'"{hoje.isoformat()}"'
            vai_gravar = bool(alteradas) or self._nome_definido(painel.wb, config.NOME_CALCULADO_EM) != calculado_em
            if vai_gravar:
                painel.definir_nome(config.NOME_CALCULADO_EM, calculado_em)

            def _perguntar(_tentativa, _erro):
                return bool(callback_retry_lock(caminho)) if callback_retry_lock else False

            try:
                painel.salvar(on_locked=_perguntar)
            except PermissionError:
                yield (f"[AVISO] {nome} está aberto no Excel: situação e dias de atraso NÃO foram gravados "
                       "nesta rodada. Feche o arquivo e rode de novo.")
                return resultado
            except Exception as e:
                yield f"[AVISO] {nome}: falha ao gravar ({type(e).__name__}: {e}). Nada gravado."
                return resultado

            resultado['calculado'] = True
            resultado['gravado'] = vai_gravar
            if alteradas:
                yield f" -> {nome}: {alteradas} célula(s) de situação/dias de atraso atualizada(s)."
            return resultado
        finally:
            painel.fechar()

    @staticmethod
    def _nome_definido(wb, nome):
        """O texto de um nome definido global do workbook (openpyxl), ou `None`."""
        try:
            definido = wb.defined_names.get(nome)
        except Exception:
            return None
        return getattr(definido, "attr_text", None) if definido is not None else None

    # --- FLUXO PRINCIPAL EXECUTADO PELO APP ---
    def executar_fluxo(self, caminho_api, pasta_raiz_status, caminho_gerenciadora, callback_confirm=None,
                       callback_retry_lock=None, hoje=None):
        """
        Orquestra todo o processo de gerenciamento.
        Yields: Logs de progresso.

        `callback_retry_lock`: chamado SEM argumento quando a mapeadora está
        aberta no Excel (desistir aborta o fluxo), e com o CAMINHO quando é um
        `_STATUS_PMIB` (desistir pula só aquele arquivo).

        `hoje` (T3-b): a data do cálculo da autorização; padrão, hoje. Existe
        para o kit de teste ser reprodutível (`hoje=date(2026, 10, 10)`).
        """
        hoje = hoje or date.today()

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
        # [2026-10-05, T3-a] Pastas de teste, obsoletas e cópias ficam de fora
        # (`status_pmib_arquivos`). O `os.walk` daqui entrava em
        # `testes_autospec/`, e a cópia de teste virava o link "Abrir Box" da
        # mapeadora. Todo arquivo deixado de fora aparece no log, com o motivo.
        yield ("Buscando arquivos _STATUS_PMIB na pasta raiz...", 0.15)
        levantamento = status_pmib_arquivos.listar(pasta_raiz_status)
        for caminho, motivo in levantamento.ignorados:
            yield f" -> Ignorado ({motivo}): {os.path.relpath(caminho, pasta_raiz_status)}"
        for codigo, escolhido, descartados in levantamento.repetidos:
            yield (f"[AVISO] Mais de um _STATUS_PMIB vivo para {codigo}: usando o modificado por último, "
                   f"{os.path.relpath(escolhido, pasta_raiz_status)}. Ignorado(s): "
                   + ", ".join(os.path.relpath(d, pasta_raiz_status) for d in descartados))
        lista_documentos = levantamento.vivos

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
        # A mapeadora continua sendo gravada pelo openpyxl (insere linhas,
        # cria a aba de preços...): hoje ela não tem comentário em thread nem
        # lista suspensa de extensão, que ele apagaria. Se passar a ter, avisa
        # ANTES -- os `_STATUS_PMIB`, que têm, são gravados pelo editor
        # cirúrgico (`StatusPMIB`).
        perdas = _o_que_o_openpyxl_apagaria(caminho_gerenciadora)
        if perdas:
            yield (f"[AVISO] A planilha de mapeamento tem {' e '.join(perdas)}, que esta gravação vai APAGAR "
                   "(o openpyxl não os preserva). Para não perder, use Anotação (Nota) em vez de Comentário.")
        try:
            wb = load_workbook(caminho_gerenciadora)
            ws, motivo = achar_aba(
                wb, NOME_ABA_SOBRESSALENTES, COLUNA_CHAVE_SOBRESSALENTES)
            if ws is None:
                yield f"[ERRO] Não achei a aba de sobressalentes: {motivo}"
                wb.close()
                return
            yield f" -> Usando a {motivo}."

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

        # 5. Recalcular a autorização (T3-c) e ler cada Status PMIB
        yield ("Recalculando a autorização de Itaipu e lendo as fichas...", 0.75)
        resultados_por_rdspp = {}
        calculados = gravados = 0

        for _, (codigo_atual, caminho_arquivo) in codigos_renomeados.items():
            if not os.path.exists(caminho_arquivo):
                yield f"[AVISO] {os.path.basename(caminho_arquivo)} sumiu da pasta durante o processo. Não lido."
                continue

            # ANTES da leitura: as contagens e o painel veem o que acabou de
            # ser gravado.
            autorizacao_lida = yield from self._atualizar_autorizacao(caminho_arquivo, hoje, callback_retry_lock)
            calculados += bool(autorizacao_lida['calculado'])
            gravados += bool(autorizacao_lida['gravado'])

            df_fichas, rdspp_lido = self._ler_status_pmib(codigo_atual, caminho_arquivo)
            if df_fichas is None:
                yield f"[AVISO] {os.path.basename(caminho_arquivo)}: não consegui ler a lista de materiais. Fora da contagem."
                continue
            res = self._calcula_fichas(df_fichas, rdspp_lido)
            res['caminho_absoluto_arquivo'] = caminho_arquivo  # Salvamos o caminho para gerar o link depois
            res['revisao_em_uso'] = autorizacao_lida['revisao_em_uso']
            resultados_por_rdspp[rdspp_lido] = res

        yield (f" -> Autorização de Itaipu calculada em {calculados} _STATUS_PMIB (data do cálculo: "
               f"{hoje.strftime('%d/%m/%Y')}): {gravados} gravado(s), {calculados - gravados} já em dia.")

        # 6. Gravar na Mestra: link, SITUAÇÃO NO PMIB e REVISÃO EM USO
        # [2026-10-05, T3-g] A mapeadora virou CADASTRO (decisão do Luan,
        # 05/10/2026): as contagens (FICHAS EXISTENTES ... ÍNDICE DE CONCLUSÃO)
        # saem de cada `_STATUS_PMIB` pelo Power BI v2, e o bloco de colunas
        # foi retirado da aba. O Gestão PMIB grava só o LINK DA PLANILHA, a
        # cascata da SITUAÇÃO NO PMIB e a REVISÃO EM USO (lida do próprio
        # `_STATUS_PMIB`). Colunas achadas pelo nome da linha 2; a que não
        # existir é pulada, sem erro. As de pessoas (STATUS REAL, RESPONSÁVEL,
        # OBSERVAÇÃO...) e a fórmula do CÓDIGO DO PROJETO nunca são tocadas.
        #
        # A mapeadora é gravada pelo openpyxl: não tem comentário em thread nem
        # lista suspensa de extensão (as mensagens de validação são padrão e
        # sobrevivem). Isso deixa de valer se alguém comentar nela -- o passo 4
        # avisa no log quando acontecer.
        if resultados_por_rdspp:
            yield ("Gravando link, situação e revisão em uso na Planilha Mestra...", 0.90)
            try:
                wb = load_workbook(caminho_gerenciadora)
                ws, motivo = achar_aba(
                    wb, NOME_ABA_SOBRESSALENTES, COLUNA_CHAVE_SOBRESSALENTES)
                if ws is None:
                    yield f"[ERRO] Não achei a aba de sobressalentes: {motivo}"
                    wb.close()
                    return

                # Recalcula índices (pois o arquivo pode ter mudado ou sido recarregado)
                col_indices = {}
                for col_idx, cell in enumerate(ws[2]):
                    if cell.value: col_indices[cell.value] = col_idx

                doc_col = col_indices.get('N° DOCUMENTO ITAIPU')
                status_rev_col = col_indices.get('STATUS DA REVISÃO')
                situacao_col = col_indices.get('SITUAÇÃO NO PMIB')
                link_col = col_indices.get('LINK DA PLANILHA')
                revisao_col = col_indices.get('REVISÃO EM USO')
                ultima_rev_col = col_indices.get('ÚLTIMA REVISÃO EMITIDA')
                revisoes_mudadas = 0

                if doc_col is not None:
                    for row_idx in range(3, ws.max_row + 1):
                        rdspp_doc = ws.cell(row=row_idx, column=doc_col + 1).value
                        if not rdspp_doc:
                            continue
                        rdspp_doc = str(rdspp_doc).strip()

                        # Sem arquivo vivo para a lista: dicionário vazio (link
                        # apagado, cascata em INICIAR, revisão intocada).
                        dados = resultados_por_rdspp.get(rdspp_doc, {})

                        # --- LINK DA PLANILHA ---
                        if link_col is not None:
                            celula = ws.cell(row=row_idx, column=link_col + 1)
                            caminho_arq = dados.get('caminho_absoluto_arquivo')
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

                        # --- REVISÃO EM USO (T3-f) ---
                        revisao = dados.get('revisao_em_uso')
                        if revisao_col is not None and revisao:
                            celula = ws.cell(row=row_idx, column=revisao_col + 1)
                            # Mesma revisão da ÚLTIMA EMITIDA: grava o valor DE LÁ
                            # (mesmo tipo, texto ou número), para a formatação
                            # condicional G≠C não acender por "1" ≠ 1.
                            novo = revisao
                            if ultima_rev_col is not None:
                                ultima = ws.cell(row=row_idx, column=ultima_rev_col + 1).value
                                if ultima is not None and autorizacao.normalizar(ultima) == autorizacao.normalizar(revisao):
                                    novo = ultima
                            if celula.value != novo:
                                celula.value = novo
                                revisoes_mudadas += 1

                        # --- CASCATA DE PRIORIDADE: SITUAÇÃO NO PMIB ---
                        if situacao_col is not None:
                            status_revisao = ""
                            if status_rev_col is not None:
                                status_revisao = str(ws.cell(row=row_idx, column=status_rev_col + 1).value or "").strip().upper()
                            ws.cell(row=row_idx, column=situacao_col + 1).value = situacao_no_pmib(dados, status_revisao)

                    # CP 1.3: retry de PermissionError unificado via
                    # `_salvar_com_retry_interativo` (delega para
                    # core.excel.locking.save_with_retry).
                    if not self._salvar_com_retry_interativo(wb, caminho_gerenciadora, callback_retry_lock):
                        yield "[ERRO] Processo cancelado. A Planilha Mestra está aberta no Excel."
                        return  # Aborta o fluxo

                    yield (f" -> Mapeadora gravada: link e situação no PMIB de cada lista; "
                           f"revisão em uso alterada em {revisoes_mudadas} lista(s).")

            except Exception as e:
                yield f"[ERRO] Gravação na Mestra: {e}"
        else:
            yield " -> Nenhuma ficha processada para a mapeadora."

        # ---------------------------------------------------------------
        # 6. Aba "Lista de preços Follow-up"  [2026-09-03]
        # ---------------------------------------------------------------
        # Pedido do usuário: "sempre na atualização do PMIB manager devemos
        # atualizar essa aba". Roda por último, depois de a aba de
        # sobressalentes estar gravada.
        #
        # Envolvido em try/except de propósito: uma falha aqui não pode
        # derrubar o resto do fluxo, que já gravou tudo o que interessa.
        yield ("Atualizando a aba Lista de preços Follow-up...", 0.92)
        try:
            for linha in self._atualizar_lista_precos(
                    caminho_gerenciadora, df_api, callback_retry_lock):
                yield linha
        except Exception as e:
            yield f"[ERRO] Lista de preços Follow-up: {type(e).__name__}: {e}"

        # ---------------------------------------------------------------
        # 7. Aba "Atividades"  [2026-09-03]
        # ---------------------------------------------------------------
        yield ("Atualizando a aba Atividades...", 0.97)
        try:
            for linha in self._atualizar_atividades(
                    caminho_gerenciadora, df_api, callback_retry_lock):
                yield linha
        except Exception as e:
            yield f"[ERRO] Atividades: {type(e).__name__}: {e}"

        yield ("--- PROCESSO CONCLUÍDO ---", 1.0)

    def _atualizar_atividades(self, caminho_gerenciadora, df_api, callback_retry_lock=None):
        """Atualiza a aba "Atividades": o CÓDIGO ITAIPU e os totais dos grupos.

        [2026-09-03] Pedido do usuário. Duas coisas:

        1. o `CÓDIGO ITAIPU` das linhas de grupo passa a acompanhar o RDS-PP
           vigente, pelo mesmo `_buscar_rdspp_mais_recente` que a aba de
           sobressalentes usa;
        2. as fórmulas de agregação viram VALOR calculado — decisão do usuário.

        ⚠️ **As fórmulas da planilha estão erradas hoje**, e não é suposição:
        comparando o cálculo com o que o Excel produz, 15 linhas batem e 2
        divergem — nas duas, o intervalo fixo da fórmula (`$A59:$A59`) não
        acompanhou linhas acrescentadas depois. A `L58` vinha dizendo "1
        atividade" para um grupo de 4. Gravar o valor calculado CORRIGE esses
        dois números.

        O app escreve só as 7 colunas de total e o código. `DESCRIÇÃO`,
        `STATUS`, `COM QUEM ESTÁ`, `DETALHE` e `CRITICIDADE` são do usuário.
        """
        from openpyxl import load_workbook

        from sigft.services import atividades as at

        wb = load_workbook(caminho_gerenciadora)
        if "Atividades" not in wb.sheetnames:
            yield " -> Aba 'Atividades' não encontrada; nada a fazer."
            wb.close()
            return

        ws = wb["Atividades"]

        # ⚠️ DOIS workbooks, e isto não é desperdício.
        #
        # `load_workbook` sem `data_only` devolve a FÓRMULA em `.value` — a
        # string `"=FALSE()"`, não `False`. Ler daí faria o cálculo tratar
        # texto de fórmula como dado: `CONCLUÍDA` traz `=FALSE()` em dezenas de
        # linhas, e as datas dos grupos são todas fórmulas. Na primeira versão
        # isto passou despercebido porque a contagem deu certo por acidente
        # (`"=FALSE()"` não está na lista de valores verdadeiros).
        #
        # E não dá para usar só `data_only=True`: esse workbook PERDE as
        # fórmulas ao salvar, o que destruiria as das outras abas.
        #
        # Então: um para LER valores, outro para ESCREVER. É o mesmo padrão que
        # `services/analyzer.py` adotou em 2026-08-26, pelo mesmo motivo.
        wb_valores = load_workbook(caminho_gerenciadora, data_only=True)
        ws_valores = wb_valores["Atividades"]

        def _valor(r, coluna):
            return ws_valores.cell(row=r, column=coluna).value

        linhas = []
        for r in range(at.LINHA_CABECALHO + 1, ws.max_row + 1):
            linhas.append({
                "_linha": r,
                "nv": _valor(r, at.COL_NV),
                "codigo": _valor(r, at.COL_CODIGO_ITAIPU),
                "concluida": _valor(r, at.COL_CONCLUIDA),
                "status": _valor(r, at.COL_STATUS),
                "data_prevista_inicio": _valor(r, at.COL_DATA_PREVISTA_INICIO) or "",
                "data_inicio": _valor(r, at.COL_DATA_INICIO) or "",
                "previsao_termino": _valor(r, at.COL_PREVISAO_TERMINO) or "",
                "data_termino": _valor(r, at.COL_DATA_TERMINO) or "",
            })
        wb_valores.close()

        # --- 1. CÓDIGO ITAIPU com o RDS-PP vigente ----------------------
        renomeados = 0
        for indice in at.linhas_de_grupo(linhas):
            codigo = linhas[indice].get("codigo")
            if not codigo:
                continue
            atual = self._buscar_rdspp_mais_recente(str(codigo).strip(), df_api)
            if atual and atual != str(codigo).strip():
                ws.cell(row=linhas[indice]["_linha"], column=at.COL_CODIGO_ITAIPU).value = atual
                yield f"   RDS-PP: {str(codigo).strip()} -> {atual}"
                renomeados += 1

        # --- 2. Totais dos grupos, no lugar das fórmulas ----------------
        totais = at.recalcular(linhas)
        for indice, valores in totais.items():
            r = linhas[indice]["_linha"]
            ws.cell(row=r, column=at.COL_ATIVIDADES).value = valores["atividades"]
            ws.cell(row=r, column=at.COL_CONCLUIDAS).value = valores["concluidas"]
            ws.cell(row=r, column=at.COL_TRAVADAS).value = valores["travadas"]
            ws.cell(row=r, column=at.COL_DATA_PREVISTA_INICIO).value = valores["data_prevista_inicio"]
            ws.cell(row=r, column=at.COL_DATA_INICIO).value = valores["data_inicio"]
            ws.cell(row=r, column=at.COL_PREVISAO_TERMINO).value = valores["previsao_termino"]
            ws.cell(row=r, column=at.COL_DATA_TERMINO).value = valores["data_termino"]

        if not self._salvar_com_retry_interativo(wb, caminho_gerenciadora, callback_retry_lock):
            yield "[ERRO] A planilha está aberta no Excel. A aba Atividades NÃO foi salva."
            return

        yield (f" -> Atividades: {len(totais)} grupo(s) recalculado(s), "
               f"{renomeados} código(s) atualizado(s) pelo RDS-PP.")

    def _atualizar_lista_precos(self, caminho_gerenciadora, df_api, callback_retry_lock=None):
        """Cria (se preciso) e atualiza a aba "Lista de preços Follow-up".

        [2026-09-03] Ver
        `docs/superpowers/specs/2026-09-03-lista-precos-followup-design.md`.

        A REGRA de pareamento não mora aqui — está em `services/lista_precos.py`,
        que se prova sem planilha nenhuma. Aqui está só a escrita.

        ⚠️ `AÇÃO` e `OBSERVAÇÕES` são do usuário e NUNCA são sobrescritas: a
        atualização casa por `N° DOCUMENTO ITAIPU` e escreve célula a célula
        nas 10 colunas do app. Recriar a aba apagaria a decisão dele, que é o
        conteúdo mais caro que ela guarda.
        """
        from datetime import datetime

        from openpyxl import load_workbook

        from sigft.services import lista_precos as lp
        from sigft.services import lista_precos_planilha as lpp

        historico = df_api.to_dict("records")
        levantado = lp.levantar(historico)
        if not levantado:
            yield " -> Nenhuma lista de preços vigente encontrada no Aconex."
            return

        wb = load_workbook(caminho_gerenciadora)
        criou = lpp.NOME_ABA not in wb.sheetnames
        ws = lpp.criar_aba(wb)
        if criou:
            yield f" -> Aba '{lpp.NOME_ABA}' criada."

        colunas = lpp.mapa_de_colunas(ws)
        existentes = lpp.linha_por_documento(ws, colunas)
        hoje = datetime.now().strftime("%d/%m")

        novas, atualizadas, alertas = 0, 0, 0

        for entrada in levantado:
            precos = entrada["precos"]
            codigo = str(precos.get(lp.COL_DOC) or "").strip()
            if not codigo:
                continue

            linha = existentes.get(codigo)
            if linha is None:
                linha = ws.max_row + 1 if ws.max_row >= lpp.LINHA_CABECALHO else lpp.LINHA_CABECALHO + 1
                existentes[codigo] = linha
                novas += 1
            else:
                atualizadas += 1

            valores = {
                "N° DOCUMENTO ITAIPU": codigo,
                "N° DOCUMENTO CMI": precos.get("Controle do Emissor"),
                "ÚLTIMA REVISÃO EMITIDA": precos.get("Revisão"),
                "STATUS DA REVISÃO": precos.get("Status"),
                "DATA DE ATUALIZAÇÃO": precos.get("Data de Alteração"),
                "DESCRIÇÃO": precos.get("Título"),
                "ESPECIFICAÇÃO TÉCNICA": precos.get("Especialidade"),
                "CAPÍTULO": precos.get("Subespecialidade"),
                "LISTA DE SOBRESSALENTES": entrada["lista"] or "",
                "ALERTA RDS-PP": entrada["alerta"],
            }
            for titulo, valor in valores.items():
                if titulo in colunas:
                    ws.cell(row=linha, column=colunas[titulo]).value = valor

            if entrada["alerta"]:
                alertas += 1

            # OBSERVAÇÕES: ACRESCENTA, nunca substitui -- e não duplica a
            # mesma linha a cada execução, senão um documento parado com
            # alerta acumularia uma linha por rodada até a célula ficar
            # ilegível.
            recado = lp.texto_de_observacao(entrada, hoje)
            coluna_obs = colunas.get("OBSERVAÇÕES")
            if recado and coluna_obs:
                celula = ws.cell(row=linha, column=coluna_obs)
                atual = str(celula.value or "")
                nucleo = recado.split("] ", 1)[-1]
                if nucleo not in atual:
                    celula.value = f"{atual}\n{recado}".strip() if atual else recado

        if not self._salvar_com_retry_interativo(wb, caminho_gerenciadora, callback_retry_lock):
            yield "[ERRO] A planilha está aberta no Excel. A aba de preços NÃO foi salva."
            return

        yield (f" -> Lista de preços: {novas} nova(s), {atualizadas} atualizada(s), "
               f"{alertas} com alerta de RDS-PP.")
