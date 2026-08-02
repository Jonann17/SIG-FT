import os
import time
import shutil
import tempfile
from unidecode import unidecode
import xlwings as xw
from deep_translator import GoogleTranslator, MyMemoryTranslator


class TechnicalTranslator:
    def __init__(self):
        self.stop_flag = False

    def request_stop(self):
        """Sinaliza para o loop de processamento parar."""
        self.stop_flag = True

    def _remover_caracteres_especiais(self, texto):
        if texto is None: return ""
        texto = str(texto)
        return unidecode(texto)

    def _traduzir_hibrido(self, texto):
        """
        Lógica original de tradução: Google -> Failover para MyMemory.
        """
        if texto is None or str(texto).strip() == "":
            return ""

        texto_str = str(texto)

        # Filtros de ignorar
        if texto_str.strip() in ["-", "N/A", "NA", ".", "0", 0]:
            return texto_str

        # Tentativa 1: Google
        try:
            tradutor_google = GoogleTranslator(source='pt', target='es')
            return tradutor_google.translate(texto_str)
        except Exception:
            pass  # Falha silenciosa, tenta o próximo

        # Tentativa 2: MyMemory
        try:
            time.sleep(1)  # Delay de segurança original
            tradutor_memory = MyMemoryTranslator(source='pt', target='es')
            return tradutor_memory.translate(texto_str)
        except Exception:
            return texto_str  # Retorna original se tudo falhar

    def processar_arquivo(self, caminho_original):
        """
        Processa um único arquivo Excel.
        Yields: Mensagens de log para a interface e Status finais ("PARADO", "SUCESSO", "ERRO").
        """
        self.stop_flag = False
        nome_arquivo = os.path.basename(caminho_original)
        yield f"Iniciando: {nome_arquivo}"

        # --- LÓGICA DE CAMINHO LONGO ---
        usando_temp = False
        caminho_trabalho = caminho_original

        if len(caminho_original) > 240:
            yield "[AVISO] Caminho longo. Usando temp..."
            try:
                temp_dir = tempfile.gettempdir()
                temp_nome = f"temp_{int(time.time())}_{nome_arquivo}"
                caminho_temp = os.path.join(temp_dir, temp_nome)
                shutil.copy2(caminho_original, caminho_temp)
                caminho_trabalho = caminho_temp
                usando_temp = True
            except Exception as e:
                yield f"[ERRO CRÍTICO] Falha ao criar temp: {e}"
                yield "ERRO"
                return

        # Inicializa Excel Invisível
        app = xw.App(visible=False)

        try:
            wb = app.books.open(caminho_trabalho)

            # 1. Validação de Abas
            sheet_name_source = "Ficha Técnica Padrão"
            sheet_names = [s.name for s in wb.sheets]

            if sheet_name_source not in sheet_names:
                yield f"[ERRO] Aba '{sheet_name_source}' não encontrada."
                wb.close()
                if usando_temp and os.path.exists(caminho_trabalho):
                    try: os.remove(caminho_trabalho)
                    except Exception: pass
                yield "ERRO"
                return

            source_sheet = wb.sheets[sheet_name_source]

            # 2. Prepara Destino
            sheet_name_dest = "Especificações técnicas copiar"
            if sheet_name_dest in sheet_names:
                yield "Recriando aba de destino..."
                wb.sheets[sheet_name_dest].delete()

            dest_sheet = wb.sheets.add(sheet_name_dest, after=wb.sheets[-1])

            # Cabeçalhos
            dest_sheet.range('A1').value = ["Pergunta", "Resposta (Espanhol s/ caracteres especiais)", "Resposta (Português s/ caracteres especiais)"]

            item_counter = 1
            current_row = 79

            # 3. Loop de Tradução
            yield "Lendo e traduzindo linhas..."

            while True:
                # Checagem de parada
                if self.stop_flag:
                    yield "[PARADO] Interrupção solicitada pelo usuário."
                    wb.close()
                    if usando_temp and os.path.exists(caminho_trabalho):
                        try: os.remove(caminho_trabalho)
                        except Exception: pass
                    yield "PARADO"  # ENVIA SINAL PARA O APP ABORTAR O LOOP
                    return

                # Leitura (Coluna 3 = C)
                pergunta_val = source_sheet.range((current_row, 3)).value

                if pergunta_val is None or str(pergunta_val).strip() == "":
                    break  # Fim dos dados

                # Processamento Texto
                pergunta_text = str(pergunta_val).split('(', 1)[0].strip().rstrip(':. ')

                # Leitura Resposta (Coluna 13 = M)
                resposta_val = source_sheet.range((current_row, 13)).value

                yield f"Traduzindo item {item_counter}: {pergunta_text[:30]}..."

                resposta_pt = self._remover_caracteres_especiais(resposta_val)

                # Delay original
                time.sleep(1.0)

                # Tradução
                resposta_es_raw = self._traduzir_hibrido(resposta_val)
                resposta_es = self._remover_caracteres_especiais(resposta_es_raw)

                # Escrita
                dest_row = item_counter + 1
                dest_sheet.range(dest_row, 1).value = pergunta_text
                dest_sheet.range(dest_row, 2).value = resposta_es
                dest_sheet.range(dest_row, 3).value = resposta_pt

                item_counter += 1
                current_row += 1

            # 4. Formatação Visual
            yield "Aplicando formatação..."
            last_row = item_counter

            # Larguras
            dest_sheet.range('A:A').column_width = 40
            dest_sheet.range('B:C').column_width = 50

            if last_row >= 2:
                dest_sheet.range(f'2:{last_row}').row_height = 50

            # Alinhamento Geral
            full_range = dest_sheet.range(f'A1:C{last_row}')
            full_range.api.WrapText = True
            full_range.api.VerticalAlignment = -4108  # xlCenter

            # Cabeçalho Estilo
            header = dest_sheet.range('A1:C1')
            header.api.Font.Bold = True
            header.api.HorizontalAlignment = -4108  # xlCenter
            header.color = (47, 117, 181)  # Azul Escuro
            header.api.Font.Color = 0xFFFFFF  # Branco

            # Zebrado e Bordas
            for i in range(2, last_row + 1):
                # Checagem extra de parada durante formatação
                if self.stop_flag:
                    wb.close()
                    yield "PARADO"
                    return

                row_range = dest_sheet.range(f'A{i}:C{i}')
                try:
                    row_range.api.Borders.LineStyle = 1
                    row_range.api.Borders.Weight = 2
                except Exception: pass

                if i % 2 == 0:
                    row_range.color = (221, 235, 247)  # Azul muito claro
                else:
                    row_range.color = (189, 215, 238)  # Azul claro

            # Salvar
            wb.save()
            wb.close()

            # Restaurar se Temp
            if usando_temp:
                yield "Restaurando arquivo original..."
                try:
                    shutil.copy2(caminho_trabalho, caminho_original)
                    os.remove(caminho_trabalho)
                    yield "Arquivo original atualizado."
                except Exception as e:
                    yield f"[ERRO] Falha ao mover arquivo temp: {e}"
                    yield "ERRO_MOVER"
                    return

            yield f"[SUCESSO] {nome_arquivo} concluído."
            yield "SUCESSO"

        except Exception as e:
            yield f"[ERRO FATAL] {e}"
            try: wb.close()
            except Exception: pass
            if usando_temp and os.path.exists(caminho_trabalho):
                try: os.remove(caminho_trabalho)
                except Exception: pass
            yield "ERRO"

        finally:
            # Garante que o processo do Excel feche
            if app.books.count == 0:
                app.quit()
