import os
import pandas as pd
import traceback
import unicodedata
import re


class PMIBSearcher:
    def __init__(self):
        # Nomes comuns da aba, para garantir resiliência
        self.sheet_names = ["Lista de Materiais", "LISTA DE MATERIAIS", "Lista de materiais"]

    def _limpar_texto_parrudo(self, texto):
        """
        Remove acentos, espaços e pontuações, mantendo só letras (A-Z) e números (0-9).
        """
        if pd.isna(texto): return ""
        texto = str(texto).upper()
        # Remove acentos (ex: Á -> A, Ç -> C)
        texto = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode('utf-8')
        # Remove tudo que não for letra ou número (espaços, hífens, parênteses, etc)
        texto = re.sub(r'[^A-Z0-9]', '', texto)
        return texto

    def _extrair_codigo_itaipu(self, filename):
        """
        Extrai o código Itaipu (prefixo) do nome do arquivo.
        Ex: '4500063671.1234_STATUS_PMIB.xlsx' -> '4500063671.1234'
        """
        nome_base = filename.upper()
        if "_STATUS_PMIB" in nome_base:
            return nome_base.split("_STATUS_PMIB")[0].strip()
        return "DESCONHECIDO"

    def _encontrar_e_formatar_dataframe(self, filepath):
        """
        Lê as primeiras linhas para encontrar o cabeçalho dinamicamente (onde tem 'DESCRIÇÃO').
        Retorna o DataFrame formatado ou (None, mensagem_erro).
        """
        df_bruto = None
        aba_encontrada = ""

        # Tenta carregar a aba correta
        try:
            # Lê apenas as primeiras 15 linhas sem cabeçalho para procurar a palavra-chave
            for sheet in self.sheet_names:
                try:
                    # Lemos as primeiras linhas também como string para evitar conversões indesejadas prematuras
                    df_bruto = pd.read_excel(filepath, sheet_name=sheet, header=None, nrows=15, dtype=str)
                    aba_encontrada = sheet
                    break
                except ValueError:
                    continue  # Aba não encontrada, tenta a próxima

            if df_bruto is None or df_bruto.empty:
                return None, "Aba 'Lista de Materiais' não encontrada."

        except Exception as e:
            return None, f"Erro ao ler arquivo: {str(e)}"

        # Procura a palavra 'DESCRIÇÃO' nas primeiras 10 linhas
        header_idx = -1
        for idx, row in df_bruto.head(10).iterrows():
            linha_str = " ".join(row.fillna('').astype(str).str.upper())
            if "DESCRIÇÃO" in linha_str or "DESCRICAO" in linha_str:
                header_idx = idx
                break

        if header_idx == -1:
            return None, "Cabeçalho com a coluna 'DESCRIÇÃO' não encontrado nas primeiras 10 linhas."

        # Lê o arquivo completo agora usando a linha correta como cabeçalho
        try:
            # CORREÇÃO PRINCIPAL: dtype=str previne que o Pandas corte zeros à direita (ex: 1.50 -> 1.5)
            # ou converta números inteiros para float (ex: 123 -> 123.0)
            df_final = pd.read_excel(filepath, sheet_name=aba_encontrada, header=header_idx, dtype=str)

            # CORREÇÃO DE SEGURANÇA: astype(str) garante que colunas com nomes numéricos (ex: 2023) não quebrem o código
            df_final.columns = df_final.columns.astype(str).str.strip().str.replace('\n', ' ')
            return df_final, "OK"
        except Exception as e:
            return None, f"Erro ao carregar os dados: {str(e)}"

    def executar_busca(self, pasta_raiz, tipo_busca, termo_busca, coluna_especifica=None, callback_log=None):
        """
        Varre a pasta raiz buscando por arquivos _STATUS_PMIB e aplica a busca.
        """
        resultados = []
        arquivos_para_processar = []
        termo_busca = str(termo_busca).strip().upper()

        if callback_log: callback_log("Iniciando mapeamento de diretórios...")

        # 1. Varredura da pasta raiz
        for root, dirs, files in os.walk(pasta_raiz):
            for file in files:
                if "STATUS_PMIB" in file.upper() and not file.startswith('~$') and file.endswith(('.xlsx', '.xls', '.xlsm')):
                    arquivos_para_processar.append(os.path.join(root, file))

        total_arquivos = len(arquivos_para_processar)
        if total_arquivos == 0:
            if callback_log: callback_log("Nenhum arquivo _STATUS_PMIB encontrado na pasta selecionada.")
            return resultados

        if callback_log: callback_log(f"{total_arquivos} arquivos encontrados. Iniciando varredura interna...")

        # 2. Processamento dos arquivos
        for idx, caminho_completo in enumerate(arquivos_para_processar):
            nome_arquivo = os.path.basename(caminho_completo)
            pasta_arquivo = os.path.dirname(caminho_completo)
            codigo_itaipu = self._extrair_codigo_itaipu(nome_arquivo)

            if callback_log: callback_log(f"[{idx+1}/{total_arquivos}] Analisando: {nome_arquivo}...")

            df, status_msg = self._encontrar_e_formatar_dataframe(caminho_completo)

            if df is None:
                if callback_log: callback_log(f" -> IGNORADO: {status_msg}")
                continue

            match_encontrado = False

            # 3. Lógica de Busca
            try:
                if tipo_busca == 'direcionada' and coluna_especifica:
                    col_real = next((c for c in df.columns if coluna_especifica.upper() in str(c).upper()), None)

                    if col_real:
                        mascara = df[col_real].fillna('').astype(str).str.upper().str.contains(termo_busca, regex=False)
                        linhas_match = df[mascara]

                        if not linhas_match.empty:
                            match_encontrado = True
                            amostras = linhas_match[col_real].head(3).tolist()
                            amostra_str = " | ".join(map(str, amostras))

                            resultados.append({
                                'codigo_itaipu': codigo_itaipu,
                                'arquivo_nome': nome_arquivo,
                                'caminho_arquivo': caminho_completo,
                                'caminho_pasta': pasta_arquivo,
                                'coluna_match': col_real,
                                'amostra': amostra_str
                            })
                    else:
                        if callback_log: callback_log(f" -> Coluna '{coluna_especifica}' não existe neste arquivo.")

                elif tipo_busca == 'generalista':
                    # =========================================================
                    # BUSCA PARRUDA (Generalista)
                    # =========================================================
                    termo_normalizado = self._limpar_texto_parrudo(termo_busca)

                    if termo_normalizado:
                        # 2. Junta todas as colunas da linha em uma única grande string
                        linhas_em_texto = df.fillna('').astype(str).agg(' '.join, axis=1)

                        # 3. OTIMIZAÇÃO: Usando métodos nativos do Pandas para remover acentos (muito mais rápido que .apply lambda)
                        linhas_limpas = (
                            linhas_em_texto.str.upper()
                            .str.normalize('NFKD')
                            .str.encode('ascii', errors='ignore')
                            .str.decode('utf-8')
                        )
                        linhas_limpas = linhas_limpas.str.replace(r'[^A-Z0-9]', '', regex=True)

                        # 4. Busca exata dentro da string "amassada"
                        mascara_geral = linhas_limpas.str.contains(termo_normalizado, regex=False)
                        linhas_match = df[mascara_geral]

                        if not linhas_match.empty:
                            match_encontrado = True
                            resultados.append({
                                'codigo_itaipu': codigo_itaipu,
                                'arquivo_nome': nome_arquivo,
                                'caminho_arquivo': caminho_completo,
                                'caminho_pasta': pasta_arquivo,
                                'coluna_match': "Múltiplas (Busca Super Geral)",
                                'amostra': f"{len(linhas_match)} linha(s) encontrada(s)."
                            })

                if match_encontrado and callback_log:
                    callback_log(f" -> ✅ Match Encontrado no PMIB {codigo_itaipu}!")

            except Exception as e:
                if callback_log: callback_log(f" -> Erro ao processar busca: {str(e)}")
                traceback.print_exc()  # Útil para ver o erro no console caso aconteça

        if callback_log: callback_log(f"Busca finalizada! {len(resultados)} correspondência(s) encontrada(s).")
        return resultados
