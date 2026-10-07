import os
import pandas as pd
from openpyxl import load_workbook
import warnings
from collections import defaultdict

# Ignora avisos padrões do openpyxl
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================
CAMINHO_TEMP = r"C:\Users\223141044\Box\CMI - Consórcio Itaipu\11 - Ger. Engenharia\15 - PDM\SOBRESSALENTES - PMIB\sobressalentes_autorizados_202607210948.xlsx"
PASTA_RAIZ_STATUS = r"C:\Users\223141044\Box\CMI - Consórcio Itaipu\11 - Ger. Engenharia\15 - PDM\SOBRESSALENTES - PMIB" 


def carregar_pmibs_aptos(caminho):
    """Lê a planilha fonte e retorna um SET (conjunto) super rápido para busca."""
    print("[1/3] Lendo a planilha temporária de PMIBs aptos...")
    df_temp = pd.read_excel(caminho)
    
    if 'PMIB' not in df_temp.columns:
        raise ValueError("Coluna 'PMIB' não encontrada na planilha temporária.")
        
    codigos = set(df_temp['PMIB'].astype(str).str.strip().str.upper())
    # Limpa sujeiras que podem vir do pandas
    for lixo in ["NAN", "NAT", ""]:
        codigos.discard(lixo)
        
    print(f" -> Sucesso: {len(codigos)} códigos únicos carregados na memória.\n")
    return codigos


def processar_arquivos(pasta_raiz, codigos_aptos):
    print("[2/3] Varrendo pastas e editando arquivos (isso pode levar alguns minutos)...")
    
    # Dicionários para organizar o resultado final
    relatorio = {'atualizados': [], 'intactos': [], 'sem_template': [], 'erros': []}
    
    # APLICANDO SUA IDEIA: Um dicionário (mapa) para rastrear ONDE cada ficha estava
    # Estrutura: {'CODIGO_PMIB': ['caminho/arquivo1.xlsx', 'caminho/arquivo2.xlsx']}
    mapa_rastreio = defaultdict(list)

    for root, dirs, files in os.walk(pasta_raiz):
        for file in files:
            if file.startswith("~$") or not file.lower().endswith("_status_pmib.xlsx"):
                continue
                
            caminho_completo = os.path.join(root, file)
            
            try:
                wb = load_workbook(caminho_completo)
                sheet_name = 'Lista de Materiais'
                ws = wb[sheet_name] if sheet_name in wb.sheetnames else wb.active
                    
                mapa_colunas = {}
                header_row = None
                
                # Busca rápida de cabeçalho usando iter_rows (muito mais rápido que ler célula a célula)
                for row_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=10, values_only=True), start=1):
                    for col_idx, val in enumerate(row, start=1):
                        val_str = str(val or "").strip().upper()
                        if val_str == "CÓDIGO PMIB":
                            mapa_colunas['PMIB'] = col_idx
                            header_row = row_idx
                        elif val_str == "APTO PARA ENTREGA":
                            mapa_colunas['APTO'] = col_idx
                    
                    if 'PMIB' in mapa_colunas and 'APTO' in mapa_colunas:
                        break # Achou as duas, para de procurar no cabeçalho
                        
                if 'APTO' not in mapa_colunas:
                    relatorio['sem_template'].append(file)
                    wb.close()
                    continue
                    
                if 'PMIB' not in mapa_colunas:
                    relatorio['erros'].append(f"{file} (Faltando coluna CÓDIGO PMIB)")
                    wb.close()
                    continue
                    
                # 3. Edição Cirúrgica - Otimizada!
                alterou_algo = False
                col_pmib_idx = mapa_colunas['PMIB'] - 1 # iter_rows usa índice começando em 0
                col_apto_idx = mapa_colunas['APTO'] - 1
                
                # iter_rows só percorre as linhas que realmente existem (evita o bug de linhas infinitas vazias do Excel)
                for row in ws.iter_rows(min_row=header_row + 1, max_row=ws.max_row):
                    celula_pmib = row[col_pmib_idx]
                    celula_apto = row[col_apto_idx]
                    
                    val_pmib = str(celula_pmib.value or "").strip().upper()
                    
                    if not val_pmib: # Se não tem PMIB nessa linha, pula rápido
                        continue
                        
                    if val_pmib in codigos_aptos:
                        val_apto_atual = str(celula_apto.value or "").strip().upper()
                        
                        if val_apto_atual != "SIM":
                            celula_apto.value = "SIM"
                            alterou_algo = True
                            
                            # Registra no seu dicionário (mapa) que alteramos este PMIB neste arquivo
                            mapa_rastreio[val_pmib].append(file)
                            
                if alterou_algo:
                    wb.save(caminho_completo)
                    relatorio['atualizados'].append(file)
                    print(f" -> [ATUALIZADO] {file}")
                else:
                    relatorio['intactos'].append(file)
                    
                wb.close()
                
            except PermissionError:
                relatorio['erros'].append(f"{file} (Aberto no Excel - Acesso Negado)")
            except Exception as e:
                relatorio['erros'].append(f"{file} ({e})")
                
    return relatorio, mapa_rastreio


def executar_atualizacao():
    print(f"{'-'*60}\nINICIANDO ATUALIZAÇÃO EM LOTE - APTO PARA ENTREGA\n{'-'*60}")
    
    try:
        codigos_aptos = carregar_pmibs_aptos(CAMINHO_TEMP)
    except Exception as e:
        print(f"[ERRO FATAL] {e}")
        return
        
    relatorio, mapa_rastreio = processar_arquivos(PASTA_RAIZ_STATUS, codigos_aptos)
    
    # 4. Resumo de Auditoria
    print(f"\n{'-'*60}\n[3/3] RESUMO DE AUDITORIA\n{'-'*60}")
    total_arquivos = sum(len(lista) for lista in relatorio.values())
    
    print(f" Total de arquivos lidos: {total_arquivos}")
    print(f" [V] Arquivos alterados e salvos: {len(relatorio['atualizados'])}")
    print(f" [-] Arquivos já corretos (ignorados): {len(relatorio['intactos'])}")
    print(f" [!] Erros de leitura: {len(relatorio['erros'])}")
    print(f" [x] Fora do template: {len(relatorio['sem_template'])}")
    
    # Exibe o SEU Dicionário (Mapa) na tela de forma visual
    if mapa_rastreio:
        print(f"\n--- MAPA DE FICHAS ATUALIZADAS (DICIONÁRIO) ---")
        # Mostra os 10 primeiros apenas para não poluir demais a tela caso sejam milhares
        for i, (pmib, arquivos) in enumerate(list(mapa_rastreio.items())[:10]):
            print(f" PMIB {pmib} liberado no(s) arquivo(s): {', '.join(arquivos)}")
        if len(mapa_rastreio) > 10:
            print(f" ... e mais {len(mapa_rastreio) - 10} PMIBs atualizados.")

    # Exibir Erros e Alertas
    if relatorio['sem_template'] or relatorio['erros']:
        print("\n--- AVISOS IMPORTANTES ---")
        for arq in relatorio['sem_template']: print(f" [Atenção] Falta coluna APTO: {arq}")
        for err in relatorio['erros']: print(f" [Erro] {err}")

    print(f"\n{'-'*60}\nPROCESSO CONCLUÍDO!\n{'-'*60}")

if __name__ == "__main__":
    executar_atualizacao()